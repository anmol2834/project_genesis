"""
Memory Layer - Interface Contracts
====================================
Strict interfaces for enterprise memory system components.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.memory.schemas import (
    ThreadMemory,
    ConversationContext,
    EntityMemory,
    RetrievalCacheEntry,
    MemorySummary,
    MemoryLoadResult,
    MemoryEnrichmentResult,
    MemorySnapshot,
    MemoryMetrics,
)


# ══════════════════════════════════════════════════════════════════════════════
# HOT MEMORY
# ══════════════════════════════════════════════════════════════════════════════

class IHotMemoryStore(ABC):
    """Interface for Redis-backed hot memory storage"""
    
    @abstractmethod
    async def load(self, thread_id: str, tenant_id: str) -> Optional[ThreadMemory]:
        """Load hot memory (<5ms target)"""
        pass
    
    @abstractmethod
    async def save(self, thread_id: str, tenant_id: str, memory: ThreadMemory, ttl_seconds: int = 86400) -> bool:
        """Save hot memory with TTL"""
        pass
    
    @abstractmethod
    async def delete(self, thread_id: str, tenant_id: str) -> bool:
        """Delete hot memory"""
        pass
    
    @abstractmethod
    async def exists(self, thread_id: str, tenant_id: str) -> bool:
        """Check if memory exists"""
        pass
    
    @abstractmethod
    async def get_size_bytes(self, thread_id: str, tenant_id: str) -> int:
        """Get memory size in bytes"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# COLD MEMORY
# ══════════════════════════════════════════════════════════════════════════════

class IColdMemoryStore(ABC):
    """Interface for PostgreSQL-backed cold memory storage"""
    
    @abstractmethod
    async def load(self, thread_id: str, tenant_id: str) -> Optional[MemorySummary]:
        """Load cold memory summary"""
        pass
    
    @abstractmethod
    async def save(self, summary: MemorySummary) -> bool:
        """Save conversation summary to cold storage"""
        pass
    
    @abstractmethod
    async def search(self, tenant_id: str, filters: Dict[str, Any], limit: int = 10) -> List[MemorySummary]:
        """Search historical conversations"""
        pass
    
    @abstractmethod
    async def get_user_history(self, tenant_id: str, limit: int = 10) -> List[MemorySummary]:
        """Get user's conversation history"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATION STATE
# ══════════════════════════════════════════════════════════════════════════════

class IConversationStateEngine(ABC):
    """Interface for conversation state machine"""
    
    @abstractmethod
    def compute_state(
        self,
        current_state: str,
        intent: str,
        sub_intent: str,
        turn_count: int,
        entities: Dict[str, Any]
    ) -> str:
        """Compute new conversation state"""
        pass
    
    @abstractmethod
    def compute_stage(
        self,
        current_stage: str,
        intent: str,
        turn_count: int
    ) -> str:
        """Compute funnel stage"""
        pass
    
    @abstractmethod
    def should_transition(
        self,
        current_state: str,
        intent: str,
        sub_intent: str
    ) -> bool:
        """Check if state transition should occur"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

class IMemoryEnricher(ABC):
    """Interface for query enrichment using memory"""
    
    @abstractmethod
    def enrich_query(
        self,
        query: str,
        keywords: List[str],
        memory: Optional[ThreadMemory],
        is_continuation: bool,
        content: str
    ) -> MemoryEnrichmentResult:
        """Enrich query with memory context"""
        pass
    
    @abstractmethod
    def is_continuation(self, content: str, memory: Optional[ThreadMemory]) -> bool:
        """Detect if message is a continuation"""
        pass
    
    @abstractmethod
    def is_affirmative(self, content: str) -> bool:
        """Detect affirmative responses"""
        pass
    
    @abstractmethod
    def resolve_references(
        self,
        query: str,
        memory: ThreadMemory
    ) -> str:
        """Resolve references like 'the first one', 'that product'"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ENTITY GRAPH
# ══════════════════════════════════════════════════════════════════════════════

class IEntityGraph(ABC):
    """Interface for entity continuity tracking"""
    
    @abstractmethod
    async def track_entity(
        self,
        thread_id: str,
        tenant_id: str,
        entity_type: str,
        entity_value: str,
        context: str
    ) -> EntityMemory:
        """Track entity mention"""
        pass
    
    @abstractmethod
    async def get_entities(
        self,
        thread_id: str,
        tenant_id: str,
        entity_type: Optional[str] = None
    ) -> List[EntityMemory]:
        """Get tracked entities"""
        pass
    
    @abstractmethod
    async def resolve_reference(
        self,
        thread_id: str,
        tenant_id: str,
        reference: str,
        entity_type: Optional[str] = None
    ) -> Optional[str]:
        """Resolve entity reference"""
        pass
    
    @abstractmethod
    async def get_related_entities(
        self,
        thread_id: str,
        tenant_id: str,
        entity_value: str
    ) -> List[str]:
        """Get related entities"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# RETRIEVAL CACHE
# ══════════════════════════════════════════════════════════════════════════════

class IRetrievalCache(ABC):
    """Interface for retrieval result caching"""
    
    @abstractmethod
    async def get(
        self,
        cache_key: str,
        tenant_id: str
    ) -> Optional[RetrievalCacheEntry]:
        """Get cached retrieval result"""
        pass
    
    @abstractmethod
    async def set(
        self,
        cache_key: str,
        tenant_id: str,
        entry: RetrievalCacheEntry,
        ttl_seconds: int = 1200
    ) -> bool:
        """Cache retrieval result"""
        pass
    
    @abstractmethod
    async def invalidate(
        self,
        cache_key: str,
        tenant_id: str
    ) -> bool:
        """Invalidate cache entry"""
        pass
    
    @abstractmethod
    async def should_skip_retrieval(
        self,
        thread_id: str,
        tenant_id: str,
        intent: str,
        sub_intent: str
    ) -> bool:
        """Determine if retrieval can be skipped"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY PRIORITY
# ══════════════════════════════════════════════════════════════════════════════

class IMemoryPriority(ABC):
    """Interface for memory priority selection"""
    
    @abstractmethod
    def prioritize(
        self,
        memory: ThreadMemory,
        token_budget: int
    ) -> Dict[str, Any]:
        """Prioritize memory items within token budget"""
        pass
    
    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        pass
    
    @abstractmethod
    def compress_memory(
        self,
        memory: ThreadMemory,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Compress memory to fit token budget"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARIZATION
# ══════════════════════════════════════════════════════════════════════════════

class IMemorySummarizer(ABC):
    """Interface for conversation summarization"""
    
    @abstractmethod
    async def summarize(
        self,
        thread_id: str,
        tenant_id: str,
        messages: List[Dict[str, Any]],
        memory: ThreadMemory
    ) -> MemorySummary:
        """Generate conversation summary"""
        pass
    
    @abstractmethod
    async def extract_key_facts(
        self,
        messages: List[Dict[str, Any]],
        memory: ThreadMemory
    ) -> List[str]:
        """Extract key facts from conversation"""
        pass
    
    @abstractmethod
    async def should_summarize(
        self,
        memory: ThreadMemory
    ) -> bool:
        """Determine if conversation should be summarized"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY SNAPSHOTS
# ══════════════════════════════════════════════════════════════════════════════

class IMemorySnapshotGenerator(ABC):
    """Interface for generating memory snapshots"""
    
    @abstractmethod
    def generate_snapshot(
        self,
        memory: ThreadMemory,
        conversation_context: Optional[ConversationContext] = None
    ) -> MemorySnapshot:
        """Generate memory snapshot for handoff"""
        pass
    
    @abstractmethod
    def compress_for_handoff(
        self,
        memory: ThreadMemory,
        max_size: int = 2000
    ) -> str:
        """Compress memory for human agent"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY ORCHESTRATION
# ══════════════════════════════════════════════════════════════════════════════

class IMemoryOrchestrator(ABC):
    """Interface for central memory coordinator"""
    
    @abstractmethod
    async def load_memory(
        self,
        thread_id: str,
        tenant_id: str,
        include_cold: bool = False,
        include_entities: bool = True
    ) -> MemoryLoadResult:
        """Load memory from all sources"""
        pass
    
    @abstractmethod
    async def save_memory(
        self,
        thread_id: str,
        tenant_id: str,
        memory: ThreadMemory,
        save_to_cold: bool = False
    ) -> bool:
        """Save memory to appropriate stores"""
        pass
    
    @abstractmethod
    async def update_memory(
        self,
        thread_id: str,
        tenant_id: str,
        intent: str,
        sub_intent: str,
        retrieved_products: List[str],
        category: str,
        ai_reply: str,
        action: str,
        entities: Dict[str, Any]
    ) -> ThreadMemory:
        """Update memory after turn"""
        pass
    
    @abstractmethod
    async def enrich_query(
        self,
        thread_id: str,
        tenant_id: str,
        query: str,
        keywords: List[str],
        content: str
    ) -> MemoryEnrichmentResult:
        """Enrich query with memory"""
        pass
    
    @abstractmethod
    async def generate_snapshot(
        self,
        thread_id: str,
        tenant_id: str
    ) -> MemorySnapshot:
        """Generate memory snapshot"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# OBSERVABILITY
# ══════════════════════════════════════════════════════════════════════════════

class IMemoryMetrics(ABC):
    """Interface for memory observability"""
    
    @abstractmethod
    async def record_load(self, latency_ms: float, source: str) -> None:
        """Record memory load latency"""
        pass
    
    @abstractmethod
    async def record_save(self, latency_ms: float) -> None:
        """Record memory save latency"""
        pass
    
    @abstractmethod
    async def record_cache_hit(self, cache_type: str) -> None:
        """Record cache hit"""
        pass
    
    @abstractmethod
    async def record_cache_miss(self, cache_type: str) -> None:
        """Record cache miss"""
        pass
    
    @abstractmethod
    async def get_metrics(self, tenant_id: str) -> MemoryMetrics:
        """Get memory metrics"""
        pass


__all__ = [
    "IHotMemoryStore",
    "IColdMemoryStore",
    "IConversationStateEngine",
    "IMemoryEnricher",
    "IEntityGraph",
    "IRetrievalCache",
    "IMemoryPriority",
    "IMemorySummarizer",
    "IMemorySnapshotGenerator",
    "IMemoryOrchestrator",
    "IMemoryMetrics",
]
