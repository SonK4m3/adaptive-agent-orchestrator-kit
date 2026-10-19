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
            {'type':'final','text':'done'}])
        status, report = self.run_child(f'print({payload!r})')
        self.assertEqual(status, 0)
        self.assertEqual(report['answer'], 'done')
        self.assertEqual(report['session_id'], 'session-test')
        self.assertEqual(report['requested_permission_mode'], 'read-only')
        self.assertIsNone(report['effective_permission_mode'])
        self.assertEqual(report['permission_verification'], 'unverified')
        self.assertNotIn('HIDDEN', json.dumps(report))

    def test_utf8_input_output_under_cp1252(self):
        child = ('import json,sys; text=sys.stdin.buffer.read().decode("utf-8"); '
                 'sys.stdout.buffer.write((json.dumps({"type":"final","text":text},'
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
        code = ('import os,json; print(json.dumps({"type":"final","text":json.dumps('
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
        self.assertFalse(report['output_capture_complete'])
        self.assertNotIn('answer', report)
        self.assertLess(time.monotonic() - start, 6)

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
        status, report = self.run_child('print(\'{"type":"final","text":"done"}\')')
        self.assertEqual(status, 0)
        self.assertIsNone(report['session_id'])
        self.assertEqual(report['session_evidence'], 'missing')

    @unittest.skipUnless(os.name == 'nt', 'Windows batch launcher')
    def test_windows_cmd_launcher_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='dsh launcher ') as tmp:
            base = Path(tmp)
            (base / 'child.py').write_text(
                'import sys,json; assert sys.argv[1:] == ["--profile","headless","--json","-"]; '
                'print(json.dumps({"type":"final","text":"batch works"}))', encoding='utf-8')
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
