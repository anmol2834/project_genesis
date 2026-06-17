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

# ── Attribute compatibility shim ──────────────────────────────────────────────
# The schemas.RetrievalSource enum uses L3_EXACT_MATCH for the exact-match layer.
# Older code in this file was written against app.models.enums.RetrievalSource
# which used L2_EXACT_MATCH.  The canonical attribute in schemas is L3_EXACT_MATCH.
_EXACT_MATCH_SOURCE = RetrievalSource.L3_EXACT_MATCH

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

        IMPORTANT: Hardware specs (8GB RAM, 512GB SSD, RTX 4070, etc.) are
        NOT product names — they are search criteria. Caching a spec string
        as an entity name would poison the cache with wrong products that
        happen to be returned first. Spec queries must ALWAYS go to Qdrant.
        """
        if not user_id or not entity_name:
            return []

        # Skip L2 cache entirely for hardware spec strings.
        # A spec string like "8GB RAM" or "512GB SSD" is a filter criterion,
        # not a product identifier. Caching it would return the same wrong
        # products every time for any query containing that spec.
        if self._is_spec_entity(entity_name):
            logger.debug(
                "L2 exact cache bypassed for spec entity '%s' — "
                "going directly to Qdrant",
                entity_name,
            )
            return await self._search_qdrant_exact(user_id, entity_name, entity_type)

        # L2.1: Check Redis exact match cache
        cached = await self._get_cached_exact_match(user_id, entity_name)

        if cached:
            logger.info(f"L2 cache HIT: {entity_name}")
            return cached

        # L2.2: Query Qdrant for exact match
        chunks = await self._search_qdrant_exact(user_id, entity_name, entity_type)

        # Cache result (only for real product names, not specs)
        if chunks:
            await self._cache_exact_match(user_id, entity_name, chunks)

        logger.info(f"L2 Qdrant: {entity_name} found={len(chunks)}")

        return chunks

    def _is_spec_entity(self, entity_name: str) -> bool:
        """
        Return True when entity_name is a hardware/product spec rather than
        a real product name.  Spec strings are search CRITERIA — caching
        them would return products that happen to score highest for that spec
        in the first run, regardless of whether they actually match.

        Works for any business domain:
        - Electronics: "8GB RAM", "512GB SSD", "4K display", "RTX 4070"
        - Automotive: "2.0L engine", "250 HP", "AWD"
        - Industrial: "5kW motor", "10mm shaft"
        - Medical: "3.5 MHz probe", "12-lead ECG"
        """
        import re as _re
        _SPEC_PAT = _re.compile(
            r"^\d+\s*(?:gb|tb|mb|ghz|mhz|nm|inch|inches|watt|hp|cc|km|kg|lb|oz|rpm|mpg|kwh|v|a|hz)\b"
            r"|\b\d+\s*(?:gb|tb|mb|ghz|mhz)\b"
            r"|\b(?:ram|ssd|hdd|nvme|gpu|cpu|vram|ddr|pcie|usb|hdmi|lcd|oled|ips|amoled)\b"
            r"|\b(?:awd|fwd|rwd|4wd|abs|esc|tcs|ebs)\b"
            r"|\b\d+\s*(?:core|thread|bit|bit|channel|port|slot)\b",
            _re.IGNORECASE,
        )
        _GENERIC_NAMES = {
            "laptop", "laptops", "product", "products", "item", "items",
            "service", "services", "option", "options", "device", "devices",
        }
        n = str(entity_name).strip()
        return bool(n.lower() in _GENERIC_NAMES or _SPEC_PAT.search(n))
    
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
                    source=_EXACT_MATCH_SOURCE,
                    user_id=user_id,
                    metadata=chunk_dict.get("metadata", {}),
                    retrieval_layer="L3"
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
        Search Qdrant using exact name matching via scroll,
        with soft token-overlap fallback for partial spec matches
        (e.g. 'i5 8GB 512GB SSD' matches product with name 'i5 8GB 512GB SSD 11th Gen').
        """
        try:
            filters = {
                "chunk_type": "product_service" if entity_type == "product" else entity_type
            }

            results = await self.qdrant.scroll(
                user_id=user_id,
                filters=filters,
                limit=20  # Fetch more candidates to enable soft matching
            )

            entity_lower = entity_name.lower()
            entity_tokens = set(entity_lower.split())
            exact_chunks: List[RetrievedChunk] = []
            soft_chunks: List[RetrievedChunk]  = []

            for result in results:
                payload = result.get("payload", {})
                # Check name field and also content for the entity name
                name = (
                    payload.get("name", "")
                    or payload.get("title", "")
                    or payload.get("attributes", {}).get("name", "")
                    or payload.get("structured_data", {}).get("name", "")
                ).lower()

                content_lower = payload.get("content", "").lower()

                # ── Exact match ──
                if name == entity_lower or entity_lower in content_lower:
                    chunk = RetrievedChunk(
                        content=payload.get("content", ""),
                        score=1.0,
                        chunk_type=ChunkType(payload.get("chunk_type", "general")),
                        chunk_id=payload.get("chunk_id", str(result.get("id", ""))),
                        source=_EXACT_MATCH_SOURCE,
                        user_id=user_id,
                        metadata=payload,
                        retrieval_layer="L3",
                    )
                    exact_chunks.append(chunk)
                    continue

                # ── Soft match: token overlap score ──
                # Used for attribute queries like "i5 8GB 512GB SSD"
                # Matches products that contain a majority of the query tokens.
                if entity_tokens:
                    candidate_text = f"{name} {content_lower}"
                    candidate_tokens = set(candidate_text.split())
                    overlap = len(entity_tokens & candidate_tokens)
                    overlap_ratio = overlap / len(entity_tokens)

                    if overlap_ratio >= 0.6:  # At least 60% token match
                        soft_score = 0.5 + (overlap_ratio * 0.4)  # 0.74–0.90
                        chunk = RetrievedChunk(
                            content=payload.get("content", ""),
                            score=soft_score,
                            chunk_type=ChunkType(payload.get("chunk_type", "general")),
                            chunk_id=payload.get("chunk_id", str(result.get("id", ""))),
                            source=_EXACT_MATCH_SOURCE,
                            user_id=user_id,
                            metadata=dict(payload, _soft_match=True, _overlap_ratio=round(overlap_ratio, 2)),
                            retrieval_layer="L3",
                        )
                        soft_chunks.append(chunk)

            # Return exact first, then soft matches sorted by score
            soft_chunks.sort(key=lambda c: c.score, reverse=True)
            all_chunks = exact_chunks + soft_chunks[:3]  # cap soft matches at 3

            if exact_chunks:
                logger.info("L2 exact: '%s' exact=%d soft=%d", entity_name, len(exact_chunks), len(soft_chunks))
            elif soft_chunks:
                logger.info("L2 soft match: '%s' soft_found=%d best_score=%.2f",
                            entity_name, len(soft_chunks), soft_chunks[0].score if soft_chunks else 0)

            return all_chunks

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
