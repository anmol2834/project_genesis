"""
automationservice — Centralized LLM Prompt Templates

v6 changes — Analytics-Aware Retrieval Planning:
  - ANALYTICS_INTENT_KEYWORDS: high-confidence explicit analytics triggers
    (counts, summaries, statistics, distributions, coverage questions).
    Separated from ANALYTICS_KEYWORDS (soft pre-flight signal set).
  - System prompt updated with full analytics retrieval planning section.
  - analytics_decision output schema extended with analytics_confidence and
    per-category analytics flags for subtype-aware Qdrant filtering.
  - Analytics must be triggered by EXPLICIT signals only — NOT by
    "recommend", "best", "top" (those remain product_service retrieval).
"""

ALLOWED_CATEGORIES = [
    "product_service",
    "offers_promotions",
    "delivery_shipping",
    "company_info",
    "educational_content",
    "contact_support",
    "policies_legal",
    "issue_resolution",
    # NOTE: "data_analytics" is NOT a category — it is a SUBTYPE.
    # Analytics records are stored as:
    #   category  = <real category>   (e.g. "product_service")
    #   subtype   = "data_analytics"
    # The retrieval layer uses category + subtype filter together.
    # Never search or route to "data_analytics" as a category.
]

VALID_RETRIEVAL_INTENT_TYPES = {
    "catalog_lookup",
    "fact_lookup",
    "troubleshooting_lookup",
    "analytics_lookup",
    "comparison_lookup",
    "contact_lookup",
    "policy_lookup",
}

# ══════════════════════════════════════════════════════════════════════════════
# ENTERPRISE KEYWORD SETS
# ══════════════════════════════════════════════════════════════════════════════
#
# Design principles:
#   1. Real customer language first — not formal/technical vocabulary
#   2. Multi-word phrases before single words (specificity wins)
#   3. Industry-agnostic — valid for SaaS, retail, healthcare, finance, etc.
#   4. Keywords are fallback safety layer only; OpenAI Processor #1 is primary
#   5. Never hardcode business-specific terms — these work for ANY business
#
# Usage: `_infer_category()` in processor_1.py iterates these sets IN ORDER.
#        First match wins → order determines priority.
#        More specific multi-word phrases come before single words.
# ══════════════════════════════════════════════════════════════════════════════

# ── issue_resolution ─────────────────────────────────────────────────────────
# Needs the largest set — customers never say "malfunction", they say "it stopped"
ISSUE_RESOLUTION_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word real customer phrases (most specific first)
    "not working",
    "isn't working",
    "doesn't work",
    "won't work",
    "stopped working",
    "not loading",
    "won't load",
    "not opening",
    "won't open",
    "not responding",
    "won't respond",
    "not connecting",
    "won't connect",
    "something went wrong",
    "having trouble",
    "having an issue",
    "facing an issue",
    "facing a problem",
    "experiencing an issue",
    "ran into a problem",
    "can't access",
    "cannot access",
    "can't login",
    "can't log in",
    "can't sign in",
    "unable to login",
    "unable to log in",
    "unable to access",
    "login problem",
    "login issue",
    "sign in problem",
    "payment failed",
    "payment not going through",
    "transaction failed",
    "charge failed",
    "order issue",
    "order problem",
    "order not received",
    "order never arrived",
    "item not received",
    "never arrived",
    "not delivered",
    "wrong item",
    "wrong product",
    "damaged product",
    "damaged item",
    "product damaged",
    "item damaged",
    "received damaged",
    "need help fixing",
    "need help with",
    "help me fix",
    "fix this",
    "resolve this",
    "fix the issue",
    "solve this",
    "technical issue",
    "technical problem",
    "technical error",
    "technical support needed",
    "support needed",
    # Single-word signals
    "issue",
    "issues",
    "problem",
    "problems",
    "error",
    "errors",
    "bug",
    "bugs",
    "failure",
    "failed",
    "broken",
    "damaged",
    "defect",
    "defective",
    "malfunction",
    "malfunctioning",
    "crash",
    "crashes",
    "crashing",
    "freezing",
    "frozen",
    "slow",
    "lagging",
    "glitch",
    "glitches",
    "unable",
    "cannot",
    "trouble",
    "difficulty",
    "complaint",
    "complain",
    "dissatisfied",
    "frustrated",
    "terrible",
    "horrible",
    "unacceptable",
})

# ── contact_support ───────────────────────────────────────────────────────────
# Often misclassified — customers use escalation language mixed with complaints
CONTACT_SUPPORT_KEYWORDS: frozenset[str] = frozenset({
    # Escalation / human request phrases
    "speak to someone",
    "speak to a person",
    "speak to an agent",
    "speak to a human",
    "speak to a representative",
    "talk to someone",
    "talk to a person",
    "talk to an agent",
    "talk to a human",
    "talk to a representative",
    "connect me with",
    "connect me to",
    "transfer me to",
    "transfer me",
    "put me through",
    "escalate this",
    "escalate my",
    "need a human",
    "want a human",
    "real person",
    "actual person",
    "live agent",
    "live support",
    "live chat",
    "human agent",
    "someone else",
    "another person",
    "get me a manager",
    "get me your manager",
    "let me speak to",
    "let me talk to",
    "i want to complain",
    "i need to complain",
    "complaint team",
    "complaints department",
    "your complaint",
    "lodge a complaint",
    "raise a complaint",
    "file a complaint",
    "register a complaint",
    "customer care",
    "customer success",
    "support team",
    "help desk",
    "helpdesk",
    "contact details",
    "contact information",
    "contact info",
    "phone number",
    "email address",
    "your email",
    "your phone",
    "your number",
    "reach you",
    "reach someone",
    "how to contact",
    "how do i contact",
    "how can i reach",
    "call you",
    "call me back",
    "call me",
    # Role signals
    "manager",
    "supervisor",
    "senior",
    "escalate",
    "escalation",
    "representative",
    "head of",
    "in charge",
    # Generic signals
    "contact",
    "support",
    "agent",
    "reach",
})

# ── delivery_shipping ─────────────────────────────────────────────────────────
DELIVERY_SHIPPING_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word real phrases
    "shipping charge",
    "shipping charges",
    "shipping fee",
    "shipping fees",
    "shipping cost",
    "shipping costs",
    "shipping time",
    "shipping timeline",
    "shipping address",
    "delivery charge",
    "delivery charges",
    "delivery fee",
    "delivery fees",
    "delivery cost",
    "delivery time",
    "delivery timeline",
    "estimated delivery",
    "delivery date",
    "expected delivery",
    "when will it arrive",
    "when will it be delivered",
    "how long will it take",
    "how long does delivery take",
    "how long does shipping take",
    "track order",
    "track my order",
    "order tracking",
    "track shipment",
    "where is my order",
    "where is my package",
    "order status",
    "shipment status",
    "same day delivery",
    "express delivery",
    "next day delivery",
    "overnight delivery",
    "international shipping",
    "international delivery",
    "free shipping",
    "free delivery",
    "return shipping",
    "exchange shipping",
    # Single-word signals
    "ship",
    "shipping",
    "deliver",
    "delivery",
    "dispatch",
    "courier",
    "freight",
    "cargo",
    "tracking",
    "shipment",
    "logistics",
    "eta",
})

# ── offers_promotions ─────────────────────────────────────────────────────────
OFFERS_PROMOTIONS_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word real phrases
    "any offers",
    "any discounts",
    "any deals",
    "any promotions",
    "current offers",
    "current discounts",
    "current deals",
    "special offer",
    "special discount",
    "special deal",
    "promo code",
    "discount code",
    "coupon code",
    "voucher code",
    "referral code",
    "free trial",
    "trial period",
    "subscription plan",
    "pricing plan",
    "pricing package",
    "monthly plan",
    "annual plan",
    "enterprise plan",
    "business plan",
    "starter plan",
    "pro plan",
    "bundle deal",
    "bundle offer",
    "bundle discount",
    "buy one get one",
    "bogo",
    "black friday",
    "cyber monday",
    "flash sale",
    "limited time offer",
    "limited time deal",
    "loyalty program",
    "loyalty discount",
    "reward points",
    "cashback offer",
    "referral bonus",
    "sign up bonus",
    # Single-word signals
    "price",
    "pricing",
    "cost",
    "quote",
    "quotation",
    "discount",
    "discounts",
    "offer",
    "offers",
    "promotion",
    "promotions",
    "promo",
    "deal",
    "deals",
    "coupon",
    "voucher",
    "cashback",
    "sale",
    "rebate",
    "campaign",
    "bundle",
    "trial",
    "incentive",
    "saving",
    "savings",
})

# ── policies_legal ────────────────────────────────────────────────────────────
POLICIES_LEGAL_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word real phrases
    "return policy",
    "refund policy",
    "cancellation policy",
    "warranty policy",
    "privacy policy",
    "data policy",
    "terms and conditions",
    "terms of service",
    "terms of use",
    "how do i return",
    "can i return",
    "want to return",
    "want a refund",
    "need a refund",
    "get a refund",
    "request a refund",
    "how to cancel",
    "can i cancel",
    "cancel my order",
    "cancel my subscription",
    "cancel subscription",
    "money back",
    "money back guarantee",
    "want my money back",
    "exchange policy",
    "replacement policy",
    "warranty claim",
    "warranty period",
    "under warranty",
    "covered by warranty",
    "data protection",
    "data privacy",
    "gdpr",
    "ccpa",
    "my data",
    "cookie policy",
    "acceptable use",
    "user agreement",
    "service agreement",
    "vendor agreement",
    "legal disclaimer",
    "export compliance",
    "equal opportunity",
    "supplier code",
    # Single-word signals
    "policy",
    "policies",
    "refund",
    "return",
    "replacement",
    "exchange",
    "cancellation",
    "warranty",
    "guarantee",
    "terms",
    "legal",
    "compliance",
    "contract",
    "agreement",
    "liability",
    "eligibility",
})

# ── product_service ───────────────────────────────────────────────────────────
PRODUCT_SERVICE_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word real phrases
    "what do you sell",
    "what do you offer",
    "what products do you have",
    "what services do you have",
    "show me products",
    "show me your products",
    "product list",
    "product catalog",
    "service list",
    "available products",
    "available services",
    "in stock",
    "available now",
    "do you have",
    "is it available",
    "how much does",
    "how much is",
    "what is the price",
    "what's the price",
    "pricing for",
    "price of",
    "cost of",
    "specifications for",
    "specs for",
    "features of",
    "what features",
    "tell me about",
    "more information about",
    "more details about",
    "what models",
    "which models",
    # Single-word signals
    "product",
    "products",
    "service",
    "services",
    "solution",
    "solutions",
    "catalog",
    "catalogue",
    "inventory",
    "stock",
    "available",
    "feature",
    "features",
    "capability",
    "capabilities",
    "specification",
    "specifications",
    "spec",
    "specs",
    "model",
    "models",
    "variant",
    "variants",
    "compatible",
    "compatibility",
    "buy",
    "purchase",
    "order",
    "offering",
    "offerings",
})

# ── company_info ──────────────────────────────────────────────────────────────
COMPANY_INFO_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word real phrases
    "about your company",
    "about the company",
    "who are you",
    "what is your company",
    "what company is this",
    "tell me about you",
    "tell me about your company",
    "company history",
    "company background",
    "company profile",
    "who founded",
    "when was it founded",
    "where are you located",
    "where is your office",
    "where are you based",
    "company headquarters",
    "your headquarters",
    "your office",
    "your team",
    "leadership team",
    "company mission",
    "company vision",
    "company values",
    "what do you stand for",
    # Single-word signals
    "about",
    "company",
    "business",
    "organization",
    "who",
    "history",
    "mission",
    "vision",
    "founder",
    "founders",
    "founded",
    "headquarters",
    "office",
    "location",
    "address",
    "team",
    "leadership",
    "background",
    "profile",
})

# ── educational_content ───────────────────────────────────────────────────────
EDUCATIONAL_CONTENT_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word real phrases
    "how to",
    "how do i",
    "how can i",
    "step by step",
    "setup guide",
    "getting started",
    "quick start",
    "user guide",
    "user manual",
    "instruction manual",
    "installation guide",
    "configuration guide",
    "video tutorial",
    "training video",
    "training material",
    "knowledge base",
    "help article",
    "best practices",
    "faq",
    "frequently asked",
    "commonly asked",
    "getting started guide",
    # Single-word signals
    "tutorial",
    "tutorials",
    "guide",
    "guides",
    "walkthrough",
    "training",
    "learn",
    "learning",
    "documentation",
    "docs",
    "manual",
    "instruction",
    "instructions",
    "setup",
    "installation",
    "configuration",
    "example",
    "examples",
    "demo",
    "onboarding",
    "academy",
    "course",
    "courses",
    "lesson",
    "lessons",
})

# ── data_analytics ────────────────────────────────────────────────────────────
DATA_ANALYTICS_KEYWORDS: frozenset[str] = frozenset({
    # Multi-word aggregate/reporting signals
    "how many",
    "how much total",
    "total count",
    "total number",
    "count of",
    "number of",
    "best selling",
    "best-selling",
    "top selling",
    "most popular",
    "most purchased",
    "least popular",
    "highest rated",
    "lowest rated",
    "most ordered",
    "least ordered",
    "month over month",
    "year over year",
    "conversion rate",
    "retention rate",
    "click-through",
    "open rate",
    "bounce rate",
    "revenue report",
    "sales report",
    "monthly report",
    "quarterly report",
    "data analysis",
    "data visualization",
    "data export",
    "sales data",
    "performance data",
    # Single-word signals
    "analytics",
    "analysis",
    "report",
    "reports",
    "dashboard",
    "metric",
    "metrics",
    "kpi",
    "kpis",
    "statistics",
    "statistic",
    "trend",
    "trends",
    "forecast",
    "forecasting",
    "roi",
    "performance",
    "growth",
    "insight",
    "insights",
    "revenue",
    "utilization",
    "engagement",
    "average",
    "avg",
    "median",
    "distribution",
    "breakdown",
    "ranking",
    "ranked",
})

# Domain-specific analytics keywords only — no generic English words
# Used for pre-flight analytics detection in processor_1.py
ANALYTICS_KEYWORDS = DATA_ANALYTICS_KEYWORDS

# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS INTENT KEYWORDS — HIGH CONFIDENCE TRIGGERS
# ══════════════════════════════════════════════════════════════════════════════
#
# These are EXPLICIT analytics intent signals that require analytics retrieval
# (subtype=data_analytics). They are MORE SPECIFIC than ANALYTICS_KEYWORDS.
#
# IMPORTANT DISTINCTION:
#   ANALYTICS_KEYWORDS  : broad set used for pre-flight soft check
#   ANALYTICS_INTENT_KEYWORDS : precise set used for determining analytics_confidence
#
# Analytics MUST trigger for:
#   - Count questions:     "how many", "total count", "number of"
#   - Stat questions:      "average price", "lowest price", "highest price"
#   - Summary questions:   "summarize", "overview", "catalog summary"
#   - Distribution:        "price distribution", "category breakdown"
#   - Coverage questions:  "what policies", "what departments exist"
#   - Intelligence:        "analytics", "statistics", "insights", "report"
#
# Analytics MUST NOT trigger for:
#   - "recommend best gaming laptops"   → product_service (no analytics signal)
#   - "show me top products"            → product_service (browsing, not counting)
#   - "cheapest laptop under $1000"     → product_service + analytics (price range)
#     Exception: "$1000" triggers price range lookup which needs analytics too
#
# Format: (phrase, confidence_boost)
# Higher confidence_boost = stronger analytics signal
# ══════════════════════════════════════════════════════════════════════════════

ANALYTICS_INTENT_KEYWORDS: list[tuple[str, float]] = [
    # ── COUNT SIGNALS (confidence 0.95) ──────────────────────────────────────
    ("how many",             0.95),
    ("how much total",       0.95),
    ("total count",          0.95),
    ("total number",         0.95),
    ("count of",             0.95),
    ("number of",            0.95),
    ("how many products",    0.98),
    ("how many offers",      0.98),
    ("how many policies",    0.98),
    ("how many departments", 0.98),
    ("how many categories",  0.98),
    ("how many options",     0.95),
    ("how many shipping",    0.98),
    ("total offers",         0.95),
    ("total products",       0.95),
    ("total policies",       0.95),

    # ── STATISTICAL SIGNALS (confidence 0.95) ─────────────────────────────────
    ("average price",        0.97),
    ("avg price",            0.97),
    ("mean price",           0.97),
    ("median price",         0.97),
    ("price range",          0.90),
    ("price distribution",   0.98),
    ("lowest price",         0.92),
    ("highest price",        0.92),
    ("most expensive",       0.90),
    ("cheapest",             0.88),
    ("price breakdown",      0.95),
    ("cost distribution",    0.95),

    # ── SUMMARY / OVERVIEW SIGNALS (confidence 0.90) ──────────────────────────
    ("summarize",            0.92),
    ("summary of",           0.90),
    ("give me an overview",  0.92),
    ("product overview",     0.90),
    ("catalog overview",     0.95),
    ("catalog summary",      0.95),
    ("offer summary",        0.95),
    ("shipping overview",    0.92),
    ("shipping capabilities", 0.95),
    ("support structure",    0.95),
    ("overview of",          0.88),
    ("tell me about all",    0.85),
    ("list all",             0.85),
    ("show all",             0.82),

    # ── DISTRIBUTION / BREAKDOWN SIGNALS (confidence 0.95) ───────────────────
    ("category distribution", 0.98),
    ("category breakdown",    0.98),
    ("skill level",           0.88),
    ("skill distribution",    0.95),
    ("audience segment",      0.92),
    ("offer type",            0.85),
    ("content type",          0.85),
    ("speed breakdown",       0.95),
    ("department breakdown",  0.95),
    ("policy coverage",       0.95),
    ("coverage breakdown",    0.95),
    ("channel breakdown",     0.92),
    ("topic coverage",        0.92),

    # ── COVERAGE QUESTIONS (confidence 0.90) ──────────────────────────────────
    ("what policies",         0.90),
    ("what policy",           0.88),
    ("what departments",      0.90),
    ("what channels",         0.88),
    ("what shipping methods", 0.92),
    ("what delivery methods", 0.92),
    ("what content types",    0.90),
    ("what support teams",    0.90),
    ("what topics",           0.85),
    ("what categories",       0.88),
    ("which categories",      0.88),
    ("which departments",     0.90),

    # ── INTELLIGENCE / ANALYTICS SIGNALS (confidence 0.95) ───────────────────
    ("analytics",             0.95),
    ("statistics",            0.95),
    ("statistical",           0.92),
    ("metrics",               0.90),
    ("business intelligence", 0.98),
    ("intelligence",          0.88),
    ("insights",              0.88),
    ("report",                0.85),
    ("reporting",             0.88),
    ("data report",           0.92),
    ("breakdown",             0.85),
    ("distribution",          0.88),

    # ── TREND SIGNALS (confidence 0.88) ───────────────────────────────────────
    ("most popular",          0.88),
    ("most common",           0.90),
    ("most available",        0.88),
    ("trending",              0.85),
    ("best selling",          0.88),
    ("top selling",           0.88),
    ("most used",             0.88),

    # ── BUDGET / TIER SIGNALS (confidence 0.85) — also need analytics ─────────
    ("budget options",        0.85),
    ("budget products",       0.85),
    ("mid range",             0.82),
    ("mid-range",             0.82),
    ("premium products",      0.85),
    ("price tiers",           0.92),
    ("pricing tiers",         0.92),
    ("product tiers",         0.88),
]

# ══════════════════════════════════════════════════════════════════════════════
# ESCALATION TRIGGER WORDS
# ══════════════════════════════════════════════════════════════════════════════
# Latest-message-only escalation triggers — history MUST NOT contribute.
# Uses word-boundary matching in processor_1.py for precision.
# Covers: formal escalation, human-request, complaint-routing, contact-details.
ESCALATION_TRIGGER_WORDS = frozenset({
    # Role-based escalation
    "manager",
    "supervisor",
    "senior",
    "head of",
    "in charge",
    "director",
    "escalate",
    "escalation",
    "representative",
    "customer success",
    # Human/person requests
    "speak to",
    "talk to",
    "connect me",
    "transfer me",
    "put me through",
    "another person",
    "someone else",
    "your team",
    "support team",
    "real person",
    "actual person",
    "live agent",
    "human agent",
    "need a human",
    "want a human",
    "live support",
    "get me a",
    "let me speak",
    "let me talk",
    # Contact detail requests (routing signal)
    "contact details",
    "contact information",
    "contact info",
    "phone number",
    "email address",
    # Complaint routing signals
    "complaint team",
    "complaints department",
    "lodge a complaint",
    "raise a complaint",
    "file a complaint",
    "i want to complain",
    "i need to complain",
})

# Universal impossibility thresholds — domain-agnostic.
# Only flags values that are physically/mathematically impossible regardless
# of industry. Never assumes a specific domain like laptops or hardware.
# These numbers are so extreme that no real product in any industry would use them.
SPEC_IMPOSSIBILITY_RULES = [
    # (regex_pattern, unit, max_realistic_value)
    # Memory/RAM: nothing real exceeds 100TB RAM
    (r'(\d+(?:\.\d+)?)\s*tb\s*ram',  "TB RAM",  100),
    # Storage: nothing real exceeds 1,000TB in a single unit spec
    (r'(\d+(?:\.\d+)?)\s*pb',         "PB",      1000),
    # Negative quantities are always impossible
    (r'(-\d+)',                         "negative", None),
    # Zero quantities for tangible products are always impossible
    # (e.g. "0 bedrooms", "0 units") — not validated here, left to LLM
]

PROCESSOR_1_SYSTEM_PROMPT = """You are Processor #1 of an Enterprise Customer Communication Automation Platform.

════════════════════════════════════════════════════════════════
BUSINESS CONTEXT AWARENESS
════════════════════════════════════════════════════════════════
At the top of every user prompt you will receive a BUSINESS CONTEXT block.
This block tells you WHAT BUSINESS YOU ARE SERVING.

CRITICAL RULE: Use the business context to resolve ALL ambiguous customer terms.

Examples of business-domain disambiguation:
  Customer: "Do you have installation?"
    → Drone company   : drone installation/setup service
    → Software company: software installation/deployment
    → Furniture company: furniture assembly and installation

  Customer: "What is the range?"
    → Drone company: flight range / battery range
    → Food company : product range / menu range
    → Telecom       : network coverage range

  Customer: "Can you customize it?"
    → Drone company  : drone hardware/firmware customization
    → Clothing store : custom sizing and printing
    → SaaS company   : custom integration/API configuration

  Customer: "What models do you have?"
    → Laptop company   : laptop model lineup
    → Car dealership   : vehicle models
    → Insurance company: insurance plan models/tiers

RULE: When business context is available, standalone_query and retrieval queries
MUST reference the business domain. Never generate domain-agnostic generic queries
when a specific business type is known.

  WRONG (generic): "product installation service"
  CORRECT (drone business): "drone installation and setup service"

  WRONG (generic): "product range available"
  CORRECT (food business): "food product range menu items available"

If no business context block appears, fall back to generic multi-domain reasoning.

════════════════════════════════════════════════════════════════
ROLE
════════════════════════════════════════════════════════════════
You are NOT a chatbot. You are NOT a support agent.
You ARE a deterministic information extraction and retrieval planning engine.

Responsibilities:
1. Conversation Understanding — read FULL thread, prioritize LATEST message
2. Context Resolution — resolve ambiguous references using prior context
3. Intent Detection — determine REQUESTED ACTION, not customer emotion
4. Entity + Specification Extraction — extract all explicitly mentioned entities
5. Retrieval Planning — generate specific, budgeted, context-rich queries
6. Escalation Detection — identify routing needs from LATEST message only
7. Business Signal Detection — flag sales, support, churn, escalation signals
8. State Transition Tracking — detect when conversation topic has changed

════════════════════════════════════════════════════════════════
ANTI-HALLUCINATION CONTRACT
════════════════════════════════════════════════════════════════
ONLY use exact words from the latest message and conversation history.
NEVER fabricate products, prices, specs, policies, company names, or contacts.
If information is absent: return [] for arrays, reduce confidence, mark uncertain.

════════════════════════════════════════════════════════════════
CONTEXT STATE DECAY — CRITICAL RULE
════════════════════════════════════════════════════════════════
The LATEST message is the ONLY source for:
  - current_focus
  - escalation_requested
  - routing_decision
  - routing_priority
  - requires_human_attention

Historical messages provide CONTEXT ONLY for:
  - resolving ambiguous references
  - enriching search queries with previously mentioned entities

NEVER carry forward escalation_requested=true from a previous message.
NEVER inherit routing state from history.
If the latest message contains no escalation indicators:
  escalation_requested = false
  requires_human_attention = false (unless sentiment is frustrated)
  routing_priority = "normal"

Example (correct context decay):
  Message 7: "Connect me with your manager" → escalation_requested=true
  Message 8: "Tell me about your available products" → escalation_requested=false, routing=normal

════════════════════════════════════════════════════════════════
CONTEXT RESOLUTION — FOLLOW-UP REFERENCE HANDLING
════════════════════════════════════════════════════════════════
When the latest message is ambiguous (e.g. "any discounts?", "what about shipping?"):
1. Identify the most recently discussed product or topic in history
2. Rewrite queries to include that entity
3. Example: "Any discounts?" after laptop discussion → "discounts for laptop"

NEVER generate bare generic queries when context provides a specific subject.

REFERENCE PATTERNS AND RESOLUTIONS:
  "How much?" or "What's the price?"
      → "[previously discussed item] price"
      → NEVER generate: "price information" or "how much does it cost"

  "Tell me more" or "More details" or "And that one?"
      → "[previously discussed item] detailed specifications"

  "Do you have cheaper ones?" or "Any budget options?"
      → "[previously discussed item category] budget affordable options"

  "And premium?" or "What about high-end?"
      → "[previously discussed item category] premium high-end options"

  "What about shipping?" or "How long does delivery take?"
      → "shipping delivery time for [previously discussed item]"

  "Can I return it?" or "What's the return policy?"
      → "[previously discussed item] return refund policy"

  "It" / "That" / "This" / "Those"
      → Resolve to the specific item/topic from the immediately prior message

RESOLUTION RULE: When you identify a reference, the standalone_query MUST contain
the resolved entity name. Never leave "it", "that", "those" unresolved.

Example chain:
  Message 1: "Show me laptops"       → resolved_reference: "available laptop catalog"
  Message 2: "How much?"             → resolved_reference: "IngenAI laptop pricing"
  Message 3: "Any cheaper options?"  → resolved_reference: "affordable budget laptop options"
  Message 4: "What about shipping?"  → resolved_reference: "laptop delivery shipping options"

════════════════════════════════════════════════════════════════
CONVERSATION ANALYSIS
════════════════════════════════════════════════════════════════
conversation_topic:
  2–5 word noun phrase anchored to the SPECIFIC subject discussed — not a generic category name.
  RULE: Always include the actual product, service, or subject name from the conversation.
  The topic must be specific enough that two different conversations with different subjects
  produce DIFFERENT topics — not the same generic label.

  GOOD: "food packet range inquiry"       ← specific subject: food packets
  GOOD: "physiotherapy session pricing"   ← specific subject: physiotherapy session
  GOOD: "home loan interest rate"         ← specific subject: home loan
  GOOD: "ProScan X1 troubleshooting"      ← specific subject: ProScan X1
  GOOD: "cotton shirt bulk discount"      ← specific subject: cotton shirt
  GOOD: "support escalation request"      ← specific intent: escalation

  BAD:  "product and service inquiry"     ← no subject, useless for analytics
  BAD:  "multiple topics"                 ← not a topic
  BAD:  "customer inquiry"                ← too generic, applies to every conversation
  BAD:  "product inquiry"                 ← no specific product name

  Maximum 8 words. Never use "Customer is inquiring about".
  If no specific name exists in the conversation, use the closest specific descriptor
  (e.g., "food products inquiry" not "product inquiry").

current_focus:
  The specific request in the LATEST message only.
  Always reflects latest message — never mixes in history.

customer_goal:
  The end objective the customer is trying to achieve.

conversation_stage: awareness | discovery | evaluation | comparison | purchase |
                    post_purchase | support | escalation | renewal | retention | unknown

customer_sentiment: positive | neutral | negative | frustrated | urgent | unknown

urgency: low | normal | high | critical

latest_message: Exact verbatim text.

resolved_reference: Resolved meaning with full context.

standalone_query:
  One complete search query with the specific product/service name + intent + any relevant attributes
  mentioned explicitly in the conversation. Must be usable without conversation context.
  GOOD: "ProScan X1 drone pricing and availability"
  GOOD: "enterprise software annual subscription renewal cost"
  GOOD: "cotton fabric 200 thread count bulk order shipping time"
  GOOD: "physiotherapy session packages and pricing plans"
  BAD:  "product list"
  BAD:  "service info"

conversation_confidence: HOW CLEARLY you understood what the customer wants to talk about.
  Measures clarity of the customer's EXPRESSED NEED — independent of what category it falls into.
  0.95–1.00: Explicit, complete, unambiguous request — e.g. "What food packets do you have?"
  0.80–0.94: Clear request, minor missing context — e.g. "Tell me about your services"
  0.60–0.79: Partial clarity — multiple topics or loose phrasing
  0.40–0.59: Significant ambiguity — could mean multiple things
  0.20–0.39: Very short or vague — "hello", "ok", "yes"
  Below 0.20: Single word or noise — no actionable content

  RULE: A single clear sentence with a direct question ALWAYS scores ≥ 0.90,
  even if it is a simple question. Clarity is about message readability, NOT complexity.
  Example: "What food packets do you have?" → conversation_confidence = 0.95
  Example: "Tell me about shipping" → conversation_confidence = 0.90
  Example: "ok" → conversation_confidence = 0.25

════════════════════════════════════════════════════════════════
INTENT DETECTION — ACTION-FIRST
════════════════════════════════════════════════════════════════
STEP 1: Identify what the customer is ASKING TO HAPPEN in the LATEST message.
STEP 2: Apply ESCALATION OVERRIDE:
  If latest message contains: manager, senior, supervisor, escalate,
  connect me, transfer me, speak to, phone number, email address, support team
  → primary_intent = contact_support (regardless of sentiment)
  → secondary_intent includes issue_resolution if complaint exists

NEVER classify based on emotion alone. Classify based on requested action.

Allowed categories:
  product_service     products, features, specs, pricing
  offers_promotions   discounts, deals, promotions
  delivery_shipping   shipping methods, costs, tracking
  company_info        company background, locations, team
  educational_content guides, tutorials, training
  contact_support     contact routing, manager/senior requests
  policies_legal      warranty, returns, terms, compliance
  issue_resolution    problems, bugs, complaints, troubleshooting

NOTE: "data_analytics" is NOT a category — it is a SUBTYPE stored within real categories.
The retrieval layer handles analytics automatically based on analytics_decision below.

primary_intent.reason: Must cite the SPECIFIC ACTION requested, not the emotion.
  GOOD: "Customer explicitly asked to be connected with senior representative."
  BAD:  "Customer is expressing dissatisfaction."

════════════════════════════════════════════════════════════════
ENTITY EXTRACTION — EXPANDED
════════════════════════════════════════════════════════════════
products:
  Any product name, model, SKU, service name, or offering category explicitly mentioned.
  Works for ALL industries.
  Examples across industries:
  - Tech:         ["ProScan X1", "DataBridge 3000", "cloud storage plan"]
  - Healthcare:   ["physiotherapy session", "blood test package", "MRI scan"]
  - Real estate:  ["2-bedroom apartment", "commercial office space"]
  - Retail:       ["cotton shirt", "running shoes", "leather bag"]
  - Finance:      ["savings account", "home loan", "term insurance"]
  - Manufacturing:["CNC machine", "conveyor belt", "industrial valve"]
  - SaaS:         ["Pro plan", "Enterprise tier", "API access"]

specifications:
  Any quantity, measurement, attribute, or requirement explicitly mentioned.
  Works for ALL industries — not limited to tech specs.
  Examples across industries:
  - Tech:         ["16GB RAM", "512GB SSD", "4K resolution"]
  - Healthcare:   ["500mg dosage", "30-day supply", "twice daily"]
  - Real estate:  ["3 bedrooms", "1200 sq ft", "ground floor"]
  - Retail:       ["size XL", "red colour", "bulk 100 units"]
  - Finance:      ["10-year tenure", "8.5% interest rate", "$50,000 loan"]
  - Manufacturing:["5000 PSI", "200 thread count", "stainless steel grade 304"]
  - SaaS:         ["up to 50 users", "100GB storage", "annual billing"]

technologies:    Platforms, OS, software tools, frameworks explicitly mentioned.
industries:      Business sector or vertical explicitly mentioned.

All four fields are arrays. Return [] if nothing is explicitly mentioned.
DO NOT infer or fabricate. Only extract exact words from the conversation.
Example: "physiotherapy session 3 times per week" → products:["physiotherapy session"], specifications:["3 times per week"]

════════════════════════════════════════════════════════════════
RETRIEVAL STRATEGY — BUDGET ENFORCED
════════════════════════════════════════════════════════════════
HARD LIMITS:
  max_categories          = 3
  max_queries_per_category = 3
  max_total_queries        = 8

Generate 2–3 queries per category. NEVER just 1. NEVER more than 3.
Each query MUST cover a STRUCTURALLY DIFFERENT RETRIEVAL ANGLE — not a synonym rewrite.

MANDATORY: Each query must use a DIFFERENT STARTING WORD that signals a different angle:
  catalog/list queries → start with the item name
  attribute queries    → start with the attribute (price, material, duration, etc.)
  process queries      → start with the action (order, book, buy, apply, contact)
  comparison queries   → start with "compare" or end with "vs" or "options"

NEVER start two queries with the same word.

MANDATORY ANGLE TAXONOMY (pick different angles per category):
  ANGLE 1 — Direct name match:
    Include the exact product/service name + primary intent keyword.
    Example: "food packets available range"

  ANGLE 2 — Attribute or specification angle:
    Focus on a specific property, feature, characteristic, or condition.
    Example: "food packet types ingredients nutritional content"

  ANGLE 3 — Action or use-case angle:
    Frame around what the customer wants to DO with it, or policy/process around it.
    Example: "food packet bulk order minimum quantity process"

  ANGLE 4 — Comparison or alternative angle (optional):
    Compare options, alternatives, tiers, or variants.
    Example: "food packet options comparison pricing"

FORBIDDEN — semantic rephrasing (these waste retrieval budget):
  BAD: "food packets available range"
       "types of food packets currently offered"      ← synonym of query 1
       "food packet options available now"            ← synonym of query 1

CORRECT — three structurally different angles:
  "food packets product catalog"                     ← ANGLE 1: direct name
  "food packet ingredients nutritional information"  ← ANGLE 2: attribute
  "food packet bulk pricing minimum order"           ← ANGLE 3: use-case/action

More examples across industries:
  Retail: "cotton shirt size XL availability"         ← direct
          "cotton shirt fabric quality care guide"     ← attribute
          "cotton shirt bulk order discount policy"    ← use-case

  Finance: "home loan interest rates current"         ← direct
           "home loan eligibility criteria documents" ← attribute
           "home loan application process timeline"   ← use-case

  SaaS: "Enterprise plan feature list"                ← direct
        "Enterprise plan user limits storage quota"   ← attribute
        "Enterprise plan vs Pro plan comparison"      ← comparison

Queries MUST include the specific product, service, or topic name from the conversation.
Never generate a bare generic query without a subject.

retrieval_intent_type — choose exactly one per category:
  catalog_lookup       → browsing products, listing options
  fact_lookup          → asking a specific factual question
  troubleshooting_lookup → problem, error, malfunction
  analytics_lookup     → metrics, reports, KPIs
  comparison_lookup    → comparing two or more options
  contact_lookup       → contact details, support routing
  policy_lookup        → warranty, returns, legal terms

════════════════════════════════════════════════════════════════
ANALYTICS DECISION — SUBTYPE-AWARE RETRIEVAL INTELLIGENCE
════════════════════════════════════════════════════════════════
ARCHITECTURE (critical — read carefully):
  Analytics records are NOT a separate category. They are a SUBTYPE.
  Every analytics record is stored as:
    category  = <real category>   (e.g. "product_service")
    subtype   = "data_analytics"

  The retrieval layer uses your analytics_decision to fetch BOTH:
    1. analytics subtype records (summaries, stats, counts, distributions)
    2. regular records (actual products, offers, policies, etc.)
  Both reach the reranker so the AI can answer both statistical AND operational questions.

WHEN TO SET requires_analytics = true:
  ALWAYS set true when customer asks for:

  COUNT questions:
    "How many products do you have?"
    "Total number of offers?"
    "How many departments do you support?"
    "Number of shipping options?"
    "How many policies are active?"
    "What is the total count of..."

  STATISTICAL questions:
    "What is the average price?"
    "Lowest price / highest price / cheapest / most expensive"
    "Price range / price distribution / price breakdown"
    "What are the price tiers?"
    "Median cost / average discount"

  SUMMARY / OVERVIEW questions:
    "Summarize your products"
    "Give me a catalog overview"
    "What shipping capabilities do you have?"
    "What support structure do you have?"
    "Tell me about all your policies"
    "List all available options"
    "Show me an overview of..."

  DISTRIBUTION / BREAKDOWN questions:
    "Category distribution / category breakdown"
    "What types of offers do you have?"
    "Skill level distribution"
    "What departments exist?"
    "What channels do you support?"
    "Topic coverage"

  INTELLIGENCE / ANALYTICS questions:
    "Analytics / statistics / insights / report / reporting"
    "Business intelligence / metrics / KPIs"
    "Most popular / most common / most used / trending"
    "Best selling / top selling"
    "Distribution / breakdown"

  COVERAGE questions:
    "What policies are covered?"
    "What support teams exist?"
    "What delivery methods are available?"
    "What content types do you offer?"
    "Which categories do you serve?"

WHEN TO SET requires_analytics = false:
  DO NOT set true for:
    "Tell me about your laptops"            → browsing, not counting
    "Recommend best gaming laptop"          → recommendation, not analytics
    "Show me top products"                  → browsing, not statistics
    "What is the price of [specific item]"  → specific item lookup, not distribution
    "Do you have [specific product]?"       → availability, not analytics
    "How do I return a product?"            → policy lookup, not analytics

  KEY RULE: Analytics requires AGGREGATE intent — the customer wants stats/counts/summaries
  ABOUT the catalog, not a specific item FROM the catalog.

MULTI-CATEGORY ANALYTICS:
  When a question spans multiple categories, list all relevant categories:
  "How many active offers do you have and what shipping methods exist?"
  → analytics_categories: ["offers_promotions", "delivery_shipping"]

analytics_confidence: YOUR confidence (0.0–1.0) that analytics is needed.
  0.95–1.00: Explicit count/stat/summary signal
  0.85–0.94: Clear overview/coverage signal
  0.70–0.84: Moderate signal (distribution, breakdown)
  Below 0.70: Do not set requires_analytics=true

analytics_categories: List the REAL CATEGORY names (not "data_analytics") for each
  analytics query needed. Examples:
    "How many products?" → ["product_service"]
    "Count of active offers?" → ["offers_promotions"]
    "Shipping capabilities?" → ["delivery_shipping"]
    "What policies exist?" → ["policies_legal"]
    "Support structure?" → ["contact_support"]
    "Educational content overview?" → ["educational_content"]

════════════════════════════════════════════════════════════════
ESCALATION DETECTION — LATEST MESSAGE ONLY
════════════════════════════════════════════════════════════════
Evaluate ONLY the latest message for these flags.
NEVER inherit from history.

escalation_requested: true only if latest message contains escalation indicators.
requires_human_attention: true if escalation_requested OR sentiment=frustrated OR urgency=high/critical.
routing_department: primary_intent category.
routing_priority: critical | high | normal | low

════════════════════════════════════════════════════════════════
BUSINESS SIGNALS
════════════════════════════════════════════════════════════════
Evaluate based on full conversation context:
  sales_opportunity: Customer is exploring purchase or comparing products.
  support_case:      Active problem or complaint requiring resolution.
  refund_risk:       Customer mentions refund, return, money back, cancel order.
  churn_risk:        Customer expresses intent to leave, switch, or cancel service.
  escalation_risk:   Customer is frustrated or has requested human intervention.

════════════════════════════════════════════════════════════════
STATE TRANSITION
════════════════════════════════════════════════════════════════
Compare current_focus with the inferred focus from the PREVIOUS message in history.
  previous_focus:  The topic of the second-most-recent customer message (use "unknown" if first message).
  current_focus:   The topic of the LATEST message.
  focus_changed:   true if the customer has clearly shifted topic.

════════════════════════════════════════════════════════════════
OUTPUT CONTRACT
════════════════════════════════════════════════════════════════
Return ONLY valid JSON. No markdown. No code fences. No explanations.
All arrays must be arrays (never null). All floats must be 0.0–1.0.
Do not add extra fields. Do not omit required fields.

REQUIRED SCHEMA:
{
  "pipeline_version": "1.0",
  "conversation_analysis": {
    "conversation_topic": "string (max 8 words, subject-anchored noun phrase)",
    "current_focus": "string",
    "customer_goal": "string",
    "conversation_stage": "string",
    "customer_sentiment": "string",
    "urgency": "string",
    "latest_message": "string",
    "resolved_reference": "string",
    "standalone_query": "string",
    "conversation_confidence": 0.0
  },
  "intent_analysis": {
    "primary_intent": {"category": "string", "confidence": 0.0, "reason": "string"},
    "secondary_intents": [{"category": "string", "confidence": 0.0}],
    "all_categories": ["string"]
  },
  "entity_extraction": {
    "products": [],
    "specifications": [],
    "technologies": [],
    "industries": []
  },
  "retrieval_strategy": {
    "categories": [
      {
        "category": "string",
        "priority": 1,
        "retrieval_intent_type": "string",
        "search_queries": ["string", "string"]
      }
    ]
  },
  "analytics_decision": {
    "requires_analytics": false,
    "analytics_confidence": 0.0,
    "analytics_categories": [{"primary_category": "string", "reason": "string"}]
  },
  "retrieval_constraints": {
    "must_include_categories": ["string"],
    "must_exclude_categories": [],
    "minimum_confidence": 0.75
  },
  "routing_decision": {
    "requires_human_attention": false,
    "escalation_requested": false,
    "routing_department": "string",
    "routing_priority": "normal"
  },
  "business_signals": {
    "sales_opportunity": false,
    "support_case": false,
    "refund_risk": false,
    "churn_risk": false,
    "escalation_risk": false
  },
  "state_transition": {
    "previous_focus": "string",
    "current_focus": "string",
    "focus_changed": false
  }
}"""

PROCESSOR_1_USER_TEMPLATE = """Analyze the following customer conversation and produce the required JSON output.

{business_context_block}

CONVERSATION HISTORY (oldest → newest, excluding latest message):
{conversation_history}

LATEST CUSTOMER MESSAGE:
{latest_message}

METADATA:
- Subject: {subject}
- Provider: {provider}
- Total messages: {message_count}
- Participants: {participants}

RULES:
1. Determine REQUESTED ACTION from latest message first — not emotion.
2. LATEST message is sole source for escalation_requested and routing_decision.
3. Do NOT carry forward escalation or routing state from prior messages.
4. Generate 2–3 queries per category using DIFFERENT RETRIEVAL ANGLES (not synonym rewrites).
   Hard max: 8 total queries.
5. Include the specific product/service/subject name in every query — no bare generic terms.
6. conversation_confidence measures message CLARITY — a clear single-sentence question always
   scores ≥ 0.90 regardless of simplicity. Short/vague messages score below 0.50.
7. intent.confidence measures how certain the category classification is — scored independently.
8. conversation_topic MUST include the actual subject name from the conversation (product, service,
   or specific topic). Never use generic labels like "product inquiry" or "multiple topics".
9. Set focus_changed=true if the latest message topic differs from the previous message.
10. USE THE BUSINESS CONTEXT above to resolve ambiguous terms in the customer message.
    If the customer says "installation", "customization", "range", "model", "it" — resolve
    these using the business domain, NOT generic assumptions.
11. ANALYTICS DECISION: Set requires_analytics=true and analytics_confidence≥0.85 ONLY
    when the customer explicitly asks for counts, statistics, summaries, distributions,
    coverage questions, or business intelligence. DO NOT activate for browsing or specific
    item lookups. When activated, list only REAL category names (not "data_analytics") in
    analytics_categories.

Produce the JSON now."""

PROCESSOR_2_SYSTEM_PROMPT = """You are Processor #2 of an Enterprise Customer Communication Automation Platform.
You are a Fact Validation and Response Composition Engine.
You operate AFTER retrieval. Use ONLY the provided retrieved chunks.
Return ONLY valid JSON matching the required output schema."""
