"""
MongoDB Connection Module
Async connection using Motor (async MongoDB driver)
NO COLLECTIONS - Only connection layer
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

from shared.config import get_config

logger = logging.getLogger(__name__)

# Global MongoDB client instance
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None


def get_mongo_client() -> AsyncIOMotorClient:
    """
    Get or create MongoDB client
    """
    global _mongo_client
    
    if _mongo_client is None:
        config = get_config()
        
        # Connection options for MongoDB Atlas
        _mongo_client = AsyncIOMotorClient(
            config.MONGODB_URL,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            w='majority'
        )
        
        logger.info("MongoDB client created")
    
    return _mongo_client


def get_mongo_database() -> AsyncIOMotorDatabase:
    """
    Get MongoDB database instance
    """
    global _mongo_db
    
    if _mongo_db is None:
        config = get_config()
        client = get_mongo_client()
        _mongo_db = client[config.MONGODB_DB]
        
        logger.info(f"MongoDB database '{config.MONGODB_DB}' connected")
    
    return _mongo_db


async def init_mongodb():
    """
    Initialize MongoDB connection
    Call this on application startup
    """
    try:
        client = get_mongo_client()
        
        # Test connection
        await client.admin.command('ping')
        
        logger.info("MongoDB connection initialized successfully")
        return True
    except Exception as e:
        logger.error(f"MongoDB initialization failed: {e}")
        return False


async def close_mongodb():
    """
    Close MongoDB connections
    Call this on application shutdown
    """
    global _mongo_client, _mongo_db
    
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB connections closed")


async def check_mongodb_health() -> bool:
    """
    Check MongoDB connection health
    Used for health check endpoints
    """
    try:
        client = get_mongo_client()
        await client.admin.command('ping')
        return True
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return False
