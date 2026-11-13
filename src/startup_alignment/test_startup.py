"""Actual CLI copied-root tests and explicitly repinned child protocol fixtures."""
from pathlib import Path
import ctypes
import hashlib
import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = Path(os.environ.get('STARTUP_PARENT_MODULE', str(HERE/'runner.py')))
CONTRACT_RAW = (HERE/'contract.json').read_bytes()
CONTRACT = json.loads(CONTRACT_RAW)
WORKER = (HERE/'worker.py').read_bytes()
OUTPUT = 'outputs/supervised-alignment-v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class StartupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in CONTRACT['inputs']:
            target = self.root/path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/path, target)
        directory = self.root/'src/startup_alignment'
        directory.mkdir(parents=True)
        self.runner = directory/'runner.py'
        self.runner_raw = PARENT.read_bytes()
        self.runner.write_bytes(self.runner_raw)
        (directory/'worker.py').write_bytes(WORKER)
        (directory/'contract.json').write_bytes(CONTRACT_RAW)
        self.assertEqual(self.cli('build').returncode, 0)
        self.assertEqual(self.state()['status'], 'PASS')

    def cli(self, action):
        return subprocess.run([sys.executable, '-I', str(self.runner), action,
            '--root', str(self.root)], cwd=self.root.parent, capture_output=True, timeout=25)

    def state(self):
        return json.loads((self.root/OUTPUT/'current.json').read_bytes())

    def bundle(self):
        return self.root/OUTPUT/'runs'/self.state()['run_id']

    def failure(self):
        previous = self.state()['run_id']
        result = self.cli('build')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.state()['status'], 'FAILED', result.stderr)
        self.assertNotEqual(self.state()['run_id'], previous)
        self.assertTrue(self.state()['reason'])
        self.assertNotEqual(self.cli('verify').returncode, 0)
        return result

    def parent_module(self):
        spec = importlib.util.spec_from_file_location('copied_supervisor', self.runner)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def repin_fixture(self, worker):
        # Test-only copied trust root. No production file or production pin changes.
        directory = self.runner.parent
        (directory/'worker.py').write_bytes(worker)
        contract = dict(CONTRACT, worker_sha256=sha(worker))
        raw = (json.dumps(contract, indent=2)+'\n').encode()
        (directory/'contract.json').write_bytes(raw)
        original_pin = sha(CONTRACT_RAW).encode()
        self.assertEqual(self.runner_raw.count(original_pin), 1)
        self.runner.write_bytes(self.runner_raw.replace(original_pin, sha(raw).encode()))

    def real_worker_then(self, code):
        prefix = 'import sys, json, hashlib\nfrom pathlib import Path\n'
        prefix += 'exec(compile('+repr(WORKER)+', __file__, "exec"), globals())\n'
        prefix += 'bundle = Path(sys.argv[sys.argv.index("--bundle")+1])\n'
        return (prefix+code+'\n').encode()

    def test_original_missing_core_cli_and_recovery(self):
        core = self.root/CONTRACT['core_path']
        raw = core.read_bytes()
        core.unlink()
        self.failure()
        self.assertEqual(self.state()['child_exit_code'], 1)
        diagnostic = (self.bundle()/'child-stderr.bin').read_bytes()
        self.assertIn(b'StopIteration', diagnostic)
        core.write_bytes(raw)
        self.assertNotEqual(self.cli('verify').returncode, 0)
        self.assertEqual(self.cli('build').returncode, 0)
        self.assertEqual(self.cli('verify').returncode, 0)
        held = core.with_suffix('.held')
        core.rename(held)
        self.failure()
        held.rename(core)
        self.assertNotEqual(self.cli('verify').returncode, 0)

    def test_all_repository_dependency_missing_and_tampered(self):
        paths = [CONTRACT['asset_path'], CONTRACT['approval_path'], CONTRACT['receipt_path'],
                 CONTRACT['kin_path'], 'src/startup_alignment/worker.py', 'src/startup_alignment/contract.json']
        for path in paths:
            with self.subTest(path=path):
                target = self.root/path
                raw = target.read_bytes()
                target.unlink()
                self.failure()
                target.write_bytes(raw)
                self.assertNotEqual(self.cli('verify').returncode, 0)
        for path in [CONTRACT['core_path'], CONTRACT['asset_path'], 'src/startup_alignment/worker.py',
                     'src/startup_alignment/contract.json']:
            with self.subTest(tampered=path):
                target = self.root/path
                raw = target.read_bytes()
                target.write_bytes(raw+b'\ninvalid syntax !\n')
                self.failure()
                target.write_bytes(raw)
        native = self.root/'models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft'
        native.write_bytes(b'bad zip')
        self.failure()

    @unittest.skipUnless(os.name == 'nt', 'Windows exclusive file read denial')
    def test_real_cli_read_sharing_error(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(self.root/CONTRACT['core_path']), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            self.failure()
            self.assertIn(b'PermissionError', (self.bundle()/'child-stderr.bin').read_bytes())
        finally:
            kernel.CloseHandle(handle)

    def test_exit_nonzero_after_valid_bound_response(self):
        self.repin_fixture(self.real_worker_then('raise SystemExit(7)'))
        self.failure()
        self.assertEqual(self.state()['child_exit_code'], 7)
        self.assertTrue((self.bundle()/'response.json').exists())
        self.assertTrue((self.bundle()/'report.json').exists())

    def test_actual_child_syntax_import_exit_and_timeout(self):
        for worker, expected in ((b'not valid syntax !', b'SyntaxError'),
                                 (b'import intentionally_missing_startup_dependency', b'ModuleNotFoundError'),
                                 (b'raise SystemExit(4)', b''), (b'pass', b'')):
            with self.subTest(worker=worker):
                self.repin_fixture(worker)
                self.failure()
                self.assertIn(expected, (self.bundle()/'child-stderr.bin').read_bytes())
        self.repin_fixture(b'import time\ntime.sleep(20)\n')
        self.failure()
        self.assertEqual(self.state()['reason'], 'TimeoutExpired')

    def test_actual_cli_response_and_report_rejection(self):
        cases = {
            'missing': '(bundle/"response.json").unlink()',
            'response_shape': '(bundle/"response.json").write_text("[]")',
            'response_scope': 'response["scope"] = "PHYSICAL_APPROVED"',
            'response_run': 'response["run_id"] = "0"*32',
            'response_source': 'response["sources"] = {}',
            'response_hash': 'response["files"]["report.json"] = "0"*64',
            'report_count': 'report["joints"].pop()',
            'report_scope': 'report["scope"] = "all CAD verified"',
            'report_hardware': 'report["hardware_approved"] = True',
            'report_zero': 'report["joints"][0]["native_saved_value_rad"] = 1',
            'report_error': 'report["joints"][0]["origin_max_error_mm"] = 1',
            'report_axis': 'report["joints"][0]["native_axis_world"] = []',
            'report_geometric': 'report["joints"][0]["canonical_delta_at_geometric_zero_deg"] = True',
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                if name in ('missing', 'response_shape'):
                    code = change
                else:
                    code = 'response = json.loads((bundle/"response.json").read_bytes())\n'
                    code += 'report = json.loads((bundle/"report.json").read_bytes())\n'+change+'\n'
                    if name.startswith('report_'):
                        code += 'raw = json.dumps(report).encode()\n(bundle/"report.json").write_bytes(raw)\n'
                        code += 'response["files"]["report.json"] = hashlib.sha256(raw).hexdigest()\n'
                    code += '(bundle/"response.json").write_text(json.dumps(response))'
                self.repin_fixture(self.real_worker_then(code))
                self.failure()

    def test_first_dependency_read_observes_building(self):
        module = self.parent_module()
        original, seen = module.read, []
        def observe(path, *args, **kwargs):
            if not seen:
                seen.append(self.state()['status'])
                self.assertEqual(seen[0], 'BUILDING')
            return original(path, *args, **kwargs)
        with patch.object(module, 'read', side_effect=observe):
            self.assertEqual(module.build(self.root)['status'], 'PASS')
        self.assertEqual(seen, ['BUILDING'])

    def test_id_allocation_marker_write_and_final_verify_faults(self):
        module = self.parent_module()
        with patch.object(module.uuid, 'uuid4', side_effect=OSError('ID unavailable')):
            with self.assertRaises(OSError):
                module.build(self.root)
        self.assertEqual(self.state()['status'], 'FAILED')
        self.assertIsNone(self.state()['run_id'])
        original = module.atomic
        for target in ('BUILDING', 'PASS'):
            def failing(path, value):
                if value['status'] == target:
                    raise OSError('publication failed')
                original(path, value)
            with patch.object(module, 'atomic', side_effect=failing):
                with self.assertRaises(OSError):
                    module.build(self.root)
            self.assertEqual(self.state()['status'], 'FAILED')
        sentinel = ArithmeticError('final verify fault')
        with patch.object(module, 'verify', side_effect=sentinel):
            with self.assertRaises(ArithmeticError) as caught:
                module.build(self.root)
        self.assertIs(caught.exception, sentinel)
        self.assertEqual(self.state()['status'], 'FAILED')

    def test_readonly_verify_identity_and_no_import(self):
        current = self.state()
        bundle = self.bundle()
        for path in ('report.json', 'response.json', 'worker.py', 'contract.json', 'manifest.json'):
            target = bundle/path
            raw = target.read_bytes()
            target.write_bytes(raw+b' ')
            self.assertNotEqual(self.cli('verify').returncode, 0)
            self.assertEqual(self.state(), current)
            target.write_bytes(raw)
        core = self.root/CONTRACT['core_path']
        core.unlink()
        result = self.cli('verify')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'StopIteration', result.stderr)
        self.assertEqual(self.state(), current)
        self.failure()

    def test_exact_core_bytes_ignore_untrusted_bytecode_cache(self):
        core = self.root/CONTRACT['core_path']
        cache = Path(importlib.util.cache_from_source(str(core)))
        py_compile.compile(str(core), cfile=str(cache), doraise=True)
        header = cache.read_bytes()[:16]
        surrogate = self.root/'cache_probe.py'
        surrogate.write_text('raise RuntimeError("UNTRUSTED_PYC_PROBE")\n')
        payload = self.root/'payload.pyc'
        py_compile.compile(str(surrogate), cfile=str(payload), doraise=True)
        cache.write_bytes(header+payload.read_bytes()[16:])
        probe = ('import importlib.util; p='+repr(str(core))+'; '
            's=importlib.util.spec_from_file_location("cache_probe_core",p); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m)')
        unsafe = subprocess.run([sys.executable, '-I', '-B', '-c', probe], capture_output=True)
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertIn(b'UNTRUSTED_PYC_PROBE', unsafe.stderr)
        self.assertEqual(sha(core.read_bytes()), CONTRACT['core_sha256'])
        result = self.cli('build')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b'UNTRUSTED_PYC_PROBE', (self.bundle()/'child-stderr.bin').read_bytes())
        self.assertEqual(self.cli('verify').returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
