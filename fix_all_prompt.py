path = r'C:\Users\Rishiraj\OneDrive\Desktop\project_genesis\server\services\automation-service\app\llm\prompt_builder\__init__.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

results = []

# Fix 1: discovery stage modifier - present products directly, not vague "lead with value"
old1 = '    "discovery":     "The customer is exploring options. Lead with value and clarity.",'
new1 = '    "discovery":     "The customer is exploring options. Present the actual available products and services from context directly. Do not suggest questions — answer with catalog facts first.",'
if old1 in content:
    content = content.replace(old1, new1)
    results.append('Fix discovery modifier: OK')
else:
    results.append('Fix discovery modifier: NOT FOUND')

# Fix 2: awareness stage modifier (same issue - generic nurturing)
old2 = '    "awareness":     '
# awareness is not in _JOURNEY_MODIFIERS in original but add it as a safeguard
# Actually ConversationStage.AWARENESS maps to "awareness" string
# It falls through to empty string in _JOURNEY_MODIFIERS.get() - no modifier applied
# This is fine, the issue is the "general" role + "discovery" modifier combo

# Fix 3: The _build_grounded_prompt_async in llm/orchestrator.py
# Currently only calls format_for_llm when products/pricing/support/features/policies exist
# but analytics data (which has pricing) is excluded from this check
# Fix: also include analytics in the condition
import re
path2 = r'C:\Users\Rishiraj\OneDrive\Desktop\project_genesis\server\services\automation-service\app\llm\orchestrator.py'
with open(path2, 'r', encoding='utf-8') as f:
    content2 = f.read()

old3 = (
    '        if fact_graph and (\n'
    '            fact_graph.get("products") or fact_graph.get("pricing")\n'
    '            or fact_graph.get("support") or fact_graph.get("features")\n'
    '            or fact_graph.get("policies")\n'
    '        ):'
)
new3 = (
    '        if fact_graph and (\n'
    '            fact_graph.get("products") or fact_graph.get("pricing")\n'
    '            or fact_graph.get("support") or fact_graph.get("features")\n'
    '            or fact_graph.get("policies") or fact_graph.get("analytics")\n'
    '        ):'
)
if old3 in content2:
    content2 = content2.replace(old3, new3)
    results.append('Fix orchestrator analytics condition: OK')
else:
    results.append('Fix orchestrator analytics condition: NOT FOUND')

# Fix 4: _count_fact_graph_sections should count CATALOG OVERVIEW too
# Already done in fix_prompt2.py but verify
if 'CATALOG OVERVIEW:' in content:
    results.append('Fix section counter (CATALOG OVERVIEW): already present')
else:
    results.append('Fix section counter (CATALOG OVERVIEW): MISSING - apply')
    old4 = 'return sum(1 for h in ("PRODUCTS:", "PRICING:", "SUPPORT", "POLICIES:", "FEATURES:")'
    new4 = 'return sum(1 for h in ("PRODUCTS:", "PRICING:", "SUPPORT", "POLICIES:", "FEATURES:", "CATALOG OVERVIEW:")'
    if old4 in content:
        content = content.replace(old4, new4)
        results.append('  -> applied')

# Fix 5: general_inquiry should route to "sales" role when context has catalog data,
# not "general" role. But we already fixed the "general" role prompt to answer directly.
# Additionally fix: remove "general_inquiry" -> "general" mapping and use "catalog_overview" role
# Actually the cleanest fix is to add a new "catalog" role and route general_inquiry there

# Check if our general role fix was already applied
if 'list 3-5 concrete example questions' in content:
    results.append('WARNING: old general role still present!')
elif 'directly from catalog data' in content or 'directly answer' in content.lower() or 'Directly answer' in content:
    results.append('general role fix: already applied')
else:
    results.append('general role fix: unknown state')

# Fix 6: Add OUTPUT_PROMPT instruction for product/service queries
# The output prompt currently says "2-4 short paragraphs" which is too vague
# For product queries, we need structured output
old6 = '''_OUTPUT_PROMPT = """
FORMAT RULES:
- Be concise: 2-4 short paragraphs maximum unless detailed explanation is required.
- Do NOT use markdown headers, bullet lists with asterisks, or HTML tags.
- Write in plain, conversational prose.
- End with a clear next step or call to action when appropriate."""'''

new6 = '''_OUTPUT_PROMPT = """
FORMAT RULES:
- Be concise but complete: answer the question fully using verified context.
- When listing products or services: name them explicitly (e.g. "IngenAI Air 13, IngenAI Gaming 15").
- When pricing is available in context: state it clearly (e.g. "priced at 1299").
- Do NOT use markdown headers, bullet lists with asterisks, or HTML tags.
- Write in plain, conversational prose with concrete facts from the context.
- NEVER substitute catalog facts with generic topic suggestions or questions.
- End with a clear next step or call to action when appropriate."""'''

if '_OUTPUT_PROMPT' in content and '2-4 short paragraphs' in content:
    content = content.replace(old6, new6)
    results.append('Fix output prompt: OK')
else:
    # try without exact match
    old6b = '- Be concise: 2-4 short paragraphs maximum unless detailed explanation is required.\n- Do NOT use markdown headers, bullet lists with asterisks, or HTML tags.\n- Write in plain, conversational prose.\n- End with a clear next step or call to action when appropriate.'
    new6b = '- Be concise but complete: answer the question fully using verified context.\n- When listing products or services: name them explicitly (e.g. the actual product names from context).\n- When pricing is available in context: state it clearly.\n- Do NOT use markdown headers, bullet lists with asterisks, or HTML tags.\n- Write in plain, conversational prose with concrete facts from context.\n- NEVER substitute catalog facts with generic topic suggestions or follow-up questions.\n- End with a clear next step or call to action when appropriate.'
    if old6b in content:
        content = content.replace(old6b, new6b)
        results.append('Fix output prompt (alt): OK')
    else:
        results.append('Fix output prompt: NOT FOUND')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

with open(path2, 'w', encoding='utf-8') as f:
    f.write(content2)

for r in results:
    print(r)
print('DONE')
