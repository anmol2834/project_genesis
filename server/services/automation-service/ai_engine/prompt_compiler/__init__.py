"""
Prompt Compiler
================
Converts structured pipeline inputs into a strict, token-optimized LLM prompt.

Public interface:
  PromptBuilder  — main compiler class
  CompiledPrompt — output struct consumed by LLM Engine
  PromptMode     — template variant enum
"""
from .builder import PromptBuilder
from .schema import CompiledPrompt, PromptMode, PromptMetadata

__all__ = ["PromptBuilder", "CompiledPrompt", "PromptMode", "PromptMetadata"]
