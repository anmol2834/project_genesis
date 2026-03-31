"""
Intent Engine — Utils
======================
Shared helpers for the intent engine:
  - Text cleaning (HTML, whitespace, encoding)
  - MiniLM embedding singleton (reuses auth-service model, no new instance)
  - Cosine similarity scoring
  - Language type detection
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer, util

from ..schemas.intent_schema import LanguageType

logger = logging.getLogger(__name__)

# ── Model singleton ───────────────────────────────────────────────────────────
# Reuses the same all-MiniLM-L6-v2 already used by auth-service.
# Loaded once per process — safe for async use (encode() is thread-safe).

_embedding_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """Return the singleton MiniLM embedding model. Loads on first call."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading all-MiniLM-L6-v2 embedding model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _embedding_model


# ── Text cleaning ─────────────────────────────────────────────────────────────

_HTML_TAG_RE    = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE    = re.compile(r"\n{3,}")
_URL_RE         = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE       = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.IGNORECASE)


def clean_text(text: str, max_chars: int = 1500) -> str:
    """
    Lightweight text cleaner for classification input.
    Strips HTML, normalises unicode, collapses whitespace.
    Does NOT remove URLs/emails — those are needed for risk flag detection.
    """
    if not text:
        return ""
    # Decode HTML entities (&amp; → &, etc.)
    text = html.unescape(text)
    # Strip HTML tags
    text = _HTML_TAG_RE.sub(" ", text)
    # Normalise unicode (NFKC handles ligatures, full-width chars, etc.)
    text = unicodedata.normalize("NFKC", text)
    # Collapse whitespace
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    text = text.strip()
    # Hard truncate to keep within token budget
    return text[:max_chars]


def extract_plain_text(text: str) -> str:
    """
    More aggressive cleaning for embedding input:
    removes URLs, emails, and punctuation noise.
    """
    text = clean_text(text)
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text


def truncate_history(messages: List[str], max_messages: int = 3) -> str:
    """
    Take the last N messages from conversation history and join as plain text.
    Only uses incoming messages to avoid polluting context with our own replies.
    """
    recent = messages[-max_messages:] if len(messages) > max_messages else messages
    return " | ".join(m.strip() for m in recent if m.strip())


# ── Embedding & similarity ────────────────────────────────────────────────────

def embed(text: str) -> np.ndarray:
    """Encode a single text string to a 384-dim numpy vector."""
    model = get_embedding_model()
    return model.encode(text, convert_to_numpy=True, normalize_embeddings=True)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalised vectors. Returns [0, 1]."""
    score = float(np.dot(a, b))
    # Clamp to [0, 1] — normalised vectors can have tiny float errors
    return max(0.0, min(1.0, score))


def best_match(
    query_vec: np.ndarray,
    anchor_vecs: Dict[str, np.ndarray],
) -> tuple[str, float, Dict[str, float]]:
    """
    Find the anchor label with highest cosine similarity to the query.

    Returns:
        (best_label, best_score, all_scores_dict)
    """
    scores: Dict[str, float] = {
        label: cosine_similarity(query_vec, vec)
        for label, vec in anchor_vecs.items()
    }
    best_label = max(scores, key=lambda k: scores[k])
    return best_label, scores[best_label], scores


# ── Language type detection ───────────────────────────────────────────────────

# Slang indicators
_SLANG_PATTERNS = re.compile(
    r"\b(lol|lmao|omg|wtf|bruh|bro|sis|ngl|tbh|imo|imho|idk|"
    r"gonna|wanna|gotta|kinda|sorta|ya|yep|nope|sup|wassup|"
    r"haha|hehe|xd|😂|🤣|👍|🔥|💯)\b",
    re.IGNORECASE,
)
_FORMAL_PATTERNS = re.compile(
    r"\b(dear|sincerely|regards|pursuant|herewith|aforementioned|"
    r"kindly|please find|attached|per our|as per|i hope this|"
    r"i am writing|thank you for your|best regards|yours faithfully)\b",
    re.IGNORECASE,
)


def detect_language_type(text: str) -> LanguageType:
    """
    Heuristic language formality detection.
    Returns FORMAL, INFORMAL, SLANG, or MIXED.
    """
    has_slang  = bool(_SLANG_PATTERNS.search(text))
    has_formal = bool(_FORMAL_PATTERNS.search(text))

    if has_slang and has_formal:
        return LanguageType.MIXED
    if has_slang:
        return LanguageType.SLANG
    if has_formal:
        return LanguageType.FORMAL
    return LanguageType.INFORMAL


# ── Anchor embeddings cache ───────────────────────────────────────────────────
# Pre-computed once at first use. Each anchor is a representative sentence
# for that intent — chosen to maximise separation in embedding space.

_INTENT_ANCHORS: Dict[str, str] = {
    "question":       "I want to know about your business, products, and services. Tell me more about what you offer.",
    "interest":       "I am interested in learning more and would like to get started or schedule a demo.",
    "not_interested": "I am not interested, please do not contact me again, no thank you.",
    "negotiation":    "Can we discuss the price or terms? I want to negotiate a better deal.",
    "objection":      "I have concerns and doubts. I am not sure this is the right fit for me.",
    "reply":          "Hi, hello, thanks for reaching out. Just a quick reply to your message.",
    "follow_up":      "Following up on our previous conversation. Any update on what we discussed?",
    "support_request":"I need help with a technical issue, my account, or a problem I am facing.",
    "complaint":      "I am very unhappy with the service. This is a complaint about a problem.",
    "spam":           "Click here buy now limited time offer act fast exclusive deal free gift.",
    "promo":          "Special promotion discount newsletter announcement marketing campaign.",
    "abuse":          "This is terrible you are awful I hate this service you are useless.",
    "unsubscribe":    "Please remove me from your mailing list. I want to unsubscribe.",
    "out_of_office":  "I am out of office on vacation and will return on a future date.",
    "unknown":        "Random message with no clear intent or meaning whatsoever.",
}

_anchor_vecs: Optional[Dict[str, np.ndarray]] = None


def get_anchor_vectors() -> Dict[str, np.ndarray]:
    """Return pre-computed anchor embeddings (lazy, cached for process lifetime)."""
    global _anchor_vecs
    if _anchor_vecs is None:
        logger.info("Pre-computing intent anchor embeddings...")
        _anchor_vecs = {
            label: embed(text)
            for label, text in _INTENT_ANCHORS.items()
        }
        logger.info("Anchor embeddings ready.")
    return _anchor_vecs
