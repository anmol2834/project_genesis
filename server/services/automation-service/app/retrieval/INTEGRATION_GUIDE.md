# RETRIEVAL LAYER - INTEGRATION GUIDE

## Quick Start

### Initialize Retrieval System

```python
from app.retrieval import get_hierarchical_retriever
from shared.cache import get_redis
import os

# Get Redis client
redis = await get_redis()

# Get Qdrant configuration
qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
collection_name = os.getenv("QDRANT_COLLECTION", "business_context")

# Initialize hierarchical retriever (singleton)
retriever = get_hierarchical_retriever(
    redis_client=redis,
    qdrant_url=qdrant_url,
    collection_name=collection_name
)
```

---

## Integration with Orchestration Pipeline

### Complete Pipeline Integration

```python
# orchestration/pipeline/main_orchestrator.py

async def process_event(event: dict) -> dict:
    # ── Phase 1-5: Intelligence & Memory ──────────────────────────────
    intelligence_result, memory = await asyncio.gather(
        intelligence_orchestrator.analyze(content, thread_id, tenant_id),
        memory_orchestrator.load_memory(thread_id, tenant_id)
    )
    
    # ── Phase 6: Hierarchical Retrieval ───────────────────────────────
    from app.retrieval import get_hierarchical_retriever
    
    retriever = get_hierarchical_retriever(redis, qdrant_url, collection)
    
    retrieval_result = await retriever.retrieve(
        user_id=tenant_id,                              # MANDATORY
        conversation_id=conversation_id,                # For L1 cache
        query=intelligence_result.rewritten_query,      # Enriched query
        query_plan=intelligence_result.query_plan,      # From intelligence
        intent=intelligence_result.primary_intent,      # For layer selection
        entities=intelligence_result.entities,          # For exact/metadata
        memory=memory,                                  # For cache decisions
        top_k=8                                         # Target chunks
    )
    
    # ── Phase 7: Validate Retrieval ──────────────────────────────────
    if len(retrieval_result.chunks) == 0:
        logger.warning("Zero chunks retrieved - escalating to human")
        return await handoff.escalate(thread_id, "no_retrieval_results")
    
    if retrieval_result.retrieval_confidence < 0.5:
        logger.warning(f"Low retrieval confidence: {retrieval_result.retrieval_confidence:.2f}")
        # Consider escalation or conservative response
    
    # ── Phase 8: LLM Generation ───────────────────────────────────────
    validated_chunks = retrieval_result.get_validated_chunks()
    
    llm_response = await llm_orchestrator.generate(
        query=intelligence_result.rewritten_query,
        chunks=validated_chunks,
        memory=memory,
        intent=intelligence_result.primary_intent
    )
    
    # ── Phase 9: Response Dispatch ────────────────────────────────────
    return await messaging.dispatch(llm_response)
```

---

## Usage Examples

### Example 1: Simple Product Query

```python
# User: "Tell me about AeroCam X1 pricing"

retrieval_result = await retriever.retrieve(
    user_id="tenant-123",
    conversation_id="conv-456",
    query="AeroCam X1 pricing details",
    query_plan=query_plan,
    intent="pricing",
    entities={"product_name": "AeroCam X1"},
    memory=None,
    top_k=8
)

# Expected flow:
# L1: Cache miss (first query)
# L2: Exact match on "AeroCam X1" → FOUND → Early exit
# Result: 1-3 chunks, latency ~5ms, confidence 0.95
```

---

### Example 2: Continuation Query with Cache Hit

```python
# Turn 1: User: "show me drones"
# AI showed: AeroCam X1, AgriFly Pro, RescueEye

# Turn 2: User: "tell me about the first one"

retrieval_result = await retriever.retrieve(
    user_id="tenant-123",
    conversation_id="conv-456",
    query="tell me about AeroCam X1",  # Resolved by intelligence
    query_plan=query_plan,
    intent="interest",
    entities={"product_name": "AeroCam X1"},
    memory=memory,
    top_k=8
)

# Expected flow:
# L1: Cache HIT → Profile + product chunks from cache → Early exit
# Result: 5-8 chunks, latency <1ms, confidence 0.90
```

---

### Example 3: Metadata Filtering Query

```python
# User: "show me drones under $50,000 with 4K camera"

retrieval_result = await retriever.retrieve(
    user_id="tenant-123",
    conversation_id="conv-456",
    query="drones under $50,000 with 4K camera",
    query_plan=query_plan,
    intent="interest",
    entities={
        "category": "drones",
        "price_max": 50000,
        "features": ["4K"]
    },
    memory=None,
    top_k=8
)

# Expected flow:
# L1: Cache miss
# L2: No exact product name → skip
# L3: Metadata filters → category=drones, price<=50000, features=4K → FOUND
# Result: 3-8 chunks, latency ~30ms, confidence 0.80
```

---

### Example 4: No Results Scenario

```python
# User: "do you sell helicopters?"
# (Business doesn't sell helicopters)

retrieval_result = await retriever.retrieve(
    user_id="tenant-123",
    conversation_id="conv-456",
    query="helicopters for sale",
    query_plan=query_plan,
    intent="interest",
    entities={"category": "helicopters"},
    memory=None,
    top_k=8
)

# Expected flow:
# L1: Cache miss
# L2: No exact match
# L3: Metadata filter on category=helicopters → EMPTY
# L4-L7: Not yet implemented
# Result: 0 chunks, confidence 0.0

# Orchestration should detect and escalate:
if len(retrieval_result.chunks) == 0:
    return await handoff.escalate(thread_id, "unsupported_category")
```

---

## Accessing Retrieval Results

### Get Top Validated Chunks

```python
# Get only validated chunks
validated = retrieval_result.get_validated_chunks()

# Get top N chunks by score
top_5 = retrieval_result.get_top_chunks(n=5)

# Access individual chunks
for chunk in retrieval_result.chunks:
    print(f"Content: {chunk.content[:100]}")
    print(f"Score: {chunk.score}")
    print(f"Source: {chunk.source.value}")
    print(f"Type: {chunk.chunk_type.value}")
    print(f"Validated: {chunk.validated}")
    print(f"Metadata: {chunk.metadata}")
```

### Check Retrieval Metrics

```python
# Performance metrics
print(f"Total latency: {retrieval_result.latency_ms:.1f}ms")
print(f"Layers used: {retrieval_result.layers_used}")
print(f"Layer latencies: {retrieval_result.layer_latencies}")

# Cache performance
print(f"Cache hit: {retrieval_result.cache_hit}")
print(f"Cache hit layer: {retrieval_result.cache_hit_layer}")
print(f"Early exit: {retrieval_result.early_exit}")

# Quality metrics
print(f"Total retrieved: {retrieval_result.total_retrieved}")
print(f"Validation passed: {retrieval_result.validation_passed}")
print(f"Validation rejected: {retrieval_result.validation_rejected}")
print(f"Retrieval confidence: {retrieval_result.retrieval_confidence:.2f}")
```

---

## Updating Conversation Cache

### After Showing Products to User

```python
from app.retrieval.caching import ConversationCacheEngine

conv_cache = ConversationCacheEngine(redis)

# Save conversation context after retrieval
await conv_cache.save_conversation_context(
    user_id=tenant_id,
    conversation_id=conversation_id,
    profile_chunks=profile_chunks,
    product_chunks=product_chunks,
    shown_products=["AeroCam X1", "AgriFly Pro"],
    turn=turn_count
)

# Update shown products incrementally
await conv_cache.update_shown_products(
    user_id=tenant_id,
    conversation_id=conversation_id,
    shown_products=["RescueEye"]  # Adds to existing list
)
```

---

## Error Handling

### Graceful Degradation

```python
try:
    retrieval_result = await retriever.retrieve(...)
    
    if len(retrieval_result.chunks) == 0:
        logger.warning("Zero chunks retrieved")
        # Fall back to general business profile
        retrieval_result = await retrieve_fallback_profile(user_id)
    
    if retrieval_result.retrieval_confidence < 0.5:
        logger.warning("Low confidence retrieval")
        # Add conservative response flag
        conservative_mode = True
    
except Exception as e:
    logger.error(f"Retrieval failed: {e}", exc_info=True)
    # Escalate to human
    return await handoff.escalate(thread_id, "retrieval_error")
```

---

## Performance Monitoring

### Logging Retrieval Metrics

```python
logger.info(
    "Retrieval completed",
    extra={
        "user_id": user_id[:8],
        "conversation_id": conversation_id[:12],
        "query_length": len(query),
        "intent": intent,
        "total_latency_ms": retrieval_result.latency_ms,
        "l1_latency_ms": retrieval_result.layer_latencies.get("L1", 0),
        "l2_latency_ms": retrieval_result.layer_latencies.get("L2", 0),
        "l3_latency_ms": retrieval_result.layer_latencies.get("L3", 0),
        "layers_used": retrieval_result.layers_used,
        "chunks_retrieved": retrieval_result.total_retrieved,
        "chunks_validated": retrieval_result.validation_passed,
        "chunks_rejected": retrieval_result.validation_rejected,
        "cache_hit": retrieval_result.cache_hit,
        "cache_hit_layer": retrieval_result.cache_hit_layer,
        "early_exit": retrieval_result.early_exit,
        "retrieval_confidence": retrieval_result.retrieval_confidence
    }
)
```

---

## Testing Integration

### Integration Test Example

```python
import pytest
from app.retrieval import get_hierarchical_retriever

@pytest.mark.asyncio
async def test_retrieval_integration(redis_client, qdrant_url):
    retriever = get_hierarchical_retriever(redis_client, qdrant_url)
    
    # Test exact match retrieval
    result = await retriever.retrieve(
        user_id="test-tenant",
        conversation_id="test-conv",
        query="AeroCam X1 pricing",
        query_plan=None,
        intent="pricing",
        entities={"product_name": "AeroCam X1"},
        memory=None,
        top_k=5
    )
    
    # Assertions
    assert len(result.chunks) > 0
    assert result.retrieval_confidence > 0.7
    assert all(c.user_id == "test-tenant" for c in result.chunks)
    assert all(c.validated for c in result.chunks)
    assert result.latency_ms < 100  # L1-L3 target
```

---

## Configuration

### Environment Variables

```bash
# From /server/.env

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=business_context
QDRANT_VECTOR_SIZE=768
QDRANT_DISTANCE_METRIC=Cosine

# Redis Configuration
REDIS_URL=rediss://default:password@host:6379

# Retrieval Configuration (optional)
RETRIEVAL_MIN_CHUNKS_EXIT=5          # Early exit threshold
RETRIEVAL_MIN_SCORE_EXIT=0.85        # Early exit score
RETRIEVAL_MIN_RELEVANCE=0.3          # Validation threshold
RETRIEVAL_CONV_CACHE_TTL=1200        # L1 cache TTL (20 min)
RETRIEVAL_EXACT_CACHE_TTL=604800     # L2 cache TTL (7 days)
```

---

## Best Practices

1. **Always provide user_id**: Mandatory for tenant isolation
2. **Use enriched queries**: Pass intelligence-enriched query, not raw input
3. **Provide memory when available**: Enables L1 cache hits
4. **Check retrieval confidence**: Low confidence may need escalation
5. **Validate chunk count**: Zero chunks should trigger fallback
6. **Monitor latencies**: Alert if exceeding 100ms for L1-L3
7. **Update conversation cache**: Save context after showing products
8. **Log retrieval metrics**: Track performance and cache hit rates

---

## Summary

The retrieval layer provides:

✅ **Simple API**: Single `retrieve()` method for all scenarios  
✅ **Automatic optimization**: Early exit, cache-first, layer selection  
✅ **Tenant-safe**: Built-in isolation enforcement  
✅ **Observable**: Complete metrics and logging  
✅ **Validated**: Only quality chunks reach LLM  
✅ **Fast**: <100ms for L1-L3 hierarchical retrieval  

**Integration**: Drop-in replacement for any RAG system with superior performance and safety.

---

*Enterprise-grade retrieval in 3 lines of code.*
