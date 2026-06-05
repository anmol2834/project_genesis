"""
Workers - Distributed Execution Layer
======================================
Worker infrastructure for processing automation events.
"""

# Runtime
from app.workers.runtime import (
    WorkerRuntime,
    get_worker_runtime
)

# Consumer
from app.workers.consumer import (
    StreamConsumer,
    STREAM_AUTOMATION_EVENTS
)

# Processor
from app.workers.processor import MessageProcessor

# Execution
from app.workers.execution import (
    WorkerExecutionEngine,
    get_execution_engine
)


__all__ = [
    # Runtime
    "WorkerRuntime",
    "get_worker_runtime",
    
    # Consumer
    "StreamConsumer",
    "STREAM_AUTOMATION_EVENTS",
    
    # Processor
    "MessageProcessor",
    
    # Execution
    "WorkerExecutionEngine",
    "get_execution_engine",
]
