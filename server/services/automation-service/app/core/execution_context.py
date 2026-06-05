"""
Core - Execution Context
=========================
Runtime context propagation via Python contextvars.
Flows automatically through all async operations in a request.

Design: plain Python dataclass — NOT a Pydantic model.
This is a runtime-only object used for trace propagation, not serialization.
Pydantic inheritance was removed because it requires super().__init__(**kwargs)
which conflicts with the explicit __init__ and causes AttributeError on
__pydantic_fields_set__ when any serialization path calls model_dump().
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from contextvars import ContextVar
from datetime import datetime


# Context variable — propagates automatically through asyncio tasks
_execution_context: ContextVar[Optional["ExecutionContext"]] = ContextVar(
    "execution_context", default=None
)


@dataclass
class ExecutionContext:
    """
    Immutable-by-convention runtime context for a single workflow execution.
    Propagated through contextvars — no need to thread it through every call.
    """

    trace_id: str
    correlation_id: str
    user_id: str
    workflow_id: str
    execution_id: str
    message_id: str
    conversation_id: str
    thread_id: str
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        user_id: str,
        message_id: str,
        conversation_id: str,
        thread_id: str,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionContext":
        """Create a new root execution context."""
        trace_id = trace_id or str(uuid.uuid4())
        return cls(
            trace_id=trace_id,
            correlation_id=correlation_id or trace_id,
            user_id=user_id,
            workflow_id=f"wf_{conversation_id}",
            execution_id=str(uuid.uuid4()),
            message_id=message_id,
            conversation_id=conversation_id,
            thread_id=thread_id,
            metadata=metadata or {},
        )

    # ── Child span ────────────────────────────────────────────────────────────

    def create_child_span(self, operation: str) -> "ExecutionContext":
        """Create a child context for a sub-operation span."""
        child_meta = self.metadata.copy()
        child_meta["parent_operation"] = operation
        return ExecutionContext(
            trace_id=self.trace_id,
            correlation_id=self.correlation_id,
            user_id=self.user_id,
            workflow_id=self.workflow_id,
            execution_id=self.execution_id,
            message_id=self.message_id,
            conversation_id=self.conversation_id,
            thread_id=self.thread_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
            metadata=child_meta,
        )

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "thread_id": self.thread_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "started_at": self.started_at.isoformat(),
            "metadata": self.metadata,
        }


# ── Context accessors ─────────────────────────────────────────────────────────


def set_execution_context(ctx: ExecutionContext) -> None:
    """Set execution context for the current async task."""
    _execution_context.set(ctx)


def get_execution_context() -> Optional[ExecutionContext]:
    """Get execution context for the current async task."""
    return _execution_context.get()


def clear_execution_context() -> None:
    """Clear execution context for the current async task."""
    _execution_context.set(None)


def ensure_execution_context() -> ExecutionContext:
    """Get context or raise if not set."""
    ctx = get_execution_context()
    if ctx is None:
        raise RuntimeError("Execution context not set for this task")
    return ctx


# ── Context manager ───────────────────────────────────────────────────────────


class ExecutionContextManager:
    """Async/sync context manager that scopes an ExecutionContext to a block."""

    def __init__(self, ctx: ExecutionContext) -> None:
        self.ctx = ctx
        self._previous: Optional[ExecutionContext] = None

    def __enter__(self) -> ExecutionContext:
        self._previous = get_execution_context()
        set_execution_context(self.ctx)
        return self.ctx

    def __exit__(self, *_) -> None:
        if self._previous is not None:
            set_execution_context(self._previous)
        else:
            clear_execution_context()

    async def __aenter__(self) -> ExecutionContext:
        self._previous = get_execution_context()
        set_execution_context(self.ctx)
        return self.ctx

    async def __aexit__(self, *_) -> None:
        if self._previous is not None:
            set_execution_context(self._previous)
        else:
            clear_execution_context()


def execution_context(ctx: ExecutionContext) -> ExecutionContextManager:
    """Return a context manager that activates the given ExecutionContext."""
    return ExecutionContextManager(ctx)


__all__ = [
    "ExecutionContext",
    "set_execution_context",
    "get_execution_context",
    "clear_execution_context",
    "ensure_execution_context",
    "execution_context",
    "ExecutionContextManager",
]
