"""
automationservice — API Router

Pipeline executed per incoming email:
  Step 1 — Trigger Automation       : validate event fields
  Step 2 — Fetch Thread Context     : es_conversations → es_messages (DB)
  Step 3 — Processor 1 (LLM Call #1): Analysis & Retrieval Planning
"""
from __future__ import annotations
import datetime
import os
import sys
import logging
import time

_API_DIR      = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR      = os.path.dirname(_API_DIR)
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json
import redis.asyncio as aioredis
from fastapi import APIRouter
from pydantic import BaseModel, Field

from shared.config import get_config
from core.config import AUTOMATION_RESPONSES, AUTOMATION_RESPONSES_NOTIFY
from services.email_context import fetch_thread_messages
from services.business_context import get_business_context
from llm.processor_1 import run_processor_1
from services.qdrant_search import run_hybrid_retrieval
from services.reranker import rerank_candidates
from llm.processor_2 import run_processor_2

logger = logging.getLogger("automationservice.router")

router = APIRouter(tags=["automation"])

_router_redis: aioredis.Redis | None = None

async def _get_router_redis() -> aioredis.Redis:
    global _router_redis
    if _router_redis is None:
        cfg = get_config()
        _router_redis = aioredis.from_url(
            cfg.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            socket_timeout=15,
            max_connections=10,
        )
    return _router_redis

async def _dispatch_automation_response(response_payload: dict) -> bool:
    try:
        r = await _get_router_redis()
        pipe = r.pipeline(transaction=True)
        pipe.xadd(AUTOMATION_RESPONSES, {"data": json.dumps(response_payload)})
        pipe.lpush(AUTOMATION_RESPONSES_NOTIFY, "1")
        await pipe.execute()
        logger.info(
            "[DISPATCH] automation response published | conv=%s action=%s send_email=%s",
            response_payload.get("conversation_id", "")[:8],
            response_payload.get("action"),
            response_payload.get("send_email"),
        )
        return True
    except Exception as exc:
        logger.error("[DISPATCH] failed to publish automation response: %s", exc)
        return False

# ── Persistent escalation state (Fix 1) ───────────────────────────────────────
# key = conversation_id, value = {"open": bool, "level": str, "reason": str,
#                                  "created_at": str, "message_count": int}
_conversation_escalation_state: dict[str, dict] = {}


class AutomationTrigger(BaseModel):
    conversation_id:    str  = ""
    user_id:            str
    message_id:         str
    thread_id:          str  = ""
    subject:            str  = ""
    from_email:         str  = ""
    provider:           str  = ""
    trace_id:           str  = ""
    automation_enabled: bool = True
    priority:           int  = Field(default=2, alias="_priority")

    model_config = {"populate_by_name": True}


async def process_event(event: dict) -> dict:
    t_start = time.monotonic()

    user_id         = event.get("user_id", "")
    message_id      = event.get("message_id", "")
    conversation_id = event.get("conversation_id", "")
    thread_id       = event.get("thread_id", "")
    subject         = event.get("subject", "")
    provider        = event.get("provider", "")
    automation_enabled = event.get("automation_enabled", True)

    # ── Step 1: Validate ───────────────────────────────────────────────────────
    if not automation_enabled:
        logger.info("Automation disabled | user=%s message=%s", user_id, message_id)
        return {"status": "skipped", "reason": "automation_disabled"}

    if not user_id or not message_id:
        missing = [f for f, v in [("user_id", user_id), ("message_id", message_id)] if not v]
        logger.warning("Invalid event — missing %s", missing)
        return {"status": "error", "reason": f"missing_required_fields: {missing}"}

    if not conversation_id:
        logger.warning("Missing conversation_id | user=%s message=%s", user_id, message_id)
        return {"status": "error", "reason": "missing_conversation_id", "message_id": message_id}

    # ── Step 2: Fetch thread context from DB ───────────────────────────────────
    context = await fetch_thread_messages(
        conversation_id   = conversation_id,
        user_id           = user_id,
        latest_message_id = message_id,
    )

    if not context["messages"]:
        logger.warning("No messages fetched | conv=%s user=%s reason=%s",
                       conversation_id, user_id, context["fetch_reason"])
        return {
            "status":          "no_context",
            "reason":          context["fetch_reason"],
            "message_id":      message_id,
            "conversation_id": conversation_id,
            "elapsed_ms":      (time.monotonic() - t_start) * 1000,
        }

    conv_meta      = context.get("conversation") or {}
    latest_message = context.get("latest_message") or {}
    messages       = context["messages"]

    # ── Step 2.5: Load Business Context (PostgreSQL) ───────────────────────────
    # Single indexed UUID query → < 20 ms.
    # Must run BEFORE Processor #1 so the LLM knows the business domain.
    # Source: users table (NOT Qdrant). Qdrant remains knowledge retrieval only.
    biz_ctx = await get_business_context(user_id)
    logger.info(
        "[BIZ_CTX] loaded=%s  business=%s  type=%s  industry=%s  source=%s",
        biz_ctx.get("_loaded", False),
        biz_ctx.get("business_name", "(none)"),
        biz_ctx.get("business_type", "(none)"),
        ", ".join(biz_ctx.get("industry", [])) or "(none)",
        biz_ctx.get("_source", "?"),
    )

    # Issue 5 — Business context domain enforcement
    # Build a vocabulary from the business description to detect out-of-domain queries.
    # If the customer asks about something clearly outside the business domain,
    # log a warning so downstream (Processor #2) can handle it appropriately.
    if biz_ctx.get("_loaded"):
        biz_desc = (biz_ctx.get("business_description") or "").lower()
        biz_type = (biz_ctx.get("business_type") or "").lower()
        biz_text = biz_desc + " " + biz_type
        # Inject domain context into p1_output so retrieval layer can use it
        biz_ctx["_domain_tokens"] = set(
            w for w in biz_text.split() if len(w) > 3
        )

    # ── Step 3: Processor 1 — LLM Call #1 ─────────────────────────────────────
    p1_output = await run_processor_1(
        messages          = messages,
        latest_message    = latest_message,
        conversation_meta = conv_meta,
        business_context  = biz_ctx,
    )

    elapsed_ms = (time.monotonic() - t_start) * 1000
    p1_status  = p1_output.get("_meta", {}).get("status", "ok")
    p1_meta    = p1_output.get("_meta", {})
    ca         = p1_output.get("conversation_analysis", {})
    ia         = p1_output.get("intent_analysis", {})
    pi         = ia.get("primary_intent", {})
    ee         = p1_output.get("entity_extraction", {})
    rs         = p1_output.get("retrieval_strategy", {})
    ad         = p1_output.get("analytics_decision", {})
    rc         = p1_output.get("retrieval_constraints", {})
    si         = ia.get("secondary_intents", [])

    # ── Processor 1 output summary log ────────────────────────────────────────
    logger.info("─" * 68)
    logger.info("PROCESSOR #1 OUTPUT  |  conv=%s  |  p1_elapsed=%.0fms  model=%s",
                conversation_id[:8], p1_meta.get("elapsed_ms", 0), p1_meta.get("model", "?"))
    logger.info("─" * 68)
    logger.info("[CONVERSATION]  topic     : %s", ca.get("conversation_topic", "?"))
    logger.info("[CONVERSATION]  stage     : %s  |  sentiment: %s  |  urgency: %s",
                ca.get("conversation_stage", "?"),
                ca.get("customer_sentiment", "?"),
                ca.get("urgency", "?"))
    logger.info("[CONVERSATION]  goal      : %s", ca.get("customer_goal", "?"))
    logger.info("[CONVERSATION]  resolved  : %s", ca.get("resolved_reference", "?"))
    logger.info("[CONVERSATION]  query     : %s", ca.get("standalone_query", "?"))
    logger.info("[CONVERSATION]  conv_conf : %.2f", ca.get("conversation_confidence", 0.0))
    logger.info("[INTENT]  primary : %-22s  conf=%.2f  reason: %s",
                pi.get("category", "?"), pi.get("confidence", 0.0), pi.get("reason", "?"))
    for s in si:
        logger.info("[INTENT]  secondary: %-22s  conf=%.2f", s.get("category", "?"), s.get("confidence", 0.0))
    products = ee.get("products", [])
    specs    = ee.get("specifications", [])
    techs    = ee.get("technologies", [])
    industs  = ee.get("industries", [])
    if products: logger.info("[ENTITIES] products        : %s", ", ".join(products))
    if specs:    logger.info("[ENTITIES] specifications  : %s", ", ".join(specs))
    if techs:    logger.info("[ENTITIES] technologies    : %s", ", ".join(techs))
    if industs:  logger.info("[ENTITIES] industries      : %s", ", ".join(industs))
    if not any([products, specs, techs, industs]):
        logger.info("[ENTITIES] none extracted")
    for cat_entry in rs.get("categories", []):
        logger.info("[RETRIEVAL] cat=%-22s  priority=%d  queries=%d",
                    cat_entry.get("category", "?"),
                    cat_entry.get("priority", 0),
                    len(cat_entry.get("search_queries", [])))
        for q in cat_entry.get("search_queries", []):
            logger.info("[RETRIEVAL]   → %s", q)
    logger.info("[ANALYTICS] requires=%s  categories=%d",
                ad.get("requires_analytics", False),
                len(ad.get("analytics_categories", [])))
    logger.info("[CONSTRAINTS] must_include=%s  min_confidence=%.2f",
                rc.get("must_include_categories", []),
                rc.get("minimum_confidence", 0.75))
    rd = p1_output.get("routing_decision", {})
    logger.info("[ROUTING]  human_needed=%s  escalation=%s  dept=%s  priority=%s",
                rd.get("requires_human_attention", False),
                rd.get("escalation_requested", False),
                rd.get("routing_department", "?"),
                rd.get("routing_priority", "?"))
    bs = p1_output.get("business_signals", {})
    active_signals = [k for k, v in bs.items() if v]
    if active_signals:
        logger.info("[SIGNALS]  %s", ", ".join(active_signals))
    st = p1_output.get("state_transition", {})
    if st.get("focus_changed"):
        logger.info("[STATE]    focus_changed=True  %s → %s",
                    st.get("previous_focus", "?"), st.get("current_focus", "?"))
    spec_uncertain = ee.get("specification_uncertain", False)
    if spec_uncertain:
        logger.warning("[ENTITIES] specification_uncertain=True — confidence penalised")
    if p1_status == "fallback":
        logger.warning("[P1 STATUS] FALLBACK — reason: %s", p1_meta.get("reason", "unknown"))
    else:
        logger.info("[P1 STATUS] ok  |  attempts=%d", p1_meta.get("attempts", 1))

    # Log retrieval_contract (Issues 1/2/3/6)
    rc_contract  = p1_output.get("retrieval_contract") or {}
    det_mode     = rc_contract.get("deterministic_mode") or {}
    num_constr   = rc_contract.get("numeric_constraints") or []
    requirements = rc_contract.get("requirements") or []
    if det_mode.get("active"):
        logger.info("[CONTRACT] deterministic=True  field=%s  direction=%s",
                    det_mode.get("field"), det_mode.get("direction"))
    if num_constr:
        logger.info("[CONTRACT] numeric_constraints=%s", num_constr)
    if requirements:
        logger.info("[CONTRACT] requirements=%s",
                    [{"field": r.get("field"), "op": r.get("operator"), "value": r.get("value")}
                     for r in requirements[:5]])
    if rc_contract.get("entity"):
        logger.info("[CONTRACT] entity=%s  specs=%s",
                    rc_contract.get("entity"), rc_contract.get("specifications", []))
    # Log which business understanding was active
    bu = p1_output.get("business_understanding", {})
    logger.info(
        "[BIZ_UNDERSTANDING] business=%s  type=%s  industry=%s  source=%s",
        bu.get("business_name", "(none)"),
        bu.get("business_type", "(none)"),
        ", ".join(bu.get("industry", [])) or "(none)",
        bu.get("source", "?"),
    )
    logger.info("─" * 68)
    logger.info("Pipeline 1-3 complete | user=%s conv=%s intent=%s conv_conf=%.2f intent_conf=%.2f msgs=%d elapsed=%.0fms",
                user_id, conversation_id[:8], pi.get("category", "?"),
                ca.get("conversation_confidence", 0.0),
                pi.get("confidence", 0.0),
                context["fetch_count"], elapsed_ms)

    # ── Persistent escalation state tracking (Fix 1) ───────────────────────────
    current_escalation = rd.get("escalation_requested", False)
    esc_state = _conversation_escalation_state.get(conversation_id, {})

    if current_escalation:
        # New escalation — open or refresh it
        _conversation_escalation_state[conversation_id] = {
            "open":          True,
            "level":         rd.get("routing_priority", "high"),
            "reason":        p1_output.get("intent_analysis", {}).get("primary_intent", {}).get("reason", ""),
            "created_at":    datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "message_count": context["fetch_count"],
        }
        esc_state = _conversation_escalation_state[conversation_id]
    elif esc_state.get("open"):
        # Prior escalation is still open — check if latest message resolves it
        RESOLUTION_SIGNALS = {
            "thank you", "thanks", "resolved", "never mind", "cancel",
            "forget it", "no need", "ok thanks", "got it",
        }
        latest_lower = (latest_message.get("content") or "").lower()
        if any(sig in latest_lower for sig in RESOLUTION_SIGNALS):
            _conversation_escalation_state[conversation_id]["open"] = False
            logger.info("[ESCALATION] closed | conv=%s reason=resolution_signal", conversation_id[:8])
        else:
            logger.info(
                "[ESCALATION] still open | conv=%s level=%s",
                conversation_id[:8], esc_state.get("level"),
            )

    # Inject open_escalation into p1_output so retrieval and downstream can see it
    p1_output["open_escalation"] = _conversation_escalation_state.get(conversation_id, {"open": False})

    # Log escalation state
    esc = p1_output.get("open_escalation", {})
    logger.info(
        "[ESCALATION] state=%s  level=%s",
        "open" if esc.get("open") else "closed",
        esc.get("level", "none"),
    )
    if esc.get("open"):
        logger.info(
            "[ESCALATION] open=True  level=%s  reason=%s",
            esc.get("level", "?"), (esc.get("reason") or "?")[:80],
        )

    # ── Step 4: Hybrid Retrieval — Metadata-filtered Qdrant search ─────────────
    retrieval_output = await run_hybrid_retrieval(
        user_id   = user_id,
        p1_output = p1_output,
    )

    elapsed_ms = (time.monotonic() - t_start) * 1000

    r_id      = retrieval_output.get("retrieval_id", "?")
    r_cats    = retrieval_output.get("categories_searched", [])
    r_total   = retrieval_output.get("total_candidates_found", 0)
    r_final   = retrieval_output.get("total_candidates_after_filtering", 0)
    r_elapsed = retrieval_output.get("elapsed_ms", 0.0)
    r_analytics = retrieval_output.get("analytics_searched", False)

    logger.info(
        "Pipeline 1-4 complete | user=%s conv=%s retrieval_id=%s cats=%s "
        "candidates=%d→%d analytics=%s retrieval_ms=%.0f total_ms=%.0f",
        user_id, conversation_id[:8], r_id, r_cats,
        r_total, r_final, r_analytics, r_elapsed, elapsed_ms,
    )

    logger.info(
        "[RETRIEVAL]  diversity_score=%.3f  deterministic=%s  requirements=%d",
        retrieval_output.get("retrieval_diversity_score", 0.0),
        retrieval_output.get("deterministic_mode_used", False),
        len((retrieval_output.get("retrieval_contract_applied") or {}).get("requirements", [])),
    )

    # ── Step 5: Cross-Encoder Reranking ────────────────────────────────────────
    standalone_query = (
        ca.get("standalone_query")
        or (latest_message.get("content") or "")[:200]
        or pi.get("category", "inquiry")
    )
    reranked_chunks = await rerank_candidates(
        query=standalone_query,
        candidates=retrieval_output.get("results", []),
        top_k=7,
    )

    # ── Step 6: Grounded Response Generation Pipeline ─────────────────────────
    p2_output = await run_processor_2(
        messages=messages,
        latest_message=latest_message,
        conversation_meta=conv_meta,
        business_context=biz_ctx,
        p1_output=p1_output,
        retrieved_chunks=reranked_chunks,
    )

    # Telemetry logging for pipeline stages
    strat_mode = p2_output.get("strategy_mode", "?")
    gr_rep = p2_output.get("grounding_report") or {}
    pol_rep = p2_output.get("policy_report") or {}
    c_summary = p2_output.get("contract_summary") or {}

    logger.info(
        "[GROUNDED PIPELINE] conv=%s mode=%s facts=%d conflicts=%d grounded=%s (score=%.2f) action=%s send_email=%s",
        conversation_id[:8],
        strat_mode,
        c_summary.get("facts_count", 0),
        c_summary.get("conflicts_count", 0),
        gr_rep.get("is_grounded", True),
        gr_rep.get("grounding_score", 1.0),
        p2_output.get("action"),
        p2_output.get("send_email"),
    )
    if gr_rep.get("violations"):
        logger.warning("[GROUNDED PIPELINE] grounding violations: %s", gr_rep.get("violations"))

    # ── Step 7: Dispatch to emailservice via Redis ────────────────────────────
    has_body = bool(p2_output.get("email_body"))
    response_payload = {
        "action":            "reply" if has_body else p2_output.get("action", "reply"),
        "conversation_id":   conversation_id,
        "message_id":        message_id,
        "thread_id":         conv_meta.get("thread_id", thread_id),
        "user_id":           user_id,
        "response_text":     p2_output.get("email_body", ""),
        "confidence":        p2_output.get("confidence", 0.0),
        "send_email":        True if has_body else False,
        "trace_id":          event.get("trace_id", ""),
        "escalation_reason": p2_output.get("escalation_reason"),
        "email_subject":     p2_output.get("email_subject"),
        "strategy_mode":     strat_mode,
    }
    dispatched = await _dispatch_automation_response(response_payload)

    elapsed_ms = (time.monotonic() - t_start) * 1000

    logger.info(
        "Pipeline 1-7 complete | user=%s conv=%s mode=%s action=%s conf=%.2f send_email=%s dispatched=%s total_ms=%.0f",
        user_id, conversation_id[:8], strat_mode, p2_output.get("action"),
        p2_output.get("confidence", 0.0), p2_output.get("send_email"), dispatched, elapsed_ms,
    )

    return {
        "status":             "pipeline_complete",
        "user_id":            user_id,
        "message_id":         message_id,
        "conversation_id":    conversation_id,
        "thread_id":          conv_meta.get("thread_id", thread_id),
        "fetch_count":        context["fetch_count"],
        "fetch_reason":       context["fetch_reason"],
        "conversation":       conv_meta,
        "latest_message":     latest_message,
        "business_context":   biz_ctx,
        "processor_1_output": p1_output,
        "retrieval_output":   retrieval_output,
        "reranked_chunks":    reranked_chunks,
        "processor_2_output": p2_output,
        "dispatched":         dispatched,
        "elapsed_ms":         elapsed_ms,
    }


@router.post("/trigger")
async def trigger_automation(payload: AutomationTrigger) -> dict:
    return await process_event(payload.model_dump(by_alias=True))


@router.post("/process")
async def process_fallback(payload: AutomationTrigger) -> dict:
    return await trigger_automation(payload)


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "automationservice", "version": "1.0.0"}
