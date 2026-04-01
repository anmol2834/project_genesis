"""
Migration: Create Data Ingestion Tables
Run once to create:
  - user_data_sources
  - user_data_entries
  - user_data_versions

Usage:
  cd server/services/user-service
  python migrations/create_data_tables.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text, inspect
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

    # Import models to register them with Base
    from shared.database.postgres import Base
    from models.data_entry import UserDataSource, UserDataEntry, UserDataVersion

    inspector = inspect(engine)
    existing = inspector.get_table_names()

    tables_to_create = []
    for table_name in ["user_data_sources", "user_data_entries", "user_data_versions"]:
        if table_name in existing:
            print(f"  Table '{table_name}' already exists — skipping")
        else:
            tables_to_create.append(table_name)

    if tables_to_create:
        print(f"Creating tables: {tables_to_create}")
        Base.metadata.create_all(
            engine,
            tables=[
                Base.metadata.tables[t]
                for t in tables_to_create
                if t in Base.metadata.tables
            ],
        )
        print("Tables created successfully.")
    else:
        print("All tables already exist. Nothing to do.")

    engine.dispose()
    print("Migration complete.")


if __name__ == "__main__":
    run_migration()
