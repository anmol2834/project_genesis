"""Quick smoke-test for the enterprise keyword engine."""
import sys, os, re, types, importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm'))
sys.path.insert(0, os.path.dirname(__file__))

# Load prompts module
spec = importlib.util.spec_from_file_location('prompts', 'llm/prompts.py')
prompts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompts)
sys.modules['llm.prompts'] = prompts

# Patch heavy deps before loading processor_1
for mod in ('openai', 'shared', 'shared.config'):
    sys.modules.setdefault(mod, types.ModuleType(mod))
sys.modules['shared.config'].get_config = lambda: None

# Extract just the utility functions via exec
with open('llm/processor_1.py', 'r', encoding='utf-8') as f:
    src = f.read()

ns = {k: getattr(prompts, k) for k in dir(prompts) if not k.startswith('__')}
ns['re'] = re
# find start of _check_escalation_triggers
start = src.find('\ndef _check_escalation_triggers')
exec(src[start:], ns)

_check = ns['_check_escalation_triggers']
_infer = ns['_infer_category']

# ── Escalation trigger tests ─────────────────────────────────────────────────
print("=== ESCALATION TRIGGER TESTS ===")
cases_esc = [
    ("speak to your manager", True),
    ("get me a senior representative", True),
    ("i want to complain about my order", True),
    ("connect me with your support team", True),
    ("what is your email address", True),
    ("tell me about your products", False),
    ("management is important", False),   # 'management' != 'manager'
    ("the escalating prices are too high", False),  # 'escalating' != 'escalate'
    ("need a live agent please", True),
    ("real person please", True),
    ("i need to lodge a complaint", True),
]
for text, expected in cases_esc:
    result = _check(text.lower())
    status = "PASS" if result == expected else "FAIL"
    mark = "ESC" if expected else "OK "
    print(f"  {status}  [{mark}] \"{text}\" -> {result}")

# ── Category inference tests ─────────────────────────────────────────────────
print("\n=== CATEGORY INFERENCE TESTS ===")
cases_cat = [
    # issue_resolution
    ("it isn't working", "issue_resolution"),
    ("something went wrong", "issue_resolution"),
    ("i can't login", "issue_resolution"),
    ("my order never arrived", "issue_resolution"),
    ("the app keeps crashing", "issue_resolution"),
    ("payment failed", "issue_resolution"),
    ("having trouble with my account", "issue_resolution"),
    ("facing a problem with checkout", "issue_resolution"),
    # contact_support (escalation override)
    ("speak to your manager", "contact_support"),
    ("need a live agent", "contact_support"),
    ("what is your phone number", "contact_support"),
    ("customer care contact", "contact_support"),
    # delivery_shipping
    ("what are the shipping charges", "delivery_shipping"),
    ("what is the shipping fee", "delivery_shipping"),
    ("where is my order", "delivery_shipping"),
    ("how long does delivery take", "delivery_shipping"),
    ("track my order", "delivery_shipping"),
    ("estimated delivery time", "delivery_shipping"),
    # offers_promotions
    ("any discounts available", "offers_promotions"),
    ("do you have any offers", "offers_promotions"),
    ("enterprise plan pricing", "offers_promotions"),
    ("free trial available", "offers_promotions"),
    ("promo code for new users", "offers_promotions"),
    ("subscription plan cost", "offers_promotions"),
    # policies_legal
    ("return policy details", "policies_legal"),
    ("want my money back", "policies_legal"),
    ("cancel my subscription", "policies_legal"),
    ("terms and conditions", "policies_legal"),
    ("warranty claim process", "policies_legal"),
    ("gdpr compliance", "policies_legal"),
    # educational_content
    ("how to set up the product", "educational_content"),
    ("getting started guide", "educational_content"),
    ("step by step tutorial", "educational_content"),
    ("video tutorial link", "educational_content"),
    ("user manual download", "educational_content"),
    # company_info
    ("about your company", "company_info"),
    ("who are you", "company_info"),
    ("company history background", "company_info"),
    ("where is your headquarters", "company_info"),
    # data_analytics
    ("how many orders this month", "data_analytics"),
    ("best selling products", "data_analytics"),
    ("show me the revenue report", "data_analytics"),
    ("conversion rate this quarter", "data_analytics"),
    # product_service (default)
    ("do you have laptops", "product_service"),
    ("what products do you have", "product_service"),
    ("tell me about your services", "product_service"),
    ("available models", "product_service"),
    ("product specifications", "product_service"),
]
passed = failed = 0
for text, expected in cases_cat:
    result = _infer(text)
    status = "PASS" if result == expected else "FAIL"
    if result == expected:
        passed += 1
    else:
        failed += 1
    print(f"  {status}  [{expected[:20]:<20}] \"{text}\"" + (f" -> GOT: {result}" if status == "FAIL" else ""))

print(f"\nResults: {passed}/{len(cases_cat)} passed, {failed} failed")
