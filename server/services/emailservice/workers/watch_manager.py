"""
emailservice — Watch Manager
Manages Gmail Pub/Sub watch registrations and Outlook Graph subscriptions.

Gmail watch:
  - One-time setup per account
  - Auto-renews every ~6 days (before 7-day expiry)
  - Runs as a background task — no manual intervention

Outlook subscription:
  - Renews every 3 days (max 4230 minutes)
  - Validation handshake handled by webhook layer
"""
from __future__ import annotations
import asyncio, logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

import config as cfg
from token_cache import get_account_snapshot, get_fresh_token, invalidate
from shared.database import get_db_session
from shared.cache import get_redis

logger = logging.getLogger("emailservice.watch_manager")


class WatchManager:
    """Manages Gmail/Outlook watch subscriptions."""

    async def ensure_watch(self, account) -> str:
        """Register or renew watch for a newly connected account."""
        provider = account.provider.value if hasattr(account.provider, "value") else str(account.provider)
        if provider == "gmail":
            return await self._ensure_gmail_watch(account)
        elif provider == "outlook":
            return await self._ensure_outlook_subscription(account)
        return "no_watch_needed"

    async def sync_all_watches(self) -> None:
        """
        Called on startup and periodically.
        Renews watches expiring within WATCH_RENEW_BEFORE_HOURS.
        """
        accounts = await self._load_active_oauth_accounts()
        logger.info("Watch sync: checking %d accounts", len(accounts))

        sem = asyncio.Semaphore(10)
        tasks = [self._renew_if_needed(acct, sem) for acct in accounts]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _renew_if_needed(self, acct: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            provider = acct.get("provider", "")
            expiry_raw = acct.get("watch_expiry")
            if not expiry_raw:
                # No watch yet — register
                await self._register_by_snap(acct)
                return

            try:
                expiry = datetime.fromisoformat(expiry_raw)
                if expiry.tzinfo:
                    expiry = expiry.replace(tzinfo=None)
            except Exception:
                expiry = datetime.utcnow()

            renew_threshold = datetime.utcnow() + timedelta(hours=cfg.WATCH_RENEW_BEFORE_HOURS)
            if expiry <= renew_threshold:
                await self._register_by_snap(acct)

    async def _register_by_snap(self, snap: dict) -> None:
        provider = snap.get("provider", "")
        try:
            if provider == "gmail":
                await self._gmail_watch_by_snap(snap)
            elif provider == "outlook":
                await self._outlook_sub_by_snap(snap)
        except Exception as e:
            logger.error("Watch registration failed for %s: %s", snap.get("email_address"), e)

    # ── Gmail watch ───────────────────────────────────────────────────────────

    async def _ensure_gmail_watch(self, account) -> str:
        snap = await get_account_snapshot(account.email_address)
        if not snap:
            return "no_snap"
        return await self._gmail_watch_by_snap(snap)

    async def _gmail_watch_by_snap(self, snap: dict) -> str:
        token = await get_fresh_token(snap)
        cfg_obj = cfg.get_config()
        topic = cfg_obj.GMAIL_PUBSUB_TOPIC

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"topicName": topic, "labelIds": ["INBOX"]},
                )
        except Exception as e:
            logger.error("Gmail watch request failed for %s: %s", snap["email_address"], e)
            return "error"

        if resp.status_code not in (200, 201):
            logger.error("Gmail watch failed (%d) for %s: %s",
                         resp.status_code, snap["email_address"], resp.text[:100])
            return "error"

        data       = resp.json()
        history_id = str(data.get("historyId", ""))
        expiry_ms  = int(data.get("expiration", 0))
        expiry     = datetime.utcfromtimestamp(expiry_ms / 1000) if expiry_ms else \
                     datetime.utcnow() + timedelta(days=cfg.WATCH_MAX_EXPIRY_DAYS)

        await self._save_watch_expiry(snap["id"], history_id, expiry)
        await invalidate(snap["email_address"])

        logger.info("Gmail watch registered | email=%s historyId=%s expiry=%s",
                    snap["email_address"], history_id, expiry.date())
        return "registered"

    # ── Outlook subscription ──────────────────────────────────────────────────

    async def _ensure_outlook_subscription(self, account) -> str:
        snap = await get_account_snapshot(account.email_address)
        if not snap:
            return "no_snap"
        return await self._outlook_sub_by_snap(snap)

    async def _outlook_sub_by_snap(self, snap: dict) -> str:
        token    = await get_fresh_token(snap)
        cfg_obj  = cfg.get_config()
        notif_url = f"{cfg_obj.EMAIL_SERVICE_PUBLIC_URL}/webhooks/outlook"
        expiry   = (datetime.utcnow() + timedelta(minutes=4230)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")

        body = {
            "changeType":         "created",
            "notificationUrl":    notif_url,
            "resource":           "me/messages",
            "expirationDateTime": expiry,
            "clientState":        snap["id"],
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://graph.microsoft.com/v1.0/subscriptions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=body,
                )
        except Exception as e:
            logger.error("Outlook subscription failed for %s: %s", snap["email_address"], e)
            return "error"

        if resp.status_code not in (200, 201):
            logger.error("Outlook sub failed (%d) for %s", resp.status_code, snap["email_address"])
            return "error"

        data = resp.json()
        sub_id = data.get("id", "")
        exp_dt = data.get("expirationDateTime", "")

        # Cache subscription_id → account mapping
        try:
            import json
            redis = await get_redis()
            await redis.setex(f"es:sub:{sub_id}", 86400 * 4, json.dumps(snap))
        except Exception:
            pass

        logger.info("Outlook subscription registered | email=%s sub_id=%s",
                    snap["email_address"], sub_id[:12])
        return "registered"

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _save_watch_expiry(self, account_id: str, history_id: str, expiry: datetime) -> None:
        try:
            from models.email_account import EmailAccount
            from sqlalchemy import update as sa_update
            from uuid import UUID
            async with get_db_session() as session:
                await session.execute(
                    sa_update(EmailAccount).where(EmailAccount.id == UUID(account_id))
                    .values(watch_expiry=expiry, last_history_id=history_id)
                )
                await session.commit()
        except Exception as e:
            logger.error("Failed to save watch expiry: %s", e)

    async def _load_active_oauth_accounts(self) -> list[dict]:
        try:
            from models.email_account import EmailAccount, EmailProvider
            from sqlalchemy import select
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        EmailAccount.id, EmailAccount.user_id, EmailAccount.email_address,
                        EmailAccount.provider, EmailAccount.access_token, EmailAccount.refresh_token,
                        EmailAccount.token_expiry, EmailAccount.watch_expiry, EmailAccount.last_history_id,
                    ).where(
                        EmailAccount.provider.in_([EmailProvider.GMAIL, EmailProvider.OUTLOOK]),
                        EmailAccount.is_active == True,
                    )
                )
                return [
                    {
                        "id": str(r[0]), "user_id": str(r[1]), "email_address": r[2],
                        "provider": r[3].value, "access_token": r[4], "refresh_token": r[5],
                        "token_expiry": r[6].isoformat() if r[6] else None,
                        "watch_expiry": r[7].isoformat() if r[7] else None,
                        "last_history_id": r[8],
                    }
                    for r in result.all()
                ]
        except Exception as e:
            logger.error("Failed to load OAuth accounts: %s", e)
            return []
