"""
EmailConversation Model - AI-First Unified Storage
Single table for all email conversations with embedded message history.
Optimized for AI context, real-time updates, and high-performance queries.

Design Philosophy:
- Memory system for AI, not just email storage
- JSONB for flexible message history (last 24h)
- Persistent AI summary for full conversation context
- Minimal tables, maximum intelligence
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Float, DateTime,
    Text, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from shared.database.postgres import Base


class EmailConversation(Base):
    """
    Unified email conversation storage.
    Each row represents a conversation thread with embedded message history.
    """
    __tablename__ = "email_conversations"

    # ═══════════════════════════════════════════════════════════════════════
    # 🔥 CORE IDENTIFIERS
    # ═══════════════════════════════════════════════════════════════════════
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Multi-tenant isolation
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Email account this conversation belongs to
    email_account_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Provider identifier (gmail, outlook, smtp)
    provider = Column(String(50), nullable=False)
    
    # Thread identifier from email provider (Gmail: thread_id, Outlook: conversationId)
    thread_id = Column(String(255), nullable=False)
    
    # Latest message ID in this conversation (for deduplication)
    # NOTE: uniqueness is enforced per-user via UniqueConstraint below, NOT globally
    message_id = Column(String(255), nullable=False)

    # ═══════════════════════════════════════════════════════════════════════
    # 📧 EMAIL METADATA
    # ═══════════════════════════════════════════════════════════════════════
    
    from_email = Column(Text, nullable=False)
    
    # JSONB arrays for multiple recipients
    to_emails = Column(JSONB, nullable=False, default=list)
    cc_emails = Column(JSONB, nullable=True, default=list)
    bcc_emails = Column(JSONB, nullable=True, default=list)
    
    subject = Column(Text, nullable=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 🧠 CONVERSATION STORAGE (CORE AI FEATURE)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Last 24 hours of messages in this conversation
    # Structure: [{"message_id": "...", "from": "...", "to": [...], "content": "...", "timestamp": "...", "direction": "incoming/outgoing"}]
    # MUST be: normalized, ordered (timestamp ASC), clean (no HTML junk)
    last_24h_messages = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Recent message history for AI context (auto-trimmed to 24h)"
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 🧠 AI SUMMARY FIELD (CRITICAL FOR LLM)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Full conversation summary (NOT limited to 24h)
    # Used directly in LLM prompts for context
    # Persists entire conversation history in condensed form
    message_summary = Column(
        Text,
        nullable=True,
        comment="AI-generated summary of full conversation history"
    )

    # ═══════════════════════════════════════════════════════════════════════
    # ⚡ PERFORMANCE & STATUS FIELDS
    # ═══════════════════════════════════════════════════════════════════════
    
    # Timestamp of most recent message (for sorting inbox)
    last_message_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    # Read/unread status
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    
    # Conversation lifecycle status
    # Values: active, archived, snoozed, deleted
    conversation_status = Column(
        String(50),
        default="active",
        nullable=False,
        index=True
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 📊 ADVANCED AI FIELDS (ENTERPRISE)
    # ═══════════════════════════════════════════════════════════════════════
    
    # AI-detected intent (support, sales, inquiry, complaint, etc.)
    intent_type = Column(String(100), nullable=True, index=True)
    
    # AI-calculated priority score (0.0 - 1.0)
    priority_score = Column(Float, nullable=True, index=True)
    
    # Flexible tags for categorization
    # Structure: ["urgent", "customer", "follow-up"]
    tags = Column(JSONB, nullable=True, default=list)

    # ═══════════════════════════════════════════════════════════════════════
    # 🕒 TIMESTAMPS
    # ═══════════════════════════════════════════════════════════════════════
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        server_default=func.now()
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        server_default=func.now()
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 🔍 INDEXES & CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════════════
    
    __table_args__ = (
        Index("ix_email_conversations_user_thread",   "user_id", "thread_id"),
        Index("ix_email_conversations_user_message",  "user_id", "message_id"),
        Index("ix_email_conversations_inbox",         "user_id", "conversation_status", "is_read", "last_message_at"),
        Index("ix_email_conversations_priority",      "user_id", "priority_score", "last_message_at"),
        Index("ix_email_conversations_intent",        "user_id", "intent_type", "conversation_status"),
        Index("ix_email_conversations_messages_gin",  "last_24h_messages", postgresql_using="gin"),
        Index("ix_email_conversations_tags_gin",      "tags",              postgresql_using="gin"),
        UniqueConstraint("user_id", "message_id", name="uq_email_conversations_user_message"),
    )

    def __repr__(self) -> str:
        return f"<EmailConversation thread={self.thread_id[:8]}... from={self.from_email}>"
