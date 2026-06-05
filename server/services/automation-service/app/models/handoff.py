"""
Global Models - Handoff Contracts
==================================
Human escalation and handoff models.
Consolidates app/handoff/models with global standards.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.base import BaseTenant, BaseLayerResult
from app.models.enums import (
    EscalationReason, EscalationPriority, HandoffStatus, RiskCategory
)


class ConfidenceSignal(BaseModel):
    """Multi-signal confidence breakdown"""
    retrieval_confidence: float = 0.0
    llm_confidence: float = 0.0
    hallucination_guard_score: float = 1.0
    intent_confidence: float = 0.0
    memory_continuity_score: float = 1.0
    entity_resolution_score: float = 1.0
    final_confidence: float = 0.0
    
    def compute_final(self) -> float:
        """Multi-signal fusion"""
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


class RiskSignals(BaseModel):
    """Risk detection signals"""
    risk_categories: List[RiskCategory] = Field(default_factory=list)
    risk_level: float = 0.0
    requires_human: bool = False
    risk_reasons: List[str] = Field(default_factory=list)


class EscalationDecision(BaseLayerResult):
    """Handoff decision"""
    should_escalate: bool
    reason: EscalationReason
    priority: EscalationPriority
    confidence_signal: ConfidenceSignal
    risk_signals: RiskSignals
    fallback_message: Optional[str] = None
    decision: str = "send"  # send, skip, draft, escalate


class HandoffTicket(BaseTenant):
    """Escalation ticket"""
    ticket_id: str
    conversation_id: str
    thread_id: str
    message_id: str
    reason: EscalationReason
    priority: EscalationPriority
    status: HandoffStatus
    user_message: str
    ai_reply: Optional[str] = None
    retrieved_context: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_breakdown: Dict[str, float] = Field(default_factory=dict)
    risk_analysis: Dict[str, Any] = Field(default_factory=dict)
    assigned_human_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    escalated_at: datetime = Field(default_factory=datetime.utcnow)
    sla_deadline: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    department: Optional[str] = None
    escalation_count: int = 1
    resolution_notes: Optional[str] = None
    customer_satisfied: Optional[bool] = None


class FallbackResponse(BaseModel):
    """Safe fallback message"""
    message: str
    tone: str = "professional"
    language: str = "en"
    requires_send: bool = True


class HandoffMetrics(BaseModel):
    """Handoff system metrics"""
    total_escalations: int = 0
    escalation_rate: float = 0.0
    avg_confidence: float = 0.0
    by_reason: Dict[str, int] = Field(default_factory=dict)
    by_priority: Dict[str, int] = Field(default_factory=dict)
    sla_breach_count: int = 0
    avg_resolution_time_minutes: float = 0.0


__all__ = [
    "ConfidenceSignal",
    "RiskSignals",
    "EscalationDecision",
    "HandoffTicket",
    "FallbackResponse",
    "HandoffMetrics",
]
