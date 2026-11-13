"""Offline audit of the fixed 133/05 actual body poses, using source envelopes."""
import argparse
import hashlib
import io
import itertools
import json
import os
import pathlib
import stat
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np
import scipy
import trimesh

# -I removes the script directory; import only this sibling explicitly.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import geometry as geo

RUN = '850124eb93cc4cc4945ee02c3aa1ed0d'
JOB = '816522a14e506263a7a7517ce76ad7deb23402ffc6bddd6c23513f306725a6ae'
F6_SHA = '3cf40c09cc20bac27195fc1963e997734f3dbc3e8e03b25bf737e0ecf97ace3f'
NATIVE_SHA = 'c4345f4461601566d9398a7ab6101217f2bfa0e1f851b8bfb33352687a92b4e2'
PLAN_SHA = 'cc5b21a58b3bd39863616b494ad6ccdfa4d86cd5d65283919dd623ed2e08d00c'
F6_PATH = 'outputs/mp18-manipulation-133/author/source-freeze.json'
ATTEMPT = 'outputs/mp18-manipulation-133/attempts/05'
URDF = 'models/robot-arm-urdf-v4/robot_arm.urdf'
LEDGER = 'models/robot-arm-urdf-v4/asset-ledger.json'
COMPONENTS = 'src/simulation/mp18_manipulation_133/jaw_components.json'
NATIVE_SOURCE = 'src/simulation/mp18_manipulation_133/native.py'
NAMES = ('Base', 'Link1', 'Link2', 'Link3', 'Link4', 'Link5', 'Link6', 'KG1', 'KG1_A', 'KG1_B', 'KG1_R')
CHECKPOINTS = (8, 39, 57, 80, 93)
ROWS = 11161
OUTPUT_ROOT = 'outputs/mp18-collision-audit-134'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def numeric(value, shape, label):
    array = np.asarray(value, dtype=float)
    need(array.shape == shape and np.isfinite(array).all(), 'Invalid finite '+label)
    return array


def scalar(value, target, label, tolerance=1e-8):
    need(type(value) in (int, float) and np.isfinite(value) and abs(value-target) <= tolerance, label)


class Producer:
    """Production always captures authenticated local bytes before interpretation."""
    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()
        self.manifest = {}
        self.raw = {}
        self.read(F6_PATH, F6_SHA)
        self.freeze = parse(self.raw[F6_PATH])
        self.read(ATTEMPT+'/native-result.json', NATIVE_SHA)
        self.native = parse(self.raw[ATTEMPT+'/native-result.json'])
        n = self.native
        need(n['unit'] == 133 and n['attempt'] == 5 and n['run_id'] == RUN and n['job_sha256'] == JOB,
             'Canonical attempt/run/job identity')
        need(n['source_freeze_sha256'] == F6_SHA and n['runtime_accepted'] is True and n['SDK_reaped'] is True,
             'Canonical runtime acceptance and reaped SDK')
        need(n['hardware_approved'] is False and n['terminal_status'] == 'COMPLETE_PRE_CLOSE', 'Canonical terminal state')
        self.documents = {}
        for name in ('process.json', 'terminal.json', 'report.json', 'manipulation.json',
                     'manipulation-scene.json', 'import-static.json', 'motion.ndjson'):
            rel = ATTEMPT+'/retrieved/'+name
            self.read(rel, n['files_sha256'][name])
            if name != 'motion.ndjson':
                self.documents[name] = parse(self.raw[rel])
        validate_runtime(n, self.documents)
        for relative in (URDF, LEDGER, COMPONENTS, NATIVE_SOURCE):
            self.source(relative)
        self.read('docs/design/134-v4-recorded-self-collision-audit.md', PLAN_SHA)

    def read(self, relative, sha256, size=None):
        path = (self.root/relative).resolve()
        need(path.is_relative_to(self.root), 'Input path outside project')
        raw = path.read_bytes()
        need(digest(raw) == sha256 and (size is None or len(raw) == size), 'Input SHA/bytes mismatch: '+relative)
        self.raw[relative] = raw
        self.manifest[relative] = {'sha256': digest(raw), 'bytes': len(raw)}
        return raw

    def source(self, relative):
        if relative not in self.raw:
            item = self.freeze['files'][relative]
            self.read(relative, item['sha256'], item['bytes'])
        return self.raw[relative]


def validate_runtime(native, documents):
    process, terminal, report, task = [documents[n] for n in ('process.json', 'terminal.json', 'report.json', 'manipulation.json')]
    for record in (process, terminal, report):
        need(record['run_id'] == RUN and record['job_sha256'] == JOB, 'Retrieved run/job identity')
    need(process['child_pid'] == native['SDK_pid'] == terminal['pid'] == report['pid'], 'Same actual SDK owner')
    need(process['child_creation_time'] == native['SDK_birth'], 'Same actual SDK birth identity')
    need(process['actual_child_exit_code'] == 0 and process['policy_exit_code'] == 0 and
         process['child_state'] == 'REAPED' and process['terminal'] is True and
         process['job_active_after'] == 0 and process['raw_complete'] is True and
         process['timed_out'] is False and process['errors'] == [], 'Actual SDK exit/reap/raw completeness')
    need(terminal['code'] == 0 and terminal['status'] == 'COMPLETE_PRE_CLOSE', 'Native terminal completion')
    need(report['runtime_accepted'] is True and report['completed_steps'] == ROWS-1 and len(report['frames']) == 931,
         'Original report complete rows/frames/runtime')
    need(task == native['task'] and task['passed'] is True and task['rows'] == ROWS, 'Canonical original task readback')
    checkpoints = task['checkpoints']
    need(len(checkpoints) == 5 and tuple(c['actual_time_s'] for c in checkpoints) == CHECKPOINTS and
         all(c['passed'] is True and c['reasons'] == [] for c in checkpoints), 'Five original actual checkpoints PASS')


def parse_motion(raw, names=NAMES):
    positions = np.empty((ROWS, len(names), 3))
    quaternions = np.empty((ROWS, len(names), 4))
    max_error, count = 0., 0
    name_indices = {n: i for i, n in enumerate(names)}
    for step, line in enumerate(io.BytesIO(raw)):
        need(step < ROWS, 'Extra motion row')
        row = parse(line)
        need(type(row['step']) is int and row['step'] == step, 'Contiguous actual step')
        time_s = step/120
        scalar(row['time_s'], time_s, 'Actual time/dt mismatch')
        clock = row['clock']
        need(type(clock['lab_step']) is int and clock['lab_step'] == step, 'Actual lab clock step')
        scalar(clock['engine_time_s'], time_s, 'Actual engine clock')
        phase, origin = ('hold', 0) if step <= 960 else (('small', 8) if step <= 4680 else ('large', 39))
        need(row['phase'] == phase, 'Actual phase clock')
        scalar(row['stage_time_s'], time_s-origin, 'Actual stage clock')
        poses = row['body_poses']
        need(len(poses) == len(names), 'Actual body count')
        seen = set()
        for pose in poses:
            name = pose['name']
            need(name in name_indices and name not in seen, 'Duplicate/unexpected actual body name')
            seen.add(name)
            index = name_indices[name]
            positions[step, index] = numeric(pose['position'], (3,), 'position')
            q = numeric(pose['orientation_wxyz'], (4,), 'quaternion')
            error = abs(float(np.linalg.norm(q))-1)
            need(error <= 1e-5, 'Actual quaternion is not near unit')
            max_error = max(max_error, error)
            quaternions[step, index] = q
        need(seen == set(names), 'Missing actual body')
        count = step+1
    need(count == ROWS, 'Missing final motion row')
    return positions, quaternions, {'rows': count, 'first_step': 0, 'last_step': count-1,
            'first_time_s': 0, 'last_time_s': 93, 'dt_s': 1/120,
            'max_original_quaternion_norm_error': max_error, 'quaternion_norm_limit': 1e-5,
            'normalization': 'CALCULATION_ONLY_ORIGINAL_WXYZ_RETAINED'}


@dataclass
class Envelope:
    shape: geo.Hull
    meta: dict


def build_envelopes(producer, static=None, scene=None, components=None):
    static = producer.documents['import-static.json'] if static is None else static
    scene = producer.documents['manipulation-scene.json'] if scene is None else scene
    components = parse(producer.source(COMPONENTS)) if components is None else components
    need(static['units'] == {'meters': 1., 'kilograms': 1., 'up': 'Z'}, 'Actual SI units')
    bodies = static['bodies']
    need(len(bodies) == 11 and {b['name'] for b in bodies} == set(NAMES), 'Eleven unique rigid body names')
    body_paths = {b['name']: b['path'] for b in bodies}
    need(len(set(body_paths.values())) == 11, 'Unique rigid body paths')
    old = static['colliders']
    need(len(old) == 11 and {x['owner'] for x in old} == set(NAMES), 'Eleven original collider prims')
    need(all(x['enabled'] is True and x['approximation'] == 'convexHull' and
             x['path'] == body_paths[x['owner']]+'/'+x['owner'] for x in old), 'Original collider owner/path/approximation')
    overrides = scene['collision_approximation']
    kg1_path = body_paths['KG1']+'/KG1'
    need(len(overrides) == 1 and overrides[0] == {'path': kg1_path, 'before': 'convexHull',
         'after': 'convexDecomposition', 'cooked_shape_validated': False}, 'Actual KG1 after override, cooked UNKNOWN')
    overlay = scene['jaw_component_overlay']['after_reset']
    need(overlay['count'] == 12 and overlay['old_whole_colliders_disabled'] is True and
         overlay['same_rigid_body_mass_inertia'] is True, 'Actual post-reset overlay policy')
    active = overlay['active_components']
    need(len(active) == 12 and len({x['path'] for x in active}) == 12, 'Twelve unique active jaw children')
    need(components['unit'] == 133 and components['frame'] == 'OWNING_JAW_LINK_FRAME' and
         components['mass_inertia_policy'] == 'ORIGINAL_RIGID_BODY_UNCHANGED' and
         set(components['jaws']) == {'KG1_A', 'KG1_B'}, 'Pinned original jaw frame')
    xml = ET.fromstring(producer.source(URDF))
    ledger = parse(producer.source(LEDGER))
    links = {x.attrib['name']: x for x in xml.findall('link') if x.find('collision') is not None}
    need(set(links) == set(NAMES), 'URDF collision owner set')
    envelopes, expected_children = [], set()
    for name in NAMES:
        collisions = links[name].findall('collision')
        need(len(collisions) == 1, 'One original collision mesh per body')
        collision = collisions[0]
        mesh = collision.find('geometry/mesh')
        need(mesh is not None, 'Original source collision mesh')
        source = (pathlib.PurePosixPath(URDF).parent/mesh.attrib['filename']).as_posix()
        raw = producer.source(source)
        scale = numeric([float(v) for v in mesh.attrib.get('scale', '1 1 1').split()], (3,), 'URDF scale')
        need(np.array_equal(scale, [1, 1, 1]), 'Original SI mesh scale exactly once')
        origin = collision.find('origin')
        xyz = np.zeros(3) if origin is None else numeric([float(v) for v in origin.attrib.get('xyz', '0 0 0').split()], (3,), 'collision xyz')
        rpy = np.zeros(3) if origin is None else numeric([float(v) for v in origin.attrib.get('rpy', '0 0 0').split()], (3,), 'collision rpy')
        frame = {'scale': scale.tolist(), 'collision_origin_xyz_m': xyz.tolist(), 'collision_origin_rpy_rad': rpy.tolist(),
                 'application': 'ONCE_BEFORE_ACTUAL_BODY_POSE'}
        source_mesh = trimesh.load(io.BytesIO(raw), file_type='stl', force='mesh', process=False)
        source_vertices = np.asarray(source_mesh.vertices, dtype=float)
        entries = [e for e in ledger['geometry_components'] if e['link'] == name and e['collision_included']]
        need(bool(entries), 'Ledger source SI provenance')
        ledger_bounds = np.asarray([e['bounds_m'] for e in entries], dtype=float)
        bounds = np.array([ledger_bounds[:, 0].min(axis=0), ledger_bounds[:, 1].max(axis=0)])
        need(np.max(np.abs(np.array([source_vertices.min(axis=0), source_vertices.max(axis=0)])-bounds)) < 2e-7,
             'SI source mesh bounds agree with original ledger: '+name)
        if name not in ('KG1_A', 'KG1_B'):
            shape = geo.hull((source_vertices*scale) @ geo.rpy_rotation(rpy).T+xyz)
            approximation = 'convexDecomposition' if name == 'KG1' else 'convexHull'
            envelopes.append(Envelope(shape, {'id': name, 'owner': name, 'owner_path': body_paths[name],
                 'authored_prim_path': body_paths[name]+'/'+name, 'source': source, 'frame': frame,
                 'source_representation': 'FULL_SOURCE_CONVEX_OUTER_ENVELOPE',
                 'final_authored_approximation': approximation, 'backend_cooked_shape_count': 'UNKNOWN',
                 'cooked_shape_validated': False,
                 'approximation_evidence': 'import-static.json + manipulation-scene.json.collision_approximation',
                 'contact_rest_offsets_scope': 'NOT_INCLUDED_IN_SOURCE_GEOMETRY'}))
            continue
        data = components['jaws'][name]
        need(scene['jaw_paths'][name] == body_paths[name] and data['source'] == source and
             data['source_sha256'] == digest(raw) and data['scale'] == [1, 1, 1] and
             data['collision_origin_xyz_m'] == xyz.tolist() and data['collision_origin_rpy_rad'] == rpy.tolist() and
             data['component_count'] == 6 and len(data['components']) == 6, 'Original jaw source/SI/origin binding')
        need({p['index'] for p in data['components']} == set(range(6)), 'Jaw component unique index set')
        for part in sorted(data['components'], key=lambda p: p['index']):
            child = body_paths[name]+'/ExplicitJawColliders133/component_%02d'%part['index']
            expected_children.add(child)
            readbacks = [x for x in active if x['path'] == child]
            need(len(readbacks) == 1, 'Expected actual child path')
            readback = readbacks[0]
            vertices = numeric(part['vertices_m'], (len(part['vertices_m']), 3), 'component vertices')
            triangles = np.asarray(part['triangle_indices'])
            need(triangles.ndim == 2 and triangles.shape[1] == 3 and np.issubdtype(triangles.dtype, np.integer)
                 and triangles.min() >= 0 and triangles.max() < len(vertices), 'Original component topology')
            need(readback['owner_path'] == body_paths[name] and readback['vertices'] == len(vertices) == part['original_vertices']
                 and readback['faces'] == len(triangles) == part['original_triangles'], 'Actual component owner/vertices/faces')
            need(np.max(np.abs(np.array([vertices.min(axis=0), vertices.max(axis=0)])-part['original_bounds_m'])) < 1e-12,
                 'Component bounds source readback')
            offsets = readback['offsets']
            scalar(offsets['contact_offset_m'], .0005, 'Actual child contact offset', 1e-9)
            scalar(offsets['rest_offset_m'], 0, 'Actual child rest offset', 1e-12)
            shape = geo.hull(vertices)  # Fixed component data are already in the owning link frame.
            envelopes.append(Envelope(shape, {'id': name+':%02d'%part['index'], 'owner': name,
                 'owner_path': body_paths[name], 'authored_prim_path': child, 'source': COMPONENTS,
                 'component_index': part['index'], 'source_mesh': source, 'frame': frame,
                 'source_representation': 'FIXED_COMPONENT_SOURCE_CONVEX_ENVELOPE',
                 'final_authored_approximation': 'convexHull', 'backend_cooked_shape_count': 'UNKNOWN',
                 'cooked_shape_validated': False, 'actual_readback': readback,
                 'approximation_evidence': 'F6 native.py _audit_components133 validates convexHull before emitting readback',
                 'contact_rest_offsets_scope': 'RECORDED_NOT_INCLUDED_IN_SOURCE_GEOMETRY'}))
    need(expected_children == {x['path'] for x in active}, 'No extra/missing actual jaw child')
    need(len(envelopes) == 21, 'Twenty-one source envelopes/authored prims')
    adjacency = []
    path_names = {path: name for name, path in body_paths.items()}
    for joint in static['joints']:
        if joint['body0'] in path_names and joint['body1'] in path_names:
            adjacency.append({'name': joint['name'], 'body0': joint['body0'], 'body1': joint['body1'],
                              'owners': [path_names[joint['body0']], path_names[joint['body1']]]})
    need(len(adjacency) == 10, 'Ten actual interbody direct joints')
    return envelopes, adjacency


def pair_registry(envelopes, adjacency):
    inter, same = [], []
    for a, b in itertools.combinations(range(len(envelopes)), 2):
        ma, mb = envelopes[a].meta, envelopes[b].meta
        owners = sorted([ma['owner'], mb['owner']])
        record = {'id': ma['id']+'|'+mb['id'], 'indices': [a, b], 'envelopes': [ma['id'], mb['id']],
                  'owners': owners, 'body_pair': '|'.join(owners),
                  'direct_joints': [j for j in adjacency if sorted(j['owners']) == owners],
                  'automatic_geometry_exclusion': False,
                  'known_mount_or_gear_unknown': 'Link6' in owners and any(n.startswith('KG1') for n in owners)
                         or any(n in ('KG1_A', 'KG1_B') for n in owners) and 'KG1_R' in owners}
        (same if ma['owner'] == mb['owner'] else inter).append(record)
    need(len(inter) == 180 and len(same) == 30 and len({p['body_pair'] for p in inter}) == 55,
         'Exact source envelope pair accounting')
    return {'interbody': inter, 'same_owner_internal': same, 'body_pair_count': 55}


def intervals(mask):
    indices = np.flatnonzero(mask)
    if not len(indices):
        return []
    groups = np.split(indices, np.flatnonzero(np.diff(indices) != 1)+1)
    return [{'first_step': int(g[0]), 'last_step': int(g[-1]), 'first_time_s': int(g[0])/120,
             'last_time_s': int(g[-1])/120, 'rows': len(g)} for g in groups]


def analyze(envelopes, registry, positions, quaternions):
    need(len(positions) == ROWS and len(quaternions) == ROWS, 'Full recorded-row analysis only')
    rotation = geo.rotations(quaternions)
    name_indices = {n: i for i, n in enumerate(NAMES)}
    boxes = [geo.world_boxes(e.shape, rotation[:, name_indices[e.meta['owner']]], positions[:, name_indices[e.meta['owner']]])
             for e in envelopes]
    summaries, witnesses = [], []
    for pair in registry['interbody']:
        a, b = pair['indices']
        axis_gaps = geo.box_axis_gaps(*boxes[a], *boxes[b])
        gap = axis_gaps.max(axis=1)
        need(np.isfinite(axis_gaps).all(), 'Finite full-row conservative broadphase')
        candidates = gap <= geo.TOLERANCE_M
        minimum = int(gap.argmin())
        summary = {**pair, 'rows_checked': ROWS, 'aabb_separated_rows': int((~candidates).sum()),
                   'candidate_rows': int(candidates.sum()), 'candidate_intervals': intervals(candidates),
                   'minimum_aabb_axis_separation_m': float(gap[minimum]), 'minimum_step': minimum,
                   'minimum_time_s': minimum/120, 'axis_gaps_at_minimum_m': axis_gaps[minimum].tolist(),
                   'minimum_per_axis_gap_m': axis_gaps.min(axis=0).tolist(), 'narrowphase_samples': []}
        if candidates.any():
            selections = {t*120: ['ACTUAL_CHECKPOINT_'+str(t)+'s'] for t in CHECKPOINTS}
            selections.setdefault(minimum, []).append('MINIMUM_AABB_AXIS_SEPARATION')
            for step, reasons in sorted(selections.items()):
                world = []
                poses = []
                for index in (a, b):
                    envelope = envelopes[index]
                    body = name_indices[envelope.meta['owner']]
                    world.append(geo.transformed(envelope.shape, rotation[step, body], positions[step, body]))
                    poses.append({'owner': envelope.meta['owner'], 'position_m': positions[step, body].tolist(),
                                  'original_orientation_wxyz': quaternions[step, body].tolist()})
                result = geo.classify(*world)
                witness = {'pair_id': pair['id'], 'step': step, 'time_s': step/120, 'selection_reasons': reasons,
                           'aabb_candidate': bool(candidates[step]), 'poses': poses, **result}
                witnesses.append(witness)
                summary['narrowphase_samples'].append({'step': step, 'category': result['category']})
            checked_candidates = {x['step'] for x in summary['narrowphase_samples'] if candidates[x['step']]}
        else:
            checked_candidates = set()
        summary['unchecked_candidate_rows'] = summary['candidate_rows']-len(checked_candidates)
        categories = [x['category'] for x in summary['narrowphase_samples']]
        summary['category'] = (geo.OVERLAP if geo.OVERLAP in categories else
             (geo.UNKNOWN if summary['unchecked_candidate_rows'] or geo.UNKNOWN in categories else geo.SEPARATION))
        summaries.append(summary)
    return summaries, witnesses


def dump(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def admit_output(root, output):
    """The lexical outputs/134 namespace is authority; reparse targets never are."""
    root = pathlib.Path(root).resolve()
    allowed = root/OUTPUT_ROOT
    requested = pathlib.Path(output)
    destination = pathlib.Path(os.path.abspath(requested if requested.is_absolute() else root/requested))
    need(destination.is_relative_to(allowed) and destination != allowed,
         'Fresh output must be below the 134 output root')
    current = root
    for part in destination.relative_to(root).parts:
        current = current/part
        if not os.path.lexists(current):
            break  # A child cannot exist under an absent parent; fresh creation follows below.
        attributes = current.lstat()
        need(not current.is_symlink() and
             not getattr(attributes, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
             'Reparse or symbolic-link output ancestor is forbidden')
    need(destination.resolve() == destination, 'Output resolution must preserve the fixed namespace')
    need(not destination.exists(), 'Exclusive output directory already exists')
    return destination


def run(root, output):
    root = pathlib.Path(root).resolve()
    destination = admit_output(root, output)
    own = pathlib.Path(__file__).resolve().parent
    source_bytes = {name: (own/name).read_bytes() for name in ('audit.py', 'geometry.py', 'test_audit.py', 'test_geometry.py')}
    producer = Producer(root)
    envelopes, adjacency = build_envelopes(producer)
    registry = pair_registry(envelopes, adjacency)
    positions, quaternions, motion = parse_motion(producer.raw[ATTEMPT+'/retrieved/motion.ndjson'])
    summaries, witnesses = analyze(envelopes, registry, positions, quaternions)
    for envelope in envelopes:
        envelope.meta['hull_vertices'] = len(envelope.shape.vertices)
        envelope.meta['hull_faces'] = len(envelope.shape.equations)
        envelope.meta['local_bounds_m'] = [envelope.shape.vertices.min(axis=0).tolist(), envelope.shape.vertices.max(axis=0).tolist()]
    categories = {c: sum(p['category'] == c for p in summaries) for c in (geo.SEPARATION, geo.OVERLAP, geo.UNKNOWN)}
    sample_categories = {c: sum(w['category'] == c for w in witnesses) for c in (geo.SEPARATION, geo.OVERLAP, geo.UNKNOWN)}
    body_pairs = []
    for body_pair in sorted({p['body_pair'] for p in summaries}):
        children = [p for p in summaries if p['body_pair'] == body_pair]
        body_pairs.append({'body_pair': body_pair, 'source_envelope_pair_count': len(children),
              'source_envelope_overlap_pairs': sum(p['category'] == geo.OVERLAP for p in children),
              'unknown_pairs': sum(p['category'] == geo.UNKNOWN for p in children),
              'unchecked_candidate_pair_rows': sum(p['unchecked_candidate_rows'] for p in children)})
    result = {'unit': 134, 'audit_completed': True, 'source_envelope_collision_free': categories[geo.SEPARATION] == 180,
         'collision_free_status': 'CERTIFIED_RECORDED_SOURCE_ENVELOPES' if categories[geo.SEPARATION] == 180 else 'NOT_CERTIFIED',
         'continuous_collision_checked': False, 'physical_safety_certified': False, 'hardware_approved': False,
         'run_id': RUN, 'job_sha256': JOB, 'original_runtime_accepted': True,
         'source_envelope_count': 21, 'authored_collider_prim_count': 21, 'backend_cooked_shape_count': 'UNKNOWN',
         'backend_cooked_shape_pair_count': 'UNKNOWN', 'rigid_body_count': 11, 'interbody_source_envelope_pairs': 180,
         'same_owner_internal_source_envelope_pairs': 30, 'body_pair_count': 55,
         'tolerance_m': geo.TOLERANCE_M, 'roundoff_guard_formula': '128*float64_epsilon*max(1,absolute_coordinate_scale)',
         'broadphase_box_padding': 'roundoff guard on every world box, not penetration depth',
         'motion': motion, 'pair_categories': categories, 'sample_categories': sample_categories,
         'selected_narrowphase_samples': len(witnesses), 'max_samples_per_candidate_pair': 6,
         'unchecked_candidate_pair_rows': sum(p['unchecked_candidate_rows'] for p in summaries),
         'body_pairs': body_pairs,
         'limitations': ['SOURCE_CONVEX_OUTER_ENVELOPES_ONLY', 'KG1_ACTUAL_CONVEX_DECOMPOSITION_COOKED_UNKNOWN',
           'NO_RAW_SOLID_INTERSECTION_CERTIFICATION', 'CONTACT_REST_OFFSETS_NOT_INCLUDED',
           'UNSAMPLED_BROADPHASE_CANDIDATES_UNKNOWN', 'NO_CONTINUOUS_COLLISION_TEST',
           'NO_BACKEND_CONTACT_OR_HARDWARE_SAFETY_CERTIFICATION'],
         'replay_command': 'python -X utf8 -I -B -u src/simulation/mp18_collision_audit_134/audit.py --output outputs/mp18-collision-audit-134/NEW_EMPTY_RUN',
         'versions': {'numpy': np.__version__, 'scipy': scipy.__version__, 'trimesh': trimesh.__version__}}
    # Recheck every captured input after computation, before exclusive publication.
    for relative, pin in producer.manifest.items():
        need(digest((root/relative).read_bytes()) == pin['sha256'], 'Input changed during audit: '+relative)
    for name, raw in source_bytes.items():
        need((own/name).read_bytes() == raw, 'Audit source changed during computation: '+name)
    source_manifest = {str((own/name).relative_to(root)).replace('\\', '/'): {'sha256': digest(raw),
                       'bytes': len(raw)} for name, raw in source_bytes.items()}
    source_manifest['docs/design/134-v4-recorded-self-collision-audit.md'] = producer.manifest['docs/design/134-v4-recorded-self-collision-audit.md']
    need(admit_output(root, output) == destination, 'Output namespace changed during computation')
    destination.mkdir(parents=True, exist_ok=False)
    dump(destination/'input-manifest.json', producer.manifest)
    dump(destination/'source-manifest.json', source_manifest)
    dump(destination/'envelopes.json', [e.meta for e in envelopes])
    dump(destination/'pair-registry.json', registry)
    dump(destination/'broadphase.json', summaries)
    dump(destination/'witnesses.json', witnesses)
    text = ['# 134 실제 기록 source-envelope 자기충돌 감사', '',
            '감사 실행 완료: true. 전체 기록 source-envelope collision-free: '+str(result['source_envelope_collision_free']).lower()+'.',
            '실제 133/05의 0~93초 11161행, 11몸체, 180 interbody source-envelope pair를 전수 broadphase 처리했다.',
            '검사 source envelope 21개 / authored collider prim 21개 / backend cooked shape 수 UNKNOWN을 구분한다.',
            'KG1 본체의 최종 authored approximation은 convexDecomposition이며 cooked shape는 미검증이다.',
            '다른 비-jaw 8개 및 jaw child 12개의 authored approximation은 convexHull이다.',
            '고정 허용오차 1e-6m에 float64 수치오차 가드를 추가했다. contact/rest offset은 형상에 포함하지 않았다.', '',
            f"쌍 판독: 분리 {categories[geo.SEPARATION]}, 표본 source-envelope 겹침 {categories[geo.OVERLAP]}, UNKNOWN {categories[geo.UNKNOWN]}.",
            f"선정 narrowphase {len(witnesses)}표본. 미판독 broadphase 후보 pair-row {result['unchecked_candidate_pair_rows']}개는 UNKNOWN이다.",
            'AABB의 음의 간격은 침투깊이가 아니다. 표본 겹침은 원고체 교차·물리접촉·안전 인증을 뜻하지 않는다.',
            '관절 인접·장착·기어 쌍도 자동 제외하지 않았다. 같은 rigid owner 내부 30쌍은 별도 등록했다.', '',
            '## 우선 확인할 몸체쌍', '']
    ranked = sorted(body_pairs, key=lambda p: (-p['source_envelope_overlap_pairs'], -p['unchecked_candidate_pair_rows'], p['body_pair']))
    for p in ranked[:12]:
        text.append(f"- {p['body_pair']}: 표본 겹침 source-envelope 쌍 {p['source_envelope_overlap_pairs']}, UNKNOWN 쌍 {p['unknown_pairs']}, 미판독 후보 pair-row {p['unchecked_candidate_pair_rows']}.")
    text += ['', '다음 단계: 겹침 witness를 원 part/component 형상 및 장착 설계와 대조하고, KG1 cooked 표현과 contact offset을 별도 확인한 뒤 새 충돌 표현 수리·시뮬레이션 계획을 검토한다.',
             '시간 표본 사이 연속 충돌과 실물 안전은 미검증이다. 원133 소스·기록·수용 결과는 변경하지 않았다.', '',
             '재실행: `'+result['replay_command']+'`', '']
    with (destination/'audit.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(text))
    # Completion is published last; failed/partial publication cannot leave a completed audit.json.
    dump(destination/'audit.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Fresh child directory below outputs/mp18-collision-audit-134')
    args = parser.parse_args()
    try:
        result = run(pathlib.Path(__file__).resolve().parents[3], args.output)
    except Exception as exc:
        print(json.dumps({'audit_completed': False, 'error': type(exc).__name__+': '+str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({k: result[k] for k in ('audit_completed', 'source_envelope_collision_free', 'pair_categories', 'selected_narrowphase_samples')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
