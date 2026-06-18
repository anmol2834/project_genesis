"""
Workers - Execution Engine
===========================
Worker execution engine integrating orchestration layer.
"""
import asyncio
from typing import Dict, Any
from app.models.events import AutomationEvent, ResponseEvent
from app.core.execution_context import ExecutionContext, set_execution_context, clear_execution_context
from app.orchestration.execution_engine import execution_engine
from app.core.exceptions import ExecutionError
from app.observability import get_logger, get_metrics_collector

logger = get_logger(__name__)


class WorkerExecutionEngine:
    """
    Worker execution engine.
    Delegates to orchestration layer for actual workflow execution.
    """
    
    def __init__(self):
        self.metrics = get_metrics_collector()
    
    async def execute(self, event: AutomationEvent) -> ResponseEvent:
        """
        Execute complete AI workflow for automation event.
        
        Flow:
        1. Create execution context
        2. Set context for propagation
        3. Delegate to orchestration engine
        4. Return response event
        """
        import time
        start = time.perf_counter()
        
        # Create execution context
        ctx = ExecutionContext.create(
            user_id=event.user_id,
            message_id=event.message_id,
            conversation_id=event.conversation_id,
            thread_id=event.thread_id,
            trace_id=event.trace_id,
            correlation_id=event.correlation_id,
            metadata={
                "provider": event.metadata.get("provider", "unknown"),
                "priority": event.priority
            }
        )
        
        try:
            # Set execution context for propagation
            set_execution_context(ctx)
            
            logger.info(
                "Starting workflow execution",
                user_id=ctx.user_id,
                trace_id=ctx.trace_id,
                workflow_id=ctx.workflow_id,
                message_id=ctx.message_id
            )
            
            # Execute via orchestration engine
            response = await execution_engine.execute_workflow(event)
            
            elapsed = (time.perf_counter() - start) * 1000
            
            logger.info(
                "Workflow execution complete",
                user_id=ctx.user_id,
                trace_id=ctx.trace_id,
                duration_ms=round(elapsed, 2),
                action=response.action
            )
            
            # Record metrics
            self.metrics.record_histogram(
                "worker.execution_duration_ms",
                elapsed,
                ctx.user_id
            )
            
            self.metrics.record_counter(
                f"worker.execution.{response.action}",
                1,
                ctx.user_id
            )
            
            return response
            
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            
            logger.error(
                f"Workflow execution failed: {e}",
                user_id=ctx.user_id,
                trace_id=ctx.trace_id,
                duration_ms=round(elapsed, 2),
                exc_info=True
            )
            
            self.metrics.record_counter(
                "worker.execution.failed",
                1,
                ctx.user_id
            )
            
            raise ExecutionError(
                f"Workflow execution failed: {e}",
                details={
                    "user_id": ctx.user_id,
                    "trace_id": ctx.trace_id,
                    "message_id": ctx.message_id
                }
            )
            
        finally:
            # Clear execution context
            clear_execution_context()
    
    async def execute_batch(self, events: list[AutomationEvent]) -> list[ResponseEvent]:
        """Execute batch of events with controlled concurrency"""
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent executions
        
        async def execute_with_semaphore(event: AutomationEvent) -> ResponseEvent:
            async with semaphore:
                return await self.execute(event)
        
        results = await asyncio.gather(
            *[execute_with_semaphore(event) for event in events],
            return_exceptions=True
        )
        
        # Filter successful responses
        responses = []
        for i, result in enumerate(results):
            if isinstance(result, ResponseEvent):
                responses.append(result)
            else:
                logger.error(f"Batch execution error for event {i}: {result}")
        
        return responses


# Global execution engine
from typing import Optional as _Optional
_execution_engine: _Optional[WorkerExecutionEngine] = None


def get_execution_engine() -> WorkerExecutionEngine:
    """Get worker execution engine"""
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = WorkerExecutionEngine()
    return _execution_engine


__all__ = ["WorkerExecutionEngine", "get_execution_engine"]
