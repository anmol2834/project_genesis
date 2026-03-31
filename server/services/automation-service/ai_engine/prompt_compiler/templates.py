"""
Prompt Compiler — Templates
============================
Business-driven, human-level communication engine.

CORE PRINCIPLES:
  1. Business boundary: only speak about what exists in business_context
  2. Out-of-scope: acknowledge → deny clearly → redirect to what we DO offer
  3. Anti-repetition: never ask the same question twice
  4. Context priority: current message 70%, history 20%, older 10%
  5. Language mirror: exact same language and script as user
  6. Conversion: every reply moves toward a business outcome
"""
import json as _json

_CASUAL_PATTERNS = [
    "kaisa hai", "kaise ho", "kya chal raha", "kya kar rahe", "aur batao",
    "kya haal", "sab theek", "how are you", "what's up", "whats up",
    "how r u", "sup bro", "hey bhai", "hi bhai", "hello bhai",
    "kya haal chaal", "kya scene hai", "bhai kya kar raha",
]


def _is_casual_message(message: str) -> bool:
    msg_lower = message.lower().strip()
    if len(msg_lower) < 40:
        for pattern in _CASUAL_PATTERNS:
            if pattern in msg_lower:
                return True
    return False


def build_system_prompt(company_name: str, intent: str) -> str:
    system = {
        "identity": f"You are a smart business communication assistant for {company_name}. You behave like an experienced human sales and support agent.",

        "business_boundary_rules": [
            "You ONLY speak about what is explicitly present in business_context.",
            "If the user asks about something NOT in business_context → do NOT answer it, do NOT pretend you can help.",
            "Out-of-scope response strategy: (1) Acknowledge their query, (2) Clearly state this is not what we offer, (3) Redirect to what we DO offer.",
            "NEVER hallucinate services, products, or capabilities not in business_context.",
            "NEVER act as a different business or pretend to offer something you don't.",
            "Example of correct out-of-scope response: 'That's an interesting requirement! However, we currently focus on [business offering] — not AI calling systems. If you're interested in [what we do], I'd love to tell you more.'"
        ],

        "thinking_protocol": [
            "Step 1: What is the user ACTUALLY asking in the current message?",
            "Step 2: Is this inside our business scope (check business_context)?",
            "Step 3: If YES → answer directly and move toward conversion.",
            "Step 4: If NO → acknowledge, deny clearly, redirect to our actual offering.",
            "Step 5: Have I already asked this question in last_ai_reply? If YES → do NOT ask again."
        ],

        "anti_repetition_rules": [
            "If last_ai_reply asked a question → do NOT ask the same or similar question again.",
            "If the user has already answered a question → do NOT ask it again.",
            "Each reply MUST add new value — new information, new direction, or a clear next step.",
            "Do NOT reuse the same sentence structure as last_ai_reply.",
            "Do NOT use: 'I'm here to help', 'feel free to ask', 'hope this helps'."
        ],

        "language_rules": [
            "Detect the user's language AND script from the current message.",
            "Reply in the EXACT same language and script.",
            "Hinglish → Hinglish. Hindi (Devanagari) → Hindi. English → English.",
            "Do NOT translate or switch scripts.",
            "Match the user's tone and message length."
        ],

        "conversion_rules": [
            "Every reply should move the conversation toward a business outcome.",
            "If user shows interest → guide them toward what we offer.",
            "If user is out-of-scope → redirect to our actual offering with a question.",
            "If user is disengaged → close professionally, leave door open.",
            "Do NOT keep asking the same qualifying question in a loop."
        ],

        "output_rules": [
            "Return ONLY valid JSON. No markdown, no extra text."
        ],

        "output_schema": {
            "status": "success",
            "reply": "your reply text",
            "confidence": "number 0.5-1.0",
            "intent_handled": intent,
            "mode": "answer | redirect | refuse | convert"
        }
    }
    return _json.dumps(system, ensure_ascii=False)


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
            "has_products": False,
            "has_services": False,
            "has_pricing":  False,
            "has_use_cases": False,
        }

    is_casual = _is_casual_message(incoming_message)

    context = {
        "current_message": {
            "subject":   subject,
            "message":   incoming_message,
            "intent":    intent,
            "sentiment": sentiment,
            "is_casual": is_casual
        },
        "conversation_history": conversation_history,
        "data_flags": data_flags
    }

    has_biz = bool(business_instruction and "(business context not available" not in business_instruction)
    if has_biz:
        context["business_context"] = business_instruction

    if last_ai_reply and last_ai_reply.strip():
        context["last_ai_reply"] = last_ai_reply.strip()[:300]

    # ── Task instructions ─────────────────────────────────────────────────────

    if mode == "minimal":
        task = [
            f"Acknowledge warmly (max {max_tokens} words). Say message received, team will follow up.",
            "Reply in same language/script as current message."
        ]

    elif mode == "abuse":
        task = [
            f"Respond calmly and briefly (max {max_tokens} words). Do NOT push business info.",
            "Acknowledge their feeling. Offer to disengage or help if needed.",
            "Reply in same language/script as current message."
        ]

    elif mode == "no_context":
        if is_casual:
            task = [
                "Acknowledge the greeting in 1 sentence. Then ask one business question.",
                "Example: 'Sab badhiya 🙂 Waise aap kisi specific cheez ke bare me explore kar rahe ho?'",
                "Reply in same language/script as current message."
            ]
        else:
            task = [
                f"Reply (max {max_tokens} words).",
                "No business details available. Ask a smart follow-up to understand their need.",
                "Do NOT invent products, services, or pricing.",
                "Reply in same language/script as current message."
            ]

    elif mode == "safe":
        if intent == "unsubscribe" or (intent == "not_interested" and sentiment in ("negative", "neutral")):
            task = [
                "User wants to stop contact. Send ONE final polite acknowledgement (1-2 sentences).",
                "Confirm no further contact. Do NOT push business info or ask questions.",
                "Example (Hinglish): 'Samajh gaya — aapko ab contact nahi kiya jayega. Dhanyavaad.'",
                "Example (English): 'Understood — we will not contact you again. Thank you.'",
                "Reply in same language/script as current message."
            ]
        elif is_casual:
            task = [
                "Acknowledge greeting in 1 sentence. Then ask one business question.",
                "Do NOT continue casual chat.",
                "Reply in same language/script as current message."
            ]
        else:
            intent_guidance = _get_intent_guidance(intent, sub_intent, sentiment, has_biz, data_flags, last_ai_reply)
            task = [
                f"Reply (max {max_tokens} words).",
                intent_guidance,
                "Reply in same language/script as current message."
            ]

    else:  # standard
        if is_casual:
            task = [
                "Acknowledge greeting in 1 sentence. Then ask one business question.",
                "Do NOT continue casual chat.",
                "Reply in same language/script as current message."
            ]
        else:
            intent_guidance = _get_intent_guidance(intent, sub_intent, sentiment, has_biz, data_flags, last_ai_reply)
            task = [
                f"Reply (max {max_tokens} words).",
                intent_guidance,
                "Use ONLY data in business context. Check data_flags before mentioning products/services/pricing.",
                "Reply in same language/script as current message."
            ]

    payload = {
        "context": context,
        "task": task
    }

    return _json.dumps(payload, ensure_ascii=False)


def _get_intent_guidance(
    intent: str,
    sub_intent: str,
    sentiment: str,
    has_biz: bool,
    data_flags: dict,
    last_ai_reply: str = "",
) -> str:
    """
    Return a business-driven, non-repetitive instruction.
    Detects if a clarifying question was already asked and avoids repeating it.
    Handles out-of-scope queries with honest redirect.
    """
    has_pricing  = data_flags.get("has_pricing", False)
    has_services = data_flags.get("has_services", False)
    has_products = data_flags.get("has_products", False)

    # Detect if we already asked a clarifying question in the last reply
    already_asked = bool(last_ai_reply and "?" in last_ai_reply)

    # Negative/abusive sentiment — calm, no business push
    if sentiment in ("negative", "abusive", "angry"):
        if intent == "not_interested":
            return "Respect their decision calmly. 1 sentence. Do NOT mention services or products."
        return "Respond calmly and briefly. Acknowledge their feeling. Do NOT push business info."

    if sub_intent == "pricing" or "pricing" in sub_intent.lower():
        if has_pricing:
            return "Share pricing from business context clearly."
        if already_asked:
            return "Pricing is not in our current context. Acknowledge this honestly and offer to connect them with the right person."
        return "Pricing not in context. Ask what type of experience/solution they need so you can guide them."

    if intent in ("question", "interest"):
        # Check if the query is likely out-of-scope
        # If business context exists but user is asking about something very specific
        # that isn't in it, we should redirect honestly
        if has_biz:
            if already_asked:
                # We already asked a clarifying question — now we must give a real answer or honest redirect
                return (
                    "You already asked a clarifying question in last_ai_reply. "
                    "Now you MUST do one of: "
                    "(A) If their need matches business_context → answer directly with what we offer. "
                    "(B) If their need does NOT match business_context → say clearly: "
                    "'What you're describing (e.g. AI calling system) is not something we currently offer. "
                    "We focus on [business offering]. Would you be interested in exploring that instead?' "
                    "Do NOT ask another clarifying question."
                )
            return (
                "Answer using only what is in business_context. "
                "If their query is outside business scope → acknowledge it, clearly state we don't offer that, "
                "then redirect: 'We focus on [business offering] — would you like to know more about that?'"
            )
        if already_asked:
            return "You already asked a question. Now provide a direct answer or honest redirect. Do NOT ask again."
        return "Ask one specific follow-up question to understand their need."

    if intent == "follow_up":
        if already_asked:
            return "Continue the conversation. Provide the next logical step or a concrete answer. Do NOT ask the same question again."
        return "Continue from where the conversation left off. Provide the next logical step."

    if intent == "objection":
        if has_biz:
            return "Address the specific concern using business context. Ask what would help them feel comfortable."
        return "Acknowledge their concern. Ask what specific information would help."

    if intent == "complaint":
        return "Acknowledge the issue. Apologize briefly. Offer a concrete next step."

    if intent == "support_request":
        return "Address the support need directly. If not in context, ask for more details."

    if intent == "not_interested":
        return "Respect their decision. Keep it brief. Do not push anything."

    if intent == "reply":
        return "Acknowledge briefly. Ask one relevant business question."

    if has_biz:
        if already_asked:
            return "Provide a direct answer or honest redirect. Do NOT ask another question."
        return "Answer using only business context. If data missing, ask one clarifying question."
    return "Ask one specific follow-up question to understand their need."


# ── Legacy constants ──────────────────────────────────────────────────────────
SYSTEM_BASE = ""
USER_STANDARD = ""
USER_SAFE = ""
USER_MINIMAL = ""
USER_ABUSE = ""
USER_NO_CONTEXT = ""
MIXED_INTENT_NOTE = ""
