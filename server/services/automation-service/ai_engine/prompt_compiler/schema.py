"""
Prompt Compiler — Schema
=========================
Data contracts for the Prompt Compiler layer.

CompiledPrompt — the output sent to the LLM Engine.
PromptMode     — which template variant was used.
PromptMetadata — audit trail for debugging and logging.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class PromptMode(str, Enum):
    """
    Which prompt variant was compiled.
    Determines template selection and constraint injection.
    """
    STANDARD    = "standard"     # Full context, full AI freedom
    SAFE        = "safe_mode"    # Constrained: no assumptions, no pricing
    MINIMAL     = "minimal"      # Very short, acknowledge + handoff only
    ABUSE       = "abuse"        # Calm professional tone, de-escalation
    NO_CONTEXT  = "no_context"   # No knowledge available — force no_response


@dataclass
class PromptMetadata:
    """Audit trail attached to every compiled prompt."""
    mode:              PromptMode
    intent:            str
    sub_intent:        str
    confidence_level:  str          # high / medium / low
    tokens_estimate:   int
    context_sources:   list         # Which sources were used
    constraints_applied: Dict[str, Any] = field(default_factory=dict)
    safe_mode:         bool = False
    has_knowledge:     bool = False
    has_conversation:  bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode":                self.mode.value,
            "intent":              self.intent,
            "sub_intent":          self.sub_intent,
            "confidence_level":    self.confidence_level,
            "tokens_estimate":     self.tokens_estimate,
            "context_sources":     self.context_sources,
            "constraints_applied": self.constraints_applied,
            "safe_mode":           self.safe_mode,
            "has_knowledge":       self.has_knowledge,
            "has_conversation":    self.has_conversation,
        }


@dataclass
class CompiledPrompt:
    """
    Ready-to-send prompt package for the LLM Engine.
    system_prompt → injected as the 'system' role in chat APIs.
    user_prompt   → injected as the 'user' role.
    """
    system_prompt:    str
    user_prompt:      str
    estimated_tokens: int
    is_safe_mode:     bool
    mode:             PromptMode = PromptMode.STANDARD
    metadata:         Optional[PromptMetadata] = None
