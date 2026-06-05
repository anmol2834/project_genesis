"""
Audit Logger - Complete traceability for all handoff decisions
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from redis import Redis
import psycopg2
from psycopg2.extras import Json

logger = logging.getLogger(__name__)

class HandoffAuditLogger:
    """Logs all handoff decisions for compliance, debugging, and learning"""
    
    def __init__(self, redis_client: Redis, postgres_conn):
        self.redis = redis_client
        self.pg_conn = postgres_conn
        self.audit_prefix = "handoff:audit:"
        self._ensure_audit_table()
    
    def _ensure_audit_table(self):
        """Create audit table if not exists"""
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS handoff_audit (
                        id BIGSERIAL PRIMARY KEY,
                        tenant_id VARCHAR(255) NOT NULL,
                        thread_id VARCHAR(255) NOT NULL,
                        ticket_id VARCHAR(255),
                        event_type VARCHAR(50) NOT NULL,
                        decision VARCHAR(50) NOT NULL,
                        confidence_score DECIMAL(5,4),
                        risk_level VARCHAR(20),
                        escalation_reason TEXT,
                        confidence_signals JSONB,
                        risk_factors JSONB,
                        retrieved_chunks JSONB,
                        hallucination_violations JSONB,
                        routing_decision JSONB,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT NOW(),
                        INDEX idx_tenant_thread (tenant_id, thread_id),
                        INDEX idx_created_at (created_at),
                        INDEX idx_decision (decision)
                    );
                """)
                self.pg_conn.commit()
        except Exception as e:
            logger.error(f"Failed to create audit table: {e}")
    
    def log_handoff_decision(
        self,
        tenant_id: str,
        thread_id: str,
        decision: str,
        confidence_score: float,
        risk_level: str,
        escalation_reason: str,
        confidence_signals: Dict[str, Any],
        risk_factors: Dict[str, Any],
        retrieved_chunks: Optional[list] = None,
        hallucination_violations: Optional[list] = None,
        routing_decision: Optional[Dict] = None,
        ticket_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Log complete handoff decision with all signals"""
        
        audit_record = {
            "tenant_id": tenant_id,
            "thread_id": thread_id,
            "ticket_id": ticket_id,
            "event_type": "handoff_decision",
            "decision": decision,
            "confidence_score": confidence_score,
            "risk_level": risk_level,
            "escalation_reason": escalation_reason,
            "confidence_signals": confidence_signals,
            "risk_factors": risk_factors,
            "retrieved_chunks": retrieved_chunks or [],
            "hallucination_violations": hallucination_violations or [],
            "routing_decision": routing_decision or {},
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Store in Redis for fast access (24h TTL)
            redis_key = f"{self.audit_prefix}{thread_id}:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            self.redis.setex(redis_key, 86400, json.dumps(audit_record))
            
            # Store in PostgreSQL for long-term audit
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO handoff_audit (
                        tenant_id, thread_id, ticket_id, event_type, decision,
                        confidence_score, risk_level, escalation_reason,
                        confidence_signals, risk_factors, retrieved_chunks,
                        hallucination_violations, routing_decision, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    tenant_id, thread_id, ticket_id, "handoff_decision", decision,
                    confidence_score, risk_level, escalation_reason,
                    Json(confidence_signals), Json(risk_factors), Json(retrieved_chunks or []),
                    Json(hallucination_violations or []), Json(routing_decision or {}), Json(metadata or {})
                ))
                self.pg_conn.commit()
            
            logger.info(f"Logged handoff decision for {thread_id}: {decision}")
            return True
        except Exception as e:
            logger.error(f"Failed to log handoff decision: {e}")
            return False
    
    def log_human_assignment(
        self,
        tenant_id: str,
        thread_id: str,
        ticket_id: str,
        assigned_human: str,
        priority: str,
        sla_deadline: str
    ) -> bool:
        """Log human assignment event"""
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO handoff_audit (
                        tenant_id, thread_id, ticket_id, event_type, decision, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    tenant_id, thread_id, ticket_id, "human_assignment", "assigned",
                    Json({
                        "assigned_human": assigned_human,
                        "priority": priority,
                        "sla_deadline": sla_deadline
                    })
                ))
                self.pg_conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to log human assignment: {e}")
            return False
    
    def log_ai_reentry(
        self,
        tenant_id: str,
        thread_id: str,
        resolution_summary: str,
        reentry_decision: str
    ) -> bool:
        """Log AI re-entry after human resolution"""
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO handoff_audit (
                        tenant_id, thread_id, event_type, decision, metadata
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    tenant_id, thread_id, "ai_reentry", reentry_decision,
                    Json({
                        "resolution_summary": resolution_summary,
                        "reentry_time": datetime.utcnow().isoformat()
                    })
                ))
                self.pg_conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to log AI reentry: {e}")
            return False
    
    def get_thread_audit_trail(self, thread_id: str, limit: int = 50) -> list:
        """Retrieve complete audit trail for a thread"""
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM handoff_audit
                    WHERE thread_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (thread_id, limit))
                
                columns = [desc[0] for desc in cursor.description]
                results = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            return []
