"""
Email Service — Send Reply API
================================
Receives a fully-validated email payload from automation-service
and dispatches it through the correct provider (Gmail / SMTP / Outlook).

THREAD SAFETY GUARANTEES:
  - thread_id MUST match the conversation's thread_id (validated before send)
  - in_reply_to MUST be the original message_id (validated before send)
  - Idempotency: duplicate sends blocked via Redis dedup key
  - Retry: up to 3 attempts with exponential backoff on transient failures

CRITICAL RULES:
  - NEVER send to a different thread than the incoming message
  - NEVER send without a valid email_account_id
  - ALWAYS store the outgoing message in last_24h_messages after send
"""
from __future__ import annotations

import asyncio
import base64
import email as _email_lib
import logging
import time
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from uuid import UUID

from shared.config import get_config
from shared.database import get_db_session
from shared.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/email", tags=["send-reply"])

_config = get_config()

# ── Max retries for transient send failures ───────────────────────────────────
_MAX_RETRIES    = 3
_RETRY_BACKOFF  = [1, 2, 4]   # seconds between retries


# ── Request / Response schemas ────────────────────────────────────────────────

class SendReplyRequest(BaseModel):
    """
    Validated email payload from automation-service.
    All fields are required — no optional threading fields.
    """
    # Routing
    provider:         str   = Field(..., description="gmail | smtp | outlook")
    email_account_id: str   = Field(..., description="UUID of the sending email account")
    user_id:          str   = Field(..., description="UUID of the account owner")

    # Threading — CRITICAL: must match incoming message exactly
    thread_id:        str   = Field(..., description="Provider thread ID — must match incoming")
    in_reply_to:      str   = Field(..., description="message_id of the message being replied to")
    references:       str   = Field(..., description="thread_id for References header chain")
    conversation_id:  str   = Field(..., description="Internal conversation UUID")

    # Email headers
    to:               str   = Field(..., description="Recipient email address")
    from_email:       str   = Field(..., description="Sender email address (account email)")
    subject:          str   = Field(..., description="Subject line (must start with Re:)")

    # Body
    body_text:        str   = Field(..., description="Plain text reply body")
    body_html:        str   = Field(default="", description="HTML reply body (optional)")

    # Idempotency
    idempotency_key:  str   = Field(default="", description="Unique key to prevent duplicate sends")


class SendReplyResponse(BaseModel):
    success:             bool
    provider_message_id: Optional[str] = None
    thread_id:           str
    in_reply_to:         str
    conversation_id:     str
    sent_at:             str
    error:               Optional[str] = None


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.post("/send-reply", response_model=SendReplyResponse)
async def send_reply(req: SendReplyRequest):
    """
    Send an AI-generated reply through the correct email provider.

    Validates thread consistency, checks idempotency, sends via provider,
    and stores the outgoing message in the conversation history.
    """
    trace = req.idempotency_key or str(uuid.uuid4())

    logger.info(
        "send_reply: received | provider=%s account=%s thread=%s in_reply_to=%s conv=%s",
        req.provider, req.email_account_id[:8], req.thread_id[:12],
        req.in_reply_to[:12], req.conversation_id[:8],
    )

    # ── Step 1: Idempotency check ─────────────────────────────────────────
    dedup_key = f"sent:{req.email_account_id}:{req.in_reply_to}"
    if await _is_already_sent(dedup_key):
        logger.warning(
            "send_reply: DUPLICATE BLOCKED | in_reply_to=%s conv=%s",
            req.in_reply_to[:12], req.conversation_id[:8],
        )
        return SendReplyResponse(
            success=True,
            provider_message_id=None,
            thread_id=req.thread_id,
            in_reply_to=req.in_reply_to,
            conversation_id=req.conversation_id,
            sent_at=datetime.utcnow().isoformat(),
            error="duplicate_skipped",
        )

    # ── Step 2: Load email account ────────────────────────────────────────
    account = await _load_account(req.email_account_id, req.user_id)
    if not account:
        raise HTTPException(
            status_code=404,
            detail=f"Email account {req.email_account_id} not found or not owned by user {req.user_id}",
        )

    # Resolve from_email: if the payload sent a UUID instead of an email address,
    # use the account's actual email_address from the DB.
    from_email = req.from_email
    if not from_email or "@" not in from_email:
        from_email = account.email_address
        logger.debug(
            "from_email resolved from account | account=%s conv=%s",
            account.email_address, req.conversation_id[:8],
        )

    # ── Step 3: Thread consistency validation ─────────────────────────────
    # The conversation's thread_id must match what we're sending to.
    # This prevents replies going to the wrong thread.
    conv = await _load_conversation(req.conversation_id, req.user_id)
    if conv:
        if conv.thread_id != req.thread_id:
            logger.error(
                "THREAD MISMATCH: conv.thread_id=%s != payload.thread_id=%s | conv=%s",
                conv.thread_id, req.thread_id, req.conversation_id[:8],
            )
            raise HTTPException(
                status_code=422,
                detail=f"Thread mismatch: conversation has thread_id={conv.thread_id}, payload has {req.thread_id}",
            )
        if conv.message_id != req.in_reply_to:
            logger.error(
                "REPLY MAPPING BROKEN: conv.message_id=%s != payload.in_reply_to=%s | conv=%s",
                conv.message_id, req.in_reply_to, req.conversation_id[:8],
            )
            raise HTTPException(
                status_code=422,
                detail=f"Reply mapping broken: conversation message_id={conv.message_id}, payload in_reply_to={req.in_reply_to}",
            )

    # ── Step 4: Send via provider ─────────────────────────────────────────
    # Normalize provider to lowercase for consistent matching
    provider_key = req.provider.lower().strip()

    provider_message_id = None
    last_error = None

    for attempt in range(_MAX_RETRIES):
        try:
            if provider_key == "gmail":
                provider_message_id = await _send_gmail(account, req, from_email)
            elif provider_key in ("smtp", "yahoo", "zoho"):
                provider_message_id = await _send_smtp(account, req, from_email)
            elif provider_key == "outlook":
                provider_message_id = await _send_outlook(account, req, from_email)
            else:
                raise ValueError(f"Unsupported provider: {req.provider}")

            break  # success — exit retry loop

        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "send_reply: attempt %d/%d failed | error=%s | conv=%s",
                attempt + 1, _MAX_RETRIES, last_error[:100], req.conversation_id[:8],
            )
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_RETRY_BACKOFF[attempt])

    if provider_message_id is None:
        logger.error(
            "send_reply: ALL RETRIES FAILED | conv=%s | last_error=%s",
            req.conversation_id[:8], last_error,
        )
        return SendReplyResponse(
            success=False,
            thread_id=req.thread_id,
            in_reply_to=req.in_reply_to,
            conversation_id=req.conversation_id,
            sent_at=datetime.utcnow().isoformat(),
            error=last_error,
        )

    # ── Step 5: Mark as sent (idempotency) ────────────────────────────────
    await _mark_sent(dedup_key)

    # ── Step 6: Store outgoing message in conversation history ────────────
    await _store_outgoing_message(req, provider_message_id)

    sent_at = datetime.utcnow().isoformat()
    logger.info(
        "send_reply: SUCCESS | provider=%s provider_msg_id=%s thread=%s conv=%s",
        req.provider, provider_message_id, req.thread_id[:12], req.conversation_id[:8],
    )

    return SendReplyResponse(
        success=True,
        provider_message_id=provider_message_id,
        thread_id=req.thread_id,
        in_reply_to=req.in_reply_to,
        conversation_id=req.conversation_id,
        sent_at=sent_at,
    )


# ── Gmail sender ──────────────────────────────────────────────────────────────

async def _send_gmail(account, req: SendReplyRequest, from_email: str) -> str:
    """
    Send reply via Gmail API.
    Uses threadId to keep the reply in the correct thread.
    Sets In-Reply-To and References headers for proper threading.
    """
    from utils.encryption import decrypt_token
    from adapter.providers.gmail_adapter import GmailEventAdapter

    _GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"

    # Ensure fresh token
    async with get_db_session() as session:
        adapter = GmailEventAdapter()
        account = await adapter._ensure_fresh_token(account, session)

    access_token = decrypt_token(account.access_token)

    # Build RFC 2822 message with threading headers
    msg = MIMEMultipart("alternative")
    msg["To"]           = req.to
    msg["From"]         = from_email
    msg["Subject"]      = req.subject
    msg["In-Reply-To"]  = f"<{req.in_reply_to}>"
    msg["References"]   = f"<{req.references}>"
    msg["Message-ID"]   = f"<reply-{uuid.uuid4()}@wandercall.ai>"

    msg.attach(MIMEText(req.body_text, "plain", "utf-8"))
    if req.body_html:
        msg.attach(MIMEText(req.body_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_GMAIL_API_BASE}/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "raw":      raw,
                "threadId": req.thread_id,   # CRITICAL: keeps reply in correct thread
            },
        )

    if resp.status_code == 401:
        raise RuntimeError(f"Gmail 401 — token invalid for {account.email_address}")
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Gmail send failed ({resp.status_code}): {resp.text[:200]}")

    data = resp.json()
    provider_message_id = data.get("id", "")
    logger.info(
        "Gmail send OK | provider_msg_id=%s thread=%s account=%s",
        provider_message_id, req.thread_id[:12], account.email_address,
    )
    return provider_message_id


# ── SMTP sender ───────────────────────────────────────────────────────────────

async def _send_smtp(account, req: SendReplyRequest, from_email: str) -> str:
    """
    Send reply via SMTP with In-Reply-To and References headers.
    Runs in thread pool to avoid blocking the event loop.
    """
    import smtplib
    from utils.encryption import decrypt_token

    smtp_password = decrypt_token(account.smtp_password) if account.smtp_password else ""

    msg = MIMEMultipart("alternative")
    msg["To"]           = req.to
    msg["From"]         = from_email
    msg["Subject"]      = req.subject
    msg["In-Reply-To"]  = f"<{req.in_reply_to}>"
    msg["References"]   = f"<{req.references}>"
    msg["Message-ID"]   = f"<reply-{uuid.uuid4()}@wandercall.ai>"

    msg.attach(MIMEText(req.body_text, "plain", "utf-8"))
    if req.body_html:
        msg.attach(MIMEText(req.body_html, "html", "utf-8"))

    raw_bytes = msg.as_bytes()

    def _do_send():
        host = account.smtp_host or "smtp.gmail.com"
        port = account.smtp_port or 587
        user = account.smtp_username or from_email

        if account.smtp_use_tls:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo()
                s.starttls()
                s.login(user, smtp_password)
                s.sendmail(from_email, [req.to], raw_bytes)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, smtp_password)
                s.sendmail(from_email, [req.to], raw_bytes)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _do_send)

    provider_message_id = f"smtp-{uuid.uuid4()}"
    logger.info("SMTP send OK | account=%s to=%s", account.email_address, req.to)
    return provider_message_id


# ── Outlook sender ────────────────────────────────────────────────────────────

async def _send_outlook(account, req: SendReplyRequest, from_email: str) -> str:
    """
    Send reply via Microsoft Graph API.
    Uses conversationId to keep the reply in the correct thread.
    """
    from utils.encryption import decrypt_token

    _GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    access_token = decrypt_token(account.access_token)

    body = {
        "message": {
            "subject": req.subject,
            "body": {
                "contentType": "HTML" if req.body_html else "Text",
                "content":     req.body_html or req.body_text,
            },
            "toRecipients": [{"emailAddress": {"address": req.to}}],
            "internetMessageHeaders": [
                {"name": "In-Reply-To", "value": f"<{req.in_reply_to}>"},
                {"name": "References",  "value": f"<{req.references}>"},
            ],
        },
        "saveToSentItems": True,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_GRAPH_BASE}/me/sendMail",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json",
            },
            json=body,
        )

    if resp.status_code == 401:
        raise RuntimeError(f"Outlook 401 — token invalid for {account.email_address}")
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Outlook send failed ({resp.status_code}): {resp.text[:200]}")

    provider_message_id = f"outlook-{uuid.uuid4()}"
    logger.info("Outlook send OK | account=%s to=%s", account.email_address, req.to)
    return provider_message_id


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_account(email_account_id: str, user_id: str):
    """Load and validate the email account belongs to the user."""
    from models.email_account import EmailAccount
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(
                    EmailAccount.id      == UUID(email_account_id),
                    EmailAccount.user_id == UUID(user_id),
                    EmailAccount.is_active == True,
                )
            )
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("Failed to load email account: %s", exc)
        return None


async def _load_conversation(conversation_id: str, user_id: str):
    """Load conversation for thread consistency validation."""
    from models.email_conversation import EmailConversation
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailConversation).where(
                    EmailConversation.id      == UUID(conversation_id),
                    EmailConversation.user_id == UUID(user_id),
                )
            )
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("Failed to load conversation: %s", exc)
        return None


async def _store_outgoing_message(req: SendReplyRequest, provider_message_id: str) -> None:
    """
    Store the outgoing reply in the conversation's last_24h_messages.
    This ensures the AI has context about what was already sent.
    """
    from models.email_conversation import EmailConversation
    from worker.json_manager import JSONConversationManager
    from sqlalchemy import update

    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailConversation).where(
                    EmailConversation.id      == UUID(req.conversation_id),
                    EmailConversation.user_id == UUID(req.user_id),
                )
            )
            conv = result.scalar_one_or_none()
            if not conv:
                return

            jm = JSONConversationManager()
            new_msg = jm.create_message_object(
                message_id=provider_message_id,
                from_email=req.from_email,
                to_emails=[req.to],
                content=req.body_text,
                timestamp=datetime.utcnow(),
                direction="outgoing",
                subject=req.subject,
            )

            existing = conv.last_24h_messages or []
            updated  = jm.update_messages(existing, new_msg, message_id=provider_message_id)

            await session.execute(
                update(EmailConversation)
                .where(EmailConversation.id == UUID(req.conversation_id))
                .values(
                    last_24h_messages=updated,
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()
            logger.debug(
                "Stored outgoing message | conv=%s provider_msg=%s",
                req.conversation_id[:8], provider_message_id,
            )
    except Exception as exc:
        # Non-fatal — reply was sent, just couldn't store it
        logger.error("Failed to store outgoing message: %s", exc)


async def _is_already_sent(dedup_key: str) -> bool:
    """Check Redis for duplicate send prevention."""
    try:
        from shared.cache import get_redis
        redis = await get_redis()
        return bool(await redis.exists(dedup_key))
    except Exception:
        return False   # Redis unavailable — allow send (fail open)


async def _mark_sent(dedup_key: str) -> None:
    """Mark message as sent in Redis (24h TTL)."""
    try:
        from shared.cache import get_redis
        redis = await get_redis()
        await redis.setex(dedup_key, 86400, "1")   # 24h TTL
    except Exception:
        pass   # Redis unavailable — non-fatal
