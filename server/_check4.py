import ast, sys, os, json

files = [
    "server/services/automation-service/ai_engine/intent_engine/classifier.py",
    "server/services/automation-service/ai_engine/intent_engine/utils.py",
    "server/services/automation-service/ai_engine/prompt_compiler/templates.py",
    "server/services/automation-service/main.py",
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
    except Exception as e:
        print("ERR reading " + name + ": " + str(e))
        ok = False

print()
print("=== CONTENT CHECKS ===")

# Classifier checks
with open("server/services/automation-service/ai_engine/intent_engine/classifier.py", encoding="utf-8") as fh:
    clf = fh.read()
assert "asking about the business or products" in clf, "Missing business inquiry label"
assert "requesting information or details" in clf, "Missing info request label"
assert "falling back to QUESTION intent" in clf, "Confidence fallback missing"
print("OK  classifier.py: improved labels + fallback present")

# Utils checks
with open("server/services/automation-service/ai_engine/intent_engine/utils.py", encoding="utf-8") as fh:
    utils = fh.read()
assert "wanna know about your business" in utils, "Improved question anchor missing"
print("OK  utils.py: improved anchor sentences present")

# Templates check — exec just the templates module (no relative imports)
with open("server/services/automation-service/ai_engine/prompt_compiler/templates.py", encoding="utf-8") as fh:
    tmpl_src = fh.read()

# Patch out the relative import of _json (it's just json)
tmpl_src_patched = tmpl_src.replace("import json as _json", "import json as _json")
ns = {}
exec(compile(tmpl_src_patched, "templates.py", "exec"), ns)
sp = ns["build_system_prompt"]("TestCo", "question")
parsed = json.loads(sp)
rules = parsed["rules"]
assert "quality" in rules, "quality rules missing"
assert any("generic" in r.lower() or "filler" in r.lower() for r in rules["quality"]), "Anti-generic rule missing"
assert any("explicitly" in r.lower() for r in rules["memory"]), "Anti-hallucination memory rule missing"
print("OK  templates.py: quality + anti-hallucination rules present")

# Main.py checks
with open("server/services/automation-service/main.py", encoding="utf-8") as fh:
    main = fh.read()
assert "warmed up" in main, "Model warmup log missing"
assert "get_zero_shot_classifier" in main, "Zero-shot warmup missing"
assert "get_anchor_vectors" in main, "Anchor warmup missing"
print("OK  main.py: model warmup at startup present")

print()
print("ALL OK" if ok else "ERRORS FOUND")
sys.exit(0 if ok else 1)
