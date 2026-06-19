"""
Migration: Re-score policies_legal + company_info entries to fix 0% AI-Ready

Root Cause
----------
The normalizer v4 used a generic search_text fallback and no keyword expansion
for `policies_legal` and `company_info` categories. These categories have
structurally minimal CSVs (name + short description + status) that scored
between 55–72 under the generic scoring logic — all below the AI-ready
threshold of 75. This caused the frontend to show 0% AI-Ready for both sources.

What This Migration Does
------------------------
1. Fetches ALL entries from PostgreSQL where
     category IN ('policies_legal', 'company_info')
     AND is_deleted = False
2. For each entry, re-runs the v5 normalizer on the canonical data to
   produce new search_text, keywords, and quality_score.
3. Updates Postgres (quality_score, search_text, keywords, updated_at).
4. Updates Qdrant in-place (same point ID preserved — no duplicates).
5. Recalculates ai_ready_count for each affected source and updates
   user_data_sources.ai_ready_count.

Zero data loss: only quality_score, search_text, keywords are recalculated.
Title, structured_data, category, subtype, attributes — all untouched.
Analytics entries (subtype = "data_analytics") are excluded — they already
have quality_score = 95 and don't need re-scoring.

Usage
-----
  cd server/services/user-service
  python migrations/fix_quality_scores.py

Environment
-----------
Requires DATABASE_URL and QDRANT_URL in environment (same as user-service).
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Categories affected by this migration
_TARGET_CATEGORIES = {"policies_legal", "company_info"}

# AI-ready threshold (must match pipeline.py)
AI_READY_THRESHOLD = 75.0


# ── Normalizer v5 re-scoring helpers ─────────────────────────────────────────

def _rebuild_entry_scores(
    structured_data: Dict[str, Any],
    category: str,
    title: str,
    subtype: Optional[str],
) -> Tuple[str, List[str], float]:
    """
    Re-compute search_text, keywords, and quality_score using normalizer v5.

    Uses the display-form structured_data (original CSV column names) as input
    because that's what's stored in Postgres. The normalizer reads all fields
    generically — it doesn't require canonical key names for these categories.

    Returns (search_text, keywords, quality_score).
    """
    from services.ingestion.normalizer import (
        _build_search_text,
        _extract_keywords,
        _compute_quality_score,
        normalize_row,
    )

    # Build a canonical-style data dict the normalizer can work with.
    # For policies_legal: map policy_name→name, summary→description, etc.
    # For company_info:   map information_type→name/information_type, value→field_value, etc.
    # We map conservatively — include all fields, let normalize_row clean them.
    canonical: Dict[str, Any] = {}

    for k, v in structured_data.items():
        if not v or str(v).strip().lower() in ("none", "null", "n/a", "na", "-", ""):
            continue
        k_clean = k.lower().strip()

        # Policy-specific mappings
        if k_clean in ("policy_name",):
            canonical["name"] = str(v)
        elif k_clean in ("summary", "policy_summary"):
            canonical["description"] = str(v)
        elif k_clean == "visibility":
            canonical["visibility"] = str(v)
        elif k_clean in ("effective_date", "effective date"):
            canonical["created_date"] = str(v)
        elif k_clean == "status":
            s = str(v).strip().lower()
            canonical["status"] = "active" if s in ("active", "yes", "enabled", "live") else s

        # Company info-specific mappings
        elif k_clean in ("information_type", "information type"):
            canonical["information_type"] = str(v)
            if "name" not in canonical:
                canonical["name"] = str(v)  # use information_type as name if no name yet
        elif k_clean == "value":
            canonical["field_value"] = str(v)
        elif k_clean == "description":
            # Company info: description is the label, value is the data
            # Don't overwrite existing description that was merged by normalize_row
            if "description" not in canonical:
                canonical["description"] = str(v)

        # Generic fallback — keep the field as-is
        else:
            canonical[k_clean] = str(v)

    # If still no name, use title
    if "name" not in canonical:
        canonical["name"] = title

    # For company_info: merge field_value into description (mirrors normalize_row logic)
    if "field_value" in canonical:
        fv = canonical.pop("field_value")
        existing_desc = canonical.get("description", "")
        if existing_desc and str(fv).strip() and str(fv).strip() not in existing_desc:
            canonical["description"] = f"{existing_desc}: {str(fv).strip()}"
        elif not existing_desc:
            canonical["description"] = str(fv).strip()

    # Run normalizer
    normalized = normalize_row(canonical, category)
    if normalized is None:
        # Sparse entry — use raw canonical as fallback
        normalized = canonical

    # Re-generate search_text, keywords, quality_score
    search_text = _build_search_text(normalized, category, subtype, title)
    keywords    = _extract_keywords(normalized, title)
    quality     = _compute_quality_score(
        normalized, category,
        title=title, search_text=search_text, keywords=keywords,
    )

    return search_text, keywords, quality


# ── Qdrant update ─────────────────────────────────────────────────────────────

def _update_qdrant_payload(
    qdrant_point_id: str,
    search_text: str,
    keywords: List[str],
    quality_score: float,
    updated_at: str,
) -> bool:
    """Update payload fields in Qdrant in-place (preserves vector)."""
    try:
        from shared.vector_db import get_qdrant_client
        from qdrant_client.models import SetPayload

        client = get_qdrant_client()
        client.set_payload(
            collection_name="user_data_entries",
            payload={
                "search_text":   search_text,
                "keywords":      keywords,
                "quality_score": quality_score,
                "updated_at":    updated_at,
            },
            points=[qdrant_point_id],
        )
        return True
    except Exception as e:
        logger.warning(f"Qdrant update failed for point {qdrant_point_id}: {e}")
        return False


# ── Main migration ─────────────────────────────────────────────────────────────

async def run_migration() -> None:
    from shared.database import init_database, close_database, get_db_session
    from models.data_entry import UserDataEntry, UserDataSource
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    await init_database()

    logger.info("=" * 60)
    logger.info("Migration: fix_quality_scores")
    logger.info(f"Targets: {_TARGET_CATEGORIES}")
    logger.info(f"AI-ready threshold: {AI_READY_THRESHOLD}")
    logger.info("=" * 60)

    updated_entries  = 0
    skipped_entries  = 0
    failed_entries   = 0
    newly_ai_ready   = 0

    # Track source-level ai_ready counts for the final source stats update
    source_ready_map: Dict[str, Dict[str, int]] = {}  # {source_id: {total: N, ai_ready: N}}

    async with get_db_session() as session:
        # Fetch all non-deleted entries in target categories
        result = await session.execute(
            select(UserDataEntry).where(
                UserDataEntry.category.in_(_TARGET_CATEGORIES),
                UserDataEntry.is_deleted == False,
            )
        )
        entries: List[UserDataEntry] = result.scalars().all()

    logger.info(f"Found {len(entries)} entries to process")

    for entry in entries:
        entry_id     = str(entry.id)
        source_id    = str(entry.source_id)
        category     = str(entry.category.value if hasattr(entry.category, "value") else entry.category)
        title        = entry.title or ""
        subtype      = entry.subtype
        old_score    = float(entry.quality_score or 0)
        qdrant_id    = entry.qdrant_point_id

        # Skip analytics entries — they have quality_score=95 by design
        if subtype == "data_analytics":
            skipped_entries += 1
            continue

        # Track source stats
        if source_id not in source_ready_map:
            source_ready_map[source_id] = {"total": 0, "ai_ready": 0}
        source_ready_map[source_id]["total"] += 1

        try:
            sd = entry.structured_data or {}
            new_search_text, new_keywords, new_quality = _rebuild_entry_scores(
                sd, category, title, subtype
            )
            now_iso = datetime.utcnow().isoformat()

            # Postgres update
            async with get_db_session() as session:
                await session.execute(
                    sa_update(UserDataEntry)
                    .where(UserDataEntry.id == entry.id)
                    .values(
                        search_text   = new_search_text,
                        quality_score = new_quality,
                        updated_at    = datetime.utcnow(),
                    )
                )
                await session.commit()

            # Qdrant update (in-place payload patch, no re-embedding needed)
            if qdrant_id:
                _update_qdrant_payload(qdrant_id, new_search_text, new_keywords, new_quality, now_iso)

            if new_quality >= AI_READY_THRESHOLD:
                source_ready_map[source_id]["ai_ready"] += 1
                if old_score < AI_READY_THRESHOLD:
                    newly_ai_ready += 1

            updated_entries += 1
            logger.info(
                f"  [{category}] {title[:50]:<50} "
                f"score: {old_score:5.1f} → {new_quality:5.1f}  "
                f"{'✅ AI-Ready' if new_quality >= AI_READY_THRESHOLD else '⚠️  below 75'}"
            )

        except Exception as e:
            logger.error(f"  Failed to update entry {entry_id[:12]} ({title[:30]}): {e}")
            failed_entries += 1

    # ── Update source ai_ready_count ──────────────────────────────────────
    logger.info("\nUpdating source ai_ready_count ...")
    for source_id, counts in source_ready_map.items():
        try:
            async with get_db_session() as session:
                await session.execute(
                    sa_update(UserDataSource)
                    .where(UserDataSource.id == source_id)
                    .values(
                        ai_ready_count = counts["ai_ready"],
                        total_records  = counts["total"],
                        updated_at     = datetime.utcnow(),
                    )
                )
                await session.commit()
            ai_pct = round(counts["ai_ready"] / max(counts["total"], 1) * 100)
            logger.info(
                f"  Source {source_id[:12]}: "
                f"{counts['ai_ready']}/{counts['total']} AI-ready = {ai_pct}%"
            )
        except Exception as e:
            logger.error(f"  Failed to update source {source_id[:12]}: {e}")

    await close_database()

    logger.info("\n" + "=" * 60)
    logger.info(f"Migration complete:")
    logger.info(f"  Updated entries : {updated_entries}")
    logger.info(f"  Newly AI-ready  : {newly_ai_ready}")
    logger.info(f"  Skipped         : {skipped_entries}")
    logger.info(f"  Failed          : {failed_entries}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_migration())
