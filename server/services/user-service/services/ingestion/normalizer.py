"""
Data Normalizer + Quality Scorer
Transforms raw mapped rows into structured, AI-ready DataEntry payloads.

Changes from v1:
  - entities REMOVED (was producing noise: IDs as prices, SKUs as phones)
  - search_text rebuilt: no labels, no repetition, only meaningful data
    Format: "<name> price <price> INR stock <stock> supplier <supplier> status <status>"
  - quality_score rebuilt: based on actual fields present in the data,
    not a fixed list that penalises product catalogs for missing "description"
  - attributes dict added: typed numeric/string values for Qdrant filtering
  - RECOMMENDED_FIELDS updated per category to reflect real-world data shapes

Changes from v2 (this version):
  - numeric fields (price, stock) cast to int/float in structured_data
  - status normalized to canonical values: active / out_of_stock / limited_stock / inactive
  - search_text enforces strict template with normalized status
  - priority_score added: active=3, limited=2, out_of_stock=1, default=2
  - keywords list added: name tokens for fast keyword matching
  - ai_tags are now fully dynamic/contextual based on actual data values
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_FIELDS_THRESHOLD = 2

# ── Category-specific recommended fields ─────────────────────────────────────

RECOMMENDED_FIELDS: Dict[str, List[str]] = {
    "product_service":     ["name", "price", "stock", "status", "sku"],
    "pricing_payment":     ["name", "price", "plan_name", "payment_methods"],
    "contact_support":     ["phone", "email", "support_hours"],
    "offers_promotions":   ["name", "discount", "promo_code", "valid_until"],
    "delivery_shipping":   ["delivery_timeline", "shipping_charges", "return_window"],
    "company_info":        ["name", "description", "mission"],
    "policies_legal":      ["name", "policy_text"],
    "educational_content": ["question", "answer"],
    "uncategorized":       ["name"],
}

HIGH_VALUE_FIELDS: Dict[str, set] = {
    "product_service":     {"name", "price", "stock", "status"},
    "pricing_payment":     {"name", "price"},
    "contact_support":     {"phone", "email"},
    "offers_promotions":   {"name", "discount", "promo_code"},
    "delivery_shipping":   {"delivery_timeline"},
    "company_info":        {"name", "description"},
    "policies_legal":      {"name", "policy_text"},
    "educational_content": {"question", "answer"},
    "uncategorized":       {"name"},
}

# ── Numeric fields — cast to int/float in structured_data ─────────────────────
_NUMERIC_FIELDS = {"price", "original_price", "discount", "stock", "quantity", "rating", "weight"}
_STATUS_FIELDS  = {"status", "availability_status", "stock_status"}

# ── Status normalization map ──────────────────────────────────────────────────
# Maps any raw status string to one of 4 canonical values.
_STATUS_MAP: Dict[str, str] = {
    # active
    "active":        "active",
    "in stock":      "active",
    "instock":       "active",
    "available":     "active",
    "in-stock":      "active",
    "yes":           "active",
    "enabled":       "active",
    "live":          "active",
    # out_of_stock
    "out of stock":  "out_of_stock",
    "outofstock":    "out_of_stock",
    "out-of-stock":  "out_of_stock",
    "unavailable":   "out_of_stock",
    "sold out":      "out_of_stock",
    "soldout":       "out_of_stock",
    "no":            "out_of_stock",
    "0":             "out_of_stock",
    # limited_stock
    "limited":       "limited_stock",
    "limited stock": "limited_stock",
    "low stock":     "limited_stock",
    "low":           "limited_stock",
    "few left":      "limited_stock",
    "almost gone":   "limited_stock",
    # inactive
    "inactive":      "inactive",
    "disabled":      "inactive",
    "discontinued":  "inactive",
    "archived":      "inactive",
    "draft":         "inactive",
}

# ── Priority score map ────────────────────────────────────────────────────────
_PRIORITY_MAP: Dict[str, int] = {
    "active":        3,
    "limited_stock": 2,
    "out_of_stock":  1,
    "inactive":      1,
}

# ── AI routing tags ───────────────────────────────────────────────────────────
_CATEGORY_AI_TAGS: Dict[str, List[str]] = {
    "product_service":     ["product_info", "catalog"],
    "pricing_payment":     ["pricing_info", "plan_comparison", "payment_options"],
    "contact_support":     ["contact_context", "outreach_targeting"],
    "offers_promotions":   ["promotion", "urgency", "value_proposition"],
    "delivery_shipping":   ["logistics_info", "objection_handling"],
    "company_info":        ["trust_building", "credibility", "brand_context"],
    "policies_legal":      ["trust_building", "compliance"],
    "educational_content": ["objection_handling", "education", "onboarding"],
    "uncategorized":       ["general_context"],
}

_SUBTYPE_AI_TAGS: Dict[str, List[str]] = {
    "product":     ["catalog", "product_info"],
    "service":     ["service_info"],
    "plan":        ["plan_comparison", "pricing_tier"],
    "support":     ["support_routing"],
    "sales":       ["sales_context"],
    "faq":         ["faq_answer"],
    "tutorial":    ["how_to", "onboarding"],
    "troubleshoot":["error_resolution"],
    "seasonal":    ["urgency", "seasonal_offer"],
    "referral":    ["referral_program"],
    "privacy":     ["compliance"],
    "terms":       ["compliance"],
    "refund":      ["objection_handling"],
    "about":       ["brand_context"],
    "mission":     ["brand_context"],
}

# ── Fields to skip in search_text ────────────────────────────────────────────
_SKIP_IN_SEARCH = {
    "product_id", "sku", "created_date", "updated_date",
    "product_code", "item_id", "id",
}


def normalize_row(row: Dict[str, Any], category: str) -> Optional[Dict[str, Any]]:
    """
    Clean and normalize a single mapped row.
    - Casts numeric fields (price, stock, etc.) to int/float
    - Normalizes status to canonical values
    Returns None if too sparse.
    """
    cleaned: Dict[str, Any] = {}
    for key, value in row.items():
        if not key or not isinstance(key, str):
            continue
        clean_key = _clean_key(key)
        clean_val = _clean_value(value)
        if clean_val is None:
            continue

        # Cast numeric fields to proper types
        if clean_key in _NUMERIC_FIELDS:
            try:
                num_str = re.sub(r"[^\d.]", "", clean_val)
                if num_str:
                    cleaned[clean_key] = float(num_str) if "." in num_str else int(num_str)
                    continue
            except (ValueError, TypeError):
                pass

        # Normalize status to canonical value
        if clean_key in _STATUS_FIELDS:
            cleaned["status"] = _normalize_status(clean_val)
            continue

        cleaned[clean_key] = clean_val

    if len(cleaned) < MIN_FIELDS_THRESHOLD:
        logger.debug(f"Row rejected: only {len(cleaned)} non-empty fields")
        return None
    return cleaned


def build_entry_payload(
    structured_data: Dict[str, Any],
    category: str,
    subtype: Optional[str],
    source_type: str,
    raw_row: Optional[Dict[str, Any]] = None,
    quality_penalty: float = 0.0,
) -> Dict[str, Any]:
    """Build the full entry payload from a normalized row."""
    title          = _generate_title(structured_data, category)
    search_text    = _build_search_text(structured_data, category, subtype, title)
    quality        = _compute_quality_score(structured_data, category, quality_penalty)
    ai_tags        = _assign_ai_tags(structured_data, category, subtype)
    attributes     = _extract_attributes(structured_data)
    keywords       = _extract_keywords(structured_data, title)

    return {
        "title":           title,
        "structured_data": structured_data,
        "raw_data":        raw_row,
        "search_text":     search_text,
        "ai_tags":         ai_tags,
        "ai_relevance":    ai_tags,       # backward compat
        "entities":        [],            # intentionally empty
        "attributes":      attributes,
        "keywords":        keywords,
        "quality_score":   quality,
        "missing_fields":  [],
        "source_type":     source_type,
        "subtype":         subtype,
        "category":        category,
    }


# ── Title generation ──────────────────────────────────────────────────────────

_TITLE_PRIORITY = [
    "name", "product_name", "title", "plan_name", "service_name",
    "offer_name", "question", "policy_name", "contact_name", "description",
]


def _generate_title(data: Dict[str, Any], category: str) -> str:
    for field in _TITLE_PRIORITY:
        if field in data and data[field]:
            return str(data[field]).strip()[:200]
    for v in data.values():
        if v:
            return str(v).strip()[:200]
    return f"Untitled {category.replace('_', ' ').title()} Entry"


# ── Search text ───────────────────────────────────────────────────────────────

# Fields to SKIP in search_text (IDs, internal codes, dates — not useful for semantic search)
_SKIP_IN_SEARCH = {"product_id", "sku", "created_date", "updated_date", "product_code", "item_id"}

# Human-readable label overrides for search_text
_SEARCH_LABELS: Dict[str, str] = {
    "price":          "price",
    "original_price": "original price",
    "stock":          "stock",
    "status":         "status",
    "supplier":       "supplier",
    "brand":          "brand",
    "category":       "category",
    "subcategory":    "type",
    "discount":       "discount",
    "description":    "",   # value only, no label
    "name":           "",   # value only, no label
}


def _build_search_text(
    data: Dict[str, Any],
    category: str,
    subtype: Optional[str],
    title: str,
) -> str:
    """
    Build clean, embedding-optimized search text using strict template.

    Template: <name> price <price> INR stock <stock> supplier <supplier> status <status> category <category>

    Rules:
      - Start with the product/entry name
      - Include price with INR hint
      - Include stock quantity
      - Include supplier/brand
      - Include normalized status (active/out_of_stock/limited_stock)
      - Include product's own category
      - Include description/features if present
      - NO label prefixes like "Category:", "Type:", "Title:"
      - NO IDs, SKUs, internal codes, or dates
      - NO repetition of the same value

    Example: "Wooden Comb price 299 INR stock 150 supplier Cavolil Suppliers status active category Personal Care"
    """
    parts: List[str] = [title]
    seen: set = {title.lower()}

    def _add(value: Any, prefix: str = "") -> None:
        v = str(value).strip()
        if not v or v.lower() in seen:
            return
        seen.add(v.lower())
        parts.append(f"{prefix}{v}" if prefix else v)

    # Price with INR hint
    if "price" in data:
        price_val = data["price"]
        price_str = str(price_val)
        _add(price_str, "price ")
        if not any(c in price_str for c in ("₹", "$", "€", "£", "INR", "USD")):
            parts.append("INR")

    # Stock
    if "stock" in data:
        _add(data["stock"], "stock ")

    # Supplier / brand
    for field in ("supplier", "brand"):
        if field in data:
            _add(data[field], "supplier " if field == "supplier" else "brand ")
            break

    # Status (already normalized to canonical value in normalize_row)
    if "status" in data:
        _add(data["status"], "status ")

    # Product's own category (e.g. "Personal Care", "Hair Care")
    if "category" in data:
        _add(data["category"], "category ")

    # Subcategory
    if "subcategory" in data:
        _add(data["subcategory"])

    # Description / features
    for field in ("description", "features"):
        if field in data:
            _add(data[field])

    # Any remaining meaningful fields
    skip = _SKIP_IN_SEARCH | {
        "price", "stock", "supplier", "brand", "status",
        "category", "subcategory", "description", "features", "name",
    }
    for k, v in data.items():
        if k not in skip and v:
            _add(str(v))

    return " ".join(parts)[:1500]


# ── Attributes extraction ─────────────────────────────────────────────────────

def _normalize_status(raw: str) -> str:
    """Map any raw status string to a canonical value."""
    key = raw.strip().lower()
    return _STATUS_MAP.get(key, key)  # return as-is if not in map


def _extract_attributes(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract typed attributes for Qdrant payload filtering.

    Returns:
      {
        "price": 299,          # int/float
        "stock": 150,          # int
        "status": "active",    # canonical string
        "priority_score": 3,   # 3=active, 2=limited, 1=out_of_stock/inactive
        "supplier": "Cavolil", # string
        "category": "Personal Care",
        "name": "Wooden Comb",
      }
    """
    attrs: Dict[str, Any] = {}

    # Numeric fields — already cast in normalize_row, just copy typed values
    for field in _NUMERIC_FIELDS:
        if field in data and data[field] is not None:
            val = data[field]
            if isinstance(val, (int, float)):
                attrs[field] = val
            else:
                try:
                    num_str = re.sub(r"[^\d.]", "", str(val))
                    if num_str:
                        attrs[field] = float(num_str) if "." in num_str else int(num_str)
                except (ValueError, TypeError):
                    pass

    # Status — canonical value
    status_val = data.get("status")
    if status_val:
        canonical = str(status_val).strip().lower()
        # If already normalized (from normalize_row), use directly
        if canonical in ("active", "out_of_stock", "limited_stock", "inactive"):
            attrs["status"] = canonical
        else:
            attrs["status"] = _normalize_status(canonical)
    else:
        attrs["status"] = "active"  # default

    # Priority score based on status
    attrs["priority_score"] = _PRIORITY_MAP.get(attrs.get("status", "active"), 2)

    # String attributes for filtering
    for field in ("supplier", "brand", "category", "subcategory", "name"):
        if field in data and data[field]:
            attrs[field] = str(data[field]).strip()

    return attrs


def _extract_keywords(data: Dict[str, Any], title: str) -> List[str]:
    """
    Extract keyword list for fast keyword matching.

    Generates:
      - Full title as-is
      - Individual meaningful words from title (length > 2)
      - Category value
      - Supplier/brand value

    Example: ["wooden comb", "wooden", "comb", "personal care", "cavolil suppliers"]
    """
    keywords: List[str] = []
    seen: set = set()

    def _add_kw(text: str) -> None:
        t = text.strip().lower()
        if t and t not in seen and len(t) > 1:
            keywords.append(t)
            seen.add(t)

    # Full title
    _add_kw(title)

    # Individual words from title (skip stop words and short tokens)
    stop_words = {"a", "an", "the", "of", "in", "for", "and", "or", "to", "is", "are", "with"}
    for word in re.split(r"\s+", title.lower()):
        word = re.sub(r"[^a-z0-9]", "", word)
        if word and len(word) > 2 and word not in stop_words:
            _add_kw(word)

    # Category
    if "category" in data and data["category"]:
        _add_kw(str(data["category"]))

    # Supplier / brand
    for field in ("supplier", "brand"):
        if field in data and data[field]:
            _add_kw(str(data[field]))
            break

    return keywords[:20]  # cap at 20 keywords


# ── Quality scoring ───────────────────────────────────────────────────────────

def _compute_quality_score(
    data: Dict[str, Any],
    category: str,
    dedup_penalty: float = 0.0,
) -> float:
    """
    Score 0-100 based on what's actually in the data:

      completeness (50 pts) — % of category-recommended fields present
      high_value   (30 pts) — % of high-value fields present
      richness     (20 pts) — avg value length (capped at 100 chars)

    No penalty for fields that don't exist in the source data type.
    """
    recommended = RECOMMENDED_FIELDS.get(category, ["name"])
    present_rec = sum(1 for f in recommended if f in data and data[f])
    completeness = (present_rec / len(recommended)) * 50 if recommended else 50

    hv_fields = HIGH_VALUE_FIELDS.get(category, {"name"})
    hv_present = sum(1 for f in hv_fields if f in data and data[f])
    high_value = (hv_present / len(hv_fields)) * 30 if hv_fields else 30

    values = [str(v) for v in data.values() if v]
    avg_len = sum(len(v) for v in values) / len(values) if values else 0
    richness = min(avg_len / 100, 1.0) * 20

    total = completeness + high_value + richness - dedup_penalty
    return round(max(0.0, min(total, 100.0)), 1)


# ── AI tags ───────────────────────────────────────────────────────────────────

def _assign_ai_tags(
    data: Dict[str, Any],
    category: str,
    subtype: Optional[str],
) -> List[str]:
    """
    Assign contextual AI routing tags based on actual data values.
    Tags are dynamic — driven by what's in the data, not just the category.
    """
    tags = list(_CATEGORY_AI_TAGS.get(category, ["general_context"]))

    if subtype and subtype in _SUBTYPE_AI_TAGS:
        tags.extend(_SUBTYPE_AI_TAGS[subtype])

    # Pricing context
    if "price" in data or "cost" in data:
        tags.append("pricing_context")

    # Discount / promotion context
    if "discount" in data or "promo_code" in data or "offer_name" in data:
        tags.append("promotional_context")

    # Contact context
    if "email" in data or "phone" in data:
        tags.append("contact_context")

    # FAQ context
    if "question" in data:
        tags.append("faq_context")

    # Stock-based tags
    status = data.get("status", "")
    if isinstance(status, str):
        status_lower = status.lower()
        if status_lower == "out_of_stock":
            tags.append("out_of_stock")
        elif status_lower == "limited_stock":
            tags.append("limited_availability")
        elif status_lower == "active":
            tags.append("in_stock")

    # High-value item tag
    price = data.get("price")
    if price is not None:
        try:
            if float(str(price).replace(",", "")) >= 500:
                tags.append("premium_item")
        except (ValueError, TypeError):
            pass

    return list(dict.fromkeys(tags))  # deduplicate, preserve order


# ── Value cleaning ────────────────────────────────────────────────────────────

def _clean_key(key: str) -> str:
    key = key.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_") or "field"


def _clean_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in ("", "none", "null", "n/a", "na", "-", "\u2014", "undefined", "nan"):
        return None
    s = re.sub(r"\s+", " ", s)
    return s[:5000]


# ── Batch normalization ───────────────────────────────────────────────────────

def normalize_batch(
    rows: List[Dict[str, Any]],
    categories: List[str],
    subtypes: List[Optional[str]],
    source_type: str,
    raw_rows: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    accepted, rejected = [], []
    for i, (row, category, subtype) in enumerate(zip(rows, categories, subtypes)):
        raw = raw_rows[i] if raw_rows else None
        normalized = normalize_row(row, category)
        if normalized is None:
            rejected.append(f"Row {i + 1}: too sparse (< {MIN_FIELDS_THRESHOLD} non-empty fields)")
            continue
        payload = build_entry_payload(normalized, category, subtype, source_type, raw)
        accepted.append(payload)
    logger.info(f"Normalization: {len(accepted)} accepted, {len(rejected)} rejected")
    return accepted, rejected
