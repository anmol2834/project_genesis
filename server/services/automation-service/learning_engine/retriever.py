"""
Learning Engine — Retriever
============================
Fetches learning insights and injects them into the AI pipeline.

Integration points:
  - Confidence Engine: get_confidence_adjustment(user_id, intent)
  - Policy Engine:     get_safe_mode_recommendation(user_id, intent)
  - Prompt Compiler:   get_prompt_hints(user_id, intent)

All lookups are per (user_id, intent) — strict multi-tenant isolation.
Falls back to defaults when no insight exists (new user / new intent).

Usage in pipeline:
  insights = await get_feedback_insights(user_id, intent)
  # insights.recommended_confidence_threshold → override confidence threshold
  # insights.recommended_safe_mode           → force safe mode
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from .repository import get_learning_insight
from .schema import LearningInsight

logger = logging.getLogger(__name__)

# Defaults used when no insight exists
_DEFAULT_THRESHOLD = 0.60
_DEFAULT_SAFE_MODE = False


async def get_feedback_insights(
    user_id: UUID,
    intent: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch the latest learning insight for a (user_id, intent) pair.

    Returns:
        Dict with insight fields, or None if no data exists yet.
    """
    try:
        from shared.database import get_db_session
        async with get_db_session() as session:
            return await get_learning_insight(session, user_id, intent)
    except Exception as exc:
        logger.warning("get_feedback_insights failed: %s — using defaults", exc)
        return None


async def get_confidence_adjustment(
    user_id: UUID,
    intent: str,
) -> float:
    """
    Return the recommended confidence threshold for this (user, intent) pair.
    Used by the Confidence Engine to dynamically adjust thresholds.

    Returns:
        float — recommended threshold in [0.50, 0.85]
    """
    insight = await get_feedback_insights(user_id, intent)
    if insight:
        return float(insight.get("recommended_confidence_threshold", _DEFAULT_THRESHOLD))
    return _DEFAULT_THRESHOLD


async def get_safe_mode_recommendation(
    user_id: UUID,
    intent: str,
) -> bool:
    """
    Return whether safe mode is recommended for this (user, intent) pair.
    Used by the Policy Engine to override the default safe mode decision.

    Returns:
        bool — True if safe mode is recommended based on historical failures.
    """
    insight = await get_feedback_insights(user_id, intent)
    if insight:
        return bool(insight.get("recommended_safe_mode", _DEFAULT_SAFE_MODE))
    return _DEFAULT_SAFE_MODE


async def get_prompt_hints(
    user_id: UUID,
    intent: str,
) -> Dict[str, Any]:
    """
    Return prompt-level hints derived from learning insights.
    Used by the Prompt Compiler to adjust tone and constraints.

    Returns:
        Dict with hint fields:
          - success_rate: float
          - failure_rate: float
          - avg_confidence: float
          - force_safe_mode: bool
          - confidence_threshold: float
    """
    insight = await get_feedback_insights(user_id, intent)
    if not insight:
        return {
            "success_rate":         0.0,
            "failure_rate":         0.0,
            "avg_confidence":       0.0,
            "force_safe_mode":      False,
            "confidence_threshold": _DEFAULT_THRESHOLD,
            "has_data":             False,
        }

    return {
        "success_rate":         float(insight.get("success_rate", 0.0)),
        "failure_rate":         float(insight.get("failure_rate", 0.0)),
        "avg_confidence":       float(insight.get("avg_confidence", 0.0)),
        "force_safe_mode":      bool(insight.get("recommended_safe_mode", False)),
        "confidence_threshold": float(insight.get("recommended_confidence_threshold", _DEFAULT_THRESHOLD)),
        "has_data":             True,
    }
