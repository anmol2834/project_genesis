
"""
Prompt Compiler — Formatter
============================
Converts structured inputs into clean, readable strings for template injection.

Responsibilities:
  - Format SelectedContext fields into prompt-ready strings
  - Format IntentResult fields (intent, sub_intent, sentiment)
  - Format PolicyDecision constraints
  - Sanitize all strings (strip control chars, limit length)
  - Produce consistent, token-minimal output

No LLM calls. No I/O. Pure string transformation.
"""
from __future__ import annotations

import re
from typing import List, Optional

from ..context_builder.schema import SelectedContext
from ..schemas.intent_schema import IntentResult, IntentType, SentimentType, RiskFlag
from ..policy_engine.schema import PolicyDecision, PromptConstraints
from ..preprocess.processor import PreprocessedInput

# Max chars for each context section before truncation
_MAX_BUSINESS_INSTRUCTION_CHARS = 600
_MAX_BUSINESS_CORE_CHARS        = 400
_MAX_KNOWLEDGE_CHARS            = 600
_MAX_CONVERSATION_CHARS         = 1200   # Increased — conversation history must never be cut short
_MAX_INCOMING_CHARS             = 1000
_MAX_SUBJECT_CHARS              = 120

_CTRL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(text: str, max_chars: int = 0) -> str:
    """Strip control characters, normalize whitespace, optionally truncate."""
    if not text:
        return ""
    text = _CTRL_CHAR_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "..."
    return text


def format_business_instruction(context: SelectedContext) -> str:
    """
    Primary business instruction from Qdrant 'instruction' chunk.
    Returns structured format for clarity.
    """
    raw = sanitize(context.business_instruction, _MAX_BUSINESS_INSTRUCTION_CHARS)
    if not raw:
        return "(business instructions not available)"
    return raw


def format_structured_business_context(context: SelectedContext) -> str:
    """
    Build a structured business context block for the prompt.
    Combines instruction + business_core + tone + use_case into a clean structure.
    CRITICAL: This is the primary knowledge source for the LLM.
    """
    parts = []

    instruction = sanitize(context.business_instruction, _MAX_BUSINESS_INSTRUCTION_CHARS)
    if instruction:
        parts.append(instruction)

    core = sanitize(context.business_core, _MAX_BUSINESS_CORE_CHARS)
    if core:
        parts.append(core)

    use_case = sanitize(context.use_case_context, 200)
    if use_case:
        parts.append(f"Use Cases: {use_case}")

    if not parts:
        return "(business context not available — respond professionally and offer to connect with the team)"

    return "\n".join(parts)


def format_business_core(context: SelectedContext) -> str:
    """Business overview from Qdrant 'business_core' chunk."""
    return sanitize(context.business_core, _MAX_BUSINESS_CORE_CHARS)


def format_tone(constraints: PromptConstraints) -> str:
    """Human-readable tone instruction with smart conditional guidance."""
    tone_map = {
        "professional":       "Professional and helpful",
        "calm_professional":  "Calm, professional, and empathetic",
        "neutral":            "Neutral and factual",
        "formal":             "Formal and precise",
        "friendly":           "Friendly and approachable",
    }
    base = tone_map.get(constraints.tone, constraints.tone.replace("_", " ").title())
    extras = []
    if not constraints.allow_pricing:
        extras.append("If pricing data is available in context → share it clearly. If not → respond professionally without guessing")
    if not constraints.allow_commitments:
        extras.append("Avoid making specific commitments on behalf of the team")
    # NOTE: allow_assumptions constraint removed — never tell AI to "not assume anything"
    # as it causes unhelpful, evasive responses
    if extras:
        return f"{base}. {'. '.join(extras)}."
    return base


def format_conversation_history(context: SelectedContext, preprocessed: "PreprocessedInput" = None) -> str:
    """
    Format conversation history as a numbered timeline.
    Uses a generous char limit — conversation history must never be truncated to empty.
    NEVER returns empty — always provides context about the thread state.
    """
    raw = context.recent_history_text or ""

    if raw.strip():
        lines = raw.strip().split("\n")
        numbered = []
        idx = 1
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("[Lead]:"):
                content = line[len("[Lead]:"):].strip()
                numbered.append(f"{idx}. User: {content}")
                idx += 1
            elif line.startswith("[You (AI)]:"):
                content = line[len("[You (AI)]:"):].strip()
                numbered.append(f"{idx}. Assistant: {content}")
                idx += 1
            else:
                numbered.append(f"{idx}. {line}")
                idx += 1

        if numbered:
            # Use 1200 chars — generous limit so history is never cut to empty
            timeline = "Conversation Timeline:\n" + "\n".join(numbered)
            return sanitize(timeline, 1200)

    # Fallback: check conversation summary
    if context.conversation_summary:
        summary = sanitize(context.conversation_summary, 800)
        if summary:
            return f"Conversation Summary:\n{summary}"

    return "No previous messages in this thread."


def format_knowledge_context(context: SelectedContext) -> str:
    """
    Assemble knowledge context from business_core + use_case_context.
    Keeps it minimal — only what's relevant.
    """
    parts = []
    if context.business_core:
        parts.append(sanitize(context.business_core, 250))
    if context.use_case_context:
        parts.append(sanitize(context.use_case_context, 200))
    if context.conversation_summary:
        parts.append(f"Summary: {sanitize(context.conversation_summary, 200)}")
    combined = "\n".join(parts)
    return sanitize(combined, _MAX_KNOWLEDGE_CHARS) if combined else "(no knowledge available)"


def format_incoming_message(preprocessed: PreprocessedInput) -> str:
    """Clean incoming message text, truncated to budget."""
    return sanitize(preprocessed.clean_incoming_content, _MAX_INCOMING_CHARS)


def format_subject(preprocessed: PreprocessedInput) -> str:
    """Email subject line."""
    return sanitize(preprocessed.subject or "", _MAX_SUBJECT_CHARS) or "(no subject)"


def format_metadata(preprocessed: PreprocessedInput) -> str:
    """
    Format full enterprise metadata for prompt injection.
    All fields required for email threading and audit traceability.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)

    thread_id        = preprocessed.thread_id or ""
    message_id       = getattr(preprocessed, "message_id", "") or ""
    sender_email     = getattr(preprocessed, "sender_email", "") or ""
    email_account_id = getattr(preprocessed, "email_account_id", "") or ""
    to_emails        = getattr(preprocessed, "to_emails", []) or []

    missing = []
    if not thread_id:    missing.append("thread_id")
    if not message_id:   missing.append("message_id")
    if not sender_email: missing.append("sender_email")

    if missing:
        _log.warning(
            "METADATA INCOMPLETE: missing=%s | conv=%s",
            missing, preprocessed.conversation_id,
        )

    to_str = ", ".join(to_emails) if isinstance(to_emails, list) else str(to_emails)

    return (
        f"conversation_id:  {preprocessed.conversation_id}\n"
        f"thread_id:        {thread_id}\n"
        f"message_id:       {message_id}\n"
        f"reply_to:         {sender_email}\n"
        f"lead_email:       {sender_email}\n"
        f"to:               {to_str}\n"
        f"user_id:          {preprocessed.user_id}\n"
        f"email_account_id: {email_account_id}"
    )


def format_intent_section(intent_result: IntentResult) -> dict:
    """Return a dict of intent-related strings for template injection."""
    return {
        "intent":     intent_result.intent.value,
        "sub_intent": intent_result.sub_intent.value,
        "sentiment":  intent_result.sentiment.value,
    }


def format_constraints_section(constraints: PromptConstraints) -> dict:
    """Return a dict of constraint strings for template injection."""
    return {
        "max_tokens":       str(constraints.max_tokens),
        "strict_mode":      "YES" if constraints.strict_mode else "NO",
        "allow_pricing":    "YES" if constraints.allow_pricing else "NO",
        "allow_commitments":"YES" if constraints.allow_commitments else "NO",
        "tone":             format_tone(constraints),
    }


def format_mixed_intent_note(intent_result: IntentResult) -> str:
    """Return a mixed-intent instruction if secondary intents exist."""
    if not intent_result.secondary_intents:
        return ""
    from .templates import MIXED_INTENT_NOTE
    return MIXED_INTENT_NOTE.format(intent=intent_result.intent.value)


def has_sufficient_context(context: SelectedContext) -> bool:
    """
    Returns True if there is enough context to attempt a response.
    False triggers the NO_CONTEXT template path.
    """
    has_knowledge = bool(
        context.business_instruction.strip()
        or context.business_core.strip()
        or context.use_case_context.strip()
    )
    has_conversation = bool(context.recent_history_text.strip())
    has_summary = bool(context.conversation_summary.strip())
    return has_knowledge or has_conversation or has_summary
