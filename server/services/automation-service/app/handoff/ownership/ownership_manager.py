"""
Human Ownership Manager - Prevents AI from replying when human owns conversation
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from redis import Redis

logger = logging.getLogger(__name__)

class OwnershipManager:
    """Manages conversation ownership between AI and human agents"""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.ownership_prefix = "handoff:owner:"
        self.default_ttl = 86400  # 24 hours
    
    def assign_to_human(
        self,
        thread_id: str,
        tenant_id: str,
        assigned_human: str,
        escalation_reason: str,
        priority: str,
        sla_minutes: int = 60
    ) -> bool:
        """Lock conversation to human agent"""
        key = f"{self.ownership_prefix}{thread_id}"
        
        ownership_data = {
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "assigned_human": assigned_human,
            "escalation_time": datetime.utcnow().isoformat(),
            "escalation_reason": escalation_reason,
            "priority": priority,
            "sla_expiry": (datetime.utcnow() + timedelta(minutes=sla_minutes)).isoformat(),
            "status": "human_assigned"
        }
        
        try:
            self.redis.setex(
                key,
                self.default_ttl,
                json.dumps(ownership_data)
            )
            logger.info(f"Assigned thread {thread_id} to human {assigned_human}")
            return True
        except Exception as e:
            logger.error(f"Failed to assign ownership: {e}")
            return False
    
    def is_human_owned(self, thread_id: str) -> bool:
        """Check if conversation is currently owned by human"""
        key = f"{self.ownership_prefix}{thread_id}"
        return self.redis.exists(key) > 0
    
    def get_owner(self, thread_id: str) -> Optional[dict]:
        """Get current ownership details"""
        key = f"{self.ownership_prefix}{thread_id}"
        data = self.redis.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    def release_to_ai(self, thread_id: str, resolution_summary: str = "") -> bool:
        """Release conversation back to AI"""
        key = f"{self.ownership_prefix}{thread_id}"
        
        try:
            owner_data = self.get_owner(thread_id)
            if owner_data:
                # Store resolution summary for AI context
                if resolution_summary:
                    summary_key = f"handoff:resolution:{thread_id}"
                    self.redis.setex(summary_key, 3600, resolution_summary)
                
                self.redis.delete(key)
                logger.info(f"Released thread {thread_id} back to AI")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to release ownership: {e}")
            return False
    
    def extend_sla(self, thread_id: str, additional_minutes: int) -> bool:
        """Extend SLA for complex cases"""
        owner_data = self.get_owner(thread_id)
        if not owner_data:
            return False
        
        try:
            current_expiry = datetime.fromisoformat(owner_data["sla_expiry"])
            new_expiry = current_expiry + timedelta(minutes=additional_minutes)
            owner_data["sla_expiry"] = new_expiry.isoformat()
            
            key = f"{self.ownership_prefix}{thread_id}"
            self.redis.setex(key, self.default_ttl, json.dumps(owner_data))
            return True
        except Exception as e:
            logger.error(f"Failed to extend SLA: {e}")
            return False
