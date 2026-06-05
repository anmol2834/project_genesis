"""
Observability - Distributed Tracing System
===========================================
Enterprise distributed tracing with context propagation.
"""
import uuid
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import asynccontextmanager
from app.models.observability import TraceContext, SpanEvent
from app.models.enums import SpanKind

class DistributedTracer:
    """Distributed tracing manager"""
    
    def __init__(self):
        self.active_traces: Dict[str, TraceContext] = {}
        self.active_spans: Dict[str, SpanEvent] = {}
    
    def create_trace_context(
        self,
        user_id: str,
        operation_name: str,
        correlation_id: Optional[str] = None
    ) -> TraceContext:
        """Create new trace context"""
        trace_id = str(uuid.uuid4())
        
        ctx = TraceContext(
            trace_id=trace_id,
            correlation_id=correlation_id or trace_id,
            user_id=user_id,
            service_name="automation-service",
            operation_name=operation_name,
            start_time=datetime.utcnow()
        )
        
        self.active_traces[trace_id] = ctx
        return ctx
    
    def create_span(
        self,
        trace_id: str,
        operation: str,
        span_kind: SpanKind = SpanKind.INTERNAL,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> SpanEvent:
        """Create new span"""
        span_id = str(uuid.uuid4())
        
        span = SpanEvent(
            span_id=span_id,
            span_kind=span_kind,
            operation=operation,
            start_time=datetime.utcnow(),
            attributes=attributes or {}
        )
        
        self.active_spans[span_id] = span
        return span
    
    def end_span(self, span_id: str, status: str = "ok", error: Optional[str] = None):
        """End span and record duration"""
        if span_id not in self.active_spans:
            return
        
        span = self.active_spans[span_id]
        span.end_time = datetime.utcnow()
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.status = status
        
        if error:
            span.attributes["error"] = error
    
    def end_trace(self, trace_id: str, status: str = "ok", error: Optional[str] = None):
        """End trace context"""
        if trace_id not in self.active_traces:
            return
        
        ctx = self.active_traces[trace_id]
        ctx.end_time = datetime.utcnow()
        ctx.duration_ms = (ctx.end_time - ctx.start_time).total_seconds() * 1000
        ctx.status = status
        
        if error:
            ctx.error = error
    
    @asynccontextmanager
    async def trace_operation(
        self,
        user_id: str,
        operation_name: str,
        correlation_id: Optional[str] = None
    ):
        """Context manager for traced operations"""
        ctx = self.create_trace_context(user_id, operation_name, correlation_id)
        try:
            yield ctx
            self.end_trace(ctx.trace_id, status="ok")
        except Exception as e:
            self.end_trace(ctx.trace_id, status="error", error=str(e))
            raise

# Global tracer instance
tracer = DistributedTracer()

def get_tracer() -> DistributedTracer:
    """Get global tracer instance"""
    return tracer

__all__ = ["DistributedTracer", "tracer", "get_tracer"]
