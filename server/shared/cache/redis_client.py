"""
Redis Connection Module
Async connection using redis-py with asyncio support.

Architecture:
- Single global ConnectionPool shared across the entire process
- Single global Redis client that draws from that pool
- Pool size tuned for concurrent async workload (webhooks + background tasks)
"""

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional
import logging
import asyncio

from shared.config import get_config

logger = logging.getLogger(__name__)

# ── Globals ───────────────────────────────────────────────────────────────────
_redis_pool:   Optional[ConnectionPool] = None
_redis_client: Optional[redis.Redis]    = None
_init_lock = asyncio.Lock()


async def _build_pool() -> ConnectionPool:
    """Build the shared connection pool (called once at startup)."""
    config = get_config()
    pool = ConnectionPool.from_url(
        config.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=5,           # conservative — shared free-tier Redis
        socket_timeout=10,
        socket_connect_timeout=10,
        socket_keepalive=True,
        health_check_interval=30,
        retry_on_timeout=True,
    )
    logger.info("Redis connection pool created (max_connections=5)")
    return pool


async def init_redis() -> bool:
    """
    Initialise the shared pool and client.
    Must be called once at application startup (lifespan).
    """
    global _redis_pool, _redis_client

    async with _init_lock:
        if _redis_client is not None:
            return True  # already initialised

        try:
            _redis_pool   = await _build_pool()
            _redis_client = redis.Redis(connection_pool=_redis_pool)

            await asyncio.wait_for(_redis_client.ping(), timeout=5.0)
            logger.info("Redis initialised successfully")
            return True

        except asyncio.TimeoutError:
            logger.error("Redis init timeout")
            return False
        except Exception as e:
            logger.error(f"Redis init failed: {e}")
            return False


def get_redis_client() -> redis.Redis:
    """
    Return the shared Redis client.
    Raises RuntimeError if init_redis() was never called.
    """
    if _redis_client is None:
        # Fallback: build a client on-the-fly (e.g. Celery worker process)
        config = get_config()
        return redis.from_url(
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
    return _redis_client


async def get_redis() -> redis.Redis:
    """
    Async alias used throughout the codebase: `redis = await get_redis()`.
    Returns the shared client; initialises lazily if needed.
    """
    if _redis_client is None:
        await init_redis()
    return get_redis_client()


async def close_redis() -> None:
    """Close all Redis connections. Call on application shutdown."""
    global _redis_client, _redis_pool

    try:
        if _redis_client:
            await _redis_client.aclose()
            _redis_client = None
        if _redis_pool:
            await _redis_pool.aclose()
            _redis_pool = None
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")


async def check_redis_health() -> bool:
    try:
        client = get_redis_client()
        await asyncio.wait_for(client.ping(), timeout=3.0)
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


# ── Simple cache helpers ──────────────────────────────────────────────────────

async def get_cached(key: str) -> Optional[str]:
    try:
        return await get_redis_client().get(key)
    except Exception as e:
        logger.error(f"Redis GET '{key}': {e}")
        return None


async def set_cached(key: str, value: str, ttl: int = 300) -> bool:
    try:
        await get_redis_client().setex(key, ttl, value)
        return True
    except Exception as e:
        logger.error(f"Redis SET '{key}': {e}")
        return False


async def delete_cached(key: str) -> bool:
    try:
        await get_redis_client().delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis DEL '{key}': {e}")
        return False
