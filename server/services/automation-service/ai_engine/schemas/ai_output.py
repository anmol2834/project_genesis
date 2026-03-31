"""
AI Engine Output Schema
=======================
Enterprise output contract for the ACRE pipeline.

status values:
  success      — reply generated and approved
  no_response  — pipeline decided not to reply (e.g. out-of-office, spam)
  rejected     — policy engine blocked the reply
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AIDecisionStatus(str, Enum):
    SUCCESS      = "success"
    NO_RESPONSE  = "no_response"
    REJECTED     = "rejected"
    HUMAN_REVIEW = "human_review"   # Reply preserved, awaiting human approval


class OutputMetadata(BaseModel):
    """Full traceability metadata — required for enterprise threading and audit."""
    conversation_id:  Optional[str] = None
    thread_id:        Optional[str] = None
    message_id:       Optional[str] = None   # The incoming message_id being replied to
    reply_to:         Optional[str] = None   # sender email (reply target)
    user_id:          Optional[str] = None
    email_account_id: Optional[str] = None
    lead_email:       Optional[str] = None   # alias for reply_to, explicit for clarity

    model_config = {"extra": "allow"}


class OutputRouting(BaseModel):
    """Routing decision for downstream email dispatch."""
    send_email:      bool  = False
    priority:        str   = "normal"   # "normal" | "high"
    requires_human:  bool  = False

    model_config = {"extra": "allow"}


class AIEngineOutput(BaseModel):
    """
    Enterprise output of the ACRE pipeline.
    Consumed by automation-service to dispatch or queue the reply.
    """
    # ── Core fields ───────────────────────────────────────────────────────
    status: AIDecisionStatus
    reply: str = Field(
        ...,
        description="Generated reply text. Empty string when status != success."
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    intent_handled: str = Field(
        ...,
        description="The IntentType value that was acted upon."
    )

    # ── Optional audit field ──────────────────────────────────────────────
    reason: Optional[str] = Field(
        None,
        description="Human-readable reason for rejection or no_response decisions."
    )

    # ── Enterprise metadata block (thread tracking + audit) ───────────────
    metadata: OutputMetadata = Field(default_factory=OutputMetadata)

    # ── Routing decision ──────────────────────────────────────────────────
    routing: OutputRouting = Field(default_factory=OutputRouting)

    # ── Email dispatch payload (from LLM — for direct send) ───────────────
    email_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Ready-to-send email payload populated by LLM from metadata."
    )

    # ── Legacy traceability (kept for backward compat) ────────────────────
    conversation_id: Optional[UUID] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_reply_consistency(self) -> "AIEngineOutput":
        """
        Enforce contract:
          - success       → reply must be non-empty
          - human_review  → reply preserved (may be non-empty), reason required
          - rejected      → hard block, reply empty, reason required
          - no_response   → reply empty, reason required
        """
        if self.status == AIDecisionStatus.SUCCESS and not self.reply.strip():
            raise ValueError("reply must be non-empty when status is 'success'")
        if self.status in (AIDecisionStatus.NO_RESPONSE, AIDecisionStatus.REJECTED) and not self.reason:
            raise ValueError(f"reason must be provided when status is '{self.status.value}'")
        # HUMAN_REVIEW may have a reply — no validation error
        return self

    model_config = {"extra": "forbid"}
