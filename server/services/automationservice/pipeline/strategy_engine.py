"""
automationservice — Response Strategy Engine (Phase 6)
======================================================
Operates deterministically BEFORE OpenAI Call #2.
Decides the authorized response mode:
  - 'answer'         : Full, factually grounded answer.
  - 'clarify'        : Must pose clarification questions to customer.
  - 'partial_result' : Answering supported parts while acknowledging missing data.
  - 'no_match'       : Incompatible requirements or out-of-catalog request.
  - 'escalate'       : Human attention required (conflict, complaint, or explicit request).

CRITICAL DIRECTIVE:
  OpenAI #2 does NOT override this engine.
  If this engine dictates mode='clarify', OpenAI #2 must generate a clarification
  response and is strictly forbidden from converting the response to mode='answer'.
"""
from __future__ import annotations

import logging
from typing import Any

from pipeline.contracts import (
    CustomerRequirements,
    ResponseStrategy,
    ResponseMode,
    VerifiedEvidence,
    EvidenceConflict,
)
from pipeline.grounded_context_builder import GroundedContextPackage

logger = logging.getLogger("automationservice.pipeline.strategy_engine")


def determine_response_strategy(
    p1_output: dict[str, Any] | None,
    customer_requirements: CustomerRequirements,
    context_package: GroundedContextPackage,
    business_context: dict[str, Any] | None = None,
) -> ResponseStrategy:
    """
    Determine the operational strategy and response mode before LLM generation.

    Args:
        p1_output: Complete output of Processor #1.
        customer_requirements: Structured hard/soft customer requirements.
        context_package: Verified grounded facts and conflict records.
        business_context: Business profile from PostgreSQL.

    Returns:
        Authoritative ResponseStrategy instance governing Call #2.
    """
    p1 = p1_output or {}
    ca = p1.get("conversation_analysis") or {}
    ia = p1.get("intent_analysis") or {}
    rd = p1.get("routing_decision") or {}
    rc = p1.get("retrieval_contract") or {}
    open_esc = p1.get("open_escalation") or {}

    customer_goal = ca.get("customer_goal") or "General Inquiry"
    clarification_flag = bool(rc.get("clarification_required", False))
    escalation_requested = bool(
        rd.get("escalation_requested", False)
        or rd.get("requires_human_attention", False)
        or open_esc.get("open", False)
    )

    approved_facts = context_package.approved_facts
    conflicts = context_package.conflicts
    prohibited_ids = set(context_package.prohibited_fact_ids)

    # Filter out company-only facts to see if product/operational facts exist
    product_facts = [f for f in approved_facts if f.source_type in ("product", "policy", "delivery", "support", "analytics")]
    all_allowed_ids = [f.evidence_id for f in approved_facts if f.evidence_id not in prohibited_ids]

    # ── Check 1: Explicit Escalation or Critical Unresolved Conflict ───────────
    # If customer asked for escalation, human agent, or severe complaint
    if escalation_requested:
        reason = rd.get("reason") or open_esc.get("reason") or "Customer requested escalation or human review."
        logger.info("[strategy_engine] mode=escalate | reason=%s", reason)
        return ResponseStrategy(
            mode="escalate",
            objective="Acknowledge the customer's request and confirm that their inquiry is routed to a human representative.",
            required_sections=["greeting", "escalation_notice", "next_steps", "closing"],
            allowed_actions=["confirm_handover"],
            missing_information=["Human specialist review needed"],
            required_clarifications=[],
            allowed_facts=all_allowed_ids,
            prohibited_facts=list(prohibited_ids),
            allow_pricing=False,
            allow_availability=False,
            allow_alternatives=False,
        )

    # If critical unresolved conflict exists on price, return policy, or availability
    critical_conflicts = [
        c for c in conflicts
        if c.resolution == "unresolved" and c.attribute.lower() in (
            "price", "cost", "warranty", "return_window", "stock", "availability", "in_stock"
        )
    ]
    if critical_conflicts:
        c_attr = critical_conflicts[0].attribute
        c_ent = critical_conflicts[0].entity_name
        logger.warning("[strategy_engine] mode=escalate | critical unresolved conflict on %s.%s", c_ent, c_attr)
        is_avail_conflict = c_attr.lower() in ("stock", "availability", "in_stock")
        is_price_conflict = c_attr.lower() in ("price", "cost")
        return ResponseStrategy(
            mode="escalate",
            objective=f"Inform customer that their inquiry regarding {c_ent} {c_attr} is being confirmed with the management team. Do NOT claim any conflicting state as definitive.",
            required_sections=["greeting", "under_review_notice", "next_steps", "closing"],
            allowed_actions=["state_review_in_progress"],
            missing_information=[f"Authoritative verification required for {c_ent} {c_attr}"],
            required_clarifications=[],
            allowed_facts=[f.evidence_id for f in approved_facts if f.evidence_id not in prohibited_ids and f.entity_name != c_ent],
            prohibited_facts=list(prohibited_ids),
            allow_pricing=False if is_price_conflict else True,
            allow_availability=False if is_avail_conflict else True,
            allow_alternatives=True,
        )

    # ── Check 2: No Match / Out of Catalog / Domain Incompatible ──────────────
    # Case 2a: No product/policy facts found at all
    if not product_facts:
        logger.info("[strategy_engine] mode=no_match | no product/operational facts found")
        biz_name = (business_context or {}).get("business_name") or "Our Team"
        biz_type = (business_context or {}).get("business_type") or "products"
        return ResponseStrategy(
            mode="no_match",
            objective=f"Politely explain that {biz_name} does not carry the requested item or service, and explain what {biz_name} provides.",
            required_sections=["greeting", "no_match_explanation", "business_capabilities", "closing"],
            allowed_actions=["state_catalog_limitations", "offer_relevant_scope"],
            missing_information=["Requested product or service not in business catalog"],
            required_clarifications=[],
            allowed_facts=all_allowed_ids,
            prohibited_facts=list(prohibited_ids),
            allow_pricing=False,
            allow_availability=False,
            allow_alternatives=False,
        )

    # Case 2b: Hard budget constraint violation (e.g. budget $500, but all retrieved laptops are > $1000)
    budget_req = next((hr for hr in customer_requirements.hard if hr.field == "budget"), None)
    if budget_req and isinstance(budget_req.value, (int, float)):
        budget_limit = float(budget_req.value)
        # Check prices of retrieved products
        prices = []
        for f in approved_facts:
            if f.attribute.lower() in ("price", "cost") and f.evidence_id not in prohibited_ids:
                try:
                    num_val = float(str(f.value).replace("$", "").replace(",", "").strip())
                    prices.append((num_val, f.entity_name, f.evidence_id))
                except (ValueError, TypeError):
                    continue

        if prices and all(p[0] > budget_limit for p in prices):
            cheapest = min(prices, key=lambda x: x[0])
            logger.info(
                "[strategy_engine] mode=no_match | budget limit $%.2f exceeded (cheapest: $%.2f %s)",
                budget_limit, cheapest[0], cheapest[1],
            )
            return ResponseStrategy(
                mode="no_match",
                objective=f"Politely explain that all current models in this category start above the requested ${budget_limit:g} budget, mentioning our starting option ({cheapest[1]} at ${cheapest[0]:g}).",
                required_sections=["greeting", "budget_discrepancy_explanation", "available_options", "closing"],
                allowed_actions=["quote_starting_price", "offer_alternatives"],
                missing_information=[f"No models found within ${budget_limit:g} budget"],
                required_clarifications=[],
                allowed_facts=all_allowed_ids,
                prohibited_facts=list(prohibited_ids),
                allow_pricing=True,
                allow_availability=True,
                allow_alternatives=True,
            )

    # Case 2c: Hard specification requirement violation (e.g. must_have = RTX GPU, but candidate only has integrated graphics)
    for hr in customer_requirements.hard:
        if hr.field in ("gpu", "ram", "storage", "cpu", "specification", "must_have"):
            hr_val = str(hr.value).lower().strip()
            # Check if any approved fact satisfies this requirement
            req_satisfied = False
            candidate_spec = "the requested specifications"
            for f in approved_facts:
                if f.evidence_id in prohibited_ids:
                    continue
                f_val = str(f.value).lower().strip()
                f_claim = f.claim.lower().strip()
                if hr_val in f_val or hr_val in f_claim or (hr.field in f.attribute.lower() and hr_val in f_val):
                    req_satisfied = True
                    break
                if hr.field in f.attribute.lower() or f.attribute.lower() in ("gpu", "graphics", "specs", "ram"):
                    candidate_spec = f"{f.attribute}: {f.value}"

            if not req_satisfied and product_facts:
                logger.info(
                    "[strategy_engine] mode=no_match | hard requirement '%s=%s' not satisfied (candidate: %s)",
                    hr.field, hr.value, candidate_spec
                )
                return ResponseStrategy(
                    mode="no_match",
                    objective=f"Politely inform the customer that our available models do not meet their hard requirement for {hr.value} (available model features {candidate_spec}). The response must NOT claim the candidate satisfies the requirement.",
                    required_sections=["greeting", "specification_mismatch_explanation", "alternative_options", "closing"],
                    allowed_actions=["state_specification_limitations", "offer_relevant_scope"],
                    missing_information=[f"No models found satisfying hard requirement: {hr.raw_text}"],
                    required_clarifications=[],
                    allowed_facts=all_allowed_ids,
                    prohibited_facts=list(prohibited_ids),
                    allow_pricing=False,
                    allow_availability=False,
                    allow_alternatives=True,
                )

    # ── Check 3: Clarification Required ───────────────────────────────────────
    # If Call #1 flagged clarification, or customer query is ambiguous
    if clarification_flag:
        logger.info("[strategy_engine] mode=clarify | clarification_flag=True")
        return ResponseStrategy(
            mode="clarify",
            objective="Politely ask the customer for specific details (such as preferred specifications, budget, or use case) to provide accurate recommendations.",
            required_sections=["greeting", "clarification_request", "guided_options", "closing"],
            allowed_actions=["ask_targeted_questions", "mention_general_categories"],
            missing_information=["Specific user requirements or target product selection"],
            required_clarifications=[
                "What primary tasks or software will you run?",
                "Do you have a specific budget range or preferred screen size?",
            ],
            allowed_facts=all_allowed_ids,
            prohibited_facts=list(prohibited_ids),
            allow_pricing=False,
            allow_availability=False,
            allow_alternatives=False,
        )

    # ── Check 4: Missing Price / Partial Result ────────────────────────────────
    # Check if pricing was explicitly inquired about but is missing or unknown in evidence
    wants_pricing = (
        "price" in customer_goal.lower()
        or "how much" in customer_goal.lower()
        or "cost" in customer_goal.lower()
        or any(hr.field in ("price", "cost", "budget") for hr in customer_requirements.hard)
    )
    has_valid_price = any(
        f.attribute.lower() in ("price", "cost")
        and str(f.value).lower() not in ("unknown", "none", "null", "unavailable", "")
        and f.evidence_id not in prohibited_ids
        for f in approved_facts
    )

    if wants_pricing and not has_valid_price:
        logger.info("[strategy_engine] mode=partial_result | pricing requested but price is unknown/missing")
        return ResponseStrategy(
            mode="partial_result",
            objective="Answer using verified details (such as availability and specifications), but honestly state that pricing information is currently unavailable. The model must NOT produce a price.",
            required_sections=["greeting", "available_details", "missing_price_acknowledgement", "next_steps", "closing"],
            allowed_actions=["state_specs", "state_availability", "confirm_followup"],
            missing_information=["Pricing information is unavailable"],
            required_clarifications=[],
            allowed_facts=all_allowed_ids,
            prohibited_facts=list(prohibited_ids),
            allow_pricing=False,
            allow_availability=True,
            allow_alternatives=True,
        )

    # Check if multiple questions/intents exist and some lack facts
    secondary_intents = ia.get("secondary_intents") or []
    missing_items: list[str] = []
    if len(secondary_intents) > 0:
        for si in secondary_intents:
            cat = si.get("category", "")
            # Check if we have facts for this secondary intent
            has_cat_facts = any(f.metadata.get("category") == cat for f in approved_facts)
            if not has_cat_facts:
                missing_items.append(f"Information regarding {cat.replace('_', ' ')}")

    if missing_items:
        logger.info("[strategy_engine] mode=partial_result | missing: %s", missing_items)
        return ResponseStrategy(
            mode="partial_result",
            objective="Answer the primary inquiry directly using verified evidence, and transparently state that details for remaining items are being retrieved.",
            required_sections=["greeting", "direct_answer", "missing_aspects_acknowledgement", "next_steps", "closing"],
            allowed_actions=["quote_price", "state_specs", "confirm_followup"],
            missing_information=missing_items,
            required_clarifications=[],
            allowed_facts=all_allowed_ids,
            prohibited_facts=list(prohibited_ids),
            allow_pricing=has_valid_price and customer_requirements.communication.include_pricing,
            allow_availability=True,
            allow_alternatives=True,
        )

    # ── Check 5: Direct Answer (Default Success Path) ─────────────────────────
    logger.info("[strategy_engine] mode=answer | verified facts satisfy customer goal: %s", customer_goal[:50])
    return ResponseStrategy(
        mode="answer",
        objective=f"Provide a direct, thorough, and professional response satisfying '{customer_goal}' using exclusively verified evidence.",
        required_sections=["greeting", "recommendation_or_answer", "key_specifications", "pricing_and_warranty", "closing"],
        allowed_actions=["quote_price", "state_specs", "state_warranty", "state_policy"],
        missing_information=[],
        required_clarifications=[],
        allowed_facts=all_allowed_ids,
        prohibited_facts=list(prohibited_ids),
        allow_pricing=customer_requirements.communication.include_pricing,
        allow_availability=True,
        allow_alternatives=customer_requirements.communication.include_alternatives,
    )

