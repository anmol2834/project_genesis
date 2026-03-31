"""
Learning Engine — Updater
==========================
Applies learning insights back into the pipeline.

Redis has been removed from the automation-service to avoid connection
exhaustion on shared free-tier Redis instances.

Insights are read directly from the ai_learning_insights DB table via
retriever.py on every pipeline run. No caching layer needed — the DB
query is a simple indexed lookup (user_id + intent) and is fast enough.

Future: if caching becomes necessary, use an in-process LRU cache
(functools.lru_cache or cachetools.TTLCache) instead of Redis.
"""
from __future__ import annotations

import logging
from typing import Any, Dict
from uuid import UUID

logger = logging.getLogger(__name__)


async def push_insight_to_cache(
    user_id: UUID,
    intent: str,
    confidence_threshold: float,
    safe_mode: bool,
) -> bool:
    """
    No-op — Redis removed from automation-service.
    Insights are read directly from DB by retriever.py.
    """
    return True


async def get_cached_confidence_threshold(
    user_id: UUID,
    intent: str,
    default: float = 0.60,
) -> float:
    """
    No-op cache — falls back to DB lookup via retriever.get_confidence_adjustment().
    """
    return default


async def get_cached_safe_mode(
    user_id: UUID,
    intent: str,
    default: bool = False,
) -> bool:
    """
    No-op cache — falls back to DB lookup via retriever.get_safe_mode_recommendation().
    """
    return default


async def apply_all_insights_to_cache() -> int:
    """
    No-op — Redis removed. Returns 0 (nothing pushed).
    """
    logger.debug("apply_all_insights_to_cache: Redis removed, skipping.")
    return 0
