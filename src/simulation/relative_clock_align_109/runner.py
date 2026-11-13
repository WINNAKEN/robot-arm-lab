"""109 single local-clock operation. All authority is checked before UAC.

The controller owns SSH and its raw pipes. The elevated, contained worker
only validates authenticated permits and calls the synchronous time API.
"""
from __future__ import annotations

import base64
import ctypes
import datetime
import json
import msvcrt
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time
import traceback
import zlib
from multiprocessing.connection import Client, Listener

import ral109_core as core
import ral109_win32 as win

SOURCE = {'core.py', 'win32.py', 'runner.py', 'test_core.py',
          'test_win32.py', 'test_runner.py'}
HARNESS = {'execute.py', 'config.json'}
MACHINE = '민주환-JUHWANMI'
PROTOCOL = 'ral109-clock-v1'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def bounded_get(items, lease, phase='active'):
    while True:
        lease.check(win.tick_ms(), phase)
        try:
            kind, value = items.get(timeout=.05)
        except queue.Empty:
            continue
        if kind == 'error':
            raise RuntimeError(value)
        return value


def start_read(connection, raw_path):
    items = queue.Queue()

    def reader():
        try:
            with raw_path.open('xb') as output:
                while True:
                    raw = connection.recv_bytes(1024 * 1024)
                    output.write(len(raw).to_bytes(4, 'big') + raw)
                    output.flush()
                    os.fsync(output.fileno())
                    items.put(('message', core.strict_loads(raw)))
        except Exception as error:
            items.put(('error', repr(error)))
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    return items, thread


def send(connection, kind, nonce, **values):
    connection.send_bytes(core.canonical({'kind': kind, 'nonce': nonce, **values}))


def receive(connection, nonce, lease):
    while not connection.poll(.05):
        lease.check(win.tick_ms(), 'uac')
    value = core.strict_loads(connection.recv_bytes(1024 * 1024))
    core.need(type(value) is dict and value.get('nonce') == nonce,
              'Authenticated invocation nonce')
    return value


def payload_arguments(modules, pins, payload):
    """Compress reviewed bytes, not file paths, into the UAC invocation."""
    archive = {'modules': modules, 'pins': pins, 'payload': payload}
    packed = base64.b64encode(zlib.compress(core.canonical(archive), 9)).decode()
    boot = (
        'import base64,json,zlib,hashlib,sys,types\n'
        f"a=json.loads(zlib.decompress(base64.b64decode('{packed}')))\n"
        "for name in ('core','win32','runner'):\n"
        " raw=a['modules'][name+'.py'].encode('utf-8')\n"
        " assert hashlib.sha256(raw).hexdigest()==a['pins'][name+'.py']\n"
        " alias='ral109_'+name\n"
        " m=types.ModuleType(alias);m.__file__='<reviewed109:'+name+'>'\n"
        " sys.modules[alias]=m;exec(compile(raw,m.__file__,'exec'),m.__dict__)\n"
        "sys.modules['ral109_runner'].worker(a['payload'])\n"
    )
    code = base64.b64encode(zlib.compress(boot.encode(), 9)).decode()
    argument = '-I -S -B -c "exec(__import__(\'zlib\').decompress(__import__(\'base64\').b64decode(\'' + code + '\')))"'
    core.need(len(argument) < 30000, 'Windows immutable command length cap')
    return argument


def worker(payload):
    """Only called from the immutable reviewed in-memory bootstrap."""
    parent = None
    connection = None
    applied = False
    try:
        core.validate_approval(payload['approval'], core.PLAN_SHA,
                               payload['freeze_sha'], payload['review_sha'])
        core.validate_l4(payload['review'], payload['freeze_sha'], core.PLAN_SHA)
        lease = core.Lease(**payload['lease'])
        lease.check(win.tick_ms(), 'worker')
        parent = win.Process.open(lease.parent_pid, lease.parent_created)
        core.need(parent.alive(), 'Live pinned controller before containment')
        attached = win.Job.attach_self_and_close(payload['job_name'])
        core.need(attached['assigned'] is True and
                  attached['worker_job_handle_closed'] is True,
                  'Actual worker containment and closed worker job handle')
        lease.check(win.tick_ms(), 'worker')
        connection = Client(payload['address'], family='AF_PIPE',
                            authkey=bytes.fromhex(payload['auth_hex']))
        send(connection, 'HELLO', lease.nonce, attached=attached,
             freeze_sha=payload['freeze_sha'], review_sha=payload['review_sha'])
        command = receive(connection, lease.nonce, lease)
        core.need(command['kind'] == 'DECIDE', 'Single parent decision')
        sample = command['sample']
        core.need(sample['nonce'] == lease.nonce, 'Sample invocation identity')
        decision = core.validate_sample(sample, win.tick_ms())
        core.need(command['sample_sha'] == core.sha(core.canonical(sample)),
                  'Actual sample bytes bound to permit')
        core.need(command['decision'] == decision, 'Independently derived decision')

        def admission():
            now = win.tick_ms()
            lease.check(now, 'api')
            core.need(lease.active_end-now >= 100 and
                      now-sample['finished_tick_ms'] <= 4900,
                      '100ms dispatch reserve inside original lease/sample bounds')
            core.need(parent.alive(), 'Pinned controller still alive')
            core.need(not applied, 'No second API call')
            core.validate_sample(sample, win.tick_ms())
            expected = sample['local_receive_unix'] + (
                win.tick_ms() - sample['finished_tick_ms']) / 1000
            core.need(abs(time.time() - expected) <= .25,
                      'No local wall jump since fresh measurement')
            return True

        admission()
        if decision['needs_change']:
            send(connection, 'PREPARED', lease.nonce,
                 sample_sha=command['sample_sha'])
            permit = receive(connection, lease.nonce, lease)
            core.need(permit == {'kind': 'APPLY_ONCE', 'nonce': lease.nonce,
                                  'sample_sha': command['sample_sha']},
                      'Final live single-call permit')
            admission()
            # Set before invocation: even a false/error API return consumes it.
            applied = True

            def final_guard():
                now = win.tick_ms()
                lease.check(now, 'api')
                core.need(lease.active_end-now >= 100 and
                          now-sample['finished_tick_ms'] <= 4900,
                          '100ms immediate dispatch reserve')
                core.need(parent.alive(), 'Live parent at synchronous API boundary')
                core.validate_sample(sample, win.tick_ms())
                expected = sample['local_receive_unix'] + (
                    win.tick_ms() - sample['finished_tick_ms']) / 1000
                core.need(abs(time.time() - expected) <= .25, 'Fresh local wall anchor')
                return True

            api = win.adjust_utc_once(decision['midpoint'], final_guard)
            send(connection, 'API_RESULT', lease.nonce, api=api)
        else:
            api = {'called': False, 'ok': True, 'reason': 'Already within original bound'}
            send(connection, 'NO_CHANGE', lease.nonce, api=api)
        command = receive(connection, lease.nonce, lease)
        core.need(command == {'kind': 'STOP', 'nonce': lease.nonce},
                  'No subsequent mutation commands')
    except Exception:
        if connection is not None:
            try:
                send(connection, 'ERROR', payload['lease']['nonce'],
                     error=traceback.format_exc(), mutation_entered=applied)
            except Exception as error:
                # No rollback or new authority follows diagnostic failure.
                sys.stderr.write('109 worker IPC failed: ' + repr(error) + '\n')
        raise
    finally:
        if connection is not None:
            connection.close()
        if parent is not None:
            parent.close()


def trusted_ssh():
    buffer = ctypes.create_unicode_buffer(32768)
    size = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    core.need(0 < size < len(buffer), 'Trusted Windows system directory')
    executable = Path(buffer.value) / 'OpenSSH' / 'ssh.exe'
    core.need(executable.is_file(), 'Installed system SSH executable')
    return str(executable)


def pipe_state(stream):
    """Kernel availability, with unbuffered single-owner pipe reads below."""
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    peek = api.PeekNamedPipe
    peek.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                     ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    peek.restype = ctypes.c_int
    available = ctypes.c_uint32()
    handle = msvcrt.get_osfhandle(stream.fileno())
    if not peek(handle, None, 0, None, ctypes.byref(available), None):
        error = ctypes.get_last_error()
        if error == 109:  # ERROR_BROKEN_PIPE, after buffered bytes are drained.
            return 0, True
        raise ctypes.WinError(error)
    return available.value, False


def run_query(script, label, folder, lease, job, local=False):
    """Fresh source: no capture-thread startup or thread-dependent drain."""
    encoded = base64.b64encode(script.encode('utf-16le')).decode()
    argv = [trusted_ssh(), '-T', '-o', 'BatchMode=yes', '-o',
            'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8', 'isaacpc',
            'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + encoded]
    if local:
        executable = Path(trusted_ssh()).parents[1] / 'WindowsPowerShell/v1.0/powershell.exe'
        argv = [str(executable), '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded]
    start_wall = time.time()
    start_tick = win.tick_ms()
    end = min(start_tick + 20000, lease.active_end)
    communication_end = end - 2000
    stage_guard = getattr(job, 'stage_guard', None)
    if stage_guard is not None:
        core.need(stage_guard.get('stage_end') is None, 'No overlapping SSH stage')
        stage_guard['stage_end'] = end
    core.atomic_result_exclusive(folder / (label + '-request.json'),
                                {'script': script, 'argv': argv,
                                 'started_unix': start_wall, 'started_tick_ms': start_tick,
                                 'stage_end_tick_ms': end})
    raw = {'stdout': bytearray(), 'stderr': bytearray()}
    outputs = {}
    process = None
    eof = {'stdout': False, 'stderr': False}
    errors = []
    finished_wall = finished_tick = None

    def drain():
        for name in raw:
            if eof[name]:
                continue
            count, broken = pipe_state(getattr(process, name))
            if count:
                chunk = getattr(process, name).read(min(count, 16384))
                core.need(chunk is not None and len(chunk) > 0, 'Available pipe bytes read')
                core.need(len(raw[name]) + len(chunk) <= 1024 * 1024,
                          'Explicit bounded raw capture; overflow is incomplete')
                raw[name].extend(chunk)
                outputs[name].write(chunk)
                outputs[name].flush()
                os.fsync(outputs[name].fileno())
            elif broken:
                eof[name] = True
    try:
        # Reader destinations exist before a query can emit even one byte.
        for name in raw:
            outputs[name] = (folder/(label+'-'+name+'.raw')).open('xb')
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   bufsize=0, creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign_process(process.pid)
        while process.poll() is None or not all(eof.values()):
            lease.check(win.tick_ms(), 'sample')
            core.need(win.tick_ms() < communication_end, 'SSH communication timeout with shared cleanup reserve')
            drain()
            time.sleep(.002)
        finished_wall, finished_tick = time.time(), win.tick_ms()
    except Exception as error:
        errors.append(repr(error))
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=max(.001, min(2, (end-win.tick_ms()) / 1000)))
            try:
                while not all(eof.values()) and win.tick_ms() < end:
                    drain()
                    time.sleep(.002)
            except Exception as error:
                errors.append('Final raw drain: '+repr(error))
            for stream in (process.stdout, process.stderr):
                stream.close()
        for output in outputs.values():
            output.close()
        core.atomic_result_exclusive(folder / (label + '-capture.json'), {
            'returncode': process.returncode if process is not None else None,
            'capture_source': 'CONTROLLER_DIRECT_PEEK_AND_UNBUFFERED_READ_NO_READER_THREADS',
            'readers_terminal': all(eof.values()),
            'raw_bytes': {name: len(value) for name,value in raw.items()},
            'raw_b64': {name: base64.b64encode(value).decode() for name,value in raw.items()},
            'capture_errors': errors,
            'all_raw_captured': process is not None and all(eof.values()) and not errors})
        core.need(win.tick_ms() < end, 'Query20s lifecycle includes final capture')
    core.need(process is not None and all(eof.values()) and not errors,
              'All original query raw captured with direct terminal reads')
    core.need(process.returncode == 0, 'OS query unsuccessful; raw retained')
    result = core.strict_loads(bytes(raw['stdout']))
    core.need(win.tick_ms() < end, 'Query20s lifecycle includes parsing')
    if stage_guard is not None:
        stage_guard['stage_end'] = None
    return result, {'local_send_unix': start_wall, 'local_receive_unix': finished_wall,
                    'local_elapsed_s': (finished_tick-start_tick) / 1000,
                    'finished_tick_ms': finished_tick}


def remote_sample(folder, lease, job, label):
    script = (
        "$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "$n=[DateTimeOffset]::UtcNow;@{computer=$env:COMPUTERNAME;"
        f"nonce='{lease.nonce}';remote_unix_ms=$n.ToUnixTimeMilliseconds()}}"
        '|ConvertTo-Json -Compress')
    value, timing = run_query(script, label, folder, lease, job)
    core.need(type(value) is dict and set(value) == {'computer', 'nonce', 'remote_unix_ms'}
              and value['nonce'] == lease.nonce and value['computer'] == MACHINE,
              'Closed expected remote machine and challenge')
    sample = {**timing, **value}
    decision = core.validate_sample(sample, win.tick_ms())
    core.atomic_result_exclusive(folder / (label + '.json'),
                                {'sample': sample, 'decision': decision})
    return sample, decision


def preflight(root, folder, lease, job):
    # Native108 activation must still be absent; no clock step inside a live budget.
    native = root / 'outputs' / 'isaac-clock-ready-108'
    for name in ('native-approval.json', 'runtime-budget.json', 'activation.json',
                 'execution-freeze.json', 'clock-query-attempt.json'):
        core.need(not (native / name).exists(), '108 has not started: ' + name)
    cfg = core.strict_loads((root / 'src/simulation/clock_ready_resume_108/config.json').read_bytes())
    core.need(type(cfg['deadline_unix']) is int and cfg['deadline_unix'] == 0,
              'No active108 deadline during OS repair')
    script = (
        "$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "@{computer=$env:COMPUTERNAME;native=@(Get-CimInstance Win32_Process|"
        "Where-Object {$_.Name -match '^(kit|isaacsim)(\\.exe)?$' -or "
        "($_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -match 'SimulationApp|isaacsim')}|"
        "Select-Object ProcessId,Name)}|ConvertTo-Json -Depth 4 -Compress")
    value, _ = run_query(script, 'remote-idle', folder, lease, job)
    core.need(value['computer'] == MACHINE and value['native'] == [],
              'Remote native process preflight idle')
    value, _ = run_query(script, 'local-idle', folder, lease, job, local=True)
    core.need(value['native'] == [], 'Local native process preflight idle')


def soft_stop(lease, done, job, state):
    """Best-effort early cancellation; hard enforcement never depends on it."""
    try:
        while not done.wait(.025):
            if win.tick_ms() >= lease.active_end:
                job.terminate()
                return
    except BaseException:
        state['soft_stop_failed'] = True  # Memory only, never diagnostic I/O.


def fatal_exit():
    try:
        win.terminate_current(124)
    finally:
        os._exit(124)


def hard_stop(lease, done, state=None):
    """Independent fail-closed process fence: no job/diagnostic/file calls."""
    try:
        while not done.wait(.025):
            now = win.tick_ms()
            stage_end = state.get('stage_end') if state is not None else None
            if now >= lease.hard_end or (stage_end is not None and now >= stage_end):
                break
        else:
            return
    except BaseException:
        # Even a supervisor failure must revoke this helper's authority.
        return fatal_exit()
    fatal_exit()


def controller(context):
    """One reserved operation; code review and separate authority already checked."""
    root, out = context['root'], context['out']
    operation = out / 'execution'
    operation.mkdir(exist_ok=True)
    nonce = secrets.token_hex(16)
    identity = win.current_identity()
    start = win.tick_ms()
    lease = core.Lease(start, identity['pid'], identity['created_filetime'], nonce)
    core.reserve_attempt(operation/'attempt.json', {
        'unit': '109', 'nonce': nonce, 'start_tick_ms': start,
        'parent': identity, 'active_end': lease.active_end, 'hard_end': lease.hard_end,
        'approval_sha256': context['approval_sha'], 'freeze_sha256': context['freeze_sha'],
        'review_sha256': context['review_sha'], 'plan_sha256': core.PLAN_SHA,
        'boot_witness': 'Same live kernel parent/job nonce and nondecreasing GetTickCount64'})
    job = None
    listener = None
    connection = None
    child = None
    watchdog_done = threading.Event()
    launch_done = threading.Event()
    launch_result = queue.Queue()
    launch_state = {'entered': False, 'child': None, 'error': None}
    supervisor_state = {}
    api = None
    mutation_requested = False
    terminal = False
    result = {'unit': '109', 'status': 'IN_FLIGHT_UNKNOWN', 'nonce': nonce,
              'freeze_sha256': context['freeze_sha'], 'review_sha256': context['review_sha'],
              'plan_sha256': core.PLAN_SHA, 'native108_started': False,
              'hardware_CAN': False}
    try:
        job = win.Job.create('Local\\ral109-' + nonce)
        job.stage_guard = supervisor_state

        threading.Thread(target=hard_stop,
                         args=(lease, watchdog_done, supervisor_state), daemon=True).start()
        threading.Thread(target=soft_stop,
                         args=(lease, watchdog_done, job, supervisor_state), daemon=True).start()
        auth = secrets.token_bytes(32)
        listener = Listener(family='AF_PIPE', authkey=auth)
        accepted = queue.Queue()

        def accept():
            try:
                accepted.put(('message', listener.accept()))
            except Exception as error:
                accepted.put(('error', repr(error)))
        threading.Thread(target=accept, daemon=True).start()
        # The controller has checked the complete raw report/hash. Only its
        # required typed gate fields travel to the immutable worker, not long
        # review narratives that can exceed Windows' command-line limit.
        gate_fields = ('unit','phase','round','verdict','non_author','all_required_met',
                       'met','unmet','reviewer','actual_freeze_sha256','actual_plan_sha256')
        review_gate = {key: context['review'][key] for key in gate_fields}
        review_gate['criteria'] = [{key: row[key] for key in ('id','required','met')}
                                   for row in context['review']['criteria']]
        payload = {'approval': context['approval'], 'review': review_gate,
                   'freeze_sha': context['freeze_sha'], 'review_sha': context['review_sha'],
                   'lease': {'start_tick': start, 'parent_pid': identity['pid'],
                             'parent_created': identity['created_filetime'], 'nonce': nonce},
                   'job_name': job.name, 'address': listener.address, 'auth_hex': auth.hex()}
        arguments = payload_arguments(context['modules'], context['pins'], payload)

        def launch():
            launch_state['entered'] = True
            try:
                handle = win.launch_elevated(sys.executable, arguments)
                # Capture ownership before notification or deadline admission.
                launch_state['child'] = handle
                launch_result.put(('message', handle))
            except Exception as error:
                launch_state['error'] = repr(error)
                launch_result.put(('error', repr(error)))
            finally:
                launch_done.set()
        threading.Thread(target=launch, daemon=True).start()
        while not launch_done.wait(.025):
            lease.check(win.tick_ms(), 'uac')
        child = bounded_get(launch_result, lease, 'uac')
        connection = bounded_get(accepted, lease, 'uac')
        messages, _ = start_read(connection, operation/'worker-ipc.raw')
        hello = bounded_get(messages, lease)
        attached = hello.get('attached', {})
        core.need(hello.get('kind') == 'HELLO' and hello.get('nonce') == nonce
                  and hello.get('freeze_sha') == context['freeze_sha']
                  and hello.get('review_sha') == context['review_sha']
                  and attached.get('assigned') is True
                  and attached.get('worker_job_handle_closed') is True
                  and attached.get('worker_identity') == {
                      'pid': child.pid, 'created_filetime': child.created_filetime}
                  and job.contains(child) and child.alive(), 'Actual pinned contained worker')
        preflight(root, operation, lease, job)
        sample, decision = remote_sample(operation, lease, job, 'before')
        sample_sha = core.sha(core.canonical(sample))
        send(connection, 'DECIDE', nonce, sample=sample,
             sample_sha=sample_sha, decision=decision)
        value = bounded_get(messages, lease)
        if decision['needs_change']:
            core.need(value == {'kind': 'PREPARED', 'nonce': nonce, 'sample_sha': sample_sha},
                      'Contained worker accepted same fresh sample')
            lease.check(win.tick_ms(), 'adjust')
            core.validate_sample(sample, win.tick_ms())
            core.need(job.contains(child) and child.alive(), 'Live final containment')
            mutation_requested = True
            send(connection, 'APPLY_ONCE', nonce, sample_sha=sample_sha)
            value = bounded_get(messages, lease)
            core.need(value.get('kind') == 'API_RESULT', 'Typed single API result')
        else:
            core.need(value.get('kind') == 'NO_CHANGE', 'Typed unchanged path')
        core.need(value.get('nonce') == nonce, 'API response invocation')
        api = value['api']
        core.need(api.get('ok') is True and api.get('called') is decision['needs_change'],
                  'Successful API or independently verified no-change result')
        after, after_decision = remote_sample(operation, lease, job, 'after')
        core.need(after_decision['needs_change'] is False,
                  'Fresh post-verification entire interval within original bound')
        send(connection, 'STOP', nonce)
        core.need(child.wait(max(1, min(5000, lease.remaining_ms(win.tick_ms(), 'cleanup')))),
                  'Pinned worker terminal')
        while job.active_count() != 0:
            lease.check(win.tick_ms(), 'cleanup')
            time.sleep(.01)
        terminal = True
        result.update({'status': 'ALIGNED' if api['called'] else 'VERIFIED_NO_CHANGE',
                       'before_sample': sample, 'before_decision': decision,
                       'api': api, 'after_sample': after, 'after_decision': after_decision,
                       'terminal': True, 'job_active_processes': 0,
                       'relative_clock_verified': True, 'UTC_certified': False})
    except Exception as error:
        result.update({'error': repr(error), 'traceback': traceback.format_exc(),
                       'mutation_requested': mutation_requested, 'api_report': api,
                       'relative_clock_verified': False, 'UTC_certified': False})
    finally:
        # An expired launch result still conveys an owned handle, not permission.
        if child is None and launch_state['child'] is not None:
            child = launch_state['child']
        if job is not None and not terminal:
            try:
                job.terminate()
                end = min(lease.hard_end, win.tick_ms()+8000)
                while win.tick_ms() < end:
                    if child is None and launch_state['child'] is not None:
                        child = launch_state['child']
                    known_launch_terminal = (
                        not launch_state['entered'] or
                        (launch_done.is_set() and child is not None and child.wait(0)))
                    if job.active_count() == 0 and known_launch_terminal:
                        terminal = True
                        break
                    time.sleep(.025)
            except Exception as error:
                result['cleanup_error'] = repr(error)
        result['terminal'] = terminal
        result['launch_returned_handle'] = child is not None
        result['launch_error'] = launch_state['error']
        result['supervision'] = supervisor_state
        result['authority_revocation_requested'] = True
        result['authority_revoked_confirmed'] = terminal
        result['clock_change_may_be_inflight'] = not terminal
        if result['status'] == 'IN_FLIGHT_UNKNOWN' and terminal:
            result['status'] = 'FAILED_CLOSED_UNKNOWN'
        # Keep watcher live through result I/O. Any failure keeps attempt consumed.
        try:
            core.atomic_result_exclusive(operation/'result.json', result)
        finally:
            if connection is not None:
                connection.close()
            if listener is not None:
                listener.close()
            if child is not None:
                child.close()
            if job is not None:
                job.close()
            # Unresolved/pending elevated children never cancel the hard fence.
            if terminal:
                watchdog_done.set()
    return result
