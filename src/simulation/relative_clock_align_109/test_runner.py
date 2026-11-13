"""HOST wiring tests: real local IPC, fake clock/UAC/kernel, no real mutation."""
from pathlib import Path
import contextlib
import base64
import hashlib
import io
import json
import random
import subprocess
import sys
import tempfile
import threading
import time as real_time
import types
import unittest
import zlib
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for name in ('core', 'win32', 'runner'):
    alias = 'ral109_' + name
    if alias not in sys.modules:
        module = types.ModuleType(alias)
        module.__file__ = str(HERE/(name+'.py'))
        sys.modules[alias] = module
        exec(compile((HERE/(name+'.py')).read_bytes(), module.__file__, 'exec'), module.__dict__)
core = sys.modules['ral109_core']
runner = sys.modules['ral109_runner']


def authority():
    freeze, review_hash = 'a'*64, 'b'*64
    approval = {'unit':'109','explicit_user_approval':True,
                'scope':'LOCAL_CLOCK_ALIGN109_ONCE_LE5S','hardware_approved':False,
                'clock_cap_s':5,'one_adjustment':1,'plan_sha256':core.PLAN_SHA,
                'source_freeze_sha256':freeze,'review_sha256':review_hash,
                'user_quote':'HOST_ONLY_NOT_EXECUTABLE_AUTHORITY'}
    review = {'unit':'109','phase':'L4','round':1,'verdict':'PASS','non_author':True,
              'all_required_met':True,'met':6,'unmet':0,'reviewer':'HOST_NONAUTHOR_FIXTURE',
              'actual_freeze_sha256':freeze,'actual_plan_sha256':core.PLAN_SHA,
              'criteria':[{'id':'AC'+str(i),'required':True,'met':True} for i in range(1,7)]}
    return approval, review


class FakeClock:
    def __init__(self):
        self.offset = 0
        self.origin = real_time.monotonic()
    def time(self):
        return real_time.time()+self.offset
    def sleep(self, amount):
        real_time.sleep(amount)
    def ticks(self):
        return 100000 + int((real_time.monotonic()-self.origin)*1000)


class Environment:
    def __init__(self, offset=2.2, api_ok=True, stale=False, peer=runner.MACHINE,
                 membership=True, age_ms=0):
        self.clock = FakeClock()
        self.offset, self.api_ok, self.stale = offset, api_ok, stale
        self.peer, self.membership = peer, membership
        self.age_ms = age_ms
        self.apis, self.launches, self.preflights = [], 0, 0
        self.payload = None
        self.killed = threading.Event()
        self.finished = threading.Event()
        self.worker_errors = []
        self.parent = types.SimpleNamespace(alive=lambda:True, close=lambda:None)
        self.child = types.SimpleNamespace(pid=101, created_filetime=10001,
            alive=lambda:not self.finished.is_set(),
            wait=lambda ms:self.finished.wait(ms/1000), close=lambda:None)
        env = self

        class Job:
            def __init__(self, name): self.name = name
            @classmethod
            def create(cls, name): return cls(name)
            @classmethod
            def attach_self_and_close(cls, name):
                return {'assigned':True,'worker_job_handle_closed':True,
                        'worker_identity':{'pid':101,'created_filetime':10001}}
            def contains(self, process): return env.membership
            def active_count(self): return 0 if env.finished.is_set() else 1
            def terminate(self): env.killed.set()
            def close(self): env.killed.set()
        self.win = types.SimpleNamespace(Job=Job, tick_ms=self.tick,
             current_identity=lambda:{'pid':100,'created_filetime':10000},
             Process=types.SimpleNamespace(open=lambda *args:env.parent),
             launch_elevated=self.launch, adjust_utc_once=self.adjust_time)

    def tick(self):
        if threading.current_thread().name == 'host-worker' and self.killed.is_set():
            raise RuntimeError('HOST simulated terminated worker')
        return self.clock.ticks()

    def packed(self, modules, pins, payload):
        self.payload = payload
        return 'HOST_NO_UAC'

    def launch(self, exe, arguments):
        self.launches += 1
        def run():
            try:
                runner.worker(self.payload)
            except BaseException as error:
                self.worker_errors.append(repr(error))
            finally:
                self.finished.set()
        threading.Thread(target=run, name='host-worker', daemon=True).start()
        return self.child

    def adjust_time(self, delta, guard):
        self.assert_guard = guard() is True
        if not self.assert_guard:
            raise AssertionError('HOST immediate guard denied')
        target = self.clock.time()+delta
        self.apis.append(target)
        if self.api_ok:
            self.clock.offset = target-real_time.time()
        return {'called':True,'ok':self.api_ok,'return_value':int(self.api_ok),
                'winerror':0 if self.api_ok else 1314,'retry_count':0}

    def preflight(self, *args):
        self.preflights += 1

    def sample(self, folder, lease, job, label):
        sent = self.clock.time()
        remote = int((real_time.time()+self.offset)*1000)
        received = self.clock.time()
        sample = {'local_send_unix':sent,'local_receive_unix':received,
                  'local_elapsed_s':received-sent,'finished_tick_ms':self.tick(),
                  'remote_unix_ms':remote,'computer':self.peer,'nonce':lease.nonce}
        if self.stale:
            sample['finished_tick_ms'] -= 5001
        sample['finished_tick_ms'] -= self.age_ms
        return sample, core.validate_sample(sample, self.tick())


class Wiring(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ral109-host-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root/'out'
        self.out.mkdir()

    def context(self):
        approval, review = authority()
        return {'root':self.root,'out':self.out,'approval':approval,'review':review,
                'freeze_sha':'a'*64,'review_sha':'b'*64,'approval_sha':'c'*64,
                'modules':{},'pins':{}}

    def execute(self, env):
        with patch.object(runner,'win',env.win), patch.object(runner,'time',env.clock), \
             patch.object(runner,'payload_arguments',env.packed), \
             patch.object(runner,'preflight',env.preflight), \
             patch.object(runner,'remote_sample',env.sample):
            result = runner.controller(self.context())
            self.assertTrue(env.finished.wait(1))
            return result

    def test_whole_wiring_single_adjustment_and_terminal(self):
        env = Environment()
        result = self.execute(env)
        self.assertEqual(result['status'],'ALIGNED')
        self.assertEqual(len(env.apis),1)
        self.assertTrue(result['terminal'])
        self.assertEqual(result['job_active_processes'],0)
        self.assertTrue(result['relative_clock_verified'])
        self.assertFalse(result['UTC_certified'])
        self.assertEqual(env.launches,1)
        self.assertTrue((self.out/'execution/worker-ipc.raw').stat().st_size > 0)

    def test_already_aligned_verifies_without_api(self):
        env = Environment(offset=0)
        result = self.execute(env)
        self.assertEqual(result['status'],'VERIFIED_NO_CHANGE')
        self.assertEqual(env.apis,[])

    def test_api_failure_never_retries_or_accepts_clock(self):
        env = Environment(api_ok=False)
        result = self.execute(env)
        self.assertEqual(len(env.apis),1)
        self.assertEqual(result['status'],'FAILED_CLOSED_UNKNOWN')
        self.assertFalse(result['relative_clock_verified'])

    def test_stale_sample_rejected_before_permit(self):
        env = Environment(stale=True)
        result = self.execute(env)
        self.assertEqual(env.apis,[])
        self.assertFalse(result['relative_clock_verified'])

    def test_dispatch_margin_rejects_sample_too_close_to_five_seconds(self):
        env=Environment(age_ms=4950)
        result=self.execute(env)
        self.assertEqual(env.apis,[])
        self.assertFalse(result['relative_clock_verified'])

    def test_different_peer_rejected_before_permit(self):
        env = Environment(peer='OTHER')
        result = self.execute(env)
        self.assertEqual(env.apis,[])
        self.assertFalse(result['relative_clock_verified'])

    def test_membership_not_assumed_from_worker_message(self):
        env = Environment(membership=False)
        result = self.execute(env)
        self.assertEqual(env.apis,[])
        self.assertEqual(env.preflights,0)
        self.assertFalse(result['relative_clock_verified'])

    def test_consumed_attempt_blocks_second_uac(self):
        env = Environment()
        self.execute(env)
        with patch.object(runner,'win',env.win), self.assertRaises(FileExistsError):
            runner.controller(self.context())
        self.assertEqual(env.launches,1)
        self.assertEqual(len(env.apis),1)

    def test_result_loss_after_call_remains_consumed(self):
        env = Environment()
        original = core.atomic_result_exclusive
        def failing(path, record):
            if Path(path).name == 'result.json':
                raise OSError('HOST injected result I/O loss')
            return original(path,record)
        with patch.object(core,'atomic_result_exclusive',failing), self.assertRaises(OSError):
            self.execute(env)
        self.assertEqual(len(env.apis),1)
        self.assertTrue((self.out/'execution/attempt.json').exists())
        self.assertFalse((self.out/'execution/result.json').exists())

    def test_worker_approval_denial_does_not_attach_or_call(self):
        env = Environment()
        approval,review = authority()
        approval['explicit_user_approval'] = False
        with patch.object(runner,'win',env.win), self.assertRaises(ValueError):
            runner.worker({'approval':approval,'review':review,'freeze_sha':'a'*64,
                           'review_sha':'b'*64})
        self.assertEqual(env.apis,[])

    def test_payload_executes_captured_module_bytes(self):
        modules={'core.py':'VALUE=1','win32.py':'VALUE=2',
                 'runner.py':"def worker(payload):\n print(payload['value'])\n"}
        pins={key:hashlib.sha256(value.encode()).hexdigest() for key,value in modules.items()}
        arguments=runner.payload_arguments(modules,pins,{'value':'HOST_CAPTURED_BYTES'})
        result=subprocess.run(subprocess.list2cmdline([sys.executable])+' '+arguments,
                              capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),b'HOST_CAPTURED_BYTES')

    def test_payload_hash_mismatch_denied_before_worker(self):
        modules={'core.py':'VALUE=1','win32.py':'VALUE=2',
                 'runner.py':"def worker(payload):\n print('SHOULD_NOT_RUN')\n"}
        arguments=runner.payload_arguments(modules,{key:'0'*64 for key in modules},{})
        result=subprocess.run(subprocess.list2cmdline([sys.executable])+' '+arguments,
                              capture_output=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn(b'SHOULD_NOT_RUN',result.stdout)

    def test_command_length_cap_precedes_launch(self):
        modules={'core.py':random.Random(109).randbytes(40000).hex(),
                 'win32.py':'VALUE=1','runner.py':'VALUE=1'}
        pins={key:hashlib.sha256(value.encode()).hexdigest() for key,value in modules.items()}
        with self.assertRaises(ValueError):
            runner.payload_arguments(modules,pins,{})

    def load_entry(self):
        path = ROOT/'outputs/relative-clock-align-109/execute.py'
        module = types.ModuleType('host109_entry')
        module.__file__ = str(self.root/'outputs/relative-clock-align-109/execute.py')
        exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
        return module

    def test_actual_missing_review_gate_precedes_operation_creation(self):
        entry = self.load_entry()
        with patch.object(sys,'argv',['execute.py','--apply']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(entry.main(),1)
        self.assertFalse((self.root/'outputs/relative-clock-align-109/execution').exists())

    def test_default_entry_only_reports_status(self):
        entry = self.load_entry()
        with patch.object(sys,'argv',['execute.py']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(entry.main(),0)
        self.assertFalse((self.root/'outputs/relative-clock-align-109/execution').exists())

    def test_entry_rejects_duplicate_or_nonfinite_metadata(self):
        entry = self.load_entry()
        for raw in ('{"unit":"109","unit":"099"}','{"a":NaN}','{"a":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                entry.strict_initial(raw)

    def query_fixture(self, rc):
        class Process:
            pid = 109
            stdout = io.BytesIO(b'failed-or-partial-query\xff')
            stderr = io.BytesIO(b'original-stderr\x00\xff')
            returncode = rc
            def poll(self): return self.returncode
            def kill(self): self.returncode = -9
            def wait(self, timeout): return self.returncode
        return Process()

    @staticmethod
    def buffered_fixture_state(stream):
        remaining = len(stream.getbuffer())-stream.tell()
        return remaining, remaining == 0

    def test_failed_os_query_preserves_both_original_byte_streams(self):
        process = self.query_fixture(23)
        fake = types.SimpleNamespace(tick_ms=lambda:1000)
        job = types.SimpleNamespace(assign_process=lambda pid:None)
        lease = core.Lease(0,1,1,'HOST_QUERY')
        with patch.object(runner,'win',fake), patch.object(runner,'trusted_ssh',lambda:sys.executable), \
             patch.object(runner,'pipe_state',self.buffered_fixture_state), \
             patch.object(runner.subprocess,'Popen',return_value=process), self.assertRaises(ValueError):
            runner.run_query('HOST','failure',self.out,lease,job)
        self.assertEqual((self.out/'failure-stdout.raw').read_bytes(),b'failed-or-partial-query\xff')
        self.assertEqual((self.out/'failure-stderr.raw').read_bytes(),b'original-stderr\x00\xff')
        self.assertTrue(json.loads((self.out/'failure-capture.json').read_bytes())['all_raw_captured'])

    def test_os_query_timeout_preserves_bytes_after_owned_process_kill(self):
        process = self.query_fixture(None)
        ticks = iter([1000]+[19500]*30)
        fake = types.SimpleNamespace(tick_ms=lambda:next(ticks))
        job = types.SimpleNamespace(assign_process=lambda pid:None)
        lease = core.Lease(0,1,1,'HOST_TIMEOUT')
        with patch.object(runner,'win',fake), patch.object(runner,'trusted_ssh',lambda:sys.executable), \
             patch.object(runner,'pipe_state',self.buffered_fixture_state), \
             patch.object(runner.subprocess,'Popen',return_value=process), self.assertRaises(ValueError):
            runner.run_query('HOST','timeout',self.out,lease,job)
        self.assertEqual(process.returncode,-9)
        self.assertEqual((self.out/'timeout-stderr.raw').read_bytes(),b'original-stderr\x00\xff')
        self.assertTrue(json.loads((self.out/'timeout-capture.json').read_bytes())['readers_terminal'])

    def test_success_exit_with_invalid_payload_retains_raw(self):
        process = self.query_fixture(0)
        fake = types.SimpleNamespace(tick_ms=lambda:1000)
        job = types.SimpleNamespace(assign_process=lambda pid:None)
        lease = core.Lease(0,1,1,'HOST_INVALID')
        with patch.object(runner,'win',fake), patch.object(runner,'trusted_ssh',lambda:sys.executable), \
             patch.object(runner,'pipe_state',self.buffered_fixture_state), \
             patch.object(runner.subprocess,'Popen',return_value=process), self.assertRaises(ValueError):
            runner.run_query('HOST','invalid',self.out,lease,job)
        self.assertEqual((self.out/'invalid-stdout.raw').read_bytes(),b'failed-or-partial-query\xff')

    def test_actual_print_child_raw_capture_has_no_thread_start_dependency(self):
        original = subprocess.Popen
        known = b'known-standard-error-109\r\n'
        code = "import sys;sys.stdout.buffer.write(b'{\"ok\":true}\\n');sys.stdout.flush();sys.stderr.buffer.write("+repr(known)+");sys.stderr.flush()"
        def child(*args, **kwargs):
            return original([sys.executable,'-I','-B','-c',code],**kwargs)
        origin = real_time.monotonic()
        fake = types.SimpleNamespace(tick_ms=lambda:100000+int((real_time.monotonic()-origin)*1000))
        start = fake.tick_ms()
        lease = core.Lease(start,1,1,'HOST_DIRECT_RAW')
        job = types.SimpleNamespace(assign_process=lambda pid:None)
        with patch.object(runner,'win',fake), patch.object(runner,'trusted_ssh',lambda:sys.executable), \
             patch.object(runner.subprocess,'Popen',side_effect=child), \
             patch.object(threading.Thread,'start',side_effect=RuntimeError('HOST reader start unavailable')) as blocked:
            result,_ = runner.run_query('HOST','thread-free',self.out,lease,job)
        self.assertEqual(result,{'ok':True})
        self.assertEqual(blocked.call_count,0)
        self.assertEqual((self.out/'thread-free-stderr.raw').read_bytes(),known)
        self.assertTrue(json.loads((self.out/'thread-free-capture.json').read_bytes())['all_raw_captured'])

    def test_independent_hard_fence_survives_soft_failure_and_broken_stderr(self):
        lease=core.Lease(1000,1,1,'HOST_HARD_FENCE')
        done=types.SimpleNamespace(wait=lambda seconds:False)
        state={}
        job=types.SimpleNamespace(terminate=lambda:(_ for _ in ()).throw(OSError('HOST terminate failed')))
        fake=types.SimpleNamespace(tick_ms=lambda:lease.hard_end,
                                   terminate_current=unittest.mock.Mock())
        bad_stderr=types.SimpleNamespace(write=lambda text:(_ for _ in ()).throw(OSError('HOST stderr failed')))
        class ExitObserved(BaseException):
            pass
        with patch.object(runner,'win',fake), patch.object(sys,'stderr',bad_stderr), \
             patch.object(runner.os,'_exit',side_effect=ExitObserved) as exit_call:
            runner.soft_stop(lease,done,job,state)
            with self.assertRaises(ExitObserved):
                runner.hard_stop(lease,done)
        self.assertTrue(state['soft_stop_failed'])
        fake.terminate_current.assert_called_once_with(124)
        exit_call.assert_called_once_with(124)

    def test_hard_supervisor_exception_itself_revokes_process(self):
        lease=core.Lease(1000,1,1,'HOST_HARD_ERROR')
        done=types.SimpleNamespace(wait=lambda seconds:False)
        fake=types.SimpleNamespace(tick_ms=lambda:(_ for _ in ()).throw(OSError('HOST tick failed')),
                                   terminate_current=unittest.mock.Mock())
        class ExitObserved(BaseException):
            pass
        with patch.object(runner,'win',fake), patch.object(runner.os,'_exit',side_effect=ExitObserved):
            with self.assertRaises(ExitObserved):
                runner.hard_stop(lease,done)
        fake.terminate_current.assert_called_once_with(124)

    def test_shared_query_stage_deadline_uses_same_independent_hard_fence(self):
        lease=core.Lease(1000,1,1,'HOST_STAGE_FENCE')
        done=types.SimpleNamespace(wait=lambda seconds:False)
        fake=types.SimpleNamespace(tick_ms=lambda:5000,terminate_current=unittest.mock.Mock())
        class ExitObserved(BaseException):
            pass
        with patch.object(runner,'win',fake), patch.object(runner.os,'_exit',side_effect=ExitObserved):
            with self.assertRaises(ExitObserved):
                runner.hard_stop(lease,done,{'stage_end':4000})
        fake.terminate_current.assert_called_once_with(124)

    def test_late_uac_return_never_substitutes_job_zero_for_process_terminal(self):
        approval,review=authority()
        clock={'tick':1000}
        waited=[]
        closed=[]
        def wait(ms):
            waited.append(ms)
            clock['tick']=181000
            return False
        child=types.SimpleNamespace(pid=101,created_filetime=10001,
            wait=wait,close=lambda:closed.append(True))
        class Job:
            name='Local\\HOST_LATE'
            @classmethod
            def create(cls,name):return cls()
            def active_count(self):return 0
            def terminate(self):clock['tick']=93000
            def close(self):return None
        def launch(exe,args):
            clock['tick']=92000
            return child
        fake=types.SimpleNamespace(tick_ms=lambda:clock['tick'],Job=Job,
              current_identity=lambda:{'pid':100,'created_filetime':10000},
              launch_elevated=launch)
        # Supervision threads are separately tested; avoid actual process exits.
        def no_supervisor(target,*args,**kwargs):
            if target in (runner.hard_stop,runner.soft_stop):
                return types.SimpleNamespace(start=lambda:None)
            return original_thread(*args,target=target,**kwargs)
        original_thread=threading.Thread
        def factory(*args,**kwargs):
            target=kwargs.pop('target',args[0] if args else None)
            return no_supervisor(target,**kwargs)
        with patch.object(runner,'win',fake), patch.object(runner,'payload_arguments',lambda *args:'HOST_NO_UAC'), \
             patch.object(runner,'Listener',lambda **kwargs:types.SimpleNamespace(address='HOST_PIPE',
                  accept=lambda:(_ for _ in ()).throw(OSError('HOST absent peer')),close=lambda:None)), \
             patch.object(threading,'Thread',side_effect=factory):
            result=runner.controller(self.context())
        self.assertEqual(result['status'],'IN_FLIGHT_UNKNOWN')
        self.assertFalse(result['terminal'])
        self.assertTrue(result['launch_returned_handle'])
        self.assertEqual(waited,[0])
        self.assertEqual(closed,[True])



def real_hard_probe():
    """Actual source hard deadline in an owned nonadmin controller child only."""
    import secrets
    win = sys.modules['ral109_win32']
    modules = {name:(HERE/(name+'.py')).read_bytes().decode('utf-8')
               for name in ('core','win32','runner')}
    compressed = base64.b64encode(zlib.compress(json.dumps(modules).encode())).decode()
    load = (
        "import base64,json,zlib,sys,types,subprocess,time,threading\n"
        f"sources=json.loads(zlib.decompress(base64.b64decode('{compressed}')))\n"
        "for name in ('core','win32','runner'):\n"
        " m=types.ModuleType('ral109_'+name);m.__file__='<medium-hard-probe>'\n"
        " sys.modules[m.__name__]=m;exec(compile(sources[name],m.__file__,'exec'),m.__dict__)\n"
        "w=sys.modules['ral109_win32'];r=sys.modules['ral109_runner'];c=sys.modules['ral109_core']\n"
        "def trap(*args):raise AssertionError('Clock/UAC forbidden in medium probe')\n"
        "w._get_api().SetSystemTime=trap;w.launch_elevated=trap\n"
    )
    nonce = secrets.token_hex(16)
    name = 'Local\\ral109-hard-probe-'+nonce
    worker = load + (
        f"e=w.Job.attach_self_and_close({name!r})\n"
        "print(json.dumps(e),flush=True)\n"
        "time.sleep(60)\n")
    parent = load + (
        f"job=w.Job.create({name!r})\n"
        "p=subprocess.Popen([sys.executable,'-I','-S','-B','-c',packet['worker']],stdout=subprocess.PIPE,stderr=subprocess.PIPE)\n"
        "e=json.loads(p.stdout.readline())\n"
        "assert e['assigned'] is True and e['worker_job_handle_closed'] is True\n"
        "assert job.contains(p.pid)\n"
        f"print(json.dumps({{'nonce':{nonce!r},'worker':e,'parent':w.current_identity()}}),flush=True)\n"
        "assert sys.stdin.buffer.read(1)==b'X'\n"
        "i=w.current_identity();lease=c.Lease(w.tick_ms()-180000,i['pid'],i['created_filetime'],'medium-hard')\n"
        "r.hard_stop(lease,threading.Event())\n"
        "raise AssertionError('Hard fence returned')\n")
    loader="import sys,json;packet=json.loads(sys.stdin.buffer.readline());exec(packet['parent'])"
    process = subprocess.Popen([sys.executable,'-I','-S','-B','-c',loader],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               bufsize=0,creationflags=subprocess.CREATE_NO_WINDOW)
    raw = {'stdout':bytearray(),'stderr':bytearray()}
    pinned = None
    try:
        packet=(json.dumps({'parent':parent,'worker':worker})+'\n').encode()
        position=0
        while position<len(packet):
            written=process.stdin.write(packet[position:])
            if not written:raise RuntimeError('Probe bootstrap input incomplete')
            position+=written
        process.stdin.flush()
        end = real_time.monotonic()+10
        while b'\n' not in raw['stdout']:
            if real_time.monotonic() >= end or process.poll() is not None:
                raise RuntimeError('Owned probe parent did not publish a frame')
            for channel in raw:
                amount,broken=runner.pipe_state(getattr(process,channel))
                if amount:raw[channel].extend(getattr(process,channel).read(amount))
            real_time.sleep(.005)
        frame=json.loads(bytes(raw['stdout']).splitlines()[0])
        assert frame['nonce']==nonce
        identity=frame['worker']['worker_identity']
        pinned=win.Process.open(identity['pid'],identity['created_filetime'])
        assert pinned.alive()
        process.stdin.write(b'X');process.stdin.flush();process.stdin.close()
        process.wait(timeout=8)
        assert process.returncode==124,'Actual hard fence exit code differs'
        assert pinned.wait(5000),'Contained owned worker not terminal after controller hard exit'
        for channel in raw:
            while True:
                amount,broken=runner.pipe_state(getattr(process,channel))
                if amount:raw[channel].extend(getattr(process,channel).read(amount))
                elif broken:break
                elif real_time.monotonic()>=end:raise RuntimeError('Probe raw not terminal')
                else:real_time.sleep(.005)
        return {'status':'ACTUAL_MEDIUM_SOURCE_HARD_FENCE_PASS','parent_returncode':124,
                'worker_terminal_on_pinned_handle':True,'worker':identity,
                'same_source_hard_stop':True,'last_job_handle_closed_by_parent_process_death':True,
                'source_sha256':{name:hashlib.sha256(value.encode('utf-8')).hexdigest()
                                 for name,value in modules.items()},
                'stdout_b64':base64.b64encode(raw['stdout']).decode(),
                'stderr_b64':base64.b64encode(raw['stderr']).decode(),
                'elevated':False,'UAC':0,'SetSystemTime':0,'SSH_native_CAN':0}
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=5)
        if pinned is not None:pinned.close()
        for stream in (process.stdin,process.stdout,process.stderr):
            if not stream.closed:stream.close()


if __name__ == '__main__':
    if sys.argv[1:] == ['--real-hard-probe']:
        print(json.dumps(real_hard_probe(),ensure_ascii=False))
    else:
        unittest.main(verbosity=2)
