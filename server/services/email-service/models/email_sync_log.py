"""
EmailSyncLog Model - PostgreSQL
Append-only audit log for every sync attempt per email account.
Used for debugging, health monitoring, and user-facing sync history.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.dialects.postgresql import UUID
import enum

from shared.database.postgres import Base


class SyncEventStatus(str, enum.Enum):
    STARTED   = "started"
    SUCCESS   = "success"
    PARTIAL   = "partial"   # some emails synced, some failed
    FAILED    = "failed"
    SKIPPED   = "skipped"   # e.g. account paused


class EmailSyncLog(Base):
    __tablename__ = "email_sync_logs"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status  = Column(SAEnum(SyncEventStatus), nullable=False)
    message = Column(Text, nullable=True)          # human-readable detail / error
    emails_synced = Column(String(20), nullable=True)  # e.g. "42 new, 5 updated"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Efficient pagination: latest logs per account
        Index("ix_email_sync_logs_account_created", "email_account_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EmailSyncLog account={self.email_account_id} status={self.status}>"
