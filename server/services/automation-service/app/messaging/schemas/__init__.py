"""
Messaging Layer - Pydantic Schemas
====================================
Type-safe event schemas for distributed messaging system.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator


class EventType(str, Enum):
    """Event type classification"""
    INCOMING_MESSAGE = "incoming_message"
    OUTGOING_RESPONSE = "outgoing_response"
    ESCALATION = "escalation"
    HANDOFF = "handoff"


class EventStatus(str, Enum):
    """Event processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DLQ = "dlq"


class Priority(int, Enum):
    """Message priority levels"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class AutomationEvent(BaseModel):
    """Incoming event from emailservice"""
    event_id: str
    message_id: str
    conversation_id: str
    thread_id: str
    user_id: str
    content: str
    subject: str = ""
    automation_enabled: bool = True
    priority: int = Priority.MEDIUM
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    source_service: str = "email-service"
    created_at: datetime
    ts: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    history: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('user_id', 'thread_id', 'message_id')
    def validate_ids(cls, v):
        if not v or len(v) < 3:
            raise ValueError(f"Invalid ID: {v}")
        return v


class ResponseEvent(BaseModel):
    """Outgoing response to emailservice"""
    event_id: str
    message_id: str
    conversation_id: str
    thread_id: str
    user_id: str
    response_text: str
    action: str
    confidence: float
    intent: str
    send_email: bool
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: datetime
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Event validation result"""
    valid: bool
    event: Optional[AutomationEvent] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    """Event processing result"""
    event_id: str
    status: EventStatus
    response: Optional[ResponseEvent] = None
    latency_ms: float
    pipeline_stage: str
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessagingMetrics(BaseModel):
    """Messaging system metrics"""
    events_received: int = 0
    events_processed: int = 0
    events_failed: int = 0
    avg_processing_latency_ms: float = 0.0
    idempotency_hits: int = 0
    duplicate_suppressions: int = 0
    stream_lag_ms: float = 0.0
    active_consumers: int = 0
    window_start: datetime
    window_end: datetime


__all__ = [
    "EventType",
    "EventStatus",
    "Priority",
    "AutomationEvent",
    "ResponseEvent",
    "ValidationResult",
    "ProcessingResult",
    "MessagingMetrics",
]
