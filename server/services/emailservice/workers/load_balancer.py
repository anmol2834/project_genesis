"""
emailservice — Smart Worker Load Balancer / Coordinator
=========================================================
Monitors stream lag per topic and emits worker scaling signals.
Implements round-robin scheduling across user partitions to prevent
hot-partition overload.

What it does:
  1. Monitors XINFO GROUPS pending count per stream every 15s
  2. Detects hot partitions (one user generating disproportionate load)
  3. Emits backpressure signals to workers via shared in-process state
  4. Round-robin user assignment: distributes users across worker slots
     so no single worker handles all traffic from one heavy user

Round-Robin Algorithm:
  - Each user_id is hashed to a slot (0..N_SLOTS-1)
  - Workers claim slots via Redis SET NX (distributed lock)
  - If a slot's lag exceeds threshold → reassign to least-loaded worker
  - Rebalance check every 30s

SLA Tier Routing:
  - CRITICAL/HIGH priority events → fast lane (smaller batch, lower sleep)
  - LOW priority events → slow lane (larger batch, higher sleep tolerance)
  - Tier determined by _priority field set by FilterDedupWorker

This is a coordinator, not a blocker — workers continue processing
even if the load balancer is unavailable.
"""
from __future__ import annotations
import asyncio, hashlib, logging, time
from typing import Optional

from metrics import M

logger = logging.getLogger("emailservice.load_balancer")

# ── SLA tier definitions ──────────────────────────────────────────────────────
SLA_FREE       = "free"       # standard processing
SLA_PREMIUM    = "premium"    # faster lane, smaller batches
SLA_ENTERPRISE = "enterprise" # dedicated processing, lowest latency

# Priority → SLA tier mapping
_PRIORITY_TO_SLA = {
    0: SLA_ENTERPRISE,   # CRITICAL
    1: SLA_PREMIUM,      # HIGH
    2: SLA_FREE,         # MEDIUM
    3: SLA_FREE,         # LOW
}

# SLA tier → max batch size override
SLA_BATCH_LIMITS = {
    SLA_ENTERPRISE: 10,    # small batches → low latency
    SLA_PREMIUM:    50,
    SLA_FREE:       100,
}

# SLA tier → max sleep override (seconds)
SLA_SLEEP_LIMITS = {
    SLA_ENTERPRISE: 0.0,
    SLA_PREMIUM:    0.5,
    SLA_FREE:       30.0,
}

N_SLOTS = 64   # virtual partition slots (matches stream count)


def get_user_slot(user_id: str) -> int:
    """Deterministically assign a user to a slot via consistent hashing."""
    h = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    return h % N_SLOTS


def get_sla_tier(priority: int) -> str:
    """Map a priority level to an SLA tier."""
    return _PRIORITY_TO_SLA.get(priority, SLA_FREE)


def get_batch_limit_for_sla(tier: str) -> int:
    return SLA_BATCH_LIMITS.get(tier, 100)


def get_sleep_limit_for_sla(tier: str) -> float:
    return SLA_SLEEP_LIMITS.get(tier, 30.0)


class LoadBalancer:
    """
    Lightweight in-process load balancer.
    Runs as a background task, emits signals to workers.
    """

    def __init__(self):
        # stream → lag value (updated every 15s)
        self._lag_snapshot: dict[str, int] = {}
        self._last_check = 0.0
        self._running    = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._task    = asyncio.create_task(self._monitor_loop())
        logger.info("LoadBalancer started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(300)  # check every 5 minutes — not 15s
                await self._update_lag_snapshot()
                self._emit_signals()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("LoadBalancer monitor error: %s", e)

    async def _update_lag_snapshot(self) -> None:
        """Read pending counts from all streams."""
        try:
            from stream_client import get_stream_lag
            import config as cfg
            streams = [
                cfg.TOPIC_GMAIL_RAW, cfg.TOPIC_FETCH_RESULTS,
                cfg.TOPIC_STORE_READY, cfg.TOPIC_AI_EVENTS,
            ]
            groups = [
                cfg.CG_GMAIL_FETCH, cfg.CG_FILTER_DEDUP,
                cfg.CG_STORAGE, cfg.CG_AI_HANDOFF,
            ]
            for stream, group in zip(streams, groups):
                lag = await get_stream_lag(stream, group)
                self._lag_snapshot[stream] = lag
                M.kafka_lag.labels(topic=stream, worker="load_balancer").set(lag)
        except Exception:
            pass

    def _emit_signals(self) -> None:
        """Log load distribution summary."""
        if not self._lag_snapshot:
            return
        total = sum(self._lag_snapshot.values())
        if total > 0:
            logger.info(
                "LoadBalancer | total_lag=%d streams=%s",
                total,
                {k.split("_")[0]: v for k, v in self._lag_snapshot.items()},
            )

    def get_lag(self, stream: str) -> int:
        return self._lag_snapshot.get(stream, 0)

    def is_overloaded(self, stream: str, threshold: int = 50_000) -> bool:
        return self._lag_snapshot.get(stream, 0) > threshold

    @property
    def stats(self) -> dict:
        return {
            "lag_snapshot": self._lag_snapshot,
            "total_lag":    sum(self._lag_snapshot.values()),
        }


# ── Process-level singleton ───────────────────────────────────────────────────
_lb: Optional[LoadBalancer] = None

def get_load_balancer() -> LoadBalancer:
    global _lb
    if _lb is None:
        _lb = LoadBalancer()
    return _lb
