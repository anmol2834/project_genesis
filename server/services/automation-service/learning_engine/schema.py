"""
Learning Engine — Schema
=========================
Pydantic models and dataclasses for the feedback + learning system.

Tables:
  ai_feedback_logs      — one row per AI pipeline run
  ai_learning_insights  — aggregated per (user_id, intent) pair
  ai_prompt_versions    — prompt template version history (future)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class FeedbackOutcome(str, Enum):
    """
    Outcome of an AI reply, determined by observing the next user action.

    success  — user replied positively (continued conversation, accepted info)
    failed   — user replied negatively (complaint, correction, frustration)
    ignored  — no reply within the observation window (24h)
    pending  — outcome not yet determined (observation window still open)
    """
    SUCCESS  = "success"
    FAILED   = "failed"
    IGNORED  = "ignored"
    PENDING  = "pending"


class FinalActionType(str, Enum):
    SEND_REPLY   = "send_reply"
    SKIP         = "skip"
    HUMAN_REVIEW = "human_review"
    REJECT       = "reject"


# ── Pydantic models (API / serialization layer) ───────────────────────────────

class FeedbackLogCreate(BaseModel):
    """Data required to create a new feedback log entry."""
    user_id:               UUID
    conversation_id:       UUID
    email_account_id:      UUID
    intent:                str
    sub_intent:            str = "none"
    ai_reply:              str = ""
    confidence_score:      float = Field(ge=0.0, le=1.0)
    final_action:          str
    outcome:               FeedbackOutcome = FeedbackOutcome.PENDING
    response_time_seconds: Optional[float] = None
    safe_mode:             bool = False
    policy_rule_id:        str = ""
    confidence_level:      str = "medium"


class FeedbackLogRead(FeedbackLogCreate):
    """Full feedback log row as returned from DB."""
    id:         UUID
    user_reply: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LearningInsight(BaseModel):
    """Aggregated learning insight for a (user_id, intent) pair."""
    id:              UUID
    user_id:         UUID
    intent:          str
    total_count:     int
    success_count:   int
    failed_count:    int
    ignored_count:   int
    success_rate:    float
    failure_rate:    float
    avg_confidence:  float
    # Derived recommendations
    recommended_confidence_threshold: float
    recommended_safe_mode:            bool
    last_updated:    datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent":                          self.intent,
            "total_count":                     self.total_count,
            "success_rate":                    round(self.success_rate, 4),
            "failure_rate":                    round(self.failure_rate, 4),
            "avg_confidence":                  round(self.avg_confidence, 4),
            "recommended_confidence_threshold": round(self.recommended_confidence_threshold, 4),
            "recommended_safe_mode":           self.recommended_safe_mode,
            "last_updated":                    self.last_updated.isoformat(),
        }


class OutcomeClassification(BaseModel):
    """Result of classifying a user reply as positive/negative/neutral."""
    outcome:    FeedbackOutcome
    confidence: float
    signals:    list = Field(default_factory=list)
