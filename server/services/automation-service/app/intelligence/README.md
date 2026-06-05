# Intelligence Layer

## Responsibility
Understands user intent, extracts entities, and plans retrieval strategies.

## Components

### Intent Understanding
- Classifies user intent (interest, pricing, support, question, follow_up)
- Language detection
- Confidence scoring
- **Does NOT**: Retrieve business data (that's retrieval/)

### Entity Extraction
- Extracts products, categories, features, constraints
- Normalizes entity names
- Resolves entity references across turns
- **Does NOT**: Store entities (that's memory/)

### Conversation Analysis
- Analyzes conversation flow and user engagement
- Detects topic shifts
- Identifies user sentiment and urgency
- **Does NOT**: Generate responses (that's llm/)

### Query Decomposition
- Breaks complex queries into sub-queries
- Identifies calculation requirements
- Handles multi-intent messages
- **Does NOT**: Execute retrieval (that's retrieval/)

### Query Planning
- Determines retrieval strategy (exact, semantic, hybrid)
- Plans multi-stage retrieval
- Estimates retrieval cost
- **Does NOT**: Execute retrieval (that's retrieval/)

### Intent Routing
- Routes intent to appropriate workflow
- Determines if fast-path is possible
- Priority classification
- **Does NOT**: Orchestrate pipeline (that's orchestration/)

### Confidence Analysis
- Scores confidence for all predictions
- Multi-signal confidence fusion
- Calibrated probability estimates
- **Does NOT**: Make send/skip decisions (that's handoff/)

### Risk Analysis
- Identifies high-risk queries (pricing, legal, technical)
- Detects potential hallucination triggers
- Flags queries requiring human review
- **Does NOT**: Validate LLM outputs (that's llm/hallucination_guard)

## Integration Points
- **Input**: Raw message content, conversation history from memory
- **Output**: Structured understanding (intent, entities, query plan) to orchestration
- **Dependencies**: memory/ for context, llm/providers for understanding models

## Design Principles
- **Fast-First**: Intent classification must be <100ms
- **Confidence-Aware**: Every prediction must include confidence score
- **Memory-Enhanced**: Use conversation memory to boost accuracy
- **Multi-Lingual**: Support English, Hindi, Hinglish out of the box
