"""132 local SI trajectory and measured v4 workspace planner; no runtime/SDK entry."""
from __future__ import annotations
import hashlib,json,math,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
MODEL='models/robot-arm-urdf-v4/robot_arm.urdf'
CONTRACT='src/simulation/mp18_isaac_130/contract.py'
CONFIG='src/simulation/mp18_isaac_130/config.json'
MODEL_SHA='d55f0cbdffb8f82094b8797b187f02a3a5fd77a4a4f4272c975f21945b53135f'
CONTRACT_SHA='9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf'
ARM=['J%d'%i for i in range(1,7)]
NAMES=ARM+['KG1_slide_A','KG1_slide_B','KG1_pinion']
UNITS={n:('m' if 'slide' in n else 'rad') for n in NAMES}
CAPS=dict(zip(NAMES,[3.,12.,7.,2.,2.,1.,10.,10.,.2]))
RATIO=-74.07407407407408

def need(ok,message):
    if not ok: raise ValueError(message)
def digest(raw): return hashlib.sha256(raw).hexdigest()
def canonical(x): return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def parse(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            need(k not in d,'Duplicate key');d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:need(False,'Nonfinite JSON'))
def sources():
    raw=(ROOT/CONTRACT).read_bytes();need(digest(raw)==CONTRACT_SHA,'Contract pin')
    C=types.ModuleType('contract132');C.__file__=str(ROOT/CONTRACT);exec(compile(raw,C.__file__,'exec'),C.__dict__)
    cfg=parse((ROOT/CONFIG).read_bytes());need(digest((ROOT/MODEL).read_bytes())==MODEL_SHA,'URDF pin')
    for rel,pin in cfg['model_pins'].items():
        b=(ROOT/'models/robot-arm-urdf-v4'/rel).read_bytes()
        need(len(b)==pin['bytes'] and digest(b)==pin['sha256'],'Model pin '+rel)
    return C,C.parse_model(ROOT/MODEL),cfg

def target(deg,slider):
    return dict(zip(NAMES,[math.radians(x) for x in deg]+[slider,slider,RATIO*slider]))
def build_scenario():
    C,m,cfg=sources()
    home=[0,-25,-25,-15,45,10]
    rows=[('safe_home',6,home,.01,'open'),('diversity_A',6,[45,-35,-40,-40,20,60],.01,'open'),
      ('diversity_B',9,[-45,-15,-50,30,-20,-50],.01,'open'),('diversity_C',8,[20,-35,-25,-25,35,45],.01,'open'),
      ('safe_home_return',6,home,.01,'open'),('safe_home_settle',2,home,.01,'open'),
      ('source_approach',6,[-25,-35,20,-15,60,10],.01,'open'),('source_lower',5,[-25,-7,-8,-15,60,10],.01,'open'),
      ('grasp_close',2,[-25,-7,-8,-15,60,10],-.0105,'contact_hold'),('grasp_settle',1,[-25,-7,-8,-15,60,10],-.0105,'contact_hold'),
      ('lift',5,[-25,-40,25,-15,60,10],-.0105,'contact_hold'),('transfer',7,[25,-40,25,-15,60,10],-.0105,'contact_hold'),
      ('place_lower',5,[25,-7,-8,-15,60,10],-.0105,'contact_hold'),('release',2,[25,-7,-8,-15,60,10],.01,'open'),
      ('place_settle',2,[25,-7,-8,-15,60,10],.01,'open'),('retract',5,[25,-35,20,-15,60,10],.01,'open'),
      ('home',6,home,.01,'open'),('home_settle',2,home,.01,'open')]
    stages=[];boundary=0
    for name,d,q,jaw,mode in rows:
        stages.append(dict(name=name,duration_steps=120*d,targets_si=target(q,jaw),gripper_mode=mode,start_s=boundary,end_s=boundary+d))
        boundary+=d
    def grasp(q):
        T=C.fk(m,q)['KG1'];return C.mm(T,C.tf([0,0,.104],[r[:3] for r in C.ident()[:3]]))
    pick=grasp(stages[7]['targets_si']);place=grasp(stages[12]['targets_si']);lift=grasp(stages[10]['targets_si'])
    # Object z points up, x is the actual jaw closing axis in the world.
    def obj(T):
        return [[T[i][0],-T[i][1],-T[i][2],T[i][3]] for i in range(3)]+[[0.,0.,0.,1.]]
    source,destination=obj(pick),obj(place)
    height=source[2][3]-.004
    pins={CONTRACT:dict(sha256=CONTRACT_SHA,bytes=len((ROOT/CONTRACT).read_bytes())),MODEL:dict(sha256=MODEL_SHA,bytes=len((ROOT/MODEL).read_bytes()))}
    for rel,pin in cfg['model_pins'].items():pins['models/robot-arm-urdf-v4/'+rel]=pin
    for path in [CONFIG,'outputs/mp18-isaac-119/A/support.json','outputs/mp18-profile-repair-130/runs/dee4f7e320ea464aabd34bc41740efe1/retrieved/runtime-inertias.json']:
        b=(ROOT/path).read_bytes();pins[path]=dict(sha256=digest(b),bytes=len(b))
    return dict(unit=132,kind='LOCAL_STATIC_MANIPULATION_PLAN',hardware_approved=False,runtime_grasp_status='NOT_RUN',
      joint_units=UNITS,dt_s=1/120,duration_s=boundary,initial_targets_si=target([0]*6,0),stages=stages,
      boundaries_s=[s['end_s'] for s in stages],source_pins=pins,
      policy=dict(arm_stiffness=64,arm_damping=16,caps_si=CAPS,source_velocity_tolerance=1e-4,settling_position_rad=math.radians(.5),settling_velocity_rad_s=math.radians(1),floor_z_m=0.,object_attachment_forbidden=True),
      object=dict(shape='box',dimensions_m=[.020,.010,.008],mass_kg=.002,material_assumption=True,static_friction=.8,dynamic_friction=.6,source_T_world=source,destination_T_world=destination),
      pedestals=[dict(name=n,dimensions_m=[.012,.008,height],center_m=[T[0][3],T[1][3],height/2],yaw_rad=math.atan2(T[1][0],T[0][0])) for n,T in [('source',source),('destination',destination)]],
      grasp=dict(frame_parent='KG1',translation_m=[0,0,.104],tool0_offset_m=[0,0,.001],pad_z_band_m=[.100,.106],measured_y_band_m=[-.009,.009],opening_formula='0.04+2*slider_q_m',open_slider_q_m=.01,touch_slider_q_m=-.01,contact_target_slider_q_m=-.0105,pinion_multiplier=RATIO,contact_target_is_intentional=True),
      checkpoints=[dict(phase=x,at_end=True,kind='SETTLE_ARM_SOURCE_CRITERIA') for x in ['safe_home_settle','grasp_settle','place_settle','home_settle']],
      acceptance=dict(min_lift_m=.020,min_transport_xy_m=.150,both_jaw_object_contact_required=True,object_actual_pose_required=True,release_then_settle_required=True,static_grasp_success=False),
      geometry_hypothesis=dict(source_grasp_T_world=pick,lift_grasp_T_world=lift,destination_grasp_T_world=place),
      limitations=['Static desired object pose is a hypothesis; object must remain free and be observed at runtime.','Link6/KG1_B and Link6/KG1_R coarse collider overlap remains unresolved; no global self-collision clearance certification.','Gravity check is static, not a dynamic torque or physical grasp proof.','Retracting lift moves horizontally as it rises; physical contact and slip remain untested.'])

def sample(scenario,t_s):
    need(type(t_s) in (int,float) and math.isfinite(t_s) and 0<=t_s<=scenario['duration_s'],'Sample time')
    previous=scenario['initial_targets_si'];start=0.
    for index,stage in enumerate(scenario['stages']):
        d=stage['duration_steps']/120
        if t_s<=start+d+1e-10:
            u=min(1.,max(0.,(t_s-start)/d));s=u*u*u*(10+u*(-15+6*u));v=30*u*u*(1-u)*(1-u)/d
            q={n:previous[n]+(stage['targets_si'][n]-previous[n])*s for n in NAMES}
            qd={n:(stage['targets_si'][n]-previous[n])*v for n in NAMES}
            return dict(targets=q,reference_velocity=qd,phase=stage['name'],phase_index=index,gripper_mode=stage['gripper_mode'],opening_m=.04+2*q['KG1_slide_A'])
        previous=stage['targets_si'];start+=d
    raise ValueError('Complete time coverage')
target_at=sample

def validate(s,geometry=False):
    C,m,cfg=sources();expected=build_scenario()
    need(set(s)==set(expected),'Closed scenario schema')
    for key in ['unit','kind','hardware_approved','runtime_grasp_status','joint_units','dt_s','policy','grasp','acceptance','source_pins','object','pedestals','checkpoints','geometry_hypothesis','limitations']:
        need(s[key]==expected[key],'Immutable measured contract '+key)
    need(s['initial_targets_si']==expected['initial_targets_si'],'Initial coordinates')
    need(len(s['stages'])==len(expected['stages']),'Required task phases')
    peaks={n:0. for n in NAMES};mins={n:1e9 for n in NAMES};maxs={n:-1e9 for n in NAMES};margin={n:1e9 for n in NAMES}
    prev=s['initial_targets_si'];time=0.
    for stage,base in zip(s['stages'],expected['stages']):
        need(set(stage)==set(base) and stage['name']==base['name'] and stage['gripper_mode']==base['gripper_mode'],'Phase schema/order')
        steps=stage['duration_steps'];need(type(steps) is int and steps>=120,'Integer 120Hz duration')
        d=steps/120;need(stage['start_s']==time and stage['end_s']==time+d,'Phase boundaries')
        q=stage['targets_si'];need(set(q)==set(NAMES),'Exact named target set')
        for n in NAMES:
            need(type(q[n]) in (int,float) and math.isfinite(q[n]),'Finite SI target')
            j=m['joints'][n];need(j['lower']<=q[n]<=j['upper'],'Source position limit '+n)
            peak=1.875*abs(q[n]-prev[n])/d;need(peak<=j['velocity']+1e-12,'Source planned velocity '+n)
            peaks[n]=max(peaks[n],peak);mins[n]=min(mins[n],q[n],prev[n]);maxs[n]=max(maxs[n],q[n],prev[n]);margin[n]=min(margin[n],q[n]-j['lower'],j['upper']-q[n])
        need(abs(q[NAMES[7]]-q[NAMES[6]])<1e-12 and abs(q[NAMES[8]]-RATIO*q[NAMES[6]])<1e-12,'Actual mimic')
        need(q==base['targets_si'],'Reviewed measured waypoint')
        prev=q;time+=d
    need(time==s['duration_s']<=90 and s['boundaries_s']==[x['end_s'] for x in s['stages']],'Duration coverage')
    need(all(maxs[n]-mins[n]>=math.radians(30) for n in ARM),'Six joint diversity')
    for t in s['boundaries_s']:need(max(abs(x) for x in sample(s,t)['reference_velocity'].values())<1e-10,'Zero velocity boundaries')
    A=s['geometry_hypothesis'];lift=A['lift_grasp_T_world'][2][3]-A['source_grasp_T_world'][2][3]
    xy=math.hypot(A['destination_grasp_T_world'][0][3]-A['source_grasp_T_world'][0][3],A['destination_grasp_T_world'][1][3]-A['source_grasp_T_world'][1][3])
    need(lift>=.020 and xy>=.150,'Required lift and displacement')
    result=dict(status='STATIC_PLAN_VALID_RUNTIME_NOT_RUN',range_si={n:maxs[n]-mins[n] for n in NAMES},peak_velocity_si=peaks,limit_margin_si=margin,lift_m=lift,transport_xy_m=xy,sampled_steps=0)
    if geometry:result.update(measure_geometry(s,C,m))
    return result

def measure_geometry(s,C=None,m=None):
    import numpy as np
    import trimesh
    if C is None:C,m,_=sources()
    root=ROOT/'models/robot-arm-urdf-v4'
    verts={n:np.unique(np.concatenate([trimesh.load(root/x['file'],force='mesh',process=False).vertices for x in row['collisions']]),axis=0) for n,row in m['links'].items() if row['collisions']}
    # Source compound collision shells; whole-mesh hull/AABB overlap is UNKNOWN, not contact proof.
    pairs=[];excluded=[]
    direct={frozenset([j['parent'],j['child']]) for j in m['joints'].values()}
    names=list(verts)
    for i,a in enumerate(names):
        for b in names[i+1:]:
            if frozenset([a,b]) in direct or (a.startswith('KG1') and b.startswith('KG1')):excluded.append([a,b])
            else:pairs.append((a,b))
    floor=1e9;floor_phase='';unresolved={};pairmin={};gravmax={n:0. for n in NAMES};obstaclemin=1e9;obstacleunknown=set();home_floor=None
    descendants={}
    for n in NAMES:
        children={m['joints'][n]['child']};changed=True
        while changed:
            before=len(children);children.update(j['child'] for j in m['joints'].values() if j['parent'] in children);changed=len(children)>before
        descendants[n]=children
    # Nine named SI state and every 1/120s trajectory sample; no physics steps.
    for k in range(int(s['duration_s']*120)+1):
        row=sample(s,k/120);q=row['targets'];poses=C.fk(m,q)
        T={n:np.asarray(poses[n]) for n in verts};wv={n:v@T[n][:3,:3].T+T[n][:3,3] for n,v in verts.items()};bounds={n:(v.min(0),v.max(0)) for n,v in wv.items()}
        f=min(float(v[:,2].min()) for n,v in wv.items() if n!='Base')
        if f<floor:floor=f;floor_phase=row['phase']
        if k==720:home_floor=f
        need(f>=-.000001,'Planned collision geometry below floor '+row['phase'])
        for a,b in pairs:
            alo,ahi=bounds[a];blo,bhi=bounds[b];gap=float(np.maximum(blo-ahi,alo-bhi).max())
            if gap<=0:
                axes=np.concatenate([T[a][:3,:3].T,T[b][:3,:3].T]);pa=wv[a]@axes.T;pb=wv[b]@axes.T
                gap=max(gap,float(np.maximum(pb.min(0)-pa.max(0),pa.min(0)-pb.max(0)).max()))
            key=a+'|'+b;pairmin[key]=min(pairmin.get(key,1e9),gap)
            if gap<=0:unresolved[key]=unresolved.get(key,0)+1
        # Static gravity from actual v4 link COMs, plus the assumed free object only during predicted carry.
        com={n:np.asarray(C.mv(poses[n],[*v['com'],1.])[:3]) for n,v in m['links'].items() if v['mass'] is not None}
        carried=row['phase'] in ['grasp_settle','lift','transfer','place_lower']
        objectcom=np.asarray(C.mv(poses['KG1'],[0,0,.104,1])[:3])
        for n in NAMES:
            j=m['joints'][n];P=np.asarray(poses[j['child']]);axis=P[:3,:3]@np.asarray(j['axis']);p=P[:3,3];tau=0.
            for link in descendants[n]:
                body=m['links'][link]
                if body['mass'] is None:continue
                force=np.array([0.,0.,body['mass']*9.81])
                tau+=float(axis@ (force if j['type']=='prismatic' else np.cross(com[link]-p,force)))
            if carried and n in ARM:tau+=float(axis@np.cross(objectcom-p,[0,0,s['object']['mass_kg']*9.81]))
            gravmax[n]=max(gravmax[n],abs(tau));need(abs(tau)<=CAPS[n]+1e-9,'Static gravity cap '+n+' '+row['phase'])
        # Conservative oriented-box separation against both narrow pedestals.
        for pedestal in s['pedestals']:
            yaw=pedestal['yaw_rad'];R=np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
            center=np.asarray(pedestal['center_m']);half=np.asarray(pedestal['dimensions_m'])/2
            for n,v in wv.items():
                if n=='Base':continue
                local=(v-center)@R;gap=float(np.maximum(-half-local.max(0),local.min(0)-half).max())
                obstaclemin=min(obstaclemin,gap)
                if gap<=0:obstacleunknown.add(n+'|'+pedestal['name'])
    need(home_floor is not None and home_floor>.05,'Measured safe-home floor margin')
    return dict(sampled_steps=int(s['duration_s']*120)+1,min_moving_floor_m=floor,min_floor_phase=floor_phase,safe_home_floor_m=home_floor,
      min_pair_separating_lower_bound_m=pairmin,self_unresolved_samples=unresolved,self_exclusions=excluded,self_status='PARTIAL_SEPARATION_WITH_EXPLICIT_UNKNOWN',
      pedestal_separation_lower_bound_m=obstaclemin,pedestal_unresolved=sorted(obstacleunknown),static_gravity_peak_si=gravmax,
      static_gravity_remaining_si={n:CAPS[n]-gravmax[n] for n in NAMES},object_friction_min_normal_per_jaw_N=s['object']['mass_kg']*9.81/(2*s['object']['static_friction']))

def measure_pad_band():
    import numpy as np
    import trimesh
    result={}
    root=ROOT/'models/robot-arm-urdf-v4/meshes'
    for kind in ['visual','collision']:
        rows=[]
        for z in [.100,.101,.102,.104]:
            inner=[]
            for name,origin in [('KG1_A',-.020),('KG1_B',.020)]:
                mesh=trimesh.load(root/('collision/'+name+'.stl' if kind=='collision' else name+'.stl'),force='mesh',process=False)
                section=mesh.section(plane_origin=[0,0,z],plane_normal=[0,0,1]);need(section is not None,'Measured pad section')
                # Each polyline segment crosses y=0 at an actual mesh section edge.
                xs=[]
                for poly in section.discrete:
                    for a,b in zip(poly[:-1],poly[1:]):
                        if min(a[1],b[1])<=0<=max(a[1],b[1]) and abs(a[1]-b[1])>1e-12:
                            xs.append(float(a[0]+(b[0]-a[0])*(-a[1])/(b[1]-a[1])))
                need(xs,'Inner pad samples');inner.append(origin+(max(xs) if name=='KG1_A' else min(xs)))
            gap=inner[1]-inner[0];need(abs(gap-.04)<2e-6,'Visual/collision inner gap agreement');rows.append(dict(z_m=z,inner_x_m=inner,gap_m=gap))
        result[kind]=rows
    return result


def measure_object_sweep(s):
    """Every120Hz actual robot collision projection against the assumed free box.
    Positive separation proves clearance; planned jaw overlap is not a grasp proof.
    """
    import numpy as np
    import trimesh
    C,m,_=sources();root=ROOT/'models/robot-arm-urdf-v4'
    verts={n:np.unique(np.concatenate([trimesh.load(root/x['file'],force='mesh',process=False).vertices for x in row['collisions']]),axis=0) for n,row in m['links'].items() if row['collisions']}
    # Actual previous native importer uses one convex hull per link. Include all SAT face/edge axes.
    from scipy.spatial import ConvexHull
    hulls={}
    for n,v in verts.items():
        h=ConvexHull(v);v=v[h.vertices];h=ConvexHull(v)
        edges=np.concatenate([v[h.simplices[:,1]]-v[h.simplices[:,0]],v[h.simplices[:,2]]-v[h.simplices[:,0]],v[h.simplices[:,2]]-v[h.simplices[:,1]]])
        hulls[n]=(v,np.unique(np.round(h.equations[:,:3],9),axis=0),np.unique(np.round(edges,9),axis=0))
    nonjaw=1e9;openjaw=1e9;intentional={};unknown={};half=np.asarray(s['object']['dimensions_m'])/2
    carry=['grasp_settle','lift','transfer','place_lower']
    allowed=carry+['grasp_close','release']
    for k in range(int(s['duration_s']*120)+1):
        p=sample(s,k/120);pose=C.fk(m,p['targets']);phase=p['phase']
        if phase in carry:
            T=np.asarray(pose['KG1']);center=T[:3,:3]@np.asarray([0,0,.104])+T[:3,3];R=T[:3,:3]@np.diag([1,-1,-1])
        else:
            T=np.asarray(s['object']['destination_T_world' if phase in ['release','place_settle','retract','home','home_settle'] else 'source_T_world']);center=T[:3,3];R=T[:3,:3]
        for n,(v,normals,edges) in hulls.items():
            P=np.asarray(pose[n]);local=(v@P[:3,:3].T+P[:3,3]-center)@R
            gap=float(np.maximum(-half-local.max(0),local.min(0)-half).max())
            if gap<=0:
                e=edges@P[:3,:3].T@R
                axes=np.concatenate([normals@P[:3,:3].T@R]+[np.cross(e,a) for a in np.eye(3)])
                axes=axes[np.linalg.norm(axes,axis=1)>1e-10];axes/=np.linalg.norm(axes,axis=1)[:,None]
                projected=local@axes.T;radius=np.abs(axes)@half
                gap=max(gap,float(np.maximum(-radius-projected.max(0),projected.min(0)-radius).max()))
            if n in ['KG1_A','KG1_B'] and phase in allowed:
                if gap<=0:intentional[phase+'|'+n]=intentional.get(phase+'|'+n,0)+1
            elif n in ['KG1_A','KG1_B']:
                openjaw=min(openjaw,gap)
                if gap<=0:unknown[phase+'|'+n]=unknown.get(phase+'|'+n,0)+1
            else:
                nonjaw=min(nonjaw,gap)
                if gap<=0:unknown[phase+'|'+n]=unknown.get(phase+'|'+n,0)+1
    need(not unknown,'Object non-contact separation unresolved '+str(unknown))
    return dict(sampled_steps=int(s['duration_s']*120)+1,nonjaw_object_separation_lower_bound_m=nonjaw,open_jaw_object_separation_lower_bound_m=openjaw,intentional_jaw_object_overlap_samples=intentional,unexpected_object_overlap=unknown,status='GEOMETRIC_CONTACT_HYPOTHESIS_NOT_PHYSICAL_GRASP')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');p.add_argument('--geometry',action='store_true');args=p.parse_args()
    scenario=build_scenario()
    if args.write:Path(__file__).with_name('scenario.json').write_bytes(canonical(scenario))
    print(json.dumps(validate(scenario,args.geometry),indent=2,allow_nan=False))
