"""
EmailProviderConfig Model - PostgreSQL
Stores provider-level OAuth / SMTP configuration.
Seeded once at startup; not user-specific.
Enables adding new providers without code changes.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum

from shared.database.postgres import Base


class AuthType(str, enum.Enum):
    OAUTH = "oauth"
    SMTP  = "smtp"


class EmailProviderConfig(Base):
    __tablename__ = "email_provider_configs"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_name = Column(String(50), unique=True, nullable=False, index=True)
    auth_type     = Column(SAEnum(AuthType), nullable=False)

    # OAuth fields (nullable for smtp providers)
    base_auth_url = Column(String(500), nullable=True)
    token_url     = Column(String(500), nullable=True)
    scopes        = Column(JSON, nullable=True)   # list[str]

    # Default SMTP/IMAP settings (nullable for oauth providers)
    default_smtp_host = Column(String(255), nullable=True)
    default_smtp_port = Column(String(10),  nullable=True)
    default_imap_host = Column(String(255), nullable=True)
    default_imap_port = Column(String(10),  nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<EmailProviderConfig {self.provider_name}>"
