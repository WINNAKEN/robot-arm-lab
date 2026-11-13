"""Narrow Win32 handles for 109. Importing this module performs no OS calls.

No clock retry, privilege-policy change, breakaway, or alternate launcher exists.
The controller must supply all authority/lifecycle checks in admission_guard.
"""
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import math
from pathlib import Path
import time

SYNCHRONIZE = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_SET_QUOTA, PROCESS_TERMINATE = 0x100, 0x1
JOB_OBJECT_ASSIGN_PROCESS = 0x0001
JOB_OBJECT_QUERY = 0x0004
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
HANDLE_FLAG_INHERIT = 1
WAIT_OBJECT_0, WAIT_TIMEOUT, WAIT_FAILED = 0, 258, 0xFFFFFFFF
ERROR_ALREADY_EXISTS = 183
SEE_MASK_NOCLOSEPROCESS, SEE_MASK_NOASYNC, SEE_MASK_FLAG_NO_UI = 0x40, 0x100, 0x400
MAX_SHIFT_NS = 5_000_000_000
DISPATCH_MARGIN_NS = 50_000_000
MAX_TARGET_AGE_NS = 20_000_000
MAX_TARGET_COHERENCE_ERROR_NS = 5_000_000


class FILETIME(C.Structure):
    _fields_ = [('low', W.DWORD), ('high', W.DWORD)]


class SYSTEMTIME(C.Structure):
    _fields_ = [(n, W.WORD) for n in ('year', 'month', 'day_of_week', 'day',
                                      'hour', 'minute', 'second', 'milliseconds')]


class BASIC_LIMIT(C.Structure):
    _fields_ = [('PerProcessUserTimeLimit', C.c_longlong),
                ('PerJobUserTimeLimit', C.c_longlong), ('LimitFlags', W.DWORD),
                ('MinimumWorkingSetSize', C.c_size_t), ('MaximumWorkingSetSize', C.c_size_t),
                ('ActiveProcessLimit', W.DWORD), ('Affinity', C.c_size_t),
                ('PriorityClass', W.DWORD), ('SchedulingClass', W.DWORD)]


class IO_COUNTERS(C.Structure):
    _fields_ = [(n, C.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount',
                                           'OtherOperationCount', 'ReadTransferCount',
                                           'WriteTransferCount', 'OtherTransferCount')]


class EXTENDED_LIMIT(C.Structure):
    _fields_ = [('BasicLimitInformation', BASIC_LIMIT), ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', C.c_size_t), ('JobMemoryLimit', C.c_size_t),
                ('PeakProcessMemoryUsed', C.c_size_t), ('PeakJobMemoryUsed', C.c_size_t)]


class ACCOUNTING(C.Structure):
    _fields_ = [(n, C.c_longlong) for n in ('TotalUserTime', 'TotalKernelTime',
                                          'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')] + [
        (n, W.DWORD) for n in ('TotalPageFaultCount', 'TotalProcesses',
                              'ActiveProcesses', 'TotalTerminatedProcesses')]


class SHELLEXECUTEINFO(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('fMask', W.ULONG), ('hwnd', W.HWND),
                ('lpVerb', W.LPCWSTR), ('lpFile', W.LPCWSTR), ('lpParameters', W.LPCWSTR),
                ('lpDirectory', W.LPCWSTR), ('nShow', C.c_int), ('hInstApp', W.HINSTANCE),
                ('lpIDList', C.c_void_p), ('lpClass', W.LPCWSTR), ('hkeyClass', W.HKEY),
                ('dwHotKey', W.DWORD), ('hIcon', W.HANDLE), ('hProcess', W.HANDLE)]


class _Native:
    """ctypes signatures; instantiated lazily, replaceable by HOST fake DLLs."""
    def __init__(self):
        kernel = C.WinDLL('kernel32', use_last_error=True)
        shell = C.WinDLL('shell32', use_last_error=True)
        ole = C.WinDLL('ole32', use_last_error=True)
        signatures = {
            'GetTickCount64': (kernel, [], C.c_ulonglong),
            'GetCurrentProcessId': (kernel, [], W.DWORD),
            'GetCurrentProcess': (kernel, [], W.HANDLE),
            'OpenProcess': (kernel, [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            'GetProcessId': (kernel, [W.HANDLE], W.DWORD),
            'GetProcessTimes': (kernel, [W.HANDLE] + [C.POINTER(FILETIME)] * 4, W.BOOL),
            'WaitForSingleObject': (kernel, [W.HANDLE, W.DWORD], W.DWORD),
            'CloseHandle': (kernel, [W.HANDLE], W.BOOL),
            'SetHandleInformation': (kernel, [W.HANDLE, W.DWORD, W.DWORD], W.BOOL),
            'GetHandleInformation': (kernel, [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
            'CreateJobObjectW': (kernel, [C.c_void_p, W.LPCWSTR], W.HANDLE),
            'OpenJobObjectW': (kernel, [W.DWORD, W.BOOL, W.LPCWSTR], W.HANDLE),
            'SetInformationJobObject': (kernel, [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            'QueryInformationJobObject': (kernel, [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
            'AssignProcessToJobObject': (kernel, [W.HANDLE, W.HANDLE], W.BOOL),
            'IsProcessInJob': (kernel, [W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
            'TerminateJobObject': (kernel, [W.HANDLE, W.UINT], W.BOOL),
            'TerminateProcess': (kernel, [W.HANDLE, W.UINT], W.BOOL),
            'SetSystemTime': (kernel, [C.POINTER(SYSTEMTIME)], W.BOOL),
            'ShellExecuteExW': (shell, [C.POINTER(SHELLEXECUTEINFO)], W.BOOL),
            'CoInitializeEx': (ole, [C.c_void_p, W.DWORD], C.c_long),
            'CoUninitialize': (ole, [], None),
        }
        for name, (dll, args, result) in signatures.items():
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result
            setattr(self, name, function)
        self.get_last_error, self.set_last_error = C.get_last_error, C.set_last_error


_api = None


def _get_api():
    global _api
    if _api is None:
        _api = _Native()
    return _api


def _need(value, reason):
    if not value:
        raise ValueError(reason)


def _error(api, operation):
    code = int(api.get_last_error())
    error = OSError(code, operation + ' failed (Win32 ' + str(code) + ')')
    error.winerror = code
    raise error


def _check(api, value, operation):
    if not value:
        _error(api, operation)


def _noninherit(api, handle):
    _check(api, api.SetHandleInformation(handle, HANDLE_FLAG_INHERIT, 0), 'SetHandleInformation')
    flags = W.DWORD()
    _check(api, api.GetHandleInformation(handle, C.byref(flags)), 'GetHandleInformation')
    _need(not flags.value & HANDLE_FLAG_INHERIT, 'Kernel handle must be non-inheritable')


def _created(api, handle):
    created, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    _check(api, api.GetProcessTimes(handle, C.byref(created), C.byref(exited),
                                   C.byref(kernel), C.byref(user)), 'GetProcessTimes')
    value = (int(created.high) << 32) | int(created.low)
    _need(value > 0, 'Nonzero kernel process creation FILETIME')
    return value


def tick_ms():
    """Same-boot monotonic witness; never derives boot identity from UTC."""
    return int(_get_api().GetTickCount64())


def current_identity():
    api = _get_api()
    pid = int(api.GetCurrentProcessId())
    _need(pid > 0, 'Current process PID')
    return {'pid': pid, 'created_filetime': _created(api, api.GetCurrentProcess())}


class Process:
    def __init__(self, handle, api, expected_created=None, expected_pid=None):
        self._handle, self._api = handle, api
        try:
            _need(bool(handle), 'Non-null process handle')
            _noninherit(api, handle)
            self.pid = int(api.GetProcessId(handle))
            _check(api, self.pid, 'GetProcessId')
            self.created_filetime = _created(api, handle)
            if expected_pid is not None:
                _need(self.pid == expected_pid, 'Pinned process PID mismatch')
            if expected_created is not None:
                _need(type(expected_created) is int and expected_created > 0,
                      'Typed expected process creation FILETIME')
                _need(self.created_filetime == expected_created, 'Pinned process creation mismatch')
        except Exception:
            if handle:
                self.close()
            raise

    @classmethod
    def open(cls, pid, expected_created=None):
        _need(type(pid) is int and 0 < pid <= 0xFFFFFFFF, 'Typed process PID')
        api = _get_api()
        handle = api.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        _check(api, handle, 'OpenProcess')
        return cls(handle, api, expected_created, pid)

    def _live_handle(self):
        _need(bool(self._handle), 'Process handle is closed')
        return self._handle

    def wait(self, ms):
        _need(type(ms) is int and 0 <= ms < 0xFFFFFFFF, 'Finite DWORD wait milliseconds')
        result = int(self._api.WaitForSingleObject(self._live_handle(), ms))
        if result == WAIT_OBJECT_0:
            return True
        if result == WAIT_TIMEOUT:
            return False
        if result == WAIT_FAILED:
            _error(self._api, 'WaitForSingleObject')
        raise OSError('Unexpected process wait result ' + str(result))

    def alive(self):
        return not self.wait(0)

    def close(self):
        if self._handle:
            _check(self._api, self._api.CloseHandle(self._handle), 'CloseHandle(process)')
            self._handle = None


def _job_name(name):
    _need(type(name) is str and name.startswith('Local\\') and 6 < len(name) < 260
          and '\x00' not in name and '\\' not in name[6:], 'Owned nonempty Local job name')


class Job:
    def __init__(self, handle, name, api):
        self._handle, self.name, self._api = handle, name, api

    @classmethod
    def create(cls, name):
        _job_name(name)
        api = _get_api()
        api.set_last_error(0)
        handle = api.CreateJobObjectW(None, name)
        error = int(api.get_last_error())
        _check(api, handle, 'CreateJobObjectW')
        job = cls(handle, name, api)
        try:
            _need(error != ERROR_ALREADY_EXISTS, 'Named job already exists')
            _noninherit(api, handle)
            limits = EXTENDED_LIMIT()
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            _check(api, api.SetInformationJobObject(handle, 9, C.byref(limits), C.sizeof(limits)),
                   'SetInformationJobObject')
            job._verify_limits()
            _need(job.active_count() == 0, 'New job must have zero active processes')
            return job
        except Exception:
            job.close()
            raise

    def _live_handle(self):
        _need(bool(self._handle), 'Job handle is closed')
        return self._handle

    def _verify_limits(self):
        limits = EXTENDED_LIMIT()
        _check(self._api, self._api.QueryInformationJobObject(self._live_handle(), 9,
               C.byref(limits), C.sizeof(limits), None), 'QueryInformationJobObject(limits)')
        _need(limits.BasicLimitInformation.LimitFlags == JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
              'Exact kill-on-close job limits; no breakaway policy')

    @classmethod
    def attach_self_and_close(cls, name):
        """Worker opens the existing nonce job; never creates/falls back to one."""
        _job_name(name)
        api = _get_api()
        handle = api.OpenJobObjectW(JOB_OBJECT_ASSIGN_PROCESS | JOB_OBJECT_QUERY, False, name)
        _check(api, handle, 'OpenJobObjectW')
        job = cls(handle, name, api)
        try:
            _noninherit(api, handle)
            job._verify_limits()
            process = api.GetCurrentProcess()
            _check(api, api.AssignProcessToJobObject(handle, process), 'AssignProcessToJobObject(self)')
            contained = W.BOOL()
            _check(api, api.IsProcessInJob(process, handle, C.byref(contained)), 'IsProcessInJob(self)')
            _need(contained.value != 0, 'Worker not contained in pinned job')
            identity, tick = current_identity(), tick_ms()
        finally:
            job.close()
        return {'job_name': name, 'assigned': True, 'worker_job_handle_closed': True,
                'worker_identity': identity, 'tick_ms': tick, 'kill_on_job_close': True}

    def contains(self, process_or_pid):
        owned = type(process_or_pid) is int
        process = Process.open(process_or_pid) if owned else process_or_pid
        _need(isinstance(process, Process), 'Pinned Process or typed PID required')
        try:
            result = W.BOOL()
            _check(self._api, self._api.IsProcessInJob(process._live_handle(), self._live_handle(),
                   C.byref(result)), 'IsProcessInJob')
            return result.value != 0
        finally:
            if owned:
                process.close()

    def active_count(self):
        accounting = ACCOUNTING()
        _check(self._api, self._api.QueryInformationJobObject(self._live_handle(), 1,
               C.byref(accounting), C.sizeof(accounting), None), 'QueryInformationJobObject(active)')
        return int(accounting.ActiveProcesses)

    def assign_process(self, process_or_pid):
        """Contain a caller-owned child, verifying its pinned kernel identity.

        This never enumerates/selects another process or enables breakaway.
        The controller owns child creation and supplies that child only.
        """
        owned = type(process_or_pid) is int
        process = Process.open(process_or_pid) if owned else process_or_pid
        _need(isinstance(process, Process), 'Pinned owned child Process or PID required')
        assignment = None
        try:
            _need(process.alive(), 'Cannot assign a terminal child')
            api = self._api
            rights = SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA | PROCESS_TERMINATE
            handle = api.OpenProcess(rights, False, process.pid)
            _check(api, handle, 'OpenProcess(assign owned child)')
            assignment = Process(handle, api, process.created_filetime, process.pid)
            _check(api, api.AssignProcessToJobObject(self._live_handle(), assignment._live_handle()),
                   'AssignProcessToJobObject(owned child)')
            _need(self.contains(assignment), 'Assigned child not contained in pinned job')
            return True
        finally:
            if assignment is not None:
                assignment.close()
            if owned:
                process.close()

    def terminate(self):
        _check(self._api, self._api.TerminateJobObject(self._live_handle(), 1), 'TerminateJobObject')

    def close(self):
        if self._handle:
            _check(self._api, self._api.CloseHandle(self._handle), 'CloseHandle(job)')
            self._handle = None


def launch_elevated(exe, arguments):
    """One runas request. Caller must supervise this blocking call on another thread."""
    _need(type(exe) is str and Path(exe).is_absolute() and '\x00' not in exe, 'Absolute executable')
    _need(type(arguments) is str and '\x00' not in arguments, 'Exact argument string')
    api = _get_api()
    hr = int(api.CoInitializeEx(None, 0x2 | 0x4))  # STA | DISABLE_OLE1DDE
    _need(hr in (0, 1), 'COM STA initialization failed: ' + str(hr))
    try:
        info = SHELLEXECUTEINFO()
        info.cbSize = C.sizeof(info)
        info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI
        info.lpVerb, info.lpFile, info.lpParameters, info.nShow = 'runas', exe, arguments, 0
        _check(api, api.ShellExecuteExW(C.byref(info)), 'ShellExecuteExW(runas)')
        _need(bool(info.hProcess), 'UAC launch returned no pinned process handle')
        return Process(info.hProcess, api)
    finally:
        api.CoUninitialize()


def set_utc_unix(target, admission_guard):
    """Legacy absolute raw adapter, retained for historical HOST coverage only.

    Production worker uses adjust_utc_once; this function does not bound target age.

    SetSystemTime itself enables/disables SE_SYSTEMTIME_NAME on the calling process:
    https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-setsystemtime
    No AdjustTokenPrivileges or alternate clock setter is used here.
    """
    _need(type(target) in (int, float) and math.isfinite(target), 'Finite typed UTC target')
    _need(callable(admission_guard), 'Admission callback required')
    milliseconds = math.floor(target * 1000)
    stamp = datetime.fromtimestamp(milliseconds / 1000, timezone.utc)
    _need(stamp.year >= 1601, 'SYSTEMTIME supported year')
    system = SYSTEMTIME(stamp.year, stamp.month, (stamp.weekday() + 1) % 7, stamp.day,
                        stamp.hour, stamp.minute, stamp.second, milliseconds % 1000)
    api = _get_api()
    before_utc_ns, before_tick = time.time_ns(), tick_ms()
    api.set_last_error(0)
    if admission_guard() is not True:
        raise PermissionError('Immediate clock admission denied')
    returned = int(api.SetSystemTime(C.byref(system)))
    error = int(api.get_last_error())
    after_tick, after_utc_ns = tick_ms(), time.time_ns()
    return {'api': 'SetSystemTime', 'called': True, 'ok': returned != 0,
            'return_value': returned, 'winerror': error, 'target_unix_ms': milliseconds,
            'systemtime_utc': {name: int(getattr(system, name)) for name, _ in SYSTEMTIME._fields_},
            'before_utc_ns': before_utc_ns, 'after_utc_ns': after_utc_ns,
            'before_tick_ms': before_tick, 'after_tick_ms': after_tick,
            'retry_count': 0, 'rollback_attempted': False}


def adjust_utc_once(delta, admission_guard):
    """Fresh relative operand after admission, one synchronous SetSystemTime call.

    The last userspace observation is bounded and saved, not an atomic proof of
    kernel-entry scheduling. The 50ms dispatch margin tightens the original 5s cap.
    No caller callback runs after fixing the target; no retries or rollback exist.
    """
    _need(type(delta) in (int, float) and math.isfinite(delta) and abs(delta) <= 5,
          'Finite relative correction within original five-second authority')
    _need(callable(admission_guard), 'Admission callback required')
    delta_ns = round(delta * 1_000_000_000)
    api = _get_api()
    setter = api.SetSystemTime
    if admission_guard() is not True:
        raise PermissionError('Immediate relative clock admission denied')
    # All potentially arbitrary admission work is complete before the UTC anchor.
    api.set_last_error(0)
    before_tick = tick_ms()
    origin_mono_ns = time.monotonic_ns()
    origin_utc_ns = time.time_ns()
    milliseconds = (origin_utc_ns + delta_ns) // 1_000_000
    stamp = datetime.fromtimestamp(milliseconds // 1000, timezone.utc)
    _need(stamp.year >= 1601, 'SYSTEMTIME supported year')
    system = SYSTEMTIME(stamp.year, stamp.month, (stamp.weekday() + 1) % 7, stamp.day,
                        stamp.hour, stamp.minute, stamp.second, milliseconds % 1000)
    operand = C.byref(system)
    check_mono_ns = time.monotonic_ns()
    check_utc_ns = time.time_ns()
    age_ns = check_mono_ns - origin_mono_ns
    coherence_ns = (check_utc_ns - origin_utc_ns) - age_ns
    shift_ns = milliseconds * 1_000_000 - check_utc_ns
    _need(0 <= age_ns <= MAX_TARGET_AGE_NS, 'Clock target aged before API')
    _need(abs(coherence_ns) <= MAX_TARGET_COHERENCE_ERROR_NS,
          'Local wall changed while constructing clock operand')
    _need(abs(shift_ns) <= MAX_SHIFT_NS - DISPATCH_MARGIN_NS,
          'Actual pre-call shift exceeds conservative five-second boundary')
    returned = int(setter(operand))
    error = int(api.get_last_error())
    after_tick, after_utc_ns = tick_ms(), time.time_ns()
    return {'api': 'SetSystemTime', 'mode': 'RELATIVE_FRESH_AFTER_GUARD',
            'called': True, 'ok': returned != 0, 'return_value': returned,
            'winerror': error, 'requested_delta_s': float(delta),
            'target_unix_ms': milliseconds,
            'systemtime_utc': {name: int(getattr(system, name)) for name, _ in SYSTEMTIME._fields_},
            'target_created_utc_ns': origin_utc_ns, 'target_created_monotonic_ns': origin_mono_ns,
            'before_utc_ns': check_utc_ns, 'after_utc_ns': after_utc_ns,
            'before_tick_ms': before_tick, 'after_tick_ms': after_tick,
            'target_age_ns': age_ns, 'target_age_limit_ns': MAX_TARGET_AGE_NS,
            'wall_monotonic_error_ns': coherence_ns, 'observed_pre_call_shift_ns': shift_ns,
            'dispatch_margin_ns': DISPATCH_MARGIN_NS,
            'boundary_scope': 'LAST_USERSPACE_OBSERVATION_NOT_ATOMIC_KERNEL_ENTRY_PROOF',
            'retry_count': 0, 'rollback_attempted': False}


def terminate_current(exit_code=124):
    """Direct self-process hard fence. Caller always uses os._exit in finally.

    No process lookup, Job close, diagnostic, stderr, or file operation precedes it.
    A return (success or failure) is not a terminal proof; caller fallback is required.
    """
    _need(type(exit_code) is int and 0 <= exit_code <= 0xFFFFFFFF, 'Typed self exit code')
    api = _get_api()
    return bool(api.TerminateProcess(api.GetCurrentProcess(), exit_code))
