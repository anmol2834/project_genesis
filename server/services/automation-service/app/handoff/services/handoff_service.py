"""
Handoff — Main Service
=======================
Orchestrates the complete handoff decision process.
"""

import logging
from typing import Optional
from datetime import datetime

from app.handoff.models import (
    EscalationDecision,
    EscalationReason,
    EscalationPriority,
    ConfidenceSignal,
    RiskSignals,
)
from app.handoff.confidence_engine import ConfidenceEngine
from app.handoff.risk_engine import RiskEngine

logger = logging.getLogger("automation-service.handoff")


class HandoffService:
    """Main handoff decision orchestrator"""
    
    def __init__(self):
        self.confidence_engine = ConfidenceEngine()
        self.risk_engine = RiskEngine()
    
    async def decide(
        self,
        user_id: str,
        conversation_id: str,
        thread_id: str,
        message_id: str,
        user_message: str,
        retrieval_chunks: list,
        retrieval_top_score: float,
        retrieval_count: int,
        llm_confidence: float,
        llm_status: str,
        llm_reply: Optional[str],
        hallucination_risk: str,
        guard_passed: bool,
        guard_reason: str,
        intent_confidence: float,
        intent_value: str,
        memory_turn_count: int,
        is_continuation: bool,
        entities_extracted: dict,
        entity_resolution_failed: bool,
        send_threshold: float,
        skip_threshold: float,
        conversation_history: Optional[list] = None,
        historical_avg_score: Optional[float] = None,
    ) -> EscalationDecision:
        """Decide whether to escalate to human"""
        
        is_human_owned = await self._check_human_ownership(thread_id)
        if is_human_owned:
            return EscalationDecision(
                should_escalate=False,
                reason=EscalationReason.SYSTEM_ERROR,
                priority=EscalationPriority.LOW,
                confidence_signal=ConfidenceSignal(),
                risk_signals=RiskSignals(),
                fallback_message=None,
                metadata={"blocked_reason": "human_ownership_active"},
            )
        
        confidence_signal = self.confidence_engine.compute_confidence(
            retrieval_chunks=retrieval_chunks,
            retrieval_top_score=retrieval_top_score,
            retrieval_count=retrieval_count,
            llm_confidence=llm_confidence,
            llm_status=llm_status,
            hallucination_risk=hallucination_risk,
            guard_passed=guard_passed,
            guard_reason=guard_reason,
            intent_confidence=intent_confidence,
            intent_value=intent_value,
            memory_turn_count=memory_turn_count,
            is_continuation=is_continuation,
            entities_extracted=entities_extracted,
            entity_resolution_failed=entity_resolution_failed,
            user_id=user_id,
            historical_avg_score=historical_avg_score,
        )
        
        risk_signals = self.risk_engine.analyze_risk(
            user_message=user_message,
            ai_reply=llm_reply,
            intent=intent_value,
            sentiment=None,
            conversation_history=conversation_history,
        )
        
        should_escalate_risk, risk_reason = self.risk_engine.should_escalate_on_risk(risk_signals)
        if should_escalate_risk:
            return await self._create_escalation_decision(
                True,
                self._map_risk_to_reason(risk_signals),
                self._map_risk_to_priority(risk_signals),
                confidence_signal,
                risk_signals,
                user_id,
                thread_id,
                "high_risk",
            )
        
        if not guard_passed and guard_reason in (
            "contact_cited_as_product",
            "price_claim_no_context_prices",
            "hallucinated_products",
        ):
            return await self._create_escalation_decision(
                True,
                EscalationReason.HALLUCINATION_DETECTED,
                EscalationPriority.HIGH,
                confidence_signal,
                risk_signals,
                user_id,
                thread_id,
                f"hallucination:{guard_reason}",
            )
        
        if retrieval_count == 0 and intent_value not in ("casual", "greeting"):
            return await self._create_escalation_decision(
                True,
                EscalationReason.RETRIEVAL_FAILURE,
                EscalationPriority.MEDIUM,
                confidence_signal,
                risk_signals,
                user_id,
                thread_id,
                "zero_retrieval",
            )
        
        should_escalate_conf, conf_reason = self.confidence_engine.should_escalate_on_confidence(
            confidence_signal,
            send_threshold,
            skip_threshold,
        )
        if should_escalate_conf and "too_low" in conf_reason:
            return await self._create_escalation_decision(
                True,
                EscalationReason.LOW_CONFIDENCE,
                EscalationPriority.MEDIUM,
                confidence_signal,
                risk_signals,
                user_id,
                thread_id,
                conf_reason,
            )
        
        return EscalationDecision(
            should_escalate=False,
            reason=EscalationReason.LOW_CONFIDENCE,
            priority=EscalationPriority.LOW,
            confidence_signal=confidence_signal,
            risk_signals=risk_signals,
            fallback_message=None,
            metadata={"decision": "proceed_with_ai"},
        )
    
    async def _check_human_ownership(self, thread_id: str) -> bool:
        try:
            from shared.cache import get_redis
            redis = await get_redis()
            exists = await redis.exists(f"handoff:owner:{thread_id}")
            return bool(exists)
        except Exception:
            return False
    
    async def _create_escalation_decision(
        self,
        should_escalate: bool,
        reason: EscalationReason,
        priority: EscalationPriority,
        confidence_signal: ConfidenceSignal,
        risk_signals: RiskSignals,
        user_id: str,
        thread_id: str,
        escalation_trigger: str,
    ) -> EscalationDecision:
        fallback_message = await self._generate_fallback_message(reason, priority, user_id)
        
        logger.info(
            "Escalation | user=%s thread=%s reason=%s priority=%s trigger=%s",
            user_id[:8], thread_id[:12], reason.value, priority.value, escalation_trigger,
        )
        
        return EscalationDecision(
            should_escalate=should_escalate,
            reason=reason,
            priority=priority,
            confidence_signal=confidence_signal,
            risk_signals=risk_signals,
            fallback_message=fallback_message,
            metadata={"escalation_trigger": escalation_trigger, "timestamp": datetime.utcnow().isoformat()},
        )
    
    async def _generate_fallback_message(
        self,
        reason: EscalationReason,
        priority: EscalationPriority,
        user_id: str,
    ) -> str:
        templates = {
            EscalationReason.LEGAL_THREAT: "Thank you for reaching out. Our specialist team has been notified and will get in touch with you shortly.",
            EscalationReason.REFUND_REQUEST: "I understand you're requesting a refund. Our customer service team is reviewing your request.",
            EscalationReason.ANGRY_CUSTOMER: "I sincerely apologize for your experience. Your concerns are important to us, and our team is prioritizing your case.",
            EscalationReason.PRICING_NEGOTIATION: "Thank you for your interest! Our sales team would be happy to discuss pricing options with you.",
            EscalationReason.HALLUCINATION_DETECTED: "Thank you for your inquiry. To ensure I provide accurate information, our specialist team will review your question.",
            EscalationReason.LOW_CONFIDENCE: "Thank you for reaching out. Our team is reviewing your message to provide you with the most accurate response.",
            EscalationReason.RETRIEVAL_FAILURE: "Thank you for your inquiry. Our team is gathering the information you need and will respond with details shortly.",
        }
        
        return templates.get(
            reason,
            "Thank you for your message. Our team is reviewing your inquiry and will get back to you soon.",
        )
    
    def _map_risk_to_reason(self, risk_signals: RiskSignals) -> EscalationReason:
        reasons = risk_signals.risk_reasons
        
        if any("legal" in r for r in reasons):
            return EscalationReason.LEGAL_THREAT
        if any("refund" in r or "chargeback" in r for r in reasons):
            return EscalationReason.REFUND_REQUEST
        if any("angry" in r for r in reasons):
            return EscalationReason.ANGRY_CUSTOMER
        if any("pricing" in r for r in reasons):
            return EscalationReason.PRICING_NEGOTIATION
        if any("medical" in r for r in reasons):
            return EscalationReason.MEDICAL_ADVICE
        if any("privacy" in r for r in reasons):
            return EscalationReason.DATA_PRIVACY_CONCERN
        if any("technical" in r for r in reasons):
            return EscalationReason.COMPLAINT
        
        return EscalationReason.LOW_CONFIDENCE
    
    def _map_risk_to_priority(self, risk_signals: RiskSignals) -> EscalationPriority:
        if risk_signals.risk_level >= 0.90:
            return EscalationPriority.CRITICAL
        elif risk_signals.risk_level >= 0.70:
            return EscalationPriority.HIGH
        elif risk_signals.risk_level >= 0.50:
            return EscalationPriority.MEDIUM
        else:
            return EscalationPriority.LOW
