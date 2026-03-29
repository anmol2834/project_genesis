"""
Event Router
Routes normalized email events to appropriate queues based on priority and provider.
"""

from typing import Dict, Any, Optional
from enum import Enum

from shared.logger import get_logger
from normalizer.event_schema import NormalizedEmailEvent

logger = get_logger(__name__)


class EventPriority(int, Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class EventRouter:
    """
    Routes email events to appropriate queues.
    Determines priority and routing strategy.
    """
    
    # Keywords that indicate high priority
    HIGH_PRIORITY_KEYWORDS = [
        "urgent", "asap", "important", "critical", "emergency",
        "immediate", "priority", "time-sensitive"
    ]
    
    # VIP domains (can be configured per user)
    VIP_DOMAINS = [
        "ceo", "founder", "director", "vp", "president"
    ]
    
    def route(
        self,
        event: NormalizedEmailEvent
    ) -> Dict[str, Any]:
        """
        Determine routing for an email event.
        
        Args:
            event: Normalized email event
            
        Returns:
            Routing configuration with queue, priority, and metadata
        """
        # Determine priority
        priority = self._calculate_priority(event)
        
        # Determine queue (currently all go to same queue, but can be extended)
        queue_name = self._select_queue(event, priority)
        
        # Build routing config
        routing_config = {
            "queue": queue_name,
            "priority": priority.value,
            "routing_key": self._get_routing_key(event),
            "metadata": {
                "provider": event.provider,
                "direction": event.direction,
                "has_attachments": event.has_attachments,
                "user_id": event.user_id
            }
        }
        
        logger.debug(
            f"Routed event {event.message_id}: "
            f"queue={queue_name}, priority={priority.name}"
        )
        
        return routing_config
    
    def _calculate_priority(self, event: NormalizedEmailEvent) -> EventPriority:
        """
        Calculate event priority based on content and metadata.
        
        Priority factors:
        - Subject keywords
        - Sender importance
        - Direction (incoming usually higher priority)
        - Attachments
        """
        priority_score = EventPriority.NORMAL.value
        
        # Check subject for high-priority keywords
        subject_lower = event.subject.lower()
        if any(keyword in subject_lower for keyword in self.HIGH_PRIORITY_KEYWORDS):
            priority_score += 3
            logger.debug(f"High priority keyword found in subject: {event.subject}")
        
        # Check sender domain for VIP indicators
        from_email_lower = event.from_email.lower()
        if any(vip in from_email_lower for vip in self.VIP_DOMAINS):
            priority_score += 2
            logger.debug(f"VIP sender detected: {event.from_email}")
        
        # Incoming emails slightly higher priority than outgoing
        if event.direction == "incoming":
            priority_score += 1
        
        # Emails with attachments might be more important
        if event.has_attachments:
            priority_score += 1
        
        # Map score to priority enum
        if priority_score >= 10:
            return EventPriority.CRITICAL
        elif priority_score >= 8:
            return EventPriority.HIGH
        elif priority_score >= 5:
            return EventPriority.NORMAL
        else:
            return EventPriority.LOW
    
    def _select_queue(
        self,
        event: NormalizedEmailEvent,
        priority: EventPriority
    ) -> str:
        """
        Select appropriate queue for the event.
        
        Currently all events go to the same queue, but this can be extended
        to route to different queues based on:
        - Provider (gmail_queue, outlook_queue, smtp_queue)
        - Priority (high_priority_queue, normal_queue)
        - User tier (premium_queue, standard_queue)
        """
        from email_queue.config.celery_config import EMAIL_EVENTS_QUEUE
        
        # Future: Implement queue selection logic
        # if priority == EventPriority.CRITICAL:
        #     return "email_critical_queue"
        # elif event.provider == "gmail":
        #     return "email_gmail_queue"
        
        return EMAIL_EVENTS_QUEUE
    
    def _get_routing_key(self, event: NormalizedEmailEvent) -> str:
        """
        Get routing key for the event.
        
        Routing key format: email.{provider}.{direction}
        """
        return f"email.{event.provider}.{event.direction}"
    
    def should_skip(self, event: NormalizedEmailEvent) -> bool:
        """
        Determine if event should be skipped (not queued).
        
        Currently returns False (queue all events), but can be extended
        to skip certain events based on business logic.
        """
        # Future: Implement skip logic
        # - Skip auto-replies
        # - Skip out-of-office messages
        # - Skip certain senders
        
        return False
