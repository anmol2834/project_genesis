"""
emailservice — User Aggregation Buffer + Priority Engine
=========================================================
Solves: each Pub/Sub event triggering a separate Gmail API call.
Fix:    buffer events per user for 2-5s, then process once → 70-80% API reduction.

Design:
  - In-memory async buffer keyed by user_id (or email_address)
  - Flush triggers: time threshold OR buffer size threshold
  - Hard max wait: never hold an event longer than BUFFER_MAX_WAIT_S
  - Priority scoring: CRITICAL events bypass buffer entirely
  - Hot user detection: users with >N emails/min get dedicated processing lane
  - Ordering preserved: events sorted by history_id before processing

Priority levels (lower = more urgent):
  CRITICAL (0) → bypass buffer, process immediately
  HIGH     (1) → buffer 2s
  MEDIUM   (2) → buffer 3s
  LOW      (3) → buffer 5s + delayed 45s

Hot user detection:
  if emails_per_minute > HOT_USER_EMAILS_PER_MIN → mark HOT
  HOT users get dedicated semaphore slots (don't compete with normal users)
"""
from __future__ import annotations
import asyncio, time, logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Optional

import config as cfg
from metrics import M

logger = logging.getLogger("emailservice.user_buffer")


# ── Priority scoring ──────────────────────────────────────────────────────────

_VIP_DOMAINS = frozenset([
    # Add known important domains here — e.g. your own domain, key clients
])

_LOW_PRIORITY_PATTERNS = frozenset([
    "newsletter", "noreply", "no-reply", "notifications", "updates",
    "marketing", "promo", "offers", "deals", "alerts",
])


def score_priority(event: dict) -> int:
    """
    Score an event's priority based on sender, subject, and metadata.
    Returns PRIORITY_CRITICAL / HIGH / MEDIUM / LOW.
    """
    from_email = (event.get("from_email") or "").lower()
    subject    = (event.get("subject") or "").lower()

    # CRITICAL: direct reply to our outgoing message
    if event.get("direction") == "incoming" and event.get("in_reply_to"):
        return cfg.PRIORITY_CRITICAL

    # CRITICAL: VIP domain
    domain = from_email.split("@")[-1] if "@" in from_email else ""
    if domain in _VIP_DOMAINS:
        return cfg.PRIORITY_CRITICAL

    # LOW: automated / newsletter patterns
    if any(p in from_email for p in _LOW_PRIORITY_PATTERNS):
        return cfg.PRIORITY_LOW
    if any(p in subject for p in ("unsubscribe", "newsletter", "promo", "offer")):
        return cfg.PRIORITY_LOW

    # HIGH: has explicit reply-to or is a direct message
    if event.get("thread_id") and event.get("thread_id") != event.get("message_id"):
        return cfg.PRIORITY_HIGH

    return cfg.PRIORITY_MEDIUM


# ── Hot user tracker ──────────────────────────────────────────────────────────

class HotUserTracker:
    """
    Tracks email volume per user over a sliding 60s window.
    Users exceeding HOT_USER_EMAILS_PER_MIN are marked HOT.
    """
    _WINDOW_S = 60

    def __init__(self):
        # user_id → deque of timestamps
        self._windows: dict[str, deque] = defaultdict(deque)

    def record(self, user_id: str) -> bool:
        """Record an event for user. Returns True if user is HOT."""
        now = time.monotonic()
        dq  = self._windows[user_id]
        dq.append(now)
        # Evict old entries outside window
        while dq and (now - dq[0]) > self._WINDOW_S:
            dq.popleft()
        is_hot = len(dq) >= cfg.HOT_USER_EMAILS_PER_MIN
        if is_hot:
            M.hot_users_detected.inc()
        return is_hot

    def is_hot(self, user_id: str) -> bool:
        now = time.monotonic()
        dq  = self._windows.get(user_id)
        if not dq:
            return False
        # Count events in last 60s
        count = sum(1 for t in dq if (now - t) <= self._WINDOW_S)
        return count >= cfg.HOT_USER_EMAILS_PER_MIN

    def evict_inactive(self) -> None:
        """Remove users with no events in last 5 minutes."""
        now = time.monotonic()
        stale = [uid for uid, dq in self._windows.items()
                 if not dq or (now - dq[-1]) > 300]
        for uid in stale:
            del self._windows[uid]


# ── Buffered event ────────────────────────────────────────────────────────────

@dataclass
class BufferedEvent:
    event:      dict
    priority:   int
    arrived_at: float = field(default_factory=time.monotonic)


# ── User Aggregation Buffer ───────────────────────────────────────────────────

FlushCallback = Callable[[str, list[dict]], Awaitable[None]]


class UserAggregationBuffer:
    """
    Buffers Kafka events per user_id and flushes them in batches.

    Flush triggers (whichever comes first):
      1. BUFFER_FLUSH_INTERVAL_S of inactivity
      2. BUFFER_MAX_SIZE events accumulated
      3. BUFFER_MAX_WAIT_S hard deadline
      4. PRIORITY_CRITICAL event → immediate flush

    After flush, events are sorted by history_id (ordering preserved).
    """

    def __init__(self, flush_callback: FlushCallback, worker_name: str = ""):
        self._callback    = flush_callback
        self._worker_name = worker_name
        # user_id → list of BufferedEvent
        self._buffers:    dict[str, list[BufferedEvent]] = {}
        self._first_seen: dict[str, float] = {}   # user_id → first event time
        self._lock        = asyncio.Lock()
        self._hot_tracker = HotUserTracker()
        self._running     = False
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running    = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("[%s] UserAggregationBuffer started", self._worker_name)

    async def stop(self) -> None:
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
        # Flush remaining buffers
        await self._flush_all()

    async def add(self, user_id: str, event: dict) -> None:
        """Add an event to the user's buffer."""
        priority = score_priority(event)
        event["_priority"] = priority
        M.priority_events.labels(priority=_priority_name(priority)).inc()

        # CRITICAL → bypass buffer, flush immediately
        if priority == cfg.PRIORITY_CRITICAL:
            await self._callback(user_id, [event])
            return

        is_hot = self._hot_tracker.record(user_id)

        async with self._lock:
            if user_id not in self._buffers:
                self._buffers[user_id]    = []
                self._first_seen[user_id] = time.monotonic()

            self._buffers[user_id].append(BufferedEvent(event, priority))

            # Flush immediately if buffer is full
            if len(self._buffers[user_id]) >= cfg.BUFFER_MAX_SIZE:
                await self._flush_user(user_id)
                return

        # HOT users: flush after shorter window (don't let them starve)
        if is_hot:
            await asyncio.sleep(0)  # yield to event loop
            async with self._lock:
                if user_id in self._buffers:
                    await self._flush_user(user_id)

        M.buffer_size.labels(worker=self._worker_name).set(
            sum(len(v) for v in self._buffers.values())
        )
        M.active_users.labels(worker=self._worker_name).set(len(self._buffers))

    async def _flush_loop(self) -> None:
        """Background loop: flush buffers that have exceeded their time threshold."""
        while self._running:
            try:
                await asyncio.sleep(2.0)   # check every 2s — was 500ms
                await self._flush_expired()
                # Periodic hot-user eviction
                self._hot_tracker.evict_inactive()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[%s] flush loop error: %s", self._worker_name, e)

    async def _flush_expired(self) -> None:
        now = time.monotonic()
        async with self._lock:
            to_flush = []
            for user_id, events in list(self._buffers.items()):
                if not events:
                    continue
                first_ts = self._first_seen.get(user_id, now)
                age      = now - first_ts
                priority = min(e.priority for e in events)

                # Determine flush threshold based on priority
                if priority <= cfg.PRIORITY_HIGH:
                    threshold = cfg.BUFFER_FLUSH_INTERVAL_S
                elif priority == cfg.PRIORITY_MEDIUM:
                    threshold = cfg.BUFFER_FLUSH_INTERVAL_S
                else:  # LOW
                    threshold = cfg.BUFFER_MAX_WAIT_S

                if age >= threshold or age >= cfg.BUFFER_MAX_WAIT_S:
                    to_flush.append(user_id)

            for user_id in to_flush:
                await self._flush_user(user_id)

    async def _flush_user(self, user_id: str) -> None:
        """Flush a single user's buffer. Must be called under self._lock."""
        buffered = self._buffers.pop(user_id, [])
        self._first_seen.pop(user_id, None)
        if not buffered:
            return

        # Sort by history_id to preserve ordering
        buffered.sort(key=lambda e: int(e.event.get("history_id", 0)))

        # Separate LOW priority events — delay them
        low_events    = [e.event for e in buffered if e.priority == cfg.PRIORITY_LOW]
        normal_events = [e.event for e in buffered if e.priority != cfg.PRIORITY_LOW]

        if normal_events:
            asyncio.create_task(self._callback(user_id, normal_events))

        if low_events:
            asyncio.create_task(self._delayed_flush(user_id, low_events))

    async def _delayed_flush(self, user_id: str, events: list[dict]) -> None:
        """Delay LOW priority events before processing."""
        await asyncio.sleep(cfg.PRIORITY_LOW_DELAY_S)
        await self._callback(user_id, events)

    async def _flush_all(self) -> None:
        async with self._lock:
            for user_id in list(self._buffers.keys()):
                await self._flush_user(user_id)


def _priority_name(p: int) -> str:
    return {0: "critical", 1: "high", 2: "medium", 3: "low"}.get(p, "unknown")
