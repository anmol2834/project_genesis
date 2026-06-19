"""
Orchestration - Execution Engine
==================================
Enterprise AI workflow execution engine with distributed coordination.
"""
import asyncio
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models.events import AutomationEvent, ResponseEvent
from app.models.observability import TraceContext
from app.observability import get_tracer, get_logger, get_metrics_collector

logger = get_logger(__name__)

class ExecutionState:
    """Workflow execution state"""
    RECEIVED = "received"
    MEMORY_LOADED = "memory_loaded"
    INTELLIGENCE_COMPLETED = "intelligence_completed"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    VALIDATION_COMPLETED = "validation_completed"
    GROUNDING_VALIDATED = "grounding_validated"
    LLM_COMPLETED = "llm_completed"
    HALLUCINATION_CHECKED = "hallucination_checked"
    CONFIDENCE_EVALUATED = "confidence_evaluated"
    HANDOFF_TRIGGERED = "handoff_triggered"
    RESPONSE_SENT = "response_sent"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"

class WorkflowExecutionContext:
    """
    Workflow execution context for a single pipeline run.

    Renamed from ExecutionContext → WorkflowExecutionContext (Task 9 / R19)
    to eliminate the name collision with app.core.execution_context.ExecutionContext
    (the dataclass with contextvars propagation).  The collision broke distributed
    trace propagation because workers set the core ExecutionContext in contextvars
    but the orchestration engine stored a completely different object under the
    same name, making trace IDs non-propagatable across the worker → pipeline boundary.
    """
    def __init__(
        self,
        trace_id: str,
        correlation_id: str,
        user_id: str,
        workflow_id: str,
        execution_id: str
    ):
        self.trace_id = trace_id
        self.correlation_id = correlation_id
        self.user_id = user_id
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.state = ExecutionState.RECEIVED
        self.started_at = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}
        self.layer_results: Dict[str, Any] = {}
        self.timings: Dict[str, float] = {}

    def set_state(self, state: str):
        """Update execution state"""
        self.state = state
        self.metadata[f"{state}_at"] = datetime.utcnow().isoformat()

class ExecutionEngine:
    """Enterprise workflow execution engine"""
    
    def __init__(self):
        self.tracer = get_tracer()
        self.metrics = get_metrics_collector()
        self.active_executions: Dict[str, WorkflowExecutionContext] = {}

    def create_execution_context(self, event: AutomationEvent) -> WorkflowExecutionContext:
        """Create workflow execution context from event"""
        execution_id = str(uuid.uuid4())
        workflow_id = f"wf_{event.conversation_id}"

        ctx = WorkflowExecutionContext(
            trace_id=event.trace_id or str(uuid.uuid4()),
            correlation_id=event.correlation_id or event.trace_id or str(uuid.uuid4()),
            user_id=event.user_id,
            workflow_id=workflow_id,
            execution_id=execution_id
        )

        self.active_executions[execution_id] = ctx
        return ctx
    
    async def execute_workflow(self, event: AutomationEvent) -> ResponseEvent:
        """Execute complete AI workflow with orchestration"""
        ctx = self.create_execution_context(event)
        
        logger.info(
            f"Starting workflow execution",
            user_id=ctx.user_id,
            trace_id=ctx.trace_id,
            workflow_id=ctx.workflow_id,
            execution_id=ctx.execution_id
        )
        
        try:
            # Execute workflow stages
            result = await self._execute_stages(ctx, event)
            response = self._create_response_event(ctx, event, result)
            ctx.set_state(ExecutionState.RESPONSE_SENT)
            
            return response
            
        except Exception as e:
            logger.error(f"Workflow execution failed", user_id=ctx.user_id, trace_id=ctx.trace_id, error=e)
            ctx.set_state(ExecutionState.FAILED)
            raise
        finally:
            if ctx.execution_id in self.active_executions:
                del self.active_executions[ctx.execution_id]
    
    async def _execute_stages(self, ctx: WorkflowExecutionContext, event: AutomationEvent) -> Dict[str, Any]:
        """Execute workflow stages with full distributed tracing, tenant isolation, and priority routing."""
        import time
        from app.memory.orchestrator import get_memory_orchestrator
        from app.intelligence.orchestrator import get_intelligence_orchestrator
        from app.retrieval.orchestrator import get_retrieval_orchestrator
        from app.llm.orchestrator import get_llm_orchestrator
        from app.handoff.orchestrator import get_handoff_orchestrator
        from app.observability.pipeline_trace import (
            PipelineTraceRecorder,
            memory_span_meta, intelligence_span_meta, response_filter_span_meta,
            retrieval_span_meta, llm_span_meta, decision_span_meta,
        )
        from app.core.tenant_context import TenantContext, Priority
        from app.orchestration.priority_classifier import get_priority_classifier, RetrievalBudget

        memory_orch       = get_memory_orchestrator()
        intelligence_orch = get_intelligence_orchestrator()
        retrieval_orch    = get_retrieval_orchestrator()
        llm_orch          = get_llm_orchestrator()
        handoff_orch      = get_handoff_orchestrator()

        pipeline_start = time.perf_counter()

        # ── Build immutable TenantContext (validates tenant_id is present) ─
        tenant_ctx = TenantContext(
            tenant_id=ctx.user_id,
            trace_id=ctx.trace_id,
            thread_id=event.thread_id,
            conversation_id=event.conversation_id,
            message_id=event.message_id,
        )

        recorder = PipelineTraceRecorder(
            trace_id=ctx.trace_id,
            tenant_id=ctx.user_id,
            thread_id=event.thread_id,
            message_id=event.message_id,
            conversation_id=event.conversation_id,
        )

        # ── Stage 1: Load Intelligence Memory ────────────────────────────
        recorder.stage_start("memory")
        try:
            memory = await memory_orch.load_memory(
                user_id=ctx.user_id,
                conversation_id=event.conversation_id,
                thread_id=event.thread_id,
                trace_id=ctx.trace_id,
            )
            ctx.timings["memory_load"] = recorder.stage_end(
                "memory", status="ok", **memory_span_meta(memory)
            )
        except Exception as e:
            recorder.stage_error("memory", str(e))
            raise
        ctx.set_state(ExecutionState.MEMORY_LOADED)
        ctx.layer_results["memory"] = memory

        # ── Stage 2: Intelligence ─────────────────────────────────────────
        # Pre-filter: skip transactional/automated emails before calling Brain #1
        if self._is_transactional_email(event):
            logger.info(
                "Transactional email filtered | from=%s subject=%s",
                getattr(event, "from_email", "")[:40],
                getattr(event, "subject", "")[:60],
                trace_id=ctx.trace_id,
            )
            return {
                "memory": memory, "intelligence": None, "retrieval": {},
                "llm_result": {"response_text": "", "confidence": 1.0},
                "decision": {"action": "skip", "should_send": False,
                             "final_confidence": 1.0, "escalation_reason": None,
                             "escalation_priority": None},
                "response_filter": None, "pipeline_trace": {}, "priority": {},
                "security": {},
            }

        # ── Greeting fast-path: bypass retrieval + LLM for pure greetings ─
        # A greeting with no question and no subject keyword goes through a
        # deterministic response — zero OpenAI calls, zero Qdrant queries.
        greeting_response = self._try_greeting_fast_path(event, memory)
        if greeting_response is not None:
            logger.info(
                "Greeting fast-path | latency<50ms | msg=%s",
                event.message_id[:12], trace_id=ctx.trace_id,
            )
            total_ms = (time.perf_counter() - pipeline_start) * 1000
            return {
                "memory": memory,
                "intelligence": None,
                "retrieval": {"chunks": [], "retrieval_confidence": 1.0, "layers_used": ["GREETING_FAST_PATH"]},
                "llm_result": {
                    "response_text": greeting_response,
                    "confidence": 0.95,
                    "hallucination_detected": False,
                    "grounding_score": 0.95,
                    "fallback_tier": 0,
                    "fallback_tier_name": "greeting_fast_path",
                    "fallback_error_chain": [],
                    "escalate_to_human": False,
                    "pre_gen_grounding": {"escalate": False, "overall_confidence": 0.95,
                                         "accepted_chunks": 0, "rejected_chunks": 0,
                                         "pricing_conflicts": 0, "tenant_violations": 0,
                                         "category_violations": 0},
                },
                "decision": {"action": "send", "should_send": True,
                             "final_confidence": 0.95, "escalation_reason": None,
                             "escalation_priority": None},
                "response_filter": None,
                "pipeline_trace": recorder.finalize(outcome="send", total_latency_ms=total_ms),
                "priority": {"priority": "low", "priority_int": 3},
                "security": tenant_ctx.security_summary(),
            }

        recorder.stage_start("intelligence")
        try:
            intelligence = await intelligence_orch.understand_intent(
                message_content=event.content,
                subject=event.subject,
                memory=memory,
                trace_id=ctx.trace_id,
            )
            ctx.timings["intelligence"] = recorder.stage_end(
                "intelligence", status="ok", **intelligence_span_meta(intelligence)
            )
        except Exception as e:
            recorder.stage_error("intelligence", str(e))
            raise
        ctx.set_state(ExecutionState.INTELLIGENCE_COMPLETED)
        ctx.layer_results["intelligence"] = intelligence

        # ── Stage 2.5: Priority Classification ───────────────────────────
        # Runs immediately after intelligence, before retrieval.
        classifier = get_priority_classifier()
        priority_result = classifier.classify(
            message_content=event.content,
            intelligence=intelligence,
            memory=memory,
            event_priority=event.priority,
        )
        # Attach priority to tenant context (immutable after this point)
        object.__setattr__(tenant_ctx, "priority",        priority_result.priority)
        object.__setattr__(tenant_ctx, "priority_reason", priority_result.reason)
        ctx.metadata["priority"]         = priority_result.to_dict()
        ctx.metadata["priority_level"]   = priority_result.priority
        ctx.metadata["priority_reason"]  = priority_result.reason

        # P0: log security/legal incident for auditing
        if priority_result.priority == Priority.P0_CRITICAL:
            logger.warning(
                "🚨 P0_CRITICAL | tenant=%s trace=%s reason=%s signals=%s",
                ctx.user_id[:12], ctx.trace_id[:12],
                priority_result.reason, priority_result.signals,
                trace_id=ctx.trace_id,
            )
            self.metrics.record_counter("pipeline.priority.p0_critical", 1, ctx.user_id)

        # Get retrieval budget for this priority
        budget = RetrievalBudget.for_priority(priority_result.priority)
        # Inject into memory for retrieval orchestrator to use
        memory["_priority"] = priority_result.priority
        memory["_retrieval_budget"] = budget

        # ── Stage 2.6: Response Repetition Filter ────────────────────────
        recorder.stage_start("response_filter")
        try:
            response_filter = await memory_orch.check_response_filter(
                thread_id=event.thread_id,
                message_content=event.content,
                intelligence=intelligence,
            )
            ctx.timings["response_filter"] = recorder.stage_end(
                "response_filter", status="ok",
                **response_filter_span_meta(response_filter),
            )
        except Exception as e:
            recorder.stage_error("response_filter", str(e))
            response_filter = None
        ctx.layer_results["response_filter"] = response_filter
        ctx.metadata["response_filter_obs"] = (
            response_filter.observability if response_filter else {}
        )
        memory["_response_filter"] = response_filter

        # ── Stage 3: Retrieval ────────────────────────────────────────────
        recorder.stage_start("retrieval")
        try:
            retrieval = await retrieval_orch.retrieve(
                intelligence=intelligence,
                memory=memory,
                user_id=ctx.user_id,
                trace_id=ctx.trace_id,
            )
            # Hard tenant filter: discard any cross-tenant chunks that slipped through
            clean_chunks, cross_tenant_rejected = tenant_ctx.filter_chunks_by_tenant(
                retrieval.get("chunks", [])
            )
            if cross_tenant_rejected:
                retrieval["chunks"] = clean_chunks
                retrieval["cross_tenant_rejected"] = cross_tenant_rejected
                self.metrics.record_counter(
                    "pipeline.security.cross_tenant_chunks_rejected",
                    cross_tenant_rejected,
                    ctx.user_id,
                )
            ctx.timings["retrieval"] = recorder.stage_end(
                "retrieval", status="ok",
                cross_tenant_rejected=cross_tenant_rejected,
                **retrieval_span_meta(retrieval),
            )
        except Exception as e:
            recorder.stage_error("retrieval", str(e))
            raise
        ctx.set_state(ExecutionState.RETRIEVAL_COMPLETED)
        ctx.layer_results["retrieval"] = retrieval

        # ── Stage 3.5: Analytics Fallback (cache-first, Qdrant-second) ──
        # For discovery/greeting intents, inject analytics context so Brain #2
        # has real business facts. Reads from memory cache first — Qdrant only
        # on the first discovery turn. Subsequent turns reuse the cache.
        retrieval = await self._inject_analytics_if_needed(
            retrieval=retrieval,
            intelligence=intelligence,
            user_id=ctx.user_id,
            trace_id=ctx.trace_id,
            memory=memory,
            message_content=event.content,
            subject=event.subject,
        )

        # ── Stage 4: LLM Generation ───────────────────────────────────────
        recorder.stage_start("llm")
        try:
            llm_result = await llm_orch.generate_response(
                intelligence=intelligence,
                retrieval=retrieval,
                memory=memory,
                message_content=event.content,
                subject=event.subject,
                trace_id=ctx.trace_id,
            )
            ctx.timings["llm"] = recorder.stage_end(
                "llm", status="ok", **llm_span_meta(llm_result)
            )
        except Exception as e:
            recorder.stage_error("llm", str(e))
            raise
        ctx.set_state(ExecutionState.GROUNDING_VALIDATED)
        ctx.set_state(ExecutionState.LLM_COMPLETED)
        ctx.set_state(ExecutionState.HALLUCINATION_CHECKED)
        ctx.layer_results["llm"] = llm_result

        grounding_meta = llm_result.get("pre_gen_grounding", {})
        if grounding_meta.get("escalate"):
            ctx.metadata["grounding_escalation"] = True
            ctx.metadata["grounding_confidence"] = grounding_meta.get("overall_confidence", 0.0)

        # ── Stage 5: Handoff Decision (priority-aware) ────────────────────
        recorder.stage_start("decision")
        try:
            decision = await handoff_orch.make_decision(
                intelligence=intelligence,
                retrieval=retrieval,
                llm_result=llm_result,
                memory=memory,
                trace_id=ctx.trace_id,
                priority=priority_result.priority,
                priority_reason=priority_result.reason,
            )
            ctx.timings["decision"] = recorder.stage_end(
                "decision", status="ok",
                priority=Priority.label(priority_result.priority),
                **decision_span_meta(decision, llm_result, intelligence),
            )
        except Exception as e:
            recorder.stage_error("decision", str(e))
            raise
        ctx.set_state(ExecutionState.CONFIDENCE_EVALUATED)
        ctx.layer_results["decision"] = decision

        # ── Stage 6: Intelligence-Aware Memory Update ─────────────────────
        await memory_orch.update_memory(
            thread_id=event.thread_id,
            intelligence=intelligence,
            retrieval=retrieval,
            llm_result=llm_result,
            trace_id=ctx.trace_id,
        )

        # ── Finalize trace ────────────────────────────────────────────────
        total_ms = (time.perf_counter() - pipeline_start) * 1000
        trace = recorder.finalize(
            outcome=decision.get("action", "unknown"),
            total_latency_ms=total_ms,
        )
        ctx.metadata["pipeline_trace"] = trace

        # Record aggregate metrics
        self.metrics.record_histogram("pipeline.total_latency_ms", total_ms, ctx.user_id)
        self.metrics.record_counter(
            f"pipeline.outcome.{decision.get('action', 'unknown')}", 1, ctx.user_id
        )
        self.metrics.record_counter(
            f"pipeline.priority.{Priority.label(priority_result.priority)}", 1, ctx.user_id
        )
        if llm_result.get("hallucination_detected"):
            self.metrics.record_counter("pipeline.hallucination_detected", 1, ctx.user_id)
        if retrieval.get("cache_hit"):
            self.metrics.record_counter("pipeline.retrieval_cache_hit", 1, ctx.user_id)

        # Security summary metrics
        sec = tenant_ctx.security_summary()
        if sec["security_incidents"] > 0:
            self.metrics.record_counter(
                "pipeline.security.incidents", sec["security_incidents"], ctx.user_id
            )

        return {
            "memory":          memory,
            "intelligence":    intelligence,
            "retrieval":       retrieval,
            "llm_result":      llm_result,
            "decision":        decision,
            "response_filter": response_filter,
            "pipeline_trace":  trace,
            "priority":        priority_result.to_dict(),
            "security":        sec,
        }
    

    
    async def _inject_analytics_if_needed(
        self,
        retrieval: Dict,
        intelligence: Any,
        user_id: str,
        trace_id: str,
        memory: Optional[Dict] = None,
        message_content: str = "",
        subject: str = "",
    ) -> Dict:
        """
        Inject data_analytics context for genuine discovery/inquiry intents.

        Gate: only injects when the current message contains information-seeking
        signals (product/price/support/etc. in body OR subject). Pure greetings
        with no subject intent are excluded even if intent=general_inquiry.

        Cache-first: if memory already holds a discovery_context from a
        previous turn, rebuild analytics chunks from it without hitting
        Qdrant at all (zero extra I/O on continuations).
        """
        if retrieval.get("_analytics_injected"):
            return retrieval

        existing_chunks = retrieval.get("chunks", [])
        conf = retrieval.get("retrieval_confidence", 0.0)

        # SOURCE PRIORITY ENFORCEMENT
        # Analytics MUST be lowest priority. Append AFTER existing chunks,
        # not before. Give analytics a capped score so they never outrank
        # real product/service records in the fact graph.
        _ANALYTICS_MAX_SCORE = 0.40

        generic_intents = {"follow_up", "general_inquiry", "greeting", "unknown", "follow-up"}
        intent_str = "unknown"
        analytics_allowed = False
        if hasattr(intelligence, "primary_intents") and intelligence.primary_intents:
            t = intelligence.primary_intents[0].type
            intent_str = (t.value if hasattr(t, "value") else str(t)).lower()
        # Check Brain #1's explicit analytics_allowed flag
        if hasattr(intelligence, "retrieval_strategy") and intelligence.retrieval_strategy:
            analytics_allowed = getattr(intelligence.retrieval_strategy, "analytics_allowed", False)

        # Analytics are ONLY allowed when:
        # 1. Brain #1 explicitly set analytics_allowed=True, OR
        # 2. User explicitly asked for stats/reports/analytics/trends/insights, OR
        # 3. Message contains catalog-overview signals (range, how many, list all, etc.)
        _ANALYTICS_EXPLICIT_SIGNALS = {
            "analytics", "statistics", "stats", "report", "reports",
            "trend", "trends", "insight", "insights", "summary", "summaries",
            "how many", "total count", "overview report",
        }
        # Catalog-overview signals: user wants a high-level view of what's available.
        # These ALWAYS need analytics context because individual product chunks
        # cannot answer "what range do you have" or "how many products" questions.
        _CATALOG_OVERVIEW_SIGNALS = {
            "range", "ranges", "overview", "all products", "all services",
            "what do you have", "what do you offer", "what you have",
            "what you offer", "what you sell", "list of products", "list of services",
            "show me all", "show all", "full catalog", "complete catalog",
            "catalogue", "how many products", "how many items", "total products",
            "price range", "pricing range", "cost range", "minimum price",
            "maximum price", "cheapest", "most expensive", "starting from",
            "starts at", "from what price", "what is the range",
            "entire range", "whole range", "product line", "service line",
        }
        combined_text = f"{message_content} {subject}".lower()
        user_wants_analytics = any(s in combined_text for s in _ANALYTICS_EXPLICIT_SIGNALS)
        user_wants_catalog_overview = any(s in combined_text for s in _CATALOG_OVERVIEW_SIGNALS)

        # Relevance gate: analytics should NOT inject for pure greetings or
        # generic questions (contact, help, etc.) unrelated to products/pricing.
        # Only inject when message contains genuine product/catalog discovery signals.
        _DISCOVERY_SIGNALS = {
            "product", "service", "price", "cost", "buy", "order", "offer",
            "discount", "feature", "spec", "available", "catalog", "range",
            "delivery", "policy", "refund", "enquiry", "inquiry",
            "laptop", "model", "compare", "recommend", "option",
            "cheapest", "expensive", "budget", "premium", "gaming",
            "wanna", "want", "tell me", "show", "list", "what do you", "what you have",
            # Company/contact signals
            "company", "business", "about", "who are", "contact", "reach", "support",
            "phone", "email", "address", "help", "team", "department",
        }
        # Block analytics injection when query is clearly off-catalog
        # (account issues, generic help, etc.)
        _ANALYTICS_BLOCKLIST = {
            "account", "login", "password", "reset", "sign in", "sign up",
        }
        combined_text = f"{message_content} {subject}".lower()
        has_discovery_signal = (
            any(s in combined_text for s in _DISCOVERY_SIGNALS)
            and not any(b in combined_text for b in _ANALYTICS_BLOCKLIST)
        )

        # Intent is specific (non-generic): always allow analytics
        # Intent is generic but message has discovery signals: allow
        # Intent is generic and no discovery signals: block (pure greeting)
        # pricing_inquiry / product_inquiry ALWAYS get analytics
        catalog_intents = {"pricing_inquiry", "product_inquiry"}
        has_info_intent = (
            intent_str not in generic_intents
            or has_discovery_signal
        )

        # Analytics inject ONLY when:
        # - user explicitly wants analytics (stats/reports/trends), OR
        # - Brain #1 explicitly permitted it, AND
        # - existing product chunks are insufficient
        # Analytics NEVER inject for product_inquiry when product chunks already exist.
        product_intents = {"product_inquiry", "pricing_inquiry", "feature_request"}
        # Intents that ALWAYS need business_context injection regardless of existing chunks
        business_context_intents = {"company_inquiry", "contact_inquiry"}
        has_product_chunks = any(
            str(c.get("chunk_type", "")).lower() in ("product_service", "product")
            for c in existing_chunks
        )

        # Block analytics when product chunks already satisfy product/pricing requests
        # EXCEPTION: catalog overview queries ("range", "all products", "what do you have")
        # always need analytics context even if individual product chunks exist.
        if intent_str in product_intents and has_product_chunks and not user_wants_catalog_overview:
            logger.debug(
                "analytics_injection_blocked | product_chunks_exist=%d intent=%s",
                len([c for c in existing_chunks if str(c.get("chunk_type", "")).lower() in ("product_service", "product")]),
                intent_str,
            )
            return retrieval

        # DEDUP PROTECTION: when retrieval confidence is high (intent-cache hit with real data)
        # but existing_chunks is empty because dedup removed all previously-shown chunks,
        # do NOT fall through to analytics injection for product/pricing intents.
        # Injecting delivery/education analytics when the user asks "tell me which products"
        # is worse than showing no context — the LLM will format analytics as "products".
        #
        # Instead: skip analytics injection entirely. The fact_graph compressor will produce
        # an empty products section → the LLM prompt will say "no specific verified information"
        # and gracefully prompt the user to ask about something new or specific.
        # This is far better than sending "20 delivery options" as an answer to "which products".
        if intent_str in product_intents and not has_product_chunks and not user_wants_catalog_overview:
            retrieval_conf = retrieval.get("retrieval_confidence", 0.0)
            cache_hit = retrieval.get("cache_hit", False)
            if retrieval_conf >= 0.70 or cache_hit:
                # High-confidence retrieval that was deduped → all chunks were already shown.
                # Don't inject analytics; let the LLM gracefully say the catalog was already shared.
                logger.info(
                    "analytics_injection_blocked_dedup | intent=%s conf=%.2f cache_hit=%s "
                    "existing_chunks=0 (all deduped — catalog already presented)",
                    intent_str, retrieval_conf, cache_hit,
                )
                return retrieval

        # Company inquiry ALWAYS needs business_context injection — no gate
        is_business_context_request = intent_str in business_context_intents

        # Only inject when no product data exists and it's a discovery/generic query
        needs_analytics = (
            is_business_context_request   # company/contact queries always get context
            or (analytics_allowed or user_wants_analytics)
            or user_wants_catalog_overview  # catalog-overview queries always need analytics
            or (
                has_discovery_signal
                and not has_product_chunks
                and intent_str not in product_intents
            )
            or (
                # Fallback: no chunks at all — inject analytics as last resort
                not existing_chunks
                and has_discovery_signal
            )
        )

        if not needs_analytics:
            return retrieval

        # ── CACHE-FIRST: reuse discovery_context stored by a previous turn ─
        mem = memory or {}
        cached_discovery = mem.get("discovery_context")

        # ── Intent-aware cache filtering ──────────────────────────────────
        # The discovery_context cache may contain analytics from a DIFFERENT intent
        # (e.g. delivery+education analytics from a support_request turn).
        # When intent has changed, filter the cache to only inject analytics
        # that are RELEVANT to the current intent.
        #
        # Intent → relevant primary_category in analytics structured_data:
        _INTENT_TO_ANALYTICS_CATEGORY = {
            "product_inquiry":    "product_service",
            "pricing_inquiry":    "product_service",
            "offers_inquiry":     "offers_promotions",
            "shipping_inquiry":   "delivery_shipping",
            "educational_inquiry":"educational_content",
            "support_request":    "contact_support",
            "technical_support_request": "contact_support",
            "company_inquiry":    "company_info",
            "refund_request":     "policies_legal",
        }
        target_analytics_cat = _INTENT_TO_ANALYTICS_CATEGORY.get(intent_str)

        # For offers_inquiry: ONLY inject offers analytics, never delivery/education
        # For product_inquiry: ONLY inject product analytics, never delivery/education
        # For other specific intents with a known category: filter accordingly
        # For generic/catalog-overview queries: keep all analytics
        if cached_discovery and isinstance(cached_discovery, list) and cached_discovery:
            if target_analytics_cat and not user_wants_catalog_overview:
                # Filter cache to only chunks whose primary_category matches
                filtered_cache = []
                for c in cached_discovery:
                    # Check structured_data.primary_category or attributes.primary_category
                    meta = c.get("metadata") or {}
                    if not isinstance(meta, dict):
                        meta = {}
                    sd   = meta.get("structured_data") or c.get("structured_data") or {}
                    attr = meta.get("attributes") or c.get("attributes") or {}
                    chunk_cat = (
                        (sd.get("primary_category") if isinstance(sd, dict) else "")
                        or (attr.get("primary_category") if isinstance(attr, dict) else "")
                        or (meta.get("category") if isinstance(meta, dict) else "")
                        or ""
                    ).lower()
                    if chunk_cat == target_analytics_cat:
                        filtered_cache.append(c)
                # If no matching analytics in cache → bypass cache, fall through to Qdrant fetch
                if not filtered_cache:
                    logger.info(
                        "discovery_cache_filtered | intent=%s target_cat=%s "
                        "cache_size=%d filtered=0 → falling through to Qdrant",
                        intent_str, target_analytics_cat, len(cached_discovery),
                        trace_id=trace_id,
                    )
                    cached_discovery = None  # Force Qdrant fetch for correct analytics
                else:
                    cached_discovery = filtered_cache
                    logger.info(
                        "discovery_cache_filtered | intent=%s target_cat=%s "
                        "cache_size→filtered=%d→%d",
                        intent_str, target_analytics_cat,
                        len(filtered_cache) + (len(mem.get("discovery_context", [])) - len(filtered_cache)),
                        len(filtered_cache),
                        trace_id=trace_id,
                    )

        if cached_discovery and isinstance(cached_discovery, list) and cached_discovery:
            # Apply score cap before injecting from cache
            capped_cache = [
                dict(c, score=min(c.get("score", 0.4), _ANALYTICS_MAX_SCORE))
                for c in cached_discovery
            ]
            logger.info(
                "discovery_mode_triggered | analytics_cache_hit=True "
                "intent=%s chunks_from_cache=%d",
                intent_str, len(capped_cache),
                trace_id=trace_id,
            )
            retrieval = dict(retrieval)
            # Analytics APPENDED AFTER product chunks — never before
            retrieval["chunks"] = existing_chunks + capped_cache
            retrieval["_analytics_injected"] = True
            retrieval["_analytics_from_cache"] = True
            retrieval["retrieval_confidence"] = max(conf, 0.45)
            if "L_ANALYTICS" not in retrieval.get("layers_used", []):
                retrieval["layers_used"] = retrieval.get("layers_used", []) + ["L_ANALYTICS"]
            return retrieval

        # ── QDRANT FETCH: first discovery turn, no cache yet ─────────────
        logger.info(
            "discovery_mode_triggered | analytics_cache_miss=True intent=%s",
            intent_str, trace_id=trace_id,
        )
        try:
            from app.core.resource_management import get_resource_manager
            qdrant_repo = get_resource_manager().get_qdrant_repository()

            # For company_inquiry: fetch from business_context collection (profile data)
            # which contains business_core, use_case, audience, tone, instruction records
            if intent_str == "company_inquiry":
                # Fetch business context profile chunks
                profile_chunks = await qdrant_repo.scroll(
                    user_id=user_id,
                    filters={"chunk_type": "profile"},  # profile type in business_context
                    limit=5,
                )
                if profile_chunks:
                    formatted = []
                    for record in profile_chunks:
                        payload = record.get("payload", {})
                        content = payload.get("content") or ""
                        if content:
                            formatted.append({
                                "content":         content,
                                "score":           0.70,
                                "chunk_type":      "profile",
                                "chunk_id":        str(record.get("id", "")),
                                "source":          "business_context",
                                "retrieval_layer": "L_BUSINESS_CONTEXT",
                                "metadata":        payload,
                                "user_id":         user_id,
                            })
                    if formatted:
                        retrieval = dict(retrieval)
                        retrieval["chunks"] = existing_chunks + formatted
                        retrieval["_analytics_injected"] = True
                        retrieval["_analytics_from_cache"] = False
                        retrieval["retrieval_confidence"] = max(conf, 0.65)
                        if "L_BUSINESS_CONTEXT" not in retrieval.get("layers_used", []):
                            retrieval["layers_used"] = retrieval.get("layers_used", []) + ["L_BUSINESS_CONTEXT"]
                        logger.info(
                            "business_context_injected | intent=%s profile_chunks=%d",
                            intent_str, len(formatted), trace_id=trace_id,
                        )
                        return retrieval

            # Fetch analytics filtered to the current intent's relevant category.
            # Fetching all 7 analytics chunks and injecting unrelated ones is the root
            # cause of "delivery options" appearing in product queries, and
            # "I don't have offers" when offers analytics are buried under 2 irrelevant ones.
            #
            # Strategy:
            # - If we have a specific target category → fetch only that analytics chunk (limit=1)
            # - For catalog-overview / generic queries → fetch up to 3 (product analytics preferred)
            # - Always save the fetched chunk(s) to discovery_context for future turns
            if target_analytics_cat and not user_wants_catalog_overview:
                # Intent-specific: only fetch the analytics chunk for this category
                analytics_chunks = await qdrant_repo.scroll(
                    user_id=user_id,
                    filters={
                        "category": "data_analytics",
                        "primary_category": target_analytics_cat,  # matched in structured_data
                    },
                    limit=1,
                )
                # Fallback: if primary_category filter not supported, fetch all and filter
                if not analytics_chunks:
                    all_analytics = await qdrant_repo.scroll(
                        user_id=user_id,
                        filters={"category": "data_analytics"},
                        limit=7,  # fetch all to filter locally
                    )
                    analytics_chunks = [
                        r for r in all_analytics
                        if _match_analytics_category(r, target_analytics_cat)
                    ][:1]
            else:
                analytics_chunks = await qdrant_repo.scroll(
                    user_id=user_id,
                    filters={"category": "data_analytics"},
                    limit=3,
                )

            analytics_found = len(analytics_chunks)
            logger.info(
                "analytics_found=%d intent=%s existing_chunks=%d conf=%.2f",
                analytics_found, intent_str, len(existing_chunks), conf,
                trace_id=trace_id,
            )

            if analytics_chunks:
                formatted = []
                for record in analytics_chunks:
                    payload = record.get("payload", {})
                    content = (
                        payload.get("content")
                        or payload.get("search_text")
                        or payload.get("title")
                        or payload.get("description")
                        or payload.get("summary")
                        or payload.get("text")
                        or ""
                    )
                    if not content:
                        sd = payload.get("structured_data") or {}
                        attrs = payload.get("attributes") or {}
                        parts = []
                        for src in (sd, attrs, payload):
                            if isinstance(src, dict):
                                if src.get("business_name"):
                                    parts.append(str(src["business_name"]))
                                if src.get("industry"):
                                    parts.append(str(src["industry"]))
                                if src.get("categories"):
                                    cats = src["categories"]
                                    if isinstance(cats, list):
                                        parts.extend(str(c) for c in cats[:5])
                                    else:
                                        parts.append(str(cats))
                                if src.get("capabilities"):
                                    caps = src["capabilities"]
                                    if isinstance(caps, list):
                                        parts.extend(str(c) for c in caps[:5])
                                    else:
                                        parts.append(str(caps))
                        content = " ".join(parts) or "business analytics data"

                    # SOURCE PRIORITY: analytics score capped at 0.40 — always below
                    # real product chunks which score 0.50+ from semantic search
                    formatted.append({
                        "content":         content,
                        "score":           _ANALYTICS_MAX_SCORE,  # CAPPED — never outranks products
                        "chunk_type":      "data_analytics",
                        "chunk_id":        str(record.get("id", "")),
                        "source":          "analytics",
                        "retrieval_layer": "L_ANALYTICS",
                        "metadata":        payload,
                        "user_id":         user_id,
                        "structured_data": payload.get("structured_data", {}),
                        "attributes":      payload.get("attributes", {}),
                    })

                logger.info(
                    "analytics_selected=%d analytics_validated=%d analytics_injected=%d",
                    len(formatted), len(formatted), len(formatted),
                    trace_id=trace_id,
                )

                retrieval = dict(retrieval)
                # CRITICAL FIX: analytics APPENDED AFTER product chunks — never before
                retrieval["chunks"] = existing_chunks + formatted
                retrieval["_analytics_injected"] = True
                retrieval["_analytics_from_cache"] = False
                retrieval["_analytics_chunks"] = formatted
                retrieval["retrieval_confidence"] = max(conf, 0.45)
                if "L_ANALYTICS" not in retrieval.get("layers_used", []):
                    retrieval["layers_used"] = retrieval.get("layers_used", []) + ["L_ANALYTICS"]

                logger.info(
                    "analytics_retrieved | intent=%s chunks=%d conf=%.2f→%.2f position=AFTER_PRODUCTS",
                    intent_str, len(formatted), conf, retrieval["retrieval_confidence"],
                    trace_id=trace_id,
                )
            else:
                logger.debug(
                    "analytics_retrieved=0 | no data_analytics entries for user=%s",
                    user_id[:12], trace_id=trace_id,
                )

        except Exception as e:
            logger.warning("Analytics fallback error: %s", e, trace_id=trace_id)

        return retrieval

    def _try_greeting_fast_path(self, event: Any, memory: dict) -> str | None:
        """
        Returns a deterministic greeting response when the message is a pure
        greeting/acknowledgement with no information-seeking intent.

        Conditions for fast-path (ALL must be true):
          1. Message body is a known greeting phrase or very short (<= 3 words)
          2. Subject has no information-seeking keywords
          3. First or early turn (turn_count <= 1) — avoids hijacking mid-conversation

        Returns response string if fast-path applies, None otherwise.
        """
        content = (event.content or "").strip().lower()
        subject = (event.subject or "").strip().lower()

        # Only apply on new conversations (turn 0)
        turn_count = memory.get("turn_count", 0)
        if turn_count > 0:
            return None

        # Pure greeting patterns — exact or prefix match
        _GREETING_EXACT = {
            "hello", "hi", "hey", "hii", "hiii", "hiiii", "helloooo",
            "helo", "helo there", "hi there", "hey there", "hello there",
            "good morning", "good afternoon", "good evening", "good day",
            "greetings", "howdy", "yo", "sup",
            "thanks", "thank you", "thank you!", "thanks!", "ty",
            "ok", "okay", "k", "noted",
        }
        # Also match if the full content is <=3 words and all words are greetings
        _GREETING_WORDS = {
            "hello", "hi", "hey", "hii", "helo", "hola", "greetings",
            "good", "morning", "afternoon", "evening", "thanks", "thank", "you",
            "howdy", "yo", "sup", "okay", "ok",
        }

        is_greeting = (
            content in _GREETING_EXACT
            or content.rstrip("!.") in _GREETING_EXACT
            or (len(content.split()) <= 3
                and all(w in _GREETING_WORDS for w in content.split()))
        )

        if not is_greeting:
            return None

        # Subject must not contain information-seeking keywords
        _INFO_KEYWORDS = {
            "price", "cost", "buy", "purchase", "order", "product", "service",
            "support", "help", "issue", "problem", "refund", "return", "delivery",
            "enquiry", "inquiry", "information", "details", "quote", "offer",
            "discount", "available", "stock", "spec", "feature", "review",
        }
        if any(kw in subject for kw in _INFO_KEYWORDS):
            return None

        # Return a warm, brief greeting response
        return (
            "Hello! Thank you for reaching out. "
            "How can I assist you today? Feel free to ask about our products, "
            "pricing, support, or anything else you'd like to know."
        )

    def _is_transactional_email(self, event: Any) -> bool:
        """
        Fast O(1) transactional email check using the same frozensets as emailservice.
        Returns True when the event should be silently skipped (no AI pipeline).
        Only fires for emails that somehow passed emailservice's own filter
        (e.g. CATEGORY_PERSONAL bank e-statements that have no 'unsubscribe' snippet).
        """
        subject    = (getattr(event, "subject",    "") or "").lower()[:80]
        from_email = (getattr(event, "from_email", "") or "").lower()

        # Subject prefix check (mirrors email_filter._REJECT_SUBJECT_PREFIXES)
        _TRANSACTIONAL_SUBJECT_PREFIXES = (
            "statement of your account",
            "your account statement",
            "e-statement",
            "account statement for",
            "transaction alert",
            "transaction notification",
            "otp for",
            "your otp",
            "verification code",
            "your verification",
            "password reset",
            "reset your password",
            "security alert",
            "login attempt",
            "suspicious activity",
            "delivery status",
            "mail delivery",
            "undeliverable",
            "auto-reply:",
            "auto reply:",
            "out of office",
            "automatic reply",
        )
        if subject.startswith(_TRANSACTIONAL_SUBJECT_PREFIXES):
            return True

        # Sender local-part check (e.g. estatement@bankofbaroda.bank.in)
        _TRANSACTIONAL_LOCAL_PARTS = frozenset({
            "estatement", "statement", "alert", "alerts",
            "notification", "notifications", "notify",
            "updates", "update", "system", "robot",
            "noreply", "no-reply", "donotreply", "do-not-reply",
            "mailer-daemon", "postmaster", "bounce", "bounces",
            "automated", "newsletter", "marketing", "promo",
        })
        at = from_email.find("@")
        if at > 0:
            local = from_email[:at].replace(".", "").replace("-", "").replace("_", "")
            if local in _TRANSACTIONAL_LOCAL_PARTS:
                return True
            # Also check the raw local part without normalisation
            raw_local = from_email[:at]
            if raw_local in _TRANSACTIONAL_LOCAL_PARTS:
                return True

        return False

    def _create_response_event(self, ctx: WorkflowExecutionContext, original_event: AutomationEvent, result: Dict) -> ResponseEvent:
        """Create response event from execution results"""
        decision     = result["decision"]
        llm_result   = result["llm_result"]
        intelligence = result["intelligence"]

        # intelligence may be None on transactional skip path
        if intelligence is not None and hasattr(intelligence, "primary_intents") and intelligence.primary_intents:
            first_intent = intelligence.primary_intents[0].type
            intent_str = first_intent.value if hasattr(first_intent, "value") else str(first_intent)
        else:
            intent_str = "unknown"

        return ResponseEvent(
            event_id=str(uuid.uuid4()),
            event_type="automation.response.generated",   # required by BaseEvent
            trace_id=ctx.trace_id,
            correlation_id=ctx.correlation_id,
            user_id=ctx.user_id,
            message_id=original_event.message_id,
            conversation_id=original_event.conversation_id,
            thread_id=original_event.thread_id,
            response_text=llm_result.get("response_text", ""),
            action=decision.get("action", "escalate"),
            confidence=decision.get("final_confidence", 0.0),
            intent=intent_str,
            send_email=decision.get("should_send", False),
            processing_time_ms=sum(ctx.timings.values()),
            metadata={
                "execution_id":           ctx.execution_id,
                "escalation_reason":      decision.get("escalation_reason"),
                "escalation_priority":    decision.get("escalation_priority"),
                "hallucination_detected": llm_result.get("hallucination_detected", False),
                "retrieval_chunks":       result["retrieval"].get("total_retrieved", 0),
                "timings":                ctx.timings,
            },
        )

execution_engine = ExecutionEngine()


def _match_analytics_category(record: Dict, target_cat: str) -> bool:
    """
    Check if a Qdrant analytics record's primary_category matches the target.
    Works with both flat payload dicts and nested metadata structures.

    The analytics structured_data always contains primary_category as per the
    Qdrant ingestion schema. This function handles all layout variants.
    """
    payload = record.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    # Try structured_data first (most reliable — always set by analytics engine)
    sd = payload.get("structured_data") or {}
    if isinstance(sd, dict):
        cat = sd.get("primary_category", "")
        if cat and cat.lower() == target_cat.lower():
            return True

    # Try attributes
    attr = payload.get("attributes") or {}
    if isinstance(attr, dict):
        cat = attr.get("primary_category", "")
        if cat and cat.lower() == target_cat.lower():
            return True

    # Try top-level payload category
    cat = payload.get("category", "") or payload.get("primary_category", "")
    if cat and cat.lower() == target_cat.lower():
        return True

    return False


__all__ = ["ExecutionEngine", "WorkflowExecutionContext", "ExecutionState", "execution_engine"]
