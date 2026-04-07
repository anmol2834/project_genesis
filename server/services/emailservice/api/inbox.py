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

    # Determine the "other party" email for display
    # For incoming threads: the sender of the first/latest incoming message
    # For outgoing threads: the recipient
    from_email = ""
    if messages:
        incoming = [m for m in messages if str(m.direction).lower() in ("incoming", "messagedirection.incoming")]
        outgoing = [m for m in messages if str(m.direction).lower() in ("outgoing", "messagedirection.outgoing")]
        if incoming:
            from_email = incoming[0].from_email or ""
        elif outgoing:
            to = outgoing[0].to_emails
            if isinstance(to, list) and to:
                from_email = to[0]
            elif isinstance(to, str) and to:
                import json as _json
                try:
                    parsed = _json.loads(to)
                    from_email = parsed[0] if parsed else ""
                except Exception:
                    from_email = to

    # Unread count
    unread = sum(
        1 for m in messages
        if not m.is_read and str(m.direction).lower() in ("incoming", "messagedirection.incoming")
    )

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
        # Fields the client adapter needs at thread level
        "from_email":      from_email,
        "to_emails":       conv.participants or [],
        "unread":          unread,
        "snippet":         (latest.content or "")[:80] if latest else "",
        "direction":       str(latest.direction).split(".")[-1].lower() if latest else "incoming",
        "priority_score":  conv.priority_score,
        "intent_type":     conv.intent_type,
        "lead_status":     conv.lead_status,
        "tags":            conv.tags or [],
        "follow_up_required": conv.follow_up_required,
        # messages array for UI (last 20 only — not full history)
        "messages": [_fmt_msg(m) for m in messages],
    }


def _fmt_msg(m: EmailMessage) -> dict:
    # Normalize direction to plain string (handles both enum and string values)
    direction = str(m.direction).split(".")[-1].lower()
    return {
        "message_id":      m.message_id,
        "from_email":      m.from_email,
        "to_emails":       m.to_emails or [],
        "subject":         m.subject,
        "content":         m.content,
        "timestamp":       m.timestamp.isoformat() if m.timestamp else None,
        "direction":       direction,
        "is_read":         m.is_read,
        "has_attachments": m.has_attachments,
        # Aliases for client compatibility
        "from":            m.from_email,
        "to":              m.to_emails or [],
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
                    EmailConversation.status.in_(["active", None]),
                ))
            )).scalar() or 0

            convs = (await db.execute(
                select(EmailConversation)
                .where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.status.in_(["active", None]),
                ))
                .order_by(desc(EmailConversation.last_message_at))
                .limit(limit).offset(offset)
            )).scalars().all()

            # ── Fallback: rebuild conversations from es_messages if table is empty ──
            # This handles the case where es_conversations rows were never created
            # (e.g. first run before the upsert logic was in place).
            if not convs:
                logger.warning(
                    "es_conversations empty for user %s — rebuilding from es_messages", user_id
                )
                convs = await _rebuild_conversations_from_messages(db, user_id)
                total = len(convs)
                # Persist rebuilt conversations so future queries are fast
                for conv in convs:
                    try:
                        from sqlalchemy.dialects.postgresql import insert as pg_insert
                        await db.execute(
                            pg_insert(EmailConversation.__table__)
                            .values(
                                id=conv.id,
                                thread_id=conv.thread_id,
                                user_id=conv.user_id,
                                email_account_id=conv.email_account_id,
                                provider=conv.provider,
                                subject=conv.subject,
                                participants=conv.participants,
                                message_count=conv.message_count,
                                last_message_id=conv.last_message_id,
                                last_message_at=conv.last_message_at,
                                is_read=conv.is_read,
                                status="active",
                            )
                            .on_conflict_do_nothing(
                                index_elements=["user_id", "thread_id"]
                            )
                        )
                    except Exception as e:
                        logger.warning("Failed to persist rebuilt conv %s: %s", conv.thread_id, e)
                try:
                    await db.commit()
                except Exception as e:
                    logger.warning("Failed to commit rebuilt conversations: %s", e)

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


# ── Conversation rebuild helper ───────────────────────────────────────────────

async def _rebuild_conversations_from_messages(db, user_id: UUID) -> list:
    """
    Build synthetic EmailConversation objects from es_messages when
    es_conversations is empty. Groups messages by thread_id and creates
    one conversation per thread. Used as a one-time recovery path.
    """
    import uuid as _uuid
    from datetime import datetime

    # Fetch all messages for this user, ordered by time
    all_msgs = (await db.execute(
        select(EmailMessage)
        .where(EmailMessage.user_id == user_id)
        .order_by(EmailMessage.timestamp)
    )).scalars().all()

    if not all_msgs:
        return []

    # Group by thread_id
    threads: dict[str, list] = {}
    for m in all_msgs:
        tid = m.thread_id or m.message_id
        threads.setdefault(tid, []).append(m)

    convs = []
    for thread_id, msgs in threads.items():
        latest = msgs[-1]
        participants = list({
            e.lower()
            for m in msgs
            for e in ([m.from_email] + (m.to_emails if isinstance(m.to_emails, list) else []))
            if e
        })
        unread = sum(
            1 for m in msgs
            if not m.is_read and str(m.direction).lower() in ("incoming", "messagedirection.incoming")
        )

        conv = EmailConversation(
            id               = _uuid.uuid4(),
            thread_id        = thread_id,
            user_id          = user_id,
            email_account_id = latest.email_account_id,
            provider         = latest.provider,
            subject          = latest.subject or "(No Subject)",
            participants     = participants,
            message_count    = len(msgs),
            last_message_id  = latest.message_id,
            last_message_at  = latest.timestamp or datetime.utcnow(),
            is_read          = unread == 0,
            status           = "active",
        )
        convs.append(conv)

    # Sort by last_message_at desc (newest first)
    convs.sort(key=lambda c: c.last_message_at or datetime.min, reverse=True)
    return convs
