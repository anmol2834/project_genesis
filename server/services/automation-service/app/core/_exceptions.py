"""
Core - Exception Hierarchy (canonical source)
==============================================
All exceptions live here. Imported by both:
  - app/core/exceptions.py  (module-level import)
  - app/core/exceptions/__init__.py  (package import)

Having exceptions/ as a package AND exceptions.py as a module caused Python
to always resolve `from app.core.exceptions import X` to the package __init__,
which tried to re-import from itself → circular ImportError → fallback stubs
→ bare Exception subclasses with no __init__ kwargs → runtime crashes.

Solution: canonical definitions live in _exceptions.py (no name collision),
both the .py module shim and the package __init__ import from here.
"""
from typing import Optional, Dict, Any


class AutomationServiceException(Exception):
    """Base exception for all automation-service errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.is_retryable = False


# ── Retryable ─────────────────────────────────────────────────────────────────

class RetryableException(AutomationServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.is_retryable = True


class ServiceUnavailableError(RetryableException):
    """Downstream service unavailable."""


class RateLimitError(RetryableException):
    """Rate limit exceeded."""


class TimeoutError(RetryableException):
    """Operation timed out."""


class ConnectionError(RetryableException):
    """Network connection failure."""


class StorageError(RetryableException):
    """Storage layer failure."""


class CacheError(RetryableException):
    """Cache operation failure."""


class QueueError(RetryableException):
    """Queue operation failure."""


class MemoryError(RetryableException):
    """Memory layer failure."""


class IntelligenceError(RetryableException):
    """Intelligence layer failure."""


class RetrievalError(RetryableException):
    """Retrieval layer failure."""


class LLMError(RetryableException):
    """LLM generation failure."""


class ExecutionError(RetryableException):
    """Workflow execution failure."""


class MessageProcessingError(RetryableException):
    """Message processing failure."""


# ── Non-Retryable ─────────────────────────────────────────────────────────────

class NonRetryableException(AutomationServiceException):
    pass


class ValidationError(NonRetryableException):
    """Input validation failure."""


class TenantIsolationError(NonRetryableException):
    """Tenant isolation violation."""


class AuthenticationError(NonRetryableException):
    """Authentication failure."""


class AuthorizationError(NonRetryableException):
    """Authorization failure."""


class ConfigurationError(NonRetryableException):
    """Configuration or startup failure."""


class PipelineError(NonRetryableException):
    """Pipeline execution failure."""


class HandoffError(NonRetryableException):
    """Handoff decision failure."""


class WorkflowError(NonRetryableException):
    """Workflow orchestration error."""


class StateTransitionError(WorkflowError):
    """Invalid state transition."""


class DLQError(NonRetryableException):
    """Dead letter queue error."""


# ── Worker ────────────────────────────────────────────────────────────────────

class WorkerError(AutomationServiceException):
    """Worker runtime error."""


__all__ = [
    "AutomationServiceException",
    "RetryableException",
    "NonRetryableException",
    "ServiceUnavailableError",
    "RateLimitError",
    "TimeoutError",
    "ConnectionError",
    "ValidationError",
    "TenantIsolationError",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "PipelineError",
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
