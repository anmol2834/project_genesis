"""
Ingestion Pipeline Orchestrator
Coordinates the full data intelligence flow for every input method.

Flow (file/sheet/webhook):
  Raw rows
    -> Column mapping (AI-assisted, e5-base-v2)
    -> Apply mapping (rename keys to canonical)
    -> Batch AI classification (category + subtype + confidence)
    -> Category merge (ai_confidence > 0.75 -> ai wins, else user_category)
    -> Normalization + quality scoring
    -> Conditional raw storage decision (confidence >= 0.80 -> skip raw_data)
    -> PostgreSQL insert
    -> Qdrant embed + upsert (enterprise payload, dedup at 0.95)
    -> Store Qdrant point IDs back in Postgres
    -> Update source stats

Flow (manual entry):
  Structured fields
    -> Normalize
    -> AI classify (if category not provided or low confidence)
    -> Category merge
    -> Conditional raw storage decision
    -> PostgreSQL insert
    -> Qdrant embed + upsert

Flow (update):
  PATCH structured_data
    -> Re-normalize
    -> Re-classify
    -> Version snapshot in user_data_versions
    -> Update Postgres entry
    -> Re-embed + upsert to Qdrant (auto-sync)

Raw data retention policy:
  confidence >= 0.80 → raw_data = NULL  (high confidence, structured data is trusted)
  confidence <  0.80 → raw_data stored  (low confidence, keep original for reprocessing)

  is_raw_retained flag is always stored in classification_meta for observability.
  raw_reference (source_id + row_index) is always stored for future reprocessing.

Auto-sync guarantee:
  Every write to structured_data in Postgres is ALWAYS followed by
  upsert_entries to Qdrant. This is the single enforcement point.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# ── Raw data retention threshold ──────────────────────────────────────────────
# Entries with AI classification confidence >= this value do NOT store raw_data.
# Entries below this threshold retain raw_data for audit and reprocessing.
RAW_RETENTION_CONFIDENCE_THRESHOLD = 0.80


# ── File / Sheet pipeline ─────────────────────────────────────────────────────

async def run_file_pipeline(
    rows: List[Dict[str, Any]],
    headers: List[str],
    source_id: str,
    user_id: str,
    source_type: str,
    session,
    forced_category: str = None,
) -> Dict[str, Any]:
    """
    Full intelligence pipeline for CSV/Excel/Google Sheets rows.

    forced_category: user-selected category from the UI.
    When provided, it is ALWAYS used as the final category for all rows —
    the user's explicit choice is never overridden by AI classification.
    AI classification only runs as a fallback when forced_category is absent.
    """
    from .column_mapper     import map_columns, apply_mapping
    from .classifier        import classify_batch, merge_category
    from .normalizer        import normalize_batch
    from .embedding_service import upsert_entries

    logger.info(
        f"Pipeline start: {len(rows)} rows source={source_id} "
        f"user={user_id} user_category={forced_category or 'none'}"
    )

    # ── Step 1: AI-assisted column mapping ───────────────────────────────
    mapping     = await asyncio.to_thread(map_columns, headers)
    mapped_rows = await asyncio.to_thread(apply_mapping, rows, mapping)
    logger.info(f"Column mapping: {len(mapping)} columns mapped")

    # ── Step 2: AI classification ─────────────────────────────────────────
    # Skip expensive ML inference when the user already chose a category.
    # This cuts ~20s of latency per 20-row upload.
    if forced_category and forced_category not in ("uncategorized", ""):
        # User explicitly selected category — assign it to every row
        ai_results = [("uncategorized", None, 0.0)] * len(mapped_rows)
        logger.info(f"Skipping AI classification — user selected '{forced_category}'")
    else:
        ai_results = await asyncio.to_thread(classify_batch, mapped_rows)

    # ── Step 3: Category merge per row ────────────────────────────────────
    # User-selected category ALWAYS wins. AI is only a fallback.
    final_categories: List[str] = []
    final_subtypes:   List[Optional[str]] = []
    classification_metas: List[Dict] = []

    for row_idx, (ai_cat, subtype, ai_conf) in enumerate(ai_results):
        final_cat, decision = merge_category(ai_cat, ai_conf, forced_category)
        final_categories.append(final_cat)
        # When user forced a category, still detect subtype from mapped row
        if forced_category and forced_category not in ("uncategorized", "") and subtype is None:
            subtype = None  # subtype detection is optional; skip for user-forced uploads
        final_subtypes.append(subtype)
        classification_metas.append({
            "user_category":   forced_category,
            "ai_category":     ai_cat,
            "ai_confidence":   ai_conf,
            "final_category":  final_cat,
            "subtype":         subtype,
            "decision_reason": decision,
            "row_index":       row_idx,
        })

    logger.info(f"Category merge complete. Sample: {final_categories[:3]}")

    # ── Step 4: Normalization + quality scoring + entity extraction ───────
    # Pass classification_metas into normalize_batch so each accepted payload
    # gets the meta for its own source row — fixes the N→M index misalignment.
    payloads, rejection_reasons = await asyncio.to_thread(
        normalize_batch, mapped_rows, final_categories, final_subtypes,
        source_type, rows, classification_metas,
    )
    logger.info(f"Normalization: {len(payloads)} accepted, {len(rejection_reasons)} rejected")

    if not payloads:
        return {"accepted": 0, "rejected": len(rows), "errors": rejection_reasons, "entry_ids": []}

    # ── Step 5: PostgreSQL insert (raw_data preserved) ────────────────────
    entry_ids = await _insert_entries_pg(payloads, source_id, user_id, source_type, session)

    # ── Step 6: Qdrant embed + upsert (enterprise payload) ────────────────
    # NOTE: upsert_entries runs in a thread and takes ~20s for 100 rows.
    # The pipeline session connection may be recycled by the pool during this
    # time. _update_qdrant_ids opens its OWN fresh session to avoid this.
    qdrant_payloads = [
        {**p, "entry_id": eid, "source_id": source_id, "updated_at": datetime.utcnow().isoformat()}
        for p, eid in zip(payloads, entry_ids)
    ]
    qdrant_point_ids = await asyncio.to_thread(upsert_entries, qdrant_payloads, user_id)

    # ── Step 7: Store Qdrant point IDs back in Postgres ───────────────────
    # Opens its own fresh session — avoids stale connection after long upsert
    await _update_qdrant_ids(entry_ids, qdrant_point_ids, session)

    # ── Step 8: Update source stats ───────────────────────────────────────
    # Opens its own fresh session — same reason
    await _update_source_stats(source_id, len(payloads), payloads, session)

    # Commit the pipeline session (covers _insert_entries_pg flush)
    await session.commit()

    # ── Step 9: Compute + store analytics object in Qdrant ────────────────
    # Opens its OWN fresh session — never reuses the pipeline session.
    # asyncpg connections are not safe for concurrent use across tasks.
    asyncio.create_task(_compute_and_store_analytics(
        source_id=source_id,
        user_id=user_id,
        new_payloads=qdrant_payloads,
    ))

    logger.info(f"Pipeline complete: {len(entry_ids)} entries stored")
    return {
        "accepted":  len(entry_ids),
        "rejected":  len(rejection_reasons),
        "errors":    rejection_reasons,
        "entry_ids": entry_ids,
    }


# ── Manual entry pipeline ─────────────────────────────────────────────────────

async def run_manual_pipeline(
    title: str,
    fields: List[Dict[str, str]],
    category: Optional[str],
    source_id: str,
    user_id: str,
    session,
) -> Dict[str, Any]:
    """
    Pipeline for a single manual entry.
    AI classification always runs; confidence merge decides final category.
    """
    from .classifier        import classify_text, merge_category
    from .normalizer        import normalize_row, build_entry_payload
    from .embedding_service import upsert_entries

    raw_data = {f["key"]: f["value"] for f in fields}

    # Build text for classification
    classify_input = " ".join(f"{f['label']}: {f['value']}" for f in fields)
    ai_cat, subtype, ai_conf = await asyncio.to_thread(classify_text, classify_input)

    # Confidence merge
    final_cat, decision = merge_category(ai_cat, ai_conf, category)
    classification_meta = {
        "user_category":   category,
        "ai_category":     ai_cat,
        "ai_confidence":   ai_conf,
        "final_category":  final_cat,
        "subtype":         subtype,
        "decision_reason": decision,
        # row_index is None for manual entries
        "row_index":       None,
    }

    normalized = await asyncio.to_thread(normalize_row, raw_data, final_cat)
    if normalized is None:
        return {"accepted": 0, "rejected": 1, "errors": ["Entry too sparse"], "entry_ids": []}

    # For manual entries, display_data = raw_data (user's own field keys/values)
    from .normalizer import _build_display_structured_data
    display_data = _build_display_structured_data(raw_data)

    payload = await asyncio.to_thread(
        build_entry_payload, normalized, final_cat, subtype, "manual", raw_data, 0.0, display_data
    )
    payload["title"] = title
    payload["classification_meta"] = classification_meta

    entry_ids = await _insert_entries_pg([payload], source_id, user_id, "manual", session)

    qdrant_payloads = [{
        **payload,
        "entry_id":  entry_ids[0],
        "source_id": source_id,
        "updated_at": datetime.utcnow().isoformat(),
    }]
    qdrant_point_ids = await asyncio.to_thread(upsert_entries, qdrant_payloads, user_id)
    await _update_qdrant_ids(entry_ids, qdrant_point_ids, session)
    await _update_source_stats(source_id, 1, [payload], session)
    await session.commit()

    # Compute + store analytics after manual entry (own fresh session)
    asyncio.create_task(_compute_and_store_analytics(
        source_id=source_id,
        user_id=user_id,
        new_payloads=qdrant_payloads,
    ))

    return {"accepted": 1, "rejected": 0, "errors": [], "entry_ids": entry_ids}


# ── Update pipeline (auto-sync Qdrant) ───────────────────────────────────────

async def run_update_pipeline(
    entry_id: str,
    user_id: str,
    updates: Dict[str, Any],
    session,
) -> bool:
    """
    Update an existing entry.
    ALWAYS re-normalizes, re-classifies, and re-embeds to Qdrant.
    This is the auto-sync enforcement point.
    """
    from .classifier        import classify_text, merge_category
    from .normalizer        import normalize_row, build_entry_payload
    from .embedding_service import upsert_entries
    from models.data_entry  import UserDataEntry

    result = await session.execute(
        select(UserDataEntry).where(
            UserDataEntry.id         == entry_id,
            UserDataEntry.user_id    == user_id,
            UserDataEntry.is_deleted == False,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        return False

    # Merge updates into existing structured_data
    new_data = dict(entry.structured_data)
    if "structured_data" in updates:
        new_data.update(updates["structured_data"])

    user_category = updates.get("category", str(entry.category.value if hasattr(entry.category, "value") else entry.category))
    title         = updates.get("title", entry.title)

    # Re-classify on update
    classify_text_input = " ".join(f"{k}: {v}" for k, v in new_data.items() if v)
    ai_cat, subtype, ai_conf = await asyncio.to_thread(classify_text, classify_text_input)
    final_cat, decision = merge_category(ai_cat, ai_conf, user_category)

    normalized = await asyncio.to_thread(normalize_row, new_data, final_cat)
    if normalized is None:
        return False

    # For updates, preserve existing structured_data column names by using new_data as display
    from .normalizer import _build_display_structured_data
    display_data = _build_display_structured_data(new_data)
    src_type = str(entry.source_type.value if hasattr(entry.source_type, "value") else entry.source_type)

    payload = await asyncio.to_thread(
        build_entry_payload, normalized, final_cat, subtype, src_type, new_data, 0.0, display_data
    )
    payload["title"] = title

    # Update entry fields
    entry.structured_data      = payload["structured_data"]
    entry.search_text          = payload["search_text"]
    entry.quality_score        = payload["quality_score"]
    entry.missing_fields       = payload["missing_fields"]
    entry.ai_tags              = payload["ai_tags"]
    entry.ai_relevance         = payload["ai_tags"]
    entry.entities             = payload["entities"]
    entry.subtype              = subtype
    entry.title                = payload["title"]
    entry.category             = final_cat
    entry.classification_meta  = {
        "user_category":   user_category,
        "ai_category":     ai_cat,
        "ai_confidence":   ai_conf,
        "final_category":  final_cat,
        "subtype":         subtype,
        "decision_reason": decision,
    }
    entry.updated_at = datetime.utcnow()

    await session.commit()

    # Auto-sync: re-embed and upsert to Qdrant
    qdrant_payloads = [{
        **payload,
        "entry_id":  str(entry.id),
        "source_id": str(entry.source_id),
        "updated_at": entry.updated_at.isoformat(),
    }]
    await asyncio.to_thread(upsert_entries, qdrant_payloads, user_id)

    logger.info(f"Entry {entry_id} updated, Qdrant synced")
    return True


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _insert_entries_pg(
    payloads: List[Dict[str, Any]],
    source_id: str,
    user_id: str,
    source_type: str,
    session,
) -> List[str]:
    """
    Bulk-insert entry payloads into user_data_entries.

    Conditional raw data storage:
      confidence >= RAW_RETENTION_CONFIDENCE_THRESHOLD (0.80)
        → raw_data = NULL  (structured data is trusted, save storage)
      confidence <  RAW_RETENTION_CONFIDENCE_THRESHOLD
        → raw_data stored  (keep original for audit and reprocessing)

    is_raw_retained and raw_reference are always written into
    classification_meta for full observability — no data is silently lost.
    """
    from models.data_entry import UserDataEntry

    entry_ids = []
    now = datetime.utcnow()

    for payload in payloads:
        cat_val = payload["category"]
        if hasattr(cat_val, "value"):
            cat_val = cat_val.value

        meta        = payload.get("classification_meta") or {}
        ai_conf     = float(meta.get("ai_confidence", 0.0))
        row_index   = meta.get("row_index")
        store_raw   = ai_conf < RAW_RETENTION_CONFIDENCE_THRESHOLD
        raw_to_store = payload.get("raw_data") if store_raw else None

        enriched_meta = {
            **meta,
            "is_raw_retained": store_raw,
            "raw_reference": {"source_id": source_id, "row_index": row_index},
        }
        enriched_meta.pop("row_index", None)

        entry_uuid = uuid.uuid4()
        entry = UserDataEntry(
            id                  = entry_uuid,
            user_id             = user_id,
            source_id           = source_id,
            category            = cat_val,
            subtype             = payload.get("subtype"),
            title               = payload["title"],
            structured_data     = payload["structured_data"],
            raw_data            = raw_to_store,
            search_text         = payload["search_text"],
            ai_tags             = payload.get("ai_tags", []),
            ai_relevance        = payload.get("ai_tags", []),
            entities            = payload.get("entities", []),
            quality_score       = payload.get("quality_score", 0.0),
            missing_fields      = payload.get("missing_fields", []),
            classification_meta = enriched_meta,
            source_type         = source_type,
            version             = 1,
            is_deleted          = False,
            created_at          = now,
            updated_at          = now,
        )
        session.add(entry)
        entry_ids.append(str(entry.id))

    await session.flush()
    logger.info(f"Inserted {len(entry_ids)} entries into PostgreSQL")
    return entry_ids


async def _update_qdrant_ids(
    entry_ids: List[str],
    qdrant_point_ids: List[str],
    session,
) -> None:
    """
    Write Qdrant point IDs back to PostgreSQL.

    Opens a FRESH session instead of reusing the pipeline session.
    The pipeline session may have its underlying asyncpg connection recycled
    by the pool during the long upsert_entries() call (~20s for 100 rows).
    Reusing a recycled connection causes InterfaceError: connection is closed.
    """
    import uuid as _uuid
    from shared.database import get_db_session
    from models.data_entry import UserDataEntry

    if not entry_ids or not qdrant_point_ids:
        return

    try:
        async with get_db_session() as fresh_session:
            for entry_id, point_id in zip(entry_ids, qdrant_point_ids):
                try:
                    eid = _uuid.UUID(entry_id) if isinstance(entry_id, str) else entry_id
                except ValueError:
                    logger.warning(f"Invalid UUID for entry_id: {entry_id}")
                    continue
                await fresh_session.execute(
                    update(UserDataEntry)
                    .where(UserDataEntry.id == eid)
                    .values(qdrant_point_id=point_id, updated_at=datetime.utcnow())
                )
            await fresh_session.commit()
        logger.info(f"Qdrant IDs written back for {len(entry_ids)} entries")
    except Exception as e:
        # Non-fatal: Qdrant IDs are cosmetic — data is already in Qdrant
        logger.error(f"_update_qdrant_ids failed (non-fatal): {e}", exc_info=True)


async def _update_source_stats(
    source_id: str,
    new_count: int,
    payloads: List[Dict[str, Any]],
    session,
) -> None:
    """
    Update source stats. Uses a fresh session to avoid stale connection issues
    after the long upsert_entries() call.
    """
    import uuid as _uuid
    from shared.database import get_db_session
    from models.data_entry import UserDataSource, IngestionStatus

    ai_ready = sum(1 for p in payloads if p.get("quality_score", 0) >= 75)

    try:
        async with get_db_session() as fresh_session:
            try:
                sid = _uuid.UUID(source_id) if isinstance(source_id, str) else source_id
            except ValueError:
                logger.warning(f"Invalid UUID for source_id: {source_id}")
                return
            result = await fresh_session.execute(
                select(UserDataSource).where(UserDataSource.id == sid)
            )
            source = result.scalar_one_or_none()
            if not source:
                return
            source.total_records    = (source.total_records or 0) + new_count
            source.ai_ready_count   = (source.ai_ready_count or 0) + ai_ready
            source.last_sync_at     = datetime.utcnow()
            source.ingestion_status = IngestionStatus.completed
            source.status           = "active"
            await fresh_session.commit()
    except Exception as e:
        logger.error(f"_update_source_stats failed (non-fatal): {e}", exc_info=True)


async def _compute_and_store_analytics(
    source_id: str,
    user_id: str,
    new_payloads: List[Dict[str, Any]],
) -> None:
    """
    Compute category-specific business intelligence for a source and upsert to Qdrant.
    Runs as a background task — doesn't block the ingestion response.

    Data feed strategy:
      Primary  — fetch from Postgres with BOTH structured_data AND attributes columns.
                 attributes holds typed canonical values (price, status, department…)
                 structured_data holds display_data (original CSV keys, user-facing).
      Fallback — if Postgres returns nothing yet (race condition), use new_payloads
                 directly, which already have both keys correctly populated.

    CRITICAL: Opens its OWN fresh DB session via get_db_session.
    """
    await asyncio.sleep(0.5)   # let pipeline commit propagate

    try:
        from shared.database import get_db_session
        from models.data_entry import UserDataEntry, UserDataSource
        from sqlalchemy import select
        from .analytics_engine import compute_source_analytics, upsert_analytics_to_qdrant

        async with get_db_session() as session:
            # Get source name
            source_result = await session.execute(
                select(UserDataSource.name).where(UserDataSource.id == source_id)
            )
            source_name = source_result.scalar_one_or_none() or "Unknown Source"

            # Fetch all entries — include BOTH structured_data (display) and
            # attributes (typed canonical values) so builders can read price,
            # status, department, valid_until etc. correctly.
            entries_result = await session.execute(
                select(
                    UserDataEntry.structured_data,
                    UserDataEntry.category,
                    UserDataEntry.quality_score,
                    UserDataEntry.title,
                ).where(
                    UserDataEntry.source_id  == source_id,
                    UserDataEntry.user_id    == user_id,
                    UserDataEntry.is_deleted == False,
                )
            )
            existing_entries = [
                {
                    # display_data — original CSV column names (user-facing)
                    "structured_data": row.structured_data or {},
                    # attributes not stored in Postgres; pass structured_data as
                    # attributes too so builders can read typed fields directly.
                    # Builders always check attributes first, then structured_data.
                    "attributes":      row.structured_data or {},
                    "category":        str(row.category.value if hasattr(row.category, "value") else row.category),
                    "quality_score":   float(row.quality_score or 0),
                    "title":           row.title or "",
                }
                for row in entries_result.fetchall()
            ]

        # Fallback: DB commit not yet visible — use the just-ingested payloads
        if not existing_entries:
            for p in new_payloads:
                existing_entries.append({
                    "structured_data": p.get("structured_data") or {},
                    "attributes":      p.get("attributes") or {},
                    "category":        str(p.get("category", "")),
                    "quality_score":   float(p.get("quality_score") or 0),
                    "title":           p.get("title") or "",
                })

        if not existing_entries:
            return

        # Determine primary category
        cat_counts: Dict[str, int] = {}
        for e in existing_entries:
            cat = e.get("category", "")
            if cat and cat != "data_analytics":
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        primary_cat = max(cat_counts, key=cat_counts.get) if cat_counts else ""

        # Dispatch to the correct category intelligence builder
        analytics = compute_source_analytics(
            entries=existing_entries,
            source_id=source_id,
            source_name=source_name,
            category_hint=primary_cat,
        )

        if analytics:
            await asyncio.to_thread(
                upsert_analytics_to_qdrant, analytics, user_id, source_id
            )
            logger.info(
                f"Analytics stored | source={source_id[:8]} user={user_id[:8]} "
                f"entries={len(existing_entries)} category={primary_cat}"
            )

    except Exception as e:
        logger.warning(f"Analytics computation failed (non-critical): {e}", exc_info=True)
