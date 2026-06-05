# Orchestration Layer

## Responsibility
Coordinates the entire AI automation pipeline from event ingestion to response dispatch.

## Components

### Pipeline
- Defines the end-to-end processing pipeline
- Manages stage transitions
- Handles parallel execution coordination
- **Does NOT**: Implement business logic or AI models

### State Machine
- Tracks conversation state across turns
- Manages workflow transitions
- Handles state persistence and recovery
- **Does NOT**: Store conversation content (that's memory/)

### Execution Engine
- Executes pipeline stages asynchronously
- Manages timeouts and circuit breakers
- Coordinates resource allocation
- **Does NOT**: Implement retrieval or LLM logic

### Routing
- Routes events to appropriate handlers based on intent/priority
- Load balancing across workers
- Dynamic scaling decisions
- **Does NOT**: Classify intents (that's intelligence/)

### Workflow Manager
- Manages multi-step workflows (onboarding, support, sales)
- Tracks workflow progress
- Handles workflow-specific state
- **Does NOT**: Implement tenant-specific logic

## Integration Points
- **Input**: Events from messaging/stream_consumer
- **Output**: Orchestration commands to all pipeline layers
- **Dependencies**: All pipeline components (memory, intelligence, retrieval, llm, handoff)

## Design Principles
- **Stateless**: No business state stored here, only execution state
- **Tenant-Isolated**: All operations must be tenant-aware
- **Observable**: Every stage must emit metrics and traces
- **Resilient**: All stages must support retry, timeout, and fallback
