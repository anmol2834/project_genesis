"""
EmailAccountHealth Model - PostgreSQL
Tracks deliverability and performance metrics per email account.
health_score (0-100) is calculated from bounce/spam/reply rates.
One row per account; updated on each health check cycle.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID

from shared.database.postgres import Base


class EmailAccountHealth(Base):
    __tablename__ = "email_account_health"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # one health record per account
        index=True,
    )

    # ── Volume ───────────────────────────────────────────────────────────────
    emails_sent     = Column(Integer, default=0,   nullable=False)
    emails_received = Column(Integer, default=0,   nullable=False)

    # ── Rates (0.0 – 1.0 floats, e.g. 0.24 = 24%) ──────────────────────────
    bounce_rate = Column(Float, default=0.0, nullable=False)
    reply_rate  = Column(Float, default=0.0, nullable=False)
    open_rate   = Column(Float, default=0.0, nullable=False)
    spam_rate   = Column(Float, default=0.0, nullable=False)
    click_rate  = Column(Float, default=0.0, nullable=False)

    # ── Composite score (0–100, higher = healthier) ──────────────────────────
    # Calculated: 100 - (bounce_rate*40 + spam_rate*40 - reply_rate*20) * 100
    health_score = Column(Float, default=100.0, nullable=False)

    last_checked_at = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Allows analytics queries: "accounts with health_score < 50"
        Index("ix_email_account_health_score", "health_score"),
    )

    def __repr__(self) -> str:
        return f"<EmailAccountHealth account={self.email_account_id} score={self.health_score}>"
