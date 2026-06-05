"""
Retrieval Layer - Interface Contracts
======================================
Defines contracts for deterministic retrieval components.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.retrieval.schemas import RetrievedChunk, RetrievalResult, ValidationResult


class IRetrievalCache(ABC):
    """Interface for retrieval caching"""
    
    @abstractmethod
    async def get_cached_retrieval(
        self,
        user_id: str,
        query_hash: str
    ) -> Optional[List[Dict]]:
        """Get cached retrieval result"""
        pass
    
    @abstractmethod
    async def cache_retrieval(
        self,
        user_id: str,
        query_hash: str,
        chunks: List[RetrievedChunk],
        ttl_seconds: int = 1200
    ) -> bool:
        """Cache retrieval result"""
        pass
    
    @abstractmethod
    async def invalidate_cache(
        self,
        user_id: str,
        pattern: Optional[str] = None
    ) -> int:
        """Invalidate cached retrievals"""
        pass


class IConversationCache(ABC):
    """Interface for L1 conversation cache"""
    
    @abstractmethod
    async def get_conversation_context(
        self,
        user_id: str,
        conversation_id: str
    ) -> Optional[Dict]:
        """Get conversation context cache"""
        pass
    
    @abstractmethod
    async def save_conversation_context(
        self,
        user_id: str,
        conversation_id: str,
        profile_chunks: List[Dict],
        product_chunks: List[Dict],
        shown_products: List[str],
        ttl_seconds: int = 1200
    ) -> bool:
        """Save conversation context"""
        pass


class IExactSearchEngine(ABC):
    """Interface for exact search (L2)"""
    
    @abstractmethod
    async def search_exact(
        self,
        user_id: str,
        entity_name: str,
        entity_type: str = "product"
    ) -> List[RetrievedChunk]:
        """Exact match search"""
        pass
    
    @abstractmethod
    async def cache_exact_match(
        self,
        user_id: str,
        entity_name: str,
        chunks: List[RetrievedChunk]
    ) -> bool:
        """Cache exact match result"""
        pass


class IMetadataSearchEngine(ABC):
    """Interface for metadata filtering (L3)"""
    
    @abstractmethod
    async def search_metadata(
        self,
        user_id: str,
        filters: Dict[str, Any],
        top_k: int = 10
    ) -> List[RetrievedChunk]:
        """Search by metadata filters"""
        pass


class ISemanticSearchEngine(ABC):
    """Interface for semantic search (L5)"""
    
    @abstractmethod
    async def search_semantic(
        self,
        user_id: str,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[RetrievedChunk]:
        """Semantic vector search"""
        pass


class IValidationEngine(ABC):
    """Interface for chunk validation"""
    
    @abstractmethod
    def validate_chunk(
        self,
        chunk: RetrievedChunk,
        query: str,
        user_id: str,
        min_relevance: float = 0.3
    ) -> ValidationResult:
        """Validate single chunk"""
        pass
    
    @abstractmethod
    def validate_chunks(
        self,
        chunks: List[RetrievedChunk],
        query: str,
        user_id: str,
        min_relevance: float = 0.3
    ) -> List[ValidationResult]:
        """Validate multiple chunks"""
        pass


class IQdrantRepository(ABC):
    """Interface for Qdrant operations"""
    
    @abstractmethod
    async def search(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Vector search with tenant isolation"""
        pass
    
    @abstractmethod
    async def scroll(
        self,
        user_id: str,
        filters: Optional[Dict] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Scroll through records with tenant isolation"""
        pass


class IHierarchicalRetriever(ABC):
    """Interface for L1-L7 hierarchical retrieval orchestrator"""
    
    @abstractmethod
    async def retrieve(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
        query_plan: Any,
        intent: str,
        entities: Dict,
        memory: Optional[Any] = None,
        top_k: int = 8
    ) -> RetrievalResult:
        """Execute hierarchical retrieval with early exit"""
        pass


__all__ = [
    "IRetrievalCache",
    "IConversationCache",
    "IExactSearchEngine",
    "IMetadataSearchEngine",
    "ISemanticSearchEngine",
    "IValidationEngine",
    "IQdrantRepository",
    "IHierarchicalRetriever"
]
