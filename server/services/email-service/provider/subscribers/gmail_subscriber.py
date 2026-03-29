"""
Gmail Subscriber - Gmail Pub/Sub Watch Management
Manages Gmail push notifications via Pub/Sub watch API.

Architecture for 10,000+ users:
  - Each connected Gmail account gets its own gmail.users.watch() call
  - All watches point to the SAME Pub/Sub topic
  - Google sends emailAddress in every notification → routes to correct account
  - Watches expire every 7 days → auto-renewed by SubscriptionScheduler
"""

from typing import Dict, Any
from datetime import datetime, timedelta
import httpx

from shared.logger import get_logger
from shared.config import get_config
from utils.encryption import decrypt_token, encrypt_token

logger = get_logger(__name__)
config = get_config()

_TOKEN_REFRESH_URL = "https://oauth2.googleapis.com/token"


class GmailSubscriber:
    """Manages Gmail Pub/Sub watch subscriptions per account."""

    GMAIL_WATCH_URL = "https://gmail.googleapis.com/gmail/v1/users/me/watch"
    GMAIL_STOP_URL  = "https://gmail.googleapis.com/gmail/v1/users/me/stop"

    async def subscribe(self, account) -> Dict[str, Any]:
        """
        Register a Gmail watch for this account.
        Google will push to our Pub/Sub topic whenever a new email arrives.
        The emailAddress field in the notification identifies which account it is.
        """
        logger.info(f"Registering Gmail watch for {account.email_address}")

        access_token = await self._get_valid_token(account)

        watch_request = {
            "topicName":         config.GMAIL_PUBSUB_TOPIC,
            "labelIds":          ["INBOX"],
            "labelFilterAction": "include",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                self.GMAIL_WATCH_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json=watch_request,
            )

        if response.status_code == 401:
            raise Exception(
                f"Gmail watch 401 for {account.email_address} — "
                "token invalid. Re-connect the account."
            )

        if response.status_code != 200:
            raise Exception(
                f"Gmail watch API error {response.status_code} "
                f"for {account.email_address}: {response.text}"
            )

        data = response.json()
        logger.info(
            f"Gmail watch registered for {account.email_address}: "
            f"historyId={data.get('historyId')}, "
            f"expiration={data.get('expiration')}"
        )

        # Gmail watch expires in exactly 7 days — renew 1 day early
        expires_at = datetime.utcnow() + timedelta(days=6)

        # Store historyId on account for gap recovery
        # This is the starting point for history sync after downtime
        if data.get("historyId"):
            account.last_history_id = str(data["historyId"])
        account.watch_expiry = expires_at

        return {
            "subscription_id": data.get("historyId"),
            "resource_id":     account.email_address,
            "expires_at":      expires_at,
        }

    async def renew(self, account, subscription) -> Dict[str, Any]:
        """Re-register the watch (Gmail has no explicit renewal — just re-watch)."""
        logger.info(f"Renewing Gmail watch for {account.email_address}")
        return await self.subscribe(account)

    async def unsubscribe(self, account, subscription) -> None:
        """Stop the Gmail watch for this account."""
        logger.info(f"Stopping Gmail watch for {account.email_address}")
        try:
            access_token = await self._get_valid_token(account)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.GMAIL_STOP_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if response.status_code == 204:
                logger.info(f"Gmail watch stopped for {account.email_address}")
            else:
                logger.warning(
                    f"Gmail stop returned {response.status_code} "
                    f"for {account.email_address}: {response.text}"
                )
        except Exception as e:
            logger.error(f"Failed to stop Gmail watch for {account.email_address}: {e}")

    # ── Token helpers ─────────────────────────────────────────────────────────

    async def _get_valid_token(self, account) -> str:
        """
        Return a valid (non-expired) access token.
        Refreshes automatically if expired or expiring within 5 minutes.
        Updates the account object in-place (caller must flush/commit the session).
        """
        now = datetime.utcnow()  # naive UTC — matches DB column type

        expiry = account.token_expiry
        if expiry is not None:
            # Normalise: strip tzinfo if somehow stored as aware
            if hasattr(expiry, 'tzinfo') and expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
            if expiry > now + timedelta(minutes=5):
                # Token still valid
                return decrypt_token(account.access_token)

        # Token expired or expiring soon — refresh
        if not account.refresh_token:
            logger.warning(
                f"Token expired for {account.email_address} and no refresh token. "
                "Using existing token (may fail)."
            )
            return decrypt_token(account.access_token)

        logger.info(f"Refreshing token for {account.email_address} before watch registration")
        new_token = await self._refresh_token(account)
        return new_token

    async def _refresh_token(self, account) -> str:
        """Call Google token endpoint and update account in-place."""
        try:
            refresh_token = decrypt_token(account.refresh_token)

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _TOKEN_REFRESH_URL,
                    data={
                        "client_id":     config.GOOGLE_CLIENT_ID_EMAIL,
                        "client_secret": config.GOOGLE_CLIENT_SECRET_EMAIL,
                        "refresh_token": refresh_token,
                        "grant_type":    "refresh_token",
                    },
                )

            if resp.status_code != 200:
                logger.error(
                    f"Token refresh failed for {account.email_address}: {resp.text}"
                )
                return decrypt_token(account.access_token)

            data       = resp.json()
            new_access = data.get("access_token")
            expires_in = data.get("expires_in", 3600)

            if not new_access:
                logger.error(f"Token refresh returned no access_token for {account.email_address}")
                return decrypt_token(account.access_token)

            # Update account object (caller must flush to DB)
            account.access_token = encrypt_token(new_access)
            # Store as naive UTC — DB column is TIMESTAMP WITHOUT TIME ZONE
            account.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

            logger.info(f"Token refreshed for {account.email_address}")
            return new_access

        except Exception as e:
            logger.error(f"Token refresh exception for {account.email_address}: {e}")
            return decrypt_token(account.access_token)
