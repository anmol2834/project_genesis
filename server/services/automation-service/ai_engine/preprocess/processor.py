"""
Preprocess Layer
================
Cleans and normalizes raw email content before AI processing.

Responsibilities:
  1. Strip HTML tags, decode HTML entities.
  2. Remove quoted reply chains (> On Mon... patterns).
  3. Remove email signatures (-- separator, common footers).
  4. Normalize whitespace and encoding artifacts.
  5. Truncate to token budget.
  6. Return PreprocessedInput ready for the Intent Engine.

No ML calls — pure text normalization only.
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List

from ..schemas.ai_input import AIEngineInput, ConversationMessage

# ── Regex patterns ────────────────────────────────────────────────────────────
_HTML_TAG_RE      = re.compile(r"<[^>]+>", re.DOTALL)
_MULTI_SPACE_RE   = re.compile(r"[ \t]+")
_MULTI_NL_RE      = re.compile(r"\n{3,}")
_QUOTED_REPLY_RE  = re.compile(
    r"(^|\n)(>.*(\n|$))+",
    re.MULTILINE,
)

# ── Email thread / reply chain patterns ──────────────────────────────────────
# These patterns match the quoted reply chain that Gmail/Outlook appends to
# reply messages. They must be stripped BEFORE any AI processing.
#
# Pattern 1: "On Mon, 1 Jan 2024, 10:00 AM, John <john@example.com> wrote:"
#   — standard Gmail/Outlook format, may or may not have a preceding newline
# Pattern 2: "On Wed, 1 Apr, 2026, 10:34 pm blackmist file, <email@...>"
#   — Gmail mobile format without "wrote:" at the end
# Pattern 3: "---------- Forwarded message ---------"
# Pattern 4: "From: ...\nSent: ...\nTo: ...\nSubject: ..."  (Outlook format)

_ON_DATE_WROTE_RE = re.compile(
    r"(\n|^|\s{2,})"                    # preceded by newline, start, or 2+ spaces
    r"[-–—]*\s*"                         # optional dash separator
    r"On\s+"                             # "On "
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?,?\s*"  # optional day name
    r"\d{1,2}\s+\w+[,\s]+\d{4}"         # date: "1 Apr, 2026" or "1 Apr 2026"
    r".*",                               # rest of line and everything after
    re.DOTALL | re.IGNORECASE,
)

# Fallback: catch any "On <date>" pattern that slipped through
_ON_DATE_FALLBACK_RE = re.compile(
    r"\s+On\s+\w+,?\s+\d{1,2}\s+\w+,?\s+\d{4}.*",
    re.DOTALL | re.IGNORECASE,
)

# Outlook-style forwarded/reply header
_OUTLOOK_HEADER_RE = re.compile(
    r"\n[-_]{3,}.*?(Forwarded|Original)\s+(message|email).*",
    re.DOTALL | re.IGNORECASE,
)

# "From: ... Sent: ... To: ... Subject: ..." block (Outlook reply format)
_OUTLOOK_FROM_RE = re.compile(
    r"\n\s*From:\s+.+?\n\s*Sent:\s+.+?\n\s*To:\s+.+",
    re.DOTALL | re.IGNORECASE,
)

_SIGNATURE_RE = re.compile(
    r"\n[-–—]{1,3}\s*\n.*",
    re.DOTALL,
)
_FOOTER_RE = re.compile(
    r"\n(sent from|get outlook|unsubscribe|this email was sent|"
    r"confidentiality notice|disclaimer|you received this).*",
    re.DOTALL | re.IGNORECASE,
)

# Token budget constants
_MAX_INCOMING_CHARS  = 2000
_MAX_HISTORY_CHARS   = 600
_CHARS_PER_TOKEN     = 4
_TOTAL_TOKEN_BUDGET  = 3000


@dataclass
class CleanMessage:
    """A single message after preprocessing."""
    message_id:    str
    from_email:    str
    direction:     str    # "incoming" | "outgoing"
    clean_content: str
    timestamp:     str    # ISO string


@dataclass
class PreprocessedInput:
    """Output contract of the Preprocess layer."""
    user_id:                str
    email_account_id:       str
    conversation_id:        str
    thread_id:              str
    subject:                str
    clean_incoming_content: str
    clean_history:          List[CleanMessage]
    message_summary:        str
    token_budget_remaining: int
    # Enterprise metadata — required for email threading
    message_id:             str = ""   # The triggering message_id
    sender_email:           str = ""   # from_email of the incoming message
    to_emails:              List[str] = field(default_factory=list)  # to_emails of the incoming message


class EmailPreprocessor:
    """Stateless email preprocessor."""

    async def process(self, ai_input: AIEngineInput) -> PreprocessedInput:
        """
        Clean the incoming message and conversation history.

        Args:
            ai_input: Raw AIEngineInput from the orchestrator.

        Returns:
            PreprocessedInput ready for the Intent Engine.
        """
        # Clean incoming message
        clean_incoming = self._clean_text(
            ai_input.incoming_message.content,
            max_chars=_MAX_INCOMING_CHARS,
        )

        # Clean conversation history (last 24h messages)
        clean_history: List[CleanMessage] = []
        for msg in ai_input.last_24h_messages:
            cleaned = self._clean_text(msg.content, max_chars=_MAX_HISTORY_CHARS)
            if not cleaned.strip():
                continue
            clean_history.append(CleanMessage(
                message_id=msg.message_id,
                from_email=msg.from_email,
                direction=msg.direction,
                clean_content=cleaned,
                timestamp=msg.timestamp.isoformat() if hasattr(msg.timestamp, "isoformat") else str(msg.timestamp),
            ))

        # Estimate remaining token budget
        used_tokens = (
            len(clean_incoming) // _CHARS_PER_TOKEN
            + sum(len(m.clean_content) // _CHARS_PER_TOKEN for m in clean_history)
        )
        budget_remaining = max(0, _TOTAL_TOKEN_BUDGET - used_tokens)

        return PreprocessedInput(
            user_id=str(ai_input.user_id),
            email_account_id=str(ai_input.email_account_id),
            conversation_id=str(ai_input.conversation_id),
            thread_id=ai_input.thread_id,
            subject=self._clean_text(ai_input.subject or "", max_chars=200),
            clean_incoming_content=clean_incoming,
            clean_history=clean_history,
            message_summary=ai_input.message_summary or "",
            token_budget_remaining=budget_remaining,
            message_id=ai_input.incoming_message.message_id,
            sender_email=ai_input.incoming_message.from_email,
            to_emails=list(ai_input.incoming_message.to or []),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _clean_text(self, text: str, max_chars: int = 2000) -> str:
        """Full cleaning pipeline for a single text string."""
        if not text:
            return ""
        text = self._strip_html(text)
        text = self._remove_quoted_reply(text)
        text = self._remove_signature(text)
        text = self._normalize_whitespace(text)
        return self._truncate_to_budget(text, max_chars)

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags and decode HTML entities."""
        text = html.unescape(text)
        text = _HTML_TAG_RE.sub(" ", text)
        text = unicodedata.normalize("NFKC", text)
        return text

    def _remove_quoted_reply(self, text: str) -> str:
        """
        Strip all email reply chain content.
        Handles Gmail, Outlook, mobile, and forwarded message formats.
        """
        # Primary: "On Wed, 1 Apr, 2026, 10:34 pm ..." (Gmail/mobile format)
        text = _ON_DATE_WROTE_RE.sub("", text)
        # Fallback: any remaining "On <date>" pattern
        text = _ON_DATE_FALLBACK_RE.sub("", text)
        # Outlook forwarded message header
        text = _OUTLOOK_HEADER_RE.sub("", text)
        # Outlook From/Sent/To block
        text = _OUTLOOK_FROM_RE.sub("", text)
        # Quoted lines starting with >
        text = _QUOTED_REPLY_RE.sub("\n", text)
        return text

    def _remove_signature(self, text: str) -> str:
        """Remove email signatures and footers."""
        text = _SIGNATURE_RE.sub("", text)
        text = _FOOTER_RE.sub("", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Collapse whitespace."""
        text = _MULTI_SPACE_RE.sub(" ", text)
        text = _MULTI_NL_RE.sub("\n\n", text)
        return text.strip()

    def _truncate_to_budget(self, text: str, max_chars: int) -> str:
        """Hard truncate to max_chars, breaking at word boundary."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit(" ", 1)[0] + "..."
