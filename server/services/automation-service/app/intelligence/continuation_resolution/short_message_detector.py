"""
Short Message Detection Engine
================================
Detects context-dependent short messages that require conversation history analysis.
"""
from typing import Dict, List, Tuple
import re


class ShortMessageDetector:
    """
    Detects if a message is short, ambiguous, and context-dependent.
    
    Real customers reply with:
    - "yes", "no", "okay", "thanks"
    - "pricing?", "available?", "demo?"
    - "tell me more", "continue", "interested"
    
    These REQUIRE conversation history for understanding.
    """
    
    # Continuation keywords that indicate context dependency
    CONTINUATION_KEYWORDS = {
        # Affirmative
        "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "fine", "alright",
        "agreed", "sounds good", "perfect", "great", "excellent",
        
        # Negative
        "no", "nope", "nah", "not interested", "no thanks",
        
        # Interest signals
        "interested", "tell me more", "continue", "go ahead", "more details",
        "explain", "elaborate", "more info", "learn more",
        
        # Questions needing context
        "pricing?", "price?", "cost?", "how much?", "available?", "when?",
        "why?", "how?", "where?", "demo?", "trial?", "free?",
        
        # Confirmations
        "thanks", "thank you", "got it", "understood", "i see",
        "makes sense", "clear",
        
        # Follow-ups
        "and?", "so?", "then?", "what about", "what if", "can you",
        "do you", "is it", "does it",
        
        # Progression
        "next", "what's next", "proceed", "let's do it", "send details",
        "sign up", "purchase", "buy", "order"
    }
    
    # Single-word contextual messages
    SINGLE_WORD_CONTEXT = {
        "yes", "no", "okay", "sure", "thanks", "interested", "available",
        "pricing", "cost", "demo", "trial", "continue", "more", "explain",
        "why", "how", "when", "where", "maybe", "perhaps"
    }
    
    # Question words that need context
    CONTEXT_QUESTION_WORDS = {
        "how", "when", "where", "why", "which", "what", "who", "whose"
    }
    
    def is_short_contextual_message(
        self,
        message: str,
        threshold_tokens: int = 8,
        threshold_chars: int = 50
    ) -> Tuple[bool, str, float]:
        """
        Detect if message is short and context-dependent.
        
        Returns:
            (is_contextual, reason, confidence)
        """
        message_clean = message.strip().lower()
        
        # Rule 1: Very short messages
        word_count = len(message_clean.split())
        char_count = len(message_clean)
        
        if word_count <= 2:
            return (True, "very_short_message", 0.95)
        
        if word_count <= threshold_tokens and char_count <= threshold_chars:
            # Check if it's a continuation keyword
            if self._contains_continuation_keyword(message_clean):
                return (True, "continuation_keyword", 0.90)
            
            # Check if single word needing context
            if word_count == 1 and message_clean in self.SINGLE_WORD_CONTEXT:
                return (True, "single_word_context", 0.95)
            
            # Check if question needing context
            if self._is_context_question(message_clean):
                return (True, "context_question", 0.85)
            
            # Short but might be standalone
            return (True, "short_ambiguous", 0.70)
        
        # Rule 2: Longer but still ambiguous
        if word_count <= threshold_tokens:
            if self._contains_continuation_keyword(message_clean):
                return (True, "continuation_phrase", 0.80)
            
            if self._is_context_question(message_clean):
                return (True, "context_question_phrase", 0.75)
        
        # Rule 3: Not context-dependent
        return (False, "standalone_message", 0.0)
    
    def _contains_continuation_keyword(self, message: str) -> bool:
        """Check if message contains continuation keywords."""
        message_lower = message.lower()
        
        # Exact match
        if message_lower in self.CONTINUATION_KEYWORDS:
            return True
        
        # Contains match
        for keyword in self.CONTINUATION_KEYWORDS:
            if keyword in message_lower:
                return True
        
        return False
    
    def _is_context_question(self, message: str) -> bool:
        """Check if message is a question needing context."""
        # Ends with question mark
        if message.endswith('?'):
            # Very short question
            if len(message.split()) <= 3:
                return True
            
            # Starts with question word
            first_word = message.split()[0].lower().rstrip('?')
            if first_word in self.CONTEXT_QUESTION_WORDS:
                return True
        
        return False
    
    def get_continuation_type(self, message: str) -> str:
        """
        Classify the type of continuation.
        
        Returns: affirmative, negative, interest, question, confirmation, follow_up
        """
        message_lower = message.strip().lower()
        
        # Affirmative
        affirmative = {"yes", "yeah", "yep", "sure", "okay", "ok", "sounds good", "perfect", "great"}
        if any(word in message_lower for word in affirmative):
            return "affirmative"
        
        # Negative
        negative = {"no", "nope", "nah", "not interested", "no thanks"}
        if any(word in message_lower for word in negative):
            return "negative"
        
        # Interest
        interest = {"interested", "tell me more", "continue", "more details", "learn more"}
        if any(word in message_lower for word in interest):
            return "interest"
        
        # Question
        if message_lower.endswith('?'):
            return "question"
        
        # Confirmation
        confirmation = {"thanks", "thank you", "got it", "understood", "clear"}
        if any(word in message_lower for word in confirmation):
            return "confirmation"
        
        # Follow-up
        follow_up = {"what about", "what if", "can you", "do you", "how about"}
        if any(phrase in message_lower for phrase in follow_up):
            return "follow_up"
        
        return "unknown"


# Global instance
_detector: ShortMessageDetector = None


def get_short_message_detector() -> ShortMessageDetector:
    """Get global short message detector."""
    global _detector
    if _detector is None:
        _detector = ShortMessageDetector()
    return _detector


__all__ = ["ShortMessageDetector", "get_short_message_detector"]
