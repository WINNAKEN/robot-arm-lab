"""HOST: python -X utf8 -I -B test_winjob.py; kernel: append --kernel.

All process termination probes are confined to newly created own subprocesses.
"""
import ctypes as C
from ctypes import wintypes as W
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch


HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('winjob110_under_test', HERE / 'winjob.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
ARTIFACTS = HERE.parents[2] / 'outputs' / 'single-host-controller-110' / 'A-kernel-fixtures'


class FakeKernel:
    def __init__(self, failure=None):
        self.failure, self.calls = failure, []
        self.running = self.killed = False

    def visit(self, name):
        self.calls.append(name)
        if self.failure == name:
            if name == 'create':
                raise w.SpawnFailed('injected CreateProcess FALSE')
            raise OSError('injected ' + name)

    def job(self):
        self.visit('job')
        return 11

    def create(self, argv, job, streams):
        self.visit('create')
        self.streams = streams
        return type('Process', (), dict(process=12, thread=13, pid=42))()

    def identity(self, *_):
        self.visit('identity')
        return 123456789

    def resume(self, *_):
        self.visit('resume')
        self.running = True
        self.streams[1].write(b'fake child raw\n')

    def wait(self, *_):
        self.visit('wait')
        return self.failure != 'timeout' or self.killed

    def active(self, *_):
        self.visit('active')
        return 0

    def exit_code(self, *_):
        self.visit('exit_code')
        return 124 if self.killed else 0

    def terminate(self, *_):
        self.visit('terminate')
        self.killed = True

    def close(self, *_):
        self.visit('close')


class HostTests(unittest.TestCase):
    def setUp(self):
        self.root = ARTIFACTS.parent / 'A-host-fixtures' / ('%s-%s' % (self._testMethodName, time.time_ns()))
        self.root.mkdir(parents=True, exist_ok=False)

    def call(self, kernel, **kwargs):
        with patch.object(w, 'Kernel', return_value=kernel):
            return w.run([sys.executable, '-c', 'print(1)'], self.root, 3, **kwargs)

    def test_normal_actual_caller(self):
        k = FakeKernel()
        result = self.call(k)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['policy_exit_code'], 0)
        self.assertEqual(result['actual_child_exit_code'], 0)
        self.assertEqual(result['child_creation_time'], 123456789)
        self.assertEqual(result['child_state'], 'REAPED')
        self.assertTrue(result['terminal'] and result['raw_complete'])
        self.assertEqual(result['job_active_after'], 0)
        self.assertLess(k.calls.index('identity'), k.calls.index('resume'))
        self.assertEqual((self.root / 'stdout.txt').read_bytes(), b'fake child raw\n')

    def test_identity_and_resume_faults_never_success(self):
        for fault in ('identity', 'resume'):
            with self.subTest(fault=fault):
                target = self.root / fault
                target.mkdir()
                k = FakeKernel(fault)
                with patch.object(w, 'Kernel', return_value=k):
                    result = w.run([sys.executable], target, 3)
                self.assertFalse(result['terminal'] or result['raw_complete'])
                self.assertEqual(result['policy_exit_code'], 125)
                self.assertIn('terminate', k.calls)
                self.assertTrue(result['errors'])

    def test_create_false_and_job_failure(self):
        for fault in ('job', 'create'):
            target = self.root / fault
            target.mkdir()
            k = FakeKernel(fault)
            with patch.object(w, 'Kernel', return_value=k):
                result = w.run([sys.executable], target, 3)
            self.assertIsNone(result['child_pid'])
            self.assertFalse(result['terminal'] or result['raw_complete'])
            self.assertNotIn('resume', k.calls)

    def test_timeout_actual_caller(self):
        result = self.call(FakeKernel('timeout'))
        self.assertTrue(result['timed_out'] and result['terminal'])
        self.assertEqual(result['policy_exit_code'], 124)
        self.assertEqual(result['actual_child_exit_code'], 124)
        self.assertEqual(result['job_active_after'], 0)

    def test_sender_main_thread_and_noninherit_parent(self):
        k = FakeKernel()
        def sender(stream, stdout_path, deadline):
            self.assertTrue(k.running)
            self.assertIs(threading.current_thread(), threading.main_thread())
            self.assertFalse(os.get_inheritable(stream.fileno()))
            self.assertTrue(stdout_path.is_file())
            self.assertGreater(deadline, time.monotonic())
        result = self.call(k, input_sender=sender)
        self.assertTrue(result['terminal'])

    def test_sender_error_retains_failure_and_kills(self):
        k = FakeKernel()
        def sender(*_):
            raise BrokenPipeError('sender failure')
        result = self.call(k, input_sender=sender)
        self.assertFalse(result['terminal'] or result['raw_complete'])
        self.assertIn('terminate', k.calls)
        self.assertIn('BrokenPipeError', result['errors'][0])

    def test_admission_before_any_capture_and_after_watcher(self):
        def admit():
            self.assertFalse((self.root / 'stdout.txt').exists())
            self.assertTrue(any(t.name.startswith('Thread-') and t.is_alive() for t in threading.enumerate()))
            raise PermissionError('not admitted')
        k = FakeKernel()
        result = self.call(k, admit=admit)
        self.assertFalse(result['terminal'])
        self.assertEqual(k.calls, [])
        self.assertFalse((self.root / 'stdout.txt').exists())

    def test_admission_can_create_output(self):
        out = self.root / 'after-admit'
        with patch.object(w, 'Kernel', return_value=FakeKernel()):
            result = w.run([sys.executable], out, 3, admit=lambda: out.mkdir())
        self.assertTrue(result['terminal'])

    def test_capture_exclusive_and_missing_out(self):
        (self.root / 'stdout.txt').write_bytes(b'original')
        k = FakeKernel()
        result = self.call(k)
        self.assertFalse(result['terminal'])
        self.assertEqual((self.root / 'stdout.txt').read_bytes(), b'original')
        self.assertNotIn('create', k.calls)
        with patch.object(w, 'Kernel', return_value=k):
            result = w.run([sys.executable], self.root / 'absent', 3)
        self.assertFalse(result['terminal'])
        self.assertFalse((self.root / 'absent').exists())

    def test_capture_fsync_failure_never_success(self):
        with patch.object(w.os, 'fsync', side_effect=OSError('capture cannot sync')):
            result = self.call(FakeKernel())
        self.assertFalse(result['terminal'] or result['raw_complete'])
        self.assertEqual(result['policy_exit_code'], 125)
        self.assertTrue(result['errors'])

    def test_reparse_path_refused_before_creation(self):
        k = FakeKernel()
        info = type('Info', (), {'st_file_attributes': 0x400})()
        with patch.object(w.Path, 'lstat', return_value=info):
            result = self.call(k)
        self.assertFalse(result['terminal'] or result['raw_complete'])
        self.assertEqual(k.calls, [])
        self.assertFalse((self.root / 'stdout.txt').exists())

    def test_signalled_but_late_work_is_timeout(self):
        k = FakeKernel()
        original_wait = k.wait
        def delayed_wait(*args):
            if not k.calls or k.calls[-1] != 'wait':
                time.sleep(.06)
            return original_wait(*args)
        k.wait = delayed_wait
        with patch.object(w, 'Kernel', return_value=k):
            result = w.run([sys.executable], self.root, .04, cleanup_s=1)
        self.assertTrue(result['terminal'] and result['timed_out'])
        self.assertEqual(result['actual_child_exit_code'], 0)
        self.assertEqual(result['policy_exit_code'], 124)

    def test_argument_guards(self):
        for kwargs in ({'stdin_path': 'x', 'input_sender': lambda *_: None},
                       {'cleanup_s': True}, {'cleanup_s': float('inf')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.call(FakeKernel(), **kwargs)
        with patch.object(w, 'Kernel', return_value=FakeKernel()):
            result = w.run(['python.exe'], self.root, 3)
        self.assertFalse(result['terminal'])

    def test_fence_actual_arm_and_join(self):
        with w.Fence(time.monotonic() + 3) as fence:
            self.assertTrue(fence.armed.is_set() and fence.thread.is_alive())
        self.assertFalse(fence.thread.is_alive())
        fence.close()


def isolated(mode, folder):
    """Executed only in a new test subprocess; never terminates its parent."""
    if mode == 'hard-fence':
        with w.Fence(time.monotonic() + .35):
            time.sleep(30)
    elif mode == 'diagnostic-fail':
        class BadText(Exception):
            def __str__(self):
                raise OSError('diagnostic channel failed')
        def admit():
            raise BadText()
        w.run([sys.executable], folder, .3, cleanup_s=.2, admit=admit)
    elif mode == 'unarmed-start':
        with patch.object(w.threading.Thread, 'start', return_value=None):
            with w.Fence(time.monotonic() + .3):
                raise AssertionError('admitted without watcher')
    elif mode == 'failed-join':
        fence = w.Fence(time.monotonic() + .4).__enter__()
        fence.stop.set = lambda: None
        fence.thread.join = lambda *_: None
        fence.close()
    elif mode == 'late-join':
        fence = w.Fence(time.monotonic() + .2).__enter__()
        original_join = fence.thread.join
        def late_join(*args):
            original_join(*args)
            time.sleep(.3)
        fence.thread.join = late_join
        fence.close()
    elif mode == 'fence-fallback':
        w.C.WinDLL = lambda *_a, **_k: (_ for _ in ()).throw(OSError('kernel unavailable'))
        w._die()
    elif mode in ('blocked-capture', 'blocked-sender', 'blocked-close', 'blocked-diagnostic'):
        if mode == 'blocked-capture':
            w._capture = lambda *_: time.sleep(30)
        if mode == 'blocked-close':
            class BlockClose(w.Kernel):
                def close(self, _):
                    time.sleep(30)
            w.Kernel = BlockClose
        sender = None
        if mode == 'blocked-sender':
            sender = lambda *_: time.sleep(30)
        if mode == 'blocked-diagnostic':
            class BlockingText(Exception):
                def __str__(self):
                    time.sleep(30)
                    return 'diagnostic delayed'
            def sender(*_):
                raise BlockingText()
        w.run([sys.executable, '-I', '-S', '-B', '-c', 'print("before block",flush=True)'],
              folder, .3, cleanup_s=.2, input_sender=sender)
    elif mode in ('wait', 'active', 'exit_code', 'close', 'terminate', 'pending-create'):
        k = FakeKernel(mode)
        if mode == 'terminate':
            k.wait = lambda *_: False
        if mode == 'pending-create':
            def pending(*_):
                time.sleep(30)
            k.create = pending
        w.Kernel = lambda: k
        w.run([sys.executable], folder, .3, cleanup_s=.2)
    elif mode == 'producer-death':
        original = w.Kernel
        class Producer(original):
            def resume(self, thread):
                super().resume(thread)
                # Main test holds the child process handle before this parent dies.
                while not (folder / 'held').exists():
                    time.sleep(.01)
                os._exit(77)
        w.Kernel = Producer
        source = 'import os,time,pathlib; pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(30)' % str(folder / 'pid')
        w.run([sys.executable, '-I', '-S', '-B', '-c', source], folder, 5)
    elif mode in ('suspended-last-close', 'pending-real-create'):
        original = w.Kernel
        class Suspended(original):
            def resume(self, thread):
                # Child has never executed; Job closes its last noninherited handle.
                self.close(self.saved_job)
                self.closed_job = True
                (folder / 'last-close').write_text('closed')
            def job(self):
                self.saved_job = super().job()
                self.closed_job = False
                return self.saved_job
            def active(self, job):
                if self.closed_job:
                    raise OSError('job handle intentionally closed')
                return super().active(job)
            def create(self, *args):
                pi = super().create(*args)
                creation = self.identity(pi.process, args[1])
                Path(folder / 'suspended.json').write_text(json.dumps({'pid': pi.pid, 'creation': creation}))
                while not (folder / 'held').exists():
                    time.sleep(.01)
                if mode == 'pending-real-create':
                    time.sleep(30)
                return pi
        w.Kernel = Suspended
        w.run([sys.executable, '-c', 'raise SystemExit(99)'], folder, 2, cleanup_s=.3)
    elif mode == 'nested-job':
        inner = folder / 'inner'
        inner.mkdir()
        result = w.run([sys.executable, '-I', '-S', '-B', '-c', 'print("nested")'], inner, 3)
        print(json.dumps(result), flush=True)
        return
    elif mode == 'real-query-fail':
        class QueryFailure(w.Kernel):
            def active(self, _):
                raise OSError('injected actual child query failure')
        w.Kernel = QueryFailure
        w.run([sys.executable, '-c', 'print("actual before query failure")'], folder, .5, cleanup_s=.3)
    else:
        raise ValueError(mode)
    raise AssertionError('isolated kill mode unexpectedly returned: ' + mode)


def python_args(*tail):
    return [sys.executable, '-X', 'utf8', '-I', '-B', str(Path(__file__).absolute()), *tail]


@unittest.skipUnless('--kernel' in sys.argv and os.name == 'nt', 'explicit --kernel Windows probes')
class KernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        cls.batch = ARTIFACTS / ('run-%s-%s' % (time.time_ns(), os.getpid()))
        cls.batch.mkdir()
        (cls.batch / 'environment.json').write_text(json.dumps({
            'test_owner_pid': os.getpid(), 'python': sys.executable,
            'is_administrator': bool(C.WinDLL('shell32').IsUserAnAdmin()),
            'scope': 'new own local subprocesses only; no remote/SDK/CAN/clock mutation',
        }, indent=2))

    def setUp(self):
        self.folder = self.batch / self._testMethodName
        self.folder.mkdir()

    def child(self, source, **kwargs):
        return w.run([sys.executable, '-I', '-S', '-B', '-c', source], self.folder, 4, **kwargs)

    def save(self, result):
        (self.folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')

    def test_print_only_real_kernel(self):
        result = self.child('print("actual print-only child", flush=True)')
        self.save(result)
        self.assertEqual(result['errors'], [])
        self.assertTrue(result['terminal'] and result['raw_complete'])
        self.assertEqual(result['child_state'], 'REAPED')
        self.assertEqual(result['actual_child_exit_code'], 0)
        self.assertEqual(result['job_active_after'], 0)
        self.assertEqual((self.folder / 'stdout.txt').read_bytes(), b'actual print-only child\r\n')

    def test_stdin_file_positive(self):
        inp = self.folder / 'input.bin'
        inp.write_bytes(b'file-input\x00payload')
        result = self.child('import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())', stdin_path=inp)
        self.save(result)
        self.assertTrue(result['terminal'])
        self.assertEqual((self.folder / 'stdout.txt').read_bytes(), inp.read_bytes())

    def test_input_sender_positive(self):
        def sender(stream, stdout, deadline):
            while b'READY' not in stdout.read_bytes():
                if time.monotonic() >= deadline:
                    raise TimeoutError('no READY')
                time.sleep(.01)
            stream.write(b'LIVE\n')
        result = self.child('import sys; print("READY",flush=True); print(sys.stdin.readline().strip(),flush=True)', input_sender=sender)
        self.save(result)
        self.assertTrue(result['terminal'])
        self.assertIn(b'LIVE', (self.folder / 'stdout.txt').read_bytes())

    def test_timeout_and_descendant_active_zero(self):
        source = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-I","-S","-B","-c","import time;time.sleep(30)"]); print("started",flush=True); time.sleep(30)'
        result = w.run([sys.executable, '-I', '-S', '-B', '-c', source], self.folder, .4, cleanup_s=2)
        self.save(result)
        self.assertTrue(result['timed_out'] and result['terminal'])
        self.assertEqual(result['job_active_after'], 0)
        self.assertEqual(result['policy_exit_code'], 124)

    def test_primary_exit_remaining_descendant_reaped(self):
        source = 'import subprocess,sys; subprocess.Popen([sys.executable,"-I","-S","-B","-c","import time;time.sleep(30)"]); print("parent exit",flush=True)'
        result = self.child(source)
        self.save(result)
        self.assertTrue(result['terminal'])
        self.assertEqual(result['actual_child_exit_code'], 0)
        self.assertEqual(result['job_active_after'], 0)

    def test_nested_job_positive(self):
        result = w.run(python_args('--isolate', 'nested-job', '--out', str(self.folder)), self.folder, 6)
        # Nested helper exits by the explicit assertion after printing its receipt.
        self.save(result)
        nested = json.loads((self.folder / 'stdout.txt').read_text().splitlines()[0])
        self.assertTrue(nested['terminal'])
        self.assertEqual(nested['job_active_after'], 0)
        self.assertEqual(nested['actual_child_exit_code'], 0)

    def test_isolated_hard_and_fault_fences(self):
        modes = ('hard-fence', 'diagnostic-fail', 'unarmed-start', 'failed-join', 'late-join', 'fence-fallback', 'wait', 'active',
                 'exit_code', 'close', 'terminate', 'pending-create', 'real-query-fail',
                 'blocked-capture', 'blocked-sender', 'blocked-close', 'blocked-diagnostic')
        for mode in modes:
            with self.subTest(mode=mode):
                folder = self.folder / mode
                folder.mkdir()
                start = time.monotonic()
                result = subprocess.run(python_args('--isolate', mode, '--out', str(folder)),
                                        capture_output=True, timeout=6)
                (folder / 'outer-stdout.raw').write_bytes(result.stdout)
                (folder / 'outer-stderr.raw').write_bytes(result.stderr)
                (folder / 'observation.json').write_text(json.dumps({'returncode': result.returncode,
                    'elapsed_s': time.monotonic() - start, 'mode': mode}))
                self.assertEqual(result.returncode, 124)

    def hold_and_confirm(self, mode, metadata_name):
        producer = subprocess.Popen(python_args('--isolate', mode, '--out', str(self.folder)),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: producer.poll() is None and producer.kill())
        until = time.monotonic() + 4
        metadata = self.folder / metadata_name
        while not metadata.exists() and time.monotonic() < until:
            time.sleep(.01)
        self.assertTrue(metadata.exists(), 'producer did not publish child identity')
        info = json.loads(metadata.read_text()) if metadata.suffix == '.json' else {'pid': int(metadata.read_text())}
        kernel = w.Kernel()
        kernel.k.OpenProcess.restype = W.HANDLE
        kernel.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        handle = kernel.k.OpenProcess(0x100000 | 0x1000, False, info['pid'])
        self.assertTrue(handle)
        try:
            times = [W.FILETIME() for _ in range(4)]
            kernel.check(kernel.k.GetProcessTimes(handle, *[C.byref(t) for t in times]))
            creation = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            if 'creation' in info:
                self.assertEqual(creation, info['creation'])
            self.assertFalse(kernel.wait(handle, 0))
            (self.folder / 'held').write_text(str(creation))
            if mode == 'suspended-last-close':
                while not (self.folder / 'last-close').exists() and time.monotonic() < until:
                    time.sleep(.01)
                self.assertTrue((self.folder / 'last-close').exists())
                self.assertTrue(kernel.wait(handle, .5), 'suspended child survived last Job handle close')
                self.assertIsNone(producer.poll(), 'parent already dead; last-close observation ambiguous')
            stdout, stderr = producer.communicate(timeout=5)
            (self.folder / 'producer-stdout.raw').write_bytes(stdout)
            (self.folder / 'producer-stderr.raw').write_bytes(stderr)
            self.assertTrue(kernel.wait(handle, 2), 'owned child survived producer death/last close')
            exit_code = kernel.exit_code(handle)
            self.assertNotEqual(exit_code, 259)
            self.save({'producer_exit': producer.returncode, 'child_pid': info['pid'],
                       'held_creation_time': creation, 'held_child_exit_code': exit_code,
                       'held_child_signalled': True, 'mode': mode})
        finally:
            kernel.close(handle)

    def test_producer_death_owned_held_child(self):
        self.hold_and_confirm('producer-death', 'pid')

    def test_suspended_last_job_handle_close(self):
        self.hold_and_confirm('suspended-last-close', 'suspended.json')

    def test_create_return_pending_owned_held_child(self):
        self.hold_and_confirm('pending-real-create', 'suspended.json')


if __name__ == '__main__':
    if '--isolate' in sys.argv:
        mode = sys.argv[sys.argv.index('--isolate') + 1]
        folder = Path(sys.argv[sys.argv.index('--out') + 1])
        isolated(mode, folder)
    else:
        unittest.main(argv=[sys.argv[0]] + [a for a in sys.argv[1:] if a != '--kernel'], verbosity=2)
