"""
Intelligence Models Module
"""
from app.intelligence.models.intelligence_result import (
    IntelligenceResult,
    Intent,
    ConversationStage,
    Urgency,
    RetrievalStrategy,
    QueryPlan,
    ContinuationResolution,
    RiskAnalysis,
    ConfidenceAnalysis,
    FastPathDecision,
)

try:
    from app.intelligence.models.enterprise_intelligence import (
        EnterpriseIntelligenceResult,
        ConversationAnalysis,
        IntentDefinition,
        EntityExtraction,
        SearchPlan,
        RetrievalStrategy as EnterpriseRetrievalStrategy,
        BusinessReasoning,
        ResponseStrategy,
        ConversationStage as EnterpriseConversationStage,
        CustomerType,
        Sentiment,
        Urgency as EnterpriseUrgency,
        IntentType,
        ResponseTone,
        PromptTemplate,
    )
    ENTERPRISE_MODELS_AVAILABLE = True
except ImportError:
    ENTERPRISE_MODELS_AVAILABLE = False

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

if ENTERPRISE_MODELS_AVAILABLE:
    __all__.extend([
        "EnterpriseIntelligenceResult",
        "ConversationAnalysis",
        "IntentDefinition",
        "EntityExtraction",
        "SearchPlan",
        "EnterpriseRetrievalStrategy",
        "BusinessReasoning",
        "ResponseStrategy",
        "EnterpriseConversationStage",
        "CustomerType",
        "Sentiment",
        "EnterpriseUrgency",
        "IntentType",
        "ResponseTone",
        "PromptTemplate",
    ])
