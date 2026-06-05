"""
emailservice — Recovery Worker (Event-Driven)
===============================================
Zero Redis commands when idle. Only reads from Redis when:
  1. A failed event is pushed (push_to_recovery signals _wake_event)
  2. On startup (drain any leftover events from previous crash)
  3. Never otherwise.

How it works:
  - push_to_recovery() → XADD to email_queue → sets _wake_event
  - drain_loop() waits on _wake_event (pure Python, zero Redis)
  - When woken: XRANGE to read all pending → process → XDEL
  - Goes back to sleep until next push

Redis command budget:
  Idle:   0 commands (sleeping on asyncio.Event, not polling Redis)
  On failure: 1 XADD (push) + N XRANGE + N XDEL (drain)
  On startup: 1 XRANGE (check for leftover events)
  vs old: 1 XREADGROUP every 8s = 450/hour
  New:    0/hour when no failures occur
"""
from __future__ import annotations
import asyncio, json, logging, time
from typing import Optional

from shared.cache import get_redis_client
from pipeline import process_gmail_event, process_outlook_event

logger = logging.getLogger("emailservice.recovery")

RECOVERY_STREAM = "email_queue"
_MAXLEN         = 10_000

# In-process signal: set when something is pushed to the recovery queue
_wake_event: asyncio.Event = asyncio.Event()

# In-process fallback queue: if Redis is unavailable, events go here
_in_memory_queue: asyncio.Queue = asyncio.Queue()


async def push_to_recovery(event_type: str, payload: dict) -> None:
    """
    Push a failed event for retry.
    Primary: write to Redis Stream (survives restarts).
    Fallback: in-memory queue (if Redis unavailable).
    Always signals the drain loop to wake up immediately.
    """
    pushed_to_redis = False
    try:
        redis = await get_redis_client()
        await redis.xadd(
            RECOVERY_STREAM,
            {"type": event_type, "data": json.dumps(payload, default=str)},
            maxlen=_MAXLEN,
            approximate=True,
        )
        pushed_to_redis = True
        logger.info("Recovery queued (Redis): type=%s", event_type)
    except Exception as e:
        logger.warning("Redis unavailable for recovery push, using in-memory: %s", e)
        await _in_memory_queue.put({"type": event_type, "data": payload})

    # Wake the drain loop — it will process immediately
    _wake_event.set()


class RecoveryWorker:
    """
    Event-driven recovery worker.
    Sleeps until push_to_recovery() wakes it up.
    Zero Redis commands while idle.
    """

    def __init__(self):
        self._running   = False
        self._processed = 0
        self._errors    = 0

    async def start(self) -> None:
        self._running = True
        logger.info("RecoveryWorker started (event-driven, zero idle cost)")

        # Drain any leftover events from previous crash (1 Redis command on startup)
        await self._drain_redis()

        # Drain any in-memory events (none on fresh start)
        await self._drain_memory()

        # Main loop: sleep until woken by push_to_recovery()
        await self._event_loop()

    async def stop(self) -> None:
        self._running = False
        _wake_event.set()  # unblock the wait
        logger.info("RecoveryWorker stopped | processed=%d errors=%d",
                    self._processed, self._errors)

    async def _event_loop(self) -> None:
        """Sleep until woken, then drain. Zero Redis commands while sleeping."""
        while self._running:
            try:
                # Wait for a push_to_recovery() signal — pure Python, zero Redis
                await asyncio.wait_for(_wake_event.wait(), timeout=None)
                _wake_event.clear()

                if not self._running:
                    break

                # Process everything in the queue
                await self._drain_redis()
                await self._drain_memory()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("RecoveryWorker event loop error: %s", e, exc_info=True)
                await asyncio.sleep(5)

    async def _drain_redis(self) -> None:
        """
        Read and process all messages from the Redis Stream.
        Uses XRANGE (not XREADGROUP) — simpler, no consumer group overhead.
        Deletes messages after successful processing.
        """
        try:
            redis = await get_redis_client()
            # Read up to 100 messages at a time
            while True:
                messages = await redis.xrange(RECOVERY_STREAM, "-", "+", count=100)
                if not messages:
                    break

                for msg_id, fields in messages:
                    success = await self._process_one(fields)
                    if success:
                        await redis.xdel(RECOVERY_STREAM, msg_id)
                        self._processed += 1
                    else:
                        # Failed again — leave in stream, will retry next wake
                        self._errors += 1
                        logger.warning("Recovery retry failed for msg %s — will retry on next event", msg_id)

                # If we got fewer than 100, we've drained the queue
                if len(messages) < 100:
                    break

        except Exception as e:
            logger.error("Redis drain error: %s", e, exc_info=True)

    async def _drain_memory(self) -> None:
        """Process any in-memory fallback events."""
        while not _in_memory_queue.empty():
            try:
                item = _in_memory_queue.get_nowait()
                event_type = item.get("type", "")
                data       = item.get("data", {})
                success    = await self._process_event(event_type, data)
                if not success:
                    # Re-queue for next attempt
                    await _in_memory_queue.put(item)
                    break  # avoid infinite loop on persistent failure
                self._processed += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error("Memory drain error: %s", e)
                break

    async def _process_one(self, fields: dict) -> bool:
        try:
            event_type = fields.get("type", "")
            raw_data   = fields.get("data", "{}")
            data       = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            return await self._process_event(event_type, data)
        except Exception as e:
            logger.error("Recovery process_one error: %s", e, exc_info=True)
            return False

    async def _process_event(self, event_type: str, data: dict) -> bool:
        if event_type == "gmail":
            return await process_gmail_event(
                pubsub_id     = data.get("pubsub_id", ""),
                email_address = data.get("email_address", ""),
                history_id    = data.get("history_id", ""),
            )
        elif event_type == "outlook":
            return await process_outlook_event(
                subscription_id = data.get("subscription_id", ""),
                message_id      = data.get("message_id", ""),
            )
        else:
            logger.warning("Unknown recovery event type: %s — discarding", event_type)
            return True  # discard unknown types
