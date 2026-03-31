"""
ACRE — AI Controlled Response Engine
=====================================
Decision-making AI system for MailFlowAI automation-service.

Pipeline:
  Preprocess → Intent → Confidence → Policy → Context → Prompt → LLM → Validate → Decision

Trigger:
  Called by email-service after a conversation is written to DB.
  Entry point: orchestrator.pipeline.handle_incoming_email_event(conversation_id)

Layers:
  preprocess/       — HTML stripping, normalization, token budgeting
  intent_engine/    — multi-label classification, risk flag detection
  confidence_engine/— weighted confidence scoring
  policy_engine/    — rule-based allow/reject/safe_mode/human_review
  context_builder/  — Qdrant vector retrieval + conversation history assembly
  prompt_compiler/  — template-based prompt assembly with token budget
  llm_engine/       — async LLM provider caller with retry
  validators/       — JSON validation + hallucination/safety checks
  decision_engine/  — final AIEngineOutput construction
  orchestrator/     — pipeline coordinator + public entry point
  schemas/          — Pydantic data contracts (AIEngineInput, AIEngineOutput, IntentResult)
"""

from .orchestrator.pipeline import handle_incoming_email_event, get_pipeline, ACREPipeline

__all__ = ["handle_incoming_email_event", "get_pipeline", "ACREPipeline"]
