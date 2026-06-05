"""
Atomic Query Decomposition Engine
====================================
Converts complex multi-intent messages and long emails into atomic
retrieval units — one focused search task per intent/topic.

Responsibilities:
  1. Extract search_units from EnterpriseIntelligenceResult.search_plan
  2. Group by intent cluster (pricing / support / product / onboarding / etc.)
  3. Resolve short-message continuations using memory context
  4. Produce an IntentRetrievalPlan — the input to MultiIntentOrchestrator

Intent Reuse:
  If a new intent is semantically equivalent to a recent intent from memory
  (same type + overlapping entities), reuse is flagged so the retrieval
  layer can serve from L1 cache rather than executing a full pipeline.

This module never calls Qdrant or Redis directly.
It is a pure planning/decomposition layer.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AtomicSearchUnit:
    """
    A single focused retrieval task derived from one intent cluster.

    One AtomicSearchUnit → one HierarchicalRetriever call.
    """
    intent_type: str               # e.g. "pricing_inquiry"
    priority: int                  # 1 = highest
    query: str                     # primary search string
    queries: List[str]             # all queries for this unit (semantic + exact + ...)
    entities: List[str]            # product/feature names relevant to this unit
    metadata_filters: Dict[str, Any] = field(default_factory=dict)
    chunk_types_hint: List[str]    = field(default_factory=list)
    can_reuse_cache: bool          = False
    cache_reuse_reason: str        = ""


@dataclass
class IntentRetrievalPlan:
    """
    Complete decomposed retrieval plan.

    Passed from QueryDecomposer → MultiIntentOrchestrator.
    """
    units: List[AtomicSearchUnit]
    is_multi_intent: bool
    is_continuation: bool
    intent_count: int
    query_count: int
    # Observability
    decomposition_source: str      # "intelligence" | "continuation" | "fallback"
    intent_reuse_hit: bool = False
    intent_reuse_intent: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Intent → chunk type hint mapping
# ─────────────────────────────────────────────────────────────────────────────

_INTENT_CHUNK_HINTS: Dict[str, List[str]] = {
    "pricing_inquiry":            ["product_service", "faq", "policy"],
    "product_inquiry":            ["product_service", "faq"],
    "support_request":            ["support", "faq", "policy"],
    "technical_support_request":  ["support", "faq"],
    "technical_assistance":       ["support", "faq"],
    "technical_question":         ["support", "faq"],
    "complaint":                  ["support", "policy"],
    "refund_request":             ["policy", "support"],
    "billing_inquiry":            ["policy", "product_service"],
    "customization_request":      ["product_service", "faq"],
    "bulk_purchase":              ["product_service", "policy"],
    "onboarding":                 ["faq", "support"],
    "general_inquiry":            ["faq", "product_service"],
}


# ─────────────────────────────────────────────────────────────────────────────
# QueryDecomposer
# ─────────────────────────────────────────────────────────────────────────────

class QueryDecomposer:
    """
    Atomic Query Decomposition Engine.

    Usage:
        decomposer = get_query_decomposer()
        plan = decomposer.decompose(intelligence, memory, message_content)
        # plan.units → list of AtomicSearchUnit → one per parallel retrieval call
    """

    def decompose(
        self,
        intelligence: Any,
        memory: Dict[str, Any],
        message_content: str,
    ) -> IntentRetrievalPlan:
        """
        Decompose intelligence result into atomic retrieval units.

        Handles:
        - Multi-intent: pricing + support + product → 3 parallel tasks
        - Single-intent: standard one task
        - Short continuation: inherits topic/entity from memory, no new retrieval
        - Long email: each search_plan cluster becomes its own task
        """
        int_dict = _to_dict(intelligence)

        # ── Continuation fast path ────────────────────────────────────────
        if self._is_simple_continuation(message_content, int_dict):
            return self._plan_from_continuation(int_dict, memory, message_content)

        # ── Multi-intent decomposition ────────────────────────────────────
        return self._plan_from_intelligence(int_dict, memory)

    # ── Main decomposition ────────────────────────────────────────────────

    def _plan_from_intelligence(
        self, int_dict: Dict, memory: Dict
    ) -> IntentRetrievalPlan:
        """Build per-intent AtomicSearchUnit list from intelligence result."""
        search_plan = int_dict.get("search_plan", {})
        sp = _to_dict(search_plan) if not isinstance(search_plan, dict) else search_plan

        primary_intents   = int_dict.get("primary_intents", []) or []
        secondary_intents = int_dict.get("secondary_intents", []) or []
        all_intents       = list(primary_intents) + list(secondary_intents)

        entities_obj = int_dict.get("entities", {})
        ed = _to_dict(entities_obj) if not isinstance(entities_obj, dict) else entities_obj
        all_entities = (ed.get("products") or []) + (ed.get("features") or [])

        units: List[AtomicSearchUnit] = []
        used_intent_types: set = set()

        # ── One unit per distinct intent ──────────────────────────────────
        for idx, intent_obj in enumerate(all_intents[:4]):  # cap at 4 parallel tasks
            intent_type = _get_intent_type(intent_obj)
            if intent_type in used_intent_types:
                continue
            used_intent_types.add(intent_type)

            # Gather queries relevant to this intent
            queries = _queries_for_intent(intent_type, sp, all_entities)
            if not queries:
                continue

            # Check intent reuse from memory
            can_reuse, reuse_reason = _check_intent_reuse(
                intent_type, all_entities, memory
            )

            unit = AtomicSearchUnit(
                intent_type=intent_type,
                priority=idx + 1,
                query=queries[0],
                queries=queries[:6],
                entities=all_entities[:5],
                metadata_filters=_metadata_filters_for_intent(intent_type),
                chunk_types_hint=_INTENT_CHUNK_HINTS.get(intent_type, ["general"]),
                can_reuse_cache=can_reuse,
                cache_reuse_reason=reuse_reason,
            )
            units.append(unit)

        # ── Fallback: one general unit if nothing was produced ────────────
        if not units:
            semantic_q = sp.get("semantic_queries", [])
            fallback_q = semantic_q[:3] if semantic_q else [
                int_dict.get("business_reasoning", {}).get("likely_goal", "general inquiry")
            ]
            units.append(AtomicSearchUnit(
                intent_type="general_inquiry",
                priority=1,
                query=fallback_q[0] if fallback_q else "general inquiry",
                queries=fallback_q,
                entities=all_entities[:5],
                chunk_types_hint=["general", "faq"],
            ))

        total_queries = sum(len(u.queries) for u in units)
        intent_reuse = any(u.can_reuse_cache for u in units)

        logger.info(
            "QueryDecomposer | intents=%d units=%d queries=%d multi=%s reuse=%s",
            len(all_intents), len(units), total_queries,
            len(units) > 1, intent_reuse,
        )

        return IntentRetrievalPlan(
            units=units,
            is_multi_intent=len(units) > 1,
            is_continuation=False,
            intent_count=len(units),
            query_count=total_queries,
            decomposition_source="intelligence",
            intent_reuse_hit=intent_reuse,
            intent_reuse_intent=units[0].intent_type if intent_reuse else "",
        )

    def _plan_from_continuation(
        self, int_dict: Dict, memory: Dict, message: str
    ) -> IntentRetrievalPlan:
        """
        Short message / continuation — inherit intent and entities from memory.
        No new Qdrant search unless memory has nothing useful.
        """
        last_intent  = memory.get("last_intent", "general_inquiry")
        active_topic = memory.get("active_topic", "")
        last_intents = memory.get("last_intents", [])
        last_entities= memory.get("already_shared_entities", [])
        unresolved   = memory.get("unresolved_questions", [])

        # Build an inherited query
        if active_topic and last_intent != "unknown":
            inherited_query = f"{active_topic} {_intent_to_query_fragment(last_intent)}"
        elif last_entities:
            inherited_query = f"{last_entities[0]} {_intent_to_query_fragment(last_intent)}"
        else:
            inherited_query = last_intent.replace("_", " ")

        # Also include any unresolved questions as queries
        queries = [inherited_query]
        if unresolved:
            queries.extend(q[:80] for q in unresolved[:2])

        # Reuse cache — same intent as last turn
        can_reuse = bool(last_intent and last_intent != "unknown" and active_topic)

        unit = AtomicSearchUnit(
            intent_type=last_intent,
            priority=1,
            query=inherited_query,
            queries=queries,
            entities=last_entities[:5] or ([active_topic] if active_topic else []),
            chunk_types_hint=_INTENT_CHUNK_HINTS.get(last_intent, ["general"]),
            can_reuse_cache=can_reuse,
            cache_reuse_reason="continuation_same_topic" if can_reuse else "",
        )

        logger.info(
            "QueryDecomposer (continuation) | intent=%s topic=%s reuse=%s",
            last_intent, active_topic, can_reuse,
        )

        return IntentRetrievalPlan(
            units=[unit],
            is_multi_intent=False,
            is_continuation=True,
            intent_count=1,
            query_count=len(queries),
            decomposition_source="continuation",
            intent_reuse_hit=can_reuse,
            intent_reuse_intent=last_intent if can_reuse else "",
        )

    # ── Continuation detection ────────────────────────────────────────────

    def _is_simple_continuation(self, message: str, int_dict: Dict) -> bool:
        """
        Detect short-message continuations that should inherit context.
        Uses the intelligence result's is_continuation flag first,
        then falls back to length/keyword heuristic.
        """
        if int_dict.get("is_continuation"):
            return True
        msg = message.strip().lower()
        if len(msg.split()) <= 4:
            _cont_signals = {
                "yes", "no", "okay", "ok", "sure", "thanks", "continue",
                "tell me more", "go ahead", "what else", "and then",
                "interested", "pricing?", "available?",
            }
            if msg in _cont_signals or any(s in msg for s in _cont_signals):
                return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_dict(obj: Any) -> Dict:
    if isinstance(obj, dict):
        return obj
    if obj is None:
        return {}
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


def _get_intent_type(intent_obj: Any) -> str:
    if isinstance(intent_obj, dict):
        return str(intent_obj.get("type", "general_inquiry")).lower()
    return str(getattr(intent_obj, "type", "general_inquiry")).lower()


def _queries_for_intent(
    intent_type: str,
    search_plan: Dict,
    entities: List[str],
) -> List[str]:
    """Select search plan queries most relevant to an intent type."""
    queries: List[str] = []

    if "pricing" in intent_type or "billing" in intent_type or "negotiation" in intent_type:
        queries += (search_plan.get("pricing_queries") or [])[:3]
        queries += (search_plan.get("exact_search_queries") or [])[:2]

    elif "support" in intent_type or "technical" in intent_type or "complaint" in intent_type:
        queries += (search_plan.get("support_queries") or [])[:3]
        queries += (search_plan.get("semantic_queries") or [])[:2]

    elif "refund" in intent_type or "policy" in intent_type or "onboarding" in intent_type:
        queries += (search_plan.get("support_queries") or [])[:2]
        queries += (search_plan.get("semantic_queries") or [])[:2]

    else:
        # Product / general / follow-up
        queries += (search_plan.get("semantic_queries") or [])[:3]
        queries += (search_plan.get("exact_search_queries") or [])[:2]
        queries += (search_plan.get("followup_queries") or [])[:2]

    # Append entity-specific queries
    for ent in entities[:2]:
        if ent and ent.lower() not in " ".join(queries).lower():
            queries.append(f"{ent} {_intent_to_query_fragment(intent_type)}")

    # Deduplicate preserving order
    seen: set = set()
    unique: List[str] = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            unique.append(q)

    return unique[:6]


def _metadata_filters_for_intent(intent_type: str) -> Dict[str, Any]:
    """Build Qdrant metadata pre-filters for an intent."""
    if "support" in intent_type or "technical" in intent_type:
        return {"chunk_type": "support"}
    if "refund" in intent_type or "policy" in intent_type:
        return {"chunk_type": "policy"}
    if "pricing" in intent_type or "billing" in intent_type:
        return {}  # pricing info spans product_service and faq
    return {}


def _intent_to_query_fragment(intent_type: str) -> str:
    _MAP = {
        "pricing_inquiry":   "price cost",
        "product_inquiry":   "details features",
        "support_request":   "support help",
        "technical_support_request": "technical support",
        "complaint":         "complaint resolution",
        "refund_request":    "refund policy",
        "billing_inquiry":   "billing invoice",
        "onboarding":        "setup guide",
        "general_inquiry":   "information",
    }
    for k, v in _MAP.items():
        if k in intent_type:
            return v
    return "information"


def _check_intent_reuse(
    intent_type: str, entities: List[str], memory: Dict
) -> tuple[bool, str]:
    """
    Check if this intent + entities matches a recent memory entry.
    Returns (can_reuse, reason).
    """
    last_intents = memory.get("last_intents", [])
    if not last_intents:
        return False, ""

    entity_set = {e.lower() for e in entities if e}
    for rec in last_intents[:3]:
        rec_intent = str(rec.get("intent", "")).lower() if isinstance(rec, dict) else ""
        rec_entities = [str(e).lower() for e in (rec.get("entities", []) if isinstance(rec, dict) else [])]

        if rec_intent == intent_type and entity_set and any(e in entity_set for e in rec_entities):
            return True, f"same_intent_entities_as_turn_n-{last_intents.index(rec)+1}"

    # Also check last_intent string for same-type match
    last_intent = memory.get("last_intent", "")
    if last_intent == intent_type:
        return True, "same_as_last_intent"

    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_decomposer: Optional[QueryDecomposer] = None


def get_query_decomposer() -> QueryDecomposer:
    global _decomposer
    if _decomposer is None:
        _decomposer = QueryDecomposer()
    return _decomposer


__all__ = [
    "QueryDecomposer",
    "AtomicSearchUnit",
    "IntentRetrievalPlan",
    "get_query_decomposer",
]
