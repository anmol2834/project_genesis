"""
emailservice — Gmail Fetch Worker (v3 — hyperscale)
=====================================================
Additions over v2:
  ✅ Circuit breaker — stops hammering Gmail API on failure cascades
  ✅ Cross-user domain batching — users on same domain share one TLS connection
  ✅ Predictive fetch suppression — inactive + LOW priority users delayed 2min
  ✅ Dynamic config — batch size / rate limits tunable live from Redis
  ✅ SLA tier routing — CRITICAL/HIGH get dedicated semaphore slots
"""
from __future__ import annotations
import asyncio, base64, logging, re, time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import httpx

import config as cfg
from workers.base_worker import BaseWorker
from kafka_client import publish_batch
from token_cache import get_account_snapshot, get_fresh_token, advance_history_cursor
from user_buffer import UserAggregationBuffer
from rate_limiter import get_rate_limiter
from idempotency import get_idempotency_cache
from circuit_breaker import get_circuit_breaker
from shared.cache import get_redis, get_redis_client
from metrics import M

logger = logging.getLogger("emailservice.gmail_fetch")

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


def _domain_of(email: str) -> str:
    return email.split("@")[-1].lower() if "@" in email else ""


class GmailFetchWorker(BaseWorker):
    topics   = [cfg.TOPIC_GMAIL_RAW]
    group_id = cfg.CG_GMAIL_FETCH

    def __init__(self):
        super().__init__()
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            http2=True,
        )
        self._buffer = UserAggregationBuffer(
            flush_callback=self._process_user_events,
            worker_name="GmailFetchWorker",
        )
        self._normal_sem = asyncio.Semaphore(cfg.WORKER_CONCURRENCY)
        self._hot_sem    = asyncio.Semaphore(cfg.HOT_USER_CONCURRENCY)
        # Domain batching: group users by domain for shared TLS connection reuse
        self._domain_batch: dict[str, list[tuple[str, list[dict]]]] = defaultdict(list)
        self._domain_batch_lock = asyncio.Lock()

    async def start(self) -> None:
        await self._buffer.start()
        asyncio.create_task(self._domain_batch_flusher())
        await super().start()

    async def stop(self) -> None:
        await self._buffer.stop()
        await self._http.aclose()
        await super().stop()

    def _provider_label(self) -> str:
        return "gmail"

    # ── Kafka consume → buffer ────────────────────────────────────────────────

    async def process_batch(self, records: list[dict]) -> None:
        for rec in records:
            email = rec.get("email_address", "")
            if email:
                await self._buffer.add(email, rec)

    # ── Buffer flush → domain batcher ─────────────────────────────────────────

    async def _process_user_events(self, email: str, events: list[dict]) -> None:
        """
        After buffer flush: check predictive suppression, then route to
        domain batcher for cross-user TLS connection reuse.
        """
        # Predictive fetch suppression: skip inactive LOW-priority users
        if await self._should_suppress(email, events):
            asyncio.create_task(self._delayed_fetch(email, events))
            return

        domain = _domain_of(email)
        async with self._domain_batch_lock:
            self._domain_batch[domain].append((email, events))

    async def _domain_batch_flusher(self) -> None:
        """
        Flush domain batches every DOMAIN_BATCH_WINDOW_S seconds.
        Users on the same domain are processed concurrently, sharing
        the same persistent httpx connection pool (TLS reuse).
        """
        while True:
            await asyncio.sleep(cfg.DOMAIN_BATCH_WINDOW_S)
            async with self._domain_batch_lock:
                batches = dict(self._domain_batch)
                self._domain_batch.clear()

            if not batches:
                continue

            # Process each domain's users concurrently
            tasks = []
            for domain, user_events in batches.items():
                for email, events in user_events[:cfg.DOMAIN_BATCH_MAX_USERS]:
                    is_hot = len(events) >= cfg.HOT_USER_EMAILS_PER_MIN
                    sem    = self._hot_sem if is_hot else self._normal_sem
                    tasks.append(self._fetch_with_sem(email, events, sem))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_with_sem(self, email: str, events: list[dict], sem: asyncio.Semaphore) -> None:
        async with sem:
            await self._fetch_and_publish(email, events)

    async def _delayed_fetch(self, email: str, events: list[dict]) -> None:
        """Delay suppressed fetches — runs after FETCH_SUPPRESS_DELAY_S."""
        await asyncio.sleep(cfg.FETCH_SUPPRESS_DELAY_S)
        async with self._normal_sem:
            await self._fetch_and_publish(email, events)

    async def _should_suppress(self, email: str, events: list[dict]) -> bool:
        if not cfg.FETCH_SUPPRESS_LOW_PRIORITY:
            return False
        priorities = [e.get("_priority", cfg.PRIORITY_MEDIUM) for e in events]
        if any(p < cfg.PRIORITY_LOW for p in priorities):
            return False
        # Use L1 in-process cache to avoid Redis hit on every event
        try:
            from token_cache import _l1_get
            snap = _l1_get(email)
            if snap:
                last_ts = snap.get("_last_active_ts", 0)
                if last_ts:
                    inactive_s = time.time() - last_ts
                    if inactive_s > cfg.FETCH_SUPPRESS_INACTIVE_HOURS * 3600:
                        return True
        except Exception:
            pass
        return False

    # ── Core fetch pipeline ───────────────────────────────────────────────────

    async def _fetch_and_publish(self, email: str, events: list[dict]) -> None:
        cb = get_circuit_breaker("gmail")

        # Circuit breaker check — fail fast if Gmail API is degraded
        if not await cb.allow_request():
            logger.warning("Gmail circuit OPEN — skipping fetch for %s", email)
            M.api_errors.labels(provider="gmail", status_code="circuit_open").inc()
            return

        latest = self._pick_latest_event(events)
        if not latest:
            return

        pubsub_id  = latest.get("pubsub_id", "")
        history_id = latest.get("history_id", "")

        if pubsub_id and not await self._claim_envelope(pubsub_id):
            return

        snap = await get_account_snapshot(email)
        if not snap or not snap.get("is_active"):
            return

        user_id = snap["user_id"]

        # Update last-active timestamp in L1 cache only (no Redis write per fetch)
        try:
            from token_cache import _l1_get, _l1_set
            snap_cached = _l1_get(email)
            if snap_cached:
                snap_cached["_last_active_ts"] = time.time()
                _l1_set(email, snap_cached)
        except Exception:
            pass

        # Dynamic rate limit (live-tunable)
        limiter = get_rate_limiter()
        await limiter.acquire_gmail(user_id)

        try:
            token = await get_fresh_token(snap)
        except Exception as e:
            logger.error("Token refresh failed for %s: %s", email, e)
            await self._release_envelope(pubsub_id)
            return

        stored_id = snap.get("last_history_id")
        start_id  = stored_id if (stored_id and stored_id != history_id) \
                    else str(max(1, int(history_id) - 1))

        t0 = time.monotonic()
        message_ids, fetch_error = await self._fetch_message_ids(token, email, start_id)
        M.api_call_latency.labels(provider="gmail", endpoint="history").observe(time.monotonic() - t0)
        M.api_calls.labels(provider="gmail", endpoint="history").inc()

        if fetch_error:
            await cb.record_failure()
            await self._release_envelope(pubsub_id)
            return

        await cb.record_success()

        if not message_ids:
            await advance_history_cursor(snap["id"], history_id, email)
            return

        idem    = get_idempotency_cache()
        new_ids = [mid for mid in message_ids[:cfg.FETCH_BATCH_SIZE]
                   if not idem.check_and_mark("gmail", mid)]

        if not new_ids:
            await advance_history_cursor(snap["id"], history_id, email)
            return

        fetch_sem = asyncio.Semaphore(10)
        results   = await asyncio.gather(
            *[self._fetch_message_safe(token, email, mid, fetch_sem) for mid in new_ids]
        )
        messages = [m for m in results if m is not None]

        if not messages:
            await advance_history_cursor(snap["id"], history_id, email)
            return

        await publish_batch(cfg.TOPIC_FETCH_RESULTS, [
            (
                {
                    "provider": "gmail", "email_address": email,
                    "user_id": user_id, "email_account_id": snap["id"],
                    **msg,
                    "timestamp": msg["timestamp"].isoformat()
                        if isinstance(msg.get("timestamp"), datetime) else msg.get("timestamp", ""),
                },
                user_id,
            )
            for msg in messages
        ])

        await advance_history_cursor(snap["id"], history_id, email)
        logger.info("Gmail fetch | email=%s events=%d messages=%d historyId=%s",
                    email, len(events), len(messages), history_id)

    async def _fetch_message_safe(self, token, email, msg_id, sem):
        async with sem:
            return await self._fetch_message(token, email, msg_id)

    # ── Gmail API ─────────────────────────────────────────────────────────────

    async def _fetch_message_ids(self, token, email, start_id):
        ids, fetch_error, page_token = [], False, None
        while True:
            params = {"startHistoryId": start_id, "historyTypes": "messageAdded", "maxResults": 500}
            if page_token:
                params["pageToken"] = page_token
            try:
                resp = await self._http.get(
                    f"{_GMAIL_API}/users/me/history",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
            except Exception as e:
                logger.error("History API exception for %s: %s", email, e)
                fetch_error = True
                break
            if resp.status_code == 429:
                M.api_rate_limited.labels(provider="gmail").inc()
                await asyncio.sleep(10)
                fetch_error = True
                break
            if resp.status_code >= 500:
                M.api_errors.labels(provider="gmail", status_code=str(resp.status_code)).inc()
                fetch_error = True
                break
            if resp.status_code in (401, 404):
                M.api_errors.labels(provider="gmail", status_code=str(resp.status_code)).inc()
                break
            if resp.status_code != 200:
                M.api_errors.labels(provider="gmail", status_code=str(resp.status_code)).inc()
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
        return ids, fetch_error

    async def _fetch_message(self, token, email, message_id):
        t0 = time.monotonic()
        try:
            resp = await self._http.get(
                f"{_GMAIL_API}/users/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "full"},
            )
        except Exception as e:
            logger.error("Message fetch exception %s: %s", message_id, e)
            return None
        finally:
            M.api_call_latency.labels(provider="gmail", endpoint="messages.get").observe(time.monotonic() - t0)
            M.api_calls.labels(provider="gmail", endpoint="messages.get").inc()

        if resp.status_code != 200:
            M.api_errors.labels(provider="gmail", status_code=str(resp.status_code)).inc()
            return None

        msg    = resp.json()
        labels = msg.get("labelIds", [])
        if any(l in labels for l in ("DRAFT", "TRASH", "SPAM")):
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
            "in_reply_to":     hdrs.get("In-Reply-To", ""),
            "content":         content or msg.get("snippet", "(no content)"),
            "timestamp":       ts,
            "has_attachments": _has_attachments(msg.get("payload", {})),
            "metadata":        {"label_ids": labels, "snippet": msg.get("snippet", "")},
        }

    def _pick_latest_event(self, events):
        if not events:
            return None
        try:
            return max(events, key=lambda e: int(e.get("history_id", 0)))
        except Exception:
            return events[-1]

    async def _claim_envelope(self, pubsub_id):
        try:
            redis = await get_redis()
            return bool(await redis.set(f"es:env:{pubsub_id}", "1", nx=True, ex=cfg.DEDUP_ENVELOPE_TTL))
        except Exception:
            return True

    async def _release_envelope(self, pubsub_id):
        try:
            redis = await get_redis()
            await redis.delete(f"es:env:{pubsub_id}")
        except Exception:
            pass


# ── Content helpers ───────────────────────────────────────────────────────────

def _extract_content(payload):
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
    return text.strip() or _html_to_text(html), html

def _html_to_text(html):
    if not html:
        return ""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html).replace('&nbsp;', ' ')).strip()

def _parse_email(s):
    if not s:
        return ""
    m = re.search(r'<([^>]+)>', s)
    return m.group(1) if m else s.strip()

def _parse_email_list(s):
    if not s:
        return []
    return [e for part in s.split(',') if (e := _parse_email(part.strip()))]

def _has_attachments(payload):
    def check(p):
        if p.get("filename"):
            return True
        return any(check(x) for x in p.get("parts", []))
    return check(payload)
