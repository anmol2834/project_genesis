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
  We need server/ on path so shared.* resolves, and automationservice/ root
  so core.* and services.* resolve.
"""
from __future__ import annotations
import os
import sys
import logging
import time

_API_DIR      = os.path.dirname(os.path.abspath(__file__))          # .../api
_SVC_DIR      = os.path.dirname(_API_DIR)                           # .../automationservice
_SERVICES_DIR = os.path.dirname(_SVC_DIR)                           # .../services
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)                      # .../server

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
    Payload sent by emailservice ai_handoff_worker HTTP fallback
    and accepted by the /trigger + /process endpoints.

    NOTE: _priority uses a leading underscore in the Redis event dict,
    but Pydantic v2 treats fields starting with _ as private (ClassVar).
    We use `priority` here and map from `_priority` in process_event().
    """
    conversation_id:    str  = ""
    user_id:            str
    message_id:         str
    thread_id:          str
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

      Step 1 — Trigger Automation  : validate + log incoming event
          ↓
      Step 2 — Fetch Last 10 Msgs  : dynamic fetch (10 normal / 20 short)
    """
    t_start = time.monotonic()

    user_id    = event.get("user_id", "")
    message_id = event.get("message_id", "")
    # thread_id may arrive as thread_id OR conversation_id from emailservice
    thread_id  = event.get("thread_id", "") or event.get("conversation_id", "")
    subject    = event.get("subject", "")
    from_email = event.get("from_email", "")
    provider   = event.get("provider", "")
    trace_id   = event.get("trace_id", "")
    # _priority key in the Redis payload (leading underscore is fine in a plain dict)
    priority           = event.get("_priority", event.get("priority", 2))
    automation_enabled = event.get("automation_enabled", True)

    # ── STEP 1: Trigger Automation ────────────────────────────────────────────
    print(f"\n{'#'*70}")
    print(f"[AUTOMATIONSERVICE] 🚀 PIPELINE TRIGGERED — STEP 1")
    print(f"  user_id            : {user_id}")
    print(f"  message_id         : {message_id}")
    print(f"  thread_id          : {thread_id}")
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

    if not user_id or not message_id or not thread_id:
        missing = [f for f, v in [("user_id", user_id), ("message_id", message_id), ("thread_id", thread_id)] if not v]
        print(f"[AUTOMATIONSERVICE] ⚠️  INVALID EVENT — missing fields: {missing}")
        logger.warning("Invalid event — missing fields %s | event=%s", missing, event)
        return {"status": "error", "reason": f"missing_required_fields: {missing}"}

    # ── STEP 2: Fetch Last 10 Messages (Dynamic Fetching) ────────────────────
    print(f"\n[AUTOMATIONSERVICE] ⬇️  STEP 2 — FETCH THREAD CONTEXT")
    context = await fetch_thread_messages(
        thread_id=thread_id,
        user_id=user_id,
        latest_message_id=message_id,
    )

    elapsed_ms = (time.monotonic() - t_start) * 1000

    if not context["messages"]:
        print(f"\n[AUTOMATIONSERVICE] ⚠️  NO MESSAGES FETCHED — pipeline halted")
        print(f"  reason  : {context['fetch_reason']}")
        print(f"  elapsed : {elapsed_ms:.1f}ms")
        logger.warning(
            "No messages fetched | thread=%s user=%s reason=%s",
            thread_id, user_id, context["fetch_reason"],
        )
        return {
            "status":     "no_context",
            "reason":     context["fetch_reason"],
            "message_id": message_id,
            "thread_id":  thread_id,
            "elapsed_ms": elapsed_ms,
        }

    # ── Checkpoint ────────────────────────────────────────────────────────────
    print(f"\n[AUTOMATIONSERVICE] ✅ PIPELINE STEPS 1-2 COMPLETE")
    print(f"  ✔ Step 1 — Trigger Automation   : OK")
    print(f"  ✔ Step 2 — Fetch Thread Context : {context['fetch_count']} msgs ({context['fetch_reason']})")
    print(f"  elapsed  : {elapsed_ms:.1f}ms")
    print(f"  next     : LLM Call #1 → Processor 1 (Analysis & Retrieval Planning)")
    print(f"{'#'*70}\n")

    logger.info(
        "Pipeline steps 1-2 complete | user=%s thread=%s msgs=%d fetch=%s elapsed=%.0fms",
        user_id, thread_id[:12], context["fetch_count"], context["fetch_reason"], elapsed_ms,
    )

    return {
        "status":         "pipeline_steps_1_2_complete",
        "user_id":        user_id,
        "message_id":     message_id,
        "thread_id":      thread_id,
        "fetch_count":    context["fetch_count"],
        "fetch_reason":   context["fetch_reason"],
        "messages":       context["messages"],
        "latest_message": context["latest_message"],
        "elapsed_ms":     elapsed_ms,
    }


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@router.post("/trigger")
async def trigger_automation(payload: AutomationTrigger) -> dict:
    """
    HTTP trigger — for testing and ai_handoff_worker HTTP fallback.
    Primary path is the Redis notify loop in main.py.
    """
    print(f"\n[AUTOMATIONSERVICE] 🌐 HTTP /trigger")
    print(f"  from_email : {payload.from_email}")
    print(f"  subject    : {payload.subject}")
    print(f"  message_id : {payload.message_id}")
    # Convert to plain dict; map priority back to _priority key for process_event
    event = payload.model_dump(by_alias=True)
    return await process_event(event)


@router.post("/process")
async def process_fallback(payload: AutomationTrigger) -> dict:
    """Legacy /process alias — ai_handoff_worker HTTP fallback posts here."""
    return await trigger_automation(payload)


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "automationservice", "version": "1.0.0"}
