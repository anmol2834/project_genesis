"""
emailservice — SMTP/IMAP Worker (IMAP IDLE — push-based)
==========================================================
Replaces the polling-based SmtpPoller with IMAP IDLE connections.

IMAP IDLE (RFC 2177):
  - Server pushes EXISTS/RECENT notifications when new mail arrives
  - Client holds a persistent connection, no polling
  - Timeout: 29 minutes (RFC recommends < 30 min), then re-issue IDLE
  - Zero Redis commands while idle — only fires when mail arrives

Architecture:
  - One IdleConnection per SMTP account (managed by ImapIdleManager)
  - On new mail notification: fetch UNSEEN messages → publish to store_ready
  - On connection error: reconnect after IMAP_RECONNECT_DELAY_S
  - Graceful shutdown: sends DONE command before closing

Fallback for servers that don't support IDLE:
  - Falls back to NOOP polling every IMAP_IDLE_TIMEOUT_S seconds
  - Still far better than the old 30s polling loop
"""
from __future__ import annotations
import asyncio, email as _email_lib, imaplib, logging, re, time
from datetime import datetime
from email.header import decode_header
from typing import Optional

import config as cfg
from pipeline import store_message_with_retry
from token_cache import get_account_snapshot
from shared.database import get_db_session
from idempotency import get_idempotency_cache
from metrics import M

logger = logging.getLogger("emailservice.smtp_fetch")


class ImapIdleConnection:
    """
    Manages a single IMAP IDLE connection for one account.
    Push-based: server notifies us when new mail arrives.
    """

    def __init__(self, snap: dict):
        self._snap    = snap
        self._running = False
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    async def run(self) -> None:
        """Main loop: connect → IDLE → on notification fetch → repeat."""
        self._running = True
        email = self._snap.get("email_address", "?")
        logger.info("IMAP IDLE started | email=%s", email)

        while self._running:
            try:
                await self._connect_and_idle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("IMAP IDLE error for %s: %s — reconnecting in %ds",
                             email, e, cfg.IMAP_RECONNECT_DELAY_S)
                await asyncio.sleep(cfg.IMAP_RECONNECT_DELAY_S)

    async def stop(self) -> None:
        self._running = False
        if self._imap:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._close_imap)
            except Exception:
                pass

    def _close_imap(self) -> None:
        try:
            self._imap.send(b"DONE\r\n")
        except Exception:
            pass
        try:
            self._imap.logout()
        except Exception:
            pass
        self._imap = None

    async def _connect_and_idle(self) -> None:
        loop = asyncio.get_event_loop()
        snap = self._snap

        # Refresh snap in case credentials changed
        fresh = await get_account_snapshot(snap["email_address"])
        if fresh:
            self._snap = snap = fresh

        from encryption import decrypt_token
        host = snap.get("imap_host") or snap.get("smtp_host") or "imap.gmail.com"
        port = snap.get("imap_port") or 993
        user = snap.get("smtp_username") or snap.get("email_address")
        pwd  = decrypt_token(snap["smtp_password"]) if snap.get("smtp_password") else ""

        # Connect + login in thread pool (blocking I/O)
        def _connect():
            imap = imaplib.IMAP4_SSL(host, port)
            imap.login(user, pwd)
            imap.select("INBOX")
            return imap

        self._imap = await loop.run_in_executor(None, _connect)

        # Check for IDLE capability
        caps = self._imap.capabilities
        supports_idle = b"IDLE" in caps if caps else False

        if supports_idle:
            await self._idle_loop(loop)
        else:
            # Fallback: NOOP every IMAP_IDLE_TIMEOUT_S
            await self._noop_loop(loop)

    async def _idle_loop(self, loop) -> None:
        """True IMAP IDLE — server pushes notifications."""
        email = self._snap.get("email_address", "?")
        while self._running:
            # Send IDLE command
            def _start_idle():
                self._imap.send(b"A001 IDLE\r\n")
                # Read the continuation response (+ idling)
                self._imap.readline()

            await loop.run_in_executor(None, _start_idle)

            # Wait for server notification (up to IMAP_IDLE_TIMEOUT_S)
            def _wait_for_notification():
                self._imap.sock.settimeout(cfg.IMAP_IDLE_TIMEOUT_S)
                try:
                    line = self._imap.readline()
                    return line
                except Exception:
                    return b""

            notification = await loop.run_in_executor(None, _wait_for_notification)

            # Send DONE to exit IDLE
            def _end_idle():
                try:
                    self._imap.send(b"DONE\r\n")
                    self._imap.readline()  # OK response
                except Exception:
                    pass

            await loop.run_in_executor(None, _end_idle)

            # If we got a real notification (EXISTS/RECENT), fetch new messages
            if notification and (b"EXISTS" in notification or b"RECENT" in notification):
                logger.debug("IMAP IDLE notification for %s: %s", email, notification[:80])
                await self._fetch_and_store(loop)

    async def _noop_loop(self, loop) -> None:
        """Fallback for servers without IDLE support."""
        while self._running:
            await asyncio.sleep(cfg.IMAP_IDLE_TIMEOUT_S)
            def _noop():
                self._imap.noop()
            await loop.run_in_executor(None, _noop)
            await self._fetch_and_store(loop)

    async def _fetch_and_store(self, loop) -> None:
        """Fetch UNSEEN messages and store them via pipeline."""
        snap = self._snap
        messages = await loop.run_in_executor(None, self._fetch_unseen)
        if not messages:
            return

        idem = get_idempotency_cache()
        stored = 0
        for msg in messages:
            event_id = f"smtp:{snap['id']}:{msg['message_id']}"
            if idem.check_and_mark("smtp_store", event_id):
                continue

            msg["user_id"]    = snap["user_id"]
            msg["account_id"] = snap["id"]
            msg["provider"]   = "smtp"
            msg["event_id"]   = event_id
            msg["direction"]  = "incoming"

            ok = await store_message_with_retry(msg)
            if ok:
                stored += 1

        if stored:
            logger.info("IMAP IDLE: stored %d messages for %s", stored, snap.get("email_address"))
            M.messages_processed.labels(provider="smtp", status="ok").inc(stored)

    def _fetch_unseen(self) -> list[dict]:
        messages = []
        try:
            _, data = self._imap.search(None, "UNSEEN")
            msg_nums = data[0].split()
            for num in msg_nums[-50:]:  # max 50 per fetch
                _, raw = self._imap.fetch(num, "(RFC822)")
                if raw and raw[0]:
                    parsed = _parse_raw_email(raw[0][1])
                    if parsed:
                        messages.append(parsed)
        except Exception as e:
            logger.error("IMAP fetch error: %s", e)
        return messages


class ImapIdleManager:
    """
    Manages IMAP IDLE connections for all active SMTP accounts.
    Starts one IdleConnection per account on startup.
    Monitors for new accounts added at runtime.
    """

    def __init__(self):
        self._connections: dict[str, ImapIdleConnection] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        accounts = await _load_smtp_accounts()
        for acct in accounts:
            await self._start_account(acct)
        # Monitor for new accounts every 5 minutes
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("ImapIdleManager started | accounts=%d", len(self._connections))

    async def stop(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        for conn in self._connections.values():
            await conn.stop()
        self._connections.clear()

    async def _start_account(self, acct: dict) -> None:
        account_id = acct["id"]
        if account_id in self._connections:
            return
        snap = await get_account_snapshot(acct["email_address"])
        if not snap or not snap.get("smtp_password"):
            return
        conn = ImapIdleConnection(snap)
        self._connections[account_id] = conn
        asyncio.create_task(conn.run())
        logger.info("IMAP IDLE connection started | email=%s", acct["email_address"])

    async def _monitor_loop(self) -> None:
        """Check for new SMTP accounts every 5 minutes."""
        while self._running:
            await asyncio.sleep(300)
            try:
                accounts = await _load_smtp_accounts()
                for acct in accounts:
                    if acct["id"] not in self._connections:
                        await self._start_account(acct)
            except Exception as e:
                logger.error("ImapIdleManager monitor error: %s", e)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_smtp_accounts() -> list[dict]:
    try:
        from models.email_account import EmailAccount, EmailProvider
        from sqlalchemy import select
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount.id, EmailAccount.user_id, EmailAccount.email_address)
                .where(
                    EmailAccount.provider.in_([EmailProvider.SMTP, EmailProvider.YAHOO, EmailProvider.ZOHO]),
                    EmailAccount.is_active == True,
                )
            )
            return [
                {"id": str(r[0]), "user_id": str(r[1]), "email_address": r[2]}
                for r in result.all()
            ]
    except Exception as e:
        logger.error("Failed to load SMTP accounts: %s", e)
        return []


def _parse_raw_email(raw: bytes) -> Optional[dict]:
    try:
        msg = _email_lib.message_from_bytes(raw)
        subject  = _decode_header_value(msg.get("Subject", ""))
        from_raw = msg.get("From", "")
        to_raw   = msg.get("To", "")
        msg_id   = msg.get("Message-ID", "").strip("<>")
        thread_id = msg.get("References", msg_id).split()[-1].strip("<>") if msg.get("References") else msg_id

        content = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                content = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break

        date_str = msg.get("Date", "")
        try:
            from email.utils import parsedate_to_datetime
            ts = parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            ts = datetime.utcnow()

        return {
            "message_id":      msg_id or f"smtp-{time.time()}",
            "thread_id":       thread_id,
            "subject":         subject,
            "from_email":      _parse_email_addr(from_raw),
            "to_emails":       [_parse_email_addr(a) for a in to_raw.split(",") if a.strip()],
            "cc_emails":       [],
            "content":         content.strip() or "(no content)",
            "timestamp":       ts,
            "has_attachments": any(part.get_filename() for part in msg.walk() if part.get_filename()),
            "metadata":        {},
        }
    except Exception as e:
        logger.error("Email parse error: %s", e)
        return None


def _decode_header_value(value: str) -> str:
    parts = decode_header(value)
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="ignore")
        else:
            result += part
    return result


def _parse_email_addr(s: str) -> str:
    m = re.search(r'<([^>]+)>', s)
    return m.group(1) if m else s.strip()
