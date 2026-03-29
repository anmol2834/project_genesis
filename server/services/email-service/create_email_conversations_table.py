"""
Database Migration: Create email_conversations table
Run this script to initialize the AI-first email ingestion system.

Usage:
    python create_email_conversations_table.py
"""

import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.database import init_database, get_engine
from shared.logger import setup_logging
from models.email_conversation import EmailConversation

logger = setup_logging("email-service-migration")


async def create_email_conversations_table():
    """Create email_conversations table with all indexes."""
    logger.info("Starting email_conversations table creation...")
    
    try:
        # Initialize database connection
        await init_database()
        logger.info("Database connection initialized")
        
        # Get engine
        engine = get_engine()
        
        # Create table
        async with engine.begin() as conn:
            await conn.run_sync(EmailConversation.metadata.create_all)
        
        logger.info("✅ email_conversations table created successfully!")
        logger.info("✅ All indexes created successfully!")
        logger.info("")
        logger.info("Table structure:")
        logger.info("  - Core identifiers: id, user_id, email_account_id, provider, thread_id, message_id")
        logger.info("  - Email metadata: from_email, to_emails, cc_emails, bcc_emails, subject")
        logger.info("  - AI features: last_24h_messages (JSONB), message_summary (TEXT)")
        logger.info("  - Performance: last_message_at, is_read, conversation_status")
        logger.info("  - Advanced: intent_type, priority_score, tags (JSONB)")
        logger.info("")
        logger.info("Indexes created:")
        logger.info("  - ix_email_conversations_user_thread (user_id, thread_id)")
        logger.info("  - ix_email_conversations_user_message (user_id, message_id)")
        logger.info("  - ix_email_conversations_inbox (user_id, conversation_status, is_read, last_message_at)")
        logger.info("  - ix_email_conversations_priority (user_id, priority_score, last_message_at)")
        logger.info("  - ix_email_conversations_intent (user_id, intent_type, conversation_status)")
        logger.info("  - ix_email_conversations_messages_gin (last_24h_messages) - GIN index")
        logger.info("  - ix_email_conversations_tags_gin (tags) - GIN index")
        logger.info("")
        logger.info("🚀 Email ingestion system is ready!")
        
    except Exception as e:
        logger.error(f"❌ Failed to create table: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(create_email_conversations_table())
