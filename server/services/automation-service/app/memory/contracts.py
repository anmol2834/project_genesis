"""
Memory Layer - Interface Contracts
===================================
Defines contracts for conversation memory management.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ThreadMemory:
    """Conversation memory structure"""
    thread_id: str = ""
    turn_count: int = 0
    last_intent: str = ""
    last_sub_intent: str = ""
    last_action: str = ""
    last_topic: str = ""
    
    # Conversation state
    conversation_state: str = "initial"  # initial, greeting, qualification, pricing, closing
    stage: str = "awareness"             # awareness, consideration, decision
    
    # User context
    user_preferences: dict = field(default_factory=dict)
    context_summary: str = ""
    recommended_next_actions: list[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class IMemoryStore(ABC):
    """Interface for memory storage (hot or cold)"""
    
    @abstractmethod
    async def load(self, thread_id: str) -> Optional[ThreadMemory]:
        """Load memory for a thread"""
        pass
    
    @abstractmethod
    async def save(self, thread_id: str, memory: ThreadMemory) -> bool:
        """Save memory for a thread"""
        pass
    
    @abstractmethod
    async def delete(self, thread_id: str) -> bool:
        """Delete memory for a thread"""
        pass
    
    @abstractmethod
    async def exists(self, thread_id: str) -> bool:
        """Check if memory exists for a thread"""
        pass


class IMemoryEnricher(ABC):
    """Interface for query enrichment using memory"""
    
    @abstractmethod
    def enrich_query(
        self, 
        query: str, 
        memory: ThreadMemory,
        is_continuation: bool
    ) -> tuple[str, list[str]]:
        """
        Enrich query with conversation context.
        
        Args:
            query: Original query
            memory: Conversation memory
            is_continuation: Is this a continuation query?
            
        Returns:
            (enriched_query, keywords)
        """
        pass
    
    @abstractmethod
    def resolve_references(
        self,
        query: str,
        memory: ThreadMemory
    ) -> str:
        """
        Resolve references like "the first one", "that product".
        
        Args:
            query: Query with potential references
            memory: Conversation memory
            
        Returns:
            Query with resolved references
        """
        pass


class IMemorySummarizer(ABC):
    """Interface for conversation summarization"""
    
    @abstractmethod
    async def summarize(
        self,
        thread_id: str,
        messages: list[dict]
    ) -> str:
        """
        Summarize conversation history.
        
        Args:
            thread_id: Thread identifier
            messages: List of messages to summarize
            
        Returns:
            Summary text
        """
        pass
