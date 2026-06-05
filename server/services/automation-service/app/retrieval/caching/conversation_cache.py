"""
L1 Conversation Cache Engine
=============================
Eliminates redundant Qdrant queries by caching conversation context.

Performance: <1ms cache lookup
Hit Rate: ~40%
TTL: 20 minutes
"""

import json
import logging
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversationCacheEngine:
    """
    L1 cache that stores conversation context to avoid repeated retrieval.
    
    Cache stores:
    - Profile chunks (business info, tone, policies)
    - Product chunks (retrieved products)
    - Shown products list
    - All product names for fuzzy matching
    """
    
    def __init__(self, redis_client):
        """
        Initialize conversation cache engine.
        
        Args:
            redis_client: Redis client from shared.cache
        """
        self.redis = redis_client
        self.key_prefix = "automation:conv"
        self.default_ttl = 1200  # 20 minutes
    
    async def get_conversation_context(
        self,
        user_id: str,
        conversation_id: str
    ) -> Optional[Dict]:
        """
        Get cached conversation context.
        
        Args:
            user_id: Tenant ID
            conversation_id: Conversation identifier
            
        Returns:
            Cached context or None if miss
        """
        key = f"{self.key_prefix}:{user_id}:{conversation_id}:ctx"
        
        try:
            cached = await self.redis.get(key)
            
            if not cached:
                logger.debug(f"L1 cache miss: {conversation_id[:12]}")
                return None
            
            context = json.loads(cached)
            
            logger.info(
                f"L1 cache HIT: conv={conversation_id[:12]} "
                f"products={len(context.get('product_chunks', []))}"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"L1 cache error: {e}")
            return None
    
    async def save_conversation_context(
        self,
        user_id: str,
        conversation_id: str,
        profile_chunks: List[Dict],
        product_chunks: List[Dict],
        shown_products: List[str],
        turn: int = 0,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Save conversation context to cache.
        
        Args:
            user_id: Tenant ID
            conversation_id: Conversation identifier
            profile_chunks: Business profile chunks
            product_chunks: Product/service chunks
            shown_products: List of shown product names
            turn: Current turn number
            ttl_seconds: Cache TTL (default: 20 min)
            
        Returns:
            True if saved successfully
        """
        key = f"{self.key_prefix}:{user_id}:{conversation_id}:ctx"
        ttl = ttl_seconds or self.default_ttl
        
        # Extract all product names for fuzzy matching
        all_product_names = []
        for chunk in product_chunks:
            if "name" in chunk.get("metadata", {}):
                all_product_names.append(chunk["metadata"]["name"])
        
        context = {
            "profile": profile_chunks,
            "products": product_chunks,
            "shown_products": shown_products,
            "all_product_names": all_product_names,
            "turn": turn,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        try:
            await self.redis.setex(
                key,
                ttl,
                json.dumps(context)
            )
            
            logger.debug(
                f"L1 cache saved: conv={conversation_id[:12]} "
                f"profile={len(profile_chunks)} products={len(product_chunks)}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"L1 cache save error: {e}")
            return False
    
    async def update_shown_products(
        self,
        user_id: str,
        conversation_id: str,
        shown_products: List[str]
    ) -> bool:
        """
        Update shown products list in cache.
        
        Args:
            user_id: Tenant ID
            conversation_id: Conversation identifier
            shown_products: List of product names shown to user
            
        Returns:
            True if updated successfully
        """
        context = await self.get_conversation_context(user_id, conversation_id)
        
        if not context:
            return False
        
        # Merge with existing shown products
        existing_shown = set(context.get("shown_products", []))
        existing_shown.update(shown_products)
        
        context["shown_products"] = list(existing_shown)
        context["turn"] = context.get("turn", 0) + 1
        
        return await self.save_conversation_context(
            user_id=user_id,
            conversation_id=conversation_id,
            profile_chunks=context["profile"],
            product_chunks=context["products"],
            shown_products=context["shown_products"],
            turn=context["turn"]
        )
    
    async def invalidate_cache(
        self,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> int:
        """
        Invalidate conversation cache.
        
        Args:
            user_id: Tenant ID
            conversation_id: Specific conversation or None for all
            
        Returns:
            Number of keys deleted
        """
        if conversation_id:
            key = f"{self.key_prefix}:{user_id}:{conversation_id}:ctx"
            deleted = await self.redis.delete(key)
            return deleted
        else:
            # Delete all conversation caches for user
            pattern = f"{self.key_prefix}:{user_id}:*"
            keys = await self.redis.keys(pattern)
            
            if keys:
                deleted = await self.redis.delete(*keys)
                return deleted
            
            return 0
    
    def should_skip_retrieval(
        self,
        context: Dict,
        intent: str,
        entities: Dict
    ) -> bool:
        """
        Determine if retrieval can be skipped using cache.
        
        Args:
            context: Cached conversation context
            intent: Current intent
            entities: Current entities
            
        Returns:
            True if cache contains sufficient information
        """
        if not context:
            return False
        
        # Check if we have profile chunks (always needed)
        if not context.get("profile"):
            return False
        
        # For follow-up/continuation intents
        if intent in ["follow_up", "casual"]:
            return True
        
        # For product queries, check if we have relevant products
        if intent in ["interest", "question"]:
            product_name = entities.get("product_name")
            
            if product_name:
                # Check if product is in cache
                all_names = context.get("all_product_names", [])
                if product_name in all_names:
                    return True
        
        # For pricing queries on known products
        if intent == "pricing":
            product_name = entities.get("product_name")
            
            if product_name:
                shown = context.get("shown_products", [])
                if product_name in shown:
                    return True
        
        return False
    
    def get_chunks_from_cache(
        self,
        context: Dict,
        intent: str,
        entities: Dict,
        top_k: int = 8
    ) -> List[Dict]:
        """
        Extract relevant chunks from cache.
        
        Args:
            context: Cached conversation context
            intent: Current intent
            entities: Current entities
            top_k: Maximum chunks to return
            
        Returns:
            List of relevant chunks from cache
        """
        chunks = []
        
        # Always include profile chunks
        profile_chunks = context.get("profile", [])
        chunks.extend(profile_chunks[:2])  # Top 2 profile chunks
        
        # Add product chunks based on intent
        product_chunks = context.get("products", [])
        
        if intent in ["interest", "question", "pricing"]:
            product_name = entities.get("product_name")
            
            if product_name:
                # Filter to specific product
                matching = [
                    p for p in product_chunks
                    if p.get("metadata", {}).get("name") == product_name
                ]
                chunks.extend(matching[:3])
            else:
                # Include all cached products
                chunks.extend(product_chunks[:top_k - len(chunks)])
        
        return chunks[:top_k]
