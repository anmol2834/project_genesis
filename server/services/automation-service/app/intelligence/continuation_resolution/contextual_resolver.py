"""
Contextual Continuation Resolver
==================================
Walks backwards through conversation history to resolve short message context.
"""
from typing import Dict, List, Any, Optional, Tuple
import json


class ContextualContinuationResolver:
    """
    Resolves context for short, ambiguous messages by analyzing conversation history.
    
    Example:
        Latest: "yes"
        Prev 1: "Would you like pricing details?"
        Prev 2: "Here's our AeroCam X1 drone..."
        
        Resolved: "Customer wants AeroCam X1 pricing details"
    """
    
    def __init__(self):
        self.max_context_turns = 5  # Look back max 5 turns
        
    def resolve_continuation_context(
        self,
        latest_message: str,
        continuation_type: str,
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve context for continuation message.
        
        Returns enriched context with:
        - resolved_intent
        - active_topic
        - relevant_entities
        - conversation_summary
        - requires_retrieval
        - cached_context
        """
        # Extract conversation history
        history = memory.get("history", [])
        turn_count = memory.get("turn_count", 0)
        
        if not history or turn_count == 0:
            # No history - treat as new conversation
            return self._create_fallback_context(latest_message, continuation_type)
        
        # Walk backwards through history
        context = self._walk_history_backwards(
            latest_message,
            continuation_type,
            history,
            memory
        )
        
        return context
    
    def _walk_history_backwards(
        self,
        latest_message: str,
        continuation_type: str,
        history: List[Dict],
        memory: Dict
    ) -> Dict[str, Any]:
        """
        Walk backwards through conversation to find context.
        
        Priority:
        1. Last 1-2 messages
        2. Last 3-4 messages
        3. Active topic memory
        4. Last resolved intent
        """
        # Start with most recent
        recent_turns = history[-self.max_context_turns:][::-1]  # Reverse for backwards walk
        
        context = {
            "resolved_intent": None,
            "active_topic": None,
            "relevant_entities": [],
            "conversation_summary": "",
            "requires_retrieval": False,
            "cached_context": None,
            "continuation_type": continuation_type,
            "context_source": None
        }
        
        # Check immediate previous turn first
        if recent_turns:
            prev_turn = recent_turns[0]
            context = self._resolve_from_previous_turn(
                latest_message,
                continuation_type,
                prev_turn,
                context
            )
            
            if context["resolved_intent"]:
                context["context_source"] = "previous_turn"
                return context
        
        # Check last 2-3 turns
        if len(recent_turns) >= 2:
            context = self._resolve_from_recent_turns(
                latest_message,
                continuation_type,
                recent_turns[:3],
                context
            )
            
            if context["resolved_intent"]:
                context["context_source"] = "recent_turns"
                return context
        
        # Check active topic memory
        active_topic = memory.get("active_topics", [])
        if active_topic:
            context["active_topic"] = active_topic[0] if isinstance(active_topic, list) else active_topic
            context["context_source"] = "active_topic"
        
        # Check last resolved intent
        last_intent = memory.get("last_intent", None)
        if last_intent:
            context["resolved_intent"] = last_intent
            context["context_source"] = "last_intent"
        
        # Check shared entities
        shared_entities = memory.get("shared_entities", {})
        if shared_entities:
            context["relevant_entities"] = list(shared_entities.keys())
            if not context["context_source"]:
                context["context_source"] = "shared_entities"
        
        # If still no context, will need retrieval
        if not context["resolved_intent"] and not context["active_topic"]:
            context["requires_retrieval"] = True
            context["context_source"] = "insufficient_memory"
        
        return context
    
    def _resolve_from_previous_turn(
        self,
        latest_message: str,
        continuation_type: str,
        prev_turn: Dict,
        context: Dict
    ) -> Dict:
        """Resolve context from immediate previous turn."""
        # Get previous response/intent
        prev_intent = prev_turn.get("intent", "unknown")
        prev_response = prev_turn.get("response", "")
        prev_entities = prev_turn.get("entities", {})
        
        # Map continuation type to likely intent
        if continuation_type == "affirmative":
            # "yes" likely confirms previous offer/question
            if "pricing" in prev_intent.lower() or "pricing" in prev_response.lower():
                context["resolved_intent"] = "pricing_inquiry_continuation"
                context["active_topic"] = "pricing_details"
                context["requires_retrieval"] = False  # Already have pricing context
            
            elif "demo" in prev_intent.lower() or "demo" in prev_response.lower():
                context["resolved_intent"] = "demo_request_confirmation"
                context["active_topic"] = "demo_scheduling"
                context["requires_retrieval"] = False
            
            elif "feature" in prev_intent.lower() or "feature" in prev_response.lower():
                context["resolved_intent"] = "feature_inquiry_continuation"
                context["active_topic"] = "product_features"
                context["requires_retrieval"] = False
            
            else:
                # Generic affirmation
                context["resolved_intent"] = "affirmative_continuation"
                context["active_topic"] = prev_intent
                context["requires_retrieval"] = False
        
        elif continuation_type == "interest":
            # "tell me more", "interested"
            context["resolved_intent"] = "interest_continuation"
            context["active_topic"] = prev_intent
            context["requires_retrieval"] = True  # Need more details
        
        elif continuation_type == "question":
            # Short question - inherit context from previous
            context["resolved_intent"] = self._map_question_to_intent(latest_message, prev_intent)
            context["active_topic"] = prev_intent
            context["requires_retrieval"] = True
        
        elif continuation_type == "confirmation":
            # "thanks", "got it"
            context["resolved_intent"] = "conversation_closing"
            context["active_topic"] = prev_intent
            context["requires_retrieval"] = False
        
        # Extract entities from previous turn
        if prev_entities:
            context["relevant_entities"] = list(prev_entities.keys()) if isinstance(prev_entities, dict) else prev_entities
        
        return context
    
    def _resolve_from_recent_turns(
        self,
        latest_message: str,
        continuation_type: str,
        recent_turns: List[Dict],
        context: Dict
    ) -> Dict:
        """Resolve context from last 2-3 turns."""
        # Aggregate topics and entities
        topics = []
        entities = []
        intents = []
        
        for turn in recent_turns:
            intent = turn.get("intent", "unknown")
            if intent != "unknown":
                intents.append(intent)
            
            turn_entities = turn.get("entities", {})
            if turn_entities:
                if isinstance(turn_entities, dict):
                    entities.extend(turn_entities.keys())
                else:
                    entities.extend(turn_entities)
        
        # Find dominant topic
        if intents:
            context["active_topic"] = intents[0]  # Most recent
            context["resolved_intent"] = f"{intents[0]}_continuation"
        
        if entities:
            context["relevant_entities"] = list(set(entities))
        
        # Determine if retrieval needed
        if continuation_type in ["interest", "question"]:
            context["requires_retrieval"] = True
        else:
            context["requires_retrieval"] = False
        
        return context
    
    def _map_question_to_intent(self, question: str, prev_intent: str) -> str:
        """Map short question to intent based on keywords."""
        q_lower = question.lower()
        
        if any(word in q_lower for word in ["price", "cost", "how much"]):
            return "pricing_inquiry"
        
        if any(word in q_lower for word in ["when", "delivery", "ship"]):
            return "delivery_inquiry"
        
        if any(word in q_lower for word in ["available", "stock", "in stock"]):
            return "availability_inquiry"
        
        if any(word in q_lower for word in ["feature", "support", "can it", "does it"]):
            return "feature_inquiry"
        
        if any(word in q_lower for word in ["demo", "trial", "test"]):
            return "demo_request"
        
        # Fallback to previous intent
        return f"{prev_intent}_clarification"
    
    def _create_fallback_context(
        self,
        latest_message: str,
        continuation_type: str
    ) -> Dict[str, Any]:
        """Create fallback context when no history exists."""
        return {
            "resolved_intent": "general_inquiry",
            "active_topic": None,
            "relevant_entities": [],
            "conversation_summary": "",
            "requires_retrieval": True,  # No context, need retrieval
            "cached_context": None,
            "continuation_type": continuation_type,
            "context_source": "no_history"
        }
    
    def should_use_cached_retrieval(
        self,
        context: Dict,
        memory: Dict
    ) -> Tuple[bool, Optional[List]]:
        """
        Check if we can reuse cached retrieval results.
        
        Returns: (use_cache, cached_chunks)
        """
        # Check if topic is same as previous
        active_topic = context.get("active_topic")
        last_topic = memory.get("last_topic")
        
        if active_topic and last_topic and active_topic == last_topic:
            # Same topic - check if we have cached chunks
            cached_chunks = memory.get("retrieved_chunks_cache", [])
            if cached_chunks:
                return (True, cached_chunks)
        
        return (False, None)


# Global instance
_resolver: ContextualContinuationResolver = None


def get_continuation_resolver() -> ContextualContinuationResolver:
    """Get global continuation resolver."""
    global _resolver
    if _resolver is None:
        _resolver = ContextualContinuationResolver()
    return _resolver


__all__ = ["ContextualContinuationResolver", "get_continuation_resolver"]
