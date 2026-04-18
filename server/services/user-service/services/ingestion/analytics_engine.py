"""
Data Analytics Engine — Computes and stores rich insights at ingestion time.

When a user imports any data (CSV, Excel, manual, sheets), this engine:
  1. Computes comprehensive statistical insights from ALL entries in the source
  2. Stores a single analytics object in Qdrant (collection: user_data_entries)
     with category="data_analytics" so automationservice can retrieve it
  3. Updates the analytics object on every new import (upsert by source_id)

Analytics stored per source (flexible, works for any business data):
  - Basic stats: count, min, max, mean, median, std_dev per numeric field
  - Price insights: min_price, max_price, avg_price, price_range, cheapest/priciest item
  - Category breakdown: count per category/subtype
  - Top items: top 5 by price, top 5 by quality_score
  - Data quality: avg quality score, missing field rates
  - Inventory: active/inactive/out_of_stock counts (if status field present)

The analytics object's search_text is a rich natural-language summary so
semantic search can find it for ANY insight-related query.

Multi-tenant: scoped by user_id — never cross-tenant.
"""
from __future__ import annotations
import logging
import statistics
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ANALYTICS_CATEGORY = "data_analytics"
_ANALYTICS_SUBTYPE  = "source_insights"


def compute_source_analytics(
    entries: List[Dict[str, Any]],
    source_id: str,
    source_name: str,
    category_hint: str = "",
) -> Dict[str, Any]:
    """
    Compute comprehensive analytics from a list of entry payloads.
    Works for ANY business data — products, contacts, offers, etc.

    Args:
        entries:       List of entry payloads (structured_data + metadata)
        source_id:     UUID of the source
        source_name:   Human-readable source name
        category_hint: Primary category of this source (optional)

    Returns:
        Analytics dict ready for Qdrant upsert
    """
    if not entries:
        return {}

    total = len(entries)

    # ── Collect all numeric values per field ──────────────────────────────
    numeric_fields: Dict[str, List[float]] = {}
    string_fields:  Dict[str, Dict[str, int]] = {}  # field → {value: count}
    status_counts:  Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    quality_scores: List[float] = []
    named_items: List[Dict[str, Any]] = []  # {name, price, quality, category}

    for entry in entries:
        sd = entry.get("structured_data") or {}
        attrs = entry.get("attributes") or {}
        merged = {**sd, **attrs}  # attributes take precedence for typed values

        # Quality score
        qs = entry.get("quality_score", 0.0)
        if qs:
            quality_scores.append(float(qs))

        # Category
        cat = entry.get("category", "")
        if cat and cat not in ("data_analytics",):
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Status
        status = merged.get("status", "")
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1

        # Named item tracking
        name = merged.get("name", "") or entry.get("title", "")
        price = merged.get("price")
        if name and not str(name).strip().isdigit():
            item: Dict[str, Any] = {
                "name":     str(name).strip()[:100],
                "category": cat,
                "quality":  float(qs),
            }
            if price is not None:
                try:
                    item["price"] = float(price)
                except (ValueError, TypeError):
                    pass
            named_items.append(item)

        # Numeric field collection
        for k, v in merged.items():
            if v is None:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                # Skip ratio/time values like 24 from "24/7"
                if k in ("priority_score",):
                    continue
                if k not in numeric_fields:
                    numeric_fields[k] = []
                numeric_fields[k].append(float(v))
            elif isinstance(v, str) and v.strip():
                # Track string field distributions (for category/status/type fields)
                if k in ("category", "status", "subtype", "department", "type"):
                    if k not in string_fields:
                        string_fields[k] = {}
                    string_fields[k][v] = string_fields[k].get(v, 0) + 1

    # ── Compute stats per numeric field ───────────────────────────────────
    field_stats: Dict[str, Dict[str, float]] = {}
    for field, values in numeric_fields.items():
        if not values:
            continue
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        field_stats[field] = {
            "count":    n,
            "min":      sorted_vals[0],
            "max":      sorted_vals[-1],
            "sum":      sum(sorted_vals),
            "mean":     round(statistics.mean(sorted_vals), 2),
            "median":   round(statistics.median(sorted_vals), 2),
            "std_dev":  round(statistics.stdev(sorted_vals), 2) if n > 1 else 0.0,
            "range":    round(sorted_vals[-1] - sorted_vals[0], 2),
            "p25":      round(sorted_vals[max(0, int(n * 0.25))], 2),
            "p75":      round(sorted_vals[min(n - 1, int(n * 0.75))], 2),
            "p90":      round(sorted_vals[min(n - 1, int(n * 0.90))], 2),
        }

    # ── Price-specific insights ───────────────────────────────────────────
    price_insights: Dict[str, Any] = {}
    if "price" in field_stats:
        ps = field_stats["price"]
        price_insights = {
            "min_price":    ps["min"],
            "max_price":    ps["max"],
            "avg_price":    ps["mean"],
            "median_price": ps["median"],
            "price_range":  ps["range"],
            "total_items_with_price": ps["count"],
        }
        # Find cheapest and most expensive named items
        priced_items = [i for i in named_items if "price" in i]
        if priced_items:
            cheapest  = min(priced_items, key=lambda x: x["price"])
            priciest  = max(priced_items, key=lambda x: x["price"])
            price_insights["cheapest_item"]  = cheapest["name"]
            price_insights["cheapest_price"] = cheapest["price"]
            price_insights["priciest_item"]  = priciest["name"]
            price_insights["priciest_price"] = priciest["price"]

            # Price distribution buckets
            prices = [i["price"] for i in priced_items]
            if prices:
                p_min, p_max = min(prices), max(prices)
                if p_max > p_min:
                    bucket_size = (p_max - p_min) / 3
                    price_insights["budget_items"]   = sum(1 for p in prices if p <= p_min + bucket_size)
                    price_insights["mid_range_items"] = sum(1 for p in prices if p_min + bucket_size < p <= p_min + 2 * bucket_size)
                    price_insights["premium_items"]  = sum(1 for p in prices if p > p_min + 2 * bucket_size)

    # ── Top items ─────────────────────────────────────────────────────────
    top_by_price = sorted(
        [i for i in named_items if "price" in i],
        key=lambda x: -x["price"]
    )[:5]
    bottom_by_price = sorted(
        [i for i in named_items if "price" in i],
        key=lambda x: x["price"]
    )[:5]
    top_by_quality = sorted(named_items, key=lambda x: -x.get("quality", 0))[:5]

    # ── Quality insights ──────────────────────────────────────────────────
    quality_insights: Dict[str, Any] = {}
    if quality_scores:
        quality_insights = {
            "avg_quality":    round(statistics.mean(quality_scores), 1),
            "min_quality":    round(min(quality_scores), 1),
            "max_quality":    round(max(quality_scores), 1),
            "high_quality_count": sum(1 for q in quality_scores if q >= 80),
            "low_quality_count":  sum(1 for q in quality_scores if q < 60),
        }

    # ── Build analytics structured_data ──────────────────────────────────
    analytics_data: Dict[str, Any] = {
        # Core counts
        "total_entries":    total,
        "source_id":        source_id,
        "source_name":      source_name,
        "primary_category": category_hint or (max(category_counts, key=category_counts.get) if category_counts else ""),
        "computed_at":      datetime.utcnow().isoformat(),

        # Category breakdown
        "category_breakdown": category_counts,

        # Status breakdown (if applicable)
        "status_breakdown": status_counts,

        # Numeric field statistics
        "field_stats": field_stats,

        # Price insights (most commonly queried)
        "price_insights": price_insights,

        # Top/bottom items
        "top_by_price":    [{"name": i["name"], "price": i.get("price")} for i in top_by_price],
        "bottom_by_price": [{"name": i["name"], "price": i.get("price")} for i in bottom_by_price],
        "top_by_quality":  [{"name": i["name"], "quality": i.get("quality")} for i in top_by_quality],

        # Quality
        "quality_insights": quality_insights,

        # All item names (for "list all products" queries)
        "all_item_names": [i["name"] for i in named_items if i.get("name")][:100],
    }

    # ── Build rich search_text for semantic retrieval ─────────────────────
    search_text = _build_analytics_search_text(analytics_data, source_name)

    return {
        "category":        _ANALYTICS_CATEGORY,
        "subtype":         _ANALYTICS_SUBTYPE,
        "title":           f"Analytics: {source_name}",
        "search_text":     search_text,
        "structured_data": analytics_data,
        "attributes":      {
            "source_id":     source_id,
            "total_entries": total,
            "min_price":     price_insights.get("min_price"),
            "max_price":     price_insights.get("max_price"),
            "avg_price":     price_insights.get("avg_price"),
            "cheapest_item": price_insights.get("cheapest_item", ""),
            "priciest_item": price_insights.get("priciest_item", ""),
            "status":        "active",
            "priority_score": 5,  # analytics always high priority
        },
        "ai_tags": [
            "data_analytics", "insights", "statistics", "pricing_analysis",
            "catalog_summary", "business_intelligence", "aggregation",
        ],
        "keywords": _build_analytics_keywords(analytics_data, source_name),
        "quality_score": 95.0,
        "source_type":   "analytics",
    }


def _build_analytics_search_text(data: Dict[str, Any], source_name: str) -> str:
    """Build rich natural-language search text for the analytics object."""
    parts: List[str] = []

    total = data.get("total_entries", 0)
    parts.append(f"{source_name} has {total} total entries.")

    pi = data.get("price_insights", {})
    if pi:
        if pi.get("max_price") is not None:
            parts.append(
                f"Most expensive item is {pi.get('priciest_item', 'unknown')} "
                f"at {pi['max_price']:,.0f}."
            )
        if pi.get("min_price") is not None:
            parts.append(
                f"Cheapest item is {pi.get('cheapest_item', 'unknown')} "
                f"at {pi['min_price']:,.0f}."
            )
        if pi.get("avg_price") is not None:
            parts.append(f"Average price is {pi['avg_price']:,.0f}.")
        if pi.get("price_range") is not None:
            parts.append(f"Price range is {pi['price_range']:,.0f}.")

    cat_breakdown = data.get("category_breakdown", {})
    if cat_breakdown:
        cat_str = ", ".join(f"{k}: {v}" for k, v in cat_breakdown.items())
        parts.append(f"Category breakdown: {cat_str}.")

    status_breakdown = data.get("status_breakdown", {})
    if status_breakdown:
        active = status_breakdown.get("active", 0)
        if active:
            parts.append(f"{active} active items.")

    all_names = data.get("all_item_names", [])
    if all_names:
        parts.append(f"Items include: {', '.join(all_names[:20])}.")

    qi = data.get("quality_insights", {})
    if qi.get("avg_quality"):
        parts.append(f"Average data quality score: {qi['avg_quality']}.")

    # Add insight keywords for semantic search
    parts.append(
        "statistics insights analytics summary count total highest lowest average "
        "most expensive cheapest price range distribution breakdown"
    )

    return " ".join(parts)[:2000]


def _build_analytics_keywords(data: Dict[str, Any], source_name: str) -> List[str]:
    """Build keywords for the analytics object."""
    kws = [
        "analytics", "insights", "statistics", "summary", "total", "count",
        "highest", "lowest", "average", "mean", "median", "price range",
        "most expensive", "cheapest", "distribution", "breakdown",
        source_name.lower(),
    ]
    pi = data.get("price_insights", {})
    if pi.get("priciest_item"):
        kws.append(pi["priciest_item"].lower())
    if pi.get("cheapest_item"):
        kws.append(pi["cheapest_item"].lower())
    for name in (data.get("all_item_names") or [])[:10]:
        kws.append(name.lower())
    return list(dict.fromkeys(kws))[:50]  # deduplicate, cap at 50


def upsert_analytics_to_qdrant(
    analytics_payload: Dict[str, Any],
    user_id: str,
    source_id: str,
) -> Optional[str]:
    """
    Upsert the analytics object to Qdrant.
    Uses a deterministic point ID based on user_id + source_id so it's
    always updated in-place (never duplicated).
    """
    if not analytics_payload:
        return None

    try:
        from services.ingestion.embedding_service import embed_texts, COLLECTION_NAME
        from shared.vector_db import get_qdrant_client
        from qdrant_client.models import PointStruct

        client = get_qdrant_client()

        # Deterministic point ID for this user+source analytics
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"analytics:{user_id}:{source_id}"))

        # Embed the search_text
        search_text = analytics_payload.get("search_text", "")
        vecs = embed_texts([search_text])
        vector = vecs[0].tolist()

        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "user_id":         user_id,
                "entry_id":        point_id,
                "source_id":       source_id,
                "category":        _ANALYTICS_CATEGORY,
                "subtype":         _ANALYTICS_SUBTYPE,
                "title":           analytics_payload.get("title", ""),
                "search_text":     search_text[:500],
                "ai_tags":         analytics_payload.get("ai_tags", []),
                "keywords":        analytics_payload.get("keywords", []),
                "attributes":      analytics_payload.get("attributes", {}),
                "structured_data": analytics_payload.get("structured_data", {}),
                "status":          "active",
                "priority_score":  5,
                "quality_score":   95.0,
                "source_type":     "analytics",
                "updated_at":      datetime.utcnow().isoformat(),
            },
        )

        client.upsert(collection_name=COLLECTION_NAME, points=[point])
        logger.info(
            "Analytics upserted to Qdrant | user=%s source=%s point=%s",
            user_id[:8], source_id[:8], point_id[:12],
        )
        return point_id

    except Exception as e:
        logger.error("Analytics upsert failed: %s", e, exc_info=True)
        return None
