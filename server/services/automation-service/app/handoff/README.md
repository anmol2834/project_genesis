# Handoff Layer - Enterprise AI Decision & Escalation System

## Quick Start

```python
from app.handoff import HandoffOrchestrator

# Initialize
handoff = HandoffOrchestrator(
    redis_client=redis_client,
    postgres_conn=postgres_conn
)

# Evaluate handoff
decision = handoff.evaluate_handoff(
    tenant_id="tenant_123",
    thread_id="thread_456",
    query="customer query",
    retrieval_context=retrieval_result,
    llm_response=llm_response,
    conversation_history=history,
    intent_result=intent,
    memory_context=memory,
    hallucination_check=hallucination_result,
    metadata={"language": "en"}
)

if decision.should_escalate:
    if decision.blocking:
        # Send fallback message only
        return decision.fallback_message
    else:
        # Send AI response + escalation notice
        return llm_response
```

## What is the Handoff Layer?

The handoff layer is the **Enterprise AI Decision & Escalation System** for automation-service. It intelligently decides when to escalate conversations from AI to human agents based on:

- **Confidence signals**: Multi-source confidence fusion
- **Risk detection**: Dangerous scenarios (refunds, legal, angry customers)
- **Hallucination prevention**: Blocks unsafe AI responses
- **Business policy**: Tenant-configurable escalation rules

## Why Do We Need It?

Without intelligent handoff:
- ❌ AI sends low-confidence responses (customer frustration)
- ❌ AI hallucinates unsafe information (legal/financial risk)
- ❌ Angry customers get AI responses (escalation)
- ❌ Complex queries get inadequate answers (poor experience)
- ❌ No human oversight for critical situations

With handoff layer:
- ✅ AI knows when it doesn't know
- ✅ Dangerous queries escalate safely
- ✅ Human agents handle complex cases
- ✅ Seamless AI ↔ Human handoffs
- ✅ Complete audit trail for compliance
- ✅ Near-zero hallucination customer exposure

## Architecture

```
Query → Orchestrator → Handoff Evaluation → Decision
                            ↓
                    ┌───────┴────────┐
                    │                │
              Confidence          Risk
              Engine             Engine
                    │                │
                    └───────┬────────┘
                            ↓
                    Should Escalate?
                            │
                ┌───────────┴───────────┐
                │                       │
               YES                     NO
                │                       │
        Escalation Workflow      AI Responds
        (Routing, Queue,
         Ownership, SLA)
```

## Core Components

### 1. Confidence Engine
Fuses multiple signals into final confidence score:
- Retrieval quality (30%)
- LLM confidence (20%)
- Hallucination guard (15%)
- Reranker score (10%)
- Intent confidence (10%)
- Memory continuity (10%)
- Historical feedback (5%)

### 2. Risk Engine
Detects dangerous scenarios:
- Angry customer detection
- Refund/billing requests
- Legal/compliance queries
- Hallucination risk
- Unsupported claims
- Privacy concerns

### 3. Ownership Manager
Locks conversations when humans take over:
- Prevents AI from responding
- Tracks assigned human
- Manages ownership lifecycle
- Enables AI re-entry after resolution

### 4. SLA Manager
Tracks escalation timers:
- Critical: 15min
- High: 30min
- Medium: 60min
- Low: 240min
- Breach detection
- Overdue alerts

### 5. Queue Manager
Distributed-safe human review queue:
- FIFO + Priority
- Tenant isolation
- Deduplication
- Stale ticket recovery
- Crash-resistant

### 6. Routing Engine
Intelligent human assignment:
- Round-robin
- Least-loaded
- Skill-based
- Priority-based
- Future CRM integration

### 7. Fallback Response Generator
Professional escalation messages:
- Context-aware
- Multi-language
- Tone variants
- NO hardcoded business data

### 8. AI Re-entry Manager
Enables AI to resume after human:
- Reentry eligibility
- Resolution context injection
- Higher confidence thresholds
- Blocking for sensitive cases

### 9. Audit Logger
Complete traceability:
- All decisions logged
- Confidence signals tracked
- Risk factors recorded
- PostgreSQL long-term storage
- Redis hot cache

### 10. Metrics Collector
Real-time observability:
- Handoff rate
- Average latency
- SLA compliance
- Priority distribution
- Confidence trends

## File Structure

```
app/handoff/
├── __init__.py                      # Package exports
├── IMPLEMENTATION.md                # Detailed architecture doc
├── INTEGRATION_GUIDE.md             # How to integrate
├── README.md                        # This file
│
├── models/
│   └── __init__.py                  # Data models (HandoffDecision, etc.)
│
├── confidence_engine/
│   └── __init__.py                  # Multi-signal confidence fusion
│
├── risk_engine/
│   └── __init__.py                  # Risk detection
│
├── ownership/
│   ├── __init__.py
│   └── ownership_manager.py         # Human ownership locking
│
├── sla/
│   ├── __init__.py
│   └── sla_manager.py               # SLA tracking
│
├── queue_management/
│   ├── __init__.py
│   └── queue_manager.py             # Human review queue
│
├── routing/
│   ├── __init__.py
│   └── routing_engine.py            # Agent assignment
│
├── fallback_responses/
│   ├── __init__.py
│   └── response_generator.py        # Escalation messages
│
├── ai_reentry/
│   ├── __init__.py
│   └── reentry_manager.py           # AI resumption logic
│
├── audit/
│   ├── __init__.py
│   └── audit_logger.py              # Complete audit trail
│
├── metrics/
│   ├── __init__.py
│   └── metrics_collector.py         # Observability
│
└── services/
    ├── __init__.py
    ├── handoff_service.py
    └── handoff_orchestrator.py      # Main integration point
```

## Redis Keys

```
handoff:owner:{thread_id}                    # Ownership lock
handoff:sla:{ticket_id}                      # SLA tracker
handoff:overdue                              # Overdue sorted set
handoff:queue:{tenant_id}:{priority}         # Queue per priority
handoff:ticket:{ticket_id}                   # Ticket data
handoff:processing:{ticket_id}               # Processing lock
handoff:dedup:{thread_id}                    # Deduplication
handoff:reentry:{thread_id}                  # Reentry eligibility
handoff:resolution:{thread_id}               # Human summary
handoff:ai_blocked:{thread_id}               # AI blocked
handoff:metrics:*                            # Metrics data
handoff:audit:{thread_id}:{timestamp}        # Audit cache
```

## PostgreSQL Tables

```sql
-- Audit trail
handoff_audit (
    id, tenant_id, thread_id, ticket_id, event_type,
    decision, confidence_score, risk_level, escalation_reason,
    confidence_signals, risk_factors, retrieved_chunks,
    hallucination_violations, routing_decision, metadata, created_at
)

-- Human agents (future CRM sync)
handoff_agents (
    id, tenant_id, agent_id, agent_name, agent_email,
    skills, max_concurrent, is_available, priority_tier, created_at
)

-- Routing rules (tenant-customizable)
handoff_routing_rules (
    id, tenant_id, rule_name, conditions, routing_strategy,
    target_agents, priority, is_active, created_at
)
```

## Performance

| Component | Target Latency |
|-----------|---------------|
| Confidence Engine | <5ms |
| Risk Engine | <5ms |
| Ownership Check | <2ms |
| SLA Creation | <5ms |
| Queue Enqueue | <10ms |
| Routing | <15ms |
| Fallback Gen | <2ms |
| Audit Log | <20ms |
| **Total** | **<50ms** |

## Configuration

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

## Usage Example

### Check if Human Owns Thread

```python
if handoff.ownership_manager.is_human_owned(thread_id):
    return {"response": "This conversation is being handled by our team."}
```

### Evaluate Handoff

```python
decision = handoff.evaluate_handoff(
    tenant_id=tenant_id,
    thread_id=thread_id,
    query=query,
    retrieval_context=retrieval_result,
    llm_response=llm_response,
    conversation_history=history,
    intent_result=intent,
    memory_context=memory,
    hallucination_check=hallucination_result,
    metadata={"language": "en"}
)
```

### Handle Decision

```python
if decision.should_escalate:
    logger.info(f"Escalated: {decision.escalation_reason.value}")
    
    if decision.blocking:
        # AI must NOT respond
        return {
            "response": decision.fallback_message,
            "escalated": True,
            "ticket_id": decision.ticket_id
        }
    else:
        # AI responds + escalation notice
        return {
            "response": llm_response,
            "escalated": True,
            "ticket_id": decision.ticket_id,
            "notice": decision.fallback_message
        }
else:
    # Normal AI response
    return {"response": llm_response, "escalated": False}
```

### Get Metrics

```python
metrics = handoff.metrics.get_dashboard_metrics(tenant_id)
print(f"Handoff rate: {metrics['handoff_rate_24h']}")
print(f"SLA compliance: {metrics['sla_compliance_24h']}")
```

### Human Agent Workflow

```python
# Human pulls next ticket
ticket = handoff.queue_manager.dequeue(tenant_id, ["critical", "high", "medium", "low"])

# Human resolves issue
handoff.ownership_manager.release_to_ai(thread_id, resolution_summary="Issue resolved")
handoff.queue_manager.complete_processing(ticket_id)
handoff.sla_manager.resolve_sla(ticket_id)
```

## Testing

```bash
# Run tests
pytest app/handoff/tests/

# Test coverage
pytest app/handoff/tests/ --cov=app/handoff
```

## Monitoring Endpoints

```
GET /api/handoff/metrics/{tenant_id}           # Dashboard metrics
GET /api/handoff/queue/{tenant_id}/depth       # Queue depth
GET /api/handoff/audit/{thread_id}             # Audit trail
GET /api/handoff/queue/{tenant_id}/next        # Get next ticket
POST /api/handoff/tickets/{ticket_id}/resolve  # Resolve ticket
```

## Future Extensions

- [ ] CRM integration (Salesforce, Zendesk, Intercom)
- [ ] Multi-channel support (chat, SMS, voice)
- [ ] Advanced routing (time-of-day, language, expertise)
- [ ] Learning engine integration (auto-tune confidence weights)
- [ ] Customer sentiment analysis
- [ ] Proactive escalation prediction
- [ ] Human agent performance analytics

## Documentation

- [IMPLEMENTATION.md](./IMPLEMENTATION.md) - Complete architecture and implementation details
- [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) - Step-by-step integration instructions

## Summary

The handoff layer provides:

✅ **Intelligent escalation** - Multi-signal confidence + risk detection  
✅ **Human-AI orchestration** - Seamless handoffs with ownership management  
✅ **Production-ready** - Distributed, scalable, crash-resistant  
✅ **Observable** - Complete audit trail + real-time metrics  
✅ **Fast** - <50ms overhead  
✅ **Safe** - Prevents hallucinations from reaching customers  
✅ **Flexible** - Tenant-customizable rules  
✅ **Enterprise-grade** - Ready for millions of tenants  

This is NOT a prototype. This is production-ready enterprise architecture.
