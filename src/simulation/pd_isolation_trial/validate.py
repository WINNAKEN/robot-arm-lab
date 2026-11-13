"""069 canonical-source oracle. Stdlib only; no SDK imports or model writers."""
import hashlib
import itertools
import json
import math
import copy
import types
from pathlib import Path
import struct
import zlib
import xml.etree.ElementTree as ET
from fractions import Fraction


def need(ok, message):
    if not ok:
        raise ValueError(message)

def verify_reference(report):
    try:
        if report['reference'].get('errors'):
            return {'status':'REFERENCE_OBSERVATION_FAILED','faults':report['reference']['errors'],'summary':{},'robot_PD':'NOT_DIRECTLY_MEASURED','combined_PD':'UNKNOWN'}
        return _verify_reference_strict(report)
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        return {'status':'REFERENCE_RECORD_INVALID','faults':[{'error':type(exc).__name__+': '+str(exc)}],'summary':{},'robot_PD':'NOT_DIRECTLY_MEASURED','combined_PD':'UNKNOWN'}

def _verify_reference_strict(report):
    packet=report['reference'];setups={x['mode']:x for x in packet['setup']}
    need(set(setups)=={'force','acceleration'} and len(packet['samples'])==240,'Two references and complete240 observations')
    phases=('external_only','force_PD_only','combined_residual','acceleration_PD_only','free');summary={};faults=[]
    for mode,setup in setups.items():
        need(setup['body_count']==2 and setup['collision_shapes']==0 and len(setup['dof_names'])==1,'Unconnected reference inventory')
        need(setup['tensor_drive_type']==[[1 if mode=='force' else 2]],'Actual fixed drive mode')
        inertia=num(setup['inertia_z']);need(abs(inertia-.2)<=1e-6,'Actual reference inertia')
        need(len(setup['inertias'])==1 and len(setup['inertias'][0])==2,'Actual two-link inertia shape')
        for tensor in setup['inertias'][0]:
            need(len(tensor)==9 and all(abs(num(x)-(.2 if i in (0,4,8) else 0.))<1e-6 for i,x in enumerate(tensor)),'Known isotropic native inertia tensor')
        need(num(setup['inertias'][0][setup['link_names'].index('Rotor')][8])==inertia,'Inertial balance bound to raw rotor tensor')
        need(len(setup['coms'])==1 and len(setup['coms'][0])==2 and all(abs(v)<1e-6 for com in setup['coms'][0] for v in vec(com)),'Actual COM at pivot')
        need(setup['same_owned_lab_view'] is True and len(setup['link_names'])==2 and set(setup['link_names'])=={'Base','Rotor'},'Reference link identity and view')
        need(len(setup['masses'])==1 and all(abs(num(v)-1.)<1e-6 for v in setup['masses'][0]),'Known actual masses')
        need(all(num(v)==0 for matrix in setup['friction'] for row in matrix for v in row) and setup['armature']==[[0.]],'Zero reference friction and armature')
        need(abs(setup['initial_q'])<1e-6 and abs(setup['initial_qd'])<1e-6 and abs(setup['velocity_limit']-10.)<1e-6,'Unmoved reference and wide speed limit')
        summary[mode]={p:[] for p in phases}
    previous={mode:num(x['initial_qd']) for mode,x in setups.items()}
    for step,sample in enumerate(packet['samples'],1):
        before=sample['clock_before_step'];after=sample['clock_after_step'];need(after==sample['clock_after_read'] and after['lab_step']==before['lab_step']+1 and abs(after['engine_time_s']-before['engine_time_s']-1/120)<1e-10,'One actual reference step, stable read')
        need(before==report['observations'][step-1]['clock_after'] and after==report['observations'][step]['clock_after'],'Reference step bound to exact robot state clock')
        need(len(sample['rows'])==2 and {x['mode'] for x in sample['rows']}==set(setups),'Exactly two reference rows')
        p=phases[(step-1)//48]
        for row in sample['rows']:
            mode=row['mode'];need(row['step']==step and row['command']['phase']==p,'Boundary step command phase')
            need(num(row['before_qd'])==previous[mode],'Reference velocity chain has exact previous endpoint')
            need(sum(x=={k:row[k] for k in ('mode','step','command','before_qd')} for x in sample['issued'])==1,'Same actual issued command bound to observed row')
            active=(mode=='force' and p in phases[1:3]) or (mode=='acceleration' and p==phases[3])
            expected_external=.02 if p==phases[0] or (mode=='force' and p==phases[2]) else 0.
            need(row['command']=={'phase':p,'kp':64. if active else 0.,'kd':16. if active else 0.,'target':.2,'external':expected_external,'cap':.01},'Independent reference command reconstruction')
            need(row['kp_readback']==(64. if active else 0.) and row['kd_readback']==(16. if active else 0.) and abs(row['cap_readback']-.01)<1e-8 and abs(row['external_readback']-expected_external)<1e-8,'Actual reference command readbacks')
            velocity=num(row['after_qd']);position=num(row['after_q']);need(abs(velocity)<9 and abs(position)<10,'Reference limits inactive')
            previous[mode]=velocity
            balance=num(setups[mode]['inertia_z'])*(velocity-num(row['before_qd']))*120;measured=num(row['projected']);tolerance=1e-4+.01*max(abs(balance),abs(measured))
            need(len(row['incoming_force'])==len(row['incoming_torque'])==1 and len(row['incoming_force'][0])==len(row['incoming_torque'][0])==2,'Reference incoming6D shape')
            for force,moment in zip(row['incoming_force'][0],row['incoming_torque'][0]):vec(force);vec(moment)
            rotor=setups[mode]['link_names'].index('Rotor');need(abs(measured-row['incoming_torque'][0][rotor][2])<=1e-3+1e-4*abs(measured),'Reference incoming active-axis coherence')
            if abs(balance-measured)>tolerance:faults.append({'step':step,'mode':mode,'kind':'PROJECTED_VS_INERTIAL_BALANCE','balance_Nm':balance,'projected_Nm':measured})
            if not active and abs(balance-expected_external)>1e-4+.01*abs(expected_external):faults.append({'step':step,'mode':mode,'kind':'EXTERNAL_OR_FREE_BALANCE'})
            pure=active and expected_external==0
            if pure and abs(balance)>.01+1e-4+.01*.01:faults.append({'step':step,'mode':mode,'kind':'PD_ONLY_EXCEEDS_CAP','actual_PD_Nm':balance})
            if mode=='force' and p=='combined_residual' and abs(balance-.03)>1e-4+.01*.03:faults.append({'step':step,'mode':mode,'kind':'COMBINED_ADDITIVITY_UNCONFIRMED','balance_Nm':balance})
            # Combined remains a residual even when it matches a simple additive hypothesis.
            summary[mode][p].append({'step':step,'total_inertial_Nm':balance,'PD_only_Nm':balance if pure else None,'conditional_residual_Nm':balance-row['external_readback'],'projected_Nm':measured,'reference_PD_only_near_cap':pure and abs(abs(balance)-.01)<=.0002})
    for mode,p in (('force','force_PD_only'),('acceleration','acceleration_PD_only')):
        if not any(abs(x['PD_only_Nm'])>1e-4 for x in summary[mode][p]):faults.append({'mode':mode,'kind':'PD_ONLY_SIGNAL_MISSING'})
    return {'status':'REFERENCE_SEMANTICS_VERIFIED' if not faults else 'MEASUREMENT_SEMANTICS_UNRESOLVED','faults':faults,'summary':summary,'robot_PD':'NOT_DIRECTLY_MEASURED','combined_PD':'UNKNOWN_EXTERNAL_CONTRIBUTION_NOT_INDEPENDENTLY_IDENTIFIED','scope':'PD-only inertial reference measurement, not robot force calibration'}


def num(x):
    need(type(x) in (int, float) and math.isfinite(x), 'finite non-bool number')
    return float(x)


def vec(x, n=3):
    need(type(x) is list and len(x) == n, 'vector shape')
    return [num(v) for v in x]


def near(a, b, tol=5e-5):
    if isinstance(b, dict):
        need(type(a) is dict and set(a) == set(b), 'exact object fields')
        for k in b:
            near(a[k], b[k], tol)
    elif isinstance(b, (list, tuple)):
        need(type(a) in (list, tuple) and len(a) == len(b), 'exact array shape')
        for x, y in zip(a, b):
            near(x, y, tol)
    elif type(b) in (int, float):
        need(abs(num(a) - b) <= tol, 'numeric canonical mismatch')
    else:
        need(type(a) is type(b) and a == b, 'typed identity mismatch')


I = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
def tr(a): return [list(x) for x in zip(*a)]
def mv(a, x): return [sum(u*v for u, v in zip(r, x)) for r in a]
def mm(a, b): return [[sum(u*v for u, v in zip(r, c)) for c in zip(*b)] for r in a]
def add(a, b): return [x+y for x, y in zip(a, b)]
def sub(a, b): return [x-y for x, y in zip(a, b)]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def tf(a, b): return add(a[0], mv(a[1], b[0])), mm(a[1], b[1])


def rpy(v):
    r, p, y = v
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr], [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]


def quat(v):
    w, x, y, z = vec(v, 4)
    need(abs(w*w+x*x+y*y+z*z-1) < 1e-3, 'unit quaternion')
    s = 2/(w*w+x*x+y*y+z*z)
    return [[1-s*(y*y+z*z), s*(x*y-z*w), s*(x*z+y*w)], [s*(x*y+z*w), 1-s*(x*x+z*z), s*(y*z-x*w)], [s*(x*z-y*w), s*(y*z+x*w), 1-s*(x*x+y*y)]]


def axis_rot(a, t):
    c, s = math.cos(t), math.sin(t)
    return [[c*(i == j)+(1-c)*a[i]*a[j]+s*sum((1 if (i,j,k) in ((1,0,2),(2,1,0),(0,2,1)) else -1 if (i,j,k) in ((0,1,2),(1,2,0),(2,0,1)) else 0)*a[k] for k in range(3)) for j in range(3)] for i in range(3)]


def floats(s, n=3):
    a = [float(x) for x in s.split()]
    need(len(a) == n and all(math.isfinite(x) for x in a), 'XML numeric field')
    return a


def origin(e):
    o = e.find('origin')
    return ([0., 0., 0.], I) if o is None else (floats(o.get('xyz', '0 0 0')), rpy(floats(o.get('rpy', '0 0 0'))))


def pmodel(path):
    path = Path(path); root = ET.parse(path).getroot(); links = {}; joints = {}
    need(root.tag == 'robot', 'canonical robot XML')
    for e in root.findall('link'):
        name = e.attrib['name']; need(name not in links, 'duplicate link')
        item = {'mass': None, 'com': [0.]*3, 'inertia': [[0.]*3 for _ in range(3)], 'inertial_R': I, 'collision': None, 'visual': None}
        n = e.find('inertial')
        if n is not None:
            item['mass'] = num(float(n.find('mass').attrib['value'])); item['com'], R = origin(n); item['inertial_R'] = R
            a = n.find('inertia').attrib; T = [[float(a['ixx']),float(a['ixy']),float(a['ixz'])],[float(a['ixy']),float(a['iyy']),float(a['iyz'])],[float(a['ixz']),float(a['iyz']),float(a['izz'])]]
            item['inertia'] = mm(mm(R, T), tr(R)); need(item['mass'] > 0 and all(T[i][i] > 0 for i in range(3)), 'positive assumed inertia')
        v = e.find('visual')
        if v is not None:
            m = v.find('geometry/mesh'); need(m is not None, 'canonical visual mesh')
            rel = m.attrib['filename']; need(not Path(rel).is_absolute() and '..' not in Path(rel).parts, 'safe mesh URI')
            item['visual'] = {'meshrel': rel, 'origin': origin(v), 'scale': floats(m.get('scale','1 1 1'))}
        c = e.findall('collision'); need(len(c) <= 1, 'one canonical collider per physical link')
        if c:
            box = c[0].find('geometry/box'); need(box is not None, 'canonical box collider')
            item['collision'] = {'origin': origin(c[0]), 'size': floats(box.attrib['size'])}
        links[name] = item
    for e in root.findall('joint'):
        name = e.attrib['name']; need(name not in joints, 'duplicate joint')
        axis = e.find('axis'); limit = e.find('limit'); mimic = e.find('mimic')
        joints[name] = {'type': e.attrib['type'], 'parent': e.find('parent').attrib['link'], 'child': e.find('child').attrib['link'], 'origin': origin(e), 'axis': floats(axis.get('xyz')) if axis is not None else [0.,0.,1.], 'mimic': None if mimic is None else {'joint':mimic.attrib['joint'],'multiplier':float(mimic.get('multiplier','1')),'offset':float(mimic.get('offset','0'))}}
        for key in ('lower','upper','effort','velocity'):
            joints[name][key] = float(limit.attrib[key]) if limit is not None else None
    movable = [n for n,j in joints.items() if j['type'] != 'fixed']; roots = set(links)-{j['child'] for j in joints.values()}
    need(len(roots) == 1 and set(movable) == {*(f'J{i}' for i in range(1,7)), 'KG1_slide_A','KG1_slide_B','KG1_pinion'}, 'canonical articulated joint inventory')
    need(len(links)==12 and len(joints)==11 and sum(x['mass'] is not None for x in links.values())==11, 'canonical complete physical census')
    return {'links':links,'joints':joints,'movable':movable,'root':next(iter(roots)),'robot_name':root.attrib['name'],'path':str(path)}


def fk(model, q):
    poses = {model['root']:([0.,0.,0.],I)}; todo = dict(model['joints']); qs = dict(q)
    def coordinate(n, seen=()):
        need(n not in seen, 'no mimic cycle')
        if n in qs: return num(qs[n])
        m = model['joints'][n]['mimic']
        return 0. if m is None else m['multiplier']*coordinate(m['joint'],(*seen,n))+m['offset']
    while todo:
        progressed = False
        for name,j in list(todo.items()):
            if j['parent'] not in poses: continue
            amount = coordinate(name); motion = ([0.]*3,I)
            if j['type']=='revolute': motion=([0.]*3,axis_rot(j['axis'],amount))
            elif j['type']=='prismatic': motion=([amount*x for x in j['axis']],I)
            else: need(j['type']=='fixed','supported joint type')
            poses[j['child']]=tf(tf(poses[j['parent']],j['origin']),motion); del todo[name]; progressed=True
        need(progressed,'acyclic connected joint tree')
    return poses


def box_corners(spec):
    return [add(spec['origin'][0],mv(spec['origin'][1],[s*d/2 for s,d in zip(sign,spec['size'])])) for sign in itertools.product((-1.,1.),repeat=3)]


def same_points(actual, expected, tol=2e-6):
    need(type(actual) is list and len(actual)==len(expected),'complete shape corner set')
    remaining=[vec(p) for p in actual]
    for p in expected:
        index=next((i for i,x in enumerate(remaining) if max(abs(a-b) for a,b in zip(x,p))<=tol),None)
        need(index is not None,'canonical collider point mismatch');remaining.pop(index)


_BOUNDS_CACHE={}

def mesh_bounds(model, name, pose):
    v=model['links'][name]['visual']; data=(Path(model['path']).parent/v['meshrel']).read_bytes(); need(len(data)>=84,'binary STL')
    key=(hashlib.sha256(data).hexdigest(),json.dumps([v,pose],sort_keys=True));
    if key in _BOUNDS_CACHE:return json.loads(_BOUNDS_CACHE[key])
    count=struct.unpack_from('<I',data,80)[0]; need(len(data)==84+50*count and count>0,'complete actual STL')
    lo=[math.inf]*3; hi=[-math.inf]*3; local=tf(pose,v['origin'])
    for i in range(count):
        xyz=struct.unpack_from('<9f',data,84+50*i+12)
        for k in (0,3,6):
            p=add(local[0],mv(local[1],[xyz[k+a]*v['scale'][a] for a in range(3)]))
            lo=[min(a,b) for a,b in zip(lo,p)];hi=[max(a,b) for a,b in zip(hi,p)]
    result={'min':lo,'max':hi};_BOUNDS_CACHE[key]=json.dumps(result);return result


def check_body(model, b, expected_pose, visual=True):
    m=model['links'][b['name']];near(b['position'],expected_pose[0]);near(b['rotation'],expected_pose[1]);near(b['mass'],m['mass'],2e-6);near(b['com'],m['com'],2e-6)
    R=quat(b['principal_axes_wxyz']);di=vec(b['inertia_diag']); tensor=mm(mm(R,[[di[i] if i==j else 0. for j in range(3)] for i in range(3)]),tr(R));near(tensor,m['inertia'],3e-8)
    need(b['mass_api_applied'] is True and b['visual_point_count']>0 and b['visual_meshes'],'authored body and actual visual')
    if visual: near(b['visual_bounds'],mesh_bounds(model,b['name'],expected_pose),2e-5)


def check_colliders(model, packet, poses, cfg, floor=False):
    physical={n for n,x in model['links'].items() if x['mass'] is not None};rows=packet['colliders'];expected=physical|({'__floor__'} if floor else set())
    need(len(rows)==len(expected) and {r['owner'] for r in rows}==expected,'all source colliders including floor')
    for r in rows:
        need(r['enabled'] is True and r['shape'] in ('Cube','Mesh'),'actual enabled box representation')
        need(r['filtered_pairs']==[],'no unauthorised collider pair filtering')
        if r['owner']=='__floor__':
            f=cfg['floor'];need(r['path']==f['path'] and r['static'] is True,'source static floor identity')
            corners=[[f['position'][i]+s[i]*f['scale'][i]*f['size']/2 for i in range(3)] for s in itertools.product((-1.,1.),repeat=3)];same_points(r['corners_world'],corners)
        else:
            need(r['owner'] in physical and r['static'] is False,'physical collider owner');expected_local=box_corners(model['links'][r['owner']]['collision']);same_points(r['corners_link'],expected_local)
            p,R=poses[r['owner']];same_points(r['corners_world'],[add(p,mv(R,x)) for x in expected_local],5e-5)
    need(packet['self_collision'] is False,'explicit selfcollision OFF for AABB proxies')


WORLD_ROLE_KEYS={'path','exists','type','applied_schemas','active','defined','rigid_body','mass_api','world_matrix','matrix_convention','time_samples','xform_time_samples'}
I4=[[float(i==j) for j in range(4)] for i in range(4)]


def static_world_role(row, path, root=False):
    need(type(row) is dict and set(row)==WORLD_ROLE_KEYS|({'ancestors'} if root else set()),'closed actual world-role fields')
    need(row['path']==path and row['exists'] is True and row['active'] is True and row['defined'] is True,'existing active defined world target')
    need(row['type']=='Xform' if root else row['type'] in ('Xform','Scope'),'supported static world prim type')
    need(row['rigid_body'] is False and row['mass_api'] is False,'world target cannot be a physical body')
    schemas=row['applied_schemas'];need(type(schemas) is list and all(type(x) is str and x for x in schemas) and len(schemas)==len(set(schemas)),'actual API inventory')
    need(not any('RigidBodyAPI' in x or 'MassAPI' in x for x in schemas),'world API inventory agrees with nonphysical role')
    need(row['matrix_convention']=='GfMatrix4d_ROW_VECTOR_ROWS','actual full matrix convention');near(row['world_matrix'],I4,1e-8)
    samples=row['xform_time_samples'];need(type(samples) is dict and all(type(k) is str and (k=='xformOpOrder' or k.startswith('xformOp:')) for k in samples),'actual transform attribute time samples')
    need(all(type(v) is list and all(type(t) in (int,float) and math.isfinite(t) for t in v) for v in samples.values()),'finite sampled transform times')
    need(type(row['time_samples']) is int and row['time_samples']==sum(len(v) for v in samples.values())==0,'supported world frame is time invariant')


def world_endpoint(model, packet, bypath, world):
    anchors=packet['world_anchors'];need(type(anchors) is dict,'actual world-anchor mapping')
    target=world['body0']
    if target is None:
        need(not anchors,'None-world has no invented target role');return ([0.]*3,I)
    need(type(target) is str and world['name']=='root_joint','exact explicit importer root constraint')
    roots=('/'+model['robot_name'],'/World/Robot');need(target in roots,'only the two pinned robot-root layouts')
    base=next(b['path'] for b in packet['bodies'] if b['name']==model['root'])
    need(base==target+'/Geometry/'+model['root'] and target not in bypath,'explicit target is exact nonbody root of canonical Base')
    expected_default=target if target==roots[0] else '/World'
    need(packet['default_prim']==expected_default and packet['root_placement']['path']==expected_default,'actual import/reference default-root layout')
    near(packet['root_placement']['position'],[0.]*3,1e-8);near(packet['root_placement']['rotation'],I,1e-8)
    need(set(anchors)=={target},'no missing or extra world-anchor observations');role=anchors[target];static_world_role(role,target,True)
    parts=target.strip('/').split('/');expected=['/'+ '/'.join(parts[:i]) for i in range(len(parts)-1,0,-1)]
    ancestors=role['ancestors'];need(type(ancestors) is list and len(ancestors)==len(expected),'complete ancestor chain excluding pseudo-root')
    for row,path in zip(ancestors,expected):static_world_role(row,path)
    matrix=role['world_matrix']
    return (matrix[3][:3],[[matrix[j][i] for j in range(3)] for i in range(3)])


def verify_import(model_path, packet, cfg):
    if isinstance(packet,(str,Path)):
        from driver import read
        packet_path=Path(packet);packet=read(packet_path)
        raw=read(packet_path.parent/'raw-static.json')
        need(packet['usd_sha256']==hashlib.sha256((packet_path.parent/'model.usda').read_bytes()).hexdigest(),'snapshot bound to actual normalized USD bytes')
        need(raw['usd_sha256']==hashlib.sha256((packet_path.parent/'raw-import.usda').read_bytes()).hexdigest(),'raw snapshot bound to actual original USD bytes')
        near(packet['bodies'],[b for b in raw['bodies'] if b['name']!='tool0'],0.)
        near(packet['joints'],[j for j in raw['joints'] if j['name']!='tool0_mount'],0.)
        near(packet['colliders'],raw['colliders'],0.)
        near(packet['world_anchors'],raw['world_anchors'],0.)
        need(packet['normalization']['canonical_empty'] is True,'recorded empty-frame-only normalization')
    model=pmodel(model_path);poses=fk(model,{});physical={n for n,x in model['links'].items() if x['mass'] is not None};bodies=packet['bodies']
    need(packet['timeline_stopped'] is True,'static saved USD only');near(packet['units']['meters_per_unit'],1.,0);near(packet['units']['kilograms_per_unit'],1.,0);need(packet['units']['up_axis']=='Z','Z up')
    need(len(bodies)==11 and {b['name'] for b in bodies}==physical,'exact 11 physical source bodies')
    bypath={b['path']:b['name'] for b in bodies}
    for b in bodies:check_body(model,b,poses[b['name']])
    canonical={n:j for n,j in model['joints'].items() if j['child']!='tool0'};actual={j['name']:j for j in packet['joints'] if j['name'] in canonical};world=[j for j in packet['joints'] if j['name'] not in canonical]
    need(set(actual)==set(canonical) and len(packet['joints'])==len(canonical)+1 and len(world)==1,'canonical movable/fixed plus one world base constraint')
    need(all(j.get('enabled') is True for j in packet['joints']),'all source and world constraints are enabled')
    for name,j in canonical.items():
        a=actual[name];need(a['type']==j['type'] and bypath[a['body0']]==j['parent'] and bypath[a['body1']]==j['child'],'canonical joint topology/type')
        w0=tf(poses[j['parent']],(vec(a['local_pos0']),quat(a['local_rot0_wxyz'])));w1=tf(poses[j['child']],(vec(a['local_pos1']),quat(a['local_rot1_wxyz'])));near(w0,w1)
        expected=tf(poses[j['parent']],j['origin']);near(w0[0],expected[0]);near(w1[0],expected[0])
        if j['type']!='fixed':
            near(mv(w0[1],[float(a['axis']==s) for s in 'XYZ']),mv(expected[1],j['axis']))
            scale=math.pi/180 if j['type']=='revolute' else 1.;near(num(a['lower_limit'])*scale,j['lower'],2e-6);near(num(a['upper_limit'])*scale,j['upper'],2e-6)
    w=world[0];need(w['type']=='fixed' and bypath[w['body1']]==model['root'],'world fixed base topology');frame=world_endpoint(model,packet,bypath,w);near(tf(frame,(vec(w['local_pos0']),quat(w['local_rot0_wxyz']))),tf(poses[model['root']],(vec(w['local_pos1']),quat(w['local_rot1_wxyz']))))
    tool=packet['tool0'];need(tool['parent_name']=='KG1' and tool['rigid_body'] is False and tool['mass_api'] is False,'empty frame stays nonphysical');near(tool['position'],poses['tool0'][0]);near(tool['rotation'],poses['tool0'][1])
    check_colliders(model,packet,poses,cfg)
    return {'bodies':11,'source_joints':11,'runtime_constraints':11,'movable':9,'colliders':11,'assumed_mass_kg':sum(x['mass'] or 0 for x in model['links'].values()),'status':'CANONICAL_IMPORT_VERIFIED'}


def check_runtime_inertias(model, rows):
    physical={n for n,x in model['links'].items() if x['mass'] is not None};need(len(rows)==11 and {r['name'] for r in rows}==physical,'all runtime inertial bodies')
    for row in rows:
        m=model['links'][row['name']];near(row['mass'],m['mass'],2e-6);near(row['com'],m['com'],2e-6);R=quat(row['principal_axes_wxyz']);near(row['inertia_link_about_com'],m['inertia'],3e-8)
        need(row['mass_shape']==[1,1] and row['com_shape']==[1,3] and row['principal_axes_shape']==[1,4] and row['inertia_shape']==[1,9] and row['order']=='F','actual tensor shapes and declared full matrix order')
        raw=vec(row['raw_inertia'],9);near([[raw[3*j+i] for j in range(3)] for i in range(3)],row['inertia_link_about_com'],0.)
        principal=mm(mm(tr(R),m['inertia']),R)
        need(max(abs(principal[i][j]) for i in range(3) for j in range(3) if i!=j)<=3e-8,'actual principal axes diagonalize canonical full tensor')


def check_binding(value, static, cfg):
    need(value['device']=='cpu' and value['lab_manager']=='isaaclab_physx.physics.physx_manager.PhysxManager','recorded real Lab manager')
    need(set(value['sources'])==set(cfg['physics_pins']),'full installed physics source set')
    for name,row in value['sources'].items():need(row['sha256']==cfg['physics_pins'][name] and Path(row['origin']).is_absolute(),'pinned actual physics module')
    references=('isaacsim.core.experimental.prims.impl.articulation','isaacsim.core.experimental.prims.impl.rigid_prim','isaacsim.core.experimental.prims.impl.prim')
    need(set(value['references'])==set(references),'three SDK owner references');vid=value['lab_view_id'];need(type(vid) is int and vid>0,'actual Lab view identity')
    owners=value['owners'];ids={x['id'] for x in owners};need(1<=len(owners)<=3 and len(ids)==len(owners) and set(value['references'].values())==ids,'actual unique owners')
    callbacks={'warm_start','on_stop','stage_open','stage_close','post_warm_start'}
    for row in owners:
        need(type(row['id']) is int and row['id']>0 and row['module']=='isaacsim.core.simulation_manager.impl.simulation_manager','pinned actual owner')
        need(row['before_view_id'] in (None,vid) and row['after_view_id']==vid and row['device']=='cpu' and row['engine']=='physx','same real physics view/device')
        need(set(row['callbacks'])==callbacks and all(type(x) is bool and not x for x in row['callbacks'].values()),'complete inactive callbacks')
    expected={('RigidPrim',b['path']) for b in static['bodies']}|{('Articulation',static['articulation_path'])};prims=value['consumers']
    need(len(prims)==12 and {(p['type'],p['paths'][0]) for p in prims if len(p['paths'])==1}==expected,'exact canonical consumers')
    for p in prims:
        mod=references[0] if p['type']=='Articulation' else references[1]
        need(p['module']==mod and p['manager_id']==value['references'][mod] and p['view_id']==vid and p['valid'] is True,'actual consumer readiness')


def check_generation(m):
    for n in ('rgb','reference','dispatcher'):
        a,b=m['before'][n],m['after'][n]
        need(a['path']==b['path'] and a['type']==b['type'] and a['id']==b['id'],'same observed graph node')
        need(type(a['id']) is int and a['id']>0 and a['path'] and a['type'] and a['id_kind']==b['id_kind']=='PYTHON_WRAPPER','explicit wrapper identity')
        need(type(a['compute_count']) is int and type(b['compute_count']) is int and 0<=a['compute_count']<b['compute_count'],'each native node completed a fresh compute')
    def rational(x):
        need(type(x) is list and len(x)==2 and all(type(v) is int for v in x) and x[1]>0,'actual rational render time')
        return Fraction(x[0],x[1])
    binary=float(rational(m['scheduled_source_raw']));need(num(m['source_engine_time_s'])==binary and binary>=0 and m['scheduled_binary64_hex']==binary.hex() and m['quantization_rule']=='FLOAT64_RATIONAL_MULTIPLY_1E9_TRUNCATE','Actual binary64 render clock contract')
    near(m['scheduled'],[int(binary*1_000_000_000),1_000_000_000],0.)
    need(rational(m['scheduled'])<=rational(m['dispatcher_reference'])==rational(m['render_product_reference']),'completed scheduled frame on same RP')
    need(type(m['render_product']) is str and m['render_product'].startswith('/'),'explicit render product path')
    text=m.get('renderer_log','').lower();need(not any(s in text for s in ('renderer failed to advance','failed to schedule','step scheduling failed')),'no renderer soft failure')


def gravity(model, poses, masses=None):
    if type(poses) is list:poses={r['name']:(vec(r['position']),quat(r['orientation_wxyz'])) for r in poses}
    props={r['name']:r for r in masses} if masses is not None else model['links'];result={}
    def descendant(link, ancestor):
        while link!=model['root']:
            if link==ancestor:return True
            link=next(j['parent'] for j in model['joints'].values() if j['child']==link)
        return link==ancestor
    for name in model['movable']:
        j=model['joints'][name];anchor, R=tf(poses[j['parent']],j['origin']);axis=mv(R,j['axis']);value=0.
        for n,p in props.items():
            if p['mass'] is None or not descendant(n,j['child']):continue
            point=add(poses[n][0],mv(poses[n][1],p['com']));f=[0.,0.,-9.81*p['mass']];moment=f if j['type']=='prismatic' else cross(sub(point,anchor),f);value-=sum(a*b for a,b in zip(axis,moment))
        result[name]=value
    return result


def target(t, program):
    before={f'J{i}':0. for i in range(1,7)};opening=.04;start=0.
    for segment in program['segments']:
        end=start+segment['duration_s'];after={**before,**segment.get('arm',{})};gap=segment.get('opening_m',opening)
        if t<=end+1e-9:
            x=max(0.,min(1.,(t-start)/segment['duration_s']));h=x*x*x*(10+x*(-15+6*x));q={n:before[n]+h*(after[n]-before[n]) for n in before};d=(opening+h*(gap-opening))/2-.02;q.update(KG1_slide_A=d,KG1_slide_B=d,KG1_pinion=-d/.0135);return q,segment['name']
        before,opening,start=after,gap,end
    raise ValueError('time beyond program')


def reference_velocity(t, program):
    previous={f'J{i}':0. for i in range(1,7)};opening=.04;elapsed=0.
    for phase in program['segments']:
        duration=phase['duration_s'];end=elapsed+duration;following={**previous,**phase.get('arm',{})};gap=phase.get('opening_m',opening)
        if t<=end+1e-9:
            x=max(0.,min(1.,(t-elapsed)/duration));slope=30*x*x*(x-1)*(x-1)/duration
            result={n:(following[n]-previous[n])*slope for n in previous};jaw=(gap-opening)*slope/2.
            result.update(KG1_slide_A=jaw,KG1_slide_B=jaw,KG1_pinion=-jaw/.0135)
            return result,{n:struct.unpack('<f',struct.pack('<f',value))[0] for n,value in result.items()}
        previous,opening,elapsed=following,gap,end
    raise ValueError('velocity reference beyond program')


def check_velocity_configuration(row, program, model):
    reference,encoded=reference_velocity(num(row['time_s']),program)
    need(set(reference)==set(model['movable']),'Nine canonical velocity coordinates')
    near(row['reference_velocity'],reference,1e-12);near(row['velocity_targets'],encoded,0.)
    near(row['configuration']['velocity_targets'],encoded,1e-8)
    need(all(abs(value)<=model['joints'][n]['velocity'] for n,value in encoded.items()),'Original velocity command bounds')


def checked_force_arrays(raw):
    need(type(raw) is dict and set(raw)=={'command','projected','force','torque'},'Closed force channel objects')
    need(all(type(raw[n]) is list and len(raw[n])==1 for n in raw),'Single force articulation')
    command=vec(raw['command'][0],9);projected=vec(raw['projected'][0],9)
    need(len(raw['force'][0])==len(raw['torque'][0])==11,'Full incoming6D links')
    force=[vec(x) for x in raw['force'][0]];moment=[vec(x) for x in raw['torque'][0]]
    return command,projected,force,moment


def check_torque_observation(row, report, model):
    obs=row['torque_observation'];step=row['step'];need(type(obs['sample_step']) is int and obs['sample_step']==step,'Force sample index')
    if step==0:
        need(obs=={'available':False,'sample_step':0,'reason':'NO_COMPLETED_POSITIVE_STEP','clock':row['clock_after']},'No fabricated step0 force');return
    need(obs['available'] is True,'Positive solver force observation')
    near(obs['clock_before'],row['clock_after'],0.);near(obs['clock_after'],row['clock_after'],0.)
    binding=report['torque_binding'];names=binding['dof_names'];links=binding['link_names']
    need(names==report['dof_names'] and links==row['configuration']['link_names'],'Actual force native names')
    need(len(names)==9 and len(set(names))==9 and set(names)==set(model['movable']) and len(links)==11 and len(set(links))==11,'Force inventories')
    command,projected,force,moment=checked_force_arrays(obs['raw'])
    joints={j['name']:j for j in report['static']['joints']}
    for n in model['movable']:
        joint=joints[n];child=model['joints'][n]['child'];axis={'X':0,'Y':1,'Z':2}[joint['axis']];kind=model['joints'][n]['type'];di=names.index(n);li=links.index(child)
        need(joint['body1'].split('/')[-1]==child,'Observed child joint force frame')
        expected_binding={'dof_index':di,'link_index':li,'axis':joint['axis'],'child':child,'kind':kind,'unit':'N' if kind=='prismatic' else 'N*m'}
        need(binding['mapping'][n]==expected_binding,'Canonical force mapping')
        value=(force if kind=='prismatic' else moment)[li][axis];measured=projected[di]
        need(abs(measured-value)<=1e-3+1e-4*max(abs(value),abs(measured)),'Incoming6D/projected internal coherence')
        expected=struct.unpack('<f',struct.pack('<f',row['ff']['native'][n]))[0];near(command[di],expected,1e-8)
    need(obs['semantics']=={'command':'EXTERNAL_COMMAND_NOT_MEASURED_DRIVE','projected':'NET_ACTIVE_JOINT_EFFORT_NOT_ISOLATED_PD','incoming':'CHILD_JOINT_FRAME_6D'},'No force semantic promotion')


def png_header(data, cfg):
    need(data[:8]==b'\x89PNG\r\n\x1a\n','actual PNG signature');pos=8;ihdr=None;payload=b'';ended=False
    while pos<len(data):
        need(pos+12<=len(data),'complete PNG chunk');size=struct.unpack_from('>I',data,pos)[0];kind=data[pos+4:pos+8];body=data[pos+8:pos+8+size];need(pos+12+size<=len(data),'complete PNG payload')
        need(zlib.crc32(kind+body)&0xffffffff==struct.unpack_from('>I',data,pos+8+size)[0],'actual PNG chunk CRC');pos+=size+12
        if kind==b'IHDR':need(ihdr is None and size==13,'unique PNG IHDR');ihdr=struct.unpack('>IIBBBBB',body)
        if kind==b'IDAT':payload+=body
        if kind==b'IEND':need(size==0 and pos==len(data),'final PNG IEND');ended=True;break
    need(ended and ihdr in ((cfg['width'],cfg['height'],8,2,0,0,0),(cfg['width'],cfg['height'],8,6,0,0,0)),'native RGB/RGBA8 configured image dimensions')
    channels=3 if ihdr[3]==2 else 4
    raw=zlib.decompress(payload);need(len(raw)==cfg['height']*(cfg['width']*channels+1),'decoded image scanline size')
    need(channels==4 and all(raw[y*(cfg['width']*4+1)]==0 for y in range(cfg['height'])),'native RGBA8 filter-zero rows')
    rgba=b''.join(raw[y*(cfg['width']*4+1)+1:(y+1)*(cfg['width']*4+1)] for y in range(cfg['height']))
    need(len(set(rgba[0::4]))>1 or len(set(rgba[1::4]))>1 or len(set(rgba[2::4]))>1,'nonblank actual pixels')
    return hashlib.sha256(rgba).hexdigest()


def verify_workspace(model_path):
    base=Path(model_path).parent.parent
    def module(path):
        m=types.ModuleType('_workspace_math_'+path.stem);m.__file__=str(path)
        exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m
    generator=module(base/'source/workspace.py');oracle=module(base/'ref/sampling-oracle.py')
    data=json.loads((base/'ref/workspace.json').read_text(encoding='utf-8'))
    metrics=generator.validate_result(data,oracle.pmodel(model_path),oracle,full=True)
    near(data['program'],json.loads((base/'source/program.json').read_text(encoding='utf-8')),0.)
    return data,metrics


def check_ff(model, ff, previous, inertias):
    names=model['movable'];shape=ff['shape']
    need(type(shape) is list and len(shape)==2 and all(type(v) is int for v in shape) and shape[0]==1 and shape[1] in (9,15),'actual native gravity shape')
    values=vec(ff['full'],shape[1]);dofs=ff['names'];need(len(dofs)==9 and len(set(dofs))==9 and set(dofs)==set(names),'actual complete unique DOF mapping')
    columns={n:shape[1]-9+dofs.index(n) for n in names};near(ff['columns'],columns,0.)
    native={n:values[columns[n]] for n in names};near(ff['native'],native,0.)
    near(ff['query_before'],previous['clock_after'],0.);near(ff['query_after'],previous['clock_after'],0.)
    reference=gravity(model,previous['body_poses'],inertias);near(ff['expected'],reference,1e-8);near(native,reference,1e-3)
    return native


def gravity_margin(model, efforts, program, phase):
    need(set(efforts)==set(model['movable']),'complete actual gravity ratio mapping')
    phase_names=[s['name'] for s in program['segments']];need(phase in phase_names,'known source load phase')
    ratio=max(abs(num(efforts[n]))/model['joints'][n]['effort'] for n in model['movable'])
    limit=.95 if phase_names.index(phase)<=1 else .8
    return ratio,limit,ratio<=limit+1e-6


def large_motion_check(rows, frames, model, purpose):
    names=['J'+str(i) for i in range(1,7)]
    excursions={n:max(r['q'][n] for r in rows)-min(r['q'][n] for r in rows) for n in names}
    initial_excursion=max(abs(r['q']['J2']-rows[0]['q']['J2']) for r in rows)
    tcp=[rows[f['state_index']]['actual_tcp']['position'] for f in frames]
    diameter=max(math.dist(a,b) for a in tcp for b in tcp)
    passed=purpose!='motion' or all(excursions[n]>=math.radians(d) for n,d in {'J1':100,'J3':40,'J6':100}.items()) and initial_excursion>=math.radians(30) and diameter>=.3
    return {'joint_excursion_rad':excursions,'J2_excursion_from_initial_rad':initial_excursion,'tcp_diameter_m':diameter,'large_motion_pass':passed}


def check_cloud_camera(data, report, source_program):
    cloud=report['workspace_cloud'];indices=data['cloud']['render_indices']
    need(cloud['visibility']=='invisible','User-requested fog hidden')
    need(cloud['path']=='/World/SampledWorkspace' and cloud['kind']=='UsdGeom.PointInstancer' and cloud['physics'] is False,'native nonphysical workspace identity')
    near(cloud['render_indices'],indices,0.);near(cloud['positions'],[data['cloud']['voxels'][i]['position'] for i in indices],1e-6)
    near(cloud['opacity'],.08,1e-6);near(cloud['sphere_radius_m'],.01,1e-8)
    roles=cloud['prim_roles'];need(len(roles)>=4 and len({r['path'] for r in roles})==len(roles),'actual cloud prim inventory')
    for row in roles:
        need(row['path'].startswith('/World/SampledWorkspace') and all(row[k] is False for k in ('rigid_body','mass_api','collision')),'cloud never changes physics')
        need(not any(any(x in s for x in ('RigidBodyAPI','MassAPI','CollisionAPI')) for s in row['applied_schemas']),'cloud physics schema inventory')
    camera=report['camera'];a,b=data['cloud']['bbox'],data['planned_body_bounds']
    envelope={'min':[min(a['min'][i],b['min'][i]) for i in range(3)],'max':[max(a['max'][i],b['max'][i]) for i in range(3)]}
    near(camera['union_bounds'],envelope,1e-10)
    for key in ('path','focal_length_mm','horizontal_aperture_mm','vertical_aperture_mm'):near(camera[key],source_program['camera'][key],0.)
    eye,target=vec(camera['eye']),vec(camera['target']);f=sub(target,eye);length=math.sqrt(sum(x*x for x in f));need(length>0,'nondegenerate camera')
    f=[x/length for x in f];right=[f[1],-f[0],0.];length=math.sqrt(sum(x*x for x in right));need(length>0,'camera up');right=[x/length for x in right];up=cross(right,f)
    fractions=[]
    for point in itertools.product(*zip(envelope['min'],envelope['max'])):
        delta=sub(point,eye);depth=sum(x*y for x,y in zip(delta,f));need(depth>0,'whole envelope in camera front')
        fractions.extend(abs(sum(x*y for x,y in zip(delta,axis)))/(depth*camera[aperture]/(2*camera['focal_length_mm'])) for axis,aperture in ((right,'horizontal_aperture_mm'),(up,'vertical_aperture_mm')))
    need(max(fractions)<=1/1.15+1e-10,'whole workspace/body envelope fits camera');near(camera['max_projected_fraction'],max(fractions),1e-10)
    return {'cloud_points':len(indices),'camera_max_projected_fraction':max(fractions)}


def check_initialization(report,model,output_dir):
    rows=report['observations'];audit=report['initialization_boundary'];names=set(model['movable'])
    need(audit['status']=='COMPLETE' and audit['original_descriptor_restored'] is True and not audit['faults'],'actual initialization closure')
    need(audit['module_sha256']=='dc1a3fbabbb54a4a3f7c45bf10e25643a346b06a6d9577e8f974584df9869742' and audit['reset_engine_time_s']==0. and audit['reset_positive_events']==0,'pinned zero-time reset')
    initial=audit['initial_state'];need(set(initial)=={'q','qd'} and set(initial['q'])==set(initial['qd'])==names,'closed initial nine coordinates')
    near(initial,{'q':rows[0]['q'],'qd':rows[0]['qd']},0.);need(all(abs(num(v))<=1e-6 for values in initial.values() for v in values.values()),'actual zero initial state')
    near(rows[0]['clock_after']['engine_time_s'],0.,0.)
    events=[json.loads(line) for line in (Path(output_dir)/'native-steps.ndjson').read_text(encoding='utf-8').splitlines()];near(events,audit['events'],0.)
    positive=[e for e in events if num(e['dt_s'])>0];need(len(positive)==2*report['completed_steps'],'complete ordered native steps')
    for i in range(report['completed_steps']):
        for j,phase in enumerate(('pre','post')):
            e=positive[2*i+j];row=rows[i+j];need(e['phase']==phase and e['state_available'] is True,'ordered actual PRE/POST availability')
            near(e['dt_s'],1/120,1e-9);near(e['engine_time_s'],row['clock_after']['engine_time_s'],1e-8)
            need(set(e['state'])=={'q','qd'} and set(e['state']['q'])==set(e['state']['qd'])==names,'closed callback coordinates')
            near(e['state'],{'q':row['q'],'qd':row['qd']},1e-8)


def verify_simulation(model_path, report, cfg, output_dir, purpose='motion'):
    if isinstance(report,(str,Path)):
        from driver import read
        report=read(report)
    model=pmodel(model_path);rows=report['observations'];program=report['program'];
    check_initialization(report,model,output_dir)
    gain=report['gain_initialization'];need(gain['backend']=='tensor','Actual tensor gain initialization')
    near(gain['engine_time_s'],0.,0.);near(gain['kp'],{n:64. for n in model['movable']},0.);near(gain['kd'],{n:16. for n in model['movable']},0.)
    near(gain['kp'],rows[0]['configuration']['kp'],0.);near(gain['kd'],rows[0]['configuration']['kd'],0.)
    source_program=json.loads((Path(model_path).parent.parent/'source/program.json').read_text(encoding='utf-8'))
    need(purpose in ('render_smoke','motion') and report['purpose']==purpose,'exact stage purpose')
    expected_program=copy.deepcopy(source_program)
    if purpose=='render_smoke':expected_program.update(segments=expected_program['segments'][:1],duration_s=2,steps=240,capture_count=21)
    near(program,expected_program,0.);need(all(s['gravity'] is True for s in program['segments']),'full gravity from first step')
    workspace,workspace_metrics=verify_workspace(model_path);cloud_metrics=check_cloud_camera(workspace,report,source_program)
    static=report['static'];clean_static=dict(static);clean_static['colliders']=[r for r in static['colliders'] if r['owner']!='__floor__'];verify_import(model_path,clean_static,cfg);check_colliders(model,static,fk(model,{}),cfg,True);check_binding(report['binding'],static,cfg)
    nsteps=program['steps'];partial=report.get('complete_program') is False
    if partial:
        need(type(report.get('stopped_at_step')) is int and report['stopped_at_step']==len(rows) and 1<=len(rows)<=program['steps'] and 'stopped_command' in report,'explicit original-cap stop after complete prefix')
        nsteps=len(rows)-1
    need(len(rows)==nsteps+1,'complete observed state prefix');check_runtime_inertias(model,report['inertias']);physical={n for n,x in model['links'].items() if x['mass'] is not None};names=model['movable'];need(report['dof_names'] and len(report['dof_names'])==9 and set(report['dof_names'])==set(names),'actual named 9 physical DOFs')
    prime=report['torque_prime'];checked_force_arrays(prime['raw']);need(prime['available'] is False and prime['sample_step']==0,'Prime not solver evidence')
    near(prime['clock_before'],rows[0]['clock_after'],0.);near(prime['clock_after'],rows[0]['clock_after'],0.)
    need(report['torque_api_pin']==cfg['sdk_source_pins'][-1],'Pinned force API')
    endpoints=set();end=0.
    for segment in program['segments']:
        end+=segment['duration_s']
        if segment['kind']=='hold' and segment['checkpoint']:endpoints.add(round(end*120))
    base_time=num(rows[0]['clock_after']['engine_time_s']);base_step=rows[0]['clock_after']['lab_step'];need(type(base_step) is int and base_step>=0,'actual initial Lab step');metrics={'max_fk_m':0.,'max_fk_rotation':0.,'max_gripper_relation_m':0.,'settling_pass':True,'checks':{},'frames':0}
    metrics.update(workspace=workspace_metrics,**cloud_metrics,limits_pass=True,floor_pass=True,gravity_margin_pass=True,min_floor_clearance_m=1e9,max_gravity_ratio=0.,max_actual_pose_gravity_ratio=0.)
    for i,row in enumerate(rows):
        check_torque_observation(row,report,model)
        need(type(row['step']) is int and row['step']==i,'contiguous actual state indices');near(row['time_s'],i/120,1e-8);near(num(row['clock_after']['engine_time_s'])-base_time,i/120,1e-6);near(row['clock_before'],row['clock_after'],0.)
        need(type(row['clock_after']['lab_step']) is int and row['clock_after']['lab_step']-base_step==i,'actual Lab step advancement')
        need(set(row['q'])==set(row['qd'])==set(row['targets'])==set(names),'complete named coordinates');q={n:num(row['q'][n]) for n in names};qd={n:num(row['qd'][n]) for n in names};expected,phase=target(i/120,program);need(row['phase']==phase,'phase matches immutable program');near(row['targets'],expected,1e-10)
        ps=fk(model,q);actual={p['name']:(vec(p['position']),quat(p['orientation_wxyz'])) for p in row['body_poses']};need(len(row['body_poses'])==11 and set(actual)==physical,'all runtime LINK poses')
        tool_joint=next(j for j in model['joints'].values() if j['child']=='tool0');tcp=row['actual_tcp'];body=next(p for p in row['body_poses'] if p['name']=='KG1')
        need(tcp['source_body']==tool_joint['parent']=='KG1','actual TCP fixed-frame owner')
        near(tcp['body_position'],body['position'],0.);near(tcp['body_orientation_wxyz'],body['orientation_wxyz'],0.);near(tcp['local_tool_offset'],tool_joint['origin'][0],0.)
        near(tcp['position'],add(actual['KG1'][0],mv(actual['KG1'][1],tool_joint['origin'][0])),1e-8);near(tcp['position'],ps['tool0'][0],8e-5)
        for n in names:
            joint=model['joints'][n]
            metrics['limits_pass'] &= joint['lower']-1e-5<=q[n]<=joint['upper']+1e-5 and abs(qd[n])<=joint['velocity']+1e-3
        clearance=min(add(ps[n][0],mv(ps[n][1],p))[2] for n in physical if n!=model['root'] for p in box_corners(model['links'][n]['collision']))
        metrics['min_floor_clearance_m']=min(metrics['min_floor_clearance_m'],clearance);metrics['floor_pass'] &= clearance>=.005
        for name in physical:
            pe=max(abs(a-b) for a,b in zip(actual[name][0],ps[name][0]));re=max(abs(a-b) for a,b in zip(sum(actual[name][1],[]),sum(ps[name][1],[])));metrics['max_fk_m']=max(metrics['max_fk_m'],pe);metrics['max_fk_rotation']=max(metrics['max_fk_rotation'],re);need(pe<=8e-5 and re<=1e-3,'runtime FK/axis observation')
        relation=max(abs(q['KG1_slide_B']-q['KG1_slide_A']),abs(q['KG1_pinion']*.0135+q['KG1_slide_A']));metrics['max_gripper_relation_m']=max(metrics['max_gripper_relation_m'],relation)
        if i in endpoints:
            arm_ok=all(abs(q[n]-expected[n])<=math.radians(.5) and abs(qd[n])<=math.radians(1) for n in names[:6]);jaw_ok=all(abs(q[n]-expected[n])<=.0005 and abs(qd[n])<=.001 for n in ('KG1_slide_A','KG1_slide_B'));pin_ok=abs(q['KG1_pinion']-expected['KG1_pinion'])<=math.radians(2) and abs(qd['KG1_pinion'])<=math.radians(3)
            metrics['settling_pass'] &= arm_ok and jaw_ok and pin_ok
        configuration=row['configuration'];near(configuration['gravity'],[0.,0.,-9.81],1e-6);need(len(configuration['link_enabled'])==11 and all(x is True for x in configuration['link_enabled']),'all body gravity flags');need(set(configuration['kp'])==set(names),'actual full drive states');near(configuration['kp'],{n:64. for n in names},1e-6);near(configuration['kd'],{n:16. for n in names},1e-6);need(all(t=='acceleration' for t in configuration['drive_types'].values()),'native acceleration drives')
        need(len(configuration['link_names'])==11 and set(configuration['link_names'])==physical,'exact gravity flag body names')
        near(configuration['position_targets'],expected,2e-6);check_velocity_configuration(row,program,model);near(configuration['velocity_limits'],{n:model['joints'][n]['velocity'] for n in names},2e-6)
        ff=row['ff'];native={n:0. for n in names}
        previous=rows[max(0,i-1)];need(ff['source_state_index']==max(0,i-1),'actual gravity source state index');near(ff['source_clock'],previous['clock_after'],0.);near(row['before_step'],previous['clock_after'],0.)
        native=check_ff(model,ff,previous,report['inertias'])
        used_ratio,load_limit,used_ok=gravity_margin(model,native,program,phase)
        actual_ratio,_,actual_ok=gravity_margin(model,gravity(model,row['body_poses'],report['inertias']),program,phase)
        metrics['gravity_margin_pass'] &= used_ok and actual_ok
        metrics['max_actual_pose_gravity_ratio']=max(metrics['max_actual_pose_gravity_ratio'],actual_ratio)
        for name in names:
            cap=model['joints'][name]['effort'];remaining=cap-abs(native[name]);need(remaining>=0,'source cap sufficient for native FF');near(row['effort_remaining'][name],remaining,2e-5);near(configuration['effort'][name],remaining,2e-5)
            metrics['max_gravity_ratio']=max(metrics['max_gravity_ratio'],abs(native[name])/cap)
    if partial:
        stop=report['stopped_command'];last=rows[-1];near(stop['source_before']['q'],last['q'],0.);near(stop['source_before']['body_poses'],last['body_poses'],0.);near(stop['clock'],last['clock_after'],0.)
        expected,_=target(len(rows)/120,program);near(stop['target']['targets'],expected,1e-10);ff=stop['ff'];count=ff['shape'][1];values=vec(ff['full'],count);offset=count-9;need(ff['shape'][0]==1 and offset in (0,6) and set(ff['names'])==set(names),'complete stopped native mapping');mapped={n:values[offset+ff['names'].index(n)] for n in names};near(ff['native'],mapped,0.);near(mapped,gravity(model,last['body_poses'],report['inertias']),1e-3);remaining={n:model['joints'][n]['effort']-abs(mapped[n]) for n in names};near(stop['remaining_caps'],remaining,1e-8);need(any(x<0 for x in remaining.values()),'genuine original cap infeasibility')
        metrics['settling_pass']=False
    metrics['complete_program']=not partial
    # Rendering is an observed source, not physics-loop count or successful API return.
    # Root independently checks capture generation rather than invoking the producer predicate.
    journal=[json.loads(line) for line in (Path(output_dir)/'motion.ndjson').read_text(encoding='utf-8').splitlines()];near(journal,rows,0.)
    frames=report['frames'];stride=program['capture_stride'];need(len(frames)==len(range(0,nsteps+1,stride)) and [x['state_index'] for x in frames]==list(range(0,nsteps+1,stride)),'exact native capture state prefix');seen=set()
    for i,f in enumerate(frames):
        need(f['frame_index']==i and f['phase']==rows[f['state_index']]['phase'],'frame/state phase binding');check_generation(f['freshness']);near(f['native_before'],f['native_after'],0.)
        bound=rows[f['state_index']];near(f['freshness']['source_engine_time_s'],f['native_before']['clock']['engine_time_s'],0.);near(f['physics_time_s'],bound['time_s'],1e-9);near(f['native_before']['q'],bound['q'],0.);near(f['native_before']['qd'],bound['qd'],0.);near(f['native_before']['body_poses'],bound['body_poses'],0.);near(f['native_before']['clock'],bound['clock_after'],0.)
        near(f['actual_tcp'],bound['actual_tcp'],0.);visual=f['actual_tcp_visual'];need(visual['marker_path']=='/World/ActualTCP/Marker' and visual['trail_path']=='/World/ActualTCP/Trail' and type(visual['trail_count']) is int and visual['trail_count']==(0 if i==0 else i+1),'native actual trajectory inventory');near(visual['marker_position'],bound['actual_tcp']['position'],1e-6)
        rel=Path(f['png']);need(not rel.is_absolute() and '..' not in rel.parts,'safe frame path');p=Path(output_dir)/rel;data=p.read_bytes();need(hashlib.sha256(data).hexdigest()==f['sha256'],'actual PNG bytes sealed');need(png_header(data,cfg)==f['rgba_sha256'] and f['png_encoding']=='RGBA8_FILTER0_ZLIB1','decoded native RGBA SHA');seen.add(f['sha256'])
        near(json.loads(p.with_suffix('.json').read_text(encoding='utf-8')),f,0.)
    need(len(seen)>(10 if purpose=='motion' else 0),'observed scene imagery inventory')
    motion_metrics=large_motion_check(rows,frames,model,purpose);metrics.update(motion_metrics)
    tcp=[rows[f['state_index']]['actual_tcp']['position'] for f in frames]
    trail=report['actual_tcp_visual'];need(trail['root']=='/World/ActualTCP' and trail['physics'] is False and trail['marker_path']=='/World/ActualTCP/Marker' and trail['trail_path']=='/World/ActualTCP/Trail','distinct native actual trail identity');near(trail['positions'],tcp,1e-6)
    need(len(trail['prim_roles'])>=3,'native actual trail prim inventory')
    for role in trail['prim_roles']:
        need(role['path'].startswith('/World/ActualTCP') and all(role[k] is False for k in ('rigid_body','mass_api','collision')) and not any(any(a in s for a in ('RigidBodyAPI','MassAPI','CollisionAPI')) for s in role['applied_schemas']),'actual marker/trail has no physics')
    reference=verify_reference(report)
    metrics['reference_measurement_status']=reference['status'];metrics['reference_faults']=len(reference['faults'])
    metrics['frames']=len(frames);metrics['checks']={'settling':metrics['settling_pass'],'gripper_sync':metrics['max_gripper_relation_m']<=.001,'canonical_fk':True,'native_render':True,'complete_program':not partial,'joint_limits_and_velocity':metrics['limits_pass'],'floor_clearance':metrics['floor_pass'],'gravity_margin':metrics['gravity_margin_pass'],'large_motion':motion_metrics['large_motion_pass']};metrics['dynamics_pass']=all(metrics['checks'].values());return metrics
