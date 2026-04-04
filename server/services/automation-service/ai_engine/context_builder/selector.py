"""
Context Builder — Selector
============================
Orchestrates the full context assembly pipeline:

  1. Extract conversation blocks from PreprocessedInput.clean_history
  2. Retrieve knowledge blocks from Qdrant (intent-aware)
  3. Build intent-specific context blocks
  4. Rank all blocks (similarity + recency + type priority)
  5. Deduplicate overlapping blocks
  6. Enforce token budgets
  7. Assemble into SelectedContext for the Prompt Compiler

Public interface (called by orchestrator):
  selector.select(hits, preprocessed)           ← legacy call (hits=[])
  selector.select_full(preprocessed, intent_result, policy_decision)  ← full call

The orchestrator currently calls select(hits, preprocessed) with hits=[].
The selector detects this and triggers full intent-aware retrieval internally.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from .schema import (
    ContextBlock, ContextResult, ContextSource, SelectedContext,
)
from .retriever import VectorRetriever
from .ranker import rank_blocks, deduplicate_blocks, build_recency_map
from .tokenizer import enforce_group_budgets, blocks_to_text, estimate_tokens
from .hybrid_search_engine import get_hybrid_search_engine, NO_CONTEXT
from ..preprocess.processor import PreprocessedInput
from ..schemas.intent_schema import IntentResult, IntentType

logger = logging.getLogger(__name__)

# Similarity threshold — discard Qdrant hits below this
_SCORE_THRESHOLD = 0.40

# Chunk type priority for Qdrant results (lower = higher priority in final assembly)
_CHUNK_TYPE_PRIORITY = {
    "instruction":   1,
    "business_core": 2,
    "tone":          3,
    "use_case":      4,
    "audience":      5,
    "user_data":     2,   # User business data — same priority as business_core
}

# Max conversation messages to include (last N incoming + last N outgoing)
_MAX_INCOMING_MSGS = 3
_MAX_OUTGOING_MSGS = 2

# Total token budget for context (leaves room for prompt template + LLM response)
_DEFAULT_TOKEN_BUDGET = 800

# Intents that need minimal/no knowledge context
_MINIMAL_CONTEXT_INTENTS = {
    IntentType.REPLY,
    IntentType.SPAM,
    IntentType.PROMO,
    IntentType.UNSUBSCRIBE,
    IntentType.OUT_OF_OFFICE,
}


class ContextSelector:
    """
    Assembles the final SelectedContext from all available sources.
    Stateless — safe to share across requests.
    """

    def __init__(self) -> None:
        self._retriever = VectorRetriever()

    # ── Public interface (called by orchestrator) ─────────────────────────────

    async def select(
        self,
        hits: List,
        preprocessed: PreprocessedInput,
        intent_result: Optional[IntentResult] = None,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> SelectedContext:
        """
        Assemble SelectedContext from all sources.
        Business context is MANDATORY — pipeline logs a critical warning if missing.
        """
        # ── Step 1: Conversation context ──────────────────────────────────
        conv_blocks = self._extract_conversation_blocks(preprocessed)

        # ── Step 2: Knowledge context (Qdrant) ────────────────────────────
        knowledge_blocks: List[ContextBlock] = []

        if hits:
            knowledge_blocks = self._convert_hits(hits)
        elif intent_result is not None:
            # Intents that never need product/pricing data — skip hybrid search
            _NO_HYBRID_INTENTS = {
                IntentType.REPLY, IntentType.SPAM, IntentType.PROMO,
                IntentType.UNSUBSCRIBE, IntentType.OUT_OF_OFFICE, IntentType.UNKNOWN,
            }
            run_hybrid = intent_result.intent not in _NO_HYBRID_INTENTS

            intent_str = intent_result.intent.value if intent_result else None

            if run_hybrid:
                # Extract last AI reply for entity memory
                last_ai_reply = ""
                if preprocessed.clean_history:
                    for msg in reversed(preprocessed.clean_history):
                        if msg.direction == "outgoing" and msg.clean_content.strip():
                            last_ai_reply = msg.clean_content.strip()[:300]
                            break

                # Run business_context retrieval AND hybrid user_data search in parallel
                business_blocks_task = self._retriever.retrieve_for_intent(
                    user_id=preprocessed.user_id,
                    message_text=preprocessed.clean_incoming_content,
                    intent_result=intent_result,
                    limit=6,
                )
                hybrid_task = get_hybrid_search_engine().search(
                    user_id=preprocessed.user_id,
                    raw_query=preprocessed.clean_incoming_content,
                    intent=intent_str,
                    top_k=3,
                    clean_history=preprocessed.clean_history,
                    last_ai_reply=last_ai_reply,
                )
                business_blocks, hybrid_result = await asyncio.gather(
                    business_blocks_task,
                    hybrid_task,
                    return_exceptions=True,
                )

                # Unpack tuple return (context_string, active_entity)
                if isinstance(hybrid_result, Exception):
                    hybrid_context = NO_CONTEXT
                    active_entity  = None
                elif isinstance(hybrid_result, tuple):
                    hybrid_context, active_entity = hybrid_result
                else:
                    # Fallback: old string return (backward compat)
                    hybrid_context = hybrid_result if hybrid_result else NO_CONTEXT
                    active_entity  = None
            else:
                # Skip hybrid search — only fetch business profile context
                business_blocks = await self._retriever.retrieve_for_intent(
                    user_id=preprocessed.user_id,
                    message_text=preprocessed.clean_incoming_content,
                    intent_result=intent_result,
                    limit=6,
                )
                hybrid_context = NO_CONTEXT
                active_entity  = None
                logger.info(
                    "HybridSearch: skipped for intent=%s | user=%s",
                    intent_str, preprocessed.user_id[:8],
                )

            # Handle exceptions gracefully — never block the pipeline
            if isinstance(business_blocks, Exception):
                logger.warning("Business context retrieval failed: %s", business_blocks)
                business_blocks = []

            knowledge_blocks = list(business_blocks)

            # Inject hybrid search result ONLY when it contains relevant data
            if hybrid_context and hybrid_context != NO_CONTEXT:
                knowledge_blocks.append(ContextBlock(
                    content=hybrid_context,
                    score=0.92,
                    source=ContextSource.QDRANT,
                    chunk_type="user_data",
                ))
                logger.info(
                    "HybridSearch injected %d chars of user data context | user=%s entity=%r",
                    len(hybrid_context), preprocessed.user_id[:8], active_entity,
                )
                print(f"[CONTEXT] HybridSearch: injected user_data block ({len(hybrid_context)} chars) entity={active_entity!r}")
            else:
                logger.info("HybridSearch: no relevant user data | user=%s intent=%s entity=%r",
                            preprocessed.user_id[:8], intent_str, active_entity)
                print(f"[CONTEXT] HybridSearch: NO_CONTEXT for user={preprocessed.user_id[:8]}")

        # ── CRITICAL: Log context health ──────────────────────────────────
        found_types = {b.chunk_type for b in knowledge_blocks}
        missing_mandatory = {"instruction", "business_core", "tone", "use_case"} - found_types
        if missing_mandatory:
            logger.warning(
                "CONTEXT WARNING: Missing mandatory chunk types after retrieval: %s | "
                "user=%s | knowledge_blocks=%d",
                missing_mandatory, preprocessed.user_id[:8], len(knowledge_blocks),
            )
            print(
                f"[CONTEXT] WARNING: Missing chunks {missing_mandatory} for user={preprocessed.user_id[:8]} "
                f"— {len(knowledge_blocks)} blocks retrieved"
            )
        else:
            logger.info(
                "Context OK: all mandatory chunks present | user=%s | blocks=%d",
                preprocessed.user_id[:8], len(knowledge_blocks),
            )
            print(f"[CONTEXT] OK: {len(knowledge_blocks)} blocks | types={sorted(found_types)}")

        # ── Step 3: Intent-specific context blocks ────────────────────────
        intent_blocks = self._build_intent_blocks(preprocessed, intent_result)

        # ── Step 4: Rank all blocks ───────────────────────────────────────
        all_conv      = self._rank_conversation(conv_blocks)
        all_knowledge = self._rank_knowledge(knowledge_blocks)
        all_intent    = intent_blocks

        # ── Step 5: Deduplicate ───────────────────────────────────────────
        all_conv      = deduplicate_blocks(all_conv)
        all_knowledge = deduplicate_blocks(all_knowledge)

        # ── Step 6: Build ContextResult and enforce token budget ──────────
        result = ContextResult(
            conversation_blocks=all_conv,
            knowledge_blocks=all_knowledge,
            intent_blocks=all_intent,
            sources_used=self._collect_sources(all_conv, all_knowledge, all_intent),
            retrieval_skipped=(not knowledge_blocks and intent_result is not None
                               and intent_result.intent not in _MINIMAL_CONTEXT_INTENTS),
        )
        result = enforce_group_budgets(result, token_budget)

        # ── Step 7: Assemble SelectedContext ──────────────────────────────
        selected = self._assemble(result, preprocessed)

        # ── CRITICAL: Verify business context made it through ─────────────
        if not selected.business_instruction and not selected.business_core:
            logger.error(
                "CRITICAL: Business context is EMPTY after assembly! "
                "knowledge_blocks=%d all_knowledge=%d user=%s",
                len(knowledge_blocks), len(all_knowledge), preprocessed.user_id[:8],
            )
            print(
                f"[CONTEXT] CRITICAL: Business context empty after assembly! "
                f"knowledge_blocks={len(knowledge_blocks)} ranked={len(all_knowledge)}"
            )

        return selected

    # ── Conversation extraction ───────────────────────────────────────────────

    def _extract_conversation_blocks(
        self,
        preprocessed: PreprocessedInput,
    ) -> List[ContextBlock]:
        """
        Extract conversation messages as ContextBlocks.
        Includes ALL messages in clean_history (prior messages only — the
        triggering message is handled separately as IncomingMessage).
        Assigns recency-based scores so recent messages are prioritised.
        """
        blocks: List[ContextBlock] = []
        history = preprocessed.clean_history

        if not history:
            return blocks

        # Sort by timestamp string (ISO format sorts correctly lexicographically)
        try:
            sorted_history = sorted(history, key=lambda m: m.timestamp or "")
        except Exception:
            sorted_history = list(history)

        n = len(sorted_history)
        for i, msg in enumerate(sorted_history):
            if not msg.clean_content.strip():
                continue

            # Recency score: most recent = 1.0, oldest = 0.50
            recency = round(0.50 + (i / max(n - 1, 1)) * 0.50, 4) if n > 1 else 1.0

            direction_label = "Lead" if msg.direction == "incoming" else "You (AI)"
            formatted = f"[{direction_label}]: {msg.clean_content.strip()}"

            blocks.append(ContextBlock(
                content=formatted,
                score=recency,
                source=ContextSource.CONVERSATION,
                chunk_type=msg.direction,
            ))

        return blocks

    # ── Knowledge ranking ─────────────────────────────────────────────────────

    def _rank_knowledge(self, blocks: List[ContextBlock]) -> List[ContextBlock]:
        """
        Rank knowledge blocks by type priority + score.
        NOTE: Filter is applied AFTER ranking so scroll blocks (score=0.95)
        are never accidentally dropped before their score is computed.
        Blocks with chunk_type in mandatory set are NEVER filtered out.
        """
        if not blocks:
            return []

        recency_map = build_recency_map(blocks)
        ranked = rank_blocks(blocks, recency_map)

        # Filter: keep mandatory chunk types always, filter others by threshold
        mandatory = {"instruction", "business_core", "tone", "use_case", "audience", "user_data"}
        result = [
            b for b in ranked
            if b.chunk_type in mandatory or b.score >= _SCORE_THRESHOLD
        ]

        # Sort by chunk type priority first, then by score
        def sort_key(b: ContextBlock):
            type_rank = _CHUNK_TYPE_PRIORITY.get(b.chunk_type, 99)
            return (type_rank, -b.score)

        return sorted(result, key=sort_key)

    def _rank_conversation(self, blocks: List[ContextBlock]) -> List[ContextBlock]:
        """Rank conversation blocks by recency (already scored in extraction)."""
        recency_map = build_recency_map(blocks)
        return rank_blocks(blocks, recency_map)

    # ── Intent-specific context ───────────────────────────────────────────────

    def _build_intent_blocks(
        self,
        preprocessed: PreprocessedInput,
        intent_result: Optional[IntentResult],
    ) -> List[ContextBlock]:
        """
        Build intent-specific context blocks from available data.
        These are lightweight blocks derived from the preprocessed input itself,
        not from Qdrant — they provide immediate context for the LLM.
        """
        blocks: List[ContextBlock] = []

        # Add message summary if available (full conversation history condensed)
        if preprocessed.message_summary and preprocessed.message_summary.strip():
            blocks.append(ContextBlock(
                content=f"Conversation summary: {preprocessed.message_summary.strip()}",
                score=0.90,
                source=ContextSource.SUMMARY,
                chunk_type="summary",
            ))

        # Add subject line as context if meaningful
        if preprocessed.subject and preprocessed.subject.strip():
            blocks.append(ContextBlock(
                content=f"Email subject: {preprocessed.subject.strip()}",
                score=0.85,
                source=ContextSource.INTENT,
                chunk_type="subject",
            ))

        return blocks

    # ── Final assembly ────────────────────────────────────────────────────────

    def _assemble(
        self,
        result: ContextResult,
        preprocessed: PreprocessedInput,
    ) -> SelectedContext:
        """
        Flatten ContextResult into the SelectedContext struct
        that the Prompt Compiler expects.
        Also computes data availability flags to prevent hallucination.
        """
        # Extract named knowledge chunks by type
        knowledge_by_type = {b.chunk_type: b.content for b in result.knowledge_blocks}

        business_instruction = knowledge_by_type.get("instruction", "")
        business_core        = knowledge_by_type.get("business_core", "")
        tone_guidance        = knowledge_by_type.get("tone", "")
        use_case_context     = knowledge_by_type.get("use_case", "")

        # User business data (products, pricing, contacts, offers) from hybrid search
        user_data_context = knowledge_by_type.get("user_data", "")

        # Append user_data to business_core so the prompt compiler sees it
        # without requiring any changes to the prompt compiler interface
        if user_data_context:
            if business_core:
                business_core = business_core + "\n\n" + user_data_context
            else:
                business_core = user_data_context

        # Conversation summary from intent blocks
        summary_blocks = [b for b in result.intent_blocks if b.chunk_type == "summary"]
        conversation_summary = summary_blocks[0].content if summary_blocks else preprocessed.message_summary or ""

        # Recent history as readable text
        recent_history_text = blocks_to_text(result.conversation_blocks, separator="\n")

        # Total token estimate
        total_tokens = result.tokens_estimate

        # ── Data availability flags ───────────────────────────────────────
        # CRITICAL: flags are based ONLY on what was actually injected into context.
        # user_data_context is only present when hybrid search found relevant results.
        # Scanning business_instruction/business_core for product keywords is WRONG
        # because those chunks describe the business profile, not actual product data.

        import re as _re

        # has_products/has_pricing/has_services: TRUE only when user_data was injected
        # (user_data comes from hybrid search on user_data_entries collection)
        has_user_data = bool(user_data_context.strip())

        # Universal product detection — any entry title or item name present
        # Looks for: "Relevant ... Data:" header, "- <Title>" lines, or any named item
        has_products = has_user_data and bool(_re.search(
            r"(relevant\s+\w+|^\s*-\s+\w)",
            user_data_context.lower(),
            _re.MULTILINE,
        ))

        # Universal pricing detection — any currency symbol or price keyword
        has_pricing = has_user_data and bool(_re.search(
            r"(₹|€|£|\$|price|pricing|cost|fee|rate|per\s+month|per\s+year|"
            r"\d+\s*inr|\d+\s*usd|\d+\s*eur|\bfree\b|\bpaid\b)",
            user_data_context.lower(),
        ))

        # Contact detection — phone/email in user_data
        has_contact = has_user_data and bool(_re.search(
            r"(\+?\d[\d\s\-]{7,}|[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}|"
            r"phone|email|contact|helpline|whatsapp)",
            user_data_context.lower(),
        ))

        # Services: from explicit service descriptions in business_instruction
        has_services = bool(_re.search(
            r"(services?\s*[:=\-]\s*\w|we\s+offer\s+\w|our\s+services?\s+(include|are)\s+|"
            r"we\s+provide\s+\w|\b(consultation|coaching|training|tour|trip|event|workshop)\b)",
            (business_instruction + " " + business_core).lower(),
        ))
        has_use_cases = bool(use_case_context.strip())

        return SelectedContext(
            business_instruction=business_instruction,
            business_core=business_core,
            tone_guidance=tone_guidance,
            use_case_context=use_case_context,
            conversation_summary=conversation_summary,
            recent_history_text=recent_history_text,
            total_context_tokens=total_tokens,
            full_result=result,
            has_products=has_products,
            has_services=has_services,
            has_pricing=has_pricing,
            has_use_cases=has_use_cases,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _convert_hits(self, hits: List) -> List[ContextBlock]:
        """
        Convert legacy VectorHit objects to ContextBlock.
        Handles both old VectorHit dataclass and new ContextBlock.
        """
        blocks: List[ContextBlock] = []
        for h in hits:
            if isinstance(h, ContextBlock):
                blocks.append(h)
            elif hasattr(h, "content") and hasattr(h, "score"):
                # Legacy VectorHit
                blocks.append(ContextBlock(
                    content=getattr(h, "content", ""),
                    score=getattr(h, "score", 0.0),
                    source=ContextSource.QDRANT,
                    chunk_type=getattr(h, "chunk_type", "unknown"),
                ))
        return blocks

    def _collect_sources(self, *block_lists: List[ContextBlock]) -> List[str]:
        """Collect unique source names from all block lists."""
        sources = set()
        for blocks in block_lists:
            for b in blocks:
                sources.add(b.source.value)
        return sorted(sources)
