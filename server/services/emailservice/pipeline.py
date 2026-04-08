"""
emailservice — Direct Processing Pipeline
==========================================
Enterprise-grade, event-driven email processing.

Architecture:
  Webhook arrives → process() called directly → DB write
  No intermediate streams. No idle workers. Zero Redis commands when idle.

  Redis Stream (email_queue) is used ONLY as a crash-recovery buffer:
  - If direct processing fails → push to email_queue
  - Recovery worker drains email_queue on startup and every 5 min
  - Normal path: webhook → process() → DB (0 Redis commands)

Redis command budget:
  Idle:   0 commands/sec (no polling workers)
  Active: ~5 commands per email (XADD on failure, XACK on recovery)
  vs old: ~10 commands/sec idle = 864,000/day

Scales to millions of users:
  - Add more FastAPI workers (horizontal scaling)
  - Each worker processes independently (no shared state)
  - Redis Stream handles burst buffering automatically
"""
from __future__ import annotations
import asyncio, json, logging, time
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert

import config as cfg
from token_cache import get_account_snapshot, get_fresh_token, advance_history_cursor
from email_filter import should_filter, should_filter_by_labels
from dedup import get_dedup
from idempotency import get_idempotency_cache
from circuit_breaker import get_circuit_breaker
from rate_limiter import get_rate_limiter
from shared.database import get_db_session
from shared.cache import get_redis_client
from models.messages import EmailMessage, MessageStatus
from models.conversations import EmailConversation
from metrics import M

import httpx, base64, re

logger = logging.getLogger("emailservice.pipeline")

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"

# Single shared HTTP client — reused across all requests
_http_client: httpx.AsyncClient | None = None

def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
            http2=True,
        )
    return _http_client

async def close_http_client() -> None:
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ── Main entry points ─────────────────────────────────────────────────────────

async def process_gmail_event(pubsub_id: str, email_address: str, history_id: str, event_id: str = "") -> bool:
    """
    Process a Gmail Pub/Sub notification.
    Called from GmailFetchWorker (stream consumer), not from webhook handler.
    Returns True on success, False on transient failure (caller will retry via DLQ).
    """
    if not event_id:
        event_id = f"gmail:{pubsub_id}"
    try:
        # Envelope dedup — prevent double-processing same pubsub notification
        idem = get_idempotency_cache()
        if idem.check_and_mark("pubsub", pubsub_id):
            logger.debug("Duplicate pubsub_id %s — skipping", pubsub_id)
            return True  # already processed, not a failure

        # Circuit breaker
        cb = get_circuit_breaker("gmail")
        if not await cb.allow_request():
            logger.warning("Gmail circuit OPEN — queuing %s for retry", email_address)
            return False

        # Load account
        snap = await get_account_snapshot(email_address)
        if not snap or not snap.get("is_active"):
            return True  # account not found/inactive — not a failure worth retrying

        user_id = snap["user_id"]

        # Rate limit
        await get_rate_limiter().acquire_gmail(user_id)

        # Get fresh token — always attempt refresh if expired
        token = await get_fresh_token(snap)

        # Fetch message IDs from Gmail History API
        stored_id = snap.get("last_history_id")
        start_id  = stored_id if (stored_id and stored_id != history_id) \
                    else str(max(1, int(history_id) - 1))

        message_ids, fetch_error, auth_error = await _fetch_message_ids(token, email_address, start_id)

        if auth_error:
            # Token was expired even after get_fresh_token() — force re-fetch from DB
            # and retry once with a fresh token
            logger.warning("Auth error for %s — forcing token refresh from DB", email_address)
            from token_cache import invalidate as _invalidate
            await _invalidate(email_address)
            snap_fresh = await get_account_snapshot(email_address)
            if snap_fresh:
                token_fresh = await get_fresh_token(snap_fresh)
                message_ids, fetch_error, auth_error = await _fetch_message_ids(
                    token_fresh, email_address, start_id
                )
                if auth_error:
                    logger.error("Auth error persists for %s after token refresh — event will retry via DLQ",
                                 email_address)
                    await cb.record_failure()
                    return False  # → DLQ retry
            else:
                logger.error("Cannot load account for %s after cache invalidation", email_address)
                return False  # → DLQ retry

        if fetch_error:
            logger.warning("Transient fetch error for %s historyId=%s — event will retry via DLQ",
                           email_address, history_id)
            await cb.record_failure()
            return False  # → DLQ retry

        await cb.record_success()

        if not message_ids:
            logger.info("No new messages for %s historyId=%s (history gap or already processed)",
                        email_address, history_id)
            await advance_history_cursor(snap["id"], history_id, email_address)
            return True

        # Dedup message IDs
        idem_msg = get_idempotency_cache()
        new_ids = [mid for mid in message_ids[:cfg.FETCH_BATCH_SIZE]
                   if not idem_msg.check_and_mark("gmail_msg", mid)]

        if not new_ids:
            await advance_history_cursor(snap["id"], history_id, email_address)
            return True

        # Fetch full messages concurrently
        sem = asyncio.Semaphore(5)
        results = await asyncio.gather(
            *[_fetch_gmail_message_safe(token, email_address, mid, sem) for mid in new_ids],
            return_exceptions=True,
        )

        # Separate: real messages | filtered/skipped | hard errors | transient errors
        messages  = [m for m in results if isinstance(m, dict)]
        filtered  = sum(1 for m in results if m == "FILTERED")
        exceptions = [r for r in results if isinstance(r, Exception)]
        fetch_failures = sum(1 for r in results if r is None)

        if exceptions:
            logger.warning("Gmail message fetch: %d/%d raised exceptions for %s | errors: %s",
                           len(exceptions), len(new_ids), email_address,
                           [str(e)[:80] for e in exceptions[:3]])

        if filtered:
            logger.debug("Gmail: %d/%d messages filtered/skipped for %s historyId=%s",
                         filtered, len(new_ids), email_address, history_id)

        # Only retry if ALL messages were actual fetch failures (not filtered)
        if not messages and fetch_failures > 0 and filtered == 0:
            logger.warning("Gmail: all %d messages failed to fetch for %s historyId=%s — event will retry",
                           len(new_ids), email_address, history_id)
            return False  # → DLQ retry

        # If everything was filtered (e.g. all SENT/DRAFT), advance cursor and succeed
        if not messages:
            logger.debug("Gmail: all %d messages filtered for %s historyId=%s — advancing cursor",
                         len(new_ids), email_address, history_id)
            await advance_history_cursor(snap["id"], history_id, email_address)
            return True

        # Filter + store via durable store_ready queue
        store_events = []
        for msg in messages:
            # label_ids and snippet are top-level fields on the message dict
            # (set by _fetch_gmail_message) — no metadata dict needed
            label_ids = msg.get("label_ids")
            snippet   = msg.get("snippet", "")
            if should_filter(
                subject    = msg.get("subject", ""),
                from_email = msg.get("from_email", ""),
                snippet    = snippet,
                label_ids  = label_ids,
            ):
                continue
            if get_dedup().is_duplicate(msg["message_id"]):
                continue
            get_dedup().mark_seen(msg["message_id"])

            direction = "outgoing" if msg.get("from_email", "").lower() == email_address.lower() else "incoming"
            msg["direction"]  = direction
            msg["user_id"]    = user_id
            msg["account_id"] = snap["id"]
            msg["provider"]   = "gmail"
            msg["event_id"]   = event_id  # end-to-end idempotency key

            store_events.append((msg, user_id))

        if store_events:
            # Publish to store_ready stream — StorageWorker handles DB write with retry
            from stream_client import publish_batch as _pub_batch
            await _pub_batch(cfg.TOPIC_STORE_READY, store_events)
            logger.info("Gmail enqueued to store_ready | email=%s messages=%d historyId=%s",
                        email_address, len(store_events), history_id)
        else:
            logger.info("Gmail: all %d messages filtered/deduped for %s historyId=%s",
                        len(messages), email_address, history_id)

        await advance_history_cursor(snap["id"], history_id, email_address)
        return True

    except Exception as e:
        logger.error("Gmail processing failed for %s: %s", email_address, e, exc_info=True)
        return False


async def process_outlook_event(subscription_id: str, message_id: str, event_id: str = "") -> bool:
    """Process an Outlook Graph notification. Called from OutlookFetchWorker."""
    if not event_id:
        event_id = f"outlook:{subscription_id}:{message_id}"
    try:
        idem = get_idempotency_cache()
        if idem.check_and_mark("outlook_msg", message_id):
            return True

        snap = await _resolve_outlook_account(subscription_id)
        if not snap:
            return True  # can't resolve account — not retryable

        token = await get_fresh_token(snap)
        msg = await _fetch_outlook_message(token, message_id)
        if not msg:
            return True

        if should_filter(
            subject    = msg.get("subject", ""),
            from_email = msg.get("from_email", ""),
            snippet    = "",
            label_ids  = None,
        ):
            return True

        email_address = snap["email_address"]
        direction = "outgoing" if msg.get("from_email", "").lower() == email_address.lower() else "incoming"
        msg["direction"]  = direction
        msg["user_id"]    = snap["user_id"]
        msg["account_id"] = snap["id"]
        msg["provider"]   = "outlook"
        msg["event_id"]   = event_id

        # Publish to store_ready — StorageWorker handles DB write with retry
        from stream_client import publish_batch as _pub_batch
        await _pub_batch(cfg.TOPIC_STORE_READY, [(msg, snap["user_id"])])

        return True
    except Exception as e:
        logger.error("Outlook processing failed for msg %s: %s", message_id, e, exc_info=True)
        return False


# ── Storage (called by StorageWorker, not directly) ───────────────────────────

async def store_message_with_retry(msg: dict) -> bool:
    """
    Write message + upsert conversation to PostgreSQL with exponential backoff.
    Called by StorageWorker — never drops a message on DB failure.
    Returns True on success, False after max retries (caller sends to DLQ).
    """
    user_id    = msg.get("user_id", "")
    account_id = msg.get("account_id", "")
    provider   = msg.get("provider", "")

    try:
        row = {
            "message_id":       msg["message_id"],
            "thread_id":        msg.get("thread_id") or msg["message_id"],
            "user_id":          UUID(user_id),
            "email_account_id": UUID(account_id),
            "provider":         provider,
            "from_email":       msg.get("from_email", ""),
            "to_emails":        msg.get("to_emails") or [],
            "cc_emails":        msg.get("cc_emails") or [],
            "subject":          msg.get("subject") or "",
            "content":          msg.get("content") or "(no content)",
            "timestamp":        _parse_ts(msg.get("timestamp")),
            "direction":        msg.get("direction", "incoming"),
            "status":           MessageStatus.RECEIVED.value,
            "is_read":          False,
            "has_attachments":  bool(msg.get("has_attachments", False)),
        }
    except Exception as e:
        logger.error("Row build failed for msg %s: %s", msg.get("message_id", "?"), e)
        return False  # bad data — don't retry

    for attempt in range(cfg.STORE_RETRY_MAX):
        try:
            async with get_db_session() as session:
                stmt = (
                    pg_insert(EmailMessage.__table__)
                    .values([row])
                    .on_conflict_do_nothing(index_elements=["user_id", "message_id"])
                )
                await session.execute(stmt)

                conv_row = {
                    "thread_id":        row["thread_id"],
                    "user_id":          UUID(user_id),
                    "email_account_id": UUID(account_id),
                    "provider":         provider,
                    "subject":          row["subject"],
                    "participants":     _participants(msg),
                    "message_count":    1,
                    "last_message_id":  row["message_id"],
                    "last_message_at":  row["timestamp"],
                    "is_read":          False,
                    "status":           "active",
                }
                conv_stmt = (
                    pg_insert(EmailConversation.__table__)
                    .values([conv_row])
                    .on_conflict_do_update(
                        # Use constraint name — more reliable than index_elements
                        # when the table was created before the constraint was added.
                        constraint="uq_es_conversations_user_thread",
                        set_={
                            "last_message_id": pg_insert(EmailConversation.__table__).excluded.last_message_id,
                            "last_message_at": pg_insert(EmailConversation.__table__).excluded.last_message_at,
                            "message_count":   EmailConversation.__table__.c.message_count + 1,
                            "participants":    pg_insert(EmailConversation.__table__).excluded.participants,
                            "is_read":         False,
                            "updated_at":      datetime.utcnow(),
                        },
                    )
                )
                try:
                    await session.execute(conv_stmt)
                except Exception as conv_err:
                    # Constraint may not exist yet (table created before migration).
                    # Fall back to index_elements — PostgreSQL will find the unique index.
                    logger.debug("conv upsert constraint fallback for %s: %s",
                                 row["thread_id"], conv_err)
                    conv_stmt2 = (
                        pg_insert(EmailConversation.__table__)
                        .values([conv_row])
                        .on_conflict_do_update(
                            index_elements=["user_id", "thread_id"],
                            set_={
                                "last_message_id": pg_insert(EmailConversation.__table__).excluded.last_message_id,
                                "last_message_at": pg_insert(EmailConversation.__table__).excluded.last_message_at,
                                "message_count":   EmailConversation.__table__.c.message_count + 1,
                                "participants":    pg_insert(EmailConversation.__table__).excluded.participants,
                                "is_read":         False,
                                "updated_at":      datetime.utcnow(),
                            },
                        )
                    )
                    await session.execute(conv_stmt2)
                await session.commit()

            M.db_writes.labels(table="es_messages", status="ok").inc(1)

            # Publish to ai_events stream for async automation handoff
            if msg.get("direction") == "incoming":
                await _publish_ai_event(user_id, msg["message_id"],
                                        msg.get("thread_id", ""), provider,
                                        msg.get("event_id", ""))
            return True

        except Exception as e:
            delay = cfg.STORE_RETRY_BASE_DELAY_S * (2 ** attempt)
            logger.warning("DB write attempt %d/%d failed for msg %s: %s — retry in %.1fs",
                           attempt + 1, cfg.STORE_RETRY_MAX,
                           msg.get("message_id", "?"), e, delay)
            M.db_writes.labels(table="es_messages", status="error").inc(1)
            if attempt < cfg.STORE_RETRY_MAX - 1:
                await asyncio.sleep(delay)

    logger.error("DB write permanently failed for msg %s after %d attempts",
                 msg.get("message_id", "?"), cfg.STORE_RETRY_MAX)
    return False


async def _publish_ai_event(user_id: str, message_id: str, thread_id: str,
                             provider: str, event_id: str) -> None:
    """
    Publish to ai_events stream for async automation handoff.
    Includes automation_enabled flag so AIHandoffWorker can route to
    draft storage vs immediate send.
    """
    try:
        # Load automation_enabled from account snapshot (L1 cache — zero DB cost on hot path)
        automation_enabled = True  # default: send
        try:
            from token_cache import get_account_snapshot
            from models.email_account import EmailAccount
            from sqlalchemy import select as sa_select
            async with get_db_session() as _s:
                _r = await _s.execute(
                    sa_select(EmailAccount.automation_enabled, EmailAccount.id,
                              EmailAccount.email_address, EmailAccount.daily_sent_count,
                              EmailAccount.daily_send_limit)
                    .where(EmailAccount.user_id == UUID(user_id),
                           EmailAccount.is_active == True)
                    .limit(1)
                )
                _row = _r.first()
                if _row:
                    automation_enabled = bool(_row[0])
        except Exception:
            pass  # fail open — default to automation_enabled=True

        from stream_client import publish as _pub
        await _pub(
            cfg.TOPIC_AI_EVENTS,
            {
                "event_id":          event_id,
                "user_id":           user_id,
                "message_id":        message_id,
                "thread_id":         thread_id,
                "provider":          provider,
                "automation_enabled": automation_enabled,
                "ts":                time.time(),
            },
            partition_key=user_id,
        )
    except Exception as e:
        logger.warning("ai_events publish failed for msg %s: %s", message_id, e)
        # Non-critical — automation will catch up via history recovery


# ── Legacy _store_message kept for backward compat (send_reply.py uses it) ───

async def _store_message(msg: dict, user_id: str, account_id: str, provider: str, email_address: str) -> bool:
    """Backward-compatible wrapper. New code should use store_message_with_retry()."""
    msg["user_id"]    = user_id
    msg["account_id"] = account_id
    msg["provider"]   = provider
    return await store_message_with_retry(msg)


# ── Gmail API helpers ─────────────────────────────────────────────────────────

async def _fetch_message_ids(token: str, email: str, start_id: str):
    """
    Fetch message IDs from Gmail History API.
    Returns (ids, fetch_error, auth_error) where:
      - fetch_error=True  → transient failure, should retry
      - auth_error=True   → token expired/invalid, must refresh and retry
      - both False        → success (ids may be empty = no new messages)
    """
    ids, fetch_error, page_token = [], False, None
    http = get_http_client()
    while True:
        params = {"startHistoryId": start_id, "historyTypes": "messageAdded", "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        try:
            resp = await http.get(
                f"{_GMAIL_API}/users/me/history",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
        except Exception as e:
            logger.error("History API network error for %s: %s", email, e)
            return ids, True, False  # transient — retry

        if resp.status_code == 429:
            logger.warning("History API rate limited for %s", email)
            await asyncio.sleep(10)
            return ids, True, False  # transient — retry

        if resp.status_code >= 500:
            logger.warning("History API server error %d for %s", resp.status_code, email)
            return ids, True, False  # transient — retry

        if resp.status_code == 401:
            logger.warning("History API 401 (token expired) for %s — will refresh and retry", email)
            return ids, False, True  # auth error — refresh token and retry

        if resp.status_code == 404:
            # historyId too old — gap in history. Use current historyId as new start.
            logger.warning("History API 404 for %s (historyId=%s expired) — will re-sync from current",
                           email, start_id)
            return ids, False, False  # not retryable — history gap, advance cursor

        if resp.status_code != 200:
            logger.error("History API unexpected status %d for %s", resp.status_code, email)
            return ids, True, False  # treat unknown errors as transient

        data = resp.json()
        for record in data.get("history", []):
            for m in record.get("messagesAdded", []):
                mid = m.get("message", {}).get("id")
                if mid and mid not in ids:
                    ids.append(mid)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids, False, False


async def _fetch_gmail_message_safe(token: str, email: str, msg_id: str, sem: asyncio.Semaphore):
    async with sem:
        return await _fetch_gmail_message(token, email, msg_id)


async def _fetch_gmail_message(token: str, email: str, msg_id: str):
    http = get_http_client()
    try:
        resp = await http.get(
            f"{_GMAIL_API}/users/me/messages/{msg_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"format": "full"},
        )
    except Exception as e:
        logger.error("Message fetch error %s: %s", msg_id, e)
        return None  # transient network error → caller counts as failure

    if resp.status_code == 404:
        # Message deleted or not yet visible (race condition on SENT messages).
        # Return sentinel "FILTERED" so caller doesn't count this as a failure.
        logger.debug("Message %s not found (404) — likely deleted or SENT race condition", msg_id)
        return "FILTERED"

    if resp.status_code == 403:
        # Insufficient permissions for this specific message (e.g. delegated account).
        logger.debug("Message %s forbidden (403) — skipping", msg_id)
        return "FILTERED"

    if resp.status_code != 200:
        logger.warning("Message fetch HTTP %d for %s — will retry", resp.status_code, msg_id)
        return None  # real error → caller counts as failure

    msg    = resp.json()
    labels = msg.get("labelIds", [])

    # Stage 1: O(1) label check BEFORE any content parsing
    if should_filter_by_labels(labels):
        return "FILTERED"  # sentinel — not a failure

    if any(l in labels for l in ("DRAFT", "TRASH", "SPAM")):
        return "FILTERED"

    hdrs    = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    snippet = msg.get("snippet", "")

    # Stage 2-4: sender + subject + snippet check
    if should_filter(
        subject    = hdrs.get("Subject", ""),
        from_email = _parse_email(hdrs.get("From", "")),
        snippet    = snippet,
        label_ids  = labels,
    ):
        return "FILTERED"

    content = _extract_text(msg.get("payload", {}))
    ts      = datetime.utcfromtimestamp(int(msg.get("internalDate", 0)) / 1000)

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
        # label_ids and snippet kept as top-level for in-flight filtering only
        # (not persisted to DB — metadata column removed)
        "label_ids":       labels,
        "snippet":         msg.get("snippet", ""),
    }


# ── Outlook API helpers ───────────────────────────────────────────────────────

async def _resolve_outlook_account(subscription_id: str):
    try:
        redis = get_redis_client()
        cached = await redis.get(f"es:sub:{subscription_id}")
        if cached:
            import json as _json
            return _json.loads(cached)
    except Exception:
        pass
    try:
        from models.email_account import EmailAccount
        from sqlalchemy import select
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(
                    EmailAccount.id.cast(str) == subscription_id,
                    EmailAccount.is_active == True,
                ).limit(1)
            )
            acct = result.scalar_one_or_none()
            if not acct:
                return None
            return {
                "id": str(acct.id), "user_id": str(acct.user_id),
                "email_address": acct.email_address, "provider": acct.provider.value,
                "access_token": acct.access_token, "refresh_token": acct.refresh_token,
                "token_expiry": acct.token_expiry.isoformat() if acct.token_expiry else None,
            }
    except Exception as e:
        logger.error("Outlook account resolution failed: %s", e)
        return None


async def _fetch_outlook_message(token: str, message_id: str):
    http = get_http_client()
    try:
        resp = await http.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"$select": "id,subject,from,toRecipients,ccRecipients,body,receivedDateTime,hasAttachments,conversationId"},
        )
    except Exception as e:
        logger.error("Graph message fetch failed: %s", e)
        return None

    if resp.status_code != 200:
        return None

    m = resp.json()
    body_content = m.get("body", {}).get("content", "")
    body_type    = m.get("body", {}).get("contentType", "text")
    ts_raw = m.get("receivedDateTime", "")
    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        ts = datetime.utcnow()

    raw_content = body_content if body_type == "text" else _html_to_text(body_content)

    return {
        "message_id":      m.get("id", message_id),
        "thread_id":       m.get("conversationId", ""),
        "subject":         m.get("subject", "(No Subject)"),
        "from_email":      m.get("from", {}).get("emailAddress", {}).get("address", ""),
        "to_emails":       [r["emailAddress"]["address"] for r in m.get("toRecipients", [])],
        "cc_emails":       [r["emailAddress"]["address"] for r in m.get("ccRecipients", [])],
        "content":         strip_reply_chain(raw_content),
        "timestamp":       ts,
        "has_attachments": m.get("hasAttachments", False),
    }


# ── Utility functions ─────────────────────────────────────────────────────────

def _extract_text(payload: dict) -> str:
    text = ""
    def walk(part):
        nonlocal text
        mt = part.get("mimeType", "")
        if mt == "text/plain":
            d = part.get("body", {}).get("data", "")
            if d:
                text += base64.urlsafe_b64decode(d).decode("utf-8", errors="ignore")
        for p in part.get("parts", []):
            walk(p)
    walk(payload)
    if not text:
        # Fall back to HTML → text
        html = ""
        def walk_html(part):
            nonlocal html
            if part.get("mimeType") == "text/html":
                d = part.get("body", {}).get("data", "")
                if d:
                    html += base64.urlsafe_b64decode(d).decode("utf-8", errors="ignore")
            for p in part.get("parts", []):
                walk_html(p)
        walk_html(payload)
        text = _html_to_text(html)
    return strip_reply_chain(text)

def _html_to_text(html: str) -> str:
    if not html:
        return ""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL | re.IGNORECASE)
    # Convert block-level tags to newlines before stripping all tags
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</(p|div|tr|li|blockquote)>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    html = html.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    # Collapse multiple spaces on a single line but preserve newlines
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in html.split('\n')]
    return '\n'.join(lines).strip()

# Invisible/zero-width Unicode chars that email clients inject before attribution lines
_INVISIBLE_RE = re.compile(
    r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f'
    r'\u00ad\u200b-\u200f\u2028\u2029\u202a-\u202f'
    r'\u2060-\u206f\ufeff\ufff0-\uffff]'
)

# "On Tue, 7 Apr 2026 at 7:44 PM John <john@example.com> wrote:" (single or multi-line)
_ATTRIBUTION_RE = re.compile(
    r'\n?On\s.+?wrote:\s*$',
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

def strip_reply_chain(text: str) -> str:
    """
    Remove quoted reply chains from plain-text email content.
    Handles:
    - Invisible Unicode chars injected before attribution lines
    - Single-line and multi-line "On ... wrote:" headers
    - HTML-derived single-line content where attribution is inline
    - Outlook "From: / Sent: / To:" block headers
    - Lines starting with ">"
    """
    if not text:
        return text

    # 1. Strip invisible chars
    text = _INVISIBLE_RE.sub('', text)

    # 2. Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 3. Handle single-line case: if "On <weekday/month>..." appears inline,
    #    cut everything from that point. This covers HTML→text collapsed output.
    _inline_attr = re.search(
        r'\s+On\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s',
        text, re.IGNORECASE
    )
    if _inline_attr:
        text = text[:_inline_attr.start()].strip()
        return text

    # 4. Collapse multi-line attribution (Gmail wraps name + email across lines)
    text = re.sub(r'\nOn (.+?)\n(<[^>]+>)\s*wrote:', r'\nOn \1 \2 wrote:', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\nOn (.+?)\n(wrote:)', r'\nOn \1 \2', text, flags=re.IGNORECASE | re.DOTALL)

    # 5. Walk lines and cut at the first reply-chain marker
    lines = text.split('\n')
    cleaned: list[str] = []
    for line in lines:
        trimmed = line.strip()
        # "On <date> ... wrote:" — full attribution line
        if re.match(r'^On\s.+wrote:\s*$', trimmed, re.IGNORECASE):
            break
        # "On Tue/Mon/..." — start of attribution even without "wrote:" (split line)
        if re.match(r'^On\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', trimmed, re.IGNORECASE):
            break
        # Outlook block-quote header
        if re.match(r'^From:\s*.+', trimmed, re.IGNORECASE) and cleaned:
            break
        # Quoted lines
        if trimmed.startswith('>'):
            continue
        # Separator lines
        if re.match(r'^[-_]{3,}$', trimmed):
            break
        cleaned.append(line)

    return re.sub(r'\n{3,}', '\n\n', '\n'.join(cleaned)).strip()

def _parse_email(s: str) -> str:
    if not s:
        return ""
    m = re.search(r'<([^>]+)>', s)
    return m.group(1) if m else s.strip()

def _parse_email_list(s: str) -> list:
    if not s:
        return []
    return [e for part in s.split(',') if (e := _parse_email(part.strip()))]

def _has_attachments(payload: dict) -> bool:
    def check(p):
        if p.get("filename"):
            return True
        return any(check(x) for x in p.get("parts", []))
    return check(payload)

def _participants(msg: dict) -> list:
    p = set()
    if msg.get("from_email"):
        p.add(msg["from_email"].lower())
    for e in (msg.get("to_emails") or []):
        p.add(e.lower())
    return list(p)

def _parse_ts(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=None) if ts.tzinfo else ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.utcnow()
