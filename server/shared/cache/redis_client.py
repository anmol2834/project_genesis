"""
Redis Connection Module
Async connection using redis-py with asyncio support
Used for caching and Celery broker
"""

import redis.asyncio as redis
from typing import Optional
import logging

from shared.config import get_config

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Get or create Redis client
    Connection pooling handled automatically
    """
    global _redis_client
    
    if _redis_client is None:
        config = get_config()
        
        _redis_client = redis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=config.REDIS_MAX_CONNECTIONS,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        
        logger.info(f"Redis client created with max_connections={config.REDIS_MAX_CONNECTIONS}")
    
    return _redis_client


async def init_redis():
    """
    Initialize Redis connection
    Call this on application startup
    """
    try:
        client = get_redis_client()
        
        # Test connection
        await client.ping()
        
        logger.info("Redis connection initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        return False


async def close_redis():
    """
    Close Redis connections
    Call this on application shutdown
    """
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connections closed")


async def check_redis_health() -> bool:
    """
    Check Redis connection health
    Used for health check endpoints
    """
    try:
        client = get_redis_client()
        await client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


async def get_cached(key: str) -> Optional[str]:
    """
    Get value from Redis cache
    """
    try:
        client = get_redis_client()
        return await client.get(key)
    except Exception as e:
        logger.error(f"Redis get error for key '{key}': {e}")
        return None


async def set_cached(key: str, value: str, ttl: int = 300) -> bool:
    """
    Set value in Redis cache with TTL
    Default TTL: 5 minutes
    """
    try:
        client = get_redis_client()
        await client.setex(key, ttl, value)
        return True
    except Exception as e:
        logger.error(f"Redis set error for key '{key}': {e}")
        return False


async def delete_cached(key: str) -> bool:
    """
    Delete value from Redis cache
    """
    try:
        client = get_redis_client()
        await client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis delete error for key '{key}': {e}")
        return False
