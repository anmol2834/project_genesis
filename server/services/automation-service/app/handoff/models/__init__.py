"""
Handoff Layer — Core Models
============================
Production-grade handoff system models.
Multi-tenant, distributed-safe, enterprise-ready.

Changes from original:
  - Added RiskLevel enum (was missing, causing ImportError in handoff_orchestrator.py)
  - Added EscalationReason.HUMAN_IN_LOOP, UNCERTAIN, NONE, LEGAL_ISSUE values
    (used by handoff_orchestrator.py but absent from the enum)
  - Added HandoffDecision dataclass (used by handoff_orchestrator.py, was completely missing)
  - Fixed ConfidenceSignal.compute_final — added historical_feedback_score field so
    weights sum to 1.0 instead of 0.95 (Task 11 fix batched here, same file)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class EscalationReason(str, Enum):
    """Why was this conversation escalated"""
    # Uncertainty signals
    LOW_CONFIDENCE     = "low_confidence"
    INCOMPLETE_CONTEXT = "incomplete_context"
    RETRIEVAL_FAILURE  = "retrieval_failure"
    AMBIGUOUS_QUERY    = "ambiguous_query"

    # Hallucination risk
    HALLUCINATION_DETECTED = "hallucination_detected"
    UNSUPPORTED_CLAIM      = "unsupported_claim"
    CONTACT_AS_PRODUCT     = "contact_as_product"
    PRICE_MISMATCH         = "price_mismatch"

    # Emotional / Risk signals
    ANGRY_CUSTOMER  = "angry_customer"
    LEGAL_THREAT    = "legal_threat"
    REFUND_REQUEST  = "refund_request"
    COMPLAINT       = "complaint"
    CHARGEBACK_RISK = "chargeback_risk"

    # Policy / Compliance
    PRICING_NEGOTIATION = "pricing_negotiation"
    DATA_PRIVACY_CONCERN = "data_privacy_concern"
    MEDICAL_ADVICE      = "medical_advice"
    LEGAL_ADVICE        = "legal_advice"

    # Technical
    MULTI_STEP_UNRESOLVED = "multi_step_unresolved"
    CONTEXT_OVERFLOW      = "context_overflow"
    SYSTEM_ERROR          = "system_error"

    # ── Added values (were missing, caused AttributeError in handoff_orchestrator.py) ──
    HUMAN_IN_LOOP = "human_in_loop"   # conversation already owned by a human agent
    UNCERTAIN     = "uncertain"        # general uncertainty — catch-all
    NONE          = "none"             # no escalation reason (AI handled cleanly)
    LEGAL_ISSUE   = "legal_issue"      # legal concern broader than a direct threat


class EscalationPriority(str, Enum):
    """SLA priority levels"""
    CRITICAL = "critical"   # Legal, refund, angry — 1 h SLA
    HIGH     = "high"       # Pricing, negotiation — 4 h SLA
    MEDIUM   = "medium"     # Support, technical — 24 h SLA
    LOW      = "low"        # Informational — 48 h SLA


class HandoffStatus(str, Enum):
    """Handoff lifecycle states"""
    PENDING     = "pending"       # Just escalated, waiting for human
    ASSIGNED    = "assigned"      # Human claimed ownership
    IN_PROGRESS = "in_progress"   # Human actively working
    RESOLVED    = "resolved"      # Human resolved, AI can resume
    FAILED      = "failed"        # Escalation failed (no human available)
    CANCELLED   = "cancelled"     # User no longer needs help
    EXPIRED     = "expired"       # SLA breached, auto-escalated


class RiskCategory(str, Enum):
    """Risk classification for routing"""
    LEGAL      = "legal"
    FINANCIAL  = "financial"
    TECHNICAL  = "technical"
    EMOTIONAL  = "emotional"
    COMPLIANCE = "compliance"
    NONE       = "none"


class RiskLevel(str, Enum):
    """
    Risk severity level.
    Added — was missing from this module, causing ImportError in
    app/handoff/services/handoff_orchestrator.py which imports it here.
    """
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConfidenceSignal:
    """
    Multi-signal confidence breakdown.

    Fix (Task 11): added historical_feedback_score field so compute_final()
    weights sum exactly to 1.0 (previously summed to 0.95, causing every
    confidence score to be systematically 5 % lower than intended).
    """
    retrieval_confidence:      float = 0.0
    llm_confidence:            float = 0.0
    hallucination_guard_score: float = 1.0
    intent_confidence:         float = 0.0
    memory_continuity_score:   float = 1.0
    entity_resolution_score:   float = 1.0
    historical_feedback_score: float = 0.0   # ← new field; default 0 is backward-safe

    # Computed — populated by compute_final()
    final_confidence: float = 0.0

    def compute_final(self) -> float:
        """
        Multi-signal confidence fusion.

        Weights (must sum to 1.0):
          retrieval  0.30
          llm        0.20
          guard      0.15
          intent     0.10
          memory     0.10
          entity     0.10
          historical 0.05
          ─────────────
          total      1.00
        """
        self.final_confidence = (
            0.30 * self.retrieval_confidence
            + 0.20 * self.llm_confidence
            + 0.15 * self.hallucination_guard_score
            + 0.10 * self.intent_confidence
            + 0.10 * self.memory_continuity_score
            + 0.10 * self.entity_resolution_score
            + 0.05 * self.historical_feedback_score
        )
        return self.final_confidence


@dataclass
class RiskSignals:
    """Risk detection signals"""
    risk_categories: List[RiskCategory] = field(default_factory=list)
    risk_level:      float = 0.0          # 0.0 – 1.0 continuous score
    requires_human:  bool  = False
    risk_reasons:    List[str] = field(default_factory=list)


@dataclass
class EscalationDecision:
    """Final handoff decision (returned by HandoffService / confidence path)"""
    should_escalate:   bool
    reason:            EscalationReason
    priority:          EscalationPriority
    confidence_signal: ConfidenceSignal
    risk_signals:      RiskSignals
    fallback_message:  Optional[str] = None
    metadata:          dict = field(default_factory=dict)


@dataclass
class HandoffDecision:
    """
    Decision output of the full HandoffOrchestrator evaluation.

    Added — was completely missing, causing ImportError in
    app/handoff/services/handoff_orchestrator.py which imports and
    instantiates HandoffDecision throughout its _make_decision() method.

    Fields mirror every attribute assigned or read in handoff_orchestrator.py:
      decision, confidence_score, risk_level, escalation_reason,
      escalation_priority, blocking, fallback_message, ticket_id,
      assigned_agent, routing_metadata, sla_deadline, risk_categories.
    """
    should_escalate:     bool
    decision:            str               # "ai_handled"|"high_risk"|"human_owned"|…
    confidence_score:    float
    risk_level:          RiskLevel
    escalation_reason:   EscalationReason
    escalation_priority: EscalationPriority
    blocking:            bool = False
    fallback_message:    Optional[str] = None
    ticket_id:           Optional[str] = None
    assigned_agent:      Optional[str] = None
    routing_metadata:    dict = field(default_factory=dict)
    sla_deadline:        Optional[str] = None
    risk_categories:     List[str] = field(default_factory=list)


@dataclass
class HandoffTicket:
    """Escalation ticket persisted to PostgreSQL"""
    ticket_id:       str
    user_id:         str
    conversation_id: str
    thread_id:       str
    message_id:      str

    reason:   EscalationReason
    priority: EscalationPriority
    status:   HandoffStatus

    user_message: str
    ai_reply:     Optional[str]

    retrieved_context:    List[dict] = field(default_factory=list)
    confidence_breakdown: dict       = field(default_factory=dict)
    risk_analysis:        dict       = field(default_factory=dict)

    assigned_human_id: Optional[str]      = None
    assigned_at:       Optional[datetime] = None

    escalated_at: datetime           = field(default_factory=datetime.utcnow)
    sla_deadline: Optional[datetime] = None
    resolved_at:  Optional[datetime] = None

    department:        Optional[str] = None
    routing_metadata:  dict = field(default_factory=dict)

    escalation_count:   int = 1
    resolution_notes:   Optional[str]  = None
    customer_satisfied: Optional[bool] = None


@dataclass
class HumanOwnership:
    """Redis hot-state for human ownership locks"""
    thread_id:          str
    assigned_human_id:  str
    assigned_at:        datetime
    sla_expiry:         datetime
    escalation_reason:  str
    conversation_snapshot: dict = field(default_factory=dict)


@dataclass
class FallbackResponse:
    """Safe fallback messages for escalation scenarios"""
    message:      str
    tone:         str    # professional | empathetic | apologetic
    language:     str  = "en"
    requires_send: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Enums
    "EscalationReason",
    "EscalationPriority",
    "HandoffStatus",
    "RiskCategory",
    "RiskLevel",
    # Dataclasses
    "ConfidenceSignal",
    "RiskSignals",
    "EscalationDecision",
    "HandoffDecision",
    "HandoffTicket",
    "HumanOwnership",
    "FallbackResponse",
]
