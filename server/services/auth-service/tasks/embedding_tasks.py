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
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from services.embedding_service import generate_user_embeddings

logger = get_logger(__name__)
celery_app = get_celery_app()

_engine = None


def get_sync_engine():
    """Reusable sync engine with NullPool to prevent connection leaks"""
    global _engine
    if _engine is None:
        from shared.config import get_config
        config = get_config()
        sync_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        connect_args = {}
        if "rds.amazonaws.com" in sync_url:
            connect_args["sslmode"] = "require"
        _engine = create_engine(sync_url, connect_args=connect_args, poolclass=NullPool)
    return _engine


def _fetch_user_sync(user_id: str):
    """Fetch user using reusable engine to prevent connection leaks"""
    engine = get_sync_engine()
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
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 5}
)
def create_user_embedding(self, user_id: str):
    """
    Generate and store Qdrant embeddings for a user.
    Fully synchronous — no asyncio, no event loop issues.
    Retries up to 5 times with exponential backoff on failure.
    """
    try:
        row = _fetch_user_sync(user_id)
    except Exception as e:
        logger.error(f"DB fetch failed for {user_id}: {e}")
        raise

    if row is None:
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
        logger.error(f"Embedding failed for {user_id}: {e}")
        raise

    if not success:
        logger.error(f"Embedding returned False for {user_id}")
        raise Exception("Embedding generation failed")

    print(f"[SUCCESS] Embeddings created for user {user_id}")
    return {"success": True, "message": "Embeddings generated", "user_id": user_id}
