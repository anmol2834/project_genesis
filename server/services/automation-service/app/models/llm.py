"""
Global Models - LLM Contracts
==============================
LLM generation, grounding, and hallucination detection models.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.base import BaseLayerResult, BaseTenant, BaseReplayable
from app.models.enums import LLMProvider, PromptType, HallucinationSeverity


class PromptMessage(BaseModel):
    """Single prompt message"""
    role: PromptType
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None


class PromptPackage(BaseTenant):
    """Complete prompt for LLM with grounding"""
    messages: List[PromptMessage] = Field(default_factory=list)
    system_prompt: str = ""
    user_prompt: str = ""
    grounded_context: List[str] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    max_tokens: int = 500
    temperature: float = 0.7
    model: str = "gpt-4o-mini"
    token_count: int = 0
    
    def add_system(self, content: str) -> None:
        """Add system message"""
        self.messages.append(PromptMessage(role=PromptType.SYSTEM, content=content))
        self.system_prompt = content
    
    def add_user(self, content: str) -> None:
        """Add user message"""
        self.messages.append(PromptMessage(role=PromptType.USER, content=content))
        self.user_prompt = content


class GroundedContext(BaseModel):
    """Grounded context chunks for LLM"""
    profile_chunks: List[str] = Field(default_factory=list)
    product_chunks: List[str] = Field(default_factory=list)
    faq_chunks: List[str] = Field(default_factory=list)
    policy_chunks: List[str] = Field(default_factory=list)
    total_chunks: int = 0
    total_tokens: int = 0
    compression_ratio: float = 1.0


class LLMGenerationResult(BaseLayerResult):
    """LLM generation output"""
    response_text: str
    model: str = "gpt-4o-mini"
    provider: LLMProvider = LLMProvider.OPENAI
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    generation_confidence: float = 0.0
    finish_reason: str = "stop"
    streaming: bool = False


class HallucinationReport(BaseModel):
    """Hallucination detection result"""
    detected: bool
    severity: HallucinationSeverity
    hallucinated_claims: List[str] = Field(default_factory=list)
    unsupported_entities: List[str] = Field(default_factory=list)
    price_mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    feature_mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_penalty: float = 0.0
    guard_passed: bool = True
    guard_version: str = "1.0"


class TokenBudget(BaseModel):
    """Token budget management"""
    max_prompt_tokens: int = 3000
    max_completion_tokens: int = 500
    current_prompt_tokens: int = 0
    current_completion_tokens: int = 0
    remaining_prompt_tokens: int = 3000
    remaining_completion_tokens: int = 500
    exceeded: bool = False


class ValidationReport(BaseModel):
    """Response validation result"""
    valid: bool
    completeness_score: float = 0.0
    coherence_score: float = 0.0
    relevance_score: float = 0.0
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class LLMReplaySnapshot(BaseReplayable):
    """Snapshot for deterministic LLM replay"""
    prompt_package: PromptPackage
    grounded_context: GroundedContext
    generation_result: LLMGenerationResult
    hallucination_report: HallucinationReport
    model_version: str = "gpt-4o-mini-2024"
    temperature: float = 0.7
    seed: Optional[int] = None


__all__ = [
    "PromptMessage",
    "PromptPackage",
    "GroundedContext",
    "LLMGenerationResult",
    "HallucinationReport",
    "TokenBudget",
    "ValidationReport",
    "LLMReplaySnapshot",
]
