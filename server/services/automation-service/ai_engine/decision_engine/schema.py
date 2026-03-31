"""
Decision Engine — Schema
=========================
Data contracts for the Decision Engine layer.

FinalDecision  — the rich internal decision object (used within this layer)
FinalAction    — the action enum
DecisionTrace  — full audit trail for logging and debugging

Note: The pipeline's public output is still AIEngineOutput (schemas/ai_output.py).
FinalDecision is an internal intermediate that gets mapped to AIEngineOutput
by the finalizer before returning to the orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FinalAction(str, Enum):
    """The four possible final actions the Decision Engine can produce."""
    SEND_REPLY    = "send_reply"    # Valid AI output — dispatch the reply
    SKIP          = "skip"          # No response needed
    HUMAN_REVIEW  = "human_review"  # Escalate to human agent
    REJECT        = "reject"        # Block — spam, unsafe, policy violation


@dataclass
class DecisionTrace:
    """
    Full audit trail for a single pipeline run.
    Stored for debugging, monitoring, and future fine-tuning.
    """
    policy_action:       str
    policy_rule_id:      str
    policy_layer:        str
    llm_status:          str          # "success" | "no_response" | "not_called"
    llm_intent_handled:  str
    llm_confidence:      float
    validation_passed:   bool
    validation_reasons:  List[str]
    consistency_score:   float        # Intent vs reply semantic similarity
    consistency_passed:  bool
    final_action:        str
    final_reason:        str
    confidence_level:    str          # high / medium / low
    safe_mode:           bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_action":      self.policy_action,
            "policy_rule_id":     self.policy_rule_id,
            "policy_layer":       self.policy_layer,
            "llm_status":         self.llm_status,
            "llm_intent_handled": self.llm_intent_handled,
            "llm_confidence":     self.llm_confidence,
            "validation_passed":  self.validation_passed,
            "validation_reasons": self.validation_reasons,
            "consistency_score":  round(self.consistency_score, 4),
            "consistency_passed": self.consistency_passed,
            "final_action":       self.final_action,
            "final_reason":       self.final_reason,
            "confidence_level":   self.confidence_level,
            "safe_mode":          self.safe_mode,
        }


@dataclass
class FinalDecision:
    """
    Internal decision object produced by the Decision Engine.
    Mapped to AIEngineOutput before returning to the orchestrator.
    """
    action:     FinalAction
    reply:      str                    # Empty string when action != SEND_REPLY
    reason:     str
    confidence: float
    trace:      DecisionTrace
    metadata:   Dict[str, Any] = field(default_factory=dict)
