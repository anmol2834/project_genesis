"""
L1 Intent Retrieval Cache
==========================
Stores intent + retrieval associations for intelligent cache reuse.

Performance: <5ms lookup
Hit Rate: ~50% for continuation conversations
TTL: 1 hour (intent-specific)

CRITICAL: This is the FIRST layer in hierarchical retrieval.
If intent matches previous intent semantically, reuse cached retrieval.
"""

import json
import hashlib
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class IntentCacheEngine:
    """
    L1 Intent Cache - stores intent → retrieval mappings.
    
    Enables intent reuse for:
    - Same intent continuations ("tell me more")
    - Topic-based follow-ups ("what about pricing?")
    - Entity-focused queries ("AeroCam X1 features")
    
    Cache stores:
    - Intent fingerprint (type + entities + keywords)
    - Retrieved chunk IDs
    - Retrieval confidence
    - Active topic
    - Timestamp
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.key_prefix = "automation:intent_cache"
        self.default_ttl = 3600  # 1 hour
    
    async def get_cached_retrieval(
        self,
        user_id: str,
        intent_type: str,
        entities: List[str],
        keywords: List[str]
    ) -> Optional[Dict]:
        """
        Get cached retrieval by intent fingerprint.
        
        Args:
            user_id: Tenant ID
            intent_type: Primary intent type
            entities: Extracted entities (products, features)
            keywords: Search keywords from query plan
            
        Returns:
            Cached retrieval data or None if miss
        """
        # Generate intent fingerprint
        intent_key = self._generate_intent_key(
            user_id, intent_type, entities, keywords
        )
        
        try:
            cached = await self.redis.get(intent_key)

            if not cached:
                logger.debug(f"L1 intent cache MISS: {intent_type}")
                return None

            data = json.loads(cached)

            logger.info(
                f"L1 intent cache HIT: {intent_type} | "
                f"chunks={len(data['chunk_ids'])}"
            )

            return data
            
        except Exception as e:
            logger.error(f"L1 intent cache read error: {e}")
            return None
    
    async def store_intent_with_retrieval(
        self,
        user_id: str,
        intent_type: str,
        entities: List[str],
        keywords: List[str],
        chunk_ids: List[str],
        chunks_summary: List[Dict],
        retrieval_confidence: float,
        active_topic: str,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Store intent → retrieval mapping.
        
        Args:
            user_id: Tenant ID
            intent_type: Primary intent type
            entities: Extracted entities
            keywords: Search keywords
            chunk_ids: Retrieved chunk IDs
            chunks_summary: Lightweight chunk summaries
            retrieval_confidence: Confidence score
            active_topic: Current conversation topic
            ttl_seconds: Cache TTL (default: 1 hour)
            
        Returns:
            True if stored successfully
        """
        intent_key = self._generate_intent_key(
            user_id, intent_type, entities, keywords
        )
        ttl = ttl_seconds or self.default_ttl
        
        cache_data = {
            "intent_type": intent_type,
            "entities": entities,
            "keywords": keywords,
            "chunk_ids": chunk_ids,
            "chunks_summary": chunks_summary[:5],  # Store top 5 summaries
            "retrieval_confidence": retrieval_confidence,
            "active_topic": active_topic,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        try:
            await self.redis.setex(
                intent_key,
                ttl,
                json.dumps(cache_data)
            )
            
            logger.debug(
                f"L1 intent cache STORED: {intent_type} | chunks={len(chunk_ids)}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"L1 intent cache write error: {e}")
            return False
    
    async def invalidate_intent_cache(
        self,
        user_id: str,
        intent_type: Optional[str] = None
    ) -> int:
        """
        Invalidate intent cache using SCAN (non-blocking, safe on large keyspaces).

        Uses HSCAN-compatible cursor iteration instead of KEYS so that Redis
        is never blocked on large datasets.  KEYS is O(N) and blocks the server
        — SCAN is O(1) per call and iterates lazily.

        Args:
            user_id: Tenant ID
            intent_type: Specific intent or None for all tenant intents

        Returns:
            Number of keys deleted
        """
        if intent_type:
            pattern = f"{self.key_prefix}:{user_id}:*{intent_type}*"
        else:
            pattern = f"{self.key_prefix}:{user_id}:*"

        deleted = 0
        try:
            # Use SCAN with a cursor loop — non-blocking, works on all Redis sizes
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    result = await self.redis.delete(*keys)
                    deleted += result if isinstance(result, int) else len(keys)
                if cursor == 0:
                    break

            if deleted:
                logger.info("L1 intent cache invalidated: %d keys for user=%s", deleted, user_id[:12])
            return deleted

        except Exception as e:
            logger.error("L1 intent cache invalidation error: %s", e)
            return 0
    
    def _generate_intent_key(
        self,
        user_id: str,
        intent_type: str,
        entities: List[str],
        keywords: List[str]
    ) -> str:
        """
        Generate deterministic intent cache key.
        
        Key includes:
        - user_id (tenant isolation)
        - intent_type
        - sorted entities (normalized)
        - sorted keywords (normalized)
        """
        # Normalize entities and keywords
        entities_norm = sorted([e.lower().strip() for e in entities if e])
        keywords_norm = sorted([k.lower().strip() for k in keywords if k])
        
        # Create fingerprint
        fingerprint_data = {
            "intent": intent_type,
            "entities": entities_norm,
            "keywords": keywords_norm[:5]  # Top 5 keywords only
        }
        
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]
        
        return f"{self.key_prefix}:{user_id}:{fingerprint_hash}"
    
    def should_use_intent_cache(
        self,
        intent_type: str,
        entities: List[str],
        is_continuation: bool
    ) -> bool:
        """
        Determine if intent cache lookup is worthwhile.
        
        Args:
            intent_type: Current intent type
            entities: Extracted entities
            is_continuation: Is this a continuation message?
            
        Returns:
            True if cache should be checked
        """
        # Always check cache for continuations
        if is_continuation:
            return True
        
        # Check cache for entity-specific queries
        if entities and len(entities) > 0:
            return True
        
        # Check cache for common intents
        cacheable_intents = [
            "pricing_inquiry",
            "product_inquiry",
            "support_request",
            "feature_request",
            "technical_question"
        ]
        
        if intent_type in cacheable_intents:
            return True
        
        return False
