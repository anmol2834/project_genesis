"""
emailservice — Base Worker (Event-Driven, Zero Idle Cost)
==========================================================
Architecture:
  1. start()     → drain startup backlog
  2. _wait()     → sleep on asyncio.Event (0 Redis commands while idle)
  3. _drain()    → XRANGE all messages → process_batch() → XDEL
  4. goto 2

No XREADGROUP. No XAUTOCLAIM. No blocking Redis calls.
No periodic timers. No consumer groups.

Workers wake ONLY when:
  - publish() signals the asyncio.Event (new message arrived)
  - A retry is due (in-process timer, no Redis)
  - stop() is called

Redis command budget:
  Idle:   0 commands/sec
  Active: 1 XRANGE + N XDEL per batch (drain)
  Retry:  in-process queue, no Redis until re-published to DLQ

Scalability:
  Multiple workers can run on different shards (N_SHARDS > 1).
  Each shard has its own asyncio.Event — no locking, no conflicts.
  Deterministic partitioning via user_id hash ensures no duplicates.
"""
from __future__ import annotations
import asyncio, logging, time
from abc import ABC, abstractmethod

import config as cfg
from stream_client import EventDrivenConsumer, _stream_events, _wake_key, publish
from metrics import M

logger = logging.getLogger("emailservice.worker")


async def _wait_for(source: asyncio.Event, target: asyncio.Event) -> None:
    """Wait for source event, then set target. Used to fan-in multiple events."""
    await source.wait()
    target.set()


class BaseWorker(ABC):
    topics:   list[str]
    group_id: str   # kept for compat; not used in event-driven model

    def __init__(self):
        self._consumer: EventDrivenConsumer | None = None
        self._running   = False
        self._processed = 0
        self._errors    = 0
        self._dlq_sent  = 0

    async def start(self) -> None:
        self._consumer = EventDrivenConsumer(self.topics)
        await self._consumer.start()
        self._running = True
        logger.info("[%s] started (event-driven) | streams=%s",
                    self.__class__.__name__, self.topics)

        # Drain startup backlog — catches events from previous crash
        await self._drain_and_process()

        # Main event loop
        await self._event_loop()

    async def stop(self) -> None:
        logger.info("[%s] stopping...", self.__class__.__name__)
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        logger.info("[%s] stopped | processed=%d errors=%d dlq=%d",
                    self.__class__.__name__, self._processed, self._errors, self._dlq_sent)

    async def _event_loop(self) -> None:
        """
        Sleep until woken by publish() or a retry becoming due.
        Zero Redis commands while sleeping.
        """
        while self._running:
            try:
                # Calculate wait timeout: finite if retries are pending, else None (infinite)
                timeout: float | None = None
                if self._consumer and self._consumer.has_pending_retries():
                    delay = self._consumer.next_retry_delay()
                    timeout = delay if delay > 0 else 0.001

                # Build one combined asyncio.Event per stream
                # We use a single "any stream woke" event for simplicity
                combined = asyncio.Event()

                async def _watch_streams():
                    """Set combined when any stream event fires."""
                    watchers = [
                        asyncio.create_task(_wait_for(_stream_events[_wake_key(s)], combined))
                        for s in self.topics
                    ]
                    try:
                        await combined.wait()
                    finally:
                        for t in watchers:
                            t.cancel()

                if timeout is not None:
                    try:
                        await asyncio.wait_for(_watch_streams(), timeout=timeout)
                    except asyncio.TimeoutError:
                        pass  # retry is due — fall through to drain
                else:
                    await _watch_streams()

                if not self._running:
                    break

                # Clear stream events before draining
                for s in self.topics:
                    _stream_events[_wake_key(s)].clear()

                await self._drain_and_process()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[%s] event loop error: %s", self.__class__.__name__, e, exc_info=True)
                await asyncio.sleep(1)

    async def _drain_and_process(self) -> None:
        """Drain all pending messages and process them in one batch."""
        if not self._consumer:
            return
        try:
            records = await self._consumer.drain_once()
            if not records:
                return

            t0 = time.monotonic()
            failed_records: list[dict] = []

            try:
                await self.process_batch(records)
                self._processed += len(records)
                M.messages_processed.labels(
                    provider=self._provider_label(), status="ok"
                ).inc(len(records))
            except Exception as e:
                self._errors += len(records)
                failed_records = records
                logger.error("[%s] batch error: %s", self.__class__.__name__, e, exc_info=True)
                M.messages_processed.labels(
                    provider=self._provider_label(), status="error"
                ).inc(len(records))

            M.processing_latency.labels(
                stage=self.__class__.__name__.lower()
            ).observe(time.monotonic() - t0)

            # Handle failures: retry with backoff, DLQ after max retries
            for rec in failed_records:
                retry_count = rec.get("_retry_count", 0) + 1
                if retry_count > cfg.DLQ_MAX_RETRIES:
                    await self._send_to_dlq([rec], reason="max_retries_exceeded")
                else:
                    self._consumer.requeue(rec, reason="batch_error")

        except Exception as e:
            logger.error("[%s] drain error: %s", self.__class__.__name__, e, exc_info=True)

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
            "processed": self._processed,
            "errors":    self._errors,
            "dlq_sent":  self._dlq_sent,
            "running":   self._running,
        }
