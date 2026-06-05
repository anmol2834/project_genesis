"""
Storage - Redis Layer
======================
Enterprise Redis abstraction with tenant isolation and observability.
"""
from typing import Optional, Dict, Any, List
import json
from datetime import timedelta
from shared.cache import get_redis
from app.models.serialization import Serializer
from app.observability import get_logger, get_metrics_collector

logger = get_logger(__name__)

class RedisStorage:
    """Enterprise Redis storage layer"""
    
    # Key prefixes for namespacing
    PREFIX_MEMORY = "automation:memory"
    PREFIX_CACHE = "automation:cache"
    PREFIX_RETRIEVAL = "automation:retrieval"
    PREFIX_WORKFLOW = "automation:workflow"
    PREFIX_LOCK = "automation:lock"
    
    def __init__(self):
        self.metrics = get_metrics_collector()
    
    async def set_memory(
        self,
        user_id: str,
        thread_id: str,
        memory: Dict[str, Any],
        ttl_hours: int = 24
    ) -> bool:
        """Store conversation memory"""
        key = self._memory_key(user_id, thread_id)
        
        try:
            redis = await get_redis()
            serialized = Serializer.to_redis(memory)
            await redis.setex(key, timedelta(hours=ttl_hours), serialized)
            
            self.metrics.record_counter("redis.memory.set", 1, user_id)
            return True
            
        except Exception as e:
            logger.error(f"Redis memory set failed", user_id=user_id, error=e)
            return False
    
    async def get_memory(
        self,
        user_id: str,
        thread_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve conversation memory"""
        key = self._memory_key(user_id, thread_id)
        
        try:
            redis = await get_redis()
            data = await redis.get(key)
            
            if data:
                self.metrics.record_counter("redis.memory.hit", 1, user_id)
                return Serializer.from_redis(data)
            else:
                self.metrics.record_counter("redis.memory.miss", 1, user_id)
                return None
                
        except Exception as e:
            logger.error(f"Redis memory get failed", user_id=user_id, error=e)
            return None
    
    async def set_retrieval_cache(
        self,
        user_id: str,
        cache_key: str,
        chunks: List[Dict[str, Any]],
        ttl_minutes: int = 30
    ) -> bool:
        """Cache retrieval results"""
        key = self._retrieval_cache_key(user_id, cache_key)
        
        try:
            redis = await get_redis()
            serialized = Serializer.to_redis({"chunks": chunks})
            await redis.setex(key, timedelta(minutes=ttl_minutes), serialized)
            
            self.metrics.record_counter("redis.retrieval_cache.set", 1, user_id)
            return True
            
        except Exception as e:
            logger.error(f"Redis retrieval cache set failed", user_id=user_id, error=e)
            return False
    
    async def get_retrieval_cache(
        self,
        user_id: str,
        cache_key: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached retrieval results"""
        key = self._retrieval_cache_key(user_id, cache_key)
        
        try:
            redis = await get_redis()
            data = await redis.get(key)
            
            if data:
                self.metrics.record_counter("redis.retrieval_cache.hit", 1, user_id)
                result = Serializer.from_redis(data)
                return result.get("chunks", [])
            else:
                self.metrics.record_counter("redis.retrieval_cache.miss", 1, user_id)
                return None
                
        except Exception as e:
            logger.error(f"Redis retrieval cache get failed", user_id=user_id, error=e)
            return None
    
    async def set_workflow_state(
        self,
        workflow_id: str,
        state: Dict[str, Any],
        ttl_hours: int = 48
    ) -> bool:
        """Store workflow execution state"""
        key = self._workflow_key(workflow_id)
        
        try:
            redis = await get_redis()
            serialized = Serializer.to_redis(state)
            await redis.setex(key, timedelta(hours=ttl_hours), serialized)
            return True
            
        except Exception as e:
            logger.error(f"Redis workflow state set failed", workflow_id=workflow_id, error=e)
            return False
    
    async def get_workflow_state(
        self,
        workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve workflow execution state"""
        key = self._workflow_key(workflow_id)
        
        try:
            redis = await get_redis()
            data = await redis.get(key)
            return Serializer.from_redis(data) if data else None
            
        except Exception as e:
            logger.error(f"Redis workflow state get failed", workflow_id=workflow_id, error=e)
            return None
    
    async def acquire_lock(
        self,
        lock_key: str,
        ttl_seconds: int = 30
    ) -> bool:
        """Acquire distributed lock"""
        key = self._lock_key(lock_key)
        
        try:
            redis = await get_redis()
            result = await redis.set(key, "1", ex=ttl_seconds, nx=True)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis lock acquire failed", lock_key=lock_key, error=e)
            return False
    
    async def release_lock(self, lock_key: str) -> bool:
        """Release distributed lock"""
        key = self._lock_key(lock_key)
        
        try:
            redis = await get_redis()
            await redis.delete(key)
            return True
            
        except Exception as e:
            logger.error(f"Redis lock release failed", lock_key=lock_key, error=e)
            return False
    
    def _memory_key(self, user_id: str, thread_id: str) -> str:
        """Generate memory key with tenant isolation"""
        return f"{self.PREFIX_MEMORY}:{user_id}:{thread_id}"
    
    def _retrieval_cache_key(self, user_id: str, cache_key: str) -> str:
        """Generate retrieval cache key"""
        return f"{self.PREFIX_RETRIEVAL}:{user_id}:{cache_key}"
    
    def _workflow_key(self, workflow_id: str) -> str:
        """Generate workflow state key"""
        return f"{self.PREFIX_WORKFLOW}:{workflow_id}"
    
    def _lock_key(self, lock_key: str) -> str:
        """Generate distributed lock key"""
        return f"{self.PREFIX_LOCK}:{lock_key}"

redis_storage = RedisStorage()

__all__ = ["RedisStorage", "redis_storage"]
