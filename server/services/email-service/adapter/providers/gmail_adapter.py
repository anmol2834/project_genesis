"""
Gmail Event Adapter
Parses Gmail Pub/Sub notifications and fetches full email details.

Multi-account design:
  - Shared Pub/Sub topic for ALL Gmail accounts
  - Google sends emailAddress in every notification → routes to correct account
  - Only accounts in email_accounts table are processed
  - Unknown emailAddresses (old watches) are silently acknowledged → HTTP 200
  - history_id is updated on every successful fetch for gap recovery
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta   # single top-level import — NEVER re-import inside methods
import httpx
import base64
import re

from shared.logger import get_logger
from shared.database import get_db_session
from models.email_account import EmailAccount
from sqlalchemy import select
from utils.encryption import decrypt_token, encrypt_token
from adapter.base_adapter import BaseAdapter

logger = get_logger(__name__)

_GMAIL_API_BASE    = "https://gmail.googleapis.com/gmail/v1"
_TOKEN_REFRESH_URL = "https://oauth2.googleapis.com/token"


class GmailEventAdapter(BaseAdapter):
    """Adapter for Gmail Pub/Sub events. Handles any number of Gmail accounts."""

    async def parse(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Gmail Pub/Sub payload.

        Gmail Pub/Sub sends the CURRENT historyId (the new watermark), not the
        previous one. To fetch what changed, we must call History API with
        startHistoryId = PREVIOUS historyId (stored in account.last_history_id).

        Flow:
          1. Extract emailAddress + new historyId from Pub/Sub
          2. Look up account — unknown accounts silently ignored
          3. Determine startHistoryId:
               - Use account.last_history_id if available (correct approach)
               - Fall back to (incoming historyId - 1) if no stored value
          4. Refresh token if expired
          5. Fetch messages added since startHistoryId
          6. Update last_history_id to the incoming historyId (advance cursor)
        """
        email_address    = payload.get("email_address")
        new_history_id   = payload.get("history_id")   # current watermark from Pub/Sub

        if not email_address or not new_history_id:
            raise ValueError("Gmail payload missing email_address or history_id")

        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(
                    EmailAccount.email_address == email_address
                )
            )
            account = result.scalar_one_or_none()

            if not account:
                logger.warning(
                    f"Pub/Sub notification for unknown account: {email_address}. "
                    "Watch likely from a previous project — expires in ≤7 days. "
                    "To stop immediately: POST /subscriptions/stop-unknown-watch"
                )
                return None

            # Determine the correct startHistoryId:
            # Pub/Sub sends the NEW historyId (current state).
            # History API needs the PREVIOUS historyId to return what changed.
            # account.last_history_id is the last value we processed — use that.
            stored_history_id = account.last_history_id
            if stored_history_id and str(stored_history_id) != str(new_history_id):
                start_history_id = stored_history_id
                logger.info(
                    f"Gmail history fetch: email={email_address} "
                    f"start={start_history_id} → new={new_history_id}"
                )
            else:
                # No stored value or same as incoming — use subscription historyId
                # as fallback, or subtract 1 from incoming as last resort
                start_history_id = str(int(new_history_id) - 1)
                logger.info(
                    f"Gmail history fetch (no prior cursor): email={email_address} "
                    f"start={start_history_id} (derived from new={new_history_id})"
                )

            # Ensure fresh token before any API call
            account = await self._ensure_fresh_token(account, session)

            # Fetch messages added since start_history_id
            message_data = await self._fetch_latest_message(account, start_history_id)

            # Advance the cursor to the new historyId regardless of result
            account.last_history_id = str(new_history_id)
            await session.flush()

            return message_data

    # ── Token management ──────────────────────────────────────────────────────

    async def _ensure_fresh_token(
        self,
        account: EmailAccount,
        session
    ) -> EmailAccount:
        """
        Ensure account has a valid access token.
        Refreshes if expired or expiring within 5 minutes.
        All datetime comparisons use naive UTC to match DB column type.
        """
        now    = datetime.utcnow()   # naive UTC — matches TIMESTAMP WITHOUT TIME ZONE
        expiry = account.token_expiry

        if expiry is not None:
            # Strip tzinfo if somehow stored as aware (defensive)
            if expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
            # Token still valid — return immediately
            if expiry > now + timedelta(minutes=5):
                return account

        if not account.refresh_token:
            logger.warning(
                f"Token expired for {account.email_address}, no refresh token available"
            )
            return account

        logger.info(f"Refreshing access token for {account.email_address}")

        try:
            from shared.config import get_config
            cfg = get_config()

            refresh_token_plain = decrypt_token(account.refresh_token)

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _TOKEN_REFRESH_URL,
                    data={
                        "client_id":     cfg.GOOGLE_CLIENT_ID_EMAIL,
                        "client_secret": cfg.GOOGLE_CLIENT_SECRET_EMAIL,
                        "refresh_token": refresh_token_plain,
                        "grant_type":    "refresh_token",
                    },
                )

            if resp.status_code != 200:
                logger.error(
                    f"Token refresh failed for {account.email_address} "
                    f"({resp.status_code}): {resp.text}"
                )
                return account

            token_data = resp.json()
            new_access = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)

            if not new_access:
                logger.error(f"Token refresh returned no access_token for {account.email_address}")
                return account

            account.access_token = encrypt_token(new_access)
            # Naive UTC — DB column is TIMESTAMP WITHOUT TIME ZONE
            account.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            await session.flush()

            logger.info(f"Token refreshed for {account.email_address}")

        except Exception as e:
            logger.error(
                f"Token refresh exception for {account.email_address}: {e}",
                exc_info=True
            )

        return account

    # ── History / message fetching ────────────────────────────────────────────

    async def _fetch_latest_message(
        self,
        account: EmailAccount,
        history_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch latest message from Gmail API using history."""
        access_token = decrypt_token(account.access_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_GMAIL_API_BASE}/users/me/history",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "startHistoryId": history_id,
                    "historyTypes":   "messageAdded",
                    "maxResults":     10,
                }
            )

        logger.info(
            f"Gmail History API response: status={resp.status_code} "
            f"account={account.email_address} startHistoryId={history_id}"
        )

        if resp.status_code == 401:
            logger.error(
                f"Gmail 401 for {account.email_address} — token invalid. "
                "Re-connect the account."
            )
            return None

        if resp.status_code == 404:
            logger.warning(
                f"historyId {history_id} expired for {account.email_address}, "
                "falling back to latest inbox message"
            )
            return await self._fetch_latest_inbox_message(account)

        if resp.status_code != 200:
            logger.error(
                f"Gmail history failed ({resp.status_code}) "
                f"for {account.email_address}: {resp.text}"
            )
            return None

        data            = resp.json()
        history_records = data.get("history", [])
        latest_id       = data.get("historyId", history_id)

        logger.info(
            f"Gmail history records: count={len(history_records)} "
            f"latestHistoryId={latest_id} account={account.email_address}"
        )

        if not history_records:
            logger.info(
                f"No new messages for {account.email_address} "
                f"since historyId={history_id} (latestId={latest_id})"
            )
            return None

        for record in history_records:
            msgs = record.get("messagesAdded", [])
            if msgs:
                msg_id = msgs[0]["message"]["id"]
                logger.info(
                    f"Found new message: id={msg_id} "
                    f"account={account.email_address}"
                )
                return await self._fetch_message_details(account, msg_id)

        logger.info(
            f"History records exist but no messagesAdded for {account.email_address}"
        )
        return None

    async def _fetch_latest_inbox_message(
        self,
        account: EmailAccount
    ) -> Optional[Dict[str, Any]]:
        """Fallback: fetch the most recent INBOX message directly."""
        access_token = decrypt_token(account.access_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_GMAIL_API_BASE}/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"labelIds": "INBOX", "maxResults": 1}
            )

        if resp.status_code != 200:
            logger.error(f"Gmail messages list failed: {resp.text}")
            return None

        messages = resp.json().get("messages", [])
        if not messages:
            return None

        return await self._fetch_message_details(account, messages[0]["id"])

    async def _fetch_message_details(
        self,
        account: EmailAccount,
        message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch full message details from Gmail API."""
        access_token = decrypt_token(account.access_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_GMAIL_API_BASE}/users/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "full"}
            )

        if resp.status_code == 401:
            logger.error(f"Gmail 401 fetching message {message_id} — token expired")
            return None

        if resp.status_code != 200:
            logger.error(
                f"Gmail message fetch failed ({resp.status_code}): {resp.text}"
            )
            return None

        message = resp.json()
        hdrs    = {
            h["name"]: h["value"]
            for h in message.get("payload", {}).get("headers", [])
        }

        content, content_html = self._extract_content(message.get("payload", {}))
        if not content:
            content = message.get("snippet", "(no content)")

        # Naive UTC — consistent with DB storage
        timestamp = datetime.utcfromtimestamp(
            int(message.get("internalDate", 0)) / 1000
        )

        return {
            "message_id":      message.get("id"),
            "thread_id":       message.get("threadId"),
            "subject":         hdrs.get("Subject", "(No Subject)"),
            "from_email":      self._parse_email(hdrs.get("From", "")),
            "to_emails":       self._parse_email_list(hdrs.get("To", "")),
            "cc_emails":       self._parse_email_list(hdrs.get("Cc", "")),
            "content":         content,
            "content_html":    content_html,
            "timestamp":       timestamp,
            "has_attachments": self._has_attachments(message.get("payload", {})),
            "provider_data": {
                "label_ids": message.get("labelIds", []),
                "snippet":   message.get("snippet", ""),
            },
        }

    # ── Content helpers ───────────────────────────────────────────────────────

    def _extract_content(self, payload: Dict[str, Any]):
        text, html = "", ""

        def walk(part):
            nonlocal text, html
            mt = part.get("mimeType", "")
            if mt == "text/plain":
                d = part.get("body", {}).get("data", "")
                if d:
                    text += base64.urlsafe_b64decode(d).decode("utf-8", errors="ignore")
            elif mt == "text/html":
                d = part.get("body", {}).get("data", "")
                if d:
                    html += base64.urlsafe_b64decode(d).decode("utf-8", errors="ignore")
            for p in part.get("parts", []):
                walk(p)

        walk(payload)
        return text.strip() or self._html_to_text(html), html

    def _html_to_text(self, html: str) -> str:
        if not html:
            return ""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', html)
        text = (text.replace('&nbsp;', ' ').replace('&lt;', '<')
                    .replace('&gt;', '>').replace('&amp;', '&'))
        return re.sub(r'\s+', ' ', text).strip()

    def _parse_email(self, s: str) -> str:
        if not s:
            return ""
        m = re.search(r'<([^>]+)>', s)
        return m.group(1) if m else s.strip()

    def _parse_email_list(self, s: str) -> list:
        if not s:
            return []
        return [e for part in s.split(',') if (e := self._parse_email(part.strip()))]

    def _has_attachments(self, payload: Dict[str, Any]) -> bool:
        def check(p):
            if p.get("filename"):
                return True
            return any(check(x) for x in p.get("parts", []))
        return check(payload)
