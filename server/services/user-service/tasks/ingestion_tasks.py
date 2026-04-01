"""
Celery Tasks — Data Ingestion
Background tasks for async file processing and source management.

Tasks:
  user.process_file_upload    — Process CSV/Excel after upload
  user.process_sheets_webhook — Process Google Sheets webhook payload
  user.delete_source_data     — Delete all data for a source (Postgres + Qdrant)
"""

import sys
import os
import logging
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.celery import get_celery_app
from shared.config import get_config
from shared.logger import get_logger

logger = get_logger(__name__)
celery_app = get_celery_app()
config = get_config()


# ── Task: process file upload ─────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="user.process_file_upload",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    ignore_result=False,
)
def process_file_upload(
    self,
    source_id: str,
    user_id: str,
    source_type: str,
    rows: List[Dict[str, Any]],
    headers: List[str],
) -> Dict[str, Any]:
    """
    Process a parsed file upload asynchronously.
    Called after the file has been parsed and the source record created.

    Args:
        source_id:   UUID of the UserDataSource record
        user_id:     UUID of the owning user
        source_type: "csv_import" | "excel_import"
        rows:        Parsed rows as list of dicts
        headers:     Ordered list of column headers

    Returns:
        {accepted, rejected, errors, entry_ids}
    """
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import NullPool

    logger.info(f"[process_file_upload] source={source_id} rows={len(rows)}")

    try:
        _update_source_status(source_id, "processing")

        # Run async pipeline in sync context
        result = asyncio.run(_run_pipeline_sync(source_id, user_id, source_type, rows, headers))

        _update_source_status(source_id, "active", ingestion_log=result)
        logger.info(f"[process_file_upload] done: {result['accepted']} accepted, {result['rejected']} rejected")
        return result

    except Exception as exc:
        logger.error(f"[process_file_upload] failed: {exc}", exc_info=True)
        _update_source_status(source_id, "error", last_error=str(exc))
        raise self.retry(exc=exc)


# ── Task: process Google Sheets webhook ──────────────────────────────────────

@celery_app.task(
    bind=True,
    name="user.process_sheets_webhook",
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
    ignore_result=False,
)
def process_sheets_webhook(
    self,
    source_id: str,
    user_id: str,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Process rows received from a Google Sheets webhook.

    Args:
        source_id: UUID of the UserDataSource (google_sheets type)
        user_id:   UUID of the owning user
        rows:      Normalized rows from the webhook payload
    """
    import asyncio

    logger.info(f"[process_sheets_webhook] source={source_id} rows={len(rows)}")

    try:
        _update_source_status(source_id, "syncing")

        headers = list(rows[0].keys()) if rows else []
        result = asyncio.run(_run_pipeline_sync(source_id, user_id, "google_sheets", rows, headers))

        _update_source_status(source_id, "active", ingestion_log=result)
        logger.info(f"[process_sheets_webhook] done: {result['accepted']} accepted")
        return result

    except Exception as exc:
        logger.error(f"[process_sheets_webhook] failed: {exc}", exc_info=True)
        _update_source_status(source_id, "error", last_error=str(exc))
        raise self.retry(exc=exc)


# ── Task: delete source data ──────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="user.delete_source_data",
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
    ignore_result=False,
)
def delete_source_data(
    self,
    source_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Hard-delete all data for a source from both PostgreSQL and Qdrant.
    Called after the source record itself has been soft-deleted.
    """
    import asyncio

    logger.info(f"[delete_source_data] source={source_id} user={user_id}")

    try:
        result = asyncio.run(_delete_source_async(source_id, user_id))
        logger.info(f"[delete_source_data] done: {result}")
        return result
    except Exception as exc:
        logger.error(f"[delete_source_data] failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ── Internal async helpers ────────────────────────────────────────────────────

async def _run_pipeline_sync(
    source_id: str,
    user_id: str,
    source_type: str,
    rows: List[Dict[str, Any]],
    headers: List[str],
) -> Dict[str, Any]:
    """Run the ingestion pipeline inside an async context."""
    from shared.database.postgres import get_session_factory
    from services.ingestion.pipeline import run_file_pipeline

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            result = await run_file_pipeline(
                rows=rows,
                headers=headers,
                source_id=source_id,
                user_id=user_id,
                source_type=source_type,
                session=session,
            )
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def _delete_source_async(source_id: str, user_id: str) -> Dict[str, Any]:
    """Delete all entries for a source from Postgres + Qdrant."""
    from shared.database.postgres import get_session_factory
    from services.ingestion.embedding_service import delete_source_entries
    from models.data_entry import UserDataEntry, UserDataSource
    from sqlalchemy import update, delete as sa_delete
    import asyncio

    session_factory = get_session_factory()
    async with session_factory() as session:
        # Count entries first
        from sqlalchemy import select, func
        count_result = await session.execute(
            select(func.count(UserDataEntry.id)).where(
                UserDataEntry.source_id == source_id,
                UserDataEntry.user_id == user_id,
            )
        )
        entry_count = count_result.scalar() or 0

        # Delete from Qdrant first (uses source_id filter)
        vectors_deleted = await asyncio.to_thread(delete_source_entries, user_id, source_id)

        # Hard delete entries from Postgres
        await session.execute(
            sa_delete(UserDataEntry).where(
                UserDataEntry.source_id == source_id,
                UserDataEntry.user_id == user_id,
            )
        )

        # Delete the source record itself
        await session.execute(
            sa_delete(UserDataSource).where(
                UserDataSource.id == source_id,
                UserDataSource.user_id == user_id,
            )
        )

        await session.commit()

    return {
        "source_id":       source_id,
        "entries_deleted": entry_count,
        "vectors_deleted": vectors_deleted,
    }


# ── Sync DB helper (for status updates from sync context) ────────────────────

def _update_source_status(
    source_id: str,
    status: str,
    last_error: str = None,
    ingestion_log: Dict = None,
) -> None:
    """Update source status synchronously (used inside Celery tasks)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    sync_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    connect_args = {}
    if "rds.amazonaws.com" in sync_url:
        connect_args["sslmode"] = "require"

    engine = create_engine(sync_url, connect_args=connect_args, poolclass=NullPool)
    try:
        with engine.begin() as conn:
            params: Dict[str, Any] = {
                "status":    status,
                "source_id": source_id,
            }
            set_clauses = ["status = :status", "ingestion_status = :status"]

            if last_error is not None:
                set_clauses.append("last_error = :last_error")
                params["last_error"] = last_error

            if ingestion_log is not None:
                import json
                set_clauses.append("ingestion_log = :ingestion_log")
                params["ingestion_log"] = json.dumps(ingestion_log)

            sql = f"UPDATE user_data_sources SET {', '.join(set_clauses)} WHERE id = :source_id"
            conn.execute(text(sql), params)
    except Exception as e:
        logger.error(f"Failed to update source status: {e}")
    finally:
        engine.dispose()
