"""
emailservice — SMTP/IMAP Fetch Worker
Consumes from: smtp_events (published by SmtpPoller)
Produces to:   fetch_results

Also runs the SmtpPoller internally — smart polling:
  - Active users (last message < 1h): poll every 60s
  - Inactive users: poll every 300s
  - IMAP IDLE when server supports it
"""
from __future__ import annotations
import asyncio, email as _email_lib, imaplib, logging, time
from datetime import datetime
from email.header import decode_header
from typing import Optional

import config as cfg
from workers.base_worker import BaseWorker
from kafka_client import publish, publish_batch
from token_cache import get_account_snapshot
from shared.database import get_db_session
from shared.cache import get_redis

logger = logging.getLogger("emailservice.smtp_fetch")


class SmtpFetchWorker(BaseWorker):
    """Consumes smtp_events and fetches IMAP messages."""
    topics   = [cfg.TOPIC_SMTP_RAW]
    group_id = cfg.CG_SMTP_FETCH

    async def process_batch(self, records: list[dict]) -> None:
        sem = asyncio.Semaphore(cfg.WORKER_CONCURRENCY)
        tasks = [self._process_one(rec, sem) for rec in records]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_one(self, rec: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            account_id = rec.get("account_id", "")
            email_addr = rec.get("email_address", "")
            if not account_id:
                return

            snap = await get_account_snapshot(email_addr) if email_addr else None
            if not snap:
                snap = await self._load_snap_by_id(account_id)
            if not snap:
                return

            messages = await self._fetch_imap(snap)
            if not messages:
                return

            events = [
                (
                    {
                        "provider":         "smtp",
                        "email_address":    snap["email_address"],
                        "user_id":          snap["user_id"],
                        "email_account_id": snap["id"],
                        **msg,
                        "timestamp": msg["timestamp"].isoformat()
                            if isinstance(msg.get("timestamp"), datetime) else msg.get("timestamp", ""),
                    },
                    snap["user_id"],
                )
                for msg in messages
            ]
            await publish_batch(cfg.TOPIC_FETCH_RESULTS, events)

    async def _load_snap_by_id(self, account_id: str) -> Optional[dict]:
        try:
            from models.email_account import EmailAccount
            from sqlalchemy import select
            from uuid import UUID
            async with get_db_session() as session:
                acct = (await session.execute(
                    select(EmailAccount).where(EmailAccount.id == UUID(account_id))
                )).scalar_one_or_none()
                if not acct:
                    return None
                return {
                    "id": str(acct.id), "user_id": str(acct.user_id),
                    "email_address": acct.email_address, "provider": acct.provider.value,
                    "smtp_host": acct.smtp_host, "smtp_port": acct.smtp_port,
                    "smtp_username": acct.smtp_username, "smtp_password": acct.smtp_password,
                    "imap_host": acct.imap_host, "imap_port": acct.imap_port,
                    "last_synced_at": acct.last_synced_at.isoformat() if acct.last_synced_at else None,
                }
        except Exception as e:
            logger.error("Failed to load SMTP snap: %s", e)
            return None

    async def _fetch_imap(self, snap: dict) -> list[dict]:
        """Fetch new IMAP messages in a thread pool (blocking I/O)."""
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._fetch_imap_sync, snap)
        except Exception as e:
            logger.error("IMAP fetch failed for %s: %s", snap.get("email_address"), e)
            return []

    def _fetch_imap_sync(self, snap: dict) -> list[dict]:
        from encryption import decrypt_token
        host = snap.get("imap_host") or snap.get("smtp_host") or "imap.gmail.com"
        port = snap.get("imap_port") or 993
        user = snap.get("smtp_username") or snap.get("email_address")
        pwd  = decrypt_token(snap["smtp_password"]) if snap.get("smtp_password") else ""

        messages = []
        try:
            with imaplib.IMAP4_SSL(host, port) as imap:
                imap.login(user, pwd)
                imap.select("INBOX")
                # Fetch UNSEEN messages only
                _, data = imap.search(None, "UNSEEN")
                msg_nums = data[0].split()
                for num in msg_nums[-50:]:  # max 50 per poll
                    _, raw = imap.fetch(num, "(RFC822)")
                    if raw and raw[0]:
                        parsed = self._parse_raw_email(raw[0][1])
                        if parsed:
                            messages.append(parsed)
        except Exception as e:
            logger.error("IMAP sync error: %s", e)

        return messages

    def _parse_raw_email(self, raw: bytes) -> Optional[dict]:
        try:
            msg = _email_lib.message_from_bytes(raw)
            subject = _decode_header_value(msg.get("Subject", ""))
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
                "has_attachments": any(
                    part.get_filename() for part in msg.walk() if part.get_filename()
                ),
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
    import re
    m = re.search(r'<([^>]+)>', s)
    return m.group(1) if m else s.strip()


# ═════════════════════════════════════════════════════════════════════════════
# SMTP SMART POLLER
# Runs as a background task inside the SMTP fetch worker process.
# Publishes smtp_events to Kafka based on activity level.
# ═════════════════════════════════════════════════════════════════════════════

class SmtpPoller:
    """
    Smart SMTP poller — polls active users frequently, inactive users rarely.
    Publishes smtp_events to Kafka; SmtpFetchWorker consumes them.
    """

    async def run(self) -> None:
        logger.info("SmtpPoller started")
        while True:
            try:
                await self._poll_all()
            except Exception as e:
                logger.error("SmtpPoller error: %s", e)
            await asyncio.sleep(30)  # check every 30s, actual poll interval per account

    async def _poll_all(self) -> None:
        accounts = await self._load_smtp_accounts()
        now = time.time()

        for acct in accounts:
            account_id = acct["id"]
            email      = acct["email_address"]
            last_msg   = acct.get("last_message_at_ts", 0)
            last_poll  = await self._get_last_poll(account_id)

            # Determine poll interval based on activity
            is_active = (now - last_msg) < cfg.SMTP_ACTIVE_THRESHOLD
            interval  = cfg.SMTP_POLL_ACTIVE_SECS if is_active else cfg.SMTP_POLL_INACTIVE_SECS

            if (now - last_poll) < interval:
                continue  # not time yet

            await publish(
                cfg.TOPIC_SMTP_RAW,
                {"account_id": account_id, "email_address": email},
                partition_key=acct.get("user_id", account_id),
            )
            await self._set_last_poll(account_id, now)

    async def _load_smtp_accounts(self) -> list[dict]:
        try:
            from models.email_account import EmailAccount, EmailProvider
            from models.conversations import EmailConversation
            from sqlalchemy import select, func
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        EmailAccount.id, EmailAccount.user_id, EmailAccount.email_address,
                        func.max(EmailConversation.last_message_at).label("last_msg"),
                    )
                    .outerjoin(EmailConversation, EmailConversation.email_account_id == EmailAccount.id)
                    .where(
                        EmailAccount.provider.in_([EmailProvider.SMTP, EmailProvider.YAHOO, EmailProvider.ZOHO]),
                        EmailAccount.is_active == True,
                    )
                    .group_by(EmailAccount.id, EmailAccount.user_id, EmailAccount.email_address)
                )
                return [
                    {"id": str(r[0]), "user_id": str(r[1]), "email_address": r[2],
                     "last_message_at_ts": r[3].timestamp() if r[3] else 0}
                    for r in result.all()
                ]
        except Exception as e:
            logger.error("Failed to load SMTP accounts: %s", e)
            return []

    async def _get_last_poll(self, account_id: str) -> float:
        try:
            redis = await get_redis()
            val = await redis.get(f"es:smtp:poll:{account_id}")
            return float(val) if val else 0.0
        except Exception:
            return 0.0

    async def _set_last_poll(self, account_id: str, ts: float) -> None:
        try:
            redis = await get_redis()
            await redis.setex(f"es:smtp:poll:{account_id}", 3600, str(ts))
        except Exception:
            pass
