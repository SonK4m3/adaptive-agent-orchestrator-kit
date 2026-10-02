import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from jev_advisory import prepare, record, recommendation, POLICY
from jev_live_smoke import api_key, payload, normalize, NoRedirect, main as live_main


def state():
    return json.loads((ROOT / 'eval/fixtures/jev-advisory/state.json').read_text())


def response(s):
    return {'schema_version': 1, 'policy': POLICY,
            'state_fingerprint': prepare(s)['state_fingerprint'],
            'choice': 'independent-review', 'confidence': .9,
            'probabilities': {'reuse-worker': .2, 'independent-review': .8}}


def decision():
    return {'choice': 'reuse-worker', 'reason': 'Run outstanding test first.', 'evidence': []}


class AdvisoryTests(unittest.TestCase):
    def test_ownership_filter_before_classification(self):
        result = prepare(state())
        self.assertEqual(result['rejected']['conflicting-worker'], ['ownership_conflict'])
        self.assertEqual(result['questions'][0]['choices'], ['reuse-worker', 'independent-review'])

    def test_root_overrides_without_executing(self):
        s = state()
        result = record(s, response(s), decision())
        self.assertEqual(result['disposition'], 'overridden')
        self.assertFalse(result['executed'])
        self.assertFalse(result['model_invoked_by_helper'])
        self.assertEqual(result['network_calls_by_helper'], 0)
        self.assertIsNone(result['outcome'])
        self.assertEqual(result['state']['acceptance_gaps'], s['acceptance_gaps'])

    def test_acceptance(self):
        s = state()
        d = decision()
        d['choice'] = 'independent-review'
        self.assertEqual(record(s, response(s), d)['disposition'], 'accepted')

    def test_stale_advice(self):
        s = state()
        old = response(s)
        for key, value in [('revision', 2), ('summary', 'New requirement'), ('time_remaining_seconds', 299)]:
            changed = copy.deepcopy(s)
            changed[key] = value
            self.assertEqual(record(changed, old, decision())['disposition'], 'fallback')

    def test_candidate_change_invalidates_advice(self):
        s = state()
        old = response(s)
        s['candidates'][0]['output'] = 'Changed work contract'
        self.assertIsNone(recommendation(prepare(s), old)[0])

    def test_no_classifier_when_one_choice(self):
        s = state()
        s['max_agents'] = 1
        result = prepare(s)
        self.assertFalse(result['classification_required'])
        self.assertEqual(result['questions'], [])
        self.assertEqual([c['id'] for c in result['eligible']], ['reuse-worker'])

    def test_unavailable_fallback(self):
        self.assertEqual(record(state(), None, decision())['response_status'], 'not_supplied')

    def test_invalid_response_fallback(self):
        s = state()
        for change in ({'choice': 'conflicting-worker'}, {'confidence': float('nan')},
                       {'confidence': True}, {'probabilities': {'reuse-worker': 1}},
                       {'choice': 'reuse-worker'}, {'schema_version': True}):
            r = response(s)
            r.update(change)
            with self.subTest(change=change):
                self.assertEqual(record(s, r, decision())['response_status'], 'invalid_response')

    def test_root_cannot_select_rejected_choice(self):
        d = decision()
        d['choice'] = 'conflicting-worker'
        with self.assertRaises(ValueError):
            record(state(), None, d)

    def test_scope_readonly_runtime_and_independence(self):
        for key, value, cid, reason in [
                ('mode', 'review', 'reuse-worker', 'read_only'),
                ('allowed_write_paths', [], 'reuse-worker', 'outside_write_scope'),
                ('available_roles', ['worker'], 'independent-review', 'role_unavailable'),
                ('max_agents', 0, 'reuse-worker', 'capacity_already_exceeded')]:
            s = state()
            s[key] = value
            self.assertIn(reason, prepare(s)['rejected'][cid])
        s = state()
        s['candidates'][1]['independent'] = False
        self.assertIn('no_independent_output', prepare(s)['rejected']['independent-review'])

    def test_hard_stop_only_allows_stop(self):
        for key, value in [('time_remaining_seconds', 0), ('stop_required', True)]:
            s = state()
            s[key] = value
            s['candidates'].append({'id': 'stop', 'action': 'stop', 'role': 'architect',
                                    'actor': 'root', 'output': 'Report unresolved gaps.',
                                    'write_paths': [], 'independent': False})
            self.assertEqual([c['id'] for c in prepare(s)['eligible']], ['stop'])

    def test_conflicting_current_ownership_rejected(self):
        s = state()
        s['owners'].append({'actor': 'root', 'write_paths': ['./SRC\\AUTH.ts']})
        with self.assertRaises(ValueError):
            prepare(s)

    def test_paths_bounds_unknown_fields_and_bool(self):
        for change in [{'revision': True}, {'summary': 'x' * 1001}, {'secret': 'do not transmit'},
                       {'allowed_write_paths': ['../outside.ts']}, {'active_agents': ['root']},
                       {'acceptance_gaps': ['gap'] * 33}]:
            s = state()
            s.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                prepare(s)

    def test_wrong_types_rejected_cleanly(self):
        s = state()
        s['candidates'][0]['action'] = []
        with self.assertRaises(ValueError):
            prepare(s)

    def test_live_payload_excludes_rejected_and_identity(self):
        body = payload(prepare(state()))
        self.assertNotIn('conflicting-worker', json.dumps(body))
        self.assertNotIn('owners', body['state'])
        self.assertNotIn('task_id', body['state'])
        self.assertEqual(body['questions']['next_workstream']['type'], 'choice')

    def test_live_skip_single_candidate(self):
        s = state()
        s['max_agents'] = 1
        self.assertIsNone(payload(prepare(s)))

    def test_live_response_normalization(self):
        s = state()
        r = response(s)
        raw = {'model': 'jev-1.13.0', 'usage': {'input_tokens': 10, 'output_tokens': 2},
               'answers': {'next_workstream': {'type': 'choice', **{k: r[k] for k in
                           ('choice', 'confidence', 'probabilities')}}}}
        normalized, metadata = normalize(prepare(s), raw)
        self.assertEqual(normalized, r)
        self.assertEqual(metadata['usage']['input_tokens'], 10)
        raw['usage']['input_tokens'] = True
        with self.assertRaises(ValueError):
            normalize(prepare(s), raw)

    def test_redirect_denied(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other'))

    def test_env_key_parser_no_execution_or_logging(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {}, clear=True):
            env = Path(tmp) / '.env'
            env.write_text('UNRELATED=private\nexport TYPESAFE_API_KEY="test-key"\n')
            self.assertEqual(api_key(env), 'test-key')
            env.write_text('TYPESAFE_API_KEY=a\nTYPESAFE_API_KEY=b\n')
            with self.assertRaises(ValueError):
                api_key(env)

    def test_live_mock_failure_records_fallback_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'evidence'
            argv = ['jev_live_smoke.py', '--state', str(ROOT / 'eval/fixtures/jev-advisory/state.json'),
                    '--root-decision', str(ROOT / 'eval/fixtures/jev-advisory/root-decision.json'),
                    '--output-dir', str(out), '--allow-live-send-state']
            with patch.object(sys, 'argv', argv), patch.dict('os.environ', {'TYPESAFE_API_KEY': 'test-key'}), \
                    patch('jev_live_smoke.urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect = urllib.error.HTTPError(
                    'fixed', 401, 'sensitive body deliberately not emitted', {}, None)
                self.assertEqual(live_main(), 1)
                self.assertEqual(opener.return_value.open.call_count, 1)
            evidence = json.loads((out / 'evidence.json').read_text())
            self.assertEqual(evidence['error_category'], 'http_401')
            self.assertNotIn('test-key', json.dumps(evidence))
            result = json.loads((out / 'record.json').read_text())
            self.assertEqual(result['disposition'], 'fallback')
            self.assertEqual(result['response_status'], 'live_failed')
            self.assertFalse(result['coding_models_invoked'])

    def test_live_send_gate(self):
        with patch.object(sys, 'argv', ['jev_live_smoke.py', '--state', 'unused',
                                      '--root-decision', 'unused', '--output-dir', 'unused']), \
                patch('jev_live_smoke.urllib.request.build_opener') as opener:
            with self.assertRaises(SystemExit):
                live_main()
            opener.assert_not_called()

    def test_cli_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'request.json'
            command = [sys.executable, str(ROOT / 'scripts/jev_advisory.py'), 'prepare',
                       '--state', str(ROOT / 'eval/fixtures/jev-advisory/state.json'),
                       '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = output.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
