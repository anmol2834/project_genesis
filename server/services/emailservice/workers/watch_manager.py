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
import asyncio, logging, time
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
        Called on startup. Checks each account individually based on its
        own watch_expiry timestamp — not a global fixed interval.
        Renews accounts whose watch expires within WATCH_RENEW_BEFORE_HOURS.
        Also immediately renews any account whose watch has already expired
        (handles server downtime scenarios).
        """
        accounts = await self._load_active_oauth_accounts()
        logger.info("Watch sync: checking %d accounts", len(accounts))

        now = datetime.utcnow()
        overdue  = []
        upcoming = []

        for acct in accounts:
            expiry_raw = acct.get("watch_expiry")
            if not expiry_raw:
                overdue.append(acct)  # never registered
                continue
            try:
                expiry = datetime.fromisoformat(expiry_raw)
                if expiry.tzinfo:
                    expiry = expiry.replace(tzinfo=None)
            except Exception:
                overdue.append(acct)
                continue

            renew_at = expiry - timedelta(hours=cfg.WATCH_RENEW_BEFORE_HOURS)
            if now >= renew_at:
                if now >= expiry:
                    overdue.append(acct)   # already expired — renew immediately
                else:
                    upcoming.append(acct)  # expiring soon — renew now
            # else: still valid, skip

        if overdue:
            logger.warning("Watch sync: %d accounts have expired/missing watches — renewing immediately",
                           len(overdue))
        if upcoming:
            logger.info("Watch sync: %d accounts expiring soon — renewing", len(upcoming))

        to_renew = overdue + upcoming
        if not to_renew:
            logger.info("Watch sync: all watches valid")
            return

        sem = asyncio.Semaphore(5)
        tasks = [self._register_by_snap_sem(acct, sem) for acct in to_renew]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _register_by_snap_sem(self, snap: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            await self._register_by_snap(snap)

    async def run_scheduler(self) -> None:
        """
        Per-account renewal scheduler.
        Checks each account individually and renews based on its own expiry.
        Runs hourly — lightweight check, only renews when actually needed.
        This replaces the old global 6-day interval.
        """
        logger.info("Watch scheduler started (hourly per-account check)")
        while True:
            await asyncio.sleep(3600)  # check every hour
            try:
                await self.sync_all_watches()
            except Exception as e:
                logger.error("Watch scheduler error: %s", e)

    async def run_watchdog(self) -> None:
        """
        Heartbeat watchdog — dual-layer subscription protection.
        Runs every WATCH_HEARTBEAT_INTERVAL_S and re-registers any account
        that has been silent for WATCH_INACTIVITY_THRESHOLD_S.

        This catches silent subscription failures that the scheduled renewal
        misses (e.g. Google silently drops a watch without sending expiry).
        """
        logger.info("Watch heartbeat watchdog started (interval=%ds, threshold=%ds)",
                    cfg.WATCH_HEARTBEAT_INTERVAL_S, cfg.WATCH_INACTIVITY_THRESHOLD_S)
        while True:
            await asyncio.sleep(cfg.WATCH_HEARTBEAT_INTERVAL_S)
            try:
                await self._check_heartbeats()
            except Exception as e:
                logger.error("Watchdog error: %s", e)

    async def _check_heartbeats(self) -> None:
        """Re-register watches for accounts that haven't received events recently."""
        accounts = await self._load_active_oauth_accounts()
        redis    = await get_redis()
        now      = time.time()
        renewed  = 0

        for acct in accounts:
            email = acct.get("email_address", "")
            try:
                last_seen_raw = await redis.get(f"es:heartbeat:{email}")
                if last_seen_raw:
                    last_seen = float(last_seen_raw)
                    silent_s  = now - last_seen
                    if silent_s < cfg.WATCH_INACTIVITY_THRESHOLD_S:
                        continue  # recently active — no action needed
                    logger.warning("Watchdog: account %s silent for %.1fh — re-registering watch",
                                   email, silent_s / 3600)
                else:
                    # No heartbeat key at all — account may never have received an event
                    # Only re-register if watch_expiry is set (account was connected)
                    if not acct.get("watch_expiry"):
                        continue
                    logger.info("Watchdog: no heartbeat for %s — re-registering watch", email)

                await self._register_by_snap(acct)
                renewed += 1

            except Exception as e:
                logger.error("Watchdog check failed for %s: %s", email, e)

        if renewed:
            logger.info("Watchdog: renewed %d watches", renewed)

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
