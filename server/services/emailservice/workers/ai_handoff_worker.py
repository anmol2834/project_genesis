"""
emailservice — AI Handoff Worker
=================================
Reads from ai_events stream, publishes to automation_events stream.
automation_events is published to REDIS_URL (RedisLabs) — the same Redis
that automationservice reads from. This ensures cross-service event delivery
without requiring both services to share the same Redis instance.
"""
from __future__ import annotations
import asyncio
import json
import logging

import httpx
import redis.asyncio as aioredis

import config as cfg
from workers.base_worker import BaseWorker
from idempotency import get_idempotency_cache
from metrics import M, timer

logger = logging.getLogger("emailservice.ai_handoff")

TOPIC_AUTOMATION = "automation_events"
WAKE_CHANNEL     = "automation:wake"

# Dedicated Redis client for publishing to automationservice Redis (REDIS_URL)
_automation_redis: aioredis.Redis | None = None


async def _get_automation_redis() -> aioredis.Redis:
    """
    Get Redis client for automation_events stream.
    Uses REDIS_URL (RedisLabs) — same instance automationservice reads from.
    """
    global _automation_redis
    if _automation_redis is None:
        from shared.config import get_config
        url = get_config().REDIS_URL
        _automation_redis = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            max_connections=10,
        )
    return _automation_redis


class AIHandoffWorker(BaseWorker):
    topics   = [cfg.TOPIC_AI_EVENTS]
    group_id = cfg.CG_AI_HANDOFF

    def __init__(self):
        super().__init__()
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=60.0, write=5.0, pool=3.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=8),
        )

    async def stop(self) -> None:
        await self._http.aclose()
        global _automation_redis
        if _automation_redis:
            await _automation_redis.aclose()
            _automation_redis = None
        await super().stop()

    def _provider_label(self) -> str:
        return "ai"

    async def process_batch(self, records: list[dict]) -> None:
        async with timer("ai_handoff"):
            # Deduplicate by message_id, keep highest priority
            by_msg: dict[str, dict] = {}
            for rec in records:
                msg_id = rec.get("message_id", "") or rec.get("event_id", "")
                if not msg_id:
                    continue
                existing = by_msg.get(msg_id)
                if not existing or rec.get("_priority", 99) < existing.get("_priority", 99):
                    by_msg[msg_id] = rec

            sorted_events = sorted(by_msg.values(), key=lambda r: r.get("_priority", 99))

            idem = get_idempotency_cache()
            new_events = [
                rec for rec in sorted_events
                if not idem.check_and_mark(
                    "ai_handoff",
                    rec.get("message_id", "") or rec.get("event_id", "")
                )
            ]

            if not new_events:
                return

            ok = await self._publish_to_automation_redis(new_events)
            if not ok:
                # HTTP fallback
                sem = asyncio.Semaphore(16)
                await asyncio.gather(
                    *[self._http_fallback(rec, sem) for rec in new_events],
                    return_exceptions=True,
                )

    async def _publish_to_automation_redis(self, events: list[dict]) -> bool:
        """
        Publish to automation_events on REDIS_URL (RedisLabs).
        Uses Redis-based dedup (1h TTL) to prevent publishing same message twice
        across service restarts — in-process cache is lost on restart.
        """
        try:
            redis = await _get_automation_redis()

            # Redis-based dedup — survives service restarts
            truly_new = []
            for rec in events:
                msg_id = rec.get("message_id", "")
                if not msg_id:
                    truly_new.append(rec)
                    continue
                dedup_key = f"es:handoff:dedup:{msg_id}"
                # SET NX EX 3600 — only publish if not seen in last hour
                acquired = await redis.set(dedup_key, "1", nx=True, ex=3600)
                if acquired:
                    truly_new.append(rec)
                else:
                    logger.debug("Handoff dedup: msg=%s already published — skipping", msg_id[:12])

            if not truly_new:
                return True

            pipe = redis.pipeline(transaction=False)
            for rec in truly_new:
                payload = {
                    "conversation_id":    rec.get("conversation_id", ""),
                    "user_id":            rec.get("user_id", ""),
                    "message_id":         rec.get("message_id", ""),
                    "thread_id":          rec.get("thread_id", ""),
                    "provider":           rec.get("provider", ""),
                    "trace_id":           rec.get("trace_id", ""),
                    "automation_enabled": rec.get("automation_enabled", True),
                    "_priority":          rec.get("_priority", cfg.PRIORITY_MEDIUM),
                    "_schema_version":    2,
                    "ts":                 rec.get("ts") or __import__("time").time(),
                }
                pipe.xadd(
                    TOPIC_AUTOMATION,
                    {"data": json.dumps(payload)},
                    maxlen=10_000,
                    approximate=True,
                )
            # Wake signal in same pipeline
            pipe.publish(WAKE_CHANNEL, "1")
            await pipe.execute()
            logger.info("AI handoff → automation_events (REDIS_URL) | events=%d (deduped from %d)",
                        len(truly_new), len(events))
            return True
        except Exception as e:
            logger.warning("automation_events publish failed: %s — HTTP fallback", e)
            return False

    async def _http_fallback(self, rec: dict, sem: asyncio.Semaphore) -> None:
        """HTTP POST fallback — calls automationservice /process directly."""
        async with sem:
            cfg_obj = cfg.get_config()
            url = getattr(cfg_obj, "AUTOMATIONSERVICE_URL", "http://localhost:8010")
            payload = {
                "conversation_id":    rec.get("conversation_id", ""),
                "user_id":            rec.get("user_id", ""),
                "message_id":         rec.get("message_id", ""),
                "thread_id":          rec.get("thread_id", ""),
                "provider":           rec.get("provider", ""),
                "trace_id":           rec.get("trace_id", ""),
                "automation_enabled": rec.get("automation_enabled", True),
                "_priority":          rec.get("_priority", cfg.PRIORITY_MEDIUM),
            }
            try:
                resp = await self._http.post(f"{url}/process", json=payload)
                if resp.status_code == 200:
                    logger.info("HTTP fallback OK | conv=%s", rec.get("conversation_id", "?")[:8])
                    return
                logger.warning("HTTP fallback %d | url=%s", resp.status_code, url)
            except Exception as e:
                logger.error("HTTP fallback failed | url=%s: %s", url, e)
