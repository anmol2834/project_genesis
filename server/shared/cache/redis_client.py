"""
Redis Connection Module
Async connection using redis-py with asyncio support
Used for caching and Celery broker
"""

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional
import logging
import asyncio

from shared.config import get_config

logger = logging.getLogger(__name__)

# Global Redis connection pool
_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None
_pool_lock = asyncio.Lock()


async def get_redis_pool() -> ConnectionPool:
    """
    Get or create Redis connection pool
    Ensures single pool instance across application
    """
    global _redis_pool
    
    if _redis_pool is None:
        async with _pool_lock:
            if _redis_pool is None:  # Double-check after acquiring lock
                config = get_config()
                
                _redis_pool = ConnectionPool.from_url(
                    config.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=5,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    socket_keepalive=True,
                    health_check_interval=30,
                    retry_on_timeout=True,
                )
                
                logger.info(f"Redis connection pool created with max_connections=5")
    
    return _redis_pool


def get_redis_client() -> redis.Redis:
    """
    Get or create Redis client
    Uses shared connection pool to prevent exhaustion
    """
    global _redis_client
    
    if _redis_client is None:
        config = get_config()
        
        # Create client without pool first (pool will be set during init)
        _redis_client = redis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=5,
            socket_timeout=10,
            socket_connect_timeout=10,
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        
        logger.info(f"Redis client created with connection pooling")
    
    return _redis_client


async def init_redis():
    """
    Initialize Redis connection pool
    Call this on application startup
    """
    try:
        # Initialize pool first
        pool = await get_redis_pool()
        
        # Get client
        client = get_redis_client()
        
        # Test connection with timeout
        try:
            await asyncio.wait_for(client.ping(), timeout=5.0)
            logger.info("Redis connection initialized successfully")
            return True
        except asyncio.TimeoutError:
            logger.error("Redis initialization timeout")
            return False
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        return False


async def close_redis():
    """
    Close Redis connections and pool
    Call this on application shutdown
    """
    global _redis_client, _redis_pool
    
    try:
        if _redis_client:
            await _redis_client.close()
            _redis_client = None
        
        if _redis_pool:
            await _redis_pool.disconnect()
            _redis_pool = None
        
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis connections: {e}")


async def check_redis_health() -> bool:
    """
    Check Redis connection health with timeout
    Used for health check endpoints
    """
    try:
        client = get_redis_client()
        await asyncio.wait_for(client.ping(), timeout=3.0)
        return True
    except asyncio.TimeoutError:
        logger.error("Redis health check timeout")
        return False
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
