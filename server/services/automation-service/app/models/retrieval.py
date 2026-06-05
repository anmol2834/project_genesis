"""
Global Models - Retrieval Contracts
====================================
Consolidated retrieval layer models.
Extends app/retrieval/schemas with global standards.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.base import BaseLayerResult, BaseTenant, BaseReplayable
from app.models.enums import RetrievalStrategy, RetrievalSource, ChunkType


class RetrievedChunk(BaseTenant):
    """
    Single retrieved knowledge chunk.
    Extends existing retrieval/schemas/RetrievedChunk.
    """
    content: str = Field(..., description="Chunk text content")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    chunk_type: ChunkType = Field(..., description="Chunk classification")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    source: RetrievalSource = Field(..., description="Retrieval layer source")
    retrieval_layer: str = Field(default="", description="Layer name (L1-L7)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    validated: bool = Field(default=False, description="Passed validation")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Validation relevance")
    mentioned_entities: List[str] = Field(default_factory=list, description="Entities in chunk")
    retrieval_timestamp: datetime = Field(default_factory=datetime.utcnow)


class RetrievalResult(BaseLayerResult):
    """
    Complete retrieval operation result.
    Extends existing retrieval/schemas/RetrievalResult.
    """
    chunks: List[RetrievedChunk] = Field(default_factory=list)
    total_retrieved: int = 0
    cache_hit: bool = False
    early_exit: bool = False
    layers_used: List[str] = Field(default_factory=list)
    layer_latencies: Dict[str, float] = Field(default_factory=dict)
    strategy_used: RetrievalStrategy = RetrievalStrategy.HIERARCHICAL
    retrieval_confidence: float = 0.0
    validation_passed: int = 0
    validation_rejected: int = 0
    cache_key: Optional[str] = None
    cache_hit_layer: Optional[str] = None
    user_id: str = ""
    conversation_id: str = ""


class QueryPlan(BaseModel):
    """
    Retrieval strategy plan from intelligence layer.
    Consolidates intelligence/models/QueryPlan.
    """
    retrieval_strategy: RetrievalStrategy
    confidence: float = Field(ge=0.0, le=1.0)
    memory_dependency: str = "none"  # none, low, high
    needs_new_retrieval: bool = True
    stages: List[str] = Field(default_factory=list)
    secondary_queries: List[str] = Field(default_factory=list)
    cache_reusable: bool = False
    cached_entities_reusable: List[str] = Field(default_factory=list)
    expected_chunk_types: List[ChunkType] = Field(default_factory=list)
    expected_result_count: int = 5
    min_score_threshold: float = 0.7
    skip_reranking: bool = False
    estimated_latency_ms: float = 0.0


class ValidationResult(BaseModel):
    """Chunk validation result"""
    chunk_id: str
    valid: bool
    relevance_score: float
    rejection_reasons: List[str] = Field(default_factory=list)
    tenant_valid: bool = True
    content_valid: bool = True
    relevance_valid: bool = True
    validation_confidence: float = 0.0


class RetrievalMetrics(BaseTenant):
    """Retrieval performance metrics"""
    total_latency_ms: float
    l1_latency_ms: float = 0.0
    l2_latency_ms: float = 0.0
    l3_latency_ms: float = 0.0
    l4_latency_ms: float = 0.0
    l5_latency_ms: float = 0.0
    l6_latency_ms: float = 0.0
    l7_latency_ms: float = 0.0
    l1_cache_hit: bool = False
    l2_cache_hit: bool = False
    chunks_retrieved: int = 0
    chunks_validated: int = 0
    chunks_rejected: int = 0
    early_exit: bool = False
    exit_layer: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RetrievalReplaySnapshot(BaseReplayable):
    """Snapshot for deterministic retrieval replay"""
    query: str
    query_vector: List[float]
    query_plan: QueryPlan
    filters: Dict[str, Any] = Field(default_factory=dict)
    result: RetrievalResult
    qdrant_version: str = "1.0"
    embedding_model: str = "e5-base-v2"


__all__ = [
    "RetrievedChunk",
    "RetrievalResult",
    "QueryPlan",
    "ValidationResult",
    "RetrievalMetrics",
    "RetrievalReplaySnapshot",
]
