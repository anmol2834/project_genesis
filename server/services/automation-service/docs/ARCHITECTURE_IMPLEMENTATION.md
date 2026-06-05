# Automation Service - Architecture Implementation

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Architectural Principles](#architectural-principles)
3. [System Architecture](#system-architecture)
4. [Pipeline Flow](#pipeline-flow)
5. [Module Responsibilities](#module-responsibilities)
6. [Data Flow](#data-flow)
7. [Multi-Tenant Isolation](#multi-tenant-isolation)
8. [Infrastructure Integration](#infrastructure-integration)
9. [Performance & Scalability](#performance--scalability)
10. [Deployment Strategy](#deployment-strategy)
11. [Future Implementation Phases](#future-implementation-phases)

---

## Executive Summary

The **Automation Service v2.0** is a complete architectural rebuild designed for:

- **Ultra-fast multi-tenant AI automation** (<5s end-to-end latency)
- **Near-zero hallucination RAG** (grounded retrieval with validation)
- **High-scale business handling** (100K–1M conversations/day)
- **Enterprise conversation intelligence** (memory-driven reasoning)
- **Horizontal scalability** (stateless workers, event-driven architecture)
- **Reasoning-first RAG pipeline** (multi-stage retrieval with early exit)

This is NOT just another chatbot backend. This is an **AI Operating System for Businesses**.

### Key Design Decisions

1. **Event-Driven Architecture**: Redis Streams with consumer groups for exactly-once delivery
2. **Separation of Concerns**: 9 independent layers, each replaceable
3. **Tenant Isolation**: Every query, cache, retrieval filtered by user_id
4. **Deterministic Retrieval**: L1-L7 hierarchical retrieval with cache-first strategy
5. **Grounded-Only Generation**: LLM only generates from retrieved chunks, never from knowledge
6. **Memory-Driven Reasoning**: Conversation memory enriches every stage
7. **Intelligent Handoff**: Multi-signal confidence-based escalation

---

## Architectural Principles

### 1. Separation of Concerns
Each layer has ONE responsibility:
- **orchestration/**: Coordinates pipeline, NO business logic
- **memory/**: Conversation continuity, NO retrieval
- **intelligence/**: Intent understanding, NO generation
- **retrieval/**: Data fetching, NO reasoning
- **llm/**: Generation ONLY from retrieved data
- **handoff/**: Escalation decisions, NO generation

### 2. Modular AI Pipeline
Every AI component is independently replaceable:
- Swap OpenAI → Anthropic → Local LLM
- Swap e5-base-v2 → OpenAI embeddings → Cohere
- Swap Qdrant → Pinecone → Weaviate
- NO vendor lock-in

### 3. Stateless Worker Design
Workers are completely stateless:
- All state in Redis (hot) or PostgreSQL (cold)
- Workers can crash and restart without data loss
- Horizontal scaling by adding workers
- No sticky sessions, no affinity routing

### 4. Tenant Isolation
EVERY operation is tenant-aware:
```python
# WRONG
results = qdrant.search(query_vector, limit=10)

# RIGHT
results = qdrant.search(
    query_vector, 
    limit=10,
    query_filter=Filter(must=[FieldCondition(key="user_id", match=user_id)])
)
```

### 5. Retrieval Determinism
Same query → same results:
- L1: Conversation cache (Redis) — instant
- L2: Exact match cache (Redis) — <5ms
- L3: Metadata filter (Qdrant) — <50ms
- L4: BM25 lexical (in-memory) — <10ms
- L5: Semantic vector (Qdrant) — <300ms
- L6: Hybrid fusion (RRF) — <10ms
- L7: Reranking (optional GPU) — <200ms

Early exit when high-confidence data found.

### 6. Memory-Driven Reasoning
Every stage enhanced by conversation memory:
- **Intelligence**: Inherit intent from previous turn
- **Retrieval**: Query enrichment with context
- **LLM**: Include conversation summary
- **Handoff**: Consider engagement history

### 7. Horizontal Scalability
Scale each component independently:
- Add workers → handle more messages
- Add GPUs → faster embeddings
- Add Qdrant nodes → more storage
- Add Redis replicas → more cache hits

### 8. Async-First Architecture
Everything is async:
```python
# Parallel execution
qu, memory, cache = await asyncio.gather(
    query_understand(content),
    load_memory(thread_id),
    get_cached_response(cache_key),
)
```

### 9. GPU/CPU Hybrid Support
Automatic device detection:
- GPU available → use for embeddings + reranking
- CPU only → HTTP delegation to GPU worker OR CPU fallback

### 10. Zero Hardcoded Business Logic
NO product names, prices, categories in code:
```python
# WRONG
if "AeroCam X1" in message:
    return get_product("AeroCam X1")

# RIGHT
entities = extract_entities(message)  # dynamic
if entities.product_name:
    return retrieve_by_name(user_id, entities.product_name)
```

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Email Service                               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │
│  │ Gmail Fetch  │   │Outlook Fetch │   │ SMTP Fetch   │           │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘           │
│         │                   │                   │                    │
│         └───────────────────┴───────────────────┘                    │
│                             │                                        │
│                   ┌─────────▼─────────┐                             │
│                   │  AI Handoff Worker │                             │
│                   └─────────┬─────────┘                             │
└─────────────────────────────┼─────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  Redis Streams      │
                   │  automation_events  │
                   └──────────┬──────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────────┐
│                   Automation Service v2.0                          │
│                              │                                      │
│         ┌────────────────────▼────────────────────┐               │
│         │   messaging/stream_consumer             │               │
│         │   (Consumer Group: exactly-once)        │               │
│         └────────────────────┬────────────────────┘               │
│                              │                                      │
│         ┌────────────────────▼────────────────────┐               │
│         │   orchestration/pipeline                │               │
│         │   (Async parallel execution)            │               │
│         └──┬──────┬──────┬──────┬──────┬──────┬──┘               │
│            │      │      │      │      │      │                    │
│    ┌───────▼──┐ ┌▼──────▼┐  ┌─▼──────▼─┐  ┌─▼────────┐          │
│    │ memory/  │ │intellig│  │retrieval/│  │   llm/   │          │
│    │ hot+cold │ │ence/   │  │L1-L7 hier│  │ grounded │          │
│    └──────────┘ │intent+ │  │archical  │  │ prompt   │          │
│                  │entity  │  │retrieval │  │ builder  │          │
│                  └────────┘  └──────────┘  └─────┬────┘          │
│                                                   │                 │
│                             ┌─────────────────────▼───────┐        │
│                             │   handoff/                  │        │
│                             │   confidence-based          │        │
│                             │   escalation                │        │
│                             └─────────────┬───────────────┘        │
│                                           │                         │
│         ┌─────────────────────────────────▼────────────┐          │
│         │   messaging/stream_producer                  │          │
│         │   (Response dispatch)                        │          │
│         └─────────────────────────────────┬────────────┘          │
└───────────────────────────────────────────┼───────────────────────┘
                                            │
                   ┌────────────────────────▼──────────────┐
                   │  Email Service                        │
                   │  (Send reply via SMTP/Gmail/Outlook) │
                   └───────────────────────────────────────┘
```

### Infrastructure Dependencies

```
┌────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                   │
│                                                            │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │PostgreSQL │  │  Redis   │  │  Qdrant  │  │ OpenAI  │ │
│  │  (cold)   │  │  (hot)   │  │ (vector) │  │  (LLM)  │ │
│  └───────────┘  └──────────┘  └──────────┘  └─────────┘ │
│       ▲              ▲             ▲             ▲        │
│       │              │             │             │        │
│  ┌────┴──────────────┴─────────────┴─────────────┴────┐  │
│  │          shared/ (reusable across services)        │  │
│  │  • database/postgres.py                            │  │
│  │  • cache/redis_client.py                           │  │
│  │  • vector_db/qdrant_client.py                      │  │
│  │  • config/settings.py                              │  │
│  │  • logger/logging_config.py                        │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## Pipeline Flow

### End-to-End Request Flow

```
1. EVENT ARRIVES
   └─> Redis Streams: automation_events (from emailservice)

2. STREAM CONSUMER
   └─> XREADGROUP: exactly-once delivery to this worker
   └─> Parse event → validate → enqueue

3. ORCHESTRATION
   └─> Fast checks: rate limit, dedup, stale event
   └─> Load DB context (message, conversation, history)
   
4. FAST PATH CHECK
   └─> Simple reply? (ok, thanks, hi) → SEND IMMEDIATELY
   └─> Complex query → SLOW PATH

5. SLOW PATH - PARALLEL BATCH 1
   ├─> Query Understanding (intent, entities, confidence)
   └─> Memory Load (last 5 turns, conversation state)
   
6. MEMORY ENRICHMENT
   └─> Enrich query with context from memory
   └─> Inherit intent if unknown
   └─> Extract continuation signals

7. PARALLEL BATCH 2 (Redis Pipeline)
   ├─> get_cached_response(cache_key)
   ├─> get_intent_from_pattern(user_id) [if low confidence]
   ├─> get_dynamic_max_tokens(user_id, intent)
   ├─> get_dynamic_send_threshold(user_id)
   └─> get_dynamic_top_k(user_id)

8. CACHE HIT CHECK
   └─> Cached response exists? → SEND IMMEDIATELY

9. L1-L7 HIERARCHICAL RETRIEVAL
   L1: Conv cache (Redis) → instant
   L2: Exact match (Redis) → <5ms
   L3: Metadata filter (Qdrant) → <50ms
   L4: BM25 lexical → <10ms
   L5: Semantic vector (Qdrant) → <300ms
   L6: Hybrid fusion (RRF) → <10ms
   L7: Reranking (optional) → <200ms
   └─> Early exit if high-confidence data found

10. RELEVANCE FILTERING
    └─> RIE: Filter irrelevant items using 4-signal scoring
    └─> Keep only items matching use_case + features

11. DATA INTELLIGENCE
    └─> Compute facts: count, list, price range
    └─> Scroll Qdrant if calculation needed

12. PROMPT BUILDING
    └─> System: Grounded instruction + business context
    └─> User: Query + conversation history
    └─> Token budget enforcement

13. LLM GENERATION
    └─> OpenAI gpt-4o-mini (streaming)
    └─> Reasoning trace logged
    └─> Confidence score computed

14. HALLUCINATION GUARD
    └─> Validate: reply only uses retrieved chunks
    └─> Flag unsupported claims
    └─> Adjust confidence if guard failed

15. DECISION ENGINE
    ├─> Confidence >= send_threshold → SEND
    ├─> Confidence < skip_threshold → SKIP
    └─> Middle zone → DRAFT (store for human review)

16. DISPATCH
    ├─> SEND: messaging/stream_producer → emailservice
    ├─> SKIP: Log + metrics, no action
    └─> DRAFT: Save to database for human review

17. BACKGROUND TASKS
    ├─> Save memory (updated conversation state)
    ├─> Update conv cache (shown products)
    ├─> Collect feedback (for learning engine)
    └─> Log metrics (latency, confidence, tokens)

18. XACK + COMPLETE
    └─> XACK: Remove from Redis pending queue
    └─> Total latency logged
```

### Timing Budget (Target: <5s)

```
Fast checks:            <5ms
DB context load:        <50ms
─────────────────────────────────
PARALLEL BATCH 1:       <3500ms
├─ Query Understanding: <3000ms  (OpenAI API)
└─ Memory Load:         <5ms     (Redis)
─────────────────────────────────
Memory enrichment:      <1ms
─────────────────────────────────
PARALLEL BATCH 2:       <10ms
└─ Redis pipeline:      <10ms    (5 keys)
─────────────────────────────────
L1-L7 Retrieval:        <500ms
├─ L1 Conv cache:       <1ms
├─ L2 Exact match:      <5ms
├─ L3 Metadata:         <50ms
├─ L4 BM25:             <10ms
├─ L5 Semantic:         <300ms
├─ L6 Fusion:           <10ms
└─ L7 Rerank:           <200ms   (optional)
─────────────────────────────────
Relevance filter:       <5ms
Data intelligence:      <200ms   (includes scroll if needed)
Prompt building:        <1ms
─────────────────────────────────
LLM Generation:         <1500ms
─────────────────────────────────
Hallucination guard:    <1ms
Decision:               <1ms
Dispatch:               <200ms   (HTTP to emailservice)
─────────────────────────────────
TOTAL:                  <5000ms
─────────────────────────────────
Background (async):     0ms impact on latency
├─ Save memory
├─ Update cache
└─ Collect feedback
```

---


## Module Responsibilities

### api/ — HTTP Endpoints
**Responsibility**: HTTP interface for health checks, metrics, and internal operations.

**Folders**:
- `health/`: Liveness and readiness probes
- `metrics/`: Prometheus-compatible metrics export
- `internal/`: Internal admin operations (manual replay, cache clear)
- `admin/`: Admin dashboard API (optional future)

**Key Points**:
- Primary interface is Redis Streams, NOT HTTP
- HTTP used ONLY for observability and admin operations
- NO business logic in API layer

---

### core/ — Infrastructure Foundation
**Responsibility**: Cross-cutting concerns used by all layers.

**Folders**:
- `config/`: Service configuration management
- `logging/`: Structured logging with correlation IDs
- `security/`: Tenant isolation enforcement, API key validation
- `constants/`: System-wide constants (NO business constants)
- `exceptions/`: Custom exception hierarchy
- `middleware/`: FastAPI middleware (request ID, timing, CORS)
- `telemetry/`: OpenTelemetry integration (future)
- `lifecycle/`: Startup/shutdown hooks
- `dependency_injection/`: DI container (future)

**Key Points**:
- Imported by ALL other modules
- ZERO business logic
- ZERO external dependencies except shared/

---

### orchestration/ — Pipeline Coordinator
**Responsibility**: Coordinates the entire pipeline from event to response.

**Folders**:
- `pipeline/`: Main pipeline definition and execution
- `state_machine/`: Conversation state transitions
- `execution_engine/`: Async task execution with timeouts
- `routing/`: Event routing based on priority/intent
- `workflow_manager/`: Multi-step workflow orchestration

**Pipeline Stages**:
```python
async def process_event(event: dict) -> dict:
    # Stage 1: Load context
    ctx = await load_message_context(event)
    
    # Stage 2: Fast path check
    if fast_path.can_handle(ctx):
        return await fast_path.handle(ctx)
    
    # Stage 3: Parallel - Intelligence + Memory
    qu, memory = await asyncio.gather(
        intelligence.understand(ctx),
        memory.load(ctx.thread_id),
    )
    
    # Stage 4: Memory enrichment
    qu = memory.enrich(qu, memory)
    
    # Stage 5: Parallel - Cache checks
    cached, dynamic_config = await asyncio.gather(
        cache.get_response(ctx, qu),
        config.get_dynamic(ctx.user_id, qu.intent),
    )
    
    if cached:
        return await dispatch(ctx, cached)
    
    # Stage 6: Retrieval
    chunks = await retrieval.hierarchical_retrieve(ctx, qu, memory)
    
    # Stage 7: LLM
    response = await llm.generate(ctx, qu, chunks)
    
    # Stage 8: Validation
    validated = await llm.validate(response, chunks)
    
    # Stage 9: Decision
    decision = await handoff.decide(validated, qu)
    
    # Stage 10: Dispatch
    result = await messaging.dispatch(ctx, decision)
    
    # Background: Memory + Feedback
    asyncio.create_task(memory.save(ctx, qu, response))
    asyncio.create_task(feedback.collect(ctx, qu, response))
    
    return result
```

**Key Points**:
- Orchestration coordinates, does NOT implement
- All business logic in specialized layers
- Parallel execution wherever possible
- Observable: every stage emits metrics

---

### memory/ — Conversation Continuity
**Responsibility**: Maintains conversation state and context across turns.

**Folders**:
- `hot_memory/`: Redis-backed recent turns (<5 turns, <5ms access)
- `cold_memory/`: PostgreSQL-backed history (summarized, indexed)
- `summarization/`: Compress old turns into key facts
- `conversation_state/`: Track conversation phase, user prefs
- `memory_priority/`: Relevance scoring for memory retrieval
- `retrieval_cache/`: Cache Qdrant results per conversation

**Memory Structure**:
```python
@dataclass
class ThreadMemory:
    thread_id: str
    turn_count: int
    last_intent: str
    last_sub_intent: str
    last_action: str
    conversation_state: str  # greeting, qualification, pricing, closing
    stage: str              # awareness, consideration, decision
    user_preferences: dict  # extracted constraints
    context_summary: str    # compressed history
    last_topic: str         # last discussed entity
    recommended_next_actions: list[str]
```

**Memory Lifecycle**:
```
Turn 1: User asks about drones
  └─> memory.last_intent = "interest"
  └─> memory.last_topic = "drones"
  └─> memory.stage = "awareness"

Turn 2: User asks "what about cameras?"
  └─> Inherit context: drones + cameras
  └─> memory.last_topic = "cameras"
  └─> memory.stage = "consideration"

Turn 3: User asks "price?"
  └─> Inherit: knows we're talking about cameras (from Turn 2)
  └─> memory.last_intent = "pricing"
  └─> memory.stage = "decision"
```

**Key Points**:
- Hot memory: <5ms Redis access
- Cold memory: PostgreSQL with summarization
- Memory NEVER stores full message content (that's es_messages table)
- Memory enriches EVERY stage (intelligence, retrieval, LLM)

---

### intelligence/ — Intent Understanding
**Responsibility**: Understands what the user wants and how to retrieve it.

**Folders**:
- `intent_understanding/`: Intent classification (interest, pricing, support, question)
- `entity_extraction/`: Extract products, categories, features, constraints
- `conversation_analysis/`: Analyze engagement, sentiment, urgency
- `query_decomposition/`: Break complex queries into sub-queries
- `query_planning/`: Plan retrieval strategy (exact, semantic, hybrid)
- `intent_routing/`: Route to appropriate workflow
- `confidence_analysis/`: Multi-signal confidence fusion
- `risk_analysis/`: Identify high-risk queries

**Query Understanding Output**:
```python
@dataclass
class QueryUnderstanding:
    intent: Intent                    # interest, pricing, support, question
    sub_intent: str                   # product_detail, count_products, pricing_inquiry
    confidence: float                 # 0.0-1.0
    language: str                     # en, hi, hi-en (Hinglish)
    rewritten_query: str              # optimized for retrieval
    keywords: list[str]               # BM25 keywords
    entities: dict                    # {product_name, category, features}
    calculation_type: str             # none, count, list, price_range
    requires_calculation: bool
    strict_requirements: list[str]    # must-have features
    use_case: str                     # extracted use case
    source: str                       # fast_path, openai, ollama
```

**Query Planning**:
```python
@dataclass
class QueryPlan:
    retrieval_strategy: str           # exact, semantic, hybrid, hierarchical
    memory_dependency: str            # none, low, high
    needs_new_retrieval: bool         # or can reuse cache?
    secondary_queries: list[str]      # for multi-intent
    expected_chunk_types: list[str]   # profile, product, policy
```

**Key Points**:
- Fast path: <100ms for simple intents
- Slow path: OpenAI API for complex understanding
- Memory-enhanced: inherit intent from previous turn
- Multi-lingual: English, Hindi, Hinglish

---

### retrieval/ — Data Fetching
**Responsibility**: Fetch relevant business data from Qdrant with zero hallucination.

**Folders**:
- `exact_search/`: BM25 lexical matching
- `semantic_search/`: Vector similarity via Qdrant
- `metadata_search/`: Structured field filtering
- `hybrid_search/`: Combined exact + semantic
- `fusion/`: RRF score merging
- `reranking/`: Cross-encoder reranking (optional GPU)
- `validation/`: Relevance validation before LLM
- `compression/`: Token budget enforcement
- `qdrant/`: Qdrant client wrapper
- `embeddings/`: Embedding model management (e5-base-v2)
- `retrieval_strategy/`: L1-L7 hierarchical retrieval

**L1-L7 Hierarchical Retrieval**:
```
L1: Conversation Cache (Redis)
    ├─ Profile chunks: business info, tone, policies
    ├─ Recently shown products: avoid repetition
    └─ Latency: <1ms | Hit rate: ~40%

L2: Exact Match Cache (Redis)
    ├─ Product name → product chunk
    ├─ SKU → product chunk
    └─ Latency: <5ms | Hit rate: ~30%

L3: Metadata Filter (Qdrant)
    ├─ category = "Drones"
    ├─ price <= 50000
    └─ Latency: <50ms | Hit rate: ~15%

L4: BM25 Lexical (In-Memory)
    ├─ Keyword matching on retrieved chunks
    └─ Latency: <10ms

L5: Semantic Vector (Qdrant)
    ├─ Vector similarity search
    ├─ Multi-query expansion for robustness
    └─ Latency: <300ms

L6: Hybrid Fusion (RRF)
    ├─ Merge BM25 + vector scores
    ├─ Adaptive weights by query type
    └─ Latency: <10ms

L7: Reranking (Optional GPU)
    ├─ Cross-encoder reranking
    ├─ Only if GPU available
    └─ Latency: <200ms
```

**Early Exit Optimization**:
```python
# Exit early if high-confidence data found in upper layers
if len(chunks) >= top_k and all(c.score > 0.85 for c in chunks[:top_k]):
    return chunks[:top_k]  # Skip semantic search
```

**Key Points**:
- EVERY query filtered by user_id (tenant isolation)
- Deterministic: same query → same results (cache-based)
- Fast: <500ms target
- Zero-hallucination: only return verified chunks

---

### llm/ — Grounded Generation
**Responsibility**: Generate responses ONLY from retrieved data, NEVER from knowledge.

**Folders**:
- `providers/`: OpenAI client, retry logic
- `reasoning/`: Chain-of-thought prompting
- `prompt_builder/`: Construct grounded prompts
- `grounding/`: Inject retrieved chunks into system prompt
- `hallucination_guard/`: Post-generation validation
- `structured_outputs/`: JSON parsing and validation
- `response_validation/`: Completeness, coherence checks
- `prompt_templates/`: Reusable templates by intent
- `token_management/`: Token usage tracking

**Grounded Prompt Structure**:
```
SYSTEM PROMPT:
──────────────────────────────────────────────────────────
You are the AI assistant for {business_name}.

CRITICAL RULES:
1. Use ONLY the business context below. DO NOT use your training knowledge.
2. If information is not in the context, say "I don't have that information."
3. Be specific: use exact product names, prices, features from the context.
4. Never invent features, prices, or capabilities.

BUSINESS CONTEXT:
{profile_chunks}      # Company info, tone, policies
{product_chunks}      # Products matching the query
{conversation_summary}  # Previous turns

USER QUERY:
{user_message}

RESPONSE:
```

**Hallucination Guard**:
```python
def validate(response: str, chunks: list[Chunk]) -> GuardResult:
    """
    Validates that LLM response only uses retrieved data.
    
    Checks:
    1. Product names mentioned exist in chunks
    2. Prices mentioned match chunk data
    3. Features mentioned are in chunk descriptions
    4. No unsupported claims
    """
    issues = []
    
    # Extract product names from response
    mentioned_products = extract_product_names(response)
    chunk_products = {c.metadata.get("name") for c in chunks}
    
    for product in mentioned_products:
        if product not in chunk_products:
            issues.append(f"Mentioned product '{product}' not in context")
    
    # Extract prices from response
    mentioned_prices = extract_prices(response)
    chunk_prices = {c.metadata.get("price") for c in chunks}
    
    for price in mentioned_prices:
        if price not in chunk_prices:
            issues.append(f"Mentioned price '{price}' not in context")
    
    if issues:
        return GuardResult(passed=False, reason="; ".join(issues))
    
    return GuardResult(passed=True)
```

**Key Points**:
- Grounded-only: NO knowledge-based generation
- Observable: log ALL prompts and responses
- Validated: hallucination guard on every output
- Fast: <2s target for generation

---

### handoff/ — Intelligent Escalation
**Responsibility**: Decide when to escalate to humans based on confidence and risk.

**Folders**:
- `escalation/`: Confidence-based escalation rules
- `human_review/`: Queue management for human review
- `ticket_generation/`: Create support tickets
- `confidence_thresholds/`: Dynamic threshold adjustment
- `fallback_responses/`: Pre-approved fallback messages

**Decision Logic**:
```python
def decide(llm_response: LLMResponse, qu: QueryUnderstanding) -> Decision:
    """
    Multi-signal decision fusion.
    
    Signals:
    1. LLM confidence score
    2. QU confidence score
    3. Hallucination guard result
    4. Risk analysis (pricing, legal, technical)
    5. Learning engine feedback (historical accuracy)
    """
    # Dynamic threshold per user
    send_threshold = get_dynamic_send_threshold(user_id)
    
    # Compute final confidence
    final_confidence = (
        0.50 * llm_response.confidence +
        0.30 * qu.confidence +
        0.20 * (1.0 if hallucination_guard.passed else 0.0)
    )
    
    # Risk override
    if is_high_risk_query(qu):
        send_threshold += 0.15  # require higher confidence
    
    # Decision
    if final_confidence >= send_threshold:
        return Decision.SEND
    elif final_confidence < skip_threshold:
        return Decision.SKIP
    else:
        return Decision.DRAFT  # human review
```

**Key Points**:
- Conservative: when in doubt, escalate
- Fast: <10ms decision time
- Transparent: log all decisions for analysis
- Learnable: adjust thresholds from feedback

---

### messaging/ — Event Communication
**Responsibility**: Consume events from emailservice, dispatch responses back.

**Folders**:
- `stream_consumer/`: XREADGROUP consumer with exactly-once delivery
- `stream_producer/`: Publish responses to emailservice
- `redis_streams/`: Redis Streams client wrapper
- `event_processing/`: Event parsing, validation, enrichment
- `dead_letter_queue/`: DLQ management
- `retry_management/`: Exponential backoff retries

**Consumer Group Architecture**:
```
emailservice → XADD automation_events

Worker 1: XREADGROUP automation_group worker-1001
Worker 2: XREADGROUP automation_group worker-1002
Worker 3: XREADGROUP automation_group worker-1003
Worker 4: XREADGROUP automation_group worker-1004

Redis delivers each message to EXACTLY ONE worker.
No race conditions. No duplicates.

Worker 1 processes message → XACK → removes from pending
If Worker 1 crashes → XAUTOCLAIM after 30s → Worker 2 takes over
```

**Zero-Idle-Cost Design**:
```
Idle state:
  └─ Worker sleeps on asyncio.Event (pub/sub wake)
  └─ ZERO Redis commands
  └─ ZERO CPU usage

New message arrives:
  └─ emailservice: XADD + PUBLISH automation:wake
  └─ Worker wakes on pub/sub
  └─ XREADGROUP → get messages
  └─ Process → XACK
  └─ Sleep again
```

**Key Points**:
- Exactly-once delivery via consumer groups
- Zero idle cost (event-driven wakeup)
- Automatic recovery from crashes (XAUTOCLAIM)
- Observable: every event logged with timing

---


## Data Flow

### Conversation Memory Flow
```
Turn 1: User asks "Tell me about your drones"
─────────────────────────────────────────────────────────
1. Load memory (thread_id)
   └─> memory = ThreadMemory(turn_count=0, last_intent="", last_topic="")

2. Query Understanding
   └─> qu.intent = "interest"
   └─> qu.entities = {category: "drones"}

3. Retrieval
   └─> chunks = [AeroCam X1, AgriFly Pro, RescueEye]

4. LLM generates response about 3 drone products

5. Save memory
   └─> memory.turn_count = 1
   └─> memory.last_intent = "interest"
   └─> memory.last_topic = "drones"
   └─> memory.stage = "awareness"
   └─> memory.conversation_state = "product_discovery"

─────────────────────────────────────────────────────────
Turn 2: User asks "what about the first one?"
─────────────────────────────────────────────────────────
1. Load memory (thread_id)
   └─> memory.last_topic = "drones" (from Turn 1)
   └─> memory.shown_products = ["AeroCam X1", "AgriFly Pro", "RescueEye"]

2. Query Understanding
   └─> qu.intent = "follow_up" (low confidence)
   └─> qu.entities = {} (no explicit product name)

3. Memory Enrichment
   └─> Resolve "the first one" → "AeroCam X1" (from memory.shown_products[0])
   └─> qu.rewritten_query = "Tell me about AeroCam X1"
   └─> qu.intent = "question" (inherited from context)

4. Retrieval
   └─> L2 exact match: "AeroCam X1" → cache HIT
   └─> chunks = [AeroCam X1 full details]

5. LLM generates response about AeroCam X1

6. Save memory
   └─> memory.turn_count = 2
   └─> memory.last_intent = "question"
   └─> memory.last_topic = "AeroCam X1"
   └─> memory.stage = "consideration"
```

### Redis Strategy
```
┌─────────────────────────────────────────────────────────┐
│                      Redis Usage                        │
└─────────────────────────────────────────────────────────┘

HOT MEMORY (Conversation State)
─────────────────────────────────
Key Pattern: automation:memory:{thread_id}
TTL: 24 hours
Structure: JSON string
Example:
  automation:memory:thread-12345
  {
    "turn_count": 3,
    "last_intent": "pricing",
    "last_topic": "AeroCam X1",
    "conversation_state": "negotiation",
    "stage": "decision",
    ...
  }

EXACT MATCH CACHE
─────────────────────────────────
Key Pattern: automation:exact:{user_id}:{product_name_hash}
TTL: 7 days
Structure: JSON string (chunk)
Example:
  automation:exact:user-789:a3f4b2c1
  {
    "content": "AeroCam X1 is a...",
    "score": 1.0,
    "chunk_type": "product_service",
    ...
  }

RESPONSE CACHE
─────────────────────────────────
Key Pattern: automation:cache:{user_id}:{intent}:{content_hash}
TTL: 5 minutes
Structure: Plain text (AI reply)
Example:
  automation:cache:user-789:pricing:a3f4b2c1
  "The AeroCam X1 is priced at ₹45,000..."

CONVERSATION CACHE (Conv Context)
─────────────────────────────────
Key Pattern: automation:conv:{user_id}:{conversation_id}
TTL: 24 hours
Structure: JSON string
Example:
  automation:conv:user-789:conv-12345
  {
    "profile": [{chunk1}, {chunk2}],
    "products": [{prod1}, {prod2}],
    "shown_products": ["AeroCam X1"],
    "turn": 3
  }

EMBEDDING CACHE
─────────────────────────────────
Key Pattern: automation:emb:{user_id}:{sha256[:24]}
TTL: 24 hours
Structure: JSON array (vector)
Example:
  automation:emb:user-789:a3f4b2c1d5e6f7g8h9i0
  [0.123, -0.456, 0.789, ...]

LEARNING ENGINE STATE
─────────────────────────────────
Key Pattern: automation:learn:{metric}:{user_id}[:{intent}]
TTL: 30 days
Examples:
  automation:learn:topk:user-789           → "12"
  automation:learn:maxtokens:user-789:pricing → "350"
  automation:learn:send_thresh:user-789    → "0.58"

PATTERN RECOGNITION
─────────────────────────────────
Key Pattern: automation:fb:patterns:{user_id}
TTL: 30 days
Structure: JSON object (query → intent mapping)
Example:
  automation:fb:patterns:user-789
  {
    "tell me about your services": "interest",
    "what's the price": "pricing",
    "how does it work": "question"
  }

DEDUPLICATION LOCK
─────────────────────────────────
Key Pattern: automation:lock:msg:{message_id}
TTL: 1 hour
Structure: "1" (flag)
Purpose: Prevent duplicate processing with multi-worker setup

RATE LIMITING
─────────────────────────────────
Key Pattern: automation:rate:{user_id}
TTL: 60 seconds
Structure: Integer (request count)
Purpose: Enforce rate limits per user

LOAD GAUGE
─────────────────────────────────
Key Pattern: automation:load:active
TTL: 30 seconds
Structure: Integer (active worker count)
Purpose: Load shedding for low-priority messages

REDIS STREAMS
─────────────────────────────────
Stream: automation_events
Consumer Group: automation_group
Consumers: worker-{pid} (one per process)
Purpose: Event ingestion from emailservice

Stream: automation_dlq
Purpose: Dead letter queue for failed messages
```

### Qdrant Strategy
```
┌─────────────────────────────────────────────────────────┐
│                  Qdrant Collection Structure            │
└─────────────────────────────────────────────────────────┘

Collection: business_context
Vector Size: 768 (e5-base-v2)
Distance: Cosine
Indexed: Yes

CHUNK TYPES
─────────────────────────────────
1. profile          — Company info, tone, policies
2. product_service  — Products/services catalog
3. faq              — Frequently asked questions
4. policy           — Pricing, refunds, warranties
5. support          — Technical support, troubleshooting
6. team             — Team members, expertise
7. location         — Office locations, service areas

PAYLOAD STRUCTURE
─────────────────────────────────
{
  "user_id": "uuid",          # Tenant ID (MANDATORY)
  "chunk_type": "product_service",
  "chunk_id": "prod-12345",
  
  # Product-specific
  "name": "AeroCam X1",
  "category": "Drones",
  "price": 45000,
  "currency": "INR",
  "features": ["4K Camera", "GPS", "30min Flight"],
  "use_cases": ["Aerial Photography", "Inspection"],
  
  # Metadata
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-20T14:45:00Z",
  "version": 2,
  
  # Content
  "content": "AeroCam X1 is a professional-grade...",
  "content_hash": "sha256:a3f4b2c1..."
}

RETRIEVAL PATTERNS
─────────────────────────────────
# Pattern 1: Semantic search with tenant filter
results = qdrant.search(
    collection="business_context",
    query_vector=embed("show me drones"),
    limit=10,
    query_filter=Filter(
        must=[
            FieldCondition(key="user_id", match=user_id),
            FieldCondition(key="chunk_type", match="product_service")
        ]
    )
)

# Pattern 2: Metadata filter (exact match)
results = qdrant.scroll(
    collection="business_context",
    scroll_filter=Filter(
        must=[
            FieldCondition(key="user_id", match=user_id),
            FieldCondition(key="name", match="AeroCam X1")
        ]
    ),
    limit=1
)

# Pattern 3: Category + price range
results = qdrant.search(
    collection="business_context",
    query_vector=embed("affordable drones"),
    query_filter=Filter(
        must=[
            FieldCondition(key="user_id", match=user_id),
            FieldCondition(key="category", match="Drones"),
            FieldCondition(key="price", range=Range(lte=50000))
        ]
    )
)

# Pattern 4: Fallback scroll (guarantees results)
# Used when semantic search returns 0 results
results = qdrant.scroll(
    collection="business_context",
    scroll_filter=Filter(
        must=[FieldCondition(key="user_id", match=user_id)]
    ),
    limit=20
)

TENANT ISOLATION ENFORCEMENT
─────────────────────────────────
CRITICAL RULE: EVERY Qdrant query MUST include user_id filter.

# WRONG - leaks data across tenants
results = qdrant.search(query_vector, limit=10)

# RIGHT - tenant-isolated
results = qdrant.search(
    query_vector, 
    limit=10,
    query_filter=Filter(must=[FieldCondition(key="user_id", match=user_id)])
)

# Enforcement in code
class QdrantRepository:
    def search(self, user_id: str, query_vector: list[float], **kwargs):
        if not user_id:
            raise ValueError("user_id is mandatory for tenant isolation")
        
        # Force user_id filter - cannot be bypassed
        query_filter = Filter(must=[
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ])
        
        return self._client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=query_filter,
            **kwargs
        )
```

---

## Multi-Tenant Isolation

### Tenant Isolation Strategy

#### Level 1: Database (PostgreSQL)
```sql
-- ALL queries filtered by user_id
SELECT * FROM es_messages 
WHERE user_id = $1 AND conversation_id = $2;

-- Row-level security (RLS) policy (future)
CREATE POLICY tenant_isolation ON es_messages
  USING (user_id = current_setting('app.current_user_id')::uuid);
```

#### Level 2: Cache (Redis)
```python
# Tenant-scoped keys
key = f"automation:memory:{user_id}:{thread_id}"
key = f"automation:cache:{user_id}:{intent}:{hash}"
key = f"automation:conv:{user_id}:{conversation_id}"

# NO global keys that leak across tenants
# WRONG: key = "automation:cache:pricing:hash"
# RIGHT: key = f"automation:cache:{user_id}:pricing:hash"
```

#### Level 3: Vector DB (Qdrant)
```python
# Mandatory user_id filter on EVERY query
results = qdrant.search(
    query_vector=vector,
    query_filter=Filter(
        must=[FieldCondition(key="user_id", match=user_id)]
    )
)

# Enforcement at client level
class TenantAwareQdrantClient:
    def search(self, user_id: str, **kwargs):
        if not user_id:
            raise TenantIsolationError("user_id required")
        # Force filter injection
        ...
```

#### Level 4: Memory Layer
```python
# Thread ID includes user_id
thread_id = f"{user_id}:{conversation_id}"

# Memory NEVER loads data from other users
def load_memory(thread_id: str) -> ThreadMemory:
    user_id = extract_user_id_from_thread(thread_id)
    # Validate thread_id belongs to user_id
    if not validate_ownership(user_id, thread_id):
        raise TenantIsolationError("Thread ownership violation")
    ...
```

#### Level 5: Observability
```python
# Every log includes user_id
logger.info(
    "Processing message",
    extra={
        "user_id": user_id[:8],  # truncated for privacy
        "conversation_id": conversation_id[:8],
        "message_id": message_id[:12],
    }
)

# Metrics include user_id label
metrics.counter("messages_processed", labels={"user_id": user_id})
```

### Tenant Isolation Testing

```python
# Integration test
async def test_tenant_isolation():
    # User A's data
    await ingest_chunks(user_id="user-A", chunks=[
        {"name": "Product A1", "price": 1000}
    ])
    
    # User B's data
    await ingest_chunks(user_id="user-B", chunks=[
        {"name": "Product B1", "price": 2000}
    ])
    
    # User A queries
    results_A = await retrieval.search(user_id="user-A", query="products")
    assert all(r.metadata["user_id"] == "user-A" for r in results_A)
    assert "Product B1" not in [r.metadata["name"] for r in results_A]
    
    # User B queries
    results_B = await retrieval.search(user_id="user-B", query="products")
    assert all(r.metadata["user_id"] == "user-B" for r in results_B)
    assert "Product A1" not in [r.metadata["name"] for r in results_B]
```

### Data Leakage Prevention Checklist

- [ ] PostgreSQL: ALL queries include `WHERE user_id = $1`
- [ ] Redis: ALL keys include user_id prefix
- [ ] Qdrant: ALL queries include user_id filter
- [ ] Memory: Thread IDs include user_id
- [ ] Cache: Cache keys include user_id
- [ ] Logs: Truncate user_id for privacy (first 8 chars)
- [ ] Metrics: User_id as label (aggregated, not individual tracking)
- [ ] Tests: Integration tests for cross-tenant isolation

---


## Infrastructure Integration

### Integration with Shared Modules

The automation service leverages shared infrastructure modules:

```python
# shared/database/postgres.py
from shared.database import get_db_session

async with get_db_session() as session:
    result = await session.execute(
        text("SELECT * FROM es_messages WHERE user_id = :user_id"),
        {"user_id": user_id}
    )

# shared/cache/redis_client.py
from shared.cache import get_redis

redis = await get_redis()
await redis.setex(f"automation:cache:{key}", ttl, value)

# shared/vector_db/qdrant_client.py
from shared.vector_db import get_qdrant_client

qdrant = get_qdrant_client()
results = qdrant.search(
    collection_name="business_context",
    query_vector=vector,
    query_filter=Filter(must=[FieldCondition(key="user_id", match=user_id)])
)

# shared/logger/logging_config.py
from shared.logger import setup_logging

logger = setup_logging("automation-service")
logger.info("Processing message", extra={"user_id": user_id})

# shared/config/settings.py
from shared.config import get_config

config = get_config()
openai_key = config.OPENAI_API_KEY
redis_url = config.REDIS_URL
```

### Event Flow with EmailService

```
┌─────────────────────────────────────────────────────────┐
│                    EmailService                         │
│                                                         │
│  1. Gmail/Outlook/SMTP Fetch Workers                   │
│     └─> Fetch new emails                               │
│                                                         │
│  2. Filter + Dedup Worker                              │
│     └─> Filter spam, duplicates                        │
│                                                         │
│  3. Storage Worker                                     │
│     └─> Save to es_messages, es_conversations          │
│                                                         │
│  4. AI Handoff Worker                                  │
│     └─> Check: automation_enabled?                     │
│     └─> XADD automation_events                         │
│     └─> PUBLISH automation:wake                        │
└─────────────────────┬───────────────────────────────────┘
                      │
            ┌─────────▼─────────┐
            │  Redis Streams    │
            │ automation_events │
            └─────────┬─────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              Automation Service                         │
│                                                         │
│  1. Stream Consumer (XREADGROUP)                       │
│     └─> Exactly-once delivery per worker               │
│                                                         │
│  2. Orchestration Pipeline                             │
│     └─> Memory → Intelligence → Retrieval → LLM        │
│                                                         │
│  3. Handoff Decision                                   │
│     └─> SEND / SKIP / DRAFT                            │
│                                                         │
│  4. Stream Producer (XADD)                             │
│     └─> Publish response to emailservice               │
└─────────────────────┬───────────────────────────────────┘
                      │
            ┌─────────▼─────────┐
            │  Redis Streams    │
            │   (response)      │
            └─────────┬─────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                EmailService                             │
│                                                         │
│  5. Response Handler                                   │
│     └─> Draft or Send via SMTP/Gmail/Outlook API       │
└─────────────────────────────────────────────────────────┘
```

---

## Performance & Scalability

### Horizontal Scaling Strategy

#### Worker Scaling
```
Single Worker (4 CPU cores):
  └─ 16 concurrent messages (WORKER_CONCURRENCY=16)
  └─ ~320 messages/minute (avg 3s per message)
  └─ ~19K messages/hour

4 Workers (16 CPU cores):
  └─ 64 concurrent messages
  └─ ~1,280 messages/minute
  └─ ~77K messages/hour

20 Workers (80 CPU cores):
  └─ 320 concurrent messages
  └─ ~6,400 messages/minute
  └─ ~384K messages/hour

50 Workers (200 CPU cores):
  └─ 800 concurrent messages
  └─ ~16,000 messages/minute
  └─ ~960K messages/hour = 1M/hour capacity
```

#### GPU Acceleration
```
CPU-only embedding: ~200ms per embed
GPU embedding: ~50ms per embed

CPU-only retrieval pipeline: ~800ms
GPU retrieval pipeline: ~400ms

CPU-only total latency: ~5000ms
GPU total latency: ~3500ms

With 4 GPUs:
  └─ 4x embedding throughput
  └─ 4x retrieval throughput
  └─ 4x total system capacity
```

#### Caching Impact
```
L1 Conv Cache Hit (40%):
  └─ Latency: <100ms (skip retrieval + LLM)
  └─ 40% of queries served in <100ms

L2 Exact Match Cache Hit (30%):
  └─ Latency: <500ms (skip semantic search)
  └─ 30% of queries served in <500ms

Response Cache Hit (20%):
  └─ Latency: <200ms (skip retrieval + LLM)
  └─ 20% of queries served in <200ms

Cache Miss (10%):
  └─ Latency: ~5000ms (full pipeline)
  └─ Only 10% of queries need full pipeline

Effective Average Latency:
  = 0.20 * 200ms   (response cache)
  + 0.40 * 100ms   (conv cache)
  + 0.30 * 500ms   (exact cache)
  + 0.10 * 5000ms  (full pipeline)
  = 40 + 40 + 150 + 500
  = 730ms average
```

### Load Shedding Strategy

```python
# Priority-based load shedding
PRIORITY_HIGH   = 0  # VIP customers, urgent queries
PRIORITY_MEDIUM = 1  # Regular customers
PRIORITY_LOW    = 2  # Demo accounts, testing

# Load gauge
active_load = await get_active_load()

if active_load > MAX_SLOW_PATH_CONCURRENT:
    if priority == PRIORITY_LOW:
        return {"status": "skipped", "reason": "load_shed"}
    elif priority == PRIORITY_MEDIUM:
        # Reduce retrieval quality
        retrieval_top_k = 5  # instead of 8
```

### Backpressure Handling

```python
# Check pending queue depth
queue_depth = await redis.xpending(stream, group)

if queue_depth > 2000:
    # CRITICAL: Drop low-priority messages
    logger.warning("Backpressure CRITICAL | dropping low-priority")
    if message.priority >= PRIORITY_LOW:
        await xack(message_id)  # ACK without processing
        return

elif queue_depth > 500:
    # WARNING: Reduce concurrency
    logger.warning("Backpressure WARNING | reducing concurrency")
    effective_concurrency = WORKER_CONCURRENCY // 2
```

### Database Connection Pooling

```python
# PostgreSQL (shared/database/postgres.py)
engine = create_async_engine(
    database_url,
    pool_size=15,        # base connections
    max_overflow=10,     # burst capacity
    pool_timeout=10,     # fail fast
    pool_pre_ping=True,  # detect stale connections
    pool_recycle=900,    # recycle every 15min
)

# Connection lifecycle
async with get_db_session() as session:
    # Query must complete within session context
    result = await session.execute(query)
    # NEVER hold session during HTTP calls or LLM generation
```

### Redis Connection Pooling

```python
# Redis (shared/cache/redis_client.py)
_redis_pool = ConnectionPool.from_url(
    redis_url,
    max_connections=20,      # per worker
    socket_timeout=15,
    socket_connect_timeout=10,
    socket_keepalive=True,
    retry_on_timeout=True,
)

# With 4 workers: 80 total connections
# With 20 workers: 400 total connections
```

---

## Deployment Strategy

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY shared/ ./shared/

# Non-root user
RUN useradd -m -u 1000 automation && chown -R automation:automation /app
USER automation

EXPOSE 8009

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009", "--workers", "4"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: automation-service
spec:
  replicas: 4
  selector:
    matchLabels:
      app: automation-service
  template:
    metadata:
      labels:
        app: automation-service
    spec:
      containers:
      - name: automation-service
        image: automation-service:2.0.0
        ports:
        - containerPort: 8009
        env:
        - name: WEB_CONCURRENCY
          value: "4"
        - name: WORKER_CONCURRENCY
          value: "16"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8009
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8009
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: automation-service
spec:
  selector:
    app: automation-service
  ports:
  - port: 8009
    targetPort: 8009
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: automation-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: automation-service
  minReplicas: 4
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### GPU Worker Deployment

```yaml
# GPU worker for embeddings
apiVersion: apps/v1
kind: Deployment
metadata:
  name: automation-service-gpu
spec:
  replicas: 2
  selector:
    matchLabels:
      app: automation-service-gpu
  template:
    metadata:
      labels:
        app: automation-service-gpu
    spec:
      containers:
      - name: automation-service
        image: automation-service:2.0.0-gpu
        resources:
          limits:
            nvidia.com/gpu: 1
        env:
        - name: EMBED_DEVICE
          value: "cuda"
        - name: BGE_DEVICE
          value: "cuda"
```

### Environment Variables

```bash
# .env.production
SERVICE_PORT=8009
ENVIRONMENT=production

# Worker Configuration
WEB_CONCURRENCY=4
WORKER_CONCURRENCY=16
BATCH_SIZE=50

# Redis
REDIS_URL=rediss://prod-redis.upstash.io:6379

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@postgres.rds.amazonaws.com:5432/mailautomation

# Qdrant
QDRANT_URL=https://qdrant.prod.company.com:6333

# OpenAI
OPENAI_API_KEY=sk-prod-xxx

# Performance Tuning
MAX_SLOW_PATH_CONCURRENT=32
RETRIEVAL_TOP_K=8
CONFIDENCE_SEND_THRESHOLD=0.55

# GPU (if available)
EMBED_DEVICE=cuda
BGE_DEVICE=cuda
```

---

## Future Implementation Phases

### Phase 1: Core Infrastructure (COMPLETE)
✅ Folder structure
✅ Configuration management
✅ Health checks
✅ Logging integration
✅ Database/Redis/Qdrant connections

### Phase 2: Messaging Layer
🔲 Redis Streams consumer (XREADGROUP)
🔲 Event parsing and validation
🔲 Consumer group management
🔲 Dead letter queue
🔲 Retry management with exponential backoff
🔲 Pub/sub wakeup mechanism

**Target**: Exactly-once event processing from emailservice

### Phase 3: Memory Engine
🔲 Hot memory (Redis-backed conversation state)
🔲 Cold memory (PostgreSQL-backed history)
🔲 Conversation summarization
🔲 Memory priority and relevance scoring
🔲 Retrieval cache per conversation
🔲 Memory enrichment for query understanding

**Target**: Human-like conversation continuity

### Phase 4: Intelligence Layer
🔲 Intent classification (interest, pricing, support, question)
🔲 Entity extraction (products, categories, features)
🔲 Query decomposition for complex queries
🔲 Query planning (exact, semantic, hybrid strategies)
🔲 Confidence analysis (multi-signal fusion)
🔲 Risk analysis (high-risk query detection)

**Target**: Accurate intent understanding with <100ms fast path

### Phase 5: Retrieval Engine
🔲 L1-L7 hierarchical retrieval
🔲 Exact search (BM25 lexical)
🔲 Semantic search (Qdrant vector)
🔲 Metadata filtering
🔲 Hybrid search (BM25 + vector)
🔲 RRF score fusion
🔲 Reranking (optional GPU cross-encoder)
🔲 Relevance validation
🔲 Context compression
🔲 Embedding management (e5-base-v2)
🔲 GPU/CPU auto-detection

**Target**: <500ms retrieval with deterministic results

### Phase 6: LLM Layer
🔲 OpenAI provider (gpt-4o-mini)
🔲 Grounded prompt builder
🔲 Chain-of-thought reasoning
🔲 Hallucination guard (post-generation validation)
🔲 Response validation (completeness, coherence)
🔲 Token management and budget enforcement
🔲 Prompt templates by intent
🔲 Structured output parsing

**Target**: <2s generation with zero hallucination

### Phase 7: Handoff Layer
🔲 Confidence-based escalation rules
🔲 Risk-based escalation (pricing, legal, technical)
🔲 Human review queue management
🔲 Ticket generation for escalated queries
🔲 Dynamic threshold adjustment
🔲 Fallback responses for low-confidence scenarios

**Target**: Conservative escalation with <10ms decision time

### Phase 8: Orchestration Layer
🔲 Pipeline coordinator
🔲 Parallel execution engine
🔲 State machine for conversation phases
🔲 Event routing by priority/intent
🔲 Workflow manager (onboarding, support, sales)
🔲 Load balancing and backpressure handling

**Target**: <5s end-to-end latency with 95th percentile

### Phase 9: Observability
🔲 Prometheus metrics export
🔲 Structured logging with correlation IDs
🔲 OpenTelemetry tracing (distributed tracing)
🔲 Grafana dashboards
🔲 Alerting (PagerDuty, Slack)
🔲 Performance profiling

**Target**: Full observability for debugging and optimization

### Phase 10: Learning Engine
🔲 Dynamic threshold adjustment from feedback
🔲 Pattern recognition (query → intent mapping)
🔲 User-specific configuration learning
🔲 A/B testing framework
🔲 Model performance tracking
🔲 Continuous improvement loop

**Target**: Self-improving system that learns from human feedback

### Phase 11: Advanced Features
🔲 Multi-step reasoning for complex queries
🔲 Tool use (calculator, calendar, CRM integration)
🔲 Voice note support (Whisper integration)
🔲 Image understanding (GPT-4 Vision)
🔲 Multi-lingual support beyond English/Hindi
🔲 Real-time streaming responses
🔲 Proactive engagement (follow-ups, reminders)

**Target**: Enterprise-grade conversational AI platform

### Phase 12: Scale & Performance
🔲 GPU cluster for embeddings
🔲 Multi-region deployment
🔲 Global load balancing
🔲 Read replicas for PostgreSQL
🔲 Redis cluster mode
🔲 Qdrant sharding
🔲 CDN for static assets
🔲 Edge caching

**Target**: 10M+ conversations/day globally

---

## Migration Strategy

### Migrating from Old automationservice

```python
# Step 1: Deploy new automation-service v2.0 alongside old automationservice
# Both services run in parallel, new service in shadow mode (no actual sends)

# Step 2: Duplicate events to both services
# emailservice AI Handoff Worker publishes to BOTH streams:
#   - automation_events (new service)
#   - automationservice_events (old service)

# Step 3: Compare outputs (shadow mode)
# Log differences between old and new responses
# Alert if confidence divergence > 0.20

# Step 4: Gradual rollout (canary deployment)
# Route 5% of traffic to new service (actual sends)
# Monitor: latency, error rate, confidence scores, escalation rate

# Step 5: Scale up
# 5% → 25% → 50% → 75% → 100%
# Rollback if error rate > 0.5% or latency > 10s

# Step 6: Decommission old service
# Stop old automationservice workers
# Archive old code for reference
```

---

## Conclusion

The **Automation Service v2.0** is designed from the ground up for:

1. **Ultra-fast performance**: <5s end-to-end with aggressive caching
2. **Near-zero hallucination**: Grounded-only generation with validation
3. **Horizontal scalability**: Stateless workers, event-driven architecture
4. **Multi-tenant isolation**: Every layer enforces tenant boundaries
5. **Enterprise reliability**: Exactly-once delivery, automatic recovery
6. **Observable**: Full metrics, logs, and traces for debugging
7. **Extensible**: Every component independently replaceable

This is NOT a refactor. This is a **complete architectural rebuild** that positions the automation service as the foundation for an AI Operating System for Businesses.

The modular design enables:
- Independent scaling of each layer
- GPU acceleration where it matters
- Gradual rollout without disruption
- Continuous improvement through learning
- Future expansion to voice, vision, and multi-modal AI

**Next Steps**: Implement Phase 2 (Messaging Layer) to enable event processing from emailservice.

