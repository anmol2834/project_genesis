"""
automationservice — LLM Processor #1: Analysis & Retrieval Planning

Responsibilities:
  - Build a structured conversation string for the LLM
  - Call OpenAI with the enterprise system prompt
  - Validate and repair the JSON output against the required schema
  - Return a guaranteed-valid Processor1Output dict

Enterprise hardening:
  - Pre-flight analytics keyword check (avoids LLM mistake on analytics flag)
  - Retry with exponential backoff (up to OPENAI_MAX_RETRIES from config)
  - JSON extraction from markdown fences if model wraps output
  - Schema validation with field-level type coercion
  - Fallback to safe minimal output on total failure (never raises to caller)
  - Strict allowed-category enforcement (strips hallucinated categories)
"""
from __future__ import annotations
import json
import logging
import os
import re
import sys
import time
import asyncio
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
)

logger = logging.getLogger("automationservice.processor_1")

# Lazy singleton client — created once, reused across all calls
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        cfg = get_config()
        _client = AsyncOpenAI(
            api_key=cfg.OPENAI_API_KEY,
            timeout=cfg.OPENAI_TIMEOUT_SECONDS,
            max_retries=0,   # we handle retries ourselves for precise control
        )
    return _client


# ── Schema constants ───────────────────────────────────────────────────────────

VALID_STAGES     = {"awareness", "discovery", "evaluation", "comparison", "purchase",
                    "post_purchase", "support", "escalation", "renewal", "retention", "unknown"}
VALID_SENTIMENTS = {"positive", "neutral", "negative", "frustrated", "urgent", "unknown"}
VALID_URGENCY    = {"low", "normal", "high", "critical"}
ALLOWED_CAT_SET  = set(ALLOWED_CATEGORIES)


# ── Public entry point ─────────────────────────────────────────────────────────

async def run_processor_1(
    messages: list[dict],
    latest_message: dict,
    conversation_meta: dict,
) -> dict:
    """
    Execute LLM Call #1: Analysis & Retrieval Planning.

    Args:
        messages:          Full conversation history (oldest → newest), each a row from es_messages.
        latest_message:    The triggering incoming message row from es_messages.
        conversation_meta: The es_conversations row for this thread.

    Returns:
        A guaranteed-valid Processor1Output dict. Never raises.
        On total failure, returns a safe fallback dict with status="fallback".
    """
    t0 = time.monotonic()
    cfg = get_config()

    # ── Build inputs ───────────────────────────────────────────────────────────
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

    # ── Pre-flight analytics detection ────────────────────────────────────────
    # Check analytics keywords in the ENTIRE conversation, not just latest message.
    # This catches cases where the LLM might miss the keyword.
    all_text_lower = " ".join(
        (m.get("content") or "") for m in messages
    ).lower()
    preflight_analytics = bool(ANALYTICS_KEYWORDS & set(re.findall(r'\b\w+\b', all_text_lower)))

    # ── Call OpenAI with retry ─────────────────────────────────────────────────
    raw_output = None
    last_error = None
    max_retries = max(1, cfg.OPENAI_MAX_RETRIES)

    for attempt in range(1, max_retries + 1):
        try:
            client = _get_client()
            response = await client.chat.completions.create(
                model       = cfg.OPENAI_MODEL,
                temperature = 0.0,        # deterministic — critical for extraction tasks
                top_p       = 1.0,
                seed        = 42,         # reproducible outputs across identical inputs
                response_format = {"type": "json_object"},  # forces JSON mode
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
            logger.warning("[P1] rate limit on attempt %d/%d — waiting %ds: %s",
                           attempt, max_retries, wait, e)
            if attempt < max_retries:
                await asyncio.sleep(wait)

        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            wait = 1 * attempt
            logger.warning("[P1] transient error on attempt %d/%d — waiting %ds: %s",
                           attempt, max_retries, wait, e)
            if attempt < max_retries:
                await asyncio.sleep(wait)

        except APIStatusError as e:
            last_error = e
            # 5xx → retry; 4xx (except 429) → do not retry
            if e.status_code >= 500 and attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("[P1] API status %d on attempt %d/%d — waiting %ds",
                               e.status_code, attempt, max_retries, wait)
                await asyncio.sleep(wait)
            else:
                logger.error("[P1] non-retryable API error %d: %s", e.status_code, e)
                break

        except Exception as e:
            last_error = e
            logger.error("[P1] unexpected error on attempt %d/%d: %s", attempt, max_retries, e)
            break

    elapsed_ms = (time.monotonic() - t0) * 1000

    if raw_output is None:
        logger.error("[P1] all attempts failed | last_error=%s | elapsed=%.0fms",
                     last_error, elapsed_ms)
        return _build_fallback(latest_body, subject, str(last_error))

    # ── Parse & validate ───────────────────────────────────────────────────────
    parsed = _parse_json(raw_output)
    if parsed is None:
        logger.error("[P1] JSON parse failure | raw=%s...", raw_output[:200])
        return _build_fallback(latest_body, subject, "json_parse_failure")

    validated = _validate_and_repair(parsed, latest_body, preflight_analytics)
    validated["_meta"] = {
        "elapsed_ms": round(elapsed_ms, 1),
        "model":      cfg.OPENAI_MODEL,
        "attempts":   attempt,
        "status":     "ok",
    }

    logger.info(
        "[P1] complete | intent=%s confidence=%.2f queries=%d analytics=%s elapsed=%.0fms",
        validated.get("intent_analysis", {}).get("primary_intent", {}).get("category", "?"),
        validated.get("conversation_analysis", {}).get("confidence", 0.0),
        sum(
            len(c.get("search_queries", []))
            for c in validated.get("retrieval_strategy", {}).get("categories", [])
        ),
        validated.get("analytics_decision", {}).get("requires_analytics", False),
        elapsed_ms,
    )

    return validated


# ── Conversation string builder ────────────────────────────────────────────────

def _build_conversation_string(messages: list[dict], latest_message: dict) -> str:
    """
    Format the conversation history into a clean, LLM-readable string.
    Excludes the latest message (it is passed separately).
    Direction labels: CUSTOMER / AGENT
    """
    lines = []
    latest_id = latest_message.get("message_id", "")

    for msg in messages:
        if msg.get("message_id") == latest_id:
            continue  # latest message is passed separately
        direction = (msg.get("direction") or "").upper()
        role = "CUSTOMER" if direction == "INCOMING" else "AGENT"
        content = (msg.get("content") or "").strip()
        ts      = (msg.get("timestamp") or "")[:16]
        if content:
            lines.append(f"[{ts}] {role}: {content}")

    if not lines:
        return "(no prior conversation history)"
    return "\n".join(lines)


# ── JSON parsing ───────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict | None:
    """
    Parse JSON from the model output.
    Handles: clean JSON, markdown code fences, leading/trailing whitespace.
    """
    raw = raw.strip()

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences: ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Find the outermost JSON object by bracket matching
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

def _validate_and_repair(data: dict, latest_body: str, preflight_analytics: bool) -> dict:
    """
    Validate the parsed output against the required schema.
    Repairs field-by-field rather than rejecting the whole output.
    Enforces allowed categories and pre-flight analytics override.
    """

    # ── pipeline_version ──────────────────────────────────────────────────────
    data["pipeline_version"] = "1.0"

    # ── conversation_analysis ─────────────────────────────────────────────────
    ca = data.get("conversation_analysis") if isinstance(data.get("conversation_analysis"), dict) else {}

    ca["conversation_topic"]  = _str(ca.get("conversation_topic"),  "unknown")
    ca["current_focus"]       = _str(ca.get("current_focus"),       "unknown")
    ca["customer_goal"]       = _str(ca.get("customer_goal"),       "unknown")
    ca["latest_message"]      = _str(ca.get("latest_message"),      latest_body or "unknown")
    ca["resolved_reference"]  = _str(ca.get("resolved_reference"),  ca["latest_message"])
    ca["standalone_query"]    = _str(ca.get("standalone_query"),     ca["current_focus"])
    ca["conversation_stage"]  = ca.get("conversation_stage") if ca.get("conversation_stage") in VALID_STAGES else "unknown"
    ca["customer_sentiment"]  = ca.get("customer_sentiment") if ca.get("customer_sentiment") in VALID_SENTIMENTS else "unknown"
    ca["urgency"]             = ca.get("urgency") if ca.get("urgency") in VALID_URGENCY else "normal"
    ca["confidence"]          = _clamp(ca.get("confidence"), 0.0, 1.0, 0.5)

    data["conversation_analysis"] = ca

    # ── intent_analysis ───────────────────────────────────────────────────────
    ia = data.get("intent_analysis") if isinstance(data.get("intent_analysis"), dict) else {}

    pi = ia.get("primary_intent") if isinstance(ia.get("primary_intent"), dict) else {}
    pi_cat = pi.get("category", "")
    if pi_cat not in ALLOWED_CAT_SET:
        # Attempt to infer from standalone_query
        pi_cat = _infer_category(ca.get("standalone_query", ""))
    pi["category"]   = pi_cat
    pi["confidence"] = _clamp(pi.get("confidence"), 0.0, 1.0, 0.5)
    pi["reason"]     = _str(pi.get("reason"), "inferred from conversation")
    ia["primary_intent"] = pi

    # Secondary intents — strip invalid categories
    raw_secondary = ia.get("secondary_intents") if isinstance(ia.get("secondary_intents"), list) else []
    ia["secondary_intents"] = [
        {"category": s["category"], "confidence": _clamp(s.get("confidence"), 0.0, 1.0, 0.5)}
        for s in raw_secondary
        if isinstance(s, dict) and s.get("category") in ALLOWED_CAT_SET and _clamp(s.get("confidence"), 0.0, 1.0, 0.0) > 0.4
    ]

    all_cats = list({pi["category"]} | {s["category"] for s in ia["secondary_intents"]} if pi["category"] else set())
    ia["all_categories"] = all_cats
    data["intent_analysis"] = ia

    # ── entity_extraction ─────────────────────────────────────────────────────
    ee = data.get("entity_extraction") if isinstance(data.get("entity_extraction"), dict) else {}
    ee["products"]      = _str_list(ee.get("products"))
    ee["technologies"]  = _str_list(ee.get("technologies"))
    ee["industries"]    = _str_list(ee.get("industries"))
    data["entity_extraction"] = ee

    # ── retrieval_strategy ────────────────────────────────────────────────────
    rs = data.get("retrieval_strategy") if isinstance(data.get("retrieval_strategy"), dict) else {}
    raw_cats = rs.get("categories") if isinstance(rs.get("categories"), list) else []

    valid_cats = []
    seen_cats  = set()
    for entry in raw_cats:
        if not isinstance(entry, dict):
            continue
        cat = entry.get("category", "")
        if cat not in ALLOWED_CAT_SET or cat in seen_cats:
            continue
        queries = _str_list(entry.get("search_queries"))
        # Filter blank/too-short queries
        queries = [q for q in queries if len(q.strip()) > 8]
        if not queries:
            continue
        valid_cats.append({
            "category":      cat,
            "priority":      max(1, min(5, int(entry.get("priority", 99)))),
            "search_queries": queries[:5],  # cap at 5 per category
        })
        seen_cats.add(cat)
        if len(valid_cats) >= 3:  # max 3 categories
            break

    # Guarantee primary intent category is always in retrieval_strategy
    if pi["category"] and pi["category"] not in seen_cats:
        fallback_query = ca.get("standalone_query") or ca.get("current_focus") or "general inquiry"
        valid_cats.insert(0, {
            "category":      pi["category"],
            "priority":      1,
            "search_queries": [fallback_query],
        })
        # Re-sort by priority
        valid_cats = sorted(valid_cats, key=lambda x: x["priority"])

    rs["categories"] = valid_cats
    data["retrieval_strategy"] = rs

    # ── analytics_decision ────────────────────────────────────────────────────
    ad = data.get("analytics_decision") if isinstance(data.get("analytics_decision"), dict) else {}

    # Pre-flight override: if keywords detected but LLM missed it, force True
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
            {"primary_category": _str(a.get("primary_category"), "unknown"), "reason": _str(a.get("reason"), "analytics keyword detected")}
            for a in raw_ac
            if isinstance(a, dict)
        ] or [{"primary_category": pi["category"] or "product_service", "reason": "analytics keyword detected in conversation"}]

    data["analytics_decision"] = ad

    # ── retrieval_constraints ─────────────────────────────────────────────────
    rc = data.get("retrieval_constraints") if isinstance(data.get("retrieval_constraints"), dict) else {}

    mic = _str_list(rc.get("must_include_categories"))
    mic = [c for c in mic if c in ALLOWED_CAT_SET]
    if not mic and pi["category"]:
        mic = [pi["category"]]

    mec = _str_list(rc.get("must_exclude_categories"))
    mec = [c for c in mec if c in ALLOWED_CAT_SET and c not in mic]

    min_conf = _clamp(rc.get("minimum_confidence"), 0.5, 1.0, 0.75)

    rc["must_include_categories"] = mic
    rc["must_exclude_categories"] = mec
    rc["minimum_confidence"]      = min_conf
    data["retrieval_constraints"] = rc

    return data


# ── Fallback output ────────────────────────────────────────────────────────────

def _build_fallback(latest_body: str, subject: str, reason: str) -> dict:
    """
    Return a safe minimal output when Processor 1 fails completely.
    This allows the pipeline to continue with degraded quality rather than crashing.
    The fallback always generates at least one search query from the available text.
    """
    query = (latest_body or subject or "customer inquiry").strip()
    cat   = _infer_category(query)

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
            "confidence":         0.3,
        },
        "intent_analysis": {
            "primary_intent":    {"category": cat, "confidence": 0.3, "reason": "fallback — processor failed"},
            "secondary_intents": [],
            "all_categories":    [cat],
        },
        "entity_extraction": {"products": [], "technologies": [], "industries": []},
        "retrieval_strategy": {
            "categories": [{"category": cat, "priority": 1, "search_queries": [query[:300]]}],
        },
        "analytics_decision": {"requires_analytics": False, "analytics_categories": []},
        "retrieval_constraints": {
            "must_include_categories": [cat],
            "must_exclude_categories": [],
            "minimum_confidence":      0.6,
        },
        "_meta": {"status": "fallback", "reason": reason, "elapsed_ms": 0.0},
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _str(value: Any, default: str = "unknown") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _clamp(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(value)
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return default


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _infer_category(text: str) -> str:
    """
    Simple keyword-based category inference used when the LLM returns
    an invalid or missing category. Returns the most likely allowed category.
    """
    t = text.lower()
    if any(w in t for w in ("ship", "deliver", "track", "logistic", "dispatch")):
        return "delivery_shipping"
    if any(w in t for w in ("price", "cost", "discount", "offer", "promo", "deal", "coupon")):
        return "offers_promotions"
    if any(w in t for w in ("policy", "return", "refund", "warranty", "term", "legal", "compliance")):
        return "policies_legal"
    if any(w in t for w in ("problem", "issue", "error", "bug", "broken", "not working", "complaint")):
        return "issue_resolution"
    if any(w in t for w in ("contact", "support", "help", "reach", "phone", "email address")):
        return "contact_support"
    if any(w in t for w in ("about", "company", "who are", "mission", "history", "location")):
        return "company_info"
    if any(w in t for w in ("how to", "tutorial", "guide", "learn", "training", "demo")):
        return "educational_content"
    if any(w in t for w in ("analytic", "metric", "report", "dashboard", "statistic", "trend")):
        return "data_analytics"
    return "product_service"
