"""Prepared task/space contract and optional Gym wrapper; native Lab registration NOT_RUN."""
try:from .profile import ROOT,validate,readiness,require
except ImportError:from profile import ROOT,validate,readiness,require


def specification(profile,root=ROOT):
    validate(profile,root);cfg=profile['config']
    return {'status':'INTERFACE_PREPARED_NATIVE_NOT_RUN','task_id':'RobotArmLab-JointReach-Smooth-v0',
        'native_registration':'NOT_RUN','target_framework':'Isaac Lab release/3.0.0 candidate; RC pairing unverified',
        'physics_backend':'isaacsim_physx','physics_dt_s':1/cfg['physics_hz'],'decimation':240,'decision_dt_s':2.,
        'episode_decisions':16,'episode_duration_s':32.,'num_envs':1,
        'observation_dim':41,'observation_fields':[['q_delta_rad',6],['qd_rad_s',6],['estimated_qdd_rad_s2',6],
            ['goal_error_rad',6],['q_reference_rad',6],['previous_action',6],['world_gravity_direction',3],['episode_progress',1],['unexpected_contact',1]],
        'action_dim':6,'action_semantics':'bounded joint delta per 2-second rest-to-rest primitive',
        'coordinate':profile['coordinate'],'asset_sha256':profile['asset_sha256'],'profile_hash':profile['profile_hash'],
        'native_backend_port':{'kind':'ISAAC_SIM','reset':'reset(q,qd)->actual State',
            'execute_reference':'241 same-clock actual State records, NOT target echo','control_signature':profile['control_signature'],
            'verification':'actual baseline and native bridge evidence required before calls'},
        'ppo_candidate':cfg['ppo_candidate'],'hardware_approved':False,'training_executed':False}


def as_gym_environment(task,profile,root=ROOT,training=False):
    """No native driver is hidden here. Caller must provide the verified backend port."""
    validate(profile,root);require(task.profile==profile,'Task profile mismatch')
    require(type(training) is bool,'Training mode must be explicit')
    if training:
        check=readiness(profile,root,task.backend)
        require(check['ready'],'Training blocked: '+','.join(check['reasons']))
    import gymnasium as gym
    import numpy as np
    class PreparedGymEnvironment(gym.Env):
        metadata={'render_modes':[]}
        observation_space=gym.spaces.Box(-5.,5.,shape=(41,),dtype=np.float32)
        action_space=gym.spaces.Box(-1.,1.,shape=(6,),dtype=np.float32)
        def reset(self,*,seed=None,options=None):
            super().reset(seed=seed)
            options={} if options is None else options
            require(type(options) is dict and set(options)<={'goal','randomize'},'Reset options')
            obs,info=task.reset(seed=0 if seed is None else seed,**options)
            return np.asarray(obs,dtype=np.float32),info
        def step(self,action):
            obs,reward,terminated,truncated,info=task.step(np.asarray(action,dtype=float).tolist())
            return np.asarray(obs,dtype=np.float32),reward,terminated,truncated,info
    return PreparedGymEnvironment()
