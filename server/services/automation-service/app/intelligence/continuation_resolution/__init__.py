"""
Continuation Resolution Module
================================
Handles short message contextual reasoning and conversation continuity.
"""

from .short_message_detector import ShortMessageDetector, get_short_message_detector
from .contextual_resolver import ContextualContinuationResolver, get_continuation_resolver
from .active_topic_memory import ActiveTopicMemory, get_active_topic_memory

__all__ = [
    "ShortMessageDetector",
    "get_short_message_detector",
    "ContextualContinuationResolver",
    "get_continuation_resolver",
    "ActiveTopicMemory",
    "get_active_topic_memory",
]
