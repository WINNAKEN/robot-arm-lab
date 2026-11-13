if __name__ == '__main__':
    raise SystemExit('Use launch.ps1; direct execution is forbidden')

import math
import struct
from pathlib import Path
need,read,sha=API['need'],API['read'],API['sha']
IDENTITY=[[float(i==j) for j in range(3)] for i in range(3)]
LINKS=['Base']+[f'Link{i}' for i in range(1,7)]
JOINTS=[f'J{i}' for i in range(1,7)]
DT=1/120
CALLBACK_DT=struct.unpack('f',struct.pack('f',DT))[0]

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


def static_check(s, golden, cfg):
    for key in ('units','default_prim','root_placement','robot_root','bodies','joints','colliders'):
        deep_equal(s[key],golden[key],key)
    expected = {k:v for k,v in golden['environment'].items() if k not in ('contact_mapping','probe_runtime_mass')}
    deep_equal(s['environment'],expected,'complete source environment')
    deep_equal(s['configuration'],{'gravity':[0,0,0],'frequency_hz':120,'device':'cpu','manager':'isaaclab_physx.physics.physx_manager.PhysxManager'})
    need(len(s['dof_names'])==6 and set(s['dof_names'])==set(JOINTS), 'Exact named DOFs')
    deep_equal(s['actual_drives'],{'kp':[0]*6,'kd':[0]*6,'effort':cfg['cap_Nm'],'types':['force']*6})
    expected_bodies = {b['name']:b for b in s['bodies']}
    expected_bodies['probe'] = s['environment']['probe_source_observation']
    runtime = s['runtime_masses']
    need(len(runtime)==8 and {b['name'] for b in runtime}==set(expected_bodies), 'All runtime mass frames')
    for item in runtime:
        source = expected_bodies[item['name']]
        need(abs(number(item['mass'],'mass')-source['mass'])<=1e-6 and error(vector(item['com']),source['com'])<=1e-6,'Runtime mass/local COM')
        rotation = quaternion(source['principal_axes_wxyz'])
        d = vector(source['inertia_diag'])
        expected_tensor = mm(mm(rotation,[[d[i] if i==j else 0 for j in range(3)] for i in range(3)]),transpose(rotation))
        actual = matrix(item['inertia_link_about_com'],rigid=False)
        need(error(actual,expected_tensor)<=1e-7,'Full source inertia tensor')
        principal = quaternion(item['principal_axes_wxyz'])
        diagonal = mm(mm(transpose(principal),actual),principal)
        need(min(diagonal[i][i] for i in range(3))>0 and max(abs(diagonal[i][j]) for i in range(3) for j in range(3) if i!=j)<=1e-7,'Principal frame diagonalizes full tensor')


def rows_check(s, rows, api):
    need(type(rows) is list and len(rows)==11,'All eleven connection observations')
    layout = api['lib']['frames'].decode(api['data']['data/kinematics.json'])
    frames = api['lib']['frames']
    bodies = {b['name']:b for b in s['bodies']}
    paths = {b['path']:name for name,b in bodies.items()}
    joints = {j['name']:j for j in s['joints'] if j['type']=='revolute'}
    fixed = [j for j in s['joints'] if j['type']=='fixed']
    need(set(joints)==set(JOINTS) and len(fixed)==1,'Complete physical joints')
    baseline = rows[0]['read_after']
    base_lab = integer(baseline['lab_step'],'baseline Lab step')
    base_time = number(baseline['engine_time_s'],'baseline engine time')
    maxima = {'link_m':0.,'rotation':0.,'anchor_m':0.,'joint_rotation':0.,'axis':0.,'angle_rad':0.,'speed_rad_s':0.}
    previous = None
    for index,row in enumerate(rows):
        need(type(row['index']) is int and row['index']==index and row['timeline_playing'] is True,'Actual indexed playing observation')
        deep_equal(row['read_before'],row['read_after'],'read ownership',1e-10)
        clock = row['read_after']
        need(set(clock)=={'lab_step','engine_event_index','engine_time_s','callback_time_s'},'Closed observed clock schema')
        need(integer(clock['lab_step'],'Lab step')==base_lab+index and integer(clock['engine_event_index'],'PhysX post-event index')==index,'Actual Lab request/post-step progress')
        need(abs(number(clock['engine_time_s'],'engine time')-base_time-index*DT)<=1e-6,'Actual engine time progression')
        need(abs(number(clock['callback_time_s'],'callback time')-index*CALLBACK_DT)<=1e-9,'Actual float32 post-step dt progression')
        deep_equal(row['before_step'],previous if previous is not None else baseline,'Consecutive step interval',1e-10)
        previous = clock
        q,qd = vector(row['q_rad'],6),vector(row['qd_rad_s'],6)
        maxima['angle_rad'] = max(maxima['angle_rad'],max(abs(x) for x in q))
        maxima['speed_rad_s'] = max(maxima['speed_rad_s'],max(abs(x) for x in qd))
        need(maxima['angle_rad']<=math.radians(.5) and maxima['speed_rad_s']<=math.radians(1),'Gravity-zero unchanged display pose')
        need(len(row['links'])==7 and {x['name'] for x in row['links']}==set(LINKS),'All actual LINK poses')
        poses = {x['name']:(vector(x['position']),quaternion(x['orientation_wxyz'])) for x in row['links']}
        fk_rows = frames.fk(layout,q)
        fk = {'Base':([0.,0.,0.],IDENTITY),**{f'Link{i}':(r['origin_m'],r['rotation_world']) for i,r in enumerate(fk_rows,1)}}
        for name in LINKS:
            maxima['link_m']=max(maxima['link_m'],error(poses[name][0],fk[name][0]))
            maxima['rotation']=max(maxima['rotation'],error(poses[name][1],fk[name][1]))
        def pose(target):
            if target in paths:
                return poses[paths[target]]
            need(target in (None,'','/World/Robot','/World'),'Unknown root joint target')
            return [0.,0.,0.],IDENTITY
        for joint in [*fixed,*[joints[n] for n in JOINTS]]:
            a,b=frame(pose(joint['body0']),joint,0),frame(pose(joint['body1']),joint,1)
            maxima['anchor_m']=max(maxima['anchor_m'],error(a[0],b[0]))
            rotated=a[1]
            if joint['type']=='revolute':
                i=JOINTS.index(joint['name']);axis=[float(joint['axis']==x) for x in 'XYZ']
                rotated=mm(a[1],frames.rotation(axis,q[i]))
                maxima['axis']=max(maxima['axis'],error(mv(a[1],axis),fk_rows[i]['axis_world']),error(mv(b[1],axis),fk_rows[i]['axis_world']))
            maxima['joint_rotation']=max(maxima['joint_rotation'],error(rotated,b[1]))
        need(maxima['link_m']<=.001 and maxima['anchor_m']<=.001 and max(maxima['rotation'],maxima['joint_rotation'],maxima['axis'])<=.001,'All physical frames/FK/closure/signed axes')
        probe=row['probe_pose'];expected=s['environment']['probe']
        need(error(vector(probe['position']),vector(expected['position']))<=.001 and error(quaternion(probe['orientation_wxyz']),IDENTITY)<=.001,'Gravity-zero probe frame')
    return maxima


def consume(records, api):
    records=Path(records);terminal=read(records/'terminal.json');ex=read(records/'exit.json')
    run,job,cfg=api['run'],api['job'],api['cfg'];job_hash=sha(run/'job.json')
    need(terminal['run_id']==ex['run_id']==job['run_id'] and terminal['job_sha256']==ex['job_sha256']==job_hash,'Run/job execution binding')
    need(type(terminal['code']) is int and terminal['code']==0 and type(ex['child_exit_code']) is int and ex['child_exit_code']==0,'Worker/process failure dominates')
    need(terminal['status'] in ('COMPLETE_PRE_CLOSE','CLOSED') and terminal['phase'] in ('CLOSING_APP','APP_CLOSED') and ex['status']=='FINISHED','Complete shutdown protocol')
    need(type(terminal['pid']) is int and terminal['pid']>0 and terminal['pid']==ex['child_pid']==ex['worker_pid'] and terminal['parent_pid']==ex['pid'],'Direct Python supervisor/worker PID chain')
    need(terminal['hardware_approved'] is False and terminal['physical_calibration'] is False and terminal['training']=='NOT_RUN','No physical/training authority')
    files={'static.json','rows.json','scene.usda','modules.json','sdk.json'}
    need(set(terminal['files_sha256'])==files,'Complete native observation inventory')
    for name,h in terminal['files_sha256'].items():
        need(sha(records/name)==h,'Changed raw observation '+name)
    sdk,modules=read(records/'sdk.json'),read(records/'modules.json')
    for item in (sdk,modules):
        need(item['pid']==terminal['pid'] and item['job_sha256']==job_hash,'Same-process SDK/module observations')
    need(sdk['version']==cfg['isaac_version'] and Path(sdk['isaacsim_origin']).is_relative_to(Path(cfg['isaac_root'])) and
         sdk['bootstrap_sha256']=={k:v['sha256'] for k,v in cfg['sdk_files'].items()},'Actual SDK initialization identity')
    versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','warp':'1.17.0','gymnasium':'1.4.0','rsl_rl':'5.5.1'}
    need(set(modules['modules'])==set(versions) and modules['cuda'].startswith('13.') and modules['sum']==6. and modules['device']=='cuda:0','Actual module/GPU calculation')
    for name,version in versions.items():
        item=modules['modules'][name]
        need(item['version']==version and Path(item['origin']).is_relative_to(Path(cfg['installation_prefix'])),'Approved framework provider')
    s=read(records/'static.json')
    need(s['run_id']==run.name and s['job_sha256']==job_hash and s['pid']==terminal['pid'] and s['usd_sha256']==job['inputs']['data/model.usda'],'Actual observed model identity')
    static_check(s,api['parse'](api['data']['data/golden.json']),cfg)
    metrics=rows_check(s,read(records/'rows.json'),api)
    return {'status':'ISAACLAB_CONNECTION_VERIFIED_GRAVITY_ZERO','run_id':run.name,'sdk_connected':True,'source_scope':'050_CONNECTION_ONLY',
            'physical_steps':10,'sample_count':11,'metrics_max':metrics,'motion_settling':'NOT_TESTED_UNRESOLVED_047',
            'mass_inertia':'SIMULATION_ASSUMPTION','hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN','weights':None,'ring_geometry':'DEFERRED'}
