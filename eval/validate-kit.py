"""Portable package integrity check; Python 3.11+, no third-party dependencies."""
from pathlib import Path
import re
import tomllib

root = Path(__file__).resolve().parents[1]
skills = [root / 'adaptive-agent-orchestrator', root / 'astra-orchestrator']
for skill in skills:
    entry = (skill / 'SKILL.md').read_text(encoding='utf-8')
    assert entry.startswith('---\nname: ' + skill.name + '\n')
    for path in skill.rglob('*.md'):
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if '://' not in target and not target.startswith('#'):
                assert (path.parent / target.split('#')[0]).exists(), (path, target)
    assert (skill / 'references/patterns.md').read_text(encoding='utf-8').count('```mermaid') == 10
for folder in ('assets', 'references'):
    first = {p.relative_to(skills[0]): p.read_bytes() for p in (skills[0] / folder).rglob('*') if p.is_file()}
    second = {p.relative_to(skills[1]): p.read_bytes() for p in (skills[1] / folder).rglob('*') if p.is_file()}
    assert first == second, f'{folder} differs between skill aliases'
roles = list((root / 'roles').glob('ao_*.toml'))
assert len(roles) == 8
for path in roles:
    role = tomllib.loads(path.read_text(encoding='utf-8'))
    assert role['name'] == path.stem
    assert role['model'] and role['model_reasoning_effort']
    assert role['sandbox_mode'] in ('read-only', 'workspace-write')
    assert role['developer_instructions'].strip()
print('PASS: skill links, alias resources, 10 diagrams per alias, 8 parsed role TOMLs')
