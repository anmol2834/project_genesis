"""
Retrieval Layer - Public API
=============================
Enterprise-grade hierarchical retrieval system.
"""

from typing import Optional
from app.retrieval.orchestration.hierarchical_retriever import HierarchicalRetriever
from app.retrieval.qdrant.repository import QdrantRepository


# Singleton instance
_retriever_instance: Optional[HierarchicalRetriever] = None


def get_hierarchical_retriever(
    redis_client,
    qdrant_url: str,
    collection_name: str = "business_context"
) -> HierarchicalRetriever:
    """
    Get or create hierarchical retriever singleton.
    
    Args:
        redis_client: Redis client from shared.cache
        qdrant_url: Qdrant server URL
        collection_name: Qdrant collection name
        
    Returns:
        HierarchicalRetriever instance
    """
    global _retriever_instance
    
    if _retriever_instance is None:
        # Initialize Qdrant repository
        qdrant_repo = QdrantRepository(
            qdrant_url=qdrant_url,
            collection_name=collection_name
        )
        
        # Initialize hierarchical retriever
        _retriever_instance = HierarchicalRetriever(
            redis_client=redis_client,
            qdrant_repository=qdrant_repo,
            min_chunks_for_exit=5,
            min_score_for_exit=0.85
        )
    
    return _retriever_instance


# Export main components
from app.retrieval.schemas import (
    RetrievalSource,
    ChunkType,
    RetrievedChunk,
    RetrievalResult,
    ValidationResult,
    RetrievalMetrics
)

from app.retrieval.interfaces import (
    IRetrievalCache,
    IConversationCache,
    IExactSearchEngine,
    IMetadataSearchEngine,
    IValidationEngine,
    IQdrantRepository,
    IHierarchicalRetriever
)


__all__ = [
    # Factory
    "get_hierarchical_retriever",
    
    # Schemas
    "RetrievalSource",
    "ChunkType",
    "RetrievedChunk",
    "RetrievalResult",
    "ValidationResult",
    "RetrievalMetrics",
    
    # Interfaces
    "IRetrievalCache",
    "IConversationCache",
    "IExactSearchEngine",
    "IMetadataSearchEngine",
    "IValidationEngine",
    "IQdrantRepository",
    "IHierarchicalRetriever",
]
