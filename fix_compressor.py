path = r'C:\Users\Rishiraj\OneDrive\Desktop\project_genesis\server\services\automation-service\app\llm\grounding\fact_graph_compressor.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the analytics section start (line 709 is 0-indexed 708)
# Find "CATALOG OVERVIEW" line and the matching sections.append after it
start_line = None
end_line = None
for i, line in enumerate(lines):
    if 'CATALOG OVERVIEW' in line:
        start_line = i - 1  # the "if fact_graph.get("analytics"):" line
        break

if start_line is None:
    print("ERROR: Could not find CATALOG OVERVIEW")
    exit(1)

# Find the closing sections.append for this block
for i in range(start_line, len(lines)):
    if 'sections.append' in lines[i] and i > start_line + 5:
        end_line = i + 1
        break

print(f"Found analytics block: lines {start_line+1} to {end_line}")
print("Current block:")
for i in range(start_line, end_line):
    print(f"{i+1}: {repr(lines[i])}")
