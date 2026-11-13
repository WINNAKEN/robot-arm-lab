"""Host-only public-path probes; all edits are in disposable copied roots."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

HERE = Path(__file__).resolve().parent
MODULE = Path(os.environ.get('ALIGNMENT_MODULE', str(HERE/'alignment.py')))
spec = importlib.util.spec_from_file_location('alignment_under_test', MODULE)
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)
ROOT = HERE.parents[1]
F = a.approved_core()
NATIVE_RAW = (ROOT/a.NATIVE).read_bytes()
NATIVE = json.loads(zipfile.ZipFile(io.BytesIO(NATIVE_RAW)).read('document.json'))
COMMAND_RAW = (ROOT/a.COMMANDS).read_bytes()
COMMAND = json.loads(COMMAND_RAW)
APPROVED = json.loads((ROOT/a.APPROVAL).read_text(encoding='utf-8-sig'))


def packed(document):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('document.json', json.dumps(document).encode())
    return stream.getvalue()


def walk(value, prefix):
    yield prefix
    if type(value) is dict:
        for key, child in value.items():
            yield from walk(child, prefix+(key,))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from walk(child, prefix+(index,))


def at(document, path):
    for key in path:
        document = document[key]
    return document


def replace(document, path, value):
    if not path:
        return value
    at(document, path[:-1])[path[-1]] = value
    return document


def commands_joint(document, index):
    return [x['params'] for x in document['commands'] if x['command'] == 'joint.as_built'][index]


class AlignmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        paths = {x['path'] for x in APPROVED} | {a.APPROVAL, a.RECEIPT, a.KIN, a.NATIVE, a.COMMANDS}
        for path in paths:
            destination = self.root/path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/path, destination)
        a.build(self.root)

    def current(self):
        return json.loads((self.root/a.OUTPUT/'current.json').read_bytes())

    def report(self):
        return json.loads((self.root/a.OUTPUT/'runs'/self.current()['run_id']/'report.json').read_bytes())

    def failure(self, updates):
        originals = {path: (self.root/path).read_bytes() for path in updates}
        previous = self.current()['run_id']
        try:
            for path, raw in updates.items():
                (self.root/path).write_bytes(raw)
            with self.assertRaises(Exception):
                a.build(self.root)
            state = self.current()
            self.assertEqual(state['status'], 'FAILED')
            self.assertNotEqual(state['run_id'], previous)
            self.assertTrue(state['reason'])
        finally:
            for path, raw in originals.items():
                (self.root/path).write_bytes(raw)
        with self.assertRaises(ValueError):
            a.verify(self.root)

    def test_positive_and_exclusions(self):
        report = self.report()
        self.assertEqual(len(report['joints']), 6)
        self.assertEqual(a.verify(self.root)['scope'], 'STATIC_JOINT_METADATA_ALIGNED')
        self.assertLess(max(x['origin_max_error_mm'] for x in report['joints']), 1e-10)
        self.assertLess(max(x['axis_max_component_error'] for x in report['joints']), 1e-14)
        self.assertEqual([round(x['canonical_delta_at_geometric_zero_deg']) for x in report['joints']],
                         [-15, 50, -70, -15, -25, 10])
        # Snap x and flip are NOT the core child orientation or a native motor sign.
        doc = copy.deepcopy(NATIVE)
        for joint in doc['assembly']['joints']:
            joint['b']['snap']['x'] = [-x for x in joint['b']['snap']['x']]
            joint['flip'] = False
        # Ring features are opaque and intentionally outside static metadata proof.
        doc['features'] = []
        (self.root/a.NATIVE).write_bytes(packed(doc))
        a.build(self.root)
        for row in self.report()['joints']:
            self.assertIsNone(row['native_positive_sign'])
            self.assertIsNone(row['native_command_at_geometric_zero'])
            self.assertFalse(row['native_flip'])
        self.assertEqual(self.report()['ring_geometry'], 'DEFERRED_UNRESOLVED_020')
        self.assertEqual(self.report()['native_body_orientation_agreement'], 'NOT_DERIVED')

    def test_public_shape_matrix(self):
        native_paths = [(), ('format',), ('units',)]
        for key in ('components', 'occurrences', 'assembly'):
            native_paths.extend(walk(NATIVE[key], (key,)))
        command_paths = [(), ('commands',)]
        for i, row in enumerate(COMMAND['commands']):
            base = ('commands', i)
            command_paths += [base, base+('command',), base+('params',)]
            if row['command'] == 'joint.as_built':
                command_paths.extend(list(walk(row['params'], base+('params',)))[1:])
        count = 0
        for original, paths, target, encode in ((NATIVE, native_paths, a.NATIVE, packed),
                (COMMAND, command_paths, a.COMMANDS, lambda d: json.dumps(d).encode())):
            for path in paths:
                kind = type(at(original, path))
                replacements = [None, True, {}, [], 0, 'bad']
                for value in replacements:
                    if type(value) is kind or (kind in (int, float) and type(value) in (int, float)):
                        continue
                    with self.subTest(target=target, path=path, replacement=value):
                        mutated = replace(copy.deepcopy(original), path, value)
                        self.failure({target: encode(mutated)})
                        count += 1
        print('PUBLIC_NATIVE_COMMAND_SHAPE_FAILURES', count)

    def test_array_lengths_and_ids(self):
        native_paths = []
        for key in ('components', 'occurrences', 'assembly'):
            native_paths.extend(p for p in walk(NATIVE[key], (key,)) if type(at(NATIVE, p)) is list)
        command_paths = []
        for i, row in enumerate(COMMAND['commands']):
            if row['command'] == 'joint.as_built':
                base = ('commands', i, 'params')
                command_paths.extend(p for p in walk(row['params'], base) if type(at(COMMAND, p)) is list)
        for original, paths, target, encode in ((NATIVE, native_paths, a.NATIVE, packed),
                (COMMAND, command_paths, a.COMMANDS, lambda d: json.dumps(d).encode())):
            for path in paths:
                for longer in (False, True):
                    with self.subTest(target=target, array=path, longer=longer):
                        doc = copy.deepcopy(original)
                        values = at(doc, path)
                        changed = values+[values[-1]] if longer else values[:-1]
                        self.failure({target: encode(replace(doc, path, changed))})
        for key in ('components', 'occurrences'):
            for identity in (0, -1, 2**31):
                native = copy.deepcopy(NATIVE)
                native[key][0]['id'] = identity
                self.failure({a.NATIVE: packed(native)})
        native = copy.deepcopy(NATIVE)
        native['assembly']['joints'][1]['id'] = native['assembly']['joints'][0]['id']
        self.failure({a.NATIVE: packed(native)})

    def test_missing_consumed_fields(self):
        native_paths = [('format',), ('units',)]
        for key in ('components', 'occurrences', 'assembly'):
            native_paths.append((key,))
            native_paths.extend(p for p in walk(NATIVE[key], (key,)) if len(p) > 1 and type(p[-1]) is str)
        command_paths = [('commands',)]
        for i, row in enumerate(COMMAND['commands']):
            base = ('commands', i)
            command_paths += [base+('command',), base+('params',)]
            if row['command'] == 'joint.as_built':
                command_paths.extend(p for p in walk(row['params'], base+('params',))
                                     if len(p) > 3 and type(p[-1]) is str)
        for original, paths, target, encode in ((NATIVE, native_paths, a.NATIVE, packed),
                (COMMAND, command_paths, a.COMMANDS, lambda d: json.dumps(d).encode())):
            for path in paths:
                with self.subTest(target=target, missing=path):
                    doc = copy.deepcopy(original)
                    del at(doc, path[:-1])[path[-1]]
                    self.failure({target: encode(doc)})

    def test_each_joint_origin_axis_zero_and_topology(self):
        for index in range(6):
            for mode in ('point', 'axis', 'angle', 'values', 'offset', 'topology', 'limits'):
                with self.subTest(index=index, mode=mode):
                    native, command = copy.deepcopy(NATIVE), copy.deepcopy(COMMAND)
                    joint = native['assembly']['joints'][index]
                    entry = commands_joint(command, index)
                    if mode == 'point':
                        for point in (joint['a']['snap']['point'], joint['b']['snap']['origin'], entry['at']['point']):
                            point[0] += .01
                    elif mode == 'axis':
                        for holder, key in ((joint['a']['snap'], 'z'), (joint['b']['snap'], 'z'), (entry['at'], 'z')):
                            holder[key] = [-x for x in holder[key]]
                    elif mode == 'topology':
                        joint['a']['occurrence'], joint['b']['occurrence'] = joint['b']['occurrence'], joint['a']['occurrence']
                        entry['a'], entry['b'] = entry['b'], entry['a']
                    elif mode == 'limits':
                        joint['limits'][0][0] -= .1
                    else:
                        joint[mode] = [1.] if mode == 'values' else 1.
                    self.failure({a.NATIVE: packed(native), a.COMMANDS: json.dumps(command).encode()})

    def test_tolerance_and_unsupported_transforms(self):
        for multiplier, expected in ((.4, True), (2., False)):
            native, command = copy.deepcopy(NATIVE), copy.deepcopy(COMMAND)
            joint = native['assembly']['joints'][0]
            entry = commands_joint(command, 0)
            for point in (joint['a']['snap']['point'], joint['b']['snap']['origin'], entry['at']['point']):
                point[0] += multiplier*a.POINT_TOL_MM
            updates = {a.NATIVE: packed(native), a.COMMANDS: json.dumps(command).encode()}
            if expected:
                for path, raw in updates.items():
                    (self.root/path).write_bytes(raw)
                a.build(self.root)
                self.assertLess(self.report()['joints'][0]['origin_max_error_mm'], a.POINT_TOL_MM)
                (self.root/a.NATIVE).write_bytes(NATIVE_RAW)
                (self.root/a.COMMANDS).write_bytes(COMMAND_RAW)
            else:
                self.failure(updates)
        for key in ('transform', 'grounded'):
            native = copy.deepcopy(NATIVE)
            if key == 'transform':
                native['occurrences'][1]['transform'][0][3] = 1e-15
            else:
                native['occurrences'][1]['grounded'] = True
            self.failure({a.NATIVE: packed(native)})

    def test_zip_and_numeric_rejection(self):
        invalid = [b'not a zip', NATIVE_RAW[:50], b'0'*(8*1024*1024+1)]
        duplicate = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(duplicate, 'w') as archive:
                archive.writestr('document.json', '{}')
                archive.writestr('document.json', '{}')
        invalid.append(duplicate.getvalue())
        for encrypted, compression in ((False, 99), (True, 0)):
            raw = bytearray(packed(NATIVE))
            central = raw.index(b'PK\x01\x02')
            struct.pack_into('<H', raw, 8, compression)
            struct.pack_into('<H', raw, central+10, compression)
            if encrypted:
                struct.pack_into('<H', raw, 6, 1)
                struct.pack_into('<H', raw, central+8, 1)
            invalid.append(bytes(raw))
        for raw in invalid:
            self.failure({a.NATIVE: raw})
        for value in (10**400, float('inf'), float('nan')):
            native = copy.deepcopy(NATIVE)
            native['assembly']['joints'][0]['a']['snap']['point'][0] = value
            self.failure({a.NATIVE: packed(native)})
        for raw in (b'{', b'{"commands":[],"commands":[]}', b'['*100+b'0'+b']'*100, b' '*1048577):
            self.failure({a.COMMANDS: raw})

    def test_approved_dependency_not_merely_integrity(self):
        for path in (a.APPROVAL, a.RECEIPT, 'src/joint_frames/README.md'):
            self.failure({path: (self.root/path).read_bytes()+b' '})
        # A changed producer and regenerated021 output really pass that producer's
        # public verify, but MUST NOT pass022's independent approval admission.
        changed = self.root/'src/joint_frames/frames.py'
        changed.write_bytes(changed.read_bytes()+b'\n# unreviewed producer\n')
        name = 'unreviewed_copy'
        spec = importlib.util.spec_from_file_location(name, changed)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        self.assertEqual(module.build(self.root)['status'], 'PASS')
        self.assertEqual(module.verify(self.root)['status'], 'PASS')
        with self.assertRaises(ValueError):
            a.build(self.root)
        self.assertEqual(self.current()['status'], 'FAILED')
        with patch.object(a, 'CORE_PATH', changed):
            with self.assertRaises(ValueError):
                a.build(self.root)
        self.assertEqual(self.current()['status'], 'FAILED')

    def test_unexpected_errors_identity_and_no_fallback(self):
        for function in ('decode_native', 'compare', 'verify'):
            with patch.object(a, function, side_effect=ArithmeticError('unexpected')):
                with self.assertRaisesRegex(ArithmeticError, 'unexpected'):
                    a.build(self.root)
            self.assertEqual(self.current()['status'], 'FAILED')
            with self.assertRaises(ValueError):
                a.verify(self.root)
        a.build(self.root)
        current = self.current()
        bundle = self.root/a.OUTPUT/'runs'/current['run_id']
        for name in a.FILES+('manifest.json',):
            path = bundle/name
            original = path.read_bytes()
            path.write_bytes(original+b' ')
            with self.assertRaises(ValueError):
                a.verify(self.root)
            path.write_bytes(original)
        with patch.object(a, '__file__', str(self.root/a.COMMANDS)):
            with self.assertRaises(ValueError):
                a.verify(self.root)
        path = self.root/a.OUTPUT/'current.json'
        for change in ({'status': 'FAILED'}, {'status': 'BUILDING'}, {'run_id': '../bad'}, {'run_id': '0'*32}):
            path.write_bytes(a.encoded(current | change))
            with self.assertRaises((ValueError, FileNotFoundError)):
                a.verify(self.root)
        path.write_bytes(a.encoded(current))
        self.assertEqual(a.verify(self.root)['status'], 'PASS')

    def test_midbuild_change_and_write_errors(self):
        original = a.compare
        def changed(*args):
            result = original(*args)
            (self.root/a.COMMANDS).write_bytes(COMMAND_RAW+b' ')
            return result
        with patch.object(a, 'compare', side_effect=changed):
            with self.assertRaises(ValueError):
                a.build(self.root)
        self.assertEqual(self.current()['status'], 'FAILED')
        (self.root/a.COMMANDS).write_bytes(COMMAND_RAW)
        atomic = a.atomic
        for status in ('BUILDING', 'PASS'):
            def broken(path, value):
                if value['status'] == status:
                    raise OSError('publication failure')
                atomic(path, value)
            with patch.object(a, 'atomic', side_effect=broken):
                with self.assertRaises(OSError):
                    a.build(self.root)
            self.assertEqual(self.current()['status'], 'FAILED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
