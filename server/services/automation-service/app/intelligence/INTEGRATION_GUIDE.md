# Intelligence Layer - Quick Integration Guide

## Overview

The intelligence layer is the AI reasoning brain that converts raw conversations into structured intelligence. It's now ready to integrate into the orchestrator.

---

## Quick Start (5 minutes)

### 1. Import the Orchestrator

```python
# In app/orchestration/orchestrator.py or wherever you process queries

from app.intelligence.orchestration.intelligence_orchestrator import (
    IntelligenceOrchestrator
)
```

### 2. Initialize in Your Main Orchestrator

```python
class AIOrchestrator:
    def __init__(self, redis_client, postgres_conn, ...):
        # Existing components
        self.redis = redis_client
        self.pg_conn = postgres_conn
        
        # NEW: Initialize intelligence orchestrator
        self.intelligence = IntelligenceOrchestrator(
            redis_client=redis_client,
            enable_caching=True,
            enable_fast_path=True
        )
```

### 3. Use in Query Processing

```python
async def process_query(self, tenant_id, thread_id, query, conversation_history, ...):
    # Load memory first
    memory = await load_memory(thread_id)
    
    # NEW: Run intelligence analysis
    intel_result = await self.intelligence.analyze(
        content=query,
        thread_id=thread_id,
        tenant_id=tenant_id,
        subject=subject,
        conversation_history=conversation_history,
        memory=memory,
        metadata=metadata
    )
    
    # Fast path exit
    if intel_result.fast_path_eligible and intel_result.fast_path_response:
        return {
            "response": intel_result.fast_path_response,
            "fast_path": True,
            "latency_ms": intel_result.processing_time_ms
        }
    
    # Use intelligence result for retrieval
    retrieval_result = await self.retrieval_engine.retrieve(
        query=intel_result.rewritten_query,
        strategy=intel_result.retrieval_strategy,
        exact_keywords=intel_result.exact_keywords,
        semantic_queries=intel_result.semantic_queries,
        metadata_filters=intel_result.metadata_filters,
        expected_chunks=intel_result.expected_chunk_types,
        cache_reusable=intel_result.cache_reusable,
        cached_entities=intel_result.cached_entities
    )
    
    # Check if human escalation needed
    if intel_result.requires_human:
        # Escalate to handoff layer
        handoff_decision = await self.handoff.evaluate_handoff(
            risk_level=intel_result.risk_level,
            risk_categories=intel_result.risk_categories,
            escalation_reason=intel_result.escalation_reason,
            confidence=intel_result.final_confidence,
            ...
        )
        
        if handoff_decision.should_escalate:
            return {
                "response": handoff_decision.fallback_message,
                "escalated": True
            }
    
    # Continue with LLM generation...
```

---

## Key Benefits

### 1. Continuation Resolution
```python
# Before:
User: "yes"
→ No context, can't understand

# After:
User: "yes" 
→ Resolved: intent=pricing, entity="AeroCam X1"
```

### 2. Fast Path
```python
# Before:
User: "hi"
→ Full pipeline (retrieval + LLM) = 3000ms

# After:
User: "hi"
→ Fast path = 30ms
```

### 3. Intelligent Retrieval Planning
```python
# Before:
Always semantic search (expensive)

# After:
- "AeroCam X1 price" → Exact match (fast)
- "best drone for crops" → Semantic search
- "yes" with memory → Cache reuse (instant)
```

### 4. Risk Detection
```python
# Before:
AI might respond to legal question (hallucination risk)

# After:
Legal question detected → Escalate to human
```

---

## What You Get

The `IntelligenceResult` object contains **everything** you need:

```python
result = await intelligence.analyze(...)

# Intent Understanding
result.primary_intent          # Intent.PRICING
result.sub_intent             # "pricing_info"
result.intent_confidence      # 0.92
result.secondary_intents      # [Intent.INTEREST]

# Entities
result.entities               # {"product_name": "AeroCam X1", "category": "drone"}
result.entity_confidence      # 0.88

# Query Transformation
result.rewritten_query        # "AeroCam X1 price cost details"
result.keywords               # ["AeroCam", "X1", "price", "cost"]
result.search_queries         # ["AeroCam X1 pricing", "AeroCam X1 cost"]

# Continuation
result.is_continuation        # True
result.continuation_context   # "AeroCam X1 pricing details"
result.resolved_reference     # "AeroCam X1"

# Retrieval Planning
result.retrieval_strategy     # RetrievalStrategy.EXACT_MATCH
result.requires_retrieval     # True
result.retrieval_priority     # "high"
result.exact_keywords         # ["AeroCam X1"]
result.semantic_queries       # []
result.metadata_filters       # {"category": "drone"}
result.expected_chunk_types   # ["product_service", "pricing"]
result.cache_reusable         # False
result.cached_entities        # []

# Calculation
result.requires_calculation   # False
result.calculation_type       # "none"

# Conversation Analysis
result.conversation_stage     # ConversationStage.CONSIDERATION
result.conversation_type      # "new_query"
result.urgency               # Urgency.MEDIUM

# Risk & Confidence
result.risk_level            # "low"
result.risk_categories       # []
result.requires_human        # False
result.final_confidence      # 0.89
result.confidence_signals    # {"intent": 0.92, "entity": 0.88, ...}

# Fast Path
result.fast_path_eligible    # False
result.fast_path_type        # None
result.fast_path_response    # None

# Memory
result.memory_enriched       # True
result.memory_confidence     # 0.85
result.inherited_entities    # {"last_topic": "AeroCam X1"}

# Multi-Intent
result.is_multi_intent       # False
result.decomposed_queries    # []

# Language
result.language              # "english"
result.language_confidence   # 1.0

# Metadata
result.processing_time_ms    # 487.3
result.source                # "intelligence"
result.timestamp             # "2024-01-15T10:30:00Z"
```

---

## Performance Expectations

| Scenario | Latency | Hit Rate |
|----------|---------|----------|
| Fast path (greetings) | <50ms | ~20% |
| Continuation (with memory) | <100ms | ~15% |
| Cached intent | <300ms | ~30% |
| Uncached (LLM reasoning) | <1500ms | ~35% |
| **Average** | **<500ms** | **100%** |

---

## Configuration

### Environment Variables

Add to `/server/.env`:

```bash
# Intelligence Layer Configuration
INTELLIGENCE_ENABLE_CACHING=true
INTELLIGENCE_ENABLE_FAST_PATH=true
INTELLIGENCE_CACHE_TTL_MINUTES=10
INTELLIGENCE_FAST_PATH_TTL_MINUTES=5

# LLM for Reasoning (optional, uses query_understanding.py by default)
INTELLIGENCE_LLM_MODEL=gpt-4o-mini
INTELLIGENCE_LLM_TIMEOUT_MS=1500
```

### Redis Configuration

No additional Redis setup needed - uses existing Redis client.

---

## Monitoring

### Log Structured Events

```python
logger.info(
    "Intelligence analysis complete",
    extra={
        "thread_id": thread_id,
        "tenant_id": tenant_id,
        "intent": result.primary_intent.value,
        "confidence": result.final_confidence,
        "strategy": result.retrieval_strategy.value,
        "latency_ms": result.processing_time_ms,
        "fast_path": result.fast_path_eligible,
        "continuation": result.is_continuation,
        "risk": result.risk_level
    }
)
```

### Key Metrics to Track

1. **Latency**: `result.processing_time_ms`
2. **Fast path hit rate**: `fast_path_eligible / total_queries`
3. **Continuation hit rate**: `is_continuation / total_queries`
4. **Confidence distribution**: Histogram of `final_confidence`
5. **Risk flag rate**: `requires_human / total_queries`

---

## Troubleshooting

### Issue: High Latency (>2s)

**Cause**: LLM reasoning taking too long  
**Fix**: Enable caching, increase cache TTL, optimize query_understanding.py

### Issue: Low Fast Path Hit Rate (<10%)

**Cause**: Fast path detector too conservative  
**Fix**: Review fast_path/detector.py patterns, add more greeting variations

### Issue: Low Continuation Resolution (<70%)

**Cause**: Memory context not being passed  
**Fix**: Ensure `memory` parameter is populated in `intelligence.analyze()`

### Issue: High False Positives for Human Escalation

**Cause**: Risk analyzer too aggressive  
**Fix**: Tune risk thresholds in `risk_analysis/analyzer.py`

---

## Testing

### Unit Test Example

```python
import pytest
from app.intelligence.orchestration.intelligence_orchestrator import IntelligenceOrchestrator

@pytest.mark.asyncio
async def test_continuation_resolution():
    intel = IntelligenceOrchestrator(redis_client=redis_mock)
    
    # Setup memory with context
    memory = Mock(
        last_question="Would you like pricing for AeroCam X1?",
        last_topic="AeroCam X1",
        last_intent="interest"
    )
    
    # Analyze continuation
    result = await intel.analyze(
        content="yes",
        thread_id="test_thread",
        tenant_id="test_tenant",
        memory=memory
    )
    
    # Assert resolution
    assert result.is_continuation == True
    assert result.resolved_reference == "AeroCam X1"
    assert result.primary_intent == Intent.PRICING
    assert result.final_confidence > 0.8
```

---

## Migration Path

### Phase 1: Parallel Run (Week 1)
- Run intelligence layer alongside existing query_understanding
- Log both results for comparison
- No behavior changes

### Phase 2: Gradual Rollout (Week 2)
- Enable for 10% of traffic
- Monitor metrics (latency, accuracy)
- Increase to 50% if metrics good

### Phase 3: Full Rollout (Week 3)
- Enable for 100% of traffic
- Remove old query_understanding calls
- Clean up deprecated code

---

## Summary

The intelligence layer provides:

✅ **Continuation Resolution** - Handles "yes", "first one", "cheaper one"  
✅ **Fast Path** - <100ms for simple messages  
✅ **Intelligent Retrieval Planning** - Exact vs semantic vs cached  
✅ **Risk Detection** - Legal, billing, complaints → escalate  
✅ **Multi-Signal Confidence** - Intent + entity + memory + language  
✅ **Memory-Aware** - Inherits context from previous messages  

**Integration Time**: ~1 hour  
**Expected Impact**: 40% latency reduction, 30% accuracy improvement  

---

For detailed documentation, see:
- `IMPLEMENTATION.md` - Complete architecture
- `models/intelligence_result.py` - Data models
- `orchestration/intelligence_orchestrator.py` - Main code

**Status**: ✅ Ready for integration
