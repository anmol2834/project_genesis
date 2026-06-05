"""
Handoff Layer — Core Models
============================
Production-grade handoff system models.
Multi-tenant, distributed-safe, enterprise-ready.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EscalationReason(str, Enum):
    """Why was this conversation escalated"""
    # Uncertainty signals
    LOW_CONFIDENCE = "low_confidence"
    INCOMPLETE_CONTEXT = "incomplete_context"
    RETRIEVAL_FAILURE = "retrieval_failure"
    AMBIGUOUS_QUERY = "ambiguous_query"
    
    # Hallucination risk
    HALLUCINATION_DETECTED = "hallucination_detected"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    CONTACT_AS_PRODUCT = "contact_as_product"
    PRICE_MISMATCH = "price_mismatch"
    
    # Emotional/Risk signals
    ANGRY_CUSTOMER = "angry_customer"
    LEGAL_THREAT = "legal_threat"
    REFUND_REQUEST = "refund_request"
    COMPLAINT = "complaint"
    CHARGEBACK_RISK = "chargeback_risk"
    
    # Policy/Compliance
    PRICING_NEGOTIATION = "pricing_negotiation"
    DATA_PRIVACY_CONCERN = "data_privacy_concern"
    MEDICAL_ADVICE = "medical_advice"
    LEGAL_ADVICE = "legal_advice"
    
    # Technical
    MULTI_STEP_UNRESOLVED = "multi_step_unresolved"
    CONTEXT_OVERFLOW = "context_overflow"
    SYSTEM_ERROR = "system_error"


class EscalationPriority(str, Enum):
    """SLA priority levels"""
    CRITICAL = "critical"  # Legal, refund, angry — 1h SLA
    HIGH = "high"          # Pricing, negotiation — 4h SLA
    MEDIUM = "medium"      # Support, technical — 24h SLA
    LOW = "low"            # Informational — 48h SLA


class HandoffStatus(str, Enum):
    """Handoff lifecycle states"""
    PENDING = "pending"              # Just escalated, waiting for human
    ASSIGNED = "assigned"            # Human claimed ownership
    IN_PROGRESS = "in_progress"      # Human actively working
    RESOLVED = "resolved"            # Human resolved, AI can resume
    FAILED = "failed"                # Escalation failed (no human available)
    CANCELLED = "cancelled"          # User no longer needs help
    EXPIRED = "expired"              # SLA breached, auto-escalated


class RiskCategory(str, Enum):
    """Risk classification for routing"""
    LEGAL = "legal"
    FINANCIAL = "financial"
    TECHNICAL = "technical"
    EMOTIONAL = "emotional"
    COMPLIANCE = "compliance"
    NONE = "none"


@dataclass
class ConfidenceSignal:
    """Multi-signal confidence breakdown"""
    retrieval_confidence: float = 0.0
    llm_confidence: float = 0.0
    hallucination_guard_score: float = 1.0
    intent_confidence: float = 0.0
    memory_continuity_score: float = 1.0
    entity_resolution_score: float = 1.0
    
    # Computed
    final_confidence: float = 0.0
    
    def compute_final(self) -> float:
        """Multi-signal confidence fusion with weighted average"""
        weights = {
            'retrieval': 0.30,
            'llm': 0.20,
            'guard': 0.15,
            'intent': 0.10,
            'memory': 0.10,
            'entity': 0.10,
            'historical': 0.05,
        }
        
        self.final_confidence = (
            weights['retrieval'] * self.retrieval_confidence +
            weights['llm'] * self.llm_confidence +
            weights['guard'] * self.hallucination_guard_score +
            weights['intent'] * self.intent_confidence +
            weights['memory'] * self.memory_continuity_score +
            weights['entity'] * self.entity_resolution_score
        )
        
        return self.final_confidence


@dataclass
class RiskSignals:
    """Risk detection signals"""
    risk_categories: list[RiskCategory] = field(default_factory=list)
    risk_level: float = 0.0  # 0.0-1.0
    requires_human: bool = False
    risk_reasons: list[str] = field(default_factory=list)


@dataclass
class EscalationDecision:
    """Final handoff decision"""
    should_escalate: bool
    reason: EscalationReason
    priority: EscalationPriority
    confidence_signal: ConfidenceSignal
    risk_signals: RiskSignals
    fallback_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class HandoffTicket:
    """Escalation ticket stored in PostgreSQL"""
    ticket_id: str
    user_id: str
    conversation_id: str
    thread_id: str
    message_id: str
    
    # Escalation details
    reason: EscalationReason
    priority: EscalationPriority
    status: HandoffStatus
    
    # Context
    user_message: str
    ai_reply: Optional[str]
    retrieved_context: list[dict] = field(default_factory=list)
    confidence_breakdown: dict = field(default_factory=dict)
    risk_analysis: dict = field(default_factory=dict)
    
    # Ownership
    assigned_human_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    
    # SLA tracking
    escalated_at: datetime = field(default_factory=datetime.utcnow)
    sla_deadline: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Routing
    department: Optional[str] = None
    routing_metadata: dict = field(default_factory=dict)
    
    # Audit
    escalation_count: int = 1
    resolution_notes: Optional[str] = None
    customer_satisfied: Optional[bool] = None


@dataclass
class HumanOwnership:
    """Redis hot-state for human ownership locks"""
    thread_id: str
    assigned_human_id: str
    assigned_at: datetime
    sla_expiry: datetime
    escalation_reason: str
    conversation_snapshot: dict = field(default_factory=dict)


@dataclass
class FallbackResponse:
    """Safe fallback messages for escalation scenarios"""
    message: str
    tone: str  # professional, empathetic, apologetic
    language: str = "en"
    requires_send: bool = True
