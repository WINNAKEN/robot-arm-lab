if __name__=='__main__':
    raise SystemExit('Use launch.ps1; direct execution is forbidden')

import os
import sys
import json
import tempfile
import hashlib
import importlib
import math
from pathlib import Path
import time
import traceback
LINKS=['Base']+[f'Link{i}' for i in range(1,7)]
JOINTS=[f'J{i}' for i in range(1,7)]

def run(api, start=None, collect_fn=None):
    """One lifecycle owner; every outcome supplies the actual process exit code."""
    app,code=None,1
    out=api['run']/'output';write=api['write']
    terminal={'run_id':api['run'].name,'job_sha256':api['sha'](api['run']/'job.json'),
              'pid':os.getpid(),'parent_pid':os.getppid(),'started_unix':time.time(),'code':1,
              'status':'BUILDING','phase':'APP_START','stage':'robot_connection','hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN'}
    write(out/'status.json',terminal,True)
    try:
        app=(start or api['lib']['providers'].create_app)(api)
        terminal['phase']='COLLECTING'
        write(out/'status.json',terminal)
        (collect_fn or collect)(api)
        names=('observations.json','scene.usda','providers.json','sdk.json','physics-binding.json','clock-report.json','gravity-report.json','gravity-journal.ndjson','gravity-checkpoint.json')
        terminal['files_sha256']={n:api['sha'](out/n) for n in names}
        code=0
        terminal.update(status='COMPLETE_PRE_CLOSE',phase='CLOSING_APP',code=0)
    except Exception as exc:
        terminal.update(status='FAILED',code=1,primary_error=f'{type(exc).__name__}: {exc}')
        (out/'failure-traceback.txt').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
    finally:
        terminal['code']=code
        write(out/'terminal.json',terminal)
        write(out/'status.json',terminal)
        if app is not None:
            try:
                app.close(wait_for_replicator=False,exit_code=code)
                terminal['close_returned']=True
            except Exception as exc:
                code=1
                terminal.update(status='FAILED',code=1,close_error=f'{type(exc).__name__}: {exc}')
        if code==0:
            terminal.update(status='CLOSED',phase='APP_CLOSED')
        terminal['finished_unix']=time.time()
        write(out/'terminal.json',terminal)
        write(out/'status.json',terminal)
    return code

def setup(api):
    api['frameworks']=api['lib']['providers'].frameworks(api)
    import omni.timeline
    import omni.physx
    from pxr import Usd,UsdGeom,UsdPhysics
    import isaacsim.core.experimental.utils.backend as backend
    import isaacsim.core.experimental.utils.stage as stage_utils
    from isaacsim.core.experimental.prims import Articulation,RigidPrim
    from isaaclab.sim import SimulationCfg,SimulationContext
    run,cfg=api['run'],api['cfg'];out=run/'output';source=run/'input'
    need,write=api['need'],api['write'];environment=api['lib']['environment']
    sim=SimulationContext(SimulationCfg(dt=1/120,device='cpu',gravity=(0.,0.,0.),
        physics_prim_path='/World/physicsScene',use_newton_actuators=False))
    stage=sim.stage
    stage_utils.set_stage_units(meters_per_unit=1.,kilograms_per_unit=1.)
    stage_utils.set_stage_up_axis('Z')
    stage_utils.add_reference_to_stage(str(source/'data/model.usda'),'/World/Robot')
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    timeline=omni.timeline.get_timeline_interface()
    need(timeline.is_stopped(),'Pre-play model observation')
    environment.setup(stage)
    runtime={'run_id':run.name,'pid':os.getpid(),'hardware_approved':False}
    static=api['lib']['extract'].observe_stage(stage,source/'data/model.usda',runtime,True)
    static['environment']=environment.snapshot(stage)
    static['environment']['probe_source_observation']=next(b for b in static['bodies'] if b['path']==environment.PROBE)
    static['bodies']=[b for b in static['bodies'] if b['name'] in LINKS]
    bodies={b['name']:b for b in static['bodies']}
    need(set(bodies)==set(LINKS),'Seven source LINKs')
    robot=Articulation('/World/Robot/Geometry/Base')
    links=[RigidPrim(bodies[n]['path']) for n in LINKS]
    probe=RigidPrim(environment.PROBE)
    names=list(robot.dof_names)
    need(robot.num_dofs==6 and len(names)==6 and set(names)==set(JOINTS),'Named six DOFs')
    indices=[names.index(n) for n in JOINTS]
    caps=[cfg['cap_Nm'][JOINTS.index(n)] for n in names]
    with backend.use_backend('usd',raise_on_unsupported=True,raise_on_fallback=True):
        robot.set_dof_drive_types('force')
        robot.set_dof_gains([0.]*6,[0.]*6)
        robot.set_dof_max_efforts(caps)
    cache=UsdGeom.XformCache(Usd.TimeCode.Default())
    def placement(prim):
        t=cache.GetLocalToWorldTransform(prim)
        return {'path':str(prim.GetPath()),'position':[float(x) for x in t.ExtractTranslation()],
                'rotation':[[float(t[j][i]) for j in range(3)] for i in range(3)]}
    static['robot_root']=placement(stage.GetPrimAtPath('/World/Robot'))
    static['colliders']=[]
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.CollisionAPI) and str(prim.GetPath()).startswith(environment.ROOT+'/'):
            body=prim.GetParent();local=cache.GetLocalToWorldTransform(prim)*cache.GetLocalToWorldTransform(body).GetInverse()
            static['colliders'].append({'path':str(prim.GetPath()),'body_path':str(body.GetPath()),
                'local_position':[float(x) for x in local.ExtractTranslation()],
                'local_basis':[[float(local[j][i]) for j in range(3)] for i in range(3)],
                'size':float(UsdGeom.Cube(prim).GetSizeAttr().Get()),
                'enabled':bool(UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get())})
    physics=UsdPhysics.Scene(stage.GetPrimAtPath('/World/physicsScene'))
    direction,magnitude=physics.GetGravityDirectionAttr().Get(),physics.GetGravityMagnitudeAttr().Get()
    static.update(run_id=run.name,pid=os.getpid(),job_sha256=api['sha'](run/'job.json'),dof_names=names,
        configuration={'gravity':[float(x*magnitude) for x in direction],'frequency_hz':1/sim.get_physics_dt(),
            'device':str(sim.device),'manager':sim.physics_manager.__module__+'.'+sim.physics_manager.__name__})
    stage.Flatten().Export(str(out/'scene.usda'))
    return locals()


def bindings(api):
    api['need'](set(COLLECTORS)==set(api['contract']['facets']),'Collector obligation coverage')


def collect_static(state):
    return {k:state['static'][k] for k in state['api']['contract']['required_fields']['static']}


def collect_bodies(state):
    api,sim,timeline,static,backend,robot,indices,links,probe,names,environment=(state[k] for k in ('api','sim','timeline','static','backend','robot','indices','links','probe','names','environment'))
    need=api['need']
    sim.reset()
    need(timeline.is_playing(),'Actual playing Lab context')
    api['lib']['physics'].bind(api,sim,[robot,*links,probe])
    static['runtime_masses']=[]
    with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
        kp,kd=robot.get_dof_gains();effort=robot.get_dof_max_efforts().numpy().copy()[0]
        kp,kd=kp.numpy().copy()[0],kd.numpy().copy()[0]
        static['actual_drives']={'kp':[float(kp[i]) for i in indices],'kd':[float(kd[i]) for i in indices],
                                 'effort':[float(effort[i]) for i in indices]}
        for name,link in [*zip(LINKS,links),('probe',probe)]:
            com,axes=link.get_coms()
            static['runtime_masses'].append({'name':name,'mass':float(link.get_masses().numpy()[0,0]),
                'com':com.numpy().copy()[0].tolist(),'principal_axes_wxyz':axes.numpy().copy()[0].tolist(),
                'inertia_link_about_com':link.get_inertias().numpy().copy()[0].reshape((3,3),order='F').tolist()})
    with backend.use_backend('usd',raise_on_unsupported=True,raise_on_fallback=True):
        drive_types=robot.get_dof_drive_types()[0]
        static['actual_drives']['types']=[str(drive_types[i]) for i in indices]
    state['contact_reader']=environment.ContactReader(sim.physics_manager.get_physics_sim_view())
    return {k:static[k] for k in ('runtime_masses','dof_names','actual_drives','configuration')}



CLOCK_MANAGER='isaacsim.core.simulation_manager.impl.simulation_manager'
CLOCK_BINDING='isaacsim.core.simulation_manager.bindings._simulation_manager'
CLOCK_EXTENSION='isaacsim.core.simulation_manager.impl.extension'
CLOCK_SELECTED=CLOCK_MANAGER+'.SimulationManager.get_simulation_time'
CLOCK_PINS={
 CLOCK_MANAGER:('exts/isaacsim.core.simulation_manager/isaacsim/core/simulation_manager/impl/simulation_manager.py','0dd33b5f6927112450fb06bc81a3dffb8f82409b108d64657853f3cec11b1833'),
 CLOCK_EXTENSION:('exts/isaacsim.core.simulation_manager/isaacsim/core/simulation_manager/impl/extension.py','ee5356e1118fa0ceda57e2cc79a9165d8162c65a23ef502fcc46a41f7c7fecf1'),
 CLOCK_BINDING:('exts/isaacsim.core.simulation_manager/isaacsim/core/simulation_manager/bindings/_simulation_manager.cp312-win_amd64.pyd','4eab1209f0b96f699251378193ec4729d54a12614dafcd66a64324bdd654acab')}

def clock_number(value,need):
    need(type(value) in (int,float) and math.isfinite(value) and value>=0,'Finite nonnegative native engine time')
    return float(value)

def clock_owner(api,sim,omni,report):
    need=api['need'];modules={n:importlib.import_module(n) for n in CLOCK_PINS};sources={};report['sources']=sources
    for name,module in modules.items():
        path=Path(module.__file__).resolve();relative,pin=CLOCK_PINS[name]
        need(path== (Path(api['cfg']['isaac_root'])/relative).resolve(),'Exact installed clock source path')
        digest=hashlib.sha256(path.read_bytes()).hexdigest();need(digest==pin,'Pinned installed clock source bytes')
        sources[name]={'origin':str(path),'sha256':digest}
    module=modules[CLOCK_MANAGER];owner=module.SimulationManager;native=owner._simulation_manager_interface
    getter=getattr(owner,'get_simulation_time',None)
    report.update({'selected':CLOCK_SELECTED,'manager_name':CLOCK_MANAGER+'.SimulationManager','manager_id':id(owner),
        'native_id':id(native),'native_type':type(native).__module__+'.'+type(native).__qualname__,'native_identity':type(native) is modules[CLOCK_BINDING].ISimulationManager,
        'api_inventory':{'physx_get_simulation_time':callable(getattr(omni.physx.get_physx_interface(),'get_simulation_time',None)),
            'sdk_get_simulation_time':callable(getter),'lab_get_simulation_time':callable(getattr(sim.physics_manager,'get_simulation_time',None))},'sources':sources})
    need(owner.__module__==CLOCK_MANAGER and owner.__name__=='SimulationManager' and modules[CLOCK_EXTENSION].SimulationManager is owner,'Original SDK clock manager')
    need(type(native) is modules[CLOCK_BINDING].ISimulationManager,'Actual native clock interface identity')
    need(native is modules[CLOCK_EXTENSION].acquire_simulation_manager_interface(),'Startup native clock interface identity')
    need(callable(getter) and callable(getattr(native,'get_simulation_time',None)),'Native engine time getter available')

    return report,getter

def check_clock(value,rows,run,job,pid,cfg,physics,need):
    need(set(value)=={'schema_version','run_id','job_sha256','pid','status','phase','owner','samples'} and value['schema_version']==1,'Closed native clock report')
    need(value['run_id']==run and value['job_sha256']==job and type(value['pid']) is int and value['pid']==pid,'Clock report run/job/PID binding')
    need(value['status']=='READY' and value['phase']=='TRACE_COMPLETE','Actual clock trace completed')
    o=value['owner'];need(set(o)=={'selected','manager_name','manager_id','native_id','native_type','native_identity','api_inventory','sources'},'Closed clock owner observation')
    need(o['selected']==CLOCK_SELECTED and o['manager_name']==CLOCK_MANAGER+'.SimulationManager' and o['native_type']==CLOCK_BINDING+'.ISimulationManager' and o['native_identity'] is True,'Pinned native clock owner')
    need(type(o['manager_id']) is int and o['manager_id'] in {m['id'] for m in physics['managers']} and type(o['native_id']) is int and o['native_id']>0,'Clock/readiness owner binding')
    inv=o['api_inventory'];need(set(inv)=={'physx_get_simulation_time','sdk_get_simulation_time','lab_get_simulation_time'} and all(type(x) is bool for x in inv.values()) and inv['sdk_get_simulation_time'],'Complete clock API availability')
    need(set(o['sources'])==set(CLOCK_PINS),'Complete clock source observations')
    for n,(relative,pin) in CLOCK_PINS.items():
        item=o['sources'][n];need(set(item)=={'origin','sha256'} and Path(item['origin']).resolve()==(Path(cfg['isaac_root'])/relative).resolve() and item['sha256']==pin,'Pinned native clock source evidence')
    need(type(rows) is list and len(rows)==11 and len(value['samples'])==33,'Complete engine clock samples')
    baseline=clock_number(rows[0]['read_after']['engine_time_s'],need)
    for i,row in enumerate(rows):
        need(type(row['index']) is int and row['index']==i,'Indexed clock trace')
        for j,point in enumerate(('before_step','read_before','read_after')):
            sample=value['samples'][3*i+j]
            need(set(sample)=={'index','point','clock'} and type(sample['index']) is int and sample['index']==i and sample['point']==point and sample['clock']==row[point],'Native clock samples match actual trace')
            current=clock_number(sample['clock']['engine_time_s'],need)
            need(abs(current-baseline-max(0,i-(point=='before_step'))/120)<=1e-6,'Native clock time progressed independently')
        need(row['read_before']==row['read_after'],'Stable native clock during tensor reads')


def collect_trace(state):
    api,sim,timeline,backend,robot,indices,links,probe,omni=(state[k] for k in ('api','sim','timeline','backend','robot','indices','links','probe','omni'))
    need=api['need']
    observed={'count':0,'time':0.}
    def post_step(dt):
        observed['count']+=1;observed['time']+=float(dt)
    report={'schema_version':1,'run_id':api['run'].name,'job_sha256':api['sha'](api['run']/'job.json'),'pid':os.getpid(),'status':'BUILDING','phase':'OWNER','owner':None,'samples':[]}
    target=api['run']/'output/clock-report.json'
    write=lambda:api['write'](target,report)
    write()
    subscription=None
    def clock(index,point):
        engine=clock_number(getter(),need)
        value= {'lab_step':int(sim.get_physics_step_count()),'engine_event_index':observed['count'],
                'engine_time_s':engine,'callback_time_s':observed['time']}
        report['samples'].append({'index':index,'point':point,'clock':value.copy()});write()
        return value
    def record(index,before):
        read_before=clock(index,'read_before')
        with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
            q,qd=robot.get_dof_positions().numpy().copy()[0],robot.get_dof_velocities().numpy().copy()[0]
            poses=[]
            for name,link in zip(LINKS,links):
                p,r=link.get_world_poses()
                poses.append({'name':name,'position':p.numpy().copy()[0].tolist(),'orientation_wxyz':r.numpy().copy()[0].tolist()})
            pp,pq=probe.get_world_poses()
            probe_pose={'position':pp.numpy().copy()[0].tolist(),'orientation_wxyz':pq.numpy().copy()[0].tolist()}
        return {'index':index,'before_step':before,'read_before':read_before,'read_after':clock(index,'read_after'),
            'q_rad':[float(q[i]) for i in indices],'qd_rad_s':[float(qd[i]) for i in indices],
            'links':poses,'probe_pose':probe_pose,'timeline_playing':bool(timeline.is_playing())}
    try:
        report['owner']={}
        _,getter=clock_owner(api,sim,omni,report['owner'])
        report['phase']='READING';write()
        physx=omni.physx.get_physx_interface()
        subscription=physx.subscribe_physics_on_step_events(post_step,False,0)
        need(subscription is not None,'Retained actual PhysX subscription')
        rows=[record(0,clock(0,'before_step'))]
        for index in range(1,11):
            before=clock(index,'before_step')
            sim.step(render=False)
            rows.append(record(index,before))
            # Reject a stale/reversed native clock immediately, before another step.
            need(abs(rows[-1]['read_after']['engine_time_s']-rows[0]['read_after']['engine_time_s']-index/120)<=1e-6,'Actual native engine time progression')
            need(rows[-1]['read_before']==rows[-1]['read_after'],'Stable native clock during tensor reads')
        state['engine_event_index']=observed['count']
        report.update(status='READY',phase='TRACE_COMPLETE')
        check_clock(report,rows,api['run'].name,report['job_sha256'],os.getpid(),api['cfg'],api['read'](api['run']/'output/physics-binding.json'),need)
        return {'rows':rows}
    except Exception as exc:
        report.update(status='FAILED',primary_error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            if subscription is not None:subscription.unsubscribe()
        except Exception as exc:
            report.update(status='FAILED',cleanup_error=f'{type(exc).__name__}: {exc}')
            # A pending query/trace exception remains the primary cause.
            # Cleanup alone still fails the lifecycle and supplies its cause.
            if 'primary_error' not in report:
                report['primary_error']=report['cleanup_error']
                raise
        finally:write()


def collect_contact(state):
    reader=state['contact_reader'];view=reader.view
    return {'mapping':reader.mapping,'sample':reader.read(1/120),'engine_event_index':state['engine_event_index'],
            'sensor_count':int(view.sensor_count),'filter_count':int(view.filter_count),'capacity':int(view.max_contact_data_count)}


COLLECTORS={'static':collect_static,'bodies':collect_bodies,'trace':collect_trace,'contact':collect_contact}


def collect(api):
    bindings(api)
    state=setup(api);facets={};out=api['run']/'output'
    for name in api['contract']['facets']:
        value=COLLECTORS[name](state)
        api['need'](type(value) is dict and set(value)==set(api['contract']['required_fields'][name]),'Collected facet schema '+name)
        facets[name]=value
        api['write'](out/'observations.partial.json',{'completed':list(facets),'facets':facets})
    packet={'run_id':api['run'].name,'job_sha256':api['sha'](api['run']/'job.json'),'pid':os.getpid(),
            'usd_sha256':api['job']['inputs']['data/model.usda'],'facets':facets}
    api['write'](out/'observations.json',packet,True)
    api['validate_observations'](packet)
    collect_gravity(api,state,packet)
    api['write'](out/'providers.json',{'pid':os.getpid(),'job_sha256':packet['job_sha256'],
        'numeric_before':api['numeric_before'],'numeric_after':api['lib']['providers'].numeric(api),'frameworks':api['frameworks']},True)


def gravity_frames(s, rows, api):
    k=api['kernel'];need=k.need;integer=k.integer;number=k.number;deep_equal=k.deep_equal;vector=k.vector;quaternion=k.quaternion;frame=k.frame;error=k.error;mm=k.mm;mv=k.mv
    DT=1/120;CALLBACK_DT=__import__('struct').unpack('f',__import__('struct').pack('f',DT))[0];IDENTITY=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
    need(type(rows) is list and len(rows)==241,'All241 gravity observations')
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
        # Hold thresholds are a dynamics result, separate from observation integrity.
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
        probe=row['probe_pose'];vector(probe['position']);quaternion(probe['orientation_wxyz'])
    return maxima


def contact_component_interval(matrix,terms,need):
    import struct
    def half_ulp(value):
        need(type(value) in (int,float) and math.isfinite(value) and abs(value)<=3.4028234663852886e38,'Finite float32 contact observation')
        need(struct.unpack('f',struct.pack('f',value))[0]==value,'Exact float32 contact observation')
        return 2.**-150 if abs(value)<2.**-126 else math.ldexp(1.,math.frexp(abs(value))[1]-25)
    budget=1e-6+half_ulp(matrix);reconstructed=0.
    for force,normal in terms:
        df,dn=half_ulp(force),half_ulp(normal);reconstructed+=force*normal
        budget+=abs(force)*dn+abs(normal)*df+df*dn
    need(budget<=1e-4,'Contact numerical resolution budget insufficient')
    residual=abs(matrix-reconstructed)
    need(residual<=budget,'Contact matrix and scalar-normal float32 intervals disagree')
    return {'residual_N':residual,'budget_N':budget,'legacy_absolute_pass':residual<=1e-6}


def gravity_contact(value,baseline,api,index):
    k=api['kernel'];need=k.need;number=k.number;vector=k.vector;DT=1/120
    golden=baseline['facets']['contact']['mapping']
    mapping=value['mapping'];sensors,filters=golden['canonical_sensors'],golden['canonical_filters']
    need(set(mapping)==set(golden),'Complete live contact mapping schema')
    need(mapping['canonical_sensors']==sensors and mapping['canonical_filters']==filters and mapping['capacity']==512 and
         mapping['force_frame']=='WORLD' and mapping['force_units']=='N','Live contact canonical identity/units/capacity')
    need(len(mapping['sensor_paths'])==8 and set(mapping['sensor_paths'])==set(sensors),'All unique actual sensor indices')
    need(len(mapping['filter_paths'])==8 and all(len(row)==9 and set(row)==set(filters) for row in mapping['filter_paths']),'All actual per-sensor filter indices')
    need(value['sensor_count']==8 and value['filter_count']==9 and value['capacity']==512 and
         type(value['engine_event_index']) is int and value['engine_event_index']==index,'Actual view dimensions and final event')
    sample=value['sample'];need(set(sample)=={'normal_force_N','counts','active','dt_s'} and abs(number(sample['dt_s'],'contact dt')-DT)<1e-10,'Actual contact sample schema/dt')
    force,counts=sample['normal_force_N'],sample['counts']
    need(type(force) is list and len(force)==8 and type(counts) is list and len(counts)==8,'Eight contact rows')
    for frow,crow in zip(force,counts):
        need(type(frow) is list and len(frow)==9 and type(crow) is list and len(crow)==9,'Nine contact filters per row')
        for f,c in zip(frow,crow):
            vector(f);need(type(c) is int and 0<=c<512,'Actual contact count range')
    need(type(sample['active']) is list and len(sample['active'])==sum(sum(r) for r in counts)<512,'Complete actual contact buffer')
    tally=[[0]*9 for _ in range(8)];reconstructed=[[[0.]*3 for _ in range(9)] for _ in range(8)]
    for item in sample['active']:
        need(set(item)=={'sensor','filter','force_N','point','normal','separation_m'},'Complete active contact schema')
        i,j=item['sensor'],item['filter'];need(type(i) is int and 0<=i<8 and type(j) is int and 0<=j<9,'Canonical active contact indices')
        need(number(item['force_N'],'force')>=0,'Contact force sign');number(item['separation_m'],'separation');vector(item['point']);vector(item['normal'])
        tally[i][j]+=1
        for axis in range(3):reconstructed[i][j][axis]+=item['force_N']*item['normal'][axis]
    need(tally==counts,'All active contacts match each canonical count')
    stats={'maximum_residual_N':0.,'maximum_budget_N':0.,'legacy_absolute_pass':True}
    for i in range(8):
        for j in range(9):
            for axis in range(3):
                terms=[(item['force_N'],item['normal'][axis]) for item in sample['active'] if item['sensor']==i and item['filter']==j]
                comparison=contact_component_interval(force[i][j][axis],terms,need)
                stats['maximum_residual_N']=max(stats['maximum_residual_N'],comparison['residual_N']);stats['maximum_budget_N']=max(stats['maximum_budget_N'],comparison['budget_N']);stats['legacy_absolute_pass']&=comparison['legacy_absolute_pass']
    return stats


GRAVITY=[0.,0.,-9.81]
G_STEPS=240

def gravity_math(static,poses,k):
    bodies={b['name']:b for b in static['bodies']};links={p['name']:p for p in poses}
    k.need(len(poses)==7 and set(links)==set(LINKS),'Actual seven LINK gravity inputs')
    pose={n:(k.vector(links[n]['position']),k.quaternion(links[n]['orientation_wxyz'])) for n in LINKS}
    by_path={b['path']:b['name'] for b in bodies.values()};joints={j['name']:j for j in static['joints'] if j['type']=='revolute'}
    def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    result=[]
    for i,name in enumerate(JOINTS):
        joint=joints[name];pos,rot=pose[by_path[joint['body0']]]
        anchor=k.add(pos,k.mv(rot,joint['local_pos0']));axis=k.mv(k.mm(rot,k.quaternion(joint['local_rot0_wxyz'])),[float(joint['axis']==x) for x in 'XYZ'])
        tau=0.
        for child in LINKS[i+1:]:
            b=bodies[child];point,r=pose[child];com=k.add(point,k.mv(r,b['com']));force=[b['mass']*x for x in GRAVITY]
            tau-=sum(a*b for a,b in zip(axis,cross([x-y for x,y in zip(com,anchor)],force)))
        result.append(k.number(tau,'gravity torque'))
    return result



G_API_MODULE='isaacsim.core.experimental.prims.impl.articulation'

def map_generalized(shape,full,names,need):
    need(type(shape) is list and len(shape)==2 and all(type(x) is int for x in shape) and shape[0]==1 and shape[1] in (6,12),'Supported complete generalized force shape')
    need(type(names) is list and len(names)==6 and all(type(n) is str for n in names) and set(names)==set(JOINTS),'Six unique actual native DOF names')
    need(type(full) is list and len(full)==shape[1] and all(type(v) in (int,float) and math.isfinite(v) for v in full),'Finite full generalized force values')
    offset=shape[1]-6;columns=[offset+names.index(n) for n in JOINTS]
    return {'native_full':full[:],'native_shape':shape[:],'native_offset':offset,'native_layout':'DOFS_ONLY' if offset==0 else 'ROOT_WRENCH_THEN_DOFS',
        'native_root_wrench':full[:offset],'native_dof_names':names[:],'native_columns':columns,'native':[full[j] for j in columns]}

def gravity_api_identity(robot,physics,need):
    method=robot.get_dof_gravity_compensation_forces;cls=type(robot);func=getattr(method,'__func__',None)
    need(cls.__module__==G_API_MODULE and cls.__qualname__=='Articulation','Pinned gravity Articulation class')
    need(func is not None and method.__self__ is robot and func is cls.get_dof_gravity_compensation_forces and func.__module__==G_API_MODULE and func.__name__=='get_dof_gravity_compensation_forces','Actual gravity method binding')
    path=Path(func.__code__.co_filename).resolve();source={'origin':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()};expected=physics['sources'][G_API_MODULE]
    need(path==Path(expected['origin']).resolve() and source['sha256']==expected['sha256'],'Gravity method belongs to pinned physics source')
    return {'module':cls.__module__,'class':cls.__qualname__,'method':func.__name__,'bound_identity':True,'source':source,'paths':list(robot.paths),'dof_names':list(robot.dof_names)}



def retain_error(primary,extra,label):
    if primary is None:return extra
    if extra is not primary:primary.add_note(f'{label}: {type(extra).__name__}: {extra}')
    return primary


def atomic_json(path,value):
    path=Path(path);raw=json.dumps(value,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')+b'\n'
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent);primary=None
    try:
        offset=0
        while offset<len(raw):
            count=os.write(fd,raw[offset:])
            if count<=0:raise OSError('Incomplete atomic write')
            offset+=count
        os.fsync(fd)
    except BaseException as exc:primary=exc
    try:os.close(fd)
    except Exception as exc:primary=retain_error(primary,exc,'Atomic descriptor close')
    if primary is None:
        try:os.replace(name,path)
        except Exception as exc:primary=exc
    try:Path(name).unlink(missing_ok=True)
    except Exception as exc:primary=retain_error(primary,exc,'Atomic temp cleanup')
    if primary is not None:raise primary
    return hashlib.sha256(raw).hexdigest()


def gravity_header(report):return {n:v for n,v in report.items() if n not in ('rows','pending_native')}


class GravityJournal:
    def __init__(self,out,report):
        self.out=Path(out);self.stream=(self.out/'gravity-journal.ndjson').open('xb')
        self.identity={n:report[n] for n in ('run_id','job_sha256','pid')}
        self.sequence=-1;self.head=None;self.byte_count=0;self.row_count=0;self.last_index=None;self.report_hash=None
        self.report_publications=0;self.max_checkpoint_bytes=0;self.row_payload_bytes=0
        try:self.checkpoint(report)
        except BaseException as primary:
            try:self.stream.close()
            except Exception as extra:retain_error(primary,extra,'Initial journal close')
            raise
    def append(self,kind,payload):
        record={'schema_version':1,**self.identity,'sequence':self.sequence+1,'previous_sha256':self.head,'kind':kind,'payload':payload}
        raw=json.dumps(record,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')+b'\n'
        if self.stream.write(raw)!=len(raw):raise OSError('Incomplete journal append')
        self.stream.flush();os.fsync(self.stream.fileno())
        self.sequence+=1;self.head=hashlib.sha256(raw).hexdigest();self.byte_count+=len(raw)
        if kind=='ROW':self.row_payload_bytes+=len(raw)
    def checkpoint(self,report):
        value={'schema_version':1,**self.identity,'status':report['status'],'phase':report['phase'],
            'row_count':self.row_count,'last_index':self.last_index,'last_sequence':self.sequence,'last_record_sha256':self.head,
            'journal_bytes':self.byte_count,'pending_native':report.get('pending_native'),'header':gravity_header(report),'report_sha256':self.report_hash}
        self.max_checkpoint_bytes=max(self.max_checkpoint_bytes,len(json.dumps(value)))
        atomic_json(self.out/'gravity-checkpoint.json',value)
    def ready(self,report):self.append('HEADER',gravity_header(report))
    def row(self,report,row):
        self.append('ROW',row);self.row_count+=1;self.last_index=row['index'];self.checkpoint(report)
    def finish(self,report):
        self.report_hash=atomic_json(self.out/'gravity-report.json',report);self.report_publications+=1
        if report['status']=='COLLECTED':
            self.append('COMPLETE',{'report_sha256':self.report_hash,'row_count':self.row_count,'last_index':self.last_index})
        self.checkpoint(report)
    def close(self):self.stream.close()


def check_journal(raw,checkpoint,report,report_hash,need):
    need(type(raw) is bytes and raw.endswith(b'\n'),'Complete newline-terminated journal')
    identity={n:report[n] for n in ('run_id','job_sha256','pid')};previous=None;rows=[];records=[]
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'Duplicate journal JSON key');result[key]=value
        return result
    for i,line in enumerate(raw.splitlines(keepends=True)):
        need(line.endswith(b'\n'),'Complete journal line')
        value=json.loads(line.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite journal JSON')))
        need(type(value) is dict and set(value)=={'schema_version',*identity,'sequence','previous_sha256','kind','payload'},'Closed journal record')
        need(type(value['schema_version']) is int and value['schema_version']==1 and type(value['sequence']) is int and value['sequence']==i and value['previous_sha256']==previous,'Journal sequence/hash chain')
        need(all(value[n]==v and type(value[n]) is type(v) for n,v in identity.items()),'Journal run/job/PID binding')
        previous=hashlib.sha256(line).hexdigest();records.append(value)
    need(len(records)==243,'Exact HEADER/241ROW/COMPLETE record count')
    header=dict(records[0]['payload']);need(records[0]['kind']=='HEADER' and header['status']=='BUILDING' and header['phase']=='GRAVITY_COLLECTING','Ready collecting journal header')
    header.update(status='COLLECTED',phase='GRAVITY_COMPLETE');need(header==gravity_header(report),'Journal/final report header agreement')
    for i,value in enumerate(records[1:-1]):
        need(value['kind']=='ROW' and type(value['payload']) is dict and type(value['payload']['index']) is int and value['payload']['index']==i,'Journal rows contiguous exactly once')
        rows.append(value['payload'])
    need(rows==report['rows'],'Journal rows equal final full report')
    need(records[-1]['kind']=='COMPLETE' and records[-1]['payload']=={'report_sha256':report_hash,'row_count':241,'last_index':240},'Complete binds actual full report')
    need(type(checkpoint) is dict and set(checkpoint)=={'schema_version',*identity,'status','phase','row_count','last_index','last_sequence','last_record_sha256','journal_bytes','pending_native','header','report_sha256'},'Closed final checkpoint')
    need(type(checkpoint['schema_version']) is int,'Integer checkpoint schema')
    need(checkpoint=={'schema_version':1,**identity,'status':'COLLECTED','phase':'GRAVITY_COMPLETE','row_count':241,'last_index':240,'last_sequence':242,'last_record_sha256':previous,'journal_bytes':len(raw),'pending_native':None,'header':gravity_header(report),'report_sha256':report_hash},'Final checkpoint agrees with complete journal/report')
    return {'records':243,'rows':241,'bytes':len(raw),'last_record_sha256':previous}


def collect_gravity(api,state,baseline):
    import carb
    sim,robot,backend,links,probe,indices,omni=(state[n] for n in ('sim','robot','backend','links','probe','indices','omni'))
    need=api['need'];out=api['run']/'output';target=out/'gravity-report.json';k=api['kernel']
    view=sim.physics_manager.get_physics_sim_view();observed={'count':0,'time':0.};subscription=None
    report={'schema_version':1,'run_id':api['run'].name,'job_sha256':api['sha'](api['run']/'job.json'),'pid':os.getpid(),'status':'BUILDING','phase':'GRAVITY_SETUP','hardware_approved':False,'mode':'NATIVE_FF_ZERO_PD_2S','view_id':id(view),'clock_owner':{},'native_api':{},'base_binding':{},'pending_native':None,'gravity_before':None,'rows':[],'contact_mapping':state['contact_reader'].mapping,'dimensions':{'sensor_count':int(state['contact_reader'].view.sensor_count),'filter_count':int(state['contact_reader'].view.filter_count),'capacity':int(state['contact_reader'].view.max_contact_data_count)}}
    journal=GravityJournal(out,report)
    write=lambda:journal.checkpoint(report)
    def post_step(dt):observed['count']+=1;observed['time']+=float(dt)
    def clock():
        return {'lab_step':int(sim.get_physics_step_count()),'engine_event_index':observed['count'],'engine_time_s':clock_number(getter(),need),'callback_time_s':observed['time']}
    def six(value):
        raw=value.numpy().copy();need(raw.shape==(1,6),'Actual named fixed-base six-force columns');return raw[0].tolist()
    def capture(i,before,actuation):
        pre=clock()
        with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
            q,qd=six(robot.get_dof_positions(dof_indices=indices)),six(robot.get_dof_velocities(dof_indices=indices))
            poses=[]
            for name,link in zip(LINKS,links):
                pos,rot=link.get_world_poses();poses.append({'name':name,'position':pos.numpy().copy()[0].tolist(),'orientation_wxyz':rot.numpy().copy()[0].tolist()})
            pp,pq=probe.get_world_poses();probe_pose={'position':pp.numpy().copy()[0].tolist(),'orientation_wxyz':pq.numpy().copy()[0].tolist()}
            kp,kd=robot.get_dof_gains(dof_indices=indices)
            flags=robot.get_link_enabled_gravities().numpy().copy()[0].tolist();probe_flags=probe.get_enabled_gravities().numpy().copy().reshape(-1).tolist()
            configuration={'gravity':[float(v) for v in view.get_gravity()],'link_names':list(robot.link_names),'link_enabled':flags,'probe_enabled':probe_flags,'kp':six(kp),'kd':six(kd),'effort':six(robot.get_dof_max_efforts(dof_indices=indices))}
        contact=state['contact_reader'].read(1/120)
        after=clock();need(pre==after,'Same gravity sample clock during tensor/contact reads')
        return {'index':i,'before_step':before,'read_before':pre,'read_after':after,'q_rad':q,'qd_rad_s':qd,'links':poses,'probe_pose':probe_pose,'timeline_playing':bool(state['timeline'].is_playing()),'configuration':configuration,'actuation':actuation,'contact':contact}
    try:
        _,getter=clock_owner(api,sim,omni,report['clock_owner'])
        need(report['clock_owner']==api['read'](out/'clock-report.json')['owner'],'Same baseline native clock owner')
        report['native_api']=gravity_api_identity(robot,api['read'](out/'physics-binding.json'),need)
        need(report['native_api']['dof_names']==baseline['facets']['bodies']['dof_names'],'Same actual DOF names across phases')
        report['gravity_before']=[float(x) for x in view.get_gravity()]
        view.set_gravity(carb.Float3(*GRAVITY))
        subscription=omni.physx.get_physx_interface().subscribe_physics_on_step_events(post_step,False,0)
        need(subscription is not None,'Retained gravity phase post-step subscription')
        report['phase']='GRAVITY_COLLECTING';report['rows'].append(capture(0,clock(),None))
        report['base_binding']={'source_fixed_joints':[j for j in baseline['facets']['static']['joints'] if j['type']=='fixed'],'actual_base_pose_at_start':next(x for x in report['rows'][0]['links'] if x['name']=='Base')};journal.ready(report);journal.row(report,report['rows'][0])
        for i in range(1,G_STEPS+1):
            before=clock()
            with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
                report['pending_native']={'stage':'QUERY_REQUESTED','source_index':i-1,'read_clock':before};write()
                native_tensor=robot.get_dof_gravity_compensation_forces();native_shape=[int(x) for x in native_tensor.shape]
                report['pending_native'].update(stage='SHAPE_OBSERVED',native_shape=native_shape);write()
                full=native_tensor.numpy().copy().reshape(-1).tolist();names=list(robot.dof_names)
                finite=all(type(x) in (int,float) and math.isfinite(x) for x in full)
                report['pending_native']={'stage':'RAW','source_index':i-1,'read_clock':before,'native_shape':native_shape,'native_full':full if finite else None,'native_repr':[repr(x) for x in full],'finite':finite,'native_dof_names':names};write()
                mapped=map_generalized(native_shape,full,names,need)
                need(names==report['native_api']['dof_names'],'Actual gravity DOF names remained unchanged')
                reference=gravity_math(baseline['facets']['static'],report['rows'][-1]['links'],k);delta=k.error(mapped['native'],reference)
                report['pending_native'].update(stage='MAPPED',mapping=mapped,math_reference=reference,maximum_difference_Nm=delta);write()
                need(delta<=1e-3,'Native gravity mapping agrees with actual LINK/COM before command')
                native=mapped['native']
                command=[max(-cap,min(cap,x)) for cap,x in zip(api['cfg']['cap_Nm'],native)]
                robot.set_dof_efforts([command],dof_indices=indices)
                readback=six(robot.get_dof_efforts(dof_indices=indices))
            act={'source_index':i-1,'read_clock':before,**mapped,'math':reference,'command':command,'readback':readback,'saturated':[abs(x)>cap for x,cap in zip(native,api['cfg']['cap_Nm'])]}
            need(clock()==before,'Gravity command belongs to pre-step observation')
            sim.step(render=False)
            row=capture(i,before,act);report['rows'].append(row);report['pending_native']=None
            need(abs(row['read_after']['engine_time_s']-report['rows'][0]['read_after']['engine_time_s']-i/120)<=1e-6,'Native gravity phase engine progression')
            journal.row(report,row)
        report.pop('pending_native');report.update(status='COLLECTED',phase='GRAVITY_COMPLETE')
        check_gravity(report,baseline,api['read'](out/'clock-report.json'),api,api['read'](out/'physics-binding.json'))
    except Exception as exc:
        report.update(status='FAILED',primary_error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            if subscription is not None:subscription.unsubscribe()
        except Exception as exc:
            report.update(status='FAILED',cleanup_error=f'{type(exc).__name__}: {exc}')
            if 'primary_error' not in report:report['primary_error']=report['cleanup_error'];raise
        finally:
            original_error=sys.exception();primary=original_error;finalization_failed=False
            def failed(exc,label):
                nonlocal primary,finalization_failed
                finalization_failed=True;report[label]=f'{type(exc).__name__}: {exc}'
                if primary is None:report.update(status='FAILED',primary_error=f'{type(exc).__name__}: {exc}')
                primary=retain_error(primary,exc,label)
            try:journal.finish(report)
            except Exception as exc:failed(exc,'publication_error')
            try:journal.close()
            except Exception as exc:failed(exc,'journal_close_error')
            if finalization_failed:
                try:journal.report_hash=atomic_json(target,report)
                except Exception as exc:primary=retain_error(primary,exc,'Failure report publication')
                try:journal.checkpoint(report)
                except Exception as exc:primary=retain_error(primary,exc,'Failure checkpoint publication')
            if original_error is None and primary is not None:raise primary


def check_gravity(value,baseline,clock_report,api,physics):
    k=api['kernel'];need=k.need;rows=value['rows'];static=baseline['facets']['static'];caps=list(api['cfg']['cap_Nm'])
    need(set(value)=={'schema_version','run_id','job_sha256','pid','status','phase','hardware_approved','mode','view_id','clock_owner','native_api','base_binding','gravity_before','rows','contact_mapping','dimensions'},'Closed gravity report')
    need(value['schema_version']==1 and value['run_id']==baseline['run_id']==api['run'].name and value['job_sha256']==baseline['job_sha256']==api['sha'](api['run']/'job.json') and type(value['pid']) is int and value['pid']==baseline['pid']==clock_report['pid'],'Gravity run/job/process binding')
    need(value['status']=='COLLECTED' and value['phase']=='GRAVITY_COMPLETE' and value['hardware_approved'] is False and value['mode']=='NATIVE_FF_ZERO_PD_2S','Complete gravity experiment without hardware')
    need(type(value['view_id']) is int and value['view_id']==physics['lab_view_id'],'Same validated Lab gravity view')
    need(value['clock_owner']==clock_report['owner'] and k.error(k.vector(value['gravity_before']),[0,0,0])<=1e-6,'Baseline owner and zero gravity transition')
    identity=value['native_api'];need(set(identity)=={'module','class','method','bound_identity','source','paths','dof_names'},'Complete native gravity API identity')
    need(identity['module']==G_API_MODULE and identity['class']=='Articulation' and identity['method']=='get_dof_gravity_compensation_forces' and identity['bound_identity'] is True,'Pinned actual gravity method')
    expected_source=physics['sources'][G_API_MODULE];need(set(identity['source'])=={'origin','sha256'} and Path(identity['source']['origin']).resolve()==Path(expected_source['origin']).resolve() and identity['source']['sha256']==expected_source['sha256'],'Pinned gravity method source evidence')
    need(identity['paths']==next(p['paths'] for p in physics['prims'] if p['type']=='Articulation') and identity['dof_names']==baseline['facets']['bodies']['dof_names'],'Same Articulation and actual DOF sequence')
    need(set(value['base_binding'])=={'source_fixed_joints','actual_base_pose_at_start'},'Separate base constraint and actual pose evidence')
    k.deep_equal(value['base_binding']['source_fixed_joints'],[j for j in static['joints'] if j['type']=='fixed'],'Source fixed joint graph')
    k.deep_equal(value['base_binding']['actual_base_pose_at_start'],next(x for x in rows[0]['links'] if x['name']=='Base'),'Actual base pose')
    need(value['dimensions']=={'sensor_count':8,'filter_count':9,'capacity':512},'Actual complete gravity contact dimensions')
    need(type(rows) is list and len(rows)==241,'Complete240-step gravity trace')
    end=baseline['facets']['trace']['rows'][-1]
    for field in ('q_rad','qd_rad_s','links','probe_pose'):k.deep_equal(rows[0][field],end[field],'Continuous baseline/gravity '+field,1e-10)
    need(rows[0]['read_after']['lab_step']==end['read_after']['lab_step'] and abs(rows[0]['read_after']['engine_time_s']-end['read_after']['engine_time_s'])<=1e-10,'Same absolute Lab/native time at gravity transition')
    metrics=gravity_frames(static,rows,api)
    metrics.update(contact_comparison='FLOAT32_INTERVAL_COMPATIBILITY_V1',contact_maximum_residual_N=0.,contact_maximum_budget_N=0.,contact_legacy_absolute_pass=True,torque_difference_Nm=0.,command_difference_Nm=0.,unwanted_force_N=0.,probe_floor_peak_N=0.,probe_drop_m=0.,probe_settled_error_m=0.,saturated=False,qd_difference_from_finite_difference_rad_s=0.)
    initial_z=k.vector(rows[0]['probe_pose']['position'])[2]
    for i,row in enumerate(rows):
        need(set(row)=={'index','before_step','read_before','read_after','q_rad','qd_rad_s','links','probe_pose','timeline_playing','configuration','actuation','contact'},'Closed gravity row')
        cfg=row['configuration'];need(set(cfg)=={'gravity','link_names','link_enabled','probe_enabled','kp','kd','effort'},'Complete actual gravity/drive states')
        need(k.error(k.vector(cfg['gravity']),GRAVITY)<=1e-6 and len(cfg['link_names'])==7 and set(cfg['link_names'])==set(LINKS) and len(cfg['link_enabled'])==7 and all(x is True for x in cfg['link_enabled']) and cfg['probe_enabled']==[True],'Actual backend gravity and all actor gravity flags')
        k.deep_equal(cfg['kp'],[0]*6);k.deep_equal(cfg['kd'],[0]*6);k.deep_equal(cfg['effort'],caps)
        if i==0:need(row['actuation'] is None,'No step0 gravity command')
        else:
            act=row['actuation'];need(set(act)=={'source_index','read_clock','native','native_full','native_shape','native_offset','native_layout','native_root_wrench','native_dof_names','native_columns','math','command','readback','saturated'} and type(act['source_index']) is int and act['source_index']==i-1 and act['read_clock']==row['before_step'],'Previous actual state owns gravity command')
            shape=act['native_shape'];need(type(shape) is list and len(shape)==2 and all(type(x) is int for x in shape) and shape[0]==1 and shape[1] in (6,12),'Complete supported generalized layout')
            names=act['native_dof_names'];need(type(names) is list and len(names)==6 and set(names)==set(JOINTS) and names==identity['dof_names'],'Actual unique native DOF sequence')
            offset=0 if shape[1]==6 else 6;columns=[offset+names.index(n) for n in JOINTS]
            need(type(act['native_offset']) is int and act['native_offset']==offset and act['native_layout']==('DOFS_ONLY' if offset==0 else 'ROOT_WRENCH_THEN_DOFS'),'Independently derived generalized offset')
            need(act['native_columns']==columns and all(type(x) is int for x in act['native_columns']),'Named absolute generalized force columns')
            full=k.vector(act['native_full'],shape[1]);native=k.vector(act['native'],6);need(k.vector(act['native_root_wrench'],offset)==full[:offset] and native==[full[j] for j in columns],'Full native/prefix/canonical force binding')
            expected=gravity_math(static,rows[i-1]['links'],k);math_claim=k.vector(act['math'],6)
            need(k.error(math_claim,expected)<=1e-9,'Root-recomputed gravity reference')
            need(k.error(native,expected)<=1e-3,'Eligible native mapping before dispatched command')
            command=[max(-cap,min(cap,x)) for cap,x in zip(caps,native)];readback=k.vector(act['readback'],6)
            need(k.error(k.vector(act['command'],6),command)<=1e-9 and all(abs(x-y)<=1e-6+abs(x)*1e-5 for x,y in zip(command,readback)),'Actual gravity effort command/readback within unchanged cap')
            saturation=[abs(x)>cap for x,cap in zip(native,caps)];need(act['saturated']==saturation and all(type(x) is bool for x in act['saturated']),'Observed native torque saturation')
            metrics['saturated']|=any(saturation);metrics['torque_difference_Nm']=max(metrics['torque_difference_Nm'],k.error(native,expected));metrics['command_difference_Nm']=max(metrics['command_difference_Nm'],k.error(command,readback))
            metrics['qd_difference_from_finite_difference_rad_s']=max(metrics['qd_difference_from_finite_difference_rad_s'],max(abs((q-p)*120-v) for q,p,v in zip(row['q_rad'],rows[i-1]['q_rad'],row['qd_rad_s'])))
        contact={'mapping':value['contact_mapping'],'sample':row['contact'],'engine_event_index':i,**value['dimensions']}
        contact_stats=gravity_contact(contact,baseline,api,i)
        metrics['contact_maximum_residual_N']=max(metrics['contact_maximum_residual_N'],contact_stats['maximum_residual_N']);metrics['contact_maximum_budget_N']=max(metrics['contact_maximum_budget_N'],contact_stats['maximum_budget_N']);metrics['contact_legacy_absolute_pass']&=contact_stats['legacy_absolute_pass']
        forces=row['contact']['normal_force_N']
        for si in range(8):
            for fi in range(9):
                norm=math.sqrt(sum(x*x for x in forces[si][fi]))
                if si==7 and fi==0:metrics['probe_floor_peak_N']=max(metrics['probe_floor_peak_N'],norm)
                elif not(si==0 and fi==0):metrics['unwanted_force_N']=max(metrics['unwanted_force_N'],norm)
        z=k.vector(row['probe_pose']['position'])[2];metrics['probe_drop_m']=max(metrics['probe_drop_m'],initial_z-z)
        if i>=120:metrics['probe_settled_error_m']=max(metrics['probe_settled_error_m'],abs(z-.025))
    metrics['checks']={'hold':metrics['angle_rad']<=math.radians(.5) and metrics['speed_rad_s']<=math.radians(1),'native_math':metrics['torque_difference_Nm']<=1e-3,'unsaturated':not metrics['saturated'],'no_unwanted_contact':metrics['unwanted_force_N']<=1e-3,'probe_drop':metrics['probe_drop_m']>=.05,'probe_settled':metrics['probe_settled_error_m']<=.002,'probe_contact_positive':metrics['probe_floor_peak_N']>.1}
    metrics['dynamics_pass']=all(metrics['checks'].values())
    return metrics
