"""
automationservice — LLM Processor #2: Validation & Grounded Email Generation
============================================================================
Pipeline Position:
    Qdrant Hybrid Retrieval (broad candidates)
    ↓
    Cross-Encoder Reranker (top 5-7 pristine chunks)
    ↓
    THIS MODULE (LLM Call #2: Fact Validation & Response Generation)
    ↓
    Redis (automation_responses stream) → emailservice

Guarantees:
  - Zero hallucination: Generates content exclusively from verified facts.
  - Multi-intent resolution: Systematically answers multi-part inquiries.
  - Tone alignment: Matches business context and communication tone.
  - Fail-safe execution: Never raises; returns validated structured output.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any

_LLM_DIR = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR = os.path.dirname(_LLM_DIR)
_SERVER_DIR = os.path.dirname(os.path.dirname(_SVC_DIR))

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError, APIStatusError
from shared.config import get_config
from llm.prompts import (
    PROCESSOR_2_SYSTEM_PROMPT,
    PROCESSOR_2_USER_TEMPLATE,
)
from services.business_context import build_business_context_block
from services.reranker import format_retrieved_context_block

logger = logging.getLogger("automationservice.processor_2")

_client: AsyncOpenAI | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def _get_client() -> AsyncOpenAI:
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



def _build_history_text(messages: list[dict], max_history: int = 8) -> str:
    """Format conversation thread messages into clean text."""
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


def _parse_json(text: str) -> dict[str, Any] | None:
    """Robust JSON parser handling Markdown code blocks."""
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except Exception:
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


def _build_safe_fallback(
    p1_output: dict[str, Any],
    latest_message: dict[str, Any],
    conversation_meta: dict[str, Any],
    business_context: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Generate a safe, polite fallback response when LLM Call #2 is unavailable."""
    subject = conversation_meta.get("subject") or "your inquiry"
    re_subject = f"Re: {subject}" if not subject.lower().startswith("re:") else subject
    biz_name = (business_context or {}).get("business_name") or "Our Team"

    body = (
        f"Thank you for contacting {biz_name}.\n\n"
        "We have received your message and are currently reviewing the details. "
        "A representative will get back to you shortly with the requested information.\n\n"
        f"Best regards,\n{biz_name} Support"
    )

    return {
        "answerable": False,
        "confidence": 0.50,
        "action": "draft",
        "send_email": False,
        "escalation_requested": True,
        "escalation_reason": f"Fallback triggered: {reason}",
        "missing_information": ["Automated response generation fallback invoked"],
        "sources_used": [],
        "email_subject": re_subject,
        "email_body": body,
        "_meta": {
            "status": "fallback",
            "reason": reason,
        },
    }


async def run_processor_2(
    messages: list[dict],
    latest_message: dict,
    conversation_meta: dict,
    business_context: dict,
    p1_output: dict,
    retrieved_chunks: list[dict],
) -> dict[str, Any]:
    """
    Execute Grounded Response Generation Pipeline (Target 10-Stage Architecture).

    Stages:
        1. Verified Retrieval (Atomic VerifiedEvidence extraction)
        2. Customer Requirements (Hard, Soft, Communication separation)
        3. Grounded Context Builder (Relevance, Dedup, Conflict Detection)
        4. Response Strategy Engine (Determines authorized mode)
        5. Response Input Contract (Typed Pydantic contract)
        6. OpenAI Call #2 (Pure grounded text generation)
        7. Output Structure Validator (Typed schema enforcement)
        8. Grounding Validator (Hallucination, price, & citation verification)
        9. Response Policy Engine (Operational decisions & send_email gate)
        10. Email Renderer & Response Assembly

    Args:
        messages: Previous thread messages.
        latest_message: The triggering customer email message.
        conversation_meta: Thread metadata (subject, thread_id, etc.).
        business_context: Business profile from PostgreSQL users table.
        p1_output: Complete output of Processor #1.
        retrieved_chunks: Top reranked knowledge chunks from reranker.

    Returns:
        Structured response dict ready for dispatch to emailservice.
    """
    try:
        from pipeline.response_pipeline import run_grounded_response_pipeline

        pipeline_resp = await run_grounded_response_pipeline(
            messages=messages,
            latest_message=latest_message,
            conversation_meta=conversation_meta,
            business_context=business_context,
            p1_output=p1_output,
            retrieved_chunks=retrieved_chunks,
        )

        return {
            "answerable":           pipeline_resp.answerable,
            "confidence":           pipeline_resp.confidence,
            "action":               pipeline_resp.action,
            "send_email":           pipeline_resp.send_email,
            "escalation_requested": pipeline_resp.escalation_requested,
            "escalation_reason":    pipeline_resp.escalation_reason,
            "requires_human_review": pipeline_resp.requires_human_review,
            "missing_information":  pipeline_resp.missing_information,
            "sources_used":         pipeline_resp.sources_used,
            "email_subject":        pipeline_resp.email_subject,
            "email_body":           pipeline_resp.email_body,
            "strategy_mode":        pipeline_resp.strategy_mode,
            "grounding_report":     pipeline_resp.grounding_report.model_dump(),
            "policy_report":        pipeline_resp.policy_report.model_dump(),
            "customer_response":    pipeline_resp.customer_response.model_dump() if pipeline_resp.customer_response else None,
            "internal_validation":  pipeline_resp.internal_validation.model_dump() if pipeline_resp.internal_validation else None,
            "rendered_email":       pipeline_resp.rendered_email.model_dump() if pipeline_resp.rendered_email else None,
            "send_authorization":   pipeline_resp.send_authorization.model_dump() if pipeline_resp.send_authorization else None,
            "send_result":          pipeline_resp.send_result.model_dump() if pipeline_resp.send_result else None,
            "contract_summary":     pipeline_resp.contract_summary,
            "_meta":                pipeline_resp.meta,
        }

    except Exception as exc:
        logger.error("[processor_2] unhandled pipeline error: %s", exc, exc_info=True)
        return _build_safe_fallback(p1_output, latest_message, conversation_meta, business_context, str(exc))


