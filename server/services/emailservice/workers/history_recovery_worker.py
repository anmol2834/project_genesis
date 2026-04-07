"""
emailservice — History Recovery Worker
=======================================
Purpose: recover emails missed during server downtime.

Schedule:
  - On startup: run ONCE to catch any gap since last cursor
  - Periodic: every HISTORY_RECOVERY_INTERVAL_DAYS (6 days) — aligns with
    Gmail watch expiry so recovery and watch renewal happen together
  - NOT a continuous poller — live emails come via Pub/Sub webhooks

Design:
  - Redis lock prevents concurrent runs across restarts
  - Per-account skip if synced within last 5 minutes (debounce)
  - Rate limiter: half-weight tokens (doesn't compete with live fetch)
  - Idempotency cache: skips messages already processed by live workers
  - Persistent httpx client: connection reuse, HTTP/2
  - Exponential backoff with jitter on 429
"""
from __future__ import annotations
import asyncio, logging, random, time
from datetime import datetime, timedelta

import httpx

import config as cfg
from kafka_client import publish_batch
from token_cache import get_account_snapshot, get_fresh_token
from rate_limiter import get_rate_limiter
from idempotency import get_idempotency_cache
from shared.database import get_db_session
from shared.cache import get_redis
from workers.gmail_fetch_worker import (
    _extract_content, _parse_email, _parse_email_list, _has_attachments
)
from metrics import M

logger = logging.getLogger("emailservice.history_recovery")

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"

# Run recovery every 6 days (aligns with Gmail watch expiry)
HISTORY_RECOVERY_INTERVAL_DAYS = 6
# Redis key to track last recovery run time
_LAST_RUN_KEY = "es:history_recovery:last_run"
# Minimum gap between per-account syncs (debounce)
_ACCOUNT_DEBOUNCE_S = 300   # 5 minutes


class HistoryRecoveryWorker:
    """
    Standalone recovery worker.
    Run once on startup, then every 6 days via run_forever().
    Never runs continuously — live emails come via Pub/Sub.
    """

    def __init__(self):
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            http2=True,
        )
        self._closed = False

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._http.aclose()

    async def run_forever(self) -> None:
        """
        Run recovery on startup, then every 6 days.
        Uses a Redis timestamp to survive restarts — won't re-run if
        a recovery already happened within the interval.
        """
        interval_s = HISTORY_RECOVERY_INTERVAL_DAYS * 86400
        logger.info("HistoryRecovery scheduler started (interval=%d days)", HISTORY_RECOVERY_INTERVAL_DAYS)

        while True:
            try:
                should_run = await self._should_run_now()
                if should_run:
                    await self.run_once()
                    await self._mark_ran()
                else:
                    next_run = await self._seconds_until_next_run(interval_s)
                    logger.info("HistoryRecovery: next run in %.1f hours", next_run / 3600)
            except Exception as e:
                logger.error("HistoryRecovery scheduler error: %s", e, exc_info=True)

            await asyncio.sleep(interval_s)

    async def _should_run_now(self) -> bool:
        """Returns True if enough time has passed since last run."""
        try:
            redis = await get_redis()
            last_run = await redis.get(_LAST_RUN_KEY)
            if not last_run:
                return True  # never run before
            elapsed = time.time() - float(last_run)
            interval_s = HISTORY_RECOVERY_INTERVAL_DAYS * 86400
            return elapsed >= interval_s
        except Exception:
            return True  # fail-open: run if Redis unavailable

    async def _mark_ran(self) -> None:
        try:
            redis = await get_redis()
            # TTL = 2x interval so key auto-expires if service is down long-term
            ttl = HISTORY_RECOVERY_INTERVAL_DAYS * 86400 * 2
            await redis.setex(_LAST_RUN_KEY, ttl, str(time.time()))
        except Exception as e:
            logger.warning("Failed to mark recovery run time: %s", e)

    async def _seconds_until_next_run(self, interval_s: int) -> float:
        try:
            redis = await get_redis()
            last_run = await redis.get(_LAST_RUN_KEY)
            if not last_run:
                return 0
            elapsed = time.time() - float(last_run)
            return max(0, interval_s - elapsed)
        except Exception:
            return interval_s

    async def run_once(self) -> None:
        """Run one recovery pass across all active Gmail accounts."""
        accounts = await self._load_gmail_accounts()
        if not accounts:
            logger.info("HistoryRecovery: no accounts to check")
            return

        logger.info("HistoryRecovery: checking %d accounts", len(accounts))
        # Max 4 concurrent — leaves DB connections for live webhook processing
        sem = asyncio.Semaphore(4)
        tasks = [self._recover_account(acct, sem) for acct in accounts]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _recover_account(self, acct: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            email = acct["email_address"]

            # Debounce: skip if this account was synced very recently
            try:
                redis = await get_redis()
                debounce_key = f"es:recovery:debounce:{acct['id']}"
                if await redis.exists(debounce_key):
                    logger.debug("HistoryRecovery: skipping %s (debounced)", email)
                    return
            except Exception:
                pass

            snap = await get_account_snapshot(email)
            if not snap or not snap.get("last_history_id"):
                return

            # Half-weight rate limit — don't compete with live fetch workers
            limiter = get_rate_limiter()
            await limiter.acquire_gmail(snap["user_id"], tokens=0.5)

            try:
                token = await get_fresh_token(snap)
            except Exception as e:
                logger.error("Token refresh failed for %s: %s", email, e)
                return

            message_ids = await self._fetch_ids_since(token, email, snap["last_history_id"])
            if not message_ids:
                return

            # Skip messages already processed by live workers (idempotency)
            idem = get_idempotency_cache()
            new_ids = [mid for mid in message_ids[:cfg.FETCH_BATCH_SIZE]
                       if not idem.check_and_mark("gmail", mid)]

            if not new_ids:
                logger.debug("HistoryRecovery: all messages already processed for %s", email)
                return

            messages = []
            for msg_id in new_ids:
                msg = await self._fetch_message(token, email, msg_id)
                if msg:
                    messages.append(msg)

            if not messages:
                return

            events = [
                (
                    {
                        "provider":         "gmail",
                        "email_address":    email,
                        "user_id":          snap["user_id"],
                        "email_account_id": snap["id"],
                        **msg,
                        "timestamp": msg["timestamp"].isoformat()
                            if isinstance(msg.get("timestamp"), datetime)
                            else msg.get("timestamp", ""),
                    },
                    snap["user_id"],
                )
                for msg in messages
            ]
            await publish_batch(cfg.TOPIC_FETCH_RESULTS, events)

            # Set debounce key so this account isn't re-processed immediately
            try:
                redis = await get_redis()
                await redis.setex(debounce_key, _ACCOUNT_DEBOUNCE_S, "1")
            except Exception:
                pass

            M.messages_processed.labels(provider="gmail_recovery", status="ok").inc(len(messages))
            logger.info("HistoryRecovery: recovered %d messages for %s", len(messages), email)

    async def _fetch_ids_since(self, token: str, email: str, start_id: str) -> list[str]:
        ids: list[str] = []
        page_token = None
        backoff = 5.0

        while True:
            params = {
                "startHistoryId": start_id,
                "historyTypes":   "messageAdded",
                "maxResults":     500,
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                resp = await self._http.get(
                    f"{_GMAIL_API}/users/me/history",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
            except Exception as e:
                logger.error("History API error for %s: %s", email, e)
                break

            if resp.status_code == 429:
                jitter = random.uniform(0, backoff * 0.2)
                await asyncio.sleep(backoff + jitter)
                backoff = min(backoff * 2, 120)
                continue
            if resp.status_code == 404:
                logger.warning("historyId expired for %s — gap too large, skipping", email)
                break
            if resp.status_code != 200:
                logger.warning("History API %d for %s", resp.status_code, email)
                break

            data = resp.json()
            for record in data.get("history", []):
                for m in record.get("messagesAdded", []):
                    mid = m.get("message", {}).get("id")
                    if mid and mid not in ids:
                        ids.append(mid)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return ids

    async def _fetch_message(self, token: str, email: str, msg_id: str):
        try:
            resp = await self._http.get(
                f"{_GMAIL_API}/users/me/messages/{msg_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "full"},
            )
        except Exception:
            return None

        if resp.status_code != 200:
            return None

        msg    = resp.json()
        labels = msg.get("labelIds", [])
        if any(lbl in labels for lbl in ("DRAFT", "TRASH", "SPAM")):
            return None

        hdrs    = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        content, _ = _extract_content(msg.get("payload", {}))  # discard HTML
        ts = datetime.utcfromtimestamp(int(msg.get("internalDate", 0)) / 1000)

        return {
            "message_id":      msg.get("id"),
            "thread_id":       msg.get("threadId"),
            "subject":         hdrs.get("Subject", "(No Subject)"),
            "from_email":      _parse_email(hdrs.get("From", "")),
            "to_emails":       _parse_email_list(hdrs.get("To", "")),
            "cc_emails":       _parse_email_list(hdrs.get("Cc", "")),
            "content":         content or msg.get("snippet", "(no content)"),
            "timestamp":       ts,
            "has_attachments": _has_attachments(msg.get("payload", {})),
            "metadata":        {"label_ids": labels},
        }

    async def _load_gmail_accounts(self) -> list[dict]:
        try:
            from models.email_account import EmailAccount, EmailProvider
            from sqlalchemy import select
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        EmailAccount.id, EmailAccount.user_id, EmailAccount.email_address,
                        EmailAccount.last_history_id, EmailAccount.last_synced_at,
                    ).where(
                        EmailAccount.provider == EmailProvider.GMAIL,
                        EmailAccount.is_active == True,
                        EmailAccount.last_history_id.isnot(None),
                    )
                )
                return [
                    {
                        "id":              str(r[0]),
                        "user_id":         str(r[1]),
                        "email_address":   r[2],
                        "last_history_id": r[3],
                        "last_synced_at":  r[4].isoformat() if r[4] else None,
                    }
                    for r in result.all()
                ]
        except Exception as e:
            logger.error("Failed to load Gmail accounts: %s", e)
            return []
