"""Opt-in, one-request TypeSafe advisory smoke; never dispatches coding agents."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from jev_advisory import load, prepare, recommendation, record, POLICY

ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-1.13.0'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the bearer credential to another endpoint.


def api_key(env_file):
    key = os.environ.get('TYPESAFE_API_KEY', '').strip()
    if not key and env_file:
        # Read only this named setting. Do not execute/interpolate dotenv content.
        values = []
        for line in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.strip().removeprefix('export ').partition('=')
            if sep and name.strip() == 'TYPESAFE_API_KEY':
                values.append(value.strip().strip('\"\''))
        if len(values) == 1:
            key = values[0]
    if not key or any(c.isspace() for c in key):
        raise ValueError('missing or malformed credential')
    return key


def payload(request):
    if not request['classification_required']:
        return None
    # Only eligible candidates cross the service boundary.
    state = {k: request['state'][k] for k in
             ('summary', 'trigger', 'mode', 'acceptance_gaps', 'time_remaining_seconds')}
    state['eligible_candidates'] = request['eligible']
    return {'model': MODEL, 'state': state, 'questions': {
        'next_workstream': {'type': 'choice',
                           'instructions': 'Which eligible workstream should root prioritize next? '
                                           + request['questions'][0]['criteria'],
                           'criteria': {c['id']: c['output'] for c in request['eligible']}}}}


def normalize(request, raw):
    answer = raw['answers']['next_workstream']
    if answer['type'] != 'choice':
        raise ValueError('unexpected answer type')
    normalized = {'schema_version': 1, 'policy': POLICY,
                  'state_fingerprint': request['state_fingerprint'],
                  **{k: answer[k] for k in ('choice', 'confidence', 'probabilities')}}
    if recommendation(request, normalized)[0] is None:
        raise ValueError('invalid classifier response')
    usage = raw['usage']
    if any(type(usage.get(k)) is not int or usage[k] < 0
           for k in ('input_tokens', 'output_tokens')):
        raise ValueError('invalid usage')
    if not isinstance(raw['model'], str) or not raw['model'].startswith('jev-'):
        raise ValueError('invalid returned model')
    return normalized, {'model': raw['model'],
                        'usage': {k: usage[k] for k in ('input_tokens', 'output_tokens')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True)
    parser.add_argument('--root-decision', required=True,
                        help='Root decision supplied before reading classifier scores')
    parser.add_argument('--output-dir', required=True, help='New, nonexisting directory')
    parser.add_argument('--env-file', help='Optional dotenv file; key is never logged')
    parser.add_argument('--allow-live-send-state', action='store_true',
                        help='Explicit consent to send the bounded state to TypeSafe')
    args = parser.parse_args()
    if not args.allow_live_send_state:
        parser.error('live smoke requires --allow-live-send-state')
    try:
        state, decision = load(args.state), load(args.root_decision)
        baseline = record(state, None, decision)  # Validate decision before incurring cost.
        request = prepare(state)
        body = payload(request)
        key = api_key(args.env_file) if body else None
        encoded = json.dumps(body, allow_nan=False).encode() if body else None
        if encoded and (len(encoded) > 65536 or key in encoded.decode()):
            raise ValueError('payload too large or credential present in payload')
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=False)
    except (ValueError, OSError, RecursionError):
        print('Preflight rejected; check schema, credential and new output directory. No API call made.')
        return 2
    started = time.perf_counter()
    evidence = {'recorded_at': datetime.now(timezone.utc).isoformat(),
                'endpoint': ENDPOINT, 'requested_model': MODEL,
                'state_fingerprint': request['state_fingerprint'],
                'network_calls_attempted': 0, 'retries': 0, 'status': 'skipped_deterministic',
                'payload': body, 'response': None, 'error_category': None,
                'graph_execution': 'not_run', 'cost_usd': None}
    final = baseline
    if body:
        evidence['network_calls_attempted'] = 1
        try:
            req = urllib.request.Request(ENDPOINT, data=encoded,
                    headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as res:
                raw_bytes = res.read(65537)
                if len(raw_bytes) > 65536:
                    raise ValueError('response too large')
                raw = json.loads(raw_bytes)
            normalized, metadata = normalize(request, raw)
            final = record(state, normalized, decision)
            evidence.update(metadata)
            evidence['response'] = normalized
            evidence['status'] = 'pass'
        except urllib.error.HTTPError as exc:
            evidence['status'] = 'failed'
            evidence['error_category'] = f'http_{exc.code}'
        except (urllib.error.URLError, TimeoutError, OSError):
            evidence['status'] = 'failed'
            evidence['error_category'] = 'transport_or_timeout'
        except (ValueError, KeyError, TypeError):
            evidence['status'] = 'failed'
            evidence['error_category'] = 'invalid_response'
    evidence['elapsed_seconds'] = round(time.perf_counter() - started, 4)
    final['network_calls_by_helper'] = evidence['network_calls_attempted']
    final['model_invoked_by_helper'] = evidence['network_calls_attempted'] > 0
    final['coding_models_invoked'] = False
    final['response_status'] = ('live_validated' if evidence['status'] == 'pass' else
                                'live_failed' if evidence['status'] == 'failed' else
                                final['response_status'])
    for name, value in [('request.json', request), ('record.json', final), ('evidence.json', evidence)]:
        with (out / name).open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write('\n')
    print(json.dumps({k: evidence.get(k) for k in
                     ('status', 'model', 'usage', 'elapsed_seconds', 'error_category')}))
    print(f'Evidence: {out}; graph execution not run; no model-routing proxy.')
    return 0 if evidence['status'] != 'failed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
