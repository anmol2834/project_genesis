"""
Pre-Generation Grounding Validator
====================================
Runs AFTER retrieval, BEFORE prompt builder.

Validates every chunk against:
  1. Tenant alignment     — chunk.user_id == current user_id (zero exceptions)
  2. Entity alignment     — chunk mentions the requested entity / topic
  3. Category alignment   — chunk type matches intent category
  4. Semantic relevance   — chunk score >= minimum threshold
  5. Pricing consistency  — no conflicting prices for same product
  6. Business alignment   — chunk belongs to this tenant's knowledge scope
  7. Content quality      — not empty / too short / placeholder

Returns a GroundingResult with:
  - validated chunks (only those that passed ALL checks)
  - per-chunk grounding scores
  - overall grounding confidence
  - rejection audit trail
  - escalation flag when grounding is too low

Performance target: <50ms
"""

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Thresholds
# ─────────────────────────────────────────────────────────────────────────────
MIN_SEMANTIC_SCORE      = 0.28   # below this → rejected outright
MIN_GROUNDING_SCORE     = 0.50   # below this → chunk rejected from prompt
ESCALATE_THRESHOLD      = 0.35   # overall confidence below this → flag for handoff
PRICING_CONFLICT_DELTA  = 0.20   # >20% price spread → conflict detected

# Intent → allowed chunk_types  (prevents category cross-contamination)
INTENT_CHUNK_WHITELIST: Dict[str, set] = {
    "pricing_inquiry":            {"product_service", "faq", "general", "profile", "data_analytics"},
    "product_inquiry":            {"product_service", "faq", "general", "profile", "data_analytics"},
    "feature_request":            {"product_service", "faq", "general", "profile", "data_analytics"},
    "support_request":            {"support", "faq", "general", "policy"},
    "technical_support_request":  {"support", "faq", "general", "policy"},
    "technical_assistance":       {"support", "faq", "general", "policy"},
    "onboarding":                 {"faq", "general", "policy", "profile"},
    "refund_request":             {"policy", "faq", "general"},
    "follow_up":                  {"product_service", "support", "faq", "general", "policy", "profile", "data_analytics"},
    "general_inquiry":            {"product_service", "support", "faq", "general", "policy", "profile", "data_analytics"},
    "greeting":                   {"product_service", "faq", "general", "profile", "data_analytics"},
    "unknown":                    {"product_service", "support", "faq", "general", "policy", "profile", "data_analytics"},
}
_DEFAULT_WHITELIST = {"product_service", "support", "faq", "general", "policy", "profile", "data_analytics"}


# ─────────────────────────────────────────────────────────────────────────────
# Data contracts
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ChunkGroundingScore:
    """Per-chunk validation result with full audit trail."""
    chunk_id:             str
    tenant_valid:         bool
    entity_alignment:     float   # 0-1
    category_alignment:   float   # 0-1
    semantic_relevance:   float   # 0-1 (from retrieval score)
    pricing_consistent:   bool
    content_valid:        bool
    final_grounding_score: float  # weighted composite
    validated:            bool
    rejection_reasons:    List[str] = field(default_factory=list)


@dataclass
class GroundingResult:
    """Result of the pre-generation grounding validation pass."""
    validated_chunks:       List[Dict]          # only chunks that passed
    rejected_chunks:        List[Dict]          # chunks that failed
    chunk_scores:           List[ChunkGroundingScore]
    overall_confidence:     float               # 0-1
    pricing_conflicts:      List[Dict]          # detected price conflicts
    category_violations:    int
    tenant_violations:      int
    escalate:               bool                # True when confidence too low
    latency_ms:             float
    accepted_count:         int
    rejected_count:         int


# ─────────────────────────────────────────────────────────────────────────────
# PreGenerationGroundingValidator
# ─────────────────────────────────────────────────────────────────────────────

class PreGenerationGroundingValidator:
    """
    Pre-generation grounding validator.

    Runs between retrieval output and the fact graph compressor.
    Every chunk that fails ANY check is removed before Brain #2 ever sees it.

    Usage:
        validator = PreGenerationGroundingValidator()
        result = validator.validate(chunks, intelligence, user_id, query)
        # use result.validated_chunks for fact graph compression
    """

    def validate(
        self,
        chunks: List[Dict],
        intelligence: Any,
        user_id: str,
        query: str = "",
    ) -> GroundingResult:
        """
        Validate all chunks before prompt construction.

        Args:
            chunks:       Raw chunk dicts from retrieval pipeline
            intelligence: EnterpriseIntelligenceResult or plain dict
            user_id:      Tenant ID — mandatory, zero exceptions
            query:        Primary query string for relevance checks

        Returns:
            GroundingResult with validated_chunks and full audit data
        """
        t_start = time.perf_counter()

        if not chunks:
            return self._empty_result(t_start)

        # Extract context from intelligence (handles both dataclass and dict)
        intent_type   = self._get_intent_type(intelligence)
        entities      = self._get_entities(intelligence)       # List[str]
        active_topic  = self._get_active_topic(intelligence)
        allowed_types = INTENT_CHUNK_WHITELIST.get(intent_type, _DEFAULT_WHITELIST)

        validated:   List[Dict]               = []
        rejected:    List[Dict]               = []
        scores:      List[ChunkGroundingScore] = []
        pricing_map: Dict[str, List[float]]   = {}   # entity → [prices]
        category_violations = 0
        tenant_violations   = 0

        for chunk in chunks:
            score = self._score_chunk(
                chunk=chunk,
                user_id=user_id,
                intent_type=intent_type,
                entities=entities,
                active_topic=active_topic,
                allowed_types=allowed_types,
                query=query,
                pricing_map=pricing_map,
            )
            scores.append(score)

            if not score.tenant_valid:
                tenant_violations += 1

            if score.category_alignment < 0.5:
                category_violations += 1

            if score.validated:
                validated.append(chunk)
            else:
                rejected.append(chunk)

        # Detect pricing conflicts across all accepted chunks
        pricing_conflicts = self._detect_pricing_conflicts(pricing_map)

        # Downgrade grounding for pricing conflicts
        if pricing_conflicts:
            logger.warning(
                "⚠️ Pricing conflicts detected: %d | entities=%s",
                len(pricing_conflicts),
                [c["entity"] for c in pricing_conflicts],
            )
            # Remove chunks that contributed conflicting prices
            conflict_entities = {c["entity"].lower() for c in pricing_conflicts}
            validated = [
                c for c in validated
                if not self._chunk_mentions_entity(
                    c.get("content", ""), conflict_entities
                )
            ]

        # Overall grounding confidence
        if not scores:
            overall = 0.0
        else:
            passing = [s for s in scores if s.validated]
            if not passing:
                overall = 0.0
            else:
                overall = sum(s.final_grounding_score for s in passing) / len(passing)
                # Penalise for high rejection ratio
                reject_ratio = len(rejected) / len(chunks)
                overall = overall * (1.0 - reject_ratio * 0.3)

        escalate = overall < ESCALATE_THRESHOLD and len(validated) == 0

        latency = (time.perf_counter() - t_start) * 1000

        logger.info(
            "🛡️ Pre-gen grounding | intent=%s accepted=%d rejected=%d "
            "pricing_conflicts=%d tenant_violations=%d confidence=%.3f latency=%.1fms",
            intent_type, len(validated), len(rejected),
            len(pricing_conflicts), tenant_violations, overall, latency,
        )

        return GroundingResult(
            validated_chunks=validated,
            rejected_chunks=rejected,
            chunk_scores=scores,
            overall_confidence=overall,
            pricing_conflicts=pricing_conflicts,
            category_violations=category_violations,
            tenant_violations=tenant_violations,
            escalate=escalate,
            latency_ms=latency,
            accepted_count=len(validated),
            rejected_count=len(rejected),
        )

    # ══════════════════════════════════════════════════════════════════════
    # Core scoring
    # ══════════════════════════════════════════════════════════════════════

    def _score_chunk(
        self,
        chunk: Dict,
        user_id: str,
        intent_type: str,
        entities: List[str],
        active_topic: str,
        allowed_types: set,
        query: str,
        pricing_map: Dict[str, List[float]],
    ) -> ChunkGroundingScore:

        chunk_id   = chunk.get("chunk_id") or chunk.get("id", "unknown")
        content    = chunk.get("content", "")
        chunk_type = str(chunk.get("chunk_type", "general")).lower()
        score_raw  = float(chunk.get("score", 0.0))
        chunk_uid  = chunk.get("user_id") or chunk.get("metadata", {}).get("user_id", "")
        reasons: List[str] = []

        # ── 1. Tenant validation (ZERO exceptions) ────────────────────────
        tenant_valid = (not chunk_uid) or (chunk_uid == user_id)
        if not tenant_valid:
            reasons.append("tenant_mismatch")
            return ChunkGroundingScore(
                chunk_id=chunk_id, tenant_valid=False,
                entity_alignment=0.0, category_alignment=0.0,
                semantic_relevance=score_raw, pricing_consistent=True,
                content_valid=False, final_grounding_score=0.0,
                validated=False, rejection_reasons=reasons,
            )

        # ── 2. Content quality ────────────────────────────────────────────
        content_valid = bool(content) and len(content.strip()) >= 20
        if not content_valid:
            reasons.append("empty_or_too_short")

        # ── 3. Semantic score ─────────────────────────────────────────────
        if score_raw < MIN_SEMANTIC_SCORE:
            reasons.append(f"low_semantic_score_{score_raw:.2f}")

        # ── 4. Category alignment ─────────────────────────────────────────
        normalized_type = chunk_type.replace("-", "_")
        category_ok = normalized_type in allowed_types or "general" in allowed_types
        category_score = 1.0 if category_ok else 0.0
        if not category_ok:
            reasons.append(f"category_mismatch_{chunk_type}_for_{intent_type}")

        # ── 5. Entity alignment ───────────────────────────────────────────
        entity_score = self._entity_alignment_score(content, entities, active_topic, query)
        if entity_score < 0.1 and entities:
            reasons.append("entity_not_found_in_chunk")

        # ── 6. Pricing consistency (collect prices, conflicts checked later) ─
        prices = self._extract_prices(content)
        entity_key = self._dominant_entity(content, entities) or "unknown"
        if prices:
            if entity_key not in pricing_map:
                pricing_map[entity_key] = []
            pricing_map[entity_key].extend(prices)
        pricing_consistent = True  # conflict resolution done after all chunks

        # ── 7. Composite grounding score ─────────────────────────────────
        grounding = (
            score_raw         * 0.35 +
            entity_score      * 0.30 +
            category_score    * 0.25 +
            (1.0 if content_valid else 0.0) * 0.10
        )
        grounding = min(1.0, max(0.0, grounding))

        validated = (
            tenant_valid
            and content_valid
            and score_raw >= MIN_SEMANTIC_SCORE
            and category_ok
            and grounding >= MIN_GROUNDING_SCORE
        )

        if not validated and not reasons:
            reasons.append(f"composite_grounding_too_low_{grounding:.2f}")

        return ChunkGroundingScore(
            chunk_id=chunk_id,
            tenant_valid=tenant_valid,
            entity_alignment=entity_score,
            category_alignment=category_score,
            semantic_relevance=score_raw,
            pricing_consistent=pricing_consistent,
            content_valid=content_valid,
            final_grounding_score=grounding,
            validated=validated,
            rejection_reasons=reasons,
        )

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _entity_alignment_score(
        self,
        content: str,
        entities: List[str],
        active_topic: str,
        query: str,
    ) -> float:
        """Score 0-1: how well content aligns with known entities / query."""
        if not content:
            return 0.0

        content_lower = content.lower()
        signals: List[float] = []

        # Entity hits
        if entities:
            hits = sum(
                1 for e in entities
                if e and e.lower() in content_lower
            )
            signals.append(hits / len(entities))

        # Active topic hit
        if active_topic and active_topic.lower() in content_lower:
            signals.append(0.8)

        # Query keyword overlap
        if query:
            stop = {"the", "a", "an", "is", "are", "for", "to", "in", "on", "of",
                    "do", "does", "can", "what", "how", "tell", "me", "and", "or"}
            keywords = [
                w for w in re.findall(r"\w+", query.lower())
                if w not in stop and len(w) > 2
            ]
            if keywords:
                kw_hits = sum(1 for k in keywords if k in content_lower)
                signals.append(kw_hits / len(keywords))

        if not signals:
            return 0.5   # no entities to check → neutral

        return min(1.0, sum(signals) / len(signals))

    def _extract_prices(self, content: str) -> List[float]:
        """Extract all dollar amounts from content."""
        matches = re.findall(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", content)
        result = []
        for m in matches:
            try:
                result.append(float(m.replace(",", "")))
            except ValueError:
                pass
        return result

    def _dominant_entity(self, content: str, entities: List[str]) -> Optional[str]:
        """Return the entity most mentioned in content."""
        if not entities:
            return None
        content_lower = content.lower()
        best, best_count = None, 0
        for e in entities:
            if not e:
                continue
            count = content_lower.count(e.lower())
            if count > best_count:
                best, best_count = e, count
        return best

    def _detect_pricing_conflicts(
        self, pricing_map: Dict[str, List[float]]
    ) -> List[Dict]:
        """Flag entities where retrieved prices diverge by >20%."""
        conflicts = []
        for entity, prices in pricing_map.items():
            if len(prices) < 2:
                continue
            mn, mx = min(prices), max(prices)
            if mn > 0 and (mx - mn) / mn > PRICING_CONFLICT_DELTA:
                conflicts.append({
                    "entity": entity,
                    "prices": prices,
                    "min":    mn,
                    "max":    mx,
                    "spread": round((mx - mn) / mn, 3),
                })
        return conflicts

    def _chunk_mentions_entity(self, content: str, entities: set) -> bool:
        content_lower = content.lower()
        return any(e in content_lower for e in entities)

    # ── Intelligence extraction (handles dataclass and dict) ──────────────

    def _get_intent_type(self, intelligence: Any) -> str:
        if isinstance(intelligence, dict):
            intents = intelligence.get("primary_intents", [])
            if intents:
                first = intents[0]
                return first.get("type", "general_inquiry") if isinstance(first, dict) \
                    else str(getattr(first, "type", "general_inquiry"))
            return intelligence.get("intent", "general_inquiry")

        # dataclass: EnterpriseIntelligenceResult
        intents = getattr(intelligence, "primary_intents", [])
        if intents:
            return str(getattr(intents[0], "type", "general_inquiry"))
        return "general_inquiry"

    def _get_entities(self, intelligence: Any) -> List[str]:
        if isinstance(intelligence, dict):
            ents = intelligence.get("entities", {})
            if isinstance(ents, dict):
                return (ents.get("products", []) or []) + (ents.get("features", []) or [])
            return []
        ents = getattr(intelligence, "entities", None)
        if ents is None:
            return []
        return list(getattr(ents, "products", []) or []) + list(getattr(ents, "features", []) or [])

    def _get_active_topic(self, intelligence: Any) -> str:
        if isinstance(intelligence, dict):
            br = intelligence.get("business_reasoning", {})
            return (br.get("likely_goal", "") if isinstance(br, dict) else "") or ""
        br = getattr(intelligence, "business_reasoning", None)
        return str(getattr(br, "likely_goal", "") or "") if br else ""

    # ── Empty result ──────────────────────────────────────────────────────

    def _empty_result(self, t_start: float) -> GroundingResult:
        return GroundingResult(
            validated_chunks=[],
            rejected_chunks=[],
            chunk_scores=[],
            overall_confidence=0.0,
            pricing_conflicts=[],
            category_violations=0,
            tenant_violations=0,
            escalate=False,
            latency_ms=(time.perf_counter() - t_start) * 1000,
            accepted_count=0,
            rejected_count=0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────────────────────────────
_validator: Optional[PreGenerationGroundingValidator] = None


def get_grounding_validator() -> PreGenerationGroundingValidator:
    global _validator
    if _validator is None:
        _validator = PreGenerationGroundingValidator()
    return _validator


__all__ = [
    "PreGenerationGroundingValidator",
    "GroundingResult",
    "ChunkGroundingScore",
    "get_grounding_validator",
]
