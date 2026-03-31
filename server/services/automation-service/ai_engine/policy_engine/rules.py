"""
Policy Engine — Rules
======================
Rule definitions for the PolicyEvaluator.

Design:
  - Rules are pure data — no logic here.
  - Evaluation logic lives in decision_tree.py.
  - Rules are priority-ordered: lower number = evaluated first.
  - First matching rule wins (short-circuit evaluation).
  - Rules are grouped into named layers for traceability.

Layers (in evaluation order):
  LAYER_1_HARD      — account-level hard blocks (automation off, daily limit)
  LAYER_2_SAFETY    — risk-based safety gates (legal, threats, PII, abuse)
  LAYER_3_NOISE     — noise filtering (spam, OOO, unsubscribe)
  LAYER_4_BUSINESS  — intent-based business routing
  LAYER_5_CONFIDENCE — confidence-threshold overrides
  LAYER_6_DEFAULT   — catch-all allow
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ..schemas.intent_schema import IntentType, RiskFlag, SentimentType


class PolicyAction(str, Enum):
    ALLOW        = "allow"         # Full AI processing
    REJECT       = "reject"        # Block — no response, mark as handled
    SAFE_MODE    = "safe_mode"     # AI allowed with strict constraints
    HUMAN_REVIEW = "human_review"  # Escalate to human agent
    SKIP         = "skip"          # No response needed (casual, irrelevant)


class RuleLayer(str, Enum):
    HARD       = "LAYER_1_HARD"
    SAFETY     = "LAYER_2_SAFETY"
    NOISE      = "LAYER_3_NOISE"
    BUSINESS   = "LAYER_4_BUSINESS"
    CONFIDENCE = "LAYER_5_CONFIDENCE"
    DEFAULT    = "LAYER_6_DEFAULT"


@dataclass
class PolicyRule:
    """
    A single evaluatable policy rule.
    All specified conditions must match (AND logic).
    """
    rule_id:     str
    description: str
    priority:    int           # Lower = evaluated first
    action:      PolicyAction
    layer:       RuleLayer

    # ── Condition fields ──────────────────────────────────────────────────
    # Account-level
    automation_must_be_disabled: bool = False   # Fires when automation is OFF
    daily_limit_exceeded:        bool = False   # Fires when sent >= limit

    # Intent matching
    blocked_intents:   List[IntentType]   = field(default_factory=list)
    required_intents:  List[IntentType]   = field(default_factory=list)   # ANY of these

    # Risk flag matching (ANY of these flags must be present)
    required_risk_flags: List[RiskFlag]   = field(default_factory=list)

    # Sentiment matching
    blocked_sentiments: List[SentimentType] = field(default_factory=list)

    # Confidence thresholds
    confidence_below: Optional[float] = None   # Fires when final_score < this
    confidence_above: Optional[float] = None   # Fires when final_score >= this

    # Mixed intent
    requires_secondary_intents: bool = False   # Fires when secondary_intents is non-empty

    # Spam confidence guard (spam only fires above this threshold)
    spam_confidence_min: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT RULE SET
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_RULES: List[PolicyRule] = [

    # ── LAYER 1: HARD BLOCKS ──────────────────────────────────────────────────

    PolicyRule(
        rule_id="RULE_001",
        description="Block all replies when automation is disabled on the account.",
        priority=1,
        action=PolicyAction.REJECT,
        layer=RuleLayer.HARD,
        automation_must_be_disabled=True,
    ),
    PolicyRule(
        rule_id="RULE_002",
        description="Reject when daily send limit is exceeded.",
        priority=2,
        action=PolicyAction.REJECT,
        layer=RuleLayer.HARD,
        daily_limit_exceeded=True,
    ),

    # ── LAYER 2: SAFETY GATES ─────────────────────────────────────────────────

    PolicyRule(
        rule_id="RULE_010",
        description="Escalate to human on legal language or direct threats.",
        priority=10,
        action=PolicyAction.HUMAN_REVIEW,
        layer=RuleLayer.SAFETY,
        required_risk_flags=[RiskFlag.LEGAL_LANGUAGE],
    ),
    PolicyRule(
        rule_id="RULE_011",
        description="Escalate to human on explicit threat language.",
        priority=11,
        action=PolicyAction.HUMAN_REVIEW,
        layer=RuleLayer.SAFETY,
        required_risk_flags=[RiskFlag.THREAT],
    ),
    PolicyRule(
        rule_id="RULE_012",
        description="Safe mode when PII is detected in the message.",
        priority=12,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.SAFETY,
        required_risk_flags=[RiskFlag.SENSITIVE_DATA_PII],
    ),
    PolicyRule(
        rule_id="RULE_013",
        description="Safe mode for abusive language — respond calmly, do not reject.",
        priority=13,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.SAFETY,
        required_risk_flags=[RiskFlag.ABUSE_PATTERN],
    ),
    PolicyRule(
        rule_id="RULE_014",
        description="Safe mode for abusive sentiment — respond calmly.",
        priority=14,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.SAFETY,
        blocked_sentiments=[SentimentType.ABUSIVE],
    ),

    # ── LAYER 3: NOISE FILTERING ──────────────────────────────────────────────

    PolicyRule(
        rule_id="RULE_020",
        description="Reject confirmed spam (confidence > 0.90 required).",
        priority=20,
        action=PolicyAction.REJECT,
        layer=RuleLayer.NOISE,
        blocked_intents=[IntentType.SPAM],
        spam_confidence_min=0.90,
    ),
    PolicyRule(
        rule_id="RULE_021",
        description="Reject promotional emails not related to an active conversation.",
        priority=21,
        action=PolicyAction.REJECT,
        layer=RuleLayer.NOISE,
        blocked_intents=[IntentType.PROMO],
    ),
    PolicyRule(
        rule_id="RULE_022",
        description="Send a single polite opt-out acknowledgement then stop — legal compliance.",
        priority=22,
        action=PolicyAction.SAFE_MODE,   # SAFE_MODE so LLM sends one final polite reply
        layer=RuleLayer.NOISE,
        blocked_intents=[IntentType.UNSUBSCRIBE],
    ),
    PolicyRule(
        rule_id="RULE_023",
        description="Skip out-of-office auto-replies — no response needed.",
        priority=23,
        action=PolicyAction.SKIP,
        layer=RuleLayer.NOISE,
        blocked_intents=[IntentType.OUT_OF_OFFICE],
    ),

    # ── LAYER 4: BUSINESS LOGIC ───────────────────────────────────────────────

    PolicyRule(
        rule_id="RULE_030",
        description="Allow genuine questions — high-value lead signal.",
        priority=30,
        action=PolicyAction.ALLOW,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.QUESTION],
        confidence_above=0.60,
    ),
    PolicyRule(
        rule_id="RULE_031",
        description="Allow interest signals — high-value lead signal.",
        priority=31,
        action=PolicyAction.ALLOW,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.INTEREST],
        confidence_above=0.60,
    ),
    PolicyRule(
        rule_id="RULE_032",
        description="Allow negotiation — active deal signal.",
        priority=32,
        action=PolicyAction.ALLOW,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.NEGOTIATION],
        confidence_above=0.60,
    ),
    PolicyRule(
        rule_id="RULE_033",
        description="Allow follow-up messages.",
        priority=33,
        action=PolicyAction.ALLOW,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.FOLLOW_UP],
        confidence_above=0.60,
    ),
    PolicyRule(
        rule_id="RULE_034",
        description="Safe mode for objections — respond carefully, no assumptions.",
        priority=34,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.OBJECTION],
    ),
    PolicyRule(
        rule_id="RULE_035",
        description="Safe mode for complaints — respond calmly, no commitments.",
        priority=35,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.COMPLAINT],
    ),
    PolicyRule(
        rule_id="RULE_036",
        description="Allow support requests — customer needs help.",
        priority=36,
        action=PolicyAction.ALLOW,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.SUPPORT_REQUEST],
        confidence_above=0.55,
    ),
    PolicyRule(
        rule_id="RULE_037",
        description="Skip pure casual chat with no secondary intents — no business value.",
        priority=37,
        action=PolicyAction.SKIP,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.REPLY],
        confidence_above=0.80,   # Raised from 0.70 — only skip when very confident it's pure casual
    ),
    PolicyRule(
        rule_id="RULE_038",
        description="Safe mode for mixed-intent messages — multiple signals detected.",
        priority=38,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.BUSINESS,
        requires_secondary_intents=True,
    ),
    PolicyRule(
        rule_id="RULE_039",
        description="Safe mode for not-interested — acknowledge politely.",
        priority=39,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.BUSINESS,
        required_intents=[IntentType.NOT_INTERESTED],
    ),

    # ── LAYER 5: CONFIDENCE OVERRIDES ────────────────────────────────────────

    PolicyRule(
        rule_id="RULE_050",
        description="Skip very low confidence messages — unreliable classification.",
        priority=50,
        action=PolicyAction.SKIP,
        layer=RuleLayer.CONFIDENCE,
        confidence_below=0.30,   # Lowered from 0.40 — only skip truly unreliable signals
    ),
    PolicyRule(
        rule_id="RULE_051",
        description="Safe mode for low confidence — constrained AI response, not rejection.",
        priority=51,
        action=PolicyAction.SAFE_MODE,   # Changed from HUMAN_REVIEW — still reply, just constrained
        layer=RuleLayer.CONFIDENCE,
        confidence_below=0.60,
    ),
    PolicyRule(
        rule_id="RULE_052",
        description="Safe mode for medium confidence — constrained AI response.",
        priority=52,
        action=PolicyAction.SAFE_MODE,
        layer=RuleLayer.CONFIDENCE,
        confidence_below=0.85,
    ),

    # ── LAYER 6: DEFAULT ──────────────────────────────────────────────────────

    PolicyRule(
        rule_id="RULE_099",
        description="Default allow — all other cases proceed with full AI processing.",
        priority=99,
        action=PolicyAction.ALLOW,
        layer=RuleLayer.DEFAULT,
    ),
]
