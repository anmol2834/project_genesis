"""
AI Engine Input Schema
======================
Strict Pydantic contract for data entering the ACRE pipeline.

Sourced from:
  - email_accounts table  (user_id, email_account_id, provider, automation_enabled, daily_send_limit)
  - email_conversations table (conversation_id, thread_id, subject, from_email, last_24h_messages,
                               message_summary, intent_type, priority_score, tags)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ConversationMessage(BaseModel):
    """
    Single message entry from email_conversations.last_24h_messages JSONB array.
    Structure mirrors the normalizer output written by email-service.
    """
    message_id: str = ""          # empty string for legacy rows without message_id
    from_email: str = Field(alias="from")
    to: List[str] = Field(default_factory=list)
    content: str
    timestamp: datetime
    direction: str  # "incoming" | "outgoing"
    subject: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    has_attachments: Optional[bool] = False

    model_config = {"populate_by_name": True}


class IncomingMessage(BaseModel):
    """The single triggering message that caused this pipeline run."""
    message_id: str
    from_email: str
    to: List[str]
    subject: Optional[str] = None
    content: str
    timestamp: datetime
    cc_emails: Optional[List[str]] = None
    has_attachments: bool = False


class AccountMetadata(BaseModel):
    """
    Relevant fields from email_accounts row — no credentials, no tokens.
    Used by Policy Engine and Context Builder.
    """
    provider: str                    # gmail | outlook | smtp | yahoo | zoho
    automation_enabled: bool
    daily_send_limit: int
    daily_sent_count: int
    warmup_enabled: bool
    is_primary: bool


class AIEngineInput(BaseModel):
    """
    Top-level input contract for the ACRE pipeline.
    Constructed by the orchestrator from DB data after email-service writes a conversation.
    """
    # ── Identity ──────────────────────────────────────────────────────────
    user_id: UUID
    email_account_id: UUID
    conversation_id: UUID

    # ── Thread context ────────────────────────────────────────────────────
    thread_id: str
    subject: Optional[str] = None

    # ── The message that triggered this run ───────────────────────────────
    incoming_message: IncomingMessage

    # ── Recent conversation history (last 24h, ordered ASC by timestamp) ──
    last_24h_messages: List[ConversationMessage] = Field(default_factory=list)

    # ── Full-history AI summary (persisted in DB, may be None for new threads)
    message_summary: Optional[str] = None

    # ── Existing AI fields already stored on the conversation row ─────────
    existing_intent_type: Optional[str] = None
    existing_priority_score: Optional[float] = None
    existing_tags: Optional[List[str]] = Field(default_factory=list)

    # ── Account-level metadata ────────────────────────────────────────────
    account_metadata: AccountMetadata

    # ── Pipeline metadata ─────────────────────────────────────────────────
    pipeline_triggered_at: datetime = Field(default_factory=datetime.utcnow)
    extra: Optional[Dict[str, Any]] = None
