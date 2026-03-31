"""
Policy Engine — Decision Tree
==============================
Layered rule evaluation engine.

Execution order:
  LAYER 1 — HARD BLOCKS       (account-level, always checked first)
  LAYER 2 — SAFETY GATES      (risk flags: legal, threat, PII, abuse)
  LAYER 3 — NOISE FILTERING   (spam, promo, OOO, unsubscribe)
             └─ Semantic rescue: if message is business-relevant despite noise
                signals, downgrade REJECT → SAFE_MODE
  LAYER 4 — BUSINESS LOGIC    (intent-based routing)
  LAYER 5 — CONFIDENCE OVERRIDE (threshold-based fallback)
  LAYER 6 — DEFAULT ALLOW

Key design decisions:
  - NEVER reject based on a single keyword.
  - Spam requires confidence > 0.90 (enforced in RULE_020).
  - Mixed intent (secondary_intents non-empty) → SAFE_MODE, not REJECT.
  - Abuse → SAFE_MODE (calm response), not REJECT.
  - Semantic rescue prevents false rejection of genuine leads.
  - All decisions include a reason string for full explainability.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from ..schemas.intent_schema import IntentResult, IntentType, RiskFlag, SentimentType
from ..confidence_engine.schema import ConfidenceScore, ConfidenceLevel
from ..schemas.ai_input import AccountMetadata
from .rules import PolicyAction, PolicyRule, RuleLayer, DEFAULT_RULES
from .schema import (
    PolicyDecision, PromptConstraints,
    CONSTRAINTS_FULL, CONSTRAINTS_SAFE, CONSTRAINTS_MINIMAL, CONSTRAINTS_ABUSE,
)

logger = logging.getLogger(__name__)


class DecisionTree:
    """
    Stateless layered rule evaluator.
    Evaluates rules in priority order; first match wins.
    Includes semantic rescue for mixed-intent messages.
    """

    def __init__(self, rules: Optional[List[PolicyRule]] = None) -> None:
        self._rules: List[PolicyRule] = sorted(
            rules or DEFAULT_RULES,
            key=lambda r: r.priority,
        )

    async def evaluate(
        self,
        intent_result: IntentResult,
        confidence_score: ConfidenceScore,
        account_metadata: AccountMetadata,
        message_text: str = "",
    ) -> PolicyDecision:
        """
        Run the full layered decision tree.

        Args:
            intent_result:     Output from Intent Engine.
            confidence_score:  Output from Confidence Engine.
            account_metadata:  Account-level metadata.
            message_text:      Raw incoming message text (for semantic rescue).

        Returns:
            PolicyDecision with action, reason, constraints, and layer trace.
        """
        flags = set(intent_result.risk_flags)
        final_conf = confidence_score.final_score
        conf_level = confidence_score.confidence_level

        # ── LAYER 1: HARD BLOCKS ──────────────────────────────────────────
        hard_decision = self._check_hard_blocks(account_metadata)
        if hard_decision:
            return hard_decision

        # ── LAYER 2: SAFETY GATES ─────────────────────────────────────────
        safety_decision = self._check_safety_gates(intent_result, flags)
        if safety_decision:
            return safety_decision

        # ── LAYER 3: NOISE FILTERING ──────────────────────────────────────
        # Semantic rescue: check if message is business-relevant before rejecting
        noise_decision = await self._check_noise_with_rescue(
            intent_result, flags, final_conf, message_text
        )
        if noise_decision:
            return noise_decision

        # ── LAYER 4: BUSINESS LOGIC ───────────────────────────────────────
        business_decision = self._check_business_logic(intent_result, final_conf)
        if business_decision:
            return business_decision

        # ── LAYER 5: CONFIDENCE OVERRIDE ─────────────────────────────────
        confidence_decision = self._check_confidence_override(final_conf, conf_level)
        if confidence_decision:
            return confidence_decision

        # ── LAYER 6: DEFAULT ALLOW ────────────────────────────────────────
        return PolicyDecision(
            action=PolicyAction.ALLOW,
            matched_rule_id="RULE_099",
            reason="Default allow — no blocking rules matched.",
            constraints=CONSTRAINTS_FULL,
            layer_trace=RuleLayer.DEFAULT.value,
        )

    # ── Layer 1: Hard blocks ──────────────────────────────────────────────────

    def _check_hard_blocks(
        self,
        account_metadata: AccountMetadata,
    ) -> Optional[PolicyDecision]:
        """Account-level hard blocks. Always checked first."""

        if not account_metadata.automation_enabled:
            return PolicyDecision(
                action=PolicyAction.REJECT,
                matched_rule_id="RULE_001",
                reason="Automation is disabled for this account.",
                constraints=CONSTRAINTS_MINIMAL,
                layer_trace=RuleLayer.HARD.value,
            )

        if account_metadata.daily_sent_count >= account_metadata.daily_send_limit:
            return PolicyDecision(
                action=PolicyAction.REJECT,
                matched_rule_id="RULE_002",
                reason=(
                    f"Daily send limit reached "
                    f"({account_metadata.daily_sent_count}/{account_metadata.daily_send_limit})."
                ),
                constraints=CONSTRAINTS_MINIMAL,
                layer_trace=RuleLayer.HARD.value,
            )

        return None

    # ── Layer 2: Safety gates ─────────────────────────────────────────────────

    def _check_safety_gates(
        self,
        intent_result: IntentResult,
        flags: set,
    ) -> Optional[PolicyDecision]:
        """Risk-based safety gates. Checked before any business logic."""

        if RiskFlag.LEGAL_LANGUAGE in flags or RiskFlag.THREAT in flags:
            flag_names = [
                f.value for f in [RiskFlag.LEGAL_LANGUAGE, RiskFlag.THREAT]
                if f in flags
            ]
            return PolicyDecision(
                action=PolicyAction.HUMAN_REVIEW,
                matched_rule_id="RULE_010",
                reason=f"Legal or threat language detected: {flag_names}. Escalating to human.",
                constraints=CONSTRAINTS_MINIMAL,
                requires_human=True,
                layer_trace=RuleLayer.SAFETY.value,
            )

        if RiskFlag.SENSITIVE_DATA_PII in flags:
            return PolicyDecision(
                action=PolicyAction.SAFE_MODE,
                matched_rule_id="RULE_012",
                reason="PII detected in message. Using safe mode to prevent data exposure.",
                constraints=CONSTRAINTS_SAFE,
                is_safe_mode=True,
                layer_trace=RuleLayer.SAFETY.value,
            )

        # Abuse → safe mode with calm tone, NOT rejection
        if (
            RiskFlag.ABUSE_PATTERN in flags
            or intent_result.sentiment in (SentimentType.ABUSIVE, SentimentType.ANGRY)
        ):
            return PolicyDecision(
                action=PolicyAction.SAFE_MODE,
                matched_rule_id="RULE_013",
                reason="Abusive or angry sentiment detected. Responding with calm professional tone.",
                constraints=CONSTRAINTS_ABUSE,
                is_safe_mode=True,
                layer_trace=RuleLayer.SAFETY.value,
            )

        return None

    # ── Layer 3: Noise filtering with semantic rescue ─────────────────────────

    async def _check_noise_with_rescue(
        self,
        intent_result: IntentResult,
        flags: set,
        final_conf: float,
        message_text: str,
    ) -> Optional[PolicyDecision]:
        """
        Noise filtering with semantic rescue.

        Before rejecting a message as spam/promo/unsubscribe, check if it is
        semantically relevant to a business conversation. If it is, downgrade
        REJECT → SAFE_MODE to avoid false rejection of genuine leads.

        Example: "unsubscribe me but also send pricing" → SAFE_MODE, not REJECT.
        """
        intent = intent_result.intent

        # ── Spam: requires confidence > 0.90 ─────────────────────────────
        if intent == IntentType.SPAM:
            if final_conf > 0.90:
                return PolicyDecision(
                    action=PolicyAction.REJECT,
                    matched_rule_id="RULE_020",
                    reason=f"Confirmed spam (confidence={final_conf:.2f} > 0.90).",
                    constraints=CONSTRAINTS_MINIMAL,
                    layer_trace=RuleLayer.NOISE.value,
                )
            else:
                # Confidence too low to confirm spam — downgrade to safe mode
                return PolicyDecision(
                    action=PolicyAction.SAFE_MODE,
                    matched_rule_id="RULE_020_DOWNGRADE",
                    reason=(
                        f"Possible spam but confidence={final_conf:.2f} < 0.90. "
                        "Using safe mode instead of rejection."
                    ),
                    constraints=CONSTRAINTS_SAFE,
                    is_safe_mode=True,
                    layer_trace=RuleLayer.NOISE.value,
                )

        # ── Promo: check semantic relevance before rejecting ──────────────
        if intent == IntentType.PROMO:
            is_relevant = await self._semantic_rescue(message_text)
            if is_relevant:
                return PolicyDecision(
                    action=PolicyAction.SAFE_MODE,
                    matched_rule_id="RULE_021_RESCUED",
                    reason="Promotional content but semantically relevant to business context. Using safe mode.",
                    constraints=CONSTRAINTS_SAFE,
                    is_safe_mode=True,
                    layer_trace=RuleLayer.NOISE.value,
                )
            return PolicyDecision(
                action=PolicyAction.REJECT,
                matched_rule_id="RULE_021",
                reason="Promotional email not related to active conversation.",
                constraints=CONSTRAINTS_MINIMAL,
                layer_trace=RuleLayer.NOISE.value,
            )

        # ── Unsubscribe: check for mixed intent before rejecting ──────────
        if intent == IntentType.UNSUBSCRIBE:
            # Mixed intent: secondary intents suggest genuine interest
            has_interest_secondary = any(
                si in (IntentType.QUESTION, IntentType.INTEREST, IntentType.NEGOTIATION)
                for si in intent_result.secondary_intents
            )
            if has_interest_secondary:
                return PolicyDecision(
                    action=PolicyAction.SAFE_MODE,
                    matched_rule_id="RULE_022_MIXED",
                    reason=(
                        "Unsubscribe request with interest signals detected. "
                        "Responding carefully to retain potential lead."
                    ),
                    constraints=CONSTRAINTS_SAFE,
                    is_safe_mode=True,
                    layer_trace=RuleLayer.NOISE.value,
                )
            # Also check semantic relevance
            is_relevant = await self._semantic_rescue(message_text)
            if is_relevant:
                return PolicyDecision(
                    action=PolicyAction.SAFE_MODE,
                    matched_rule_id="RULE_022_RESCUED",
                    reason="Unsubscribe with business-relevant content. Using safe mode.",
                    constraints=CONSTRAINTS_SAFE,
                    is_safe_mode=True,
                    layer_trace=RuleLayer.NOISE.value,
                )
            return PolicyDecision(
                action=PolicyAction.REJECT,
                matched_rule_id="RULE_022",
                reason="Pure unsubscribe request. Routing to unsubscribe handler.",
                constraints=CONSTRAINTS_MINIMAL,
                layer_trace=RuleLayer.NOISE.value,
            )

        # ── Out of office: always skip ────────────────────────────────────
        if intent == IntentType.OUT_OF_OFFICE:
            return PolicyDecision(
                action=PolicyAction.SKIP,
                matched_rule_id="RULE_023",
                reason="Out-of-office auto-reply. No response needed.",
                constraints=CONSTRAINTS_MINIMAL,
                layer_trace=RuleLayer.NOISE.value,
            )

        return None

    # ── Layer 4: Business logic ───────────────────────────────────────────────

    def _check_business_logic(
        self,
        intent_result: IntentResult,
        final_conf: float,
    ) -> Optional[PolicyDecision]:
        """Intent-based business routing."""
        intent = intent_result.intent

        # Mixed intent: secondary intents present → safe mode
        if intent_result.secondary_intents:
            secondary_vals = [si.value for si in intent_result.secondary_intents]
            return PolicyDecision(
                action=PolicyAction.SAFE_MODE,
                matched_rule_id="RULE_038",
                reason=f"Mixed intent detected: primary={intent.value}, secondary={secondary_vals}.",
                constraints=CONSTRAINTS_SAFE,
                is_safe_mode=True,
                layer_trace=RuleLayer.BUSINESS.value,
            )

        # High-value lead intents → ALLOW (when confidence sufficient)
        if intent in (IntentType.QUESTION, IntentType.INTEREST, IntentType.NEGOTIATION):
            if final_conf >= 0.60:
                return PolicyDecision(
                    action=PolicyAction.ALLOW,
                    matched_rule_id=f"RULE_03{['0','1','2'][list((IntentType.QUESTION, IntentType.INTEREST, IntentType.NEGOTIATION)).index(intent)]}",
                    reason=f"High-value lead intent: {intent.value} (confidence={final_conf:.2f}).",
                    constraints=CONSTRAINTS_FULL,
                    layer_trace=RuleLayer.BUSINESS.value,
                )

        # Follow-up → ALLOW
        if intent == IntentType.FOLLOW_UP and final_conf >= 0.60:
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_id="RULE_033",
                reason=f"Follow-up message (confidence={final_conf:.2f}).",
                constraints=CONSTRAINTS_FULL,
                layer_trace=RuleLayer.BUSINESS.value,
            )

        # Support request → ALLOW
        if intent == IntentType.SUPPORT_REQUEST and final_conf >= 0.55:
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_id="RULE_036",
                reason=f"Support request (confidence={final_conf:.2f}).",
                constraints=CONSTRAINTS_FULL,
                layer_trace=RuleLayer.BUSINESS.value,
            )

        # Objection → SAFE_MODE
        if intent == IntentType.OBJECTION:
            return PolicyDecision(
                action=PolicyAction.SAFE_MODE,
                matched_rule_id="RULE_034",
                reason="Objection detected. Responding carefully without assumptions.",
                constraints=CONSTRAINTS_SAFE,
                is_safe_mode=True,
                layer_trace=RuleLayer.BUSINESS.value,
            )

        # Complaint → SAFE_MODE
        if intent == IntentType.COMPLAINT:
            return PolicyDecision(
                action=PolicyAction.SAFE_MODE,
                matched_rule_id="RULE_035",
                reason="Complaint detected. Responding calmly without commitments.",
                constraints=CONSTRAINTS_ABUSE,
                is_safe_mode=True,
                layer_trace=RuleLayer.BUSINESS.value,
            )

        # Not interested → SAFE_MODE (acknowledge politely)
        if intent == IntentType.NOT_INTERESTED:
            return PolicyDecision(
                action=PolicyAction.SAFE_MODE,
                matched_rule_id="RULE_039",
                reason="Not-interested signal. Acknowledging politely.",
                constraints=CONSTRAINTS_SAFE,
                is_safe_mode=True,
                layer_trace=RuleLayer.BUSINESS.value,
            )

        # Casual chat / generic reply → SKIP
        if intent == IntentType.REPLY and final_conf >= 0.70:
            return PolicyDecision(
                action=PolicyAction.SKIP,
                matched_rule_id="RULE_037",
                reason="Casual chat or generic reply. No business response needed.",
                constraints=CONSTRAINTS_MINIMAL,
                layer_trace=RuleLayer.BUSINESS.value,
            )

        return None

    # ── Layer 5: Confidence override ──────────────────────────────────────────

    def _check_confidence_override(
        self,
        final_conf: float,
        conf_level: ConfidenceLevel,
    ) -> Optional[PolicyDecision]:
        """Confidence-threshold fallback when no business rule matched."""

        if final_conf < 0.40:
            return PolicyDecision(
                action=PolicyAction.SKIP,
                matched_rule_id="RULE_050",
                reason=f"Very low confidence ({final_conf:.2f}). Classification unreliable.",
                constraints=CONSTRAINTS_MINIMAL,
                layer_trace=RuleLayer.CONFIDENCE.value,
            )

        if conf_level == ConfidenceLevel.LOW:
            return PolicyDecision(
                action=PolicyAction.HUMAN_REVIEW,
                matched_rule_id="RULE_051",
                reason=f"Low confidence ({final_conf:.2f}). Routing to human review.",
                constraints=CONSTRAINTS_MINIMAL,
                requires_human=True,
                layer_trace=RuleLayer.CONFIDENCE.value,
            )

        if conf_level == ConfidenceLevel.MEDIUM:
            return PolicyDecision(
                action=PolicyAction.SAFE_MODE,
                matched_rule_id="RULE_052",
                reason=f"Medium confidence ({final_conf:.2f}). Using safe mode.",
                constraints=CONSTRAINTS_SAFE,
                is_safe_mode=True,
                layer_trace=RuleLayer.CONFIDENCE.value,
            )

        return None

    # ── Semantic rescue helper ────────────────────────────────────────────────

    async def _semantic_rescue(self, message_text: str) -> bool:
        """
        Check if a message flagged as noise is actually business-relevant.
        Returns True if the message should be rescued from rejection.
        """
        if not message_text.strip():
            return False
        try:
            from .semantic import is_business_relevant
            return await is_business_relevant(message_text, threshold=0.55)
        except Exception as exc:
            logger.warning("Semantic rescue failed: %s — defaulting to no rescue", exc)
            return False
