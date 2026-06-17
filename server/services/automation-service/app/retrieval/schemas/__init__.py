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
    """
    Source of retrieved chunk — maps to the actual L1-L9 hierarchical pipeline layers.

    Task 12 fix (R13): corrected layer numbering so enum values match the real
    architecture defined in hierarchical_retriever.py:
      L1 = Intent cache
      L2 = Chunk/conversation cache
      L3 = Exact match
      L4 = Metadata filter
      L5 = BM25 sparse keyword    ← was wrongly labelled L4_BM25
      L6 = Dense semantic search  ← was wrongly labelled L5_SEMANTIC
      L7 = RRF fusion
      L8 = Cross-encoder rerank
      L9 = Context validation

    Backward-compat aliases keep old names pointing to the correct values so
    existing code that references L4_BM25 / L5_SEMANTIC still works.
    """
    # ── Canonical names (match layer numbers in hierarchical_retriever.py) ──
    L1_INTENT_CACHE = "l1_intent_cache"
    L2_CHUNK_CACHE  = "l2_chunk_cache"
    L3_EXACT_MATCH  = "l3_exact_match"
    L4_METADATA     = "l4_metadata"
    L5_BM25         = "l5_bm25"
    L6_SEMANTIC     = "l6_semantic"
    L7_RRF_FUSION   = "l7_rrf_fusion"
    L8_RERANK       = "l8_rerank"
    L9_VALIDATION   = "l9_validation"
    MEMORY_CACHE    = "memory_cache"

    # ── Backward-compat aliases (old names → correct values) ──
    # Python enums allow aliases (same value, different name).
    # Code using the old names continues to work; the canonical names are preferred.
    #
    # IMPORTANT: L2_EXACT_MATCH and L3_METADATA are the old names used in
    # app/models/enums.py and earlier versions of exact_search/engine.py and
    # metadata_search/engine.py.  Both engines have been updated to use the
    # canonical L3_EXACT_MATCH and L4_METADATA names, but these aliases are
    # retained for any code that still imports them from the schemas module.
    L1_CONV_CACHE     = "l1_intent_cache"    # old name for L1 (still valid)
    L2_EXACT_MATCH    = "l3_exact_match"     # OLD BUGGY NAME: mapped to L3_EXACT_MATCH (canonical)
    L3_METADATA       = "l4_metadata"        # OLD BUGGY NAME: mapped to L4_METADATA (canonical)
    L4_BM25           = "l5_bm25"            # old name was off-by-one → now alias of L5_BM25
    L5_SEMANTIC       = "l6_semantic"        # old name was off-by-one → now alias of L6_SEMANTIC
    L6_HYBRID         = "l6_semantic"        # old hybrid → semantic
    L7_RERANKED       = "l8_rerank"          # old name → L8_RERANK


class ChunkType(str, Enum):
    """Type of knowledge chunk — values match the 'category' field in user_data_entries."""
    PROFILE = "profile"
    PRODUCT_SERVICE = "product_service"
    FAQ = "faq"
    POLICY = "policy"
    SUPPORT = "support"
    TEAM = "team"
    LOCATION = "location"
    GENERAL = "general"
    DATA_ANALYTICS = "data_analytics"
    # Full category names used in user_data_entries — added so retrieval engines
    # can create RetrievedChunk objects without a ValueError on ChunkType(cat).
    OFFERS_PROMOTIONS = "offers_promotions"
    DELIVERY_SHIPPING = "delivery_shipping"
    CONTACT_SUPPORT = "contact_support"
    POLICIES_LEGAL = "policies_legal"
    COMPANY_INFO = "company_info"
    EDUCATIONAL_CONTENT = "educational_content"
    ISSUE_RESOLUTION = "issue_resolution"


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
