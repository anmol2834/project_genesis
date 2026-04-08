"""
emailservice — es_outbox (Deferred Send Queue)

Stores outgoing messages that could not be sent immediately due to daily
send limits. The DeferredScheduler worker drains this table using a Redis
ZSET (score = scheduled_send_time epoch) — zero polling, wakes only when
the next send window arrives.

Lifecycle:
  PENDING  → scheduler picks it up at scheduled_send_time
  SENDING  → in-flight (prevents double-send on restart)
  SENT     → delivered, row kept for 7 days then pruned
  FAILED   → exhausted retries, needs manual review
"""
from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime, Float,
    Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import enum

from shared.database.postgres import Base


class OutboxStatus(str, enum.Enum):
    PENDING = "pending"
    SENDING = "sending"   # claimed by scheduler, in-flight
    SENT    = "sent"
    FAILED  = "failed"


class EsOutbox(Base):
    """
    Deferred outbox — one row per pending outgoing message.
    Keyed by (user_id, idempotency_key) for strict dedup.
    """
    __tablename__ = "es_outbox"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Ownership ─────────────────────────────────────────────────────────────
    user_id          = Column(UUID(as_uuid=True), nullable=False)
    email_account_id = Column(UUID(as_uuid=True), nullable=False)

    # ── Thread context (needed to send in correct thread) ─────────────────────
    provider         = Column(String(50), nullable=False)
    thread_id        = Column(String(512), nullable=False)
    in_reply_to      = Column(String(512), nullable=False)   # Message-ID header
    references       = Column(String(1024), nullable=True)
    to_email         = Column(Text, nullable=False)
    from_email       = Column(Text, nullable=False)
    subject          = Column(Text, nullable=True)

    # ── Content ───────────────────────────────────────────────────────────────
    body_text        = Column(Text, nullable=False)

    # ── Scheduling ────────────────────────────────────────────────────────────
    scheduled_send_time = Column(DateTime, nullable=False)   # UTC
    status           = Column(
        SAEnum(OutboxStatus, name="outboxstatusenum", create_type=True),
        default=OutboxStatus.PENDING, nullable=False,
    )
    retry_count      = Column(Integer, default=0, nullable=False)
    last_error       = Column(Text, nullable=True)

    # ── Idempotency ───────────────────────────────────────────────────────────
    # Prevents duplicate sends on retry. Format: "{email_account_id}:{in_reply_to}"
    idempotency_key  = Column(String(512), nullable=False, unique=True)

    # ── Source message (for status update after send) ─────────────────────────
    # The incoming message_id whose draft_message this outbox row represents.
    source_message_id = Column(String(512), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at       = Column(DateTime, nullable=False, server_default=func.now())
    sent_at          = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_es_outbox_schedule",  "status", "scheduled_send_time"),
        Index("ix_es_outbox_user",      "user_id", "status"),
        Index("ix_es_outbox_account",   "email_account_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<EsOutbox {self.id} status={self.status} to={self.to_email}>"
