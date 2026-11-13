"""043 gravity/collision consumer; old043 data and source042 remain immutable."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
BASE_VERIFY_SHA='ceb5f3da61592ac61f19923a1bc8844d843ac4af85ee650289532de9558d4724'

# Verify every reused repository helper before any transitive project import.
_pins=json.loads((Path(__file__).with_name('pins.json')).read_text(encoding='utf-8'))
for _path,_digest in _pins['dependencies_sha256'].items():
    if hashlib.sha256((ROOT/_path).read_bytes()).hexdigest()!=_digest:
        raise ValueError('Approved transitive dependency drift before import: '+_path)
def module(name,path,approved_sha=None):
    if approved_sha is not None and hashlib.sha256(Path(path).read_bytes()).hexdigest()!=approved_sha:
        raise ValueError('Approved baseline dependency hash drift')
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
B=module('_contact_baseline',ROOT/'src/simulation/motion/verify.py',BASE_VERIFY_SHA)
C=module('_contact_core',Path(__file__).with_name('core.py'))
E=module('_contact_environment',Path(__file__).parent.parent/'contact_motion/environment.py')
R=module('_contact_runtime',Path(__file__).with_name('runtime.py'))
SOURCES=R.SOURCE_PATHS
B.SOURCES=SOURCES
for _name in ('need','sha','read_json','number','integer','vector','matrix','quaternion','error','mm','mv',
              'transpose','check_identity_pose','context','parse','completion_gate','USD_SHA','LINKS','JOINTS','IDENTITY',
              'DT','CALLBACK_DT','CLOCK_TOL','CALLBACK_CLOCK_TOL','POSITION_TOL','ROTATION_TOL','ANGLE_TOL','SPEED_TOL','frame'):
    globals()[_name]=getattr(B,_name)


def validate_environment(env):
    need(set(env['actors']) == set(E.SENSORS) and len(env['actors']) == 8, 'Eight actual rigid actors')
    expected_colliders = {p+'/assumed_aabb_proxy' for p in E.PATHS} | {E.PROBE, E.GROUND}
    need(set(env['colliders']) == expected_colliders and len(env['colliders']) == 9, 'Nine exact collider frames')
    ground, probe = env['ground'], env['probe']
    for item, path, position, basis, size, rigid in (
        (ground, E.GROUND, [0,0,-.05], [[4,0,0],[0,4,0],[0,0,.1]], 1., False),
        (probe, E.PROBE, [-.6,0,.2], IDENTITY, .05, True)):
        need(item['path'] == path and item['rigid'] is rigid and item['collision_enabled'] is True, 'Environment body/collider identity')
        need(error(vector(item['position']), position) <= 1e-6 and
             error(matrix(item['basis'], rigid=False), basis) <= 1e-6 and abs(item['size']-size) < 1e-6,
             'Actual floor/probe placement, orientation and scale')
    need(probe['collider_owner_path'] == E.PROBE and error(vector(probe['collider_local_position']), [0,0,0]) < 1e-8
         and error(matrix(probe['collider_local_basis']), IDENTITY) < 1e-8, 'Probe local collider frame')
    inertia = .1*.05*.05/6
    for observed in (probe, env['probe_source_observation'], env['probe_runtime_mass']):
        need(abs(number(observed['mass'], 'probe mass')-.1) < 1e-6 and
             error(vector(observed['com']), [0,0,0]) < 1e-6, 'Probe assumed mass/local COM')
        principal = quaternion(observed['principal_axes_wxyz'])
        if 'inertia_link_about_com' in observed:
            tensor = matrix(observed['inertia_link_about_com'], rigid=False)
        else:
            diagonal = vector(observed['inertia_diag'])
            tensor = mm(mm(principal, [[diagonal[i] if i == j else 0. for j in range(3)] for i in range(3)]), transpose(principal))
        need(error(tensor, [[inertia if i == j else 0. for j in range(3)] for i in range(3)]) < 1e-7,
             'Probe COM-centred principal/full inertia frame')
    p = env['probe_source_observation']
    need(p['path'] == E.PROBE and error(vector(p['position']), [-.6,0,.2]) < 1e-6
         and error(matrix(p['rotation']), IDENTITY) < 1e-6, 'Observed probe LINK frame')
    mat = env['material']
    need(mat['path'] == E.MATERIAL and abs(mat['static_friction']-.6)<1e-6 and
         abs(mat['dynamic_friction']-.5)<1e-6 and mat['restitution']==0, 'Assumed contact material')
    need(env['filters'] == {a:[b] for a,b in zip(E.PATHS,E.PATHS[1:])}, 'Only six adjacent collision exclusions')
    need(env['joint_collisions'] == {name:True for name in JOINTS}, 'Every revolute collision flag enabled')
    need(env['report_thresholds'] == {p:0 for p in E.SENSORS}, 'Every actor contact reporting threshold zero')
    need(env['material_bindings'] == {p:[E.MATERIAL] for p in expected_colliders}, 'Every collider material binding')
    mapping = env['contact_mapping']
    need(mapping['canonical_sensors'] == E.SENSORS and mapping['canonical_filters'] == E.FILTERS and
         mapping['capacity'] == 512 and mapping['force_frame'] == 'WORLD' and mapping['force_units']=='N', 'Contact mapping units/frame')
    need(len(mapping['sensor_paths']) == 8 and set(mapping['sensor_paths']) == set(E.SENSORS) and
         len(mapping['filter_paths']) == 8 and all(len(p)==9 and set(p)==set(E.FILTERS) for p in mapping['filter_paths']),
         'Actual tensor sensor/filter path index mapping')


def audit_contacts(static, rows):
    failures, previous, probe_start = set(), None, None
    max_unwanted, max_probe_force, min_probe_z, max_saturation = 0., 0., float('inf'), 0
    proxies={x['link']:x for x in read_json(ROOT/SOURCES['source-assumptions.json'])['links']}
    for i, row in enumerate(rows):
        need(type(row['index']) is int and row['index']==i, 'Contact sample ordering')
        p = vector(row['probe_pose']['position']); quaternion(row['probe_pose']['orientation_wxyz'])
        if probe_start is None:
            probe_start = p[2]
        min_probe_z = min(min_probe_z, p[2])
        need(abs(p[0]+.6) < .01 and abs(p[1]) < .01, 'Probe remains in isolated test column')
        if i >= 120 and abs(p[2]-.025) > .002:
            failures.add('PROBE_DID_NOT_SETTLE_ON_FLOOR')
        data = row['contacts']
        need(abs(number(data['dt_s'], 'contact dt')-1/120) < 1e-9, 'Impulse to force conversion dt')
        matrix_force = np.asarray(data['normal_force_N'], dtype=float)
        counts = np.asarray(data['counts'])
        need(matrix_force.shape==(8,9,3) and np.isfinite(matrix_force).all() and counts.shape==(8,9)
             and np.issubdtype(counts.dtype,np.integer) and counts.min()>=0 and counts.sum()<512, 'Contact buffer overflow/shape/finite')
        need(len(data['active']) == int(counts.sum()), 'Full detailed contact inventory')
        aggregate, observed_counts = np.zeros((8,9,3)), np.zeros((8,9), dtype=int)
        poses={x['name']:(np.asarray(x['position']),np.asarray(quaternion(x['orientation_wxyz']))) for x in row['links']}
        poses['ContactProbe']=(np.asarray(p),np.asarray(quaternion(row['probe_pose']['orientation_wxyz'])))
        def inside_contact_body(path,point):
            if path==E.GROUND:
                position=np.asarray([0.,0.,-.05]);rotation=np.eye(3);center=np.zeros(3);half=np.asarray([2.,2.,.05])
            else:
                name='ContactProbe' if path==E.PROBE else LINKS[E.PATHS.index(path)]
                position,rotation=poses[name]
                center=np.zeros(3) if name=='ContactProbe' else np.asarray(proxies[name]['com_m'])
                half=np.asarray([.025]*3) if name=='ContactProbe' else np.asarray(proxies[name]['box_size_m'])/2
            local=rotation.T@(point-position)-center
            need(np.all(np.abs(local)<=half+.025), 'Contact point world frame must lie near both colliders')
        for item in data['active']:
            si, fi = integer(item['sensor'],'sensor index'), integer(item['filter'],'filter index')
            need(0<=si<8 and 0<=fi<9, 'Actual contact index range')
            force = number(item['force_N'],'normal force'); normal = vector(item['normal'])
            point=np.asarray(vector(item['point'])); number(item['separation_m'],'separation')
            need(force >= -1e-6 and abs(sum(x*x for x in normal)-1)<1e-4, 'World-space contact normal/scalar force')
            inside_contact_body(E.SENSORS[si],point);inside_contact_body(E.FILTERS[fi],point)
            if fi==0:
                need(error(normal,[0.,0.,1.])<1e-3 and abs(point[2])<.025, 'Floor contact normal/point are in world Z-up frame')
            aggregate[si,fi] += force*np.asarray(normal); observed_counts[si,fi] += 1
        need(np.array_equal(counts,observed_counts) and
             np.max(np.abs(aggregate-matrix_force)) <= .001+1e-4*np.max(np.abs(matrix_force)), 'Detailed contacts must reproduce world normal-force matrix')
        max_probe_force = max(max_probe_force, float(matrix_force[7,0,2]))
        for si in range(7):
            for fi in range(9):
                if si==0 and fi==0:
                    continue  # Fixed mounting face may touch the floor.
                max_unwanted = max(max_unwanted, float(np.linalg.norm(matrix_force[si,fi])))
        if i:
            actual = row['actuation']; expected = C.bounded_efforts(C.gravity_efforts(static, previous['links']))
            need(actual['source_index'] == i-1 and actual['read_step'] == row['clock']['step_before'], 'Previous actual pose drives feedforward at the same command step')
            for key in ('ff','pd_cap'):
                planned = vector(actual[key],6,key); readback = vector(actual[key+'_readback'],6,key+' readback')
                need(error(planned,expected[key])<1e-9 and all(abs(x-y)<=1e-6+abs(x)*1e-5 for x,y in zip(planned,readback)),
                     'Gravity command or residual drive cap readback')
            need(actual['saturated'] == expected['saturated'] and
                 all(abs(t)+cap<=total+1e-9 for t,cap,total in zip(actual['ff'],actual['pd_cap'],C.CAP)), 'Conservative total effort cap')
            max_saturation += int(any(actual['saturated']))
        else:
            need(row['actuation'] is None, 'Initial uncommanded baseline')
        previous = row
    if max_unwanted>.001:
        failures.add('UNWANTED_ROBOT_CONTACT')
    if max_probe_force<=.1 or probe_start-min_probe_z<.05:
        failures.add('CONTACT_ENGINE_POSITIVE_CONTROL_FAILED')
    if max_saturation:
        failures.add('GRAVITY_FEEDFORWARD_SATURATED')
    return {'dynamic_failures':sorted(failures),'contact_probe':{'max_floor_normal_force_N':max_probe_force,
        'initial_z_m':probe_start,'min_z_m':min_probe_z,'final_z_m':previous['probe_pose']['position'][2]},
        'max_unwanted_robot_normal_force_N':max_unwanted,'feedforward_saturation_samples':max_saturation}


def audit_record_quality(static, rows, program, motion_core):
    """Check all observation/clock fields even when tracking later fails early."""
    need(len(rows)==6781, 'Complete observation inventory')
    start_step=integer(static['baseline_step'],'baseline step')
    start_time=number(static['baseline_time_s'],'baseline time')
    previous=None
    for i,row in enumerate(rows):
        need(type(row['index']) is int and row['index']==i and abs(number(row['schedule_time_s'],'schedule')-i/120)<1e-10,
             'Full observation index/schedule')
        expected=motion_core.sample(program,i/120)
        need(row['segment']==expected['segment'] and row['checkpoint']==expected['checkpoint'] and
             error(vector(row['target_q_rad'],6),expected['q_rad'])<1e-10 and
             error(vector(row['target_qd_rad_s'],6),expected['qd_rad_s'])<1e-10, 'Exact unchanged full recipe')
        vector(row['q_rad'],6);vector(row['qd_rad_s'],6)
        need(row['timeline_paused'] is True and len(row['links'])==7 and {x['name'] for x in row['links']}==set(LINKS), 'Full actual LINK observation schema')
        for pose in row['links']:
            vector(pose['position']);quaternion(pose['orientation_wxyz'])
        clock=row['clock']
        for key in ('step_before','step_after','read_step_before','read_step_after','callback_count'):
            integer(clock[key],key)
        need(clock['step_after']==start_step+i and clock['callback_count']==i and
             clock['read_step_before']==clock['read_step_after']==clock['step_after'], 'Full same-step observation/callback counts')
        before=number(clock['time_before_s'],'time before');after=number(clock['time_after_s'],'time after')
        callback=number(clock['callback_time_s'],'callback time')
        need(abs(after-start_time-i/120)<=1e-6 and abs(callback-i*B.CALLBACK_DT)<=1e-9, 'Independent actual clock domains')
        if i:
            need(clock['step_before']==previous['step_after'] and abs(before-previous['time_after_s'])<=1e-6 and
                 clock['step_after']-clock['step_before']==1 and abs(after-before-1/120)<=1e-6 and
                 abs(callback-previous['callback_time_s']-B.CALLBACK_DT)<=1e-9, 'Full physics interval continuity')
        else:
            need(clock['step_before']==start_step and abs(before-start_time)<=1e-6 and abs(after-before)<=1e-6 and callback==0,
                 'Unstepped baseline')
        previous=clock

def validate_static(static, reference_module, reference, core, root=ROOT):
    """Check every source frame and actual post-initialization local mass frame."""
    need(static['control_variant'] in ('solver','solver_pd'), 'Approved observed variant')
    need(static['solver']=={'position_iterations':64,'velocity_iterations':16}, 'Actual solver settings differ')
    need(all(type(x) is int for x in static['solver'].values()), 'Integer solver settings')
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
    need(config == {'engine': 'physx', 'device': 'cpu', 'gravity': config['gravity'],
                    'frequency_hz': 120., 'self_collisions': True}, 'Actual isolated PhysX configuration')
    need(config['self_collisions'] is True and error(vector(config['gravity']), [0., 0., -9.81]) <= 1e-6
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
        need(collider['enabled'] is True and number(collider['size'], 'Cube size') == 1.,
             'Actual unit-cube collision proxy enabled')
        expected = proxies[name]
        need(error(vector(collider['local_position']), vector(expected['com_m'])) <= 1e-5,
             'Collider local position differs from source: ' + name)
        basis = matrix(collider['local_basis'], 'collider basis', rigid=False)
        size = vector(expected['box_size_m'])
        expected_basis = [[size[i] if i == j else 0. for j in range(3)] for i in range(3)]
        need(error(basis, expected_basis) <= 1e-5, 'Collider local basis/scale differs from source: ' + name)
    need(owners == set(LINKS), 'Collider frame coverage of every LINK')
    return {'source_frame_result': source_result['status'], 'runtime_mass_metrics': maxima}



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
    tracking_failures = set()
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
            if angle_error > ANGLE_TOL or speed > SPEED_TOL:
                tracking_failures.add(sample['checkpoint'])
            if '_positive' in sample['checkpoint'] and '_after_' not in sample['checkpoint']:
                if actual_q[JOINTS.index(sample['checkpoint'].split('_')[0])] <= 0:
                    tracking_failures.add(sample['checkpoint'])
            if sample['checkpoint'].endswith('_negative') and '_after_' not in sample['checkpoint']:
                if actual_q[JOINTS.index(sample['checkpoint'].split('_')[0])] >= 0:
                    tracking_failures.add(sample['checkpoint'])
        seen += 1
    need(seen == expected_count and checkpoints == names, 'All samples and all 28 ordered checkpoints required')
    need(expected['checkpoint'] == 'final_zero', 'Actual final checkpoint required')
    if max(abs(q) for q in actual_q) > ANGLE_TOL or max(abs(v) for v in actual_qd) > SPEED_TOL:
        tracking_failures.add('final_zero')
    return {'status': 'HOST_DATA_CHECKS_ONLY', 'sample_count': seen, 'physics_steps': seen-1,
            'checkpoints': checkpoints, 'metrics_max': maxima, 'tracking_failures': sorted(tracking_failures),
            'checkpoints_passed': len(checkpoints)-len(tracking_failures), 'full_frame_samples': seen,
            'frame_coverage': ['world', 'robot_root', '7_LINK', 'fixed_both_sides', '6_revolute_both_sides',
                               '6_signed_axes', '7_local_COM', '7_principal_inertia', '7_disabled_colliders']}

def verify_run(run_dir, root=ROOT):
    """Bind current sources, original preparation, actual process and raw data."""
    root, run = Path(root).resolve(), Path(run_dir).resolve()
    job = read_json(run/'job.json')
    run_id = job['run_id']
    need(type(run_id) is str and re.fullmatch('[0-9a-f]{32}', run_id), 'GUID attempt identity')
    prepared_dir = root/'outputs/isaac-settling-v1/runs'/run_id
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
    need(config['maximum_author_attempts'] == 2 and config['timeout_seconds'] == 600, 'Frozen finite execution budget')
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
             ('runtime.py', 'core.py', 'motion_core.py', 'environment.py', 'extract_usd.py', 'frames.py')}, 'Actual runtime/version/script identity')
    static = read_json(run/'static.json')
    need(static['control_variant']==job['control_variant'], 'Observed/prepared variant binding')
    need(static['runtime'] == runtime and PureWindowsPath(static['usd_path']) == remote_run/'input.usda',
         'Static observed source/runtime identity')
    ref_module, reference, frames, layout, core, program = context(root)
    static_result = validate_static(static, ref_module, reference, core, root)
    validate_environment(static['environment'])
    need(summary['experiment'] == 'GRAVITY_COLLISION_047', 'Experiment identity')
    def records():
        with (run/'samples.ndjson').open('r', encoding='utf-8') as stream:
            for line in stream:
                need(line.strip(), 'Empty telemetry record')
                yield parse(line)
    rows = list(records())
    need(len(rows) == 6781, 'Complete actual contact experiment')
    audit_record_quality(static, rows, program, core)
    contact_result = audit_contacts(static, rows)
    result = compare_samples(static, iter(rows), program, frames, layout, core)
    motion_ok = not result['tracking_failures']
    status = 'GRAVITY_COLLISION_MOTION_PASS' if motion_ok and not contact_result['dynamic_failures'] else 'DYNAMICS_FAILED'
    if 'frame_coverage' in result:
        result['frame_coverage'] = [x.replace('disabled_colliders','enabled_colliders') for x in result['frame_coverage']] + ['floor_frame','probe_LINK_COM_inertia_collider','contact_world_frame_and_mapping']
    return {**result, **static_result, 'status': status, 'evidence_valid': True, **contact_result,
            'run_id': run_id, 'run_dir': str(run), 'runtime': runtime,
            'completion_evidence': completion, 'raw_runtime_status': state['status'], 'raw_runtime_phase': state['phase'],
            'mass_inertia': 'SIMULATION_ASSUMPTION', 'physical_verified': False,
            'hardware_approved': False, 'physical_calibration': False, 'motor_operation': 'NOT_RUN',
            'can_operation': 'NOT_RUN', 'rl_training': 'NOT_RUN', 'ring_geometry': 'DEFERRED',
            'approved_baseline_verify_sha256': BASE_VERIFY_SHA}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--run-dir',type=Path,required=True);cli.add_argument('--root',type=Path,default=ROOT)
    args=cli.parse_args(); report=args.run_dir/'validation.json'
    try:
        result=verify_run(args.run_dir,args.root);code=0 if result['status']=='GRAVITY_COLLISION_MOTION_PASS' else 2
    except Exception as exc:
        result={'status':'INVALID_EVIDENCE','evidence_valid':False,'reason':f'{type(exc).__name__}: {exc}','hardware_approved':False};code=1
    report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result));return code


if __name__=='__main__':
    raise SystemExit(main())
