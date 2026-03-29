"""
Index Manager
Ensures optimal database indexes for high-performance queries.
"""

from typing import List, Dict, Any
from shared.logger import get_logger
from shared.database import get_engine

logger = get_logger(__name__)


class IndexManager:
    """
    Manages database indexes for email_conversations table.
    Ensures all performance-critical indexes exist.
    """
    
    @staticmethod
    async def verify_indexes() -> Dict[str, bool]:
        """
        Verify all required indexes exist.
        
        Returns:
            Dictionary of index_name: exists
        """
        required_indexes = [
            "ix_email_conversations_user_thread",
            "ix_email_conversations_user_message",
            "ix_email_conversations_inbox",
            "ix_email_conversations_priority",
            "ix_email_conversations_intent",
            "ix_email_conversations_messages_gin",
            "ix_email_conversations_tags_gin",
            "uq_email_conversations_user_message"
        ]
        
        results = {}
        
        try:
            engine = get_engine()
            
            async with engine.connect() as conn:
                for index_name in required_indexes:
                    # Check if index exists
                    query = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE indexname = :index_name
                    )
                    """
                    
                    result = await conn.execute(query, {"index_name": index_name})
                    exists = result.scalar()
                    
                    results[index_name] = exists
                    
                    if exists:
                        logger.info(f"✅ Index exists: {index_name}")
                    else:
                        logger.warning(f"❌ Index missing: {index_name}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to verify indexes: {e}", exc_info=True)
            return {}
    
    @staticmethod
    async def create_missing_indexes() -> bool:
        """
        Create any missing indexes.
        
        Returns:
            True if all indexes created successfully
        """
        try:
            from models.email_conversation import EmailConversation
            
            engine = get_engine()
            
            async with engine.begin() as conn:
                # Create all indexes defined in model
                await conn.run_sync(EmailConversation.metadata.create_all)
            
            logger.info("✅ All indexes created/verified")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def analyze_index_usage() -> List[Dict[str, Any]]:
        """
        Analyze index usage statistics.
        
        Returns:
            List of index usage stats
        """
        try:
            engine = get_engine()
            
            query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched
            FROM pg_stat_user_indexes
            WHERE tablename = 'email_conversations'
            ORDER BY idx_scan DESC
            """
            
            async with engine.connect() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()
                
                stats = []
                for row in rows:
                    stats.append({
                        "schema": row[0],
                        "table": row[1],
                        "index": row[2],
                        "scans": row[3],
                        "tuples_read": row[4],
                        "tuples_fetched": row[5]
                    })
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to analyze index usage: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def get_table_size() -> Dict[str, Any]:
        """
        Get email_conversations table size statistics.
        
        Returns:
            Table size info
        """
        try:
            engine = get_engine()
            
            query = """
            SELECT
                pg_size_pretty(pg_total_relation_size('email_conversations')) as total_size,
                pg_size_pretty(pg_relation_size('email_conversations')) as table_size,
                pg_size_pretty(pg_indexes_size('email_conversations')) as indexes_size,
                (SELECT count(*) FROM email_conversations) as row_count
            """
            
            async with engine.connect() as conn:
                result = await conn.execute(query)
                row = result.fetchone()
                
                return {
                    "total_size": row[0],
                    "table_size": row[1],
                    "indexes_size": row[2],
                    "row_count": row[3]
                }
                
        except Exception as e:
            logger.error(f"Failed to get table size: {e}", exc_info=True)
            return {}
    
    @staticmethod
    async def vacuum_analyze() -> bool:
        """
        Run VACUUM ANALYZE on email_conversations table.
        
        This optimizes query performance and updates statistics.
        Should be run periodically (e.g., daily).
        """
        try:
            engine = get_engine()
            
            async with engine.connect() as conn:
                await conn.execute("VACUUM ANALYZE email_conversations")
            
            logger.info("✅ VACUUM ANALYZE completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to run VACUUM ANALYZE: {e}", exc_info=True)
            return False
    
    @staticmethod
    def get_recommended_indexes() -> List[str]:
        """
        Get list of recommended indexes for common queries.
        
        Returns:
            List of index creation SQL statements
        """
        return [
            # User + thread lookup (most common)
            """
            CREATE INDEX IF NOT EXISTS ix_email_conversations_user_thread
            ON email_conversations (user_id, thread_id)
            """,
            
            # User + message_id (deduplication)
            """
            CREATE INDEX IF NOT EXISTS ix_email_conversations_user_message
            ON email_conversations (user_id, message_id)
            """,
            
            # Inbox queries (unread, sorted by recent)
            """
            CREATE INDEX IF NOT EXISTS ix_email_conversations_inbox
            ON email_conversations (user_id, conversation_status, is_read, last_message_at DESC)
            """,
            
            # Priority-based sorting
            """
            CREATE INDEX IF NOT EXISTS ix_email_conversations_priority
            ON email_conversations (user_id, priority_score DESC, last_message_at DESC)
            """,
            
            # Intent filtering
            """
            CREATE INDEX IF NOT EXISTS ix_email_conversations_intent
            ON email_conversations (user_id, intent_type, conversation_status)
            """,
            
            # JSONB GIN indexes for fast JSON queries
            """
            CREATE INDEX IF NOT EXISTS ix_email_conversations_messages_gin
            ON email_conversations USING GIN (last_24h_messages)
            """,
            
            """
            CREATE INDEX IF NOT EXISTS ix_email_conversations_tags_gin
            ON email_conversations USING GIN (tags)
            """
        ]
