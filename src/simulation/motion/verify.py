"""042 offline consumer of bound PhysX drive telemetry; never starts a simulator."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath
import re
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
USD_SHA = '117d94292c75e89b201e12606eafbcf24065c537c6f8308647562f9a0679f4db'
REFERENCE_VERIFIER_SHA = 'bcf682c5a3a14d04b91458845331b92f9794e231ac0c57b7c5a475677a283eeb'
JOINTS = [f'J{i}' for i in range(1, 7)]
LINKS = ['Base'] + [f'Link{i}' for i in range(1, 7)]
IDENTITY = [[float(i == j) for j in range(3)] for i in range(3)]
SOURCES = {
    'runtime.py': 'src/simulation/motion/runtime.py',
    'core.py': 'src/simulation/motion/core.py',
    'program.json': 'src/simulation/motion/program.json',
    'config.json': 'src/simulation/motion/remote_config.json',
    'extract_usd.py': 'src/simulation/isaac_import/extract_usd.py',
    'frames.py': 'src/joint_frames/frames.py',
    'kinematics.json': 'models/armold-mks-concept-v1/kinematics.json',
    'input.usda': 'outputs/isaac-import-v1/asset/robot-arm-v2.usda',
    'source-assumptions.json': 'outputs/isaac-import-v1/asset/source-assumptions.json',
    'reference.urdf': 'models/robot-arm-urdf-v1/robot_arm.urdf',
}
DT = 1.0 / 120.0
CALLBACK_DT = struct.unpack('f', struct.pack('f', DT))[0]
CALLBACK_CLOCK_TOL = 1e-9
POSITION_TOL = .001
ROTATION_TOL = .001
CLOCK_TOL = 1e-6
ANGLE_TOL = math.radians(.5)
SPEED_TOL = math.radians(1)


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse(raw):
    """Reject duplicate keys and all non-finite JSON constants at the boundary."""
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate JSON key: ' + key)
            value[key] = item
        return value

    def invalid(value):
        raise ValueError('Non-finite JSON constant: ' + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def read_json(path):
    return parse(Path(path).read_text(encoding='utf-8-sig'))


def number(value, label):
    need(type(value) in (int, float) and math.isfinite(value), 'Finite number: ' + label)
    return float(value)


def integer(value, label):
    need(type(value) is int and value >= 0, 'Nonnegative integer: ' + label)
    return value


def vector(value, length=3, label='vector'):
    need(type(value) is list and len(value) == length, 'Vector shape: ' + label)
    return [number(x, label) for x in value]


def transpose(a):
    return [list(row) for row in zip(*a)]


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(a, b):
    return [sum(x*y for x, y in zip(row, b)) for row in a]


def add(a, b):
    return [x+y for x, y in zip(a, b)]


def error(a, b):
    if isinstance(a[0], (list, tuple)):
        return max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3))
    return max(abs(x-y) for x, y in zip(a, b))


def matrix(value, label='matrix', rigid=True):
    need(type(value) is list and len(value) == 3, 'Matrix shape: ' + label)
    result = [vector(row, label=label) for row in value]
    if rigid:
        a, b, c = result
        determinant = (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0])
                       + a[2]*(b[0]*c[1]-b[1]*c[0]))
        need(error(mm(result, transpose(result)), IDENTITY) <= 1e-5
             and abs(determinant-1) <= 1e-5, 'Proper rotation: ' + label)
    return result


def quaternion(value):
    w, x, y, z = vector(value, 4, 'quaternion wxyz')
    norm = math.sqrt(w*w+x*x+y*y+z*z)
    need(abs(norm-1) <= 1e-5, 'Unit quaternion wxyz')
    w, x, y, z = [q/norm for q in (w, x, y, z)]
    return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def context(root=ROOT):
    root = Path(root).resolve()
    reference_path = root/'src/simulation/isaac_import/verify_import.py'
    need(sha(reference_path) == REFERENCE_VERIFIER_SHA, 'Pinned 041 reference consumer source drift')
    reference_module = import_file('_motion041_reference', reference_path)
    reference = reference_module.load_reference(root)
    frames = import_file('_motion021_frames', root/SOURCES['frames.py'])
    core = import_file('_motion042_core', root/SOURCES['core.py'])
    layout = frames.decode((root/SOURCES['kinematics.json']).read_bytes())
    program = core.load_program(root/SOURCES['program.json'])
    return reference_module, reference, frames, layout, core, program


def check_identity_pose(value, path):
    need(value['path'] == path, 'Frame path: ' + path)
    need(error(vector(value['position']), [0., 0., 0.]) <= 1e-8
         and error(matrix(value['rotation']), IDENTITY) <= 1e-8, 'Identity root placement: ' + path)


def validate_static(static, reference_module, reference, core, root=ROOT):
    """Check every source frame and actual post-initialization local mass frame."""
    check_identity_pose(static['root_placement'], '/World')
    check_identity_pose(static['robot_root'], '/World/Robot')
    need(static['default_prim'] == '/World', 'Default prim must be /World')
    need(static['usd_sha256'] == USD_SHA, 'Observed source USD pin')
    # 041's consumer expects its non-rigid asset root to be the default prim.
    # Normalize that root selection only; all measured poses/frames stay intact.
    normalized = copy.deepcopy(static)
    normalized['default_prim'] = static['robot_root']['path']
    normalized['root_placement'] = copy.deepcopy(static['robot_root'])
    source_result = reference_module.compare(normalized, reference)
    config = static['configuration']
    need(config == {'engine': 'physx', 'device': 'cpu', 'gravity': [0., 0., 0.],
                    'frequency_hz': 120., 'self_collisions': False}, 'Actual isolated PhysX configuration')
    need(config['self_collisions'] is False and vector(config['gravity']) == [0., 0., 0.]
         and number(config['frequency_hz'], 'frequency') == 120., 'Strict actual physics configuration types')
    names = static['dof_names']
    need(type(names) is list and len(names) == 6 and all(type(x) is str for x in names)
         and set(names) == set(JOINTS), 'Six unique actual named DOFs')
    bodies = {body['name']: body for body in static['bodies']}
    expected_path = '/World/Robot/Geometry/Base'
    for name in LINKS:
        need(bodies[name]['path'] == expected_path, 'Exact body path: ' + name)
        if name != 'Link6':
            expected_path += '/Link' + str(1 if name == 'Base' else int(name[4:])+1)
    paths = {body['path']: name for name, body in bodies.items()}
    expected_gains = core.gains(static)
    for key in ('kp', 'kd', 'effort', 'i_eff'):
        actual = vector(static['gains'][key], 6, 'gains.'+key)
        expected = expected_gains[key]
        need(all(x > 0 for x in actual) and error(actual, expected) <= 1e-10,
             'Assumed source-derived SI drive settings: ' + key)
    drives = static['actual_drives']
    need(drives['types'] == ['force']*6, 'Actual force drive mode on every DOF')
    for key in ('kp', 'kd', 'effort'):
        actual = vector(drives[key], 6, 'actual_drives.'+key)
        expected = expected_gains[key]
        need(all(x > 0 and abs(x-y) <= 1e-7+1e-5*abs(y) for x, y in zip(actual, expected)),
             'Actual SI drive gains/effort differ from source settings: ' + key)
    masses = static['runtime_masses']
    need(type(masses) is list and len(masses) == 7
         and len({m['name'] for m in masses}) == 7 and {m['name'] for m in masses} == set(LINKS),
         'Seven actual runtime mass/COM/inertia observations')
    maxima = {'mass_kg': 0., 'com_m': 0., 'inertia_kg_m2': 0.}
    for actual in masses:
        source = bodies[actual['name']]
        maxima['mass_kg'] = max(maxima['mass_kg'], abs(number(actual['mass'], 'mass')-source['mass']))
        maxima['com_m'] = max(maxima['com_m'], error(vector(actual['com']), vector(source['com'])))
        # COM/principal orientation is LINK-local, never a world body transform.
        principal = quaternion(actual['principal_axes_wxyz'])
        source_principal = quaternion(source['principal_axes_wxyz'])
        diag = vector(source['inertia_diag'])
        diagonal = [[diag[i] if i == j else 0. for j in range(3)] for i in range(3)]
        expected_tensor = mm(mm(source_principal, diagonal), transpose(source_principal))
        actual_tensor = matrix(actual['inertia_link_about_com'], 'runtime inertia', rigid=False)
        need(error(actual_tensor, transpose(actual_tensor)) <= 1e-7, 'Symmetric runtime inertia')
        maxima['inertia_kg_m2'] = max(maxima['inertia_kg_m2'], error(actual_tensor, expected_tensor))
        # Runtime may choose equivalent eigen-axis signs or degenerate subspaces.
        # Its principal frame must still diagonalize the actual full LINK tensor.
        rotated = mm(mm(transpose(principal), actual_tensor), principal)
        need(max(abs(rotated[i][j]) for i in range(3) for j in range(3) if i != j) <= 1e-7,
             'Runtime principal frame must diagonalize LINK inertia')
        need(min(rotated[i][i] for i in range(3)) > 0, 'Positive runtime principal inertia')
    need(maxima['mass_kg'] <= 1e-5 and maxima['com_m'] <= 1e-5
         and maxima['inertia_kg_m2'] <= 1e-7, 'Runtime assumed mass/COM/inertia differs from source')
    assumptions = read_json(Path(root)/SOURCES['source-assumptions.json'])
    need(assumptions['physical_verified'] is False and assumptions['status'] == 'SIMULATION_ASSUMPTION',
         'Assumed physical properties remain unverified')
    proxies = {entry['link']: entry for entry in assumptions['links']}
    colliders = static['colliders']
    need(type(colliders) is list and len(colliders) == 7 and len({x['path'] for x in colliders}) == 7,
         'Seven unique actual collision frames')
    owners = set()
    for collider in colliders:
        need(collider['body_path'] in paths, 'Collider owner must be an observed LINK')
        name = paths[collider['body_path']]
        need(name not in owners, 'One collision proxy per LINK')
        owners.add(name)
        need(type(collider['path']) is str and collider['path'].startswith(collider['body_path']+'/'),
             'Collider path inside its body')
        need(collider['enabled'] is False and number(collider['size'], 'Cube size') == 1.,
             'Actual unit-cube collision proxy disabled')
        expected = proxies[name]
        need(error(vector(collider['local_position']), vector(expected['com_m'])) <= 1e-5,
             'Collider local position differs from source: ' + name)
        basis = matrix(collider['local_basis'], 'collider basis', rigid=False)
        size = vector(expected['box_size_m'])
        expected_basis = [[size[i] if i == j else 0. for j in range(3)] for i in range(3)]
        need(error(basis, expected_basis) <= 1e-5, 'Collider local basis/scale differs from source: ' + name)
    need(owners == set(LINKS), 'Collider frame coverage of every LINK')
    return {'source_frame_result': source_result['status'], 'runtime_mass_metrics': maxima}


def frame(body_pose, joint, side):
    position, rotation = body_pose
    return (add(position, mv(rotation, vector(joint['local_pos'+str(side)]))),
            mm(rotation, quaternion(joint['local_rot'+str(side)+'_wxyz'])))


def compare_samples(static, samples, program, frames, layout, core):
    """Pure numeric checks only; success here does not attest a real Isaac run."""
    need(core.total_time(program) == 56.5 and program['rate_hz'] == 120, 'Frozen finite recipe')
    expected_count = 6781
    names = [part['name'] for part in core.segments(program)]
    bodies = {body['name']: body for body in static['bodies']}
    paths = {body['path']: name for name, body in bodies.items()}
    joints = {joint['name']: joint for joint in static['joints'] if joint['type'] == 'revolute'}
    fixed = [joint for joint in static['joints'] if joint['type'] == 'fixed']
    need(len(fixed) == 1 and len(joints) == 6 and set(joints) == set(JOINTS), 'Actual joint inventory')
    baseline_step = integer(static['baseline_step'], 'baseline step')
    baseline_time = number(static['baseline_time_s'], 'baseline time')
    need(baseline_time >= 0, 'Nonnegative actual baseline time')
    checkpoints, seen, previous = [], 0, None
    maxima = {'link_position_m': 0., 'link_rotation': 0., 'anchor_m': 0.,
              'joint_rotation': 0., 'signed_axis': 0., 'clock_increment_s': 0.,
              'engine_accum_error_s': 0., 'callback_accum_error_s': 0.,
              'callback_increment_error_s': 0.,
              'endpoint_angle_rad': 0., 'endpoint_speed_rad_s': 0.}
    for index, sample in enumerate(samples):
        need(index < expected_count and type(sample) is dict, 'Extra or malformed telemetry record')
        need(type(sample['index']) is int and sample['index'] == index, 'Contiguous actual sample index')
        schedule = number(sample['schedule_time_s'], 'schedule time')
        need(abs(schedule-index*DT) <= 1e-10, 'Schedule sample time/order')
        expected = core.sample(program, index*DT)
        need(sample['segment'] == expected['segment'] and sample['checkpoint'] == expected['checkpoint'],
             'Missing/wrong recipe checkpoint or segment')
        target = vector(sample['target_q_rad'], 6, 'target q rad')
        target_velocity = vector(sample['target_qd_rad_s'], 6, 'target qd rad/s')
        need(error(target, expected['q_rad']) <= 1e-10
             and error(target_velocity, expected['qd_rad_s']) <= 1e-10, 'Wrong target units/trajectory')
        need(max(abs(v) for v in target_velocity) <= .5, 'Command velocity cap')
        actual_q = vector(sample['q_rad'], 6, 'actual canonical J1..J6 q')
        actual_qd = vector(sample['qd_rad_s'], 6, 'actual canonical J1..J6 qd')
        need(max(abs(q) for q in actual_q) <= math.radians(170)+1e-5, 'Actual q outside assumed limits')
        need(sample['timeline_paused'] is True, 'Paused manual-step owner required')
        clock = sample['clock']
        for key in ('step_before', 'step_after', 'read_step_before', 'read_step_after', 'callback_count'):
            integer(clock[key], key)
        before = number(clock['time_before_s'], 'actual time before')
        after = number(clock['time_after_s'], 'actual time after')
        callback_time = number(clock['callback_time_s'], 'actual callback accumulated dt')
        need(clock['step_after'] == baseline_step+index and clock['callback_count'] == index,
             'Actual step/callback count progression')
        need(clock['read_step_before'] == clock['read_step_after'] == clock['step_after'],
             'State read must remain within one actual physics step')
        # Isaac6.2's engine clock is double while POST_STEP exposes float32 dt.
        # Validate each against its own representation, rather than equating
        # their accumulated values or broadening a shared tolerance.
        engine_error = abs((after-baseline_time)-index*DT)
        callback_error = abs(callback_time-index*CALLBACK_DT)
        maxima['engine_accum_error_s'] = max(maxima['engine_accum_error_s'], engine_error)
        maxima['callback_accum_error_s'] = max(maxima['callback_accum_error_s'], callback_error)
        need(engine_error <= CLOCK_TOL, 'Actual double physics clock progression')
        need(callback_error <= CALLBACK_CLOCK_TOL, 'Actual float32 callback clock progression')
        if index == 0:
            need(clock['step_before'] == baseline_step and abs(before-baseline_time) <= CLOCK_TOL
                 and abs(after-before) <= CLOCK_TOL and callback_time == 0., 'Baseline must precede manual stepping')
        else:
            need(clock['step_before'] == previous['step_after'] and abs(before-previous['time_after_s']) <= CLOCK_TOL,
                 'Missing/stale/repeated physics interval')
            increment_error = abs((after-before)-DT)
            maxima['clock_increment_s'] = max(maxima['clock_increment_s'], increment_error)
            need(clock['step_after']-clock['step_before'] == 1 and increment_error <= CLOCK_TOL,
                 'Exactly one physics step and dt per sample')
            callback_increment_error = abs((callback_time-previous['callback_time_s'])-CALLBACK_DT)
            maxima['callback_increment_error_s'] = max(maxima['callback_increment_error_s'], callback_increment_error)
            need(callback_increment_error <= CALLBACK_CLOCK_TOL, 'Actual float32 callback increment')
        previous = clock
        observations = sample['links']
        need(type(observations) is list and len(observations) == 7
             and len({link['name'] for link in observations}) == 7
             and {link['name'] for link in observations} == set(LINKS), 'Seven actual LINK origin poses')
        poses = {link['name']: (vector(link['position']), quaternion(link['orientation_wxyz'])) for link in observations}
        fk_rows = frames.fk(layout, actual_q)
        fk = {'Base': ([0., 0., 0.], IDENTITY)}
        fk.update({f'Link{i}': (row['origin_m'], row['rotation_world']) for i, row in enumerate(fk_rows, 1)})
        for name in LINKS:
            maxima['link_position_m'] = max(maxima['link_position_m'], error(poses[name][0], fk[name][0]))
            maxima['link_rotation'] = max(maxima['link_rotation'], error(poses[name][1], fk[name][1]))
        need(maxima['link_position_m'] <= POSITION_TOL and maxima['link_rotation'] <= ROTATION_TOL,
             'Actual LINK frame differs from FK(actual q), including fixed Base')
        def body_pose(target):
            if target in paths:
                return poses[paths[target]]
            need(target in (None, '', '/World/Robot', '/World'), 'Unknown joint world/root reference')
            return [0., 0., 0.], IDENTITY
        for joint in [fixed[0], *[joints[name] for name in JOINTS]]:
            a = frame(body_pose(joint['body0']), joint, 0)
            b = frame(body_pose(joint['body1']), joint, 1)
            maxima['anchor_m'] = max(maxima['anchor_m'], error(a[0], b[0]))
            if joint['type'] == 'fixed':
                rotated = a[1]
            else:
                j = JOINTS.index(joint['name'])
                axis = [float(joint['axis'] == token) for token in 'XYZ']
                rotated = mm(a[1], frames.rotation(axis, actual_q[j]))
                expected_axis = fk_rows[j]['axis_world']
                maxima['anchor_m'] = max(maxima['anchor_m'], error(a[0], fk_rows[j]['origin_m']),
                                         error(b[0], fk_rows[j]['origin_m']))
                maxima['signed_axis'] = max(maxima['signed_axis'], error(mv(a[1], axis), expected_axis),
                                            error(mv(b[1], axis), expected_axis))
            maxima['joint_rotation'] = max(maxima['joint_rotation'], error(rotated, b[1]))
        need(maxima['anchor_m'] <= POSITION_TOL and maxima['joint_rotation'] <= ROTATION_TOL
             and maxima['signed_axis'] <= ROTATION_TOL, 'Fixed/revolute frame closure or signed axis mismatch')
        if sample['checkpoint'] is not None:
            checkpoints.append(sample['checkpoint'])
            angle_error = error(actual_q, target)
            speed = max(abs(v) for v in actual_qd)
            maxima['endpoint_angle_rad'] = max(maxima['endpoint_angle_rad'], angle_error)
            maxima['endpoint_speed_rad_s'] = max(maxima['endpoint_speed_rad_s'], speed)
            need(angle_error <= ANGLE_TOL and speed <= SPEED_TOL, 'Endpoint tracking/speed, independent of FK')
            if '_positive' in sample['checkpoint'] and '_after_' not in sample['checkpoint']:
                need(actual_q[JOINTS.index(sample['checkpoint'].split('_')[0])] > 0, 'Positive individual response')
            if sample['checkpoint'].endswith('_negative') and '_after_' not in sample['checkpoint']:
                need(actual_q[JOINTS.index(sample['checkpoint'].split('_')[0])] < 0, 'Negative individual response')
        seen += 1
    need(seen == expected_count and checkpoints == names, 'All samples and all 28 ordered checkpoints required')
    need(expected['checkpoint'] == 'final_zero' and max(abs(q) for q in actual_q) <= ANGLE_TOL
         and max(abs(v) for v in actual_qd) <= SPEED_TOL, 'Actual final zero/low speed before STOP')
    return {'status': 'HOST_DATA_CHECKS_ONLY', 'sample_count': seen, 'physics_steps': seen-1,
            'checkpoints': checkpoints, 'metrics_max': maxima,
            'frame_coverage': ['world', 'robot_root', '7_LINK', 'fixed_both_sides', '6_revolute_both_sides',
                               '6_signed_axes', '7_local_COM', '7_principal_inertia', '7_disabled_colliders']}


def completion_gate(summary, state, process, actual_summary_sha):
    """Accept a bound fast-shutdown marker only with observed native exit0.

    This gate does not replace source/input/output/PID ownership checks in
    verify_run; it separates the two supported application completion paths.
    """
    need(summary['status'] == 'DATA_CAPTURED' and summary['kind'] == 'ACTUAL_PHYSX_DRIVE_TELEMETRY',
         'Completed actual telemetry summary required')
    closed = state['status'] == 'CLOSED' and state['phase'] == 'APP_CLOSED'
    pre_close = state['status'] == 'DATA_CAPTURED' and state['phase'] == 'CLOSING_APP'
    need(closed or pre_close, 'Incomplete/FAILED runtime completion phase')
    if pre_close:
        need(summary['runtime'].get('close_protocol') == 'OFFICIAL_FAST_SHUTDOWN_EXPLICIT_EXIT',
             'Bound official explicit-exit fast-shutdown protocol required')
    need(type(process['exit_code']) is int and process['exit_code'] == 0,
         'Actual process exit0 required; captured data alone is insufficient')
    need(summary['run_id'] == state['run_id'] == process['run_id'] == summary['runtime']['run_id'],
         'Completion attempt identity mismatch')
    pid = integer(summary['pid'], 'completion worker PID')
    need(pid > 0 and summary['runtime']['pid'] == state['pid'] == process['pid'] == pid,
         'Completion actual worker PID mismatch')
    need(state['runtime'] == summary['runtime'], 'Completion runtime identity mismatch')
    need(state['summary_sha256'] == actual_summary_sha, 'Completion must bind actual summary bytes')
    need(summary['final_before_stop'] is True, 'Final observation must precede STOP/reset')
    started = number(state['started_unix'], 'worker start time')
    captured = number(summary['finished_unix'], 'capture time')
    finished = number(process['finished_unix'], 'process exit time')
    need(started <= captured <= finished and finished-started <= 600, 'Finite actual worker chronology')
    if closed:
        closed_time = number(state['closed_unix'], 'closed time')
        need(captured <= closed_time <= finished, 'Post-close chronology')
    return 'POST_CLOSE_MARKER_AND_ACTUAL_EXIT0' if closed else 'BOUND_PRE_CLOSE_SUMMARY_AND_ACTUAL_EXIT0'


def verify_run(run_dir, root=ROOT):
    """Bind current sources, original preparation, actual process and raw data."""
    root, run = Path(root).resolve(), Path(run_dir).resolve()
    job = read_json(run/'job.json')
    run_id = job['run_id']
    need(type(run_id) is str and re.fullmatch('[0-9a-f]{32}', run_id), 'GUID attempt identity')
    prepared_dir = root/'outputs/isaac-motion-v1/runs'/run_id
    prepared = read_json(prepared_dir/'prepared.json')
    need(prepared['run_id'] == run_id and prepared['job_sha256'] == sha(run/'job.json'), 'Original prepared job binding')
    need(Path(prepared['local_run_dir']).resolve() == prepared_dir.resolve(), 'Original local preparation directory')
    need(sha(prepared_dir/'bundle.zip') == prepared['bundle_sha256'], 'Original preparation bundle hash')
    need(job['source_paths'] == prepared['source_paths'] == SOURCES, 'Frozen source path map')
    need(set(job['files_sha256']) == set(SOURCES) and job['files_sha256'] == prepared['files_sha256'],
         'Prepared complete input manifest')
    for name, relative in SOURCES.items():
        digest = job['files_sha256'][name]
        need(sha(run/name) == digest == sha(root/relative), 'Executed/current source hash drift: ' + name)
        need(sha(prepared_dir/name) == digest, 'Original prepared source hash drift: ' + name)
    need(job['files_sha256']['input.usda'] == USD_SHA, 'Pinned original 041 USD')
    need(sha(run/'source-assumptions.json') == sha(root/'models/robot-arm-urdf-v1/assumptions.json'),
         'Copied assumptions differ from approved reference package')
    config = read_json(root/SOURCES['config.json'])
    need(job['hardware_approved'] is False and job['physical_calibration'] is False
         and job['ring_geometry'] == 'DEFERRED' and config['hardware_approved'] is False
         and config['physical_calibration'] is False and config['ring_geometry'] == 'DEFERRED',
         'Simulation-only authority remains false')
    need(config['maximum_author_attempts'] == 3 and config['timeout_seconds'] == 600, 'Frozen finite execution budget')
    need(PureWindowsPath(job['owned_runs_root']) == PureWindowsPath(config['remote_runs_root'])
         and PureWindowsPath(job['expected_isaac_root']) == PureWindowsPath(config['isaac_root'])
         and job['expected_isaac_version'] == config['expected_isaac_version'], 'Approved remote runtime configuration')
    remote_run = PureWindowsPath(job['owned_runs_root'])/run_id
    need(PureWindowsPath(prepared['remote_run_dir']) == remote_run, 'Original remote attempt path')
    summary, state = read_json(run/'summary.json'), read_json(run/'status.json')
    process, supervisor = read_json(run/'exit.json'), read_json(run/'supervisor.json')
    completion = completion_gate(summary, state, process, sha(run/'summary.json'))
    need(all(value['run_id'] == run_id for value in (summary, state, process, supervisor)), 'Run identity across process/data')
    pid = integer(summary['pid'], 'actual worker PID')
    need(pid > 0 and summary['runtime']['pid'] == state['pid'] == process['pid'] == supervisor['worker_pid'] == pid,
         'Actual worker PID binding')
    need(integer(process['native_pid'], 'native PID') > 0 and process['native_pid'] == supervisor['child_pid']
         and integer(supervisor['pid'], 'supervisor PID') > 0 and process['supervisor_pid'] == supervisor['pid'],
         'Actual supervisor/native child ownership')
    need(type(process['exit_code']) is int and process['exit_code'] == 0
         and supervisor['status'] == 'FINISHED' and type(supervisor['child_exit_code']) is int
         and supervisor['child_exit_code'] == 0, 'Actual process must finish with exit0')
    need(PureWindowsPath(supervisor['expected_isaac_root']) == PureWindowsPath(job['expected_isaac_root']), 'Native runtime root binding')
    need(summary['final_before_stop'] is True and summary['hardware_approved'] is False
         and summary['physical_calibration'] is False and summary['ring_geometry'] == 'DEFERRED', 'Final pre-STOP authority boundary')
    need(type(summary['sample_count']) is int and summary['sample_count'] == 6781
         and type(summary['physics_steps']) is int and summary['physics_steps'] == 6780, 'Complete finite sample inventory')
    need(set(summary['files_sha256']) == {'static.json', 'samples.ndjson', 'scene.usda'}, 'Complete observed file manifest')
    for name, digest in summary['files_sha256'].items():
        need(sha(run/name) == digest, 'Observed output hash drift: ' + name)
    runtime = summary['runtime']
    need(runtime['run_id'] == run_id and runtime['isaac_version'] == job['expected_isaac_version']
         and runtime['scripts_sha256'] == {key: job['files_sha256'][key] for key in
             ('runtime.py', 'core.py', 'extract_usd.py', 'frames.py')}, 'Actual runtime/version/script identity')
    static = read_json(run/'static.json')
    need(static['runtime'] == runtime and PureWindowsPath(static['usd_path']) == remote_run/'input.usda',
         'Static observed source/runtime identity')
    ref_module, reference, frames, layout, core, program = context(root)
    static_result = validate_static(static, ref_module, reference, core, root)
    def records():
        with (run/'samples.ndjson').open('r', encoding='utf-8') as stream:
            for line in stream:
                need(line.strip(), 'Empty telemetry record')
                yield parse(line)
    result = compare_samples(static, records(), program, frames, layout, core)
    return {**result, **static_result, 'status': 'ACTUAL_PHYSX_GENERAL_MOTION_VERIFIED',
            'run_id': run_id, 'run_dir': str(run), 'runtime': runtime,
            'completion_evidence': completion, 'raw_runtime_status': state['status'], 'raw_runtime_phase': state['phase'],
            'mass_inertia': 'SIMULATION_ASSUMPTION', 'physical_verified': False,
            'hardware_approved': False, 'physical_calibration': False, 'motor_operation': 'NOT_RUN',
            'can_operation': 'NOT_RUN', 'rl_training': 'NOT_RUN', 'ring_geometry': 'DEFERRED'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--run-dir', type=Path, required=True)
    cli.add_argument('--root', type=Path, default=ROOT)
    cli.add_argument('--report', type=Path)
    args = cli.parse_args()
    report = args.report or args.run_dir/'validation.json'
    result = {'status': 'VALIDATING', 'hardware_approved': False}
    try:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result)+'\n', encoding='utf-8')
        result = verify_run(args.run_dir, args.root)
        code = 0
    except Exception as exc:
        result = {'status': 'FAILED', 'reason': f'{type(exc).__name__}: {exc}',
                  'physical_verified': False, 'hardware_approved': False, 'ring_geometry': 'DEFERRED'}
        code = 1
    report.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(result, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
