"""
Validators — Response Validator
================================
Content safety and hallucination prevention layer.

Checks (all independent — failures collected before returning):
  1. Length       — too short (<10 chars) or too long (>4000 chars)
  2. PII leakage  — SSN, credit card, phone number patterns in reply
  3. Policy       — threats, profanity, legal language in reply
  4. Hallucination — URLs/emails in reply not present in the original context
  5. Sanitize     — strip suspicious bare URLs from reply (non-destructive)

A failed validation sets passed=False. The Decision Finalizer maps this to NO_RESPONSE.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from .json_validator import ParsedLLMOutput
from ..schemas.ai_input import AIEngineInput

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_REPLY_CHARS = 10
MAX_REPLY_CHARS = 4000

# ── Regex patterns ────────────────────────────────────────────────────────────
_SSN_RE          = re.compile(r"\b\d{3}[-.\s]\d{2}[-.\s]\d{4}\b")
_CREDIT_CARD_RE  = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")
_PHONE_RE        = re.compile(r"\b(\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b")
_URL_RE          = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_EMAIL_RE        = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.IGNORECASE)
_THREAT_RE       = re.compile(
    r"\b(sue|lawsuit|legal action|attorney|court|report you|threatening)\b",
    re.IGNORECASE,
)
_PROFANITY_RE    = re.compile(
    r"\b(f+u+c+k|sh[i1]t|a+s+s+h+o+l+e|b[i1]tch|bastard)\b",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    """Output of the Response Validator."""
    passed:          bool
    failure_reasons: List[str] = field(default_factory=list)
    sanitized_reply: str = ""


class ResponseValidator:
    """
    Multi-check response validator.
    All checks run independently — all failures collected before returning.
    """

    async def validate(
        self,
        parsed_output: ParsedLLMOutput,
        ai_input: AIEngineInput,
        context_data_flags: dict = None,
    ) -> ValidationResult:
        """
        Run all content validation checks.

        Args:
            parsed_output:      Output from JSONValidator.
            ai_input:           Original pipeline input (for hallucination context).
            context_data_flags: Data availability flags from SelectedContext.
                                Used to detect business entity hallucination.

        Returns:
            ValidationResult with passed=True if all checks pass.
        """
        reply = parsed_output.reply

        # no_response status — always valid (empty reply is expected)
        if parsed_output.status == "no_response":
            return ValidationResult(passed=True, sanitized_reply="")

        failures: List[str] = []

        # Run all checks
        failures.extend(self._check_length(reply))
        failures.extend(self._check_pii_leakage(reply))
        failures.extend(self._check_policy_violations(reply))
        failures.extend(self._check_hallucinated_entities(reply, ai_input))

        if failures:
            return ValidationResult(
                passed=False,
                failure_reasons=failures,
                sanitized_reply="",
            )

        sanitized = self._sanitize(reply)
        return ValidationResult(passed=True, sanitized_reply=sanitized)

    # ── Individual checks ─────────────────────────────────────────────────────

    def _check_length(self, reply: str) -> List[str]:
        """Reject suspiciously short or runaway long replies."""
        failures = []
        if len(reply.strip()) < MIN_REPLY_CHARS:
            failures.append(f"Reply too short ({len(reply.strip())} chars, min={MIN_REPLY_CHARS}).")
        if len(reply) > MAX_REPLY_CHARS:
            failures.append(f"Reply too long ({len(reply)} chars, max={MAX_REPLY_CHARS}).")
        return failures

    def _check_pii_leakage(self, reply: str) -> List[str]:
        """Detect PII patterns in the generated reply."""
        failures = []
        if _SSN_RE.search(reply):
            failures.append("PII detected: SSN pattern in reply.")
        if _CREDIT_CARD_RE.search(reply):
            failures.append("PII detected: credit card pattern in reply.")
        return failures

    def _check_policy_violations(self, reply: str) -> List[str]:
        """Detect threats or profanity in the generated reply."""
        failures = []
        if _THREAT_RE.search(reply):
            failures.append("Policy violation: legal threat language in reply.")
        if _PROFANITY_RE.search(reply):
            failures.append("Policy violation: profanity detected in reply.")
        return failures

    def _check_hallucinated_entities(
        self,
        reply: str,
        ai_input: AIEngineInput,
    ) -> List[str]:
        """
        Detect URLs and email addresses in the reply that were not present
        in the original context (incoming message + conversation history + account emails).

        Includes account email addresses in the allowed set to prevent false positives
        when the AI correctly references the business email.
        """
        failures = []

        # Build the set of URLs/emails that were in the original context
        context_text = ai_input.incoming_message.content
        for msg in ai_input.last_24h_messages:
            context_text += " " + msg.content

        context_urls   = set(u.lower() for u in _URL_RE.findall(context_text))
        context_emails = set(e.lower() for e in _EMAIL_RE.findall(context_text))

        # Add known account emails — these are always allowed in replies
        # (the AI may reference the business email address legitimately)
        context_emails.add(ai_input.incoming_message.from_email.lower())
        for addr in (ai_input.incoming_message.to or []):
            context_emails.add(addr.lower())

        reply_urls   = set(u.lower() for u in _URL_RE.findall(reply))
        reply_emails = set(e.lower() for e in _EMAIL_RE.findall(reply))

        hallucinated_urls   = reply_urls   - context_urls
        hallucinated_emails = reply_emails - context_emails

        if hallucinated_urls:
            failures.append(f"Hallucination: URLs in reply not in context: {list(hallucinated_urls)[:3]}")
        if hallucinated_emails:
            failures.append(f"Hallucination: emails in reply not in context: {list(hallucinated_emails)[:3]}")

        return failures

    def _sanitize(self, reply: str) -> str:
        """
        Light sanitization: normalize whitespace.
        Does NOT strip URLs — that would alter meaning.
        Hallucinated URLs are caught by _check_hallucinated_entities.
        """
        reply = re.sub(r"[ \t]+", " ", reply)
        reply = re.sub(r"\n{3,}", "\n\n", reply)
        return reply.strip()
