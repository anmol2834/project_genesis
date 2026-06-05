"""
L3 Metadata Search Engine
==========================
Structured field filtering on categories, prices, features, departments.

Performance: <50ms
"""

import logging
from typing import List, Dict, Optional, Any

from app.retrieval.schemas import RetrievedChunk, ChunkType, RetrievalSource

logger = logging.getLogger(__name__)


class MetadataSearchEngine:
    """
    L3 metadata filtering on structured fields.
    
    Filters:
    - category (drones, cameras, training)
    - price range (min/max)
    - features (4K, GPS, thermal)
    - department (sales, support)
    - availability (in_stock, pre_order)
    """
    
    def __init__(self, qdrant_repository):
        """
        Initialize metadata search engine.
        
        Args:
            qdrant_repository: Qdrant repository for vector DB access
        """
        self.qdrant = qdrant_repository
    
    async def search_metadata(
        self,
        user_id: str,
        filters: Dict[str, Any],
        top_k: int = 10
    ) -> List[RetrievedChunk]:
        """
        Search by metadata filters.
        
        Args:
            user_id: Tenant ID (mandatory)
            filters: Metadata filters
                {
                    "category": "drones",
                    "price_min": 1000,
                    "price_max": 50000,
                    "features": ["4K", "GPS"],
                    "chunk_type": "product_service"
                }
            top_k: Maximum results
            
        Returns:
            List of matching chunks
        """
        if not user_id or not filters:
            return []
        
        try:
            # Scroll Qdrant with metadata filters
            # Note: user_id filter is enforced by repository
            results = await self.qdrant.scroll(
                user_id=user_id,
                filters=filters,
                limit=top_k
            )
            
            # Convert to RetrievedChunk
            chunks = []
            for result in results:
                payload = result.get("payload", {})
                
                # Calculate metadata match score
                score = self._calculate_metadata_score(payload, filters)
                
                chunk = RetrievedChunk(
                    content=payload.get("content", ""),
                    score=score,
                    chunk_type=ChunkType(payload.get("chunk_type", "general")),
                    chunk_id=payload.get("chunk_id", str(result.get("id", ""))),
                    source=RetrievalSource.L3_METADATA,
                    user_id=user_id,
                    metadata=payload,
                    retrieval_layer="L3"
                )
                chunks.append(chunk)
            
            # Sort by score
            chunks.sort(key=lambda c: c.score, reverse=True)
            
            logger.info(f"L3 metadata: filters={filters} found={len(chunks)}")
            
            return chunks[:top_k]
            
        except Exception as e:
            logger.error(f"L3 metadata search error: {e}")
            return []
    
    def _calculate_metadata_score(
        self,
        payload: Dict,
        filters: Dict
    ) -> float:
        """
        Calculate match score based on metadata filters.
        
        Score components:
        - Category match: +0.5
        - Price in range: +0.3
        - Features match: +0.2 per feature
        """
        score = 0.0
        
        # Category match
        if "category" in filters:
            if payload.get("category", "").lower() == filters["category"].lower():
                score += 0.5
        
        # Price range match
        price = payload.get("price")
        if price:
            in_range = True
            
            if "price_min" in filters and price < filters["price_min"]:
                in_range = False
            
            if "price_max" in filters and price > filters["price_max"]:
                in_range = False
            
            if in_range:
                score += 0.3
        
        # Features match
        if "features" in filters:
            required_features = set(f.lower() for f in filters["features"])
            chunk_features = set(f.lower() for f in payload.get("features", []))
            
            matched_features = required_features & chunk_features
            feature_match_ratio = len(matched_features) / len(required_features) if required_features else 0
            
            score += 0.2 * feature_match_ratio
        
        # Normalize to [0, 1]
        return min(1.0, score)
    
    def build_filters_from_entities(
        self,
        entities: Dict,
        intent: str
    ) -> Dict[str, Any]:
        """
        Build Qdrant filters from extracted entities.
        
        Args:
            entities: Extracted entities from QU
            intent: User intent
            
        Returns:
            Qdrant-compatible filter dict
        """
        filters = {}
        
        # Category filter
        if "category" in entities and entities["category"]:
            filters["category"] = entities["category"]
        
        # Price range filter
        if "price_min" in entities:
            filters["price_min"] = entities["price_min"]
        
        if "price_max" in entities:
            filters["price_max"] = entities["price_max"]
        
        # Features filter
        if "features" in entities and entities["features"]:
            filters["features"] = entities["features"]
        
        # Chunk type filter based on intent
        if intent == "support":
            filters["chunk_type"] = "support"
        elif intent == "question":
            filters["chunk_type"] = "faq"
        elif intent in ["interest", "pricing"]:
            filters["chunk_type"] = "product_service"
        
        return filters
    
    def has_meaningful_filters(self, filters: Dict) -> bool:
        """
        Check if filters are meaningful enough for L3 search.
        
        Args:
            filters: Filter dict
            
        Returns:
            True if filters are specific enough
        """
        if not filters:
            return False
        
        # Require at least category or price range or features
        has_category = "category" in filters
        has_price = "price_min" in filters or "price_max" in filters
        has_features = "features" in filters and len(filters["features"]) > 0
        
        return has_category or has_price or has_features
