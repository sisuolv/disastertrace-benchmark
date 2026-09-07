"""Validate the Markdown handoff structure and preserve upstream starter bytes."""
from pathlib import Path
import ast
import json
import re
import yaml

root = Path(__file__).resolve().parents[1]
text = (root / 'DISASTERTRACE_CODEX_PLAN.md').read_text(encoding='utf-8')
lines = text.splitlines()
opened = None
blocks = []
body = []
for n, line in enumerate(lines, 1):
    if line.startswith('```'):
        if opened is None:
            opened = (n, line[3:].strip())
            body = []
        else:
            blocks.append((opened[0], opened[1], '\n'.join(body)))
            opened = None
    elif opened is not None:
        body.append(line)
assert opened is None, f'Unclosed fence at {opened}'
for line_no, lang, code in blocks:
    if lang == 'yaml':
        yaml.safe_load(code)
    if lang == 'python':
        ast.parse(code)
anchors = set(re.findall(r'<a id="([^"]+)"', text))
links = set(re.findall(r'\]\(#([^)]*)\)', text))
assert links <= anchors, f'Missing anchors: {links-anchors}'
tasks = re.findall(r'^### (DT-\d+)[：:]', text, flags=re.M)
assert len(tasks) == 21 and len(set(tasks)) == 21
assert set(tasks) == {f'DT-{i:02d}' for i in range(21)}
tests = re.findall(r'^\| (T\d{2}) \|', text, flags=re.M)
assert len(tests) == 48 and len(set(tests)) == 48
assert not re.search(r'^\s*- \[x\]', text, re.M), 'Unexecuted tasks falsely checked DONE'
assert not any(token in text for token in ['turn543053','turn181280','turn933578'])
result = {'status':'passed','tasks':len(tasks),'behavior_test_groups':len(tests),
          'lines':len(lines),'code_blocks':len(blocks),'anchors':len(anchors)}
print(json.dumps(result, ensure_ascii=False, indent=2))
