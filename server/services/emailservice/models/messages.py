"""
emailservice — EmailMessage (NEW normalized messages table)

Design principles:
  - Append-only: no row rewrites, ever
  - One row per message (not per conversation)
  - Indexed for fast per-user, per-thread, per-direction queries
  - NO JSONB message arrays (that was the old system's bottleneck)
  - DB-level unique constraint on (user_id, message_id) for dedup safety net
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


class EmailMessage(Base):
    """
    Core messages table — append-only, one row per message.
    Replaces the JSONB last_24h_messages array in the old system.
    """
    __tablename__ = "es_messages"

    # ── Identity ──────────────────────────────────────────────────────────────
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id       = Column(String(512), nullable=False)   # provider message ID
    thread_id        = Column(String(512), nullable=True)    # provider thread/conversation ID

    # ── Multi-tenant ──────────────────────────────────────────────────────────
    user_id          = Column(UUID(as_uuid=True), nullable=False)
    email_account_id = Column(UUID(as_uuid=True), nullable=False)
    provider         = Column(String(50), nullable=False)    # gmail | outlook | smtp

    # ── Headers ───────────────────────────────────────────────────────────────
    from_email       = Column(Text, nullable=False)
    to_emails        = Column(JSONB, nullable=False, default=list)
    cc_emails        = Column(JSONB, nullable=True,  default=list)
    subject          = Column(Text, nullable=True)

    # ── Body ──────────────────────────────────────────────────────────────────
    content          = Column(Text, nullable=True)       # cleaned plain-text
    # content_html removed — HTML is not stored (bandwidth + storage waste)

    # ── Metadata ──────────────────────────────────────────────────────────────
    timestamp        = Column(DateTime, nullable=False)  # email send/receive time (UTC)
    direction        = Column(SAEnum(MessageDirection), nullable=False)
    status           = Column(SAEnum(MessageStatus), default=MessageStatus.RECEIVED, nullable=False)
    is_read          = Column(Boolean, default=False, nullable=False)
    has_attachments  = Column(Boolean, default=False, nullable=False)

    # ── Flexible metadata (headers, label_ids, etc.) ──────────────────────────
    msg_metadata     = Column("metadata", JSONB, nullable=True, default=dict)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at       = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        # Primary dedup safety net — DB rejects duplicate (user, message)
        UniqueConstraint("user_id", "message_id", name="uq_es_messages_user_message"),

        # Fast inbox queries: user → thread → time
        Index("ix_es_messages_thread",     "user_id", "thread_id", "timestamp"),
        # Fast unread count
        Index("ix_es_messages_unread",     "user_id", "is_read", "timestamp"),
        # Direction filter (incoming only for AI)
        Index("ix_es_messages_direction",  "user_id", "direction", "timestamp"),
        # Account-level queries
        Index("ix_es_messages_account",    "email_account_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<EmailMessage {self.message_id[:12]}... from={self.from_email}>"
