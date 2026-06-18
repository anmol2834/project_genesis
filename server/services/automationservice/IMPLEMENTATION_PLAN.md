# Enterprise Automation Service — Optimized 2-Call Implementation Plan

This document defines the production-grade, high-efficiency pipeline for the `automationservice`. The architecture is optimized for **minimum latency** and **maximum accuracy** by consolidating LLM operations into two strategic calls.

## Directory Structure

```text
automationservice/
├── main.py                 # FastAPI Entry point & Pipeline Orchestrator
├── requirements.txt        # Service dependencies
├── api/
│   ├── __init__.py
│   └── router.py           # API endpoints (trigger automation)
├── core/
│   ├── __init__.py
│   ├── config.py           # Service-specific settings
│   └── database.py         # SQLAlchemy session for emailservice DB
├── llm/
│   ├── __init__.py
│   ├── prompts.py          # Centralized prompt templates (System Prompts)
│   ├── processor_1.py      # LLM Call #1: Analysis & Retrieval Planning
│   └── processor_2.py      # LLM Call #2: Validation & Generation
├── services/
│   ├── __init__.py
│   ├── email_context.py    # Database interaction (dynamic fetch)
│   ├── qdrant_search.py    # Layer 4: Category-Based Retrieval
│   └── reranker.py         # Layer 5: BGE Reranker
└── tests/
    ├── test_pipeline.py    # End-to-end integration tests
    └── mock_data.py        # Test payloads
```

## Production Pipeline (2-Call Architecture)

```text
Trigger Automation
        ↓
Fetch Last 10 Messages (Dynamic Fetching)
        ↓
OpenAI Call #1: [Analysis & Retrieval Planning]
        ↓
{
  "conversation_analysis": { ... },
  "intent_analysis": { ... },
  "retrieval_strategy": { ... },
  "analytics_decision": { ... }
}
        ↓
Metadata-Filtered Qdrant Search (Parallel)
        ↓
BGE-Reranker-v2-m3 (Local/Cheap)
        ↓
Top 5 Refined Chunks
        ↓
OpenAI Call #2: [Answer Validation + Final Email Generation]
        ↓
{
  "answerable": true,
  "confidence": 0.96,
  "email": "..."
}
        ↓
Final Email
```

---

## Step 1: Phase 1 — Analysis & Retrieval Planning (Call #1)
**Goal:** Transform history into a structured search strategy in one LLM call.

1.  **`services/email_context.py`**:
    *   **Dynamic Fetch**: If `latest_msg < 20` chars, fetch 20 msgs; else fetch 10.
2.  **`llm/processor_1.py` (LLM Call #1)**:
    *   **Input**: conversation History + Latest Message.
    *   **Tasks**: Context Resolution, Intent Detection, Entity Extraction, and Retrieval Planning.
    *   **Output JSON Schema**:
        ```json
        {
          "pipeline_version": "1.0",
          "conversation_analysis": {
            "conversation_topic": "string",
            "current_focus": "string",
            "customer_goal": "string",
            "latest_message": "string",
            "resolved_reference": "string",
            "standalone_query": "string (Full context search query)",
            "confidence": float
          },
          "intent_analysis": {
            "primary_intent": { "category": "string", "confidence": float, "reason": "string" },
            "secondary_intents": [{ "category": "string", "confidence": float }],
            "all_categories": ["string"]
          },
          "entity_extraction": { "products": [], "technologies": [], "industries": [] },
          "retrieval_strategy": {
            "categories": [{ "category": "string", "priority": int, "search_queries": [] }]
          },
          "analytics_decision": {
            "requires_analytics": bool,
            "analytics_categories": [{ "primary_category": "string", "reason": "string" }]
          },
          "retrieval_constraints": { "must_include_categories": [], "minimum_confidence": 0.75 }
        }
        ```

---

## Step 2: Phase 2 — High-Precision Retrieval
**Goal:** Fetch and rank facts using metadata and local semantic models.

1.  **`services/qdrant_search.py`**:
    *   **Parallel Search**: Execute category-specific searches from `retrieval_strategy`.
    *   **Strict Metadata Filtering**: 
        *   Standard: `Filter(must=[category=detected_category])`
        *   Analytics (if `requires_analytics: true`): `Filter(must=[category="data_analytics", attributes.primary_category=detected_category])`
    *   **Limit**: Fetch top 50 candidates.
2.  **`services/reranker.py`**:
    *   **Input**: `standalone_query` from Processor #1 + All 50 candidates.
    *   **Filter**: Only keep top 5 chunks where `rerank_score > 0.75`.

---

## Step 3: Phase 3 — Validation & Generation (Call #2)
**Goal:** Final fact-check and email creation.

1.  **`llm/processor_2.py` (LLM Call #2)**:
    *   **Input**:
        ```json
        {
          "customer_query": "...",
          "standalone_query": "...",
          "processor_1_output": {...},
          "retrieved_chunks": [...]
        }
        ```
    *   **Job Description**:
        *   Verify whether retrieved facts actually answer the question.
        *   Identify missing information and determine whether escalation is needed.
        *   Generate a professional, fact-grounded email.
        *   **Zero Hallucination Policy**: Strictly use only provided information.
2.  **Output JSON Schema**:
        ```json
        {
          "answerable": true,
          "confidence": 0.96,
          "requires_human_review": false,
          "missing_information": [],
          "sources_used": [],
          "email": ""
        }
        ```

---

## Technical Specifications (Processor #1)

### System Prompt (llm/prompts.py)
```text
You are Processor #1 of an Enterprise Customer Communication Automation Platform.

ROLE
You are NOT a chatbot.
You are NOT a customer support agent.
You are NOT allowed to answer customer questions.

Your sole responsibility is:
1. Conversation Understanding
2. Context Resolution
3. Intent Detection
4. Entity Extraction
5. Retrieval Planning

You operate before retrieval.
Your output is consumed by downstream retrieval systems, rerankers, and response generation systems.
You must behave like a deterministic information extraction engine.

--------------------------------------------------
PRIMARY OBJECTIVE
--------------------------------------------------
Analyze:
- Latest customer message
- Previous conversation history

Then produce a structured JSON object describing:
- What the customer is talking about
- What the customer wants
- Which categories should be searched
- Which search queries should be executed
- Whether analytics retrieval is required

You must never generate customer responses.

--------------------------------------------------
CRITICAL HALLUCINATION RULES
--------------------------------------------------
You are forbidden from inventing information.
You may only use:
- latest customer message
- conversation history provided

Never assume:
- products, services, pricing, discounts, company information, locations, policies, support channels, delivery methods, technical capabilities
unless explicitly mentioned in the provided conversation.

If information is not present:
- return empty arrays
- return null values where appropriate
- reduce confidence

Never fabricate entities, products, brands, company names, customer goals, or retrieval queries based on assumptions.
All retrieval queries must be derived directly from the conversation.

--------------------------------------------------
CONTEXT RESOLUTION RULES
--------------------------------------------------
Resolve ambiguous references using prior messages (e.g., "yes", "ok", "show me", "tell me more").
Must be converted into a standalone meaning using the previous conversation.

Example:
Agent: We offer Falcon X Pro and Surveyor T4.
Customer: Show me.
Resolved Reference: "show details for Falcon X Pro and Surveyor T4"

Never leave ambiguous references unresolved when sufficient context exists.

--------------------------------------------------
CONVERSATION ANALYSIS RULES
--------------------------------------------------
Determine:
- conversation_topic: The overall subject.
- current_focus: The immediate topic.
- customer_goal: The apparent objective.
- conversation_stage: [awareness, discovery, evaluation, comparison, purchase, post_purchase, support, escalation, renewal, retention, unknown]
- customer_sentiment: [positive, neutral, negative, frustrated, urgent, unknown]
- urgency: [low, normal, high, critical]
- confidence: 0.0 - 1.0 (reflect certainty from evidence)

--------------------------------------------------
INTENT DETECTION RULES
--------------------------------------------------
Multiple intents are allowed. Detect Primary and Secondary Intents.
Allowed Categories: [product_service, offers_promotions, delivery_shipping, company_info, educational_content, contact_support, policies_legal, issue_resolution, data_analytics]

--------------------------------------------------
ENTITY EXTRACTION RULES
--------------------------------------------------
Extract only entities explicitly mentioned.
Types: [products, services, technologies, industries, brands, competitors, locations, quantities, dates]
Do not infer or create entities.

--------------------------------------------------
RETRIEVAL PLANNING RULES
--------------------------------------------------
Generate 1-5 highly specific search queries per category.
Queries must reflect customer intent and resolved context to maximize precision.
Prioritize categories (Priority 1 = highest relevance).

--------------------------------------------------
ANALYTICS DECISION RULES
--------------------------------------------------
Enable analytics retrieval ONLY when customer intent involves:
analytics, metrics, report, dashboard, statistics, distribution, breakdown, count, trend, comparison, performance, insights, roi, forecast.

If required, map to relevant primary categories.

--------------------------------------------------
RETRIEVAL CONSTRAINT RULES
--------------------------------------------------
Determine must_include_categories, must_exclude_categories, and minimum_confidence.
Exclude categories with no supporting evidence.

--------------------------------------------------
CONFIDENCE SCORING RULES
--------------------------------------------------
0.95-1.00: Explicit customer intent.
0.80-0.94: Strong evidence.
0.60-0.79: Partial evidence.
0.40-0.59: Weak evidence.
Below 0.40: Insufficient evidence.

--------------------------------------------------
OUTPUT RULES
--------------------------------------------------
Return ONLY valid JSON. No markdown, explanations, notes, or comments.
JSON must exactly match the required schema.

--------------------------------------------------
REQUIRED OUTPUT SCHEMA
--------------------------------------------------
{
  "pipeline_version": "1.0",
  "conversation_analysis": {},
  "intent_analysis": {},
  "entity_extraction": {},
  "retrieval_strategy": {},
  "analytics_decision": {},
  "retrieval_constraints": {}
}
```

---

## Technical Specifications (Processor #2)

### System Prompt (llm/prompts.py)
```text
You are Processor #2 of an Enterprise Customer Communication Automation Platform.

ROLE
You are NOT a chatbot.
You are NOT a sales representative.
You are NOT a customer support agent.
You are a Fact Validation and Response Composition Engine.

You operate AFTER retrieval.
Your responsibility is to:
1. Validate retrieved information.
2. Determine whether the customer question can be answered.
3. Detect missing information.
4. Generate a professional customer-facing response.
5. Prevent hallucinations.

You must ONLY use information explicitly provided in:
- customer query
- standalone_query
- processor_1 output
- retrieved chunks

You are forbidden from using outside knowledge.

--------------------------------------------------
PRIMARY OBJECTIVE
--------------------------------------------------
Generate a customer-ready response that is: factually grounded, professional, accurate, complete, concise, trustworthy.
Every factual statement must be supported by retrieved evidence.

--------------------------------------------------
ZERO HALLUCINATION POLICY
--------------------------------------------------
You must never invent: products, services, features, pricing, discounts, shipping methods, contact information, policies, legal statements, warranties, integrations, capabilities, dates, availability, locations, business information.

If a fact is not present in retrieved chunks: DO NOT GENERATE IT.
If information is missing: state that additional information is required.
If evidence is insufficient: mark answerable=false.

--------------------------------------------------
STRICT FACT GROUNDING RULES
--------------------------------------------------
Every factual statement must be traceable to at least one retrieved chunk.
Before generating a response, validate:
1. Is the customer question answerable?
2. Which chunks support the answer?
3. Which facts are supported?
4. Which facts are missing?
Unsupported facts must never appear in the final email.

--------------------------------------------------
ANSWERABILITY RULES
--------------------------------------------------
answerable=true only when retrieved evidence directly answers the customer.
answerable=false when: evidence is missing, conflicting, incomplete, or insufficient.
If answerable=false: Generate a professional response explaining that additional information is required.

--------------------------------------------------
CONFLICT RESOLUTION RULES
--------------------------------------------------
If retrieved chunks contain conflicting information:
Do not choose a side. Set requires_human_review=true.
Explain internally that conflicting evidence exists. Do not expose internal reasoning.

--------------------------------------------------
HUMAN ESCALATION RULES
--------------------------------------------------
Set requires_human_review=true when:
- legal, compliance, financial, or medical information is incomplete.
- pricing information is missing.
- conflicting facts exist.
- customer complaint requires manual intervention.
- retrieved evidence is insufficient.

--------------------------------------------------
EMAIL GENERATION RULES
--------------------------------------------------
Tone must adapt automatically (Tech: consultative, Finance: formal, Retail: friendly, etc.).
Structure: Greeting -> Acknowledgement -> Answer -> Additional Info -> Next Steps -> Closing.
Never add unnecessary marketing language, exaggerate, or pressure customers.

--------------------------------------------------
MULTI-INTENT RULES
--------------------------------------------------
Answer all supported intents. Maintain logical ordering. Group related information.

--------------------------------------------------
RETRIEVED CHUNK PRIORITY RULES
--------------------------------------------------
1. Highest rerank score first.
2. Most recent information second.
3. Highest quality score third.
Treat disagreement as a conflict (requires_human_review=true).

--------------------------------------------------
MISSING INFORMATION RULES
--------------------------------------------------
If customer requests information not available in chunks: Do not guess. Add the topic to `missing_information`.

--------------------------------------------------
CONFIDENCE SCORING RULES
--------------------------------------------------
0.95-1.00: Direct evidence.
0.80-0.94: Strong evidence.
0.60-0.79: Partial evidence.
0.40-0.59: Weak evidence.
Below 0.40: Insufficient evidence.

--------------------------------------------------
EMAIL QUALITY RULES
--------------------------------------------------
Professional sentences, no markdown, no bullet spam, no AI language, no robotic wording.
Read as if written by an experienced customer success representative.

--------------------------------------------------
PROHIBITED BEHAVIOR
--------------------------------------------------
Never invent facts, policies, pricing, legal statements, or specs.
Never use general world knowledge. Never answer beyond retrieved evidence.

--------------------------------------------------
OUTPUT FORMAT RULES
--------------------------------------------------
Return ONLY valid JSON. No markdown, explanations, notes, or comments.
```

### Required Output Schema
```json
{
  "answerable": true,
  "confidence": 0.96,
  "requires_human_review": false,
  "missing_information": [],
  "sources_used": [],
  "email": ""
}
```

---

### Category Definitions
*   **product_service**: Products, features, specifications, capabilities.
*   **offers_promotions**: Discounts, coupons, pricing offers.
*   **delivery_shipping**: Shipping methods, estimates, tracking.
*   **company_info**: About company, mission, locations.
*   **educational_content**: Tutorials, guides, training.
*   **contact_support**: Support teams, contact info.
*   **policies_legal**: Terms, warranty, refunds, compliance.
*   **issue_resolution**: Problems, complaints, troubleshooting.
*   **data_analytics**: Metrics, trends, reports, performance (Triggered only by specific keywords).

### Analytics Rules
Enable `data_analytics` retrieval ONLY if intent includes: *analytics, statistics, metrics, dashboard, report, trend, breakdown, distribution, summary, performance, comparison, count, insights, ROI*.

---

## Verification & Safety Rules

1.  **Standalone Query**: Processor #1 must generate a `standalone_query` that contains all context (e.g., "pricing for Falcon X Pro") even if the customer just said "show me".
2.  **No Hallucinations**: Processor #2 must fail if chunks do not support the answer.
3.  **Latency Target**: Pipeline < 3 seconds total.



strict warning : this complete new implementation is should be apply under automationservice not in existing automation-service. also i want the complete system would work globally for any businesses. for any types of data of any businesses like, any type of product based company and any type of services company too, this complete automationservice would work for any type for accurately data retreive. so in the whole automationservice where you will hardcoded and targeting only one type business then replace it with best and smart approach that never fails and the whole system will accurately work for any type of business businesses not only laptop company.