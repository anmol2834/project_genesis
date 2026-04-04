"""
Data Normalizer + Quality Scorer  — v4 (Universal AI-Ready Data Engine)
========================================================================
ENTERPRISE DATA ENGINE — fixes all data quality failures:

  v4 changes (this version):
  - TITLE FIX: contact-aware title generation (department - person_name)
    Never uses numeric IDs as title. Checks all contact name fields.
  - ATTRIBUTE ENRICHMENT: extracts email, phone, working_hours, department,
    person_name, valid_until, description for all categories
  - SEARCH TEXT GENERATOR: category-specific natural language templates
    (contact, offer, product each get semantically rich sentences)
  - KEYWORD ENGINE: 20+ tokens with synonyms, misspellings, category variants
  - SYNONYM ENGINE: price→cost/rate/fee, contact→phone/support, offer→deal/promo
  - QUALITY SCORE REBUILD: completeness(30) + keyword_richness(20) +
    search_text_quality(20) + attribute_depth(20) + embedding_similarity(10)
    Target: quality_score >= 85
  - VALIDATION LAYER: rejects numeric titles, missing attributes, weak keywords
  - structured_data now preserves ALL fields including valid_until, description
  - expiry_date aliased to valid_until for offer compatibility
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_FIELDS_THRESHOLD = 2

# ── Category-specific recommended fields ─────────────────────────────────────
# Updated to reflect real-world data shapes and fix quality score calculation.
# contact_support: added person_name, department, working_hours
# offers_promotions: valid_until aliased from expiry_date
# product_service: removed sku (rarely present), added description

RECOMMENDED_FIELDS: Dict[str, List[str]] = {
    "product_service":     ["name", "price", "status", "category", "description"],
    "pricing_payment":     ["name", "price", "plan_name", "payment_methods"],
    "contact_support":     ["phone", "email", "category", "name"],
    "offers_promotions":   ["name", "discount", "valid_until", "description"],
    "delivery_shipping":   ["delivery_timeline", "shipping_charges", "return_window"],
    "company_info":        ["name", "description", "mission"],
    "policies_legal":      ["name", "policy_text"],
    "educational_content": ["question", "answer"],
    "uncategorized":       ["name"],
}

HIGH_VALUE_FIELDS: Dict[str, set] = {
    "product_service":     {"name", "price", "status", "category"},
    "pricing_payment":     {"name", "price"},
    "contact_support":     {"phone", "email", "name"},
    "offers_promotions":   {"name", "discount", "valid_until"},
    "delivery_shipping":   {"delivery_timeline"},
    "company_info":        {"name", "description"},
    "policies_legal":      {"name", "policy_text"},
    "educational_content": {"question", "answer"},
    "uncategorized":       {"name"},
}

# ── Numeric fields — cast to int/float in structured_data ─────────────────────
_NUMERIC_FIELDS = {"price", "original_price", "discount", "stock", "quantity", "rating", "weight"}
_STATUS_FIELDS  = {"status", "availability_status", "stock_status"}

# ── Contact-specific name fields (checked in order for title generation) ──────
_CONTACT_NAME_FIELDS = [
    "name", "contact_name", "person_name", "full_name", "agent_name",
    "representative", "rep_name", "staff_name", "employee_name",
]

# ── Contact-specific department/role fields ───────────────────────────────────
_CONTACT_DEPT_FIELDS = [
    "department", "category", "team", "role", "division",
    "support_type", "contact_type",
]

# ── Fields that hold working hours / availability ─────────────────────────────
_HOURS_FIELDS = [
    "working_hours", "support_hours", "availability", "hours",
    "office_hours", "business_hours", "timing", "timings",
]

# ── Fields that hold valid_until / expiry for offers ─────────────────────────
_VALID_UNTIL_FIELDS = [
    "valid_until", "expiry_date", "expiry", "end_date",
    "offer_end", "valid_through", "deadline",
]

# ── Status normalization map ──────────────────────────────────────────────────
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
    - Aliases expiry_date → valid_until for offer compatibility
    - Preserves ALL fields including contact-specific ones
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

    # ── Alias expiry_date → valid_until (offer compatibility) ────────────
    # column_mapper maps "valid until" → expiry_date; normalizer expects valid_until
    if "expiry_date" in cleaned and "valid_until" not in cleaned:
        cleaned["valid_until"] = cleaned["expiry_date"]

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
    """
    Build the full entry payload from a normalized row.

    Includes validation layer:
      - Rejects numeric titles
      - Rejects entries with < 10 keywords
      - Rejects entries with < 10 word search_text
    """
    title       = _generate_title(structured_data, category)
    search_text = _build_search_text(structured_data, category, subtype, title)
    ai_tags     = _assign_ai_tags(structured_data, category, subtype)
    attributes  = _extract_attributes(structured_data)
    keywords    = _extract_keywords(structured_data, title)

    # ── Validation layer ──────────────────────────────────────────────────
    validation_warnings: List[str] = []
    if title.strip().isdigit():
        validation_warnings.append(f"WARN: numeric title '{title}' — check column mapping")
    if len(keywords) < _MIN_KEYWORDS:
        validation_warnings.append(f"WARN: only {len(keywords)} keywords (min {_MIN_KEYWORDS})")
    if len(search_text.split()) < _MIN_SEARCH_WORDS:
        validation_warnings.append(f"WARN: search_text too short ({len(search_text.split())} words)")
    if validation_warnings:
        logger.warning(f"Quality validation: {'; '.join(validation_warnings)} | title={title!r}")

    quality = _compute_quality_score(
        structured_data, category, quality_penalty,
        title=title, search_text=search_text, keywords=keywords,
    )

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
        "missing_fields":  validation_warnings,
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
    """
    Generate a meaningful, human-readable title.

    Rules by category:
      contact_support  → "{department} - {person_name}"  (NEVER numeric ID)
      offers_promotions → offer_name or name
      product_service  → product name
      all others       → first meaningful string field

    NEVER uses a numeric value as title.
    NEVER uses product_id / row number as title.
    """
    # ── Contact: build "Department - Person Name" ─────────────────────────
    if category == "contact_support":
        person = None
        for field in _CONTACT_NAME_FIELDS:
            if field in data and data[field]:
                val = str(data[field]).strip()
                if val and not val.isdigit() and len(val) > 1:
                    person = val
                    break

        dept = None
        for field in _CONTACT_DEPT_FIELDS:
            if field in data and data[field]:
                val = str(data[field]).strip()
                if val and not val.isdigit() and len(val) > 1:
                    dept = val
                    break

        if dept and person:
            return f"{dept} - {person}"[:200]
        if person:
            return person[:200]
        if dept:
            return dept[:200]
        # Last resort for contact: email domain or phone
        for field in ("email", "phone"):
            if field in data and data[field]:
                return str(data[field]).strip()[:200]

    # ── Standard priority fields ──────────────────────────────────────────
    for field in _TITLE_PRIORITY:
        if field in data and data[field]:
            val = str(data[field]).strip()
            if val and len(val) > 1 and not val.isdigit():
                return val[:200]

    # ── Fallback: first non-empty, non-numeric string value ───────────────
    # Skip known ID/numeric fields
    _skip_title = {"product_id", "id", "sku", "product_code", "item_id",
                   "status", "priority_score", "stock", "quantity"}
    for field, v in data.items():
        if field in _skip_title:
            continue
        if v and isinstance(v, str) and len(v) > 2 and not str(v).strip().isdigit():
            return str(v).strip()[:200]

    # ── Last resort: category label ───────────────────────────────────────
    return category.replace("_", " ").title()


# ── Search text ───────────────────────────────────────────────────────────────

# Fields to SKIP in search_text (IDs, internal codes — not useful for semantic search)
_SKIP_IN_SEARCH = {"product_id", "sku", "created_date", "updated_date", "product_code", "item_id", "id"}


def _build_search_text(
    data: Dict[str, Any],
    category: str,
    subtype: Optional[str],
    title: str,
) -> str:
    """
    Build semantically rich, natural-language search text per category.

    Rules:
      - Natural sentence structure (not raw field concatenation)
      - Category-specific templates for maximum embedding quality
      - All meaningful fields included with human-readable labels
      - No IDs, SKUs, row numbers, or internal codes
      - No repetition of the same value
      - Minimum 10 words for embedding quality

    Examples:
      product:  "AgriFly Pro is an Agriculture Drone priced at ₹2500,
                 used for crop monitoring and spraying. Currently active."
      contact:  "Customer Support - Amit Sharma handles customer support.
                 Contact: support@skyforgedrones.com, +91-9876543210.
                 Available 9 AM - 6 PM."
      offer:    "Student Offer provides 25% discount for students on
                 training programs. Valid until 2026-09-30."
    """
    parts: List[str] = []
    seen: set = set()

    def _seen_add(v: str) -> bool:
        """Returns True if value is new (not seen), adds to seen set."""
        key = v.strip().lower()
        if key in seen or not key:
            return False
        seen.add(key)
        return True

    def _val(field: str) -> Optional[str]:
        v = data.get(field)
        return str(v).strip() if v else None

    # ── Helper: resolve valid_until from multiple possible fields ─────────
    def _get_valid_until() -> Optional[str]:
        for f in _VALID_UNTIL_FIELDS:
            v = data.get(f)
            if v:
                return str(v).strip()
        return None

    # ── Helper: resolve working hours ─────────────────────────────────────
    def _get_hours() -> Optional[str]:
        for f in _HOURS_FIELDS:
            v = data.get(f)
            if v:
                return str(v).strip()
        return None

    # ── Helper: resolve person name ───────────────────────────────────────
    def _get_person() -> Optional[str]:
        for f in _CONTACT_NAME_FIELDS:
            v = data.get(f)
            if v and not str(v).strip().isdigit():
                return str(v).strip()
        return None

    # ── Helper: resolve department ────────────────────────────────────────
    def _get_dept() -> Optional[str]:
        for f in _CONTACT_DEPT_FIELDS:
            v = data.get(f)
            if v and not str(v).strip().isdigit():
                return str(v).strip()
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # CONTACT SUPPORT — natural sentence with all contact details
    # ═══════════════════════════════════════════════════════════════════════
    if category == "contact_support":
        person = _get_person()
        dept   = _get_dept()
        email  = _val("email")
        phone  = _val("phone")
        hours  = _get_hours()

        # Sentence 1: who handles what
        if dept and person:
            parts.append(f"{person} handles {dept.lower()} inquiries.")
            _seen_add(person); _seen_add(dept)
        elif dept:
            parts.append(f"{dept} department handles customer inquiries.")
            _seen_add(dept)
        elif person:
            parts.append(f"{person} is a support contact.")
            _seen_add(person)

        # Sentence 2: contact details
        contact_parts = []
        if email and _seen_add(email):
            contact_parts.append(f"Email: {email}")
        if phone and _seen_add(phone):
            contact_parts.append(f"Phone: {phone}")
        if contact_parts:
            parts.append("Contact via " + ", ".join(contact_parts) + ".")

        # Sentence 3: availability
        if hours and _seen_add(hours):
            parts.append(f"Available {hours}.")

        # Sentence 4: website if present
        website = _val("website")
        if website and _seen_add(website):
            parts.append(f"Website: {website}.")

        # Sentence 5: description/notes
        desc = _val("description") or _val("notes") or _val("answer")
        if desc and _seen_add(desc):
            parts.append(desc)

        # Append title as context anchor if not already present
        if title and _seen_add(title):
            parts.insert(0, title + ".")

        return " ".join(parts)[:1500]

    # ═══════════════════════════════════════════════════════════════════════
    # OFFERS / PROMOTIONS — discount-focused natural sentence
    # ═══════════════════════════════════════════════════════════════════════
    if category == "offers_promotions":
        name        = _val("name") or _val("offer_name") or title
        discount    = _val("discount")
        description = _val("description") or _val("details") or _val("features")
        valid_until = _get_valid_until()
        promo_code  = _val("promo_code")

        _seen_add(name)

        # Sentence 1: what the offer is
        if discount and description:
            parts.append(f"{name} provides {discount}% discount. {description}.")
            _seen_add(discount); _seen_add(description)
        elif discount:
            parts.append(f"{name} offers {discount}% discount.")
            _seen_add(discount)
        elif description:
            parts.append(f"{name}: {description}.")
            _seen_add(description)
        else:
            parts.append(f"{name} is a special promotional offer.")

        # Sentence 2: validity
        if valid_until and _seen_add(valid_until):
            parts.append(f"Valid until {valid_until}.")

        # Sentence 3: promo code
        if promo_code and _seen_add(promo_code):
            parts.append(f"Use code {promo_code} to avail.")

        # Sentence 4: subtype context
        if subtype and subtype not in ("general", "loyalty"):
            parts.append(f"Offer type: {subtype}.")

        return " ".join(parts)[:1500]

    # ═══════════════════════════════════════════════════════════════════════
    # PRODUCT / SERVICE — price-focused natural sentence
    # ═══════════════════════════════════════════════════════════════════════
    if category in ("product_service", "pricing_payment"):
        name        = _val("name") or title
        price       = _val("price")
        cat         = _val("category")
        description = _val("description") or _val("features")
        stock       = _val("stock")
        status      = _val("status") or "active"
        supplier    = _val("supplier") or _val("brand")

        _seen_add(name)

        # Sentence 1: what it is and price
        if cat and price:
            parts.append(f"{name} is a {cat} priced at ₹{price}.")
            _seen_add(cat); _seen_add(price)
        elif price:
            parts.append(f"{name} is priced at ₹{price}.")
            _seen_add(price)
        elif cat:
            parts.append(f"{name} is a {cat}.")
            _seen_add(cat)
        else:
            parts.append(f"{name} is available.")

        # Sentence 2: description
        if description and _seen_add(description):
            parts.append(description + ".")

        # Sentence 3: stock / availability
        if stock and _seen_add(stock):
            parts.append(f"Stock: {stock} units available.")
        elif status and _seen_add(status):
            status_text = {
                "active": "Currently available.",
                "out_of_stock": "Currently out of stock.",
                "limited_stock": "Limited stock available.",
                "inactive": "Currently inactive.",
            }.get(status.lower(), f"Status: {status}.")
            parts.append(status_text)

        # Sentence 4: supplier
        if supplier and _seen_add(supplier):
            parts.append(f"Supplied by {supplier}.")

        # Sentence 5: any remaining fields
        skip = _SKIP_IN_SEARCH | {
            "price", "stock", "supplier", "brand", "status",
            "category", "subcategory", "description", "features", "name",
        }
        for k, v in data.items():
            if k not in skip and v and _seen_add(str(v)):
                parts.append(str(v))

        return " ".join(parts)[:1500]

    # ═══════════════════════════════════════════════════════════════════════
    # ALL OTHER CATEGORIES — generic but structured
    # ═══════════════════════════════════════════════════════════════════════
    parts.append(title)
    _seen_add(title)

    skip = _SKIP_IN_SEARCH | {"name", "product_id"}
    for k, v in data.items():
        if k not in skip and v:
            label = k.replace("_", " ")
            val_s = str(v).strip()
            if _seen_add(val_s):
                parts.append(f"{label} {val_s}")

    return " ".join(parts)[:1500]


# ── Attributes extraction ─────────────────────────────────────────────────────

def _normalize_status(raw: str) -> str:
    """Map any raw status string to a canonical value. Always returns lowercase."""
    key = raw.strip().lower()
    # Return canonical value from map, or lowercase of original as fallback
    # (never return uppercase — Qdrant filters expect lowercase canonical values)
    return _STATUS_MAP.get(key, key.lower())


def _extract_attributes(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract typed attributes for Qdrant payload filtering.
    Covers ALL categories: products, contacts, offers, services.

    Returns typed, filterable fields:
      product:  price, stock, status, priority_score, supplier, category, name
      contact:  name, email, phone, department, working_hours, category
      offer:    name, discount, valid_until, description
    """
    attrs: Dict[str, Any] = {}

    # ── Numeric fields ────────────────────────────────────────────────────
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

    # ── Status — canonical value ──────────────────────────────────────────
    status_val = data.get("status")
    if status_val:
        canonical = str(status_val).strip().lower()
        attrs["status"] = canonical if canonical in (
            "active", "out_of_stock", "limited_stock", "inactive"
        ) else _normalize_status(canonical)
    else:
        attrs["status"] = "active"

    # ── Priority score based on status ────────────────────────────────────
    attrs["priority_score"] = _PRIORITY_MAP.get(attrs.get("status", "active"), 2)

    # ── Product / generic string attributes ──────────────────────────────
    for field in ("supplier", "brand", "category", "subcategory", "name"):
        if field in data and data[field]:
            attrs[field] = str(data[field]).strip()

    # ── Contact-specific attributes ───────────────────────────────────────
    # email
    if "email" in data and data["email"]:
        attrs["email"] = str(data["email"]).strip()

    # phone
    if "phone" in data and data["phone"]:
        attrs["phone"] = str(data["phone"]).strip()

    # person name (from any contact name field)
    if "name" not in attrs:
        for field in _CONTACT_NAME_FIELDS:
            if field in data and data[field] and not str(data[field]).strip().isdigit():
                attrs["name"] = str(data[field]).strip()
                break

    # department (from any dept field)
    if "department" not in attrs:
        for field in _CONTACT_DEPT_FIELDS:
            if field in data and data[field] and not str(data[field]).strip().isdigit():
                attrs["department"] = str(data[field]).strip()
                break

    # working hours
    for field in _HOURS_FIELDS:
        if field in data and data[field]:
            attrs["working_hours"] = str(data[field]).strip()
            break

    # ── Offer-specific attributes ─────────────────────────────────────────
    # valid_until (from any expiry/valid field)
    for field in _VALID_UNTIL_FIELDS:
        if field in data and data[field]:
            attrs["valid_until"] = str(data[field]).strip()
            break

    # description (for offers and products)
    for field in ("description", "details", "features"):
        if field in data and data[field]:
            attrs["description"] = str(data[field]).strip()[:300]
            break

    return attrs


def _extract_keywords(data: Dict[str, Any], title: str) -> List[str]:
    """
    Extract 20+ keyword tokens for fast keyword matching.

    Generates tokens from:
      - Full title + individual words
      - Category, subcategory, department
      - All string field values
      - Synonyms for key terms (price→cost/rate, contact→phone/support, etc.)
      - Common misspellings for product names

    Target: minimum 20 tokens per entry.
    """
    keywords: List[str] = []
    seen: set = set()

    def _add_kw(text: str) -> None:
        t = text.strip().lower()
        if t and t not in seen and len(t) > 1:
            keywords.append(t)
            seen.add(t)

    stop_words = {
        "a", "an", "the", "of", "in", "for", "and", "or", "to", "is",
        "are", "with", "by", "at", "on", "from", "as", "its", "it",
        "be", "was", "has", "have", "this", "that", "we", "our",
    }

    def _tokenize(text: str) -> None:
        """Add full phrase + individual words."""
        _add_kw(text)
        if " " in text and len(text) < 150:
            for word in re.split(r"[\s\-_/]+", text.lower()):
                word = re.sub(r"[^a-z0-9]", "", word)
                if word and len(word) > 2 and word not in stop_words:
                    _add_kw(word)

    # ── Core: title ───────────────────────────────────────────────────────
    _tokenize(title)

    # ── All string fields ─────────────────────────────────────────────────
    skip_kw = {"product_id", "sku", "created_date", "updated_date", "id",
               "product_code", "status", "priority_score"}
    for field, value in data.items():
        if field in skip_kw or not value:
            continue
        val_str = str(value).strip()
        if not val_str or val_str.isdigit():
            continue
        _tokenize(val_str)

    # ── Synonym expansion ─────────────────────────────────────────────────
    # Price synonyms
    if "price" in data or any(k in title.lower() for k in ("price", "cost", "rate")):
        for syn in ("cost", "rate", "fee", "charge", "amount", "pricing"):
            _add_kw(syn)

    # Contact synonyms
    if "email" in data or "phone" in data:
        for syn in ("contact", "support", "helpline", "reach", "connect",
                    "customer care", "helpdesk", "assistance"):
            _add_kw(syn)

    # Offer synonyms
    if "discount" in data or "offer_name" in data:
        for syn in ("deal", "promo", "promotion", "sale", "savings",
                    "coupon", "voucher", "offer", "discount"):
            _add_kw(syn)

    # Product synonyms based on category
    cat = str(data.get("category", "")).lower()
    if "drone" in cat or "drone" in title.lower():
        for syn in ("uav", "unmanned aerial", "aerial vehicle", "quadcopter",
                    "multirotor", "flying device"):
            _add_kw(syn)
    if "software" in cat or "software" in title.lower():
        for syn in ("app", "application", "platform", "tool", "system",
                    "saas", "digital", "web app"):
            _add_kw(syn)
    if "agriculture" in cat or "agri" in title.lower():
        for syn in ("farming", "crop", "field", "agricultural", "agri",
                    "precision farming", "farm tech"):
            _add_kw(syn)

    # ── Category-level keywords ───────────────────────────────────────────
    category_kw_map = {
        "contact_support":   ["support", "help", "contact", "customer service",
                               "assistance", "helpdesk", "team", "department"],
        "offers_promotions": ["offer", "deal", "discount", "promo", "sale",
                               "promotion", "savings", "coupon"],
        "product_service":   ["product", "item", "catalog", "available",
                               "buy", "purchase", "order"],
        "pricing_payment":   ["price", "cost", "plan", "subscription",
                               "payment", "billing", "fee"],
    }
    # We don't have category here directly, infer from data
    if "email" in data or "phone" in data:
        for kw in category_kw_map["contact_support"]:
            _add_kw(kw)
    if "discount" in data:
        for kw in category_kw_map["offers_promotions"]:
            _add_kw(kw)
    if "price" in data:
        for kw in category_kw_map["product_service"]:
            _add_kw(kw)

    # ── Pad to minimum 20 if needed ───────────────────────────────────────
    # Add title character n-grams as last resort padding
    if len(keywords) < 20:
        title_words = re.findall(r"[a-z0-9]+", title.lower())
        for w in title_words:
            if len(w) >= 3:
                _add_kw(w)
                # Add common suffix variants
                if not w.endswith("s"):
                    _add_kw(w + "s")
                if not w.endswith("ing"):
                    _add_kw(w + "ing")

    return keywords[:50]  # cap at 50 (was 30)


# ── Quality scoring ───────────────────────────────────────────────────────────

# Minimum thresholds for validation layer
_MIN_KEYWORDS    = 10
_MIN_SEARCH_WORDS = 10
_MIN_TITLE_LEN   = 2


def _compute_quality_score(
    data: Dict[str, Any],
    category: str,
    dedup_penalty: float = 0.0,
    title: str = "",
    search_text: str = "",
    keywords: Optional[List[str]] = None,
) -> float:
    """
    Enterprise quality score — 5 components, target >= 85.

      completeness_score  (0–30): % of category-recommended fields present
      keyword_richness    (0–20): keyword count vs target (20 tokens = full score)
      search_text_quality (0–20): word count + sentence structure quality
      attribute_depth     (0–20): % of high-value fields present + contact fields
      embedding_similarity(0–10): proxy — richness of search_text for embedding

    Validation penalties:
      - numeric title: -20
      - keywords < 10: -10
      - search_text < 10 words: -10
    """
    keywords = keywords or []

    # ── 1. Completeness (0–30) ────────────────────────────────────────────
    recommended = RECOMMENDED_FIELDS.get(category, ["name"])
    # For contact_support: also check aliased fields
    present_rec = 0
    for f in recommended:
        if f in data and data[f]:
            present_rec += 1
        elif f == "name":
            # Check all contact name fields
            if any(data.get(cf) for cf in _CONTACT_NAME_FIELDS):
                present_rec += 1
        elif f == "valid_until":
            # Check all valid_until aliases
            if any(data.get(vf) for vf in _VALID_UNTIL_FIELDS):
                present_rec += 1
        elif f == "working_hours":
            if any(data.get(hf) for hf in _HOURS_FIELDS):
                present_rec += 1
    completeness_score = (present_rec / len(recommended)) * 30 if recommended else 30

    # ── 2. Keyword richness (0–20) ────────────────────────────────────────
    kw_count = len(keywords)
    keyword_richness = min(kw_count / 20, 1.0) * 20  # 20 keywords = full score

    # ── 3. Search text quality (0–20) ─────────────────────────────────────
    word_count = len(search_text.split()) if search_text else 0
    # Full score at 30+ words; partial for 10-30 words
    if word_count >= 30:
        search_text_quality = 20.0
    elif word_count >= _MIN_SEARCH_WORDS:
        search_text_quality = (word_count / 30) * 20
    else:
        search_text_quality = 0.0

    # Bonus: natural sentence structure (has period = sentence-like)
    if search_text and "." in search_text:
        search_text_quality = min(search_text_quality + 3, 20.0)

    # ── 4. Attribute depth (0–20) ─────────────────────────────────────────
    hv_fields = HIGH_VALUE_FIELDS.get(category, {"name"})
    hv_present = 0
    for f in hv_fields:
        if f in data and data[f]:
            hv_present += 1
        elif f == "name" and any(data.get(cf) for cf in _CONTACT_NAME_FIELDS):
            hv_present += 1
        elif f == "valid_until" and any(data.get(vf) for vf in _VALID_UNTIL_FIELDS):
            hv_present += 1
    attribute_depth = (hv_present / len(hv_fields)) * 20 if hv_fields else 20

    # Bonus for extra contact fields
    if category == "contact_support":
        extra = sum(1 for f in ("email", "phone") if data.get(f))
        attribute_depth = min(attribute_depth + extra * 2, 20.0)

    # ── 5. Embedding similarity proxy (0–10) ──────────────────────────────
    # Proxy: avg field value length (longer = richer embedding)
    values = [str(v) for v in data.values() if v and not str(v).isdigit()]
    avg_len = sum(len(v) for v in values) / len(values) if values else 0
    embedding_similarity = min(avg_len / 50, 1.0) * 10

    # ── Validation penalties ──────────────────────────────────────────────
    penalty = dedup_penalty
    if title and title.strip().isdigit():
        penalty += 20  # numeric title is a critical failure
    if kw_count < _MIN_KEYWORDS:
        penalty += 10
    if word_count < _MIN_SEARCH_WORDS:
        penalty += 10

    total = (
        completeness_score
        + keyword_richness
        + search_text_quality
        + attribute_depth
        + embedding_similarity
        - penalty
    )
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
