"""
automationservice — Enterprise Conversation State Management
============================================================
Multi-tenant, tenant-agnostic conversation state machine and persistence.
Authoritative source of truth: PostgreSQL es_conversations.conversation_state (JSONB).

Design Principles:
1. Zero hardcoded business concepts (no products, services, prices, or domains).
2. Pure generic state machine: NEW -> DISCOVERY/INFORMATION -> ACTION_REQUESTED -> ACTION_CONFIRMED -> CLOSED -> REOPENED.
3. Persistent memory: Tracks presented entries, rejected entries, confirmed slots, and closure status.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy import text

from core.database import get_db_session

logger = logging.getLogger("automationservice.conversation_state")


class ConversationStage(str, Enum):
    NEW = "NEW"
    DISCOVERY = "DISCOVERY"
    INFORMATION = "INFORMATION"
    QUALIFICATION = "QUALIFICATION"
    SELECTION = "SELECTION"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    ACTION_IN_PROGRESS = "ACTION_IN_PROGRESS"
    ACTION_CONFIRMED = "ACTION_CONFIRMED"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    HANDOFF = "HANDOFF"


class BookingStatus(str, Enum):
    NONE = "none"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class BookingState(BaseModel):
    status: BookingStatus = BookingStatus.NONE
    action_type: str = "booking"  # generic: booking, appointment, quote, consultation, etc.
    confirmed_slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    confirmation_reference: Optional[str] = None
    confirmed_at: Optional[str] = None


class ConversationState(BaseModel):
    conversation_id: str = ""
    user_id: str = ""
    thread_id: str = ""
    stage: ConversationStage = ConversationStage.NEW
    status: str = "active"  # "active" | "closed" | "reopened"
    
    # Intent & Topic tracking
    current_intent: str = "general_inquiry"
    current_topic: str = ""
    customer_goal: str = ""
    discussed_topics: list[str] = Field(default_factory=list)
    
    # Slot / Requirements tracking (domain-agnostic)
    confirmed_slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    customer_preferences: dict[str, Any] = Field(default_factory=dict)
    customer_constraints: dict[str, Any] = Field(default_factory=dict)
    
    # Booking / Action state
    booking_state: BookingState = Field(default_factory=BookingState)
    
    # Evidence & Catalog tracking (prevents repeating / handles "more" and "rejection")
    presented_entry_ids: list[str] = Field(default_factory=list)
    rejected_entry_ids: list[str] = Field(default_factory=list)
    last_retrieval_query: Optional[str] = None
    last_retrieval_domain: Optional[str] = None
    
    # Deduplication & Loop prevention
    last_assistant_response_hash: Optional[str] = None
    last_response_intent: Optional[str] = None
    response_count: int = 0
    consecutive_same_topic_count: int = 0
    closure_reason: Optional[str] = None
    
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_slot_known(self, slot_name: str) -> bool:
        """Check if a slot is already provided with a non-empty value."""
        val = self.confirmed_slots.get(slot_name) or self.booking_state.confirmed_slots.get(slot_name)
        return bool(val and str(val).strip().lower() not in ("unknown", "none", "null", ""))

    def mark_presented(self, entry_ids: list[str]) -> None:
        """Record entry IDs that were actually communicated to the customer."""
        for eid in entry_ids:
            if eid and eid not in self.presented_entry_ids:
                self.presented_entry_ids.append(str(eid))

    def mark_rejected(self, entry_ids: list[str]) -> None:
        """Record entry IDs that the customer explicitly rejected."""
        for eid in entry_ids:
            if eid and eid not in self.rejected_entry_ids:
                self.rejected_entry_ids.append(str(eid))

    def transition_to(self, new_stage: ConversationStage, reason: str = "") -> None:
        """Transitions conversation stage with audit logging."""
        old_stage = self.stage
        self.stage = new_stage
        self.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "[STATE TRANSITION] conv=%s: %s -> %s | reason=%s",
            self.conversation_id[:8] if self.conversation_id else "?",
            old_stage.value,
            new_stage.value,
            reason or "intent_driven",
        )

    def close(self, reason: str = "goal_completed") -> None:
        """Marks conversation as closed."""
        self.status = "closed"
        self.closure_reason = reason
        self.transition_to(ConversationStage.CLOSED, reason=reason)

    def reopen(self, reason: str = "new_customer_inquiry") -> None:
        """Reopens a closed conversation for a new inquiry."""
        self.status = "reopened"
        self.closure_reason = None
        self.transition_to(ConversationStage.REOPENED, reason=reason)


def parse_conversation_state(
    conversation_id: str,
    user_id: str,
    thread_id: str,
    raw_state: dict[str, Any] | None,
) -> ConversationState:
    """Parse raw JSONB dict from DB into typed ConversationState."""
    if not raw_state or not isinstance(raw_state, dict):
        return ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            thread_id=thread_id,
        )
    try:
        data = dict(raw_state)
        data.setdefault("conversation_id", conversation_id)
        data.setdefault("user_id", user_id)
        data.setdefault("thread_id", thread_id)
        return ConversationState.model_validate(data)
    except Exception as e:
        logger.warning(
            "[parse_conversation_state] fallback to default state | conv=%s error=%s",
            conversation_id[:8], e
        )
        return ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            thread_id=thread_id,
        )


async def save_conversation_state(state: ConversationState) -> bool:
    """
    Persist ConversationState directly into PostgreSQL es_conversations.conversation_state (JSONB).
    ACID durable, survives worker and server restarts.
    """
    if not state.conversation_id or not state.user_id:
        logger.warning("[save_conversation_state] missing conversation_id or user_id — skipping persist")
        return False

    state.updated_at = datetime.now(timezone.utc).isoformat()
    dumped_dict = state.model_dump(mode="json")

    try:
        async with get_db_session() as session:
            await session.execute(
                text("""
                    UPDATE es_conversations
                    SET conversation_state = :c_state,
                        updated_at         = NOW()
                    WHERE id      = :conv_id
                      AND user_id = :user_id
                """),
                {
                    "c_state": dumped_dict,
                    "conv_id": state.conversation_id,
                    "user_id": state.user_id,
                },
            )
            await session.commit()
            logger.debug(
                "[save_conversation_state] state committed | conv=%s stage=%s presented=%d",
                state.conversation_id[:8], state.stage.value, len(state.presented_entry_ids)
            )
            return True
    except Exception as e:
        logger.error(
            "[save_conversation_state] failed to persist state | conv=%s: %s",
            state.conversation_id[:8], e, exc_info=True
        )
        return False
