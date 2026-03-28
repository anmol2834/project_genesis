"""
EmailAccount Model - PostgreSQL
Stores connected email accounts per user.
Supports Gmail, Outlook, and custom SMTP providers.
Credentials are stored encrypted (AES-256 via utils/encryption.py).
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime,
    Text, Enum as SAEnum, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
import enum

from shared.database.postgres import Base


class EmailProvider(str, enum.Enum):
    GMAIL   = "gmail"
    OUTLOOK = "outlook"
    SMTP    = "smtp"       # generic SMTP/IMAP (any provider)
    YAHOO   = "yahoo"
    ZOHO    = "zoho"


class ConnectionStatus(str, enum.Enum):
    CONNECTED    = "connected"
    DISCONNECTED = "disconnected"
    ERROR        = "error"


class SyncStatus(str, enum.Enum):
    IDLE    = "idle"
    SYNCING = "syncing"
    FAILED  = "failed"


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    # ── Identity ────────────────────────────────────────────────────────────
    id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    email_address       = Column(String(255), nullable=False)
    display_name        = Column(String(255), nullable=True)   # friendly label set by user
    provider            = Column(SAEnum(EmailProvider), nullable=False)
    provider_account_id = Column(String(255), nullable=True)   # OAuth subject / account ID

    # ── OAuth tokens (AES-256 encrypted at application layer) ───────────────
    access_token  = Column(Text, nullable=True)   # encrypted
    refresh_token = Column(Text, nullable=True)   # encrypted
    token_expiry  = Column(DateTime, nullable=True)

    # ── SMTP / IMAP credentials (nullable — only for smtp provider) ─────────
    smtp_host     = Column(String(255), nullable=True)
    smtp_port     = Column(Integer,     nullable=True)
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(Text,        nullable=True)   # encrypted
    smtp_use_tls  = Column(Boolean,     default=True, nullable=False)

    imap_host = Column(String(255), nullable=True)
    imap_port = Column(Integer,     nullable=True)

    # ── Status ───────────────────────────────────────────────────────────────
    connection_status = Column(
        SAEnum(ConnectionStatus), default=ConnectionStatus.DISCONNECTED, nullable=False
    )
    sync_status = Column(
        SAEnum(SyncStatus), default=SyncStatus.IDLE, nullable=False
    )
    last_error_message = Column(Text, nullable=True)

    # ── Sending limits (per-account rate control & warmup) ──────────────────
    daily_send_limit = Column(Integer, default=500,  nullable=False)
    daily_sent_count = Column(Integer, default=0,    nullable=False)
    warmup_enabled   = Column(Boolean, default=False, nullable=False)

    # ── Sync tracking ────────────────────────────────────────────────────────
    last_synced_at = Column(DateTime, nullable=True)

    # ── Account flags ────────────────────────────────────────────────────────
    is_active  = Column(Boolean, default=True,  nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    automation_enabled = Column(Boolean, default=True, nullable=False)

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── Constraints & indexes ────────────────────────────────────────────────
    __table_args__ = (
        # One email address per user (prevents duplicate connections)
        UniqueConstraint("user_id", "email_address", name="uq_email_accounts_user_email"),
        # Fast lookups by user + status (dashboard queries)
        Index("ix_email_accounts_user_status", "user_id", "connection_status"),
        # Fast lookups by user + active flag (automation queries)
        Index("ix_email_accounts_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<EmailAccount {self.email_address} [{self.provider}]>"
