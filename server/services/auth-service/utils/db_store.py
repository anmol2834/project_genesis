"""
Auth Service — DB-backed Store
================================
Replaces Redis for OTP, rate limiting, and token blacklisting.
Uses a single PostgreSQL table with TTL semantics.

Table: auth_store
  key   TEXT PRIMARY KEY
  value TEXT NOT NULL
  expires_at TIMESTAMP NOT NULL

Expired rows are ignored on read and cleaned up lazily.
All operations are async, using the shared get_db_session().
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

# ── DDL ───────────────────────────────────────────────────────────────────────

CREATE_AUTH_STORE_TABLE = """
CREATE TABLE IF NOT EXISTS auth_store (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_auth_store_expires_at ON auth_store (expires_at);
"""


async def ensure_table() -> None:
    """Create auth_store table if it doesn't exist. Called once at startup."""
    from shared.database import get_db_session
    async with get_db_session() as session:
        for stmt in [s.strip() for s in CREATE_AUTH_STORE_TABLE.split(";") if s.strip()]:
            await session.execute(text(stmt))
        await session.commit()


# ── Core operations ───────────────────────────────────────────────────────────

async def store_set(key: str, value: str, ttl_seconds: int) -> None:
    """Set a key with a TTL (upsert)."""
    from shared.database import get_db_session
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    async with get_db_session() as session:
        await session.execute(
            text("""
                INSERT INTO auth_store (key, value, expires_at)
                VALUES (:key, :value, :expires_at)
                ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value,
                        expires_at = EXCLUDED.expires_at
            """),
            {"key": key, "value": value, "expires_at": expires_at},
        )
        await session.commit()


async def store_get(key: str) -> Optional[str]:
    """Get a key's value. Returns None if missing or expired."""
    from shared.database import get_db_session
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT value FROM auth_store
                WHERE key = :key AND expires_at > NOW()
            """),
            {"key": key},
        )
        row = result.fetchone()
        return row[0] if row else None


async def store_delete(key: str) -> None:
    """Delete a key."""
    from shared.database import get_db_session
    async with get_db_session() as session:
        await session.execute(
            text("DELETE FROM auth_store WHERE key = :key"),
            {"key": key},
        )
        await session.commit()


async def store_increment(key: str, ttl_seconds: int) -> int:
    """
    Increment a counter key. Creates it at 1 if it doesn't exist.
    Returns the new value.
    """
    from shared.database import get_db_session
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO auth_store (key, value, expires_at)
                VALUES (:key, '1', :expires_at)
                ON CONFLICT (key) DO UPDATE
                    SET value = CAST(
                            CASE
                                WHEN auth_store.expires_at > NOW()
                                THEN CAST(auth_store.value AS INTEGER) + 1
                                ELSE 1
                            END AS TEXT
                        ),
                        expires_at = CASE
                            WHEN auth_store.expires_at > NOW()
                            THEN auth_store.expires_at
                            ELSE :expires_at
                        END
                RETURNING value
            """),
            {"key": key, "expires_at": expires_at},
        )
        row = result.fetchone()
        await session.commit()
        return int(row[0]) if row else 1


async def store_exists(key: str) -> bool:
    """Return True if key exists and has not expired."""
    return await store_get(key) is not None


async def cleanup_expired() -> int:
    """Delete all expired rows. Call periodically (e.g. on startup)."""
    from shared.database import get_db_session
    async with get_db_session() as session:
        result = await session.execute(
            text("DELETE FROM auth_store WHERE expires_at <= NOW()")
        )
        await session.commit()
        return result.rowcount
