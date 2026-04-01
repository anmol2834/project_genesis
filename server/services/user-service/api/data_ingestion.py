"""
Data Ingestion API
All endpoints for the My Data page — sources, entries, file upload, manual entry,
Google Sheets connection, webhook receiver, delete, update, stats.

Prefix: /data
Auth:   Bearer JWT (same verify_token pattern as profile.py)

Endpoints:
  POST   /data/upload                              — Upload CSV/Excel file
  POST   /data/manual                              — Manual entry
  POST   /data/sources/google-sheets               — Connect Google Sheet
  POST   /data/webhook/google-sheets/{source_id}   — Receive sheet updates (Apps Script)
  GET    /data/sources                             — List all sources
  DELETE /data/sources/{source_id}                 — Delete source + all its data
  PATCH  /data/sources/{source_id}/sync            — Trigger re-sync (sheets/api)
  GET    /data/entries                             — List entries (paginated, filterable)
  GET    /data/entries/{entry_id}                  — Get single entry
  PATCH  /data/entries/{entry_id}                  — Update entry
  DELETE /data/entries/{entry_id}                  — Soft-delete entry
  GET    /data/stats                               — Aggregate stats
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form,
    Header, HTTPException, Query, UploadFile, status,
)
from sqlalchemy import select, func, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.database import get_db_session
from shared.logger   import get_logger
from models.data_entry import (
    UserDataSource, UserDataEntry, UserDataVersion,
    SourceType, SourceStatus, IngestionStatus,
)
from schemas.data_ingestion import (
    ManualEntryRequest, GoogleSheetsConnectRequest, GoogleSheetsWebhookPayload,
    DataSourceResponse, DataSourceListResponse,
    DataEntryResponse, DataEntryListResponse,
    UpdateDataEntryRequest, IngestionJobResponse,
    DeleteSourceResponse, SyncSourceResponse, DataStatsResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/data", tags=["Data Ingestion"])


# ── Auth dependency (same pattern as profile.py) ──────────────────────────────

async def verify_token(authorization: str = Header(...)) -> str:
    import httpx
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = authorization.replace("Bearer ", "")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8001/auth/verify-token",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            data = resp.json()
            if not data.get("valid"):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            return data["user_id"]
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth service unavailable")


# ── Helper: get source (scoped to user) ──────────────────────────────────────

async def _get_source(source_id: str, user_id: str, session) -> UserDataSource:
    result = await session.execute(
        select(UserDataSource).where(
            UserDataSource.id == source_id,
            UserDataSource.user_id == user_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


# ── POST /data/upload ─────────────────────────────────────────────────────────

@router.post("/upload", response_model=IngestionJobResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_name: str = Form(...),
    category: str = Form(..., description="Required category key, e.g. product_service"),
    user_id: str = Depends(verify_token),
):
    """
    Upload a CSV or Excel file.
    Category is mandatory — must be one of the 8 supported categories.
    File is parsed synchronously (fast), then processing runs in background.
    Returns immediately with a job_id.
    """
    from services.ingestion.file_parser import parse_file, FileParseError
    from models.data_entry import DataCategory as DBDataCategory

    # Validate category
    valid_categories = [c.value for c in DBDataCategory]
    if category not in valid_categories:
        raise HTTPException(status_code=422, detail=f"Invalid category '{category}'. Must be one of: {valid_categories}")

    # Validate file type
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(status_code=400, detail="Only .csv, .xlsx, and .xls files are accepted")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Parse file (fast — no ML yet)
    try:
        rows, headers = parse_file(content, filename)
    except FileParseError as e:
        raise HTTPException(status_code=422, detail=str(e))

    source_type = SourceType.csv_import if ext == "csv" else SourceType.excel_import

    async with get_db_session() as session:
        # Create source record
        source = UserDataSource(
            id               = uuid.uuid4(),
            user_id          = user_id,
            name             = source_name.strip() or filename,
            source_type      = source_type,
            status           = SourceStatus.active,
            ingestion_status = IngestionStatus.processing,
            created_at       = datetime.utcnow(),
            updated_at       = datetime.utcnow(),
        )
        session.add(source)
        await session.commit()
        source_id = str(source.id)

    logger.info(f"File upload: source={source_id} rows={len(rows)} user={user_id} category={category}")

    # Queue background processing
    background_tasks.add_task(
        _run_file_pipeline_bg, source_id, user_id, str(source_type.value), rows, headers, category
    )

    return IngestionJobResponse(
        job_id     = source_id,
        source_id  = source_id,
        status     = "processing",
        message    = f"File received. Processing {len(rows)} rows in background.",
        total_rows = len(rows),
    )


async def _run_file_pipeline_bg(
    source_id: str, user_id: str, source_type: str,
    rows: list, headers: list, forced_category: str = None,
) -> None:
    """Background task wrapper for file pipeline."""
    from services.ingestion.pipeline import run_file_pipeline
    from models.data_entry import UserDataSource, IngestionStatus, SourceStatus

    try:
        async with get_db_session() as session:
            result = await run_file_pipeline(
                rows=rows, headers=headers,
                source_id=source_id, user_id=user_id,
                source_type=source_type, session=session,
                forced_category=forced_category,
            )
            await session.commit()
            logger.info(f"File pipeline done: {result['accepted']} accepted, {result['rejected']} rejected")
    except Exception as e:
        logger.error(f"File pipeline failed for source {source_id}: {e}", exc_info=True)
        async with get_db_session() as session:
            await session.execute(
                sa_update(UserDataSource)
                .where(UserDataSource.id == source_id)
                .values(status=SourceStatus.error, last_error=str(e)[:500],
                        ingestion_status=IngestionStatus.failed)
            )
            await session.commit()


# ── POST /data/manual ─────────────────────────────────────────────────────────

@router.post("/manual", response_model=IngestionJobResponse, status_code=201)
async def create_manual_entry(
    request: ManualEntryRequest,
    user_id: str = Depends(verify_token),
):
    """
    Create a single manual data entry.
    Processed synchronously (small payload).
    """
    from services.ingestion.pipeline import run_manual_pipeline

    async with get_db_session() as session:
        # Create or reuse a "Manual Entry" source for this user
        result = await session.execute(
            select(UserDataSource).where(
                UserDataSource.user_id == user_id,
                UserDataSource.source_type == SourceType.manual,
            ).limit(1)
        )
        source = result.scalar_one_or_none()

        if not source:
            source = UserDataSource(
                id               = uuid.uuid4(),
                user_id          = user_id,
                name             = "Manual Entry",
                source_type      = SourceType.manual,
                status           = SourceStatus.active,
                ingestion_status = IngestionStatus.completed,
                created_at       = datetime.utcnow(),
                updated_at       = datetime.utcnow(),
            )
            session.add(source)
            await session.flush()

        source_id = str(source.id)

        result = await run_manual_pipeline(
            title     = request.title,
            fields    = [f.model_dump() for f in request.fields],
            category  = request.category.value if request.category else None,
            source_id = source_id,
            user_id   = user_id,
            session   = session,
        )
        await session.commit()

    if result["accepted"] == 0:
        raise HTTPException(status_code=422, detail=result["errors"][0] if result["errors"] else "Entry rejected")

    return IngestionJobResponse(
        job_id    = result["entry_ids"][0],
        source_id = source_id,
        status    = "completed",
        message   = "Entry created successfully",
        accepted  = 1,
        rejected  = 0,
    )


# ── POST /data/sources/google-sheets ─────────────────────────────────────────

@router.post("/sources/google-sheets", response_model=DataSourceResponse, status_code=201)
async def connect_google_sheet(
    request: GoogleSheetsConnectRequest,
    user_id: str = Depends(verify_token),
):
    """
    Register a Google Sheet as a live data source.
    Returns the source record with a webhook_secret.
    The user must deploy the Apps Script template using this secret.
    """
    from services.ingestion.sheets_webhook import generate_webhook_secret

    # Extract sheet_id from URL
    sheet_id = _extract_sheet_id(request.sheet_url)

    async with get_db_session() as session:
        source = UserDataSource(
            id               = uuid.uuid4(),
            user_id          = user_id,
            name             = request.name,
            source_type      = SourceType.google_sheets,
            status           = SourceStatus.active,
            sheet_url        = request.sheet_url,
            sheet_id         = sheet_id,
            sheet_name       = request.sheet_name,
            webhook_secret   = generate_webhook_secret(),
            ingestion_status = IngestionStatus.pending,
            created_at       = datetime.utcnow(),
            updated_at       = datetime.utcnow(),
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)

        logger.info(f"Google Sheet connected: source={source.id} user={user_id}")
        return _source_to_response(source)


# ── POST /data/webhook/google-sheets/{source_id} ─────────────────────────────

@router.post("/webhook/google-sheets/{source_id}", status_code=200)
async def receive_sheets_webhook(
    source_id: str,
    payload: GoogleSheetsWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Receive real-time updates from Google Apps Script.
    No auth header — validated via HMAC webhook secret.
    Responds immediately; processing runs in background.
    """
    from services.ingestion.sheets_webhook import (
        validate_webhook_secret, filter_empty_rows, normalize_webhook_rows,
    )

    async with get_db_session() as session:
        result = await session.execute(
            select(UserDataSource).where(
                UserDataSource.id == source_id,
                UserDataSource.source_type == SourceType.google_sheets,
            )
        )
        source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Validate webhook secret
    if not validate_webhook_secret(payload.secret, source.webhook_secret or ""):
        logger.warning(f"Webhook secret mismatch for source {source_id}")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    rows = normalize_webhook_rows(filter_empty_rows(payload.rows))
    if not rows:
        return {"status": "ok", "message": "No data rows received"}

    user_id = str(source.user_id)
    logger.info(f"Webhook received: source={source_id} rows={len(rows)}")

    background_tasks.add_task(
        _run_sheets_pipeline_bg, source_id, user_id, rows
    )

    return {"status": "ok", "message": f"Received {len(rows)} rows, processing in background"}


async def _run_sheets_pipeline_bg(source_id: str, user_id: str, rows: list) -> None:
    from services.ingestion.pipeline import run_file_pipeline
    from models.data_entry import UserDataSource, IngestionStatus, SourceStatus

    headers = list(rows[0].keys()) if rows else []
    try:
        async with get_db_session() as session:
            result = await run_file_pipeline(
                rows=rows, headers=headers,
                source_id=source_id, user_id=user_id,
                source_type="google_sheets", session=session,
            )
            await session.commit()
            logger.info(f"Sheets webhook pipeline done: {result['accepted']} accepted")
    except Exception as e:
        logger.error(f"Sheets pipeline failed for source {source_id}: {e}", exc_info=True)
        async with get_db_session() as session:
            await session.execute(
                sa_update(UserDataSource)
                .where(UserDataSource.id == source_id)
                .values(status=SourceStatus.error, last_error=str(e)[:500],
                        ingestion_status=IngestionStatus.failed)
            )
            await session.commit()


# ── GET /data/sources ─────────────────────────────────────────────────────────

@router.get("/sources", response_model=DataSourceListResponse)
async def list_sources(user_id: str = Depends(verify_token)):
    """List all data sources for the authenticated user."""
    async with get_db_session() as session:
        result = await session.execute(
            select(UserDataSource)
            .where(UserDataSource.user_id == user_id)
            .order_by(UserDataSource.created_at.desc())
        )
        sources = result.scalars().all()

    total_records = sum(s.total_records or 0 for s in sources)
    ai_ready      = sum(s.ai_ready_count or 0 for s in sources)

    return DataSourceListResponse(
        sources       = [_source_to_response(s) for s in sources],
        total         = len(sources),
        ai_ready      = ai_ready,
        total_records = total_records,
    )


# ── DELETE /data/sources/{source_id} ─────────────────────────────────────────

@router.delete("/sources/{source_id}", response_model=DeleteSourceResponse)
async def delete_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_token),
):
    """
    Delete a source and ALL its data entries from Postgres + Qdrant.
    Deletion runs in background; returns immediately.
    """
    async with get_db_session() as session:
        source = await _get_source(source_id, user_id, session)

        # Count entries
        count_result = await session.execute(
            select(func.count(UserDataEntry.id)).where(
                UserDataEntry.source_id == source_id,
                UserDataEntry.user_id == user_id,
            )
        )
        entry_count = count_result.scalar() or 0

    background_tasks.add_task(_delete_source_bg, source_id, user_id)

    return DeleteSourceResponse(
        success         = True,
        source_id       = source_id,
        entries_deleted = entry_count,
        vectors_deleted = entry_count,
        message         = f"Deleting source and {entry_count} entries in background",
    )


async def _delete_source_bg(source_id: str, user_id: str) -> None:
    import asyncio
    from services.ingestion.embedding_service import delete_source_entries

    vectors_deleted = await asyncio.to_thread(delete_source_entries, user_id, source_id)

    async with get_db_session() as session:
        await session.execute(
            sa_delete(UserDataEntry).where(
                UserDataEntry.source_id == source_id,
                UserDataEntry.user_id == user_id,
            )
        )
        await session.execute(
            sa_delete(UserDataSource).where(
                UserDataSource.id == source_id,
                UserDataSource.user_id == user_id,
            )
        )
        await session.commit()

    logger.info(f"Source {source_id} deleted: {vectors_deleted} vectors removed")


# ── PATCH /data/sources/{source_id}/sync ─────────────────────────────────────

@router.patch("/sources/{source_id}/sync", response_model=SyncSourceResponse)
async def sync_source(
    source_id: str,
    user_id: str = Depends(verify_token),
):
    """
    Mark a source as syncing. For Google Sheets, the next webhook push
    will trigger a full re-process. For CSV/Excel, returns instructions.
    """
    async with get_db_session() as session:
        source = await _get_source(source_id, user_id, session)
        source.status           = SourceStatus.syncing
        source.ingestion_status = IngestionStatus.pending
        source.updated_at       = datetime.utcnow()
        await session.commit()

    return SyncSourceResponse(
        success   = True,
        source_id = source_id,
        message   = "Source marked for sync. Next webhook push will re-process all rows.",
    )


# ── GET /data/entries ─────────────────────────────────────────────────────────

@router.get("/entries", response_model=DataEntryListResponse)
async def list_entries(
    user_id:   str = Depends(verify_token),
    category:  Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    page:      int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List data entries for the authenticated user.
    Supports filtering by category and source_id.
    Paginated.
    """
    async with get_db_session() as session:
        q = select(UserDataEntry).where(
            UserDataEntry.user_id   == user_id,
            UserDataEntry.is_deleted == False,
        )
        if category:
            q = q.where(UserDataEntry.category == category)
        if source_id:
            q = q.where(UserDataEntry.source_id == source_id)

        # Total count
        count_q = select(func.count()).select_from(q.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Paginated results
        q = q.order_by(UserDataEntry.updated_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        entries = result.scalars().all()

    return DataEntryListResponse(
        entries   = [_entry_to_response(e) for e in entries],
        total     = total,
        page      = page,
        page_size = page_size,
        has_more  = (page * page_size) < total,
    )


# ── GET /data/entries/{entry_id} ──────────────────────────────────────────────

@router.get("/entries/{entry_id}", response_model=DataEntryResponse)
async def get_entry(
    entry_id: str,
    user_id: str = Depends(verify_token),
):
    async with get_db_session() as session:
        result = await session.execute(
            select(UserDataEntry).where(
                UserDataEntry.id       == entry_id,
                UserDataEntry.user_id  == user_id,
                UserDataEntry.is_deleted == False,
            )
        )
        entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return _entry_to_response(entry)


# ── PATCH /data/entries/{entry_id} ───────────────────────────────────────────

@router.patch("/entries/{entry_id}", response_model=DataEntryResponse)
async def update_entry(
    entry_id: str,
    request: UpdateDataEntryRequest,
    user_id: str = Depends(verify_token),
):
    """
    Update an entry. Re-normalizes, re-embeds, and creates a version snapshot.
    """
    from services.ingestion.pipeline import run_update_pipeline

    updates = request.model_dump(exclude_unset=True)
    if request.category:
        updates["category"] = request.category.value

    async with get_db_session() as session:
        success = await run_update_pipeline(entry_id, user_id, updates, session)
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found or update failed")

        result = await session.execute(
            select(UserDataEntry).where(UserDataEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()

    return _entry_to_response(entry)


# ── DELETE /data/entries/{entry_id} ──────────────────────────────────────────

@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: str,
    user_id: str = Depends(verify_token),
):
    """Soft-delete a single entry and remove its Qdrant vector."""
    import asyncio
    from services.ingestion.embedding_service import delete_entries

    async with get_db_session() as session:
        result = await session.execute(
            select(UserDataEntry).where(
                UserDataEntry.id      == entry_id,
                UserDataEntry.user_id == user_id,
                UserDataEntry.is_deleted == False,
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        qdrant_id = entry.qdrant_point_id
        entry.is_deleted = True
        entry.updated_at = datetime.utcnow()
        await session.commit()

    if qdrant_id:
        await asyncio.to_thread(delete_entries, [qdrant_id])

    logger.info(f"Entry {entry_id} soft-deleted by user {user_id}")


# ── GET /data/stats ───────────────────────────────────────────────────────────

@router.get("/stats", response_model=DataStatsResponse)
async def get_stats(user_id: str = Depends(verify_token)):
    """Aggregate stats for the My Data page header."""
    async with get_db_session() as session:
        # Total entries
        total_entries = (await session.execute(
            select(func.count(UserDataEntry.id)).where(
                UserDataEntry.user_id == user_id,
                UserDataEntry.is_deleted == False,
            )
        )).scalar() or 0

        # Total sources
        total_sources = (await session.execute(
            select(func.count(UserDataSource.id)).where(
                UserDataSource.user_id == user_id,
            )
        )).scalar() or 0

        # Avg quality
        avg_quality = (await session.execute(
            select(func.avg(UserDataEntry.quality_score)).where(
                UserDataEntry.user_id == user_id,
                UserDataEntry.is_deleted == False,
            )
        )).scalar() or 0.0

        # AI-ready (quality >= 75)
        ai_ready = (await session.execute(
            select(func.count(UserDataEntry.id)).where(
                UserDataEntry.user_id == user_id,
                UserDataEntry.is_deleted == False,
                UserDataEntry.quality_score >= 75,
            )
        )).scalar() or 0

        # By category
        cat_rows = (await session.execute(
            select(UserDataEntry.category, func.count(UserDataEntry.id))
            .where(UserDataEntry.user_id == user_id, UserDataEntry.is_deleted == False)
            .group_by(UserDataEntry.category)
        )).all()

        # By source type
        src_rows = (await session.execute(
            select(UserDataEntry.source_type, func.count(UserDataEntry.id))
            .where(UserDataEntry.user_id == user_id, UserDataEntry.is_deleted == False)
            .group_by(UserDataEntry.source_type)
        )).all()

    return DataStatsResponse(
        total_entries    = total_entries,
        total_sources    = total_sources,
        avg_quality      = round(float(avg_quality), 1),
        ai_ready_entries = ai_ready,
        by_category      = {str(r[0].value if hasattr(r[0], 'value') else r[0]): r[1] for r in cat_rows},
        by_source_type   = {str(r[0].value if hasattr(r[0], 'value') else r[0]): r[1] for r in src_rows},
    )


# ── Serialization helpers ─────────────────────────────────────────────────────

def _source_to_response(source: UserDataSource) -> DataSourceResponse:
    return DataSourceResponse(
        id               = str(source.id),
        user_id          = str(source.user_id),
        name             = source.name,
        source_type      = source.source_type.value if hasattr(source.source_type, 'value') else str(source.source_type),
        status           = source.status.value if hasattr(source.status, 'value') else str(source.status),
        total_records    = source.total_records or 0,
        ai_ready_count   = source.ai_ready_count or 0,
        last_sync_at     = source.last_sync_at.isoformat() if source.last_sync_at else None,
        ingestion_status = source.ingestion_status.value if hasattr(source.ingestion_status, 'value') else str(source.ingestion_status),
        sheet_url        = source.sheet_url,
        api_endpoint     = source.api_endpoint,
        created_at       = source.created_at.isoformat(),
        updated_at       = source.updated_at.isoformat(),
    )


def _entry_to_response(entry: UserDataEntry) -> DataEntryResponse:
    return DataEntryResponse(
        id                  = str(entry.id),
        user_id             = str(entry.user_id),
        source_id           = str(entry.source_id),
        category            = entry.category.value if hasattr(entry.category, 'value') else str(entry.category),
        subtype             = entry.subtype,
        title               = entry.title,
        structured_data     = entry.structured_data or {},
        search_text         = entry.search_text or "",
        ai_tags             = entry.ai_tags,
        ai_relevance        = entry.ai_relevance,
        entities            = entry.entities,
        quality_score       = entry.quality_score or 0.0,
        missing_fields      = entry.missing_fields,
        classification_meta = entry.classification_meta,
        source_type         = entry.source_type.value if hasattr(entry.source_type, 'value') else str(entry.source_type),
        version             = entry.version or 1,
        created_at          = entry.created_at.isoformat(),
        updated_at          = entry.updated_at.isoformat(),
    )


# ── Utility ───────────────────────────────────────────────────────────────────

def _extract_sheet_id(url: str) -> Optional[str]:
    """Extract the Google Sheet ID from a spreadsheet URL."""
    import re
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None
