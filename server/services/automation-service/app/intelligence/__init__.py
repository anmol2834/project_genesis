"""
Intelligence Layer — Public API
================================
Exports the canonical IntelligenceOrchestrator from app.intelligence.orchestrator.

History:
  - Previously only exported get_intelligence_orchestrator (class itself was missing).
  - app/intelligence/enterprise_orchestrator.py is a parallel implementation used
    by some paths; the canonical version used by execution_engine.py is orchestrator.py.
  - Both the class and its factory function are now exported so any import path works:
      from app.intelligence import get_intelligence_orchestrator
      from app.intelligence import IntelligenceOrchestrator
"""

from app.intelligence.orchestrator import (
    IntelligenceOrchestrator,
    get_intelligence_orchestrator,
)

__all__ = [
    "IntelligenceOrchestrator",
    "get_intelligence_orchestrator",
]
