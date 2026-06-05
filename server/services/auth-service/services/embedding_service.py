"""
Embedding Service
Generates and stores user context embeddings in Qdrant.
Model: nomic-embed-text via Ollama (dim=384, Cosine)

Falls back to all-MiniLM-L6-v2 (SentenceTransformers) if Ollama is unavailable.
Both produce dim=384 — Qdrant collection stays consistent.
"""

from typing import Dict, List
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.vector_db import create_collection, upsert_vectors
from shared.config import get_config

logger = logging.getLogger(__name__)
config = get_config()

_OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL      = "nomic-embed-text"
_EMBED_DIM        = 768

# SentenceTransformers fallback — must also be dim=768
_st_model = None


def _embed_text(text: str) -> List[float]:
    """
    Embed text using nomic-embed-text via Ollama (dim=768).
    Falls back to all-mpnet-base-v2 (SentenceTransformers, dim=768) if Ollama unavailable.
    """
    # Primary: Ollama nomic-embed-text
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
            elif vec:
                logger.warning("nomic-embed-text returned dim=%d, expected %d", len(vec), _EMBED_DIM)
    except Exception as e:
        logger.debug("Ollama embed unavailable (%s) — using SentenceTransformers fallback", e)

    # Fallback: all-mpnet-base-v2 (dim=768, matches nomic-embed-text)
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-mpnet-base-v2")
        logger.info("Embedding fallback: all-mpnet-base-v2 loaded (dim=768)")
    return _st_model.encode(text).tolist()


def create_embedding_chunks(user_data: Dict) -> List[Dict]:
    """Build structured text chunks from user business context."""
    chunks = []

    business_core = (
        f"Business Name: {user_data['business_name']}\n"
        f"Business Type: {user_data['business_type']}\n"
        f"Industry: {', '.join(user_data.get('industries', []))}\n"
        f"Country: {user_data['country']}\n"
        f"Description: {user_data['business_description']}"
    )
    chunks.append({"type": "business_core", "content": business_core})

    if user_data.get("target_audience"):
        chunks.append({
            "type": "audience",
            "content": f"Target Audience: {user_data['target_audience']}"
        })

    chunks.append({
        "type": "tone",
        "content": f"Communication Tone: {user_data['communication_tone']}"
    })

    chunks.append({
        "type": "use_case",
        "content": f"Primary Use Cases: {', '.join(user_data['use_cases'])}"
    })

    chunks.append({
        "type": "instruction",
        "content": (
            f"You are an AI email assistant for {user_data['business_name']}, "
            f"a {user_data['business_type']} business. "
            f"Your communication style is {user_data['communication_tone']}. "
            f"You help with: {', '.join(user_data['use_cases'])}. "
            f"Always maintain context about: {user_data['business_description']}"
        )
    })

    return chunks


def generate_user_embeddings(user_id: str, user_data: Dict) -> bool:
    """
    Generate embeddings for all user context chunks and store in Qdrant.
    Returns True on success, False on any failure.
    """
    try:
        chunks = create_embedding_chunks(user_data)

        # Ensure collection exists before upserting
        create_collection(
            collection_name=config.QDRANT_COLLECTION,
            vector_size=config.QDRANT_VECTOR_SIZE,
            distance=config.QDRANT_DISTANCE_METRIC,
        )

        vectors = [
            {
                "id": f"{user_id}_{chunk['type']}",
                "vector": _embed_text(chunk["content"]),
                "payload": {
                    "user_id": user_id,
                    "type": chunk["type"],
                    "content": chunk["content"],
                    "created_at": user_data.get("created_at", ""),
                },
            }
            for chunk in chunks
        ]

        success = upsert_vectors(config.QDRANT_COLLECTION, vectors)

        if not success:
            logger.error(f"Failed to store embeddings for {user_id}")

        return success

    except Exception as e:
        logger.error(f"Embedding error for {user_id}: {e}")
        return False
