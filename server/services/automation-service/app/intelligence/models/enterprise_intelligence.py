"""
Enterprise Intelligence Models
================================
Advanced conversational intelligence structures for enterprise-grade automation.
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ConversationStage(str, Enum):
    """Customer journey stage"""
    AWARENESS = "awareness"
    INTEREST = "interest"
    CONSIDERATION = "consideration"
    DECISION = "decision"
    RETENTION = "retention"
    ESCALATION = "escalation"


class CustomerType(str, Enum):
    """Customer segment"""
    B2B = "b2b"
    B2C = "b2c"
    ENTERPRISE = "enterprise"
    SMB = "smb"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"


class Sentiment(str, Enum):
    """Emotional tone"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"
    URGENT = "urgent"


class Urgency(str, Enum):
    """Request urgency"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IntentType(str, Enum):
    """Primary intent categories"""
    PRICING_INQUIRY = "pricing_inquiry"
    PRODUCT_INQUIRY = "product_inquiry"
    SUPPORT_REQUEST = "support_request"
    TECHNICAL_SUPPORT_REQUEST = "technical_support_request"
    TECHNICAL_ASSISTANCE = "technical_assistance"
    FEATURE_REQUEST = "feature_request"
    COMPLAINT = "complaint"
    REFUND_REQUEST = "refund_request"
    CUSTOMIZATION_REQUEST = "customization_request"
    BULK_PURCHASE = "bulk_purchase"
    PARTNERSHIP_INQUIRY = "partnership_inquiry"
    TECHNICAL_QUESTION = "technical_question"
    BILLING_INQUIRY = "billing_inquiry"
    ACCOUNT_ISSUE = "account_issue"
    GENERAL_INQUIRY = "general_inquiry"
    FOLLOW_UP = "follow_up"
    GREETING = "greeting"
    ONBOARDING = "onboarding"
    UNKNOWN = "unknown"


class ResponseTone(str, Enum):
    """Recommended response tone"""
    PROFESSIONAL_CONSULTATIVE = "professional_consultative"
    FRIENDLY_SUPPORTIVE = "friendly_supportive"
    TECHNICAL_DETAILED = "technical_detailed"
    EMPATHETIC_APOLOGETIC = "empathetic_apologetic"
    CONCISE_DIRECT = "concise_direct"
    SALES_PERSUASIVE = "sales_persuasive"


class PromptTemplate(str, Enum):
    """Dynamic prompt family"""
    SALES_PRICING = "sales_pricing_consultative"
    SALES_PRODUCT = "sales_product_discovery"
    SALES_PRODUCT_INQUIRY = "sales_product_inquiry"
    SUPPORT_TECHNICAL = "support_technical_troubleshooting"
    SUPPORT_TECHNICAL_SHORT = "support_technical"
    SUPPORT_GENERAL = "support_general_inquiry"
    PRODUCT_INQUIRY_RESPONSE = "product_inquiry_response"
    TECHNICAL_SUPPORT_RESPONSE = "technical_support_response"
    GENERAL_FOLLOWUP = "general_followup"
    GENERAL_ENGAGEMENT = "general_engagement"
    ESCALATION_COMPLAINT = "escalation_complaint_handling"
    ESCALATION_REFUND = "escalation_refund_request"
    ONBOARDING = "onboarding_guidance"
    RETENTION = "retention_upsell"
    FOLLOW_UP = "follow_up_continuation"
    SHORT_REPLY = "short_reply_continuation"
    MULTI_INTENT = "multi_intent_enterprise"
    DEFAULT = "default_professional"


class ConversationAnalysis(BaseModel):
    """Deep conversation understanding"""
    stage: ConversationStage
    customer_type: CustomerType
    sentiment: Sentiment
    urgency: Urgency
    intent_confidence: float = Field(ge=0.0, le=1.0)


class IntentDefinition(BaseModel):
    """Structured intent with confidence"""
    type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)


class EntityExtraction(BaseModel):
    """Comprehensive entity extraction"""
    products: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)
    quantities: List[str] = Field(default_factory=list)
    pricing_terms: List[str] = Field(default_factory=list)
    technical_terms: List[str] = Field(default_factory=list)
    competitors: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    timelines: List[str] = Field(default_factory=list)
    budget_indicators: List[str] = Field(default_factory=list)


class SearchPlan(BaseModel):
    """Multi-dimensional search strategy"""
    exact_search_queries: List[str] = Field(default_factory=list)
    semantic_queries: List[str] = Field(default_factory=list)
    metadata_queries: List[str] = Field(default_factory=list)
    support_queries: List[str] = Field(default_factory=list)
    pricing_queries: List[str] = Field(default_factory=list)
    followup_queries: List[str] = Field(default_factory=list)


class RetrievalStrategy(BaseModel):
    """Retrieval execution plan"""
    cache_lookup_first: bool = True
    exact_match_priority: bool = False
    semantic_search: bool = True
    reranking_required: bool = True
    metadata_filtering: bool = True
    fusion_required: bool = True


class BusinessReasoning(BaseModel):
    """Business context understanding"""
    likely_goal: str = ""
    possible_objections: List[str] = Field(default_factory=list)
    upsell_opportunities: List[str] = Field(default_factory=list)
    handoff_risk: bool = False


class ResponseStrategy(BaseModel):
    """Response generation strategy"""
    tone: ResponseTone
    prompt_template: PromptTemplate
    response_depth: str = "balanced"  # concise, balanced, detailed


class EnterpriseIntelligenceResult(BaseModel):
    """
    Complete enterprise intelligence output.
    This is the operating system for the entire pipeline.
    """
    # Conversation understanding
    conversation_analysis: ConversationAnalysis
    
    # Intent classification
    primary_intents: List[IntentDefinition]
    secondary_intents: List[IntentDefinition] = Field(default_factory=list)
    support_intents: List[str] = Field(default_factory=list)
    sales_intents: List[str] = Field(default_factory=list)
    
    # Entity extraction
    entities: EntityExtraction
    
    # Search planning
    search_plan: SearchPlan
    
    # Retrieval strategy
    retrieval_strategy: RetrievalStrategy
    
    # Business reasoning
    business_reasoning: BusinessReasoning
    
    # Response strategy
    response_strategy: ResponseStrategy
    
    # Metadata
    turn_count: int = 0
    is_continuation: bool = False
    requires_escalation: bool = False
    processing_latency_ms: float = 0.0


__all__ = [
    "EnterpriseIntelligenceResult",
    "ConversationAnalysis",
    "IntentDefinition",
    "EntityExtraction",
    "SearchPlan",
    "RetrievalStrategy",
    "BusinessReasoning",
    "ResponseStrategy",
    "ConversationStage",
    "CustomerType",
    "Sentiment",
    "Urgency",
    "IntentType",
    "ResponseTone",
    "PromptTemplate",
]
