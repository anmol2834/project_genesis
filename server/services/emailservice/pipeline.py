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
from email_filter import should_filter
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

async def process_gmail_event(pubsub_id: str, email_address: str, history_id: str) -> bool:
    """
    Process a Gmail Pub/Sub notification directly.
    Called from webhook handler — no Redis Stream involved.
    Returns True on success, False on failure (caller will queue for retry).
    """
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

        # Get fresh token
        token = await get_fresh_token(snap)

        # Fetch message IDs from Gmail History API
        stored_id = snap.get("last_history_id")
        start_id  = stored_id if (stored_id and stored_id != history_id) \
                    else str(max(1, int(history_id) - 1))

        message_ids, fetch_error = await _fetch_message_ids(token, email_address, start_id)

        if fetch_error:
            await cb.record_failure()
            return False

        await cb.record_success()

        if not message_ids:
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
        messages = [m for m in results if m and not isinstance(m, Exception)]

        if not messages:
            await advance_history_cursor(snap["id"], history_id, email_address)
            return True

        # Filter + store directly
        stored = 0
        for msg in messages:
            if should_filter(msg.get("subject", ""), msg.get("from_email", "")):
                continue
            if get_dedup().is_duplicate(msg["message_id"]):
                continue
            get_dedup().mark_seen(msg["message_id"])

            direction = "outgoing" if msg.get("from_email", "").lower() == email_address.lower() else "incoming"
            msg["direction"] = direction

            ok = await _store_message(msg, user_id, snap["id"], "gmail", email_address)
            if ok:
                stored += 1
                # Notify automation service (fire-and-forget, no stream needed)
                if direction == "incoming":
                    asyncio.create_task(_notify_automation(user_id, msg["message_id"], msg.get("thread_id", "")))

        await advance_history_cursor(snap["id"], history_id, email_address)
        if stored:
            logger.info("Gmail processed | email=%s messages=%d stored=%d historyId=%s",
                        email_address, len(messages), stored, history_id)
        return True

    except Exception as e:
        logger.error("Gmail processing failed for %s: %s", email_address, e, exc_info=True)
        return False


async def process_outlook_event(subscription_id: str, message_id: str) -> bool:
    """Process an Outlook Graph notification directly."""
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

        if should_filter(msg.get("subject", ""), msg.get("from_email", "")):
            return True

        email_address = snap["email_address"]
        direction = "outgoing" if msg.get("from_email", "").lower() == email_address.lower() else "incoming"
        msg["direction"] = direction

        ok = await _store_message(msg, snap["user_id"], snap["id"], "outlook", email_address)
        if ok and direction == "incoming":
            asyncio.create_task(_notify_automation(snap["user_id"], msg["message_id"], msg.get("thread_id", "")))

        return True
    except Exception as e:
        logger.error("Outlook processing failed for msg %s: %s", message_id, e, exc_info=True)
        return False


# ── Storage ───────────────────────────────────────────────────────────────────

async def _store_message(msg: dict, user_id: str, account_id: str, provider: str, email_address: str) -> bool:
    """Write message + upsert conversation to PostgreSQL."""
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
            "metadata":         msg.get("metadata") or {},
        }

        async with get_db_session() as session:
            # Insert message
            stmt = (
                pg_insert(EmailMessage.__table__)
                .values([row])
                .on_conflict_do_nothing(index_elements=["user_id", "message_id"])
            )
            result = await session.execute(stmt)

            # Upsert conversation
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
            await session.execute(conv_stmt)
            await session.commit()

        M.db_writes.labels(table="es_messages", status="ok").inc(1)
        return True

    except Exception as e:
        logger.error("Store failed for msg %s: %s", msg.get("message_id", "?"), e, exc_info=True)
        M.db_writes.labels(table="es_messages", status="error").inc(1)
        return False


# ── Gmail API helpers ─────────────────────────────────────────────────────────

async def _fetch_message_ids(token: str, email: str, start_id: str):
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
            logger.error("History API error for %s: %s", email, e)
            return ids, True

        if resp.status_code == 429:
            await asyncio.sleep(10)
            return ids, True
        if resp.status_code >= 500:
            return ids, True
        if resp.status_code in (401, 404):
            return ids, False  # auth error or expired history — not retryable
        if resp.status_code != 200:
            return ids, False

        data = resp.json()
        for record in data.get("history", []):
            for m in record.get("messagesAdded", []):
                mid = m.get("message", {}).get("id")
                if mid and mid not in ids:
                    ids.append(mid)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids, False


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
        return None

    if resp.status_code != 200:
        return None

    msg    = resp.json()
    labels = msg.get("labelIds", [])
    if any(l in labels for l in ("DRAFT", "TRASH", "SPAM")):
        return None

    hdrs    = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
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
        "metadata":        {"label_ids": labels, "snippet": msg.get("snippet", "")},
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

    return {
        "message_id":      m.get("id", message_id),
        "thread_id":       m.get("conversationId", ""),
        "subject":         m.get("subject", "(No Subject)"),
        "from_email":      m.get("from", {}).get("emailAddress", {}).get("address", ""),
        "to_emails":       [r["emailAddress"]["address"] for r in m.get("toRecipients", [])],
        "cc_emails":       [r["emailAddress"]["address"] for r in m.get("ccRecipients", [])],
        "content":         body_content if body_type == "text" else _html_to_text(body_content),
        "timestamp":       ts,
        "has_attachments": m.get("hasAttachments", False),
        "metadata":        {},
    }


# ── Automation notification (fire-and-forget) ─────────────────────────────────

async def _notify_automation(user_id: str, message_id: str, thread_id: str) -> None:
    """
    Notify automation service about new incoming message.
    Uses a simple HTTP POST — no Redis Stream needed.
    If automation service is down, this silently fails (non-critical path).
    """
    try:
        from shared.config import get_config
        automation_url = get_config().AUTOMATION_SERVICE_URL
        if not automation_url:
            return
        http = get_http_client()
        await http.post(
            f"{automation_url}/ai/process",
            json={"user_id": user_id, "message_id": message_id, "thread_id": thread_id},
            timeout=5.0,
        )
    except Exception:
        pass  # automation is optional — don't fail email processing


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
    return text.strip()

def _html_to_text(html: str) -> str:
    if not html:
        return ""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html).replace('&nbsp;', ' ')).strip()

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
