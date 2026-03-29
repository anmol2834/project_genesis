"""
Email Event Contract
Normalized event structure for email ingestion pipeline.
Supports Gmail, Outlook, and SMTP providers.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Literal
from datetime import datetime
from uuid import UUID


class EmailEventMessage(BaseModel):
    """
    Individual message within a conversation.
    Used in last_24h_messages JSONB field.
    """
    message_id: str = Field(..., description="Unique message identifier from provider")
    from_email: EmailStr = Field(..., alias="from", description="Sender email address")
    to_emails: List[EmailStr] = Field(..., alias="to", description="Recipient email addresses")
    cc_emails: Optional[List[EmailStr]] = Field(default=None, description="CC recipients")
    bcc_emails: Optional[List[EmailStr]] = Field(default=None, description="BCC recipients")
    content: str = Field(..., description="Clean message content (no HTML)")
    timestamp: datetime = Field(..., description="Message timestamp")
    direction: Literal["incoming", "outgoing"] = Field(..., description="Message direction")
    
    class Config:
        populate_by_name = True


class EmailIngestEvent(BaseModel):
    """
    Normalized email event for ingestion pipeline.
    Produced by adapters, consumed by Celery workers.
    """
    # Identity
    user_id: UUID = Field(..., description="User who owns this email account")
    email_account_id: UUID = Field(..., description="Email account this message belongs to")
    provider: Literal["gmail", "outlook", "smtp"] = Field(..., description="Email provider")
    
    # Thread & Message IDs
    thread_id: str = Field(..., description="Conversation thread identifier")
    message_id: str = Field(..., description="Unique message identifier")
    
    # Email metadata
    from_email: EmailStr = Field(..., description="Sender email address")
    to_emails: List[EmailStr] = Field(..., description="Recipient email addresses")
    cc_emails: Optional[List[EmailStr]] = Field(default=None, description="CC recipients")
    bcc_emails: Optional[List[EmailStr]] = Field(default=None, description="BCC recipients")
    subject: Optional[str] = Field(None, description="Email subject line")
    
    # Message content
    content: str = Field(..., description="Clean message content (HTML stripped)")
    
    # Timing
    timestamp: datetime = Field(..., description="Message timestamp")
    
    # Direction
    direction: Literal["incoming", "outgoing"] = Field(..., description="Message direction")
    
    # Optional metadata
    labels: Optional[List[str]] = Field(default=None, description="Provider-specific labels")
    is_read: bool = Field(default=False, description="Read status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "d9004cda-3246-4f56-bb6b-48c4fa33cba4",
                "email_account_id": "40b7e7b3-fcd6-4510-967a-bfe5d97e7371",
                "provider": "gmail",
                "thread_id": "18d4f2a3b5c6e7f8",
                "message_id": "18d4f2a3b5c6e7f8-msg1",
                "from_email": "customer@example.com",
                "to_emails": ["support@mycompany.com"],
                "cc_emails": None,
                "bcc_emails": None,
                "subject": "Question about your product",
                "content": "Hi, I have a question about pricing...",
                "timestamp": "2026-03-28T18:30:00Z",
                "direction": "incoming",
                "labels": ["INBOX", "UNREAD"],
                "is_read": False
            }
        }


class WebSocketEmailEvent(BaseModel):
    """
    Real-time event sent to frontend via WebSocket.
    Minimal payload for instant inbox updates.
    """
    event_type: Literal["new_message", "message_read", "conversation_archived"] = Field(
        ..., description="Type of event"
    )
    thread_id: str = Field(..., description="Conversation thread ID")
    message_preview: str = Field(..., description="First 100 chars of message")
    from_email: EmailStr = Field(..., description="Sender email")
    timestamp: datetime = Field(..., description="Message timestamp")
    is_read: bool = Field(default=False, description="Read status")
    priority_score: Optional[float] = Field(None, description="AI priority score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "new_message",
                "thread_id": "18d4f2a3b5c6e7f8",
                "message_preview": "Hi, I have a question about pricing...",
                "from_email": "customer@example.com",
                "timestamp": "2026-03-28T18:30:00Z",
                "is_read": False,
                "priority_score": 0.85
            }
        }
