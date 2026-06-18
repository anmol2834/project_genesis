"""
automationservice — Email Context Fetcher

Fetch flow:
  1. es_conversations WHERE id = conversation_id  → verified thread_id + metadata
  2. es_messages WHERE user_id + message_id       → triggering message (fetch depth decision)
  3. es_messages WHERE user_id + thread_id        → full history (10 or 20 msgs, oldest→newest)
"""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime

_SVCS_DIR     = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR      = os.path.dirname(_SVCS_DIR)
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import text

from core.database import get_db_session
from core.config import SHORT_MSG_CHAR_THRESHOLD, FETCH_COUNT_SHORT, FETCH_COUNT_NORMAL

logger = logging.getLogger("automationservice.email_context")


async def fetch_thread_messages(
    conversation_id: str,
    user_id: str,
    latest_message_id: str,
) -> dict:
    """
    Fetch conversation metadata + thread history via proper DB chain.

    Returns:
        {
            "conversation":   dict | None,
            "messages":       list[dict],   # oldest → newest
            "latest_message": dict | None,
            "fetch_count":    int,
            "fetch_reason":   "short_message" | "normal" | "conversation_not_found"
                              | "message_not_found" | "error"
        }
    """
    try:
        async with get_db_session() as session:

            # Query 1: es_conversations — O(1) UUID PK lookup
            conv_row = await session.execute(
                text("""
                    SELECT
                        id              AS conversation_id,
                        thread_id,
                        user_id,
                        email_account_id,
                        provider,
                        subject,
                        participants,
                        message_count,
                        last_message_id,
                        last_message_at,
                        is_read,
                        status,
                        intent_type,
                        priority_score,
                        lead_status,
                        created_at,
                        updated_at
                    FROM es_conversations
                    WHERE id      = :conversation_id
                      AND user_id = :user_id
                    LIMIT 1
                """),
                {"conversation_id": conversation_id, "user_id": user_id},
            )
            conversation = conv_row.mappings().first()

            if not conversation:
                logger.warning(
                    "[email_context] conversation not found | conv=%s user=%s",
                    conversation_id, user_id,
                )
                return {
                    "conversation": None, "messages": [], "latest_message": None,
                    "fetch_count": 0, "fetch_reason": "conversation_not_found",
                }

            conversation_dict = dict(conversation)
            db_thread_id = conversation_dict["thread_id"]

            # Query 2: triggering message — O(1) unique index (user_id, message_id)
            latest_row = await session.execute(
                text("""
                    SELECT
                        message_id, thread_id, from_email, to_emails, cc_emails,
                        subject, content, direction, timestamp,
                        has_attachments, status, message_state
                    FROM es_messages
                    WHERE user_id    = :user_id
                      AND message_id = :message_id
                    LIMIT 1
                """),
                {"user_id": user_id, "message_id": latest_message_id},
            )
            latest = latest_row.mappings().first()

            if not latest:
                logger.warning(
                    "[email_context] triggering message not found | message_id=%s user=%s conv=%s",
                    latest_message_id, user_id, conversation_id,
                )
                return {
                    "conversation": conversation_dict, "messages": [], "latest_message": None,
                    "fetch_count": 0, "fetch_reason": "message_not_found",
                }

            latest_dict = dict(latest)
            body_len    = len(latest_dict.get("content") or "")

            # Dynamic fetch depth
            if body_len < SHORT_MSG_CHAR_THRESHOLD:
                fetch_count, fetch_reason = FETCH_COUNT_SHORT, "short_message"
            else:
                fetch_count, fetch_reason = FETCH_COUNT_NORMAL, "normal"

            # Query 3: full history using DB-verified thread_id
            # Index: ix_es_messages_thread (user_id, thread_id, timestamp)
            history_rows = await session.execute(
                text("""
                    SELECT
                        message_id, thread_id, from_email, to_emails, cc_emails,
                        subject, content, direction, timestamp,
                        has_attachments, status, message_state
                    FROM es_messages
                    WHERE user_id   = :user_id
                      AND thread_id = :thread_id
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"user_id": user_id, "thread_id": db_thread_id, "limit": fetch_count},
            )
            messages_raw = history_rows.mappings().all()

        # Reverse DESC → ASC (oldest first)
        messages = [dict(r) for r in reversed(messages_raw)]

        # Serialize datetime → ISO string
        for m in messages:
            if isinstance(m.get("timestamp"), datetime):
                m["timestamp"] = m["timestamp"].isoformat()
        if isinstance(latest_dict.get("timestamp"), datetime):
            latest_dict["timestamp"] = latest_dict["timestamp"].isoformat()
        for key in ("last_message_at", "created_at", "updated_at"):
            if isinstance(conversation_dict.get(key), datetime):
                conversation_dict[key] = conversation_dict[key].isoformat()

        return {
            "conversation":   conversation_dict,
            "messages":       messages,
            "latest_message": latest_dict,
            "fetch_count":    len(messages),
            "fetch_reason":   fetch_reason,
        }

    except Exception as e:
        logger.error("[email_context] fetch failed | conv=%s user=%s: %s",
                     conversation_id, user_id, e, exc_info=True)
        return {
            "conversation": None, "messages": [], "latest_message": None,
            "fetch_count": 0, "fetch_reason": "error",
        }
