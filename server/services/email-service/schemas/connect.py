"""
Unified Email Connection Schemas
Request/response models for POST /email/connect
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from uuid import UUID


class ConnectionCredentials(BaseModel):
    # OAuth
    code: Optional[str] = None
    # SMTP / manual
    smtp_host: Optional[str] = Field(None, max_length=255)
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = None
    smtp_use_tls: bool = True
    imap_host: Optional[str] = Field(None, max_length=255)
    imap_port: Optional[int] = Field(None, ge=1, le=65535)


class ConnectEmailRequest(BaseModel):
    provider: Literal["gmail", "outlook", "smtp"]
    connection_type: Literal["oauth", "manual"]
    email: Optional[EmailStr] = None
    credentials: ConnectionCredentials = Field(default_factory=ConnectionCredentials)


class ConnectEmailData(BaseModel):
    email: str
    provider: str
    status: str
    account_id: UUID


class ConnectEmailResponse(BaseModel):
    status: str
    message: str
    data: ConnectEmailData
