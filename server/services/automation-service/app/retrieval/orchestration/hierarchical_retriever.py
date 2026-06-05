"""
Hierarchical Retrieval Orchestrator
====================================
TRUE L1-L10 hierarchical retrieval with early exit at every layer.

Architecture (CPU memory hierarchy model):
  L1:  Intent Cache (Redis)        <5ms   → STOP if confidence >= 0.90
  L2:  Conversation/Chunk Cache    <10ms  → STOP if confidence >= 0.88
  L3:  Exact Match (Redis+Qdrant)  <20ms  → STOP if confidence >= 0.92
  L4:  Metadata Filter (Qdrant)    <30ms  → STOP if confidence >= 0.85
  L5:  Sparse BM25 (keyword)       <60ms  → STOP if confidence >= 0.80
  L6:  Dense Semantic (Qdrant)     <120ms → continues to L7 always
  L7:  RRF Fusion (multi-source)   <20ms
  L8:  Cross-Encoder Rerank        <100ms
  L9:  Context Validation          <10ms
  L10: Fact Graph Compression      → handled by LLM orchestrator

Each layer returns a LayerDecision(continue_pipeline, confidence, chunks).
The pipeline STOPS immediately when a layer signals sufficient confidence.
Tenant isolation (chunk.user_id == current user_id) is enforced at EVERY layer.
"""

import time
import math
import json
import hashlib
import logging
import re
from collections import defaultdict
from typing import List, Dict, Optional, Any, Tuple

from app.retrieval.schemas import (
    RetrievalResult, RetrievedChunk, ChunkType, RetrievalSource
)
from app.retrieval.caching.conversation_cache import ConversationCacheEngine
from app.retrieval.exact_search.engine import ExactSearchEngine
from app.retrieval.metadata_search.engine import MetadataSearchEngine
from app.retrieval.validation.engine import ValidationEngine

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Per-layer confidence stop thresholds
# ─────────────────────────────────────────────────────────────────────────────
LAYER_STOP_THRESHOLDS: Dict[str, float] = {
    "L1_INTENT_CACHE": 0.90,
    "L2_CHUNK_CACHE":  0.88,
    "L3_EXACT_MATCH":  0.92,   # exact entity → highest trust
    "L4_METADATA":     0.85,
    "L5_BM25":         0.80,
    # L6 semantic: never stops early — it's the expensive fallback
}

# Minimum chunks required before a stop decision is considered valid
MIN_CHUNKS_FOR_STOP = 3


# ─────────────────────────────────────────────────────────────────────────────
# LayerDecision — standard contract returned by every layer
# ─────────────────────────────────────────────────────────────────────────────
class LayerDecision:
    """
    Every retrieval layer MUST return this.
    The pipeline reads `continue_pipeline` to decide STOP vs CONTINUE.
    """
    __slots__ = (
        "layer", "confidence", "continue_pipeline",
        "matched_entities", "chunks", "retrieval_latency_ms",
        "cache_hit", "decision_reason"
    )

    def __init__(
        self,
        layer: str,
        confidence: float,
        continue_pipeline: bool,
        chunks: List[RetrievedChunk],
        retrieval_latency_ms: float,
        matched_entities: Optional[List[str]] = None,
        cache_hit: bool = False,
        decision_reason: str = "",
    ):
        self.layer = layer
        self.confidence = min(1.0, max(0.0, confidence))
        self.continue_pipeline = continue_pipeline
        self.chunks = chunks
        self.retrieval_latency_ms = retrieval_latency_ms
        self.matched_entities = matched_entities or []
        self.cache_hit = cache_hit
        self.decision_reason = decision_reason

    def to_log_dict(self) -> Dict:
        return {
            "layer": self.layer,
            "confidence": round(self.confidence, 4),
            "continue_pipeline": self.continue_pipeline,
            "chunk_count": len(self.chunks),
            "cache_hit": self.cache_hit,
            "latency_ms": round(self.retrieval_latency_ms, 2),
            "decision_reason": self.decision_reason,
            "matched_entities": self.matched_entities,
        }


# ─────────────────────────────────────────────────────────────────────────────
# HierarchicalRetriever
# ─────────────────────────────────────────────────────────────────────────────
class HierarchicalRetriever:
    """
    TRUE L1-L10 hierarchical retrieval with sequential early exit.

    Execution is strictly sequential: cheap cached layers first,
    expensive vector search layers only when cheaper layers fail to
    meet the confidence threshold.
    """

    def __init__(
        self,
        redis_client,
        qdrant_repository,
        min_chunks_for_exit: int = MIN_CHUNKS_FOR_STOP,
        min_score_for_exit: float = 0.85,
    ):
        self.redis = redis_client
        self.qdrant = qdrant_repository

        # ── Existing layer engines (reused, not duplicated) ────────────
        self.conv_cache     = ConversationCacheEngine(redis_client)
        self.exact_search   = ExactSearchEngine(redis_client, qdrant_repository)
        self.metadata_search = MetadataSearchEngine(qdrant_repository)
        self.validation     = ValidationEngine(min_relevance_threshold=0.3)

        # Semantic engine — lazy-loaded on first use (avoid startup penalty)
        self._semantic_engine = None

        self.min_chunks_exit = min_chunks_for_exit
        self.min_score_exit  = min_score_for_exit

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC — main entry point
    # ══════════════════════════════════════════════════════════════════════

    async def retrieve(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
        query_plan: Any,
        intent: str,
        entities: Dict,
        memory: Optional[Dict] = None,
        top_k: int = 8,
    ) -> RetrievalResult:
        """
        Execute TRUE hierarchical retrieval with early exit at each layer.

        Flow:
          L1 → L2 → L3 → L4 → L5 → L6 → L7(RRF) → L8(Rerank) → L9(Validate)

        Each layer checks its stop threshold before proceeding to the next.
        Tenant isolation is enforced at every layer (zero exceptions).
        """
        if not user_id:
            raise ValueError("user_id is MANDATORY for tenant isolation")

        pipeline_start = time.perf_counter()
        layers_used: List[str] = []
        layer_latencies: Dict[str, float] = {}
        layer_decisions: List[LayerDecision] = []
        accumulated_chunks: List[RetrievedChunk] = []
        sources_used: List[str] = []   # tracks which deep layers ran (for RRF)
        cache_hit = False
        cache_hit_layer: Optional[str] = None
        early_exit = False

        memory = memory or {}

        # ── L1: Intent Cache ──────────────────────────────────────────────
        d1 = await self._layer_l1_intent_cache(
            user_id, conversation_id, intent, entities, query_plan, top_k
        )
        layer_latencies["L1"] = d1.retrieval_latency_ms
        layer_decisions.append(d1)
        self._log_layer(d1)

        if d1.chunks:
            layers_used.append("L1_INTENT_CACHE")
            accumulated_chunks.extend(d1.chunks)
            cache_hit = True
            cache_hit_layer = "L1"

        if not d1.continue_pipeline:
            early_exit = True
            logger.info(
                "🛑 PIPELINE STOP @ L1 | reason=%s confidence=%.3f chunks=%d",
                d1.decision_reason, d1.confidence, len(accumulated_chunks)
            )

        # ── L2: Conversation / Chunk Cache ────────────────────────────────
        if not early_exit:
            d2 = await self._layer_l2_chunk_cache(
                user_id, conversation_id, intent, entities, top_k
            )
            layer_latencies["L2"] = d2.retrieval_latency_ms
            layer_decisions.append(d2)
            self._log_layer(d2)

            if d2.chunks:
                layers_used.append("L2_CHUNK_CACHE")
                accumulated_chunks.extend(d2.chunks)
                if not cache_hit:
                    cache_hit = True
                    cache_hit_layer = "L2"

            if not d2.continue_pipeline:
                early_exit = True
                logger.info(
                    "🛑 PIPELINE STOP @ L2 | reason=%s confidence=%.3f",
                    d2.decision_reason, d2.confidence
                )

        # ── L3: Exact Match ───────────────────────────────────────────────
        if not early_exit:
            d3 = await self._layer_l3_exact_match(user_id, entities, intent)
            layer_latencies["L3"] = d3.retrieval_latency_ms
            layer_decisions.append(d3)
            self._log_layer(d3)

            if d3.chunks:
                layers_used.append("L3_EXACT_MATCH")
                accumulated_chunks.extend(d3.chunks)

            if not d3.continue_pipeline:
                early_exit = True
                logger.info(
                    "🛑 PIPELINE STOP @ L3 | reason=%s confidence=%.3f",
                    d3.decision_reason, d3.confidence
                )

        # ── L4: Metadata Filter ───────────────────────────────────────────
        if not early_exit:
            d4 = await self._layer_l4_metadata(user_id, entities, intent, top_k)
            layer_latencies["L4"] = d4.retrieval_latency_ms
            layer_decisions.append(d4)
            self._log_layer(d4)

            if d4.chunks:
                layers_used.append("L4_METADATA")
                accumulated_chunks.extend(d4.chunks)
                sources_used.append("L4")

            if not d4.continue_pipeline:
                early_exit = True
                logger.info(
                    "🛑 PIPELINE STOP @ L4 | reason=%s confidence=%.3f",
                    d4.decision_reason, d4.confidence
                )

        # ── L5: BM25 Sparse Keyword ───────────────────────────────────────
        if not early_exit:
            d5 = await self._layer_l5_bm25(user_id, query, query_plan, intent, top_k)
            layer_latencies["L5"] = d5.retrieval_latency_ms
            layer_decisions.append(d5)
            self._log_layer(d5)

            if d5.chunks:
                layers_used.append("L5_BM25")
                accumulated_chunks.extend(d5.chunks)
                sources_used.append("L5")

            if not d5.continue_pipeline:
                early_exit = True
                logger.info(
                    "🛑 PIPELINE STOP @ L5 | reason=%s confidence=%.3f",
                    d5.decision_reason, d5.confidence
                )

        # ── L6: Dense Semantic Search ─────────────────────────────────────
        # Only runs when all cheaper layers failed — this is the EXPENSIVE fallback
        semantic_chunks: List[RetrievedChunk] = []
        if not early_exit:
            d6 = await self._layer_l6_semantic(user_id, query, query_plan, top_k)
            layer_latencies["L6"] = d6.retrieval_latency_ms
            layer_decisions.append(d6)
            self._log_layer(d6)

            if d6.chunks:
                layers_used.append("L6_SEMANTIC")
                accumulated_chunks.extend(d6.chunks)
                semantic_chunks = d6.chunks
                sources_used.append("L6")

        # ── L7: RRF Fusion (only when multiple sources contributed) ───────
        if len(sources_used) > 1 and not early_exit:
            t7 = time.perf_counter()
            accumulated_chunks = self._layer_l7_rrf_fusion(
                accumulated_chunks, sources_used
            )
            layer_latencies["L7"] = (time.perf_counter() - t7) * 1000
            layers_used.append("L7_RRF_FUSION")
            logger.debug(
                "L7 RRF fusion | sources=%s chunks_after=%d latency=%.1fms",
                sources_used, len(accumulated_chunks), layer_latencies["L7"]
            )

        # ── L8: Cross-Encoder Rerank ──────────────────────────────────────
        # Only run reranking when semantic search was used (worth the cost)
        if semantic_chunks and not early_exit:
            t8 = time.perf_counter()
            accumulated_chunks = self._layer_l8_rerank(
                query, accumulated_chunks, top_k
            )
            layer_latencies["L8"] = (time.perf_counter() - t8) * 1000
            layers_used.append("L8_RERANK")
            logger.debug(
                "L8 rerank | chunks=%d latency=%.1fms",
                len(accumulated_chunks), layer_latencies["L8"]
            )

        # ── L9: Context Validation & Deduplication ────────────────────────
        t9 = time.perf_counter()
        unique_chunks = self.validation.remove_duplicates(accumulated_chunks)
        valid_chunks, passed, rejected = self.validation.filter_valid_chunks(
            unique_chunks, query, user_id, min_relevance=0.3
        )
        layer_latencies["L9"] = (time.perf_counter() - t9) * 1000
        layers_used.append("L9_VALIDATION")

        # Sort by score, trim to top_k
        valid_chunks.sort(key=lambda c: c.score, reverse=True)
        final_chunks = valid_chunks[:top_k]

        # ── Build result ───────────────────────────────────────────────────
        total_latency = (time.perf_counter() - pipeline_start) * 1000
        retrieval_confidence = self._calculate_confidence(
            final_chunks, layers_used, layer_decisions, early_exit
        )

        logger.info(
            "✅ Hierarchical retrieval done | layers=%s chunks=%d/%d "
            "confidence=%.3f early_exit=%s latency=%.1fms",
            layers_used, len(final_chunks), len(accumulated_chunks),
            retrieval_confidence, early_exit, total_latency
        )

        return RetrievalResult(
            chunks=final_chunks,
            total_retrieved=len(accumulated_chunks),
            cache_hit=cache_hit,
            early_exit=early_exit,
            latency_ms=total_latency,
            layers_used=layers_used,
            layer_latencies=layer_latencies,
            strategy_used="hierarchical",
            retrieval_confidence=retrieval_confidence,
            validation_passed=passed,
            validation_rejected=rejected,
            cache_hit_layer=cache_hit_layer,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    # ══════════════════════════════════════════════════════════════════════
    # L1 — Intent Cache
    # ══════════════════════════════════════════════════════════════════════

    async def _layer_l1_intent_cache(
        self,
        user_id: str,
        conversation_id: str,
        intent: str,
        entities: Dict,
        query_plan: Any,
        top_k: int,
    ) -> LayerDecision:
        t = time.perf_counter()
        threshold = LAYER_STOP_THRESHOLDS["L1_INTENT_CACHE"]

        try:
            # Build intent fingerprint key
            cache_key = self._build_intent_cache_key(user_id, intent, entities)
            raw = await self.redis.get(cache_key)

            if not raw:
                return LayerDecision(
                    layer="L1_INTENT_CACHE",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    cache_hit=False,
                    decision_reason="intent_cache_miss",
                )

            cached = json.loads(raw)
            cached_confidence = float(cached.get("retrieval_confidence", 0.0))
            chunks = self._deserialize_chunks(cached.get("chunks_summary", []), user_id, "L1")

            # Tenant safety: filter any chunk that doesn't match user_id
            chunks = [c for c in chunks if c.user_id == user_id]

            confidence = cached_confidence
            stop = confidence >= threshold and len(chunks) >= MIN_CHUNKS_FOR_STOP

            return LayerDecision(
                layer="L1_INTENT_CACHE",
                confidence=confidence,
                continue_pipeline=not stop,
                chunks=chunks,
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                matched_entities=cached.get("entities", []),
                cache_hit=True,
                decision_reason=(
                    f"intent_cache_hit_stop confidence={confidence:.3f}"
                    if stop else
                    f"intent_cache_hit_continue confidence={confidence:.3f}"
                ),
            )

        except Exception as e:
            logger.warning("L1 intent cache error: %s", e)
            return LayerDecision(
                layer="L1_INTENT_CACHE",
                confidence=0.0,
                continue_pipeline=True,
                chunks=[],
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=f"l1_error: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # L2 — Conversation / Chunk Cache
    # ══════════════════════════════════════════════════════════════════════

    async def _layer_l2_chunk_cache(
        self,
        user_id: str,
        conversation_id: str,
        intent: str,
        entities: Dict,
        top_k: int,
    ) -> LayerDecision:
        t = time.perf_counter()
        threshold = LAYER_STOP_THRESHOLDS["L2_CHUNK_CACHE"]

        try:
            context = await self.conv_cache.get_conversation_context(
                user_id, conversation_id
            )

            if not context:
                return LayerDecision(
                    layer="L2_CHUNK_CACHE",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    cache_hit=False,
                    decision_reason="chunk_cache_miss",
                )

            can_serve = self.conv_cache.should_skip_retrieval(context, intent, entities)
            if not can_serve:
                return LayerDecision(
                    layer="L2_CHUNK_CACHE",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    cache_hit=False,
                    decision_reason="chunk_cache_insufficient_for_intent",
                )

            chunks_dict = self.conv_cache.get_chunks_from_cache(
                context, intent, entities, top_k
            )
            chunks = self._deserialize_chunks(chunks_dict, user_id, "L2")
            # Tenant safety
            chunks = [c for c in chunks if c.user_id == user_id]

            if not chunks:
                return LayerDecision(
                    layer="L2_CHUNK_CACHE",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="chunk_cache_empty_after_filter",
                )

            avg_score = sum(c.score for c in chunks) / len(chunks)
            confidence = min(0.90, avg_score * 1.05)  # small cache trust boost
            stop = confidence >= threshold and len(chunks) >= MIN_CHUNKS_FOR_STOP

            return LayerDecision(
                layer="L2_CHUNK_CACHE",
                confidence=confidence,
                continue_pipeline=not stop,
                chunks=chunks,
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                cache_hit=True,
                decision_reason=(
                    f"chunk_cache_hit_stop confidence={confidence:.3f}"
                    if stop else
                    f"chunk_cache_hit_continue confidence={confidence:.3f}"
                ),
            )

        except Exception as e:
            logger.warning("L2 chunk cache error: %s", e)
            return LayerDecision(
                layer="L2_CHUNK_CACHE",
                confidence=0.0,
                continue_pipeline=True,
                chunks=[],
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=f"l2_error: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # L3 — Exact Match
    # ══════════════════════════════════════════════════════════════════════

    async def _layer_l3_exact_match(
        self,
        user_id: str,
        entities: Dict,
        intent: str,
    ) -> LayerDecision:
        t = time.perf_counter()
        threshold = LAYER_STOP_THRESHOLDS["L3_EXACT_MATCH"]

        try:
            product_name = entities.get("product_name") or (
                entities.get("products", [None])[0]
                if entities.get("products") else None
            )

            if not product_name:
                return LayerDecision(
                    layer="L3_EXACT_MATCH",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="no_entity_for_exact_match",
                )

            chunks = await self.exact_search.search_exact(
                user_id=user_id,
                entity_name=product_name,
                entity_type="product",
            )
            # Tenant safety
            chunks = [c for c in chunks if c.user_id == user_id]

            if not chunks:
                return LayerDecision(
                    layer="L3_EXACT_MATCH",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="exact_match_not_found",
                )

            # Exact match scores are always 1.0 — high confidence
            confidence = 1.0 if any(c.score >= 0.99 for c in chunks) else 0.88
            stop = confidence >= threshold and len(chunks) >= MIN_CHUNKS_FOR_STOP

            return LayerDecision(
                layer="L3_EXACT_MATCH",
                confidence=confidence,
                continue_pipeline=not stop,
                chunks=chunks,
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                matched_entities=[product_name],
                decision_reason=(
                    f"exact_match_stop entity={product_name} confidence={confidence:.3f}"
                    if stop else
                    f"exact_match_partial entity={product_name} confidence={confidence:.3f}"
                ),
            )

        except Exception as e:
            logger.warning("L3 exact match error: %s", e)
            return LayerDecision(
                layer="L3_EXACT_MATCH",
                confidence=0.0,
                continue_pipeline=True,
                chunks=[],
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=f"l3_error: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # L4 — Metadata Filter
    # ══════════════════════════════════════════════════════════════════════

    async def _layer_l4_metadata(
        self,
        user_id: str,
        entities: Dict,
        intent: str,
        top_k: int,
    ) -> LayerDecision:
        t = time.perf_counter()
        threshold = LAYER_STOP_THRESHOLDS["L4_METADATA"]

        try:
            filters = self.metadata_search.build_filters_from_entities(entities, intent)

            if not self.metadata_search.has_meaningful_filters(filters):
                return LayerDecision(
                    layer="L4_METADATA",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="no_meaningful_metadata_filters",
                )

            chunks = await self.metadata_search.search_metadata(
                user_id=user_id, filters=filters, top_k=top_k
            )
            # Tenant safety
            chunks = [c for c in chunks if c.user_id == user_id]

            if not chunks:
                return LayerDecision(
                    layer="L4_METADATA",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="metadata_search_no_results",
                )

            avg_score = sum(c.score for c in chunks) / len(chunks)
            stop = avg_score >= threshold and len(chunks) >= MIN_CHUNKS_FOR_STOP

            return LayerDecision(
                layer="L4_METADATA",
                confidence=avg_score,
                continue_pipeline=not stop,
                chunks=chunks,
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=(
                    f"metadata_stop score={avg_score:.3f}"
                    if stop else
                    f"metadata_continue score={avg_score:.3f}"
                ),
            )

        except Exception as e:
            logger.warning("L4 metadata error: %s", e)
            return LayerDecision(
                layer="L4_METADATA",
                confidence=0.0,
                continue_pipeline=True,
                chunks=[],
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=f"l4_error: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # L5 — BM25 Sparse Keyword Search
    # ══════════════════════════════════════════════════════════════════════

    async def _layer_l5_bm25(
        self,
        user_id: str,
        query: str,
        query_plan: Any,
        intent: str,
        top_k: int,
    ) -> LayerDecision:
        """
        BM25 keyword-based sparse search.
        Implemented using Qdrant scroll + in-process BM25 scoring
        (no external sparse index required).
        """
        t = time.perf_counter()
        threshold = LAYER_STOP_THRESHOLDS["L5_BM25"]

        try:
            # Extract keywords from query plan
            keywords = self._extract_bm25_keywords(query, query_plan)
            if not keywords:
                return LayerDecision(
                    layer="L5_BM25",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="no_bm25_keywords",
                )

            # Fetch candidate documents from Qdrant via scroll (tenant-safe)
            chunk_type_filter = self._intent_to_chunk_type(intent)
            filters = {"chunk_type": chunk_type_filter} if chunk_type_filter else {}

            candidates = await self.qdrant.scroll(
                user_id=user_id,
                filters=filters,
                limit=min(top_k * 5, 50),  # over-fetch for BM25 scoring
            )

            if not candidates:
                return LayerDecision(
                    layer="L5_BM25",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="bm25_no_candidates",
                )

            # Score candidates with BM25
            scored = self._bm25_score(keywords, candidates)
            scored = scored[:top_k]

            if not scored:
                return LayerDecision(
                    layer="L5_BM25",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="bm25_no_scored_results",
                )

            chunks = []
            for item in scored:
                payload = item["payload"]
                # Tenant safety — double-check
                if payload.get("user_id") != user_id:
                    continue
                chunk = RetrievedChunk(
                    content=payload.get("content", ""),
                    score=item["bm25_score"],
                    chunk_type=ChunkType(payload.get("chunk_type", "general")),
                    chunk_id=payload.get("chunk_id", str(item.get("id", ""))),
                    source=RetrievalSource.L4_BM25,
                    user_id=user_id,
                    metadata=payload,
                    retrieval_layer="L5",
                )
                chunks.append(chunk)

            if not chunks:
                return LayerDecision(
                    layer="L5_BM25",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="bm25_all_rejected_tenant",
                )

            top_score = chunks[0].score
            stop = top_score >= threshold and len(chunks) >= MIN_CHUNKS_FOR_STOP

            return LayerDecision(
                layer="L5_BM25",
                confidence=top_score,
                continue_pipeline=not stop,
                chunks=chunks,
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=(
                    f"bm25_stop score={top_score:.3f}"
                    if stop else
                    f"bm25_continue score={top_score:.3f}"
                ),
            )

        except Exception as e:
            logger.warning("L5 BM25 error: %s", e)
            return LayerDecision(
                layer="L5_BM25",
                confidence=0.0,
                continue_pipeline=True,
                chunks=[],
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=f"l5_error: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # L6 — Dense Semantic Search
    # ══════════════════════════════════════════════════════════════════════

    async def _layer_l6_semantic(
        self,
        user_id: str,
        query: str,
        query_plan: Any,
        top_k: int,
    ) -> LayerDecision:
        """
        Dense vector semantic search — the EXPENSIVE fallback.
        Only executes when L1-L5 all failed to meet confidence thresholds.
        """
        t = time.perf_counter()

        try:
            engine = self._get_semantic_engine()
            if not engine:
                return LayerDecision(
                    layer="L6_SEMANTIC",
                    confidence=0.0,
                    continue_pipeline=False,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="semantic_engine_unavailable",
                )

            # Build semantic queries from query plan
            queries = self._extract_semantic_queries(query, query_plan)

            chunks = await engine.search_multi_query(
                user_id=user_id,
                queries=queries,
                top_k_per_query=max(3, top_k // len(queries)),
                score_threshold=0.28,
            )

            # Tenant safety — semantic engine already filters but we double-check
            chunks = [c for c in chunks if c.user_id == user_id]

            if not chunks:
                return LayerDecision(
                    layer="L6_SEMANTIC",
                    confidence=0.0,
                    continue_pipeline=False,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="semantic_no_results",
                )

            avg_score = sum(c.score for c in chunks) / len(chunks)

            return LayerDecision(
                layer="L6_SEMANTIC",
                confidence=avg_score,
                continue_pipeline=False,  # L6 is the last retrieval layer
                chunks=chunks,
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=f"semantic_done score={avg_score:.3f}",
            )

        except Exception as e:
            logger.warning("L6 semantic error: %s", e)
            return LayerDecision(
                layer="L6_SEMANTIC",
                confidence=0.0,
                continue_pipeline=False,
                chunks=[],
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=f"l6_error: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # L7 — RRF Fusion
    # ══════════════════════════════════════════════════════════════════════

    def _layer_l7_rrf_fusion(
        self,
        all_chunks: List[RetrievedChunk],
        sources_used: List[str],
    ) -> List[RetrievedChunk]:
        """
        Reciprocal Rank Fusion across multiple retrieval sources.
        Groups chunks by source, assigns RRF rank, re-scores.
        RRF formula: score = sum(1 / (k + rank)) across sources, k=60
        """
        if len(sources_used) <= 1:
            return all_chunks

        k = 60
        # Group by source
        by_source: Dict[str, List[RetrievedChunk]] = defaultdict(list)
        for chunk in all_chunks:
            src = chunk.retrieval_layer or "unknown"
            by_source[src].append(chunk)

        # Sort each source by score (descending)
        for src in by_source:
            by_source[src].sort(key=lambda c: c.score, reverse=True)

        # Accumulate RRF scores per chunk_id
        rrf_scores: Dict[str, float] = defaultdict(float)
        chunk_by_id: Dict[str, RetrievedChunk] = {}

        for src, chunks in by_source.items():
            for rank, chunk in enumerate(chunks, start=1):
                cid = chunk.chunk_id
                rrf_scores[cid] += 1.0 / (k + rank)
                if cid not in chunk_by_id:
                    chunk_by_id[cid] = chunk

        # Normalize and assign fused scores
        max_rrf = max(rrf_scores.values()) if rrf_scores else 1.0
        result = []
        for cid, rrf_score in rrf_scores.items():
            chunk = chunk_by_id[cid]
            chunk.score = rrf_score / max_rrf  # normalize to [0,1]
            result.append(chunk)

        result.sort(key=lambda c: c.score, reverse=True)
        return result

    # ══════════════════════════════════════════════════════════════════════
    # L8 — Cross-Encoder Rerank (lightweight score-based approximation)
    # ══════════════════════════════════════════════════════════════════════

    def _layer_l8_rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int,
    ) -> List[RetrievedChunk]:
        """
        Score-based reranking using query-content overlap.
        This is a lightweight approximation; a cross-encoder model can be
        plugged in here when available (replace _rerank_score with model inference).
        """
        if not chunks or not query:
            return chunks

        query_tokens = set(re.findall(r"\w+", query.lower()))

        for chunk in chunks:
            content_tokens = set(re.findall(r"\w+", chunk.content.lower()))
            if not query_tokens:
                overlap = 0.0
            else:
                overlap = len(query_tokens & content_tokens) / len(query_tokens)
            # Blend: 60% original score + 40% overlap
            chunk.score = 0.6 * chunk.score + 0.4 * overlap

        chunks.sort(key=lambda c: c.score, reverse=True)
        return chunks[:top_k]

    # ── L9 — Context Validation (named method for audit/testing discoverability)

    def _layer_l9_validation(
        self,
        accumulated_chunks: List[RetrievedChunk],
        query: str,
        user_id: str,
        top_k: int,
    ):
        """
        L9 Context Validation & Deduplication.
        Delegates to ValidationEngine (removes duplicates, filters by relevance/tenant).
        Called both inline from retrieve() and available as a named method.
        """
        unique = self.validation.remove_duplicates(accumulated_chunks)
        valid, passed, rejected = self.validation.filter_valid_chunks(
            unique, query, user_id, min_relevance=0.3
        )
        valid.sort(key=lambda c: c.score, reverse=True)
        return valid[:top_k], passed, rejected

    # ══════════════════════════════════════════════════════════════════════
    # BM25 Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _bm25_score(
        self,
        keywords: List[str],
        candidates: List[Dict],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> List[Dict]:
        """
        In-process BM25 scoring against fetched Qdrant documents.
        Returns candidates sorted by bm25_score descending.
        """
        if not candidates or not keywords:
            return []

        # Compute average document length
        doc_lengths = []
        tokenized = []
        for doc in candidates:
            content = doc.get("payload", {}).get("content", "")
            tokens = re.findall(r"\w+", content.lower())
            tokenized.append(tokens)
            doc_lengths.append(len(tokens))

        avg_dl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1
        N = len(candidates)

        # IDF per keyword
        idf: Dict[str, float] = {}
        for kw in keywords:
            kw_lower = kw.lower()
            df = sum(1 for tokens in tokenized if kw_lower in tokens)
            idf[kw_lower] = math.log((N - df + 0.5) / (df + 0.5) + 1)

        # Score each document
        scored = []
        for i, doc in enumerate(candidates):
            tokens = tokenized[i]
            dl = doc_lengths[i]
            tf_dict: Dict[str, int] = defaultdict(int)
            for token in tokens:
                tf_dict[token] += 1

            score = 0.0
            for kw in keywords:
                kw_lower = kw.lower()
                tf = tf_dict.get(kw_lower, 0)
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * dl / avg_dl)
                score += idf.get(kw_lower, 0) * (numerator / denominator if denominator else 0)

            if score > 0:
                doc_copy = dict(doc)
                doc_copy["bm25_score"] = min(1.0, score / (len(keywords) * 3))
                scored.append(doc_copy)

        scored.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored

    # ══════════════════════════════════════════════════════════════════════
    # Confidence Calculation
    # ══════════════════════════════════════════════════════════════════════

    def _calculate_confidence(
        self,
        chunks: List[RetrievedChunk],
        layers_used: List[str],
        layer_decisions: List[LayerDecision],
        early_exit: bool,
    ) -> float:
        if not chunks:
            return 0.0

        # Base: weighted average of top-3 chunk scores
        top_scores = sorted([c.score for c in chunks], reverse=True)[:3]
        avg_top = sum(top_scores) / len(top_scores)
        confidence = avg_top * 0.55

        # Validated chunk ratio
        validated_ratio = sum(1 for c in chunks if c.validated) / len(chunks)
        confidence += validated_ratio * 0.20

        # Layer depth bonus — shallower = more precise
        if any("L1" in l for l in layers_used):
            confidence += 0.20
        elif any("L2" in l for l in layers_used):
            confidence += 0.15
        elif any("L3" in l for l in layers_used):
            confidence += 0.12
        elif any("L4" in l for l in layers_used):
            confidence += 0.08
        else:
            confidence += 0.05

        # Early exit bonus (reached a high-confidence stop)
        if early_exit:
            confidence += 0.05

        return min(1.0, confidence)

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _build_intent_cache_key(
        self,
        user_id: str,
        intent: str,
        entities: Dict,
    ) -> str:
        """Deterministic intent cache key with tenant isolation."""
        products = sorted(str(p).lower() for p in entities.get("products", []))
        features = sorted(str(f).lower() for f in entities.get("features", []))
        fingerprint = json.dumps(
            {"intent": intent, "products": products, "features": features},
            sort_keys=True,
        )
        h = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
        return f"automation:intent_cache:{user_id}:{h}"

    def _deserialize_chunks(
        self,
        chunks_data: List[Dict],
        user_id: str,
        layer: str,
    ) -> List[RetrievedChunk]:
        """Convert serialized chunk dicts back to RetrievedChunk objects."""
        result = []
        for d in chunks_data:
            try:
                chunk = RetrievedChunk(
                    content=d.get("content", ""),
                    score=float(d.get("score", 0.8)),
                    chunk_type=ChunkType(d.get("chunk_type", "general")),
                    chunk_id=d.get("chunk_id", d.get("id", "")),
                    source=RetrievalSource.MEMORY_CACHE,
                    user_id=d.get("user_id", user_id),
                    metadata=d.get("metadata", {}),
                    retrieval_layer=layer,
                )
                result.append(chunk)
            except Exception:
                continue
        return result

    def _extract_bm25_keywords(self, query: str, query_plan: Any) -> List[str]:
        """Extract keywords for BM25 from query and query plan."""
        keywords: List[str] = []

        if query:
            stop = {
                "the", "a", "an", "is", "are", "was", "were", "for",
                "to", "in", "on", "of", "do", "does", "can", "could",
                "what", "how", "tell", "me", "and", "or", "with",
            }
            keywords.extend(
                w for w in re.findall(r"\w+", query.lower())
                if w not in stop and len(w) > 2
            )

        if isinstance(query_plan, dict):
            for q in query_plan.get("exact_search_queries", []):
                keywords.extend(re.findall(r"\w+", str(q).lower()))
        elif hasattr(query_plan, "search_plan"):
            sp = query_plan.search_plan
            for q in getattr(sp, "exact_search_queries", []):
                keywords.extend(re.findall(r"\w+", str(q).lower()))

        # Deduplicate, keep order
        seen: set = set()
        unique: List[str] = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        return unique[:15]

    def _extract_semantic_queries(self, query: str, query_plan: Any) -> List[str]:
        """Extract semantic query strings for L6 dense search."""
        queries: List[str] = []

        if isinstance(query_plan, dict):
            queries.extend(query_plan.get("semantic_queries", []))
            queries.extend(query_plan.get("pricing_queries", []))
        elif hasattr(query_plan, "search_plan"):
            sp = query_plan.search_plan
            queries.extend(getattr(sp, "semantic_queries", []))
            queries.extend(getattr(sp, "pricing_queries", []))

        if query and query not in queries:
            queries.insert(0, query)

        return [q for q in queries if q][:5]  # max 5 semantic queries

    def _intent_to_chunk_type(self, intent: str) -> Optional[str]:
        """Map intent string to a Qdrant chunk_type filter value."""
        mapping = {
            "pricing_inquiry":          "product_service",
            "product_inquiry":          "product_service",
            "support_request":          "support",
            "technical_support_request": "support",
            "technical_assistance":     "support",
            "feature_request":          "product_service",
            "general_inquiry":          None,
            "follow_up":                None,
        }
        return mapping.get(intent)

    def _get_semantic_engine(self):
        """Lazy-load semantic search engine."""
        if self._semantic_engine is None:
            try:
                from app.retrieval.semantic_search.engine import SemanticSearchEngine
                self._semantic_engine = SemanticSearchEngine(self.qdrant)
            except Exception as e:
                logger.error("Failed to load semantic engine: %s", e)
        return self._semantic_engine

    def _log_layer(self, decision: LayerDecision) -> None:
        """Structured log for every layer decision."""
        d = decision.to_log_dict()
        logger.info(
            "📊 Layer[%s] confidence=%.3f continue=%s chunks=%d "
            "cache_hit=%s latency=%.1fms | %s",
            d["layer"], d["confidence"], d["continue_pipeline"],
            d["chunk_count"], d["cache_hit"], d["latency_ms"],
            d["decision_reason"],
        )
