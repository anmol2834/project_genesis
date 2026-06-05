"""
Redis Connection Module — Upstash TCP/TLS (rediss://)
All services use REDIS_URL from .env — single source of truth.
"""
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional
import logging, asyncio

from shared.config import get_config

logger = logging.getLogger(__name__)

_redis_pool:   Optional[ConnectionPool] = None
_redis_client: Optional[redis.Redis]    = None
_init_lock = asyncio.Lock()
_initialized_url: Optional[str] = None   # track which URL was used


def _build_pool_sync(url: str, max_connections: int = 20) -> ConnectionPool:
    """
    Build connection pool from the given Redis URL.
    rediss:// → SSL handled automatically by redis-py from the URL scheme.
    """
    return ConnectionPool.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=max_connections,
        socket_timeout=15,
        socket_connect_timeout=10,
        socket_keepalive=True,
        retry_on_timeout=True,
    )


async def init_redis(url: Optional[str] = None) -> bool:
    """
    Initialise Redis connection pool.
    Always uses REDIS_URL from config — the single source of truth.
    The url parameter is accepted for backward compat but REDIS_URL always wins.
    """
    global _redis_pool, _redis_client, _initialized_url
    async with _init_lock:
        if _redis_client is not None:
            return True
        # Always use REDIS_URL from config — never use system env vars directly
        cfg = get_config()
        resolved_url = cfg.REDIS_URL   # single source of truth
        for attempt in range(3):
            try:
                _redis_pool   = _build_pool_sync(resolved_url, 20)
                _redis_client = redis.Redis(connection_pool=_redis_pool)
                await asyncio.wait_for(_redis_client.ping(), timeout=10.0)
                _initialized_url = resolved_url
                logger.info("Redis connected | url=%s", resolved_url[:60])
                return True
            except asyncio.TimeoutError:
                logger.warning("Redis init timeout (attempt %d/3)", attempt + 1)
                _redis_pool = _redis_client = None
            except Exception as e:
                logger.warning("Redis init failed (attempt %d/3): %s", attempt + 1, e)
                _redis_pool = _redis_client = None
            if attempt < 2:
                await asyncio.sleep(1)
        logger.error("Redis unavailable after 3 attempts — url=%s", resolved_url[:60])
        return False


def get_redis_client() -> redis.Redis:
    global _redis_client, _redis_pool
    if _redis_client is None:
        url = get_config().REDIS_URL   # always REDIS_URL — single source of truth
        _redis_pool   = _build_pool_sync(url, 10)
        _redis_client = redis.Redis(connection_pool=_redis_pool)
        logger.info("Redis client created | url=%s", url[:60])
    return _redis_client


async def get_redis() -> redis.Redis:
    if _redis_client is None:
        await init_redis()
    return get_redis_client()


async def close_redis() -> None:
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
        logger.error("Error closing Redis: %s", e)


async def check_redis_health() -> bool:
    try:
        await asyncio.wait_for(get_redis_client().ping(), timeout=3.0)
        return True
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        return False


async def get_cached(key: str) -> Optional[str]:
    try:
        return await get_redis_client().get(key)
    except Exception:
        return None

async def set_cached(key: str, value: str, ttl: int = 300) -> bool:
    try:
        await get_redis_client().setex(key, ttl, value)
        return True
    except Exception:
        return False

async def delete_cached(key: str) -> bool:
    try:
        await get_redis_client().delete(key)
        return True
    except Exception:
        return False
