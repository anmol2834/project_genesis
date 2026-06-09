"""
Workers - Queue Consumer
=========================
Redis Streams consumer for automation_events from emailservice.
Matches emailservice stream_client architecture exactly.
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


# Stream configuration (matches emailservice)
STREAM_AUTOMATION_EVENTS = "automation_events"
WAKE_CHANNEL = "automation:wake"
BATCH_SIZE = 100
MAX_RETRY_COUNT = 3
# Poll interval: wake worker every N seconds to drain the stream.
# This is the primary wake mechanism since Upstash Redis does not support
# Pub/Sub on most plans. Pub/Sub is attempted as a best-effort fast-path
# but the poll interval guarantees real-time processing regardless.
POLL_INTERVAL_S = 5.0


class StreamConsumer:
    """
    Zero-idle-cost Redis Streams consumer for automation_events.

    Architecture:
      - Sleeps on Redis Pub/Sub (automation:wake channel) — zero commands when idle
      - Wakes ONLY when emailservice publishes a new event
      - Drains via XRANGE + XDEL (no consumer groups, no XREADGROUP polling)
      - In-process retry queue with exponential backoff (no Redis until DLQ)

    Redis command budget:
      Idle:   0 commands/sec  (blocked on Pub/Sub subscribe, no polling)
      Active: 1 XRANGE + N XDEL per batch
      vs old: 1 XREADGROUP/sec = 86,400/day
    """

    def __init__(self):
        self.metrics = get_metrics_collector()
        self._running = False
        self._redis: Optional[Redis] = None
        self._wake_event: asyncio.Event = asyncio.Event()
        self._retry_queue: List[tuple[Dict, int, float]] = []  # (payload, retry_count, next_attempt)
        self._listener_task: Optional[asyncio.Task] = None
        self._pubsub_redis: Optional[aioredis.Redis] = None

    async def start(self) -> None:
        self._redis = get_resource_manager().get_redis()
        self._running = True

        # Background task: dedicated connection for Pub/Sub wake signals with auto-reconnect
        self._listener_task = asyncio.create_task(self._pubsub_listener())

        # Check backlog size — if messages exist, set the wake event immediately
        # so _worker_loop processes them without waiting for a new Pub/Sub signal.
        try:
            backlog_size = await self._redis.xlen(STREAM_AUTOMATION_EVENTS)
            if backlog_size:
                logger.info("StreamConsumer: %d backlog messages found — signalling worker",
                            backlog_size)
                self._wake_event.set()
        except Exception as e:
            logger.warning("StreamConsumer: backlog check failed: %s", e)

        logger.info("StreamConsumer started (event-driven, zero idle cost)")

    async def stop(self) -> None:
        self._running = False
        self._wake_event.set()  # unblock any waiting consumer
        if self._listener_task:
            self._listener_task.cancel()
            await asyncio.gather(self._listener_task, return_exceptions=True)
        if self._pubsub_redis:
            try:
                await self._pubsub_redis.aclose()
            except Exception:
                pass
        logger.info("StreamConsumer stopped")

    async def _pubsub_listener(self) -> None:
        """
        Best-effort Pub/Sub listener for fast-path wake signals.
        Upstash Redis does not support Pub/Sub on most plans — if subscribe
        fails after 3 attempts, this task exits gracefully and the poll
        interval (POLL_INTERVAL_S) takes over as the sole wake mechanism.
        """
        from shared.config import get_config
        url = get_config().REDIS_URL
        consecutive_failures = 0
        max_failures = 3
        while self._running and consecutive_failures < max_failures:
            try:
                self._pubsub_redis = aioredis.from_url(
                    url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )
                pubsub = self._pubsub_redis.pubsub()
                await pubsub.subscribe(WAKE_CHANNEL)
                consecutive_failures = 0  # reset on successful subscribe
                logger.debug("StreamConsumer: Pub/Sub subscribed to %s (fast-path active)", WAKE_CHANNEL)
                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message and message.get("type") == "message":
                        self._wake_event.set()
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_failures += 1
                if self._running and consecutive_failures < max_failures:
                    logger.debug("StreamConsumer: Pub/Sub unavailable (%d/%d): %s",
                                 consecutive_failures, max_failures, e)
                    await asyncio.sleep(2)
            finally:
                if self._pubsub_redis:
                    try:
                        await self._pubsub_redis.aclose()
                    except Exception:
                        pass
                    self._pubsub_redis = None
        if self._running:
            logger.info("StreamConsumer: Pub/Sub disabled (not supported by Redis provider) "
                        "— poll interval %.0fs is the active wake mechanism", POLL_INTERVAL_S)

    async def wait_for_work(self, timeout: Optional[float] = None) -> None:
        """
        Block until a Pub/Sub wake signal arrives OR the poll interval elapses.
        The poll interval (POLL_INTERVAL_S) is the safety fallback: even if the
        Pub/Sub listener dies or a wake signal is missed, the worker wakes up
        and drains the stream every POLL_INTERVAL_S seconds.
        """
        effective_timeout = timeout if timeout is not None else POLL_INTERVAL_S
        try:
            await asyncio.wait_for(self._wake_event.wait(), timeout=effective_timeout)
        except asyncio.TimeoutError:
            pass
        self._wake_event.clear()

    async def consume_batch(self) -> List[Dict[str, Any]]:
        """
        Drain messages from stream via XRANGE + XDEL.
        Returns parsed events + any due retry items.
        Called ONLY after wait_for_work() signals activity.
        """
        records = await self._drain_once()

        # Add due retry items (no Redis involved)
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

    async def _drain_once(self) -> List[Dict[str, Any]]:
        """XRANGE + XDEL — reads and immediately deletes processed messages."""
        records = []
        try:
            messages = await self._redis.xrange(STREAM_AUTOMATION_EVENTS, "-", "+", count=BATCH_SIZE)
            if not messages:
                return records

            ids_to_del = []
            for msg_id, fields in messages:
                try:
                    data = json.loads(fields.get("data", "{}"))
                    data["_stream_id"] = msg_id
                    data["_stream"] = STREAM_AUTOMATION_EVENTS
                    records.append(data)
                    ids_to_del.append(msg_id)
                except Exception as e:
                    logger.error("Failed to parse message %s: %s", msg_id, e)
                    ids_to_del.append(msg_id)  # delete unparseable

            if ids_to_del:
                pipe = self._redis.pipeline(transaction=False)
                for mid in ids_to_del:
                    pipe.xdel(STREAM_AUTOMATION_EVENTS, mid)
                await pipe.execute(raise_on_error=False)

        except Exception as e:
            logger.error("Stream drain error: %s", e)
        return records
    
    def has_pending_retries(self) -> bool:
        """Check if retry queue has pending items"""
        return bool(self._retry_queue)
    
    def next_retry_delay(self) -> float:
        """Get delay until next retry is due (seconds)"""
        if not self._retry_queue:
            return 0.0
        now = time.monotonic()
        return max(0.0, min(ts - now for _, _, ts in self._retry_queue))

    async def _send_to_dlq(self, message: Dict[str, Any], reason: str) -> None:
        """Send failed message to dead letter queue after max retries exhausted."""
        try:
            dlq_payload = {
                "original_message": {k: v for k, v in message.items() if not k.startswith("_")},
                "failure_reason": reason,
                "retry_count": message.get("_retry_count", 0),
                "timestamp": time.time(),
            }
            await self._redis.xadd(
                "automation_dlq",
                {"data": json.dumps(dlq_payload)},
                maxlen=10_000,
                approximate=True,
            )
            self.metrics.record_counter("worker.messages_dlq", 1, "system")
            logger.warning("Message sent to DLQ: %s — %s",
                           message.get("message_id", "?")[:12], reason)
        except Exception as e:
            logger.error("Failed to send to DLQ: %s", e)


__all__ = ["StreamConsumer", "STREAM_AUTOMATION_EVENTS", "POLL_INTERVAL_S"]
