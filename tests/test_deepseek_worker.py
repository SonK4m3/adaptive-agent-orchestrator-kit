"""Offline integration tests using real pipes/process guards; no model usage."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import deepseek_worker as worker
from process_guard import spawn_process


class DeepSeekWorkerTests(unittest.TestCase):
    def run_child(self, code, args=(), task='bounded task'):
        def spawn(command, **kwargs):
            kwargs['shell'] = False
            return spawn_process([sys.executable, '-c', code], **kwargs)
        with patch.object(worker.shutil, 'which', return_value='fake-dsh'), \
                patch.object(worker, 'spawn_process', side_effect=spawn), \
                patch.object(worker.sys, 'stdin', io.StringIO(task)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            status = worker.main(list(args))
        return status, json.loads(output.getvalue())

    def test_final_only_and_permission_not_verified(self):
        payload = '\n'.join(json.dumps(e) for e in [
            {'type':'session','id':'session-test'}, {'type':'thinking','text':'HIDDEN'},
            {'type':'final','text':'done','sessionId':'session-test',
             'reason':{'kind':'completed'}}])
        status, report = self.run_child(f'print({payload!r})')
        self.assertEqual(status, 0)
        self.assertEqual(report['answer'], 'done')
        self.assertEqual(report['session_id'], 'session-test')
        self.assertEqual(report['final_reason'], 'completed')
        self.assertEqual(report['failure_layer'], None)
        self.assertEqual(report['requested_permission_mode'], 'read-only')
        self.assertIsNone(report['effective_permission_mode'])
        self.assertEqual(report['permission_verification'], 'unverified')
        self.assertNotIn('HIDDEN', json.dumps(report))

    def test_utf8_input_output_under_cp1252(self):
        child = ('import json,sys; text=sys.stdin.buffer.read().decode("utf-8"); '
                 'sys.stdout.buffer.write((json.dumps({"type":"final","text":text,"reason":{"kind":"completed"}},'
                 'ensure_ascii=False)+"\\n").encode("utf-8"))')
        runner = (f'import sys; sys.path.insert(0, {str(SCRIPTS)!r}); '
                  'import deepseek_worker as w; from process_guard import spawn_process; '
                  'w.shutil.which=lambda _: "fake-dsh"; '
                  f'w.spawn_process=lambda cmd, **kw: spawn_process([sys.executable,"-c",{child!r}], **kw); '
                  'raise SystemExit(w.main([]))')
        result = subprocess.run([sys.executable, '-c', runner],
                                input='Tiếng Việt → 日本語 😀'.encode('utf-8'),
                                capture_output=True, env=dict(os.environ, PYTHONIOENCODING='cp1252'), timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.isascii())
        self.assertEqual(json.loads(result.stdout)['answer'], 'Tiếng Việt → 日本語 😀')

    def test_environment_filter_and_explicit_write_permission(self):
        code = ('import os,json; print(json.dumps({"type":"final","reason":{"kind":"completed"},"text":json.dumps('
                '{k:os.environ.get(k) for k in ["UNRELATED_SECRET","NODE_OPTIONS",'
                '"PYTHONPATH","DSH_PERMISSION_MODE","DEEPSEEK_API_KEY"]})}))')
        with patch.dict(os.environ, {'UNRELATED_SECRET':'SENTINEL', 'NODE_OPTIONS':'--inspect',
                                     'PYTHONPATH':'bad', 'DSH_PERMISSION_MODE':'unsafe',
                                     'DEEPSEEK_API_KEY':'fake-test-key'}):
            status, report = self.run_child(code, ['--permission-mode', 'workspace-write'])
        self.assertEqual(status, 0)
        child = json.loads(report['answer'])
        for key in ['UNRELATED_SECRET', 'NODE_OPTIONS', 'PYTHONPATH']:
            self.assertIsNone(child[key])
        self.assertEqual(child['DSH_PERMISSION_MODE'], 'workspace-write')
        self.assertEqual(child['DEEPSEEK_API_KEY'], 'fake-test-key')

    def test_timeout_retains_session(self):
        start = time.monotonic()
        status, report = self.run_child(
            'import time; print(\'{"type":"session","id":"session-timeout"}\',flush=True); time.sleep(30)',
            ['--timeout-seconds', '1'])
        self.assertEqual(status, 124)
        self.assertEqual(report['status'], 'timeout')
        self.assertEqual(report['session_id'], 'session-timeout')
        self.assertEqual(report['failure_layer'], 'wrapper')
        self.assertFalse(report['output_capture_complete'])
        self.assertNotIn('answer', report)
        self.assertLess(time.monotonic() - start, 6)

    def test_progress_journal_records_only_bounded_lifecycle_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / 'progress.jsonl'
            events = [
                {'type':'session','sessionId':'session-progress','cwd':'/private/path'},
                {'type':'status','phase':'step_end','step':2},
                {'type':'text','text':'SECRET_ANSWER'},
                {'type':'tool_result','result':'SECRET_TOOL_OUTPUT'},
                {'type':'final','sessionId':'session-progress','reason':{'kind':'completed'},
                 'text':'SECRET_FINAL'},
            ]
            code = 'import json; print(' + repr('\n'.join(json.dumps(e) for e in events)) + ')'
            status, report = self.run_child(code, ['--progress-file', str(progress)])
            rows = [json.loads(line) for line in progress.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(status, 0)
            self.assertEqual(report['progress_events_written'], 5)
            self.assertEqual(report['progress_write_errors'], 0)
            self.assertEqual([row['event_type'] for row in rows],
                             ['session', 'status', 'text', 'tool_result', 'final'])
            self.assertEqual(rows[0]['session_id'], 'session-progress')
            self.assertEqual(rows[1]['phase'], 'step_end')
            self.assertEqual(rows[-1]['final_reason'], 'completed')
            self.assertNotIn('SECRET', json.dumps(rows))
            self.assertNotIn('cwd', json.dumps(rows))

    def test_blocked_stdin_timeout(self):
        status, report = self.run_child('import time; time.sleep(30)',
                                      ['--timeout-seconds', '1'], 'x' * 500000)
        self.assertEqual(status, 124)
        self.assertEqual(report['status'], 'timeout')

    def test_output_limits(self):
        for fd, flag in [(1, '--max-stdout-bytes'), (2, '--max-stderr-bytes')]:
            with self.subTest(fd=fd):
                status, report = self.run_child(
                    f'import os,time; os.write({fd}, b"X"*100000); time.sleep(30)', [flag, '1024'])
                self.assertEqual(status, 1)
                self.assertEqual(report['status'], 'output_limit')
                self.assertNotIn('answer', report)

    def test_failed_jobs_suppress_answers_and_diagnostics(self):
        for suffix in ['raise SystemExit(7)', 'print(\'{"type":"error","message":"SECRET"}\')']:
            status, report = self.run_child(
                'import sys; print(\'{"type":"final","text":"not accepted"}\'); '
                'sys.stderr.write("401 Unauthorized credential=SECRET"); ' + suffix)
            self.assertEqual(status, 1)
            self.assertEqual(report['status'], 'failed')
            self.assertNotIn('answer', report)
            self.assertNotIn('SECRET', json.dumps(report))
            self.assertEqual(report['stderr_signals'], ['authentication'])

    def test_missing_final_and_conflicting_sessions(self):
        for lines in [[], [{'type':'status'}],
                      [{'type':'session','id':'a'}, {'type':'session','id':'b'}, {'type':'final','text':'done'}],
                      [{'type':'final','text':'one'}, {'type':'final','text':'two'}]]:
            payload = '\n'.join(json.dumps(x) for x in lines)
            status, report = self.run_child(f'print({payload!r})')
            self.assertEqual(status, 1)
            self.assertNotIn('answer', report)

    def test_session_aliases_and_absence(self):
        for key in ['session_id', 'sessionId', 'id']:
            parsed = worker.read_result(json.dumps({'type':'session',key:'same'}).encode())
            self.assertEqual(parsed['session_id'], 'same')
        status, report = self.run_child('print(\'{"type":"final","text":"done","reason":{"kind":"completed"}}\')')
        self.assertEqual(status, 0)
        self.assertIsNone(report['session_id'])
        self.assertEqual(report['session_evidence'], 'missing')

    def test_explicit_session_resume_is_passed_to_dsh(self):
        child = ('import json,sys; print(json.dumps({"type":"final","text":"resumed",'
                 '"reason":"completed","sessionId":"session-resume"}))')
        expected_command = []
        def spawn(command, **kwargs):
            expected_command.extend(command)
            kwargs['shell'] = False
            return spawn_process([sys.executable, '-c', child], **kwargs)
        with patch.object(worker.shutil, 'which', return_value='fake-dsh'), \
                patch.object(worker, 'spawn_process', side_effect=spawn), \
                patch.object(worker.sys, 'stdin', io.StringIO('continue from checkpoint')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            status = worker.main(['--session-id', 'session-resume'])
        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(expected_command, ['fake-dsh', '--profile', 'headless', '--session-id',
                                            'session-resume', '--json', '-'])
        self.assertEqual(report['requested_session_id'], 'session-resume')
        self.assertEqual(report['final_session_id'], 'session-resume')

    def test_noncompleted_final_reason_is_reported_as_dsh_failure(self):
        payload = json.dumps({'type':'final','text':'partial','reason':'max_tokens',
                              'sessionId':'session-partial'})
        status, report = self.run_child(f'print({payload!r})')
        self.assertEqual(status, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['failure_layer'], 'dsh')
        self.assertEqual(report['final_reason'], 'max_tokens')
        self.assertNotIn('answer', report)

    def test_final_session_mismatch_is_protocol_failure(self):
        payload = '\\n'.join(json.dumps(e) for e in [
            {'type':'session','id':'session-a'},
            {'type':'final','text':'done','reason':'completed','sessionId':'session-b'}])
        status, report = self.run_child(f'print({payload!r})')
        self.assertEqual(status, 1)
        self.assertEqual(report['failure_layer'], 'protocol')
        self.assertGreater(report['protocol_errors'], 0)

    def test_invalid_resume_session_id_is_rejected_before_spawn(self):
        with patch.object(worker, 'spawn_process') as spawn, \
                patch.object(worker.sys, 'stdin', io.StringIO('task')), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                worker.main(['--session-id', 'bad/id'])
        self.assertEqual(raised.exception.code, 2)
        spawn.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows batch launcher')
    def test_windows_cmd_launcher_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='dsh launcher ') as tmp:
            base = Path(tmp)
            (base / 'child.py').write_text(
                'import sys,json; assert sys.argv[1:] == ["--profile","headless","--json","-"]; '
                'print(json.dumps({"type":"final","text":"batch works","reason":{"kind":"completed"}}))', encoding='utf-8')
            launcher = base / 'dsh.cmd'
            launcher.write_text(f'@echo off\n@"{sys.executable}" "%~dp0child.py" %*\n', encoding='utf-8')
            with patch.object(worker.shutil, 'which', return_value=str(launcher)), \
                    patch.object(worker.sys, 'stdin', io.StringIO('task')), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(worker.main(['--timeout-seconds','5']), 0)
            self.assertEqual(json.loads(output.getvalue())['answer'], 'batch works')

    def test_cleanup_failure_preserves_primary_timeout(self):
        class Guard:
            def __init__(self, real):
                self.real = real
            def close(self):
                self.real.close()
                raise OSError('synthetic failure')
        proc, real_guard = spawn_process([sys.executable, '-c', 'import time; time.sleep(30)'],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr, counts, reason, errors = worker.capture(proc, Guard(real_guard), b'task', 0.1, 1024, 1024)
        self.assertEqual(reason, 'timeout')
        self.assertIn('guard_close_failed', errors)

    def test_descendant_held_pipes_are_closed_on_timeout(self):
        code = ('import subprocess,sys; subprocess.Popen([sys.executable,"-c",'
                '"import time; time.sleep(30)"]); '
                'print(\'{"type":"session","id":"parent-exited"}\', flush=True)')
        start = time.monotonic()
        status, report = self.run_child(code, ['--timeout-seconds', '1'])
        self.assertEqual(status, 124)
        self.assertEqual(report['cleanup_errors'], [])
        self.assertLess(time.monotonic() - start, 6)

    def test_invalid_events_fail_closed(self):
        cases = [b'not-json-SECRET', b'[]', b'\xff', b'{"type":"final","type":"text"}',
                 b'{"type":"final","text":NaN}', b'[' * 2000 + b']' * 2000,
                 b'{"type":"session","id":"bad\\nvalue"}', b'x' * (worker.MAX_EVENT + 1)]
        for raw in cases:
            parsed = worker.read_result(raw)
            self.assertGreater(parsed['protocol_errors'], 0)
            self.assertIsNone(parsed['answer'])
        self.assertGreater(worker.read_result(b'{}\n' * (worker.MAX_EVENTS + 1))['protocol_errors'], 0)

    def test_missing_cli_or_task(self):
        with patch.object(worker.shutil, 'which', return_value=None), \
                patch.object(worker, 'spawn_process') as spawn, \
                patch.object(worker.sys, 'stdin', io.StringIO('task')), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(worker.main([]), 127)
        spawn.assert_not_called()
        with patch.object(worker.sys, 'stdin', io.StringIO('  ')), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(worker.main([]), 2)


if __name__ == '__main__':
    unittest.main()
