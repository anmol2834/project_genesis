"""
emailservice — Inbox API
Reads from the NEW normalized es_messages + es_conversations tables.
AI context: fetches last N messages dynamically (no JSONB arrays).
"""
from __future__ import annotations
import sys, os, logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, desc, func

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from shared.database import get_db_session
from dependencies import get_current_user
from models.conversations import EmailConversation
from models.messages import EmailMessage

logger = logging.getLogger("emailservice.inbox")
router = APIRouter(prefix="/email/inbox", tags=["inbox"])


def _fmt_conv(conv: EmailConversation, messages: list) -> dict:
    latest = messages[-1] if messages else None
    return {
        "id":              str(conv.id),
        "thread_id":       conv.thread_id,
        "subject":         conv.subject or "(No Subject)",
        "provider":        conv.provider,
        "is_read":         conv.is_read,
        "status":          conv.status,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "message_count":   conv.message_count,
        "participants":    conv.participants or [],
        "snippet":         (latest.content or "")[:80] if latest else "",
        "direction":       latest.direction if latest else "incoming",
        "priority_score":  conv.priority_score,
        "intent_type":     conv.intent_type,
        "lead_status":     conv.lead_status,
        "tags":            conv.tags or [],
        "follow_up_required": conv.follow_up_required,
        # messages array for UI (last 20 only — not full history)
        "messages": [_fmt_msg(m) for m in messages],
    }


def _fmt_msg(m: EmailMessage) -> dict:
    return {
        "message_id":     m.message_id,
        "from_email":     m.from_email,
        "to_emails":      m.to_emails or [],
        "subject":        m.subject,
        "content":        m.content,
        "timestamp":      m.timestamp.isoformat() if m.timestamp else None,
        "direction":      m.direction,
        "is_read":        m.is_read,
        "has_attachments": m.has_attachments,
    }


@router.get("/threads")
async def list_threads(
    limit:  int = Query(default=10, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_id = UUID(str(current_user["user_id"]))
    try:
        async with get_db_session() as db:
            total = (await db.execute(
                select(func.count(EmailConversation.id)).where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.status == "active",
                ))
            )).scalar() or 0

            convs = (await db.execute(
                select(EmailConversation)
                .where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.status == "active",
                ))
                .order_by(desc(EmailConversation.last_message_at))
                .limit(limit).offset(offset)
            )).scalars().all()

            # Fetch last 20 messages per thread (dynamic — no JSONB)
            threads = []
            for conv in convs:
                msgs = (await db.execute(
                    select(EmailMessage)
                    .where(and_(
                        EmailMessage.user_id == user_id,
                        EmailMessage.thread_id == conv.thread_id,
                    ))
                    .order_by(desc(EmailMessage.timestamp))
                    .limit(20)
                )).scalars().all()
                threads.append(_fmt_conv(conv, list(reversed(msgs))))

        return {"threads": threads, "total": total}
    except Exception as exc:
        logger.error("list_threads failed for user %s: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve inbox")


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user),
):
    user_id = UUID(str(current_user["user_id"]))
    try:
        async with get_db_session() as db:
            conv = (await db.execute(
                select(EmailConversation).where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.thread_id == thread_id,
                ))
            )).scalar_one_or_none()

            if not conv:
                raise HTTPException(status_code=404, detail="Thread not found")

            msgs = (await db.execute(
                select(EmailMessage)
                .where(and_(
                    EmailMessage.user_id == user_id,
                    EmailMessage.thread_id == thread_id,
                ))
                .order_by(EmailMessage.timestamp)
                .limit(limit)
            )).scalars().all()

        return _fmt_conv(conv, list(msgs))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_thread failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve thread")


@router.post("/threads/{thread_id}/read")
async def mark_read(thread_id: str, current_user: dict = Depends(get_current_user)):
    user_id = UUID(str(current_user["user_id"]))
    try:
        async with get_db_session() as db:
            conv = (await db.execute(
                select(EmailConversation).where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.thread_id == thread_id,
                ))
            )).scalar_one_or_none()
            if conv:
                conv.is_read = True
                await db.commit()
        return {"status": "ok"}
    except Exception as exc:
        logger.error("mark_read failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to mark as read")
