"""
Confidence Engine — Context Consistency Scorer
================================================
Computes context_score in [0, 1] by measuring how well the incoming message
fits within the existing conversation thread.

Scoring logic:
  - New thread (no history)         → neutral score (0.65) — can't penalise unknown
  - Continuation of same topic      → high score (0.85–0.95)
  - Partial topic match             → medium score (0.60–0.80)
  - Completely unrelated message    → low score (0.30–0.50)
  - Reply to our outgoing message   → high score (0.90) — expected continuation

Context signals used:
  1. Semantic similarity between incoming message and last conversation message
  2. Intent continuity — does the new intent make sense after the previous one?
  3. Thread depth — longer threads have more context, higher baseline

Input:  IntentResult + PreprocessedInput (conversation history)
Output: float in [0, 1]
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from ..schemas.intent_schema import IntentResult, IntentType
from ..preprocess.processor import PreprocessedInput, CleanMessage
from ..intent_engine.utils import extract_plain_text, embed, cosine_similarity

logger = logging.getLogger(__name__)

# Intent transitions that are naturally consistent (previous → current)
_CONSISTENT_TRANSITIONS = {
    # After we send outreach, these replies make sense
    (IntentType.REPLY,        IntentType.QUESTION),
    (IntentType.REPLY,        IntentType.INTEREST),
    (IntentType.REPLY,        IntentType.NOT_INTERESTED),
    (IntentType.REPLY,        IntentType.OBJECTION),
    (IntentType.REPLY,        IntentType.FOLLOW_UP),
    (IntentType.REPLY,        IntentType.COMPLAINT),
    (IntentType.REPLY,        IntentType.SUPPORT_REQUEST),
    # Natural follow-ups
    (IntentType.QUESTION,     IntentType.FOLLOW_UP),
    (IntentType.QUESTION,     IntentType.INTEREST),
    (IntentType.QUESTION,     IntentType.NEGOTIATION),
    (IntentType.INTEREST,     IntentType.NEGOTIATION),
    (IntentType.INTEREST,     IntentType.QUESTION),
    (IntentType.INTEREST,     IntentType.FOLLOW_UP),
    (IntentType.NEGOTIATION,  IntentType.OBJECTION),
    (IntentType.NEGOTIATION,  IntentType.INTEREST),
    (IntentType.OBJECTION,    IntentType.QUESTION),
    (IntentType.OBJECTION,    IntentType.NOT_INTERESTED),
    (IntentType.COMPLAINT,    IntentType.SUPPORT_REQUEST),
    (IntentType.COMPLAINT,    IntentType.COMPLAINT),
    (IntentType.SUPPORT_REQUEST, IntentType.FOLLOW_UP),
    (IntentType.FOLLOW_UP,    IntentType.INTEREST),
    (IntentType.FOLLOW_UP,    IntentType.QUESTION),
}

# Intents that are always contextually valid regardless of history
_ALWAYS_VALID_INTENTS = {
    IntentType.REPLY,
    IntentType.FOLLOW_UP,
    IntentType.SUPPORT_REQUEST,
    IntentType.COMPLAINT,
    IntentType.OUT_OF_OFFICE,
}

# Baseline score for new threads (no history to compare against)
_NEW_THREAD_BASELINE = 0.65


async def compute_context_score(
    intent_result: IntentResult,
    preprocessed: PreprocessedInput,
) -> float:
    """
    Compute context consistency score.

    Args:
        intent_result: Output from Intent Engine.
        preprocessed:  Cleaned conversation data from Preprocess layer.

    Returns:
        float in [0.0, 1.0]
    """
    history = preprocessed.clean_history

    # ── No history: new thread ────────────────────────────────────────────
    if not history:
        return _NEW_THREAD_BASELINE

    # ── Get last message in thread ────────────────────────────────────────
    last_msg = history[-1]

    # ── Signal 1: Semantic similarity to last message ─────────────────────
    semantic_sim = await _semantic_similarity(
        preprocessed.clean_incoming_content,
        last_msg.clean_content,
    )

    # ── Signal 2: Intent transition consistency ───────────────────────────
    transition_score = _intent_transition_score(
        last_msg=last_msg,
        current_intent=intent_result.intent,
        history=history,
    )

    # ── Signal 3: Thread depth bonus ─────────────────────────────────────
    # Longer threads = more established context = higher baseline
    depth_bonus = min(0.10, len(history) * 0.02)

    # ── Weighted combination ──────────────────────────────────────────────
    # Semantic similarity is the strongest signal
    score = (semantic_sim * 0.55) + (transition_score * 0.35) + (depth_bonus * 0.10)

    # ── Reply-to-outgoing boost ───────────────────────────────────────────
    # If the last message was outgoing (we sent it), this is an expected reply
    if last_msg.direction == "outgoing":
        score = min(1.0, score + 0.10)

    return round(max(0.0, min(1.0, score)), 4)


async def _semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Compute cosine similarity between two message embeddings.
    Returns 0.65 (neutral) if either text is empty.
    """
    if not text_a.strip() or not text_b.strip():
        return 0.65

    loop = asyncio.get_event_loop()
    plain_a = extract_plain_text(text_a)
    plain_b = extract_plain_text(text_b)

    if not plain_a.strip() or not plain_b.strip():
        return 0.65

    vec_a, vec_b = await asyncio.gather(
        loop.run_in_executor(None, lambda: embed(plain_a)),
        loop.run_in_executor(None, lambda: embed(plain_b)),
    )

    raw_sim = cosine_similarity(vec_a, vec_b)

    # Rescale: email replies are rarely > 0.8 cosine sim even when on-topic.
    # Map [0, 0.8] → [0.3, 1.0] to avoid artificially low context scores.
    rescaled = 0.30 + (raw_sim / 0.80) * 0.70
    return round(max(0.0, min(1.0, rescaled)), 4)


def _intent_transition_score(
    last_msg: CleanMessage,
    current_intent: IntentType,
    history: List[CleanMessage],
) -> float:
    """
    Score how naturally the current intent follows from the conversation history.

    Returns:
        float in [0.0, 1.0]
    """
    # Always-valid intents don't need transition checking
    if current_intent in _ALWAYS_VALID_INTENTS:
        return 0.85

    # We can't infer previous intent from CleanMessage alone (no intent field).
    # Use direction as a proxy: outgoing = we replied, incoming = they replied.
    last_direction = last_msg.direction

    if last_direction == "outgoing":
        # We sent the last message — any incoming reply is contextually valid
        return 0.90

    # Last message was also incoming — check if it's a continuation
    # Use thread depth as a proxy: deeper threads are more coherent
    thread_depth = len(history)
    if thread_depth >= 3:
        return 0.80   # Established thread — likely coherent
    elif thread_depth >= 1:
        return 0.70   # Short thread — moderate coherence
    else:
        return 0.65   # Single message — no context
