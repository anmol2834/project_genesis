"""
Intent Engine — Rule Engine
============================
Keyword and regex-based signal detection.

Design principles:
  - NEVER classify on a single keyword alone.
  - Rules produce HINTS and SCORES, not final decisions.
  - The classifier fuses rule signals with model + semantic signals.
  - Spam requires confidence > 0.9 — rules alone cannot trigger it.
  - Mixed-intent messages are handled by scoring both signals and letting
    the fusion layer decide.

Output: RuleSignal (schema.py)
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .schema import RiskFlags, RuleSignal
from .utils import clean_text, detect_language_type
from ..schemas.intent_schema import IntentType, SubIntent, SentimentType


# ═══════════════════════════════════════════════════════════════════════════════
# Pattern definitions
# ═══════════════════════════════════════════════════════════════════════════════

# ── Unsubscribe ───────────────────────────────────────────────────────────────
_UNSUB_RE = re.compile(
    r"\b(unsubscribe|opt.?out|remove me|stop emailing|"
    r"take me off|no more emails?|don.?t (email|contact|message) me|"
    # Hindi/Hinglish opt-out phrases
    r"contact mat karo|contact mat karna|contact na karo|contact na karna|"
    r"message mat karo|message mat karna|message na karo|"
    r"band karo|band kar do|band kar|rokh do|rokh|"
    r"mujhe nahi chahiye|nahi chahiye|nahi janna|nahi sunna|"
    r"mujhe disturb mat|disturb mat karo|pareshan mat karo|"
    r"mujhe contact|kabhi contact mat)\b",
    re.IGNORECASE,
)

# ── Pricing / interest ────────────────────────────────────────────────────────
_PRICING_RE = re.compile(
    r"\b(pric(e|ing|es)|how much|cost|fee|rate|plan|package|"
    r"subscription|quote|budget|afford|cheap|expensive)\b",
    re.IGNORECASE,
)
_INTEREST_RE = re.compile(
    r"\b(interested|tell me more|learn more|more info|"
    r"sounds good|love to|would like|can you send|please share|"
    r"sign me up|sign up|get started|let.?s (talk|chat|connect|discuss))\b",
    re.IGNORECASE,
)
_DEMO_RE = re.compile(
    r"\b(demo|trial|free trial|schedule|book a call|"
    r"set up a meeting|walkthrough|show me)\b",
    re.IGNORECASE,
)
_MEETING_RE = re.compile(
    r"\b(meeting|call|schedule|calendar|availability|"
    r"book|appointment|zoom|teams|google meet)\b",
    re.IGNORECASE,
)

# ── Objection / not interested ────────────────────────────────────────────────
_NOT_INTERESTED_RE = re.compile(
    r"\b(not interested|no thanks|no thank you|pass|"
    r"don.?t need|not (looking|relevant|right)|wrong person|"
    r"already (have|using|covered)|not a fit|not for (me|us))\b",
    re.IGNORECASE,
)
_OBJECTION_RE = re.compile(
    r"\b(concern|hesitant|not sure|worried|doubt|"
    r"seems (expensive|risky|complicated)|why should|"
    r"prove|evidence|guarantee|what if)\b",
    re.IGNORECASE,
)

# ── Complaint ─────────────────────────────────────────────────────────────────
_COMPLAINT_RE = re.compile(
    r"\b(complain|unhappy|disappointed|frustrated|terrible|"
    r"awful|horrible|worst|broken|doesn.?t work|not working|"
    r"issue|problem|bug|error|failed|refund|money back|"
    r"waste of (time|money)|scam|fraud|rip.?off)\b",
    re.IGNORECASE,
)

# ── Support ───────────────────────────────────────────────────────────────────
_SUPPORT_RE = re.compile(
    r"\b(help|support|assist|can.?t (login|access|find|use)|"
    r"how do i|how to|trouble|stuck|confused|reset|password|"
    r"account|billing issue|charge|invoice)\b",
    re.IGNORECASE,
)

# ── Abuse / profanity ─────────────────────────────────────────────────────────
_ABUSE_RE = re.compile(
    r"\b(idiot|stupid|moron|trash|garbage|f+u+c+k|sh[i1]t|"
    r"a+s+s+h+o+l+e|b[i1]tch|bastard|hate you|go to hell|"
    r"you suck|terrible service|absolute garbage|"
    # Hindi/Hinglish abuse patterns
    r"randi|madarchod|bhenchod|chutiya|gaandu|harami|"
    r"bakwaas|bakwas|bekar|ullu|gadha|kamina|kamine|"
    r"besharam|nalayak|bewakoof|pagal|saala|sala)\b",
    re.IGNORECASE,
)

# ── Threat / legal ────────────────────────────────────────────────────────────
_THREAT_RE = re.compile(
    r"\b(sue|lawsuit|legal action|attorney|lawyer|court|"
    r"report you|file a complaint|consumer protection|"
    r"i will (sue|report|take action)|threatening)\b",
    re.IGNORECASE,
)

# ── Spam / promo patterns ─────────────────────────────────────────────────────
# These are WEAK signals — require multiple matches + length to fire
_SPAM_WORDS_RE = re.compile(
    r"\b(click here|buy now|act now|limited (time|offer)|"
    r"exclusive deal|free gift|you.?ve (won|been selected)|"
    r"congratulations|claim your|don.?t miss|order now|"
    r"100% free|no obligation|risk.?free|guaranteed|"
    r"make money|earn \$|work from home|lose weight fast)\b",
    re.IGNORECASE,
)
_CTA_RE = re.compile(
    r"\b(click|shop now|get yours|subscribe|join now|"
    r"sign up today|register now|download now|start free)\b",
    re.IGNORECASE,
)

# ── Links ─────────────────────────────────────────────────────────────────────
_LINK_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

# ── PII ───────────────────────────────────────────────────────────────────────
_PII_RE = re.compile(
    r"\b(\d{3}[-.\s]?\d{2}[-.\s]?\d{4}|"   # SSN
    r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}|"  # Credit card
    r"\b\d{10,}\b)\b",                       # Long number sequences
    re.IGNORECASE,
)

# ── Out of office ─────────────────────────────────────────────────────────────
_OOO_RE = re.compile(
    r"\b(out of (office|town)|on vacation|on leave|"
    r"away until|will return|auto.?reply|automatic reply|"
    r"currently unavailable|back on)\b",
    re.IGNORECASE,
)

# ── Casual chat ───────────────────────────────────────────────────────────────
_CASUAL_RE = re.compile(
    r"^(hi+|hey+|hello+|sup|what.?s up|howdy|"
    r"good (morning|afternoon|evening)|how are you|"
    r"hope you.?re (well|doing well|good))[.!?]?\s*$",
    re.IGNORECASE,
)

# ── Positive sentiment ────────────────────────────────────────────────────────
_POSITIVE_RE = re.compile(
    r"\b(great|excellent|amazing|love|perfect|fantastic|"
    r"wonderful|awesome|thank(s| you)|appreciate|impressed|"
    r"happy|pleased|satisfied|good job|well done)\b",
    re.IGNORECASE,
)

# ── Negative sentiment ────────────────────────────────────────────────────────
_NEGATIVE_RE = re.compile(
    r"\b(bad|poor|terrible|awful|horrible|disappointed|"
    r"frustrated|angry|upset|annoyed|useless|waste|"
    r"never again|worst|hate|dislike|not happy)\b",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Engine
# ═══════════════════════════════════════════════════════════════════════════════

class RuleEngine:
    """
    Stateless rule engine.
    Evaluates keyword/regex patterns and returns a RuleSignal.

    Key design decisions:
      - Spam requires 3+ spam words AND a CTA AND length > 300 chars.
        This prevents false positives on genuine messages containing "offer".
      - Mixed intent (unsubscribe + pricing) → intent_hint = INTEREST, not UNSUBSCRIBE.
      - Abuse → intent_hint = COMPLAINT (not ABUSE) — abuse is a risk flag, not a rejection.
    """

    def evaluate(self, text: str, subject: str = "") -> RuleSignal:
        """
        Evaluate all rules against the combined text.

        Args:
            text:    Cleaned incoming message content.
            subject: Email subject line (may be empty).

        Returns:
            RuleSignal with hints, risk flags, and a rule_score.
        """
        combined = f"{subject} {text}".strip()
        flags = RiskFlags()
        matched: List[str] = []

        # ── Risk flag detection (independent of intent) ───────────────────
        if _LINK_RE.search(combined):
            flags.contains_links = True
            matched.append("contains_links")

        if _PII_RE.search(combined):
            flags.contains_pii = True
            matched.append("pii_detected")

        if _THREAT_RE.search(combined):
            flags.contains_threat = True
            flags.contains_legal_language = True
            matched.append("legal_threat")

        unsub_match = bool(_UNSUB_RE.search(combined))
        if unsub_match:
            flags.contains_unsubscribe = True
            matched.append("unsubscribe_keyword")

        abuse_match = bool(_ABUSE_RE.search(combined))
        if abuse_match:
            flags.contains_abuse = True
            matched.append("abuse_keyword")

        # Spam: requires multiple signals, not a single keyword
        spam_word_count = len(_SPAM_WORDS_RE.findall(combined))
        has_cta         = bool(_CTA_RE.search(combined))
        is_long         = len(combined) > 300
        is_spam_pattern = spam_word_count >= 3 and has_cta and is_long
        if spam_word_count >= 2:
            flags.contains_spam_words = True
            matched.append(f"spam_words({spam_word_count})")

        # ── Intent hint detection ─────────────────────────────────────────
        intent_hint:     Optional[IntentType]    = None
        sub_intent_hint: Optional[SubIntent]     = None
        sentiment_hint:  Optional[SentimentType] = None
        rule_score:      float                   = 0.0

        # Out of office — high confidence, check first
        if _OOO_RE.search(combined):
            intent_hint = IntentType.OUT_OF_OFFICE
            rule_score  = 0.90
            matched.append("out_of_office")

        # Casual chat — very short, greeting-only messages
        elif _CASUAL_RE.match(text.strip()) and len(text.strip()) < 60:
            intent_hint     = IntentType.REPLY
            sub_intent_hint = SubIntent.CASUAL_CHAT
            rule_score      = 0.80
            matched.append("casual_chat")

        # Spam pattern — only when all three signals fire
        elif is_spam_pattern and not _PRICING_RE.search(combined) and not _INTEREST_RE.search(combined):
            intent_hint = IntentType.SPAM
            rule_score  = 0.75   # Still needs model confirmation to reach 0.9 threshold
            matched.append("spam_pattern")

        # Mixed intent: unsubscribe + pricing/interest → treat as INTEREST
        elif unsub_match and (_PRICING_RE.search(combined) or _INTEREST_RE.search(combined)):
            intent_hint     = IntentType.INTEREST
            sub_intent_hint = SubIntent.UNSUBSCRIBE  # Track the unsub signal as sub-intent
            rule_score      = 0.65
            matched.append("mixed_unsub_interest")

        # Pure unsubscribe (no interest signals)
        elif unsub_match and not _INTEREST_RE.search(combined) and not _PRICING_RE.search(combined):
            intent_hint = IntentType.UNSUBSCRIBE
            rule_score  = 0.80
            matched.append("pure_unsubscribe")

        # Abuse → complaint (abuse is a risk flag, not a rejection intent)
        elif abuse_match:
            intent_hint    = IntentType.COMPLAINT
            sentiment_hint = SentimentType.ABUSIVE
            rule_score     = 0.70
            matched.append("abuse_as_complaint")

        # Legal threat
        elif flags.contains_threat:
            intent_hint    = IntentType.COMPLAINT
            sub_intent_hint = SubIntent.LEGAL_THREAT
            sentiment_hint = SentimentType.ANGRY
            rule_score     = 0.75
            matched.append("legal_threat_complaint")

        # Not interested
        elif _NOT_INTERESTED_RE.search(combined):
            intent_hint = IntentType.NOT_INTERESTED
            rule_score  = 0.72
            matched.append("not_interested")

        # Objection
        elif _OBJECTION_RE.search(combined):
            intent_hint = IntentType.OBJECTION
            rule_score  = 0.60
            matched.append("objection")

        # Complaint
        elif _COMPLAINT_RE.search(combined):
            intent_hint = IntentType.COMPLAINT
            rule_score  = 0.68
            matched.append("complaint")

        # Support request
        elif _SUPPORT_RE.search(combined):
            intent_hint = IntentType.SUPPORT_REQUEST
            rule_score  = 0.65
            matched.append("support")

        # Pricing question
        elif _PRICING_RE.search(combined):
            intent_hint     = IntentType.QUESTION
            sub_intent_hint = SubIntent.PRICING
            rule_score      = 0.70
            matched.append("pricing_question")

        # Demo / meeting request
        elif _DEMO_RE.search(combined):
            intent_hint     = IntentType.INTEREST
            sub_intent_hint = SubIntent.DEMO_REQUEST
            rule_score      = 0.72
            matched.append("demo_request")

        elif _MEETING_RE.search(combined):
            intent_hint     = IntentType.INTEREST
            sub_intent_hint = SubIntent.MEETING
            rule_score      = 0.65
            matched.append("meeting_request")

        # General interest
        elif _INTEREST_RE.search(combined):
            intent_hint = IntentType.INTEREST
            rule_score  = 0.65
            matched.append("interest")

        # ── Sentiment hint ────────────────────────────────────────────────
        if sentiment_hint is None:
            pos = bool(_POSITIVE_RE.search(combined))
            neg = bool(_NEGATIVE_RE.search(combined))
            if pos and neg:
                sentiment_hint = SentimentType.MIXED
            elif pos:
                sentiment_hint = SentimentType.POSITIVE
            elif neg:
                sentiment_hint = SentimentType.NEGATIVE
            else:
                sentiment_hint = SentimentType.NEUTRAL

        # ── Language type ─────────────────────────────────────────────────
        language_type = detect_language_type(combined)

        return RuleSignal(
            intent_hint=intent_hint,
            sub_intent_hint=sub_intent_hint,
            sentiment_hint=sentiment_hint,
            language_type=language_type,
            risk_flags=flags,
            rule_score=rule_score,
            matched_patterns=matched,
        )
