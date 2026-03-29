"""
Metadata Enricher
Enriches events with metadata like direction detection and timestamp normalization.
"""

from datetime import datetime, timezone
from typing import Dict, Any

from shared.logger import get_logger

logger = get_logger(__name__)


class MetadataEnricher:
    """Enriches events with additional metadata."""
    
    def normalize_timestamp(self, timestamp: datetime) -> datetime:
        """
        Normalize timestamp to UTC.
        
        Args:
            timestamp: Input timestamp
            
        Returns:
            UTC timestamp
        """
        if timestamp.tzinfo is None:
            # Assume UTC if no timezone
            return timestamp.replace(tzinfo=timezone.utc)
        
        # Convert to UTC
        return timestamp.astimezone(timezone.utc)
    
    def detect_direction(
        self,
        from_email: str,
        to_emails: list,
        account_email: str
    ) -> str:
        """
        Detect email direction (incoming or outgoing).
        
        Args:
            from_email: Sender email
            to_emails: Recipient emails
            account_email: The email account being monitored
            
        Returns:
            "incoming" or "outgoing"
        """
        # Normalize emails for comparison
        from_email_lower = from_email.lower().strip()
        account_email_lower = account_email.lower().strip()
        
        # If from_email matches account, it's outgoing
        if from_email_lower == account_email_lower:
            return "outgoing"
        
        # If account is in to_emails, it's incoming
        to_emails_lower = [e.lower().strip() for e in to_emails]
        if account_email_lower in to_emails_lower:
            return "incoming"
        
        # Default to incoming (most common case)
        return "incoming"
    
    def enrich(
        self,
        data: Dict[str, Any],
        account_email: str
    ) -> Dict[str, Any]:
        """
        Enrich event data with metadata.
        
        Args:
            data: Parsed event data
            account_email: Email account address
            
        Returns:
            Enriched data
        """
        # Normalize timestamp
        if "timestamp" in data and data["timestamp"]:
            data["timestamp"] = self.normalize_timestamp(data["timestamp"])
        else:
            data["timestamp"] = datetime.utcnow().replace(tzinfo=timezone.utc)
        
        # Detect direction
        data["direction"] = self.detect_direction(
            data.get("from_email", ""),
            data.get("to_emails", []),
            account_email
        )
        
        # Add processing timestamps
        data["received_at"] = datetime.utcnow().replace(tzinfo=timezone.utc)
        data["normalized_at"] = datetime.utcnow().replace(tzinfo=timezone.utc)
        
        return data
