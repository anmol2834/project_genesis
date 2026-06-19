"""
automationservice — Enterprise Hybrid Retrieval Engine
=======================================================
Collection  : user_data_entries
Model       : BAAI/bge-m3  (1024-dim, Cosine)
Architecture: Dense (vector) + Metadata (scroll/filter) fusion

Multi-tenancy contract:
    EVERY search call includes payload.user_id == user_id.
    Cross-tenant access is structurally impossible.

Pipeline position:
    Processor #1 output  →  THIS MODULE  →  Reranker  →  Processor #2

Phases:
    1. Category filter build  — strict per-category Qdrant filters
    2. Analytics routing      — category=<real> + subtype=data_analytics filter
                                (NOT a separate "data_analytics" category)
    3. Dense retrieval        — BAAI/bge-m3 (no prefix), top-K=20 per query
    4. Metadata retrieval     — scroll with keyword/attribute/value matching
    5. Parallel execution     — asyncio.gather() across all category × query pairs
    6. Score fusion           — vector + metadata + quality + priority weighted sum
    7. Result limiting        — top-20 per category → top-10 after fusion

Analytics storage pattern (user-service analytics_engine.py):
    category  = <real category>   e.g. "product_service"
    subtype   = "data_analytics"
    attributes.primary_category = <same real category>

    "data_analytics" is a SUBTYPE, NOT a category.
    Analytics records live inside their real category bucket.
    _build_analytics_subtype_filter correctly targets them.

Prefix contract (must match user-service embedding_service.py):
    BAAI/bge-m3 does NOT use instruction prefixes.
    Both storage (user-service) and query (automationservice) pass text as-is.
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
VECTOR_SIZE     = 1024

# Stable model cache — same path as user-service model_singleton so both
# services share a single on-disk download.
_THIS_DIR        = os.path.dirname(os.path.abspath(__file__))      # .../services
_SVC_DIR         = os.path.dirname(_THIS_DIR)                      # .../automationservice
_SERVICES_DIR_AS = os.path.dirname(_SVC_DIR)                       # .../services
_SERVER_DIR_AS   = os.path.dirname(_SERVICES_DIR_AS)               # .../server
_MODEL_CACHE_DIR = os.path.join(_SERVER_DIR_AS, ".model_cache")
os.makedirs(_MODEL_CACHE_DIR, exist_ok=True)

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
# NOTE: "data_analytics" is NOT a category — it is a SUBTYPE.
# Analytics records are stored as: category=<real> + subtype=data_analytics
# The retrieval layer uses _build_analytics_subtype_filter for analytics queries.
ALLOWED_CATEGORIES = frozenset({
    "product_service",
    "offers_promotions",
    "delivery_shipping",
    "company_info",
    "educational_content",
    "contact_support",
    "policies_legal",
    "issue_resolution",
})

# ── Lazy singletons ────────────────────────────────────────────────────────────

_embed_model        = None
_qdrant_client      = None
_embed_model_lock   = None   # created once at first access (avoids import-time threading import)


# ── Model & client access ──────────────────────────────────────────────────────

def _get_embed_model():
    """
    Lazy-load BAAI/bge-m3 singleton.

    Thread-safety: module-level lock created on first call (not inside the
    guarded block) so double-checked locking actually works correctly.
    Without a stable lock reference, concurrent threads each create a new lock
    object and race past the outer `if _embed_model is None` check — causing
    multiple model loads. The lock must be created BEFORE the first guard check.

    Identical to user-service model_singleton — same model, same dimension,
    guarantees query/passage vector space alignment.
    """
    global _embed_model, _embed_model_lock
    import threading

    if _embed_model_lock is None:
        _embed_model_lock = threading.Lock()

    if _embed_model is None:
        with _embed_model_lock:
            if _embed_model is None:
                from sentence_transformers import SentenceTransformer
                import logging as _log
                _log.getLogger("sentence_transformers").setLevel(_log.ERROR)
                _embed_model = SentenceTransformer(
                    "BAAI/bge-m3",
                    cache_folder=_MODEL_CACHE_DIR,
                )
                _log.getLogger("sentence_transformers").setLevel(_log.INFO)
                logger.info("automationservice: BAAI/bge-m3 loaded (1024-dim)")
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
    Embed a single retrieval query using BAAI/bge-m3.

    BGE-M3 does NOT require instruction prefixes — text is passed as-is.
    This matches the storage encoding in user-service/embedding_service.py.
    """
    model    = _get_embed_model()
    vector   = model.encode(query.strip()[:512], normalize_embeddings=True)
    return vector.tolist()


async def warmup() -> None:
    """
    Pre-warm the BAAI/bge-m3 model and Qdrant client at service startup.

    Without pre-warming, the first real request incurs ~30s cold-start latency
    (model load + JIT compilation). After warmup, each embed call takes ~50ms.

    Called from main.py lifespan() before the notify loop starts.
    Runs in a thread pool to avoid blocking the event loop.
    Non-fatal: startup continues even if warmup fails.
    """
    def _run() -> None:
        try:
            model = _get_embed_model()
            model.encode("warmup", normalize_embeddings=True)
            logger.info("automationservice: BAAI/bge-m3 warmup complete")
        except Exception as exc:
            logger.warning("automationservice: BAAI/bge-m3 warmup failed (non-fatal): %s", exc)
        try:
            _get_qdrant_client()
            logger.info("automationservice: Qdrant client warmup complete")
        except Exception as exc:
            logger.warning("automationservice: Qdrant client warmup failed (non-fatal): %s", exc)

    await asyncio.to_thread(_run)


# ── Filter builders ────────────────────────────────────────────────────────────

def _build_category_filter(user_id: str, category: str):
    """
    Build a strict Qdrant Filter for tenant-scoped category search.

    This filter is used for NORMAL (operational) record retrieval only.
    Analytics subtype records (subtype=data_analytics) are NOT included —
    they are handled separately by _build_analytics_subtype_filter.

    Mandatory conditions:
        user_id  == user_id    (multi-tenancy isolation — NON-NEGOTIABLE)
        category == category   (category isolation — reduces noise)

    For offers_promotions: additionally filters status == "active" at vector
    search time to exclude inactive/scheduled offers before scoring.
    """
    # Delegate to the new explicit normal-category filter
    return _build_normal_category_filter(user_id, category)


def _build_analytics_subtype_filter(user_id: str, category: str):
    """
    Build a Qdrant filter for analytics subtype records within a real category.

    CORRECT analytics storage pattern (from user-service analytics_engine.py):
        category  = <real category>   e.g. "product_service"
        subtype   = "data_analytics"
        attributes.primary_category = <same real category>

    This is the FIXED filter that replaces the old broken _build_analytics_filter
    which incorrectly searched for category="data_analytics" (a non-existent category).

    Mandatory conditions:
        user_id  == user_id           (multi-tenancy isolation)
        category == <real category>   (e.g. "product_service")
        subtype  == "data_analytics"  (analytics subtype marker)
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    return Filter(must=[
        FieldCondition(key="user_id",  match=MatchValue(value=user_id)),
        FieldCondition(key="category", match=MatchValue(value=category)),
        FieldCondition(key="subtype",  match=MatchValue(value="data_analytics")),
    ])


def _build_normal_category_filter(user_id: str, category: str):
    """
    Build a Qdrant filter for NORMAL (non-analytics) records within a category.

    Excludes analytics subtype records — only returns operational data entries
    (actual products, actual offers, actual policies, etc.).

    Used for the operational retrieval pass that runs alongside analytics retrieval.
    The retrieval layer runs BOTH analytics + normal passes when analytics is needed,
    sending both result sets to the reranker which picks the most relevant chunks.

    Mandatory conditions:
        user_id  == user_id           (multi-tenancy isolation)
        category == <real category>   (category isolation)
        subtype  != "data_analytics"  (exclude analytics summaries)

    Note for offers: additionally filters status == "active" to exclude
    inactive/scheduled/expired offers at the Qdrant filter level.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue, IsNullCondition, IsEmptyCondition
    conditions = [
        FieldCondition(key="user_id",  match=MatchValue(value=user_id)),
        FieldCondition(key="category", match=MatchValue(value=category)),
    ]
    # Exclude analytics subtype entries — use must_not to filter out data_analytics subtype
    # We do this by NOT matching subtype=data_analytics via a must_not condition
    must_not_conditions = [
        FieldCondition(key="subtype", match=MatchValue(value="data_analytics")),
    ]
    # For offers, also filter to active only
    if category == "offers_promotions":
        conditions.append(
            FieldCondition(key="status", match=MatchValue(value="active"))
        )
    return Filter(must=conditions, must_not=must_not_conditions)


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
    """
    Vector search scoped to analytics subtype within a real category.

    Uses _build_analytics_subtype_filter: category=<primary_category> + subtype=data_analytics.
    This correctly targets the analytics intelligence layer stored alongside
    operational records — NOT a separate "data_analytics" category.
    """
    def _run() -> list[dict]:
        client  = _get_qdrant_client()
        vector  = _embed_query(query)
        f       = _build_analytics_subtype_filter(user_id, primary_category)
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

def _metadata_score(payload: dict[str, Any], query_tokens: frozenset[str], escalation_boost: bool = False) -> float:
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

    # Escalation boost (Fix 5): prioritize senior/manager/escalation contacts.
    # Uses the same enterprise ESCALATION_TRIGGER_WORDS from prompts.py for
    # consistency with processor_1.py pre-flight detection.
    if escalation_boost:
        try:
            import sys, os
            _llm_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "llm")
            if _llm_dir not in sys.path:
                sys.path.insert(0, _llm_dir)
            from prompts import ESCALATION_TRIGGER_WORDS as _ESC_TRIGGERS
        except ImportError:
            _ESC_TRIGGERS = frozenset({
                "senior", "manager", "escalation", "head", "director",
                "supervisor", "lead", "specialist", "vip", "priority",
                "dedicated", "representative", "customer success",
                "live agent", "real person", "complaint team",
            })
        all_text = (
            str(payload.get("title", "")) + " " +
            str(payload.get("search_text", "")) + " " +
            " ".join(str(v) for v in _json_values(payload.get("attributes") or {}))
        ).lower()
        if any(trigger in all_text for trigger in _ESC_TRIGGERS):
            score = min(score + 0.30, 1.0)

    return min(score, 1.0)


async def _metadata_search(
    query: str,
    user_id: str,
    category: str,
    top_k: int = METADATA_TOP_K,
    escalation_boost: bool = False,
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
            if not _is_offer_valid(payload):   # Fix 6: skip invalid offers
                continue
            ms = _metadata_score(payload, q_tokens, escalation_boost)
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
    """
    Metadata scroll for analytics subtype records within a real category.

    Uses _build_analytics_subtype_filter: category=<primary_category> + subtype=data_analytics.
    This is the correct approach — analytics records are co-located with their
    real category, not stored under a separate "data_analytics" category.
    """
    def _run() -> list[dict]:
        client  = _get_qdrant_client()
        f       = _build_analytics_subtype_filter(user_id, primary_category)
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


# ── Score normalization ────────────────────────────────────────────────────────

def _normalize_scores(fused: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Apply min-max normalization to spread fusion scores across [0.20, 1.00].

    Without normalization, fusion scores cluster tightly (e.g. 0.67–0.68)
    making it impossible to distinguish best from weakest results.

    After normalization:
        best result  → 1.00
        worst result → 0.20
        others       → linearly spread between

    Preserves the relative ranking. Only changes the absolute values.
    Skips normalization if all scores are identical (avoids div-by-zero).
    """
    if len(fused) <= 1:
        return fused
    scores = [r["score"] for r in fused]
    min_s, max_s = min(scores), max(scores)
    if max_s - min_s < 1e-6:
        return fused   # all identical — nothing to spread

    OUT_MIN, OUT_MAX = 0.20, 1.00
    spread    = OUT_MAX - OUT_MIN
    raw_spread = max_s - min_s

    for r in fused:
        normalized = OUT_MIN + ((r["score"] - min_s) / raw_spread) * spread
        r["score"] = round(normalized, 4)
    return fused


# ── Offer validity filter (Fix 6) ─────────────────────────────────────────────

def _is_offer_valid(payload: dict[str, Any]) -> bool:
    """
    Check if an offer/promotion is currently valid.

    Rules:
        1. status must be "active" (case-insensitive) — excludes "scheduled",
           "inactive", "expired"
        2. valid_until (if present) must be >= today

    Applied ONLY to offers_promotions category.
    For all other categories, always returns True.

    Date format support: DD-MM-YYYY, MM/DD/YYYY, YYYY-MM-DD (ISO), DD/MM/YYYY
    """
    import datetime as _dt

    category = str(payload.get("category", "")).lower()
    if category != "offers_promotions":
        return True

    # Check status
    attrs  = payload.get("attributes") or {}
    sd     = payload.get("structured_data") or {}
    status = str(attrs.get("status") or sd.get("status") or "active").lower().strip()

    if status not in ("active", ""):
        return False   # scheduled, inactive, expired, paused → exclude

    # Check valid_until date
    valid_until_raw = str(
        attrs.get("valid_until") or sd.get("end_date") or sd.get("valid_until") or ""
    ).strip()
    if not valid_until_raw:
        return True   # no date — assume active

    today = _dt.date.today()

    # Try multiple date formats
    for fmt in ("%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            expiry = _dt.datetime.strptime(valid_until_raw, fmt).date()
            return expiry >= today
        except ValueError:
            continue

    # If date can't be parsed — include it (don't wrongly exclude)
    return True


# ── Diversity score (Fix 8) ────────────────────────────────────────────────────

def _compute_diversity_score(results: list[dict[str, Any]]) -> float:
    """
    Measure retrieval diversity: what fraction of returned results have
    DIFFERENT categories. A diverse result set = 1.0, all same category = 0.0.
    """
    if len(results) < 2:
        return 1.0
    cats = [r.get("category", "") for r in results]
    unique_cats = len(set(cats))
    return round((unique_cats - 1) / max(len(cats) - 1, 1), 3)


# ── Per-category search ────────────────────────────────────────────────────────

async def _search_category(
    category:  str,
    queries:   list[str],
    user_id:   str,
    analytics: bool = False,
    analytics_primary_category: str = "",
    escalation_boost: bool = False,
) -> dict[str, Any]:
    """
    Execute all queries for a single category in parallel (dense + metadata).

    Dual-mode operation:
      Normal mode  (analytics=False):
        Searches category=<category> with subtype != data_analytics.
        Returns operational records (actual products, offers, policies, etc.)

      Analytics mode (analytics=True):
        Searches category=<analytics_primary_category> with subtype=data_analytics.
        Returns business intelligence summaries (counts, distributions, price ranges).
        analytics_primary_category is the REAL category (e.g. "product_service").

    Returns:
        {
            category, queries_executed, vector_hits, metadata_hits,
            candidates_before_fusion, candidates_after_fusion, results
        }
    """
    if analytics:
        # Analytics routing: use analytics subtype filter
        # category=<analytics_primary_category> + subtype=data_analytics
        tasks = []
        for q in queries:
            tasks.append(_analytics_dense_search(q, user_id, analytics_primary_category))
            tasks.append(_analytics_metadata_search(q, user_id, analytics_primary_category))
    else:
        tasks = []
        for q in queries:
            tasks.append(_dense_search(q, user_id, category))
            tasks.append(_metadata_search(q, user_id, category, escalation_boost=escalation_boost))

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
    fused = _normalize_scores(fused)   # Fix 3: spread scores across [0.20, 1.00]
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
    # Use only ALLOWED categories. "data_analytics" is now a subtype, not a
    # category — it will never appear in cat_queries from P1 output since it
    # was removed from ALLOWED_CATEGORIES.
    cat_queries: dict[str, list[str]] = {}
    for cat_entry in raw_categories:
        if not isinstance(cat_entry, dict):
            continue
        cat = str(cat_entry.get("category", "")).strip()
        if cat not in ALLOWED_CATEGORIES:
            continue
        raw_qs = cat_entry.get("search_queries") or []
        qs = [str(q).strip() for q in raw_qs if str(q).strip()]
        if qs:
            cat_queries[cat] = qs

    # Guarantee primary intent category is always searched
    if primary_intent_cat in ALLOWED_CATEGORIES:
        if primary_intent_cat not in cat_queries:
            fallback_q = standalone_query or primary_intent_cat.replace("_", " ") + " information"
            cat_queries[primary_intent_cat] = [fallback_q]

    # ── Build analytics category tasks (if required) ──────────────────────
    # analytics_categories contains REAL category names (e.g. "product_service").
    # The retrieval layer will search category=<real> + subtype=data_analytics.
    analytics_categories: list[str] = []
    if requires_analytics:
        raw_ac = ad.get("analytics_categories") or []
        for ac in raw_ac:
            if isinstance(ac, dict):
                pc = str(ac.get("primary_category", "")).strip()
                if pc in ALLOWED_CATEGORIES:
                    analytics_categories.append(pc)
        if not analytics_categories and primary_intent_cat in ALLOWED_CATEGORIES:
            analytics_categories = [primary_intent_cat]

    # ── Launch all category searches in parallel ──────────────────────────
    tasks: list[tuple[str, bool, str, list[str], bool]] = []
    # (category_label, is_analytics, analytics_primary_cat, query_list, escalation_boost)

    # Fix 5: Detect if this is an escalation search
    open_esc = p1_output.get("open_escalation", {})
    is_escalation_search = (
        open_esc.get("open", False) or
        (pi.get("category") == "contact_support" and
         p1_output.get("routing_decision", {}).get("escalation_requested", False))
    )

    for cat, qs in cat_queries.items():
        boost = is_escalation_search and cat == "contact_support"
        tasks.append((cat, False, "", qs, boost))

    for ac_primary in analytics_categories:
        # Analytics search: category=<ac_primary> + subtype=data_analytics
        # Use standalone_query enriched with "analytics summary" context for
        # better vector alignment with analytics subtype documents.
        qs = [standalone_query] if standalone_query else [ac_primary.replace("_", " ") + " analytics summary"]
        # Task tuple: (category_label, is_analytics, analytics_primary_cat, query_list, escalation_boost)
        # category_label is the real category for display/logging purposes.
        tasks.append((ac_primary, True, ac_primary, qs, False))

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
    for (cat, is_analytics, ac_primary, qs, boost) in tasks:
        coro_list.append(
            _search_category(
                category   = cat,
                queries    = qs,
                user_id    = user_id,
                analytics  = is_analytics,
                analytics_primary_category = ac_primary,
                escalation_boost           = boost,
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
        cat, is_analytics, ac_primary, qs, boost = task_def

        if isinstance(raw, Exception):
            logger.warning("[hybrid_retrieval] category task failed cat=%s: %s", cat, raw)
            continue

        # Label format: "product_service[analytics]" for analytics tasks, "product_service" for normal.
        # This makes the log clear about what kind of retrieval ran per category.
        label = f"{ac_primary}[analytics]" if is_analytics and ac_primary else cat
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

    # Fix 6: Filter out invalid offers from final results
    deduped = [r for r in deduped if _is_offer_valid(r.get("payload", {}))]

    # Fix 3: Normalize scores across all categories for meaningful ranking
    deduped = _normalize_scores(deduped)

    top_score    = deduped[0]["score"]  if deduped else 0.0
    lowest_score = deduped[-1]["score"] if deduped else 0.0
    elapsed_ms   = (time.monotonic() - t0) * 1000

    # Fix 8: Compute retrieval diversity score
    diversity_score = _compute_diversity_score(deduped)

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

    # ── Per-result visibility log (for review) ────────────────────────────
    for rank, result in enumerate(deduped, start=1):
        p        = result.get("payload", {})
        sd       = p.get("structured_data") or {}
        attrs    = p.get("attributes") or {}
        tags     = p.get("ai_tags") or []
        kws      = p.get("keywords") or []
        cat      = result.get("category", "?")
        subtype  = result.get("subtype", "") or ""
        cat_label = f"{cat}/{subtype}" if subtype else cat

        logger.info(
            "[RESULT #%d]  score=%.4f  v=%.4f  m=%.4f  q=%.1f  cat=%-28s  title=%s",
            rank,
            result.get("score", 0.0),
            result.get("vector_score", 0.0),
            result.get("metadata_score", 0.0),
            float(p.get("quality_score", 0.0)),
            cat_label,
            result.get("title", "?"),
        )
        if sd:
            # Show structured_data key:value pairs (truncated for readability)
            sd_preview = "  |  ".join(
                f"{k}: {str(v)[:80]}" for k, v in list(sd.items())[:8]
            )
            logger.info("           structured_data  → %s", sd_preview)
        if attrs:
            attr_preview = "  |  ".join(
                f"{k}: {str(v)[:60]}" for k, v in list(attrs.items())[:6]
                if k not in ("source_id", "priority_score")
            )
            if attr_preview:
                logger.info("           attributes      → %s", attr_preview)
        if tags:
            logger.info("           ai_tags         → %s", ", ".join(str(t) for t in tags[:8]))
        if kws:
            logger.info("           keywords        → %s", ", ".join(str(k) for k in kws[:10]))
        search_text = result.get("search_text", "") or p.get("search_text", "")
        if search_text:
            logger.info("           search_text     → %s", search_text[:160])

    return {
        "retrieval_id":                    retrieval_id,
        "categories_searched":             categories_searched,
        "total_candidates_found":          total_before_fusion,
        "total_candidates_after_filtering": len(deduped),
        "analytics_searched":              bool(analytics_categories),
        "elapsed_ms":                      round(elapsed_ms, 1),
        "results":                         deduped,
        "retrieval_diversity_score":       diversity_score,   # Fix 8
    }
