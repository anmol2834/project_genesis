"""
Core Exceptions - Package re-export
=====================================
Single source of truth: all exceptions live in app/core/exceptions.py
This __init__.py simply re-exports them so both import paths work:
  from app.core.exceptions import ExecutionError   ← .py file
  from app.core.exceptions import ExecutionError   ← package __init__

The circular-import problem is avoided by importing from the sibling
module directly using a relative import, not from the package itself.
"""

# Relative import from the sibling .py file avoids the circular reference
# that caused the try/except fallback to always define bare stubs.
from app.core._exceptions import (  # noqa: F401
    AutomationServiceException,
    RetryableException,
    NonRetryableException,
    ConfigurationError,
    PipelineError,
    ServiceUnavailableError,
    RateLimitError,
    TimeoutError,
    ConnectionError,
    ValidationError,
    TenantIsolationError,
    AuthenticationError,
    AuthorizationError,
    StorageError,
    CacheError,
    QueueError,
    MemoryError,
    IntelligenceError,
    RetrievalError,
    LLMError,
    HandoffError,
    WorkflowError,
    StateTransitionError,
    ExecutionError,
    WorkerError,
    MessageProcessingError,
    DLQError,
)

__all__ = [
    "AutomationServiceException",
    "RetryableException",
    "NonRetryableException",
    "ConfigurationError",
    "PipelineError",
    "ServiceUnavailableError",
    "RateLimitError",
    "TimeoutError",
    "ConnectionError",
    "ValidationError",
    "TenantIsolationError",
    "AuthenticationError",
    "AuthorizationError",
    "StorageError",
    "CacheError",
    "QueueError",
    "MemoryError",
    "IntelligenceError",
    "RetrievalError",
    "LLMError",
    "HandoffError",
    "WorkflowError",
    "StateTransitionError",
    "ExecutionError",
    "WorkerError",
    "MessageProcessingError",
    "DLQError",
]
