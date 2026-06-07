"""
Memory - Intelligence-Aware Orchestrator
==========================================
Enterprise Conversational Intelligence Memory Engine.

NOT basic chat history storage.

This orchestrator manages 8 layered memory tiers:
  1. Conversation Memory   — turn count, state, history
  2. Intent Memory         — last intents, intent progression
  3. Retrieval Memory      — already-retrieved chunk IDs, retrieval cache keys
  4. Response Memory       — already-shared entities, pricing, products, chunks
  5. Semantic Topic Memory — active topic, semantic cluster, unresolved questions
  6. Business Context      — customer journey stage, tenant context
  7. Escalation Memory     — escalation history, sentiment history
  8. Journey State Memory  — sales/support/onboarding stage

TTLs (tiered):
  conversation cache  →  3h  (mem:hot)
  retrieval cache     →  1h  (mem:retrieval)
  semantic memory     →  6h  (mem:semantic)
  business context    → 24h  (mem:business)

All memory is TENANT-ISOLATED (user_id embedded in every key).
Never cross-tenant.

Performance targets:
  fetch  <10ms
  write  <15ms

Every stage logs memory hit ratio, retrieval reuse, response duplication prevented.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.resource_management import get_resource_manager
from app.observability import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# TTLs (seconds)
# ─────────────────────────────────────────────────────────────────────────────
_TTL_HOT        = 10_800   # 3h  — conversation + intent memory
_TTL_RETRIEVAL  =  3_600   #  1h  — retrieval cache keys
_TTL_SEMANTIC   = 21_600   #  6h  — topic cluster
_TTL_BUSINESS   = 86_400   # 24h  — journey stage, tenant context
_TTL_HISTORY    = 86_400   # 24h  — raw history list

# Max sizes (prevent unbounded growth)
_MAX_HISTORY            = 10
_MAX_SHARED_CHUNKS      = 100
_MAX_INTENT_HISTORY     = 20
_MAX_SENTIMENT_HISTORY  = 20
_MAX_ESCALATION_HISTORY = 10
_MAX_UNRESOLVED         = 10
_MAX_TOPIC_CLUSTER      = 20
_MAX_ACTIVE_TOPICS      = 8

# Explicit re-ask signals — allow repeating already-shared info
_EXPLICIT_REASK_SIGNALS = [
    "tell me again", "repeat", "say again", "remind me", "what was the",
    "send again", "send details again", "share again", "can you repeat",
    "one more time", "didn't catch", "missed that",
]


# ─────────────────────────────────────────────────────────────────────────────
# MemoryOrchestrator
# ─────────────────────────────────────────────────────────────────────────────

class MemoryOrchestrator:
    """
    Enterprise Conversational Intelligence Memory Engine.

    Public API:
        load_memory(user_id, conversation_id, thread_id, trace_id) → Dict
        update_memory(thread_id, intelligence, retrieval, llm_result, trace_id) → None
        check_response_filter(thread_id, message_content, intelligence) → ResponseFilterResult
    """

    def __init__(self):
        self.resource_manager = get_resource_manager()

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC — load_memory
    # ══════════════════════════════════════════════════════════════════════

    async def load_memory(
        self,
        user_id: str,
        conversation_id: str,
        thread_id: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        Load complete intelligence memory (<10ms target).

        Returns a unified memory dict with all 8 tiers merged.
        Falls back to empty-state safely on any Redis error.
        """
        t_start = time.perf_counter()
        try:
            redis = self.resource_manager.get_redis()

            # Parallel load of all memory tiers
            (
                hot,
                retrieval_mem,
                semantic_mem,
                business_mem,
                history,
                entities,
            ) = await _gather(
                self._load_raw(redis, f"mem:hot:{thread_id}"),
                self._load_raw(redis, f"mem:retrieval:{thread_id}"),
                self._load_raw(redis, f"mem:semantic:{thread_id}"),
                self._load_raw(redis, f"mem:business:{user_id}"),
                self._load_history(redis, thread_id),
                self._load_raw(redis, f"mem:entities:{thread_id}"),
            )

            turn_count = hot.get("turn_count", 0)
            memory = {
                # Tier 1 — Conversation
                "thread_id":            thread_id,
                "user_id":              user_id,
                "conversation_id":      conversation_id,
                "turn_count":           turn_count,
                "conversation_state":   hot.get("conversation_state", _state(turn_count)),
                "stage":                hot.get("stage", "initial"),
                "history":              history[:_MAX_HISTORY],
                "cache_hit":            bool(hot),
                "timestamp":            datetime.utcnow().isoformat(),

                # Tier 2 — Intent Memory
                "last_intent":          hot.get("last_intent", "unknown"),
                "last_intents":         hot.get("last_intents", []),        # full intent objects [{intent, entities, confidence, timestamp}]
                "intent_history":       hot.get("intent_history", []),

                # Tier 3 — Retrieval Memory
                "already_shared_chunks":       retrieval_mem.get("already_shared_chunks", []),
                "retrieval_cache_keys":        retrieval_mem.get("retrieval_cache_keys", []),
                "last_retrieval_confidence":   retrieval_mem.get("last_retrieval_confidence", 0.0),
                "last_retrieval_layers":       retrieval_mem.get("last_retrieval_layers", []),
                "retrieval_reuse_count":       retrieval_mem.get("retrieval_reuse_count", 0),
                # Discovery context cache — analytics chunks from previous discovery turn
                # loaded here so _inject_analytics_if_needed can serve cache-first
                "discovery_context":           retrieval_mem.get("discovery_context", []),
                "catalog_summary_cached":      retrieval_mem.get("catalog_summary_cached", False),

                # Tier 4 — Response Memory (repetition prevention)
                "already_shared_entities":     retrieval_mem.get("already_shared_entities", []),
                "already_shared_products":     retrieval_mem.get("already_shared_products", []),
                "pricing_already_shared":      retrieval_mem.get("pricing_already_shared", []),
                "support_info_shared":         retrieval_mem.get("support_info_shared", []),
                "last_response_summary":       retrieval_mem.get("last_response_summary", ""),

                # Tier 5 — Semantic Topic Memory
                "active_topics":               semantic_mem.get("active_topics", []),
                "active_topic":                semantic_mem.get("active_topic", ""),
                "semantic_topic_cluster":      semantic_mem.get("semantic_topic_cluster", []),
                "unresolved_questions":        semantic_mem.get("unresolved_questions", []),

                # Tier 6 — Business Context
                "shared_entities":             entities,
                "business_context":            business_mem.get("business_context", {}),
                "tenant_context":              business_mem.get("tenant_context", {}),

                # Tier 7 — Escalation Memory
                "escalation_history":          hot.get("escalation_history", []),
                "sentiment_history":           hot.get("sentiment_history", []),
                "confidence_history":          hot.get("confidence_history", []),
                "hallucination_history":       hot.get("hallucination_history", []),

                # Tier 8 — Journey State Memory
                "customer_journey_stage":      hot.get("customer_journey_stage", "discovery"),
                "sales_stage":                 hot.get("sales_stage", "awareness"),
                "support_context":             hot.get("support_context", {}),
                "onboarding_stage":            hot.get("onboarding_stage", ""),
                "negotiation_state":           hot.get("negotiation_state", ""),
                "grounding_state":             hot.get("grounding_state", {}),
            }

            elapsed = (time.perf_counter() - t_start) * 1000

            logger.info(
                "Memory loaded | thread=%s turns=%d state=%s "
                "shared_chunks=%d shared_entities=%d topic=%s latency=%.1fms",
                thread_id[:12], turn_count, memory["conversation_state"],
                len(memory["already_shared_chunks"]),
                len(memory["already_shared_entities"]),
                memory["active_topic"] or "none",
                elapsed,
                trace_id=trace_id,
            )

            return memory

        except Exception as e:
            logger.error("Memory load failed: %s", e, trace_id=trace_id, exc_info=True)
            return _empty_memory(user_id, conversation_id, thread_id, str(e))

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC — update_memory (intelligence-aware)
    # ══════════════════════════════════════════════════════════════════════

    async def update_memory(
        self,
        thread_id: str,
        intelligence: Any,
        retrieval: Optional[Dict[str, Any]],
        llm_result: Optional[Dict[str, Any]],
        trace_id: str,
        # Legacy compat params (used by execution_engine.py fallback path)
        intent: str = "",
        entities: Optional[Dict] = None,
        response_text: str = "",
        active_topic: str = "",
    ) -> None:
        """
        Update all 8 memory tiers after processing a turn.

        Accepts either:
          - Full intelligence result (EnterpriseIntelligenceResult or dict) + retrieval + llm_result
          - Legacy params (intent, entities, response_text) for backward compat

        <15ms target.
        """
        t_start = time.perf_counter()
        try:
            redis = self.resource_manager.get_redis()
            now_iso = datetime.utcnow().isoformat()

            # ── Extract values from intelligence ─────────────────────────
            int_dict    = _to_dict(intelligence)
            ret_dict    = retrieval or {}
            llm_dict    = llm_result or {}

            # Intent — extract bare string from enum if needed
            primary_intents = int_dict.get("primary_intents", [])
            primary = primary_intents[0] if primary_intents else {}
            raw_intent = _get(primary, "type") or intent or "unknown"
            resolved_intent = (
                raw_intent.value
                if hasattr(raw_intent, "value")
                else str(raw_intent).split(".")[-1].lower()
            )

            # Entities
            ent_obj   = int_dict.get("entities", entities or {})
            ent_dict  = _to_dict(ent_obj) if not isinstance(ent_obj, dict) else ent_obj
            products  = ent_dict.get("products", [])
            features  = ent_dict.get("features", [])
            all_entities = list(dict.fromkeys(products + features))

            # Topic
            br        = int_dict.get("business_reasoning", {})
            br_dict   = _to_dict(br) if not isinstance(br, dict) else br
            goal      = br_dict.get("likely_goal", "")
            resolved_topic = active_topic or goal or (products[0] if products else "")

            # Journey stage — extract bare string from enum if needed
            conv      = int_dict.get("conversation_analysis", {})
            conv_dict = _to_dict(conv) if not isinstance(conv, dict) else conv
            journey_raw = conv_dict.get("stage", "discovery")
            journey = (
                journey_raw.value
                if hasattr(journey_raw, "value")
                else str(journey_raw).split(".")[-1].lower()
            )
            sentiment_raw = conv_dict.get("sentiment", "neutral")
            sentiment = (
                sentiment_raw.value
                if hasattr(sentiment_raw, "value")
                else str(sentiment_raw).split(".")[-1].lower()
            )

            # Response text
            resp_text = response_text or llm_dict.get("response_text", "")

            # Retrieval fields
            chunks         = ret_dict.get("chunks", [])
            chunk_ids      = _extract_chunk_ids(chunks)
            retrieval_conf = float(ret_dict.get("retrieval_confidence", 0.0))
            layers_used    = ret_dict.get("layers_used", [])

            # ── Tier 1+2+7+8 — Hot memory ────────────────────────────────
            old_hot = await self._load_raw(redis, f"mem:hot:{thread_id}")

            # Accumulate intent history
            intent_record = {
                "intent":     resolved_intent,
                "entities":   all_entities[:5],
                "confidence": float(_get(primary, "confidence") or 0.5),
                "timestamp":  now_iso,
            }
            last_intents   = [intent_record] + old_hot.get("last_intents", [])[:_MAX_INTENT_HISTORY - 1]
            intent_history = [resolved_intent] + old_hot.get("intent_history", [])[:_MAX_INTENT_HISTORY - 1]

            # Sentiment history
            sent_history = [sentiment] + old_hot.get("sentiment_history", [])[:_MAX_SENTIMENT_HISTORY - 1]

            # Confidence history
            gen_conf = float(llm_dict.get("confidence", 0.0))
            conf_history = [gen_conf] + old_hot.get("confidence_history", [])[:19]

            # Hallucination history
            hall_detected = bool(llm_dict.get("hallucination_detected", False))
            hall_history = [hall_detected] + old_hot.get("hallucination_history", [])[:19]

            # Escalation history
            esc_history = list(old_hot.get("escalation_history", []))
            if llm_dict.get("escalate_to_human") or llm_dict.get("pre_gen_grounding", {}).get("escalate"):
                esc_history.insert(0, {"reason": llm_dict.get("fallback_tier_name", "escalation"), "timestamp": now_iso})
                esc_history = esc_history[:_MAX_ESCALATION_HISTORY]

            hot = {
                # Base
                "turn_count":           old_hot.get("turn_count", 0) + 1,
                "last_intent":          resolved_intent,
                "conversation_state":   _state(old_hot.get("turn_count", 0) + 1),
                "stage":                "active",
                "updated_at":           now_iso,
                # Tier 2 — Intent
                "last_intents":         last_intents,
                "intent_history":       intent_history,
                # Tier 7 — Escalation / sentiment
                "sentiment_history":    sent_history,
                "confidence_history":   conf_history,
                "hallucination_history": hall_history,
                "escalation_history":   esc_history,
                "grounding_state": {
                    "pre_gen_confidence": llm_dict.get("pre_gen_grounding", {}).get("overall_confidence", 0.0),
                    "post_gen_score":     llm_dict.get("grounding_score", 0.0),
                },
                # Tier 8 — Journey
                "customer_journey_stage": str(journey),
                "sales_stage":            str(journey),
                "support_context":        {},
            }

            await redis.setex(f"mem:hot:{thread_id}", _TTL_HOT, json.dumps(hot))

            # ── Tier 3+4 — Retrieval + Response memory ───────────────────
            old_ret = await self._load_raw(redis, f"mem:retrieval:{thread_id}")

            # Accumulate already-shared chunk IDs
            existing_chunk_ids = old_ret.get("already_shared_chunks", [])
            merged_chunks = list(dict.fromkeys(existing_chunk_ids + chunk_ids))[:_MAX_SHARED_CHUNKS]

            # Accumulate already-shared entities
            existing_ents = old_ret.get("already_shared_entities", [])
            merged_ents   = list(dict.fromkeys(existing_ents + all_entities))[:50]

            # Accumulate already-shared products
            existing_prods = old_ret.get("already_shared_products", [])
            merged_prods   = list(dict.fromkeys(existing_prods + products))[:30]

            # Accumulate pricing already shared (extract from response text)
            pricing_shared = list(old_ret.get("pricing_already_shared", []))
            pricing_records = _extract_pricing_shared(products, resp_text)
            if pricing_records:
                pricing_shared = pricing_records + pricing_shared
                pricing_shared = pricing_shared[:20]

            # Retrieval cache keys
            cache_keys = list(dict.fromkeys(
                old_ret.get("retrieval_cache_keys", []) + [ret_dict.get("intent_cache_key", "")]
            ))
            cache_keys = [k for k in cache_keys if k][:20]

            ret_mem = {
                # Tier 3
                "already_shared_chunks":      merged_chunks,
                "retrieval_cache_keys":       cache_keys,
                "last_retrieval_confidence":  retrieval_conf,
                "last_retrieval_layers":      layers_used,
                "retrieval_reuse_count":      old_ret.get("retrieval_reuse_count", 0) + (1 if ret_dict.get("cache_hit") else 0),
                # Discovery context cache — persist analytics chunks for reuse on continuation turns.
                # _inject_analytics_if_needed sets _analytics_chunks on the first discovery turn;
                # we store them here so subsequent turns skip Qdrant entirely.
                "discovery_context":          (
                    ret_dict.get("_analytics_chunks")
                    or old_ret.get("discovery_context", [])
                ),
                "catalog_summary_cached":     bool(
                    ret_dict.get("_analytics_chunks")
                    or old_ret.get("catalog_summary_cached", False)
                ),
                # Tier 4
                "already_shared_entities":    merged_ents,
                "already_shared_products":    merged_prods,
                "pricing_already_shared":     pricing_shared,
                "support_info_shared":        old_ret.get("support_info_shared", []),
                "last_response_summary":      resp_text[:300] if resp_text else "",
                "updated_at":                 now_iso,
            }

            await redis.setex(f"mem:retrieval:{thread_id}", _TTL_RETRIEVAL, json.dumps(ret_mem))

            # ── Tier 5 — Semantic Topic memory ───────────────────────────
            old_sem = await self._load_raw(redis, f"mem:semantic:{thread_id}")

            # Active topics
            existing_topics: list = old_sem.get("active_topics", [])
            if resolved_topic and resolved_topic not in existing_topics:
                existing_topics.insert(0, resolved_topic)
            active_topics = existing_topics[:_MAX_ACTIVE_TOPICS]

            # Semantic topic cluster
            search_plan = int_dict.get("search_plan", {})
            sp_dict = _to_dict(search_plan) if not isinstance(search_plan, dict) else search_plan
            sem_queries = sp_dict.get("semantic_queries", [])
            existing_cluster: list = old_sem.get("semantic_topic_cluster", [])
            cluster = list(dict.fromkeys(existing_cluster + sem_queries))[:_MAX_TOPIC_CLUSTER]

            # Unresolved questions — detect question marks in last message
            unresolved = list(old_sem.get("unresolved_questions", []))
            # Remove any that are now answered (simple heuristic: entity match)
            unresolved = [q for q in unresolved if not any(p.lower() in q.lower() for p in products)]
            unresolved = unresolved[:_MAX_UNRESOLVED]

            sem = {
                "active_topic":          resolved_topic,
                "active_topics":         active_topics,
                "semantic_topic_cluster": cluster,
                "unresolved_questions":  unresolved,
                "updated_at":            now_iso,
            }

            await redis.setex(f"mem:semantic:{thread_id}", _TTL_SEMANTIC, json.dumps(sem))

            # ── Entities (shared across turns) ───────────────────────────
            if ent_dict:
                old_ents = await self._load_raw(redis, f"mem:entities:{thread_id}")
                old_ents.update({k: v for k, v in ent_dict.items() if v})
                await redis.setex(f"mem:entities:{thread_id}", _TTL_BUSINESS, json.dumps(old_ents))

            # ── History ───────────────────────────────────────────────────
            history_key  = f"mem:history:{thread_id}"
            history_item = {
                "intent":    resolved_intent,
                "response":  resp_text[:250] if resp_text else "",
                "entities":  all_entities[:5],
                "topic":     resolved_topic,
                "timestamp": now_iso,
            }
            await redis.lpush(history_key, json.dumps(history_item))
            await redis.ltrim(history_key, 0, _MAX_HISTORY - 1)
            await redis.expire(history_key, _TTL_HISTORY)

            elapsed = (time.perf_counter() - t_start) * 1000

            logger.info(
                "Memory updated | thread=%s intent=%s topic=%s "
                "chunks_total=%d entities_total=%d "
                "retrieval_reuse=%d sentiment=%s latency=%.1fms",
                thread_id[:12], resolved_intent, resolved_topic,
                len(merged_chunks), len(merged_ents),
                ret_mem["retrieval_reuse_count"],
                sentiment, elapsed,
                trace_id=trace_id,
            )

        except Exception as e:
            logger.error("Memory update failed: %s", e, trace_id=trace_id, exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC — check_response_filter (response repetition prevention)
    # ══════════════════════════════════════════════════════════════════════

    async def check_response_filter(
        self,
        thread_id: str,
        message_content: str,
        intelligence: Any,
    ) -> "ResponseFilterResult":
        """
        Response Memory Filter — executes BEFORE retrieval and prompt builder.

        Checks:
          - already_shared_entities
          - already_shared_products
          - pricing_already_shared
          - already_shared_chunks
          - Explicit re-ask detection

        Returns ResponseFilterResult with:
          allow_repeated_injection: bool
          already_shared_entities: List[str]
          already_shared_chunks: List[str]
          pricing_already_shared: List[dict]
          is_explicit_reask: bool
          observability: dict
        """
        t = time.perf_counter()
        try:
            redis = self.resource_manager.get_redis()
            ret_mem = await self._load_raw(redis, f"mem:retrieval:{thread_id}")

            # Explicit re-ask detection
            msg_lower = message_content.lower()
            is_explicit_reask = any(sig in msg_lower for sig in _EXPLICIT_REASK_SIGNALS)

            shared_chunks   = ret_mem.get("already_shared_chunks", [])
            shared_entities = ret_mem.get("already_shared_entities", [])
            shared_products = ret_mem.get("already_shared_products", [])
            pricing_shared  = ret_mem.get("pricing_already_shared", [])

            # Determine which current-turn entities were already shared
            int_dict = _to_dict(intelligence)
            ent_obj  = int_dict.get("entities", {})
            ent_dict = _to_dict(ent_obj) if not isinstance(ent_obj, dict) else ent_obj
            current_products = ent_dict.get("products", [])
            current_features = ent_dict.get("features", [])
            current_entities = list(set(current_products + current_features))

            already_shared_now = [e for e in current_entities if e in shared_entities]
            already_priced_now = [
                p for p in pricing_shared
                if any(prod.lower() in _safe_str(p).lower() for prod in current_products)
            ]

            elapsed_ms = (time.perf_counter() - t) * 1000

            observability = {
                "shared_chunk_count":        len(shared_chunks),
                "shared_entity_count":       len(shared_entities),
                "already_shared_this_turn":  len(already_shared_now),
                "pricing_already_shared":    len(already_priced_now),
                "is_explicit_reask":         is_explicit_reask,
                "filter_latency_ms":         round(elapsed_ms, 2),
                "duplication_prevented":     len(already_shared_now) > 0 and not is_explicit_reask,
            }

            if observability["duplication_prevented"]:
                logger.info(
                    "🔁 Response filter: duplicates prevented | entities=%s reask=%s latency=%.1fms",
                    already_shared_now, is_explicit_reask, elapsed_ms,
                )

            return ResponseFilterResult(
                allow_repeated_injection=is_explicit_reask,
                already_shared_entities=shared_entities,
                already_shared_chunks=shared_chunks,
                already_shared_products=shared_products,
                pricing_already_shared=pricing_shared,
                already_shared_this_turn=already_shared_now,
                is_explicit_reask=is_explicit_reask,
                observability=observability,
            )

        except Exception as e:
            logger.warning("Response filter failed: %s", e)
            return ResponseFilterResult(
                allow_repeated_injection=True,   # fail-open
                already_shared_entities=[],
                already_shared_chunks=[],
                already_shared_products=[],
                pricing_already_shared=[],
                already_shared_this_turn=[],
                is_explicit_reask=False,
                observability={"error": str(e)},
            )

    # ══════════════════════════════════════════════════════════════════════
    # INTERNAL helpers
    # ══════════════════════════════════════════════════════════════════════

    async def _load_raw(self, redis, key: str) -> Dict[str, Any]:
        """Load a JSON blob from Redis; return {} on miss/error."""
        try:
            raw = await redis.get(key)
            return json.loads(raw) if raw else {}
        except Exception as e:
            logger.debug("Redis read error key=%s: %s", key, e)
            return {}

    async def _load_history(self, redis, thread_id: str) -> List[Dict]:
        """Load conversation history list."""
        try:
            key   = f"mem:history:{thread_id}"
            items = await redis.lrange(key, 0, _MAX_HISTORY - 1)
            result = []
            for item in items:
                try:
                    result.append(json.loads(item))
                except Exception:
                    pass
            return result
        except Exception:
            return []


# ─────────────────────────────────────────────────────────────────────────────
# ResponseFilterResult
# ─────────────────────────────────────────────────────────────────────────────

class ResponseFilterResult:
    """Result from the response repetition filter."""
    __slots__ = (
        "allow_repeated_injection",
        "already_shared_entities",
        "already_shared_chunks",
        "already_shared_products",
        "pricing_already_shared",
        "already_shared_this_turn",
        "is_explicit_reask",
        "observability",
    )

    def __init__(
        self,
        allow_repeated_injection: bool,
        already_shared_entities: List[str],
        already_shared_chunks: List[str],
        already_shared_products: List[str],
        pricing_already_shared: List[Any],
        already_shared_this_turn: List[str],
        is_explicit_reask: bool,
        observability: Dict[str, Any],
    ):
        self.allow_repeated_injection  = allow_repeated_injection
        self.already_shared_entities   = already_shared_entities
        self.already_shared_chunks     = already_shared_chunks
        self.already_shared_products   = already_shared_products
        self.pricing_already_shared    = pricing_already_shared
        self.already_shared_this_turn  = already_shared_this_turn
        self.is_explicit_reask         = is_explicit_reask
        self.observability             = observability


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _gather(*coros):
    """asyncio.gather wrapper for parallel Redis reads."""
    import asyncio
    return await asyncio.gather(*coros, return_exceptions=False)


def _state(turn_count: int) -> str:
    if turn_count == 0:   return "new"
    if turn_count == 1:   return "initial"
    if turn_count < 5:    return "active"
    return "ongoing"


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Convert a dataclass/Pydantic model or dict to dict."""
    if isinstance(obj, dict):
        return obj
    if obj is None:
        return {}
    if hasattr(obj, "dict"):           # Pydantic v1
        try:
            return obj.dict()
        except Exception:
            pass
    if hasattr(obj, "model_dump"):     # Pydantic v2
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


def _get(d: Any, key: str) -> Any:
    if isinstance(d, dict):
        return d.get(key)
    return getattr(d, key, None)


def _safe_str(v: Any) -> str:
    try:
        return str(v) if v is not None else ""
    except Exception:
        return ""


def _extract_chunk_ids(chunks: List[Any]) -> List[str]:
    ids = []
    for c in chunks:
        cid = (
            c.get("chunk_id") or c.get("id") or ""
            if isinstance(c, dict)
            else getattr(c, "chunk_id", "") or getattr(c, "id", "")
        )
        if cid:
            ids.append(str(cid))
    return ids


def _extract_pricing_shared(products: List[str], response_text: str) -> List[Dict]:
    """
    Detect price mentions in response text and associate with products.
    Simple heuristic — good enough for repetition prevention.
    """
    if not response_text or not products:
        return []
    import re
    prices = re.findall(r"[\$₹€£¥]\s*[\d,]+(?:\.\d{1,2})?", response_text)
    if not prices:
        return []
    result = []
    for prod in products:
        for price in prices:
            result.append({"entity": prod, "price": price})
    return result


def _empty_memory(user_id: str, conversation_id: str, thread_id: str, error: str = "") -> Dict:
    base = {
        "thread_id": thread_id, "user_id": user_id, "conversation_id": conversation_id,
        "turn_count": 0, "conversation_state": "new", "stage": "initial",
        "history": [], "cache_hit": False, "timestamp": datetime.utcnow().isoformat(),
        "last_intent": "unknown", "last_intents": [], "intent_history": [],
        "already_shared_chunks": [], "retrieval_cache_keys": [],
        "last_retrieval_confidence": 0.0, "last_retrieval_layers": [],
        "retrieval_reuse_count": 0,
        "discovery_context": [], "catalog_summary_cached": False,
        "already_shared_entities": [], "already_shared_products": [],
        "pricing_already_shared": [], "support_info_shared": [], "last_response_summary": "",
        "active_topics": [], "active_topic": "", "semantic_topic_cluster": [],
        "unresolved_questions": [], "shared_entities": {}, "business_context": {}, "tenant_context": {},
        "escalation_history": [], "sentiment_history": [], "confidence_history": [], "hallucination_history": [],
        "customer_journey_stage": "discovery", "sales_stage": "awareness",
        "support_context": {}, "onboarding_stage": "", "negotiation_state": "", "grounding_state": {},
    }
    if error:
        base["error"] = error
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_memory_orchestrator: Optional[MemoryOrchestrator] = None


def get_memory_orchestrator() -> MemoryOrchestrator:
    global _memory_orchestrator
    if _memory_orchestrator is None:
        _memory_orchestrator = MemoryOrchestrator()
    return _memory_orchestrator


__all__ = [
    "MemoryOrchestrator",
    "ResponseFilterResult",
    "get_memory_orchestrator",
]
