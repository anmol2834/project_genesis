"""
Global Models - Base Contracts
===============================
Universal base models for all distributed operations.
Every model in automation-service MUST inherit from these bases.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class BaseTraceable(BaseModel):
    """Base model with distributed tracing support"""
    trace_id: str = Field(..., description="Distributed trace ID for request tracking")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for event chaining")
    span_id: Optional[str] = Field(None, description="Span ID for this operation")
    parent_span_id: Optional[str] = Field(None, description="Parent span ID")
    
    class Config:
        frozen = False
        use_enum_values = True


class BaseTenant(BaseModel):
    """Base model with tenant isolation"""
    user_id: str = Field(..., description="Tenant ID - MANDATORY for multi-tenant isolation")
    
    class Config:
        frozen = False


class BaseEvent(BaseTraceable, BaseTenant):
    """Base distributed event model"""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Event type classification")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    source_service: str = Field(default="automation-service", description="Source service name")
    version: str = Field(default="2.0", description="Schema version")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BaseMessage(BaseTenant):
    """Base message model"""
    message_id: str = Field(..., description="Unique message identifier")
    conversation_id: str = Field(..., description="Conversation identifier")
    thread_id: str = Field(..., description="Thread identifier with user_id prefix")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BaseTimed(BaseModel):
    """Base model with timing metadata"""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    
    class Config:
        frozen = False


class BaseConfidence(BaseModel):
    """Base model with confidence scoring"""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    confidence_signals: Dict[str, float] = Field(default_factory=dict, description="Individual signal scores")
    confidence_source: str = Field(default="unknown", description="Confidence computation source")


class BaseReplayable(BaseTraceable, BaseTenant):
    """Base model supporting deterministic replay"""
    replay_id: Optional[str] = Field(None, description="Replay session identifier")
    is_replay: bool = Field(default=False, description="Is this a replay execution")
    original_timestamp: Optional[datetime] = Field(None, description="Original execution timestamp")
    replay_timestamp: Optional[datetime] = Field(None, description="Replay execution timestamp")
    
    class Config:
        frozen = False


class BaseVersioned(BaseModel):
    """Base model with schema versioning"""
    schema_version: str = Field(default="1.0", description="Schema version for backward compatibility")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class BaseLayerResult(BaseTimed, BaseConfidence):
    """Base result from any pipeline layer"""
    layer: str = Field(..., description="Layer name (intelligence, retrieval, llm, etc)")
    success: bool = Field(default=True, description="Operation success status")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ServiceHealth(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class OperationStatus(str, Enum):
    """Generic operation status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


__all__ = [
    "BaseTraceable",
    "BaseTenant",
    "BaseEvent",
    "BaseMessage",
    "BaseTimed",
    "BaseConfidence",
    "BaseReplayable",
    "BaseVersioned",
    "BaseLayerResult",
    "ServiceHealth",
    "OperationStatus",
]
