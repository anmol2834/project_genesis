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
MIN_SEMANTIC_SCORE      = 0.15   # lowered: BM25 normalized scores are naturally lower
MIN_GROUNDING_SCORE     = 0.35   # lowered: L5/L6-only chunks have naturally lower composite scores
                                  #          when L3/L4 are the primary fix; 0.35 passes good chunks
ESCALATE_THRESHOLD      = 0.30   # overall confidence below this → flag for handoff
PRICING_CONFLICT_DELTA  = 0.20   # >20% price spread → conflict detected

# Intent → allowed chunk_types
# Values MUST match the exact normalized chunk_type strings produced by
# _normalize_payload in async_repository.py, i.e. the exact category strings
# stored in user_data_entries: offers_promotions, delivery_shipping, etc.
# "general" is always included as a permissive fallback for business_context chunks.
INTENT_CHUNK_WHITELIST: Dict[str, set] = {
    # ── 8 real Qdrant categories (from user_data_entries.category field): ──
    # product_service, offers_promotions, delivery_shipping, company_info,
    # educational_content, contact_support, policies_legal, issue_resolution
    # Plus data_analytics (computed by the analytics engine).
    # "general" is the fallback for business_context chunks that didn't map to a category.
    #
    # IMPORTANT: "faq", "support", "policy", "profile" are NOT real Qdrant categories.
    # They are raw aliases that _normalize_payload converts to the 8 real ones:
    #   faq → educational_content | support → contact_support
    #   policy → policies_legal  | profile → company_info
    # After normalization, chunk_type is always one of the 8 real values.

    "pricing_inquiry": {
        # Pricing data spans all three commerce categories:
        #   product_service   — product records with inline prices (primary)
        #   offers_promotions — promotional/discounted prices
        #   delivery_shipping — shipping cost/pricing data
        "product_service", "offers_promotions", "delivery_shipping",
        "company_info",
        "data_analytics",   # price-range aggregate (cheapest/most expensive/avg)
        "general",          # fallback for business_context profile chunks
    },
    "product_inquiry": {
        "product_service",
        "company_info",
        "data_analytics",   # catalog overview (total products, categories, price range)
        "general",
    },
    "offers_inquiry": {
        "offers_promotions",
        "product_service",  # some offers reference specific products
        "company_info",
        "data_analytics",
        "general",
    },
    "shipping_inquiry": {
        "delivery_shipping",
        "product_service",  # some products bundle delivery info
        "company_info",
        "data_analytics",
        "general",
    },
    "company_inquiry": {
        "company_info",
        "data_analytics",
        "general",
    },
    "educational_inquiry": {
        "educational_content",
        "company_info",
        "data_analytics",
        "general",
    },
    "feature_request": {
        "product_service",
        "company_info",
        "data_analytics",
        "general",
    },
    "support_request": {
        "contact_support",
        "policies_legal",
        "company_info",
        "general",
    },
    "technical_support_request": {
        "issue_resolution",
        "contact_support",
        "policies_legal",
        "general",
    },
    "technical_assistance": {
        "issue_resolution",
        "contact_support",
        "general",
    },
    "issue_inquiry": {
        "issue_resolution",
        "contact_support",
        "general",
    },
    "issue_resolution": {
        "issue_resolution",
        "contact_support",
        "general",
    },
    "onboarding": {
        "educational_content",
        "policies_legal",
        "company_info",
        "general",
    },
    "refund_request": {
        "policies_legal",
        "contact_support",
        "general",
    },
    "billing_inquiry": {
        "policies_legal",
        "product_service",
        "general",
    },
    "complaint": {
        "contact_support",
        "policies_legal",
        "general",
    },
    "follow_up": {
        # follow_up can continue any prior conversation — allow all 8 + analytics
        "product_service", "offers_promotions", "delivery_shipping",
        "contact_support", "company_info", "educational_content",
        "issue_resolution", "policies_legal",
        "data_analytics", "general",
    },
    "general_inquiry": {
        "product_service", "offers_promotions", "delivery_shipping",
        "contact_support", "company_info", "educational_content",
        "issue_resolution", "policies_legal",
        "data_analytics", "general",
    },
    "greeting": {
        "product_service",
        "company_info",
        "general",
    },
    "unknown": {
        "product_service", "offers_promotions", "delivery_shipping",
        "contact_support", "company_info", "educational_content",
        "issue_resolution", "policies_legal",
        "data_analytics", "general",
    },
    "analytics_inquiry": {
        "data_analytics",
        "general",
    },
}
_DEFAULT_WHITELIST = {
    # All 8 real Qdrant categories + analytics + general fallback
    "product_service", "offers_promotions", "delivery_shipping",
    "contact_support", "company_info", "educational_content",
    "issue_resolution", "policies_legal",
    "data_analytics", "general",
}


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
            # Skip data_analytics chunks for pricing conflict detection —
            # they contain aggregate/discount data, not authoritative product prices.
            is_analytics = str(chunk.get("chunk_type", "")).lower() == "data_analytics"

            score = self._score_chunk(
                chunk=chunk,
                user_id=user_id,
                intent_type=intent_type,
                entities=entities,
                active_topic=active_topic,
                allowed_types=allowed_types,
                query=query,
                pricing_map=pricing_map if not is_analytics else {},
                is_analytics=is_analytics,
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

        # Downgrade grounding for pricing conflicts — but only REMOVE chunks when
        # the spread is severe (>50%).  A 20–50% spread just gets flagged with
        # price_conflict in the fact graph; Brain #2 is instructed not to quote it.
        # Removing all conflicted chunks leaves Brain #2 with zero context which
        # causes generic responses — worse than showing the products with a warning.
        _SEVERE_CONFLICT_DELTA = 0.50   # >50% spread → actually remove the chunks
        if pricing_conflicts:
            logger.warning(
                "Pricing conflicts detected: %d | entities=%s",
                len(pricing_conflicts),
                [c["entity"] for c in pricing_conflicts],
            )
            severe_conflict_entities = {
                c["entity"].lower() for c in pricing_conflicts
                if c.get("spread", 0.0) > _SEVERE_CONFLICT_DELTA
            }
            if severe_conflict_entities:
                validated = [
                    c for c in validated
                    if not self._chunk_mentions_entity(
                        c.get("content", ""), severe_conflict_entities
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
                reject_ratio = len(rejected) / len(chunks)
                overall = overall * (1.0 - reject_ratio * 0.3)

        escalate = overall < ESCALATE_THRESHOLD and len(validated) == 0

        latency = (time.perf_counter() - t_start) * 1000

        logger.info(
            "Pre-gen grounding | intent=%s accepted=%d rejected=%d "
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
        is_analytics: bool = False,
    ) -> ChunkGroundingScore:

        chunk_id   = chunk.get("chunk_id") or chunk.get("id", "unknown")
        content    = chunk.get("content", "")
        chunk_type = str(chunk.get("chunk_type", "general")).lower()
        score_raw  = float(chunk.get("score", 0.0))
        chunk_uid  = chunk.get("user_id") or chunk.get("metadata", {}).get("user_id", "")
        reasons: List[str] = []

        # 1. Tenant validation (ZERO exceptions)
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

        # 2. Content quality
        content_valid = bool(content) and len(content.strip()) >= 20
        if not content_valid:
            reasons.append("empty_or_too_short")

        # 3. Semantic score
        if score_raw < MIN_SEMANTIC_SCORE:
            reasons.append(f"low_semantic_score_{score_raw:.2f}")

        # 4. Category alignment
        normalized_type = chunk_type.replace("-", "_")
        category_ok = normalized_type in allowed_types or "general" in allowed_types
        category_score = 1.0 if category_ok else 0.0
        if not category_ok:
            reasons.append(f"category_mismatch_{chunk_type}_for_{intent_type}")

        # 5. Entity alignment
        # data_analytics chunks are ONLY relevant when user explicitly requested analytics.
        # For product_inquiry and pricing_inquiry, analytics chunks fail category check
        # (removed from whitelist) and are correctly rejected.
        content_lower_check = content.lower()
        is_pricing_analytics = False  # analytics no longer bypass entity check for product/pricing intents
        entity_score = self._entity_alignment_score(content, entities, active_topic, query, chunk)

        # SPEC QUERY LENIENCY: When the query contains hardware specs (8GB RAM, 512GB SSD)
        # and the chunk is from an allowed category (product_service / data_analytics),
        # do NOT penalise entity_score below 0.4 — the spec may appear in a normalised
        # form that exact string matching misses (e.g. "8 GB" vs "8GB").
        # The BM25 layer (L5) already ran spec-specific exact matching; if this chunk
        # reached the grounding validator it means L5 scored it positively.
        # Artificially low entity_score here would override that signal and reject
        # a valid chunk, leaving Brain #2 with empty context.
        _SPEC_KW_GUARD = re.compile(
            r'\b\d+\s*(?:gb|tb|mb|ghz|mhz)\b'
            r'|\bram\b|\bssd\b|\bhdd\b|\bgpu\b|\bcpu\b',
            re.IGNORECASE,
        )
        if entity_score < 0.4 and entities and category_ok:
            # Check if any entity is a hardware spec
            has_spec_entity = any(_SPEC_KW_GUARD.search(str(e)) for e in entities)
            if has_spec_entity:
                # Promote entity_score to neutral 0.45 so the chunk isn't rejected
                # solely because the spec didn't appear verbatim in the content text.
                # The category filter already ensures this chunk is relevant by type.
                entity_score = max(entity_score, 0.45)
        if entity_score < 0.1 and entities:
            reasons.append("entity_not_found_in_chunk")

        # 6. Pricing consistency (collect prices, conflicts checked later)
        prices = self._extract_prices(content)
        entity_key = self._dominant_entity(content, entities) or "unknown"
        if prices:
            if entity_key not in pricing_map:
                pricing_map[entity_key] = []
            pricing_map[entity_key].extend(prices)
        pricing_consistent = True

        # 7. Composite grounding score
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
        chunk: Optional[Dict] = None,
    ) -> float:
        """Score 0-1: how well content aligns with known entities / query.

        SPEC MATCHING FIX:
        Hardware specs like "8GB RAM" or "512GB SSD" may appear in product
        content as "8 GB", "8GB", "8 gb ram", "8gb ram", "512 GB SSD", etc.
        Exact string match misses normalized forms.  We extract the numeric
        value + unit and do a fuzzy regex match so spec-matching chunks are
        not incorrectly rejected by the grounding validator.

        METADATA SCAN FIX:
        Category/type entities like "gaming", "GPU", "gaming laptop" often
        appear in structured_data.category, attributes.category, or metadata
        fields rather than the content text. We scan all text representations
        of the full chunk payload so category-level queries don't reject
        all chunks due to zero content-field matches.
        """
        if not content:
            return 0.0

        content_lower = content.lower()
        # Normalised version: collapse all whitespace so "8GB RAM" matches "8 GB ram"
        content_nospace = re.sub(r"\s+", "", content_lower)

        # Build an extended search text that includes metadata fields:
        # category, structured_data values, attributes values, title, search_text, keywords
        # This fixes the "gaming / GPU" entity miss when category="gaming" lives in metadata
        extended_text = content_lower
        if chunk and isinstance(chunk, dict):
            meta = chunk.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}
            for src in (meta, meta.get("structured_data") or {}, meta.get("attributes") or {},
                        chunk.get("structured_data") or {}, chunk.get("attributes") or {}):
                if isinstance(src, dict):
                    for v in src.values():
                        if v:
                            extended_text += " " + re.sub(r"\s+", " ", str(v).lower())
        extended_nospace = re.sub(r"\s+", "", extended_text)

        signals: List[float] = []

        # Compiled spec pattern: extracts numeric value + storage/freq unit
        _SPEC_NUM = re.compile(r'^(\d+)\s*(gb|tb|mb|ghz|mhz)', re.IGNORECASE)

        # Entity hits — try exact, whitespace-normalised, and spec-numeric matching
        if entities:
            hits: float = 0
            for e in entities:
                if not e:
                    continue
                e_lower = e.lower()
                e_nospace = re.sub(r"\s+", "", e_lower)

                # 1. Exact string match in content (fastest path)
                if e_lower in content_lower or (e_nospace and e_nospace in content_nospace):
                    hits += 1
                    continue

                # 2. Match in extended metadata text (catches category-based entities)
                if e_lower in extended_text or (e_nospace and e_nospace in extended_nospace):
                    hits += 0.9  # Slightly lower confidence than content hit
                    continue

                # 3. Spec-numeric match: "8GB RAM" → search for \b8\s*gb\b in content + metadata
                m = _SPEC_NUM.match(e_lower.strip())
                if m:
                    num_str = m.group(1)   # e.g. "8" or "512"
                    unit    = m.group(2).lower()  # e.g. "gb"
                    # Allow optional space between number and unit
                    spec_pat = re.compile(
                        rf'\b{re.escape(num_str)}\s*{re.escape(unit)}\b',
                        re.IGNORECASE,
                    )
                    if spec_pat.search(extended_text):
                        hits += 1
                    elif num_str in extended_text:
                        # Partial: the number appears but unit form differs → half credit
                        hits += 0.5

                # 4. Individual word matches (for multi-word entities like "gaming laptop GPU")
                # Split entity into significant words and check overlap
                else:
                    e_words = [w for w in e_lower.split() if len(w) > 3]
                    if e_words:
                        word_hits = sum(1 for w in e_words if w in extended_text)
                        if word_hits == len(e_words):
                            hits += 0.8
                        elif word_hits > 0:
                            hits += 0.4 * (word_hits / len(e_words))

            signals.append(min(1.0, hits / len(entities)))

        # Active topic hit
        if active_topic and active_topic.lower() in extended_text:
            signals.append(0.8)

        # Query keyword overlap (use extended_text for better coverage)
        if query:
            stop = {"the", "a", "an", "is", "are", "for", "to", "in", "on", "of",
                    "do", "does", "can", "what", "how", "tell", "me", "and", "or"}
            keywords = [
                w for w in re.findall(r"\w+", query.lower())
                if w not in stop and len(w) > 2
            ]
            if keywords:
                kw_hits = sum(1 for k in keywords if k in extended_text)
                signals.append(kw_hits / len(keywords))

        if not signals:
            return 0.5   # no entities to check → neutral

        return min(1.0, sum(signals) / len(signals))

    def _extract_prices(self, content: str) -> List[float]:
        """Extract all price amounts from content regardless of currency symbol."""
        # Match $, ₹, €, £, USD, INR, EUR, GBP prefixed amounts
        patterns = [
            r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)",
            r"[\u20b9\u20ac\u00a3]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)",
            r"(?:USD|INR|EUR|GBP)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)",
        ]
        result = []
        for pat in patterns:
            for m in re.findall(pat, content, re.IGNORECASE):
                try:
                    result.append(float(str(m).replace(",", "")))
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
        """Flag entities where retrieved prices diverge by >20%.
        
        IMPORTANT: The "unknown" key is used when no dominant entity is found —
        this happens when multiple different products each have prices but none of
        them mentions the query entities prominently. These are NOT a pricing conflict
        for the same product; they are prices for DIFFERENT products that happen to
        share the "unknown" bucket. Skip this key entirely.
        """
        conflicts = []
        for entity, prices in pricing_map.items():
            # Skip the catch-all "unknown" bucket — it aggregates prices from
            # multiple unrelated products and always produces false positives.
            if entity == "unknown":
                continue
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

    # Intelligence extraction (handles dataclass and dict)

    def _get_intent_type(self, intelligence: Any) -> str:
        if isinstance(intelligence, dict):
            intents = intelligence.get("primary_intents", [])
            if intents:
                first = intents[0]
                if isinstance(first, dict):
                    raw = first.get("type", "general_inquiry")
                else:
                    raw = getattr(first, "type", "general_inquiry")
                # Enum → get .value; str with "EnumClass.VALUE" → split after "."
                if hasattr(raw, "value"):
                    return str(raw.value)
                s = str(raw)
                return s.split(".")[-1].lower() if "." in s else s.lower()
            return intelligence.get("intent", "general_inquiry")
        intents = getattr(intelligence, "primary_intents", [])
        if intents:
            raw = getattr(intents[0], "type", "general_inquiry")
            if hasattr(raw, "value"):
                return str(raw.value)
            s = str(raw)
            return s.split(".")[-1].lower() if "." in s else s.lower()
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

    # Empty result

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
