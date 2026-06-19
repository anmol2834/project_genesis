"""
Async Qdrant Repository
========================
Wraps AsyncQdrantClient with the same interface that all retrieval engines
expect: .search(user_id, query_vector, ...) and .scroll(user_id, filters, ...).

DUAL-COLLECTION SUPPORT:
  The automation-service uses two Qdrant collections:

  1. business_context (QDRANT_COLLECTION)
     - Written by embedding_tasks.py (Celery)
     - Contains: business profile chunks (business_core, audience, tone, etc.)
     - Payload fields: user_id, type, content

  2. user_data_entries (QDRANT_CATALOG_COLLECTION)
     - Written by embedding_service.py (ingestion pipeline)
     - Contains: full product/service/analytics/contact catalog
     - Payload fields: user_id, entry_id, category, search_text, title, ai_tags, etc.

  This repository ALWAYS searches user_data_entries first (catalog data),
  then optionally merges results from business_context (profile data).
  It normalizes user_data_entries payloads to the schema that retrieval
  engines expect (content, chunk_type, chunk_id).

  The original 768-vs-384 dimension mismatch caused ALL searches against
  business_context to fail. Additionally, business_context was empty (0 points)
  while all 101 catalog entries lived in user_data_entries — unreachable.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

logger = logging.getLogger(__name__)


def _normalize_payload(payload: Dict) -> Dict:
    """
    Normalize a Qdrant payload to the standard schema expected by retrieval engines.

    user_data_entries uses:  search_text, category, entry_id, title, ai_tags, attributes
    business_context uses:   content, type (mapped → chunk_type), chunk_id

    After normalization every payload has:
      content     — text used for BM25 scoring and display
      chunk_type  — category enum value
      chunk_id    — stable identifier
      user_id     — tenant key

    BUSINESS-AGNOSTIC: The content field is built from every available text field
    without assuming any specific business domain. Rather than pulling a fixed list
    of hardware-specific keys (ram, storage, processor…), we iterate ALL keys in
    structured_data and attributes so that:
      - A laptop company's "ram: 8GB" is included
      - A restaurant's "cuisine: Italian" is included
      - A law firm's "practice_area: Corporate" is included
      - A medical device company's "certification: ISO-13485" is included
    No business-specific field names are hardcoded here.
    """
    normalized = dict(payload)

    # content: prefer explicit content, else build from all available text sources
    if not normalized.get("content"):
        parts = []
        if normalized.get("title"):
            parts.append(str(normalized["title"]))
        if normalized.get("search_text"):
            parts.append(str(normalized["search_text"]))

        # Append ALL structured_data values so BM25 scoring picks up any domain's specs.
        # This is intentionally domain-agnostic — we iterate every key/value pair
        # rather than hardcoding specific field names like "ram" or "storage".
        for src_key in ("structured_data", "attributes"):
            src = normalized.get(src_key) or {}
            if isinstance(src, dict):
                for k, v in src.items():
                    if v is not None and str(v).strip():
                        # Include both key and value for richer token overlap scoring
                        parts.append(f"{k}: {v}")

        if parts:
            normalized["content"] = " | ".join(parts)
        elif normalized.get("type"):
            # business_context uses "type" as content label
            normalized["content"] = str(normalized.get("type", ""))

    # chunk_type: prefer explicit chunk_type, else map from category or type.
    # CRITICAL FIX: We now preserve the ORIGINAL category name in chunk_type so that
    # L4/L5/L6 category filters produce exact matches against the Qdrant "category" field.
    # e.g. intent "offers_inquiry" → target_category "offers_promotions" → filter
    # category="offers_promotions" in Qdrant → chunk_type="offers_promotions" in result.
    # business_context entries (which use "type" not "category") are mapped to the
    # closest user_data_entries category name for consistency.
    if not normalized.get("chunk_type"):
        cat = str(normalized.get("category") or normalized.get("type") or "general").lower()
        category_map = {
            # user_data_entries categories — preserve exact identity for filter routing
            "product_service":     "product_service",
            "product":             "product_service",
            "service":             "product_service",
            "offers_promotions":   "offers_promotions",
            "delivery_shipping":   "delivery_shipping",
            "contact_support":     "contact_support",
            "support":             "contact_support",
            "contact":             "contact_support",
            "policies_legal":      "policies_legal",
            "policy":              "policies_legal",
            "company_info":        "company_info",
            "profile":             "company_info",
            "educational_content": "educational_content",
            "faq":                 "educational_content",
            "issue_resolution":    "issue_resolution",
            "team_people":         "company_info",
            "testimonials":        "company_info",
            "data_analytics":      "data_analytics",
            "analytics":           "data_analytics",
            # business_context chunk types → closest category equivalent
            "business_core":       "company_info",
            "audience":            "company_info",
            "tone":                "company_info",
            "use_case":            "product_service",
            "instruction":         "company_info",
        }
        normalized["chunk_type"] = category_map.get(cat, "general")

    # chunk_id: prefer explicit chunk_id, else entry_id, else id
    if not normalized.get("chunk_id"):
        normalized["chunk_id"] = str(
            normalized.get("entry_id") or normalized.get("id", "")
        )

    return normalized


class AsyncQdrantRepository:
    """
    Tenant-safe async Qdrant repository.

    Drop-in replacement for QdrantRepository that works with AsyncQdrantClient.
    Searches the catalog collection (user_data_entries) by default, with optional
    fallback to the profile collection (business_context).

    Every query enforces user_id isolation via a Qdrant filter.
    All payloads are normalized to the standard schema before returning.
    """

    def __init__(
        self,
        client: AsyncQdrantClient,
        collection_name: str = "business_context",
        catalog_collection: Optional[str] = None,
    ):
        self._client = client
        self._profile_collection = collection_name        # business_context
        self._catalog_collection = catalog_collection     # user_data_entries

        # Primary search target: catalog collection if available, else profile
        self._primary_collection = catalog_collection or collection_name
        logger.info(
            "AsyncQdrantRepository | primary=%s profile=%s",
            self._primary_collection, self._profile_collection,
        )

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0,
    ) -> List[Dict]:
        """Vector search with mandatory tenant isolation.

        Searches the primary collection (user_data_entries) first.
        If results are insufficient (< 3) and a separate profile collection exists,
        merges in results from business_context.
        """
        if not user_id:
            raise ValueError("user_id is MANDATORY for tenant isolation")

        results = await self._search_collection(
            collection=self._primary_collection,
            user_id=user_id,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
            score_threshold=score_threshold,
        )

        # Augment with profile collection when few results and collections are different
        if (
            len(results) < 3
            and self._catalog_collection
            and self._profile_collection != self._primary_collection
        ):
            profile_results = await self._search_collection(
                collection=self._profile_collection,
                user_id=user_id,
                query_vector=query_vector,
                limit=limit - len(results),
                filters=None,   # profile collection has different filter schema
                score_threshold=score_threshold,
            )
            # Merge, deduplicate by id
            seen = {r["id"] for r in results}
            for r in profile_results:
                if r["id"] not in seen:
                    results.append(r)
                    seen.add(r["id"])

        return results

    async def _search_collection(
        self,
        collection: str,
        user_id: str,
        query_vector: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]],
        score_threshold: float,
    ) -> List[Dict]:
        must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if filters:
            must.extend(self._build_conditions(filters))

        try:
            results = await self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=Filter(must=must),
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {
                    "id": r.id,
                    "score": r.score,
                    "payload": _normalize_payload(r.payload or {}),
                }
                for r in results
            ]
        except Exception as e:
            logger.error("AsyncQdrantRepository.search error (collection=%s): %s", collection, e)
            return []

    # ── Scroll ────────────────────────────────────────────────────────────────

    async def scroll(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        offset: Optional[str] = None,
    ) -> List[Dict]:
        """Scroll through records with mandatory tenant isolation."""
        if not user_id:
            raise ValueError("user_id is MANDATORY for tenant isolation")

        results = await self._scroll_collection(
            collection=self._primary_collection,
            user_id=user_id,
            filters=filters,
            limit=limit,
            offset=offset,
        )

        # Augment with profile collection for general scrolls
        if (
            len(results) < limit
            and self._catalog_collection
            and self._profile_collection != self._primary_collection
        ):
            remaining = limit - len(results)
            profile_results = await self._scroll_collection(
                collection=self._profile_collection,
                user_id=user_id,
                filters=None,
                limit=remaining,
                offset=None,
            )
            seen = {r["id"] for r in results}
            for r in profile_results:
                if r["id"] not in seen:
                    results.append(r)
                    seen.add(r["id"])

        return results

    async def _scroll_collection(
        self,
        collection: str,
        user_id: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        offset: Optional[str],
    ) -> List[Dict]:
        must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if filters:
            must.extend(self._build_conditions(filters))

        try:
            results, _ = await self._client.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=must),
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {
                    "id": r.id,
                    "payload": _normalize_payload(r.payload or {}),
                }
                for r in results
            ]
        except Exception as e:
            logger.error("AsyncQdrantRepository.scroll error (collection=%s): %s", collection, e)
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_conditions(self, filters: Dict[str, Any]) -> List[FieldCondition]:
        """
        Build Qdrant filter conditions from a dict of filter parameters.

        BUSINESS-AGNOSTIC DESIGN:
        ---------------------------------------------------------------------------
        This method does NOT know or assume anything about the business domain.
        It supports two categories of filters:

        1. SYSTEM FILTERS (always supported — used for routing/isolation):
           - category / chunk_type: routes to the correct Qdrant category bucket
           - primary_category: used by analytics injection to find the right analytics
             chunk (e.g. primary_category="offers_promotions")

        2. DYNAMIC ATTRIBUTE FILTERS (domain-agnostic):
           The caller can pass any key/value pair under the "attributes" sub-dict.
           Each key is mapped to a Qdrant field condition using dot-notation:
             filters={"attributes": {"price_min": 500, "price_max": 1000}}
           This works for:
             - A laptop company: {"attributes": {"ram_gb": 8, "storage_gb": 512}}
             - A restaurant:     {"attributes": {"cuisine": "Italian"}}
             - A law firm:       {"attributes": {"practice_area": "Corporate"}}
             - Any business:     {"attributes": {<any_field>: <any_value>}}

        3. LEGACY COMPAT FILTERS (kept for backward compatibility):
           - price_min / price_max: maps to Range on "price" field
           - features: list of feature tags
           These exist because older callers pass these directly; new callers should
           use the "attributes" sub-dict approach instead.
        ---------------------------------------------------------------------------
        """
        conditions: List[FieldCondition] = []

        # ── 1. System routing filters ──────────────────────────────────────────
        # category / chunk_type: routes to the correct Qdrant category bucket
        for field_alias in ("category", "chunk_type"):
            if filters.get(field_alias):
                conditions.append(
                    FieldCondition(key="category", match=MatchValue(value=filters[field_alias]))
                )

        # primary_category: used by analytics scroll to find intent-specific analytics
        if filters.get("primary_category"):
            conditions.append(
                FieldCondition(
                    key="structured_data.primary_category",
                    match=MatchValue(value=filters["primary_category"]),
                )
            )

        # department: direct field match (supported by some legacy data schemas)
        if filters.get("department"):
            conditions.append(
                FieldCondition(key="department", match=MatchValue(value=filters["department"]))
            )

        # ── 2. Dynamic attribute filters — fully business-agnostic ────────────
        # Any key/value pair passed under "attributes" is turned into a Qdrant
        # FieldCondition on the corresponding dot-notation path.
        # Numeric values → Range condition; string values → MatchValue condition.
        # This design means zero code changes are needed to support a new business
        # type or a new filterable attribute.
        dynamic_attrs = filters.get("attributes", {})
        if isinstance(dynamic_attrs, dict):
            for attr_key, attr_val in dynamic_attrs.items():
                if attr_val is None:
                    continue
                qdrant_field = f"structured_data.{attr_key}"
                if isinstance(attr_val, dict) and ("gte" in attr_val or "lte" in attr_val):
                    # Explicit range condition: {"gte": 100, "lte": 500}
                    range_kwargs = {}
                    if attr_val.get("gte") is not None:
                        range_kwargs["gte"] = float(attr_val["gte"])
                    if attr_val.get("lte") is not None:
                        range_kwargs["lte"] = float(attr_val["lte"])
                    conditions.append(
                        FieldCondition(key=qdrant_field, range=Range(**range_kwargs))
                    )
                elif isinstance(attr_val, (int, float)):
                    # Numeric single value → exact range match (gte=lte)
                    conditions.append(
                        FieldCondition(
                            key=qdrant_field,
                            range=Range(gte=float(attr_val), lte=float(attr_val)),
                        )
                    )
                else:
                    # String or other → exact match
                    conditions.append(
                        FieldCondition(key=qdrant_field, match=MatchValue(value=str(attr_val)))
                    )
                # Also try the attributes.* path for businesses that store flat attributes
                conditions.append(
                    FieldCondition(
                        key=f"attributes.{attr_key}",
                        match=MatchValue(value=str(attr_val)),
                    )
                )

        # ── 3. Legacy compat filters ───────────────────────────────────────────
        # price_min / price_max: backwards-compatible range on the "price" field.
        # New integrations should use filters["attributes"]["price"] = {"gte": x, "lte": y}
        range_params: Dict[str, Any] = {}
        if "price_min" in filters and filters["price_min"] is not None:
            range_params["gte"] = float(filters["price_min"])
        if "price_max" in filters and filters["price_max"] is not None:
            range_params["lte"] = float(filters["price_max"])
        if range_params:
            conditions.append(FieldCondition(key="price", range=Range(**range_params)))
            # Also try structured_data.price for businesses that store price there
            conditions.append(
                FieldCondition(key="structured_data.price", range=Range(**range_params))
            )

        # features: list of feature/tag values — stored as array in Qdrant payload
        for feature in filters.get("features", []):
            if feature:
                conditions.append(
                    FieldCondition(key="features", match=MatchValue(value=feature))
                )

        return conditions
