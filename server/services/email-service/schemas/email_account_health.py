"""
Email Account Health Schemas
Pydantic models for health metrics response.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class EmailAccountHealthResponse(BaseModel):
    id: UUID
    email_account_id: UUID
    emails_sent: int
    emails_received: int
    bounce_rate: float
    reply_rate: float
    open_rate: float
    spam_rate: float
    click_rate: float
    health_score: float
    last_checked_at: Optional[datetime]
    updated_at: datetime

    class Config:
        from_attributes = True
