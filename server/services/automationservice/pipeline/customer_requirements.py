"""
automationservice — Customer Requirements Engine (Phase 4)
===========================================================
Creates a structured representation of customer requirements, strictly separating:
  - Hard Requirements: Non-negotiable constraints (e.g., budget <= $1200, 16GB RAM).
  - Soft Preferences: Desirable features (e.g., preferred brand, color).
  - Communication Requirements: Tone, formatting, pricing disclosures.

Guarantees:
  - Does NOT collapse requirements into one free-form string.
  - Extracts parameters deterministically from Processor #1 output & message text.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pipeline.contracts import (
    CustomerRequirements,
    HardRequirement,
    SoftPreference,
    CommunicationRequirements,
)

logger = logging.getLogger("automationservice.pipeline.customer_requirements")


def _extract_budget(text: str) -> float | None:
    """Extract budget ceiling from text (e.g. 'under $1200', 'budget of 1000', '< $1500')."""
    patterns = [
        r"(?:under|below|max|maximum|budget|less than|up to)\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\b",
        r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:budget|or less|max)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                clean_num = m.group(1).replace(",", "")
                val = float(clean_num)
                if val > 0:
                    return val
            except ValueError:
                continue
    return None


def extract_customer_requirements(
    p1_output: dict[str, Any] | None,
    latest_message: dict[str, Any] | None,
    business_context: dict[str, Any] | None = None,
) -> CustomerRequirements:
    """
    Extract structured requirements from conversation intelligence.

    Args:
        p1_output: Complete output of Processor #1.
        latest_message: The triggering inbound message.
        business_context: Business profile for tone alignment.

    Returns:
        Structured CustomerRequirements instance.
    """
    p1 = p1_output or {}
    msg_body = ""
    if latest_message and isinstance(latest_message, dict):
        msg_body = str(latest_message.get("content") or latest_message.get("snippet") or "").strip()

    hard_reqs: list[HardRequirement] = []
    soft_prefs: list[SoftPreference] = []

    rc_contract = p1.get("retrieval_contract") or {}
    ee = p1.get("entity_extraction") or {}
    ca = p1.get("conversation_analysis") or {}
    ia = p1.get("intent_analysis") or {}

    # ── 1. Hard Requirements from Processor #1 Retrieval Contract ─────────────
    # Numeric constraints (e.g. price <= 1200)
    num_constraints = rc_contract.get("numeric_constraints") or []
    budget_handled = False
    for nc in num_constraints:
        if isinstance(nc, dict):
            field = str(nc.get("field", "")).strip().lower()
            op = str(nc.get("operator", "<=")).strip()
            val = nc.get("value")
            if val is not None and field in ("price", "budget", "cost"):
                budget_handled = True
                hard_reqs.append(
                    HardRequirement(
                        field="budget",
                        operator=op,
                        value=float(val) if isinstance(val, (int, float, str)) and str(val).replace(".", "", 1).isdigit() else val,
                        raw_text=f"{field} {op} {val}",
                    )
                )
            elif val is not None and field:
                hard_reqs.append(
                    HardRequirement(
                        field=field,
                        operator=op,
                        value=val,
                        raw_text=f"{field} {op} {val}",
                    )
                )

    # Fallback budget extraction directly from message if not extracted by P1
    if not budget_handled and msg_body:
        found_budget = _extract_budget(msg_body)
        if found_budget is not None:
            hard_reqs.append(
                HardRequirement(
                    field="budget",
                    operator="<=",
                    value=found_budget,
                    raw_text=f"budget <= {found_budget}",
                )
            )

    # Structured requirements (e.g. RAM, GPU, storage)
    contract_reqs = rc_contract.get("requirements") or []
    for cr in contract_reqs:
        if isinstance(cr, dict):
            field = str(cr.get("field") or cr.get("type") or "").strip()
            val = cr.get("value") or cr.get("raw_value")
            op = str(cr.get("operator") or "==")
            raw = str(cr.get("raw_spec") or "")
            if field and val:
                # Avoid duplicate budget
                if field.lower() in ("price", "budget") and any(h.field == "budget" for h in hard_reqs):
                    continue
                hard_reqs.append(
                    HardRequirement(
                        field=field.lower(),
                        operator=op,
                        value=val,
                        raw_text=raw or f"{field}: {val}",
                    )
                )

    # Specifications from entity extraction if not already covered
    specs = ee.get("specifications") or []
    for spec in specs:
        s_clean = str(spec).strip()
        if s_clean and not any(s_clean.lower() in h.raw_text.lower() for h in hard_reqs):
            hard_reqs.append(
                HardRequirement(
                    field="specification",
                    operator="contains",
                    value=s_clean,
                    raw_text=s_clean,
                )
            )

    # Specific product model inquiries (e.g. looking for a specific item)
    products = ee.get("products") or []
    for prod in products:
        p_clean = str(prod).strip()
        if p_clean:
            hard_reqs.append(
                HardRequirement(
                    field="product_target",
                    operator="==",
                    value=p_clean,
                    raw_text=p_clean,
                )
            )

    # ── 2. Soft Preferences (Brand, Color, Windows, Optional Features) ────────
    lower_body = msg_body.lower()
    # Brand preferences
    pref_match = re.search(r"(?:prefer|preferably|would like|leaning towards)\s+([a-zA-Z0-9\s]+?)(?:,|\.|\band\b|$)", lower_body)
    if pref_match:
        pref_text = pref_match.group(1).strip()
        if len(pref_text) < 40:
            soft_prefs.append(
                SoftPreference(
                    field="preference",
                    value=pref_text,
                    raw_text=pref_text,
                    weight=0.7,
                )
            )

    # ── 3. Communication Requirements ─────────────────────────────────────────
    biz_tone = (business_context or {}).get("communication_tone") or "professional"
    sentiment = ca.get("customer_sentiment") or "neutral"

    # Adapt communication tone if customer is frustrated or urgent
    comm_tone = biz_tone
    if sentiment in ("frustrated", "negative"):
        comm_tone = f"{biz_tone} and empathetic"
    elif sentiment == "urgent":
        comm_tone = f"{biz_tone} and direct"

    include_pricing = True
    # If customer specifically asks not to discuss pricing or it's purely technical troubleshooting
    if "without price" in lower_body or "no pricing" in lower_body:
        include_pricing = False

    comm_reqs = CommunicationRequirements(
        tone=comm_tone,
        language="English",
        length="concise" if "short" in lower_body or "quick" in lower_body else "standard",
        include_pricing=include_pricing,
        include_alternatives=True,
    )

    logger.debug(
        "[customer_requirements] hard=%d soft=%d tone=%s",
        len(hard_reqs), len(soft_prefs), comm_tone,
    )

    return CustomerRequirements(
        hard=hard_reqs,
        soft=soft_prefs,
        communication=comm_reqs,
    )
