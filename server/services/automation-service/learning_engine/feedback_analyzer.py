"""
Learning Engine — Feedback Analyzer
=====================================
Classifies user replies as positive / negative / neutral.
Also handles the observation window expiry (pending → ignored).

Outcome classification logic:
  POSITIVE signals → SUCCESS
    - User asks follow-up question (continued engagement)
    - User says thank you / confirms / agrees
    - User provides requested info
  NEGATIVE signals → FAILED
    - User expresses frustration, complaint, correction
    - User says the reply was wrong / unhelpful
    - User asks to speak to a human
  NEUTRAL / no reply → IGNORED

Uses keyword patterns (fast, no ML needed for v1).
Future: replace with a lightweight sentiment classifier.
"""
from __future__ import annotations

import re
import logging
from typing import List

from .schema import FeedbackOutcome, OutcomeClassification

logger = logging.getLogger(__name__)

# ── Positive signals ──────────────────────────────────────────────────────────
_POSITIVE_RE = re.compile(
    r"\b(thank(s| you)|great|perfect|exactly|helpful|appreciate|"
    r"got it|understood|makes sense|sounds good|yes|sure|"
    r"can you (also|tell|send|share)|what about|how about|"
    r"interested|let.?s (proceed|move|schedule|talk)|"
    r"i.?d like|please (send|share|schedule)|"
    r"when can|how much|what.?s the)\b",
    re.IGNORECASE,
)

# ── Negative signals ──────────────────────────────────────────────────────────
_NEGATIVE_RE = re.compile(
    r"\b(wrong|incorrect|not (right|helpful|what i asked|what i meant)|"
    r"that.?s not|didn.?t answer|missed the point|"
    r"useless|unhelpful|terrible|awful|frustrated|"
    r"speak to (a human|someone|a person|your team)|"
    r"human agent|real person|escalate|"
    r"stop (emailing|contacting)|unsubscribe|"
    r"this is (wrong|bad|not right))\b",
    re.IGNORECASE,
)

# ── Neutral / acknowledgement only ───────────────────────────────────────────
_NEUTRAL_RE = re.compile(
    r"^(ok|okay|noted|received|got it|fine|alright|sure)[.!]?\s*$",
    re.IGNORECASE,
)


def classify_user_reply(user_reply: str) -> OutcomeClassification:
    """
    Classify a user reply as SUCCESS, FAILED, or IGNORED.

    Args:
        user_reply: The raw text of the user's next message.

    Returns:
        OutcomeClassification with outcome and confidence.
    """
    if not user_reply or not user_reply.strip():
        return OutcomeClassification(
            outcome=FeedbackOutcome.IGNORED,
            confidence=1.0,
            signals=["empty_reply"],
        )

    text = user_reply.strip()
    signals: List[str] = []

    pos_matches = _POSITIVE_RE.findall(text)
    neg_matches = _NEGATIVE_RE.findall(text)
    is_neutral  = bool(_NEUTRAL_RE.match(text))

    if pos_matches:
        signals.extend([f"positive:{m}" for m in pos_matches[:3]])
    if neg_matches:
        signals.extend([f"negative:{m}" for m in neg_matches[:3]])

    # Decision logic
    if neg_matches and not pos_matches:
        return OutcomeClassification(
            outcome=FeedbackOutcome.FAILED,
            confidence=min(0.90, 0.60 + len(neg_matches) * 0.10),
            signals=signals,
        )

    if pos_matches and not neg_matches:
        return OutcomeClassification(
            outcome=FeedbackOutcome.SUCCESS,
            confidence=min(0.90, 0.65 + len(pos_matches) * 0.08),
            signals=signals,
        )

    if pos_matches and neg_matches:
        # Mixed — lean toward failed (safety-first)
        return OutcomeClassification(
            outcome=FeedbackOutcome.FAILED,
            confidence=0.55,
            signals=signals + ["mixed_signals"],
        )

    if is_neutral:
        # Neutral acknowledgement — treat as ignored (no strong signal)
        return OutcomeClassification(
            outcome=FeedbackOutcome.IGNORED,
            confidence=0.70,
            signals=["neutral_ack"],
        )

    # No strong signal — treat as success (user continued the conversation)
    return OutcomeClassification(
        outcome=FeedbackOutcome.SUCCESS,
        confidence=0.55,
        signals=["continued_conversation"],
    )


async def expire_pending_logs() -> int:
    """
    Mark all pending feedback logs older than 24h as IGNORED.
    Called by the scheduler every 6 hours.

    Returns:
        Number of logs updated.
    """
    total_updated = 0
    try:
        from shared.database import get_db_session
        from .repository import get_pending_feedback_logs, update_feedback_outcome
        from uuid import UUID

        async with get_db_session() as session:
            pending = await get_pending_feedback_logs(session, older_than_hours=24, limit=500)

        for row in pending:
            conv_id = UUID(str(row["conversation_id"]))
            async with get_db_session() as session:
                updated = await update_feedback_outcome(
                    session, conv_id, FeedbackOutcome.IGNORED, user_reply=None
                )
                total_updated += updated

        if total_updated:
            logger.info("Expired %d pending feedback logs → ignored", total_updated)

    except Exception as exc:
        logger.error("expire_pending_logs failed: %s", exc)

    return total_updated
