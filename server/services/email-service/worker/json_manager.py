"""
JSON Conversation Manager
Handles 24-hour sliding window message storage with enterprise-grade logic.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from shared.logger import get_logger

logger = get_logger(__name__)


class JSONConversationManager:
    """
    Manages conversation message history with 24-hour sliding window.
    
    Core Logic:
    1. Append new message
    2. Sort by timestamp
    3. Filter to last 24 hours
    4. Remove duplicates
    """
    
    @staticmethod
    def update_messages(
        existing_messages: List[Dict[str, Any]],
        new_message: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Update message list with new message and apply 24h window.
        
        Args:
            existing_messages: Current message list
            new_message: New message to add
            
        Returns:
            Updated message list (last 24h only)
        """
        try:
            # Ensure existing_messages is a list
            if not isinstance(existing_messages, list):
                existing_messages = []
            
            # Validate new message
            if not JSONConversationManager._validate_message(new_message):
                logger.error(f"Invalid message structure: {new_message}")
                return existing_messages
            
            # Step 1: Check for duplicate
            message_id = new_message.get("message_id")
            if JSONConversationManager._is_duplicate(existing_messages, message_id):
                logger.debug(f"Duplicate message {message_id}, skipping")
                return existing_messages
            
            # Step 2: Append new message
            messages = existing_messages.copy()
            messages.append(new_message)
            
            # Step 3: Sort by timestamp (ascending)
            messages = JSONConversationManager._sort_by_timestamp(messages)
            
            # Step 4: Apply 24-hour window filter
            messages = JSONConversationManager._apply_24h_filter(messages)
            
            logger.debug(
                f"Updated messages: {len(existing_messages)} → {len(messages)} "
                f"(added {new_message['message_id']})"
            )
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to update messages: {e}", exc_info=True)
            return existing_messages
    
    @staticmethod
    def _validate_message(message: Dict[str, Any]) -> bool:
        """Validate message structure."""
        required_fields = ["message_id", "timestamp", "content", "direction"]
        
        for field in required_fields:
            if field not in message:
                logger.error(f"Message missing required field: {field}")
                return False
        
        # Validate timestamp
        timestamp = message.get("timestamp")
        if not isinstance(timestamp, (str, datetime)):
            logger.error(f"Invalid timestamp type: {type(timestamp)}")
            return False
        
        # Validate direction
        direction = message.get("direction")
        if direction not in ["incoming", "outgoing"]:
            logger.error(f"Invalid direction: {direction}")
            return False
        
        return True
    
    @staticmethod
    def _is_duplicate(messages: List[Dict[str, Any]], message_id: str) -> bool:
        """Check if message_id already exists."""
        return any(msg.get("message_id") == message_id for msg in messages)
    
    @staticmethod
    def _sort_by_timestamp(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort messages by timestamp (ascending). Handles both aware and naive datetimes."""
        from datetime import timezone

        def get_timestamp(msg: Dict[str, Any]) -> datetime:
            ts = msg.get("timestamp")
            
            if isinstance(ts, datetime):
                # Normalise to UTC-aware for consistent comparison
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            elif isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    try:
                        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
                    except ValueError:
                        logger.error(f"Failed to parse timestamp for sort: {ts}")
                        return datetime.min.replace(tzinfo=timezone.utc)
            else:
                return datetime.min.replace(tzinfo=timezone.utc)
        
        try:
            return sorted(messages, key=get_timestamp)
        except Exception as e:
            logger.error(f"Failed to sort messages: {e}")
            return messages
    
    @staticmethod
    def _apply_24h_filter(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter messages to last 24 hours.
        
        This is the CORE sliding window logic.
        All timestamp comparisons are done in UTC with timezone-naive datetimes
        to avoid TypeError when mixing aware and naive datetimes.
        """
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=24)
            
            filtered = []
            
            for msg in messages:
                ts = msg.get("timestamp")
                
                # Parse timestamp to aware datetime
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        # Ensure aware — naive ISO strings (no tz suffix) get UTC
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except ValueError:
                        try:
                            ts = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
                        except ValueError:
                            logger.warning(f"Skipping message with invalid timestamp: {ts}")
                            continue
                elif isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                else:
                    logger.warning(f"Skipping message with non-datetime timestamp: {type(ts)}")
                    continue
                
                # Filter by 24h window
                if ts >= cutoff:
                    filtered.append(msg)
                else:
                    logger.debug(f"Filtered out message {msg.get('message_id')} (older than 24h)")
            
            logger.debug(f"24h filter: {len(messages)} → {len(filtered)} messages")
            
            return filtered
            
        except Exception as e:
            logger.error(f"Failed to apply 24h filter: {e}", exc_info=True)
            return messages
    
    @staticmethod
    def create_message_object(
        message_id: str,
        from_email: str,
        to_emails: List[str],
        content: str,
        timestamp: datetime,
        direction: str,
        subject: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        has_attachments: bool = False
    ) -> Dict[str, Any]:
        """
        Create a standardized message object for storage.
        
        This is the canonical message format for last_24h_messages JSONB field.
        """
        return {
            "message_id": message_id,
            "from": from_email,
            "to": to_emails or [],
            "cc": cc_emails or [],
            "subject": subject or "",
            "content": content,
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "direction": direction,
            "has_attachments": has_attachments
        }
    
    @staticmethod
    def get_message_count(messages: List[Dict[str, Any]]) -> int:
        """Get count of messages in list."""
        return len(messages) if isinstance(messages, list) else 0
    
    @staticmethod
    def get_latest_message(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get the most recent message."""
        if not messages or not isinstance(messages, list):
            return None
        
        # Messages should already be sorted, so return last
        return messages[-1] if messages else None
    
    @staticmethod
    def extract_conversation_participants(
        messages: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Extract all unique participants from conversation.
        
        Returns:
            {"from": [...], "to": [...], "cc": [...]}
        """
        from_emails = set()
        to_emails = set()
        cc_emails = set()
        
        for msg in messages:
            if "from" in msg:
                from_emails.add(msg["from"])
            
            if "to" in msg and isinstance(msg["to"], list):
                to_emails.update(msg["to"])
            
            if "cc" in msg and isinstance(msg["cc"], list):
                cc_emails.update(msg["cc"])
        
        return {
            "from": list(from_emails),
            "to": list(to_emails),
            "cc": list(cc_emails)
        }
