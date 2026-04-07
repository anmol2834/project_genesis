"""
emailservice — Gmail Fetch Worker
====================================
Consumes from gmail_events stream (published by webhook handler).
Calls pipeline.process_gmail_event() for each event.

This is the ONLY consumer of gmail_events — the webhook handler
never calls pipeline directly. Strict event-driven decoupling.

SLA routing: events with priority < SLA_PRIORITY_THRESHOLD are
processed first (CRITICAL/HIGH before MEDIUM/LOW).
"""
from __future__ import annotations
import asyncio, base64, logging, re, time
from datetime import datetime

import config as cfg
from workers.base_worker import BaseWorker, TransientFailure
from pipeline import process_gmail_event
from idempotency import get_idempotency_cache
from metrics import M

logger = logging.getLogger("emailservice.gmail_fetch")


class GmailFetchWorker(BaseWorker):
    """
    Consumes gmail_events stream and processes each notification via pipeline.
    On transient failure: BaseWorker sends to DLQ for retry.
    """
    topics   = [cfg.TOPIC_GMAIL_RAW]
    group_id = cfg.CG_GMAIL_FETCH

    def _provider_label(self) -> str:
        return "gmail"

    async def process_batch(self, records: list[dict]) -> None:
        if not records:
            return

        # Process concurrently but bounded — respect rate limits
        sem = asyncio.Semaphore(cfg.WORKER_CONCURRENCY)
        tasks = [self._process_one(rec, sem) for rec in records]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate hard exceptions (bugs) from soft False returns (transient failures)
        hard_failures = [r for r in results if isinstance(r, Exception)]
        soft_failures = sum(1 for r in results if r is False)

        if hard_failures:
            # Unexpected exception — re-raise so BaseWorker can DLQ the batch
            raise hard_failures[0]

        if soft_failures:
            # Transient failures (API errors, token refresh, rate limits, etc.)
            # Already logged by process_gmail_event() with full context.
            # Use TransientFailure so BaseWorker logs at WARNING, not ERROR.
            raise TransientFailure(f"{soft_failures}/{len(records)} Gmail events need retry")

    async def _process_one(self, rec: dict, sem: asyncio.Semaphore) -> bool:
        async with sem:
            pubsub_id     = rec.get("pubsub_id", "")
            email_address = rec.get("email_address", "")
            history_id    = rec.get("history_id", "")
            event_id      = rec.get("event_id", f"gmail:{pubsub_id}")

            if not email_address or not history_id:
                logger.warning("GmailFetchWorker: skipping malformed record | event_id=%s", event_id)
                return True  # ACK bad records — don't block the stream

            success = await process_gmail_event(
                pubsub_id=pubsub_id,
                email_address=email_address,
                history_id=history_id,
                event_id=event_id,
            )
            if not success:
                logger.warning("GmailFetchWorker: process_gmail_event failed | email=%s event_id=%s",
                               email_address, event_id)
            return success


# ── Content helpers (used by history_recovery_worker) ────────────────────────

def _extract_content(payload: dict):
    """Extract plain text and HTML from Gmail message payload."""
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
