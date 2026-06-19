"""
Data Analytics Engine — Category-Specific Business Intelligence
===============================================================
Architecture: dispatcher → category builder → intelligence schema → Qdrant upsert

GLOBALLY SCALABLE — works for ANY business in ANY domain:
  retail, SaaS, healthcare, pharma, food & beverage, fintech,
  manufacturing, real estate, education, hospitality, logistics, etc.

Zero domain-specific hardcodes. Every builder derives intelligence
exclusively from the actual data present in each entry — titles,
field values, numeric attributes, and status fields. No assumptions
about product types, industry verticals, or company names.

Builders
--------
ProductIntelligenceBuilder      → price tiers, status breakdown, category/subcategory
                                   distribution, numeric spec distributions, item names
OffersIntelligenceBuilder       → status (active/scheduled/expired), discount types
                                   (percentage/fixed/free), audience segments from titles,
                                   largest discounts extracted from any title pattern
ContactIntelligenceBuilder      → department/role breakdown from actual field values,
                                   channel availability (email/phone/chat/whatsapp),
                                   location/region detection from titles
ShippingIntelligenceBuilder     → delivery speed flags (express/standard/same-day),
                                   scope flags (international/domestic/local),
                                   special service flags (free/eco/white-glove/business)
CompanyIntelligenceBuilder      → presence indicators derived from actual field titles,
                                   identity/contact/strategy field groupings
PoliciesIntelligenceBuilder     → universal policy category mapping (rights/privacy/
                                   security/legal/compliance/coverage/accessibility)
EducationIntelligenceBuilder    → skill level from attributes + title signals,
                                   content type from title patterns, topic map
IssueResolutionIntelligenceBuilder → issue category from title/description,
                                      severity/resolution tracking

Critical contract
-----------------
Analytics is NAVIGATION, not evidence.
It helps Brain #1 discover what exists and plan retrieval.
It NEVER replaces actual source records.

Multi-tenant: scoped by user_id — never cross-tenant.
"""
from __future__ import annotations

import logging
import re
import statistics
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Subtype written on every analytics (source_insights) point.
# Distinct from regular data subtypes — lets automationservice filter
# analytics entries separately from regular ingested records.
_ANALYTICS_SUBTYPE = "data_analytics"


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT — dispatcher
# ══════════════════════════════════════════════════════════════════════════════

def compute_source_analytics(
    entries: List[Dict[str, Any]],
    source_id: str,
    source_name: str,
    category_hint: str = "",
) -> Dict[str, Any]:
    """
    Dispatch to the correct category intelligence builder.

    Each entry is expected to have:
        title          : str   — item display name
        category       : str   — e.g. "product_service"
        quality_score  : float
        attributes     : dict  — typed canonical fields (price, status, etc.)
        structured_data: dict  — original CSV fields (fallback read source)
    """
    if not entries:
        return {}

    category = category_hint or _dominant_category(entries)

    builder     = _get_builder(category)
    intelligence = builder.build(entries, source_id, source_name, category)

    search_text = _build_search_text(intelligence, source_name, category)
    ai_tags     = _build_ai_tags(category, intelligence)
    keywords    = _build_keywords(intelligence, source_name, category)

    return {
        "category":        category,        # scoped to the actual source category, not a generic bucket
        "subtype":         _ANALYTICS_SUBTYPE,
        "title":           f"Analytics: {source_name}",
        "search_text":     search_text,
        "structured_data": intelligence,
        "attributes": {
            "source_id":        source_id,
            "total_entries":    intelligence.get("total_entries", len(entries)),
            "primary_category": category,
            "status":           "active",
            "priority_score":   5,
        },
        "ai_tags":       ai_tags,
        "keywords":      keywords,
        "quality_score": 95.0,
        "source_type":   "analytics",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY BUILDER BASE
# ══════════════════════════════════════════════════════════════════════════════

class _BaseBuilder:
    def build(
        self,
        entries: List[Dict[str, Any]],
        source_id: str,
        source_name: str,
        category: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    # ── Shared helpers ────────────────────────────────────────────────────

    @staticmethod
    def _title(entry: Dict[str, Any]) -> str:
        return str(entry.get("title") or "").strip()

    @staticmethod
    def _attr(entry: Dict[str, Any], key: str, fallback: Any = None) -> Any:
        """Read from attributes first, then structured_data, then fallback."""
        attrs = entry.get("attributes") or {}
        sd    = entry.get("structured_data") or {}
        v = attrs.get(key)
        if v is None:
            v = sd.get(key)
        return v if v is not None else fallback

    @staticmethod
    def _status(entry: Dict[str, Any]) -> str:
        attrs = entry.get("attributes") or {}
        sd    = entry.get("structured_data") or {}
        raw = (attrs.get("status") or sd.get("status") or
               sd.get("availability") or sd.get("availability_status") or "")
        return str(raw).strip()

    @staticmethod
    def _names(entries: List[Dict[str, Any]]) -> List[str]:
        seen: set = set()
        result: List[str] = []
        for e in entries:
            t = str(e.get("title") or "").strip()
            if t and t not in seen:
                seen.add(t)
                result.append(t)
        return result

    @staticmethod
    def _price(entry: Dict[str, Any]) -> Optional[float]:
        """Extract price from any recognizable price field."""
        attrs = entry.get("attributes") or {}
        sd    = entry.get("structured_data") or {}
        for src in (attrs, sd):
            for key in ("price", "Price", "selling_price", "unit_price",
                        "cost", "rate", "fee", "amount", "mrp", "list_price"):
                v = src.get(key)
                if v is not None:
                    cleaned = re.sub(r"[^\d.]", "", str(v))
                    if cleaned:
                        try:
                            return float(cleaned)
                        except ValueError:
                            pass
        return None

    @staticmethod
    def _contains_any(text: str, keywords: List[str]) -> bool:
        t = text.lower()
        return any(k in t for k in keywords)

    @staticmethod
    def _normalize_status(raw: str) -> str:
        """Normalize any status string to a lowercase canonical form."""
        s = raw.strip().lower()
        _active   = {"active", "available", "live", "enabled", "yes", "in stock",
                     "instock", "in-stock", "published", "open", "approved"}
        _inactive = {"inactive", "disabled", "discontinued", "archived", "draft",
                     "no", "out of stock", "out-of-stock", "outofstock", "closed",
                     "expired", "rejected", "deleted"}
        _pending  = {"pending", "scheduled", "draft", "in review", "queued",
                     "processing", "waiting"}
        if s in _active:   return "active"
        if s in _inactive: return "inactive"
        if s in _pending:  return "scheduled"
        return s or "active"

    @staticmethod
    def _base_meta(
        entries: List[Dict[str, Any]],
        source_id: str,
        source_name: str,
        category: str,
    ) -> Dict[str, Any]:
        return {
            "total_entries":    len(entries),
            "source_id":        source_id,
            "source_name":      source_name,
            "primary_category": category,
            "computed_at":      datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _collect_field_values(entries: List[Dict[str, Any]], field: str) -> List[str]:
        """Collect all non-empty string values for a given field across entries."""
        values = []
        for e in entries:
            for src in (e.get("attributes") or {}, e.get("structured_data") or {}):
                v = src.get(field)
                if v:
                    s = str(v).strip()
                    if s and s.lower() not in ("none", "null", "n/a", "na", "-", ""):
                        values.append(s)
                        break
        return values

    @staticmethod
    def _count_distribution(values: List[str]) -> Dict[str, int]:
        """Build a frequency distribution dict from a list of string values."""
        dist: Dict[str, int] = {}
        for v in values:
            dist[v] = dist.get(v, 0) + 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))

    @staticmethod
    def _numeric_stats(values: List[float]) -> Dict[str, Any]:
        """Compute basic numeric stats for a list of floats."""
        if not values:
            return {}
        sv = sorted(values)
        n  = len(sv)
        return {
            "count":  n,
            "min":    round(sv[0], 2),
            "max":    round(sv[-1], 2),
            "mean":   round(statistics.mean(sv), 2),
            "median": round(statistics.median(sv), 2),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 1 — PRODUCT / SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class ProductIntelligenceBuilder(_BaseBuilder):
    """
    Universal product/service intelligence builder.

    Works for: laptops, phones, furniture, clothing, food, pharma, SaaS plans,
    vehicles, machinery, medical devices, books, software licences — anything.

    Intelligence derived entirely from actual field values present in the data:
      - Price tiers from numeric price distribution (budget/mid/premium split
        at 33rd and 67th percentile — adapts to any price range)
      - Category/subcategory distribution from the actual category field values
      - Status distribution from the actual status field values
      - Numeric spec distributions from ANY numeric fields present in the data
        (not hardcoded to RAM/CPU — works for weight, dosage, screen size, etc.)
      - Item name list for discovery
    """

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        prices:        List[float]           = []
        priced_items:  List[Dict[str, Any]]  = []
        status_counts: Dict[str, int]        = {}
        cat_dist:      Dict[str, int]        = {}
        subcat_dist:   Dict[str, int]        = {}

        # Collect numeric field values dynamically — works for any domain
        numeric_fields: Dict[str, List[float]] = {}

        for entry in entries:
            title  = self._title(entry)
            price  = self._price(entry)
            status = self._normalize_status(self._status(entry) or "active")

            status_counts[status] = status_counts.get(status, 0) + 1

            if price is not None:
                prices.append(price)
                priced_items.append({"name": title, "price": price})

            # Category / subcategory distribution from actual field values
            # Use _attr which already merges attrs + sd with attrs taking precedence
            cat_val = self._attr(entry, "category") or self._attr(entry, "type") or ""
            if cat_val and str(cat_val).strip():
                k = str(cat_val).strip()
                cat_dist[k] = cat_dist.get(k, 0) + 1

            subcat_val = self._attr(entry, "subcategory") or self._attr(entry, "subtype") or ""
            # Exclude the analytics subtype marker from subcategory distribution
            if subcat_val and str(subcat_val).strip() and str(subcat_val).strip() != "data_analytics":
                k = str(subcat_val).strip()
                subcat_dist[k] = subcat_dist.get(k, 0) + 1

            # Collect ALL numeric field values (domain-agnostic spec detection)
            # Only collect from fields whose values are genuinely numeric —
            # skip string fields that happen to contain a digit (e.g. product names,
            # processor model strings). Rule: accept a string only if it consists
            # ENTIRELY of digits and at most one decimal point (no letters).
            #
            # DEDUP: merge attributes and structured_data into a single dict so
            # that overlapping keys (e.g. "ram" in both) are not double-counted.
            # attributes takes precedence over structured_data.
            attrs_sd = {**(entry.get("structured_data") or {}), **(entry.get("attributes") or {})}
            for field_key, field_val in attrs_sd.items():
                # Skip identity/meta/price fields — already handled above
                if field_key in ("price", "cost", "rate", "fee", "amount", "mrp",
                                 "priority_score", "quality_score",
                                 "product_name", "name", "title", "description",
                                 "processor", "category", "subcategory", "status",
                                 "source_id", "source_name", "primary_category"):
                    continue
                if isinstance(field_val, (int, float)) and not isinstance(field_val, bool):
                    numeric_fields.setdefault(field_key, []).append(float(field_val))
                elif isinstance(field_val, str):
                    # Only accept strings that are purely numeric (no letters)
                    stripped = field_val.strip()
                    cleaned  = re.sub(r"[^\d.]", "", stripped)
                    # Reject if original had any letter — it's a model/name string
                    if cleaned and len(cleaned) <= 10 and not re.search(r"[a-zA-Z]", stripped):
                        try:
                            numeric_fields.setdefault(field_key, []).append(float(cleaned))
                        except ValueError:
                            pass

        # Price tiers — percentile-based, adapts to any price range
        price_dist:     Dict[str, int]      = {}
        cheapest        = most_expensive    = None
        avg_price       = None
        price_stats:    Dict[str, Any]      = {}

        if prices:
            sv    = sorted(prices)
            n     = len(sv)
            p33   = sv[int(n * 0.33)]
            p67   = sv[int(n * 0.67)]
            price_dist = {
                "budget":    sum(1 for p in prices if p <= p33),
                "mid_range": sum(1 for p in prices if p33 < p <= p67),
                "premium":   sum(1 for p in prices if p > p67),
            }
            cheapest       = min(priced_items, key=lambda x: x["price"])
            most_expensive = max(priced_items, key=lambda x: x["price"])
            avg_price      = round(statistics.mean(prices), 2)
            price_stats    = self._numeric_stats(prices)

        # Numeric spec distributions — only include fields with ≥2 distinct values
        # and ≥3 entries (avoids noise from ID fields)
        spec_distributions: Dict[str, Dict[str, Any]] = {}
        for field_key, vals in numeric_fields.items():
            if len(vals) >= 3 and len(set(vals)) >= 2:
                spec_distributions[field_key] = self._numeric_stats(vals)

        total = len(entries)
        summary_parts = [f"{total} items."]
        if prices:
            summary_parts.append(
                f"Price range {price_stats['min']:,.2f}–{price_stats['max']:,.2f}, "
                f"avg {avg_price:,.2f}."
            )
            summary_parts.append(
                f"Budget: {price_dist['budget']}, "
                f"mid-range: {price_dist['mid_range']}, "
                f"premium: {price_dist['premium']}."
            )
        if cat_dist:
            summary_parts.append(
                "Categories: " + ", ".join(f"{k}({v})" for k, v in list(cat_dist.items())[:5]) + "."
            )
        if status_counts:
            summary_parts.append(
                "Status: " + ", ".join(f"{k}({v})" for k, v in status_counts.items()) + "."
            )

        return {
            **meta,
            "total_products":         total,
            "products_with_price":    len(prices),
            "price_distribution":     price_dist,
            "cheapest_product":       cheapest,
            "most_expensive_product": most_expensive,
            "avg_price":              avg_price,
            "price_stats":            price_stats,
            "price_range":            {"min": price_stats.get("min"), "max": price_stats.get("max")} if price_stats else {},
            "status_breakdown":       status_counts,
            "category_distribution":  cat_dist,
            "subcategory_distribution": subcat_dist,
            "spec_distributions":     spec_distributions,
            "all_item_names":         self._names(entries),
            "intelligence_summary":   " ".join(summary_parts),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 2 — OFFERS / PROMOTIONS
# ══════════════════════════════════════════════════════════════════════════════

class OffersIntelligenceBuilder(_BaseBuilder):
    """
    Universal offers/promotions intelligence builder.

    Works for: retail discounts, SaaS coupons, restaurant deals, hotel promos,
    pharma rebates, B2B trade programmes, subscription discounts, etc.

    Intelligence derived from:
      - Status field values (active/scheduled/expired) — domain-agnostic
      - Percentage/fixed discount extraction via regex on title text
      - Audience segment detection from title keywords (universal signals:
        student, business, enterprise, new user, returning, referral, bundle)
      - Free-item offers detected by "free" prefix in title
      - Offer type distribution from actual offer_type/type field values
    """

    # Universal audience signals — applicable across all industries
    _AUDIENCE_SIGNALS = {
        "student":           ["student", "academic", "university", "college", "school"],
        "business":          ["business", "enterprise", "corporate", "b2b", "company",
                              "professional", "commercial"],
        "new_customer":      ["new customer", "first purchase", "first order",
                              "first time", "welcome", "new user", "sign up"],
        "returning_customer":["returning", "loyal", "loyalty", "repeat", "existing",
                              "member", "subscriber"],
        "referral":          ["referral", "refer a friend", "invite", "recommend"],
        "bundle":            ["bundle", "buy", "combo", "package", "kit", "set",
                              "get 1 free", "get one free", "bulk"],
        "trade_in":          ["trade-in", "trade in", "tradein", "exchange", "upgrade bonus"],
        "seasonal":          ["seasonal", "holiday", "festival", "sale", "clearance",
                              "flash", "limited time", "weekend", "event"],
        "subscription":      ["subscription", "annual", "monthly", "plan", "membership"],
        "cashback":          ["cashback", "cash back", "rebate", "reward", "points"],
    }

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        active = scheduled = expired = 0
        offer_types:     Dict[str, int]        = {}
        audience_segments: Dict[str, int]      = {}
        pct_discounts:   List[Dict[str, Any]]  = []
        fixed_discounts: List[Dict[str, Any]]  = []
        free_item_offers: List[str]            = []
        all_names = self._names(entries)

        for entry in entries:
            title  = self._title(entry)
            tl     = title.lower()
            status = self._normalize_status(self._status(entry) or "active")

            # Status bucketing
            if status == "active":
                active += 1
            elif status == "scheduled":
                scheduled += 1
            elif status in ("inactive", "expired"):
                expired += 1
            else:
                active += 1

            # Offer type from actual field value (any domain)
            otype = self._attr(entry, "offer_type") or self._attr(entry, "type") or ""
            if otype and str(otype).strip():
                k = str(otype).strip()
                offer_types[k] = offer_types.get(k, 0) + 1

            # Audience segment from title — universal signals
            for seg, tokens in self._AUDIENCE_SIGNALS.items():
                if self._contains_any(tl, tokens):
                    audience_segments[seg] = audience_segments.get(seg, 0) + 1

            # Percentage discount extraction from title
            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", tl)
            if pct_match:
                pct_discounts.append({
                    "name":  title,
                    "value": float(pct_match.group(1)),
                })

            # Fixed currency discount extraction — handles $, £, €, ₹, ¥ and plain numbers
            fixed_match = re.search(
                r"(?:[$£€₹¥]|rs\.?\s*|inr\s*)(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
                tl, re.IGNORECASE
            )
            if fixed_match:
                val_str = fixed_match.group(1).replace(",", "")
                try:
                    fixed_discounts.append({"name": title, "value": float(val_str)})
                except ValueError:
                    pass

            # Free-item offer detection — universal signal
            if re.search(r"\bfree\b", tl) and not re.search(r"\bfree shipping\b", tl):
                free_item_offers.append(title)

        # Largest discounts
        largest_pct   = max(pct_discounts, key=lambda x: x["value"]) if pct_discounts else None
        largest_fixed = max(fixed_discounts, key=lambda x: x["value"]) if fixed_discounts else None

        if largest_pct:
            largest_pct = {"name": largest_pct["name"], "value": f"{largest_pct['value']:.0f}%"}
        if largest_fixed:
            largest_fixed = {"name": largest_fixed["name"], "value": largest_fixed["value"]}

        discount_dist: Dict[str, int] = {}
        if pct_discounts:
            vals = [d["value"] for d in pct_discounts]
            discount_dist["under_10_pct"] = sum(1 for v in vals if v < 10)
            discount_dist["10_to_20_pct"] = sum(1 for v in vals if 10 <= v <= 20)
            discount_dist["over_20_pct"]  = sum(1 for v in vals if v > 20)
        if fixed_discounts:
            discount_dist["fixed_amount"] = len(fixed_discounts)
        if free_item_offers:
            discount_dist["free_item"] = len(free_item_offers)

        total = len(entries)

        # Validate: discount buckets count offers by pattern match, not by offer_type field,
        # so some offers may match multiple patterns. Log a warning when totals diverge.
        total_bucketed = sum(discount_dist.values())
        if total_bucketed > total:
            logger.warning(
                "discount_distribution total (%d) exceeds offer count (%d) — "
                "some offers match multiple discount patterns (counted in each matching bucket)",
                total_bucketed, total,
            )

        summary_parts = [
            f"{total} offers: {active} active, {scheduled} scheduled, {expired} expired."
        ]
        if largest_pct:
            summary_parts.append(f"Largest % discount: {largest_pct['value']} ({largest_pct['name']}).")
        if largest_fixed:
            summary_parts.append(f"Largest fixed discount: {largest_fixed['name']}.")
        if audience_segments:
            segs = ", ".join(f"{k}({v})" for k, v in audience_segments.items())
            summary_parts.append(f"Audience segments: {segs}.")
        if free_item_offers:
            summary_parts.append(f"Free item offers: {len(free_item_offers)}.")

        return {
            **meta,
            "total_offers":               total,
            "active_offers":              active,
            "scheduled_offers":           scheduled,
            "expired_offers":             expired,
            "offer_type_distribution":    offer_types,
            "audience_segments":          audience_segments,
            "discount_distribution":      discount_dist,
            "largest_percentage_discount": largest_pct,
            "largest_fixed_discount":     largest_fixed,
            "free_item_offers":           free_item_offers,
            "all_offer_names":            all_names,
            "intelligence_summary":       " ".join(summary_parts),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 3 — CONTACT / SUPPORT
# ══════════════════════════════════════════════════════════════════════════════

class ContactIntelligenceBuilder(_BaseBuilder):
    """
    Universal contact/support intelligence builder.

    Works for: tech support, medical helplines, bank branches, HR teams,
    law firm contacts, hotel front desk, restaurant reservation teams, etc.

    Intelligence derived from:
      - Department/role from actual field values (department, category, role fields)
      - Channel detection from actual email/phone/website field presence
      - Location/region from title keywords (universal geographic signals)
      - Specialized team detection from title patterns
    """

    # Universal channel detection — checks actual field values, not hardcoded names
    # These are field names that indicate channel presence
    _CHANNEL_FIELDS = {
        "email":    ["email", "e_mail", "support_email", "contact_email", "mail"],
        "phone":    ["phone", "mobile", "telephone", "contact_number", "contact_no",
                     "tel", "fax", "hotline"],
        "website":  ["website", "url", "web", "portal", "link"],
        "chat":     ["chat", "live_chat", "messenger", "whatsapp", "telegram",
                     "slack", "discord"],
        "in_person": ["address", "location", "office", "branch", "walk_in",
                      "appointment"],
    }

    # Universal geographic region signals
    _REGION_SIGNALS = [
        "north", "south", "east", "west", "central",
        "northeast", "northwest", "southeast", "southwest",
        "region", "zone", "district", "branch", "office",
    ]

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        dept_counts:      Dict[str, int]  = {}
        channel_presence: Dict[str, bool] = {ch: False for ch in self._CHANNEL_FIELDS}
        regions:          List[str]       = []
        specialized_teams: List[str]      = []
        all_names = self._names(entries)

        for entry in entries:
            title = self._title(entry)
            tl    = title.lower()
            attrs = entry.get("attributes") or {}
            sd    = entry.get("structured_data") or {}
            merged = {**sd, **attrs}

            # Department from actual field values — works for any industry
            dept = (attrs.get("department") or sd.get("department") or
                    attrs.get("category") or sd.get("category") or
                    attrs.get("role") or sd.get("role") or
                    attrs.get("team") or sd.get("team") or
                    attrs.get("type") or sd.get("type") or "")
            if dept and str(dept).strip():
                k = str(dept).strip()
                dept_counts[k] = dept_counts.get(k, 0) + 1
            else:
                # Fallback: use first significant word of title as department label
                words = [w for w in tl.split() if len(w) > 3]
                dept_label = words[0].title() if words else "General"
                dept_counts[dept_label] = dept_counts.get(dept_label, 0) + 1

            # Channel detection — check actual field values AND title text
            for channel, field_names in self._CHANNEL_FIELDS.items():
                # 1) Field-value presence check
                for fn in field_names:
                    v = merged.get(fn)
                    if v and str(v).strip() and str(v).strip().lower() not in ("none", "n/a", "-"):
                        channel_presence[channel] = True
                        break
                # 2) Title-text fallback — catches entries whose title IS the channel
                #    (e.g. "Live Chat", "WhatsApp Support", "Email Helpdesk")
                if not channel_presence[channel]:
                    if self._contains_any(tl, field_names):
                        channel_presence[channel] = True

            # Region/location detection from title
            for sig in self._REGION_SIGNALS:
                if sig in tl:
                    region_label = title  # use full title as the region label
                    if region_label not in regions:
                        regions.append(region_label)
                    break

            # Specialized team: any entry with escalation/vip/specialist signals
            if self._contains_any(tl, ["escalation", "vip", "specialist", "expert",
                                        "senior", "dedicated", "priority", "key account",
                                        "premium care", "ai features"]):
                if title not in specialized_teams:
                    specialized_teams.append(title)

        active_channels = [ch for ch, present in channel_presence.items() if present]
        summary_parts = [f"{len(entries)} support contacts."]
        if dept_counts:
            summary_parts.append(
                "Departments: " + ", ".join(list(dept_counts.keys())[:6]) + "."
            )
        if active_channels:
            summary_parts.append("Channels: " + ", ".join(active_channels) + ".")
        if regions:
            summary_parts.append(f"{len(regions)} regional contacts.")

        return {
            **meta,
            "total_contacts":       len(entries),
            "department_breakdown": dept_counts,
            "support_channels":     {
                **{ch: present for ch, present in channel_presence.items()},
                "regional_contacts": len(regions),
            },
            "regional_contacts":    regions[:20],
            "specialized_teams":    specialized_teams,
            "all_contact_names":    all_names,
            "intelligence_summary": " ".join(summary_parts),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 4 — DELIVERY / SHIPPING
# ══════════════════════════════════════════════════════════════════════════════

class ShippingIntelligenceBuilder(_BaseBuilder):
    """
    Universal delivery/shipping intelligence builder.

    Works for: e-commerce, food delivery, pharma distribution, B2B freight,
    furniture logistics, document courier, medical supply chains, etc.

    Intelligence derived entirely from title text signals:
      Speed flags:     express, same-day, overnight, next-day, standard, economy
      Scope flags:     international, domestic, local, cross-border, worldwide
      Service flags:   free, tracked, insured, white-glove, eco, temperature-controlled
      Audience flags:  business, enterprise, retail, wholesale, personal
    Status from actual field values.
    """

    # Universal delivery speed signals
    _SPEED_SIGNALS = {
        "same_day":    ["same day", "same-day", "immediate", "instant", "within hours"],
        "next_day":    ["next day", "next-day", "overnight", "24 hour", "24hr",
                        "next business day"],
        "express":     ["express", "priority", "urgent", "rush", "fast track",
                        "expedited", "quick"],
        "standard":    ["standard", "regular", "normal", "economy", "ground"],
        "scheduled":   ["scheduled", "appointment", "fixed date", "slot", "pre-book"],
    }

    # Universal scope signals
    _SCOPE_SIGNALS = {
        "international": ["international", "global", "worldwide", "cross-border",
                           "overseas", "export", "import", "foreign"],
        "domestic":      ["domestic", "national", "nationwide", "within country",
                           "local delivery", "countrywide"],
        "local":         ["local", "city", "urban", "nearby", "neighborhood",
                           "same city", "hyperlocal"],
    }

    # Universal service feature signals
    _SERVICE_SIGNALS = {
        "free":                 ["free shipping", "free delivery", "no charge",
                                  "complimentary delivery"],
        "tracked":              ["tracked", "tracking", "real-time", "gps",
                                  "live tracking"],
        "insured":              ["insured", "insurance", "protected", "covered",
                                  "guaranteed"],
        "white_glove":          ["white glove", "white-glove", "premium delivery",
                                  "installation", "assembly", "in-home"],
        "eco":                  ["eco", "green", "sustainable", "carbon neutral",
                                  "electric vehicle", "ev delivery", "bicycle"],
        "temperature_controlled":["temperature", "cold chain", "refrigerated",
                                   "frozen", "chilled", "pharma"],
        "bulk":                 ["bulk", "freight", "cargo", "pallet", "wholesale",
                                  "enterprise bulk", "b2b"],
        "contactless":          ["contactless", "no contact", "drop-off", "locker",
                                  "pickup point", "click and collect"],
    }

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        speed_counts:   Dict[str, int]  = {}
        scope_counts:   Dict[str, int]  = {}
        service_counts: Dict[str, int]  = {}
        status_counts:  Dict[str, int]  = {}
        all_names = self._names(entries)

        for entry in entries:
            tl     = self._title(entry).lower()
            status = self._normalize_status(self._status(entry) or "active")
            status_counts[status] = status_counts.get(status, 0) + 1

            for speed, tokens in self._SPEED_SIGNALS.items():
                if self._contains_any(tl, tokens):
                    speed_counts[speed] = speed_counts.get(speed, 0) + 1
                    break
            else:
                speed_counts["standard"] = speed_counts.get("standard", 0) + 1

            for scope, tokens in self._SCOPE_SIGNALS.items():
                if self._contains_any(tl, tokens):
                    scope_counts[scope] = scope_counts.get(scope, 0) + 1
                    break

            for svc, tokens in self._SERVICE_SIGNALS.items():
                if self._contains_any(tl, tokens):
                    service_counts[svc] = service_counts.get(svc, 0) + 1

        # Boolean flags for the most commonly queried capabilities
        flags = {
            "express_available":       bool(speed_counts.get("express") or speed_counts.get("next_day")),
            "same_day_available":      bool(speed_counts.get("same_day")),
            "international_available": bool(scope_counts.get("international")),
            "free_shipping_available": bool(service_counts.get("free")),
            "tracked_available":       bool(service_counts.get("tracked")),
            "eco_option_available":    bool(service_counts.get("eco")),
            "white_glove_available":   bool(service_counts.get("white_glove")),
            "bulk_available":          bool(service_counts.get("bulk")),
            "contactless_available":   bool(service_counts.get("contactless")),
        }

        active_flags = [k.replace("_available", "").replace("_", " ")
                        for k, v in flags.items() if v]
        summary = (
            f"{len(entries)} delivery options. "
            + (f"Speed options: {', '.join(speed_counts.keys())}. " if speed_counts else "")
            + ("Available services: " + ", ".join(active_flags) + "." if active_flags else "")
        )

        return {
            **meta,
            "total_options":    len(entries),
            "speed_breakdown":  speed_counts,
            "scope_breakdown":  scope_counts,
            "service_breakdown": service_counts,
            "status_breakdown": status_counts,
            **flags,
            "all_shipping_names":    all_names,
            "intelligence_summary":  summary.strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 5 — COMPANY INFORMATION
# ══════════════════════════════════════════════════════════════════════════════

class CompanyIntelligenceBuilder(_BaseBuilder):
    """
    Universal company information intelligence builder.

    Works for any company — tech startup, hospital, law firm, manufacturer,
    NGO, government agency, restaurant chain, etc.

    Intelligence derived from actual field/entry titles present in the data.
    Uses universal keyword signals that apply to any organisation type.
    """

    # Universal identity field signals — any organisation will have these
    _IDENTITY_SIGNALS   = ["name", "founded", "established", "incorporated",
                            "headquarters", "hq", "industry", "sector", "type",
                            "size", "employee", "staff", "ceo", "founder",
                            "president", "director", "website", "registration",
                            "tax id", "company number"]

    _CONTACT_SIGNALS    = ["email", "phone", "address", "office", "hours",
                            "contact", "helpline", "support", "sales", "mail",
                            "fax", "hotline", "inbox"]

    _STRATEGY_SIGNALS   = ["mission", "vision", "values", "goal", "objective",
                            "strategy", "purpose", "commitment", "promise",
                            "sustainability", "csr", "responsibility",
                            "roadmap", "plan"]

    _PRODUCT_SIGNALS    = ["product", "service", "offering", "solution",
                            "portfolio", "catalog", "range", "collection"]

    _PRESENCE_SIGNALS   = ["global", "international", "worldwide", "country",
                            "region", "branch", "partner",
                            "distributor", "reseller", "franchise", "locations"]

    _RESEARCH_SIGNALS   = ["research", "r&d", "innovation", "lab", "patent",
                            "technology", "development", "centre", "center"]

    _CERTIFICATION_SIGNALS = ["certification", "certified", "accredited", "award",
                               "recognition", "compliance", "iso", "standard"]

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        all_names = self._names(entries)
        titles    = [t.lower() for t in all_names]

        def _match(signals: List[str]) -> List[str]:
            return [n for n in all_names
                    if self._contains_any(n.lower(), signals)]

        identity_present     = _match(self._IDENTITY_SIGNALS)
        contact_present      = _match(self._CONTACT_SIGNALS)
        strategy_present     = _match(self._STRATEGY_SIGNALS)
        product_present      = _match(self._PRODUCT_SIGNALS)
        presence_present     = _match(self._PRESENCE_SIGNALS)
        research_present     = _match(self._RESEARCH_SIGNALS)
        certification_present = _match(self._CERTIFICATION_SIGNALS)

        flags = {
            "mission_present":          any(s in t for t in titles for s in ["mission"]),
            "vision_present":           any(s in t for t in titles for s in ["vision"]),
            "strategy_present":         bool(strategy_present),
            "global_presence_present":  bool(presence_present),
            "product_portfolio_present": bool(product_present),
            "research_present":         bool(research_present),
            "certification_present":    bool(certification_present),
            "contact_info_present":     bool(contact_present),
            "identity_info_present":    bool(identity_present),
        }

        present = [k.replace("_present", "").replace("_", " ")
                   for k, v in flags.items() if v]
        summary = (
            f"{len(entries)}-field company profile. "
            + ("Identity: " + ", ".join(identity_present[:4]) + ". " if identity_present else "")
            + ("Contact: " + ", ".join(contact_present[:3]) + ". " if contact_present else "")
            + ("Documented: " + ", ".join(present) + "." if present else "")
        )

        return {
            **meta,
            "total_fields":               len(entries),
            "identity_fields_present":    identity_present,
            "contact_fields_present":     contact_present,
            "strategy_fields_present":    strategy_present,
            "product_fields_present":     product_present,
            "presence_fields_present":    presence_present,
            "research_fields_present":    research_present,
            "certification_fields_present": certification_present,
            **flags,
            "all_field_names":            all_names,
            "intelligence_summary":       summary.strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 6 — POLICIES / LEGAL
# ══════════════════════════════════════════════════════════════════════════════

class PoliciesIntelligenceBuilder(_BaseBuilder):
    """
    Universal policy/legal intelligence builder.

    Works for any organisation — e-commerce return policies, HIPAA compliance,
    GDPR privacy notices, financial terms, employment policies, tenancy agreements, etc.

    Policy categories are universal coverage areas applicable to all industries.
    """

    _POLICY_GROUPS = {
        "customer_rights":  ["return", "refund", "cancellation", "exchange",
                              "chargeback", "complaint", "dispute", "money back",
                              "consumer rights"],
        "data_privacy":     ["privacy", "data protection", "gdpr", "ccpa", "cookie",
                              "data retention", "personal data", "consent",
                              "information security", "data processing"],
        "security":         ["security", "fraud", "anti-fraud", "cyber", "breach",
                              "incident response", "threat", "vulnerability",
                              "access control", "authentication"],
        "legal":            ["terms", "conditions", "agreement", "disclaimer",
                              "liability", "intellectual property", "copyright",
                              "trademark", "patent", "governing law",
                              "jurisdiction", "indemnity", "force majeure",
                              "acceptable use", "export"],
        "compliance":       ["compliance", "regulatory", "equal opportunity",
                              "anti-discrimination", "diversity", "inclusion",
                              "environmental", "esg", "ethics", "code of conduct",
                              "supplier", "vendor", "anti-bribery", "aml",
                              "kyc", "sanctions"],
        # Named "product_warranty" (not "warranty" alone) to avoid key collision
        # with generic "warranty" tokens that exist in multiple other categories.
        # Coverage flag will be emitted as "product_warranty_coverage".
        "product_warranty": ["warranty", "guarantee", "maintenance", "service level",
                              "sla", "uptime", "support policy", "after-sales",
                              "product liability"],
        "hr_employment":    ["employment", "hr", "human resources", "leave",
                              "absence", "remote work", "dress code", "conduct",
                              "performance", "disciplinary", "grievance",
                              "recruitment", "onboarding"],
        "financial":        ["payment", "billing", "invoice", "subscription",
                              "pricing", "fee", "tax", "vat", "gst", "refund policy",
                              "auto-renewal", "credit"],
        "accessibility":    ["accessibility", "ada", "wcag", "disability",
                              "inclusion", "special needs"],
        "health_safety":    ["health", "safety", "workplace", "hazard", "risk",
                              "emergency", "fire", "first aid", "ppe",
                              "occupational health"],
    }

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        policy_categories: Dict[str, List[str]] = {k: [] for k in self._POLICY_GROUPS}
        status_counts:     Dict[str, int]        = {}
        all_names = self._names(entries)

        for entry in entries:
            title  = self._title(entry)
            tl     = title.lower()
            status = self._normalize_status(self._status(entry) or "active")
            status_counts[status] = status_counts.get(status, 0) + 1

            for group, tokens in self._POLICY_GROUPS.items():
                if self._contains_any(tl, tokens):
                    if title not in policy_categories[group]:
                        policy_categories[group].append(title)

        total        = len(entries)
        active_count = status_counts.get("active", total)

        # Build coverage flags from whichever groups are populated
        coverage_flags = {
            f"{group}_coverage": bool(items)
            for group, items in policy_categories.items()
        }

        covered = [g for g, items in policy_categories.items() if items]
        summary = (
            f"{total} policies, {active_count} active. "
            + ("Coverage: " + ", ".join(covered) + "." if covered else "")
        )

        return {
            **meta,
            "total_policies":    total,
            "active_policies":   active_count,
            "all_active":        active_count == total,
            "status_breakdown":  status_counts,
            "policy_categories": {k: v for k, v in policy_categories.items() if v},
            **coverage_flags,
            "all_policy_names":      all_names,
            "intelligence_summary":  summary.strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 7 — EDUCATIONAL CONTENT
# ══════════════════════════════════════════════════════════════════════════════

class EducationIntelligenceBuilder(_BaseBuilder):
    """
    Universal educational content intelligence builder.

    Works for: software tutorials, medical CME, legal CPD, financial literacy,
    corporate training, language learning, cooking courses, fitness guides, etc.

    Intelligence derived from:
      - skill_level attribute field value (highest priority)
      - Universal skill-level signals in title text
      - Universal content-type signals in title text
      - Topic map built from actual content — no domain assumptions
    """

    # Universal skill-level signals
    _SKILL_SIGNALS = {
        "beginner":     ["beginner", "basics", "basic", "introduction", "intro",
                          "getting started", "101", "fundamentals", "first steps",
                          "for beginners", "starter", "new to", "overview"],
        "intermediate": ["intermediate", "practical", "applied", "workflow",
                          "best practices", "tips", "how to", "step by step",
                          "hands-on", "use cases"],
        "advanced":     ["advanced", "expert", "deep dive", "masterclass", "mastery",
                          "in-depth", "architecture", "enterprise", "optimization",
                          "performance", "diagnostics", "certification", "professional"],
    }

    # Universal content-type signals
    _CONTENT_TYPE_SIGNALS = {
        "tutorial":        ["tutorial", "how to", "step by step", "guide", "setup",
                              "installation", "configuration", "walkthrough"],
        "troubleshooting": ["troubleshooting", "troubleshoot", "fix", "error",
                              "problem", "issue", "diagnose", "debug", "resolve"],
        "overview":        ["overview", "introduction", "what is", "basics",
                              "fundamentals", "concepts", "101"],
        "training":        ["training", "course", "workshop", "program", "class",
                              "masterclass", "certification", "bootcamp"],
        "reference":       ["reference", "documentation", "glossary", "handbook",
                              "manual", "cheatsheet", "cheat sheet", "quick reference"],
        "case_study":      ["case study", "example", "use case", "success story",
                              "implementation", "project"],
        "webinar":         ["webinar", "video", "recording", "session", "demo",
                              "presentation", "talk"],
        "faq":             ["faq", "frequently asked", "q&a", "questions", "answers"],
    }

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        skill_counts:  Dict[str, int]          = {}
        type_counts:   Dict[str, int]          = {}
        status_counts: Dict[str, int]          = {}
        all_names = self._names(entries)

        # Build topic map dynamically from actual entry titles — no domain assumptions
        # Topics are derived by grouping titles that share common meaningful words
        topic_map: Dict[str, List[str]] = {}

        for entry in entries:
            title  = self._title(entry)
            tl     = title.lower()
            status = self._normalize_status(self._status(entry) or "active")
            status_counts[status] = status_counts.get(status, 0) + 1

            # Skill level — check attribute first, then title signals
            skill_attr = str(self._attr(entry, "skill_level") or
                             self._attr(entry, "level") or
                             self._attr(entry, "difficulty") or "").lower()
            full_text  = tl + " " + skill_attr

            matched_skill = False
            for level, tokens in self._SKILL_SIGNALS.items():
                if self._contains_any(full_text, tokens):
                    skill_counts[level] = skill_counts.get(level, 0) + 1
                    matched_skill = True
                    break
            if not matched_skill:
                skill_counts["intermediate"] = skill_counts.get("intermediate", 0) + 1

            # Content type
            matched_type = False
            for ctype, tokens in self._CONTENT_TYPE_SIGNALS.items():
                if self._contains_any(tl, tokens):
                    type_counts[ctype] = type_counts.get(ctype, 0) + 1
                    matched_type = True
                    break
            if not matched_type:
                type_counts["tutorial"] = type_counts.get("tutorial", 0) + 1

            # Topic map: use resource_type or topic attribute if present
            topic_attr = str(self._attr(entry, "topic") or
                             self._attr(entry, "resource_type") or
                             self._attr(entry, "subject") or
                             self._attr(entry, "category") or "").strip()
            if topic_attr:
                topic_map.setdefault(topic_attr, [])
                if title not in topic_map[topic_attr]:
                    topic_map[topic_attr].append(title)

        total     = len(entries)
        skill_str = ", ".join(f"{k}({v})" for k, v in skill_counts.items() if v)
        type_str  = ", ".join(type_counts.keys())
        summary_parts = [f"{total} educational articles."]
        if skill_str:
            summary_parts.append(f"Skill levels: {skill_str}.")
        if type_str:
            summary_parts.append(f"Content types: {type_str}.")
        if topic_map:
            summary_parts.append("Topics: " + ", ".join(list(topic_map.keys())[:6]) + ".")
        summary = " ".join(summary_parts)

        return {
            **meta,
            "total_articles":         total,
            "all_active":             status_counts.get("active", total) == total,
            "status_breakdown":       status_counts,
            "skill_level_breakdown":  skill_counts,
            "content_type_breakdown": type_counts,
            "topic_coverage":         topic_map,
            "all_article_names":      all_names,
            "intelligence_summary":   summary.strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER 8 — ISSUE RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

class IssueResolutionIntelligenceBuilder(_BaseBuilder):
    """
    Universal issue resolution intelligence builder.

    Works for: software bugs, medical complaints, customer service tickets,
    HR grievances, financial disputes, product defects, service outages, etc.

    Issue categories use universal signals applicable across all industries.
    Severity and resolution status read from actual field values.
    """

    # Universal issue category signals
    _ISSUE_CATEGORIES = {
        "technical":    ["technical", "error", "bug", "crash", "fail", "broken",
                          "not working", "issue", "malfunction", "outage",
                          "downtime", "connectivity"],
        "account":      ["account", "login", "password", "access", "locked",
                          "authentication", "permission", "sign in", "profile",
                          "registration", "verification"],
        "payment":      ["payment", "billing", "charge", "invoice", "refund",
                          "transaction", "subscription", "fee", "overcharged",
                          "deducted", "credit", "debit"],
        "delivery":     ["delivery", "shipping", "order", "dispatch", "tracking",
                          "lost", "damaged", "missing", "not received",
                          "wrong item", "return"],
        "product":      ["product", "item", "defect", "quality", "damaged",
                          "broken", "faulty", "not as described", "wrong"],
        "service":      ["service", "support", "response", "slow", "unhelpful",
                          "no response", "escalation", "wait time", "experience"],
        "data":         ["data", "information", "record", "export", "import",
                          "sync", "backup", "loss", "corrupt", "privacy"],
        "compliance":   ["compliance", "legal", "regulation", "policy violation",
                          "gdpr", "privacy breach", "audit"],
        "general":      [],
    }

    # Universal severity signals
    _SEVERITY_SIGNALS = {
        "critical": ["critical", "urgent", "emergency", "blocker", "p0", "p1",
                      "showstopper", "production down", "all users affected"],
        "high":     ["high", "major", "significant", "important", "p2",
                      "many users", "widespread"],
        "medium":   ["medium", "moderate", "p3", "some users", "workaround available"],
        "low":      ["low", "minor", "cosmetic", "p4", "enhancement",
                      "nice to have", "trivial"],
    }

    # Universal resolution status signals
    _RESOLVED_STATUSES = {"resolved", "closed", "fixed", "done", "completed",
                           "solved", "remediated", "addressed", "confirmed fixed",
                           "deployed", "released"}

    def build(self, entries, source_id, source_name, category):
        meta = self._base_meta(entries, source_id, source_name, category)

        if not entries:
            return {
                **meta,
                "total_issues":             0,
                "issue_category_breakdown": {},
                "severity_breakdown":       {},
                "resolution_rate":          0,
                "all_issue_names":          [],
                "intelligence_summary":     "No issue resolution records ingested yet.",
            }

        cat_counts: Dict[str, int] = {}
        sev_counts: Dict[str, int] = {}
        resolved = 0
        all_names = self._names(entries)

        for entry in entries:
            title  = self._title(entry)
            tl     = title.lower()
            attrs  = entry.get("attributes") or {}
            sd     = entry.get("structured_data") or {}

            # Full text for classification: title + description
            desc = str(attrs.get("description") or sd.get("description") or
                       sd.get("issue_description") or "").lower()
            full = tl + " " + desc

            # Issue category
            matched = False
            for icat, tokens in self._ISSUE_CATEGORIES.items():
                if tokens and self._contains_any(full, tokens):
                    cat_counts[icat] = cat_counts.get(icat, 0) + 1
                    matched = True
                    break
            if not matched:
                cat_counts["general"] = cat_counts.get("general", 0) + 1

            # Severity — read from field first, then detect from text
            sev_raw = str(attrs.get("severity") or sd.get("severity") or
                          sd.get("priority") or sd.get("impact") or "").lower()
            sev_matched = False
            for sev_level, tokens in self._SEVERITY_SIGNALS.items():
                if self._contains_any(sev_raw + " " + full, tokens):
                    sev_counts[sev_level] = sev_counts.get(sev_level, 0) + 1
                    sev_matched = True
                    break
            if not sev_matched and sev_raw:
                sev_counts[sev_raw] = sev_counts.get(sev_raw, 0) + 1

            # Resolution status
            status_raw = str(attrs.get("status") or sd.get("status") or
                             sd.get("resolution_status") or "").lower().strip()
            if status_raw in self._RESOLVED_STATUSES:
                resolved += 1

        total           = len(entries)
        resolution_rate = round(resolved / total * 100, 1) if total else 0

        summary = (
            f"{total} issues logged. "
            + ("Categories: " + ", ".join(f"{k}({v})" for k, v in cat_counts.items()) + ". "
               if cat_counts else "")
            + ("Severity: " + ", ".join(f"{k}({v})" for k, v in sev_counts.items()) + ". "
               if sev_counts else "")
            + f"Resolution rate: {resolution_rate}%."
        )

        return {
            **meta,
            "total_issues":             total,
            "issue_category_breakdown": cat_counts,
            "severity_breakdown":       sev_counts,
            "resolved_count":           resolved,
            "resolution_rate":          resolution_rate,
            "all_issue_names":          all_names,
            "intelligence_summary":     summary.strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

_BUILDERS: Dict[str, _BaseBuilder] = {
    "product_service":     ProductIntelligenceBuilder(),
    "offers_promotions":   OffersIntelligenceBuilder(),
    "contact_support":     ContactIntelligenceBuilder(),
    "delivery_shipping":   ShippingIntelligenceBuilder(),
    "company_info":        CompanyIntelligenceBuilder(),
    "policies_legal":      PoliciesIntelligenceBuilder(),
    "educational_content": EducationIntelligenceBuilder(),
    "issue_resolution":    IssueResolutionIntelligenceBuilder(),
}


def _get_builder(category: str) -> _BaseBuilder:
    return _BUILDERS.get(category, _BaseBuilder())


def _dominant_category(entries: List[Dict[str, Any]]) -> str:
    counts: Dict[str, int] = {}
    for e in entries:
        cat = str(e.get("category") or "").strip()
        if cat and cat != "data_analytics":
            counts[cat] = counts.get(cat, 0) + 1
    return max(counts, key=counts.get) if counts else ""


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH TEXT — category-aware, domain-agnostic
# ══════════════════════════════════════════════════════════════════════════════

def _build_search_text(intelligence: Dict[str, Any], source_name: str, category: str) -> str:
    summary = intelligence.get("intelligence_summary", "")
    parts   = [f"{source_name} analytics. {summary}"]

    if category == "product_service":
        pd = intelligence.get("price_distribution") or {}
        if pd:
            parts.append(
                f"Budget: {pd.get('budget', 0)}, "
                f"mid-range: {pd.get('mid_range', 0)}, "
                f"premium: {pd.get('premium', 0)}."
            )
        cheapest = intelligence.get("cheapest_product")
        priciest = intelligence.get("most_expensive_product")
        if cheapest:
            parts.append(f"Cheapest: {cheapest['name']} at {cheapest['price']:,.2f}.")
        if priciest:
            parts.append(f"Most expensive: {priciest['name']} at {priciest['price']:,.2f}.")
        cat_dist = intelligence.get("category_distribution") or {}
        if cat_dist:
            parts.append("Categories: " + ", ".join(f"{k}({v})" for k, v in list(cat_dist.items())[:6]) + ".")

    elif category == "offers_promotions":
        parts.append(
            f"Active: {intelligence.get('active_offers', 0)}, "
            f"scheduled: {intelligence.get('scheduled_offers', 0)}, "
            f"expired: {intelligence.get('expired_offers', 0)}."
        )
        lp = intelligence.get("largest_percentage_discount")
        if lp:
            parts.append(f"Largest % discount: {lp['value']} — {lp['name']}.")
        aud = intelligence.get("audience_segments") or {}
        if aud:
            parts.append("Segments: " + ", ".join(f"{k}({v})" for k, v in list(aud.items())[:5]) + ".")

    elif category == "contact_support":
        channels = intelligence.get("support_channels") or {}
        active_ch = [k for k, v in channels.items() if v and k != "regional_contacts"]
        if active_ch:
            parts.append("Channels: " + ", ".join(active_ch) + ".")
        dept = intelligence.get("department_breakdown") or {}
        if dept:
            parts.append("Departments: " + ", ".join(list(dept.keys())[:6]) + ".")

    elif category == "delivery_shipping":
        speed = intelligence.get("speed_breakdown") or {}
        if speed:
            parts.append("Speed options: " + ", ".join(speed.keys()) + ".")
        flags = {k: v for k, v in intelligence.items()
                 if k.endswith("_available") and v is True}
        if flags:
            parts.append("Available: " +
                         ", ".join(k.replace("_available", "").replace("_", " ")
                                   for k in flags) + ".")

    elif category == "company_info":
        present = [k.replace("_present", "").replace("_", " ")
                   for k, v in intelligence.items()
                   if k.endswith("_present") and v is True]
        if present:
            parts.append("Documented: " + ", ".join(present) + ".")

    elif category == "policies_legal":
        covered = [k.replace("_coverage", "")
                   for k, v in intelligence.items()
                   if k.endswith("_coverage") and v is True]
        if covered:
            parts.append("Coverage: " + ", ".join(covered) + ".")

    elif category == "educational_content":
        # Skill and topic details are already in intelligence_summary —
        # only add topic map keys here to avoid repeating skill counts twice.
        topics = intelligence.get("topic_coverage") or {}
        if topics:
            parts.append("Topics: " + ", ".join(list(topics.keys())[:8]) + ".")

    elif category == "issue_resolution":
        cats = intelligence.get("issue_category_breakdown") or {}
        if cats:
            parts.append("Issue types: " + ", ".join(f"{k}({v})" for k, v in cats.items()) + ".")
        parts.append(f"Resolution rate: {intelligence.get('resolution_rate', 0)}%.")

    # All item names for keyword-level retrieval
    name_key = next(
        (k for k in ("all_item_names", "all_offer_names", "all_contact_names",
                     "all_shipping_names", "all_field_names", "all_policy_names",
                     "all_article_names", "all_issue_names")
         if k in intelligence),
        None,
    )
    if name_key:
        names = intelligence.get(name_key) or []
        if names:
            parts.append("Items include: " + ", ".join(names[:20]) + ".")

    parts.append(
        "analytics insights statistics summary business intelligence "
        "count total distribution breakdown"
    )
    return " ".join(parts)[:2000]


# ══════════════════════════════════════════════════════════════════════════════
# AI TAGS — category-aware
# ══════════════════════════════════════════════════════════════════════════════

_CATEGORY_AI_TAGS: Dict[str, List[str]] = {
    "product_service":     ["product_intelligence", "price_analysis", "catalog_summary",
                             "product_recommendation", "category_distribution", "price_tiers"],
    "offers_promotions":   ["offer_intelligence", "discount_analysis", "promotion_summary",
                             "audience_segmentation", "deal_discovery"],
    "contact_support":     ["support_intelligence", "department_routing", "channel_availability",
                             "contact_discovery", "escalation_routing"],
    "delivery_shipping":   ["shipping_intelligence", "delivery_options", "logistics_summary",
                             "express_availability", "service_flags"],
    "company_info":        ["company_intelligence", "brand_overview", "identity_summary",
                             "mission_vision", "presence_indicators"],
    "policies_legal":      ["policy_intelligence", "compliance_coverage", "rights_coverage",
                             "legal_coverage", "coverage_flags"],
    "educational_content": ["education_intelligence", "content_discovery", "skill_routing",
                             "topic_coverage", "training_summary"],
    "issue_resolution":    ["issue_intelligence", "problem_categorization", "severity_analysis",
                             "resolution_tracking"],
}


def _build_ai_tags(category: str, intelligence: Dict[str, Any]) -> List[str]:
    # base tags: "business_intelligence" and "data_analytics" mark these as
    # analytics/navigation entries. The actual source category (e.g. "delivery_shipping")
    # is stored in the category field for retrieval routing.
    base     = ["business_intelligence", "data_analytics", "source_insights"]
    specific = _CATEGORY_AI_TAGS.get(category, ["general_analytics"])
    return base + specific


# ══════════════════════════════════════════════════════════════════════════════
# KEYWORDS — category-aware, domain-agnostic
# ══════════════════════════════════════════════════════════════════════════════

def _build_keywords(
    intelligence: Dict[str, Any],
    source_name: str,
    category: str,
) -> List[str]:
    kws = ["analytics", "insights", "statistics", "summary", "intelligence",
           "total", "count", "distribution", "breakdown", source_name.lower()]

    if category == "product_service":
        kws += ["price", "budget", "mid-range", "premium", "cheapest",
                "most expensive", "category", "status", "available", "items"]
        cheapest = intelligence.get("cheapest_product")
        priciest = intelligence.get("most_expensive_product")
        if cheapest and isinstance(cheapest, dict):
            kws.append(cheapest.get("name", "").lower())
        if priciest and isinstance(priciest, dict):
            kws.append(priciest.get("name", "").lower())
        # Add actual category values found in the data
        for cat_name in list((intelligence.get("category_distribution") or {}).keys())[:8]:
            kws.append(cat_name.lower())

    elif category == "offers_promotions":
        kws += ["offer", "discount", "deal", "promo", "promotion", "active",
                "scheduled", "expired", "free", "percent", "fixed", "audience"]
        lp = intelligence.get("largest_percentage_discount")
        if lp:
            kws.append(lp.get("name", "").lower())
        # Add actual audience segments found in the data
        for seg in list((intelligence.get("audience_segments") or {}).keys())[:6]:
            kws.append(seg.lower())

    elif category == "contact_support":
        kws += ["support", "contact", "department", "channel", "email", "phone",
                "chat", "helpdesk", "team", "escalation", "region"]
        for dept in list((intelligence.get("department_breakdown") or {}).keys())[:8]:
            kws.append(dept.lower())

    elif category == "delivery_shipping":
        kws += ["shipping", "delivery", "express", "same day", "international",
                "free shipping", "eco", "tracked", "insured", "logistics"]
        for speed in list((intelligence.get("speed_breakdown") or {}).keys()):
            kws.append(speed.replace("_", " "))

    elif category == "company_info":
        kws += ["company", "about", "mission", "vision", "contact",
                "identity", "profile", "headquarters", "industry", "global"]

    elif category == "policies_legal":
        kws += ["policy", "terms", "legal", "compliance", "privacy",
                "warranty", "refund", "security", "rights", "coverage"]
        # Add actual covered policy group names
        for group in list((intelligence.get("policy_categories") or {}).keys()):
            kws.append(group.replace("_", " "))

    elif category == "educational_content":
        kws += ["tutorial", "guide", "training", "beginner", "intermediate",
                "advanced", "course", "content", "topic", "skill", "learning"]
        for level in list((intelligence.get("skill_level_breakdown") or {}).keys()):
            kws.append(level)
        for topic in list((intelligence.get("topic_coverage") or {}).keys())[:8]:
            kws.append(topic.replace("_", " "))

    elif category == "issue_resolution":
        kws += ["issue", "problem", "resolution", "severity", "critical",
                "fix", "troubleshoot", "ticket", "resolved", "open"]
        for icat in list((intelligence.get("issue_category_breakdown") or {}).keys()):
            kws.append(icat.replace("_", " "))

    # Always add first 15 item names for direct name-based retrieval
    name_key = next(
        (k for k in ("all_item_names", "all_offer_names", "all_contact_names",
                     "all_shipping_names", "all_field_names", "all_policy_names",
                     "all_article_names", "all_issue_names")
         if k in intelligence),
        None,
    )
    if name_key:
        for name in (intelligence.get(name_key) or [])[:15]:
            kws.append(name.lower())

    return list(dict.fromkeys(kws))[:60]


# ══════════════════════════════════════════════════════════════════════════════
# QDRANT UPSERT
# ══════════════════════════════════════════════════════════════════════════════

def upsert_analytics_to_qdrant(
    analytics_payload: Dict[str, Any],
    user_id: str,
    source_id: str,
) -> Optional[str]:
    """
    Upsert the analytics object to Qdrant.
    Deterministic point ID (user_id + source_id) — always updates in-place.
    """
    if not analytics_payload:
        return None

    try:
        from services.ingestion.embedding_service import embed_texts, COLLECTION_NAME
        from shared.vector_db import get_qdrant_client
        from qdrant_client.models import PointStruct  # type: ignore[import-untyped]

        client      = get_qdrant_client()
        point_id    = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"analytics:{user_id}:{source_id}"))
        search_text = analytics_payload.get("search_text", "")
        vector      = embed_texts([search_text])[0].tolist()

        structured_data = analytics_payload.get("structured_data", {})

        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "user_id":         user_id,
                "entry_id":        point_id,
                "source_id":       source_id,
                "category":        analytics_payload.get("category", ""),
                "subtype":         _ANALYTICS_SUBTYPE,
                "title":           analytics_payload.get("title", ""),
                "search_text":     search_text[:500],
                "ai_tags":         analytics_payload.get("ai_tags", []),
                "keywords":        analytics_payload.get("keywords", []),
                "attributes":      analytics_payload.get("attributes", {}),
                "structured_data": structured_data,
                "status":          "active",
                "priority_score":  5,
                "quality_score":   95.0,
                "source_type":     "analytics",
                "updated_at":      datetime.utcnow().isoformat(),
            },
        )

        client.upsert(collection_name=COLLECTION_NAME, points=[point])
        logger.info(
            "Analytics upserted | user=%s source=%s category=%s point=%s",
            user_id[:8],
            source_id[:8],
            structured_data.get("primary_category", "?"),
            point_id[:12],
        )
        return point_id

    except Exception as e:
        logger.error("Analytics upsert failed: %s", e, exc_info=True)
        return None
