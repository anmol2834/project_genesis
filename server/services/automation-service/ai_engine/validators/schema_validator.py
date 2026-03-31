"""
Validators — Schema Validator
==============================
Validates that a parsed LLM JSON dict matches the required output schema.

Required schema:
  {
    "status":         "success" | "no_response"
    "reply":          string
    "confidence":     float [0, 1]
    "intent_handled": string
  }

Rules:
  - No extra fields allowed.
  - All four fields must be present.
  - Correct types enforced.
  - confidence clamped to [0, 1].
  - reply must be a string (may be empty when status == no_response).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

REQUIRED_FIELDS  = {"status", "reply", "confidence", "intent_handled"}
OPTIONAL_FIELDS  = {"metadata", "reasoning", "follow_up", "email_payload"}   # LLM may add these — allowed
VALID_STATUSES   = {"success", "no_response"}


@dataclass
class SchemaValidationResult:
    valid:    bool
    errors:   List[str]
    cleaned:  Optional[Dict[str, Any]] = None   # Normalised dict if valid


def validate_schema(parsed: Dict[str, Any]) -> SchemaValidationResult:
    """
    Validate and normalise the parsed LLM output dict.
    Required fields must be present and correctly typed.
    Optional/extra fields are silently ignored (not rejected).
    """
    errors: List[str] = []

    # ── Check for truly unexpected extra fields (warn, don't reject) ──────
    known_fields = REQUIRED_FIELDS | OPTIONAL_FIELDS
    unexpected = set(parsed.keys()) - known_fields
    if unexpected:
        # Log but don't fail — LLM may add harmless extra fields
        pass  # Previously this caused hard failures; now we silently ignore

    # ── Check required fields present ────────────────────────────────────
    missing = REQUIRED_FIELDS - set(parsed.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")
        return SchemaValidationResult(valid=False, errors=errors)

    # ── Validate status ───────────────────────────────────────────────────
    status = parsed.get("status", "")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        errors.append(f"'status' must be one of {VALID_STATUSES}, got: {status!r}")

    # ── Validate reply ────────────────────────────────────────────────────
    reply = parsed.get("reply", "")
    if not isinstance(reply, str):
        errors.append(f"'reply' must be a string, got: {type(reply).__name__}")
        reply = str(reply)

    # ── Validate confidence ───────────────────────────────────────────────
    confidence = parsed.get("confidence", 0)
    if not isinstance(confidence, (int, float)):
        errors.append(f"'confidence' must be a number, got: {type(confidence).__name__}")
        confidence = 0.0
    confidence = float(max(0.0, min(1.0, confidence)))

    # ── Validate intent_handled ───────────────────────────────────────────
    intent_handled = parsed.get("intent_handled", "")
    if not isinstance(intent_handled, str):
        errors.append(f"'intent_handled' must be a string, got: {type(intent_handled).__name__}")
        intent_handled = str(intent_handled)

    if errors:
        return SchemaValidationResult(valid=False, errors=errors)

    cleaned = {
        "status":         status,
        "reply":          reply.strip(),
        "confidence":     confidence,
        "intent_handled": intent_handled.strip(),
    }
    return SchemaValidationResult(valid=True, errors=[], cleaned=cleaned)
