"""
Gmail Event Receiver
Receives and validates Gmail Pub/Sub push notifications.

Critical contract with Google Pub/Sub:
  - ALWAYS return HTTP 200. Any non-200 causes Pub/Sub to retry indefinitely,
    creating a retry storm that exhausts Redis connections and DB pools.
  - Deduplication prevents double-processing of retried messages.
"""

from typing import Dict, Any, Optional
from fastapi import Request
import base64
import json

from shared.logger import get_logger
from provider.filters.email_filter import EmailFilter
from provider.deduplicator.event_deduplicator import EventDeduplicator
from normalizer.normalizer import EmailNormalizer
from email_queue.producer.event_producer import EventProducer

logger = get_logger(__name__)


class GmailReceiver:
    """Handles incoming Gmail Pub/Sub notifications."""

    def __init__(self):
        self.email_filter   = EmailFilter()
        self.deduplicator   = EventDeduplicator()
        self.normalizer     = EmailNormalizer()
        self.queue_producer = EventProducer()

    async def receive_notification(self, request: Request) -> Dict[str, Any]:
        """
        Full pipeline:
          1. Parse Pub/Sub envelope
          2. Dedup on Pub/Sub messageId  (Redis — fast path, stops retry storm)
          3. Normalize  (adapter fetches full message from Gmail API)
          4. Filter     (spam / OTP / no-reply)
          5. Dedup on Gmail message_id   (second layer)
          6. Push to Celery queue

        Always returns a dict — never raises. HTTP 200 is always sent.
        """
        # ── 1. Parse envelope ────────────────────────────────────────────────
        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse Pub/Sub body: {e}")
            return {"status": "error", "reason": "invalid_json"}

        message    = body.get("message", {})
        pubsub_id  = message.get("messageId")

        if not pubsub_id:
            logger.warning("Pub/Sub message missing messageId")
            return {"status": "error", "reason": "missing_message_id"}

        # ── 2. Dedup on Pub/Sub messageId ────────────────────────────────────
        dedup_key = f"gmail_pubsub_{pubsub_id}"
        try:
            if await self.deduplicator.is_duplicate(dedup_key):
                logger.debug(f"Duplicate Pub/Sub message: {pubsub_id}")
                return {"status": "duplicate", "pubsub_id": pubsub_id}
        except Exception as e:
            # Redis unavailable — log and continue (don't block the pipeline)
            logger.error(f"Dedup check failed (Redis?): {e}")

        # ── 3. Decode Pub/Sub data ───────────────────────────────────────────
        data_b64 = message.get("data", "")
        try:
            data          = json.loads(base64.b64decode(data_b64).decode("utf-8"))
            email_address = data.get("emailAddress")
            history_id    = data.get("historyId")
        except Exception as e:
            logger.error(f"Failed to decode Pub/Sub data: {e}")
            return {"status": "error", "reason": "invalid_data_encoding"}

        if not email_address or not history_id:
            logger.warning(f"Pub/Sub data missing fields: {data}")
            return {"status": "error", "reason": "missing_fields"}

        logger.debug(f"Pub/Sub notification: email={email_address} historyId={history_id}")

        # Mark Pub/Sub message processed BEFORE doing any expensive work.
        try:
            await self.deduplicator.mark_processed(dedup_key)
        except Exception as e:
            logger.error(f"Failed to mark Pub/Sub message processed: {e}")

        # ── 4. Normalize ─────────────────────────────────────────────────────
        logger.debug(f"[PIPELINE] Normalizing event for {email_address}")
        raw_event = {
            "provider":      "gmail",
            "email_address": email_address,
            "history_id":    history_id,
            "message_id":    pubsub_id,
            "timestamp":     message.get("publishTime"),
        }

        normalized_event = await self.normalizer.normalize("gmail", raw_event)

        if not normalized_event:
            # Track unknown watches for cleanup — but only log once per hour per address
            if email_address:
                try:
                    from shared.cache import get_redis
                    redis = await get_redis()
                    await redis.sadd("gmail:unknown:watches", email_address)
                    await redis.expire("gmail:unknown:watches", 86400 * 7)
                    # Rate-limit the warning: log at most once per hour per address
                    rate_key = f"gmail:unknown:warned:{email_address}"
                    already_warned = await redis.exists(rate_key)
                    if not already_warned:
                        await redis.setex(rate_key, 3600, "1")
                        logger.warning(
                            f"[PIPELINE] Pub/Sub for unknown account: {email_address} "
                            "(old watch — expires in ≤7 days). "
                            "POST /subscriptions/stop-unknown-watch to stop immediately."
                        )
                except Exception:
                    pass
            # For known accounts, None just means no new messages — silent
            return {
                "status":     "skipped",
                "reason":     "no_new_messages",
                "history_id": history_id,
            }

        logger.debug(
            f"[PIPELINE] Normalized: "
            f"message_id={normalized_event.message_id} "
            f"subject='{normalized_event.subject}' "
            f"from={normalized_event.from_email}"
        )

        # ── 5. Filter ─────────────────────────────────────────────────────────
        try:
            if await self.email_filter.should_filter(
                normalized_event.subject,
                normalized_event.from_email
            ):
                logger.info(
                    f"[PIPELINE] STOPPED at Step 2 — FILTERED: "
                    f"subject='{normalized_event.subject}' from='{normalized_event.from_email}'"
                )
                return {
                    "status":     "filtered",
                    "message_id": normalized_event.message_id,
                    "reason":     "spam_or_otp",
                }
        except Exception as e:
            logger.error(f"Filter check failed: {e}")

        # ── 6. Dedup on Gmail message_id ──────────────────────────────────────
        gmail_dedup_key = f"gmail_msg_{normalized_event.message_id}"
        try:
            if await self.deduplicator.is_duplicate(gmail_dedup_key):
                logger.debug(f"[PIPELINE] DUPLICATE message_id={normalized_event.message_id}")
                return {"status": "duplicate", "message_id": normalized_event.message_id}
            await self.deduplicator.mark_processed(gmail_dedup_key)
        except Exception as e:
            logger.error(f"Message-level dedup failed: {e}")

        # ── 7. Push to queue ──────────────────────────────────────────────────
        try:
            queued = await self.queue_producer.produce(normalized_event)
        except Exception as e:
            logger.error(f"Failed to push to queue: {e}")
            queued = False

        if not queued:
            logger.error(
                f"[PIPELINE] Could not queue event "
                f"message_id={normalized_event.message_id}. "
                f"Check Redis connection and Celery worker."
            )

        return {
            "status":     "queued" if queued else "processed",
            "message_id": normalized_event.message_id,
            "user_id":    normalized_event.user_id,
            "queued":     queued,
        }
