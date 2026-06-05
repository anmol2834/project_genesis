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
    ("product_id",   ["product id", "item id", "id", "product number", "item number", "record id"]),
    ("name",         ["name", "product name", "item name", "title", "full name", "entry name"]),
    ("description",  ["description", "details", "about", "summary", "overview", "info", "notes"]),
    ("sku",          ["sku", "stock keeping unit", "product code", "part number", "barcode", "item code"]),
    ("category",     ["category", "product category", "type", "kind", "group", "segment", "class", "department"]),
    ("subcategory",  ["subcategory", "sub category", "sub type", "product type"]),
    ("brand",        ["brand", "brand name", "manufacturer", "make"]),
    ("features",     ["features", "capabilities", "highlights", "key features", "benefits", "specifications", "specs"]),
    ("tags",         ["tags", "labels", "keywords", "topics"]),

    # ── Pricing ───────────────────────────────────────────────────────────
    ("price",        ["price", "cost", "amount", "fee", "rate", "charge", "selling price", "unit price", "mrp", "price inr", "price usd"]),
    ("original_price", ["original price", "list price", "market price", "base price", "regular price"]),
    ("discount",     ["discount", "offer", "deal", "reduction", "savings", "promo", "discount percent"]),
    ("currency",     ["currency", "currency code"]),

    # ── Inventory ─────────────────────────────────────────────────────────
    ("stock",        ["stock", "stock quantity", "quantity", "inventory", "units available", "qty", "in stock", "stock level", "available quantity"]),
    ("status",       ["status", "availability status", "product status", "state", "active", "enabled", "stock status"]),
    ("supplier",     ["supplier", "vendor", "manufacturer", "brand", "distributor", "source", "supplied by"]),
    ("location",     ["location", "warehouse", "store", "address", "city", "region"]),

    # ── Dates ─────────────────────────────────────────────────────────────
    ("created_date", ["created date", "creation date", "date added", "added on", "date created", "entry date", "launch date"]),
    ("updated_date", ["updated date", "last updated", "modified date", "last modified"]),
    ("valid_until",  ["expiry date", "expiry", "valid until", "expires", "end date", "deadline",
                      "offer expiry", "valid through", "offer end date"]),

    # ── Contact ───────────────────────────────────────────────────────────
    ("email",        ["email", "email address", "e-mail", "mail"]),
    ("phone",        ["phone", "phone number", "contact no", "mobile", "telephone", "cell", "contact number"]),
    ("website",      ["website", "url", "link", "web", "site"]),
    ("contact_name", ["contact name", "person name", "agent name", "representative name",
                      "staff name", "employee name", "full name of contact"]),
    ("department",   ["department", "team", "division", "support type", "contact type",
                      "role", "designation", "position"]),
    ("working_hours",["working hours", "support hours", "availability", "office hours",
                      "business hours", "timing", "timings", "hours of operation"]),

    # ── Pricing / Plans ───────────────────────────────────────────────────
    ("plan_name",    ["plan name", "plan", "tier", "subscription plan", "package"]),
    ("annual_price", ["annual price", "yearly price", "annual cost", "yearly cost"]),
    ("payment_methods", ["payment methods", "payment options", "accepted payments"]),
    ("refund_policy", ["refund policy", "return policy", "cancellation policy"]),

    # ── FAQ / Policy ──────────────────────────────────────────────────────
    ("question",     ["question", "query", "faq question", "q"]),
    ("answer",       ["answer", "response", "reply", "faq answer", "a"]),
    ("policy_text",  ["policy", "terms", "conditions", "rules", "guidelines", "policy text"]),

    # ── Offers ────────────────────────────────────────────────────────────
    ("promo_code",   ["promo code", "coupon code", "voucher", "discount code"]),
    ("offer_name",   ["offer name", "deal name", "promotion name"]),
    ("valid_until",  ["valid until", "offer expiry", "valid through", "offer end date"]),
]

# ── Keyword override rules ────────────────────────────────────────────────────
# Applied BEFORE the model. Exact/substring matches on lowercased header.
# Format: (substring_to_match, canonical_key)
# Ordered by specificity — more specific rules first.

_KEYWORD_OVERRIDES: List[Tuple[str, str]] = [
    ("product id",       "product_id"),
    ("item id",          "product_id"),
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
    ("product name",     "name"),
    ("item name",        "name"),
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
    ("working hours",    "working_hours"),
    ("support hours",    "working_hours"),
    ("office hours",     "working_hours"),
    ("availability",     "working_hours"),
    ("timing",           "working_hours"),
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
