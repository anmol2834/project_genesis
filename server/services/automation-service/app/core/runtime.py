"""
Core - Application Runtime
===========================
Enterprise application runtime - the heartbeat of automation-service.
"""
import asyncio
from typing import Optional
from datetime import datetime
from app.core.startup import create_startup_sequence
from app.core.shutdown import create_shutdown_sequence, setup_signal_handlers
from app.core.dependency_injection import get_container
from app.observability import get_logger

logger = get_logger(__name__)


class AutomationServiceRuntime:
    """
    Enterprise application runtime.
    Orchestrates complete service lifecycle.
    """
    
    def __init__(self):
        self.started_at: Optional[datetime] = None
        self.is_running = False
        self._startup_engine = None
        self._shutdown_engine = None
        self._worker_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start automation-service runtime"""
        if self.is_running:
            logger.warning("Runtime already running")
            return
        
        self.started_at = datetime.utcnow()
        
        # Create and execute startup sequence
        self._startup_engine = await create_startup_sequence()
        await self._startup_engine.execute()
        
        # Create shutdown engine
        self._shutdown_engine = await create_shutdown_sequence()
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        setup_signal_handlers(loop, self._shutdown_engine)
        
        self.is_running = True
        logger.info("Automation-service runtime started successfully")
    
    async def run_workers(self) -> None:
        """Start worker runtime"""
        from app.workers.runtime import get_worker_runtime
        
        worker_runtime = get_worker_runtime()
        self._worker_task = asyncio.create_task(worker_runtime.run())
        
        logger.info("Worker runtime started")
        
        # Wait for workers
        try:
            await self._worker_task
        except asyncio.CancelledError:
            logger.info("Worker runtime cancelled")
    
    async def shutdown(self) -> None:
        """Shutdown automation-service runtime"""
        if not self.is_running:
            return
        
        logger.info("Initiating graceful shutdown...")
        
        # Cancel worker task
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # Execute shutdown sequence
        if self._shutdown_engine:
            await self._shutdown_engine.execute()
        
        self.is_running = False
        
        uptime = (datetime.utcnow() - self.started_at).total_seconds() if self.started_at else 0
        logger.info(f"Runtime shutdown complete (uptime: {uptime:.1f}s)")
    
    async def run(self) -> None:
        """Run complete lifecycle"""
        try:
            await self.start()
            await self.run_workers()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()


# Global runtime instance
_runtime: Optional[AutomationServiceRuntime] = None


def get_runtime() -> AutomationServiceRuntime:
    """Get global runtime instance"""
    global _runtime
    if _runtime is None:
        _runtime = AutomationServiceRuntime()
    return _runtime


async def run_application() -> None:
    """Run automation-service application"""
    runtime = get_runtime()
    await runtime.run()


__all__ = ["AutomationServiceRuntime", "get_runtime", "run_application"]
