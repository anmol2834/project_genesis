"""Shared database module"""

from .postgres import (
    get_engine,
    get_session_factory,
    get_db_session,
    init_database,
    close_database,
    check_database_health,
    Base
)

from .mongodb import (
    get_mongo_client,
    get_mongo_database,
    init_mongodb,
    close_mongodb,
    check_mongodb_health
)

__all__ = [
    # PostgreSQL
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "init_database",
    "close_database",
    "check_database_health",
    "Base",
    # MongoDB
    "get_mongo_client",
    "get_mongo_database",
    "init_mongodb",
    "close_mongodb",
    "check_mongodb_health",
]
