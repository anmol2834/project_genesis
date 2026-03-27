"""
Celery Tasks for Embedding Generation
Background task: fetch user from DB, generate vectors, store in Qdrant
Uses synchronous DB access — Celery workers are sync, no asyncio needed.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from celery.exceptions import MaxRetriesExceededError
from shared.celery import get_celery_app
from shared.logger import get_logger

from services.embedding_service import generate_user_embeddings

logger = get_logger(__name__)
celery_app = get_celery_app()


def _fetch_user_sync(user_id: str):
    """
    Fetch user from PostgreSQL using a synchronous psycopg2 connection.
    Celery workers are sync processes — no event loop, no asyncpg.
    Creates a fresh connection per task to avoid pool/loop conflicts.
    """
    from sqlalchemy import create_engine, text
    from shared.config import get_config

    config = get_config()

    # Convert asyncpg URL → psycopg2 URL
    sync_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    connect_args = {}
    if "rds.amazonaws.com" in sync_url:
        connect_args["sslmode"] = "require"

    engine = create_engine(sync_url, connect_args=connect_args, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, business_name, business_type, industry,
                           country, business_description, target_audience,
                           communication_tone, use_cases, created_at
                    FROM users WHERE id = :uid
                """),
                {"uid": user_id},
            ).fetchone()
    finally:
        engine.dispose()

    return row


@celery_app.task(
    bind=True,
    name="auth.create_user_embedding",
    max_retries=5,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
)
def create_user_embedding(self, user_id: str):
    """
    Generate and store Qdrant embeddings for a user.
    Fully synchronous — no asyncio, no event loop issues.
    Retries up to 5 times with exponential backoff on failure.
    """
    logger.info(f"Embedding task started for user {user_id} (attempt {self.request.retries + 1})")

    try:
        row = _fetch_user_sync(user_id)
    except Exception as e:
        logger.error(f"DB fetch failed for user {user_id}: {e}", exc_info=True)
        raise self.retry(exc=e)

    if row is None:
        # User doesn't exist — no point retrying
        logger.error(f"User {user_id} not found in DB, skipping embedding")
        return {"success": False, "message": f"User {user_id} not found", "user_id": user_id}

    user_data = {
        "user_id":            user_id,
        "business_name":      row.business_name or "",
        "business_type":      row.business_type or "",
        "industries":         row.industry or [],
        "country":            row.country or "",
        "business_description": row.business_description or "",
        "target_audience":    row.target_audience or "",
        "communication_tone": row.communication_tone or "professional",
        "use_cases":          row.use_cases or [],
        "created_at":         row.created_at.isoformat() if row.created_at else "",
    }

    try:
        success = generate_user_embeddings(user_id, user_data)
    except Exception as e:
        logger.error(f"Embedding generation failed for user {user_id}: {e}", exc_info=True)
        raise self.retry(exc=e)

    if not success:
        logger.error(f"Embedding returned False for user {user_id}, retrying")
        raise self.retry(exc=Exception("generate_user_embeddings returned False"))

    logger.info(f"Embedding task completed for user {user_id}")
    return {"success": True, "message": "Embeddings generated successfully", "user_id": user_id}
