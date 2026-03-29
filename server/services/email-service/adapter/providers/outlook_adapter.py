"""
Outlook Event Adapter
Parses Microsoft Graph webhook notifications and fetches full email details.
Handles token refresh automatically.

Provider isolation:
  - This adapter is ONLY used for Outlook/Microsoft accounts
  - Gmail accounts use GmailEventAdapter exclusively
  - SMTP accounts use SMTPEventAdapter exclusively
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
import re

from shared.logger import get_logger
from shared.database import get_db_session
from models.email_account import EmailAccount
from sqlalchemy import select
from utils.encryption import decrypt_token, encrypt_token
from adapter.base_adapter import BaseAdapter

logger = get_logger(__name__)

_GRAPH_API_BASE    = "https://graph.microsoft.com/v1.0"
_MS_TOKEN_URL      = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


class OutlookEventAdapter(BaseAdapter):
    """Adapter for Outlook Graph webhook events."""

    async def parse(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Outlook webhook payload.
        Graph only sends message ID — we fetch the full message.
        Returns None when message cannot be fetched (not an error).
        """
        message_id      = payload.get("message_id")
        subscription_id = payload.get("subscription_id")

        if not message_id or not subscription_id:
            raise ValueError("Outlook payload missing message_id or subscription_id")

        # Resolve account from subscription_id
        from provider.manager.subscription_manager import SubscriptionManager
        manager    = SubscriptionManager()
        account_id = await manager.get_account_id_from_subscription(subscription_id)

        if not account_id:
            logger.warning(f"No account found for Outlook subscription: {subscription_id}")
            return None

        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(EmailAccount.id == account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                logger.warning(f"Email account not found: {account_id}")
                return None

            # Ensure fresh token before API call
            access_token = await self._get_valid_token(account, session)
            message_data = await self._fetch_message_details(access_token, message_id)
            return message_data

    # ── Token management ──────────────────────────────────────────────────────

    async def _get_valid_token(self, account: EmailAccount, session) -> str:
        """Return a valid access token, refreshing if needed."""
        now    = datetime.utcnow()
        expiry = account.token_expiry

        if expiry is not None:
            if hasattr(expiry, 'tzinfo') and expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
            if expiry > now + timedelta(minutes=5):
                return decrypt_token(account.access_token)

        if not account.refresh_token:
            logger.warning(f"Outlook token expired for {account.email_address}, no refresh token")
            return decrypt_token(account.access_token)

        return await self._refresh_token(account, session)

    async def _refresh_token(self, account: EmailAccount, session) -> str:
        """Refresh Microsoft token and persist to DB."""
        try:
            from shared.config import get_config
            cfg    = get_config()
            tenant = cfg.MICROSOFT_TENANT_ID_EMAIL or "common"

            refresh_token = decrypt_token(account.refresh_token)

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _MS_TOKEN_URL.format(tenant=tenant),
                    data={
                        "client_id":     cfg.MICROSOFT_CLIENT_ID_EMAIL,
                        "client_secret": cfg.MICROSOFT_CLIENT_SECRET_EMAIL,
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
                logger.error(f"Outlook token refresh failed: {resp.text}")
                return decrypt_token(account.access_token)

            data       = resp.json()
            new_access = data.get("access_token")
            expires_in = data.get("expires_in", 3600)

            if not new_access:
                return decrypt_token(account.access_token)

            account.access_token = encrypt_token(new_access)
            account.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

            new_refresh = data.get("refresh_token")
            if new_refresh:
                account.refresh_token = encrypt_token(new_refresh)

            await session.flush()
            logger.info(f"Outlook token refreshed for {account.email_address}")
            return new_access

        except Exception as e:
            logger.error(f"Outlook token refresh exception: {e}")
            return decrypt_token(account.access_token)

    # ── Message fetching ──────────────────────────────────────────────────────

    async def _fetch_message_details(
        self,
        access_token: str,
        message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch full message from Microsoft Graph API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_GRAPH_API_BASE}/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.status_code == 401:
            logger.error(f"Graph 401 fetching message {message_id} — token expired")
            return None

        if response.status_code != 200:
            logger.error(f"Graph message fetch failed ({response.status_code}): {response.text}")
            return None

        message = response.json()

        # Parse timestamp — Graph returns ISO 8601 with Z
        timestamp_str = message.get("receivedDateTime") or message.get("sentDateTime", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            # Store as naive UTC for DB consistency
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
        except Exception:
            timestamp = datetime.utcnow()

        # Extract body
        body         = message.get("body", {})
        content_html = body.get("content", "")
        content_type = body.get("contentType", "text")
        content      = self._html_to_text(content_html) if content_type == "html" else content_html

        if not content:
            content = message.get("bodyPreview", "(no content)")

        # Parse recipients
        to_emails  = [r["emailAddress"]["address"] for r in message.get("toRecipients",  [])]
        cc_emails  = [r["emailAddress"]["address"] for r in message.get("ccRecipients",  [])]
        bcc_emails = [r["emailAddress"]["address"] for r in message.get("bccRecipients", [])]

        from_data  = message.get("from", {}).get("emailAddress", {})
        from_email = from_data.get("address", "")

        return {
            "message_id":      message.get("id"),
            "thread_id":       message.get("conversationId"),
            "subject":         message.get("subject", "(No Subject)"),
            "from_email":      from_email,
            "to_emails":       to_emails,
            "cc_emails":       cc_emails,
            "bcc_emails":      bcc_emails,
            "content":         content,
            "content_html":    content_html if content_type == "html" else None,
            "timestamp":       timestamp,
            "has_attachments": message.get("hasAttachments", False),
            "provider_data": {
                "conversation_id": message.get("conversationId"),
                "importance":      message.get("importance"),
                "is_read":         message.get("isRead", False),
                "categories":      message.get("categories", []),
            },
        }

    def _html_to_text(self, html: str) -> str:
        if not html:
            return ""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', html)
        text = (text.replace('&nbsp;', ' ').replace('&lt;', '<')
                    .replace('&gt;', '>').replace('&amp;', '&')
                    .replace('&quot;', '"').replace('&#39;', "'"))
        return re.sub(r'\s+', ' ', text).strip()
