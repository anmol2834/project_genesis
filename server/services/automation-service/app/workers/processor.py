"""
Workers - Message Processor
============================
Validates and transforms queue messages into execution events.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from app.models.events import AutomationEvent
from app.models.validation import SchemaValidator
from app.core.exceptions import ValidationError
from app.observability import get_logger

logger = get_logger(__name__)


class MessageProcessor:
    """
    Message validation and transformation.
    Converts raw queue messages into validated AutomationEvent objects.
    """
    
    def __init__(self):
        self.validator = SchemaValidator()
    
    async def process(self, raw_message: Dict[str, Any]) -> Optional[AutomationEvent]:
        """
        Process raw message into AutomationEvent (async — may fetch content from DB).
        Returns None if message is invalid.
        """
        try:
            self._validate_required_fields(raw_message)
            event = self._transform_to_event(raw_message)

            # automation_events stream only carries metadata (no email body).
            # Fetch content from DB when empty so the AI pipeline has real text.
            if not event.content:
                event = await self._enrich_content(event)

            self.validator.validate_event_schema(event.model_dump())
            self.validator.validate_tenant_isolation(event, event.user_id)
            self.validator.validate_trace_context(event)
            return event
            
        except ValidationError as e:
            logger.warning(
                "Message validation failed: %s",
                e.message,
                message_id=raw_message.get("message_id", "unknown"),
                details=e.details
            )
            return None
        
        except Exception as e:
            logger.error(
                "Message processing error: %s",
                e,
                message_id=raw_message.get("message_id", "unknown")
            )
            return None

    async def _enrich_content(self, event: AutomationEvent) -> AutomationEvent:
        """
        Fetch email content + subject from DB when the stream payload is empty.
        Retries up to 3 times with 500ms back-off to handle the race condition
        where emailservice writes to Redis stream before committing to Postgres.
        """
        import asyncio as _asyncio
        max_attempts = 3
        delay_s = 0.5
        for attempt in range(1, max_attempts + 1):
            try:
                from shared.database import get_db_session
                from sqlalchemy import text
                async with get_db_session() as session:
                    result = await session.execute(
                        text(
                            "SELECT content, subject FROM es_messages "
                            "WHERE message_id = :mid AND user_id = :uid "
                            "LIMIT 1"
                        ),
                        {"mid": event.message_id, "uid": event.user_id},
                    )
                    row = result.first()
                    if row:
                        content, subject = row
                        if content:  # only accept non-empty content
                            data = event.model_dump()
                            data["content"] = content
                            if not data.get("subject") and subject:
                                data["subject"] = subject
                            return AutomationEvent(**data)
                    # Row exists but content still empty (race) — retry
                    if attempt < max_attempts:
                        logger.debug(
                            "Content enrichment attempt %d/%d: content empty for msg=%s, retrying in %.1fs",
                            attempt, max_attempts, event.message_id[:12], delay_s,
                        )
                        await _asyncio.sleep(delay_s)
                        delay_s *= 2  # exponential back-off
            except Exception as e:
                logger.warning(
                    "Content enrichment attempt %d/%d failed for msg=%s: %s",
                    attempt, max_attempts, event.message_id[:12], e,
                )
                if attempt < max_attempts:
                    await _asyncio.sleep(delay_s)
                    delay_s *= 2
        return event
    
    def _validate_required_fields(self, message: Dict[str, Any]) -> None:
        """Validate required message fields"""
        if not message.get("conversation_id") and message.get("thread_id"):
            message["conversation_id"] = message["thread_id"]

        required = ["user_id", "message_id", "conversation_id", "thread_id"]
        missing = [field for field in required if not message.get(field)]
        
        if missing:
            raise ValidationError(
                f"Missing required fields: {', '.join(missing)}",
                details={"missing_fields": missing}
            )
    
    def _transform_to_event(self, message: Dict[str, Any]) -> AutomationEvent:
        """Transform raw message to AutomationEvent"""
        import uuid
        
        trace_id = message.get("trace_id") or str(uuid.uuid4())
        
        return AutomationEvent(
            event_id=str(uuid.uuid4()),
            event_type="automation.message.received",
            trace_id=trace_id,
            correlation_id=message.get("correlation_id", trace_id),
            user_id=message["user_id"],
            message_id=message["message_id"],
            conversation_id=message["conversation_id"],
            thread_id=message["thread_id"],
            content=message.get("content") or "",
            subject=message.get("subject", ""),
            from_email=message.get("from_email", ""),
            automation_enabled=message.get("automation_enabled", True),
            priority=message.get("_priority", 5),
            history=message.get("history", []),
            timestamp=datetime.utcnow(),
            source_service="emailservice",
            metadata={
                "provider": message.get("provider", "unknown"),
                "retry_count": message.get("_retry_count", 0)
            }
        )
    
    def should_skip(self, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Check if message should be skipped.
        Returns (should_skip, reason).
        """
        if not message.get("automation_enabled", True):
            return True, "automation_disabled"
        
        if not message.get("user_id"):
            return True, "missing_user_id"
        
        retry_count = message.get("_retry_count", 0)
        if retry_count > 10:
            return True, f"retry_exhausted ({retry_count})"
        
        return False, None


__all__ = ["MessageProcessor"]
