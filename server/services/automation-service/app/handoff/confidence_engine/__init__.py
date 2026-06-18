"""
Handoff — Confidence Engine
============================
Enterprise multi-signal confidence fusion.
Confidence MUST NOT depend only on LLM.

Signals:
- retrieval quality (chunk scores, count, diversity)
- reranker confidence
- hallucination guard result
- intent confidence
- memory continuity
- entity resolution
- historical feedback

Task 6 fix (R8):
  - __init__ now accepts an optional `weights` dict so HandoffOrchestrator
    can pass confidence_weights without a TypeError.
  - Added calculate_confidence() as an alias that matches the signature
    HandoffOrchestrator.evaluate_handoff() calls.
"""

import logging
from typing import Dict, Optional
from app.handoff.models import ConfidenceSignal

logger = logging.getLogger("automation-service.handoff.confidence")


class ConfidenceEngine:
    """
    Multi-signal confidence fusion engine.
    Tenant-aware, feedback-adjustable, observable.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: Optional override dict for base_weights.
                     Only provided keys are overridden; missing keys keep defaults.
                     Example: {"retrieval": 0.40, "llm": 0.15}
        """
        self.base_weights = {
            "retrieval":  0.30,
            "llm":        0.20,
            "guard":      0.15,
            "intent":     0.10,
            "memory":     0.10,
            "entity":     0.10,
            "historical": 0.05,
        }
        if weights:
            self.base_weights.update(weights)

    # ── Primary API ───────────────────────────────────────────────────────────

    def compute_confidence(
        self,
        # Retrieval signals
        retrieval_chunks: list,
        retrieval_top_score: float,
        retrieval_count: int,
        # LLM signals
        llm_confidence: float,
        llm_status: str,
        hallucination_risk: str,
        # Guard signals
        guard_passed: bool,
        guard_reason: str,
        # Intent signals
        intent_confidence: float,
        intent_value: str,
        # Memory signals
        memory_turn_count: int,
        is_continuation: bool,
        # Entity signals
        entities_extracted: dict,
        entity_resolution_failed: bool,
        # Historical signals
        user_id: str,
        historical_avg_score: Optional[float] = None,
    ) -> ConfidenceSignal:
        """
        Compute final confidence from all available signals.
        Called by HandoffService (the lightweight per-request path).
        Returns ConfidenceSignal with breakdown + final score.
        """
        signal = ConfidenceSignal()

        # Retrieval confidence
        signal.retrieval_confidence = self._compute_retrieval_confidence(
            retrieval_chunks, retrieval_top_score, retrieval_count,
        )

        # LLM confidence
        signal.llm_confidence = llm_confidence if llm_status == "success" else 0.0

        # Hallucination guard score
        signal.hallucination_guard_score = 1.0 if guard_passed else 0.3
        if hallucination_risk == "high":
            signal.hallucination_guard_score = min(signal.hallucination_guard_score, 0.2)
        elif hallucination_risk == "medium":
            signal.hallucination_guard_score = min(signal.hallucination_guard_score, 0.6)

        # Intent confidence
        signal.intent_confidence = intent_confidence
        if intent_value in ("pricing", "interest", "support") and intent_confidence > 0.80:
            signal.intent_confidence = min(1.0, intent_confidence + 0.10)

        # Memory continuity
        signal.memory_continuity_score = self._compute_memory_score(
            memory_turn_count, is_continuation,
        )

        # Entity resolution
        signal.entity_resolution_score = 0.5 if entity_resolution_failed else 1.0
        if entities_extracted and entities_extracted.get("product_name"):
            signal.entity_resolution_score = 1.0

        # Compute final score
        signal.final_confidence = signal.compute_final()

        # Historical adjustment
        if historical_avg_score is not None and historical_avg_score < 0.40:
            signal.final_confidence *= 0.90
        elif historical_avg_score is not None and historical_avg_score > 0.75:
            signal.final_confidence = min(1.0, signal.final_confidence * 1.05)

        logger.debug(
            "Confidence computed | user=%s final=%.2f retrieval=%.2f llm=%.2f "
            "guard=%.2f intent=%.2f",
            user_id[:8], signal.final_confidence, signal.retrieval_confidence,
            signal.llm_confidence, signal.hallucination_guard_score,
            signal.intent_confidence,
        )

        return signal

    def calculate_confidence(
        self,
        retrieval_confidence: float,
        llm_confidence: float,
        hallucination_score: float,
        reranker_confidence: float,
        intent_confidence: float,
        memory_confidence: float,
        historical_feedback: float,
        tenant_id: str,
    ) -> ConfidenceSignal:
        """
        Simplified interface used by HandoffOrchestrator.evaluate_handoff().

        HandoffOrchestrator passes pre-aggregated signal scalars (not raw chunks),
        so this maps them directly onto ConfidenceSignal fields and calls compute_final().

        Returns a ConfidenceSignal with:
            retrieval_confidence      ← retrieval_confidence arg
            llm_confidence            ← llm_confidence arg
            hallucination_guard_score ← hallucination_score arg (1.0 = clean)
            intent_confidence         ← intent_confidence arg
            memory_continuity_score   ← memory_confidence arg
            entity_resolution_score   ← reranker_confidence (best proxy available)
            historical_feedback_score ← historical_feedback arg
        """
        signal = ConfidenceSignal(
            retrieval_confidence=float(retrieval_confidence),
            llm_confidence=float(llm_confidence),
            hallucination_guard_score=float(hallucination_score),
            intent_confidence=float(intent_confidence),
            memory_continuity_score=float(memory_confidence),
            entity_resolution_score=float(reranker_confidence),
            historical_feedback_score=float(historical_feedback),
        )
        signal.final_confidence = signal.compute_final()

        logger.debug(
            "Confidence calculated | tenant=%s final=%.2f",
            tenant_id[:8], signal.final_confidence,
        )
        return signal

    # ── Escalation decision helper ────────────────────────────────────────────

    def should_escalate_on_confidence(
        self,
        signal: ConfidenceSignal,
        send_threshold: float,
        skip_threshold: float,
    ) -> tuple[bool, str]:
        """
        Determine if confidence requires escalation.
        Returns: (should_escalate, reason)
        """
        final = signal.final_confidence

        if final < skip_threshold:
            return True, f"confidence_too_low:{final:.2f}"

        if final < send_threshold:
            if signal.hallucination_guard_score < 0.5:
                return True, "hallucination_guard_failed"
            if signal.retrieval_confidence < 0.30:
                return True, "retrieval_confidence_too_low"
            if signal.llm_confidence < 0.40:
                return True, "llm_confidence_too_low"
            return False, f"low_confidence:{final:.2f}_draft"

        return False, "confidence_acceptable"

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_retrieval_confidence(
        self,
        chunks: list,
        top_score: float,
        count: int,
    ) -> float:
        if not chunks or count == 0:
            return 0.0
        conf = top_score
        if count >= 5:
            conf = min(1.0, conf + 0.10)
        elif count >= 3:
            conf = min(1.0, conf + 0.05)
        if count < 2:
            conf *= 0.70
        chunk_types = set(c.get("chunk_type", "unknown") for c in chunks)
        if len(chunk_types) >= 3:
            conf = min(1.0, conf + 0.05)
        return max(0.0, min(1.0, conf))

    def _compute_memory_score(
        self,
        turn_count: int,
        is_continuation: bool,
    ) -> float:
        if turn_count == 0:
            return 0.80
        if is_continuation:
            return 1.0
        return 0.90 if turn_count >= 3 else 0.85


__all__ = ["ConfidenceEngine"]
