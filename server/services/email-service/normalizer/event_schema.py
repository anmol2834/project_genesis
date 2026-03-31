"""
Normalized Email Event Schema
Universal event format used across the entire system.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class EmailDirection(str, Enum):
    """Email direction."""
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class EmailProvider(str, Enum):
    """Email provider."""
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SMTP = "smtp"


class NormalizedEmailEvent(BaseModel):
    """
    Universal normalized email event.
    This is the SINGLE SOURCE OF TRUTH for email events across the system.
    """
    
    # ── Identity ────────────────────────────────────────────────────────────
    user_id: str = Field(..., description="User ID who owns the email account")
    email_account_id: str = Field(..., description="Email account ID")
    
    # ── Provider ────────────────────────────────────────────────────────────
    provider: EmailProvider = Field(..., description="Email provider")
    
    # ── Message Identifiers ─────────────────────────────────────────────────
    message_id: str = Field(..., description="Unique message ID")
    thread_id: Optional[str] = Field(None, description="Thread/conversation ID")
    
    # ── Email Headers ───────────────────────────────────────────────────────
    subject: str = Field(..., description="Email subject")
    from_email: str = Field(..., description="Sender email address")
    to_emails: List[str] = Field(..., description="Recipient email addresses")
    cc_emails: Optional[List[str]] = Field(default_factory=list, description="CC recipients")
    bcc_emails: Optional[List[str]] = Field(default_factory=list, description="BCC recipients")
    
    # ── Content ─────────────────────────────────────────────────────────────
    content: str = Field(..., description="Email body content (cleaned, AI-ready)")
    content_html: Optional[str] = Field(None, description="Original HTML content")
    
    # ── Metadata ────────────────────────────────────────────────────────────
    timestamp: datetime = Field(..., description="Email timestamp (UTC)")
    direction: EmailDirection = Field(..., description="Email direction")
    
    # ── Attachments ─────────────────────────────────────────────────────────
    has_attachments: bool = Field(default=False, description="Whether email has attachments")
    attachment_count: int = Field(default=0, description="Number of attachments")
    
    # ── Provider-Specific ───────────────────────────────────────────────────
    provider_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific metadata"
    )
    
    # ── Processing Metadata ─────────────────────────────────────────────────
    received_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When event was received by our system"
    )
    normalized_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When event was normalized"
    )

    # ── Traceability ─────────────────────────────────────────────────────────
    trace_id: Optional[str] = Field(
        default=None,
        description="Cross-service trace ID for log correlation"
    )
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator('to_emails', 'cc_emails', 'bcc_emails', pre=True)
    def ensure_list(cls, v):
        """Ensure email lists are always lists."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v
    
    @validator('content')
    def validate_content(cls, v):
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("Email content cannot be empty")
        return v.strip()
    
    @validator('timestamp', 'received_at', 'normalized_at')
    def ensure_utc(cls, v):
        """Ensure all timestamps are UTC."""
        if v and v.tzinfo is None:
            return v.replace(tzinfo=None)
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.dict()
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return self.json()
