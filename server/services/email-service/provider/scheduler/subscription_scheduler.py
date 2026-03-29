"""
Subscription Scheduler - Auto-Renewal System
Periodically checks and renews expiring subscriptions.
Ensures no subscription ever expires.
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, and_

from shared.logger import get_logger
from shared.database import get_db_session

from models.email_provider_subscription import (
    EmailProviderSubscription,
    SubscriptionStatus
)
from provider.manager.subscription_manager import SubscriptionManager

logger = get_logger(__name__)


class SubscriptionScheduler:
    """Manages subscription renewal scheduling."""

    def __init__(self):
        self.manager = SubscriptionManager()
        self.check_interval = 3600  # Check every hour
        self.renewal_threshold = timedelta(hours=24)  # Renew 24h before expiry
        self.is_running = False

    async def start_scheduler(self):
        """Start the renewal scheduler."""
        if self.is_running:
            logger.warning("Subscription scheduler already running")
            return

        self.is_running = True
        logger.info("Subscription scheduler started")

        while self.is_running:
            try:
                await self._check_and_renew()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            # Wait before next check
            await asyncio.sleep(self.check_interval)

    async def stop_scheduler(self):
        """Stop the renewal scheduler."""
        self.is_running = False
        logger.info("Subscription scheduler stopped")

    async def _check_and_renew(self):
        """Check for expiring subscriptions and renew them."""
        logger.info("Checking for expiring subscriptions")

        renewal_cutoff = datetime.utcnow() + self.renewal_threshold

        async with get_db_session() as session:
            # Find subscriptions expiring soon
            result = await session.execute(
                select(EmailProviderSubscription).where(
                    and_(
                        EmailProviderSubscription.status == SubscriptionStatus.ACTIVE,
                        EmailProviderSubscription.expires_at <= renewal_cutoff
                    )
                )
            )
            expiring_subscriptions = result.scalars().all()

            if not expiring_subscriptions:
                logger.debug("No subscriptions need renewal")
                return

            logger.info(f"Found {len(expiring_subscriptions)} subscriptions to renew")

            renewed = 0
            failed = 0

            for subscription in expiring_subscriptions:
                try:
                    # Fetch associated account
                    from models.email_account import EmailAccount
                    result = await session.execute(
                        select(EmailAccount).where(
                            EmailAccount.id == subscription.email_account_id
                        )
                    )
                    account = result.scalar_one_or_none()

                    if not account:
                        logger.warning(
                            f"Account not found for subscription {subscription.id}"
                        )
                        continue

                    # Renew subscription
                    await self.manager._renew_subscription(account, subscription, session)
                    renewed += 1

                except Exception as e:
                    logger.error(
                        f"Failed to renew subscription {subscription.id}: {e}"
                    )
                    failed += 1

            await session.commit()

            logger.info(
                f"Subscription renewal complete: {renewed} renewed, {failed} failed"
            )

    async def check_subscription_health(self) -> dict:
        """
        Check overall subscription health.
        Returns statistics about subscription status.
        """
        async with get_db_session() as session:
            # Count by status
            result = await session.execute(
                select(EmailProviderSubscription)
            )
            subscriptions = result.scalars().all()

            stats = {
                "total": len(subscriptions),
                "active": 0,
                "expired": 0,
                "failed": 0,
                "expiring_soon": 0
            }

            expiry_threshold = datetime.utcnow() + self.renewal_threshold

            for sub in subscriptions:
                if sub.status == SubscriptionStatus.ACTIVE:
                    stats["active"] += 1
                    if sub.expires_at and sub.expires_at <= expiry_threshold:
                        stats["expiring_soon"] += 1
                elif sub.status == SubscriptionStatus.EXPIRED:
                    stats["expired"] += 1
                elif sub.status == SubscriptionStatus.FAILED:
                    stats["failed"] += 1

            return stats

    async def force_renewal_check(self):
        """Manually trigger renewal check (for testing/debugging)."""
        logger.info("Manual renewal check triggered")
        await self._check_and_renew()
