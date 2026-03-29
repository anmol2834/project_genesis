"""
Migration: Add last_history_id and watch_expiry to email_accounts table.

Run once:
    cd server/services/email-service
    set PYTHONPATH=%cd%;%cd%\..\..
    python create_email_accounts_migration.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.database import init_database, close_database
from shared.database.postgres import get_engine
from sqlalchemy import text


async def migrate():
    await init_database()
    engine = get_engine()

    migrations = [
        """
        ALTER TABLE email_accounts
        ADD COLUMN IF NOT EXISTS last_history_id VARCHAR(64) NULL;
        """,
        """
        ALTER TABLE email_accounts
        ADD COLUMN IF NOT EXISTS watch_expiry TIMESTAMP WITHOUT TIME ZONE NULL;
        """,
    ]

    async with engine.begin() as conn:
        for sql in migrations:
            await conn.execute(text(sql.strip()))
            print(f"OK: {sql.strip()[:60]}")

    await close_database()
    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
