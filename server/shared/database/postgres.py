"""
PostgreSQL Database Connection Module
Async connection pool — production-grade configuration.

Pool sizing rationale:
  pool_size=15:    handles concurrent webhooks + background tasks + Celery workers
  max_overflow=10: burst headroom for history sync + parallel webhook storms
  pool_timeout=10: fail fast (was 30s — long timeout caused cascade failures)
  pool_pre_ping:   recycles stale AWS RDS connections automatically
  pool_recycle:    prevents 8-hour AWS RDS idle timeout from killing connections

CRITICAL RULE: Never hold a DB session open during network I/O (HTTP calls).
Acquire → query → release. HTTP calls happen OUTSIDE the session context.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import text
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from shared.config import get_config

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine = None
_session_factory = None


def get_engine():
    global _engine

    if _engine is None:
        config = get_config()

        connect_args = {}
        if "rds.amazonaws.com" in config.DATABASE_URL:
            connect_args["ssl"] = "require"

        # asyncpg-specific: set statement_timeout and command_timeout
        # to prevent hanging queries from blocking the pool
        connect_args["command_timeout"] = 30   # max 30s per query
        connect_args["server_settings"] = {
            "statement_timeout": "25000",   # 25s — slightly less than command_timeout
            "idle_in_transaction_session_timeout": "10000",  # 10s idle-in-txn
        }

        _engine = create_async_engine(
            config.DATABASE_URL,
            echo=False,
            pool_size=15,
            max_overflow=10,
            pool_timeout=10,
            pool_pre_ping=True,
            pool_recycle=900,    # was 1800 — recycle every 15min to prevent stale connections
            poolclass=AsyncAdaptedQueuePool,
            connect_args=connect_args,
        )
        logger.info("Database engine created | pool_size=15 max_overflow=10 timeout=10s")

    return _engine


def get_session_factory():
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    CRITICAL: Keep sessions SHORT. Never hold open during network I/O.
    Pattern: acquire → query → release → then do HTTP calls.
    """
    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error("Database session error: %s", e)
        raise
    finally:
        await session.close()


async def init_database():
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection initialized successfully")
        return True
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        return False


async def close_database():
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")


async def check_database_health() -> bool:
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False
