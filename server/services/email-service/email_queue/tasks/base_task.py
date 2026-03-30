"""
Base Task
Base class for all email processing tasks with retry and DLQ handling.
"""

from celery import Task
from typing import Any, Dict
import traceback

from shared.logger import get_logger
from email_queue.config.celery_config import get_email_celery_app, EMAIL_DLQ

logger = get_logger(__name__)


class BaseEmailTask(Task):
    """
    Base task class with automatic retry and DLQ handling.
    """
    
    # Retry configuration
    autoretry_for = (Exception,)
    max_retries = 3
    default_retry_delay = 10  # seconds
    
    # Exponential backoff
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max
    retry_jitter = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails after all retries exhausted.
        Sends event to Dead Letter Queue.
        """
        logger.error(
            f"Task {task_id} failed after {self.max_retries} retries: {exc}",
            exc_info=True
        )
        
        # Extract payload
        payload = args[0] if args else kwargs.get("payload", {})
        
        # Send to DLQ
        self._send_to_dlq(payload, task_id, exc, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task is retried.
        """
        retry_count = self.request.retries
        logger.warning(
            f"Task {task_id} retry {retry_count}/{self.max_retries}: {exc}"
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        pass  # success is silent — errors/warnings are the signal
    
    def _send_to_dlq(
        self,
        payload: Dict[str, Any],
        task_id: str,
        exception: Exception,
        einfo: Any
    ):
        """
        Send failed event to Dead Letter Queue.
        """
        try:
            from email_queue.tasks.email_tasks import handle_dlq_event
            
            dlq_payload = {
                "original_payload": payload,
                "task_id": task_id,
                "error": str(exception),
                "traceback": str(einfo),
                "retry_count": self.request.retries,
                "failed_at": self.request.eta or "unknown"
            }
            
            # Send to DLQ
            handle_dlq_event.apply_async(
                args=[dlq_payload],
                queue=EMAIL_DLQ,
                routing_key="email.dlq"
            )
            
            logger.debug(f"Event sent to DLQ: task_id={task_id}")
            
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}", exc_info=True)
    
    def _calculate_retry_delay(self) -> int:
        """
        Calculate retry delay with exponential backoff.
        
        Returns:
            Delay in seconds
        """
        retry_count = self.request.retries
        
        # Exponential backoff: 10s, 30s, 60s
        delays = [10, 30, 60]
        
        if retry_count < len(delays):
            return delays[retry_count]
        else:
            return delays[-1]


class BaseTaskWithRetry(BaseEmailTask):
    """
    Extended base task with higher retry count for consumer workers.
    Used by worker/consumer.py tasks that need more aggressive retry logic.
    """
    max_retries = 5
    default_retry_delay = 10
    retry_backoff = True
    retry_backoff_max = 300   # 5 minutes max for consumer tasks
    retry_jitter = True
