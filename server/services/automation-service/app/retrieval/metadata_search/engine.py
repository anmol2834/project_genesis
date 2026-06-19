"""
L4 Metadata Search Engine
==========================
Structured field filtering on categories, prices, and any domain-specific attributes.

Performance: <50ms

BUSINESS-AGNOSTIC DESIGN:
--------------------------
This engine does NOT assume any specific business domain.
It supports electronics, restaurants, law firms, medical devices, SaaS — anything.

Filter extraction is driven by Brain #1's entity output:
  - technical_terms: any spec strings ("8GB RAM", "Enterprise plan", "ISO-13485")
  - features: any feature/capability strings
  - budget_indicators: price signals
  - Any key=value entity from Brain #1's structured entities

For well-known numeric spec formats (8GB, 512GB SSD, 2.4GHz) we extract
the numeric value + unit for range-based Qdrant filtering.
For all other entity strings we attempt key=value parsing.
Unrecognised strings are passed to L5/L6 for token-overlap and semantic matching.
"""

import logging
import re
from typing import List, Dict, Optional, Any

from app.retrieval.schemas import RetrievedChunk, ChunkType, RetrievalSource

# ── Attribute compatibility shim ──────────────────────────────────────────────
_METADATA_SOURCE = RetrievalSource.L4_METADATA

logger = logging.getLogger(__name__)

# ── Universal numeric-unit patterns (domain-agnostic) ─────────────────────────
# Matches any "number unit" combination that could be a filterable spec in ANY domain.
# Examples across domains:
#   Electronics:  "8GB", "512GB SSD", "2.4GHz", "4K"
#   Medical:      "10mg", "Class III", "ISO-13485"
#   Vehicles:     "200hp", "2.0L", "150km/h"
#   SaaS:         "1000 users", "99.9% uptime"
_NUMERIC_UNIT_PAT = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*"
    r"(gb|tb|mb|kb|ghz|mhz|hz|watt|w|hp|cc|km|mile|nm|mm|cm|inch|in|\""
    r"|mg|g|kg|ml|l|rpm|fps|px|k|m|users?|seats?|days?|months?|years?|%)\b",
    re.IGNORECASE,
)

# ── Key=value entity patterns ──────────────────────────────────────────────────
# Brain #1 may return technical_terms like "service_tier: Enterprise" or
# "certification: ISO-13485" — these map directly to structured_data fields.
_KV_ENTITY_PAT = re.compile(r"^([a-zA-Z][a-zA-Z0-9_\-\s]{1,40}):\s*(.+)$")


class MetadataSearchEngine:
    """
    L4 metadata filtering on structured fields.

    Works for ANY business domain — product, service, consulting, medical, legal, SaaS.
    Filter keys are generated dynamically from entity strings rather than from a
    hardcoded vocabulary.
    """

    def __init__(self, qdrant_repository):
        self.qdrant = qdrant_repository

    async def search_metadata(
        self,
        user_id: str,
        filters: Dict[str, Any],
        top_k: int = 10,
    ) -> List[RetrievedChunk]:
        """
        Search by metadata filters.

        The `filters` dict is forwarded to AsyncQdrantRepository._build_conditions
        which handles all domain-agnostic conversion to Qdrant FieldCondition objects.
        """
        if not user_id or not filters:
            return []

        try:
            results = await self.qdrant.scroll(
                user_id=user_id,
                filters=filters,
                limit=top_k,
            )

            chunks = []
            for result in results:
                payload = result.get("payload", {})
                score = self._calculate_metadata_score(payload, filters)

                try:
                    ct = ChunkType(payload.get("chunk_type", "general"))
                except ValueError:
                    ct = ChunkType.GENERAL

                chunk = RetrievedChunk(
                    content=payload.get("content", ""),
                    score=score,
                    chunk_type=ct,
                    chunk_id=payload.get("chunk_id", str(result.get("id", ""))),
                    source=_METADATA_SOURCE,
                    user_id=user_id,
                    metadata=payload,
                    retrieval_layer="L4",
                )
                chunks.append(chunk)

            chunks.sort(key=lambda c: c.score, reverse=True)
            logger.info("L4 metadata: filters=%s found=%d", list(filters.keys()), len(chunks))
            return chunks[:top_k]

        except Exception as e:
            logger.error("L4 metadata search error: %s", e)
            return []

    def _calculate_metadata_score(self, payload: Dict, filters: Dict) -> float:
        """
        Domain-agnostic score: reward category match, price range, and feature overlap.
        """
        score = 0.0

        # Category / chunk_type match
        for cat_field in ("category", "chunk_type"):
            if cat_field in filters:
                pval = str(payload.get("category", "") or payload.get("chunk_type", "")).lower()
                if pval == str(filters[cat_field]).lower():
                    score += 0.4
                    break

        # Price range match — check both flat "price" and nested structured_data.price
        price_raw = (
            payload.get("price")
            or (payload.get("structured_data") or {}).get("price")
            or (payload.get("attributes") or {}).get("price")
        )
        if price_raw is not None:
            try:
                price = float(str(price_raw).replace(",", "").replace("$", "")
                              .replace("₹", "").replace("€", "").replace("£", "").strip())
                in_range = True
                if "price_min" in filters and price < float(filters["price_min"]):
                    in_range = False
                if "price_max" in filters and price > float(filters["price_max"]):
                    in_range = False
                if in_range:
                    score += 0.3
            except (ValueError, TypeError):
                pass

        # Features / tags overlap
        if "features" in filters:
            required = {f.lower() for f in filters["features"]}
            present = set()
            for fld in ("features", "ai_tags", "keywords"):
                for v in (payload.get(fld) or []):
                    present.add(str(v).lower())
            matched = required & present
            if required:
                score += 0.3 * len(matched) / len(required)

        # Dynamic attribute match — reward any structured_data/attributes hit
        dyn_attrs = filters.get("attributes", {})
        if isinstance(dyn_attrs, dict) and dyn_attrs:
            sd = payload.get("structured_data") or {}
            at = payload.get("attributes") or {}
            matched_attrs = sum(
                1 for k, v in dyn_attrs.items()
                if str(sd.get(k, at.get(k, ""))).lower() == str(v).lower()
            )
            if matched_attrs:
                score += 0.1 * matched_attrs

        return min(1.0, score)

    def build_filters_from_entities(
        self,
        entities: Dict,
        intent: str,
    ) -> Dict[str, Any]:
        """
        Build Qdrant filters from Brain #1 entity output.

        BUSINESS-AGNOSTIC:
        ------------------
        Instead of recognising only electronics specs, we:
        1. Extract any "number unit" pattern from technical_terms → dynamic attributes
        2. Parse "key: value" entity strings → dynamic attributes
        3. Pass unrecognised strings to L5/L6 (text layers) via the returned filter's
           "features" list so they're still used for scoring

        This works for any domain:
          - Laptop company:    "8GB RAM", "512GB SSD"  → {attributes: {ram: "8gb", storage: "512gb ssd"}}
          - Restaurant:        "Italian cuisine"       → features: ["Italian cuisine"]
          - Law firm:          "practice_area: IP"     → {attributes: {practice_area: "IP"}}
          - SaaS:              "Enterprise plan"       → features: ["Enterprise plan"]
          - Medical device:    "ISO-13485"             → features: ["ISO-13485"]
        """
        filters: Dict[str, Any] = {}
        dynamic_attrs: Dict[str, Any] = {}

        # ── Category filter from entity ────────────────────────────────────────
        if entities.get("category"):
            filters["category"] = entities["category"]

        # ── Price range filter ─────────────────────────────────────────────────
        if "price_min" in entities and entities["price_min"] is not None:
            filters["price_min"] = entities["price_min"]
        if "price_max" in entities and entities["price_max"] is not None:
            filters["price_max"] = entities["price_max"]

        # Also parse budget_indicators from Brain #1 for price range signals
        for bi in (entities.get("budget_indicators") or []):
            bi_lower = str(bi).lower()
            # "under $1000", "below 500", "max 2000"
            m_under = re.search(r"(?:under|below|max|<)\s*[\$₹€£]?\s*(\d[\d,]*)", bi_lower)
            m_above = re.search(r"(?:above|over|min|>)\s*[\$₹€£]?\s*(\d[\d,]*)", bi_lower)
            if m_under:
                try:
                    filters["price_max"] = float(m_under.group(1).replace(",", ""))
                except ValueError:
                    pass
            if m_above:
                try:
                    filters["price_min"] = float(m_above.group(1).replace(",", ""))
                except ValueError:
                    pass

        # ── Features filter ─────────────────────────────────────────────────────
        if entities.get("features"):
            filters["features"] = list(entities["features"])

        # ── Dynamic attribute extraction from technical_terms + features ────────
        tech_terms = list(entities.get("technical_terms") or [])
        feat_terms = list(entities.get("features") or [])
        all_terms  = tech_terms + feat_terms

        for term in all_terms:
            if not term or len(str(term).strip()) < 2:
                continue
            term_str = str(term).strip()

            # Try "key: value" format first (highest priority — explicit mapping)
            kv_match = _KV_ENTITY_PAT.match(term_str)
            if kv_match:
                attr_key   = kv_match.group(1).strip().lower().replace(" ", "_")
                attr_value = kv_match.group(2).strip()
                dynamic_attrs[attr_key] = attr_value
                continue

            # Try numeric+unit extraction — works for ANY domain with measurable specs
            unit_matches = _NUMERIC_UNIT_PAT.findall(term_str)
            if unit_matches:
                for num_str, unit_str in unit_matches:
                    # Normalise the key: "8gb ram" → key="ram", val={"gte":8, "lte":8}
                    # "512gb ssd" → key="storage", val="512gb ssd" (string match)
                    # "2.4ghz" → key="frequency", val={"gte":2.4, "lte":2.4}
                    unit_norm = unit_str.lower()
                    try:
                        num_val = float(num_str)
                    except ValueError:
                        continue

                    # Store as a normalised string value for MatchValue filtering
                    # (Qdrant payload stores specs as strings like "8GB", "512GB SSD")
                    # The async_repository._build_conditions handles the conversion.
                    term_lower = term_str.lower()
                    if unit_norm in ("gb", "tb", "mb"):
                        if any(w in term_lower for w in ("ssd", "hdd", "nvme", "storage", "disk")):
                            dynamic_attrs["storage"] = term_str
                        elif any(w in term_lower for w in ("ram", "memory", "ddr")):
                            dynamic_attrs["ram"] = term_str
                        else:
                            # ambiguous — store with the unit as key
                            dynamic_attrs[f"capacity_{unit_norm}"] = term_str
                    elif unit_norm in ("ghz", "mhz", "hz"):
                        dynamic_attrs["frequency"] = term_str
                    elif unit_norm in ("watt", "w"):
                        dynamic_attrs["power_watts"] = term_str
                    elif unit_norm in ("hp",):
                        dynamic_attrs["horsepower"] = term_str
                    elif unit_norm in ("cc", "l"):
                        dynamic_attrs["engine_displacement"] = term_str
                    elif unit_norm in ("km", "mile"):
                        dynamic_attrs["range_distance"] = term_str
                    elif unit_norm in ("nm",):
                        dynamic_attrs["process_node"] = term_str
                    elif unit_norm in ("mg", "g", "kg"):
                        dynamic_attrs["weight"] = term_str
                    elif unit_norm in ("ml", "l"):
                        dynamic_attrs["volume"] = term_str
                    elif unit_norm in ("rpm",):
                        dynamic_attrs["rpm"] = term_str
                    else:
                        # Generic: use normalised unit as key
                        dynamic_attrs[unit_norm] = term_str
                continue

            # No structured pattern — keep it in features for L5/L6 text matching
            # (already in filters["features"] if it came from entities.features)

        if dynamic_attrs:
            filters["attributes"] = dynamic_attrs

        # ── Chunk type filter based on intent ──────────────────────────────────
        _INTENT_TO_CHUNK = {
            "support_request":           "contact_support",
            "technical_support_request": "issue_resolution",
            "technical_assistance":      "issue_resolution",
            "complaint":                 "contact_support",
            "pricing_inquiry":           None,   # no filter — prices span multiple categories
            "product_inquiry":           "product_service",
            "feature_request":           "product_service",
            "general_inquiry":           "product_service",
            "offers_inquiry":            "offers_promotions",
            "shipping_inquiry":          "delivery_shipping",
            "company_inquiry":           "company_info",
            "educational_inquiry":       "educational_content",
            "refund_request":            "policies_legal",
            "billing_inquiry":           "policies_legal",
            "issue_inquiry":             "issue_resolution",
            "issue_resolution":          "issue_resolution",
        }
        mapped_type = _INTENT_TO_CHUNK.get(str(intent).lower())
        if mapped_type:
            filters["chunk_type"] = mapped_type

        return filters

    def has_meaningful_filters(self, filters: Dict) -> bool:
        """
        Check if filters are meaningful enough to run L4 metadata search.

        A filter is meaningful if it contains at least one of:
        - category / chunk_type  (narrows the Qdrant category bucket)
        - price_min / price_max  (numeric range)
        - features               (tag/capability list)
        - attributes             (any domain-specific dynamic attribute)

        This is intentionally domain-agnostic — no hardcoded electronics field names.
        """
        if not filters:
            return False

        meaningful_keys = {
            "category", "chunk_type",
            "price_min", "price_max",
            "features",
            "attributes",    # dynamic key from build_filters_from_entities
            "primary_category",
        }
        return any(k in filters for k in meaningful_keys)
