"""
Global Models - Intelligence Contracts
=======================================
Consolidated intelligence layer models.
Extends app/intelligence/models with global standards.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.base import BaseLayerResult
from app.models.enums import (
    Intent, ConversationStage, Urgency, RiskLevel, RetrievalStrategy
)


class IntelligenceResult(BaseLayerResult):
    """
    Complete intelligence analysis result.
    Consolidates intelligence/models/intelligence_result.IntelligenceResult.
    """
    # Core intent
    primary_intent: Intent
    sub_intent: str
    intent_confidence: float
    secondary_intents: List[Intent] = Field(default_factory=list)
    
    # Query transformation
    rewritten_query: str = ""
    keywords: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    
    # Entities
    entities: Dict[str, Any] = Field(default_factory=dict)
    entity_confidence: float = 0.0
    
    # Conversation analysis
    conversation_stage: ConversationStage = ConversationStage.AWARENESS
    conversation_type: str = "new_query"
    is_continuation: bool = False
    continuation_context: Optional[str] = None
    
    # Urgency & risk
    urgency: Urgency = Urgency.LOW
    risk_level: RiskLevel = RiskLevel.LOW
    risk_categories: List[str] = Field(default_factory=list)
    requires_human: bool = False
    escalation_reason: Optional[str] = None
    
    # Retrieval planning
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC
    requires_retrieval: bool = True
    exact_keywords: List[str] = Field(default_factory=list)
    semantic_queries: List[str] = Field(default_factory=list)
    metadata_filters: Dict[str, Any] = Field(default_factory=dict)
    expected_chunk_types: List[str] = Field(default_factory=list)
    cache_reusable: bool = False
    
    # Feature matching
    use_case: str = ""
    strict_requirements: List[str] = Field(default_factory=list)
    negative_constraints: List[str] = Field(default_factory=list)
    
    # Language
    language: str = "english"
    language_confidence: float = 1.0
    
    # Multi-intent
    is_multi_intent: bool = False
    decomposed_queries: List[str] = Field(default_factory=list)
    
    # Memory integration
    memory_enriched: bool = False
    memory_confidence: float = 0.0
    inherited_entities: Dict[str, Any] = Field(default_factory=dict)
    
    # Confidence
    final_confidence: float = 0.0
    confidence_signals: Dict[str, float] = Field(default_factory=dict)
    
    # Fast path
    fast_path_eligible: bool = False
    fast_path_response: Optional[str] = None
    
    # Routing
    department: str = "sales"
    processing_time_ms: float = 0.0


class ContinuationResolution(BaseModel):
    """Continuation reference resolution result"""
    is_continuation: bool
    resolved: bool
    resolved_intent: Optional[Intent] = None
    resolved_entity: Optional[str] = None
    resolved_entity_type: Optional[str] = None
    resolved_query: Optional[str] = None
    reference_type: str = "none"
    last_topic: Optional[str] = None
    confidence: float = 0.0
    source: str = "memory"


class RiskAnalysis(BaseModel):
    """Risk assessment result"""
    risk_level: RiskLevel
    requires_human: bool
    risk_categories: List[str] = Field(default_factory=list)
    is_legal_query: bool = False
    is_billing_query: bool = False
    is_complaint: bool = False
    is_angry_customer: bool = False
    has_hallucination_risk: bool = False
    escalation_reason: Optional[str] = None
    escalation_priority: str = "medium"
    confidence: float = 0.0
    signals: Dict[str, float] = Field(default_factory=dict)


class ConfidenceAnalysis(BaseModel):
    """Multi-signal confidence fusion"""
    final_confidence: float
    intent_confidence: float = 0.0
    entity_confidence: float = 0.0
    continuation_confidence: float = 0.0
    memory_confidence: float = 0.0
    language_confidence: float = 0.0
    query_plan_confidence: float = 0.0
    weights: Dict[str, float] = Field(default_factory=dict)
    breakdown: str = ""


__all__ = [
    "IntelligenceResult",
    "ContinuationResolution",
    "RiskAnalysis",
    "ConfidenceAnalysis",
]
