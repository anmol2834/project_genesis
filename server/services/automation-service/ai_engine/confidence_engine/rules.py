"""
Confidence Engine — Rule-Based Scorer
=======================================
Computes a rule_score in [0, 1] by applying penalties to a baseline of 1.0.

Penalty design principles:
  - NEVER drop score to 0 from a single signal.
  - Mixed intent (unsubscribe + pricing) gets a mild penalty, not a hard drop.
  - Abuse gets a small penalty — it is still a valid interaction.
  - Spam pattern requires multiple signals before a large penalty fires.
  - Short messages ("Hi") get a mild penalty for low information, not rejection.

Input:  IntentResult + raw message text + message length
Output: float in [0, 1]
"""
from __future__ import annotations

import re
from typing import List

from ..schemas.intent_schema import IntentResult, RiskFlag, IntentType, SentimentType

# ── Link density detector ─────────────────────────────────────────────────────
_LINK_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

# Thresholds
_SHORT_MSG_CHARS  = 20    # Below this → low information penalty
_LONG_PROMO_CHARS = 800   # Above this with spam signals → promo penalty
_HIGH_LINK_COUNT  = 3     # More than this → link density penalty


def compute_rule_score(
    intent_result: IntentResult,
    message_text: str,
) -> float:
    """
    Compute rule-based confidence score.

    Args:
        intent_result: Output from Intent Engine.
        message_text:  Raw (or lightly cleaned) incoming message text.

    Returns:
        float in [0.0, 1.0]
    """
    score = 1.0
    flags = set(intent_result.risk_flags)
    text_len = len(message_text.strip())
    link_count = len(_LINK_RE.findall(message_text))

    # ── Penalty: spam pattern ─────────────────────────────────────────────
    # Only penalise heavily when BOTH spam_pattern flag AND intent is SPAM/PROMO
    if RiskFlag.SPAM_PATTERN in flags:
        if intent_result.intent in (IntentType.SPAM, IntentType.PROMO):
            score -= 0.35   # Strong penalty — confirmed spam
        else:
            score -= 0.10   # Weak penalty — spam word in genuine message

    # ── Penalty: link density ─────────────────────────────────────────────
    if link_count > _HIGH_LINK_COUNT:
        score -= 0.20
    elif RiskFlag.CONTAINS_LINKS in flags:
        score -= 0.05   # Single link is normal, mild penalty only

    # ── Penalty: abuse language ───────────────────────────────────────────
    # Abuse is a valid interaction — do NOT drop confidence drastically
    if RiskFlag.ABUSE_PATTERN in flags:
        score -= 0.10

    # ── Penalty: legal / threat language ─────────────────────────────────
    if RiskFlag.LEGAL_LANGUAGE in flags or RiskFlag.THREAT in flags:
        score -= 0.15

    # ── Penalty: PII detected ─────────────────────────────────────────────
    if RiskFlag.SENSITIVE_DATA_PII in flags:
        score -= 0.10

    # ── Penalty: unsubscribe — mild, not a hard drop ──────────────────────
    # Mixed intent (unsubscribe + pricing) should NOT lose much confidence
    if RiskFlag.UNSUBSCRIBE_REQUEST in flags:
        if intent_result.intent == IntentType.UNSUBSCRIBE:
            score -= 0.15   # Pure unsubscribe — lower confidence for AI reply
        else:
            score -= 0.05   # Mixed intent — barely penalise

    # ── Penalty: very short message ───────────────────────────────────────
    # "Hi" is valid but low-information — medium confidence, not low
    if text_len < _SHORT_MSG_CHARS:
        score -= 0.10

    # ── Penalty: long promotional email ──────────────────────────────────
    # Long text + spam signals + unsubscribe footer = high-confidence promo
    if (
        text_len > _LONG_PROMO_CHARS
        and RiskFlag.SPAM_PATTERN in flags
        and RiskFlag.UNSUBSCRIBE_REQUEST in flags
    ):
        score -= 0.20   # Additional penalty on top of spam penalty

    # ── Penalty: multiple conflicting secondary intents ───────────────────
    secondary_count = len(intent_result.secondary_intents)
    if secondary_count >= 3:
        score -= 0.10
    elif secondary_count == 2:
        score -= 0.05

    # ── Boost: high-clarity intents ───────────────────────────────────────
    # Clear, unambiguous intents deserve a small confidence boost
    if intent_result.intent in (
        IntentType.QUESTION,
        IntentType.INTEREST,
        IntentType.SUPPORT_REQUEST,
        IntentType.OUT_OF_OFFICE,
    ) and not flags - {RiskFlag.NONE, RiskFlag.CONTAINS_LINKS}:
        score += 0.05

    return round(max(0.0, min(1.0, score)), 4)
