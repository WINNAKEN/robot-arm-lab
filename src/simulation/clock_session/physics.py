if __name__=='__main__':raise SystemExit('Use launch.ps1')
import os
import importlib
import hashlib
from pathlib import Path
CALLBACKS={'warm_start','on_stop','stage_open','stage_close','post_warm_start'}
REFERENCES=('isaacsim.core.experimental.prims.impl.articulation','isaacsim.core.experimental.prims.impl.rigid_prim','isaacsim.core.experimental.prims.impl.prim')
def expected_prims():
    base='/World/Robot/Geometry/Base';paths=[base]
    for i in range(1,7):paths.append(paths[-1]+'/Link'+str(i))
    return [('Articulation',base),*[('RigidPrim',p) for p in paths],('RigidPrim','/World/ContactProbe')]

def source_hashes():
    result={}
    for name,pin in PINNED.items():
        m=importlib.import_module(name);p=Path(m.__file__);actual=hashlib.sha256(p.read_bytes()).hexdigest()
        if actual!=pin:raise ValueError('Unsupported installed physics source '+name)
        result[name]={'origin':str(p),'sha256':actual}
    return result

def bind(api,sim,prims):
    out=api['run']/'output/physics-binding.json';need=api['need'];view=None
    value={'run_id':api['run'].name,'job_sha256':api['sha'](api['run']/'job.json'),'pid':os.getpid(),'status':'FAILED','phase':'ENTERED','managers':[],'prims':[]}
    try:
        value['sources']=source_hashes();manager=sim.physics_manager
        value['lab_manager']=manager.__module__+'.'+manager.__name__;value['device']=str(sim.device)
        need(value['lab_manager']=='isaaclab_physx.physics.physx_manager.PhysxManager' and value['device']=='cpu','Owned CPU Lab PhysxManager')
        view=manager.get_physics_sim_view();value['lab_view_id']=id(view) if view is not None else None;value['lab_view_valid']=view is not None and bool(view.is_valid)
        need(value['lab_view_valid'],'Valid Lab physics view after reset')
        references={name:importlib.import_module(name).SimulationManager for name in REFERENCES}
        value['reference_modules']={name:id(m) for name,m in references.items()}
        managers=list({id(m):m for m in references.values()}.values())
        # Validate every owner before changing any cache.
        for sdk in managers:
            previous=getattr(sdk,'_physics_sim_view__warp',None);callbacks=sdk.get_default_callback_status()
            row={'name':sdk.__module__+'.'+sdk.__name__,'id':id(sdk),'before_view_id':None if previous is None else id(previous),'callbacks':dict(callbacks),'device':str(sdk.get_physics_sim_device()),'engine':str(sdk.get_active_physics_engine()),'after_view_id':None}
            value['managers'].append(row)
            need(row['name']=='isaacsim.core.simulation_manager.impl.simulation_manager.SimulationManager','Pinned SDK manager class')
            need(set(callbacks)==CALLBACKS and all(type(v) is bool and not v for v in callbacks.values()),'Complete inactive SDK callbacks')
            need(row['device']=='cpu' and row['engine']=='physx','Same CPU PhysX device/engine')
            need(previous is None or previous is view,'Reject foreign existing SDK view')
        value['phase']='OWNERS_VALIDATED';api['write'](out,value)
        for sdk,row in zip(managers,value['managers']):
            sdk._physics_sim_view__warp=view;row['after_view_id']=id(sdk._physics_sim_view__warp)
        for p in prims:
            p._on_physics_ready(None)
            sdk=importlib.import_module(type(p).__module__).SimulationManager
            row={'type':type(p).__name__,'module':type(p).__module__,'paths':list(p.paths),'manager_id':id(sdk),'view_id':id(sdk._physics_sim_view__warp),'valid':bool(p.is_physics_tensor_entity_valid())}
            value['prims'].append(row);need(row['valid'] and row['view_id']==id(view),'Real prim tensor entity bound')
        value.update(status='READY',phase='PRIMS_READY');check(value,value['run_id'],value['job_sha256'],value['pid'],api['cfg'],need)
    except Exception as exc:
        value.update(status='FAILED',primary_error=repr(exc));raise
    finally:api['write'](out,value)

def check(value,run_id,job_hash,pid,cfg,need):
    need(value['run_id']==run_id and value['job_sha256']==job_hash and value['pid']==pid,'Physics report same process/job')
    need(value['status']=='READY' and value['phase']=='PRIMS_READY','Physics readiness completed')
    need(value['lab_manager']=='isaaclab_physx.physics.physx_manager.PhysxManager' and value['device']=='cpu' and value['lab_view_valid'] is True,'Valid CPU Lab manager')
    vid=value['lab_view_id'];need(type(vid) is int and vid>0,'Actual Lab view identity')
    need(set(value['sources'])==set(PINNED),'Complete installed source evidence')
    for name,row in value['sources'].items():
        root=cfg['installation_prefix'] if name.startswith('isaaclab') else cfg['isaac_root']
        need(row['sha256']==PINNED[name] and Path(row['origin']).is_absolute() and Path(row['origin']).resolve().is_relative_to(Path(root).resolve()),'Pinned actual physics source')
    managers=value['managers'];need(1<=len(managers)<=3,'Bounded manager references');ids=set()
    refs=value.get('reference_modules');need(type(refs) is dict and set(refs)==set(REFERENCES),'Complete three-module manager observation')
    for m in managers:
        need(type(m['id']) is int and m['id']>0 and m['id'] not in ids,'Unique SDK manager identity');ids.add(m['id'])
        need(m['name']=='isaacsim.core.simulation_manager.impl.simulation_manager.SimulationManager' and m['device']=='cpu' and m['engine']=='physx','Pinned same backend manager')
        need(m['before_view_id'] is None or m['before_view_id']==vid,'No foreign view overwritten')
        need(m['after_view_id']==vid and set(m['callbacks'])==CALLBACKS and all(type(v) is bool and not v for v in m['callbacks'].values()),'One view with complete inactive SDK callbacks')
    need(all(type(v) is int and v>0 for v in refs.values()) and set(refs.values())==ids,'All referenced owners observed exactly')
    need(len(value['prims'])==9 and sorted((p['type'],p['paths'][0]) for p in value['prims'] if len(p['paths'])==1)==sorted(expected_prims()),'Exact nine model consumers')
    for p in value['prims']:
        module=REFERENCES[0] if p['type']=='Articulation' else REFERENCES[1]
        need(p['module']==module and p['manager_id']==refs[module] and p['view_id']==vid and p['valid'] is True,'Actual consumer bound to Lab view')
PINNED={'isaacsim.core.experimental.prims.impl.articulation': '9a2b617077bb2171436465d0f6a6140949b506970810a247bf9553678aa6b374', 'isaacsim.core.experimental.prims.impl.rigid_prim': 'f9d5863e2cf4b9f4746831e0f26e4f346046a107fa6f96bc8dbe16e058cd50eb', 'isaacsim.core.experimental.prims.impl.prim': 'bffa6875946a40b754fe048328331a179beb4af0725cbda522e5aee2a7f15ac0', 'isaacsim.core.simulation_manager.impl.simulation_manager': '0dd33b5f6927112450fb06bc81a3dffb8f82409b108d64657853f3cec11b1833', 'isaaclab_physx.physics.physx_manager': 'dc1a3fbabbb54a4a3f7c45bf10e25643a346b06a6d9577e8f974584df9869742'}
