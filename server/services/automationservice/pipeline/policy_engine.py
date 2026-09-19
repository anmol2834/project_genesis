"""
automationservice — Response Policy Engine (Phase 13)
====================================================
The authoritative operational decision-maker of the pipeline.
Runs strictly AFTER Grounding Validation to enforce business rules
independently of the LLM.

The LLM must NEVER be the final authority for:
  - maximum discount
  - allowed pricing disclosure
  - restricted product information
  - legal disclaimers
  - customer segmentation
  - communication restrictions
  - refund language
  - availability restrictions
  - promotional restrictions
  - internal-only information

Architecture:
  LLM
   ↓
  Grounding Validator
   ↓
  Policy Engine
   ↓
  Approved Response
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pipeline.contracts import (
    LLMCall2Output,
    ResponseStrategy,
    GroundingReport,
    PolicyReport,
)

logger = logging.getLogger("automationservice.pipeline.policy_engine")

AUTO_SEND_MIN_CONFIDENCE = 0.70

# ── Pattern Matchers for Policy Enforcement ───────────────────────────────────

_DISCOUNT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:off|discount)|(?:discount\s*of\s*(\d+(?:\.\d+)?)\s*%)|offer\s+you\s+(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

_PROMO_CODE_PATTERN = re.compile(
    r"\b(?:use\s+code|promo\s+code|coupon\s+code|discount\s+code)\s+['\"]?([A-Z0-9_-]+)['\"]?",
    re.IGNORECASE,
)

_RESTRICTED_INTERNAL_TERMS = [
    "margin",
    "profit margin",
    "wholesale cost",
    "cost basis",
    "internal sku",
    "confidential",
    "do not disclose",
    "internal only",
    "internal note",
    "markup",
]

_UNAUTHORIZED_REFUND_PROMISES = [
    "lifetime refund",
    "instant cash refund",
    "no questions asked cash refund",
    "unconditional full refund anytime",
    "instant refund at any time",
]

_UNAUTHORIZED_SHIPPING_GUARANTEES = [
    "guaranteed same-day delivery",
    "guaranteed delivery tomorrow",
    "guaranteed overnight delivery",
    "100% guaranteed delivery time",
]


def _extract_highest_offered_discount(text: str) -> float:
    """Extract highest percentage discount mentioned in text."""
    max_disc = 0.0
    for m in _DISCOUNT_PATTERN.finditer(text):
        for g in m.groups():
            if g:
                try:
                    val = float(g)
                    if val > max_disc:
                        max_disc = val
                except ValueError:
                    continue
    return max_disc


def evaluate_response_policy(
    llm_output: LLMCall2Output,
    strategy: ResponseStrategy,
    grounding_report: GroundingReport,
    business_context: dict[str, Any] | None = None,
    upstream_confidence: float = 0.85,
) -> PolicyReport:
    """
    Evaluate business policies, confidence thresholds, and operational dispatch rules.

    Args:
        llm_output: Validated Call #2 output.
        strategy: Authoritative ResponseStrategy.
        grounding_report: Output of Grounding Validator.
        business_context: Business profile from PostgreSQL.
        upstream_confidence: Combined confidence from P1 / retrieval.

    Returns:
        PolicyReport containing operational action, send_email boolean, and added disclaimers.
    """
    biz_ctx = business_context or {}
    policy_violations: list[str] = []
    disclaimers_added: list[str] = []

    # ── 1. Calculate Composite Confidence ─────────────────────────────────────
    composite_confidence = round(
        (grounding_report.grounding_score * 0.5) + (upstream_confidence * 0.5),
        2
    )

    # ── 2. Strategy-Level Policy Gates ─────────────────────────────────────────
    if strategy.mode == "escalate":
        logger.info("[policy_engine] strategy mode is escalate — routing to escalation")
        return PolicyReport(
            approved_for_sending=False,
            action="escalate",
            send_email=False,
            escalation_requested=True,
            escalation_reason=strategy.objective,
            confidence_score=composite_confidence,
            policy_violations=["Escalation mandated by strategy engine."],
        )

    # ── 3. Grounding Safety Gates ─────────────────────────────────────────────
    if not grounding_report.is_grounded or grounding_report.grounding_score < 0.70:
        logger.warning(
            "[policy_engine] REJECTED auto-send: grounding failure (score=%.2f, violations=%s)",
            grounding_report.grounding_score, grounding_report.violations,
        )
        return PolicyReport(
            approved_for_sending=False,
            action="draft",
            send_email=False,
            escalation_requested=True,
            escalation_reason=f"Grounding failure: {'; '.join(grounding_report.violations[:2])}",
            confidence_score=composite_confidence,
            policy_violations=grounding_report.violations,
        )

    # ── 4. Conflict Gates ─────────────────────────────────────────────────────
    if grounding_report.prohibited_claims_detected:
        logger.warning(
            "[policy_engine] REJECTED auto-send: prohibited conflict facts cited (%s)",
            grounding_report.prohibited_claims_detected,
        )
        return PolicyReport(
            approved_for_sending=False,
            action="escalate",
            send_email=False,
            escalation_requested=True,
            escalation_reason=f"Unresolved knowledge conflict cited: {grounding_report.prohibited_claims_detected}",
            confidence_score=composite_confidence,
            policy_violations=["Prohibited conflicting knowledge items were cited."],
        )

    # ── 5. Independent Business Policy Verification ───────────────────────────
    email_text = (llm_output.email_body or llm_output.body or "").lower()

    # Policy 1: Maximum Discount Rule
    # Check max discount allowed in business rules (default: 0% if discounts disabled, else 10%)
    discounts_allowed = (
        biz_ctx.get("allow_discounts", True)
        and not biz_ctx.get("discount_not_allowed", False)
    )
    max_allowed_discount = float(biz_ctx.get("max_discount_percentage", 10.0 if discounts_allowed else 0.0))
    if not discounts_allowed:
        max_allowed_discount = 0.0

    offered_discount = _extract_highest_offered_discount(llm_output.email_body or llm_output.body or "")
    if offered_discount > max_allowed_discount:
        msg = f"Offered discount of {offered_discount:g}% exceeds maximum allowed limit of {max_allowed_discount:g}%."
        policy_violations.append(msg)
        logger.warning("[policy_engine] POLICY VIOLATION: %s", msg)

    # Policy 2: Allowed Pricing Disclosure
    pricing_disclosure_allowed = biz_ctx.get("allow_pricing_disclosure", True) and strategy.allow_pricing
    if not pricing_disclosure_allowed and any(c in email_text for c in ("$", "₹", "€", "£")):
        msg = "Pricing disclosure is restricted by business policy but price amounts were stated."
        policy_violations.append(msg)
        logger.warning("[policy_engine] POLICY VIOLATION: %s", msg)

    # Policy 3: Restricted Internal Information
    for restricted_term in _RESTRICTED_INTERNAL_TERMS:
        if restricted_term in email_text:
            msg = f"Restricted internal business information detected: '{restricted_term}'."
            policy_violations.append(msg)
            logger.warning("[policy_engine] POLICY VIOLATION: %s", msg)

    # Policy 4: Promotional Code Restrictions
    if _PROMO_CODE_PATTERN.search(llm_output.email_body or llm_output.body or ""):
        # Check if promo codes are explicitly authorized in business context
        authorized_promos = [p.lower() for p in (biz_ctx.get("authorized_promo_codes") or [])]
        for m in _PROMO_CODE_PATTERN.finditer(llm_output.email_body or llm_output.body or ""):
            code = m.group(1).lower()
            if code not in authorized_promos:
                msg = f"Unauthorized promotional discount code mentioned: '{code}'."
                policy_violations.append(msg)
                logger.warning("[policy_engine] POLICY VIOLATION: %s", msg)

    # Policy 5: Refund Language Rules
    for unauth_refund in _UNAUTHORIZED_REFUND_PROMISES:
        if unauth_refund in email_text:
            msg = f"Unauthorized refund promise detected: '{unauth_refund}'."
            policy_violations.append(msg)
            logger.warning("[policy_engine] POLICY VIOLATION: %s", msg)

    # Policy 6: Availability & Shipping Guarantees
    for unauth_shipping in _UNAUTHORIZED_SHIPPING_GUARANTEES:
        if unauth_shipping in email_text:
            msg = f"Unauthorized shipping SLA guarantee: '{unauth_shipping}'."
            policy_violations.append(msg)
            logger.warning("[policy_engine] POLICY VIOLATION: %s", msg)

    # ── 6. Mandatory Legal Disclaimers ────────────────────────────────────────
    # Pricing disclosure disclaimer
    if any(c in email_text for c in ("$", "₹", "€", "£", "price", "pricing", "cost")):
        disclaimers_added.append("Prices are subject to applicable taxes, shipping, and standard commercial terms.")

    # Hardware/specs warranty disclaimer
    if any(term in email_text for term in ("laptop", "ram", "warranty", "spec", "gpu", "hardware")):
        disclaimers_added.append("Specifications and manufacturer warranty terms are subject to standard factory conditions.")

    # Custom legal disclaimer from business profile
    custom_disclaimer = biz_ctx.get("legal_disclaimer")
    if custom_disclaimer and custom_disclaimer not in disclaimers_added:
        disclaimers_added.append(custom_disclaimer)

    # ── 7. Operational Dispatch Decision ──────────────────────────────────────
    if policy_violations:
        logger.warning("[policy_engine] Policy violations present — blocking auto-send: %s", policy_violations)
        return PolicyReport(
            approved_for_sending=False,
            action="escalate" if any("internal" in pv.lower() or "exceeds" in pv.lower() for pv in policy_violations) else "draft",
            send_email=False,
            escalation_requested=True,
            escalation_reason=f"Policy violation: {policy_violations[0]}",
            confidence_score=composite_confidence,
            disclaimers_added=disclaimers_added,
            policy_violations=policy_violations,
        )

    # Dispatch logic when no policy violations occur
    action: str = "reply"
    send_email: bool = False

    if strategy.mode == "answer":
        if composite_confidence >= AUTO_SEND_MIN_CONFIDENCE:
            action = "reply"
            send_email = True
        else:
            action = "draft"
            send_email = False
            policy_violations.append(f"Confidence {composite_confidence:.2f} below threshold {AUTO_SEND_MIN_CONFIDENCE:.2f}")

    elif strategy.mode == "clarify":
        if composite_confidence >= 0.60 and (llm_output.clarification_questions or "?" in llm_output.email_body):
            action = "reply"
            send_email = True
        else:
            action = "draft"
            send_email = False

    elif strategy.mode == "no_match":
        if composite_confidence >= 0.60:
            action = "reply"
            send_email = True
        else:
            action = "draft"
            send_email = False

    elif strategy.mode == "partial_result":
        action = "draft"
        send_email = False
        disclaimers_added.append("Review needed for secondary missing information.")

    approved_for_sending = (send_email is True and len(policy_violations) == 0)

    logger.info(
        "[policy_engine] evaluated | mode=%s action=%s send_email=%s conf=%.2f disclaimers=%d",
        strategy.mode, action, send_email, composite_confidence, len(disclaimers_added),
    )

    return PolicyReport(
        approved_for_sending=approved_for_sending,
        action=action,  # type: ignore[arg-type]
        send_email=send_email,
        escalation_requested=False,
        escalation_reason=None,
        confidence_score=composite_confidence,
        disclaimers_added=disclaimers_added,
        policy_violations=policy_violations,
    )
