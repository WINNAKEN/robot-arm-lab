"""112 D HOST evidence; synthetic authorities are not code/native acceptance."""
import ast
import builtins
import contextlib
import copy
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name('validate.py')
OUT = ROOT / 'outputs/static-workspace-preflight-112/D-repair-r1/raw'


def load_module(path, name):
    raw = Path(path).read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path); module.__source_bytes__ = raw
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def template_bundle(root=ROOT, module=None):
    """Current source20 + canonical model/ref fixture; explicit HOST authority only."""
    module = module or load_module(SOURCE, 'fixture_validate112')
    legacy = root / 'src/simulation/clock_ready_resume_108'
    current = root / 'src/simulation/static_workspace_preflight_112'
    cfg = json.loads((current / 'config.json').read_bytes())
    bundle = {}
    for name in module._SOURCE_NAMES:
        if name == 'validate.py': raw = module.__source_bytes__
        elif name in ('bootstrap.py', 'driver.py', 'config.json'): raw = (current / name).read_bytes()
        elif name == 'winjob.py': raw = (root / 'src/simulation/single_host_controller_110/winjob.py').read_bytes()
        else: raw = (legacy / name).read_bytes()
        bundle['source/' + name] = raw
    for name in module._MODEL_NAMES:
        bundle['model/' + name] = (root / cfg['model_dir'] / name).read_bytes()
    for name in module._REF_NAMES:
        bundle['ref/' + name] = (root / cfg['refs'][name]['path']).read_bytes()
    return bundle


def synthetic_receipt(bundle, module):
    """SYNTHETIC_HOST_FIXTURE_NOT_REVIEW: consumer/owner fixtures only."""
    data = module._json(bundle['ref/workspace.json']); metrics = module._metrics(data)
    sha = module._digest(bundle['ref/workspace.json'])
    return module._canonical({'schema_version': 1, 'unit': '112', 'scope': module._WORKSPACE_SCOPE,
        'inputs': module._input_pins(bundle), 'algorithms': module._algorithm_pins(bundle),
        'full_sampling': True, 'sample_count': 8192, 'path_state_count': 6241,
        'workspace_sha256': sha, 'metrics': metrics, 'result_sha256': module._result_sha(sha, metrics)})


class WorkspaceReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cls.module = load_module(SOURCE, 'validate112_host')
        cls.bundle = template_bundle(module=cls.module)
        cls.model_path = OUT / 'realpath-fixture/model/robot_arm.urdf'
        base = cls.model_path.parent.parent
        for name, raw in cls.bundle.items():
            target = base / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        original = load_module(ROOT / 'src/simulation/clock_ready_resume_108/validate.py', 'original108_host')
        start = time.monotonic()
        cls.original_data, cls.original_metrics = original.verify_workspace(cls.model_path)
        original_seconds = time.monotonic() - start
        blocked = []
        def no_read(*args, **kwargs):
            blocked.append(str(args[:1])); raise AssertionError('actual filesystem read in sealed producer')
        start = time.monotonic()
        with contextlib.ExitStack() as stack:
            for obj, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                              (Path, 'open'), (Path, 'read_bytes'), (Path, 'read_text'), (ET, 'parse')):
                stack.enter_context(mock.patch.object(obj, name, no_read))
            cls.receipt = cls.module.produce_workspace_receipt(cls.bundle)
        producer_seconds = time.monotonic() - start
        cls.receipt_sha = hashlib.sha256(cls.receipt).hexdigest()
        cls.data, cls.metrics = cls.module.verify_workspace_receipt(cls.bundle, cls.receipt, cls.receipt_sha)
        cls.blocked = blocked
        (OUT / 'full-positive.json').write_text(json.dumps({
            'scope': 'HOST_ORIGINAL_REALPATH_VS_MEMORY_FS_READ_BLOCKED_NOT_REVIEW',
            'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'original_full_seconds': original_seconds, 'memory_full_seconds': producer_seconds,
            'actual_fs_read_attempts': blocked, 'input_count': len(cls.bundle),
            'receipt_sha256': cls.receipt_sha, 'receipt_bytes': len(cls.receipt),
            'metrics': cls.metrics, 'data_equal': cls.original_data == cls.data,
            'metrics_equal': cls.original_metrics == cls.metrics}, indent=2) + '\n', encoding='utf-8')
        (OUT / 'actual-producer-host-receipt.json').write_bytes(cls.receipt)

    def setUp(self):
        self.module._workspace_use = None

    def verify(self, raw=None, bundle=None):
        raw = self.receipt if raw is None else raw
        return self.module.verify_workspace_receipt(self.bundle if bundle is None else bundle,
                                                   raw, hashlib.sha256(raw).hexdigest())

    def mutate_receipt(self, callback):
        value = json.loads(self.receipt); callback(value)
        return self.module._canonical(value)

    def test_actual_full_original_and_memory_are_identical(self):
        self.assertEqual(self.original_data, self.data)
        self.assertEqual(self.original_metrics, self.metrics)
        self.assertEqual(self.blocked, [])
        self.assertEqual((self.metrics['samples'], self.metrics['path_states']), (8192, 6241))

    def test_original_all_physical_function_asts_preserved(self):
        old = ast.parse((ROOT / 'src/simulation/clock_ready_resume_108/validate.py').read_bytes())
        new = ast.parse(SOURCE.read_bytes())
        current = {f.name: ast.dump(f, include_attributes=False) for f in new.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for function in old.body:
            if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and function.name != 'verify_workspace':
                self.assertEqual(ast.dump(function, include_attributes=False), current[function.name], function.name)

    def test_physical_import_allowed_without_binding_or_metadata(self):
        raw = SOURCE.read_bytes(); module = types.ModuleType('scene_direct_exec')
        module.__file__ = str(SOURCE); exec(compile(raw, str(SOURCE), 'exec'), module.__dict__)
        model = module.pmodel(self.model_path)
        self.assertEqual(len(model['movable']), 9)
        with self.assertRaisesRegex(ValueError, 'provider must be bound'):
            module.verify_workspace(self.model_path)

    def test_exact_closed_key47_and_bytes_only(self):
        mutations = [lambda b: b.pop('model/README.md'), lambda b: b.update({'source/extra.py': b'x'}),
            lambda b: b.update({'source/config.json': bytearray(b'{}')}),
            lambda b: b.update({'model/../README.md': b'x'}),
            lambda b: b.update({'ref/kernel.py': b''})]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bundle = dict(self.bundle); mutation(bundle)
                with self.assertRaises(ValueError): self.verify(bundle=bundle)

    def test_each_input_group_change_rejected(self):
        for name in ('source/driver.py', 'model/meshes/Base.stl', 'ref/kernel.py'):
            with self.subTest(name=name):
                bundle = dict(self.bundle); bundle[name] += b'\n'
                with self.assertRaisesRegex(ValueError, 'current input bytes'): self.verify(bundle=bundle)

    def test_old_unit_active_and_bool_template_rejected(self):
        for field, value in (('experiment_id', 'known_lifetime_111'), ('deadline_unix', 1),
                             ('deadline_unix', False), ('deadline_unix', 0.0), ('remote_root', '/old/111/worker/runs')):
            with self.subTest(field=field, value=value):
                bundle = dict(self.bundle); cfg = json.loads(bundle['source/config.json']); cfg[field] = value
                bundle['source/config.json'] = self.module._canonical(cfg)
                with self.assertRaises(ValueError): self.verify(bundle=bundle)

    def test_loaded_source_identity_and_fixed_executable_pins(self):
        for name in ('source/validate.py', 'source/workspace.py', 'ref/sampling-oracle.py'):
            with self.subTest(name=name):
                bundle = dict(self.bundle); bundle[name] += b'\n'
                with self.assertRaises(ValueError): self.module.produce_workspace_receipt(bundle)

    def test_receipt_independent_expected_sha_required(self):
        for sha in ('0' * 64, '', None, True, 'A' * 64):
            with self.subTest(sha=sha):
                with self.assertRaises(ValueError): self.module.verify_workspace_receipt(self.bundle, self.receipt, sha)

    def test_receipt_closed_schema_and_types(self):
        mutations = [lambda r: r.update(extra=1), lambda r: r.pop('metrics'),
            lambda r: r.update(unit='111'), lambda r: r.update(unit=112),
            lambda r: r.update(schema_version=True), lambda r: r.update(scope='NATIVE_AUTHORITY'),
            lambda r: r.update(full_sampling=1), lambda r: r.update(sample_count=True),
            lambda r: r.update(sample_count=8191), lambda r: r.update(path_state_count=6240),
            lambda r: r['inputs']['model/README.md'].update(bytes=True),
            lambda r: r['inputs']['model/README.md'].update(extra=1),
            lambda r: r['algorithms'].update(extra='x'),
            lambda r: r['algorithms'].update(mode='SHORTCUT'),
            lambda r: r['metrics'].update(samples=True),
            lambda r: r['metrics'].update(feasible=r['metrics']['feasible'] + 1),
            lambda r: r.update(result_sha256='0' * 64),
            lambda r: r.update(workspace_sha256='0' * 64)]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(ValueError): self.verify(self.mutate_receipt(mutation))

    def test_receipt_duplicate_nonfinite_and_noncanonical_json(self):
        raws = [self.receipt + b'\n', b'{"unit":"112","unit":"112"}', b'{"bad":NaN}',
                self.receipt.replace(b'"sample_count":8192', b'"sample_count":Infinity')]
        for raw in raws:
            with self.subTest(raw=raw[:80]):
                with self.assertRaises(ValueError): self.verify(raw)

    def test_consumer_does_not_execute_full_math(self):
        with mock.patch.object(self.module, 'produce_workspace_receipt', side_effect=AssertionError('producer called')), \
             mock.patch.object(self.module, '_memory_modules', side_effect=AssertionError('math loaded')):
            data, metrics = self.verify()
        self.assertEqual(metrics, self.original_metrics)
        self.assertEqual(data, self.original_data)

    def test_returns_are_fresh_and_mutation_is_not_reused(self):
        first, metrics = self.verify(); first['samples'].clear(); metrics['samples'] = 0
        second, newmetrics = self.verify()
        self.assertEqual(len(second['samples']), 8192); self.assertEqual(newmetrics['samples'], 8192)
        self.assertIsNot(first, second); self.assertIsNot(metrics, newmetrics)

    def test_bundle_is_separately_frozen_before_execution(self):
        supplied = dict(self.bundle); real = self.module._memory_modules
        def mutate_after_freeze(frozen):
            supplied['ref/workspace.json'] = b'{}'
            self.assertEqual(frozen['ref/workspace.json'], self.bundle['ref/workspace.json'])
            with self.assertRaises(TypeError): frozen['ref/workspace.json'] = b'{}'
            raise RuntimeError('stop after demonstrating immutable separate copy')
        with mock.patch.object(self.module, '_memory_modules', mutate_after_freeze):
            with self.assertRaisesRegex(RuntimeError, 'separate copy'):
                self.module.produce_workspace_receipt(supplied)
        self.assertIsNotNone(real)

    def test_bound_provider_every_use_and_exit_precedes_return(self):
        calls = []
        @contextlib.contextmanager
        def provider():
            calls.append('enter')
            yield (dict(self.bundle), self.receipt, self.receipt_sha, self.model_path)
            calls.append('exit')
        self.module.bind_workspace(provider)
        first = self.module.verify_workspace(self.model_path)
        self.assertEqual(calls, ['enter', 'exit'])
        first[1]['samples'] = 0
        second = self.module.verify_workspace(self.model_path)
        self.assertEqual(calls, ['enter', 'exit', 'enter', 'exit']); self.assertEqual(second[1]['samples'], 8192)

    def test_provider_second_use_failure_and_exit_failure_propagate(self):
        calls = []
        @contextlib.contextmanager
        def provider():
            calls.append('enter')
            if len(calls) > 1: raise RuntimeError('current authority ended')
            yield (dict(self.bundle), self.receipt, self.receipt_sha, self.model_path)
        self.module.bind_workspace(provider); self.module.verify_workspace(self.model_path)
        with self.assertRaisesRegex(RuntimeError, 'authority ended'): self.module.verify_workspace(self.model_path)
        @contextlib.contextmanager
        def exit_failure():
            yield (dict(self.bundle), self.receipt, self.receipt_sha, self.model_path)
            raise RuntimeError('owner expired on return')
        self.module.bind_workspace(exit_failure)
        with self.assertRaisesRegex(RuntimeError, 'expired on return'): self.module.verify_workspace(self.model_path)

    def test_missing_binding_packet_and_path_alias_rejected(self):
        with self.assertRaises(ValueError): self.module.verify_workspace(self.model_path)
        with self.assertRaises(ValueError): self.module.bind_workspace(None)
        for packet in ([], (), (self.bundle, self.receipt, self.receipt_sha),
                       (self.bundle, self.receipt, self.receipt_sha, str(self.model_path) + '.alias')):
            @contextlib.contextmanager
            def provider(): yield packet
            self.module.bind_workspace(provider)
            with self.assertRaises(ValueError): self.module.verify_workspace(self.model_path)
        @contextlib.contextmanager
        def provider(): yield (dict(self.bundle), self.receipt, self.receipt_sha, self.model_path)
        self.module.bind_workspace(provider)
        for path in (str(self.model_path.parent / '..' / 'model' / 'robot_arm.urdf'), 'model/robot_arm.urdf'):
            with self.assertRaises(ValueError): self.module.verify_workspace(path)

    def test_producer_rejects_malformed_sample_and_path(self):
        for field, mutation in (('samples', lambda rows: rows[0]['tcp'].__setitem__(0, True)),
                                ('path_checks', lambda rows: rows[0].__setitem__('time_s', False))):
            with self.subTest(field=field):
                bundle = dict(self.bundle); data = copy.deepcopy(self.data); mutation(data[field])
                bundle['ref/workspace.json'] = self.module._canonical(data)
                with self.assertRaises(ValueError): self.module.produce_workspace_receipt(bundle)

    def rebound_receipt(self, bundle):
        """Coherent HOST authority control: changing only a key hash cannot fail this test."""
        value = json.loads(self.receipt)
        value['inputs'] = self.module._input_pins(bundle)
        value['algorithms'] = self.module._algorithm_pins(bundle)
        value['workspace_sha256'] = self.module._digest(bundle['ref/workspace.json'])
        value['result_sha256'] = self.module._result_sha(value['workspace_sha256'], value['metrics'])
        return self.module._canonical(value)

    def test_r1_three_exact_numeric_witnesses_actual_producer_and_rebound_consumer(self):
        evidence = []
        for name, path, bad in (('ref/workspace.json', ('gravity', 0), False),
                                ('source/config.json', ('width',), False),
                                ('source/config.json', ('width',), 'OVERFLOW_1e999')):
            bundle = dict(self.bundle); value = json.loads(bundle[name]); target = value
            for key in path[:-1]: target = target[key]
            target[path[-1]] = bad
            raw = self.module._canonical(value)
            if bad == 'OVERFLOW_1e999': raw = raw.replace(b'"OVERFLOW_1e999"', b'1e999')
            bundle[name] = raw; receipt = self.rebound_receipt(bundle)
            errors = {}
            for api, call in (
                ('actual_producer', lambda: self.module.produce_workspace_receipt(bundle)),
                ('actual_consumer_coherently_rebound_expected_sha', lambda: self.module.verify_workspace_receipt(
                    bundle, receipt, hashlib.sha256(receipt).hexdigest()))):
                with self.subTest(document=name, path=path, bad=bad, api=api):
                    with self.assertRaisesRegex(ValueError, 'numeric role|integer role|nonfinite JSON number') as raised:
                        call()
                    errors[api] = str(raised.exception)
            evidence.append({'document': name, 'path': path, 'bad': bad,
                             'input_pins_coherently_rebound': True, 'errors': errors})
        (OUT / 'R1-three-witness-closure.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')

    def test_required_numeric_roles_and_collection_types_across_all_decision_documents(self):
        cases = [
            ('source/config.json', ('height',), '480'),
            ('source/config.json', ('fps',), None),
            ('source/config.json', ('sdk', 'cap_Nm', 0), False),
            ('source/config.json', ('sdk', 'steps'), 10.0),
            ('source/config.json', ('floor', 'position', 0), {}),
            ('source/program.json', ('drive', 'kp'), False),
            ('source/program.json', ('segments', 0, 'opening_m'), None),
            ('source/program.json', ('resolution', 0), 640.0),
            ('source/program.json', ('settling', 'window_s'), []),
            ('model/asset-ledger.json', ('links', 'KG1', 'mass_kg'), False),
            ('model/asset-ledger.json', ('links', 'KG1', 'com_m', 0), '0'),
            ('model/asset-ledger.json', ('source_items', 0, 'triangles'), 5916.0),
            ('model/provenance.json', ('input_census', 'models/arm-v3-kg1-assembly/assembly.json', 'bytes'), True),
            ('ref/model-submission.json', ('source_and_evidence_count',), '681'),
            ('ref/model-submission.json', ('fresh_controls',), False),
            ('ref/prefix-seal.json', ('schema_version',), True),
            ('ref/workspace.json', ('settings', 'seed'), True),
            ('ref/workspace.json', ('samples', 0, 'q', 'J1'), False),
            ('ref/workspace.json', ('samples', 0, 'tcp', 0), None),
            ('ref/workspace.json', ('path_checks', 0, 'phase_index'), 0.0),
            ('ref/workspace.json', ('cloud', 'voxels', 0, 'key', 0), False),
            ('ref/workspace.json', ('model_inputs', 'robot_arm.urdf', 'bytes'), '1'),
            ('ref/workspace.json', ('stats', 'peak_velocity', 'J1'), {}),
        ]
        evidence = []
        for name, path, bad in cases:
            with self.subTest(document=name, path=path, bad=bad):
                value = json.loads(self.bundle[name]); target = value
                for key in path[:-1]: target = target[key]
                target[path[-1]] = bad
                with self.assertRaisesRegex(ValueError, 'numeric role|integer role|numeric collection') as raised:
                    self.module._decision_json(self.module._canonical(value), name)
                evidence.append({'document': name, 'path': path, 'bad': bad, 'error': str(raised.exception)})
        (OUT / 'broader-numeric-role-negatives.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')

    def test_nonfinite_overflow_all_documents_and_closed_logical_roles(self):
        roles = {}
        for name in self.module._DECISION_SCHEMAS:
            raw = self.bundle[name]; value = self.module._decision_json(raw, name)
            numbers = booleans = 0
            def count(item):
                nonlocal numbers, booleans
                if type(item) is bool: booleans += 1
                elif type(item) in (int, float): numbers += 1
                elif type(item) is dict:
                    for child in item.values(): count(child)
                elif type(item) is list:
                    for child in item: count(child)
            count(value); roles[name] = {'numeric_leaves': numbers, 'valid_logical_boolean_leaves': booleans}
            for number in (b'1e999', b'-1e999', b'NaN', b'Infinity', b'-Infinity'):
                with self.subTest(name=name, number=number):
                    # Even an extra opaque metadata branch cannot hide nonfinite numbers.
                    changed = raw.rstrip()[:-1] + b',"unexpected_nonfinite":' + number + b'}'
                    with self.assertRaisesRegex(ValueError, 'nonfinite JSON'):
                        self.module._decision_json(changed, name)
            value['unexpected_numeric'] = False
            with self.assertRaisesRegex(ValueError, 'undeclared decision numeric/logical role'):
                self.module._decision_json(self.module._canonical(value), name)
        self.assertGreater(sum(v['numeric_leaves'] for v in roles.values()), 500000)
        self.assertGreater(sum(v['valid_logical_boolean_leaves'] for v in roles.values()), 8192)
        (OUT / 'normal-numeric-logical-role-coverage.json').write_text(json.dumps(roles, indent=2) + '\n', encoding='utf-8')

    def test_actual_B_build_rejects_width_bool_before_creating_receipt(self):
        host = load_module(SOURCE.with_name('test_bootstrap.py'), 'B_actual_numeric_repair_host')
        b = host.b; root = OUT / 'actual-B-width-bool-fixture'
        root.mkdir(parents=True, exist_ok=True)
        census = ROOT / b.OUT / 'dependency-census-pre-receipt.json'
        for record in b.read(census)['records']:
            target = root / record['target_path']; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / record['source_path']).read_bytes())
        for name in ('bootstrap.py', 'driver.py', 'config.json', 'validate.py'):
            target = root / b.SRC / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / b.SRC / name).read_bytes())
        target_census = root / b.OUT / census.name; target_census.parent.mkdir(parents=True, exist_ok=True)
        target_census.write_bytes(census.read_bytes())
        config_path = root / b.SRC / 'config.json'; config = b.read(config_path); config['width'] = False
        config_path.write_bytes(b.canonical(config))
        with self.assertRaisesRegex(ValueError, 'required integer role') as raised:
            b.build_static_receipt(root)
        self.assertFalse((root / b.RECEIPT).exists())
        self.assertFalse((root / b.OUT / 'native-approval.json').exists())
        (OUT / 'actual-B-width-bool-rejection.json').write_text(json.dumps({
            'scope': 'HOST_FIXTURE_ONLY_NO_PRODUCTION_OR_NATIVE_AUTHORITY',
            'actual_api': 'B.build_static_receipt -> actual D.produce_workspace_receipt',
            'error': str(raised.exception), 'receipt_created': False,
            'native_approval_created': False}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    unittest.main(verbosity=2)
