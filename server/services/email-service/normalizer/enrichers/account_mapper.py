"""
Account Mapper Enricher
Maps email address or subscription to email_account_id.
"""

from typing import Optional
from sqlalchemy import select

from shared.logger import get_logger
from shared.database import get_db_session
from shared.cache import get_redis
from models.email_account import EmailAccount

logger = get_logger(__name__)


class AccountMapper:
    """Maps email address to email_account_id."""
    
    CACHE_TTL = 3600  # 1 hour
    
    async def get_account_id_by_email(self, email_address: str) -> Optional[str]:
        """
        Get email_account_id by email address.
        
        Args:
            email_address: Email address
            
        Returns:
            email_account_id or None if not found
        """
        # Try cache first
        redis = await get_redis()
        cache_key = f"account:email:{email_address}"
        
        cached_account_id = await redis.get(cache_key)
        if cached_account_id:
            account_id = cached_account_id.decode() if isinstance(cached_account_id, bytes) else cached_account_id
            logger.debug(f"Account ID cache hit: {email_address} -> {account_id}")
            return account_id
        
        # Cache miss - query database
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount.id).where(
                    EmailAccount.email_address == email_address
                )
            )
            account_id = result.scalar_one_or_none()
            
            if account_id:
                # Cache for future lookups
                await redis.setex(cache_key, self.CACHE_TTL, str(account_id))
                logger.debug(f"Account ID cached: {email_address} -> {account_id}")
                return str(account_id)
            
            logger.warning(f"Account ID not found for email: {email_address}")
            return None
    
    async def get_account_id_by_subscription(self, subscription_id: str) -> Optional[str]:
        """
        Get email_account_id by subscription_id.
        
        Args:
            subscription_id: Provider subscription ID
            
        Returns:
            email_account_id or None if not found
        """
        from provider.manager.subscription_manager import SubscriptionManager
        manager = SubscriptionManager()
        return await manager.get_account_id_from_subscription(subscription_id)
