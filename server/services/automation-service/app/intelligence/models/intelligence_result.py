"""
Intelligence Result Model
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

class Intent(str, Enum):
    INTEREST = "interest"
    PRICING = "pricing"
    SUPPORT = "support"
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    UNKNOWN = "unknown"

class ConversationStage(str, Enum):
    AWARENESS = "awareness"
    INTEREST = "interest"
    CONSIDERATION = "consideration"
    DECISION = "decision"

class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RetrievalStrategy(str, Enum):
    EXACT = "exact"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    SKIP = "skip"

class QueryPlan(BaseModel):
    search_queries: List[str] = Field(default_factory=list)
    strategy: str = "hybrid"
    filters: Dict[str, Any] = Field(default_factory=dict)

class ContinuationResolution(BaseModel):
    is_continuation: bool = False
    resolved_query: str = ""
    context_used: List[str] = Field(default_factory=list)

class RiskAnalysis(BaseModel):
    risk_level: str = "low"
    risk_factors: List[str] = Field(default_factory=list)
    requires_escalation: bool = False

class ConfidenceAnalysis(BaseModel):
    overall_confidence: float = 0.0
    intent_confidence: float = 0.0
    entity_confidence: float = 0.0

class FastPathDecision(BaseModel):
    can_fast_path: bool = False
    reason: str = ""
    cached_response: Optional[str] = None

class IntelligenceResult(BaseModel):
    intent: str
    sub_intent: str = ""
    entities: Dict[str, Any] = Field(default_factory=dict)
    confidence: float
    retrieval_strategy: str
    query_plan: QueryPlan = Field(default_factory=QueryPlan)
    continuation: ContinuationResolution = Field(default_factory=ContinuationResolution)
    risk: RiskAnalysis = Field(default_factory=RiskAnalysis)
    confidence_analysis: ConfidenceAnalysis = Field(default_factory=ConfidenceAnalysis)
    fast_path: FastPathDecision = Field(default_factory=FastPathDecision)

__all__ = [
    "IntelligenceResult",
    "Intent",
    "ConversationStage",
    "Urgency",
    "RetrievalStrategy",
    "QueryPlan",
    "ContinuationResolution",
    "RiskAnalysis",
    "ConfidenceAnalysis",
    "FastPathDecision",
]
