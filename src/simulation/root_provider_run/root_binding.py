"""Normalize only articulation-root metadata; preserve the physical world joint."""
import copy
import hashlib
import math
from pathlib import Path

SCOPE='/World/Robot'
BASE=SCOPE+'/Geometry/Base'
JOINT=SCOPE+'/Physics/root_joint'
ROOT_API='PhysicsArticulationRootAPI'
PHYSX_API='PhysxArticulationAPI'
NEWTON_API='NewtonArticulationRootAPI'
PROVIDER_NAMES=['newton:jointsAddMobility','newton:selfCollisionEnabled']


def need(ok, reason):
    if not ok:raise ValueError(reason)


def choose(packet, roots, stopped):
    need(stopped is True,'Root normalization requires stopped timeline')
    need(roots==[BASE] and packet['articulation_path']==BASE,'Exactly original Base root')
    bodies=packet['bodies'];names={b['name'] for b in bodies}
    need(len(bodies)==len(names)==11 and 'Base' in names,'Exact distinct physical body census')
    base=next(b for b in bodies if b['name']=='Base')
    need(base['path']==BASE and ROOT_API in base['applied_schemas'] and NEWTON_API in base['applied_schemas'] and PHYSX_API not in base['applied_schemas'],'Original source root metadata')
    candidates=[j for j in packet['joints'] if j['name']=='root_joint']
    need(len(candidates)==1,'Exactly one source world root joint')
    joint=candidates[0]
    need(joint['type']=='fixed' and joint['path']==JOINT and joint['body0']==SCOPE and joint['body1']==BASE and joint['enabled'] is True,'Exact enabled world fixed joint')
    need(JOINT.startswith(SCOPE+'/') and all(b['path'].startswith(SCOPE+'/') for b in bodies),'New root contains joint and all links')
    role=packet['world_anchors'][SCOPE]
    need(role['rigid_body'] is False and role['mass_api'] is False and role['type']=='Xform','World target is a nonphysical Xform')
    need(role['world_matrix']==[[float(i==j) for j in range(4)] for i in range(4)] and role['time_samples']==0,'Identity time-invariant world target')
    need(all(api not in role['applied_schemas'] for api in (ROOT_API,NEWTON_API,PHYSX_API)),'No preexisting destination root API')
    return {'before_root':BASE,'after_root':SCOPE,'world_joint':JOINT}


def normalize(stage, packet, roots, timeline):
    from pxr import Usd,UsdPhysics,PhysxSchema
    receipt=choose(packet,roots,timeline.is_stopped())
    old=stage.GetPrimAtPath(BASE);new=stage.GetPrimAtPath(SCOPE)
    need(bool(old) and bool(new) and not new.HasAPI(UsdPhysics.RigidBodyAPI) and not new.HasAPI(UsdPhysics.MassAPI),'Actual nonphysical destination')
    definition=Usd.SchemaRegistry().FindAppliedAPIPrimDefinition(NEWTON_API)
    need(bool(definition),'Installed Newton root schema definition required')
    before_provider=observe_provider(stage)
    values=[]
    for name in definition.GetPropertyNames():
        attr=old.GetAttribute(name)
        destination=new.GetAttribute(name)
        need(not destination or (not destination.HasAuthoredValueOpinion() and not destination.GetTimeSamples()),'No conflicting destination provider attribute')
        need(bool(attr) and not attr.GetTimeSamples(),'Root provider attributes must be time invariant')
        if attr and attr.HasAuthoredValueOpinion():
            values.append((name,attr.GetTypeName(),attr.Get(),attr.GetVariability(),attr.IsCustom()))
    need(old.RemoveAppliedSchema(NEWTON_API),'Remove old root provider API')
    need(old.RemoveAPI(UsdPhysics.ArticulationRootAPI),'Remove old root API')
    need(new.AddAppliedSchema(NEWTON_API),'Move root provider API to ancestor')
    need(bool(UsdPhysics.ArticulationRootAPI.Apply(new)) and bool(PhysxSchema.PhysxArticulationAPI.Apply(new)),'Apply fixed-base ancestor APIs')
    for name,kind,value,variability,custom in values:
        need(new.CreateAttribute(name,kind,custom=custom,variability=variability).Set(value),'Preserve authored root provider value')
        need(new.GetAttribute(name).Get()==value,'Root provider value readback')
    actual=[str(p.GetPath()) for p in stage.Traverse() if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    need(actual==[SCOPE] and not old.HasAPI(UsdPhysics.ArticulationRootAPI),'Actual unique new articulation root')
    verify_provider(before_provider,observe_provider(stage))
    return receipt


def _plain(value):
    if value is None or type(value) in (bool,int,str):return value
    if type(value) is float:
        need(math.isfinite(value),'Finite provider value');return value
    if type(value) in (list,tuple):return [_plain(x) for x in value]
    raise ValueError('Unsupported provider value type')


def observe_provider(stage):
    """Actual USD query, not a declaration from the import configuration."""
    from pxr import Usd
    definition=Usd.SchemaRegistry().FindAppliedAPIPrimDefinition(NEWTON_API)
    need(bool(definition),'Installed Newton root schema definition required')
    names=sorted(str(n) for n in definition.GetPropertyNames())
    need(names==PROVIDER_NAMES,'Exact installed supported Newton root attribute inventory')
    result={'names':names}
    for label,path in (('base',BASE),('scope',SCOPE)):
        prim=stage.GetPrimAtPath(path);need(bool(prim),'Provider prim exists')
        metadata=prim.GetMetadata('apiSchemas')
        row={'authored_apis':[] if metadata is None else [str(x) for x in metadata.GetAddedOrExplicitItems()],
             'applied_apis':[str(x) for x in prim.GetAppliedSchemas()],'attributes':{}}
        for name in names:
            attr=prim.GetAttribute(name)
            row['attributes'][name]={'exists':bool(attr),'authored':bool(attr and attr.HasAuthoredValueOpinion()),
                'times':[float(t) for t in attr.GetTimeSamples()] if attr else [],
                'type':str(attr.GetTypeName()) if attr else None,
                'variability':str(attr.GetVariability()) if attr else None,
                'custom':bool(attr.IsCustom()) if attr else False,
                'value':_plain(attr.Get()) if attr else None}
        result[label]=row
    return result


def verify_provider(before,after):
    """Pure HOST guard: exact allowed API deltas BEFORE any restoration."""
    names=before['names']
    need(type(names) is list and names==PROVIDER_NAMES,'Exact complete supported provider names')
    need(after['names']==names,'Same installed provider definition')
    for label in ('base','scope'):
        for key in ('authored_apis','applied_apis'):
            old=before[label][key];new=after[label][key]
            need(all(type(a) is list and len(a)==len(set(a)) and all(type(x) is str and x for x in a) for a in (old,new)),'Typed exact API inventories')
            if label=='base':
                need({ROOT_API,NEWTON_API}.issubset(old),'Original provider APIs present')
                expected=set(old)-{ROOT_API,NEWTON_API}
            else:
                need(not set(old)&{ROOT_API,NEWTON_API,PHYSX_API},'Original destination has no root API')
                expected=set(old)|{ROOT_API,NEWTON_API,PHYSX_API}
            need(set(new)==expected,'Exact allowed '+label+' '+key+' delta')
        need(set(before[label]['attributes'])==set(after[label]['attributes'])==set(names),'Complete provider property inventory')
    for name in names:
        original=before['base']['attributes'][name];destination=before['scope']['attributes'][name]
        actual=after['scope']['attributes'][name];old_after=after['base']['attributes'][name]
        need(original['exists'] is True and type(original['authored']) is bool and original['times']==[],'Static actual source provider property')
        need(destination['authored'] is False and destination['times']==[],'No conflicting destination provider attribute')
        need(actual['exists'] is True and actual['authored'] is original['authored'] and actual['times']==[],'Exact provider authored state')
        for key in ('value','type','variability','custom'):
            need(actual[key]==original[key],'Same effective provider '+key)
        if original['authored']:need(old_after==original,'Original authored provider property unchanged')
        else:need(old_after['authored'] is False,'No source property introduced')
    return {'status':'EXACT_PROVIDER_DELTA_VERIFIED','names':names}


def prove_files(before_path,after_path):
    """Reopen saved snapshots; validate deltas, then compare remaining full USD."""
    from pxr import Sdf,Usd
    stages=[]
    for path in (before_path,after_path):
        source=Sdf.Layer.FindOrOpen(str(path));need(bool(source),'Saved USD layer opens')
        layer=Sdf.Layer.CreateAnonymous('provider-proof.usda');layer.TransferContent(source)
        stages.append(Usd.Stage.Open(layer))
    left,right=stages
    before,after=observe_provider(left),observe_provider(right)
    verify_provider(before,after)  # MUST precede metadata restoration.
    for path in (BASE,SCOPE):
        old=left.GetPrimAtPath(path);new=right.GetPrimAtPath(path)
        metadata=old.GetMetadata('apiSchemas')
        if metadata is None:new.ClearMetadata('apiSchemas')
        else:new.SetMetadata('apiSchemas',metadata)
    for name in before['names']:
        if before['base']['attributes'][name]['authored']:
            need(right.GetPrimAtPath(SCOPE).RemoveProperty(name),'Remove only declared copied provider property')
    need(left.GetRootLayer().ExportToString()==right.GetRootLayer().ExportToString(),'All remaining authored USD exactly unchanged')
    return {'schema_version':1,'before':before,'after':after,
            'before_sha256':hashlib.sha256(Path(before_path).read_bytes()).hexdigest(),
            'after_sha256':hashlib.sha256(Path(after_path).read_bytes()).hexdigest(),
            'api_delta_checked_before_restoration':True,'remaining_authored_USD_identical':True}


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
        if old:base['applied_schemas']=[a for a in apis if a not in (ROOT_API,NEWTON_API)]
        else:need(all(a not in apis for a in (ROOT_API,NEWTON_API,PHYSX_API)),'Base no longer has articulation-root metadata')
    near(new_bodies,old_bodies,0.)
    for key in ('joints','colliders','tool0','units','root_placement'):
        near(after[key],before[key],0.)
    old_roles=copy.deepcopy(before['world_anchors']);new_roles=copy.deepcopy(after['world_anchors'])
    expected_apis=set(old_roles[SCOPE]['applied_schemas'])|{ROOT_API,NEWTON_API,PHYSX_API}
    need(set(new_roles[SCOPE]['applied_schemas'])==expected_apis,'Only declared ancestor APIs added')
    new_roles[SCOPE]['applied_schemas']=old_roles[SCOPE]['applied_schemas']
    near(new_roles,old_roles,0.)
    proof=packet['provider']
    need(type(proof['schema_version']) is int and proof['schema_version']==1 and proof['api_delta_checked_before_restoration'] is True and proof['remaining_authored_USD_identical'] is True,'Actual provider proof required')
    verify_provider(proof['before'],proof['after'])
    for label,observed in (('before',before),('after',after)):
        base=next(b for b in observed['bodies'] if b['name']=='Base')
        need(set(proof[label]['base']['applied_apis'])==set(base['applied_schemas']) and set(proof[label]['scope']['applied_apis'])==set(observed['world_anchors'][SCOPE]['applied_schemas']),'Provider API observations agree with SDK snapshot')
    need(proof['before_sha256']==before['usd_sha256'] and proof['after_sha256']==after['usd_sha256'],'Provider proof tied to SDK snapshot hashes')
    if output_dir is not None:
        for label,row in (('before',before),('after',after)):
            raw=(Path(output_dir)/('base-'+label+'.usda')).read_bytes()
            need(hashlib.sha256(raw).hexdigest()==row['usd_sha256'],'Binding snapshot tied to written '+label+' USD')
    return {'status':'FIXED_BASE_ROOT_REPRESENTATION_VERIFIED','before_root':BASE,'after_root':SCOPE,'physical_inputs_unchanged':True}
