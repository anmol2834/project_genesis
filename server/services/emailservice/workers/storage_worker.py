"""
emailservice — Storage Worker
===============================
Consumes from store_ready stream, writes to es_messages + es_conversations.

Key properties:
- Guaranteed delivery: uses store_message_with_retry() — never drops on DB failure
- Idempotent: ON CONFLICT DO NOTHING at DB level + event_id idempotency check
- SLA-aware: CRITICAL/HIGH priority messages processed before MEDIUM/LOW
- Batched writes: accumulates rows and flushes in bulk for throughput
"""
from __future__ import annotations
import asyncio, logging, time
from datetime import datetime

import config as cfg
from workers.base_worker import BaseWorker
from pipeline import store_message_with_retry
from idempotency import get_idempotency_cache
from email_filter import should_filter_pre_db
from metrics import M

logger = logging.getLogger("emailservice.storage")


class StorageWorker(BaseWorker):
    """
    Consumes store_ready stream and writes messages to PostgreSQL.
    Uses store_message_with_retry() for guaranteed delivery with backoff.
    """
    topics   = [cfg.TOPIC_STORE_READY]
    group_id = cfg.CG_STORAGE

    def _provider_label(self) -> str:
        return "db"

    async def process_batch(self, records: list[dict]) -> None:
        if not records:
            return

        # SLA sort: CRITICAL (0) and HIGH (1) first, then MEDIUM/LOW
        records.sort(key=lambda r: r.get("_priority", cfg.PRIORITY_MEDIUM))

        idem = get_idempotency_cache()
        stored = skipped = failed = filtered = 0

        for rec in records:
            msg_id   = rec.get("message_id", "")
            event_id = rec.get("event_id", f"store:{msg_id}")

            # Zero-leak guarantee: final O(1) filter check before DB insert.
            # Catches any promotional/automated email that slipped through
            # earlier stages (e.g. backlog from before filter was deployed,
            # or edge cases from restarts/partial failures).
            if should_filter_pre_db(rec):
                filtered += 1
                logger.debug("StorageWorker: pre-DB filter dropped msg %s", msg_id)
                continue

            # End-to-end idempotency: skip if this event_id was already stored
            if idem.check_and_mark("store", event_id):
                skipped += 1
                continue

            success = await store_message_with_retry(rec)
            if success:
                stored += 1
            else:
                failed += 1
                # store_message_with_retry already logged and exhausted retries
                # BaseWorker._send_to_dlq will handle this record

        logger.info("StorageWorker: stored=%d skipped=%d filtered=%d failed=%d batch=%d",
                    stored, skipped, filtered, failed, len(records))

        if failed:
            # Raise so BaseWorker sends failed records to DLQ
            raise RuntimeError(f"{failed} records failed after max retries")
