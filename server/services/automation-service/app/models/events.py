"""
Global Models - Distributed Events
===================================
Enterprise-grade event contracts for distributed messaging.
Extends existing messaging/schemas with tracing and replay.
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from app.models.base import BaseEvent, BaseReplayable
from app.models.enums import EventType, EventStatus, MessagePriority


class AutomationEvent(BaseEvent):
    """
    Incoming automation event from email-service.
    Extends messaging/schemas/AutomationEvent with full tracing.
    """
    message_id: str = Field(..., description="Unique message identifier")
    conversation_id: str = Field(..., description="Conversation identifier")
    thread_id: str = Field(..., description="Thread identifier with user_id prefix")
    content: str = Field(..., description="Message content")
    subject: str = Field(default="", description="Email subject")
    automation_enabled: bool = Field(default=True, description="Automation enabled flag")
    priority: int = Field(default=MessagePriority.MEDIUM, description="Message priority")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation history")
    
    class Config:
        use_enum_values = True


class IntelligenceCompletedEvent(BaseEvent):
    """Event emitted after intelligence layer completion"""
    message_id: str
    intent: str
    sub_intent: str
    confidence: float
    entities: Dict[str, Any] = Field(default_factory=dict)
    retrieval_strategy: str
    risk_level: str
    processing_time_ms: float = 0.0


class RetrievalCompletedEvent(BaseEvent):
    """Event emitted after retrieval layer completion"""
    message_id: str
    chunks_retrieved: int
    layers_used: List[str] = Field(default_factory=list)
    cache_hit: bool = False
    early_exit: bool = False
    retrieval_confidence: float = 0.0
    latency_ms: float = 0.0


class LLMCompletedEvent(BaseEvent):
    """Event emitted after LLM generation completion"""
    message_id: str
    response_text: str
    confidence: float
    hallucination_detected: bool = False
    tokens_used: int = 0
    generation_latency_ms: float = 0.0
    model: str = "gpt-4o-mini"


class HandoffDecisionEvent(BaseEvent):
    """Event emitted after handoff decision"""
    message_id: str
    decision: str  # send, skip, draft, escalate
    final_confidence: float
    escalation_reason: Optional[str] = None
    escalation_priority: Optional[str] = None


class ResponseEvent(BaseEvent):
    """
    Outgoing response event to email-service.
    Extends messaging/schemas/ResponseEvent with tracing.
    """
    message_id: str
    conversation_id: str
    thread_id: str
    response_text: str
    action: str  # send, skip, draft
    confidence: float
    intent: str
    send_email: bool
    processing_time_ms: float = 0.0


class MemoryUpdatedEvent(BaseEvent):
    """Event emitted after memory update"""
    thread_id: str
    turn_count: int
    conversation_state: str
    stage: str
    last_intent: str
    updated_entities: Dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    """Batch of events for efficient processing"""
    batch_id: str
    events: List[BaseEvent]
    batch_size: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EventReplayRequest(BaseReplayable):
    """Request to replay a specific event"""
    original_event_id: str
    original_event_type: EventType
    replay_config: Dict[str, Any] = Field(default_factory=dict, description="Replay configuration")
    dry_run: bool = Field(default=False, description="Dry run without side effects")


class EventReplayResult(BaseModel):
    """Result of event replay"""
    replay_id: str
    original_event_id: str
    success: bool
    differences: Dict[str, Any] = Field(default_factory=dict, description="Differences from original")
    replay_timestamp: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0


__all__ = [
    "AutomationEvent",
    "IntelligenceCompletedEvent",
    "RetrievalCompletedEvent",
    "LLMCompletedEvent",
    "HandoffDecisionEvent",
    "ResponseEvent",
    "MemoryUpdatedEvent",
    "EventBatch",
    "EventReplayRequest",
    "EventReplayResult",
]
