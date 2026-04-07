"""
emailservice — Send Reply API (standalone)
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
from models.messages import EmailMessage, MessageDirection, MessageStatus
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
    dedup_key = f"es:sent:{req.email_account_id}:{req.in_reply_to}"
    try:
        redis = await get_redis()
        if await redis.exists(dedup_key):
            return SendReplyResponse(success=True, thread_id=req.thread_id,
                in_reply_to=req.in_reply_to, conversation_id=req.conversation_id,
                sent_at=datetime.utcnow().isoformat(), error="duplicate_skipped")
    except Exception:
        pass

    snap = await _load_snap(req.email_account_id, req.user_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Account {req.email_account_id} not found")

    from_email = req.from_email if "@" in req.from_email else snap["email_address"]

    if not await _check_limit(req.email_account_id):
        return SendReplyResponse(success=True, thread_id=req.thread_id,
            in_reply_to=req.in_reply_to, conversation_id=req.conversation_id,
            sent_at=datetime.utcnow().isoformat(), error="deferred_daily_limit")

    provider_key = req.provider.lower().strip()
    provider_msg_id = None
    last_error = None

    for attempt in range(3):
        try:
            if provider_key == "gmail":
                provider_msg_id = await _send_gmail(snap, req, from_email)
            elif provider_key in ("smtp", "yahoo", "zoho"):
                provider_msg_id = await _send_smtp(snap, req, from_email)
            elif provider_key == "outlook":
                provider_msg_id = await _send_outlook(snap, req, from_email)
            else:
                raise ValueError(f"Unsupported provider: {req.provider}")
            break
        except Exception as e:
            last_error = str(e)
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
    try:
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
            return {
                "id": str(acct.id), "user_id": str(acct.user_id),
                "email_address": acct.email_address, "provider": acct.provider.value,
                "access_token": acct.access_token, "refresh_token": acct.refresh_token,
                "token_expiry": acct.token_expiry.isoformat() if acct.token_expiry else None,
                "smtp_host": acct.smtp_host, "smtp_port": acct.smtp_port,
                "smtp_username": acct.smtp_username, "smtp_password": acct.smtp_password,
                "smtp_use_tls": acct.smtp_use_tls,
                "daily_send_limit": acct.daily_send_limit, "daily_sent_count": acct.daily_sent_count,
            }
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
                subject=req.subject, content=strip_reply_chain(req.body_text),
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


async def _send_gmail(snap: dict, req: SendReplyRequest, from_email: str) -> str:
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    token = await get_fresh_token(snap)
    msg = MIMEMultipart("alternative")
    msg["To"] = req.to; msg["From"] = from_email; msg["Subject"] = req.subject
    msg["In-Reply-To"] = f"<{req.in_reply_to}>"; msg["References"] = f"<{req.references}>"
    msg["Message-ID"] = f"<reply-{uuid.uuid4()}@emailservice>"
    msg.attach(MIMEText(req.body_text, "plain", "utf-8"))
    if req.body_html:
        msg.attach(MIMEText(req.body_html, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"raw": raw, "threadId": req.thread_id},
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Gmail send failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json().get("id", "")


async def _send_smtp(snap: dict, req: SendReplyRequest, from_email: str) -> str:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    pwd = decrypt_token(snap["smtp_password"]) if snap.get("smtp_password") else ""
    msg = MIMEMultipart("alternative")
    msg["To"] = req.to; msg["From"] = from_email; msg["Subject"] = req.subject
    msg["In-Reply-To"] = f"<{req.in_reply_to}>"; msg["References"] = f"<{req.references}>"
    msg.attach(MIMEText(req.body_text, "plain", "utf-8"))
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


async def _send_outlook(snap: dict, req: SendReplyRequest, from_email: str) -> str:
    token = await get_fresh_token(snap)
    body = {
        "message": {
            "subject": req.subject,
            "body": {"contentType": "HTML" if req.body_html else "Text", "content": req.body_html or req.body_text},
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
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Outlook send failed ({resp.status_code}): {resp.text[:200]}")
    return f"outlook-{uuid.uuid4()}"
