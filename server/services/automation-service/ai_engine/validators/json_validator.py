"""
Validators — JSON Validator
============================
Parses and validates the raw LLM text output.

Pipeline:
  raw_text → strip markdown fences → json.loads → schema validation → ParsedLLMOutput

Fallback chain (never discard a valid reply):
  1. Direct json.loads
  2. Strip markdown fences → json.loads
  3. Brace-counting extraction → json.loads
  4. Reply-text extraction (last resort — extract reply field from broken JSON)

The orchestrator catches JSONValidationError only when ALL fallbacks fail.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from .schema_validator import validate_schema

logger = logging.getLogger(__name__)

# Markdown code fence stripper
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

# Last-resort: extract reply value from broken JSON
_REPLY_EXTRACT_RE = re.compile(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)


@dataclass
class ParsedLLMOutput:
    """Validated and parsed LLM JSON output."""
    status:         str
    reply:          str
    confidence:     float
    intent_handled: str
    raw_text:       str
    email_payload:  dict = field(default=None)


class JSONValidationError(Exception):
    """Raised when LLM output cannot be parsed and no reply can be extracted."""
    pass


class JSONValidator:
    """
    Stateless JSON validator with multi-layer fallback.
    NEVER discards a valid reply — always tries to extract something useful.
    """

    async def validate(self, raw_text: str) -> ParsedLLMOutput:
        if not raw_text or not raw_text.strip():
            raise JSONValidationError("LLM returned empty response.")

        # ── Attempt 1: Direct parse ───────────────────────────────────────
        parsed = self._try_parse(raw_text)

        # ── Attempt 2: Strip markdown fences ─────────────────────────────
        if parsed is None:
            parsed = self._try_parse(self._strip_markdown(raw_text))

        # ── Attempt 3: Brace-counting extraction ──────────────────────────
        if parsed is None:
            parsed = self._extract_by_braces(raw_text)

        # ── Attempt 4: Schema validation ──────────────────────────────────
        if parsed is not None:
            result = validate_schema(parsed)
            if result.valid:
                cleaned = result.cleaned
                return ParsedLLMOutput(
                    status=cleaned["status"],
                    reply=cleaned["reply"],
                    confidence=cleaned["confidence"],
                    intent_handled=cleaned["intent_handled"],
                    raw_text=raw_text,
                    email_payload=parsed.get("email_payload"),
                )
            # Schema invalid but we have a dict — try to salvage reply
            logger.warning("Schema validation failed: %s — attempting reply salvage", result.errors)
            salvaged = self._salvage_reply(parsed, raw_text)
            if salvaged:
                return salvaged

        # ── Attempt 5: Last-resort reply extraction ───────────────────────
        salvaged = self._salvage_reply(parsed or {}, raw_text)
        if salvaged:
            logger.warning("JSON broken — salvaged reply from raw text | len=%d", len(raw_text))
            return salvaged

        logger.error("All JSON parsing attempts failed | raw_len=%d | raw=%s", len(raw_text), raw_text[:200])
        raise JSONValidationError("LLM output could not be parsed and no reply could be extracted.")

    # ── Parsing helpers ───────────────────────────────────────────────────────

    def _try_parse(self, text: str) -> Optional[dict]:
        """Attempt standard json.loads."""
        try:
            result = json.loads(text.strip())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _strip_markdown(self, text: str) -> str:
        """Remove markdown code fences."""
        match = _CODE_FENCE_RE.search(text)
        return match.group(1).strip() if match else text.strip()

    def _extract_by_braces(self, text: str) -> Optional[dict]:
        """
        Extract JSON by counting braces — handles nested objects correctly.
        Finds the outermost {...} block and attempts to parse it.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i, ch in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    result = self._try_parse(candidate)
                    if result is not None:
                        return result
                    # Try fixing common issues: trailing commas
                    fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
                    return self._try_parse(fixed)
        return None

    def _salvage_reply(self, parsed: dict, raw_text: str) -> Optional[ParsedLLMOutput]:
        """
        Last-resort: extract reply text from a broken/partial JSON response.
        Returns a ParsedLLMOutput with status=success if any reply text found.
        """
        # Try to get reply from parsed dict first
        reply = ""
        if parsed:
            reply = str(parsed.get("reply", "")).strip()

        # Fall back to regex extraction from raw text
        if not reply:
            match = _REPLY_EXTRACT_RE.search(raw_text)
            if match:
                try:
                    # Decode JSON string escapes
                    reply = json.loads('"' + match.group(1) + '"')
                except Exception:
                    reply = match.group(1)

        # If raw text itself looks like a plain reply (no JSON at all)
        if not reply and not raw_text.strip().startswith("{"):
            reply = raw_text.strip()[:800]

        if not reply or len(reply.strip()) < 5:
            return None

        confidence = float(parsed.get("confidence", 0.7)) if parsed else 0.7
        intent     = str(parsed.get("intent_handled", "unknown")) if parsed else "unknown"

        return ParsedLLMOutput(
            status="success",
            reply=reply.strip(),
            confidence=min(1.0, max(0.0, confidence)),
            intent_handled=intent,
            raw_text=raw_text,
        )
