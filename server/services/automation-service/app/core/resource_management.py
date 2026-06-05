"""
Core - Resource Management
===========================
Enterprise resource pooling and lifecycle management.
"""
import asyncio
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager
from redis.asyncio import Redis, ConnectionPool as RedisPool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from qdrant_client import AsyncQdrantClient
from shared.config import get_config
from app.observability import get_logger, get_metrics_collector

logger = get_logger(__name__)


class ResourceManager:
    """Enterprise resource manager with pooling"""
    
    def __init__(self):
        # Import shared config directly
        from shared.config import get_config as get_shared_config
        from app.observability import get_metrics_collector
        
        self.shared_config = get_shared_config()
        self.metrics = get_metrics_collector()
        
        # Access settings from shared_config
        self.REDIS_URL = self.shared_config.REDIS_URL
        self.DATABASE_URL = self.shared_config.DATABASE_URL
        self.QDRANT_URL = self.shared_config.QDRANT_URL
        self.REDIS_MAX_CONNECTIONS = self.shared_config.REDIS_MAX_CONNECTIONS
        self.DB_POOL_SIZE = self.shared_config.DB_POOL_SIZE
        self.DB_MAX_OVERFLOW = self.shared_config.DB_MAX_OVERFLOW
        self.DB_POOL_TIMEOUT = self.shared_config.DB_POOL_TIMEOUT
        
        # Connection pools
        self._redis_pool: Optional[RedisPool] = None
        self._redis_client: Optional[Redis] = None
        self._db_engine: Optional[AsyncEngine] = None
        self._db_session_factory: Optional[async_sessionmaker] = None
        self._qdrant_client: Optional[AsyncQdrantClient] = None
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all resource pools"""
        if self._initialized:
            return
        
        logger.info("Initializing resource pools")
        
        # Redis pool
        await self._init_redis()
        
        # PostgreSQL pool
        await self._init_database()
        
        # Qdrant client
        await self._init_qdrant()
        
        self._initialized = True
        logger.info("Resource pools initialized")
    
    async def _init_redis(self) -> None:
        """Initialize Redis connection pool"""
        try:
            self._redis_pool = RedisPool.from_url(
                self.REDIS_URL,
                max_connections=self.REDIS_MAX_CONNECTIONS,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            
            self._redis_client = Redis(connection_pool=self._redis_pool)
            
            # Test connection
            await self._redis_client.ping()
            logger.info(f"Redis pool initialized (max_connections={self.REDIS_MAX_CONNECTIONS})")
            
        except Exception as e:
            logger.error(f"Redis pool initialization failed: {e}")
            raise
    
    async def _init_database(self) -> None:
        """Initialize PostgreSQL connection pool"""
        try:
            self._db_engine = create_async_engine(
                self.DATABASE_URL,
                pool_size=self.DB_POOL_SIZE,
                max_overflow=self.DB_MAX_OVERFLOW,
                pool_timeout=self.DB_POOL_TIMEOUT,
                pool_pre_ping=True,
                echo=False
            )
            
            self._db_session_factory = async_sessionmaker(
                self._db_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            async with self._db_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            
            logger.info(f"Database pool initialized (pool_size={self.DB_POOL_SIZE})")
            
        except Exception as e:
            logger.error(f"Database pool initialization failed: {e}")
            raise
    
    async def _init_qdrant(self) -> None:
        """Initialize Qdrant client"""
        try:
            # Parse URL
            url = self.QDRANT_URL.replace("http://", "").replace("https://", "")
            host, port = url.split(":") if ":" in url else (url, "6333")
            
            self._qdrant_client = AsyncQdrantClient(
                host=host,
                port=int(port),
                timeout=30
            )
            
            # Test connection
            collections = await self._qdrant_client.get_collections()
            logger.info(f"Qdrant client initialized ({len(collections.collections)} collections)")
            
        except Exception as e:
            logger.error(f"Qdrant client initialization failed: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown all resource pools"""
        logger.info("Shutting down resource pools")
        
        # Close Redis
        if self._redis_client:
            await self._redis_client.aclose()
        if self._redis_pool:
            await self._redis_pool.disconnect()
        
        # Close database
        if self._db_engine:
            await self._db_engine.dispose()
        
        # Close Qdrant
        if self._qdrant_client:
            await self._qdrant_client.close()
        
        self._initialized = False
        logger.info("Resource pools shutdown complete")
    
    def get_redis(self) -> Redis:
        """Get Redis client"""
        if not self._redis_client:
            raise RuntimeError("Redis not initialized")
        return self._redis_client
    
    @asynccontextmanager
    async def get_db_session(self):
        """Get database session context manager"""
        if not self._db_session_factory:
            raise RuntimeError("Database not initialized")
        
        session = self._db_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    def get_qdrant(self) -> AsyncQdrantClient:
        """Get raw Qdrant async client (use get_qdrant_repository() for retrieval engines)."""
        if not self._qdrant_client:
            raise RuntimeError("Qdrant not initialized")
        return self._qdrant_client

    def get_qdrant_repository(self):
        """
        Get tenant-safe Qdrant repository with collection_name baked in.
        All retrieval engines (L2-L6) MUST use this — NOT get_qdrant().
        """
        if not self._qdrant_client:
            raise RuntimeError("Qdrant not initialized")
        from app.retrieval.qdrant.async_repository import AsyncQdrantRepository
        from shared.config import get_config as _gc
        collection = _gc().QDRANT_COLLECTION
        return AsyncQdrantRepository(self._qdrant_client, collection)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all resources"""
        health = {
            "redis": {"status": "unknown"},
            "database": {"status": "unknown"},
            "qdrant": {"status": "unknown"}
        }
        
        # Redis health
        try:
            await self._redis_client.ping()
            health["redis"]["status"] = "healthy"
        except Exception as e:
            health["redis"]["status"] = "unhealthy"
            health["redis"]["error"] = str(e)
        
        # Database health
        try:
            async with self._db_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            health["database"]["status"] = "healthy"
        except Exception as e:
            health["database"]["status"] = "unhealthy"
            health["database"]["error"] = str(e)
        
        # Qdrant health
        try:
            await self._qdrant_client.get_collections()
            health["qdrant"]["status"] = "healthy"
        except Exception as e:
            health["qdrant"]["status"] = "unhealthy"
            health["qdrant"]["error"] = str(e)
        
        return health


# Global resource manager
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get global resource manager"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


async def initialize_resources() -> None:
    """Initialize global resource manager"""
    manager = get_resource_manager()
    await manager.initialize()


async def shutdown_resources() -> None:
    """Shutdown global resource manager"""
    global _resource_manager
    if _resource_manager:
        await _resource_manager.shutdown()
        _resource_manager = None


__all__ = [
    "ResourceManager",
    "get_resource_manager",
    "initialize_resources",
    "shutdown_resources",
]
