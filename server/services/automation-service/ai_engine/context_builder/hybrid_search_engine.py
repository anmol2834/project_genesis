"""
Hybrid Search Engine — User Data Retrieval
==========================================
Memory-aware, entity-tracking hybrid search engine.

Pipeline:
  1. Entity Memory     — extract active entity from conversation history
  2. Query Rewriting   — resolve pronouns ("it", "its") to actual entity
  3. Query Understanding — language normalization, typo correction
  4. Category Detection — map intent + keywords to data category
  5. Embedding          — e5-base-v2 (768-dim)
  6. Hybrid Search      — vector + entity boost + keyword match + attribute filter
  7. Scoring Engine     — weighted: entity(0.40) + vector(0.40) + keyword(0.20)
  8. Fallback Search    — if no results, retry with active entity only
  9. Context Compression — format top-k results into clean LLM-ready text

Multi-tenancy: every query is ALWAYS filtered by user_id. No exceptions.
Fail-safe: returns NO_CONTEXT string if no relevant data found.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

COLLECTION_NAME   = "user_data_entries"
VECTOR_SIZE       = 768
SEARCH_LIMIT      = 15
TOP_K             = 3
MIN_SCORE         = 0.45         # Slightly relaxed to allow entity-boosted results
NO_CONTEXT        = "NO_CONTEXT"

# Scoring weights — entity match is now equal to vector
W_ENTITY    = 0.40
W_VECTOR    = 0.40
W_KEYWORD   = 0.20
# Attribute and priority contribute within the entity/vector budget
# (kept for backward compat with _score_results formula)
W_ATTRIBUTE = 0.00   # folded into attr_score which feeds W_VECTOR
W_PRIORITY  = 0.00   # folded into priority_norm which feeds W_VECTOR

# ── Pronoun / reference words that signal entity resolution needed ────────────
# ONLY single words — multi-word phrases can't match word-level set intersection
_PRONOUN_WORDS = {
    "it", "its", "this", "that", "these", "those",
    "iska", "uska", "yeh", "woh", "iske", "uske",
}

# Short standalone keywords that imply "about the thing we were just discussing"
_STANDALONE_KEYWORDS = re.compile(
    r"^(price|cost|stock|available|details|info|kitna|hai|kya|rate|fee|"
    r"amount|quantity|delivery|shipping|refund|discount|offer)\??$",
    re.IGNORECASE,
)

# ── Product name extraction patterns ─────────────────────────────────────────
# Universal product/entity indicators — NOT business-specific.
# These are GENERIC words that appear near entity names across ALL business types.
# The system extracts Title Case sequences regardless of these words,
# but boosts confidence when these words are present.

_PRODUCT_INDICATORS = {
    # Physical goods
    "product", "item", "goods", "unit", "piece", "pack", "set", "kit",
    "bottle", "box", "bag", "bundle", "combo",
    # Services
    "service", "plan", "package", "subscription", "tier", "offering",
    "solution", "tool", "platform", "app", "software",
    # Generic business entities
    "course", "program", "membership", "license", "deal", "offer",
    # Hindi/Hinglish
    "cheez", "vastu", "saman", "maal",
}


# ── Entity Memory Engine ──────────────────────────────────────────────────────

def extract_active_entity(
    clean_history: List[Any],   # List[CleanMessage] from preprocessed
    last_ai_reply: str = "",
) -> Optional[str]:
    """
    Extract the most recently mentioned product/entity from conversation history.

    Strategy:
      1. Scan last AI reply for product names (most recent context)
      2. Scan last 2 user messages for product names
      3. Return the most recently mentioned entity, or None

    Returns:
      Entity string (e.g. "Scalp Scratcher") or None if no entity found.
    """
    candidates: List[Tuple[str, int]] = []  # (entity, recency_score)

    # Priority 1: last AI reply (most recent context — AI just mentioned this)
    if last_ai_reply:
        entities = _extract_entities_from_text(last_ai_reply)
        for e in entities:
            candidates.append((e, 10))  # highest priority

    # Priority 2: last 2 user messages (reverse order — most recent first)
    if clean_history:
        user_msgs = [m for m in reversed(clean_history) if m.direction == "incoming"]
        for i, msg in enumerate(user_msgs[:2]):
            entities = _extract_entities_from_text(msg.clean_content)
            for e in entities:
                candidates.append((e, 5 - i))  # recent = higher score

    if not candidates:
        return None

    # Return the entity with the highest recency score
    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0]


def _extract_entities_from_text(text: str) -> List[str]:
    """
    Extract product/entity names from a text string.

    Looks for:
      - Title Case sequences (e.g. "Neem Wooden Comb", "Scalp Scratcher")
      - Words adjacent to product indicators
    """
    if not text:
        return []

    entities = []
    text_lower = text.lower()

    # Find Title Case sequences (2-4 words) that look like product names
    words = text.split()
    i = 0
    while i < len(words):
        # Check if this word starts a Title Case sequence
        if words[i] and words[i][0].isupper() and words[i].isalpha():
            # Collect consecutive Title Case words
            seq = [words[i]]
            j = i + 1
            while j < len(words) and words[j] and words[j][0].isupper() and words[j].isalpha():
                seq.append(words[j])
                j += 1

            if len(seq) >= 2:  # At least 2 Title Case words = likely a product name
                entity = " ".join(seq)
                # Boost if any word is a product indicator
                if any(w.lower() in _PRODUCT_INDICATORS for w in seq):
                    entities.insert(0, entity)  # High priority
                else:
                    entities.append(entity)
            i = j
        else:
            i += 1

    # Also check for known product patterns in lowercase
    for indicator in _PRODUCT_INDICATORS:
        if indicator in text_lower:
            # Find the surrounding context (2 words before + indicator)
            pattern = re.compile(
                r"(\w+\s+){0,2}" + re.escape(indicator) + r"(\s+\w+){0,1}",
                re.IGNORECASE,
            )
            for m in pattern.finditer(text):
                candidate = m.group(0).strip().title()
                if len(candidate) > 3 and candidate not in entities:
                    entities.append(candidate)

    return entities[:3]  # Return top 3 candidates


def has_pronoun_reference(query: str) -> bool:
    """
    Returns True ONLY when the query is ambiguous and needs entity resolution.

    True cases:
      - Contains explicit pronouns: "its price", "this one", "woh wala"
      - Is a standalone keyword with no product name: "price?", "stock?"

    False cases:
      - Contains a specific product name: "wooden comb price"
      - Is a complete informational query: "neem comb details batao"
    """
    query_lower = query.lower().strip()
    words = set(re.findall(r"\b\w+\b", query_lower))

    # Explicit pronoun present
    if words & _PRONOUN_WORDS:
        return True

    # Standalone keyword only (no product name context)
    if _STANDALONE_KEYWORDS.match(query_lower):
        return True

    return False


def rewrite_query_with_entity(raw_query: str, active_entity: str) -> str:
    """
    Rewrite a pronoun-containing query by substituting the active entity.

    Examples:
      "I want to know its price" + "Scalp Scratcher"
        → "Scalp Scratcher price"
      "price?" + "Wooden Comb"
        → "Wooden Comb price"
      "stock hai?" + "Neem Wooden Comb"
        → "Neem Wooden Comb stock"
    """
    query = raw_query.strip()
    query_lower = query.lower()

    # Replace pronoun words with entity
    for pronoun in sorted(_PRONOUN_WORDS, key=len, reverse=True):
        if pronoun in query_lower:
            query = re.sub(
                r"\b" + re.escape(pronoun) + r"\b",
                active_entity,
                query,
                flags=re.IGNORECASE,
            )
            break

    # If query is very short (just a keyword), prepend entity
    if len(query.strip()) <= 20 and active_entity.lower() not in query.lower():
        query = f"{active_entity} {query.strip()}"

    logger.info(
        "QueryRewrite: %r + entity=%r → %r",
        raw_query[:60], active_entity, query[:80],
    )
    return query.strip()


# ── Entity match scorer ───────────────────────────────────────────────────────

def entity_match_score(entity: Optional[str], payload: Dict[str, Any]) -> float:
    """
    Score a result based on how well it matches the active entity.

    Checks title and keywords field for exact/partial entity match.
    Returns 0.0-1.0.
    """
    if not entity:
        return 0.0

    title    = str(payload.get("title", "")).lower()
    kw_list  = [str(k).lower() for k in (payload.get("keywords") or [])]
    combined = title + " " + " ".join(kw_list)

    entity_lower = entity.lower()
    entity_words = entity_lower.split()

    # Exact title match
    if entity_lower == title:
        return 1.0

    # All entity words present in title
    if all(w in title for w in entity_words):
        return 0.9

    # Most entity words present
    matches = sum(1 for w in entity_words if w in combined)
    if matches > 0:
        return round(0.5 + (matches / len(entity_words)) * 0.4, 3)

    return 0.0

# ── Query type detection ──────────────────────────────────────────────────────
# Greetings and casual messages must NEVER trigger a data search.

_GREETING_PATTERNS = re.compile(
    r"^(hi+|hey+|hello+|helo|hii+|hiii+|sup|what'?s up|howdy|"
    r"good\s+(morning|afternoon|evening|day|night)|"
    r"how are you|hope you'?re (well|good|doing well)|"
    r"namaste|namaskar|jai hind|"
    r"salam|assalam|assalamualaikum|"
    r"greetings?|dear\s+\w+|"
    r"thanks?|thank you|thx|ty|"
    r"ok|okay|k|got it|noted|sure|alright|fine|"
    r"bye|goodbye|see you|take care|"
    r"yes|no|yeah|nope|yep|nah)[.!?🙏👋😊]*\s*$",
    re.IGNORECASE,
)

# Informational keywords that REQUIRE a data search — universal, not product-specific
_INFORMATIONAL_KEYWORDS = re.compile(
    r"\b(price|prise|cost|rate|fee|amount|kitna|daam|paisa|charges|fees|"
    r"product|item|goods|service|plan|package|offering|solution|"
    r"prodict|prodcut|cheez|vastu|"
    r"offer|discount|deal|promo|chhoot|sale|coupon|cashback|"
    r"stock|available|availability|milega|inventory|units|"
    r"contact|phone|number|email|support|helpline|reach|"
    r"delivery|shipping|dispatch|courier|track|kab aayega|"
    r"refund|return|cancel|policy|warranty|terms|"
    r"service|plan|package|subscription|"
    r"about|company|who are you|mission|"
    r"how much|what is|tell me|batao|dikhao|chahiye|"
    r"buy|purchase|order|book|details|info|jankari|"
    r"features|benefits|specs|specifications|"
    r"guide|tutorial|faq|how to|explain|samjhao)\b",
    re.IGNORECASE,
)


def is_search_worthy(raw_query: str, intent: Optional[str] = None) -> bool:
    """
    Determine if a query warrants a data search.

    Returns False (skip search) for:
      - Pure greetings: "Hello", "Hi", "Good morning"
      - Casual acknowledgements: "Ok", "Thanks", "Sure"
      - Intents that never need product data

    Returns True (run search) for:
      - Any query containing informational keywords
      - Intents like question, interest, negotiation, support_request
    """
    # Intent-based gate — these intents never need product/pricing data
    _NO_SEARCH_INTENTS = {"reply", "spam", "promo", "unsubscribe", "out_of_office", "unknown"}
    if intent and intent in _NO_SEARCH_INTENTS:
        return False

    query = raw_query.strip()
    if not query:
        return False

    # Pure greeting / casual check (short messages only — long messages may contain info)
    if len(query) <= 60 and _GREETING_PATTERNS.match(query):
        return False

    # Must contain at least one informational keyword to warrant search
    if _INFORMATIONAL_KEYWORDS.search(query):
        return True

    # For longer messages without clear keywords, allow search for business intents
    _BUSINESS_INTENTS = {"question", "interest", "negotiation", "objection",
                         "complaint", "support_request", "follow_up", "not_interested"}
    if intent and intent in _BUSINESS_INTENTS:
        return True

    # Default: skip search for ambiguous short messages
    return len(query) > 80  # Only search for long messages without clear keywords

# ── Universal keyword maps ────────────────────────────────────────────────────
# Multi-language, typo-tolerant, synonym-aware keyword maps.
# Covers ALL business types: E-commerce, SaaS, Education, Healthcare, Legal, Services.
# NO business-specific words (no "comb", "scratcher", etc.)

_HINDI_TRANSLATIONS: Dict[str, str] = {
    # ── Price / Cost ──────────────────────────────────────────────────────
    "price kya hai":       "what is the price",
    "price batao":         "tell me the price",
    "kitna hai":           "how much is it",
    "kitne ka hai":        "how much does it cost",
    "daam kya hai":        "what is the price",
    "rate kya hai":        "what is the rate",
    "cost kya hai":        "what is the cost",
    "paisa kitna":         "how much money",
    "kitna paisa":         "how much money",
    "mehnga hai":          "is it expensive",
    "sasta hai":           "is it cheap",
    "kitne mein milega":   "how much will it cost",
    "kya rate hai":        "what is the rate",
    "fees kya hai":        "what are the fees",
    "charges kya hain":    "what are the charges",
    # ── Discount / Offer ─────────────────────────────────────────────────
    "discount hai":        "is there a discount",
    "chhoot hai":          "is there a discount",
    "chhoot":              "discount",
    "offer hai":           "is there an offer",
    "offer kya hai":       "what is the offer",
    "deal hai":            "is there a deal",
    "sale hai":            "is there a sale",
    "cashback milega":     "will I get cashback",
    "promo code hai":      "is there a promo code",
    # ── Product / Service ─────────────────────────────────────────────────
    "product kya hai":     "what is the product",
    "kya hai":             "what is it",
    "kya milta hai":       "what do you offer",
    "kya bechte ho":       "what do you sell",
    "batao":               "tell me",
    "dikhao":              "show me",
    "chahiye":             "I want",
    "mujhe chahiye":       "I want",
    "details do":          "give me details",
    "jankari do":          "give me information",
    "samjhao":             "explain",
    "bata do":             "tell me",
    "kya features hain":   "what are the features",
    "kya benefits hain":   "what are the benefits",
    # ── Stock / Availability ──────────────────────────────────────────────
    "stock hai":           "is it in stock",
    "available hai":       "is it available",
    "milega":              "will I get it",
    "nahi milega":         "not available",
    "khatam ho gaya":      "out of stock",
    "khatam":              "finished",
    "kab milega":          "when will I get it",
    "kitne din mein":      "how many days",
    # ── Contact / Support ─────────────────────────────────────────────────
    "number do":           "give me the number",
    "contact karo":        "contact me",
    "phone number":        "phone number",
    "helpline":            "helpline",
    "support chahiye":     "I need support",
    "help chahiye":        "I need help",
    "baat karni hai":      "I want to talk",
    "kaise contact karein":"how to contact",
    # ── Delivery / Shipping ───────────────────────────────────────────────
    "delivery kab":        "when is delivery",
    "delivery kab hogi":   "when will delivery happen",
    "shipping kab":        "when is shipping",
    "kab aayega":          "when will it arrive",
    "track karna hai":     "I want to track",
    "wapas karna":         "return it",
    "return karna hai":    "I want to return",
    # ── Refund / Policy ───────────────────────────────────────────────────
    "refund chahiye":      "I want a refund",
    "paise wapas":         "money back",
    "cancel karna hai":    "I want to cancel",
    "policy kya hai":      "what is the policy",
    "terms kya hain":      "what are the terms",
    # ── General ───────────────────────────────────────────────────────────
    "aur batao":           "tell me more",
    "aur kuch":            "anything else",
    "sab kuch batao":      "tell me everything",
    "poori jankari":       "complete information",
    "compare karo":        "compare",
    "difference kya hai":  "what is the difference",
    "best kya hai":        "what is the best",
    "recommend karo":      "recommend",
}

# ── Typo correction map ───────────────────────────────────────────────────────
_TYPO_MAP: Dict[str, str] = {
    # Price
    "prise":      "price",
    "proce":      "price",
    "prce":       "price",
    "priec":      "price",
    "pric":       "price",
    # Product
    "prodict":    "product",
    "prodcut":    "product",
    "prodect":    "product",
    "produt":     "product",
    "prduct":     "product",
    # Discount
    "chhoot":     "discount",
    "choot":      "discount",
    "dicount":    "discount",
    "discont":    "discount",
    "disount":    "discount",
    # Offer
    "offfer":     "offer",
    "offr":       "offer",
    "ofer":       "offer",
    # Contact
    "contect":    "contact",
    "contakt":    "contact",
    "numbr":      "number",
    "numbur":     "number",
    "phon":       "phone",
    # Stock
    "stok":       "stock",
    "stoock":     "stock",
    "stcok":      "stock",
    # Available
    "avialable":  "available",
    "availble":   "available",
    "availabel":  "available",
    # Shipping
    "shiping":    "shipping",
    "shpping":    "shipping",
    "shippng":    "shipping",
    # Delivery
    "delivry":    "delivery",
    "deliveri":   "delivery",
    "delvery":    "delivery",
    # Refund
    "refnd":      "refund",
    "refudn":     "refund",
    "refudn":     "refund",
    # Policy
    "polcy":      "policy",
    "polici":     "policy",
    "polisy":     "policy",
    # Service
    "servce":     "service",
    "servise":    "service",
    # Support
    "suport":     "support",
    "supprt":     "support",
    # Details
    "detials":    "details",
    "detals":     "details",
    # Features
    "fetures":    "features",
    "featurs":    "features",
}

# ── Synonym expansion ─────────────────────────────────────────────────────────
_SYNONYMS: Dict[str, List[str]] = {
    "price":      ["price", "cost", "rate", "fee", "amount", "charge", "pricing"],
    "discount":   ["discount", "offer", "deal", "promo", "sale", "chhoot", "cashback", "voucher"],
    "stock":      ["stock", "available", "inventory", "quantity", "units"],
    "contact":    ["contact", "phone", "number", "email", "support", "helpline", "reach"],
    "delivery":   ["delivery", "shipping", "dispatch", "courier", "logistics"],
    "refund":     ["refund", "return", "money back", "cancel", "cancellation"],
    "product":    ["product", "item", "goods", "offering", "service", "solution"],
    "service":    ["service", "plan", "package", "subscription", "offering"],
    "details":    ["details", "info", "information", "specs", "specifications"],
    "features":   ["features", "capabilities", "benefits", "highlights"],
    "policy":     ["policy", "terms", "conditions", "rules", "guidelines"],
    "about":      ["about", "company", "background", "history", "mission"],
    "help":       ["help", "support", "assist", "guide", "faq"],
    "buy":        ["buy", "purchase", "order", "book", "get"],
}

# ── Universal category keyword map ────────────────────────────────────────────
# Maps query keywords to Qdrant category values.
# Covers ALL business types — no product-specific words.

_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "product_service": [
        # English
        "product", "item", "goods", "service", "plan", "package", "offering",
        "solution", "tool", "software", "app", "platform", "course", "program",
        "what do you sell", "what you offer", "what do you have",
        "catalog", "inventory", "collection", "range",
        # Hinglish
        "kya milta hai", "kya bechte ho", "kya hai", "cheez", "vastu",
        "prodict", "prodcut",
    ],
    "pricing_payment": [
        # English
        "price", "cost", "rate", "fee", "amount", "charge", "pricing",
        "how much", "subscription", "billing", "payment", "pay",
        "monthly", "annual", "yearly", "per month", "per year",
        "plan cost", "plan price", "tier", "budget", "affordable",
        "expensive", "cheap", "free", "paid", "premium", "basic",
        # Hinglish
        "kitna", "daam", "paisa", "paise", "prise", "proce",
        "kitne mein", "kya rate", "fees", "charges",
    ],
    "offers_promotions": [
        # English
        "discount", "offer", "deal", "promo", "sale", "coupon",
        "cashback", "voucher", "code", "limited time", "special offer",
        "festival", "seasonal", "clearance", "flash sale",
        "referral", "loyalty", "reward", "bonus",
        # Hinglish
        "chhoot", "choot", "offfer", "offr", "cashback milega",
    ],
    "contact_support": [
        # English
        "contact", "phone", "number", "email", "support", "help",
        "helpline", "reach", "call", "whatsapp", "chat", "live chat",
        "customer care", "customer service", "assistance",
        "ticket", "complaint", "issue", "problem",
        # Hinglish
        "contect", "numbr", "baat karni hai", "help chahiye",
        "support chahiye", "kaise contact",
    ],
    "delivery_shipping": [
        # English
        "delivery", "shipping", "dispatch", "courier", "track",
        "when will", "how long", "return", "exchange", "logistics",
        "estimated", "arrival", "transit", "tracking",
        # Hinglish
        "delivry", "shiping", "kab aayega", "kab milega",
        "delivery kab", "track karna",
    ],
    "policies_legal": [
        # English
        "policy", "terms", "conditions", "warranty", "guarantee",
        "refund", "return policy", "cancellation", "legal",
        "privacy", "data", "gdpr", "compliance",
        # Hinglish
        "polcy", "polici", "refund chahiye", "paise wapas",
        "cancel karna", "wapas karna",
    ],
    "educational_content": [
        # English
        "how to", "guide", "tutorial", "faq", "help", "explain",
        "what is", "how does", "steps", "instructions", "learn",
        "documentation", "manual", "walkthrough", "demo",
        # Hinglish
        "kaise karte hain", "samjhao", "batao kaise",
        "kya hota hai", "sikhna hai",
    ],
    "company_info": [
        # English
        "about", "company", "who are you", "background", "founded",
        "team", "mission", "vision", "history", "story",
        "headquarters", "location", "office", "certifications",
        "awards", "recognition", "media",
        # Hinglish
        "kaun ho aap", "company ke baare mein", "kahan se ho",
    ],
}

# Intent → category mapping (from automation-service intent engine)
_INTENT_TO_CATEGORY: Dict[str, Optional[str]] = {
    "question":        None,          # detect from keywords
    "interest":        "product_service",
    "negotiation":     "pricing_payment",
    "objection":       None,
    "complaint":       "contact_support",
    "support_request": "contact_support",
    "follow_up":       None,
    "not_interested":  None,
    "reply":           None,
    "unknown":         None,
}

# ── Embedding model ───────────────────────────────────────────────────────────
# Uses e5-base-v2 (768-dim) to match the user_data_entries collection.
# SEPARATE from the all-MiniLM-L6-v2 used by the intent engine.

_e5_model = None


def _get_e5_model():
    """Load e5-base-v2 once per process. Raises on failure — model is confirmed installed."""
    global _e5_model
    if _e5_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("HybridSearchEngine: loading intfloat/e5-base-v2...")
        _e5_model = SentenceTransformer("intfloat/e5-base-v2")
        logger.info("HybridSearchEngine: e5-base-v2 ready (768-dim)")
    return _e5_model


def _embed_query(text: str) -> List[float]:
    """Embed a query string with e5-base-v2 using 'query:' prefix (required by e5 models)."""
    model = _get_e5_model()
    vec = model.encode(f"query: {text[:512]}", normalize_embeddings=True)
    return vec.tolist()


# ── Language Detection + Translation Engine ───────────────────────────────────
# Enterprise-grade query normalization:
#   1. Fast-path: Hinglish phrase map (no network, instant)
#   2. Script detection: identify non-Latin scripts
#   3. Translation: deep-translator GoogleTranslator (free, no API key)
#   4. LRU cache: avoid repeated network calls for same query
#   5. Graceful fallback: original text if translation fails

# Script detection patterns — covers all major non-English scripts
_DEVANAGARI_RE  = re.compile(r"[\u0900-\u097F]")   # Hindi, Marathi, Nepali
_ARABIC_RE      = re.compile(r"[\u0600-\u06FF]")   # Arabic, Urdu, Persian
_CJK_RE         = re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]")  # Chinese, Japanese, Korean
_CYRILLIC_RE    = re.compile(r"[\u0400-\u04FF]")   # Russian, Ukrainian, etc.
_LATIN_ONLY_RE  = re.compile(r"^[\x00-\x7F\s\d\W]+$")  # Pure ASCII/Latin

# Minimum non-ASCII ratio to trigger translation (avoids translating Hinglish)
_NON_ASCII_THRESHOLD = 0.30

# Translation cache — keyed by (text, source_lang)
# functools.lru_cache can't handle mutable args, so we use a simple dict cache
_translation_cache: Dict[str, str] = {}
_CACHE_MAX_SIZE = 500

_translator_available: Optional[bool] = None  # None = not yet checked


def _is_translator_available() -> bool:
    """Check if deep-translator is installed. Cached after first check."""
    global _translator_available
    if _translator_available is None:
        try:
            from deep_translator import GoogleTranslator  # noqa: F401
            _translator_available = True
        except ImportError:
            _translator_available = False
            logger.warning(
                "deep-translator not installed — translation disabled. "
                "Install with: pip install deep-translator==1.9.1"
            )
    return _translator_available


def detect_script(text: str) -> str:
    """
    Detect the dominant script of the text.

    Returns: "devanagari" | "arabic" | "cjk" | "cyrillic" | "latin" | "mixed"
    """
    if _DEVANAGARI_RE.search(text):
        return "devanagari"
    if _ARABIC_RE.search(text):
        return "arabic"
    if _CJK_RE.search(text):
        return "cjk"
    if _CYRILLIC_RE.search(text):
        return "cyrillic"
    return "latin"


def needs_translation(text: str) -> bool:
    """
    Determine if the text needs translation to English.

    Rules:
      - Pure Latin/ASCII → no translation needed (English or Hinglish)
      - Non-Latin script detected → translate
      - High ratio of non-ASCII chars → translate
    """
    if not text or len(text.strip()) < 3:
        return False

    script = detect_script(text)
    if script != "latin":
        return True

    # Check non-ASCII ratio for mixed scripts
    non_ascii = sum(1 for c in text if ord(c) > 127)
    ratio = non_ascii / max(len(text), 1)
    return ratio >= _NON_ASCII_THRESHOLD


def translate_to_english(text: str) -> str:
    """
    Translate text to English using deep-translator (GoogleTranslator).

    Features:
      - LRU cache: same query never translated twice
      - Auto language detection: no need to specify source language
      - Graceful fallback: returns original text if translation fails
      - Rate-limit safe: short text only (max 500 chars)

    Returns:
      Translated English text, or original text if translation fails/unavailable.
    """
    if not text or not text.strip():
        return text

    # Check cache first
    cache_key = text.strip().lower()[:200]
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    if not _is_translator_available():
        return text

    try:
        from deep_translator import GoogleTranslator

        # Truncate to avoid rate limits (500 chars is enough for a query)
        text_to_translate = text.strip()[:500]

        translated = GoogleTranslator(source="auto", target="en").translate(text_to_translate)

        if not translated or not translated.strip():
            return text

        result = translated.strip()

        # Cache the result (evict oldest if cache is full)
        if len(_translation_cache) >= _CACHE_MAX_SIZE:
            # Remove oldest 10% of entries
            keys_to_remove = list(_translation_cache.keys())[:_CACHE_MAX_SIZE // 10]
            for k in keys_to_remove:
                del _translation_cache[k]

        _translation_cache[cache_key] = result

        logger.info(
            "Translation: %r → %r",
            text[:60], result[:60],
        )
        return result

    except Exception as exc:
        # Never block the pipeline — fall back to original text
        logger.warning(
            "Translation failed (non-fatal): %s — using original text: %r",
            exc, text[:60],
        )
        return text


# ── Query Understanding ───────────────────────────────────────────────────────

def normalize_query(raw_query: str) -> Tuple[str, List[str]]:
    """
    Normalize a raw query string into clean English + keywords.

    Pipeline:
      1. Fast-path: apply Hinglish phrase map (no network, instant)
      2. Language detection: check if non-English script present
      3. Translation: deep-translator GoogleTranslator (free, auto-detect)
      4. Typo correction: fix common misspellings
      5. Keyword extraction: remove stop words, extract meaningful terms
      6. Synonym expansion: boost recall with related terms

    Returns:
      (clean_english_query, keywords_list)
    """
    text = raw_query.strip().lower()

    # ── Step 1: Fast-path Hinglish phrase map ─────────────────────────────
    # Apply longest-match first to avoid partial replacements
    sorted_phrases = sorted(_HINDI_TRANSLATIONS.keys(), key=len, reverse=True)
    for phrase in sorted_phrases:
        if phrase in text:
            text = text.replace(phrase, _HINDI_TRANSLATIONS[phrase])

    # ── Step 2: Translation for non-Latin scripts ─────────────────────────
    # Only translate if non-Latin script detected (Devanagari, Arabic, CJK, etc.)
    # Hinglish (Latin script with Hindi words) is handled by the phrase map above
    if needs_translation(text):
        text = translate_to_english(text)
        text = text.lower()

    # ── Step 3: Typo correction (word-level) ─────────────────────────────
    words = text.split()
    corrected = []
    for word in words:
        clean_word = re.sub(r"[^\w]", "", word)
        corrected.append(_TYPO_MAP.get(clean_word, word))
    text = " ".join(corrected)

    # ── Step 4: Extract keywords (meaningful words, no stop words) ────────
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "i", "me", "my", "we", "our", "you", "your", "it", "its",
        "this", "that", "these", "those", "and", "or", "but", "in",
        "on", "at", "to", "for", "of", "with", "by", "from", "up",
        "about", "into", "through", "during", "before", "after",
        "please", "hi", "hello", "hey", "thanks", "thank",
        "want", "need", "like", "know", "tell", "give", "show",
    }

    keywords = [
        w for w in re.findall(r"\b\w+\b", text)
        if len(w) > 2 and w not in stop_words
    ]

    # ── Step 5: Synonym expansion ─────────────────────────────────────────
    expanded_keywords = list(keywords)
    for kw in keywords:
        if kw in _SYNONYMS:
            expanded_keywords.extend(_SYNONYMS[kw])

    # Deduplicate while preserving order
    seen: set = set()
    final_keywords = []
    for kw in expanded_keywords:
        if kw not in seen:
            final_keywords.append(kw)
            seen.add(kw)

    return text.strip(), final_keywords[:20]


def detect_category(
    clean_query: str,
    keywords: List[str],
    intent: Optional[str] = None,
) -> Optional[str]:
    """
    Detect the most likely data category from query + intent.

    Returns a category string (e.g. "pricing_payment") or None if ambiguous.
    None means: search all categories (no category filter applied).
    """
    # Intent-based category hint
    if intent and intent in _INTENT_TO_CATEGORY:
        hint = _INTENT_TO_CATEGORY[intent]
        if hint:
            return hint

    # Keyword-based category scoring
    scores: Dict[str, int] = {cat: 0 for cat in _CATEGORY_KEYWORDS}
    query_words = set(clean_query.lower().split() + keywords)

    for category, cat_keywords in _CATEGORY_KEYWORDS.items():
        for kw in cat_keywords:
            if kw in clean_query or kw in query_words:
                scores[category] += 1

    best_cat = max(scores, key=lambda c: scores[c])
    best_score = scores[best_cat]

    if best_score == 0:
        return None  # No category detected — search all

    # Require at least 1 keyword match to apply category filter
    return best_cat if best_score >= 1 else None


# ── Attribute filter builder ──────────────────────────────────────────────────

def build_attribute_filters(
    clean_query: str,
    keywords: List[str],
    category: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Build Qdrant filter conditions based on query semantics.

    Returns a list of filter dicts to be combined with 'must' in the Qdrant query.
    These are ADDITIONAL filters on top of the mandatory user_id filter.
    """
    filters = []

    # Stock availability filter: "stock hai", "available", "in stock"
    stock_keywords = {"stock", "available", "availability", "in stock", "milega"}
    if any(kw in stock_keywords for kw in keywords) or "stock" in clean_query:
        # Filter: attributes.stock > 0 (items with stock available)
        filters.append({
            "key":   "attributes.stock",
            "range": {"gt": 0},
        })

    # Active status filter: most queries should only see active items
    # Exception: "out of stock" queries should see out_of_stock items
    out_of_stock_keywords = {"out of stock", "khatam", "nahi milega", "unavailable"}
    if any(kw in out_of_stock_keywords for kw in keywords):
        filters.append({
            "key":   "status",
            "match": {"value": "out_of_stock"},
        })
    elif category in ("product_service", "pricing_payment", "offers_promotions"):
        # For product/pricing/offer queries, prefer active items
        filters.append({
            "key":   "status",
            "match": {"value": "active"},
        })

    return filters


# ── Keyword match scorer ──────────────────────────────────────────────────────

def keyword_match_score(keywords: List[str], payload: Dict[str, Any]) -> float:
    """
    Score a Qdrant result based on keyword overlap with its payload.

    Checks: title, search_text, keywords field, attributes.
    Returns a score in [0, 1].
    """
    if not keywords:
        return 0.0

    # Build a searchable text from the payload
    title       = str(payload.get("title", "")).lower()
    search_text = str(payload.get("search_text", "")).lower()
    kw_list     = [str(k).lower() for k in (payload.get("keywords") or [])]
    attrs       = payload.get("attributes") or {}
    attr_text   = " ".join(str(v).lower() for v in attrs.values())

    combined = f"{title} {search_text} {' '.join(kw_list)} {attr_text}"

    matches = sum(1 for kw in keywords if kw.lower() in combined)
    return min(1.0, matches / max(len(keywords), 1))


# ── Attribute match scorer ────────────────────────────────────────────────────

def attribute_match_score(
    clean_query: str,
    keywords: List[str],
    payload: Dict[str, Any],
) -> float:
    """
    Score based on how well the entry's attributes match the query intent.

    Checks:
      - Status matches query intent (active for availability queries)
      - Price range matches if query mentions price
      - Stock > 0 for availability queries
    """
    score = 0.0
    attrs = payload.get("attributes") or {}

    # Status check
    status = str(attrs.get("status", "")).lower()
    if status == "active":
        score += 0.5   # Active items are always preferred
    elif status == "limited_stock":
        score += 0.3
    elif status == "out_of_stock":
        # Only good if query is specifically about out-of-stock
        if any(kw in {"out of stock", "khatam", "unavailable"} for kw in keywords):
            score += 0.4
        else:
            score -= 0.2  # Penalize out-of-stock for general queries

    # Stock availability
    stock = attrs.get("stock")
    if stock is not None:
        try:
            if float(stock) > 0:
                score += 0.3
        except (ValueError, TypeError):
            pass

    # Price relevance for pricing queries
    price_keywords = {"price", "cost", "rate", "how much", "kitna", "daam"}
    if any(kw in price_keywords for kw in keywords):
        price = attrs.get("price")
        if price is not None:
            score += 0.2   # Has price data — relevant for pricing query

    return max(0.0, min(1.0, score))


# ── Result formatter ──────────────────────────────────────────────────────────

def format_result(payload: Dict[str, Any], score: float) -> str:
    """
    Format a single Qdrant result into a clean, LLM-readable block.

    Category-aware formatting:
      product:  "AgriFly Pro: ₹2500 | Agriculture Drone | Crop monitoring drone. Available."
      contact:  "Customer Support - Amit Sharma | Email: support@... | Phone: +91-... | 9 AM - 6 PM"
      offer:    "Student Offer: 25% discount for students on training programs. Valid until 2026-09-30."
    """
    title    = payload.get("title", "Unknown")
    attrs    = payload.get("attributes") or {}
    cat      = payload.get("category", "")
    # Use structured_data if available (new schema), fall back to attrs
    sd       = payload.get("structured_data") or {}

    # ── CONTACT SUPPORT ───────────────────────────────────────────────────
    if cat == "contact_support":
        parts = [title]

        email = attrs.get("email") or sd.get("email")
        if email:
            parts.append(f"Email: {email}")

        phone = attrs.get("phone") or sd.get("phone")
        if phone:
            parts.append(f"Phone: {phone}")

        hours = attrs.get("working_hours") or sd.get("working_hours") or sd.get("support_hours")
        if hours:
            parts.append(f"Available: {hours}")

        website = sd.get("website")
        if website:
            parts.append(f"Website: {website}")

        return " | ".join(parts)

    # ── OFFERS / PROMOTIONS ───────────────────────────────────────────────
    if cat == "offers_promotions":
        parts = [title]

        discount = attrs.get("discount") or sd.get("discount")
        if discount is not None:
            try:
                parts.append(f"{int(float(discount))}% discount")
            except (ValueError, TypeError):
                parts.append(f"{discount} discount")

        desc = attrs.get("description") or sd.get("description") or sd.get("details")
        if desc:
            parts.append(str(desc)[:150])

        valid_until = attrs.get("valid_until") or sd.get("valid_until") or sd.get("expiry_date")
        if valid_until:
            parts.append(f"Valid until: {valid_until}")

        promo = sd.get("promo_code")
        if promo:
            parts.append(f"Code: {promo}")

        return " | ".join(parts)

    # ── PRODUCT / SERVICE (default) ───────────────────────────────────────
    parts = [title]

    price = attrs.get("price") or sd.get("price")
    if price is not None:
        try:
            parts.append(f"₹{int(float(price))}")
        except (ValueError, TypeError):
            parts.append(f"₹{price}")

    category_label = attrs.get("category") or sd.get("category")
    if category_label:
        parts.append(str(category_label))

    desc = attrs.get("description") or sd.get("description") or sd.get("features")
    if desc:
        parts.append(str(desc)[:150])

    stock = attrs.get("stock") or sd.get("stock")
    if stock is not None:
        try:
            stock_int = int(float(stock))
            parts.append(f"In Stock ({stock_int} units)" if stock_int > 0 else "Out of Stock")
        except (ValueError, TypeError):
            pass
    else:
        status = attrs.get("status", "")
        if status == "limited_stock":
            parts.append("Limited Stock")
        elif status in ("active", ""):
            parts.append("Available")
        elif status == "out_of_stock":
            parts.append("Out of Stock")

    supplier = attrs.get("supplier") or sd.get("supplier")
    if supplier:
        parts.append(f"by {supplier}")

    return " | ".join(parts)


# ── Main Engine ───────────────────────────────────────────────────────────────

class HybridSearchEngine:
    """
    Hybrid search engine for user_data_entries collection.

    Combines:
      - Vector similarity (e5-base-v2, 768-dim)
      - Keyword matching (title + search_text + keywords field)
      - Attribute filtering (stock, status, price)
      - Priority scoring (active > limited > out_of_stock)

    Multi-tenancy: every query is filtered by user_id.
    Fail-safe: returns NO_CONTEXT if no relevant data found.
    """

    async def search(
        self,
        user_id: str,
        raw_query: str,
        intent: Optional[str] = None,
        top_k: int = TOP_K,
        clean_history: Optional[List[Any]] = None,
        last_ai_reply: str = "",
    ) -> Tuple[str, Optional[str]]:
        """
        Run the full memory-aware hybrid search pipeline.

        Returns:
          (context_string, active_entity)
          context_string: formatted data for LLM, or NO_CONTEXT
          active_entity:  the entity used/found (for prompt injection)
        """
        if not raw_query.strip():
            return NO_CONTEXT, None

        # ── Gate: skip search for non-informational queries ───────────────
        # But first check if there's an active entity — even "price?" needs search
        active_entity = extract_active_entity(clean_history or [], last_ai_reply)

        if not is_search_worthy(raw_query, intent):
            # Even for non-informational queries, if there's an active entity
            # and the query is a short reference, still search
            if active_entity and has_pronoun_reference(raw_query):
                logger.info(
                    "HybridSearch: pronoun query with entity=%r — proceeding | user=%s",
                    active_entity, user_id[:8],
                )
            else:
                logger.info(
                    "HybridSearch: skipped (not search-worthy) | user=%s intent=%s query=%r",
                    user_id[:8], intent, raw_query[:60],
                )
                return NO_CONTEXT, active_entity

        # ── Step 1: Query rewriting (entity resolution) ───────────────────
        rewritten_query = raw_query
        if active_entity and has_pronoun_reference(raw_query):
            rewritten_query = rewrite_query_with_entity(raw_query, active_entity)

        # ── Step 2: Query understanding ───────────────────────────────────
        clean_query, keywords = normalize_query(rewritten_query)
        category = detect_category(clean_query, keywords, intent)

        logger.info(
            "HybridSearch: user=%s query=%r rewritten=%r category=%s entity=%r keywords=%s",
            user_id[:8], raw_query[:60], rewritten_query[:60], category,
            active_entity, keywords[:6],
        )

        # ── Step 3: Embed the normalized query ────────────────────────────
        loop = asyncio.get_event_loop()
        try:
            query_vec = await loop.run_in_executor(None, lambda: _embed_query(clean_query))
        except Exception as exc:
            logger.warning("HybridSearch: embedding failed: %s", exc)
            return NO_CONTEXT, active_entity

        # ── Step 4: Build Qdrant filters ──────────────────────────────────
        attr_filters = build_attribute_filters(clean_query, keywords, category)

        # ── Step 5: Vector search with filters ────────────────────────────
        raw_results = await self._vector_search(
            user_id=user_id,
            query_vec=query_vec,
            category=category,
            attr_filters=attr_filters,
            limit=SEARCH_LIMIT,
        )

        # ── Step 6: Fallback — if no results, retry with entity only ──────
        if not raw_results and active_entity:
            logger.info(
                "HybridSearch: no results — retrying with entity=%r | user=%s",
                active_entity, user_id[:8],
            )
            fallback_query, fallback_kw = normalize_query(active_entity)
            fallback_vec = await loop.run_in_executor(None, lambda: _embed_query(fallback_query))
            raw_results = await self._vector_search(
                user_id=user_id,
                query_vec=fallback_vec,
                category=None,   # No category filter on fallback
                attr_filters=[],
                limit=SEARCH_LIMIT,
            )
            if raw_results:
                keywords = fallback_kw  # Use fallback keywords for scoring
                clean_query = fallback_query

        if not raw_results:
            logger.info("HybridSearch: no results for user=%s query=%r", user_id[:8], raw_query[:60])
            return NO_CONTEXT, active_entity

        # ── Step 7: Hybrid scoring with entity boost ──────────────────────
        scored = self._score_results(raw_results, clean_query, keywords, active_entity)

        # ── Step 8: Filter + rank ─────────────────────────────────────────
        ranked = [r for r in scored if r["final_score"] >= MIN_SCORE]
        ranked.sort(key=lambda r: r["final_score"], reverse=True)
        top_results = ranked[:top_k]

        if not top_results:
            # If entity-boosted results exist but below threshold, include top 1
            if active_entity and scored:
                top_scored = sorted(scored, key=lambda r: -r["final_score"])
                if top_scored[0]["entity_score"] > 0.5:
                    top_results = [top_scored[0]]
                    logger.info("HybridSearch: entity-boosted result included below threshold")

        if not top_results:
            return NO_CONTEXT, active_entity

        # ── Step 9: Format context ────────────────────────────────────────
        # Update active_entity from top result if not already set
        if not active_entity and top_results:
            active_entity = top_results[0]["payload"].get("title")

        context = self._format_context(top_results, category)

        logger.info(
            "HybridSearch: returning %d results | user=%s category=%s entity=%r",
            len(top_results), user_id[:8], category, active_entity,
        )
        return context, active_entity

    async def _vector_search(
        self,
        user_id: str,
        query_vec: List[float],
        category: Optional[str],
        attr_filters: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Execute Qdrant vector search with mandatory user_id filter
        and optional category + attribute filters.
        """
        loop = asyncio.get_event_loop()
        try:
            from shared.vector_db import get_qdrant_client
            from qdrant_client.models import (
                Filter, FieldCondition, MatchValue, Range,
            )

            client = get_qdrant_client()

            # Build filter conditions — user_id is ALWAYS required
            must_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            ]

            # Category filter (optional — None means search all categories)
            if category:
                must_conditions.append(
                    FieldCondition(key="category", match=MatchValue(value=category))
                )

            # Attribute filters (stock, status, etc.)
            for af in attr_filters:
                if "match" in af:
                    must_conditions.append(
                        FieldCondition(key=af["key"], match=MatchValue(value=af["match"]["value"]))
                    )
                elif "range" in af:
                    r = af["range"]
                    must_conditions.append(
                        FieldCondition(
                            key=af["key"],
                            range=Range(
                                gt=r.get("gt"),
                                gte=r.get("gte"),
                                lt=r.get("lt"),
                                lte=r.get("lte"),
                            ),
                        )
                    )

            search_filter = Filter(must=must_conditions)

            results = await loop.run_in_executor(
                None,
                lambda: client.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=query_vec,
                    query_filter=search_filter,
                    limit=limit,
                    score_threshold=0.20,  # Low threshold — re-ranking handles quality
                    with_payload=True,
                ),
            )

            return [
                {"score": float(r.score), "payload": r.payload or {}}
                for r in results
            ]

        except Exception as exc:
            logger.warning("HybridSearch: vector search failed: %s", exc)
            return []

    def _score_results(
        self,
        raw_results: List[Dict[str, Any]],
        clean_query: str,
        keywords: List[str],
        active_entity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Apply the hybrid scoring formula to each result.

        Formula:
          final_score = W_ENTITY * entity_score
                      + W_VECTOR * vector_score
                      + W_KEYWORD * keyword_score

        entity_score: 0.0-1.0 based on title/keyword match with active_entity
        vector_score: cosine similarity from Qdrant
        keyword_score: keyword overlap + attribute relevance + priority boost
        """
        scored = []
        for r in raw_results:
            payload      = r["payload"]
            vector_score = r["score"]

            # Entity match score (0.0-1.0)
            ent_score = entity_match_score(active_entity, payload) if active_entity else 0.0

            # Keyword match score (0.0-1.0)
            kw_score = keyword_match_score(keywords, payload)

            # Attribute relevance (folds into keyword score as a bonus)
            attr_bonus = attribute_match_score(clean_query, keywords, payload) * 0.3

            # Priority bonus (active items ranked higher)
            raw_priority  = int((payload.get("attributes") or {}).get("priority_score", 2))
            priority_bonus = (raw_priority - 1) / 2.0 * 0.1  # max +0.1

            # Combined keyword score with bonuses
            combined_kw = min(1.0, kw_score + attr_bonus + priority_bonus)

            final_score = (
                W_ENTITY  * ent_score    +
                W_VECTOR  * vector_score +
                W_KEYWORD * combined_kw
            )

            scored.append({
                "payload":       payload,
                "vector_score":  round(vector_score, 4),
                "entity_score":  round(ent_score, 4),
                "kw_score":      round(combined_kw, 4),
                "final_score":   round(final_score, 4),
            })

        return scored

    def _format_context(
        self,
        top_results: List[Dict[str, Any]],
        category: Optional[str],
    ) -> str:
        """
        Format top results into a clean, compressed context string for the LLM.

        Format:
          Relevant Data:
            - Wooden Comb: ₹299 | In Stock (150 units) | by Cavolil Suppliers
            - Neem Wooden Comb: ₹349 | In Stock (80 units) | by GreenCare Pvt Ltd
        """
        lines = []
        for r in top_results:
            line = format_result(r["payload"], r["final_score"])
            if line:
                lines.append(f"  - {line}")

        if not lines:
            return NO_CONTEXT

        cat_label = (category or "").replace("_", " ").title() if category else "Business Data"
        header = f"Relevant {cat_label}:"
        return header + "\n" + "\n".join(lines)


# ── Singleton ─────────────────────────────────────────────────────────────────

_engine_instance: Optional[HybridSearchEngine] = None


def get_hybrid_search_engine() -> HybridSearchEngine:
    """Return the singleton HybridSearchEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = HybridSearchEngine()
    return _engine_instance
