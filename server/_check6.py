import ast, sys, os, json, re

files = [
    "server/services/automation-service/ai_engine/context_builder/schema.py",
    "server/services/automation-service/ai_engine/context_builder/selector.py",
    "server/services/automation-service/ai_engine/prompt_compiler/templates.py",
    "server/services/automation-service/ai_engine/prompt_compiler/builder.py",
    "server/services/automation-service/ai_engine/validators/response_validator.py",
    "server/services/automation-service/ai_engine/orchestrator/pipeline.py",
]

ok = True
for f in files:
    name = os.path.basename(f)
    try:
        with open(f, encoding="utf-8") as fh:
            ast.parse(fh.read())
        print("OK  " + name)
    except SyntaxError as e:
        print("ERR " + name + ": " + str(e))
        ok = False

print()
print("=== ANTI-HALLUCINATION CHECKS ===")

# 1. SelectedContext has data flags
with open("server/services/automation-service/ai_engine/context_builder/schema.py", encoding="utf-8") as fh:
    schema_src = fh.read()
for flag in ["has_products", "has_services", "has_pricing", "has_use_cases"]:
    assert flag in schema_src, f"Missing flag: {flag}"
print("OK  SelectedContext has all 4 data flags")

# 2. Selector populates data flags
with open("server/services/automation-service/ai_engine/context_builder/selector.py", encoding="utf-8") as fh:
    sel_src = fh.read()
assert "has_products=" in sel_src, "Selector not setting has_products"
assert "has_pricing=" in sel_src, "Selector not setting has_pricing"
print("OK  Selector populates data flags from context text")

# 3. Templates: no hallucination triggers
with open("server/services/automation-service/ai_engine/prompt_compiler/templates.py", encoding="utf-8") as fh:
    tmpl_src = fh.read()
bad_phrases = [
    "Actively reference business context — mention specific services",
    "Mention 1-2 relevant services",
    "mention specific services or value",
]
for phrase in bad_phrases:
    assert phrase not in tmpl_src, f"Hallucination trigger still present: '{phrase}'"
print("OK  Hallucination trigger phrases removed from templates")

# 4. Templates: anti-hallucination rules present
assert "data_flags.has_products=false" in tmpl_src, "data_flags rule missing"
assert "data_flags.has_services=false" in tmpl_src, "data_flags rule missing"
assert "data_flags.has_pricing=false" in tmpl_src, "data_flags rule missing"
print("OK  data_flags rules present in system prompt")

# 5. Test build_user_prompt with data_flags
ns = {}
exec(compile(tmpl_src, "templates.py", "exec"), ns)
build_user = ns["build_user_prompt"]

# Test: no services in context → guidance should NOT say "mention services"
up_no_services = build_user(
    mode="standard",
    business_instruction="WanderCall is a travel company.",
    conversation_history="No history",
    subject="Test",
    incoming_message="What services do you offer?",
    intent="question",
    sub_intent="none",
    sentiment="neutral",
    tone="Professional",
    max_tokens="150",
    data_flags={"has_products": False, "has_services": False, "has_pricing": False, "has_use_cases": False},
)
parsed_no_svc = json.loads(up_no_services)
task_str = " ".join(parsed_no_svc["task"]).lower()
assert "mention" not in task_str or "do not" in task_str or "only" in task_str, \
    f"Task still instructs to mention services when has_services=False: {task_str}"
assert parsed_no_svc["context"]["data_flags"]["has_services"] == False
print("OK  No services in context → task does NOT instruct to mention services")

# Test: pricing in context → guidance says share it
up_with_pricing = build_user(
    mode="standard",
    business_instruction="WanderCall pricing: Basic 2999, Premium 7999.",
    conversation_history="No history",
    subject="Test",
    incoming_message="pricing batao",
    intent="question",
    sub_intent="pricing",
    sentiment="neutral",
    tone="Professional",
    max_tokens="150",
    data_flags={"has_products": False, "has_services": True, "has_pricing": True, "has_use_cases": False},
)
parsed_pricing = json.loads(up_with_pricing)
task_pricing = " ".join(parsed_pricing["task"]).lower()
assert "pricing" in task_pricing or "share" in task_pricing, "Pricing guidance missing when has_pricing=True"
print("OK  Pricing in context → task instructs to share it")

# 6. Builder passes data_flags
with open("server/services/automation-service/ai_engine/prompt_compiler/builder.py", encoding="utf-8") as fh:
    builder_src = fh.read()
assert "data_flags" in builder_src, "Builder not passing data_flags"
assert "context.has_products" in builder_src, "Builder not reading has_products from context"
print("OK  Builder passes data_flags to build_user_prompt")

# 7. Pipeline passes context_data_flags to validator
with open("server/services/automation-service/ai_engine/orchestrator/pipeline.py", encoding="utf-8") as fh:
    pipe_src = fh.read()
assert "context_data_flags" in pipe_src, "Pipeline not passing context_data_flags"
print("OK  Pipeline passes context_data_flags to response validator")

print()
print("ALL OK" if ok else "ERRORS FOUND")
sys.exit(0 if ok else 1)
