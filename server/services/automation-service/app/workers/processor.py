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
    
    def process(self, raw_message: Dict[str, Any]) -> Optional[AutomationEvent]:
        """
        Process raw message into AutomationEvent.
        Returns None if message is invalid.
        """
        try:
            # Validate required fields
            self._validate_required_fields(raw_message)
            
            # Transform to AutomationEvent
            event = self._transform_to_event(raw_message)
            
            # Validate event schema
            self.validator.validate_event_schema(event.model_dump())
            
            # Validate tenant isolation — pass event.user_id as the expected tenant
            self.validator.validate_tenant_isolation(event, event.user_id)
            
            # Validate trace context
            self.validator.validate_trace_context(event)
            
            return event
            
        except ValidationError as e:
            logger.warning(
                f"Message validation failed: {e.message}",
                message_id=raw_message.get("message_id", "unknown"),
                details=e.details
            )
            return None
        
        except Exception as e:
            logger.error(
                f"Message processing error: {e}",
                message_id=raw_message.get("message_id", "unknown")
            )
            return None
    
    def _validate_required_fields(self, message: Dict[str, Any]) -> None:
        """Validate required message fields"""
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
        
        # Generate trace_id if not present
        trace_id = message.get("trace_id") or str(uuid.uuid4())
        
        # Extract fields
        event = AutomationEvent(
            event_id=str(uuid.uuid4()),
            event_type="automation.message.received",
            trace_id=trace_id,
            correlation_id=message.get("correlation_id", trace_id),
            user_id=message["user_id"],
            message_id=message["message_id"],
            conversation_id=message["conversation_id"],
            thread_id=message["thread_id"],
            content=message.get("content", ""),
            subject=message.get("subject", ""),
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
        
        return event
    
    def should_skip(self, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Check if message should be skipped.
        Returns (should_skip, reason).
        """
        # Skip if automation disabled
        if not message.get("automation_enabled", True):
            return True, "automation_disabled"
        
        # Skip if missing user_id (tenant isolation required)
        if not message.get("user_id"):
            return True, "missing_user_id"
        
        # Skip if retry count exhausted (already handled by consumer)
        retry_count = message.get("_retry_count", 0)
        if retry_count > 10:  # Safety check
            return True, f"retry_exhausted ({retry_count})"
        
        return False, None


__all__ = ["MessageProcessor"]
