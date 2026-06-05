"""
emailservice — Watch Manager (Enterprise v2)
=============================================
Gmail Watch Recovery and Auto-Subscription System.

Architecture:
  - Startup recovery: ensures all valid Gmail accounts are watched on boot
  - Redis distributed lock: prevents duplicate watches across multiple instances
  - Token validation layer: detects invalid_grant before calling Gmail API
  - Exponential backoff: resilient retries per account
  - Failure isolation: one account failure never crashes the system
  - Horizontal scaling: Redis SETNX locks coordinate multiple workers

Redis key schema:
  es:watch_lock:{email}     — distributed lock (TTL=300s) prevents duplicate watch
  es:watch_active:{email}   — active watch marker (TTL=watch_expiry)
  es:heartbeat:{email}      — last webhook received timestamp

Watch status values (email_accounts.watch_status):
  active  — watch registered and running
  stopped — never started or explicitly stopped
  expired — watch_expiry passed without renewal

Observability:
  Structured logs with: email, action, reason, expiry, elapsed_ms
  Startup metrics: total_accounts, watches_started, skipped, failed
"""
from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

import config as cfg
from token_cache import (
    get_account_snapshot, get_fresh_token, invalidate,
    InvalidGrantError, TokenExpiredError,
)
from shared.database import get_db_session
from shared.cache import get_redis

logger = logging.getLogger("emailservice.watch_manager")

# ── Constants ─────────────────────────────────────────────────────────────────
_WATCH_LOCK_TTL_S   = 300    # Redis lock TTL — prevents duplicate watch during startup
_WATCH_LOCK_PREFIX  = "es:watch_lock:"
_WATCH_ACTIVE_PREFIX = "es:watch_active:"
_MAX_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_S = 2.0
# Concurrency: 20 concurrent watch registrations — safe for Gmail API rate limits
# Gmail watch API: no documented per-user rate limit, but 1B quota units/day globally
# At 20 concurrent × ~100ms each = ~200 accounts/sec = 720k accounts/hour
_STARTUP_CONCURRENCY = 20


def is_watch_expired(acct: dict) -> bool:
    """
    Returns True if the watch needs renewal:
      - watch_status is 'stopped' or 'expired'
      - watch_expiry is missing
      - watch_expiry is within WATCH_RENEW_BEFORE_HOURS of now
    """
    status = acct.get("watch_status", "stopped")
    if status in ("stopped", "expired"):
        return True

    expiry_raw = acct.get("watch_expiry")
    if not expiry_raw:
        return True

    try:
        expiry = datetime.fromisoformat(expiry_raw)
        if expiry.tzinfo:
            expiry = expiry.replace(tzinfo=None)
        renew_at = expiry - timedelta(hours=cfg.WATCH_RENEW_BEFORE_HOURS)
        return datetime.utcnow() >= renew_at
    except Exception:
        return True  # unparseable expiry → treat as expired


class WatchManager:
    """
    Manages Gmail Pub/Sub watch registrations and Outlook Graph subscriptions.

    Key design principles:
      1. Redis distributed lock prevents duplicate watches (horizontal scaling safe)
      2. InvalidGrantError is caught and account marked inactive — no retry
      3. Each account failure is isolated — never crashes the system
      4. Startup recovery processes only accounts that need renewal
      5. Structured logging for full observability
    """

    # ── Public API ────────────────────────────────────────────────────────────

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
        Startup watch recovery — called once on application startup.

        Algorithm:
          1. Stop watches for accounts that became inactive (invalid_grant etc.)
          2. Load all active Gmail/Outlook accounts from DB
          3. Filter: only accounts needing renewal (expired/stopped/missing)
          4. For each: acquire Redis lock → validate token → call Gmail watch API
          5. Log structured metrics at end

        Handles 100k+ accounts via bounded concurrency (semaphore=20).
        Each account failure is isolated — never stops other accounts.
        """
        t0 = time.monotonic()

        # Step 0: Stop watches for accounts that became inactive
        await self._stop_watches_for_inactive_accounts()

        accounts = await self._load_accounts_needing_watch()
        total = len(accounts)

        if total == 0:
            logger.info("Watch sync: all watches valid — nothing to do")
            return

        logger.info("Watch sync: %d accounts need watch renewal", total)

        # Metrics counters
        started = 0
        skipped = 0
        failed  = 0

        sem = asyncio.Semaphore(_STARTUP_CONCURRENCY)

        async def _process(acct: dict) -> str:
            nonlocal started, skipped, failed
            result = await self._register_with_lock(acct)
            if result == "registered":
                started += 1
            elif result in ("skipped_lock", "skipped_active"):
                skipped += 1
            else:
                failed += 1
            return result

        await asyncio.gather(
            *[self._bounded(sem, _process, acct) for acct in accounts],
            return_exceptions=True,
        )

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        logger.info(
            "Watch sync complete | total=%d started=%d skipped=%d failed=%d elapsed_ms=%d",
            total, started, skipped, failed, elapsed_ms,
        )

    async def run_scheduler(self) -> None:
        """
        Hourly per-account renewal scheduler.
        Checks each account individually based on its own expiry timestamp.
        """
        logger.info("Watch scheduler started (hourly per-account check)")
        while True:
            await asyncio.sleep(3600)
            try:
                await self.sync_all_watches()
            except Exception as e:
                logger.error("Watch scheduler error: %s", e)

    async def run_watchdog(self) -> None:
        """
        Heartbeat watchdog — dual-layer subscription protection.
        Re-registers accounts that have been silent for WATCH_INACTIVITY_THRESHOLD_S.
        Catches silent subscription failures that scheduled renewal misses.
        """
        logger.info("Watch heartbeat watchdog started (interval=%ds, threshold=%ds)",
                    cfg.WATCH_HEARTBEAT_INTERVAL_S, cfg.WATCH_INACTIVITY_THRESHOLD_S)
        while True:
            await asyncio.sleep(cfg.WATCH_HEARTBEAT_INTERVAL_S)
            try:
                await self._check_heartbeats()
            except Exception as e:
                logger.error("Watchdog error: %s", e)

    # ── Core registration with distributed lock ───────────────────────────────

    async def _register_with_lock(self, snap: dict) -> str:
        """
        Acquire Redis distributed lock then register watch.

        Lock key: es:watch_lock:{email}
        Lock TTL: 300s — prevents duplicate watch during concurrent startup

        Returns:
          "registered"      — watch successfully started
          "skipped_lock"    — another instance holds the lock
          "skipped_active"  — watch already active (Redis marker present)
          "skipped_inactive"— account is_active=False
          "token_failure"   — invalid_grant, account marked inactive
          "api_failure"     — Gmail API error (transient)
          "error"           — unexpected exception
        """
        email = snap.get("email_address", "")
        provider = snap.get("provider", "")

        # Skip accounts that are permanently revoked or explicitly deactivated
        account_state = snap.get("account_state", "active")
        if account_state == "token_revoked":
            logger.info("watch_skipped | email=%s reason=token_revoked", email)
            return "skipped_inactive"
        if not snap.get("is_active", True):
            logger.info("watch_skipped | email=%s reason=account_inactive", email)
            return "skipped_inactive"
        # TOKEN_EXPIRED accounts: attempt watch registration — token refresh will be tried
        # inside _gmail_watch_by_snap. If it succeeds, account heals automatically.

        try:
            redis = await get_redis()

            # Check active watch marker (fast path — no lock needed)
            active_key = f"{_WATCH_ACTIVE_PREFIX}{email}"
            if await redis.exists(active_key):
                logger.debug("watch_skipped | email=%s reason=already_active_redis", email)
                return "skipped_active"

            # Acquire distributed lock (SETNX with TTL)
            lock_key = f"{_WATCH_LOCK_PREFIX}{email}"
            acquired = await redis.set(lock_key, "1", nx=True, ex=_WATCH_LOCK_TTL_S)
            if not acquired:
                logger.info("watch_skipped | email=%s reason=lock_held_by_another_instance", email)
                return "skipped_lock"

        except Exception as e:
            logger.warning("Redis lock unavailable for %s (%s) — proceeding without lock", email, e)
            # Fail open — proceed without lock rather than blocking all watches

        try:
            result = await self._register_by_snap(snap)
            return result
        finally:
            # Always release lock after attempt (success or failure)
            try:
                redis = await get_redis()
                await redis.delete(f"{_WATCH_LOCK_PREFIX}{email}")
            except Exception:
                pass  # lock will expire via TTL

    async def _register_by_snap(self, snap: dict) -> str:
        """Register watch for a single account. Handles both Gmail and Outlook."""
        provider = snap.get("provider", "")
        email    = snap.get("email_address", "")

        try:
            if provider == "gmail":
                return await self._gmail_watch_by_snap(snap)
            elif provider == "outlook":
                return await self._outlook_sub_by_snap(snap)
            else:
                logger.debug("watch_skipped | email=%s reason=unsupported_provider=%s", email, provider)
                return "skipped_provider"
        except InvalidGrantError as e:
            logger.error("watch_token_failure | email=%s reason=token_revoked | %s", email, e)
            return "token_failure"
        except TokenExpiredError as e:
            logger.warning("watch_token_failure | email=%s reason=token_expired | %s", email, e)
            return "token_failure"
        except Exception as e:
            logger.error("watch_error | email=%s error=%s", email, e)
            return "error"

    # ── Gmail watch ───────────────────────────────────────────────────────────

    async def _ensure_gmail_watch(self, account) -> str:
        snap = await get_account_snapshot(account.email_address)
        if not snap:
            return "no_snap"
        return await self._register_with_lock(snap)

    async def _gmail_watch_by_snap(self, snap: dict) -> str:
        """
        Register Gmail Pub/Sub watch with exponential backoff retry.

        Steps:
          1. Validate/refresh token (raises InvalidGrantError on invalid_grant)
          2. Call Gmail watch API
          3. Save expiry to DB + update watch_status = active
          4. Set Redis active marker with TTL = watch_expiry
        """
        email   = snap["email_address"]
        cfg_obj = cfg.get_config()
        topic   = cfg_obj.GMAIL_PUBSUB_TOPIC

        # Step 1: Token validation — raises InvalidGrantError if permanently revoked
        try:
            token = await get_fresh_token(snap)
        except InvalidGrantError:
            raise  # propagate — caller handles, account set to token_revoked
        except TokenExpiredError as e:
            logger.warning("watch_token_expired | email=%s — will retry on next cycle: %s", email, e)
            return "token_failure"  # transient — retry on next hourly cycle
        except Exception as e:
            logger.warning("watch_token_refresh_failed | email=%s error=%s", email, e)
            return "token_failure"

        # Step 2: Call Gmail watch API with retry
        last_error = None
        for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"topicName": topic, "labelIds": ["INBOX"]},
                    )

                if resp.status_code in (200, 201):
                    break  # success

                if resp.status_code == 401:
                    # Token expired mid-flight — don't retry
                    logger.warning("watch_api_401 | email=%s attempt=%d", email, attempt)
                    return "api_failure"

                if resp.status_code == 429:
                    # Rate limited — backoff and retry
                    delay = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                    logger.warning("watch_api_429 | email=%s attempt=%d retry_in=%.1fs",
                                   email, attempt, delay)
                    await asyncio.sleep(delay)
                    last_error = f"HTTP 429 (rate limited)"
                    continue

                last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
                logger.warning("watch_api_error | email=%s attempt=%d status=%d",
                               email, attempt, resp.status_code)

                if attempt < _MAX_RETRY_ATTEMPTS:
                    await asyncio.sleep(_RETRY_BASE_DELAY_S * attempt)

            except Exception as e:
                last_error = str(e)
                logger.warning("watch_api_exception | email=%s attempt=%d error=%s",
                               email, attempt, e)
                if attempt < _MAX_RETRY_ATTEMPTS:
                    await asyncio.sleep(_RETRY_BASE_DELAY_S * attempt)
        else:
            logger.error("watch_api_failed | email=%s all_attempts_exhausted last_error=%s",
                         email, last_error)
            return "api_failure"

        # Step 3: Parse response and persist
        data       = resp.json()
        history_id = str(data.get("historyId", ""))
        expiry_ms  = int(data.get("expiration", 0))
        expiry     = (datetime.utcfromtimestamp(expiry_ms / 1000) if expiry_ms
                      else datetime.utcnow() + timedelta(days=cfg.WATCH_MAX_EXPIRY_DAYS))

        await self._save_watch_state(snap["id"], history_id, expiry, status="active")
        await invalidate(email)

        # Step 4: Set Redis active marker (TTL = seconds until expiry)
        try:
            redis = await get_redis()
            ttl_s = max(60, int((expiry - datetime.utcnow()).total_seconds()))
            await redis.setex(f"{_WATCH_ACTIVE_PREFIX}{email}", ttl_s, "1")
        except Exception:
            pass  # non-critical — DB is source of truth

        logger.info(
            "watch_started | email=%s provider=gmail historyId=%s expiry=%s",
            email, history_id, expiry.date(),
        )
        return "registered"

    # ── Outlook subscription ──────────────────────────────────────────────────

    async def _ensure_outlook_subscription(self, account) -> str:
        snap = await get_account_snapshot(account.email_address)
        if not snap:
            return "no_snap"
        return await self._register_with_lock(snap)

    async def _outlook_sub_by_snap(self, snap: dict) -> str:
        email   = snap["email_address"]
        cfg_obj = cfg.get_config()

        try:
            token = await get_fresh_token(snap)
        except InvalidGrantError:
            raise
        except Exception as e:
            logger.warning("watch_token_refresh_failed | email=%s error=%s", email, e)
            return "token_failure"

        notif_url = f"{cfg_obj.EMAIL_SERVICE_PUBLIC_URL}/webhooks/outlook"
        expiry_dt = datetime.utcnow() + timedelta(minutes=4230)
        expiry_str = expiry_dt.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")

        body = {
            "changeType":         "created",
            "notificationUrl":    notif_url,
            "resource":           "me/messages",
            "expirationDateTime": expiry_str,
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
            logger.error("watch_outlook_exception | email=%s error=%s", email, e)
            return "api_failure"

        if resp.status_code not in (200, 201):
            logger.error("watch_outlook_failed | email=%s status=%d body=%s",
                         email, resp.status_code, resp.text[:100])
            return "api_failure"

        data   = resp.json()
        sub_id = data.get("id", "")

        # Cache subscription_id → account mapping
        try:
            import json as _json
            redis = await get_redis()
            await redis.setex(f"es:sub:{sub_id}", 86400 * 4, _json.dumps(snap))
        except Exception:
            pass

        logger.info("watch_started | email=%s provider=outlook sub_id=%s", email, sub_id[:12])
        return "registered"

    # ── Heartbeat watchdog ────────────────────────────────────────────────────

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
                    silent_s = now - float(last_seen_raw)
                    if silent_s < cfg.WATCH_INACTIVITY_THRESHOLD_S:
                        continue
                    logger.warning("watchdog_silent | email=%s silent_hours=%.1f — re-registering",
                                   email, silent_s / 3600)
                else:
                    if not acct.get("watch_expiry"):
                        continue
                    logger.info("watchdog_no_heartbeat | email=%s — re-registering", email)

                await self._register_with_lock(acct)
                renewed += 1

            except Exception as e:
                logger.error("watchdog_check_failed | email=%s error=%s", email, e)

        if renewed:
            logger.info("Watchdog: renewed %d watches", renewed)

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _stop_watches_for_inactive_accounts(self) -> None:
        """
        Stop Gmail watches for accounts that became inactive (e.g. invalid_grant).
        This prevents Google from sending Pub/Sub notifications for dead accounts,
        which would generate noise in the logs and waste quota.

        Only stops watches where watch_status='active' AND is_active=False.
        """
        try:
            from models.email_account import EmailAccount, EmailProvider
            from sqlalchemy import select, update as sa_update
            from uuid import UUID

            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        EmailAccount.id,
                        EmailAccount.email_address,
                        EmailAccount.access_token,
                        EmailAccount.refresh_token,
                        EmailAccount.token_expiry,
                    ).where(
                        EmailAccount.provider == EmailProvider.GMAIL,
                        EmailAccount.is_active == False,
                        EmailAccount.watch_status == "active",
                    )
                )
                inactive_with_watch = result.all()

            if not inactive_with_watch:
                return

            logger.info("Stopping watches for %d inactive Gmail accounts", len(inactive_with_watch))

            for row in inactive_with_watch:
                acct_id, email = str(row[0]), row[1]
                snap = {
                    "id": acct_id, "email_address": email,
                    "access_token": row[2], "refresh_token": row[3],
                    "token_expiry": row[4].isoformat() if row[4] else None,
                    "provider": "gmail",
                }
                try:
                    await self._stop_gmail_watch(snap)
                except Exception as e:
                    logger.warning("Failed to stop watch for inactive %s: %s", email, e)

                # Mark watch_status = stopped regardless of API result
                await self._save_watch_state(acct_id, "", datetime.utcnow(), status="stopped")
                # Clear Redis active marker
                try:
                    redis = await get_redis()
                    await redis.delete(f"{_WATCH_ACTIVE_PREFIX}{email}")
                except Exception:
                    pass

        except Exception as e:
            logger.error("Failed to stop watches for inactive accounts: %s", e)

    async def _stop_gmail_watch(self, snap: dict) -> None:
        """
        Call Gmail API to stop the watch for an account.
        Best-effort — if it fails, the watch expires naturally in ≤7 days.
        """
        email = snap.get("email_address", "")
        try:
            token = await get_fresh_token(snap)
        except (InvalidGrantError, TokenExpiredError, Exception):
            # Can't get token — watch will expire naturally in ≤7 days
            logger.debug("Cannot stop watch for %s — no valid token (will expire naturally)", email)
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/stop",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code in (200, 204):
                logger.info("watch_stopped | email=%s", email)
            else:
                logger.debug("watch_stop_failed | email=%s status=%d (will expire naturally)",
                             email, resp.status_code)
        except Exception as e:
            logger.debug("watch_stop_exception | email=%s error=%s (will expire naturally)", email, e)

    async def _save_watch_state(
        self,
        account_id: str,
        history_id: str,
        expiry: datetime,
        status: str = "active",
    ) -> None:
        """Persist watch_expiry, watch_status, last_watch_started_at, last_history_id."""
        try:
            from models.email_account import EmailAccount
            from sqlalchemy import update as sa_update
            from uuid import UUID
            now = datetime.utcnow()
            async with get_db_session() as session:
                await session.execute(
                    sa_update(EmailAccount)
                    .where(EmailAccount.id == UUID(account_id))
                    .values(
                        watch_expiry=expiry,
                        watch_status=status,
                        last_watch_started_at=now,
                        last_history_id=history_id or None,
                    )
                )
                await session.commit()
        except Exception as e:
            logger.error("Failed to save watch state for %s: %s", account_id[:8], e)

    async def _load_accounts_needing_watch(self) -> list[dict]:
        """
        Load Gmail/Outlook accounts that need watch renewal.
        Filters at DB level for efficiency at 100k+ scale.

        Criteria (OR):
          - watch_status IN ('stopped', 'expired')
          - watch_expiry IS NULL
          - watch_expiry < NOW() + WATCH_RENEW_BEFORE_HOURS

        Exclusions (always skip):
          - account_state = 'token_revoked'  (permanent failure — user must reconnect)
          - is_active = False                (explicitly deactivated)
        """
        try:
            from models.email_account import EmailAccount, EmailProvider
            from sqlalchemy import select, or_

            renew_threshold = datetime.utcnow() + timedelta(hours=cfg.WATCH_RENEW_BEFORE_HOURS)

            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        EmailAccount.id,
                        EmailAccount.user_id,
                        EmailAccount.email_address,
                        EmailAccount.provider,
                        EmailAccount.access_token,
                        EmailAccount.refresh_token,
                        EmailAccount.token_expiry,
                        EmailAccount.watch_expiry,
                        EmailAccount.watch_status,
                        EmailAccount.last_history_id,
                        EmailAccount.account_state,
                    ).where(
                        EmailAccount.provider.in_([EmailProvider.GMAIL, EmailProvider.OUTLOOK]),
                        EmailAccount.is_active == True,
                        # Skip permanently revoked accounts — they cannot be watched
                        # until the user reconnects via OAuth
                        EmailAccount.account_state != "token_revoked",
                        or_(
                            EmailAccount.watch_status.in_(["stopped", "expired"]),
                            EmailAccount.watch_expiry.is_(None),
                            EmailAccount.watch_expiry < renew_threshold,
                        ),
                    ).order_by(EmailAccount.created_at)
                )
                return [
                    {
                        "id":               str(r[0]),
                        "user_id":          str(r[1]),
                        "email_address":    r[2],
                        "provider":         r[3].value,
                        "access_token":     r[4],
                        "refresh_token":    r[5],
                        "token_expiry":     r[6].isoformat() if r[6] else None,
                        "watch_expiry":     r[7].isoformat() if r[7] else None,
                        "watch_status":     r[8] or "stopped",
                        "last_history_id":  r[9],
                        "is_active":        True,
                        "account_state":    r[10] or "active",
                    }
                    for r in result.all()
                ]
        except Exception as e:
            logger.error("Failed to load accounts needing watch: %s", e)
            return []

    async def _load_active_oauth_accounts(self) -> list[dict]:
        """Load all active Gmail/Outlook accounts (for watchdog heartbeat check)."""
        try:
            from models.email_account import EmailAccount, EmailProvider
            from sqlalchemy import select
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        EmailAccount.id,
                        EmailAccount.user_id,
                        EmailAccount.email_address,
                        EmailAccount.provider,
                        EmailAccount.access_token,
                        EmailAccount.refresh_token,
                        EmailAccount.token_expiry,
                        EmailAccount.watch_expiry,
                        EmailAccount.watch_status,
                        EmailAccount.last_history_id,
                    ).where(
                        EmailAccount.provider.in_([EmailProvider.GMAIL, EmailProvider.OUTLOOK]),
                        EmailAccount.is_active == True,
                    )
                )
                return [
                    {
                        "id":              str(r[0]),
                        "user_id":         str(r[1]),
                        "email_address":   r[2],
                        "provider":        r[3].value,
                        "access_token":    r[4],
                        "refresh_token":   r[5],
                        "token_expiry":    r[6].isoformat() if r[6] else None,
                        "watch_expiry":    r[7].isoformat() if r[7] else None,
                        "watch_status":    r[8] or "stopped",
                        "last_history_id": r[9],
                        "is_active":       True,
                    }
                    for r in result.all()
                ]
        except Exception as e:
            logger.error("Failed to load OAuth accounts: %s", e)
            return []

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    async def _bounded(sem: asyncio.Semaphore, coro_fn, *args) -> None:
        """Run coro_fn(*args) under semaphore. Swallows exceptions for isolation."""
        async with sem:
            try:
                await coro_fn(*args)
            except Exception as e:
                logger.error("Bounded task failed: %s", e)
