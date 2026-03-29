"""
Scheduled Celery Tasks
======================
Three periodic tasks that keep the email ingestion system healthy:

1. subscription_refresh_task  — every 1 hour
   Renews Gmail watches and Outlook Graph subscriptions before they expire.
   Ensures all accounts always have active push notifications.

2. history_sync_task          — every 30 minutes
   Calls Gmail History API for all accounts to recover any emails missed
   during downtime or Pub/Sub delivery failures. Zero data loss guarantee.

3. cleanup_task               — every 24 hours
   Stops Gmail watches for unknown accounts (old projects, manual registrations).
   Keeps the Pub/Sub topic clean.
"""

import asyncio
from datetime import datetime

from shared.logger import get_logger
from email_queue.config.celery_config import get_email_celery_app

logger = get_logger(__name__)
celery_app = get_email_celery_app()


def _run_async(coro):
    """Run async coroutine from sync Celery task (Python 3.10+ safe)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for t in pending:
                t.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()
            asyncio.set_event_loop(None)


@celery_app.task(
    name="email_queue.tasks.scheduled_tasks.subscription_refresh_task",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def subscription_refresh_task(self):
    """
    Renew all expiring Gmail/Outlook subscriptions.
    Runs every hour via Celery Beat.
    """
    logger.info("Scheduled: subscription_refresh_task started")
    try:
        async def _run():
            from provider.manager.subscription_manager import SubscriptionManager
            manager = SubscriptionManager()
            return await manager.sync_all_subscriptions()

        stats = _run_async(_run())
        logger.info(f"Scheduled: subscription_refresh_task complete: {stats}")
        return {"status": "success", "stats": stats, "ran_at": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error(f"subscription_refresh_task failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(
    name="email_queue.tasks.scheduled_tasks.history_sync_task",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def history_sync_task(self):
    """
    Recover emails missed during downtime via Gmail History API.
    Runs every 30 minutes via Celery Beat.
    """
    logger.info("Scheduled: history_sync_task started")
    try:
        async def _run():
            from recovery.history_sync import get_history_sync
            syncer = get_history_sync()
            return await syncer.run_recovery_for_all()

        stats = _run_async(_run())
        logger.info(f"Scheduled: history_sync_task complete: {stats}")
        return {"status": "success", "stats": stats, "ran_at": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error(f"history_sync_task failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(
    name="email_queue.tasks.scheduled_tasks.cleanup_task",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def cleanup_task(self):
    """
    Stop Gmail watches for unknown accounts (old projects, stale registrations).
    Runs every 24 hours via Celery Beat.
    """
    logger.info("Scheduled: cleanup_task started")
    try:
        async def _run():
            from recovery.watch_cleanup import get_watch_cleanup
            cleanup = get_watch_cleanup()
            return await cleanup.cleanup_all_unknown_watches()

        result = _run_async(_run())
        logger.info(f"Scheduled: cleanup_task complete: {result}")
        return {"status": "success", "result": result, "ran_at": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error(f"cleanup_task failed: {e}", exc_info=True)
        # Don't retry cleanup — it's best-effort
        return {"status": "error", "error": str(e)}
