"""119 HOST contract probes and deterministic support/profile preparation; no SDK or devices."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'outputs/mp18-isaac-119/A'
spec = importlib.util.spec_from_file_location('contract119', HERE / 'contract.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
MODEL = ROOT / 'models/robot-arm-urdf-v4'
CFG = C.parse((HERE / 'config.json').read_bytes())
PROGRAM = C.parse((HERE / 'program.json').read_bytes())


def triangle_data(model):
    import numpy as np
    import struct
    dtype = np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')])
    result = {}
    for name in C.PHYSICAL:
        raw = (MODEL / ('meshes/' + name + '.stl')).read_bytes()
        count = struct.unpack_from('<I', raw, 80)[0]
        result[name] = np.frombuffer(raw, dtype=dtype, offset=84, count=count)['v'].astype(float)
    return result


def static_fixture(model):
    world = C.fk(model, {})
    links = []
    for name in C.PHYSICAL:
        b = model['links'][name]
        links.append({'name': name, 'mass': b['mass'], 'com': b['com'], 'inertia_link_about_com': b['inertia'],
                      'T_world': world[name], 'visual_count': len(b['visuals']), 'collision_count': len(b['collisions'])})
    joints = []
    for name, j in model['joints'].items():
        if name == 'tool0_mount':
            continue
        anchor1 = C.ident()
        axis = None
        if j['type'] != 'fixed':
            axis = next(k for k, v in zip(('X', 'Y', 'Z'), j['axis']) if abs(v) > .5)
            if min(j['axis']) < -.5:
                anchor1 = C.tf([0, 0, 0], C.rotation([0, 1, 0], 3.141592653589793))
        joints.append({'name': name, 'parent': j['parent'], 'child': j['child'], 'type': j['type'],
                       'enabled': True, 'anchor0': C.mm(j['matrix'], anchor1), 'anchor1': anchor1,
                       'axis': axis, 'lower': j.get('lower'), 'upper': j.get('upper')})
    joints.append({'name': 'root_joint', 'type': 'fixed', 'parent': '__world__', 'child': 'Base', 'enabled': True})
    return {'links': links, 'joints': joints, 'fixed_base': True, 'articulation_count': 1,
            'tool0': {'physical': False, 'T_world': world['tool0']}}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = C.verify_inputs(MODEL, CFG, ROOT)

    def test_01_complete_model_and_origin(self):
        m = self.model
        self.assertEqual(len(m['movable']), 9)
        self.assertAlmostEqual(sum(b['mass'] or 0 for b in m['links'].values()), 8.863854736164349, places=12)
        self.assertEqual(m['joints']['J4']['origin'][0], [.165, 0, 0])
        old = copy.deepcopy(CFG)
        old['model_pins']['robot_arm.urdf']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Model pin'):
            C.verify_inputs(MODEL, old)

    def test_02_closed_json_and_paths(self):
        for raw in ('{"x":1,"x":2}', '{"v":NaN}'):
            with self.assertRaises(ValueError):
                C.parse(raw)
        for path in ('../file', 'a/../file', 'a/./file', '/absolute', 'a:b', 'a\\file', 'a//file'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                C.relative(path)

    def test_03_cap_authority(self):
        decision = {'unit': 119, 'cap_mode': 'legacy', 'cap_approved': False,
                    'user_request': '119_SIMULATION_VIDEO_DRIVE', 'user_reply': 'HOST FIXTURE ONLY',
                    'hardware_approved': False}
        self.assertEqual(C.effective_caps(CFG, decision)['J2'], 6)
        decision.update(cap_mode='sim_override_12_7')
        with self.assertRaises(ValueError):
            C.effective_caps(CFG, decision)
        decision['cap_approved'] = True
        self.assertEqual(C.effective_caps(CFG, decision)['J2'], 12)
        for key, value in (('hardware_approved', True), ('cap_mode', 'arbitrary'), ('user_reply', '')):
            bad = dict(decision, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                C.effective_caps(CFG, bad)

    def test_04_named_force_mapping(self):
        reverse = list(reversed(C.NAMES))
        values = [float(C.NAMES.index(n)) for n in reverse]
        mapped, columns = C.map_gravity(reverse, C.NAMES, [99.] * 6 + values)
        self.assertEqual(mapped, {n: float(i) for i, n in enumerate(C.NAMES)})
        self.assertTrue(all(columns[n] >= 6 for n in C.NAMES))
        with self.assertRaises(ValueError):
            C.map_gravity(reverse, C.NAMES, [0.] * 10)
        with self.assertRaises(ValueError):
            C.named_columns(C.NAMES[:-1] + [C.NAMES[0]], C.NAMES, [0.] * 9)

    def test_05_quintic_and_limits(self):
        for name, stage in PROGRAM['stages'].items():
            for t in (0, stage['duration_s']):
                row = C.target_at(PROGRAM, name, t)
                self.assertTrue(all(abs(v) < 1e-12 for v in row['targets'].values()))
                self.assertTrue(all(v == 0 for v in row['velocity_targets'].values()))
        middle = C.target_at(PROGRAM, 'large', 16)
        self.assertLessEqual(max(abs(x) for x in middle['reference_velocity'].values()), .5)
        self.assertEqual(middle['velocity_targets'], {n: C.binary32(x) for n, x in middle['reference_velocity'].items()})
        with self.assertRaises(ValueError):
            C.target_at(PROGRAM, 'large', 42.1)

    def test_06_actual_static_predicates(self):
        packet = static_fixture(self.model)
        self.assertEqual(C.verify_static(self.model, packet)['physical_bodies'], 11)
        changes = [('mass', lambda p: p['links'][0].update(mass=99)),
                   ('inertia', lambda p: p['links'][1].update(inertia_link_about_com=[[1, 0, 0]] * 3)),
                   ('visual', lambda p: p['links'][2].update(visual_count=1)),
                   ('base', lambda p: p.update(fixed_base=False)),
                   ('tool', lambda p: p['tool0'].update(physical=True)),
                   ('axis', lambda p: p['joints'][0].update(axis='X'))]
        for label, change in changes:
            bad = copy.deepcopy(packet)
            change(bad)
            with self.subTest(label=label), self.assertRaises(ValueError):
                C.verify_static(self.model, bad)

    def test_07_checkpoint_not_transient(self):
        target = C.target_at(PROGRAM, 'hold', 2)
        zero = dict(target['targets'])
        self.assertTrue(C.phase_check(self.model, 'hold', zero, zero, target, PROGRAM)['passed'])
        bad = dict(zero, J3=.02)
        self.assertFalse(C.phase_check(self.model, 'hold', bad, zero, target, PROGRAM)['passed'])
        self.assertFalse(C.phase_check(self.model, 'hold', zero, zero, target, PROGRAM, min_world_z=-.01)['passed'])

    def test_08_gravity_from_world_com(self):
        from scipy.spatial.transform import Rotation
        world = C.fk(self.model, {})
        poses, masses = [], []
        for name in C.PHYSICAL:
            t = world[name]
            xyzw = Rotation.from_matrix([row[:3] for row in t[:3]]).as_quat()
            poses.append({'name': name, 'position': [row[3] for row in t[:3]],
                          'orientation_wxyz': [xyzw[3], *xyzw[:3]]})
            b = self.model['links'][name]
            masses.append({'name': name, 'mass': b['mass'], 'com': b['com']})
        ff = C.gravity_reference(self.model, poses, masses)
        self.assertAlmostEqual(ff['J2'], -9.418032982363094, places=8)
        self.assertAlmostEqual(ff['J3'], -5.23524289129088, places=8)
        self.assertEqual(set(C.remaining_caps(self.model, ff)[1]), {'J2', 'J3'})
        self.assertEqual(C.remaining_caps(self.model, ff, CFG['cap_modes']['sim_override_12_7'])[1], [])

    def test_09_full_facets_and_interior_mutation(self):
        actual = triangle_data(self.model)
        proof = C.verify_geometry(self.model, actual)
        self.assertEqual(set(proof), set(C.PHYSICAL))
        # Same face count and AABB, changed interior vertex: the old bounds-only weakness.
        import numpy as np
        original = actual['Base']
        bad = original.copy()
        bad[0, 0] = (bad[0, 0] + bad.reshape((-1, 3)).mean(axis=0)) / 2
        self.assertTrue(np.array_equal(original.min(axis=(0, 1)), bad.min(axis=(0, 1))))
        self.assertTrue(np.array_equal(original.max(axis=(0, 1)), bad.max(axis=(0, 1))))
        actual['Base'] = bad
        with self.assertRaisesRegex(ValueError, 'facet|multiplicity'):
            C.verify_geometry(self.model, actual)
        actual['Base'] = original.copy()
        actual['Base'][0] = actual['Base'][1]
        with self.assertRaisesRegex(ValueError, 'facet|multiplicity'):
            C.verify_geometry(self.model, actual)

    def test_10_complete_colored_visual_partition_and_swap(self):
        import numpy as np
        import struct
        dtype = np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')])
        groups, actual = {}, {}
        for name in C.PHYSICAL:
            for v in self.model['links'][name]['visuals']:
                rel = v['file']
                raw = C.path_in(MODEL, rel).read_bytes()
                count = struct.unpack_from('<I', raw, 80)[0]
                groups[rel] = [rel]
                actual[rel] = np.frombuffer(raw, dtype=dtype, offset=84, count=count)['v'].astype(float)
        self.assertEqual(len(C.verify_geometry(self.model, actual, visual_groups=groups)), 47)
        a, b = [v['file'] for v in self.model['links']['Base']['visuals']][:2]
        swapped = dict(actual)
        swapped[a], swapped[b] = actual[b], actual[a]
        with self.assertRaisesRegex(ValueError, 'facet|multiplicity'):
            C.verify_geometry(self.model, swapped, visual_groups=groups)
        missing = dict(groups)
        missing.pop(a)
        with self.assertRaisesRegex(ValueError, 'partition'):
            C.verify_geometry(self.model, actual, visual_groups=missing)
        duplicate = dict(groups, **{a: groups[b]})
        with self.assertRaisesRegex(ValueError, 'partition'):
            C.verify_geometry(self.model, actual, visual_groups=duplicate)


def prepare():
    model = C.verify_inputs(MODEL, CFG, ROOT)
    support = C.build_support(model)
    receipt = C.validate_program(PROGRAM, model, support)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'support.json').write_text(json.dumps(support, separators=(',', ':')) + '\n', encoding='utf-8')
    (OUT / 'workspace.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preparation.json').write_text(json.dumps({'contract_sha256': C.sha(HERE/'contract.py'),
        'program_sha256': C.sha(HERE/'program.json'), 'config_sha256': C.sha(HERE/'config.json'),
        'support_sha256': C.sha(OUT/'support.json'), 'workspace_sha256': C.sha(OUT/'workspace.json'),
        'model_files': 74, 'SDK': 0, 'hardware': 0}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'prepared': True, 'stages': receipt['stages'], 'SDK': 0}), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--prepare']:
        prepare()
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
