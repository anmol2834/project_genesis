"""
automationservice — LLM Processor #1: Analysis & Retrieval Planning

Fixes applied (all 8 problems from log analysis):
  1. Action-first intent: ESCALATION_TRIGGER_WORDS override sentiment-based classification
  2. Query specificity: minimum 2 queries per category enforced in validator
  3. Entity expansion: specifications[] field added alongside products/technologies/industries
  4. Confidence calibration: short/greeting messages capped at 0.45 before validation
  5. Conversation topic specificity: validated in prompt (no code-level fix needed)
  6. Current focus enforcement: handled in prompt (latest message priority)
  7. Context-aware query rewriting: handled in prompt + user template
  8. Escalation detection: routing_decision{} block validated and repaired
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
    VALID_RETRIEVAL_INTENT_TYPES,
    ESCALATION_TRIGGER_WORDS,
    SPEC_IMPOSSIBILITY_RULES,
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
) -> dict:
    """
    Execute LLM Call #1: Analysis & Retrieval Planning.
    Never raises. Returns a guaranteed-valid dict.
    """
    t0  = time.monotonic()
    cfg = get_config()

    conversation_str = _build_conversation_string(messages, latest_message)
    latest_body      = (latest_message.get("content") or "").strip()
    subject          = conversation_meta.get("subject") or ""
    provider         = conversation_meta.get("provider") or ""
    message_count    = conversation_meta.get("message_count") or len(messages)
    participants     = conversation_meta.get("participants") or []

    user_prompt = PROCESSOR_1_USER_TEMPLATE.format(
        conversation_history = conversation_str,
        latest_message       = latest_body or "(empty message)",
        subject              = subject or "(no subject)",
        provider             = provider or "unknown",
        message_count        = message_count,
        participants         = ", ".join(participants) if participants else "unknown",
    )

    # ── Pre-flight checks ──────────────────────────────────────────────────────
    all_text_lower      = " ".join((m.get("content") or "") for m in messages).lower()
    preflight_analytics = bool(ANALYTICS_KEYWORDS & set(re.findall(r'\b\w+\b', all_text_lower)))

    # Detect escalation triggers in latest message for post-validation override
    latest_lower      = latest_body.lower()
    preflight_escalation = any(t in latest_lower for t in ESCALATION_TRIGGER_WORDS)

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
        return _build_fallback(latest_body, subject, str(last_error))

    parsed = _parse_json(raw_output)
    if parsed is None:
        logger.error("[P1] JSON parse failure | raw=%s...", raw_output[:200])
        return _build_fallback(latest_body, subject, "json_parse_failure")

    validated = _validate_and_repair(
        parsed,
        latest_body,
        preflight_analytics,
        preflight_escalation,
        max_conv_confidence,
    )
    validated["_meta"] = {
        "elapsed_ms": round(elapsed_ms, 1),
        "model":      cfg.OPENAI_MODEL,
        "attempts":   attempt,
        "status":     "ok",
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
    preflight_escalation: bool,
    max_conv_confidence: float,
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
        pi_cat = _infer_category(ca.get("standalone_query", ""))
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

    # ── analytics_decision ────────────────────────────────────────────────────
    ad = data.get("analytics_decision") if isinstance(data.get("analytics_decision"), dict) else {}
    requires_analytics = bool(ad.get("requires_analytics", False))
    if preflight_analytics and not requires_analytics:
        requires_analytics = True
        logger.debug("[P1] pre-flight analytics override applied")
    if not requires_analytics:
        ad["requires_analytics"]   = False
        ad["analytics_categories"] = []
    else:
        ad["requires_analytics"] = True
        raw_ac = ad.get("analytics_categories") if isinstance(ad.get("analytics_categories"), list) else []
        ad["analytics_categories"] = [
            {
                "primary_category": _str(a.get("primary_category"), "unknown"),
                "reason":           _str(a.get("reason"), "analytics keyword detected"),
            }
            for a in raw_ac if isinstance(a, dict)
        ] or [{"primary_category": pi["category"] or "product_service",
               "reason": "analytics keyword detected in conversation"}]
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
        "analytics_decision":  {"requires_analytics": False, "analytics_categories": []},
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
        "data_analytics":      "analytics_lookup",
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


def _infer_category(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ("ship", "deliver", "track", "logistic", "dispatch")):
        return "delivery_shipping"
    if any(w in t for w in ("price", "cost", "discount", "offer", "promo", "deal", "coupon")):
        return "offers_promotions"
    if any(w in t for w in ("policy", "return", "refund", "warranty", "term", "legal", "compliance")):
        return "policies_legal"
    if any(w in t for w in ("problem", "issue", "error", "bug", "broken", "not working", "complaint")):
        return "issue_resolution"
    if any(w in t for w in ("contact", "support", "help", "reach", "phone", "email address", "manager", "senior")):
        return "contact_support"
    if any(w in t for w in ("about", "company", "who are", "mission", "history", "location")):
        return "company_info"
    if any(w in t for w in ("how to", "tutorial", "guide", "learn", "training", "demo")):
        return "educational_content"
    if any(w in t for w in ("analytic", "metric", "report", "dashboard", "statistic", "trend")):
        return "data_analytics"
    return "product_service"
