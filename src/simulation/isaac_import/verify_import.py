"""Compare a real saved-USD observation to the pinned CAD-v2 URDF; no simulator/device I/O."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath
import re
import xml.etree.ElementTree as ET

MANIFEST_SHA = 'd82f530e301a448c58248b5e5cb94580da610c247fddbc7f643b76836b626b4c'
KIN_SHA = 'fe000e47a3885566a9ca808b053f429e13272da97a8dac132cb44b6153eeae50'
ROOT = Path(__file__).resolve().parents[3]
I = [[float(i == j) for j in range(3)] for i in range(3)]


def need(ok, why):
    if not ok:
        raise ValueError(why)


def vector(v, n=3):
    need(isinstance(v, (list, tuple)) and len(v) == n and
         all(type(x) in (int, float) and math.isfinite(x) for x in v), 'Finite vector')
    return list(v)


def matrix(r):
    need(isinstance(r, list) and len(r) == 3, 'Rotation shape')
    r = [vector(row) for row in r]
    gram = mm(r, tr(r))
    det = sum(r[0][i]*(r[1][(i+1)%3]*r[2][(i+2)%3]-r[1][(i+2)%3]*r[2][(i+1)%3]) for i in range(3))
    need(error(gram, I) <= 1e-5 and abs(det-1) <= 1e-5, 'Proper rigid rotation; no scale/shear/reflection')
    return r


def tr(r):
    return list(map(list, zip(*r)))


def mv(r, v):
    return [sum(a*b for a, b in zip(row, v)) for row in r]


def mm(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def error(a, b):
    if isinstance(a[0], (list, tuple)):
        return max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3))
    return max(abs(x-y) for x, y in zip(a, b))


def quat(q):
    w, x, y, z = vector(q, 4)
    need(abs(w*w+x*x+y*y+z*z-1) <= 1e-5, 'Unit quaternion wxyz')
    return matrix([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                   [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                   [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def completion_gate(status, process, job, snapshot, snapshot_sha):
    """Final authority is the observed process plus bound data, not a pre-exit label.

    Isaac6.2 fast shutdown terminates Python in app.close(). Its CLOSING_APP
    progress cannot publish a post-close EXTRACTED label. Retain that raw fact.
    An earlier exception may also exit0 on close, so exit0 alone is insufficient.
    """
    need(type(process['exit_code']) is int and process['exit_code'] == 0, 'Actual import/extract process must exit0')
    need(status['run_id'] == job['run_id'] == process['run_id'] == snapshot['runtime']['run_id'], 'Attempt identity mismatch')
    final_marker = status['status'] == 'EXTRACTED' and status['phase'] == 'APP_CLOSED'
    pre_fast_shutdown = status['status'] == 'BUILDING' and status['phase'] == 'CLOSING_APP'
    need(final_marker or pre_fast_shutdown, 'Incomplete runtime phase; exit0 is not completion')
    need(status['snapshot_sha256'] == snapshot_sha, 'Closing phase must bind actual saved snapshot hash')
    need(status['timeline_stopped_before'] is True and status['timeline_stopped_after'] is True and
         snapshot['timeline_stopped'] is True, 'Stopped timeline must bracket actual observation')
    need(status['runtime'] == snapshot['runtime'] and status['pid'] == snapshot['runtime']['pid'], 'Observed runtime/PID mismatch')
    need(PureWindowsPath(status['usd_path']) == PureWindowsPath(snapshot['usd_path']) and
         status['usd_sha256'] == snapshot['usd_sha256'], 'Closing phase USD identity mismatch')
    return 'POST_CLOSE_MARKER_AND_EXIT0' if final_marker else 'BOUND_PRE_CLOSE_SNAPSHOT_AND_ACTUAL_EXIT0'


def load_reference(root=ROOT):
    root = Path(root).resolve()
    package = root / 'models/robot-arm-urdf-v1'
    need(sha(package/'manifest.json') == MANIFEST_SHA, 'Pinned URDF package manifest')
    manifest = json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    for name, digest in manifest['files'].items():
        path = (package/name).resolve()
        need(path.is_relative_to(package) and sha(path) == digest, 'Source package hash/path drift')
    kin_path = root/'models/armold-mks-concept-v1/kinematics.json'
    need(sha(kin_path) == KIN_SHA, 'Pinned CAD kinematics')
    kin = json.loads(kin_path.read_text(encoding='utf-8'))
    # This module has stdlib-only import and side-effect-free FK/STL helpers.
    helper_path = root/'src/simulation/urdf_draft/verify.py'
    provenance = json.loads((package/'provenance.json').read_text(encoding='utf-8'))
    need(sha(helper_path) == provenance['generator_files_sha256']['verify.py'], 'Approved reference helper source drift')
    spec = importlib.util.spec_from_file_location('_urdf040_reference', helper_path)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    robot = ET.parse(package/'robot_arm.urdf').getroot()
    joints = robot.findall('joint')
    frames = [([0., 0., 0.], I)] + helpers.urdf_fk(joints, [0.]*6)
    for (p, r), k in zip(frames[1:], kin['joints']):
        need(error(p, [x/1000 for x in k['origin_mm']]) < 1e-10 and error(r, k['R_child']) < 1e-10, 'URDF zero differs from pinned CAD display')
    bodies, ref_joints = {}, {}
    for link, (p, r) in zip(robot.findall('link'), frames):
        inertia = link.find('inertial')
        tensor = inertia.find('inertia')
        diag = [float(tensor.get(k)) for k in ('ixx', 'iyy', 'izz')]
        vertices = []
        for mesh in link.findall('visual/geometry/mesh'):
            for triangle in helpers.stl_triangles(package/mesh.get('filename')):
                for v in triangle:
                    vertices.append([a+b for a, b in zip(p, mv(r, v))])
        bodies[link.get('name')] = {'position': p, 'rotation': r,
            'mass': float(inertia.find('mass').get('value')),
            'com': [float(x) for x in inertia.find('origin').get('xyz').split()],
            'tensor': [[diag[i] if i == j else 0. for j in range(3)] for i in range(3)],
            'bounds': {'min': [min(v[k] for v in vertices) for k in range(3)],
                       'max': [max(v[k] for v in vertices) for k in range(3)]}}
    for i, joint in enumerate(joints):
        child, parent = joint.find('child').get('link'), joint.find('parent').get('link')
        axis = [float(x) for x in joint.find('axis').get('xyz').split()]
        ref_joints[joint.get('name')] = {'parent': parent, 'child': child,
            'anchor': bodies[child]['position'], 'axis': mv(bodies[child]['rotation'], axis),
            'limits': [math.degrees(float(joint.find('limit').get(k))) for k in ('lower', 'upper')]}
    cfg = json.loads((package/'assumptions.json').read_text(encoding='utf-8'))
    need(cfg['physical_verified'] is False and cfg['hardware_approved'] is False, 'Physical assumptions remain unapproved')
    return {'bodies': bodies, 'joints': ref_joints, 'manifest_sha256': MANIFEST_SHA}


def compare(snapshot, reference):
    need(type(snapshot['schema_version']) is int and snapshot['schema_version'] == 1 and snapshot['timeline_stopped'] is True, 'Static stopped observation required')
    need(snapshot['observation_kind'] == 'ACTUAL_RELOADED_USD_STATIC' and snapshot['physical_verified'] is False
         and snapshot['hardware_approved'] is False, 'Actual observation with physical approval false required')
    u = snapshot['units']
    # Official USD resolvers: missing MPU=.01, missing kgPU=1. No common fallback.
    need(type(u['meters_per_unit']) in (int, float) and u['meters_per_unit'] == 1, 'Unsupported length unit; resolved MPU must be 1')
    need(type(u['kilograms_per_unit']) in (int, float) and u['kilograms_per_unit'] == 1, 'Unsupported mass unit; resolved kgPU must be 1')
    need(u['up_axis'] == 'Z', 'Unsupported up axis')
    for key, default in (('meters_per_unit', .01), ('kilograms_per_unit', 1.)):
        authored = u[key+'_authored']
        value = u[key+'_authored_value']
        need(type(authored) is bool, 'Unit authored flag')
        need((authored and type(value) in (int, float) and value == u[key]) or
             (not authored and value is None and u[key] == default), 'Authored/resolved unit mismatch')
    need(not snapshot['dependencies']['unresolved'], 'Unresolved USD dependencies')
    root_placement = snapshot['root_placement']
    need(root_placement is not None and root_placement['path'] == snapshot['default_prim'], 'Explicit default-root placement required')
    need(error(vector(root_placement['position']), [0., 0., 0.]) <= 1e-5 and
         error(matrix(root_placement['rotation']), I) <= 1e-5, 'Supported identity root placement required')
    raw_bodies = snapshot['bodies']
    bodies = {b['name']: b for b in raw_bodies}
    need(len(raw_bodies) == len(bodies) == 7 and set(bodies) == set(reference['bodies']), 'Seven unique CAD links required')
    paths = {b['path']: name for name, b in bodies.items()}
    need(len(paths) == 7, 'Unique body paths')
    metrics = {'link_position_m': 0., 'link_rotation': 0., 'visual_bounds_m': 0.,
               'mass_kg': 0., 'com_m': 0., 'inertia_kg_m2': 0., 'anchor_m': 0., 'signed_axis': 0., 'zero_frame': 0.}
    for name, b in bodies.items():
        expected = reference['bodies'][name]
        p, r = vector(b['position']), matrix(b['rotation'])
        need(b['mass_api_applied'] is True and all(b['mass_properties_authored'][key] is True
             for key in ('mass', 'com', 'inertia_diag')), 'Explicit authored assumed mass/COM/inertia required')
        metrics['link_position_m'] = max(metrics['link_position_m'], error(p, expected['position']))
        metrics['link_rotation'] = max(metrics['link_rotation'], error(r, expected['rotation']))
        need(type(b['mass']) in (int, float) and math.isfinite(b['mass']) and b['mass'] > 0, 'Explicit assumed mass required')
        metrics['mass_kg'] = max(metrics['mass_kg'], abs(b['mass']-expected['mass']))
        metrics['com_m'] = max(metrics['com_m'], error(vector(b['com']), expected['com']))
        diag = vector(b['inertia_diag'])
        need(all(x > 0 for x in diag), 'Explicit positive inertia required')
        principal = quat(b['principal_axes_wxyz'])
        actual_tensor = mm(mm(principal, [[diag[i] if i == j else 0. for j in range(3)] for i in range(3)]), tr(principal))
        metrics['inertia_kg_m2'] = max(metrics['inertia_kg_m2'], error(actual_tensor, expected['tensor']))
        bounds = b['visual_bounds']
        need(bounds is not None and b['visual_meshes'], 'Actual visual Mesh points required')
        for end in ('min', 'max'):
            metrics['visual_bounds_m'] = max(metrics['visual_bounds_m'], error(vector(bounds[end]), expected['bounds'][end]))
    need(metrics['link_position_m'] <= 1e-5 and metrics['link_rotation'] <= 1e-5, 'CAD zero link pose mismatch')
    need(metrics['visual_bounds_m'] <= 1e-5, 'CAD zero visual bounds mismatch')
    need(metrics['mass_kg'] <= 1e-6, 'Assumed mass changed during import')
    need(metrics['com_m'] <= 1e-5, 'Assumed COM changed during import')
    need(metrics['inertia_kg_m2'] <= 1e-8, 'Assumed inertia tensor changed during import')
    revolute = [j for j in snapshot['joints'] if j['type'] == 'revolute']
    joints = {j['name']: j for j in revolute}
    need(len(revolute) == len(joints) == 6 and set(joints) == set(reference['joints']), 'Six unique revolute joints required')
    fixed = [j for j in snapshot['joints'] if j['type'] == 'fixed']
    need(all(j['type'] in ('revolute', 'fixed') for j in snapshot['joints']), 'Unexpected additional joint type')
    world_targets = (None, '', root_placement['path'])
    need(root_placement['path'] not in paths, 'Default root is a non-rigid world reference')
    need(len(fixed) == 1 and any((j['body0'] in world_targets and paths.get(j['body1']) == 'Base') or
             (j['body1'] in world_targets and paths.get(j['body0']) == 'Base') for j in fixed), 'Fixed world-to-Base joint required')
    # The fixed joint is a physical constraint too: both authored frames must
    # close at this displayed Base pose. A common change of anchor gauge is OK.
    fixed_frames = []
    for side in (0, 1):
        joint = fixed[0]
        target = joint['body'+str(side)]
        if target in paths:
            body = bodies[paths[target]]
            p, r = body['position'], body['rotation']
        elif target == root_placement['path']:
            p, r = root_placement['position'], root_placement['rotation']
        else:
            need(target in (None, ''), 'Unsupported fixed world reference')
            p, r = [0., 0., 0.], I
        local_p = vector(joint['local_pos'+str(side)])
        local_r = quat(joint['local_rot'+str(side)+'_wxyz'])
        fixed_frames.append(([x+y for x, y in zip(p, mv(r, local_p))], mm(r, local_r)))
    metrics['fixed_anchor_closure_m'] = error(fixed_frames[0][0], fixed_frames[1][0])
    metrics['fixed_zero_frame'] = error(fixed_frames[0][1], fixed_frames[1][1])
    need(metrics['fixed_anchor_closure_m'] <= 1e-5, 'Fixed base anchor closure mismatch')
    need(metrics['fixed_zero_frame'] <= 1e-5, 'Fixed base zero-frame closure mismatch')
    rows = []
    for name, j in joints.items():
        expected = reference['joints'][name]
        need(paths.get(j['body0']) == expected['parent'] and paths.get(j['body1']) == expected['child'], 'Joint parent/child orientation mismatch')
        a, b = bodies[expected['parent']], bodies[expected['child']]
        q0, q1 = quat(j['local_rot0_wxyz']), quat(j['local_rot1_wxyz'])
        frame0, frame1 = mm(a['rotation'], q0), mm(b['rotation'], q1)
        p0 = [x+y for x, y in zip(a['position'], mv(a['rotation'], vector(j['local_pos0'])))]
        p1 = [x+y for x, y in zip(b['position'], mv(b['rotation'], vector(j['local_pos1'])))]
        need(j['axis'] in ('X', 'Y', 'Z'), 'Supported joint axis token')
        axis = mv(frame0, [float(k == 'XYZ'.index(j['axis'])) for k in range(3)])
        metrics['anchor_m'] = max(metrics['anchor_m'], error(p0, expected['anchor']), error(p1, expected['anchor']))
        metrics['signed_axis'] = max(metrics['signed_axis'], error(axis, expected['axis']))
        metrics['zero_frame'] = max(metrics['zero_frame'], error(frame0, frame1))
        lower, upper = vector([j['lower_limit'], j['upper_limit']], 2)
        need(error([lower, upper], expected['limits']) <= 1e-4, 'Assumed delta limits changed')
        rows.append({'joint': name, 'anchor_m': p0, 'signed_axis_world': axis})
    need(metrics['anchor_m'] <= 1e-5, 'CAD joint anchor mismatch')
    need(metrics['zero_frame'] <= 1e-5, 'Joint zero-frame closure mismatch')
    need(metrics['signed_axis'] <= 1e-5, 'CAD signed joint axis mismatch')
    return {'status': 'IMPORTED_USD_STATIC_FRAME_ALIGNMENT', 'links': 7, 'revolute_joints': 6,
        'metrics_max': metrics, 'joint_observations': rows, 'mass_inertia': 'SIMULATION_ASSUMPTION', 'assumed_values_preserved': True,
        'physical_verified': False, 'hardware_approved': False, 'timeline_play': 'NOT_RUN',
        'articulation_motion': 'NOT_RUN', 'rl_training': 'NOT_RUN', 'ring_geometry': 'DEFERRED'}


def verify_run(run_copy, remote_run_dir, root=ROOT):
    run_copy = Path(run_copy).resolve()
    job = json.loads((run_copy/'job.json').read_text(encoding='utf-8'))
    status = json.loads((run_copy/'status.json').read_text(encoding='utf-8'))
    process = json.loads((run_copy/'exit.json').read_text(encoding='utf-8-sig'))
    snapshot = json.loads((run_copy/'snapshot.json').read_text(encoding='utf-8'))
    completion = completion_gate(status, process, job, snapshot, sha(run_copy/'snapshot.json'))
    need(type(job['run_id']) is str and re.fullmatch(r'[a-f0-9]{32}', job['run_id']), 'Generated attempt ID required')
    prepared_path = Path(root)/'outputs/isaac-import-v1/runs'/job['run_id']/'prepared.json'
    prepared = json.loads(prepared_path.read_text(encoding='utf-8'))
    need(sha(run_copy/'job.json') == prepared['job_sha256'], 'Executed job differs from original preparation')
    need(prepared['run_id'] == job['run_id'] and PureWindowsPath(prepared['remote_run_dir']) == PureWindowsPath(remote_run_dir), 'Prepared attempt path mismatch')
    need(prepared['config'] == json.loads((Path(__file__).parent/'remote_config.json').read_text(encoding='utf-8')), 'Approved runtime configuration drift')
    need(snapshot['runtime']['isaac_version'] == job['expected_isaac_version'], 'Installed runtime identity changed')
    need(snapshot['runtime']['package_manifest_sha256'] == job['package_manifest_sha256'] == MANIFEST_SHA,
         'Runtime package identity differs from actual job/input')
    need(snapshot['runtime']['scripts_sha256'] == job['scripts_sha256'], 'Runtime script identity differs from actual job/source')
    installed = json.loads((Path(root)/'.dev/isaac-import-evidence/preflight/api-hashes.json').read_text(encoding='utf-8-sig'))
    for key, suffix in {
        'importer_config_sha256': '/pip_prebundle/isaacsim/asset/importer/urdf/impl/config.py',
        'importer_converter_sha256': '/pip_prebundle/isaacsim/asset/importer/urdf/impl/converter.py',
        'importer_extension_sha256': '/isaacsim.asset.importer.urdf/config/extension.toml',
    }.items():
        matches = [x['sha256'] for x in installed if x['path'].replace('\\', '/').endswith(suffix)]
        need(len(matches) == 1 and snapshot['runtime'][key] == matches[0], 'Runtime importer identity differs from installed preflight')
    settings = json.loads((run_copy/'import-settings.json').read_text(encoding='utf-8'))
    need(snapshot['import_settings'] == settings, 'Observed import settings differ from recorded invocation')
    relative = PureWindowsPath(snapshot['usd_path']).relative_to(PureWindowsPath(remote_run_dir))
    need('..' not in relative.parts and relative.parts[0] == 'usd', 'USD outside owned run output')
    usd = run_copy.joinpath(*relative.parts).resolve()
    need(usd.is_relative_to(run_copy) and usd.is_file() and sha(usd) == snapshot['usd_sha256'], 'Downloaded actual USD hash/path mismatch')
    need(job['package_manifest_sha256'] == MANIFEST_SHA, 'Imported package identity mismatch')
    transferred = (run_copy/job['package_rel']).resolve()
    need(transferred.is_relative_to(run_copy) and sha(transferred/'manifest.json') == MANIFEST_SHA, 'Transferred input manifest drift')
    for name, digest in json.loads((transferred/'manifest.json').read_text(encoding='utf-8'))['files'].items():
        path = (transferred/name).resolve()
        need(path.is_relative_to(transferred) and sha(path) == digest, 'Transferred input payload drift after import')
    for name, digest in job['scripts_sha256'].items():
        need(name in ('remote_import.py', 'extract_usd.py') and sha(run_copy/name) == digest and
             sha(Path(__file__).parent/name) == digest, 'Executed remote script differs from recorded/current source')
    need(sha(run_copy/'supervise.py') == job['supervisor_sha256'] == sha(Path(__file__).parent/'supervise.py'), 'Executed supervisor source drift')
    result = compare(snapshot, load_reference(root))
    return {**result, 'run_id': job['run_id'], 'remote_usd_path': snapshot['usd_path'],
            'local_usd_path': str(usd), 'usd_sha256': snapshot['usd_sha256'],
            'completion_evidence': completion, 'raw_runtime_status': status['status'], 'raw_runtime_phase': status['phase']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-copy', required=True, type=Path)
    parser.add_argument('--remote-run-dir', required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    current = ROOT/'.dev/isaac-import-evidence/current.json'
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text(json.dumps({'status': 'VALIDATING', 'hardware_approved': False})+'\n', encoding='utf-8')
    try:
        result = verify_run(args.run_copy, args.remote_run_dir)
        if args.report:
            args.report.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        current.write_text(json.dumps({**result, 'run_copy': str(args.run_copy.resolve())}, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(json.dumps(result, allow_nan=False))
    except Exception as exc:
        failure = {'status': 'FAILED', 'reason': f'{type(exc).__name__}: {exc}', 'hardware_approved': False}
        current.write_text(json.dumps(failure)+'\n', encoding='utf-8')
        if args.report:
            args.report.write_text(json.dumps(failure)+'\n', encoding='utf-8')
        raise
