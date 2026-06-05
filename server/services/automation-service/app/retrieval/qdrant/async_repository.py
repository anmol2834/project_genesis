"""
Async Qdrant Repository
========================
Wraps AsyncQdrantClient with the same interface that all retrieval engines
expect: .search(user_id, query_vector, ...) and .scroll(user_id, filters, ...).

Why this exists:
  ResourceManager.get_qdrant() returns a raw AsyncQdrantClient.
  All retrieval engines (L4-L6) call self.qdrant.search(user_id=...) and
  self.qdrant.scroll(user_id=...) — these are NOT methods on AsyncQdrantClient.
  AsyncQdrantClient requires collection_name as its first positional argument.

  This adapter bridges that gap: collection_name is baked in at construction,
  tenant isolation (user_id filter) is enforced on every query, and the
  calling engines need zero changes.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

logger = logging.getLogger(__name__)


class AsyncQdrantRepository:
    """
    Tenant-safe async Qdrant repository.

    Drop-in replacement for QdrantRepository that works with AsyncQdrantClient.
    Collection name is fixed at construction — engines never pass it.
    Every query enforces user_id isolation via a Qdrant filter.
    """

    def __init__(self, client: AsyncQdrantClient, collection_name: str = "business_context"):
        self._client = client
        self._collection = collection_name

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0,
    ) -> List[Dict]:
        """Vector search with mandatory tenant isolation."""
        if not user_id:
            raise ValueError("user_id is MANDATORY for tenant isolation")

        must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if filters:
            must.extend(self._build_conditions(filters))

        try:
            results = await self._client.search(
                collection_name=self._collection,
                query_vector=query_vector,
                query_filter=Filter(must=must),
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )
            return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]
        except Exception as e:
            logger.error("AsyncQdrantRepository.search error: %s", e)
            return []

    # ── Scroll ────────────────────────────────────────────────────────────────

    async def scroll(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        offset: Optional[str] = None,
    ) -> List[Dict]:
        """Scroll through records with mandatory tenant isolation."""
        if not user_id:
            raise ValueError("user_id is MANDATORY for tenant isolation")

        must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if filters:
            must.extend(self._build_conditions(filters))

        try:
            results, _ = await self._client.scroll(
                collection_name=self._collection,
                scroll_filter=Filter(must=must),
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            return [{"id": r.id, "payload": r.payload} for r in results]
        except Exception as e:
            logger.error("AsyncQdrantRepository.scroll error: %s", e)
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_conditions(self, filters: Dict[str, Any]) -> List[FieldCondition]:
        conditions: List[FieldCondition] = []

        for field in ("category", "chunk_type", "department"):
            if filters.get(field):
                conditions.append(
                    FieldCondition(key=field, match=MatchValue(value=filters[field]))
                )

        range_params: Dict[str, Any] = {}
        if "price_min" in filters:
            range_params["gte"] = filters["price_min"]
        if "price_max" in filters:
            range_params["lte"] = filters["price_max"]
        if range_params:
            conditions.append(FieldCondition(key="price", range=Range(**range_params)))

        for feature in filters.get("features", []):
            conditions.append(
                FieldCondition(key="features", match=MatchValue(value=feature))
            )

        return conditions
