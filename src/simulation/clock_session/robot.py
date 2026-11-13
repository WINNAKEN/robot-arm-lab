if __name__=='__main__':
    raise SystemExit('Use launch.ps1; direct execution is forbidden')

import os
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
        names=('observations.json','scene.usda','providers.json','sdk.json','physics-binding.json','clock-report.json')
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
    api['write'](out/'providers.json',{'pid':os.getpid(),'job_sha256':packet['job_sha256'],
        'numeric_before':api['numeric_before'],'numeric_after':api['lib']['providers'].numeric(api),'frameworks':api['frameworks']},True)
    api['validate_observations'](packet)
