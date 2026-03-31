"""
Confidence Engine — Scorer
===========================
Computes the FINAL confidence score by fusing four independent signals:

  system_confidence =
    (model_score   * 0.40) +
    (semantic_score * 0.25) +
    (rule_score    * 0.20) +
    (context_score * 0.15)

When LLM confidence is available (post-LLM blend):
  final_confidence = (0.6 * llm_confidence) + (0.4 * system_confidence)

This ensures the LLM's own confidence assessment is the dominant signal,
while system signals provide a safety floor.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..schemas.intent_schema import IntentResult
from ..preprocess.processor import PreprocessedInput
from .schema import ConfidenceScore, ConfidenceLevel, SignalBreakdown
from .rules import compute_rule_score
from .semantic import compute_semantic_score
from .context import compute_context_score

logger = logging.getLogger(__name__)

# ── Pre-LLM fusion weights ────────────────────────────────────────────────────
_W_MODEL    = 0.40
_W_SEMANTIC = 0.25
_W_RULE     = 0.20
_W_CONTEXT  = 0.15

# ── Post-LLM blend weights ────────────────────────────────────────────────────
_W_LLM_CONFIDENCE    = 0.60
_W_SYSTEM_CONFIDENCE = 0.40

# ── Confidence thresholds ─────────────────────────────────────────────────────
_THRESHOLD_HIGH   = 0.85
_THRESHOLD_MEDIUM = 0.60


class ConfidenceScorer:
    """
    Async confidence scorer.
    Fuses model, semantic, rule, and context signals into a single score.
    Supports post-LLM blending when llm_confidence is provided.
    """

    async def score(
        self,
        intent_result: IntentResult,
        preprocessed: Optional[PreprocessedInput] = None,
        llm_confidence: Optional[float] = None,
    ) -> ConfidenceScore:
        """
        Compute the final fused confidence score.

        Args:
            intent_result:   Output from the Intent Engine.
            preprocessed:    Output from the Preprocess layer (optional).
            llm_confidence:  LLM's own confidence (0-1), if available post-LLM.
                             When provided, blended as dominant signal (60%).

        Returns:
            ConfidenceScore with final_score, level, breakdown, and threshold flag.
        """
        message_text = (
            preprocessed.clean_incoming_content
            if preprocessed is not None
            else ""
        )

        # ── Signal 1: Model confidence ────────────────────────────────────
        model_score = _normalise(intent_result.confidence)

        # ── Signal 2: Semantic confidence ─────────────────────────────────
        if message_text.strip():
            semantic_score = await compute_semantic_score(intent_result, message_text)
        else:
            semantic_score = model_score

        # ── Signal 3: Rule-based score ────────────────────────────────────
        rule_score = compute_rule_score(intent_result, message_text)

        # ── Signal 4: Context consistency score ───────────────────────────
        if preprocessed is not None and preprocessed.clean_history:
            context_score = await compute_context_score(intent_result, preprocessed)
        else:
            context_score = 0.65

        # ── System confidence (pre-LLM) ───────────────────────────────────
        system_score = (
            (model_score    * _W_MODEL)    +
            (semantic_score * _W_SEMANTIC) +
            (rule_score     * _W_RULE)     +
            (context_score  * _W_CONTEXT)
        )
        system_score = round(max(0.0, min(1.0, system_score)), 4)

        # ── Blend with LLM confidence if available ────────────────────────
        if llm_confidence is not None:
            llm_norm = _normalise(llm_confidence)
            final = (_W_LLM_CONFIDENCE * llm_norm) + (_W_SYSTEM_CONFIDENCE * system_score)
            final = round(max(0.0, min(1.0, final)), 4)
            logger.debug(
                "Confidence blended | llm=%.3f system=%.3f final=%.3f",
                llm_norm, system_score, final,
            )
        else:
            final = system_score

        level = _bucket(final)

        breakdown = SignalBreakdown(
            model=model_score,
            semantic=semantic_score,
            rule=rule_score,
            context=context_score,
        )

        logger.debug(
            "Confidence scored",
            extra={
                "final": final,
                "level": level.value,
                "breakdown": breakdown.to_dict(),
                "intent": intent_result.intent.value,
                "llm_confidence": llm_confidence,
            },
        )

        return ConfidenceScore(
            final_score=final,
            confidence_level=level,
            breakdown=breakdown,
            is_above_threshold=final >= _THRESHOLD_MEDIUM,
            threshold_used=_THRESHOLD_MEDIUM,
        )


def _normalise(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _bucket(score: float) -> ConfidenceLevel:
    if score >= _THRESHOLD_HIGH:
        return ConfidenceLevel.HIGH
    if score >= _THRESHOLD_MEDIUM:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
