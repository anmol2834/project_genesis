"""
LLM Multi-Tier Fallback Chain
==============================
Enterprise 5-tier fallback system. NEVER allows pipeline collapse.

Tier 1: OpenAI GPT           — primary generation
Tier 2: Cached intelligence  — pattern-matched responses from Redis cache
Tier 3: Retrieval-only mode  — return structured context without LLM generation
Tier 4: Rule-based emergency — deterministic intent→template responses
Tier 5: Human handoff        — escalate with full context, guaranteed delivery

Each tier is attempted in order. A tier is skipped only on hard failure,
NOT on "low confidence". Tier 5 is infallible by design (no I/O path to fail).
"""
import asyncio
import hashlib
import json
import sys
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result contract
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FallbackResult:
    """Unified result returned regardless of which tier handled the request."""
    response_text: str
    confidence: float
    tier_used: int
    tier_name: str
    tokens_used: int = 0
    generation_latency_ms: float = 0.0
    hallucination_detected: bool = False
    grounding_score: float = 0.0
    escalate_to_human: bool = False
    escalation_reason: str = ""
    error_chain: List[str] = field(default_factory=list)
    # mirrors LLMOrchestrator result keys for drop-in compatibility
    model: str = ""
    pre_gen_grounding: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_text":          self.response_text,
            "confidence":             self.confidence,
            "tier_used":              self.tier_used,
            "tier_name":              self.tier_name,
            "tokens_used":            self.tokens_used,
            "generation_latency_ms":  self.generation_latency_ms,
            "hallucination_detected": self.hallucination_detected,
            "grounding_score":        self.grounding_score,
            "escalate_to_human":      self.escalate_to_human,
            "escalation_reason":      self.escalation_reason,
            "error_chain":            self.error_chain,
            "model":                  self.model,
            "pre_gen_grounding":      self.pre_gen_grounding,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tier 4 — rule-based templates (pure in-memory, zero I/O)
# ─────────────────────────────────────────────────────────────────────────────

_EMERGENCY_TEMPLATES: Dict[str, str] = {
    "pricing_inquiry": (
        "Thank you for reaching out about pricing. "
        "Our team will provide you with accurate pricing details shortly. "
        "We appreciate your patience."
    ),
    "product_inquiry": (
        "Thank you for your interest in our products. "
        "A specialist will follow up with detailed product information shortly."
    ),
    "complaint": (
        "We sincerely apologize for any inconvenience caused. "
        "Your concern has been flagged as high priority and a team member "
        "will personally reach out to resolve this promptly."
    ),
    "refund_request": (
        "Thank you for contacting us regarding your refund request. "
        "Our billing team will review your case and respond within 1–2 business days."
    ),
    "technical_support": (
        "Thank you for reaching out about a technical issue. "
        "Our technical support team has been notified and will assist you shortly."
    ),
    "general_inquiry": (
        "Thank you for contacting us. "
        "We have received your message and a team member will respond shortly."
    ),
    "order_status": (
        "Thank you for your inquiry about your order. "
        "Our team will check your order status and update you promptly."
    ),
    "cancellation": (
        "We have received your cancellation request. "
        "A team member will process this and confirm the details with you shortly."
    ),
    # Catch-all fallback
    "_default": (
        "Thank you for contacting us. "
        "We have received your message and will respond as soon as possible. "
        "We apologize for any inconvenience."
    ),
}


def _get_emergency_template(intent: str) -> str:
    """Return the closest matching emergency template for a given intent."""
    intent_lower = (intent or "").lower().replace(" ", "_")
    # Direct match
    if intent_lower in _EMERGENCY_TEMPLATES:
        return _EMERGENCY_TEMPLATES[intent_lower]
    # Substring match
    for key, template in _EMERGENCY_TEMPLATES.items():
        if key != "_default" and key in intent_lower:
            return template
    return _EMERGENCY_TEMPLATES["_default"]


# ─────────────────────────────────────────────────────────────────────────────
# FallbackChain
# ─────────────────────────────────────────────────────────────────────────────

class FallbackChain:
    """
    Executes Tier1→Tier5 in order. Each tier is wrapped in its own
    try/except so a failure in one tier triggers the next.

    Usage:
        chain = FallbackChain(openai_client, redis_client, model)
        result = await chain.execute(prompt, context)
    """

    def __init__(
        self,
        openai_client,
        redis_client,
        model: str,
        max_tokens: int = 500,
    ):
        self._openai   = openai_client
        self._redis    = redis_client
        self._model    = model
        self._max_tok  = max_tokens

    # ── public entry point ────────────────────────────────────────────────────

    async def execute(
        self,
        prompt: str,
        intelligence: Dict[str, Any],
        retrieval: Dict[str, Any],
        memory: Dict[str, Any],
        message_content: str,
        subject: str,
        trace_id: str,
        grounding_result: Any = None,
    ) -> FallbackResult:
        """
        Execute the fallback chain. Returns a FallbackResult from whichever
        tier first succeeds. Tier 5 (human handoff) is always reached when
        all prior tiers fail — it cannot itself fail.
        """
        errors: List[str] = []
        intent = self._extract_intent(intelligence)
        start  = time.perf_counter()

        # ── Tier 1: OpenAI GPT ────────────────────────────────────────────
        try:
            result = await self._tier1_openai(prompt, trace_id, start)
            result.error_chain = errors
            logger.info("FallbackChain: Tier 1 (OpenAI) succeeded | trace=%s", trace_id)
            return result
        except Exception as exc:
            err = f"T1_OpenAI: {_safe_str(exc)}"
            errors.append(err)
            logger.warning("FallbackChain: Tier 1 failed — %s | trace=%s", err, trace_id)

        # ── Tier 2: Cached Intelligence Patterns ─────────────────────────
        try:
            result = await self._tier2_cached_intelligence(
                message_content, intent, memory, retrieval, trace_id, start
            )
            if result:
                result.error_chain = errors
                logger.warning(
                    "FallbackChain: Tier 2 (cache) serving | trace=%s", trace_id
                )
                return result
        except Exception as exc:
            err = f"T2_Cache: {_safe_str(exc)}"
            errors.append(err)
            logger.warning("FallbackChain: Tier 2 failed — %s | trace=%s", err, trace_id)

        # ── Tier 3: Retrieval-only Response Mode ──────────────────────────
        try:
            result = self._tier3_retrieval_only(
                retrieval, message_content, subject, intent, start
            )
            if result:
                result.error_chain = errors
                logger.warning(
                    "FallbackChain: Tier 3 (retrieval-only) serving | trace=%s", trace_id
                )
                return result
        except Exception as exc:
            err = f"T3_Retrieval: {_safe_str(exc)}"
            errors.append(err)
            logger.warning("FallbackChain: Tier 3 failed — %s | trace=%s", err, trace_id)

        # ── Tier 4: Rule-based Emergency Response ────────────────────────
        try:
            result = self._tier4_rule_based(intent, start)
            result.error_chain = errors
            logger.warning(
                "FallbackChain: Tier 4 (rule-based) serving | intent=%s trace=%s",
                intent, trace_id
            )
            return result
        except Exception as exc:
            err = f"T4_Rules: {_safe_str(exc)}"
            errors.append(err)
            logger.error(
                "FallbackChain: Tier 4 failed (should never happen) — %s | trace=%s",
                err, trace_id
            )

        # ── Tier 5: Human Handoff (infallible) ───────────────────────────
        result = self._tier5_human_handoff(
            message_content, subject, intent, errors, memory, trace_id, start
        )
        logger.error(
            "FallbackChain: ALL tiers failed — Tier 5 human handoff | "
            "errors=%s trace=%s", errors, trace_id
        )
        return result

    # ── Tier 1 ────────────────────────────────────────────────────────────────

    async def _tier1_openai(
        self, prompt: str, trace_id: str, start: float
    ) -> FallbackResult:
        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=self._max_tok,
            timeout=30.0,
        )
        text   = response.choices[0].message.content.strip()
        tokens = response.usage.total_tokens
        return FallbackResult(
            response_text=text,
            confidence=0.85,
            tier_used=1,
            tier_name="openai_gpt",
            tokens_used=tokens,
            generation_latency_ms=(time.perf_counter() - start) * 1000,
            grounding_score=0.85,
            model=self._model,
            pre_gen_grounding={"escalate": False},
        )

    # ── Tier 2 ────────────────────────────────────────────────────────────────

    async def _tier2_cached_intelligence(
        self,
        message: str,
        intent: str,
        memory: Dict[str, Any],
        retrieval: Dict[str, Any],
        trace_id: str,
        start: float,
    ) -> Optional[FallbackResult]:
        """Look up cached response pattern from Redis by intent+query fingerprint."""
        if not self._redis:
            return None

        user_id    = memory.get("user_id", "unknown")
        cache_key  = _make_cache_key("llm_pattern", user_id, intent, message[:120])

        raw = await self._redis.get(cache_key)
        if not raw:
            # Also try intent-only (broader pattern)
            broad_key = _make_cache_key("llm_pattern_intent", user_id, intent)
            raw = await self._redis.get(broad_key)

        if not raw:
            return None

        cached: Dict[str, Any] = json.loads(raw)
        text = cached.get("response_text", "")
        if not text:
            return None

        return FallbackResult(
            response_text=text,
            confidence=0.65,
            tier_used=2,
            tier_name="cached_intelligence",
            tokens_used=0,
            generation_latency_ms=(time.perf_counter() - start) * 1000,
            grounding_score=cached.get("grounding_score", 0.6),
            model="cache",
            pre_gen_grounding={"escalate": False},
        )

    # ── Tier 3 ────────────────────────────────────────────────────────────────

    def _tier3_retrieval_only(
        self,
        retrieval: Dict[str, Any],
        message: str,
        subject: str,
        intent: str,
        start: float,
    ) -> Optional[FallbackResult]:
        """
        Synthesize a response directly from retrieved chunks — no LLM call.
        Presents factual bullet-points from the top-scored chunks.
        """
        chunks: List[Any] = retrieval.get("chunks", [])
        if not chunks:
            return None

        # Take top-3 highest-scored chunks
        def _score(c: Any) -> float:
            return float(c.get("score", 0) if isinstance(c, dict) else getattr(c, "score", 0))

        top = sorted(chunks, key=_score, reverse=True)[:3]

        facts = []
        for c in top:
            content = (
                c.get("content", "") if isinstance(c, dict)
                else getattr(c, "content", "")
            )
            if content and content.strip():
                facts.append(content.strip()[:300])

        if not facts:
            return None

        intro = (
            f"Regarding your inquiry about {subject or intent or 'your request'}, "
            "here is the relevant information we have on file:"
        )
        body = "\n\n".join(f"• {f}" for f in facts)
        closing = (
            "\n\nIf you need further clarification or this does not fully address "
            "your question, a team member will follow up with you shortly."
        )
        response_text = f"{intro}\n\n{body}{closing}"

        avg_score = sum(_score(c) for c in top) / len(top)

        return FallbackResult(
            response_text=response_text,
            confidence=min(0.60, avg_score * 0.85),
            tier_used=3,
            tier_name="retrieval_only",
            tokens_used=0,
            generation_latency_ms=(time.perf_counter() - start) * 1000,
            grounding_score=avg_score,
            model="retrieval_only",
            pre_gen_grounding={"escalate": False},
        )

    # ── Tier 4 ────────────────────────────────────────────────────────────────

    def _tier4_rule_based(self, intent: str, start: float) -> FallbackResult:
        """Return a deterministic rule-based template. Zero I/O — cannot fail."""
        text = _get_emergency_template(intent)
        return FallbackResult(
            response_text=text,
            confidence=0.40,
            tier_used=4,
            tier_name="rule_based_emergency",
            tokens_used=0,
            generation_latency_ms=(time.perf_counter() - start) * 1000,
            grounding_score=0.40,
            model="rule_based",
            pre_gen_grounding={"escalate": False},
        )

    # ── Tier 5 ────────────────────────────────────────────────────────────────

    def _tier5_human_handoff(
        self,
        message: str,
        subject: str,
        intent: str,
        errors: List[str],
        memory: Dict[str, Any],
        trace_id: str,
        start: float,
    ) -> FallbackResult:
        """
        Guaranteed human handoff. Constructs the customer-facing acknowledgement
        and sets escalate_to_human=True so the caller (HandoffOrchestrator)
        immediately routes to a human agent queue.

        This method contains ONLY pure Python — no I/O, no external calls.
        It is structurally infallible.
        """
        user_id = memory.get("user_id", "unknown")
        ack_text = (
            "Thank you for reaching out. We want to ensure you receive the best "
            "possible assistance. A member of our team will personally review "
            "your message and respond to you shortly.\n\n"
            "We apologize for any inconvenience and appreciate your patience."
        )
        return FallbackResult(
            response_text=ack_text,
            confidence=0.10,
            tier_used=5,
            tier_name="human_handoff",
            tokens_used=0,
            generation_latency_ms=(time.perf_counter() - start) * 1000,
            grounding_score=0.0,
            escalate_to_human=True,
            escalation_reason=(
                f"All AI tiers exhausted. Errors: {'; '.join(errors[:3])}"
                if errors else "All AI tiers exhausted"
            ),
            model="human",
            pre_gen_grounding={"escalate": True},
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_intent(intelligence: Any) -> str:
        if isinstance(intelligence, dict):
            return intelligence.get("intent", "general_inquiry")
        analysis = getattr(intelligence, "conversation_analysis", None)
        if analysis:
            return getattr(analysis, "intent", "general_inquiry")
        return "general_inquiry"


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_cache_key(*parts: str) -> str:
    fingerprint = hashlib.sha256(
        ":".join(str(p) for p in parts).encode("utf-8")
    ).hexdigest()[:24]
    return f"llm_fallback:{fingerprint}"


def _safe_str(exc: Exception) -> str:
    """Convert exception to a safe ASCII-clean string (never crashes)."""
    try:
        return str(exc).encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        return repr(type(exc))


__all__ = ["FallbackChain", "FallbackResult"]
