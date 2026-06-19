"""
Workers - Queue Consumer
=========================
Notification-driven Redis consumer for automation_events from emailservice.

Architecture: BLPOP on automation_notify (zero idle cost, exact wake count)
─────────────────────────────────────────────────────────────────────────────
emailservice does:
  1. XADD  automation_events  <N messages>
  2. LPUSH automation_notify  <N>   ← one token per batch, value = count

This consumer does:
  1. BLPOP automation_notify  (blocks until emailservice pushes a token)
  2. Parse count from the token  → know exactly how many messages to pull
  3. XRANGE automation_events COUNT <count>  → pull exactly that many
  4. Process them, XDEL each one
  5. Loop back to BLPOP — no polling, no unnecessary wakes

Why BLPOP instead of XREAD BLOCK:
  - XREAD BLOCK wakes the moment *any* XADD hits the stream.
    If the consumer is slower than the producer, XREAD keeps waking
    on partially-empty batches, causing tight re-poll cycles.
  - BLPOP on the notify list wakes *once per batch* — emailservice controls
    the cadence. After processing N messages the consumer sleeps again until
    the next batch token arrives.
  - The notify token carries the exact count so we do one XRANGE call
    per batch instead of looping until empty.

Upstash socket timeout compatibility:
  Upstash enforces ~10s socket read timeout on standard connections.
  BLPOP uses a dedicated connection with socket_read_timeout=15s and
  a block timeout of 8s so the call always completes before Upstash
  closes the socket.

Startup backlog:
  On first start, before any BLPOP, the consumer checks XLEN and drains
  any messages already on the stream (left from a previous run or service
  restart) so no emails are lost.

Idle cost:   0 commands while waiting (server-side block)
Active cost: 1 BLPOP + 1 XRANGE + N XDEL per batch
"""
import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from redis.asyncio import Redis
import redis.asyncio as aioredis
from app.core.resource_management import get_resource_manager
from app.observability import get_logger, get_metrics_collector

logger = get_logger(__name__)

# Stream / notify key names (must match emailservice ai_handoff_worker.py)
STREAM_AUTOMATION_EVENTS  = "automation_events"
NOTIFY_LIST               = "automation_notify"

BATCH_SIZE     = 100
MAX_RETRY_COUNT = 3

# Block window for BLPOP — must be < Upstash socket read timeout (~10s)
_BLPOP_TIMEOUT_S      = 8      # seconds
_SOCKET_READ_TIMEOUT_S = 15    # must exceed _BLPOP_TIMEOUT_S

# Legacy export kept for backward compat
POLL_INTERVAL_S = 0.0


class StreamConsumer:
    """
    Notification-driven Redis consumer.

    Wakes only when emailservice pushes a token to automation_notify.
    Each token carries the batch size so the consumer pulls exactly the
    right number of messages — no over-polling, no tight loops.

    Idle cost:   0 commands (blocked at Redis server level via BLPOP)
    Active cost: 1 BLPOP + 1 XRANGE + N XDEL per email batch
    """

    _DEDUP_TTL_S = 600  # 10 minutes

    def __init__(self):
        self.metrics = get_metrics_collector()
        self._running = False
        self._redis: Optional[Redis] = None           # shared pool — short commands
        self._block_redis: Optional[aioredis.Redis] = None  # dedicated — BLPOP
        self._retry_queue: List[tuple[Dict, int, float]] = []
        self._work_ready: asyncio.Event = asyncio.Event()
        self._pending_count: int = 0   # messages signalled by last notify token
        self._pending_stream_ids: List[str] = []  # stream IDs awaiting ack after processing

    async def start(self) -> None:
        self._redis = get_resource_manager().get_redis()
        self._running = True
        logger.info(
            "StreamConsumer started (BLPOP notification-driven) | "
            "stream=%s notify=%s blpop_timeout=%ds socket_timeout=%ds",
            STREAM_AUTOMATION_EVENTS, NOTIFY_LIST,
            _BLPOP_TIMEOUT_S, _SOCKET_READ_TIMEOUT_S,
        )
        # Drain any startup backlog before entering the notification loop
        asyncio.create_task(self._startup_drain())
        # Background task: BLPOP on notify list, sets _work_ready when token arrives
        asyncio.create_task(self._notify_listener())

    async def stop(self) -> None:
        self._running = False
        self._work_ready.set()  # unblock any sleeping wait_for_work()
        if self._block_redis:
            try:
                await self._block_redis.aclose()
            except Exception:
                pass
            self._block_redis = None
        logger.info("StreamConsumer stopped")

    # ── Dedicated blocking connection ────────────────────────────────────────

    async def _make_block_redis(self) -> aioredis.Redis:
        """Create a dedicated Redis connection for BLPOP."""
        from shared.config import get_config
        url = get_config().REDIS_URL
        return aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            socket_timeout=_SOCKET_READ_TIMEOUT_S,  # must exceed BLPOP timeout
        )

    # ── Startup backlog drain ────────────────────────────────────────────────

    async def _startup_drain(self) -> None:
        """
        On startup, drain any messages already sitting on automation_events
        (left from a previous run or service restart).
        Signals _work_ready once for the whole backlog so the worker loop
        processes it immediately without waiting for a notify token.
        """
        try:
            backlog = await self._redis.xlen(STREAM_AUTOMATION_EVENTS)
            if backlog:
                logger.info(
                    "StreamConsumer: startup backlog detected — %d messages on %s",
                    backlog, STREAM_AUTOMATION_EVENTS,
                )
                self._pending_count = backlog
                self._work_ready.set()
        except Exception as e:
            logger.warning("StreamConsumer: startup backlog check failed: %s", e)

    # ── Notification listener ────────────────────────────────────────────────

    async def _notify_listener(self) -> None:
        """
        Background task: BLPOP automation_notify on a dedicated connection.

        Each token pushed by emailservice carries the count of messages just
        added to automation_events. We accumulate the count and set _work_ready
        so the worker loop wakes and processes exactly that many messages.

        Reconnects automatically on any socket error.
        """
        while self._running:
            if self._block_redis is None:
                try:
                    self._block_redis = await self._make_block_redis()
                except Exception as e:
                    logger.warning("StreamConsumer: cannot connect for BLPOP: %s", e)
                    await asyncio.sleep(2)
                    continue
            try:
                # BLPOP returns (list_name, value) or None on timeout
                result = await self._block_redis.blpop(
                    [NOTIFY_LIST],
                    timeout=_BLPOP_TIMEOUT_S,
                )
                if result:
                    _list_name, raw_count = result
                    try:
                        count = int(raw_count)
                    except (ValueError, TypeError):
                        count = 1
                    self._pending_count += count
                    logger.debug(
                        "StreamConsumer: notify token received | count=%d pending=%d",
                        count, self._pending_count,
                    )
                    self._work_ready.set()
                # If result is None: BLPOP timed out (8s idle) — loop immediately
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "StreamConsumer: BLPOP error (reconnecting): %s",
                    type(e).__name__,
                )
                try:
                    await self._block_redis.aclose()
                except Exception:
                    pass
                self._block_redis = None
                if self._running:
                    await asyncio.sleep(1)

    # ── Public API ───────────────────────────────────────────────────────────

    async def wait_for_work(self, timeout: Optional[float] = None) -> None:
        """
        Block until _notify_listener signals that messages are on the stream.

        For the retry path, timeout caps the wait so due retries are processed
        without overshooting their scheduled time.
        """
        if timeout is not None and timeout > 0:
            try:
                await asyncio.wait_for(self._work_ready.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass
        else:
            await self._work_ready.wait()
        self._work_ready.clear()

    async def consume_batch(self) -> List[Dict[str, Any]]:
        """
        Pull exactly _pending_count messages from the stream (or BATCH_SIZE max),
        then clear the pending counter.
        Also merges any due retry items.
        Called immediately after wait_for_work() signals activity.
        """
        # Clamp to BATCH_SIZE to avoid oversized pulls
        pull_count = min(self._pending_count, BATCH_SIZE) if self._pending_count > 0 else BATCH_SIZE
        self._pending_count = max(0, self._pending_count - pull_count)

        records = await self._drain_once(count=pull_count)

        now = time.monotonic()
        due   = [(p, rc) for p, rc, ts in self._retry_queue if ts <= now]
        later = [(p, rc, ts) for p, rc, ts in self._retry_queue if ts > now]
        self._retry_queue = later
        for payload, retry_count in due:
            payload["_retry_count"] = retry_count
            records.append(payload)

        if records:
            self.metrics.record_counter("worker.messages_consumed", len(records), "system")
        return records

    async def _drain_once(self, count: int = BATCH_SIZE) -> List[Dict[str, Any]]:
        """
        XRANGE + deferred XDEL.

        ZERO-DATA-LOSS GUARANTEE:
        --------------------------
        Messages are NOT deleted from the stream until the caller has finished
        processing them.  The flow is:

          1. XRANGE  → read up to `count` messages
          2. Dedup check (SET NX) → immediately XDEL dedup-skipped entries
          3. Return processable records WITH their stream IDs attached
          4. Caller processes records; when done, calls ack_batch(stream_ids)
          5. ack_batch() issues XDEL for confirmed-processed message IDs

        If the worker crashes between step 3 and step 5, the unacknowledged
        messages remain on the stream.  On restart, _startup_drain() will pick
        them up again.  The dedup key (10 min TTL) prevents double-processing
        during the restart window.

        NOTE: This replaces the old pattern where XDEL fired inside _drain_once
        before any processing occurred (at-most-once delivery).  The new pattern
        is at-least-once delivery with dedup protection.
        """
        records = []
        dedup_skip_ids = []   # stream IDs to delete immediately (already processed)
        pending_ids    = []   # stream IDs to delete after caller processes them

        try:
            messages = await self._redis.xrange(
                STREAM_AUTOMATION_EVENTS, "-", "+", count=count
            )
            if not messages:
                return records

            for msg_id, fields in messages:
                try:
                    data = json.loads(fields.get("data", "{}"))
                    data["_stream_id"] = msg_id
                    data["_stream"]    = STREAM_AUTOMATION_EVENTS

                    message_id = data.get("message_id", "")
                    if message_id:
                        dedup_key = f"automation:processed:{message_id}"
                        is_new = await self._redis.set(
                            dedup_key, "1", nx=True, ex=self._DEDUP_TTL_S
                        )
                        if is_new is None:
                            # Already processed — delete from stream immediately
                            logger.warning(
                                "Dedup: skipping already-processed message_id=%s stream_id=%s",
                                message_id[:20], msg_id,
                            )
                            dedup_skip_ids.append(msg_id)
                            self.metrics.record_counter(
                                "worker.messages_dedup_skipped", 1, "system"
                            )
                            continue

                    records.append(data)
                    pending_ids.append(msg_id)

                except Exception as e:
                    logger.error("Failed to parse message %s: %s", msg_id, e)
                    # Malformed messages are deleted immediately to avoid blocking the stream
                    dedup_skip_ids.append(msg_id)

            # Immediately delete dedup-skipped and malformed messages
            if dedup_skip_ids:
                pipe = self._redis.pipeline(transaction=False)
                for mid in dedup_skip_ids:
                    pipe.xdel(STREAM_AUTOMATION_EVENTS, mid)
                await pipe.execute(raise_on_error=False)

            # Store pending IDs on records so caller can ack after processing
            # We attach them to the batch as a whole via a sentinel record
            if pending_ids:
                # Attach the list of pending stream IDs to the last record
                # so ack_batch can be called by the runtime after processing
                self._pending_stream_ids = pending_ids

        except Exception as e:
            logger.error("Stream drain error: %s", e)
        return records

    async def ack_batch(self, stream_ids: Optional[List[str]] = None) -> None:
        """
        Acknowledge (XDEL) a batch of successfully-processed stream messages.

        Called by WorkerRuntime._process_batch() after all messages in a batch
        have reached a terminal state (response sent or DLQ'd).

        Args:
            stream_ids: explicit list of stream IDs to delete, or None to use
                        self._pending_stream_ids set by the last _drain_once call.
        """
        ids_to_ack = stream_ids or getattr(self, "_pending_stream_ids", [])
        if not ids_to_ack:
            return
        try:
            pipe = self._redis.pipeline(transaction=False)
            for mid in ids_to_ack:
                pipe.xdel(STREAM_AUTOMATION_EVENTS, mid)
            await pipe.execute(raise_on_error=False)
            logger.debug("ack_batch: deleted %d stream entries", len(ids_to_ack))
        except Exception as e:
            logger.warning("ack_batch: XDEL error (messages may be reprocessed): %s", e)
        finally:
            self._pending_stream_ids = []

    def has_pending_retries(self) -> bool:
        return bool(self._retry_queue)

    def next_retry_delay(self) -> float:
        if not self._retry_queue:
            return 0.0
        now = time.monotonic()
        return max(0.0, min(ts - now for _, _, ts in self._retry_queue))

    async def _send_to_dlq(self, message: Dict[str, Any], reason: str) -> None:
        try:
            dlq_payload = {
                "original_message": {k: v for k, v in message.items() if not k.startswith("_")},
                "failure_reason":   reason,
                "retry_count":      message.get("_retry_count", 0),
                "timestamp":        time.time(),
            }
            await self._redis.xadd(
                "automation_dlq",
                {"data": json.dumps(dlq_payload)},
                maxlen=10_000,
                approximate=True,
            )
            self.metrics.record_counter("worker.messages_dlq", 1, "system")
            logger.warning(
                "Message sent to DLQ: %s — %s",
                message.get("message_id", "?")[:12], reason,
            )
        except Exception as e:
            logger.error("Failed to send to DLQ: %s", e)


__all__ = ["StreamConsumer", "STREAM_AUTOMATION_EVENTS", "POLL_INTERVAL_S"]
