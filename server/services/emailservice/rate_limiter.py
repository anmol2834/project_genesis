"""
emailservice — Multi-Level Rate Limiter
Token bucket algorithm — async-safe, non-blocking.

Levels:
  1. Per-user rate limit  (e.g. 2 Gmail API calls/sec per user)
  2. Global provider rate limit (e.g. 200 Gmail calls/sec total)
  3. Worker-level throttle (adaptive based on backpressure)

Design:
  - Pure in-process (no Redis) — each worker process has its own limiter
  - asyncio.Lock per bucket — no thread contention
  - Tokens refill continuously (not in discrete intervals)
  - wait() is non-blocking to the event loop — uses asyncio.sleep
"""
from __future__ import annotations
import asyncio, time, logging
from collections import defaultdict
from typing import Optional

import config as cfg
from metrics import M

logger = logging.getLogger("emailservice.rate_limiter")


class TokenBucket:
    """
    Single token bucket.
    rate: tokens added per second
    capacity: max tokens (burst size)
    """
    __slots__ = ("rate", "capacity", "_tokens", "_last_refill", "_lock")

    def __init__(self, rate: float, capacity: Optional[float] = None):
        self.rate      = rate
        self.capacity  = capacity or rate * 2   # burst = 2s worth
        self._tokens   = self.capacity
        self._last_refill = time.monotonic()
        self._lock     = asyncio.Lock()

    def _refill(self) -> None:
        now     = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquire tokens. Returns wait time in seconds (0 if immediate).
        Non-blocking: caller awaits asyncio.sleep(wait) outside the lock.
        """
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            # Calculate wait time
            deficit = tokens - self._tokens
            wait    = deficit / self.rate
            # Optimistically consume — caller will sleep
            self._tokens = 0.0
            return wait

    async def wait_and_acquire(self, tokens: float = 1.0) -> None:
        """Acquire tokens, sleeping if necessary. Fully non-blocking."""
        wait = await self.acquire(tokens)
        if wait > 0:
            await asyncio.sleep(wait)


class RateLimiter:
    """
    Multi-level rate limiter for Gmail/Outlook API calls.

    Usage:
        limiter = get_rate_limiter()
        await limiter.acquire_gmail(user_id="abc123")
        # now safe to make Gmail API call
    """

    def __init__(self):
        # Global buckets (shared across all users in this process)
        self._gmail_global   = TokenBucket(cfg.RATE_GMAIL_GLOBAL_PER_SEC,   capacity=cfg.RATE_GMAIL_GLOBAL_PER_SEC * 3)
        self._outlook_global = TokenBucket(cfg.RATE_OUTLOOK_GLOBAL_PER_SEC, capacity=cfg.RATE_OUTLOOK_GLOBAL_PER_SEC * 3)

        # Per-user buckets (created on demand, GC'd when empty)
        self._gmail_per_user:   dict[str, TokenBucket] = {}
        self._outlook_per_user: dict[str, TokenBucket] = {}
        self._user_lock = asyncio.Lock()

    def _get_user_bucket(
        self, store: dict, user_id: str, rate: float
    ) -> TokenBucket:
        bucket = store.get(user_id)
        if bucket is None:
            bucket = TokenBucket(rate, capacity=rate * 5)  # 5s burst
            store[user_id] = bucket
        return bucket

    async def acquire_gmail(self, user_id: str, tokens: float = 1.0) -> None:
        """Acquire Gmail API quota for a user. Blocks if rate exceeded."""
        # Per-user limit
        async with self._user_lock:
            user_bucket = self._get_user_bucket(
                self._gmail_per_user, user_id, cfg.RATE_GMAIL_PER_USER_PER_SEC
            )
        await user_bucket.wait_and_acquire(tokens)

        # Global limit
        await self._gmail_global.wait_and_acquire(tokens)

    async def acquire_outlook(self, user_id: str, tokens: float = 1.0) -> None:
        async with self._user_lock:
            user_bucket = self._get_user_bucket(
                self._outlook_per_user, user_id, cfg.RATE_OUTLOOK_PER_USER_PER_SEC
            )
        await user_bucket.wait_and_acquire(tokens)
        await self._outlook_global.wait_and_acquire(tokens)

    def evict_user(self, user_id: str) -> None:
        """Remove per-user buckets when user is no longer active."""
        self._gmail_per_user.pop(user_id, None)
        self._outlook_per_user.pop(user_id, None)

    @property
    def stats(self) -> dict:
        return {
            "gmail_global_tokens":   round(self._gmail_global._tokens, 2),
            "outlook_global_tokens": round(self._outlook_global._tokens, 2),
            "tracked_gmail_users":   len(self._gmail_per_user),
            "tracked_outlook_users": len(self._outlook_per_user),
        }


# ── Process-level singleton ───────────────────────────────────────────────────
_limiter: Optional[RateLimiter] = None

def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
