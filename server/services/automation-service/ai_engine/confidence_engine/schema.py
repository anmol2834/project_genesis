"""
Confidence Engine — Schema
===========================
Data contracts for the Confidence Engine layer.
Consumed by Policy Engine and Decision Engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class ConfidenceLevel(str, Enum):
    """
    Bucketed confidence level used by Policy Engine for routing decisions.

    HIGH   (>= 0.85) — safe for full AI processing
    MEDIUM (>= 0.60) — use safe_mode: restricted context, minimal response
    LOW    (<  0.60) — do not use AI: route to human or skip
    """
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


@dataclass
class SignalBreakdown:
    """
    Per-signal scores before fusion.
    Stored for audit logging and debugging.
    """
    model:    float   # From IntentResult.confidence (normalised)
    semantic: float   # Cosine similarity to intent anchor cluster
    rule:     float   # Rule-based penalty score
    context:  float   # Conversation context consistency score

    def to_dict(self) -> Dict[str, float]:
        return {
            "model":    round(self.model,    4),
            "semantic": round(self.semantic, 4),
            "rule":     round(self.rule,     4),
            "context":  round(self.context,  4),
        }


@dataclass
class ConfidenceScore:
    """
    Full output of the Confidence Engine.
    Replaces the old ConfidenceScore dataclass in scorer.py.
    """
    final_score:       float            # Fused score, clamped [0, 1]
    confidence_level:  ConfidenceLevel  # HIGH / MEDIUM / LOW bucket
    breakdown:         SignalBreakdown  # Per-signal scores for audit
    is_above_threshold: bool            # True when final_score >= LOW threshold (0.60)
    threshold_used:    float = 0.60

    # Legacy alias — keeps Policy Engine code unchanged
    @property
    def final_score_value(self) -> float:
        return self.final_score
