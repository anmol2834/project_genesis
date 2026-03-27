"""
Embedding Service
Generates and stores user context embeddings in Qdrant
Model: all-MiniLM-L6-v2 (384-dim vectors)
"""

from sentence_transformers import SentenceTransformer
from typing import Dict, List
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.vector_db import create_collection, upsert_vectors
from shared.config import get_config

logger = logging.getLogger(__name__)
config = get_config()

_model = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


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
        model = get_embedding_model()
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
                "vector": model.encode(chunk["content"]).tolist(),
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
