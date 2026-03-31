"""
Learning Engine — Feedback Collector
======================================
Hook point: called immediately after the ACRE pipeline produces a final output.

Responsibilities:
  1. Log every pipeline run to ai_feedback_logs with outcome=PENDING.
  2. Provide update_outcome() for when the user's next reply is observed.
  3. Fire-and-forget — never blocks the main pipeline.

Hook location in orchestrator:
  After pipeline.run() returns AIEngineOutput, call:
    asyncio.create_task(collector.log_pipeline_result(ai_input, output, elapsed_ms))

Multi-tenant: every log row is tagged with user_id — strict isolation.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional
from uuid import UUID

from .schema import FeedbackLogCreate, FeedbackOutcome
from .repository import insert_feedback_log, update_feedback_outcome

logger = logging.getLogger(__name__)


class FeedbackCollector:
    """
    Async feedback logger. Stateless — safe to share across requests.
    All DB writes are fire-and-forget (wrapped in asyncio.create_task).
    """

    async def log_pipeline_result(
        self,
        user_id: UUID,
        conversation_id: UUID,
        email_account_id: UUID,
        intent: str,
        sub_intent: str,
        ai_reply: str,
        confidence_score: float,
        final_action: str,
        safe_mode: bool,
        policy_rule_id: str,
        confidence_level: str,
        elapsed_ms: float = 0.0,
    ) -> Optional[UUID]:
        """
        Log a pipeline run to ai_feedback_logs.
        Outcome starts as PENDING — updated later when user replies.

        Returns the new log row UUID, or None on failure.
        Never raises — failures are logged and swallowed.
        """
        data = FeedbackLogCreate(
            user_id=user_id,
            conversation_id=conversation_id,
            email_account_id=email_account_id,
            intent=intent,
            sub_intent=sub_intent,
            ai_reply=ai_reply,
            confidence_score=confidence_score,
            final_action=final_action,
            outcome=FeedbackOutcome.PENDING,
            response_time_seconds=elapsed_ms / 1000.0 if elapsed_ms else None,
            safe_mode=safe_mode,
            policy_rule_id=policy_rule_id,
            confidence_level=confidence_level,
        )

        try:
            from shared.database import get_db_session
            async with get_db_session() as session:
                row_id = await insert_feedback_log(session, data)
                logger.debug(
                    "Feedback log created: %s | intent=%s | action=%s",
                    row_id, intent, final_action,
                )
                return row_id
        except Exception as exc:
            logger.error("Failed to log feedback: %s", exc)
            return None

    async def update_outcome(
        self,
        conversation_id: UUID,
        outcome: FeedbackOutcome,
        user_reply: Optional[str] = None,
    ) -> bool:
        """
        Update the outcome of a pending feedback log.
        Called when the next incoming message in the thread is observed.

        Args:
            conversation_id: The conversation being tracked.
            outcome:         SUCCESS / FAILED / IGNORED.
            user_reply:      The user's reply text (for analysis).

        Returns:
            True if at least one row was updated.
        """
        try:
            from shared.database import get_db_session
            async with get_db_session() as session:
                rows = await update_feedback_outcome(
                    session, conversation_id, outcome, user_reply
                )
                logger.debug(
                    "Feedback outcome updated: conv=%s outcome=%s rows=%d",
                    conversation_id, outcome.value, rows,
                )
                return rows > 0
        except Exception as exc:
            logger.error("Failed to update feedback outcome: %s", exc)
            return False


# ── Module-level singleton ────────────────────────────────────────────────────
_collector: Optional[FeedbackCollector] = None


def get_feedback_collector() -> FeedbackCollector:
    """Return the singleton FeedbackCollector."""
    global _collector
    if _collector is None:
        _collector = FeedbackCollector()
    return _collector
