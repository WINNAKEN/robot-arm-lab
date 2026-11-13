"""116 HOST preservation tests for the reviewed all-format decision policy."""
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import time
import types
import unittest
import uuid
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
SRC = Path(__file__).resolve().parent
OUT = REPO / 'outputs/blended-reference-trial-116'


def run_host_tests(module_name, stem):
    """Each invocation keeps its own HOST log; explicit tags never overwrite."""
    run_id = os.environ.get('ROBOT_ARM_116_TEST_RUN_ID') or uuid.uuid4().hex
    if re.fullmatch(r'[A-Za-z0-9_-]{1,96}', run_id) is None:
        raise ValueError('invalid HOST test run id')
    folder = OUT / 'D-implementation/host-runs' / run_id
    folder.mkdir(parents=True, exist_ok=True)
    pins = {}
    for filename in ('validate.py', 'decision_schema.py', 'test_validate.py', 'test_decision_schema.py'):
        raw = (SRC / filename).read_bytes()
        pins[filename] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    started = time.monotonic()
    metadata = {'scope': 'SYNTHETIC_HOST_FIXTURE_NOT_REVIEW_OR_NATIVE_AUTHORITY', 'run_id': run_id,
                'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source': pins}
    with (folder / (stem + '-start.json')).open('x', encoding='utf-8') as start_file:
        json.dump(metadata, start_file, indent=2)
    with (folder / (stem + '-stderr.raw')).open('x', encoding='utf-8', newline='\n') as log:
        class Tee:
            def write(self, text):
                sys.stderr.write(text); log.write(text)
            def flush(self):
                sys.stderr.flush(); log.flush()
        result = unittest.main(module=module_name, verbosity=2, exit=False,
            testRunner=unittest.TextTestRunner(stream=Tee(), verbosity=2)).result
    metadata.update(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                    skipped=len(result.skipped), elapsed_s=time.monotonic() - started)
    with (folder / (stem + '-result.json')).open('x', encoding='utf-8') as result_file:
        json.dump(metadata, result_file, indent=2)
    print(json.dumps({'HOST_evidence': str(folder), 'tests': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors)}))
    raise SystemExit(0 if result.wasSuccessful() else 1)


def load_raw(name, raw, filename):
    module = types.ModuleType(name)
    module.__file__ = str(filename)
    module.__source_bytes__ = raw
    exec(compile(raw, str(filename), 'exec'), module.__dict__)
    return module


def fixture_bundle():
    """Read-only actual inputs; these bytes grant no review or native authority."""
    cfg_raw = (SRC / 'config.json').read_bytes()
    cfg = json.loads(cfg_raw)
    result = {}
    for name in cfg['source_A'] + cfg['source_B']:
        if name in {'bootstrap.py', 'driver.py', 'config.json', 'validate.py', 'decision_schema.py',
                    'scene.py', 'workspace.py', 'program.json', 'test_scene.py'}:
            path = SRC / name
        elif name == 'winjob.py':
            path = REPO / 'src/simulation/single_host_controller_110/winjob.py'
        else:
            path = REPO / 'src/simulation/clock_ready_resume_108' / name
        result['source/' + name] = path.read_bytes()
    model = REPO / cfg['model_dir']
    for path in model.rglob('*'):
        if path.is_file():
            result['model/' + path.relative_to(model).as_posix()] = path.read_bytes()
    for name, pin in cfg['refs'].items():
        result['ref/' + name] = (REPO / pin['path']).read_bytes()
    return result


def policy_module(bundle):
    return load_raw('host_policy114', bundle['source/decision_schema.py'], SRC / 'decision_schema.py')


def thaw(value):
    if hasattr(value, 'items'):
        return {key: thaw(child) for key, child in value.items()}
    if type(value) is tuple:
        return [thaw(child) for child in value]
    return value


class DecisionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fixture_bundle()
        cls.policy = policy_module(cls.bundle)
        cls.coverage = cls.policy.validate_decision_inputs(cls.bundle)

    def test_closed_dispatch_and_fresh_results(self):
        c = self.coverage
        self.assertEqual(set(c), {'schema_version', 'unit', 'scope', 'policy_sha256',
                                 'inputs_sha256', 'files', 'totals'})
        self.assertEqual(len(c['files']), 48)
        self.assertEqual(c['totals']['typed_files'], 20)
        self.assertEqual(c['totals']['opaque_files'], 28)
        self.assertEqual(c['files']['model/robot_arm.urdf']['numeric_components'], 512)
        self.assertEqual(sum(v['kind'] == 'JSON' for v in c['files'].values()), 8)
        self.assertEqual(sum(v['kind'] == 'STL_BINARY' for v in c['files'].values()), 11)
        for name, row in c['files'].items():
            self.assertEqual(set(row), {'kind', 'numeric_components', 'logical_values'})
            self.assertIs(type(row['numeric_components']), int)
            self.assertIs(type(row['logical_values']), int)
            if row['kind'] == 'OPAQUE':
                self.assertEqual((row['numeric_components'], row['logical_values']), (0, 0))
        fresh = self.policy.validate_decision_inputs(self.bundle)
        self.assertEqual(c, fresh)
        self.assertIsNot(c, fresh)
        self.assertIsNot(c['files'], fresh['files'])

    def test_l2_ir_is_identical_and_immutable(self):
        raw = (OUT / 'json-numeric-role-contract.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.policy.ROLE_CONTRACT_SHA)
        self.assertEqual(thaw(self.policy.JSON_ROLES), json.loads(raw)['documents'])
        with self.assertRaises(TypeError):
            self.policy.JSON_ROLES['new'] = {'kind': 'number'}
        with self.assertRaises(TypeError):
            self.policy.JSON_ROLES['source/config.json']['required']['width'] = {'kind': 'boolean'}

    def test_bundle_closed_exact_bytes_and_self_pin(self):
        for mutation in ('missing', 'extra', 'alias', 'bytearray', 'empty', 'self'):
            with self.subTest(mutation=mutation):
                b = dict(self.bundle)
                if mutation == 'missing':
                    del b['source/README.md']
                elif mutation == 'extra':
                    b['extra'] = b'x'
                elif mutation == 'alias':
                    b['source/./README.md'] = b.pop('source/README.md')
                elif mutation == 'bytearray':
                    b['source/README.md'] = bytearray(b'x')
                elif mutation == 'empty':
                    b['source/README.md'] = b''
                else:
                    b['source/decision_schema.py'] += b'\n'
                with self.assertRaises(ValueError):
                    self.policy.validate_decision_inputs(b)

    def test_all_json_documents_required_roles_and_two_way_coverage(self):
        p = self.policy
        for name, role in p.JSON_ROLES.items():
            raw = self.bundle[name]
            with self.subTest(name=name):
                n, logical = p._json_document(raw, role, name)
                self.assertEqual((n, logical), (self.coverage['files'][name]['numeric_components'],
                                             self.coverage['files'][name]['logical_values']))
                document = json.loads(raw)
                document['host_metadata'] = {'text': ['nan Inf 1e999', None]}
                p._json_document(json.dumps(document).encode(), role, name)
                for value in (1, 1.5, True, {'nested': [False]}, [0]):
                    document['host_metadata'] = value
                    with self.assertRaisesRegex(ValueError, 'uncovered'):
                        p._json_document(json.dumps(document).encode(), role, name)
                if role['required']:
                    del document[next(iter(role['required']))]
                    with self.assertRaises(ValueError):
                        p._json_document(json.dumps(document).encode(), role, name)

    def test_json_semantic_types_arrays_mappings_and_constants(self):
        p = self.policy
        role = {'kind': 'object', 'required': {
            'n': {'kind': 'number'}, 'i': {'kind': 'integer'}, 'b': {'kind': 'boolean'},
            'a': {'kind': 'array', 'item': {'kind': 'number'}, 'min_length': 1, 'exact_length': 3},
            'm': {'kind': 'mapping', 'value': {'kind': 'integer'}, 'min_entries': 1}},
            'other': 'opaque_metadata_without_numeric_or_logical_leaves'}
        normal = {'n': 1.25, 'i': 1, 'b': False, 'a': [0, 1, -1], 'm': {'one': 1}}
        self.assertEqual(p._json_document(json.dumps(normal).encode(), role, 'HOST'), (6, 1))
        for key, bad_values in {'n': [True, None, '1', [], {}],
                                'i': [True, 1.0, None, '1'], 'b': [0, 1, None, 'false'],
                                'a': [[], [0, 1], [0, True, 2], None],
                                'm': [{}, {'one': False}, [], None]}.items():
            for bad in bad_values:
                with self.subTest(key=key, value=bad):
                    doc = copy.deepcopy(normal)
                    doc[key] = bad
                    with self.assertRaises(ValueError):
                        p._json_document(json.dumps(doc).encode(), role, 'HOST')
        for raw in (b'{"n":NaN}', b'{"n":Infinity}', b'{"n":-Infinity}', b'{"n":1e999}',
                    b'{"n":1,"n":2}'):
            with self.assertRaises(ValueError):
                p._json_document(raw, role, 'HOST')
        same = json.dumps(normal).replace('1.25', '1.250e+0').encode()
        self.assertEqual(p._json_document(same, role, 'HOST'), (6, 1))
        tiny = json.dumps(normal).replace('1.25', '1e-999').encode()
        self.assertEqual(p._json_document(tiny, role, 'HOST'), (6, 1))

    def test_urdf_every_numeric_attribute_and_component(self):
        p = self.policy
        root = ET.fromstring(self.bundle['model/robot_arm.urdf'])
        scalar_count = 0
        def walk(node, path):
            nonlocal scalar_count
            attrs = p._XML[path][0]
            for key, arity in attrs.items():
                if not arity:
                    continue
                tokens = node.attrib[key].split()
                old = node.attrib[key]
                for index in range(arity):
                    changed = list(tokens)
                    changed[index] = ('inf', 'nan', '1e999')[scalar_count % 3]
                    node.attrib[key] = ' '.join(changed)
                    with self.subTest(path=path, key=key, index=index):
                        with self.assertRaisesRegex(ValueError, 'decimal|finite'):
                            p._urdf_document(ET.tostring(root))
                    scalar_count += 1
                node.attrib[key] = old
            for child in node:
                walk(child, path + '/' + child.tag)
        walk(root, 'robot')
        self.assertEqual(scalar_count, 512)

    def test_urdf_profile_missing_unknown_comments_and_lexical_controls(self):
        p = self.policy
        normal = self.bundle['model/robot_arm.urdf']
        comment = normal.replace(b'<robot ', b'<!-- nan DOCTYPE <!ENTITY x> -->\n<robot ', 1)
        self.assertEqual(p._urdf_document(comment), (512, 0))
        root = ET.fromstring(normal)
        inertia = root.find('link/inertial/inertia')
        inertia.attrib['ixy'] = '-0.000e+0'
        self.assertEqual(p._urdf_document(ET.tostring(root)), (512, 0))
        for mutation in ('attribute', 'element', 'missing', 'frame', 'mimic', 'arity', 'underscore', 'DTD'):
            with self.subTest(mutation=mutation):
                root = ET.fromstring(normal)
                if mutation == 'attribute':
                    root.find('link/inertial/mass').set('extra', 'inf')
                elif mutation == 'element':
                    ET.SubElement(root, 'unknown', {'value': '0'})
                elif mutation == 'missing':
                    del root.find('link/inertial/inertia').attrib['ixz']
                elif mutation == 'frame':
                    node = root.find('link'); node.clear(); node.set('name', 'Base')
                elif mutation == 'mimic':
                    node = root.find("joint[@name='KG1_slide_B']"); node.remove(node.find('mimic'))
                elif mutation == 'arity':
                    root.find('link/inertial/origin').set('xyz', '0 0')
                elif mutation == 'underscore':
                    root.find('link/inertial/mass').set('value', '1_0')
                raw = ET.tostring(root)
                if mutation == 'DTD':
                    raw = b'<!DOCTYPE robot [<!ENTITY x "1">]>' + raw
                with self.assertRaises(ValueError):
                    p._urdf_document(raw)

    def test_binary_stl_every_float_attribute_length_and_solid_header(self):
        p = self.policy
        header = b'solid nan opaque'.ljust(80, b' ')
        normal = header + struct.pack('<I12fH', 1, *([0.] * 12), 65535)
        self.assertEqual(p._stl_document(normal), ('STL_BINARY', 14, 0))
        self.assertEqual(p._stl_document(header + struct.pack('<I', 0)), ('STL_BINARY', 1, 0))
        for component in range(12):
            for bad in (math.inf, -math.inf, math.nan):
                raw = bytearray(normal)
                struct.pack_into('<f', raw, 84 + component * 4, bad)
                with self.subTest(component=component, bad=bad):
                    with self.assertRaises(ValueError):
                        p._stl_document(bytes(raw))
        for raw in (normal[:-1], normal + b'x', normal[:80] + struct.pack('<I', 2) + normal[84:]):
            with self.assertRaises((ValueError, UnicodeError)):
                p._stl_document(raw)

    def test_ascii_stl_closed_grammar_all_components_and_binary_priority(self):
        p = self.policy
        normal = (b'solid nan is opaque\nfacet normal 0 0 1\nouter loop\n'
                  b'vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid\n')
        self.assertEqual(p._stl_document(normal), ('STL_ASCII', 12, 0))
        self.assertEqual(p._stl_document(b'solid empty\nendsolid empty\n'), ('STL_ASCII', 0, 0))
        self.assertEqual(p._stl_document(normal.replace(b'vertex 1 0 0', b'vertex +1.00e0 0e-999 -0')),
                         ('STL_ASCII', 12, 0))
        whitespace = normal.replace(b'facet normal ', b'facet\t normal\n').replace(
            b'outer loop', b'outer\tloop').replace(b'vertex ', b'vertex\t')
        self.assertEqual(p._stl_document(whitespace), ('STL_ASCII', 12, 0))
        rows = normal.decode().splitlines()
        locations = [(1, i) for i in range(2, 5)] + [(j, i) for j in (3, 4, 5) for i in range(1, 4)]
        for row, token in locations:
            for bad in ('nan', 'inf', '1e999', 'False', '1_0'):
                changed = list(rows); words = changed[row].split(); words[token] = bad
                changed[row] = ' '.join(words)
                with self.subTest(row=row, token=token, bad=bad):
                    with self.assertRaises(ValueError):
                        p._stl_document(('\n'.join(changed)).encode())
        for raw in (normal + b'garbage', normal.replace(b'outer loop', b'outer nope'),
                    normal.replace(b'vertex 1 0 0\n', b''), normal.replace(b'endfacet', b'')):
            with self.assertRaises(ValueError):
                p._stl_document(raw)

    def test_actual_dispatch_ascii_and_solid_header_binary_policy_positives(self):
        ascii_mesh = (b'solid opaque name 1e999\nfacet normal 0 0 1\nouter loop\n'
                      b'vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid\n')
        b = dict(self.bundle)
        b['model/meshes/Base.stl'] = ascii_mesh
        coverage = self.policy.validate_decision_inputs(b)
        self.assertEqual(coverage['files']['model/meshes/Base.stl'],
                         {'kind': 'STL_ASCII', 'numeric_components': 12, 'logical_values': 0})
        b['model/meshes/Base.stl'] = b'solid opaque'.ljust(80, b' ') + struct.pack(
            '<I12fH', 1, *([0.] * 12), 65535)
        coverage = self.policy.validate_decision_inputs(b)
        self.assertEqual(coverage['files']['model/meshes/Base.stl'],
                         {'kind': 'STL_BINARY', 'numeric_components': 14, 'logical_values': 0})



class ProfilePolicyTests(unittest.TestCase):
    """Pure new-role HOST cases, not a complete bundle or an authority receipt."""
    @classmethod
    def setUpClass(cls):
        raw=(SRC/'decision_schema.py').read_bytes()
        cls.policy=load_raw('profile116_policy',raw,SRC/'decision_schema.py')
        cls.role=cls.policy.JSON_ROLES['source/program.json']['required']['reference_profile']
        cls.profile={'name':'reach_high_right_half_quintic_septic_v1','phase':'reach_high_right',
                     'blend_numerator':1,'blend_denominator':2}

    def check_profile(self, value):
        return self.policy._json_document(json.dumps(value).encode(),self.role,'HOST/profile')

    def test_literal_profile_and_two_numeric_leaves(self):
        self.assertEqual(self.check_profile(self.profile),(2,0))
        declared=json.loads((OUT/'json-numeric-role-contract.json').read_bytes())['documents']
        self.assertEqual(thaw(self.policy.JSON_ROLES),declared)
        self.assertEqual(self.policy.ROLE_CONTRACT_SHA,
                         'c0a162d8a90f72d8f7c8141ef93c99a0fe27277fa856b007c7668090318766ff')

    def test_profile_required_exact_values_types_and_keys(self):
        for key in self.profile:
            bad=copy.deepcopy(self.profile);del bad[key]
            with self.subTest(missing=key),self.assertRaises(ValueError):self.check_profile(bad)
        for key,values in [('name',[None,True,17,'wrong']),('phase',[None,False,9,'raise']),
                           ('blend_numerator',[False,1.0,2,float('nan'),float('inf')]),
                           ('blend_denominator',[True,2.0,3,float('nan'),float('-inf')])]:
            for value in values:
                bad=copy.deepcopy(self.profile);bad[key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.check_profile(bad)
        for value in ['opaque-extra',0,False]:
            bad=copy.deepcopy(self.profile);bad['extra']=value
            with self.subTest(extra=value),self.assertRaises(ValueError):self.check_profile(bad)
        for value in [None,[],True,1]:
            with self.subTest(object=value),self.assertRaises(ValueError):self.check_profile(value)

    def test_profile_duplicate_keys_and_unknown_role_refused(self):
        raw=json.dumps(self.profile)[:-1]+',"name":"reach_high_right_half_quintic_septic_v1"}'
        with self.assertRaises(ValueError):self.policy._json_document(raw.encode(),self.role,'HOST/duplicate')
        with self.assertRaises(ValueError):self.policy._json_document(b'"x"',{'kind':'unknown'},'HOST/unknown')


if __name__ == '__main__':
    run_host_tests(__name__, Path(__file__).stem)
