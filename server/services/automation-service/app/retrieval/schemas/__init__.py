"""
Retrieval Layer - Data Schemas
===============================
Production-grade data models for retrieval operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


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
    DATA_ANALYTICS = "data_analytics"


@dataclass
class RetrievedChunk:
    """Single retrieved knowledge chunk with full metadata"""
    
    content: str
    score: float
    chunk_type: ChunkType
    chunk_id: str
    source: RetrievalSource
    user_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_layer: str = ""
    retrieval_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    validated: bool = False
    relevance_score: float = 0.0
    mentioned_entities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "score": self.score,
            "chunk_type": self.chunk_type.value if isinstance(self.chunk_type, ChunkType) else self.chunk_type,
            "chunk_id": self.chunk_id,
            "source": self.source.value if isinstance(self.source, RetrievalSource) else self.source,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "retrieval_layer": self.retrieval_layer,
            "validated": self.validated,
            "relevance_score": self.relevance_score
        }


@dataclass
class RetrievalResult:
    """Complete result of hierarchical retrieval operation"""
    
    chunks: List[RetrievedChunk]
    total_retrieved: int
    cache_hit: bool
    early_exit: bool
    latency_ms: float
    layers_used: List[str]
    layer_latencies: Dict[str, float] = field(default_factory=dict)
    strategy_used: str = "hierarchical"
    retrieval_confidence: float = 0.0
    validation_passed: int = 0
    validation_rejected: int = 0
    cache_key: Optional[str] = None
    cache_hit_layer: Optional[str] = None
    user_id: str = ""
    conversation_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def get_top_chunks(self, n: int = 5) -> List[RetrievedChunk]:
        return sorted(self.chunks, key=lambda c: c.score, reverse=True)[:n]
    
    def get_validated_chunks(self) -> List[RetrievedChunk]:
        return [c for c in self.chunks if c.validated]


@dataclass
class ValidationResult:
    """Result of chunk validation"""
    chunk_id: str
    valid: bool
    relevance_score: float
    rejection_reasons: List[str] = field(default_factory=list)
    tenant_valid: bool = True
    content_valid: bool = True
    relevance_valid: bool = True
    validation_confidence: float = 0.0


@dataclass
class RetrievalMetrics:
    """Retrieval performance metrics"""
    total_latency_ms: float
    l1_latency_ms: float = 0.0
    l2_latency_ms: float = 0.0
    l3_latency_ms: float = 0.0
    l1_cache_hit: bool = False
    l2_cache_hit: bool = False
    chunks_retrieved: int = 0
    chunks_validated: int = 0
    chunks_rejected: int = 0
    early_exit: bool = False
    exit_layer: Optional[str] = None
    user_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


__all__ = [
    "RetrievalSource",
    "ChunkType",
    "RetrievedChunk",
    "RetrievalResult",
    "ValidationResult",
    "RetrievalMetrics"
]
