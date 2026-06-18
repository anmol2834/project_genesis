"""
automationservice — API Router
Endpoints: POST /trigger  POST /process  GET /health
"""
from __future__ import annotations
import os
import sys
import logging
import time

_API_DIR      = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR      = os.path.dirname(_API_DIR)
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.email_context import fetch_thread_messages

logger = logging.getLogger("automationservice.router")

router = APIRouter(tags=["automation"])


class AutomationTrigger(BaseModel):
    conversation_id:    str  = ""
    user_id:            str
    message_id:         str
    thread_id:          str  = ""
    subject:            str  = ""
    from_email:         str  = ""
    provider:           str  = ""
    trace_id:           str  = ""
    automation_enabled: bool = True
    priority:           int  = Field(default=2, alias="_priority")

    model_config = {"populate_by_name": True}


async def process_event(event: dict) -> dict:
    t_start = time.monotonic()

    user_id         = event.get("user_id", "")
    message_id      = event.get("message_id", "")
    conversation_id = event.get("conversation_id", "")
    thread_id       = event.get("thread_id", "")
    subject         = event.get("subject", "")
    from_email      = event.get("from_email", "")
    provider        = event.get("provider", "")
    priority        = event.get("_priority", event.get("priority", 2))
    automation_enabled = event.get("automation_enabled", True)

    if not automation_enabled:
        logger.info("Automation disabled | user=%s message=%s", user_id, message_id)
        return {"status": "skipped", "reason": "automation_disabled"}

    if not user_id or not message_id:
        missing = [f for f, v in [("user_id", user_id), ("message_id", message_id)] if not v]
        logger.warning("Invalid event — missing %s", missing)
        return {"status": "error", "reason": f"missing_required_fields: {missing}"}

    if not conversation_id:
        logger.warning("Missing conversation_id | user=%s message=%s thread=%s",
                       user_id, message_id, thread_id)
        return {"status": "error", "reason": "missing_conversation_id", "message_id": message_id}

    context = await fetch_thread_messages(
        conversation_id   = conversation_id,
        user_id           = user_id,
        latest_message_id = message_id,
    )

    elapsed_ms = (time.monotonic() - t_start) * 1000

    if not context["messages"]:
        logger.warning("No messages fetched | conv=%s user=%s reason=%s",
                       conversation_id, user_id, context["fetch_reason"])
        return {
            "status":          "no_context",
            "reason":          context["fetch_reason"],
            "message_id":      message_id,
            "conversation_id": conversation_id,
            "elapsed_ms":      elapsed_ms,
        }

    conv_meta = context.get("conversation") or {}

    logger.info(
        "Pipeline 1-2 complete | user=%s conv=%s subject=%r msgs=%d fetch=%s provider=%s elapsed=%.0fms",
        user_id,
        conversation_id[:8],
        subject,
        context["fetch_count"],
        context["fetch_reason"],
        provider,
        elapsed_ms,
    )

    return {
        "status":          "pipeline_steps_1_2_complete",
        "user_id":         user_id,
        "message_id":      message_id,
        "conversation_id": conversation_id,
        "thread_id":       conv_meta.get("thread_id", thread_id),
        "fetch_count":     context["fetch_count"],
        "fetch_reason":    context["fetch_reason"],
        "conversation":    conv_meta,
        "messages":        context["messages"],
        "latest_message":  context["latest_message"],
        "elapsed_ms":      elapsed_ms,
    }


@router.post("/trigger")
async def trigger_automation(payload: AutomationTrigger) -> dict:
    return await process_event(payload.model_dump(by_alias=True))


@router.post("/process")
async def process_fallback(payload: AutomationTrigger) -> dict:
    return await trigger_automation(payload)


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "automationservice", "version": "1.0.0"}
