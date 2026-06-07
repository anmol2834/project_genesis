"""
Priority Classifier
=====================
Classifies every incoming request into P0/P1/P2/P3 immediately after
the intelligence layer, using:

  - Primary intent type
  - Conversation sentiment + urgency
  - Message content keyword signals
  - Escalation history from memory
  - Pre-existing event priority

P0 — CRITICAL  → legal threats, compliance, security incidents, fraud, data breach
P1 — HIGH      → refunds, angry customers, VIP, contract issues, SLA breaches
P2 — MEDIUM    → sales, support, technical questions, onboarding
P3 — LOW       → general inquiry, greetings, small follow-ups

P0 requests:
  - Force immediate human escalation (HandoffOrchestrator respects this)
  - Skip slow queue path in WorkerRuntime
  - Full retrieval budget regardless of cache

P3 requests:
  - Aggressive cache-first retrieval (L1/L2 only unless cache miss)
  - Minimal expensive operations
  - Low escalation bias

The classifier is stateless and synchronous (<1ms).
It does NOT call OpenAI or Redis.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.tenant_context import Priority

logger = logging.getLogger("automation-service.priority")

# ─────────────────────────────────────────────────────────────────────────────
# Signal dictionaries
# ─────────────────────────────────────────────────────────────────────────────

# Intent type → base priority
_INTENT_PRIORITY: Dict[str, int] = {
    # P0
    "legal_issue":           Priority.P0_CRITICAL,
    "compliance_violation":  Priority.P0_CRITICAL,
    "fraud":                 Priority.P0_CRITICAL,
    "data_breach":           Priority.P0_CRITICAL,
    # P1
    "refund_request":        Priority.P1_HIGH,
    "billing_inquiry":       Priority.P1_HIGH,
    "account_issue":         Priority.P1_HIGH,
    "complaint":             Priority.P1_HIGH,
    "partnership_inquiry":   Priority.P1_HIGH,
    # P2
    "pricing_inquiry":       Priority.P2_MEDIUM,
    "product_inquiry":       Priority.P2_MEDIUM,
    "support_request":       Priority.P2_MEDIUM,
    "technical_support_request": Priority.P2_MEDIUM,
    "technical_assistance":  Priority.P2_MEDIUM,
    "technical_question":    Priority.P2_MEDIUM,
    "feature_request":       Priority.P2_MEDIUM,
    "customization_request": Priority.P2_MEDIUM,
    "bulk_purchase":         Priority.P2_MEDIUM,
    "onboarding":            Priority.P2_MEDIUM,
    # P3
    "follow_up":             Priority.P3_LOW,
    "greeting":              Priority.P3_LOW,
    "general_inquiry":       Priority.P3_LOW,
    "unknown":               Priority.P3_LOW,
}

# Keyword patterns that upgrade priority regardless of intent
# Each tuple: (regex, priority_level, reason)
_KEYWORD_SIGNALS: List[Tuple[re.Pattern, int, str]] = [
    # P0 — legal / regulatory / security (includes conjugated forms: suing, sued, sues)
    (re.compile(r"\b(lawsuit|sue[sd]?|suing|legal action|attorney|solicitor|court|litigation|fraud|regulatory|compliance|gdpr|data breach|hack|stolen data)\b", re.I), Priority.P0_CRITICAL, "legal_keyword"),
    # P1 — financial disputes / urgency
    (re.compile(r"\b(refund|chargeback|dispute|cancel.*subscription|cancel.*contract|SLA|breach|angry|furious|unacceptable|worst|terrible|never.again|vip|priority.customer|escalate)\b", re.I), Priority.P1_HIGH, "high_urgency_keyword"),
    # P1 — strong negative emotional signals
    (re.compile(r"\b(disgusted|outraged|incompetent|rubbish|scam|fraud|lied|mislead|false advertising)\b", re.I), Priority.P1_HIGH, "negative_emotional_signal"),
]

# Sentiment → priority floor
_SENTIMENT_FLOOR: Dict[str, int] = {
    "angry":      Priority.P1_HIGH,
    "frustrated": Priority.P1_HIGH,
    "urgent":     Priority.P1_HIGH,
    "negative":   Priority.P2_MEDIUM,
    "neutral":    Priority.P2_MEDIUM,
    "positive":   Priority.P3_LOW,
}

# Urgency → priority floor
_URGENCY_FLOOR: Dict[str, int] = {
    "critical": Priority.P0_CRITICAL,
    "high":     Priority.P1_HIGH,
    "medium":   Priority.P2_MEDIUM,
    "low":      Priority.P3_LOW,
}


# ─────────────────────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────────────────────

class PriorityResult:
    __slots__ = ("priority", "reason", "signals", "escalate_immediately")

    def __init__(self, priority: int, reason: str, signals: List[str]):
        self.priority           = priority
        self.reason             = reason
        self.signals            = signals
        self.escalate_immediately = (priority == Priority.P0_CRITICAL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority":             Priority.label(self.priority),
            "priority_int":         self.priority,
            "priority_reason":      self.reason,
            "priority_signals":     self.signals,
            "escalate_immediately": self.escalate_immediately,
        }

    @property
    def priority_label(self) -> str:
        """Human-readable priority label: 'p0_critical', 'p1_high', etc."""
        return Priority.label(self.priority)


# ─────────────────────────────────────────────────────────────────────────────
# PriorityClassifier
# ─────────────────────────────────────────────────────────────────────────────

class PriorityClassifier:
    """
    Stateless, synchronous priority classifier.
    Returns PriorityResult in <1ms.

    Evaluation order (first signal wins at escalation, lowest integer wins overall):
      1. Keyword scan of message content
      2. Intelligence urgency field
      3. Intelligence sentiment field
      4. Primary intent type
      5. Escalation history from memory (previous P0/P1 escalations)
      6. Existing event priority (from emailservice)
    """

    def classify(
        self,
        message_content: str,
        intelligence: Any,
        memory: Dict[str, Any],
        event_priority: int = Priority.P2_MEDIUM,
    ) -> PriorityResult:
        """
        Classify request priority.

        Args:
            message_content:  Raw customer message
            intelligence:     EnterpriseIntelligenceResult (dict or dataclass)
            memory:           Memory dict from MemoryOrchestrator
            event_priority:   Priority already set by emailservice (0-3 or 0-10)

        Returns:
            PriorityResult
        """
        candidate = Priority.P3_LOW   # start at lowest
        signals:  List[str] = []

        # ── 1. Keyword scan (highest-weight signal) ───────────────────────
        for pattern, level, reason in _KEYWORD_SIGNALS:
            if pattern.search(message_content):
                if level < candidate:
                    candidate = level
                    signals.append(reason)
                    if candidate == Priority.P0_CRITICAL:
                        break   # can't go higher, short-circuit

        # ── 2. Intelligence urgency ───────────────────────────────────────
        urgency_raw = _get_nested(intelligence, "conversation_analysis", "urgency") or "medium"
        # Extract bare string from enum (Urgency.LOW → "low") or use string directly
        urgency_str = (
            urgency_raw.value if hasattr(urgency_raw, "value")
            else str(urgency_raw).split(".")[-1].lower()
        )
        urgency_floor = _URGENCY_FLOOR.get(urgency_str, Priority.P2_MEDIUM)
        if urgency_floor < candidate:
            candidate = urgency_floor
            signals.append(f"urgency={urgency_str}")

        # ── 3. Intelligence sentiment ─────────────────────────────────────
        sentiment_raw = _get_nested(intelligence, "conversation_analysis", "sentiment") or "neutral"
        sentiment_str = (
            sentiment_raw.value if hasattr(sentiment_raw, "value")
            else str(sentiment_raw).split(".")[-1].lower()
        )
        sent_floor = _SENTIMENT_FLOOR.get(sentiment_str, Priority.P2_MEDIUM)
        if sent_floor < candidate:
            candidate = sent_floor
            signals.append(f"sentiment={sentiment_str}")

        # ── 4. Primary intent ─────────────────────────────────────────────
        intent = _get_primary_intent(intelligence)
        intent_priority = _INTENT_PRIORITY.get(intent, Priority.P2_MEDIUM)
        if intent_priority < candidate:
            candidate = intent_priority
            signals.append(f"intent={intent}")

        # ── 5. Escalation history from memory ─────────────────────────────
        esc_history = memory.get("escalation_history", [])
        if esc_history:
            # Previous P0/P1 escalations → maintain elevated priority
            prev_reasons = [
                str(e.get("reason", "")).lower()
                if isinstance(e, dict) else ""
                for e in esc_history[:3]
            ]
            if any("legal" in r or "fraud" in r or "security" in r for r in prev_reasons):
                if Priority.P0_CRITICAL < candidate:
                    candidate = Priority.P0_CRITICAL
                    signals.append("escalation_history_critical")
            elif len(esc_history) >= 2:
                # Multiple escalations → at least P1
                if Priority.P1_HIGH < candidate:
                    candidate = Priority.P1_HIGH
                    signals.append("repeated_escalations")

        # ── 6. Event priority from emailservice ───────────────────────────
        # emailservice MessagePriority: CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3
        # Values 0-3 map directly. Values > 3 treated as MEDIUM.
        if isinstance(event_priority, int):
            if event_priority == 0:
                mapped_event_priority = Priority.P0_CRITICAL
            elif event_priority == 1:
                mapped_event_priority = Priority.P1_HIGH
            elif event_priority == 3:
                mapped_event_priority = Priority.P3_LOW
            else:
                # 2 (MEDIUM) or anything else → P2
                mapped_event_priority = Priority.P2_MEDIUM
        else:
            mapped_event_priority = Priority.P2_MEDIUM
        if mapped_event_priority < candidate:
            candidate = mapped_event_priority
            signals.append(f"event_priority={event_priority}")

        reason = signals[0] if signals else "default_medium"

        logger.info(
            "Priority classified | level=%s reason=%s signals=%s",
            Priority.label(candidate), reason, signals,
        )

        return PriorityResult(
            priority=candidate,
            reason=reason,
            signals=signals,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Per-priority retrieval configuration
# ─────────────────────────────────────────────────────────────────────────────

class RetrievalBudget:
    """
    Controls how much retrieval work to perform based on priority.

    P0 — full retrieval + full validation + full observability
    P1 — enhanced (higher top_k, force deep layers if cache misses)
    P2 — standard
    P3 — cache-first, skip expensive layers if L1/L2 hit
    """

    _CONFIGS: Dict[int, Dict[str, Any]] = {
        Priority.P0_CRITICAL: {
            "top_k":                12,
            "force_deep_retrieval": True,
            "skip_if_cache_hit":    False,
            "min_retrieval_layers": 6,   # run at least L1-L6
            "enhanced_grounding":   True,
        },
        Priority.P1_HIGH: {
            "top_k":                10,
            "force_deep_retrieval": True,
            "skip_if_cache_hit":    False,
            "min_retrieval_layers": 4,
            "enhanced_grounding":   True,
        },
        Priority.P2_MEDIUM: {
            "top_k":                8,
            "force_deep_retrieval": False,
            "skip_if_cache_hit":    False,
            "min_retrieval_layers": 2,
            "enhanced_grounding":   False,
        },
        Priority.P3_LOW: {
            "top_k":                5,
            "force_deep_retrieval": False,
            "skip_if_cache_hit":    True,   # accept L1/L2 cache hit, skip deep layers
            "min_retrieval_layers": 1,
            "enhanced_grounding":   False,
        },
    }

    @classmethod
    def for_priority(cls, priority: int) -> Dict[str, Any]:
        return cls._CONFIGS.get(priority, cls._CONFIGS[Priority.P2_MEDIUM])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_nested(obj: Any, *keys: str) -> Any:
    current = obj
    for k in keys:
        if current is None:
            return None
        current = current.get(k) if isinstance(current, dict) else getattr(current, k, None)
    return current


def _get_primary_intent(intelligence: Any) -> str:
    intents = (
        intelligence.get("primary_intents", [])
        if isinstance(intelligence, dict)
        else getattr(intelligence, "primary_intents", [])
    ) or []
    if intents:
        first = intents[0]
        t = first.get("type") if isinstance(first, dict) else getattr(first, "type", None)
        if t is None:
            return "general_inquiry"
        # Extract .value from enum (IntentType.GENERAL_INQUIRY → "general_inquiry")
        # then fall back to splitting on "." for legacy string repr
        if hasattr(t, "value"):
            return str(t.value).lower()
        raw = str(t).lower()
        return raw.split(".")[-1] if "." in raw else raw
    return "general_inquiry"


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_classifier: Optional[PriorityClassifier] = None


def get_priority_classifier() -> PriorityClassifier:
    global _classifier
    if _classifier is None:
        _classifier = PriorityClassifier()
    return _classifier


__all__ = [
    "PriorityClassifier",
    "PriorityResult",
    "RetrievalBudget",
    "Priority",
    "get_priority_classifier",
    # Audit-accessible pattern aliases
    "_P0_PATTERN",
    "_P1_PATTERN",
]

# Pattern aliases for audit/testing discoverability
# The classifier uses _KEYWORD_SIGNALS list — expose compiled patterns by priority level
_P0_PATTERN = _KEYWORD_SIGNALS[0][0]   # legal/regulatory P0 pattern
_P1_PATTERN = _KEYWORD_SIGNALS[1][0]   # refund/urgency P1 pattern
