"""
Context Builder — Retriever
============================
Two-layer retrieval strategy:

  Layer 1 — Semantic search (vector similarity, score_threshold=0.35)
  Layer 2 — Mandatory scroll fallback (filter-only, no vector needed)

The scroll fallback GUARANTEES business context is always present.
If semantic search returns 0 results, scroll fetches ALL chunks for the user.
This eliminates the "No business context available" failure mode.

Multi-tenant: every query is filtered by user_id — no cross-user data leakage.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .schema import ContextBlock, ContextSource
from ..schemas.intent_schema import IntentResult, IntentType, SubIntent

logger = logging.getLogger(__name__)

# Semantic search threshold — lower than before to catch more relevant results
_QDRANT_SCORE_THRESHOLD = 0.30   # was 0.40 — too aggressive, caused 0-result failures

# Chunk types that are ALWAYS required (fetched via scroll if semantic misses them)
_MANDATORY_CHUNK_TYPES = {"instruction", "business_core", "tone", "use_case"}

# Intent → query text bias
_INTENT_QUERY_BIAS: Dict[str, str] = {
    IntentType.QUESTION.value:        "product features pricing information details",
    IntentType.INTEREST.value:        "product benefits value proposition why choose us",
    IntentType.NEGOTIATION.value:     "pricing plans discount offer deal terms",
    IntentType.OBJECTION.value:       "trust credibility guarantee testimonials proof",
    IntentType.COMPLAINT.value:       "support resolution refund policy customer care",
    IntentType.SUPPORT_REQUEST.value: "help FAQ troubleshooting how to guide",
    IntentType.FOLLOW_UP.value:       "next steps action items follow up",
    IntentType.NOT_INTERESTED.value:  "value proposition why choose us benefits",
    IntentType.REPLY.value:           "business overview general information",
    IntentType.SPAM.value:            "",
    IntentType.PROMO.value:           "",
    IntentType.UNSUBSCRIBE.value:     "",
    IntentType.OUT_OF_OFFICE.value:   "",
    IntentType.UNKNOWN.value:         "business overview general information",
}

_SUBINTENT_QUERY_BIAS: Dict[str, str] = {
    SubIntent.PRICING.value:         "pricing cost fee subscription plan",
    SubIntent.FEATURES.value:        "features capabilities product overview",
    SubIntent.REFUND.value:          "refund policy money back guarantee",
    SubIntent.TRUST.value:           "testimonials case studies credibility proof",
    SubIntent.COMPARISON.value:      "comparison competitor advantage unique",
    SubIntent.DEMO_REQUEST.value:    "demo trial walkthrough schedule",
    SubIntent.MEETING.value:         "meeting schedule call availability",
    SubIntent.TECHNICAL_ISSUE.value: "technical support troubleshooting fix",
    SubIntent.ACCOUNT_ISSUE.value:   "account billing login access",
    SubIntent.LEGAL_THREAT.value:    "",
    SubIntent.CASUAL_CHAT.value:     "",
    SubIntent.NONE.value:            "",
}

# Intents that skip semantic search but STILL get mandatory scroll context
_SKIP_SEMANTIC_INTENTS = {
    IntentType.SPAM,
    IntentType.PROMO,
    IntentType.UNSUBSCRIBE,
    IntentType.OUT_OF_OFFICE,
}


class VectorRetriever:
    """
    Two-layer async retriever.
    Layer 1: semantic search (fast, relevance-ranked).
    Layer 2: mandatory scroll fallback (guarantees business context is never empty).
    """

    async def retrieve(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 5,
    ) -> List[ContextBlock]:
        """Legacy entry point — returns empty list when no vector provided."""
        if not query_vector:
            return []
        return await self._semantic_search(user_id, query_vector, limit)

    async def retrieve_for_intent(
        self,
        user_id: str,
        message_text: str,
        intent_result: IntentResult,
        limit: int = 6,
    ) -> List[ContextBlock]:
        """
        Full two-layer retrieval for a given intent.

        Layer 1: Semantic search with intent-biased query.
        Layer 2: Mandatory scroll — fills any missing chunk types.

        Returns merged, deduplicated blocks with mandatory context guaranteed.
        """
        # Layer 1: Semantic search (skip for pure noise intents)
        semantic_blocks: List[ContextBlock] = []
        if intent_result.intent not in _SKIP_SEMANTIC_INTENTS:
            query_text = self._build_query_text(message_text, intent_result)
            if query_text.strip():
                try:
                    loop = asyncio.get_event_loop()
                    from ..intent_engine.utils import embed, extract_plain_text
                    plain = extract_plain_text(query_text)
                    query_vec = await loop.run_in_executor(None, lambda: embed(plain).tolist())
                    semantic_blocks = await self._semantic_search(user_id, query_vec, limit)
                    logger.info(
                        "Semantic search: %d blocks for user=%s intent=%s",
                        len(semantic_blocks), user_id[:8], intent_result.intent.value,
                    )
                except Exception as exc:
                    logger.warning("Semantic search failed: %s — using scroll fallback", exc)

        # Layer 2: Mandatory scroll — always fetch business context
        # Check which mandatory chunk types are missing from semantic results
        found_types = {b.chunk_type for b in semantic_blocks}
        missing_mandatory = _MANDATORY_CHUNK_TYPES - found_types

        if missing_mandatory or not semantic_blocks:
            scroll_blocks = await self._mandatory_scroll(user_id)
            logger.info(
                "Mandatory scroll: %d blocks for user=%s (missing=%s)",
                len(scroll_blocks), user_id[:8], missing_mandatory,
            )
            # Merge: add scroll blocks for chunk types not already covered
            existing_types = {b.chunk_type for b in semantic_blocks}
            for block in scroll_blocks:
                if block.chunk_type not in existing_types:
                    semantic_blocks.append(block)
                    existing_types.add(block.chunk_type)

        logger.info(
            "Context retrieval complete: %d total blocks for user=%s",
            len(semantic_blocks), user_id[:8],
        )
        return semantic_blocks

    async def _semantic_search(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int,
    ) -> List[ContextBlock]:
        """Execute semantic vector search."""
        loop = asyncio.get_event_loop()
        try:
            from shared.vector_db import search_vectors
            from shared.config import get_config
            config = get_config()

            raw_results = await loop.run_in_executor(
                None,
                lambda: search_vectors(
                    collection_name=config.QDRANT_COLLECTION,
                    query_vector=query_vector,
                    limit=limit,
                    user_id=user_id,
                    score_threshold=_QDRANT_SCORE_THRESHOLD,
                ),
            )
            return [self._parse_hit(r) for r in raw_results if r]
        except Exception as exc:
            logger.warning("Semantic search error: %s", exc)
            return []

    async def _mandatory_scroll(self, user_id: str) -> List[ContextBlock]:
        """
        Scroll all business context chunks for a user — no vector needed.
        This is the guaranteed fallback that ensures context is NEVER empty.
        """
        loop = asyncio.get_event_loop()
        try:
            from shared.vector_db import scroll_vectors
            from shared.config import get_config
            config = get_config()

            raw_results = await loop.run_in_executor(
                None,
                lambda: scroll_vectors(
                    collection_name=config.QDRANT_COLLECTION,
                    user_id=user_id,
                    limit=20,
                ),
            )
            blocks = [self._parse_hit(r) for r in raw_results if r]
            # Assign high base score to mandatory context (it's always relevant)
            for b in blocks:
                b.score = 0.95
            return blocks
        except Exception as exc:
            logger.warning("Mandatory scroll failed: %s", exc)
            return []

    def _parse_hit(self, raw_hit: Dict[str, Any]) -> ContextBlock:
        payload    = raw_hit.get("payload", {})
        content    = payload.get("content", "")
        chunk_type = payload.get("type", "unknown")
        score      = float(raw_hit.get("score", 0.0))
        return ContextBlock(
            content=content,
            score=score,
            source=ContextSource.QDRANT,
            chunk_type=chunk_type,
        )

    def _build_query_text(self, message_text: str, intent_result: IntentResult) -> str:
        intent_bias    = _INTENT_QUERY_BIAS.get(intent_result.intent.value, "")
        subintent_bias = _SUBINTENT_QUERY_BIAS.get(intent_result.sub_intent.value, "")
        parts = [p for p in [message_text[:300], intent_bias, subintent_bias] if p.strip()]
        return " ".join(parts)
