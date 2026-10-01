"""Recorder invariants, isolated from real user runs."""
import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('survey', Path(__file__).with_name('survey.py'))
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous_root = survey.SKILL_ROOT
        survey.SKILL_ROOT = Path(self.tmp.name)
        self.addCleanup(setattr, survey, 'SKILL_ROOT', self.previous_root)
        result = survey.start(argparse.Namespace(task='folder management', timezone='Asia/Saigon', utc_offset='+07:00'))
        self.run = Path(result['run_path'])

    def action(self, command, payload=None, **kwargs):
        path = None
        if payload is not None:
            path = Path(self.tmp.name) / 'input.json'
            path.write_text(json.dumps(payload), encoding='utf-8')
        return survey.operate(argparse.Namespace(command=command, run=str(self.run), input=str(path) if path else None, **kwargs))

    def test_start_collision_and_explicit_timezone(self):
        second = survey.start(argparse.Namespace(task='folder management', timezone='Asia/Saigon', utc_offset='+07:00'))
        self.assertNotEqual(self.run.name, second['run_id'])
        task = survey.read(self.run / 'task.json')
        self.assertEqual(datetime.fromisoformat(task['started_at']).utcoffset().total_seconds(), 7 * 3600)
        self.assertIsNone(task['details']['plan'])

    def test_events_preserve_unknown_usage_and_user_attribution(self):
        self.action('update', {'objective': 'Improve folders', 'expected_elapsed_minutes': 20})
        self.action('event', {'data': {'metric': 'subscription_used_percent', 'value': 30, 'scope': 'account', 'source_type': 'user'}}, kind='usage', note=None)
        events = [json.loads(line) for line in (self.run / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([e['sequence'] for e in events], [1, 2, 3])
        self.assertEqual(events[-1]['data']['source_type'], 'user')
        self.assertNotIn('tokens', events[-1]['data'])
        self.assertIsNone(events[-1]['observed_at'])

    def test_live_event_has_observed_time_but_historical_report_does_not(self):
        self.action('event', {'observation_basis': 'live'}, kind='phase', note='now')
        self.action('event', {'observation_basis': 'reported', 'data': {'worker_count': 1}}, kind='tool_skill', note=None)
        events = [json.loads(line) for line in (self.run / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(events[-2]['observed_at'], events[-2]['recorded_at'])
        self.assertIsNone(events[-1]['observed_at'])

    def test_finalize_and_amend_preserve_original_timing(self):
        self.action('finalize', {'outcome': {'status': 'blocked'}, 'usage': None}, status='blocked')
        original = survey.read(self.run / 'summary.json')
        self.assertIsNone(original['report']['usage'])
        self.assertGreaterEqual(original['elapsed_wall_seconds'], 0)
        with self.assertRaises(ValueError):
            self.action('finalize', {'outcome': 'success'}, status='completed')
        self.action('amend', {'outcome': {'status': 'blocked'}, 'usage': {'evidence': []}})
        amended = survey.read(self.run / 'summary.json')
        self.assertEqual(amended['ended_at'], original['ended_at'])
        archive = next(self.run.glob('summary-before-amend-*.json'))
        self.assertEqual(survey.read(archive), original)
        self.assertTrue((self.run / 'summary.md').exists())

    def test_outside_run_rejected(self):
        with self.assertRaises(ValueError):
            survey.resolve_run(Path(self.tmp.name))

    def test_no_unattributed_timestamp(self):
        with self.assertRaises(ValueError):
            self.action('event', {'observed_at': '2026-10-01T10:00:00'}, kind='phase', note=None)

    def test_writer_lock_prevents_interleaved_updates(self):
        with survey.lock(self.run):
            with self.assertRaises(FileExistsError):
                self.action('event', {}, kind='phase', note='another writer')

    def test_bad_offset_rejected(self):
        with self.assertRaises(ValueError):
            survey.offset('+14:30')


if __name__ == '__main__':
    unittest.main()
