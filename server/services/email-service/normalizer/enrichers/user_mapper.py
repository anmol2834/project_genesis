"""
User Mapper Enricher
Maps email account to user_id.
"""

from typing import Optional
from sqlalchemy import select

from shared.logger import get_logger
from shared.database import get_db_session
from shared.cache import get_redis
from models.email_account import EmailAccount

logger = get_logger(__name__)


class UserMapper:
    """Maps email account to user_id."""
    
    CACHE_TTL = 3600  # 1 hour
    
    async def get_user_id(self, email_account_id: str) -> Optional[str]:
        """
        Get user_id for an email account.
        Uses Redis cache for O(1) lookup.
        
        Args:
            email_account_id: Email account ID
            
        Returns:
            user_id or None if not found
        """
        # Try cache first
        redis = await get_redis()
        cache_key = f"user:account:{email_account_id}"
        
        cached_user_id = await redis.get(cache_key)
        if cached_user_id:
            user_id = cached_user_id.decode() if isinstance(cached_user_id, bytes) else cached_user_id
            logger.debug(f"User ID cache hit: {email_account_id} -> {user_id}")
            return user_id
        
        # Cache miss - query database
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount.user_id).where(
                    EmailAccount.id == email_account_id
                )
            )
            user_id = result.scalar_one_or_none()
            
            if user_id:
                # Cache for future lookups
                await redis.setex(cache_key, self.CACHE_TTL, str(user_id))
                logger.debug(f"User ID cached: {email_account_id} -> {user_id}")
                return str(user_id)
            
            logger.warning(f"User ID not found for account: {email_account_id}")
            return None
