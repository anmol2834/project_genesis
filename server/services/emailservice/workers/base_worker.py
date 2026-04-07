"""
emailservice — Base Worker
===========================
Stream consumer using blocking XREADGROUP (30s timeout).

Idle cost: 1 Redis command per 30s per worker = ~5 commands/30s total.
Active: messages delivered instantly when published to stream.
"""
from __future__ import annotations
import asyncio, logging, time
from abc import ABC, abstractmethod
from typing import Optional

import config as cfg
from kafka_client import make_consumer, publish
from metrics import M

logger = logging.getLogger("emailservice.worker")


class BaseWorker(ABC):
    topics:   list[str]
    group_id: str

    def __init__(self):
        self._consumer  = None
        self._running   = False
        self._processed = 0
        self._errors    = 0
        self._dlq_sent  = 0

    async def start(self) -> None:
        self._consumer = make_consumer(self.topics, self.group_id)
        await self._consumer.start()
        self._running = True
        logger.info("[%s] started | streams=%s", self.__class__.__name__, self.topics)
        await self._run_loop()

    async def stop(self) -> None:
        logger.info("[%s] stopping...", self.__class__.__name__)
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        logger.info("[%s] stopped | processed=%d errors=%d",
                    self.__class__.__name__, self._processed, self._errors)

    async def _run_loop(self) -> None:
        while self._running:
            try:
                # Blocking read — returns when messages arrive OR after 30s timeout.
                # Zero idle cost: Redis holds the connection server-side.
                records_map = await self._consumer.getmany(
                    max_records=cfg.PROCESS_BATCH_SIZE,
                )

                if not records_map:
                    continue  # timeout with no messages — loop back to block again

                batch: list[dict] = []
                for msgs in records_map.values():
                    batch.extend(msgs)

                if not batch:
                    continue

                t0 = time.monotonic()
                try:
                    await self.process_batch(batch)
                    self._processed += len(batch)
                    M.messages_processed.labels(
                        provider=self._provider_label(), status="ok"
                    ).inc(len(batch))
                    await self._consumer.commit()
                except Exception as e:
                    self._errors += len(batch)
                    logger.error("[%s] batch error: %s", self.__class__.__name__, e, exc_info=True)
                    M.messages_processed.labels(
                        provider=self._provider_label(), status="error"
                    ).inc(len(batch))
                    # ACK anyway to prevent infinite redelivery — send to DLQ
                    await self._consumer.commit()
                    await self._send_to_dlq(batch, reason=str(e)[:200])

                M.processing_latency.labels(
                    stage=self.__class__.__name__.lower()
                ).observe(time.monotonic() - t0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[%s] loop error: %s", self.__class__.__name__, e, exc_info=True)
                await asyncio.sleep(2)

    async def _send_to_dlq(self, records: list[dict], reason: str) -> None:
        for rec in records:
            retry_count = rec.get("_retry_count", 0) + 1
            if retry_count > cfg.DLQ_MAX_RETRIES:
                try:
                    await publish(cfg.TOPIC_DLQ, {
                        **rec,
                        "_dlq_reason":  reason,
                        "_dlq_worker":  self.__class__.__name__,
                        "_dlq_ts":      time.time(),
                        "_retry_count": retry_count,
                    }, partition_key=rec.get("user_id", ""))
                    self._dlq_sent += 1
                    M.dlq_events.labels(reason="batch_error").inc()
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
