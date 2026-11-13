"""044 pinned assumptions and failed-baseline profile. No physics/learning execution."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
JOINTS=[f'J{i}' for i in range(1,7)]
ASSET_SHA='117d94292c75e89b201e12606eafbcf24065c537c6f8308647562f9a0679f4db'


def require(ok,why):
    if not ok:raise ValueError(why)


def number(x):
    require(type(x) in (int,float) and math.isfinite(x),'Finite number required')
    return float(x)


def vector(x,n=6):
    require(type(x) in (list,tuple) and len(x)==n,'Numeric vector shape')
    return [number(v) for v in x]


def read(path):
    def pairs(items):
        obj={}
        for k,v in items:
            require(k not in obj,'Duplicate JSON key');obj[k]=v
        return obj
    def invalid(x):raise ValueError('Nonfinite JSON constant: '+x)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def configuration(root=ROOT):
    cfg=read(Path(root)/'src/simulation/rl_prep/task_config.json')
    require(set(cfg)=={'schema_version','scope','input_pins','physics_hz','move_s','hold_s','max_decisions','observation_dim','action_dim','limits','reward','ppo_candidate'},'Configuration schema')
    require(type(cfg['schema_version']) is int and cfg['schema_version']==1 and cfg['scope']=='SIMULATION_PREPARATION_ONLY','Preparation scope')
    for key,value in {'physics_hz':120,'max_decisions':16,'observation_dim':41,'action_dim':6}.items():
        require(type(cfg[key]) is int and cfg[key]==value,'Frozen task dimension/rate: '+key)
    require(number(cfg['move_s'])==1.5 and number(cfg['hold_s'])==.5,'Fixed 240-tick decision duration')
    lim=cfg['limits']
    require(set(lim)=={'command_deg','goal_deg','increment_deg','velocity_rad_s','acceleration_rad_s2','jerk_rad_s3','actual_abort_deg'},'Limit schema')
    require(all(number(v)>0 for v in lim.values()),'Positive simulation limits')
    require(lim['increment_deg']<=2 and lim['goal_deg']<=lim['command_deg']<=10 and
            lim['velocity_rad_s']<=.5 and lim['actual_abort_deg']==15,'Simulation-only envelope')
    for v in cfg['reward'].values():require(number(v)>=0,'Nonnegative reward weight')
    require(set(cfg['reward'])=={'progress','position','velocity','acceleration','jerk','action_change','time','goal_bonus','fault_penalty'},'Reward schema')
    candidate=cfg['ppo_candidate']
    require(set(candidate)=={'status','algorithm','suggested_library','actor_hidden_dims','critic_hidden_dims','learning_rate','clip_param','gamma','gae_lambda','rollout_steps','mini_batches','learning_epochs','num_envs'},'PPO candidate schema')
    require(candidate['status']=='CANDIDATE_NOT_NATIVE_VALIDATED' and candidate['algorithm']=='PPO' and candidate['suggested_library']=='rsl_rl','Candidate scope')
    for key in ('actor_hidden_dims','critic_hidden_dims'):
        require(type(candidate[key]) is list and candidate[key] and all(type(x) is int and x>0 for x in candidate[key]),'Positive candidate layer widths')
    for key in ('learning_rate','clip_param','gamma','gae_lambda'):require(0<number(candidate[key])<1,'Candidate fraction: '+key)
    for key in ('rollout_steps','mini_batches','learning_epochs','num_envs'):require(type(candidate[key]) is int and candidate[key]>0,'Candidate integer: '+key)
    require(candidate['num_envs']==1 and candidate['rollout_steps']%candidate['mini_batches']==0,'Single-env divisible candidate rollout')
    return cfg


def build(root=ROOT):
    root=Path(root);cfg=configuration(root)
    require(len(cfg['input_pins'])==4,'Complete pinned source inventory')
    for path,expected in cfg['input_pins'].items():
        p=(root/path).resolve();require(p.is_relative_to(root.resolve()) and sha(p)==expected,'Approved preparation input changed: '+path)
    d=read(root/'outputs/isaac-contact-v1/delivery.json')
    run=root/'outputs/isaac-contact-v1/runs'/d['run_id']/'retrieved'/d['run_id']
    require(sha(run/'validation.json')==d['validation_sha256'],'Actual baseline validation binding')
    result=read(run/'validation.json');assumptions=read(root/'models/robot-arm-urdf-v1/assumptions.json')
    require(result['evidence_valid'] is True and result['hardware_approved'] is False,'Valid simulation-only baseline evidence')
    for path,h in d['source_sha256'].items():require(sha(root/path)==h,'Original controller source drift: '+path)
    require(assumptions['physical_verified'] is False and assumptions['status']=='SIMULATION_ASSUMPTION','Keep physical assumptions')
    control={path:h for path,h in d['source_sha256'].items() if path.endswith(('runtime.py','environment.py','core.py'))}
    error=number(d['max_endpoint_error_deg']);speed=number(d['max_endpoint_speed_deg_s'])
    require(0<=error<=cfg['limits']['command_deg'] and 0<=speed and math.radians(math.ceil(speed))<=assumptions['velocity_rad_s'],'Reset distribution must fit declared envelope')
    accepted=(d['motion_accepted'] is True and d['motion_acceptance']=='GRAVITY_COLLISION_MOTION_PASS' and
              result['status']=='GRAVITY_COLLISION_MOTION_PASS' and error<=.5 and speed<=1 and d['checkpoints_passed']==28)
    env_path=root/'outputs/rl-prep-v1/evidence/environment.json'
    env=read(env_path) if env_path.is_file() else {'status':'NOT_VERIFIED','modules':{}}
    p={'schema_version':1,'status':'PREPARATION_ONLY','joint_names':JOINTS,'coordinate':'CAD_DISPLAY_DELTA_RAD',
       'display_geometric_offsets_deg':[15,-50,70,15,25,-10],'asset_sha256':ASSET_SHA,
       'mass_inertia':'SIMULATION_ASSUMPTION','assumptions':assumptions,'total_effort_cap_Nm':assumptions['effort_Nm'],
       'original_velocity_limit_rad_s':assumptions['velocity_rad_s'],'config':cfg,
       'config_sha256':sha(root/'src/simulation/rl_prep/task_config.json'),'source_pins':cfg['input_pins'],
       'control_signature':digest({'sources':control,'asset':ASSET_SHA,'gravity':[0,0,-9.81],'collision':True}),
       'baseline':{'run_id':d['run_id'],'status':d['motion_acceptance'],'accepted':accepted,'max_error_deg':error,
           'max_speed_deg_s':speed,'checkpoints_passed':d['checkpoints_passed'],'validation_sha256':d['validation_sha256']},
       'reset_distribution':{'q_span_deg':math.ceil(error),'qd_span_deg_s':math.ceil(speed),
           'basis':'OBSERVED_FAILURE_MARGIN_ROUNDED_UP_ASSUMPTION_NOT_PHYSICAL_DISTRIBUTION'},
       'environment':env,'environment_sha256':sha(env_path) if env_path.is_file() else None,
       'hardware_approved':False,'calibration_approved':False,'ring_geometry':'DEFERRED','training':'NOT_RUN','weights':None}
    p['profile_hash']=digest(p)
    return p


def validate(p,root=ROOT):
    require(type(p) is dict and p==build(root),'Profile/config/source mismatch; edited ready flags cannot override baseline')
    return p


def readiness(p,root=ROOT,backend=None):
    validate(p,root);reasons=[]
    if not p['baseline']['accepted']:reasons.append('BASELINE_DYNAMICS_FAILED')
    modules=p['environment'].get('modules',{})
    for name in ('isaaclab','gymnasium','torch','rsl_rl'):
        if modules.get(name) is not True:reasons.append('MODULE_NOT_VERIFIED:'+name)
    if backend is None or getattr(backend,'kind',None)!='ISAAC_SIM':reasons.append('NATIVE_SIM_BACKEND_NOT_VERIFIED')
    elif getattr(backend,'control_signature',None)!=p['control_signature'] or getattr(backend,'native_verified',False) is not True:
        reasons.append('NATIVE_CONTROL_SIGNATURE_OR_EVIDENCE_MISMATCH')
    return {'status':'BLOCKED' if reasons else 'READY_FOR_SIMULATION_TRAINING','ready':not reasons,'reasons':reasons,
            'training_executed':False,'hardware_approved':False}
