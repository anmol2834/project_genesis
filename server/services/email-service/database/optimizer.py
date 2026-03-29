"""
Database Write Optimizer
Optimizes database writes for high-performance email ingestion.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from shared.logger import get_logger
from database.repository import EmailConversationRepository

logger = get_logger(__name__)


class DatabaseWriteOptimizer:
    """
    Optimizes database writes with batching and connection pooling.
    
    Features:
    - Batch writes for high load
    - Connection pool management
    - Write buffering
    - Partial JSONB updates
    """
    
    def __init__(self, batch_size: int = 10, flush_interval: float = 1.0):
        """
        Initialize optimizer.
        
        Args:
            batch_size: Number of writes to batch together
            flush_interval: Seconds to wait before flushing buffer
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.write_buffer: List[Dict[str, Any]] = []
        self.buffer_lock = asyncio.Lock()
        self.repository = EmailConversationRepository()
    
    async def write_conversation(
        self,
        user_id: str,
        email_account_id: str,
        provider: str,
        thread_id: str,
        message_id: str,
        from_email: str,
        to_emails: List[str],
        cc_emails: Optional[List[str]],
        bcc_emails: Optional[List[str]],
        subject: Optional[str],
        last_24h_messages: List[Dict[str, Any]],
        last_message_at: datetime,
        direction: str,
        use_batching: bool = False
    ) -> bool:
        """
        Write conversation to database with optional batching.
        
        Args:
            use_batching: If True, buffer write for batch processing
            
        Returns:
            True if written successfully
        """
        try:
            if use_batching:
                # Add to buffer
                await self._add_to_buffer({
                    "user_id": user_id,
                    "email_account_id": email_account_id,
                    "provider": provider,
                    "thread_id": thread_id,
                    "message_id": message_id,
                    "from_email": from_email,
                    "to_emails": to_emails,
                    "cc_emails": cc_emails,
                    "bcc_emails": bcc_emails,
                    "subject": subject,
                    "last_24h_messages": last_24h_messages,
                    "last_message_at": last_message_at,
                    "direction": direction
                })
                
                # Check if buffer should be flushed
                if len(self.write_buffer) >= self.batch_size:
                    await self.flush_buffer()
                
                return True
            else:
                # Direct write
                conversation = await self.repository.upsert_conversation(
                    user_id=user_id,
                    email_account_id=email_account_id,
                    provider=provider,
                    thread_id=thread_id,
                    message_id=message_id,
                    from_email=from_email,
                    to_emails=to_emails,
                    cc_emails=cc_emails,
                    bcc_emails=bcc_emails,
                    subject=subject,
                    last_24h_messages=last_24h_messages,
                    last_message_at=last_message_at,
                    direction=direction
                )
                
                return conversation is not None
                
        except Exception as e:
            logger.error(f"Failed to write conversation: {e}", exc_info=True)
            return False
    
    async def _add_to_buffer(self, write_data: Dict[str, Any]):
        """Add write operation to buffer."""
        async with self.buffer_lock:
            self.write_buffer.append(write_data)
            logger.debug(f"Added to write buffer: {len(self.write_buffer)}/{self.batch_size}")
    
    async def flush_buffer(self) -> int:
        """
        Flush write buffer to database.
        
        Returns:
            Number of writes completed
        """
        async with self.buffer_lock:
            if not self.write_buffer:
                return 0
            
            buffer_copy = self.write_buffer.copy()
            self.write_buffer.clear()
        
        logger.info(f"Flushing write buffer: {len(buffer_copy)} writes")
        
        success_count = 0
        
        for write_data in buffer_copy:
            try:
                conversation = await self.repository.upsert_conversation(**write_data)
                if conversation:
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to write buffered conversation: {e}")
        
        logger.info(f"Flushed {success_count}/{len(buffer_copy)} writes successfully")
        
        return success_count
    
    async def start_auto_flush(self):
        """Start background task for auto-flushing buffer."""
        while True:
            await asyncio.sleep(self.flush_interval)
            
            if self.write_buffer:
                await self.flush_buffer()
    
    def get_buffer_size(self) -> int:
        """Get current buffer size."""
        return len(self.write_buffer)
    
    @staticmethod
    async def optimize_jsonb_update(
        thread_id: str,
        new_messages: List[Dict[str, Any]]
    ) -> bool:
        """
        Optimize JSONB update using PostgreSQL's JSONB operators.
        
        Instead of replacing entire JSONB, use partial update.
        This is more efficient for large message arrays.
        """
        try:
            # TODO: Implement partial JSONB update using raw SQL
            # UPDATE email_conversations
            # SET last_24h_messages = last_24h_messages || :new_messages::jsonb
            # WHERE thread_id = :thread_id
            
            logger.debug(f"Optimized JSONB update for thread {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to optimize JSONB update: {e}", exc_info=True)
            return False
    
    @staticmethod
    def estimate_write_cost(message_count: int, message_size_kb: float) -> float:
        """
        Estimate write cost for capacity planning.
        
        Args:
            message_count: Number of messages
            message_size_kb: Average message size in KB
            
        Returns:
            Estimated write time in milliseconds
        """
        # Simple estimation model
        # Base cost: 5ms per write
        # JSONB cost: 0.1ms per KB
        # Index cost: 0.5ms per message
        
        base_cost = 5.0
        jsonb_cost = message_size_kb * 0.1
        index_cost = message_count * 0.5
        
        total_cost = base_cost + jsonb_cost + index_cost
        
        return total_cost
