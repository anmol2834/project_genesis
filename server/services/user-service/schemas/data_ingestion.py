"""
Data Ingestion Schemas
Pydantic models for all data ingestion request/response validation.
Covers: file upload, manual entry, Google Sheets webhook, CRUD operations.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


# ── Enums (mirror model enums for schema validation) ─────────────────────────

class SourceTypeEnum(str, Enum):
    csv_import    = "csv_import"
    excel_import  = "excel_import"
    manual        = "manual"
    google_sheets = "google_sheets"
    api           = "api"


class SourceStatusEnum(str, Enum):
    active    = "active"
    paused    = "paused"
    error     = "error"
    syncing   = "syncing"


class DataCategoryEnum(str, Enum):
    product_service     = "product_service"
    pricing_payment     = "pricing_payment"
    contact_support     = "contact_support"
    offers_promotions   = "offers_promotions"
    delivery_shipping   = "delivery_shipping"
    company_info        = "company_info"
    policies_legal      = "policies_legal"
    educational_content = "educational_content"


# ── Manual Entry ──────────────────────────────────────────────────────────────

class ManualEntryField(BaseModel):
    key:   str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=1, max_length=5000)


class ManualEntryRequest(BaseModel):
    """
    POST /data/manual
    User submits a structured form entry manually.
    Category is now mandatory — selected before reaching this form.
    """
    title:    str = Field(..., min_length=2, max_length=500)
    category: DataCategoryEnum = Field(..., description="Required — chosen in the category selection step")
    fields:   List[ManualEntryField] = Field(..., min_length=1, max_length=50)

    @field_validator("fields")
    @classmethod
    def no_duplicate_keys(cls, v: List[ManualEntryField]) -> List[ManualEntryField]:
        keys = [f.key for f in v]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate field keys are not allowed")
        return v

    model_config = {"json_schema_extra": {"example": {
        "title": "Pro Plan Pricing",
        "fields": [
            {"key": "price", "label": "Monthly Price", "value": "$79/month"},
            {"key": "emails", "label": "Emails/Month",  "value": "15,000"},
        ]
    }}}


# ── Google Sheets ─────────────────────────────────────────────────────────────

class GoogleSheetsConnectRequest(BaseModel):
    """
    POST /data/sources/google-sheets
    Connect a Google Sheet as a live data source.
    Category is mandatory — selected before reaching this form.
    """
    name:       str = Field(..., min_length=2, max_length=255)
    sheet_url:  str = Field(..., min_length=10, max_length=2000)
    sheet_name: Optional[str] = Field(None, max_length=255)
    category:   DataCategoryEnum = Field(..., description="Required — chosen in the category selection step")

    @field_validator("sheet_url")
    @classmethod
    def must_be_google_sheets_url(cls, v: str) -> str:
        if "docs.google.com/spreadsheets" not in v:
            raise ValueError("URL must be a valid Google Sheets URL")
        return v


class GoogleSheetsWebhookPayload(BaseModel):
    """
    POST /data/webhook/google-sheets/{source_id}
    Payload sent by Google Apps Script when a sheet is updated.
    """
    secret:    str                       # HMAC secret for validation
    rows:      List[Dict[str, Any]]      # Updated rows as key-value dicts
    sheet_id:  str
    timestamp: Optional[str] = None


# ── Source Responses ──────────────────────────────────────────────────────────

class DataSourceResponse(BaseModel):
    id:               str
    user_id:          str
    name:             str
    source_type:      str
    status:           str
    total_records:    int
    ai_ready_count:   int
    last_sync_at:     Optional[str]
    ingestion_status: str
    sheet_url:        Optional[str] = None
    api_endpoint:     Optional[str] = None
    created_at:       str
    updated_at:       str

    model_config = {"from_attributes": True}


class DataSourceListResponse(BaseModel):
    sources:     List[DataSourceResponse]
    total:       int
    ai_ready:    int
    total_records: int


# ── Entry Responses ───────────────────────────────────────────────────────────

class DataEntryResponse(BaseModel):
    id:                  str
    user_id:             str
    source_id:           str
    category:            str
    subtype:             Optional[str] = None
    title:               str
    structured_data:     Dict[str, Any]
    search_text:         str
    ai_tags:             Optional[List[str]] = None
    ai_relevance:        Optional[List[str]] = None
    entities:            Optional[List[Dict[str, str]]] = None
    quality_score:       float
    missing_fields:      Optional[List[str]] = None
    classification_meta: Optional[Dict[str, Any]] = None
    source_type:         str
    version:             int
    created_at:          str
    updated_at:          str

    model_config = {"from_attributes": True}


class DataEntryListResponse(BaseModel):
    entries:      List[DataEntryResponse]
    total:        int
    page:         int
    page_size:    int
    has_more:     bool


# ── Update Entry ──────────────────────────────────────────────────────────────

class UpdateDataEntryRequest(BaseModel):
    """
    PATCH /data/entries/{entry_id}
    Partial update — only provided fields are changed.
    """
    title:           Optional[str]                  = Field(None, min_length=2, max_length=500)
    category:        Optional[DataCategoryEnum]     = None
    structured_data: Optional[Dict[str, Any]]       = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateDataEntryRequest":
        if not any([self.title, self.category, self.structured_data]):
            raise ValueError("At least one field must be provided for update")
        return self


# ── Ingestion Job Response ────────────────────────────────────────────────────

class IngestionJobResponse(BaseModel):
    """
    Returned immediately after a file upload or sheet connect.
    Processing happens asynchronously.
    """
    job_id:       str
    source_id:    str
    status:       str          # "processing" | "completed" | "failed"
    message:      str
    total_rows:   Optional[int] = None
    accepted:     Optional[int] = None
    rejected:     Optional[int] = None
    errors:       Optional[List[str]] = None


# ── Column Mapping ────────────────────────────────────────────────────────────

class ColumnMappingResult(BaseModel):
    """
    Result of AI-assisted column mapping.
    Maps raw CSV headers → canonical field names.
    """
    original_column: str
    mapped_to:       str
    confidence:      float   # 0.0 – 1.0
    suggested_label: str


class ColumnMappingResponse(BaseModel):
    mappings:    List[ColumnMappingResult]
    unmapped:    List[str]   # Columns that couldn't be mapped


# ── Delete / Sync ─────────────────────────────────────────────────────────────

class DeleteSourceResponse(BaseModel):
    success:         bool
    source_id:       str
    entries_deleted: int
    vectors_deleted: int
    message:         str


class SyncSourceResponse(BaseModel):
    success:    bool
    source_id:  str
    message:    str
    job_id:     Optional[str] = None


# ── Stats ─────────────────────────────────────────────────────────────────────

class DataStatsResponse(BaseModel):
    total_entries:    int
    total_sources:    int
    avg_quality:      float
    ai_ready_entries: int
    by_category:      Dict[str, int]
    by_source_type:   Dict[str, int]
