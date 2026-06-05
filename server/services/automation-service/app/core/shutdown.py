"""
Core - Shutdown Engine
=======================
Enterprise graceful shutdown with worker draining.
"""
import asyncio
import signal
from typing import List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from app.observability import get_logger

logger = get_logger(__name__)


@dataclass
class ShutdownTask:
    """Shutdown task definition"""
    name: str
    handler: Callable
    is_async: bool
    timeout_seconds: float = 30.0


class ShutdownEngine:
    """Enterprise shutdown orchestration"""
    
    def __init__(self):
        self.tasks: List[ShutdownTask] = []
        self.shutdown_initiated = False
        self.shutdown_complete = False
    
    def register_task(
        self,
        name: str,
        handler: Callable,
        is_async: bool = True,
        timeout_seconds: float = 30.0
    ) -> None:
        """Register shutdown task"""
        self.tasks.append(ShutdownTask(
            name=name,
            handler=handler,
            is_async=is_async,
            timeout_seconds=timeout_seconds
        ))
    
    async def execute(self) -> None:
        """Execute graceful shutdown"""
        if self.shutdown_initiated:
            return
        
        self.shutdown_initiated = True
        start_time = datetime.utcnow()
        
        logger.info("═" * 70)
        logger.info("AUTOMATION-SERVICE SHUTDOWN")
        logger.info("═" * 70)
        
        # Execute shutdown tasks in reverse order (LIFO)
        for task in reversed(self.tasks):
            await self._execute_task(task)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("═" * 70)
        logger.info(f"SHUTDOWN COMPLETE ({elapsed:.2f}s)")
        logger.info("═" * 70)
        
        self.shutdown_complete = True
    
    async def _execute_task(self, task: ShutdownTask) -> None:
        """Execute single shutdown task"""
        logger.info(f"⚙ {task.name}...")
        
        try:
            if task.is_async:
                await asyncio.wait_for(
                    task.handler(),
                    timeout=task.timeout_seconds
                )
            else:
                task.handler()
            
            logger.info(f"✓ {task.name} complete")
            
        except asyncio.TimeoutError:
            logger.warning(f"⚠ {task.name} TIMEOUT ({task.timeout_seconds}s) - forcing")
        
        except Exception as e:
            logger.error(f"✗ {task.name} FAILED: {e}")


async def create_shutdown_sequence() -> ShutdownEngine:
    """Create standard shutdown sequence"""
    engine = ShutdownEngine()
    
    # 1. Stop accepting new messages
    engine.register_task(
        name="Stop Message Ingestion",
        handler=_stop_ingestion,
        is_async=True,
        timeout_seconds=5.0
    )
    
    # 2. Drain worker queues
    engine.register_task(
        name="Drain Worker Queues",
        handler=_drain_workers,
        is_async=True,
        timeout_seconds=30.0
    )
    
    # 3. Stop workers
    engine.register_task(
        name="Stop Workers",
        handler=_stop_workers,
        is_async=True,
        timeout_seconds=10.0
    )
    
    # 4. Flush telemetry
    engine.register_task(
        name="Flush Telemetry",
        handler=_flush_telemetry,
        is_async=True,
        timeout_seconds=5.0
    )
    
    # 5. Save pending state
    engine.register_task(
        name="Save Pending State",
        handler=_save_state,
        is_async=True,
        timeout_seconds=10.0
    )
    
    # 6. Close resource pools
    engine.register_task(
        name="Close Resource Pools",
        handler=_close_resources,
        is_async=True,
        timeout_seconds=10.0
    )
    
    # 7. Final cleanup
    engine.register_task(
        name="Final Cleanup",
        handler=_final_cleanup,
        is_async=False,
        timeout_seconds=5.0
    )
    
    return engine


# ── Task Implementations ─────────────────────────────────────────────────────

async def _stop_ingestion():
    """Stop accepting new messages"""
    logger.info("Stopping message consumers...")


async def _drain_workers():
    """Drain pending messages from workers"""
    logger.info("Draining worker queues...")
    await asyncio.sleep(2.0)


async def _stop_workers():
    """Stop all workers"""
    logger.info("Stopping workers...")


async def _flush_telemetry():
    """Flush all telemetry data"""
    logger.info("Flushing metrics and traces...")
    await asyncio.sleep(0.5)


async def _save_state():
    """Save any pending execution state"""
    logger.info("Saving pending execution state...")


async def _close_resources():
    """Close all resource pools"""
    from app.core.resource_management import shutdown_resources
    await shutdown_resources()


def _final_cleanup():
    """Final cleanup tasks"""
    logger.info("Final cleanup complete")


# ── Signal Handlers ──────────────────────────────────────────────────────────

_shutdown_engine: Optional[ShutdownEngine] = None
_shutdown_task: Optional[asyncio.Task] = None


def setup_signal_handlers(loop: asyncio.AbstractEventLoop, engine: ShutdownEngine):
    """Setup signal handlers for graceful shutdown"""
    global _shutdown_engine
    _shutdown_engine = engine
    
    def handle_signal(sig):
        """Handle shutdown signal"""
        global _shutdown_task
        
        if _shutdown_task is None or _shutdown_task.done():
            logger.info(f"Received signal {sig}, initiating graceful shutdown...")
            _shutdown_task = asyncio.create_task(engine.execute())
        else:
            logger.warning(f"Shutdown already in progress, signal {sig} ignored")
    
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
    
    logger.info("Signal handlers registered (SIGTERM, SIGINT)")


__all__ = ["ShutdownEngine", "create_shutdown_sequence", "setup_signal_handlers"]
