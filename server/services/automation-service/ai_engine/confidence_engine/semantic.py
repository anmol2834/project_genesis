"""
Confidence Engine — Semantic Scorer
=====================================
Computes semantic_score in [0, 1] by measuring how well the message embedding
aligns with the classified intent's anchor cluster.

Strategy:
  1. Embed the incoming message using the shared MiniLM singleton (no new model).
  2. Compare against the pre-computed anchor vector for the classified intent.
  3. Also compare against the top-3 anchors and take a weighted average —
     this prevents a single bad anchor from tanking the score.

The semantic score answers: "Does this message actually LOOK like the classified intent?"
High semantic score = the model and the embedding agree → higher overall confidence.
Low semantic score  = the model classified it but the embedding disagrees → lower confidence.

Input:  IntentResult + message text
Output: float in [0, 1]
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from ..schemas.intent_schema import IntentResult, IntentType
from ..intent_engine.utils import (
    extract_plain_text,
    embed,
    cosine_similarity,
    get_anchor_vectors,
)

logger = logging.getLogger(__name__)

# Map IntentType → anchor key in get_anchor_vectors()
_INTENT_TO_ANCHOR: Dict[IntentType, str] = {
    IntentType.QUESTION:        "question",
    IntentType.INTEREST:        "interest",
    IntentType.NOT_INTERESTED:  "not_interested",
    IntentType.NEGOTIATION:     "negotiation",
    IntentType.OBJECTION:       "objection",
    IntentType.REPLY:           "reply",
    IntentType.FOLLOW_UP:       "follow_up",
    IntentType.SUPPORT_REQUEST: "support_request",
    IntentType.COMPLAINT:       "complaint",
    IntentType.SPAM:            "spam",
    IntentType.PROMO:           "promo",
    IntentType.ABUSE:           "abuse",
    IntentType.UNSUBSCRIBE:     "unsubscribe",
    IntentType.OUT_OF_OFFICE:   "out_of_office",
    IntentType.UNKNOWN:         "unknown",
}


async def compute_semantic_score(
    intent_result: IntentResult,
    message_text: str,
) -> float:
    """
    Compute semantic confidence score.

    Compares the message embedding against:
      - Primary anchor (classified intent)     weight: 0.60
      - Best secondary anchor (if any)         weight: 0.25
      - Overall best anchor across all intents weight: 0.15

    This multi-anchor approach prevents a single misclassification from
    collapsing the semantic score.

    Args:
        intent_result: Output from Intent Engine.
        message_text:  Incoming message text (will be cleaned internally).

    Returns:
        float in [0.0, 1.0]
    """
    if not message_text.strip():
        return 0.50   # No text → neutral score, not zero

    loop = asyncio.get_event_loop()

    # Embed the message (CPU-bound → thread pool)
    plain_text = extract_plain_text(message_text)
    if not plain_text.strip():
        return 0.50

    query_vec  = await loop.run_in_executor(None, lambda: embed(plain_text))
    anchor_vecs = await loop.run_in_executor(None, get_anchor_vectors)

    # ── Primary anchor similarity ─────────────────────────────────────────
    primary_anchor_key = _INTENT_TO_ANCHOR.get(intent_result.intent, "unknown")
    primary_vec        = anchor_vecs.get(primary_anchor_key)

    if primary_vec is None:
        primary_sim = 0.50
    else:
        primary_sim = cosine_similarity(query_vec, primary_vec)

    # ── Best secondary anchor similarity ──────────────────────────────────
    secondary_sim = 0.0
    if intent_result.secondary_intents:
        sims: List[float] = []
        for sec_intent in intent_result.secondary_intents[:2]:
            anchor_key = _INTENT_TO_ANCHOR.get(sec_intent, "unknown")
            vec = anchor_vecs.get(anchor_key)
            if vec is not None:
                sims.append(cosine_similarity(query_vec, vec))
        secondary_sim = max(sims) if sims else 0.0

    # ── Overall best anchor similarity ────────────────────────────────────
    all_sims = [
        cosine_similarity(query_vec, vec)
        for vec in anchor_vecs.values()
    ]
    best_overall_sim = max(all_sims) if all_sims else 0.50

    # ── Weighted combination ──────────────────────────────────────────────
    if intent_result.secondary_intents:
        score = (primary_sim * 0.60) + (secondary_sim * 0.25) + (best_overall_sim * 0.15)
    else:
        score = (primary_sim * 0.75) + (best_overall_sim * 0.25)

    # ── Alignment bonus ───────────────────────────────────────────────────
    # If the best overall anchor IS the primary anchor, the model and
    # embedding fully agree — small bonus.
    all_scores: Dict[str, float] = {
        k: cosine_similarity(query_vec, v) for k, v in anchor_vecs.items()
    }
    best_anchor_key = max(all_scores, key=lambda k: all_scores[k])
    if best_anchor_key == primary_anchor_key:
        score = min(1.0, score + 0.05)

    return round(max(0.0, min(1.0, score)), 4)
