"""
emailservice — Outlook Fetch Worker
Consumes from: outlook_events
Produces to:   fetch_results

Fetches full message via Graph API, normalizes, publishes.
Token refresh happens here — never in webhook handler.
"""
from __future__ import annotations
import asyncio, logging
from datetime import datetime
from typing import Optional

import httpx

import config as cfg
from workers.base_worker import BaseWorker
from kafka_client import publish_batch
from token_cache import get_fresh_token
from shared.cache import get_redis
from shared.database import get_db_session

logger = logging.getLogger("emailservice.outlook_fetch")

_GRAPH_API = "https://graph.microsoft.com/v1.0"


class OutlookFetchWorker(BaseWorker):
    topics   = [cfg.TOPIC_OUTLOOK_RAW]
    group_id = cfg.CG_OUTLOOK_FETCH

    async def process_batch(self, records: list[dict]) -> None:
        sem = asyncio.Semaphore(cfg.WORKER_CONCURRENCY)
        tasks = [self._process_one(rec, sem) for rec in records]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_one(self, rec: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            sub_id    = rec.get("subscription_id", "")
            msg_id    = rec.get("message_id", "")

            if not msg_id:
                return

            # Resolve account from subscription_id
            snap = await self._resolve_account(sub_id)
            if not snap:
                logger.warning("Cannot resolve account for subscription %s", sub_id[:12])
                return

            # Dedup
            dedup_key = f"es:out:{snap['id']}:{msg_id}"
            try:
                redis = await get_redis()
                if not await redis.set(dedup_key, "1", nx=True, ex=86400):
                    return
            except Exception:
                pass

            token = await get_fresh_token(snap)

            # Fetch full message from Graph API
            msg = await self._fetch_message(token, msg_id)
            if not msg:
                return

            await publish_batch(
                cfg.TOPIC_FETCH_RESULTS,
                [(
                    {
                        "provider":         "outlook",
                        "email_address":    snap["email_address"],
                        "user_id":          snap["user_id"],
                        "email_account_id": snap["id"],
                        **msg,
                        "timestamp": msg["timestamp"].isoformat()
                            if isinstance(msg.get("timestamp"), datetime) else msg.get("timestamp", ""),
                    },
                    snap["user_id"],
                )],
            )

    async def _resolve_account(self, subscription_id: str) -> Optional[dict]:
        """Resolve account snapshot from Outlook subscription ID."""
        try:
            # Check Redis cache first
            redis = await get_redis()
            cached = await redis.get(f"es:sub:{subscription_id}")
            if cached:
                import json
                return json.loads(cached)
        except Exception:
            pass

        try:
            from models.email_account import EmailAccount
            from sqlalchemy import select
            import json

            async with get_db_session() as session:
                # Look up by client_state stored in Redis during subscription creation
                result = await session.execute(
                    select(EmailAccount).where(
                        EmailAccount.id.cast(str) == subscription_id,
                        EmailAccount.is_active == True,
                    ).limit(1)
                )
                acct = result.scalar_one_or_none()
                if not acct:
                    return None
                snap = {
                    "id": str(acct.id), "user_id": str(acct.user_id),
                    "email_address": acct.email_address, "provider": acct.provider.value,
                    "access_token": acct.access_token, "refresh_token": acct.refresh_token,
                    "token_expiry": acct.token_expiry.isoformat() if acct.token_expiry else None,
                }
                try:
                    redis = await get_redis()
                    await redis.setex(f"es:sub:{subscription_id}", 3600, json.dumps(snap))
                except Exception:
                    pass
                return snap
        except Exception as e:
            logger.error("Account resolution failed for sub %s: %s", subscription_id[:12], e)
            return None

    async def _fetch_message(self, token: str, message_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GRAPH_API}/me/messages/{message_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"$select": "id,subject,from,toRecipients,ccRecipients,body,receivedDateTime,hasAttachments,conversationId,internetMessageId"},
                )
        except Exception as e:
            logger.error("Graph message fetch failed %s: %s", message_id, e)
            return None

        if resp.status_code != 200:
            return None

        m = resp.json()
        from_addr = m.get("from", {}).get("emailAddress", {}).get("address", "")
        to_addrs  = [r["emailAddress"]["address"] for r in m.get("toRecipients", [])]
        cc_addrs  = [r["emailAddress"]["address"] for r in m.get("ccRecipients", [])]
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
            "from_email":      from_addr,
            "to_emails":       to_addrs,
            "cc_emails":       cc_addrs,
            "content":         body_content if body_type == "text" else _html_to_text(body_content),
            "timestamp":       ts,
            "has_attachments": m.get("hasAttachments", False),
        }


def _html_to_text(html: str) -> str:
    import re
    if not html:
        return ""
    html = re.sub(r'<[^>]+>', '', html)
    return re.sub(r'\s+', ' ', html).strip()
