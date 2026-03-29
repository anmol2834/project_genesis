"""
Event Deduplicator
Prevents duplicate email event processing using Redis.
"""

from shared.logger import get_logger
from shared.cache import get_redis

logger = get_logger(__name__)


class EventDeduplicator:
    """Deduplicates email events using message_id as unique key."""

    # TTL for deduplication keys (24 hours)
    DEDUP_TTL = 86400

    async def is_duplicate(self, event_key: str) -> bool:
        """
        Check if event has already been processed.
        
        Args:
            event_key: Unique event identifier (e.g., "gmail_message_id")
        
        Returns:
            True if event is duplicate, False if new
        """
        redis = await get_redis()
        
        key = f"dedup:event:{event_key}"
        exists = await redis.exists(key)
        
        return bool(exists)

    async def mark_processed(self, event_key: str):
        """
        Mark event as processed.
        
        Args:
            event_key: Unique event identifier
        """
        redis = await get_redis()
        
        key = f"dedup:event:{event_key}"
        await redis.setex(key, self.DEDUP_TTL, "1")
        
        logger.debug(f"Event marked as processed: {event_key}")

    async def clear_event(self, event_key: str):
        """
        Clear event from deduplication cache (for testing/debugging).
        
        Args:
            event_key: Unique event identifier
        """
        redis = await get_redis()
        
        key = f"dedup:event:{event_key}"
        await redis.delete(key)
        
        logger.debug(f"Event cleared from dedup cache: {event_key}")

    async def get_stats(self) -> dict:
        """Get deduplication statistics."""
        redis = await get_redis()
        
        # Count all dedup keys
        cursor = 0
        count = 0
        
        while True:
            cursor, keys = await redis.scan(
                cursor,
                match="dedup:event:*",
                count=100
            )
            count += len(keys)
            
            if cursor == 0:
                break
        
        return {
            "total_tracked_events": count,
            "ttl_seconds": self.DEDUP_TTL
        }
