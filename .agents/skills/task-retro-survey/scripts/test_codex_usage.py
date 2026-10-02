"""Synthetic, credential-free collector and survey integration checks."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
import sys

import codex_usage as usage
import survey


def event(kind, payload, stamp='2026-10-02T01:00:00Z'):
    return {'type': kind, 'payload': payload, 'timestamp': stamp}


def counts(n):
    return dict(input_tokens=n, cached_input_tokens=2, output_tokens=3,
                reasoning_output_tokens=1, total_tokens=n + 3)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def log(self, name='root', parent=None, records=None, cumulative=None, role=None):
        meta = {'id': name, 'session_id': 'root', 'parent_thread_id': parent,
                'cwd': 'PRIVATE_REPOSITORY', 'instructions': 'SECRET_INSTRUCTIONS'}
        if role:
            meta['source'] = {'subagent': {'thread_spawn': {'agent_role': role}}}
        events = [event('session_meta', meta),
                  event('turn_context', {'model': 'model-a', 'effort': 'medium'}),
                  event('response_item', {'text': 'SECRET_PROMPT'})]
        events += records or []
        if cumulative is not None:
            events.append(event('event_msg', {'type': 'token_count',
                          'info': {'total_token_usage': cumulative}}))
        path = self.base / (name + '.jsonl')
        path.write_text('\n'.join(json.dumps(e) for e in events) + '\n')
        return path

    def test_readonly_and_privacy(self):
        path = self.log(cumulative=counts(10))
        before = path.read_bytes()
        report = usage.collect([path], 'root')
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(report['threads'][0]['sha256'], hashlib.sha256(before).hexdigest())
        self.assertNotIn('SECRET', json.dumps(report))
        self.assertNotIn('PRIVATE_REPOSITORY', json.dumps(report))
        self.assertIsNone(report['usage_total'])

    def test_response_dedup_and_no_cumulative_double_count(self):
        response = event('token_usage_record', {'id': 'response-1', 'usage': counts(10)})
        path = self.log(records=[response, response], cumulative=counts(10))
        t = usage.analyze(path)
        self.assertEqual(t['counters']['input_tokens'], 10)
        self.assertEqual(len(t['responses']), 1)
        self.assertEqual(t['by_model'][0]['model'], 'model-a')

    def test_equal_usage_without_id_is_not_silently_deduplicated(self):
        response = event('token_usage_record', {'usage': counts(10)})
        t = usage.analyze(self.log(records=[response, response]))
        self.assertEqual(t['counters']['input_tokens'], 20)
        self.assertTrue(any('possible_replay' in g['reason'] for g in t['gaps']))

    def test_partial_response_coverage_flagged(self):
        t = usage.analyze(self.log(records=[event('token_usage_record', {'usage': counts(10)})],
                                  cumulative=counts(20)))
        self.assertTrue(any('differs' in g['reason'] for g in t['gaps']))
        self.assertEqual(t['counters']['input_tokens'], 10)

    def test_cumulative_not_assigned_to_last_model(self):
        t = usage.analyze(self.log(records=[event('turn_context', {'model': 'model-b', 'effort': 'high'})],
                                  cumulative=counts(10)))
        self.assertEqual(t['by_model'], [])
        self.assertEqual(len(t['model_bindings']), 2)

    def test_unknown_not_zero(self):
        t = usage.analyze(self.log())
        self.assertIsNone(t['counters']['total_tokens'])
        self.assertEqual(t['counter_basis'], 'missing')
        bad = counts(10)
        bad['input_tokens'] = True
        self.assertIsNone(usage.analyze(self.log(cumulative=bad))['counters']['input_tokens'])

    def test_parent_chain_and_guardian_included(self):
        root = self.log()
        child = self.log('child', 'root', cumulative=counts(20), role='guardian')
        report = usage.collect([root, child, child], 'root')
        self.assertEqual(len(report['threads']), 2)
        self.assertEqual(report['threads'][1]['category'], 'approval_review')

    def test_unrelated_and_missing_root_rejected(self):
        child = self.log('other')
        with self.assertRaises(ValueError):
            usage.collect([child], 'root')
        root = self.log()
        raw = child.read_text().replace('"session_id": "root"', '"session_id": "unrelated"')
        child.write_text(raw)
        with self.assertRaises(ValueError):
            usage.collect([root, child], 'root')

    def test_counter_decrease_and_malformed_line(self):
        path = self.log(records=[event('event_msg', {'type': 'token_count',
                                      'info': {'total_token_usage': counts(20)}})], cumulative=counts(10))
        with path.open('a') as fh:
            fh.write('not json\n')
        reasons = [g['reason'] for g in usage.analyze(path)['gaps']]
        self.assertIn('cumulative_counter_decreased', reasons)
        self.assertIn('malformed_envelope', reasons)

    def test_snapshot_conflicts_rejected(self):
        root = self.log()
        other = self.base / 'second.jsonl'
        other.write_text(root.read_text() + '\n')
        with self.assertRaises(ValueError):
            usage.collect([root, other], 'root')

    def test_import_and_finalize_keep_channels_separate(self):
        previous = survey.SKILL_ROOT
        survey.SKILL_ROOT = self.base
        self.addCleanup(setattr, survey, 'SKILL_ROOT', previous)
        run = Path(survey.start(argparse.Namespace(task='test', timezone='Asia/Saigon',
                                                 utc_offset='+07:00'))['run_path'])
        jev = self.base / 'jev.json'
        jev.write_text(json.dumps({'status': 'pass', 'network_calls_attempted': 1, 'retries': 0,
                                  'model': 'jev-1.13.0', 'usage': {'input_tokens': 9, 'output_tokens': 2},
                                  'payload': 'SECRET_NOT_IMPORTED'}))
        args = argparse.Namespace(run=str(run), root='root', rollout=[str(self.log(cumulative=counts(20)))],
                                  jev_evidence=[str(jev), str(jev)])
        survey.collect_usage(args)
        survey.collect_usage(args)  # snapshots, not another billable request
        payload = self.base / 'report.json'
        payload.write_text(json.dumps({'outcome': {'status': 'partial'}, 'usage': None}))
        survey.operate(argparse.Namespace(command='finalize', run=str(run), input=str(payload), status='partial'))
        summary = survey.read(run / 'summary.json')
        channels = summary['report']['usage']['measured_channels']
        self.assertEqual(len(channels['jev_advisory']), 1)
        self.assertEqual(channels['jev_advisory'][0]['tokens']['input_tokens'], 9)
        self.assertIsNone(channels['combined_token_total'])
        self.assertNotIn('SECRET', json.dumps(summary))
        self.assertTrue((run / 'summary.md').exists())
        with self.assertRaises(ValueError):
            survey.collect_usage(args)

    def test_account_snapshot_has_no_task_delta(self):
        path = self.log(records=[event('event_msg', {'type': 'token_count', 'rate_limits': {
            'primary': {'used_percent': 30, 'resets_at': 100}, 'secondary': {'used_percent': 20}}})])
        report = usage.collect([path], 'root')
        self.assertIsNone(report['subscription_delta'])
        self.assertEqual(report['threads'][0]['account_snapshots'][0]['scope'], 'account')

    def test_copied_skill_runs_without_repository_dependencies(self):
        copied = self.base / 'shared-skill'
        shutil.copytree(Path(__file__).resolve().parents[1], copied,
                        ignore=shutil.ignore_patterns('runs', '__pycache__'))
        script = copied / 'scripts/survey.py'
        started = subprocess.run([sys.executable, str(script), 'start', '--task', 'portable',
                                  '--timezone', 'Asia/Saigon', '--utc-offset', '+07:00'],
                                 cwd=self.base, capture_output=True, text=True)
        self.assertEqual(started.returncode, 0, started.stderr)
        run = json.loads(started.stdout)['run_path']
        imported = subprocess.run([sys.executable, str(script), 'collect-usage', '--run', run,
                                   '--root', 'root', '--rollout', str(self.log())],
                                  cwd=self.base, capture_output=True, text=True)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertTrue(list(Path(run).glob('usage-*.json')))


if __name__ == '__main__':
    unittest.main()
