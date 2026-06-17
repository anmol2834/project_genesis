"""
Hierarchical Retrieval Orchestrator
====================================
TRUE L1-L10 hierarchical retrieval with early exit at every layer.

Architecture:
  L1:  Intent Cache (Redis)                   <5ms   → STOP if confidence >= 0.90
  L2:  Conversation/Chunk Cache               <10ms  → STOP if confidence >= 0.88
  L3:  Exact Match (Redis+Qdrant)             <20ms  → STOP if confidence >= 0.92
  L4:  Metadata Filter (Qdrant)              <30ms  → STOP if confidence >= 0.85
  L5:  Category Keyword Scan (Qdrant scroll) <80ms  → STOP if confidence >= 0.85
  L6:  Dense Vector Search (e5-base-v2)      <200ms → always continues to L7
  L7:  RRF Fusion (multi-source)             <20ms
  L8:  Score-blend Rerank                    <10ms
  L9:  Context Validation                    <10ms
  L10: Fact Graph Compression                → handled by LLM orchestrator

L5 is a pure Python token-overlap scan (NO BM25 library) using Qdrant scroll.
It scores every field: content, search_text, title, keywords[], ai_tags[],
and ALL structured_data / attributes key+value pairs.
This is complementary to L6 dense vector search (e5-base-v2, 768-dim).
"""

import time
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
    "L5_BM25":         0.85,   # raised: only stop if BM25 is highly confident
    # L6 semantic: never stops early — it's the expensive fallback
}

# Minimum chunks required before a stop decision is considered valid
# Raised to 5: categories have 20+ entries, we want broad retrieval
MIN_CHUNKS_FOR_STOP = 5


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
            # ── SPEC BYPASS: Skip L1 cache for spec-only queries ─────────────
            # When all entities are hardware specs (8GB RAM, 512GB SSD, RTX 4070)
            # with no real product names, the cache key is identical to a generic
            # product_inquiry — it will serve wrong (stale) chunks from a previous
            # broad query. Force fresh retrieval for spec queries so L5 BM25 can
            # find products that actually match the specs in Qdrant.
            all_entity_values = (
                list(entities.get("products", []) or [])
                + list(entities.get("features", []) or [])
                + list(entities.get("technical_terms", []) or [])
            )
            if all_entity_values:
                _spec_bypass_pat = re.compile(
                    r"^\d+\s*(?:gb|tb|mb|ghz|mhz|inch|\")\b"
                    r"|ram$|ssd$|hdd$|gpu$|cpu$|vram$",
                    re.IGNORECASE,
                )
                _generic_bypass = {
                    "laptop", "laptops", "product", "products",
                    "item", "items", "service", "services",
                }
                real_product_entities = [
                    e for e in all_entity_values
                    if e and not _spec_bypass_pat.search(str(e).strip())
                    and str(e).lower() not in _generic_bypass
                    and len(str(e).strip()) >= 3
                ]
                if not real_product_entities:
                    # All entities are specs — bypass L1 cache, force deep retrieval
                    logger.info(
                        "L1 cache bypassed: spec-only query entities=%s "
                        "— forcing fresh deep retrieval",
                        all_entity_values[:4],
                    )
                    return LayerDecision(
                        layer="L1_INTENT_CACHE",
                        confidence=0.0,
                        continue_pipeline=True,
                        chunks=[],
                        retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                        cache_hit=False,
                        decision_reason="spec_query_cache_bypass",
                    )

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
    # L5 — Category-Scoped Keyword + Structured-Data Scan
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
        Category-scoped keyword scan using Qdrant scroll.

        Fetches ALL records for the target category (tenant-safe), then scores
        each record by token-overlap across ALL text fields AND structured_data
        key/value pairs.  This is purely additive to L4 (metadata) and L6
        (dense vector) — it catches records that have exact keyword hits in
        title, search_text, keywords[], or structured_data values but that may
        score lower in dense vector space.

        NO BM25 library required — plain Python token overlap is sufficient
        because the embedding model (e5-base-v2) already handles semantic
        similarity in L6.  This layer only needs to surface records with strong
        literal matches that vector search might rank too low.
        """

        t = time.perf_counter()
        threshold = LAYER_STOP_THRESHOLDS["L5_BM25"]

        try:
            # Extract query keywords (stop-word filtered)
            keywords = self._extract_query_keywords(query, query_plan)
            if not keywords:
                return LayerDecision(
                    layer="L5_BM25",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="no_keywords_for_scan",
                )

            # Determine category filter from Brain #1 target_categories or intent mapping
            chunk_type_filter = self._intent_to_chunk_type(intent, query_plan)
            filters = {"chunk_type": chunk_type_filter} if chunk_type_filter else {}

            # Fetch ALL records for this category (up to 300) — categories have 20+ entries
            candidates = await self.qdrant.scroll(
                user_id=user_id,
                filters=filters,
                limit=300,
            )

            if not candidates:
                return LayerDecision(
                    layer="L5_BM25",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="l5_no_candidates",
                )

            # Score each record by token overlap across ALL payload fields
            scored = self._keyword_overlap_score(keywords, candidates)

            # Dynamic overlap threshold based on query type:
            # - Spec queries (containing hardware keywords like "8gb", "512gb", "ssd")
            #   produce a naturally smaller keyword set after stop-word filtering.
            #   A lower threshold ensures spec-matching records are not filtered out.
            # - General queries with many words have a larger denominator so we
            #   use the standard 0.25 threshold.
            # - Category-level queries ("all offers", "shipping") use 0 so all
            #   records in the category are returned for reranking.
            _SPEC_KW_PAT = re.compile(
                r"^\d+\s*(?:gb|tb|mb|ghz|mhz)\b"
                r"|^(?:ssd|hdd|ram|gpu|cpu|vram|nvme|ddr)$",
                re.IGNORECASE,
            )
            spec_keyword_count = sum(1 for kw in keywords if _SPEC_KW_PAT.match(kw))
            is_spec_query = spec_keyword_count >= 1

            # Lower threshold for spec queries — spec terms are high-signal,
            # matching even 1 spec keyword out of 5 clean keywords is significant.
            MIN_OVERLAP = 0.15 if is_spec_query else 0.25

            above_threshold = [s for s in scored if s["overlap_score"] >= MIN_OVERLAP]

            if above_threshold:
                scored = above_threshold[:top_k * 2]
            else:
                # Category-level query: assign base score 0.50 to all category records
                scored = []
                for doc in candidates:
                    doc_copy = dict(doc)
                    doc_copy["overlap_score"] = 0.50
                    scored.append(doc_copy)
                scored = scored[:top_k * 2]
                logger.info(
                    "L5 keyword scan | no overlap above %.2f for intent=%s — "
                    "returning all %d category records with base score",
                    MIN_OVERLAP, intent, len(scored),
                )

            if not scored:
                return LayerDecision(
                    layer="L5_BM25",
                    confidence=0.0,
                    continue_pipeline=True,
                    chunks=[],
                    retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                    decision_reason="l5_no_candidates_after_score",
                )

            chunks = []
            for item in scored:
                payload = item["payload"]
                if payload.get("user_id") != user_id:
                    continue
                display_content = (
                    payload.get("content")
                    or payload.get("search_text", "")
                    or payload.get("title", "")
                )
                try:
                    ct = ChunkType(payload.get("chunk_type", "general"))
                except ValueError:
                    ct = ChunkType.GENERAL
                chunk = RetrievedChunk(
                    content=display_content,
                    score=item["overlap_score"],
                    chunk_type=ct,
                    chunk_id=payload.get("chunk_id", payload.get("entry_id", str(item.get("id", "")))),
                    source=RetrievalSource.L5_BM25,
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
                    decision_reason="l5_all_rejected_tenant",
                )

            top_score = chunks[0].score
            # Only stop pipeline if highly confident — otherwise always continue to L6
            # so dense vector search can complement keyword matches.
            stop = top_score >= threshold and len(chunks) >= MIN_CHUNKS_FOR_STOP

            return LayerDecision(
                layer="L5_BM25",
                confidence=top_score,
                continue_pipeline=not stop,
                chunks=chunks,
                retrieval_latency_ms=(time.perf_counter() - t) * 1000,
                decision_reason=(
                    f"l5_keyword_stop score={top_score:.3f} matched={len(chunks)}"
                    if stop else
                    f"l5_keyword_continue score={top_score:.3f} matched={len(chunks)}"
                ),
            )

        except Exception as e:
            logger.warning("L5 keyword scan error: %s", e)
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
        Applies category filter from Brain #1's target_categories so semantic
        search never returns policy/analytics chunks for product queries.
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

            # ── Category filter for L6: use Brain #1's target_categories ──
            # This is the most critical fix: without this, L6 returns policy/FAQ
            # chunks for product queries because vector similarity doesn't know
            # about intent. The filter forces Qdrant to search only the correct
            # category bucket, e.g. product_service for product_inquiry.
            chunk_type_filter = self._intent_to_chunk_type(
                # Extract intent string from query_plan
                (
                    str(getattr(
                        getattr(query_plan, "primary_intents", [{}])[0]
                        if hasattr(query_plan, "primary_intents") and getattr(query_plan, "primary_intents", [])
                        else {},
                        "type", "general_inquiry"
                    ))
                    if not isinstance(query_plan, dict)
                    else (
                        (query_plan.get("primary_intents") or [{}])[0].get("type", "general_inquiry")
                        if query_plan.get("primary_intents")
                        else "general_inquiry"
                    )
                ),
                query_plan,
            )

            # Resolve the Qdrant category value (user_data_entries uses "category" field)
            # chunk_type_filter is the ChunkType string e.g. "product_service"
            # which maps back to category="product_service" in user_data_entries
            semantic_filters: Optional[Dict] = None
            if chunk_type_filter:
                semantic_filters = {"chunk_type": chunk_type_filter}
                logger.debug(
                    "L6 semantic | applying category filter: %s", chunk_type_filter
                )

            chunks = await engine.search_multi_query(
                user_id=user_id,
                queries=queries,
                top_k_per_query=max(3, top_k // max(len(queries), 1)),
                score_threshold=0.25,
                filters=semantic_filters,
            )

            # If filtered search returned nothing, retry WITHOUT filter as fallback
            # (prevents total failure when the category has low vector coverage)
            if not chunks and semantic_filters:
                logger.info(
                    "L6 semantic | no results with filter=%s, retrying without filter",
                    chunk_type_filter,
                )
                chunks = await engine.search_multi_query(
                    user_id=user_id,
                    queries=queries,
                    top_k_per_query=max(3, top_k // max(len(queries), 1)),
                    score_threshold=0.25,
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
                decision_reason=f"semantic_done score={avg_score:.3f} filter={chunk_type_filter}",
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
    # Keyword Scan Helpers (replaces BM25 — uses e5-compatible token overlap)
    # ══════════════════════════════════════════════════════════════════════

    def _keyword_overlap_score(self, keywords: List[str], candidates: List[Dict]) -> List[Dict]:
        """
        Score each Qdrant record by keyword token overlap across ALL payload fields.

        Scoring strategy:
          1. Build a unified token set per record from: content, search_text, title,
             keywords[], ai_tags[], AND every key+value pair in structured_data and
             attributes dicts.  This catches "ram": "16GB" when user asks "8gb ram".
          2. Score = (matched_keywords / total_keywords) normalized to [0, 1].
          3. Bonus +0.1 per keyword found as a structured_data VALUE (exact spec match).

        SPEC EQUALITY FIX:
          Hardware specs like "8gb" and "16gb" share the token "gb". A naive token
          overlap would match "8gb" against ANY product that has "gb" anywhere, giving
          false positive scores to 16GB/32GB products.
          
          Fix: For spec keywords (digits + unit like "8gb", "512gb", "16ghz"), require
          the FULL spec token to match, not just the unit. The unit ("gb", "tb", "mhz")
          alone is NOT considered a match. Only the full "8gb" or "512gb" string counts.

        Returns candidates sorted by overlap_score descending.
        Records with score == 0 are excluded.
        """
        if not candidates or not keywords:
            return []

        kw_lower = [k.lower() for k in keywords]

        # Identify which keywords are hardware specs (digit+unit) for strict matching
        _SPEC_NUM_FULL = re.compile(r'^(\d+)\s*(gb|tb|mb|ghz|mhz|nm)$', re.IGNORECASE)
        spec_keywords = {kw for kw in kw_lower if _SPEC_NUM_FULL.match(kw)}
        # Unit-only tokens that should NOT count as standalone matches (they're too generic)
        _UNIT_ONLY = {"gb", "tb", "mb", "ghz", "mhz", "nm", "ram", "ssd", "hdd", "gpu", "cpu"}
        # Pure unit tokens should be removed from scoring keywords since they match
        # everything that has memory/storage specs regardless of the actual value
        scoring_keywords = [kw for kw in kw_lower if kw not in _UNIT_ONLY or kw in spec_keywords]
        if not scoring_keywords:
            scoring_keywords = kw_lower

        def _payload_token_set(payload: Dict) -> set:
            tokens: set = set()
            # Primary text fields
            for field in ("content", "search_text", "title"):
                val = payload.get(field, "")
                if val:
                    tokens.update(re.findall(r"\w+", str(val).lower()))
            # keywords[] list stored in payload — these are pre-computed by ingestion
            for kw in payload.get("keywords", []) or []:
                tokens.update(re.findall(r"\w+", str(kw).lower()))
            # ai_tags[]
            for tag in payload.get("ai_tags", []) or []:
                tokens.update(re.findall(r"\w+", str(tag).lower()))
            # structured_data — include both keys AND values
            sd = payload.get("structured_data") or {}
            if isinstance(sd, dict):
                for k, v in sd.items():
                    tokens.update(re.findall(r"\w+", str(k).lower()))
                    tokens.update(re.findall(r"\w+", str(v).lower()))
            # attributes — include both keys AND values
            attrs = payload.get("attributes") or {}
            if isinstance(attrs, dict):
                for k, v in attrs.items():
                    tokens.update(re.findall(r"\w+", str(k).lower()))
                    tokens.update(re.findall(r"\w+", str(v).lower()))
            return tokens

        def _structured_data_value_tokens(payload: Dict) -> set:
            """Token set from structured_data VALUES only — for exact spec bonus."""
            tokens: set = set()
            for src in (payload.get("structured_data") or {}, payload.get("attributes") or {}):
                if isinstance(src, dict):
                    for v in src.values():
                        tokens.update(re.findall(r"\w+", str(v).lower()))
            return tokens

        def _full_text_for_spec_check(payload: Dict) -> str:
            """Return the full searchable text blob for spec equality checking."""
            parts = []
            for field in ("content", "search_text", "title"):
                val = payload.get(field, "")
                if val:
                    parts.append(str(val).lower())
            sd = payload.get("structured_data") or {}
            if isinstance(sd, dict):
                for v in sd.values():
                    parts.append(str(v).lower())
            attrs = payload.get("attributes") or {}
            if isinstance(attrs, dict):
                for v in attrs.values():
                    parts.append(str(v).lower())
            return " ".join(parts)

        scored = []
        for doc in candidates:
            payload = doc.get("payload", {})
            token_set = _payload_token_set(payload)
            sd_value_tokens = _structured_data_value_tokens(payload)
            full_text = _full_text_for_spec_check(payload)

            matched = 0
            for kw in scoring_keywords:
                # For spec keywords (e.g. "8gb", "512gb"), require the FULL spec token
                # to appear in the full text. The unit alone ("gb") is NOT a match.
                if kw in spec_keywords:
                    # Check that "8gb" appears as a contiguous token in full_text
                    # This prevents "16gb" from matching a "8gb" query
                    # We match: "8gb", "8 gb", "8gb", or "8 GB" but NOT "16gb"
                    m = _SPEC_NUM_FULL.match(kw)
                    if m:
                        num_val = m.group(1)
                        unit_val = m.group(2).lower()
                        # Look for exact spec: the number followed immediately by unit
                        # e.g. "8gb", "8 gb", "8GB" — but NOT "16gb" or "32gb"
                        spec_exact = re.compile(
                            rf'\b{re.escape(num_val)}\s*{re.escape(unit_val)}\b',
                            re.IGNORECASE,
                        )
                        if spec_exact.search(full_text):
                            matched += 1
                        # NO partial credit for unit-only matches — that's the whole point
                else:
                    if kw in token_set:
                        matched += 1

            if matched == 0:
                continue

            base_score = matched / len(scoring_keywords)

            # Bonus for exact structured_data value matches (e.g. "16gb", "512gb")
            sd_matches = sum(1 for kw in spec_keywords if kw in sd_value_tokens)
            bonus = min(0.30, sd_matches * 0.10)  # up to +0.30 bonus

            overlap_score = min(1.0, base_score + bonus)
            doc_copy = dict(doc)
            doc_copy["overlap_score"] = overlap_score
            scored.append(doc_copy)

        scored.sort(key=lambda x: x["overlap_score"], reverse=True)
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

    def _extract_query_keywords(self, query: str, query_plan: Any) -> List[str]:
        """
        Extract query keywords for L5 keyword scan.
        Pulls from: raw query, semantic_queries, exact_search_queries, pricing_queries.
        Stop-word filtered; deduplicated; order preserved.
        """
        _STOP = {
            # Articles, prepositions, conjunctions
            "the", "a", "an", "and", "or", "but", "nor", "so", "yet",
            "in", "on", "at", "to", "for", "of", "with", "by", "from",
            "into", "onto", "upon", "about", "above", "below", "after",
            "before", "between", "through", "during", "against", "among",
            # Pronouns
            "i", "me", "my", "we", "our", "you", "your", "it", "its",
            "he", "she", "they", "them", "his", "her", "their",
            # Auxiliary/modal verbs
            "is", "are", "was", "were", "be", "been", "being",
            "do", "does", "did", "will", "would", "can", "could",
            "may", "might", "shall", "should", "have", "has", "had",
            # Interrogative/relative
            "what", "which", "who", "whom", "whose", "where", "when",
            "why", "how",
            # Common filler words
            "any", "all", "some", "too", "also", "just", "now", "then",
            "very", "much", "more", "most", "less", "such", "own", "same",
            "other", "another", "each", "every", "both", "few", "many",
            # Action/intent words that add no retrieval value
            "want", "need", "give", "show", "know", "like", "tell",
            "get", "got", "let", "use", "make", "take", "see", "look",
            "find", "give", "help", "ask", "say", "said", "go", "come",
            # Question words
            "please", "thanks", "thank",
            # Common short words passing len>2 check that add no value
            "not", "yes", "via", "per", "etc", "vs",
        }
        raw: List[str] = []

        if query:
            raw.extend(re.findall(r"\w+", query.lower()))

        # Also pull from Brain #1 search plan queries
        sp = None
        if isinstance(query_plan, dict):
            sp = query_plan.get("search_plan") or query_plan
        elif hasattr(query_plan, "search_plan"):
            sp = query_plan.search_plan

        if sp is not None:
            for field in ("semantic_queries", "exact_search_queries", "pricing_queries", "support_queries"):
                items = (sp.get(field, []) if isinstance(sp, dict) else getattr(sp, field, []) or [])
                for q in items:
                    raw.extend(re.findall(r"\w+", str(q).lower()))

        seen: set = set()
        unique: List[str] = []
        for w in raw:
            if w not in _STOP and len(w) > 2 and w not in seen:
                seen.add(w)
                unique.append(w)
        return unique[:20]

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

    def _intent_to_chunk_type(self, intent: str, query_plan: Any = None) -> Optional[str]:
        """Map intent string to a Qdrant chunk_type filter value.
        
        Respects target_categories from the search plan (set by Brain #1).
        Falls back to intent mapping when no explicit categories are set.
        """
        # Brain #1 explicit routing takes priority
        if query_plan is not None:
            sp = (query_plan.get("search_plan", {}) if isinstance(query_plan, dict)
                  else getattr(query_plan, "search_plan", None))
            if sp is not None:
                target = (sp.get("target_categories", []) if isinstance(sp, dict)
                          else getattr(sp, "target_categories", []))
                if target:
                    return target[0]  # use first target category as primary filter

        # Fallback: intent-based mapping
        # Maps every IntentType to the correct Qdrant category field value.
        # This is the canonical routing table — every new intent MUST have an entry.
        # Values MUST match the exact "category" strings stored in user_data_entries.
        # None means "no category filter" — all categories are searched (used when
        # pricing data spans multiple categories: product_service, offers_promotions).
        mapping = {
            # pricing_inquiry: prices live in product_service AND offers_promotions AND
            # delivery_shipping — using None removes the category filter so all are searched.
            "pricing_inquiry":           None,
            "product_inquiry":           "product_service",
            "offers_inquiry":            "offers_promotions",
            "shipping_inquiry":          "delivery_shipping",
            "company_inquiry":           "company_info",
            "educational_inquiry":       "educational_content",
            "support_request":           "contact_support",
            # technical_support_request = specific bug/error report → issue_resolution
            "technical_support_request": "issue_resolution",
            "technical_assistance":      "issue_resolution",
            "technical_question":        "issue_resolution",
            "feature_request":           "product_service",
            "complaint":                 "contact_support",
            "refund_request":            "policies_legal",
            "billing_inquiry":           "product_service",
            "general_inquiry":           "product_service",
            "issue_inquiry":             "issue_resolution",
            "issue_resolution":          "issue_resolution",
            "follow_up":                 None,
            "unknown":                   None,
        }
        # Normalise intent string — handles both "pricing_inquiry" and
        # "IntentType.PRICING_INQUIRY" enum string representations
        intent_lower = intent.lower() if intent else ""
        if "." in intent_lower:
            intent_lower = intent_lower.split(".")[-1]
        return mapping.get(intent_lower)

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
