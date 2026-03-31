"""
Decision Engine — Final Validator
===================================
Last safety gate before a reply is approved for sending.

Checks performed here are DIFFERENT from validators/response_validator.py:
  - response_validator.py checks the raw LLM output (PII, hallucination, length)
  - This validator checks the DECISION CONTEXT (intent mismatch, spam override, etc.)

Checks:
  1. Spam override — if intent is SPAM/PROMO but somehow reached this layer, block it.
  2. Intent mismatch — if LLM's intent_handled differs significantly from classified intent.
  3. Confidence floor — if final confidence is below the absolute floor, block.
  4. Safe mode compliance — if safe mode is active, verify reply respects constraints.

Returns:
  FinalValidationResult with passed=True if all checks pass.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from ..schemas.intent_schema import IntentResult, IntentType
from ..confidence_engine.schema import ConfidenceScore, ConfidenceLevel
from ..policy_engine.schema import PolicyDecision
from ..validators.json_validator import ParsedLLMOutput

logger = logging.getLogger(__name__)

# Absolute confidence floor — below this, route to human review (never silently drop)
ABSOLUTE_CONFIDENCE_FLOOR = 0.25   # Lowered — policy engine handles 0.30-0.60 range

# Intents that must NEVER produce a reply (final safety net)
_BLOCKED_INTENTS = {IntentType.SPAM, IntentType.PROMO, IntentType.UNSUBSCRIBE, IntentType.OUT_OF_OFFICE}

# Intent groups for mismatch detection (intents within a group are compatible)
_INTENT_GROUPS = [
    {IntentType.QUESTION, IntentType.INTEREST, IntentType.NEGOTIATION, IntentType.FOLLOW_UP},
    {IntentType.COMPLAINT, IntentType.SUPPORT_REQUEST, IntentType.OBJECTION},
    {IntentType.REPLY, IntentType.NOT_INTERESTED},
    {IntentType.SPAM, IntentType.PROMO, IntentType.ABUSE},
]


@dataclass
class FinalValidationResult:
    """Output of the final validator."""
    passed:   bool
    reasons:  List[str] = field(default_factory=list)


def run_final_validation(
    intent_result: IntentResult,
    confidence_score: ConfidenceScore,
    policy_decision: PolicyDecision,
    parsed_output: ParsedLLMOutput,
) -> FinalValidationResult:
    """
    Run all final validation checks synchronously.

    Args:
        intent_result:    Output from Intent Engine.
        confidence_score: Output from Confidence Engine.
        policy_decision:  Output from Policy Engine.
        parsed_output:    Parsed and schema-validated LLM output.

    Returns:
        FinalValidationResult with passed=True if all checks pass.
    """
    reasons: List[str] = []

    # ── Check 1: Spam/noise override ──────────────────────────────────────
    if intent_result.intent in _BLOCKED_INTENTS:
        reasons.append(
            f"Final safety block: intent '{intent_result.intent.value}' must not produce a reply."
        )

    # ── Check 2: Absolute confidence floor ───────────────────────────────
    if confidence_score.final_score < ABSOLUTE_CONFIDENCE_FLOOR:
        reasons.append(
            f"Confidence below absolute floor "
            f"({confidence_score.final_score:.2f} < {ABSOLUTE_CONFIDENCE_FLOOR})."
        )

    # ── Check 3: Intent mismatch between classifier and LLM ──────────────
    classified = intent_result.intent.value
    llm_handled = parsed_output.intent_handled.lower().strip()

    if llm_handled and llm_handled != classified:
        mismatch = _is_significant_mismatch(classified, llm_handled)
        if mismatch:
            logger.warning(
                "Intent mismatch: classified=%s, llm_handled=%s",
                classified, llm_handled,
            )
            # Mismatch is a warning, not a hard block — log and continue
            # (The consistency checker handles the semantic check)

    # ── Check 4: Safe mode compliance ────────────────────────────────────
    if policy_decision.is_safe_mode:
        reply = parsed_output.reply
        constraints = policy_decision.constraints
        # Verify reply doesn't exceed safe mode token budget (rough check)
        estimated_tokens = len(reply) // 4
        if estimated_tokens > constraints.max_tokens * 1.5:
            reasons.append(
                f"Safe mode reply too long: ~{estimated_tokens} tokens "
                f"(limit={constraints.max_tokens})."
            )

    return FinalValidationResult(
        passed=len(reasons) == 0,
        reasons=reasons,
    )


def _is_significant_mismatch(classified: str, llm_handled: str) -> bool:
    """
    Returns True if classified and llm_handled intents are in different groups
    AND the mismatch is significant (not just a synonym).
    """
    classified_group = _find_group(classified)
    llm_group        = _find_group(llm_handled)

    # If either is unknown or they're in the same group → not a significant mismatch
    if classified_group is None or llm_group is None:
        return False
    return classified_group != llm_group


def _find_group(intent_val: str) -> int | None:
    """Return the group index for an intent value, or None if not found."""
    for i, group in enumerate(_INTENT_GROUPS):
        if any(m.value == intent_val for m in group):
            return i
    return None
