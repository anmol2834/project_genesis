"""
Queue Manager - Distributed-safe human review queue with priority and tenant isolation
"""
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict
from redis import Redis
import uuid

logger = logging.getLogger(__name__)

class QueueManager:
    """Manages human review queue with FIFO + priority, tenant isolation, dedup-safe"""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.queue_prefix = "handoff:queue:"
        self.processing_prefix = "handoff:processing:"
        self.dedup_prefix = "handoff:dedup:"
    
    def enqueue(
        self,
        tenant_id: str,
        thread_id: str,
        ticket_id: str,
        priority: str,
        escalation_reason: str,
        context: Dict,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Add ticket to human review queue with dedup"""
        
        # Deduplication check
        dedup_key = f"{self.dedup_prefix}{thread_id}"
        if self.redis.exists(dedup_key):
            logger.info(f"Thread {thread_id} already in queue, skipping duplicate")
            return False
        
        queue_item = {
            "ticket_id": ticket_id,
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "priority": priority,
            "escalation_reason": escalation_reason,
            "context": context,
            "metadata": metadata or {},
            "enqueued_at": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        
        try:
            # Priority-based queue key
            queue_key = f"{self.queue_prefix}{tenant_id}:{priority}"
            
            # Add to queue (sorted set with timestamp for FIFO within priority)
            score = datetime.utcnow().timestamp()
            self.redis.zadd(queue_key, {ticket_id: score})
            
            # Store full ticket data
            ticket_key = f"handoff:ticket:{ticket_id}"
            self.redis.setex(ticket_key, 86400, json.dumps(queue_item))
            
            # Set dedup marker (1 hour TTL)
            self.redis.setex(dedup_key, 3600, "1")
            
            logger.info(f"Enqueued ticket {ticket_id} for tenant {tenant_id} with priority {priority}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue ticket: {e}")
            return False
    
    def dequeue(
        self,
        tenant_id: str,
        priorities: List[str] = ["critical", "high", "medium", "low"]
    ) -> Optional[Dict]:
        """Dequeue next ticket respecting priority order"""
        
        for priority in priorities:
            queue_key = f"{self.queue_prefix}{tenant_id}:{priority}"
            
            try:
                # Get oldest ticket in this priority (lowest score)
                items = self.redis.zrange(queue_key, 0, 0, withscores=False)
                
                if items:
                    ticket_id = items[0].decode() if isinstance(items[0], bytes) else items[0]
                    
                    # Move to processing set with distributed lock
                    processing_key = f"{self.processing_prefix}{ticket_id}"
                    lock_acquired = self.redis.set(processing_key, "1", nx=True, ex=600)
                    
                    if lock_acquired:
                        # Remove from queue
                        self.redis.zrem(queue_key, ticket_id)
                        
                        # Get ticket data
                        ticket_key = f"handoff:ticket:{ticket_id}"
                        ticket_data = self.redis.get(ticket_key)
                        
                        if ticket_data:
                            ticket = json.loads(ticket_data)
                            ticket["dequeued_at"] = datetime.utcnow().isoformat()
                            ticket["status"] = "processing"
                            
                            # Update ticket data
                            self.redis.setex(ticket_key, 86400, json.dumps(ticket))
                            
                            logger.info(f"Dequeued ticket {ticket_id} from {priority} queue")
                            return ticket
            except Exception as e:
                logger.error(f"Failed to dequeue from {priority} queue: {e}")
        
        return None
    
    def complete_processing(self, ticket_id: str) -> bool:
        """Mark ticket as completed and release lock"""
        try:
            processing_key = f"{self.processing_prefix}{ticket_id}"
            self.redis.delete(processing_key)
            
            # Update ticket status
            ticket_key = f"handoff:ticket:{ticket_id}"
            ticket_data = self.redis.get(ticket_key)
            
            if ticket_data:
                ticket = json.loads(ticket_data)
                ticket["status"] = "completed"
                ticket["completed_at"] = datetime.utcnow().isoformat()
                self.redis.setex(ticket_key, 3600, json.dumps(ticket))  # Keep for 1h
            
            logger.info(f"Completed processing ticket {ticket_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to complete processing: {e}")
            return False
    
    def requeue_stale(self, tenant_id: str, stale_minutes: int = 10) -> int:
        """Requeue stale tickets that were processing but not completed"""
        requeued_count = 0
        
        try:
            # Find all processing tickets
            pattern = f"{self.processing_prefix}*"
            for key in self.redis.scan_iter(match=pattern):
                ticket_id = key.decode().split(":")[-1]
                ticket_key = f"handoff:ticket:{ticket_id}"
                ticket_data = self.redis.get(ticket_key)
                
                if ticket_data:
                    ticket = json.loads(ticket_data)
                    
                    # Check if stale
                    if ticket.get("tenant_id") == tenant_id and ticket.get("status") == "processing":
                        dequeued_at = datetime.fromisoformat(ticket["dequeued_at"])
                        age_minutes = (datetime.utcnow() - dequeued_at).total_seconds() / 60
                        
                        if age_minutes > stale_minutes:
                            # Requeue
                            queue_key = f"{self.queue_prefix}{tenant_id}:{ticket['priority']}"
                            score = datetime.utcnow().timestamp()
                            self.redis.zadd(queue_key, {ticket_id: score})
                            
                            # Release lock
                            self.redis.delete(key)
                            
                            # Update status
                            ticket["status"] = "requeued"
                            ticket["requeued_at"] = datetime.utcnow().isoformat()
                            self.redis.setex(ticket_key, 86400, json.dumps(ticket))
                            
                            requeued_count += 1
                            logger.info(f"Requeued stale ticket {ticket_id}")
            
            return requeued_count
        except Exception as e:
            logger.error(f"Failed to requeue stale tickets: {e}")
            return 0
    
    def get_queue_depth(self, tenant_id: str, priority: Optional[str] = None) -> int:
        """Get current queue depth"""
        try:
            if priority:
                queue_key = f"{self.queue_prefix}{tenant_id}:{priority}"
                return self.redis.zcard(queue_key)
            else:
                total = 0
                for p in ["critical", "high", "medium", "low"]:
                    queue_key = f"{self.queue_prefix}{tenant_id}:{p}"
                    total += self.redis.zcard(queue_key)
                return total
        except Exception as e:
            logger.error(f"Failed to get queue depth: {e}")
            return 0
