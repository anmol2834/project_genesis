"""
Email Processing Tasks
Celery tasks for processing email events from the queue.
Integrated with worker layer for actual processing.
"""

from typing import Dict, Any
from datetime import datetime
import asyncio

from shared.logger import get_logger
from email_queue.config.celery_config import get_email_celery_app
from email_queue.tasks.base_task import BaseEmailTask
from worker.processor import EventProcessor

logger = get_logger(__name__)

# Get Celery app
celery_app = get_email_celery_app()


def _run_async(coro):
    """
    Safely run an async coroutine from a sync Celery task.

    Critical: SQLAlchemy's async engine holds connections tied to the event loop.
    When we close the loop after each task, those connections become invalid.
    We reset the engine globals before each run so a fresh engine+pool is created
    on the new loop — preventing 'Event loop is closed' errors on retries.
    """
    # Reset the shared async engine so it's recreated on the new event loop
    import shared.database.postgres as _pg
    _pg._engine = None
    _pg._session_factory = None

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            # Dispose the engine cleanly before closing the loop
            if _pg._engine is not None:
                loop.run_until_complete(_pg._engine.dispose())
        except Exception:
            pass
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
            # Reset again so next task gets a clean engine
            _pg._engine = None
            _pg._session_factory = None


@celery_app.task(
    base=BaseEmailTask,
    name="email_queue.tasks.email_tasks.process_email_event",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True
)
def process_email_event(self, payload: Dict[str, Any]):
    """
    Process email event from email_queue.
    
    Args:
        payload: Email event payload
    """
    message_id = payload.get("message_id", "unknown")
    user_id = payload.get("user_id", "unknown")
    provider = payload.get("provider", "unknown")
    subject  = payload.get("subject", "")

    logger.debug(
        f"[WORKER] Received task: message_id={message_id} "
        f"user_id={user_id} provider={provider} subject='{subject}'"
    )

    try:
        processor = EventProcessor()
        success = _run_async(processor.process_event(payload))

        if success:
            return {
                "status": "success",
                "message_id": message_id,
                "processed_at": datetime.utcnow().isoformat()
            }
        else:
            logger.error(f"[WORKER] ✗ FAILED to save: message_id={message_id}")
            raise Exception("Event processing failed")
        
    except Exception as e:
        logger.error(f"Error processing email event {message_id}: {e}")
        raise  # Re-raise to trigger retry


@celery_app.task(
    name="email_queue.tasks.email_tasks.retry_email_event",
    bind=True,
    acks_late=True
)
def retry_email_event(self, payload: Dict[str, Any]):
    """
    Retry failed email event.
    
    Args:
        payload: Email event payload
    """
    message_id = payload.get("message_id", "unknown")
    
    logger.info(f"Retrying email event: {message_id}")
    
    try:
        return process_email_event.apply_async(
            args=[payload],
            retry=True
        )
        
    except Exception as e:
        logger.error(f"Error retrying email event {message_id}: {e}")
        raise


@celery_app.task(
    name="email_queue.tasks.email_tasks.handle_dlq_event",
    bind=True,
    acks_late=True
)
def handle_dlq_event(self, dlq_payload: Dict[str, Any]):
    """
    Handle event in Dead Letter Queue.
    Logs the failure and stores it for manual review.
    
    Args:
        dlq_payload: DLQ payload with original event and error info
    """
    original_payload = dlq_payload.get("original_payload", {})
    message_id = original_payload.get("message_id", "unknown")
    error = dlq_payload.get("error", "unknown")
    task_id = dlq_payload.get("task_id", "unknown")
    
    logger.error(
        f"Event in DLQ: "
        f"message_id={message_id}, "
        f"task_id={task_id}, "
        f"error={error}"
    )
    
    try:
        # Persist DLQ event to Redis for manual review / alerting
        import json

        dlq_record = json.dumps({
            "message_id": message_id,
            "task_id": task_id,
            "error": error,
            "payload": original_payload,
            "logged_at": datetime.utcnow().isoformat()
        })

        def _store_dlq():
            from shared.cache import get_redis_client
            client = get_redis_client()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def _store():
                    await client.lpush("email:dlq:events", dlq_record)
                    # Keep only last 1000 DLQ events
                    await client.ltrim("email:dlq:events", 0, 999)
                loop.run_until_complete(_store())
            finally:
                loop.close()
                asyncio.set_event_loop(None)

        _store_dlq()
        logger.debug(f"DLQ event stored: {message_id}")
        
        return {
            "status": "dlq_logged",
            "message_id": message_id,
            "task_id": task_id,
            "logged_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error handling DLQ event {message_id}: {e}")
        # Don't raise — DLQ handler must never fail
        return {
            "status": "dlq_error",
            "message_id": message_id,
            "error": str(e)
        }
