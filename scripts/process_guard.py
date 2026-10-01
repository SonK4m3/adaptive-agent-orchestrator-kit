"""Own process trees; Windows jobs kill descendants even after parent exit.

No daemon/tool sessions outside the owned OS tree are covered.
"""
import os
import signal
import subprocess


class ProcessGuard:
    def __init__(self):
        self.job = None
        self.pid = None
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.ctypes = ctypes
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
            self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]

            class Basic(ctypes.Structure):
                _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                            ('flags', wintypes.DWORD), ('min_working', ctypes.c_size_t),
                            ('max_working', ctypes.c_size_t), ('active_limit', wintypes.DWORD),
                            ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                            ('scheduling', wintypes.DWORD)]

            class IO(ctypes.Structure):
                _fields_ = [(name, ctypes.c_uint64) for name in
                            ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]

            class Extended(ctypes.Structure):
                _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                            ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                            ('peak_job', ctypes.c_size_t)]

            self.job = self.kernel.CreateJobObjectW(None, None)
            if not self.job:
                raise OSError('Cannot create private process job')
            limit = Extended()
            limit.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limit), ctypes.sizeof(limit)):
                self.close()
                raise OSError('Cannot contain process job')

    def attach(self, proc):
        self.pid = proc.pid
        if os.name == 'nt':
            if not self.kernel.AssignProcessToJobObject(self.job, int(proc._handle)):
                raise OSError('Cannot assign child to private job')
            # Child is created suspended, so it cannot escape before assignment.
            ntdll = self.ctypes.WinDLL('ntdll')
            ntdll.NtResumeProcess.argtypes = [self.ctypes.c_void_p]
            ntdll.NtResumeProcess.restype = self.ctypes.c_long
            if ntdll.NtResumeProcess(int(proc._handle)) != 0:
                raise OSError('Cannot resume contained child')

    def close(self):
        if os.name == 'nt' and self.job:
            result = self.kernel.CloseHandle(self.job)
            self.job = None
            if not result:
                raise OSError('Cannot close process job')
        elif os.name != 'nt' and self.pid:
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.pid = None


def spawn_process(command, **kwargs):
    guard = ProcessGuard()
    if os.name == 'nt':
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | 0x4  # CREATE_SUSPENDED
    else:
        kwargs['start_new_session'] = True
    proc = None
    try:
        proc = subprocess.Popen(command, **kwargs)
        guard.attach(proc)
        return proc, guard
    except BaseException:
        if proc is not None:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        guard.close()
        raise
