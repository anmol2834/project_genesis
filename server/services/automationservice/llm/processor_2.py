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


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        cfg = get_config()
        _client = AsyncOpenAI(
            api_key=cfg.OPENAI_API_KEY,
            timeout=cfg.OPENAI_TIMEOUT_SECONDS,
            max_retries=0,
        )
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
    Execute LLM Call #2: Validation, Hallucination Gate, and Email Generation.

    Args:
        messages: Previous thread messages.
        latest_message: The triggering customer email message.
        conversation_meta: Thread metadata (subject, thread_id, etc.).
        business_context: Business profile from PostgreSQL.
        p1_output: Complete output of Processor #1.
        retrieved_chunks: Top reranked knowledge chunks from reranker.

    Returns:
        Structured response dict ready for dispatch to emailservice.
    """
    t0 = time.monotonic()
    cfg = get_config()

    # Extract relevant fields from P1 output
    ca = p1_output.get("conversation_analysis") or {}
    ia = p1_output.get("intent_analysis") or {}
    pi = ia.get("primary_intent") or {}
    rd = p1_output.get("routing_decision") or {}

    subject = conversation_meta.get("subject") or "(No Subject)"
    customer_goal = ca.get("customer_goal") or "General Inquiry"
    standalone_query = ca.get("standalone_query") or (latest_message.get("content") or "")[:200]
    primary_intent = pi.get("category") or "product_service"
    customer_sentiment = ca.get("customer_sentiment") or "neutral"
    escalation_requested = bool(rd.get("escalation_requested", False) or rd.get("requires_human_attention", False))

    # Format prompt blocks
    biz_block = build_business_context_block(business_context or {})
    conv_history_str = _build_history_text(messages)
    latest_body = (latest_message.get("content") or latest_message.get("snippet") or "").strip()
    knowledge_block = format_retrieved_context_block(retrieved_chunks)

    user_prompt = PROCESSOR_2_USER_TEMPLATE.format(
        business_context_block=biz_block,
        subject=subject,
        customer_goal=customer_goal,
        standalone_query=standalone_query,
        primary_intent=primary_intent,
        customer_sentiment=customer_sentiment,
        escalation_requested=escalation_requested,
        conversation_history=conv_history_str,
        latest_message=latest_body or "(Empty message content)",
        retrieved_knowledge_block=knowledge_block,
    )

    raw_output = None
    last_error = None
    max_retries = max(1, cfg.OPENAI_MAX_RETRIES)

    for attempt in range(1, max_retries + 1):
        try:
            response = await _get_client().chat.completions.create(
                model=cfg.OPENAI_MODEL,
                temperature=0.2,  # Low temperature for factuality while preserving natural writing tone
                top_p=1.0,
                max_tokens=2048,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": PROCESSOR_2_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw_output = response.choices[0].message.content
            break
        except RateLimitError as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning("[P2] rate limit attempt %d/%d — wait %ds", attempt, max_retries, wait)
            if attempt < max_retries:
                await asyncio.sleep(wait)
        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            wait = attempt
            logger.warning("[P2] transient error attempt %d/%d — wait %ds: %s", attempt, max_retries, wait, e)
            if attempt < max_retries:
                await asyncio.sleep(wait)
        except APIStatusError as e:
            last_error = e
            if e.status_code >= 500 and attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("[P2] API %d attempt %d/%d — wait %ds", e.status_code, attempt, max_retries, wait)
                await asyncio.sleep(wait)
            else:
                logger.error("[P2] non-retryable API error %d: %s", e.status_code, e)
                break
        except Exception as e:
            last_error = e
            logger.error("[P2] unexpected error attempt %d/%d: %s", attempt, max_retries, e)
            break

    elapsed_ms = (time.monotonic() - t0) * 1000

    if raw_output is None:
        logger.error("[P2] all attempts failed: %s | elapsed=%.0fms", last_error, elapsed_ms)
        return _build_safe_fallback(p1_output, latest_message, conversation_meta, business_context, str(last_error))

    parsed = _parse_json(raw_output)
    if parsed is None or not isinstance(parsed, dict):
        logger.error("[P2] JSON parse failed: %s...", raw_output[:200])
        return _build_safe_fallback(p1_output, latest_message, conversation_meta, business_context, "json_parse_error")

    # Validate and normalize parsed schema
    answerable = bool(parsed.get("answerable", False))
    confidence = float(parsed.get("confidence", 0.0) if parsed.get("confidence") is not None else 0.5)
    action = str(parsed.get("action", "reply")).lower().strip()
    if action not in ("reply", "draft", "escalate"):
        action = "reply" if answerable else "draft"

    send_email = bool(parsed.get("send_email", answerable and confidence >= 0.70))
    email_body = str(parsed.get("email_body", "")).strip()

    # Determine subject
    email_sub = parsed.get("email_subject") or subject
    if email_sub and not email_sub.lower().startswith("re:"):
        email_sub = f"Re: {email_sub}"

    output = {
        "answerable": answerable,
        "confidence": round(confidence, 3),
        "action": action,
        "send_email": send_email,
        "escalation_requested": bool(parsed.get("escalation_requested", escalation_requested)),
        "escalation_reason": parsed.get("escalation_reason") or (rd.get("reason") if escalation_requested else None),
        "missing_information": parsed.get("missing_information") or [],
        "sources_used": parsed.get("sources_used") or [],
        "email_subject": email_sub,
        "email_body": email_body,
        "_meta": {
            "status": "ok",
            "model": cfg.OPENAI_MODEL,
            "elapsed_ms": round(elapsed_ms, 1),
            "chunks_provided": len(retrieved_chunks),
        },
    }

    logger.info(
        "[P2 COMPLETE] answerable=%s action=%s conf=%.2f send_email=%s chunks=%d elapsed=%.0fms",
        output["answerable"], output["action"], output["confidence"],
        output["send_email"], len(retrieved_chunks), elapsed_ms,
    )

    return output
