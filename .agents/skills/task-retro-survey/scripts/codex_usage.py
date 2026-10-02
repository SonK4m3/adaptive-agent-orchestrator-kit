"""Read explicitly selected Codex rollouts; export counters, never prompts or source."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

KEYS = ('input_tokens', 'cached_input_tokens', 'output_tokens',
        'reasoning_output_tokens', 'total_tokens')


def identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,150}', value) else None


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.isoformat() if parsed.utcoffset() is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def counters(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {k: raw.get(k) if type(raw.get(k)) is int and raw[k] >= 0 else None for k in KEYS}


def sum_counters(values):
    return {k: sum(v[k] for v in values) if values and all(v[k] is not None for v in values)
            else None for k in KEYS}


def analyze(path):
    digest, meta, models, records, seen = hashlib.sha256(), None, [], [], set()
    cumulative, limits, gaps = [], [], []
    model = effort = None
    first = last = None
    with Path(path).open('rb') as stream:
        for number, line in enumerate(stream, 1):
            digest.update(line)
            ref = f'{Path(path).name}:{number}'
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(event.get('payload'), dict):
                    raise ValueError()
            except (ValueError, UnicodeError):
                gaps.append({'source_ref': ref, 'reason': 'malformed_envelope'})
                continue
            payload = event['payload']
            kind = event.get('type')
            ts = timestamp(event.get('timestamp'))
            if ts:
                if first is None or datetime.fromisoformat(ts) < datetime.fromisoformat(first):
                    first = ts
                if last is None or datetime.fromisoformat(ts) > datetime.fromisoformat(last):
                    last = ts
            if kind == 'session_meta':
                if meta is not None:
                    gaps.append({'source_ref': ref, 'reason': 'duplicate_metadata'})
                    continue
                source = payload.get('source')
                sub = source.get('subagent') if isinstance(source, dict) else None
                spawn = sub.get('thread_spawn') if isinstance(sub, dict) else None
                spawn = spawn if isinstance(spawn, dict) else {}
                meta = {'id': identifier(payload.get('id')),
                        'session_id': identifier(payload.get('session_id')),
                        'parent_thread_id': identifier(payload.get('parent_thread_id')) or
                                            identifier(spawn.get('parent_thread_id')),
                        'role': identifier(spawn.get('agent_role')),
                        'cli_version': identifier(payload.get('cli_version'))}
            elif kind == 'turn_context':
                model = identifier(payload.get('model'))
                effort = identifier(payload.get('effort') or payload.get('model_reasoning_effort'))
                entry = {'model': model, 'effort': effort}
                if entry not in models:
                    models.append(entry)
            elif kind == 'token_usage_record' or (kind == 'event_msg' and
                                                 payload.get('type') == 'token_usage_record'):
                usage = counters(payload.get('usage'))
                # Deduplicate only with stable IDs. Equal timestamp/counters alone cannot
                # distinguish replay from two real responses.
                event_id = identifier(payload.get('id') or event.get('id'))
                dedup = json.dumps([event_id or ts, model, effort, usage], sort_keys=True)
                if (event_id or ts) and dedup in seen:
                    if event_id:
                        continue
                    gaps.append({'source_ref': ref, 'reason': 'possible_replay_without_stable_id'})
                if event_id or ts:
                    seen.add(dedup)
                records.append({'source_ref': ref, 'measured_at': ts, 'model': model,
                                'effort': effort, 'counters': usage})
            elif kind == 'event_msg' and payload.get('type') == 'token_count':
                info = payload.get('info')
                info = info if isinstance(info, dict) else {}
                if isinstance(info.get('total_token_usage'), dict):
                    cumulative.append({'source_ref': ref, 'measured_at': ts,
                                       'counters': counters(info['total_token_usage'])})
                raw_limits = payload.get('rate_limits')
                if isinstance(raw_limits, dict):
                    windows = {}
                    for window in ('primary', 'secondary'):
                        raw = raw_limits.get(window)
                        if not isinstance(raw, dict):
                            continue
                        percent = raw.get('used_percent')
                        if type(percent) not in (int, float) or not 0 <= percent <= 100:
                            continue
                        windows[window] = {'used_percent': percent,
                            'resets_at': raw.get('resets_at') if type(raw.get('resets_at')) is int else None,
                            'window_minutes': raw.get('window_minutes') if type(raw.get('window_minutes')) is int else None}
                    if windows:
                        limits.append({'source_ref': ref, 'measured_at': ts,
                                       'scope': 'account', 'windows': windows})
    if meta is None or meta['id'] is None:
        raise ValueError('Missing supported session metadata')
    for previous, current in zip(cumulative, cumulative[1:]):
        if any(previous['counters'][k] is not None and current['counters'][k] is not None
               and current['counters'][k] < previous['counters'][k] for k in KEYS):
            gaps.append({'source_ref': current['source_ref'], 'reason': 'cumulative_counter_decreased'})
    total = sum_counters([r['counters'] for r in records]) if records else (
        cumulative[-1]['counters'] if cumulative else counters(None))
    if records and cumulative:
        if any(total[k] is not None and cumulative[-1]['counters'][k] is not None
               and total[k] != cumulative[-1]['counters'][k] for k in KEYS):
            gaps.append({'source_ref': cumulative[-1]['source_ref'],
                         'reason': 'response_sum_differs_from_cumulative; inherited_or_missing_records_possible'})
    if any(v is None for v in total.values()):
        gaps.append({'reason': 'missing_counter_fields'})
    by_model = []
    if records:
        bindings = []
        for r in records:
            binding = {'model': r['model'], 'effort': r['effort']}
            if binding not in bindings:
                bindings.append(binding)
        for binding in bindings:
            selected = [r['counters'] for r in records if r['model'] == binding['model'] and r['effort'] == binding['effort']]
            if selected:
                by_model.append({**binding, 'counters': sum_counters(selected)})
    # A cumulative fallback is not attributed to the final active model.
    uncached = (total['input_tokens'] - total['cached_input_tokens']
                if total['input_tokens'] is not None and total['cached_input_tokens'] is not None
                and total['input_tokens'] >= total['cached_input_tokens'] else None)
    return {**meta, 'source_file': Path(path).name, 'sha256': digest.hexdigest(),
            'observed_start': first, 'observed_end': last, 'model_bindings': models,
            'counter_basis': 'observed_response_sum' if records else
                             'last_cumulative_snapshot' if cumulative else 'missing',
            'counters': total, 'uncached_input_tokens': uncached, 'by_model': by_model,
            'responses': records, 'cumulative_snapshot': cumulative[-1] if cumulative else None,
            'account_snapshots': limits, 'gaps': gaps}


def collect(paths, root):
    root = identifier(root)
    if not root:
        raise ValueError('Exact root thread ID required')
    threads, hashes = {}, set()
    for path in paths:
        thread = analyze(path)
        if thread['sha256'] in hashes:
            continue
        hashes.add(thread['sha256'])
        if thread['id'] in threads:
            raise ValueError('Conflicting snapshots for a thread; select one rollout')
        threads[thread['id']] = thread
    if root not in threads:
        raise ValueError('Selected root rollout is required')
    members = {root}
    changed = True
    while changed:
        before = len(members)
        for tid, thread in threads.items():
            if thread['session_id'] == root or thread['parent_thread_id'] in members:
                members.add(tid)
        changed = len(members) != before
    if members != set(threads):
        raise ValueError('Unrelated rollout supplied; no cross-session collection')
    ordered = [threads[root], *[t for tid, t in threads.items() if tid != root]]
    for thread in ordered:
        thread['role'] = 'root' if thread['id'] == root else thread['role'] or 'unknown'
        thread['category'] = ('approval_review' if thread['role'] in {'guardian', 'guardian_review'}
                              else 'coding')
    return {'schema_version': 1, 'provider': 'codex', 'root': root,
            'collected_at': datetime.now(timezone.utc).isoformat(), 'threads': ordered,
            'usage_total': None, 'child_coverage': 'selected files only; completeness unknown',
            'aggregation_note': 'No cross-thread total: inherited counters or overlapping accounting unverified. '
                                'Cached input and reasoning are subsets, not additional tokens. '
                                'Session interval is not active time or necessarily one task.',
            'billing_cost_usd': None, 'subscription_delta': None}


def markdown(report):
    lines = ['# Codex observed usage', '', f"Root: {report['root']}", '',
             '| Thread | Role | Basis | Input | Cached | Output | Reasoning | Total |',
             '|---|---|---|---:|---:|---:|---:|---:|']
    for t in report['threads']:
        values = [str(t['counters'][k]) if t['counters'][k] is not None else 'unknown' for k in KEYS]
        lines.append('| ' + ' | '.join([t['id'], t['role'], t['counter_basis'], *values]) + ' |')
    lines += ['', report['aggregation_note'], '', 'JEV usage is imported separately. '
              'Account snapshots are not a task-cost delta. See JSON for coverage gaps and source pointers.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--rollout', action='append', required=True,
                        help='Exact selected root/child JSONL; repeat for each, no history scan')
    parser.add_argument('--format', choices=('json', 'md'), default='json')
    args = parser.parse_args()
    try:
        report = collect(args.rollout, args.root)
        print(json.dumps(report, indent=2, allow_nan=False) if args.format == 'json' else markdown(report))
        return 0
    except (ValueError, OSError, RecursionError):
        parser.exit(2, 'Usage collection rejected: check selected rollout metadata and root ID.\n')


if __name__ == '__main__':
    raise SystemExit(main())
