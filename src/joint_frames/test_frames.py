"""Public workflow failure probes and independent numerical checks for021."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(os.environ.get('FRAMES_MODULE', str(Path(__file__).with_name('frames.py'))))
spec = importlib.util.spec_from_file_location('frames_under_test', MODULE)
f = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = f
spec.loader.exec_module(f)
ROOT = Path(__file__).resolve().parents[2]
RAW = (ROOT/f.SOURCE).read_bytes()
DATA = json.loads(RAW)


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


class FramesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root/f.SOURCE
        self.input.parent.mkdir(parents=True)
        self.input.write_bytes(RAW)
        self.layout = f.decode(RAW)

    def current(self):
        return json.loads((self.root/f.OUTPUT/'current.json').read_bytes())

    def failure(self, raw):
        f.build(self.root)
        previous = self.current()['run_id']
        self.input.write_bytes(raw)
        with self.assertRaises(Exception):
            f.build(self.root)
        state = self.current()
        self.assertEqual(state['status'], 'FAILED')
        self.assertNotEqual(state['run_id'], previous)
        self.assertTrue(state['reason'])
        self.input.write_bytes(RAW)
        with self.assertRaises(ValueError):
            f.verify(self.root)

    def test_shape_matrix(self):
        # Every consumed container/leaf, all six joints, plus nested matrix rows/cells.
        paths = [(), ('units',), ('joint_count',), ('joints',)]
        for i, joint in enumerate(DATA['joints']):
            base = ('joints', i)
            paths.append(base)
            for key in ('name', 'parent', 'child', 'origin_mm', 'axis_world',
                        'axis_parent_zero', 'pose_deg', 'R_parent', 'R_child'):
                paths.append(base+(key,))
                if type(joint[key]) is list:
                    for j, item in enumerate(joint[key]):
                        paths.append(base+(key, j))
                        if type(item) is list:
                            paths.extend(base+(key, j, k) for k in range(3))
        count = 0
        for path in paths:
            for replacement in (None, True, {}, [], 'bad'):
                with self.subTest(path=path, replacement=replacement):
                    doc = copy.deepcopy(DATA)
                    if not path:
                        doc = replacement
                    else:
                        cursor = doc
                        for key in path[:-1]:
                            cursor = cursor[key]
                        cursor[path[-1]] = replacement
                    self.failure(json.dumps(doc).encode())
                    count += 1
        print('PUBLIC_SHAPE_FAILURE_CASES', count)

    def test_missing_fields_and_lengths(self):
        paths = [('units',), ('joint_count',), ('joints',)]
        paths.extend(('joints', i, k) for i in range(6) for k in DATA['joints'][i])
        consumed = {'name', 'parent', 'child', 'origin_mm', 'axis_world',
                    'axis_parent_zero', 'pose_deg', 'R_parent', 'R_child',
                    'units', 'joint_count', 'joints'}
        for path in paths:
            if path[-1] not in consumed:
                continue
            doc = copy.deepcopy(DATA)
            cursor = doc
            for key in path[:-1]:
                cursor = cursor[key]
            del cursor[path[-1]]
            self.failure(json.dumps(doc).encode())
        for n in (0, 5, 7):
            doc = copy.deepcopy(DATA)
            doc['joints'] = (doc['joints']*2)[:n]
            self.failure(json.dumps(doc).encode())

    def test_parse_and_number_failures(self):
        for raw in (b'{', b'{"units":"mm","units":"mm"}', b'NaN', b'1e999',
                    b'['*100+b'0'+b']'*100, b' '*1048577, b'\xff'):
            self.failure(raw)
        for key in ('pose_deg', 'origin_mm', 'R_child'):
            for value in (10**400, float('inf'), -1e30):
                doc = copy.deepcopy(DATA)
                if key == 'pose_deg':
                    doc['joints'][0][key] = value
                elif key == 'origin_mm':
                    doc['joints'][0][key][0] = value
                else:
                    doc['joints'][0][key][0][0] = value
                self.failure(json.dumps(doc).encode())

    def test_semantic_rejection(self):
        cases = [('axis_world', [1, 0, 0]), ('axis_parent_zero', [0, 0, 0]),
                 ('pose_deg', 20), ('R_child', [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]),
                 ('R_parent', [[1, 0, 0], [0, 0, -1], [0, 1, 0]]), ('parent', 'Link6')]
        for key, value in cases:
            doc = copy.deepcopy(DATA)
            doc['joints'][0][key] = value
            self.failure(json.dumps(doc).encode())

    def test_unexpected_and_io_finalization(self):
        for name in ('decode', 'verify'):
            f.build(self.root)
            with patch.object(f, name, side_effect=RuntimeError('unexpected')):
                with self.assertRaisesRegex(RuntimeError, 'unexpected'):
                    f.build(self.root)
            self.assertEqual(self.current()['status'], 'FAILED')
        # First status, PASS publication, source read, and payload write fail once.
        original = f.atomic
        for target in ('BUILDING', 'PASS'):
            def fail_once(path, value):
                if value['status'] == target:
                    raise OSError('status injection')
                return original(path, value)
            with patch.object(f, 'atomic', side_effect=fail_once):
                with self.assertRaises(OSError):
                    f.build(self.root)
            self.assertEqual(self.current()['status'], 'FAILED')
        self.input.unlink()
        with self.assertRaises(FileNotFoundError):
            f.build(self.root)
        self.assertEqual(self.current()['status'], 'FAILED')
        self.input.write_bytes(RAW)
        write = Path.write_bytes
        def broken_payload(path, raw):
            if path.name == 'frames.json':
                raise OSError('payload injection')
            return write(path, raw)
        with patch.object(Path, 'write_bytes', broken_payload):
            with self.assertRaises(OSError):
                f.build(self.root)
        self.assertEqual(self.current()['status'], 'FAILED')
        with patch.object(f, 'atomic', side_effect=OSError('storage unavailable')):
            with self.assertRaises(OSError):
                f.build(self.root)
        self.assertNotEqual(self.current()['status'], 'PASS')

    def test_identity_no_fallback(self):
        f.build(self.root)
        good = copy.deepcopy(self.current())
        bundle = self.root/f.OUTPUT/'runs'/good['run_id']
        for name in ('frames.json', 'input.json', 'manifest.json'):
            path = bundle/name
            raw = path.read_bytes()
            path.write_bytes(raw+b' ')
            with self.assertRaises(ValueError):
                f.verify(self.root)
            path.write_bytes(raw)
        self.input.write_bytes(RAW+b' ')
        with self.assertRaises(ValueError):
            f.verify(self.root)
        self.input.write_bytes(RAW)
        with patch.object(f, '__file__', str(self.input)):
            with self.assertRaises(ValueError):
                f.verify(self.root)
        current = self.root/f.OUTPUT/'current.json'
        for changes in ({'status': 'FAILED'}, {'status': 'BUILDING'},
                        {'run_id': '../bad'}, {'run_id': '0'*32}):
            current.write_bytes(f.encoded(good | changes))
            with self.assertRaises((ValueError, FileNotFoundError)):
                f.verify(self.root)
        current.write_bytes(f.encoded(good))
        self.assertEqual(f.verify(self.root)['status'], 'PASS')

    def test_display_and_geometric(self):
        display = f.fk(self.layout, [0]*6)
        for actual, source in zip(display, DATA['joints']):
            self.assertTrue(f.close(actual['origin_m'], [x/1000 for x in source['origin_mm']]))
            self.assertTrue(f.close(actual['rotation_world'], source['R_child']))
            self.assertTrue(f.close(actual['axis_world'], source['axis_world']))
        zero = f.fk(self.layout, f.geometric_to_delta(self.layout, [0]*6))
        expected = [(0, 0, .096), (0, 0, .174), (.165, 0, .174),
                    (.305, 0, .174), (.383, 0, .174), (.523, 0, .174)]
        for actual, origin in zip(zero, expected):
            self.assertTrue(f.close(actual['origin_m'], origin))
            self.assertTrue(f.close(actual['rotation_world'], f.I))
        rng = random.Random(21)
        for _ in range(100):
            q = [rng.uniform(-3, 3) for _ in range(6)]
            self.assertTrue(f.close(f.delta_to_geometric(self.layout,
                f.geometric_to_delta(self.layout, q)), q))

    def test_all_axis_derivatives(self):
        rng, epsilon = random.Random(62), 1e-6
        for _ in range(5):
            q = [rng.uniform(-1, 1) for _ in range(6)]
            baseline = f.fk(self.layout, q)
            for axis_index in range(6):
                plus, minus = q[:], q[:]
                plus[axis_index] += epsilon
                minus[axis_index] -= epsilon
                high, low = f.fk(self.layout, plus), f.fk(self.layout, minus)
                axis = baseline[axis_index]['axis_world']
                origin = baseline[axis_index]['origin_m']
                for link in range(axis_index, 6):
                    expected = cross(axis, tuple(x-y for x, y in zip(baseline[link]['origin_m'], origin)))
                    measured = tuple((x-y)/(2*epsilon) for x, y in zip(high[link]['origin_m'], low[link]['origin_m']))
                    self.assertTrue(f.close(expected, measured, 1e-7))
                    for column in range(3):
                        expected = cross(axis, tuple(row[column] for row in baseline[link]['rotation_world']))
                        measured = tuple((a[column]-b[column])/(2*epsilon)
                            for a, b in zip(high[link]['rotation_world'], low[link]['rotation_world']))
                        self.assertTrue(f.close(expected, measured, 1e-7))
        with self.assertRaises(ValueError):
            f.fk(self.layout, [True]*6)

    def test_transform_domain_closure(self):
        # R1-1: accepted conversion output must be accepted by the inverse.
        for magnitude in (1e6, 1e6+10, 1e100, sys.float_info.max):
            for sign in (-1, 1):
                original = [sign*magnitude]*6
                for forward, inverse in ((f.delta_to_geometric, f.geometric_to_delta),
                                         (f.geometric_to_delta, f.delta_to_geometric)):
                    with self.subTest(magnitude=magnitude, sign=sign, forward=forward.__name__):
                        try:
                            converted = forward(self.layout, original)
                            restored = inverse(self.layout, converted)
                        except ValueError as exc:
                            self.fail('Accepted transform domain is not closed: '+str(exc))
                        self.assertTrue(all(math.isfinite(x) for x in converted))
                        self.assertTrue(f.close(restored, original))
                        self.assertEqual(len(f.fk(self.layout, converted)), 6)
        for invalid in (True, None, '1', float('nan'), float('inf'), -float('inf'), 10**400):
            for function in (f.delta_to_geometric, f.geometric_to_delta, f.fk):
                with self.subTest(invalid=str(invalid), function=function.__name__):
                    with self.assertRaises(ValueError):
                        function(self.layout, [invalid]*6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
