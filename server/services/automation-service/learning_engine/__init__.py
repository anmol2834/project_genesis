"""
Learning Engine
================
Feedback collection, outcome analysis, and adaptive learning for the ACRE pipeline.

Public interface:
  get_feedback_collector()     — log pipeline results + update outcomes
  get_feedback_insights()      — fetch learning insights for a (user, intent) pair
  get_confidence_adjustment()  — dynamic confidence threshold per user+intent
  get_safe_mode_recommendation() — safe mode flag per user+intent
  run_learning_cycle()         — trigger a full learning cycle (also runs via Celery)
  register_beat_schedule()     — register Celery Beat jobs at startup

Hook point in orchestrator:
  After pipeline.run() returns, call:
    asyncio.create_task(
        get_feedback_collector().log_pipeline_result(...)
    )

Outcome update (when next email arrives in same thread):
    await get_feedback_collector().update_outcome(
        conversation_id, outcome, user_reply
    )
"""
from .feedback_collector import get_feedback_collector, FeedbackCollector
from .retriever import get_feedback_insights, get_confidence_adjustment, get_safe_mode_recommendation
from .learning_processor import run_learning_cycle
from .scheduler import register_beat_schedule

__all__ = [
    "get_feedback_collector",
    "FeedbackCollector",
    "get_feedback_insights",
    "get_confidence_adjustment",
    "get_safe_mode_recommendation",
    "run_learning_cycle",
    "register_beat_schedule",
]
