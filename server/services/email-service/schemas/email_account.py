"""
Email Account Schemas
Pydantic models for email account request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

from models.email_account import EmailProvider, ConnectionStatus, SyncStatus


# ── Connect SMTP Request ─────────────────────────────────────────────────────

class ConnectSMTPRequest(BaseModel):
    email_address: EmailStr
    display_name: Optional[str] = Field(None, max_length=255)
    smtp_host: str = Field(..., max_length=255)
    smtp_port: int = Field(..., ge=1, le=65535)
    smtp_username: str = Field(..., max_length=255)
    smtp_password: str = Field(..., min_length=1)
    smtp_use_tls: bool = True
    imap_host: Optional[str] = Field(None, max_length=255)
    imap_port: Optional[int] = Field(None, ge=1, le=65535)
    daily_send_limit: int = Field(default=500, ge=1, le=10000)

    class Config:
        json_schema_extra = {
            "example": {
                "email_address": "user@domain.com",
                "smtp_host": "smtp.domain.com",
                "smtp_port": 587,
                "smtp_username": "user@domain.com",
                "smtp_password": "app-password",
                "smtp_use_tls": True,
            }
        }


# ── Email Account Response ───────────────────────────────────────────────────

class EmailAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    email_address: str
    display_name: Optional[str]
    provider: EmailProvider
    connection_status: ConnectionStatus
    sync_status: SyncStatus
    daily_send_limit: int
    daily_sent_count: int
    warmup_enabled: bool
    is_active: bool
    is_primary: bool
    automation_enabled: bool
    last_synced_at: Optional[datetime]
    last_error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Update Account Request ───────────────────────────────────────────────────

class UpdateEmailAccountRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    daily_send_limit: Optional[int] = Field(None, ge=1, le=10000)
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
    automation_enabled: Optional[bool] = None
    warmup_enabled: Optional[bool] = None


# ── Account List Response ────────────────────────────────────────────────────

class EmailAccountListResponse(BaseModel):
    accounts: list[EmailAccountResponse]
    total: int
    active: int
