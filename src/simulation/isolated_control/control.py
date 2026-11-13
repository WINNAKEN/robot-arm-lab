"""Single engine-model computed-torque candidate; no hardware I/O."""
import math
import numpy as np
CAP=[3.,6.,5.,2.,2.,1.]


def acceleration(motion,program,t):
    lo=max(0.,t-1/120);hi=min(motion.total_time(program),t+1/120)
    return ((np.asarray(motion.sample(program,hi)['qd_rad_s'])-np.asarray(motion.sample(program,lo)['qd_rad_s']))/(hi-lo)).tolist()


def command(q,qd,reference,qdd,M,g,c):
    def numeric(value):
        if isinstance(value,(list,tuple)):
            for x in value:numeric(x)
        elif type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite numeric control input, no bool/string')
    for value in (q,qd,reference['q_rad'],reference['qd_rad_s'],qdd,M,g,c):numeric(value)
    arrays=[np.asarray(x,dtype=float) for x in (q,qd,reference['q_rad'],reference['qd_rad_s'],qdd,M,g,c)]
    if any(not np.isfinite(x).all() for x in arrays):raise ValueError('Finite actual engine/control values required')
    q,v,goal,vel,a,M,g,c=arrays
    if any(x.shape!=(6,) for x in (q,v,goal,vel,a,g,c)) or M.shape!=(6,6):raise ValueError('Canonical fixed-base six-DOF dynamics shape')
    if np.max(np.abs(M-M.T))>1e-6 or np.linalg.eigvalsh((M+M.T)/2).min()<=1e-8:raise ValueError('Finite symmetric positive-definite mass matrix')
    raw=g+c+M@(a+64*(goal-q)+16*(vel-v));tau=np.clip(raw,-np.asarray(CAP),np.asarray(CAP))
    return {'tau':tau.tolist(),'raw_tau':raw.tolist(),'saturated':(np.abs(raw)>np.asarray(CAP)).tolist()}


def gains(_):return {'kp':[0.]*6,'kd':[0.]*6,'effort':CAP[:]}
