"""
Outlook Subscriber - Microsoft Graph Webhook Management

Architecture:
  - Each Outlook account registers its own Graph subscription (webhook)
  - Microsoft pushes to POST /webhooks/outlook when new mail arrives
  - Subscriptions expire every ~3 days — auto-renewed by SubscriptionScheduler
  - Token refresh handled automatically before every API call
  - COMPLETELY SEPARATE from Gmail Pub/Sub — no cross-provider contamination

Provider isolation guarantee:
  - GmailSubscriber  → only called for EmailProvider.GMAIL accounts
  - OutlookSubscriber → only called for EmailProvider.OUTLOOK accounts
  - SMTPSubscriber   → only called for EmailProvider.SMTP accounts
  The SubscriptionManager enforces this routing — never cross-wires providers.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

from shared.logger import get_logger
from shared.config import get_config
from utils.encryption import decrypt_token, encrypt_token

logger = get_logger(__name__)
config = get_config()

_MS_TOKEN_URL            = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_GRAPH_SUBSCRIPTIONS_URL = "https://graph.microsoft.com/v1.0/subscriptions"


class OutlookSubscriber:
    """Manages Microsoft Graph webhook subscriptions per Outlook account."""

    async def subscribe(self, account, session=None) -> Dict[str, Any]:
        """
        Register a Microsoft Graph webhook for this Outlook account.
        Microsoft will POST to /webhooks/outlook when new mail arrives.

        Args:
            account: EmailAccount ORM object
            session: Optional SQLAlchemy AsyncSession — if provided, refreshed
                     tokens are flushed to DB immediately.

        Raises:
            Exception: if Graph API returns an error
            NotImplementedError: if public URL is not configured (localhost)
        """
        webhook_url = self._get_webhook_url()

        # Guard: Microsoft Graph cannot reach localhost — skip gracefully
        if any(x in webhook_url for x in ["localhost", "127.0.0.1", "0.0.0.0"]):
            logger.warning(
                f"Skipping Outlook subscription for {account.email_address} — "
                f"EMAIL_SERVICE_PUBLIC_URL is set to a local address ({webhook_url}). "
                "Set it to your ngrok/public URL to enable Outlook push notifications."
            )
            raise NotImplementedError(
                f"Outlook webhooks require a public URL. "
                f"Current EMAIL_SERVICE_PUBLIC_URL resolves to: {webhook_url}. "
                "Update it in server/.env to your ngrok URL."
            )

        logger.info(f"Registering Outlook Graph subscription for {account.email_address}")

        access_token = await self._get_valid_token(account, session)

        # Graph mail subscriptions expire in max 4230 minutes (~2.9 days)
        expiration_datetime = datetime.utcnow() + timedelta(days=2, hours=12)

        subscription_request = {
            "changeType":         "created",
            "notificationUrl":    self._get_webhook_url(),
            "resource":           "me/mailFolders('Inbox')/messages",
            "expirationDateTime": expiration_datetime.isoformat() + "Z",
            "clientState":        str(account.id),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                _GRAPH_SUBSCRIPTIONS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type":  "application/json",
                },
                json=subscription_request,
            )

        if response.status_code == 401:
            raise Exception(
                f"Outlook Graph 401 for {account.email_address} — "
                "token invalid or expired. Re-connect the account."
            )

        if response.status_code not in [200, 201]:
            raise Exception(
                f"Outlook Graph API error {response.status_code} "
                f"for {account.email_address}: {response.text}"
            )

        data = response.json()
        logger.info(
            f"Outlook subscription registered for {account.email_address}: "
            f"id={data.get('id')}, expires={data.get('expirationDateTime')}"
        )

        return {
            "subscription_id": data.get("id"),
            "resource_id":     data.get("resource"),
            "expires_at":      expiration_datetime,
        }

    async def renew(self, account, subscription, session=None) -> Dict[str, Any]:
        """Extend an existing Graph subscription."""
        logger.info(f"Renewing Outlook subscription for {account.email_address}")

        access_token   = await self._get_valid_token(account, session)
        new_expiration = datetime.utcnow() + timedelta(days=2, hours=12)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.patch(
                f"{_GRAPH_SUBSCRIPTIONS_URL}/{subscription.subscription_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type":  "application/json",
                },
                json={"expirationDateTime": new_expiration.isoformat() + "Z"},
            )

        if response.status_code != 200:
            logger.warning(
                f"Outlook renewal failed ({response.status_code}) for "
                f"{account.email_address} — creating new subscription"
            )
            return await self.subscribe(account, session)

        data = response.json()
        return {
            "subscription_id": data.get("id"),
            "resource_id":     data.get("resource"),
            "expires_at":      new_expiration,
        }

    async def unsubscribe(self, account, subscription, session=None) -> None:
        """Delete the Graph subscription."""
        logger.info(f"Deleting Outlook subscription for {account.email_address}")
        try:
            access_token = await self._get_valid_token(account, session)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{_GRAPH_SUBSCRIPTIONS_URL}/{subscription.subscription_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if response.status_code == 204:
                logger.info(f"Outlook subscription deleted for {account.email_address}")
            else:
                logger.warning(
                    f"Outlook delete returned {response.status_code} "
                    f"for {account.email_address}: {response.text}"
                )
        except Exception as e:
            logger.error(f"Failed to delete Outlook subscription for {account.email_address}: {e}")

    # ── Token management ──────────────────────────────────────────────────────

    async def _get_valid_token(self, account, session=None) -> str:
        """
        Return a valid (non-expired) Microsoft Graph access token.
        Refreshes automatically if expired or expiring within 5 minutes.
        If session is provided, flushes the updated token to DB immediately.
        """
        now    = datetime.utcnow()  # naive UTC — matches DB column type
        expiry = account.token_expiry

        if expiry is not None:
            # Normalise: strip tzinfo if somehow stored as aware
            if hasattr(expiry, 'tzinfo') and expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
            if expiry > now + timedelta(minutes=5):
                # Token still valid
                return decrypt_token(account.access_token)

        # Token expired or expiring soon
        if not account.refresh_token:
            logger.warning(
                f"Outlook token expired for {account.email_address} "
                "and no refresh token available. Using existing token (may fail)."
            )
            return decrypt_token(account.access_token)

        logger.info(f"Refreshing Outlook token for {account.email_address}")
        new_token = await self._refresh_token(account)

        # Persist the refreshed token to DB if we have a session
        if session is not None:
            try:
                await session.flush()
                logger.debug(f"Refreshed Outlook token flushed to DB for {account.email_address}")
            except Exception as e:
                logger.error(f"Failed to flush refreshed token for {account.email_address}: {e}")

        return new_token

    async def _refresh_token(self, account) -> str:
        """
        Call Microsoft token endpoint and update account object in-place.
        Returns the new raw access token string.
        """
        try:
            tenant        = config.MICROSOFT_TENANT_ID_EMAIL or "common"
            token_url     = _MS_TOKEN_URL.format(tenant=tenant)
            refresh_token = decrypt_token(account.refresh_token)

            logger.debug(
                f"Calling Microsoft token endpoint for {account.email_address} "
                f"(tenant={tenant}, client_id={config.MICROSOFT_CLIENT_ID_EMAIL})"
            )

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    token_url,
                    data={
                        "client_id":     config.MICROSOFT_CLIENT_ID_EMAIL,
                        "client_secret": config.MICROSOFT_CLIENT_SECRET_EMAIL,
                        "refresh_token": refresh_token,
                        "grant_type":    "refresh_token",
                        "scope": (
                            "https://graph.microsoft.com/Mail.Send "
                            "https://graph.microsoft.com/Mail.Read "
                            "https://graph.microsoft.com/User.Read "
                            "offline_access"
                        ),
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if resp.status_code != 200:
                logger.error(
                    f"Outlook token refresh failed for {account.email_address} "
                    f"({resp.status_code}): {resp.text}"
                )
                # Fall back to existing token — caller will get a 401 from Graph
                # and the error will surface clearly
                return decrypt_token(account.access_token)

            data       = resp.json()
            new_access = data.get("access_token")
            expires_in = data.get("expires_in", 3600)

            if not new_access:
                logger.error(
                    f"Outlook token refresh returned no access_token "
                    f"for {account.email_address}. Response: {data}"
                )
                return decrypt_token(account.access_token)

            # Update account object in-place
            account.access_token = encrypt_token(new_access)
            # Store as naive UTC — DB column is TIMESTAMP WITHOUT TIME ZONE
            account.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

            # Rotate refresh token if Microsoft issued a new one
            new_refresh = data.get("refresh_token")
            if new_refresh:
                account.refresh_token = encrypt_token(new_refresh)
                logger.debug(f"Outlook refresh token rotated for {account.email_address}")

            logger.info(
                f"Outlook token refreshed for {account.email_address} "
                f"(expires_in={expires_in}s)"
            )
            return new_access

        except Exception as e:
            logger.error(
                f"Outlook token refresh exception for {account.email_address}: {e}",
                exc_info=True
            )
            return decrypt_token(account.access_token)

    def _get_webhook_url(self) -> str:
        """Public URL that Microsoft Graph will POST notifications to."""
        return config.EMAIL_SERVICE_PUBLIC_URL.rstrip("/") + "/webhooks/outlook"
