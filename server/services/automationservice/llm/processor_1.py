"""
automationservice — LLM Processor #1: Analysis & Retrieval Planning

Fixes applied:
  1. Action-first intent: ESCALATION_TRIGGER_WORDS override sentiment-based classification
  2. Query specificity: minimum 2 queries per category enforced in validator
  3. Entity expansion: specifications[] field added alongside products/technologies/industries
  4. Confidence calibration: short/greeting messages capped at 0.45 before validation
  5. Conversation topic specificity: validated in prompt (no code-level fix needed)
  6. Current focus enforcement: handled in prompt (latest message priority)
  7. Context-aware query rewriting: handled in prompt + user template
  8. Escalation detection: routing_decision{} block validated and repaired
  9. Enterprise keyword sets: _infer_category uses real customer language across 8 categories
 10. Analytics-Aware Retrieval Planning:
     - _detect_analytics_intent(): pre-flight analytics confidence scorer using
       ANALYTICS_INTENT_KEYWORDS — determines requires_analytics + analytics_confidence
       before the LLM call so the LLM output can be validated/corrected.
     - analytics_decision validator: extended to handle analytics_confidence field,
       validate per-category analytics list, and map categories correctly.
     - "data_analytics" removed from ALLOWED_CATEGORIES — it is a SUBTYPE not a category.
     - _infer_retrieval_intent_type: removed "data_analytics" mapping.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import sys
import time
from typing import Any

_LLM_DIR      = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR      = os.path.dirname(_LLM_DIR)
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError, APIStatusError

from shared.config import get_config
from llm.prompts import (
    PROCESSOR_1_SYSTEM_PROMPT,
    PROCESSOR_1_USER_TEMPLATE,
    ALLOWED_CATEGORIES,
    ANALYTICS_KEYWORDS,
    ANALYTICS_INTENT_KEYWORDS,
    VALID_RETRIEVAL_INTENT_TYPES,
    ESCALATION_TRIGGER_WORDS,
    SPEC_IMPOSSIBILITY_RULES,
    # Enterprise keyword sets for _infer_category fallback
    ISSUE_RESOLUTION_KEYWORDS,
    CONTACT_SUPPORT_KEYWORDS,
    DELIVERY_SHIPPING_KEYWORDS,
    OFFERS_PROMOTIONS_KEYWORDS,
    POLICIES_LEGAL_KEYWORDS,
    PRODUCT_SERVICE_KEYWORDS,
    COMPANY_INFO_KEYWORDS,
    EDUCATIONAL_CONTENT_KEYWORDS,
    DATA_ANALYTICS_KEYWORDS,
)

logger = logging.getLogger("automationservice.processor_1")

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        cfg = get_config()
        _client = AsyncOpenAI(
            api_key=cfg.OPENAI_API_KEY,
            timeout=cfg.OPENAI_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client


# ── Schema constants ───────────────────────────────────────────────────────────

VALID_STAGES     = {"awareness", "discovery", "evaluation", "comparison", "purchase",
                    "post_purchase", "support", "escalation", "renewal", "retention", "unknown"}
VALID_SENTIMENTS = {"positive", "neutral", "negative", "frustrated", "urgent", "unknown"}
VALID_URGENCY    = {"low", "normal", "high", "critical"}
VALID_PRIORITY   = {"critical", "high", "normal", "low"}
ALLOWED_CAT_SET  = set(ALLOWED_CATEGORIES)

# ESCALATION_TRIGGER_WORDS imported from prompts.py — single source of truth


# ── Public entry point ─────────────────────────────────────────────────────────

async def run_processor_1(
    messages: list[dict],
    latest_message: dict,
    conversation_meta: dict,
    business_context: dict | None = None,
) -> dict:
    """
    Execute LLM Call #1: Analysis & Retrieval Planning.
    Never raises. Returns a guaranteed-valid dict.

    Args:
        messages:          Full thread history (oldest → newest, latest excluded).
        latest_message:    The triggering message dict from es_messages.
        conversation_meta: The es_conversations row dict.
        business_context:  Normalized business profile from services/business_context.py.
                           When provided, injected BEFORE conversation history in the
                           user prompt so the LLM understands the business domain first.
                           When None, Processor #1 falls back to generic reasoning.
    """
    t0  = time.monotonic()
    cfg = get_config()

    conversation_str = _build_conversation_string(messages, latest_message)
    latest_body      = (latest_message.get("content") or "").strip()
    subject          = conversation_meta.get("subject") or ""
    provider         = conversation_meta.get("provider") or ""
    message_count    = conversation_meta.get("message_count") or len(messages)
    participants     = conversation_meta.get("participants") or []

    # ── Build business context block (injected before conversation) ────────────
    # Import here to avoid circular imports; business_context module is services/
    from services.business_context import build_business_context_block
    business_block = build_business_context_block(business_context or {})

    user_prompt = PROCESSOR_1_USER_TEMPLATE.format(
        business_context_block = business_block,
        conversation_history   = conversation_str,
        latest_message         = latest_body or "(empty message)",
        subject                = subject or "(no subject)",
        provider               = provider or "unknown",
        message_count          = message_count,
        participants           = ", ".join(participants) if participants else "unknown",
    )

    # ── Pre-flight checks ──────────────────────────────────────────────────────
    all_text_lower      = " ".join((m.get("content") or "") for m in messages).lower()
    # Include latest message body in the analytics detection text
    all_text_for_analytics = (all_text_lower + " " + latest_body.lower()).strip()

    # Pre-flight analytics intent detection using ANALYTICS_INTENT_KEYWORDS.
    # Returns (requires_analytics, analytics_confidence, matched_phrases).
    # Used to validate/correct the LLM's analytics_decision output.
    preflight_analytics_flag, preflight_analytics_confidence, preflight_analytics_phrases = \
        _detect_analytics_intent(all_text_for_analytics)

    # Soft pre-flight: also check the broader ANALYTICS_KEYWORDS set for
    # the existing single-word pre-flight check (backward compat).
    preflight_analytics = preflight_analytics_flag or bool(
        ANALYTICS_KEYWORDS & set(re.findall(r'\b\w+\b', all_text_for_analytics))
    )

    # Detect escalation triggers in latest message for post-validation override.
    latest_lower      = latest_body.lower()
    preflight_escalation = _check_escalation_triggers(latest_lower)

    # Calibrate max conversation_confidence for very short messages before sending to LLM.
    # conversation_confidence measures message CLARITY — not category match strength.
    # The LLM has a tendency to return 0.95 for everything including "hello".
    body_word_count = len(latest_body.split()) if latest_body else 0
    if body_word_count <= 2:
        max_conv_confidence = 0.45   # "hi", "ok", "yes" — genuinely ambiguous
    elif body_word_count <= 5:
        max_conv_confidence = 0.80   # "any offers?" — short but possibly clear
    else:
        max_conv_confidence = 1.0    # full sentence — no cap

    # ── OpenAI call with retry ─────────────────────────────────────────────────
    raw_output  = None
    last_error  = None
    max_retries = max(1, cfg.OPENAI_MAX_RETRIES)

    for attempt in range(1, max_retries + 1):
        try:
            response = await _get_client().chat.completions.create(
                model           = cfg.OPENAI_MODEL,
                temperature     = 0.0,
                top_p           = 1.0,
                seed            = 42,
                response_format = {"type": "json_object"},
                messages = [
                    {"role": "system", "content": PROCESSOR_1_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            raw_output = response.choices[0].message.content
            break

        except RateLimitError as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning("[P1] rate limit attempt %d/%d — wait %ds", attempt, max_retries, wait)
            if attempt < max_retries:
                await asyncio.sleep(wait)

        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            wait = attempt
            logger.warning("[P1] transient error attempt %d/%d — wait %ds: %s", attempt, max_retries, wait, e)
            if attempt < max_retries:
                await asyncio.sleep(wait)

        except APIStatusError as e:
            last_error = e
            if e.status_code >= 500 and attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("[P1] API %d attempt %d/%d — wait %ds", e.status_code, attempt, max_retries, wait)
                await asyncio.sleep(wait)
            else:
                logger.error("[P1] non-retryable API error %d: %s", e.status_code, e)
                break

        except Exception as e:
            last_error = e
            logger.error("[P1] unexpected error attempt %d/%d: %s", attempt, max_retries, e)
            break

    elapsed_ms = (time.monotonic() - t0) * 1000

    if raw_output is None:
        logger.error("[P1] all attempts failed | %s | elapsed=%.0fms", last_error, elapsed_ms)
        fb = _build_fallback(latest_body, subject, str(last_error))
        fb["business_understanding"] = {
            "business_name": (business_context or {}).get("business_name", ""),
            "business_type": (business_context or {}).get("business_type", ""),
            "industry":      (business_context or {}).get("industry", []),
            "source":        "unavailable",
        }
        return fb

    parsed = _parse_json(raw_output)
    if parsed is None:
        logger.error("[P1] JSON parse failure | raw=%s...", raw_output[:200])
        fb = _build_fallback(latest_body, subject, "json_parse_failure")
        fb["business_understanding"] = {
            "business_name": (business_context or {}).get("business_name", ""),
            "business_type": (business_context or {}).get("business_type", ""),
            "industry":      (business_context or {}).get("industry", []),
            "source":        "unavailable",
        }
        return fb

    validated = _validate_and_repair(
        parsed,
        latest_body,
        preflight_analytics,
        preflight_analytics_confidence,
        preflight_analytics_phrases,
        preflight_escalation,
        max_conv_confidence,
        business_context,
    )
    validated["_meta"] = {
        "elapsed_ms": round(elapsed_ms, 1),
        "model":      cfg.OPENAI_MODEL,
        "attempts":   attempt,
        "status":     "ok",
    }

    # ── Attach business understanding for downstream observability ─────────────
    # Future Processor #2 and reranker can read this to confirm which business
    # profile was active during this pipeline run — without re-fetching.
    if business_context and business_context.get("_loaded"):
        validated["business_understanding"] = {
            "business_name": business_context.get("business_name", ""),
            "business_type": business_context.get("business_type", ""),
            "industry":      business_context.get("industry", []),
            "source":        business_context.get("_source", "postgresql"),
        }
    else:
        validated["business_understanding"] = {
            "business_name": "",
            "business_type": "",
            "industry":      [],
            "source":        "unavailable",
        }

    total_queries = sum(
        len(c.get("search_queries", []))
        for c in validated.get("retrieval_strategy", {}).get("categories", [])
    )
    logger.info(
        "[P1] complete | intent=%s conv_conf=%.2f intent_conf=%.2f queries=%d analytics=%s escalation=%s elapsed=%.0fms",
        validated.get("intent_analysis", {}).get("primary_intent", {}).get("category", "?"),
        validated.get("conversation_analysis", {}).get("conversation_confidence", 0.0),
        validated.get("intent_analysis", {}).get("primary_intent", {}).get("confidence", 0.0),
        total_queries,
        validated.get("analytics_decision", {}).get("requires_analytics", False),
        validated.get("routing_decision", {}).get("escalation_requested", False),
        elapsed_ms,
    )
    return validated


# ── Conversation string builder ────────────────────────────────────────────────

def _build_conversation_string(messages: list[dict], latest_message: dict) -> str:
    lines     = []
    latest_id = latest_message.get("message_id", "")
    for msg in messages:
        if msg.get("message_id") == latest_id:
            continue
        direction = (msg.get("direction") or "").upper()
        role      = "CUSTOMER" if direction == "INCOMING" else "AGENT"
        content   = (msg.get("content") or "").strip()
        ts        = (msg.get("timestamp") or "")[:16]
        if content:
            lines.append(f"[{ts}] {role}: {content}")
    return "\n".join(lines) if lines else "(no prior conversation history)"


# ── JSON parsing ───────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(raw[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


# ── Schema validation & repair ─────────────────────────────────────────────────

def _validate_and_repair(
    data: dict,
    latest_body: str,
    preflight_analytics: bool,
    preflight_analytics_confidence: float,
    preflight_analytics_phrases: list[str],
    preflight_escalation: bool,
    max_conv_confidence: float,
    business_context: dict | None = None,
) -> dict:

    data["pipeline_version"] = "1.0"

    # ── conversation_analysis ─────────────────────────────────────────────────
    ca = data.get("conversation_analysis") if isinstance(data.get("conversation_analysis"), dict) else {}

    ca["conversation_topic"] = _str(ca.get("conversation_topic"), "unknown")
    ca["current_focus"]      = _str(ca.get("current_focus"),      "unknown")
    ca["customer_goal"]      = _str(ca.get("customer_goal"),       "unknown")
    ca["latest_message"]     = _str(ca.get("latest_message"),      latest_body or "unknown")
    ca["resolved_reference"] = _str(ca.get("resolved_reference"),  ca["latest_message"])
    ca["standalone_query"]   = _str(ca.get("standalone_query"),    ca["current_focus"])
    ca["conversation_stage"] = ca.get("conversation_stage") if ca.get("conversation_stage") in VALID_STAGES else "unknown"
    ca["customer_sentiment"] = ca.get("customer_sentiment") if ca.get("customer_sentiment") in VALID_SENTIMENTS else "unknown"
    ca["urgency"]            = ca.get("urgency") if ca.get("urgency") in VALID_URGENCY else "normal"
    # Apply max_conv_confidence cap — prevents LLM returning 0.95 for "hello"
    # conversation_confidence: how clearly was the message understood (message clarity)
    # Support legacy field name "confidence" in addition to new "conversation_confidence"
    raw_conv_conf                  = _clamp(
        ca.get("conversation_confidence") if ca.get("conversation_confidence") is not None
        else ca.get("confidence"),
        0.0, 1.0, 0.5
    )
    ca["conversation_confidence"]  = min(raw_conv_conf, max_conv_confidence)
    # Remove legacy field to keep schema clean
    ca.pop("confidence", None)
    data["conversation_analysis"] = ca

    # ── intent_analysis ───────────────────────────────────────────────────────
    ia = data.get("intent_analysis") if isinstance(data.get("intent_analysis"), dict) else {}

    pi     = ia.get("primary_intent") if isinstance(ia.get("primary_intent"), dict) else {}
    pi_cat = pi.get("category", "")
    if pi_cat not in ALLOWED_CAT_SET:
        pi_cat = _infer_category(ca.get("standalone_query", ""), business_context)
    pi["category"]   = pi_cat
    pi["confidence"] = _clamp(pi.get("confidence"), 0.0, 1.0, 0.5)
    pi["reason"]     = _str(pi.get("reason"), "inferred from conversation")

    # ESCALATION OVERRIDE (Problem 1 fix):
    # If pre-flight detected escalation triggers AND primary is not contact_support,
    # demote current primary to secondary and force contact_support as primary.
    raw_secondary = ia.get("secondary_intents") if isinstance(ia.get("secondary_intents"), list) else []
    secondary_cats = {
        s["category"]: _clamp(s.get("confidence"), 0.0, 1.0, 0.5)
        for s in raw_secondary
        if isinstance(s, dict) and s.get("category") in ALLOWED_CAT_SET
    }

    if preflight_escalation and pi["category"] != "contact_support":
        # Demote current primary to secondary
        if pi["category"] and pi["category"] not in secondary_cats:
            secondary_cats[pi["category"]] = pi["confidence"]
        # Force contact_support as primary
        pi["category"]   = "contact_support"
        pi["confidence"] = max(pi["confidence"], 0.90)
        pi["reason"]     = "Customer explicitly requested escalation or contact with a representative."

    ia["primary_intent"] = pi

    ia["secondary_intents"] = [
        {"category": cat, "confidence": conf}
        for cat, conf in secondary_cats.items()
        if cat != pi["category"] and conf > 0.4
    ]
    all_cats = list({pi["category"]} | {s["category"] for s in ia["secondary_intents"]})
    ia["all_categories"] = all_cats
    data["intent_analysis"] = ia

    # ── entity_extraction (expanded — Problem 3 fix) ──────────────────────────
    ee = data.get("entity_extraction") if isinstance(data.get("entity_extraction"), dict) else {}
    ee["products"]       = _str_list(ee.get("products"))
    ee["specifications"] = _str_list(ee.get("specifications"))
    ee["technologies"]   = _str_list(ee.get("technologies"))
    ee["industries"]     = _str_list(ee.get("industries"))
    data["entity_extraction"] = ee

    # ── retrieval_strategy — budget enforced + retrieval_intent_type ─────────
    # Hard limits (Critical Issue #3): max 3 cats, max 3 queries/cat, max 8 total
    MAX_CATEGORIES           = 3
    MAX_QUERIES_PER_CATEGORY = 3
    MAX_TOTAL_QUERIES        = 8

    rs       = data.get("retrieval_strategy") if isinstance(data.get("retrieval_strategy"), dict) else {}
    raw_cats = rs.get("categories") if isinstance(rs.get("categories"), list) else []

    valid_cats   = []
    seen_cats    = set()
    standalone   = ca.get("standalone_query", "")
    total_budget = MAX_TOTAL_QUERIES

    for entry in raw_cats:
        if not isinstance(entry, dict):
            continue
        if len(valid_cats) >= MAX_CATEGORIES or total_budget <= 0:
            break
        cat = entry.get("category", "")
        if cat not in ALLOWED_CAT_SET or cat in seen_cats:
            continue
        queries = [q.strip() for q in _str_list(entry.get("search_queries")) if len(q.strip()) > 8]
        # Cap per-category
        queries = queries[:MAX_QUERIES_PER_CATEGORY]
        # Cap to remaining budget
        queries = queries[:total_budget]
        # Deduplicate semantically similar queries
        queries = _deduplicate_queries(queries)
        if not queries:
            continue
        # Minimum 2 queries — add standalone as second if only 1 returned
        if len(queries) < 2 and standalone and standalone not in queries:
            queries.append(standalone)
            queries = queries[:MAX_QUERIES_PER_CATEGORY]
        # retrieval_intent_type validation (Critical Issue #4)
        rit = entry.get("retrieval_intent_type", "")
        if rit not in VALID_RETRIEVAL_INTENT_TYPES:
            rit = _infer_retrieval_intent_type(cat)
        valid_cats.append({
            "category":              cat,
            "priority":             max(1, min(5, int(entry.get("priority", 99)))),
            "retrieval_intent_type": rit,
            "search_queries":        queries,
        })
        seen_cats.add(cat)
        total_budget -= len(queries)

    # Guarantee primary intent category is always present
    if pi["category"] and pi["category"] not in seen_cats and total_budget > 0:
        q1 = standalone or ca.get("current_focus") or "general inquiry"
        q2 = ca.get("resolved_reference", "")
        fb_queries = list(dict.fromkeys(q for q in [q1, q2] if q and len(q) > 8))
        if len(fb_queries) < 2:
            fb_queries.append(f"{pi['category'].replace('_', ' ')} inquiry")
        fb_queries = fb_queries[:min(MAX_QUERIES_PER_CATEGORY, total_budget)]
        valid_cats.insert(0, {
            "category":              pi["category"],
            "priority":              1,
            "retrieval_intent_type": _infer_retrieval_intent_type(pi["category"]),
            "search_queries":        fb_queries,
        })
        valid_cats = sorted(valid_cats, key=lambda x: x["priority"])

    rs["categories"] = valid_cats
    data["retrieval_strategy"] = rs

    # ── analytics_decision — subtype-aware analytics routing ─────────────────
    # Architecture: analytics records are stored as:
    #   category = <real category>  (e.g. "product_service")
    #   subtype  = "data_analytics"
    # The retrieval layer uses analytics_categories to search
    # category=X + subtype=data_analytics for each X in the list.
    #
    # Validation logic (priority order):
    #   1. If pre-flight detected high-confidence analytics intent → override LLM
    #   2. If LLM returned requires_analytics=true → validate and repair categories
    #   3. If neither → analytics off
    #
    # analytics_confidence is the HIGHER of pre-flight score and LLM-returned score.
    # This prevents the LLM from under-reporting analytics intent.

    ad = data.get("analytics_decision") if isinstance(data.get("analytics_decision"), dict) else {}

    llm_requires_analytics    = bool(ad.get("requires_analytics", False))
    llm_analytics_confidence  = _clamp(ad.get("analytics_confidence"), 0.0, 1.0, 0.0)

    # Final requires_analytics = either pre-flight OR LLM detected it
    requires_analytics = llm_requires_analytics or preflight_analytics

    # Final analytics_confidence = max of pre-flight and LLM scores
    analytics_confidence = max(preflight_analytics_confidence, llm_analytics_confidence)
    if requires_analytics and analytics_confidence < 0.70:
        analytics_confidence = max(analytics_confidence, 0.75)  # floor when triggered

    # Determine the analytics categories (which real categories need analytics subtype)
    if not requires_analytics:
        ad["requires_analytics"]     = False
        ad["analytics_confidence"]   = 0.0
        ad["analytics_categories"]   = []
    else:
        ad["requires_analytics"]   = True
        ad["analytics_confidence"] = round(analytics_confidence, 3)

        # Collect categories from LLM output — normalize to list of category strings
        raw_ac = ad.get("analytics_categories") if isinstance(ad.get("analytics_categories"), list) else []
        validated_ac_cats: list[str] = []

        for item in raw_ac:
            if isinstance(item, dict):
                # LLM returned {"primary_category": "...", "reason": "..."}
                pc = str(item.get("primary_category", "")).strip()
                if pc in ALLOWED_CAT_SET and pc not in validated_ac_cats:
                    validated_ac_cats.append(pc)
            elif isinstance(item, str) and item.strip() in ALLOWED_CAT_SET:
                # LLM returned plain string category names
                pc = item.strip()
                if pc not in validated_ac_cats:
                    validated_ac_cats.append(pc)

        # If LLM returned no valid categories, default to the primary intent category
        if not validated_ac_cats:
            default_cat = pi.get("category", "")
            if default_cat and default_cat in ALLOWED_CAT_SET:
                validated_ac_cats = [default_cat]
            else:
                validated_ac_cats = ["product_service"]

        # If pre-flight detected analytics phrases, ensure their implied category is included.
        # We infer from the phrase context which category is most relevant.
        if preflight_analytics_phrases:
            implied_cat = _infer_analytics_category_from_phrases(
                preflight_analytics_phrases, pi.get("category", ""), business_context
            )
            if implied_cat and implied_cat not in validated_ac_cats:
                validated_ac_cats.append(implied_cat)

        # Normalize to structured list format for downstream consumers
        ad["analytics_categories"] = [
            {"primary_category": cat, "reason": _get_analytics_reason(cat, preflight_analytics_phrases)}
            for cat in validated_ac_cats
        ]

        if preflight_analytics_confidence >= 0.85:
            logger.debug(
                "[P1] pre-flight analytics | confidence=%.2f phrases=%s cats=%s",
                preflight_analytics_confidence, preflight_analytics_phrases[:3], validated_ac_cats,
            )

    data["analytics_decision"] = ad

    # ── retrieval_constraints ─────────────────────────────────────────────────
    rc  = data.get("retrieval_constraints") if isinstance(data.get("retrieval_constraints"), dict) else {}
    mic = [c for c in _str_list(rc.get("must_include_categories")) if c in ALLOWED_CAT_SET]
    if not mic and pi["category"]:
        mic = [pi["category"]]
    mec      = [c for c in _str_list(rc.get("must_exclude_categories")) if c in ALLOWED_CAT_SET and c not in mic]
    min_conf = _clamp(rc.get("minimum_confidence"), 0.5, 1.0, 0.75)
    rc["must_include_categories"] = mic
    rc["must_exclude_categories"] = mec
    rc["minimum_confidence"]      = min_conf
    data["retrieval_constraints"] = rc

    # ── routing_decision — Context State Decay (Critical Issue #1) ──────────
    # CRITICAL: escalation_requested is derived SOLELY from preflight_escalation
    # (latest message keyword scan). We NEVER read rd.get("escalation_requested")
    # from the LLM output because the LLM sees full history and will incorrectly
    # carry forward escalation flags from previous messages.
    rd = data.get("routing_decision") if isinstance(data.get("routing_decision"), dict) else {}

    # Sole authority: latest message keyword scan only
    escalation_requested = preflight_escalation

    sentiment = ca.get("customer_sentiment", "unknown")
    urgency   = ca.get("urgency", "normal")
    is_issue  = pi["category"] == "issue_resolution"

    requires_human = (
        escalation_requested
        or sentiment == "frustrated"
        or urgency in ("high", "critical")
        or (is_issue and sentiment in ("negative", "frustrated"))
    )

    if escalation_requested and sentiment == "frustrated":
        r_priority = "critical"
    elif escalation_requested or urgency == "high":
        r_priority = "high"
    elif urgency == "critical":
        r_priority = "critical"
    else:
        r_priority = "normal"

    rd["requires_human_attention"] = requires_human
    rd["escalation_requested"]     = escalation_requested
    rd["routing_department"]       = pi["category"] or "product_service"
    rd["routing_priority"]         = r_priority
    data["routing_decision"] = rd

    # ── entity_extraction — specification validation (Critical Issue #2) ─────
    spec_uncertain, confidence_penalty = _validate_specs(ee.get("specifications", []))
    if spec_uncertain:
        ca["conversation_confidence"] = max(0.1, ca["conversation_confidence"] - confidence_penalty)
        data["conversation_analysis"] = ca
    ee["specification_uncertain"] = spec_uncertain
    data["entity_extraction"] = ee

    # ── business_signals (Medium Issue #3) ────────────────────────────────────
    bs = data.get("business_signals") if isinstance(data.get("business_signals"), dict) else {}
    data["business_signals"] = {
        "sales_opportunity": bool(bs.get("sales_opportunity", False)),
        "support_case":      bool(bs.get("support_case",      False)),
        "refund_risk":       bool(bs.get("refund_risk",       False)),
        "churn_risk":        bool(bs.get("churn_risk",        False)),
        "escalation_risk":   bool(bs.get("escalation_risk",   False)) or escalation_requested or sentiment == "frustrated",
    }

    # ── state_transition ──────────────────────────────────────────────────────
    st = data.get("state_transition") if isinstance(data.get("state_transition"), dict) else {}
    data["state_transition"] = {
        "previous_focus": _str(st.get("previous_focus"), "unknown"),
        "current_focus":  _str(st.get("current_focus"),  ca.get("current_focus", "unknown")),
        "focus_changed":  bool(st.get("focus_changed",   False)),
    }

    return data


# ── Fallback output ────────────────────────────────────────────────────────────

def _build_fallback(latest_body: str, subject: str, reason: str) -> dict:
    query = (latest_body or subject or "customer inquiry").strip()
    cat   = _infer_category(query)
    q2    = f"{cat.replace('_', ' ')} related inquiry"
    return {
        "pipeline_version": "1.0",
        "conversation_analysis": {
            "conversation_topic": subject or "unknown",
            "current_focus":      query[:200],
            "customer_goal":      "unknown",
            "conversation_stage": "unknown",
            "customer_sentiment": "unknown",
            "urgency":            "normal",
            "latest_message":     latest_body or "unknown",
            "resolved_reference": latest_body or "unknown",
            "standalone_query":   query[:300],
            "conversation_confidence": 0.3,
        },
        "intent_analysis": {
            "primary_intent":    {"category": cat, "confidence": 0.3, "reason": "fallback — processor failed"},
            "secondary_intents": [],
            "all_categories":    [cat],
        },
        "entity_extraction": {"products": [], "specifications": [], "technologies": [], "industries": []},
        "retrieval_strategy": {
            "categories": [{"category": cat, "priority": 1, "search_queries": [query[:300], q2]}],
        },
        "analytics_decision":  {"requires_analytics": False, "analytics_confidence": 0.0, "analytics_categories": []},
        "retrieval_constraints": {
            "must_include_categories": [cat],
            "must_exclude_categories": [],
            "minimum_confidence":      0.6,
        },
        "routing_decision": {
            "requires_human_attention": False,
            "escalation_requested":     False,
            "routing_department":       cat,
            "routing_priority":         "normal",
        },
        "business_signals": {
            "sales_opportunity": False,
            "support_case":      False,
            "refund_risk":       False,
            "churn_risk":        False,
            "escalation_risk":   False,
        },
        "state_transition": {
            "previous_focus": "unknown",
            "current_focus":  query[:100],
            "focus_changed":  False,
        },
        "_meta": {"status": "fallback", "reason": reason, "elapsed_ms": 0.0},
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _str(value: Any, default: str = "unknown") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _clamp(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _infer_retrieval_intent_type(category: str) -> str:
    """Map a category to its most likely retrieval intent type."""
    mapping = {
        "product_service":     "catalog_lookup",
        "offers_promotions":   "catalog_lookup",
        "delivery_shipping":   "fact_lookup",
        "company_info":        "fact_lookup",
        "educational_content": "fact_lookup",
        "contact_support":     "contact_lookup",
        "policies_legal":      "policy_lookup",
        "issue_resolution":    "troubleshooting_lookup",
        # NOTE: "data_analytics" removed — it is a subtype, not a category.
        # Analytics retrieval uses analytics_lookup intent type when the
        # retrieval layer searches category=X + subtype=data_analytics.
    }
    return mapping.get(category, "fact_lookup")


def _validate_specs(specifications: list[str]) -> tuple[bool, float]:
    """
    Universal domain-agnostic specification impossibility detector.

    Strategy: ONLY flag specifications that are physically/mathematically
    impossible regardless of industry. Never assumes a specific domain.

    Rules:
      - Negative numeric quantities are always impossible
      - Astronomically large values for known units (e.g. 5000 TB RAM) are impossible
      - Everything else is preserved as-is — the LLM extracted it verbatim

    Works correctly for: tech, healthcare, real estate, retail, finance,
    manufacturing, SaaS, education, hospitality — any business type.

    Returns (specification_uncertain, confidence_penalty).
    Preserves original customer wording. Never rewrites or corrects.
    """
    for spec in specifications:
        s = spec.lower().strip()
        for pattern, label, max_val in SPEC_IMPOSSIBILITY_RULES:
            m = re.search(pattern, s)
            if m:
                if label == "negative":
                    # Any explicitly negative quantity is impossible
                    return True, 0.15
                if max_val is not None:
                    try:
                        val = float(m.group(1))
                        if val > max_val:
                            return True, 0.15
                    except (ValueError, IndexError):
                        pass
    return False, 0.0


def _deduplicate_queries(queries: list[str]) -> list[str]:
    """
    Remove semantically duplicate queries using token-level Jaccard similarity.
    Queries with Jaccard similarity > 0.60 on their token sets are considered duplicates.
    Keeps the first occurrence (highest priority query stays).
    Works for any language/domain — pure token comparison, no ML needed.
    """
    kept: list[str] = []
    kept_token_sets: list[frozenset[str]] = []
    # Common stop words to exclude from similarity comparison
    STOP = {"the", "a", "an", "of", "for", "and", "or", "in", "on", "at", "to",
            "is", "are", "be", "do", "how", "what", "any", "all", "get", "me",
            "my", "your", "about", "with", "by", "from", "it", "its", "our"}
    for q in queries:
        tokens = frozenset(t for t in q.lower().split() if t not in STOP and len(t) > 2)
        is_dup = False
        for existing_tokens in kept_token_sets:
            if not tokens or not existing_tokens:
                continue
            intersection = len(tokens & existing_tokens)
            union = len(tokens | existing_tokens)
            jaccard = intersection / union if union > 0 else 0.0
            if jaccard > 0.60:
                is_dup = True
                break
        if not is_dup:
            kept.append(q)
            kept_token_sets.append(tokens)
    return kept


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS INTENT DETECTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _detect_analytics_intent(
    text: str,
) -> tuple[bool, float, list[str]]:
    """
    Pre-flight analytics intent scorer using ANALYTICS_INTENT_KEYWORDS.

    Scans the combined conversation text (all messages + latest body) for
    explicit analytics trigger phrases and returns a scored decision BEFORE
    the LLM call. This allows the validator to correct the LLM if it missed
    an analytics signal.

    Algorithm:
      1. Normalize input text to lowercase
      2. Scan ANALYTICS_INTENT_KEYWORDS in order (highest confidence first)
      3. Accumulate matched phrases and take the MAX confidence score
      4. Requires confidence >= 0.80 to set requires_analytics = True

    Domain-agnostic: works for any business type — SaaS, retail, healthcare,
    manufacturing, finance, etc. The keywords cover universal aggregate/summary
    intent patterns that any customer might express.

    Returns:
        (requires_analytics: bool, confidence: float, matched_phrases: list[str])

    Examples:
        "how many products do you have?" → (True, 0.95, ["how many"])
        "average price of your laptops"  → (True, 0.97, ["average price"])
        "summarize your catalog"         → (True, 0.92, ["summarize"])
        "tell me about your laptops"     → (False, 0.0, [])
        "show me best gaming laptops"    → (False, 0.0, [])
    """
    t = text.lower().strip()
    if not t:
        return False, 0.0, []

    matched_phrases: list[str] = []
    max_confidence = 0.0

    for phrase, confidence in ANALYTICS_INTENT_KEYWORDS:
        if phrase in t:
            matched_phrases.append(phrase)
            if confidence > max_confidence:
                max_confidence = confidence

    # Require >= 0.80 confidence threshold to trigger analytics
    # This prevents weak partial matches from activating analytics retrieval
    ANALYTICS_CONFIDENCE_THRESHOLD = 0.80
    requires = max_confidence >= ANALYTICS_CONFIDENCE_THRESHOLD and bool(matched_phrases)

    return requires, round(max_confidence, 3), matched_phrases


def _infer_analytics_category_from_phrases(
    matched_phrases: list[str],
    primary_intent_category: str,
    business_context: dict | None = None,
) -> str:
    """
    Infer which real category the analytics query targets based on matched phrases.

    When the LLM returns analytics_categories but misses an implied category,
    this function uses the matched phrases + primary intent category to determine
    the correct real category for analytics subtype retrieval.

    Logic (priority order):
      1. Phrase-to-category signal map: specific phrases strongly imply a category
         (e.g. "shipping capabilities" → delivery_shipping)
      2. Primary intent category fallback: if no phrase maps cleanly, the primary
         intent category is the most likely analytics target
      3. Business context augmentation: for ambiguous phrases, checks business
         description to disambiguate (e.g. "product overview" for a food company
         still maps to product_service)

    Domain-agnostic: category signals are derived from universal analytics
    vocabulary, not from business-specific product names.

    Returns the category string (one of the 8 valid categories).
    """
    if not matched_phrases:
        return primary_intent_category or "product_service"

    # Phrase → category signal map (highest specificity first)
    PHRASE_CATEGORY_MAP: list[tuple[str, str]] = [
        # Product catalog signals
        ("product overview",      "product_service"),
        ("catalog overview",      "product_service"),
        ("catalog summary",       "product_service"),
        ("product tiers",         "product_service"),
        ("pricing tiers",         "product_service"),
        ("price distribution",    "product_service"),
        ("price breakdown",       "product_service"),
        ("price range",           "product_service"),
        ("average price",         "product_service"),
        ("avg price",             "product_service"),
        ("cheapest",              "product_service"),
        ("most expensive",        "product_service"),
        ("total products",        "product_service"),
        ("how many products",     "product_service"),
        ("category distribution", "product_service"),
        ("category breakdown",    "product_service"),
        ("how many categories",   "product_service"),

        # Offers/promotions signals
        ("offer summary",         "offers_promotions"),
        ("total offers",          "offers_promotions"),
        ("how many offers",       "offers_promotions"),
        ("discount distribution", "offers_promotions"),
        ("audience segment",      "offers_promotions"),
        ("offer type",            "offers_promotions"),

        # Shipping/delivery signals
        ("shipping capabilities", "delivery_shipping"),
        ("shipping overview",     "delivery_shipping"),
        ("delivery methods",      "delivery_shipping"),
        ("shipping methods",      "delivery_shipping"),
        ("what delivery",         "delivery_shipping"),
        ("what shipping",         "delivery_shipping"),
        ("speed breakdown",       "delivery_shipping"),
        ("how many shipping",     "delivery_shipping"),

        # Contact/support signals
        ("support structure",     "contact_support"),
        ("support teams",         "contact_support"),
        ("what departments",      "contact_support"),
        ("department breakdown",  "contact_support"),
        ("which departments",     "contact_support"),
        ("channel breakdown",     "contact_support"),
        ("what channels",         "contact_support"),
        ("how many departments",  "contact_support"),

        # Policies/legal signals
        ("policy coverage",       "policies_legal"),
        ("coverage breakdown",    "policies_legal"),
        ("what policies",         "policies_legal"),
        ("what policy",           "policies_legal"),
        ("how many policies",     "policies_legal"),

        # Educational content signals
        ("skill level",           "educational_content"),
        ("skill distribution",    "educational_content"),
        ("topic coverage",        "educational_content"),
        ("content type",          "educational_content"),
        ("what content",          "educational_content"),
        ("what topics",           "educational_content"),

        # Company info signals
        ("company profile",       "company_info"),
        ("company overview",      "company_info"),
    ]

    # Check each phrase against the map
    for phrase in matched_phrases:
        for map_phrase, category in PHRASE_CATEGORY_MAP:
            if map_phrase in phrase or phrase in map_phrase:
                return category

    # Fallback to primary intent category
    if primary_intent_category and primary_intent_category in {
        "product_service", "offers_promotions", "delivery_shipping",
        "company_info", "educational_content", "contact_support",
        "policies_legal", "issue_resolution",
    }:
        return primary_intent_category

    return "product_service"


def _get_analytics_reason(
    category: str,
    matched_phrases: list[str],
) -> str:
    """
    Generate a human-readable reason string for why analytics was triggered
    for a given category. Used in the analytics_categories output for
    observability and downstream context.

    Domain-agnostic: reasons are generic enough to apply to any business.
    """
    phrase_preview = ", ".join(f'"{p}"' for p in matched_phrases[:3]) if matched_phrases else "analytics signal"

    CATEGORY_REASON_TEMPLATES: dict[str, str] = {
        "product_service":     f"Customer asking for product statistics, counts, or price distribution ({phrase_preview})",
        "offers_promotions":   f"Customer asking for offer statistics, counts, or discount summary ({phrase_preview})",
        "delivery_shipping":   f"Customer asking for shipping capabilities, options summary, or delivery counts ({phrase_preview})",
        "company_info":        f"Customer asking for company overview or profile summary ({phrase_preview})",
        "educational_content": f"Customer asking for content distribution, skill levels, or topic coverage ({phrase_preview})",
        "contact_support":     f"Customer asking for support structure, department breakdown, or channel summary ({phrase_preview})",
        "policies_legal":      f"Customer asking for policy coverage, count, or legal area distribution ({phrase_preview})",
        "issue_resolution":    f"Customer asking for issue statistics, resolution rate, or category breakdown ({phrase_preview})",
    }
    return CATEGORY_REASON_TEMPLATES.get(
        category,
        f"Analytics intent detected via: {phrase_preview}"
    )


def _check_escalation_triggers(text_lower: str) -> bool:
    """
    Precision escalation detection using phrase-aware matching.

    Algorithm:
      1. Multi-word phrases are matched as substrings (exact phrase match).
         e.g. "speak to" matches "i want to speak to someone" correctly.
      2. Single-word triggers use word-boundary regex to prevent false positives:
         - "senior" should NOT match "seniority"
         - "manager" should NOT match "management"
         - "escalate" SHOULD match "please escalate this"

    Returns True if ANY trigger phrase is detected in the text.
    """
    for trigger in ESCALATION_TRIGGER_WORDS:
        if " " in trigger:
            # Multi-word phrase — simple substring match is correct
            if trigger in text_lower:
                return True
        else:
            # Single word — require word boundary to avoid partial matches
            if re.search(r'\b' + re.escape(trigger) + r'\b', text_lower):
                return True
    return False


def _infer_category(text: str, business_context: dict | None = None) -> str:
    """
    Enterprise keyword-based category fallback.

    Used ONLY when the LLM returns an invalid or missing category.
    Primary classifier is always OpenAI Processor #1.

    Architecture (in order of execution):
      1. Business-context domain overlap check — boosts product_service accuracy
         for business-specific vocabulary (e.g. "flight range" for a drone company)
      2. Escalation phrase detection — runs FIRST among keyword checks because
         escalation signals are high-priority routing overrides
      3. Category keyword matching — evaluates each category's keyword set in
         priority order. Multi-word phrases are checked before single words.
         Uses substring matching for phrases, word-boundary for single words.
      4. Default fallback → product_service (most common intent)

    Keyword sets are defined in prompts.py (ISSUE_RESOLUTION_KEYWORDS, etc.)
    and cover real customer language, not formal/technical vocabulary.

    Design principles:
      - Most specific multi-word phrases before single words
      - issue_resolution checked AFTER contact_support (escalation wins over issues)
      - delivery_shipping checked before offers_promotions (shipping charge vs. discount)
      - Never hardcodes business-specific terms — works for any business

    Examples of correctly handled real-world phrases:
      "it isn't working"         → issue_resolution
      "something went wrong"     → issue_resolution
      "I can't log in"           → issue_resolution
      "my order never arrived"   → issue_resolution
      "speak to your manager"    → contact_support (escalation override)
      "shipping charges"         → delivery_shipping
      "shipping fee"             → delivery_shipping
      "where is my order"        → delivery_shipping
      "any discounts?"           → offers_promotions
      "enterprise plan pricing"  → offers_promotions
      "return policy"            → policies_legal
      "want my money back"       → policies_legal
      "how to set up"            → educational_content
      "about your company"       → company_info
      "total orders this month"  → data_analytics
    """
    t = text.lower().strip()

    # ── 1. Business-domain vocabulary overlap ─────────────────────────────────
    # When query overlaps substantially with business description vocabulary,
    # lean product_service but still run all keyword checks below.
    # (Product vocabulary check is implicit — product_service is the default.)
    if business_context and business_context.get("_loaded"):
        biz_text = (
            (business_context.get("business_description") or "") + " " +
            (business_context.get("business_type") or "") + " " +
            " ".join(business_context.get("industry") or [])
        ).lower()
        STOP = {"the", "and", "for", "are", "our", "with", "that", "this",
                "from", "has", "have", "was", "been", "will", "can", "all"}
        biz_tokens   = {w for w in biz_text.split() if len(w) > 2 and w not in STOP}
        query_tokens = set(t.split())
        # Substantial domain overlap — still fall through to keyword checks
        _domain_match = len(biz_tokens & query_tokens) >= 2

    # ── 2. Escalation override — checked FIRST (highest routing priority) ─────
    if _check_escalation_triggers(t):
        return "contact_support"

    # ── 3. Category keyword matching — priority order ─────────────────────────
    # Each category uses its enterprise keyword set from prompts.py.
    # Multi-word phrases are checked as substrings; single words as whole words.

    def _matches(keyword_set: frozenset[str]) -> bool:
        for kw in keyword_set:
            if " " in kw:
                if kw in t:
                    return True
            else:
                if re.search(r'\b' + re.escape(kw) + r'\b', t):
                    return True
        return False

    # Delivery/shipping before offers — "shipping charge" is logistics, not a discount
    if _matches(DELIVERY_SHIPPING_KEYWORDS):
        return "delivery_shipping"

    # Policies/legal before issue — "return policy" is legal, not an issue
    if _matches(POLICIES_LEGAL_KEYWORDS):
        return "policies_legal"

    # Issue resolution — broadest problem vocabulary
    if _matches(ISSUE_RESOLUTION_KEYWORDS):
        return "issue_resolution"

    # Contact support — human routing requests
    if _matches(CONTACT_SUPPORT_KEYWORDS):
        return "contact_support"

    # Offers/promotions — pricing and discount signals
    if _matches(OFFERS_PROMOTIONS_KEYWORDS):
        return "offers_promotions"

    # Educational content — how-to and guide signals
    if _matches(EDUCATIONAL_CONTENT_KEYWORDS):
        return "educational_content"

    # NOTE: DATA_ANALYTICS_KEYWORDS intentionally NOT routed to "data_analytics" here.
    # "data_analytics" is a SUBTYPE, not a category. Analytics signals are handled by
    # _detect_analytics_intent() which sets analytics_decision.requires_analytics=True.
    # The category fallback remains "product_service" — the retrieval layer will add
    # subtype=data_analytics filter on top via the analytics_decision output.

    # Company info — identity and background signals
    if _matches(COMPANY_INFO_KEYWORDS):
        return "company_info"

    # Product/service — catalog and availability signals (also covers analytics signals)
    if _matches(PRODUCT_SERVICE_KEYWORDS):
        return "product_service"

    # ── 4. Default fallback ───────────────────────────────────────────────────
    return "product_service"
