"""
emailservice — Filter + Dedup Worker
======================================
Consumes from fetch_results, filters/deduplicates, publishes to store_ready.
"""
from __future__ import annotations
import logging

import config as cfg
from workers.base_worker import BaseWorker
from kafka_client import publish_batch
from email_filter import should_filter
from dedup import get_dedup
from idempotency import get_idempotency_cache
from user_buffer import score_priority
from metrics import M

logger = logging.getLogger("emailservice.filter_dedup")


class FilterDedupWorker(BaseWorker):
    topics   = [cfg.TOPIC_FETCH_RESULTS]
    group_id = cfg.CG_FILTER_DEDUP

    def _provider_label(self) -> str:
        return "all"

    async def process_batch(self, records: list[dict]) -> None:
        dedup    = get_dedup()
        idem     = get_idempotency_cache()
        to_store: list[tuple[dict, str]] = []
        filtered = deduped = 0

        for rec in records:
            msg_id     = rec.get("message_id", "")
            provider   = rec.get("provider", "")
            subject    = rec.get("subject", "")
            from_email = rec.get("from_email", "")

            # 1. Idempotency (in-process LRU — resets on restart, that's fine)
            if idem.check_and_mark(provider, msg_id):
                deduped += 1
                continue

            # 2. Email filter (only bounces/noreply/OTP)
            if should_filter(subject, from_email):
                filtered += 1
                M.messages_filtered.labels(reason="filter").inc()
                logger.info("Filtered | subject='%s' from=%s", subject[:60], from_email)
                continue

            # 3. Bloom dedup
            if dedup.is_duplicate(msg_id):
                deduped += 1
                M.messages_deduped.labels(layer="bloom").inc()
                continue
            dedup.mark_seen(msg_id)

            # 4. Enrich
            rec = _detect_direction(rec)
            rec = _enrich_participants(rec)
            if "_priority" not in rec:
                rec["_priority"] = score_priority(rec)
            rec["_schema_version"] = 2

            to_store.append((rec, rec.get("user_id", "")))

        logger.info("FilterDedup: in=%d → pass=%d filtered=%d deduped=%d",
                    len(records), len(to_store), filtered, deduped)

        if to_store:
            await publish_batch(cfg.TOPIC_STORE_READY, to_store)
            logger.info("FilterDedup: published %d records to store_ready", len(to_store))


def _detect_direction(rec: dict) -> dict:
    from_email    = (rec.get("from_email") or "").lower()
    account_email = (rec.get("email_address") or "").lower()
    rec["direction"] = (
        "outgoing"
        if from_email and account_email and from_email == account_email
        else "incoming"
    )
    return rec


def _enrich_participants(rec: dict) -> dict:
    participants = set()
    if rec.get("from_email"):
        participants.add(rec["from_email"].lower())
    for e in (rec.get("to_emails") or []):
        participants.add(e.lower())
    for e in (rec.get("cc_emails") or []):
        participants.add(e.lower())
    rec["participants"] = list(participants)
    return rec
