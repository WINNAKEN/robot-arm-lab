"""Regression checks plus actual recorded native CLI observations; no hardware."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = Path(os.environ.get('ND_MODULE', str(Path(__file__).with_name('measure.py'))))
spec = importlib.util.spec_from_file_location('direction_measure', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DirectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = m.parse(m.read(ROOT/m.OUTPUT/'current.json'))
        cls.bundle = ROOT/m.OUTPUT/'runs'/cls.current['run_id']
        cls.core = m.load_core(ROOT, m.read(ROOT/m.CORE))
        cls.layout = cls.core.decode(m.read(ROOT/m.KIN))

    def test_recorded_actual_cli_direction(self):
        results = []
        for index, (name, degrees) in enumerate(m.cases()):
            raw = m.parse(m.read(self.bundle/f'case-{index:02d}-response.json'))
            result = m.check_pose(raw, degrees, self.core, self.layout)
            direct = all(v['matches'] for v in result['official_plus_one'].values())
            reverse = all(v['matches'] for v in result['diagnostic_all_signs_reversed_NOT_ADOPTED'].values())
            self.assertTrue(direct, name)
            self.assertEqual(reverse, name == 'zero', name)
            self.assertTrue(result['return_to_zero'])
            results.append(result)
        self.assertEqual(len(results), 27)

    def test_rotation_guard(self):
        rotated = [[0., -1., 0., 0.], [1., 0., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]
        self.assertTrue(m.compare(m.I4, m.I4)['matches'])
        self.assertFalse(m.compare(rotated, m.I4)['matches'])

    def test_translation_guard(self):
        translated = copy.deepcopy(m.I4)
        translated[0][3] = 1.
        self.assertTrue(m.compare(m.I4, m.I4)['matches'])
        self.assertFalse(m.compare(translated, m.I4)['matches'])

    def test_invalid_measurements_and_solver_states(self):
        raw = m.parse(m.read(self.bundle/'case-01-response.json'))
        variants = []
        for side in ('a', 'b'):
            bad = copy.deepcopy(raw)
            bad[11]['joints'][0][side]['resolves'] = False
            variants.append(bad)
        bad = copy.deepcopy(raw); bad[12]['joints'][0]['values'][0]['value'] = 0.; variants.append(bad)
        bad = copy.deepcopy(raw); bad[12]['floating'] = [{}]; variants.append(bad)
        bad = copy.deepcopy(raw); bad[9]['errors'] = ['failure']; variants.append(bad)
        bad = copy.deepcopy(raw); bad[3]['moved'] = False; variants.append(bad)
        bad = copy.deepcopy(raw); bad[3]['stopped_by_loop'] = {}; variants.append(bad)
        bad = copy.deepcopy(raw); bad[10]['components'][0]['children'][1]['transform'][0][0] = 2.; variants.append(bad)
        bad = copy.deepcopy(raw); bad[20]['components'][0]['children'][1]['transform'][3][0] = 1.; variants.append(bad)
        bad = copy.deepcopy(raw)
        bad[10]['components'][0]['children'][1]['transform'] = list(map(list, zip(*bad[10]['components'][0]['children'][1]['transform'])))
        variants.append(bad)
        bad = copy.deepcopy(raw); bad[10]['components'][0]['children'].pop(); variants.append(bad)
        variants.append(raw[:-1])
        for index, bad in enumerate(variants):
            with self.subTest(index=index), self.assertRaises((ValueError, KeyError, TypeError)):
                m.check_pose(bad, [5, 0, 0, 0, 0, 0], self.core, self.layout)
        for malformed in (b'{"x":1,"x":2}', b'{"x":NaN}', b'['*140+b'0'+b']'*140):
            with self.assertRaises(ValueError):
                m.parse(malformed)

    def test_real_cli_missing_core_or_native_has_failed_marker(self):
        for missing in (m.CORE, m.MODEL):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for path in m.PINS:
                    dest = root/path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(m.read(ROOT/path))
                out = root/m.OUTPUT
                out.mkdir(parents=True)
                (out/'current.json').write_text('{"status":"PASS","run_id":"old"}', encoding='utf-8')
                before = (root/missing).read_bytes()
                (root/missing).unlink()
                proc = subprocess.run([sys.executable, '-I', '-B', str(MODULE), 'build', '--root', str(root), '--cli', str(root/'unused.exe')],
                                      capture_output=True, timeout=20)
                self.assertNotEqual(proc.returncode, 0)
                current = json.loads((out/'current.json').read_bytes())
                self.assertEqual(current['status'], 'FAILED')
                self.assertNotEqual(current['run_id'], 'old')
                (root/missing).write_bytes(before)
                with self.assertRaises(ValueError):
                    m.verify(root, root/'unused.exe')

    def test_actual_child_nonzero_and_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            with self.assertRaises(ValueError):
                m.execute([sys.executable, '-c', 'print("not successful"); raise SystemExit(7)'], bundle, 'nonzero')
            self.assertEqual(m.parse(m.read(bundle/'nonzero-exit.json'))['exit_code'], 7)
            with self.assertRaises(subprocess.TimeoutExpired):
                m.execute([sys.executable, '-c', 'import time; time.sleep(10)'], bundle, 'timeout', timeout=.1)
            self.assertTrue((bundle/'timeout-stderr.bin').is_file())

    def test_current_alignment_and_readonly_verify(self):
        self.assertEqual(self.current['status'], 'PASS')
        report = m.parse(m.read(self.bundle/'report.json'))
        self.assertFalse(report['mapping_adopted'])
        self.assertFalse(report['hardware_approved'])
        self.assertTrue(report['official_plus_one_matches'])
        cli = Path(os.environ['ND_CLI'])
        before = m.read(ROOT/m.OUTPUT/'current.json')
        self.assertEqual(m.verify(ROOT, cli)['status'], 'PASS')
        self.assertEqual(before, m.read(ROOT/m.OUTPUT/'current.json'))
        # Wrong CLI identity cannot reuse a successful result.
        with self.assertRaises(ValueError):
            m.verify(ROOT, MODULE)

    def test_rehashed_but_semantically_forged_bundle_is_rejected(self):
        cli = Path(os.environ['ND_CLI'])
        for target in ('report.json', 'case-01-exit.json', 'case-01-commands.json'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                paths = set(m.PINS)
                paths.update(m.parse(m.read(ROOT/'src/startup_alignment/contract.json'))['inputs'])
                for path in paths:
                    dest = root/path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(m.read(ROOT/path))
                sb = ROOT/'outputs/supervised-alignment-v1'
                sb_current = m.parse(m.read(sb/'current.json'))
                dest = root/'outputs/supervised-alignment-v1'
                dest.mkdir(parents=True, exist_ok=True)
                (dest/'current.json').write_bytes(m.read(sb/'current.json'))
                shutil.copytree(sb/'runs'/sb_current['run_id'], dest/'runs'/sb_current['run_id'])
                out = root/m.OUTPUT
                out.mkdir(parents=True, exist_ok=True)
                (out/'current.json').write_bytes(m.read(ROOT/m.OUTPUT/'current.json'))
                bundle = out/'runs'/self.current['run_id']
                shutil.copytree(self.bundle, bundle)
                self.assertEqual(m.verify(root, cli)['status'], 'PASS')
                payload = m.parse(m.read(bundle/target))
                if target == 'report.json':
                    payload['cases'] = []
                elif target.endswith('-exit.json'):
                    payload['exit_code'] = 7
                else:
                    payload['commands'][3]['params']['value'] = -5
                (bundle/target).write_bytes(m.encoded(payload))
                manifest = m.parse(m.read(bundle/'manifest.json'))
                manifest['files'][target] = m.sha(m.read(bundle/target))
                (bundle/'manifest.json').write_bytes(m.encoded(manifest))
                current = dict(self.current, manifest_sha256=m.sha(m.read(bundle/'manifest.json')))
                (out/'current.json').write_bytes(m.encoded(current))
                with self.assertRaises(ValueError):
                    m.verify(root, cli)


if __name__ == '__main__':
    unittest.main(verbosity=2)
