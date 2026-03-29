"""
SMTP Subscriber - Polling Registration
Registers SMTP/IMAP accounts for periodic polling (no push notifications).
"""

from typing import Dict, Any
from datetime import datetime, timedelta

from shared.logger import get_logger
from shared.cache import get_redis

logger = get_logger(__name__)


class SMTPSubscriber:
    """Manages SMTP/IMAP polling registrations."""

    async def subscribe(self, account) -> Dict[str, Any]:
        """
        Register SMTP account for polling.
        Returns: {subscription_id, resource_id, expires_at}
        """
        logger.info(f"Registering SMTP account for polling: {account.email_address}")

        # For SMTP, we just register the account in Redis for the poller to pick up
        redis = await get_redis()
        
        # Add to polling queue
        await redis.sadd("smtp:polling:accounts", str(account.id))
        
        # Set polling metadata
        await redis.hset(
            f"smtp:account:{account.id}",
            mapping={
                "email": account.email_address,
                "last_poll": "0",
                "poll_interval": "300"  # 5 minutes
            }
        )

        # SMTP doesn't expire, but we set a far future date for consistency
        expires_at = datetime.utcnow() + timedelta(days=365)

        return {
            "subscription_id": f"smtp_{account.id}",
            "resource_id": account.email_address,
            "expires_at": expires_at
        }

    async def renew(self, account, subscription) -> Dict[str, Any]:
        """
        Renew SMTP polling registration (essentially a no-op).
        """
        logger.info(f"Renewing SMTP polling for {account.email_address}")
        
        # Just update the expiry date
        expires_at = datetime.utcnow() + timedelta(days=365)
        
        return {
            "subscription_id": subscription.subscription_id,
            "resource_id": subscription.resource_id,
            "expires_at": expires_at
        }

    async def unsubscribe(self, account, subscription):
        """Remove SMTP account from polling queue."""
        logger.info(f"Unregistering SMTP account from polling: {account.email_address}")

        try:
            redis = await get_redis()
            
            # Remove from polling queue
            await redis.srem("smtp:polling:accounts", str(account.id))
            
            # Delete metadata
            await redis.delete(f"smtp:account:{account.id}")
            
            logger.info(f"SMTP account unregistered: {account.email_address}")
        except Exception as e:
            logger.error(f"Failed to unregister SMTP account: {e}")
