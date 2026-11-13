"""Simulation-only policy manifests and reference requests; no weights are executed."""
from pathlib import Path
try:
    from .profile import ROOT,validate,require,read,sha
    from .trajectory import action_reference
except ImportError:
    from profile import ROOT,validate,require,read,sha
    from trajectory import action_reference


def untrained_contract(profile,root=ROOT):
    validate(profile,root)
    return {'schema_version':1,'status':'UNTRAINED','profile_hash':profile['profile_hash'],
        'control_signature':profile['control_signature'],'asset_sha256':profile['asset_sha256'],
        'coordinate':profile['coordinate'],'observation_dim':41,'action_dim':6,
        'hardware_approved':False,'calibration_approved':False,'mass_inertia':'SIMULATION_ASSUMPTION',
        'weights_path':None,'weights_sha256':None}


def validate_weights_manifest(manifest_path,profile,root=ROOT):
    """Validate metadata/opaque bytes only. This is not policy performance approval."""
    expected=untrained_contract(profile,root);m=read(manifest_path)
    require(type(m) is dict and set(m)==set(expected),'Policy manifest schema')
    require(m['status']=='TRAINED_SIMULATION_ONLY','No trained simulation-only weights available')
    for key in ('schema_version','profile_hash','control_signature','asset_sha256','coordinate','observation_dim','action_dim','mass_inertia'):
        require(type(m[key]) is type(expected[key]) and m[key]==expected[key],'Policy model/profile/shape mismatch: '+key)
    require(m['hardware_approved'] is False and m['calibration_approved'] is False,'Policy cannot grant physical authority')
    require(type(m['weights_path']) is str and type(m['weights_sha256']) is str,'Trained opaque weight identity required')
    base=Path(manifest_path).resolve().parent;relative=Path(m['weights_path'])
    require(not relative.is_absolute() and '..' not in relative.parts,'Weight path must stay in policy package')
    weight=(base/relative).resolve()
    require(weight.is_relative_to(base) and sha(weight)==m['weights_sha256'],'Weight bytes changed')
    return {'status':'METADATA_AND_HASH_ONLY','weights_executed':False,'physical_authority':False,'manifest':m}


def reference_request(profile,q_command,action,root=ROOT):
    validate(profile,root);target,applied,rows=action_reference(q_command,action,profile['config'])
    return {'type':'SIM_REFERENCE_SEQUENCE','coordinate':profile['coordinate'],'joint_names':profile['joint_names'],
        'profile_hash':profile['profile_hash'],'policy_state':'UNTRAINED_PREPARATION','target':target,'applied_action':applied,
        'samples':rows,'hardware_approved':False,'calibration_approved':False,'device_dispatch':'NOT_IMPLEMENTED_NOT_AUTHORIZED'}
