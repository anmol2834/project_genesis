"""
Event Producer
Pushes normalized email events to the queue system.
Fast, non-blocking, and reliable.
"""

from typing import Optional, Dict, Any
import json
from datetime import datetime

from shared.logger import get_logger
from normalizer.event_schema import NormalizedEmailEvent
from email_queue.config.celery_config import get_email_celery_app
from email_queue.producer.router import EventRouter

logger = get_logger(__name__)


class EventProducer:
    """
    Produces email events to the queue system.
    Handles serialization, routing, and error handling.
    """
    
    def __init__(self):
        self.celery_app = get_email_celery_app()
        self.router = EventRouter()
    
    async def produce(
        self,
        event: NormalizedEmailEvent
    ) -> bool:
        """
        Push normalized event to queue.
        
        Args:
            event: Normalized email event
            
        Returns:
            True if successfully queued, False otherwise
        """
        try:
            # Check if event should be skipped
            if self.router.should_skip(event):
                logger.debug(f"Skipping event {event.message_id} based on routing rules")
                return True
            
            # Get routing configuration
            routing_config = self.router.route(event)
            
            # Prepare payload
            payload = self._prepare_payload(event)
            
            # Send to queue
            task_id = await self._send_to_queue(payload, routing_config)
            
            if task_id:
                return True
            else:
                logger.error(f"Failed to queue event {event.message_id}")
                return False
                
        except Exception as e:
            logger.error(
                f"Error producing event {event.message_id}: {e}",
                exc_info=True
            )
            return False
    
    def _prepare_payload(self, event: NormalizedEmailEvent) -> Dict[str, Any]:
        """
        Prepare lightweight payload for queue.
        
        Only include essential fields to minimize queue size.
        """
        payload = {
            # Identity
            "user_id": event.user_id,
            "email_account_id": event.email_account_id,
            
            # Provider
            "provider": event.provider,
            
            # Message identifiers
            "message_id": event.message_id,
            "thread_id": event.thread_id,
            
            # Email headers
            "subject": event.subject,
            "from_email": event.from_email,
            "to_emails": event.to_emails,
            "cc_emails": event.cc_emails,
            
            # Content (AI-ready)
            "content": event.content,
            "content_html": event.content_html,
            
            # Metadata
            "timestamp": event.timestamp.isoformat(),
            "direction": event.direction,
            
            # Attachments
            "has_attachments": event.has_attachments,
            "attachment_count": event.attachment_count,
            
            # Provider-specific data
            "provider_data": event.provider_data,
            
            # Processing metadata
            "received_at": event.received_at.isoformat(),
            "normalized_at": event.normalized_at.isoformat(),
            "queued_at": datetime.utcnow().isoformat()
        }
        
        return payload
    
    async def _send_to_queue(
        self,
        payload: Dict[str, Any],
        routing_config: Dict[str, Any]
    ) -> Optional[str]:
        """
        Send payload to queue using Celery.
        
        Celery's apply_async is synchronous (non-blocking for the broker call itself),
        but we run it in a thread executor to avoid blocking the asyncio event loop
        under high load.
        
        Returns:
            Task ID if successful, None otherwise
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        try:
            from email_queue.tasks.email_tasks import process_email_event

            def _dispatch():
                return process_email_event.apply_async(
                    args=[payload],
                    queue=routing_config["queue"],
                    priority=routing_config["priority"],
                    routing_key=routing_config["routing_key"],
                    retry=True,
                    retry_policy={
                        "max_retries": 3,
                        "interval_start": 10,
                        "interval_step": 20,
                        "interval_max": 60,
                    }
                )

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(executor, _dispatch)

            return result.id

        except Exception as e:
            logger.error(f"Failed to send to queue: {e}", exc_info=True)
            return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue stats
        """
        try:
            inspect = self.celery_app.control.inspect()
            
            # Get active tasks
            active = inspect.active()
            
            # Get reserved tasks
            reserved = inspect.reserved()
            
            # Get scheduled tasks
            scheduled = inspect.scheduled()
            
            stats = {
                "active_tasks": len(active) if active else 0,
                "reserved_tasks": len(reserved) if reserved else 0,
                "scheduled_tasks": len(scheduled) if scheduled else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
