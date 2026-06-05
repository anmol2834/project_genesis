# CORE ORCHESTRATOR INTEGRATION GUIDE

## Overview

This document describes how to integrate the handoff layer into the main orchestrator.

## Integration Steps

### 1. Import Handoff Orchestrator

```python
# app/orchestration/orchestrator.py

from app.handoff import HandoffOrchestrator, HandoffDecision
```

### 2. Initialize in Orchestrator __init__

```python
class AIOrchestrator:
    def __init__(
        self,
        redis_client,
        postgres_conn,
        embedding_engine,
        retrieval_engine,
        llm_client,
        # ... other components
    ):
        # Existing components
        self.redis = redis_client
        self.pg_conn = postgres_conn
        self.embedding_engine = embedding_engine
        self.retrieval_engine = retrieval_engine
        self.llm_client = llm_client
        # ...
        
        # Initialize handoff orchestrator
        self.handoff = HandoffOrchestrator(
            redis_client=redis_client,
            postgres_conn=postgres_conn,
            confidence_weights=None  # Use defaults, or tenant-specific
        )
```

### 3. Integrate in Process Query Flow

```python
async def process_query(
    self,
    tenant_id: str,
    thread_id: str,
    query: str,
    conversation_history: list,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Main query processing with integrated handoff evaluation
    """
    
    # Step 1: Intent classification
    intent_result = await self.intent_classifier.classify(query)
    
    # Step 2: Memory retrieval
    memory_context = await self.memory_engine.get_context(thread_id)
    
    # Step 3: Retrieval
    retrieval_result = await self.retrieval_engine.retrieve(
        query=query,
        tenant_id=tenant_id,
        intent=intent_result,
        memory_context=memory_context
    )
    
    # Step 4: LLM generation
    llm_response = await self.llm_client.generate(
        query=query,
        context=retrieval_result["chunks"],
        conversation_history=conversation_history
    )
    
    # Step 5: Hallucination guard
    hallucination_result = await self.hallucination_guard.check(
        response=llm_response,
        context=retrieval_result["chunks"]
    )
    
    # Step 6: HANDOFF EVALUATION
    handoff_decision = self.handoff.evaluate_handoff(
        tenant_id=tenant_id,
        thread_id=thread_id,
        query=query,
        retrieval_context=retrieval_result,
        llm_response=llm_response,
        conversation_history=conversation_history,
        intent_result=intent_result,
        memory_context=memory_context,
        hallucination_check=hallucination_result,
        metadata=metadata
    )
    
    # Step 7: Handle handoff decision
    if handoff_decision.should_escalate:
        logger.info(f"Escalating thread {thread_id}: {handoff_decision.escalation_reason.value}")
        
        if handoff_decision.blocking:
            # Blocking escalation: AI must NOT respond
            # Return only fallback message
            return {
                "response": handoff_decision.fallback_message,
                "escalated": True,
                "blocking": True,
                "ticket_id": handoff_decision.ticket_id,
                "assigned_agent": handoff_decision.assigned_agent,
                "sla_deadline": handoff_decision.sla_deadline,
                "confidence": handoff_decision.confidence_score,
                "risk_level": handoff_decision.risk_level.value
            }
        else:
            # Non-blocking escalation: Send AI response + escalation notice
            return {
                "response": llm_response,
                "escalated": True,
                "blocking": False,
                "ticket_id": handoff_decision.ticket_id,
                "escalation_notice": handoff_decision.fallback_message,
                "assigned_agent": handoff_decision.assigned_agent,
                "confidence": handoff_decision.confidence_score
            }
    
    # Step 8: Normal AI response
    return {
        "response": llm_response,
        "escalated": False,
        "confidence": handoff_decision.confidence_score
    }
```

### 4. Pre-check Before Processing

Add this at the START of process_query to prevent AI from responding when human owns conversation:

```python
async def process_query(self, tenant_id, thread_id, query, ...):
    # CRITICAL: Check if human owns conversation FIRST
    if self.handoff.ownership_manager.is_human_owned(thread_id):
        logger.info(f"Thread {thread_id} is human-owned, blocking AI processing")
        return {
            "response": "This conversation is currently being handled by our team.",
            "escalated": True,
            "blocking": True,
            "human_owned": True
        }
    
    # Continue with normal processing...
```

### 5. Event Publishing to Email Service

When escalation happens, publish event to email-service:

```python
# After handoff_decision.should_escalate == True

if handoff_decision.should_escalate:
    # Publish escalation event to email-service
    escalation_event = {
        "event_type": "escalation_required",
        "thread_id": thread_id,
        "tenant_id": tenant_id,
        "ticket_id": handoff_decision.ticket_id,
        "fallback_message": handoff_decision.fallback_message,
        "assigned_agent": handoff_decision.assigned_agent,
        "priority": handoff_decision.escalation_priority.value,
        "escalation_reason": handoff_decision.escalation_reason.value,
        "risk_level": handoff_decision.risk_level.value,
        "sla_deadline": handoff_decision.sla_deadline,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await self.event_publisher.publish(
        topic="email.escalations",
        key=thread_id,
        value=escalation_event
    )
```

## Configuration

### Environment Variables

Add to `/server/.env`:

```bash
# Handoff Configuration
HANDOFF_CONFIDENCE_THRESHOLD=0.7
HANDOFF_HIGH_RISK_THRESHOLD=0.6
HANDOFF_ENABLE_AUTO_REENTRY=true

# SLA Defaults (minutes)
HANDOFF_SLA_CRITICAL=15
HANDOFF_SLA_HIGH=30
HANDOFF_SLA_MEDIUM=60
HANDOFF_SLA_LOW=240
```

### Load Configuration

```python
# app/core/config.py

class Settings(BaseSettings):
    # ... existing settings
    
    # Handoff settings
    handoff_confidence_threshold: float = 0.7
    handoff_high_risk_threshold: float = 0.6
    handoff_enable_auto_reentry: bool = True
    
    handoff_sla_critical: int = 15
    handoff_sla_high: int = 30
    handoff_sla_medium: int = 60
    handoff_sla_low: int = 240
```

## Testing Integration

### Unit Test

```python
# app/tests/test_handoff_integration.py

def test_handoff_blocks_ai_when_human_owns():
    """Test that AI is blocked when human owns conversation"""
    
    # Setup
    orchestrator = AIOrchestrator(...)
    
    # Simulate human ownership
    orchestrator.handoff.ownership_manager.assign_to_human(
        thread_id="test_thread",
        tenant_id="tenant_123",
        assigned_human="agent_001",
        escalation_reason="test",
        priority="high"
    )
    
    # Process query
    result = await orchestrator.process_query(
        tenant_id="tenant_123",
        thread_id="test_thread",
        query="test query",
        conversation_history=[]
    )
    
    # Assert AI was blocked
    assert result["escalated"] == True
    assert result["blocking"] == True
    assert result["human_owned"] == True

def test_low_confidence_escalates():
    """Test that low confidence triggers escalation"""
    
    orchestrator = AIOrchestrator(...)
    
    # Mock low confidence retrieval
    with patch.object(orchestrator.retrieval_engine, 'retrieve', return_value={
        "chunks": [],
        "confidence": 0.3  # Low confidence
    }):
        result = await orchestrator.process_query(
            tenant_id="tenant_123",
            thread_id="test_thread",
            query="complex question",
            conversation_history=[]
        )
    
    assert result["escalated"] == True
    assert result.get("ticket_id") is not None
```

## Monitoring Integration

### Add Metrics Endpoint

```python
# app/api/handoff.py

from fastapi import APIRouter, Depends
from app.handoff import HandoffOrchestrator

router = APIRouter(prefix="/handoff", tags=["handoff"])

@router.get("/metrics/{tenant_id}")
async def get_handoff_metrics(
    tenant_id: str,
    handoff: HandoffOrchestrator = Depends(get_handoff_orchestrator)
):
    """Get handoff system metrics for tenant"""
    metrics = handoff.metrics.get_dashboard_metrics(tenant_id)
    return metrics

@router.get("/queue/{tenant_id}/depth")
async def get_queue_depth(
    tenant_id: str,
    priority: Optional[str] = None,
    handoff: HandoffOrchestrator = Depends(get_handoff_orchestrator)
):
    """Get current queue depth"""
    depth = handoff.queue_manager.get_queue_depth(tenant_id, priority)
    return {"tenant_id": tenant_id, "queue_depth": depth}

@router.get("/audit/{thread_id}")
async def get_audit_trail(
    thread_id: str,
    handoff: HandoffOrchestrator = Depends(get_handoff_orchestrator)
):
    """Get complete audit trail for thread"""
    trail = handoff.audit_logger.get_thread_audit_trail(thread_id)
    return {"thread_id": thread_id, "audit_trail": trail}
```

## Human Agent Interface (Future)

### API for Human Agents

```python
@router.get("/queue/{tenant_id}/next")
async def get_next_ticket(
    tenant_id: str,
    agent_id: str,
    handoff: HandoffOrchestrator = Depends(get_handoff_orchestrator)
):
    """Human agent pulls next ticket from queue"""
    
    ticket = handoff.queue_manager.dequeue(
        tenant_id=tenant_id,
        priorities=["critical", "high", "medium", "low"]
    )
    
    if ticket:
        return ticket
    else:
        return {"message": "No tickets in queue"}

@router.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: str,
    resolution_data: dict,
    handoff: HandoffOrchestrator = Depends(get_handoff_orchestrator)
):
    """Human agent resolves ticket"""
    
    thread_id = resolution_data["thread_id"]
    tenant_id = resolution_data["tenant_id"]
    resolution_summary = resolution_data["summary"]
    resolution_type = resolution_data["type"]  # e.g., "issue_resolved"
    
    # Release ownership back to AI
    handoff.ownership_manager.release_to_ai(
        thread_id=thread_id,
        resolution_summary=resolution_summary
    )
    
    # Evaluate AI reentry
    eligibility = handoff.reentry_manager.evaluate_reentry_eligibility(
        thread_id=thread_id,
        tenant_id=tenant_id,
        resolution_summary=resolution_summary,
        resolution_type=resolution_type
    )
    
    # Mark ticket complete
    handoff.queue_manager.complete_processing(ticket_id)
    
    # Resolve SLA
    handoff.sla_manager.resolve_sla(ticket_id)
    
    # Audit log
    handoff.audit_logger.log_ai_reentry(
        tenant_id=tenant_id,
        thread_id=thread_id,
        resolution_summary=resolution_summary,
        reentry_decision="eligible" if eligibility["eligible"] else "blocked"
    )
    
    return {
        "status": "resolved",
        "ticket_id": ticket_id,
        "ai_reentry_eligible": eligibility["eligible"]
    }
```

## Performance Monitoring

### Add Prometheus Metrics (Optional)

```python
from prometheus_client import Counter, Histogram, Gauge

# Handoff metrics
handoff_decisions_total = Counter(
    'handoff_decisions_total',
    'Total handoff decisions',
    ['tenant_id', 'decision']
)

handoff_latency = Histogram(
    'handoff_latency_seconds',
    'Handoff decision latency',
    ['tenant_id']
)

queue_depth = Gauge(
    'handoff_queue_depth',
    'Current queue depth',
    ['tenant_id', 'priority']
)

# In orchestrator
with handoff_latency.labels(tenant_id=tenant_id).time():
    handoff_decision = self.handoff.evaluate_handoff(...)

handoff_decisions_total.labels(
    tenant_id=tenant_id,
    decision=handoff_decision.decision
).inc()
```

## Summary

Integration checklist:

✅ Import HandoffOrchestrator in orchestrator  
✅ Initialize handoff in __init__  
✅ Add ownership check at start of process_query  
✅ Call evaluate_handoff after LLM generation  
✅ Handle blocking vs non-blocking escalations  
✅ Publish escalation events to email-service  
✅ Add configuration to .env and Settings  
✅ Create handoff API endpoints  
✅ Add monitoring and metrics  
✅ Write integration tests  

The handoff layer is now fully integrated and ready for production use.
