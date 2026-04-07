"""
emailservice — AI Handoff Worker (v2 — Kafka-native)
=====================================================
Improvements:
  ✅ Primary path: publish to automation Kafka topic (zero HTTP dependency)
  ✅ Fallback path: HTTP POST if automation service doesn't consume Kafka
  ✅ Priority-aware: CRITICAL events processed before LOW
  ✅ Dedup: in-process idempotency cache (no Redis round-trip per event)
  ✅ Batch dedup: collapse multiple events for same conversation
  ✅ Metrics on handoff latency and errors

Architecture:
  ai_events (Kafka) → AIHandoffWorker → automation_events (Kafka)
                                      ↘ HTTP POST /ai/process (fallback)

The automation-service should consume from automation_events topic directly.
HTTP fallback ensures backward compatibility during migration.
"""
from __future__ import annotations
import asyncio, logging, time
from collections import defaultdict

import httpx

import config as cfg
from workers.base_worker import BaseWorker
from kafka_client import publish_batch, publish
from idempotency import get_idempotency_cache
from metrics import M, timer

logger = logging.getLogger("emailservice.ai_handoff")

# Dedicated Kafka topic for automation service to consume
TOPIC_AUTOMATION = "automation_events"


class AIHandoffWorker(BaseWorker):
    topics   = [cfg.TOPIC_AI_EVENTS]
    group_id = cfg.CG_AI_HANDOFF

    def __init__(self):
        super().__init__()
        self._automation_url = cfg.get_config().AUTOMATION_SERVICE_URL
        # Persistent HTTP client for fallback path
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=60.0, write=5.0, pool=3.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=8),
        )

    async def stop(self) -> None:
        await self._http.aclose()
        await super().stop()

    def _provider_label(self) -> str:
        return "ai"

    async def process_batch(self, records: list[dict]) -> None:
        async with timer("ai_handoff"):
            # Deduplicate by conversation_id — keep highest priority per conv
            by_conv: dict[str, dict] = {}
            for rec in records:
                conv_id = rec.get("conversation_id", "")
                if not conv_id:
                    continue
                existing = by_conv.get(conv_id)
                if not existing or rec.get("_priority", 99) < existing.get("_priority", 99):
                    by_conv[conv_id] = rec

            # Sort by priority (CRITICAL first)
            sorted_events = sorted(by_conv.values(), key=lambda r: r.get("_priority", 99))

            # Idempotency check
            idem = get_idempotency_cache()
            new_events = []
            for rec in sorted_events:
                conv_id = rec["conversation_id"]
                if not idem.check_and_mark("ai_handoff", conv_id):
                    new_events.append(rec)

            if not new_events:
                return

            # Primary: publish to automation_events Kafka topic
            kafka_ok = await self._publish_to_kafka(new_events)

            # Fallback: HTTP POST for events that failed Kafka publish
            if not kafka_ok:
                sem = asyncio.Semaphore(16)
                tasks = [self._http_fallback(rec, sem) for rec in new_events]
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _publish_to_kafka(self, events: list[dict]) -> bool:
        """
        Publish to automation_events Kafka topic.
        Automation-service consumes this topic directly — zero HTTP coupling.
        """
        try:
            to_publish = [
                (
                    {
                        "conversation_id": rec["conversation_id"],
                        "user_id":         rec.get("user_id", ""),
                        "message_id":      rec.get("message_id", ""),
                        "thread_id":       rec.get("thread_id", ""),
                        "provider":        rec.get("provider", ""),
                        "trace_id":        rec.get("trace_id", ""),
                        "_priority":       rec.get("_priority", cfg.PRIORITY_MEDIUM),
                        "_schema_version": 2,
                    },
                    rec.get("user_id", ""),
                )
                for rec in events
            ]
            await publish_batch(TOPIC_AUTOMATION, to_publish)
            logger.info("AI handoff → Kafka | events=%d", len(events))
            return True
        except Exception as e:
            logger.warning("Kafka AI handoff failed, falling back to HTTP: %s", e)
            return False

    async def _http_fallback(self, rec: dict, sem: asyncio.Semaphore) -> None:
        """HTTP POST fallback for backward compatibility."""
        async with sem:
            conv_id  = rec["conversation_id"]
            endpoint = f"{self._automation_url}/ai/process"
            payload  = {
                "conversation_id": conv_id,
                "trace_id":        rec.get("trace_id", ""),
            }
            t0 = time.monotonic()
            for attempt in range(2):
                try:
                    resp = await self._http.post(endpoint, json=payload)
                    M.processing_latency.labels(stage="ai_http").observe(time.monotonic() - t0)
                    if resp.status_code == 200:
                        logger.info("AI HTTP fallback OK | conv=%s", conv_id[:8])
                        return
                    logger.warning("AI HTTP %d | conv=%s", resp.status_code, conv_id[:8])
                    return
                except httpx.ConnectError:
                    if attempt == 0:
                        await asyncio.sleep(2)
                    else:
                        logger.error("Automation unreachable | conv=%s", conv_id[:8])
                except httpx.TimeoutException:
                    logger.warning("Automation timeout | conv=%s", conv_id[:8])
                    return
                except Exception as e:
                    logger.error("AI HTTP error | conv=%s: %s", conv_id[:8], e)
                    return
