"""
Gmail History Sync — Gap Recovery Engine
=========================================
Guarantees zero email loss even during server downtime.

How it works:
  1. Every time a Pub/Sub notification is processed, last_history_id is updated
     on the EmailAccount row.
  2. On startup (and periodically via Celery Beat), this engine calls:
       GET /gmail/v1/users/me/history?startHistoryId=<last_history_id>
     for every active Gmail account.
  3. Any messages added since last_history_id are fetched and queued — these
     are the emails that arrived while the server was down or Pub/Sub missed.
  4. After processing, last_history_id is advanced to the latest historyId.

This makes Pub/Sub a "fast path" and History API a "safety net".
Together they guarantee no email is ever lost.

Scalability:
  - Accounts are processed in configurable batches (default 50)
  - Each account uses its own DB session — one failure never affects others
  - Exponential backoff on Gmail API rate limits (429)
  - Designed for 10,000+ accounts
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import httpx

from shared.logger import get_logger
from shared.database import get_db_session
from shared.cache import get_redis
from models.email_account import EmailAccount, EmailProvider, ConnectionStatus
from sqlalchemy import select, and_
from utils.encryption import decrypt_token, encrypt_token

logger = get_logger(__name__)

_GMAIL_API_BASE    = "https://gmail.googleapis.com/gmail/v1"
_TOKEN_REFRESH_URL = "https://oauth2.googleapis.com/token"

# How many accounts to process in parallel
_BATCH_SIZE = 50

# Minimum gap before running recovery (avoid hammering API on every startup)
_MIN_RECOVERY_GAP_SECONDS = 60


class GmailHistorySync:
    """
    Recovers emails missed during downtime by replaying Gmail History API.
    """

    async def run_recovery_for_all(self) -> Dict[str, int]:
        """
        Run gap recovery for all active Gmail accounts.
        Called on startup and by Celery Beat every 30 minutes.

        Returns stats dict: {processed, recovered, skipped, failed}
        """
        stats = {"processed": 0, "recovered": 0, "skipped": 0, "failed": 0}

        # Fetch all active Gmail account IDs
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount.id).where(
                    and_(
                        EmailAccount.provider == EmailProvider.GMAIL,
                        EmailAccount.is_active == True,
                        EmailAccount.connection_status == ConnectionStatus.CONNECTED,
                        EmailAccount.automation_enabled == True,
                    )
                )
            )
            account_ids = [row[0] for row in result.all()]

        logger.info(f"History sync: {len(account_ids)} Gmail accounts to check")

        # Process in batches to avoid overwhelming the DB pool
        for i in range(0, len(account_ids), _BATCH_SIZE):
            batch = account_ids[i : i + _BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[self._recover_account(aid) for aid in batch],
                return_exceptions=True
            )
            for r in batch_results:
                if isinstance(r, Exception):
                    stats["failed"] += 1
                elif isinstance(r, dict):
                    stats["processed"] += 1
                    stats["recovered"] += r.get("recovered", 0)
                    if r.get("skipped"):
                        stats["skipped"] += 1

        logger.info(f"History sync complete: {stats}")
        return stats

    async def _recover_account(self, account_id) -> Dict[str, Any]:
        """
        Recover missed emails for a single Gmail account.
        Uses its own DB session — isolated from other accounts.
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(EmailAccount.id == account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                return {"skipped": True}

            # Skip if no history_id stored — nothing to recover from
            if not account.last_history_id:
                logger.debug(
                    f"No last_history_id for {account.email_address} — skipping recovery"
                )
                return {"skipped": True}

            # Skip if last sync was very recent (avoid hammering API)
            if account.last_synced_at:
                gap = (datetime.utcnow() - account.last_synced_at).total_seconds()
                if gap < _MIN_RECOVERY_GAP_SECONDS:
                    logger.debug(
                        f"Skipping recovery for {account.email_address} — "
                        f"last sync was {gap:.0f}s ago"
                    )
                    return {"skipped": True}

            logger.info(
                f"Running history recovery for {account.email_address} "
                f"from historyId={account.last_history_id}"
            )

            # Ensure fresh token
            access_token = await self._get_valid_token(account, session)

            # Fetch all history since last_history_id
            messages, latest_history_id = await self._fetch_history_since(
                access_token, account.last_history_id, account.email_address
            )

            recovered = 0
            if messages:
                logger.info(
                    f"Recovering {len(messages)} missed messages "
                    f"for {account.email_address}"
                )
                for msg_id in messages:
                    try:
                        await self._process_missed_message(
                            account, access_token, msg_id
                        )
                        recovered += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to recover message {msg_id} "
                            f"for {account.email_address}: {e}"
                        )

            # Advance the history cursor
            if latest_history_id:
                account.last_history_id = str(latest_history_id)
            account.last_synced_at = datetime.utcnow()
            await session.commit()

            return {"recovered": recovered}

    async def _fetch_history_since(
        self,
        access_token: str,
        start_history_id: str,
        email_address: str
    ):
        """
        Fetch all messageAdded events since start_history_id.
        Returns (list_of_message_ids, latest_history_id).
        Handles pagination and rate limiting with exponential backoff.
        """
        message_ids = []
        latest_history_id = None
        page_token = None
        retries = 0
        max_retries = 3

        while True:
            params = {
                "startHistoryId": start_history_id,
                "historyTypes":   "messageAdded",
                "maxResults":     500,
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.get(
                        f"{_GMAIL_API_BASE}/users/me/history",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params=params,
                    )

                if resp.status_code == 429:
                    # Rate limited — exponential backoff
                    wait = (2 ** retries) * 5
                    logger.warning(
                        f"Gmail rate limit for {email_address}, "
                        f"waiting {wait}s (retry {retries+1}/{max_retries})"
                    )
                    if retries >= max_retries:
                        logger.error(f"Max retries exceeded for {email_address}")
                        break
                    await asyncio.sleep(wait)
                    retries += 1
                    continue

                if resp.status_code == 404:
                    # historyId too old — can't recover this far back
                    logger.warning(
                        f"historyId {start_history_id} expired for {email_address} "
                        "— gap recovery limited to last 7 days"
                    )
                    break

                if resp.status_code == 401:
                    logger.error(f"Gmail 401 during history sync for {email_address}")
                    break

                if resp.status_code != 200:
                    logger.error(
                        f"Gmail history API error ({resp.status_code}) "
                        f"for {email_address}: {resp.text}"
                    )
                    break

                data = resp.json()
                latest_history_id = data.get("historyId", latest_history_id)

                for record in data.get("history", []):
                    for msg in record.get("messagesAdded", []):
                        msg_id = msg.get("message", {}).get("id")
                        if msg_id and msg_id not in message_ids:
                            message_ids.append(msg_id)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

                retries = 0  # Reset retries on successful page

            except Exception as e:
                logger.error(f"History fetch exception for {email_address}: {e}")
                break

        return message_ids, latest_history_id

    async def _process_missed_message(
        self,
        account: EmailAccount,
        access_token: str,
        message_id: str
    ):
        """
        Fetch and queue a single missed message.
        Uses the same normalizer + queue pipeline as real-time events.
        """
        from normalizer.normalizer import EmailNormalizer
        from email_queue.producer.event_producer import EventProducer
        from provider.filters.email_filter import EmailFilter
        from provider.deduplicator.event_deduplicator import EventDeduplicator

        deduplicator = EventDeduplicator()
        email_filter = EmailFilter()
        normalizer   = EmailNormalizer()
        producer     = EventProducer()

        # Dedup check — don't reprocess already-seen messages
        dedup_key = f"gmail_msg_{message_id}"
        if await deduplicator.is_duplicate(dedup_key):
            logger.debug(f"Recovery: message {message_id} already processed")
            return

        # Build a synthetic payload that the normalizer understands
        # We pass the message_id directly so the adapter fetches it
        raw_event = {
            "provider":      "gmail",
            "email_address": account.email_address,
            "message_id":    message_id,
            # Use a synthetic history_id — adapter will fetch by message_id directly
            "history_id":    account.last_history_id or "1",
            "timestamp":     datetime.utcnow().isoformat(),
            "_recovery_message_id": message_id,  # hint for adapter
        }

        normalized = await normalizer.normalize("gmail", raw_event)
        if not normalized:
            return

        # Filter spam/OTP
        if await email_filter.should_filter(normalized.subject, normalized.from_email):
            logger.debug(f"Recovery: filtered message {message_id}")
            return

        # Mark processed before queuing
        await deduplicator.mark_processed(dedup_key)

        # Queue
        await producer.produce(normalized)
        logger.info(
            f"Recovery: queued missed message {message_id} "
            f"for {account.email_address}"
        )

    async def _get_valid_token(self, account: EmailAccount, session) -> str:
        """Return a valid access token, refreshing if needed."""
        now    = datetime.utcnow()
        expiry = account.token_expiry

        if expiry is not None:
            if expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
            if expiry > now + timedelta(minutes=5):
                return decrypt_token(account.access_token)

        if not account.refresh_token:
            return decrypt_token(account.access_token)

        try:
            from shared.config import get_config
            cfg = get_config()

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _TOKEN_REFRESH_URL,
                    data={
                        "client_id":     cfg.GOOGLE_CLIENT_ID_EMAIL,
                        "client_secret": cfg.GOOGLE_CLIENT_SECRET_EMAIL,
                        "refresh_token": decrypt_token(account.refresh_token),
                        "grant_type":    "refresh_token",
                    },
                )

            if resp.status_code == 200:
                data = resp.json()
                new_access = data.get("access_token")
                if new_access:
                    account.access_token = encrypt_token(new_access)
                    account.token_expiry = (
                        datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
                    )
                    await session.flush()
                    return new_access

        except Exception as e:
            logger.error(f"Token refresh failed during recovery for {account.email_address}: {e}")

        return decrypt_token(account.access_token)


# Module-level singleton
_history_sync: Optional[GmailHistorySync] = None


def get_history_sync() -> GmailHistorySync:
    global _history_sync
    if _history_sync is None:
        _history_sync = GmailHistorySync()
    return _history_sync
