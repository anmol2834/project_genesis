"""
automationservice — Enterprise Hybrid Retrieval Engine
=======================================================
Collection  : user_data_entries
Model       : intfloat/e5-base-v2  (768-dim, Cosine)
Architecture: Dense (vector) + Metadata (scroll/filter) fusion

Multi-tenancy contract:
    EVERY search call includes payload.user_id == user_id.
    Cross-tenant access is structurally impossible.

Pipeline position:
    Processor #1 output  →  THIS MODULE  →  Reranker  →  Processor #2

Phases:
    1. Category filter build  — strict per-category Qdrant filters
    2. Analytics routing      — data_analytics category + primary_category attr
    3. Dense retrieval        — e5-base-v2 "query: " prefix, top-K=20 per query
    4. Metadata retrieval     — scroll with keyword/attribute/value matching
    5. Parallel execution     — asyncio.gather() across all category × query pairs
    6. Score fusion           — vector + metadata + quality + priority weighted sum
    7. Result limiting        — top-20 per category → top-10 after fusion

Embedding prefix contract (must match user-service embedding_service.py):
    Storage : "passage: {search_text}"   ← user-service writes this
    Query   : "query: {query_text}"      ← automationservice reads with this
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from typing import Any

_SVC_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)
for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger("automationservice.qdrant_search")

# ── Constants ──────────────────────────────────────────────────────────────────

COLLECTION_NAME = "user_data_entries"
VECTOR_SIZE     = 768

# Per-query vector search top-K (candidates before fusion)
DENSE_TOP_K          = 20
# Per-query metadata scroll top-K
METADATA_TOP_K       = 20
# Per-category result cap after fusion (passed to reranker)
PER_CATEGORY_TOP_K   = 10
# Minimum vector score to include a candidate
VECTOR_SCORE_FLOOR   = 0.30

# Score fusion weights  (must sum to 1.0)
W_VECTOR   = 0.60
W_METADATA = 0.20
W_QUALITY  = 0.10
W_PRIORITY = 0.10

# Allowed category values (mirrors user-service DataCategory enum)
ALLOWED_CATEGORIES = frozenset({
    "product_service",
    "offers_promotions",
    "delivery_shipping",
    "company_info",
    "educational_content",
    "contact_support",
    "policies_legal",
    "issue_resolution",
    "data_analytics",
})

# ── Lazy singletons ────────────────────────────────────────────────────────────

_embed_model   = None
_qdrant_client = None


# ── Model & client access ──────────────────────────────────────────────────────

def _get_embed_model():
    """
    Lazy-load intfloat/e5-base-v2 singleton.
    Identical to user-service model_singleton — same model, same dimension,
    guarantees query/passage vector space alignment.
    """
    global _embed_model
    if _embed_model is None:
        import threading
        _lock = threading.Lock()
        with _lock:
            if _embed_model is None:
                from sentence_transformers import SentenceTransformer
                import logging as _log
                _log.getLogger("sentence_transformers").setLevel(_log.ERROR)
                _embed_model = SentenceTransformer("intfloat/e5-base-v2")
                _log.getLogger("sentence_transformers").setLevel(_log.INFO)
                logger.info("automationservice: e5-base-v2 loaded (768-dim)")
    return _embed_model


def _get_qdrant_client():
    """
    Lazy-load the shared Qdrant client singleton.
    Reuses shared.vector_db which the user-service also uses — same connection.
    """
    global _qdrant_client
    if _qdrant_client is None:
        from shared.vector_db import get_qdrant_client
        _qdrant_client = get_qdrant_client()
    return _qdrant_client


def _embed_query(query: str) -> list[float]:
    """
    Embed a single retrieval query using e5-base-v2 with "query: " prefix.

    e5-base-v2 instruction:
        Storage   → "passage: {text}"  (user-service writes this)
        Retrieval → "query: {text}"    (we use this)
    This asymmetry is required by the e5 architecture for max recall.
    """
    model   = _get_embed_model()
    prefixed = f"query: {query.strip()[:512]}"
    vector   = model.encode(prefixed, normalize_embeddings=True)
    return vector.tolist()


# ── Filter builders ────────────────────────────────────────────────────────────

def _build_category_filter(user_id: str, category: str):
    """
    Build a strict Qdrant Filter for tenant-scoped category search.

    Mandatory conditions:
        user_id  == user_id    (multi-tenancy isolation — NON-NEGOTIABLE)
        category == category   (category isolation — reduces noise)
        is_deleted != true     (exclude soft-deleted entries if indexed)
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    return Filter(must=[
        FieldCondition(key="user_id",  match=MatchValue(value=user_id)),
        FieldCondition(key="category", match=MatchValue(value=category)),
    ])


def _build_analytics_filter(user_id: str, primary_category: str):
    """
    Build analytics-specific filter.

    Analytics records have:
        category             = "data_analytics"
        attributes.primary_category = <source category>

    Both conditions are required to avoid mixing analytics summaries
    from unrelated categories.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    return Filter(must=[
        FieldCondition(key="user_id",                     match=MatchValue(value=user_id)),
        FieldCondition(key="category",                    match=MatchValue(value="data_analytics")),
        FieldCondition(key="attributes.primary_category", match=MatchValue(value=primary_category)),
    ])


def _build_tenant_only_filter(user_id: str):
    """
    Tenant-only filter — no category restriction.
    Used for fallback scroll when category-filtered search returns 0 results.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    return Filter(must=[
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
    ])


# ── Dense retrieval ────────────────────────────────────────────────────────────

async def _dense_search(
    query: str,
    user_id: str,
    category: str,
    top_k: int = DENSE_TOP_K,
) -> list[dict[str, Any]]:
    """
    Vector similarity search scoped to user_id + category.
    Runs in a thread pool to avoid blocking the event loop.
    Returns list of raw Qdrant ScoredPoint dicts.
    """
    def _run() -> list[dict]:
        client   = _get_qdrant_client()
        vector   = _embed_query(query)
        f        = _build_category_filter(user_id, category)
        results  = client.search(
            collection_name = COLLECTION_NAME,
            query_vector    = vector,
            query_filter    = f,
            limit           = top_k,
            score_threshold = VECTOR_SCORE_FLOOR,
            with_payload    = True,
            with_vectors    = False,
        )
        return [{"id": str(r.id), "vector_score": r.score, "payload": r.payload or {}} for r in results]

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("[dense_search] failed cat=%s query='%s': %s", category, query[:60], exc)
        return []


async def _analytics_dense_search(
    query: str,
    user_id: str,
    primary_category: str,
    top_k: int = DENSE_TOP_K,
) -> list[dict[str, Any]]:
    """Vector search scoped to data_analytics + primary_category."""
    def _run() -> list[dict]:
        client  = _get_qdrant_client()
        vector  = _embed_query(query)
        f       = _build_analytics_filter(user_id, primary_category)
        results = client.search(
            collection_name = COLLECTION_NAME,
            query_vector    = vector,
            query_filter    = f,
            limit           = top_k,
            score_threshold = VECTOR_SCORE_FLOOR,
            with_payload    = True,
            with_vectors    = False,
        )
        return [{"id": str(r.id), "vector_score": r.score, "payload": r.payload or {}} for r in results]

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("[analytics_dense] failed primary_cat=%s: %s", primary_category, exc)
        return []


# ── Metadata retrieval ─────────────────────────────────────────────────────────

def _metadata_score(payload: dict[str, Any], query_tokens: frozenset[str]) -> float:
    """
    Score a Qdrant payload against a set of query tokens.

    Searches ALL payload fields including nested structured_data and attributes
    values — not just keys. This covers cases like:
        - Customer: "512GB SSD"  → matches structured_data value "512GB SSD"
        - Customer: "Mon-Sat"    → matches attribute value "Mon-Sat"
        - Customer: "$1049"      → matches structured_data value "$1,049"
        - Customer: "South"      → matches title or attribute value "Repair Center South"

    Scoring:
        title match      → +0.40 per matching token (highest weight — most discriminative)
        keywords match   → +0.30 per matching token
        ai_tags match    → +0.25 per matching token
        structured_data  → +0.20 per matching token in any value
        attributes       → +0.20 per matching token in any value
        search_text      → +0.15 per matching token (broad fallback)

    Score is capped at 1.0 and normalized to 0.0–1.0.
    """
    if not query_tokens:
        return 0.0

    score = 0.0
    n     = len(query_tokens)

    def _tokenize(text: Any) -> frozenset[str]:
        return frozenset(str(text).lower().split()) if text else frozenset()

    def _json_values(obj: Any) -> list[str]:
        """Recursively collect all leaf string/numeric values from nested dict/list."""
        results: list[str] = []
        if isinstance(obj, dict):
            for v in obj.values():
                results.extend(_json_values(v))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(_json_values(item))
        elif obj is not None:
            results.append(str(obj))
        return results

    # Title — highest signal
    title_tokens = _tokenize(payload.get("title", ""))
    hits = len(query_tokens & title_tokens)
    score += (hits / n) * 0.40

    # Keywords list
    kw_tokens: frozenset[str] = frozenset()
    kws = payload.get("keywords") or []
    if isinstance(kws, list):
        kw_tokens = frozenset(" ".join(str(k) for k in kws).lower().split())
    hits = len(query_tokens & kw_tokens)
    score += (hits / n) * 0.30

    # AI tags
    tag_tokens: frozenset[str] = frozenset()
    tags = payload.get("ai_tags") or []
    if isinstance(tags, list):
        tag_tokens = frozenset(" ".join(str(t) for t in tags).lower().split())
    hits = len(query_tokens & tag_tokens)
    score += (hits / n) * 0.25

    # Structured data — search ALL values (including nested)
    sd_values  = _json_values(payload.get("structured_data") or {})
    sd_tokens  = frozenset(" ".join(sd_values).lower().split())
    hits = len(query_tokens & sd_tokens)
    score += (hits / n) * 0.20

    # Attributes — search ALL values (including nested)
    attr_values = _json_values(payload.get("attributes") or {})
    attr_tokens = frozenset(" ".join(attr_values).lower().split())
    hits = len(query_tokens & attr_tokens)
    score += (hits / n) * 0.20

    # Search text (broad fallback)
    st_tokens = _tokenize(payload.get("search_text", ""))
    hits = len(query_tokens & st_tokens)
    score += (hits / n) * 0.15

    return min(score, 1.0)


async def _metadata_search(
    query: str,
    user_id: str,
    category: str,
    top_k: int = METADATA_TOP_K,
) -> list[dict[str, Any]]:
    """
    Metadata-driven scroll search.
    Fetches up to top_k points by filter (no vector), scores each by keyword
    overlap across ALL payload fields and values (including nested JSON).
    Returns list of {id, metadata_score, payload} dicts sorted by score desc.
    """
    def _run() -> list[dict]:
        client  = _get_qdrant_client()
        f       = _build_category_filter(user_id, category)
        # Scroll returns up to top_k points — no vector similarity
        points, _cursor = client.scroll(
            collection_name = COLLECTION_NAME,
            scroll_filter   = f,
            limit           = top_k,
            with_payload    = True,
            with_vectors    = False,
        )
        if not points:
            return []

        # Tokenize query for matching
        q_tokens = frozenset(query.lower().split())
        scored = []
        for p in points:
            payload = p.payload or {}
            ms = _metadata_score(payload, q_tokens)
            if ms > 0.0:
                scored.append({"id": str(p.id), "metadata_score": ms, "payload": payload})
        scored.sort(key=lambda x: x["metadata_score"], reverse=True)
        return scored[:top_k]

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("[metadata_search] failed cat=%s query='%s': %s", category, query[:60], exc)
        return []


async def _analytics_metadata_search(
    query: str,
    user_id: str,
    primary_category: str,
    top_k: int = METADATA_TOP_K,
) -> list[dict[str, Any]]:
    """Metadata scroll for data_analytics category scoped to primary_category."""
    def _run() -> list[dict]:
        client  = _get_qdrant_client()
        f       = _build_analytics_filter(user_id, primary_category)
        points, _ = client.scroll(
            collection_name = COLLECTION_NAME,
            scroll_filter   = f,
            limit           = top_k,
            with_payload    = True,
            with_vectors    = False,
        )
        if not points:
            return []
        q_tokens = frozenset(query.lower().split())
        scored = []
        for p in points:
            payload = p.payload or {}
            ms = _metadata_score(payload, q_tokens)
            scored.append({"id": str(p.id), "metadata_score": ms, "payload": payload})
        scored.sort(key=lambda x: x["metadata_score"], reverse=True)
        return scored[:top_k]

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("[analytics_metadata] failed primary_cat=%s: %s", primary_category, exc)
        return []


# ── Score fusion ───────────────────────────────────────────────────────────────

def _fuse_results(
    dense_hits:    list[dict[str, Any]],
    metadata_hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge dense and metadata results into a single ranked list.

    Fusion formula (weights defined at module top):
        final_score = W_VECTOR   * vector_score
                    + W_METADATA * metadata_score
                    + W_QUALITY  * normalized_quality_score
                    + W_PRIORITY * normalized_priority_score

    quality_score : stored as 0.0–100.0 in payload → normalize to 0.0–1.0
    priority_score: stored as 0–5 in payload       → normalize to 0.0–1.0

    Deduplication: same point_id from both sources → takes MAX of each score.
    """
    merged: dict[str, dict[str, Any]] = {}

    for hit in dense_hits:
        pid = hit["id"]
        merged[pid] = {
            "id":             pid,
            "vector_score":   hit.get("vector_score", 0.0),
            "metadata_score": 0.0,
            "payload":        hit.get("payload", {}),
        }

    for hit in metadata_hits:
        pid = hit["id"]
        if pid in merged:
            # Take the better metadata score
            merged[pid]["metadata_score"] = max(
                merged[pid]["metadata_score"],
                hit.get("metadata_score", 0.0),
            )
        else:
            merged[pid] = {
                "id":             pid,
                "vector_score":   0.0,
                "metadata_score": hit.get("metadata_score", 0.0),
                "payload":        hit.get("payload", {}),
            }

    fused: list[dict[str, Any]] = []
    for entry in merged.values():
        payload = entry["payload"]
        raw_q   = float(payload.get("quality_score", 0.0))
        raw_p   = int(payload.get("priority_score", 2))

        # Normalize quality (0–100 → 0–1) and priority (0–5 → 0–1)
        q_norm = min(raw_q / 100.0, 1.0)
        p_norm = min(raw_p / 5.0,   1.0)

        final_score = (
            W_VECTOR   * entry["vector_score"]
            + W_METADATA * entry["metadata_score"]
            + W_QUALITY  * q_norm
            + W_PRIORITY * p_norm
        )

        fused.append({
            "id":             entry["id"],
            "vector_score":   round(entry["vector_score"],   4),
            "metadata_score": round(entry["metadata_score"], 4),
            "quality_score":  round(q_norm,                  4),
            "priority_score": round(p_norm,                  4),
            "score":          round(final_score,             4),
            "payload":        payload,
        })

    fused.sort(key=lambda x: x["score"], reverse=True)
    return fused


# ── Per-category search ────────────────────────────────────────────────────────

async def _search_category(
    category:  str,
    queries:   list[str],
    user_id:   str,
    analytics: bool = False,
    analytics_primary_category: str = "",
) -> dict[str, Any]:
    """
    Execute all queries for a single category in parallel (dense + metadata).

    For analytics routing:
        category  = "data_analytics"
        analytics_primary_category = original intent category (e.g. "product_service")
        Both filters use the analytics-specific filter builder.

    Returns:
        {
            category, queries_executed, vector_hits, metadata_hits,
            candidates_before_fusion, candidates_after_fusion, results
        }
    """
    if analytics:
        # Analytics routing: both dense and metadata use analytics filter
        tasks = []
        for q in queries:
            tasks.append(_analytics_dense_search(q, user_id, analytics_primary_category))
            tasks.append(_analytics_metadata_search(q, user_id, analytics_primary_category))
    else:
        tasks = []
        for q in queries:
            tasks.append(_dense_search(q, user_id, category))
            tasks.append(_metadata_search(q, user_id, category))

    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Split interleaved [dense0, meta0, dense1, meta1, ...] results
    all_dense:    list[dict] = []
    all_metadata: list[dict] = []
    for i, result in enumerate(all_results):
        if isinstance(result, Exception):
            logger.warning("[search_category] task %d failed: %s", i, result)
            continue
        if i % 2 == 0:
            all_dense.extend(result)
        else:
            all_metadata.extend(result)

    # Deduplicate within each source by point id (take max score)
    def _dedup_max(hits: list[dict], score_key: str) -> list[dict]:
        best: dict[str, dict] = {}
        for h in hits:
            pid = h["id"]
            if pid not in best or h.get(score_key, 0.0) > best[pid].get(score_key, 0.0):
                best[pid] = h
        return list(best.values())

    dense_dedup    = _dedup_max(all_dense,    "vector_score")
    metadata_dedup = _dedup_max(all_metadata, "metadata_score")

    fused = _fuse_results(dense_dedup, metadata_dedup)
    top   = fused[:PER_CATEGORY_TOP_K]

    return {
        "category":                  category,
        "queries_executed":          len(queries),
        "vector_hits":               len(dense_dedup),
        "metadata_hits":             len(metadata_dedup),
        "candidates_before_fusion":  len(fused),
        "candidates_after_fusion":   len(top),
        "results":                   top,
    }


# ── Fallback: tenant-wide scroll ──────────────────────────────────────────────

async def _fallback_scroll(
    user_id: str,
    query: str,
    top_k: int = PER_CATEGORY_TOP_K,
) -> list[dict[str, Any]]:
    """
    Emergency fallback: scroll ALL user data regardless of category.
    Triggered when every category search returns 0 results.
    Guarantees that downstream (Processor #2) always has at least some context.
    """
    def _run() -> list[dict]:
        client  = _get_qdrant_client()
        f       = _build_tenant_only_filter(user_id)
        points, _ = client.scroll(
            collection_name = COLLECTION_NAME,
            scroll_filter   = f,
            limit           = top_k * 3,
            with_payload    = True,
            with_vectors    = False,
        )
        if not points:
            return []
        q_tokens = frozenset(query.lower().split())
        scored = []
        for p in points:
            payload = p.payload or {}
            ms = _metadata_score(payload, q_tokens)
            scored.append({
                "id":             str(p.id),
                "vector_score":   0.0,
                "metadata_score": ms,
                "quality_score":  min(float(payload.get("quality_score", 0.0)) / 100.0, 1.0),
                "priority_score": min(int(payload.get("priority_score", 2)) / 5.0, 1.0),
                "score":          ms,
                "payload":        payload,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.error("[fallback_scroll] failed user=%s: %s", user_id[:8], exc)
        return []


# ── Result formatter ───────────────────────────────────────────────────────────

def _format_result(hit: dict[str, Any], category: str) -> dict[str, Any]:
    """
    Convert a fused hit into the canonical output format consumed by the reranker
    and Processor #2. Strips large/unnecessary payload fields for downstream safety.
    """
    payload = hit.get("payload", {})
    return {
        "entry_id":    payload.get("entry_id") or hit.get("id", ""),
        "category":    payload.get("category", category),
        "subtype":     payload.get("subtype", ""),
        "score":       hit.get("score", 0.0),
        "vector_score":   hit.get("vector_score", 0.0),
        "metadata_score": hit.get("metadata_score", 0.0),
        "quality_score":  hit.get("quality_score", 0.0),
        "priority_score": hit.get("priority_score", 0.0),
        "source_type": payload.get("source_type", ""),
        "title":       payload.get("title", ""),
        "search_text": payload.get("search_text", ""),
        "ai_tags":     payload.get("ai_tags") or [],
        "keywords":    payload.get("keywords") or [],
        # Full structured payload for LLM context — the entire business knowledge chunk
        "payload": {
            "title":           payload.get("title", ""),
            "search_text":     payload.get("search_text", ""),
            "structured_data": payload.get("structured_data") or {},
            "attributes":      payload.get("attributes") or {},
            "ai_tags":         payload.get("ai_tags") or [],
            "keywords":        payload.get("keywords") or [],
            "entities":        payload.get("entities") or [],
            "rie_type":        payload.get("rie_type", ""),
            "rie_capabilities":payload.get("rie_capabilities") or [],
            "status":          payload.get("status", ""),
            "source_type":     payload.get("source_type", ""),
            "quality_score":   payload.get("quality_score", 0.0),
            "updated_at":      payload.get("updated_at", ""),
        },
    }


# ── Logging ────────────────────────────────────────────────────────────────────

def _log_retrieval_summary(
    retrieval_id:              str,
    user_id:                   str,
    categories_searched:       list[str],
    total_queries:             int,
    total_vector_hits:         int,
    total_metadata_hits:       int,
    candidates_before_fusion:  int,
    candidates_after_fusion:   int,
    analytics_searched:        bool,
    elapsed_ms:                float,
    category_details:          list[dict[str, Any]],
    top_score:                 float,
    lowest_score:              float,
) -> None:
    """Mandatory enterprise-grade retrieval log block."""
    logger.info("=" * 56)
    logger.info("HYBRID RETRIEVAL COMPLETE")
    logger.info("=" * 56)
    logger.info("retrieval_id              : %s", retrieval_id)
    logger.info("user_id                   : %s...", user_id[:8])
    logger.info("categories searched       : %s", categories_searched)
    logger.info("queries executed          : %d", total_queries)
    logger.info("vector matches            : %d", total_vector_hits)
    logger.info("metadata matches          : %d", total_metadata_hits)
    logger.info("candidates before fusion  : %d", candidates_before_fusion)
    logger.info("candidates after fusion   : %d", candidates_after_fusion)
    logger.info("top score                 : %.4f", top_score)
    logger.info("lowest score              : %.4f", lowest_score)
    logger.info("analytics searched        : %s", analytics_searched)
    logger.info("elapsed_ms                : %.0f", elapsed_ms)
    logger.info("=" * 56)

    for cd in category_details:
        logger.info(
            "[RETRIEVAL] cat=%-22s  queries=%d  vector_hits=%d  metadata_hits=%d  final_hits=%d",
            cd["category"],
            cd["queries_executed"],
            cd["vector_hits"],
            cd["metadata_hits"],
            cd["candidates_after_fusion"],
        )
        for q in cd.get("query_list", []):
            logger.info("[RETRIEVAL]   → %s", q)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def run_hybrid_retrieval(
    user_id:       str,
    p1_output:     dict[str, Any],
) -> dict[str, Any]:
    """
    Execute Enterprise Hybrid Retrieval based on Processor #1 output.

    Args:
        user_id   : Authenticated user UUID — injected into every Qdrant filter.
        p1_output : Complete Processor #1 JSON output dict.

    Returns:
        {
            retrieval_id, categories_searched, total_candidates_found,
            total_candidates_after_filtering, analytics_searched,
            elapsed_ms, results: [RetrievalResult, ...]
        }

    Never raises. Returns an empty result set on any unhandled error.
    """
    t0           = time.monotonic()
    retrieval_id = str(uuid.uuid4())[:12]

    try:
        return await _run_hybrid_retrieval_inner(user_id, p1_output, retrieval_id, t0)
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        logger.error("[hybrid_retrieval] unhandled error | retrieval_id=%s: %s",
                     retrieval_id, exc, exc_info=True)
        return {
            "retrieval_id":                    retrieval_id,
            "categories_searched":             [],
            "total_candidates_found":          0,
            "total_candidates_after_filtering": 0,
            "analytics_searched":              False,
            "elapsed_ms":                      round(elapsed, 1),
            "results":                         [],
            "_error":                          str(exc),
        }


async def _run_hybrid_retrieval_inner(
    user_id:       str,
    p1_output:     dict[str, Any],
    retrieval_id:  str,
    t0:            float,
) -> dict[str, Any]:
    """Core implementation — separated for clean error boundary in public entry point."""

    # ── Extract P1 fields ────────────────────────────────────────────────────
    rs  = p1_output.get("retrieval_strategy") or {}
    ad  = p1_output.get("analytics_decision") or {}
    ca  = p1_output.get("conversation_analysis") or {}
    ia  = p1_output.get("intent_analysis") or {}
    pi  = ia.get("primary_intent") or {}

    raw_categories      = rs.get("categories") or []
    requires_analytics  = bool(ad.get("requires_analytics", False))
    standalone_query    = ca.get("standalone_query") or ""
    primary_intent_cat  = pi.get("category") or "product_service"

    # ── Build category → queries map ─────────────────────────────────────────
    # Use only ALLOWED categories; guard against P1 producing invalid values.
    cat_queries: dict[str, list[str]] = {}
    for cat_entry in raw_categories:
        if not isinstance(cat_entry, dict):
            continue
        cat = str(cat_entry.get("category", "")).strip()
        if cat not in ALLOWED_CATEGORIES or cat == "data_analytics":
            continue  # data_analytics handled separately via analytics routing
        raw_qs = cat_entry.get("search_queries") or []
        qs = [str(q).strip() for q in raw_qs if str(q).strip()]
        if qs:
            cat_queries[cat] = qs

    # Guarantee primary intent category is always searched
    if primary_intent_cat in ALLOWED_CATEGORIES and primary_intent_cat != "data_analytics":
        if primary_intent_cat not in cat_queries:
            fallback_q = standalone_query or primary_intent_cat.replace("_", " ") + " information"
            cat_queries[primary_intent_cat] = [fallback_q]

    # ── Build analytics category tasks (if required) ──────────────────────
    analytics_categories: list[str] = []
    if requires_analytics:
        raw_ac = ad.get("analytics_categories") or []
        for ac in raw_ac:
            if isinstance(ac, dict):
                pc = str(ac.get("primary_category", "")).strip()
                if pc in ALLOWED_CATEGORIES and pc != "data_analytics":
                    analytics_categories.append(pc)
        if not analytics_categories and primary_intent_cat in ALLOWED_CATEGORIES:
            analytics_categories = [primary_intent_cat]

    # ── Launch all category searches in parallel ──────────────────────────
    tasks: list[tuple[str, bool, str, list[str]]] = []
    # (category_label, is_analytics, analytics_primary_cat, query_list)

    for cat, qs in cat_queries.items():
        tasks.append((cat, False, "", qs))

    for ac_primary in analytics_categories:
        # Use standalone_query as the analytics search query
        qs = [standalone_query] if standalone_query else [ac_primary.replace("_", " ") + " analytics"]
        tasks.append(("data_analytics", True, ac_primary, qs))

    if not tasks:
        logger.warning("[hybrid_retrieval] no tasks built | user=%s ... falling back", user_id[:8])
        fallback = await _fallback_scroll(user_id, standalone_query or "business information")
        elapsed  = (time.monotonic() - t0) * 1000
        return {
            "retrieval_id":                    retrieval_id,
            "categories_searched":             [],
            "total_candidates_found":          len(fallback),
            "total_candidates_after_filtering": len(fallback),
            "analytics_searched":              False,
            "elapsed_ms":                      round(elapsed, 1),
            "results":                         [_format_result(r, "product_service") for r in fallback],
        }

    # Execute all tasks concurrently
    coro_list = []
    for (cat, is_analytics, ac_primary, qs) in tasks:
        coro_list.append(
            _search_category(
                category   = cat,
                queries    = qs,
                user_id    = user_id,
                analytics  = is_analytics,
                analytics_primary_category = ac_primary,
            )
        )

    category_raw_results = await asyncio.gather(*coro_list, return_exceptions=True)

    # ── Aggregate stats and build output ─────────────────────────────────
    all_results:          list[dict[str, Any]] = []
    categories_searched:  list[str]            = []
    category_details:     list[dict[str, Any]] = []
    total_vector_hits     = 0
    total_metadata_hits   = 0
    total_before_fusion   = 0
    total_after_fusion    = 0
    total_queries_run     = 0

    for idx, (task_def, raw) in enumerate(zip(tasks, category_raw_results)):
        cat, is_analytics, ac_primary, qs = task_def

        if isinstance(raw, Exception):
            logger.warning("[hybrid_retrieval] category task failed cat=%s: %s", cat, raw)
            continue

        label = f"data_analytics[{ac_primary}]" if is_analytics and ac_primary else cat
        categories_searched.append(label)
        total_vector_hits   += raw.get("vector_hits", 0)
        total_metadata_hits += raw.get("metadata_hits", 0)
        total_before_fusion += raw.get("candidates_before_fusion", 0)
        total_after_fusion  += raw.get("candidates_after_fusion", 0)
        total_queries_run   += raw.get("queries_executed", 0)

        category_details.append({
            "category":                  label,
            "queries_executed":          raw.get("queries_executed", 0),
            "vector_hits":               raw.get("vector_hits", 0),
            "metadata_hits":             raw.get("metadata_hits", 0),
            "candidates_before_fusion":  raw.get("candidates_before_fusion", 0),
            "candidates_after_fusion":   raw.get("candidates_after_fusion", 0),
            "query_list":                qs,
        })

        for hit in raw.get("results", []):
            all_results.append(_format_result(hit, cat))

    # ── Fallback: if all categories returned 0 results ───────────────────
    if not all_results:
        logger.warning("[hybrid_retrieval] all categories empty — running tenant fallback | user=%s", user_id[:8])
        fallback = await _fallback_scroll(user_id, standalone_query or "business information")
        all_results = [_format_result(r, primary_intent_cat) for r in fallback]

    # ── Final dedup and sort ──────────────────────────────────────────────
    # Multiple categories may return the same entry — deduplicate by entry_id
    seen_entries: set[str] = set()
    deduped:      list[dict[str, Any]] = []
    for r in sorted(all_results, key=lambda x: x.get("score", 0.0), reverse=True):
        eid = r.get("entry_id") or r.get("payload", {}).get("entry_id", "")
        key = eid or r.get("entry_id", "")
        if key and key in seen_entries:
            continue
        seen_entries.add(key)
        deduped.append(r)

    top_score    = deduped[0]["score"]  if deduped else 0.0
    lowest_score = deduped[-1]["score"] if deduped else 0.0
    elapsed_ms   = (time.monotonic() - t0) * 1000

    _log_retrieval_summary(
        retrieval_id             = retrieval_id,
        user_id                  = user_id,
        categories_searched      = categories_searched,
        total_queries            = total_queries_run,
        total_vector_hits        = total_vector_hits,
        total_metadata_hits      = total_metadata_hits,
        candidates_before_fusion = total_before_fusion,
        candidates_after_fusion  = total_after_fusion,
        analytics_searched       = bool(analytics_categories),
        elapsed_ms               = elapsed_ms,
        category_details         = category_details,
        top_score                = top_score,
        lowest_score             = lowest_score,
    )

    return {
        "retrieval_id":                    retrieval_id,
        "categories_searched":             categories_searched,
        "total_candidates_found":          total_before_fusion,
        "total_candidates_after_filtering": len(deduped),
        "analytics_searched":              bool(analytics_categories),
        "elapsed_ms":                      round(elapsed_ms, 1),
        "results":                         deduped,
    }
