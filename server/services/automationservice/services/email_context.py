"""
automationservice — Email Context Fetcher
==========================================
Dynamic Fetch Rule (implementation_plan.md):
  latest message body < 20 chars  →  fetch last 20 messages (short/ambiguous)
  otherwise                       →  fetch last 10 messages

sys.path note:
  This file lives at: server/services/automationservice/services/email_context.py
  server/ is 4 levels up from this file's directory.
"""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime

_SVCS_DIR     = os.path.dirname(os.path.abspath(__file__))          # .../services
_SVC_DIR      = os.path.dirname(_SVCS_DIR)                          # .../automationservice
_SERVICES_DIR = os.path.dirname(_SVC_DIR)                           # .../services (server/services)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)                      # .../server
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

# Also ensure automationservice root is on path so core.* imports resolve
if _SVC_DIR not in sys.path:
    sys.path.insert(0, _SVC_DIR)

from sqlalchemy import text

from core.database import get_db_session
from core.config import (
    SHORT_MSG_CHAR_THRESHOLD,
    FETCH_COUNT_SHORT,
    FETCH_COUNT_NORMAL,
)

logger = logging.getLogger("automationservice.email_context")


async def fetch_thread_messages(
    thread_id: str,
    user_id: str,
    latest_message_id: str,
) -> dict:
    """
    Fetch thread history from es_messages for the triggering message.

    Returns:
        {
            "messages":       list[dict],  # ordered oldest → newest
            "latest_message": dict | None, # the triggering incoming message
            "fetch_count":    int,
            "fetch_reason":   "short_message" | "normal" | "not_found" | "error"
        }
    """
    print(f"\n{'='*60}")
    print(f"[AUTOMATIONSERVICE] 📨 FETCH THREAD MESSAGES")
    print(f"  thread_id         : {thread_id}")
    print(f"  user_id           : {user_id}")
    print(f"  latest_message_id : {latest_message_id}")
    print(f"{'='*60}")

    try:
        async with get_db_session() as session:

            # ── Step 1: Load triggering message to decide fetch depth ──────────
            latest_row = await session.execute(
                text("""
                    SELECT message_id, thread_id, from_email, to_emails,
                           subject, content, direction, timestamp
                    FROM es_messages
                    WHERE user_id   = :user_id
                      AND message_id = :message_id
                    LIMIT 1
                """),
                {"user_id": user_id, "message_id": latest_message_id},
            )
            latest = latest_row.mappings().first()

            if not latest:
                logger.warning(
                    "[email_context] triggering message not found | message_id=%s user_id=%s",
                    latest_message_id, user_id,
                )
                print(f"[AUTOMATIONSERVICE] ⚠️  Triggering message NOT FOUND in DB")
                print(f"  message_id : {latest_message_id}")
                print(f"  user_id    : {user_id}")
                return {
                    "messages":       [],
                    "latest_message": None,
                    "fetch_count":    0,
                    "fetch_reason":   "not_found",
                }

            latest_dict = dict(latest)
            latest_body = latest_dict.get("content") or ""

            # ── Step 2: Dynamic fetch count decision ──────────────────────────
            if len(latest_body) < SHORT_MSG_CHAR_THRESHOLD:
                fetch_count  = FETCH_COUNT_SHORT
                fetch_reason = "short_message"
            else:
                fetch_count  = FETCH_COUNT_NORMAL
                fetch_reason = "normal"

            print(f"\n[AUTOMATIONSERVICE] 🔍 DYNAMIC FETCH DECISION")
            print(f"  latest body length : {len(latest_body)} chars")
            print(f"  threshold          : {SHORT_MSG_CHAR_THRESHOLD} chars")
            print(f"  fetch_count        : {fetch_count} messages")
            print(f"  fetch_reason       : {fetch_reason}")

            # ── Step 3: Fetch last N messages in thread (DESC), reverse to ASC ─
            rows = await session.execute(
                text("""
                    SELECT message_id, thread_id, from_email, to_emails,
                           subject, content, direction, timestamp
                    FROM es_messages
                    WHERE user_id   = :user_id
                      AND thread_id = :thread_id
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"user_id": user_id, "thread_id": thread_id, "limit": fetch_count},
            )
            messages_raw = rows.mappings().all()

        # Reverse → oldest first
        messages = [dict(r) for r in reversed(messages_raw)]

        # Serialize datetime → ISO string (safe for JSON)
        for m in messages:
            if isinstance(m.get("timestamp"), datetime):
                m["timestamp"] = m["timestamp"].isoformat()
        if isinstance(latest_dict.get("timestamp"), datetime):
            latest_dict["timestamp"] = latest_dict["timestamp"].isoformat()

        # ── Print full context summary ────────────────────────────────────────
        print(f"\n[AUTOMATIONSERVICE] ✅ THREAD CONTEXT FETCHED")
        print(f"  messages fetched : {len(messages)}")
        print(f"  subject          : {latest_dict.get('subject', '(no subject)')}")
        print(f"  latest direction : {latest_dict.get('direction', '?')}")
        print(f"  latest from      : {latest_dict.get('from_email', '?')}")
        snippet = latest_body[:120]
        print(f"  latest snippet   : {snippet}{'...' if len(latest_body) > 120 else ''}")
        print(f"  {'─'*56}")
        for i, msg in enumerate(messages):
            icon = "📥" if msg.get("direction") == "incoming" else "📤"
            ts   = (msg.get("timestamp") or "")[:19]
            body_len = len(msg.get("content") or "")
            print(
                f"  [{i+1:02d}] {icon} [{msg.get('direction','?'):8s}] "
                f"from={msg.get('from_email','?'):<32s} "
                f"ts={ts}  len={body_len}"
            )

        return {
            "messages":       messages,
            "latest_message": latest_dict,
            "fetch_count":    len(messages),
            "fetch_reason":   fetch_reason,
        }

    except Exception as e:
        logger.error("[email_context] fetch failed: %s", e, exc_info=True)
        print(f"[AUTOMATIONSERVICE] ❌ FETCH ERROR: {e}")
        return {
            "messages":       [],
            "latest_message": None,
            "fetch_count":    0,
            "fetch_reason":   "error",
        }
