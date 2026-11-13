"""Bounded, creation-time Windows Job ownership; no PID-based termination."""
import ctypes as C
from ctypes import wintypes as W
import math
import os
from pathlib import Path
import subprocess
import threading
import time


def _die():
    try:
        k = C.WinDLL('kernel32', use_last_error=True)
        k.GetCurrentProcess.restype = W.HANDLE
        k.TerminateProcess.argtypes = [W.HANDLE, W.UINT]
        k.TerminateProcess(k.GetCurrentProcess(), 124)
    finally:
        os._exit(124)


class Fence:
    def __init__(self, deadline_monotonic):
        if isinstance(deadline_monotonic, bool) or not math.isfinite(deadline_monotonic):
            raise ValueError('finite absolute deadline required')
        self.deadline = deadline_monotonic
        self.stop = threading.Event()
        self.armed = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.started = self.closed = False

    def _watch(self):
        try:
            self.armed.set()
            if not self.stop.wait(max(0, self.deadline - time.monotonic())):
                _die()
        except BaseException:
            _die()

    def __enter__(self):
        if self.started:
            raise RuntimeError('fence already started')
        self.thread.start()
        self.started = True
        if not self.armed.wait(max(0, min(1, self.deadline - time.monotonic()))):
            _die()
        if not self.thread.is_alive() or time.monotonic() >= self.deadline:
            _die()
        return self

    def close(self):
        if self.closed:
            return
        if not self.started or not self.armed.is_set():
            raise RuntimeError('unarmed fence')
        if time.monotonic() >= self.deadline:
            _die()
        self.stop.set()
        self.thread.join(max(0, self.deadline - time.monotonic()))
        if self.thread.is_alive() or time.monotonic() >= self.deadline:
            _die()
        self.closed = True

    def __exit__(self, *_):
        self.close()


class _Limits(C.Structure):
    _fields_ = [('per_process', C.c_longlong), ('per_job', C.c_longlong),
                ('flags', W.DWORD), ('min_ws', C.c_size_t), ('max_ws', C.c_size_t),
                ('active', W.DWORD), ('affinity', C.c_size_t),
                ('priority', W.DWORD), ('scheduling', W.DWORD)]


class _IO(C.Structure):
    _fields_ = [(n, C.c_ulonglong) for n in
                ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class _Extended(C.Structure):
    _fields_ = [('basic', _Limits), ('io', _IO), ('process_mem', C.c_size_t),
                ('job_mem', C.c_size_t), ('peak_process', C.c_size_t), ('peak_job', C.c_size_t)]


class _Accounting(C.Structure):
    _fields_ = [(n, C.c_longlong) for n in ('user', 'kernel', 'period_user', 'period_kernel')]
    _fields_ += [(n, W.DWORD) for n in ('faults', 'total', 'active', 'terminated')]


class _Startup(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR),
                ('title', W.LPWSTR)]
    _fields_ += [(n, W.DWORD) for n in
                ('x', 'y', 'xs', 'ys', 'xc', 'yc', 'fill', 'flags')]
    _fields_ += [('show', W.WORD), ('reserved_size', W.WORD), ('reserved_ptr', C.c_void_p),
                ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]


class _StartupEx(C.Structure):
    _fields_ = [('si', _Startup), ('attributes', C.c_void_p)]


class _Process(C.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE),
                ('pid', W.DWORD), ('tid', W.DWORD)]


class SpawnFailed(OSError):
    """CreateProcess returned FALSE: no successful creation to reap."""


class Kernel:
    def __init__(self):
        self.k = C.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': (W.HANDLE, [C.c_void_p, W.LPCWSTR]),
            'SetInformationJobObject': (W.BOOL, [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]),
            'QueryInformationJobObject': (W.BOOL, [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p]),
            'InitializeProcThreadAttributeList': (W.BOOL, [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)]),
            'UpdateProcThreadAttribute': (W.BOOL, [C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p]),
            'DeleteProcThreadAttributeList': (None, [C.c_void_p]),
            'CreateProcessW': (W.BOOL, [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.c_void_p, C.POINTER(_Process)]),
            'IsProcessInJob': (W.BOOL, [W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)]),
            'GetProcessTimes': (W.BOOL, [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4),
            'ResumeThread': (W.DWORD, [W.HANDLE]),
            'WaitForSingleObject': (W.DWORD, [W.HANDLE, W.DWORD]),
            'GetExitCodeProcess': (W.BOOL, [W.HANDLE, C.POINTER(W.DWORD)]),
            'TerminateJobObject': (W.BOOL, [W.HANDLE, W.UINT]),
            'CloseHandle': (W.BOOL, [W.HANDLE]),
        }
        for name, (restype, argtypes) in signatures.items():
            f = getattr(self.k, name)
            f.restype, f.argtypes = restype, argtypes

    @staticmethod
    def check(ok):
        if not ok:
            raise C.WinError(C.get_last_error())

    def job(self):
        job = self.k.CreateJobObjectW(None, None)
        self.check(job)
        try:
            limits = _Extended()
            limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE, no breakaway
            self.check(self.k.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
            return job
        except BaseException:
            try:
                self.close(job)
            except BaseException:
                _die()
            raise

    def create(self, argv, job, streams):
        import msvcrt
        handles = (W.HANDLE * 3)(*[msvcrt.get_osfhandle(s.fileno()) for s in streams])
        jobs = (W.HANDLE * 1)(job)
        size = C.c_size_t()
        self.k.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
        if not size.value:
            raise SpawnFailed('attribute size unavailable before creation')
        attributes = C.create_string_buffer(size.value)
        self.check(self.k.InitializeProcThreadAttributeList(attributes, 2, 0, C.byref(size)))
        try:
            self.check(self.k.UpdateProcThreadAttribute(attributes, 0, 0x20002,
                       handles, C.sizeof(handles), None, None))
            self.check(self.k.UpdateProcThreadAttribute(attributes, 0, 0x2000D,
                       jobs, C.sizeof(jobs), None, None))
            si = _StartupEx()
            si.si.cb, si.si.flags = C.sizeof(si), 0x100
            si.si.stdin, si.si.stdout, si.si.stderr = handles
            si.attributes = C.cast(attributes, C.c_void_p)
            pi = _Process()
            command = C.create_unicode_buffer(subprocess.list2cmdline(argv))
            ok = self.k.CreateProcessW(argv[0], command, None, None, True,
                                      0x80000 | 0x4 | 0x8000000, None, None,
                                      C.byref(si), C.byref(pi))
            if not ok:
                raise SpawnFailed(C.get_last_error(), 'CreateProcessW returned FALSE')
            return pi
        finally:
            self.k.DeleteProcThreadAttributeList(attributes)

    def identity(self, process, job):
        inside = W.BOOL()
        self.check(self.k.IsProcessInJob(process, job, C.byref(inside)))
        if not inside.value:
            raise RuntimeError('child outside creation-time job')
        times = [W.FILETIME() for _ in range(4)]
        self.check(self.k.GetProcessTimes(process, *[C.byref(t) for t in times]))
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime

    def resume(self, thread):
        previous = self.k.ResumeThread(thread)
        if previous != 1:
            raise RuntimeError('ResumeThread did not observe exactly one suspension: %s' % previous)

    def wait(self, process, seconds):
        result = self.k.WaitForSingleObject(process, max(0, min(0xFFFFFFFE, math.ceil(seconds * 1000))))
        if result not in (0, 258):
            raise C.WinError(C.get_last_error())
        return result == 0

    def exit_code(self, process):
        code = W.DWORD()
        self.check(self.k.GetExitCodeProcess(process, C.byref(code)))
        return code.value

    def active(self, job):
        value = _Accounting()
        self.check(self.k.QueryInformationJobObject(job, 1, C.byref(value), C.sizeof(value), None))
        return value.active

    def terminate(self, job):
        self.check(self.k.TerminateJobObject(job, 124))

    def close(self, handle):
        self.check(self.k.CloseHandle(handle))


def _safe_path(value, directory=False):
    p = Path(value)
    if not p.is_absolute() or str(p).startswith(('\\\\', '//')) or '..' in p.parts:
        raise ValueError('absolute local path required')
    if any(':' in part for part in p.parts[1:]):
        raise ValueError('alternate stream path rejected')
    if any(part.endswith((' ', '.')) for part in p.parts[1:]):
        raise ValueError('ambiguous Windows path rejected')
    for part in [*reversed(p.parents), p]:
        info = part.lstat()
        if info.st_file_attributes & 0x400:
            raise ValueError('reparse path rejected: %s' % part)
    if directory and not p.is_dir():
        raise ValueError('existing output directory required')
    if not directory and not p.is_file():
        raise ValueError('existing regular file required')
    return p


def _capture(out, stdin_path, input_sender):
    streams = []
    sender = None
    try:
        for name in ('stdout.txt', 'stderr.txt'):
            streams.append(open(out / name, 'xb', buffering=0))
        if input_sender is not None:
            rd, wr = os.pipe()
            try:
                sender = os.fdopen(wr, 'wb', buffering=0)
                child_in = os.fdopen(rd, 'rb', buffering=0)
            except BaseException:
                os.close(rd)
                if sender is None:
                    os.close(wr)
                raise
        else:
            child_in = open(_safe_path(stdin_path) if stdin_path is not None else 'NUL', 'rb', buffering=0)
        streams.append(child_in)
        for stream in streams:
            os.set_inheritable(stream.fileno(), True)
        return streams, sender
    except BaseException:
        for stream in streams:
            try:
                stream.close()
            except BaseException:
                _die()
        if sender is not None:
            try:
                sender.close()
            except BaseException:
                _die()
        raise


def run(argv, out, timeout_s, *, cleanup_s=2, admit=None, stdin_path=None, input_sender=None):
    if (not isinstance(argv, (list, tuple)) or not argv or
            any(not isinstance(a, str) or '\0' in a for a in argv)):
        raise ValueError('nonempty string argv required')
    for value in (timeout_s, cleanup_s):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('positive finite timeout and cleanup required')
    if stdin_path is not None and input_sender is not None:
        raise ValueError('stdin_path and input_sender are exclusive')
    t0 = time.monotonic()
    work_end, end = t0 + timeout_s, t0 + timeout_s + cleanup_s
    fence = Fence(end).__enter__()
    record = dict(child_pid=None, actual_child_exit_code=None, policy_exit_code=125,
                  policy_basis='NOT_CREATED', timed_out=False, child_state='NOT_CREATED',
                  terminal=False, job_active_after=None, raw_complete=False, errors=[])
    kernel = job = pi = sender = None
    streams = []
    creation_unknown = False
    signal = False

    def error(stage, exc):
        try:
            record['errors'].append('%s: %s: %s' % (stage, type(exc).__name__, exc))
        except BaseException:
            _die()

    try:
        if admit is not None:
            admit()
        out = _safe_path(out, directory=True)
        exe = _safe_path(argv[0])
        if exe.suffix.lower() != '.exe':
            raise ValueError('absolute executable .exe required')
        streams, sender = _capture(out, stdin_path, input_sender)
        kernel = Kernel()
        job = kernel.job()
        if time.monotonic() >= work_end:
            record['timed_out'] = True
            raise TimeoutError('work deadline before creation')
        creation_unknown = True
        try:
            pi = kernel.create(argv, job, [streams[2], streams[0], streams[1]])
        except SpawnFailed:
            creation_unknown = False
            raise
        creation_unknown = False
        record['child_pid'] = pi.pid
        record['child_state'] = 'SUSPENDED'
        record['child_creation_time'] = kernel.identity(pi.process, job)
        if time.monotonic() >= work_end:
            record['timed_out'] = True
        else:
            kernel.resume(pi.thread)
            record['child_state'] = 'RUNNING'
            streams[2].close()
            if input_sender is not None:
                input_sender(sender, out / 'stdout.txt', work_end)
                sender.close()
                sender = None
            signal = kernel.wait(pi.process, max(0, work_end - time.monotonic()))
            if not signal or time.monotonic() >= work_end:
                record['timed_out'] = True
    except BaseException as exc:
        error('work', exc)
    finally:
        # Unknown creation cannot be cancelled or converted to a terminal receipt.
        if creation_unknown:
            while True:
                time.sleep(.01)
        if pi is not None:
            try:
                if not signal:
                    kernel.terminate(job)
                elif kernel.active(job):
                    kernel.terminate(job)
                while time.monotonic() < end:
                    signal = kernel.wait(pi.process, 0)
                    record['job_active_after'] = kernel.active(job)
                    if signal and record['job_active_after'] == 0:
                        record['actual_child_exit_code'] = kernel.exit_code(pi.process)
                        break
                    time.sleep(min(.01, max(0, end - time.monotonic())))
            except BaseException as exc:
                error('cleanup', exc)
            if not signal or record['job_active_after'] != 0 or record['actual_child_exit_code'] is None:
                while True:
                    time.sleep(.01)
        for stream in [sender, *streams]:
            if stream is not None and not stream.closed:
                try:
                    if stream in streams[:2]:
                        stream.flush()
                        os.fsync(stream.fileno())
                except BaseException as exc:
                    error('capture-sync', exc)
                try:
                    stream.close()
                except BaseException as exc:
                    error('capture-close', exc)
                    while True:
                        time.sleep(.01)
        if kernel is not None:
            for handle in ([pi.thread, pi.process] if pi is not None else []) + ([job] if job else []):
                try:
                    kernel.close(handle)
                except BaseException as exc:
                    error('handle-close', exc)
                    # A failed release must not escape its lifetime owner.
                    while True:
                        time.sleep(.01)
        record['terminal'] = pi is not None and signal and record['job_active_after'] == 0 and not record['errors']
        record['raw_complete'] = record['terminal']
        record['child_state'] = 'REAPED' if record['terminal'] else ('UNKNOWN' if pi else 'NOT_CREATED')
        record['policy_exit_code'] = (124 if record['timed_out'] else
                                      record['actual_child_exit_code'] if record['terminal'] else 125)
        record['policy_basis'] = 'TIMEOUT' if record['timed_out'] else ('CHILD_EXIT' if record['terminal'] else 'ERROR')
        fence.close()
    return record
