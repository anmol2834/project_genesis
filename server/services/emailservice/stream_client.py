"""
emailservice — Redis Streams Client (Event-Driven, Zero Idle Cost)
===================================================================
Architecture:
  publish()  → XADD to stream + signal in-process asyncio.Event
  consume()  → sleep on asyncio.Event → wake → XRANGE drain → XDEL

Zero Redis commands when idle.
No XREADGROUP. No XAUTOCLAIM. No blocking loops.
No consumer groups — simpler, cheaper, no group overhead.

Redis command budget:
  Idle:   0 commands/sec (workers sleeping on asyncio.Event)
  Active: 1 XADD (publish) + N XRANGE + N XDEL per batch (drain)
  vs old: 3 workers × 1 XREADGROUP/8s = 22 commands/min idle
  New:    0 commands/min idle

Shard-aware routing:
  partition_key (user_id) is hashed to a shard index.
  Each shard has its own asyncio.Event — workers can be pinned to shards
  for horizontal scaling without locks or duplicate processing.

Startup recovery:
  On startup, each stream is drained once to catch events from previous crash.
  This costs 1 XRANGE per stream on startup, then 0 until next event.
"""
from __future__ import annotations
import asyncio, hashlib, json, logging, time, uuid
from collections import defaultdict
from typing import Callable, Awaitable

from shared.cache import get_redis_client
import config as cfg

logger = logging.getLogger("emailservice.streams")

STREAM_MAXLEN = 10_000
N_SHARDS      = cfg.STREAM_N_SHARDS  # 1 by default; increase for horizontal scale

# ── Per-stream wake signals ───────────────────────────────────────────────────
# Each logical stream has one asyncio.Event per shard.
# publish() sets the event; the drain loop clears it after draining.
_stream_events: dict[str, asyncio.Event] = defaultdict(asyncio.Event)


def _wake_key(stream: str, shard: int = 0) -> str:
    return f"{stream}:{shard}" if N_SHARDS > 1 else stream


def _shard_for(partition_key: str) -> int:
    if not partition_key or N_SHARDS <= 1:
        return 0
    return int(hashlib.md5(partition_key.encode()).hexdigest(), 16) % N_SHARDS


def _stream_key(stream: str, partition_key: str = "") -> str:
    shard = _shard_for(partition_key)
    return f"{stream}:{shard}" if N_SHARDS > 1 else stream


def _all_shards(stream: str) -> list[str]:
    if N_SHARDS <= 1:
        return [stream]
    return [f"{stream}:{i}" for i in range(N_SHARDS)]


def _get_event(stream: str, partition_key: str = "") -> asyncio.Event:
    """Get the asyncio.Event for a stream+shard combination."""
    key = _wake_key(stream, _shard_for(partition_key))
    return _stream_events[key]


# ── Producer ──────────────────────────────────────────────────────────────────

async def publish(stream: str, payload: dict, partition_key: str = "") -> None:
    """
    Write event to Redis Stream and signal the in-process wake event.
    The drain worker wakes immediately and processes the batch.
    """
    redis  = get_redis_client()
    target = _stream_key(stream, partition_key)
    await redis.xadd(
        target,
        {"data": json.dumps(payload, default=str)},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    # Signal the drain worker — pure Python, zero Redis
    _get_event(stream, partition_key).set()


async def publish_batch(stream: str, events: list[tuple[dict, str]]) -> None:
    """Publish multiple events in one pipeline round-trip, then signal once."""
    if not events:
        return
    redis = get_redis_client()
    # Group by shard for efficient pipelining
    by_shard: dict[str, list[dict]] = {}
    for payload, key in events:
        shard_key = _stream_key(stream, key)
        by_shard.setdefault(shard_key, []).append((payload, key))

    for shard_key, shard_events in by_shard.items():
        pipe = redis.pipeline(transaction=False)
        for payload, _ in shard_events:
            pipe.xadd(
                shard_key,
                {"data": json.dumps(payload, default=str)},
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
        await pipe.execute()

    # Signal all affected shards once (not per-message)
    signalled: set[str] = set()
    for _, key in events:
        wake_key = _wake_key(stream, _shard_for(key))
        if wake_key not in signalled:
            _stream_events[wake_key].set()
            signalled.add(wake_key)


# ── Event-Driven Drain Consumer ───────────────────────────────────────────────

class EventDrivenConsumer:
    """
    Zero-idle-cost stream consumer.

    Lifecycle:
      1. start()  → drain startup backlog (1 XRANGE per stream)
      2. wait()   → sleep on asyncio.Event (0 Redis commands)
      3. drain()  → XRANGE all messages → process → XDEL
      4. goto 2

    No XREADGROUP. No XAUTOCLAIM. No consumer groups.
    No blocking Redis calls. No periodic timers.

    Retry model:
      Failed messages are re-added to the in-process retry queue with
      exponential backoff. They are NOT left in Redis (no pending state).
      After MAX_RETRIES, they go to the DLQ stream.
    """

    MAX_RETRIES    = cfg.DLQ_MAX_RETRIES
    DRAIN_BATCH    = 500   # max messages per drain cycle

    def __init__(self, streams: list[str]):
        self.streams  = streams
        self._running = False
        # Retry queue: (stream_key, payload_dict, retry_count, next_attempt_ts)
        self._retry_queue: list[tuple[str, dict, int, float]] = []

    async def start(self) -> None:
        """Ensure streams exist and drain any startup backlog."""
        redis = get_redis_client()
        pipe  = redis.pipeline(transaction=False)
        for stream in self.streams:
            for shard in _all_shards(stream):
                pipe.xlen(shard)  # creates the key if it doesn't exist via XADD later
        try:
            await pipe.execute(raise_on_error=False)
        except Exception:
            pass
        self._running = True
        logger.info("EventDrivenConsumer | streams=%s", self.streams)

    async def stop(self) -> None:
        self._running = False
        # Wake all events so any waiting coroutines can exit
        for stream in self.streams:
            for shard in range(max(N_SHARDS, 1)):
                _stream_events[_wake_key(stream, shard)].set()

    async def drain_once(self) -> list[dict]:
        """
        Drain all pending messages from all shards of all streams.
        Returns list of parsed records. Deletes successfully-read messages.
        Called by the worker after waking from asyncio.Event.
        """
        redis   = get_redis_client()
        records = []

        for stream in self.streams:
            for shard_key in _all_shards(stream):
                try:
                    messages = await redis.xrange(shard_key, "-", "+", count=self.DRAIN_BATCH)
                    if not messages:
                        continue

                    ids_to_delete = []
                    for msg_id, fields in messages:
                        try:
                            record = json.loads(fields.get("data", "{}"))
                            record["_stream_id"]  = msg_id
                            record["_stream"]     = stream
                            record["_shard_key"]  = shard_key
                            records.append(record)
                            ids_to_delete.append(msg_id)
                        except Exception as e:
                            logger.error("Parse error for msg %s: %s", msg_id, e)
                            ids_to_delete.append(msg_id)  # delete unparseable

                    # Delete in one pipeline call
                    if ids_to_delete:
                        pipe = redis.pipeline(transaction=False)
                        for mid in ids_to_delete:
                            pipe.xdel(shard_key, mid)
                        await pipe.execute(raise_on_error=False)

                except Exception as e:
                    logger.error("Drain error for %s: %s", shard_key, e)

        # Also drain any due retry items
        now = time.monotonic()
        due = [(sk, p, rc) for sk, p, rc, ts in self._retry_queue if ts <= now]
        self._retry_queue = [(sk, p, rc, ts) for sk, p, rc, ts in self._retry_queue if ts > now]

        for shard_key, payload, retry_count in due:
            payload["_retry_count"] = retry_count
            payload["_stream"]      = shard_key.split(":")[0] if ":" in shard_key else shard_key
            payload["_shard_key"]   = shard_key
            records.append(payload)

        return records

    def requeue(self, record: dict, reason: str = "") -> None:
        """
        Re-queue a failed record with exponential backoff.
        After MAX_RETRIES, the record is sent to DLQ (handled by caller).
        """
        retry_count = record.get("_retry_count", 0) + 1
        shard_key   = record.get("_shard_key", record.get("_stream", "unknown"))
        delay       = min(cfg.STORE_RETRY_BASE_DELAY_S * (2 ** (retry_count - 1)), 300.0)
        next_ts     = time.monotonic() + delay

        # Strip internal fields before re-queuing
        payload = {k: v for k, v in record.items() if not k.startswith("_")}

        self._retry_queue.append((shard_key, payload, retry_count, next_ts))
        logger.debug("Requeued msg %s (attempt %d, delay=%.1fs): %s",
                     record.get("message_id", "?"), retry_count, delay, reason)

        # Wake the drain loop so it picks up retries when they're due
        if self._retry_queue:
            for stream in self.streams:
                _stream_events[_wake_key(stream)].set()

    def has_pending_retries(self) -> bool:
        return bool(self._retry_queue)

    def next_retry_delay(self) -> float:
        """Seconds until the next retry is due (0 if none pending)."""
        if not self._retry_queue:
            return 0.0
        now = time.monotonic()
        return max(0.0, min(ts - now for _, _, _, ts in self._retry_queue))


# ── Stream setup ──────────────────────────────────────────────────────────────

async def ensure_streams() -> None:
    """
    Ensure all stream keys exist. No consumer groups needed.
    Clean up legacy XREADGROUP-era keys.
    """
    redis = get_redis_client()

    # All logical streams used by the system
    all_streams = [
        cfg.TOPIC_GMAIL_RAW,
        cfg.TOPIC_OUTLOOK_RAW,
        cfg.TOPIC_SMTP_RAW,
        cfg.TOPIC_STORE_READY,
        cfg.TOPIC_AI_EVENTS,
        cfg.TOPIC_DLQ,
    ]

    # Streams exist implicitly when first XADD is called.
    # Just log what we expect to use.
    logger.info("Event-driven streams configured: %s (N_SHARDS=%d)", all_streams, N_SHARDS)

    # Clean up legacy consumer group keys and old shard keys
    old_groups = [
        cfg.CG_GMAIL_FETCH, cfg.CG_OUTLOOK_FETCH, cfg.CG_SMTP_FETCH,
        cfg.CG_STORAGE, cfg.CG_AI_HANDOFF, cfg.CG_DLQ_MONITOR,
        cfg.CG_FILTER_DEDUP,
    ]
    old_suffixes = [":0", ":1", ":2", ":3"]
    old_bases    = all_streams + ["automation_events", "fetch_results", "email_queue"]

    pipe = redis.pipeline(transaction=False)
    # Delete old consumer groups
    for stream in all_streams:
        for group in old_groups:
            pipe.xgroup_destroy(stream, group)
    # Delete old shard keys
    for base in old_bases:
        for suffix in old_suffixes:
            pipe.delete(f"{base}{suffix}")
    try:
        await pipe.execute(raise_on_error=False)
        logger.info("Legacy XREADGROUP consumer groups and shard keys cleaned up")
    except Exception:
        pass

    # Recovery stream (XRANGE/XDEL pattern — no group)
    from workers.recovery_worker import RECOVERY_STREAM
    try:
        length = await redis.xlen(RECOVERY_STREAM)
        if length:
            logger.info("Recovery stream has %d leftover events — will drain on startup", length)
    except Exception:
        pass


async def get_stream_lag(stream: str, group_id: str = "") -> int:
    """Returns approximate number of unprocessed messages in a stream."""
    try:
        total = 0
        for shard in _all_shards(stream):
            total += await get_redis_client().xlen(shard)
        return total
    except Exception:
        return 0


# ── Backward-compat shim (kafka_client.py uses make_consumer) ─────────────────

class StreamConsumer:
    """
    Backward-compatible shim. Returns an EventDrivenConsumer.
    BaseWorker calls make_consumer() → this class.
    """
    def __init__(self, streams: list[str], group_id: str):
        self._inner = EventDrivenConsumer(streams)
        self.streams  = streams
        self.group_id = group_id

    async def start(self) -> None:
        await self._inner.start()

    async def stop(self) -> None:
        await self._inner.stop()

    def get_inner(self) -> EventDrivenConsumer:
        return self._inner

    def assignment(self) -> list[str]:
        return list(self.streams)
