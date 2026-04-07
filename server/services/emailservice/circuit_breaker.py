"""
emailservice — Circuit Breaker for External APIs
=================================================
Prevents cascading failures when Gmail/Outlook APIs slow down or fail.

States:
  CLOSED   → normal operation, requests pass through
  OPEN     → failure threshold exceeded, requests blocked immediately
  HALF_OPEN → probe state, one request allowed to test recovery

Algorithm:
  - Track failure rate over a sliding window (last N calls)
  - If failure_rate > threshold → OPEN (block all calls)
  - After reset_timeout → HALF_OPEN (allow one probe)
  - If probe succeeds → CLOSED; if fails → OPEN again

Design:
  - Per-provider circuit breaker (Gmail, Outlook separate)
  - In-process (no Redis) — each worker has its own breaker
  - asyncio.Lock — safe for concurrent async callers
  - Metrics on state transitions
"""
from __future__ import annotations
import asyncio, time, logging
from collections import deque
from enum import Enum
from typing import Optional

from metrics import M

logger = logging.getLogger("emailservice.circuit_breaker")


class CBState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Sliding-window circuit breaker.

    Usage:
        cb = CircuitBreaker("gmail", failure_threshold=0.5, window=20, reset_timeout=60)
        if not await cb.allow_request():
            raise RuntimeError("Circuit open — Gmail API unavailable")
        try:
            result = await call_gmail_api()
            await cb.record_success()
        except Exception:
            await cb.record_failure()
            raise
    """

    def __init__(
        self,
        name: str,
        failure_threshold: float = 0.5,   # 50% failure rate → OPEN
        window: int = 20,                  # sliding window size (calls)
        reset_timeout: float = 60.0,       # seconds before HALF_OPEN probe
        min_calls: int = 5,                # minimum calls before evaluating
    ):
        self.name              = name
        self._threshold        = failure_threshold
        self._window           = window
        self._reset_timeout    = reset_timeout
        self._min_calls        = min_calls
        self._state            = CBState.CLOSED
        self._results: deque[bool] = deque(maxlen=window)  # True=success, False=failure
        self._opened_at: float = 0.0
        self._lock             = asyncio.Lock()

    async def allow_request(self) -> bool:
        """Returns True if the request should proceed."""
        async with self._lock:
            if self._state == CBState.CLOSED:
                return True

            if self._state == CBState.OPEN:
                if time.monotonic() - self._opened_at >= self._reset_timeout:
                    self._state = CBState.HALF_OPEN
                    logger.info("[CB:%s] → HALF_OPEN (probing)", self.name)
                    return True  # allow one probe
                return False  # still open

            # HALF_OPEN: only one probe at a time
            return True

    async def record_success(self) -> None:
        async with self._lock:
            self._results.append(True)
            if self._state == CBState.HALF_OPEN:
                self._state = CBState.CLOSED
                self._results.clear()
                logger.info("[CB:%s] → CLOSED (probe succeeded)", self.name)

    async def record_failure(self) -> None:
        async with self._lock:
            self._results.append(False)
            if self._state == CBState.HALF_OPEN:
                self._state    = CBState.OPEN
                self._opened_at = time.monotonic()
                logger.warning("[CB:%s] → OPEN (probe failed)", self.name)
                M.api_errors.labels(provider=self.name, status_code="circuit_open").inc()
                return

            if self._state == CBState.CLOSED and len(self._results) >= self._min_calls:
                failure_rate = self._results.count(False) / len(self._results)
                if failure_rate >= self._threshold:
                    self._state    = CBState.OPEN
                    self._opened_at = time.monotonic()
                    logger.warning(
                        "[CB:%s] → OPEN | failure_rate=%.0f%% window=%d",
                        self.name, failure_rate * 100, len(self._results),
                    )
                    M.api_errors.labels(provider=self.name, status_code="circuit_open").inc()

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def failure_rate(self) -> float:
        if not self._results:
            return 0.0
        return self._results.count(False) / len(self._results)

    @property
    def stats(self) -> dict:
        return {
            "name":         self.name,
            "state":        self._state.value,
            "failure_rate": round(self.failure_rate, 3),
            "window_size":  len(self._results),
            "opened_at":    self._opened_at,
        }


# ── Process-level singletons ──────────────────────────────────────────────────
_breakers: dict[str, CircuitBreaker] = {}

def get_circuit_breaker(provider: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a provider."""
    if provider not in _breakers:
        _breakers[provider] = CircuitBreaker(
            name=provider,
            failure_threshold=0.5,
            window=20,
            reset_timeout=60.0,
            min_calls=5,
        )
    return _breakers[provider]
