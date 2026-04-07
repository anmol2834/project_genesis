"""
emailservice — Write-Ahead Buffer (DB Protection Layer)
========================================================
Absorbs DB write spikes by accumulating rows in memory and flushing
in bulk every WRITE_BUFFER_FLUSH_MS milliseconds.

Problem it solves:
  - Direct DB writes on every batch → connection pool exhaustion under load
  - Bursty writes → DB CPU spikes → query latency increases for reads

Design:
  - In-process deque per table (messages + conversations)
  - Background flush task: every 75ms OR when buffer hits max size
  - Flush calls the same bulk INSERT logic as StorageWorker
  - Thread-safe via asyncio.Lock (single event loop per process)
  - If flush fails: records stay in buffer, retry on next flush cycle
  - Hard limit: if buffer > MAX_BUFFER_ROWS, flush synchronously (backpressure)

Memory estimate:
  - 1 message row ≈ 2KB average
  - MAX_BUFFER_ROWS = 2000 → ~4MB max memory per worker
  - Flush every 75ms → max 75ms additional write latency
"""
from __future__ import annotations
import asyncio, logging, time
from collections import deque
from typing import Callable, Awaitable

from metrics import M

logger = logging.getLogger("emailservice.write_buffer")

# ── Tuning ────────────────────────────────────────────────────────────────────
FLUSH_INTERVAL_MS = 500      # flush every 500ms — was 75ms (saves ~85% idle iterations)
MAX_BUFFER_ROWS   = 2_000    # force-flush above this (backpressure)
MAX_FLUSH_ROWS    = 500      # max rows per flush call


FlushFn = Callable[[list[dict]], Awaitable[int]]


class WriteBuffer:
    """
    Generic write-ahead buffer for a single table.

    Usage:
        buf = WriteBuffer("es_messages", flush_fn=storage_worker._bulk_insert_messages)
        await buf.start()
        await buf.add(row_dict)
        # background task flushes automatically
        await buf.stop()  # flushes remaining rows on shutdown
    """

    def __init__(self, table: str, flush_fn: FlushFn):
        self._table    = table
        self._flush_fn = flush_fn
        self._buf: deque[dict] = deque()
        self._lock     = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._running  = False
        self._total_flushed = 0
        self._total_errors  = 0

    async def start(self) -> None:
        self._running = True
        self._task    = asyncio.create_task(self._flush_loop())
        logger.info("[WriteBuffer:%s] started (flush_ms=%d max=%d)",
                    self._table, FLUSH_INTERVAL_MS, MAX_BUFFER_ROWS)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        # Drain remaining rows
        await self._flush_now()
        logger.info("[WriteBuffer:%s] stopped | flushed=%d errors=%d",
                    self._table, self._total_flushed, self._total_errors)

    async def add(self, row: dict) -> None:
        """Add a row to the buffer. Triggers sync flush if buffer is full."""
        async with self._lock:
            self._buf.append(row)
            size = len(self._buf)

        if size >= MAX_BUFFER_ROWS:
            # Backpressure: flush synchronously to protect memory
            await self._flush_now()

    async def add_many(self, rows: list[dict]) -> None:
        """Add multiple rows at once."""
        async with self._lock:
            self._buf.extend(rows)
            size = len(self._buf)

        if size >= MAX_BUFFER_ROWS:
            await self._flush_now()

    async def _flush_loop(self) -> None:
        interval = FLUSH_INTERVAL_MS / 1000.0
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self._flush_now()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[WriteBuffer:%s] flush loop error: %s", self._table, e)

    async def _flush_now(self) -> None:
        """Drain up to MAX_FLUSH_ROWS from the buffer and write to DB."""
        async with self._lock:
            if not self._buf:
                return
            # Take up to MAX_FLUSH_ROWS
            batch = []
            for _ in range(min(MAX_FLUSH_ROWS, len(self._buf))):
                batch.append(self._buf.popleft())

        if not batch:
            return

        t0 = time.monotonic()
        try:
            inserted = await self._flush_fn(batch)
            self._total_flushed += inserted
            elapsed_ms = (time.monotonic() - t0) * 1000
            M.db_writes.labels(table=self._table, status="ok").inc(inserted)
            M.db_write_batch_size.labels(table=self._table).observe(len(batch))
            logger.debug("[WriteBuffer:%s] flushed %d rows in %.1fms",
                         self._table, len(batch), elapsed_ms)
        except Exception as e:
            self._total_errors += len(batch)
            M.db_writes.labels(table=self._table, status="error").inc(len(batch))
            logger.error("[WriteBuffer:%s] flush failed (%d rows): %s",
                         self._table, len(batch), e)
            # Put rows back at front of buffer for retry
            async with self._lock:
                for row in reversed(batch):
                    self._buf.appendleft(row)

    @property
    def size(self) -> int:
        return len(self._buf)

    @property
    def stats(self) -> dict:
        return {
            "table":          self._table,
            "buffered":       len(self._buf),
            "total_flushed":  self._total_flushed,
            "total_errors":   self._total_errors,
        }
