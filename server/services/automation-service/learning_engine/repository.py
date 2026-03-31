"""
Learning Engine — Repository
=============================
All database operations for the feedback + learning system.
Uses raw SQL via SQLAlchemy async sessions — no ORM models needed.

Tables managed:
  ai_feedback_logs      — raw feedback per pipeline run
  ai_learning_insights  — aggregated insights per (user_id, intent)

All queries are parameterised — no string interpolation (SQL injection safe).
All operations are async.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text

from .schema import FeedbackLogCreate, FeedbackOutcome

logger = logging.getLogger(__name__)

# ── DDL — run once at startup ─────────────────────────────────────────────────

CREATE_FEEDBACK_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS ai_feedback_logs (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                UUID NOT NULL,
    conversation_id        UUID NOT NULL,
    email_account_id       UUID NOT NULL,
    intent                 VARCHAR(100) NOT NULL,
    sub_intent             VARCHAR(100) NOT NULL DEFAULT 'none',
    ai_reply               TEXT NOT NULL DEFAULT '',
    user_reply             TEXT,
    confidence_score       FLOAT NOT NULL DEFAULT 0.0,
    final_action           VARCHAR(50) NOT NULL,
    outcome                VARCHAR(20) NOT NULL DEFAULT 'pending',
    response_time_seconds  FLOAT,
    safe_mode              BOOLEAN NOT NULL DEFAULT FALSE,
    policy_rule_id         VARCHAR(50) NOT NULL DEFAULT '',
    confidence_level       VARCHAR(20) NOT NULL DEFAULT 'medium',
    created_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ai_feedback_logs_user_id
    ON ai_feedback_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_ai_feedback_logs_conversation_id
    ON ai_feedback_logs (conversation_id);
CREATE INDEX IF NOT EXISTS ix_ai_feedback_logs_user_intent
    ON ai_feedback_logs (user_id, intent);
CREATE INDEX IF NOT EXISTS ix_ai_feedback_logs_outcome
    ON ai_feedback_logs (outcome, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_feedback_logs_pending
    ON ai_feedback_logs (outcome, created_at)
    WHERE outcome = 'pending';
"""

CREATE_LEARNING_INSIGHTS_TABLE = """
CREATE TABLE IF NOT EXISTS ai_learning_insights (
    id                                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                           UUID NOT NULL,
    intent                            VARCHAR(100) NOT NULL,
    total_count                       INT NOT NULL DEFAULT 0,
    success_count                     INT NOT NULL DEFAULT 0,
    failed_count                      INT NOT NULL DEFAULT 0,
    ignored_count                     INT NOT NULL DEFAULT 0,
    success_rate                      FLOAT NOT NULL DEFAULT 0.0,
    failure_rate                      FLOAT NOT NULL DEFAULT 0.0,
    avg_confidence                    FLOAT NOT NULL DEFAULT 0.0,
    recommended_confidence_threshold  FLOAT NOT NULL DEFAULT 0.60,
    recommended_safe_mode             BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated                      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, intent)
);

CREATE INDEX IF NOT EXISTS ix_ai_learning_insights_user_id
    ON ai_learning_insights (user_id);
"""

CREATE_PROMPT_VERSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS ai_prompt_versions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID,
    intent       VARCHAR(100),
    version      INT NOT NULL DEFAULT 1,
    changes      JSONB NOT NULL DEFAULT '{}',
    success_rate FLOAT NOT NULL DEFAULT 0.0,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


async def create_tables(session) -> None:
    """
    Create all learning engine tables if they don't exist.

    Each DDL statement is executed separately — asyncpg does not allow
    multiple commands in a single prepared statement call.
    """
    # Collect every individual statement from all DDL blocks
    all_ddl = []
    for block in [CREATE_FEEDBACK_LOGS_TABLE, CREATE_LEARNING_INSIGHTS_TABLE, CREATE_PROMPT_VERSIONS_TABLE]:
        # Split on semicolons, strip whitespace, drop empty strings
        statements = [s.strip() for s in block.split(";") if s.strip()]
        all_ddl.extend(statements)

    for stmt in all_ddl:
        await session.execute(text(stmt))

    await session.commit()
    logger.info("Learning engine tables ensured (%d statements executed).", len(all_ddl))


# ── Feedback log operations ───────────────────────────────────────────────────

async def insert_feedback_log(session, data: FeedbackLogCreate) -> UUID:
    """Insert a new feedback log row. Returns the new row UUID."""
    row_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO ai_feedback_logs
                (id, user_id, conversation_id, email_account_id,
                 intent, sub_intent, ai_reply, confidence_score,
                 final_action, outcome, response_time_seconds,
                 safe_mode, policy_rule_id, confidence_level)
            VALUES
                (:id, :user_id, :conversation_id, :email_account_id,
                 :intent, :sub_intent, :ai_reply, :confidence_score,
                 :final_action, :outcome, :response_time_seconds,
                 :safe_mode, :policy_rule_id, :confidence_level)
        """),
        {
            "id":                    str(row_id),
            "user_id":               str(data.user_id),
            "conversation_id":       str(data.conversation_id),
            "email_account_id":      str(data.email_account_id),
            "intent":                data.intent,
            "sub_intent":            data.sub_intent,
            "ai_reply":              data.ai_reply[:4000],   # Guard against oversized replies
            "confidence_score":      data.confidence_score,
            "final_action":          data.final_action,
            "outcome":               data.outcome.value,
            "response_time_seconds": data.response_time_seconds,
            "safe_mode":             data.safe_mode,
            "policy_rule_id":        data.policy_rule_id,
            "confidence_level":      data.confidence_level,
        }
    )
    return row_id


async def update_feedback_outcome(
    session,
    conversation_id: UUID,
    outcome: FeedbackOutcome,
    user_reply: Optional[str] = None,
) -> int:
    """
    Update the outcome of a pending feedback log for a conversation.
    Returns the number of rows updated.
    """
    result = await session.execute(
        text("""
            UPDATE ai_feedback_logs
            SET outcome    = :outcome,
                user_reply = :user_reply,
                updated_at = NOW()
            WHERE conversation_id = :conversation_id
              AND outcome = 'pending'
        """),
        {
            "outcome":         outcome.value,
            "user_reply":      (user_reply or "")[:2000],
            "conversation_id": str(conversation_id),
        }
    )
    return result.rowcount


async def get_pending_feedback_logs(
    session,
    older_than_hours: int = 24,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    Fetch pending feedback logs older than the observation window.
    These will be marked as 'ignored' by the analyzer.
    """
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    result = await session.execute(
        text("""
            SELECT id, user_id, conversation_id, intent, created_at
            FROM ai_feedback_logs
            WHERE outcome = 'pending'
              AND created_at < :cutoff
            ORDER BY created_at ASC
            LIMIT :limit
        """),
        {"cutoff": cutoff, "limit": limit}
    )
    return [dict(row._mapping) for row in result]


async def get_feedback_stats_for_user(
    session,
    user_id: UUID,
    intent: str,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Aggregate feedback stats for a (user_id, intent) pair over the last N days.
    Used by the learning processor to compute insights.
    """
    since = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        text("""
            SELECT
                COUNT(*)                                          AS total_count,
                SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN outcome = 'failed'  THEN 1 ELSE 0 END) AS failed_count,
                SUM(CASE WHEN outcome = 'ignored' THEN 1 ELSE 0 END) AS ignored_count,
                AVG(confidence_score)                             AS avg_confidence
            FROM ai_feedback_logs
            WHERE user_id = :user_id
              AND intent   = :intent
              AND outcome  != 'pending'
              AND created_at >= :since
        """),
        {"user_id": str(user_id), "intent": intent, "since": since}
    )
    row = result.fetchone()
    if not row:
        return {}
    return dict(row._mapping)


async def get_all_user_intent_pairs(session, days: int = 30) -> List[Dict[str, Any]]:
    """Return all distinct (user_id, intent) pairs with recent activity."""
    since = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        text("""
            SELECT DISTINCT user_id, intent
            FROM ai_feedback_logs
            WHERE outcome != 'pending'
              AND created_at >= :since
        """),
        {"since": since}
    )
    return [dict(row._mapping) for row in result]


# ── Learning insights operations ──────────────────────────────────────────────

async def upsert_learning_insight(session, data: Dict[str, Any]) -> None:
    """Insert or update a learning insight row."""
    await session.execute(
        text("""
            INSERT INTO ai_learning_insights
                (id, user_id, intent, total_count, success_count, failed_count,
                 ignored_count, success_rate, failure_rate, avg_confidence,
                 recommended_confidence_threshold, recommended_safe_mode, last_updated)
            VALUES
                (gen_random_uuid(), :user_id, :intent, :total_count, :success_count,
                 :failed_count, :ignored_count, :success_rate, :failure_rate,
                 :avg_confidence, :recommended_confidence_threshold,
                 :recommended_safe_mode, NOW())
            ON CONFLICT (user_id, intent) DO UPDATE SET
                total_count                       = EXCLUDED.total_count,
                success_count                     = EXCLUDED.success_count,
                failed_count                      = EXCLUDED.failed_count,
                ignored_count                     = EXCLUDED.ignored_count,
                success_rate                      = EXCLUDED.success_rate,
                failure_rate                      = EXCLUDED.failure_rate,
                avg_confidence                    = EXCLUDED.avg_confidence,
                recommended_confidence_threshold  = EXCLUDED.recommended_confidence_threshold,
                recommended_safe_mode             = EXCLUDED.recommended_safe_mode,
                last_updated                      = NOW()
        """),
        data
    )


async def get_learning_insight(
    session,
    user_id: UUID,
    intent: str,
) -> Optional[Dict[str, Any]]:
    """Fetch the latest learning insight for a (user_id, intent) pair."""
    result = await session.execute(
        text("""
            SELECT * FROM ai_learning_insights
            WHERE user_id = :user_id AND intent = :intent
        """),
        {"user_id": str(user_id), "intent": intent}
    )
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def cleanup_old_logs(session, older_than_days: int = 90) -> int:
    """Delete feedback logs older than N days. Returns rows deleted."""
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    result = await session.execute(
        text("DELETE FROM ai_feedback_logs WHERE created_at < :cutoff"),
        {"cutoff": cutoff}
    )
    return result.rowcount
