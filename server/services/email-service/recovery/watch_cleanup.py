"""
Gmail Watch Cleanup
===================
Stops Gmail watches for accounts that are NOT in the database.

Problem: Old projects or manual registrations leave active Gmail watches
pointing to our Pub/Sub topic. These generate noise and waste resources.

Solution:
  - If we have a token for the unknown account → call gmail.users.stop()
  - If we don't have a token → log and ignore (watch expires in ≤7 days)

This module is called:
  1. Via API: POST /subscriptions/stop-unknown-watch
  2. Via Celery Beat: cleanup_task runs weekly
"""

from typing import Optional
import httpx

from shared.logger import get_logger
from shared.database import get_db_session
from models.email_account import EmailAccount, EmailProvider
from sqlalchemy import select

logger = get_logger(__name__)

_GMAIL_STOP_URL = "https://gmail.googleapis.com/gmail/v1/users/me/stop"


class WatchCleanup:
    """Stops unwanted Gmail watches."""

    async def stop_unknown_watch(
        self,
        email_address: str,
        access_token: Optional[str] = None
    ) -> dict:
        """
        Stop a Gmail watch for an email address that is NOT in our DB.

        Args:
            email_address: The Gmail address whose watch should be stopped
            access_token: Optional raw (decrypted) access token. If not provided,
                          we check the DB — if the account exists there, we use
                          its token. If neither is available, we can't stop it.

        Returns:
            {"stopped": bool, "reason": str}
        """
        # Check if account is in DB (it shouldn't be for "unknown" watches,
        # but handle the case where it was recently added)
        token_to_use = access_token

        if not token_to_use:
            async with get_db_session() as session:
                result = await session.execute(
                    select(EmailAccount).where(
                        EmailAccount.email_address == email_address
                    )
                )
                account = result.scalar_one_or_none()

                if account and account.access_token:
                    from utils.encryption import decrypt_token
                    try:
                        token_to_use = decrypt_token(account.access_token)
                    except Exception:
                        pass

        if not token_to_use:
            logger.warning(
                f"Cannot stop watch for {email_address} — no access token available. "
                "The watch will expire automatically within 7 days."
            )
            return {
                "stopped": False,
                "reason": "no_token_available",
                "message": "Watch will expire automatically within 7 days",
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _GMAIL_STOP_URL,
                    headers={"Authorization": f"Bearer {token_to_use}"},
                )

            if resp.status_code == 204:
                logger.info(f"Gmail watch stopped for {email_address}")
                return {"stopped": True, "reason": "success"}

            if resp.status_code == 401:
                logger.warning(
                    f"Gmail 401 stopping watch for {email_address} — token expired. "
                    "Watch will expire automatically within 7 days."
                )
                return {
                    "stopped": False,
                    "reason": "token_expired",
                    "message": "Watch will expire automatically within 7 days",
                }

            logger.error(
                f"Gmail stop watch returned {resp.status_code} "
                f"for {email_address}: {resp.text}"
            )
            return {
                "stopped": False,
                "reason": f"api_error_{resp.status_code}",
                "detail": resp.text,
            }

        except Exception as e:
            logger.error(f"Exception stopping watch for {email_address}: {e}")
            return {"stopped": False, "reason": "exception", "detail": str(e)}

    async def cleanup_all_unknown_watches(self) -> dict:
        """
        Attempt to stop watches for all known-unknown accounts.
        These are tracked in Redis under key: gmail:unknown:watches

        When the receiver sees an unknown emailAddress, it adds it to this set.
        This method then tries to stop those watches.
        """
        from shared.cache import get_redis

        redis  = await get_redis()
        emails = await redis.smembers("gmail:unknown:watches")

        if not emails:
            return {"checked": 0, "stopped": 0}

        stopped = 0
        for email_bytes in emails:
            email = email_bytes if isinstance(email_bytes, str) else email_bytes.decode()
            result = await self.stop_unknown_watch(email)
            if result.get("stopped"):
                stopped += 1
                await redis.srem("gmail:unknown:watches", email)

        return {"checked": len(emails), "stopped": stopped}


_cleanup: Optional[WatchCleanup] = None


def get_watch_cleanup() -> WatchCleanup:
    global _cleanup
    if _cleanup is None:
        _cleanup = WatchCleanup()
    return _cleanup
