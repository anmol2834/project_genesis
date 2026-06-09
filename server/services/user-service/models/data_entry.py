"""
Data Entry Models — PostgreSQL
Source of truth for all user-ingested business data.

Enterprise storage design:
  - raw_data        : original row exactly as received — never mutated
  - structured_data : AI-normalized, cleaned key-value pairs
  - search_text     : embedding-optimized flattened text (regenerated on every update)
  - subtype         : fine-grained classification within category
  - ai_tags         : use-case tags for context builder routing
  - entities        : extracted named entities (prices, names, dates, etc.)
  - classification_meta : full audit trail of how category was decided

Any update to raw_data or structured_data MUST trigger Qdrant re-embedding
via run_update_pipeline — enforced at the pipeline layer.

Tables:
  user_data_sources  — tracks each connected source (CSV, manual, sheets, API)
  user_data_entries  — structured data entries (one per row/record)
  user_data_versions — full version history for every entry update
"""

from sqlalchemy import (
    Column, String, DateTime, Text, JSON, Integer,
    Float, Boolean, ForeignKey, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from shared.database.postgres import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class SourceType(str, enum.Enum):
    csv_import    = "csv_import"
    excel_import  = "excel_import"
    manual        = "manual"
    google_sheets = "google_sheets"
    api           = "api"


class SourceStatus(str, enum.Enum):
    active    = "active"
    paused    = "paused"
    error     = "error"
    syncing   = "syncing"


class DataCategory(str, enum.Enum):
    product_service     = "product_service"
    issue_resolution    = "issue_resolution"   # Troubleshooting & Issue Resolution
    contact_support     = "contact_support"
    offers_promotions   = "offers_promotions"
    delivery_shipping   = "delivery_shipping"
    company_info        = "company_info"
    policies_legal      = "policies_legal"
    educational_content = "educational_content"
    uncategorized       = "uncategorized"
    # Legacy — kept for backward compat with existing DB rows; no new entries
    pricing_payment     = "pricing_payment"


class IngestionStatus(str, enum.Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


# ── user_data_sources ─────────────────────────────────────────────────────────

class UserDataSource(Base):
    """
    Tracks every connected data source per user.
    One source can produce many data entries.
    """
    __tablename__ = "user_data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source identity
    name         = Column(String(255), nullable=False)
    source_type  = Column(SAEnum(SourceType), nullable=False)
    status       = Column(SAEnum(SourceStatus), default=SourceStatus.active, nullable=False)

    # Google Sheets specific
    sheet_url      = Column(Text, nullable=True)
    sheet_id       = Column(String(255), nullable=True)
    sheet_name     = Column(String(255), nullable=True)
    webhook_secret = Column(String(255), nullable=True)

    # API source specific
    api_endpoint = Column(Text, nullable=True)
    api_headers  = Column(JSON, nullable=True)

    # Stats
    total_records  = Column(Integer, default=0, nullable=False)
    ai_ready_count = Column(Integer, default=0, nullable=False)
    last_sync_at   = Column(DateTime, nullable=True)
    last_error     = Column(Text, nullable=True)

    # Ingestion job tracking
    ingestion_status = Column(SAEnum(IngestionStatus), default=IngestionStatus.pending, nullable=False)
    ingestion_log    = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_user_data_sources_user_status", "user_id", "status"),
    )

    def __repr__(self):
        return f"<UserDataSource {self.name} ({self.source_type}) user={self.user_id}>"


# ── user_data_entries ─────────────────────────────────────────────────────────

class UserDataEntry(Base):
    """
    One structured data entry — the core unit of the knowledge base.

    Storage contract:
      raw_data        — immutable original row (audit, re-processing)
      structured_data — AI-cleaned normalized fields (what AI reads)
      search_text     — embedding-optimized text (regenerated on every update)
      subtype         — fine-grained label within category (e.g. "plan" in pricing)
      ai_tags         — routing tags for context builder (e.g. "pricing_info")
      entities        — extracted named entities [{type, value}]
      classification_meta — full audit of how category/subtype was decided
      qdrant_point_id — reference to Qdrant vector (kept in sync automatically)
    """
    __tablename__ = "user_data_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Classification ────────────────────────────────────────────────────
    category = Column(SAEnum(DataCategory), nullable=False, index=True)
    subtype  = Column(String(100), nullable=True, index=True)   # e.g. "plan", "support", "faq"
    title    = Column(String(500), nullable=False)

    # ── Data payload ──────────────────────────────────────────────────────
    # raw_data: original row as received — NEVER mutated after insert
    # structured_data: AI-normalized, cleaned — updated on PATCH
    # search_text: regenerated from structured_data on every update
    raw_data        = Column(JSON, nullable=True)
    structured_data = Column(JSON, nullable=False)
    search_text     = Column(Text, nullable=False)

    # ── AI intelligence fields ────────────────────────────────────────────
    ai_tags    = Column(JSON, nullable=True)   # ["pricing_info", "plan_comparison"]
    entities   = Column(JSON, nullable=True)   # [{"type": "price", "value": "$79"}]
    ai_relevance = Column(JSON, nullable=True) # legacy — kept for backward compat

    # ── Quality ───────────────────────────────────────────────────────────
    quality_score  = Column(Float, default=0.0, nullable=False)
    missing_fields = Column(JSON, nullable=True)

    # ── Classification audit trail ────────────────────────────────────────
    # Stores: user_category, ai_category, ai_confidence, final_category, decision_reason
    classification_meta = Column(JSON, nullable=True)

    # ── Source tracking ───────────────────────────────────────────────────
    source_type = Column(SAEnum(SourceType), nullable=False)
    version     = Column(Integer, default=1, nullable=False)

    # ── Qdrant reference ──────────────────────────────────────────────────
    # Kept in sync: any update to structured_data triggers re-embedding
    qdrant_point_id = Column(String(255), nullable=True, index=True)

    # ── Soft delete ───────────────────────────────────────────────────────
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_user_data_entries_user_category",    "user_id", "category"),
        Index("ix_user_data_entries_user_subtype",     "user_id", "subtype"),
        Index("ix_user_data_entries_user_deleted",     "user_id", "is_deleted"),
        Index("ix_user_data_entries_source",           "source_id", "is_deleted"),
        Index("ix_user_data_entries_quality",          "user_id", "quality_score"),
    )

    def __repr__(self):
        return f"<UserDataEntry {self.title} [{self.category}/{self.subtype}] user={self.user_id}>"


# ── user_data_versions ────────────────────────────────────────────────────────

class UserDataVersion(Base):
    """
    Immutable version history for every data entry update.
    Every PATCH to an entry creates a new version row here.
    Enables full audit trail and rollback capability.
    """
    __tablename__ = "user_data_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_data_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Full snapshot at this version
    version         = Column(Integer, nullable=False)
    structured_data = Column(JSON, nullable=False)
    raw_data        = Column(JSON, nullable=True)
    search_text     = Column(Text, nullable=False)
    quality_score   = Column(Float, nullable=False)
    category        = Column(SAEnum(DataCategory), nullable=False)
    subtype         = Column(String(100), nullable=True)
    title           = Column(String(500), nullable=False)
    ai_tags         = Column(JSON, nullable=True)
    entities        = Column(JSON, nullable=True)

    # Change audit
    change_summary = Column(Text, nullable=True)
    changed_fields = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_user_data_versions_entry_version", "entry_id", "version"),
    )

    def __repr__(self):
        return f"<UserDataVersion entry={self.entry_id} v{self.version}>"
