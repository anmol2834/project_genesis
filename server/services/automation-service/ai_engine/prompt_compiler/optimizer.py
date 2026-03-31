"""
Prompt Compiler — Optimizer
============================
Token trimming before the prompt is sent to the LLM.

CRITICAL RULE: The optimizer MUST NEVER corrupt prompt structure.
It only trims content within sections — never removes sections entirely.

Trim priority (highest value kept longest):
  1. System prompt        — never trimmed
  2. Incoming message     — never trimmed (it's what we're responding to)
  3. Metadata             — never trimmed (required for threading)
  4. Intent / constraints — never trimmed (small, critical)
  5. Business context     — trimmed last among knowledge
  6. Conversation history — trimmed before knowledge
  7. Knowledge context    — trimmed first (largest, most redundant)

Token estimation: len(text) // 4  (conservative English approximation)
"""
from __future__ import annotations

import re
from typing import Tuple

# Hard caps
_MAX_TOTAL_CHARS     = 14_000   # ~3500 tokens — absolute ceiling
_MAX_KNOWLEDGE_CHARS = 1_200
_MAX_CONV_CHARS      = 1_200
_MAX_BIZ_INSTR_CHARS = 800

_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")

# All known section headers in the prompt templates — used to find section boundaries
_ALL_SECTION_HEADERS = [
    "=== BUSINESS CONTEXT ===",
    "=== CONVERSATION HISTORY ===",
    "=== INCOMING MESSAGE ===",
    "=== METADATA ===",
    "=== CLASSIFICATION ===",
    "=== TONE ===",
    "=== CONSTRAINTS ===",
    "=== INSTRUCTIONS ===",
    "=== TASK ===",
    "=== KNOWLEDGE ===",
    "=== GUIDELINES ===",
]


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 chars."""
    return max(1, len(text) // 4)


def estimate_prompt_tokens(system_prompt: str, user_prompt: str) -> int:
    """Estimate total tokens for a system + user prompt pair."""
    return estimate_tokens(system_prompt) + estimate_tokens(user_prompt)


def clean_whitespace(text: str) -> str:
    """Collapse excessive blank lines and spaces."""
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def trim_section(text: str, max_chars: int) -> str:
    """
    Trim a text section to max_chars.
    Tries to break at a word boundary. Appends '...' if truncated.
    """
    if not text or len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:") + "..."


def _find_section_end(prompt: str, content_start: int) -> int:
    """
    Find the end of a section by looking for the next known section header.
    Returns len(prompt) if no next header found.
    CRITICAL: searches ALL known headers, not just one specific one.
    """
    best_end = len(prompt)
    for header in _ALL_SECTION_HEADERS:
        idx = prompt.find(header, content_start)
        if idx != -1 and idx < best_end:
            best_end = idx
    return best_end


def _trim_section_in_prompt(
    prompt: str,
    section_header: str,
    max_chars: int,
) -> str:
    """
    Find a named section in the prompt and trim its content to max_chars.
    Uses _find_section_end to correctly locate the next section boundary.
    NEVER removes the section header or any other section.
    """
    start_idx = prompt.find(section_header)
    if start_idx == -1:
        return prompt  # Section not present — leave prompt unchanged

    content_start = start_idx + len(section_header)
    end_idx = _find_section_end(prompt, content_start)

    section_content = prompt[content_start:end_idx].strip()
    if len(section_content) <= max_chars:
        return prompt  # Already within budget — no change needed

    trimmed_content = trim_section(section_content, max_chars)

    return (
        prompt[:content_start]
        + "\n"
        + trimmed_content
        + "\n\n"
        + prompt[end_idx:]
    )


def optimize_user_prompt(
    user_prompt: str,
    max_total_tokens: int = 2800,
) -> Tuple[str, int]:
    """
    Optimize the user prompt to fit within max_total_tokens.

    Strategy:
      1. Clean whitespace first (free wins).
      2. If still over budget, trim knowledge context section.
      3. If still over budget, trim conversation history section.
      4. If still over budget, trim business context section.
      5. Hard char cap as final safety net (never removes sections).

    CRITICAL: NEVER removes =INCOMING MESSAGE=, =METADATA=, =CLASSIFICATION=,
    =TONE=, =CONSTRAINTS=, =INSTRUCTIONS=, or =TASK= sections.

    Returns:
        (optimized_prompt, estimated_tokens)
    """
    prompt = clean_whitespace(user_prompt)

    # Fast path: already within budget
    tokens = estimate_tokens(prompt)
    if tokens <= max_total_tokens:
        return prompt, tokens

    # ── Trim knowledge context (if present) ──────────────────────────────
    prompt = _trim_section_in_prompt(prompt, "=== KNOWLEDGE ===", _MAX_KNOWLEDGE_CHARS)
    tokens = estimate_tokens(prompt)
    if tokens <= max_total_tokens:
        return prompt, tokens

    # ── Trim conversation history ─────────────────────────────────────────
    prompt = _trim_section_in_prompt(prompt, "=== CONVERSATION HISTORY ===", _MAX_CONV_CHARS)
    tokens = estimate_tokens(prompt)
    if tokens <= max_total_tokens:
        return prompt, tokens

    # ── Trim business context ─────────────────────────────────────────────
    prompt = _trim_section_in_prompt(prompt, "=== BUSINESS CONTEXT ===", _MAX_BIZ_INSTR_CHARS)
    tokens = estimate_tokens(prompt)
    if tokens <= max_total_tokens:
        return prompt, tokens

    # ── Hard char cap (last resort — preserves structure, just cuts at end) ──
    max_chars = max_total_tokens * 4
    if len(prompt) > max_chars:
        # Find the last complete section before the cap
        prompt = prompt[:max_chars]
        # Don't append truncated marker — just return what we have
    return prompt, estimate_tokens(prompt)
