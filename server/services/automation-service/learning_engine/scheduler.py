"""
Learning Engine — Scheduler
=============================
Celery Beat periodic tasks for the learning engine.

Jobs:
  1. learning_cycle_task     — every 6 hours: compute insights from feedback
  2. expire_pending_task     — every 2 hours: mark stale pending logs as ignored
  3. push_cache_task         — every 6 hours: push insights to Redis cache
  4. cleanup_old_logs_task   — daily at 02:00 UTC: delete logs older than 90 days

Registration:
  These tasks are registered with the shared Celery app.
  Beat schedule is added to the automation-service celery worker config.

Usage:
  from learning_engine.scheduler import register_beat_schedule
  register_beat_schedule()   # Call once at automation-service startup
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_beat_schedule() -> None:
    """
    Register learning engine periodic tasks with Celery Beat.
    Call this once during automation-service startup.
    """
    try:
        from shared.celery import get_celery_app
        from celery.schedules import crontab

        app = get_celery_app()

        # Register tasks
        app.conf.beat_schedule.update({
            "learning-cycle-every-6h": {
                "task":     "learning_engine.scheduler.run_learning_cycle_task",
                "schedule": crontab(minute=0, hour="*/6"),
                "options":  {"queue": "automation_queue"},
            },
            "expire-pending-every-2h": {
                "task":     "learning_engine.scheduler.expire_pending_task",
                "schedule": crontab(minute=30, hour="*/2"),
                "options":  {"queue": "automation_queue"},
            },
            "push-cache-every-6h": {
                "task":     "learning_engine.scheduler.push_cache_task",
                "schedule": crontab(minute=15, hour="*/6"),
                "options":  {"queue": "automation_queue"},
            },
            "cleanup-old-logs-daily": {
                "task":     "learning_engine.scheduler.cleanup_logs_task",
                "schedule": crontab(minute=0, hour=2),
                "options":  {"queue": "automation_queue"},
            },
        })

        # Add automation queue to task routes
        if "automation_queue" not in str(app.conf.task_routes):
            existing = dict(app.conf.task_routes or {})
            existing["learning_engine.*"] = {"queue": "automation_queue"}
            app.conf.task_routes = existing

        logger.info("Learning engine beat schedule registered.")
        # Register task functions with Celery
        _make_tasks()

    except Exception as exc:
        logger.error("Failed to register beat schedule: %s", exc)


# ── Celery task definitions ───────────────────────────────────────────────────

def _get_celery():
    from shared.celery import get_celery_app
    return get_celery_app()


def _make_tasks():
    """Register Celery tasks lazily — only called when Celery is available."""
    celery = _get_celery()

    @celery.task(name="learning_engine.scheduler.run_learning_cycle_task", bind=True, max_retries=2)
    def run_learning_cycle_task(self):
        import asyncio
        try:
            from learning_engine.learning_processor import run_learning_cycle
            result = asyncio.get_event_loop().run_until_complete(run_learning_cycle())
            logger.info("Learning cycle task complete: %s", result)
            return result
        except Exception as exc:
            logger.error("Learning cycle task failed: %s", exc)
            raise self.retry(exc=exc, countdown=300)

    @celery.task(name="learning_engine.scheduler.expire_pending_task", bind=True, max_retries=2)
    def expire_pending_task(self):
        import asyncio
        try:
            from learning_engine.feedback_analyzer import expire_pending_logs
            count = asyncio.get_event_loop().run_until_complete(expire_pending_logs())
            logger.info("Expired %d pending logs", count)
            return {"expired": count}
        except Exception as exc:
            logger.error("Expire pending task failed: %s", exc)
            raise self.retry(exc=exc, countdown=120)

    @celery.task(name="learning_engine.scheduler.push_cache_task", bind=True, max_retries=2)
    def push_cache_task(self):
        import asyncio
        try:
            from learning_engine.updater import apply_all_insights_to_cache
            count = asyncio.get_event_loop().run_until_complete(apply_all_insights_to_cache())
            logger.info("Pushed %d insights to cache", count)
            return {"pushed": count}
        except Exception as exc:
            logger.error("Push cache task failed: %s", exc)
            raise self.retry(exc=exc, countdown=120)

    @celery.task(name="learning_engine.scheduler.cleanup_logs_task", bind=True, max_retries=1)
    def cleanup_logs_task(self):
        import asyncio
        try:
            from shared.database import get_db_session
            from learning_engine.repository import cleanup_old_logs

            async def _run():
                async with get_db_session() as session:
                    return await cleanup_old_logs(session, older_than_days=90)

            deleted = asyncio.get_event_loop().run_until_complete(_run())
            logger.info("Cleaned up %d old feedback logs", deleted)
            return {"deleted": deleted}
        except Exception as exc:
            logger.error("Cleanup logs task failed: %s", exc)
            raise self.retry(exc=exc, countdown=600)

    return run_learning_cycle_task, expire_pending_task, push_cache_task, cleanup_logs_task
