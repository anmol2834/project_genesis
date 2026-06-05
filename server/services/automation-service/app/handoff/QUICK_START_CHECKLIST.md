# HANDOFF IMPLEMENTATION - QUICK START CHECKLIST

## 🎯 GOAL
Integrate the handoff layer into automation-service orchestrator for intelligent AI-to-human escalation.

---

## ✅ PHASE 1: REVIEW & UNDERSTAND (30 minutes)

- [ ] Read `app/handoff/README.md` (quick overview)
- [ ] Scan `app/handoff/ARCHITECTURE_VISUAL.md` (visual architecture)
- [ ] Review `app/handoff/HANDOFF_DELIVERY_SUMMARY.md` (what was delivered)
- [ ] Understand the flow: Query → Confidence/Risk → Decision → Escalation/AI Response

**Key Concepts:**
- HandoffOrchestrator = main integration point
- HandoffDecision = result object (should_escalate, blocking, fallback_message, etc.)
- Blocking escalation = AI MUST NOT respond
- Non-blocking escalation = AI responds + escalation notice

---

## ✅ PHASE 2: ENVIRONMENT SETUP (15 minutes)

### Step 1: Add Environment Variables

Edit `/server/.env`:

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

### Step 2: Verify Dependencies

All dependencies already exist in automation-service:
- ✅ Redis client
- ✅ PostgreSQL connection
- ✅ Python 3.10+
- ✅ No new packages required

### Step 3: Database Tables

PostgreSQL tables auto-create on first run:
- `handoff_audit` (audit trail)
- `handoff_agents` (human agents)
- `handoff_routing_rules` (routing logic)

**No manual SQL required.**

---

## ✅ PHASE 3: CODE INTEGRATION (45 minutes)

### Step 1: Import Handoff in Orchestrator

File: `app/orchestration/orchestrator.py`

```python
# Add import
from app.handoff import HandoffOrchestrator, HandoffDecision
```

### Step 2: Initialize in __init__

```python
class AIOrchestrator:
    def __init__(self, redis_client, postgres_conn, ...):
        # Existing components
        self.redis = redis_client
        self.pg_conn = postgres_conn
        # ... other components
        
        # NEW: Initialize handoff
        self.handoff = HandoffOrchestrator(
            redis_client=redis_client,
            postgres_conn=postgres_conn
        )
```

### Step 3: Add Ownership Check (CRITICAL)

Add this at the **START** of `process_query()`:

```python
async def process_query(self, tenant_id, thread_id, query, conversation_history, metadata=None):
    # CRITICAL: Check if human owns conversation FIRST
    if self.handoff.ownership_manager.is_human_owned(thread_id):
        logger.info(f"Thread {thread_id} is human-owned, blocking AI")
        return {
            "response": "This conversation is currently being handled by our team.",
            "escalated": True,
            "blocking": True,
            "human_owned": True
        }
    
    # Continue with normal processing...
```

### Step 4: Add Handoff Evaluation

Add this **AFTER** LLM generation and hallucination check:

```python
    # ... existing code: intent, memory, retrieval, LLM, hallucination ...
    
    # NEW: Handoff evaluation
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
    
    # Handle handoff decision
    if handoff_decision.should_escalate:
        logger.info(
            f"Escalated thread {thread_id}: {handoff_decision.escalation_reason.value}",
            extra={
                "ticket_id": handoff_decision.ticket_id,
                "confidence": handoff_decision.confidence_score,
                "risk_level": handoff_decision.risk_level.value
            }
        )
        
        if handoff_decision.blocking:
            # Blocking: AI must NOT respond
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
            # Non-blocking: Send AI response + escalation notice
            return {
                "response": llm_response,
                "escalated": True,
                "blocking": False,
                "ticket_id": handoff_decision.ticket_id,
                "escalation_notice": handoff_decision.fallback_message,
                "assigned_agent": handoff_decision.assigned_agent,
                "confidence": handoff_decision.confidence_score
            }
    
    # Normal AI response
    return {
        "response": llm_response,
        "escalated": False,
        "confidence": handoff_decision.confidence_score
    }
```

### Step 5: Event Publishing to Email Service (Optional)

If you want email-service to be notified of escalations:

```python
    if handoff_decision.should_escalate:
        # Publish escalation event
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

---

## ✅ PHASE 4: TESTING (30 minutes)

### Test 1: Low Confidence Escalation

```python
# Mock low retrieval confidence
# Expected: should_escalate=True, reason=LOW_CONFIDENCE

result = await orchestrator.process_query(
    tenant_id="test_tenant",
    thread_id="test_thread_1",
    query="What is your refund policy for defective products?",
    conversation_history=[]
)

assert result["escalated"] == True
assert "ticket_id" in result
```

### Test 2: High Risk Escalation (Angry Customer)

```python
# Query with angry tone
# Expected: should_escalate=True, reason=ANGRY_CUSTOMER, risk_level=HIGH

result = await orchestrator.process_query(
    tenant_id="test_tenant",
    thread_id="test_thread_2",
    query="This is unacceptable! I demand a full refund immediately!",
    conversation_history=[]
)

assert result["escalated"] == True
assert result.get("risk_level") in ["high", "critical"]
```

### Test 3: Human Ownership Blocking

```python
# Simulate human ownership
orchestrator.handoff.ownership_manager.assign_to_human(
    thread_id="test_thread_3",
    tenant_id="test_tenant",
    assigned_human="agent_001",
    escalation_reason="test",
    priority="high"
)

# Try to process query
result = await orchestrator.process_query(
    tenant_id="test_tenant",
    thread_id="test_thread_3",
    query="follow-up question",
    conversation_history=[]
)

assert result["blocking"] == True
assert result["human_owned"] == True
```

### Test 4: Normal AI Response (High Confidence)

```python
# Mock high confidence retrieval
# Expected: should_escalate=False

result = await orchestrator.process_query(
    tenant_id="test_tenant",
    thread_id="test_thread_4",
    query="What are your business hours?",
    conversation_history=[]
)

assert result["escalated"] == False
assert "response" in result
```

---

## ✅ PHASE 5: MONITORING SETUP (20 minutes)

### Step 1: Add API Endpoints

File: `app/api/handoff.py` (create new file)

```python
from fastapi import APIRouter, Depends
from app.handoff import HandoffOrchestrator

router = APIRouter(prefix="/handoff", tags=["handoff"])

@router.get("/metrics/{tenant_id}")
async def get_handoff_metrics(tenant_id: str):
    """Get handoff system metrics"""
    # Get handoff orchestrator from dependency injection
    handoff = ...  # Your DI logic
    metrics = handoff.metrics.get_dashboard_metrics(tenant_id)
    return metrics

@router.get("/queue/{tenant_id}/depth")
async def get_queue_depth(tenant_id: str, priority: str = None):
    """Get current queue depth"""
    handoff = ...
    depth = handoff.queue_manager.get_queue_depth(tenant_id, priority)
    return {"tenant_id": tenant_id, "queue_depth": depth}

@router.get("/audit/{thread_id}")
async def get_audit_trail(thread_id: str):
    """Get complete audit trail for thread"""
    handoff = ...
    trail = handoff.audit_logger.get_thread_audit_trail(thread_id)
    return {"thread_id": thread_id, "audit_trail": trail}
```

### Step 2: Configure Logging

Ensure structured logging is enabled:

```python
import logging
import structlog

logger = structlog.get_logger(__name__)

# Logs will automatically include:
# - tenant_id
# - thread_id
# - ticket_id
# - confidence
# - risk_level
# - escalation_reason
```

### Step 3: Set Up Alerts

Configure alerts for:
- **SLA breaches**: `handoff_sla_breach_total > 0`
- **High queue depth**: `handoff_queue_depth > 100`
- **High handoff rate**: `handoff_rate > 0.25` (>25% escalations)
- **Low SLA compliance**: `handoff_sla_compliance < 0.90` (<90%)

---

## ✅ PHASE 6: DEPLOYMENT (30 minutes)

### Pre-Deployment Checklist

- [ ] Environment variables set in production `.env`
- [ ] Redis persistence enabled
- [ ] PostgreSQL connection verified
- [ ] Integration tests passed
- [ ] Performance tests passed (<50ms handoff overhead)
- [ ] Monitoring endpoints accessible
- [ ] Alerting configured

### Deployment Steps

1. **Deploy to Staging**
   ```bash
   # Deploy automation-service with handoff integration
   docker-compose up -d automation-service
   ```

2. **Verify Tables Created**
   ```sql
   SELECT * FROM handoff_audit LIMIT 1;
   SELECT * FROM handoff_agents LIMIT 1;
   SELECT * FROM handoff_routing_rules LIMIT 1;
   ```

3. **Test End-to-End**
   - Send test query with low confidence → Should escalate
   - Check Redis keys: `redis-cli KEYS "handoff:*"`
   - Check PostgreSQL audit: `SELECT * FROM handoff_audit;`
   - Check metrics endpoint: `GET /api/handoff/metrics/{tenant_id}`

4. **Monitor Initial Performance**
   - Handoff latency: Should be <50ms p99
   - Handoff rate: Typically 10-20% for first deployment
   - SLA compliance: Should be >95%

5. **Deploy to Production**
   - Same steps as staging
   - Monitor closely for first 24 hours
   - Adjust confidence thresholds per tenant if needed

---

## ✅ PHASE 7: POST-DEPLOYMENT (Ongoing)

### Week 1: Monitor & Tune

- [ ] Monitor handoff rate per tenant
- [ ] Check SLA compliance
- [ ] Review audit trail for false escalations
- [ ] Adjust confidence thresholds if needed
- [ ] Verify queue depth stays manageable

### Week 2: Tenant Customization

- [ ] Create routing rules for key tenants
- [ ] Register human agents in `handoff_agents` table
- [ ] Customize fallback messages per tenant
- [ ] Configure tenant-specific SLA timers

### Month 1: Optimization

- [ ] Analyze confidence signal weights
- [ ] Tune risk detection rules
- [ ] Implement custom routing strategies
- [ ] Add tenant-specific escalation policies

---

## 🚨 TROUBLESHOOTING

### Issue: High Handoff Rate (>30%)

**Cause**: Confidence threshold too strict  
**Fix**: Lower `HANDOFF_CONFIDENCE_THRESHOLD` from 0.7 to 0.6

### Issue: Handoff Latency >100ms

**Cause**: PostgreSQL routing query slow  
**Fix**: Add index on `handoff_routing_rules(tenant_id, is_active)`

### Issue: Queue Depth Growing

**Cause**: No human agents consuming queue  
**Fix**: 
1. Check agent availability: `SELECT * FROM handoff_agents WHERE is_available=true;`
2. Register agents if missing
3. Implement human agent interface (see INTEGRATION_GUIDE.md)

### Issue: SLA Breaches

**Cause**: SLA timers too aggressive  
**Fix**: Increase SLA timers in `.env`:
```bash
HANDOFF_SLA_HIGH=60  # Increase from 30 to 60
```

### Issue: Redis Connection Errors

**Cause**: Redis unavailable  
**Fix**: 
1. System gracefully degrades (allows AI responses)
2. Check Redis connection
3. Alert fires automatically

---

## 📊 SUCCESS METRICS

After 1 week, you should see:

- ✅ **Handoff rate**: 10-20% (varies by business)
- ✅ **SLA compliance**: >95%
- ✅ **Average latency**: <50ms
- ✅ **False escalations**: <5%
- ✅ **Zero hallucination incidents**: (hallucinations blocked before reaching customers)

---

## 📚 REFERENCE DOCUMENTATION

- **Quick Start**: This file
- **Architecture**: `app/handoff/ARCHITECTURE_VISUAL.md`
- **Complete Details**: `app/handoff/IMPLEMENTATION.md`
- **Integration Guide**: `app/handoff/INTEGRATION_GUIDE.md`
- **Delivery Summary**: `app/handoff/HANDOFF_DELIVERY_SUMMARY.md`
- **README**: `app/handoff/README.md`

---

## 🎓 TRAINING RESOURCES

### For Developers
1. Read this checklist (30 min)
2. Review code in `app/handoff/services/handoff_orchestrator.py` (20 min)
3. Read INTEGRATION_GUIDE.md (30 min)

### For DevOps
1. Environment setup section (15 min)
2. Monitoring setup section (20 min)
3. Deployment section (30 min)

### For Product Managers
1. Read HANDOFF_DELIVERY_SUMMARY.md (20 min)
2. Review success metrics (10 min)

---

## ✅ FINAL CHECKLIST

Before marking as COMPLETE:

- [ ] Environment variables added to `.env`
- [ ] Handoff imported in orchestrator
- [ ] Ownership check added at start of process_query
- [ ] Handoff evaluation added after LLM generation
- [ ] Decision handling implemented
- [ ] Integration tests written and passing
- [ ] API endpoints created
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] Deployed to staging
- [ ] End-to-end tests passed
- [ ] Deployed to production
- [ ] Team trained on handoff system
- [ ] Documentation reviewed

---

## 🎉 CONGRATULATIONS!

Once all checklist items are complete, the handoff layer is fully integrated and operational.

**Status**: ✅ READY FOR INTELLIGENT AI-TO-HUMAN ESCALATION

---

**Total Time Estimate**: 3-4 hours (including testing and deployment)

**Impact**: Near-zero hallucination customer exposure + better handling of complex queries

**Next Steps**: Monitor metrics, tune thresholds, customize per tenant
