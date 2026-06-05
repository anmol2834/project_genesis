"""
Continuation Resolution Engine
==============================
Resolves short conversational continuations like "yes", "okay", "first one", "cheaper one".

This is CRITICAL for enterprise conversational AI.

Examples:
    AI: "Would you like AeroCam X1 pricing?"
    User: "yes"
    → Resolved: intent=pricing, entity="AeroCam X1"
    
    AI: "We have AeroCam X1 and RescueEye. Which interests you?"
    User: "first one"
    → Resolved: entity="AeroCam X1"
    
    AI: "AgriFly Pro costs $15,000. Want a cheaper option?"
    User: "yes cheaper one"
    → Resolved: intent=pricing, constraint=price<15000
"""

import re
import logging
from typing import Optional, Any, Dict
from app.intelligence.models.intelligence_result import (
    ContinuationResolution, Intent
)

logger = logging.getLogger(__name__)


# ── Affirmative Keywords ──────────────────────────────────────────────────────
AFFIRMATIVE_WORDS = {
    # English
    "yes", "yess", "yesss", "yeah", "yea", "yep", "yup", "sure",
    "ok", "okay", "k", "alright", "alrite", "definitely", "absolutely",
    "please", "please do", "go ahead", "sounds good",
    
    # Hindi/Hinglish
    "haan", "ha", "bilkul", "zaroor", "theek", "acha", "accha",
    "sahi", "thik hai", "haan ji", "ji haan"
}

# ── Negative Keywords ─────────────────────────────────────────────────────────
NEGATIVE_WORDS = {
    # English
    "no", "nope", "nah", "not", "dont", "don't", "never",
    "no thanks", "no thank you", "not interested",
    
    # Hindi/Hinglish
    "nahi", "naa", "na", "nahi chahiye", "mat karo"
}

# ── Ordinal References ────────────────────────────────────────────────────────
ORDINAL_PATTERNS = [
    (r"\b(first|1st|one)\b", 0),
    (r"\b(second|2nd|two)\b", 1),
    (r"\b(third|3rd|three)\b", 2),
    (r"\b(fourth|4th|four)\b", 3),
    (r"\b(last|final)\b", -1),
]

# ── Comparative References ────────────────────────────────────────────────────
COMPARATIVE_PATTERNS = {
    "cheaper": {"constraint": "price", "direction": "lower"},
    "less expensive": {"constraint": "price", "direction": "lower"},
    "budget": {"constraint": "price", "direction": "lower"},
    "affordable": {"constraint": "price", "direction": "lower"},
    "sasta": {"constraint": "price", "direction": "lower"},
    "kam price": {"constraint": "price", "direction": "lower"},
    
    "expensive": {"constraint": "price", "direction": "higher"},
    "premium": {"constraint": "price", "direction": "higher"},
    "best": {"constraint": "quality", "direction": "higher"},
    "mehnga": {"constraint": "price", "direction": "higher"},
    
    "faster": {"constraint": "speed", "direction": "higher"},
    "slower": {"constraint": "speed", "direction": "lower"},
    "bigger": {"constraint": "size", "direction": "higher"},
    "smaller": {"constraint": "size", "direction": "lower"},
    "lighter": {"constraint": "weight", "direction": "lower"},
}

# ── Demonstrative References ──────────────────────────────────────────────────
DEMONSTRATIVE_WORDS = {
    "this", "that", "these", "those", "it", "them",
    "yeh", "woh", "ye", "wo", "isko", "usko"
}


class ContinuationResolver:
    """
    Resolves conversational continuations using memory context.
    """
    
    def __init__(self):
        self.affirmative_re = re.compile(
            r"\b(" + "|".join(AFFIRMATIVE_WORDS) + r")\b",
            re.IGNORECASE
        )
        self.negative_re = re.compile(
            r"\b(" + "|".join(NEGATIVE_WORDS) + r")\b",
            re.IGNORECASE
        )
    
    async def resolve(
        self,
        content: str,
        memory: Optional[Any],
        memory_context: Optional[Dict]
    ) -> ContinuationResolution:
        """
        Resolve continuation reference.
        
        Args:
            content: User message
            memory: Thread memory
            memory_context: Enriched memory context
            
        Returns:
            ContinuationResolution with resolved context
        """
        clean = content.strip().lower()
        words = clean.split()
        
        # Not a continuation if too long
        if len(words) > 8:
            return ContinuationResolution(
                is_continuation=False,
                resolved=False,
                original_text=content
            )
        
        # Check if it's a continuation type message
        is_cont = self._is_continuation_message(clean, words)
        
        if not is_cont:
            return ContinuationResolution(
                is_continuation=False,
                resolved=False,
                original_text=content
            )
        
        # Try to resolve based on type
        
        # 1. Affirmative response ("yes", "sure", "okay")
        if self._is_affirmative(clean):
            return await self._resolve_affirmative(
                content, clean, memory, memory_context
            )
        
        # 2. Negative response ("no", "not interested")
        if self._is_negative(clean):
            return await self._resolve_negative(
                content, clean, memory, memory_context
            )
        
        # 3. Ordinal reference ("first one", "second option")
        ordinal_result = self._resolve_ordinal(clean, memory)
        if ordinal_result.resolved:
            return ordinal_result
        
        # 4. Comparative reference ("cheaper one", "faster option")
        comparative_result = self._resolve_comparative(clean, memory)
        if comparative_result.resolved:
            return comparative_result
        
        # 5. Demonstrative reference ("this product", "that service")
        demonstrative_result = self._resolve_demonstrative(clean, memory)
        if demonstrative_result.resolved:
            return demonstrative_result
        
        # 6. Generic continuation ("another", "more", "next")
        generic_result = self._resolve_generic_continuation(clean, memory)
        if generic_result.resolved:
            return generic_result
        
        # Could not resolve - return as continuation but unresolved
        return ContinuationResolution(
            is_continuation=True,
            resolved=False,
            original_text=content,
            last_topic=self._get_last_topic(memory),
            last_intent=self._get_last_intent(memory),
            confidence=0.3,
            source="memory"
        )
    
    # ══════════════════════════════════════════════════════════════════════
    # Detection Methods
    # ══════════════════════════════════════════════════════════════════════
    
    def _is_continuation_message(self, clean: str, words: list) -> bool:
        """Check if message is a continuation."""
        # Very short message
        if len(words) <= 3:
            return True
        
        # Contains affirmative/negative
        if self.affirmative_re.search(clean) or self.negative_re.search(clean):
            return True
        
        # Contains ordinal
        for pattern, _ in ORDINAL_PATTERNS:
            if re.search(pattern, clean):
                return True
        
        # Contains comparative
        if any(comp in clean for comp in COMPARATIVE_PATTERNS.keys()):
            return True
        
        # Contains demonstrative
        if any(demo in clean.split() for demo in DEMONSTRATIVE_WORDS):
            return True
        
        # Generic continuation words
        continuation_words = {
            "another", "more", "next", "continue", "different",
            "other", "else", "aur", "doosra", "dusra"
        }
        if any(word in words for word in continuation_words):
            return True
        
        return False
    
    def _is_affirmative(self, clean: str) -> bool:
        """Check if message is affirmative."""
        return bool(self.affirmative_re.search(clean))
    
    def _is_negative(self, clean: str) -> bool:
        """Check if message is negative."""
        return bool(self.negative_re.search(clean))
    
    # ══════════════════════════════════════════════════════════════════════
    # Resolution Methods
    # ══════════════════════════════════════════════════════════════════════
    
    async def _resolve_affirmative(
        self,
        content: str,
        clean: str,
        memory: Optional[Any],
        memory_context: Optional[Dict]
    ) -> ContinuationResolution:
        """
        Resolve affirmative response.
        
        AI: "Would you like AeroCam X1 pricing?"
        User: "yes"
        → intent=pricing, entity="AeroCam X1"
        """
        if not memory:
            return ContinuationResolution(
                is_continuation=True,
                resolved=False,
                original_text=content,
                reference_type="affirmative",
                confidence=0.5
            )
        
        # Get last question AI asked
        last_question = getattr(memory, "last_question", "")
        last_topic = self._get_last_topic(memory)
        last_intent = self._get_last_intent(memory)
        
        if not last_question and not last_topic:
            return ContinuationResolution(
                is_continuation=True,
                resolved=False,
                original_text=content,
                reference_type="affirmative",
                confidence=0.4
            )
        
        # Parse last question to infer intent
        resolved_intent = None
        resolved_entity = None
        resolved_query = None
        
        if last_question:
            q_lower = last_question.lower()
            
            # Pricing question
            if any(w in q_lower for w in ["price", "cost", "rate", "pricing", "kitna"]):
                resolved_intent = Intent.PRICING
                resolved_query = f"{last_topic} price cost details" if last_topic else "pricing details"
            
            # Feature question
            elif any(w in q_lower for w in ["feature", "spec", "detail", "capabilit"]):
                resolved_intent = Intent.INTEREST
                resolved_query = f"{last_topic} features specifications details" if last_topic else "product details"
            
            # Support question
            elif any(w in q_lower for w in ["support", "help", "contact", "assist"]):
                resolved_intent = Intent.SUPPORT
                resolved_query = f"{last_topic} support contact details" if last_topic else "support details"
            
            # General exploration
            elif any(w in q_lower for w in ["know more", "explore", "learn", "tell"]):
                resolved_intent = Intent.INTEREST
                resolved_query = f"{last_topic} complete details" if last_topic else "more information"
            
            # Default: inherit last intent
            else:
                resolved_intent = self._map_intent(last_intent) if last_intent else Intent.INTEREST
                resolved_query = f"{last_topic} details" if last_topic else "more information"
        
        else:
            # No question, use last intent + topic
            resolved_intent = self._map_intent(last_intent) if last_intent else Intent.INTEREST
            resolved_query = f"{last_topic} details" if last_topic else "more information"
        
        resolved_entity = last_topic if last_topic else None
        
        return ContinuationResolution(
            is_continuation=True,
            resolved=True,
            resolved_intent=resolved_intent,
            resolved_entity=resolved_entity,
            resolved_entity_type="product" if resolved_entity else None,
            resolved_query=resolved_query,
            original_text=content,
            reference_type="affirmative",
            last_topic=last_topic,
            last_intent=last_intent,
            last_question=last_question,
            confidence=0.85,
            source="memory"
        )
    
    async def _resolve_negative(
        self,
        content: str,
        clean: str,
        memory: Optional[Any],
        memory_context: Optional[Dict]
    ) -> ContinuationResolution:
        """
        Resolve negative response.
        
        User: "no" / "not interested"
        → intent=not_interested
        """
        last_topic = self._get_last_topic(memory)
        last_intent = self._get_last_intent(memory)
        
        return ContinuationResolution(
            is_continuation=True,
            resolved=True,
            resolved_intent=Intent.NOT_INTERESTED,
            resolved_entity=last_topic,
            resolved_query="not interested declined",
            original_text=content,
            reference_type="negative",
            last_topic=last_topic,
            last_intent=last_intent,
            confidence=0.90,
            source="memory"
        )
    
    def _resolve_ordinal(
        self,
        clean: str,
        memory: Optional[Any]
    ) -> ContinuationResolution:
        """
        Resolve ordinal reference.
        
        AI: "We have AeroCam X1 and RescueEye. Which interests you?"
        User: "first one"
        → entity="AeroCam X1"
        """
        if not memory:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        # Find ordinal
        ordinal_idx = None
        for pattern, idx in ORDINAL_PATTERNS:
            if re.search(pattern, clean):
                ordinal_idx = idx
                break
        
        if ordinal_idx is None:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        # Get last products shown
        last_products = getattr(memory, "last_products", [])
        
        if not last_products:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        # Resolve index
        try:
            entity = last_products[ordinal_idx]
        except IndexError:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        return ContinuationResolution(
            is_continuation=True,
            resolved=True,
            resolved_intent=Intent.INTEREST,
            resolved_entity=entity,
            resolved_entity_type="product",
            resolved_query=f"{entity} details features specifications",
            original_text=clean,
            reference_type="ordinal",
            last_topic=self._get_last_topic(memory),
            confidence=0.90,
            source="memory"
        )
    
    def _resolve_comparative(
        self,
        clean: str,
        memory: Optional[Any]
    ) -> ContinuationResolution:
        """
        Resolve comparative reference.
        
        User: "cheaper one"
        → constraint=price<current_price
        """
        if not memory:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        # Find comparative
        comparative = None
        for comp, details in COMPARATIVE_PATTERNS.items():
            if comp in clean:
                comparative = details
                break
        
        if not comparative:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        last_topic = self._get_last_topic(memory)
        category = getattr(memory, "last_category", "")
        
        # Build resolved query
        constraint = comparative["constraint"]
        direction = comparative["direction"]
        
        if constraint == "price":
            if direction == "lower":
                resolved_query = f"cheaper budget {category or 'products'} low price"
            else:
                resolved_query = f"premium expensive {category or 'products'} high quality"
        else:
            resolved_query = f"{constraint} {direction} {category or 'products'}"
        
        return ContinuationResolution(
            is_continuation=True,
            resolved=True,
            resolved_intent=Intent.PRICING if constraint == "price" else Intent.INTEREST,
            resolved_entity=category if category else None,
            resolved_entity_type="category" if category else None,
            resolved_query=resolved_query,
            original_text=clean,
            reference_type="comparative",
            last_topic=last_topic,
            confidence=0.80,
            source="memory"
        )
    
    def _resolve_demonstrative(
        self,
        clean: str,
        memory: Optional[Any]
    ) -> ContinuationResolution:
        """
        Resolve demonstrative reference.
        
        User: "this product" / "that service"
        → entity=last_topic
        """
        if not memory:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        # Check if demonstrative present
        has_demonstrative = any(demo in clean.split() for demo in DEMONSTRATIVE_WORDS)
        
        if not has_demonstrative:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        last_topic = self._get_last_topic(memory)
        
        if not last_topic:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        return ContinuationResolution(
            is_continuation=True,
            resolved=True,
            resolved_intent=Intent.INTEREST,
            resolved_entity=last_topic,
            resolved_entity_type="product",
            resolved_query=f"{last_topic} details features specifications",
            original_text=clean,
            reference_type="demonstrative",
            last_topic=last_topic,
            confidence=0.75,
            source="memory"
        )
    
    def _resolve_generic_continuation(
        self,
        clean: str,
        memory: Optional[Any]
    ) -> ContinuationResolution:
        """
        Resolve generic continuation.
        
        User: "another" / "more" / "next"
        → show_more_products
        """
        if not memory:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        continuation_words = ["another", "more", "next", "different", "else", "aur"]
        
        has_continuation = any(word in clean.split() for word in continuation_words)
        
        if not has_continuation:
            return ContinuationResolution(is_continuation=True, resolved=False, original_text=clean)
        
        last_topic = self._get_last_topic(memory)
        category = getattr(memory, "last_category", "")
        
        topic = last_topic or category or "products"
        
        return ContinuationResolution(
            is_continuation=True,
            resolved=True,
            resolved_intent=Intent.INTEREST,
            resolved_entity=category if category else None,
            resolved_entity_type="category" if category else None,
            resolved_query=f"show more {topic} options catalog",
            original_text=clean,
            reference_type="generic_continuation",
            last_topic=last_topic,
            confidence=0.70,
            source="memory"
        )
    
    # ══════════════════════════════════════════════════════════════════════
    # Helper Methods
    # ══════════════════════════════════════════════════════════════════════
    
    def _get_last_topic(self, memory: Optional[Any]) -> Optional[str]:
        """Extract last topic from memory."""
        if not memory:
            return None
        
        # Try multiple fields
        if hasattr(memory, "last_topic") and memory.last_topic:
            return memory.last_topic
        
        if hasattr(memory, "active_entities") and memory.active_entities:
            if "product_name" in memory.active_entities:
                return memory.active_entities["product_name"]
            if "category" in memory.active_entities:
                return memory.active_entities["category"]
        
        if hasattr(memory, "last_products") and memory.last_products:
            return memory.last_products[0]
        
        if hasattr(memory, "last_category") and memory.last_category:
            return memory.last_category
        
        return None
    
    def _get_last_intent(self, memory: Optional[Any]) -> Optional[str]:
        """Extract last intent from memory."""
        if not memory:
            return None
        
        if hasattr(memory, "last_intent") and memory.last_intent:
            return memory.last_intent
        
        return None
    
    def _map_intent(self, intent_str: Optional[str]) -> Intent:
        """Map string intent to Intent enum."""
        if not intent_str:
            return Intent.UNKNOWN
        
        mapping = {
            "interest": Intent.INTEREST,
            "pricing": Intent.PRICING,
            "support": Intent.SUPPORT,
            "question": Intent.QUESTION,
            "follow_up": Intent.FOLLOW_UP,
            "negotiation": Intent.NEGOTIATION,
            "complaint": Intent.COMPLAINT,
            "casual": Intent.CASUAL,
            "not_interested": Intent.NOT_INTERESTED
        }
        
        return mapping.get(intent_str, Intent.UNKNOWN)
