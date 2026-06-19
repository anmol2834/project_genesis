"""
Migration: Recreate user_data_entries Qdrant collection for BAAI/bge-m3 (1024-dim)

Why this is needed:
  The previous model (intfloat/e5-base-v2) produced 768-dim vectors.
  BAAI/bge-m3 produces 1024-dim vectors.
  Qdrant collections are fixed-dimension — the old collection cannot store
  1024-dim vectors and must be recreated.

What this script does:
  1. Deletes the existing user_data_entries collection (768-dim)
  2. Creates a new user_data_entries collection (1024-dim, Cosine)
  3. Re-reads ALL entries from PostgreSQL (structured_data + search_text)
  4. Re-embeds each entry with BAAI/bge-m3
  5. Re-upserts every point back into Qdrant with the full enterprise payload

WARNING:
  - Step 1 permanently deletes all existing vectors.
  - Ensure no ingestion is running while this migration executes.
  - The migration is resumable: if it crashes, re-run from scratch (upsert is idempotent).

Usage:
  cd server/services/user-service
  python migrations/recreate_qdrant_bge_m3.py
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
NEW_VECTOR_SIZE = 1024
BATCH_SIZE      = 32    # entries per embed+upsert batch


def _get_qdrant():
    from shared.vector_db import get_qdrant_client
    return get_qdrant_client()


def _recreate_collection(client) -> None:
    from qdrant_client.models import VectorParams, Distance

    # Delete existing collection
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        logger.info("Deleted existing collection '%s'", COLLECTION_NAME)
    except Exception as e:
        logger.warning("Could not delete collection (may not exist): %s", e)

    # Create new 1024-dim collection
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=NEW_VECTOR_SIZE, distance=Distance.COSINE),
    )
    logger.info("Created new collection '%s' (%d-dim, Cosine)", COLLECTION_NAME, NEW_VECTOR_SIZE)


def _load_embed_model():
    from sentence_transformers import SentenceTransformer
    import logging as _log
    _log.getLogger("sentence_transformers").setLevel(_log.ERROR)
    model = SentenceTransformer("BAAI/bge-m3")
    _log.getLogger("sentence_transformers").setLevel(_log.INFO)
    logger.info("BAAI/bge-m3 loaded (%d-dim)", NEW_VECTOR_SIZE)
    return model


def _fetch_all_entries():
    """Fetch all non-deleted entries from PostgreSQL using a sync connection."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    from shared.config import get_config

    config = get_config()
    sync_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    connect_args = {}
    if "rds.amazonaws.com" in sync_url:
        connect_args["sslmode"] = "require"

    engine = create_engine(sync_url, connect_args=connect_args, poolclass=NullPool)
    rows = []
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                id, user_id, source_id, category, subtype, title,
                search_text, structured_data, ai_tags, entities,
                quality_score, source_type, updated_at,
                attributes, keywords
            FROM user_data_entries
            WHERE is_deleted = FALSE
            ORDER BY created_at ASC
        """))
        for row in result:
            rows.append(dict(row._mapping))
    engine.dispose()
    logger.info("Fetched %d entries from PostgreSQL", len(rows))
    return rows


def _upsert_batch(client, model, batch: list) -> None:
    from qdrant_client.models import PointStruct

    texts   = [r.get("search_text") or r.get("title") or "" for r in batch]
    # BGE-M3: no prefixes
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=BATCH_SIZE)

    points = []
    for row, vector in zip(batch, vectors):
        entry_id = str(row["id"])
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, entry_id))

        cat_val = row.get("category")
        if hasattr(cat_val, "value"):
            cat_val = cat_val.value

        src_val = row.get("source_type")
        if hasattr(src_val, "value"):
            src_val = src_val.value

        updated = row.get("updated_at")
        if hasattr(updated, "isoformat"):
            updated = updated.isoformat()

        attrs   = row.get("attributes") or {}
        sd      = row.get("structured_data") or {}
        ai_tags = row.get("ai_tags") or []
        kws     = row.get("keywords") or []

        points.append(PointStruct(
            id=point_id,
            vector=vector.tolist(),
            payload={
                "user_id":        str(row["user_id"]),
                "entry_id":       entry_id,
                "source_id":      str(row["source_id"]),
                "category":       cat_val or "uncategorized",
                "subtype":        row.get("subtype") or "",
                "title":          row.get("title") or "",
                "search_text":    (row.get("search_text") or "")[:500],
                "ai_tags":        ai_tags,
                "keywords":       kws,
                "attributes":     attrs,
                "structured_data": sd,
                "status":         attrs.get("status", ""),
                "priority_score": int(attrs.get("priority_score", 2)),
                "quality_score":  float(row.get("quality_score") or 0.0),
                "source_type":    src_val or "manual",
                "updated_at":     updated or "",
                # RIE tags — default values (re-generated on next ingestion)
                "rie_type":                  "product",
                "rie_capabilities":          [],
                "rie_supports_customization": False,
                "rie_is_physical_product":   False,
            },
        ))

    client.upsert(collection_name=COLLECTION_NAME, points=points)


def run_migration():
    client = _get_qdrant()

    # Step 1 & 2: recreate collection
    _recreate_collection(client)

    # Step 3: fetch all entries
    rows = _fetch_all_entries()
    if not rows:
        logger.info("No entries to migrate — collection ready.")
        return

    # Step 4 & 5: embed + upsert in batches
    model    = _load_embed_model()
    total    = len(rows)
    upserted = 0

    for start in range(0, total, BATCH_SIZE):
        batch = rows[start: start + BATCH_SIZE]
        try:
            _upsert_batch(client, model, batch)
            upserted += len(batch)
            logger.info("Progress: %d / %d", upserted, total)
        except Exception as e:
            logger.error("Batch %d failed: %s — continuing", start, e, exc_info=True)

    logger.info("Migration complete: %d / %d entries upserted into '%s' (1024-dim).",
                upserted, total, COLLECTION_NAME)


if __name__ == "__main__":
    run_migration()
