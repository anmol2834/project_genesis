"""
Intent Engine - Classifier
===========================
Hybrid classification pipeline:
  1. Rule Engine   - keyword/regex signals     (rule_score)
  2. Zero-shot NLI - DistilRoBERTa MNLI        (model_score)
  3. Semantic      - MiniLM cosine similarity  (similarity_score)
  4. Fusion        - weighted average          (final confidence)

Fusion: confidence = (model_score * 0.5) + (semantic * 0.3) + (rule_score * 0.2)
Spam guard: SPAM only when fused confidence > 0.90 AND all signals agree.
Abuse: classified as COMPLAINT + risk_flag, never rejected at this layer.
"""
from __future__ import annotations

import asyncio
import logging
import os
import warnings
from typing import Dict, List, Optional

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings("ignore", category=UserWarning)

from transformers import pipeline as hf_pipeline

from ..preprocess.processor import PreprocessedInput
from ..schemas.intent_schema import (
    IntentResult, IntentType, SubIntent, SentimentType, LanguageType, RiskFlag,
)
from .schema import IntentEngineContext, ModelSignal, SemanticSignal, FusedSignals
from .rules import RuleEngine
from .utils import extract_plain_text, truncate_history, embed, best_match, get_anchor_vectors

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zero-shot model singleton
# ---------------------------------------------------------------------------
_ZS_MODEL_NAME = "cross-encoder/nli-distilroberta-base"
_zs_classifier = None


def get_zero_shot_classifier():
    """Load once per process, reuse forever."""
    global _zs_classifier
    if _zs_classifier is None:
        logger.info("Loading zero-shot classifier: %s", _ZS_MODEL_NAME)
        _zs_classifier = hf_pipeline(
            "zero-shot-classification",
            model=_ZS_MODEL_NAME,
            device=-1,
        )
        logger.info("Zero-shot classifier ready.")
    return _zs_classifier


# ---------------------------------------------------------------------------
# Label mappings
# ---------------------------------------------------------------------------
_ZS_LABELS: List[str] = [
    "asking about the business or products",
    "requesting information or details",
    "pricing question or cost inquiry",
    "interested in the product or service",
    "not interested or declining",
    "complaint or problem with service",
    "support request or technical help",
    "spam or promotional email",
    "unsubscribe request",
    "casual greeting or conversation",
    "objection or concern about the offer",
    "follow up on previous conversation",
]

_LABEL_TO_INTENT: Dict[str, IntentType] = {
    "asking about the business or products":  IntentType.QUESTION,
    "requesting information or details":       IntentType.QUESTION,
    "pricing question or cost inquiry":        IntentType.QUESTION,
    "interested in the product or service":    IntentType.INTEREST,
    "not interested or declining":             IntentType.NOT_INTERESTED,
    "complaint or problem with service":       IntentType.COMPLAINT,
    "support request or technical help":       IntentType.SUPPORT_REQUEST,
    "spam or promotional email":               IntentType.SPAM,
    "unsubscribe request":                     IntentType.UNSUBSCRIBE,
    "casual greeting or conversation":         IntentType.REPLY,
    "objection or concern about the offer":    IntentType.OBJECTION,
    "follow up on previous conversation":      IntentType.FOLLOW_UP,
}

_ANCHOR_LABEL_MAP: Dict[str, IntentType] = {
    "question":        IntentType.QUESTION,
    "interest":        IntentType.INTEREST,
    "not_interested":  IntentType.NOT_INTERESTED,
    "negotiation":     IntentType.NEGOTIATION,
    "objection":       IntentType.OBJECTION,
    "reply":           IntentType.REPLY,
    "follow_up":       IntentType.FOLLOW_UP,
    "support_request": IntentType.SUPPORT_REQUEST,
    "complaint":       IntentType.COMPLAINT,
    "spam":            IntentType.SPAM,
    "promo":           IntentType.PROMO,
    "abuse":           IntentType.COMPLAINT,
    "unsubscribe":     IntentType.UNSUBSCRIBE,
    "out_of_office":   IntentType.OUT_OF_OFFICE,
    "unknown":         IntentType.UNKNOWN,
}

_DEFAULT_SUBINTENT: Dict[IntentType, SubIntent] = {
    IntentType.QUESTION:        SubIntent.GENERAL_QUESTION,
    IntentType.INTEREST:        SubIntent.NONE,
    IntentType.NOT_INTERESTED:  SubIntent.NONE,
    IntentType.COMPLAINT:       SubIntent.NONE,
    IntentType.SUPPORT_REQUEST: SubIntent.TECHNICAL_ISSUE,
    IntentType.SPAM:            SubIntent.NONE,
    IntentType.UNSUBSCRIBE:     SubIntent.UNSUBSCRIBE,
    IntentType.REPLY:           SubIntent.CASUAL_CHAT,
    IntentType.OBJECTION:       SubIntent.NONE,
    IntentType.FOLLOW_UP:       SubIntent.FOLLOW_UP,
    IntentType.NEGOTIATION:     SubIntent.NONE,
    IntentType.PROMO:           SubIntent.NONE,
    IntentType.ABUSE:           SubIntent.NONE,
    IntentType.OUT_OF_OFFICE:   SubIntent.NONE,
    IntentType.UNKNOWN:         SubIntent.NONE,
}


# ---------------------------------------------------------------------------
# Main classifier class
# ---------------------------------------------------------------------------
class IntentClassifier:
    """
    Hybrid intent classifier. Singleton-safe — models load on first classify() call.
    Pluggable: swap zero-shot model or rule engine without changing the interface.
    """

    def __init__(self) -> None:
        self._rule_engine = RuleEngine()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def classify(self, preprocessed: PreprocessedInput) -> IntentResult:
        """
        Run the full hybrid pipeline and return a strict IntentResult.

        Args:
            preprocessed: Output from the Preprocess layer.

        Returns:
            IntentResult - no extra fields, confidence in [0, 1].
        """
        ctx = self._build_context(preprocessed)

        # Run all three signal sources concurrently
        rule_signal, model_signal, semantic_signal = await asyncio.gather(
            asyncio.coroutine(lambda: self._rule_engine.evaluate(
                ctx.clean_content, ctx.subject
            ))() if False else self._sync_rules(ctx),
            self._run_zero_shot(ctx.combined_text),
            self._run_semantic(ctx.combined_text),
        )

        fused      = self._fuse(model_signal, semantic_signal, rule_signal)
        intent     = self._resolve_intent(fused)
        sub_intent = self._resolve_sub_intent(intent, rule_signal)
        sentiment  = self._resolve_sentiment(fused, rule_signal, intent)
        language   = rule_signal.language_type
        risk_flags = rule_signal.risk_flags.to_risk_flag_list()
        secondary  = self._detect_secondary_intents(fused, intent)
        reasoning  = self._build_reasoning(fused, intent, rule_signal)

        return IntentResult(
            intent=intent,
            sub_intent=sub_intent,
            sentiment=sentiment,
            language_type=language,
            confidence=round(fused.fused_confidence, 4),
            risk_flags=risk_flags,
            secondary_intents=secondary,
            reasoning=reasoning,
        )

    async def _sync_rules(self, ctx: IntentEngineContext):
        """Wrap synchronous rule engine in a coroutine."""
        return self._rule_engine.evaluate(ctx.clean_content, ctx.subject)

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------
    def _build_context(self, preprocessed: PreprocessedInput) -> IntentEngineContext:
        """
        Build classification context.
        Uses: incoming message + subject + last 3 INCOMING messages only.
        Ignores outgoing messages to avoid self-anchoring bias.
        """
        incoming_history = [
            m.clean_content for m in preprocessed.clean_history
            if m.direction == "incoming"
        ]
        history_snippet = truncate_history(incoming_history, max_messages=3)

        return IntentEngineContext(
            clean_content=preprocessed.clean_incoming_content,
            subject=preprocessed.subject or "",
            conversation_history_snippet=history_snippet,
            existing_intent=None,
        )

    # ------------------------------------------------------------------
    # Zero-shot NLI signal
    # ------------------------------------------------------------------
    async def _run_zero_shot(self, text: str) -> ModelSignal:
        """
        Run DistilRoBERTa zero-shot classification.
        Offloaded to thread pool - keeps event loop non-blocking.
        """
        if not text.strip():
            return ModelSignal(intent=IntentType.UNKNOWN, model_score=0.0, all_scores={})

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: get_zero_shot_classifier()(
                text[:512],
                candidate_labels=_ZS_LABELS,
                multi_label=True,
            )
        )

        all_scores: Dict[str, float] = dict(zip(result["labels"], result["scores"]))
        top_label  = result["labels"][0]
        top_score  = float(result["scores"][0])
        top_intent = _LABEL_TO_INTENT.get(top_label, IntentType.UNKNOWN)

        return ModelSignal(intent=top_intent, model_score=top_score, all_scores=all_scores)

    # ------------------------------------------------------------------
    # Semantic similarity signal
    # ------------------------------------------------------------------
    async def _run_semantic(self, text: str) -> SemanticSignal:
        """
        Compute cosine similarity between message embedding and intent anchors.
        Uses pre-computed anchor vectors (cached after first call).
        """
        if not text.strip():
            return SemanticSignal(
                best_intent=IntentType.UNKNOWN, similarity_score=0.0, all_similarities={}
            )

        loop = asyncio.get_event_loop()
        plain     = extract_plain_text(text)
        query_vec = await loop.run_in_executor(None, lambda: embed(plain))
        anchors   = await loop.run_in_executor(None, get_anchor_vectors)

        best_label, best_score, all_scores = best_match(query_vec, anchors)
        best_intent = _ANCHOR_LABEL_MAP.get(best_label, IntentType.UNKNOWN)

        return SemanticSignal(
            best_intent=best_intent,
            similarity_score=float(best_score),
            all_similarities={
                _ANCHOR_LABEL_MAP.get(k, IntentType.UNKNOWN).value: v
                for k, v in all_scores.items()
            },
        )

    # ------------------------------------------------------------------
    # Signal fusion
    # ------------------------------------------------------------------
    def _fuse(self, model: ModelSignal, semantic: SemanticSignal, rule) -> FusedSignals:
        """Weighted fusion: model*0.5 + semantic*0.3 + rule*0.2"""
        fused_confidence = (
            (model.model_score         * 0.5) +
            (semantic.similarity_score * 0.3) +
            (rule.rule_score           * 0.2)
        )
        return FusedSignals(
            model=model,
            semantic=semantic,
            rule=rule,
            fused_confidence=round(min(1.0, max(0.0, fused_confidence)), 4),
        )

    # ------------------------------------------------------------------
    # Intent resolution
    # ------------------------------------------------------------------
    def _resolve_intent(self, fused: FusedSignals) -> IntentType:
        """
        Determine final intent from fused signals.

        Priority:
          1. High-confidence rule overrides (OOO, mixed-intent rescue)
          2. Spam guard - requires confidence > 0.90 AND all signals agree
          3. Abuse always maps to COMPLAINT
          4. Model signal (primary when score >= 0.60)
          5. Rule hint tiebreaker
          6. Semantic fallback
        """
        rule_hint    = fused.rule.intent_hint
        model_intent = fused.model.intent
        sem_intent   = fused.semantic.best_intent
        confidence   = fused.fused_confidence

        # Out-of-office: high-confidence rule wins
        if rule_hint == IntentType.OUT_OF_OFFICE and fused.rule.rule_score >= 0.85:
            return IntentType.OUT_OF_OFFICE

        # Mixed intent rescue: unsubscribe + pricing/interest -> INTEREST
        if rule_hint == IntentType.INTEREST and fused.rule.rule_score >= 0.60:
            return IntentType.INTEREST

        # Spam guard: NEVER spam unless confidence > 0.90 AND semantic agrees
        if model_intent == IntentType.SPAM or rule_hint == IntentType.SPAM:
            if confidence > 0.90 and sem_intent == IntentType.SPAM:
                return IntentType.SPAM
            return IntentType.PROMO  # Downgrade - less aggressive

        # Abuse -> COMPLAINT (abuse is a risk flag, not a rejection intent)
        if fused.rule.risk_flags.contains_abuse:
            return IntentType.COMPLAINT

        # Model is primary when confident
        if fused.model.model_score >= 0.60:
            return model_intent

        # Rule hint tiebreaker
        if rule_hint is not None and fused.rule.rule_score >= 0.55:
            return rule_hint

        # Semantic fallback
        if fused.semantic.similarity_score >= 0.45:
            return sem_intent

        # Low confidence fallback — default to QUESTION rather than UNKNOWN
        # "I wanna know your business" type messages should always get a reply
        if fused.fused_confidence < 0.60:
            logger.info(
                "Low confidence (%.3f) — falling back to QUESTION intent",
                fused.fused_confidence,
            )
            return IntentType.QUESTION

        return IntentType.UNKNOWN

    # ------------------------------------------------------------------
    # Sub-intent, sentiment, secondary intents
    # ------------------------------------------------------------------
    def _resolve_sub_intent(self, intent: IntentType, rule) -> SubIntent:
        """Rule hints carry specific keyword signals - take priority over defaults."""
        if rule.sub_intent_hint is not None:
            return rule.sub_intent_hint
        return _DEFAULT_SUBINTENT.get(intent, SubIntent.NONE)

    def _resolve_sentiment(self, fused: FusedSignals, rule, intent: IntentType) -> SentimentType:
        """Rule-based sentiment is reliable for clear cases. Falls back to intent inference."""
        if rule.sentiment_hint is not None:
            return rule.sentiment_hint
        if intent in (IntentType.COMPLAINT, IntentType.ABUSE):
            return SentimentType.NEGATIVE
        if intent == IntentType.INTEREST:
            return SentimentType.POSITIVE
        if intent in (IntentType.SPAM, IntentType.PROMO, IntentType.UNSUBSCRIBE):
            return SentimentType.NEUTRAL
        return SentimentType.NEUTRAL

    def _detect_secondary_intents(self, fused: FusedSignals, primary: IntentType) -> List[IntentType]:
        """Collect model labels scoring > 0.40 that differ from primary intent."""
        secondary: List[IntentType] = []
        for label, score in fused.model.all_scores.items():
            if score < 0.40:
                continue
            mapped = _LABEL_TO_INTENT.get(label, IntentType.UNKNOWN)
            if mapped != primary and mapped != IntentType.UNKNOWN:
                secondary.append(mapped)
        return secondary[:3]

    def _build_reasoning(self, fused: FusedSignals, intent: IntentType, rule) -> str:
        """Short audit trail for logging and debugging."""
        rule_hint_val = rule.intent_hint.value if rule.intent_hint else "none"
        patterns = ",".join(rule.matched_patterns[:4]) if rule.matched_patterns else "none"
        return (
            f"intent={intent.value} | "
            f"model={fused.model.intent.value}({fused.model.model_score:.2f}) | "
            f"semantic={fused.semantic.best_intent.value}({fused.semantic.similarity_score:.2f}) | "
            f"rule={rule_hint_val}({rule.rule_score:.2f}) | "
            f"fused={fused.fused_confidence:.3f} | "
            f"patterns=[{patterns}]"
        )
