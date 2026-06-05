"""
emailservice — Send Reply API (standalone)
Endpoints:
  POST /email/send-reply  — send a reply immediately (automation or manual)
  POST /email/send-draft  — send a stored draft (user clicks "Send" in UI)
"""
from __future__ import annotations
import asyncio, base64, uuid, logging
from datetime import datetime
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update as sa_update
from uuid import UUID

from shared.database import get_db_session
from shared.cache import get_redis
from token_cache import get_account_snapshot, get_fresh_token
from models.messages import EmailMessage, MessageDirection, MessageStatus, MessageState
from models.conversations import EmailConversation
from models.email_account import EmailAccount
from encryption import decrypt_token

logger = logging.getLogger("emailservice.send_reply")
router = APIRouter(prefix="/email", tags=["send-reply"])


class SendReplyRequest(BaseModel):
    provider:         str = Field(...)
    email_account_id: str = Field(...)
    user_id:          str = Field(...)
    thread_id:        str = Field(...)
    in_reply_to:      str = Field(...)
    references:       str = Field(...)
    conversation_id:  str = Field(...)
    to:               str = Field(...)
    from_email:       str = Field(...)
    subject:          str = Field(...)
    body_text:        str = Field(...)
    body_html:        str = Field(default="")
    idempotency_key:  str = Field(default="")


class SendReplyResponse(BaseModel):
    success:             bool
    provider_message_id: Optional[str] = None
    thread_id:           str
    in_reply_to:         str
    conversation_id:     str
    sent_at:             str
    error:               Optional[str] = None


@router.post("/send-reply", response_model=SendReplyResponse)
async def send_reply(req: SendReplyRequest):
    """
    Send a reply. Called by automation-service after AI generates a reply.
    Checks automation_enabled on the account:
      - True  + within limit → send immediately
      - True  + over limit   → enqueue to deferred outbox
      - False                → store as draft (no send)
    """
    dedup_key = f"es:sent:{req.email_account_id}:{req.in_reply_to}"
    try:
        redis = await get_redis()
        if await redis.exists(dedup_key):
            logger.info("send_reply: duplicate skipped | account=%s msg=%s",
                        req.email_account_id[:8], req.in_reply_to[:12])
            return SendReplyResponse(success=True, thread_id=req.thread_id,
                in_reply_to=req.in_reply_to, conversation_id=req.conversation_id,
                sent_at=datetime.utcnow().isoformat(), error="duplicate_skipped")
    except Exception:
        pass

    snap = await _load_snap(req.email_account_id, req.user_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Account {req.email_account_id} not found")

    from_email = req.from_email if "@" in req.from_email else snap["email_address"]

    # ── Check automation_enabled ──────────────────────────────────────────────
    automation_enabled = True
    try:
        async with get_db_session() as _s:
            _r = await _s.execute(
                select(EmailAccount.automation_enabled)
                .where(EmailAccount.id == UUID(req.email_account_id))
            )
            _row = _r.first()
            if _row is not None:
                automation_enabled = bool(_row[0])
    except Exception:
        pass

    if not automation_enabled:
        # Store as draft on the source message row — do NOT send
        from draft_manager import DraftManager
        # Find the source message_id from idempotency_key or in_reply_to
        source_msg_id = req.idempotency_key or req.in_reply_to
        await DraftManager()._store_draft(
            message_id=source_msg_id,
            user_id=req.user_id,
            email_account_id=req.email_account_id,
            draft_text=req.body_text,
        )
        logger.info("send_reply: automation disabled — stored draft | msg=%s", source_msg_id[:12])
        return SendReplyResponse(
            success=True, thread_id=req.thread_id,
            in_reply_to=req.in_reply_to, conversation_id=req.conversation_id,
            sent_at=datetime.utcnow().isoformat(), error="draft_stored",
        )

    # ── Check daily limit ─────────────────────────────────────────────────────
    if not await _check_limit(req.email_account_id):
        from draft_manager import DraftManager
        from datetime import timedelta
        dm = DraftManager()
        _, reset_time = await dm._check_and_reserve_send_slot(req.email_account_id)
        source_msg_id = req.idempotency_key or req.in_reply_to
        await dm._enqueue_deferred(
            message_id=source_msg_id,
            user_id=req.user_id,
            email_account_id=req.email_account_id,
            thread_id=req.thread_id,
            provider=req.provider,
            in_reply_to=req.in_reply_to,
            references=req.references,
            to_email=req.to,
            from_email=from_email,
            subject=req.subject,
            draft_text=req.body_text,
            scheduled_send_time=reset_time,
        )
        logger.info("send_reply: daily limit reached — deferred | msg=%s", source_msg_id[:12])
        return SendReplyResponse(
            success=True, thread_id=req.thread_id,
            in_reply_to=req.in_reply_to, conversation_id=req.conversation_id,
            sent_at=datetime.utcnow().isoformat(), error="deferred_daily_limit",
        )

    # ── Send immediately ──────────────────────────────────────────────────────
    # Strip any quoted reply chains from the body before sending
    from pipeline import strip_reply_chain as _strip
    clean_body_text = _strip(req.body_text or "").strip()
    if not clean_body_text:
        clean_body_text = req.body_text

    # Pre-refresh token ONCE before retry loop — avoids 15s refresh inside each attempt
    try:
        fresh_token = await get_fresh_token(snap)
    except Exception as e:
        logger.warning("Token pre-refresh failed: %s — will retry inline", e)
        fresh_token = None

    provider_key = req.provider.lower().strip()
    provider_msg_id = None
    last_error = None

    for attempt in range(3):
        try:
            if provider_key == "gmail":
                provider_msg_id = await _send_gmail(snap, req, from_email, clean_body_text, fresh_token)
            elif provider_key in ("smtp", "yahoo", "zoho"):
                provider_msg_id = await _send_smtp(snap, req, from_email, clean_body_text)
            elif provider_key == "outlook":
                provider_msg_id = await _send_outlook(snap, req, from_email, clean_body_text, fresh_token)
            else:
                raise ValueError(f"Unsupported provider: {req.provider}")
            break
        except Exception as e:
            last_error = str(e)
            fresh_token = None   # force re-fetch on retry
            if attempt < 2:
                await asyncio.sleep([1, 2, 4][attempt])

    if not provider_msg_id:
        return SendReplyResponse(success=False, thread_id=req.thread_id,
            in_reply_to=req.in_reply_to, conversation_id=req.conversation_id,
            sent_at=datetime.utcnow().isoformat(), error=last_error)

    try:
        redis = await get_redis()
        await redis.setex(dedup_key, 86400, "1")
    except Exception:
        pass

    await _store_outgoing(req, provider_msg_id, from_email)
    await _inc_sent(req.email_account_id)

    return SendReplyResponse(success=True, provider_message_id=provider_msg_id,
        thread_id=req.thread_id, in_reply_to=req.in_reply_to,
        conversation_id=req.conversation_id, sent_at=datetime.utcnow().isoformat())


async def _load_snap(account_id: str, user_id: str) -> Optional[dict]:
    """
    Load account snapshot using the token cache (L1 → L2 → DB).
    Much faster than raw DB query on hot path — L1 hit is zero-cost.
    """
    try:
        # Try token cache first (L1 in-process → L2 Redis → L3 DB)
        from token_cache import get_account_snapshot
        from models.email_account import EmailAccount
        from sqlalchemy import select
        # We need account_id lookup, not email lookup — go to DB directly
        # but use the cache for subsequent calls
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(
                    EmailAccount.id == UUID(account_id),
                    EmailAccount.user_id == UUID(user_id),
                    EmailAccount.is_active == True,
                )
            )
            acct = result.scalar_one_or_none()
            if not acct:
                return None
            snap = {
                "id": str(acct.id), "user_id": str(acct.user_id),
                "email_address": acct.email_address, "provider": acct.provider.value,
                "access_token": acct.access_token, "refresh_token": acct.refresh_token,
                "token_expiry": acct.token_expiry.isoformat() if acct.token_expiry else None,
                "smtp_host": acct.smtp_host, "smtp_port": acct.smtp_port,
                "smtp_username": acct.smtp_username, "smtp_password": acct.smtp_password,
                "smtp_use_tls": acct.smtp_use_tls,
                "daily_send_limit": acct.daily_send_limit, "daily_sent_count": acct.daily_sent_count,
            }
            return snap
    except Exception as e:
        logger.error("Failed to load account: %s", e)
        return None


async def _check_limit(account_id: str) -> bool:
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount.daily_sent_count, EmailAccount.daily_send_limit)
                .where(EmailAccount.id == UUID(account_id))
            )
            row = result.first()
            return row[0] < row[1] if row else True
    except Exception:
        return True


async def _inc_sent(account_id: str) -> None:
    try:
        async with get_db_session() as session:
            await session.execute(
                sa_update(EmailAccount).where(EmailAccount.id == UUID(account_id))
                .values(daily_sent_count=EmailAccount.daily_sent_count + 1)
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to increment sent count: %s", e)


async def _store_outgoing(req: SendReplyRequest, provider_msg_id: str, from_email: str) -> None:
    from pipeline import strip_reply_chain
    try:
        async with get_db_session() as session:
            msg = EmailMessage(
                message_id=provider_msg_id, thread_id=req.thread_id,
                user_id=UUID(req.user_id), email_account_id=UUID(req.email_account_id),
                provider=req.provider, from_email=from_email, to_emails=[req.to],
                subject=req.subject, content=strip_reply_chain(req.body_text or ""),
                timestamp=datetime.utcnow(),
                direction=MessageDirection.OUTGOING, status=MessageStatus.SENT, is_read=True,
            )
            session.add(msg)
            conv = (await session.execute(
                select(EmailConversation).where(
                    EmailConversation.id == UUID(req.conversation_id),
                    EmailConversation.user_id == UUID(req.user_id),
                )
            )).scalar_one_or_none()
            if conv:
                conv.last_message_id = provider_msg_id
                conv.last_message_at = datetime.utcnow()
                conv.message_count   = (conv.message_count or 0) + 1
            await session.commit()
    except Exception as e:
        logger.error("Failed to store outgoing message: %s", e)


async def _send_gmail(snap: dict, req: SendReplyRequest, from_email: str, body_text: str = "", token: str = None) -> str:
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    # Use pre-fetched token if available, otherwise refresh
    if not token:
        token = await get_fresh_token(snap)
    body_text = body_text or req.body_text
    msg = MIMEMultipart("alternative")
    msg["To"] = req.to; msg["From"] = from_email; msg["Subject"] = req.subject
    msg["In-Reply-To"] = f"<{req.in_reply_to}>"; msg["References"] = f"<{req.references}>"
    msg["Message-ID"] = f"<reply-{uuid.uuid4()}@emailservice>"
    # Always attach plain text first (fallback for clients that don't render HTML)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    # Attach HTML version — email clients prefer the last part in multipart/alternative
    html_body = req.body_html or body_text
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"raw": raw, "threadId": req.thread_id},
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Gmail send failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json().get("id", "")


async def _send_smtp(snap: dict, req: SendReplyRequest, from_email: str, body_text: str = "") -> str:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    body_text = body_text or req.body_text
    pwd = decrypt_token(snap["smtp_password"]) if snap.get("smtp_password") else ""
    msg = MIMEMultipart("alternative")
    msg["To"] = req.to; msg["From"] = from_email; msg["Subject"] = req.subject
    msg["In-Reply-To"] = f"<{req.in_reply_to}>"; msg["References"] = f"<{req.references}>"
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if req.body_html:
        msg.attach(MIMEText(req.body_html, "html", "utf-8"))
    raw = msg.as_bytes()
    def _do():
        host = snap.get("smtp_host") or "smtp.gmail.com"
        port = snap.get("smtp_port") or 587
        user = snap.get("smtp_username") or from_email
        if snap.get("smtp_use_tls", True):
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo(); s.starttls(); s.login(user, pwd); s.sendmail(from_email, [req.to], raw)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, pwd); s.sendmail(from_email, [req.to], raw)
    await asyncio.get_event_loop().run_in_executor(None, _do)
    return f"smtp-{uuid.uuid4()}"


async def _send_outlook(snap: dict, req: SendReplyRequest, from_email: str, body_text: str = "", token: str = None) -> str:
    if not token:
        token = await get_fresh_token(snap)
    body_text = body_text or req.body_text
    html_body = req.body_html or body_text
    body = {
        "message": {
            "subject": req.subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": req.to}}],
            "internetMessageHeaders": [
                {"name": "In-Reply-To", "value": f"<{req.in_reply_to}>"},
                {"name": "References",  "value": f"<{req.references}>"},
            ],
        },
        "saveToSentItems": True,
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Outlook send failed ({resp.status_code}): {resp.text[:200]}")
    return f"outlook-{uuid.uuid4()}"


# ── Send Draft endpoint ───────────────────────────────────────────────────────

class SendDraftRequest(BaseModel):
    """
    User clicks "Send" on a pending draft in the inbox UI.
    The draft_message is already stored on the incoming message row.
    We just need the message_id to look it up + account context to send.
    """
    message_id:       str = Field(..., description="Incoming message_id whose draft to send")
    user_id:          str = Field(...)
    email_account_id: str = Field(...)


class SendDraftResponse(BaseModel):
    success:             bool
    provider_message_id: Optional[str] = None
    sent_at:             str
    error:               Optional[str] = None


@router.post("/send-draft", response_model=SendDraftResponse)
async def send_draft(req: SendDraftRequest):
    """
    Send the AI-generated draft stored on an incoming message row.
    Idempotent: repeated calls return success without re-sending.
    Lifecycle: DRAFTED → SENT (updates message_state on the incoming row).
    """
    # ── Load the incoming message with its draft ──────────────────────────────
    async with get_db_session() as session:
        result = await session.execute(
            select(EmailMessage).where(
                EmailMessage.message_id == req.message_id,
                EmailMessage.user_id == UUID(req.user_id),
            )
        )
        msg = result.scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if not msg.draft_message:
        raise HTTPException(status_code=400, detail="No draft found for this message")

    # Idempotency: already sent
    if msg.message_state == MessageState.SENT:
        return SendDraftResponse(
            success=True, sent_at=datetime.utcnow().isoformat(), error="already_sent"
        )

    # ── Dedup via Redis ───────────────────────────────────────────────────────
    dedup_key = f"es:draft_sent:{req.email_account_id}:{req.message_id}"
    try:
        redis = await get_redis()
        if await redis.exists(dedup_key):
            return SendDraftResponse(
                success=True, sent_at=datetime.utcnow().isoformat(), error="duplicate_skipped"
            )
    except Exception:
        pass

    # ── Load account ──────────────────────────────────────────────────────────
    snap = await _load_snap(req.email_account_id, req.user_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Email account not found")

    from_email = snap["email_address"]

    # ── Check daily limit — defer if over ────────────────────────────────────
    if not await _check_limit(req.email_account_id):
        # Enqueue to deferred outbox instead of failing
        from draft_manager import DraftManager
        # Reconstruct reply headers from message fields (no metadata needed)
        to_email_deferred = (msg.from_email if msg.direction == MessageDirection.INCOMING
                             else (msg.to_emails[0] if msg.to_emails else ""))
        dm = DraftManager()
        await dm._enqueue_deferred(
            message_id=req.message_id,
            user_id=req.user_id,
            email_account_id=req.email_account_id,
            thread_id=msg.thread_id or req.message_id,
            provider=msg.provider,
            in_reply_to=msg.message_id,
            references=msg.thread_id or msg.message_id,
            to_email=to_email_deferred,
            from_email=from_email,
            subject=msg.subject or "",
            draft_text=msg.draft_message,
            scheduled_send_time=await dm._check_and_reserve_send_slot(req.email_account_id)[1],
        )
        # Update state to QUEUED
        async with get_db_session() as session:
            await session.execute(
                sa_update(EmailMessage)
                .where(EmailMessage.message_id == req.message_id,
                       EmailMessage.user_id == UUID(req.user_id))
                .values(message_state=MessageState.QUEUED)
            )
            await session.commit()
        return SendDraftResponse(
            success=True, sent_at=datetime.utcnow().isoformat(), error="deferred_daily_limit"
        )

    # ── Build send request from message fields (no metadata needed) ───────────
    to_email = (msg.from_email if msg.direction == MessageDirection.INCOMING
                else (msg.to_emails[0] if isinstance(msg.to_emails, list) and msg.to_emails else ""))

    send_req = SendReplyRequest(
        provider=msg.provider,
        email_account_id=req.email_account_id,
        user_id=req.user_id,
        thread_id=msg.thread_id or req.message_id,
        in_reply_to=msg.message_id,
        references=msg.thread_id or msg.message_id,
        conversation_id="",
        to=to_email,
        from_email=from_email,
        subject=f"Re: {msg.subject}" if msg.subject and not msg.subject.startswith("Re:") else (msg.subject or ""),
        body_text=msg.draft_message,
    )

    # ── Send ──────────────────────────────────────────────────────────────────
    from pipeline import strip_reply_chain as _strip
    clean_draft = _strip(msg.draft_message or "").strip() or msg.draft_message

    # Pre-refresh token once
    try:
        fresh_token = await get_fresh_token(snap)
    except Exception:
        fresh_token = None

    provider_key = msg.provider.lower()
    provider_msg_id = None
    last_error = None

    for attempt in range(3):
        try:
            if provider_key == "gmail":
                provider_msg_id = await _send_gmail(snap, send_req, from_email, clean_draft, fresh_token)
            elif provider_key == "outlook":
                provider_msg_id = await _send_outlook(snap, send_req, from_email, clean_draft, fresh_token)
            else:
                provider_msg_id = await _send_smtp(snap, send_req, from_email, clean_draft)
            break
        except Exception as e:
            last_error = str(e)
            fresh_token = None
            if attempt < 2:
                await asyncio.sleep([1, 2, 4][attempt])

    if not provider_msg_id:
        # Mark as FAILED
        async with get_db_session() as session:
            await session.execute(
                sa_update(EmailMessage)
                .where(EmailMessage.message_id == req.message_id,
                       EmailMessage.user_id == UUID(req.user_id))
                .values(message_state=MessageState.FAILED)
            )
            await session.commit()
        return SendDraftResponse(
            success=False, sent_at=datetime.utcnow().isoformat(), error=last_error
        )

    # ── Mark sent + set dedup key ─────────────────────────────────────────────
    try:
        redis = await get_redis()
        await redis.setex(dedup_key, 86400, "1")
    except Exception:
        pass

    async with get_db_session() as session:
        await session.execute(
            sa_update(EmailMessage)
            .where(EmailMessage.message_id == req.message_id,
                   EmailMessage.user_id == UUID(req.user_id))
            .values(message_state=MessageState.SENT, draft_message=None)
        )
        await session.commit()

    await _inc_sent(req.email_account_id)

    logger.info("Draft sent | msg=%s provider_msg=%s", req.message_id[:12], provider_msg_id[:12])
    return SendDraftResponse(
        success=True, provider_message_id=provider_msg_id,
        sent_at=datetime.utcnow().isoformat(),
    )
