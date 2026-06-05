"""
Memory Layer - Pydantic Schemas
=================================
Enterprise-grade type-safe data models for conversational memory operating system.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class ConversationPhase(str, Enum):
    """Conversation journey phases"""
    DISCOVERY = "discovery"
    BROWSING = "browsing"
    CONSIDERATION = "consideration"
    DECISION = "decision"
    POST_PURCHASE = "post_purchase"
    SUPPORT = "support"


class FunnelStage(str, Enum):
    """Customer funnel stages"""
    AWARENESS = "awareness"
    INTEREST = "interest"
    CONSIDERATION = "consideration"
    INTENT = "intent"
    PURCHASE = "purchase"


class MemoryPriority(str, Enum):
    """Memory importance levels"""
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
# CORE MEMORY MODELS
# ══════════════════════════════════════════════════════════════════════════════

class ThreadMemory(BaseModel):
    """
    Hot memory structure - Redis-backed with 24h TTL.
    Optimized for <5ms lookup and conversation continuity.
    Compatible with existing automationservice/memory_engine.py
    """
    # ─── Identification ───────────────────────────────────────────────────
    thread_id: str = ""
    tenant_id: str = ""
    conversation_id: str = ""
    
    # ─── Conversation state ───────────────────────────────────────────────
    conversation_state: str = "discovery"
    stage: str = "awareness"
    turn_count: int = 0
    
    # ─── Intent tracking ──────────────────────────────────────────────────
    last_intent: str = "unknown"
    last_sub_intent: str = "none"
    last_action: str = ""
    intent_history: List[str] = Field(default_factory=list)
    
    # ─── Entity tracking ──────────────────────────────────────────────────
    last_entities: Dict[str, Any] = Field(default_factory=dict)
    active_entities: Dict[str, Any] = Field(default_factory=dict)
    last_topic: str = ""
    last_category: str = ""
    last_question: str = ""
    
    # ─── Product tracking ─────────────────────────────────────────────────
    last_products: List[str] = Field(default_factory=list)
    shown_products: List[str] = Field(default_factory=list)
    products_already_shown: List[str] = Field(default_factory=list)
    
    # ─── User preferences ─────────────────────────────────────────────────
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    user_interest: List[str] = Field(default_factory=list)
    rejected_categories: List[str] = Field(default_factory=list)
    
    # ─── Memory layers ────────────────────────────────────────────────────
    short_term_memory: List[str] = Field(default_factory=list)
    long_term_memory: List[str] = Field(default_factory=list)
    context_summary: str = ""
    
    # ─── AI guidance ──────────────────────────────────────────────────────
    recommended_next_actions: List[str] = Field(default_factory=list)
    
    # ─── Metrics ──────────────────────────────────────────────────────────
    confidence: float = 0.0
    last_ai_reply: str = ""
    
    # ─── Timestamps ───────────────────────────────────────────────────────
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    timestamp: str = ""


class ConversationContext(BaseModel):
    """
    L1 retrieval cache - eliminates redundant Qdrant queries.
    Compatible with existing automationservice/conv_cache.py
    """
    products: List[Dict[str, Any]] = Field(default_factory=list)
    profile: List[Dict[str, Any]] = Field(default_factory=list)
    shown_products: List[str] = Field(default_factory=list)
    all_product_names: List[str] = Field(default_factory=list)
    turn: int = 0
    last_intent: str = ""
    last_retrieval_strategy: str = ""
    cache_version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EntityMemory(BaseModel):
    """Entity graph node - tracks entity mentions and relationships"""
    entity_id: str
    entity_type: str
    entity_value: str
    mention_count: int = 0
    first_mentioned: datetime
    last_mentioned: datetime
    related_entities: List[str] = Field(default_factory=list)
    co_occurrence_count: Dict[str, int] = Field(default_factory=dict)
    context_summary: str = ""
    user_sentiment: str = "neutral"


class RetrievalCacheEntry(BaseModel):
    """Cached retrieval result - avoids repeated Qdrant searches"""
    cache_key: str
    query: str
    query_hash: str
    chunks: List[Dict[str, Any]] = Field(default_factory=list)
    chunk_count: int = 0
    strategy: str
    confidence: float = 0.0
    latency_ms: float = 0.0
    hit_count: int = 0
    created_at: datetime
    expires_at: datetime
    invalidate_on: List[str] = Field(default_factory=list)


class MemorySummary(BaseModel):
    """Compressed conversation summary for cold storage"""
    thread_id: str
    tenant_id: str
    summary_text: str
    key_facts: List[str] = Field(default_factory=list)
    mentioned_products: List[str] = Field(default_factory=list)
    mentioned_categories: List[str] = Field(default_factory=list)
    final_state: str
    final_stage: str
    outcome: str
    turn_count: int
    duration_seconds: int
    conversation_start: datetime
    conversation_end: datetime
    created_at: datetime


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

class MemoryLoadRequest(BaseModel):
    """Request to load memory"""
    thread_id: str
    tenant_id: str
    include_cold: bool = False
    include_entities: bool = True
    include_retrieval_cache: bool = True
    max_turns: Optional[int] = None


class MemoryLoadResult(BaseModel):
    """Result of memory load operation"""
    hot_memory: Optional[ThreadMemory] = None
    cold_memory: Optional[MemorySummary] = None
    entity_memory: List[EntityMemory] = Field(default_factory=list)
    retrieval_cache: List[RetrievalCacheEntry] = Field(default_factory=list)
    load_latency_ms: float = 0.0
    source: str = "redis"


class MemoryEnrichmentResult(BaseModel):
    """Result of memory enrichment on query"""
    original_query: str
    enriched_query: str
    enriched_keywords: List[str] = Field(default_factory=list)
    is_continuation: bool = False
    is_affirmative: bool = False
    resolved_intent: Optional[str] = None
    resolved_entity: Optional[str] = None
    resolved_topic: Optional[str] = None
    inherited_intent: Optional[str] = None
    inherited_entities: Dict[str, Any] = Field(default_factory=dict)
    memory_confidence: float = 0.0
    enrichment_type: str = "none"


class MemoryUpdateRequest(BaseModel):
    """Request to update memory after turn"""
    thread_id: str
    tenant_id: str
    intent: str
    sub_intent: str
    retrieved_products: List[str] = Field(default_factory=list)
    category: str = ""
    ai_reply: str = ""
    action: str = ""
    entities: Dict[str, Any] = Field(default_factory=dict)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)


class MemorySnapshot(BaseModel):
    """Memory snapshot for handoff to human agents"""
    thread_id: str
    tenant_id: str
    conversation_id: str
    context_summary: str
    key_facts: List[str] = Field(default_factory=list)
    conversation_state: str
    stage: str
    active_entities: Dict[str, Any] = Field(default_factory=dict)
    shown_products: List[str] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    recommended_next_actions: List[str] = Field(default_factory=list)
    turn_count: int
    confidence: float
    last_ai_reply: str
    created_at: datetime


class MemoryMetrics(BaseModel):
    """Memory system observability metrics"""
    hot_load_latency_ms: float = 0.0
    cold_load_latency_ms: float = 0.0
    save_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    retrieval_cache_hit_rate: float = 0.0
    hot_memory_size_bytes: int = 0
    entity_graph_size: int = 0
    continuation_resolution_rate: float = 0.0
    memory_enrichment_rate: float = 0.0


__all__ = [
    "ConversationPhase",
    "FunnelStage",
    "MemoryPriority",
    "EntityType",
    "MemorySource",
    "ThreadMemory",
    "ConversationContext",
    "EntityMemory",
    "RetrievalCacheEntry",
    "MemorySummary",
    "MemoryLoadRequest",
    "MemoryLoadResult",
    "MemoryEnrichmentResult",
    "MemoryUpdateRequest",
    "MemorySnapshot",
    "MemoryMetrics",
]
