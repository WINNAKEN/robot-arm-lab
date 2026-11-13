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


def validate_static(value, facets, api):
    s=value;golden=api['parse'](api['data']['data/golden.json'])
    for key in ('units','default_prim','root_placement','robot_root','bodies','joints','colliders'):
        deep_equal(s[key],golden[key],key)
    expected = {k:v for k,v in golden['environment'].items() if k not in ('contact_mapping','probe_runtime_mass')}
    deep_equal(s['environment'],expected,'complete source environment')


def validate_bodies(value, facets, api):
    s={**facets['static'],**value};cfg=api['cfg']
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


def validate_trace(value,facets,api):
    return rows_check(facets['static'],value['rows'],api)


def validate_contact(value,facets,api):
    golden=api['parse'](api['data']['data/golden.json'])['environment']['contact_mapping']
    mapping=value['mapping'];sensors,filters=golden['canonical_sensors'],golden['canonical_filters']
    need(set(mapping)==set(golden),'Complete live contact mapping schema')
    need(mapping['canonical_sensors']==sensors and mapping['canonical_filters']==filters and mapping['capacity']==512 and
         mapping['force_frame']=='WORLD' and mapping['force_units']=='N','Live contact canonical identity/units/capacity')
    need(len(mapping['sensor_paths'])==8 and set(mapping['sensor_paths'])==set(sensors),'All unique actual sensor indices')
    need(len(mapping['filter_paths'])==8 and all(len(row)==9 and set(row)==set(filters) for row in mapping['filter_paths']),'All actual per-sensor filter indices')
    need(value['sensor_count']==8 and value['filter_count']==9 and value['capacity']==512 and
         type(value['engine_event_index']) is int and value['engine_event_index']==10,'Actual view dimensions and final event')
    sample=value['sample'];need(set(sample)=={'normal_force_N','counts','active','dt_s'} and abs(number(sample['dt_s'],'contact dt')-DT)<1e-10,'Actual contact sample schema/dt')
    force,counts=sample['normal_force_N'],sample['counts']
    need(type(force) is list and len(force)==8 and type(counts) is list and len(counts)==8,'Eight contact rows')
    for frow,crow in zip(force,counts):
        need(type(frow) is list and len(frow)==9 and type(crow) is list and len(crow)==9,'Nine contact filters per row')
        for f,c in zip(frow,crow):
            vector(f);need(type(c) is int and 0<=c<512,'Actual contact count range')
    need(type(sample['active']) is list and len(sample['active'])==sum(sum(r) for r in counts)<512,'Complete actual contact buffer')
    tally=[[0]*9 for _ in range(8)]
    for item in sample['active']:
        need(set(item)=={'sensor','filter','force_N','point','normal','separation_m'},'Complete active contact schema')
        i,j=item['sensor'],item['filter'];need(type(i) is int and 0<=i<8 and type(j) is int and 0<=j<9,'Canonical active contact indices')
        need(number(item['force_N'],'force')>=0,'Contact force sign');number(item['separation_m'],'separation');vector(item['point']);vector(item['normal'])
        tally[i][j]+=1
    need(tally==counts,'All active contacts match each canonical count')


VALIDATORS={'static':validate_static,'bodies':validate_bodies,'trace':validate_trace,'contact':validate_contact}


def bindings(api):
    need(set(VALIDATORS)==set(api['contract']['facets']),'Validator obligation coverage')


def observations(packet,api):
    bindings(api)
    need(set(packet)=={'run_id','job_sha256','pid','usd_sha256','facets'},'Closed robot observation envelope')
    need(packet['run_id']==api['run'].name and packet['job_sha256']==sha(api['run']/'job.json') and
         packet['usd_sha256']==api['job']['inputs']['data/model.usda'],'Source robot observation binding')
    facets=packet['facets'];need(type(facets) is dict and set(facets)==set(api['contract']['facets']),'Every source obligation is present')
    metrics={}
    for name in api['contract']['facets']:
        need(type(facets[name]) is dict and set(facets[name])==set(api['contract']['required_fields'][name]),'Complete facet fields '+name)
        metrics[name]=VALIDATORS[name](facets[name],facets,api)
    return metrics


def consume(records,api):
    records=Path(records);run,job,cfg=api['run'],api['job'],api['cfg'];h=sha(run/'job.json')
    terminal,ex=read(records/'terminal.json'),read(records/'exit.json')
    need(job['stage']=='robot_connection' and terminal['stage']=='robot_connection','Scoped robot stage')
    need(terminal['run_id']==ex['run_id']==run.name and terminal['job_sha256']==ex['job_sha256']==h,'Actual run/job identity')
    need(type(terminal['code']) is int and terminal['code']==0 and type(ex['child_exit_code']) is int and ex['child_exit_code']==0,'Worker/process exit failure dominates')
    need(terminal['status'] in ('CLOSED','COMPLETE_PRE_CLOSE') and terminal['phase'] in ('APP_CLOSED','CLOSING_APP') and ex['status']=='FINISHED','Actual complete lifecycle')
    need(type(terminal['pid']) is int and terminal['pid']>0 and terminal['pid']==ex['child_pid']==ex['worker_pid'] and terminal['parent_pid']==ex['pid'],'Actual direct supervisor/worker PID chain')
    need(terminal['hardware_approved'] is False and terminal['physical_calibration'] is False and terminal['training']=='NOT_RUN','No physical/training authority')
    expected={'observations.json','scene.usda','providers.json','sdk.json'}
    need(set(terminal['files_sha256'])==expected,'All actual robot artifacts')
    for name,value in terminal['files_sha256'].items():need(sha(records/name)==value,'Actual raw hash '+name)
    prereq=records/'prerequisite';expected_prereq={'job.json','terminal.json','exit.json','providers.json','sdk.json','reservation.json'}
    need(set(ex['prerequisite_hashes'])==expected_prereq,'Complete parent prerequisite proof')
    for name,value in ex['prerequisite_hashes'].items():need(sha(prereq/name)==value,'Original prerequisite raw bytes')
    old_job,reservation=read(prereq/'job.json'),read(prereq/'reservation.json')
    need(reservation['stage']=='sdk_preflight' and reservation['run_id']==old_job['run_id'] and
         reservation['job_sha256']==sha(prereq/'job.json') and reservation['input_signature']==api['runner'].signature(job),'Prerequisite reservation/source binding')
    api['runner'].sdk_pass(prereq,old_job,reservation['job_sha256'],api['runner'].signature(job),cfg,api['lib']['providers'])
    providers,sdk=read(records/'providers.json'),read(records/'sdk.json')
    need(providers['pid']==sdk['pid']==terminal['pid'] and providers['job_sha256']==sdk['job_sha256']==h,'Same-process module/SDK evidence')
    need(sdk['version']==cfg['isaac_version'] and Path(sdk['isaacsim_origin']).is_relative_to(Path(cfg['isaac_root'])) and
         sdk['bootstrap_sha256']=={k:v['sha256'] for k,v in cfg['sdk_files'].items()},'Actual SDK identity')
    for key in ('numeric_before','numeric_after'):api['lib']['providers'].check_numeric(providers[key],cfg,need)
    framework=providers['frameworks'];versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','warp':'1.17.0','gymnasium':'1.4.0','rsl_rl':'5.5.1'}
    need(set(framework['modules'])==set(versions) and framework['cuda'].startswith('13.') and framework['sum']==6 and framework['device']=='cuda:0','Actual framework/GPU result')
    for name,version in versions.items():
        item=framework['modules'][name];allowed=cfg['warp_root'] if name=='warp' else cfg['installation_prefix']
        need(item['version']==version and Path(item['origin']).is_relative_to(Path(allowed)),'Actual framework provider')
    packet=read(records/'observations.json');need(packet['pid']==terminal['pid'],'Actual robot observer process')
    metrics=observations(packet,api)
    return {'status':'ISAACLAB_ROBOT_CONNECTION_VERIFIED','sdk_connected':True,'run_id':run.name,'steps':10,'samples':11,
            'facets_verified':list(api['contract']['facets']),'metrics':metrics,'mass_inertia':'SIMULATION_ASSUMPTION',
            'physical_calibration':False,'hardware_approved':False,'training':'NOT_RUN','weights':None,'ring_geometry':'DEFERRED','settling':'UNRESOLVED_047'}
