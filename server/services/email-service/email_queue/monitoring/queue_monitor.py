"""
Queue Monitor
Monitors queue health, performance, and statistics.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from shared.logger import get_logger
from shared.cache import get_redis
from email_queue.config.celery_config import (
    get_email_celery_app,
    EMAIL_EVENTS_QUEUE,
    EMAIL_RETRY_QUEUE,
    EMAIL_DLQ
)

logger = get_logger(__name__)


class QueueMonitor:
    """
    Monitors queue system health and performance.
    """
    
    def __init__(self):
        self.celery_app = get_email_celery_app()
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive queue statistics.
        
        Returns:
            Dictionary with queue stats
        """
        try:
            stats = {
                "timestamp": datetime.utcnow().isoformat(),
                "queues": {},
                "workers": {},
                "tasks": {}
            }
            
            # Get queue lengths
            stats["queues"] = await self._get_queue_lengths()
            
            # Get worker stats
            stats["workers"] = self._get_worker_stats()
            
            # Get task stats
            stats["tasks"] = self._get_task_stats()
            
            # Get processing rate
            stats["processing_rate"] = await self._get_processing_rate()
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _get_queue_lengths(self) -> Dict[str, int]:
        """Get length of each queue."""
        try:
            redis = await get_redis()
            
            queues = {
                EMAIL_EVENTS_QUEUE: 0,
                EMAIL_RETRY_QUEUE: 0,
                EMAIL_DLQ: 0
            }
            
            for queue_name in queues.keys():
                # Redis list length
                length = await redis.llen(queue_name)
                queues[queue_name] = length
            
            return queues
            
        except Exception as e:
            logger.error(f"Failed to get queue lengths: {e}")
            return {}
    
    def _get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        try:
            inspect = self.celery_app.control.inspect()
            
            # Get active workers
            active_workers = inspect.active()
            
            # Get worker stats
            stats = inspect.stats()
            
            worker_info = {
                "active_workers": len(active_workers) if active_workers else 0,
                "workers": []
            }
            
            if stats:
                for worker_name, worker_stats in stats.items():
                    worker_info["workers"].append({
                        "name": worker_name,
                        "pool": worker_stats.get("pool", {}),
                        "total_tasks": worker_stats.get("total", {})
                    })
            
            return worker_info
            
        except Exception as e:
            logger.error(f"Failed to get worker stats: {e}")
            return {"error": str(e)}
    
    def _get_task_stats(self) -> Dict[str, Any]:
        """Get task statistics."""
        try:
            inspect = self.celery_app.control.inspect()
            
            # Get active tasks
            active = inspect.active()
            
            # Get reserved tasks
            reserved = inspect.reserved()
            
            # Get scheduled tasks
            scheduled = inspect.scheduled()
            
            # Count tasks
            active_count = sum(len(tasks) for tasks in active.values()) if active else 0
            reserved_count = sum(len(tasks) for tasks in reserved.values()) if reserved else 0
            scheduled_count = sum(len(tasks) for tasks in scheduled.values()) if scheduled else 0
            
            return {
                "active": active_count,
                "reserved": reserved_count,
                "scheduled": scheduled_count,
                "total": active_count + reserved_count + scheduled_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get task stats: {e}")
            return {"error": str(e)}
    
    async def _get_processing_rate(self) -> Dict[str, float]:
        """
        Get processing rate (events per minute).
        
        Uses Redis to track processed events.
        """
        try:
            redis = await get_redis()
            
            # Get processed count from last minute
            current_minute = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
            key = f"queue:processed:{current_minute}"
            
            processed_count = await redis.get(key)
            processed_count = int(processed_count) if processed_count else 0
            
            return {
                "events_per_minute": processed_count,
                "minute": current_minute
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing rate: {e}")
            return {"error": str(e)}
    
    async def increment_processed_count(self):
        """
        Increment processed event counter.
        Called after each successful event processing.
        """
        try:
            redis = await get_redis()
            
            current_minute = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
            key = f"queue:processed:{current_minute}"
            
            # Increment counter
            await redis.incr(key)
            
            # Set expiry (2 minutes)
            await redis.expire(key, 120)
            
        except Exception as e:
            logger.error(f"Failed to increment processed count: {e}")
    
    async def get_dlq_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get events from Dead Letter Queue (stored in Redis by handle_dlq_event task).
        
        Args:
            limit: Maximum number of events to retrieve
            
        Returns:
            List of DLQ events
        """
        try:
            redis = await get_redis()
            
            # DLQ events are stored under "email:dlq:events" by handle_dlq_event
            events_raw = await redis.lrange("email:dlq:events", 0, limit - 1)
            
            dlq_events = []
            for event_data in events_raw:
                if isinstance(event_data, bytes):
                    event_data = event_data.decode()
                try:
                    import json
                    event = json.loads(event_data)
                    dlq_events.append(event)
                except Exception:
                    pass
            
            return dlq_events
            
        except Exception as e:
            logger.error(f"Failed to get DLQ events: {e}")
            return []
    
    async def check_queue_health(self) -> Dict[str, Any]:
        """
        Check overall queue system health.
        
        Returns:
            Health status with warnings/errors
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "warnings": [],
            "errors": []
        }
        
        try:
            # Check queue lengths
            queue_lengths = await self._get_queue_lengths()
            
            # Warn if main queue is too long
            if queue_lengths.get(EMAIL_EVENTS_QUEUE, 0) > 1000:
                health["warnings"].append(
                    f"Main queue length is high: {queue_lengths[EMAIL_EVENTS_QUEUE]}"
                )
                health["status"] = "degraded"
            
            # Error if DLQ is growing
            if queue_lengths.get(EMAIL_DLQ, 0) > 100:
                health["errors"].append(
                    f"DLQ has many failed events: {queue_lengths[EMAIL_DLQ]}"
                )
                health["status"] = "unhealthy"
            
            # Check workers
            worker_stats = self._get_worker_stats()
            if worker_stats.get("active_workers", 0) == 0:
                health["errors"].append("No active workers")
                health["status"] = "unhealthy"
            
            health["queue_lengths"] = queue_lengths
            health["active_workers"] = worker_stats.get("active_workers", 0)
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health["status"] = "unhealthy"
            health["errors"].append(str(e))
        
        return health
