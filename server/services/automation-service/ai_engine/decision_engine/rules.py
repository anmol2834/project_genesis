"""
Decision Engine — Rules
========================
Deterministic rule set evaluated by the finalizer.

Rules are evaluated in strict priority order. First match wins.
Each rule maps a combination of pipeline signals to a FinalAction.

Layer order:
  RULE_1xx — Policy hard exits (highest priority)
  RULE_2xx — LLM output checks
  RULE_3xx — Confidence threshold checks
  RULE_4xx — Validation failure checks
  RULE_5xx — Consistency checks (intent vs reply)
  RULE_6xx — Safe mode handling
  RULE_9xx — Default allow

Design principles:
  - NEVER send reply if validation failed.
  - NEVER trust LLM blindly — always check status + content.
  - Policy engine decisions are final for REJECT/SKIP/HUMAN_REVIEW.
  - Confidence thresholds are secondary to policy.
  - Consistency check is advisory — low score downgrades, not blocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .schema import FinalAction
from ..policy_engine.rules import PolicyAction
from ..confidence_engine.schema import ConfidenceLevel

# Thresholds
CONFIDENCE_HUMAN_REVIEW_BELOW = 0.60
CONFIDENCE_SAFE_MODE_BELOW    = 0.85
CONSISTENCY_REJECT_BELOW      = 0.20   # Very low → likely hallucinated reply
CONSISTENCY_DOWNGRADE_BELOW   = 0.40   # Low → downgrade to human_review


@dataclass
class DecisionRule:
    """A single evaluatable decision rule."""
    rule_id:     str
    description: str
    priority:    int
    action:      FinalAction
    reason_template: str


# ── Rule definitions ──────────────────────────────────────────────────────────

RULE_101 = DecisionRule(
    rule_id="DR_101",
    description="Policy REJECT — block unconditionally.",
    priority=101,
    action=FinalAction.REJECT,
    reason_template="Policy rejected: {policy_reason}",
)

RULE_102 = DecisionRule(
    rule_id="DR_102",
    description="Policy HUMAN_REVIEW — escalate unconditionally.",
    priority=102,
    action=FinalAction.HUMAN_REVIEW,
    reason_template="Human review required: {policy_reason}",
)

RULE_103 = DecisionRule(
    rule_id="DR_103",
    description="Policy SKIP — no response needed.",
    priority=103,
    action=FinalAction.SKIP,
    reason_template="Skipped: {policy_reason}",
)

RULE_201 = DecisionRule(
    rule_id="DR_201",
    description="LLM returned no_response status.",
    priority=201,
    action=FinalAction.SKIP,
    reason_template="LLM returned no_response: insufficient context or low confidence.",
)

RULE_202 = DecisionRule(
    rule_id="DR_202",
    description="LLM reply is empty or whitespace-only.",
    priority=202,
    action=FinalAction.SKIP,
    reason_template="LLM produced empty reply.",
)

RULE_301 = DecisionRule(
    rule_id="DR_301",
    description="Final confidence below human_review threshold.",
    priority=301,
    action=FinalAction.HUMAN_REVIEW,
    reason_template="Confidence too low ({confidence:.2f} < {threshold:.2f}) — routing to human.",
)

RULE_401 = DecisionRule(
    rule_id="DR_401",
    description="Response validation failed (PII, hallucination, policy violation).",
    priority=401,
    action=FinalAction.SKIP,
    reason_template="Validation failed: {reasons}",
)

RULE_501 = DecisionRule(
    rule_id="DR_501",
    description="Intent-reply consistency critically low — likely hallucinated.",
    priority=501,
    action=FinalAction.HUMAN_REVIEW,
    reason_template="Reply inconsistent with intent (score={score:.2f}) — routing to human.",
)

RULE_601 = DecisionRule(
    rule_id="DR_601",
    description="Safe mode — allow reply with constrained output.",
    priority=601,
    action=FinalAction.SEND_REPLY,
    reason_template="Safe mode reply approved (confidence={confidence:.2f}).",
)

RULE_901 = DecisionRule(
    rule_id="DR_901",
    description="Default allow — all checks passed.",
    priority=901,
    action=FinalAction.SEND_REPLY,
    reason_template="Valid response approved (confidence={confidence:.2f}).",
)
