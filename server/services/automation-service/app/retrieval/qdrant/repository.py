"""
Qdrant Repository
=================
Tenant-safe Qdrant operations with mandatory user_id filtering.

CRITICAL: EVERY query MUST enforce tenant isolation.
"""

import logging
from typing import List, Dict, Optional, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

logger = logging.getLogger(__name__)


class QdrantRepository:
    """
    Tenant-safe Qdrant repository.
    
    CRITICAL RULE: ALL queries MUST include user_id filter.
    """
    
    def __init__(
        self,
        qdrant_url: str,
        collection_name: str = "business_context",
        timeout: int = 30
    ):
        """
        Initialize Qdrant repository.
        
        Args:
            qdrant_url: Qdrant server URL
            collection_name: Collection name
            timeout: Request timeout in seconds
        """
        self.client = QdrantClient(url=qdrant_url, timeout=timeout)
        self.collection = collection_name
    
    async def search(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0
    ) -> List[Dict]:
        """
        Vector search with MANDATORY tenant isolation.
        
        Args:
            user_id: Tenant ID (MANDATORY - cannot be None)
            query_vector: Query embedding vector
            limit: Maximum results
            filters: Additional metadata filters
            score_threshold: Minimum similarity score
            
        Returns:
            List of search results with payloads
            
        Raises:
            ValueError: If user_id is not provided
        """
        if not user_id:
            raise ValueError("user_id is MANDATORY for tenant isolation")
        
        try:
            # Build tenant filter
            must_conditions = [
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            ]
            
            # Add additional filters
            if filters:
                must_conditions.extend(self._build_filter_conditions(filters))
            
            qdrant_filter = Filter(must=must_conditions)
            
            # Execute search
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )
            
            # Convert to dict format
            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Qdrant search error: {e}", exc_info=True)
            return []
    
    async def scroll(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        offset: Optional[str] = None
    ) -> List[Dict]:
        """
        Scroll through records with MANDATORY tenant isolation.
        
        Args:
            user_id: Tenant ID (MANDATORY)
            filters: Metadata filters
            limit: Maximum results per page
            offset: Pagination offset
            
        Returns:
            List of records with payloads
            
        Raises:
            ValueError: If user_id is not provided
        """
        if not user_id:
            raise ValueError("user_id is MANDATORY for tenant isolation")
        
        try:
            # Build tenant filter
            must_conditions = [
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            ]
            
            # Add additional filters
            if filters:
                must_conditions.extend(self._build_filter_conditions(filters))
            
            qdrant_filter = Filter(must=must_conditions)
            
            # Execute scroll
            results, next_offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=qdrant_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            # Convert to dict format
            return [
                {
                    "id": record.id,
                    "payload": record.payload
                }
                for record in results
            ]
            
        except Exception as e:
            logger.error(f"Qdrant scroll error: {e}", exc_info=True)
            return []
    
    async def get_by_id(
        self,
        user_id: str,
        point_id: str
    ) -> Optional[Dict]:
        """
        Get single record by ID with tenant validation.
        
        Args:
            user_id: Tenant ID
            point_id: Qdrant point ID
            
        Returns:
            Record payload or None
        """
        if not user_id:
            raise ValueError("user_id is MANDATORY")
        
        try:
            result = self.client.retrieve(
                collection_name=self.collection,
                ids=[point_id],
                with_payload=True,
                with_vectors=False
            )
            
            if not result:
                return None
            
            record = result[0]
            
            # Validate tenant ownership
            if record.payload.get("user_id") != user_id:
                logger.warning(
                    f"Tenant isolation violation: "
                    f"point={point_id} expected={user_id} actual={record.payload.get('user_id')}"
                )
                return None
            
            return {
                "id": record.id,
                "payload": record.payload
            }
            
        except Exception as e:
            logger.error(f"Qdrant get_by_id error: {e}")
            return None
    
    def _build_filter_conditions(
        self,
        filters: Dict[str, Any]
    ) -> List[FieldCondition]:
        """
        Build Qdrant filter conditions from dict.

        BUSINESS-AGNOSTIC: supports any domain via the "attributes" sub-dict.
        Legacy filters (category, chunk_type, price_min, price_max, features)
        are kept for backward compatibility.

        For domain-specific filtering pass:
            filters={"attributes": {"<any_field>": <value>}}
        e.g. {"attributes": {"cuisine": "Italian"}} for a restaurant,
             {"attributes": {"practice_area": "Corporate"}} for a law firm.
        """
        conditions = []

        # Routing filters
        for field_alias in ("category", "chunk_type"):
            if filters.get(field_alias):
                conditions.append(
                    FieldCondition(key="category", match=MatchValue(value=filters[field_alias]))
                )
        if filters.get("department"):
            conditions.append(
                FieldCondition(key="department", match=MatchValue(value=filters["department"]))
            )

        # Dynamic attribute filters — domain-agnostic
        dynamic_attrs = filters.get("attributes", {})
        if isinstance(dynamic_attrs, dict):
            for attr_key, attr_val in dynamic_attrs.items():
                if attr_val is None:
                    continue
                qdrant_field = f"structured_data.{attr_key}"
                if isinstance(attr_val, dict) and ("gte" in attr_val or "lte" in attr_val):
                    range_kwargs = {}
                    if attr_val.get("gte") is not None:
                        range_kwargs["gte"] = float(attr_val["gte"])
                    if attr_val.get("lte") is not None:
                        range_kwargs["lte"] = float(attr_val["lte"])
                    conditions.append(FieldCondition(key=qdrant_field, range=Range(**range_kwargs)))
                elif isinstance(attr_val, (int, float)):
                    conditions.append(
                        FieldCondition(
                            key=qdrant_field,
                            range=Range(gte=float(attr_val), lte=float(attr_val)),
                        )
                    )
                else:
                    conditions.append(
                        FieldCondition(key=qdrant_field, match=MatchValue(value=str(attr_val)))
                    )

        # Legacy range filters
        if "price_min" in filters or "price_max" in filters:
            range_params = {}
            if "price_min" in filters and filters["price_min"] is not None:
                range_params["gte"] = float(filters["price_min"])
            if "price_max" in filters and filters["price_max"] is not None:
                range_params["lte"] = float(filters["price_max"])
            if range_params:
                conditions.append(FieldCondition(key="price", range=Range(**range_params)))

        # Legacy array contains filters
        if "features" in filters and filters["features"]:
            for feature in filters["features"]:
                if feature:
                    conditions.append(
                        FieldCondition(key="features", match=MatchValue(value=feature))
                    )

        return conditions
    
    async def count(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count records with tenant isolation.
        
        Args:
            user_id: Tenant ID
            filters: Optional filters
            
        Returns:
            Count of matching records
        """
        if not user_id:
            raise ValueError("user_id is MANDATORY")
        
        try:
            # Build filter
            must_conditions = [
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            ]
            
            if filters:
                must_conditions.extend(self._build_filter_conditions(filters))
            
            qdrant_filter = Filter(must=must_conditions)
            
            # Count
            result = self.client.count(
                collection_name=self.collection,
                count_filter=qdrant_filter
            )
            
            return result.count
            
        except Exception as e:
            logger.error(f"Qdrant count error: {e}")
            return 0
