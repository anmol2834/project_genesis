"""
Celery Worker Consumer
Consumes email events from queue and processes them.
High-throughput, idempotent, parallel processing.
"""

from typing import Dict, Any
import asyncio

from shared.logger import get_logger
from email_queue.config.celery_config import get_email_celery_app
from email_queue.tasks.base_task import BaseEmailTask, BaseTaskWithRetry
from worker.processor import EventProcessor

logger = get_logger(__name__)

# Get Celery app
celery_app = get_email_celery_app()


def _run_async(coro):
    """
    Safely run an async coroutine from a sync Celery task.
    Always creates a fresh event loop to avoid Python 3.10+ deprecation issues.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()
            asyncio.set_event_loop(None)


@celery_app.task(
    base=BaseTaskWithRetry,
    name="worker.consumer.process_email_event",
    bind=True,
    max_retries=5,
    default_retry_delay=10
)
def process_email_event(self, event_data: Dict[str, Any]):
    """
    Process email event from email_queue.
    Main entry point for Celery workers.
    
    Args:
        event_data: Normalized email event payload
    """
    try:
        logger.info(
            f"Worker processing event: message_id={event_data.get('message_id')}, "
            f"user_id={event_data.get('user_id')}"
        )
        
        processor = EventProcessor()
        success = _run_async(processor.process_event(event_data))
        
        if success:
            logger.info(f"Successfully processed event: {event_data.get('message_id')}")
            return {
                "status": "success",
                "message_id": event_data.get("message_id"),
                "user_id": event_data.get("user_id")
            }
        else:
            logger.error(f"Failed to process event: {event_data.get('message_id')}")
            raise Exception("Event processing failed")
            
    except Exception as e:
        logger.error(
            f"Worker error processing event {event_data.get('message_id')}: {e}",
            exc_info=True
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=self.default_retry_delay * (2 ** self.request.retries))


@celery_app.task(name="worker.consumer.health_check")
def health_check():
    """Health check task for monitoring."""
    return {"status": "healthy", "worker": "email-service"}


@celery_app.task(name="worker.consumer.cleanup_old_messages")
def cleanup_old_messages():
    """
    Periodic task to cleanup old messages.
    Safety net — the 24h logic handles most cleanup.
    Run daily to ensure consistency.
    """
    try:
        logger.info("Running cleanup_old_messages task")
        # TODO: Implement cleanup logic
        logger.info("Cleanup completed")
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}
