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
from app.core.resource_management import get_resource_manager
from app.observability import get_logger, get_metrics_collector

logger = get_logger(__name__)


# Stream configuration (matches emailservice)
STREAM_AUTOMATION_EVENTS = "automation_events"
WAKE_CHANNEL = "automation:wake"
BATCH_SIZE = 100
MAX_RETRY_COUNT = 3


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
        self._pubsub = None
        self._wake_event: asyncio.Event = asyncio.Event()
        self._retry_queue: List[tuple[Dict, int, float]] = []  # (payload, retry_count, next_attempt)
        self._listener_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._redis = get_resource_manager().get_redis()
        self._running = True

        # Subscribe to wake channel — zero-cost idle
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(WAKE_CHANNEL)

        # Background task: listens for wake signals and sets the asyncio.Event
        self._listener_task = asyncio.create_task(self._pubsub_listener())

        # Drain any backlog left from previous run (startup only — 1 XRANGE)
        backlog = await self._drain_once()
        if backlog:
            logger.info("StreamConsumer: drained %d backlog messages on startup", len(backlog))

        logger.info("StreamConsumer started (event-driven, zero idle cost)")

    async def stop(self) -> None:
        self._running = False
        self._wake_event.set()  # unblock any waiting consumer
        if self._listener_task:
            self._listener_task.cancel()
            await asyncio.gather(self._listener_task, return_exceptions=True)
        if self._pubsub:
            await self._pubsub.unsubscribe(WAKE_CHANNEL)
            await self._pubsub.aclose()
        logger.info("StreamConsumer stopped")

    async def _pubsub_listener(self) -> None:
        """Listens on automation:wake channel. Sets asyncio.Event on each message."""
        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break
                if message and message.get("type") == "message":
                    self._wake_event.set()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Pub/Sub listener error: %s", e)

    async def wait_for_work(self, timeout: Optional[float] = None) -> None:
        """
        Sleep until woken by a Pub/Sub message or a retry becomes due.
        Zero Redis commands while sleeping.
        """
        self._wake_event.clear()
        try:
            if timeout is not None:
                await asyncio.wait_for(self._wake_event.wait(), timeout=timeout)
            else:
                await self._wake_event.wait()
        except asyncio.TimeoutError:
            pass

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


__all__ = ["StreamConsumer", "STREAM_AUTOMATION_EVENTS"]
