"""
Context Builder — Schema
=========================
Data contracts for the Context Builder layer.

ContextBlock  — a single piece of retrieved/assembled context with score + source
ContextResult — the full output passed to the Prompt Compiler
SelectedContext — the flat struct the Prompt Compiler already expects (kept for compat)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ContextSource(str, Enum):
    """Where a context block came from."""
    CONVERSATION = "conversation"   # last_24h_messages
    QDRANT       = "qdrant"         # vector DB retrieval
    SUMMARY      = "summary"        # message_summary field
    INTENT       = "intent"         # intent-specific knowledge chunk
    FALLBACK     = "fallback"       # default / empty fallback


@dataclass
class ContextBlock:
    """
    A single piece of context with relevance score and provenance.
    Used internally by the selector and ranker before final assembly.
    """
    content:     str
    score:       float           # Relevance score [0, 1]
    source:      ContextSource
    chunk_type:  str = ""        # e.g. "business_core", "tone", "incoming", "outgoing"
    token_count: int = 0         # Estimated tokens (len // 4)

    def __post_init__(self) -> None:
        if self.token_count == 0:
            self.token_count = max(1, len(self.content) // 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content":    self.content,
            "score":      round(self.score, 4),
            "source":     self.source.value,
            "chunk_type": self.chunk_type,
            "tokens":     self.token_count,
        }


@dataclass
class ContextResult:
    """
    Full structured output of the Context Builder.
    Consumed by the Prompt Compiler.
    """
    # Grouped context blocks by category
    conversation_blocks: List[ContextBlock] = field(default_factory=list)
    knowledge_blocks:    List[ContextBlock] = field(default_factory=list)
    intent_blocks:       List[ContextBlock] = field(default_factory=list)

    # Metadata
    tokens_estimate:  int       = 0
    sources_used:     List[str] = field(default_factory=list)
    retrieval_skipped: bool     = False   # True when Qdrant unavailable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_blocks": {
                "conversation": [b.to_dict() for b in self.conversation_blocks],
                "knowledge":    [b.to_dict() for b in self.knowledge_blocks],
                "intent":       [b.to_dict() for b in self.intent_blocks],
            },
            "metadata": {
                "tokens_estimate":  self.tokens_estimate,
                "sources_used":     self.sources_used,
                "retrieval_skipped": self.retrieval_skipped,
            },
        }


@dataclass
class SelectedContext:
    """
    Flat context struct consumed by the Prompt Compiler (PromptBuilder.build).
    Assembled from ContextResult by the ContextSelector.
    Keeps the existing Prompt Compiler interface unchanged.
    """
    # Business knowledge (from Qdrant)
    business_instruction: str = ""
    business_core:        str = ""
    tone_guidance:        str = ""
    use_case_context:     str = ""

    # Conversation history
    conversation_summary:  str = ""   # From message_summary field
    recent_history_text:   str = ""   # Last N clean messages as readable text

    # Token budget tracking
    total_context_tokens: int = 0

    # Full structured result (for audit / downstream use)
    full_result: Optional[ContextResult] = None

    # ── Data availability flags ───────────────────────────────────────────
    # Set by the selector after assembly. Used by the prompt compiler to
    # tell the LLM exactly what data is and isn't available.
    # CRITICAL: prevents hallucination of products/services/pricing.
    has_products:  bool = False   # True if product names found in context
    has_services:  bool = False   # True if service descriptions found in context
    has_pricing:   bool = False   # True if pricing data found in context
    has_use_cases: bool = False   # True if use case context is present
