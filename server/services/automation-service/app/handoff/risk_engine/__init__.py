"""
Handoff — Risk Engine
======================
Detects high-risk scenarios requiring human intervention.

Risk Categories:
- Legal threats
- Refund/chargeback
- Angry customers
- Pricing negotiation
- Medical/legal advice
- Data privacy concerns
- Technical support complexity
"""

import re
import logging
from typing import Optional
from app.handoff.models import RiskSignals, RiskCategory

logger = logging.getLogger("automation-service.handoff.risk")


# ── Risk Detection Patterns ──────────────────────────────────────────────────

_LEGAL_THREAT_RE = re.compile(
    r"\b(lawyer|attorney|legal action|sue|court|litigation|law firm|"
    r"consumer protection|file a complaint|regulatory|ombudsman|"
    r"vakil|kanoon|nyaya|adaalat)\b",
    re.IGNORECASE,
)

_REFUND_RE = re.compile(
    r"\b(refund|money back|return|chargeback|dispute|cancel order|"
    r"want my money|paise wapas|refund chahiye)\b",
    re.IGNORECASE,
)

_ANGRY_RE = re.compile(
    r"\b(terrible|awful|worst|horrible|useless|pathetic|disgusted|"
    r"furious|unacceptable|outraged|scam|fraud|rip.?off|cheat|"
    r"bekar|kharab|bakwas|bewakoof)\b",
    re.IGNORECASE,
)

_PRICING_NEGOTIATION_RE = re.compile(
    r"\b(discount|negotiate|better (price|deal|offer)|reduce|lower|"
    r"can you do|best price|final price|competitive|match|"
    r"kam karo|thoda kam|discount milega)\b",
    re.IGNORECASE,
)

_DATA_PRIVACY_RE = re.compile(
    r"\b(privacy|data protection|gdpr|personal information|data breach|"
    r"delete my data|remove my info|stop tracking|meri information)\b",
    re.IGNORECASE,
)

_MEDICAL_ADVICE_RE = re.compile(
    r"\b(diagnose|diagnosis|treatment|prescription|symptom|disease|"
    r"medical condition|health issue|ailment|illness|beemari|ilaaj)\b",
    re.IGNORECASE,
)

_LEGAL_ADVICE_RE = re.compile(
    r"\b(legal advice|legal opinion|contract review|terms and conditions|"
    r"liability|rights|obligations|compliance|kanuni salah)\b",
    re.IGNORECASE,
)

_CHARGEBACK_RE = re.compile(
    r"\b(chargeback|credit card dispute|bank dispute|payment reversal|"
    r"unauthorized charge|fraud claim)\b",
    re.IGNORECASE,
)

_TECHNICAL_COMPLEX_RE = re.compile(
    r"\b(technical issue|not working|bug|error|crash|failure|broken|"
    r"integration|api|setup|configuration|kaam nahi kar raha|"
    r"problem ho raha hai)\b",
    re.IGNORECASE,
)


class RiskEngine:
    """
    Detects high-risk scenarios requiring human intervention.
    Multi-signal risk assessment with category classification.
    """
    
    def analyze_risk(
        self,
        user_message: str,
        ai_reply: Optional[str],
        intent: str,
        sentiment: Optional[str] = None,
        conversation_history: Optional[list] = None,
    ) -> RiskSignals:
        """
        Analyze risk from message content and context.
        
        Returns RiskSignals with categories, level, and reasons.
        """
        signals = RiskSignals()
        combined = f"{user_message} {ai_reply or ''}".lower()
        
        # ── Legal Risk ────────────────────────────────────────────────
        if _LEGAL_THREAT_RE.search(combined):
            signals.risk_categories.append(RiskCategory.LEGAL)
            signals.risk_reasons.append("legal_threat_detected")
            signals.risk_level = max(signals.risk_level, 0.95)
            signals.requires_human = True
        
        # ── Financial Risk ────────────────────────────────────────────
        if _REFUND_RE.search(combined) or _CHARGEBACK_RE.search(combined):
            signals.risk_categories.append(RiskCategory.FINANCIAL)
            signals.risk_reasons.append("refund_or_chargeback_request")
            signals.risk_level = max(signals.risk_level, 0.90)
            signals.requires_human = True
        
        if _PRICING_NEGOTIATION_RE.search(combined):
            signals.risk_categories.append(RiskCategory.FINANCIAL)
            signals.risk_reasons.append("pricing_negotiation")
            signals.risk_level = max(signals.risk_level, 0.70)
            # Negotiation can be handled by AI if confidence is high
            # Don't force requires_human yet
        
        # ── Emotional Risk ────────────────────────────────────────────
        angry_count = len(_ANGRY_RE.findall(combined))
        if angry_count >= 2:
            signals.risk_categories.append(RiskCategory.EMOTIONAL)
            signals.risk_reasons.append(f"angry_customer:{angry_count}_signals")
            signals.risk_level = max(signals.risk_level, 0.85)
            signals.requires_human = True
        elif angry_count == 1:
            signals.risk_categories.append(RiskCategory.EMOTIONAL)
            signals.risk_reasons.append("customer_frustration")
            signals.risk_level = max(signals.risk_level, 0.60)
        
        # ── Compliance Risk ───────────────────────────────────────────
        if _DATA_PRIVACY_RE.search(combined):
            signals.risk_categories.append(RiskCategory.COMPLIANCE)
            signals.risk_reasons.append("data_privacy_concern")
            signals.risk_level = max(signals.risk_level, 0.80)
            signals.requires_human = True
        
        if _MEDICAL_ADVICE_RE.search(combined):
            signals.risk_categories.append(RiskCategory.COMPLIANCE)
            signals.risk_reasons.append("medical_advice_request")
            signals.risk_level = max(signals.risk_level, 0.95)
            signals.requires_human = True
        
        if _LEGAL_ADVICE_RE.search(combined):
            signals.risk_categories.append(RiskCategory.COMPLIANCE)
            signals.risk_reasons.append("legal_advice_request")
            signals.risk_level = max(signals.risk_level, 0.90)
            signals.requires_human = True
        
        # ── Technical Risk ────────────────────────────────────────────
        if _TECHNICAL_COMPLEX_RE.search(combined) and intent in ("support", "complaint"):
            signals.risk_categories.append(RiskCategory.TECHNICAL)
            signals.risk_reasons.append("technical_support_complex")
            signals.risk_level = max(signals.risk_level, 0.65)
            # Technical issues can sometimes be handled by AI
        
        # ── Escalation History Risk ───────────────────────────────────
        # If this conversation has already been escalated, be more conservative
        if conversation_history:
            escalation_count = sum(
                1 for msg in conversation_history
                if msg.get("escalated") or msg.get("human_handled")
            )
            if escalation_count >= 2:
                signals.risk_reasons.append(f"repeated_escalation:{escalation_count}")
                signals.risk_level = max(signals.risk_level, 0.75)
                signals.requires_human = True
        
        # ── Default: No Risk ──────────────────────────────────────────
        if not signals.risk_categories:
            signals.risk_categories.append(RiskCategory.NONE)
        
        logger.debug(
            "Risk analysis | categories=%s level=%.2f requires_human=%s reasons=%s",
            [c.value for c in signals.risk_categories],
            signals.risk_level,
            signals.requires_human,
            signals.risk_reasons[:3],
        )
        
        return signals
    
    def should_escalate_on_risk(
        self,
        signals: RiskSignals,
    ) -> tuple[bool, str]:
        """
        Determine if risk level requires immediate escalation.
        
        Returns: (should_escalate, reason)
        """
        # Force escalation for high-risk categories
        if signals.requires_human:
            return True, f"high_risk:{','.join(signals.risk_reasons[:2])}"
        
        # Escalate if risk level is critically high
        if signals.risk_level >= 0.85:
            return True, f"risk_level_critical:{signals.risk_level:.2f}"
        
        # Don't escalate for medium risk unless combined with other factors
        return False, "risk_acceptable"
