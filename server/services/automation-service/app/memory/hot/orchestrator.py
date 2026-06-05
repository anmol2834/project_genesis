"""
Memory Orchestrator - Central Memory Coordinator
=================================================
Main integration point for all memory operations.
"""
from __future__ import annotations
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger("automation-service.memory.orchestrator")


class MemoryOrchestrator:
    """
    Central memory coordinator - main API for pipeline integration.
    
    Integrates: hot storage, enrichment, state machine, caching.
    Performance target: <10ms orchestration overhead
    """
    
    def __init__(self):
        """Initialize with lazy-loaded components"""
        self._hot_store = None
        self._enricher = None
        self._state_engine = None
    
    
    async def load_memory(
        self,
        thread_id: str,
        tenant_id: str
    ):
        """
        Load hot memory from Redis (<5ms target).
        
        Returns ThreadMemory object or None if not found.
        Wraps existing automationservice/memory_engine.py functionality.
        """
        try:
            # Import here to avoid circular deps
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'automationservice'))
            from memory_engine import load_memory as load_mem
            
            memory = await load_mem(thread_id)
            
            if memory:
                logger.info(
                    "Memory loaded | thread=%s tenant=%s turns=%d state=%s",
                    thread_id[:12], tenant_id[:8], memory.turn_count, memory.conversation_state
                )
            
            return memory
        except Exception as e:
            logger.debug(f"Memory load failed: {e}")
            return None
    
    
    async def save_memory(
        self,
        thread_id: str,
        tenant_id: str,
        memory
    ) -> bool:
        """
        Save hot memory to Redis (<5ms target).
        
        Wraps existing automationservice/memory_engine.py functionality.
        """
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'automationservice'))
            from memory_engine import save_memory as save_mem
            
            await save_mem(thread_id, memory)
            
            logger.info(
                "Memory saved | thread=%s tenant=%s turns=%d",
                thread_id[:12], tenant_id[:8], memory.turn_count
            )
            return True
        except Exception as e:
            logger.error(f"Memory save failed: {e}")
            return False
    
    
    async def enrich_query(
        self,
        thread_id: str,
        tenant_id: str,
        query: str,
        keywords: List[str],
        content: str,
        memory = None
    ):
        """
        Enrich query with memory context.
        
        Handles:
        - Affirmative responses ("yes" → pricing confirmation)
        - Continuations ("first one" → product name)
        - Topic injection ("price?" → "AeroCam X1 price?")
        
        Returns: (enriched_query, enriched_keywords)
        """
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'automationservice'))
            from memory_engine import enrich_query_with_memory, is_continuation
            
            # Load memory if not provided
            if memory is None:
                memory = await self.load_memory(thread_id, tenant_id)
            
            is_cont = is_continuation(content, memory)
            
            enriched_query, enriched_keywords = enrich_query_with_memory(
                query, keywords, memory, is_cont, content
            )
            
            if enriched_query != query:
                logger.info(
                    "Query enriched | thread=%s orig=%s enriched=%s",
                    thread_id[:12], query[:40], enriched_query[:40]
                )
            
            return enriched_query, enriched_keywords
        except Exception as e:
            logger.debug(f"Query enrichment failed: {e}")
            return query, keywords
    
    
    async def update_memory(
        self,
        thread_id: str,
        tenant_id: str,
        intent: str,
        sub_intent: str,
        retrieved_products: List[str],
        category: str,
        ai_reply: str,
        action: str,
        entities: Dict[str, Any] = None
    ):
        """
        Update memory after turn.
        
        Implements full Memory Intelligence Engine:
        - State machine transitions
        - Intent tracking
        - Entity merging
        - User preference learning
        - Context summarization
        
        Returns updated ThreadMemory
        """
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'automationservice'))
            from memory_engine import (
                load_memory as load_mem,
                save_memory as save_mem,
                update_memory_from_result,
                ThreadMemory
            )
            
            # Load current memory
            memory = await load_mem(thread_id)
            if memory is None:
                memory = ThreadMemory()
            
            # Update memory using existing logic
            memory = update_memory_from_result(
                memory=memory,
                intent=intent,
                sub_intent=sub_intent,
                retrieved_products=retrieved_products,
                category=category,
                ai_reply=ai_reply,
                action=action
            )
            
            # Save updated memory
            await save_mem(thread_id, memory)
            
            logger.info(
                "Memory updated | thread=%s state=%s stage=%s turn=%d",
                thread_id[:12], memory.conversation_state, memory.stage, memory.turn_count
            )
            
            return memory
        except Exception as e:
            logger.error(f"Memory update failed: {e}")
            return None
    
    
    async def generate_snapshot(
        self,
        thread_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Generate memory snapshot for handoff.
        
        Provides compressed context (<2KB) for human agents.
        """
        memory = await self.load_memory(thread_id, tenant_id)
        
        if not memory:
            return {
                "context_summary": "No conversation history",
                "turn_count": 0,
                "confidence": 0.0
            }
        
        snapshot = {
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "context_summary": memory.context_summary,
            "conversation_state": memory.conversation_state,
            "stage": memory.stage,
            "active_entities": memory.active_entities,
            "shown_products": memory.shown_products[-10:],
            "user_preferences": memory.user_preferences,
            "recommended_next_actions": memory.recommended_next_actions,
            "turn_count": memory.turn_count,
            "confidence": memory.confidence,
            "last_ai_reply": memory.last_ai_reply[:200],
            "created_at": datetime.utcnow().isoformat()
        }
        
        logger.info(
            "Snapshot generated | thread=%s turns=%d",
            thread_id[:12], snapshot["turn_count"]
        )
        
        return snapshot


# Singleton instance
_orchestrator = None

def get_memory_orchestrator() -> MemoryOrchestrator:
    """Get singleton memory orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
    return _orchestrator


__all__ = ["MemoryOrchestrator", "get_memory_orchestrator"]
