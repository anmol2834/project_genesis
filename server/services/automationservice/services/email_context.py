"""
automationservice — Email Context Fetcher
==========================================
Fetch Strategy (correct 2-query architecture):

  Step 1 → Query es_conversations WHERE id = conversation_id
           Gets the canonical thread_id, subject, participants,
           message_count, provider, email_account_id — all stored
           by emailservice pipeline.store_message_with_retry()

  Step 2 → Query es_messages WHERE user_id = ? AND thread_id = ?
           Uses the verified thread_id from es_conversations, NOT the
           raw thread_id string from the event payload.

  Dynamic Fetch Depth (implementation_plan.md spec):
    latest message body < 20 chars  →  fetch last 20 messages
    otherwise                       →  fetch last 10 messages

Why conversation_id first, not thread_id directly?
  - thread_id is a provider-specific opaque string (Gmail threadId /
    Outlook conversationId). It is not sanitised, not UUID-validated,
    and not guaranteed to be unique across providers for the same user.
  - es_conversations is the authoritative, user-scoped, provider-scoped
    record. Its (user_id, thread_id) unique constraint is the source of
    truth. Fetching through it guarantees we read from the correct
    conversation and not a phantom or cross-user collision.
  - conversation_id (UUID) is immutable and indexed (PK). Lookup is O(1).

sys.path note:
  This file: server/services/automationservice/services/email_context.py
  server/ is 4 levels up from this file's directory (services/ subdir).
"""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime

# ── sys.path resolution ────────────────────────────────────────────────────────
_SVCS_DIR     = os.path.dirname(os.path.abspath(__file__))   # .../automationservice/services
_SVC_DIR      = os.path.dirname(_SVCS_DIR)                   # .../automationservice
_SERVICES_DIR = os.path.dirname(_SVC_DIR)                    # .../server/services
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)               # .../server

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import text

from core.database import get_db_session
from core.config import (
    SHORT_MSG_CHAR_THRESHOLD,
    FETCH_COUNT_SHORT,
    FETCH_COUNT_NORMAL,
)

logger = logging.getLogger("automationservice.email_context")


async def fetch_thread_messages(
    conversation_id: str,
    user_id: str,
    latest_message_id: str,
) -> dict:
    """
    Fetch conversation metadata + thread history from the DB.

    Query flow:
      1. es_conversations  WHERE id = conversation_id (UUID PK lookup — O(1))
            → verified thread_id, subject, participants, message_count
      2. es_messages (triggering msg)  WHERE user_id + message_id
            → content length to decide fetch depth
      3. es_messages (full history)    WHERE user_id + thread_id ORDER BY timestamp DESC LIMIT N
            → last 10 or 20 messages depending on dynamic fetch decision

    Args:
        conversation_id:   UUID from es_conversations.id — sent by emailservice ai_handoff_worker
        user_id:           UUID string — owner of the conversation
        latest_message_id: Gmail/Outlook message_id of the triggering incoming message

    Returns:
        {
            "conversation":   dict,        # es_conversations row (metadata)
            "messages":       list[dict],  # es_messages rows, oldest → newest
            "latest_message": dict | None, # triggering message row
            "fetch_count":    int,
            "fetch_reason":   "short_message" | "normal" | "not_found" | "error"
        }
    """
    print(f"\n{'='*62}")
    print(f"[AUTOMATIONSERVICE] 📨 FETCH THREAD MESSAGES")
    print(f"  conversation_id   : {conversation_id}")
    print(f"  user_id           : {user_id}")
    print(f"  latest_message_id : {latest_message_id}")
    print(f"{'='*62}")

    try:
        async with get_db_session() as session:

            # ── Query 1: Load conversation from es_conversations ───────────────
            # Uses conversation_id (UUID PK) — O(1) index lookup.
            # This gives us the authoritative thread_id owned by this user.
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
                {
                    "conversation_id": conversation_id,
                    "user_id":         user_id,
                },
            )
            conversation = conv_row.mappings().first()

            if not conversation:
                logger.warning(
                    "[email_context] conversation not found in es_conversations "
                    "| conversation_id=%s user_id=%s",
                    conversation_id, user_id,
                )
                print(f"[AUTOMATIONSERVICE] ⚠️  Conversation NOT FOUND in es_conversations")
                print(f"  conversation_id : {conversation_id}")
                print(f"  user_id         : {user_id}")
                print(f"  → This means emailservice has not yet stored the conversation,")
                print(f"    or the conversation_id in the event payload is wrong.")
                return {
                    "conversation":   None,
                    "messages":       [],
                    "latest_message": None,
                    "fetch_count":    0,
                    "fetch_reason":   "conversation_not_found",
                }

            conversation_dict = dict(conversation)
            # Verified thread_id from the DB — used for all subsequent queries
            db_thread_id = conversation_dict["thread_id"]

            print(f"\n[AUTOMATIONSERVICE] 📋 CONVERSATION FOUND in es_conversations")
            print(f"  db thread_id    : {db_thread_id}")
            print(f"  subject         : {conversation_dict.get('subject', '(no subject)')}")
            print(f"  provider        : {conversation_dict.get('provider', '?')}")
            print(f"  message_count   : {conversation_dict.get('message_count', '?')}")
            print(f"  last_message_at : {conversation_dict.get('last_message_at', '?')}")
            print(f"  status          : {conversation_dict.get('status', '?')}")
            print(f"  participants    : {conversation_dict.get('participants', [])}")

            # ── Query 2: Load triggering message to decide fetch depth ─────────
            # Uses (user_id, message_id) unique index — O(1).
            # We need the content length to apply the dynamic fetch rule.
            latest_row = await session.execute(
                text("""
                    SELECT
                        message_id,
                        thread_id,
                        from_email,
                        to_emails,
                        cc_emails,
                        subject,
                        content,
                        direction,
                        timestamp,
                        has_attachments,
                        status,
                        message_state
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
                    "[email_context] triggering message not found in es_messages "
                    "| message_id=%s user_id=%s",
                    latest_message_id, user_id,
                )
                print(f"[AUTOMATIONSERVICE] ⚠️  Triggering message NOT FOUND in es_messages")
                print(f"  message_id : {latest_message_id}")
                print(f"  Note: conversation exists but triggering message not yet stored.")
                print(f"  This can happen if automationservice woke before StorageWorker committed.")
                return {
                    "conversation":   conversation_dict,
                    "messages":       [],
                    "latest_message": None,
                    "fetch_count":    0,
                    "fetch_reason":   "message_not_found",
                }

            latest_dict = dict(latest)
            latest_body = latest_dict.get("content") or ""

            # ── Dynamic fetch depth decision ───────────────────────────────────
            # Rule from implementation_plan.md:
            #   body < 20 chars  → fetch 20 messages (short/ambiguous reply needs more context)
            #   otherwise        → fetch 10 messages
            if len(latest_body) < SHORT_MSG_CHAR_THRESHOLD:
                fetch_count  = FETCH_COUNT_SHORT
                fetch_reason = "short_message"
            else:
                fetch_count  = FETCH_COUNT_NORMAL
                fetch_reason = "normal"

            print(f"\n[AUTOMATIONSERVICE] 🔍 DYNAMIC FETCH DECISION")
            print(f"  body length  : {len(latest_body)} chars")
            print(f"  threshold    : {SHORT_MSG_CHAR_THRESHOLD} chars")
            print(f"  fetch_count  : {fetch_count} messages")
            print(f"  fetch_reason : {fetch_reason}")

            # ── Query 3: Fetch last N messages from es_messages ────────────────
            # Uses verified db_thread_id from es_conversations — never the raw
            # thread_id from the event payload.
            # Index: ix_es_messages_thread (user_id, thread_id, timestamp)
            history_rows = await session.execute(
                text("""
                    SELECT
                        message_id,
                        thread_id,
                        from_email,
                        to_emails,
                        cc_emails,
                        subject,
                        content,
                        direction,
                        timestamp,
                        has_attachments,
                        status,
                        message_state
                    FROM es_messages
                    WHERE user_id   = :user_id
                      AND thread_id = :thread_id
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {
                    "user_id":   user_id,
                    "thread_id": db_thread_id,   # ← from es_conversations, not event payload
                    "limit":     fetch_count,
                },
            )
            messages_raw = history_rows.mappings().all()

        # ── Reverse DESC → ASC (oldest message first) ─────────────────────────
        messages = [dict(r) for r in reversed(messages_raw)]

        # ── Serialize datetime → ISO string ───────────────────────────────────
        for m in messages:
            if isinstance(m.get("timestamp"), datetime):
                m["timestamp"] = m["timestamp"].isoformat()
        if isinstance(latest_dict.get("timestamp"), datetime):
            latest_dict["timestamp"] = latest_dict["timestamp"].isoformat()
        for key in ("last_message_at", "created_at", "updated_at"):
            if isinstance(conversation_dict.get(key), datetime):
                conversation_dict[key] = conversation_dict[key].isoformat()

        # ── Print full context summary ─────────────────────────────────────────
        print(f"\n[AUTOMATIONSERVICE] ✅ THREAD CONTEXT FETCHED FROM DB")
        print(f"  source           : es_conversations + es_messages (proper DB fetch)")
        print(f"  conversation_id  : {conversation_id}")
        print(f"  db_thread_id     : {db_thread_id}")
        print(f"  messages fetched : {len(messages)}")
        print(f"  subject          : {conversation_dict.get('subject', '(no subject)')}")
        print(f"  latest direction : {latest_dict.get('direction', '?')}")
        print(f"  latest from      : {latest_dict.get('from_email', '?')}")
        snippet = latest_body[:120]
        print(f"  latest snippet   : {snippet}{'...' if len(latest_body) > 120 else ''}")
        print(f"  {'─'*58}")
        for i, msg in enumerate(messages):
            icon     = "📥" if msg.get("direction") == "incoming" else "📤"
            ts       = (msg.get("timestamp") or "")[:19]
            body_len = len(msg.get("content") or "")
            state    = msg.get("message_state") or msg.get("status") or "?"
            print(
                f"  [{i+1:02d}] {icon} [{msg.get('direction','?'):8s}] "
                f"from={msg.get('from_email','?'):<32s} "
                f"ts={ts}  len={body_len:4d}  state={state}"
            )

        return {
            "conversation":   conversation_dict,
            "messages":       messages,
            "latest_message": latest_dict,
            "fetch_count":    len(messages),
            "fetch_reason":   fetch_reason,
        }

    except Exception as e:
        logger.error("[email_context] fetch failed: %s", e, exc_info=True)
        print(f"[AUTOMATIONSERVICE] ❌ FETCH ERROR: {e}")
        return {
            "conversation":   None,
            "messages":       [],
            "latest_message": None,
            "fetch_count":    0,
            "fetch_reason":   "error",
        }
