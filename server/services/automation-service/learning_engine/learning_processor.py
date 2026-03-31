"""
Learning Engine — Learning Processor
======================================
Core brain of the adaptive learning system.

Runs periodically (every 6 hours via Celery Beat).
For each (user_id, intent) pair with recent activity:
  1. Aggregate feedback stats from ai_feedback_logs
  2. Compute success_rate, failure_rate, avg_confidence
  3. Derive recommendations:
     - recommended_confidence_threshold (dynamic adjustment)
     - recommended_safe_mode (force safe mode when failure rate is high)
  4. Upsert into ai_learning_insights

Recommendation logic:
  success_rate >= 0.80 → lower threshold slightly (AI is doing well)
  success_rate < 0.60  → raise threshold + enable safe_mode
  failure_rate > 0.40  → force safe_mode
  avg_confidence < 0.65 → raise threshold

Multi-tenant: all computations are per user_id — no cross-user data mixing.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from .repository import (
    get_all_user_intent_pairs,
    get_feedback_stats_for_user,
    upsert_learning_insight,
)

logger = logging.getLogger(__name__)

# ── Threshold adjustment constants ────────────────────────────────────────────
DEFAULT_CONFIDENCE_THRESHOLD = 0.60
MIN_CONFIDENCE_THRESHOLD     = 0.50
MAX_CONFIDENCE_THRESHOLD     = 0.85
MIN_SAMPLES_FOR_LEARNING     = 5    # Don't adjust until we have enough data


def compute_recommendations(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive confidence threshold and safe_mode recommendation from stats.

    Args:
        stats: Row from get_feedback_stats_for_user()

    Returns:
        Dict with recommended_confidence_threshold and recommended_safe_mode.
    """
    total   = int(stats.get("total_count") or 0)
    success = int(stats.get("success_count") or 0)
    failed  = int(stats.get("failed_count") or 0)
    avg_conf = float(stats.get("avg_confidence") or DEFAULT_CONFIDENCE_THRESHOLD)

    if total < MIN_SAMPLES_FOR_LEARNING:
        return {
            "recommended_confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
            "recommended_safe_mode":            False,
        }

    success_rate = success / total
    failure_rate = failed  / total

    threshold = DEFAULT_CONFIDENCE_THRESHOLD

    # AI is performing well → slightly lower threshold (allow more responses)
    if success_rate >= 0.80:
        threshold = max(MIN_CONFIDENCE_THRESHOLD, threshold - 0.05)

    # High failure rate → raise threshold (be more selective)
    elif success_rate < 0.60 or failure_rate > 0.35:
        threshold = min(MAX_CONFIDENCE_THRESHOLD, threshold + 0.10)

    # Average confidence is low → raise threshold
    if avg_conf < 0.65:
        threshold = min(MAX_CONFIDENCE_THRESHOLD, threshold + 0.05)

    # Force safe mode when failure rate is high
    safe_mode = failure_rate > 0.40

    return {
        "recommended_confidence_threshold": round(threshold, 4),
        "recommended_safe_mode":            safe_mode,
    }


async def run_learning_cycle(days: int = 30) -> Dict[str, int]:
    """
    Run a full learning cycle for all active (user_id, intent) pairs.

    Args:
        days: Look-back window for feedback data.

    Returns:
        Dict with counts: {"processed": N, "errors": M}
    """
    processed = 0
    errors    = 0

    try:
        from shared.database import get_db_session

        async with get_db_session() as session:
            pairs = await get_all_user_intent_pairs(session, days=days)

        logger.info("Learning cycle: processing %d (user, intent) pairs", len(pairs))

        for pair in pairs:
            user_id = UUID(str(pair["user_id"]))
            intent  = str(pair["intent"])

            try:
                async with get_db_session() as session:
                    stats = await get_feedback_stats_for_user(session, user_id, intent, days=days)

                if not stats or not stats.get("total_count"):
                    continue

                total   = int(stats["total_count"] or 0)
                success = int(stats["success_count"] or 0)
                failed  = int(stats["failed_count"] or 0)
                ignored = int(stats["ignored_count"] or 0)
                avg_conf = float(stats["avg_confidence"] or 0.0)

                success_rate = success / total if total > 0 else 0.0
                failure_rate = failed  / total if total > 0 else 0.0

                recs = compute_recommendations(stats)

                insight_data = {
                    "user_id":                           str(user_id),
                    "intent":                            intent,
                    "total_count":                       total,
                    "success_count":                     success,
                    "failed_count":                      failed,
                    "ignored_count":                     ignored,
                    "success_rate":                      round(success_rate, 4),
                    "failure_rate":                      round(failure_rate, 4),
                    "avg_confidence":                    round(avg_conf, 4),
                    "recommended_confidence_threshold":  recs["recommended_confidence_threshold"],
                    "recommended_safe_mode":             recs["recommended_safe_mode"],
                }

                async with get_db_session() as session:
                    await upsert_learning_insight(session, insight_data)

                processed += 1
                logger.debug(
                    "Insight updated: user=%s intent=%s success=%.2f failure=%.2f",
                    str(user_id)[:8], intent, success_rate, failure_rate,
                )

            except Exception as exc:
                logger.error("Learning cycle error for user=%s intent=%s: %s", user_id, intent, exc)
                errors += 1

    except Exception as exc:
        logger.error("Learning cycle failed: %s", exc)
        errors += 1

    logger.info("Learning cycle complete: processed=%d errors=%d", processed, errors)
    return {"processed": processed, "errors": errors}
