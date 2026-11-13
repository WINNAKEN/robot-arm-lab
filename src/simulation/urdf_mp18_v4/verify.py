"""118: offline verification of directly authored XML against current MP18 CAD.

No XML or CAD writes. JSON is evidence only; this is not a URDF generator.
Use the existing mesh environment, with -I -B. No simulator or device I/O.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
import trimesh

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / 'models/robot-arm-urdf-v4'
OUT = ROOT / 'outputs/urdf-mp18-v4-118/C'
ARM = ['Base'] + [f'Link{i}' for i in range(1, 7)]
PHYSICAL = ARM + ['KG1', 'KG1_A', 'KG1_B', 'KG1_R']
DISPLAY_DEG = np.array([15., -50., 70., 15., 25., -10.])
AXES = np.array([[0., 0., 1.], [0., 1., 0.], [0., 1., 0.],
                 [1., 0., 0.], [0., 1., 0.], [1., 0., 0.]])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def semantics(element):
    """Compare XML meanings, ignoring authoring whitespace and attribute order."""
    return element.tag, dict(element.attrib), tuple(semantics(child) for child in element)


def readj(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def vec(element, key, default='0 0 0'):
    return np.fromstring(default if element is None else element.get(key, default), sep=' ')


def rotation(axis, angle):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    cross = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3) + math.sin(angle) * cross + (1. - math.cos(angle)) * (cross @ cross)


def origin(element):
    m = np.eye(4)
    r, p, y = vec(element, 'rpy')
    m[:3, :3] = rotation([0, 0, 1], y) @ rotation([0, 1, 0], p) @ rotation([1, 0, 0], r)
    m[:3, 3] = vec(element, 'xyz')
    return m


def forward(robot, values):
    joints = {j.get('name'): j for j in robot.findall('joint')}
    q = dict(values)

    def position(name, stack=()):
        if name in stack:
            raise ValueError('mimic cycle')
        j = joints[name]
        mimic = j.find('mimic')
        if mimic is None:
            return float(q.get(name, 0.))
        return (float(mimic.get('multiplier', '1')) *
                position(mimic.get('joint'), stack + (name,)) + float(mimic.get('offset', '0')))

    children = {j.find('child').get('link') for j in joints.values()}
    roots = {link.get('name') for link in robot.findall('link')} - children
    if len(roots) != 1:
        raise ValueError('not a single rooted tree')
    world = {roots.pop(): np.eye(4)}
    todo = list(joints.values())
    while todo:
        progress = False
        for joint in todo[:]:
            parent = joint.find('parent').get('link')
            if parent not in world:
                continue
            motion = np.eye(4)
            kind = joint.get('type')
            if kind in ('revolute', 'continuous'):
                motion[:3, :3] = rotation(vec(joint.find('axis'), 'xyz'), position(joint.get('name')))
            elif kind == 'prismatic':
                motion[:3, 3] = vec(joint.find('axis'), 'xyz') * position(joint.get('name'))
            elif kind != 'fixed':
                raise ValueError('unsupported joint type')
            child = joint.find('child').get('link')
            if child in world:
                raise ValueError('duplicate child')
            world[child] = world[parent] @ origin(joint.find('origin')) @ motion
            todo.remove(joint)
            progress = True
        if not progress:
            raise ValueError('disconnected/cyclic tree')
    return world


def run(xml_path=MODEL / 'robot_arm.urdf'):
    robot = ET.parse(xml_path).getroot()
    numeric = readj(MODEL / 'numeric-ledger.json')
    assets = readj(MODEL / 'asset-ledger.json')
    provenance = readj(MODEL / 'provenance.json')
    cad = module(ROOT / 'src/cad/manipulator-v2/layout.py', 'readonly_mp18_118_check')
    params = cad.load()
    checks = []

    def check(name, condition, **detail):
        checks.append({'name': name, 'met': bool(condition), **detail})

    link_map = {e.get('name'): e for e in robot.findall('link')}
    joint_map = {e.get('name'): e for e in robot.findall('joint')}
    check('exact_link_names', set(link_map) == set(PHYSICAL + ['tool0']))
    check('tree_size', len(joint_map) == 11 and len(link_map) == 12)
    check('movable_9_independent_7',
          sum(j.get('type') != 'fixed' for j in joint_map.values()) == 9 and
          sum(j.get('type') != 'fixed' and j.find('mimic') is None for j in joint_map.values()) == 7)
    check('empty_tool_frame', len(link_map['tool0']) == 0)
    original = assets['original_173_bodies']
    check('original_mass_rows', len(original) == 173 and all(row['match'] for row in original))
    replacement = assets['replaced_KG1_lump']
    check('gripper_replaced_once', replacement['count'] == 1 and abs(replacement['mass_kg'] - .1842) < 1e-12)
    components = assets['mass_components']
    check('mass_component_unique', len({c['id'] for c in components}) == len(components))
    zero_transforms = cad.link_transforms(params, [0.] * 6)
    part_frames = cad.frames(params)
    arm_component_errors = []
    for c in components:
        if c['link'] not in ARM:
            continue
        k = ARM.index(c['link'])
        expected_transform = np.linalg.inv(zero_transforms[k]) @ part_frames[c['source_frame']]
        source_centre = np.array([*c['source_com_mm'], 1.])
        expected_centre = (expected_transform @ source_centre)[:3] * .001
        expected_tensor = (expected_transform[:3, :3] @ np.asarray(c['source_inertia_kg_m2']) @
                           expected_transform[:3, :3].T)
        if not (np.allclose(c['T_link_from_source_mm'], expected_transform, atol=1e-10, rtol=0) and
                np.allclose(c['com_m'], expected_centre, atol=1e-12, rtol=0) and
                np.allclose(c['inertia_kg_m2'], expected_tensor, atol=1e-12, rtol=0)):
            arm_component_errors.append(c['id'])
    check('arm_component_frame_conversion', not arm_component_errors, errors=arm_component_errors)
    for name in PHYSICAL:
        group = [c for c in components if c['link'] == name]
        m = sum(c['mass_kg'] for c in group)
        centre = sum((c['mass_kg'] * np.asarray(c['com_m']) for c in group), np.zeros(3)) / m
        tensor = np.zeros((3, 3))
        for c in group:
            d = np.asarray(c['com_m']) - centre
            tensor += (np.asarray(c['inertia_kg_m2']) + c['mass_kg'] *
                       (np.dot(d, d) * np.eye(3) - np.outer(d, d)))
        expected = numeric['links'][name]
        check(f'{name}_component_aggregation', abs(m - expected['mass_kg']) < 1e-12 and
              np.allclose(centre, expected['com_m'], rtol=0, atol=1e-12) and
              np.allclose(tensor, expected['inertia_kg_m2'], rtol=0, atol=1e-12))
    preserved = numeric['sourcechecks']['preserved']
    check('source_inputs_preserved', preserved is True)
    source_errors = []
    for rel, recorded in provenance['input_census'].items():
        path = (ROOT / rel).resolve()
        if not (path.is_relative_to(ROOT.resolve()) and path.is_file() and
                path.stat().st_size == recorded['bytes'] and sha(path) == recorded['sha256']):
            source_errors.append(rel)
    check('current_input_hashes', not source_errors, files=len(provenance['input_census']), errors=source_errors)
    check('original_load_pins', all(r['match'] for r in numeric['sourcechecks']['load_pins_match']) and
          len(numeric['sourcechecks']['load_pins_match']) == 50)
    builds = numeric['sourcechecks']['build_pins_match']
    check('original_build_pins', len(builds) == 54 and all(r['match'] for r in builds))
    pin_errors = []
    for row in numeric['sourcechecks']['load_pins_match'] + builds:
        path = (ROOT / row['path']).resolve()
        if not (path.is_relative_to(ROOT.resolve()) and path.is_file() and sha(path) == row['expected_sha256']):
            pin_errors.append(row['record_key'])
    check('live_build_and_load_proof', not pin_errors, records=104, errors=pin_errors)
    check('display_zero_source', np.array_equal(params['poses']['display_deg'], DISPLAY_DEG))
    old = ET.parse(ROOT / 'models/robot-arm-urdf-v3/robot_arm.urdf').getroot()
    old_joints = {j.get('name'): j for j in old.findall('joint')}
    lo, hi = [], []
    for i in range(6):
        name = f'J{i + 1}'
        j = joint_map[name]
        limit = j.find('limit')
        lo.append(float(limit.get('lower')))
        hi.append(float(limit.get('upper')))
        target = (np.array(params['poses']['wanted_ranges_deg'][name]) - DISPLAY_DEG[i]) * math.pi / 180
        check(f'{name}_range_offset', np.allclose([lo[-1], hi[-1]], target, atol=1e-12, rtol=0))
        check(f'{name}_axis', np.array_equal(vec(j.find('axis'), 'xyz'), AXES[i]))
        check(f'{name}_caps_unchanged', all(limit.get(k) == old_joints[name].find('limit').get(k)
                                           for k in ('effort', 'velocity')) and
              j.find('dynamics').attrib == old_joints[name].find('dynamics').attrib)
    lo, hi = np.array(lo), np.array(hi)
    cases = [('display', np.zeros(6)), ('cad_neutral', -DISPLAY_DEG * math.pi / 180),
             ('ready', (np.array(params['poses']['ready_deg']) - DISPLAY_DEG) * math.pi / 180)]
    for i in range(6):
        for edge, edge_values in [('lower', lo), ('upper', hi)]:
            q = np.zeros(6)
            q[i] = edge_values[i]
            cases.append((f'J{i+1}_{edge}', q))
    rng = np.random.default_rng(118)
    cases += [(f'combination_{i}', rng.uniform(lo, hi)) for i in range(64)]
    max_error = 0.
    for label, q in cases:
        actual = forward(robot, {f'J{i+1}': x for i, x in enumerate(q)})
        expected = cad.link_transforms(params, np.rad2deg(q) + DISPLAY_DEG)
        for index, link in enumerate(ARM):
            expected[index][:3, 3] *= .001
            error = float(np.max(np.abs(actual[link] - expected[index])))
            max_error = max(max_error, error)
        tool_expected = actual['Link6'] @ origin(ET.fromstring(
            '<origin xyz="0.131 0 0" rpy="1.5707963267948966 0 1.5707963267948966"/>'))
        check(f'FK_{label}', all(np.allclose(actual[link], expected[i], atol=1e-11, rtol=0)
                                for i, link in enumerate(ARM)) and
              np.allclose(actual['tool0'], tool_expected, atol=1e-11, rtol=0))
    # These controls demonstrate that FK comparison detects old length/sign regressions.
    stale_length = copy.deepcopy(robot)
    stale_length.find("joint[@name='J4']/origin").set('xyz', '0.14 0 0')
    stale_fk = forward(stale_length, {})
    correct_fk = forward(robot, {})
    check('negative_old_forearm_detected', np.linalg.norm(
        stale_fk['Link6'][:3, 3] - correct_fk['Link6'][:3, 3]) > .024)
    wrong_sign = copy.deepcopy(robot)
    wrong_sign.find("joint[@name='J3']/axis").set('xyz', '0 -1 0')
    wrong_fk = forward(wrong_sign, {'J3': .2})
    signed_fk = forward(robot, {'J3': .2})
    check('negative_joint_sign_detected', np.linalg.norm(
        wrong_fk['Link6'][:3, 3] - signed_fk['Link6'][:3, 3]) > .05)
    for gap in (0., .04, .08, .094):
        d = gap / 2 - .02
        fk = forward(robot, {'KG1_slide_A': d})
        a = np.linalg.inv(fk['KG1']) @ fk['KG1_A']
        b = np.linalg.inv(fk['KG1']) @ fk['KG1_B']
        r = np.linalg.inv(fk['KG1']) @ fk['KG1_R']
        check(f'gripper_gap_{gap:g}', np.allclose(a[:3, 3], [-gap/2, 0, 0], atol=1e-12) and
              np.allclose(b[:3, 3], [gap/2, 0, 0], atol=1e-12) and
              np.allclose(r[:3, :3], rotation([0, 1, 0], -(gap/2)/.0135), atol=1e-12) and
              np.allclose(r[:3, 3], [0, 0, .026], atol=1e-12))
    gripper_source = module(ROOT / 'src/simulation/gripper_urdf/assets.py', 'readonly_gripper_118_check')
    groups = {'F': 'KG1', 'A': 'KG1_A', 'B': 'KG1_B', 'R': 'KG1_R'}
    for gap in (0., .04, .08, .094):
        source_items = gripper_source.items(gap * 500.)
        fk = forward(robot, {'KG1_slide_A': gap/2 - .02})
        G_inv = np.linalg.inv(fk['KG1'])
        check(f'gripper_source_count_{gap:g}', len(source_items) == 47)
        for group, name in groups.items():
            source_vertices = np.concatenate([i['v'] for i in source_items if i['group'] == group]) * .001
            saved = trimesh.load(MODEL / 'meshes' / f'{name}.stl', force='mesh', process=False)
            placed = trimesh.transform_points(saved.vertices, G_inv @ fk[name])
            check(f'{name}_source_geometry_gap_{gap:g}',
                  np.allclose(np.array([placed.min(0), placed.max(0)]),
                              np.array([source_vertices.min(0), source_vertices.max(0)]), atol=3e-7, rtol=0))
    mass_sum = 0.
    meshes = {}
    for name in PHYSICAL:
        link = link_map[name]
        n = numeric['links'][name]
        inertial = link.find('inertial')
        mass = float(inertial.find('mass').get('value'))
        mass_sum += mass
        com = vec(inertial.find('origin'), 'xyz')
        it = inertial.find('inertia').attrib
        I = np.array([[float(it['ixx']), float(it['ixy']), float(it['ixz'])],
                      [float(it['ixy']), float(it['iyy']), float(it['iyz'])],
                      [float(it['ixz']), float(it['iyz']), float(it['izz'])]])
        eigen = np.linalg.eigvalsh(I)
        check(f'{name}_inertial', mass > 0 and abs(mass - n['mass_kg']) < 1e-12 and
              np.allclose(com, n['com_m'], rtol=0, atol=1e-12) and
              np.allclose(I, n['inertia_kg_m2'], rtol=0, atol=1e-12) and
              eigen[0] > 0 and eigen[0] + eigen[1] >= eigen[2] - 1e-12 and
              np.allclose(vec(inertial.find('origin'), 'rpy'), 0, atol=0))
        all_visual = []
        for kind in ('visual', 'collision'):
            elements = link.findall(kind)
            expected_records = {row['file']: row for row in n[kind + 's']}
            actual_references = [e.find('geometry/mesh').get('filename') for e in elements
                                 if e.find('geometry/mesh') is not None]
            check(f'{name}_{kind}_reference_partition', len(actual_references) == len(expected_records) and
                  set(actual_references) == set(expected_records))
            check(f'{name}_{kind}_present', len(elements) > 0)
            for element in elements:
                mesh_e = element.find('geometry/mesh')
                check(f'{name}_{kind}_identity', np.array_equal(origin(element.find('origin')), np.eye(4)) and
                      mesh_e is not None and np.array_equal(vec(mesh_e, 'scale', '1 1 1'), np.ones(3)))
                if mesh_e is None:
                    continue
                rel = mesh_e.get('filename')
                path = (MODEL / rel).resolve()
                check(f'{name}_{kind}_path', path.is_relative_to(MODEL.resolve()) and path.is_file())
                if rel not in meshes:
                    mesh = trimesh.load(path, force='mesh', process=False)
                    meshes[rel] = {'sha256': sha(path), 'triangles': len(mesh.faces),
                                   'bounds_m': mesh.bounds.tolist()}
                expected_record = expected_records.get(rel)
                check(f'{name}_{kind}_saved_mesh_sha:{rel}', expected_record is not None and
                      meshes[rel]['sha256'] == expected_record['sha256'] and
                      path.stat().st_size == expected_record['bytes'])
                if kind == 'visual':
                    all_visual.append(trimesh.load(path, force='mesh', process=False))
        visual = trimesh.util.concatenate(all_visual)
        whole = trimesh.load(MODEL / 'meshes' / f'{name}.stl', force='mesh', process=False)
        whole_path = MODEL / 'meshes' / f'{name}.stl'
        canonical_record = n['canonical_mesh_record']
        check(f'{name}_canonical_saved_mesh_sha', sha(whole_path) == canonical_record['sha256'] and
              whole_path.stat().st_size == canonical_record['bytes'])
        check(f'{name}_visual_coverage', len(visual.faces) == len(whole.faces) and
              np.allclose(visual.bounds, whole.bounds, rtol=0, atol=2e-7) and
              np.allclose(whole.bounds, n['bounds_m'], rtol=0, atol=2e-7))
    check('gripper_mass_conserved', abs(sum(numeric['links'][n]['mass_kg'] for n in PHYSICAL[7:]) - .1842) < 1e-12)
    check('current_mass_estimate', abs(mass_sum - 8.8639) < .00005,
          actual_kg=mass_sum, rounded_source_total_kg=8.8639)
    for j in ('KG1_slide_A', 'KG1_slide_B', 'KG1_pinion'):
        check(f'{j}_old_contract', semantics(joint_map[j]) == semantics(old_joints[j]))
    report = {'what': '118 offline URDF/CAD cross-check', 'verdict': 'PASS' if all(c['met'] for c in checks) else 'FAIL',
              'checks': checks, 'met': sum(c['met'] for c in checks),
              'unmet': sum(not c['met'] for c in checks), 'fk_cases': len(cases),
              'max_fk_matrix_error_m_or_unitless': max_error, 'mass_kg': mass_sum,
              'xml_sha256': sha(xml_path), 'numeric_sha256': sha(MODEL / 'numeric-ledger.json'),
              'meshes': meshes, 'check_urdf': 'SKIPPED_NOT_INSTALLED',
              'Isaac_SDK': 'NOT_RUN', 'self_collision': 'NOT_ACCEPTED', 'hardware_approved': False,
              'limits': 'designer proposal; independent-axis samples are not a collision-free configuration space'}
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=OUT / 'host.json')
    a = ap.parse_args()
    if not a.output.resolve().is_relative_to(OUT.resolve()):
        ap.error('verification evidence must stay in the owned C output directory')
    report = run()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('verdict', 'met', 'unmet', 'fk_cases', 'mass_kg')}))
    raise SystemExit(0 if report['verdict'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
