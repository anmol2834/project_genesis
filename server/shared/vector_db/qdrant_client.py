"""
Qdrant Vector Database Client
Production-ready client for self-hosted Qdrant
Supports multi-tenant filtering and async operations
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Dict, Any, Optional
import logging
import uuid

from shared.config import get_config

logger = logging.getLogger(__name__)

# Global Qdrant client instance
_qdrant_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """
    Get or create Qdrant client
    Thread-safe singleton pattern
    """
    global _qdrant_client
    
    if _qdrant_client is None:
        config = get_config()
        
        _qdrant_client = QdrantClient(
            url=config.QDRANT_URL,
            timeout=30,
            prefer_grpc=False,  # Use REST API for simplicity
        )
        
        logger.info(f"Qdrant client created: {config.QDRANT_URL}")
    
    return _qdrant_client


def init_qdrant():
    """
    Initialize Qdrant connection
    Call this on application startup
    """
    try:
        client = get_qdrant_client()
        
        # Test connection
        collections = client.get_collections()
        
        logger.info(f"Qdrant initialized successfully. Collections: {len(collections.collections)}")
        return True
    except Exception as e:
        logger.error(f"Qdrant initialization failed: {e}")
        return False


def close_qdrant():
    """
    Close Qdrant connections
    Call this on application shutdown
    """
    global _qdrant_client
    
    if _qdrant_client:
        _qdrant_client.close()
        _qdrant_client = None
        logger.info("Qdrant connections closed")


def check_qdrant_health() -> bool:
    """
    Check Qdrant connection health
    Used for health check endpoints
    """
    try:
        client = get_qdrant_client()
        # Use root endpoint for health check
        client.get_collections()
        return True
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return False


def create_collection(
    collection_name: str,
    vector_size: int = 384,
    distance: str = "Cosine"
) -> bool:
    """
    Create a new collection in Qdrant
    
    Args:
        collection_name: Name of the collection
        vector_size: Dimension of vectors (default: 384 for sentence-transformers)
        distance: Distance metric (COSINE, EUCLID, DOT)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_qdrant_client()
        
        # Check if collection exists
        collections = client.get_collections()
        if any(col.name == collection_name for col in collections.collections):
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        
        # Map string distance metric to enum
        distance_map = {
            "Cosine": Distance.COSINE,
            "COSINE": Distance.COSINE,
            "Euclid": Distance.EUCLID,
            "EUCLID": Distance.EUCLID,
            "Dot": Distance.DOT,
            "DOT": Distance.DOT,
        }
        distance_enum = distance_map.get(distance, Distance.COSINE)

        # Create collection
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance_enum
            )
        )
        
        logger.info(f"Collection '{collection_name}' created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create collection '{collection_name}': {e}")
        return False


def upsert_vectors(
    collection_name: str,
    points: List[Dict[str, Any]]
) -> bool:
    """
    Insert or update vectors in collection
    
    Args:
        collection_name: Name of the collection
        points: List of points with structure:
            [
                {
                    "id": "unique_id",
                    "vector": [0.1, 0.2, ...],
                    "payload": {"user_id": "123", "text": "..."}
                }
            ]
    
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_qdrant_client()
        
        # Convert to PointStruct — Qdrant requires int or UUID point IDs
        qdrant_points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, str(point["id"]))),
                vector=point["vector"],
                payload={**point.get("payload", {}), "original_id": str(point["id"])}
            )
            for point in points
        ]
        
        # Upsert points
        client.upsert(
            collection_name=collection_name,
            points=qdrant_points
        )
        
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
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in collection
    
    Args:
        collection_name: Name of the collection
        query_vector: Query vector
        limit: Maximum number of results
        user_id: Filter by user_id (multi-tenant support)
        score_threshold: Minimum similarity score
    
    Returns:
        List of search results with structure:
            [
                {
                    "id": "unique_id",
                    "score": 0.95,
                    "payload": {"user_id": "123", "text": "..."}
                }
            ]
    """
    try:
        client = get_qdrant_client()
        
        # Build filter for multi-tenant support
        query_filter = None
        if user_id:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )
        
        # Search
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold
        )
        
        # Convert to dict
        search_results = [
            {
                "id": result.id,
                "score": result.score,
                "payload": result.payload
            }
            for result in results
        ]
        
        logger.info(f"Found {len(search_results)} results in '{collection_name}'")
        return search_results
    except Exception as e:
        logger.error(f"Failed to search in '{collection_name}': {e}")
        return []


def delete_vectors(
    collection_name: str,
    point_ids: List[str]
) -> bool:
    """
    Delete vectors from collection
    
    Args:
        collection_name: Name of the collection
        point_ids: List of point IDs to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_qdrant_client()
        
        # Convert string IDs to the same UUID5 used during upsert
        uuid_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, str(pid))) for pid in point_ids]
        client.delete(
            collection_name=collection_name,
            points_selector=uuid_ids
        )
        
        logger.info(f"Deleted {len(point_ids)} points from '{collection_name}'")
        return True
    except Exception as e:
        logger.error(f"Failed to delete vectors from '{collection_name}': {e}")
        return False


def get_collection_info(collection_name: str) -> Optional[Dict[str, Any]]:
    """
    Get collection information
    
    Args:
        collection_name: Name of the collection
    
    Returns:
        Collection info dict or None
    """
    try:
        client = get_qdrant_client()
        
        info = client.get_collection(collection_name=collection_name)
        
        return {
            "name": collection_name,
            "points_count": getattr(info, "points_count", None) or getattr(info, "vectors_count", 0),
            "status": str(info.status),
            "config": {
                "vector_size": info.config.params.vectors.size,
                "distance": str(info.config.params.vectors.distance)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get collection info for '{collection_name}': {e}")
        return None


def batch_upsert_vectors(
    collection_name: str,
    points: List[Dict[str, Any]],
    batch_size: int = 100
) -> bool:
    """
    Batch insert vectors for better performance
    
    Args:
        collection_name: Name of the collection
        points: List of points
        batch_size: Number of points per batch
    
    Returns:
        True if successful, False otherwise
    """
    try:
        total_points = len(points)
        
        for i in range(0, total_points, batch_size):
            batch = points[i:i + batch_size]
            success = upsert_vectors(collection_name, batch)
            
            if not success:
                logger.error(f"Batch upsert failed at index {i}")
                return False
            
            logger.info(f"Batch {i // batch_size + 1}: Upserted {len(batch)} points")
        
        logger.info(f"Batch upsert completed: {total_points} points")
        return True
    except Exception as e:
        logger.error(f"Batch upsert failed: {e}")
        return False
