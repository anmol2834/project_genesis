"""
Context Builder
================
RAG-based context assembly for the ACRE pipeline.

Public interface:
  VectorRetriever  — Qdrant retrieval with intent-aware query biasing
  ContextSelector  — full context assembly pipeline
  SelectedContext  — output struct consumed by Prompt Compiler
  ContextBlock     — scored context unit
  ContextResult    — structured output with metadata
"""
from .retriever import VectorRetriever
from .selector import ContextSelector
from .schema import SelectedContext, ContextBlock, ContextResult, ContextSource

__all__ = [
    "VectorRetriever",
    "ContextSelector",
    "SelectedContext",
    "ContextBlock",
    "ContextResult",
    "ContextSource",
]
