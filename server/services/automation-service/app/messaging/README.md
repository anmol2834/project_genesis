# Messaging Layer

## Responsibility
Event-driven communication with emailservice via Redis Streams.

## Components

### Stream Consumer
- Consumes events from `automation_events` stream
- Consumer group management (XREADGROUP)
- Exactly-once delivery per worker
- **Does NOT**: Process business logic (that's orchestration/)

### Stream Producer
- Publishes events to response streams
- Batch publishing for efficiency
- Delivery guarantees
- **Does NOT**: Route events (that's orchestration/routing)

### Redis Streams
- Redis Streams client wrapper
- Connection pooling
- Error handling and retries
- **Does NOT**: Implement business logic

### Event Processing
- Event parsing and validation
- Schema enforcement
- Event enrichment with metadata
- **Does NOT**: Orchestrate pipeline (that's orchestration/)

### Dead Letter Queue
- DLQ management for failed events
- Retry exhaustion handling
- DLQ monitoring and alerting
- **Does NOT**: Replay events (that's operators' responsibility)

### Retry Management
- Exponential backoff retry logic
- In-process retry queue
- Retry metrics and tracing
- **Does NOT**: Persist retries to Redis (in-memory only)

## Integration Points
- **Input**: Redis Streams (`automation_events` from emailservice)
- **Output**: Events to orchestration/, responses to emailservice
- **Storage**: Redis Streams

## Design Principles
- **Exactly-Once**: Each event processed by exactly one worker
- **Zero-Idle-Cost**: No polling when idle, event-driven wakeup
- **Observable**: Every event logged with timing and status
- **Resilient**: Automatic recovery from worker crashes via XAUTOCLAIM
