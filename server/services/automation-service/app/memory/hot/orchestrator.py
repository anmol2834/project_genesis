"""
Memory Orchestrator - Stub (unreachable dead code)
===================================================
This file is the legacy hot/orchestrator.py stub.

Task 3 fix: app/memory/__init__.py now exports from
app.memory.orchestrator (the production 8-tier Redis implementation).
This file is no longer reachable via normal imports.

Task 16 fix (R20): removed all sys.path.insert() hacks that pointed to
a non-existent 'automationservice' directory. Those caused
ModuleNotFoundError for 'memory_engine' on every method call.

The class is preserved as a stub so any stale import that somehow
still references this path doesn't crash at import time.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger("automation-service.memory.hot.orchestrator")


class MemoryOrchestrator:
    """
    Stub — use app.memory.orchestrator.MemoryOrchestrator instead.
    This implementation is unreachable; kept only to avoid ImportError
    on any stale direct imports.
    """

    def __init__(self):
        self._hot_store = None
        self._enricher = None
        self._state_engine = None

    async def load_memory(self, thread_id: str, tenant_id: str):
        logger.warning("hot/orchestrator stub called — use app.memory.orchestrator instead")
        return None

    async def save_memory(self, thread_id: str, tenant_id: str, memory) -> bool:
        logger.warning("hot/orchestrator stub called — use app.memory.orchestrator instead")
        return False

    async def enrich_query(self, thread_id, tenant_id, query, keywords, content, memory=None):
        return query, keywords

    async def update_memory(self, thread_id, tenant_id, intent, sub_intent,
                            retrieved_products, category, ai_reply, action, entities=None):
        logger.warning("hot/orchestrator stub called — use app.memory.orchestrator instead")
        return None

    async def generate_snapshot(self, thread_id: str, tenant_id: str) -> Dict[str, Any]:
        return {"context_summary": "No conversation history", "turn_count": 0, "confidence": 0.0}


_orchestrator = None


def get_memory_orchestrator() -> MemoryOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
    return _orchestrator


__all__ = ["MemoryOrchestrator", "get_memory_orchestrator"]
