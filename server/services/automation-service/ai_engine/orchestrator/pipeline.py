"""
ACRE Orchestrator — Pipeline
=============================
Central coordinator for the AI Controlled Response Engine.

Pipeline flow:
  1. Preprocess       — clean and normalize email content
  2. Intent Engine    — classify intent, sentiment, risk flags
  3. Confidence Engine — compute final confidence score
  4. Policy Engine    — evaluate rules → allow / reject / safe_mode / human_review
  5. Context Builder  — fetch vector context from Qdrant + assemble conversation history
  6. Prompt Compiler  — build the final LLM prompt
  7. LLM Engine       — call the language model
  8. JSON Validator   — parse and validate LLM JSON output
  9. Response Validator — hallucination + safety checks
  10. Decision Engine  — produce final AIEngineOutput

Integration point:
  email-service → POST /ai/process → handle_incoming_email_event(conversation_id)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional
from uuid import UUID

from ..schemas.ai_output import AIEngineOutput, AIDecisionStatus
from ..schemas.ai_input import (
    AIEngineInput, IncomingMessage, AccountMetadata, ConversationMessage,
)
from ..preprocess.processor import EmailPreprocessor
from ..intent_engine.classifier import IntentClassifier
from ..confidence_engine.scorer import ConfidenceScorer
from ..policy_engine.evaluator import PolicyEvaluator
from ..policy_engine.rules import PolicyAction
from ..context_builder.retriever import VectorRetriever
from ..context_builder.selector import ContextSelector
from ..prompt_compiler.builder import PromptBuilder
from ..llm_engine.executor import LLMExecutor, LLMExecutionError
from ..validators.json_validator import JSONValidator, JSONValidationError
from ..validators.response_validator import ResponseValidator
from ..decision_engine.finalizer import DecisionFinalizer

# Learning engine — optional, graceful degradation
try:
    from learning_engine.feedback_collector import get_feedback_collector
    _FEEDBACK_ENABLED = True
except ImportError:
    _FEEDBACK_ENABLED = False

logger = logging.getLogger(__name__)


class ACREPipeline:
    """
    Wires all ACRE layers together into a single async pipeline.
    Each layer is injected at construction for testability and replaceability.
    """

    def __init__(self) -> None:
        self.preprocessor       = EmailPreprocessor()
        self.intent_classifier  = IntentClassifier()
        self.confidence_scorer  = ConfidenceScorer()
        self.policy_evaluator   = PolicyEvaluator()
        self.vector_retriever   = VectorRetriever()
        self.context_selector   = ContextSelector()
        self.prompt_builder     = PromptBuilder()
        self.llm_executor       = LLMExecutor()
        self.json_validator     = JSONValidator()
        self.response_validator = ResponseValidator()
        self.finalizer          = DecisionFinalizer()

    async def run(self, ai_input: AIEngineInput, trace_id: str = "") -> AIEngineOutput:
        """
        Execute the full ACRE pipeline.

        Args:
            ai_input:  Fully populated AIEngineInput built from DB data.
            trace_id:  Propagated trace ID for cross-service log correlation.

        Returns:
            AIEngineOutput — strict schema with status, reply, confidence, intent_handled.
        """
        user_id_str = str(ai_input.user_id)
        conv_id_str = str(ai_input.conversation_id)
        _start_time = time.monotonic()

        log_ctx = {
            "trace_id":        trace_id,
            "user_id":         user_id_str,
            "conversation_id": conv_id_str,
        }

        logger.info("ACRE pipeline started", extra=log_ctx)

        # ── Step 1: Preprocess ────────────────────────────────────────────
        preprocessed = await self.preprocessor.process(ai_input)
        logger.debug("Step 1 preprocess done", extra={
            **log_ctx,
            "stage": "preprocess",
            "incoming_chars": len(preprocessed.clean_incoming_content),
            "history_msgs": len(preprocessed.clean_history),
        })

        # ── Step 2: Intent Engine ─────────────────────────────────────────
        intent_result = await self.intent_classifier.classify(preprocessed)
        logger.info("Step 2 intent classified", extra={
            **log_ctx,
            "stage":      "intent_engine",
            "intent":     intent_result.intent.value,
            "sub_intent": intent_result.sub_intent.value,
            "sentiment":  intent_result.sentiment.value,
            "confidence": intent_result.confidence,
            "risk_flags": [f.value for f in intent_result.risk_flags],
        })

        # ── Step 3: Confidence Engine ─────────────────────────────────────
        confidence_score = await self.confidence_scorer.score(intent_result, preprocessed)
        logger.info("Step 3 confidence scored", extra={
            **log_ctx,
            "stage":            "confidence_engine",
            "final_score":      confidence_score.final_score,
            "confidence_level": confidence_score.confidence_level.value,
            "breakdown":        confidence_score.breakdown.to_dict(),
        })

        # ── Step 4: Policy Engine ─────────────────────────────────────────
        policy_decision = await self.policy_evaluator.evaluate(
            intent_result,
            confidence_score,
            ai_input.account_metadata,
            message_text=preprocessed.clean_incoming_content,
        )
        logger.info("Step 4 policy evaluated", extra={
            **log_ctx,
            "stage":     "policy_engine",
            "action":    policy_decision.action.value,
            "rule_id":   policy_decision.matched_rule_id,
            "layer":     policy_decision.layer_trace,
            "reason":    policy_decision.reason,
            "safe_mode": policy_decision.is_safe_mode,
        })

        # Early exit — reject / human_review / skip paths skip LLM entirely
        if policy_decision.action in (PolicyAction.REJECT, PolicyAction.HUMAN_REVIEW, PolicyAction.SKIP):
            logger.info("Pipeline early exit", extra={
                **log_ctx,
                "stage":  "early_exit",
                "action": policy_decision.action.value,
                "rule":   policy_decision.matched_rule_id,
            })
            print(
                f"[ACRE] EARLY EXIT | conv={conv_id_str[:8]} "
                f"action={policy_decision.action.value} "
                f"rule={policy_decision.matched_rule_id} "
                f"reason={policy_decision.reason[:80]}"
            )
            output = await self.finalizer.finalize(
                policy_decision=policy_decision,
                validation_result=None,
                confidence_score=confidence_score,
                intent_result=intent_result,
                ai_input=ai_input,
            )
            _log_final_decision(output, log_ctx)
            _fire_feedback(ai_input, output, confidence_score, policy_decision, intent_result, _start_time)
            return output

        # ── Step 5: Context Builder ───────────────────────────────────────
        context = await self.context_selector.select(
            hits=[],
            preprocessed=preprocessed,
            intent_result=intent_result,
        )
        logger.info("Step 5 context built", extra={
            **log_ctx,
            "stage":                       "context_builder",
            "tokens_estimate":             context.total_context_tokens,
            "business_context_present":    bool(context.business_instruction or context.business_core),
            "conversation_context_present": bool(context.recent_history_text),
            "has_instruction":             bool(context.business_instruction),
            "has_business_core":           bool(context.business_core),
            "has_tone":                    bool(context.tone_guidance),
            "fallback_used":               context.full_result.retrieval_skipped if context.full_result else False,
        })
        print(
            f"[ACRE] Step 5 CONTEXT | conv={conv_id_str[:8]} "
            f"biz_ctx={bool(context.business_instruction or context.business_core)} "
            f"conv_ctx={bool(context.recent_history_text)} "
            f"tokens={context.total_context_tokens}"
        )

        # ── Validate pipeline inputs before prompt compilation ────────────
        _validate_pipeline_inputs(preprocessed, context, log_ctx)

        # ── Step 6: Prompt Compiler ───────────────────────────────────────
        compiled_prompt = await self.prompt_builder.build(
            context, intent_result, preprocessed, policy_decision
        )
        # Log prompt (mask sensitive content in production)
        logger.info("Step 6 prompt compiled", extra={
            **log_ctx,
            "stage":            "prompt_compiler",
            "prompt_mode":      compiled_prompt.mode.value,
            "estimated_tokens": compiled_prompt.estimated_tokens,
            "is_safe_mode":     compiled_prompt.is_safe_mode,
            "prompt_log": {
                "system_prompt": compiled_prompt.system_prompt[:300],
                "user_prompt":   compiled_prompt.user_prompt[:1000],
            },
        })
        print(
            f"\n[ACRE] ── STEP 6: PROMPT COMPILED ──────────────────────────\n"
            f"  conv={conv_id_str[:8]}  mode={compiled_prompt.mode.value}  "
            f"tokens={compiled_prompt.estimated_tokens}  safe={compiled_prompt.is_safe_mode}\n"
            f"SYSTEM ({len(compiled_prompt.system_prompt)} chars):\n"
            f"{compiled_prompt.system_prompt[:400]}\n"
            f"USER ({len(compiled_prompt.user_prompt)} chars):\n"
            f"{compiled_prompt.user_prompt}\n"
            f"────────────────────────────────────────────────────────────\n"
        )

        # ── Step 7: LLM Engine ────────────────────────────────────────────
        try:
            llm_response = await self.llm_executor.execute(compiled_prompt)
            logger.info("Step 7 LLM response received", extra={
                **log_ctx,
                "stage":             "llm_engine",
                "model":             llm_response.model_used,
                "prompt_tokens":     llm_response.prompt_tokens,
                "completion_tokens": llm_response.completion_tokens,
                "latency_ms":        llm_response.latency_ms,
                "retry_count":       llm_response.retry_count,
                "raw_response":      llm_response.raw_text[:500],
            })
            print(
                f"\n[ACRE] ── STEP 7: LLM RESPONSE ─────────────────────────────\n"
                f"  conv={conv_id_str[:8]}  model={llm_response.model_used}  "
                f"latency={llm_response.latency_ms}ms  "
                f"tokens={llm_response.prompt_tokens}+{llm_response.completion_tokens}\n"
                f"  RAW RESPONSE:\n    {llm_response.raw_text[:600]}\n"
            )
        except LLMExecutionError as exc:
            logger.error("LLM execution failed", extra={**log_ctx, "stage": "llm_engine", "error": str(exc)})
            output = AIEngineOutput(
                status=AIDecisionStatus.NO_RESPONSE,
                reply="",
                confidence=confidence_score.final_score,
                intent_handled=intent_result.intent.value,
                reason="LLM execution failed after retries.",
                conversation_id=ai_input.conversation_id,
            )
            _log_final_decision(output, log_ctx)
            _fire_feedback(ai_input, output, confidence_score, policy_decision, intent_result, _start_time)
            return output

        # ── Step 8: JSON Validator ────────────────────────────────────────
        try:
            parsed_output = await self.json_validator.validate(llm_response.raw_text)
            logger.info("Step 8 JSON validated", extra={
                **log_ctx,
                "stage":          "json_validator",
                "status":         parsed_output.status,
                "reply_chars":    len(parsed_output.reply),
                "llm_confidence": parsed_output.confidence,
                "intent_handled": parsed_output.intent_handled,
                "llm_response_log": {
                    "status":         parsed_output.status,
                    "reply":          parsed_output.reply[:300],
                    "confidence":     parsed_output.confidence,
                    "intent_handled": parsed_output.intent_handled,
                },
            })
        except JSONValidationError as exc:
            logger.error("JSON validation failed", extra={**log_ctx, "stage": "json_validator", "error": str(exc)})
            output = AIEngineOutput(
                status=AIDecisionStatus.NO_RESPONSE,
                reply="",
                confidence=confidence_score.final_score,
                intent_handled=intent_result.intent.value,
                reason="LLM returned malformed JSON.",
                conversation_id=ai_input.conversation_id,
            )
            _log_final_decision(output, log_ctx)
            _fire_feedback(ai_input, output, confidence_score, policy_decision, intent_result, _start_time)
            return output

        # ── Step 8b: Quality guard — retry on generic, repetitive, or off-topic replies ──
        _GENERIC_PHRASES = [
            "main check karke bataunga",
            "let me check and get back",
            "i'll get back to you",
            "feel free to ask",
            "i'm here to help",
            "hope this helps",
            "please let me know if",
            "don't hesitate to reach out",
        ]
        _NO_HISTORY_PHRASES = [
            "i don't have previous conversation",
            "i don't have any previous",
            "no previous conversation",
            "no prior conversation",
            "i have no context",
            "i don't have context",
        ]

        has_history        = bool(preprocessed.clean_history)
        reply_lower        = parsed_output.reply.lower()
        llm_denied_history = any(phrase in reply_lower for phrase in _NO_HISTORY_PHRASES)
        reply_is_generic   = any(phrase in reply_lower for phrase in _GENERIC_PHRASES)

        # Repetition check: compare with last AI reply
        from ..prompt_compiler.builder import _extract_last_ai_reply
        last_ai_reply = _extract_last_ai_reply(preprocessed)
        reply_is_repetitive = (
            bool(last_ai_reply)
            and len(parsed_output.reply) > 20
            and parsed_output.reply.strip()[:60].lower() == last_ai_reply[:60].lower()
        )

        needs_retry = (has_history and llm_denied_history) or reply_is_generic or reply_is_repetitive

        if needs_retry:
            if llm_denied_history:
                retry_reason = "denied history"
            elif reply_is_repetitive:
                retry_reason = "repetitive reply detected"
            else:
                retry_reason = "generic reply detected"

            logger.warning(
                "LLM quality issue: %s — retrying once | conv=%s",
                retry_reason, conv_id_str[:8],
            )
            print(f"[ACRE] LLM retry: {retry_reason} | conv={conv_id_str[:8]}")

            import json as _json
            retry_override = {
                "OVERRIDE": (
                    f"Issue: {retry_reason}. "
                    "You MUST: (1) directly answer the CURRENT incoming message, "
                    "(2) use completely different phrasing from any previous reply, "
                    "(3) do NOT use generic phrases. "
                    "Be specific and fresh."
                )
            }
            from ..prompt_compiler.schema import CompiledPrompt as _CP
            reinforced_prompt = _CP(
                system_prompt=compiled_prompt.system_prompt,
                user_prompt=compiled_prompt.user_prompt + "\n" + _json.dumps(retry_override, ensure_ascii=False),
                estimated_tokens=compiled_prompt.estimated_tokens + 40,
                is_safe_mode=compiled_prompt.is_safe_mode,
                mode=compiled_prompt.mode,
                metadata=compiled_prompt.metadata,
            )
            try:
                llm_response2 = await self.llm_executor.execute(reinforced_prompt)
                parsed_output2 = await self.json_validator.validate(llm_response2.raw_text)
                if parsed_output2.reply.strip():
                    parsed_output = parsed_output2
                    logger.info("LLM retry succeeded | conv=%s", conv_id_str[:8])
            except Exception as retry_exc:
                logger.warning("LLM retry failed: %s — using original output", retry_exc)

        # ── Step 8c: Re-score confidence blending LLM confidence ──────────
        # Apply a floor: if LLM returned 0.0 (copied from schema example),
        # replace with a sensible default based on whether the reply is valid.
        llm_conf = parsed_output.confidence
        if llm_conf <= 0.0:
            # LLM returned 0.0 — assign a safe default based on reply quality
            if parsed_output.reply and len(parsed_output.reply.strip()) > 20:
                llm_conf = 0.70   # Valid reply exists — reasonable confidence
            else:
                llm_conf = 0.50   # Short/minimal reply — lower confidence
            logger.info(
                "LLM confidence was 0.0 — applied floor: %.2f | conv=%s",
                llm_conf, conv_id_str[:8],
            )

        blended_confidence = await self.confidence_scorer.score(
            intent_result,
            preprocessed,
            llm_confidence=llm_conf,
        )
        logger.info(
            "Step 8c confidence blended | system=%.3f llm=%.3f final=%.3f",
            confidence_score.final_score,
            llm_conf,
            blended_confidence.final_score,
        )
        confidence_score = blended_confidence

        # ── Step 9: Response Validator ────────────────────────────────────
        validation_result = await self.response_validator.validate(
            parsed_output,
            ai_input,
            context_data_flags={
                "has_products":  context.has_products,
                "has_services":  context.has_services,
                "has_pricing":   context.has_pricing,
                "has_use_cases": context.has_use_cases,
            },
        )
        logger.debug("Step 9 response validated", extra={
            **log_ctx,
            "stage":            "response_validator",
            "passed":           validation_result.passed,
            "failure_reasons":  validation_result.failure_reasons,
        })

        # ── Step 10: Decision Engine ──────────────────────────────────────
        output = await self.finalizer.finalize(
            policy_decision=policy_decision,
            validation_result=validation_result,
            confidence_score=confidence_score,
            intent_result=intent_result,
            ai_input=ai_input,
            parsed_output=parsed_output,
        )

        elapsed_ms = (time.monotonic() - _start_time) * 1000
        _log_final_decision(output, log_ctx, elapsed_ms=elapsed_ms)
        _fire_feedback(ai_input, output, confidence_score, policy_decision, intent_result, _start_time)
        return output


# ── Module-level helpers ──────────────────────────────────────────────────────

def _validate_pipeline_inputs(preprocessed, context, log_ctx: dict) -> None:
    """
    Mandatory pipeline validation — logs CRITICAL errors for missing required data.
    Does NOT raise (never block the pipeline) but logs clearly for monitoring.
    """
    metadata_present     = bool(preprocessed.thread_id and preprocessed.message_id and preprocessed.sender_email)
    conversation_present = bool(context.recent_history_text and context.recent_history_text.strip())
    biz_context_present  = bool(context.business_instruction or context.business_core)
    prompt_valid         = metadata_present and biz_context_present

    validation_log = {
        "metadata_present":          metadata_present,
        "conversation_present":      conversation_present,
        "business_context_present":  biz_context_present,
        "prompt_valid":              prompt_valid,
        "thread_id":                 preprocessed.thread_id or "MISSING",
        "message_id":                preprocessed.message_id or "MISSING",
        "sender_email":              preprocessed.sender_email or "MISSING",
    }

    logger.info("Pipeline validation", extra={**log_ctx, **validation_log})
    print(
        f"[PIPELINE] validation | metadata={metadata_present} "
        f"conversation={conversation_present} "
        f"biz_context={biz_context_present} "
        f"prompt_valid={prompt_valid} "
        f"thread={preprocessed.thread_id or 'MISSING'} "
        f"message={preprocessed.message_id or 'MISSING'} "
        f"sender={preprocessed.sender_email or 'MISSING'}"
    )

    if not metadata_present:
        logger.error(
            "CRITICAL: Pipeline metadata incomplete | thread=%s message=%s sender=%s | conv=%s",
            preprocessed.thread_id, preprocessed.message_id, preprocessed.sender_email,
            log_ctx.get("conversation_id", ""),
        )

    if not biz_context_present:
        logger.error(
            "CRITICAL: Business context empty — LLM will hallucinate | conv=%s",
            log_ctx.get("conversation_id", ""),
        )


def _log_final_decision(output: AIEngineOutput, log_ctx: dict, elapsed_ms: float = 0.0) -> None:
    """Emit a structured final decision log."""
    logger.info("ACRE pipeline complete", extra={
        **log_ctx,
        "stage":          "decision_engine",
        "final_action":   output.status.value,
        "reply_chars":    len(output.reply),
        "confidence":     output.confidence,
        "intent_handled": output.intent_handled,
        "reason":         output.reason,
        "elapsed_ms":     round(elapsed_ms, 1),
        "decision_log": {
            "final_action":   output.status.value,
            "reason":         output.reason,
            "confidence":     output.confidence,
            "intent_handled": output.intent_handled,
        },
    })
    conv_id = str(log_ctx.get("conversation_id", ""))[:8]
    print(
        f"\n[ACRE] ── FINAL DECISION ────────────────────────────────────\n"
        f"  conv={conv_id}  status={output.status.value}  "
        f"intent={output.intent_handled}  confidence={output.confidence:.3f}  "
        f"elapsed={round(elapsed_ms, 1)}ms\n"
        f"  reason={output.reason or 'none'}\n"
        f"  reply={output.reply[:200] if output.reply else '(empty)'}\n"
        f"─────────────────────────────────────────────────────────────\n"
    )


def _fire_feedback(ai_input, output, confidence_score, policy_decision, intent_result, start_time) -> None:
    """Fire-and-forget feedback logging."""
    if not _FEEDBACK_ENABLED:
        return
    try:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        asyncio.create_task(
            get_feedback_collector().log_pipeline_result(
                user_id=ai_input.user_id,
                conversation_id=ai_input.conversation_id,
                email_account_id=ai_input.email_account_id,
                intent=intent_result.intent.value,
                sub_intent=intent_result.sub_intent.value,
                ai_reply=output.reply,
                confidence_score=confidence_score.final_score,
                final_action=output.status.value,
                safe_mode=policy_decision.is_safe_mode,
                policy_rule_id=policy_decision.matched_rule_id,
                confidence_level=confidence_score.confidence_level.value,
                elapsed_ms=elapsed_ms,
            )
        )
    except Exception:
        pass  # Never block the pipeline


# ── Singleton ─────────────────────────────────────────────────────────────────

_pipeline_instance: Optional[ACREPipeline] = None


def get_pipeline() -> ACREPipeline:
    """Return the singleton ACREPipeline instance (lazy init)."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = ACREPipeline()
    return _pipeline_instance


# ── Public entry point ────────────────────────────────────────────────────────

async def handle_incoming_email_event(
    conversation_id: UUID,
    trace_id: str = "",
) -> AIEngineOutput:
    """
    Public entry point for the ACRE pipeline.

    Called by automation-service API after email-service writes a conversation to DB.
    Loads EmailConversation + EmailAccount from DB, builds AIEngineInput, runs pipeline.

    Args:
        conversation_id: UUID of the email_conversations row just written.
        trace_id:        Cross-service trace ID for log correlation.

    Returns:
        AIEngineOutput — the AI decision for this conversation.
    """
    from sqlalchemy import text
    from shared.database import get_db_session

    logger.info(
        "handle_incoming_email_event: loading conversation",
        extra={"conversation_id": str(conversation_id), "trace_id": trace_id},
    )

    # ── Load conversation from DB ─────────────────────────────────────────
    async with get_db_session() as session:
        conv_result = await session.execute(
            text("""
                SELECT id, user_id, email_account_id, provider, thread_id,
                       message_id, from_email, to_emails, cc_emails, subject,
                       last_24h_messages, message_summary, intent_type,
                       priority_score, tags
                FROM email_conversations
                WHERE id = :conv_id
            """),
            {"conv_id": str(conversation_id)},
        )
        conv_row = conv_result.fetchone()

    if not conv_row:
        logger.error(
            "Conversation not found",
            extra={"conversation_id": str(conversation_id), "trace_id": trace_id},
        )
        return AIEngineOutput(
            status=AIDecisionStatus.NO_RESPONSE,
            reply="",
            confidence=0.0,
            intent_handled="unknown",
            reason=f"Conversation {conversation_id} not found in DB.",
            conversation_id=conversation_id,
        )

    conv = dict(conv_row._mapping)

    # ── Load email account from DB ────────────────────────────────────────
    async with get_db_session() as session:
        acct_result = await session.execute(
            text("""
                SELECT id, provider, automation_enabled, daily_send_limit,
                       daily_sent_count, warmup_enabled, is_primary
                FROM email_accounts
                WHERE id = :acct_id
            """),
            {"acct_id": str(conv["email_account_id"])},
        )
        acct_row = acct_result.fetchone()

    if not acct_row:
        logger.error(
            "Email account not found",
            extra={
                "conversation_id":  str(conversation_id),
                "email_account_id": str(conv["email_account_id"]),
                "trace_id":         trace_id,
            },
        )
        return AIEngineOutput(
            status=AIDecisionStatus.NO_RESPONSE,
            reply="",
            confidence=0.0,
            intent_handled="unknown",
            reason=f"Email account {conv['email_account_id']} not found.",
            conversation_id=conversation_id,
        )

    acct = dict(acct_row._mapping)

    # ── Build AIEngineInput ───────────────────────────────────────────────
    messages_raw = conv.get("last_24h_messages") or []

    # The last message in the array is the triggering incoming message
    # Find the most recent incoming message
    incoming_raw = None
    for msg in reversed(messages_raw):
        if msg.get("direction") == "incoming":
            incoming_raw = msg
            break

    if not incoming_raw:
        # Fallback: use the last message regardless of direction
        incoming_raw = messages_raw[-1] if messages_raw else None

    if not incoming_raw:
        logger.warning(
            "No messages in conversation — skipping",
            extra={"conversation_id": str(conversation_id), "trace_id": trace_id},
        )
        return AIEngineOutput(
            status=AIDecisionStatus.NO_RESPONSE,
            reply="",
            confidence=0.0,
            intent_handled="unknown",
            reason="No messages found in conversation.",
            conversation_id=conversation_id,
        )

    # Parse timestamp safely
    def _parse_ts(ts_val) -> datetime:
        if isinstance(ts_val, datetime):
            return ts_val
        if isinstance(ts_val, str):
            try:
                return datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            except ValueError:
                return datetime.utcnow()
        return datetime.utcnow()

    incoming_message = IncomingMessage(
        message_id=incoming_raw.get("message_id", conv["message_id"]),
        from_email=incoming_raw.get("from", conv["from_email"]),
        to=incoming_raw.get("to", conv.get("to_emails") or []),
        subject=conv.get("subject"),
        content=incoming_raw.get("content", ""),
        timestamp=_parse_ts(incoming_raw.get("timestamp")),
        cc_emails=incoming_raw.get("cc_emails"),
        has_attachments=incoming_raw.get("has_attachments", False),
    )

    # Build conversation history — ALL messages EXCEPT the triggering one.
    # The triggering message is already in IncomingMessage; including it here
    # would duplicate it in the prompt. Prior messages give the AI full context.
    history_messages = []
    for msg in messages_raw:
        # Skip the exact triggering message (matched by message_id)
        if msg.get("message_id") and msg.get("message_id") == incoming_message.message_id:
            continue
        try:
            history_messages.append(ConversationMessage(
                message_id=msg.get("message_id", ""),
                **{"from": msg.get("from", "")},
                to=msg.get("to", []),
                content=msg.get("content", ""),
                timestamp=_parse_ts(msg.get("timestamp")),
                direction=msg.get("direction", "incoming"),
                subject=msg.get("subject"),
                cc_emails=msg.get("cc_emails"),
                has_attachments=msg.get("has_attachments", False),
            ))
        except Exception as exc:
            logger.warning("Skipping malformed history message: %s", exc)

    logger.info(
        "Conversation loaded | total_messages=%d history_messages=%d incoming_id=%s thread=%s",
        len(messages_raw), len(history_messages),
        incoming_message.message_id, str(conv.get("thread_id", "")),
        extra={"conversation_id": str(conversation_id), "trace_id": trace_id},
    )

    account_metadata = AccountMetadata(
        provider=str(acct.get("provider", "gmail")),
        automation_enabled=bool(acct.get("automation_enabled", True)),
        daily_send_limit=int(acct.get("daily_send_limit", 500)),
        daily_sent_count=int(acct.get("daily_sent_count", 0)),
        warmup_enabled=bool(acct.get("warmup_enabled", False)),
        is_primary=bool(acct.get("is_primary", False)),
    )

    ai_input = AIEngineInput(
        user_id=UUID(str(conv["user_id"])),
        email_account_id=UUID(str(conv["email_account_id"])),
        conversation_id=conversation_id,
        thread_id=str(conv.get("thread_id", "")),
        subject=conv.get("subject"),
        incoming_message=incoming_message,
        last_24h_messages=history_messages,
        message_summary=conv.get("message_summary"),
        existing_intent_type=conv.get("intent_type"),
        existing_priority_score=conv.get("priority_score"),
        existing_tags=conv.get("tags") or [],
        account_metadata=account_metadata,
    )

    logger.info(
        "AIEngineInput built — running pipeline",
        extra={
            "conversation_id": str(conversation_id),
            "trace_id":        trace_id,
            "intent":          conv.get("intent_type", "unknown"),
            "history_count":   len(history_messages),
            "automation_on":   account_metadata.automation_enabled,
        },
    )

    return await get_pipeline().run(ai_input, trace_id=trace_id)
