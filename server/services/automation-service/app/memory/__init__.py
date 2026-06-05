"""
Memory Layer - Enterprise Conversational Memory Operating System
=================================================================

The memory layer provides:
- Ultra-fast hot memory (Redis <5ms)
- Long-term cold memory (PostgreSQL)
- Conversation continuity & context
- Continuation resolution ("yes" → pricing confirmation)
- Entity tracking & reference resolution
- Retrieval cache optimization
- Memory snapshots for handoff
- Token-aware memory loading
- Multi-tenant isolation

Main API:
---------
```python
from app.memory import get_memory_orchestrator

orchestrator = get_memory_orchestrator()

# Load memory
memory = await orchestrator.load_memory(thread_id, tenant_id)

# Enrich query
enriched_query, keywords = await orchestrator.enrich_query(
    thread_id, tenant_id, query, keywords, content, memory
)

# Update memory
memory = await orchestrator.update_memory(
    thread_id, tenant_id, intent, sub_intent,
    retrieved_products, category, ai_reply, action
)

# Generate snapshot for handoff
snapshot = await orchestrator.generate_snapshot(thread_id, tenant_id)
```

Integration with Pipeline:
---------------------------
The memory layer integrates with:
- Intelligence Layer: Query enrichment, continuation resolution
- Retrieval Layer: L1 cache, retrieval cache optimization
- LLM Layer: Token-aware memory loading for prompts
- Handoff Layer: Memory snapshots for human agents
- Orchestration: Central memory coordination

Performance:
------------
- Hot memory load: <5ms (Redis)
- Memory enrichment: <1ms
- Memory update: <10ms
- Snapshot generation: <10ms
- Total overhead: <10ms per request

Architecture:
-------------
See IMPLEMENTATION.md for complete architecture documentation.
"""

# Main API
from app.memory.hot.orchestrator import (
    MemoryOrchestrator,
    get_memory_orchestrator
)

# Schemas (for type hints)
try:
    from app.memory.schemas import (
        ThreadMemory,
        ConversationContext,
        MemorySnapshot,
    )
except ImportError:
    # Fallback to contracts if schemas not available
    from app.memory.contracts import ThreadMemory

# Interfaces (for dependency injection)
try:
    from app.memory.interfaces import (
        IMemoryOrchestrator,
        IHotMemoryStore,
        IMemoryEnricher,
    )
except ImportError:
    pass


__all__ = [
    # Main API
    "MemoryOrchestrator",
    "get_memory_orchestrator",
    
    # Models
    "ThreadMemory",
    "ConversationContext",
    "MemorySnapshot",
]

__version__ = "2.0.0"
__author__ = "Automation Service Team"
__doc_url__ = "https://docs.automation-service.internal/memory"
