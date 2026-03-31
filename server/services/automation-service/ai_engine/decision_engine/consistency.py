"""
Decision Engine — Consistency Checker
=======================================
Checks whether the LLM reply is semantically consistent with the classified intent.

This is the "intent vs reply" check — it catches cases where the LLM:
  - Responded to a different topic than the incoming message
  - Generated a generic reply that ignores the actual intent
  - Hallucinated a response unrelated to the context

Method:
  1. Embed the reply using the shared MiniLM singleton.
  2. Embed a reference sentence for the classified intent.
  3. Compute cosine similarity.
  4. Return ConsistencyResult with score and pass/fail.

Thresholds (from rules.py):
  score < 0.20 → critically inconsistent → HUMAN_REVIEW
  score < 0.40 → low consistency → downgrade confidence
  score >= 0.40 → acceptable

Design notes:
  - Uses the shared MiniLM singleton — no new model.
  - Runs in thread pool (CPU-bound embedding).
  - Gracefully degrades: if embedding fails, returns neutral score (0.60).
  - Does NOT block on low score alone — combined with other signals.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict

from ..schemas.intent_schema import IntentType
from .rules import CONSISTENCY_REJECT_BELOW, CONSISTENCY_DOWNGRADE_BELOW

logger = logging.getLogger(__name__)

# Reference sentences for each intent — what a good reply to this intent looks like
_INTENT_REPLY_ANCHORS: Dict[str, str] = {
    IntentType.QUESTION.value:        "Thank you for your question. Here is the information you requested.",
    IntentType.INTEREST.value:        "Thank you for your interest. I would be happy to tell you more about our offering.",
    IntentType.NOT_INTERESTED.value:  "Thank you for letting us know. We respect your decision and will not contact you further.",
    IntentType.NEGOTIATION.value:     "Thank you for discussing terms with us. Let me share what options we have available.",
    IntentType.OBJECTION.value:       "I understand your concern. Let me address that and provide some clarity.",
    IntentType.REPLY.value:           "Thank you for getting back to us. We appreciate your response.",
    IntentType.FOLLOW_UP.value:       "Following up on our previous conversation, here is an update.",
    IntentType.SUPPORT_REQUEST.value: "Thank you for reaching out. I am here to help you resolve this issue.",
    IntentType.COMPLAINT.value:       "I sincerely apologize for the inconvenience. Let me help you resolve this.",
    IntentType.SPAM.value:            "",   # Should not reach here
    IntentType.PROMO.value:           "",
    IntentType.ABUSE.value:           "I understand you are frustrated. Let me help address your concern calmly.",
    IntentType.UNSUBSCRIBE.value:     "",
    IntentType.OUT_OF_OFFICE.value:   "",
    IntentType.UNKNOWN.value:         "Thank you for your message. Let me look into this for you.",
}

_NEUTRAL_SCORE = 0.60   # Returned when embedding fails


@dataclass
class ConsistencyResult:
    """Output of the consistency check."""
    score:            float   # Cosine similarity [0, 1]
    passed:           bool    # True when score >= CONSISTENCY_DOWNGRADE_BELOW
    critically_low:   bool    # True when score < CONSISTENCY_REJECT_BELOW
    intent_used:      str
    anchor_used:      str


async def check_consistency(
    reply: str,
    intent: str,
) -> ConsistencyResult:
    """
    Check semantic consistency between the LLM reply and the classified intent.

    Args:
        reply:  The sanitized LLM reply text.
        intent: The classified intent value (e.g. "question", "complaint").

    Returns:
        ConsistencyResult with score and pass/fail flags.
    """
    anchor = _INTENT_REPLY_ANCHORS.get(intent, "")

    # Intents that should never reach this check
    if not anchor or not reply.strip():
        return ConsistencyResult(
            score=_NEUTRAL_SCORE,
            passed=True,
            critically_low=False,
            intent_used=intent,
            anchor_used=anchor,
        )

    try:
        loop = asyncio.get_event_loop()
        from ..intent_engine.utils import embed, cosine_similarity

        reply_vec  = await loop.run_in_executor(None, lambda: embed(reply[:500]))
        anchor_vec = await loop.run_in_executor(None, lambda: embed(anchor))
        score = cosine_similarity(reply_vec, anchor_vec)

    except Exception as exc:
        logger.warning("Consistency check embedding failed: %s — using neutral score", exc)
        score = _NEUTRAL_SCORE

    return ConsistencyResult(
        score=round(score, 4),
        passed=score >= CONSISTENCY_DOWNGRADE_BELOW,
        critically_low=score < CONSISTENCY_REJECT_BELOW,
        intent_used=intent,
        anchor_used=anchor,
    )
