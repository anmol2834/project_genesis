path = r'C:\Users\Rishiraj\OneDrive\Desktop\project_genesis\server\services\automation-service\app\llm\prompt_builder\__init__.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Replace the "general" role prompt — remove "suggest questions" instruction,
# replace with "answer directly from catalog data"
old_general = (
    '    "general": """ROLE: Customer Service Assistant\n'
    'Focus: Provide helpful, accurate responses to general inquiries.\n'
    '- Answer clearly and concisely using only the provided context.\n'
    '- If the context contains analytics/catalogue data, use it to suggest relevant example questions the customer could ask (e.g. about specific products, pricing, features).\n'
    '- NEVER fabricate product names, prices, or features — only reference what appears in VERIFIED CONTEXT.\n'
    '- For greetings or short openers: respond warmly, briefly explain what you can help with, then list 3-5 concrete example questions drawn directly from the catalogue data in context.\n'
    '- Maintain a warm, professional tone at all times.""",'
)

new_general = (
    '    "general": """ROLE: Customer Service Assistant\n'
    'Focus: Directly answer the customer\'s question using the verified catalog data in context.\n'
    '- When the customer asks about products or services: list actual products/services from the VERIFIED CONTEXT immediately.\n'
    '- When catalog data (product names, prices, categories) is present in context: present it clearly and factually.\n'
    '- NEVER suggest follow-up questions as a substitute for answering what was asked.\n'
    '- NEVER fabricate product names, prices, or features — only reference what appears in VERIFIED CONTEXT.\n'
    '- Structure: (1) Direct answer from context, (2) Key details, (3) Optional: one relevant follow-up offer.\n'
    '- Maintain a warm, professional tone at all times.""",'
)

if old_general in content:
    content = content.replace(old_general, new_general)
    print('Fix 1 (general role): OK')
else:
    print('Fix 1 NOT FOUND - trying normalized')
    # Try without specific newlines
    if 'suggest relevant example questions the customer could ask' in content:
        import re
        content = re.sub(
            r'"general": """ROLE: Customer Service Assistant.*?- Maintain a warm, professional tone at all times\.""",',
            new_general,
            content,
            flags=re.DOTALL
        )
        print('Fix 1 (regex): OK')
    else:
        print('Fix 1 FAILED')

# Fix 2: Fix _count_fact_graph_sections to include CATALOG OVERVIEW
old_count = 'return sum(1 for h in ("PRODUCTS:", "PRICING:", "SUPPORT", "POLICIES:", "FEATURES:")\n               if h in context)'
new_count = 'return sum(1 for h in ("PRODUCTS:", "PRICING:", "SUPPORT", "POLICIES:", "FEATURES:", "CATALOG OVERVIEW:")\n               if h in context)'

if old_count in content:
    content = content.replace(old_count, new_count)
    print('Fix 2 (section counter): OK')
else:
    print('Fix 2 NOT FOUND')

# Fix 3: Route general_inquiry with catalog context to "sales" role instead of "general"
# Add catalog-aware routing: when context has product/catalog data, use sales role
old_select_end = (
    '        key = _INTENT_TO_ROLE.get(intent, "general")\n'
    '        return key, _ROLE_PROMPTS.get(key, _ROLE_PROMPTS["general"])'
)
new_select_end = (
    '        key = _INTENT_TO_ROLE.get(intent, "general")\n'
    '        return key, _ROLE_PROMPTS.get(key, _ROLE_PROMPTS["general"])\n'
)

# Actually Fix 3 is already handled by fixing the "general" role prompt above.
# The real fix is in the general role prompt itself.

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('DONE')
