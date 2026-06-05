"""
Global Models - Enums
======================
Centralized enum definitions for entire automation-service.
"""
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# INTELLIGENCE LAYER ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class Intent(str, Enum):
    """User intent classification"""
    INTEREST = "interest"
    PRICING = "pricing"
    SUPPORT = "support"
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    NEGOTIATION = "negotiation"
    COMPLAINT = "complaint"
    CASUAL = "casual"
    NOT_INTERESTED = "not_interested"
    UNKNOWN = "unknown"


class ConversationStage(str, Enum):
    """Conversation funnel stage"""
    AWARENESS = "awareness"
    INTEREST = "interest"
    CONSIDERATION = "consideration"
    INTENT = "intent"
    DECISION = "decision"
    POST_PURCHASE = "post_purchase"


class Urgency(str, Enum):
    """Message urgency level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Risk classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ══════════════════════════════════════════════════════════════════════════════
# RETRIEVAL LAYER ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class RetrievalStrategy(str, Enum):
    """Retrieval execution strategy"""
    EXACT_MATCH = "exact"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    HIERARCHICAL = "hierarchical"
    CACHED = "cached"
    METADATA = "metadata"
    BM25 = "bm25"
    SKIP = "skip"


class RetrievalSource(str, Enum):
    """Source of retrieved chunk"""
    L1_CONV_CACHE = "l1_conv_cache"
    L2_EXACT_MATCH = "l2_exact_match"
    L3_METADATA = "l3_metadata"
    L4_BM25 = "l4_bm25"
    L5_SEMANTIC = "l5_semantic"
    L6_HYBRID = "l6_hybrid"
    L7_RERANKED = "l7_reranked"
    MEMORY_CACHE = "memory_cache"


class ChunkType(str, Enum):
    """Type of knowledge chunk"""
    PROFILE = "profile"
    PRODUCT_SERVICE = "product_service"
    FAQ = "faq"
    POLICY = "policy"
    SUPPORT = "support"
    TEAM = "team"
    LOCATION = "location"
    GENERAL = "general"


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY LAYER ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class ConversationPhase(str, Enum):
    """Conversation journey phase"""
    DISCOVERY = "discovery"
    BROWSING = "browsing"
    CONSIDERATION = "consideration"
    DECISION = "decision"
    POST_PURCHASE = "post_purchase"
    SUPPORT = "support"


class MemoryPriority(str, Enum):
    """Memory importance level"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EntityType(str, Enum):
    """Entity classification"""
    PRODUCT = "product"
    CATEGORY = "category"
    FEATURE = "feature"
    PRICE = "price"
    PERSON = "person"
    LOCATION = "location"
    COMPANY = "company"


class MemorySource(str, Enum):
    """Memory data source"""
    REDIS = "redis"
    POSTGRES = "postgres"
    CACHE = "cache"
    HYBRID = "hybrid"


# ══════════════════════════════════════════════════════════════════════════════
# HANDOFF LAYER ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class EscalationReason(str, Enum):
    """Escalation trigger"""
    LOW_CONFIDENCE = "low_confidence"
    INCOMPLETE_CONTEXT = "incomplete_context"
    RETRIEVAL_FAILURE = "retrieval_failure"
    AMBIGUOUS_QUERY = "ambiguous_query"
    HALLUCINATION_DETECTED = "hallucination_detected"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    ANGRY_CUSTOMER = "angry_customer"
    LEGAL_THREAT = "legal_threat"
    REFUND_REQUEST = "refund_request"
    COMPLAINT = "complaint"
    PRICING_NEGOTIATION = "pricing_negotiation"
    SYSTEM_ERROR = "system_error"


class EscalationPriority(str, Enum):
    """SLA priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HandoffStatus(str, Enum):
    """Handoff lifecycle state"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RiskCategory(str, Enum):
    """Risk classification category"""
    LEGAL = "legal"
    FINANCIAL = "financial"
    TECHNICAL = "technical"
    EMOTIONAL = "emotional"
    COMPLIANCE = "compliance"
    NONE = "none"


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGING LAYER ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class EventType(str, Enum):
    """Event type classification"""
    INCOMING_MESSAGE = "incoming_message"
    OUTGOING_RESPONSE = "outgoing_response"
    ESCALATION = "escalation"
    HANDOFF = "handoff"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    INTELLIGENCE_COMPLETED = "intelligence_completed"
    LLM_COMPLETED = "llm_completed"
    MEMORY_UPDATED = "memory_updated"


class EventStatus(str, Enum):
    """Event processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DLQ = "dlq"
    RETRYING = "retrying"


class MessagePriority(int, Enum):
    """Message priority levels"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


# ══════════════════════════════════════════════════════════════════════════════
# LLM LAYER ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class LLMProvider(str, Enum):
    """LLM provider"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"


class PromptType(str, Enum):
    """Prompt classification"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


class HallucinationSeverity(str, Enum):
    """Hallucination severity level"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ══════════════════════════════════════════════════════════════════════════════
# OBSERVABILITY ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class SpanKind(str, Enum):
    """OpenTelemetry span kind"""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class LogLevel(str, Enum):
    """Structured log level"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(str, Enum):
    """Metric classification"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(str, Enum):
    """Alert severity level"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


__all__ = [
    # Intelligence
    "Intent",
    "ConversationStage",
    "Urgency",
    "RiskLevel",
    # Retrieval
    "RetrievalStrategy",
    "RetrievalSource",
    "ChunkType",
    # Memory
    "ConversationPhase",
    "MemoryPriority",
    "EntityType",
    "MemorySource",
    # Handoff
    "EscalationReason",
    "EscalationPriority",
    "HandoffStatus",
    "RiskCategory",
    # Messaging
    "EventType",
    "EventStatus",
    "MessagePriority",
    # LLM
    "LLMProvider",
    "PromptType",
    "HallucinationSeverity",
    # Observability
    "SpanKind",
    "LogLevel",
    "MetricType",
    "AlertSeverity",
]
