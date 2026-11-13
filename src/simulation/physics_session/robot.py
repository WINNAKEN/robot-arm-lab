if __name__=='__main__':
    raise SystemExit('Use launch.ps1; direct execution is forbidden')

import os
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
        names=('observations.json','scene.usda','providers.json','sdk.json','physics-binding.json')
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


def collect_trace(state):
    api,sim,timeline,backend,robot,indices,links,probe,omni=(state[k] for k in ('api','sim','timeline','backend','robot','indices','links','probe','omni'))
    need=api['need']
    observed={'count':0,'time':0.}
    def post_step(dt):
        observed['count']+=1;observed['time']+=float(dt)
    physx=omni.physx.get_physx_interface()
    subscription=physx.subscribe_physics_on_step_events(post_step,False,0)
    def clock():
        return {'lab_step':int(sim.get_physics_step_count()),'engine_event_index':observed['count'],
                'engine_time_s':float(physx.get_simulation_time()),'callback_time_s':observed['time']}
    def record(index,before):
        read_before=clock()
        with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
            q,qd=robot.get_dof_positions().numpy().copy()[0],robot.get_dof_velocities().numpy().copy()[0]
            poses=[]
            for name,link in zip(LINKS,links):
                p,r=link.get_world_poses()
                poses.append({'name':name,'position':p.numpy().copy()[0].tolist(),'orientation_wxyz':r.numpy().copy()[0].tolist()})
            pp,pq=probe.get_world_poses()
            probe_pose={'position':pp.numpy().copy()[0].tolist(),'orientation_wxyz':pq.numpy().copy()[0].tolist()}
        return {'index':index,'before_step':before,'read_before':read_before,'read_after':clock(),
            'q_rad':[float(q[i]) for i in indices],'qd_rad_s':[float(qd[i]) for i in indices],
            'links':poses,'probe_pose':probe_pose,'timeline_playing':bool(timeline.is_playing())}
    rows=[record(0,clock())]
    for index in range(1,11):
        before=clock()
        sim.step(render=False)
        rows.append(record(index,before))
    state['engine_event_index']=observed['count']
    need(subscription is not None,'Retained actual PhysX subscription')
    subscription.unsubscribe()
    return {'rows':rows}

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
