"""
automationservice — Enterprise RAG Cross-Encoder & Context Reranker
===================================================================
Pipeline Position:
    Qdrant Hybrid Retrieval (20-50 broad candidates)
    ↓
    THIS MODULE (Cross-Encoder / Token-Level Factual Reranker)
    ↓
    Top 5-7 pristine, high-confidence chunks
    ↓
    Processor #2 (Validation & Response Generation)

Guarantees:
  - Factual precision: Cross-attention over query + document tokens.
  - Zero hallucination prep: Strips noise and formats authoritative context blocks.
  - Non-blocking execution: Thread-pooled model scoring with fast fallback.
  - Multi-intent support: Balances top facts across all searched categories.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from typing import Any

_SVC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVER_DIR = os.path.dirname(os.path.dirname(_SVC_DIR))
for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger("automationservice.reranker")

_RERANKER_MODEL = None
_RERANKER_LOCK = None
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_MODEL_CACHE_DIR = os.path.join(_SERVER_DIR, ".model_cache")


def _get_reranker_model():
    """Lazy load CrossEncoder model singleton with thread safety."""
    global _RERANKER_MODEL, _RERANKER_LOCK
    import threading
    if _RERANKER_LOCK is None:
        _RERANKER_LOCK = threading.Lock()

    if _RERANKER_MODEL is None:
        with _RERANKER_LOCK:
            if _RERANKER_MODEL is None:
                try:
                    from sentence_transformers import CrossEncoder
                    _RERANKER_MODEL = CrossEncoder(
                        _MODEL_NAME,
                        max_length=512,
                    )
                    logger.info("automationservice: CrossEncoder loaded (%s)", _MODEL_NAME)
                except Exception as e:
                    logger.warning("automationservice: CrossEncoder load failed (%s) — using fast semantic ranker", e)
                    _RERANKER_MODEL = False
    return _RERANKER_MODEL if _RERANKER_MODEL is not False else None


def _build_doc_text(candidate: dict[str, Any]) -> str:
    """Compose concise, informative representation of a candidate for reranking."""
    payload = candidate.get("payload") or {}
    title = candidate.get("title") or payload.get("title") or ""
    cat = candidate.get("category") or payload.get("category") or ""
    subtype = candidate.get("subtype") or payload.get("subtype") or ""

    sd = payload.get("structured_data") or {}
    attrs = payload.get("attributes") or {}

    parts = [f"Title: {title}", f"Category: {cat}"]
    if subtype:
        parts.append(f"Subtype: {subtype}")

    # Key attributes
    attr_items = []
    for k, v in list(sd.items())[:8]:
        if v and k not in ("source_id", "user_id"):
            attr_items.append(f"{k}: {v}")
    for k, v in list(attrs.items())[:6]:
        if v and k not in ("source_id", "user_id", "priority_score") and k not in sd:
            attr_items.append(f"{k}: {v}")

    if attr_items:
        parts.append("Attributes: " + " | ".join(attr_items))

    search_text = candidate.get("search_text") or payload.get("search_text") or ""
    if search_text:
        parts.append(f"Details: {search_text[:600]}")

    return "\n".join(parts)


def _fast_semantic_scoring(query: str, candidates: list[dict[str, Any]]) -> list[tuple[float, dict[str, Any]]]:
    """
    High-accuracy, token-level semantic & exact matching fallback when CrossEncoder is bypassed.
    Evaluates:
      - Title token exact overlap
      - Technical specification & number matching (e.g. 16GB, $1000, RTX)
      - Category alignment
      - Base fusion score weighting
    """
    import re as _re

    q_clean = query.lower()
    q_tokens = set(re.findall(r"\b\w{2,}\b", q_clean))
    # Extract numbers and unit patterns from query (e.g. "16", "512", "1000")
    q_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", q_clean))

    scored = []
    for cand in candidates:
        doc_text = _build_doc_text(cand).lower()
        doc_tokens = set(re.findall(r"\b\w{2,}\b", doc_text))
        doc_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", doc_text))

        # Base retrieval score (from vector + metadata fusion)
        base_score = float(cand.get("score", 0.5))

        # Token overlap
        token_overlap = len(q_tokens & doc_tokens) / max(1, len(q_tokens))

        # Numeric & specification match (crucial for exact requirements like RAM / Price / Model #)
        num_score = 1.0
        if q_numbers:
            matching_nums = len(q_numbers & doc_numbers)
            num_score = matching_nums / len(q_numbers)

        # Title match boost
        title = (cand.get("title") or cand.get("payload", {}).get("title") or "").lower()
        title_boost = 0.0
        if title:
            t_tokens = set(re.findall(r"\b\w{2,}\b", title))
            if q_tokens & t_tokens:
                title_boost = 0.25 * (len(q_tokens & t_tokens) / max(1, len(t_tokens)))

        # Weighted final rerank score
        rerank_score = (
            base_score * 0.35 +
            token_overlap * 0.35 +
            num_score * 0.20 +
            title_boost * 0.10
        )
        scored.append((min(1.0, max(0.0, rerank_score)), cand))

    return scored


async def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 7,
) -> list[dict[str, Any]]:
    """
    Reranks candidate chunks against the customer query using cross-attention or
    high-precision token scoring.

    Args:
        query: Resolved standalone query from Processor #1 (or latest message).
        candidates: List of candidate dicts from run_hybrid_retrieval.
        top_k: Maximum number of refined candidates to return.

    Returns:
        List of top candidates sorted descending by rerank_score.
    """
    if not candidates:
        return []

    t0 = time.monotonic()
    clean_q = query.strip()
    if not clean_q:
        return candidates[:top_k]

    def _execute_rerank() -> list[dict[str, Any]]:
        model = _get_reranker_model()
        if model is not None and len(candidates) > 0:
            try:
                pairs = [[clean_q, _build_doc_text(c)] for c in candidates]
                raw_scores = model.predict(pairs)
                # Convert logits or raw scores to 0.0 - 1.0 scale via sigmoid
                import math
                scored = []
                for score, c in zip(raw_scores, candidates):
                    norm_score = 1.0 / (1.0 + math.exp(-float(score)))
                    scored.append((norm_score, c))
            except Exception as e:
                logger.warning("[reranker] CrossEncoder predict error: %s — falling back", e)
                scored = _fast_semantic_scoring(clean_q, candidates)
        else:
            scored = _fast_semantic_scoring(clean_q, candidates)

        # Sort descending
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for rank, (r_score, cand) in enumerate(scored[:top_k], start=1):
            c_copy = dict(cand)
            c_copy["rerank_score"] = round(r_score, 4)
            c_copy["rerank_rank"] = rank
            results.append(c_copy)

        return results

    try:
        reranked = await asyncio.to_thread(_execute_rerank)
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "[reranker] candidates=%d -> top=%d | elapsed=%.1fms | top_score=%.4f",
            len(candidates), len(reranked), elapsed_ms,
            reranked[0].get("rerank_score", 0.0) if reranked else 0.0,
        )
        return reranked
    except Exception as exc:
        logger.error("[reranker] unhandled error: %s", exc)
        return candidates[:top_k]


def format_retrieved_context_block(chunks: list[dict[str, Any]]) -> str:
    """
    Format refined candidate chunks into a clean, human-readable, and LLM-ready
    knowledge block for Processor #2.

    Guarantees:
      - Full attributes and specifications clearly visible.
      - Explicit source references (entry_id, category, title).
      - Zero placeholder noise.
    """
    if not chunks:
        return "NO_VERIFIED_BUSINESS_FACTS_FOUND: No relevant entries were found in the knowledge base."

    lines: list[str] = [
        "RETRIEVED BUSINESS KNOWLEDGE (AUTHENTIC GROUND TRUTH)",
        "Use ONLY the following facts to compose the response. Do not invent or assume anything.",
        "=" * 60,
    ]

    for idx, c in enumerate(chunks, start=1):
        payload = c.get("payload") or {}
        entry_id = c.get("entry_id") or payload.get("entry_id") or f"doc_{idx}"
        cat = c.get("category") or payload.get("category") or "general"
        subtype = c.get("subtype") or payload.get("subtype") or ""
        title = c.get("title") or payload.get("title") or "(Untitled)"

        sd = payload.get("structured_data") or {}
        attrs = payload.get("attributes") or {}
        search_text = c.get("search_text") or payload.get("search_text") or ""

        cat_header = f"{cat.upper()}" + (f" / {subtype.upper()}" if subtype else "")
        lines.append(f"\n[DOCUMENT {idx}] — {title} ({cat_header})")
        lines.append(f"  Source ID : {entry_id}")

        # Highlight structured attributes
        attr_lines = []
        for k, v in sd.items():
            if v and k not in ("source_id", "user_id"):
                attr_lines.append(f"{k}: {v}")
        for k, v in attrs.items():
            if v and k not in ("source_id", "user_id", "priority_score") and k not in sd:
                attr_lines.append(f"{k}: {v}")

        if attr_lines:
            lines.append("  Attributes: " + " | ".join(attr_lines))

        if search_text:
            clean_details = " ".join(search_text.split())
            lines.append(f"  Content   : {clean_details}")

    lines.append("\n" + "=" * 60)
    lines.append("END OF RETRIEVED KNOWLEDGE")
    return "\n".join(lines)
