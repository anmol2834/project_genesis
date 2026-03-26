"""Shared cache module"""

from .redis_client import (
    get_redis_client,
    init_redis,
    close_redis,
    check_redis_health,
    get_cached,
    set_cached,
    delete_cached
)

__all__ = [
    "get_redis_client",
    "init_redis",
    "close_redis",
    "check_redis_health",
    "get_cached",
    "set_cached",
    "delete_cached",
]
