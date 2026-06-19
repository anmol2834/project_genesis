"""
Migration: Fix analytics entries stored with category="data_analytics"

Problem: A previous version of analytics_engine.py stored all analytics
         (source_insights) entries with category="data_analytics" regardless
         of the actual source category. This makes retrieval fail because
         Brain #1 queries by the real category (delivery_shipping, product_service,
         etc.) and never finds the analytics entries.

Fix: Scan Qdrant for all points where
       - subtype = "source_insights"   (analytics marker)
       - category = "data_analytics"   (the bad generic bucket)
     then read structured_data.primary_category from each point payload
     and re-upsert with the correct category.

The deterministic point ID (uuid5 of "analytics:{user_id}:{source_id}") is
preserved — so the re-upsert is an in-place update, not a duplicate insert.

Usage:
  cd server/services/user-service
  python migrations/fix_analytics_category.py
"""

import sys
import os
import uuid
import logging
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

COLLECTION_NAME = "user_data_entries"
SCROLL_BATCH    = 100   # points per Qdrant scroll page

# The 8 valid source categories — anything outside this set gets skipped
_VALID_CATEGORIES = {
    "product_service",
    "offers_promotions",
    "delivery_shipping",
    "company_info",
    "educational_content",
    "contact_support",
    "policies_legal",
    "issue_resolution",
}


def _get_qdrant_client():
    from shared.vector_db import get_qdrant_client
    return get_qdrant_client()


def run_migration():
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
    except ImportError:
        logger.error("qdrant_client not installed — run: pip install qdrant-client")
        return

    client = _get_qdrant_client()

    logger.info("Scanning Qdrant for analytics points with category='data_analytics' ...")

    updated = 0
    skipped = 0
    offset  = None

    while True:
        # Scroll through all points matching category=data_analytics + subtype=source_insights
        scroll_filter = Filter(must=[
            FieldCondition(key="category", match=MatchValue(value="data_analytics")),
            FieldCondition(key="subtype",  match=MatchValue(value="source_insights")),
        ])

        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=scroll_filter,
            limit=SCROLL_BATCH,
            offset=offset,
            with_payload=True,
            with_vectors=True,   # need vectors to re-upsert in-place
        )

        if not points:
            break

        for point in points:
            payload = point.payload or {}

            # Read the real category from structured_data.primary_category
            structured = payload.get("structured_data") or {}
            real_category = (
                structured.get("primary_category")
                or payload.get("attributes", {}).get("primary_category")
                or ""
            ).strip()

            if real_category not in _VALID_CATEGORIES:
                logger.warning(
                    f"  Skipping point {str(point.id)[:12]} — "
                    f"primary_category={real_category!r} not in valid set"
                )
                skipped += 1
                continue

            # Re-upsert the point with the corrected category field
            # All other payload fields are preserved exactly as-is
            corrected_payload = {
                **payload,
                "category": real_category,
                "updated_at": datetime.utcnow().isoformat(),
            }

            from qdrant_client.models import PointStruct
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=[PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=corrected_payload,
                )],
            )

            user_id   = str(payload.get("user_id", ""))[:8]
            source_id = str(payload.get("source_id", ""))[:8]
            logger.info(
                f"  Fixed point {str(point.id)[:12]} | user={user_id} "
                f"source={source_id} | data_analytics -> {real_category}"
            )
            updated += 1

        # Advance cursor
        if next_offset is None:
            break
        offset = next_offset

    logger.info(f"\nMigration complete: {updated} fixed, {skipped} skipped.")


if __name__ == "__main__":
    run_migration()
