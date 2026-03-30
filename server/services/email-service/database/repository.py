"""
Email Conversation Repository
High-performance database operations with upsert logic and optimized queries.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import select, update, and_
from sqlalchemy.dialects.postgresql import insert
from uuid import UUID

from shared.logger import get_logger
from shared.database import get_db_session
from models.email_conversation import EmailConversation

logger = get_logger(__name__)


class EmailConversationRepository:
    """
    Repository for email_conversations table.
    Handles all database operations with optimization.
    """
    
    @staticmethod
    async def upsert_conversation(
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
        direction: str
    ) -> Optional[EmailConversation]:
        """
        Upsert conversation with optimized JSONB update.
        
        Logic:
        - If thread exists: UPDATE last_24h_messages, message_id, last_message_at
        - Else: INSERT new conversation
        
        Returns:
            EmailConversation object or None
        """
        try:
            async with get_db_session() as session:
                # Check if conversation exists
                stmt = select(EmailConversation).where(
                    and_(
                        EmailConversation.user_id == UUID(user_id),
                        EmailConversation.thread_id == thread_id
                    )
                )
                
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    # UPDATE existing conversation
                    logger.debug(f"Updating existing conversation: {thread_id}")
                    
                    existing.message_id = message_id
                    existing.last_24h_messages = last_24h_messages
                    existing.last_message_at = last_message_at
                    existing.updated_at = datetime.utcnow()
                    existing.is_read = False  # Mark as unread on new message
                    
                    # Update subject if changed
                    if subject and subject != existing.subject:
                        existing.subject = subject
                    
                    await session.commit()
                    await session.refresh(existing)
                    
                    logger.debug(
                        f"Updated conversation: thread={thread_id}, "
                        f"messages={len(last_24h_messages)}"
                    )
                    
                    return existing
                    
                else:
                    # INSERT new conversation
                    logger.debug(f"Creating new conversation: {thread_id}")
                    
                    conversation = EmailConversation(
                        user_id=UUID(user_id),
                        email_account_id=UUID(email_account_id),
                        provider=provider,
                        thread_id=thread_id,
                        message_id=message_id,
                        from_email=from_email,
                        to_emails=to_emails,
                        cc_emails=cc_emails or [],
                        bcc_emails=bcc_emails or [],
                        subject=subject or "",
                        last_24h_messages=last_24h_messages,
                        last_message_at=last_message_at,
                        is_read=False,
                        conversation_status="active"
                    )
                    
                    session.add(conversation)
                    await session.commit()
                    await session.refresh(conversation)
                    
                    logger.debug(
                        f"Created conversation: thread={thread_id}, "
                        f"messages={len(last_24h_messages)}"
                    )
                    
                    return conversation
                    
        except Exception as e:
            logger.error(f"Failed to upsert conversation: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def get_conversation_by_thread(
        user_id: str,
        thread_id: str
    ) -> Optional[EmailConversation]:
        """Get conversation by thread_id."""
        try:
            async with get_db_session() as session:
                stmt = select(EmailConversation).where(
                    and_(
                        EmailConversation.user_id == UUID(user_id),
                        EmailConversation.thread_id == thread_id
                    )
                )
                
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def get_conversation_by_message_id(
        user_id: str,
        message_id: str
    ) -> Optional[EmailConversation]:
        """Get conversation by message_id (for deduplication)."""
        try:
            async with get_db_session() as session:
                stmt = select(EmailConversation).where(
                    and_(
                        EmailConversation.user_id == UUID(user_id),
                        EmailConversation.message_id == message_id
                    )
                )
                
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error(f"Failed to get conversation by message_id: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def update_conversation_summary(
        conversation_id: UUID,
        summary: str
    ) -> bool:
        """
        Update AI-generated conversation summary.
        
        This is called by AI service after generating summary.
        """
        try:
            async with get_db_session() as session:
                stmt = (
                    update(EmailConversation)
                    .where(EmailConversation.id == conversation_id)
                    .values(
                        message_summary=summary,
                        updated_at=datetime.utcnow()
                    )
                )
                
                await session.execute(stmt)
                await session.commit()
                
                logger.debug(f"Updated summary for conversation: {conversation_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update summary: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def mark_as_read(
        user_id: str,
        thread_id: str
    ) -> bool:
        """Mark conversation as read."""
        try:
            async with get_db_session() as session:
                stmt = (
                    update(EmailConversation)
                    .where(
                        and_(
                            EmailConversation.user_id == UUID(user_id),
                            EmailConversation.thread_id == thread_id
                        )
                    )
                    .values(
                        is_read=True,
                        updated_at=datetime.utcnow()
                    )
                )
                
                await session.execute(stmt)
                await session.commit()
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to mark as read: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def get_active_conversations(
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[EmailConversation]:
        """
        Get active conversations for inbox.
        Sorted by last_message_at DESC.
        """
        try:
            async with get_db_session() as session:
                stmt = (
                    select(EmailConversation)
                    .where(
                        and_(
                            EmailConversation.user_id == UUID(user_id),
                            EmailConversation.conversation_status == "active"
                        )
                    )
                    .order_by(EmailConversation.last_message_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                
                result = await session.execute(stmt)
                return list(result.scalars().all())
                
        except Exception as e:
            logger.error(f"Failed to get active conversations: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def get_unread_count(user_id: str) -> int:
        """Get count of unread conversations."""
        try:
            async with get_db_session() as session:
                from sqlalchemy import func
                
                stmt = select(func.count(EmailConversation.id)).where(
                    and_(
                        EmailConversation.user_id == UUID(user_id),
                        EmailConversation.is_read == False,
                        EmailConversation.conversation_status == "active"
                    )
                )
                
                result = await session.execute(stmt)
                return result.scalar() or 0
                
        except Exception as e:
            logger.error(f"Failed to get unread count: {e}", exc_info=True)
            return 0
