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
    """
    normalized = dict(payload)

    # content: prefer explicit content, else build from search_text + title + key structured_data values
    if not normalized.get("content"):
        parts = []
        if normalized.get("title"):
            parts.append(str(normalized["title"]))
        if normalized.get("search_text"):
            parts.append(str(normalized["search_text"]))
        # Append key structured_data values so BM25 scoring finds specs like "8GB", "512GB SSD"
        sd = normalized.get("structured_data") or {}
        if isinstance(sd, dict):
            for key in ("ram", "storage", "processor", "gpu", "display", "battery"):
                val = sd.get(key)
                if val:
                    parts.append(str(val))
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
        conditions: List[FieldCondition] = []

        # chunk_type / category: map to the Qdrant "category" field in user_data_entries
        for field in ("category", "chunk_type", "department"):
            if filters.get(field):
                raw_value = filters[field]
                qdrant_field = "category" if field == "chunk_type" else field
                conditions.append(
                    FieldCondition(key=qdrant_field, match=MatchValue(value=raw_value))
                )

        range_params: Dict[str, Any] = {}
        if "price_min" in filters:
            range_params["gte"] = filters["price_min"]
        if "price_max" in filters:
            range_params["lte"] = filters["price_max"]
        if range_params:
            conditions.append(FieldCondition(key="price", range=Range(**range_params)))

        for feature in filters.get("features", []):
            conditions.append(
                FieldCondition(key="features", match=MatchValue(value=feature))
            )

        # ── Structured key/value spec filters ─────────────────────────────
        # These match nested fields inside structured_data JSON payload.
        # Qdrant supports dot-notation for nested payload fields.
        #
        # CRITICAL: The actual data stored in user_data_entries uses STRING values
        # for hardware specs (ram="8GB", storage="512GB SSD"), NOT integer fields
        # (ram_gb=8). The old paths (structured_data.ram_gb, structured_data.storage_gb)
        # never matched anything. We now map to the actual field names used by the
        # ingestion pipeline, using MatchValue (string match) instead of Range.
        # This works for any business domain — the field names come from the data itself.
        #
        # To keep this generic (not hardcoded to laptop/electronics), we try BOTH
        # the string field (structured_data.ram) and the integer field (structured_data.ram_gb)
        # so businesses that store numeric specs also benefit from this filter.
        if "ram_gb" in filters and filters["ram_gb"] is not None:
            val_gb = filters["ram_gb"]
            # Try string match against structured_data.ram: "8GB", "8 GB", "8gb"
            conditions.append(
                FieldCondition(key="structured_data.ram", match=MatchValue(value=f"{val_gb}GB"))
            )
            # Also try integer range for businesses that store numeric ram_gb
            try:
                conditions.append(
                    FieldCondition(key="structured_data.ram_gb", range=Range(gte=float(val_gb), lte=float(val_gb)))
                )
            except Exception:
                pass

        if "storage_gb" in filters and filters["storage_gb"] is not None:
            val_gb = filters["storage_gb"]
            # Determine storage type (SSD/HDD)
            storage_type = filters.get("storage_type", "")
            # Try string match: "512GB SSD", "512GB", "512 GB SSD"
            if val_gb >= 1024:
                tb_val = val_gb // 1024
                storage_str = f"{tb_val}TB {storage_type.upper()}" if storage_type else f"{tb_val}TB"
            else:
                storage_str = f"{val_gb}GB {storage_type.upper()}" if storage_type else f"{val_gb}GB"
            conditions.append(
                FieldCondition(key="structured_data.storage", match=MatchValue(value=storage_str.strip()))
            )
            try:
                conditions.append(
                    FieldCondition(key="structured_data.storage_gb", range=Range(gte=float(val_gb), lte=float(val_gb)))
                )
            except Exception:
                pass

        if "cpu" in filters and filters["cpu"]:
            conditions.append(
                FieldCondition(key="structured_data.processor", match=MatchValue(value=str(filters["cpu"])))
            )
        if "gpu" in filters and filters["gpu"]:
            conditions.append(
                FieldCondition(key="structured_data.gpu", match=MatchValue(value=str(filters["gpu"])))
            )
        if "brand" in filters and filters["brand"]:
            conditions.append(
                FieldCondition(key="structured_data.brand", match=MatchValue(value=str(filters["brand"]).lower()))
            )

        return conditions
