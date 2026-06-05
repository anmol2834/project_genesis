"""
LLM Layer - Pydantic Schemas
============================
Type-safe schemas for LLM operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class GenerationStatus(str, Enum):
    """LLM generation status"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INVALID_JSON = "invalid_json"
    HALLUCINATION_DETECTED = "hallucination_detected"
    RETRY_EXHAUSTED = "retry_exhausted"


class HallucinationRisk(str, Enum):
    """Hallucination risk level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ModelProvider(str, Enum):
    """Supported model providers"""
    OPENAI = "openai"
    LOCAL = "local"
    FALLBACK = "fallback"


# ══════════════════════════════════════════════════════════════════════════════
# Request Schemas
# ══════════════════════════════════════════════════════════════════════════════

class GenerationRequest(BaseModel):
    """Request for LLM generation"""
    system_prompt: str = Field(..., min_length=10, max_length=4000)
    user_prompt: str = Field(..., min_length=1, max_length=8000)
    max_tokens: int = Field(default=400, ge=50, le=2000)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    model: Optional[str] = None
    tenant_id: str = Field(..., min_length=1)
    thread_id: str = Field(..., min_length=1)
    request_id: Optional[str] = None
    
    # Context for validation
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    intent: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "system_prompt": "You are a helpful assistant...",
                "user_prompt": "Answer this question: ...",
                "max_tokens": 400,
                "temperature": 0.0,
                "tenant_id": "tenant_123",
                "thread_id": "thread_456"
            }
        }


# ══════════════════════════════════════════════════════════════════════════════
# Response Schemas
# ══════════════════════════════════════════════════════════════════════════════

class LLMResponse(BaseModel):
    """Structured LLM response"""
    reply: str = Field(..., description="Generated reply text")
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: GenerationStatus
    hallucination_risk: HallucinationRisk = HallucinationRisk.LOW
    
    # Metadata
    model: str
    provider: ModelProvider = ModelProvider.OPENAI
    tokens_used: int = Field(default=0, ge=0)
    generation_time_ms: float = Field(default=0.0, ge=0.0)
    
    # Grounding
    used_data: List[str] = Field(default_factory=list)
    grounded: bool = True
    
    # Validation
    validation_passed: bool = True
    validation_reason: Optional[str] = None
    
    # Additional notes
    notes: str = ""
    
    class Config:
        json_schema_extra = {
            "example": {
                "reply": "Based on the available data...",
                "confidence": 0.85,
                "status": "success",
                "hallucination_risk": "low",
                "model": "gpt-4o-mini",
                "tokens_used": 350,
                "used_data": ["product_x", "price_y"]
            }
        }


class StreamChunk(BaseModel):
    """Streaming response chunk"""
    content: str
    done: bool = False
    token_count: int = 0
    chunk_id: int


# ══════════════════════════════════════════════════════════════════════════════
# Validation Schemas
# ══════════════════════════════════════════════════════════════════════════════

class ValidationResult(BaseModel):
    """Validation result for generated response"""
    passed: bool
    reason: str
    score: float = Field(ge=0.0, le=1.0)
    detected_issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class GroundingCheck(BaseModel):
    """Grounding validation result"""
    is_grounded: bool
    coverage_score: float = Field(ge=0.0, le=1.0)
    unsupported_claims: List[str] = Field(default_factory=list)
    supported_facts: List[str] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# Prompt Building Schemas
# ══════════════════════════════════════════════════════════════════════════════

class PromptComponents(BaseModel):
    """Components for prompt construction"""
    system_instructions: str
    grounded_data: str
    memory_context: str
    task_instruction: str
    safety_rules: str


class TokenBudget(BaseModel):
    """Token allocation for prompt components"""
    system_prompt: int = Field(ge=0, le=1000)
    context: int = Field(ge=0, le=6000)
    user_query: int = Field(ge=0, le=2000)
    completion: int = Field(ge=0, le=2000)
    total_limit: int = Field(default=8000, ge=100, le=16000)
    
    @validator('total_limit')
    def validate_total(cls, v, values):
        used = values.get('system_prompt', 0) + values.get('context', 0) + \
               values.get('user_query', 0) + values.get('completion', 0)
        if used > v:
            raise ValueError(f"Total budget {v} exceeded by component allocation {used}")
        return v


# ══════════════════════════════════════════════════════════════════════════════
# Provider Schemas
# ══════════════════════════════════════════════════════════════════════════════

class ProviderConfig(BaseModel):
    """LLM provider configuration"""
    provider: ModelProvider
    model_name: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)
    rate_limit_per_minute: Optional[int] = None


class ProviderHealthStatus(BaseModel):
    """Provider health check result"""
    provider: ModelProvider
    healthy: bool
    latency_ms: float
    error: Optional[str] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# Metrics Schemas
# ══════════════════════════════════════════════════════════════════════════════

class GenerationMetrics(BaseModel):
    """Metrics for a generation request"""
    request_id: str
    tenant_id: str
    thread_id: str
    
    # Timing
    total_time_ms: float
    prompt_build_time_ms: float
    generation_time_ms: float
    validation_time_ms: float
    
    # Tokens
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    # Quality
    confidence: float
    hallucination_risk: HallucinationRisk
    validation_passed: bool
    
    # Retries
    retry_count: int = 0
    final_status: GenerationStatus
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# Cache Schemas
# ══════════════════════════════════════════════════════════════════════════════

class CachedGeneration(BaseModel):
    """Cached LLM generation"""
    prompt_hash: str
    response: LLMResponse
    cached_at: datetime
    hit_count: int = 1
    ttl_seconds: int


# ══════════════════════════════════════════════════════════════════════════════
# Dataclasses (for internal use, lighter weight)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PromptContext:
    """Context for prompt building"""
    retrieved_chunks: List[Any]
    memory_summary: Optional[str]
    conversation_history: List[Dict[str, str]]
    intent: str
    entities: Dict[str, Any]
    tenant_tone: str
    language: str


@dataclass
class GenerationTrace:
    """Trace for debugging generation"""
    request_id: str
    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_response: Optional[LLMResponse]
    validation_results: List[ValidationResult]
    retries: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# Export All
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Enums
    "GenerationStatus",
    "HallucinationRisk",
    "ModelProvider",
    
    # Request/Response
    "GenerationRequest",
    "LLMResponse",
    "StreamChunk",
    
    # Validation
    "ValidationResult",
    "GroundingCheck",
    
    # Prompts
    "PromptComponents",
    "TokenBudget",
    "PromptContext",
    
    # Providers
    "ProviderConfig",
    "ProviderHealthStatus",
    
    # Metrics
    "GenerationMetrics",
    
    # Cache
    "CachedGeneration",
    
    # Trace
    "GenerationTrace",
]
