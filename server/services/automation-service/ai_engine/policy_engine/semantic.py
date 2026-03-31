"""
Policy Engine — Semantic Relevance Check
==========================================
Uses MiniLM embeddings to detect context relevance.

Purpose:
  Prevent false rejections of genuine messages that contain noise signals.
  Example: "unsubscribe but interested in pricing" should NOT be rejected.

The semantic check answers:
  "Is this message relevant to an active business conversation?"

If relevance is HIGH → override noise/spam rules toward SAFE_MODE instead of REJECT.
If relevance is LOW  → confirm noise/spam classification.

Uses the shared MiniLM singleton from intent_engine/utils.py — no new model.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from ..intent_engine.utils import extract_plain_text, embed, cosine_similarity

logger = logging.getLogger(__name__)

# Anchor texts representing "business-relevant" conversation
_BUSINESS_ANCHORS = [
    "I am interested in your product and would like more information",
    "Can you tell me about pricing and features",
    "I have a question about your service",
    "I would like to schedule a demo or meeting",
    "Following up on our previous conversation",
    "I need help with my account or a technical issue",
    "Can we discuss terms or negotiate the deal",
]

# Anchor texts representing "noise / irrelevant" content
_NOISE_ANCHORS = [
    "Click here buy now limited time offer act fast",
    "You have been selected for a free prize claim now",
    "Unsubscribe from this mailing list remove me",
    "Out of office I will return on a future date",
    "This is an automated promotional newsletter",
]

_business_vecs: Optional[List] = None
_noise_vecs:    Optional[List] = None


def _get_business_vecs():
    global _business_vecs
    if _business_vecs is None:
        from ..intent_engine.utils import embed as _embed
        _business_vecs = [_embed(t) for t in _BUSINESS_ANCHORS]
    return _business_vecs


def _get_noise_vecs():
    global _noise_vecs
    if _noise_vecs is None:
        from ..intent_engine.utils import embed as _embed
        _noise_vecs = [_embed(t) for t in _NOISE_ANCHORS]
    return _noise_vecs


async def compute_relevance_score(message_text: str) -> float:
    """
    Compute how relevant the message is to a business conversation.

    Returns:
        float in [0, 1]
        >= 0.60 → business-relevant (override toward safe_mode, not reject)
        <  0.60 → likely noise/spam (confirm rejection)
    """
    if not message_text.strip():
        return 0.50

    loop = asyncio.get_event_loop()
    plain = extract_plain_text(message_text)
    if not plain.strip():
        return 0.50

    query_vec = await loop.run_in_executor(None, lambda: embed(plain))

    # Similarity to business anchors
    biz_vecs = await loop.run_in_executor(None, _get_business_vecs)
    biz_sims = [cosine_similarity(query_vec, v) for v in biz_vecs]
    biz_score = max(biz_sims) if biz_sims else 0.0

    # Similarity to noise anchors
    noise_vecs = await loop.run_in_executor(None, _get_noise_vecs)
    noise_sims = [cosine_similarity(query_vec, v) for v in noise_vecs]
    noise_score = max(noise_sims) if noise_sims else 0.0

    # Relevance = how much more business-like than noise-like
    # Rescale to [0, 1]: biz dominates → high relevance
    if biz_score + noise_score == 0:
        return 0.50

    relevance = biz_score / (biz_score + noise_score)
    return round(max(0.0, min(1.0, relevance)), 4)


async def is_business_relevant(message_text: str, threshold: float = 0.55) -> bool:
    """
    Returns True if the message is semantically relevant to a business conversation.
    Used by the decision tree to rescue mixed-intent messages from false rejection.
    """
    score = await compute_relevance_score(message_text)
    return score >= threshold
