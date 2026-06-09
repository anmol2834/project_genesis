"""
Intelligent Column Mapper
Maps arbitrary CSV/sheet headers to canonical field names using
e5-base-v2 semantic similarity + keyword override rules.

Design principles:
  - NEVER produce duplicate suffixes like sku_2, availability_2
  - Each canonical key is assigned to at most ONE source column
    (the highest-confidence match wins; lower-confidence duplicates
     fall back to a slugified version of the original header)
  - Keyword override rules fire before the model for common exact matches
    (e.g. "Product ID" → product_id, "Stock Quantity" → stock)
"""

import logging
import re
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Canonical field registry ──────────────────────────────────────────────────
# (canonical_key, list_of_representative_phrases)
# Phrases are embedded and the closest match to each header wins.

CANONICAL_FIELDS: List[Tuple[str, List[str]]] = [
    # ── Identity / Product ────────────────────────────────────────────────
    ("product_id",   ["product id", "item id", "id", "product number", "item number", "record id",
                      "support id", "resource id", "shipping id", "offer id", "policy id",
                      "comp id", "entry id", "row id", "reference id"]),
    ("name",         ["name", "product name", "item name", "title", "full name", "entry name",
                      "policy name", "offer name", "offer title", "campaign name",
                      "shipping method", "information type", "resource title",
                      "department name", "service name", "plan name"]),
    ("description",  ["description", "details", "about", "summary", "overview", "info", "notes",
                      "value", "policy summary", "policy details", "content", "body"]),
    ("sku",          ["sku", "stock keeping unit", "product code", "part number", "barcode", "item code"]),
    ("category",     ["category", "product category", "type", "kind", "group", "segment", "class", "department",
                      "offer type", "resource type", "information category"]),
    ("subcategory",  ["subcategory", "sub category", "sub type", "product type"]),
    ("brand",        ["brand", "brand name", "manufacturer", "make"]),
    ("features",     ["features", "capabilities", "highlights", "key features", "benefits",
                      "specifications", "specs", "skill level", "level"]),
    ("tags",         ["tags", "labels", "keywords", "topics"]),

    # ── Pricing / Offers ──────────────────────────────────────────────────
    ("price",        ["price", "cost", "amount", "fee", "rate", "charge", "selling price",
                      "unit price", "mrp", "price inr", "price usd", "shipping cost",
                      "shipping fee", "shipping charges", "delivery cost", "delivery fee"]),
    ("original_price", ["original price", "list price", "market price", "base price", "regular price"]),
    ("discount",     ["discount", "offer value", "deal value", "reduction", "savings", "promo",
                      "discount percent", "offer amount"]),
    ("currency",     ["currency", "currency code"]),
    ("offer_name",   ["offer name", "offer title", "deal name", "promotion name", "campaign name"]),
    ("promo_code",   ["promo code", "coupon code", "voucher", "discount code"]),
    ("offer_type",   ["offer type", "promotion type", "deal type", "discount type"]),

    # ── Dates ─────────────────────────────────────────────────────────────
    ("created_date", ["created date", "creation date", "date added", "added on", "date created",
                      "entry date", "launch date", "effective date", "start date"]),
    ("updated_date", ["updated date", "last updated", "modified date", "last modified"]),
    ("valid_until",  ["expiry date", "expiry", "valid until", "expires", "end date", "deadline",
                      "offer expiry", "valid through", "offer end date", "end_date"]),

    # ── Inventory / Status ────────────────────────────────────────────────
    ("stock",        ["stock", "stock quantity", "quantity", "inventory", "units available",
                      "qty", "in stock", "stock level", "available quantity"]),
    ("status",       ["status", "availability status", "product status", "state", "stock status",
                      "record status", "entry status", "active status", "is active"]),
    ("supplier",     ["supplier", "vendor", "manufacturer", "distributor", "source", "supplied by"]),
    ("location",     ["location", "warehouse", "store", "address", "city", "region"]),

    # ── Delivery / Shipping specific ──────────────────────────────────────
    ("delivery_timeline",  ["delivery time", "delivery timeline", "delivery period", "transit time",
                             "delivery days", "shipping time", "estimated delivery"]),
    ("shipping_charges",   ["shipping cost", "shipping fee", "delivery cost", "delivery fee",
                             "shipping charges", "freight cost"]),
    ("return_window",      ["return window", "return period", "return policy days",
                             "exchange period", "replacement window"]),
    ("tracking_info",      ["tracking", "tracking available", "tracking included", "shipment tracking"]),
    ("serviceable_regions",["region", "serviceable area", "delivery zone", "coverage area",
                             "shipping region", "service area"]),
    ("shipping_notes",     ["notes", "additional info", "shipping notes", "special notes", "remarks"]),

    # ── Contact ───────────────────────────────────────────────────────────
    ("email",        ["email", "email address", "e-mail", "mail", "support email", "contact email"]),
    ("phone",        ["phone", "phone number", "contact no", "mobile", "telephone", "cell",
                      "contact number", "support phone"]),
    ("website",      ["website", "url", "link", "web", "site"]),
    ("contact_name", ["contact name", "person name", "agent name", "representative name",
                      "staff name", "employee name", "full name of contact"]),
    ("department",   ["department", "team", "division", "support type", "contact type",
                      "role", "designation", "position"]),
    ("working_hours",["working hours", "support hours", "office hours",
                      "business hours", "timing", "timings", "hours of operation",
                      "availability hours", "open hours"]),
    ("preferred_channel", ["preferred channel", "contact channel", "channel", "contact method",
                            "preferred contact"]),

    # ── Pricing / Plans ───────────────────────────────────────────────────
    ("plan_name",    ["plan name", "plan", "tier", "subscription plan", "package"]),
    ("annual_price", ["annual price", "yearly price", "annual cost", "yearly cost"]),
    ("payment_methods", ["payment methods", "payment options", "accepted payments"]),
    ("refund_policy", ["refund policy", "return policy", "cancellation policy"]),

    # ── FAQ / Policy ──────────────────────────────────────────────────────
    ("question",     ["question", "query", "faq question", "q"]),
    ("answer",       ["answer", "response", "reply", "faq answer", "a"]),
    ("policy_text",  ["policy", "policy text", "terms", "conditions", "rules", "guidelines",
                      "policy body", "policy content"]),
    ("visibility",   ["visibility", "access level", "audience", "public or internal", "scope"]),

    # ── Company Info specific ─────────────────────────────────────────────
    ("information_type", ["information type", "info type", "field type", "data type", "record type"]),
    ("mission",      ["mission", "mission statement", "company mission"]),
    ("vision",       ["vision", "vision statement", "company vision"]),

    # ── Educational / Support specific ───────────────────────────────────
    ("resource_type",  ["resource type", "content type", "material type", "format",
                         "learning format", "training type"]),
    ("skill_level",    ["skill level", "difficulty", "level", "beginner intermediate advanced",
                         "expertise level", "audience level"]),
    ("topic",          ["topic", "subject", "area", "domain", "focus area"]),
]

# ── Keyword override rules ────────────────────────────────────────────────────
# Applied BEFORE the model. Exact/substring matches on lowercased header.
# Format: (substring_to_match, canonical_key)
# Ordered by specificity — more specific rules first.

_KEYWORD_OVERRIDES: List[Tuple[str, str]] = [
    # ── ID fields — must fire first ───────────────────────────────────────
    ("product_id",       "product_id"),
    ("support_id",       "product_id"),
    ("resource_id",      "product_id"),
    ("shipping_id",      "product_id"),
    ("offer_id",         "product_id"),
    ("policy_id",        "product_id"),
    ("record_id",        "product_id"),
    ("comp_id",          "product_id"),
    ("item id",          "product_id"),

    # ── Name / Title fields ───────────────────────────────────────────────
    ("policy name",      "name"),
    ("offer title",      "offer_name"),     # offer_title → offer_name (not name, to avoid clash with campaign_name)
    ("offer name",       "offer_name"),
    ("campaign name",    "name"),           # campaign_name is the primary name for offers
    ("shipping method",  "name"),
    ("information type", "name"),
    ("product name",     "name"),
    ("item name",        "name"),
    ("resource title",   "name"),

    # ── Description / Summary ─────────────────────────────────────────────
    ("summary",          "description"),
    ("policy summary",   "description"),
    # company info CSV: "value" column holds the actual data (e.g. "IngenAI", "2024")
    # We map it to "field_value" to avoid clash with the "description" column,
    # then normalize_row merges them into a rich description.
    ("value",            "field_value"),

    # ── Delivery / Shipping specific ──────────────────────────────────────
    ("delivery time",    "delivery_timeline"),
    ("delivery_time",    "delivery_timeline"),
    ("shipping cost",    "shipping_charges"),
    ("shipping_cost",    "shipping_charges"),
    ("return window",    "return_window"),
    ("tracking",         "tracking_info"),
    ("shipping notes",   "shipping_notes"),
    ("shipping_notes",   "shipping_notes"),

    # ── Offer / Discount fields ───────────────────────────────────────────
    ("offer value",      "discount"),
    ("offer_value",      "discount"),
    ("offer type",       "offer_type"),
    ("offer_type",       "offer_type"),
    ("start date",       "created_date"),
    ("start_date",       "created_date"),
    ("end date",         "valid_until"),
    ("end_date",         "valid_until"),

    # ── Contact/Support specific ──────────────────────────────────────────
    ("preferred channel","preferred_channel"),
    ("support hours",    "working_hours"),
    ("office hours",     "working_hours"),
    ("working hours",    "working_hours"),
    ("business hours",   "working_hours"),
    ("timing",           "working_hours"),
    # "availability" alone defaults to "status" (e.g. Active/Seasonal/Paused).
    # Contact CSVs that mean "working hours" by availability will be caught
    # by the normalizer's value-aware logic (detects "24/7", "Mon-Fri" patterns).
    ("availability",     "status"),

    # ── Education specific ────────────────────────────────────────────────
    ("resource type",    "resource_type"),
    ("skill level",      "skill_level"),

    # ── Policy specific ───────────────────────────────────────────────────
    ("visibility",       "visibility"),
    ("effective date",   "created_date"),

    # ── Company Info specific ─────────────────────────────────────────────
    ("information_type", "information_type"),

    # ── Generic high-priority mappings ────────────────────────────────────
    ("stock quantity",   "stock"),
    ("qty",              "stock"),
    ("quantity",         "stock"),
    ("stock keeping",    "sku"),
    ("sku",              "sku"),
    ("part number",      "sku"),
    ("product code",     "sku"),
    ("item code",        "sku"),
    ("supplier",         "supplier"),
    ("vendor",           "supplier"),
    ("created date",     "created_date"),
    ("creation date",    "created_date"),
    ("date added",       "created_date"),
    ("updated date",     "updated_date"),
    ("last updated",     "updated_date"),
    ("expiry",           "valid_until"),
    ("valid until",      "valid_until"),
    ("offer expiry",     "valid_until"),
    ("valid through",    "valid_until"),
    ("offer end",        "valid_until"),
    ("price",            "price"),
    ("cost",             "price"),
    ("mrp",              "price"),
    ("status",           "status"),
    ("category",         "category"),
    ("brand",            "brand"),
    ("description",      "description"),
    ("discount",         "discount"),
    ("email",            "email"),
    ("phone",            "phone"),
    ("mobile",           "phone"),
    ("website",          "website"),
    ("url",              "website"),
    ("contact name",     "contact_name"),
    ("person name",      "contact_name"),
    ("agent name",       "contact_name"),
    ("representative",   "contact_name"),
    ("department",       "department"),
]

# Flatten to (canonical_key, phrase) pairs for embedding
_FIELD_PHRASES: List[Tuple[str, str]] = [
    (key, phrase)
    for key, phrases in CANONICAL_FIELDS
    for phrase in phrases
]

_model = None
_phrase_embeddings = None
_phrase_keys: List[str] = []


def _get_model():
    global _model
    if _model is None:
        from services.ingestion.model_singleton import get_shared_model
        _model = get_shared_model()
        logger.info("Column mapper: e5-base-v2 loaded")
    return _model


def _get_phrase_embeddings():
    global _phrase_embeddings, _phrase_keys
    if _phrase_embeddings is None:
        model = _get_model()
        phrases = [f"query: {p}" for _, p in _FIELD_PHRASES]
        _phrase_keys = [k for k, _ in _FIELD_PHRASES]
        _phrase_embeddings = model.encode(phrases, normalize_embeddings=True, batch_size=64)
        logger.info(f"Column mapper: {len(phrases)} phrase embeddings pre-computed")
    return _phrase_embeddings, _phrase_keys


def _keyword_override(header: str) -> str | None:
    """Return canonical key if a keyword rule matches, else None."""
    h = header.lower().strip()
    for substring, canonical in _KEYWORD_OVERRIDES:
        if substring in h:
            return canonical
    return None


def map_columns(
    headers: List[str],
    confidence_threshold: float = 0.52,
) -> Dict[str, Dict]:
    """
    Map raw column headers to canonical field names.

    Rules:
      1. Keyword override fires first (exact substring match).
      2. Semantic similarity via e5-base-v2 for remaining headers.
      3. Each canonical key is assigned to at most ONE header
         (highest confidence wins; duplicates fall back to slug).
      4. NEVER produces sku_2, availability_2, etc.

    Returns dict keyed by original header:
      { "Product ID": {"mapped_to": "product_id", "confidence": 1.0, ...} }
    """
    if not headers:
        return {}

    # ── Pass 1: keyword overrides ─────────────────────────────────────────
    override_results: Dict[str, str] = {}
    remaining: List[str] = []
    for h in headers:
        key = _keyword_override(h)
        if key:
            override_results[h] = key
        else:
            remaining.append(h)

    # ── Pass 2: semantic similarity for remaining headers ─────────────────
    semantic_results: Dict[str, Tuple[str, float]] = {}
    if remaining:
        model = _get_model()
        phrase_embs, phrase_keys = _get_phrase_embeddings()
        header_queries = [f"query: {h.lower()}" for h in remaining]
        header_embs = model.encode(header_queries, normalize_embeddings=True, batch_size=32)

        for i, header in enumerate(remaining):
            sims = np.dot(phrase_embs, header_embs[i])
            best_idx = int(np.argmax(sims))
            best_score = float(sims[best_idx])
            best_key = phrase_keys[best_idx]
            semantic_results[header] = (best_key, round(best_score, 4))

    # ── Pass 3: resolve conflicts — each canonical key used at most once ──
    # Collect all (header, canonical_key, confidence) candidates
    candidates: List[Tuple[str, str, float]] = []
    for h, key in override_results.items():
        candidates.append((h, key, 1.0))  # overrides have max confidence
    for h, (key, score) in semantic_results.items():
        candidates.append((h, key, score))

    # Sort by confidence descending so highest-confidence mapping wins
    candidates.sort(key=lambda x: -x[2])

    assigned_canonical: set = set()
    results: Dict[str, Dict] = {}

    for header, canonical, confidence in candidates:
        if header in results:
            continue  # already assigned

        if confidence >= confidence_threshold and canonical not in assigned_canonical:
            # Accept this mapping
            assigned_canonical.add(canonical)
            results[header] = {
                "mapped_to":       canonical,
                "confidence":      confidence,
                "suggested_label": canonical.replace("_", " ").title(),
            }
        else:
            # Fall back to slugified original — never produce _2 suffixes
            slug = _slugify(header)
            results[header] = {
                "mapped_to":       slug,
                "confidence":      confidence,
                "suggested_label": header.strip().title(),
            }
            if confidence >= confidence_threshold:
                logger.debug(f"Conflict: '{header}' → '{canonical}' already taken, using slug '{slug}'")
            else:
                logger.debug(f"Low-confidence: '{header}' → '{slug}' ({confidence:.3f})")

    high_conf = sum(1 for v in results.values() if v["confidence"] >= confidence_threshold)
    logger.info(f"Column mapping: {len(headers)} headers, {high_conf} high-confidence")
    return results


def apply_mapping(rows: List[Dict], mapping: Dict[str, Dict]) -> List[Dict]:
    """
    Apply column mapping to rows. Renames keys to canonical names.
    No duplicate suffixes — each canonical key appears at most once per row.
    """
    mapped_rows = []
    for row in rows:
        new_row: Dict = {}
        for orig_key, value in row.items():
            canonical = mapping.get(orig_key, {}).get("mapped_to", _slugify(orig_key))
            # If canonical already taken in this row, keep original slug
            if canonical in new_row:
                canonical = _slugify(orig_key)
            new_row[canonical] = value
        mapped_rows.append(new_row)
    return mapped_rows


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "field"
