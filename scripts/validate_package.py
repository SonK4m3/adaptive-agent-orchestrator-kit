"""Portable package integrity check; Python 3.11+, no third-party dependencies."""
from pathlib import Path
import re
import tomllib
from package_layout import distribution_files


def validate_navigation(skill):
    """Check portable skill links and specific package-level navigation contracts."""
    roles = (skill / 'references/roles.md').read_text(encoding='utf-8')
    evaluation = (skill / 'references/evaluation.md').read_text(encoding='utf-8')
    assert 'install-roles.ps1' not in roles, 'obsolete role installer'
    assert 'python scripts/manage.py install --parts roles' in roles
    assert 'source checkout or extracted kit package' in roles
    assert 'eval/scenarios/catalog.md' in evaluation
    assert 'scenario catalog in the kit root' not in evaluation
    for path in skill.rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):
                continue
            dest = (path.parent / target.split('#')[0]).resolve()
            assert dest.is_relative_to(skill.resolve()), 'installed skill link escapes its bundle'
            assert dest.exists(), (path, target)

root = Path(__file__).resolve().parents[1]
assert (root / 'scripts/manage.py').is_file()
assert (root / 'eval/scenarios/catalog.md').is_file()
skills = [root / 'skills' / 'adaptive-agent-orchestrator', root / 'skills' / 'astra-orchestrator']
for skill in skills:
    validate_navigation(skill)
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
assert skills[0].joinpath('SKILL.md').read_text(encoding='utf-8').split('---', 2)[2] == skills[1].joinpath('SKILL.md').read_text(encoding='utf-8').split('---', 2)[2], 'Skill policy bodies differ'
for name, capacity in [('adaptive', 4), ('adaptive-max-2-subagents', 2)]:
    data = tomllib.loads((root / 'profiles' / name / 'profile.toml').read_text(encoding='utf-8'))
    assert data['schema'] == 1 and data['name'] == name
    assert (root / data['roles']).is_dir()
    config = tomllib.loads((root / data['config']).read_text(encoding='utf-8'))
    assert config['agents']['max_concurrent_threads_per_session'] == capacity
    assert set(config) == {'agents'}, 'Resource presets must not change root model or permissions'
for path in distribution_files(root):
    if path.suffix != '.md':
        continue
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if '://' not in target and not target.startswith('#'):
            assert (path.parent / target.split('#')[0]).exists(), (path, target)
roles = list((root / 'profiles/adaptive/codex/agents').glob('ao_*.toml'))
assert len(roles) == 8
for path in roles:
    role = tomllib.loads(path.read_text(encoding='utf-8'))
    assert role['name'] == path.stem
    assert role['model'] and role['model_reasoning_effort']
    assert role['sandbox_mode'] in ('read-only', 'workspace-write')
    assert role['developer_instructions'].strip()
print('PASS: skill links, alias resources, 10 diagrams per alias, 8 parsed role TOMLs')
