"""049 source-derived complete-frame and engine-command consumer, no project imports."""
import hashlib
import json
import math
from pathlib import Path
import struct
import numpy as np
DT=1/120
CALLBACK_DT=struct.unpack('f',struct.pack('f',DT))[0]
CLOCK_TOL=1e-6
CALLBACK_CLOCK_TOL=1e-9
POSITION_TOL=.001
ROTATION_TOL=.001
ANGLE_TOL=math.radians(.5)
SPEED_TOL=math.radians(1)
JOINTS=[f'J{i}' for i in range(1,7)]
LINKS=['Base']+[f'Link{i}' for i in range(1,7)]
IDENTITY=[[float(i==j) for j in range(3)] for i in range(3)]
E=API['lib']['environment']
C=API['lib']['control']
motion=API['lib']['motion']


def deep_equal(actual,expected,path='source',tolerance=1e-6):
    if isinstance(expected,dict):
        need(type(actual) is dict and set(actual)==set(expected),'Complete field schema: '+path)
        for key in expected:deep_equal(actual[key],expected[key],path+'.'+key,tolerance)
    elif isinstance(expected,list):
        need(type(actual) is list and len(actual)==len(expected),'Full field array: '+path)
        for i,(a,b) in enumerate(zip(actual,expected)):deep_equal(a,b,path+'.'+str(i),tolerance)
    elif type(expected) in (int,float):
        need(type(actual) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=tolerance,'Source numeric frame mismatch: '+path)
    else:need(type(actual) is type(expected) and actual==expected,'Source identity/type mismatch: '+path)


def validate_static_source(s,golden):
    # All frame-bearing schemas are compared, not just hashes/cardinalities.
    for key in ('units','default_prim','root_placement','robot_root','bodies','joints','colliders'):
        deep_equal(s[key],golden[key],key)
    need(set(s['environment'])==set(golden['environment']),'Complete environment observation schema')
    for key in set(golden['environment'])-{'contact_mapping','probe_runtime_mass'}:
        deep_equal(s['environment'][key],golden['environment'][key],'environment.'+key)
    validate_environment(s['environment'])
    need(s['controller']=='ENGINE_COMPUTED_TORQUE_NATIVE_PD_ZERO' and 'physx' in s['lab_manager'].lower(),'New actual controller/Lab manager')
    need(s['solver']=={'position_iterations':64,'velocity_iterations':16},'Actual authored solver settings')
    need(s['configuration']['engine']=='physx' and s['configuration']['device']=='cpu' and s['configuration']['frequency_hz']==120. and
         s['configuration']['self_collisions'] is True and error(vector(s['configuration']['gravity']),[0,0,-9.81])<=1e-6,'Actual unchanged gravity/collision/Hz')
    need(s['dof_names'] and set(s['dof_names'])==set(JOINTS) and len(s['dof_names'])==6,'Actual named DOFs')
    for name in ('kp','kd'):
        need(vector(s['gains'][name],6)==[0.]*6 and vector(s['actual_drives'][name],6)==[0.]*6,'Native PD actually zero')
    need(s['actual_drives']['types']==['force']*6 and error(vector(s['actual_drives']['effort'],6),C.CAP)<1e-6,'Actual native force mode/caps')
    bodies={b['name']:b for b in s['bodies']}
    need(len(s['runtime_masses'])==7 and {b['name'] for b in s['runtime_masses']}==set(LINKS),'All runtime mass frames')
    values=list(s['runtime_masses'])+[{'name':'probe',**s['environment']['probe_runtime_mass']}]
    for item in values:
        source=bodies[item['name']] if item['name']!='probe' else s['environment']['probe_source_observation']
        need(abs(number(item['mass'],'mass')-number(source['mass'],'source mass'))<=1e-6 and error(vector(item['com']),vector(source['com']))<=1e-6,'Runtime assumed mass/local COM')
        rotation=quaternion(source['principal_axes_wxyz']);diag=vector(source['inertia_diag']);expected=mm(mm(rotation,[[diag[i] if i==j else 0 for j in range(3)] for i in range(3)]),transpose(rotation))
        actual=matrix(item['inertia_link_about_com'],rigid=False)
        need(error(actual,expected)<=1e-7,'Full LINK inertia tensor about COM')
        principal=quaternion(item['principal_axes_wxyz']);diagonal=mm(mm(transpose(principal),actual),principal)
        need(min(diagonal[i][i] for i in range(3))>0 and max(abs(diagonal[i][j]) for i in range(3) for j in range(3) if i!=j)<=1e-7,'Runtime principal frame diagonalizes tensor')


def verify_run(records,api):
    records=Path(records);job=api['job'];runtime_cfg=api['cfg'];summary=read_json(records/'summary.json');state=read_json(records/'status.json')
    ex=read_json(records/'exit.json');sup=read_json(records/'supervisor.json')
    job_sha=api['sha'](api['run']/'job.json')
    module=read_json(records/'native-module.json')
    need(sha(records/'native-module.json')==summary['runtime']['module_probe_sha256'] and module['pid']==summary['pid'] and
         module['job_sha256']==job_sha and module['status']=='MODULE_GPU_CAPTURED' and module['device']=='cuda:0' and
         module['sum']==6 and module['cuda'].startswith('13.'),'Same-process actual module/GPU operation')
    expected_versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','warp':'1.17.0','rsl_rl':'5.5.1'}
    need(set(module['modules'])==set(expected_versions)|{'gymnasium'},'Complete actual module observation')
    for name,identity in module['modules'].items():
        need(Path(identity['origin']).resolve().is_relative_to(Path(job['prefix']).resolve()),'Approved module provider')
        if name in expected_versions:need(identity['version']==expected_versions[name],'Exact runtime module version')
    need(summary['run_id']==state['run_id']==ex['run_id']==sup['run_id']==job['run_id'],'All actual run identities')
    need(ex['job_sha256']==sup['job_sha256']==summary['runtime']['job_sha256']==job_sha,'Original job authority binding')
    need(summary['runtime']['input_sha256']==job['inputs'] and summary['runtime']['isaac_version']==runtime_cfg['isaac_version'],'Executed complete payload/SDK identity')
    need(type(ex['exit_code']) is int and ex['exit_code']==sup['child_exit_code']==0 and sup['status']=='FINISHED','Actual completed native exit0')
    need(type(summary['pid']) is int and summary['pid']>0 and summary['pid']==state['pid']==ex['pid']==sup['worker_pid'],'Actual worker PID')
    need(ex['native_pid']==sup['child_pid']==summary['runtime']['parent_pid'] and ex['supervisor_pid']==sup['pid'],'Supervisor/cmd/worker process linkage')
    need(summary['status']=='DATA_CAPTURED' and summary['kind']=='ACTUAL_PHYSX_DRIVE_TELEMETRY' and summary['final_before_stop'] is True,'Actual complete capture before reset')
    closed=state['status']=='CLOSED' and state['phase']=='APP_CLOSED'
    pre=state['status']=='DATA_CAPTURED' and state['phase']=='CLOSING_APP'
    need(closed or pre and summary['runtime']['close_protocol']=='OFFICIAL_FAST_SHUTDOWN_EXPLICIT_EXIT','Bound completion protocol')
    need(summary['experiment']=='ISOLATED_COMPUTED_TORQUE_049' and summary['protocol']=='LAB_PLAYING_EXPLICIT_STEP' and summary['sample_count']==6781 and summary['physics_steps']==6780,'Registered full experiment')
    need(set(summary['files_sha256'])=={'static.json','samples.ndjson','scene.usda'},'Full raw record inventory')
    for name,h in summary['files_sha256'].items():need(sha(records/name)==h,'Raw bytes changed: '+name)
    s=read_json(records/'static.json');need(s['runtime']==summary['runtime'] and s['usd_sha256']==job['inputs']['data/model.usda'],'Observed static source/runtime')
    validate_static_source(s,api['golden'])
    program=motion.load_program(api['run']/'input/data/program.json');frames=api['lib']['frames'];layout=frames.decode((api['run']/'input/data/kinematics.json').read_bytes())
    with (records/'samples.ndjson').open(encoding='utf-8') as f:rows=[parse(line) for line in f]
    contact=audit_contacts(s,rows,program);result=compare_samples(s,rows,program,frames,layout,motion)
    ok=not result['tracking_failures'] and not contact['dynamic_failures']
    need(summary['hardware_approved'] is False and summary['physical_calibration'] is False,'No physical authority')
    return {**result,**contact,'status':'ISOLATED_LAB_COMPUTED_TORQUE_PASS' if ok else 'DYNAMICS_FAILED','motion_accepted':ok,
        'run_id':job['run_id'],'evidence_valid':True,'max_endpoint_error_deg':math.degrees(result['metrics_max']['endpoint_angle_rad']),
        'max_endpoint_speed_deg_s':math.degrees(result['metrics_max']['endpoint_speed_rad_s']),'hardware_approved':False,
        'physical_calibration':False,'training':'NOT_RUN','mass_inertia':'SIMULATION_ASSUMPTION','ring_geometry':'DEFERRED'}

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
        need(sample['timeline_playing'] is True, 'Actual Lab playing explicit-step protocol')
        need(type(sample['lab_step']) is int and sample['lab_step']==static['lab_baseline_step']+index and
             sample['clock']['lab_read_before']==sample['clock']['lab_read_after']==sample['lab_step'], 'Actual Lab step/read ownership')
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

def audit_contacts(static, rows, program):
    failures, previous, probe_start = set(), None, None
    max_unwanted, max_probe_force, min_probe_z, max_saturation = 0., 0., float('inf'), 0
    proxies={x['link']:x for x in read_json(API['run']/'input/data/assumptions.json')['links']}
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
            actual=row['actuation'];command=motion.sample(program,i/120)
            expected=C.command(previous['q_rad'],previous['qd_rad_s'],command,C.acceleration(motion,program,i/120),actual['M'],actual['g'],actual['c'])
            need(actual['source_index']==i-1 and actual['read_step']==row['clock']['step_before'], 'Actual engine dynamics and previous q/qd step binding')
            for key in ('tau','raw_tau'):
                need(error(vector(actual[key],6),expected[key])<=1e-8, 'Recomputed engine-M control command')
            need(error(vector(actual['qdd_ref'],6),C.acceleration(motion,program,i/120))<=1e-10, 'Reference acceleration')
            need(actual['saturated']==expected['saturated'] and actual['torque_scope']=='SIM_COMMAND_NOT_MEASURED_ACTUATOR_FORCE','Torque/saturation meaning')
            need(all(abs(x-y)<=1e-6+1e-5*abs(x) for x,y in zip(actual['tau'],vector(actual['tau_readback'],6))) and
                 all(abs(x)<=cap+1e-9 for x,cap in zip(actual['tau'],C.CAP)), 'Observed command readback/caps')
            max_saturation+=int(any(expected['saturated']))
        else:
            need(row['actuation'] is None, 'Initial uncommanded baseline')
        previous = row
    if max_unwanted>.001:
        failures.add('UNWANTED_ROBOT_CONTACT')
    if max_probe_force<=.1 or probe_start-min_probe_z<.05:
        failures.add('CONTACT_ENGINE_POSITIVE_CONTROL_FAILED')
    if max_saturation:
        failures.add('COMPUTED_TORQUE_COMMAND_SATURATED')
    return {'dynamic_failures':sorted(failures),'contact_probe':{'max_floor_normal_force_N':max_probe_force,
        'initial_z_m':probe_start,'min_z_m':min_probe_z,'final_z_m':previous['probe_pose']['position'][2]},
        'max_unwanted_robot_normal_force_N':max_unwanted,'command_saturation_samples':max_saturation}
