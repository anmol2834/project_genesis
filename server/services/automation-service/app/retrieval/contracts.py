"""
Retrieval Layer - Interface Contracts
======================================
Defines contracts for deterministic retrieval.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetrievedChunk:
    """A single retrieved chunk"""
    content: str
    score: float
    chunk_type: str
    chunk_id: str
    source: str  # exact, semantic, cache
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Result of retrieval operation"""
    chunks: list[RetrievedChunk]
    total_retrieved: int
    cache_hit: bool
    latency_ms: float
    layers_used: list[str]  # L1, L2, L3, etc.
    early_exit: bool


class IRetriever(ABC):
    """Interface for retrieval strategies"""
    
    @abstractmethod
    async def retrieve(
        self,
        user_id: str,
        query: str,
        query_vector: Optional[list[float]] = None,
        top_k: int = 10,
        filters: Optional[dict] = None
    ) -> list[RetrievedChunk]:
        """
        Retrieve relevant chunks.
        
        Args:
            user_id: Tenant ID (MANDATORY)
            query: Query text
            query_vector: Optional pre-computed vector
            top_k: Number of results
            filters: Optional metadata filters
            
        Returns:
            List of retrieved chunks
        """
        pass


class IReranker(ABC):
    """Interface for result reranking"""
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 5
    ) -> list[RetrievedChunk]:
        """
        Rerank retrieved chunks.
        
        Args:
            query: Original query
            chunks: Retrieved chunks
            top_n: Number of top results to return
            
        Returns:
            Reranked chunks
        """
        pass


class IRelevanceValidator(ABC):
    """Interface for relevance validation"""
    
    @abstractmethod
    def validate(
        self,
        chunk: RetrievedChunk,
        query: str,
        threshold: float = 0.30
    ) -> bool:
        """
        Validate chunk relevance.
        
        Args:
            chunk: Retrieved chunk
            query: Original query
            threshold: Minimum relevance score
            
        Returns:
            True if relevant, False otherwise
        """
        pass


class IEmbeddingModel(ABC):
    """Interface for embedding generation"""
    
    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        batch_size: int = 32
    ) -> list[list[float]]:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            
        Returns:
            List of embedding vectors
        """
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Return embedding dimension"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return model identifier"""
        pass


class IHierarchicalRetriever(ABC):
    """Interface for L1-L7 hierarchical retrieval"""
    
    @abstractmethod
    async def retrieve(
        self,
        user_id: str,
        conversation_id: str,
        query_plan: Any,
        query_understanding: Any,
        memory: Optional[Any] = None,
        top_k: int = 8
    ) -> RetrievalResult:
        """
        Execute hierarchical retrieval with early exit.
        
        Layers:
        L1: Conv cache (Redis) - instant
        L2: Exact match (Redis) - <5ms
        L3: Metadata filter (Qdrant) - <50ms
        L4: BM25 lexical - <10ms
        L5: Semantic vector (Qdrant) - <300ms
        L6: Hybrid fusion (RRF) - <10ms
        L7: Reranking (optional GPU) - <200ms
        
        Args:
            user_id: Tenant ID
            conversation_id: Conversation identifier
            query_plan: Query plan from intelligence layer
            query_understanding: QU result
            memory: Conversation memory
            top_k: Target number of results
            
        Returns:
            Retrieval result with metrics
        """
        pass
