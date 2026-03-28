"""
PostgreSQL Database Connection Module
Async connection pool using SQLAlchemy + asyncpg
NO MODELS - Only connection layer
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy import text
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from shared.config import get_config

logger = logging.getLogger(__name__)

# Base class for future models (not created here)
Base = declarative_base()

# Global engine instance
_engine = None
_session_factory = None


def get_engine():
    """
    Get or create async database engine
    Connection pooling configured for high performance
    """
    global _engine
    
    if _engine is None:
        config = get_config()
        
        # Connection arguments for AWS RDS
        connect_args = {}
        if "rds.amazonaws.com" in config.DATABASE_URL:
            # AWS RDS requires SSL
            connect_args["ssl"] = "require"
        
        _engine = create_async_engine(
            config.DATABASE_URL,
            echo=False,  # Disable SQL query logging
            pool_size=5,  # Reduced from 20 for Windows
            max_overflow=3,  # Reduced from 10 for Windows
            pool_timeout=config.DB_POOL_TIMEOUT,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=1800,   # Recycle connections after 30 minutes (AWS RDS)
            poolclass=AsyncAdaptedQueuePool,
            connect_args=connect_args,
        )
        
        logger.info(f"Database engine created with pool_size=5")
    
    return _engine


def get_session_factory():
    """
    Get or create async session factory
    """
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
        
        logger.info("Database session factory created")
    
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions
    
    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def init_database():
    """
    Initialize database connection
    Call this on application startup
    """
    try:
        engine = get_engine()
        
        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("Database connection initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


async def close_database():
    """
    Close database connections
    Call this on application shutdown
    """
    global _engine, _session_factory
    
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")


async def check_database_health() -> bool:
    """
    Check database connection health
    Used for health check endpoints
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
