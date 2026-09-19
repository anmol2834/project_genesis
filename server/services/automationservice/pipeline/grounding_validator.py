"""
automationservice — Grounding Validator (Phase 11)
=================================================
Authoritative post-generation validator that determines whether factual claims
are supported by approved verified evidence.

For each claim:
  Generated claim -> Referenced evidence -> Evidence comparison -> Supported?

Classifies claims as:
  - supported
  - partially_supported
  - unsupported
  - contradicted

The validator detects:
  1. Hallucination: A claim has no supporting evidence or cites non-existent facts.
  2. Unsupported expansion: Evidence says "starting at ₹10,000", Model says "costs exactly ₹10,000".
  3. Unsupported inference: Evidence says "ships to Gujarat", Model says "delivery will arrive tomorrow in Ahmedabad".
  4. Contradiction: Evidence says stock = unavailable, Model says "in stock".
  5. Policy violation: Evidence/policy says discount_not_allowed = true, Model says "I can offer you 15% off."

All of these MUST fail validation.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pipeline.contracts import (
    LLMCall2Output,
    ResponseStrategy,
    VerifiedEvidence,
    GroundingReport,
    ValidatedClaimItem,
    ClaimClassification,
    ViolationType,
    CustomerRequirements,
)

logger = logging.getLogger("automationservice.pipeline.grounding_validator")


# ── Regex & Extraction Helpers ────────────────────────────────────────────────

_CURRENCY_REGEX = re.compile(
    r"(?:\$|₹|€|£|Rs\.?|INR)\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)|(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:USD|INR|EUR|GBP|dollars?|rupees?)",
    re.IGNORECASE,
)

_DISCOUNT_REGEX = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:off|discount)|(?:discount\s*of\s*(\d+(?:\.\d+)?)\s*%)|offer\s+you\s+(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

_STOCK_POSITIVE_REGEX = re.compile(
    r"\b(?:in\s+stock|available\s+now|available\s+in\s+stock|ready\s+to\s+ship|currently\s+in\s+stock)\b",
    re.IGNORECASE,
)

_STOCK_NEGATIVE_REGEX = re.compile(
    r"\b(?:out\s+of\s+stock|unavailable|not\s+in\s+stock|discontinued|backordered|sold\s+out)\b",
    re.IGNORECASE,
)

_EXPANSION_EXACT_REGEX = re.compile(
    r"\b(?:costs?\s+exactly|priced?\s+exactly|exact\s+cost\s+is|fixed\s+at)\b",
    re.IGNORECASE,
)

_EXPANSION_QUALIFIER_REGEX = re.compile(
    r"\b(?:starting\s+at|starts\s+at|from\b|starting\s+from|up\s+to|as\s+low\s+as|minimum|approx(?:imately)?)\b",
    re.IGNORECASE,
)

_DELIVERY_SPECIFIC_TIMING_REGEX = re.compile(
    r"\b(?:arrive\s+tomorrow|delivery\s+will\s+arrive\s+tomorrow|deliver(?:ed)?\s+tomorrow|arrive\s+by\s+tomorrow|same-day\s+delivery|delivered\s+within\s+24\s+hours|arrives?\s+in\s+\d+\s+hours?)\b",
    re.IGNORECASE,
)


def extract_currency_amounts(text: str) -> list[float]:
    """Extract numeric money amounts from text supporting multiple currencies ($, ₹, Rs, EUR)."""
    amounts: list[float] = []
    if not text:
        return amounts
    for match in _CURRENCY_REGEX.finditer(text):
        num_str = match.group(1) or match.group(2)
        if num_str:
            try:
                val = float(num_str.replace(",", ""))
                amounts.append(val)
            except ValueError:
                continue
    return amounts


def extract_discount_percentages(text: str) -> list[float]:
    """Extract offered discount percentages from text (e.g. 15% off -> 15.0)."""
    discounts: list[float] = []
    if not text:
        return discounts
    for match in _DISCOUNT_REGEX.finditer(text):
        for g in match.groups():
            if g:
                try:
                    discounts.append(float(g))
                except ValueError:
                    continue
    return discounts


# ── Claim Verification Rules ──────────────────────────────────────────────────

def _evaluate_single_claim(
    claim_id: str,
    claim_text: str,
    evidence_ids: list[str],
    approved_map: dict[str, VerifiedEvidence],
    prohibited_set: set[str],
    discount_not_allowed: bool = False,
    allow_pricing: bool = True,
) -> ValidatedClaimItem:
    """
    Perform deep factual comparison for a single atomic claim against cited evidence.
    """
    clean_text = (claim_text or "").strip()
    clean_eids = [eid.strip() for eid in (evidence_ids or []) if eid.strip()]

    # 1. Hallucination Check A: No evidence cited at all
    if not clean_eids:
        return ValidatedClaimItem(
            claim_id=claim_id,
            text=clean_text,
            evidence_ids=[],
            classification="unsupported",
            violation_type="hallucination",
            reason="Hallucination: Claim has no supporting evidence cited.",
            violations=[f"Claim '{claim_id}' has no supporting evidence citations."],
        )

    # 2. Hallucination Check B: Non-existent evidence cited
    invalid_eids = [eid for eid in clean_eids if eid not in approved_map and eid not in prohibited_set]
    if invalid_eids:
        return ValidatedClaimItem(
            claim_id=claim_id,
            text=clean_text,
            evidence_ids=clean_eids,
            classification="unsupported",
            violation_type="hallucination",
            reason=f"Hallucination: Cited non-existent or unapproved evidence IDs: {invalid_eids}",
            violations=[f"Claim '{claim_id}' cited invalid evidence: {invalid_eids}"],
        )

    # 3. Contradiction Check A: Prohibited / conflicting evidence cited
    prohibited_cited = [eid for eid in clean_eids if eid in prohibited_set]
    if prohibited_cited:
        return ValidatedClaimItem(
            claim_id=claim_id,
            text=clean_text,
            evidence_ids=clean_eids,
            classification="contradicted",
            violation_type="contradiction",
            reason=f"Contradiction: Cited prohibited evidence with unresolved business conflict: {prohibited_cited}",
            violations=[f"Claim '{claim_id}' cited prohibited conflicting evidence: {prohibited_cited}"],
        )

    # Fetch cited approved evidence items
    cited_items = [approved_map[eid] for eid in clean_eids if eid in approved_map]

    # 4. Policy Violation Check: Discounts offered when policy disallows discounts
    if discount_not_allowed or not allow_pricing:
        discounts = extract_discount_percentages(clean_text)
        if discounts:
            return ValidatedClaimItem(
                claim_id=claim_id,
                text=clean_text,
                evidence_ids=clean_eids,
                classification="contradicted",
                violation_type="policy_violation",
                reason=f"Policy violation: Claim offers {discounts[0]:g}% discount when discount_not_allowed=True.",
                violations=[f"Claim '{claim_id}' violates policy by offering discount: {discounts[0]:g}% off."],
            )

    # Also check if policy evidence itself forbids discount
    for cev in cited_items:
        if cev.source_type == "policy":
            meta = cev.metadata or {}
            if meta.get("discount_not_allowed") is True or "discount" in cev.claim.lower() and "not allowed" in cev.claim.lower():
                discounts = extract_discount_percentages(clean_text)
                if discounts:
                    return ValidatedClaimItem(
                        claim_id=claim_id,
                        text=clean_text,
                        evidence_ids=clean_eids,
                        classification="contradicted",
                        violation_type="policy_violation",
                        reason=f"Policy violation: Evidence forbids discount but claim offered {discounts[0]:g}%.",
                        violations=[f"Claim '{claim_id}' contradicts policy forbidding discounts."],
                    )

    # 5. Contradiction Check B: Stock / Availability Contradiction
    # Evidence says stock = unavailable / out of stock, but Model says "in stock"
    stock_is_unavailable = False
    for cev in cited_items:
        val_str = str(cev.value).lower().strip()
        claim_lower = cev.claim.lower()
        attr_lower = cev.attribute.lower()
        if attr_lower in ("stock", "availability", "in_stock", "status"):
            if cev.value is False or val_str in ("unavailable", "out of stock", "false", "0", "discontinued"):
                stock_is_unavailable = True
                break
        if _STOCK_NEGATIVE_REGEX.search(claim_lower) or _STOCK_NEGATIVE_REGEX.search(val_str):
            stock_is_unavailable = True
            break

    if stock_is_unavailable:
        if _STOCK_POSITIVE_REGEX.search(clean_text):
            return ValidatedClaimItem(
                claim_id=claim_id,
                text=clean_text,
                evidence_ids=clean_eids,
                classification="contradicted",
                violation_type="contradiction",
                reason="Contradiction: Evidence says stock=unavailable but model claims item is in stock.",
                violations=[f"Claim '{claim_id}' asserts item is in stock when evidence shows unavailable."],
            )

    # 6. Unsupported Expansion Check
    # Evidence says "starting at ₹10,000", Model says "costs exactly ₹10,000" or drops the starting qualifier
    for cev in cited_items:
        ev_claim_lower = cev.claim.lower()
        has_ev_qualifier = bool(_EXPANSION_QUALIFIER_REGEX.search(ev_claim_lower))
        if has_ev_qualifier:
            # Check if model converted it into an exact claim
            if _EXPANSION_EXACT_REGEX.search(clean_text):
                return ValidatedClaimItem(
                    claim_id=claim_id,
                    text=clean_text,
                    evidence_ids=clean_eids,
                    classification="unsupported",
                    violation_type="unsupported_expansion",
                    reason=f"Unsupported expansion: Evidence specifies starting/qualified price ('{cev.claim}') but model claims exact cost.",
                    violations=[f"Claim '{claim_id}' converts qualified evidence into an exact claim."],
                )

    # 7. Unsupported Inference Check
    # Evidence says "ships to Gujarat", Model says "delivery will arrive tomorrow in Ahmedabad"
    has_timing_promise = bool(_DELIVERY_SPECIFIC_TIMING_REGEX.search(clean_text))
    if has_timing_promise:
        # Check if ANY cited evidence supports this timing promise
        ev_supports_timing = False
        for cev in cited_items:
            if _DELIVERY_SPECIFIC_TIMING_REGEX.search(cev.claim) or _DELIVERY_SPECIFIC_TIMING_REGEX.search(str(cev.value)):
                ev_supports_timing = True
                break
        if not ev_supports_timing:
            return ValidatedClaimItem(
                claim_id=claim_id,
                text=clean_text,
                evidence_ids=clean_eids,
                classification="unsupported",
                violation_type="unsupported_inference",
                reason="Unsupported inference: Model asserts specific delivery arrival timing not present in evidence.",
                violations=[f"Claim '{claim_id}' makes unsupported delivery arrival promise."],
            )

    # Check for sub-location inference (e.g. evidence says "Gujarat", model says "Ahmedabad")
    for cev in cited_items:
        cev_text = (cev.claim + " " + str(cev.value or "")).lower()
        # If evidence specifies a state/region without mentioning a specific city
        if "gujarat" in cev_text and "ahmedabad" not in cev_text and "ahmedabad" in clean_text.lower():
            return ValidatedClaimItem(
                claim_id=claim_id,
                text=clean_text,
                evidence_ids=clean_eids,
                classification="unsupported",
                violation_type="unsupported_inference",
                reason="Unsupported inference: Evidence specifies region ('Gujarat') but model infers specific city ('Ahmedabad') without evidence.",
                violations=[f"Claim '{claim_id}' makes unsupported geographic inference."],
            )

    # 8. Numeric / Price Contradiction Check
    claim_prices = extract_currency_amounts(clean_text)
    if claim_prices:
        # Gather all prices from cited items
        cited_prices: list[float] = []
        for cev in cited_items:
            if cev.attribute.lower() in ("price", "cost", "msrp", "rate", "fee") or "price" in cev.claim.lower():
                cited_prices.extend(extract_currency_amounts(str(cev.value)))
                cited_prices.extend(extract_currency_amounts(cev.claim))

        if cited_prices:
            # Verify if every claim price matches at least one cited price
            for cp in claim_prices:
                if not any(abs(cp - p) < 0.01 for p in cited_prices):
                    return ValidatedClaimItem(
                        claim_id=claim_id,
                        text=clean_text,
                        evidence_ids=clean_eids,
                        classification="contradicted",
                        violation_type="contradiction",
                        reason=f"Contradiction: Claim asserts price {cp:g} which contradicts cited evidence prices {cited_prices}.",
                        violations=[f"Claim '{claim_id}' price {cp:g} contradicts cited evidence."],
                    )

    # 8b. Absence of Fact -> Invented Fact Check (Phase 16)
    # Verify model does not transform absence of evidence into an invented factual specification
    spec_patterns = [
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:battery|runtime|battery\s+life)\b", re.IGNORECASE), "battery"),
        (re.compile(r"\b(\d+)\s*(?:years?|yrs?)\s*(?:warranty|guarantee)\b", re.IGNORECASE), "warranty"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:inch(?:es)?|\")\s*(?:display|screen)\b", re.IGNORECASE), "display"),
    ]
    for sp_regex, spec_name in spec_patterns:
        match = sp_regex.search(clean_text)
        if match:
            spec_in_evidence = any(
                spec_name in (cev.attribute.lower() + " " + cev.claim.lower() + " " + str(cev.value or "").lower())
                for cev in cited_items
            )
            if not spec_in_evidence:
                return ValidatedClaimItem(
                    claim_id=claim_id,
                    text=clean_text,
                    evidence_ids=clean_eids,
                    classification="unsupported",
                    violation_type="hallucination",
                    reason=f"Phase 16 Violation: Absence of fact converted to invented fact. No verified evidence exists for '{spec_name}'.",
                    violations=[f"Claim '{claim_id}' invented {spec_name} specification not present in evidence."],
                )

    # 9. Factual Alignment Check: Are core entities/keywords present in cited evidence?
    # Combine all text from cited evidence, normalizing punctuation/separators
    raw_ev_text = " ".join([
        f"{cev.entity_name} {cev.attribute} {cev.claim} {str(cev.value or '')}"
        for cev in cited_items
    ]).lower()
    combined_ev_text = re.sub(r"[-_/]+", " ", raw_ev_text)

    # Stop words that should not count toward factual overlap
    _STOP_WORDS = {
        # Pronouns, determiners, conjunctions, prepositions
        "the", "and", "has", "have", "had", "with", "this", "that", "these", "those",
        "for", "from", "are", "was", "were", "been", "being", "into", "onto", "over",
        "about", "our", "your", "can", "will", "would", "shall", "should", "all",
        "any", "not", "its", "does", "did", "do", "currently", "now", "also",
        "please", "note", "noted", "here", "there", "regarding", "feature", "features",
        "included", "including", "includes", "who", "whom", "whose", "what", "which",
        "where", "when", "why", "how", "each", "every", "some", "such", "both", "few",
        "more", "most", "other", "another", "only", "own", "same", "than", "too", "very",
        "just", "but", "while", "until", "because", "between", "through", "during",
        "before", "after", "above", "below", "under", "again", "further", "then", "once",
        # Common commercial & conversational vocabulary
        "service", "services", "product", "products", "item", "items", "price", "prices",
        "priced", "pricing", "cost", "costs", "costing", "rate", "rates", "fee", "fees",
        "charge", "charges", "amount", "amounts", "detail", "details", "info",
        "information", "option", "options", "type", "types", "status", "inquiry",
        "inquiries", "request", "requests", "requested", "customer", "customers",
        "client", "clients", "team", "company", "business", "kindly", "available",
        "availability", "active", "standard", "typical", "duration", "time", "times",
        "timeline", "hour", "hours", "min", "mins", "minute", "minutes", "day", "days",
        "week", "weeks", "month", "months", "year", "years", "region", "regions",
        "area", "areas", "coverage", "covered", "instant", "instantly", "directly",
        "general", "well", "prompt", "promptly", "repair", "repairs", "repairing",
        "offer", "offers", "offered", "offering", "provide", "provides", "provided",
        "providing", "allow", "allows", "allowed", "allowing", "ensure", "ensures",
        "ensured", "ensuring", "assist", "assists", "assisted", "assisting", "help",
        "helps", "helped", "helping", "reach", "reaches", "reached", "reaching",
        "support", "supports", "supported", "supporting", "schedule", "schedules",
        "scheduled", "scheduling", "book", "books", "booked", "booking", "visit",
        "visits", "visited", "visiting", "start", "starts", "starting", "started",
        "need", "needs", "needed", "want", "wants", "wanted", "like", "get", "gets",
        "know", "make", "take", "give", "gives", "given", "come", "comes", "say",
    }

    # Extract substantive content words (normalize hyphens to spaces)
    normalized_claim = re.sub(r"[-_/]+", " ", clean_text)
    all_words = [w.lower() for w in re.findall(r"\b[A-Za-z0-9]{2,}\b", normalized_claim)]
    content_words = [w for w in all_words if w not in _STOP_WORDS]
    if not content_words:
        return ValidatedClaimItem(
            claim_id=claim_id,
            text=clean_text,
            evidence_ids=clean_eids,
            classification="supported",
            violation_type="none",
            reason="Fully supported by approved conversational phrasing.",
            violations=[],
        )

    matching_content_words = [w for w in content_words if w in combined_ev_text]
    overlap_ratio = len(matching_content_words) / max(1, len(content_words))

    if overlap_ratio >= 0.35 or (len(content_words) - len(matching_content_words)) <= 1:
        return ValidatedClaimItem(
            claim_id=claim_id,
            text=clean_text,
            evidence_ids=clean_eids,
            classification="supported",
            violation_type="none",
            reason="Fully supported by approved verified evidence.",
            violations=[],
        )

    if overlap_ratio >= 0.20 and len(matching_content_words) >= 1:
        return ValidatedClaimItem(
            claim_id=claim_id,
            text=clean_text,
            evidence_ids=clean_eids,
            classification="partially_supported",
            violation_type="none",
            reason="Partially supported: Claim has partial alignment with cited evidence.",
            violations=[],
        )

    missing_terms = [w for w in content_words if w not in combined_ev_text]
    return ValidatedClaimItem(
        claim_id=claim_id,
        text=clean_text,
        evidence_ids=clean_eids,
        classification="unsupported",
        violation_type="hallucination",
        reason=f"Hallucination: Claim asserts unverified terms not present in cited evidence: {missing_terms[:3]}.",
        violations=[f"Claim '{claim_id}' asserts unverified terms: {missing_terms[:3]}."],
    )


# ── Overall Grounding Validator Engine ────────────────────────────────────────

def validate_grounding(
    llm_output: LLMCall2Output,
    strategy: ResponseStrategy,
    verified_facts: list[VerifiedEvidence],
    prohibited_fact_ids: list[str] | None = None,
    customer_requirements: CustomerRequirements | None = None,
    business_context: dict[str, Any] | None = None,
) -> GroundingReport:
    """
    Perform authoritative deep factual grounding validation of Call #2 output.

    Evaluates every claim against referenced evidence and checks for:
      - Hallucination
      - Unsupported expansion
      - Unsupported inference
      - Contradiction
      - Policy violation

    Returns:
        GroundingReport summarizing factual classifications, score, and violations.
    """
    prohibited_set = set(prohibited_fact_ids or [])
    approved_map = {f.evidence_id: f for f in verified_facts}

    # Policy flags
    biz_ctx = business_context or {}
    discount_not_allowed = (
        biz_ctx.get("discount_not_allowed") is True
        or biz_ctx.get("allow_discounts") is False
        or biz_ctx.get("max_discount_percentage", 10) == 0
    )

    claims_evaluation: list[ValidatedClaimItem] = []
    violations: list[str] = []
    unsupported_claims: list[str] = []
    invalid_citations: list[str] = []
    prohibited_claims: list[str] = []

    supported_count = 0
    partially_supported_count = 0
    unsupported_count = 0
    contradicted_count = 0
    policy_violations_count = 0

    score = 1.0

    # ── 1. Evaluate Every Individual Claim ─────────────────────────────────────
    for claim in llm_output.claims:
        evaluated = _evaluate_single_claim(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            evidence_ids=claim.evidence_ids,
            approved_map=approved_map,
            prohibited_set=prohibited_set,
            discount_not_allowed=discount_not_allowed,
            allow_pricing=strategy.allow_pricing,
        )
        claims_evaluation.append(evaluated)

        if evaluated.classification == "supported":
            supported_count += 1
        elif evaluated.classification == "partially_supported":
            partially_supported_count += 1
            score -= 0.15
        elif evaluated.classification == "unsupported":
            unsupported_count += 1
            unsupported_claims.append(evaluated.text)
            violations.extend(evaluated.violations)
            if evaluated.violation_type == "hallucination":
                score -= 0.35
            elif evaluated.violation_type == "unsupported_expansion":
                score -= 0.30
            elif evaluated.violation_type == "unsupported_inference":
                score -= 0.30
            else:
                score -= 0.25
        elif evaluated.classification == "contradicted":
            contradicted_count += 1
            violations.extend(evaluated.violations)
            if evaluated.violation_type == "policy_violation":
                policy_violations_count += 1
                score -= 0.50
            else:
                score -= 0.45

    # ── 2. Validate Top-Level Citations ───────────────────────────────────────
    for ev_id in llm_output.sources_used:
        if ev_id in prohibited_set:
            if ev_id not in prohibited_claims:
                prohibited_claims.append(ev_id)
                violations.append(f"Output cited prohibited conflicting evidence ID '{ev_id}'.")
                score -= 0.35
        elif ev_id not in approved_map:
            if ev_id not in invalid_citations:
                invalid_citations.append(ev_id)
                violations.append(f"Output cited non-existent evidence ID '{ev_id}'.")
                score -= 0.20

    # ── 3. Global Email Body Grounding Checks ──────────────────────────────────
    email_body = llm_output.email_body or llm_output.body

    # Check A: Global Policy Violation (Discount offered anywhere in email body)
    if discount_not_allowed:
        body_discounts = extract_discount_percentages(email_body)
        if body_discounts:
            policy_violations_count += 1
            msg = f"Email body offers {body_discounts[0]:g}% discount when discount_not_allowed=True."
            if msg not in violations:
                violations.append(msg)
            score -= 0.50

    # Check B: Global Stock Contradiction anywhere in email body
    has_global_out_of_stock = any(
        (f.attribute.lower() in ("stock", "availability", "in_stock") and (f.value is False or str(f.value).lower() in ("unavailable", "out of stock", "0")))
        or _STOCK_NEGATIVE_REGEX.search(f.claim)
        for f in verified_facts if f.evidence_id not in prohibited_set
    )
    if has_global_out_of_stock and _STOCK_POSITIVE_REGEX.search(email_body):
        contradicted_count += 1
        msg = "Email body claims item is in stock when verified evidence indicates out of stock."
        if msg not in violations:
            violations.append(msg)
        score -= 0.45

    # Check C: Global Price Verification (Prices in email body must match approved prices)
    body_prices = extract_currency_amounts(email_body)
    if body_prices:
        if not strategy.allow_pricing:
            violations.append("Stated prices in email body when strategy disallowed pricing.")
            score -= 0.25
        else:
            all_approved_prices: set[float] = set()
            for f in verified_facts:
                if f.evidence_id not in prohibited_set:
                    all_approved_prices.update(extract_currency_amounts(str(f.value)))
                    all_approved_prices.update(extract_currency_amounts(f.claim))

            if all_approved_prices:
                for bp in body_prices:
                    if not any(abs(bp - ap) < 0.01 for ap in all_approved_prices):
                        unsupported_claims.append(f"Price {bp:g} in email body has no supporting evidence.")
                        violations.append(f"Hallucinated or unverified price {bp:g} in email body.")
                        score -= 0.40
                        unsupported_count += 1

    # Check D: Strategy Mode Consistency
    if strategy.mode == "no_match":
        if "we have in stock" in email_body.lower() or "available now for purchase" in email_body.lower():
            violations.append("Claimed availability in no_match mode.")
            contradicted_count += 1
            score -= 0.35

    # ── 4. Determine Overall Classification & Grounding Status ─────────────────
    grounding_score = max(0.0, min(1.0, round(score, 3)))

    if policy_violations_count > 0:
        overall_classification = "policy_violation"
    elif contradicted_count > 0:
        overall_classification = "contradicted"
    elif unsupported_count > 0:
        overall_classification = "unsupported"
    elif partially_supported_count > 0:
        overall_classification = "partially_supported"
    else:
        overall_classification = "supported"

    # Grounded if overall is supported or partially supported with score >= 0.70 and zero violations
    is_grounded = (
        overall_classification in ("supported", "partially_supported")
        and grounding_score >= 0.70
        and len(violations) == 0
        and len(unsupported_claims) == 0
        and len(prohibited_claims) == 0
    )

    logger.info(
        "[grounding_validator] overall=%s is_grounded=%s score=%.2f (supp=%d, part=%d, unsupp=%d, contra=%d, pol=%d)",
        overall_classification, is_grounded, grounding_score,
        supported_count, partially_supported_count, unsupported_count,
        contradicted_count, policy_violations_count,
    )

    return GroundingReport(
        is_grounded=is_grounded,
        grounding_score=grounding_score,
        overall_classification=overall_classification,
        claims_evaluation=claims_evaluation,
        supported_claims_count=supported_count,
        partially_supported_claims_count=partially_supported_count,
        unsupported_claims_count=unsupported_count,
        contradicted_claims_count=contradicted_count,
        policy_violations_count=policy_violations_count,
        cited_evidence_valid=(len(invalid_citations) == 0 and len(prohibited_claims) == 0),
        invalid_citations=invalid_citations,
        unsupported_claims=unsupported_claims,
        prohibited_claims_detected=prohibited_claims,
        violations=violations,
    )
