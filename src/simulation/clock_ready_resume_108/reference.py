"""Unconnected inertial references. SDK imports occur only inside native creation."""
import math
import importlib

PHASES=('external_only','force_PD_only','combined_residual','acceleration_PD_only','free')
def robot_inventory(robot,backend,array):
    with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
        return {'friction':[array(x).tolist() for x in robot.get_dof_friction_properties()], 'armature':array(robot.get_dof_armatures()).tolist(),'drive_model':[array(x).tolist() for x in robot.get_dof_drive_model_properties()],'tensor_drive_types':array(robot._physics_articulation_view.get_drive_types()).tolist(),'interpretation':'MECHANISM_INVENTORY_NOT_PD_FORCE_SENSOR'}
def need(ok,why):
    if not ok:raise ValueError(why)
def phase(step):
    need(type(step) is int and 1<=step<=240,'Reference completed positive step1..240')
    return PHASES[(step-1)//48]
def command_for(step,mode):
    p=phase(step);active=(mode=='force' and p in PHASES[1:3]) or (mode=='acceleration' and p==PHASES[3])
    return {'phase':p,'kp':64. if active else 0.,'kd':16. if active else 0.,'target':.2,'external':.02 if p=='external_only' or (mode=='force' and p=='combined_residual') else 0.,'cap':.01}
def scalar(array,value):
    raw=array(value).reshape(-1).tolist();need(len(raw)==1 and math.isfinite(raw[0]),'Single finite reference DOF');return float(raw[0])

def create(stage):
    from pxr import UsdGeom,UsdPhysics,PhysxSchema,Gf
    from isaacsim.core.experimental.prims import Articulation
    result=[]
    for index,mode in enumerate(('force','acceleration')):
        offset=.4 if mode=='acceleration' else 0.;inertia=.05 if mode=='acceleration' else .2;axis='Y' if mode=='acceleration' else 'Z';angle=math.pi/4 if mode=='acceleration' else 0.;basis=[math.cos(angle/2),0.,0.,math.sin(angle/2)]
        path='/World/TorqueReference/'+mode;UsdGeom.Xform.Define(stage,path)
        for name in ('Base','Rotor'):
            body=UsdGeom.Xform.Define(stage,path+'/'+name);body.AddTranslateOp().Set(Gf.Vec3d(5.+index,0.,2.))
            body.AddOrientOp().Set(Gf.Quatf(basis[0],Gf.Vec3f(*basis[1:])))
            rb=UsdPhysics.RigidBodyAPI.Apply(body.GetPrim());rb.CreateRigidBodyEnabledAttr(True)
            mass=UsdPhysics.MassAPI.Apply(body.GetPrim());mass.CreateMassAttr(1.);mass.CreateCenterOfMassAttr(Gf.Vec3f(offset if name=='Rotor' else 0.,0.,0.));mass.CreateDiagonalInertiaAttr(Gf.Vec3f(inertia,inertia,inertia))
            phys=PhysxSchema.PhysxRigidBodyAPI.Apply(body.GetPrim());phys.CreateLinearDampingAttr(0.);phys.CreateAngularDampingAttr(0.)
        anchor=UsdPhysics.FixedJoint.Define(stage,path+'/Anchor');anchor.CreateBody1Rel().SetTargets([path+'/Base']);anchor.CreateLocalPos0Attr(Gf.Vec3f(5.+index,0.,2.));anchor.CreateLocalPos1Attr(Gf.Vec3f(0.))
        anchor.CreateLocalRot0Attr(Gf.Quatf(basis[0],Gf.Vec3f(*basis[1:])))
        UsdPhysics.ArticulationRootAPI.Apply(anchor.GetPrim())
        joint=UsdPhysics.RevoluteJoint.Define(stage,path+'/RefJoint');joint.CreateBody0Rel().SetTargets([path+'/Base']);joint.CreateBody1Rel().SetTargets([path+'/Rotor']);joint.CreateAxisAttr(axis);joint.CreateLowerLimitAttr(-10000.);joint.CreateUpperLimitAttr(10000.)
        drive=UsdPhysics.DriveAPI.Apply(joint.GetPrim(),'angular');drive.CreateTypeAttr(mode);drive.CreateStiffnessAttr(0.);drive.CreateDampingAttr(0.);drive.CreateMaxForceAttr(.01)
        articulation=Articulation(path+'/Anchor')
        result.append({'mode':mode,'path':path,'object':articulation,'joint':joint,'body_count':2,'collision_shapes':0,'basis_wxyz':basis,'axis':axis,'pivot':[5.+index,0.,2.]})
    return result

class RawReferences:
    def __init__(self,items,backend,array,clock,view,packet):
        self.items=items;self.backend=backend;self.array=array;self.clock=clock;self.packet=packet
        for item in items:
            robot=item['object'];robot._on_physics_ready(None)
            owner=importlib.import_module(type(robot).__module__).SimulationManager
            need(owner._physics_sim_view__warp is view,'Reference shares the actual owned Lab view')
            need(robot.is_physics_tensor_entity_valid() and len(robot.dof_names)==1,'Reference bound single DOF')
            need(robot._physics_articulation_view is not None,'Actual reference tensor view')
            with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
                robot.set_dof_friction_properties([[0.]],[[0.]],[[0.]]);robot.set_dof_armatures([[0.]]);robot.set_dof_max_velocities([[10.]]);robot.set_dof_max_efforts([[.01]]);robot.set_dof_gains([[0.]],[[0.]])
                robot.set_link_enabled_gravities(False)
                meta={'mode':item['mode'],'path':item['path'],'body_count':2,'collision_shapes':0,'same_owned_lab_view':True,'dof_names':list(robot.dof_names),'link_names':list(robot.link_names),
                    'inertias':array(robot.get_link_inertias()).tolist(),'masses':array(robot.get_link_masses()).tolist(),
                    'coms':array(robot.get_link_coms()[0]).tolist(),
                    'basis_wxyz':item['basis_wxyz'],'axis':str(item['joint'].GetAxisAttr().Get()),'pivot':item['pivot'],'gravity_enabled':array(robot.get_link_enabled_gravities()).tolist(),'initial_transforms':array(robot._physics_articulation_view.get_link_transforms()).tolist(),
                    'friction':[array(x).tolist() for x in robot.get_dof_friction_properties()], 'armature':array(robot.get_dof_armatures()).tolist(),
                    'tensor_drive_type':array(robot._physics_articulation_view.get_drive_types()).tolist(),
                    'velocity_limit':scalar(array,robot.get_dof_max_velocities()),'initial_q':scalar(array,robot.get_dof_positions()),'initial_qd':scalar(array,robot.get_dof_velocities())}
            ri=meta['link_names'].index('Rotor');ai=('X','Y','Z').index(meta['axis']);com=meta['coms'][0][ri];meta['effective_inertia']=meta['inertias'][0][ri][ai*3+ai]+meta['masses'][0][ri]*(sum(x*x for x in com)-com[ai]**2)
            self.packet['setup'].append(meta)
    def issue(self,step):
        if not 1<=step<=240:return None
        before=self.clock();issued=[]
        with self.backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
            for item in self.items:
                r=item['object'];c=command_for(step,item['mode']);before_q=scalar(self.array,r.get_dof_positions());before_qd=scalar(self.array,r.get_dof_velocities())
                r.set_dof_gains([[c['kp']]],[[c['kd']]]);r.set_dof_max_efforts([[c['cap']]]);r.set_dof_position_targets([[c['target']]]);r.set_dof_velocity_targets([[0.]]);r.set_dof_efforts([[c['external']]])
                issued.append({'mode':item['mode'],'step':step,'command':c,'before_q':before_q,'before_qd':before_qd})
        need(before==self.clock(),'Reference command stable clock');return {'clock_before_step':before,'issued':issued}
    def observe(self,issued):
        if issued is None:return
        before=self.clock();rows=[];sample={**issued,'clock_after_step':before,'rows':rows};self.packet['samples'].append(sample)
        with self.backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
            for item,command in zip(self.items,issued['issued']):
                r=item['object'];row=dict(command);rows.append(row)
                for key,getter in (('after_q',r.get_dof_positions),('after_qd',r.get_dof_velocities),('external_readback',r.get_dof_efforts),('projected',r.get_dof_projected_joint_forces),('cap_readback',r.get_dof_max_efforts)):
                    row[key]=scalar(self.array,getter())
                kp,kd=r.get_dof_gains();row['kp_readback']=scalar(self.array,kp);row['kd_readback']=scalar(self.array,kd)
                incoming=r.get_link_incoming_joint_force();row['incoming_force']=self.array(incoming[0]).tolist();row['incoming_torque']=self.array(incoming[1]).tolist()
                row['after_transforms']=self.array(r._physics_articulation_view.get_link_transforms()).tolist()
        after=self.clock();sample['clock_after_read']=after;need(before==after,'Reference read stable clock')

def create_safe(stage,ctx):
    packet={'setup':[],'samples':[],'errors':[]};bundle={'items':[],'packet':packet}
    try:bundle['items']=create(stage)
    except Exception as exc:packet['errors'].append({'phase':'CREATE','error':type(exc).__name__+': '+str(exc)})
    try:ctx.write(ctx.run/'output/reference.partial.json',packet)
    except Exception as exc:packet['errors'].append({'phase':'CREATE_PERSISTENCE','error':type(exc).__name__+': '+str(exc)})
    return bundle

class References:
    """Reference faults remain explicit and never become invented zero samples."""
    def __init__(self,ctx,bundle,backend,array,clock,view):
        self.ctx=ctx;self.packet=bundle['packet'];self.raw=None
        self.stream=None
        try:self.stream=(ctx.run/'output/reference.ndjson').open('x',encoding='utf-8',newline='\n')
        except Exception as exc:self.packet['errors'].append({'phase':'JOURNAL_OPEN','error':type(exc).__name__+': '+str(exc)})
        if not self.packet['errors']:
            try:self.raw=RawReferences(bundle['items'],backend,array,clock,view,self.packet)
            except Exception as exc:self.fail('BIND',exc)
        self.event({'phase':'SETUP','setup':self.packet['setup'],'errors':self.packet['errors']})
    def event(self,data):
        import json,math
        def safe(v):
            if isinstance(v,float) and not math.isfinite(v):return {'NONFINITE_RAW':repr(v)}
            if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
            if isinstance(v,(tuple,list)):return [safe(x) for x in v]
            return v
        cleaned=safe(data)
        if cleaned!=data:
            packet=safe(self.packet);self.packet.clear();self.packet.update(packet);self.packet['errors'].append({'phase':'NONFINITE_OBSERVATION','raw':cleaned})
        if self.stream is None:return
        try:self.stream.write(json.dumps(cleaned,allow_nan=False,separators=(',',':'))+'\n');self.stream.flush()
        except Exception as exc:self.packet['errors'].append({'phase':'PERSISTENCE','error':type(exc).__name__+': '+str(exc)})
    def fail(self,where,exc):
        self.packet['errors'].append({'phase':where,'error':type(exc).__name__+': '+str(exc)})
        self.event({'phase':'FAILED','error':self.packet['errors'][-1],'completed_prefix':self.packet['samples'][-1:]})
        try:self.ctx.write(self.ctx.run/'output/reference.partial.json',self.packet)
        except Exception as error:self.packet['errors'].append({'phase':'PARTIAL_PERSISTENCE','error':type(error).__name__+': '+str(error)})
    def issue(self,step):
        if self.packet['errors'] or self.raw is None or not 1<=step<=240:return None
        try:
            issued=self.raw.issue(step);self.event({'phase':'ISSUED','data':issued});return issued
        except Exception as exc:self.fail('ISSUE',exc);return None
    def observe(self,issued):
        if issued is None or self.packet['errors']:return
        try:self.raw.observe(issued);self.event({'phase':'OBSERVED','data':self.packet['samples'][-1]})
        except Exception as exc:self.fail('OBSERVE',exc)
    def close(self):
        self.event({'phase':'CLOSE_PACKET','data':self.packet})
        try:self.ctx.write(self.ctx.run/'output/reference.partial.json',self.packet)
        except Exception as exc:self.fail('CLOSE_PERSISTENCE',exc)
        try:
            if self.stream is not None:self.stream.close()
        except Exception as exc:self.packet['errors'].append({'phase':'CLOSE','error':type(exc).__name__+': '+str(exc)})
