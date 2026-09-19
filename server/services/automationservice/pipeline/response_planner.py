"""
automationservice — Conversational Response Planner
===================================================
Produces a deterministic ResponsePlan before prose generation in Processor #2.
Enforces delta-only responses, eliminates repetition, governs question generation,
and guides conversation closure.

Design Principles:
1. DELTA-BASED: Answers only what is needed for the CURRENT customer turn.
2. NO REDUNDANT QUESTIONS: If booking is confirmed or slots are known, questions are forbidden.
3. DOMAIN AGNOSTIC: Operates on generic conversational goals and actions.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from services.conversation_state import ConversationState, ConversationStage, BookingStatus
from pipeline.slot_tracker import ExtractedSignals
from pipeline.retrieval_decision import RetrievalDecision

logger = logging.getLogger("automationservice.response_planner")


class ResponsePlan(BaseModel):
    intent: str = "general_inquiry"
    conversation_stage: str = "INFORMATION"
    action_type: str = "answer"  # "booking_confirmed" | "closure" | "answer" | "clarify" | "escalate"
    answer_goal: str = ""
    should_ask_question: bool = False
    question_to_customer: Optional[str] = None
    should_close: bool = False
    is_delta_only: bool = True
    confirmed_slots: dict[str, Any] = Field(default_factory=dict)
    known_facts_summary: str = ""
    required_sections: list[str] = Field(default_factory=list)


class ResponsePlanner:
    @staticmethod
    def create_plan(
        state: ConversationState,
        signals: ExtractedSignals,
        decision: RetrievalDecision,
        latest_message: str,
        strategy_mode: str = "answer",
    ) -> ResponsePlan:
        """
        Build an authoritative ResponsePlan for the current turn.
        """
        confirmed_slots = state.confirmed_slots or {}
        pref_date = confirmed_slots.get("preferred_date")
        pref_time = confirmed_slots.get("preferred_time")

        # ── Case 1: Booking / Schedule Confirmed ───────────────────────────────
        if state.stage == ConversationStage.ACTION_CONFIRMED or (
            signals.is_confirmation and (pref_date or pref_time)
        ):
            slot_desc_parts = []
            if pref_date:
                slot_desc_parts.append(f"date: {pref_date}")
            if pref_time:
                slot_desc_parts.append(f"time: {pref_time}")
            slot_desc = ", ".join(slot_desc_parts) or "your requested time"

            logger.info("[RESPONSE_PLANNER] action_type=booking_confirmed | slots=%s", slot_desc)
            return ResponsePlan(
                intent="booking_confirmation",
                conversation_stage=ConversationStage.ACTION_CONFIRMED.value,
                action_type="booking_confirmed",
                answer_goal=(
                    f"Concisely confirm that the appointment/service is scheduled for {slot_desc}. "
                    "Confirm that the team will arrive or follow up as scheduled. "
                    "CRITICAL: Do NOT re-pitch the service specifications, features, or price. "
                    "CRITICAL: Do NOT ask if the customer would like to proceed with the booking (they have already confirmed). "
                    "Keep the reply warm, professional, and concise."
                ),
                should_ask_question=False,
                question_to_customer=None,
                should_close=True,
                is_delta_only=True,
                confirmed_slots=confirmed_slots,
                required_sections=["greeting", "confirmation", "closing"],
            )

        # ── Case 2: Conversation Closure / Gratitude ──────────────────────────
        if signals.is_gratitude or state.stage == ConversationStage.CLOSED:
            logger.info("[RESPONSE_PLANNER] action_type=closure | gratitude detected")
            return ResponsePlan(
                intent="gratitude_closure",
                conversation_stage=ConversationStage.CLOSED.value,
                action_type="closure",
                answer_goal=(
                    "Graciously acknowledge the customer's message (e.g. 'You are very welcome!'). "
                    "State that we are here if they ever need anything else in the future. "
                    "CRITICAL: Do NOT ask any follow-up questions or pitch any services. Close cleanly."
                ),
                should_ask_question=False,
                question_to_customer=None,
                should_close=True,
                is_delta_only=True,
                confirmed_slots=confirmed_slots,
                required_sections=["greeting", "acknowledgment", "closing"],
            )

        # ── Case 3: Customer Rejection ("not this", "too expensive") ──────────
        if signals.is_rejection or decision.is_rejection:
            logger.info("[RESPONSE_PLANNER] action_type=rejection_handling")
            return ResponsePlan(
                intent="rejection_alternatives",
                conversation_stage=ConversationStage.INFORMATION.value,
                action_type="answer",
                answer_goal=(
                    "Acknowledge the customer's preference for a different option without being defensive. "
                    "Present ONLY the new alternative options retrieved. "
                    "Do NOT mention or repeat the previously rejected options."
                ),
                should_ask_question=True,
                question_to_customer="Please let us know if any of these alternatives better match what you are looking for.",
                should_close=False,
                is_delta_only=True,
                confirmed_slots=confirmed_slots,
                required_sections=["greeting", "alternative_options", "closing"],
            )

        # ── Case 4: Continuation ("what else?", "show me more") ───────────────
        if signals.is_continuation or decision.is_continuation:
            logger.info("[RESPONSE_PLANNER] action_type=continuation")
            return ResponsePlan(
                intent="catalog_continuation",
                conversation_stage=ConversationStage.INFORMATION.value,
                action_type="answer",
                answer_goal=(
                    "Present ONLY the newly retrieved additional options/services. "
                    "CRITICAL: Do NOT repeat the descriptions, specs, or prices of items that were already shown in prior messages."
                ),
                should_ask_question=False,
                question_to_customer=None,
                should_close=False,
                is_delta_only=True,
                confirmed_slots=confirmed_slots,
                required_sections=["greeting", "additional_options", "closing"],
            )

        # ── Case 5: Standard Inquiry (Initial or Follow-up) ───────────────────
        # Determine if customer already provided schedule or if we need one
        has_time_slot = bool(pref_date or pref_time)
        ask_q = not has_time_slot and strategy_mode != "escalate"

        logger.info("[RESPONSE_PLANNER] action_type=answer | default informational plan")
        return ResponsePlan(
            intent=state.current_intent or "informational",
            conversation_stage=state.stage.value,
            action_type="answer",
            answer_goal=(
                "Answer the customer's specific inquiry directly using verified evidence. "
                "Keep the response focused strictly on what was asked. "
                "Do NOT dump unrelated catalog information."
            ),
            should_ask_question=ask_q,
            question_to_customer=(
                "Please let us know if you would like to proceed or if you have any questions." if ask_q else None
            ),
            should_close=False,
            is_delta_only=True,
            confirmed_slots=confirmed_slots,
            required_sections=["greeting", "direct_answer", "closing"],
        )
