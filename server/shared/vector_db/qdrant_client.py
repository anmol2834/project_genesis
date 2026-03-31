"""
Qdrant Vector Database Client
Production-ready client for self-hosted Qdrant
Supports multi-tenant filtering and async operations
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)
from typing import List, Dict, Any, Optional
import logging
import uuid
import threading

from shared.config import get_config

logger = logging.getLogger(__name__)

_qdrant_client: Optional[QdrantClient] = None
_client_lock = threading.Lock()


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        with _client_lock:
            if _qdrant_client is None:
                config = get_config()
                try:
                    _qdrant_client = QdrantClient(
                        url=config.QDRANT_URL,
                        timeout=30,
                        prefer_grpc=False,
                    )
                    logger.info(f"Qdrant client created: {config.QDRANT_URL}")
                except Exception as e:
                    logger.error(f"Failed to create Qdrant client: {e}")
                    raise
    return _qdrant_client


def init_qdrant():
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        logger.info(f"Qdrant initialized successfully. Collections: {len(collections.collections)}")
        return True
    except Exception as e:
        logger.error(f"Qdrant initialization failed: {e}")
        return False


def close_qdrant():
    global _qdrant_client
    if _qdrant_client:
        _qdrant_client.close()
        _qdrant_client = None
        logger.info("Qdrant connections closed")


def check_qdrant_health() -> bool:
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return False


def create_collection(
    collection_name: str,
    vector_size: int = 384,
    distance: str = "Cosine",
) -> bool:
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        if any(col.name == collection_name for col in collections.collections):
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        distance_map = {
            "Cosine": Distance.COSINE, "COSINE": Distance.COSINE,
            "Euclid": Distance.EUCLID, "EUCLID": Distance.EUCLID,
            "Dot": Distance.DOT,       "DOT":    Distance.DOT,
        }
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance_map.get(distance, Distance.COSINE),
            ),
        )
        logger.info(f"Collection '{collection_name}' created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create collection '{collection_name}': {e}")
        return False


def upsert_vectors(
    collection_name: str,
    points: List[Dict[str, Any]],
) -> bool:
    try:
        client = get_qdrant_client()
        qdrant_points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, str(point["id"]))),
                vector=point["vector"],
                payload={**point.get("payload", {}), "original_id": str(point["id"])},
            )
            for point in points
        ]
        client.upsert(collection_name=collection_name, points=qdrant_points)
        logger.info(f"Upserted {len(points)} points to '{collection_name}'")
        return True
    except Exception as e:
        logger.error(f"Failed to upsert vectors to '{collection_name}': {e}")
        return False


def search_vectors(
    collection_name: str,
    query_vector: List[float],
    limit: int = 10,
    user_id: Optional[str] = None,
    score_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic vector search with optional user_id filter.
    Returns list of {id, score, payload} dicts.
    """
    try:
        client = get_qdrant_client()
        query_filter = None
        if user_id:
            query_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            )
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold,
        )
        search_results = [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ]
        logger.info(f"Found {len(search_results)} results in '{collection_name}'")
        return search_results
    except Exception as e:
        logger.error(f"Failed to search in '{collection_name}': {e}")
        return []


def scroll_vectors(
    collection_name: str,
    user_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Scroll (filter-only, no vector similarity) to fetch all points for a user.
    Used as a mandatory fallback when semantic search returns 0 results.

    This guarantees business context is ALWAYS available regardless of
    query embedding quality or score threshold.

    Args:
        collection_name: Qdrant collection name.
        user_id:         Filter by user_id payload field.
        limit:           Max points to return.

    Returns:
        List of {id, score, payload} dicts (score=1.0 for all scroll results).
    """
    try:
        client = get_qdrant_client()
        scroll_filter = None
        if user_id:
            scroll_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            )
        points, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        results = [
            {"id": str(p.id), "score": 1.0, "payload": p.payload}
            for p in points
        ]
        logger.info(
            f"Scroll returned {len(results)} points from '{collection_name}' "
            f"for user {str(user_id)[:8] if user_id else 'all'}"
        )
        return results
    except Exception as e:
        logger.error(f"Failed to scroll '{collection_name}': {e}")
        return []


def delete_vectors(collection_name: str, point_ids: List[str]) -> bool:
    try:
        client = get_qdrant_client()
        uuid_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, str(pid))) for pid in point_ids]
        client.delete(collection_name=collection_name, points_selector=uuid_ids)
        logger.info(f"Deleted {len(point_ids)} points from '{collection_name}'")
        return True
    except Exception as e:
        logger.error(f"Failed to delete vectors from '{collection_name}': {e}")
        return False


def get_collection_info(collection_name: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_qdrant_client()
        info = client.get_collection(collection_name=collection_name)
        return {
            "name": collection_name,
            "points_count": getattr(info, "points_count", None) or getattr(info, "vectors_count", 0),
            "status": str(info.status),
            "config": {
                "vector_size": info.config.params.vectors.size,
                "distance": str(info.config.params.vectors.distance),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get collection info for '{collection_name}': {e}")
        return None


def batch_upsert_vectors(
    collection_name: str,
    points: List[Dict[str, Any]],
    batch_size: int = 100,
) -> bool:
    try:
        for i in range(0, len(points), batch_size):
            if not upsert_vectors(collection_name, points[i:i + batch_size]):
                logger.error(f"Batch upsert failed at index {i}")
                return False
        logger.info(f"Batch upsert completed: {len(points)} points")
        return True
    except Exception as e:
        logger.error(f"Batch upsert failed: {e}")
        return False
