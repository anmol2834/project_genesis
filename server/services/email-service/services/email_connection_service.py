"""
EmailConnectionService
Routes connection requests to the correct adapter, handles upsert, and persists
encrypted credentials to email_accounts.
"""

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters import GmailAdapter, OutlookAdapter, SMTPAdapter
from models.email_account import EmailAccount, EmailProvider, ConnectionStatus, SyncStatus
from utils.encryption import encrypt
from shared.logger import get_logger

logger = get_logger(__name__)

_ADAPTERS = {
    "gmail":   GmailAdapter(),
    "outlook": OutlookAdapter(),
    "smtp":    SMTPAdapter(),
}


class EmailConnectionService:

    async def connect_and_save(
        self,
        db: AsyncSession,
        user_id: UUID,
        provider: str,
        credentials: Dict[str, Any],
    ) -> EmailAccount:
        adapter = _ADAPTERS.get(provider)
        if not adapter:
            raise ValueError(f"Unsupported provider: {provider}")

        data = await adapter.connect(credentials)
        email_address: str = data["email_address"]

        # ── Upsert: check for existing account ──────────────────────────────
        stmt = select(EmailAccount).where(
            EmailAccount.user_id == user_id,
            EmailAccount.email_address == email_address,
        )
        result = await db.execute(stmt)
        account: EmailAccount | None = result.scalar_one_or_none()

        if account:
            logger.info("Updating existing email account %s for user %s", email_address, user_id)
            self._apply_data(account, data)
        else:
            logger.info("Creating new email account %s for user %s", email_address, user_id)
            account = EmailAccount(
                user_id=user_id,
                provider=EmailProvider(provider),
            )
            self._apply_data(account, data)
            db.add(account)

        await db.flush()
        await db.refresh(account)
        return account

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _apply_data(account: EmailAccount, data: Dict[str, Any]) -> None:
        account.email_address     = data["email_address"]
        account.provider          = EmailProvider(data["provider"])
        account.connection_status = ConnectionStatus.CONNECTED
        account.sync_status       = SyncStatus.IDLE
        account.is_active         = True
        account.last_error_message = None

        if data.get("provider_account_id"):
            account.provider_account_id = data["provider_account_id"]

        # OAuth tokens — encrypt before storing
        if data.get("access_token"):
            account.access_token  = encrypt(data["access_token"])
        if data.get("refresh_token"):
            account.refresh_token = encrypt(data["refresh_token"])
        if data.get("token_expiry"):
            account.token_expiry  = data["token_expiry"]

        # SMTP credentials — encrypt password
        if data.get("smtp_host"):
            account.smtp_host     = data["smtp_host"]
            account.smtp_port     = data["smtp_port"]
            account.smtp_username = data["smtp_username"]
            account.smtp_password = encrypt(data["smtp_password"]) if data.get("smtp_password") else None
            account.smtp_use_tls  = data.get("smtp_use_tls", True)
            account.imap_host     = data.get("imap_host")
            account.imap_port     = data.get("imap_port")
