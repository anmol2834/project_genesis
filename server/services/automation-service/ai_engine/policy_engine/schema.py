"""
Policy Engine — Schema
=======================
Data contracts for the Policy Engine layer.

PolicyDecision is the output consumed by:
  - Orchestrator (routing: early exit vs continue)
  - Prompt Compiler (constraints injected into prompt)
  - Decision Engine Finalizer (maps action to AIEngineOutput status)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .rules import PolicyAction


@dataclass
class PromptConstraints:
    """
    LLM constraints produced by the Policy Engine.
    Injected into the Prompt Compiler to control generation behaviour.
    """
    max_tokens:        int   = 300
    tone:              str   = "professional"
    strict_mode:       bool  = False
    allow_assumptions: bool  = True
    allow_pricing:     bool  = True
    allow_commitments: bool  = True
    require_human_handoff: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_tokens":            self.max_tokens,
            "tone":                  self.tone,
            "strict_mode":           self.strict_mode,
            "allow_assumptions":     self.allow_assumptions,
            "allow_pricing":         self.allow_pricing,
            "allow_commitments":     self.allow_commitments,
            "require_human_handoff": self.require_human_handoff,
        }


# ── Pre-built constraint profiles ─────────────────────────────────────────────

CONSTRAINTS_FULL = PromptConstraints(
    max_tokens=300,
    tone="professional",
    strict_mode=False,
    allow_assumptions=True,
    allow_pricing=True,
    allow_commitments=True,
)

CONSTRAINTS_SAFE = PromptConstraints(
    max_tokens=120,
    tone="calm_professional",
    strict_mode=True,
    allow_assumptions=False,
    allow_pricing=False,
    allow_commitments=False,
)

CONSTRAINTS_MINIMAL = PromptConstraints(
    max_tokens=80,
    tone="neutral",
    strict_mode=True,
    allow_assumptions=False,
    allow_pricing=False,
    allow_commitments=False,
    require_human_handoff=True,
)

CONSTRAINTS_ABUSE = PromptConstraints(
    max_tokens=100,
    tone="calm_professional",
    strict_mode=True,
    allow_assumptions=False,
    allow_pricing=False,
    allow_commitments=False,
)


@dataclass
class PolicyDecision:
    """
    Full output of the Policy Engine.
    Extends the original scaffold with constraints and skip support.
    """
    action:          PolicyAction
    matched_rule_id: str
    reason:          str
    constraints:     PromptConstraints = field(default_factory=lambda: CONSTRAINTS_FULL)

    # Convenience flags consumed by orchestrator and finalizer
    is_safe_mode:    bool = False   # True when action == SAFE_MODE
    requires_human:  bool = False   # True when action == HUMAN_REVIEW

    # Send-blocking flags — pipeline CONTINUES but email is NOT dispatched
    # Set by RULE_001 (automation disabled) and RULE_002 (daily limit exceeded)
    block_send:      bool = False   # True → generate reply but do NOT send

    # Audit trail
    layer_trace:     str  = ""      # Which decision layer fired (HARD/SAFETY/BUSINESS/etc.)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action":          self.action.value,
            "matched_rule_id": self.matched_rule_id,
            "reason":          self.reason,
            "constraints":     self.constraints.to_dict(),
            "is_safe_mode":    self.is_safe_mode,
            "requires_human":  self.requires_human,
            "block_send":      self.block_send,
            "layer_trace":     self.layer_trace,
        }
