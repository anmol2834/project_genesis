"""
Retrieval - Orchestrator
=========================
Enterprise hierarchical retrieval with TRUE multi-intent parallel execution.

Single-intent path (existing):
  L1 → L2 → L3 → L4 → L5 → L6 → L7(RRF) → L8(Rerank) → L9(Validation)
  Handled by HierarchicalRetriever with early-exit at each layer.

Multi-intent path (NEW):
  QueryDecomposer splits intelligence → N AtomicSearchUnits
  Each unit runs HierarchicalRetriever CONCURRENTLY via asyncio.gather
  Results merged via RRF fusion → cross-encoder rerank → context validation
  Deduplication applied before returning

Cache-first per intent:
  If AtomicSearchUnit.can_reuse_cache → HierarchicalRetriever L1 hit is expected
  No extra skip logic needed — L1 handles it natively.

Observability:
  Logs intent_count, query_count, parallel_retrieval_count, cache_hit_ratio,
  RRF_score, rerank_score, retrieval_latency, intent_reuse_hit.
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_config
from app.core.resource_management import get_resource_manager
from app.observability import get_logger

logger = get_logger(__name__)

# Maximum concurrent intent retrievals (prevent Qdrant overload)
_MAX_PARALLEL_INTENTS = 4
# RRF constant k (standard value)
_RRF_K = 60
# Maximum chunks per intent branch before merge
_TOP_K_PER_INTENT = 6
# Final top-k after merge + rerank
_FINAL_TOP_K = 8


class RetrievalOrchestrator:
    """
    Enterprise Hierarchical + Multi-Intent Retrieval Orchestrator.

    Single-intent: delegates to HierarchicalRetriever as before.
    Multi-intent:  fans out parallel HierarchicalRetriever calls, merges via RRF,
                   reranks with cross-encoder scoring, validates context.
    """

    def __init__(self):
        self.config = get_config()
        self.resource_manager = get_resource_manager()

        from app.retrieval.orchestration.hierarchical_retriever import HierarchicalRetriever
        from app.retrieval.caching.intent_cache import IntentCacheEngine

        redis       = self.resource_manager.get_redis()
        qdrant_repo = self.resource_manager.get_qdrant_repository()

        self.hierarchical_retriever = HierarchicalRetriever(
            redis_client=redis,
            qdrant_repository=qdrant_repo,
            min_chunks_for_exit=3,
            min_score_for_exit=0.85,
        )
        self.intent_cache = IntentCacheEngine(redis)
        self.top_k = _FINAL_TOP_K

        # Cross-encoder reranker — lazy loaded
        self._reranker = None

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC entry point
    # ══════════════════════════════════════════════════════════════════════

    async def retrieve(
        self,
        intelligence: Any,
        memory: Dict[str, Any],
        user_id: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        Execute enterprise retrieval.

        Detects multi-intent → routes to parallel path or single path.
        Returns unified result dict compatible with downstream consumers.
        """
        start = time.perf_counter()

        try:
            if self._should_skip_retrieval(intelligence):
                logger.info("⚡ Retrieval skipped — no queries", trace_id=trace_id)
                return self._no_retrieval_result()

            # ── Decompose into atomic search units ───────────────────────
            from app.intelligence.query_decomposition import get_query_decomposer
            decomposer = get_query_decomposer()

            message_hint = memory.get("active_topic", "") or ""
            plan = decomposer.decompose(intelligence, memory, message_hint)

            # ── Priority-aware retrieval budget ───────────────────────────
            budget = memory.get("_retrieval_budget", {})
            priority = memory.get("_priority", 2)
            effective_top_k = budget.get("top_k", self.top_k)
            skip_if_cache_hit = budget.get("skip_if_cache_hit", False)

            # P3: if all units can reuse cache, skip deep retrieval entirely
            if skip_if_cache_hit and all(u.can_reuse_cache for u in plan.units):
                logger.info(
                    "⚡ P3 cache-first: all units reuse cache, skipping deep retrieval",
                    trace_id=trace_id,
                )
                # Still run retrieval — HierarchicalRetriever will hit L1 immediately
                # but we cap top_k low to avoid over-fetching

            # ── Response repetition filter ────────────────────────────────
            response_filter = memory.get("_response_filter")
            already_shared_chunks = (
                response_filter.already_shared_chunks
                if response_filter and hasattr(response_filter, "already_shared_chunks")
                else memory.get("already_shared_chunks", [])
            )
            allow_repeated = (
                response_filter.allow_repeated_injection
                if response_filter and hasattr(response_filter, "allow_repeated_injection")
                else True
            )

            # ── Execute: parallel for multi-intent, single for one intent ─
            if plan.is_multi_intent and len(plan.units) > 1:
                chunks, meta = await self._parallel_retrieve(
                    plan=plan,
                    user_id=user_id,
                    memory=memory,
                    trace_id=trace_id,
                    top_k=effective_top_k,
                )
            else:
                chunks, meta = await self._single_retrieve(
                    unit=plan.units[0],
                    intelligence=intelligence,
                    user_id=user_id,
                    memory=memory,
                    trace_id=trace_id,
                    top_k=effective_top_k,
                )

            # ── Dedup already-shared chunks ───────────────────────────────
            # IMPORTANT: data_analytics chunks are NEVER deduped — they contain
            # pricing/catalog summaries that must be re-injected every turn so
            # the LLM has authoritative data regardless of conversation history.
            dedup_removed = 0
            if already_shared_chunks and not allow_repeated:
                original = len(chunks)
                chunks = [
                    c for c in chunks
                    if c.get("chunk_id", c.get("id", "")) not in already_shared_chunks
                    or str(c.get("chunk_type", "")).lower() == "data_analytics"
                ]
                dedup_removed = original - len(chunks)
                if dedup_removed:
                    logger.info(
                        "🔁 Dedup: removed %d already-shared chunks", dedup_removed,
                        trace_id=trace_id,
                    )

            # ── Populate L1 intent cache ──────────────────────────────────
            retrieval_conf = meta.get("retrieval_confidence", 0.0)
            if chunks and not meta.get("cache_hit") and retrieval_conf >= 0.70:
                await self._populate_intent_cache(
                    user_id=user_id,
                    intelligence=intelligence,
                    chunks=chunks,
                    retrieval_confidence=retrieval_conf,
                    memory=memory,
                )

            elapsed = (time.perf_counter() - start) * 1000
            active_topic = self._extract_active_topic(
                intelligence, self._extract_entities(intelligence)
            )

            result = {
                "chunks":                chunks,
                "total_retrieved":       meta.get("total_retrieved", len(chunks)),
                "layers_used":           meta.get("layers_used", []),
                "cache_hit":             meta.get("cache_hit", False),
                "retrieval_confidence":  retrieval_conf,
                "early_exit":            meta.get("early_exit", False),
                "latency_ms":            elapsed,
                "layer_latencies":       meta.get("layer_latencies", {}),
                "validation_passed":     meta.get("validation_passed", len(chunks)),
                "validation_rejected":   meta.get("validation_rejected", 0),
                "active_topic":          active_topic,
                # Observability extras
                "intent_count":          plan.intent_count,
                "query_count":           plan.query_count,
                "parallel_retrieval_count": len(plan.units),
                "intent_reuse_hit":      plan.intent_reuse_hit,
                "intent_reuse_intent":   plan.intent_reuse_intent,
                "dedup_removed":         dedup_removed,
                "is_multi_intent":       plan.is_multi_intent,
            }

            logger.info(
                "✅ Retrieval | intents=%d parallel=%d chunks=%d confidence=%.2f "
                "cache_hit=%s early_exit=%s reuse=%s latency=%.1fms",
                plan.intent_count, len(plan.units), len(chunks),
                retrieval_conf, meta.get("cache_hit"), meta.get("early_exit"),
                plan.intent_reuse_hit, elapsed,
                trace_id=trace_id,
            )

            return result

        except Exception as e:
            logger.error("Retrieval pipeline failed: %s", e,
                         trace_id=trace_id, exc_info=True)
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "chunks": [], "total_retrieved": 0, "layers_used": [],
                "cache_hit": False, "retrieval_confidence": 0.0,
                "early_exit": True, "latency_ms": elapsed, "layer_latencies": {},
                "validation_passed": 0, "validation_rejected": 0,
                "intent_count": 0, "query_count": 0, "parallel_retrieval_count": 0,
                "intent_reuse_hit": False, "intent_reuse_intent": "",
                "dedup_removed": 0, "is_multi_intent": False, "error": str(e),
            }

    # ══════════════════════════════════════════════════════════════════════
    # Single-intent retrieval (existing path, unchanged in behaviour)
    # ══════════════════════════════════════════════════════════════════════

    async def _single_retrieve(
        self,
        unit,
        intelligence: Any,
        user_id: str,
        memory: Dict,
        trace_id: str,
        top_k: int = _FINAL_TOP_K,
    ) -> Tuple[List[Dict], Dict]:
        """Run a single HierarchicalRetriever call for one intent unit."""
        entities = unit.entities
        result = await self.hierarchical_retriever.retrieve(
            user_id=user_id,
            conversation_id=memory.get("conversation_id", trace_id),
            query=unit.query,
            query_plan=intelligence,
            intent=unit.intent_type,
            entities={
                "product_name": entities[0] if entities else None,
                "products":     entities,
                "features":     self._extract_features(intelligence),
            },
            memory=memory,
            top_k=top_k,
        )
        chunks = [self._chunk_to_dict(c) for c in result.chunks]
        meta = {
            "total_retrieved":      result.total_retrieved,
            "layers_used":          result.layers_used,
            "cache_hit":            result.cache_hit,
            "retrieval_confidence": result.retrieval_confidence,
            "early_exit":           result.early_exit,
            "layer_latencies":      result.layer_latencies,
            "validation_passed":    result.validation_passed,
            "validation_rejected":  result.validation_rejected,
        }
        return chunks, meta

    # ══════════════════════════════════════════════════════════════════════
    # Multi-intent parallel retrieval (NEW)
    # ══════════════════════════════════════════════════════════════════════

    async def _parallel_retrieve(
        self,
        plan,
        user_id: str,
        memory: Dict,
        trace_id: str,
        top_k: int = _FINAL_TOP_K,
    ) -> Tuple[List[Dict], Dict]:
        """
        Run N HierarchicalRetriever calls concurrently (one per intent unit),
        then merge via RRF → cross-encoder rerank → final top-k.
        """
        units = plan.units[:_MAX_PARALLEL_INTENTS]

        async def _retrieve_one(unit) -> Tuple[str, List[Dict], Dict]:
            try:
                entities = unit.entities
                res = await self.hierarchical_retriever.retrieve(
                    user_id=user_id,
                    conversation_id=memory.get("conversation_id", trace_id),
                    query=unit.query,
                    query_plan={
                        "primary_intents": [{"type": unit.intent_type, "confidence": 0.9}],
                        "search_plan":     {"semantic_queries": unit.queries[:3]},
                        "entities":        {"products": entities},
                    },
                    intent=unit.intent_type,
                    entities={
                        "product_name": entities[0] if entities else None,
                        "products":     entities,
                        "features":     [],
                    },
                    memory=memory,
                    top_k=_TOP_K_PER_INTENT,
                )
                dicts = [self._chunk_to_dict(c) for c in res.chunks]
                meta  = {
                    "layers_used":           res.layers_used,
                    "cache_hit":             res.cache_hit,
                    "retrieval_confidence":  res.retrieval_confidence,
                    "early_exit":            res.early_exit,
                    "validation_passed":     res.validation_passed,
                    "validation_rejected":   res.validation_rejected,
                }
                return unit.intent_type, dicts, meta
            except Exception as exc:
                logger.warning(
                    "Parallel intent retrieval error intent=%s: %s",
                    unit.intent_type, exc, trace_id=trace_id,
                )
                return unit.intent_type, [], {}

        # ── Execute all branches concurrently ────────────────────────────
        results: List[Tuple[str, List[Dict], Dict]] = await asyncio.gather(
            *[_retrieve_one(u) for u in units]
        )

        # ── Collect per-branch metadata for observability ─────────────────
        all_layers: List[str]   = []
        cache_hits              = 0
        total_retrieved         = 0
        val_passed              = 0
        val_rejected            = 0
        confidences: List[float] = []

        per_intent_chunks: Dict[str, List[Dict]] = {}
        for intent_type, chunks, meta in results:
            per_intent_chunks[intent_type] = chunks
            total_retrieved += len(chunks)
            if meta.get("cache_hit"):
                cache_hits += 1
            if meta.get("retrieval_confidence"):
                confidences.append(meta["retrieval_confidence"])
            all_layers.extend(meta.get("layers_used", []))
            val_passed   += meta.get("validation_passed", 0)
            val_rejected += meta.get("validation_rejected", 0)

        # ── L7 RRF Fusion ────────────────────────────────────────────────
        merged = self._rrf_merge(per_intent_chunks)

        # ── L8 Cross-encoder rerank ───────────────────────────────────────
        primary_query = plan.units[0].query if plan.units else ""
        reranked = await self._cross_encoder_rerank(merged, primary_query, top_n=self.top_k)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
        any_cache_hit = cache_hits > 0

        merged_meta = {
            "total_retrieved":      total_retrieved,
            "layers_used":          list(dict.fromkeys(all_layers)) + ["MULTI_INTENT_RRF", "MULTI_INTENT_RERANK"],
            "cache_hit":            any_cache_hit,
            "retrieval_confidence": avg_conf,
            "early_exit":           False,
            "layer_latencies":      {},
            "validation_passed":    val_passed,
            "validation_rejected":  val_rejected,
        }

        logger.info(
            "Multi-intent merge | branches=%d total_chunks=%d rrf_merged=%d "
            "reranked=%d cache_hits=%d avg_conf=%.2f",
            len(units), total_retrieved, len(merged), len(reranked), cache_hits, avg_conf,
            trace_id=trace_id,
        )

        return reranked, merged_meta

    # ══════════════════════════════════════════════════════════════════════
    # RRF Fusion
    # ══════════════════════════════════════════════════════════════════════

    def _rrf_merge(
        self, per_intent_chunks: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion across per-intent result lists.
        Score(d) = Σ 1 / (k + rank_i(d))   for each ranked list i that contains d.
        """
        rrf_scores: Dict[str, float] = {}
        chunk_registry: Dict[str, Dict] = {}

        for intent_type, chunks in per_intent_chunks.items():
            for rank, chunk in enumerate(chunks, start=1):
                cid = chunk.get("chunk_id") or chunk.get("id") or f"{intent_type}_{rank}"
                rrf_scores[cid]    = rrf_scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank)
                chunk_registry[cid] = chunk

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)

        # Attach RRF score to each chunk
        merged: List[Dict] = []
        for cid in sorted_ids:
            c = dict(chunk_registry[cid])
            c["rrf_score"] = round(rrf_scores[cid], 6)
            c["score"]     = c["rrf_score"]  # normalise score field
            merged.append(c)

        return merged

    # ══════════════════════════════════════════════════════════════════════
    # Cross-encoder reranking
    # ══════════════════════════════════════════════════════════════════════

    async def _cross_encoder_rerank(
        self,
        chunks: List[Dict],
        query: str,
        top_n: int = 8,
    ) -> List[Dict]:
        """
        Cross-encoder reranking using bge-reranker-v2-m3.
        Falls back to score-based sort if model unavailable.
        """
        if not chunks:
            return chunks

        reranker = self._get_reranker()

        if reranker is None or not query:
            # Fallback: return top_n by existing score
            return sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)[:top_n]

        try:
            pairs = [(query, c.get("content", "")[:512]) for c in chunks]
            scores = reranker.predict(pairs)

            for chunk, score in zip(chunks, scores):
                chunk["rerank_score"] = float(score)
                chunk["score"]        = float(score)

            reranked = sorted(chunks, key=lambda c: c.get("rerank_score", 0.0), reverse=True)

            logger.debug(
                "Cross-encoder rerank | input=%d output=%d top_score=%.3f",
                len(chunks), min(len(reranked), top_n),
                reranked[0].get("rerank_score", 0) if reranked else 0,
            )
            return reranked[:top_n]

        except Exception as e:
            logger.warning("Cross-encoder rerank failed: %s — using score sort", e)
            return sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)[:top_n]

    def _get_reranker(self):
        """Lazy-load bge-reranker-v2-m3 cross-encoder."""
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
            logger.info("Cross-encoder loaded: BAAI/bge-reranker-v2-m3")
        except Exception as e:
            logger.info("Cross-encoder unavailable (%s) — using score sort fallback", e)
            self._reranker = None
        return self._reranker

    # ══════════════════════════════════════════════════════════════════════
    # L1 cache population (unchanged behaviour)
    # ══════════════════════════════════════════════════════════════════════

    async def _populate_intent_cache(
        self,
        user_id: str,
        intelligence: Any,
        chunks: List[Dict],
        retrieval_confidence: float,
        memory: Dict,
    ) -> None:
        try:
            intent_type = self._extract_intent_type(intelligence)
            entities    = self._extract_entities(intelligence)
            keywords    = self._extract_keywords(intelligence)
            chunk_ids   = [c.get("chunk_id", c.get("id", "")) for c in chunks]
            active_topic = self._extract_active_topic(intelligence, entities)
            await self.intent_cache.store_intent_with_retrieval(
                user_id=user_id,
                intent_type=intent_type,
                entities=entities,
                keywords=keywords,
                chunk_ids=chunk_ids,
                chunks_summary=chunks[:5],
                retrieval_confidence=retrieval_confidence,
                active_topic=active_topic,
            )
        except Exception as e:
            logger.debug("L1 cache populate failed: %s", e)

    # ══════════════════════════════════════════════════════════════════════
    # Intelligence extraction helpers (unchanged)
    # ══════════════════════════════════════════════════════════════════════

    def _no_retrieval_result(self) -> Dict[str, Any]:
        return {
            "chunks": [], "total_retrieved": 0, "layers_used": ["SKIPPED_NO_QUERY"],
            "cache_hit": False, "retrieval_confidence": 0.0, "early_exit": True,
            "latency_ms": 0.0, "layer_latencies": {}, "validation_passed": 0,
            "validation_rejected": 0, "intent_count": 0, "query_count": 0,
            "parallel_retrieval_count": 0, "intent_reuse_hit": False,
            "intent_reuse_intent": "", "dedup_removed": 0, "is_multi_intent": False,
        }

    def _should_skip_retrieval(self, intelligence: Any) -> bool:
        search_plan = intelligence.get("search_plan", {}) if isinstance(intelligence, dict) else {}
        if not isinstance(search_plan, dict):
            return False
        has_queries = bool(
            search_plan.get("semantic_queries") or
            search_plan.get("exact_search_queries") or
            search_plan.get("pricing_queries") or
            search_plan.get("support_queries")
        )
        if not has_queries:
            rs = intelligence.get("retrieval_strategy", {}) if isinstance(intelligence, dict) else {}
            if isinstance(rs, dict) and not rs.get("semantic_search", True):
                return True
        return False

    def _extract_intent_type(self, intelligence: Any) -> str:
        primary = (intelligence.get("primary_intents", []) if isinstance(intelligence, dict)
                   else getattr(intelligence, "primary_intents", []))
        if primary:
            first = primary[0]
            return (first.get("type", "general_inquiry") if isinstance(first, dict)
                    else str(getattr(first, "type", "general_inquiry")))
        return "general_inquiry"

    def _extract_entities(self, intelligence: Any) -> List[str]:
        e = (intelligence.get("entities", {}) if isinstance(intelligence, dict)
             else getattr(intelligence, "entities", {}))
        if isinstance(e, dict):
            return (e.get("products") or []) + (e.get("features") or [])
        return list(getattr(e, "products", []) or []) + list(getattr(e, "features", []) or [])

    def _extract_features(self, intelligence: Any) -> List[str]:
        e = (intelligence.get("entities", {}) if isinstance(intelligence, dict)
             else getattr(intelligence, "entities", {}))
        if isinstance(e, dict):
            return e.get("features", [])
        return list(getattr(e, "features", []) or [])

    def _extract_keywords(self, intelligence: Any) -> List[str]:
        sp = (intelligence.get("search_plan", {}) if isinstance(intelligence, dict)
              else getattr(intelligence, "search_plan", {}))
        if isinstance(sp, dict):
            return ((sp.get("semantic_queries") or []) + (sp.get("exact_search_queries") or []))[:5]
        return (list(getattr(sp, "semantic_queries", []) or []) +
                list(getattr(sp, "exact_search_queries", []) or []))[:5]

    def _extract_active_topic(self, intelligence: Any, entities: List[str]) -> str:
        br = (intelligence.get("business_reasoning", {}) if isinstance(intelligence, dict)
              else getattr(intelligence, "business_reasoning", {}))
        goal = (br.get("likely_goal", "") if isinstance(br, dict)
                else getattr(br, "likely_goal", "")) or ""
        return goal or (entities[0] if entities else "general_inquiry")

    def _chunk_to_dict(self, chunk) -> Dict[str, Any]:
        if hasattr(chunk, "to_dict"):
            return chunk.to_dict()
        if hasattr(chunk, "__dict__"):
            return {
                "content":    chunk.content,
                "score":      chunk.score,
                "chunk_type": getattr(chunk.chunk_type, "value", chunk.chunk_type),
                "chunk_id":   chunk.chunk_id,
                "source":     getattr(chunk.source, "value", chunk.source),
                "metadata":   chunk.metadata,
                "id":         chunk.chunk_id,
                "user_id":    chunk.user_id,
            }
        return chunk


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_retrieval_orchestrator: Optional[RetrievalOrchestrator] = None


def get_retrieval_orchestrator() -> RetrievalOrchestrator:
    global _retrieval_orchestrator
    if _retrieval_orchestrator is None:
        _retrieval_orchestrator = RetrievalOrchestrator()
    return _retrieval_orchestrator


__all__ = ["RetrievalOrchestrator", "get_retrieval_orchestrator"]
