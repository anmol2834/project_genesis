"""
emailservice — Strong Idempotency Cache
Guarantees near exactly-once processing across Kafka retries.

Key: provider + ":" + message_id  (globally unique per provider)
Storage: in-process LRU cache (fast) + DB constraint (authoritative)

Why not Redis?
  - Redis adds network latency on every message
  - In-process LRU is ~0ms and handles 99.9% of duplicates
  - DB constraint catches the 0.1% that slip through (cross-process)

LRU eviction: oldest entries evicted when cache hits IDEMPOTENCY_CACHE_SIZE.
TTL: entries expire after IDEMPOTENCY_TTL_S (default 1h).
"""
from __future__ import annotations
import time, threading
from collections import OrderedDict
from typing import Optional

import config as cfg
from metrics import M


class IdempotencyCache:
    """
    Thread-safe LRU cache with TTL for idempotency keys.
    """
    def __init__(self, max_size: int = cfg.IDEMPOTENCY_CACHE_SIZE, ttl_s: float = cfg.IDEMPOTENCY_TTL_S):
        self._max_size = max_size
        self._ttl      = ttl_s
        # OrderedDict: key → expiry_timestamp
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock  = threading.Lock()

    @staticmethod
    def make_key(provider: str, message_id: str) -> str:
        """Build idempotency key from provider + message_id."""
        return f"{provider}:{message_id}"

    def is_seen(self, key: str) -> bool:
        """Returns True if key was seen and has not expired."""
        with self._lock:
            expiry = self._cache.get(key)
            if expiry is None:
                return False
            if time.monotonic() > expiry:
                # Expired — remove and treat as unseen
                del self._cache[key]
                return False
            # Move to end (LRU: recently used = keep)
            self._cache.move_to_end(key)
            return True

    def mark_seen(self, key: str) -> None:
        """Mark key as seen. Evicts oldest entry if cache is full."""
        with self._lock:
            expiry = time.monotonic() + self._ttl
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = expiry
                return
            self._cache[key] = expiry
            # Evict oldest if over capacity
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def check_and_mark(self, provider: str, message_id: str) -> bool:
        """
        Atomic check-and-mark.
        Returns True if this is a DUPLICATE (already seen).
        Returns False if this is NEW (and marks it as seen).
        """
        key = self.make_key(provider, message_id)
        with self._lock:
            expiry = self._cache.get(key)
            if expiry is not None and time.monotonic() <= expiry:
                self._cache.move_to_end(key)
                M.messages_deduped.labels(layer="idempotency").inc()
                return True  # duplicate
            # New — mark seen
            self._cache[self.make_key(provider, message_id)] = time.monotonic() + self._ttl
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
            return False  # new

    @property
    def size(self) -> int:
        return len(self._cache)


# ── Process-level singleton ───────────────────────────────────────────────────
_cache: Optional[IdempotencyCache] = None

def get_idempotency_cache() -> IdempotencyCache:
    global _cache
    if _cache is None:
        _cache = IdempotencyCache()
    return _cache
