"""
AI Re-entry Manager - Enables AI to resume conversations after human resolution
"""
import logging
from datetime import datetime
from typing import Optional, Dict
from redis import Redis

logger = logging.getLogger(__name__)

class AIReentryManager:
    """Manages AI re-entry eligibility and context synchronization"""
    
    def __init__(self, redis_client: Redis, postgres_conn):
        self.redis = redis_client
        self.pg_conn = postgres_conn
        self.reentry_prefix = "handoff:reentry:"
    
    def evaluate_reentry_eligibility(
        self,
        thread_id: str,
        tenant_id: str,
        resolution_summary: str,
        resolution_type: str
    ) -> Dict:
        """Determine if AI can safely resume conversation"""
        
        eligibility = {
            "eligible": False,
            "reason": "",
            "confidence_threshold": 0.8,
            "require_human_summary": True,
            "allow_proactive": False
        }
        
        # Evaluate based on resolution type
        if resolution_type == "information_provided":
            # AI can resume with context
            eligibility["eligible"] = True
            eligibility["reason"] = "Information provided by human, AI can continue"
            eligibility["allow_proactive"] = False
        
        elif resolution_type == "issue_resolved":
            # AI can handle follow-ups
            eligibility["eligible"] = True
            eligibility["reason"] = "Issue resolved, AI can handle follow-ups"
            eligibility["allow_proactive"] = True
        
        elif resolution_type == "escalated_further":
            # Keep in human hands
            eligibility["eligible"] = False
            eligibility["reason"] = "Further escalation, human supervision required"
        
        elif resolution_type == "policy_exception":
            # Sensitive, keep human
            eligibility["eligible"] = False
            eligibility["reason"] = "Policy exception handled, human supervision required"
        
        elif resolution_type == "customer_satisfaction":
            # AI can resume cautiously
            eligibility["eligible"] = True
            eligibility["reason"] = "Customer satisfied, AI can handle routine follow-ups"
            eligibility["confidence_threshold"] = 0.9  # Higher threshold
        
        else:
            # Default: allow with caution
            eligibility["eligible"] = True
            eligibility["reason"] = "Default reentry with human context"
        
        # Store reentry decision
        reentry_key = f"{self.reentry_prefix}{thread_id}"
        reentry_data = {
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "resolution_summary": resolution_summary,
            "resolution_type": resolution_type,
            "eligibility": eligibility,
            "evaluated_at": datetime.utcnow().isoformat()
        }
        
        try:
            self.redis.setex(reentry_key, 3600, str(reentry_data))
            logger.info(f"AI reentry eligibility for {thread_id}: {eligibility['eligible']}")
        except Exception as e:
            logger.error(f"Failed to store reentry decision: {e}")
        
        return eligibility
    
    def get_reentry_context(self, thread_id: str) -> Optional[Dict]:
        """Retrieve human resolution context for AI"""
        
        # Get resolution summary from Redis
        resolution_key = f"handoff:resolution:{thread_id}"
        resolution_summary = self.redis.get(resolution_key)
        
        if not resolution_summary:
            return None
        
        # Get reentry eligibility
        reentry_key = f"{self.reentry_prefix}{thread_id}"
        reentry_data = self.redis.get(reentry_key)
        
        context = {
            "resolution_summary": resolution_summary.decode() if isinstance(resolution_summary, bytes) else resolution_summary,
            "human_resolved": True,
            "reentry_allowed": True
        }
        
        if reentry_data:
            try:
                import ast
                reentry_dict = ast.literal_eval(reentry_data.decode() if isinstance(reentry_data, bytes) else reentry_data)
                context["eligibility"] = reentry_dict.get("eligibility", {})
                context["resolution_type"] = reentry_dict.get("resolution_type", "unknown")
            except:
                pass
        
        return context
    
    def inject_human_context(
        self,
        thread_id: str,
        conversation_history: list,
        resolution_summary: str
    ) -> list:
        """Inject human resolution into conversation history for AI context"""
        
        # Create synthetic message representing human resolution
        human_resolution_message = {
            "role": "system",
            "content": f"[HUMAN AGENT RESOLUTION] {resolution_summary}",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "source": "human_agent",
                "resolution": True
            }
        }
        
        # Append to conversation history
        updated_history = conversation_history + [human_resolution_message]
        
        logger.info(f"Injected human resolution context for {thread_id}")
        return updated_history
    
    def mark_ai_resumed(self, thread_id: str, tenant_id: str) -> bool:
        """Mark that AI has successfully resumed conversation"""
        try:
            resume_key = f"handoff:ai_resumed:{thread_id}"
            resume_data = {
                "thread_id": thread_id,
                "tenant_id": tenant_id,
                "resumed_at": datetime.utcnow().isoformat()
            }
            
            self.redis.setex(resume_key, 86400, str(resume_data))
            
            # Clear reentry keys
            self.redis.delete(f"{self.reentry_prefix}{thread_id}")
            self.redis.delete(f"handoff:resolution:{thread_id}")
            
            logger.info(f"AI resumed conversation for {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark AI resumed: {e}")
            return False
    
    def should_ai_respond(self, thread_id: str, message_confidence: float) -> bool:
        """Check if AI should respond given reentry context"""
        
        reentry_context = self.get_reentry_context(thread_id)
        
        if not reentry_context:
            # No reentry context, proceed normally
            return message_confidence >= 0.7
        
        # Apply stricter threshold after human handoff
        eligibility = reentry_context.get("eligibility", {})
        required_threshold = eligibility.get("confidence_threshold", 0.8)
        
        return message_confidence >= required_threshold
    
    def block_ai_reentry(self, thread_id: str, reason: str) -> bool:
        """Permanently block AI from re-entering conversation"""
        try:
            block_key = f"handoff:ai_blocked:{thread_id}"
            block_data = {
                "thread_id": thread_id,
                "blocked_at": datetime.utcnow().isoformat(),
                "reason": reason
            }
            
            self.redis.setex(block_key, 86400 * 7, str(block_data))  # 7 days
            logger.info(f"Blocked AI reentry for {thread_id}: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to block AI reentry: {e}")
            return False
    
    def is_ai_blocked(self, thread_id: str) -> bool:
        """Check if AI is blocked from conversation"""
        block_key = f"handoff:ai_blocked:{thread_id}"
        return self.redis.exists(block_key) > 0
