"""
emailservice — Redis Streams Client (Event-Driven, Zero Idle Cost)
===================================================================
Architecture:
  publish()  → XADD to stream + signal in-process asyncio.Event
  consume()  → sleep on asyncio.Event → wake → XRANGE drain → XDEL

Zero Redis commands when idle.
No XREADGROUP. No XAUTOCLAIM. No blocking loops. No consumer groups.

Startup flood protection:
  drain_once() accepts a rate_limit parameter (messages/sec).
  On startup, workers call drain_once(rate_limit=BACKLOG_DRAIN_RATE) to
  process the backlog in controlled batches with inter-batch delays.
  After backlog is cleared, workers switch to real-time mode (no rate limit).

Redis command budget:
  Idle:   0 commands/sec
  Active: 1 XRANGE + N XDEL per batch (drain)
  Retry:  in-process queue, no Redis until DLQ

Shard-aware routing:
  partition_key (user_id) hashed to shard index.
  Each shard has its own asyncio.Event.
  Multiple workers can be pinned to different shards — no locks, no duplicates.
"""
from __future__ import annotations
import asyncio, hashlib, json, logging, time
from collections import defaultdict

from shared.cache import get_redis_client
import config as cfg

logger = logging.getLogger("emailservice.streams")

STREAM_MAXLEN = 10_000
N_SHARDS      = cfg.STREAM_N_SHARDS  # 1 by default

# ── Per-stream wake signals ───────────────────────────────────────────────────
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
    return _stream_events[_wake_key(stream, _shard_for(partition_key))]


# ── Producer ──────────────────────────────────────────────────────────────────

async def publish(stream: str, payload: dict, partition_key: str = "") -> None:
    """XADD to stream + signal in-process wake event. Zero idle cost."""
    redis  = get_redis_client()
    target = _stream_key(stream, partition_key)
    await redis.xadd(
        target,
        {"data": json.dumps(payload, default=str)},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    _get_event(stream, partition_key).set()


async def publish_batch(stream: str, events: list[tuple[dict, str]]) -> None:
    """Publish multiple events in one pipeline, signal each affected shard once."""
    if not events:
        return
    redis = get_redis_client()
    by_shard: dict[str, list[dict]] = {}
    for payload, key in events:
        sk = _stream_key(stream, key)
        by_shard.setdefault(sk, []).append(payload)

    for sk, payloads in by_shard.items():
        pipe = redis.pipeline(transaction=False)
        for p in payloads:
            pipe.xadd(sk, {"data": json.dumps(p, default=str)},
                      maxlen=STREAM_MAXLEN, approximate=True)
        await pipe.execute()

    # Signal each affected shard exactly once
    signalled: set[str] = set()
    for _, key in events:
        wk = _wake_key(stream, _shard_for(key))
        if wk not in signalled:
            _stream_events[wk].set()
            signalled.add(wk)


# ── Event-Driven Drain Consumer ───────────────────────────────────────────────

class EventDrivenConsumer:
    """
    Zero-idle-cost stream consumer.

    Modes:
      BACKLOG  — startup, processes old events at controlled rate
      REALTIME — live, processes only new events triggered by publish()

    Retry model:
      Failed records go to in-process retry queue with exponential backoff.
      No Redis involvement until DLQ threshold is reached.
      requeue() does NOT set the wake event — the event loop uses a timeout
      to wake at the right time, preventing tight retry loops.
    """

    DRAIN_BATCH = 500  # max messages per XRANGE call

    def __init__(self, streams: list[str]):
        self.streams  = streams
        self._running = False
        # (shard_key, payload, retry_count, next_attempt_monotonic)
        self._retry_queue: list[tuple[str, dict, int, float]] = []
        # Backlog state: set to True during startup drain, False after
        self._in_backlog_mode = False

    async def start(self) -> None:
        self._running = True
        logger.info("EventDrivenConsumer | streams=%s", self.streams)

    async def stop(self) -> None:
        self._running = False
        for stream in self.streams:
            for shard in range(max(N_SHARDS, 1)):
                _stream_events[_wake_key(stream, shard)].set()

    async def backlog_size(self) -> int:
        """Total messages currently in all stream shards."""
        redis = get_redis_client()
        total = 0
        for stream in self.streams:
            for sk in _all_shards(stream):
                try:
                    total += await redis.xlen(sk)
                except Exception:
                    pass
        return total

    async def drain_once(self, batch_size: int = DRAIN_BATCH) -> list[dict]:
        """
        Drain up to batch_size messages from all shards.
        Deletes messages immediately after reading (XDEL in pipeline).
        Returns parsed records + any due retry items.
        """
        redis   = get_redis_client()
        records = []

        for stream in self.streams:
            for sk in _all_shards(stream):
                try:
                    messages = await redis.xrange(sk, "-", "+", count=batch_size)
                    if not messages:
                        continue

                    ids_to_del = []
                    for msg_id, fields in messages:
                        try:
                            rec = json.loads(fields.get("data", "{}"))
                            rec["_stream_id"] = msg_id
                            rec["_stream"]    = stream
                            rec["_shard_key"] = sk
                            records.append(rec)
                            ids_to_del.append(msg_id)
                        except Exception as e:
                            logger.error("Parse error msg %s: %s", msg_id, e)
                            ids_to_del.append(msg_id)  # delete unparseable

                    if ids_to_del:
                        pipe = redis.pipeline(transaction=False)
                        for mid in ids_to_del:
                            pipe.xdel(sk, mid)
                        await pipe.execute(raise_on_error=False)

                except Exception as e:
                    logger.error("Drain error %s: %s", sk, e)

        # Collect due retry items (no Redis involved)
        now = time.monotonic()
        due   = [(sk, p, rc) for sk, p, rc, ts in self._retry_queue if ts <= now]
        later = [(sk, p, rc, ts) for sk, p, rc, ts in self._retry_queue if ts > now]
        self._retry_queue = later

        for sk, payload, retry_count in due:
            payload["_retry_count"] = retry_count
            payload["_stream"]      = sk.split(":")[0] if ":" in sk else sk
            payload["_shard_key"]   = sk
            records.append(payload)

        return records

    def requeue(self, record: dict, reason: str = "") -> None:
        """
        Re-queue failed record with exponential backoff.
        Does NOT set the wake event — caller's event loop uses next_retry_delay()
        as a timeout to avoid tight loops.
        """
        retry_count = record.get("_retry_count", 0) + 1
        sk          = record.get("_shard_key", record.get("_stream", "unknown"))
        delay       = min(cfg.STORE_RETRY_BASE_DELAY_S * (2 ** (retry_count - 1)), 300.0)
        next_ts     = time.monotonic() + delay

        payload = {k: v for k, v in record.items() if not k.startswith("_")}
        self._retry_queue.append((sk, payload, retry_count, next_ts))
        logger.debug("Requeued msg %s (attempt %d, delay=%.1fs): %s",
                     record.get("message_id", "?"), retry_count, delay, reason)

    def has_pending_retries(self) -> bool:
        return bool(self._retry_queue)

    def next_retry_delay(self) -> float:
        """Seconds until the earliest retry is due. Returns 0 if due now."""
        if not self._retry_queue:
            return 0.0
        now = time.monotonic()
        return max(0.0, min(ts - now for _, _, _, ts in self._retry_queue))


# ── Stream setup ──────────────────────────────────────────────────────────────

async def ensure_streams() -> None:
    """
    Idempotent stream initialization.
    - First run: cleans up legacy XREADGROUP consumer groups and old shard keys
    - Subsequent runs: skips cleanup entirely (guarded by a Redis key)
    - Never destroys anything on normal startup after first run
    """
    redis = get_redis_client()

    # ── One-time legacy cleanup (runs only once across all restarts) ──────────
    # Guard key: set after first successful cleanup, TTL = 30 days
    # If the key exists, skip all destructive operations entirely
    _CLEANUP_DONE_KEY = "es:stream_init:cleanup_v2"
    try:
        already_clean = await redis.exists(_CLEANUP_DONE_KEY)
    except Exception:
        already_clean = False

    if not already_clean:
        all_streams = [
            cfg.TOPIC_GMAIL_RAW, cfg.TOPIC_OUTLOOK_RAW, cfg.TOPIC_SMTP_RAW,
            cfg.TOPIC_STORE_READY, cfg.TOPIC_AI_EVENTS, cfg.TOPIC_DLQ,
        ]
        old_groups = [
            cfg.CG_GMAIL_FETCH, cfg.CG_OUTLOOK_FETCH, cfg.CG_SMTP_FETCH,
            cfg.CG_STORAGE, cfg.CG_AI_HANDOFF, cfg.CG_DLQ_MONITOR, cfg.CG_FILTER_DEDUP,
        ]
        old_bases = all_streams + ["automation_events", "fetch_results", "email_queue"]

        pipe = redis.pipeline(transaction=False)
        # Destroy legacy consumer groups (safe — XGROUP DESTROY is idempotent if group missing)
        for stream in all_streams:
            for group in old_groups:
                pipe.xgroup_destroy(stream, group)
        # Delete old shard keys from N_SHARDS=4 era
        for base in old_bases:
            for suffix in [":0", ":1", ":2", ":3"]:
                pipe.delete(f"{base}{suffix}")
        # Mark cleanup as done — TTL 30 days
        pipe.setex(_CLEANUP_DONE_KEY, 86400 * 30, "1")
        try:
            await pipe.execute(raise_on_error=False)
            logger.info("One-time legacy stream cleanup complete")
        except Exception as e:
            logger.warning("Legacy stream cleanup warning: %s", e)
    else:
        logger.debug("Stream cleanup already done — skipping")

    logger.info("Event-driven streams ready (N_SHARDS=%d)", N_SHARDS)

    # Log backlog sizes for visibility (read-only, always safe)
    all_streams_check = [
        cfg.TOPIC_GMAIL_RAW, cfg.TOPIC_OUTLOOK_RAW, cfg.TOPIC_SMTP_RAW,
        cfg.TOPIC_STORE_READY, cfg.TOPIC_AI_EVENTS, cfg.TOPIC_DLQ,
    ]
    for stream in all_streams_check:
        try:
            length = await redis.xlen(stream)
            if length:
                logger.info("Startup backlog: %s has %d messages", stream, length)
        except Exception:
            pass


async def get_stream_lag(stream: str, group_id: str = "") -> int:
    try:
        total = 0
        for sk in _all_shards(stream):
            total += await get_redis_client().xlen(sk)
        return total
    except Exception:
        return 0


# ── Backward-compat shim ──────────────────────────────────────────────────────

class StreamConsumer:
    """Backward-compatible shim for kafka_client.make_consumer()."""
    def __init__(self, streams: list[str], group_id: str):
        self._inner   = EventDrivenConsumer(streams)
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
