"""
emailservice — Webhook Layer
==============================
Receives Gmail Pub/Sub and Outlook Graph notifications.

Architecture:
  webhook arrives → process directly (async task) → DB
  On failure → push to email_queue for recovery

Zero Redis commands on the happy path.
Redis only touched on processing failure (rare).
"""
from __future__ import annotations
import asyncio, base64, json, logging, time
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

import config as cfg
from pipeline import process_gmail_event, process_outlook_event
from workers.recovery_worker import push_to_recovery

logger = logging.getLogger("emailservice.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Gmail Pub/Sub ─────────────────────────────────────────────────────────────

@router.post("/gmail")
async def gmail_webhook(request: Request):
    """
    Gmail Pub/Sub push endpoint.
    Processes the notification directly in a background task.
    Returns 200 immediately (< 5ms) — Pub/Sub requirement.
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

        # Process directly in background — no Redis Stream involved
        asyncio.create_task(_handle_gmail(pubsub_id, email_address, history_id))

        logger.debug("Gmail webhook received | email=%s historyId=%s", email_address, history_id)
        return {"status": "accepted"}

    except Exception as e:
        logger.error("Gmail webhook error: %s", e)
        return {"status": "error"}


async def _handle_gmail(pubsub_id: str, email_address: str, history_id: str) -> None:
    """Process Gmail event. On failure, push to recovery queue."""
    success = await process_gmail_event(pubsub_id, email_address, history_id)
    if not success:
        await push_to_recovery("gmail", {
            "pubsub_id":     pubsub_id,
            "email_address": email_address,
            "history_id":    history_id,
        })


@router.get("/gmail")
async def gmail_webhook_probe():
    return {"status": "ok"}


# ── Outlook Graph ─────────────────────────────────────────────────────────────

@router.post("/outlook")
async def outlook_webhook(request: Request):
    """Outlook Graph push endpoint."""
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
            if message_id:
                asyncio.create_task(_handle_outlook(subscription_id, message_id))

        return {"status": "accepted"}
    except Exception as e:
        logger.error("Outlook webhook error: %s", e)
        return {"status": "error"}


async def _handle_outlook(subscription_id: str, message_id: str) -> None:
    success = await process_outlook_event(subscription_id, message_id)
    if not success:
        await push_to_recovery("outlook", {
            "subscription_id": subscription_id,
            "message_id":      message_id,
        })


@router.get("/outlook")
async def outlook_webhook_get(request: Request):
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return PlainTextResponse(content=validation_token, status_code=200)
    return {"status": "ok"}


@router.get("/health")
async def webhook_health():
    return {"status": "healthy", "endpoints": ["/webhooks/gmail", "/webhooks/outlook"]}
