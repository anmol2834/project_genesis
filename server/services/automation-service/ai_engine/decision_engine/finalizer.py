"""
Decision Engine — Finalizer
============================
The final control layer of the ACRE pipeline.

Evaluation order (strict priority):
  1. Policy hard exits     — REJECT / HUMAN_REVIEW / SKIP (no LLM called)
  2. LLM output checks     — no_response status, empty reply
  3. Final validation      — spam override, confidence floor, safe mode compliance
  4. Response validation   — passed/failed from validators layer
  5. Consistency check     — intent vs reply semantic similarity
  6. Confidence threshold  — below floor → human_review
  7. Default allow         — all checks passed → send_reply

Public interface (called by orchestrator — signature unchanged):
  await finalizer.finalize(policy_decision, validation_result, confidence_score,
                           intent_result, ai_input)

Returns: AIEngineOutput (strict Pydantic schema, extra="forbid")

Internal flow uses FinalDecision → mapped to AIEngineOutput at the end.
Full DecisionTrace is logged for every pipeline run.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..schemas.ai_output import AIEngineOutput, AIDecisionStatus, OutputMetadata, OutputRouting
from ..schemas.ai_input import AIEngineInput
from ..schemas.intent_schema import IntentResult
from ..confidence_engine.schema import ConfidenceScore, ConfidenceLevel
from ..policy_engine.schema import PolicyDecision
from ..policy_engine.rules import PolicyAction
from ..validators.response_validator import ValidationResult
from ..validators.json_validator import ParsedLLMOutput

from .schema import FinalDecision, FinalAction, DecisionTrace
from .rules import (
    RULE_101, RULE_102, RULE_103,
    RULE_201, RULE_202,
    RULE_301,
    RULE_401,
    RULE_501,
    RULE_601, RULE_901,
    CONFIDENCE_HUMAN_REVIEW_BELOW,
)
from .consistency import check_consistency, ConsistencyResult
from .validator import run_final_validation, FinalValidationResult

logger = logging.getLogger(__name__)

# Sentinel for "LLM was not called" (early exit path)
_NO_LLM = ParsedLLMOutput(
    status="not_called", reply="", confidence=0.0,
    intent_handled="", raw_text=""
)


class DecisionFinalizer:
    """
    Stateless final decision engine.
    Combines all upstream signals into a single, traceable FinalDecision.
    """

    async def finalize(
        self,
        policy_decision: PolicyDecision,
        validation_result: Optional[ValidationResult],
        confidence_score: ConfidenceScore,
        intent_result: IntentResult,
        ai_input: AIEngineInput,
        parsed_output: Optional[ParsedLLMOutput] = None,
    ) -> AIEngineOutput:
        """
        Produce the final AIEngineOutput.

        Args:
            policy_decision:   Output from Policy Engine.
            validation_result: Output from Response Validator (None on early exit).
            confidence_score:  Output from Confidence Engine.
            intent_result:     Output from Intent Engine.
            ai_input:          Original pipeline input.
            parsed_output:     Parsed LLM output (None on early exit).

        Returns:
            AIEngineOutput — strict schema, no extra fields.
        """
        llm_out = parsed_output or _NO_LLM
        decision = await self._decide(
            policy_decision, validation_result, confidence_score,
            intent_result, llm_out,
        )

        # Log the full trace
        logger.info(
            "Decision Engine: %s | rule=%s | conf=%.3f | intent=%s | safe=%s",
            decision.action.value,
            decision.trace.policy_rule_id,
            decision.confidence,
            intent_result.intent.value,
            decision.trace.safe_mode,
            extra={"trace": decision.trace.to_dict()},
        )

        return self._to_output(decision, intent_result, confidence_score, ai_input, llm_out)

    # ── Core decision logic ───────────────────────────────────────────────────

    async def _decide(
        self,
        policy: PolicyDecision,
        validation: Optional[ValidationResult],
        confidence: ConfidenceScore,
        intent: IntentResult,
        llm_out: ParsedLLMOutput,
    ) -> FinalDecision:
        """Run the full decision tree and return a FinalDecision."""

        # ── RULE 1xx: Policy hard exits ───────────────────────────────────
        if policy.action == PolicyAction.REJECT:
            return self._make_decision(
                RULE_101, FinalAction.REJECT, "",
                RULE_101.reason_template.format(policy_reason=policy.reason),
                confidence, policy, intent, llm_out,
                validation_passed=False, validation_reasons=[policy.reason],
                consistency_score=0.0, consistency_passed=False,
            )

        if policy.action == PolicyAction.HUMAN_REVIEW:
            return self._make_decision(
                RULE_102, FinalAction.HUMAN_REVIEW, "",
                RULE_102.reason_template.format(policy_reason=policy.reason),
                confidence, policy, intent, llm_out,
                validation_passed=False, validation_reasons=[policy.reason],
                consistency_score=0.0, consistency_passed=False,
            )

        if policy.action == PolicyAction.SKIP:
            return self._make_decision(
                RULE_103, FinalAction.SKIP, "",
                RULE_103.reason_template.format(policy_reason=policy.reason),
                confidence, policy, intent, llm_out,
                validation_passed=True, validation_reasons=[],
                consistency_score=0.0, consistency_passed=True,
            )

        # ── RULE 2xx: LLM output checks ───────────────────────────────────
        # If LLM returned no_response status, treat as skip (LLM decided not to reply)
        if llm_out.status == "not_called":
            return self._make_decision(
                RULE_201, FinalAction.SKIP, "",
                RULE_201.reason_template,
                confidence, policy, intent, llm_out,
                validation_passed=True, validation_reasons=[],
                consistency_score=0.0, consistency_passed=True,
            )

        # LLM explicitly returned no_response — route to human review instead of skip
        # (gives the lead a chance to be handled by a human rather than silently dropped)
        if llm_out.status == "no_response":
            return self._make_decision(
                RULE_201, FinalAction.HUMAN_REVIEW, "",
                "LLM returned no_response — routing to human review to avoid silent drop.",
                confidence, policy, intent, llm_out,
                validation_passed=True, validation_reasons=[],
                consistency_score=0.0, consistency_passed=True,
            )

        if not llm_out.reply or not llm_out.reply.strip():
            return self._make_decision(
                RULE_202, FinalAction.HUMAN_REVIEW, "",
                "LLM produced empty reply — routing to human review.",
                confidence, policy, intent, llm_out,
                validation_passed=True, validation_reasons=[],
                consistency_score=0.0, consistency_passed=True,
            )

        # ── RULE 3xx: Confidence floor ────────────────────────────────────
        # ENTERPRISE FIX: Low confidence does NOT drop the reply.
        # If LLM produced a valid reply, preserve it and route to human review.
        # The human can approve or discard — but the reply is never silently lost.
        if confidence.final_score < CONFIDENCE_HUMAN_REVIEW_BELOW:
            return self._make_decision(
                RULE_301, FinalAction.HUMAN_REVIEW, llm_out.reply,
                RULE_301.reason_template.format(
                    confidence=confidence.final_score,
                    threshold=CONFIDENCE_HUMAN_REVIEW_BELOW,
                ),
                confidence, policy, intent, llm_out,
                validation_passed=True, validation_reasons=[],
                consistency_score=0.0, consistency_passed=True,
            )

        # ── Final validation (spam override, safe mode compliance) ────────
        final_val: FinalValidationResult = run_final_validation(
            intent, confidence, policy, llm_out
        )

        # ── RULE 4xx: Response validation failure ─────────────────────────
        val_passed = validation is not None and validation.passed
        val_reasons = validation.failure_reasons if validation else ["validation_result missing"]

        if not val_passed:
            return self._make_decision(
                RULE_401, FinalAction.SKIP, "",
                RULE_401.reason_template.format(reasons="; ".join(val_reasons)),
                confidence, policy, intent, llm_out,
                validation_passed=False, validation_reasons=val_reasons,
                consistency_score=0.0, consistency_passed=True,
            )

        if not final_val.passed:
            return self._make_decision(
                RULE_401, FinalAction.SKIP, "",
                RULE_401.reason_template.format(reasons="; ".join(final_val.reasons)),
                confidence, policy, intent, llm_out,
                validation_passed=False, validation_reasons=final_val.reasons,
                consistency_score=0.0, consistency_passed=True,
            )

        # ── RULE 5xx: Consistency check ───────────────────────────────────
        reply_text = validation.sanitized_reply if validation else llm_out.reply
        consistency: ConsistencyResult = await check_consistency(
            reply=reply_text,
            intent=intent.intent.value,
        )

        if consistency.critically_low:
            # SAFETY RULE: Only route to human review if reply is also very short
            # (a critically low consistency score on a long, helpful reply is likely
            # a false positive from the embedding model, not actual hallucination)
            if len(reply_text.strip()) < 30:
                return self._make_decision(
                    RULE_501, FinalAction.HUMAN_REVIEW, reply_text,
                    RULE_501.reason_template.format(score=consistency.score),
                    confidence, policy, intent, llm_out,
                    validation_passed=True, validation_reasons=[],
                    consistency_score=consistency.score,
                    consistency_passed=False,
                )
            else:
                # Long reply with low consistency score — likely a false positive
                # Preserve the reply and allow it
                logger.warning(
                    "Consistency score critically low but reply is substantial — allowing | "
                    "score=%.3f reply_len=%d intent=%s",
                    consistency.score, len(reply_text), intent.intent.value,
                )

        # ── RULE 6xx / 9xx: Allow ─────────────────────────────────────────
        rule = RULE_601 if policy.is_safe_mode else RULE_901
        reason = rule.reason_template.format(confidence=confidence.final_score)

        return self._make_decision(
            rule, FinalAction.SEND_REPLY, reply_text,
            reason,
            confidence, policy, intent, llm_out,
            validation_passed=True, validation_reasons=[],
            consistency_score=consistency.score,
            consistency_passed=consistency.passed,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_decision(
        self,
        rule,
        action: FinalAction,
        reply: str,
        reason: str,
        confidence: ConfidenceScore,
        policy: PolicyDecision,
        intent: IntentResult,
        llm_out: ParsedLLMOutput,
        validation_passed: bool,
        validation_reasons: list,
        consistency_score: float,
        consistency_passed: bool,
    ) -> FinalDecision:
        trace = DecisionTrace(
            policy_action=policy.action.value,
            policy_rule_id=policy.matched_rule_id,
            policy_layer=policy.layer_trace,
            llm_status=llm_out.status,
            llm_intent_handled=llm_out.intent_handled,
            llm_confidence=llm_out.confidence,
            validation_passed=validation_passed,
            validation_reasons=validation_reasons,
            consistency_score=consistency_score,
            consistency_passed=consistency_passed,
            final_action=action.value,
            final_reason=reason,
            confidence_level=confidence.confidence_level.value,
            safe_mode=policy.is_safe_mode,
        )
        return FinalDecision(
            action=action,
            reply=reply,
            reason=reason,
            confidence=confidence.final_score,
            trace=trace,
        )

    def _to_output(
        self,
        decision: FinalDecision,
        intent: IntentResult,
        confidence: ConfidenceScore,
        ai_input: AIEngineInput,
        llm_out: Optional[ParsedLLMOutput] = None,
    ) -> AIEngineOutput:
        """Map FinalDecision → AIEngineOutput (the public pipeline contract)."""
        action_map = {
            FinalAction.SEND_REPLY:   AIDecisionStatus.SUCCESS,
            FinalAction.SKIP:         AIDecisionStatus.NO_RESPONSE,
            FinalAction.HUMAN_REVIEW: AIDecisionStatus.HUMAN_REVIEW,
            FinalAction.REJECT:       AIDecisionStatus.REJECTED,
        }
        status = action_map[decision.action]

        # HARD RULE: NEVER lose a valid reply.
        # If LLM produced a reply, preserve it regardless of routing decision.
        reply = decision.reply
        if not reply and llm_out and llm_out.reply and llm_out.reply.strip():
            reply = llm_out.reply
            logger.info("Reply rescued from llm_out — decision had empty reply | action=%s", decision.action.value)

        # ── Enterprise metadata block ─────────────────────────────────────
        meta = OutputMetadata(
            conversation_id=str(ai_input.conversation_id),
            thread_id=ai_input.thread_id,
            message_id=ai_input.incoming_message.message_id,
            reply_to=ai_input.incoming_message.from_email,
            user_id=str(ai_input.user_id),
            email_account_id=str(ai_input.email_account_id),
            lead_email=ai_input.incoming_message.from_email,
        )

        # ── Routing decision ──────────────────────────────────────────────
        send = (status == AIDecisionStatus.SUCCESS)
        routing = OutputRouting(
            send_email=send,
            priority="high" if confidence.final_score >= 0.85 else "normal",
            requires_human=(status == AIDecisionStatus.HUMAN_REVIEW),
        )

        # ── Email payload — ALWAYS built when reply exists ────────────────
        # Built from ai_input metadata — LLM never touches this.
        subject_raw   = (ai_input.subject or "").strip()
        reply_subject = (
            f"Re: {subject_raw}"
            if subject_raw and not subject_raw.lower().startswith("re:")
            else (subject_raw or "Re: ")
        )
        html_body = (
            "<p>" + reply.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
            if reply else ""
        )

        email_payload = {
            "provider": ai_input.account_metadata.provider,
            "headers": {
                "to":          ai_input.incoming_message.from_email,
                "from":        str(ai_input.email_account_id),
                "subject":     reply_subject,
                "in_reply_to": ai_input.incoming_message.message_id,
                "references":  ai_input.thread_id,
            },
            "body": {
                "text": reply,
                "html": html_body,
            },
            "metadata": {
                "conversation_id":  str(ai_input.conversation_id),
                "thread_id":        ai_input.thread_id,
                "message_id":       ai_input.incoming_message.message_id,
                "user_id":          str(ai_input.user_id),
                "email_account_id": str(ai_input.email_account_id),
                "lead_email":       ai_input.incoming_message.from_email,
            },
            "send": send,
        }

        payload_ready = bool(reply)
        logger.info(
            "Finalizer output | status=%s | reply_generated=%s | reply_preserved=%s | "
            "payload_created=%s | send=%s | thread=%s | message=%s",
            status.value,
            bool(reply),
            payload_ready,
            payload_ready,
            send,
            ai_input.thread_id,
            ai_input.incoming_message.message_id,
        )
        print(
            f"[FINALIZER] status={status.value} reply_generated={bool(reply)} "
            f"reply_preserved={payload_ready} payload_created={payload_ready} "
            f"send={send} thread={ai_input.thread_id}"
        )

        # ── Validate metadata completeness ────────────────────────────────
        missing = [k for k, v in meta.model_dump().items() if not v]
        if missing:
            logger.warning("OUTPUT METADATA INCOMPLETE: missing=%s | conv=%s", missing, meta.conversation_id)

        # ── Determine reason field ────────────────────────────────────────
        reason = None
        if status != AIDecisionStatus.SUCCESS:
            reason = decision.reason or f"Routed to {status.value}"

        return AIEngineOutput(
            status=status,
            reply=reply,
            confidence=decision.confidence,
            intent_handled=intent.intent.value,
            reason=reason,
            metadata=meta,
            routing=routing,
            email_payload=email_payload,
            conversation_id=ai_input.conversation_id,
        )
