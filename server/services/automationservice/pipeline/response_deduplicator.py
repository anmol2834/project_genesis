"""
automationservice — Response Deduplicator & Repetition Guard
============================================================
Detects and prevents repetitive responses across conversational turns.
If an assistant response is substantially identical to a recent prior turn,
it replaces or deduplicates the response to guarantee fresh, delta-based prose.
"""
from __future__ import annotations

import re
import hashlib
import logging
from typing import Any

from services.conversation_state import ConversationState, ConversationStage
from pipeline.slot_tracker import ExtractedSignals
from pipeline.response_planner import ResponsePlan

logger = logging.getLogger("automationservice.response_deduplicator")


def compute_response_hash(text: str) -> str:
    """Normalized SHA-256 hash of response text."""
    normalized = " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute token-level Jaccard similarity between two texts."""
    words_a = set(re.sub(r"[^\w\s]", "", text_a.lower()).split())
    words_b = set(re.sub(r"[^\w\s]", "", text_b.lower()).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a.intersection(words_b)
    union = words_a.union(words_b)
    return len(intersection) / len(union) if union else 0.0


class ResponseDeduplicator:
    @staticmethod
    def inspect_and_deduplicate(
        proposed_body: str,
        messages: list[dict[str, Any]],
        state: ConversationState,
        plan: ResponsePlan,
        signals: ExtractedSignals,
        business_name: str = "Our Team",
    ) -> str:
        """
        Validates proposed response against recent assistant messages in the thread.
        If near-duplicate is detected, replaces with an appropriate delta response.
        """
        if not messages:
            return proposed_body

        # Find the latest assistant message
        recent_assistant_messages = [
            m.get("content") or m.get("snippet") or ""
            for m in messages
            if m.get("direction") in ("outgoing", "sent") or m.get("sender_type") == "assistant"
        ]

        if not recent_assistant_messages:
            return proposed_body

        last_assistant_msg = recent_assistant_messages[-1].strip()
        similarity = compute_jaccard_similarity(proposed_body, last_assistant_msg)

        logger.info(
            "[DEDUPLICATOR] similarity with last assistant message: %.2f (plan_action=%s)",
            similarity, plan.action_type
        )

        # ── Check if duplicate pitch on booking confirmation ──────────────────
        if (signals.is_confirmation or plan.action_type == "booking_confirmed") and (
            similarity > 0.65 or "would you like to proceed" in proposed_body.lower()
        ):
            slots = state.confirmed_slots or {}
            date_val = slots.get("preferred_date")
            time_val = slots.get("preferred_time")
            
            schedule_parts = []
            if date_val:
                schedule_parts.append(f"{date_val}")
            if time_val:
                schedule_parts.append(f"{time_val}")
            schedule_str = " ".join(schedule_parts) or "your requested time"

            logger.warning(
                "[DEDUPLICATOR] Overwrote repetitive assistant pitch with clean booking confirmation."
            )
            return (
                f"Thank you for confirming your request. "
                f"We are pleased to confirm that your service has been scheduled for {schedule_str}. "
                f"Our team will arrive as scheduled.\n\n"
                f"Best regards,\n{business_name}"
            )

        # ── Check if duplicate pitch on gratitude / closure ───────────────────
        if (signals.is_gratitude or plan.action_type == "closure") and similarity > 0.50:
            logger.warning(
                "[DEDUPLICATOR] Overwrote repetitive assistant pitch with clean closure acknowledgment."
            )
            return (
                f"You are very welcome! "
                f"If you have any further questions or need assistance in the future, please feel free to reach out.\n\n"
                f"Best regards,\n{business_name}"
            )

        return proposed_body
