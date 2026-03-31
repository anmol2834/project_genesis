"""
Confidence Engine
==================
Computes the final fused confidence score for the ACRE pipeline.

Public interface:
  ConfidenceScorer  — main scorer class
  ConfidenceScore   — output dataclass
  ConfidenceLevel   — HIGH / MEDIUM / LOW enum
"""
from .scorer import ConfidenceScorer
from .schema import ConfidenceScore, ConfidenceLevel, SignalBreakdown

__all__ = ["ConfidenceScorer", "ConfidenceScore", "ConfidenceLevel", "SignalBreakdown"]
