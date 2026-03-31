"""
Context Builder — Ranker
=========================
Scores and ranks ContextBlocks before the selector trims them.

Scoring formula per block:
  final_score = (similarity * 0.60) + (recency * 0.25) + (type_priority * 0.15)

Where:
  similarity    — Qdrant cosine score or semantic similarity [0, 1]
  recency       — For conversation blocks: newer = higher score
                  For Qdrant blocks: always 1.0 (static knowledge)
  type_priority — Chunk type importance weight (instruction > business_core > tone > ...)

Deduplication:
  Blocks with content overlap > 80% (by token set) are merged — keep highest score.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set

from .schema import ContextBlock, ContextSource

# Chunk type priority weights (higher = more important)
_TYPE_PRIORITY: Dict[str, float] = {
    "instruction":   1.00,
    "business_core": 0.90,
    "tone":          0.75,
    "use_case":      0.70,
    "audience":      0.60,
    "incoming":      0.85,   # Conversation: incoming messages are high priority
    "outgoing":      0.65,   # Conversation: our own replies are lower priority
    "summary":       0.80,
    "unknown":       0.50,
}

_DEDUP_OVERLAP_THRESHOLD = 0.80   # 80% token overlap → consider duplicate


def rank_blocks(blocks: List[ContextBlock], recency_map: Dict[int, float] = None) -> List[ContextBlock]:
    """
    Score and sort ContextBlocks by final relevance score.

    Args:
        blocks:      List of ContextBlocks to rank.
        recency_map: Optional dict mapping block index → recency score [0, 1].
                     If None, recency = 1.0 for all blocks.

    Returns:
        Sorted list (descending by final_score), with score updated in-place.
    """
    if not blocks:
        return []

    for i, block in enumerate(blocks):
        recency = recency_map[i] if recency_map and i in recency_map else 1.0
        type_w  = _TYPE_PRIORITY.get(block.chunk_type, 0.50)

        block.score = round(
            (block.score * 0.60) + (recency * 0.25) + (type_w * 0.15),
            4,
        )

    return sorted(blocks, key=lambda b: b.score, reverse=True)


def deduplicate_blocks(blocks: List[ContextBlock]) -> List[ContextBlock]:
    """
    Remove near-duplicate blocks.
    Two blocks are duplicates if their token sets overlap > 80%.
    Keeps the block with the higher score.
    """
    if len(blocks) <= 1:
        return blocks

    kept: List[ContextBlock] = []
    seen_token_sets: List[Set[str]] = []

    for block in blocks:
        tokens = _tokenize(block.content)
        is_dup = False

        for seen_tokens in seen_token_sets:
            overlap = _jaccard(tokens, seen_tokens)
            if overlap >= _DEDUP_OVERLAP_THRESHOLD:
                is_dup = True
                break

        if not is_dup:
            kept.append(block)
            seen_token_sets.append(tokens)

    return kept


def build_recency_map(blocks: List[ContextBlock]) -> Dict[int, float]:
    """
    Build a recency score map for conversation blocks.
    Most recent message → 1.0, oldest → 0.3.
    Non-conversation blocks → 1.0 (static knowledge, always fresh).
    """
    recency_map: Dict[int, float] = {}
    conv_indices = [
        i for i, b in enumerate(blocks)
        if b.source == ContextSource.CONVERSATION
    ]

    n = len(conv_indices)
    for rank, idx in enumerate(conv_indices):
        # Linear decay: most recent = 1.0, oldest = 0.3
        recency_map[idx] = round(1.0 - (rank / max(n, 1)) * 0.70, 4)

    # Non-conversation blocks get full recency
    for i in range(len(blocks)):
        if i not in recency_map:
            recency_map[i] = 1.0

    return recency_map


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> Set[str]:
    """Simple word tokenizer for overlap comparison."""
    return set(re.findall(r"\b\w+\b", text.lower()))


def _jaccard(a: Set[str], b: Set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0
