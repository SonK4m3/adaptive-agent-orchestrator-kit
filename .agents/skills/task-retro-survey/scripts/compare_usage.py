"""Read-only comparison gate for paired retros; never runs a benchmark or estimates billing."""
import argparse
import json
from pathlib import Path
import re

FIXED = ('spec_sha256', 'prompt_sha256', 'fixture_sha256', 'coding_models', 'acceptance_ids')


def compare(baseline, advisory):
    issues = []
    runs = [baseline, advisory]
    contracts = []
    for index, run in enumerate(runs):
        label = ('baseline', 'advisory')[index]
        contract = run.get('intake', {}).get('comparison_contract')
        if not isinstance(contract, dict):
            issues.append(label + ': missing comparison contract')
            contract = {}
        contracts.append(contract)
        for key in ('spec_sha256', 'prompt_sha256', 'fixture_sha256'):
            if not isinstance(contract.get(key), str) or not re.fullmatch(r'[a-f0-9]{64}', contract[key]):
                issues.append(label + ': missing valid ' + key)
        ids = contract.get('acceptance_ids')
        if (not isinstance(ids, list) or not ids or not all(isinstance(v, str) and v for v in ids)
                or len(ids) != len(set(ids))):
            issues.append(label + ': invalid acceptance IDs')
            ids = []
        if not isinstance(contract.get('coding_models'), dict) or 'root' not in contract.get('coding_models', {}):
            issues.append(label + ': missing root/role model bindings')
        if contract.get('jev_enabled') is not bool(index):
            issues.append(label + ': incorrect advisory arm')
        report = run.get('report', {})
        outcome = report.get('outcome')
        criteria = outcome.get('criteria') if isinstance(outcome, dict) else None
        if not isinstance(criteria, list):
            criteria = []
        valid = [c for c in criteria if isinstance(c, dict) and isinstance(c.get('id'), str)]
        if (len(valid) != len(criteria) or len(valid) != len(ids)
                or {c['id'] for c in valid} != set(ids)
                or any(c.get('result') != 'met' or not isinstance(c.get('evidence'), list)
                       or not c['evidence'] or not all(isinstance(e, str) and e for e in c['evidence']) for c in valid)):
            issues.append(label + ': acceptance not fully evidenced')
        if run.get('status') != 'completed':
            issues.append(label + ': task not completed')
        channels = report.get('usage', {})
        channels = channels.get('measured_channels', {}) if isinstance(channels, dict) else {}
        coding = channels.get('coding_agents') or {}
        threads = coding.get('threads', [])
        if not threads or not any(t.get('role') == 'root' for t in threads):
            issues.append(label + ': missing observed coding resources')
        declared = contract.get('coding_models') or {}
        if not isinstance(declared, dict):
            declared = {}
        for thread in threads:
            if thread.get('category') == 'approval_review':
                continue
            binding = declared.get(thread.get('role'))
            observed = thread.get('model_bindings')
            if (not isinstance(binding, dict) or set(binding) != {'model', 'effort'}
                    or not all(isinstance(v, str) and v for v in binding.values())
                    or observed != [binding]):
                issues.append(label + ': model/effort unconfirmed or changed for ' + str(thread.get('role')))
        jev = channels.get('jev_advisory', [])
        if index == 0 and jev:
            issues.append(label + ': JEV evidence present in baseline')
        if index == 1 and not any(j.get('status') == 'pass' for j in jev):
            issues.append(label + ': successful JEV request not evidenced')
    for key in FIXED:
        if contracts[0].get(key) != contracts[1].get(key):
            issues.append('changed comparison invariant: ' + key)
    if not baseline.get('run_id') or baseline.get('run_id') == advisory.get('run_id') or not advisory.get('run_id'):
        issues.append('distinct run IDs required')
    return {'schema_version': 1, 'status': 'blocked' if issues else 'eligible_for_review',
            'issues': issues, 'run_ids': [r.get('run_id') for r in runs],
            'savings': None, 'usage_total_delta': None, 'subscription_delta': None,
            'limitations': 'Contract and evidence pointers are declarations, not independent verification. '
                           'Selected rollout coverage may be incomplete. No billing or savings inference. '
                           'Inspect acceptance artifacts, isolation and counters before drawing conclusions.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--advisory', required=True)
    args = parser.parse_args()
    try:
        result = compare(*[json.loads(Path(p).read_text(encoding='utf-8-sig'))
                           for p in (args.baseline, args.advisory)])
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'eligible_for_review' else 1
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        parser.exit(2, 'Malformed comparison summaries.\n')


if __name__ == '__main__':
    raise SystemExit(main())
