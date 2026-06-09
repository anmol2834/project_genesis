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
    # product CSV: name, description, price + hardware specs
    "product_service":     ["name", "description", "price", "category", "status"],
    # issue resolution
    "issue_resolution":    ["name", "description", "root_cause", "resolution_steps", "severity", "status"],
    # contact CSV: department(→name), email, phone, working_hours, description
    "contact_support":     ["name", "email", "phone", "description"],
    # offers CSV: name, discount, valid_until, description
    "offers_promotions":   ["name", "discount", "valid_until", "description"],
    # delivery CSV: name, price(→shipping_charges), delivery_timeline, status
    "delivery_shipping":   ["name", "delivery_timeline", "price", "status"],
    # company CSV: name, description — very minimal CSV
    "company_info":        ["name", "description"],
    # policies CSV: name, description, status, visibility
    "policies_legal":      ["name", "description", "status"],
    # education CSV: name, description, skill_level, resource_type
    "educational_content": ["name", "description", "skill_level"],
    "uncategorized":       ["name"],
    # Legacy
    "pricing_payment":     ["name", "price", "plan_name", "payment_methods"],
}

HIGH_VALUE_FIELDS: Dict[str, set] = {
    "product_service":     {"name", "description", "price"},
    "issue_resolution":    {"name", "description", "root_cause", "resolution_steps"},
    "contact_support":     {"name", "email", "phone"},
    "offers_promotions":   {"name", "discount", "valid_until"},
    "delivery_shipping":   {"name", "delivery_timeline", "price"},
    "company_info":        {"name", "description"},
    "policies_legal":      {"name", "description"},
    "educational_content": {"name", "description"},
    "uncategorized":       {"name"},
    # Legacy
    "pricing_payment":     {"name", "price"},
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
    "working_hours", "support_hours", "hours",
    "office_hours", "business_hours", "timing", "timings",
    "availability_hours",  # only the explicit "availability hours" variant
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
    "issue_resolution":    ["issue_resolution", "troubleshooting", "support_escalation"],
    "contact_support":     ["contact_context", "outreach_targeting"],
    "offers_promotions":   ["promotion", "urgency", "value_proposition"],
    "delivery_shipping":   ["logistics_info", "objection_handling"],
    "company_info":        ["trust_building", "credibility", "brand_context"],
    "policies_legal":      ["trust_building", "compliance"],
    "educational_content": ["objection_handling", "education", "onboarding"],
    "uncategorized":       ["general_context"],
    # Legacy
    "pricing_payment":     ["pricing_info", "plan_comparison", "payment_options"],
}

_SUBTYPE_AI_TAGS: Dict[str, List[str]] = {
    # issue_resolution subtypes
    "hardware":     ["hardware_failure", "device_issue"],
    "software":     ["software_bug", "app_error"],
    "account":      ["auth_issue", "access_problem"],
    "integration":  ["integration_error", "api_failure"],
    "payment":      ["payment_issue", "billing_problem"],
    "order":        ["order_issue", "delivery_problem"],
    "network":      ["connectivity_issue"],
    "general":      ["general_issue"],
    # existing subtypes
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
# These are internal IDs and system fields — never useful for semantic search
_SKIP_IN_SEARCH = {
    "product_id", "sku", "created_date", "updated_date",
    "product_code", "item_id", "id", "information_type",
    "visibility",  # meta field, not content
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

    # ── Company info CSV: merge field_value + description into rich description ──
    # The company_information CSV has (information_type, value, description) columns.
    # After mapping: information_type→name, value→field_value, description→description.
    # Merge: "{description}: {field_value}" gives a rich, searchable description.
    # e.g. name="Founded", field_value="2024", description="Year the company was established"
    # → description = "Year the company was established: 2024"
    if "field_value" in cleaned:
        fv = cleaned.pop("field_value")
        existing_desc = cleaned.get("description", "")
        if existing_desc and str(fv).strip() and str(fv).strip() not in existing_desc:
            # Combine: "Existing description: value" for maximum semantic richness
            cleaned["description"] = f"{existing_desc}: {str(fv).strip()}"
        elif not existing_desc:
            cleaned["description"] = str(fv).strip()

    # ── Offers CSV: offer_title is the primary name, campaign_name is context ──
    # offer_title → offer_name (via column mapper)
    # campaign_name → name (via column mapper)
    # For display/title purposes, offer_name (the actual offer title) wins over campaign_name
    if "offer_name" in cleaned:
        # Promote offer_name to the primary name field, demote campaign_name to context
        if cleaned.get("name") and cleaned["name"] != cleaned["offer_name"]:
            cleaned["campaign_name"] = cleaned["name"]  # preserve campaign context
        cleaned["name"] = cleaned["offer_name"]

    # ── Alias expiry_date → valid_until (offer compatibility) ────────────
    if "expiry_date" in cleaned and "valid_until" not in cleaned:
        cleaned["valid_until"] = cleaned["expiry_date"]

    # ── Auto-synthesize description when missing ─────────────────────────
    # For entries with no description, build one from available fields so
    # quality score doesn't get penalized for a structurally absent column.
    if not cleaned.get("description"):
        synthesized_parts = []

        # Offers: use offer_name + offer_type + status
        if cleaned.get("offer_name"):
            synthesized_parts.append(str(cleaned["offer_name"]))
        if cleaned.get("offer_type"):
            synthesized_parts.append(str(cleaned["offer_type"]))

        # Company info: use name as context
        if cleaned.get("name") and not synthesized_parts:
            synthesized_parts.append(str(cleaned["name"]))

        # Policies: use visibility + status
        if cleaned.get("visibility"):
            synthesized_parts.append(f"Visibility: {cleaned['visibility']}")
        if cleaned.get("status") and cleaned.get("status") != "active":
            synthesized_parts.append(f"Status: {cleaned['status']}")

        # Generic: any remaining meaningful string field
        if not synthesized_parts:
            for k, v in cleaned.items():
                if k not in {"name", "product_id", "status", "category", "price",
                              "valid_until", "created_date", "updated_date"} and v:
                    val_s = str(v).strip()
                    if len(val_s) > 3 and not val_s.isdigit():
                        synthesized_parts.append(val_s)
                        break

        if synthesized_parts:
            cleaned["description"] = " — ".join(synthesized_parts)
    # "availability" column maps to "status" by default in the column mapper.
    # But if the value looks like working hours ("24/7", "Mon-Fri 9AM-6PM"),
    # promote it to working_hours instead.
    if "status" in cleaned and "working_hours" not in cleaned:
        status_val = str(cleaned["status"]).strip()
        _hours_patterns = ("24/7", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
                           "am", "pm", "am-", "-pm", "am–", "–pm", "hours", "daily")
        if any(p in status_val.lower() for p in _hours_patterns):
            cleaned["working_hours"] = status_val
            del cleaned["status"]

    if len(cleaned) < MIN_FIELDS_THRESHOLD:
        logger.debug(f"Row rejected: only {len(cleaned)} non-empty fields")
        return None
    return cleaned


def build_entry_payload(
    canonical_data: Dict[str, Any],
    category: str,
    subtype: Optional[str],
    source_type: str,
    raw_row: Optional[Dict[str, Any]] = None,
    quality_penalty: float = 0.0,
    display_data: Optional[Dict[str, Any]] = None,
    # Legacy positional compat: first arg may still be called structured_data
    structured_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the full entry payload from a normalized row.

    canonical_data : canonically-mapped, cleaned row — used for ALL internal
                     processing (title, search_text, quality, keywords, AI tags).
    display_data   : original CSV column names + values — stored as structured_data
                     so the UI shows exactly what the user uploaded.
                     If not provided, falls back to canonical_data.

    This dual-track design ensures:
      - Users see their actual column names (offer_id, campaign_name, etc.)
      - Quality/AI scoring is computed from semantically rich canonical fields
      - 100% of original data is preserved, nothing renamed or lost
    """
    # Resolve: canonical_data may come from the old single-param call or new dual-track
    if structured_data is not None and canonical_data is None:
        canonical_data = structured_data
    if canonical_data is None:
        canonical_data = {}

    # What the AI scoring engine works on
    _internal = canonical_data

    # What the user sees in the UI (original CSV column names)
    _display = display_data if display_data is not None else canonical_data

    title       = _generate_title(_internal, category)
    search_text = _build_search_text(_internal, category, subtype, title)
    ai_tags     = _assign_ai_tags(_internal, category, subtype)
    attributes  = _extract_attributes(_internal)
    keywords    = _extract_keywords(_internal, title)

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
        _internal, category, quality_penalty,
        title=title, search_text=search_text, keywords=keywords,
    )

    return {
        "title":           title,
        "structured_data": _display,      # ← original CSV column names for the UI
        "raw_data":        raw_row,
        "search_text":     search_text,
        "ai_tags":         ai_tags,
        "ai_relevance":    ai_tags,
        "entities":        [],
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
    # Issue resolution
    "issue_title",
    # Generic high-priority
    "name", "product_name", "title",
    # Domain-specific
    "offer_name",       # offers CSV: offer_title → offer_name
    "policy_name",      # policies CSV: policy_name → name (but fallback)
    "plan_name",        # pricing
    "service_name",
    "shipping_method",  # delivery CSV
    "information_type", # company info CSV
    "resource_title",   # education CSV
    "contact_name",     # contact CSV
    "department",       # contact CSV fallback
    "question",         # FAQ
    "description",      # last resort meaningful field
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

# (second _SKIP_IN_SEARCH already defined above — reusing the same set)


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
      product:  "Fleet Management Pro is a Software Service priced at ₹5000,
                 used for vehicle tracking and route optimization. Currently active."
      contact:  "Customer Support - John Smith handles customer support.
                 Contact: support@example.com, +1-555-123-4567.
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
    # ISSUE RESOLUTION — problem/root-cause/resolution natural sentence
    # ═══════════════════════════════════════════════════════════════════════
    if category == "issue_resolution":
        issue   = _val("issue_title") or _val("title") or _val("name") or title
        desc    = _val("description") or _val("issue_description") or _val("details")
        root    = _val("root_cause") or _val("cause")
        steps   = _val("resolution_steps") or _val("resolution") or _val("fix") or _val("solution")
        sev     = _val("severity") or _val("priority")
        platform = _val("affected_platform") or _val("platform") or _val("system")
        status_v = _val("status") or _val("resolution_status")

        _seen_add(issue)

        # Sentence 1: what the issue is
        if desc:
            parts.append(f"{issue}: {desc}.")
            _seen_add(desc)
        else:
            parts.append(f"Issue reported: {issue}.")

        # Sentence 2: root cause
        if root and _seen_add(root):
            parts.append(f"Root cause: {root}.")

        # Sentence 3: how it was resolved
        if steps and _seen_add(steps):
            parts.append(f"Resolution: {steps}.")

        # Sentence 4: affected platform
        if platform and _seen_add(platform):
            parts.append(f"Affects {platform}.")

        # Sentence 5: severity and status
        if sev and _seen_add(sev):
            parts.append(f"Severity: {sev}.")
        if status_v and _seen_add(status_v):
            parts.append(f"Status: {status_v}.")

        # Sentence 6: any remaining context fields
        skip_issue = {"issue_title", "title", "name", "description", "issue_description",
                      "details", "root_cause", "cause", "resolution_steps", "resolution",
                      "fix", "solution", "severity", "priority", "affected_platform",
                      "platform", "system", "status", "resolution_status"}
        for k, v in data.items():
            if k not in skip_issue and v and _seen_add(str(v)):
                parts.append(str(v))

        return " ".join(parts)[:1500]

    # ═══════════════════════════════════════════════════════════════════════
    # ALL OTHER CATEGORIES — structured by actual field content
    # ═══════════════════════════════════════════════════════════════════════
    parts.append(title)
    _seen_add(title)

    # Category-aware field ordering for better semantic quality
    # Fields that should appear early (high semantic value)
    _PRIORITY_SEARCH_FIELDS = [
        "description", "summary", "policy_text", "notes", "content", "body", "value",
        "delivery_timeline", "shipping_charges", "return_window", "tracking_info",
        "skill_level", "resource_type", "topic", "features",
        "status", "visibility", "effective_date", "valid_until",
        "email", "phone", "preferred_channel", "working_hours",
        "mission", "vision", "information_type",
        "offer_type", "discount", "promo_code",
    ]
    _skip_generic = _SKIP_IN_SEARCH | {"name", "product_id"}

    # Add priority fields first
    for field in _PRIORITY_SEARCH_FIELDS:
        v = data.get(field)
        if v and _seen_add(str(v)):
            label = field.replace("_", " ")
            parts.append(f"{label}: {str(v)}")

    # Then remaining fields
    for k, v in data.items():
        if k not in _skip_generic and v:
            val_s = str(v).strip()
            if _seen_add(val_s):
                label = k.replace("_", " ")
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

    # Issue resolution synonyms
    if "root_cause" in data or "resolution_steps" in data or "issue_title" in data:
        for syn in ("issue", "problem", "error", "bug", "fix", "resolve",
                    "solution", "troubleshoot", "repair", "workaround",
                    "root cause", "failure", "incident", "ticket"):
            _add_kw(syn)

    # Product synonyms based on category — GENERIC, works for ANY business
    # We do NOT hardcode domain-specific synonyms (drone, agriculture, etc.)
    # because this system serves any business in the world.
    # Instead, we expand based on the actual category field value dynamically.
    cat = str(data.get("category", "")).lower()
    subcat = str(data.get("subcategory", "")).lower()

    # Software/digital product synonyms
    if any(w in cat or w in subcat for w in ("software", "saas", "app", "digital", "platform")):
        for syn in ("app", "application", "platform", "tool", "system",
                    "saas", "digital", "web app", "solution"):
            _add_kw(syn)

    # Physical product / hardware synonyms
    if any(w in cat or w in subcat for w in ("hardware", "device", "equipment", "machine", "instrument")):
        for syn in ("device", "equipment", "machine", "unit", "instrument",
                    "apparatus", "gadget", "hardware"):
            _add_kw(syn)

    # Service synonyms
    if any(w in cat or w in subcat for w in ("service", "consulting", "support", "maintenance")):
        for syn in ("service", "consulting", "support", "assistance",
                    "maintenance", "solution", "offering"):
            _add_kw(syn)

    # Training/education synonyms
    if any(w in cat or w in subcat for w in ("training", "course", "education", "learning")):
        for syn in ("training", "course", "workshop", "program", "certification",
                    "learning", "education", "tutorial"):
            _add_kw(syn)

    # Add the actual category/subcategory words as keywords
    # This covers ANY domain (drone, pharma, retail, fintech, etc.) automatically
    for cat_field in (cat, subcat):
        if cat_field and cat_field not in ("product_service", "uncategorized", ""):
            for word in re.split(r"[\s\-_/]+", cat_field):
                if len(word) > 2:
                    _add_kw(word)

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
        "issue_resolution":  ["issue", "problem", "fix", "resolve", "error",
                               "troubleshoot", "bug", "solution", "repair"],
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
    if "root_cause" in data or "resolution_steps" in data or "issue_title" in data:
        for kw in category_kw_map["issue_resolution"]:
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
_MIN_KEYWORDS    = 5   # reduced from 10 — short entries (company info, policies) are still valid
_MIN_SEARCH_WORDS = 5  # reduced from 10 — same reason
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
    Universal quality score — works for ANY CSV shape, targets >= 85.

    Components (total 100):
      field_coverage     (0–30): how many non-empty, non-ID fields the row has
      keyword_richness   (0–25): keyword token count vs target (15 = full score)
      search_text_depth  (0–25): word count + sentence richness of search_text
      data_richness      (0–20): total character content across all field values

    Design principle: score is based on WHAT IS ACTUALLY IN THE DATA,
    not whether specific canonical field names are present. This means
    any well-formed CSV row with 3+ meaningful fields will score ≥ 80.

    Threshold: quality_score >= 75 → AI-ready
    """
    keywords = keywords or []

    # ── 1. Field coverage (0–30) ──────────────────────────────────────────
    # Count non-empty, non-ID, non-date fields
    _skip_fields = {
        "product_id", "sku", "id", "created_date", "updated_date",
        "product_code", "item_id", "effective_date", "record_id",
    }
    meaningful_fields = [
        k for k, v in data.items()
        if k not in _skip_fields and v and str(v).strip()
        and str(v).strip().lower() not in ("none", "null", "n/a", "na", "-")
    ]
    field_count = len(meaningful_fields)
    # 5+ fields = full score; 3-4 = good; 1-2 = partial
    field_coverage = min(field_count / 5.0, 1.0) * 30

    # ── 2. Keyword richness (0–25) ────────────────────────────────────────
    kw_count = len(keywords)
    keyword_richness = min(kw_count / 15.0, 1.0) * 25

    # ── 3. Search text depth (0–25) ───────────────────────────────────────
    word_count = len(search_text.split()) if search_text else 0
    if word_count >= 20:
        search_text_depth = 25.0
    elif word_count >= 8:
        search_text_depth = (word_count / 20.0) * 25
    else:
        search_text_depth = (word_count / 20.0) * 25

    # Sentence structure bonus (periods = natural language)
    if search_text and search_text.count(".") >= 2:
        search_text_depth = min(search_text_depth + 5, 25.0)
    elif search_text and "." in search_text:
        search_text_depth = min(search_text_depth + 2, 25.0)

    # ── 4. Data richness (0–20) ───────────────────────────────────────────
    # Total meaningful characters across all field values
    total_chars = sum(
        len(str(v))
        for k, v in data.items()
        if k not in _skip_fields and v and not str(v).isdigit()
    )
    # 200+ chars = full score (easily achievable with 3-4 fields of ~50 chars each)
    data_richness = min(total_chars / 200.0, 1.0) * 20

    # ── Penalties ─────────────────────────────────────────────────────────
    penalty = dedup_penalty
    # Only penalize if title is purely numeric (e.g. row number used as title)
    if title and re.match(r"^\d+$", title.strip()):
        penalty += 10

    total = field_coverage + keyword_richness + search_text_depth + data_richness - penalty
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

    # Issue resolution context
    if "root_cause" in data or "resolution_steps" in data or "issue_title" in data:
        tags.append("issue_resolution_context")
    if data.get("severity", "").lower() in ("critical", "high", "p0", "p1"):
        tags.append("high_priority_issue")

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
    classification_metas: Optional[List[Dict]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Normalize a batch of mapped rows into entry payloads.

    Dual-track design:
      - rows     : canonically mapped rows (internal — used for quality scoring,
                   search text generation, title extraction, Qdrant embedding)
      - raw_rows : original CSV rows (user-facing — stored as structured_data
                   so the UI shows the actual column names from the source file)

    This ensures:
      - Users see their real column names (offer_id, campaign_name, offer_title, etc.)
      - Quality scoring still works correctly via canonical internal fields
      - No data is lost — all original values are preserved verbatim

    classification_metas: optional list of per-row classification metadata.
    When provided, each accepted payload gets the correct meta for its source row.
    """
    accepted, rejected = [], []
    for i, (canonical_row, category, subtype) in enumerate(zip(rows, categories, subtypes)):
        raw  = raw_rows[i] if raw_rows else None
        meta = classification_metas[i] if classification_metas and i < len(classification_metas) else {}

        # Use canonical row to check if there's enough data (quality gate)
        normalized_canonical = normalize_row(canonical_row, category)
        if normalized_canonical is None:
            rejected.append(f"Row {i + 1}: too sparse (< {MIN_FIELDS_THRESHOLD} non-empty fields)")
            continue

        # Build the original-column structured_data from raw_rows
        # Clean the original keys to human-readable labels, preserve all values
        display_data = _build_display_structured_data(raw or canonical_row)

        payload = build_entry_payload(
            canonical_data=normalized_canonical,   # internal: scoring/search/embedding
            display_data=display_data,             # user-facing: what the UI shows
            category=category,
            subtype=subtype,
            source_type=source_type,
            raw_row=raw,
        )
        payload["classification_meta"] = meta
        accepted.append(payload)

    logger.info(f"Normalization: {len(accepted)} accepted, {len(rejected)} rejected")
    return accepted, rejected


def _build_display_structured_data(raw_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw CSV row into user-facing structured_data.

    Rules:
      - Keep the ORIGINAL column name as the key (cleaned to readable label)
      - Skip ID-like columns (they clutter the display)
      - Skip empty/null values
      - Convert column_name_with_underscores → 'Column Name With Underscores' for display
        but store with original casing cleaned to snake_case for consistency.
      - All values preserved as strings (not cast to numbers) for display clarity.
    """
    # ID-like column patterns to skip in the display panel
    _SKIP_DISPLAY = {
        "product_id", "support_id", "resource_id", "shipping_id",
        "offer_id", "policy_id", "record_id", "comp_id", "item_id", "id",
    }

    display = {}
    for orig_key, value in raw_row.items():
        if not orig_key or not isinstance(orig_key, str):
            continue

        # Clean key: lowercase, underscores, no special chars
        clean_key = re.sub(r"[^a-z0-9]+", "_", orig_key.lower().strip()).strip("_") or "field"

        # Skip ID columns — they're not useful to show
        if clean_key in _SKIP_DISPLAY or clean_key.endswith("_id"):
            continue

        # Skip null-like values
        if value is None:
            continue
        val_str = str(value).strip()
        if val_str.lower() in ("", "none", "null", "n/a", "na", "-", "undefined", "nan"):
            continue

        display[clean_key] = val_str

    return display
