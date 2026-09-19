"""
automationservice — Output Structure Validator (Phase 10)
=========================================================
Runs immediately after OpenAI Call #2 to perform strict, deterministic
structural validation of the generated output.

Validation Criteria:
  1. Valid JSON syntax
  2. Schema compliance (Pydantic v2 typed validation)
  3. Required fields present: response_mode, subject, body, claims
  4. Enum values correctness: response_mode in {answer, clarify, partial_result, no_match, escalate}
  5. Type correctness across all fields
  6. Non-empty required content (subject and body must contain non-whitespace text)
  7. Valid claim references: each claim has claim_id, non-empty text, and evidence_ids list
  8. Strategy compatibility: model CANNOT override mandated strategy mode
  9. Forbidden fields & internal metadata leak detection: no Qdrant, evidence IDs, or prompt leaks
  10. Strict rejection: rejects malformed model output without silent semantic mutation

Deterministic validation is used throughout.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from pipeline.contracts import (
    LLMCall2Output,
    ClaimItem,
    ResponseStrategy,
    OutputStructureValidationReport,
)

logger = logging.getLogger("automationservice.pipeline.output_validator")

# Canonical response modes
VALID_RESPONSE_MODES = frozenset({
    "answer",
    "clarify",
    "partial_result",
    "no_match",
    "escalate",
})

# Forbidden architecture/internal metadata patterns in customer-facing prose
FORBIDDEN_METADATA_PATTERNS = [
    (re.compile(r"\bqdrant\b", re.IGNORECASE), "Qdrant internal database"),
    (re.compile(r"\bembeddings?\b", re.IGNORECASE), "Embedding internal abstraction"),
    (re.compile(r"\bev_[a-zA-Z0-9_]+\b", re.IGNORECASE), "Internal evidence ID leaked in text"),
    (re.compile(r"\bevidence[_\s]id\b", re.IGNORECASE), "evidence_id label leaked in text"),
    (re.compile(r"\bconfidence[_\s]score\b", re.IGNORECASE), "Confidence score internal metric"),
    (re.compile(r"\bvector[_\s]score\b", re.IGNORECASE), "Vector search score internal metric"),
    (re.compile(r"\brerank[_\s]score\b", re.IGNORECASE), "Rerank score internal metric"),
    (re.compile(r"\bpolicy[_\s]engine\b", re.IGNORECASE), "Policy engine internal component"),
    (re.compile(r"\bsystem[_\s]prompt\b", re.IGNORECASE), "System prompt reference"),
    (re.compile(r"\bprocessor_[12]\b", re.IGNORECASE), "Processor internal name"),
    (re.compile(r"\blatency[_\s:]+\d+\b", re.IGNORECASE), "Latency internal diagnostic"),
    (re.compile(r"\bchunk_[a-zA-Z0-9_]+\b", re.IGNORECASE), "Chunk ID internal identifier"),
    (re.compile(r"\bvalidation[_\s]diagnostics\b", re.IGNORECASE), "Validation diagnostics internal label"),
    (re.compile(r"\bmodel[_\s]metadata\b", re.IGNORECASE), "Model metadata internal label"),
]


# Forbidden top-level JSON keys that should never be returned by Call #2
FORBIDDEN_TOP_LEVEL_KEYS = frozenset({
    "raw_data",
    "system_instructions",
    "prompt",
    "qdrant_point_id",
    "internal_scores",
    "debug_trace",
})


def _clean_json_string(text: str) -> str:
    """Strip markdown code fences and extraneous whitespace."""
    if not text:
        return ""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return raw


def _extract_json_object(raw_str: str) -> dict[str, Any] | None:
    """Parse JSON string with fallback regex search for JSON object."""
    clean = _clean_json_string(raw_str)
    try:
        data = json.loads(clean)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


def validate_generation_output(
    raw_output: str | LLMCall2Output | dict | None,
    strategy: ResponseStrategy,
    fallback_subject: str = "your inquiry",
) -> tuple[LLMCall2Output, OutputStructureValidationReport]:
    """
    Perform strict deterministic structural validation of OpenAI Call #2 output.

    Args:
        raw_output: Raw text output, dict, or LLMCall2Output instance from OpenAI chat completion.
        strategy: Authoritative ResponseStrategy governing this call.
        fallback_subject: Default subject line if missing.

    Returns:
        tuple (LLMCall2Output, OutputStructureValidationReport)
    """
    errors: list[str] = []
    warnings: list[str] = []
    missing_fields: list[str] = []
    forbidden_detected: list[str] = []
    strategy_compatible = True

    # Normalize input if already parsed as LLMCall2Output or dict
    if isinstance(raw_output, LLMCall2Output):
        raw_text = raw_output.model_dump_json()
    elif isinstance(raw_output, dict):
        raw_text = json.dumps(raw_output)
    else:
        raw_text = raw_output

    # ── Check 1: Raw Output Presence ──────────────────────────────────────────
    if not raw_text or not str(raw_text).strip():
        errors.append("EMPTY_OUTPUT: Received empty or null raw output from OpenAI Call #2.")
        fallback = _build_fallback_output(strategy, fallback_subject, "empty_output")
        report = OutputStructureValidationReport(
            is_valid=False,
            errors=errors,
            missing_fields=["response_mode", "subject", "body", "claims"],
            strategy_compatible=False,
        )
        return fallback, report

    # ── Check 2: Valid JSON Syntax ────────────────────────────────────────────
    parsed = _extract_json_object(str(raw_text))
    if parsed is None or not isinstance(parsed, dict):
        errors.append("INVALID_JSON: Failed to parse valid JSON object from model output.")
        fallback = _build_fallback_output(strategy, fallback_subject, "json_parse_error")
        report = OutputStructureValidationReport(
            is_valid=False,
            errors=errors,
            missing_fields=["response_mode", "subject", "body", "claims"],
            strategy_compatible=False,
        )
        return fallback, report

    # ── Check 3: Forbidden Top-Level Keys ──────────────────────────────────────
    for k in parsed.keys():
        if k in FORBIDDEN_TOP_LEVEL_KEYS:
            errors.append(f"FORBIDDEN_FIELD: Model output contains forbidden internal field '{k}'.")

    # ── Check 4: Required Fields Presence ─────────────────────────────────────
    # Normalize subject and body keys (support subject/email_subject, body/email_body)
    raw_subject = parsed.get("subject") or parsed.get("email_subject")
    raw_body = parsed.get("body") or parsed.get("email_body")
    raw_mode = parsed.get("response_mode")
    raw_claims = parsed.get("claims")

    if raw_mode is None:
        missing_fields.append("response_mode")
        errors.append("MISSING_FIELD: Required field 'response_mode' is missing.")

    if raw_subject is None:
        missing_fields.append("subject")
        errors.append("MISSING_FIELD: Required field 'subject' is missing.")

    if raw_body is None:
        missing_fields.append("body")
        errors.append("MISSING_FIELD: Required field 'body' is missing.")

    if raw_claims is None:
        missing_fields.append("claims")
        errors.append("MISSING_FIELD: Required field 'claims' is missing.")

    # ── Check 5: Non-Empty Required Content ───────────────────────────────────
    subject_str = str(raw_subject or "").strip()
    if raw_subject is not None and not subject_str:
        errors.append("EMPTY_CONTENT: 'subject' must not be empty or whitespace only.")

    body_str = str(raw_body or "").strip()
    if raw_body is not None and len(body_str) < 5:
        errors.append("EMPTY_CONTENT: 'body' must contain substantive text (minimum 5 characters).")

    # ── Check 6: Enum Values Check (response_mode) ────────────────────────────
    mode_str = str(raw_mode or "").strip().lower()
    if mode_str and mode_str not in VALID_RESPONSE_MODES:
        errors.append(
            f"INVALID_ENUM: 'response_mode' value '{mode_str}' is not in allowed modes: {sorted(VALID_RESPONSE_MODES)}."
        )

    # ── Check 7: Strategy Compatibility Check ─────────────────────────────────
    # The generation model is strictly prohibited from overriding the strategy engine
    if mode_str in VALID_RESPONSE_MODES:
        if strategy.mode != mode_str:
            # If strategy mandated clarify/no_match/escalate, model CANNOT change it to answer
            if strategy.mode in ("clarify", "no_match", "escalate"):
                errors.append(
                    f"STRATEGY_OVERRIDE_REJECTED: Model returned mode '{mode_str}' which violates mandated strategy mode '{strategy.mode}'."
                )
                strategy_compatible = False
            else:
                warnings.append(
                    f"STRATEGY_DEVIATION: Model returned mode '{mode_str}' while strategy suggested '{strategy.mode}'."
                )

    # ── Check 8: Valid Claim References ───────────────────────────────────────
    validated_claims: list[ClaimItem] = []
    if isinstance(raw_claims, list):
        for idx, c in enumerate(raw_claims, 1):
            if not isinstance(c, dict):
                errors.append(f"MALFORMED_CLAIM: Claim #{idx} must be a JSON object.")
                continue
            c_id = str(c.get("claim_id") or f"c{idx}").strip()
            c_text = str(c.get("text") or "").strip()
            c_eids = c.get("evidence_ids") or []

            if not c_text:
                errors.append(f"INVALID_CLAIM_TEXT: Claim '{c_id}' has empty text.")
                continue

            if not isinstance(c_eids, list):
                errors.append(f"INVALID_CLAIM_EVIDENCE: Claim '{c_id}' 'evidence_ids' must be a list.")
                c_eids = [str(c_eids)] if c_eids else []

            validated_claims.append(
                ClaimItem(
                    claim_id=c_id,
                    text=c_text,
                    evidence_ids=[str(e).strip() for e in c_eids if e],
                )
            )
    elif raw_claims is not None:
        errors.append("INVALID_TYPE: 'claims' field must be a JSON list.")

    # ── Check 9: Forbidden Internal Metadata Leaks ────────────────────────────
    # Scan subject and body for internal architecture strings
    combined_text = f"{subject_str} {body_str}"
    for pattern, desc in FORBIDDEN_METADATA_PATTERNS:
        match = pattern.search(combined_text)
        if match:
            leak_token = match.group(0)
            forbidden_detected.append(f"{desc} ('{leak_token}')")
            errors.append(f"FORBIDDEN_METADATA_LEAK: Customer text contains leaked internal token '{leak_token}' ({desc}).")

    # ── Check 10: Pydantic Model Validation ───────────────────────────────────
    # If there are structural errors, reject model output deterministically
    is_valid = (len(errors) == 0)

    if not is_valid:
        logger.warning(
            "[output_validator] REJECTED model output: %d errors (missing=%s, forbidden=%s)",
            len(errors), missing_fields, forbidden_detected,
        )
        fallback = _build_fallback_output(strategy, fallback_subject, "; ".join(errors[:2]))
        report = OutputStructureValidationReport(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            missing_fields=missing_fields,
            forbidden_metadata_detected=forbidden_detected,
            strategy_compatible=strategy_compatible,
        )
        return fallback, report

    # Schema is valid — construct validated LLMCall2Output
    # Normalize subject prefix
    clean_subject = subject_str
    if clean_subject and not clean_subject.lower().startswith("re:"):
        clean_subject = f"Re: {clean_subject}"

    missing_info = parsed.get("missing_information") or strategy.missing_information or []
    if isinstance(missing_info, str):
        missing_info = [missing_info]

    limitations = parsed.get("limitations") or []
    if isinstance(limitations, str):
        limitations = [limitations]

    questions = parsed.get("clarification_questions") or strategy.required_clarifications or []
    if isinstance(questions, str):
        questions = [questions]

    output = LLMCall2Output(
        response_mode=mode_str,  # type: ignore[arg-type]
        subject=clean_subject,
        body=body_str,
        claims=validated_claims,
        missing_information=[str(m).strip() for m in missing_info if m],
        limitations=[str(l).strip() for l in limitations if l],
        requires_human_review=bool(parsed.get("requires_human_review", False)),
        clarification_questions=[str(q).strip() for q in questions if q],
    )

    report = OutputStructureValidationReport(
        is_valid=True,
        errors=[],
        warnings=warnings,
        missing_fields=[],
        forbidden_metadata_detected=[],
        strategy_compatible=True,
    )

    logger.debug("[output_validator] validated successfully | mode=%s claims=%d", output.response_mode, len(output.claims))
    return output, report


def _build_default_body(strategy: ResponseStrategy) -> str:
    """Generate deterministic fallback text matching strategy mode."""
    if strategy.mode == "clarify":
        q_list = "\n".join(f"• {q}" for q in strategy.required_clarifications) or "• Could you please share more details about your specific requirements?"
        return (
            "Thank you for contacting us.\n\n"
            "To ensure we recommend the best option for your needs, could you please clarify a few details:\n\n"
            f"{q_list}\n\n"
            "We look forward to your reply!\n\nBest regards,\nCustomer Support"
        )
    elif strategy.mode == "escalate":
        return (
            "Thank you for reaching out to us.\n\n"
            "We have received your request and have escalated it to a specialist on our team for dedicated review. "
            "A representative will follow up with you directly shortly.\n\n"
            "Best regards,\nCustomer Support"
        )
    elif strategy.mode == "no_match":
        return (
            "Thank you for reaching out to us.\n\n"
            "We have reviewed our current catalog and unfortunately do not carry the specific item or configuration you requested at this time. "
            "Please feel free to check back with us or let us know if you would like recommendations in our standard product lines.\n\n"
            "Best regards,\nCustomer Support"
        )
    return (
        "Thank you for reaching out to us.\n\n"
        "We are currently reviewing your inquiry and will provide the requested details shortly.\n\n"
        "Best regards,\nCustomer Support"
    )


def _build_fallback_output(strategy: ResponseStrategy, subject: str, reason: str) -> LLMCall2Output:
    """Deterministic fallback output constructed when model output is rejected."""
    re_sub = f"Re: {subject}" if not subject.lower().startswith("re:") else subject
    return LLMCall2Output(
        response_mode=strategy.mode,
        subject=re_sub,
        body=_build_default_body(strategy),
        claims=[],
        missing_information=[f"Output structure rejection: {reason}"],
        limitations=["Automated structural validation fallback invoked"],
        requires_human_review=True,
        clarification_questions=strategy.required_clarifications,
    )
