"""
EmailProviderSubscription Model - PostgreSQL
Tracks active subscriptions for real-time email monitoring across all providers.
Supports Gmail Pub/Sub, Outlook Graph Webhooks, and SMTP polling registrations.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Text, Enum as SAEnum, Index, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
import enum

from shared.database.postgres import Base


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    FAILED = "failed"
    PENDING = "pending"


class EmailProviderSubscription(Base):
    __tablename__ = "email_provider_subscriptions"

    # ── Identity ────────────────────────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    email_account_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # ── Provider details ────────────────────────────────────────────────────
    provider = Column(String(50), nullable=False)  # gmail, outlook, smtp

    # ── Subscription identifiers (provider-specific) ────────────────────────
    subscription_id = Column(Text, nullable=True)  # Gmail: watch ID, Outlook: subscription ID
    resource_id = Column(Text, nullable=True)      # Provider-specific resource identifier

    # ── Status tracking ─────────────────────────────────────────────────────
    status = Column(
        SAEnum(SubscriptionStatus),
        default=SubscriptionStatus.PENDING,
        nullable=False
    )
    last_checked_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # When subscription needs renewal

    # ── Error tracking ──────────────────────────────────────────────────────
    last_error = Column(Text, nullable=True)
    error_count = Column(String(50), default="0", nullable=False)

    # ── Timestamps ──────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # ── Indexes ─────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_subscriptions_account", "email_account_id"),
        Index("ix_subscriptions_status", "status"),
        Index("ix_subscriptions_expires", "expires_at"),
        Index("ix_subscriptions_user_provider", "user_id", "provider"),
    )

    def __repr__(self) -> str:
        return f"<EmailProviderSubscription {self.provider} [{self.status}]>"
