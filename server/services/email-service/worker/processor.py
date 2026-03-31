"""
Event Processor
Core processing logic for email events from email_queue.
Orchestrates: validation → fetch → update JSON → write DB → trigger WebSocket → trigger AI
"""

from typing import Dict, Any, Optional
from datetime import datetime

import httpx

from shared.logger import get_logger
from shared.config import get_config
from worker.json_manager import JSONConversationManager
from database.repository import EmailConversationRepository

logger = get_logger(__name__)
_config = get_config()


class EventProcessor:
    """
    Processes email events from email_queue.
    
    Flow:
    1. Validate event payload
    2. Fetch existing conversation (if any)
    3. Update JSON with 24h logic
    4. Write to database (upsert)
    5. Trigger WebSocket notification
    """
    
    def __init__(self):
        self.json_manager = JSONConversationManager()
        self.repository = EmailConversationRepository()
    
    async def process_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Process a single email event.
        
        Args:
            event_data: Normalized email event from queue
            
        Returns:
            True if processed successfully, False otherwise
        """
        try:
            # Step 1: Validate event
            if not self._validate_event(event_data):
                logger.error(f"Invalid event data: {event_data}")
                return False
            
            user_id = event_data["user_id"]
            thread_id = event_data.get("thread_id") or event_data["message_id"]
            message_id = event_data["message_id"]

            logger.debug(
                f"[PROCESSOR] Processing: user={user_id} "
                f"thread={thread_id} message={message_id} "
                f"subject='{event_data.get('subject', '')}'"
            )
            
            # Step 2: Check for duplicate message_id
            existing_by_message = await self.repository.get_conversation_by_message_id(
                user_id, message_id
            )
            
            if existing_by_message:
                logger.debug(f"Duplicate message_id {message_id}, skipping")
                return True  # Not an error, just already processed
            
            # Step 3: Fetch existing conversation by thread_id
            existing_conversation = await self.repository.get_conversation_by_thread(
                user_id, thread_id
            )
            
            # Step 4: Create new message object
            new_message = self.json_manager.create_message_object(
                message_id=message_id,
                from_email=event_data["from_email"],
                to_emails=event_data.get("to_emails", []),
                content=event_data["content"],
                timestamp=self._parse_timestamp(event_data["timestamp"]),
                direction=event_data["direction"],
                subject=event_data.get("subject"),
                cc_emails=event_data.get("cc_emails"),
                has_attachments=event_data.get("has_attachments", False)
            )
            
            # Step 5: Update message list with 24h logic
            existing_messages = []
            if existing_conversation:
                existing_messages = existing_conversation.last_24h_messages or []
            
            updated_messages = self.json_manager.update_messages(
                existing_messages,
                new_message,
                message_id=message_id
            )
            
            # Step 6: Upsert to database
            conversation = await self.repository.upsert_conversation(
                user_id=user_id,
                email_account_id=event_data["email_account_id"],
                provider=event_data["provider"],
                thread_id=thread_id,
                message_id=message_id,
                from_email=event_data["from_email"],
                to_emails=event_data.get("to_emails", []),
                cc_emails=event_data.get("cc_emails"),
                bcc_emails=event_data.get("bcc_emails"),
                subject=event_data.get("subject"),
                last_24h_messages=updated_messages,
                last_message_at=self._parse_timestamp(event_data["timestamp"]),
                direction=event_data["direction"]
            )
            
            if not conversation:
                logger.error(f"[PROCESSOR] ✗ DB upsert failed for thread={thread_id}")
                return False

            logger.debug(
                f"[PROCESSOR] ✓ SAVED: thread={thread_id} "
                f"messages_in_window={len(updated_messages)}"
            )

            # Step 7: Trigger WebSocket notification (stub — no-op)
            await self._trigger_websocket(conversation, new_message)

            # Step 8: Trigger automation-service AI pipeline (fire-and-forget)
            # Only trigger for incoming messages — don't process our own outgoing replies
            if event_data.get("direction") == "incoming":
                await self._trigger_automation(
                    conversation_id=str(conversation.id),
                    trace_id=event_data.get("trace_id", ""),
                )

            return True
            
        except Exception as e:
            logger.error(f"Failed to process event: {e}", exc_info=True)
            return False
    
    def _validate_event(self, event_data: Dict[str, Any]) -> bool:
        """Validate event has required fields."""
        required_fields = [
            "user_id",
            "email_account_id",
            "provider",
            "message_id",
            "from_email",
            "content",
            "timestamp",
            "direction"
        ]
        
        for field in required_fields:
            if field not in event_data:
                logger.error(f"Event missing required field: {field}")
                return False
        
        return True
    
    def _parse_timestamp(self, timestamp: Any) -> datetime:
        """
        Parse timestamp from various formats.
        ALWAYS returns naive UTC datetime — DB column is TIMESTAMP WITHOUT TIME ZONE.
        asyncpg rejects timezone-aware datetimes for naive columns.
        """
        from datetime import timezone

        def _strip_tz(dt: datetime) -> datetime:
            """Convert any datetime to naive UTC."""
            if dt.tzinfo is not None:
                # Convert to UTC then strip tzinfo
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        if isinstance(timestamp, datetime):
            return _strip_tz(timestamp)

        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return _strip_tz(dt)
            except ValueError:
                try:
                    return datetime.fromisoformat(timestamp)  # already naive
                except ValueError:
                    logger.error(f"Failed to parse timestamp: {timestamp}")
                    return datetime.utcnow()

        return datetime.utcnow()
    
    async def _trigger_websocket(self, conversation, new_message: dict):
        """Stub — real-time push not implemented yet."""
        pass

    async def _trigger_automation(self, conversation_id: str, trace_id: str = "") -> None:
        """
        Notify automation-service to run the AI pipeline for this conversation.
        Fire-and-forget — never blocks or fails the email ingestion pipeline.

        Uses httpx async client with a short timeout so a slow automation-service
        never delays email processing.
        """
        automation_url = getattr(_config, "AUTOMATION_SERVICE_URL", "http://localhost:8009")
        endpoint = f"{automation_url}/ai/process"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    endpoint,
                    json={
                        "conversation_id": conversation_id,
                        "trace_id":        trace_id,
                    },
                )
                if resp.status_code == 200:
                    logger.info(
                        f"[PROCESSOR] ✓ Automation triggered: conv={conversation_id[:8]} "
                        f"status={resp.json().get('status', '?')}",
                    )
                else:
                    logger.warning(
                        f"[PROCESSOR] Automation returned {resp.status_code} for conv={conversation_id[:8]}"
                    )
        except httpx.TimeoutException:
            logger.warning(
                f"[PROCESSOR] Automation trigger timed out for conv={conversation_id[:8]} — continuing"
            )
        except Exception as exc:
            # Never let automation failure break email ingestion
            logger.error(
                f"[PROCESSOR] Automation trigger failed for conv={conversation_id[:8]}: {exc}"
            )
