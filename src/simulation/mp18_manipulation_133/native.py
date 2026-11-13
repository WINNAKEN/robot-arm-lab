"""133 actual physical object task, retaining checked130 native lifecycle and guards."""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path

_here = Path(__file__).resolve().parent
_raw = (_here/'base_native.py').read_bytes()
if hashlib.sha256(_raw).hexdigest() != 'e78af630c5dfda106dca14d3059065c0e060c63671e2ba8b3d0756cd86b1dcd8':
    raise ValueError('Original130 native bytes before derivation')
_text = _raw.decode('utf-8')


def _replace_once(old,new):
    global _text
    if _text.count(old) != 1: raise ValueError('Exact133 derivation anchor:'+old[:100])
    _text = _text.replace(old,new,1)


_replace_once("    support, workspace = C.parse(ctx.data['ref/support.json']), C.parse(ctx.data['ref/workspace.json'])",
"    _scene133(ctx,stage,paths,robot,names,backend,report,sim)\n    support, workspace = C.parse(ctx.data['ref/support.json']), C.parse(ctx.data['ref/workspace.json'])\n    workspace = ctx.cfg['manipulation_workspace']")
_replace_once("_contact_setup(ctx,stage,list(paths.values()),PhysxSchema,interface,stage_id,velocity_clock,",
"_contact_setup(ctx,stage,list(paths.values())+ctx.task_scene_paths,PhysxSchema,interface,stage_id,velocity_clock,")
_replace_once("        robot.set_dof_gains([[64.]*9], [[16.]*9])", "        robot.set_dof_gains([[_gain133(n,True) for n in names]], [[_gain133(n,False) for n in names]])")
_replace_once("need(all(v == 64. for v in C.named_columns(names, model['movable'], array(kp)[0]).values()) and\n             all(v == 16. for v in C.named_columns(names, model['movable'], array(kd)[0]).values()), 'Actual unchanged 64/16 gains')",
"need(all(v == _gain133(n,True) for n,v in C.named_columns(names, model['movable'], array(kp)[0]).items()) and\n             all(v == _gain133(n,False) for n,v in C.named_columns(names, model['movable'], array(kd)[0]).items()), 'Actual ARM64/16 and forcejaw1000/20 gains')\n    _binding133(ctx,stage,robot,names,backend,report)")
_replace_once("        journal.write(json.dumps(initial, allow_nan=False)+'\\n'); journal.flush()",
"        _task133(ctx,initial,clock,backend,report,initial=True)\n        journal.write(json.dumps(initial, allow_nan=False)+'\\n'); journal.flush()")
_replace_once("                journal.write(json.dumps(row, allow_nan=False, separators=(',', ':'))+'\\n'); journal.flush()",
"                _task133(ctx,row,clock,backend,report)\n                journal.write(json.dumps(row, allow_nan=False, separators=(',', ':'))+'\\n'); journal.flush()")
_replace_once("checkpoint = local_step == round(duration*120) or stage_name == 'large' and local_step == round(program['settling']['large_check_s']*120)",
"checkpoint = local_step == round(duration*120)")
_replace_once("    report['render'] = camera.finish(len(report['frames']), purpose='motion')",
"    report['manipulation'] = ctx.task133.finish()\n    ctx.write(out/'manipulation.json',report['manipulation'])\n    report['render'] = camera.finish(len(report['frames']), purpose='motion')")
_replace_once("return {'clock': after, 'clock_before': before, 'clock_after': after, 'q': q, 'qd': qd, 'body_poses': poses}",
"return _state133(ctx,{'clock': after, 'clock_before': before, 'clock_after': after, 'q': q, 'qd': qd, 'body_poses': poses},clock,backend)")
_replace_once("'clock': observed['clock'], 'actual_tcp': tcp(observed), 'ff': proof, 'effort_remaining': remaining}",
"'clock': observed['clock'], 'render_object_state':observed.get('object'), 'actual_tcp': tcp(observed), 'ff': proof, 'effort_remaining': remaining}")
exec(compile(_text,str(_here/'base_native.py')+'#derived133','exec'),globals())


def _enter133(self,phase):
    need(phase in PHASES,'Closed133 native phase')
    with self.lock:
        self.check(); at = self.now()
        need(at < self.end-self.cfg['cleanup_s'],'Native global headroom')
        self.phase,self.entered = phase,at
        self.phase_end = min(at+self.cfg[phase+'_s'],self.end-self.cfg['cleanup_s'])
        if self.armed: self._send({'op':'phase','deadline':self.phase_end,'phase':phase})


Budget.enter = _enter133

_original_budget_init133=Budget.__init__
def _budget_init133(self,ctx,now=time.monotonic):
    _original_budget_init133(self,ctx,now=now);self.owner_context133=ctx
Budget.__init__=_budget_init133


def watchdog_code133(original):
    """Add bounded asynchronous intent logging; termination never waits for file I/O."""
    logger=r'''
identity=json.loads(sys.argv[4]);logpath=sys.argv[5];phase=identity['phase'];control_reason=None
logqueue=queue.Queue(maxsize=16);logdone=threading.Event()
def logworker():
    while True:
        record=logqueue.get()
        try:
            with open(logpath,'a',encoding='utf-8') as stream:stream.write(json.dumps(record,separators=(',',':'))+'\n');stream.flush()
        except BaseException:
            pass_marker='LOG_WRITE_UNKNOWN_ERROR'
        finally:logqueue.task_done();logdone.set()
threading.Thread(target=logworker,daemon=True).start()
def note(reason,intent):
    record={'run_id':identity['run_id'],'job_sha256':identity['job_sha256'],'parent_pid':pid,
        'parent_birth':birth,'watchdog_pid':os.getpid(),'phase':phase,'chosen_deadline_monotonic':min(deadline,native_end),
        'phase_deadline_monotonic':deadline,'native_end_monotonic':native_end,'observed_monotonic':time.monotonic(),
        'reason':reason,'kill_intent':intent,'OS_exit_causality':'NOT_INFERRED_FROM_LOG','write_policy':'ASYNC_BEST_EFFORT_NO_KILL_WAIT'}
    try:logqueue.put_nowait(record)
    except queue.Full:queue_full_status='LOG_INCOMPLETE_UNKNOWN'
'''
    need(original.count('messages=queue.Queue()')==1,'Exact original watchdog reader setup')
    code=original.replace('messages=queue.Queue()',logger+'\nmessages=queue.Queue()',1)
    code=code.replace('try:\n    while True:',"note('ARMED',False)\ntry:\n    while True:",1)
    code=code.replace('if k.WaitForSingleObject(handle,0)==0:break',"if k.WaitForSingleObject(handle,0)==0:\n            note('PARENT_EXITED',False);break",1)
    code=code.replace('if remaining<=0:\n            if not k.TerminateProcess',"if remaining<=0:\n            note(control_reason or ('GLOBAL_DEADLINE' if native_end<=deadline else 'PHASE_DEADLINE'),True)\n            if not k.TerminateProcess",1)
    code=code.replace("if row=={'op':'disarm'}:break","if row=={'op':'disarm'}:\n            note('NORMAL_DISARM',False);break",1)
    old="if set(row)=={'op','deadline'} and row['op']=='phase' and type(row['deadline']) in (float,int) and math.isfinite(row['deadline']) and row['deadline']<=native_end:\n            deadline=row['deadline']\n        else:deadline=0.0"
    new="if isinstance(row,dict) and set(row)=={'op','deadline','phase'} and row['op']=='phase' and row['phase'] in ('import','hold','small','large') and type(row['deadline']) in (float,int) and math.isfinite(row['deadline']) and row['deadline']<=native_end:\n            deadline=row['deadline'];phase=row['phase'];note('PHASE_ARMED',False)\n        else:\n            control_reason='CONTROL_PIPE_EOF' if isinstance(row,dict) and row.get('op')=='eof' else 'CONTROL_PIPE_INVALID';deadline=0.0"
    need(code.count(old)==1,'Exact original watchdog phase protocol');code=code.replace(old,new,1)
    code=code.replace('finally:k.CloseHandle(handle)','finally:\n    drain_end=time.monotonic()+.05\n    while logqueue.unfinished_tasks and time.monotonic()<drain_end:time.sleep(.001)\n    k.CloseHandle(handle)',1)
    return code


WATCHDOG_CODE=watchdog_code133(WATCHDOG_CODE)
_budget_tree133=ast.parse(_raw.decode('utf-8'))
_budget_class133=next(n for n in _budget_tree133.body if isinstance(n,ast.ClassDef) and n.name=='Budget')
_arm_node133=next(n for n in _budget_class133.body if isinstance(n,ast.FunctionDef) and n.name=='arm')
_arm_source133=ast.get_source_segment(_raw.decode('utf-8'),_arm_node133)
_arm_anchor133='str(os.getpid()), repr(min(self.phase_end, end)), repr(end)]'
need(_arm_source133.count(_arm_anchor133)==1,'Exact original watchdog argv owner boundary')
_arm_source133=_arm_source133.replace(_arm_anchor133,"str(os.getpid()), repr(min(self.phase_end, end)), repr(end), json.dumps({'run_id':self.owner_context133.job['run_id'],'job_sha256':self.owner_context133.job_hash,'phase':self.phase}),str(self.owner_context133.run/'watchdog-reason.ndjson')]",1)
exec(compile(_arm_source133,'<133-owned-watchdog-arm>','exec'),globals())
Budget.arm=arm


def _gain133(name,stiffness):
    return (1000. if stiffness else 20.) if name in ('KG1_slide_A','KG1_slide_B') else (64. if stiffness else 16.)


def _offset133(prim):
    from pxr import PhysxSchema
    api = PhysxSchema.PhysxCollisionAPI.Apply(prim)
    need(api.CreateContactOffsetAttr().Set(.0005) and api.CreateRestOffsetAttr().Set(0.),'Authored133 collision offsets')
    need(abs(api.GetContactOffsetAttr().Get()-.0005)<1e-9 and api.GetRestOffsetAttr().Get()==0.,'Actual133 collision offsets')
    return {'path':str(prim.GetPath()),'contact_offset_m':float(api.GetContactOffsetAttr().Get()),'rest_offset_m':float(api.GetRestOffsetAttr().Get())}


def _scene133(ctx,stage,paths,robot,names,backend,report,sim):
    from pxr import Gf,UsdGeom,UsdPhysics,UsdShade,PhysxSchema
    from isaacsim.core.experimental.prims import RigidPrim
    C = ctx.contract; s = ctx.scenario
    pinion=stage.GetPrimAtPath('/World/Robot/Physics/KG1_pinion')
    attr=pinion.GetAttribute('newton:mimicEnabled')
    need(bool(pinion) and bool(attr) and str(attr.GetTypeName())=='bool' and attr.Get() is True,'Actual typed imported pinion Newton mimic enabled')
    need(attr.Set(False) is True and attr.Get() is False,'Disable only imported pinion Newton mimic before reset')
    report['pinion_mimic_policy']={'path':str(attr.GetPath()),'before':True,'after':False,'software_SI_ratio':-74.07407407407408,'root_cause':'UNIT_COUPLING_HYPOTHESIS_REQUIRES_ACTUAL_SI_TRACKING','URDF_changed':False}
    offsets=[]; approximations=[]
    for name in ('KG1',):
        descendants=[]
        for p in stage.Traverse():
            path=str(p.GetPath())
            if not p.HasAPI(UsdPhysics.CollisionAPI):continue
            owners=[n for n,body_path in paths.items() if path.startswith(body_path+'/')]
            if not owners:continue
            owner=max(owners,key=lambda n:len(paths[n]))
            if owner==name:descendants.append(p)
        need(len(descendants)>0,'Actual gripper colliders:'+name)
        for prim in descendants:
            need(prim.IsA(UsdGeom.Mesh),'Existing gripper collision mesh')
            api=UsdPhysics.MeshCollisionAPI.Apply(prim)
            before=api.GetApproximationAttr().Get()
            need(str(before)=='convexHull','Original measured wholelink hull')
            need(api.CreateApproximationAttr().Set('convexDecomposition'),'Authored cavity-preserving cooking policy')
            need(str(api.GetApproximationAttr().Get())=='convexDecomposition','Actual collision approximation token')
            approximations.append({'path':str(prim.GetPath()),'before':str(before),'after':str(api.GetApproximationAttr().Get()),'cooked_shape_validated':False})
            offsets.append(_offset133(prim))
    mat=UsdShade.Material.Define(stage,'/World/TaskMaterial133')
    physicsmat=UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    physicsmat.CreateStaticFrictionAttr().Set(s['object']['static_friction'])
    physicsmat.CreateDynamicFrictionAttr().Set(s['object']['dynamic_friction'])
    physicsmat.CreateRestitutionAttr().Set(0.)
    report['jaw_component_overlay']=_component_colliders133(ctx,stage,paths,mat)
    def cube(path,dim,pos,yaw,color):
        geom=UsdGeom.Cube.Define(stage,path);geom.CreateSizeAttr(1.)
        geom.AddTranslateOp().Set(Gf.Vec3d(*pos));geom.AddRotateZOp().Set(math.degrees(yaw));geom.AddScaleOp().Set(Gf.Vec3f(*dim))
        geom.CreateDisplayColorAttr().Set([Gf.Vec3f(*color)])
        UsdPhysics.CollisionAPI.Apply(geom.GetPrim()).CreateCollisionEnabledAttr(True)
        UsdShade.MaterialBindingAPI.Apply(geom.GetPrim()).Bind(mat,UsdShade.Tokens.weakerThanDescendants,'physics')
        offsets.append(_offset133(geom.GetPrim()));return geom
    pedestal_paths=[]
    for p in s['pedestals']:
        path='/World/Task133/Pedestal_'+p['name'];cube(path,p['dimensions_m'],p['center_m'],p['yaw_rad'],(.1,.35,.8));pedestal_paths.append(path)
    obj=s['object'];T=obj['source_T_world'];objpath='/World/Task133/Object'
    objroot=UsdGeom.Xform.Define(stage,objpath)
    objroot.AddTranslateOp().Set(Gf.Vec3d(*[r[3] for r in T[:3]]))
    objroot.AddRotateZOp().Set(math.degrees(math.atan2(T[1][0],T[0][0])))
    cube(objpath+'/Collision',obj['dimensions_m'],[0,0,0],0.,(.95,.18,.04))
    prim=objroot.GetPrim();body=UsdPhysics.RigidBodyAPI.Apply(prim)
    body.CreateRigidBodyEnabledAttr(True);body.CreateKinematicEnabledAttr(False)
    mass=UsdPhysics.MassAPI.Apply(prim);mass.CreateMassAttr(obj['mass_kg']);mass.CreateCenterOfMassAttr(Gf.Vec3f(0,0,0))
    # Scale is authored on the shape; explicit SI inertia about the actual box center.
    dim=obj['dimensions_m'];I=[obj['mass_kg']*(dim[(i+1)%3]**2+dim[(i+2)%3]**2)/12 for i in range(3)]
    mass.CreateDiagonalInertiaAttr(Gf.Vec3f(*I));mass.CreatePrincipalAxesAttr(Gf.Quatf(1,Gf.Vec3f(0,0,0)))
    physbody=PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
    physbody.CreateDisableGravityAttr(False);physbody.CreateSleepThresholdAttr(0.)
    need(body.GetKinematicEnabledAttr().Get() is False and body.GetRigidBodyEnabledAttr().Get() is True,'Actual free dynamic box')
    need(abs(mass.GetMassAttr().Get()-obj['mass_kg'])<1e-9 and physbody.GetDisableGravityAttr().Get() is False,'Actual box mass/gravity')
    need(abs(physicsmat.GetStaticFrictionAttr().Get()-.8)<1e-6 and abs(physicsmat.GetDynamicFrictionAttr().Get()-.6)<1e-6,'Actual132 material assumption')
    jawindices=[names.index(n) for n in ('KG1_slide_A','KG1_slide_B')]
    with backend.use_backend('usd',raise_on_unsupported=True,raise_on_fallback=True):
        robot.set_dof_drive_types('force',dof_indices=jawindices)
        robot.set_dof_gains([[_gain133(n,True) for n in names]],[[_gain133(n,False) for n in names]])
        drive=robot.get_dof_drive_types()
    # get_dof_drive_types uses nested strings, not numeric arrays.
    flat=list(drive[0]) if len(drive)==1 and not isinstance(drive[0],str) else list(drive)
    need(len(flat)==len(names) and all(str(flat[i])==('force' if i in jawindices else 'acceleration') for i in range(len(names))),'Actual named USD drive types')
    ctx.task_scene_paths=[objpath]+pedestal_paths+['/World/Floor']
    ctx.task_object=RigidPrim(objpath);ctx.task_sim=sim
    ctx.task_object_path=objpath;ctx.task_jaw_paths={n:paths[n] for n in ('KG1_A','KG1_B')}
    ctx.task_object_usd={'path':objpath,'valid':True,'kinematic':False,'gravity_enabled':True,'mass_kg':float(mass.GetMassAttr().Get()),
        'diagonal_inertia_kg_m2':[float(v) for v in mass.GetDiagonalInertiaAttr().Get()],
        'dimensions_m':list(dim),'sleep_threshold':float(physbody.GetSleepThresholdAttr().Get()),'pose_initializations_before_reset':1,'runtime_pose_setters':0}
    ctx.task133=C.Task(s,objpath,ctx.task_jaw_paths,{r['owner_name']:{p['path'] for p in r['new']} for r in ctx.task_jaw_overlay})
    report['manipulation_scene']={'object':ctx.task_object_usd,'jaw_paths':dict(ctx.task_jaw_paths),'offsets':offsets,'collision_approximation':approximations,
        'jaw_component_overlay':report['jaw_component_overlay'],'prior_effective_jaw_friction':'UNKNOWN_NOT_CLAIMED_EQUAL',
        'material':{'static_friction':float(physicsmat.GetStaticFrictionAttr().Get()),'dynamic_friction':float(physicsmat.GetDynamicFrictionAttr().Get())},
        'gripper_drive_types':dict(zip(names,map(str,flat))),'physical_gear_contact':'NOT_VERIFIED','cooked_cavity_success':'NOT_YET_TESTED'}
    ctx.write(ctx.run/'output/manipulation-scene.json',report['manipulation_scene'])


def _binding133(ctx,stage,robot,names,backend,report):
    need(stage.GetPrimAtPath('/World/Robot/Physics/KG1_pinion').GetAttribute('newton:mimicEnabled').Get() is False,'Pinion Newton mimic remains disabled after reset')
    import importlib
    from pxr import UsdPhysics,PhysxSchema
    report['jaw_component_overlay']['after_reset']=_audit_components133(ctx,stage,ctx.task_jaw_overlay)
    with backend.use_backend('usd',raise_on_unsupported=True,raise_on_fallback=True):
        drive=robot.get_dof_drive_types()
    flat=list(drive[0]) if len(drive)==1 and not isinstance(drive[0],str) else list(drive)
    need(all(str(flat[i])==('force' if names[i].startswith('KG1_slide_') else 'acceleration') for i in range(len(names))),'Drive types survive reset')
    obj=ctx.task_object;obj._on_physics_ready(None)
    manager=importlib.import_module(type(obj).__module__).SimulationManager
    view=ctx.task_sim.physics_manager.get_physics_sim_view()
    need(manager._physics_sim_view__warp is view and bool(view.is_valid) and obj.is_physics_tensor_entity_valid(),'Actual object binds same owned Lab physics view')
    need(obj._physics_rigid_body_view.count==1 and list(obj._physics_rigid_body_view.prim_paths)==[ctx.task_object_path],'Exact actual object tensor paths')
    with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
        masses=obj.get_masses().numpy().copy().reshape(-1).tolist()
        inertia=obj.get_inertias().numpy().copy().reshape(-1).tolist()
        gravity=obj.get_enabled_gravities().numpy().copy().reshape(-1).tolist()
        dynamic=obj.get_enabled_rigid_bodies().numpy().copy().reshape(-1).tolist()
    need(len(masses)==1 and abs(masses[0]-.002)<1e-8,'Actual tensor free-object mass')
    need(gravity==[True] and dynamic==[True] and len(inertia)==9,'Actual tensor enabled gravity/dynamic and inertia')
    expected=ctx.task_object_usd['diagonal_inertia_kg_m2']
    need(all(abs(inertia[3*i+j]-(expected[i] if i==j else 0.))<1e-11 for i in range(3) for j in range(3)),'Actual tensor SI box inertia')
    prim=stage.GetPrimAtPath(ctx.task_object_path)
    need(UsdPhysics.RigidBodyAPI(prim).GetKinematicEnabledAttr().Get() is False and PhysxSchema.PhysxRigidBodyAPI(prim).GetDisableGravityAttr().Get() is False,'Reset dynamic/gravity unchanged')
    report['manipulation_scene']['object_tensor_mass_kg']=masses[0]
    report['manipulation_scene']['object_tensor_inertia']=inertia
    ctx.task_object_usd['current_view_id']=id(view)
    report['manipulation_scene']['object_binding']={'path':ctx.task_object_path,'view_id':id(view),'manager_view_identical':True,'is_valid':True,'gravity_enabled':gravity,'body_enabled':dynamic}
    report['manipulation_scene']['reset_drive_types']=dict(zip(names,map(str,flat)))
    ctx.write(ctx.run/'output/manipulation-scene.json',report['manipulation_scene'])
    ctx.task_object_bound=True


def _component_colliders133(ctx,stage,paths,material):
    """Original SI components, distinct collision shapes under the unchanged jaw rigid bodies."""
    from pxr import Gf,UsdGeom,UsdPhysics,UsdShade
    data=ctx.jaw_components
    need(data['unit']==133 and data['frame']=='OWNING_JAW_LINK_FRAME' and set(data['jaws'])=={'KG1_A','KG1_B'},'Exact original jaw component data')
    records=[]
    for name,d in data['jaws'].items():
        need(d['scale']==[1,1,1] and d['component_count']==6 and len(d['components'])==6,'Original6 SI components')
        need(ctx.sha(ctx.run/'input/model/meshes/collision'/(name+'.stl'))==d['source_sha256'],'Component original model source pin')
        original=[]
        for p in stage.Traverse():
            if not p.HasAPI(UsdPhysics.CollisionAPI):continue
            path=str(p.GetPath());owners=[n for n,b in paths.items() if path.startswith(b+'/')]
            if owners and max(owners,key=lambda n:len(paths[n]))==name:original.append(p)
        need(len(original)==1,'Exactly one original whole-jaw collision')
        old=original[0];api=UsdPhysics.CollisionAPI(old)
        need(api.GetCollisionEnabledAttr().Get() is True,'Original whole-jaw enabled before overlay')
        need(api.GetCollisionEnabledAttr().Set(False) is True,'Disable original whole-jaw collision only')
        new=[]
        for part in d['components']:
            path=paths[name]+'/ExplicitJawColliders133/component_%02d'%part['index']
            need(not stage.GetPrimAtPath(path),'Fresh component collision prim')
            mesh=UsdGeom.Mesh.Define(stage,path)
            mesh.CreatePointsAttr().Set([Gf.Vec3f(*point) for point in part['vertices_m']])
            mesh.CreateFaceVertexCountsAttr().Set([3]*len(part['triangle_indices']))
            mesh.CreateFaceVertexIndicesAttr().Set([i for face in part['triangle_indices'] for i in face])
            mesh.CreateSubdivisionSchemeAttr().Set('none');mesh.CreateVisibilityAttr().Set('invisible')
            prim=mesh.GetPrim();UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
            UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr().Set('convexHull')
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,UsdShade.Tokens.weakerThanDescendants,'physics')
            _offset133(prim)
            need(not prim.HasAPI(UsdPhysics.RigidBodyAPI) and not prim.HasAPI(UsdPhysics.MassAPI),'Child collision adds no rigid body/mass/inertia')
            new.append({'path':path,'component':part})
        records.append({'owner_name':name,'owner_path':paths[name],'old_path':str(old.GetPath()),'new':new,'material_path':str(material.GetPath())})
    ctx.task_jaw_overlay=records
    audit=_audit_components133(ctx,stage,records)
    return {'before_reset':audit,'policy':'12_ORIGINAL_SI_COMPONENT_CONVEX_SHAPES_SAME_RIGID_MASS_INERTIA',
            'source_geometry_static_pad_match':'PASS','cooked_vertices':'NOT_OBSERVED_ACTUAL_GRASP_STILL_REQUIRED'}


def _audit_components133(ctx,stage,records):
    from pxr import UsdGeom,UsdPhysics,PhysxSchema
    rows=[]
    for row in records:
        need(UsdPhysics.CollisionAPI(stage.GetPrimAtPath(row['old_path'])).GetCollisionEnabledAttr().Get() is False,'Old whole-jaw collider remains disabled')
        active=[]
        for p in stage.Traverse():
            if str(p.GetPath()).startswith(row['owner_path']+'/') and p.HasAPI(UsdPhysics.CollisionAPI) and UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get():active.append(str(p.GetPath()))
        need(set(active)=={p['path'] for p in row['new']} and len(active)==6,'Exactly six active component collision prims under original jaw')
        for item in row['new']:
            p=stage.GetPrimAtPath(item['path']);mesh=UsdGeom.Mesh(p);part=item['component']
            points=[[float(v) for v in x] for x in mesh.GetPointsAttr().Get()]
            ctx.contract.near(points,part['vertices_m'],2e-8)
            need(list(mesh.GetFaceVertexCountsAttr().Get())==[3]*len(part['triangle_indices']) and list(mesh.GetFaceVertexIndicesAttr().Get())==[i for face in part['triangle_indices'] for i in face],'Actual component triangle topology')
            need(str(UsdPhysics.MeshCollisionAPI(p).GetApproximationAttr().Get())=='convexHull','Actual component convexHull shape policy')
            need(not p.HasAPI(UsdPhysics.RigidBodyAPI) and not p.HasAPI(UsdPhysics.MassAPI),'Unchanged owning rigid mass/inertia')
            need([str(t) for t in p.GetRelationship('material:binding:physics').GetTargets()]==[row['material_path']],'Same actual physics material binding')
            collision=PhysxSchema.PhysxCollisionAPI(p)
            offsets={'contact_offset_m':float(collision.GetContactOffsetAttr().Get()),'rest_offset_m':float(collision.GetRestOffsetAttr().Get())}
            need(abs(offsets['contact_offset_m']-.0005)<1e-9 and offsets['rest_offset_m']==0.,'Actual unchanged component contact/rest offsets')
            rows.append({'path':item['path'],'owner_path':row['owner_path'],'vertices':len(points),'faces':len(part['triangle_indices']),'offsets':offsets})
    need(len(rows)==12,'Twelve explicit active jaw collision components')
    return {'active_components':rows,'count':12,'old_whole_colliders_disabled':True,'same_rigid_body_mass_inertia':True}


def _object_state133(ctx,clock,backend):
    need(ctx.task_object.is_physics_tensor_entity_valid() and ctx.task_object._physics_rigid_body_view.count==1 and list(ctx.task_object._physics_rigid_body_view.prim_paths)==[ctx.task_object_path],'Current same owned object tensor entity')
    before=clock()
    with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
        pos,rot=ctx.task_object.get_world_poses();linear,angular=ctx.task_object.get_velocities()
        value={'pose':{'position':pos.numpy().copy()[0].tolist(),'orientation_wxyz':rot.numpy().copy()[0].tolist()},
            'linear_velocity':linear.numpy().copy()[0].tolist(),'angular_velocity':angular.numpy().copy()[0].tolist(),
            'clock':before,'binding':dict(ctx.task_object_usd)}
    need(before==clock(),'Object query leaves same physics clock')
    return value


def _state133(ctx,value,clock,backend):
    if getattr(ctx,'task_object_bound',False):
        value['object']=_object_state133(ctx,clock,backend)
        need(value['object']['clock']==value['clock'],'Render snapshot object/robot same clock')
    return value


def _task133(ctx,row,clock,backend,report,initial=False):
    value=row['render_object_state']
    need(value is not None and value['clock']==clock()==row['clock'],'Actual row/render object same native clock')
    contact={} if initial else ctx._contact_probe.last
    row['object']=value
    row['manipulation']=ctx.task133.observe(row,value,contact)
    if not initial: row['object_contacts']=contact
    if row['step']%120==0:ctx.write(ctx.run/'output/manipulation-progress.json',{'step':row['step'],'task':row['manipulation'],'object':value})
