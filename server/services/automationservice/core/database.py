"""
automationservice — Database Session
Reuses the shared PostgreSQL DB where emailservice writes es_messages/es_conversations.

sys.path note:
  This file lives at:  server/services/automationservice/core/database.py
  server/ is 4 levels up:  ../../../../  → but os.path resolution from __file__:
    dirname(__file__)          = .../core
    dirname(dirname)           = .../automationservice
    dirname(dirname(dirname))  = .../services
    dirname x4                 = .../server   ← what we need
"""
from __future__ import annotations
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Resolve server/ root regardless of cwd or how the module was imported
_CORE_DIR     = os.path.dirname(os.path.abspath(__file__))          # .../core
_SVC_DIR      = os.path.dirname(_CORE_DIR)                          # .../automationservice
_SERVICES_DIR = os.path.dirname(_SVC_DIR)                           # .../services
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)                      # .../server  ← correct
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
import logging

from shared.config import get_config

logger = logging.getLogger("automationservice.database")

_engine  = None
_Session = None


def _get_engine():
    global _engine, _Session
    if _engine is None:
        cfg = get_config()

        # Mirror shared/database/postgres.py connect_args exactly —
        # same RDS instance requires SSL + timeouts
        connect_args: dict = {}
        if "rds.amazonaws.com" in cfg.DATABASE_URL:
            connect_args["ssl"] = "require"
        connect_args["command_timeout"] = 30
        connect_args["server_settings"] = {
            "statement_timeout":                    "25000",
            "idle_in_transaction_session_timeout":  "10000",
        }

        _engine = create_async_engine(
            cfg.DATABASE_URL,
            echo=False,
            pool_size=5,
            max_overflow=5,
            pool_timeout=10,
            pool_pre_ping=True,
            pool_recycle=900,
            poolclass=AsyncAdaptedQueuePool,
            connect_args=connect_args,
        )
        _Session = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("automationservice DB engine created | pool_size=5 max_overflow=5")
    return _engine


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager — mirrors shared/database/postgres.py pattern exactly.
    Commit on success, rollback on error, always close.
    """
    _get_engine()
    session: AsyncSession = _Session()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error("DB session error: %s", e)
        raise
    finally:
        await session.close()


async def close_db() -> None:
    global _engine, _Session
    if _engine:
        await _engine.dispose()
        _engine  = None
        _Session = None
        logger.info("automationservice DB pool closed")
