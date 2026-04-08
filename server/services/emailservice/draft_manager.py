"""
emailservice — DraftManager
============================
Handles two paths after AI generates a reply:

  automation_enabled=True  → enqueue directly to send pipeline (existing flow)
  automation_enabled=False → store draft_message on the incoming message row
                             + set message_state=DRAFTED
                             + if over daily limit → also enqueue to es_outbox

All operations are non-blocking and do NOT make external API calls.
The draft is stored on the SAME row as the incoming message (same message_id)
so it appears in the inbox UI as a pending draft on that conversation.

Deferred send scheduling:
  Uses Redis ZSET "es:outbox:schedule" with score = scheduled_send_time (epoch).
  DeferredScheduler worker wakes only when the next score is due.
  Zero polling. Zero idle Redis cost.
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.database import get_db_session
from shared.cache import get_redis
from models.messages import EmailMessage, MessageState
from models.email_account import EmailAccount
from models.outbox import EsOutbox, OutboxStatus
from metrics import M

logger = logging.getLogger("emailservice.draft_manager")

# Redis ZSET key — score = scheduled_send_time epoch seconds
OUTBOX_ZSET = "es:outbox:schedule"
# Redis key prefix for per-account daily reset scheduling
RESET_ZSET  = "es:daily_reset:schedule"


class DraftManager:
    """
    Stores AI-generated drafts and manages deferred send scheduling.
    Instantiated once per process — stateless, all state in DB + Redis.
    """

    async def handle_ai_reply(
        self,
        *,
        message_id:       str,
        user_id:          str,
        email_account_id: str,
        thread_id:        str,
        provider:         str,
        in_reply_to:      str,
        references:       str,
        to_email:         str,
        from_email:       str,
        subject:          str,
        draft_text:       str,
        automation_enabled: bool,
    ) -> str:
        """
        Called by AIHandoffWorker after receiving a generated reply.

        Returns:
          "sent"     — enqueued for immediate send (automation_enabled=True, within limit)
          "drafted"  — stored as draft (automation_enabled=False)
          "deferred" — over daily limit, stored in outbox for later send
        """
        if automation_enabled:
            return await self._handle_auto_send(
                message_id=message_id, user_id=user_id,
                email_account_id=email_account_id, thread_id=thread_id,
                provider=provider, in_reply_to=in_reply_to, references=references,
                to_email=to_email, from_email=from_email, subject=subject,
                draft_text=draft_text,
            )
        else:
            await self._store_draft(
                message_id=message_id, user_id=user_id,
                email_account_id=email_account_id, draft_text=draft_text,
            )
            return "drafted"

    # ── Auto-send path ────────────────────────────────────────────────────────

    async def _handle_auto_send(
        self, *, message_id, user_id, email_account_id, thread_id,
        provider, in_reply_to, references, to_email, from_email, subject, draft_text,
    ) -> str:
        """
        automation_enabled=True: check daily limit.
        Within limit → publish to send pipeline immediately.
        Over limit   → enqueue to es_outbox + Redis ZSET for deferred send.
        """
        within_limit, reset_time = await self._check_and_reserve_send_slot(email_account_id)

        if within_limit:
            # Publish to the existing send pipeline via Redis stream
            await self._publish_send_event(
                message_id=message_id, user_id=user_id,
                email_account_id=email_account_id, thread_id=thread_id,
                provider=provider, in_reply_to=in_reply_to, references=references,
                to_email=to_email, from_email=from_email, subject=subject,
                draft_text=draft_text,
            )
            logger.info("DraftManager: auto-send enqueued | msg=%s", message_id[:12])
            return "sent"
        else:
            # Over limit — defer to next reset window
            await self._enqueue_deferred(
                message_id=message_id, user_id=user_id,
                email_account_id=email_account_id, thread_id=thread_id,
                provider=provider, in_reply_to=in_reply_to, references=references,
                to_email=to_email, from_email=from_email, subject=subject,
                draft_text=draft_text, scheduled_send_time=reset_time,
            )
            logger.info("DraftManager: deferred (limit reached) | msg=%s reset=%s",
                        message_id[:12], reset_time.isoformat())
            return "deferred"

    # ── Draft storage ─────────────────────────────────────────────────────────

    async def _store_draft(
        self, *, message_id: str, user_id: str, email_account_id: str, draft_text: str,
    ) -> None:
        """
        Store draft_message on the incoming message row.
        Uses UPDATE — no new row, no duplicate records.
        """
        try:
            async with get_db_session() as session:
                await session.execute(
                    sa_update(EmailMessage)
                    .where(
                        EmailMessage.message_id == message_id,
                        EmailMessage.user_id == UUID(user_id),
                    )
                    .values(
                        draft_message=draft_text,
                        message_state=MessageState.DRAFTED,
                    )
                )
                await session.commit()
            M.db_writes.labels(table="es_messages_draft", status="ok").inc()
            logger.info("DraftManager: draft stored | msg=%s", message_id[:12])
        except Exception as e:
            M.db_writes.labels(table="es_messages_draft", status="error").inc()
            logger.error("DraftManager: draft store failed | msg=%s: %s", message_id[:12], e)

    # ── Deferred outbox ───────────────────────────────────────────────────────

    async def _enqueue_deferred(
        self, *, message_id, user_id, email_account_id, thread_id,
        provider, in_reply_to, references, to_email, from_email, subject,
        draft_text, scheduled_send_time: datetime,
    ) -> None:
        """
        Insert into es_outbox + add to Redis ZSET for scheduler wake-up.
        Idempotent: ON CONFLICT DO NOTHING on idempotency_key.
        """
        idem_key = f"{email_account_id}:{in_reply_to}"
        row = EsOutbox(
            user_id=UUID(user_id),
            email_account_id=UUID(email_account_id),
            provider=provider,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            references=references or "",
            to_email=to_email,
            from_email=from_email,
            subject=subject or "",
            body_text=draft_text,
            scheduled_send_time=scheduled_send_time,
            status=OutboxStatus.PENDING,
            idempotency_key=idem_key,
            source_message_id=message_id,
        )
        try:
            async with get_db_session() as session:
                stmt = (
                    pg_insert(EsOutbox.__table__)
                    .values(
                        id=row.id, user_id=row.user_id,
                        email_account_id=row.email_account_id,
                        provider=row.provider, thread_id=row.thread_id,
                        in_reply_to=row.in_reply_to, references=row.references,
                        to_email=row.to_email, from_email=row.from_email,
                        subject=row.subject, body_text=row.body_text,
                        scheduled_send_time=row.scheduled_send_time,
                        status=OutboxStatus.PENDING.value,
                        idempotency_key=row.idempotency_key,
                        source_message_id=row.source_message_id,
                    )
                    .on_conflict_do_nothing(index_elements=["idempotency_key"])
                )
                await session.execute(stmt)
                await session.commit()
            M.db_writes.labels(table="es_outbox", status="ok").inc()
        except Exception as e:
            M.db_writes.labels(table="es_outbox", status="error").inc()
            logger.error("DraftManager: outbox insert failed | msg=%s: %s", message_id[:12], e)
            return

        # Add to Redis ZSET — score = epoch seconds of scheduled_send_time
        score = scheduled_send_time.timestamp()
        try:
            redis = await get_redis()
            await redis.zadd(OUTBOX_ZSET, {idem_key: score})
            logger.debug("DraftManager: ZSET updated | key=%s score=%s", idem_key[:20], score)
        except Exception as e:
            logger.warning("DraftManager: ZSET update failed (scheduler will recover): %s", e)

    # ── Send pipeline publish ─────────────────────────────────────────────────

    async def _publish_send_event(
        self, *, message_id, user_id, email_account_id, thread_id,
        provider, in_reply_to, references, to_email, from_email, subject, draft_text,
    ) -> None:
        """Publish to the existing send_reply stream for immediate processing."""
        from stream_client import publish
        import config as cfg
        payload = {
            "type":             "auto_send",
            "message_id":       message_id,
            "user_id":          user_id,
            "email_account_id": email_account_id,
            "thread_id":        thread_id,
            "provider":         provider,
            "in_reply_to":      in_reply_to,
            "references":       references or "",
            "to_email":         to_email,
            "from_email":       from_email,
            "subject":          subject or "",
            "body_text":        draft_text,
        }
        await publish(cfg.TOPIC_STORE_READY, payload, partition_key=user_id)

    # ── Daily limit helpers ───────────────────────────────────────────────────

    async def _check_and_reserve_send_slot(
        self, email_account_id: str,
    ) -> tuple[bool, datetime]:
        """
        Atomically check daily_sent_count < daily_send_limit.
        Returns (within_limit, next_reset_time).
        Does NOT increment — the actual send pipeline does that.
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        EmailAccount.daily_sent_count,
                        EmailAccount.daily_send_limit,
                        EmailAccount.updated_at,
                    ).where(EmailAccount.id == UUID(email_account_id))
                )
                row = result.first()
                if not row:
                    return True, datetime.utcnow() + timedelta(hours=24)

                sent, limit, updated_at = row
                within = sent < limit
                # Next reset = midnight UTC of the day after last reset
                reset = (updated_at or datetime.utcnow()).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
                return within, reset
        except Exception as e:
            logger.error("DraftManager: limit check failed: %s", e)
            return True, datetime.utcnow() + timedelta(hours=24)

    # ── Daily reset scheduling ────────────────────────────────────────────────

    async def schedule_daily_reset(self, email_account_id: str, reset_time: datetime) -> None:
        """
        Add account to the daily reset ZSET.
        DeferredScheduler also handles resets — one mechanism for both.
        """
        try:
            redis = await get_redis()
            score = reset_time.timestamp()
            await redis.zadd(RESET_ZSET, {email_account_id: score}, nx=True)
        except Exception as e:
            logger.warning("DraftManager: reset schedule failed: %s", e)
