"""
Email Sync Log Schemas
Pydantic models for sync log response.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

from models.email_sync_log import SyncEventStatus


class EmailSyncLogResponse(BaseModel):
    id: UUID
    email_account_id: UUID
    status: SyncEventStatus
    message: Optional[str]
    emails_synced: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
