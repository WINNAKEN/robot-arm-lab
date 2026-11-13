"""Normalize only articulation-root metadata; preserve the physical world joint."""
import copy
import hashlib
from pathlib import Path

SCOPE='/World/Robot'
BASE=SCOPE+'/Geometry/Base'
JOINT=SCOPE+'/Physics/root_joint'
ROOT_API='PhysicsArticulationRootAPI'
PHYSX_API='PhysxArticulationAPI'


def need(ok, reason):
    if not ok:raise ValueError(reason)


def choose(packet, roots, stopped):
    need(stopped is True,'Root normalization requires stopped timeline')
    need(roots==[BASE] and packet['articulation_path']==BASE,'Exactly original Base root')
    bodies=packet['bodies'];names={b['name'] for b in bodies}
    need(len(bodies)==len(names)==11 and 'Base' in names,'Exact distinct physical body census')
    base=next(b for b in bodies if b['name']=='Base')
    need(base['path']==BASE and ROOT_API in base['applied_schemas'] and PHYSX_API not in base['applied_schemas'],'Original source root metadata')
    candidates=[j for j in packet['joints'] if j['name']=='root_joint']
    need(len(candidates)==1,'Exactly one source world root joint')
    joint=candidates[0]
    need(joint['type']=='fixed' and joint['path']==JOINT and joint['body0']==SCOPE and joint['body1']==BASE and joint['enabled'] is True,'Exact enabled world fixed joint')
    need(JOINT.startswith(SCOPE+'/') and all(b['path'].startswith(SCOPE+'/') for b in bodies),'New root contains joint and all links')
    role=packet['world_anchors'][SCOPE]
    need(role['rigid_body'] is False and role['mass_api'] is False and role['type']=='Xform','World target is a nonphysical Xform')
    need(role['world_matrix']==[[float(i==j) for j in range(4)] for i in range(4)] and role['time_samples']==0,'Identity time-invariant world target')
    need(ROOT_API not in role['applied_schemas'] and PHYSX_API not in role['applied_schemas'],'No preexisting destination root API')
    return {'before_root':BASE,'after_root':SCOPE,'world_joint':JOINT}


def normalize(stage, packet, roots, timeline):
    from pxr import UsdPhysics,PhysxSchema
    receipt=choose(packet,roots,timeline.is_stopped())
    old=stage.GetPrimAtPath(BASE);new=stage.GetPrimAtPath(SCOPE)
    need(bool(old) and bool(new) and not new.HasAPI(UsdPhysics.RigidBodyAPI) and not new.HasAPI(UsdPhysics.MassAPI),'Actual nonphysical destination')
    need(old.RemoveAPI(UsdPhysics.ArticulationRootAPI),'Remove old root API')
    need(bool(UsdPhysics.ArticulationRootAPI.Apply(new)) and bool(PhysxSchema.PhysxArticulationAPI.Apply(new)),'Apply fixed-base ancestor APIs')
    actual=[str(p.GetPath()) for p in stage.Traverse() if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    need(actual==[SCOPE] and not old.HasAPI(UsdPhysics.ArticulationRootAPI),'Actual unique new articulation root')
    return receipt


def verify(packet, oracle, output_dir=None):
    near=oracle['near'];need(type(packet['schema_version']) is int and packet['schema_version']==1,'Binding version')
    before,after=packet['before'],packet['after']
    expected=choose(before,[before['articulation_path']],True)
    need(packet['normalization']==expected and after['articulation_path']==SCOPE,'Exact reviewed root metadata change')
    need(after['self_collision'] is False,'Self collision remains false')
    old_bodies=copy.deepcopy(before['bodies']);new_bodies=copy.deepcopy(after['bodies'])
    for bodies,old in ((old_bodies,True),(new_bodies,False)):
        base=next(b for b in bodies if b['name']=='Base')
        apis=base['applied_schemas']
        if old:base['applied_schemas']=[a for a in apis if a!=ROOT_API]
        else:need(ROOT_API not in apis and PHYSX_API not in apis,'Base no longer has articulation-root metadata')
    near(new_bodies,old_bodies,0.)
    for key in ('joints','colliders','tool0','units','root_placement'):
        near(after[key],before[key],0.)
    old_roles=copy.deepcopy(before['world_anchors']);new_roles=copy.deepcopy(after['world_anchors'])
    expected_apis=set(old_roles[SCOPE]['applied_schemas'])|{ROOT_API,PHYSX_API}
    need(set(new_roles[SCOPE]['applied_schemas'])==expected_apis,'Only declared ancestor APIs added')
    new_roles[SCOPE]['applied_schemas']=old_roles[SCOPE]['applied_schemas']
    near(new_roles,old_roles,0.)
    if output_dir is not None:
        for label,row in (('before',before),('after',after)):
            raw=(Path(output_dir)/('base-'+label+'.usda')).read_bytes()
            need(hashlib.sha256(raw).hexdigest()==row['usd_sha256'],'Binding snapshot tied to written '+label+' USD')
    return {'status':'FIXED_BASE_ROOT_REPRESENTATION_VERIFIED','before_root':BASE,'after_root':SCOPE,'physical_inputs_unchanged':True}
