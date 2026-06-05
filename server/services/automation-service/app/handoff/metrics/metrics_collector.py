"""
Handoff Metrics Collector - Complete observability for escalation system
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from redis import Redis
import json

logger = logging.getLogger(__name__)

class HandoffMetrics:
    """Collects and aggregates handoff system metrics"""
    
    def __init__(self, redis_client: Redis, postgres_conn):
        self.redis = redis_client
        self.pg_conn = postgres_conn
        self.metrics_prefix = "handoff:metrics:"
    
    def record_handoff_decision(
        self,
        tenant_id: str,
        decision: str,
        confidence_score: float,
        risk_level: str,
        latency_ms: float
    ):
        """Record handoff decision metrics"""
        try:
            # Daily counters
            date_key = datetime.utcnow().strftime("%Y%m%d")
            
            # Total decisions
            self.redis.hincrby(f"{self.metrics_prefix}decisions:{date_key}", tenant_id, 1)
            
            # Decisions by type
            decision_key = f"{self.metrics_prefix}decisions:{date_key}:{decision}"
            self.redis.hincrby(decision_key, tenant_id, 1)
            
            # Confidence score histogram (bucketed)
            confidence_bucket = self._bucket_confidence(confidence_score)
            conf_key = f"{self.metrics_prefix}confidence:{date_key}:{confidence_bucket}"
            self.redis.hincrby(conf_key, tenant_id, 1)
            
            # Risk level distribution
            risk_key = f"{self.metrics_prefix}risk:{date_key}:{risk_level}"
            self.redis.hincrby(risk_key, tenant_id, 1)
            
            # Latency tracking (running average)
            latency_key = f"{self.metrics_prefix}latency:{tenant_id}"
            self.redis.lpush(latency_key, latency_ms)
            self.redis.ltrim(latency_key, 0, 999)  # Keep last 1000 samples
            
            # Set expiry on daily keys (7 days)
            self.redis.expire(f"{self.metrics_prefix}decisions:{date_key}", 604800)
            
        except Exception as e:
            logger.error(f"Failed to record handoff metrics: {e}")
    
    def record_escalation(
        self,
        tenant_id: str,
        priority: str,
        escalation_reason: str,
        queue_time_ms: float
    ):
        """Record escalation metrics"""
        try:
            date_key = datetime.utcnow().strftime("%Y%m%d")
            
            # Total escalations
            self.redis.hincrby(f"{self.metrics_prefix}escalations:{date_key}", tenant_id, 1)
            
            # Escalations by priority
            priority_key = f"{self.metrics_prefix}priority:{date_key}:{priority}"
            self.redis.hincrby(priority_key, tenant_id, 1)
            
            # Queue time tracking
            queue_key = f"{self.metrics_prefix}queue_time:{tenant_id}"
            self.redis.lpush(queue_key, queue_time_ms)
            self.redis.ltrim(queue_key, 0, 999)
            
        except Exception as e:
            logger.error(f"Failed to record escalation metrics: {e}")
    
    def record_sla_breach(self, tenant_id: str, priority: str, breach_minutes: float):
        """Record SLA breach"""
        try:
            date_key = datetime.utcnow().strftime("%Y%m%d")
            
            # SLA breach counter
            breach_key = f"{self.metrics_prefix}sla_breach:{date_key}"
            self.redis.hincrby(breach_key, tenant_id, 1)
            
            # Breach time distribution
            breach_time_key = f"{self.metrics_prefix}breach_time:{tenant_id}"
            self.redis.lpush(breach_time_key, breach_minutes)
            self.redis.ltrim(breach_time_key, 0, 999)
            
        except Exception as e:
            logger.error(f"Failed to record SLA breach: {e}")
    
    def record_ai_reentry(self, tenant_id: str, success: bool, confidence: float):
        """Record AI re-entry attempt"""
        try:
            date_key = datetime.utcnow().strftime("%Y%m%d")
            
            # Total reentry attempts
            self.redis.hincrby(f"{self.metrics_prefix}reentry:{date_key}", tenant_id, 1)
            
            # Success/failure tracking
            outcome = "success" if success else "failure"
            outcome_key = f"{self.metrics_prefix}reentry:{date_key}:{outcome}"
            self.redis.hincrby(outcome_key, tenant_id, 1)
            
        except Exception as e:
            logger.error(f"Failed to record AI reentry: {e}")
    
    def get_handoff_rate(self, tenant_id: str, hours: int = 24) -> float:
        """Calculate handoff rate (escalations / total decisions)"""
        try:
            total_decisions = 0
            total_escalations = 0
            
            for h in range(hours):
                date_key = (datetime.utcnow() - timedelta(hours=h)).strftime("%Y%m%d")
                
                decisions = int(self.redis.hget(f"{self.metrics_prefix}decisions:{date_key}", tenant_id) or 0)
                escalations = int(self.redis.hget(f"{self.metrics_prefix}escalations:{date_key}", tenant_id) or 0)
                
                total_decisions += decisions
                total_escalations += escalations
            
            if total_decisions == 0:
                return 0.0
            
            return total_escalations / total_decisions
        except Exception as e:
            logger.error(f"Failed to calculate handoff rate: {e}")
            return 0.0
    
    def get_average_latency(self, tenant_id: str) -> float:
        """Get average handoff decision latency"""
        try:
            latency_key = f"{self.metrics_prefix}latency:{tenant_id}"
            samples = self.redis.lrange(latency_key, 0, -1)
            
            if not samples:
                return 0.0
            
            latencies = [float(s) for s in samples]
            return sum(latencies) / len(latencies)
        except Exception as e:
            logger.error(f"Failed to calculate average latency: {e}")
            return 0.0
    
    def get_sla_compliance_rate(self, tenant_id: str, hours: int = 24) -> float:
        """Calculate SLA compliance rate"""
        try:
            total_escalations = 0
            total_breaches = 0
            
            for h in range(hours):
                date_key = (datetime.utcnow() - timedelta(hours=h)).strftime("%Y%m%d")
                
                escalations = int(self.redis.hget(f"{self.metrics_prefix}escalations:{date_key}", tenant_id) or 0)
                breaches = int(self.redis.hget(f"{self.metrics_prefix}sla_breach:{date_key}", tenant_id) or 0)
                
                total_escalations += escalations
                total_breaches += breaches
            
            if total_escalations == 0:
                return 1.0
            
            return 1.0 - (total_breaches / total_escalations)
        except Exception as e:
            logger.error(f"Failed to calculate SLA compliance: {e}")
            return 0.0
    
    def get_priority_distribution(self, tenant_id: str, hours: int = 24) -> Dict[str, int]:
        """Get escalation priority distribution"""
        try:
            distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            
            for h in range(hours):
                date_key = (datetime.utcnow() - timedelta(hours=h)).strftime("%Y%m%d")
                
                for priority in distribution.keys():
                    priority_key = f"{self.metrics_prefix}priority:{date_key}:{priority}"
                    count = int(self.redis.hget(priority_key, tenant_id) or 0)
                    distribution[priority] += count
            
            return distribution
        except Exception as e:
            logger.error(f"Failed to get priority distribution: {e}")
            return {}
    
    def get_dashboard_metrics(self, tenant_id: str) -> Dict:
        """Get comprehensive dashboard metrics"""
        return {
            "handoff_rate_24h": self.get_handoff_rate(tenant_id, 24),
            "avg_latency_ms": self.get_average_latency(tenant_id),
            "sla_compliance_24h": self.get_sla_compliance_rate(tenant_id, 24),
            "priority_distribution_24h": self.get_priority_distribution(tenant_id, 24),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _bucket_confidence(self, confidence: float) -> str:
        """Bucket confidence score for histogram"""
        if confidence >= 0.9:
            return "0.9-1.0"
        elif confidence >= 0.8:
            return "0.8-0.9"
        elif confidence >= 0.7:
            return "0.7-0.8"
        elif confidence >= 0.6:
            return "0.6-0.7"
        else:
            return "0.0-0.6"
