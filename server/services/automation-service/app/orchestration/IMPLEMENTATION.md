# Orchestration Layer - Implementation Documentation

## Overview

The orchestration layer is the **central AI workflow execution engine** for automation-service. It coordinates distributed AI operations, manages workflow lifecycle, enforces execution order, and provides enterprise-grade reliability through retries, state management, and observability.

## Architecture

### Core Components

1. **Execution Engine** (`execution_engine.py`)
   - Central workflow controller
   - Coordinates all AI layers (memory, intelligence, retrieval, LLM, handoff)
   - Manages execution context and tracing
   - Generates response events

2. **State Machine** (`state_machine.py`)
   - Workflow state tracking
   - Valid state transition enforcement
   - State history for replay
   - Terminal state detection

3. **Retry Engine** (`retry_engine.py`)
   - Exponential backoff with jitter
   - Configurable retry policies per operation
   - Transient vs. permanent error classification
   - Dead letter queue integration

## Execution Flow

### Standard Workflow Execution

```
AutomationEvent → ExecutionEngine → ExecutionContext
                        ↓
          1. Load Memory (Redis)
                        ↓
          2. Run Intelligence (Intent + Entities)
                        ↓
          3. Run Retrieval (L1-L7 Hierarchical)
                        ↓
          4. Run LLM (Grounded Generation)
                        ↓
          5. Make Decision (Confidence Evaluation)
                        ↓
          ResponseEvent → email-service
```

### State Machine Transitions

```
CREATED
  ↓
MEMORY_LOADING → MEMORY_LOADED
  ↓
INTELLIGENCE_RUNNING → INTELLIGENCE_COMPLETED
  ↓
RETRIEVAL_RUNNING → RETRIEVAL_COMPLETED
  ↓
LLM_GENERATING → LLM_COMPLETED
  ↓
VALIDATING → VALIDATION_COMPLETED
  ↓
DECIDING → DECISION_MADE
  ↓
DISPATCHING → COMPLETED
```

### Failure Handling

```
Any Stage
  ↓ (error)
FAILED
  ↓
RETRY_SCHEDULED (if retryable)
  ↓
Resume from last successful state
```

## Key Features

### 1. Distributed Tracing

Every execution has:
- **trace_id**: Unique request identifier
- **correlation_id**: Cross-service correlation
- **execution_id**: Specific execution instance
- **workflow_id**: Conversation workflow identifier

### 2. Execution Context

Carries state through entire pipeline:
```python
ExecutionContext:
  - trace_id
  - user_id (tenant isolation)
  - workflow_id
  - execution_id
  - state (current workflow state)
  - layer_results (outputs from each layer)
  - timings (performance tracking)
  - metadata (additional context)
```

### 3. Retry Policies

Configurable per operation:
- **retrieval**: max 2 retries, 50ms initial delay
- **llm**: max 3 retries, 100ms initial delay
- **memory**: max 2 retries, 20ms initial delay
- **dispatch**: max 3 retries, 200ms initial delay

### 4. Observability

Tracks:
- Per-stage latency
- State transitions
- Retry attempts
- Failure reasons
- Execution metrics

## Integration Points

### With Messaging Layer

```python
from app.orchestration import execution_engine

async def process_event(event: AutomationEvent):
    response = await execution_engine.execute_workflow(event)
    await dispatch_response(response)
```

### With Storage Layer

Execution states persisted to:
- **Redis**: Hot execution state (TTL 48h)
- **PostgreSQL**: Permanent execution history
- **Snapshots**: Replay data for debugging

### With Observability

```python
- Structured logs with trace_id
- Metrics per stage
- Performance timings
- State history
```

## Performance Targets

- **Total execution**: <5000ms (p95)
- **Memory load**: <5ms
- **Intelligence**: <3000ms
- **Retrieval**: <500ms
- **LLM**: <1500ms
- **Decision**: <10ms

## Future Enhancements

1. **Compensation Workflows**: Rollback on failures
2. **Parallel Execution**: Run independent stages concurrently
3. **Workflow Versioning**: Support multiple workflow versions
4. **Dynamic Routing**: Route to workflows based on policies
5. **Circuit Breakers**: Prevent cascading failures
6. **Adaptive Concurrency**: Auto-adjust based on load

## Usage Example

```python
from app.models import AutomationEvent
from app.orchestration import execution_engine

# Create event from incoming message
event = AutomationEvent(
    event_id="evt_123",
    message_id="msg_456",
    conversation_id="conv_789",
    thread_id="user_abc:thread_xyz",
    user_id="user_abc",
    content="What drones do you have?",
    created_at=datetime.utcnow()
)

# Execute workflow
response = await execution_engine.execute_workflow(event)

# Response contains:
# - response_text: AI-generated reply
# - action: send/skip/draft
# - confidence: final confidence score
# - trace_id: for debugging
```

## Status

**Phase**: Implemented  
**Version**: 1.0  
**Integration**: Ready for messaging layer integration
