"""
Global Models Package
=====================
Enterprise-grade contracts for entire automation-service.
"""
from app.models.base import *
from app.models.enums import *
from app.models.events import *
from app.models.intelligence import *
from app.models.retrieval import *
from app.models.memory import *
from app.models.llm import *
from app.models.handoff import *
from app.models.observability import *
from app.models.serialization import *
from app.models.validation import *

__all__ = [
    # Base
    "BaseTraceable",
    "BaseTenant",
    "BaseEvent",
    "BaseMessage",
    "BaseTimed",
    "BaseConfidence",
    "BaseReplayable",
    "BaseLayerResult",
    # Enums
    "Intent",
    "RetrievalStrategy",
    "ChunkType",
    "EscalationReason",
    "LLMProvider",
    "SpanKind",
    "LogLevel",
    # Events
    "AutomationEvent",
    "ResponseEvent",
    # Intelligence
    "IntelligenceResult",
    # Retrieval
    "RetrievedChunk",
    "RetrievalResult",
    # Memory
    "ThreadMemory",
    "ConversationContext",
    # LLM
    "PromptPackage",
    "LLMGenerationResult",
    "HallucinationReport",
    # Handoff
    "EscalationDecision",
    "HandoffTicket",
    # Observability
    "TraceContext",
    "StructuredLog",
    "MetricPoint",
    # Serialization
    "Serializer",
    # Validation
    "SchemaValidator",
    "ValidationResult",
]
