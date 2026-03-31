"""
Prompt Compiler — Builder
==========================
Builds JSON-structured prompts for the LLM engine.

Architecture:
  - System prompt: JSON object with identity, rules, output schema
  - User prompt:   JSON object with context, classification, task
  - LLM output:   flat JSON — 4 fields only (status, reply, confidence, intent_handled)
  - Finalizer:    builds email_payload from ai_input metadata (not LLM's job)
"""
from __future__ import annotations

import logging

from .schema import CompiledPrompt, PromptMode, PromptMetadata
from .templates import build_system_prompt, build_user_prompt
from .formatter import (
    format_tone, format_conversation_history, format_incoming_message,
    format_subject, format_intent_section, format_constraints_section,
    has_sufficient_context, sanitize, format_structured_business_context,
)
from .optimizer import optimize_user_prompt, estimate_prompt_tokens
from ..context_builder.schema import SelectedContext
from ..schemas.intent_schema import IntentResult, SentimentType, RiskFlag
from ..preprocess.processor import PreprocessedInput
from ..policy_engine.schema import PolicyDecision

logger = logging.getLogger(__name__)

_MAX_TOTAL_TOKENS = 2800
_DEFAULT_COMPANY  = "our company"

# Fallback reply used when pipeline cannot produce a valid response
FALLBACK_REPLY = "Hi! Thanks for reaching out \U0001f60a Let me check this and get back to you shortly."


class PromptBuilder:
    """Stateless prompt compiler. Builds JSON-structured prompts."""

    async def build(
        self,
        context: SelectedContext,
        intent_result: IntentResult,
        preprocessed: PreprocessedInput,
        policy_decision: PolicyDecision,
    ) -> CompiledPrompt:
        constraints = policy_decision.constraints
        intent_str  = intent_result.intent.value

        # ── Mode ──────────────────────────────────────────────────────────
        mode = self._determine_mode(intent_result, policy_decision, context)

        # ── System prompt (JSON-structured) ───────────────────────────────
        company_name  = self._extract_company_name(context)
        system_prompt = build_system_prompt(company_name, intent_str)

        # ── User prompt (JSON-structured) ─────────────────────────────────
        user_prompt = self._build_user_prompt(mode, context, intent_result, preprocessed, policy_decision)

        # ── Optimize ──────────────────────────────────────────────────────
        user_prompt, _ = optimize_user_prompt(
            user_prompt,
            max_total_tokens=_MAX_TOTAL_TOKENS - len(system_prompt) // 4,
        )
        total_tokens = estimate_prompt_tokens(system_prompt, user_prompt)

        # ── Metadata ──────────────────────────────────────────────────────
        intent_fields = format_intent_section(intent_result)
        sources = context.full_result.sources_used if context.full_result else []

        metadata = PromptMetadata(
            mode=mode,
            intent=intent_fields["intent"],
            sub_intent=intent_fields["sub_intent"],
            confidence_level="medium",
            tokens_estimate=total_tokens,
            context_sources=sources,
            constraints_applied=constraints.to_dict(),
            safe_mode=mode != PromptMode.STANDARD,
            has_knowledge=bool(context.business_instruction or context.business_core),
            has_conversation=bool(context.recent_history_text),
        )

        # ── Validation log ────────────────────────────────────────────────
        metadata_present    = bool(preprocessed.thread_id and preprocessed.message_id and preprocessed.sender_email)
        conv_history        = format_conversation_history(context)
        conversation_present = "(new conversation" not in conv_history
        biz_present         = bool(context.business_instruction or context.business_core)

        logger.info(
            "Prompt compiled | mode=%s | metadata=%s | conversation=%s | biz_ctx=%s | "
            "has_products=%s | has_services=%s | has_pricing=%s | tokens=%d",
            mode.value, metadata_present, conversation_present, biz_present,
            context.has_products, context.has_services, context.has_pricing, total_tokens,
        )
        print(
            f"[PROMPT] mode={mode.value} | metadata={metadata_present} "
            f"conversation={conversation_present} biz_ctx={biz_present} "
            f"products={context.has_products} services={context.has_services} "
            f"pricing={context.has_pricing} tokens={total_tokens}"
        )

        if not metadata_present:
            logger.error(
                "CRITICAL: Metadata incomplete | thread=%s message=%s sender=%s",
                preprocessed.thread_id, preprocessed.message_id, preprocessed.sender_email,
            )

        return CompiledPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            estimated_tokens=total_tokens,
            is_safe_mode=mode != PromptMode.STANDARD,
            mode=mode,
            metadata=metadata,
        )

    def _determine_mode(self, intent_result, policy_decision, context) -> PromptMode:
        if intent_result.sentiment in (SentimentType.ABUSIVE, SentimentType.ANGRY):
            return PromptMode.ABUSE
        if RiskFlag.ABUSE_PATTERN in intent_result.risk_flags:
            return PromptMode.ABUSE
        if policy_decision.constraints.require_human_handoff:
            return PromptMode.MINIMAL
        if not has_sufficient_context(context):
            return PromptMode.NO_CONTEXT
        if policy_decision.is_safe_mode:
            return PromptMode.SAFE
        return PromptMode.STANDARD

    def _build_user_prompt(self, mode, context, intent_result, preprocessed, policy_decision) -> str:
        constraints  = policy_decision.constraints
        intent_f     = format_intent_section(intent_result)
        constraint_f = format_constraints_section(constraints)

        data_flags = {
            "has_products":  context.has_products,
            "has_services":  context.has_services,
            "has_pricing":   context.has_pricing,
            "has_use_cases": context.has_use_cases,
        }

        # Extract last AI reply from conversation history to prevent repetition
        last_ai_reply = _extract_last_ai_reply(preprocessed)

        return build_user_prompt(
            mode=mode.value,
            business_instruction=format_structured_business_context(context),
            conversation_history=format_conversation_history(context),
            subject=format_subject(preprocessed),
            incoming_message=format_incoming_message(preprocessed),
            intent=intent_f["intent"],
            sub_intent=intent_f["sub_intent"],
            sentiment=intent_f["sentiment"],
            tone=format_tone(constraints),
            max_tokens=constraint_f["max_tokens"],
            data_flags=data_flags,
            last_ai_reply=last_ai_reply,
        )

    def _extract_company_name(self, context: SelectedContext) -> str:
        import re
        instr = context.business_instruction or ""
        m = re.search(r"Business Name:\s*([^\n,]+)", instr, re.IGNORECASE)
        if m:
            return sanitize(m.group(1).strip(), 60)
        m = re.search(r"assistant for ([^,.]+)", instr, re.IGNORECASE)
        if m:
            return sanitize(m.group(1).strip(), 60)
        return _DEFAULT_COMPANY


def format_subject(preprocessed: PreprocessedInput) -> str:
    from .formatter import sanitize as _san
    return _san(preprocessed.subject or "", 120) or "(no subject)"


def _extract_last_ai_reply(preprocessed: PreprocessedInput) -> str:
    """
    Extract the most recent outgoing (AI) reply from conversation history.
    Used to prevent the LLM from repeating the same phrasing.
    Returns empty string if no prior AI reply exists.
    """
    if not preprocessed.clean_history:
        return ""
    # Walk history in reverse to find the last outgoing message
    for msg in reversed(preprocessed.clean_history):
        if msg.direction == "outgoing" and msg.clean_content.strip():
            return msg.clean_content.strip()[:300]
    return ""
