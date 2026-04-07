"""
emailservice — Dynamic Configuration Engine
============================================
Allows live tuning of rate limits, batch sizes, and thresholds
WITHOUT redeployment. Values stored in Redis, refreshed every 30s.

Fallback: if Redis unavailable or key missing → use static config.py values.

Usage:
    from dynamic_config import dyn
    batch_size = dyn.get_int("PROCESS_BATCH_SIZE", default=100)
    rate_limit = dyn.get_float("RATE_GMAIL_GLOBAL_PER_SEC", default=200.0)

To update a value (from Redis CLI or admin endpoint):
    SET es:config:PROCESS_BATCH_SIZE 150
    SET es:config:RATE_GMAIL_GLOBAL_PER_SEC 150.0
    SET es:config:BACKPRESSURE_LAG_THRESHOLD 30000

Keys are namespaced under "es:config:" to avoid collisions.
"""
from __future__ import annotations
import asyncio, logging, time
from typing import Any, Optional

import config as cfg

logger = logging.getLogger("emailservice.dynamic_config")

_NAMESPACE  = "es:config:"
_REFRESH_S  = 300   # refresh from Redis every 5 minutes — was 30s


class DynamicConfig:
    """
    Live-tunable configuration layer.
    Reads from Redis with a 30s TTL cache. Falls back to static config.
    """

    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._lock   = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start background refresh task."""
        self._task = asyncio.create_task(self._refresh_loop())
        logger.info("DynamicConfig started (refresh=%ds)", _REFRESH_S)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _refresh_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_REFRESH_S)
                await self._refresh_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("DynamicConfig refresh error: %s", e)

    async def _refresh_all(self) -> None:
        """Refresh all known config keys from Redis."""
        keys = [
            "PROCESS_BATCH_SIZE", "FETCH_BATCH_SIZE", "WORKER_CONCURRENCY",
            "RATE_GMAIL_GLOBAL_PER_SEC", "RATE_GMAIL_PER_USER_PER_SEC",
            "RATE_OUTLOOK_GLOBAL_PER_SEC", "RATE_OUTLOOK_PER_USER_PER_SEC",
            "BACKPRESSURE_LAG_THRESHOLD", "BACKPRESSURE_LAG_CRITICAL",
            "BUFFER_FLUSH_INTERVAL_S", "BUFFER_MAX_SIZE",
            "HOT_USER_EMAILS_PER_MIN", "DLQ_MAX_RETRIES",
            "STREAM_MAXLEN",
        ]
        try:
            from shared.cache import get_redis_client
            redis = get_redis_client()
            pipe  = redis.pipeline(transaction=False)
            for k in keys:
                pipe.get(f"{_NAMESPACE}{k}")
            results = await pipe.execute()
            now = time.monotonic()
            async with self._lock:
                for k, v in zip(keys, results):
                    if v is not None:
                        self._cache[k] = (v, now + _REFRESH_S * 2)
        except Exception:
            pass  # fail silently — static config is the fallback

    def get_int(self, key: str, default: int) -> int:
        val = self._get_raw(key)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float) -> float:
        val = self._get_raw(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool) -> bool:
        val = self._get_raw(key)
        if val is None:
            return default
        return str(val).lower() in ("1", "true", "yes")

    def _get_raw(self, key: str) -> Optional[str]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            self._cache.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 86400) -> bool:
        """Set a dynamic config value (admin use)."""
        try:
            from shared.cache import get_redis_client
            redis = get_redis_client()
            await redis.setex(f"{_NAMESPACE}{key}", ttl, str(value))
            async with self._lock:
                self._cache[key] = (str(value), time.monotonic() + _REFRESH_S * 2)
            logger.info("DynamicConfig updated: %s = %s", key, value)
            return True
        except Exception as e:
            logger.error("DynamicConfig set failed: %s", e)
            return False

    async def get_all(self) -> dict:
        """Return all currently cached dynamic values."""
        now = time.monotonic()
        return {
            k: v for k, (v, exp) in self._cache.items()
            if now <= exp
        }


# ── Process-level singleton ───────────────────────────────────────────────────
dyn = DynamicConfig()
