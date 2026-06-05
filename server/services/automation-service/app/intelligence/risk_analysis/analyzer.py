"""
Risk Analysis Engine
====================
Detects dangerous queries requiring human intervention.

Risk Categories:
- Legal questions (compliance, privacy, GDPR)
- Billing disputes (refund, chargeback)
- Complaints (angry customer, frustrated)
- Unsupported claims (no data available)
- Hallucination zones (missing context)
- Technical complexity (requires expert)

Performance: <5ms target
"""

import re
import logging
from typing import Optional, Any
from app.intelligence.models.intelligence_result import RiskAnalysis

logger = logging.getLogger(__name__)


# ── Risk Keyword Patterns ─────────────────────────────────────────────────────
LEGAL_KEYWORDS = {
    "legal", "lawyer", "attorney", "court", "sue", "lawsuit", "litigation",
    "compliance", "regulation", "gdpr", "privacy", "data protection",
    "copyright", "trademark", "patent", "intellectual property",
    "contract", "agreement", "terms", "liability", "indemnity"
}

BILLING_KEYWORDS = {
    "refund", "chargeback", "dispute", "overcharge", "wrong charge",
    "billing error", "payment issue", "invoice wrong", "charged twice",
    "unauthorized charge", "fraudulent", "scam", "money back"
}

COMPLAINT_KEYWORDS = {
    "complaint", "angry", "furious", "frustrated", "disappointed",
    "terrible", "worst", "horrible", "awful", "disgusting",
    "unacceptable", "fed up", "sick of", "done with",
    "manager", "supervisor", "escalate", "corporate"
}

ANGER_INDICATORS = {
    "!!!", "wtf", "ridiculous", "pathetic", "joke", "disaster",
    "incompetent", "useless", "waste of time", "waste of money"
}

URGENT_KEYWORDS = {
    "urgent", "emergency", "asap", "immediately", "right now",
    "critical", "priority", "today", "now", "hurry"
}

TECHNICAL_COMPLEXITY = {
    "api", "integration", "webhook", "oauth", "authentication",
    "architecture", "deployment", "infrastructure", "database",
    "custom development", "technical requirement", "specification"
}


class RiskAnalyzer:
    """
    Analyzes queries for risk and determines if human intervention needed.
    """
    
    def analyze(
        self,
        content: str,
        qu_result: Any,
        memory: Optional[Any]
    ) -> RiskAnalysis:
        """
        Analyze query for risk factors.
        
        Args:
            content: Raw message content
            qu_result: Query understanding result
            memory: Thread memory
            
        Returns:
            RiskAnalysis with risk level and categories
        """
        clean = content.lower()
        
        # Initialize risk signals
        signals = {}
        risk_categories = []
        
        # ── Check Legal Risk ──────────────────────────────────────────────
        is_legal = self._check_keywords(clean, LEGAL_KEYWORDS)
        signals["legal"] = 1.0 if is_legal else 0.0
        
        if is_legal:
            risk_categories.append("legal")
        
        # ── Check Billing Risk ────────────────────────────────────────────
        is_billing = self._check_keywords(clean, BILLING_KEYWORDS)
        signals["billing"] = 1.0 if is_billing else 0.0
        
        if is_billing:
            risk_categories.append("billing")
        
        # ── Check Complaint Risk ──────────────────────────────────────────
        is_complaint = (
            self._check_keywords(clean, COMPLAINT_KEYWORDS) or
            qu_result.intent.value == "complaint"
        )
        signals["complaint"] = 1.0 if is_complaint else 0.0
        
        if is_complaint:
            risk_categories.append("complaint")
        
        # ── Check Anger Level ─────────────────────────────────────────────
        is_angry = self._check_keywords(clean, ANGER_INDICATORS)
        signals["anger"] = 1.0 if is_angry else 0.0
        
        if is_angry:
            risk_categories.append("angry_customer")
        
        # ── Check Urgency ─────────────────────────────────────────────────
        is_urgent = (
            self._check_keywords(clean, URGENT_KEYWORDS) or
            qu_result.urgency.value in ["high", "critical"]
        )
        signals["urgency"] = 1.0 if is_urgent else 0.0
        
        if is_urgent:
            risk_categories.append("high_urgency")
        
        # ── Check Technical Complexity ────────────────────────────────────
        is_complex = self._check_keywords(clean, TECHNICAL_COMPLEXITY)
        signals["technical_complexity"] = 1.0 if is_complex else 0.0
        
        if is_complex:
            risk_categories.append("technical_complexity")
        
        # ── Check Hallucination Risk ──────────────────────────────────────
        has_hallucination_risk = self._check_hallucination_risk(
            qu_result, memory
        )
        signals["hallucination"] = 1.0 if has_hallucination_risk else 0.0
        
        if has_hallucination_risk:
            risk_categories.append("hallucination_risk")
        
        # ── Check Missing Data Risk ───────────────────────────────────────
        has_missing_data = self._check_missing_data_risk(qu_result)
        signals["missing_data"] = 1.0 if has_missing_data else 0.0
        
        if has_missing_data:
            risk_categories.append("missing_data")
        
        # ── Compute Risk Level ────────────────────────────────────────────
        risk_level, requires_human, escalation_reason, escalation_priority = (
            self._compute_risk_level(signals, risk_categories)
        )
        
        # ── Build Result ──────────────────────────────────────────────────
        confidence = self._compute_confidence(signals)
        
        return RiskAnalysis(
            risk_level=risk_level,
            requires_human=requires_human,
            risk_categories=risk_categories,
            is_legal_query=signals["legal"] > 0,
            is_billing_query=signals["billing"] > 0,
            is_refund_query="refund" in clean or "chargeback" in clean,
            is_complaint=signals["complaint"] > 0,
            is_angry_customer=signals["anger"] > 0,
            has_hallucination_risk=signals["hallucination"] > 0,
            has_missing_data_risk=signals["missing_data"] > 0,
            has_unsupported_claim_risk=has_missing_data or has_hallucination_risk,
            escalation_reason=escalation_reason,
            escalation_priority=escalation_priority,
            confidence=confidence,
            signals=signals
        )
    
    # ══════════════════════════════════════════════════════════════════════
    # Private Helper Methods
    # ══════════════════════════════════════════════════════════════════════
    
    def _check_keywords(self, text: str, keywords: set) -> bool:
        """Check if text contains any keywords from set."""
        return any(keyword in text for keyword in keywords)
    
    def _check_hallucination_risk(
        self,
        qu_result: Any,
        memory: Optional[Any]
    ) -> bool:
        """
        Check if query has high hallucination risk.
        
        High risk scenarios:
        - Very low intent confidence (<0.5)
        - Vague continuation without memory
        - Complex multi-intent without entities
        """
        # Low confidence
        if qu_result.confidence < 0.5:
            return True
        
        # Continuation without memory
        if qu_result.conversation_type == "continuation" and not memory:
            return True
        
        # Multi-intent without clear entities
        if (qu_result.sub_intent == "multi_intent" and
            (not qu_result.entities or len(qu_result.entities) == 0)):
            return True
        
        # Unknown intent with low confidence
        if qu_result.intent.value == "unknown" and qu_result.confidence < 0.6:
            return True
        
        return False
    
    def _check_missing_data_risk(self, qu_result: Any) -> bool:
        """
        Check if query might require data we don't have.
        
        High risk scenarios:
        - Pricing questions with unknown products
        - Technical specs for unrecognized products
        - Comparison without clear entities
        """
        intent = qu_result.intent.value
        
        # Pricing without product
        if intent == "pricing":
            if not qu_result.entities or not qu_result.entities.get("product_name"):
                return True
        
        # Question without clear topic
        if intent == "question":
            if not qu_result.entities or len(qu_result.entities) == 0:
                return True
        
        # Support without context
        if intent == "support":
            if not qu_result.entities:
                return True
        
        return False
    
    def _compute_risk_level(
        self,
        signals: dict,
        risk_categories: list
    ) -> tuple:
        """
        Compute risk level and escalation requirements.
        
        Returns:
            (risk_level, requires_human, escalation_reason, escalation_priority)
        """
        
        # ── CRITICAL Risk ─────────────────────────────────────────────────
        # Legal or refund/chargeback = always requires human
        if signals.get("legal", 0) > 0:
            return (
                "critical",
                True,
                "Legal query detected - requires legal team review",
                "critical"
            )
        
        if signals.get("billing", 0) > 0:
            return (
                "critical",
                True,
                "Billing dispute detected - requires finance team review",
                "critical"
            )
        
        # ── HIGH Risk ─────────────────────────────────────────────────────
        # Angry complaint = requires human
        if signals.get("anger", 0) > 0 and signals.get("complaint", 0) > 0:
            return (
                "high",
                True,
                "Angry customer complaint - requires immediate attention",
                "high"
            )
        
        # Complex technical + urgent
        if signals.get("technical_complexity", 0) > 0 and signals.get("urgency", 0) > 0:
            return (
                "high",
                True,
                "Urgent technical complexity - requires expert review",
                "high"
            )
        
        # ── MEDIUM Risk ───────────────────────────────────────────────────
        # Regular complaint
        if signals.get("complaint", 0) > 0:
            return (
                "medium",
                False,
                "Customer complaint - consider escalation if unresolved",
                "medium"
            )
        
        # Hallucination risk
        if signals.get("hallucination", 0) > 0:
            return (
                "medium",
                False,
                "High hallucination risk - use conservative response",
                "medium"
            )
        
        # Missing data risk
        if signals.get("missing_data", 0) > 0:
            return (
                "medium",
                False,
                "Missing data risk - may need to handoff if data unavailable",
                "medium"
            )
        
        # Technical complexity
        if signals.get("technical_complexity", 0) > 0:
            return (
                "medium",
                False,
                "Technical complexity - escalate if AI cannot resolve",
                "medium"
            )
        
        # ── LOW Risk ──────────────────────────────────────────────────────
        return ("low", False, None, "low")
    
    def _compute_confidence(self, signals: dict) -> float:
        """
        Compute confidence in risk assessment.
        
        High confidence scenarios:
        - Clear keyword matches
        - Multiple risk signals
        
        Low confidence scenarios:
        - Borderline cases
        - Single weak signal
        """
        total_signals = sum(1 for v in signals.values() if v > 0)
        
        # Strong signals = high confidence
        if total_signals >= 3:
            return 0.95
        
        if total_signals == 2:
            return 0.85
        
        if total_signals == 1:
            # Check if it's a strong signal
            if signals.get("legal", 0) > 0 or signals.get("billing", 0) > 0:
                return 0.90
            
            return 0.75
        
        # No risk detected
        return 0.80
