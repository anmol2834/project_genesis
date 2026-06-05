# LLM Layer

## Responsibility
Grounded, reasoning-first LLM generation with hallucination prevention.

## Components

### Providers
- OpenAI API client (gpt-4o-mini)
- Retry logic with exponential backoff
- Token usage tracking
- **Does NOT**: Store conversation history (that's memory/)

### Reasoning
- Chain-of-thought prompting
- Multi-step reasoning for complex queries
- Reasoning trace logging
- **Does NOT**: Retrieve data (that's retrieval/)

### Prompt Builder
- Constructs grounded prompts from retrieved chunks
- Token budget management
- Context compression
- **Does NOT**: Retrieve chunks (that's retrieval/)

### Grounding
- Injects retrieved chunks into system prompt
- Strict instruction to only use provided data
- Citation enforcement
- **Does NOT**: Validate outputs (that's hallucination_guard/)

### Hallucination Guard
- Post-generation validation against retrieved chunks
- Detects unsupported claims
- Flags confidence-violating outputs
- **Does NOT**: Generate responses (that's reasoning/)

### Structured Outputs
- JSON response parsing
- Schema validation
- Type checking
- **Does NOT**: Define schemas (that's models/schemas)

### Response Validation
- Validates completeness, coherence, relevance
- Checks for policy violations
- Ensures proper formatting
- **Does NOT**: Make send/skip decisions (that's handoff/)

### Prompt Templates
- Reusable prompt templates for common intents
- Dynamic template selection
- Multi-lingual template support
- **Does NOT**: Store user data (that's memory/)

### Token Management
- Tracks token usage per request
- Budget enforcement
- Cost optimization
- **Does NOT**: Bill tenants (that's external billing service)

## Integration Points
- **Input**: Query understanding + retrieved chunks + memory context
- **Output**: Generated response + confidence score to orchestration
- **Dependencies**: retrieval/ for chunks, memory/ for context

## Design Principles
- **Grounded-Only**: NEVER generate from knowledge, only from retrieved chunks
- **Reasoning-First**: Show reasoning before answer for complex queries
- **Observable**: Log all prompts and responses for debugging
- **Fast**: <2s target for generation (use streaming for longer responses)
- **Confidence-Calibrated**: Confidence scores must correlate with actual accuracy
