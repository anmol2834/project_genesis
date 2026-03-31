"""
Intent Schema
=============
Public Pydantic contract for the output of the Intent Engine layer.
Consumed by Confidence Engine, Policy Engine, and audit logging.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class IntentType(str, Enum):
    """Primary intent categories — aligned with real-world email patterns."""
    # Engagement / sales funnel
    QUESTION        = "question"
    INTEREST        = "interest"
    NOT_INTERESTED  = "not_interested"
    NEGOTIATION     = "negotiation"
    OBJECTION       = "objection"
    # Conversation
    REPLY           = "reply"
    FOLLOW_UP       = "follow_up"
    # Support / complaints
    SUPPORT_REQUEST = "support_request"
    COMPLAINT       = "complaint"
    # Noise / risk
    SPAM            = "spam"
    PROMO           = "promo"
    ABUSE           = "abuse"
    UNSUBSCRIBE     = "unsubscribe"
    OUT_OF_OFFICE   = "out_of_office"
    # Catch-all
    UNKNOWN         = "unknown"


class SubIntent(str, Enum):
    """Granular sub-classification within a primary intent."""
    PRICING          = "pricing"
    FEATURES         = "features"
    REFUND           = "refund"
    TRUST            = "trust"
    COMPARISON       = "comparison"
    FOLLOW_UP        = "followup"
    MEETING          = "meeting"
    DEMO_REQUEST     = "demo_request"
    UNSUBSCRIBE      = "unsubscribe"
    CAREER           = "career"
    CASUAL_CHAT      = "casual_chat"
    TECHNICAL_ISSUE  = "technical_issue"
    ACCOUNT_ISSUE    = "account_issue"
    LEGAL_THREAT     = "legal_threat"
    ESCALATION       = "escalation"
    GENERAL_QUESTION = "general_question"
    NONE             = "none"


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL  = "neutral"
    NEGATIVE = "negative"
    ANGRY    = "angry"
    ABUSIVE  = "abusive"
    MIXED    = "mixed"


class LanguageType(str, Enum):
    FORMAL   = "formal"
    INFORMAL = "informal"
    SLANG    = "slang"
    MIXED    = "mixed"


class RiskFlag(str, Enum):
    """Flags that may trigger policy restrictions or human review."""
    LEGAL_LANGUAGE      = "legal_language"
    PROFANITY           = "profanity"
    THREAT              = "threat"
    SENSITIVE_DATA_PII  = "sensitive_data_pii"
    SPAM_PATTERN        = "spam_pattern"
    ABUSE_PATTERN       = "abuse_pattern"
    UNSUBSCRIBE_REQUEST = "unsubscribe_request"
    HIGH_URGENCY        = "high_urgency"
    CONTAINS_LINKS      = "contains_links"
    NONE                = "none"


class IntentResult(BaseModel):
    """
    Output of the Intent Engine.
    Consumed by Confidence Engine and Policy Engine.
    """
    intent: IntentType
    sub_intent: SubIntent = SubIntent.NONE
    sentiment: SentimentType
    language_type: LanguageType = LanguageType.INFORMAL
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    secondary_intents: List[IntentType] = Field(
        default_factory=list,
        description="Additional intents for mixed-intent messages"
    )
    reasoning: Optional[str] = Field(
        None,
        description="Audit trail — explains classification decision"
    )

    @field_validator("risk_flags", mode="before")
    @classmethod
    def deduplicate_flags(cls, v: List) -> List:
        return list(dict.fromkeys(v))
