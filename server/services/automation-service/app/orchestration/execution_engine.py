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

class ExecutionContext:
    """Global execution context for workflow"""
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
        self.active_executions: Dict[str, ExecutionContext] = {}
    
    def create_execution_context(self, event: AutomationEvent) -> ExecutionContext:
        """Create execution context from event"""
        execution_id = str(uuid.uuid4())
        workflow_id = f"wf_{event.conversation_id}"
        
        ctx = ExecutionContext(
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
    
    async def _execute_stages(self, ctx: ExecutionContext, event: AutomationEvent) -> Dict[str, Any]:
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

        # ── Stage 3.5: Analytics Fallback ────────────────────────────────
        # When retrieval returns no meaningful chunks (empty or low confidence)
        # AND the intent is generic (greeting, follow_up, general_inquiry, unknown),
        # fetch data_analytics chunks so Brain #2 can generate grounded example
        # questions from real business catalogue data instead of hallucinating.
        # This runs AT MOST ONCE per message and only when truly needed.
        retrieval = await self._inject_analytics_if_needed(
            retrieval=retrieval,
            intelligence=intelligence,
            user_id=ctx.user_id,
            trace_id=ctx.trace_id,
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
    ) -> Dict:
        """
        Fetch data_analytics chunks from Qdrant and inject them into retrieval
        when the message is generic (greeting/follow_up/unknown intent) OR when
        normal retrieval returned no usable chunks.

        Rules:
        - Only triggers when chunks == [] OR retrieval_confidence < 0.3
        - Only for low-specificity intents: follow_up, general_inquiry, greeting, unknown
        - Runs at most once per message (guarded by _analytics_injected flag in retrieval)
        - Analytics chunks are tagged with retrieval_layer="L_ANALYTICS" for observability

        This gives Brain #2 real business context to generate grounded example
        questions instead of generic "I don't have that information" responses.
        """
        # Already injected or normal retrieval succeeded — skip
        if retrieval.get("_analytics_injected"):
            return retrieval

        existing_chunks = retrieval.get("chunks", [])
        conf = retrieval.get("retrieval_confidence", 0.0)

        # Determine if this is a generic/greeting intent
        generic_intents = {"follow_up", "general_inquiry", "greeting", "unknown", "follow-up"}
        intent_str = "unknown"
        if hasattr(intelligence, "primary_intents") and intelligence.primary_intents:
            t = intelligence.primary_intents[0].type
            intent_str = (t.value if hasattr(t, "value") else str(t)).lower()

        needs_analytics = (
            not existing_chunks                    # retrieval found nothing
            or conf < 0.30                         # very low confidence
            or intent_str in generic_intents       # generic/greeting message
        )

        if not needs_analytics:
            return retrieval

        try:
            from app.core.resource_management import get_resource_manager
            qdrant_repo = get_resource_manager().get_qdrant_repository()

            analytics_chunks = await qdrant_repo.scroll(
                user_id=user_id,
                filters={"category": "data_analytics"},
                limit=3,   # one analytics entry covers the whole catalogue
            )

            if analytics_chunks:
                formatted = [
                    {
                        "content":        record.get("payload", {}).get("search_text", "")
                                          or record.get("payload", {}).get("title", ""),
                        "score":          0.80,
                        "chunk_type":     "data_analytics",
                        "chunk_id":       str(record.get("id", "")),
                        "source":         "analytics",
                        "retrieval_layer": "L_ANALYTICS",
                        "metadata":       record.get("payload", {}),
                        "user_id":        user_id,
                        # Attach full structured_data for rich context
                        "structured_data": record.get("payload", {}).get("structured_data", {}),
                        "attributes":      record.get("payload", {}).get("attributes", {}),
                    }
                    for record in analytics_chunks
                ]

                # Prepend analytics chunks — they provide catalogue context
                retrieval = dict(retrieval)
                retrieval["chunks"] = formatted + existing_chunks
                retrieval["_analytics_injected"] = True
                retrieval["retrieval_confidence"] = max(conf, 0.45)
                if "L_ANALYTICS" not in retrieval.get("layers_used", []):
                    retrieval["layers_used"] = retrieval.get("layers_used", []) + ["L_ANALYTICS"]

                logger.info(
                    "Analytics fallback injected | intent=%s chunks=%d conf=%.2f→%.2f",
                    intent_str, len(formatted), conf, retrieval["retrieval_confidence"],
                    trace_id=trace_id,
                )
            else:
                logger.debug(
                    "Analytics fallback: no data_analytics entries found for user=%s",
                    user_id[:12], trace_id=trace_id,
                )

        except Exception as e:
            # Non-critical — pipeline continues without analytics fallback
            logger.warning("Analytics fallback error: %s", e, trace_id=trace_id)

        return retrieval

    def _create_response_event(self, ctx: ExecutionContext, original_event: AutomationEvent, result: Dict) -> ResponseEvent:
        """Create response event from execution results"""
        decision     = result["decision"]
        llm_result   = result["llm_result"]
        intelligence = result["intelligence"]

        # intelligence is always an EnterpriseIntelligenceResult (Pydantic model),
        # never a plain dict — extract intent safely via attributes.
        if hasattr(intelligence, "primary_intents") and intelligence.primary_intents:
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

__all__ = ["ExecutionEngine", "ExecutionContext", "ExecutionState", "execution_engine"]
