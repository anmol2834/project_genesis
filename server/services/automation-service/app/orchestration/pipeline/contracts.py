"""
Orchestration Pipeline - Interface Contracts
=============================================
Defines the contracts for pipeline stages.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
from enum import Enum


class PipelineStage(str, Enum):
    """Pipeline execution stages"""
    LOAD_CONTEXT = "load_context"
    FAST_PATH_CHECK = "fast_path_check"
    INTELLIGENCE = "intelligence"
    MEMORY_LOAD = "memory_load"
    MEMORY_ENRICHMENT = "memory_enrichment"
    CACHE_CHECK = "cache_check"
    RETRIEVAL = "retrieval"
    LLM_GENERATION = "llm_generation"
    VALIDATION = "validation"
    DECISION = "decision"
    DISPATCH = "dispatch"


@dataclass
class PipelineContext:
    """Context passed through pipeline stages"""
    user_id: str
    conversation_id: str
    message_id: str
    thread_id: str
    content: str
    subject: str
    automation_enabled: bool
    priority: int
    history: list[dict]
    
    # Populated during pipeline
    query_understanding: Optional[Any] = None
    memory: Optional[Any] = None
    retrieved_chunks: Optional[list] = None
    llm_response: Optional[Any] = None
    decision: Optional[Any] = None
    
    # Metadata
    stage_timings: dict[str, float] = None
    
    def __post_init__(self):
        if self.stage_timings is None:
            self.stage_timings = {}


@dataclass
class PipelineResult:
    """Result of pipeline execution"""
    status: str  # processed, skipped, error
    path: str    # fast, cached, slow
    action: str  # send, skip, draft
    result: dict
    elapsed_ms: float
    
    # Observability
    timings: dict[str, float]
    metadata: dict[str, Any]


class IPipelineStage(ABC):
    """Interface for pipeline stages"""
    
    @abstractmethod
    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """
        Execute this pipeline stage.
        
        Args:
            ctx: Pipeline context with all accumulated data
            
        Returns:
            Updated context for next stage
        """
        pass
    
    @abstractmethod
    def stage_name(self) -> PipelineStage:
        """Return the stage identifier"""
        pass


class IPipelineOrchestrator(ABC):
    """Interface for pipeline orchestration"""
    
    @abstractmethod
    async def execute_pipeline(self, event: dict) -> PipelineResult:
        """
        Execute the complete pipeline for an event.
        
        Args:
            event: Event from messaging layer
            
        Returns:
            Pipeline execution result
        """
        pass
    
    @abstractmethod
    async def execute_stage(
        self, 
        stage: IPipelineStage, 
        ctx: PipelineContext
    ) -> PipelineContext:
        """
        Execute a single stage with timeout and error handling.
        
        Args:
            stage: Pipeline stage to execute
            ctx: Current pipeline context
            
        Returns:
            Updated context
        """
        pass
