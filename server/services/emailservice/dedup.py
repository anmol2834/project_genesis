"""
emailservice — Dedup System
Replaces Redis per-message keys with:
  1. Time-bucketed Bloom filter (in-process, zero Redis cost)
  2. DB-level unique constraint (safety net, catches bloom false negatives)

Bloom filter design:
  - Capacity: 10M entries per 24h bucket
  - Error rate: 0.1% false positives (acceptable — DB constraint catches them)
  - Memory: ~17 MB per bucket (2 buckets active at any time = 34 MB)
  - Rotation: new bucket every 24h, old bucket kept for overlap window

No Redis required for dedup — eliminates the Redis connection pool bottleneck.
"""
from __future__ import annotations
import math, time, threading
from typing import Optional
import mmh3  # MurmurHash3 — fast, uniform distribution

import config as cfg

# ── Bloom filter implementation ───────────────────────────────────────────────

class BloomFilter:
    """
    Simple in-process Bloom filter using MurmurHash3.
    Thread-safe via a lock (single process; use separate instances per worker).
    """
    def __init__(self, capacity: int, error_rate: float):
        self.capacity   = capacity
        self.error_rate = error_rate
        # Optimal bit array size and hash count
        self.size       = self._optimal_size(capacity, error_rate)
        self.hash_count = self._optimal_hash_count(self.size, capacity)
        self._bits      = bytearray(self.size // 8 + 1)
        self._lock      = threading.Lock()
        self._count     = 0

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        return int(-n * math.log(p) / (math.log(2) ** 2))

    @staticmethod
    def _optimal_hash_count(m: int, n: int) -> int:
        return max(1, int((m / n) * math.log(2)))

    def _positions(self, item: str) -> list[int]:
        return [
            mmh3.hash(item, seed=i, signed=False) % self.size
            for i in range(self.hash_count)
        ]

    def add(self, item: str) -> None:
        with self._lock:
            for pos in self._positions(item):
                self._bits[pos // 8] |= (1 << (pos % 8))
            self._count += 1

    def __contains__(self, item: str) -> bool:
        for pos in self._positions(item):
            if not (self._bits[pos // 8] & (1 << (pos % 8))):
                return False
        return True

    @property
    def count(self) -> int:
        return self._count


# ── Time-bucketed dedup manager ───────────────────────────────────────────────

class DedupManager:
    """
    Manages two Bloom filter buckets (current + previous 24h window).
    Rotates automatically — zero maintenance required.

    Usage:
        dedup = DedupManager()
        if dedup.is_duplicate(message_id):
            return  # skip
        dedup.mark_seen(message_id)
    """
    _BUCKET_SECONDS = cfg.DEDUP_BUCKET_HOURS * 3600

    def __init__(self):
        self._current_bucket: int = self._bucket_id()
        self._current: BloomFilter = self._new_filter()
        self._previous: Optional[BloomFilter] = None
        self._lock = threading.Lock()

    def _bucket_id(self) -> int:
        return int(time.time()) // self._BUCKET_SECONDS

    def _new_filter(self) -> BloomFilter:
        return BloomFilter(cfg.DEDUP_BLOOM_CAPACITY, cfg.DEDUP_BLOOM_ERROR_RATE)

    def _maybe_rotate(self) -> None:
        """Rotate to a new bucket if the time window has passed."""
        now_bucket = self._bucket_id()
        if now_bucket != self._current_bucket:
            with self._lock:
                if now_bucket != self._current_bucket:
                    self._previous       = self._current
                    self._current        = self._new_filter()
                    self._current_bucket = now_bucket

    def is_duplicate(self, message_id: str) -> bool:
        """
        Returns True if message_id was seen in the current or previous bucket.
        False positives possible at 0.1% rate — DB constraint is the safety net.
        """
        self._maybe_rotate()
        return (message_id in self._current) or (
            self._previous is not None and message_id in self._previous
        )

    def mark_seen(self, message_id: str) -> None:
        """Mark a message_id as seen in the current bucket."""
        self._maybe_rotate()
        self._current.add(message_id)

    @property
    def stats(self) -> dict:
        return {
            "current_bucket":  self._current_bucket,
            "current_count":   self._current.count,
            "previous_count":  self._previous.count if self._previous else 0,
        }


# ── Process-level singleton ───────────────────────────────────────────────────
# Each worker process gets its own DedupManager (no cross-process sharing needed
# because DB constraint is the authoritative dedup — bloom is just a fast pre-filter).
_dedup: Optional[DedupManager] = None

def get_dedup() -> DedupManager:
    global _dedup
    if _dedup is None:
        _dedup = DedupManager()
    return _dedup
