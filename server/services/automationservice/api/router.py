"""
automationservice — API Router
================================
Endpoints:
  POST /trigger  — HTTP trigger (testing + ai_handoff_worker HTTP fallback)
  POST /process  — legacy alias that ai_handoff_worker posts to on Redis failure
  GET  /health   — liveness probe

Primary path is the Redis BLPOP notify loop in main.py.
HTTP endpoints are fallback/test surfaces only.

sys.path note:
  This file lives at: server/services/automationservice/api/router.py
  server/ and automationservice/ root must both be on sys.path.
"""
from __future__ import annotations
import os
import sys
import logging
import time

_API_DIR      = os.path.dirname(os.path.abspath(__file__))   # .../api
_SVC_DIR      = os.path.dirname(_API_DIR)                    # .../automationservice
_SERVICES_DIR = os.path.dirname(_SVC_DIR)                    # .../server/services
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)               # .../server

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.email_context import fetch_thread_messages

logger = logging.getLogger("automationservice.router")

router = APIRouter(tags=["automation"])


# ── Request schema ─────────────────────────────────────────────────────────────

class AutomationTrigger(BaseModel):
    """
    Payload from emailservice ai_handoff_worker.

    Key fields:
      conversation_id — UUID of es_conversations.id row (authoritative)
      thread_id       — raw provider thread_id string (kept for logging only)
      message_id      — the triggering incoming message
      user_id         — owner UUID

    NOTE: _priority uses leading underscore in Redis event dicts.
    Pydantic v2 treats _ prefix as private, so we use Field alias.
    """
    conversation_id:    str  = ""
    user_id:            str
    message_id:         str
    thread_id:          str  = ""   # kept for logging/fallback only
    subject:            str  = ""
    from_email:         str  = ""
    provider:           str  = ""
    trace_id:           str  = ""
    automation_enabled: bool = True
    priority:           int  = Field(default=2, alias="_priority")

    model_config = {"populate_by_name": True}


# ── Core pipeline ──────────────────────────────────────────────────────────────

async def process_event(event: dict) -> dict:
    """
    2-step pipeline for a single automation event.

      Step 1 — Trigger Automation
            Validate + log the incoming event from emailservice.
            Extract conversation_id (UUID) — this is the anchor for all DB lookups.
            ↓
      Step 2 — Fetch Last 10 Messages (Dynamic Fetching)
            Query 1: es_conversations WHERE id = conversation_id  → verified thread_id
            Query 2: es_messages WHERE user_id + message_id       → triggering message + fetch depth
            Query 3: es_messages WHERE user_id + thread_id        → full history (10 or 20 msgs)

    The conversation_id from emailservice ai_handoff_worker is preferred.
    If missing (HTTP fallback path), we fall back to thread_id only as a
    last resort — but log a clear warning.
    """
    t_start = time.monotonic()

    user_id         = event.get("user_id", "")
    message_id      = event.get("message_id", "")
    conversation_id = event.get("conversation_id", "")
    thread_id       = event.get("thread_id", "")   # raw provider string — for logging only
    subject         = event.get("subject", "")
    from_email      = event.get("from_email", "")
    provider        = event.get("provider", "")
    trace_id        = event.get("trace_id", "")
    priority        = event.get("_priority", event.get("priority", 2))
    automation_enabled = event.get("automation_enabled", True)

    # ── STEP 1: Trigger Automation ────────────────────────────────────────────
    print(f"\n{'#'*70}")
    print(f"[AUTOMATIONSERVICE] 🚀 PIPELINE TRIGGERED — STEP 1")
    print(f"  user_id            : {user_id}")
    print(f"  message_id         : {message_id}")
    print(f"  conversation_id    : {conversation_id}  ← es_conversations UUID")
    print(f"  thread_id (raw)    : {thread_id}  ← provider string (logging only)")
    print(f"  subject            : {subject}")
    print(f"  from_email         : {from_email}")
    print(f"  provider           : {provider}")
    print(f"  trace_id           : {trace_id}")
    print(f"  priority           : {priority}")
    print(f"  automation_enabled : {automation_enabled}")
    print(f"  event_ts           : {event.get('ts', 'n/a')}")
    print(f"{'#'*70}")

    if not automation_enabled:
        print(f"[AUTOMATIONSERVICE] ⏭️  AUTOMATION DISABLED — user={user_id} skipped")
        logger.info("Automation disabled | user=%s message=%s", user_id, message_id)
        return {"status": "skipped", "reason": "automation_disabled"}

    if not user_id or not message_id:
        missing = [f for f, v in [("user_id", user_id), ("message_id", message_id)] if not v]
        print(f"[AUTOMATIONSERVICE] ⚠️  INVALID EVENT — missing: {missing}")
        logger.warning("Invalid event — missing %s | event=%s", missing, event)
        return {"status": "error", "reason": f"missing_required_fields: {missing}"}

    # conversation_id is the correct anchor — it's the UUID PK of es_conversations
    # thread_id is a raw provider string and must NOT be used directly for DB lookups
    if not conversation_id:
        # This should not happen in the normal Redis path — ai_handoff_worker always
        # includes conversation_id. Can happen on the HTTP fallback path if caller
        # omits it. Log a clear warning and refuse to proceed rather than silently
        # doing a wrong raw thread_id lookup.
        print(f"[AUTOMATIONSERVICE] ⚠️  MISSING conversation_id — cannot fetch context")
        print(f"  thread_id (raw) : {thread_id}")
        print(f"  The event must include conversation_id (UUID from es_conversations).")
        print(f"  If this is the HTTP fallback path, ensure the payload includes conversation_id.")
        logger.warning(
            "Missing conversation_id in event | user=%s message=%s thread_id=%s",
            user_id, message_id, thread_id,
        )
        return {
            "status":  "error",
            "reason":  "missing_conversation_id",
            "message_id": message_id,
        }

    # ── STEP 2: Fetch Last 10 Messages via es_conversations → es_messages ─────
    print(f"\n[AUTOMATIONSERVICE] ⬇️  STEP 2 — FETCH THREAD CONTEXT")
    print(f"  anchor: es_conversations.id = {conversation_id}")
    print(f"  → will resolve thread_id from DB, then query es_messages")

    context = await fetch_thread_messages(
        conversation_id   = conversation_id,   # ← UUID anchor, looked up in es_conversations first
        user_id           = user_id,
        latest_message_id = message_id,
    )

    elapsed_ms = (time.monotonic() - t_start) * 1000

    if not context["messages"]:
        reason = context["fetch_reason"]
        print(f"\n[AUTOMATIONSERVICE] ⚠️  NO MESSAGES FETCHED — pipeline halted")
        print(f"  reason  : {reason}")
        print(f"  elapsed : {elapsed_ms:.1f}ms")
        logger.warning(
            "No messages fetched | conv=%s user=%s reason=%s",
            conversation_id, user_id, reason,
        )
        return {
            "status":          "no_context",
            "reason":          reason,
            "message_id":      message_id,
            "conversation_id": conversation_id,
            "elapsed_ms":      elapsed_ms,
        }

    # ── Checkpoint ────────────────────────────────────────────────────────────
    conv_meta = context.get("conversation") or {}
    print(f"\n[AUTOMATIONSERVICE] ✅ PIPELINE STEPS 1-2 COMPLETE")
    print(f"  ✔ Step 1 — Trigger Automation   : OK")
    print(f"  ✔ Step 2 — Fetch Thread Context :")
    print(f"      source          : es_conversations → es_messages")
    print(f"      conversation_id : {conversation_id}")
    print(f"      db_thread_id    : {conv_meta.get('thread_id', '?')}")
    print(f"      messages_fetched: {context['fetch_count']} ({context['fetch_reason']})")
    print(f"      subject         : {conv_meta.get('subject', '?')}")
    print(f"      provider        : {conv_meta.get('provider', '?')}")
    print(f"  elapsed : {elapsed_ms:.1f}ms")
    print(f"  next    : LLM Call #1 → Processor 1 (Analysis & Retrieval Planning)")
    print(f"{'#'*70}\n")

    logger.info(
        "Pipeline steps 1-2 complete | user=%s conv=%s thread=%s msgs=%d fetch=%s elapsed=%.0fms",
        user_id,
        conversation_id[:8],
        conv_meta.get("thread_id", "?")[:12],
        context["fetch_count"],
        context["fetch_reason"],
        elapsed_ms,
    )

    return {
        "status":          "pipeline_steps_1_2_complete",
        "user_id":         user_id,
        "message_id":      message_id,
        "conversation_id": conversation_id,
        "thread_id":       conv_meta.get("thread_id", thread_id),   # verified from DB
        "fetch_count":     context["fetch_count"],
        "fetch_reason":    context["fetch_reason"],
        "conversation":    conv_meta,
        "messages":        context["messages"],
        "latest_message":  context["latest_message"],
        "elapsed_ms":      elapsed_ms,
    }


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@router.post("/trigger")
async def trigger_automation(payload: AutomationTrigger) -> dict:
    """
    HTTP trigger — for testing and ai_handoff_worker HTTP fallback.
    Primary path is the Redis notify loop in main.py.
    """
    print(f"\n[AUTOMATIONSERVICE] 🌐 HTTP /trigger")
    print(f"  from_email      : {payload.from_email}")
    print(f"  subject         : {payload.subject}")
    print(f"  message_id      : {payload.message_id}")
    print(f"  conversation_id : {payload.conversation_id}")
    event = payload.model_dump(by_alias=True)
    return await process_event(event)


@router.post("/process")
async def process_fallback(payload: AutomationTrigger) -> dict:
    """Legacy /process alias — ai_handoff_worker HTTP fallback posts here."""
    return await trigger_automation(payload)


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "automationservice", "version": "1.0.0"}
