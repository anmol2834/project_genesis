"""
Enterprise Pipeline Trace Recorder
=====================================
Wraps EVERY stage of the automation pipeline in a structured span and emits
a complete machine-readable execution trace on completion.

Uses the existing DistributedTracer + MetricsCollector — does NOT duplicate them.

For any email, an engineer can reconstruct the ENTIRE execution path by searching
logs for  `trace_id=<id>`  — every stage, decision, latency, confidence, cache hit,
retrieval layer, hallucination score, risk score, fallback tier is present.

Trace structure emitted at pipeline end:
{
  "trace_id":          "...",
  "tenant_id":         "...",
  "thread_id":         "...",
  "message_id":        "...",
  "conversation_id":   "...",
  "request_ts":        "...",
  "total_latency_ms":  147.3,
  "outcome":           "send|escalate|skip|draft",
  "stages": {
    "memory":        { "latency_ms", "status", "cache_hit", "turn_count",
                       "shared_chunks", "shared_entities", "filter_applied" },
    "intelligence":  { "latency_ms", "status", "intent", "confidence",
                       "entity_count", "keyword_count", "multi_intent_count",
                       "query_count", "sentiment", "journey_stage" },
    "response_filter": { "latency_ms", "status", "duplicates_prevented",
                         "explicit_reask", "shared_entity_count" },
    "retrieval":     { "latency_ms", "status", "layers", "cache_hit",
                       "source", "chunks", "confidence", "early_exit",
                       "dedup_removed", "intent_cache_hit", "chunk_cache_hit" },
    "llm":           { "latency_ms", "status", "model", "fallback_tier",
                       "tokens_total", "grounding_pre", "grounding_post",
                       "hallucination_detected", "confidence",
                       "prompt_route", "prompt_tokens_est",
                       "fact_graph_sections", "compression_ratio" },
    "decision":      { "latency_ms", "status", "action", "final_confidence",
                       "escalation_reason", "escalation_priority",
                       "hallucination_score", "risk_score",
                       "refund_risk", "legal_risk", "sentiment_score" }
  }
}
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("automation-service.pipeline_trace")


class PipelineTraceRecorder:
    """
    Records a complete structured trace for one pipeline execution.

    Usage in ExecutionEngine._execute_stages():
        recorder = PipelineTraceRecorder(trace_id, user_id, thread_id, message_id, conv_id)
        recorder.stage_start("memory")
        ...
        recorder.stage_end("memory", status="ok", latency_ms=8.2, cache_hit=True, ...)
        ...
        recorder.finalize(outcome="send", total_latency_ms=142.0)
    """

    def __init__(
        self,
        trace_id: str,
        tenant_id: str,
        thread_id: str,
        message_id: str,
        conversation_id: str,
    ):
        self.trace_id        = trace_id
        self.tenant_id       = tenant_id
        self.thread_id       = thread_id
        self.message_id      = message_id
        self.conversation_id = conversation_id
        self.request_ts      = datetime.now(tz=timezone.utc).isoformat()
        self._stages: Dict[str, Dict[str, Any]] = {}
        self._stage_starts: Dict[str, float] = {}

    # ── Stage lifecycle ───────────────────────────────────────────────────

    def stage_start(self, stage: str) -> None:
        self._stage_starts[stage] = time.perf_counter()
        self._stages[stage] = {"status": "running"}

    def stage_end(self, stage: str, status: str = "ok", **metadata: Any) -> float:
        """
        Mark a stage complete. Returns elapsed ms.
        All keyword args become structured metadata in the trace.
        """
        t_start = self._stage_starts.pop(stage, None)
        elapsed = (time.perf_counter() - t_start) * 1000 if t_start else 0.0

        span: Dict[str, Any] = {"status": status, "latency_ms": round(elapsed, 2)}
        span.update({k: v for k, v in metadata.items() if v is not None})
        self._stages[stage] = span

        level = logging.WARNING if status == "error" else logging.DEBUG
        logger.log(
            level,
            "SPAN | trace=%s stage=%s status=%s latency=%.1fms meta=%s",
            self.trace_id[:12], stage, status, elapsed,
            json.dumps({k: v for k, v in metadata.items() if not isinstance(v, (dict, list))},
                       default=str)[:200],
        )
        return elapsed

    def stage_error(self, stage: str, error: str) -> None:
        t_start = self._stage_starts.pop(stage, None)
        elapsed = (time.perf_counter() - t_start) * 1000 if t_start else 0.0
        self._stages[stage] = {"status": "error", "latency_ms": round(elapsed, 2), "error": error}
        logger.error(
            "SPAN_ERROR | trace=%s stage=%s latency=%.1fms error=%s",
            self.trace_id[:12], stage, elapsed, error[:200],
        )

    # ── Finalize ──────────────────────────────────────────────────────────

    def finalize(self, outcome: str, total_latency_ms: float) -> Dict[str, Any]:
        """
        Emit the complete machine-readable execution trace.
        Returns the trace dict (useful for response metadata).
        """
        trace = {
            "trace_id":         self.trace_id,
            "tenant_id":        self.tenant_id,
            "thread_id":        self.thread_id,
            "message_id":       self.message_id,
            "conversation_id":  self.conversation_id,
            "request_ts":       self.request_ts,
            "completed_ts":     datetime.now(tz=timezone.utc).isoformat(),
            "total_latency_ms": round(total_latency_ms, 2),
            "outcome":          outcome,
            "stages":           self._stages,
        }

        # Single structured log — engineers grep by trace_id to replay the full path
        logger.info(
            "PIPELINE_TRACE | trace=%s tenant=%s outcome=%s total_ms=%.1f "
            "memory_ms=%.1f intel_ms=%.1f retrieval_ms=%.1f llm_ms=%.1f decision_ms=%.1f | "
            "intent=%s confidence=%.2f retrieval_layers=%s cache_hit=%s fallback_tier=%s "
            "hallucination=%s grounding_pre=%.2f grounding_post=%.2f",
            self.trace_id[:16],
            self.tenant_id[:16],
            outcome,
            total_latency_ms,
            self._stages.get("memory",         {}).get("latency_ms", 0),
            self._stages.get("intelligence",    {}).get("latency_ms", 0),
            self._stages.get("retrieval",       {}).get("latency_ms", 0),
            self._stages.get("llm",             {}).get("latency_ms", 0),
            self._stages.get("decision",        {}).get("latency_ms", 0),
            self._stages.get("intelligence",    {}).get("intent",      "unknown"),
            self._stages.get("intelligence",    {}).get("confidence",  0.0),
            self._stages.get("retrieval",       {}).get("layers",      []),
            self._stages.get("retrieval",       {}).get("cache_hit",   False),
            self._stages.get("llm",             {}).get("fallback_tier", 1),
            self._stages.get("llm",             {}).get("hallucination_detected", False),
            self._stages.get("llm",             {}).get("grounding_pre",  0.0),
            self._stages.get("llm",             {}).get("grounding_post", 0.0),
        )

        return trace


# ─────────────────────────────────────────────────────────────────────────────
# Stage metadata extractors — keep extraction logic here, not in execution_engine
# ─────────────────────────────────────────────────────────────────────────────

def memory_span_meta(memory: Dict[str, Any]) -> Dict[str, Any]:
    filter_obs = memory.get("_response_filter")
    if filter_obs and hasattr(filter_obs, "observability"):
        filter_obs = filter_obs.observability
    return {
        "cache_hit":        memory.get("cache_hit", False),
        "turn_count":       memory.get("turn_count", 0),
        "shared_chunks":    len(memory.get("already_shared_chunks", [])),
        "shared_entities":  len(memory.get("already_shared_entities", [])),
        "active_topic":     memory.get("active_topic", ""),
        "journey_stage":    memory.get("customer_journey_stage", ""),
        "filter_applied":   bool(filter_obs),
    }


def intelligence_span_meta(intelligence: Any) -> Dict[str, Any]:
    d: Dict[str, Any] = intelligence if isinstance(intelligence, dict) else {}

    primary_intents = d.get("primary_intents", []) if d else []
    if not d and hasattr(intelligence, "primary_intents"):
        primary_intents = intelligence.primary_intents or []

    first = primary_intents[0] if primary_intents else {}
    intent = (first.get("type") if isinstance(first, dict) else getattr(first, "type", "unknown")) or "unknown"
    conf   = (first.get("confidence") if isinstance(first, dict) else getattr(first, "confidence", 0.0)) or 0.0

    ents = d.get("entities", {}) if d else getattr(intelligence, "entities", {})
    ents_d = ents if isinstance(ents, dict) else (ents.model_dump() if hasattr(ents, "model_dump") else (ents.__dict__ if hasattr(ents, "__dict__") else {}))
    entity_count = len(ents_d.get("products", []) or []) + len(ents_d.get("features", []) or [])

    sp = d.get("search_plan", {}) if d else getattr(intelligence, "search_plan", {})
    sp_d = sp if isinstance(sp, dict) else (sp.model_dump() if hasattr(sp, "model_dump") else (sp.__dict__ if hasattr(sp, "__dict__") else {}))
    query_count = len(sp_d.get("semantic_queries", []) or []) + len(sp_d.get("exact_search_queries", []) or [])

    conv = d.get("conversation_analysis", {}) if d else getattr(intelligence, "conversation_analysis", {})
    conv_d = conv if isinstance(conv, dict) else (conv.model_dump() if hasattr(conv, "model_dump") else (conv.__dict__ if hasattr(conv, "__dict__") else {}))

    return {
        "intent":              str(intent),
        "confidence":          round(float(conf), 3),
        "entity_count":        entity_count,
        "keyword_count":       len(sp_d.get("pricing_queries", []) or []),
        "multi_intent_count":  len(d.get("secondary_intents", []) or []) if d else len(getattr(intelligence, "secondary_intents", []) or []),
        "query_count":         query_count,
        "sentiment":           str(conv_d.get("sentiment", "neutral")),
        "journey_stage":       str(conv_d.get("stage", "discovery")),
        "is_continuation":     bool(d.get("is_continuation", False) if d else getattr(intelligence, "is_continuation", False)),
    }


def response_filter_span_meta(rf: Any) -> Dict[str, Any]:
    if rf is None:
        return {"status": "skipped"}
    obs = rf.observability if hasattr(rf, "observability") else {}
    return {
        "duplicates_prevented": obs.get("duplication_prevented", False),
        "explicit_reask":       obs.get("is_explicit_reask", False),
        "shared_entity_count":  obs.get("shared_entity_count", 0),
        "filter_latency_ms":    obs.get("filter_latency_ms", 0.0),
    }


def retrieval_span_meta(retrieval: Dict[str, Any]) -> Dict[str, Any]:
    layers = retrieval.get("layers_used", [])
    source = "cache" if retrieval.get("cache_hit") else (
        "qdrant" if any("SEMANTIC" in l or "BM25" in l or "EXACT" in l for l in layers) else "hybrid"
    )
    return {
        "layers":            layers,
        "cache_hit":         retrieval.get("cache_hit", False),
        "intent_cache_hit":  "L1_INTENT_CACHE" in layers,
        "chunk_cache_hit":   "L2_CHUNK_CACHE" in layers,
        "source":            source,
        "chunks":            len(retrieval.get("chunks", [])),
        "total_retrieved":   retrieval.get("total_retrieved", 0),
        "confidence":        round(retrieval.get("retrieval_confidence", 0.0), 3),
        "early_exit":        retrieval.get("early_exit", False),
        "validation_passed": retrieval.get("validation_passed", 0),
        "validation_rejected": retrieval.get("validation_rejected", 0),
    }


def llm_span_meta(llm_result: Dict[str, Any]) -> Dict[str, Any]:
    pg = llm_result.get("pre_gen_grounding", {})
    return {
        "model":                  llm_result.get("model", "unknown"),
        "fallback_tier":          llm_result.get("fallback_tier", 1),
        "fallback_tier_name":     llm_result.get("fallback_tier_name", "openai_gpt"),
        "tokens_total":           llm_result.get("tokens_used", 0),
        "confidence":             round(llm_result.get("confidence", 0.0), 3),
        "hallucination_detected": llm_result.get("hallucination_detected", False),
        "grounding_pre":          round(pg.get("overall_confidence", 0.0), 3),
        "grounding_post":         round(llm_result.get("grounding_score", 0.0), 3),
        "accepted_chunks":        pg.get("accepted_chunks", 0),
        "rejected_chunks":        pg.get("rejected_chunks", 0),
        "pricing_conflicts":      pg.get("pricing_conflicts", 0),
        "escalate":               pg.get("escalate", False),
        # prompt observability (populated when PromptBuildResult is attached)
        "prompt_route":           llm_result.get("prompt_route", ""),
        "prompt_tokens_est":      llm_result.get("prompt_tokens_est", 0),
        "fact_graph_sections":    llm_result.get("fact_graph_sections", 0),
        "compression_ratio":      llm_result.get("compression_ratio", 1.0),
    }


def decision_span_meta(decision: Dict[str, Any], llm_result: Dict[str, Any], intelligence: Any) -> Dict[str, Any]:
    conv = {}
    if isinstance(intelligence, dict):
        conv = intelligence.get("conversation_analysis", {}) or {}
    else:
        ca = getattr(intelligence, "conversation_analysis", None)
        if ca:
            conv = ca.__dict__ if hasattr(ca, "__dict__") else {}

    sentiment = str(conv.get("sentiment", "neutral"))
    urgency   = str(conv.get("urgency", "medium"))

    # Risk signals from decision dict (may or may not exist depending on handoff version)
    return {
        "action":             decision.get("action", "unknown"),
        "final_confidence":   round(decision.get("final_confidence", 0.0), 3),
        "escalation_reason":  decision.get("escalation_reason"),
        "escalation_priority": decision.get("escalation_priority"),
        "hallucination_score": round(llm_result.get("grounding_score", 0.0), 3),
        "confidence_score":   round(decision.get("final_confidence", 0.0), 3),
        "customer_sentiment": sentiment,
        "urgency":            urgency,
        "refund_risk":        "refund" in str(decision.get("escalation_reason", "")).lower(),
        "legal_risk":         "legal" in str(decision.get("escalation_reason", "")).lower(),
        "vip_risk":           urgency in ("critical", "high"),
    }


__all__ = [
    "PipelineTraceRecorder",
    "memory_span_meta",
    "intelligence_span_meta",
    "response_filter_span_meta",
    "retrieval_span_meta",
    "llm_span_meta",
    "decision_span_meta",
]
