"""
Automation Service — AI Process Endpoint
==========================================
Receives trigger from email-service after a conversation is written to DB.
Runs the full ACRE pipeline and dispatches the reply via email-service.

Flow:
  1. email-service writes incoming message to DB
  2. email-service calls POST /ai/process (this endpoint)
  3. ACRE pipeline runs → generates reply + email_payload
  4. If status=success → call email-service POST /email/send-reply
  5. Return full result to caller
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["ai-engine"])


class ProcessRequest(BaseModel):
    conversation_id: UUID
    trace_id:        Optional[str] = None


class ProcessResponse(BaseModel):
    conversation_id: UUID
    status:          str
    reply:           str
    confidence:      float
    intent_handled:  str
    reason:          Optional[str] = None
    trace_id:        str
    metadata:        Dict[str, Any] = {}
    routing:         Dict[str, Any] = {}
    email_payload:   Optional[Dict[str, Any]] = None
    send_result:     Optional[Dict[str, Any]] = None   # result from email-service send


@router.post("/process", response_model=ProcessResponse)
async def process_conversation(req: ProcessRequest, request: Request):
    """
    Run the ACRE AI pipeline and dispatch the reply via email-service.
    """
    trace_id = req.trace_id or str(uuid.uuid4())

    logger.info(
        "AI process request received",
        extra={"conversation_id": str(req.conversation_id), "trace_id": trace_id},
    )

    # ── Step 1: Run AI pipeline ───────────────────────────────────────────
    try:
        from ai_engine.orchestrator.pipeline import handle_incoming_email_event
        output = await handle_incoming_email_event(
            conversation_id=req.conversation_id,
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error(
            "AI pipeline error",
            extra={"conversation_id": str(req.conversation_id), "trace_id": trace_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    send_result = None

    # ── Step 2: Dispatch reply via email-service ──────────────────────────
    # Only send when status=success AND routing.send_email=True AND payload exists
    if (
        output.status.value == "success"
        and output.routing.send_email
        and output.email_payload
    ):
        send_result = await _dispatch_reply(output, trace_id)
    else:
        logger.info(
            "Reply not dispatched | status=%s send_email=%s has_payload=%s | conv=%s",
            output.status.value,
            output.routing.send_email,
            bool(output.email_payload),
            str(req.conversation_id)[:8],
        )

    return ProcessResponse(
        conversation_id=req.conversation_id,
        status=output.status.value,
        reply=output.reply,
        confidence=output.confidence,
        intent_handled=output.intent_handled,
        reason=output.reason,
        trace_id=trace_id,
        metadata=output.metadata.model_dump(),
        routing=output.routing.model_dump(),
        email_payload=output.email_payload,
        send_result=send_result,
    )


async def _dispatch_reply(output, trace_id: str) -> Dict[str, Any]:
    """
    Call email-service POST /email/send-reply with the validated payload.
    Returns the send result dict. Never raises — failures are logged and returned.
    """
    from shared.config import get_config
    cfg = get_config()

    email_service_url = getattr(cfg, "EMAIL_SERVICE_URL", "http://localhost:8004")
    endpoint = f"{email_service_url}/email/send-reply"

    payload = output.email_payload
    meta    = output.metadata

    # Build the SendReplyRequest payload
    # provider: normalize to lowercase — DB may store "GMAIL", "Gmail", etc.
    raw_provider = payload.get("provider", "gmail")
    provider_normalized = str(raw_provider).lower().strip()

    # from_email: the payload "from" field is the email_account_id UUID.
    # We need the actual email address — fetch it from the account metadata
    # by using the reply_to field (which is the lead's email) and the
    # email_account_id to look up the sender address.
    # The sender address is stored in the conversation's from_email (our account).
    # Use meta.reply_to as the lead email, and we need the account email as sender.
    # The account email is not directly in meta — use a fallback approach:
    # The "from" in headers was set to str(email_account_id) in finalizer.
    # We pass email_account_id and let email-service look up the actual address.
    from_email_val = payload.get("headers", {}).get("from", "") or ""
    # If from_email is a UUID (not an email address), leave it empty —
    # email-service will use the account's email_address from the DB.

    send_payload = {
        "provider":         provider_normalized,
        "email_account_id": meta.email_account_id or "",
        "user_id":          meta.user_id or "",
        "thread_id":        payload.get("headers", {}).get("references", "") or meta.thread_id or "",
        "in_reply_to":      payload.get("headers", {}).get("in_reply_to", "") or meta.message_id or "",
        "references":       payload.get("headers", {}).get("references", "") or meta.thread_id or "",
        "conversation_id":  meta.conversation_id or "",
        "to":               payload.get("headers", {}).get("to", "") or meta.lead_email or "",
        "from_email":       from_email_val,   # will be resolved by email-service from account
        "subject":          payload.get("headers", {}).get("subject", "Re: "),
        "body_text":        payload.get("body", {}).get("text", output.reply),
        "body_html":        payload.get("body", {}).get("html", ""),
        "idempotency_key":  f"{meta.message_id}:{trace_id}",
    }

    # Validate required fields before calling email-service
    missing = [k for k in ("thread_id", "in_reply_to", "to", "email_account_id", "user_id") if not send_payload.get(k)]
    if missing:
        logger.error(
            "Cannot dispatch reply — missing fields: %s | conv=%s",
            missing, meta.conversation_id,
        )
        return {"success": False, "error": f"Missing required fields: {missing}"}

    logger.info(
        "Dispatching reply | provider=%s thread=%s in_reply_to=%s to=%s | conv=%s",
        send_payload["provider"],
        send_payload["thread_id"][:12],
        send_payload["in_reply_to"][:12],
        send_payload["to"],
        meta.conversation_id[:8] if meta.conversation_id else "?",
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=send_payload)

        if resp.status_code == 200:
            result = resp.json()
            if result.get("success"):
                logger.info(
                    "Reply dispatched | provider_msg_id=%s thread=%s | conv=%s",
                    result.get("provider_message_id", "?"),
                    result.get("thread_id", "?")[:12],
                    meta.conversation_id[:8] if meta.conversation_id else "?",
                )
            else:
                logger.warning(
                    "Email-service returned success=False | error=%s | conv=%s",
                    result.get("error", "unknown"),
                    meta.conversation_id[:8] if meta.conversation_id else "?",
                )
            return result
        else:
            logger.error(
                "Email-service send failed | status=%d body=%s | conv=%s",
                resp.status_code, resp.text[:200],
                meta.conversation_id[:8] if meta.conversation_id else "?",
            )
            return {"success": False, "error": f"email-service returned {resp.status_code}"}

    except httpx.TimeoutException:
        logger.error(
            "Email-service send timed out | conv=%s",
            meta.conversation_id[:8] if meta.conversation_id else "?",
        )
        return {"success": False, "error": "email-service timeout"}
    except Exception as exc:
        logger.error(
            "Email-service send exception | error=%s | conv=%s",
            str(exc), meta.conversation_id[:8] if meta.conversation_id else "?",
        )
        return {"success": False, "error": str(exc)}


@router.get("/health")
async def ai_health():
    return {"status": "ok", "engine": "ACRE"}
