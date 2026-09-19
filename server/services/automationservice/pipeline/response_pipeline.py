"""
automationservice — Grounded Response Generation Pipeline Orchestrator (Phases 1-20)
=====================================================================================
Coordinates the complete 20-phase grounded response generation lifecycle:
  1.  VERIFIED RETRIEVAL ADAPTER (Phase 1)
  2.  CUSTOMER REQUIREMENTS ENGINE (Phases 2-3)
  3.  GROUNDED CONTEXT BUILDER & CONFLICT DETECTION (Phases 4-5)
  4.  RESPONSE STRATEGY ENGINE (Deterministic Mode Decision, Phase 6)
  5.  PROMPT INJECTION DEFENSE & FENCING (Phase 17)
  6.  RESPONSE INPUT CONTRACT (Stage 5)
  7.  OPENAI CALL #2 GENERATION (Pure text synthesis, Fact vs Language Separation, Phase 16)
  8.  OUTPUT STRUCTURE VALIDATOR (Phase 10 & 18)
  9.  GROUNDING VALIDATOR (4-tier claim classification & violation detection, Phase 11 & 16)
  10. GROUNDING FAILURE HANDLER (Deterministic routing, max 1 regeneration, Phase 12)
  11. RESPONSE POLICY ENGINE (Business rules & operational gates, Phase 13)
  12. EMAIL RENDERER (Semantically passive HTML & plain text presentation, Phase 14)
  13. SEND AUTHORIZATION GATE (Cryptographic signature verification, Phase 15)
  14. EMAIL SENDER (Strict refusal of unapproved payloads, Phase 15)
  15. DETERMINISTIC FAILURE RESOLUTION (Phase 19)
  16. CONFIDENCE & INTERNAL METADATA ISOLATION (Phase 18)
  17. STRUCTURED TELEMETRY & OBSERVABILITY (Phase 20)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from uuid import uuid4
from typing import Any, Callable, Awaitable

from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError, APIStatusError

from shared.config import get_config
from services.business_context import build_business_context_block
from llm.prompts import (
    GROUNDED_GENERATION_SYSTEM_PROMPT,
    GROUNDED_GENERATION_USER_TEMPLATE,
)
from pipeline.contracts import (
    VerifiedEvidence,
    EvidenceConflict,
    CustomerRequirements,
    ResponseStrategy,
    RequestContext,
    BusinessContextSummary,
    ResponseConstraints,
    ResponseInputContract,
    LLMCall2Output,
    GroundingReport,
    PolicyReport,
    GroundedPipelineResponse,
    RenderedEmailPayload,
    SendAuthorization,
    SendResult,
    CustomerResponse,
    InternalValidationDiagnostics,
)
from pipeline.evidence_retrieval import extract_verified_evidence
from pipeline.customer_requirements import extract_customer_requirements
from pipeline.grounded_context_builder import build_grounded_context, GroundedContextPackage
from pipeline.strategy_engine import determine_response_strategy
from pipeline.output_validator import validate_generation_output
from pipeline.grounding_validator import validate_grounding
from pipeline.grounding_failure_handler import handle_grounding_result, MAX_GROUNDING_REGENERATIONS
from pipeline.policy_engine import evaluate_response_policy
from pipeline.email_renderer import render_email
from pipeline.email_sender import issue_send_authorization, GroundedEmailSender
from pipeline.injection_defense import (
    scan_untrusted_input,
    fence_untrusted_content,
    verify_no_injection_compliance,
)
from pipeline.failure_handler import (
    FailureState,
    resolve_failure_state,
)
from pipeline.observability import (
    PipelineTelemetryEvent,
    PipelineObserver,
    mask_pii_email,
)

logger = logging.getLogger("automationservice.pipeline.response_pipeline")

_client: AsyncOpenAI | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _client is None or _client_loop != current_loop or (current_loop and current_loop.is_closed()):
        cfg = get_config()
        _client = AsyncOpenAI(
            api_key=cfg.OPENAI_API_KEY,
            timeout=cfg.OPENAI_TIMEOUT_SECONDS,
            max_retries=0,
        )
        _client_loop = current_loop
    return _client


def _format_conversation_history(messages: list[dict[str, Any]], max_history: int = 8) -> str:
    """Format previous thread messages cleanly."""
    if not messages:
        return "(No prior conversation history - this is the first message in the thread)"
    lines = []
    for msg in messages[-max_history:]:
        sender = msg.get("sender_type") or msg.get("from_name") or ("Customer" if msg.get("direction") == "inbound" else "Support")
        content = (msg.get("content") or msg.get("snippet") or "").strip()
        if content:
            clean_body = " ".join(content.split())
            lines.append(f"{sender}: {clean_body}")
    return "\n".join(lines) if lines else "(No prior conversation history)"


def _format_requirements_block(reqs: CustomerRequirements) -> str:
    """Format customer requirements for the prompt."""
    lines = []
    if reqs.hard:
        lines.append("HARD REQUIREMENTS (Must Not Violate):")
        for hr in reqs.hard:
            lines.append(f"  • {hr.field} ({hr.operator}) {hr.value}")
    else:
        lines.append("HARD REQUIREMENTS: None explicitly specified")

    if reqs.soft:
        lines.append("\nSOFT PREFERENCES:")
        for sp in reqs.soft:
            lines.append(f"  • {sp.field}: {sp.value}")

    lines.append(f"\nCOMMUNICATION: Tone={reqs.communication.tone}, Length={reqs.communication.length}")
    return "\n".join(lines)


async def _execute_call_2(
    user_prompt: str,
    system_prompt: str = GROUNDED_GENERATION_SYSTEM_PROMPT,
) -> str | None:
    """Call OpenAI Call #2 with exponential backoff for transient errors."""
    cfg = get_config()
    max_retries = max(1, cfg.OPENAI_MAX_RETRIES)
    client = _get_openai_client()

    for attempt in range(1, max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=cfg.OPENAI_MODEL,
                temperature=0.2,  # Low temperature for fact grounding
                top_p=1.0,
                max_tokens=2048,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            wait = 2 ** attempt
            logger.warning("[pipeline.call_2] rate limit attempt %d/%d — wait %ds", attempt, max_retries, wait)
            if attempt < max_retries:
                await asyncio.sleep(wait)
        except (APITimeoutError, APIConnectionError) as e:
            wait = attempt
            logger.warning("[pipeline.call_2] connection error attempt %d/%d — wait %ds: %s", attempt, max_retries, wait, e)
            if attempt < max_retries:
                await asyncio.sleep(wait)
        except APIStatusError as e:
            if e.status_code >= 500 and attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("[pipeline.call_2] API %d attempt %d/%d — wait %ds", e.status_code, attempt, max_retries, wait)
                await asyncio.sleep(wait)
            else:
                logger.error("[pipeline.call_2] non-retryable API error %d: %s", e.status_code, e)
                break
        except Exception as e:
            logger.error("[pipeline.call_2] unexpected error: %s", e)
            break
    return None


async def run_grounded_response_pipeline(
    messages: list[dict[str, Any]],
    latest_message: dict[str, Any],
    conversation_meta: dict[str, Any],
    business_context: dict[str, Any],
    p1_output: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
    email_dispatch_callback: Callable[[dict[str, Any]], Awaitable[bool]] | None = None,
) -> GroundedPipelineResponse:
    """
    Execute the complete 20-phase Grounded Response Generation Pipeline.
    """
    t0 = time.monotonic()
    request_id = f"req_{uuid4().hex[:12]}"
    cfg = get_config()

    subject = str(conversation_meta.get("subject") or "your inquiry").strip()
    thread_id = str(conversation_meta.get("thread_id") or "")
    recipient = str(conversation_meta.get("from_address") or conversation_meta.get("recipient") or "customer@example.com").strip()
    latest_body = str(latest_message.get("content") or latest_message.get("snippet") or "").strip()
    history_str = _format_conversation_history(messages)

    # ── PHASE 20: INITIALIZE OBSERVABILITY OBSERVER ───────────────────────────
    observer = PipelineObserver(request_id=request_id, conversation_id=thread_id, customer_id=recipient)
    failure_state: FailureState | None = None

    # ── PHASE 17: PROMPT INJECTION DEFENSE (UNTRUSTED INPUT SCANNING) ──────────
    t_stage = time.monotonic()
    scan_result = scan_untrusted_input(latest_body)
    fenced_customer_message = fence_untrusted_content("customer_message", scan_result.sanitized_text)
    observer.record_stage("injection_defense", (time.monotonic() - t_stage) * 1000, {"suspicious": scan_result.is_suspicious})

    # ── STAGE 1: VERIFIED RETRIEVAL ADAPTER (PHASE 1) ─────────────────────────
    t_stage = time.monotonic()
    raw_evidence = extract_verified_evidence(
        retrieved_chunks=retrieved_chunks,
        business_context=business_context,
    )
    observer.record_stage("evidence_retrieval", (time.monotonic() - t_stage) * 1000, {"count": len(raw_evidence)})

    # Failure State Check 1 & 2: No retrieval results or no evidence
    if not retrieved_chunks:
        failure_state = "NO_RETRIEVAL_RESULTS"
    elif not raw_evidence:
        failure_state = "NO_RELEVANT_EVIDENCE"

    # ── STAGE 2: CUSTOMER REQUIREMENTS ENGINE (PHASES 2-3) ─────────────────────
    t_stage = time.monotonic()
    customer_reqs = extract_customer_requirements(
        p1_output=p1_output,
        latest_message=latest_message,
        business_context=business_context,
    )
    observer.record_stage("customer_requirements", (time.monotonic() - t_stage) * 1000, {"hard": len(customer_reqs.hard)})

    # ── STAGE 3: GROUNDED CONTEXT BUILDER & CONFLICT DETECTION (PHASES 4-5) ───
    t_stage = time.monotonic()
    context_package: GroundedContextPackage = build_grounded_context(
        evidence_items=raw_evidence,
        customer_requirements=customer_reqs,
        max_facts=25,
    )
    observer.record_stage("context_builder", (time.monotonic() - t_stage) * 1000, {
        "facts": len(context_package.approved_facts),
        "conflicts": len(context_package.conflicts),
    })

    if context_package.conflicts and failure_state is None:
        failure_state = "CONFLICTING_EVIDENCE"

    # ── STAGE 4: RESPONSE STRATEGY ENGINE (PHASE 6) ───────────────────────────
    t_stage = time.monotonic()
    strategy: ResponseStrategy = determine_response_strategy(
        p1_output=p1_output,
        customer_requirements=customer_reqs,
        context_package=context_package,
        business_context=business_context,
    )
    observer.record_stage("strategy_engine", (time.monotonic() - t_stage) * 1000, {"mode": strategy.mode})

    # ── STAGE 5: RESPONSE INPUT CONTRACT ──────────────────────────────────────
    ca = (p1_output or {}).get("conversation_analysis") or {}
    biz_name = (business_context or {}).get("business_name") or "Our Team"
    contract = ResponseInputContract(
        request=RequestContext(
            customer_message=fenced_customer_message,
            subject=subject,
            thread_id=thread_id,
            objective="answer",
            history_summary=history_str[:1500],
        ),
        customer_requirements=customer_reqs,
        business_context=BusinessContextSummary(
            company_name=biz_name,
            business_type=(business_context or {}).get("business_type") or "",
            industry=(business_context or {}).get("industry") or [],
            communication_style=customer_reqs.communication.tone,
        ),
        verified_facts=context_package.approved_facts,
        conflicts=context_package.conflicts,
        constraints=ResponseConstraints(
            must_not_claim=strategy.prohibited_facts,
            must_not_offer=[],
            required_disclosures=[],
        ),
        response_strategy=strategy,
    )

    # ── STAGE 6: OPENAI CALL #2 GENERATION (PHASE 7, 8, 16) ───────────────────
    t_stage = time.monotonic()
    biz_block = build_business_context_block(business_context or {})
    reqs_block = _format_requirements_block(customer_reqs)
    evidence_block = context_package.format_prompt_block()

    user_prompt = GROUNDED_GENERATION_USER_TEMPLATE.format(
        business_context_block=biz_block,
        subject=subject,
        customer_goal=ca.get("customer_goal") or "Inquiry",
        customer_sentiment=ca.get("customer_sentiment") or "neutral",
        conversation_history=history_str,
        latest_message=fenced_customer_message,
        requirements_block=reqs_block,
        strategy_mode=strategy.mode,
        strategy_objective=strategy.objective,
        strategy_required_sections=", ".join(strategy.required_sections),
        strategy_allowed_actions=", ".join(strategy.allowed_actions) or "None",
        strategy_prohibited_facts=", ".join(strategy.prohibited_facts) or "None",
        grounded_evidence_block=evidence_block,
    )

    raw_llm_output = await _execute_call_2(user_prompt=user_prompt)
    observer.record_stage("generation_call_2", (time.monotonic() - t_stage) * 1000)

    if raw_llm_output is None and failure_state is None:
        failure_state = "LLM_TIMEOUT"

    # ── STAGE 7: OUTPUT STRUCTURE VALIDATOR (PHASE 10 & 18) ───────────────────
    t_stage = time.monotonic()
    llm_output, structure_report = validate_generation_output(
        raw_output=raw_llm_output,
        strategy=strategy,
        fallback_subject=subject,
    )
    observer.record_stage("output_validation", (time.monotonic() - t_stage) * 1000, {"valid": structure_report.is_valid})

    if not structure_report.is_valid and failure_state is None:
        failure_state = "LLM_MALFORMED_OUTPUT"

    # ── STAGE 8: GROUNDING VALIDATOR (PHASE 11 & 16) ───────────────────────────
    t_stage = time.monotonic()
    grounding_report: GroundingReport = validate_grounding(
        llm_output=llm_output,
        strategy=strategy,
        verified_facts=context_package.approved_facts,
        prohibited_fact_ids=context_package.prohibited_fact_ids,
        customer_requirements=customer_reqs,
        business_context=business_context,
    )

    # Check post-generation prompt injection compliance
    injection_violations = verify_no_injection_compliance(
        email_body=llm_output.body,
        email_subject=llm_output.subject,
        scan_result=scan_result,
    )
    if injection_violations:
        grounding_report.is_grounded = False
        grounding_report.violations.extend(injection_violations)

    observer.record_stage("grounding_validation", (time.monotonic() - t_stage) * 1000, {
        "grounded": grounding_report.is_grounded,
        "score": grounding_report.grounding_score,
    })

    # ── STAGE 8b: GROUNDING FAILURE HANDLER (PHASE 12) ────────────────────────
    t_stage = time.monotonic()
    directive = handle_grounding_result(
        llm_output=llm_output,
        grounding_report=grounding_report,
        regeneration_count=0,
        max_regenerations=MAX_GROUNDING_REGENERATIONS,
    )

    regeneration_attempted = False
    if directive.decision == "regenerate" and directive.corrective_instructions:
        logger.info("[pipeline.stage8b] Grounding failure: attempting 1 bounded regeneration with corrective prompt")
        corrective_user_prompt = f"{user_prompt}\n\n{directive.corrective_instructions}"
        retry_raw_output = await _execute_call_2(user_prompt=corrective_user_prompt)

        if retry_raw_output:
            retry_llm_output, retry_struct_report = validate_generation_output(
                raw_output=retry_raw_output,
                strategy=strategy,
                fallback_subject=subject,
            )
            retry_grounding_report = validate_grounding(
                llm_output=retry_llm_output,
                strategy=strategy,
                verified_facts=context_package.approved_facts,
                prohibited_fact_ids=context_package.prohibited_fact_ids,
                customer_requirements=customer_reqs,
                business_context=business_context,
            )
            retry_grounding_report.regeneration_count = 1
            retry_grounding_report.max_regenerations_reached = True

            llm_output = retry_llm_output
            structure_report = retry_struct_report
            grounding_report = retry_grounding_report
            regeneration_attempted = True

            directive = handle_grounding_result(
                llm_output=llm_output,
                grounding_report=grounding_report,
                regeneration_count=1,
                max_regenerations=MAX_GROUNDING_REGENERATIONS,
            )

    elif directive.decision == "sanitize" and directive.sanitized_output:
        logger.info("[pipeline.stage8b] Grounding failure: sanitizing output claims")
        llm_output = directive.sanitized_output

    observer.record_stage("grounding_failure_handler", (time.monotonic() - t_stage) * 1000, {"decision": directive.decision})

    if not grounding_report.is_grounded and failure_state is None:
        failure_state = "GROUNDING_FAILURE"

    requires_human_review = (
        directive.requires_human_review
        or not structure_report.is_valid
        or not grounding_report.is_grounded
        or llm_output.requires_human_review
        or scan_result.is_suspicious
    )

    # ── STAGE 9: RESPONSE POLICY ENGINE (PHASE 13) ────────────────────────────
    t_stage = time.monotonic()
    upstream_conf = float(ca.get("conversation_confidence", 0.85))
    policy_report: PolicyReport = evaluate_response_policy(
        llm_output=llm_output,
        strategy=strategy,
        grounding_report=grounding_report,
        business_context=business_context,
        upstream_confidence=upstream_conf,
    )

    if requires_human_review or not directive.can_send:
        policy_report.send_email = False
        policy_report.approved_for_sending = False
        if policy_report.action == "reply":
            policy_report.action = "draft" if strategy.mode != "escalate" else "escalate"

    if not policy_report.approved_for_sending and policy_report.policy_violations and failure_state is None:
        failure_state = "POLICY_FAILURE"

    observer.record_stage("policy_engine", (time.monotonic() - t_stage) * 1000, {"approved": policy_report.approved_for_sending})

    # ── STAGE 10: EMAIL RENDERER (PHASE 14) ───────────────────────────────────
    t_stage = time.monotonic()
    try:
        rendered_email: RenderedEmailPayload = render_email(
            subject=llm_output.subject,
            body=llm_output.body,
            business_context=business_context,
            disclaimers=policy_report.disclaimers_added,
            recipient=recipient,
        )
        render_status = "rendered"
    except Exception as render_exc:
        logger.error("[pipeline.render] Email rendering error: %s", render_exc)
        if failure_state is None:
            failure_state = "EMAIL_RENDERING_FAILURE"
        # Fallback to plain text rendering
        rendered_email = RenderedEmailPayload(
            recipient=recipient,
            subject=llm_output.subject,
            html_body=f"<p>{llm_output.body}</p>",
            text_body=llm_output.body,
            approval_status="draft_only",
        )
        render_status = "fallback"

    observer.record_stage("email_renderer", (time.monotonic() - t_stage) * 1000, {"status": render_status})

    # ── STAGE 11: SEND AUTHORIZATION GATE (PHASE 15) ──────────────────────────
    t_stage = time.monotonic()
    send_auth: SendAuthorization = issue_send_authorization(
        recipient=recipient,
        subject=rendered_email.subject,
        text_body=rendered_email.text_body,
        grounding_report=grounding_report,
        policy_report=policy_report,
        structure_valid=structure_report.is_valid,
    )

    rendered_email.approval_status = send_auth.status
    rendered_email.authorization = send_auth
    observer.record_stage("send_authorization", (time.monotonic() - t_stage) * 1000, {"status": send_auth.status})

    # ── STAGE 12: EMAIL SENDER (PHASE 15) ─────────────────────────────────────
    t_stage = time.monotonic()
    email_sender = GroundedEmailSender(dispatch_callback=email_dispatch_callback)
    if policy_report.send_email and send_auth.status == "approved":
        send_result = await email_sender.send(rendered_email)
    else:
        send_result = SendResult(
            sent=False,
            status="draft_stored" if policy_report.action == "draft" else "escalated",
            reason=f"Dispatch gate active: action='{policy_report.action}', auth_status='{send_auth.status}'.",
        )
    observer.record_stage("email_sender", (time.monotonic() - t_stage) * 1000, {"sent": send_result.sent})

    elapsed_ms = (time.monotonic() - t0) * 1000

    # ── STAGE 13: ASSEMBLE PIPELINE RESPONSE & ISOLATE METADATA (PHASE 18) ────
    answerable = (
        strategy.mode == "answer"
        and grounding_report.is_grounded
        and structure_report.is_valid
        and not requires_human_review
        and failure_state is None
    )
    if strategy.mode in ("clarify", "partial_result", "no_match", "escalate"):
        answerable = False

    # Strictly isolated customer-facing payload (Phase 18)
    customer_response = CustomerResponse(
        subject=llm_output.subject,
        body=llm_output.body,
        html_body=rendered_email.html_body,
        text_body=rendered_email.text_body,
        action=policy_report.action,
        send_email=policy_report.send_email and send_result.sent,
        approval_status=send_auth.status,
        disclaimers=policy_report.disclaimers_added,
    )

    # Strictly isolated internal diagnostics (Phase 18)
    internal_validation = InternalValidationDiagnostics(
        request_id=request_id,
        conversation_id=thread_id,
        customer_id=mask_pii_email(recipient),
        retrieval_id=str(conversation_meta.get("retrieval_id", "")),
        strategy_id=strategy.mode,
        composite_confidence=policy_report.confidence_score,
        retrieval_scores=[float(c.get("rerank_score", 0.0)) for c in retrieved_chunks if "rerank_score" in c],
        model_name=cfg.OPENAI_MODEL,
        latency_ms=round(elapsed_ms, 1),
        structure_valid=structure_report.is_valid,
        grounding_report=grounding_report,
        policy_report=policy_report,
        send_authorization=send_auth,
        send_result=send_result,
        retry_count=1 if regeneration_attempted else 0,
        injection_detected=scan_result.is_suspicious,
        failure_state=failure_state,
        diagnostics={
            "facts_count": len(context_package.approved_facts),
            "conflicts_count": len(context_package.conflicts),
            "claims_count": len(llm_output.claims),
            "violations_count": len(grounding_report.violations),
        },
    )

    response = GroundedPipelineResponse(
        customer_response=customer_response,
        internal_validation=internal_validation,
        answerable=answerable,
        confidence=policy_report.confidence_score,
        action=policy_report.action,
        send_email=policy_report.send_email and send_result.sent,
        email_subject=llm_output.subject,
        email_body=llm_output.body,
        strategy_mode=strategy.mode,
        escalation_requested=policy_report.escalation_requested or (directive.decision in ("block", "escalate")),
        escalation_reason=policy_report.escalation_reason or (directive.reason if directive.decision in ("block", "escalate") else None),
        requires_human_review=requires_human_review,
        missing_information=strategy.missing_information or llm_output.missing_information,
        sources_used=llm_output.sources_used,
        grounding_report=grounding_report,
        policy_report=policy_report,
        rendered_email=rendered_email,
        send_authorization=send_auth,
        send_result=send_result,
        contract_summary={
            "facts_count": len(context_package.approved_facts),
            "conflicts_count": len(context_package.conflicts),
            "hard_requirements_count": len(customer_reqs.hard),
            "strategy_mode": strategy.mode,
            "claims_count": len(llm_output.claims),
            "structure_valid": structure_report.is_valid,
            "grounding_classification": grounding_report.overall_classification,
            "regeneration_attempted": regeneration_attempted,
            "authorization_status": send_auth.status,
            "email_sent": send_result.sent,
            "failure_state": failure_state,
            "injection_detected": scan_result.is_suspicious,
        },
        meta={
            "status": "ok" if structure_report.is_valid else "fallback",
            "elapsed_ms": round(elapsed_ms, 1),
            "model": cfg.OPENAI_MODEL,
        },
    )

    # ── PHASE 20: EMIT STRUCTURED TELEMETRY EVENT ─────────────────────────────
    telemetry_event = PipelineTelemetryEvent(
        request_id=request_id,
        conversation_id=thread_id,
        customer_id=mask_pii_email(recipient),
        retrieval_id=internal_validation.retrieval_id,
        strategy_id=strategy.mode,
        model_request_id=f"call2_{request_id}",
        validation_result="valid" if structure_report.is_valid else "invalid",
        grounding_result=grounding_report.overall_classification,
        policy_result="approved" if policy_report.approved_for_sending else "blocked",
        render_result=render_status,
        send_result=send_result.status,
        latency_ms=round(elapsed_ms, 1),
        retry_count=1 if regeneration_attempted else 0,
        failure_state=failure_state,
    )
    observer.emit_summary(telemetry_event)

    return response
