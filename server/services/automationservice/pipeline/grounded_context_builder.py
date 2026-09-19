"""
automationservice — Grounded Context Builder (Phase 3)
======================================================
Transforms raw verified evidence into a compact, structured context package.

Pipeline stages:
  Raw verified evidence
          ↓
  Relevance filtering (removes unapproved or out-of-scope facts)
          ↓
  Deduplication (removes redundant assertions of the same fact)
          ↓
  Conflict detection (identifies contradictory claims across documents)
          ↓
  Priority ordering (sorts by hard-requirement relevance and rerank score)
          ↓
  Grounded Context Package

Guarantees:
  - Never silently chooses a winner when verified facts conflict.
  - Generates explicit EvidenceConflict objects.
  - Preserves source and evidence IDs for full provenance tracking.
  - Prevents noisy, ungrounded retrieval junk from reaching OpenAI Call #2.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from pipeline.contracts import (
    VerifiedEvidence,
    EvidenceConflict,
    CustomerRequirements,
)

logger = logging.getLogger("automationservice.pipeline.grounded_context_builder")


class GroundedContextPackage:
    """Packaged grounded context ready for strategy analysis and prompt formatting."""

    def __init__(
        self,
        approved_facts: list[VerifiedEvidence],
        conflicts: list[EvidenceConflict],
        prohibited_fact_ids: list[str],
    ):
        self.approved_facts = approved_facts
        self.conflicts = conflicts
        self.prohibited_fact_ids = prohibited_fact_ids

    @property
    def has_conflicts(self) -> bool:
        return any(c.resolution == "unresolved" for c in self.conflicts)

    def format_prompt_block(self) -> str:
        """
        Format approved facts into a clean, LLM-ready knowledge block
        with explicit [EVIDENCE ev_id] tags for reliable citation.
        """
        if not self.approved_facts:
            return "NO_VERIFIED_BUSINESS_FACTS_FOUND: No approved factual evidence was found in the knowledge base."

        lines: list[str] = [
            "VERIFIED BUSINESS EVIDENCE (GROUND TRUTH)",
            "Directives for OpenAI Call #2:",
            "  1. Only make statements supported by an approved [EVIDENCE ...] item below.",
            "  2. In your response output, list the exact evidence_ids you used in 'sources_used'.",
            "  3. Do NOT invent specs, prices, policies, or dates not explicitly stated below.",
        ]

        if self.conflicts:
            lines.append("\nATTENTION: THE FOLLOWING CONFLICTS WERE DETECTED IN THE KNOWLEDGE BASE:")
            for conf in self.conflicts:
                if conf.resolution == "unresolved":
                    lines.append(
                        f"  [CONFLICT {conf.conflict_group_id}] {conf.entity_name} {conf.attribute}: "
                        f"Conflicting records exist ({', '.join(str(v) for v in conf.conflicting_values)}). "
                        "DO NOT quote this information as definitive fact."
                    )

        lines.append("=" * 64)

        # Group facts by entity_name
        grouped: dict[str, list[VerifiedEvidence]] = {}
        for ev in self.approved_facts:
            key = ev.entity_name or ev.source_type.upper()
            grouped.setdefault(key, []).append(ev)

        for entity, facts in grouped.items():
            lines.append(f"\n[{entity.upper()}]")
            for f in facts:
                status_flag = " (CONFLICT PENDING)" if f.evidence_id in self.prohibited_fact_ids else ""
                lines.append(f"  • [{f.evidence_id}] {f.claim}{status_flag}")

        lines.append("\n" + "=" * 64)
        lines.append("END OF VERIFIED EVIDENCE")
        return "\n".join(lines)


def _normalize_value_for_conflict(val: Any) -> str:
    """Normalize value representation for conflict comparison."""
    if val is None:
        return ""
    s = str(val).strip().lower()
    # Strip currency signs, punctuation, commas
    s = s.replace("$", "").replace(",", "").strip()
    return s


def build_grounded_context(
    evidence_items: list[VerifiedEvidence],
    customer_requirements: CustomerRequirements | None = None,
    max_facts: int = 25,
) -> GroundedContextPackage:
    """
    Transform verified evidence into a clean, conflict-checked GroundedContextPackage.

    Args:
        evidence_items: Raw list of verified evidence extracted by Stage 1.
        customer_requirements: Structured requirements from Stage 2.
        max_facts: Maximum number of approved facts to pass downstream.

    Returns:
        GroundedContextPackage containing approved facts and explicit conflicts.
    """
    # ── Stage 1: Relevance & Approval Filtering ───────────────────────────────
    valid_items: list[VerifiedEvidence] = []
    for item in evidence_items:
        if not item.allowed_for_customer_response:
            continue
        if item.status != "verified":
            continue
        if not item.claim or not item.evidence_id:
            continue
        valid_items.append(item)

    # ── Stage 2: Deduplication ────────────────────────────────────────────────
    # Key on (entity_name, attribute, normalized_value)
    deduped_map: dict[tuple[str, str, str], VerifiedEvidence] = {}
    for item in valid_items:
        norm_val = _normalize_value_for_conflict(item.value)
        key = (item.entity_name.lower(), item.attribute.lower(), norm_val)

        if key in deduped_map:
            # Keep the one with higher rerank score if available
            existing = deduped_map[key]
            curr_score = float(item.metadata.get("rerank_score") or 0.0)
            ex_score = float(existing.metadata.get("rerank_score") or 0.0)
            if curr_score > ex_score:
                deduped_map[key] = item
        else:
            deduped_map[key] = item

    deduped_items = list(deduped_map.values())

    # ── Stage 3: Conflict Detection ───────────────────────────────────────────
    # Detect contradictory values for the same (entity_name, attribute)
    # e.g., IngenAI Gaming Pro 15 price: 1099 vs 1299
    # or return policy: 14 days vs 30 days
    conflicts: list[EvidenceConflict] = []
    prohibited_fact_ids: list[str] = []

    attr_buckets: dict[tuple[str, str], list[VerifiedEvidence]] = {}
    for item in deduped_items:
        # Ignore overview/summary strings for exact conflict checks
        if item.attribute.lower() in ("overview", "description", "name", ""):
            continue
        bucket_key = (item.entity_name.lower(), item.attribute.lower())
        attr_buckets.setdefault(bucket_key, []).append(item)

    conf_counter = 1
    for (entity, attr), items_in_bucket in attr_buckets.items():
        if len(items_in_bucket) > 1:
            # Check if values actually disagree
            distinct_values = set()
            for it in items_in_bucket:
                nv = _normalize_value_for_conflict(it.value)
                if nv:
                    distinct_values.add(nv)

            if len(distinct_values) > 1:
                # Contradiction detected!
                conf_id = f"conf_{conf_counter:02d}_{attr[:8]}"
                conf_counter += 1
                ev_ids = [it.evidence_id for it in items_in_bucket]
                raw_vals = [it.value for it in items_in_bucket]

                conf = EvidenceConflict(
                    conflict=True,
                    conflict_group_id=conf_id,
                    entity_name=items_in_bucket[0].entity_name,
                    attribute=attr,
                    facts=ev_ids,
                    conflicting_values=raw_vals,
                    resolution="unresolved",
                    resolution_reason=f"Multiple conflicting values retrieved for {items_in_bucket[0].entity_name} '{attr}': {distinct_values}",
                )
                conflicts.append(conf)
                # Mark conflicting facts as prohibited from direct single-statement assertion
                prohibited_fact_ids.extend(ev_ids)
                logger.warning(
                    "[grounded_context] CONFLICT DETECTED | %s.%s has conflicting values: %s (facts=%s)",
                    entity, attr, raw_vals, ev_ids,
                )

    # ── Stage 4: Priority Ordering ────────────────────────────────────────────
    # Order facts:
    #   1. Facts matching hard requirements (budget, specific requested specs)
    #   2. Specific technical attributes (price, specs)
    #   3. Rerank score from cross-encoder
    #   4. Company background facts
    hard_fields = set()
    if customer_requirements:
        for hr in customer_requirements.hard:
            hard_fields.add(hr.field.lower())

    def _fact_priority(ev: VerifiedEvidence) -> tuple[int, float, int]:
        is_hard_match = 1 if ev.attribute.lower() in hard_fields else 0
        rerank = float(ev.metadata.get("rerank_score") or 0.0)
        is_prohibited = 1 if ev.evidence_id in prohibited_fact_ids else 0
        # Return sorting key (descending priority):
        # higher hard_match first, non-prohibited first, higher rerank first
        return (is_hard_match, 1 - is_prohibited, rerank)

    sorted_facts = sorted(deduped_items, key=_fact_priority, reverse=True)
    selected_facts = sorted_facts[:max_facts]

    logger.info(
        "[grounded_context] built | approved_facts=%d conflicts=%d prohibited=%d",
        len(selected_facts), len(conflicts), len(prohibited_fact_ids),
    )

    return GroundedContextPackage(
        approved_facts=selected_facts,
        conflicts=conflicts,
        prohibited_fact_ids=prohibited_fact_ids,
    )
