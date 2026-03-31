import ast, sys, os

files = [
    "server/services/automation-service/ai_engine/schemas/ai_output.py",
    "server/services/automation-service/ai_engine/decision_engine/finalizer.py",
    "server/services/automation-service/ai_engine/decision_engine/validator.py",
    "server/services/automation-service/ai_engine/validators/response_validator.py",
    "server/services/automation-service/ai_engine/policy_engine/rules.py",
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

# Verify HUMAN_REVIEW status exists in ai_output
with open("server/services/automation-service/ai_engine/schemas/ai_output.py", encoding="utf-8") as fh:
    src = fh.read()
assert "HUMAN_REVIEW" in src, "HUMAN_REVIEW status missing from ai_output.py"
print("OK  HUMAN_REVIEW status present in ai_output.py")

# Verify reply rescue logic in finalizer
with open("server/services/automation-service/ai_engine/decision_engine/finalizer.py", encoding="utf-8") as fh:
    src = fh.read()
assert "Reply rescued from llm_out" in src, "Reply rescue logic missing"
assert "reply_generated" in src, "reply_generated log missing"
assert "reply_preserved" in src, "reply_preserved log missing"
assert "payload_created" in src, "payload_created log missing"
print("OK  Reply rescue + logging present in finalizer.py")

# Verify response validator fix
with open("server/services/automation-service/ai_engine/validators/response_validator.py", encoding="utf-8") as fh:
    src = fh.read()
assert "from_email.lower()" in src, "Account email whitelist missing"
print("OK  Account email whitelist present in response_validator.py")

# Verify policy rule changes
with open("server/services/automation-service/ai_engine/policy_engine/rules.py", encoding="utf-8") as fh:
    src = fh.read()
assert "confidence_below=0.30" in src, "RULE_050 threshold not lowered"
assert "SAFE_MODE" in src and "confidence_below=0.60" in src, "RULE_051 not changed to SAFE_MODE"
print("OK  Policy rules updated correctly")

print()
print("ALL OK" if ok else "ERRORS FOUND")
sys.exit(0 if ok else 1)
