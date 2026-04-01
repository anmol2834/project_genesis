"""
Migration: Add Data Intelligence Columns
Adds subtype, ai_tags, entities, classification_meta to user_data_entries.
Adds subtype, ai_tags, entities, raw_data to user_data_versions.
Adds uncategorized to DataCategory enum.

Run once:
  cd server/services/user-service
  python migrations/add_intelligence_columns.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from shared.config import get_config

config = get_config()


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
        # ── user_data_entries: new intelligence columns ───────────────────
        _add_column_if_missing(conn, "user_data_entries", "subtype",             "VARCHAR(100)")
        _add_column_if_missing(conn, "user_data_entries", "ai_tags",             "JSONB")
        _add_column_if_missing(conn, "user_data_entries", "entities",            "JSONB")
        _add_column_if_missing(conn, "user_data_entries", "classification_meta", "JSONB")

        # ── user_data_versions: new columns ──────────────────────────────
        _add_column_if_missing(conn, "user_data_versions", "subtype",   "VARCHAR(100)")
        _add_column_if_missing(conn, "user_data_versions", "ai_tags",   "JSONB")
        _add_column_if_missing(conn, "user_data_versions", "entities",  "JSONB")
        _add_column_if_missing(conn, "user_data_versions", "raw_data",  "JSONB")

        # ── Add 'uncategorized' to DataCategory enum ──────────────────────
        try:
            conn.execute(text("ALTER TYPE datacategory ADD VALUE IF NOT EXISTS 'uncategorized'"))
            print("  Enum: added 'uncategorized' to datacategory")
        except Exception as e:
            print(f"  Enum update skipped (may already exist): {e}")

        # ── Indexes for new columns ───────────────────────────────────────
        _create_index_if_missing(conn, "ix_user_data_entries_user_subtype",
                                 "user_data_entries", "user_id, subtype")
        _create_index_if_missing(conn, "ix_user_data_entries_quality",
                                 "user_data_entries", "user_id, quality_score")

    engine.dispose()
    print("Migration complete.")


def _add_column_if_missing(conn, table: str, column: str, col_type: str):
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column})
    if result.fetchone():
        print(f"  Column '{table}.{column}' already exists — skipping")
    else:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        print(f"  Added column '{table}.{column}' ({col_type})")


def _create_index_if_missing(conn, index_name: str, table: str, columns: str):
    result = conn.execute(text(
        "SELECT indexname FROM pg_indexes WHERE indexname = :n"
    ), {"n": index_name})
    if result.fetchone():
        print(f"  Index '{index_name}' already exists — skipping")
    else:
        conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({columns})"))
        print(f"  Created index '{index_name}' on {table}({columns})")


if __name__ == "__main__":
    run_migration()
