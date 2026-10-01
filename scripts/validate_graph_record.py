"""Validate graph snapshots, not the truth of trace/evidence or OS ownership.

Paths are exact workspace-relative files; globs/directories/links are not resolved.
Optional previous snapshot enables checking observed ownership deltas.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

NODE_STATES = {'pending', 'running', 'blocked', 'completed', 'cancelled'}
CRITERION_STATES = {'pending', 'pass', 'fail', 'unrun', 'blocked'}
ACTIVE = {'pending', 'running', 'blocked'}


def strings(value, *, nonempty=False):
    return isinstance(value, list) and (not nonempty or bool(value)) and all(
        isinstance(item, str) and bool(item.strip()) for item in value)


def normalize_path(value, case_sensitive=False):
    if not isinstance(value, str) or not value.strip() or value.endswith(('/', '\\')):
        raise ValueError('expected an exact relative file path')
    value = value.replace('\\', '/')
    if any(c in value for c in '*?[]:') or value.startswith('/'):
        raise ValueError('absolute paths, globs and drive paths are unsupported')
    path = PurePosixPath(value)
    if '..' in path.parts or str(path) == '.':
        raise ValueError('path traversal or workspace root is unsupported')
    reserved = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
    if any(part.endswith(('.', ' ')) or part.split('.')[0].casefold() in reserved for part in path.parts):
        raise ValueError('nonportable trailing dot/space or Windows device name')
    return str(path) if case_sensitive else str(path).casefold()


def validate_record(data, previous=None):
    """Return errors. Empty errors establish structure only; evidence is untrusted."""
    try:
        return _validate_record(data, previous)
    except (TypeError, KeyError, RecursionError) as exc:
        return [f'malformed graph field: {exc}']


def _validate_record(data, previous=None):
    errors = []
    if not isinstance(data, dict):
        return ['record must be an object']
    if type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        errors.append('schema_version must be 1')
    if not isinstance(data.get('task_id'), str) or not data['task_id'].strip():
        errors.append('task_id required')
    revision = data.get('revision')
    if type(revision) is not int or revision < 1:
        errors.append('revision must be a positive integer')
    sensitive = data.get('path_case_sensitive', False)
    if type(sensitive) is not bool:
        errors.append('path_case_sensitive must be boolean')
    nodes = data.get('nodes')
    criteria = data.get('criteria')
    edges = data.get('edges')
    if not isinstance(nodes, list) or not nodes:
        return errors + ['nodes must be a nonempty list']
    if not isinstance(criteria, list) or not criteria:
        return errors + ['criteria must be a nonempty list']
    if not isinstance(edges, list):
        return errors + ['edges must be a list']
    by_id, actors, writes = {}, {'root'}, {}
    for node in nodes:
        if not isinstance(node, dict):
            errors.append('node must be an object')
            continue
        node_id = node.get('id')
        if not isinstance(node_id, str) or not node_id.strip() or node_id in by_id:
            errors.append('node ID missing or duplicated')
            continue
        by_id[node_id] = node
        for key in ('role', 'expertise', 'output', 'agent_id'):
            if not isinstance(node.get(key), str) or not node[key].strip():
                errors.append(f'{node_id}: {key} required')
        if isinstance(node.get('agent_id'), str):
            actors.add(node['agent_id'])
        if node.get('status') not in NODE_STATES:
            errors.append(f'{node_id}: invalid status')
        if not strings(node.get('requirement_ids'), nonempty=True):
            errors.append(f'{node_id}: requirement_ids required')
        if not strings(node.get('evidence')):
            errors.append(f'{node_id}: evidence must be string list')
        elif node.get('status') in {'completed', 'cancelled'} and not node['evidence']:
            errors.append(f'{node_id}: terminal node needs evidence pointers')
        for scope in ('read_paths', 'write_paths'):
            paths = node.get(scope)
            if not strings(paths):
                errors.append(f'{node_id}: {scope} must be string list')
                continue
            normalized = set()
            for raw in paths:
                try:
                    path = normalize_path(raw, sensitive)
                except ValueError as exc:
                    errors.append(f'{node_id}: {exc}')
                    continue
                if path in normalized:
                    errors.append(f'{node_id}: duplicate normalized {scope}: {path}')
                normalized.add(path)
                if scope == 'write_paths' and node.get('status') in ACTIVE:
                    if path in writes:
                        errors.append(f'ownership collision: {path}: {writes[path]} / {node_id}')
                    writes[path] = node_id
    criterion_ids = set()
    for criterion in criteria:
        if not isinstance(criterion, dict):
            errors.append('criterion must be an object')
            continue
        cid = criterion.get('id')
        if not isinstance(cid, str) or not cid.strip() or cid in criterion_ids:
            errors.append('criterion ID missing or duplicated')
            continue
        criterion_ids.add(cid)
        implement_node = by_id.get(criterion.get('workstream_id'))
        if implement_node is None:
            errors.append(f'{cid}: workstream does not exist')
        elif criterion.get('implementation_owner') != implement_node.get('agent_id'):
            errors.append(f'{cid}: implementation owner must match workstream assignee')
        for key in ('implementation_owner', 'verification_owner'):
            if criterion.get(key) not in actors:
                errors.append(f'{cid}: {key} must be a recorded actor, not a test command')
        for key in ('outcome', 'verification_method', 'independence_reason'):
            if not isinstance(criterion.get(key), str) or not criterion[key].strip():
                errors.append(f'{cid}: {key} required')
        if type(criterion.get('independent')) is not bool:
            errors.append(f'{cid}: independent must be boolean')
        if criterion.get('independent') and criterion.get('implementation_owner') == criterion.get('verification_owner'):
            errors.append(f'{cid}: independent verification cannot use the same actor')
        if criterion.get('status') not in CRITERION_STATES:
            errors.append(f'{cid}: invalid criterion status')
        if not strings(criterion.get('evidence')):
            errors.append(f'{cid}: evidence must be string list')
        elif criterion.get('status') == 'pass' and not criterion['evidence']:
            errors.append(f'{cid}: pass needs evidence pointers')
    for node_id, node in by_id.items():
        if strings(node.get('requirement_ids')):
            for cid in node['requirement_ids']:
                if cid not in criterion_ids:
                    errors.append(f'{node_id}: unknown requirement {cid}')
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        node = by_id.get(criterion.get('workstream_id'))
        if node and strings(node.get('requirement_ids')) and criterion.get('id') not in node['requirement_ids']:
            errors.append('criterion must be linked from its implementation workstream')
    adjacency = {node_id: [] for node_id in by_id}
    for edge in edges:
        if not isinstance(edge, dict) or edge.get('kind') not in {'dependency', 'verification'}:
            errors.append('invalid edge kind')
            continue
        source, target = edge.get('from'), edge.get('to')
        if source not in by_id or target not in by_id or source == target:
            errors.append('edge needs distinct existing nodes')
        elif edge['kind'] == 'dependency':
            adjacency[source].append(target)
    visiting, visited = set(), set()

    def visit(node_id):
        if node_id in visiting:
            errors.append('dependency cycle')
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for child in adjacency[node_id]:
            visit(child)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in adjacency:
        visit(node_id)
    change = data.get('change')
    if revision == 1:
        if change is not None:
            errors.append('initial revision change must be null')
    elif not isinstance(change, dict):
        errors.append('revised graph requires change object')
    else:
        if change.get('from_revision') != revision - 1 or change.get('to_revision') != revision:
            errors.append('change revisions must be consecutive')
        for key in ('trigger', 'obsolete_work_disposition'):
            if not isinstance(change.get(key), str) or not change[key].strip():
                errors.append(f'change: {key} required')
        handoffs = change.get('handoffs')
        if not isinstance(handoffs, list):
            errors.append('handoffs must be a list')
            handoffs = []
        for item in handoffs:
            if not isinstance(item, dict):
                errors.append('handoff must be an object')
                continue
            if item.get('confirmation') not in {'stopped', 'completed', 'handoff_confirmed'}:
                errors.append('handoff requires confirmed disposition, not stop_requested')
            if not strings(item.get('evidence'), nonempty=True):
                errors.append('handoff requires confirmation evidence')
            for key in ('from_actor', 'to_actor'):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    errors.append(f'handoff {key} required')
            try:
                normalize_path(item.get('path'), sensitive)
            except ValueError as exc:
                errors.append(f'handoff: {exc}')
        if previous is not None:
            if validate_record(previous):
                errors.append('previous snapshot is invalid')
            elif previous.get('task_id') != data.get('task_id') or previous['revision'] != revision - 1:
                errors.append('previous snapshot task/revision mismatch')
            elif previous.get('path_case_sensitive', False) != sensitive:
                errors.append('path case convention cannot change between revisions')
            else:
                old_writes = {}
                for node in previous['nodes']:
                    if node['status'] in ACTIVE:
                        for raw in node['write_paths']:
                            old_writes[normalize_path(raw, sensitive)] = (node['agent_id'], node['id'])
                previous_nodes = {node['id']: node for node in previous['nodes']}
                for path, (old_actor, old_node_id) in old_writes.items():
                    current = [node for node in by_id.values() if any(
                        normalize_path_safe(raw, sensitive) == path for raw in node.get('write_paths', []))]
                    retained = any(node['agent_id'] == old_actor and node['status'] in ACTIVE for node in current)
                    def historical_terminal(node):
                        old = previous_nodes.get(node['id'])
                        return old and old['agent_id'] == node['agent_id'] and old['status'] in {'completed', 'cancelled'} \
                            and node['status'] in {'completed', 'cancelled'} and any(
                                normalize_path_safe(raw, sensitive) == path for raw in old['write_paths'])
                    new_actors = {node['agent_id'] for node in current
                                  if node['agent_id'] != old_actor and not historical_terminal(node)}
                    # Include already completed new writers: terminal state cannot hide a transfer.
                    if retained and new_actors:
                        errors.append(f'previous reservation still active during transfer: {path}')
                    targets = new_actors or ({'unassigned'} if not retained else set())
                    for new_actor in targets:
                        matches = [item for item in handoffs if isinstance(item, dict)
                                   and item.get('from_actor') == old_actor and item.get('to_actor') == new_actor
                                   and normalize_path_safe(item.get('path'), sensitive) == path]
                        terminal_release = new_actor == 'unassigned' and any(
                            node['id'] == old_node_id and node['agent_id'] == old_actor
                            and node['status'] in {'completed', 'cancelled'}
                            and strings(node.get('evidence'), nonempty=True) for node in current)
                        if not matches and not terminal_release:
                            errors.append(f'missing evidenced ownership handoff/release: {path}')
    if previous is not None and revision == 1:
        errors.append('initial snapshot cannot have previous snapshot')
    return errors


def normalize_path_safe(value, sensitive):
    try:
        return normalize_path(value, sensitive)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path)
    parser.add_argument('--previous', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.record.read_text(encoding='utf-8'))
        previous = json.loads(args.previous.read_text(encoding='utf-8')) if args.previous else None
        errors = validate_record(data, previous)
    except (OSError, ValueError, TypeError) as exc:
        errors = [str(exc)]
    if errors:
        print('\n'.join('FAIL: ' + error for error in errors))
        return 1
    print('PASS: graph structure; evidence truth, agent lifecycle and OS isolation not attested')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
