"""
emailservice — Automation Response Worker
==========================================
Consumes responses from automation-service and dispatches emails.
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Dict, Any

import httpx
import config as cfg
from workers.base_worker import BaseWorker
from metrics import M, timer
from shared.database import get_postgres_pool

logger = logging.getLogger("emailservice.automation_response")

TOPIC_AUTOMATION_RESPONSES = "automation_responses"
CG_AUTOMATION_RESPONSE = "es-automation-response"


class AutomationResponseWorker(BaseWorker):
    """
    Consumes AI-generated responses from automation-service.
    Dispatches email replies based on action (send, draft, escalate).
    """
    
    topics = [TOPIC_AUTOMATION_RESPONSES]
    group_id = CG_AUTOMATION_RESPONSE
    
    def __init__(self):
        super().__init__()
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=30.0, write=10.0, pool=3.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=8),
        )
    
    async def stop(self) -> None:
        await self._http.aclose()
        await super().stop()
    
    def _provider_label(self) -> str:
        return "automation_response"
    
    async def process_batch(self, records: list[dict]) -> None:
        """Process batch of automation responses"""
        async with timer("automation_response"):
            for rec in records:
                try:
                    await self._process_response(rec)
                except Exception as e:
                    logger.error(f"Response processing error: {e}", exc_info=True)
    
    async def _process_response(self, response: Dict[str, Any]) -> None:
        """Process single automation response"""
        
        action = response.get("action", "escalate")
        conversation_id = response.get("conversation_id", "")
        message_id = response.get("message_id", "")
        user_id = response.get("user_id", "")
        response_text = response.get("response_text", "")
        confidence = response.get("confidence", 0.0)
        send_email = response.get("send_email", False)
        
        logger.info(
            f"Automation response received | conv={conversation_id[:12]} "
            f"action={action} confidence={confidence:.2f} send={send_email}"
        )
        
        if action == "send" and send_email:
            # Send email reply
            await self._send_email_reply(
                conversation_id=conversation_id,
                message_id=message_id,
                user_id=user_id,
                response_text=response_text,
                trace_id=response.get("trace_id", "")
            )
        
        elif action == "draft":
            # Save as draft for human review
            await self._save_draft(
                conversation_id=conversation_id,
                message_id=message_id,
                user_id=user_id,
                response_text=response_text,
                confidence=confidence
            )
        
        elif action == "escalate":
            # Create escalation ticket
            await self._create_escalation(
                conversation_id=conversation_id,
                message_id=message_id,
                user_id=user_id,
                reason=response.get("escalation_reason", "unknown"),
                priority=response.get("escalation_priority", "medium")
            )
        
        else:
            logger.warning(f"Unknown action: {action}")
    
    async def _send_email_reply(
        self,
        conversation_id: str,
        message_id: str,
        user_id: str,
        response_text: str,
        trace_id: str
    ) -> None:
        """Send email reply via email-service API"""
        
        try:
            # Get conversation details from database
            pool = get_postgres_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT c.thread_id, m.from_email, m.subject
                    FROM conversations c
                    JOIN messages m ON m.id = $1
                    WHERE c.id = $2 AND c.user_id = $3
                    """,
                    message_id,
                    conversation_id,
                    user_id
                )
            
            if not row:
                logger.error(f"Conversation not found: {conversation_id}")
                return
            
            thread_id = row['thread_id']
            to_email = row['from_email']
            subject = row['subject']
            
            # Call send reply endpoint
            payload = {
                "thread_id": thread_id,
                "to_email": to_email,
                "subject": f"Re: {subject}" if not subject.startswith("Re:") else subject,
                "body": response_text,
                "user_id": user_id,
                "trace_id": trace_id
            }
            
            resp = await self._http.post(
                f"{cfg.get_config().EMAIL_SERVICE_URL}/send-reply",
                json=payload
            )
            
            if resp.status_code == 200:
                logger.info(f"✅ Email sent successfully | conv={conversation_id[:12]} to={to_email}")
                M.increment("email_sent_success")
            else:
                logger.error(f"❌ Email send failed | status={resp.status_code}")
                M.increment("email_sent_failed")
        
        except Exception as e:
            logger.error(f"Email send error: {e}", exc_info=True)
            M.increment("email_sent_error")
    
    async def _save_draft(
        self,
        conversation_id: str,
        message_id: str,
        user_id: str,
        response_text: str,
        confidence: float
    ) -> None:
        """Save response as draft for human review"""
        
        try:
            pool = get_postgres_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO drafts (
                        conversation_id, message_id, user_id,
                        draft_text, confidence, status, created_at
                    ) VALUES ($1, $2, $3, $4, $5, 'pending', NOW())
                    ON CONFLICT (message_id) DO UPDATE SET
                        draft_text = EXCLUDED.draft_text,
                        confidence = EXCLUDED.confidence,
                        updated_at = NOW()
                    """,
                    conversation_id,
                    message_id,
                    user_id,
                    response_text,
                    confidence
                )
            
            logger.info(f"✅ Draft saved | conv={conversation_id[:12]} confidence={confidence:.2f}")
            M.increment("draft_saved")
        
        except Exception as e:
            logger.error(f"Draft save error: {e}", exc_info=True)
    
    async def _create_escalation(
        self,
        conversation_id: str,
        message_id: str,
        user_id: str,
        reason: str,
        priority: str
    ) -> None:
        """Create escalation ticket"""
        
        try:
            pool = get_postgres_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO escalations (
                        conversation_id, message_id, user_id,
                        reason, priority, status, created_at
                    ) VALUES ($1, $2, $3, $4, $5, 'pending', NOW())
                    ON CONFLICT (message_id) DO UPDATE SET
                        reason = EXCLUDED.reason,
                        priority = EXCLUDED.priority,
                        updated_at = NOW()
                    """,
                    conversation_id,
                    message_id,
                    user_id,
                    reason,
                    priority
                )
            
            logger.info(f"✅ Escalation created | conv={conversation_id[:12]} reason={reason} priority={priority}")
            M.increment("escalation_created")
        
        except Exception as e:
            logger.error(f"Escalation create error: {e}", exc_info=True)
