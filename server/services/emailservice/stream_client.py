"""
emailservice — Redis Streams Client
=====================================
Cost-efficient Redis Streams consumer using BLOCKING reads.

Key design: XREADGROUP with block=30000ms
- When stream is empty: Redis holds the connection for up to 30s, returns nil
- When a message arrives: Redis returns it immediately (push, not poll)
- Result: 1 Redis command per 30s when idle (vs 15/sec with short timeouts)
- On message arrival: instant delivery, no polling delay

Command budget at idle (5 workers):
  5 workers × 1 XREADGROUP/30s = 0.17 commands/sec = ~500/hour
  vs previous: 5 × 10/sec = 50 commands/sec = 180,000/hour
"""
from __future__ import annotations
import asyncio, json, logging, time, uuid
from typing import Optional

from shared.cache import get_redis_client
import config as cfg

logger = logging.getLogger("emailservice.streams")

STREAM_MAXLEN  = 10_000
N_SHARDS       = 1
_CONSUMER_NAME = f"worker-{uuid.uuid4().hex[:8]}"

# Block time for XREADGROUP. Must be < socket_timeout (15s) with headroom.
# 8s block = Redis pushes messages instantly, returns nil after 8s if empty.
# Cost: 5 workers × 1 cmd/8s = 0.6 cmd/sec = ~2,200/hour idle (vs 90,000 before)
_BLOCK_MS = 8_000


def _all_shards(stream: str) -> list[str]:
    return [stream]


def _shard_key(stream: str, partition_key: str = "") -> str:
    return stream


# ── Producer ──────────────────────────────────────────────────────────────────

async def publish(stream: str, payload: dict, partition_key: str = "") -> None:
    redis = get_redis_client()
    await redis.xadd(
        stream,
        {"data": json.dumps(payload, default=str)},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )


async def publish_batch(stream: str, events: list[tuple[dict, str]]) -> None:
    if not events:
        return
    redis = get_redis_client()
    pipe = redis.pipeline(transaction=False)
    for payload, _ in events:
        pipe.xadd(
            stream,
            {"data": json.dumps(payload, default=str)},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    await pipe.execute()


# ── Consumer ──────────────────────────────────────────────────────────────────

class StreamConsumer:
    """
    Blocking Redis Streams consumer.

    Uses XREADGROUP with block=30000ms:
    - Empty stream: 1 command per 30s (Redis holds connection, pushes on arrival)
    - Message arrives: delivered instantly, no polling delay
    - After each 30s timeout: runs XAUTOCLAIM to recover stuck pending messages
    """

    def __init__(self, streams: list[str], group_id: str):
        self.streams   = streams
        self.group_id  = group_id
        self._consumer = _CONSUMER_NAME
        self._pending: list[tuple[str, str]] = []
        self._running  = False
        # XAUTOCLAIM: run once on startup (recover stuck messages), then every 5 min
        self._last_autoclaim = 0.0          # 0 = run on first empty poll
        self._autoclaim_interval = 300.0    # then every 5 minutes

    async def start(self) -> None:
        """Create consumer groups with id=0 (read from beginning of stream)."""
        redis = get_redis_client()
        pipe = redis.pipeline(transaction=False)
        for stream in self.streams:
            pipe.xgroup_create(stream, self.group_id, id="0", mkstream=True)
        try:
            await pipe.execute(raise_on_error=False)
        except Exception:
            pass  # BUSYGROUP = already exists = fine
        self._running = True
        logger.info("StreamConsumer | streams=%s group=%s consumer=%s",
                    self.streams, self.group_id, self._consumer)

    async def stop(self) -> None:
        self._running = False
        if self._pending:
            await self._ack_pending()

    async def getmany(self, max_records: int = 100) -> dict[str, list]:
        """
        Block until messages arrive or 30s timeout.
        On timeout: check for pending/stuck messages via XAUTOCLAIM.
        Returns immediately when messages are available.
        """
        redis = get_redis_client()
        try:
            raw = await redis.xreadgroup(
                groupname=self.group_id,
                consumername=self._consumer,
                streams={s: ">" for s in self.streams},
                count=max_records,
                block=_BLOCK_MS,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            err = str(e)
            # Socket timeout after block period = normal empty-stream behavior, not an error
            if "timeout" in err.lower() or "timed out" in err.lower():
                # Treat as empty result — check pending messages
                return await self._claim_pending(redis, max_records)
            logger.error("XREADGROUP error: %s", e)
            await asyncio.sleep(2)
            return {}

        if raw:
            return self._parse_raw(raw)

        # Timeout — no new messages. Run XAUTOCLAIM on startup and every 5 min.
        now = time.time()
        if (now - self._last_autoclaim) >= self._autoclaim_interval:
            self._last_autoclaim = now
            return await self._claim_pending(redis, max_records)

        return {}

    def _parse_raw(self, raw) -> dict[str, list]:
        result: dict[str, list] = {}
        for stream_name, messages in raw:
            for msg_id, fields in messages:
                try:
                    record = json.loads(fields.get("data", "{}"))
                    record["_stream_id"] = msg_id
                    record["_stream"]    = stream_name
                    result.setdefault(stream_name, []).append(record)
                    self._pending.append((stream_name, msg_id))
                except Exception as e:
                    logger.error("Parse error for msg %s: %s", msg_id, e)
                    # ACK unparseable messages so they don't block forever
                    asyncio.create_task(self._ack_one(stream_name, msg_id))
        return result

    async def _claim_pending(self, redis, max_records: int) -> dict[str, list]:
        """
        Reclaim messages delivered to a crashed consumer (pending > 30s).
        Called after each 30s timeout — costs 1 XAUTOCLAIM per stream per 30s.
        """
        result: dict[str, list] = {}
        for stream in self.streams:
            try:
                claimed = await redis.xautoclaim(
                    stream, self.group_id, self._consumer,
                    min_idle_time=30_000,
                    start_id="0-0",
                    count=max_records,
                )
                messages = claimed[1] if isinstance(claimed, (list, tuple)) and len(claimed) > 1 else []
                for msg_id, fields in messages:
                    try:
                        record = json.loads(fields.get("data", "{}"))
                        record["_stream_id"] = msg_id
                        record["_stream"]    = stream
                        record["_reclaimed"] = True
                        result.setdefault(stream, []).append(record)
                        self._pending.append((stream, msg_id))
                    except Exception as e:
                        logger.error("Parse error for reclaimed msg %s: %s", msg_id, e)
                        asyncio.create_task(self._ack_one(stream, msg_id))
                if messages:
                    logger.info("Reclaimed %d pending messages from %s", len(messages), stream)
            except Exception as e:
                logger.debug("XAUTOCLAIM skipped for %s: %s", stream, e)
        return result

    async def commit(self) -> None:
        await self._ack_pending()

    async def _ack_pending(self) -> None:
        if not self._pending:
            return
        redis = get_redis_client()
        by_stream: dict[str, list[str]] = {}
        for stream, msg_id in self._pending:
            by_stream.setdefault(stream, []).append(msg_id)
        pipe = redis.pipeline(transaction=False)
        for stream, ids in by_stream.items():
            pipe.xack(stream, self.group_id, *ids)
        try:
            await pipe.execute()
        except Exception as e:
            logger.error("XACK failed: %s", e)
        self._pending.clear()

    async def _ack_one(self, stream: str, msg_id: str) -> None:
        try:
            await get_redis_client().xack(stream, self.group_id, msg_id)
        except Exception:
            pass

    def assignment(self) -> list[str]:
        return list(self.streams)


# ── Stream setup ──────────────────────────────────────────────────────────────

async def ensure_streams() -> None:
    """
    Create only the recovery stream (no consumer group needed).
    Uses XRANGE/XDEL pattern — simpler than XREADGROUP, no group overhead.
    Cleans up all old stream keys from previous architecture.
    """
    redis = get_redis_client()

    # Ensure recovery stream exists (XADD a sentinel then delete it)
    from workers.recovery_worker import RECOVERY_STREAM
    try:
        # Just ensure the key exists — no consumer group needed
        length = await redis.xlen(RECOVERY_STREAM)
        logger.info("Recovery stream ready: %s (length=%d)", RECOVERY_STREAM, length)
    except Exception:
        # Stream doesn't exist yet — will be created on first XADD
        logger.info("Recovery stream will be created on first failure event")

    # Clean up all old stream keys from previous architecture
    old_streams = [
        "gmail_events", "outlook_events", "smtp_events",
        "fetch_results", "store_ready", "ai_events", "email_dlq",
        "automation_events",
    ]
    pipe = redis.pipeline(transaction=False)
    for stream in old_streams:
        for suffix in ["", ":0", ":1", ":2", ":3"]:
            pipe.delete(f"{stream}{suffix}")
    try:
        results = await pipe.execute(raise_on_error=False)
        deleted = sum(1 for r in results if r == 1)
        if deleted:
            logger.info("Cleaned up %d old stream keys", deleted)
    except Exception:
        pass


async def get_stream_lag(stream: str, group_id: str) -> int:
    try:
        groups = await get_redis_client().xinfo_groups(stream)
        for g in groups:
            if g.get("name") == group_id:
                return int(g.get("pending", 0))
    except Exception:
        pass
    return 0
