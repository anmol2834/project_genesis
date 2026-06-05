"""
LLM Layer - Interface Contracts
================================
Strict interface definitions for all LLM components.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncIterator
from app.llm.schemas import (
    GenerationRequest,
    LLMResponse,
    ValidationResult,
    GroundingCheck,
    PromptComponents,
    TokenBudget,
    StreamChunk,
    ProviderHealthStatus,
)


# ══════════════════════════════════════════════════════════════════════════════
# Provider Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class ILLMProvider(ABC):
    """Interface for LLM providers (OpenAI, local models, etc.)"""
    
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming response"""
        pass
    
    @abstractmethod
    async def health_check(self) -> ProviderHealthStatus:
        """Check provider health"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Prompt Building Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class IPromptBuilder(ABC):
    """Interface for prompt construction"""
    
    @abstractmethod
    async def build_prompt(
        self,
        retrieved_chunks: List[Any],
        memory_summary: Optional[str],
        conversation_history: List[Dict[str, str]],
        intent: str,
        entities: Dict[str, Any],
        **kwargs
    ) -> tuple[str, str, int]:
        """
        Build (system_prompt, user_prompt, max_tokens).
        
        Returns:
            tuple: (system_prompt, user_prompt, max_tokens)
        """
        pass
    
    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Grounding Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class IGroundingEngine(ABC):
    """Interface for grounding validation"""
    
    @abstractmethod
    async def validate_grounding(
        self,
        generated_text: str,
        retrieved_chunks: List[Any],
        **kwargs
    ) -> GroundingCheck:
        """
        Validate that generated text is grounded in retrieved chunks.
        
        Args:
            generated_text: LLM generated text
            retrieved_chunks: Source chunks for grounding
            
        Returns:
            GroundingCheck with validation result
        """
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Hallucination Guard Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class IHallucinationGuard(ABC):
    """Interface for hallucination detection"""
    
    @abstractmethod
    async def validate(
        self,
        reply: str,
        chunks: List[Any],
        intent: str,
        **kwargs
    ) -> ValidationResult:
        """
        Validate LLM reply for hallucinations.
        
        Args:
            reply: Generated reply
            chunks: Retrieved chunks for validation
            intent: User intent
            
        Returns:
            ValidationResult indicating if validation passed
        """
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Response Validation Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class IResponseValidator(ABC):
    """Interface for response quality validation"""
    
    @abstractmethod
    async def validate_response(
        self,
        response: LLMResponse,
        request: GenerationRequest,
        **kwargs
    ) -> ValidationResult:
        """
        Validate response quality (coherence, completeness, formatting).
        
        Args:
            response: Generated LLM response
            request: Original request
            
        Returns:
            ValidationResult with quality assessment
        """
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Caching Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class IGenerationCache(ABC):
    """Interface for generation caching"""
    
    @abstractmethod
    async def get(self, prompt_hash: str) -> Optional[LLMResponse]:
        """Get cached generation"""
        pass
    
    @abstractmethod
    async def set(
        self,
        prompt_hash: str,
        response: LLMResponse,
        ttl_seconds: int
    ) -> bool:
        """Cache generation"""
        pass
    
    @abstractmethod
    async def invalidate(self, pattern: str) -> int:
        """Invalidate cache by pattern"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Token Management Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class ITokenManager(ABC):
    """Interface for token management"""
    
    @abstractmethod
    def calculate_budget(
        self,
        context_size: int,
        max_completion: int
    ) -> TokenBudget:
        """Calculate token budget for request"""
        pass
    
    @abstractmethod
    async def track_usage(
        self,
        tenant_id: str,
        tokens_used: int,
        model: str
    ) -> None:
        """Track token usage for tenant"""
        pass
    
    @abstractmethod
    async def check_budget(
        self,
        tenant_id: str,
        requested_tokens: int
    ) -> bool:
        """Check if tenant has budget for request"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Compression Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class IContextCompressor(ABC):
    """Interface for context compression"""
    
    @abstractmethod
    async def compress(
        self,
        chunks: List[Any],
        max_tokens: int,
        priority_keywords: Optional[List[str]] = None
    ) -> str:
        """
        Compress context to fit token budget.
        
        Args:
            chunks: Retrieved chunks to compress
            max_tokens: Maximum tokens for compressed context
            priority_keywords: Keywords to prioritize
            
        Returns:
            Compressed context string
        """
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Observability Interfaces
# ══════════════════════════════════════════════════════════════════════════════

class ILLMMetrics(ABC):
    """Interface for LLM metrics collection"""
    
    @abstractmethod
    async def record_generation(
        self,
        request_id: str,
        tenant_id: str,
        latency_ms: float,
        tokens: int,
        status: str,
        **kwargs
    ) -> None:
        """Record generation metrics"""
        pass
    
    @abstractmethod
    async def record_hallucination(
        self,
        tenant_id: str,
        thread_id: str,
        reason: str
    ) -> None:
        """Record hallucination incident"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Orchestration Interface
# ══════════════════════════════════════════════════════════════════════════════

class ILLMOrchestrator(ABC):
    """Main LLM orchestration interface"""
    
    @abstractmethod
    async def generate_response(
        self,
        request: GenerationRequest
    ) -> LLMResponse:
        """
        Main entry point for LLM generation.
        Orchestrates entire pipeline: prompt building, generation, validation.
        
        Args:
            request: Generation request with all context
            
        Returns:
            Validated LLM response
        """
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Export All
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ILLMProvider",
    "IPromptBuilder",
    "IGroundingEngine",
    "IHallucinationGuard",
    "IResponseValidator",
    "IGenerationCache",
    "ITokenManager",
    "IContextCompressor",
    "ILLMMetrics",
    "ILLMOrchestrator",
]
