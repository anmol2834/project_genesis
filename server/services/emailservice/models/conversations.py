"""
emailservice — EmailConversation (NEW normalized conversations table)

Design principles:
  - One row per thread (upserted on each new message)
  - NO embedded message arrays — messages live in es_messages
  - AI context fetched dynamically: SELECT last N FROM es_messages WHERE thread_id=X
  - Append-only message table + lightweight conversation metadata = scalable
"""
from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, Float, Integer, Text,
    DateTime, Index, UniqueConstraint, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import enum

from shared.database.postgres import Base


class LeadStatus(str, enum.Enum):
    HOT  = "hot"
    WARM = "warm"
    COLD = "cold"


class EmailConversation(Base):
    """
    Conversation-level metadata.
    Message content lives in es_messages — never embedded here.
    """
    __tablename__ = "es_conversations"

    # ── Identity ──────────────────────────────────────────────────────────────
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id        = Column(String(512), nullable=False)
    user_id          = Column(UUID(as_uuid=True), nullable=False)
    email_account_id = Column(UUID(as_uuid=True), nullable=False)
    provider         = Column(String(50), nullable=False)

    # ── Thread metadata ───────────────────────────────────────────────────────
    subject          = Column(Text, nullable=True)
    participants     = Column(JSONB, nullable=True, default=list)  # all email addresses
    message_count    = Column(Integer, default=1, nullable=False)
    last_message_id  = Column(String(512), nullable=True)          # latest message_id
    last_message_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_read          = Column(Boolean, default=False, nullable=False)
    status           = Column(String(50), default="active", nullable=False)  # active|archived|snoozed

    # ── AI fields ─────────────────────────────────────────────────────────────
    summary          = Column(Text, nullable=True)          # AI-generated summary
    intent_type      = Column(String(100), nullable=True)   # support|sales|inquiry|complaint
    priority_score   = Column(Float, nullable=True)         # 0.0 – 1.0
    lead_status      = Column(SAEnum(LeadStatus), nullable=True)

    # ── Business fields ───────────────────────────────────────────────────────
    follow_up_required = Column(Boolean, default=False, nullable=False)
    last_follow_up_at  = Column(DateTime, nullable=True)
    tags               = Column(JSONB, nullable=True, default=list)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at       = Column(DateTime, nullable=False, server_default=func.now())
    updated_at       = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # One conversation per (user, thread)
        UniqueConstraint("user_id", "thread_id", name="uq_es_conversations_user_thread"),

        # Inbox listing: user → status → unread → recency
        Index("ix_es_conv_inbox",    "user_id", "status", "is_read", "last_message_at"),
        # AI priority queue
        Index("ix_es_conv_priority", "user_id", "priority_score", "last_message_at"),
        # Intent filter
        Index("ix_es_conv_intent",   "user_id", "intent_type", "status"),
        # Lead pipeline
        Index("ix_es_conv_lead",     "user_id", "lead_status", "last_message_at"),
        # Account-level
        Index("ix_es_conv_account",  "email_account_id", "last_message_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation thread={self.thread_id[:12]}... msgs={self.message_count}>"
