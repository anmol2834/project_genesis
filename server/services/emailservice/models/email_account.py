"""
emailservice — EmailAccount model (standalone copy, EXACT same schema as email-service)
DO NOT modify the schema — email_accounts table is shared.
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
    SMTP    = "smtp"
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


class WatchStatus(str, enum.Enum):
    ACTIVE  = "active"    # watch is registered and running
    STOPPED = "stopped"   # watch was never started or was explicitly stopped
    EXPIRED = "expired"   # watch expiry passed without renewal


class AccountState(str, enum.Enum):
    """
    Account state machine — replaces the simple is_active boolean.

    Transitions:
      ACTIVE          → TOKEN_EXPIRED   (token refresh fails transiently)
      ACTIVE          → TOKEN_REVOKED   (invalid_grant confirmed permanent)
      TOKEN_EXPIRED   → ACTIVE          (token refresh succeeds on retry)
      TOKEN_EXPIRED   → TOKEN_REVOKED   (invalid_grant after retry)
      TOKEN_REVOKED   → ACTIVE          (user reconnects via OAuth)
      ACTIVE          → WATCH_EXPIRED   (watch_expiry passed, auto-renews)
      WATCH_EXPIRED   → ACTIVE          (watch renewed successfully)
      any             → SYNC_REQUIRED   (history gap detected, needs replay)
      SYNC_REQUIRED   → ACTIVE          (history replay complete)
    """
    ACTIVE        = "active"         # fully operational
    TOKEN_EXPIRED = "token_expired"  # transient — retry token refresh
    TOKEN_REVOKED = "token_revoked"  # permanent — user must reconnect via OAuth
    WATCH_EXPIRED = "watch_expired"  # watch needs renewal (auto-heals)
    SYNC_REQUIRED = "sync_required"  # history gap — needs replay (auto-heals)


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), nullable=False, index=True)
    email_address       = Column(String(255), nullable=False)
    display_name        = Column(String(255), nullable=True)
    provider            = Column(SAEnum(EmailProvider), nullable=False)
    provider_account_id = Column(String(255), nullable=True)
    access_token        = Column(Text, nullable=True)
    refresh_token       = Column(Text, nullable=True)
    token_expiry        = Column(DateTime, nullable=True)
    smtp_host           = Column(String(255), nullable=True)
    smtp_port           = Column(Integer, nullable=True)
    smtp_username       = Column(String(255), nullable=True)
    smtp_password       = Column(Text, nullable=True)
    smtp_use_tls        = Column(Boolean, default=True, nullable=False)
    imap_host           = Column(String(255), nullable=True)
    imap_port           = Column(Integer, nullable=True)
    connection_status   = Column(SAEnum(ConnectionStatus), default=ConnectionStatus.DISCONNECTED, nullable=False)
    sync_status         = Column(SAEnum(SyncStatus), default=SyncStatus.IDLE, nullable=False)
    last_error_message  = Column(Text, nullable=True)
    daily_send_limit    = Column(Integer, default=500, nullable=False)
    daily_sent_count    = Column(Integer, default=0, nullable=False)
    warmup_enabled      = Column(Boolean, default=False, nullable=False)
    last_synced_at      = Column(DateTime, nullable=True)
    last_history_id     = Column(String(64), nullable=True)
    watch_expiry        = Column(DateTime, nullable=True)
    watch_status        = Column(String(20), default="stopped", nullable=False)
    last_watch_started_at = Column(DateTime, nullable=True)
    # account_state: self-healing state machine (replaces simple is_active boolean)
    # is_active is kept for backward compat — always mirrors account_state == ACTIVE
    account_state       = Column(String(20), default="active", nullable=False)
    is_active           = Column(Boolean, default=True, nullable=False)
    is_primary          = Column(Boolean, default=False, nullable=False)
    automation_enabled  = Column(Boolean, default=True, nullable=False)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "email_address", name="uq_email_accounts_user_email"),
        Index("ix_email_accounts_user_status", "user_id", "connection_status"),
        Index("ix_email_accounts_user_active", "user_id", "is_active"),
        Index("ix_email_accounts_watch_status", "provider", "is_active", "watch_status"),
        Index("ix_email_accounts_account_state", "provider", "account_state"),
    )

    def __repr__(self):
        return f"<EmailAccount {self.email_address} [{self.provider}] state={self.account_state}>"
