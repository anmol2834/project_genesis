"""
Intent Engine — Internal Schema
================================
Internal data structures used within the Intent Engine layer.
Public output contract lives in schemas/intent_schema.py (IntentResult).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..schemas.intent_schema import (
    IntentType, SubIntent, SentimentType, LanguageType, RiskFlag
)


# ── Structured risk flags (internal) ─────────────────────────────────────────

class RiskFlags:
    """
    Structured boolean risk flags used internally.
    Converted to List[RiskFlag] before building IntentResult.
    """
    __slots__ = (
        "contains_links", "contains_spam_words", "contains_abuse",
        "contains_unsubscribe", "contains_legal_language",
        "contains_pii", "contains_threat", "high_urgency",
    )

    def __init__(self) -> None:
        self.contains_links:          bool = False
        self.contains_spam_words:     bool = False
        self.contains_abuse:          bool = False
        self.contains_unsubscribe:    bool = False
        self.contains_legal_language: bool = False
        self.contains_pii:            bool = False
        self.contains_threat:         bool = False
        self.high_urgency:            bool = False

    def to_risk_flag_list(self) -> List[RiskFlag]:
        flags: List[RiskFlag] = []
        if self.contains_links:          flags.append(RiskFlag.CONTAINS_LINKS)
        if self.contains_legal_language: flags.append(RiskFlag.LEGAL_LANGUAGE)
        if self.contains_abuse:          flags.append(RiskFlag.ABUSE_PATTERN)
        if self.contains_threat:         flags.append(RiskFlag.THREAT)
        if self.contains_pii:            flags.append(RiskFlag.SENSITIVE_DATA_PII)
        if self.contains_spam_words:     flags.append(RiskFlag.SPAM_PATTERN)
        if self.contains_unsubscribe:    flags.append(RiskFlag.UNSUBSCRIBE_REQUEST)
        if self.high_urgency:            flags.append(RiskFlag.HIGH_URGENCY)
        if not flags:                    flags.append(RiskFlag.NONE)
        return flags

    def to_dict(self) -> Dict[str, bool]:
        return {s: getattr(self, s) for s in self.__slots__}


# ── Signals from each classification layer ────────────────────────────────────

@dataclass
class RuleSignal:
    """Output of the rule engine for a single message."""
    intent_hint:      Optional[IntentType]
    sub_intent_hint:  Optional[SubIntent]
    sentiment_hint:   Optional[SentimentType]
    language_type:    LanguageType
    risk_flags:       RiskFlags
    rule_score:       float                    # Confidence contribution [0, 1]
    matched_patterns: List[str] = field(default_factory=list)


@dataclass
class ModelSignal:
    """Output of the zero-shot NLI classifier (DistilRoBERTa)."""
    intent:      IntentType
    model_score: float                         # Top label score [0, 1]
    all_scores:  Dict[str, float] = field(default_factory=dict)


@dataclass
class SemanticSignal:
    """Output of the MiniLM semantic similarity pass."""
    best_intent:      IntentType
    similarity_score: float                    # Cosine similarity to best anchor [0, 1]
    all_similarities: Dict[str, float] = field(default_factory=dict)


@dataclass
class FusedSignals:
    """All three signals before final decision."""
    model:            ModelSignal
    semantic:         SemanticSignal
    rule:             RuleSignal
    fused_confidence: float = 0.0             # model*0.5 + semantic*0.3 + rule*0.2


# ── Context object passed between internal methods ────────────────────────────

@dataclass
class IntentEngineContext:
    """
    All data the Intent Engine needs to classify a message.
    Built from PreprocessedInput by the classifier.
    """
    clean_content:                str
    subject:                      str
    conversation_history_snippet: str   # Last 3 incoming messages as plain text
    existing_intent:              Optional[str]
    combined_text:                str = ""   # subject + clean_content joined

    def __post_init__(self) -> None:
        parts = [p.strip() for p in [self.subject, self.clean_content] if p.strip()]
        self.combined_text = " ".join(parts)
