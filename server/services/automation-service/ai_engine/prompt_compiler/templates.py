"""
Prompt Compiler — Templates
============================
Business-driven conversational AI prompt system.

CORE PRINCIPLE:
  Every message is a lead. Every reply must move toward a business goal.
  Casual messages get a brief acknowledgement + business redirect.
  No timepass. No friend-chat. No wasted lead attention.

PRIORITY ARCHITECTURE:
  1. CURRENT INCOMING MESSAGE — always answered first
  2. Conversation history — reference only
  3. Business context — supportive, introduced naturally

ANTI-HALLUCINATION:
  data_flags control what the LLM is allowed to mention.
"""
import json as _json

# Casual/greeting patterns — used to detect timepass messages
_CASUAL_PATTERNS = [
    "kaisa hai", "kaise ho", "kya chal raha", "kya kar rahe", "aur batao",
    "kya haal", "sab theek", "how are you", "what's up", "whats up",
    "how r u", "sup bro", "hey bhai", "hi bhai", "hello bhai",
    "kya haal chaal", "kya scene hai", "bhai kya kar raha",
]


def _is_casual_message(message: str) -> bool:
    """Detect if the message is casual/greeting with no business intent."""
    msg_lower = message.lower().strip()
    # Very short messages with no business keywords are likely casual
    if len(msg_lower) < 40:
        for pattern in _CASUAL_PATTERNS:
            if pattern in msg_lower:
                return True
    return False


def build_system_prompt(company_name: str, intent: str) -> str:
    """
    Business-driven system prompt.
    Casual messages get redirected. Every reply has a purpose.
    """
    system = {
        "identity": f"You are a business AI assistant for {company_name}. You are professional, helpful, and goal-driven.",
        "business_mode": [
            "Every conversation is a potential lead. Every reply must have a business purpose.",
            "If the message is casual or a greeting → acknowledge briefly (1 sentence) then redirect to business with a relevant question.",
            "Do NOT continue casual small talk. Do NOT act like a friend.",
            "Introduce business context naturally when the user shows any curiosity.",
            "Your goal: understand the user's need → qualify them → guide toward a solution."
        ],
        "priority_rules": [
            "PRIORITY 1: Understand what the CURRENT message is really asking.",
            "PRIORITY 2: If casual → redirect to business. If business → answer directly.",
            "PRIORITY 3: Use business context to support, not to force."
        ],
        "behavior_rules": [
            "Casual greeting (e.g. 'kaisa hai', 'what's up') → 1 sentence acknowledgement + 1 business question.",
            "Do NOT say 'Sab theek hai bhai' and ask back 'Tum kaise ho?' — that is timepass.",
            "Do NOT repeat the same sentence or structure from previous replies.",
            "If user asks 'what do you do' or 'tum kya karte ho' → give a brief business intro + ask their need.",
            "Match message length: short message → short reply (2-3 sentences max).",
            "Reply in the EXACT same language and script as the current message.",
            "Hinglish → Hinglish. Hindi → Hindi. English → English. Never translate.",
            "Sound natural. No corporate stiffness. No robotic phrases."
        ],
        "anti_hallucination_rules": [
            "Do NOT mention any product, service, feature, or pricing not explicitly in business context.",
            "If data_flags.has_products=false → do NOT mention product names.",
            "If data_flags.has_services=false → do NOT mention service names.",
            "If data_flags.has_pricing=false → do NOT mention prices or costs.",
            "If asked about something not in context → ask a clarifying question, never guess."
        ],
        "anti_repetition_rules": [
            "If last_ai_reply is provided → do NOT repeat the same phrasing or structure.",
            "Do NOT use: 'I'm here to help', 'feel free to ask', 'hope this helps', 'main check karke bataunga'."
        ],
        "output_rules": [
            "Return ONLY valid JSON. No markdown, no extra text."
        ],
        "output_schema": {
            "status": "success",
            "reply": "your reply text here",
            "confidence": "number between 0.5 and 1.0 — your honest confidence in this reply",
            "intent_handled": intent
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
    """
    Build the user prompt. Casual messages get business redirection.
    Business messages get direct, data-controlled answers.
    """
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
            "subject": subject,
            "message": incoming_message,
            "intent":  intent,
            "sentiment": sentiment,
            "is_casual": is_casual
        },
        "conversation_history": conversation_history,
        "data_flags": data_flags
    }

    has_biz = business_instruction and "(business context not available" not in business_instruction
    if has_biz:
        context["business_context"] = business_instruction

    if last_ai_reply and last_ai_reply.strip():
        context["last_ai_reply"] = last_ai_reply.strip()[:300]

    # ── Task instructions ─────────────────────────────────────────────────────

    if mode == "minimal":
        task = [
            f"Acknowledge the current message warmly (max {max_tokens} words).",
            "Say message received, team will follow up.",
            "Reply in same language/script as current message."
        ]

    elif mode == "abuse":
        task = [
            f"Respond calmly and briefly (max {max_tokens} words).",
            "Do NOT react emotionally. Do NOT push any business information.",
            "Acknowledge their feeling, offer to disengage or help if needed.",
            "Reply in same language/script as current message."
        ]

    elif mode == "no_context":
        if is_casual:
            task = [
                f"Reply briefly (max 2 sentences).",
                "Acknowledge the greeting in 1 sentence.",
                "Then ask one relevant business question to understand what they might need.",
                "Example: 'Sab badhiya 🙂 Waise aap kisi specific cheez ke bare me explore kar rahe ho?'",
                "Reply in same language/script as current message."
            ]
        else:
            task = [
                f"Reply to the current message (max {max_tokens} words).",
                "No business details available — ask a smart follow-up question to understand their need.",
                "Do NOT invent or assume any products, services, or pricing.",
                "Reply in same language/script as current message."
            ]

    elif mode == "safe":
        # Opt-out handling
        if intent == "unsubscribe" or (intent == "not_interested" and sentiment in ("negative", "neutral")):
            task = [
                "The user wants to stop receiving contact. Send ONE final polite acknowledgement.",
                "Confirm you will not contact them again. Keep it to 1-2 sentences.",
                "Do NOT push any business info. Do NOT ask follow-up questions.",
                "Example (Hinglish): 'Samajh gaya — aapko ab contact nahi kiya jayega. Dhanyavaad.'",
                "Example (English): 'Understood — we will not contact you again. Thank you.'",
                "Reply in same language/script as current message."
            ]
        elif is_casual:
            # Casual message in safe mode — redirect to business
            task = [
                f"Reply briefly (max 2 sentences).",
                "Acknowledge the greeting in 1 sentence.",
                "Then smoothly redirect: ask one relevant business question.",
                "Example: 'Sab badhiya 🙂 Waise aap wandercall ke baare mein kuch explore karna chahte ho?'",
                "Do NOT continue the casual chat. Do NOT ask 'tum kaise ho?'",
                "Reply in same language/script as current message."
            ]
        else:
            task = [
                f"Reply to the current message professionally (max {max_tokens} words).",
                "Use ONLY what is in business context. Do not add or assume anything.",
                "Do NOT push business info if the user is not asking for it.",
                "Reply in same language/script as current message."
            ]

    else:  # standard
        if is_casual:
            task = [
                f"Reply briefly (max 2 sentences).",
                "Acknowledge the greeting in 1 sentence.",
                "Then ask one relevant business question to understand their need.",
                "Example: 'Sab badhiya 🙂 Aap kisi specific experience ya solution ke baare mein soch rahe ho?'",
                "Do NOT continue casual chat. Do NOT ask personal questions back.",
                "Reply in same language/script as current message."
            ]
        else:
            intent_guidance = _get_intent_guidance(intent, sub_intent, sentiment, has_biz, data_flags)
            task = [
                f"Reply to the current message (max {max_tokens} words).",
                intent_guidance,
                "Use ONLY data present in business context. Check data_flags before mentioning products/services/pricing.",
                "Do NOT repeat phrasing from last_ai_reply if provided.",
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
) -> str:
    """
    Return a business-driven, sentiment-aware instruction.
    Every guidance ends with a forward-moving action.
    """
    has_pricing  = data_flags.get("has_pricing", False)
    has_services = data_flags.get("has_services", False)
    has_products = data_flags.get("has_products", False)

    # Negative/abusive sentiment — calm, no business push
    is_negative = sentiment in ("negative", "abusive", "angry")
    if is_negative:
        if intent == "not_interested":
            return "Respect their decision calmly. Say it's okay, no pressure. Leave the door open in one short sentence. Do NOT mention any services or products."
        return "Respond calmly and briefly. Acknowledge their feeling without reacting. Do NOT push any business information."

    if sub_intent == "pricing" or "pricing" in sub_intent.lower():
        if has_pricing:
            return "Share the pricing information from business context clearly and directly."
        return "Pricing details are not in context. Ask what type of experience/solution they're looking for so you can guide them."

    if intent == "question":
        if has_biz:
            return "Answer the specific question using only what is in business context. If the answer is not there, ask a clarifying question to understand their need better."
        return "Ask a specific follow-up question to understand what they're looking for."

    if intent == "interest":
        if has_services or has_products:
            return "Acknowledge their interest. Share relevant details from business context (only what is explicitly there). Ask what they'd like to know more about."
        return "Acknowledge their interest. Ask what specifically they're looking for — this helps you guide them to the right solution."

    if intent == "follow_up":
        return "Continue from where the conversation left off. Reference what was discussed. Provide the next logical step or ask what they need next."

    if intent == "objection":
        if has_biz:
            return "Address the specific concern using business context. Ask what would make them more comfortable moving forward."
        return "Acknowledge their concern. Ask what specific information would help address it."

    if intent == "complaint":
        return "Acknowledge the issue specifically. Apologize briefly. Offer a concrete next step to resolve it."

    if intent == "support_request":
        return "Address the specific support need directly. If answer not in context, ask for more details to help them."

    if intent == "not_interested":
        return "Respect their decision. Keep it brief. Do not push anything."

    if intent == "reply":
        # Generic reply — redirect to business
        return "Acknowledge briefly. Then ask one relevant business question to understand their need."

    if has_biz:
        return "Answer using only what is in business context. If data is missing, ask a clarifying question to understand their need."
    return "Ask a specific follow-up question to understand what they're looking for."


# ── Legacy constants — kept so stale imports don't crash ─────────────────────
SYSTEM_BASE = ""
USER_STANDARD = ""
USER_SAFE = ""
USER_MINIMAL = ""
USER_ABUSE = ""
USER_NO_CONTEXT = ""
MIXED_INTENT_NOTE = ""
