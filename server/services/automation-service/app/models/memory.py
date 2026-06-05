"""
Global Models - Memory Contracts
=================================
Consolidated memory layer models.
Extends app/memory/schemas with global standards.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.base import BaseTenant, BaseLayerResult
from app.models.enums import ConversationPhase, MemorySource


class ThreadMemory(BaseTenant):
    """
    Hot memory structure.
    Consolidates memory/schemas/ThreadMemory.
    """
    thread_id: str = ""
    conversation_id: str = ""
    conversation_state: str = "discovery"
    stage: str = "awareness"
    turn_count: int = 0
    
    # Intent tracking
    last_intent: str = "unknown"
    last_sub_intent: str = "none"
    last_action: str = ""
    intent_history: List[str] = Field(default_factory=list)
    
    # Entity tracking
    last_entities: Dict[str, Any] = Field(default_factory=dict)
    active_entities: Dict[str, Any] = Field(default_factory=dict)
    last_topic: str = ""
    last_category: str = ""
    last_question: str = ""
    
    # Product tracking
    last_products: List[str] = Field(default_factory=list)
    shown_products: List[str] = Field(default_factory=list)
    
    # User preferences
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    user_interest: List[str] = Field(default_factory=list)
    rejected_categories: List[str] = Field(default_factory=list)
    
    # Memory layers
    short_term_memory: List[str] = Field(default_factory=list)
    context_summary: str = ""
    recommended_next_actions: List[str] = Field(default_factory=list)
    
    # Metadata
    confidence: float = 0.0
    last_ai_reply: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConversationContext(BaseTenant):
    """
    L1 retrieval cache.
    Consolidates memory/schemas/ConversationContext.
    """
    conversation_id: str = ""
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


class MemoryEnrichmentResult(BaseLayerResult):
    """Memory enrichment output"""
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


class MemorySnapshot(BaseTenant):
    """Memory snapshot for handoff"""
    thread_id: str
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
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EntityMemory(BaseModel):
    """Entity graph node"""
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
    """Cached retrieval result"""
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


__all__ = [
    "ThreadMemory",
    "ConversationContext",
    "MemoryEnrichmentResult",
    "MemorySnapshot",
    "EntityMemory",
    "RetrievalCacheEntry",
]
