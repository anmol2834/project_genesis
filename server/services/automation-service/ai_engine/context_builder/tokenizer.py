"""
Context Builder — Tokenizer
============================
Token estimation and budget enforcement.

Token estimation: len(text) // 4  (standard approximation for English text)

Budget enforcement:
  Priority order when trimming:
    1. Intent context  (highest value — directly relevant to the message)
    2. Conversation    (second — grounding in thread history)
    3. Knowledge       (third — business background)

  CRITICAL: Conversation blocks are NEVER sorted by score — they must
  preserve chronological order (oldest first) so the LLM sees the thread
  in the correct sequence.
"""
from __future__ import annotations

from typing import List, Tuple

from .schema import ContextBlock, ContextResult

# Chars per token approximation
_CHARS_PER_TOKEN = 4

# Hard token budget caps per context group
# Increased conversation budget to ensure full history fits
_MAX_CONVERSATION_TOKENS = 600
_MAX_KNOWLEDGE_TOKENS    = 400
_MAX_INTENT_TOKENS       = 200


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def trim_to_budget(
    blocks: List[ContextBlock],
    max_tokens: int,
    preserve_order: bool = False,
) -> Tuple[List[ContextBlock], int]:
    """
    Trim a list of ContextBlocks to fit within max_tokens.

    Args:
        blocks:         List of context blocks to trim.
        max_tokens:     Maximum token budget.
        preserve_order: If True, keep blocks in original order (for conversation).
                        If False, sort by score descending (for knowledge).

    Returns:
        (trimmed_blocks, total_tokens_used)
    """
    if not blocks:
        return [], 0

    if preserve_order:
        # Conversation: keep all blocks in order, truncate last if needed
        kept: List[ContextBlock] = []
        used_tokens = 0
        for block in blocks:
            block_tokens = estimate_tokens(block.content)
            if used_tokens + block_tokens <= max_tokens:
                kept.append(block)
                used_tokens += block_tokens
            else:
                # Try to fit a truncated version of this block
                remaining = max_tokens - used_tokens
                if remaining >= 20:
                    truncated_chars = remaining * _CHARS_PER_TOKEN
                    truncated_content = block.content[:truncated_chars].rsplit(" ", 1)[0] + "..."
                    truncated_block = ContextBlock(
                        content=truncated_content,
                        score=block.score,
                        source=block.source,
                        chunk_type=block.chunk_type,
                        token_count=remaining,
                    )
                    kept.append(truncated_block)
                    used_tokens += remaining
                break
        return kept, used_tokens
    else:
        # Knowledge: sort by score descending, keep highest-value blocks
        sorted_blocks = sorted(blocks, key=lambda b: b.score, reverse=True)
        kept = []
        used_tokens = 0
        for block in sorted_blocks:
            block_tokens = estimate_tokens(block.content)
            if used_tokens + block_tokens <= max_tokens:
                kept.append(block)
                used_tokens += block_tokens
            else:
                remaining = max_tokens - used_tokens
                if remaining >= 20:
                    truncated_chars = remaining * _CHARS_PER_TOKEN
                    truncated_content = block.content[:truncated_chars].rsplit(" ", 1)[0] + "..."
                    truncated_block = ContextBlock(
                        content=truncated_content,
                        score=block.score,
                        source=block.source,
                        chunk_type=block.chunk_type,
                        token_count=remaining,
                    )
                    kept.append(truncated_block)
                    used_tokens += remaining
                break
        return kept, used_tokens


def enforce_group_budgets(result: ContextResult, total_budget: int) -> ContextResult:
    """
    Enforce per-group token budgets and the overall total budget.

    Priority: intent > conversation > knowledge

    CRITICAL: Conversation blocks use preserve_order=True to maintain
    chronological thread order for the LLM.

    Args:
        result:       ContextResult with all blocks.
        total_budget: Max total tokens across all groups.

    Returns:
        ContextResult with trimmed blocks and updated tokens_estimate.
    """
    # Per-group caps
    intent_max = min(_MAX_INTENT_TOKENS, total_budget // 4)
    conv_max   = min(_MAX_CONVERSATION_TOKENS, total_budget // 2)
    know_max   = min(_MAX_KNOWLEDGE_TOKENS, total_budget // 2)

    # Trim each group — conversation preserves order
    result.intent_blocks,       intent_tokens = trim_to_budget(result.intent_blocks,       intent_max, preserve_order=False)
    result.conversation_blocks, conv_tokens   = trim_to_budget(result.conversation_blocks, conv_max,   preserve_order=True)
    result.knowledge_blocks,    know_tokens   = trim_to_budget(result.knowledge_blocks,    know_max,   preserve_order=False)

    total_used = intent_tokens + conv_tokens + know_tokens

    # If still over budget, trim knowledge first (never trim conversation)
    if total_used > total_budget:
        overflow = total_used - total_budget
        if know_tokens > 0:
            new_know_max = max(0, know_max - overflow)
            result.knowledge_blocks, know_tokens = trim_to_budget(result.knowledge_blocks, new_know_max, preserve_order=False)
            total_used = intent_tokens + conv_tokens + know_tokens

    result.tokens_estimate = total_used
    return result


def blocks_to_text(blocks: List[ContextBlock], separator: str = "\n") -> str:
    """Join ContextBlock contents into a single string, preserving order."""
    return separator.join(b.content for b in blocks if b.content.strip())
