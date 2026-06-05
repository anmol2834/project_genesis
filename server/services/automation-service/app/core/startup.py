"""
Core - Startup Engine
======================
Enterprise startup lifecycle with fail-fast validation.
"""
import asyncio
from typing import List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from app.observability import get_logger
from app.core.exceptions import ConfigurationError

logger = get_logger(__name__)


@dataclass
class StartupTask:
    """Startup task definition"""
    name: str
    factory: Callable
    is_async: bool
    required: bool = True
    timeout_seconds: float = 30.0


class StartupEngine:
    """Enterprise startup orchestration"""
    
    def __init__(self):
        self.tasks: List[StartupTask] = []
        self.completed: List[str] = []
        self.failed: List[str] = []
        self.start_time: Optional[datetime] = None
    
    def register_task(
        self,
        name: str,
        factory: Callable,
        is_async: bool = True,
        required: bool = True,
        timeout_seconds: float = 30.0
    ) -> None:
        """Register startup task"""
        self.tasks.append(StartupTask(
            name=name,
            factory=factory,
            is_async=is_async,
            required=required,
            timeout_seconds=timeout_seconds
        ))
        logger.debug(f"Registered startup task: {name}")
    
    async def execute(self) -> None:
        """Execute all startup tasks in order"""
        self.start_time = datetime.utcnow()
        logger.info("═" * 70)
        logger.info("AUTOMATION-SERVICE STARTUP")
        logger.info("═" * 70)
        
        for task in self.tasks:
            await self._execute_task(task)
        
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        
        if self.failed:
            logger.error("═" * 70)
            logger.error(f"STARTUP FAILED ({len(self.failed)} tasks failed)")
            logger.error(f"Failed tasks: {', '.join(self.failed)}")
            logger.error("═" * 70)
            raise ConfigurationError(f"Startup failed: {', '.join(self.failed)}")
        
        logger.info("═" * 70)
        logger.info(f"STARTUP COMPLETE ({elapsed:.2f}s)")
        logger.info(f"Completed tasks: {len(self.completed)}")
        logger.info("═" * 70)
    
    async def _execute_task(self, task: StartupTask) -> None:
        """Execute single startup task"""
        logger.info(f"⚙ {task.name}...")
        
        try:
            if task.is_async:
                await asyncio.wait_for(
                    task.factory(),
                    timeout=task.timeout_seconds
                )
            else:
                task.factory()
            
            self.completed.append(task.name)
            logger.info(f"✓ {task.name} complete")
            
        except asyncio.TimeoutError:
            self.failed.append(task.name)
            error_msg = f"✗ {task.name} TIMEOUT ({task.timeout_seconds}s)"
            logger.error(error_msg)
            if task.required:
                raise ConfigurationError(f"{task.name} timeout")
        
        except Exception as e:
            self.failed.append(task.name)
            logger.error(f"✗ {task.name} FAILED: {e}")
            if task.required:
                raise


async def create_startup_sequence() -> StartupEngine:
    """Create standard startup sequence"""
    engine = StartupEngine()
    
    # 1. Configuration
    engine.register_task(
        name="Load Configuration",
        factory=_initialize_config,
        is_async=False,
        required=True
    )
    
    # 2. Observability Bootstrap
    engine.register_task(
        name="Initialize Observability",
        factory=_initialize_observability,
        is_async=False,
        required=True
    )
    
    # 3. Resource Pools
    engine.register_task(
        name="Initialize Resource Pools",
        factory=_initialize_resources,
        is_async=True,
        required=True,
        timeout_seconds=30.0
    )
    
    # 4. Storage Layer
    engine.register_task(
        name="Initialize Storage",
        factory=_initialize_storage,
        is_async=True,
        required=True
    )
    
    # 5. Memory Layer
    engine.register_task(
        name="Initialize Memory",
        factory=_initialize_memory,
        is_async=True,
        required=True
    )
    
    # 6. Intelligence Layer
    engine.register_task(
        name="Initialize Intelligence",
        factory=_initialize_intelligence,
        is_async=True,
        required=True
    )
    
    # 7. Retrieval Layer
    engine.register_task(
        name="Initialize Retrieval",
        factory=_initialize_retrieval,
        is_async=True,
        required=True
    )
    
    # 8. LLM Layer
    engine.register_task(
        name="Initialize LLM",
        factory=_initialize_llm,
        is_async=True,
        required=True
    )
    
    # 9. Orchestration Engine
    engine.register_task(
        name="Initialize Orchestration",
        factory=_initialize_orchestration,
        is_async=False,
        required=True
    )
    
    # 10. Messaging Layer
    engine.register_task(
        name="Initialize Messaging",
        factory=_initialize_messaging,
        is_async=True,
        required=True
    )
    
    # 11. Worker Runtime
    engine.register_task(
        name="Initialize Workers",
        factory=_initialize_workers,
        is_async=True,
        required=True
    )
    
    # 12. API Layer
    engine.register_task(
        name="Initialize API",
        factory=_initialize_api,
        is_async=False,
        required=False
    )
    
    return engine


# ── Task Implementations ─────────────────────────────────────────────────────

def _initialize_config():
    """Initialize configuration"""
    from shared.config import get_config
    config = get_config()
    logger.info(f"Environment: {config.ENVIRONMENT}")


def _initialize_observability():
    """Initialize observability"""
    from app.observability import get_tracer, get_logger, get_metrics_collector
    get_tracer()
    get_logger(__name__)
    get_metrics_collector()


async def _initialize_resources():
    """Initialize resource pools"""
    from app.core.resource_management import initialize_resources
    await initialize_resources()


async def _initialize_storage():
    """Initialize storage layer"""
    from app.storage.redis_storage import redis_storage
    from app.storage.workflow_repository import workflow_repository
    # Storage initialization happens via resource manager


async def _initialize_memory():
    """Initialize memory layer"""
    # Memory layer is stateless, no initialization needed
    pass


async def _initialize_intelligence():
    """Initialize intelligence layer"""
    # Intelligence layer is stateless
    pass


async def _initialize_retrieval():
    """Initialize retrieval layer"""
    # Retrieval layer uses resource manager
    pass


async def _initialize_llm():
    """Initialize LLM layer"""
    # LLM providers are lazy-initialized
    pass


def _initialize_orchestration():
    """Initialize orchestration engine"""
    from app.orchestration.execution_engine import execution_engine
    logger.debug("Orchestration engine ready")


async def _initialize_messaging():
    """Initialize messaging layer"""
    # Messaging consumers will be started by workers
    pass


async def _initialize_workers():
    """Initialize worker runtime"""
    # Workers started separately after startup complete
    logger.debug("Worker runtime ready")


def _initialize_api():
    """Initialize API layer"""
    logger.debug("API layer ready")


__all__ = ["StartupEngine", "create_startup_sequence"]
