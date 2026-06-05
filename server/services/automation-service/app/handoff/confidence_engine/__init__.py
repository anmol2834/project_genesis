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
"""

import logging
from typing import Optional
from app.handoff.models import ConfidenceSignal

logger = logging.getLogger("automation-service.handoff.confidence")


class ConfidenceEngine:
    """
    Multi-signal confidence fusion engine.
    Tenant-aware, feedback-adjustable, observable.
    """
    
    def __init__(self):
        # Weights can be adjusted per-tenant via learning engine
        self.base_weights = {
            'retrieval': 0.30,
            'llm': 0.20,
            'guard': 0.15,
            'intent': 0.10,
            'memory': 0.10,
            'entity': 0.10,
            'historical': 0.05,
        }
    
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
        
        Returns ConfidenceSignal with breakdown + final score.
        """
        signal = ConfidenceSignal()
        
        # ── Retrieval Confidence ──────────────────────────────────────
        # Based on: top score, count, diversity
        signal.retrieval_confidence = self._compute_retrieval_confidence(
            retrieval_chunks,
            retrieval_top_score,
            retrieval_count,
        )
        
        # ── LLM Confidence ────────────────────────────────────────────
        # Use LLM self-reported confidence, but adjust for status
        signal.llm_confidence = llm_confidence if llm_status == "success" else 0.0
        
        # ── Hallucination Guard Score ─────────────────────────────────
        # 1.0 if passed, reduced if failed
        signal.hallucination_guard_score = 1.0 if guard_passed else 0.3
        
        # Adjust based on hallucination risk
        if hallucination_risk == "high":
            signal.hallucination_guard_score = min(signal.hallucination_guard_score, 0.2)
        elif hallucination_risk == "medium":
            signal.hallucination_guard_score = min(signal.hallucination_guard_score, 0.6)
        
        # ── Intent Confidence ─────────────────────────────────────────
        signal.intent_confidence = intent_confidence
        
        # Boost for high-confidence intents
        if intent_value in ("pricing", "interest", "support") and intent_confidence > 0.80:
            signal.intent_confidence = min(1.0, intent_confidence + 0.10)
        
        # ── Memory Continuity Score ───────────────────────────────────
        # Higher if conversation has context
        signal.memory_continuity_score = self._compute_memory_score(
            memory_turn_count,
            is_continuation,
        )
        
        # ── Entity Resolution Score ───────────────────────────────────
        # Penalize if entities failed to resolve
        signal.entity_resolution_score = 0.5 if entity_resolution_failed else 1.0
        
        # Boost if entities extracted successfully
        if entities_extracted and entities_extracted.get("product_name"):
            signal.entity_resolution_score = 1.0
        
        # ── Compute Final Confidence ──────────────────────────────────
        signal.final_confidence = signal.compute_final()
        
        # ── Historical Adjustment ─────────────────────────────────────
        # If this user has low historical success, be more conservative
        if historical_avg_score is not None and historical_avg_score < 0.40:
            signal.final_confidence *= 0.90  # 10% penalty
        elif historical_avg_score is not None and historical_avg_score > 0.75:
            signal.final_confidence = min(1.0, signal.final_confidence * 1.05)  # 5% boost
        
        logger.debug(
            "Confidence computed | user=%s final=%.2f retrieval=%.2f llm=%.2f guard=%.2f intent=%.2f",
            user_id[:8], signal.final_confidence, signal.retrieval_confidence,
            signal.llm_confidence, signal.hallucination_guard_score, signal.intent_confidence,
        )
        
        return signal
    
    def _compute_retrieval_confidence(
        self,
        chunks: list,
        top_score: float,
        count: int,
    ) -> float:
        """
        Compute retrieval confidence from chunk quality signals.
        
        High confidence: top_score > 0.80, count >= 5, diverse sources
        Medium confidence: top_score > 0.60, count >= 3
        Low confidence: top_score < 0.40 or count < 2
        """
        if not chunks or count == 0:
            return 0.0
        
        # Base confidence from top score
        conf = top_score
        
        # Boost for sufficient count
        if count >= 5:
            conf = min(1.0, conf + 0.10)
        elif count >= 3:
            conf = min(1.0, conf + 0.05)
        
        # Penalize if too few chunks
        if count < 2:
            conf *= 0.70
        
        # Check diversity (different chunk types)
        chunk_types = set(c.get("chunk_type", "unknown") for c in chunks)
        if len(chunk_types) >= 3:
            conf = min(1.0, conf + 0.05)
        
        return max(0.0, min(1.0, conf))
    
    def _compute_memory_score(
        self,
        turn_count: int,
        is_continuation: bool,
    ) -> float:
        """
        Compute memory continuity score.
        
        Higher score if conversation has history and query is a continuation.
        """
        if turn_count == 0:
            return 0.80  # First message — no history, but not a penalty
        
        if is_continuation:
            return 1.0  # Strong continuity signal
        
        # Has history but not a clear continuation
        if turn_count >= 3:
            return 0.90
        else:
            return 0.85
    
    def should_escalate_on_confidence(
        self,
        signal: ConfidenceSignal,
        send_threshold: float,
        skip_threshold: float,
    ) -> tuple[bool, str]:
        """
        Determine if confidence is too low and requires escalation.
        
        Returns: (should_escalate, reason)
        """
        final = signal.final_confidence
        
        # Very low confidence → escalate
        if final < skip_threshold:
            return True, f"confidence_too_low:{final:.2f}"
        
        # Low confidence but valid reply → store draft or escalate
        if final < send_threshold:
            # Check if ANY critical signal failed
            if signal.hallucination_guard_score < 0.5:
                return True, "hallucination_guard_failed"
            if signal.retrieval_confidence < 0.30:
                return True, "retrieval_confidence_too_low"
            if signal.llm_confidence < 0.40:
                return True, "llm_confidence_too_low"
            
            # Low but not critical → draft (not escalate)
            return False, f"low_confidence:{final:.2f}_draft"
        
        # Confidence acceptable
        return False, "confidence_acceptable"
