"""Offline workflow advisory contract. No network, model dispatch or configuration edits."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

from validate_graph_record import normalize_path

POLICY = 'workflow-advisory-v1'
ACTIONS = {'root', 'reuse', 'spawn', 'revise', 'stop'}
ROLES = {'worker', 'explorer', 'researcher', 'architect', 'verifier'}


def fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError('object fields do not match the advisory schema')


def short(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ValueError('expected nonempty text of at most 1000 characters')
    return value


def items(value):
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError('expected a list of at most 32 entries')
    return value


def texts(value):
    result = [short(v) for v in items(value)]
    if len(set(result)) != len(result):
        raise ValueError('duplicate list entry')
    return result


def paths(value):
    result = [normalize_path(v) for v in texts(value)]
    if len(set(result)) != len(result):
        raise ValueError('duplicate normalized path')
    return result


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('expected bounded nonnegative integer')
    if value > 10**9:
        raise ValueError('integer exceeds bound')


def validate(state):
    fields(state, 'schema_version task_id revision summary trigger mode acceptance_gaps '
           'allowed_write_paths active_agents owners available_roles max_agents '
           'time_remaining_seconds stop_required candidates')
    if type(state['schema_version']) is not int or state['schema_version'] != 1:
        raise ValueError('schema_version must be 1')
    integer(state['revision'], 1)
    for key in ('task_id', 'summary', 'trigger'):
        short(state[key])
    if state['trigger'] not in {'initial', 'blocker', 'ownership_conflict', 'requirement_change',
                                'verification_failure', 'repeated_error', 'checkpoint'}:
        raise ValueError('unknown trigger')
    if state['mode'] not in {'review', 'implement'} or type(state['stop_required']) is not bool:
        raise ValueError('invalid mode or stop_required')
    texts(state['acceptance_gaps'])
    paths(state['allowed_write_paths'])
    agents = texts(state['active_agents'])
    if 'root' in agents:
        raise ValueError('active_agents excludes root')
    if not set(texts(state['available_roles'])) <= ROLES:
        raise ValueError('unknown available role')
    integer(state['max_agents'])
    integer(state['time_remaining_seconds'])
    owned = set()
    for owner in items(state['owners']):
        fields(owner, 'actor write_paths')
        if owner['actor'] not in ['root', *agents]:
            raise ValueError('owner must be root or an active agent')
        for path in paths(owner['write_paths']):
            if path in owned:
                raise ValueError('conflicting current ownership; reconcile before advice')
            owned.add(path)
    ids = set()
    for candidate in items(state['candidates']):
        fields(candidate, 'id action role actor output write_paths independent')
        cid = short(candidate['id'])
        if cid in ids:
            raise ValueError('duplicate candidate ID')
        ids.add(cid)
        if candidate['action'] not in ACTIONS or candidate['role'] not in ROLES:
            raise ValueError('unknown action or role')
        short(candidate['actor'])
        short(candidate['output'])
        paths(candidate['write_paths'])
        if type(candidate['independent']) is not bool:
            raise ValueError('independent must be boolean')
    if not ids:
        raise ValueError('at least one candidate is required')


def prepare(state):
    try:
        validate(state)
    except (TypeError, KeyError) as exc:
        raise ValueError('malformed advisory state') from exc
    allowed = set(paths(state['allowed_write_paths']))
    owners = {p: o['actor'] for o in state['owners'] for p in paths(o['write_paths'])}
    eligible, rejected = [], {}
    for c in state['candidates']:
        reasons = []
        action, actor = c['action'], c['actor']
        writes = set(paths(c['write_paths']))
        if not writes <= allowed:
            reasons.append('outside_write_scope')
        if writes and (state['mode'] == 'review' or c['role'] != 'worker'
                       or action in {'revise', 'stop'}):
            reasons.append('read_only')
        if any(p in owners and owners[p] != actor for p in writes):
            reasons.append('ownership_conflict')
        if action in {'root', 'revise', 'stop'} and actor != 'root':
            reasons.append('root_action_requires_root')
        if action == 'reuse' and actor not in state['active_agents']:
            reasons.append('agent_not_active')
        if action == 'spawn':
            if actor == 'root' or actor in state['active_agents']:
                reasons.append('spawn_requires_new_actor')
            if len(state['active_agents']) >= state['max_agents']:
                reasons.append('capacity')
            if c['role'] not in state['available_roles']:
                reasons.append('role_unavailable')
            if not c['independent']:
                reasons.append('no_independent_output')
        if len(state['active_agents']) > state['max_agents'] and action not in {'stop', 'revise'}:
            reasons.append('capacity_already_exceeded')
        if (state['stop_required'] or state['time_remaining_seconds'] == 0) and action != 'stop':
            reasons.append('hard_stop')
        if reasons:
            rejected[c['id']] = reasons
        else:
            eligible.append(c)
    fingerprint = hashlib.sha256(json.dumps(
        {'policy': POLICY, 'state': state}, sort_keys=True, allow_nan=False,
        separators=(',', ':')).encode()).hexdigest()
    return {
        'schema_version': 1, 'policy': POLICY, 'state_fingerprint': fingerprint,
        'mode': 'shadow', 'task_id': state['task_id'], 'revision': state['revision'],
        'eligible': eligible, 'rejected': rejected,
        'classification_required': len(eligible) > 1,
        'questions': ([{'id': 'next_workstream', 'type': 'Choice',
                       'choices': [c['id'] for c in eligible],
                       'criteria': 'Prefer complete acceptance coverage, then time, then cost. '
                                   'Prefer reuse over spawning when outputs are equivalent.'}]
                      if len(eligible) > 1 else []),
        'state': state,
        'network_calls_by_helper': 0,
    }


def recommendation(request, response):
    eligible = {c['id'] for c in request['eligible']}
    if response is None:
        return None, 'not_supplied'
    try:
        fields(response, 'schema_version policy state_fingerprint choice confidence probabilities')
        if (type(response['schema_version']) is not int or response['schema_version'] != 1
                or response['policy'] != POLICY
                or response['state_fingerprint'] != request['state_fingerprint']):
            raise ValueError('stale_or_incompatible')
        if not request['classification_required']:
            raise ValueError('classification_not_required')
        probs = response['probabilities']
        if not isinstance(probs, dict) or set(probs) != eligible:
            raise ValueError('candidate_set_mismatch')
        for value in [response['confidence'], *probs.values()]:
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('invalid_probability')
        if not math.isclose(sum(probs.values()), 1, abs_tol=1e-6):
            raise ValueError('probabilities_not_normalized')
        choice = response['choice']
        if not isinstance(choice, str) or choice not in eligible:
            raise ValueError('unknown_choice')
        if probs[choice] != max(probs.values()):
            raise ValueError('choice_not_maximal')
        return choice, 'valid_unverified_provenance'
    except (ValueError, TypeError):
        return None, 'invalid_response'


def record(state, response, decision):
    request = prepare(state)
    fields(decision, 'choice reason evidence')
    short(decision['reason'])
    texts(decision['evidence'])
    choices = {c['id'] for c in request['eligible']}
    if not isinstance(decision['choice'], str) or decision['choice'] not in choices:
        raise ValueError('root decision must select an eligible candidate')
    advised, status = recommendation(request, response)
    return {
        **request, 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'response_status': status, 'advised_choice': advised,
        'root_decision': decision,
        'disposition': ('fallback' if advised is None else
                        'accepted' if advised == decision['choice'] else 'overridden'),
        'response': response if advised is not None else None,
        'executed': False, 'model_invoked_by_helper': False,
        'outcome': None,
    }


def load(path):
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError('input exceeds 64 KiB')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'record'])
    parser.add_argument('--state', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--response')
    parser.add_argument('--root-decision')
    args = parser.parse_args()
    try:
        state = load(args.state)
        if args.command == 'prepare':
            if args.response or args.root_decision:
                raise ValueError('prepare does not accept response or root decision')
            result = prepare(state)
        else:
            if not args.root_decision:
                raise ValueError('record requires --root-decision')
            result = record(state, load(args.response) if args.response else None,
                            load(args.root_decision))
        # Exclusive creation: never overwrite evidence, input or repository configuration.
        with Path(args.output).open('x', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write('\n')
        print(f'{args.command}: shadow artifact saved to {args.output}; zero network/model calls')
        return 0
    except (ValueError, OSError, RecursionError):
        print('Advisory input/output rejected; validate schema and use a new output path.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
