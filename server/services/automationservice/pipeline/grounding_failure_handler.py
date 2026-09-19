"""
automationservice — Grounding Failure Handler (Phase 12)
========================================================
Deterministic routing and failure resolution engine for responses that fail
factual grounding validation.

Architectural Guarantees:
  1. No automatic send of ungrounded responses.
  2. Deterministic routing:
       SUPPORTED           -> continue to Policy Engine
       PARTIALLY_SUPPORTED -> sanitize claims / regenerate if allowed
       UNSUPPORTED         -> regenerate once or escalate
       CONTRADICTED        -> block response immediately
       POLICY_VIOLATION    -> block response immediately
  3. Strict retry boundary:
       max_grounding_regenerations = 1
       After retry: requires_human_review = True
  4. Infinite retry loops are strictly impossible.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pipeline.contracts import (
    LLMCall2Output,
    GroundingReport,
    GroundingActionDirective,
    ClaimItem,
)

logger = logging.getLogger("automationservice.pipeline.grounding_failure_handler")

# Strict maximum regeneration count mandated by architecture
MAX_GROUNDING_REGENERATIONS = 1


def sanitize_partially_supported_output(
    llm_output: LLMCall2Output,
    grounding_report: GroundingReport,
) -> LLMCall2Output:
    """
    Deterministically sanitize an output by retaining only validated 'supported' claims
    and excising unverified or partially supported claims.
    """
    valid_claim_ids = {
        c.claim_id
        for c in grounding_report.claims_evaluation
        if c.classification == "supported"
    }

    sanitized_claims: list[ClaimItem] = [
        c for c in llm_output.claims
        if c.claim_id in valid_claim_ids
    ]

    # Collect texts of rejected claims to redact from prose
    rejected_texts = [
        c.text
        for c in grounding_report.claims_evaluation
        if c.classification != "supported"
    ]

    clean_body = llm_output.body or llm_output.email_body
    for r_text in rejected_texts:
        if r_text and len(r_text) > 10 and r_text in clean_body:
            # Replace rejected claim sentence with clean spacing
            clean_body = clean_body.replace(r_text, "").strip()

    # Re-normalize whitespace
    clean_body = re.sub(r"\n{3,}", "\n\n", clean_body)

    return LLMCall2Output(
        response_mode=llm_output.response_mode,
        subject=llm_output.subject,
        body=clean_body,
        claims=sanitized_claims,
        missing_information=llm_output.missing_information,
        limitations=llm_output.limitations + ["Certain secondary details were redacted due to verification requirements."],
        requires_human_review=True,
        clarification_questions=llm_output.clarification_questions,
    )


def handle_grounding_result(
    llm_output: LLMCall2Output,
    grounding_report: GroundingReport,
    regeneration_count: int = 0,
    max_regenerations: int = MAX_GROUNDING_REGENERATIONS,
) -> GroundingActionDirective:
    """
    Deterministic failure handler for grounding validation results.

    Args:
        llm_output: Raw generated output from Call #2.
        grounding_report: Result of Grounding Validator.
        regeneration_count: How many regenerations have already been performed for this turn.
        max_regenerations: Strict upper bound on regenerations (default: 1).

    Returns:
        GroundingActionDirective instructing the orchestrator how to proceed.
    """
    overall = grounding_report.overall_classification

    logger.info(
        "[grounding_failure_handler] evaluating | overall=%s score=%.2f retries=%d/%d",
        overall, grounding_report.grounding_score, regeneration_count, max_regenerations,
    )

    # ── CASE 1: SUPPORTED ─────────────────────────────────────────────────────
    if overall == "supported" and grounding_report.is_grounded:
        return GroundingActionDirective(
            decision="continue",
            can_send=True,
            requires_human_review=False,
            reason="All claims are fully supported by verified evidence.",
        )

    # ── CASE 2: CONTRADICTED (Strict Block) ───────────────────────────────────
    # Never regenerate silently on direct contradiction — block immediately
    if overall == "contradicted":
        violations_summary = "; ".join(grounding_report.violations[:2]) or "Contradicted facts detected"
        logger.warning("[grounding_failure_handler] CONTRADICTION detected — blocking response: %s", violations_summary)
        return GroundingActionDirective(
            decision="block",
            can_send=False,
            requires_human_review=True,
            reason=f"Factual contradiction with approved business evidence: {violations_summary}",
        )

    # ── CASE 3: POLICY VIOLATION (Strict Block) ───────────────────────────────
    if overall == "policy_violation":
        violations_summary = "; ".join(grounding_report.violations[:2]) or "Policy violation detected"
        logger.warning("[grounding_failure_handler] POLICY VIOLATION detected — blocking response: %s", violations_summary)
        return GroundingActionDirective(
            decision="block",
            can_send=False,
            requires_human_review=True,
            reason=f"Business policy violation: {violations_summary}",
        )

    # ── CASE 4: PARTIALLY_SUPPORTED ───────────────────────────────────────────
    if overall == "partially_supported":
        if regeneration_count < max_regenerations:
            # Build targeted corrective prompt
            problem_claims = [
                f"'{c.text}' ({c.reason})"
                for c in grounding_report.claims_evaluation
                if c.classification == "partially_supported"
            ]
            corrective = (
                "CORRECTIVE GROUNDING INSTRUCTION: The following statements contained unverified details:\n"
                + "\n".join(f"- {pc}" for pc in problem_claims)
                + "\nPlease rewrite the response to strictly use only the facts provided in the approved evidence."
            )
            logger.info("[grounding_failure_handler] PARTIALLY_SUPPORTED -> requesting regeneration (attempt %d)", regeneration_count + 1)
            return GroundingActionDirective(
                decision="regenerate",
                can_send=False,
                requires_human_review=False,
                reason="Partially supported claims detected; attempting bounded regeneration.",
                corrective_instructions=corrective,
            )
        else:
            # Regeneration budget exhausted — sanitize and require review
            sanitized = sanitize_partially_supported_output(llm_output, grounding_report)
            logger.warning("[grounding_failure_handler] PARTIALLY_SUPPORTED -> retries exhausted, sanitizing output")
            return GroundingActionDirective(
                decision="sanitize",
                can_send=False,
                requires_human_review=True,
                reason="Max regenerations reached. Output sanitized to supported claims; human review required.",
                sanitized_output=sanitized,
            )

    # ── CASE 5: UNSUPPORTED (Hallucination / Expansion / Inference) ───────────
    if overall == "unsupported":
        if regeneration_count < max_regenerations:
            unsupported_items = [
                f"'{c.text}' (Type: {c.violation_type}, Reason: {c.reason})"
                for c in grounding_report.claims_evaluation
                if c.classification == "unsupported"
            ]
            corrective = (
                "CRITICAL GROUNDING ERROR: The following assertions have no supporting evidence:\n"
                + "\n".join(f"- {ui}" for ui in unsupported_items)
                + "\nYou must OMIT all unsupported claims, remove hallucinated figures/promises, "
                "and restrict the response solely to verified evidence."
            )
            logger.info("[grounding_failure_handler] UNSUPPORTED -> requesting regeneration (attempt %d)", regeneration_count + 1)
            return GroundingActionDirective(
                decision="regenerate",
                can_send=False,
                requires_human_review=False,
                reason="Unsupported claims detected; attempting bounded regeneration.",
                corrective_instructions=corrective,
            )
        else:
            # Retries exhausted -> Escalate
            logger.warning("[grounding_failure_handler] UNSUPPORTED -> retries exhausted (count=%d) — escalating", regeneration_count)
            return GroundingActionDirective(
                decision="escalate",
                can_send=False,
                requires_human_review=True,
                reason=f"Exceeded max grounding regenerations ({max_regenerations}). Unsupported claims remain.",
            )

    # Fallback safety default
    return GroundingActionDirective(
        decision="block",
        can_send=False,
        requires_human_review=True,
        reason=f"Unknown grounding state '{overall}'; defaulting to safe block.",
    )
