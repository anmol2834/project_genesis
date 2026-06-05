"""
Global Models - Observability Contracts
========================================
Enterprise observability and telemetry models.
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from app.models.base import BaseTraceable, BaseTenant, BaseLayerResult
from app.models.enums import SpanKind, LogLevel, MetricType

class TraceContext(BaseTraceable, BaseTenant):
    """Distributed trace context"""
    service_name: str = "automation-service"
    operation_name: str = ""
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "ok"
    error: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    
class SpanEvent(BaseModel):
    """Individual span event"""
    span_id: str
    span_kind: SpanKind
    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "ok"

class StructuredLog(BaseTenant, BaseTraceable):
    """Structured log entry"""
    level: LogLevel
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    logger_name: str = ""
    module: str = ""
    function: str = ""
    line_number: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

class MetricPoint(BaseTenant):
    """Single metric data point"""
    metric_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = Field(default_factory=dict)
    unit: str = ""

class RetrievalMetric(BaseTenant):
    """Retrieval-specific metrics"""
    total_latency_ms: float
    cache_hit: bool
    layers_used: List[str] = Field(default_factory=list)
    chunks_retrieved: int = 0
    chunks_validated: int = 0
    early_exit: bool = False

class LLMMetric(BaseTenant):
    """LLM generation metrics"""
    model: str
    tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    generation_latency_ms: float
    confidence: float

class HallucinationMetric(BaseTenant):
    """Hallucination detection metrics"""
    detected: bool
    severity: str
    claims_count: int = 0
    confidence_penalty: float = 0.0

class ConfidenceMetric(BaseTenant):
    """Multi-signal confidence metrics"""
    final_confidence: float
    retrieval_confidence: float
    llm_confidence: float
    guard_score: float
    intent_confidence: float

__all__ = [
    "TraceContext",
    "SpanEvent",
    "StructuredLog",
    "MetricPoint",
    "RetrievalMetric",
    "LLMMetric",
    "HallucinationMetric",
    "ConfidenceMetric",
]
