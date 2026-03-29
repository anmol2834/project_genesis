"""
SMTP Poller - Periodic IMAP Polling
Polls SMTP/IMAP accounts for new emails at regular intervals.
"""

import asyncio
from typing import List
from datetime import datetime
from sqlalchemy import select, and_

from shared.logger import get_logger
from shared.database import get_db_session
from shared.cache import get_redis

from models.email_account import EmailAccount, EmailProvider, ConnectionStatus
from provider.receivers.smtp_receiver import SMTPReceiver

logger = get_logger(__name__)


class SMTPPoller:
    """Polls SMTP/IMAP accounts for new emails."""

    def __init__(self):
        self.receiver = SMTPReceiver()
        self.poll_interval = 300  # 5 minutes default
        self.is_running = False

    async def start_polling(self):
        """Start the polling loop."""
        if self.is_running:
            logger.warning("SMTP poller already running")
            return

        self.is_running = True
        logger.info("SMTP poller started")

        while self.is_running:
            try:
                await self._poll_all_accounts()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")

            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    async def stop_polling(self):
        """Stop the polling loop."""
        self.is_running = False
        logger.info("SMTP poller stopped")

    async def _poll_all_accounts(self):
        """Poll all registered SMTP accounts."""
        redis = await get_redis()

        # Get all registered SMTP accounts from Redis
        account_ids = await redis.smembers("smtp:polling:accounts")

        if not account_ids:
            logger.debug("No SMTP accounts registered for polling")
            return

        logger.info(f"Polling {len(account_ids)} SMTP accounts")

        async with get_db_session() as session:
            for account_id_bytes in account_ids:
                account_id = (
                    account_id_bytes.decode()
                    if isinstance(account_id_bytes, bytes)
                    else account_id_bytes
                )

                try:
                    # Check if account should be polled
                    if not await self._should_poll(account_id):
                        continue

                    # Fetch account from database
                    result = await session.execute(
                        select(EmailAccount).where(
                            and_(
                                EmailAccount.id == account_id,
                                EmailAccount.is_active == True,
                                EmailAccount.connection_status == ConnectionStatus.CONNECTED,
                                EmailAccount.provider == EmailProvider.SMTP
                            )
                        )
                    )
                    account = result.scalar_one_or_none()

                    if not account:
                        logger.warning(f"SMTP account not found or inactive: {account_id}")
                        # Remove from polling queue
                        await redis.srem("smtp:polling:accounts", account_id)
                        continue

                    # Poll account
                    await self._poll_account(account)

                except Exception as e:
                    logger.error(f"Failed to poll account {account_id}: {e}")

    async def _should_poll(self, account_id: str) -> bool:
        """Check if account should be polled based on last poll time."""
        redis = await get_redis()

        # Get last poll time
        last_poll = await redis.hget(f"smtp:account:{account_id}", "last_poll")

        if not last_poll:
            return True

        last_poll_time = int(last_poll)
        current_time = int(datetime.utcnow().timestamp())

        # Get poll interval for this account
        interval = await redis.hget(f"smtp:account:{account_id}", "poll_interval")
        poll_interval = int(interval) if interval else self.poll_interval

        # Check if enough time has passed
        return (current_time - last_poll_time) >= poll_interval

    async def _poll_account(self, account):
        """Poll a single SMTP account."""
        logger.info(f"Polling SMTP account: {account.email_address}")

        try:
            # Poll for new emails
            events = await self.receiver.poll_account(account)

            if events:
                logger.info(
                    f"Found {len(events)} new emails for {account.email_address}"
                )
                # TODO: Forward events to next layer (queue)
                # For now, just log them
                for event in events:
                    logger.info(f"New email event: {event}")

            # Update last poll time
            redis = await get_redis()
            await redis.hset(
                f"smtp:account:{account.id}",
                "last_poll",
                str(int(datetime.utcnow().timestamp()))
            )

        except Exception as e:
            logger.error(f"Failed to poll {account.email_address}: {e}")

    async def poll_account_now(self, account_id: str) -> List[dict]:
        """
        Manually trigger polling for a specific account.
        Used for testing or immediate sync.
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(EmailAccount.id == account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                logger.warning(f"Account not found: {account_id}")
                return []

            return await self.receiver.poll_account(account)
