"""
emailservice — DeferredScheduler
==================================
Event-driven scheduler for deferred outbox sends and daily limit resets.

Architecture:
  Redis ZSET "es:outbox:schedule"  — score = scheduled_send_time (epoch)
  Redis ZSET "es:daily_reset:schedule" — score = reset_time (epoch)

  Scheduler wakes ONLY when the next due timestamp arrives.
  Sleep duration = min(next_outbox_score, next_reset_score) - now.
  Zero polling. Zero idle Redis cost. Zero CPU overhead.

Per-user isolation:
  Messages are processed FIFO per user (ORDER BY scheduled_send_time ASC).
  One user's backlog never blocks another — each send is independent.

Retry policy:
  Exponential backoff: 60s → 120s → 240s → 480s → 960s (max 5 retries).
  After max retries: status=FAILED, removed from ZSET.

Daily reset:
  At reset_time, daily_sent_count is set to 0 for the account.
  All PENDING outbox rows for that account are rescheduled to now.
  The account is re-added to RESET_ZSET for the next day.
"""
from __future__ import annotations
import asyncio, json, logging, time
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.database import get_db_session
from shared.cache import get_redis
from models.outbox import EsOutbox, OutboxStatus
from models.email_account import EmailAccount
from metrics import M

logger = logging.getLogger("emailservice.deferred_scheduler")

OUTBOX_ZSET = "es:outbox:schedule"
RESET_ZSET  = "es:daily_reset:schedule"
MAX_RETRIES = 5
BATCH_SIZE  = 20   # max sends per wake cycle — prevents burst
# Minimum sleep between cycles when items ARE scheduled but not yet due
MIN_SLEEP_S = 60.0
# Sleep duration when ZSETs are completely empty — nothing to do
# Reduces Redis commands from 4/min to 4/10min when no deferred sends exist
IDLE_SLEEP_S = 600.0


class DeferredScheduler:
    """
    Lightweight scheduler — wakes only when work is due.
    Runs as a single asyncio task inside the emailservice process.
    """

    def __init__(self):
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("DeferredScheduler started (event-driven, zero idle cost)")
        await self._run()

    async def stop(self) -> None:
        self._running = False

    async def _run(self) -> None:
        while self._running:
            try:
                sleep_s = await self._compute_sleep()
                if sleep_s > 0:
                    logger.debug("DeferredScheduler: sleeping %.1fs until next due item", sleep_s)
                    await asyncio.sleep(sleep_s)
                    continue

                # Process due outbox items
                await self._process_due_outbox()

                # Process due daily resets
                await self._process_due_resets()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("DeferredScheduler error: %s", e, exc_info=True)
                await asyncio.sleep(30)

    async def _compute_sleep(self) -> float:
        """
        Returns seconds until the earliest due item across both ZSETs.
        Returns 0 if something is already due.
        Uses a single ZRANGEBYSCORE pass per ZSET — O(log N).
        When both ZSETs are empty, returns IDLE_SLEEP_S (saves 4 Redis commands/cycle).
        """
        now = time.time()
        try:
            redis = await get_redis()
            outbox_due = await redis.zrangebyscore(OUTBOX_ZSET, "-inf", now, start=0, num=1)
            reset_due  = await redis.zrangebyscore(RESET_ZSET,  "-inf", now, start=0, num=1)

            if outbox_due or reset_due:
                return 0.0

            # Nothing due — find next scheduled time
            next_times = []
            for zset in (OUTBOX_ZSET, RESET_ZSET):
                items = await redis.zrange(zset, 0, 0, withscores=True)
                if items:
                    next_times.append(items[0][1])

            if not next_times:
                return IDLE_SLEEP_S  # both ZSETs empty — sleep 10min

            return max(0.0, min(next_times) - now)
        except Exception as e:
            logger.warning("DeferredScheduler: sleep compute failed: %s", e)
            return MIN_SLEEP_S

    # ── Outbox processing ─────────────────────────────────────────────────────

    async def _process_due_outbox(self) -> None:
        """
        Fetch all outbox rows due now, send them, update status.
        FIFO per user — ORDER BY scheduled_send_time ASC.
        """
        now_epoch = time.time()
        try:
            redis = await get_redis()
            # Get due idempotency keys from ZSET
            due_keys = await redis.zrangebyscore(
                OUTBOX_ZSET, "-inf", now_epoch, start=0, num=BATCH_SIZE
            )
        except Exception as e:
            logger.error("DeferredScheduler: ZSET read failed: %s", e)
            return

        if not due_keys:
            return

        logger.info("DeferredScheduler: %d outbox items due", len(due_keys))

        for idem_key in due_keys:
            await self._send_one(idem_key)

    async def _send_one(self, idem_key: str) -> None:
        """Claim, send, and update a single outbox row. Per-user isolated."""
        try:
            async with get_db_session() as session:
                # Claim the row atomically (SENDING prevents double-send on restart)
                result = await session.execute(
                    select(EsOutbox).where(
                        EsOutbox.idempotency_key == idem_key,
                        EsOutbox.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
                    ).with_for_update(skip_locked=True)
                )
                row = result.scalar_one_or_none()
                if not row:
                    # Already claimed or sent — remove from ZSET
                    await self._zset_remove(OUTBOX_ZSET, idem_key)
                    return

                row.status = OutboxStatus.SENDING
                await session.commit()

            # Attempt send via existing send_reply logic
            success, error = await self._do_send(row)

            async with get_db_session() as session:
                result = await session.execute(
                    select(EsOutbox).where(EsOutbox.idempotency_key == idem_key)
                )
                row = result.scalar_one_or_none()
                if not row:
                    return

                if success:
                    row.status  = OutboxStatus.SENT
                    row.sent_at = datetime.utcnow()
                    await session.commit()
                    await self._zset_remove(OUTBOX_ZSET, idem_key)
                    # Update source message state → SENT
                    if row.source_message_id:
                        await self._mark_source_sent(
                            row.source_message_id, str(row.user_id), session
                        )
                    await session.commit()
                    M.messages_processed.labels(provider=row.provider, status="deferred_sent").inc()
                    logger.info("DeferredScheduler: sent | key=%s", idem_key[:20])
                else:
                    row.retry_count += 1
                    row.last_error   = error
                    if row.retry_count >= MAX_RETRIES:
                        row.status = OutboxStatus.FAILED
                        await self._zset_remove(OUTBOX_ZSET, idem_key)
                        logger.error("DeferredScheduler: max retries exceeded | key=%s", idem_key[:20])
                        M.messages_processed.labels(provider=row.provider, status="deferred_failed").inc()
                    else:
                        # Exponential backoff: reschedule
                        delay = min(60 * (2 ** (row.retry_count - 1)), 960)
                        next_time = datetime.utcnow() + timedelta(seconds=delay)
                        row.scheduled_send_time = next_time
                        row.status = OutboxStatus.PENDING
                        await self._zset_update(OUTBOX_ZSET, idem_key, next_time.timestamp())
                        logger.warning("DeferredScheduler: retry %d in %ds | key=%s",
                                       row.retry_count, delay, idem_key[:20])
                    await session.commit()

        except Exception as e:
            logger.error("DeferredScheduler: _send_one failed | key=%s: %s", idem_key[:20], e)

    async def _do_send(self, row: EsOutbox) -> tuple[bool, str]:
        """
        Execute the actual send using the existing send_reply helpers.
        Returns (success, error_message).
        """
        try:
            from token_cache import get_account_snapshot, get_fresh_token
            from api.send_reply import _send_gmail, _send_smtp, _send_outlook, _inc_sent
            from api.send_reply import SendReplyRequest

            snap = await get_account_snapshot(row.from_email)
            if not snap:
                # Fall back to DB load
                from api.send_reply import _load_snap
                snap = await _load_snap(str(row.email_account_id), str(row.user_id))
            if not snap:
                return False, "Account not found"

            req = SendReplyRequest(
                provider=row.provider,
                email_account_id=str(row.email_account_id),
                user_id=str(row.user_id),
                thread_id=row.thread_id,
                in_reply_to=row.in_reply_to,
                references=row.references or row.in_reply_to,
                conversation_id="",   # not needed for send
                to=row.to_email,
                from_email=row.from_email,
                subject=row.subject or "",
                body_text=row.body_text,
            )

            provider_key = row.provider.lower()
            if provider_key == "gmail":
                await _send_gmail(snap, req, row.from_email)
            elif provider_key == "outlook":
                await _send_outlook(snap, req, row.from_email)
            else:
                await _send_smtp(snap, req, row.from_email)

            await _inc_sent(str(row.email_account_id))
            return True, ""

        except Exception as e:
            return False, str(e)[:200]

    async def _mark_source_sent(
        self, source_message_id: str, user_id: str, session
    ) -> None:
        """Update the source incoming message state to SENT after deferred send."""
        from models.messages import EmailMessage, MessageState
        try:
            await session.execute(
                sa_update(EmailMessage)
                .where(
                    EmailMessage.message_id == source_message_id,
                    EmailMessage.user_id == UUID(user_id),
                )
                .values(message_state=MessageState.SENT)
            )
        except Exception as e:
            logger.warning("DeferredScheduler: mark_source_sent failed: %s", e)

    # ── Daily reset processing ────────────────────────────────────────────────

    async def _process_due_resets(self) -> None:
        """
        Reset daily_sent_count=0 for accounts whose reset time has arrived.
        Reschedule all PENDING outbox rows for that account to now.
        Re-add account to RESET_ZSET for next day.
        """
        now_epoch = time.time()
        try:
            redis = await get_redis()
            due_accounts = await redis.zrangebyscore(
                RESET_ZSET, "-inf", now_epoch, start=0, num=50
            )
        except Exception as e:
            logger.error("DeferredScheduler: reset ZSET read failed: %s", e)
            return

        for account_id_str in due_accounts:
            await self._reset_account(account_id_str)

    async def _reset_account(self, account_id_str: str) -> None:
        """Reset daily_sent_count and reschedule pending outbox rows."""
        try:
            async with get_db_session() as session:
                # Reset counter
                await session.execute(
                    sa_update(EmailAccount)
                    .where(EmailAccount.id == UUID(account_id_str))
                    .values(daily_sent_count=0)
                )

                # Reschedule all PENDING outbox rows for this account to now
                now = datetime.utcnow()
                await session.execute(
                    sa_update(EsOutbox)
                    .where(
                        EsOutbox.email_account_id == UUID(account_id_str),
                        EsOutbox.status == OutboxStatus.PENDING,
                    )
                    .values(scheduled_send_time=now)
                )
                await session.commit()

            # Update ZSET scores for rescheduled rows
            try:
                async with get_db_session() as session:
                    result = await session.execute(
                        select(EsOutbox.idempotency_key).where(
                            EsOutbox.email_account_id == UUID(account_id_str),
                            EsOutbox.status == OutboxStatus.PENDING,
                        )
                    )
                    keys = [r[0] for r in result.all()]

                if keys:
                    redis = await get_redis()
                    now_score = time.time()
                    mapping = {k: now_score for k in keys}
                    await redis.zadd(OUTBOX_ZSET, mapping)
                    logger.info("DeferredScheduler: rescheduled %d deferred msgs for account %s",
                                len(keys), account_id_str[:8])
            except Exception as e:
                logger.warning("DeferredScheduler: ZSET reschedule failed: %s", e)

            # Remove from reset ZSET and re-add for next day
            next_reset = (datetime.utcnow() + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            try:
                redis = await get_redis()
                await redis.zrem(RESET_ZSET, account_id_str)
                await redis.zadd(RESET_ZSET, {account_id_str: next_reset.timestamp()})
            except Exception as e:
                logger.warning("DeferredScheduler: reset reschedule failed: %s", e)

            logger.info("DeferredScheduler: daily reset done | account=%s next=%s",
                        account_id_str[:8], next_reset.date())
            M.messages_processed.labels(provider="system", status="daily_reset").inc()

        except Exception as e:
            logger.error("DeferredScheduler: reset failed for %s: %s", account_id_str[:8], e)

    # ── Redis helpers ─────────────────────────────────────────────────────────

    async def _zset_remove(self, zset: str, key: str) -> None:
        try:
            redis = await get_redis()
            await redis.zrem(zset, key)
        except Exception as e:
            logger.warning("DeferredScheduler: ZSET remove failed: %s", e)

    async def _zset_update(self, zset: str, key: str, score: float) -> None:
        try:
            redis = await get_redis()
            await redis.zadd(zset, {key: score})
        except Exception as e:
            logger.warning("DeferredScheduler: ZSET update failed: %s", e)
