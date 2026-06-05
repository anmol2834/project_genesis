# Core Layer - Implementation Documentation

## Overview

The `/core` layer is the **runtime kernel** of automation-service, providing enterprise-grade infrastructure for lifecycle management, dependency injection, execution context propagation, resource pooling, and health monitoring.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CORE RUNTIME KERNEL                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Startup    │→│   Runtime    │→│   Shutdown   │    │
│  │   Engine     │  │   Manager    │  │   Engine     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Dependency  │  │  Execution   │  │   Resource   │    │
│  │  Injection   │  │   Context    │  │  Management  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    Health    │  │  Exceptions  │  │   Security   │    │
│  │    System    │  │  Hierarchy   │  │   & Guards   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Runtime (`runtime.py`)

**Purpose**: Main application runtime orchestrating complete service lifecycle.

**Key Features**:
- Single entry point for service startup
- Coordinates startup → workers → shutdown
- Signal handling (SIGTERM, SIGINT)
- Uptime tracking

**Usage**:
```python
from app.core import get_runtime, run_application

# Method 1: Direct control
runtime = get_runtime()
await runtime.start()
await runtime.run_workers()
await runtime.shutdown()

# Method 2: Complete lifecycle
await run_application()
```

### 2. Startup Engine (`startup.py`)

**Purpose**: Fail-fast initialization with ordered task execution.

**Startup Sequence**:
1. Load Configuration
2. Initialize Observability
3. Initialize Resource Pools (Redis, Postgres, Qdrant)
4. Initialize Storage
5. Initialize Memory
6. Initialize Intelligence
7. Initialize Retrieval
8. Initialize LLM
9. Initialize Orchestration
10. Initialize Messaging
11. Initialize Workers
12. Initialize API

**Features**:
- Task timeout enforcement
- Required vs optional tasks
- Detailed progress logging
- Fail-fast on critical failures

**Example Output**:
```
══════════════════════════════════════════════════════════════════
AUTOMATION-SERVICE STARTUP
══════════════════════════════════════════════════════════════════
⚙ Load Configuration...
✓ Load Configuration complete
⚙ Initialize Observability...
✓ Initialize Observability complete
⚙ Initialize Resource Pools...
✓ Initialize Resource Pools complete
...
══════════════════════════════════════════════════════════════════
STARTUP COMPLETE (3.42s)
Completed tasks: 12
══════════════════════════════════════════════════════════════════
```

### 3. Shutdown Engine (`shutdown.py`)

**Purpose**: Graceful shutdown with worker draining and resource cleanup.

**Shutdown Sequence** (LIFO order):
1. Stop Message Ingestion
2. Drain Worker Queues (30s timeout)
3. Stop Workers
4. Flush Telemetry
5. Save Pending State
6. Close Resource Pools
7. Final Cleanup

**Features**:
- Graceful worker draining
- State preservation
- Resource cleanup
- Timeout protection

### 4. Dependency Injection (`dependency_injection.py`)

**Purpose**: Enterprise DI container with lifecycle scopes.

**Service Scopes**:
- `SINGLETON`: Single instance for application lifetime
- `SCOPED`: Instance per request/workflow
- `TRANSIENT`: New instance every time

**Usage**:
```python
from app.core import get_container, ServiceScope

container = get_container()

# Register services
container.register_singleton(
    MyService,
    factory=lambda: MyService()
)

container.register_scoped(
    RequestScopedService,
    factory=lambda: RequestScopedService()
)

# Initialize all singletons
await container.initialize_all()

# Resolve services
service = await container.resolve(MyService)

# Shutdown
await container.shutdown_all()
```

### 5. Execution Context (`execution_context.py`)

**Purpose**: Global execution context propagation across all layers.

**Propagated Fields**:
- `trace_id`: Distributed trace ID
- `correlation_id`: Event correlation
- `user_id`: Tenant ID (isolation)
- `workflow_id`: Workflow identifier
- `execution_id`: Unique execution ID
- `message_id`: Message identifier
- `conversation_id`: Conversation ID
- `thread_id`: Thread ID

**Usage**:
```python
from app.core import ExecutionContext, execution_context

# Create context
ctx = ExecutionContext.create(
    user_id="user_123",
    message_id="msg_456",
    conversation_id="conv_789",
    thread_id="thread_abc"
)

# Use context manager (recommended)
async with execution_context(ctx):
    # Context automatically propagates through async calls
    await intelligence_layer()
    await retrieval_layer()
    await llm_layer()

# Manual control
from app.core import set_execution_context, get_execution_context

set_execution_context(ctx)
current_ctx = get_execution_context()
```

**Context Propagation**:
```
Message → ExecutionContext → Intelligence → Retrieval → LLM → Handoff
   ↓            ↓                 ↓            ↓         ↓        ↓
trace_id propagates through entire pipeline automatically
```

### 6. Resource Management (`resource_management.py`)

**Purpose**: Connection pooling for Redis, PostgreSQL, Qdrant.

**Managed Resources**:
- **Redis**: Connection pool (50 connections default)
- **PostgreSQL**: AsyncEngine with pool (20 connections, 10 overflow)
- **Qdrant**: AsyncQdrantClient

**Usage**:
```python
from app.core import get_resource_manager

manager = get_resource_manager()

# Initialize pools
await manager.initialize()

# Get Redis
redis = manager.get_redis()
await redis.set("key", "value")

# Get Database session
async with manager.get_db_session() as session:
    result = await session.execute("SELECT * FROM workflows")

# Get Qdrant
qdrant = manager.get_qdrant()
collections = await qdrant.get_collections()

# Health check
health = await manager.health_check()

# Shutdown
await manager.shutdown()
```

### 7. Health Check System (`health.py`)

**Purpose**: Deep health monitoring for all infrastructure.

**Health Checks**:
- Redis connectivity + latency
- PostgreSQL connectivity + latency
- Qdrant connectivity + collections
- Orchestration engine (active executions)
- Worker health
- Telemetry systems

**Health Statuses**:
- `HEALTHY`: All systems operational
- `DEGRADED`: Some non-critical failures
- `UNHEALTHY`: Critical failures
- `UNKNOWN`: Cannot determine status

**Usage**:
```python
from app.core import get_health_system

health_system = get_health_system()
result = await health_system.check_all()

# Result structure:
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "duration_ms": 25.3,
    "checks": {
        "redis": {
            "status": "healthy",
            "latency_ms": 2.1,
            "details": {"connected": true}
        },
        "database": {
            "status": "healthy",
            "latency_ms": 5.8
        },
        ...
    }
}
```

### 8. Exception Hierarchy (`exceptions.py`)

**Purpose**: Enterprise exception system with retry classification.

**Base Exceptions**:
- `AutomationServiceException`: Base for all exceptions
- `RetryableException`: Transient failures (retry)
- `NonRetryableException`: Permanent failures (no retry)

**Retryable Exceptions**:
- `ServiceUnavailableError`: Downstream service down
- `RateLimitError`: Rate limit exceeded
- `TimeoutError`: Operation timeout
- `ConnectionError`: Network failure
- `StorageError`, `CacheError`, `QueueError`
- `MemoryError`, `IntelligenceError`, `RetrievalError`, `LLMError`

**Non-Retryable Exceptions**:
- `ValidationError`: Bad input
- `TenantIsolationError`: Security violation
- `AuthenticationError`, `AuthorizationError`
- `WorkflowError`, `StateTransitionError`
- `DLQError`

**Usage**:
```python
from app.core.exceptions import RetryableException, ValidationError

try:
    result = await external_service()
except ConnectionError as e:
    # Retry logic will catch this
    raise
except ValidationError as e:
    # No retry - permanent failure
    logger.error(f"Validation failed: {e}")
    raise
```

## Integration Points

### With Observability Layer

```python
from app.core import ExecutionContext
from app.observability import get_tracer, get_logger

ctx = get_execution_context()

# Tracing automatically uses context
tracer = get_tracer()
with tracer.trace_operation("intelligence", ctx.user_id):
    # trace_id, user_id propagated automatically
    pass

# Logging includes context
logger = get_logger(__name__)
logger.info("Processing message", 
    user_id=ctx.user_id,
    trace_id=ctx.trace_id
)
```

### With Orchestration Layer

```python
from app.core import ExecutionContext, execution_context
from app.orchestration import execution_engine

# Create context
ctx = ExecutionContext.create(...)

# Execute with context
async with execution_context(ctx):
    result = await execution_engine.execute_workflow(event)
```

### With Storage Layer

```python
from app.core import get_resource_manager

manager = get_resource_manager()
redis = manager.get_redis()

# Redis operations use pooled connection
await redis.set(f"memory:{user_id}:{thread_id}", data)
```

### With Workers Layer

```python
from app.core import get_runtime

runtime = get_runtime()

# Start workers as part of runtime
await runtime.start()
await runtime.run_workers()
```

## Performance Characteristics

### Startup Time
- Target: <5 seconds
- Typical: 2-4 seconds
- Includes: Resource pool initialization, health checks

### Shutdown Time
- Target: <30 seconds
- Worker drain timeout: 30s
- Resource cleanup: <5s

### Execution Context Overhead
- Context creation: <0.1ms
- Context propagation: Zero (uses contextvars)

### Resource Pool Performance
- Redis: 50 connection pool, <2ms latency
- PostgreSQL: 20 connection pool, <5ms latency
- Qdrant: Persistent client, <10ms latency

### Health Check Performance
- Individual check: 2-10ms
- Full health check: <50ms
- Background health: Every 30s (configurable)

## Configuration

All configuration via `/server/.env`:

```bash
# Resource Pools
REDIS_MAX_CONNECTIONS=50
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30

# Health Checks
HEALTH_CHECK_INTERVAL=30
HEALTH_CHECK_TIMEOUT=5

# Worker Configuration
WORKER_CONCURRENCY=4

# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run with core runtime
CMD ["python", "-m", "app.main_new"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: automation-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: automation-service
        image: automation-service:2.0
        ports:
        - containerPort: 8009
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8009
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8009
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
```

## Testing

### Unit Tests

```python
import pytest
from app.core import ExecutionContext, get_container

@pytest.fixture
async def execution_context():
    ctx = ExecutionContext.create(
        user_id="test_user",
        message_id="test_msg",
        conversation_id="test_conv",
        thread_id="test_thread"
    )
    return ctx

async def test_context_propagation(execution_context):
    from app.core import set_execution_context, get_execution_context
    
    set_execution_context(execution_context)
    ctx = get_execution_context()
    
    assert ctx.user_id == "test_user"
    assert ctx.trace_id is not None
```

### Integration Tests

```python
async def test_startup_sequence():
    from app.core import create_startup_sequence
    
    engine = await create_startup_sequence()
    await engine.execute()
    
    assert len(engine.completed) > 0
    assert len(engine.failed) == 0
```

## Monitoring

### Metrics

Core layer exports these metrics:

- `startup_duration_seconds`: Startup time
- `shutdown_duration_seconds`: Shutdown time
- `health_check_duration_ms`: Health check latency
- `resource_pool_size`: Connection pool sizes
- `resource_pool_active`: Active connections

### Logs

Structured logs include:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "message": "Runtime started successfully",
  "service": "automation-service",
  "environment": "production"
}
```

## Troubleshooting

### Startup Failures

1. Check logs for failed task:
   ```
   ✗ Initialize Resource Pools FAILED: Connection refused
   ```

2. Verify configuration:
   ```python
   from shared.config import get_config
   config = get_config()
   print(config.REDIS_URL)
   ```

3. Test connections manually:
   ```python
   from app.core import get_resource_manager
   manager = get_resource_manager()
   await manager.initialize()
   health = await manager.health_check()
   ```

### Resource Exhaustion

1. Check pool metrics
2. Adjust pool sizes in `.env`
3. Monitor connection leaks

### Context Propagation Issues

1. Verify context is set:
   ```python
   from app.core import get_execution_context
   ctx = get_execution_context()  # Should not be None
   ```

2. Check async boundaries (contextvars propagate automatically)

## Summary

The core layer provides production-ready runtime infrastructure with:

✅ Enterprise lifecycle management  
✅ Fail-fast startup validation  
✅ Graceful shutdown with draining  
✅ Dependency injection container  
✅ Global execution context propagation  
✅ Resource pooling (Redis, Postgres, Qdrant)  
✅ Deep health monitoring  
✅ Exception hierarchy with retry classification  
✅ Signal handling (SIGTERM, SIGINT)  
✅ Kubernetes-ready (liveness, readiness probes)  

**Files**: 8 core files (~2,800 LOC)  
**Status**: Production-ready  
**Performance**: <5s startup, <30s shutdown, <0.1ms context overhead
