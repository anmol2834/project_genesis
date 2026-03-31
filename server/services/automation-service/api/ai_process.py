"""
Automation Service — AI Process Endpoint
==========================================
Receives trigger from email-service after a conversation is written to DB.
Runs the full ACRE pipeline and returns the AI decision.

Called by email-service worker after EventProcessor.process_event() succeeds.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["ai-engine"])


class ProcessRequest(BaseModel):
    conversation_id: UUID
    trace_id:        Optional[str] = None


class ProcessResponse(BaseModel):
    conversation_id: UUID
    status:          str
    reply:           str
    confidence:      float
    intent_handled:  str
    reason:          Optional[str] = None
    trace_id:        str
    # Enterprise metadata — required for email threading
    metadata:        Dict[str, Any] = {}
    routing:         Dict[str, Any] = {}
    # Ready-to-send email payload
    email_payload:   Optional[Dict[str, Any]] = None


@router.post("/process", response_model=ProcessResponse)
async def process_conversation(req: ProcessRequest, request: Request):
    """
    Trigger the ACRE AI pipeline for a conversation.

    Called by email-service after writing a new message to email_conversations.
    """
    trace_id = req.trace_id or str(uuid.uuid4())

    logger.info(
        "AI process request received",
        extra={
            "conversation_id": str(req.conversation_id),
            "trace_id":        trace_id,
        },
    )

    try:
        from ai_engine.orchestrator.pipeline import handle_incoming_email_event
        output = await handle_incoming_email_event(
            conversation_id=req.conversation_id,
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error(
            "AI pipeline error",
            extra={
                "conversation_id": str(req.conversation_id),
                "trace_id":        trace_id,
                "error":           str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    return ProcessResponse(
        conversation_id=req.conversation_id,
        status=output.status.value,
        reply=output.reply,
        confidence=output.confidence,
        intent_handled=output.intent_handled,
        reason=output.reason,
        trace_id=trace_id,
        metadata=output.metadata.model_dump(),
        routing=output.routing.model_dump(),
        email_payload=output.email_payload,
    )


@router.get("/health")
async def ai_health():
    """Quick health check for the AI engine."""
    return {"status": "ok", "engine": "ACRE"}
