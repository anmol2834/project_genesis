"""
Inbox API
Email conversations for the inbox page.
No SSE/WebSocket — client polls every 30s to keep Redis connections low.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, desc

from shared.database.postgres import get_db_session
from shared.logger import get_logger
from dependencies import get_current_user
from models.email_conversation import EmailConversation

logger = get_logger(__name__)
router = APIRouter(prefix="/email/inbox", tags=["inbox"])


def _format_thread(conv: EmailConversation) -> dict:
    messages = conv.last_24h_messages or []
    latest   = messages[-1] if messages else None
    return {
        "id":              str(conv.id),
        "thread_id":       conv.thread_id,
        "subject":         conv.subject or "(No Subject)",
        "from_email":      conv.from_email,
        "to_emails":       conv.to_emails or [],
        "provider":        conv.provider,
        "is_read":         conv.is_read,
        "status":          conv.conversation_status,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "updated_at":      conv.updated_at.isoformat() if conv.updated_at else None,
        "messages":        messages,
        "snippet":         latest["content"][:80] if latest else "",
        "direction":       latest["direction"] if latest else "incoming",
        "unread":          0 if conv.is_read else 1,
    }


@router.get("/threads")
async def list_threads(
    limit:  int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_id = UUID(str(current_user["user_id"]))
    try:
        async with get_db_session() as db:
            result = await db.execute(
                select(EmailConversation)
                .where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.conversation_status == "active",
                ))
                .order_by(desc(EmailConversation.last_message_at))
                .limit(limit)
                .offset(offset)
            )
            conversations = result.scalars().all()
        return {"threads": [_format_thread(c) for c in conversations], "total": len(conversations)}
    except Exception as exc:
        logger.error(f"Failed to list threads for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve inbox threads")


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = UUID(str(current_user["user_id"]))
    try:
        async with get_db_session() as db:
            result = await db.execute(
                select(EmailConversation).where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.thread_id == thread_id,
                ))
            )
            conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Thread not found")
        return _format_thread(conv)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get thread {thread_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve thread")


@router.post("/threads/{thread_id}/read")
async def mark_thread_read(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = UUID(str(current_user["user_id"]))
    try:
        async with get_db_session() as db:
            result = await db.execute(
                select(EmailConversation).where(and_(
                    EmailConversation.user_id == user_id,
                    EmailConversation.thread_id == thread_id,
                ))
            )
            conv = result.scalar_one_or_none()
            if conv:
                conv.is_read = True
                await db.commit()
        return {"status": "ok"}
    except Exception as exc:
        logger.error(f"Failed to mark thread {thread_id} as read: {exc}")
        raise HTTPException(status_code=500, detail="Failed to mark as read")
