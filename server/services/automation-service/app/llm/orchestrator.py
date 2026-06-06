"""
LLM - Orchestrator
==================
ChatGPT Brain #2: Response generation with grounding, hallucination guard,
and a 5-tier fallback chain that prevents pipeline collapse.

Fallback tiers (executed in order on any OpenAI failure):
  T1: OpenAI GPT           — primary path
  T2: Cached intelligence  — Redis pattern cache
  T3: Retrieval-only mode  — structured context without LLM
  T4: Rule-based emergency — deterministic intent templates
  T5: Human handoff        — guaranteed escalation, zero I/O
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from openai import AsyncOpenAI
from app.core.config import get_config
from app.observability import get_logger
from app.core.utf8_enforcement import sanitize_openai_response
from app.llm.providers.fallback_chain import FallbackChain

logger = get_logger(__name__)


class LLMOrchestrator:
    """
    LLM orchestration engine.
    Generates grounded responses and validates against hallucination.
    """
    
    def __init__(self):
        self.config = get_config()
        self.openai_client = AsyncOpenAI(api_key=self.config.get_openai_api_key())
        self.model = self.config.shared.OPENAI_MODEL
        self.max_tokens = 500
        # Lazy-initialised; needs redis which is available after startup
        self._fallback_chain: Optional[FallbackChain] = None

    def _get_fallback_chain(self) -> FallbackChain:
        """Return (and lazily create) the multi-tier fallback chain."""
        if self._fallback_chain is None:
            try:
                from app.core.resource_management import get_resource_manager
                redis = get_resource_manager().get_redis()
            except Exception:
                redis = None
            self._fallback_chain = FallbackChain(
                openai_client=self.openai_client,
                redis_client=redis,
                model=self.model,
                max_tokens=self.max_tokens,
            )
        return self._fallback_chain
    
    async def generate_response(
        self,
        intelligence: Dict[str, Any],
        retrieval: Dict[str, Any],
        memory: Dict[str, Any],
        message_content: str,
        subject: str,
        trace_id: str
    ) -> Dict[str, Any]:
        """
        Generate AI response with L10 fact-graph grounding, hallucination guard,
        and enterprise 5-tier fallback chain (never collapses).

        FLOW:
        1. Pre-generation grounding validation
        2. L10 Fact graph compression
        3. Grounded prompt builder
        4. Brain #2 generation (with fallback chain: T1→T2→T3→T4→T5)
        5. UTF-8 sanitization
        6. Post-generation hallucination check
        7. Confidence calculation
        """
        import time
        start = time.perf_counter()

        try:
            from app.llm.hallucination_guard import get_grounding_validator

            # ── PRE-GENERATION GROUNDING VALIDATION ───────────────────────────
            validator = get_grounding_validator()
            grounding_result = validator.validate(
                chunks=retrieval.get("chunks", []),
                intelligence=intelligence,
                user_id=memory.get("user_id", ""),
                query=message_content,
            )

            if grounding_result.escalate:
                logger.warning(
                    "⚠️ Grounding failed catastrophically | confidence=%.3f accepted=0",
                    grounding_result.overall_confidence,
                    trace_id=trace_id,
                )

            # ── L10: Fact Graph Compression (validated chunks only) ───────────
            prompt, prompt_obs = await self._build_grounded_prompt_async(
                intelligence=intelligence,
                retrieval_chunks=grounding_result.validated_chunks,
                memory=memory,
                message=message_content,
                subject=subject,
                grounding_confidence=grounding_result.overall_confidence,
            )

            # ── Brain #2 Generation (with FALLBACK CHAIN) ────────────────────
            chain = self._get_fallback_chain()
            fallback_result = await chain.execute(
                prompt=prompt,
                intelligence=intelligence,
                retrieval=retrieval,
                memory=memory,
                message_content=message_content,
                subject=subject,
                trace_id=trace_id,
                grounding_result=grounding_result,
            )

            # ── UTF-8 Sanitization (prevent ₹ and other non-ASCII crashes) ───
            response_text = sanitize_openai_response(fallback_result.response_text)

            # ── Post-generation Hallucination Guard (enhanced) ────────────────
            hallucination_check = self._check_hallucination(
                response_text=response_text,
                validated_chunks=grounding_result.validated_chunks,
                rejected_chunks=grounding_result.rejected_chunks,
                intelligence=intelligence,
                grounding_result=grounding_result,
            )

            # ── Confidence Calculation ────────────────────────────────────────
            confidence = self._calculate_generation_confidence(
                retrieval_confidence=retrieval["retrieval_confidence"],
                grounding_confidence=grounding_result.overall_confidence,
                post_gen_grounding_score=hallucination_check["grounding_score"],
                intent_confidence=(
                    intelligence.get("confidence", 0.5)
                    if isinstance(intelligence, dict)
                    else getattr(
                        getattr(intelligence, "conversation_analysis", None),
                        "intent_confidence", 0.5
                    )
                ),
                fallback_confidence=fallback_result.confidence,
            )

            elapsed = (time.perf_counter() - start) * 1000

            result = {
                "response_text":         response_text,
                "confidence":            confidence,
                "hallucination_detected": hallucination_check["hallucination_detected"],
                "grounding_score":       hallucination_check["grounding_score"],
                "tokens_used":           fallback_result.tokens_used,
                "generation_latency_ms": elapsed,
                "model":                 fallback_result.model,
                # Fallback chain metadata (for observability & escalation)
                "fallback_tier":         fallback_result.tier_used,
                "fallback_tier_name":    fallback_result.tier_name,
                "fallback_error_chain":  fallback_result.error_chain,
                "escalate_to_human":     fallback_result.escalate_to_human,
                # Prompt observability (from PromptRouter)
                "prompt_route":          prompt_obs.get("prompt_route", ""),
                "prompt_tokens_est":     prompt_obs.get("prompt_tokens_est", 0),
                "fact_graph_sections":   prompt_obs.get("fact_graph_sections", 0),
                "compression_ratio":     prompt_obs.get("compression_ratio", 1.0),
                "prompt_layers":         prompt_obs.get("layers_applied", []),
                # Pre-generation grounding
                "pre_gen_grounding": {
                    "overall_confidence":  grounding_result.overall_confidence,
                    "accepted_chunks":      grounding_result.accepted_count,
                    "rejected_chunks":      grounding_result.rejected_count,
                    "pricing_conflicts":    len(grounding_result.pricing_conflicts),
                    "tenant_violations":    grounding_result.tenant_violations,
                    "category_violations":  grounding_result.category_violations,
                    "escalate":             grounding_result.escalate or fallback_result.escalate_to_human,
                },
            }

            logger.info(
                "Response generated | confidence=%.2f tier=%d(%s) grounding_pre=%.2f "
                "grounding_post=%.2f hallucination=%s accepted=%d rejected=%d tokens=%d",
                confidence, fallback_result.tier_used, fallback_result.tier_name,
                grounding_result.overall_confidence,
                hallucination_check["grounding_score"],
                hallucination_check["hallucination_detected"],
                grounding_result.accepted_count, grounding_result.rejected_count,
                fallback_result.tokens_used, trace_id=trace_id,
            )

            return result

        except Exception as e:
            # Catastrophic failure — should never happen (T5 has no I/O)
            logger.error("Response generation catastrophic failure: %s", e,
                         trace_id=trace_id, exc_info=True)
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "response_text":         "We apologize, but we're experiencing technical difficulties. A team member will assist you shortly.",
                "confidence":            0.05,
                "hallucination_detected": False,
                "grounding_score":       0.0,
                "tokens_used":           0,
                "generation_latency_ms": elapsed,
                "error":                 str(e),
                "fallback_tier":         6,
                "fallback_tier_name":    "catastrophic_failure",
                "fallback_error_chain":  [str(e)],
                "escalate_to_human":     True,
                "prompt_route":          "catastrophic",
                "prompt_tokens_est":     0,
                "fact_graph_sections":   0,
                "compression_ratio":     1.0,
                "prompt_layers":         [],
                "pre_gen_grounding":     {"escalate": True},
            }
    
    async def _build_grounded_prompt_async(
        self,
        intelligence: Any,
        retrieval_chunks: List[Dict],
        memory: Dict,
        message: str,
        subject: str,
        grounding_confidence: float,
    ) -> tuple[str, dict]:
        """
        Build grounded prompt using PromptRouter (modular) + L10 Fact Graph.

        Returns (assembled_prompt_str, prompt_observability_dict)

        NEVER injects raw chunks — all context flows through:
          validated_chunks → FactGraphCompressor → PromptRouter
        """
        from app.llm.grounding.fact_graph_compressor import get_fact_graph_compressor
        from app.llm.prompt_builder import get_prompt_router

        compressor   = get_fact_graph_compressor()
        prompt_router = get_prompt_router()
        user_id      = memory.get("user_id", "")

        # ── L10: Fact Graph Compression ───────────────────────────────────
        try:
            int_dict = intelligence if isinstance(intelligence, dict) else (
                intelligence.__dict__ if hasattr(intelligence, "__dict__") else {}
            )
            fact_graph = await compressor.compress_to_fact_graph(
                retrieval_chunks=retrieval_chunks,
                intelligence=int_dict,
                user_id=user_id,
                grounding_confidence=grounding_confidence,
            )
        except Exception as e:
            logger.warning("Fact graph compression failed: %s", e)
            fact_graph = None

        # ── Format fact graph → context string ───────────────────────────
        if fact_graph and (
            fact_graph.get("products") or fact_graph.get("pricing")
            or fact_graph.get("support") or fact_graph.get("features")
            or fact_graph.get("policies")
        ):
            fact_graph_context = compressor.format_for_llm(fact_graph)
        elif retrieval_chunks:
            fact_graph_context = "\n\n".join(
                f"[{i}] {c.get('content', '')[:400]}"
                for i, c in enumerate(retrieval_chunks[:3], 1)
                if c.get("content")
            ) or "No specific context available."
        else:
            fact_graph_context = "No specific verified information available for this query."

        # ── Detect price conflicts for risk layer ─────────────────────────
        has_price_conflict = bool(
            fact_graph and any(p.get("price_conflict") for p in fact_graph.get("products", []))
        )

        # ── PromptRouter: assemble layered prompt ─────────────────────────
        build_result = prompt_router.build(
            intelligence=intelligence,
            fact_graph_context=fact_graph_context,
            memory=memory,
            message=message,
            subject=subject,
            grounding_confidence=grounding_confidence,
            has_price_conflict=has_price_conflict,
        )

        # ── Final OpenAI messages format ──────────────────────────────────
        # system = full layered prompt, user = customer message
        final_prompt = (
            build_result.system_prompt
            + "\n\n---\nCUSTOMER MESSAGE:\n"
            + build_result.user_message
            + "\n\nYour response:"
        )

        prompt_obs = {
            "prompt_route":        build_result.prompt_route,
            "prompt_tokens_est":   build_result.estimated_total_tokens,
            "fact_graph_sections": build_result.fact_graph_sections,
            "compression_ratio":   build_result.compression_ratio,
            "removed_duplicates":  build_result.removed_duplicates,
            "layers_applied":      build_result.layers_applied,
            "role_selected":       build_result.role_selected,
            "has_risk_warning":    build_result.has_risk_warning,
            "multilingual":        build_result.has_multilingual,
        }

        return final_prompt, prompt_obs
    
    async def _call_openai_generation(
        self,
        prompt: str,
        trace_id: str
    ) -> tuple[str, int]:
        """Call OpenAI for response generation (used internally by FallbackChain T1)."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=self.max_tokens,
                timeout=30.0,
            )
            # UTF-8 sanitize — ensures ₹ and other non-ASCII survive logging/DB writes
            response_text = sanitize_openai_response(
                response.choices[0].message.content.strip()
            )
            tokens_used = response.usage.total_tokens
            return response_text, tokens_used

        except Exception as e:
            logger.error("OpenAI generation failed: %s", e, trace_id=trace_id)
            raise
    
    def _check_hallucination(
        self,
        response_text: str,
        validated_chunks: List[Dict],
        rejected_chunks: List[Dict],
        intelligence: Any,
        grounding_result: Any,
    ) -> Dict[str, Any]:
        """
        Post-generation hallucination check.

        Grounding score seeded from pre-gen validation (most reliable signal).
        Word-overlap is a secondary adjustment, never the sole arbiter.

        Hallucination is only flagged when confirmed violations exist:
        - Response invents specific $prices with NO price in ANY context
        - Response makes specific entity claims with ZERO context supporting them
        A generic helpful greeting/engagement response is NEVER hallucination.
        """
        # Build context from validated chunks first; fall back to rejected
        # (reject on score, not on tenant — all rejected chunks are same-tenant)
        context_chunks = validated_chunks
        if not context_chunks and rejected_chunks:
            context_chunks = [c for c in rejected_chunks if c.get("content", "")]

        all_context = " ".join(
            c.get("content", "") for c in (validated_chunks + rejected_chunks)
        ).lower()
        context_text = " ".join(
            chunk.get("content", "") for chunk in context_chunks
        ).lower()

        response_lower = response_text.lower()
        violations: List[str] = []

        # Pattern 1: Specific price claims with NO price in any retrieved context
        if "$" in response_text and "$" not in all_context:
            violations.append("invented_pricing")

        # Pattern 2: Specific product-name claims with zero context when context exists
        hallucination_keywords = ["our price is", "costs $", "we charge", "launching on", "released in"]
        if all_context and any(kw in response_lower for kw in hallucination_keywords):
            # Only a violation if the relevant product/price is not backed by any context
            if not any(kw.replace(" ", "") in all_context.replace(" ", "") for kw in hallucination_keywords):
                violations.append("specific_claims_without_context")

        # ── Grounding score ──────────────────────────────────────────────────
        # Primary signal: use pre-gen grounding confidence when chunks were validated
        # (it is the authoritative chunk-level quality signal from GroundingValidator)
        accepted = grounding_result.accepted_count if grounding_result else 0
        pre_gen_conf = grounding_result.overall_confidence if grounding_result else 0.0

        if accepted > 0:
            # Validated chunks exist — anchor on pre-gen confidence
            # Apply a small word-overlap adjustment (max ±0.10) as secondary signal
            response_words = set(response_lower.split())
            context_words  = set(context_text.split())
            if response_words and context_words:
                overlap = len(response_words & context_words) / len(response_words)
                adjustment = (overlap - 0.10) * 0.10   # small ±0.10 band
            else:
                adjustment = 0.0
            grounding_score = min(0.95, max(0.40, pre_gen_conf + adjustment))
        elif context_chunks:
            # Only rejected chunks available — compute overlap but be generous
            response_words = set(response_lower.split())
            context_words  = set(context_text.split())
            if response_words and context_words:
                overlap = len(response_words & context_words) / len(response_words)
                grounding_score = min(0.75, 0.45 + overlap * 0.35)
            else:
                grounding_score = 0.45
        else:
            # Truly no context at all
            grounding_score = 0.45

        if violations:
            grounding_score = min(grounding_score, 0.40)

        # Hallucination only when confirmed violations exist OR zero-context + specific claims
        # A helpful engagement response with no violations is NEVER hallucination
        hallucination_detected = bool(violations)

        return {
            "hallucination_detected": hallucination_detected,
            "grounding_score":       grounding_score,
            "violations":            violations,
        }
    
    def _calculate_generation_confidence(
        self,
        retrieval_confidence: float,
        grounding_confidence: float,
        post_gen_grounding_score: float,
        intent_confidence: float,
        fallback_confidence: float = 1.0,
    ) -> float:
        """
        Calculate overall generation confidence (pre+post grounding aware).
        fallback_confidence penalizes results from lower tiers (T2→T5 < 1.0).
        """
        base = (
            retrieval_confidence       * 0.25 +
            grounding_confidence       * 0.30 +
            post_gen_grounding_score   * 0.30 +
            intent_confidence          * 0.15
        )
        return min(0.95, max(0.05, base * fallback_confidence))


# Global instance
_llm_orchestrator: Optional[LLMOrchestrator] = None


def get_llm_orchestrator() -> LLMOrchestrator:
    """Get global LLM orchestrator"""
    global _llm_orchestrator
    if _llm_orchestrator is None:
        _llm_orchestrator = LLMOrchestrator()
    return _llm_orchestrator


__all__ = ["LLMOrchestrator", "get_llm_orchestrator"]
