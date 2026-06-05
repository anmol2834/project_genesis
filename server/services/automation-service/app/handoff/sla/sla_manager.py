"""
SLA Manager - Handles escalation timers, priority routing, and overdue detection
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from redis import Redis

logger = logging.getLogger(__name__)

class SLAManager:
    """Manages Service Level Agreements for escalated conversations"""
    
    # Priority-based SLA minutes
    SLA_PRIORITIES = {
        "critical": 15,   # billing, legal, security
        "high": 30,       # refund, angry customer
        "medium": 60,     # general support
        "low": 240        # informational
    }
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.sla_prefix = "handoff:sla:"
        self.overdue_set = "handoff:overdue"
    
    def create_sla(
        self,
        ticket_id: str,
        thread_id: str,
        tenant_id: str,
        priority: str,
        custom_minutes: Optional[int] = None
    ) -> dict:
        """Create SLA tracker for escalated ticket"""
        sla_minutes = custom_minutes or self.SLA_PRIORITIES.get(priority, 60)
        
        sla_data = {
            "ticket_id": ticket_id,
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat(),
            "sla_deadline": (datetime.utcnow() + timedelta(minutes=sla_minutes)).isoformat(),
            "sla_minutes": sla_minutes,
            "status": "active",
            "breached": False
        }
        
        try:
            key = f"{self.sla_prefix}{ticket_id}"
            ttl = sla_minutes * 60 * 2  # 2x SLA for Redis TTL
            self.redis.setex(key, ttl, json.dumps(sla_data))
            
            # Add to sorted set for overdue detection
            deadline_timestamp = (datetime.utcnow() + timedelta(minutes=sla_minutes)).timestamp()
            self.redis.zadd(self.overdue_set, {ticket_id: deadline_timestamp})
            
            logger.info(f"Created SLA for ticket {ticket_id} with {sla_minutes}m deadline")
            return sla_data
        except Exception as e:
            logger.error(f"Failed to create SLA: {e}")
            return {}
    
    def check_sla_status(self, ticket_id: str) -> Optional[dict]:
        """Check current SLA status"""
        key = f"{self.sla_prefix}{ticket_id}"
        data = self.redis.get(key)
        
        if not data:
            return None
        
        sla_data = json.loads(data)
        deadline = datetime.fromisoformat(sla_data["sla_deadline"])
        now = datetime.utcnow()
        
        if now > deadline and not sla_data["breached"]:
            sla_data["breached"] = True
            sla_data["breach_time"] = now.isoformat()
            self.redis.setex(key, 3600, json.dumps(sla_data))
            logger.warning(f"SLA breached for ticket {ticket_id}")
        
        sla_data["time_remaining_minutes"] = max(0, (deadline - now).total_seconds() / 60)
        return sla_data
    
    def get_overdue_tickets(self, limit: int = 100) -> List[str]:
        """Get tickets that have breached SLA"""
        try:
            now = datetime.utcnow().timestamp()
            # Get all tickets with deadline < now
            overdue = self.redis.zrangebyscore(self.overdue_set, 0, now, start=0, num=limit)
            return [ticket_id.decode() if isinstance(ticket_id, bytes) else ticket_id for ticket_id in overdue]
        except Exception as e:
            logger.error(f"Failed to get overdue tickets: {e}")
            return []
    
    def resolve_sla(self, ticket_id: str) -> bool:
        """Mark SLA as resolved"""
        try:
            key = f"{self.sla_prefix}{ticket_id}"
            data = self.redis.get(key)
            
            if data:
                sla_data = json.loads(data)
                sla_data["status"] = "resolved"
                sla_data["resolved_at"] = datetime.utcnow().isoformat()
                self.redis.setex(key, 3600, json.dumps(sla_data))  # Keep for 1h for metrics
            
            # Remove from overdue set
            self.redis.zrem(self.overdue_set, ticket_id)
            return True
        except Exception as e:
            logger.error(f"Failed to resolve SLA: {e}")
            return False
    
    def extend_sla(self, ticket_id: str, additional_minutes: int, reason: str = "") -> bool:
        """Extend SLA deadline"""
        try:
            key = f"{self.sla_prefix}{ticket_id}"
            data = self.redis.get(key)
            
            if not data:
                return False
            
            sla_data = json.loads(data)
            current_deadline = datetime.fromisoformat(sla_data["sla_deadline"])
            new_deadline = current_deadline + timedelta(minutes=additional_minutes)
            
            sla_data["sla_deadline"] = new_deadline.isoformat()
            sla_data["extended"] = True
            sla_data["extension_reason"] = reason
            
            self.redis.setex(key, 7200, json.dumps(sla_data))
            
            # Update sorted set
            self.redis.zadd(self.overdue_set, {ticket_id: new_deadline.timestamp()})
            
            logger.info(f"Extended SLA for {ticket_id} by {additional_minutes}m")
            return True
        except Exception as e:
            logger.error(f"Failed to extend SLA: {e}")
            return False
    
    def get_priority_for_risk(self, risk_level: str) -> str:
        """Map risk level to SLA priority"""
        risk_to_priority = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low"
        }
        return risk_to_priority.get(risk_level, "medium")
