"""048 module/GPU and static Lab-stage probes. No reset, step or motor command."""
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import traceback


def module_observation(run):
    from setup import need
    prefix=(run/'packages').resolve();sys.path.insert(0,str(prefix));modules={}
    for name,distribution in [('isaaclab','isaaclab'),('torch','torch'),('torchvision','torchvision'),('warp','warp-lang'),('gymnasium','gymnasium'),('rsl_rl','rsl-rl-lib')]:
        value=importlib.import_module(name);origin=Path(value.__file__).resolve()
        need(origin.is_relative_to(prefix),'Unexpected module provider: '+name)
        modules[name]={'version':importlib.metadata.version(distribution),'origin':str(origin)}
    import torch
    need(modules['isaaclab']['version']=='3.0.0' and modules['torch']['version']=='2.11.0+cu130' and modules['warp']['version']=='1.17.0','Critical module versions')
    need(torch.cuda.is_available() and torch.version.cuda.startswith('13.'),'CUDA13 GPU required; CPU replacement rejected')
    tensor=torch.ones((2,3),device='cuda:0');answer=float(tensor.sum().item())
    need(answer==6. and tensor.is_cuda,'Actual GPU tensor operation')
    return {'modules':modules,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),'tensor_device':str(tensor.device),'tensor_sum':answer}


def static_model(run):
    from setup import need,read,sha
    cfg=read(run/'config.json');baseline=read(run/'baseline.json')
    need(baseline['motion_accepted'] is False,'This probe implements the static-only failed-baseline branch')
    # -I ignored inherited paths before the closed bootstrap gate. Add only the
    # configured SDK's own environment paths after all project bytes were checked.
    sdk=Path(cfg['isaac_root']).resolve()
    for path in os.environ.get('PYTHONPATH','').split(os.pathsep):
        if path:
            p=Path(path).resolve();need(p.is_relative_to(sdk),'Foreign SDK Python search path');sys.path.append(str(p))
    import isaaclab
    from isaacsim import SimulationApp
    app=None;code=1
    try:
        app=SimulationApp({'headless':True,'fast_shutdown':True})
        from isaaclab.sim import SimulationCfg,SimulationContext
        from pxr import Usd,UsdGeom,UsdPhysics,Gf
        import omni.timeline
        sim=SimulationContext(SimulationCfg(dt=1/120,device='cpu',gravity=(0.,0.,0.)))
        stage=sim.stage
        UsdGeom.SetStageMetersPerUnit(stage,1.);UsdPhysics.SetStageKilogramsPerUnit(stage,1.);UsdGeom.SetStageUpAxis(stage,'Z')
        root=stage.DefinePrim('/World/Robot','Xform');root.GetReferences().AddReference(str(run/'input.usda'))
        timeline=omni.timeline.get_timeline_interface()
        need(timeline.is_stopped() and sim.get_physics_step_count()==0,'Static connection must not advance physics')
        from extract_usd import observe_stage
        import frames
        source=Usd.Stage.Open(str(run/'input.usda'));need(source is not None,'Source USD opens')
        runtime={'run_id':run.name,'pid':os.getpid(),'isaaclab_version':isaaclab.__version__}
        actual=observe_stage(stage,run/'input.usda',runtime,True);reference=observe_stage(source,run/'input.usda',runtime,True)
        source_root=str(source.GetDefaultPrim().GetPath())
        def normalize(value):
            if isinstance(value,str) and value.startswith('/World/Robot'):return source_root+value[len('/World/Robot'):]
            if isinstance(value,list):return [normalize(x) for x in value]
            if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
            return value
        # Compare complete body fields (LINK, COM, principal inertia, visuals) and
        # both local sides/relationships of every fixed/revolute joint.
        need(normalize(actual['bodies'])==reference['bodies'],'Composed LINK/COM/inertia/visual frame fields differ')
        need(sorted(normalize(actual['joints']),key=lambda x:x['name'])==sorted(reference['joints'],key=lambda x:x['name']),'Both joint-frame sides/axes differ')
        bodies={b['name']:b for b in actual['bodies']};joints={j['name']:j for j in actual['joints'] if j['type']=='revolute'}
        need(set(bodies)=={'Base',*[f'Link{i}' for i in range(1,7)]} and set(joints)=={f'J{i}' for i in range(1,7)},'Exact 7 LINK / 6 DOF model')
        fk=frames.fk(frames.decode((run/'kinematics.json').read_bytes()),[0.]*6)
        maximum=0.
        for i,row in enumerate(fk,1):
            body=bodies['Link'+str(i)]
            maximum=max(maximum,max(abs(a-b) for a,b in zip(body['position'],row['origin_m'])),
                        max(abs(a-b) for ar,br in zip(body['rotation'],row['rotation_world']) for a,b in zip(ar,br)))
        need(maximum<=1e-6,'CAD displayed zero FK mismatch')
        def collider_fields(s,root_path):
            cache=UsdGeom.XformCache();items=[]
            for p in s.Traverse():
                if not str(p.GetPath()).startswith(root_path+'/') or not p.HasAPI(UsdPhysics.CollisionAPI):continue
                owner=p
                while owner and not owner.HasAPI(UsdPhysics.RigidBodyAPI):owner=owner.GetParent()
                need(bool(owner),'Collider owner')
                local=cache.GetLocalToWorldTransform(p)*cache.GetLocalToWorldTransform(owner).GetInverse()
                items.append({'suffix':str(p.GetPath())[len(root_path):],'owner':owner.GetName(),
                    'matrix':[[float(local[i][j]) for j in range(4)] for i in range(4)],
                    'enabled':bool(UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get())})
            return sorted(items,key=lambda x:x['suffix'])
        colliders=collider_fields(stage,'/World/Robot');need(len(colliders)==7 and colliders==collider_fields(source,source_root),'All local collider frames/owners differ')
        need(actual['units']['meters_per_unit']==actual['units']['kilograms_per_unit']==1 and actual['units']['up_axis']=='Z','SI / Z-up')
        manager=sim.physics_manager.__module__+'.'+sim.physics_manager.__name__
        need('physx' in manager.lower(),'Actual Lab PhysX manager required')
        from setup import write
        write(run/'lab-static-snapshot.json',actual)
        result={'status':'LAB_STATIC_MODEL_CONNECTION_DATA_CAPTURED','run_id':run.name,'pid':os.getpid(),'parent_pid':os.getppid(),
            'job_sha256':sha(run/'job.json'),'manager':manager,'model_sha256':sha(run/'input.usda'),'snapshot_sha256':sha(run/'lab-static-snapshot.json'),
            'dof_names':[f'J{i}' for i in range(1,7)],'links':7,'colliders':7,'max_zero_frame_error':maximum,'steps':sim.get_physics_step_count(),
            'gravity_m_s2':list(sim.cfg.gravity),'scope':'STATIC_ONLY_NO_RESET_NO_STEP','dynamic_connection':'NOT_RUN',
            'policy_training':'NOT_RUN','weights':None,'hardware_approved':False,'physical_calibration':False}
        need(result['steps']==0 and result['gravity_m_s2']==[0.,0.,0.],'No static physics playback')
        write(run/'native-result.json',result);code=0
    except Exception as e:
        from setup import write
        write(run/'native-result.json',{'status':'FAILED','run_id':run.name,'pid':os.getpid(),'reason':repr(e),'traceback':traceback.format_exc(),'hardware_approved':False})
        raise
    finally:
        if app is not None:app.close(wait_for_replicator=False,exit_code=code)


def main():
    from setup import write,sha
    role,folder=sys.argv[1:];run=Path(folder).resolve()
    try:
        if role=='modules':
            result={'status':'MODULE_GPU_DATA_CAPTURED','run_id':run.name,'pid':os.getpid(),'parent_pid':os.getppid(),
                'job_sha256':sha(run/'job.json'),'hardware_approved':False,**module_observation(run)}
            write(run/'modules-result.json',result)
        elif role=='native':
            sys.path.insert(0,str(run/'packages'));static_model(run)
        else:raise ValueError('Unknown fixed probe role')
    except Exception as e:
        write(run/(role+'-failed.json'),{'status':'FAILED','run_id':run.name,'pid':os.getpid(),'reason':repr(e),'traceback':traceback.format_exc(),'hardware_approved':False})
        raise


if __name__=='__main__':main()
