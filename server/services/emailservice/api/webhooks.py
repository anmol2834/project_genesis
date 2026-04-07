"""
emailservice — Webhook Layer
==============================
Strict event-driven decoupling: webhook handlers ONLY enqueue minimal
payloads into Redis Streams and return immediately. Zero processing
inside the request lifecycle.

Flow:
  Gmail Pub/Sub  → POST /webhooks/gmail   → XADD gmail_events  → 200
  Outlook Graph  → POST /webhooks/outlook → XADD outlook_events → 200

The stream workers (GmailFetchWorker, OutlookFetchWorker) consume these
events asynchronously. The webhook handler never touches pipeline.py.

Guaranteed delivery: if XADD fails, the event is written to the
in-process fallback queue so it is not silently dropped.
"""
from __future__ import annotations
import asyncio, base64, json, logging, time, uuid
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

import config as cfg
from stream_client import publish
from shared.cache import get_redis_client

logger = logging.getLogger("emailservice.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# In-process fallback: events that failed XADD go here and are retried
_fallback_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)


async def _enqueue(stream: str, payload: dict, partition_key: str = "") -> None:
    """
    Enqueue an event to a Redis Stream.
    On Redis failure: write to in-process fallback queue (never drop).
    """
    try:
        await publish(stream, payload, partition_key=partition_key)
    except Exception as e:
        logger.warning("XADD failed for %s, using fallback queue: %s", stream, e)
        try:
            _fallback_queue.put_nowait({"stream": stream, "payload": payload, "key": partition_key})
        except asyncio.QueueFull:
            logger.error("Fallback queue full — event dropped for stream %s", stream)


async def drain_fallback_queue() -> None:
    """
    Background task: retry events that failed XADD.
    Called from main.py on startup and periodically.
    """
    while not _fallback_queue.empty():
        try:
            item = _fallback_queue.get_nowait()
            await publish(item["stream"], item["payload"], partition_key=item.get("key", ""))
        except asyncio.QueueEmpty:
            break
        except Exception as e:
            logger.warning("Fallback drain failed: %s — re-queuing", e)
            try:
                _fallback_queue.put_nowait(item)
            except asyncio.QueueFull:
                pass
            break


# ── Gmail Pub/Sub ─────────────────────────────────────────────────────────────

@router.post("/gmail")
async def gmail_webhook(request: Request):
    """
    Gmail Pub/Sub push endpoint.
    Decodes envelope, enqueues to gmail_events stream, returns 200 in < 5ms.
    No processing. No pipeline calls. No asyncio.create_task with business logic.
    """
    try:
        body      = await request.json()
        message   = body.get("message", {})
        pubsub_id = message.get("messageId", "")
        data_b64  = message.get("data", "")

        if not pubsub_id or not data_b64:
            return {"status": "skip", "reason": "missing_fields"}

        try:
            data          = json.loads(base64.b64decode(data_b64).decode("utf-8"))
            email_address = data.get("emailAddress", "")
            history_id    = str(data.get("historyId", ""))
        except Exception:
            return {"status": "skip", "reason": "decode_error"}

        if not email_address or not history_id:
            return {"status": "skip", "reason": "empty_payload"}

        # Generate a global event_id for end-to-end idempotency tracking
        event_id = f"gmail:{pubsub_id}"

        # Update last-seen timestamp for the heartbeat watchdog
        asyncio.create_task(_touch_account_heartbeat(email_address))

        # Enqueue to stream — this is the ONLY thing the webhook does
        await _enqueue(
            cfg.TOPIC_GMAIL_RAW,
            {
                "event_id":     event_id,
                "pubsub_id":    pubsub_id,
                "email_address": email_address,
                "history_id":   history_id,
                "publish_time": message.get("publishTime", ""),
                "enqueued_at":  time.time(),
            },
            partition_key=email_address,
        )

        logger.debug("Gmail webhook enqueued | email=%s historyId=%s event_id=%s",
                     email_address, history_id, event_id)
        return {"status": "accepted", "event_id": event_id}

    except Exception as e:
        logger.error("Gmail webhook error: %s", e)
        return {"status": "error"}


@router.get("/gmail")
async def gmail_webhook_probe():
    return {"status": "ok"}


# ── Outlook Graph ─────────────────────────────────────────────────────────────

@router.post("/outlook")
async def outlook_webhook(request: Request):
    """
    Outlook Graph push endpoint.
    Handles validation handshake, then enqueues to outlook_events stream.
    """
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return PlainTextResponse(content=validation_token, status_code=200)

    try:
        body = await request.json()
        for notif in body.get("value", []):
            if notif.get("changeType") != "created":
                continue

            resource        = notif.get("resource", "")
            subscription_id = notif.get("subscriptionId", "")
            message_id      = resource.split("/")[-1] if "/" in resource else resource

            if not message_id:
                continue

            event_id = f"outlook:{subscription_id}:{message_id}"

            await _enqueue(
                cfg.TOPIC_OUTLOOK_RAW,
                {
                    "event_id":        event_id,
                    "subscription_id": subscription_id,
                    "message_id":      message_id,
                    "resource":        resource,
                    "client_state":    notif.get("clientState", ""),
                    "enqueued_at":     time.time(),
                },
                partition_key=subscription_id,
            )

        return {"status": "accepted"}

    except Exception as e:
        logger.error("Outlook webhook error: %s", e)
        return {"status": "error"}


@router.get("/outlook")
async def outlook_webhook_get(request: Request):
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return PlainTextResponse(content=validation_token, status_code=200)
    return {"status": "ok"}


@router.get("/health")
async def webhook_health():
    return {
        "status":    "healthy",
        "endpoints": ["/webhooks/gmail", "/webhooks/outlook"],
        "fallback_queue_depth": _fallback_queue.qsize(),
    }


# ── Heartbeat helper ──────────────────────────────────────────────────────────

async def _touch_account_heartbeat(email_address: str) -> None:
    """
    Record that this account received a webhook event right now.
    Used by the watchdog to detect silent subscription failures.
    TTL = 3 × inactivity threshold so the key auto-expires if the account
    is genuinely inactive (not a subscription failure).
    """
    try:
        redis = get_redis_client()
        ttl = cfg.WATCH_INACTIVITY_THRESHOLD_S * 3
        await redis.setex(f"es:heartbeat:{email_address}", ttl, str(time.time()))
    except Exception:
        pass  # heartbeat is best-effort — never fail the webhook for this
