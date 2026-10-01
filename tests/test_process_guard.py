"""Offline process containment: no model, credentials or user processes involved."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from process_guard import spawn_process


class ProcessGuardTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows job live check; POSIX covered by mocked group tests')
    def test_job_close_kills_descendant_after_normal_parent_exit(self):
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        child_handle = None
        with tempfile.TemporaryDirectory() as directory:
            code = "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid,flush=True)"
            env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'PATH') if key in os.environ}
            proc, guard = spawn_process([sys.executable, '-I', '-c', code], cwd=directory,
                                        env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            try:
                proc.wait(timeout=3)
                pid = int(proc.stdout.read().strip())
                child_handle = kernel.OpenProcess(0x100000, False, pid)
                self.assertTrue(child_handle)
                self.assertEqual(kernel.WaitForSingleObject(child_handle, 0), 258)  # still running
                guard.close()
                self.assertEqual(kernel.WaitForSingleObject(child_handle, 2000), 0)
            finally:
                guard.close()
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)
                proc.stdout.close()
                if child_handle:
                    kernel.CloseHandle(child_handle)


if __name__ == '__main__':
    unittest.main()
