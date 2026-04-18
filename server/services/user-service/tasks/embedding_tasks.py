"""
Celery Tasks for User Profile Embedding Updates
Smart partial update — only regenerates affected vector chunks
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from celery.exceptions import MaxRetriesExceededError
from shared.celery import get_celery_app
from shared.logger import get_logger
from shared.config import get_config
from shared.vector_db import upsert_vectors
from typing import List, Dict
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = get_logger(__name__)
celery_app = get_celery_app()
config = get_config()

_st_model  = None   # SentenceTransformers fallback
_engine    = None

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL     = "nomic-embed-text"
_EMBED_DIM       = 768


def _embed_text(text: str) -> List[float]:
    """
    Embed using nomic-embed-text via Ollama (dim=768).
    Falls back to all-mpnet-base-v2 (SentenceTransformers, dim=768) if Ollama unavailable.
    """
    try:
        import httpx
        resp = httpx.post(
            f"{_OLLAMA_BASE_URL}/api/embeddings",
            json={"model": _EMBED_MODEL, "prompt": text[:512]},
            timeout=10.0,
        )
        if resp.status_code == 200:
            vec = resp.json().get("embedding", [])
            if vec and len(vec) == _EMBED_DIM:
                return vec
    except Exception:
        pass

    # Fallback: all-mpnet-base-v2 (dim=768, matches nomic-embed-text)
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-mpnet-base-v2")
        logger.info("Embedding fallback: all-mpnet-base-v2 loaded (dim=768)")
    return _st_model.encode(text).tolist()


def get_embedding_model():
    """Backward-compat shim — returns None (we use _embed_text directly)."""
    return None


def get_sync_engine():
    """Reusable sync engine with NullPool to prevent connection leaks"""
    global _engine
    if _engine is None:
        sync_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        connect_args = {}
        if "rds.amazonaws.com" in sync_url:
            connect_args["sslmode"] = "require"
        _engine = create_engine(sync_url, connect_args=connect_args, poolclass=NullPool)
    return _engine


FIELD_TO_VECTOR_MAP = {
    "business_name": ["business_core", "instruction"],
    "business_type": ["business_core", "instruction"],
    "industries": ["business_core"],
    "country": ["business_core"],
    "business_description": ["business_core", "instruction"],
    "target_audience": ["audience"],
    "communication_tone": ["tone", "instruction"],
    "use_cases": ["use_case", "instruction"],
}


def get_affected_vector_types(changed_fields: List[str]) -> set:
    affected = set()
    for field in changed_fields:
        if field in FIELD_TO_VECTOR_MAP:
            affected.update(FIELD_TO_VECTOR_MAP[field])
    return affected


def _fetch_user_sync(user_id: str):
    """Fetch user using reusable engine to prevent connection leaks"""
    engine = get_sync_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, business_name, business_type, industry,
                       country, business_description, target_audience,
                       communication_tone, use_cases, created_at, updated_at
                FROM users WHERE id = :uid
            """),
            {"uid": user_id},
        ).fetchone()
    return row


def build_vector_chunk(chunk_type: str, user_data: Dict) -> Dict:
    if chunk_type == "business_core":
        content = (
            f"Business Name: {user_data['business_name']}\n"
            f"Business Type: {user_data['business_type']}\n"
            f"Industry: {', '.join(user_data.get('industries', []))}\n"
            f"Country: {user_data['country']}\n"
            f"Description: {user_data['business_description']}"
        )
    elif chunk_type == "audience":
        content = f"Target Audience: {user_data.get('target_audience', '')}"
    elif chunk_type == "tone":
        content = f"Communication Tone: {user_data['communication_tone']}"
    elif chunk_type == "use_case":
        content = f"Primary Use Cases: {', '.join(user_data['use_cases'])}"
    elif chunk_type == "instruction":
        content = (
            f"You are an AI email assistant for {user_data['business_name']}, "
            f"a {user_data['business_type']} business. "
            f"Your communication style is {user_data['communication_tone']}. "
            f"You help with: {', '.join(user_data['use_cases'])}. "
            f"Always maintain context about: {user_data['business_description']}"
        )
    else:
        raise ValueError(f"Unknown chunk type: {chunk_type}")
    
    return {"type": chunk_type, "content": content}


@celery_app.task(
    bind=True,
    name="user.update_user_embedding",
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
    ignore_result=True,
)
def update_user_embedding(self, user_id: str, changed_fields: List[str]):
    """
    Smart partial vector update — only regenerates affected chunks.
    Celery task wrapper — delegates to run_embedding_update_sync.
    """
    run_embedding_update_sync(user_id, changed_fields)


def run_embedding_update_sync(user_id: str, changed_fields: List[str]) -> dict:
    """
    Core embedding update logic — callable directly (FastAPI BackgroundTasks)
    or via Celery task. No Redis dependency.
    """
    logger.info(f"Partial embedding update for {user_id}, fields: {changed_fields}")
    
    try:
        row = _fetch_user_sync(user_id)
    except Exception as e:
        logger.error(f"DB fetch failed for {user_id}: {e}")
        raise
    
    if row is None:
        logger.error(f"User {user_id} not found")
        return {"success": False, "message": f"User {user_id} not found"}
    
    user_data = {
        "user_id": user_id,
        "business_name": row.business_name or "",
        "business_type": row.business_type or "",
        "industries": row.industry or [],
        "country": row.country or "",
        "business_description": row.business_description or "",
        "target_audience": row.target_audience or "",
        "communication_tone": row.communication_tone or "professional",
        "use_cases": row.use_cases or [],
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }
    
    affected_types = get_affected_vector_types(changed_fields)
    
    if not affected_types:
        logger.info(f"No AI context fields changed for {user_id}")
        return {"success": True, "message": "No vector update needed"}
    
    logger.info(f"Affected vector types: {affected_types}")
    
    try:
        chunks_to_update = [build_vector_chunk(t, user_data) for t in affected_types]

        vectors = [
            {
                "id": f"{user_id}_{chunk['type']}",
                "vector": _embed_text(chunk["content"]),
                "payload": {
                    "user_id": user_id,
                    "type": chunk["type"],
                    "content": chunk["content"],
                    "created_at": user_data.get("created_at", ""),
                    "updated_at": user_data.get("updated_at", ""),
                    "original_id": f"{user_id}_{chunk['type']}",
                },
            }
            for chunk in chunks_to_update
        ]
        
        success = upsert_vectors(config.QDRANT_COLLECTION, vectors)
        
        if not success:
            logger.error(f"Qdrant upsert failed for {user_id}")
            raise Exception("Qdrant upsert failed")
        
        logger.info(f"Updated {len(vectors)} vectors for {user_id}")
        
        return {
            "success": True,
            "message": "Embeddings updated",
            "user_id": user_id,
            "affected_types": list(affected_types),
            "vectors_updated": len(vectors),
        }
    
    except Exception as e:
        logger.error(f"Embedding update failed: {e}")
        raise
