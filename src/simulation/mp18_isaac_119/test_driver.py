"""119 owner HOST tests. Only local stdlib fixture children; SSH/Isaac/hardware never start."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import types
import time
import unittest
import uuid
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT/'outputs/mp18-isaac-119/C'
s = importlib.util.spec_from_file_location('driver119host', HERE/'driver.py')
D = importlib.util.module_from_spec(s)
sys.modules[s.name] = D
s.loader.exec_module(D)


def fixture_payload(entries=None, delay=0.):
    run_id, nonce = uuid.uuid4().hex, uuid.uuid4().hex
    fake = ("from pathlib import Path\nimport zipfile\n"
            "def remote_supervise(run,deadline):\n"
            " import time;time.sleep("+str(delay)+")\n"
            " p=Path(run)/'records.zip'\n"
            " with zipfile.ZipFile(p,'x') as z:z.writestr('HOST_ONLY.txt','No SDK or network')\n"
            " return p\n").encode()
    files = entries if entries is not None else {'source/driver.py': fake}
    job = {'unit': 119, 'run_id': run_id, 'nonce': nonce, 'hardware_approved': False,
           'inputs': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
    raw_job = json.dumps(job).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('job.json', raw_job)
        for name, raw in files.items():
            z.writestr('input/'+name, raw)
    data = buffer.getvalue()
    base = OUT/'fixtures'/uuid.uuid4().hex/'robot-arm-lab/119/runs'
    args = {'run_id': run_id, 'nonce': nonce, 'driver_sha256': hashlib.sha256(fake).hexdigest(),
            'bundle_sha256': hashlib.sha256(data).hexdigest(), 'bundle_bytes': len(data),
            'job_sha256': hashlib.sha256(raw_job).hexdigest(), 'remote_root': base.as_posix(), 'remaining': 1000.}
    identity = {key: args[key] for key in ('nonce', 'run_id', 'driver_sha256', 'bundle_sha256', 'bundle_bytes', 'job_sha256')}
    go = json.dumps(dict(identity, kind='GO')).encode()+b'\n'
    return args, data, go


class OwnerTests(unittest.TestCase):
    def test_01_delayed_remote_deadline_never_extends_global(self):
        for remaining in (623., 1000., 2700.):
            for queue in (0., 1., 19.999, 20.):
                # Same physical elapsed time represented in two different monotonic epochs.
                local_start, remote_epoch = 500., 99999.
                remote_ready = remote_epoch+queue
                end = D.lease_end(remote_ready, remaining)
                physical_end = local_start+(end-remote_epoch)
                self.assertLessEqual(physical_end, local_start+remaining+1e-9)
        for remaining in (0., 20., 622., float('inf'), float('nan')):
            with self.subTest(remaining=remaining), self.assertRaises(ValueError):
                D.lease_end(1., remaining)

    def test_02_payload_hash_and_path_rejection(self):
        args, raw, _ = fixture_payload()
        run = Path(args['remote_root'])/args['run_id']
        with self.assertRaisesRegex(ValueError, 'job hash'):
            D._unpack_payload(raw, run, '0'*64)
        self.assertFalse(run.exists())
        bad_args, bad_raw, _ = fixture_payload({'../escape': b'host only'})
        with self.assertRaises(ValueError):
            D._unpack_payload(bad_raw, Path(bad_args['remote_root'])/bad_args['run_id'], bad_args['job_sha256'])

    def test_03_closed_go_and_eof(self):
        args, raw, go = fixture_payload()
        cases = [b'', go.replace(args['nonce'].encode(), b'0'*32)+raw]
        for payload in cases:
            code = D.bootstrap_code(args)
            p = subprocess.run([sys.executable, '-I', '-B', '-c', code], input=payload,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse((Path(args['remote_root'])/args['run_id']).exists())
            self.assertIn(b'READY', p.stdout)

    def test_04_complete_one_stream_host_fixture(self):
        args, raw, go = fixture_payload(delay=20.2)
        p = subprocess.run([sys.executable, '-I', '-B', '-c', D.bootstrap_code(args)], input=go+raw,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
        self.assertEqual(p.returncode, 0, p.stderr.decode('utf8', 'replace'))
        ready, header, archive = p.stdout.split(b'\n', 2)
        ready, header = json.loads(ready), json.loads(header)
        self.assertEqual(ready['kind'], 'READY')
        self.assertEqual(header['kind'], 'RESULT')
        self.assertEqual(header['nonce'], args['nonce'])
        self.assertEqual(len(archive), header['bytes'])
        self.assertEqual(hashlib.sha256(archive).hexdigest(), header['sha256'])
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(z.read('HOST_ONLY.txt'), b'No SDK or network')

    def test_05_admission_fence_rejects_no_go_in_real_time(self):
        args, _, _ = fixture_payload()
        started = time.monotonic()
        p = subprocess.Popen([sys.executable, '-I', '-B', '-c', D.bootstrap_code(args)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Keep stdin open but provide no GO. Actual monitor, not a mocked clock, must terminate it.
        code = p.wait(timeout=24)
        stdout, stderr = p.communicate(timeout=2)
        elapsed = time.monotonic()-started
        self.assertEqual(code, 124, stderr.decode('utf8', 'replace'))
        self.assertGreaterEqual(elapsed, 19.)
        self.assertLess(elapsed, 24.)
        self.assertIn(b'READY', stdout)
        self.assertFalse((Path(args['remote_root'])/args['run_id']).exists())

    def test_06_actual_result_identity_seal_and_gate_rejections(self):
        # HOST-only synthetic failed child. Never creates a native-result in the real OUT root.
        fixture = OUT/'consumer-fixtures'/uuid.uuid4().hex
        run, destination = fixture/'run', fixture/'retrieved'
        run.mkdir(parents=True); destination.mkdir()
        def save(path, value):
            path.write_text(json.dumps(value), encoding='utf8')
        job = {'inputs': {'source/config.json': 'HOST_ONLY'}}
        save(run/'job.json', job)
        with zipfile.ZipFile(run/'bundle.zip', 'x') as z:
            z.writestr('input/source/config.json', '{}')
        record = {'run_id': 'HOST_ONLY', 'job_sha256': 'HOST_ONLY'}
        report = dict(record, pid=123, phases=[{'name': n, 'status': s} for n, s in zip(
            ('import', 'hold', 'small', 'large'), ('PASS', 'FAIL', 'NOT_RUN', 'NOT_RUN'))])
        child = dict(record, raw_complete=True, terminal=True, child_state='REAPED',
                     job_active_after=0, child_pid=123, actual_child_exit_code=1, timed_out=False)
        terminal = dict(record, pid=123, status='FAILED', code=1)
        def restore(r=report, c=child, t=terminal):
            save(destination/'report.json', r)
            save(destination/'process.json', c)
            save(destination/'terminal.json', dict(t, files_sha256={'report.json': D.sha(destination/'report.json')}))
            save(destination/'recovery-seal.json', dict(record, unit=119, actual_child_pid=c['child_pid'],
                 files_sha256={p.name: D.sha(p) for p in destination.iterdir() if p.is_file() and p.name != 'recovery-seal.json'}))
        prior = D.OUT
        prior_payload = D.verified_payload
        D.OUT = fixture
        # Lifetime/phase fixture isolates these predicates; real payload guard is exercised separately below.
        D.verified_payload = lambda r, rec: (job, {'source/config.json': b'{}'}, {})
        try:
            restore()
            self.assertEqual(D.verify_native_result(run, record, destination), 2)
            self.assertEqual(D.read(fixture/'native-result.json')['status'], 'FAIL')
            for bad_child in (dict(child, child_pid=124), dict(child, raw_complete=False), dict(child, job_active_after=1)):
                restore(c=bad_child)
                with self.assertRaisesRegex(ValueError, 'lifetime identity'):
                    D.verify_native_result(run, record, destination)
            restore()
            save(destination/'report.json', {'unsealed': True})
            with self.assertRaisesRegex(ValueError, 'artifact seal'):
                D.verify_native_result(run, record, destination)
            bad_report = copy.deepcopy(report)
            bad_report['phases'][2]['status'] = 'PASS'
            restore(r=bad_report)
            with self.assertRaisesRegex(ValueError, 'later phase'):
                D.verify_native_result(run, record, destination)
            partial_all_pass = copy.deepcopy(report)
            for p in partial_all_pass['phases']:
                p['status'] = 'PASS'
            restore(r=partial_all_pass)
            self.assertEqual(D.verify_native_result(run, record, destination), 2)
            consumed = D.read(fixture/'native-result.json')
            self.assertEqual(consumed['status'], 'FAIL')
            self.assertEqual(consumed['phases'][-1]['status'], 'FAIL')
            self.assertEqual(consumed['capture_provenance'], 'REAPED_PARENT_RECOVERY_SEAL_PARTIAL')
            restore()
            recovery = D.read(destination/'recovery-seal.json')
            del recovery['files_sha256']['report.json']
            save(destination/'recovery-seal.json', recovery)
            with self.assertRaisesRegex(ValueError, 'recovery inventory'):
                D.verify_native_result(run, record, destination)
        finally:
            D.OUT = prior
            D.verified_payload = prior_payload

    def test_07_consumed_bundle_and_member_authority_before_execution(self):
        args, raw, _ = fixture_payload({'ref/sdk.py': b'raise AssertionError("HOST code must never execute")'})
        run = OUT/'payload-fixtures'/uuid.uuid4().hex
        run.mkdir(parents=True)
        (run/'bundle.zip').write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            (run/'job.json').write_bytes(z.read('job.json'))
        record = dict(args)
        original_gate, original_prepared = D._review_gate, D.verify_prepared
        # Gate/current-pin wiring stays in product; this fixture isolates original bundle/member bytes.
        D._review_gate, D.verify_prepared = lambda: None, lambda r, rec, cfg: None
        try:
            self.assertEqual(D.verified_payload(run, record)[1]['ref/sdk.py'], b'raise AssertionError("HOST code must never execute")')
            forged = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(forged, 'w') as new:
                for info in old.infolist():
                    new.writestr(info.filename, b'HOST altered executable bytes' if info.filename == 'input/ref/sdk.py' else old.read(info))
            altered = forged.getvalue()
            (run/'bundle.zip').write_bytes(altered)
            with self.assertRaisesRegex(ValueError, 'bundle hash'):
                D.verified_payload(run, record)
            updated = dict(record, bundle_sha256=hashlib.sha256(altered).hexdigest(), bundle_bytes=len(altered))
            with self.assertRaisesRegex(ValueError, 'member hash'):
                D.verified_payload(run, updated)
            (run/'bundle.zip').write_bytes(raw)
            (run/'job.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'job hash'):
                D.verified_payload(run, record)
        finally:
            D._review_gate, D.verify_prepared = original_gate, original_prepared


if __name__ == '__main__':
    unittest.main(verbosity=2)
