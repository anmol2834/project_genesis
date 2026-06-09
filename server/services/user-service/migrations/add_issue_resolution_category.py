"""
Migration: Add issue_resolution to datacategory enum
Adds the new 'issue_resolution' value to the existing PostgreSQL enum type.

Usage:
  cd server/services/user-service
  python migrations/add_issue_resolution_category.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from shared.config import get_config

config = get_config()

NEW_VALUE = "issue_resolution"
ENUM_NAME = "datacategory"


def run_migration():
    sync_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    connect_args = {}
    if "rds.amazonaws.com" in sync_url:
        connect_args["sslmode"] = "require"

    engine = create_engine(sync_url, connect_args=connect_args, poolclass=NullPool)

    print("Connecting to database...")
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))
    print("Connected.")

    with engine.begin() as conn:
        # Check if the enum type exists
        result = conn.execute(text(
            "SELECT 1 FROM pg_type WHERE typname = :name",
        ), {"name": ENUM_NAME})
        if not result.fetchone():
            print(f"Enum type '{ENUM_NAME}' does not exist — skipping.")
            engine.dispose()
            return

        # Check if value already present
        result = conn.execute(text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = :name AND enumlabel = :val"
        ), {"name": ENUM_NAME, "val": NEW_VALUE})
        if result.fetchone():
            print(f"Value '{NEW_VALUE}' already exists in '{ENUM_NAME}' — nothing to do.")
            engine.dispose()
            return

        # Add the new enum value (PostgreSQL supports this without a full rebuild)
        conn.execute(text(
            f"ALTER TYPE {ENUM_NAME} ADD VALUE '{NEW_VALUE}'"
        ))
        print(f"Added '{NEW_VALUE}' to enum '{ENUM_NAME}' successfully.")

    engine.dispose()
    print("Migration complete.")


if __name__ == "__main__":
    run_migration()
