"""
Active Topic Memory Manager
============================
Manages active conversation topics and working memory for continuity.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime


class ActiveTopicMemory:
    """
    Stores active conversation context to enable RAG-free continuations.
    
    Working memory includes:
    - Active topic
    - Active entities
    - Last customer goal
    - Last business offer
    - Unresolved questions
    - Retrieved chunks cache
    - Last response summary
    - Conversation stage
    """
    
    def __init__(self):
        self.memory: Dict[str, Any] = {}
    
    def update_active_context(
        self,
        conversation_id: str,
        topic: str,
        entities: List[str],
        customer_goal: str,
        business_offer: Optional[str] = None,
        unresolved_question: Optional[str] = None,
        retrieved_chunks: Optional[List] = None,
        response_summary: Optional[str] = None,
        conversation_stage: Optional[str] = None
    ):
        """
        Update active conversation context.
        
        This is the WORKING MEMORY that enables memory-first responses.
        """
        if conversation_id not in self.memory:
            self.memory[conversation_id] = {}
        
        context = self.memory[conversation_id]
        
        # Update fields
        context["active_topic"] = topic
        context["active_entities"] = entities
        context["last_customer_goal"] = customer_goal
        context["last_business_offer"] = business_offer
        context["last_unresolved_question"] = unresolved_question
        context["conversation_stage"] = conversation_stage
        context["last_updated"] = datetime.utcnow().isoformat()
        
        # Cache retrieved chunks for reuse
        if retrieved_chunks:
            context["retrieved_chunks_cache"] = retrieved_chunks
            context["chunks_cached_at"] = datetime.utcnow().isoformat()
        
        # Store response summary for continuity
        if response_summary:
            context["last_response_summary"] = response_summary
    
    def get_active_context(self, conversation_id: str) -> Dict[str, Any]:
        """Get active context for conversation."""
        return self.memory.get(conversation_id, {})
    
    def has_sufficient_context(
        self,
        conversation_id: str,
        required_fields: Optional[List[str]] = None
    ) -> bool:
        """
        Check if we have sufficient context to skip retrieval.
        
        Args:
            required_fields: List of required fields, e.g. ["active_topic", "retrieved_chunks_cache"]
        """
        context = self.get_active_context(conversation_id)
        
        if not context:
            return False
        
        # Default required fields for memory-first response
        if required_fields is None:
            required_fields = ["active_topic", "active_entities"]
        
        # Check all required fields exist and are non-empty
        for field in required_fields:
            value = context.get(field)
            if not value:
                return False
            
            # Check if lists are non-empty
            if isinstance(value, list) and len(value) == 0:
                return False
        
        return True
    
    def can_reuse_cached_chunks(
        self,
        conversation_id: str,
        topic: str,
        max_age_seconds: int = 300  # 5 minutes
    ) -> bool:
        """
        Check if cached retrieval chunks can be reused.
        
        Conditions:
        - Same topic
        - Chunks exist
        - Not too old
        """
        context = self.get_active_context(conversation_id)
        
        if not context:
            return False
        
        # Check topic match
        if context.get("active_topic") != topic:
            return False
        
        # Check chunks exist
        cached_chunks = context.get("retrieved_chunks_cache", [])
        if not cached_chunks:
            return False
        
        # Check age
        cached_at = context.get("chunks_cached_at")
        if cached_at:
            try:
                cached_time = datetime.fromisoformat(cached_at)
                age_seconds = (datetime.utcnow() - cached_time).total_seconds()
                if age_seconds > max_age_seconds:
                    return False
            except:
                return False
        
        return True
    
    def get_cached_chunks(self, conversation_id: str) -> Optional[List]:
        """Get cached retrieval chunks."""
        context = self.get_active_context(conversation_id)
        return context.get("retrieved_chunks_cache")
    
    def clear_cache(self, conversation_id: str):
        """Clear cached data for conversation."""
        if conversation_id in self.memory:
            context = self.memory[conversation_id]
            context.pop("retrieved_chunks_cache", None)
            context.pop("chunks_cached_at", None)
    
    def should_skip_retrieval(
        self,
        conversation_id: str,
        continuation_context: Dict
    ) -> bool:
        """
        Determine if retrieval can be skipped based on memory.
        
        SKIP retrieval if:
        - Same topic continuation
        - Sufficient cached context
        - No new information needed
        """
        # Check if continuation says retrieval needed
        if continuation_context.get("requires_retrieval", True):
            return False
        
        # Check if we have sufficient context
        if not self.has_sufficient_context(conversation_id):
            return False
        
        context = self.get_active_context(conversation_id)
        
        # Check if we have cached chunks for topic
        active_topic = continuation_context.get("active_topic") or context.get("active_topic")
        if active_topic and self.can_reuse_cached_chunks(conversation_id, active_topic):
            return True
        
        # If all context exists in memory, can skip
        if context.get("active_topic") and context.get("active_entities"):
            return True
        
        return False
    
    def build_memory_context_summary(self, conversation_id: str) -> str:
        """
        Build rich context summary from memory for prompt injection.
        
        This replaces retrieval when memory is sufficient.
        """
        context = self.get_active_context(conversation_id)
        
        if not context:
            return ""
        
        summary_parts = []
        
        # Active topic
        topic = context.get("active_topic")
        if topic:
            summary_parts.append(f"Current Topic: {topic}")
        
        # Active entities
        entities = context.get("active_entities", [])
        if entities:
            summary_parts.append(f"Relevant Products/Features: {', '.join(entities)}")
        
        # Customer goal
        goal = context.get("last_customer_goal")
        if goal:
            summary_parts.append(f"Customer Goal: {goal}")
        
        # Business offer
        offer = context.get("last_business_offer")
        if offer:
            summary_parts.append(f"Last Business Offer: {offer}")
        
        # Unresolved question
        question = context.get("last_unresolved_question")
        if question:
            summary_parts.append(f"Pending Question: {question}")
        
        # Last response summary
        response = context.get("last_response_summary")
        if response:
            summary_parts.append(f"Previous Response Context: {response}")
        
        # Conversation stage
        stage = context.get("conversation_stage")
        if stage:
            summary_parts.append(f"Customer Journey Stage: {stage}")
        
        return "\n".join(summary_parts)


# Global instance
_active_memory: ActiveTopicMemory = None


def get_active_topic_memory() -> ActiveTopicMemory:
    """Get global active topic memory."""
    global _active_memory
    if _active_memory is None:
        _active_memory = ActiveTopicMemory()
    return _active_memory


__all__ = ["ActiveTopicMemory", "get_active_topic_memory"]
