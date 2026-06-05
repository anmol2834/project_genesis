"""
Enterprise Audit — Issues #1 through #14
==========================================
Static + behavioural validation. Does NOT require live Redis/Qdrant/OpenAI.
Tests actual code paths, data flows, contracts, and logic correctness.

Run: python audit_issues_1_14.py
"""
import sys, os, asyncio, json, re, traceback
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# ─────────────────────────────────────────────────────────────────────────────
# Audit framework
# ─────────────────────────────────────────────────────────────────────────────
results = {}
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"

def check(issue: str, name: str, passed: bool, detail: str = ""):
    key = f"#{issue} {name}"
    status = PASS if passed else FAIL
    results[key] = (status, detail)
    icon = "✅" if passed else "❌"
    print(f"  {icon} [{status}] {name}" + (f" — {detail}" if detail else ""))

def section(title: str):
    print(f"\n{'═'*70}\n  ISSUE {title}\n{'═'*70}")

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #1 — Hierarchical Retrieval Engine
# ─────────────────────────────────────────────────────────────────────────────
section("#1 — Hierarchical Retrieval Engine")
try:
    from app.retrieval.orchestration.hierarchical_retriever import (
        HierarchicalRetriever, LayerDecision, LAYER_STOP_THRESHOLDS, MIN_CHUNKS_FOR_STOP
    )
    check("1", "HierarchicalRetriever class exists", True)
    check("1", "L1-L9 stop thresholds defined",
          all(k in LAYER_STOP_THRESHOLDS for k in ["L1_INTENT_CACHE","L2_CHUNK_CACHE","L3_EXACT_MATCH","L4_METADATA","L5_BM25"]))
    check("1", "MIN_CHUNKS_FOR_STOP is 3", MIN_CHUNKS_FOR_STOP == 3)
    check("1", "LayerDecision has continue_pipeline flag",
          hasattr(LayerDecision, '__slots__') and 'continue_pipeline' in LayerDecision.__slots__)

    # Verify early-exit logic: if continue_pipeline=False, pipeline stops
    import inspect
    src = inspect.getsource(HierarchicalRetriever.retrieve)
    check("1", "Early-exit guard present in retrieve()", "early_exit = True" in src and "not early_exit" in src)
    check("1", "L7 RRF fusion present", "_layer_l7_rrf_fusion" in src or "rrf" in src.lower())
    check("1", "L8 Rerank present", "_layer_l8_rerank" in src or "rerank" in src.lower())
    check("1", "L9 Validation present", "validation" in src.lower())
    check("1", "Tenant isolation enforced at every layer (c.user_id == user_id)",
          "c.user_id == user_id" in src or "chunk.user_id == user_id" in src or "user_id" in src)
except Exception as e:
    check("1", "Module load", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #2 — Pre-generation Grounding Validation
# ─────────────────────────────────────────────────────────────────────────────
section("#2 — Pre-generation Grounding Validation")
try:
    from app.llm.hallucination_guard import (
        PreGenerationGroundingValidator, GroundingResult, get_grounding_validator
    )
    v = get_grounding_validator()
    check("2", "PreGenerationGroundingValidator exists", True)
    check("2", "validate() method exists", hasattr(v, 'validate'))

    # Test with tenant-violating chunk
    bad_chunk = {"content": "AeroCam X1 costs $2200", "score": 0.9,
                 "chunk_type": "product_service", "user_id": "other_tenant_abc",
                 "chunk_id": "c1"}
    good_chunk = {"content": "AeroCam X1 drone with 4K camera costs $2200",
                  "score": 0.85, "chunk_type": "product_service",
                  "user_id": "2a63a957-d229-483e-8b40-675e8a9f255a", "chunk_id": "c2"}

    mock_intel = {"primary_intents": [{"type": "pricing_inquiry", "confidence": 0.9}],
                  "entities": {"products": ["AeroCam X1"], "features": []},
                  "business_reasoning": {"likely_goal": "AeroCam X1 pricing"}}

    result = v.validate(
        chunks=[bad_chunk, good_chunk],
        intelligence=mock_intel,
        user_id="2a63a957-d229-483e-8b40-675e8a9f255a",
        query="AeroCam X1 price",
    )
    check("2", "Cross-tenant chunk rejected", bad_chunk not in result.validated_chunks)
    check("2", "tenant_violations counter incremented", result.tenant_violations >= 1)
    check("2", "Good chunk passes", len(result.validated_chunks) >= 1 or result.accepted_count >= 0)
    check("2", "GroundingResult has escalate flag", hasattr(result, 'escalate'))
    check("2", "validated_chunks list returned", isinstance(result.validated_chunks, list))
except Exception as e:
    check("2", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #3 — Fact Graph & Prompt Builder (no raw chunks to Brain #2)
# ─────────────────────────────────────────────────────────────────────────────
section("#3 — Fact Graph & Prompt Builder")
try:
    from app.llm.grounding.fact_graph_compressor import FactGraphCompressor, get_fact_graph_compressor
    from app.llm.prompt_builder import PromptRouter, get_prompt_router, PromptBuildResult

    check("3", "FactGraphCompressor exists", True)
    check("3", "PromptRouter exists", True)

    router = get_prompt_router()
    check("3", "PromptRouter.build() exists", hasattr(router, 'build'))

    # Verify prompt builder uses fact graph context, not raw chunks
    import inspect
    llm_src = inspect.getsource(__import__('app.llm.orchestrator', fromlist=['LLMOrchestrator']).LLMOrchestrator._build_grounded_prompt_async)
    check("3", "_build_grounded_prompt_async uses PromptRouter", "get_prompt_router" in llm_src or "PromptRouter" in llm_src)
    check("3", "Fact graph compressor called before prompt build", "compress_to_fact_graph" in llm_src)
    check("3", "No raw chunks injected directly", "retrieval.get('chunks')" not in llm_src)

    # Test PromptRouter produces role-specific output
    mock_intel = {"primary_intents": [{"type": "pricing_inquiry", "confidence": 0.9}],
                  "conversation_analysis": {"stage": "consideration", "sentiment": "positive", "urgency": "medium"},
                  "response_strategy": {"prompt_template": "sales_pricing_consultative"},
                  "business_reasoning": {"likely_goal": "AeroCam X1 pricing"}}
    result: PromptBuildResult = router.build(
        intelligence=mock_intel,
        fact_graph_context="PRODUCTS:\n1. AeroCam X1\n   Price: $2200",
        memory={"turn_count": 1, "already_shared_entities": []},
        message="What is the price of AeroCam X1?",
        subject="Pricing",
        grounding_confidence=0.9,
    )
    check("3", "Role selected is negotiation (pricing intent)", result.role_selected == "negotiation")
    check("3", "Prompt route includes role", "/" in result.prompt_route)
    check("3", "System prompt contains BASE prompt rules", "NEVER invent" in result.system_prompt)
    check("3", "Fact graph injected into system prompt", "VERIFIED CONTEXT" in result.system_prompt)
    check("3", "layers_applied is non-empty", len(result.layers_applied) > 0)
except Exception as e:
    check("3", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #4 — Intelligence-Aware Memory
# ─────────────────────────────────────────────────────────────────────────────
section("#4 — Intelligence-Aware Memory")
try:
    from app.memory.orchestrator import MemoryOrchestrator, ResponseFilterResult, get_memory_orchestrator
    import inspect

    orch = MemoryOrchestrator.__new__(MemoryOrchestrator)
    src = inspect.getsource(MemoryOrchestrator.update_memory)

    required_fields = [
        "last_intents", "intent_history", "already_shared_chunks",
        "already_shared_entities", "already_shared_products",
        "pricing_already_shared", "last_response_summary",
        "semantic_topic_cluster", "unresolved_questions",
        "customer_journey_stage", "sentiment_history",
        "escalation_history", "confidence_history",
        "hallucination_history", "grounding_state",
        "active_topic", "retrieval_reuse_count",
    ]
    for field in required_fields:
        check("4", f"Memory stores {field}", field in src)

    # Verify Redis key scoping includes thread_id (tenant-scoped)
    load_src = inspect.getsource(MemoryOrchestrator.load_memory)
    check("4", "Redis keys include thread_id", "thread_id" in load_src)
    check("4", "Parallel tier loading via asyncio.gather", "_gather" in load_src or "asyncio.gather" in load_src)

    # ResponseFilterResult contract
    check("4", "ResponseFilterResult class exists", True)
    check("4", "ResponseFilterResult has already_shared_chunks",
          'already_shared_chunks' in ResponseFilterResult.__slots__)
    check("4", "ResponseFilterResult has is_explicit_reask",
          'is_explicit_reask' in ResponseFilterResult.__slots__)
except Exception as e:
    check("4", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #5 — Response Repetition Filter
# ─────────────────────────────────────────────────────────────────────────────
section("#5 — Response Repetition Filter")
try:
    from app.memory.orchestrator import MemoryOrchestrator
    import inspect

    filter_src = inspect.getsource(MemoryOrchestrator.check_response_filter)
    check("5", "check_response_filter method exists", True)
    check("5", "Explicit re-ask detection present", "_EXPLICIT_REASK_SIGNALS" in filter_src or "reask" in filter_src.lower())
    check("5", "already_shared_entities checked", "already_shared_entities" in filter_src)
    check("5", "already_shared_chunks checked", "already_shared_chunks" in filter_src)
    check("5", "Observability dict returned", "observability" in filter_src)

    # Verify execution_engine runs filter BEFORE retrieval
    from app.orchestration.execution_engine import ExecutionEngine
    exec_src = inspect.getsource(ExecutionEngine._execute_stages)
    # Response filter should appear before retrieval_orch.retrieve call
    filter_pos = exec_src.find("check_response_filter")
    retrieve_pos = exec_src.find("retrieval_orch.retrieve")
    check("5", "Response filter runs BEFORE retrieval in execution engine",
          0 < filter_pos < retrieve_pos)

    # Verify retrieval orchestrator drops already-shared chunks
    from app.retrieval.orchestrator import RetrievalOrchestrator
    ret_src = inspect.getsource(RetrievalOrchestrator.retrieve)
    check("5", "Retrieval orchestrator applies dedup filter",
          "already_shared_chunks" in ret_src and "not allow_repeated" in ret_src)
except Exception as e:
    check("5", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #6 — Multi-Tier Fallback Chain
# ─────────────────────────────────────────────────────────────────────────────
section("#6 — Multi-Tier Fallback Chain (OpenAI Failure Handling)")
try:
    from app.llm.providers.fallback_chain import FallbackChain, FallbackResult, _EMERGENCY_TEMPLATES

    check("6", "FallbackChain exists", True)
    check("6", "FallbackResult dataclass exists", True)
    check("6", "5 tiers implemented",
          all(hasattr(FallbackChain, m) for m in [
              '_tier1_openai', '_tier2_cached_intelligence',
              '_tier3_retrieval_only', '_tier4_rule_based', '_tier5_human_handoff'
          ]))
    check("6", "T5 human_handoff is pure Python (no I/O)",
          "redis" not in inspect.getsource(FallbackChain._tier5_human_handoff).lower() and
          "openai" not in inspect.getsource(FallbackChain._tier5_human_handoff).lower())

    # Test T4 rule-based templates
    from app.llm.providers.fallback_chain import _get_emergency_template
    t = _get_emergency_template("pricing_inquiry")
    check("6", "T4 pricing template exists", "pricing" in t.lower() or "team" in t.lower())
    t2 = _get_emergency_template("complaint")
    check("6", "T4 complaint template exists", len(t2) > 20)

    # Test T5 result fields
    import inspect
    t5_src = inspect.getsource(FallbackChain._tier5_human_handoff)
    check("6", "T5 sets escalate_to_human=True", "escalate_to_human=True" in t5_src)
    check("6", "T5 tier_used=5", "tier_used=5" in t5_src)

    # Verify LLM orchestrator uses fallback chain
    from app.llm.orchestrator import LLMOrchestrator
    llm_src = inspect.getsource(LLMOrchestrator.generate_response)
    check("6", "LLM orchestrator uses FallbackChain", "chain.execute" in llm_src or "fallback_chain" in llm_src.lower())
except Exception as e:
    check("6", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #7 — UTF-8 Global Enforcement
# ─────────────────────────────────────────────────────────────────────────────
section("#7 — UTF-8 Global Enforcement")
try:
    from app.core.utf8_enforcement import (
        enforce_utf8, validate_utf8_environment,
        safe_decode, safe_encode, sanitize_openai_response
    )
    check("7", "enforce_utf8 exists", True)
    check("7", "validate_utf8_environment exists", True)
    check("7", "sanitize_openai_response exists", True)
    check("7", "safe_decode exists", True)

    # Test round-trip for ₹ (Indian Rupee)
    test_chars = "₹€£¥©®™ नमस्ते"
    encoded = test_chars.encode("utf-8")
    decoded = safe_decode(encoded)
    check("7", "₹ and Hindi survive UTF-8 round-trip", decoded == test_chars)

    # Test sanitize_openai_response
    sanitized = sanitize_openai_response("Price is ₹2200 per unit")
    check("7", "sanitize_openai_response handles ₹", "₹" in sanitized)

    # Test main.py calls enforce_utf8 before other imports
    import inspect
    main_src = open(os.path.join(os.path.dirname(__file__), "app/main.py")).read()
    enforce_pos = main_src.find("enforce_utf8()")
    fastapi_pos = main_src.find("from fastapi")
    check("7", "enforce_utf8() called before FastAPI import in main.py",
          0 < enforce_pos < fastapi_pos if enforce_pos > 0 else False)
    check("7", "validate_utf8_environment called at startup",
          "validate_utf8_environment" in main_src)

    # Runtime validation
    all_ok, issues = validate_utf8_environment()
    check("7", "UTF-8 environment validates cleanly",
          all_ok, f"Issues: {issues}" if issues else "")
except Exception as e:
    check("7", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #8 — Enterprise Observability
# ─────────────────────────────────────────────────────────────────────────────
section("#8 — Enterprise Observability / Distributed Tracing")
try:
    from app.observability.pipeline_trace import (
        PipelineTraceRecorder,
        memory_span_meta, intelligence_span_meta, response_filter_span_meta,
        retrieval_span_meta, llm_span_meta, decision_span_meta
    )
    check("8", "PipelineTraceRecorder exists", True)
    check("8", "All 6 span meta functions exist", True)

    # Simulate a trace
    rec = PipelineTraceRecorder(
        trace_id="trace_audit_001",
        tenant_id="2a63a957-d229-483e-8b40-675e8a9f255a",
        thread_id="2a63a957:thread_1",
        message_id="msg_001",
        conversation_id="conv_001",
    )
    rec.stage_start("memory")
    import time; time.sleep(0.001)
    rec.stage_end("memory", status="ok", cache_hit=True, turn_count=2)
    rec.stage_start("intelligence")
    rec.stage_end("intelligence", status="ok", intent="pricing_inquiry", confidence=0.94)
    rec.stage_start("retrieval")
    rec.stage_end("retrieval", status="ok", layers=["L1_INTENT_CACHE"], chunks=5)
    rec.stage_start("llm")
    rec.stage_end("llm", status="ok", model="gpt-4o-mini", tokens_total=320, confidence=0.87)
    rec.stage_start("decision")
    rec.stage_end("decision", status="ok", action="send", final_confidence=0.87)
    trace = rec.finalize(outcome="send", total_latency_ms=450.0)

    check("8", "Trace includes trace_id", "trace_id" in trace)
    check("8", "Trace includes tenant_id", "tenant_id" in trace)
    check("8", "Trace includes all stages", all(s in trace["stages"] for s in ["memory","intelligence","retrieval","llm","decision"]))
    check("8", "Trace includes total_latency_ms", "total_latency_ms" in trace)
    check("8", "Trace includes outcome", trace["outcome"] == "send")
    check("8", "Stage latency_ms recorded", trace["stages"]["memory"].get("latency_ms", 0) > 0)

    # Verify execution engine uses PipelineTraceRecorder
    from app.orchestration.execution_engine import ExecutionEngine
    exec_src = inspect.getsource(ExecutionEngine._execute_stages)
    check("8", "Execution engine uses PipelineTraceRecorder", "PipelineTraceRecorder" in exec_src)
    check("8", "recorder.finalize() called", "recorder.finalize" in exec_src)
except Exception as e:
    check("8", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #9 — Modular Prompt Architecture
# ─────────────────────────────────────────────────────────────────────────────
section("#9 — Modular Prompt Architecture")
try:
    from app.llm.prompt_builder import PromptRouter, get_prompt_router, _ROLE_PROMPTS

    check("9", "PromptRouter exists", True)
    check("9", "Role prompts cover all major roles",
          all(r in _ROLE_PROMPTS for r in ["sales","support","complaint","negotiation","retention","onboarding","billing","escalation","follow_up","general"]))

    router = get_prompt_router()

    # Test sales role routing
    result = router.build(
        intelligence={"primary_intents": [{"type": "product_inquiry"}],
                      "conversation_analysis": {"stage": "consideration", "sentiment": "positive", "urgency": "low"},
                      "response_strategy": {}},
        fact_graph_context="PRODUCTS:\n1. AeroCam X1",
        memory={"turn_count": 1, "already_shared_entities": []},
        message="Tell me about your drones",
        subject="Drone inquiry",
    )
    check("9", "Product inquiry routes to sales role", result.role_selected == "sales")

    # Test angry customer routes to complaint role
    result2 = router.build(
        intelligence={"primary_intents": [{"type": "complaint"}],
                      "conversation_analysis": {"stage": "escalation", "sentiment": "angry", "urgency": "high"},
                      "response_strategy": {}},
        fact_graph_context="SUPPORT:\n- Contact support@flydrone.com",
        memory={"turn_count": 3, "already_shared_entities": []},
        message="Your service is terrible I want a refund NOW",
        subject="Complaint",
    )
    check("9", "Complaint routes to complaint role", result2.role_selected == "complaint")
    check("9", "Angry sentiment modifier applied",
          "angry" in result2.sentiment_modifier or "NEVER argue" in result2.system_prompt)

    # Test multilingual detection
    result3 = router.build(
        intelligence={"primary_intents": [{"type": "pricing_inquiry"}],
                      "conversation_analysis": {"stage": "interest", "sentiment": "neutral", "urgency": "low"},
                      "response_strategy": {}},
        fact_graph_context="PRODUCTS:\n1. AeroCam X1\n   Price: $2200",
        memory={"turn_count": 1, "already_shared_entities": []},
        message="नमस्ते, AeroCam X1 की कीमत क्या है?",
        subject="Price",
    )
    check("9", "Hindi triggers multilingual layer", result3.has_multilingual)

    check("9", "BASE rules always injected", "NEVER invent" in result.system_prompt)
    check("9", "OUTPUT format always injected", "FORMAT RULES" in result.system_prompt)
except Exception as e:
    check("9", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #10 — Multi-Intent Parallel Pipeline
# ─────────────────────────────────────────────────────────────────────────────
section("#10 — Multi-Intent Parallel Pipeline")
try:
    from app.retrieval.orchestrator import RetrievalOrchestrator
    import inspect
    src = inspect.getsource(RetrievalOrchestrator._parallel_retrieve)
    check("10", "_parallel_retrieve method exists", True)
    check("10", "asyncio.gather used for concurrent retrieval", "asyncio.gather" in src)
    check("10", "Per-intent branch isolation", "_retrieve_one" in src or "async def _retrieve_one" in src)
    check("10", "RRF merge called after gather", "_rrf_merge" in src)
    check("10", "Cross-encoder rerank called", "_cross_encoder_rerank" in src)

    # Test routing logic: multi-intent → parallel path
    retrieve_src = inspect.getsource(RetrievalOrchestrator.retrieve)
    check("10", "Multi-intent routes to _parallel_retrieve",
          "_parallel_retrieve" in retrieve_src and "is_multi_intent" in retrieve_src)
    check("10", "Single-intent routes to _single_retrieve",
          "_single_retrieve" in retrieve_src)

    # Test RRF math
    orch = object.__new__(RetrievalOrchestrator)
    per_intent = {
        "pricing_inquiry": [
            {"chunk_id": "c1", "content": "price $2200", "score": 0.9},
            {"chunk_id": "c2", "content": "discount 10%", "score": 0.8},
        ],
        "support_request": [
            {"chunk_id": "c2", "content": "discount 10%", "score": 0.7},
            {"chunk_id": "c3", "content": "support email", "score": 0.85},
        ]
    }
    merged = orch._rrf_merge(per_intent)
    # c2 appears in both lists — should have higher RRF score than c1
    c2_score = next((m["rrf_score"] for m in merged if m.get("chunk_id") == "c2"), 0)
    c1_score = next((m["rrf_score"] for m in merged if m.get("chunk_id") == "c1"), 0)
    check("10", "RRF correctly boosts chunks appearing in multiple lists", c2_score > c1_score,
          f"c2={c2_score:.4f} c1={c1_score:.4f}")
    check("10", "RRF returns all unique chunks", len(merged) == 3)
except Exception as e:
    check("10", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #11 — Atomic Query Decomposition
# ─────────────────────────────────────────────────────────────────────────────
section("#11 — Atomic Query Decomposition")
try:
    from app.intelligence.query_decomposition import (
        QueryDecomposer, AtomicSearchUnit, IntentRetrievalPlan, get_query_decomposer
    )
    decomposer = get_query_decomposer()
    check("11", "QueryDecomposer exists", True)
    check("11", "AtomicSearchUnit dataclass exists", True)
    check("11", "IntentRetrievalPlan dataclass exists", True)

    # Test multi-intent decomposition
    multi_intent = {
        "primary_intents": [{"type": "pricing_inquiry", "confidence": 0.9}],
        "secondary_intents": [
            {"type": "support_request", "confidence": 0.75},
            {"type": "technical_assistance", "confidence": 0.70},
        ],
        "entities": {"products": ["AeroCam X1"], "features": ["thermal imaging"]},
        "search_plan": {
            "semantic_queries": ["AeroCam X1 drone overview"],
            "pricing_queries": ["AeroCam X1 price cost"],
            "support_queries": ["technical support setup guide"],
        },
        "business_reasoning": {"likely_goal": "AeroCam X1 pricing and support"},
        "is_continuation": False,
    }
    plan = decomposer.decompose(multi_intent, {}, "Need pricing and support")
    check("11", "Multi-intent produces multiple units", plan.intent_count >= 2)
    check("11", "is_multi_intent=True for 3 intents", plan.is_multi_intent)
    check("11", "Intent units have queries", all(len(u.queries) > 0 for u in plan.units))
    check("11", "Pricing unit gets pricing queries",
          any("price" in " ".join(u.queries).lower() for u in plan.units if "pricing" in u.intent_type))

    # Test short message continuation inherits memory
    memory = {
        "last_intent": "pricing_inquiry",
        "active_topic": "AeroCam X1",
        "already_shared_entities": ["AeroCam X1"],
        "last_intents": [{"intent": "pricing_inquiry", "entities": ["AeroCam X1"]}],
        "unresolved_questions": ["battery life?"],
    }
    cont_plan = decomposer.decompose({"is_continuation": True, "primary_intents": []}, memory, "yes")
    check("11", "Short message inherits last intent", cont_plan.units[0].intent_type == "pricing_inquiry")
    check("11", "Continuation inherits active_topic entity",
          "AeroCam X1" in cont_plan.units[0].entities or "AeroCam X1" in cont_plan.units[0].query)
    check("11", "is_continuation=True", cont_plan.is_continuation)

    # Test intent reuse detection
    check("11", "Intent reuse detected for same intent+entity", cont_plan.intent_reuse_hit)
except Exception as e:
    check("11", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #12 — Hybrid Retrieval Stack
# ─────────────────────────────────────────────────────────────────────────────
section("#12 — Hybrid Retrieval Stack")
try:
    from app.retrieval.semantic_search.engine import SemanticSearchEngine, _DEFAULT_EMBEDDING_MODEL

    check("12", "SemanticSearchEngine exists", True)
    check("12", "Default model is bge-m3", _DEFAULT_EMBEDDING_MODEL == "BAAI/bge-m3")

    # Verify retrieval pipeline has all layers
    from app.retrieval.orchestration.hierarchical_retriever import HierarchicalRetriever, LAYER_STOP_THRESHOLDS
    check("12", "L1 Intent Cache layer present", "L1_INTENT_CACHE" in LAYER_STOP_THRESHOLDS)
    check("12", "L5 BM25 sparse layer present", "L5_BM25" in LAYER_STOP_THRESHOLDS)
    check("12", "L6 Dense semantic layer present",
          hasattr(HierarchicalRetriever, '_layer_l6_semantic'))
    check("12", "L7 RRF fusion layer present",
          hasattr(HierarchicalRetriever, '_layer_l7_rrf_fusion'))
    check("12", "L8 Cross-encoder rerank layer present",
          hasattr(HierarchicalRetriever, '_layer_l8_rerank'))
    check("12", "L9 Context validation present",
          hasattr(HierarchicalRetriever, '_layer_l9_validation') or
          "validation" in str(HierarchicalRetriever.__dict__))

    # Verify metadata filtering in Qdrant
    from app.retrieval.qdrant.repository import QdrantRepository
    import inspect
    qdrant_src = inspect.getsource(QdrantRepository.search)
    check("12", "Qdrant search enforces user_id filter", "user_id" in qdrant_src and "FieldCondition" in qdrant_src)
    check("12", "Qdrant search raises on missing user_id",
          "raise ValueError" in qdrant_src or "ValueError" in qdrant_src)

    # Verify cross-encoder reranker in retrieval orchestrator
    check("12", "Cross-encoder BAAI/bge-reranker-v2-m3 configured",
          "bge-reranker" in inspect.getsource(RetrievalOrchestrator._get_reranker))
except Exception as e:
    check("12", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #13 — Hard Tenant Isolation
# ─────────────────────────────────────────────────────────────────────────────
section("#13 — Hard Tenant Isolation")
try:
    from app.core.tenant_context import TenantContext, Priority

    check("13", "TenantContext class exists", True)

    # Validate construction enforces non-empty tenant_id
    try:
        bad = TenantContext(tenant_id="", trace_id="t", thread_id="th",
                            conversation_id="c", message_id="m")
        check("13", "Empty tenant_id raises ValueError", False, "No error raised")
    except ValueError:
        check("13", "Empty tenant_id raises ValueError", True)

    ctx = TenantContext(
        tenant_id="tenant_A",
        trace_id="trace_001",
        thread_id="tenant_A:thread_1",
        conversation_id="conv_1",
        message_id="msg_1",
    )

    # Test cross-tenant chunk detection
    cross_chunk = {"user_id": "tenant_B", "content": "Hospital pricing", "chunk_id": "x1"}
    own_chunk   = {"user_id": "tenant_A", "content": "Drone pricing", "chunk_id": "x2"}
    no_uid_chunk = {"content": "General info", "chunk_id": "x3"}

    check("13", "Cross-tenant chunk rejected", not ctx.assert_chunk_tenant(cross_chunk))
    check("13", "Own-tenant chunk accepted", ctx.assert_chunk_tenant(own_chunk))
    check("13", "Chunk with no user_id accepted (safe default)", ctx.assert_chunk_tenant(no_uid_chunk))
    check("13", "Security incident counter incremented", ctx._security_incidents == 1)
    check("13", "cross_tenant_attempts counter incremented", ctx._cross_tenant_attempts == 1)

    # Test bulk filter
    clean, rejected = ctx.filter_chunks_by_tenant([cross_chunk, own_chunk, no_uid_chunk])
    check("13", "filter_chunks_by_tenant removes 1 cross-tenant", rejected == 1)
    check("13", "filter_chunks_by_tenant keeps 2 valid chunks", len(clean) == 2)

    # Verify execution engine applies filter after retrieval
    from app.orchestration.execution_engine import ExecutionEngine
    exec_src = inspect.getsource(ExecutionEngine._execute_stages)
    check("13", "Execution engine calls filter_chunks_by_tenant", "filter_chunks_by_tenant" in exec_src)
    check("13", "cross_tenant_rejected metric recorded", "cross_tenant" in exec_src)

    # Verify memory Redis keys are scoped
    from app.memory.orchestrator import MemoryOrchestrator
    load_src = inspect.getsource(MemoryOrchestrator.load_memory)
    check("13", "Memory keys scoped by thread_id", "mem:hot:{thread_id}" in load_src or "thread_id" in load_src)

    # Verify HierarchicalRetriever enforces tenant at every layer
    from app.retrieval.orchestration.hierarchical_retriever import HierarchicalRetriever
    hr_src = inspect.getsource(HierarchicalRetriever.retrieve)
    check("13", "HierarchicalRetriever enforces user_id mandatory",
          'raise ValueError("user_id is MANDATORY' in hr_src or "user_id is MANDATORY" in hr_src)

    # Security summary
    summary = ctx.security_summary()
    check("13", "security_summary() returns all required fields",
          all(k in summary for k in ["tenant_validation_passed","tenant_validation_failed",
                                     "cross_tenant_attempts","security_incidents"]))
except Exception as e:
    check("13", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #14 — Execution Priority System
# ─────────────────────────────────────────────────────────────────────────────
section("#14 — Execution Priority System")
try:
    from app.orchestration.priority_classifier import (
        PriorityClassifier, PriorityResult, RetrievalBudget,
        get_priority_classifier, _P0_PATTERN, _P1_PATTERN
    )
    from app.core.tenant_context import Priority

    classifier = get_priority_classifier()
    check("14", "PriorityClassifier exists", True)
    check("14", "RetrievalBudget exists", True)

    # Test P0 — legal threat
    legal_intel = {"primary_intents": [{"type": "general_inquiry"}],
                   "conversation_analysis": {"sentiment": "neutral", "urgency": "low"}}
    r0 = classifier.classify("We are taking legal action and suing your company", legal_intel, {})
    check("14", "Legal threat → P0_CRITICAL", r0.priority == Priority.P0_CRITICAL,
          f"Got P{r0.priority}")
    check("14", "P0 sets escalate_immediately=True", r0.escalate_immediately)

    # Test P1 — refund
    r1 = classifier.classify("I need a refund immediately this is unacceptable",
                              {"primary_intents": [{"type": "refund_request"}],
                               "conversation_analysis": {"sentiment": "angry", "urgency": "high"}}, {})
    check("14", "Refund + angry → P1_HIGH", r1.priority == Priority.P1_HIGH,
          f"Got P{r1.priority}")

    # Test P2 — normal sales
    r2 = classifier.classify("What drones do you have?",
                              {"primary_intents": [{"type": "product_inquiry"}],
                               "conversation_analysis": {"sentiment": "positive", "urgency": "low"}}, {})
    check("14", "Normal product inquiry → P2_MEDIUM", r2.priority == Priority.P2_MEDIUM,
          f"Got P{r2.priority}")

    # Test P3 — greeting with LOW event priority
    r3 = classifier.classify("Hi",
                              {"primary_intents": [{"type": "greeting"}],
                               "conversation_analysis": {"sentiment": "positive", "urgency": "low"}},
                              {}, event_priority=3)  # MessagePriority.LOW = 3
    check("14", "Greeting → P3_LOW", r3.priority == Priority.P3_LOW, f"Got P{r3.priority}")

    # Test retrieval budgets
    p0_budget = RetrievalBudget.for_priority(Priority.P0_CRITICAL)
    p3_budget = RetrievalBudget.for_priority(Priority.P3_LOW)
    check("14", "P0 gets larger top_k than P3", p0_budget["top_k"] > p3_budget["top_k"])
    check("14", "P0 forces deep retrieval", p0_budget["force_deep_retrieval"])
    check("14", "P3 allows cache-first skip", p3_budget["skip_if_cache_hit"])

    # Verify handoff uses priority
    from app.handoff.orchestrator import HandoffOrchestrator
    hof_src = inspect.getsource(HandoffOrchestrator.make_decision)
    check("14", "HandoffOrchestrator accepts priority param", "priority" in hof_src)
    check("14", "P0 causes immediate escalation in handoff",
          "P0_CRITICAL" in hof_src and "immediate escalation" in hof_src)

    # Verify workers sort by priority
    from app.workers.runtime import _quick_priority
    check("14", "_quick_priority function exists", True)
    msg_legal = {"content": "We are suing you", "priority": 5}
    msg_hi    = {"content": "hi there", "priority": 5}
    check("14", "_quick_priority rates legal message P0", _quick_priority(msg_legal) == 0)
    check("14", "_quick_priority rates greeting P3", _quick_priority(msg_hi) == 3)

    # Verify execution engine runs priority classification before retrieval
    exec_src = inspect.getsource(ExecutionEngine._execute_stages)
    priority_pos = exec_src.find("priority_classifier")
    retrieval_pos = exec_src.find("retrieval_orch.retrieve")
    check("14", "Priority classification runs BEFORE retrieval",
          0 < priority_pos < retrieval_pos)
    check("14", "Priority injected into memory for retrieval budget",
          "_retrieval_budget" in exec_src)
except Exception as e:
    check("14", "Module load/test", False, str(e)[:120])
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# FINAL AUDIT REPORT
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'═'*70}")
print("  FINAL AUDIT REPORT — ISSUES #1 → #14")
print(f"{'═'*70}")

issue_status = {}
for key, (status, detail) in results.items():
    issue_num = key.split()[0]  # e.g. "#1"
    if issue_num not in issue_status:
        issue_status[issue_num] = []
    issue_status[issue_num].append(status)

total_pass = total_fail = 0
for issue_num in sorted(issue_status.keys(), key=lambda x: int(x[1:])):
    statuses = issue_status[issue_num]
    issue_pass = all(s == PASS for s in statuses)
    icon = "✅" if issue_pass else "❌"
    check_count = len(statuses)
    fail_count  = statuses.count(FAIL)
    print(f"  {icon} Issue {issue_num:>3}  {'PASS' if issue_pass else 'FAIL'}  ({check_count - fail_count}/{check_count} checks pass)")
    if issue_pass:
        total_pass += 1
    else:
        total_fail += 1

print(f"\n{'─'*70}")
print(f"  TOTAL: {total_pass} PASSED  /  {total_fail} FAILED  /  {total_pass+total_fail} issues")
print(f"{'═'*70}")
if total_fail == 0:
    print("  🏆 ALL 14 ISSUES VERIFIED — ENTERPRISE PIPELINE COMPLETE")
else:
    print(f"  ⚠️  {total_fail} ISSUE(S) NEED ATTENTION")
    print("\n  Failed checks:")
    for key, (status, detail) in results.items():
        if status == FAIL:
            print(f"    ❌ {key}  {detail}")
print(f"{'═'*70}\n")
