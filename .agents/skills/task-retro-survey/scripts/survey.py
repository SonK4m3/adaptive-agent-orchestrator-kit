"""Portable local survey recorder. Python 3.11+, standard library only."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import sys
import uuid
import codex_usage

SKILL_ROOT = Path(__file__).resolve().parents[1]
KINDS = ('phase', 'agent_start', 'agent_end', 'blocker', 'retry', 'scope_change',
         'model_change', 'verification', 'usage', 'tool_skill', 'pause', 'resume',
         'observation_gap', 'intake_update', 'completed', 'amendment')
STATUSES = ('completed', 'partial', 'blocked', 'cancelled')
DETAIL_FIELDS = ('participant_alias', 'repository_id', 'client', 'plan', 'task_type',
                 'objective', 'acceptance_criteria', 'scope', 'specification_state',
                 'expected_elapsed_minutes', 'deadline', 'usage_limit', 'models', 'evidence_sources',
                 'comparison_contract')


def offset(value):
    match = re.fullmatch(r'([+-])(\d{2}):(\d{2})', value)
    if not match:
        raise ValueError('UTC offset must be +HH:MM or -HH:MM')
    hours, minutes = int(match[2]), int(match[3])
    if hours > 14 or minutes > 59 or (hours == 14 and minutes):
        raise ValueError('Invalid UTC offset')
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(delta if match[1] == '+' else -delta)


def now(task):
    return datetime.now(offset(task['utc_offset'])).isoformat(timespec='seconds')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(temp, path)


def input_object(path):
    value = {} if path is None else json.loads(sys.stdin.read()) if path == '-' else read(Path(path))
    if not isinstance(value, dict):
        raise ValueError('Input must be a JSON object')
    return value


def linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def resolve_run(path):
    runs = SKILL_ROOT / 'runs'
    if linked(runs):
        raise ValueError('runs/ must not be a symlink')
    original = Path(path)
    if linked(original):
        raise ValueError('Run must not be a symlink')
    run = original.resolve()
    if run.parent != runs.resolve() or not (run / 'task.json').is_file():
        raise ValueError('Run must be directly inside this installed skill\'s runs/')
    for name in ('task.json', 'task.md', 'events.jsonl', 'summary.json', 'summary.md'):
        if linked(run / name):
            raise ValueError('Record files must not be symlinks')
    return run


@contextmanager
def lock(run):
    path = run / '.writer.lock'
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        yield
    finally:
        path.unlink()


def append(run, task, kind, payload):
    recorded = now(task)
    basis = payload.get('observation_basis', 'unknown')
    if basis not in ('live', 'reported', 'imported', 'unknown'):
        raise ValueError('Invalid observation_basis')
    observed = payload.get('observed_at')
    if observed is None and basis == 'live':
        observed = recorded
    if observed is not None:
        parsed = datetime.fromisoformat(observed)
        if parsed.utcoffset() is None:
            raise ValueError('observed_at needs an ISO timestamp with UTC offset')
    events = run / 'events.jsonl'
    lines = events.read_text(encoding='utf-8').splitlines() if events.exists() else []
    sequence = json.loads(lines[-1])['sequence'] + 1 if lines else 1
    event = {'schema_version': 1, 'run_id': task['run_id'], 'sequence': sequence,
             'recorded_at': recorded, 'observed_at': observed, 'observation_basis': basis, 'kind': kind,
             'phase': payload.get('phase'), 'status': payload.get('status'),
             'actor': payload.get('actor'), 'note': payload.get('note'),
             'evidence': payload.get('evidence'), 'data': payload.get('data')}
    with events.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + '\n')


def task_markdown(run, task):
    (run / 'task.md').write_text(
        f"# {task['name']}\n\nRun: {task['run_id']}\n\nStarted: {task['started_at']} ({task['timezone']})\n\n"
        + 'Canonical intake: task.json; unknown values are null.\n\n```json\n'
        + json.dumps(task['details'], ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')


def start(args):
    tz = offset(args.utc_offset)
    runs = SKILL_ROOT / 'runs'
    if linked(runs):
        raise ValueError('runs/ must not be a symlink')
    runs.mkdir(exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', args.task.lower()).strip('-')[:48] or 'task'
    stamp = datetime.now(tz)
    run_id = stamp.strftime('%Y-%m-%d_%H%M%S%z') + '_' + slug + '_' + uuid.uuid4().hex[:8]
    run = runs / run_id
    run.mkdir()
    task = {'schema_version': 1, 'run_id': run_id, 'name': args.task,
            'started_at': stamp.isoformat(timespec='seconds'), 'timezone': args.timezone,
            'utc_offset': args.utc_offset, 'status': 'in_progress', 'recording_mode': 'helper',
            'details': {key: None for key in DETAIL_FIELDS}}
    write(run / 'task.json', task)
    task_markdown(run, task)
    append(run, task, 'phase', {'observation_basis': 'live', 'phase': 'intake', 'status': 'in_progress', 'note': 'Survey started; baseline may be unknown'})
    return {'run_id': run_id, 'run_path': str(run)}


def build_summary(task, report, ended_at, status):
    return {'schema_version': 1, 'run_id': task['run_id'], 'name': task['name'],
            'timezone': task['timezone'], 'started_at': task['started_at'], 'ended_at': ended_at,
            'status': status, 'elapsed_wall_seconds': round((datetime.fromisoformat(ended_at)
                - datetime.fromisoformat(task['started_at'])).total_seconds(), 2),
            'time_basis': 'Observed recording interval; full task duration unknown if recording began late',
            'intake': task['details'], 'report': report}


def imported_usage(run):
    """Use the latest snapshot; repeated imports must never be summed."""
    latest = None
    for line in (run / 'events.jsonl').read_text(encoding='utf-8').splitlines():
        event = json.loads(line)
        if event['kind'] == 'usage' and isinstance(event.get('data'), dict):
            name = event['data'].get('collector_snapshot')
            if isinstance(name, str) and re.fullmatch(r'usage-[a-f0-9]{32}\.json', name):
                path = run / name
                if linked(path):
                    raise ValueError('Usage snapshot must not be a symlink')
                latest = read(path)
    return latest


def attach_usage(run, payload):
    snapshot = imported_usage(run)
    if snapshot is not None:
        supplied = payload.get('usage')
        if supplied is not None and not isinstance(supplied, dict):
            raise ValueError('usage must be an object or null')
        payload['usage'] = {**(supplied or {}), 'measured_channels': snapshot,
                            'collector_policy': 'Latest snapshot only; never sum repeated imports'}


def collect_usage(args):
    run = resolve_run(args.run)
    rollout = args.rollout or []
    if bool(rollout) != bool(args.root):
        raise ValueError('--root and selected --rollout files must be supplied together')
    if not rollout and not args.jev_evidence:
        raise ValueError('At least one Codex rollout or JEV evidence file is required')
    codex = codex_usage.collect(rollout, args.root) if rollout else None
    jev, seen = [], set()
    for source in args.jev_evidence or []:
        path = Path(source)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('JEV evidence exceeds 1 MiB')
        raw_bytes = path.read_bytes()
        digest = hashlib.sha256(raw_bytes).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        raw = json.loads(raw_bytes)
        if not isinstance(raw, dict) or raw.get('status') not in ('pass', 'failed', 'skipped_deterministic'):
            raise ValueError('Unsupported JEV smoke evidence')
        attempts, retries = raw.get('network_calls_attempted'), raw.get('retries')
        if type(attempts) is not int or attempts < 0 or type(retries) is not int or retries < 0:
            raise ValueError('Invalid JEV attempts/retries')
        usage = raw.get('usage') if isinstance(raw.get('usage'), dict) else {}
        tokens = {k: usage.get(k) if type(usage.get(k)) is int and usage[k] >= 0 else None
                  for k in ('input_tokens', 'output_tokens')}
        if raw['status'] == 'pass' and (attempts < 1 or any(v is None for v in tokens.values())):
            raise ValueError('Successful JEV evidence needs usage and a request attempt')
        jev.append({'provider': 'typesafe', 'source_ref': path.name, 'source_sha256': digest,
                    'observation_basis': 'imported', 'status': raw['status'],
                    'model': codex_usage.identifier(raw.get('model')),
                    'measured_at': codex_usage.timestamp(raw.get('recorded_at')),
                    'scope': 'api_request', 'tokens': tokens, 'attempts': attempts,
                    'retries': retries, 'cost_usd': None})
    snapshot = {'schema_version': 1, 'coding_agents': codex, 'jev_advisory': jev,
                'coverage': 'Explicit selected sources; omitted agents/requests unknown',
                'combined_token_total': None, 'combined_cost_usd': None}
    with lock(run):
        task = read(run / 'task.json')
        if task['status'] != 'in_progress':
            raise ValueError('Run is closed; use a separately reviewed amendment')
        name = 'usage-' + uuid.uuid4().hex + '.json'
        write(run / name, snapshot)
        append(run, task, 'usage', {'observation_basis': 'imported',
               'note': 'Selected source counters imported; Codex and JEV remain separate',
               'evidence': [name], 'data': {'collector_snapshot': name}})
    return {'run_path': str(run), 'usage_snapshot': name}


def summary_markdown(run, summary):
    text = f"# {summary['name']} — retrospective\n\nRun: {summary['run_id']}\n\nStatus: {summary['status']}\n\n"
    text += f"{summary['started_at']} → {summary['ended_at']} ({summary['timezone']})\n\nObserved recording wall time: {summary['elapsed_wall_seconds']} seconds; full task duration is unknown if recording began late. Active time is not inferred.\n"
    report = summary['report']
    for key in ('outcome', 'observations', 'usage', 'difficulties', 'retries_rework',
                'time_breakdown', 'expectation_comparison', 'observation_gaps', 'retrospective'):
        value = report.get(key)
        text += '\n## ' + key.replace('_', ' ').title() + '\n\n'
        text += 'Unknown / not observed.\n' if value is None else '```json\n' + json.dumps(value, indent=2, ensure_ascii=False) + '\n```\n'
    (run / 'summary.md').write_text(text, encoding='utf-8')


def operate(args):
    run = resolve_run(args.run)
    payload = input_object(args.input)
    with lock(run):
        task = read(run / 'task.json')
        if args.command in ('update', 'event') and task['status'] != 'in_progress':
            raise ValueError('Run is closed; record corrections with amend')
        if args.command == 'update':
            if set(payload) - set(DETAIL_FIELDS):
                raise ValueError('Unknown intake fields: ' + str(sorted(set(payload) - set(DETAIL_FIELDS))))
            task['details'].update(payload)
            append(run, task, 'intake_update', {'observation_basis': 'live', 'data': payload})
            write(run / 'task.json', task)
            task_markdown(run, task)
        elif args.command == 'event':
            if args.note:
                payload['note'] = args.note
            if getattr(args, 'basis', None):
                payload['observation_basis'] = args.basis
            append(run, task, args.kind, payload)
        else:
            summary_path = run / 'summary.json'
            if args.command == 'finalize':
                if summary_path.exists() or task['status'] != 'in_progress':
                    raise ValueError('Summary already exists; use amend for explicit correction')
                if not payload:
                    raise ValueError('Final report is required; missing metrics may be null')
                attach_usage(run, payload)
                task['status'] = args.status
                summary = build_summary(task, payload, now(task), args.status)
                write(summary_path, summary)
                summary_markdown(run, summary)
                append(run, task, 'completed', {'observation_basis': 'live', 'status': args.status, 'data': {'summary': 'summary.json'}})
                write(run / 'task.json', task)
            else:
                if not summary_path.exists() or not payload:
                    raise ValueError('Amend requires an existing summary and corrected report')
                attach_usage(run, payload)
                previous = read(summary_path)
                archive = run / ('summary-before-amend-' + uuid.uuid4().hex[:8] + '.json')
                write(archive, previous)
                previous['report'] = payload
                previous['amended_at'] = now(task)
                write(summary_path, previous)
                summary_markdown(run, previous)
                append(run, task, 'amendment', {'observation_basis': 'live', 'note': 'Report corrected; original preserved', 'data': {'previous_summary': archive.name}})
    return {'run_path': str(run), 'status': task['status']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    create = subs.add_parser('start')
    create.add_argument('--task', required=True)
    create.add_argument('--timezone', required=True)
    create.add_argument('--utc-offset', required=True)
    usage = subs.add_parser('collect-usage')
    usage.add_argument('--run', required=True)
    usage.add_argument('--root', help='Exact root thread ID, not prefix')
    usage.add_argument('--rollout', action='append', help='Selected root/child JSONL; repeat')
    usage.add_argument('--jev-evidence', action='append', help='JEV smoke evidence.json; repeat')
    for command in ('update', 'event', 'finalize', 'amend'):
        sub = subs.add_parser(command)
        sub.add_argument('--run', required=True)
        sub.add_argument('--input', help='JSON object file or - for stdin')
        if command == 'event':
            sub.add_argument('--kind', required=True, choices=KINDS)
            sub.add_argument('--note')
            sub.add_argument('--basis', choices=('live', 'reported', 'imported', 'unknown'))
        if command == 'finalize':
            sub.add_argument('--status', required=True, choices=STATUSES)
    args = parser.parse_args()
    try:
        result = (start(args) if args.command == 'start' else collect_usage(args)
                  if args.command == 'collect-usage' else operate(args))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
