"""
Prompt Compiler — Templates
============================
Enterprise-grade, zero-hallucination, human-like communication engine.

CORE PRINCIPLES:
  1. Response mode selection BEFORE task assignment — greet/answer/clarify/redirect
  2. Language mirror — detect script + language, reply in exact same form
  3. Data-driven flags — has_products/has_pricing only True when data is injected
  4. No contradiction — LLM picks ONE path and stays on it
  5. Anti-repetition — never ask the same question twice
  6. Human-like — no robotic tone, no forced business push
"""
import json as _json
import re as _re

# ── Language / script detection ───────────────────────────────────────────────

_DEVANAGARI_RE = _re.compile(r"[\u0900-\u097F]")

_HINGLISH_WORDS = {
    "kya", "hai", "nahi", "haan", "theek", "acha", "batao", "chahiye",
    "kitna", "kab", "kaise", "kyun", "mujhe", "humko", "aap", "tum",
    "yeh", "woh", "iska", "uska", "price", "bhai", "yaar", "ek",
    "do", "teen", "mil", "milega", "dena", "lena", "karo", "karna",
    "ho", "hoga", "tha", "thi", "the", "raha", "rahi", "rahe",
    "sab", "kuch", "thoda", "bahut", "bilkul", "zaroor", "please",
    "ok", "okay", "haan", "nahin", "nahi", "accha", "acha",
}


def detect_language_mode(message: str) -> str:
    """
    Detect the language/script of the incoming message.

    Priority order (CRITICAL — must check Devanagari FIRST):
      1. Devanagari script → "hindi"
      2. Latin script with Hindi words (≥15%) → "hinglish"
      3. Pure English → "english"

    NEVER overrides user's language — if user writes English, reply in English.
    """
    if not message:
        return "english"

    # Step 1: Devanagari script check FIRST (before Hinglish word check)
    # A message like "नमस्ते price" has Devanagari → must be "hindi", not "hinglish"
    if _DEVANAGARI_RE.search(message):
        return "hindi"

    # Step 2: Check for Hinglish words in Latin script
    words = set(_re.findall(r"\b\w+\b", message.lower()))
    total_words = max(len(words), 1)
    hinglish_count = len(words & _HINGLISH_WORDS)

    # Require ≥15% Hinglish words AND at least 1 clear Hindi word
    # This prevents English words like "the", "ok" from triggering Hinglish
    if hinglish_count >= 1 and hinglish_count / total_words >= 0.15:
        return "hinglish"

    return "english"


# ── Response mode detection ───────────────────────────────────────────────────

_GREETING_RE = _re.compile(
    r"^(hi+|hey+|hello+|helo|hii+|hiii+|sup|what'?s up|howdy|"
    r"good\s+(morning|afternoon|evening|day|night)|"
    r"namaste|namaskar|salam|assalam|"
    r"greetings?|"
    r"thanks?|thank you|thx|ty|"
    r"ok|okay|k|got it|noted|sure|alright|fine|"
    r"bye|goodbye|see you|take care|"
    r"yes|no|yeah|nope|yep|nah)[.!?🙏👋😊\s]*$",
    _re.IGNORECASE,
)

_INFORMATIONAL_RE = _re.compile(
    r"\b(price|prise|cost|rate|fee|amount|kitna|daam|"
    r"product|item|goods|prodict|prodcut|"
    r"offer|discount|deal|promo|chhoot|sale|coupon|"
    r"stock|available|availability|milega|"
    r"contact|phone|number|email|support|helpline|"
    r"delivery|shipping|dispatch|courier|"
    r"refund|return|policy|warranty|"
    r"service|plan|package|subscription|"
    r"about|company|who are you|"
    r"how much|what is|tell me|batao|dikhao|chahiye|"
    r"buy|purchase|order|book|details|info|jankari)\b",
    _re.IGNORECASE,
)


def detect_response_mode(
    message: str,
    intent: str,
    has_data: bool,
    data_flags: dict,
) -> str:
    """
    Determine the response mode BEFORE building the task.

    Returns one of: "greet" | "answer" | "clarify" | "redirect"

    Rules:
      greet    — pure greeting/casual, no business query
      answer   — informational query + data available
      clarify  — informational query + no data, or vague query
      redirect — out-of-scope query
    """
    msg = message.strip()

    # Pure greeting / casual acknowledgement
    if len(msg) <= 80 and _GREETING_RE.match(msg):
        return "greet"

    # Noise intents never need data
    if intent in ("spam", "promo", "unsubscribe", "out_of_office"):
        return "greet"

    # Informational query
    has_info_keywords = bool(_INFORMATIONAL_RE.search(msg))
    has_any_data = (
        data_flags.get("has_products", False) or
        data_flags.get("has_pricing", False) or
        data_flags.get("has_services", False) or
        data_flags.get("has_use_cases", False)
    )

    if has_info_keywords or intent in ("question", "interest", "negotiation", "support_request"):
        if has_any_data:
            return "answer"
        else:
            return "clarify"

    if intent in ("follow_up", "objection", "complaint"):
        return "answer" if has_any_data else "clarify"

    if intent == "not_interested":
        return "redirect"

    # Default: clarify for vague messages
    return "clarify" if not has_any_data else "answer"


# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(company_name: str, intent: str) -> str:
    system = {
        "identity": (
            f"You are a smart business communication assistant for {company_name}. "
            "You behave like an experienced human sales and support agent."
        ),

        "core_rules": [
            "You have ONE job: reply to the current message naturally and helpfully.",
            "NEVER contradict yourself. Pick ONE response path and stay on it.",
            "If data is in business_context → use it directly. Do NOT say 'I cannot provide' then provide it.",
            "If data is NOT in business_context → say so honestly in 1 sentence, then offer to help differently.",
            "NEVER hallucinate products, prices, or services not in business_context.",
            "NEVER say 'I cannot provide details' and then provide details in the same reply.",
        ],

        "response_path_rules": {
            "greet":    "Respond warmly in 1-2 sentences. Ask ONE relevant business question. No product listing.",
            "answer":   "Answer directly using ONLY data from business_context. Be specific. No vague promises.",
            "clarify":  "Ask ONE specific question to understand their need. Do NOT invent data.",
            "redirect": "Acknowledge their message. Explain what we DO offer. Ask if that helps.",
        },

        "language_rules": [
            "Detect the user's language and script from current_message.",
            "language_mode=hinglish → reply in Hinglish (Latin script, Hindi words mixed with English).",
            "language_mode=hindi → reply in Hindi (Devanagari script).",
            "language_mode=english → reply in English only.",
            "NEVER switch scripts. NEVER translate.",
            "Match the user's tone and energy level.",
        ],

        "anti_repetition_rules": [
            "If last_ai_reply asked a question → do NOT ask the same question again.",
            "Each reply MUST add new value — new info, new direction, or a clear next step.",
            "Do NOT use: 'I'm here to help', 'feel free to ask', 'hope this helps', 'let me know'.",
            "Do NOT start with 'Great!', 'Sure!', 'Absolutely!' — these are robotic.",
        ],

        "output_format": {
            "instruction": "Return ONLY valid JSON. No markdown. No extra text before or after.",
            "schema": {
                "status": "success",
                "reply": "<your reply text here>",
                "confidence": 0.85,
                "intent_handled": intent,
                "mode": "<greet|answer|clarify|redirect>",
            },
        },
    }
    return _json.dumps(system, ensure_ascii=False)


# ── User prompt ───────────────────────────────────────────────────────────────

def build_user_prompt(
    mode: str,
    business_instruction: str,
    conversation_history: str,
    subject: str,
    incoming_message: str,
    intent: str,
    sub_intent: str,
    sentiment: str,
    tone: str,
    max_tokens: str,
    data_flags: dict = None,
    last_ai_reply: str = "",
) -> str:
    if data_flags is None:
        data_flags = {
            "has_products":  False,
            "has_services":  False,
            "has_pricing":   False,
            "has_use_cases": False,
        }

    # ── Language detection ────────────────────────────────────────────────
    language_mode = detect_language_mode(incoming_message)

    # ── Response mode detection ───────────────────────────────────────────
    has_data = any(data_flags.values())
    response_mode = detect_response_mode(incoming_message, intent, has_data, data_flags)

    # Override mode for special pipeline modes
    if mode == "minimal":
        response_mode = "greet"
    elif mode == "abuse":
        response_mode = "greet"
    elif mode == "no_context":
        response_mode = "clarify" if not _GREETING_RE.match(incoming_message.strip()) else "greet"

    # ── Build context block ───────────────────────────────────────────────
    context = {
        "current_message": {
            "subject":       subject,
            "message":       incoming_message,
            "intent":        intent,
            "sentiment":     sentiment,
            "language_mode": language_mode,
        },
        "conversation_history": conversation_history,
        "data_flags": data_flags,
        "response_mode": response_mode,
    }

    # Only inject business context when it exists and is needed
    has_biz = bool(
        business_instruction
        and "(business context not available" not in business_instruction
    )
    if has_biz:
        context["business_context"] = business_instruction

    # Only inject last_ai_reply when it exists (anti-repetition)
    if last_ai_reply and last_ai_reply.strip():
        context["last_ai_reply"] = last_ai_reply.strip()[:300]

    # ── Build task based on response_mode ─────────────────────────────────
    task = _build_task(
        response_mode=response_mode,
        mode=mode,
        intent=intent,
        sub_intent=sub_intent,
        sentiment=sentiment,
        language_mode=language_mode,
        max_tokens=max_tokens,
        has_biz=has_biz,
        data_flags=data_flags,
        last_ai_reply=last_ai_reply,
        incoming_message=incoming_message,
    )

    payload = {
        "context": context,
        "task":    task,
    }

    return _json.dumps(payload, ensure_ascii=False)


def _build_task(
    response_mode: str,
    mode: str,
    intent: str,
    sub_intent: str,
    sentiment: str,
    language_mode: str,
    max_tokens: str,
    has_biz: bool,
    data_flags: dict,
    last_ai_reply: str,
    incoming_message: str,
) -> list:
    """
    Build the task instruction list based on the detected response_mode.
    Each mode has ONE clear path — no contradictions possible.
    """
    already_asked = bool(last_ai_reply and "?" in last_ai_reply)
    lang_rule = _get_language_rule(language_mode)

    # ── GREET mode ────────────────────────────────────────────────────────
    if response_mode == "greet":
        if mode == "abuse":
            return [
                f"Respond calmly in 1-2 sentences (max {max_tokens} words).",
                "Acknowledge their feeling. Do NOT push any business info.",
                lang_rule,
            ]
        if mode == "minimal":
            return [
                f"Acknowledge warmly in 1 sentence (max {max_tokens} words).",
                "Say the team will follow up. Do NOT list products or services.",
                lang_rule,
            ]
        if intent in ("unsubscribe", "not_interested"):
            return [
                "Send ONE final polite acknowledgement (1-2 sentences).",
                "Confirm no further contact. Do NOT push business info or ask questions.",
                lang_rule,
            ]
        # Pure greeting
        return [
            "Respond to the greeting warmly in 1 sentence.",
            "Then ask ONE relevant business question to understand their need.",
            "Do NOT list products, prices, or services in a greeting reply.",
            lang_rule,
        ]

    # ── ANSWER mode ───────────────────────────────────────────────────────
    if response_mode == "answer":
        has_pricing  = data_flags.get("has_pricing", False)
        has_products = data_flags.get("has_products", False)

        # Pricing query with data — answer directly, NO questions
        if sub_intent in ("pricing", "price") or "pricing" in sub_intent.lower():
            if has_pricing:
                return [
                    f"Answer the pricing question directly (max {max_tokens} words).",
                    "Use ONLY the price data from business_context. Give the actual number(s).",
                    "Do NOT ask any questions. Do NOT say 'I cannot provide pricing'.",
                    "End with a clear CTA: invite them to proceed or ask for more details.",
                    lang_rule,
                ]
            else:
                return [
                    f"Pricing details are not in our current data (max {max_tokens} words).",
                    "Say honestly: exact pricing is not available right now.",
                    "Ask ONE question: what type of plan/product are they looking for?",
                    lang_rule,
                ]

        # Interest intent — push toward conversion, no unnecessary questions
        if intent == "interest":
            return [
                f"The user is interested. Answer directly (max {max_tokens} words).",
                "Share the most relevant product/service details from business_context.",
                "Be specific — names, prices, key benefits.",
                "End with ONE clear CTA (e.g., 'Would you like to proceed?' or 'Shall I share more details?').",
                "Do NOT ask clarifying questions — they are already interested.",
                lang_rule,
            ]

        # General answer with data
        if has_products or has_pricing:
            return [
                f"Answer directly using the data in business_context (max {max_tokens} words).",
                "Be specific — use the actual names, prices, and details from the data.",
                "Do NOT say 'I cannot provide' — the data is present, use it.",
                "If they asked about a specific item, answer ONLY about that item.",
                lang_rule,
            ]

        return [
            f"Answer using business_context (max {max_tokens} words).",
            "Be direct and specific. Use only what is in the context.",
            lang_rule,
        ]

    # ── CLARIFY mode ──────────────────────────────────────────────────────
    if response_mode == "clarify":
        if already_asked:
            return [
                f"You already asked a question in last_ai_reply (max {max_tokens} words).",
                "Do NOT ask the same question again.",
                "Either: (A) provide a helpful answer based on what you know, OR (B) offer a specific next step.",
                lang_rule,
            ]
        if intent in ("follow_up",):
            return [
                f"Continue the conversation naturally (max {max_tokens} words).",
                "Provide the next logical step or ask ONE specific question to move forward.",
                lang_rule,
            ]
        return [
            f"Ask ONE specific question to understand their need (max {max_tokens} words).",
            "Do NOT invent products, prices, or services.",
            "Do NOT list everything we offer — just ask what they need.",
            lang_rule,
        ]

    # ── REDIRECT mode ─────────────────────────────────────────────────────
    if response_mode == "redirect":
        if intent == "not_interested":
            return [
                f"Respect their decision (max {max_tokens} words).",
                "1-2 sentences only. Do NOT push anything. Leave the door open politely.",
                lang_rule,
            ]
        if intent == "objection":
            return [
                f"Address their specific concern (max {max_tokens} words).",
                "Use business_context if relevant. Ask what would help them feel comfortable.",
                lang_rule,
            ]
        if intent == "complaint":
            return [
                f"Acknowledge the issue and apologize briefly (max {max_tokens} words).",
                "Offer ONE concrete next step. Do NOT make promises not in business_context.",
                lang_rule,
            ]
        return [
            f"Acknowledge their message (max {max_tokens} words).",
            "Explain what we DO offer based on business_context.",
            "Ask if that is relevant to their need.",
            lang_rule,
        ]

    # ── Fallback ──────────────────────────────────────────────────────────
    return [
        f"Reply naturally (max {max_tokens} words).",
        "Be helpful and human. Use business_context if relevant.",
        lang_rule,
    ]


def _get_language_rule(language_mode: str) -> str:
    """
    Return the language instruction for the given mode.
    STRICT: never force a language the user didn't use.
    """
    if language_mode == "hinglish":
        return (
            "LANGUAGE: Reply in Hinglish — Latin script, natural mix of Hindi and English. "
            "Match the user's exact style. Do NOT translate to pure Hindi or pure English."
        )
    if language_mode == "hindi":
        return (
            "LANGUAGE: Reply in Hindi using Devanagari script only. "
            "Do NOT use Latin script or English words unless they are proper nouns."
        )
    # Default: English only — never force Hinglish on English users
    return "LANGUAGE: Reply in English only. Do NOT use Hindi or Hinglish words."


# ── Legacy constants (kept for backward compat) ───────────────────────────────
SYSTEM_BASE       = ""
USER_STANDARD     = ""
USER_SAFE         = ""
USER_MINIMAL      = ""
USER_ABUSE        = ""
USER_NO_CONTEXT   = ""
MIXED_INTENT_NOTE = ""
