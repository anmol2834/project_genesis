"""Shared vector database module"""

from .qdrant_client import (
    get_qdrant_client,
    init_qdrant,
    close_qdrant,
    check_qdrant_health,
    create_collection,
    upsert_vectors,
    search_vectors,
    scroll_vectors,
    delete_vectors,
    get_collection_info,
    batch_upsert_vectors,
)

__all__ = [
    "get_qdrant_client",
    "init_qdrant",
    "close_qdrant",
    "check_qdrant_health",
    "create_collection",
    "upsert_vectors",
    "search_vectors",
    "scroll_vectors",
    "delete_vectors",
    "get_collection_info",
    "batch_upsert_vectors",
]
