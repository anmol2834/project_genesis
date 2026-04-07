"""
emailservice — Base Worker (Event-Driven, Startup-Flood-Safe)
==============================================================
Two-phase lifecycle:

  PHASE 1 — BACKLOG DRAIN (startup)
    Processes existing Redis stream messages at a controlled rate.
    Rate: BACKLOG_DRAIN_RATE messages/sec (default 50/sec).
    Batches: BACKLOG_BATCH_SIZE messages per cycle.
    Inter-batch delay: batch_size / rate_limit seconds.
    Prevents DB overload and API quota exhaustion on restart.
    Switches to PHASE 2 when stream is empty.

  PHASE 2 — REALTIME (live)
    Sleeps on asyncio.Event (0 Redis commands).
    Wakes only when publish() signals a new event.
    Drains the batch, processes, sleeps again.
    No polling. No timers. No background activity.

Retry model:
  Failed records go to in-process retry queue with exponential backoff.
  requeue() does NOT wake the event loop — the loop uses next_retry_delay()
  as a sleep timeout, preventing tight retry loops.
  After DLQ_MAX_RETRIES, records are published to the DLQ stream.

Scalability:
  N_SHARDS > 1: each worker can be pinned to a shard via user_id hash.
  No locks, no conflicts, deterministic partitioning.
"""
from __future__ import annotations
import asyncio, logging, time
from abc import ABC, abstractmethod

import config as cfg
from stream_client import EventDrivenConsumer, _stream_events, _wake_key, publish
from metrics import M

logger = logging.getLogger("emailservice.worker")

# ── Backlog drain tuning ──────────────────────────────────────────────────────
# Max messages processed per second during startup backlog drain.
# Keeps DB writes and API calls within safe limits during recovery.
BACKLOG_DRAIN_RATE  = 50    # messages/sec
BACKLOG_BATCH_SIZE  = 50    # messages per drain cycle during backlog
REALTIME_BATCH_SIZE = 500   # messages per drain cycle in live mode


class BaseWorker(ABC):
    topics:   list[str]
    group_id: str  # kept for compat; not used in event-driven model

    def __init__(self):
        self._consumer: EventDrivenConsumer | None = None
        self._running   = False
        self._processed = 0
        self._errors    = 0
        self._dlq_sent  = 0
        self._mode      = "backlog"  # "backlog" | "realtime"

    async def start(self) -> None:
        self._consumer = EventDrivenConsumer(self.topics)
        await self._consumer.start()
        self._running = True
        logger.info("[%s] started | streams=%s", self.__class__.__name__, self.topics)

        # Phase 1: controlled backlog drain
        await self._drain_backlog()

        # Phase 2: real-time event loop
        self._mode = "realtime"
        logger.info("[%s] backlog cleared — switching to real-time mode", self.__class__.__name__)
        await self._realtime_loop()

    async def stop(self) -> None:
        logger.info("[%s] stopping...", self.__class__.__name__)
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        logger.info("[%s] stopped | processed=%d errors=%d dlq=%d",
                    self.__class__.__name__, self._processed, self._errors, self._dlq_sent)

    # ── Phase 1: Controlled backlog drain ─────────────────────────────────────

    async def _drain_backlog(self) -> None:
        """
        Process startup backlog at BACKLOG_DRAIN_RATE messages/sec.
        Stops when stream is empty. Never floods DB or API.
        """
        if not self._consumer:
            return

        backlog = await self._consumer.backlog_size()
        if backlog == 0:
            logger.info("[%s] no backlog — skipping drain phase", self.__class__.__name__)
            return

        logger.info("[%s] draining backlog: %d messages at %d/sec",
                    self.__class__.__name__, backlog, BACKLOG_DRAIN_RATE)

        inter_batch_delay = BACKLOG_BATCH_SIZE / BACKLOG_DRAIN_RATE  # seconds between batches
        total_drained = 0

        while self._running:
            records = await self._consumer.drain_once(batch_size=BACKLOG_BATCH_SIZE)
            if not records:
                break  # backlog exhausted

            await self._process_records(records)
            total_drained += len(records)

            # Controlled inter-batch delay — prevents flood
            await asyncio.sleep(inter_batch_delay)

        if total_drained:
            logger.info("[%s] backlog drain complete: %d messages processed",
                        self.__class__.__name__, total_drained)

    # ── Phase 2: Real-time event loop ─────────────────────────────────────────

    async def _realtime_loop(self) -> None:
        """
        Sleep until woken by publish() or a retry becoming due.
        Zero Redis commands while sleeping.
        """
        while self._running:
            try:
                # Determine sleep duration
                if self._consumer and self._consumer.has_pending_retries():
                    # Sleep until earliest retry is due
                    delay = self._consumer.next_retry_delay()
                    if delay > 0:
                        await self._sleep_or_wake(delay)
                    # Fall through to drain (retries may be due now)
                else:
                    # Sleep indefinitely until publish() wakes us
                    await self._sleep_or_wake(None)

                if not self._running:
                    break

                # Clear events before draining so new events during processing re-set them
                for s in self.topics:
                    _stream_events[_wake_key(s)].clear()

                records = await self._consumer.drain_once(batch_size=REALTIME_BATCH_SIZE)
                if records:
                    await self._process_records(records)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[%s] realtime loop error: %s", self.__class__.__name__, e, exc_info=True)
                await asyncio.sleep(1)

    async def _sleep_or_wake(self, timeout: float | None) -> None:
        """
        Sleep until any stream event fires OR timeout expires.
        Uses a single combined asyncio.Event to avoid task leaks.
        """
        combined = asyncio.Event()
        watchers: list[asyncio.Task] = []

        async def _watch(src: asyncio.Event) -> None:
            await src.wait()
            combined.set()

        for s in self.topics:
            evt = _stream_events[_wake_key(s)]
            watchers.append(asyncio.create_task(_watch(evt)))

        try:
            if timeout is not None:
                try:
                    await asyncio.wait_for(combined.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    pass
            else:
                await combined.wait()
        finally:
            for t in watchers:
                t.cancel()
            # Suppress CancelledError from cancelled watchers
            await asyncio.gather(*watchers, return_exceptions=True)

    # ── Shared processing ─────────────────────────────────────────────────────

    async def _process_records(self, records: list[dict]) -> None:
        if not records:
            return
        t0 = time.monotonic()
        failed: list[dict] = []

        try:
            await self.process_batch(records)
            self._processed += len(records)
            M.messages_processed.labels(
                provider=self._provider_label(), status="ok"
            ).inc(len(records))
        except Exception as e:
            self._errors += len(records)
            failed = records
            logger.error("[%s] batch error: %s", self.__class__.__name__, e, exc_info=True)
            M.messages_processed.labels(
                provider=self._provider_label(), status="error"
            ).inc(len(records))

        M.processing_latency.labels(
            stage=self.__class__.__name__.lower()
        ).observe(time.monotonic() - t0)

        for rec in failed:
            retry_count = rec.get("_retry_count", 0) + 1
            if retry_count > cfg.DLQ_MAX_RETRIES:
                await self._send_to_dlq([rec], reason="max_retries_exceeded")
            else:
                if self._consumer:
                    self._consumer.requeue(rec, reason="batch_error")

    async def _send_to_dlq(self, records: list[dict], reason: str) -> None:
        for rec in records:
            try:
                await publish(cfg.TOPIC_DLQ, {
                    **{k: v for k, v in rec.items() if not k.startswith("_")},
                    "_dlq_reason": reason,
                    "_dlq_worker": self.__class__.__name__,
                    "_dlq_ts":     time.time(),
                }, partition_key=rec.get("user_id", ""))
                self._dlq_sent += 1
                M.dlq_events.labels(reason=reason).inc()
            except Exception as e:
                logger.error("[%s] DLQ publish failed: %s", self.__class__.__name__, e)

    @abstractmethod
    async def process_batch(self, records: list[dict]) -> None: ...

    def _provider_label(self) -> str:
        return "unknown"

    @property
    def stats(self) -> dict:
        return {
            "worker":    self.__class__.__name__,
            "mode":      self._mode,
            "processed": self._processed,
            "errors":    self._errors,
            "dlq_sent":  self._dlq_sent,
            "running":   self._running,
        }
