"""
Handoff Orchestrator - Main integration point for complete escalation system
"""
import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime
import uuid

from app.handoff.models import (
    HandoffDecision, EscalationReason, RiskLevel, EscalationPriority
)
from app.handoff.confidence_engine import ConfidenceEngine
from app.handoff.risk_engine import RiskEngine
from app.handoff.ownership.ownership_manager import OwnershipManager
from app.handoff.sla.sla_manager import SLAManager
from app.handoff.audit.audit_logger import HandoffAuditLogger
from app.handoff.queue_management.queue_manager import QueueManager
from app.handoff.fallback_responses.response_generator import FallbackResponseGenerator
from app.handoff.routing.routing_engine import RoutingEngine
from app.handoff.ai_reentry.reentry_manager import AIReentryManager
from app.handoff.metrics.metrics_collector import HandoffMetrics

logger = logging.getLogger(__name__)

class HandoffOrchestrator:
    """
    Enterprise AI Decision & Escalation System
    
    Orchestrates complete handoff workflow:
    - Confidence fusion
    - Risk detection
    - Escalation decision
    - Human routing
    - Ownership management
    - SLA tracking
    - Fallback responses
    - AI re-entry
    - Complete observability
    """
    
    def __init__(
        self,
        redis_client,
        postgres_conn,
        confidence_weights: Optional[Dict] = None
    ):
        # Core engines
        self.confidence_engine = ConfidenceEngine(weights=confidence_weights)
        self.risk_engine = RiskEngine()
        
        # Lifecycle managers
        self.ownership_manager = OwnershipManager(redis_client)
        self.sla_manager = SLAManager(redis_client)
        self.queue_manager = QueueManager(redis_client)
        
        # Response & routing
        self.response_generator = FallbackResponseGenerator()
        self.routing_engine = RoutingEngine(redis_client, postgres_conn)
        
        # AI re-entry
        self.reentry_manager = AIReentryManager(redis_client, postgres_conn)
        
        # Observability
        self.audit_logger = HandoffAuditLogger(redis_client, postgres_conn)
        self.metrics = HandoffMetrics(redis_client, postgres_conn)
        
        self.redis = redis_client
        self.pg_conn = postgres_conn
    
    def evaluate_handoff(
        self,
        tenant_id: str,
        thread_id: str,
        query: str,
        retrieval_context: Dict,
        llm_response: Optional[str],
        conversation_history: list,
        intent_result: Optional[Dict] = None,
        memory_context: Optional[Dict] = None,
        hallucination_check: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> HandoffDecision:
        """
        Main handoff evaluation - decides if human escalation needed
        
        Returns HandoffDecision with complete escalation context
        """
        start_time = time.time()
        
        # Check if already human-owned
        if self.ownership_manager.is_human_owned(thread_id):
            logger.info(f"Thread {thread_id} is human-owned, blocking AI response")
            return HandoffDecision(
                should_escalate=True,
                decision="human_owned",
                confidence_score=0.0,
                risk_level=RiskLevel.MEDIUM,
                escalation_reason=EscalationReason.HUMAN_IN_LOOP,
                escalation_priority=EscalationPriority.MEDIUM,
                blocking=True,
                fallback_message="This conversation is currently being handled by our team."
            )
        
        # Check if AI is blocked from re-entry
        if self.reentry_manager.is_ai_blocked(thread_id):
            logger.info(f"AI blocked from thread {thread_id}")
            return HandoffDecision(
                should_escalate=True,
                decision="ai_blocked",
                confidence_score=0.0,
                risk_level=RiskLevel.HIGH,
                escalation_reason=EscalationReason.HUMAN_IN_LOOP,
                escalation_priority=EscalationPriority.HIGH,
                blocking=True
            )
        
        # Step 1: Calculate multi-signal confidence
        confidence_result = self.confidence_engine.calculate_confidence(
            retrieval_confidence=retrieval_context.get("confidence", 0.0),
            llm_confidence=retrieval_context.get("llm_confidence", 0.7),
            hallucination_score=hallucination_check.get("score", 1.0) if hallucination_check else 1.0,
            reranker_confidence=retrieval_context.get("reranker_confidence", 0.0),
            intent_confidence=intent_result.get("confidence", 0.0) if intent_result else 0.0,
            memory_confidence=memory_context.get("confidence", 0.0) if memory_context else 0.0,
            historical_feedback=0.0,  # TODO: integrate learning engine
            tenant_id=tenant_id
        )
        
        # Step 2: Detect risks
        risk_result = self.risk_engine.detect_risks(
            query=query,
            confidence_score=confidence_result.final_confidence,
            retrieval_context=retrieval_context,
            llm_response=llm_response,
            conversation_history=conversation_history,
            hallucination_check=hallucination_check
        )
        
        # Step 3: Make handoff decision
        decision = self._make_decision(
            confidence_result,
            risk_result,
            query,
            retrieval_context
        )
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Step 4: If escalation needed, execute full workflow
        if decision.should_escalate:
            ticket_id = str(uuid.uuid4())
            decision.ticket_id = ticket_id
            
            # Generate fallback response
            decision.fallback_message = self.response_generator.generate_response(
                escalation_reason=decision.escalation_reason.value,
                risk_level=decision.risk_level.value,
                language=metadata.get("language", "en") if metadata else "en",
                customer_emotion=risk_result.get("customer_emotion")
            )
            
            # Route to human agent
            routing_decision = self.routing_engine.route_ticket(
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                priority=decision.escalation_priority.value,
                escalation_reason=decision.escalation_reason.value,
                risk_categories=risk_result.get("risk_categories", [])
            )
            
            decision.assigned_agent = routing_decision.get("agent_id")
            decision.routing_metadata = routing_decision
            
            # Assign ownership
            self.ownership_manager.assign_to_human(
                thread_id=thread_id,
                tenant_id=tenant_id,
                assigned_human=routing_decision["agent_id"],
                escalation_reason=decision.escalation_reason.value,
                priority=decision.escalation_priority.value,
                sla_minutes=SLAManager.SLA_PRIORITIES.get(decision.escalation_priority.value, 60)
            )
            
            # Create SLA
            sla_priority = self.sla_manager.get_priority_for_risk(decision.risk_level.value)
            sla_data = self.sla_manager.create_sla(
                ticket_id=ticket_id,
                thread_id=thread_id,
                tenant_id=tenant_id,
                priority=sla_priority
            )
            decision.sla_deadline = sla_data.get("sla_deadline")
            
            # Enqueue for human review
            self.queue_manager.enqueue(
                tenant_id=tenant_id,
                thread_id=thread_id,
                ticket_id=ticket_id,
                priority=decision.escalation_priority.value,
                escalation_reason=decision.escalation_reason.value,
                context={
                    "query": query,
                    "retrieval_context": retrieval_context,
                    "llm_response": llm_response,
                    "confidence_result": confidence_result.__dict__,
                    "risk_result": risk_result
                },
                metadata=metadata
            )
            
            # Record metrics
            self.metrics.record_escalation(
                tenant_id=tenant_id,
                priority=decision.escalation_priority.value,
                escalation_reason=decision.escalation_reason.value,
                queue_time_ms=0  # Just enqueued
            )
            
            logger.info(f"Escalated thread {thread_id} to {routing_decision['agent_id']}")
        
        # Step 5: Audit logging
        self.audit_logger.log_handoff_decision(
            tenant_id=tenant_id,
            thread_id=thread_id,
            decision=decision.decision,
            confidence_score=confidence_result.final_confidence,
            risk_level=decision.risk_level.value,
            escalation_reason=decision.escalation_reason.value,
            confidence_signals=confidence_result.signal_scores,
            risk_factors=risk_result,
            retrieved_chunks=retrieval_context.get("chunks", []),
            hallucination_violations=hallucination_check.get("violations", []) if hallucination_check else [],
            routing_decision=decision.routing_metadata,
            ticket_id=decision.ticket_id,
            metadata=metadata
        )
        
        # Record decision metrics
        self.metrics.record_handoff_decision(
            tenant_id=tenant_id,
            decision=decision.decision,
            confidence_score=confidence_result.final_confidence,
            risk_level=decision.risk_level.value,
            latency_ms=latency_ms
        )
        
        return decision
    
    def _make_decision(
        self,
        confidence_result,
        risk_result: Dict,
        query: str,
        retrieval_context: Dict
    ) -> HandoffDecision:
        """Core decision logic"""
        
        confidence = confidence_result.final_confidence
        risk_level = risk_result["risk_level"]
        risk_categories = risk_result["risk_categories"]
        
        # Critical risk always escalates
        if risk_level == "critical":
            return HandoffDecision(
                should_escalate=True,
                decision="critical_risk",
                confidence_score=confidence,
                risk_level=RiskLevel.CRITICAL,
                escalation_reason=self._map_risk_to_reason(risk_categories),
                escalation_priority=EscalationPriority.CRITICAL,
                blocking=True,
                risk_categories=risk_categories
            )
        
        # High risk escalates
        if risk_level == "high":
            return HandoffDecision(
                should_escalate=True,
                decision="high_risk",
                confidence_score=confidence,
                risk_level=RiskLevel.HIGH,
                escalation_reason=self._map_risk_to_reason(risk_categories),
                escalation_priority=EscalationPriority.HIGH,
                blocking=True,
                risk_categories=risk_categories
            )
        
        # Low confidence escalates
        if confidence < 0.6:
            return HandoffDecision(
                should_escalate=True,
                decision="low_confidence",
                confidence_score=confidence,
                risk_level=RiskLevel.MEDIUM,
                escalation_reason=EscalationReason.LOW_CONFIDENCE,
                escalation_priority=EscalationPriority.MEDIUM,
                blocking=False,
                risk_categories=risk_categories
            )
        
        # Medium confidence with medium risk - escalate cautiously
        if confidence < 0.75 and risk_level == "medium":
            return HandoffDecision(
                should_escalate=True,
                decision="medium_confidence_with_risk",
                confidence_score=confidence,
                risk_level=RiskLevel.MEDIUM,
                escalation_reason=EscalationReason.UNCERTAIN,
                escalation_priority=EscalationPriority.LOW,
                blocking=False,
                risk_categories=risk_categories
            )
        
        # AI can handle
        return HandoffDecision(
            should_escalate=False,
            decision="ai_handled",
            confidence_score=confidence,
            risk_level=RiskLevel.LOW,
            escalation_reason=EscalationReason.NONE,
            escalation_priority=EscalationPriority.LOW,
            blocking=False,
            risk_categories=risk_categories
        )
    
    def _map_risk_to_reason(self, risk_categories: list) -> EscalationReason:
        """Map risk categories to escalation reason"""
        if "angry_customer" in risk_categories:
            return EscalationReason.ANGRY_CUSTOMER
        if "refund_risk" in risk_categories:
            return EscalationReason.REFUND_REQUEST
        if "legal_risk" in risk_categories:
            return EscalationReason.LEGAL_ISSUE
        if "hallucination_risk" in risk_categories:
            return EscalationReason.HALLUCINATION_DETECTED
        if "unsupported_claim" in risk_categories:
            return EscalationReason.UNSUPPORTED_CLAIM
        
        return EscalationReason.UNCERTAIN
