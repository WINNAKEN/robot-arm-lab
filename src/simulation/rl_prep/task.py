"""Library-independent joint-reaching MDP; native execution is baseline-gated."""
from dataclasses import dataclass
import math
import random
try:
    from .profile import ROOT,validate,readiness,require,vector,number
    from .trajectory import action_reference
except ImportError:
    from profile import ROOT,validate,readiness,require,vector,number
    from trajectory import action_reference


@dataclass(frozen=True)
class State:
    q: tuple
    qd: tuple
    t_s: float
    physics_step: int
    unexpected_contact: bool=False

    def __post_init__(self):
        object.__setattr__(self,'q',tuple(vector(self.q)))
        object.__setattr__(self,'qd',tuple(vector(self.qd)))
        number(self.t_s)
        require(type(self.physics_step) is int and self.physics_step>=0 and type(self.unexpected_contact) is bool,'State clock/contact type')


class MockBackend:
    """Ideal reference following for HOST contract tests; no physics or learning."""
    kind='HOST_MOCK'
    native_verified=False
    def reset(self,q,qd):
        self.state=State(tuple(q),tuple(qd),0.,0)
        return self.state
    def execute_reference(self,reference):
        initial=self.state
        rows=[initial]+[State(tuple(r['q']),tuple(r['qd']),initial.t_s+r['t_s'],initial.physics_step+i)
                        for i,r in enumerate(reference[1:],1)]
        self.state=rows[-1]
        return rows


class JointReachTask:
    """Backend port: reset(q,qd)->State; execute_reference(rows)->241 actual States.

    No backend is created implicitly. Hardware/network/Isaac SDK calls do not
    occur in this module. A native adapter is a separate unverified dependency.
    """
    def __init__(self,profile,backend,root=ROOT):
        self.profile=validate(profile,root);self.cfg=profile['config'];self.backend=backend
        require(getattr(backend,'kind',None) in ('HOST_MOCK','ISAAC_SIM'),'Explicit simulation backend required')
        if backend.kind=='ISAAC_SIM':
            check=readiness(profile,root,backend)
            require(check['ready'],'Native execution blocked: '+','.join(check['reasons']))
        self.needs_reset=True

    def reset(self,seed=0,goal=None,randomize=True):
        self.needs_reset=True
        require(type(seed) is int and seed>=0 and type(randomize) is bool,'Seed/reset mode')
        rng=random.Random(seed);p=self.profile
        span=math.radians(p['reset_distribution']['q_span_deg']) if randomize else 0.
        speed=math.radians(p['reset_distribution']['qd_span_deg_s']) if randomize else 0.
        q=[rng.uniform(-span,span) for _ in range(6)];qd=[rng.uniform(-speed,speed) for _ in range(6)]
        limit=math.radians(self.cfg['limits']['goal_deg'])
        self.goal=vector(goal) if goal is not None else [rng.uniform(-limit,limit) for _ in range(6)]
        require(all(abs(x)<=limit+1e-12 for x in self.goal),'Goal outside declared curriculum')
        state=self.backend.reset(q,qd);require(type(state) is State,'Backend must provide immutable State')
        bound=math.radians(self.cfg['limits']['command_deg'])
        require(all(abs(x)<=bound for x in state.q),'Reset outside command envelope')
        self.state=state;self.command=list(state.q);self.previous_action=[0.]*6;self.last_acc=[0.]*6;self.decisions=0
        self.needs_reset=False
        observation,clipped=self.observation()
        return observation,self.info({'reset_seed':seed,'observation_clipped':clipped})

    def info(self,extra):
        return {'backend':self.backend.kind,'scope':'HOST_KINEMATIC_CONTRACT_TEST' if self.backend.kind=='HOST_MOCK' else 'NATIVE_SIMULATION',
                'profile_hash':self.profile['profile_hash'],'training_executed':False,'hardware_approved':False,**extra}

    def observation(self):
        cfg=self.cfg;cap=math.radians(cfg['limits']['command_deg']);goal_scale=2*cap
        values=([q/cap for q in self.state.q]+[v/self.profile['original_velocity_limit_rad_s'] for v in self.state.qd]+
                [a/cfg['limits']['acceleration_rad_s2'] for a in self.last_acc]+
                [(g-q)/goal_scale for g,q in zip(self.goal,self.state.q)]+[q/cap for q in self.command]+
                self.previous_action+[0.,0.,-1.]+[self.decisions/cfg['max_decisions'],float(self.state.unexpected_contact)])
        require(len(values)==41 and all(math.isfinite(v) for v in values),'41 finite actor observations')
        clipped=[max(-5.,min(5.,v)) for v in values]
        return clipped,clipped!=values

    def step(self,action):
        require(not self.needs_reset,'Reset required before another decision')
        try:
            target,clipped,reference=action_reference(self.command,action,self.cfg)
            trace=self.backend.execute_reference(reference)
            require(type(trace) in (list,tuple) and len(trace)==241 and all(type(x) is State for x in trace),'241 immutable actual states required')
            require(trace[0]==self.state,'Backend trace must start at the last actual observation')
            dt=1/self.cfg['physics_hz'];start=trace[0]
            for i,state in enumerate(trace):
                require(state.physics_step==start.physics_step+i and abs(state.t_s-start.t_s-i*dt)<=1e-6,'Actual physics clock/step continuity')
            metrics,terms,success,faults=self.evaluate(trace,clipped)
            self.state=trace[-1];self.command=target;self.previous_action=clipped;self.decisions+=1
            terminated=success or bool(faults)
            truncated=self.decisions>=self.cfg['max_decisions'] and not terminated
            self.needs_reset=terminated or truncated
            observation,was_clipped=self.observation()
            reward=sum(terms.values());require(math.isfinite(reward),'Finite unclipped reward')
            return observation,reward,terminated,truncated,self.info({'success':success,'faults':sorted(faults),
                'reward_terms':terms,'raw_metrics':metrics,'observation_clipped':was_clipped,
                'command_reference_only':True,'reference_duration_s':reference[-1]['t_s']})
        except Exception:
            self.needs_reset=True
            raise

    def evaluate(self,trace,action):
        cfg=self.cfg;w=cfg['reward'];dt=1/cfg['physics_hz'];n=len(trace)-1;duration=n*dt
        scale=2*math.radians(cfg['limits']['command_deg'])
        position=lambda state:sum(((g-q)/scale)**2 for g,q in zip(self.goal,state.q))/6
        costs={'position':0.,'velocity':0.,'acceleration':0.,'jerk':0.};faults=set();previous_acc=self.last_acc[:]
        for prev,state in zip(trace,trace[1:]):
            acc=[(v-u)/dt for v,u in zip(state.qd,prev.qd)]
            jerk=[(a-b)/dt for a,b in zip(acc,previous_acc)];previous_acc=acc
            costs['position']+=position(state)*dt
            for key,values,normalizer in (
                ('velocity',state.qd,self.profile['original_velocity_limit_rad_s']),
                ('acceleration',acc,cfg['limits']['acceleration_rad_s2']),('jerk',jerk,cfg['limits']['jerk_rad_s3'])):
                costs[key]+=sum((v/normalizer)**2 for v in values)/6*dt
        self.last_acc=previous_acc
        for state in trace:
            if state.unexpected_contact:faults.add('UNEXPECTED_CONTACT')
            if max(abs(x) for x in state.q)>math.radians(cfg['limits']['actual_abort_deg']):faults.add('ACTUAL_JOINT_RANGE')
            if max(abs(x) for x in state.qd)>self.profile['original_velocity_limit_rad_s']:faults.add('ACTUAL_SPEED_BOUND')
        hold_ticks=round(.5*cfg['physics_hz']);window=trace[-(hold_ticks+1):]
        success=(not faults and len(window)==61 and window[-1].t_s-window[0].t_s>=.5-1e-8 and
            all(max(abs(q-g) for q,g in zip(s.q,self.goal))<=math.radians(.5)+1e-12 and
                max(map(abs,s.qd))<=math.radians(1)+1e-12 for s in window))
        terms={key:-w[key]*cost for key,cost in costs.items()}
        terms.update(progress=w['progress']*(position(trace[0])-position(trace[-1])),
            action_change=-w['action_change']*sum((a-b)**2 for a,b in zip(action,self.previous_action))/6,
            time=-w['time']*duration,goal_bonus=w['goal_bonus'] if success else 0.,fault_penalty=-w['fault_penalty'] if faults else 0.)
        return {'final_goal_error_rad':max(abs(q-g) for q,g in zip(trace[-1].q,self.goal)),
            'actual_jerk_cost_unclipped':costs['jerk'],'settle_window_intervals':hold_ticks},terms,success,faults
