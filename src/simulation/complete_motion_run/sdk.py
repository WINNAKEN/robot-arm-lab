"""069A installed-SDK adapter. Only lifecycle() initializes the remote SDK."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

from driver import need, read, write, sha, load_module


def reference(ctx, name):
    return load_module('ref_'+name.replace('.','_'),ctx.data['ref/'+name],ctx.run/'input/ref'/name)


def start(ctx):
    cfg=ctx.cfg['sdk'];out=ctx.run/'output';k=reference(ctx,'kernel.py');ctx.kernel=k;k.sdk_initialize(cfg)
    for pin in ctx.cfg['sdk_source_pins']:
        need(sha(pin['path'])==pin['sha256'],'installed SDK adapter/render source changed')
    for key in ('scipy_root','numpy_root'):sys.path.insert(0,str(Path(cfg[key]).parent))
    numeric=reference(ctx,'numeric.py');policy=reference(ctx,'policy.py');observer=reference(ctx,'observer.py')
    ctx.policy=policy;ctx.observer=observer
    api={'run':ctx.run,'cfg':cfg,'need':need,'write':write,'read':read,'sha':sha,'check_numeric':lambda v:k.check_numeric(v,cfg,need),'check_frameworks':lambda v:k.check_frameworks(v,cfg),'lib':{'providers':numeric}}
    ctx.api=api;ctx.read=read;ctx.write=write;ctx.sha=sha
    before=numeric.numeric(api);write(out/'numeric-before.json',before)
    c=SimpleNamespace(run=ctx.run,cfg=cfg)
    observer.bind_preapp(c,policy,k,api);api['binding_before']=observer.identities();write(out/'binding-before.json',api['binding_before'])
    import isaacsim
    need(k.owned_origin(str(isaacsim.__file__),cfg['isaac_root']),'actual SDK origin')
    write(out/'sdk.json',numeric.sdk_record(api,str(Path(isaacsim.__file__).resolve())))
    app=isaacsim.SimulationApp({'headless':True,'fast_shutdown':True,'renderer':'RayTracedLighting','width':640,'height':480})
    ctx.app=app
    # Every observation is persisted by the unchanged observer before acceptance.
    observation=observer.observe(c,policy,'latest')
    policy.require_observation(observation,cfg)
    write(out/'providers.json',{'run_id':ctx.job['run_id'],'job_sha256':ctx.job_hash,'pid':os.getpid(),'before':api['binding_before'],'observation':observation})
    return app


def lifecycle(ctx, collector):
    """070: cleanup is independent of every diagnostic I/O boundary."""
    out=ctx.run/'output';app=None;code=1;phase='OUTPUT_DIRECTORY'
    terminal={'run_id':ctx.job['run_id'],'job_sha256':ctx.job_hash,'purpose':ctx.job['purpose'],'pid':os.getpid(),'parent_pid':os.getppid(),'hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN','status':'FAILED','code':1,'phase':'SDK_START'}
    state={'close_attempts':0,'close_result':'NOT_ATTEMPTED','close_system_exit_code':None,'body_completed':False}
    ctx.lifecycle_observation=state;ctx.lifecycle_terminal=terminal

    def text(exc):
        try:return type(exc).__name__+': '+str(exc)
        except BaseException:return type(exc).__name__+': <error formatting failed>'

    def fault(exc, where):
        # Memory only: this must never depend on a file, stderr, or error formatter.
        nonlocal code
        code=1;terminal.update(status='FAILED',code=1)
        value={'phase':where,'error':text(exc)}
        if not hasattr(ctx,'first_fault'):
            ctx.first_fault=value;ctx.first_fault_exception=exc
            terminal['primary_error']=value['error'];terminal['primary_phase']=where
        else:terminal.setdefault('secondary_errors',[]).append(value)

    def emit():
        # write and flush are separately guarded, even if both fail.
        try:sys.stderr.write(json.dumps({'first_fault':ctx.first_fault,'secondary_errors':terminal.get('secondary_errors',[])})+'\n')
        except BaseException as exc:fault(exc,'STDERR_WRITE')
        try:sys.stderr.flush()
        except BaseException as exc:fault(exc,'STDERR_FLUSH')

    def publish():
        for name in ('terminal.json','status.json'):
            try:write(out/name,terminal)
            except BaseException as exc:
                fault(exc,'PUBLISH_'+name);emit()

    try:
        try:
            out.mkdir(exist_ok=True)
            phase='INITIAL_STATUS';write(out/'status.json',terminal)
            phase='SDK_START';app=start(ctx)
            phase='COLLECTOR_STATUS';terminal['phase']='COLLECTING';write(out/'status.json',terminal)
            phase='COLLECTOR';collector(ctx,app)
            phase='POSTCHECK'
            cfg=ctx.cfg['sdk'];after=ctx.observer.identities();ctx.policy.binding_contract(ctx.api['binding_before'],after,'PREFIX_TORCH_PREAPP',read(out/'providers.json')['observation'])
            write(out/'binding-after.json',after)
            numeric=reference(ctx,'numeric.py');after_numeric=numeric.numeric(ctx.api);ctx.kernel.check_numeric(after_numeric,cfg,need);write(out/'numeric-after.json',after_numeric)
            phase='ARTIFACT_SEAL'
            excluded={'terminal.json','status.json','stdout.txt','stderr.txt','exit.json','remote-shell.json','child-started.json'}
            terminal['files_sha256']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.relative_to(out).as_posix() not in excluded}
            state['body_completed']=True
            terminal.update(status='COMPLETE_PRE_CLOSE',phase='CLOSING_APP',code=0);code=0
        except BaseException as exc:
            fault(exc,phase)
            try:(out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
            except BaseException as secondary:fault(secondary,'FAILURE_TEXT')
            emit()
        # Every operation above, including publication, remains inside the
        # independent cleanup boundary below.
        publish()
    finally:
        try:
            if app is None:app=getattr(ctx,'app',None)
            if app is not None:
                state['close_attempts']+=1;state['close_requested_code']=code
                try:
                    app.close(wait_for_replicator=False,exit_code=code)
                    state['close_result']='RETURNED'
                except SystemExit as exc:
                    raw=exc.code;state['close_result']='SYSTEM_EXIT';state['close_system_exit_code']=raw if type(raw) in (int,str,bool) or raw is None else text(exc)
                    if raw is not None and (type(raw) is not int or raw!=0):fault(exc,'APP_CLOSE_SYSTEM_EXIT');emit()
                except BaseException as exc:
                    state['close_result']='EXCEPTION';terminal['close_error']=text(exc);fault(exc,'APP_CLOSE');emit()
        except BaseException as exc:
            fault(exc,'APP_CLOSE_BOUNDARY');emit()
        finally:
            if code==0:terminal.update(status='CLOSED',phase='APP_CLOSED')
            terminal['code']=code
            publish()
    return code


def verify_records(ctx, folder, terminal):
    """Pure host consumer of sealed native observations; never initializes SDK."""
    k=reference(ctx,'kernel.py');policy=reference(ctx,'policy.py');cfg=ctx.cfg['sdk'];folder=Path(folder)
    sdk=read(folder/'sdk.json');provider=read(folder/'providers.json')
    need(sdk['pid']==provider['pid']==terminal['pid'] and sdk['job_sha256']==provider['job_sha256']==ctx.job_hash and provider['run_id']==ctx.job['run_id'],'observed provider direct native PID/job')
    need(sdk['version']==cfg['isaac_version'] and k.owned_origin(sdk['isaacsim_origin'],cfg['isaac_root']) and sdk['bootstrap_sha256']=={n:v['sha256'] for n,v in cfg['sdk_files'].items()},'observed pinned SDK')
    for name in ('numeric-before.json','numeric-after.json'):k.check_numeric(read(folder/name),cfg,need)
    before=read(folder/'binding-before.json');after=read(folder/'binding-after.json')
    need(provider['before']==before,'provider pre-app identity binding')
    policy.require_observation(provider['observation'],cfg)
    policy.binding_contract(before,after,'PREFIX_TORCH_PREAPP',provider['observation'])
    return {'provider':'OBSERVED_AND_RECHECKED','numeric':'SDK_PINNED_BEFORE_AFTER','binding':'SAME_MODULES','cuda':'ACTUAL_GPU_SUM_6'}


def enable(name):
    import omni.kit.app
    root=Path(os.environ['ISAAC_PATH']);found=False
    for base in (root/'exts',root/'extscache',root/'kit/exts',root/'kit/extscache'):
        if base.is_dir() and any(p.is_dir() and (p.name==name or p.name.startswith(name+'-')) and (p/'config/extension.toml').is_file() for p in base.iterdir()):found=True
    need(found,'required extension not locally installed: '+name)
    manager=omni.kit.app.get_app().get_extension_manager();need(manager.set_extension_enabled_immediate(name,True) is not False,'enable installed extension: '+name)


def _pose(cache, prim):
    from pxr import Gf
    T=cache.GetLocalToWorldTransform(prim)
    return [float(x) for x in T.ExtractTranslation()],[[float(T[j][i]) for j in range(3)] for i in range(3)]


def _world_role(cache, prim, path):
    """Observe a USD prim role; full Gf matrices retain native row-vector rows."""
    from pxr import UsdPhysics
    exists=bool(prim)
    samples={}
    if exists:
        for attr in prim.GetAttributes():
            name=str(attr.GetName())
            if name=='xformOpOrder' or name.startswith('xformOp:'):
                samples[name]=[float(t) for t in attr.GetTimeSamples()]
        matrix=cache.GetLocalToWorldTransform(prim)
        world_matrix=[[float(matrix[i][j]) for j in range(4)] for i in range(4)]
    else:world_matrix=None
    return {'path':path,'exists':exists,'type':str(prim.GetTypeName()) if exists else None,
            'applied_schemas':[str(s) for s in prim.GetAppliedSchemas()] if exists else [],
            'active':bool(prim.IsActive()) if exists else False,'defined':bool(prim.IsDefined()) if exists else False,
            'rigid_body':bool(prim.HasAPI(UsdPhysics.RigidBodyAPI)) if exists else False,
            'mass_api':bool(prim.HasAPI(UsdPhysics.MassAPI)) if exists else False,
            'world_matrix':world_matrix,'matrix_convention':'GfMatrix4d_ROW_VECTOR_ROWS',
            'time_samples':sum(len(values) for values in samples.values()),'xform_time_samples':samples}


def _world_anchors(stage, cache, body_paths, joints):
    anchors={}
    for row in joints:
        target=row['body0']
        if target is None or target in body_paths or target in anchors:continue
        prim=stage.GetPrimAtPath(target)
        role=_world_role(cache,prim,target);role['ancestors']=[]
        if prim:
            parent=prim.GetParent()
            while parent and not parent.IsPseudoRoot():
                role['ancestors'].append(_world_role(cache,parent,str(parent.GetPath())))
                parent=parent.GetParent()
        anchors[target]=role
    return anchors


def observe(stage, path, ctx, stopped):
    from pxr import Gf,Usd,UsdGeom,UsdPhysics,PhysxSchema
    from validate import tf,quat,mv,add,tr,sub
    packet=reference(ctx,'extract.py').observe_stage(stage,path,{'run_id':ctx.job['run_id'],'pid':os.getpid(),'job_sha256':ctx.job_hash},stopped)
    cache=UsdGeom.XformCache(Usd.TimeCode.Default());prims=list(stage.Traverse());bodies={str(p.GetPath()):p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)}
    for row in packet['joints']:
        prim=stage.GetPrimAtPath(row['path'])
        row['enabled']=UsdPhysics.Joint(prim).GetJointEnabledAttr().Get()
        if prim.IsA(UsdPhysics.PrismaticJoint):
            j=UsdPhysics.PrismaticJoint(prim);row.update(type='prismatic',axis=str(j.GetAxisAttr().Get()),lower_limit=float(j.GetLowerLimitAttr().Get()),upper_limit=float(j.GetUpperLimitAttr().Get()))
    packet['world_anchors']=_world_anchors(stage,cache,bodies,packet['joints'])
    packet['colliders']=[]
    for prim in prims:
        if not prim.HasAPI(UsdPhysics.CollisionAPI):continue
        cursor=prim;owner=None
        while cursor and not cursor.IsPseudoRoot():
            if str(cursor.GetPath()) in bodies:owner=cursor;break
            cursor=cursor.GetParent()
        if prim.IsA(UsdGeom.Cube):
            size=float(UsdGeom.Cube(prim).GetSizeAttr().Get());points=[Gf.Vec3d(x*size/2,y*size/2,z*size/2) for x in (-1,1) for y in (-1,1) for z in (-1,1)]
        else:
            need(prim.IsA(UsdGeom.Mesh),'supported actual collision shape');points=list(UsdGeom.Mesh(prim).GetPointsAttr().Get())
        T=cache.GetLocalToWorldTransform(prim);world=[]
        for point in points:
            p=[float(x) for x in T.Transform(Gf.Vec3d(*[float(x) for x in point]))]
            if not any(max(abs(a-b) for a,b in zip(p,q))<1e-9 for q in world):world.append(p)
        local=[]
        if owner is not None:
            inverse=cache.GetLocalToWorldTransform(owner).GetInverse();local=[[float(x) for x in inverse.Transform(Gf.Vec3d(*p))] for p in world]
        packet['colliders'].append({'path':str(prim.GetPath()),'owner':owner.GetName() if owner is not None else '__floor__','shape':prim.GetTypeName(),'enabled':bool(UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()),'corners_link':local,'corners_world':world,'static':owner is None,'filtered_pairs':[str(p) for p in UsdPhysics.FilteredPairsAPI(prim).GetFilteredPairsRel().GetTargets()] if prim.HasAPI(UsdPhysics.FilteredPairsAPI) else []})
    roots=[p for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    need(len(roots)==1,'one actual articulation root');packet['articulation_path']=str(roots[0].GetPath());packet['self_collision']=bool(PhysxSchema.PhysxArticulationAPI(roots[0]).GetEnabledSelfCollisionsAttr().Get())
    tool=[p for p in prims if p.GetName()=='tool0'];need(len(tool)==1,'one tool0 transform');p,R=_pose(cache,tool[0]);packet['tool0']={'path':str(tool[0].GetPath()),'parent_name':tool[0].GetParent().GetName(),'position':p,'rotation':R,'rigid_body':tool[0].HasAPI(UsdPhysics.RigidBodyAPI),'mass_api':tool[0].HasAPI(UsdPhysics.MassAPI)}
    return packet


def normalize_tool(stage, model):
    from pxr import UsdGeom,UsdPhysics,PhysxSchema,Gf
    from validate import near
    source=model['links']['tool0'];need(source['mass'] is None and source['visual'] is None and source['collision'] is None,'only canonical empty frame normalization')
    tool=[p for p in stage.Traverse() if p.GetName()=='tool0'];need(len(tool)==1,'exact tool0');tool=tool[0];need(tool.GetParent().GetName()=='KG1','canonical frame parent before normalization')
    targets=[]
    for p in stage.Traverse():
        if p.IsA(UsdPhysics.Joint) and str(tool.GetPath()) in [str(x) for x in UsdPhysics.Joint(p).GetBody1Rel().GetTargets()]:targets.append(p)
    auto=tool.HasAPI(UsdPhysics.RigidBodyAPI) or bool(targets)
    result={'canonical_empty':True,'automatic_physical':auto,'removed_joint':None,'removed_apis':[]}
    if auto:
        need(len(targets)==1 and targets[0].GetName()=='tool0_mount' and targets[0].IsA(UsdPhysics.FixedJoint),'sole frame-only generated constraint')
        result['removed_joint']=str(targets[0].GetPath());stage.RemovePrim(targets[0].GetPath())
        for cls in (UsdPhysics.RigidBodyAPI,UsdPhysics.MassAPI,PhysxSchema.PhysxRigidBodyAPI):
            if tool.HasAPI(cls):result['removed_apis'].append(cls.__name__);need(tool.RemoveAPI(cls),'remove frame-only automatic physical API')
        p,R=model['joints']['tool0_mount']['origin'];matrix=Gf.Matrix4d(1)
        for i in range(3):
            for j in range(3):matrix[i][j]=R[j][i]
        matrix.SetTranslateOnly(Gf.Vec3d(*p));x=UsdGeom.Xformable(tool);x.ClearXformOpOrder();x.AddTransformOp().Set(matrix)
    need(not tool.HasAPI(UsdPhysics.RigidBodyAPI) and not tool.HasAPI(UsdPhysics.MassAPI),'tool0 now nonphysical')
    return result


def import_model(ctx, app):
    import omni.usd
    import omni.timeline
    from pxr import UsdGeom,UsdPhysics
    from validate import pmodel,verify_import,near
    out=ctx.run/'output';model=pmodel(ctx.run/'input/model/robot_arm.urdf')
    for ext in ('omni.scene.optimizer.core','isaacsim.robot.schema','isaacsim.asset.importer.urdf'):enable(ext)
    timeline=omni.timeline.get_timeline_interface();need(timeline.is_stopped(),'import while stopped')
    from isaacsim.asset.importer.urdf import URDFImporter,URDFImporterConfig
    settings={'urdf_path':str(ctx.run/'input/model/robot_arm.urdf'),'usd_path':str(out/'imported'),'merge_mesh':False,'merge_fixed_joints':False,'collision_from_visuals':False,'allow_self_collision':False,'fix_base':True,'link_density':None,'joint_drive_type':None,'joint_target_type':None,'override_joint_stiffness':None,'override_joint_damping':None,'run_asset_transformer':False,'run_multi_physics_conversion':False}
    write(out/'import-settings.json',settings);asset=Path(URDFImporter(URDFImporterConfig(**settings)).import_urdf()).resolve();need(asset.is_file() and asset.is_relative_to((out/'imported').resolve()),'actual owned saved importer result')
    context=omni.usd.get_context();context.open_stage(str(asset))
    for _ in range(3):app.update();need(timeline.is_stopped(),'no import physics playback')
    stage=context.get_stage();need(Path(stage.GetRootLayer().realPath).resolve()==asset,'active saved USD')
    raw_path=out/'raw-import.usda';stage.Flatten().Export(str(raw_path));raw=observe(stage,raw_path,ctx,True);write(out/'raw-static.json',raw)
    correction=normalize_tool(stage,model);path=out/'model.usda';stage.Flatten().Export(str(path));packet=observe(stage,path,ctx,True)
    # Independently expose exactly which physical objects changed during representation normalization.
    retained=[x for x in raw['bodies'] if x['name']!='tool0'];near(packet['bodies'],retained,0.)
    retained_joints=[x for x in raw['joints'] if x['name']!='tool0_mount'];near(packet['joints'],retained_joints,0.)
    packet['normalization']=correction;write(out/'static.json',packet)
    metrics=verify_import(ctx.run/'input/model/robot_arm.urdf',packet,ctx.cfg)
    write(out/'report.json',{'schema_version':1,'status':'IMPORT_COLLECTED','run_id':ctx.job['run_id'],'job_sha256':ctx.job_hash,'pid':os.getpid(),'metrics':metrics,'model_sha256':sha(ctx.run/'input/model/robot_arm.urdf'),'normalization':correction,'mimic_schemas':{j['name']:j['applied_schemas'] for j in packet['joints']}})


def run_import(ctx):
    return lifecycle(ctx,import_model)


def bind(ctx, sim, prims):
    ref=reference(ctx,'physics_reference.py');sources=ref.source_hashes();manager=sim.physics_manager
    need(manager.__module__+'.'+manager.__name__=='isaaclab_physx.physics.physx_manager.PhysxManager' and str(sim.device)=='cpu','actual CPU Lab PhysxManager')
    view=manager.get_physics_sim_view();need(view is not None and bool(view.is_valid),'actual Lab view')
    owners={name:importlib.import_module(name).SimulationManager for name in ref.REFERENCES};rows=[]
    for sdk in dict.fromkeys(owners.values()):
        old=getattr(sdk,'_physics_sim_view__warp',None);callbacks=dict(sdk.get_default_callback_status());need(old is None or old is view,'reject foreign view');need(set(callbacks)==ref.CALLBACKS and all(type(v) is bool and not v for v in callbacks.values()),'SDK default callbacks inactive');need(str(sdk.get_physics_sim_device())=='cpu' and str(sdk.get_active_physics_engine())=='physx','same real backend');rows.append({'module':sdk.__module__,'id':id(sdk),'before_view_id':None if old is None else id(old),'callbacks':callbacks,'device':str(sdk.get_physics_sim_device()),'engine':str(sdk.get_active_physics_engine()),'after_view_id':id(view)});sdk._physics_sim_view__warp=view
    consumers=[]
    for prim in prims:
        prim._on_physics_ready(None);need(bool(prim.is_physics_tensor_entity_valid()),'actual tensor prim ready');owner=importlib.import_module(type(prim).__module__).SimulationManager;need(owner._physics_sim_view__warp is view,'consumer bound to owned view');consumers.append({'module':type(prim).__module__,'type':type(prim).__name__,'paths':list(prim.paths),'manager_id':id(owner),'view_id':id(view),'valid':True})
    need(len(consumers)==12 and sum(x['type']=='Articulation' for x in consumers)==1 and sum(x['type']=='RigidPrim' for x in consumers)==11,'canonical eleven body consumers plus articulation')
    value={'run_id':ctx.job['run_id'],'job_sha256':ctx.job_hash,'pid':os.getpid(),'sources':sources,'device':str(sim.device),'lab_manager':manager.__module__+'.'+manager.__name__,'lab_view_id':id(view),'owners':rows,'references':{n:id(v) for n,v in owners.items()},'consumers':consumers};write(ctx.run/'output/physics-binding.json',value);return value


def runtime_inertias(ctx, links):
    import isaacsim.core.experimental.utils.backend as backend
    rows=[]
    with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
        for name,prim in links:
            com,axes=prim.get_coms();raw=prim.get_inertias().numpy().copy();mass=prim.get_masses().numpy().copy();need(raw.size==9,'full actual link inertia tensor')
            rows.append({'name':name,'mass':float(mass[0,0]),'mass_shape':list(mass.shape),'com_shape':list(com.shape),'principal_axes_shape':list(axes.shape),'inertia_shape':list(raw.shape),'raw_inertia':raw.reshape(-1).tolist(),'order':'F','com':com.numpy().copy()[0].tolist(),'principal_axes_wxyz':axes.numpy().copy()[0].tolist(),'inertia_link_about_com':raw[0].reshape((3,3),order='F').tolist()})
    return rows
