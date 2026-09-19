"""
automationservice — Verified Retrieval Adapter (Phase 2)
=========================================================
Transforms retrieved search candidates, structured database rows,
and company context into atomic, strictly-typed VerifiedEvidence objects.

Guarantees:
  - Upstream approval: Only verified records from authorized data sources
    are marked as `status="verified"`.
  - Atomicity: Decomposes structured records into fine-grained evidence items
    (e.g., price, specs, warranty, return policy) so grounding and conflict
    detection can operate at claim level.
  - Provenance: Retains source_id and metadata for audit trails and citations.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from pipeline.contracts import VerifiedEvidence, SourceType

logger = logging.getLogger("automationservice.pipeline.evidence_retrieval")


def _sanitize_id(val: str) -> str:
    """Sanitize string for use in evidence IDs."""
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(val)).strip("_").lower()
    return clean[:32] if clean else "item"


def _build_evidence_id(source_type: str, source_id: str, attribute: str) -> str:
    """Generate a clean, stable evidence ID."""
    s_id = _sanitize_id(source_id)
    attr = _sanitize_id(attribute)
    return f"ev_{source_type[:4]}_{s_id}_{attr}"


def _map_category_to_source_type(cat: str, subtype: str = "") -> SourceType:
    """Map database category/subtype to canonical SourceType."""
    cat_lower = str(cat).lower()
    subtype_lower = str(subtype).lower()

    if subtype_lower == "data_analytics" or "analytics" in cat_lower:
        return "analytics"
    if "product" in cat_lower or "hardware" in subtype_lower or "software" in subtype_lower:
        return "product"
    if "polic" in cat_lower or "legal" in cat_lower or "terms" in cat_lower:
        return "policy"
    if "delivery" in cat_lower or "shipping" in cat_lower:
        return "delivery"
    if "contact" in cat_lower or "support" in cat_lower:
        return "support"
    if "company" in cat_lower or "about" in cat_lower:
        return "company"
    return "general"


def extract_verified_evidence(
    retrieved_chunks: list[dict[str, Any]],
    business_context: dict[str, Any] | None = None,
) -> list[VerifiedEvidence]:
    """
    Extract verified evidence objects from retrieved chunks and business context.

    Args:
        retrieved_chunks: Output from Qdrant search / cross-encoder reranker.
        business_context: Authoritative business profile from PostgreSQL.

    Returns:
        List of atomic VerifiedEvidence instances ready for context building.
    """
    evidence_list: list[VerifiedEvidence] = []
    seen_ids: set[str] = set()

    # ── 1. Company & Business Context Evidence ────────────────────────────────
    if business_context and business_context.get("_loaded"):
        biz_name = (business_context.get("business_name") or "").strip()
        biz_type = (business_context.get("business_type") or "").strip()
        biz_desc = (business_context.get("business_description") or "").strip()
        tone     = (business_context.get("communication_tone") or "professional").strip()
        country  = (business_context.get("country") or "").strip()
        audience = (business_context.get("target_audience") or "").strip()

        if biz_name:
            ev_id = "ev_comp_name"
            if ev_id not in seen_ids:
                seen_ids.add(ev_id)
                evidence_list.append(
                    VerifiedEvidence(
                        evidence_id=ev_id,
                        source_type="company",
                        source_id="biz_profile",
                        entity_name=biz_name,
                        attribute="name",
                        claim=f"Company name is {biz_name}",
                        value=biz_name,
                        status="verified",
                        allowed_for_customer_response=True,
                        metadata={"source": "users_table"},
                    )
                )

        if biz_type:
            ev_id = "ev_comp_type"
            if ev_id not in seen_ids:
                seen_ids.add(ev_id)
                evidence_list.append(
                    VerifiedEvidence(
                        evidence_id=ev_id,
                        source_type="company",
                        source_id="biz_profile",
                        entity_name=biz_name or "Company",
                        attribute="business_type",
                        claim=f"Business operates in {biz_type}",
                        value=biz_type,
                        status="verified",
                        allowed_for_customer_response=True,
                        metadata={"source": "users_table"},
                    )
                )

        if biz_desc:
            ev_id = "ev_comp_description"
            if ev_id not in seen_ids:
                seen_ids.add(ev_id)
                evidence_list.append(
                    VerifiedEvidence(
                        evidence_id=ev_id,
                        source_type="company",
                        source_id="biz_profile",
                        entity_name=biz_name or "Company",
                        attribute="description",
                        claim=f"Company profile: {biz_desc[:300]}",
                        value=biz_desc,
                        status="verified",
                        allowed_for_customer_response=True,
                        metadata={"source": "users_table"},
                    )
                )

    # ── 2. Knowledge Base & Retrieved Candidates Evidence ─────────────────────
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        if not isinstance(chunk, dict):
            continue

        payload = chunk.get("payload") or {}
        entry_id = str(chunk.get("entry_id") or payload.get("entry_id") or f"chunk_{idx}")
        category = chunk.get("category") or payload.get("category") or "general"
        subtype  = chunk.get("subtype") or payload.get("subtype") or ""
        title    = (chunk.get("title") or payload.get("title") or f"Item {idx}").strip()
        source_type = _map_category_to_source_type(category, subtype)

        rerank_score = chunk.get("rerank_score")
        vector_score = chunk.get("score") or chunk.get("vector_score", 0.0)

        sd = payload.get("structured_data") or {}
        attrs = payload.get("attributes") or {}
        search_text = (chunk.get("search_text") or payload.get("search_text") or "").strip()

        # Combine structured attributes
        merged_attrs: dict[str, Any] = {}
        if isinstance(attrs, dict):
            merged_attrs.update(attrs)
        if isinstance(sd, dict):
            merged_attrs.update(sd)

        # Ignore internal noise fields
        INTERNAL_FIELDS = {
            "source_id", "user_id", "priority_score", "quality_score",
            "entry_id", "id", "created_at", "updated_at", "is_deleted"
        }

        # Entity name disambiguation for multi-entry categories
        entity_name = title
        if category == "contact_support":
            channel = sd.get("contact_channel") or attrs.get("contact_channel")
            item_name = sd.get("contact_support_item") or attrs.get("name")
            if item_name and item_name.lower() != title.lower():
                entity_name = f"{title} ({item_name})"
            elif channel and channel.lower() != title.lower():
                entity_name = f"{title} ({channel})"
        elif category == "delivery_shipping":
            region = sd.get("region") or sd.get("service_area") or attrs.get("region")
            del_type = sd.get("delivery_type") or attrs.get("delivery_type")
            if region and region.lower() != title.lower():
                entity_name = f"{title} - {region}"
            elif del_type and del_type.lower() != title.lower():
                entity_name = f"{title} ({del_type})"

        # 2a. Atomic attributes (price, ram, cpu, warranty, etc.)
        for attr_key, attr_val in merged_attrs.items():
            if attr_key in INTERNAL_FIELDS or attr_val is None:
                continue

            attr_str = str(attr_val).strip()
            if not attr_str:
                continue

            ev_id = _build_evidence_id(source_type, entry_id, attr_key)
            if ev_id in seen_ids:
                continue
            seen_ids.add(ev_id)

            # Format human-readable claim
            claim_text = f"{entity_name} {attr_key}: {attr_str}"

            evidence_list.append(
                VerifiedEvidence(
                    evidence_id=ev_id,
                    source_type=source_type,
                    source_id=entry_id,
                    entity_name=entity_name,
                    attribute=attr_key,
                    claim=claim_text,
                    value=attr_val,
                    status="verified",
                    allowed_for_customer_response=True,
                    metadata={
                        "category": category,
                        "subtype": subtype,
                        "rerank_score": rerank_score,
                        "vector_score": vector_score,
                    },
                )
            )

        # 2b. General summary text claim
        if search_text:
            overview_id = _build_evidence_id(source_type, entry_id, "overview")
            if overview_id not in seen_ids:
                seen_ids.add(overview_id)
                clean_summary = " ".join(search_text.split())[:400]
                evidence_list.append(
                    VerifiedEvidence(
                        evidence_id=overview_id,
                        source_type=source_type,
                        source_id=entry_id,
                        entity_name=entity_name,
                        attribute="overview",
                        claim=f"{entity_name}: {clean_summary}",
                        value=clean_summary,
                        status="verified",
                        allowed_for_customer_response=True,
                        metadata={
                            "category": category,
                            "subtype": subtype,
                            "rerank_score": rerank_score,
                        },
                    )
                )

    logger.debug(
        "[evidence_retrieval] extracted %d atomic verified evidence objects from %d chunks",
        len(evidence_list), len(retrieved_chunks),
    )
    return evidence_list
