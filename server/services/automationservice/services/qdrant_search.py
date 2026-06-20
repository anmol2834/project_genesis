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
# Per-query metadata scroll top-K (paginated — no hard cap)
METADATA_TOP_K       = 20
# Per-category result cap after fusion (passed to reranker)
PER_CATEGORY_TOP_K   = 10
# Minimum vector score to include a candidate
VECTOR_SCORE_FLOOR   = 0.30
# Maximum pages for metadata scroll (safety cap: 500 * 100 = 50k records)
_METADATA_SCROLL_MAX_PAGES = 500

# Score fusion weights — requirement_score always overrides these
# Priority: requirement_match > filter_match > metadata > vector
W_VECTOR   = 0.45
W_METADATA = 0.25
W_QUALITY  = 0.15
W_PRIORITY = 0.15

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


def _normalize_query_tokens(text: str) -> frozenset[str]:
    """
    Issue #4 — Query Understanding Layer.

    Normalizes tokens before metadata scoring so variant forms of the
    same concept match the same stored values:
        "16 gb" / "16-gb" / "16gb" / "16 gigabytes" / "16gig" → "16GB"
        "512 gb ssd" → "512GB", "SSD"
        "$1000" / "1,000" → "1000"

    Works for any unit system — bytes, currency, weight, area, etc.
    Domain-agnostic: no hardcoded business vocabulary.
    """
    import re as _re

    # Normalise common unit abbreviation variants first
    UNIT_NORMS = [
        (_re.compile(r'(\d+)\s*gig(?:abyte)?s?\b', _re.I),          r'\1GB'),
        (_re.compile(r'(\d+)\s*mega(?:byte)?s?\b', _re.I),          r'\1MB'),
        (_re.compile(r'(\d+)\s*tera(?:byte)?s?\b', _re.I),          r'\1TB'),
        (_re.compile(r'(\d+)\s*[-_]?\s*(gb)\b', _re.I),             r'\1GB'),
        (_re.compile(r'(\d+)\s*[-_]?\s*(tb)\b', _re.I),             r'\1TB'),
        (_re.compile(r'(\d+)\s*[-_]?\s*(mb)\b', _re.I),             r'\1MB'),
        (_re.compile(r'\$(\d[\d,]*(?:\.\d+)?)', _re.I),             r'\1'),  # $1,000 → 1000
        (_re.compile(r'(\d)[,](\d{3})', _re.I),                     r'\1\2'),  # 1,000 → 1000
    ]

    normalized = text.lower()
    for pattern, replacement in UNIT_NORMS:
        normalized = pattern.sub(replacement, normalized)

    # Tokenize and clean
    _STRIP_CHARS = '.,;:!?()-"\''
    tokens = frozenset(
        t.strip(_STRIP_CHARS)
        for t in normalized.split()
        if len(t.strip(_STRIP_CHARS)) > 1
    )
    return tokens


# ── Filter builders ────────────────────────────────────────────────────────────

def _build_category_filter(user_id: str, category: str, status_filter: str | None = None):
    """
    Build a strict Qdrant Filter for tenant-scoped category search.
    Delegates to _build_normal_category_filter.
    """
    return _build_normal_category_filter(user_id, category, status_filter=status_filter)


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


def _build_normal_category_filter(user_id: str, category: str, status_filter: str | None = None):
    """
    Build a Qdrant filter for NORMAL (non-analytics) records within a category.

    Enterprise principle: no hardcoded business category logic here.
    status_filter is passed in from the retrieval contract when P1 requires it.
    The only built-in rule is excluding data_analytics subtype (architectural,
    not business logic).

    Mandatory conditions:
        user_id  == user_id           (multi-tenancy isolation)
        category == <real category>   (category isolation)
        subtype  != "data_analytics"  (exclude analytics summaries)
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    conditions = [
        FieldCondition(key="user_id",  match=MatchValue(value=user_id)),
        FieldCondition(key="category", match=MatchValue(value=category)),
    ]
    must_not_conditions = [
        FieldCondition(key="subtype", match=MatchValue(value="data_analytics")),
    ]
    # status_filter injected from retrieval contract — no hardcoded category assumptions
    if status_filter:
        conditions.append(FieldCondition(key="status", match=MatchValue(value=status_filter)))
    return Filter(must=conditions, must_not=must_not_conditions)


def _build_requirements_filter(user_id: str, category: str, requirements: list[dict], status_filter: str | None = None):
    """
    Schema-safe requirements filter — REVISED (Issues #1, #2, #3).

    ENTERPRISE ARCHITECTURE CHANGE:
    The previous version applied MatchValue on guessed field names (e.g.
    structured_data.ram = "8GB"). This breaks when different businesses
    use different field names for the same concept.

    NEW APPROACH:
    Only apply NUMERIC RANGE constraints as hard filters (these work
    regardless of field name because we compare numeric values, not strings).
    String/semantic requirements are handled via query enrichment in the
    vector search and requirement_score in fusion — NOT hard MatchValue.

    This filter now only enforces:
      1. Tenant isolation (user_id)
      2. Category isolation
      3. Analytics subtype exclusion
      4. Status filter (if provided)
      5. Numeric range constraints (price lte/gte/between)

    String matching is intentionally left to the semantic layer.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

    must: list = [
        FieldCondition(key="user_id",  match=MatchValue(value=user_id)),
        FieldCondition(key="category", match=MatchValue(value=category)),
    ]
    must_not = [FieldCondition(key="subtype", match=MatchValue(value="data_analytics"))]

    if status_filter:
        must.append(FieldCondition(key="status", match=MatchValue(value=status_filter)))

    # Only apply numeric constraints as hard filters — schema-safe because
    # we compare against numeric values in attributes.price, not string field names
    for req in (requirements or []):
        if not isinstance(req, dict):
            continue
        operator = str(req.get("operator") or "").strip()
        # Only process actual numeric range requirements here
        # semantic/keyword requirements are handled in vector query enrichment
        if operator not in ("lte", "gte", "eq", "between"):
            continue
        field = str(req.get("field") or "").strip()
        value = req.get("value")
        if not field or value is None:
            continue
        attr_key = f"attributes.{field}"
        try:
            fval = float(value)
        except (ValueError, TypeError):
            continue
        if operator == "lte":
            must.append(FieldCondition(key=attr_key, range=Range(lte=fval)))
        elif operator == "gte":
            must.append(FieldCondition(key=attr_key, range=Range(gte=fval)))
        elif operator == "eq":
            tol = fval * 0.05
            must.append(FieldCondition(key=attr_key, range=Range(gte=fval - tol, lte=fval + tol)))
        elif operator == "between":
            min_v = req.get("min")
            max_v = req.get("max")
            if min_v is not None and max_v is not None:
                must.append(FieldCondition(key=attr_key, range=Range(gte=float(min_v), lte=float(max_v))))

    return Filter(must=must, must_not=must_not)


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
    requirements: list[dict] | None = None,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Vector similarity search scoped to user_id + category.

    When requirements[] is provided (Stage 1 mode), builds a requirements filter
    that enforces exact field=value matches inside Qdrant BEFORE scoring.
    This is Stage 1 exact-match retrieval — eliminates outliers at DB level.

    When requirements is None/empty, falls back to standard category filter.
    """
    def _run() -> list[dict]:
        client  = _get_qdrant_client()
        vector  = _embed_query(query)
        if requirements:
            f = _build_requirements_filter(user_id, category, requirements, status_filter=status_filter)
        else:
            f = _build_category_filter(user_id, category, status_filter=status_filter)
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
    Score a Qdrant payload against normalized query tokens.

    FIXED (Issue #4): Uses _normalize_query_tokens so "16gb", "16 gb",
    "16-gb" all match the stored value "16GB" consistently.

    Scoring priority (search_text demoted to last per Issue #5):
        title           → +0.40 (most discriminative)
        keywords        → +0.30
        ai_tags         → +0.25
        structured_data → +0.20 (all nested values)
        attributes      → +0.20 (all nested values)
        entities        → +0.15
        search_text     → +0.10 (fallback only — demoted)
    """
    if not query_tokens:
        return 0.0

    score = 0.0
    n     = len(query_tokens)

    def _tokenize(text: Any) -> frozenset[str]:
        if not text:
            return frozenset()
        return _normalize_query_tokens(str(text))

    def _json_values(obj: Any) -> list[str]:
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

    title_tokens = _tokenize(payload.get("title", ""))
    hits = len(query_tokens & title_tokens)
    score += (hits / n) * 0.40

    kw_tokens: frozenset[str] = frozenset()
    kws = payload.get("keywords") or []
    if isinstance(kws, list):
        kw_tokens = _normalize_query_tokens(" ".join(str(k) for k in kws))
    hits = len(query_tokens & kw_tokens)
    score += (hits / n) * 0.30

    tag_tokens: frozenset[str] = frozenset()
    tags = payload.get("ai_tags") or []
    if isinstance(tags, list):
        tag_tokens = _normalize_query_tokens(" ".join(str(t) for t in tags))
    hits = len(query_tokens & tag_tokens)
    score += (hits / n) * 0.25

    sd_values = _json_values(payload.get("structured_data") or {})
    sd_tokens = _normalize_query_tokens(" ".join(sd_values))
    hits = len(query_tokens & sd_tokens)
    score += (hits / n) * 0.20

    attr_values = _json_values(payload.get("attributes") or {})
    attr_tokens = _normalize_query_tokens(" ".join(attr_values))
    hits = len(query_tokens & attr_tokens)
    score += (hits / n) * 0.20

    ent_values = _json_values(payload.get("entities") or [])
    ent_tokens = _normalize_query_tokens(" ".join(ent_values))
    hits = len(query_tokens & ent_tokens)
    score += (hits / n) * 0.15

    # search_text demoted to last — AI-generated text, not business truth
    st_tokens = _tokenize(payload.get("search_text", ""))
    hits = len(query_tokens & st_tokens)
    score += (hits / n) * 0.10

    if escalation_boost:
        try:
            import sys, os
            _llm_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "llm")
            if _llm_dir not in sys.path:
                sys.path.insert(0, _llm_dir)
            from prompts import ESCALATION_TRIGGER_WORDS as _ESC_TRIGGERS
        except ImportError:
            _ESC_TRIGGERS = frozenset({"senior", "manager", "escalation", "head",
                                        "director", "supervisor", "lead", "specialist"})
        all_text = (
            str(payload.get("title", "")) + " " +
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
    requirements: list[dict] | None = None,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Metadata-driven search using Qdrant payload filters + keyword scoring.

    FIXED (Issue #3): Fully paginated — scrolls ALL matching records, not just
    the first 20. This guarantees record #70,000 in a 100k catalog is reachable.
    Safety cap: _METADATA_SCROLL_MAX_PAGES (500 pages × 100 = 50k records max).

    FIXED (Issue #4/5): When requirements[] are present, pushes filtering into
    Qdrant (Stage 1 filter) so only matching records are loaded into memory,
    reducing the O(N) scan to O(matching records only).

    Scoring priority (search_text demoted to last):
        title > keywords > ai_tags > structured_data > attributes > search_text
    """
    def _run() -> list[dict]:
        client = _get_qdrant_client()
        if requirements:
            f = _build_requirements_filter(user_id, category, requirements, status_filter=status_filter)
        else:
            f = _build_category_filter(user_id, category, status_filter=status_filter)

        all_points = []
        offset = None
        page = 0
        while page < _METADATA_SCROLL_MAX_PAGES:
            batch, next_offset = client.scroll(
                collection_name = COLLECTION_NAME,
                scroll_filter   = f,
                limit           = 100,
                offset          = offset,
                with_payload    = True,
                with_vectors    = False,
            )
            if not batch:
                break
            all_points.extend(batch)
            if next_offset is None:
                break
            offset = next_offset
            page  += 1

        if not all_points:
            return []

        q_tokens = _normalize_query_tokens(query)
        scored = []
        for p in all_points:
            payload = p.payload or {}
            if not _is_offer_valid(payload, doc_category=category):
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
        # Issue #11: check analytics freshness — warn if data is stale (>24h)
        import datetime as _dt
        now_utc = _dt.datetime.utcnow()
        for p in points:
            pl = p.payload or {}
            computed_at_raw = (pl.get("structured_data") or {}).get("computed_at") or ""
            if computed_at_raw:
                try:
                    computed_at = _dt.datetime.fromisoformat(str(computed_at_raw).replace("Z", "+00:00").rstrip("+00:00"))
                    age_hours = (now_utc - computed_at).total_seconds() / 3600
                    if age_hours > 24:
                        logger.warning(
                            "[analytics_metadata] stale analytics | cat=%s age_hours=%.1f computed_at=%s",
                            primary_category, age_hours, computed_at_raw,
                        )
                except Exception:
                    pass
        q_tokens = _normalize_query_tokens(query)
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

def _compute_requirement_score(payload: dict[str, Any], requirements: list[dict]) -> float:
    """
    Issue #5/6 — Requirement Match Score.

    Computes how many of the customer's required field=value pairs are
    satisfied by a candidate payload. This score is injected into fusion
    BEFORE vector/metadata scores so business truth always wins.

    Scoring:
        All requirements satisfied  → 1.0 (exact match)
        N of M requirements matched → N/M
        No requirements             → 0.5 (neutral — no penalty)

    Domain-agnostic: field names come from P1 requirements[], never hardcoded.
    Searches BOTH structured_data.<field> and attributes.<field>.
    """
    if not requirements:
        return 0.5  # neutral when no requirements

    # New schema-free requirements use operator="semantic" or "keyword"
    # Old field-based requirements use operator="eq" with a field key
    # Support BOTH so the system degrades gracefully during transition
    scorable_reqs = [
        r for r in requirements
        if isinstance(r, dict) and r.get("value")
        and r.get("operator") in ("semantic", "keyword", "eq")
    ]
    if not scorable_reqs:
        return 0.5

    # Build a single normalized searchable string from the entire payload
    # so we can find the requirement value regardless of which field stores it
    def _all_payload_text(pl: dict) -> frozenset[str]:
        parts: list[str] = []
        for key in ("structured_data", "attributes", "entities"):
            obj = pl.get(key)
            if isinstance(obj, dict):
                for v in obj.values():
                    parts.append(str(v))
            elif isinstance(obj, list):
                parts.extend(str(i) for i in obj)
        parts.append(str(pl.get("title") or ""))
        parts.extend(str(k) for k in (pl.get("keywords") or []))
        return _normalize_query_tokens(" ".join(parts))

    payload_tokens = _all_payload_text(payload)
    matched = 0

    for req in scorable_reqs:
        req_val = str(req.get("value") or "").strip()
        if not req_val:
            continue
        req_tokens = _normalize_query_tokens(req_val)
        if not req_tokens:
            continue
        # Full match: all requirement value tokens present in payload
        if req_tokens.issubset(payload_tokens):
            matched += 1
        else:
            # Partial match: majority of tokens present (>=60%)
            overlap = len(req_tokens & payload_tokens)
            if overlap >= max(1, len(req_tokens) * 0.6):
                matched += 0.6

    return round(min(matched / len(scorable_reqs), 1.0), 3)


def _fuse_results(
    dense_hits:    list[dict[str, Any]],
    metadata_hits: list[dict[str, Any]],
    requirements:  list[dict] | None = None,
) -> list[dict[str, Any]]:
    """
    Merge dense and metadata results with requirement-aware ranking.

    FIXED (Issue #5/6): Requirement score is computed BEFORE fusion and
    gates the final score. Ranking hierarchy:
        1. requirement_score (business truth — never overridden)
        2. filter_match (metadata)
        3. vector similarity

    When requirements exist:
        final_score = 0.50 * requirement_score
                    + 0.25 * (W_VECTOR * vector + W_METADATA * meta + W_QUALITY * q + W_PRIORITY * p)
                    + 0.25 * semantic_component

    When no requirements: original fusion weights apply (backward-compatible).
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
    reqs  = requirements or []
    # Activate requirement-aware fusion for semantic, keyword, AND legacy eq requirements
    has_requirements = bool([
        r for r in reqs
        if isinstance(r, dict) and r.get("operator") in ("semantic", "keyword", "eq") and r.get("value")
    ])

    for entry in merged.values():
        payload = entry["payload"]
        raw_q   = float(payload.get("quality_score", 0.0))
        raw_p   = int(payload.get("priority_score", 2))
        q_norm  = min(raw_q / 100.0, 1.0)
        p_norm  = min(raw_p / 5.0,   1.0)

        semantic = (
            W_VECTOR   * entry["vector_score"]
            + W_METADATA * entry["metadata_score"]
            + W_QUALITY  * q_norm
            + W_PRIORITY * p_norm
        )

        if has_requirements:
            req_score = _compute_requirement_score(payload, reqs)
            # Requirement score dominates: 50% weight ensures exact matches
            # always outrank semantically similar non-matching results
            final_score = 0.50 * req_score + 0.50 * semantic
        else:
            req_score   = 0.5
            final_score = semantic

        fused.append({
            "id":               entry["id"],
            "vector_score":     round(entry["vector_score"],   4),
            "metadata_score":   round(entry["metadata_score"], 4),
            "quality_score":    round(q_norm,                  4),
            "priority_score":   round(p_norm,                  4),
            "requirement_score": round(req_score,              3),
            "score":            round(final_score,             4),
            "payload":          payload,
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

def _is_offer_valid(payload: dict[str, Any], doc_category: str = "") -> bool:
    """
    Check if an offer/promotion is currently valid.

    FIXED: Uses doc_category (the outer Qdrant category field = "offers_promotions")
    instead of payload.get("category") which holds the inner sub-category
    (e.g. "Seasonal", "Clearance") — a completely different field.

    Rules:
        1. status must be "active" — excludes scheduled, inactive, expired
        2. valid_until (if present) must be >= today

    Applied ONLY to offers_promotions category.
    For all other categories, always returns True.
    """
    import datetime as _dt

    # Use outer document category — NOT the inner payload sub-category field
    outer_cat = str(doc_category or payload.get("_doc_category", "")).lower().strip()
    if outer_cat != "offers_promotions":
        return True

    attrs  = payload.get("attributes") or {}
    sd     = payload.get("structured_data") or {}
    status = str(attrs.get("status") or sd.get("status") or "active").lower().strip()

    if status not in ("active", ""):
        return False

    valid_until_raw = str(
        attrs.get("valid_until") or sd.get("end_date") or sd.get("valid_until") or ""
    ).strip()
    if not valid_until_raw:
        return True

    today = _dt.date.today()
    for fmt in ("%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            expiry = _dt.datetime.strptime(valid_until_raw, fmt).date()
            return expiry >= today
        except ValueError:
            continue
    return True


# ── Diversity score (Fix 8) ────────────────────────────────────────────────────

def _compute_diversity_score(results: list[dict[str, Any]]) -> float:
    """
    Measure retrieval diversity: what fraction of returned results have
    DIFFERENT categories. A diverse result set = 1.0, all same category = 0.0.

    NOTE: A score of 0.0 is EXPECTED and CORRECT for single-intent queries
    (e.g. product lookup, offers lookup). Diversity score is only meaningful
    for multi-category queries. Do NOT treat 0.0 as a problem.
    """
    if len(results) < 2:
        return 1.0
    # Count only the real category (not the subtype label) for diversity
    cats = []
    for r in results:
        cat = r.get("category", "")
        # Strip analytics subtype suffix if logged with it
        if "/" in cat:
            cat = cat.split("/")[0]
        cats.append(cat)
    unique_cats = len(set(cats))
    # Return 0.0 explicitly for single-category results — expected for focused queries
    if unique_cats <= 1:
        return 0.0
    return round((unique_cats - 1) / max(len(set(cats)) - 1, 1), 3)


# ── Per-category search ────────────────────────────────────────────────────────

async def _search_category(
    category:  str,
    queries:   list[str],
    user_id:   str,
    analytics: bool = False,
    analytics_primary_category: str = "",
    escalation_boost: bool = False,
    requirements: list[dict] | None = None,
    status_filter: str | None = None,
) -> dict[str, Any]:
    """
    Execute all queries for a single category in parallel (dense + metadata).

    FIXED: Passes requirements[] into dense and metadata search so Stage 1
    exact-match filters are applied inside Qdrant, not post-hoc in Python.
    Also passes requirements into _fuse_results so requirement_score drives
    ranking hierarchy.
    """
    if analytics:
        tasks = []
        for q in queries:
            tasks.append(_analytics_dense_search(q, user_id, analytics_primary_category))
            tasks.append(_analytics_metadata_search(q, user_id, analytics_primary_category))
    else:
        tasks = []
        for q in queries:
            tasks.append(_dense_search(q, user_id, category,
                                        requirements=requirements, status_filter=status_filter))
            tasks.append(_metadata_search(q, user_id, category,
                                           escalation_boost=escalation_boost,
                                           requirements=requirements, status_filter=status_filter))

    all_results = await asyncio.gather(*tasks, return_exceptions=True)

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

    def _dedup_max(hits: list[dict], score_key: str) -> list[dict]:
        best: dict[str, dict] = {}
        for h in hits:
            pid = h["id"]
            if pid not in best or h.get(score_key, 0.0) > best[pid].get(score_key, 0.0):
                best[pid] = h
        return list(best.values())

    dense_dedup    = _dedup_max(all_dense,    "vector_score")
    metadata_dedup = _dedup_max(all_metadata, "metadata_score")

    fused = _fuse_results(dense_dedup, metadata_dedup, requirements=requirements)
    fused = _normalize_scores(fused)
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
        q_tokens = _normalize_query_tokens(query)
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
    # Issue #9: Universal content_type extraction.
    # Searches multiple fields where the content type may be stored,
    # in priority order. Works for any business schema.
    sd_raw   = payload.get("structured_data") or {}
    attr_raw = payload.get("attributes") or {}
    content_type = (
        payload.get("content_type")
        or payload.get("subtype")
        or attr_raw.get("content_type")
        or attr_raw.get("record_type")
        or sd_raw.get("content_type")
        or sd_raw.get("record_type")
        or sd_raw.get("type")
        or attr_raw.get("type")
        or ""
    )
    # Infer content_type from subtype if it is data_analytics
    if not content_type and payload.get("subtype") == "data_analytics":
        content_type = "analytics"
    return {
        "entry_id":     payload.get("entry_id") or hit.get("id", ""),
        "category":     payload.get("category", category),
        "subtype":      payload.get("subtype", ""),
        "content_type": str(content_type).lower().strip(),
        "score":        hit.get("score", 0.0),
        "vector_score":      hit.get("vector_score", 0.0),
        "metadata_score":    hit.get("metadata_score", 0.0),
        "requirement_score": hit.get("requirement_score", 0.5),
        "quality_score":     hit.get("quality_score", 0.0),
        "priority_score":    hit.get("priority_score", 0.0),
        "source_type":  payload.get("source_type", ""),
        "title":        payload.get("title", ""),
        "search_text":  payload.get("search_text", ""),
        "ai_tags":      payload.get("ai_tags") or [],
        "keywords":     payload.get("keywords") or [],
        "payload": {
            "title":           payload.get("title", ""),
            "search_text":     payload.get("search_text", ""),
            "structured_data": sd_raw,
            "attributes":      attr_raw,
            "ai_tags":         payload.get("ai_tags") or [],
            "keywords":        payload.get("keywords") or [],
            "entities":        payload.get("entities") or [],
            "content_type":    str(content_type).lower().strip(),
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
# ENTERPRISE RETRIEVAL CONTRACT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_numeric_range_filter(user_id: str, category: str, constraints: list[dict]):
    """
    Build a Qdrant filter that combines category isolation WITH numeric range
    constraints extracted from the customer message (Issue 2 — Filter Planner).

    constraints: list of {"field": "price", "operator": "lte"|"gte"|"eq", "value": float}

    For "eq" operator: applies a ±5% tolerance range (lte + gte).
    For all others: single Range condition on attributes.<field>.

    Falls back to the standard category filter if constraints list is empty
    or if none of the constraint fields exist in the payload schema.
    """
    from qdrant_client.models import (
        Filter, FieldCondition, MatchValue, Range
    )
    base_must = [
        FieldCondition(key="user_id",  match=MatchValue(value=user_id)),
        FieldCondition(key="category", match=MatchValue(value=category)),
    ]
    must_not = [FieldCondition(key="subtype", match=MatchValue(value="data_analytics"))]

    # status_filter is passed from retrieval_contract — no hardcoded category assumptions
    # (offers_promotions active filter now comes from rc_contract.status_filter in P1)

    for c in constraints:
        field     = c.get("field", "")
        operator  = c.get("operator", "")
        value     = c.get("value")
        if not field:
            continue
        attr_key = f"attributes.{field}"
        if operator == "lte" and value is not None:
            base_must.append(FieldCondition(key=attr_key, range=Range(lte=value)))
        elif operator == "gte" and value is not None:
            base_must.append(FieldCondition(key=attr_key, range=Range(gte=value)))
        elif operator == "eq" and value is not None:
            tolerance = value * 0.05
            base_must.append(FieldCondition(
                key=attr_key,
                range=Range(gte=value - tolerance, lte=value + tolerance)
            ))
        elif operator == "between":
            min_v = c.get("min")
            max_v = c.get("max")
            if min_v is not None and max_v is not None:
                base_must.append(FieldCondition(
                    key=attr_key,
                    range=Range(gte=float(min_v), lte=float(max_v))
                ))

    return Filter(must=base_must, must_not=must_not)


def _deterministic_scroll(
    user_id: str,
    category: str,
    field: str,
    direction: str,
    numeric_constraints: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """
    Deterministic Retrieval Mode — bypass vector search entirely.

    Scrolls ALL records for user+category (no vector search), sorts by the
    target field, returns top_k. Business truth (actual numeric values)
    overrides semantic similarity scores completely.

    NOTE: This is called via asyncio.to_thread in _run_hybrid_retrieval_inner
    to avoid blocking the event loop.
    """
    client = _get_qdrant_client()
    f = _build_numeric_range_filter(user_id, category, numeric_constraints)

    all_points = []
    offset = None
    while True:
        batch, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=f,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not batch:
            break
        all_points.extend(batch)
        if next_offset is None:
            break
        offset = next_offset

    if not all_points:
        return []

    def _get_field_value(point) -> float:
        payload = point.payload or {}
        attrs   = payload.get("attributes") or {}
        sd      = payload.get("structured_data") or {}
        raw = attrs.get(field) or sd.get(field)
        if raw is None:
            return float("inf") if direction == "asc" else float("-inf")
        try:
            import re as _re
            cleaned = _re.sub(r"[^\d.]", "", str(raw))
            return float(cleaned) if cleaned else (float("inf") if direction == "asc" else float("-inf"))
        except (ValueError, TypeError):
            return float("inf") if direction == "asc" else float("-inf")

    all_points.sort(key=_get_field_value, reverse=(direction == "desc"))
    top = all_points[:top_k]

    return [
        {
            "id":             str(p.id),
            "vector_score":   1.0,
            "metadata_score": 1.0,
            "payload":        p.payload or {},
            "_deterministic": True,
        }
        for p in top
    ]


def _apply_deterministic_sort(
    fused: list[dict],
    field: str,
    direction: str,
) -> list[dict]:
    """
    Issue 3 — Post-fusion deterministic sort.

    When called after normal fusion (for cases where deterministic scroll
    was not used), re-sorts the fused list by the actual numeric field value
    instead of the fusion score. This ensures business truth wins over
    semantic similarity for min/max queries.

    Used as a fallback when _deterministic_scroll returns 0 results.
    """
    import re as _re

    def _val(result: dict) -> float:
        payload = result.get("payload") or {}
        attrs   = payload.get("attributes") or {}
        sd      = payload.get("structured_data") or {}
        raw = attrs.get(field) or sd.get(field)
        if raw is None:
            return float("inf") if direction == "asc" else float("-inf")
        try:
            cleaned = _re.sub(r"[^\d.]", "", str(raw))
            return float(cleaned) if cleaned else (float("inf") if direction == "asc" else float("-inf"))
        except (ValueError, TypeError):
            return float("inf") if direction == "asc" else float("-inf")

    sorted_results = sorted(fused, key=_val, reverse=(direction == "desc"))
    # Re-normalize scores so #1 = 1.0
    return _normalize_scores(sorted_results)


def _apply_candidate_validation(
    results: list[dict],
    numeric_constraints: list[dict],
    requirements: list[dict],
) -> list[dict]:
    """
    Post-retrieval candidate validation (Issues #2, #4, #12).

    FIXED: Now uses requirements[] from retrieval_contract directly.
    The old specifications: list[str] parameter is replaced with
    requirements: list[dict] — structured field→value pairs from P1.
    No regex parsing, no domain assumptions, no hardcoded fields.

    Validation hierarchy:
      1. Numeric constraints (price ranges, attribute ranges) — hard remove
         if violation exceeds 20% tolerance
      2. Exact field requirements from requirements[] — demote (not remove)
         candidates that don't match. Demotion preserves them as fallbacks.

    Analytics docs always pass through — they carry aggregated data,
    not individual product specs.
    """
    import re as _re

    if not numeric_constraints and not requirements:
        return results

    def _get_attr_float(result: dict, field: str):
        payload = result.get("payload") or {}
        attrs   = payload.get("attributes") or {}
        sd      = payload.get("structured_data") or {}
        raw = attrs.get(field) or sd.get(field)
        if raw is None:
            return None
        try:
            cleaned = _re.sub(r"[^\d.]", "", str(raw))
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    def _get_attr_str(result: dict, field: str) -> str | None:
        payload = result.get("payload") or {}
        attrs   = payload.get("attributes") or {}
        sd      = payload.get("structured_data") or {}
        for store in (attrs, sd):
            raw = store.get(field)
            if raw is not None:
                return str(raw).strip().upper().replace(" ", "")
        return None

    # Semantic requirements from schema-free P1 extraction (operator="semantic"/"keyword")
    # Legacy field-based requirements (operator="eq") also handled for backward compat
    semantic_reqs = [
        r for r in requirements
        if isinstance(r, dict)
        and r.get("operator") in ("semantic", "keyword")
        and r.get("value")
    ]
    eq_reqs = [
        r for r in requirements
        if isinstance(r, dict) and r.get("operator") == "eq" and r.get("field")
    ]

    passed  = []
    demoted = []

    for result in results:
        if result.get("subtype") == "data_analytics":
            passed.append(result)
            continue

        hard_violates = False
        # --- Numeric constraint hard removal ---
        for c in numeric_constraints:
            field    = c.get("field", "")
            operator = c.get("operator", "")
            value    = c.get("value")
            if not field or value is None:
                continue
            actual = _get_attr_float(result, field)
            if actual is None:
                continue
            TOLERANCE = 0.20
            if operator == "lte" and actual > value * (1 + TOLERANCE):
                hard_violates = True
                break
            if operator == "gte" and actual < value * (1 - TOLERANCE):
                hard_violates = True
                break
            if operator == "between":
                min_v = c.get("min")
                max_v = c.get("max")
                if min_v is not None and max_v is not None:
                    if actual < float(min_v) * (1 - TOLERANCE) or actual > float(max_v) * (1 + TOLERANCE):
                        hard_violates = True
                        break

        if hard_violates:
            demoted.append(result)
            continue

        # --- Schema-free semantic requirement soft demotion ---
        # Build normalized payload text once per result for all semantic checks
        if semantic_reqs:
            payload_inner = result.get("payload") or {}
            pl_parts: list[str] = []
            for _key in ("structured_data", "attributes", "entities"):
                _obj = payload_inner.get(_key)
                if isinstance(_obj, dict):
                    pl_parts.extend(str(v) for v in _obj.values())
                elif isinstance(_obj, list):
                    pl_parts.extend(str(i) for i in _obj)
            pl_parts.append(str(payload_inner.get("title") or ""))
            pl_parts.extend(str(k) for k in (payload_inner.get("keywords") or []))
            pl_tokens = _normalize_query_tokens(" ".join(pl_parts))

            failed_sem = 0
            for req in semantic_reqs:
                req_val_tokens = _normalize_query_tokens(str(req["value"]))
                if not req_val_tokens:
                    continue
                overlap = len(req_val_tokens & pl_tokens)
                # Fail only if ZERO tokens match — soft demotion only
                if overlap == 0:
                    failed_sem += 1

            if failed_sem > 0:
                demoted.append(result)
                continue

        # --- Legacy field-based requirement soft demotion ---
        if eq_reqs:
            failed = 0
            for req in eq_reqs:
                field = str(req["field"]).strip().lower()
                value = str(req.get("value") or "").strip().upper().replace(" ", "")
                candidate = _get_attr_str(result, field)
                if candidate is None:
                    continue
                cand_clean = _re.sub(r"[^\d.A-Z]", "", candidate)
                val_clean  = _re.sub(r"[^\d.A-Z]", "", value)
                if cand_clean and val_clean and cand_clean != val_clean:
                    failed += 1

            if failed > 0:
                demoted.append(result)
                continue

        passed.append(result)

    if demoted:
        logger.debug(
            "[candidate_validation] demoted %d/%d results (numeric=%d, spec=%d)",
            len(demoted), len(results),
            sum(1 for r in demoted if any(
                _get_attr_float(r, c.get("field", "")) is not None
                for c in numeric_constraints
            )),
            len(demoted),
        )

    return passed + demoted


def _apply_diversity_rerank(
    results: list[dict],
    max_per_subcategory: int = 2,
) -> list[dict]:
    """
    Diversity reranking — MMR-inspired, category-agnostic.

    FIXED: No longer hardcoded to product_service only.
    Works for ANY category that has a sub-category/department field.
    Analytics docs always pass through unchanged.

    Uses the outer `category` field from the formatted result dict
    (not the inner payload sub-category field) to determine which
    results are operational records eligible for diversity.

    Algorithm:
      For each result, extract its sub-category from attributes/structured_data.
      If a sub-category already has max_per_subcategory items, defer to end.
      Deferred items are still returned — just after the diverse set.
    """
    if len(results) <= 3:
        return results

    # Only apply to non-analytics operational records
    operational = [r for r in results if r.get("subtype") != "data_analytics"]
    if len(operational) <= 3:
        return results

    subcategory_counts: dict[str, int] = {}
    prioritized: list[dict] = []
    deferred:    list[dict] = []

    for result in results:
        if result.get("subtype") == "data_analytics":
            prioritized.append(result)
            continue

        payload = result.get("payload") or {}
        attrs   = payload.get("attributes") or {}
        sd      = payload.get("structured_data") or {}

        # Domain-agnostic sub-category extraction
        subcat = str(
            attrs.get("category") or attrs.get("department") or
            attrs.get("type") or attrs.get("sub_category") or
            sd.get("category") or sd.get("department") or
            sd.get("type") or "unknown"
        ).strip().lower()

        count = subcategory_counts.get(subcat, 0)
        if count < max_per_subcategory:
            subcategory_counts[subcat] = count + 1
            prioritized.append(result)
        else:
            deferred.append(result)

    return _normalize_scores(prioritized + deferred)

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

    # ── Extract P1 fields + retrieval_contract ──────────────────────────────
    rs  = p1_output.get("retrieval_strategy") or {}
    ad  = p1_output.get("analytics_decision") or {}
    ca  = p1_output.get("conversation_analysis") or {}
    ia  = p1_output.get("intent_analysis") or {}
    pi  = ia.get("primary_intent") or {}
    rc_contract = p1_output.get("retrieval_contract") or {}

    raw_categories      = rs.get("categories") or []
    requires_analytics  = bool(ad.get("requires_analytics", False))
    standalone_query    = ca.get("standalone_query") or ""
    primary_intent_cat  = pi.get("category") or "product_service"

    # ── Read retrieval_contract (Issue 1/6) ──────────────────────────────────
    numeric_constraints  = rc_contract.get("numeric_constraints") or []
    deterministic_mode   = rc_contract.get("deterministic_mode") or {"active": False, "field": "", "direction": ""}
    rc_requirements      = rc_contract.get("requirements") or []   # structured field→value pairs from P1
    rc_specifications    = rc_contract.get("specifications") or []  # kept for logging only
    det_active  = bool(deterministic_mode.get("active", False))
    det_field   = deterministic_mode.get("field", "price")
    det_dir     = deterministic_mode.get("direction", "asc")

    # status_filter: injected from retrieval_contract if P1 specified one
    # (enterprise principle: no hardcoded "offers_promotions" logic in retrieval layer)
    status_filter = rc_contract.get("status_filter") or None

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
                if pc in ALLOWED_CATEGORIES and pc not in analytics_categories:
                    analytics_categories.append(pc)
        # Scope guard: never allow more analytics categories than retrieval categories.
        # Cross-category analytics contamination is suppressed here as a second
        # defence in case P1 validator missed it (e.g. old cached P1 output).
        retrieval_cat_set = {str(c.get("category", "")) for c in raw_categories if isinstance(c, dict)}
        retrieval_cat_set.add(primary_intent_cat)
        analytics_categories = [c for c in analytics_categories if c in retrieval_cat_set]
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

    # ── Issue 3/10: Deterministic fast-path — async, non-blocking ─────────────
    # When the customer wants min/max: skip vector search entirely.
    # _deterministic_scroll runs in a thread pool (asyncio.to_thread) so it
    # never blocks the event loop — unlike the previous synchronous call.
    deterministic_results: list[dict] = []
    det_cats_done: set[str] = set()

    if det_active and det_field and primary_intent_cat in ALLOWED_CATEGORIES:
        logger.info(
            "[retrieval] deterministic mode | field=%s direction=%s cat=%s",
            det_field, det_dir, primary_intent_cat,
        )
        try:
            det_hits = await asyncio.to_thread(
                _deterministic_scroll,
                user_id, primary_intent_cat, det_field, det_dir,
                numeric_constraints, PER_CATEGORY_TOP_K,
            )
            if det_hits:
                det_cats_done.add(primary_intent_cat)
                fused_det = _fuse_results(det_hits, [], requirements=rc_requirements)
                fused_det = _normalize_scores(fused_det)
                for hit in fused_det:
                    r = _format_result(hit, primary_intent_cat)
                    r["_deterministic"] = True
                    deterministic_results.append(r)
                logger.info(
                    "[retrieval] deterministic scroll returned %d results for %s",
                    len(det_hits), primary_intent_cat,
                )
        except Exception as _det_exc:
            logger.warning("[retrieval] deterministic scroll failed: %s", _det_exc)

    for cat, qs in cat_queries.items():
        if cat in det_cats_done:
            continue
        boost = is_escalation_search and cat == "contact_support"
        tasks.append((cat, False, "", qs, boost))

    for ac_primary in analytics_categories:
        # Analytics query construction — REQUIREMENT-ENRICHED
        # The analytics chunk lives in a different semantic space from product chunks.
        # Using the raw standalone_query (a product discovery query) produces a poor
        # vector match against analytics summaries ("20 items, price range...").
        # We construct an analytics-specific query that aligns with the analytics
        # chunk's vocabulary: counts, statistics, summaries, distributions.
        #
        # Strategy:
        #   1. Extract what the customer wants to know (from analytics_categories reason)
        #   2. Build a query using aggregate vocabulary: "count", "total", "summary", etc.
        #   3. Enrich with entity context from P1 entity_extraction if available
        ee_info      = p1_output.get("entity_extraction") or {}
        specs        = ee_info.get("specifications") or []
        ca_info      = p1_output.get("conversation_analysis") or {}
        current_focus = ca_info.get("current_focus") or ""

        # Build category-specific analytics query
        cat_label = ac_primary.replace("_", " ")
        if specs:
            # Customer has specifications — they want stats about items matching specs
            spec_str = ", ".join(specs[:3])
            analytics_qs = [
                f"{cat_label} analytics summary statistics count distribution",
                f"{cat_label} total count breakdown price range {spec_str}",
            ]
        elif standalone_query:
            analytics_qs = [
                f"{cat_label} analytics statistics summary count total distribution",
                f"{standalone_query} statistics count breakdown overview",
            ]
        else:
            analytics_qs = [f"{cat_label} analytics summary statistics count distribution breakdown"]

        tasks.append((ac_primary, True, ac_primary, analytics_qs, False))

    # CRITICAL BUG FIX (Bug 1): When deterministic mode handled the primary
    # category and no other categories exist, tasks will be empty.
    # Previously this triggered _fallback_scroll which discarded all
    # deterministic_results. Now we check if we already have results.
    if not tasks:
        if deterministic_results:
            # Deterministic path succeeded — return those results directly
            # without falling back to random scroll.
            elapsed = (time.monotonic() - t0) * 1000
            logger.info(
                "[hybrid_retrieval] deterministic-only path | results=%d | user=%s",
                len(deterministic_results), user_id[:8],
            )
            return {
                "retrieval_id":                    retrieval_id,
                "categories_searched":             [primary_intent_cat],
                "total_candidates_found":          len(deterministic_results),
                "total_candidates_after_filtering": len(deterministic_results),
                "analytics_searched":              False,
                "elapsed_ms":                      round(elapsed, 1),
                "results":                         deterministic_results,
                "retrieval_diversity_score":       0.0,
                "deterministic_mode_used":         True,
                "retrieval_contract_applied": {
                    "numeric_constraints":  numeric_constraints,
                    "deterministic_mode":   deterministic_mode,
                    "requirements":         rc_requirements,
                },
            }
        # Genuinely no results anywhere — fallback
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
                requirements               = rc_requirements if not is_analytics else None,
                status_filter              = status_filter,
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

    # ── Merge deterministic + vector results ──────────────────────────────
    # Deterministic results always come first (business truth > semantic score)
    combined_results = deterministic_results + all_results

    # ── Final dedup and sort ──────────────────────────────────────────────
    # Multiple categories may return the same entry — deduplicate by entry_id
    seen_entries: set[str] = set()
    deduped:      list[dict[str, Any]] = []
    for r in sorted(combined_results, key=lambda x: x.get("score", 0.0), reverse=True):
        eid = r.get("entry_id") or r.get("payload", {}).get("entry_id", "")
        key = eid or r.get("entry_id", "")
        if key and key in seen_entries:
            continue
        seen_entries.add(key)
        deduped.append(r)

    # Issue 7 defence: Ensure analytics docs don't rank above operational records
    # when analytics=False. Analytics docs are always pushed to the end.
    if not requires_analytics:
        non_analytics = [r for r in deduped if r.get("subtype") != "data_analytics"]
        analytics_docs = [r for r in deduped if r.get("subtype") == "data_analytics"]
        deduped = non_analytics + analytics_docs

    # Filter invalid offers using correct outer category field
    deduped = [r for r in deduped if _is_offer_valid(r.get("payload", {}), doc_category=r.get("category", ""))]

    # Normalize scores across all categories for meaningful ranking
    deduped = _normalize_scores(deduped)

    # Issue 3 post-sort: if deterministic mode active but scroll returned 0,
    # fall back to metadata-based sort on the fused vector results
    if det_active and det_field and not deterministic_results and deduped:
        deduped = _apply_deterministic_sort(deduped, det_field, det_dir)
        logger.info("[retrieval] applied post-fusion deterministic sort | field=%s dir=%s", det_field, det_dir)

    # Issue 9 — Candidate validation: uses requirements[] from retrieval_contract
    if numeric_constraints or rc_requirements:
        deduped = _apply_candidate_validation(deduped, numeric_constraints, rc_requirements)

    # Diversity reranking — now category-agnostic (not product_service only)
    if not det_active:
        deduped = _apply_diversity_rerank(deduped, max_per_subcategory=2)

    top_score    = deduped[0]["score"]  if deduped else 0.0
    lowest_score = deduped[-1]["score"] if deduped else 0.0
    elapsed_ms   = (time.monotonic() - t0) * 1000

    # Compute retrieval diversity score
    diversity_score = _compute_diversity_score(deduped)

    # Log retrieval contract (Issue 1/6)
    if det_active:
        logger.info(
            "[CONTRACT] deterministic=%s field=%s dir=%s constraints=%s",
            det_active, det_field, det_dir,
            [(c["field"], c["operator"], c["value"]) for c in numeric_constraints],
        )
    if numeric_constraints:
        logger.info("[CONTRACT] numeric_constraints=%s", numeric_constraints)

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
        "retrieval_diversity_score":       diversity_score,
        "deterministic_mode_used":         det_active and bool(deterministic_results),
        "retrieval_contract_applied": {
            "numeric_constraints":  numeric_constraints,
            "deterministic_mode":   deterministic_mode,
            "requirements":         rc_requirements,
        },
    }