"""
emailservice — Storage Worker
===============================
Consumes from store_ready, writes to es_messages + es_conversations.
Direct DB insert — no write buffer delay for reliability.
"""
from __future__ import annotations
import asyncio, logging, time
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert

import config as cfg
from workers.base_worker import BaseWorker
from kafka_client import publish_batch
from shared.database import get_db_session
from models.messages import EmailMessage, MessageStatus
from models.conversations import EmailConversation
from metrics import M

logger = logging.getLogger("emailservice.storage")


class StorageWorker(BaseWorker):
    topics   = [cfg.TOPIC_STORE_READY]
    group_id = cfg.CG_STORAGE

    def _provider_label(self) -> str:
        return "db"

    async def process_batch(self, records: list[dict]) -> None:
        if not records:
            return

        # 1. Build and insert message rows
        rows = self._build_message_rows(records)
        logger.info("Storage: received=%d valid_rows=%d", len(records), len(rows))

        if not rows:
            logger.warning("Storage: 0 valid rows — dumping records for debug:")
            for rec in records:
                logger.warning("  msg_id=%s user_id=%s account_id=%s direction=%s",
                               rec.get("message_id", "?"),
                               rec.get("user_id", "?"),
                               rec.get("email_account_id", "?"),
                               rec.get("direction", "?"))
            return

        inserted = await self._insert_messages(rows)
        logger.info("Storage: inserted %d/%d rows into es_messages", inserted, len(rows))

        # 2. Upsert conversations (best-effort, non-blocking)
        asyncio.create_task(self._upsert_conversations(records))

        # 3. Forward to AI pipeline (incoming only)
        ai_events = [
            (
                {
                    "user_id":    rec.get("user_id", ""),
                    "message_id": rec.get("message_id", ""),
                    "thread_id":  rec.get("thread_id", ""),
                    "provider":   rec.get("provider", ""),
                    "_priority":  rec.get("_priority", cfg.PRIORITY_MEDIUM),
                },
                rec.get("user_id", ""),
            )
            for rec in records
            if rec.get("direction") == "incoming"
        ]
        if ai_events:
            try:
                await publish_batch(cfg.TOPIC_AI_EVENTS, ai_events)
                logger.info("Storage: forwarded %d events to ai_events", len(ai_events))
            except Exception as e:
                logger.error("ai_events publish failed: %s", e)

    async def _insert_messages(self, rows: list[dict]) -> int:
        """Bulk INSERT with ON CONFLICT DO NOTHING for idempotency."""
        if not rows:
            return 0
        try:
            async with get_db_session() as session:
                stmt = (
                    pg_insert(EmailMessage.__table__)
                    .values(rows)
                    .on_conflict_do_nothing(index_elements=["user_id", "message_id"])
                )
                result = await session.execute(stmt)
                await session.commit()
                inserted = result.rowcount if result.rowcount >= 0 else len(rows)
                M.db_writes.labels(table="es_messages", status="ok").inc(inserted)
                return inserted
        except Exception as e:
            logger.error("Message insert failed: %s", e, exc_info=True)
            M.db_writes.labels(table="es_messages", status="error").inc(len(rows))
            return 0

    def _build_message_rows(self, records: list[dict]) -> list[dict]:
        rows = []
        for rec in records:
            msg_id     = rec.get("message_id", "").strip()
            user_id    = rec.get("user_id", "").strip()
            account_id = rec.get("email_account_id", "").strip()

            if not msg_id:
                logger.warning("Skipping record: missing message_id")
                continue
            if not user_id:
                logger.warning("Skipping record: missing user_id | msg=%s", msg_id)
                continue
            if not account_id:
                logger.warning("Skipping record: missing email_account_id | msg=%s", msg_id)
                continue

            try:
                rows.append({
                    "message_id":       msg_id,
                    "thread_id":        rec.get("thread_id") or msg_id,
                    "user_id":          UUID(user_id),
                    "email_account_id": UUID(account_id),
                    "provider":         rec.get("provider", ""),
                    "from_email":       rec.get("from_email", ""),
                    "to_emails":        rec.get("to_emails") or [],
                    "cc_emails":        rec.get("cc_emails") or [],
                    "subject":          rec.get("subject") or "",
                    "content":          rec.get("content") or "(no content)",
                    "timestamp":        _parse_ts(rec.get("timestamp")),
                    "direction":        rec.get("direction", "incoming"),
                    "status":           MessageStatus.RECEIVED.value,
                    "is_read":          False,
                    "has_attachments":  bool(rec.get("has_attachments", False)),
                    "metadata":         rec.get("metadata") or {},
                })
            except Exception as e:
                logger.error("Row build error | msg=%s: %s", msg_id, e, exc_info=True)
        return rows

    async def _upsert_conversations(self, records: list[dict]) -> None:
        """Upsert conversation metadata. Runs as a background task."""
        # Deduplicate by thread — keep latest message per thread
        threads: dict[tuple, dict] = {}
        for rec in records:
            key = (rec.get("user_id", ""), rec.get("thread_id") or rec.get("message_id", ""))
            existing = threads.get(key)
            if not existing or _parse_ts(rec.get("timestamp")) >= _parse_ts(existing.get("timestamp")):
                threads[key] = rec

        rows = []
        for (user_id, thread_id), rec in threads.items():
            try:
                rows.append({
                    "thread_id":        thread_id,
                    "user_id":          UUID(user_id),
                    "email_account_id": UUID(rec["email_account_id"]),
                    "provider":         rec.get("provider", ""),
                    "subject":          rec.get("subject") or "",
                    "participants":     rec.get("participants") or [],
                    "message_count":    1,
                    "last_message_id":  rec.get("message_id"),
                    "last_message_at":  _parse_ts(rec.get("timestamp")),
                    "is_read":          False,
                    "status":           "active",
                })
            except Exception as e:
                logger.error("Conv row error | thread=%s: %s", thread_id[:16], e)

        if not rows:
            return

        try:
            async with get_db_session() as session:
                stmt = (
                    pg_insert(EmailConversation.__table__)
                    .values(rows)
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
                await session.execute(stmt)
                await session.commit()
                M.db_writes.labels(table="es_conversations", status="ok").inc(len(rows))
        except Exception as e:
            logger.error("Conversation upsert failed: %s", e, exc_info=True)
            M.db_writes.labels(table="es_conversations", status="error").inc(len(rows))


def _parse_ts(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=None) if ts.tzinfo else ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.utcnow()
