"""
emailservice — Automation Response Worker
==========================================
Consumes automation_responses stream from automation-service.
Dispatches email replies via Gmail/SMTP.

Architecture: BLPOP on automation_responses_notify (zero idle cost)
─────────────────────────────────────────────────────────────────────
automation-service does (atomically in one pipeline):
  1. XADD automation_responses  <response payload>
  2. LPUSH automation_responses_notify  "1"

This worker does:
  1. BLPOP automation_responses_notify  (blocks until a token arrives)
  2. XRANGE automation_responses "-" "+" COUNT 100  (drain available responses)
  3. Process each, XDEL each one
  4. Loop back to BLPOP — zero idle commands

Why BLPOP instead of XREAD BLOCK:
  XREAD BLOCK wakes every 8s even when the stream is empty (Upstash socket
  timeout forces a re-issue of the command). BLPOP on a dedicated notify list
  only wakes when automation-service explicitly pushes a token — true zero-idle
  behaviour. The 8s timeout on the BLPOP call is purely a keepalive to satisfy
  Upstash's socket read timeout; it produces no data transfer and is free.

Idle cost:   0 commands (server-side BLPOP block)
Active cost: 1 BLPOP + 1 XRANGE + N XDEL per response batch
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from uuid import UUID

import redis.asyncio as aioredis

import config as cfg
from metrics import M

logger = logging.getLogger("emailservice.automation_response")

TOPIC_AUTOMATION_RESPONSES = "automation_responses"
NOTIFY_LIST = "automation_responses_notify"

# BLPOP timeout — must be < Upstash socket read timeout (~10s)
_BLPOP_TIMEOUT_S = 8
# Dedicated connection socket timeout must exceed the BLPOP timeout
_SOCKET_READ_TIMEOUT_S = 15


async def _get_redis() -> aioredis.Redis:
    from redis_pool_manager import get_redis_managed
    return await get_redis_managed()


async def _make_blocking_redis() -> aioredis.Redis:
    """Dedicated Redis connection for BLPOP — never from the shared pool."""
    from shared.config import get_config
    url = get_config().REDIS_URL
    return aioredis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
        socket_timeout=_SOCKET_READ_TIMEOUT_S,
    )


class AutomationResponseWorker:
    """
    Notification-driven worker.
    Sleeps via BLPOP until automation-service pushes a response token.
    Zero idle Redis commands.
    """

    def __init__(self):
        self._running = False
        self._block_redis: aioredis.Redis | None = None

    async def start(self) -> None:
        self._running = True
        logger.info(
            "[AutomationResponseWorker] started (BLPOP notification-driven) | "
            "stream=%s notify=%s",
            TOPIC_AUTOMATION_RESPONSES, NOTIFY_LIST,
        )
        # Drain any startup backlog first, then enter the notification loop
        asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        if self._block_redis:
            try:
                await self._block_redis.aclose()
            except Exception:
                pass
            self._block_redis = None
        logger.info("[AutomationResponseWorker] stopped")

    async def _run(self) -> None:
        # Check for startup backlog with a single XLEN (1 command vs unconditional XRANGE)
        # Only drain if messages actually exist from a previous run.
        try:
            redis = await _get_redis()
            backlog = await redis.xlen(TOPIC_AUTOMATION_RESPONSES)
            if backlog:
                logger.info("[AutomationResponseWorker] startup backlog: %d responses", backlog)
                await self._drain_and_process()
        except Exception as e:
            logger.warning("[AutomationResponseWorker] startup backlog check failed: %s", e)

        while self._running:
            if self._block_redis is None:
                try:
                    self._block_redis = await _make_blocking_redis()
                except Exception as e:
                    logger.error("[AutomationResponseWorker] cannot connect: %s", e)
                    await asyncio.sleep(2)
                    continue

            try:
                # BLPOP blocks until automation-service pushes a notify token.
                # Returns None after _BLPOP_TIMEOUT_S (Upstash keepalive) — not an error.
                result = await self._block_redis.blpop(
                    [NOTIFY_LIST],
                    timeout=_BLPOP_TIMEOUT_S,
                )
                if not self._running:
                    break
                if result:
                    await self._drain_and_process()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "[AutomationResponseWorker] connection error (will reconnect): %s",
                    type(e).__name__,
                )
                try:
                    await self._block_redis.aclose()
                except Exception:
                    pass
                self._block_redis = None
                if self._running:
                    await asyncio.sleep(1)

    async def _drain_and_process(self) -> None:
        """XRANGE drain + process + XDEL in one pass."""
        try:
            redis = await _get_redis()
            messages = await redis.xrange(TOPIC_AUTOMATION_RESPONSES, "-", "+", count=100)
            if not messages:
                return

            ids_to_del = []
            for msg_id, fields in messages:
                ids_to_del.append(msg_id)
                try:
                    rec = json.loads(fields.get("data", "{}"))
                    await self._process_response(rec)
                except Exception as e:
                    logger.error("[AutomationResponseWorker] process error %s: %s",
                                 msg_id, e, exc_info=True)

            if ids_to_del:
                pipe = redis.pipeline(transaction=False)
                for mid in ids_to_del:
                    pipe.xdel(TOPIC_AUTOMATION_RESPONSES, mid)
                await pipe.execute(raise_on_error=False)
        except Exception as e:
            logger.error("[AutomationResponseWorker] drain error: %s", e)

    async def _process_response(self, response: Dict[str, Any]) -> None:
        action          = response.get("action", "escalate")
        conversation_id = response.get("conversation_id", "")
        message_id      = response.get("message_id", "")
        thread_id       = response.get("thread_id", "")
        user_id         = response.get("user_id", "")
        response_text   = response.get("response_text", "")
        confidence      = response.get("confidence", 0.0)
        send_email      = response.get("send_email", False)
        trace_id        = response.get("trace_id", "")

        if not message_id or not user_id:
            logger.warning("[AutomationResponseWorker] missing message_id/user_id — skipping")
            return

        try:
            redis = await _get_redis()
            dedup_key = f"es:resp:dedup:{message_id}"
            acquired = await redis.set(dedup_key, "1", nx=True, ex=3600)
            if not acquired:
                logger.debug("Response dedup: msg=%s already dispatched", message_id[:12])
                return
        except Exception as e:
            logger.warning("Dedup error for msg=%s: %s — proceeding", message_id[:12], e)

        logger.info("response_received | conv=%s action=%s confidence=%.2f send_email=%s",
                    conversation_id[:12] if conversation_id else "?",
                    action, confidence, send_email)

        if send_email and response_text:
            await self._dispatch_reply(
                message_id=message_id, thread_id=thread_id,
                conversation_id=conversation_id, user_id=user_id,
                response_text=response_text, trace_id=trace_id,
            )

        if action == "draft":
            await self._store_draft(message_id=message_id, user_id=user_id,
                                    response_text=response_text, confidence=confidence)
        elif action == "escalate":
            logger.info("escalation_noted | conv=%s reason=%s",
                        conversation_id[:12] if conversation_id else "?",
                        response.get("escalation_reason", "unknown"))

    async def _dispatch_reply(self, message_id: str, thread_id: str,
                               conversation_id: str, user_id: str,
                               response_text: str, trace_id: str) -> None:
        try:
            ctx = await self._resolve_send_context(
                message_id=message_id, thread_id=thread_id,
                conversation_id=conversation_id, user_id=user_id,
            )
            if not ctx:
                logger.error("Cannot dispatch reply — context not found | msg=%s",
                             message_id[:12])
                return

            from api.send_reply import _send_gmail, _send_smtp, _store_outgoing, SendReplyRequest
            from html_formatter import format_email_html
            from token_cache import get_account_snapshot, get_fresh_token

            snap = await get_account_snapshot(ctx["email_address"])
            if not snap:
                logger.error("Cannot dispatch reply — no account snap for %s",
                             ctx["email_address"])
                return

            subject = ctx["subject"]
            re_subject = (f"Re: {subject}"
                          if subject and not subject.lower().startswith("re:")
                          else subject)

            # Build the structured HTML version of the response
            response_html = format_email_html(
                plain_text=response_text,
                subject=re_subject or "",
            )

            req = SendReplyRequest(
                provider=ctx["provider"],
                email_account_id=ctx["email_account_id"],
                user_id=user_id,
                thread_id=thread_id or message_id,
                in_reply_to=message_id,
                references=thread_id or message_id,
                conversation_id=conversation_id or "",
                to=ctx["from_email"],
                from_email=ctx["email_address"],
                subject=re_subject,
                body_text=response_text,
                body_html=response_html,
            )

            try:
                fresh_token = await get_fresh_token(snap)
            except Exception:
                fresh_token = None

            provider_key = ctx["provider"].lower()
            provider_msg_id = None
            last_error = None

            for attempt in range(3):
                try:
                    if provider_key == "gmail":
                        provider_msg_id = await _send_gmail(
                            snap, req, ctx["email_address"], response_text, fresh_token, response_html)
                    else:
                        provider_msg_id = await _send_smtp(
                            snap, req, ctx["email_address"], response_text, response_html)
                    break
                except Exception as e:
                    last_error = str(e)
                    fresh_token = None
                    if attempt < 2:
                        await asyncio.sleep([1, 2, 4][attempt])

            if provider_msg_id:
                await _store_outgoing(req, provider_msg_id, ctx["email_address"])
                logger.info("✅ Reply sent | msg=%s to=%s", message_id[:12], ctx["from_email"])
                M.messages_processed.labels(provider="automation_reply", status="ok").inc()
            else:
                logger.error("❌ Reply send failed | msg=%s error=%s", message_id[:12], last_error)
                M.messages_processed.labels(provider="automation_reply", status="error").inc()

        except Exception as e:
            logger.error("_dispatch_reply error for msg=%s: %s", message_id[:12], e, exc_info=True)

    async def _resolve_send_context(self, message_id: str, thread_id: str,
                                     conversation_id: str, user_id: str
                                     ) -> Optional[Dict[str, Any]]:
        try:
            from shared.database import get_db_session
            from models.messages import EmailMessage
            from models.email_account import EmailAccount
            from sqlalchemy import select

            async with get_db_session() as session:
                result = await session.execute(
                    select(EmailMessage.from_email, EmailMessage.subject,
                           EmailMessage.thread_id, EmailMessage.provider,
                           EmailMessage.email_account_id)
                    .where(EmailMessage.message_id == message_id,
                           EmailMessage.user_id == UUID(user_id))
                    .limit(1)
                )
                row = result.first()

                if not row:
                    t_id = thread_id or message_id
                    result2 = await session.execute(
                        select(EmailMessage.from_email, EmailMessage.subject,
                               EmailMessage.thread_id, EmailMessage.provider,
                               EmailMessage.email_account_id)
                        .where(EmailMessage.thread_id == t_id,
                               EmailMessage.user_id == UUID(user_id),
                               EmailMessage.direction == "incoming")
                        .order_by(EmailMessage.timestamp.desc()).limit(1)
                    )
                    row = result2.first()

                if not row:
                    return None

                from_email, subject, db_thread_id, provider, account_id = row

                acct = await session.execute(
                    select(EmailAccount.email_address)
                    .where(EmailAccount.id == account_id,
                           EmailAccount.is_active == True)
                    .limit(1)
                )
                acct_row = acct.first()
                email_address = acct_row[0] if acct_row else ""

                return {
                    "from_email":       from_email,
                    "subject":          subject or "",
                    "thread_id":        db_thread_id or thread_id or message_id,
                    "provider":         provider or "gmail",
                    "email_account_id": str(account_id),
                    "email_address":    email_address,
                }

        except Exception as e:
            logger.error("_resolve_send_context error for msg=%s: %s",
                         message_id[:12], e, exc_info=True)
            return None

    async def _store_draft(self, message_id: str, user_id: str,
                            response_text: str, confidence: float) -> None:
        try:
            from draft_manager import DraftManager
            from shared.database import get_db_session
            from models.messages import EmailMessage
            from sqlalchemy import select

            async with get_db_session() as session:
                result = await session.execute(
                    select(EmailMessage.email_account_id)
                    .where(EmailMessage.message_id == message_id,
                           EmailMessage.user_id == UUID(user_id))
                    .limit(1)
                )
                row = result.first()
                if not row:
                    logger.warning("Cannot store draft — message not found: %s", message_id[:12])
                    return
                account_id = str(row[0])

            await DraftManager()._store_draft(
                message_id=message_id, user_id=user_id,
                email_account_id=account_id, draft_text=response_text,
            )
            logger.info("Draft stored | msg=%s confidence=%.2f", message_id[:12], confidence)
        except Exception as e:
            logger.error("_store_draft error for msg=%s: %s", message_id[:12], e, exc_info=True)

    @property
    def stats(self) -> dict:
        return {"worker": "AutomationResponseWorker", "running": self._running}
