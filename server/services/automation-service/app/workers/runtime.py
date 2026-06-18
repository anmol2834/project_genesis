"""
Workers - Runtime
=================
Notification-driven worker runtime orchestrating consumer → processor → executor pipeline.

Wake model:
  emailservice sends one LPUSH to automation_notify per batch of emails.
  The worker sleeps (BLPOP) until a token arrives, processes exactly that
  many messages, then goes back to sleep — zero Redis activity while idle.

Priority processing order within each batch:
  P0 (critical) processed first — legal, compliance, security
  P1 (high)     processed second — refunds, angry customers, VIP
  P2 (medium)   processed third — normal pipeline
  P3 (low)      processed last  — cache-first, minimal cost
"""
import asyncio
import re
import time
from typing import Optional, List, Tuple
from datetime import datetime
from app.workers.consumer import StreamConsumer, MAX_RETRY_COUNT
from app.workers.processor import MessageProcessor
from app.workers.execution import get_execution_engine
from app.observability import get_logger, get_metrics_collector

logger = get_logger(__name__)

# P0 keyword pattern — fast pre-classification before full pipeline
_P0_PATTERN = re.compile(
    r"\b(lawsuit|sue[sd]?|suing|legal action|attorney|solicitor|court|litigation|"
    r"fraud|regulatory|compliance|gdpr|data breach|hack|stolen data)\b",
    re.IGNORECASE,
)
_P1_PATTERN = re.compile(
    r"\b(refund|chargeback|dispute|cancel.*subscription|cancel.*contract|"
    r"SLA|breach|angry|furious|vip|priority.customer|escalate)\b",
    re.IGNORECASE,
)


def _quick_priority(message: dict) -> int:
    """
    Fast O(1) priority estimate from raw message dict.
    Used to sort a batch before processing — no OpenAI call.
    Returns 0-3 (lower = higher priority).
    """
    # Respect priority already set by emailservice
    raw_priority = message.get("_priority", message.get("priority", 5))
    try:
        ep = int(raw_priority)
        if ep == 0:
            return 0  # already marked critical
    except (TypeError, ValueError):
        ep = 5

    content = str(message.get("content", "")).lower()
    subject = str(message.get("subject", "")).lower()
    text = f"{subject} {content}"

    if _P0_PATTERN.search(text):
        return 0
    if _P1_PATTERN.search(text):
        return 1
    if ep <= 1:
        return 1
    if ep <= 3:
        return 2
    return 3


class WorkerRuntime:
    """
    Priority-aware worker runtime managing complete message processing pipeline.

    Pipeline:
    1. Consumer reads from Redis Streams
    2. Batch sorted by priority (P0 → P1 → P2 → P3)
    3. Processor validates and transforms messages
    4. Executor runs orchestrated AI workflow
    5. Consumer ACKs or NACKs based on result
    """

    def __init__(self):
        self.consumer = StreamConsumer()
        self.processor = MessageProcessor()
        self.executor = get_execution_engine()
        self.metrics = get_metrics_collector()

        self._running = False
        self._worker_count = 1
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        logger.info("═" * 70)
        logger.info("WORKER RUNTIME STARTING (priority-aware)")
        logger.info("═" * 70)
        await self.consumer.start()
        self._running = True
        logger.info("Worker runtime started (workers=%d)", self._worker_count)

    async def stop(self) -> None:
        logger.info("Stopping worker runtime...")
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.consumer.stop()
        logger.info("Worker runtime stopped")

    async def run(self) -> None:
        # NOTE: start() is called by the caller (app/main.py) before create_task(run()).
        # Do NOT call start() here again — that would create duplicate consumers.
        try:
            self._tasks = [
                asyncio.create_task(self._worker_loop(i))
                for i in range(self._worker_count)
            ]
            await asyncio.gather(*self._tasks)
        except Exception as e:
            logger.error("Worker runtime error: %s", e, exc_info=True)
            raise
        # Task 15 fix (R22): do NOT call self.stop() here.
        # app/main.py lifespan already calls worker_runtime.stop() explicitly
        # during shutdown. A second stop() call double-closes the Redis pubsub
        # connection and can raise redis.asyncio exceptions during graceful exit.

    async def _worker_loop(self, worker_id: int) -> None:
        """
        Notification-driven processing loop.

        Design:
          1. Wait for emailservice to push a notify token (BLPOP wake via
             StreamConsumer._notify_listener).
          2. consume_batch() pulls exactly the notified count from the stream.
          3. Process the batch.
          4. If _pending_count > 0 (multiple tokens arrived while processing)
             immediately loop without sleeping so nothing is left behind.
          5. Otherwise go back to wait — zero Redis activity until next notify.

        This gives the user's desired behaviour:
          "automation-service polls only when emailservice sends a notification
           indicating how many incoming messages to process, then loops back
           only as many times as notifications — no unnecessary polling."
        """
        logger.info("Worker %d started (notification-driven)", worker_id)
        consecutive_errors = 0
        max_consecutive_errors = 10

        while self._running:
            try:
                # ── Step 1: Wait for work notification ───────────────────
                # If retries are pending, use a capped timeout so due retries
                # are never delayed beyond their scheduled window.
                # Otherwise block indefinitely — zero Redis commands while idle.
                if self.consumer.has_pending_retries():
                    retry_delay = self.consumer.next_retry_delay()
                    await self.consumer.wait_for_work(
                        timeout=retry_delay if retry_delay > 0 else None
                    )
                else:
                    await self.consumer.wait_for_work()

                if not self._running:
                    break

                # ── Step 2 & 3: Pull and process notified batch ──────────
                # consume_batch() returns exactly the messages signalled by
                # the notify token (plus any due retries).  If the producer
                # sent multiple tokens while we were processing, _pending_count
                # will be > 0 after the first batch and we loop immediately
                # (inner while) to drain them without re-entering the outer
                # wait — this is the "loop only as many times as notifications"
                # behaviour the user requires.
                while self._running:
                    messages = await self.consumer.consume_batch()
                    if not messages and self.consumer._pending_count == 0:
                        break  # all notified messages processed — go back to sleep

                    if not messages:
                        # _pending_count > 0 but stream is empty (race: dedup
                        # consumed the message already).  Clear and sleep.
                        self.consumer._pending_count = 0
                        break

                    consecutive_errors = 0
                    messages = sorted(messages, key=_quick_priority)
                    await self._process_batch(messages, worker_id)

                    # If more tokens accumulated during processing, loop again
                    # immediately; otherwise break and wait for next notification.
                    if self.consumer._pending_count == 0:
                        break

            except asyncio.CancelledError:
                logger.info("Worker %d cancelled", worker_id)
                break

            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    "Worker %d error (%d/%d): %s",
                    worker_id, consecutive_errors, max_consecutive_errors, e,
                    exc_info=True,
                )
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(
                        "Worker %d exceeded max consecutive errors - stopping", worker_id
                    )
                    break
                await asyncio.sleep(min(2 ** consecutive_errors * 0.1, 5.0))

        logger.info("Worker %d stopped", worker_id)

    async def _process_batch(self, messages: list[dict], worker_id: int) -> None:
        start = time.perf_counter()
        processed = skipped = failed = 0
        p0_count = p1_count = p2_count = p3_count = 0

        for message in messages:
            msg_priority = _quick_priority(message)
            if msg_priority == 0:
                p0_count += 1
            elif msg_priority == 1:
                p1_count += 1
            elif msg_priority == 2:
                p2_count += 1
            else:
                p3_count += 1

            # Stamp priority into message for processor → execution_engine
            message["_priority"] = msg_priority

            try:
                should_skip, skip_reason = self.processor.should_skip(message)
                if should_skip:
                    logger.debug("Skipping message: %s", skip_reason,
                                 message_id=message.get("message_id"))
                    skipped += 1
                    continue

                event = await self.processor.process(message)
                if not event:
                    failed += 1
                    continue

                response = await self.executor.execute(event)
                await self._send_response_to_emailservice(response)
                processed += 1

                logger.debug(
                    "Message processed | user=%s msg=%s action=%s priority=P%d",
                    event.user_id, event.message_id, response.action, msg_priority,
                )

            except Exception as e:
                # Requeue with exponential backoff (in-memory, no Redis)
                retry_count = message.get("_retry_count", 0) + 1
                if retry_count <= MAX_RETRY_COUNT:
                    delay = min(2 ** (retry_count - 1) * 0.1, 30.0)
                    next_attempt = time.monotonic() + delay
                    payload = {k: v for k, v in message.items() if not k.startswith("_")}
                    self.consumer._retry_queue.append((payload, retry_count, next_attempt))
                    self.metrics.record_counter("worker.messages_retried", 1, "system")
                else:
                    # Send to DLQ after max retries
                    await self.consumer._send_to_dlq(message, str(e))
                failed += 1
                logger.warning(
                    "Message processing failed: %s | msg=%s user=%s",
                    e, message.get("message_id"), message.get("user_id"),
                )

        elapsed = (time.perf_counter() - start) * 1000

        self.metrics.record_histogram("worker.batch_duration_ms", elapsed, "system")
        self.metrics.record_counter("worker.batch_processed", processed, "system")
        self.metrics.record_counter("worker.batch_skipped",   skipped,   "system")
        self.metrics.record_counter("worker.batch_failed",    failed,    "system")
        if p0_count:
            self.metrics.record_counter("worker.priority.p0", p0_count, "system")
        if p1_count:
            self.metrics.record_counter("worker.priority.p1", p1_count, "system")

        if processed > 0 or failed > 0:
            logger.info(
                "Worker %d batch done | ok=%d skip=%d fail=%d "
                "P0=%d P1=%d P2=%d P3=%d latency=%.1fms",
                worker_id, processed, skipped, failed,
                p0_count, p1_count, p2_count, p3_count, elapsed,
            )

    async def _send_response_to_emailservice(self, response) -> None:
        try:
            from app.core.resource_management import get_resource_manager
            import json

            redis = get_resource_manager().get_redis()
            payload = {
                "conversation_id":   response.conversation_id,
                "message_id":        response.message_id,
                "thread_id":         response.thread_id,
                "user_id":           response.user_id,
                "response_text":     response.response_text,
                "action":            response.action,
                "confidence":        response.confidence,
                "intent":            response.intent,
                "send_email":        response.send_email,
                "trace_id":          response.trace_id,
                "correlation_id":    response.correlation_id,
                "processing_time_ms": response.processing_time_ms,
                "timestamp":         time.time(),
            }
            pipe = redis.pipeline(transaction=False)
            pipe.xadd(
                "automation_responses",
                {"data": json.dumps(payload)},
                maxlen=10_000,
                approximate=True,
            )
            pipe.lpush("automation_responses_notify", "1")
            await pipe.execute()
            logger.info(
                "✅ Response sent | conv=%s action=%s confidence=%.2f",
                response.conversation_id[:12], response.action, response.confidence,
            )
        except Exception as e:
            logger.error("❌ Failed to send response to email-service: %s", e, exc_info=True)
            raise


# Global worker runtime
_worker_runtime: Optional[WorkerRuntime] = None


def get_worker_runtime() -> WorkerRuntime:
    global _worker_runtime
    if _worker_runtime is None:
        _worker_runtime = WorkerRuntime()
    return _worker_runtime


__all__ = ["WorkerRuntime", "get_worker_runtime", "_quick_priority", "_P0_PATTERN", "_P1_PATTERN"]
