"""
Subscription Manager - Core System
Manages all active email account subscriptions across Gmail, Outlook, and SMTP.
Ensures each account is properly subscribed for real-time monitoring.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import get_logger
from shared.database import get_db_session
from shared.cache import get_redis

from models.email_account import EmailAccount, EmailProvider, ConnectionStatus
from models.email_provider_subscription import (
    EmailProviderSubscription,
    SubscriptionStatus
)
from provider.subscribers.gmail_subscriber import GmailSubscriber
from provider.subscribers.outlook_subscriber import OutlookSubscriber
from provider.subscribers.smtp_subscriber import SMTPSubscriber

logger = get_logger(__name__)


class SubscriptionManager:
    """
    Manages email provider subscriptions for real-time monitoring.
    Handles 10,000+ concurrent user accounts.
    """

    def __init__(self):
        self.gmail_subscriber = GmailSubscriber()
        self.outlook_subscriber = OutlookSubscriber()
        self.smtp_subscriber = SMTPSubscriber()

    async def sync_all_subscriptions(self) -> Dict[str, int]:
        """
        Sync subscriptions for all active email accounts.
        Each account is processed in its own DB session so one failure
        never poisons the transaction for other accounts.
        """
        logger.debug("Starting subscription sync for all accounts")

        stats = {"processed": 0, "created": 0, "renewed": 0, "failed": 0, "skipped": 0}

        # Fetch account IDs only — lightweight query, no session kept open
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount.id).where(
                    and_(
                        EmailAccount.is_active == True,
                        EmailAccount.connection_status == ConnectionStatus.CONNECTED,
                        EmailAccount.automation_enabled == True,
                    )
                )
            )
            account_ids = [row[0] for row in result.all()]

        logger.debug(f"Found {len(account_ids)} active accounts to sync")

        for account_id in account_ids:
            stats["processed"] += 1
            # Each account gets its own session — failure is fully isolated
            try:
                async with get_db_session() as session:
                    result = await session.execute(
                        select(EmailAccount).where(EmailAccount.id == account_id)
                    )
                    account = result.scalar_one_or_none()
                    if not account:
                        stats["skipped"] += 1
                        continue

                    outcome = await self.ensure_subscription(account, session)
                    await session.commit()

                if outcome == "created":
                    stats["created"] += 1
                elif outcome == "renewed":
                    stats["renewed"] += 1
                elif outcome in ("active", "skipped"):
                    stats["skipped"] += 1

            except NotImplementedError as e:
                # Expected in dev when public URL not configured (e.g. Outlook)
                logger.warning(f"Subscription skipped for account {account_id}: {e}")
                stats["skipped"] += 1
            except Exception as e:
                logger.error(f"Failed to sync subscription for account {account_id}: {e}")
                stats["failed"] += 1

        logger.debug(f"Subscription sync complete: {stats}")
        return stats

    async def ensure_subscription(
        self,
        account: EmailAccount,
        session: AsyncSession
    ) -> str:
        """
        Ensure a single account has an active subscription.
        Returns: "created", "renewed", "active", or "skipped"
        """
        # Check existing subscription
        result = await session.execute(
            select(EmailProviderSubscription).where(
                EmailProviderSubscription.email_account_id == account.id
            )
        )
        subscription = result.scalar_one_or_none()

        # If no subscription exists, create one
        if not subscription:
            return await self._create_subscription(account, session)

        # If subscription is active and not expiring soon, skip
        if subscription.status == SubscriptionStatus.ACTIVE:
            if subscription.expires_at:
                time_until_expiry = subscription.expires_at - datetime.utcnow()
                if time_until_expiry > timedelta(hours=24):
                    logger.debug(
                        f"Subscription for {account.email_address} is active, "
                        f"expires in {time_until_expiry}"
                    )
                    return "active"

        # Renew subscription
        return await self._renew_subscription(account, subscription, session)

    async def _create_subscription(
        self,
        account: EmailAccount,
        session: AsyncSession
    ) -> str:
        """
        Create a new subscription for an account.

        Provider isolation:
          GMAIL   → gmail.users.watch() → Google Pub/Sub → POST /webhooks/gmail
          OUTLOOK → Graph subscription  → Microsoft push → POST /webhooks/outlook
          SMTP    → Redis polling queue → SMTPPoller     → internal polling
        """
        logger.debug(
            f"Creating subscription for {account.email_address} "
            f"(provider={account.provider.value})"
        )

        try:
            if account.provider == EmailProvider.GMAIL:
                sub_data = await self.gmail_subscriber.subscribe(account)
            elif account.provider == EmailProvider.OUTLOOK:
                sub_data = await self.outlook_subscriber.subscribe(account, session)
            elif account.provider == EmailProvider.SMTP:
                sub_data = await self.smtp_subscriber.subscribe(account)
            else:
                logger.warning(
                    f"Unsupported provider '{account.provider.value}' "
                    f"for {account.email_address} — skipping"
                )
                return "skipped"

            # Flush any token updates the subscriber may have written
            await session.flush()

            subscription = EmailProviderSubscription(
                user_id=account.user_id,
                email_account_id=account.id,
                provider=account.provider.value,
                subscription_id=sub_data.get("subscription_id"),
                resource_id=sub_data.get("resource_id"),
                status=SubscriptionStatus.ACTIVE,
                expires_at=sub_data.get("expires_at"),
                last_checked_at=datetime.utcnow(),
            )

            session.add(subscription)
            await session.flush()

            await self._cache_subscription_mapping(subscription)

            logger.debug(
                f"Subscription created for {account.email_address} "
                f"[{account.provider.value}]: id={subscription.subscription_id}"
            )
            return "created"

        except NotImplementedError as e:
            logger.warning(
                f"Subscription skipped for {account.email_address} "
                f"[{account.provider.value}]: {e}"
            )
            return "skipped"

        except Exception as e:
            # Outlook 400 ValidationError (ngrok not reachable) is expected in dev
            err_str = str(e)
            if "ValidationError" in err_str or "400" in err_str:
                logger.warning(
                    f"Subscription skipped for {account.email_address} "
                    f"[{account.provider.value}] — webhook endpoint not reachable "
                    f"(set EMAIL_SERVICE_PUBLIC_URL to your ngrok URL): {err_str[:120]}"
                )
                return "skipped"
            logger.error(
                f"Failed to create subscription for {account.email_address} "
                f"[{account.provider.value}]: {e}"
            )
            raise

    async def _renew_subscription(
        self,
        account: EmailAccount,
        subscription: EmailProviderSubscription,
        session: AsyncSession
    ) -> str:
        """Renew an existing subscription."""
        logger.debug(f"Renewing subscription for {account.email_address}")

        try:
            # Route to appropriate subscriber
            if account.provider == EmailProvider.GMAIL:
                sub_data = await self.gmail_subscriber.renew(account, subscription)
            elif account.provider == EmailProvider.OUTLOOK:
                sub_data = await self.outlook_subscriber.renew(account, subscription, session)
            elif account.provider == EmailProvider.SMTP:
                sub_data = await self.smtp_subscriber.renew(account, subscription)
            else:
                return "skipped"

            # Update subscription record
            subscription.subscription_id = sub_data.get("subscription_id")
            subscription.resource_id = sub_data.get("resource_id")
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.expires_at = sub_data.get("expires_at")
            subscription.last_checked_at = datetime.utcnow()
            subscription.last_error = None
            subscription.error_count = "0"

            await session.flush()

            # Update cache
            await self._cache_subscription_mapping(subscription)

            logger.debug(f"Subscription renewed for {account.email_address}")
            return "renewed"

        except Exception as e:
            logger.error(f"Failed to renew subscription for {account.email_address}: {e}")
            subscription.status = SubscriptionStatus.FAILED
            subscription.last_error = str(e)
            subscription.error_count = str(int(subscription.error_count or "0") + 1)
            await session.flush()
            raise

    async def _cache_subscription_mapping(
        self,
        subscription: EmailProviderSubscription
    ):
        """Cache subscription mappings for O(1) lookup."""
        redis = await get_redis()

        account_id_str = str(subscription.email_account_id)
        user_id_str    = str(subscription.user_id)
        sub_id_str     = str(subscription.subscription_id) if subscription.subscription_id else ""

        # subscription_id -> email_account_id  (used by receiver to route events)
        if sub_id_str:
            await redis.setex(f"sub:id:{sub_id_str}", 86400, account_id_str)

        # email_account_id -> "subscription_id|user_id"  (used for quick lookups)
        await redis.setex(
            f"sub:account:{account_id_str}",
            86400,
            f"{sub_id_str}|{user_id_str}"
        )

    async def get_account_id_from_subscription(
        self,
        subscription_id: str
    ) -> Optional[str]:
        """
        O(1) lookup: subscription_id -> email_account_id
        Used by event receivers to identify which account received an email.
        """
        redis = await get_redis()
        account_id = await redis.get(f"sub:id:{subscription_id}")
        
        if account_id:
            return account_id.decode() if isinstance(account_id, bytes) else account_id
        
        # Cache miss - query database
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailProviderSubscription.email_account_id).where(
                    EmailProviderSubscription.subscription_id == subscription_id
                )
            )
            account_id = result.scalar_one_or_none()
            
            if account_id:
                # Populate cache
                await redis.setex(
                    f"sub:id:{subscription_id}",
                    86400,
                    str(account_id)
                )
            
            return str(account_id) if account_id else None

    async def remove_subscription(
        self,
        email_account_id: str
    ) -> bool:
        """Remove subscription when account is disconnected."""
        logger.debug(f"Removing subscription for account {email_account_id}")

        async with get_db_session() as session:
            result = await session.execute(
                select(EmailProviderSubscription).where(
                    EmailProviderSubscription.email_account_id == email_account_id
                )
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                return False

            # Unsubscribe from provider
            result = await session.execute(
                select(EmailAccount).where(EmailAccount.id == email_account_id)
            )
            account = result.scalar_one_or_none()

            if account:
                try:
                    if account.provider == EmailProvider.GMAIL:
                        await self.gmail_subscriber.unsubscribe(account, subscription)
                    elif account.provider == EmailProvider.OUTLOOK:
                        await self.outlook_subscriber.unsubscribe(account, subscription)
                    elif account.provider == EmailProvider.SMTP:
                        await self.smtp_subscriber.unsubscribe(account, subscription)
                except Exception as e:
                    logger.error(f"Failed to unsubscribe from provider: {e}")

            # Delete subscription record
            await session.delete(subscription)
            await session.commit()

            # Clear cache
            redis = await get_redis()
            if subscription.subscription_id:
                await redis.delete(f"sub:id:{subscription.subscription_id}")
            await redis.delete(f"sub:account:{email_account_id}")

            logger.debug(f"Subscription removed for account {email_account_id}")
            return True
