"""Real wrapper subprocesses with fake DSH; no model or routing engine is run."""
import ctypes
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'scripts/deepseek_worker.py'
FAKE = ROOT / 'eval/fixtures/deepseek-worker/fake_dsh.py'


def prepare_workspace(base):
    """Create a fake launcher and a small acceptance test in a disposable cwd."""
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    launcher_dir = base / 'fake-bin'
    launcher_dir.mkdir(exist_ok=True)
    if os.name == 'nt':
        (launcher_dir / 'dsh.cmd').write_text(
            f'@echo off\n"{sys.executable}" "{FAKE}" %*\n', encoding='utf-8')
    else:
        launcher = launcher_dir / 'dsh'
        launcher.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(FAKE))} "$@"\n')
        launcher.chmod(0o700)
    (base / 'calc.py').write_text('def add(a, b):\n    raise NotImplementedError\n')
    (base / 'test_calc.py').write_text(
        'import unittest\nfrom calc import add\n'
        'class AddTests(unittest.TestCase):\n'
        '    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n')
    return launcher_dir


def invoke_fake(base, case, timeout=5, wrapper=WRAPPER):
    """Invoke the unchanged wrapper; PATH points at the fake only in this child."""
    base = Path(base)
    launcher_dir = base / 'fake-bin'
    environment = dict(os.environ, PATH=str(launcher_dir) + os.pathsep + os.environ.get('PATH', ''))
    result = subprocess.run(
        [sys.executable, str(wrapper), '--permission-mode', 'workspace-write',
         '--timeout-seconds', str(timeout)],
        cwd=base, env=environment, input=json.dumps({'case': case}).encode('utf-8'),
        capture_output=True, timeout=timeout + 12)
    return result, json.loads(result.stdout)


def process_alive(pid):
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() != 87  # Unknown/access denied is not confirmed stopped.
    try:
        code = ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == 259
    finally:
        kernel.CloseHandle(handle)


class HybridDelegationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hybrid fake ')
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        prepare_workspace(self.workspace)

    def verify(self):
        return subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-v'],
                              cwd=self.workspace, capture_output=True, timeout=10)

    def test_success_and_independent_verification_in_caller_cwd(self):
        result, report = invoke_fake(self.workspace, 'success')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['session_id'], 'fake-success')
        self.assertIn('final', report['event_types'])
        self.assertIn('Tiếng Việt', report['answer'])
        self.assertEqual(report['requested_permission_mode'], 'workspace-write')
        self.assertIsNone(report['effective_permission_mode'])
        self.assertEqual(self.verify().returncode, 0)
        self.assertFalse(process_alive(int((self.workspace / 'worker.pid').read_text())))

    def test_provider_busy_is_execution_failure_with_suppressed_details(self):
        result, report = invoke_fake(self.workspace, 'busy')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['exit_code'], 75)
        self.assertTrue(report['job_failed'])
        self.assertNotIn('answer', report)
        self.assertNotIn(b'PRIVATE_DIAGNOSTIC_SENTINEL', result.stdout + result.stderr)
        self.assertEqual(report['cleanup_errors'], [])
        self.assertIn('NotImplementedError', (self.workspace / 'calc.py').read_text())

    def test_completed_report_cannot_replace_independent_tests(self):
        result, report = invoke_fake(self.workspace, 'bad_implementation')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['status'], 'completed')
        self.assertIn('tests pass', report['answer'])
        self.assertNotEqual(self.verify().returncode, 0)

    def test_timeout_tree_stopped_before_next_writer(self):
        result, report = invoke_fake(self.workspace, 'timeout', timeout=2)
        self.assertEqual(result.returncode, 124)
        self.assertEqual(report['status'], 'timeout')
        self.assertFalse(report['output_capture_complete'])
        self.assertEqual(report['cleanup_errors'], [])
        for name in ('worker.pid', 'child.pid'):
            self.assertFalse(process_alive(int((self.workspace / name).read_text())))
        heartbeat = (self.workspace / 'heartbeat.txt').read_bytes()
        time.sleep(0.15)
        self.assertEqual((self.workspace / 'heartbeat.txt').read_bytes(), heartbeat)
        # Only after observing process exit may the fallback owner write.
        (self.workspace / 'calc.py').write_text('def add(a, b):\n    return a + b\n')
        self.assertEqual(self.verify().returncode, 0)


if __name__ == '__main__':
    unittest.main()
