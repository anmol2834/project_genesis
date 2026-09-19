"""
automationservice — Conditional Retrieval Decision Engine
=========================================================
Determines whether Qdrant hybrid retrieval should be executed for the current customer message.
Prevents redundant RAG calls, enforces domain boundaries, and computes candidate exclusions.

Design Principles:
1. Retrieval is CONDITIONAL: Pure acknowledgments, booking confirmations with known slots,
   and thank-you closures bypass Qdrant completely (0ms latency, zero false retrieval).
2. Dynamic Query Construction: Continuation turns ("what else?", "show me more") preserve
   the active category but exclude all previously presented and rejected entry IDs.
3. Domain Isolation: Inquiries regarding contact channels or delivery mechanisms route
   strictly to their respective domain, never returning unrelated catalog/service records.
"""
from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, Field

from services.conversation_state import ConversationState, ConversationStage, BookingStatus
from pipeline.slot_tracker import ExtractedSignals

logger = logging.getLogger("automationservice.retrieval_decision")


class RetrievalDecision(BaseModel):
    should_retrieve: bool = True
    reason: str = "standard_retrieval"
    target_domain: str = "product_service"
    query: str = ""
    exclude_entry_ids: list[str] = Field(default_factory=list)
    is_continuation: bool = False
    is_rejection: bool = False


class RetrievalDecisionEngine:
    @staticmethod
    def evaluate(
        latest_message: str,
        state: ConversationState,
        signals: ExtractedSignals,
        p1_intent: dict[str, Any] | None = None,
    ) -> RetrievalDecision:
        """
        Evaluate whether Qdrant hybrid retrieval should be executed.
        """
        raw_msg = (latest_message or "").strip()
        p1_cat = (p1_intent or {}).get("category") or "product_service"
        all_exclusions = list(set(state.presented_entry_ids + state.rejected_entry_ids))

        # ── Case 1: Simple Gratitude / Closure ────────────────────────────────
        if signals.is_gratitude and not signals.is_continuation and not signals.is_contact_inquiry and not signals.is_delivery_inquiry:
            logger.info("[RETRIEVAL_DECISION] should_retrieve=False | reason=gratitude_closure")
            return RetrievalDecision(
                should_retrieve=False,
                reason="gratitude_closure",
                target_domain="none",
                query="",
                exclude_entry_ids=all_exclusions,
            )

        # ── Case 2: Booking / Scheduling Confirmation ─────────────────────────
        # When customer confirms ("yes", "please proceed", "go ahead") or provides scheduled time
        # and the service was already discussed / selected.
        is_confirming_booking = (
            signals.is_confirmation
            or (signals.extracted_slots.get("preferred_time") and not signals.is_continuation)
        )
        if is_confirming_booking and state.stage in (
            ConversationStage.ACTION_REQUESTED,
            ConversationStage.ACTION_IN_PROGRESS,
            ConversationStage.ACTION_CONFIRMED,
            ConversationStage.SELECTION,
            ConversationStage.INFORMATION,
        ) and state.presented_entry_ids:
            logger.info(
                "[RETRIEVAL_DECISION] should_retrieve=False | reason=booking_action_confirmation stage=%s",
                state.stage.value,
            )
            return RetrievalDecision(
                should_retrieve=False,
                reason="booking_action_confirmation",
                target_domain=state.current_topic or "product_service",
                query="",
                exclude_entry_ids=all_exclusions,
            )

        # ── Case 3: Rejection ("not this", "too expensive", "something different")
        if signals.is_rejection:
            logger.info(
                "[RETRIEVAL_DECISION] should_retrieve=True | reason=customer_rejection exclusions=%d",
                len(all_exclusions),
            )
            return RetrievalDecision(
                should_retrieve=True,
                reason="customer_rejection_alternatives",
                target_domain=state.current_topic or "product_service",
                query=f"alternative options different {raw_msg}",
                exclude_entry_ids=all_exclusions,
                is_rejection=True,
            )

        # ── Case 4: Continuation ("what else?", "show me more", "other services")
        if signals.is_continuation:
            logger.info(
                "[RETRIEVAL_DECISION] should_retrieve=True | reason=continuation exclusions=%d",
                len(all_exclusions),
            )
            return RetrievalDecision(
                should_retrieve=True,
                reason="continuation_request",
                target_domain=state.current_topic or "product_service",
                query=f"additional services products options {raw_msg}",
                exclude_entry_ids=all_exclusions,
                is_continuation=True,
            )

        # ── Case 5: Contact Channel Inquiry ───────────────────────────────────
        if signals.is_contact_inquiry or p1_cat == "contact_support":
            logger.info("[RETRIEVAL_DECISION] should_retrieve=True | domain=contact_support")
            return RetrievalDecision(
                should_retrieve=True,
                reason="contact_support_inquiry",
                target_domain="contact_support",
                query=raw_msg or "business contact support phone email address",
                exclude_entry_ids=[],
            )

        # ── Case 6: Delivery / Logistics Inquiry ──────────────────────────────
        if signals.is_delivery_inquiry or p1_cat == "delivery_shipping":
            logger.info("[RETRIEVAL_DECISION] should_retrieve=True | domain=delivery_shipping")
            return RetrievalDecision(
                should_retrieve=True,
                reason="delivery_shipping_inquiry",
                target_domain="delivery_shipping",
                query=raw_msg or "delivery shipping timeline serviceable regions",
                exclude_entry_ids=[],
            )

        # ── Case 7: Default Informational Retrieval ───────────────────────────
        logger.info(
            "[RETRIEVAL_DECISION] should_retrieve=True | reason=informational_query domain=%s exclusions=%d",
            p1_cat, len(all_exclusions),
        )
        return RetrievalDecision(
            should_retrieve=True,
            reason="informational_query",
            target_domain=p1_cat,
            query=raw_msg,
            exclude_entry_ids=all_exclusions,
        )
