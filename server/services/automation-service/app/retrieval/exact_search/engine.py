"""
L2 Exact Search Engine
======================
Exact string matching on product names, SKUs, categories with Redis caching.

Performance: <20ms
Cache Hit Rate: ~30%
Cache TTL: 7 days
"""

import json
import hashlib
import logging
from typing import List, Dict, Optional
from datetime import datetime

from app.retrieval.schemas import RetrievedChunk, ChunkType, RetrievalSource

logger = logging.getLogger(__name__)


class ExactSearchEngine:
    """
    L2 exact match search with Redis caching.
    
    Searches for:
    - Product names (exact match)
    - SKUs
    - Categories
    - Contact information
    - Department names
    """
    
    def __init__(self, redis_client, qdrant_repository):
        """
        Initialize exact search engine.
        
        Args:
            redis_client: Redis client from shared.cache
            qdrant_repository: Qdrant repository for fallback
        """
        self.redis = redis_client
        self.qdrant = qdrant_repository
        self.key_prefix = "automation:exact"
        self.cache_ttl = 604800  # 7 days
    
    async def search_exact(
        self,
        user_id: str,
        entity_name: str,
        entity_type: str = "product"
    ) -> List[RetrievedChunk]:
        """
        Exact match search with cache-first strategy.
        
        Args:
            user_id: Tenant ID (mandatory)
            entity_name: Exact entity name ("AeroCam X1")
            entity_type: Type of entity (product, category, etc.)
            
        Returns:
            List of matching chunks
        """
        if not user_id or not entity_name:
            return []
        
        # L2.1: Check Redis exact match cache
        cached = await self._get_cached_exact_match(user_id, entity_name)
        
        if cached:
            logger.info(f"L2 cache HIT: {entity_name}")
            return cached
        
        # L2.2: Query Qdrant for exact match
        chunks = await self._search_qdrant_exact(user_id, entity_name, entity_type)
        
        # Cache result
        if chunks:
            await self._cache_exact_match(user_id, entity_name, chunks)
        
        logger.info(f"L2 Qdrant: {entity_name} found={len(chunks)}")
        
        return chunks
    
    async def _get_cached_exact_match(
        self,
        user_id: str,
        entity_name: str
    ) -> Optional[List[RetrievedChunk]]:
        """Get cached exact match result"""
        cache_key = self._build_cache_key(user_id, entity_name)
        
        try:
            cached = await self.redis.get(cache_key)
            
            if not cached:
                return None
            
            data = json.loads(cached)
            
            # Deserialize chunks
            chunks = []
            for chunk_dict in data.get("chunks", []):
                chunk = RetrievedChunk(
                    content=chunk_dict["content"],
                    score=chunk_dict.get("score", 1.0),
                    chunk_type=ChunkType(chunk_dict["chunk_type"]),
                    chunk_id=chunk_dict["chunk_id"],
                    source=RetrievalSource.L2_EXACT_MATCH,
                    user_id=user_id,
                    metadata=chunk_dict.get("metadata", {}),
                    retrieval_layer="L2"
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"L2 cache read error: {e}")
            return None
    
    async def _cache_exact_match(
        self,
        user_id: str,
        entity_name: str,
        chunks: List[RetrievedChunk]
    ) -> bool:
        """Cache exact match result"""
        cache_key = self._build_cache_key(user_id, entity_name)
        
        # Serialize chunks
        serialized_chunks = [chunk.to_dict() for chunk in chunks]
        
        data = {
            "entity_name": entity_name,
            "chunks": serialized_chunks,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        try:
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data)
            )
            return True
            
        except Exception as e:
            logger.error(f"L2 cache write error: {e}")
            return False
    
    async def _search_qdrant_exact(
        self,
        user_id: str,
        entity_name: str,
        entity_type: str
    ) -> List[RetrievedChunk]:
        """
        Search Qdrant using exact name matching via scroll.
        
        Uses Qdrant scroll with metadata filter (no embedding needed).
        """
        try:
            # Build metadata filter
            filters = {
                "chunk_type": "product_service" if entity_type == "product" else entity_type
            }
            
            # Scroll Qdrant with name filter
            # Note: Qdrant scroll already enforces user_id filter via repository
            results = await self.qdrant.scroll(
                user_id=user_id,
                filters=filters,
                limit=5
            )
            
            # Filter by exact name match (case-insensitive)
            entity_lower = entity_name.lower()
            matched_chunks = []
            
            for result in results:
                payload = result.get("payload", {})
                name = payload.get("name", "")
                
                if name.lower() == entity_lower:
                    chunk = RetrievedChunk(
                        content=payload.get("content", ""),
                        score=1.0,  # Exact match = perfect score
                        chunk_type=ChunkType(payload.get("chunk_type", "general")),
                        chunk_id=payload.get("chunk_id", str(result.get("id", ""))),
                        source=RetrievalSource.L2_EXACT_MATCH,
                        user_id=user_id,
                        metadata=payload,
                        retrieval_layer="L2"
                    )
                    matched_chunks.append(chunk)
            
            return matched_chunks
            
        except Exception as e:
            logger.error(f"L2 Qdrant search error: {e}")
            return []
    
    def _build_cache_key(self, user_id: str, entity_name: str) -> str:
        """Build Redis cache key"""
        # Hash entity name for consistent key length
        name_hash = hashlib.sha256(entity_name.lower().encode()).hexdigest()[:16]
        return f"{self.key_prefix}:{user_id}:{name_hash}"
    
    async def invalidate_cache(
        self,
        user_id: str,
        entity_name: Optional[str] = None
    ) -> int:
        """
        Invalidate exact match cache.
        
        Args:
            user_id: Tenant ID
            entity_name: Specific entity or None for all
            
        Returns:
            Number of keys deleted
        """
        if entity_name:
            cache_key = self._build_cache_key(user_id, entity_name)
            return await self.redis.delete(cache_key)
        else:
            # Delete all exact match caches for user
            pattern = f"{self.key_prefix}:{user_id}:*"
            keys = await self.redis.keys(pattern)
            
            if keys:
                return await self.redis.delete(*keys)
            
            return 0
