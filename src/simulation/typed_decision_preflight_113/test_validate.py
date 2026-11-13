"""113 HOST receipt boundaries; synthetic receipts never confer authority."""
import ast
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

SRC = Path(__file__).resolve().parent
REPO = SRC.parents[2]
_spec = importlib.util.spec_from_file_location('host113_policy_tests', SRC / 'test_decision_schema.py')
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)


def d_module(bundle, policy_raw=None):
    d = helpers.load_raw('host_receipt113', bundle['source/validate.py'], SRC / 'validate.py')
    if policy_raw is not None:
        d.bind_decision_schema(policy_raw)
    return d


def synthetic_receipt(d, bundle):
    """SYNTHETIC_HOST_FIXTURE_NOT_REVIEW_OR_NATIVE_AUTHORITY; no full sampling."""
    frozen = d._bundle(bundle)
    numeric = d._run_policy(frozen)
    data = d._json(bundle['ref/workspace.json'])
    metrics = d._metrics(data)
    workspace_sha = d._digest(bundle['ref/workspace.json'])
    return d._canonical({'schema_version': 1, 'unit': '113', 'scope': d._WORKSPACE_SCOPE,
        'inputs': d._input_pins(bundle), 'algorithms': d._algorithm_pins(bundle),
        'full_sampling': True, 'sample_count': 8192, 'path_state_count': 6241,
        'workspace_sha256': workspace_sha, 'metrics': metrics, 'numeric_contract': numeric,
        'result_sha256': d._result_sha(workspace_sha, metrics, numeric)})


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = helpers.fixture_bundle()
        cls.d = d_module(cls.bundle, cls.bundle['source/decision_schema.py'])
        cls.raw = synthetic_receipt(cls.d, cls.bundle)
        cls.expected = hashlib.sha256(cls.raw).hexdigest()

    def rebound(self, bundle):
        """Recompute all integrity bindings without executing a rejecting numeric guard."""
        d = self.d
        receipt = json.loads(self.raw)
        receipt['inputs'] = d._input_pins(bundle)
        receipt['algorithms'] = d._algorithm_pins(bundle)
        receipt['workspace_sha256'] = d._digest(bundle['ref/workspace.json'])
        receipt['numeric_contract']['inputs_sha256'] = d._digest(d._canonical(receipt['inputs']))
        receipt['numeric_contract']['policy_sha256'] = d._digest(bundle['source/decision_schema.py'])
        receipt['result_sha256'] = d._result_sha(receipt['workspace_sha256'], receipt['metrics'],
                                               receipt['numeric_contract'])
        raw = d._canonical(receipt)
        return raw, hashlib.sha256(raw).hexdigest()

    def test_binding_is_nonexecuting_exact_bytes_and_immutable(self):
        d = d_module(self.bundle)
        dangerous = b'raise RuntimeError("must only execute in use")\n'
        with mock.patch('builtins.compile', side_effect=AssertionError('compile at bind')), \
             mock.patch('builtins.open', side_effect=AssertionError('IO at bind')):
            d.bind_decision_schema(dangerous)
            d.bind_decision_schema(dangerous)
        with self.assertRaises(ValueError):
            d.bind_decision_schema(self.bundle['source/decision_schema.py'])
        with self.assertRaises(ValueError):
            d_module(self.bundle).bind_decision_schema(bytearray(b'x'))
        changed = dict(self.bundle, **{'source/decision_schema.py': dangerous})
        with self.assertRaisesRegex(RuntimeError, 'must only execute'):
            d.produce_workspace_receipt(changed)

    def test_no_binding_source_mismatch_and_closed_input_refused(self):
        for kind in ('unbound', 'D', 'policy', 'missing', 'extra', 'deadline', 'unit', 'source20'):
            with self.subTest(kind=kind):
                b = dict(self.bundle)
                d = d_module(b, b['source/decision_schema.py'] if kind != 'unbound' else None)
                if kind == 'D':
                    b['source/validate.py'] += b'\n'
                elif kind == 'policy':
                    b['source/decision_schema.py'] += b'\n'
                elif kind == 'missing':
                    del b['model/README.md']
                elif kind == 'extra':
                    b['source/alias.py'] = b'x'
                elif kind in ('deadline', 'unit', 'source20'):
                    cfg = json.loads(b['source/config.json'])
                    if kind == 'deadline':
                        cfg['deadline_unix'] = False
                    elif kind == 'unit':
                        cfg['experiment_id'] = 'static_workspace_preflight_112'
                    else:
                        cfg['source_B'].remove('decision_schema.py')
                    b['source/config.json'] = json.dumps(cfg).encode()
                with self.assertRaises(ValueError):
                    d.verify_workspace_receipt(b, self.raw, self.expected)

    def test_original_json_three_and_et03_reach_actual_numeric_guards_both_apis(self):
        cases = []
        cfg = json.loads(self.bundle['source/config.json']); cfg['width'] = False
        cases.append(('original_width_bool', 'source/config.json', json.dumps(cfg).encode(), 'required integer'))
        cfg['width'] = 123456789
        cases.append(('original_width_overflow', 'source/config.json',
                      json.dumps(cfg).replace('123456789', '1e999').encode(), 'nonfinite'))
        workspace = json.loads(self.bundle['ref/workspace.json']); workspace['gravity'][0] = False
        cases.append(('original_workspace_gravity_bool', 'ref/workspace.json',
                      json.dumps(workspace).encode(), 'required number'))
        for value in ('inf', 'nan', '1e999'):
            root = ET.fromstring(self.bundle['model/robot_arm.urdf'])
            root.find('link/inertial/inertia').set('ixx', value)
            cases.append(('ET03_ixx_' + value, 'model/robot_arm.urdf', ET.tostring(root), 'decimal|finite'))
        for label, name, raw, message in cases:
            with self.subTest(case=label):
                b = dict(self.bundle); b[name] = raw
                receipt, expected = self.rebound(b)
                # Matching independent hash and all raw pins reach the numeric guard.
                self.assertEqual(hashlib.sha256(receipt).hexdigest(), expected)
                self.assertEqual(json.loads(receipt)['inputs'], self.d._input_pins(b))
                with mock.patch.object(self.d, '_memory_modules', side_effect=AssertionError('math reached')):
                    with self.assertRaisesRegex(ValueError, message):
                        self.d.produce_workspace_receipt(b)
                    with self.assertRaisesRegex(ValueError, message):
                        self.d.verify_workspace_receipt(b, receipt, expected)

    def test_consumer_reexecutes_actual_policy_and_no_full_math_and_fresh_copies(self):
        calls = []
        def observe(frame, event, arg):
            if event == 'call' and frame.f_code.co_name == 'validate_decision_inputs' and \
               frame.f_code.co_filename.endswith('/source/decision_schema.py'):
                calls.append(frame.f_globals)
        previous = sys.getprofile()
        try:
            sys.setprofile(observe)
            with mock.patch.object(self.d, '_memory_modules', side_effect=AssertionError('consumer math')):
                a, am = self.d.verify_workspace_receipt(self.bundle, self.raw, self.expected)
                b, bm = self.d.verify_workspace_receipt(self.bundle, self.raw, self.expected)
        finally:
            sys.setprofile(previous)
        self.assertEqual(len(calls), 2)
        self.assertIsNot(calls[0], calls[1])
        self.assertEqual(a, b); self.assertEqual(am, bm)
        self.assertIsNot(a, b); self.assertIsNot(a['samples'], b['samples']); self.assertIsNot(am, bm)
        a['gravity'][0] = 999; am['samples'] = -1
        self.assertEqual(b['gravity'][0], 0); self.assertEqual(bm['samples'], 8192)

    def test_other_urdf_roles_missing_and_stl_layers_both_actual_apis(self):
        cases = []
        urdf = self.bundle['model/robot_arm.urdf']
        attributes = [
            ('link/inertial/inertia', attr) for attr in ('iyy', 'izz', 'ixy', 'ixz', 'iyz')]
        attributes += [('link/inertial/mass', 'value'), ('link/inertial/origin', 'xyz'),
            ('link/inertial/origin', 'rpy'), ('link/visual/origin', 'xyz'),
            ('link/visual/origin', 'rpy'), ('link/collision/origin', 'xyz'),
            ('link/collision/origin', 'rpy'), ('joint/origin', 'xyz'), ('joint/origin', 'rpy'),
            ('joint/axis', 'xyz'), ('joint/limit', 'lower'), ('joint/limit', 'upper'),
            ('joint/limit', 'effort'), ('joint/limit', 'velocity'),
            ('joint/dynamics', 'damping'), ('joint/dynamics', 'friction'),
            ("joint[@name='KG1_slide_B']/mimic", 'multiplier'),
            ("joint[@name='KG1_slide_B']/mimic", 'offset'),
            ('link/visual/geometry/mesh', 'scale'), ('link/collision/geometry/box', 'size'),
            ('link/visual/material/color', 'rgba')]
        for index, (selector, attribute) in enumerate(attributes):
            root = ET.fromstring(urdf); node = root.find(selector)
            tokens = node.attrib[attribute].split(); tokens[-1] = ('inf', 'nan', '1e999')[index % 3]
            node.set(attribute, ' '.join(tokens))
            cases.append((selector + '@' + attribute, 'model/robot_arm.urdf', ET.tostring(root)))
        root = ET.fromstring(urdf); del root.find('link/inertial/inertia').attrib['ixx']
        cases.append(('missing_ixx', 'model/robot_arm.urdf', ET.tostring(root)))
        mesh = b'solid binary header'.ljust(80, b' ') + struct.pack('<I12fH', 1, *([0.] * 12), 0)
        for slot in (0, 3, 11):
            changed = bytearray(mesh); struct.pack_into('<f', changed, 84 + 4 * slot, math.inf)
            cases.append(('binary_component_' + str(slot), 'model/meshes/Base.stl', bytes(changed)))
        for label, changed in [('binary_truncated', mesh[:-1]), ('binary_surplus', mesh + b'x')]:
            cases.append((label, 'model/meshes/Base.stl', changed))
        ascii_mesh = (b'solid opaque\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\n'
                      b'vertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid\n')
        for label, changed in [('ascii_normal', ascii_mesh.replace(b'normal 0 0 1', b'normal nan 0 1')),
            ('ascii_vertex', ascii_mesh.replace(b'vertex 1 0 0', b'vertex 1e999 0 0')),
            ('ascii_grammar', ascii_mesh + b'extra token')]:
            cases.append((label, 'model/meshes/Base.stl', changed))
        for label, name, raw in cases:
            with self.subTest(case=label):
                b = dict(self.bundle); b[name] = raw
                receipt, expected = self.rebound(b)
                self.assertEqual(json.loads(receipt)['inputs'], self.d._input_pins(b))
                with mock.patch.object(self.d, '_memory_modules', side_effect=AssertionError('math reached')):
                    with self.assertRaises(ValueError):
                        self.d.produce_workspace_receipt(b)
                    with self.assertRaises(ValueError):
                        self.d.verify_workspace_receipt(b, receipt, expected)

    def test_xml_same_finite_notation_comment_and_logical_values_consumer_positive(self):
        b = dict(self.bundle)
        root = ET.fromstring(b['model/robot_arm.urdf'])
        inertia = root.find('link/inertial/inertia')
        inertia.set('ixx', format(float(inertia.get('ixx')), '.17e'))
        xml = ET.tostring(root).replace(b'<robot ', b'<!-- nan <!ENTITY example> -->\n<robot ', 1)
        b['model/robot_arm.urdf'] = xml
        workspace = json.loads(b['ref/workspace.json'])
        workspace['source_urdf_sha256'] = hashlib.sha256(xml).hexdigest()
        workspace['model_inputs']['robot_arm.urdf'] = {'sha256': hashlib.sha256(xml).hexdigest(), 'bytes': len(xml)}
        b['ref/workspace.json'] = self.d._canonical(workspace)
        receipt, expected = self.rebound(b)
        data, metrics = self.d.verify_workspace_receipt(b, receipt, expected)
        self.assertEqual(data, workspace)
        self.assertEqual(metrics['samples'], 8192)
        self.assertIs(type(data['samples'][0]['feasible']), bool)
        self.assertIs(type(data['program']['segments'][0]['gravity']), bool)

    def test_receipt_closed_types_current_contract_and_independent_expected_sha(self):
        with self.assertRaisesRegex(ValueError, 'independent'):
            self.d.verify_workspace_receipt(self.bundle, self.raw, '0' * 64)
        mutations = {
            'extra': lambda r: r.update(extra=0),
            'unit': lambda r: r.update(unit='112'),
            'schema_bool': lambda r: r.update(schema_version=True),
            'sample_bool': lambda r: r.update(sample_count=True),
            'pin_bool': lambda r: r['inputs']['source/README.md'].update(bytes=True),
            'alg': lambda r: r['algorithms'].update(mode='old'),
            'contract_count_bool': lambda r: r['numeric_contract']['totals'].update(typed_files=True),
            'contract_kind': lambda r: r['numeric_contract']['files']['model/robot_arm.urdf'].update(kind='OPAQUE'),
            'contract_coverage': lambda r: r['numeric_contract']['files']['model/robot_arm.urdf'].update(numeric_components=511),
        }
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                receipt = json.loads(self.raw); mutate(receipt)
                raw = self.d._canonical(receipt)
                with self.assertRaises(ValueError):
                    self.d.verify_workspace_receipt(self.bundle, raw, hashlib.sha256(raw).hexdigest())

    def test_provider_each_use_postyield_and_no_old_result_fallback(self):
        d = d_module(self.bundle, self.bundle['source/decision_schema.py'])
        expected_model = str(REPO / 'outputs/typed-decision-preflight-113/D-implementation/model/robot_arm.urdf')
        events = []
        @contextmanager
        def provider():
            events.append('enter')
            yield (self.bundle, self.raw, self.expected, expected_model)
            events.append('exit')
        d.bind_workspace(provider)
        d.verify_workspace(expected_model); d.verify_workspace(expected_model)
        self.assertEqual(events, ['enter', 'exit', 'enter', 'exit'])
        @contextmanager
        def rejected_exit():
            yield (self.bundle, self.raw, self.expected, expected_model)
            raise ValueError('expired at provider exit')
        d.bind_workspace(rejected_exit)
        with self.assertRaisesRegex(ValueError, 'provider exit'):
            d.verify_workspace(expected_model)
        with self.assertRaises(ValueError):
            d.verify_workspace(expected_model + '.other')

    def test_original_physical_functions_ast_and_direct_unbound_import(self):
        old = ast.parse((REPO / 'src/simulation/clock_ready_resume_108/validate.py').read_bytes())
        new = ast.parse(self.bundle['source/validate.py'])
        original = {node.name: ast.dump(node, include_attributes=False) for node in old.body
                    if isinstance(node, ast.FunctionDef) and node.name != 'verify_workspace'}
        current = {node.name: ast.dump(node, include_attributes=False) for node in new.body
                   if isinstance(node, ast.FunctionDef)}
        self.assertEqual(len(original), 45)
        self.assertTrue(all(current[name] == value for name, value in original.items()))
        direct = d_module(self.bundle)
        cfg = json.loads(self.bundle['source/config.json'])
        model = direct.pmodel(REPO / cfg['model_dir'] / 'robot_arm.urdf')
        self.assertEqual(len(model['movable']), 9)

    def test_full_memory_matches_original_realpath_and_filesystem_block_positive(self):
        """Own HOST result only; root production receipt remains exclusively owned."""
        cfg = json.loads(self.bundle['source/config.json'])
        generator_path = REPO / 'src/simulation/clock_ready_resume_108/workspace.py'
        oracle_path = REPO / cfg['refs']['sampling-oracle.py']['path']
        generator = helpers.load_raw('realpath_generator113', self.bundle['source/workspace.py'], generator_path)
        oracle = helpers.load_raw('realpath_oracle113', self.bundle['ref/sampling-oracle.py'], oracle_path)
        reference_data = json.loads(self.bundle['ref/workspace.json'])
        reference = generator.validate_result(reference_data,
            oracle.pmodel(REPO / cfg['model_dir'] / 'robot_arm.urdf'), oracle, full=True)
        gate = {'active': False, 'events': 0}
        def audited(event, args):
            if gate['active'] and event in {'open', 'os.listdir', 'os.scandir'}:
                gate['events'] += 1
                raise PermissionError('HOST real filesystem blocked')
        sys.addaudithook(audited)
        try:
            gate['active'] = True
            with self.assertRaisesRegex(PermissionError, 'filesystem blocked'):
                open(SRC / 'validate.py', 'rb')
            self.assertEqual(gate['events'], 1)
            gate['events'] = 0
            raw = self.d.produce_workspace_receipt(self.bundle)
        finally:
            gate['active'] = False
        self.assertEqual(gate['events'], 0)
        data, metrics = self.d.verify_workspace_receipt(self.bundle, raw, hashlib.sha256(raw).hexdigest())
        self.assertEqual(data, reference_data)
        self.assertEqual(metrics, reference)
        self.assertEqual(json.loads(raw)['sample_count'], 8192)
        self.assertEqual(json.loads(raw)['path_state_count'], 6241)
        self.assertEqual(len(json.loads(raw)), 12)


if __name__ == '__main__':
    helpers.run_host_tests(__name__, Path(__file__).stem)
