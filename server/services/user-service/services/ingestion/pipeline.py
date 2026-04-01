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

    forced_category: user-selected category from UI (optional signal, not truth).
    AI classification always runs; confidence merge decides final category.
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

    # ── Step 2: AI classification (always runs) ───────────────────────────
    # Returns (ai_category, subtype, ai_confidence) per row
    ai_results = await asyncio.to_thread(classify_batch, mapped_rows)

    # ── Step 3: Category merge per row ────────────────────────────────────
    # Enterprise rule: ai_confidence > 0.75 -> ai wins, else user_category
    final_categories: List[str] = []
    final_subtypes:   List[Optional[str]] = []
    classification_metas: List[Dict] = []

    for row_idx, (ai_cat, subtype, ai_conf) in enumerate(ai_results):
        final_cat, decision = merge_category(ai_cat, ai_conf, forced_category)
        final_categories.append(final_cat)
        final_subtypes.append(subtype)
        classification_metas.append({
            "user_category":   forced_category,
            "ai_category":     ai_cat,
            "ai_confidence":   ai_conf,
            "final_category":  final_cat,
            "subtype":         subtype,
            "decision_reason": decision,
            # Raw retention fields — populated in _insert_entries_pg
            "row_index":       row_idx,
        })

    logger.info(f"Category merge complete. Sample: {final_categories[:3]}")

    # ── Step 4: Normalization + quality scoring + entity extraction ───────
    payloads, rejection_reasons = await asyncio.to_thread(
        normalize_batch, mapped_rows, final_categories, final_subtypes, source_type, rows
    )
    logger.info(f"Normalization: {len(payloads)} accepted, {len(rejection_reasons)} rejected")

    if not payloads:
        return {"accepted": 0, "rejected": len(rows), "errors": rejection_reasons, "entry_ids": []}

    # Attach classification_meta to each payload
    accepted_metas = [m for m, p in zip(classification_metas, payloads)]
    for payload, meta in zip(payloads, accepted_metas):
        payload["classification_meta"] = meta

    # ── Step 5: PostgreSQL insert (raw_data preserved) ────────────────────
    entry_ids = await _insert_entries_pg(payloads, source_id, user_id, source_type, session)

    # ── Step 6: Qdrant embed + upsert (enterprise payload) ────────────────
    qdrant_payloads = [
        {**p, "entry_id": eid, "source_id": source_id, "updated_at": datetime.utcnow().isoformat()}
        for p, eid in zip(payloads, entry_ids)
    ]
    qdrant_point_ids = await asyncio.to_thread(upsert_entries, qdrant_payloads, user_id)

    # ── Step 7: Store Qdrant point IDs back in Postgres ───────────────────
    await _update_qdrant_ids(entry_ids, qdrant_point_ids, session)

    # ── Step 8: Update source stats ───────────────────────────────────────
    await _update_source_stats(source_id, len(payloads), payloads, session)

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

    payload = await asyncio.to_thread(
        build_entry_payload, normalized, final_cat, subtype, "manual", raw_data
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
    from models.data_entry  import UserDataEntry, UserDataVersion

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

    payload = await asyncio.to_thread(
        build_entry_payload, normalized, final_cat, subtype,
        str(entry.source_type.value if hasattr(entry.source_type, "value") else entry.source_type),
        new_data,
    )
    payload["title"] = title

    # Version snapshot before update
    version_num = (entry.version or 1) + 1
    version = UserDataVersion(
        entry_id        = entry.id,
        user_id         = user_id,
        version         = entry.version or 1,
        structured_data = entry.structured_data,
        raw_data        = entry.raw_data,
        search_text     = entry.search_text,
        quality_score   = entry.quality_score,
        category        = entry.category,
        subtype         = entry.subtype,
        title           = entry.title,
        ai_tags         = entry.ai_tags,
        entities        = entry.entities,
        change_summary  = f"Updated to version {version_num}",
        changed_fields  = list(updates.keys()),
    )
    session.add(version)

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
    entry.version              = version_num
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

    logger.info(f"Entry {entry_id} updated to v{version_num}, Qdrant synced")
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
    from models.data_entry import UserDataEntry, UserDataVersion

    entry_ids = []
    now = datetime.utcnow()

    for payload in payloads:
        cat_val = payload["category"]
        if hasattr(cat_val, "value"):
            cat_val = cat_val.value

        # ── Raw retention decision ────────────────────────────────────────
        meta        = payload.get("classification_meta") or {}
        ai_conf     = float(meta.get("ai_confidence", 0.0))
        row_index   = meta.get("row_index")          # set by run_file_pipeline
        store_raw   = ai_conf < RAW_RETENTION_CONFIDENCE_THRESHOLD

        raw_to_store = payload.get("raw_data") if store_raw else None

        # Build enriched classification_meta with retention audit fields
        enriched_meta = {
            **meta,
            "is_raw_retained": store_raw,
            "raw_reference": {
                "source_id": source_id,
                "row_index": row_index,   # None for manual entries
            },
        }
        # Remove internal row_index from top-level meta (it's in raw_reference now)
        enriched_meta.pop("row_index", None)

        # ── Enterprise logging ────────────────────────────────────────────
        entry_uuid = uuid.uuid4()
        logger.info(
            f"[raw_retention] entry={entry_uuid} "
            f"confidence={ai_conf:.4f} "
            f"store_raw={store_raw} "
            f"decision={'RETAIN raw_data' if store_raw else 'SKIP raw_data (high confidence)'}"
        )

        entry = UserDataEntry(
            id                  = entry_uuid,
            user_id             = user_id,
            source_id           = source_id,
            category            = cat_val,
            subtype             = payload.get("subtype"),
            title               = payload["title"],
            structured_data     = payload["structured_data"],
            raw_data            = raw_to_store,          # NULL when high confidence
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

        # Version snapshot — always stores raw_data regardless of retention policy
        # (version history is the safety net for reprocessing)
        version = UserDataVersion(
            entry_id        = entry.id,
            user_id         = user_id,
            version         = 1,
            structured_data = payload["structured_data"],
            raw_data        = payload.get("raw_data"),   # always stored in version
            search_text     = payload["search_text"],
            quality_score   = payload.get("quality_score", 0.0),
            category        = cat_val,
            subtype         = payload.get("subtype"),
            title           = entry.title,
            ai_tags         = payload.get("ai_tags", []),
            entities        = payload.get("entities", []),
            change_summary  = "Initial ingestion",
            changed_fields  = [],
            created_at      = now,
        )
        session.add(version)

    await session.flush()
    logger.info(f"Inserted {len(entry_ids)} entries into PostgreSQL")
    return entry_ids


async def _update_qdrant_ids(
    entry_ids: List[str],
    qdrant_point_ids: List[str],
    session,
) -> None:
    from models.data_entry import UserDataEntry
    for entry_id, point_id in zip(entry_ids, qdrant_point_ids):
        await session.execute(
            update(UserDataEntry)
            .where(UserDataEntry.id == entry_id)
            .values(qdrant_point_id=point_id)
        )


async def _update_source_stats(
    source_id: str,
    new_count: int,
    payloads: List[Dict[str, Any]],
    session,
) -> None:
    from models.data_entry import UserDataSource, IngestionStatus
    result = await session.execute(
        select(UserDataSource).where(UserDataSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        return
    ai_ready = sum(1 for p in payloads if p.get("quality_score", 0) >= 75)
    source.total_records    = (source.total_records or 0) + new_count
    source.ai_ready_count   = (source.ai_ready_count or 0) + ai_ready
    source.last_sync_at     = datetime.utcnow()
    source.ingestion_status = IngestionStatus.completed
    source.status           = "active"
