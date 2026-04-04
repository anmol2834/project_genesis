"""
Embedding Service — Qdrant Storage + Deduplication

Collection : user_data_entries
Model      : intfloat/e5-base-v2  (768-dim, Cosine)

Qdrant payload per point (enterprise, context-builder-safe):
    user_id, entry_id, source_id,
    category, subtype,
    title, search_text (truncated),
    ai_tags, entities,
    quality_score, source_type, updated_at

Deduplication:
    cosine_similarity(new, existing) > 0.95  AND  same user_id
    -> reuse existing point ID (update in-place, no duplicate vectors)

Multi-tenancy:
    Every Qdrant query MUST carry a user_id filter.
    Cross-user access is structurally impossible.

Auto-sync contract:
    Any write to structured_data in Postgres MUST be followed by
    upsert_entries(). Enforced by run_update_pipeline in pipeline.py.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

COLLECTION_NAME = "user_data_entries"
VECTOR_SIZE     = 768
DEDUP_THRESHOLD = 0.95
BATCH_SIZE      = 50

_model = None


# ── Model ─────────────────────────────────────────────────────────────────────

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("intfloat/e5-base-v2")
        logger.info("Embedding service: e5-base-v2 loaded")
    return _model


# ── Collection bootstrap ──────────────────────────────────────────────────────

def ensure_collection() -> bool:
    """Create the Qdrant collection if it does not exist. Called at startup."""
    from shared.vector_db import create_collection
    return create_collection(
        collection_name=COLLECTION_NAME,
        vector_size=VECTOR_SIZE,
        distance="Cosine",
    )


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Encode a list of search_text strings with e5-base-v2.
    Uses 'passage:' prefix as required by the e5 instruction-tuned model.
    Returns a (N, 768) float32 ndarray of L2-normalised vectors.
    """
    model = _get_model()
    prefixed = [f"passage: {t[:512]}" for t in texts]
    return model.encode(prefixed, normalize_embeddings=True, batch_size=32)


# ── Upsert ────────────────────────────────────────────────────────────────────

def upsert_entries(entries: List[Dict[str, Any]], user_id: str) -> List[str]:
    """
    Embed and upsert a batch of entry payloads into Qdrant.

    Steps per entry:
      1. Embed search_text with e5-base-v2
      2. Dedup check: cosine > 0.95 with same user -> reuse existing point ID
      3. Build enterprise payload
      4. Batch upsert to Qdrant

    Args:
        entries : list of dicts, each must contain at minimum:
                  entry_id, search_text, category, title, quality_score,
                  source_type, updated_at
                  Optional: source_id, subtype, ai_tags, entities
        user_id : owner — injected into every payload for multi-tenancy

    Returns:
        List of Qdrant point IDs in the same order as input entries.
    """
    if not entries:
        return []

    from shared.vector_db import get_qdrant_client
    from qdrant_client.models import PointStruct

    client    = get_qdrant_client()
    texts     = [e["search_text"] for e in entries]
    embs      = embed_texts(texts)

    point_ids: List[str]        = []
    to_upsert: List[PointStruct] = []

    for i, entry in enumerate(entries):
        entry_id   = str(entry["entry_id"])
        emb_vector = embs[i].tolist()

        # ── Deduplication ─────────────────────────────────────────────────
        existing_id = _find_duplicate(client, emb_vector, user_id, entry_id)
        if existing_id:
            qdrant_id = existing_id
            logger.debug(f"Dedup hit: entry {entry_id} -> reuse point {qdrant_id}")
        else:
            # Deterministic UUID so the same entry always maps to the same point
            qdrant_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, entry_id))

        point_ids.append(qdrant_id)

        # ── Enterprise payload ────────────────────────────────────────────
        to_upsert.append(PointStruct(
            id=qdrant_id,
            vector=emb_vector,
            payload={
                # Multi-tenancy (mandatory filter key for every search)
                "user_id":        user_id,

                # Entry identity
                "entry_id":       entry_id,
                "source_id":      str(entry.get("source_id") or ""),

                # Classification — enables category + subtype filtering
                "category":       entry.get("category") or "uncategorized",
                "subtype":        entry.get("subtype") or "",

                # Search + display
                "title":          entry.get("title") or "",
                "search_text":    (entry.get("search_text") or "")[:500],

                # AI routing tags (dynamic, contextual)
                "ai_tags":        entry.get("ai_tags") or entry.get("ai_relevance") or [],

                # Keywords for fast keyword matching (20+ tokens)
                "keywords":       entry.get("keywords") or [],

                # Typed attributes for filterable search (price, stock, supplier, etc.)
                # Now includes: email, phone, working_hours, department, valid_until, description
                "attributes":     entry.get("attributes") or {},

                # Full structured data — preserved for LLM context (Phase 2 schema)
                "structured_data": entry.get("structured_data") or {},

                # Top-level filter fields (promoted from attributes for direct Qdrant filtering)
                "status":         (entry.get("attributes") or {}).get("status", ""),
                "priority_score": int((entry.get("attributes") or {}).get("priority_score", 2)),

                # Quality + provenance
                "quality_score":  float(entry.get("quality_score") or 0.0),
                "source_type":    entry.get("source_type") or "manual",

                # Timestamp (ISO string)
                "updated_at":     entry.get("updated_at") or "",
            },
        ))

    # ── Batch upsert ──────────────────────────────────────────────────────
    for start in range(0, len(to_upsert), BATCH_SIZE):
        batch = to_upsert[start: start + BATCH_SIZE]
        try:
            client.upsert(collection_name=COLLECTION_NAME, points=batch)
            logger.info(f"Upserted {len(batch)} points to '{COLLECTION_NAME}'")
        except Exception as exc:
            logger.error(f"Qdrant upsert failed: {exc}", exc_info=True)
            raise

    return point_ids


# ── Delete helpers ────────────────────────────────────────────────────────────

def delete_entries(point_ids: List[str]) -> bool:
    """Delete Qdrant points by their point IDs (called on soft-delete)."""
    if not point_ids:
        return True
    from shared.vector_db import get_qdrant_client
    client = get_qdrant_client()
    try:
        client.delete(collection_name=COLLECTION_NAME, points_selector=point_ids)
        logger.info(f"Deleted {len(point_ids)} points from '{COLLECTION_NAME}'")
        return True
    except Exception as exc:
        logger.error(f"Qdrant delete_entries failed: {exc}", exc_info=True)
        return False


def delete_user_entries(user_id: str) -> int:
    """
    Delete ALL Qdrant points for a given user.
    Used when a user account is removed.
    Returns count of deleted points.
    """
    from shared.vector_db import get_qdrant_client
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_qdrant_client()
    f = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
    try:
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=f,
            limit=10_000,
            with_vectors=False,
        )
        count = len(points)
        if count > 0:
            client.delete(collection_name=COLLECTION_NAME, points_selector=f)
        logger.info(f"Deleted {count} Qdrant points for user {user_id}")
        return count
    except Exception as exc:
        logger.error(f"Qdrant delete_user_entries failed: {exc}", exc_info=True)
        return 0


def delete_source_entries(user_id: str, source_id: str) -> int:
    """
    Delete all Qdrant points belonging to a specific source for a user.
    Called when a source is deleted from Postgres.
    Returns count of deleted points.
    """
    from shared.vector_db import get_qdrant_client
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_qdrant_client()
    f = Filter(must=[
        FieldCondition(key="user_id",   match=MatchValue(value=user_id)),
        FieldCondition(key="source_id", match=MatchValue(value=source_id)),
    ])
    try:
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=f,
            limit=10_000,
            with_vectors=False,
        )
        count = len(points)
        if count > 0:
            client.delete(collection_name=COLLECTION_NAME, points_selector=f)
        logger.info(f"Deleted {count} Qdrant points for source {source_id}")
        return count
    except Exception as exc:
        logger.error(f"Qdrant delete_source_entries failed: {exc}", exc_info=True)
        return 0


# ── Deduplication ─────────────────────────────────────────────────────────────

def _find_duplicate(
    client,
    vector: List[float],
    user_id: str,
    entry_id: str,
) -> Optional[str]:
    """
    Search for a near-duplicate point in Qdrant scoped to this user.

    Returns the existing Qdrant point ID if:
      - cosine_similarity > DEDUP_THRESHOLD (0.95)
      - the matching point belongs to a DIFFERENT entry (not itself)

    Returns None otherwise (insert new point).
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    user_filter = Filter(
        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    )
    try:
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=user_filter,
            limit=1,
            score_threshold=DEDUP_THRESHOLD,
            with_payload=True,
        )
        for r in results:
            # Exclude the entry's own existing point (handles re-embed on update)
            if r.payload.get("entry_id") != entry_id:
                return str(r.id)
    except Exception as exc:
        # Non-fatal: if dedup check fails, we insert a new point
        logger.warning(f"Dedup search failed (non-fatal): {exc}")
    return None
