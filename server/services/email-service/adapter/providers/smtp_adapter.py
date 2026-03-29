"""
SMTP Event Adapter
Parses SMTP/IMAP email payloads (already fetched by SMTPReceiver).
"""

from typing import Dict, Any
from datetime import datetime
from email.utils import parsedate_to_datetime
import re

from shared.logger import get_logger
from adapter.base_adapter import BaseAdapter

logger = get_logger(__name__)


class SMTPEventAdapter(BaseAdapter):
    """Adapter for SMTP/IMAP events."""
    
    async def parse(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SMTP event payload.
        
        SMTP receiver already extracts most fields, we just need to structure them.
        """
        self._validate_required_fields(
            payload,
            ["message_id", "subject", "from", "to"]
        )
        
        # Parse timestamp
        date_str = payload.get("date", "")
        try:
            if date_str:
                timestamp = parsedate_to_datetime(date_str)
            else:
                timestamp = datetime.utcnow()
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            timestamp = datetime.utcnow()
        
        # Parse recipients
        to_emails = self._parse_email_list(payload.get("to", ""))
        cc_emails = self._parse_email_list(payload.get("cc", ""))
        
        # Get content (SMTP receiver should provide this)
        content = payload.get("content", "")
        content_html = payload.get("content_html")
        
        # If no content, try to extract from body
        if not content and "body" in payload:
            content = payload["body"]
        
        return {
            "message_id": payload.get("message_id"),
            "thread_id": payload.get("thread_id"),  # SMTP may not have this
            "subject": payload.get("subject", "(No Subject)"),
            "from_email": self._parse_email(payload.get("from", "")),
            "to_emails": to_emails,
            "cc_emails": cc_emails,
            "content": content or "(No content)",
            "content_html": content_html,
            "timestamp": timestamp,
            "has_attachments": payload.get("has_attachments", False),
            "provider_data": {
                "headers": payload.get("headers", {})
            }
        }
    
    def _parse_email(self, email_str: str) -> str:
        """Extract email address from 'Name <email>' format."""
        if not email_str:
            return ""
        
        match = re.search(r'<([^>]+)>', email_str)
        if match:
            return match.group(1)
        
        # Check if it's already just an email
        if '@' in email_str:
            return email_str.strip()
        
        return email_str.strip()
    
    def _parse_email_list(self, email_str: str) -> list:
        """Parse comma-separated email list."""
        if not email_str:
            return []
        
        emails = []
        for part in email_str.split(','):
            email = self._parse_email(part.strip())
            if email and '@' in email:
                emails.append(email)
        
        return emails
