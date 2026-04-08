"""
emailservice — EmailMessage (normalized messages table)

Lifecycle fields added:
  - draft_message : AI-generated draft stored on the INCOMING message row
                    (same message_id, no new record). Shown in UI as pending draft.
  - message_state : Full lifecycle — RECEIVED → DRAFTED → QUEUED → SENT | FAILED
"""
from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, Text, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import enum

from shared.database.postgres import Base


class MessageDirection(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class MessageStatus(str, enum.Enum):
    RECEIVED  = "received"
    SENT      = "sent"
    FAILED    = "failed"
    QUEUED    = "queued"


class MessageState(str, enum.Enum):
    """Full lifecycle state — more granular than MessageStatus."""
    RECEIVED = "received"   # incoming message stored, no action yet
    DRAFTED  = "drafted"    # AI draft generated, awaiting user approval
    QUEUED   = "queued"     # approved / auto-send queued (deferred outbox)
    SENT     = "sent"       # successfully delivered
    FAILED   = "failed"     # delivery failed after retries


class EmailMessage(Base):
    """
    Core messages table — append-only, one row per message.
    draft_message is stored on the INCOMING row (same message_id).
    """
    __tablename__ = "es_messages"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id       = Column(String(512), nullable=False)
    thread_id        = Column(String(512), nullable=True)

    user_id          = Column(UUID(as_uuid=True), nullable=False)
    email_account_id = Column(UUID(as_uuid=True), nullable=False)
    provider         = Column(String(50), nullable=False)

    from_email       = Column(Text, nullable=False)
    to_emails        = Column(JSONB, nullable=False, default=list)
    cc_emails        = Column(JSONB, nullable=True,  default=list)
    subject          = Column(Text, nullable=True)

    content          = Column(Text, nullable=True)

    # ── Draft & lifecycle ─────────────────────────────────────────────────────
    # draft_message: AI-generated reply stored on the incoming message row.
    # Null until automation generates a draft. Cleared after send.
    draft_message    = Column(Text, nullable=True)

    # message_state: full lifecycle tracker (supersedes status for new messages)
    message_state    = Column(
        SAEnum(MessageState, name="messagestateenum", create_type=True),
        nullable=True,
        default=None,
    )

    timestamp        = Column(DateTime, nullable=False)
    direction        = Column(SAEnum(MessageDirection), nullable=False)
    status           = Column(SAEnum(MessageStatus), default=MessageStatus.RECEIVED, nullable=False)
    is_read          = Column(Boolean, default=False, nullable=False)
    has_attachments  = Column(Boolean, default=False, nullable=False)

    created_at       = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "message_id", name="uq_es_messages_user_message"),
        Index("ix_es_messages_thread",     "user_id", "thread_id", "timestamp"),
        Index("ix_es_messages_unread",     "user_id", "is_read", "timestamp"),
        Index("ix_es_messages_direction",  "user_id", "direction", "timestamp"),
        Index("ix_es_messages_account",    "email_account_id", "timestamp"),
        Index("ix_es_messages_draft",      "user_id", "message_state"),
        # ── Ephemeral retention indexes ───────────────────────────────────────
        # ix_es_messages_created_at  — used by pg_cron DELETE (WHERE created_at < cutoff)
        # ix_es_messages_user_recent — used by inbox/AI queries (WHERE user_id + created_at range)
        Index("ix_es_messages_created_at",  "created_at"),
        Index("ix_es_messages_user_recent", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EmailMessage {self.message_id[:12]}... state={self.message_state}>"
