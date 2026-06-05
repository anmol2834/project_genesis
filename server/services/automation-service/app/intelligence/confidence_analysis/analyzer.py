"""
Confidence Analysis Engine
===========================
Multi-signal confidence fusion for final confidence scoring.

Signals:
- Intent confidence (30%)
- Entity confidence (20%)
- Continuation confidence (15%)
- Memory confidence (15%)
- Language confidence (10%)
- Query plan confidence (10%)

Adjustments:
- Reduce if high risk detected
- Boost if strong memory context
- Calibrate based on signal quality

Performance: <5ms target
"""

import logging
from typing import Optional, Any, Dict
from app.intelligence.models.intelligence_result import (
    ConfidenceAnalysis, ContinuationResolution, QueryPlan, RiskAnalysis
)

logger = logging.getLogger(__name__)


# ── Signal Weights ────────────────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "intent": 0.30,
    "entity": 0.20,
    "continuation": 0.15,
    "memory": 0.15,
    "language": 0.10,
    "query_plan": 0.10
}


class ConfidenceAnalyzer:
    """
    Multi-signal confidence fusion analyzer.
    Combines multiple confidence signals into final score.
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize confidence analyzer.
        
        Args:
            weights: Custom signal weights (optional)
        """
        self.weights = weights or DEFAULT_WEIGHTS.copy()
    
    def analyze(
        self,
        qu_result: Any,
        continuation: ContinuationResolution,
        memory_context: Optional[Dict],
        query_plan: QueryPlan,
        risk: RiskAnalysis
    ) -> ConfidenceAnalysis:
        """
        Compute final confidence score.
        
        Args:
            qu_result: Query understanding result
            continuation: Continuation resolution
            memory_context: Memory enrichment context
            query_plan: Query plan
            risk: Risk analysis
            
        Returns:
            ConfidenceAnalysis with final score and breakdown
        """
        
        # ── Extract Signal Scores ─────────────────────────────────────────
        intent_confidence = qu_result.confidence
        
        entity_confidence = self._compute_entity_confidence(qu_result)
        
        continuation_confidence = (
            continuation.confidence if continuation.resolved else 1.0
        )
        
        memory_confidence = (
            memory_context.get("confidence", 0.0) if memory_context else 0.0
        )
        
        language_confidence = self._compute_language_confidence(qu_result)
        
        query_plan_confidence = query_plan.plan_confidence
        
        # ── Compute Weighted Average ──────────────────────────────────────
        final_confidence = (
            self.weights["intent"] * intent_confidence +
            self.weights["entity"] * entity_confidence +
            self.weights["continuation"] * continuation_confidence +
            self.weights["memory"] * memory_confidence +
            self.weights["language"] * language_confidence +
            self.weights["query_plan"] * query_plan_confidence
        )
        
        # ── Apply Risk Adjustment ─────────────────────────────────────────
        final_confidence = self._apply_risk_adjustment(
            final_confidence, risk
        )
        
        # ── Apply Memory Boost ────────────────────────────────────────────
        final_confidence = self._apply_memory_boost(
            final_confidence, memory_context, continuation
        )
        
        # ── Clamp to [0, 1] ───────────────────────────────────────────────
        final_confidence = max(0.0, min(1.0, final_confidence))
        
        # ── Build Breakdown ───────────────────────────────────────────────
        breakdown = self._build_breakdown(
            intent_confidence,
            entity_confidence,
            continuation_confidence,
            memory_confidence,
            language_confidence,
            query_plan_confidence,
            final_confidence
        )
        
        return ConfidenceAnalysis(
            final_confidence=final_confidence,
            intent_confidence=intent_confidence,
            entity_confidence=entity_confidence,
            continuation_confidence=continuation_confidence,
            memory_confidence=memory_confidence,
            language_confidence=language_confidence,
            query_plan_confidence=query_plan_confidence,
            weights=self.weights.copy(),
            breakdown=breakdown,
            source="multi_signal_fusion"
        )
    
    # ══════════════════════════════════════════════════════════════════════
    # Private Helper Methods
    # ══════════════════════════════════════════════════════════════════════
    
    def _compute_entity_confidence(self, qu_result: Any) -> float:
        """
        Compute entity extraction confidence.
        
        High confidence:
        - Clear product name with model number
        - Multiple entities extracted
        - Specific features identified
        
        Low confidence:
        - Generic terms only
        - No entities
        - Vague references
        """
        if not qu_result.entities or len(qu_result.entities) == 0:
            return 0.3
        
        entity_count = len(qu_result.entities)
        
        # Check for high-value entities
        has_product = bool(qu_result.entities.get("product_name"))
        has_category = bool(qu_result.entities.get("category"))
        has_features = bool(qu_result.entities.get("features"))
        
        # Base score on entity count
        if entity_count >= 3:
            base_score = 0.9
        elif entity_count == 2:
            base_score = 0.8
        else:
            base_score = 0.6
        
        # Boost for high-value entities
        if has_product:
            base_score += 0.1
        
        if has_category:
            base_score += 0.05
        
        if has_features:
            base_score += 0.05
        
        return min(1.0, base_score)
    
    def _compute_language_confidence(self, qu_result: Any) -> float:
        """
        Compute language detection confidence.
        
        High confidence:
        - Clear English or Hindi
        
        Medium confidence:
        - Hinglish (mixed)
        
        Low confidence:
        - Unknown language
        """
        lang = qu_result.language.lower()
        
        if lang == "english":
            return 1.0
        
        if lang == "hindi":
            return 0.95
        
        if lang == "hinglish":
            return 0.85
        
        return 0.5
    
    def _apply_risk_adjustment(
        self,
        confidence: float,
        risk: RiskAnalysis
    ) -> float:
        """
        Adjust confidence based on risk level.
        
        High risk = reduce confidence (be conservative)
        """
        risk_level = risk.risk_level
        
        if risk_level == "critical":
            return confidence * 0.6  # Reduce by 40%
        
        if risk_level == "high":
            return confidence * 0.75  # Reduce by 25%
        
        if risk_level == "medium":
            return confidence * 0.9  # Reduce by 10%
        
        return confidence  # No adjustment for low risk
    
    def _apply_memory_boost(
        self,
        confidence: float,
        memory_context: Optional[Dict],
        continuation: ContinuationResolution
    ) -> float:
        """
        Boost confidence if strong memory context.
        
        Strong memory = increase confidence
        """
        # Strong continuation resolution
        if continuation.resolved and continuation.confidence > 0.8:
            return min(1.0, confidence * 1.1)  # Boost by 10%
        
        # Rich memory context
        if memory_context and memory_context.get("confidence", 0.0) > 0.7:
            return min(1.0, confidence * 1.05)  # Boost by 5%
        
        return confidence
    
    def _build_breakdown(
        self,
        intent_conf: float,
        entity_conf: float,
        continuation_conf: float,
        memory_conf: float,
        language_conf: float,
        query_plan_conf: float,
        final_conf: float
    ) -> str:
        """Build human-readable confidence breakdown."""
        breakdown = (
            f"Final: {final_conf:.2f} | "
            f"Intent: {intent_conf:.2f} (30%) | "
            f"Entity: {entity_conf:.2f} (20%) | "
            f"Continuation: {continuation_conf:.2f} (15%) | "
            f"Memory: {memory_conf:.2f} (15%) | "
            f"Language: {language_conf:.2f} (10%) | "
            f"QueryPlan: {query_plan_conf:.2f} (10%)"
        )
        
        return breakdown
