"""
Policy Engine — Evaluator
==========================
Public entry point for the Policy Engine layer.

Wires together:
  - DecisionTree (layered rule evaluation)
  - PolicyDecision (output schema)

The evaluator is the only class the orchestrator interacts with.
All decision logic lives in decision_tree.py.

Orchestrator call signature (unchanged):
  await evaluator.evaluate(intent_result, confidence_score, account_metadata)

Extended signature (with message text for semantic rescue):
  await evaluator.evaluate(intent_result, confidence_score, account_metadata, message_text)
"""
from __future__ import annotations

import logging
from typing import List, Optional

from ..schemas.intent_schema import IntentResult
from ..confidence_engine.schema import ConfidenceScore
from ..schemas.ai_input import AccountMetadata
from .rules import PolicyAction, PolicyRule, DEFAULT_RULES
from .schema import PolicyDecision
from .decision_tree import DecisionTree

logger = logging.getLogger(__name__)


class PolicyEvaluator:
    """
    Stateless policy evaluator.
    Delegates all decision logic to DecisionTree.
    Injected rule set enables per-user overrides and A/B testing.
    """

    def __init__(self, rules: Optional[List[PolicyRule]] = None) -> None:
        self._tree = DecisionTree(rules=rules)

    async def evaluate(
        self,
        intent_result: IntentResult,
        confidence_score: ConfidenceScore,
        account_metadata: AccountMetadata,
        message_text: str = "",
    ) -> PolicyDecision:
        """
        Evaluate the full policy decision tree and return a PolicyDecision.

        Args:
            intent_result:     Output from Intent Engine.
            confidence_score:  Output from Confidence Engine.
            account_metadata:  Account-level metadata (automation flag, limits).
            message_text:      Raw incoming message text for semantic rescue.
                               Optional — falls back to no semantic check when empty.

        Returns:
            PolicyDecision with action, reason, constraints, and layer trace.
        """
        decision = await self._tree.evaluate(
            intent_result=intent_result,
            confidence_score=confidence_score,
            account_metadata=account_metadata,
            message_text=message_text,
        )

        logger.info(
            "Policy decision",
            extra={
                "action":      decision.action.value,
                "rule":        decision.matched_rule_id,
                "layer":       decision.layer_trace,
                "reason":      decision.reason,
                "intent":      intent_result.intent.value,
                "confidence":  confidence_score.final_score,
                "safe_mode":   decision.is_safe_mode,
                "human":       decision.requires_human,
            },
        )

        return decision
