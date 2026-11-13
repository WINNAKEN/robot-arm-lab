"""Default fake-DLL HOST suite. --real-probe is explicit, medium, own child only.

The opt-in probe never calls UAC or a time setter; both are hard trapped.
"""
import argparse
import ctypes as C
from datetime import datetime as UTCDateTime, timezone as UTCTimezone
from pathlib import Path
import json
import subprocess
import sys
import threading
import time
import types
import uuid
from unittest.mock import patch


def load_adapter():
    if 'ral109_win32' in sys.modules:
        return sys.modules['ral109_win32']
    path = Path(__file__).with_name('win32.py')
    module = types.ModuleType('ral109_win32')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


w = load_adapter()


class FakeDLL:
    """Only this object receives calls during default HOST execution."""
    def __init__(self):
        self.calls, self.fail = [], set()
        self.error, self.tick, self.created = 0, 1000, 0x123456789ABC
        self.wait_result, self.flags, self.job_flags = w.WAIT_TIMEOUT, 0, w.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self.members, self.active, self.exists = set(), 0, False
        self.com_result, self.shell_handle = 0, 7000
        self.clock_result, self.clock_error = 1, 0
        self.pid_override, self.creation_override = None, None

    def call(self, name, *args):
        self.calls.append((name, *args))
        if name in self.fail:
            self.error = 5
            return False
        return True

    def get_last_error(self):
        return self.error

    def set_last_error(self, value):
        self.calls.append(('set_last_error', value))
        self.error = value

    def GetTickCount64(self):
        self.call('GetTickCount64')
        self.tick += 1
        return self.tick

    def GetCurrentProcessId(self):
        self.call('GetCurrentProcessId')
        return 42

    def GetCurrentProcess(self):
        self.call('GetCurrentProcess')
        return -1

    def OpenProcess(self, access, inherit, pid):
        return 10000 + pid if self.call('OpenProcess', access, inherit, pid) else 0

    def GetProcessId(self, handle):
        self.call('GetProcessId', handle)
        return self.pid_override if self.pid_override is not None else (55 if handle == 7000 else handle - 10000)

    def GetProcessTimes(self, handle, created, exited, kernel, user):
        if not self.call('GetProcessTimes', handle):
            return 0
        value = self.created if self.creation_override is None else self.creation_override
        stamp = C.cast(created, C.POINTER(w.FILETIME)).contents
        stamp.low, stamp.high = value & 0xFFFFFFFF, value >> 32
        return 1

    def SetHandleInformation(self, handle, mask, flags):
        return self.call('SetHandleInformation', handle, mask, flags)

    def GetHandleInformation(self, handle, result):
        if not self.call('GetHandleInformation', handle):
            return 0
        C.cast(result, C.POINTER(w.W.DWORD)).contents.value = self.flags
        return 1

    def WaitForSingleObject(self, handle, ms):
        self.call('WaitForSingleObject', handle, ms)
        return self.wait_result

    def CloseHandle(self, handle):
        return self.call('CloseHandle', handle)

    def CreateJobObjectW(self, security, name):
        if not self.call('CreateJobObjectW', security, name):
            return 0
        self.error = w.ERROR_ALREADY_EXISTS if self.exists else 0
        return 500

    def OpenJobObjectW(self, access, inherit, name):
        return 501 if self.call('OpenJobObjectW', access, inherit, name) else 0

    def SetInformationJobObject(self, handle, kind, value, size):
        if not self.call('SetInformationJobObject', handle, kind, size):
            return 0
        self.job_flags = C.cast(value, C.POINTER(w.EXTENDED_LIMIT)).contents.BasicLimitInformation.LimitFlags
        return 1

    def QueryInformationJobObject(self, handle, kind, value, size, returned):
        if not self.call('QueryInformationJobObject', handle, kind, size):
            return 0
        if kind == 9:
            C.cast(value, C.POINTER(w.EXTENDED_LIMIT)).contents.BasicLimitInformation.LimitFlags = self.job_flags
        elif kind == 1:
            C.cast(value, C.POINTER(w.ACCOUNTING)).contents.ActiveProcesses = self.active
        else:
            raise AssertionError('Unsupported fake query')
        return 1

    def AssignProcessToJobObject(self, job, process):
        if not self.call('AssignProcessToJobObject', job, process):
            return 0
        self.members.add(process)
        self.active += 1
        return 1

    def IsProcessInJob(self, process, job, result):
        if not self.call('IsProcessInJob', process, job):
            return 0
        C.cast(result, C.POINTER(w.W.BOOL)).contents.value = int(process in self.members)
        return 1

    def TerminateJobObject(self, handle, code):
        return self.call('TerminateJobObject', handle, code)

    def TerminateProcess(self, handle, code):
        return self.call('TerminateProcess', handle, code)

    def CoInitializeEx(self, reserved, flags):
        self.call('CoInitializeEx', reserved, flags)
        return self.com_result

    def CoUninitialize(self):
        self.call('CoUninitialize')

    def ShellExecuteExW(self, value):
        info = C.cast(value, C.POINTER(w.SHELLEXECUTEINFO)).contents
        ok = self.call('ShellExecuteExW', info.lpVerb, info.lpFile, info.lpParameters, info.fMask, info.nShow)
        if not ok:
            self.error = 1223
            return 0
        info.hProcess = self.shell_handle
        return 1

    def SetSystemTime(self, value):
        info = C.cast(value, C.POINTER(w.SYSTEMTIME)).contents
        self.call('SetSystemTime', {n: int(getattr(info, n)) for n, _ in w.SYSTEMTIME._fields_})
        self.error = self.clock_error
        return self.clock_result


def host_tests():
    tests = {}

    def yes(name, value):
        assert value, name
        tests[name] = True

    def reject(name, operation):
        try:
            operation()
        except (ValueError, OSError, OverflowError):
            tests[name] = True
        else:
            raise AssertionError(name)

    # Import does not even construct a native DLL adapter.
    with patch.object(C, 'WinDLL', side_effect=AssertionError('NO_DLL_DURING_IMPORT')):
        module = types.ModuleType('cold109');module.__file__ = str(Path(__file__).with_name('win32.py'))
        exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
    yes('import_zero_native_calls', module._api is None)
    yes('ABI_FILETIME8_SYSTEMTIME16', C.sizeof(w.FILETIME) == 8 and C.sizeof(w.SYSTEMTIME) == 16)
    yes('ABI_job_and_shell_layout', C.sizeof(w.EXTENDED_LIMIT) == (144 if C.sizeof(C.c_void_p) == 8 else 112)
        and C.sizeof(w.SHELLEXECUTEINFO) == (112 if C.sizeof(C.c_void_p) == 8 else 60))

    f = FakeDLL()
    with patch.object(w, '_api', f):
        yes('tick_is_int_same_boot_counter', type(w.tick_ms()) is int and w.tick_ms() == 1002)
        yes('identity_kernel_creation_not_boot_epoch', w.current_identity() == {'pid':42,'created_filetime':f.created})
        p = w.Process.open(12, f.created)
        yes('process_open_least_rights_noninherit', ('OpenProcess', w.SYNCHRONIZE | w.PROCESS_QUERY_LIMITED_INFORMATION, False, 12) in f.calls)
        yes('process_pin_fields', p.pid == 12 and p.created_filetime == f.created)
        yes('wait_timeout_is_not_terminal', p.wait(0) is False and p.alive() is True)
        f.wait_result = w.WAIT_OBJECT_0
        yes('wait_signaled_is_terminal', p.wait(200) is True and p.alive() is False)
        f.wait_result = w.WAIT_FAILED
        reject('wait_failed_never_terminal', lambda:p.wait(0))
        f.wait_result = 17
        reject('unexpected_wait_never_terminal', lambda:p.wait(0))
        for name, value in (('bool',True),('negative',-1),('infinite',0xFFFFFFFF),('float',1.0)):
            reject('wait_invalid_'+name, lambda value=value:p.wait(value))
        p.close();p.close()
        yes('process_close_idempotent', f.calls.count(('CloseHandle',10012)) == 1)
        reject('closed_process_cannot_be_alive', p.alive)
        reject('PID_boolean_rejected', lambda:w.Process.open(True))
        reject('PID_zero_rejected', lambda:w.Process.open(0))
        reject('PID_overflow_rejected', lambda:w.Process.open(0x100000000))

    for name, setup, expected in (
        ('creation_mismatch',lambda f:None,123),
        ('creation_boolean',lambda f:None,True),
        ('creation_zero',lambda f:setattr(f,'creation_override',0),None),
        ('wrong_handle_PID',lambda f:setattr(f,'pid_override',999),None),
        ('times_query_failure',lambda f:f.fail.add('GetProcessTimes'),None),
        ('set_noninherit_failure',lambda f:f.fail.add('SetHandleInformation'),None),
        ('get_noninherit_failure',lambda f:f.fail.add('GetHandleInformation'),None),
        ('inherit_bit_stuck',lambda f:setattr(f,'flags',1),None),
    ):
        f = FakeDLL();setup(f)
        with patch.object(w,'_api',f):
            reject('process_'+name,lambda:w.Process.open(12,expected))
        yes('process_'+name+'_handle_closed',('CloseHandle',10012) in f.calls)
    f=FakeDLL();f.fail.add('OpenProcess')
    with patch.object(w,'_api',f):reject('process_access_denied_no_fallback',lambda:w.Process.open(12))
    yes('denied_process_open_once',sum(c[0]=='OpenProcess' for c in f.calls)==1)
    f=FakeDLL()
    with patch.object(w,'_api',f):
        p=w.Process.open(12);f.fail.add('CloseHandle')
        reject('process_close_failure_is_visible',p.close)
        yes('process_close_failure_retains_handle',p._handle==10012)
        f.fail.clear();p.close()

    name='Local\\ral109-'+uuid.uuid4().hex
    f=FakeDLL()
    with patch.object(w,'_api',f):
        job=w.Job.create(name)
        yes('job_exact_kill_on_close',f.job_flags==w.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        yes('job_created_noninherit',('SetHandleInformation',500,1,0) in f.calls)
        yes('job_zero_then_live_query',job.active_count()==0)
        f.active=2;yes('job_active_not_cached',job.active_count()==2)
        p=w.Process.open(12)
        yes('job_not_contains',job.contains(p) is False)
        f.members.add(10012);yes('job_contains_pinned_handle',job.contains(p) is True)
        yes('job_contains_PID_owns_closes_temp',job.contains(12) is True and ('CloseHandle',10012) in f.calls)
        f.members.clear();yes('assign_owned_child_and_verify',job.assign_process(p) is True and job.contains(p))
        yes('assign_child_minimum_additional_rights',('OpenProcess',w.SYNCHRONIZE|w.PROCESS_QUERY_LIMITED_INFORMATION|w.PROCESS_SET_QUOTA|w.PROCESS_TERMINATE,False,12) in f.calls)
        job.terminate();yes('terminate_calls_real_job_once',f.calls.count(('TerminateJobObject',500,1))==1)
        job.close();job.close();yes('job_close_idempotent',f.calls.count(('CloseHandle',500))==1)
        reject('closed_job_cannot_claim_terminal',job.active_count)
        p.close()
    for label,setup in (
        ('already_exists',lambda f:setattr(f,'exists',True)),
        ('set_limits_denied',lambda f:f.fail.add('SetInformationJobObject')),
        ('query_limits_denied',lambda f:f.fail.add('QueryInformationJobObject')),
        ('new_job_nonempty',lambda f:setattr(f,'active',1)),
    ):
        f=FakeDLL();setup(f)
        with patch.object(w,'_api',f):reject('job_'+label,lambda:w.Job.create(name))
        yes('job_'+label+'_handle_closed',('CloseHandle',500) in f.calls)
    f=FakeDLL()
    with patch.object(w,'_api',f):
        for label,bad in (('global','Global\\bad'),('empty','Local\\'),('nested','Local\\a\\b'),('nul','Local\\a\x00')):
            reject('job_name_'+label,lambda bad=bad:w.Job.create(bad))
    yes('bad_job_names_before_API',not f.calls)

    f=FakeDLL()
    with patch.object(w,'_api',f):
        evidence=w.Job.attach_self_and_close(name)
    yes('self_attach_existing_only',('OpenJobObjectW',5,False,name) in f.calls and not any(c[0]=='CreateJobObjectW' for c in f.calls))
    yes('self_attach_uses_current_pseudohandle',('AssignProcessToJobObject',501,-1) in f.calls)
    yes('self_attach_worker_handle_closed',evidence['assigned'] is True and evidence['worker_job_handle_closed'] is True and ('CloseHandle',501) in f.calls)
    yes('self_attach_identity_tick_evidence',evidence['worker_identity']=={'pid':42,'created_filetime':f.created} and type(evidence['tick_ms']) is int)
    for label,setup in (
        ('late_missing_job',lambda f:f.fail.add('OpenJobObjectW')),
        ('nested_assignment_denied',lambda f:f.fail.add('AssignProcessToJobObject')),
        ('containment_query_denied',lambda f:f.fail.add('IsProcessInJob')),
        ('wrong_job_flags',lambda f:setattr(f,'job_flags',0x3000)),
    ):
        f=FakeDLL();setup(f)
        with patch.object(w,'_api',f):reject('self_attach_'+label,lambda:w.Job.attach_self_and_close(name))
        yes('self_attach_'+label+'_no_setter_or_fallback',not any(c[0] in ('SetSystemTime','CreateJobObjectW','ShellExecuteExW') for c in f.calls))
        if label!='late_missing_job':yes('self_attach_'+label+'_closed',('CloseHandle',501) in f.calls)
    f=FakeDLL()
    with patch.object(w,'_api',f):
        job=w.Job.create(name);p=w.Process.open(12)
        f.fail.add('AssignProcessToJobObject');reject('assign_failure_no_fallback',lambda:job.assign_process(p))
        f.fail.clear();f.fail.add('IsProcessInJob');reject('contains_query_error_not_false',lambda:job.contains(p))
        f.fail.clear();f.fail.add('TerminateJobObject');reject('terminate_failure_not_success',job.terminate)
        f.fail.clear();job.close();p.close()
    f=FakeDLL()
    with patch.object(w,'_api',f):
        job=w.Job.create(name);p=w.Process.open(12)
        f.creation_override=f.created+1
        reject('assign_recycled_creation_rejected',lambda:job.assign_process(p))
        yes('assign_recycled_creation_before_assignment',not any(c[0]=='AssignProcessToJobObject' for c in f.calls))
        f.creation_override=None;f.fail.add('OpenProcess')
        reject('assign_extra_access_denied',lambda:job.assign_process(p))
        f.fail.clear();f.fail.add('QueryInformationJobObject')
        reject('job_active_query_failure_not_zero',job.active_count)
        f.fail.clear();f.fail.add('CloseHandle')
        reject('job_close_failure_is_visible',job.close)
        yes('job_close_failure_retains_handle',job._handle==500)
        f.fail.clear();job.close();p.close()
    f=FakeDLL()
    with patch.object(w,'_api',f):
        def false_membership(process,job,result):
            f.call('IsProcessInJob',process,job)
            C.cast(result,C.POINTER(w.W.BOOL)).contents.value=0
            return 1
        with patch.object(f,'IsProcessInJob',false_membership):
            reject('successful_assign_without_membership_is_rejected',lambda:w.Job.attach_self_and_close(name))
    yes('false_membership_worker_handle_closed',('CloseHandle',501) in f.calls)

    f=FakeDLL()
    exe=str(Path(sys.executable).resolve())
    with patch.object(w,'_api',f):
        p=w.launch_elevated(exe,'-I -B -c "immutable payload"');p.close()
    launches=[c for c in f.calls if c[0]=='ShellExecuteExW']
    yes('UAC_fake_runas_hidden_exact_arguments',launches==[('ShellExecuteExW','runas',exe,'-I -B -c "immutable payload"',0x540,0)])
    yes('UAC_COM_thread_initialized_restored',f.calls[0]==('CoInitializeEx',None,6) and f.calls[-2][0]=='CoUninitialize')
    for label,setup in (
        ('cancelled',lambda f:f.fail.add('ShellExecuteExW')),
        ('no_handle',lambda f:setattr(f,'shell_handle',None)),
        ('COM_changed_mode',lambda f:setattr(f,'com_result',-2147417850)),
        ('handle_query_denied',lambda f:f.fail.add('GetProcessTimes')),
    ):
        f=FakeDLL();setup(f)
        with patch.object(w,'_api',f):reject('UAC_'+label,lambda:w.launch_elevated(exe,'payload'))
        yes('UAC_'+label+'_no_retry',sum(c[0]=='ShellExecuteExW' for c in f.calls)<=1)
        if label!='COM_changed_mode':yes('UAC_'+label+'_COM_uninitialized',f.calls[-1][0]=='CoUninitialize')
    f=FakeDLL();f.com_result=1
    with patch.object(w,'_api',f):
        p=w.launch_elevated(exe,'payload');p.close()
    yes('UAC_COM_S_FALSE_still_balanced',sum(c[0]=='CoUninitialize' for c in f.calls)==1)
    f=FakeDLL()
    with patch.object(w,'_api',f):
        reject('UAC_relative_exe_rejected',lambda:w.launch_elevated('python.exe','payload'))
        reject('UAC_NUL_arguments_rejected',lambda:w.launch_elevated(exe,'bad\x00argument'))
    yes('invalid_UAC_inputs_before_COM',not f.calls)

    f=FakeDLL()
    with patch.object(w,'_api',f):
        def guard():f.calls.append(('guard',));return True
        raw=w.set_utc_unix(1700000000.1239,guard)
    setters=[i for i,c in enumerate(f.calls) if c[0]=='SetSystemTime']
    yes('clock_guard_immediately_precedes_single_call',len(setters)==1 and f.calls[setters[0]-1]==('guard',))
    yes('clock_raw_bool_error_no_retry',raw['called'] is True and raw['ok'] is True and raw['return_value']==1 and raw['winerror']==0 and raw['retry_count']==0 and raw['rollback_attempted'] is False)
    yes('clock_UTC_fields_and_millisecond_floor',raw['target_unix_ms']==1700000000123 and raw['systemtime_utc']=={'year':2023,'month':11,'day_of_week':2,'day':14,'hour':22,'minute':13,'second':20,'milliseconds':123})
    yes('clock_raw_before_after_kernel_ticks',raw['after_tick_ms']>=raw['before_tick_ms'] and type(raw['before_utc_ns']) is int and type(raw['after_utc_ns']) is int)
    for label,value in (('false',False),('none',None),('truthy_integer',1)):
        f=FakeDLL()
        with patch.object(w,'_api',f):reject('clock_guard_'+label,lambda value=value:w.set_utc_unix(1700000000,lambda:value))
        yes('clock_guard_'+label+'_mutation_zero',not any(c[0]=='SetSystemTime' for c in f.calls))
    f=FakeDLL()
    with patch.object(w,'_api',f):
        def deny():raise PermissionError('deadline expired')
        reject('clock_guard_exception',lambda:w.set_utc_unix(1700000000,deny))
    yes('clock_guard_exception_mutation_zero',not any(c[0]=='SetSystemTime' for c in f.calls))
    for label,value in (('bool',True),('nan',float('nan')),('inf',float('inf')),('text','1700000000'),('overflow',1e30)):
        f=FakeDLL()
        with patch.object(w,'_api',f):reject('clock_target_'+label,lambda value=value:w.set_utc_unix(value,lambda:True))
        yes('clock_target_'+label+'_before_API',not f.calls)
    f=FakeDLL();f.clock_result=0;f.clock_error=1314
    with patch.object(w,'_api',f):raw=w.set_utc_unix(1700000000,lambda:True)
    yes('clock_privilege_denied_raw_preserved',raw['ok'] is False and raw['winerror']==1314 and raw['return_value']==0)
    yes('clock_privilege_denied_single_call_no_adjust_or_retry',sum(c[0]=='SetSystemTime' for c in f.calls)==1 and not any('Token' in c[0] for c in f.calls))
    f=FakeDLL()
    def lost_result(value):
        f.call('SetSystemTime')
        raise RuntimeError('HOST result lost after API entry')
    with patch.object(w,'_api',f),patch.object(f,'SetSystemTime',lost_result):
        try:w.set_utc_unix(1700000000,lambda:True)
        except RuntimeError as exc:yes('clock_entered_result_loss_propagates_unknown',str(exc)=='HOST result lost after API entry')
        else:raise AssertionError('Clock result loss hidden')
    yes('clock_result_loss_never_retries_or_rolls_back',sum(c[0]=='SetSystemTime' for c in f.calls)==1)
    observations={}
    for label,delay in (('no_pause',0),('guard_pause_4s',4)):
        row=_actual_worker_relative_case(guard_delay=delay)
        observations[label]=row
        yes('relative_actual_worker_'+label+'_one_API',row['error'] is None and len(row['calls'])==1)
        call=row['calls'][0]
        yes('relative_actual_worker_'+label+'_step_within_cap',abs(call['actual_shift_s'])<=5 and abs(call['actual_shift_s']+3.995)<.0011)
        yes('relative_actual_worker_'+label+'_typed_API_success',any(m['kind']=='API_RESULT' and m['api']['ok'] is True for m in row['messages']))
    yes('relative_guard_pause_original_counterexample_closed',observations['guard_pause_4s']['calls'][0]['sample_age_s']==4
        and abs(observations['guard_pause_4s']['calls'][0]['actual_shift_s'])<5)
    for label,delta,allowed in (('positive_inner',4.949,True),('negative_inner',-4.949,True),
                                 ('positive_margin',4.951,False),('negative_margin',-4.951,False),
                                 ('positive_five',5,False),('negative_five',-5,False)):
        row=_actual_worker_relative_case(delta=delta);observations[label]=row
        yes('relative_actual_cap_'+label,(row['error'] is None and len(row['calls'])==1) if allowed
            else (row['error'] is not None and not row['calls']))
    for label,options in (
        ('target_age_21ms',{'target_delay':.021}),
        ('target_age_4s',{'target_delay':4}),
        ('forward_wall_jump',{'wall_jump':1}),
        ('backward_wall_jump',{'wall_jump':-1}),
    ):
        row=_actual_worker_relative_case(**options);observations[label]=row
        yes('relative_actual_'+label+'_zero_API',row['error'] is not None and not row['calls'])
    row=_actual_worker_relative_case(target_delay=.020);observations['target_age_20ms']=row
    yes('relative_actual_target_age_boundary20ms',row['error'] is None and len(row['calls'])==1
        and any(m.get('api',{}).get('target_age_ns')==20_000_000 for m in row['messages']))
    row=_actual_worker_relative_case(api_ok=False);observations['API_denied']=row
    yes('relative_actual_failed_API_raw_no_retry',row['error'] is None and len(row['calls'])==1
        and any(m['kind']=='API_RESULT' and m['api']['ok'] is False and m['api']['winerror']==1314 for m in row['messages']))
    row=_actual_worker_relative_case(result_loss=True);observations['API_result_loss']=row
    yes('relative_actual_result_loss_unknown_once',row['error'] is not None and len(row['calls'])==1
        and any(m['kind']=='ERROR' and m.get('mutation_entered') is True for m in row['messages']))
    for label,delta,allowed in (('positive_quantized_margin',4.95,True),('negative_quantized_margin',-4.95,False),
                                 ('positive_quantized_five',5,False),('negative_quantized_five',-5,False)):
        row=_actual_worker_relative_case(delta=delta,origin_offset_ns=999999);observations[label]=row
        yes('relative_'+label,(row['error'] is None and len(row['calls'])==1 and abs(row['calls'][0]['actual_shift_s'])<=5)
            if allowed else (row['error'] is not None and not row['calls']))
    for label,jump,allowed in (('coherence_plus5ms',.005,True),('coherence_minus5ms',-.005,True),
                               ('coherence_plus5001us',.005001,False),('coherence_minus5001us',-.005001,False)):
        row=_actual_worker_relative_case(wall_jump=jump);observations[label]=row
        yes('relative_'+label,(row['error'] is None and len(row['calls'])==1) if allowed
            else (row['error'] is not None and not row['calls']))
    row=_actual_worker_relative_case(target_delay=-.001);observations['monotonic_regressed']=row
    yes('relative_monotonic_regression_zero_API',row['error'] is not None and not row['calls'])
    for label,delta in (('bool',True),('nan',float('nan')),('inf',float('inf')),('over_cap',5.001),('text','2')):
        f=FakeDLL()
        with patch.object(w,'_api',f):reject('relative_delta_'+label,lambda delta=delta:w.adjust_utc_once(delta,lambda:True))
        yes('relative_delta_'+label+'_before_API',not f.calls)
    for label,value in (('false',False),('none',None),('truthy_int',1)):
        f=FakeDLL()
        with patch.object(w,'_api',f):reject('relative_guard_'+label,lambda value=value:w.adjust_utc_once(2,lambda:value))
        yes('relative_guard_'+label+'_no_setter',not any(c[0]=='SetSystemTime' for c in f.calls))
    f=FakeDLL()
    with patch.object(w,'_api',f):
        def denied():raise PermissionError('HOST expired lease')
        reject('relative_guard_exception',lambda:w.adjust_utc_once(2,denied))
    yes('relative_guard_exception_zero_API',not any(c[0]=='SetSystemTime' for c in f.calls))
    f=FakeDLL()
    with patch.object(w,'_api',f):yes('terminate_current_default_raw_return',w.terminate_current() is True)
    yes('terminate_current_only_self_kernel_calls',f.calls==[('GetCurrentProcess',),('TerminateProcess',-1,124)])
    f=FakeDLL();f.fail.add('TerminateProcess')
    with patch.object(w,'_api',f):yes('terminate_current_failure_returns_for_finally_fallback',w.terminate_current(7) is False)
    yes('terminate_current_failure_no_IO_or_retry',f.calls==[('GetCurrentProcess',),('TerminateProcess',-1,7)])
    for label,value in (('bool',True),('negative',-1),('overflow',0x100000000),('float',124.)):
        f=FakeDLL()
        with patch.object(w,'_api',f):reject('terminate_current_invalid_'+label,lambda value=value:w.terminate_current(value))
        yes('terminate_current_invalid_'+label+'_no_kernel',not f.calls)
    return {'status':'WIN32_FAKE_DLL_HOST_PASS','count':len(tests),'tests':tests,
            'relative_actual_worker_observations':observations,
            'relative_boundary_scope':'Last userspace observation with50ms dispatch margin; targetage20ms/coherence5ms. Not atomic kernel-entry scheduling proof.',
            'real_UAC':0,'real_SetSystemTime':0,'real_child_probe':'NOT_RUN','network':0,'CAN':0}


def _actual_worker_relative_case(guard_delay=0,delta=-3.995,target_delay=0,
                                 wall_jump=0,api_ok=True,result_loss=False,origin_offset_ns=0):
    """Actual worker -> actual new adapter -> fake kernel; no transport or file IO."""
    aliases=('ral109_core','ral109_win32','ral109_runner')
    saved={name:sys.modules.get(name) for name in aliases}
    try:
        sys.modules['ral109_win32']=w
        for name in ('core','runner'):
            alias='ral109_'+name;path=Path(__file__).with_name(name+'.py')
            module=types.ModuleType(alias);module.__file__=str(path);sys.modules[alias]=module
            exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
        core,runner=sys.modules['ral109_core'],sys.modules['ral109_runner']
        nonce='HOST_RELATIVE_ONLY';pin='a'*64;review_pin='b'*64
        approval={'unit':'109','explicit_user_approval':True,'scope':'LOCAL_CLOCK_ALIGN109_ONCE_LE5S',
                  'hardware_approved':False,'clock_cap_s':5,'one_adjustment':1,'plan_sha256':core.PLAN_SHA,
                  'source_freeze_sha256':pin,'review_sha256':review_pin,'user_quote':'HOST_NOT_EXECUTABLE_AUTHORITY'}
        review={'unit':'109','phase':'L4','round':2,'verdict':'PASS','non_author':True,
                'all_required_met':True,'met':6,'unmet':0,'reviewer':'HOST_NONAUTHOR_FIXTURE',
                'actual_freeze_sha256':pin,'actual_plan_sha256':core.PLAN_SHA,
                'criteria':[{'id':'AC'+str(i),'required':True,'met':True} for i in range(1,7)]}
        # This RTT gives the original exact -3.995 midpoint with remote996000ms.
        sample={'local_send_unix':999.99,'local_receive_unix':1000.,'local_elapsed_s':.01,
                'finished_tick_ms':10000,'remote_unix_ms':round((1000+delta-.005)*1000),
                'computer':core.EXPECTED_COMPUTER,'nonce':nonce}
        if abs(delta)==5:
            # Exact endpoint fixture: avoid binary .99 rounding moving the sample over5.
            sample.update(local_send_unix=1000.,local_elapsed_s=0.,remote_unix_ms=round((1000+delta)*1000))
        decision=core.validate_sample(sample,10000)
        sample_sha=core.sha(core.canonical(sample))
        state={'wall_ns':1_000_000_000_000+origin_offset_ns,'mono_ns':10_000_000_000,'tick':10000,'calls':[]}
        def advance(amount,wall_only=False):
            ns=round(amount*1e9);state['wall_ns']+=ns
            if not wall_only:state['mono_ns']+=ns;state['tick']+=round(amount*1000)
        clock=types.SimpleNamespace(time=lambda:state['wall_ns']/1e9,
              time_ns=lambda:state['wall_ns'],monotonic_ns=lambda:state['mono_ns'])
        class Connection:
            def __init__(self):
                self.messages=[];self.commands=[
                    {'kind':'DECIDE','nonce':nonce,'sample':sample,'sample_sha':sample_sha,'decision':decision},
                    {'kind':'APPLY_ONCE','nonce':nonce,'sample_sha':sample_sha},{'kind':'STOP','nonce':nonce}]
            def poll(self,timeout):return True
            def recv_bytes(self,maximum):return core.canonical(self.commands.pop(0))
            def send_bytes(self,raw):self.messages.append(core.strict_loads(raw))
            def close(self):pass
        connection=Connection();kernel=FakeDLL();actual_adjust=w.adjust_utc_once
        def setter(pointer):
            t=pointer._obj
            target=UTCDateTime(t.year,t.month,t.day,t.hour,t.minute,t.second,
                               t.milliseconds*1000,tzinfo=UTCTimezone.utc).timestamp()
            state['calls'].append({'target_unix':target,'live_wall_before_API':state['wall_ns']/1e9,
                                  'actual_shift_s':target-state['wall_ns']/1e9,
                                  'sample_age_s':(state['tick']-10000)/1000})
            if result_loss:raise RuntimeError('HOST relative API result lost after entry')
            kernel.error=0 if api_ok else 1314
            if api_ok:state['wall_ns']=round(target*1e9)
            return int(api_ok)
        def delayed_adjust(value,guard):
            def delayed_guard():advance(guard_delay);return guard()
            return actual_adjust(value,delayed_guard)
        class StructureClock:
            @staticmethod
            def fromtimestamp(value,tz):
                stamp=UTCDateTime.fromtimestamp(value,tz)
                advance(target_delay);advance(wall_jump,wall_only=True)
                return stamp
        payload={'approval':approval,'review':review,'freeze_sha':pin,'review_sha':review_pin,
                 'lease':{'start_tick':9000,'parent_pid':1,'parent_created':1,'nonce':nonce},
                 'job_name':'Local\\HOST_FAKE_JOB','address':'HOST_FAKE_PIPE','auth_hex':'00'}
        parent=types.SimpleNamespace(alive=lambda:True,close=lambda:None)
        error=None
        with patch.object(w,'_api',kernel),patch.object(w,'tick_ms',side_effect=lambda:state['tick']), \
             patch.object(w,'time',clock),patch.object(w,'datetime',StructureClock), \
             patch.object(kernel,'SetSystemTime',setter),patch.object(w,'adjust_utc_once',delayed_adjust), \
             patch.object(w,'set_utc_unix',side_effect=AssertionError('OLD_ABSOLUTE_PATH_UNREACHABLE')), \
             patch.object(w.Process,'open',return_value=parent), \
             patch.object(w.Job,'attach_self_and_close',return_value={'assigned':True,'worker_job_handle_closed':True}), \
             patch.object(runner,'time',clock),patch.object(runner,'Client',return_value=connection):
            try:runner.worker(payload)
            except Exception as exc:error=repr(exc)
        return {'decision':decision,'guard_delay_s':guard_delay,'target_delay_s':target_delay,
                'wall_jump_s':wall_jump,'origin_offset_ns':origin_offset_ns,'calls':state['calls'],'messages':connection.messages,
                'error':error,'actual_worker':True,'actual_relative_adapter':True,'real_SetSystemTime':0}
    finally:
        for name,value in saved.items():
            if value is None:sys.modules.pop(name,None)
            else:sys.modules[name]=value


def _trap_mutations():
    api=w._get_api()
    def trap(*args):raise AssertionError('REAL_PROBE_TIME_OR_UAC_HARD_TRAP')
    api.SetSystemTime=trap;api.ShellExecuteExW=trap
    w.set_utc_unix=trap;w.adjust_utc_once=trap;w.launch_elevated=trap


def probe_worker(name):
    _trap_mutations()
    evidence=w.Job.attach_self_and_close(name)
    print(json.dumps(evidence),flush=True)
    time.sleep(30)


def _real_probe_case(close_last_handle):
    name='Local\\ral109-probe-'+uuid.uuid4().hex
    job=child=pinned=None
    readers=[];buffers={'stdout':bytearray(),'stderr':bytearray()};ready=threading.Event()
    result={'status':'REAL_PROBE_NOT_COMPLETE','mode':'LAST_HANDLE_CLOSE' if close_last_handle else 'TERMINATE_AND_QUERY_ZERO'}
    def pump(pipe,channel):
        for line in iter(pipe.readline,b''):
            buffers[channel].extend(line)
            if channel=='stdout':ready.set()
    try:
        job=w.Job.create(name)
        child=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(Path(__file__).resolve()),'--probe-worker',name],
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
        for pipe,channel in ((child.stdout,'stdout'),(child.stderr,'stderr')):
            reader=threading.Thread(target=pump,args=(pipe,channel),daemon=True);readers.append(reader);reader.start()
        pinned=w.Process.open(child.pid)
        # Pipe readers are outside the job; supervision never blocks on readline.
        deadline=time.monotonic()+8
        while time.monotonic()<deadline and pinned.alive():
            if ready.is_set() and job.contains(pinned):break
            time.sleep(.02)
        contained=job.contains(pinned)
        active_before=job.active_count()
        if close_last_handle:
            job.close()
        else:
            job.terminate()
        terminal=pinned.wait(4000)
        active_after=None
        if not close_last_handle:
            deadline=time.monotonic()+2
            active_after=job.active_count()
            while active_after and time.monotonic()<deadline:
                time.sleep(.02);active_after=job.active_count()
        child.wait(timeout=2)
        for reader in readers:reader.join(timeout=2)
        if any(reader.is_alive() for reader in readers):raise TimeoutError('Owned raw readers not terminal')
        stdout,stderr=bytes(buffers['stdout']),bytes(buffers['stderr'])
        # Terminal/kernel evidence and actual worker evidence are separate obligations.
        worker=json.loads(stdout.decode('utf-8')) if stdout.strip() else None
        passed=(contained and active_before>=1 and terminal and (close_last_handle or active_after==0) and type(worker) is dict
                and worker.get('worker_job_handle_closed') is True and worker.get('assigned') is True
                and worker.get('worker_identity')=={'pid':pinned.pid,'created_filetime':pinned.created_filetime})
        result.update(status='REAL_OWN_CHILD_CONTAINMENT_PASS' if passed else 'REAL_OWN_CHILD_CONTAINMENT_FAILED',
                      contained=contained,active_before=active_before,process_terminal=terminal,
                      active_after=active_after,worker=worker,stdout=stdout.decode('utf-8',errors='replace'),
                      stderr=stderr.decode('utf-8',errors='replace'),child_returncode=child.returncode,
                      active_after_scope='NOT_QUERYABLE_AFTER_LAST_HANDLE_CLOSE' if close_last_handle else 'ACTUAL_KERNEL_QUERY')
    except Exception as exc:
        result.update(status='REAL_OWN_CHILD_CONTAINMENT_UNKNOWN',error=repr(exc))
    finally:
        if job is not None:
            try:job.close()
            except Exception as exc:result['job_close_error']=repr(exc)
        if child is not None and child.poll() is None:
            # Cleanup only this owned Popen child if assignment never succeeded.
            try:child.kill();child.wait(timeout=3)
            except Exception as exc:result['owned_child_cleanup_error']=repr(exc)
        for reader in readers:reader.join(timeout=2)
        result['stdout_raw']=bytes(buffers['stdout']).decode('utf-8',errors='replace')
        result['stderr_raw']=bytes(buffers['stderr']).decode('utf-8',errors='replace')
        result['raw_readers_terminal']=not any(reader.is_alive() for reader in readers)
        if pinned is not None:
            try:result['final_process_terminal']=pinned.wait(1000);pinned.close()
            except Exception as exc:result['final_process_error']=repr(exc)
    if any(n.endswith('_error') for n in result) or result.get('final_process_terminal') is not True or not result['raw_readers_terminal']:
        result['status']='REAL_OWN_CHILD_CONTAINMENT_UNKNOWN'
    return result


def real_probe():
    """Own medium children only, explicit opt-in; never UAC or a time setter."""
    _trap_mutations()
    termination=_real_probe_case(False)
    closing=_real_probe_case(True)
    passed=all(row['status']=='REAL_OWN_CHILD_CONTAINMENT_PASS' for row in (termination,closing))
    return {'status':'REAL_OWN_CHILD_CONTAINMENT_PASS' if passed else 'REAL_OWN_CHILD_CONTAINMENT_NOT_PROVEN',
            'termination':termination,'last_handle_close':closing,'real_UAC':0,'real_SetSystemTime':0,
            'medium_owned_children_only':True,'network':0,'CAN':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--real-probe',action='store_true')
    mode.add_argument('--probe-worker')
    args=parser.parse_args()
    if args.probe_worker:
        probe_worker(args.probe_worker)
    else:
        report=real_probe() if args.real_probe else host_tests()
        print(json.dumps(report))
        if args.real_probe and report['status']!='REAL_OWN_CHILD_CONTAINMENT_PASS':raise SystemExit(1)
