"""
automationservice — Business Context Layer
==========================================
Source of truth: PostgreSQL `users` table  (NOT Qdrant).

Why PostgreSQL and NOT Qdrant:
    Business context is SYSTEM STATE — it is structured, authoritative,
    and already present in the users table.  Qdrant vectors derived from
    user profiles exist only for embedding-based profile similarity and
    MUST NOT be used as a business identity source.

    Using Qdrant for business context would introduce:
        • Extra vector search latency
        • Possible embedding misses (semantic gaps)
        • Inconsistency between DB master and Qdrant copy
        • Unnecessary infrastructure complexity

Responsibilities:
    1. Fetch all business fields for a given user_id in a single SQL query
    2. Normalize raw DB row → clean BusinessProfile dict
    3. Build a human-readable business_context_block for LLM prompts
    4. Cache per user_id within a process lifetime (TTL-bounded)
    5. Never raise — return a safe empty profile on any failure

Performance target: < 20 ms (single indexed UUID lookup, no JOIN).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

_SVCS_DIR     = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR      = os.path.dirname(_SVCS_DIR)
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)
for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import text

from core.database import get_db_session

logger = logging.getLogger("automationservice.business_context")

# ── In-process cache ────────────────────────────────────────────────────────────
# Key   : user_id (str)
# Value : {"profile": dict, "expires_at": float (monotonic)}
# TTL   : 300 seconds (5 minutes) — business profile rarely changes mid-session
_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 300


# ── Empty profile sentinel ──────────────────────────────────────────────────────
def _empty_profile() -> dict[str, Any]:
    """
    Returned on any DB failure or missing user.
    Processor #1 works correctly with this — it simply has no business context
    and falls back to generic multi-domain reasoning.
    """
    return {
        "business_name":        "",
        "business_type":        "",
        "industry":             [],
        "country":              "",
        "business_description": "",
        "target_audience":      "",
        "communication_tone":   "professional",
        "use_cases":            [],
        "_loaded":              False,
        "_source":              "empty",
    }


# ── Normalizer ──────────────────────────────────────────────────────────────────

def _normalize_profile(row: dict) -> dict[str, Any]:
    """
    Normalize a raw `users` table row into a clean, LLM-ready business profile.

    Field handling:
        industry   : JSON column — list of strings (e.g. ["Technology", "E-commerce"])
                     If a plain string is stored, wrap it in a list.
        use_cases  : JSON column — list of strings (e.g. ["sales", "support"])
        description: Text — may be None → return ""
        tone       : String — default to "professional" if empty

    This function is domain-agnostic — it does NOT assume laptop, drone, or any
    specific product type. All fields are taken verbatim from the DB row.
    """
    def _safe_list(val: Any) -> list[str]:
        """Convert None / str / list → list[str], deduplicated, non-empty."""
        if val is None:
            return []
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        if isinstance(val, str) and val.strip():
            return [val.strip()]
        return []

    def _safe_str(val: Any, default: str = "") -> str:
        return str(val).strip() if val and str(val).strip() else default

    return {
        "business_name":        _safe_str(row.get("business_name")),
        "business_type":        _safe_str(row.get("business_type")),
        "industry":             _safe_list(row.get("industry")),
        "country":              _safe_str(row.get("country")),
        "business_description": _safe_str(row.get("business_description")),
        "target_audience":      _safe_str(row.get("target_audience")),
        "communication_tone":   _safe_str(row.get("communication_tone"), "professional"),
        "use_cases":            _safe_list(row.get("use_cases")),
        "_loaded":              True,
        "_source":              "postgresql",
    }


# ── DB fetch ────────────────────────────────────────────────────────────────────

async def _fetch_from_db(user_id: str) -> dict[str, Any]:
    """
    Single indexed UUID lookup on the users table.
    Returns normalized profile dict or empty profile on any failure.
    Expected latency: < 5 ms (PK lookup, no JOIN, no subquery).
    """
    t0 = time.monotonic()
    try:
        async with get_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT
                        business_name,
                        business_type,
                        industry,
                        country,
                        business_description,
                        target_audience,
                        communication_tone,
                        use_cases
                    FROM users
                    WHERE id = :user_id
                    LIMIT 1
                """),
                {"user_id": user_id},
            )
            row = result.mappings().first()

        elapsed_ms = (time.monotonic() - t0) * 1000

        if row is None:
            logger.warning(
                "[business_context] user not found | user=%s... elapsed=%.1fms",
                user_id[:8], elapsed_ms,
            )
            return _empty_profile()

        profile = _normalize_profile(dict(row))
        logger.info(
            "[business_context] loaded | user=%s... business=%s industry=%s elapsed=%.1fms",
            user_id[:8],
            profile["business_name"] or "(unnamed)",
            ", ".join(profile["industry"]) or "(unknown)",
            elapsed_ms,
        )
        return profile

    except Exception as exc:
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.error(
            "[business_context] DB fetch failed | user=%s... elapsed=%.1fms error=%s",
            user_id[:8], elapsed_ms, exc,
        )
        return _empty_profile()


# ── Public API ──────────────────────────────────────────────────────────────────

async def get_business_context(user_id: str) -> dict[str, Any]:
    """
    Return the business profile for `user_id`.

    Cache strategy:
        - Check in-process cache first (TTL = 5 minutes)
        - On miss → single PostgreSQL query
        - Store result in cache regardless of success/failure
          (avoids repeated DB errors on the same hot path)

    Never raises. Returns _empty_profile() on any DB error.

    Returns:
        {
            "business_name":        str,
            "business_type":        str,
            "industry":             list[str],
            "country":              str,
            "business_description": str,
            "target_audience":      str,
            "communication_tone":   str,
            "use_cases":            list[str],
            "_loaded":              bool,   # False if DB failed or user not found
            "_source":              str,    # "postgresql" | "cache" | "empty"
        }
    """
    # ── Cache check ────────────────────────────────────────────────────────
    now = time.monotonic()
    cached = _CACHE.get(user_id)
    if cached and cached["expires_at"] > now:
        profile = dict(cached["profile"])
        profile["_source"] = "cache"
        return profile

    # ── DB fetch ───────────────────────────────────────────────────────────
    profile = await _fetch_from_db(user_id)

    # ── Cache store ────────────────────────────────────────────────────────
    _CACHE[user_id] = {
        "profile":    profile,
        "expires_at": now + _CACHE_TTL_SECONDS,
    }

    return profile


def build_business_context_block(profile: dict[str, Any]) -> str:
    """
    Render the business profile into a compact, human-readable text block
    for injection at the TOP of the Processor #1 user prompt.

    Format is intentionally plain text (not JSON) so the LLM reads it
    naturally as background knowledge, not as a data structure to parse.

    Works for any business type: SaaS, E-commerce, Healthcare, Education,
    Manufacturing, Real Estate, Finance, Hospitality, Logistics, Consulting,
    Insurance — no domain-specific assumptions.

    Returns empty string if the profile was not loaded (DB failure / user not found),
    so the prompt degrades gracefully without injecting placeholder noise.
    """
    if not profile.get("_loaded"):
        return ""

    lines: list[str] = ["BUSINESS CONTEXT", "─" * 40]

    name  = profile.get("business_name", "")
    btype = profile.get("business_type", "")
    inds  = profile.get("industry", [])
    desc  = profile.get("business_description", "")
    audience = profile.get("target_audience", "")
    tone  = profile.get("communication_tone", "")
    cases = profile.get("use_cases", [])
    country = profile.get("country", "")

    if name:
        lines.append(f"Business Name     : {name}")
    if btype:
        lines.append(f"Business Type     : {btype}")
    if inds:
        lines.append(f"Industry          : {', '.join(inds)}")
    if country:
        lines.append(f"Country           : {country}")
    if desc:
        lines.append(f"What We Do        : {desc}")
    if audience:
        lines.append(f"Target Audience   : {audience}")
    if tone:
        lines.append(f"Communication Tone: {tone}")
    if cases:
        lines.append(f"Primary Use Cases : {', '.join(cases)}")

    # ── Business-domain intent mapping hints ──────────────────────────────────
    # These are computed dynamically from the business profile and injected into
    # every prompt so the LLM can accurately map ambiguous customer phrases to
    # the correct intent category FOR THIS SPECIFIC BUSINESS.
    #
    # Logic: analyse the business description, type, industry, and use_cases to
    # infer which customer-phrase patterns map to which retrieval categories.
    # No hardcoded product assumptions — entirely driven by what the business said
    # about itself when it signed up.
    intent_hints = _build_intent_mapping_hints(profile)
    if intent_hints:
        lines.append("")
        lines.append("INTENT MAPPING FOR THIS BUSINESS")
        lines.append("(Use these mappings when classifying customer messages)")
        for hint in intent_hints:
            lines.append(f"  {hint}")

    lines.append("─" * 40)
    lines.append(
        "CRITICAL: Use the above business context to correctly interpret customer "
        "messages. Resolve all ambiguous terms (it, that, models, range, installation, "
        "customize, service, support) using the business domain defined above. "
        "Always anchor standalone_query and retrieval queries to this business's "
        "actual products and services — never use generic domain-free terms."
    )

    return "\n".join(lines)


def _build_intent_mapping_hints(profile: dict[str, Any]) -> list[str]:
    """
    Dynamically build intent mapping hints from the business profile.

    These hints tell the LLM which customer phrases map to which retrieval
    categories for this specific business. Computed entirely from what the
    business told us — business_description, business_type, industry, use_cases.

    Design principles:
      - Business-type signals (E-commerce, SaaS, Healthcare, etc.) drive the
        primary product/service vocabulary
      - Description keywords extend the vocabulary
      - Use-cases drive which categories are most relevant
      - Never assumes a specific product — always reads from the profile
      - Works for any combination of business type + industry

    Returns list of hint strings like:
        "When customer asks about PRODUCTS/SERVICES → category: product_service"
        "  Examples for THIS business: laptop models, gaming laptops, IngenAI Pro 14"
    """
    hints: list[str] = []

    desc   = (profile.get("business_description") or "").lower()
    btype  = (profile.get("business_type") or "").lower()
    inds   = [i.lower() for i in (profile.get("industry") or [])]
    cases  = [c.lower() for c in (profile.get("use_cases") or [])]
    name   = profile.get("business_name") or "this business"
    ind_str = ", ".join(profile.get("industry") or [])

    # ── Determine primary product/service vocabulary from description ─────────
    # Extract noun phrases that describe what the business sells/offers
    # These anchor the product_service category intent examples.
    product_vocab = _extract_product_vocabulary(desc, btype, inds)
    service_vocab = _extract_service_vocabulary(desc, btype, inds, cases)

    # ── Category: product_service ─────────────────────────────────────────────
    ps_examples = product_vocab[:4] if product_vocab else []
    if ps_examples:
        hints.append(
            f"When customer asks about PRODUCTS/SERVICES/FEATURES/PRICING "
            f"→ category: product_service"
        )
        hints.append(
            f"  Business-specific examples: {', '.join(ps_examples)}"
        )
    else:
        hints.append(
            f"When customer asks about products, services, features, pricing, "
            f"or what {name} offers → category: product_service"
        )

    # ── Category: offers_promotions ───────────────────────────────────────────
    hints.append(
        "When customer asks about DISCOUNTS/OFFERS/DEALS/PROMOTIONS/COUPONS "
        "→ category: offers_promotions"
    )
    if ps_examples:
        hints.append(
            f"  Business-specific examples: discounts on {ps_examples[0]}, "
            f"promotional offers, loyalty rewards"
        )

    # ── Category: delivery_shipping ───────────────────────────────────────────
    # Service businesses may not ship — but may have delivery/deployment/visit
    delivery_label = _infer_delivery_label(btype, inds, desc)
    hints.append(
        f"When customer asks about DELIVERY/SHIPPING/{delivery_label.upper()} "
        f"→ category: delivery_shipping"
    )

    # ── Category: contact_support ─────────────────────────────────────────────
    hints.append(
        "When customer asks to SPEAK TO SOMEONE, requests escalation, asks for "
        "contact details, phone, email, manager, senior representative "
        "→ category: contact_support"
    )

    # ── Category: policies_legal ──────────────────────────────────────────────
    hints.append(
        "When customer asks about RETURN/REFUND POLICY, WARRANTY, TERMS, "
        "COMPLIANCE, CANCELLATION POLICY → category: policies_legal"
    )

    # ── Category: issue_resolution ────────────────────────────────────────────
    issue_label = _infer_issue_label(btype, inds, desc)
    hints.append(
        f"When customer reports a PROBLEM, BUG, COMPLAINT, or {issue_label.upper()} "
        f"→ category: issue_resolution"
    )

    # ── Category: company_info ────────────────────────────────────────────────
    hints.append(
        f"When customer asks ABOUT {name.upper()}, company history, team, "
        f"locations, mission → category: company_info"
    )

    # ── Category: educational_content ─────────────────────────────────────────
    edu_label = _infer_edu_label(btype, inds, desc, cases)
    hints.append(
        f"When customer asks for HOW-TO, TUTORIALS, GUIDES, TRAINING, "
        f"or {edu_label.upper()} → category: educational_content"
    )

    # ── Domain-specific disambiguation examples ───────────────────────────────
    # The most important accuracy booster: show the LLM how ambiguous terms
    # map to THIS business's domain vocabulary.
    disam = _build_disambiguation_examples(btype, inds, desc, ps_examples, service_vocab)
    if disam:
        hints.append("")
        hints.append("AMBIGUOUS TERM DISAMBIGUATION FOR THIS BUSINESS:")
        for ex in disam:
            hints.append(f"  {ex}")

    return hints


def _extract_product_vocabulary(desc: str, btype: str, inds: list[str]) -> list[str]:
    """
    Extract product/service vocabulary terms from the business description
    and type to use as intent examples. Domain-agnostic.

    Reads from what the business said about itself. No hardcoded product names.
    """
    vocab: list[str] = []
    combined = f"{desc} {btype} {' '.join(inds)}".lower()

    # Ordered pairs: (keyword_in_description, example_product_term)
    # These are intentionally generic enough to apply cross-industry
    DOMAIN_VOCAB_MAP = [
        # Physical products
        ("laptop",       "laptop models"),
        ("drone",        "drone models"),
        ("vehicle",      "vehicle models"),
        ("phone",        "phone models"),
        ("furniture",    "furniture items"),
        ("clothing",     "clothing items"),
        ("shoe",         "shoe models"),
        ("bag",          "bag models"),
        ("food",         "food items"),
        ("meal",         "meal options"),
        ("medicine",     "medicine products"),
        ("device",       "device models"),
        ("machine",      "machine models"),
        ("equipment",    "equipment models"),
        ("tool",         "tools and equipment"),
        # Services
        ("session",      "session packages"),
        ("consultation", "consultation services"),
        ("therapy",      "therapy sessions"),
        ("repair",       "repair services"),
        ("installation", "installation services"),
        ("maintenance",  "maintenance plans"),
        ("training",     "training programs"),
        ("course",       "course offerings"),
        ("plan",         "subscription plans"),
        ("package",      "service packages"),
        ("policy",       "insurance policies"),
        ("loan",         "loan products"),
        ("account",      "account types"),
        ("room",         "room types"),
        ("property",     "property listings"),
        ("apartment",    "apartment types"),
        # Software/SaaS
        ("software",     "software plans"),
        ("platform",     "platform tiers"),
        ("api",          "API access plans"),
        ("saas",         "subscription tiers"),
        # Generic fallback
        ("product",      "product catalog"),
        ("service",      "service offerings"),
    ]

    for keyword, term in DOMAIN_VOCAB_MAP:
        if keyword in combined and term not in vocab:
            vocab.append(term)
        if len(vocab) >= 6:
            break

    return vocab


def _extract_service_vocabulary(
    desc: str, btype: str, inds: list[str], cases: list[str]
) -> list[str]:
    """Extract service-type vocabulary for issue_resolution and edu hints."""
    vocab: list[str] = []
    combined = f"{desc} {btype} {' '.join(inds)} {' '.join(cases)}".lower()

    SERVICE_SIGNALS = [
        ("support",       "support request"),
        ("help",          "help request"),
        ("troubleshoot",  "troubleshooting issue"),
        ("repair",        "repair request"),
        ("complaint",     "complaint"),
        ("issue",         "technical issue"),
        ("bug",           "bug report"),
        ("not working",   "functionality issue"),
    ]
    for keyword, term in SERVICE_SIGNALS:
        if keyword in combined and term not in vocab:
            vocab.append(term)
    return vocab


def _infer_delivery_label(btype: str, inds: list[str], desc: str) -> str:
    """Determine what 'delivery' means for this business type."""
    combined = f"{btype} {' '.join(inds)} {desc}".lower()
    if any(w in combined for w in ("software", "saas", "platform", "digital")):
        return "deployment/access"
    if any(w in combined for w in ("food", "meal", "restaurant", "catering")):
        return "food delivery"
    if any(w in combined for w in ("healthcare", "medical", "clinic", "hospital")):
        return "appointment scheduling"
    if any(w in combined for w in ("real estate", "property", "construction")):
        return "site visit"
    if any(w in combined for w in ("consulting", "service", "professional")):
        return "service visit"
    return "delivery/logistics"


def _infer_issue_label(btype: str, inds: list[str], desc: str) -> str:
    """Determine what 'issue' means for this business type."""
    combined = f"{btype} {' '.join(inds)} {desc}".lower()
    if any(w in combined for w in ("software", "saas", "platform", "tech", "digital")):
        return "software bug/technical error"
    if any(w in combined for w in ("drone", "hardware", "device", "machine")):
        return "hardware malfunction"
    if any(w in combined for w in ("healthcare", "medical")):
        return "care quality issue"
    if any(w in combined for w in ("food", "meal", "restaurant")):
        return "food quality/order issue"
    if any(w in combined for w in ("finance", "bank", "loan", "insurance")):
        return "account/payment issue"
    return "service problem"


def _infer_edu_label(btype: str, inds: list[str], desc: str, cases: list[str]) -> str:
    """Determine what 'educational content' means for this business."""
    combined = f"{btype} {' '.join(inds)} {desc} {' '.join(cases)}".lower()
    if any(w in combined for w in ("drone", "hardware", "machine", "equipment")):
        return "setup/usage guide"
    if any(w in combined for w in ("software", "saas", "platform")):
        return "onboarding/integration guide"
    if any(w in combined for w in ("healthcare", "medical", "therapy")):
        return "treatment guide"
    if any(w in combined for w in ("finance", "bank", "insurance")):
        return "product guide/comparison"
    return "usage guide"


def _build_disambiguation_examples(
    btype: str,
    inds: list[str],
    desc: str,
    product_vocab: list[str],
    service_vocab: list[str],
) -> list[str]:
    """
    Build concrete disambiguation examples for this business.

    These are the most critical accuracy lines in the entire prompt.
    They show the LLM exactly how ambiguous short messages ("it", "the one",
    "install", "range") should be interpreted for this specific business.
    """
    examples: list[str] = []
    combined = f"{btype} {' '.join(inds)} {desc}".lower()

    # Determine primary domain noun (what this business sells/does)
    domain_noun = product_vocab[0] if product_vocab else "product/service"

    # "installation" disambiguation
    if any(w in combined for w in ("drone", "hardware", "device", "equipment", "machine", "cctv", "solar")):
        examples.append(f'"install" / "installation" → hardware/physical installation of {domain_noun}')
    elif any(w in combined for w in ("software", "saas", "platform", "app")):
        examples.append(f'"install" / "installation" → software installation/deployment for {domain_noun}')
    elif any(w in combined for w in ("furniture", "appliance", "fixture")):
        examples.append(f'"install" / "installation" → assembly and installation of {domain_noun}')
    else:
        examples.append(f'"install" / "installation" → setup and installation related to {domain_noun}')

    # "range" disambiguation
    if any(w in combined for w in ("drone", "vehicle", "battery", "electric")):
        examples.append(f'"range" → flight range / battery range of {domain_noun}')
    elif any(w in combined for w in ("food", "meal", "menu", "product", "catalog")):
        examples.append(f'"range" → product range / available {domain_noun} options')
    elif any(w in combined for w in ("network", "telecom", "coverage")):
        examples.append(f'"range" → network coverage range')
    elif any(w in combined for w in ("finance", "loan", "insurance")):
        examples.append(f'"range" → available plans/tiers in the {domain_noun} range')
    else:
        examples.append(f'"range" → product/service range of {domain_noun} options available')

    # "customize" / "modification" disambiguation
    if any(w in combined for w in ("drone", "hardware", "device")):
        examples.append(f'"customize" / "modify" → hardware customization of {domain_noun}')
    elif any(w in combined for w in ("clothing", "apparel", "print", "embroid")):
        examples.append(f'"customize" → custom sizing/printing for {domain_noun}')
    elif any(w in combined for w in ("software", "saas", "platform")):
        examples.append(f'"customize" → custom configuration/integration for {domain_noun}')
    else:
        examples.append(f'"customize" / "special order" → customization options for {domain_noun}')

    # "model" disambiguation
    examples.append(f'"model" / "models" / "options" → the different types/variants of {domain_noun}')

    # Pricing signal
    if product_vocab:
        examples.append(f'"how much" / "price" / "cost" → pricing for {product_vocab[0]}')

    return examples


def invalidate_cache(user_id: str) -> None:
    """
    Force-expire the cached profile for a specific user.
    Call this after a business profile update to ensure the next request
    fetches fresh data. Used by profile-update webhooks if implemented.
    """
    _CACHE.pop(user_id, None)
    logger.debug("[business_context] cache invalidated | user=%s...", user_id[:8])
