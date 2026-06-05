"""
Handoff - Orchestrator
=======================
Priority-aware confidence-based handoff decision engine.
Determines whether to send AI response or escalate to human.

Priority integration:
  P0 (critical) → always escalate immediately
  P1 (high)     → lower confidence threshold for escalation
  P2 (medium)   → standard thresholds
  P3 (low)      → higher tolerance for AI response
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.core.config import get_config
from app.observability import get_logger

logger = get_logger(__name__)


class HandoffOrchestrator:
    """
    Priority-aware handoff decision orchestration engine.
    Analyzes confidence, risk, priority, and context to decide automation vs human handoff.
    """

    def __init__(self):
        self.config = get_config()
        # Base thresholds — overridden by priority
        self._base_send_threshold = 0.55
        self._base_skip_threshold = 0.25

    async def make_decision(
        self,
        intelligence: Dict[str, Any],
        retrieval: Dict[str, Any],
        llm_result: Dict[str, Any],
        memory: Dict[str, Any],
        trace_id: str,
        priority: int = 2,
        priority_reason: str = "",
    ) -> Dict[str, Any]:
        """
        Make priority-aware handoff decision.

        Priority effects:
          P0 → immediate escalation, no AI response sent
          P1 → lowered confidence threshold (0.70 required to send)
          P2 → standard (0.55 to send)
          P3 → relaxed (0.45 to send)

        Returns:
        {
            "action": "send"|"skip"|"draft"|"escalate",
            "final_confidence": float,
            "escalation_reason": Optional[str],
            "escalation_priority": Optional[str],
            "should_send": bool,
            "priority": str,
        }
        """
        from app.core.tenant_context import Priority

        try:
            # ── P0: Immediate escalation — no LLM response ────────────────
            if priority == Priority.P0_CRITICAL:
                logger.warning(
                    "P0 CRITICAL — immediate escalation | reason=%s",
                    priority_reason, trace_id=trace_id,
                )
                return {
                    "action":             "escalate",
                    "final_confidence":   0.0,
                    "escalation_reason":  f"p0_critical_{priority_reason}",
                    "escalation_priority": "critical",
                    "should_send":        False,
                    "priority":           "critical",
                }

            # ── Calculate confidence ──────────────────────────────────────
            final_confidence = self._calculate_final_confidence(
                intelligence, retrieval, llm_result
            )

            # ── Check escalation triggers (priority-aware) ────────────────
            escalation = self._check_escalation_triggers(
                intelligence, llm_result, final_confidence, priority
            )

            if escalation["should_escalate"]:
                return {
                    "action":             "escalate",
                    "final_confidence":   final_confidence,
                    "escalation_reason":  escalation["reason"],
                    "escalation_priority": escalation["priority"],
                    "should_send":        False,
                    "priority":           Priority.label(priority),
                }

            # ── Priority-aware send threshold ─────────────────────────────
            send_threshold = {
                Priority.P1_HIGH:   0.70,   # P1 requires higher confidence to send
                Priority.P2_MEDIUM: self._base_send_threshold,
                Priority.P3_LOW:    0.45,   # P3 accepts lower confidence
            }.get(priority, self._base_send_threshold)

            skip_threshold = {
                Priority.P1_HIGH:   0.35,
                Priority.P2_MEDIUM: self._base_skip_threshold,
                Priority.P3_LOW:    0.20,
            }.get(priority, self._base_skip_threshold)

            if final_confidence >= send_threshold:
                action = "send"
                should_send = True
                esc_reason = None
                esc_priority = None
            elif final_confidence < skip_threshold:
                action = "escalate"
                should_send = False
                esc_reason = "low_confidence"
                esc_priority = "medium" if priority <= Priority.P1_HIGH else "low"
            else:
                action = "draft"
                should_send = False
                esc_reason = "medium_confidence"
                esc_priority = "low"

            decision = {
                "action":             action,
                "final_confidence":   final_confidence,
                "escalation_reason":  esc_reason,
                "escalation_priority": esc_priority,
                "should_send":        should_send,
                "priority":           Priority.label(priority),
            }

            logger.info(
                "Handoff decision | action=%s confidence=%.2f priority=%s",
                action, final_confidence, Priority.label(priority),
                trace_id=trace_id,
            )
            return decision

        except Exception as e:
            logger.error("Handoff decision failed: %s", e, trace_id=trace_id, exc_info=True)
            return {
                "action":             "escalate",
                "final_confidence":   0.0,
                "escalation_reason":  "decision_error",
                "escalation_priority": "high",
                "should_send":        False,
                "priority":           "high",
                "error":              str(e),
            }
    
    def _calculate_final_confidence(
        self,
        intelligence: Any,
        retrieval: Dict,
        llm_result: Dict
    ) -> float:
        """Calculate final confidence score (handles both dict and Pydantic dataclass)."""
        # Extract intent confidence safely — handles EnterpriseIntelligenceResult and plain dict
        if isinstance(intelligence, dict):
            intent_confidence = intelligence.get("confidence", 0.5)
        else:
            # Pydantic dataclass / EnterpriseIntelligenceResult
            conv = getattr(intelligence, "conversation_analysis", None)
            if conv:
                intent_confidence = getattr(conv, "intent_confidence", 0.5)
            else:
                intent_confidence = getattr(intelligence, "confidence", 0.5) or 0.5

        retrieval_confidence = retrieval.get("retrieval_confidence", 0.5)
        generation_confidence = llm_result.get("confidence", 0.5)
        grounding_score = llm_result.get("grounding_score", 0.5)

        if llm_result.get("hallucination_detected", False):
            return min(0.3, generation_confidence * 0.5)

        final_confidence = (
            intent_confidence    * 0.20 +
            retrieval_confidence * 0.30 +
            generation_confidence * 0.30 +
            grounding_score      * 0.20
        )
        return min(0.95, max(0.05, final_confidence))

    def _check_escalation_triggers(
        self,
        intelligence: Any,
        llm_result: Dict,
        confidence: float,
        priority: int = 2,
    ) -> Dict[str, Any]:
        """Check for conditions requiring human escalation (priority-aware)."""
        from app.core.tenant_context import Priority

        pre_grounding = llm_result.get("pre_gen_grounding", {})
        if pre_grounding.get("escalate"):
            return {"should_escalate": True, "reason": "grounding_confidence_too_low",
                    "priority": "high"}

        if pre_grounding.get("pricing_conflicts", 0) > 0:
            return {"should_escalate": True, "reason": "pricing_conflict_detected",
                    "priority": "medium"}

        if priority <= Priority.P1_HIGH and llm_result.get("fallback_tier", 1) >= 3:
            return {"should_escalate": True, "reason": "llm_fallback_tier_high",
                    "priority": "high"}

        # Extract intent — handle both dict and dataclass
        if isinstance(intelligence, dict):
            intent = intelligence.get("intent", "") or ""
            primary = intelligence.get("primary_intents", [])
            if primary:
                first = primary[0]
                intent = (first.get("type", "") if isinstance(first, dict)
                          else str(getattr(first, "type", ""))) or intent
            risk_level = intelligence.get("risk_level", "low")
        else:
            primary = getattr(intelligence, "primary_intents", []) or []
            if primary:
                t = getattr(primary[0], "type", "")
                # Enum value (e.g. IntentType.REFUND_REQUEST → "refund_request")
                intent = getattr(t, "value", str(t))
            else:
                intent = ""
            risk_level = "low"

        high_risk_intents = {
            "complaint", "refund_request", "legal_issue",
            "data_privacy", "account_closure", "billing_dispute",
        }
        if intent.lower() in high_risk_intents:
            return {"should_escalate": True, "reason": f"high_risk_intent_{intent}",
                    "priority": "high"}

        if risk_level == "high":
            return {"should_escalate": True, "reason": "high_risk_level", "priority": "high"}

        if llm_result.get("hallucination_detected"):
            return {"should_escalate": True, "reason": "hallucination_detected",
                    "priority": "medium"}

        confidence_floor = {
            Priority.P1_HIGH:   0.35,
            Priority.P2_MEDIUM: 0.25,
            Priority.P3_LOW:    0.15,
        }.get(priority, 0.25)

        if confidence < confidence_floor:
            return {"should_escalate": True, "reason": "very_low_confidence",
                    "priority": "medium"}

        return {"should_escalate": False, "reason": None, "priority": None}


# Global instance
_handoff_orchestrator: Optional[HandoffOrchestrator] = None


def get_handoff_orchestrator() -> HandoffOrchestrator:
    """Get global handoff orchestrator"""
    global _handoff_orchestrator
    if _handoff_orchestrator is None:
        _handoff_orchestrator = HandoffOrchestrator()
    return _handoff_orchestrator


__all__ = ["HandoffOrchestrator", "get_handoff_orchestrator"]
