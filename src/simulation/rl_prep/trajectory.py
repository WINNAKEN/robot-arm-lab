"""Analytically bounded rest-to-rest quintic references, simulation preparation only."""
import math
try:from .profile import number,vector,require
except ImportError:from profile import number,vector,require


def segment(q0,q1,limits,hz=120,minimum_s=1.5,hold_s=.5):
    q0,q1=vector(q0),vector(q1);require(type(hz) is int and hz==120,'120 Hz reference')
    v,a,j=[number(limits[k]) for k in ('velocity_rad_s','acceleration_rad_s2','jerk_rad_s3')]
    require(min(v,a,j)>0 and number(minimum_s)>0 and number(hold_s)>=0,'Positive time/derivative bounds')
    bound=math.radians(number(limits['command_deg']))
    require(all(abs(x)<=bound+1e-12 for x in q0+q1),'Reference outside simulation command range')
    delta=[b-a for a,b in zip(q0,q1)]
    needed=max([minimum_s]+[t for d in delta for t in (1.875*abs(d)/v,math.sqrt((10/math.sqrt(3))*abs(d)/a),(60*abs(d)/j)**(1/3))])
    ticks=max(1,math.ceil(needed*hz-1e-10));hold=round(hold_s*hz)
    require(abs(hold/hz-hold_s)<1e-9,'Hold must be a whole number of physics ticks')
    duration=ticks/hz;rows=[]
    for k in range(ticks+hold+1):
        u=min(1.,k/ticks)
        h=10*u**3-15*u**4+6*u**5
        d1=30*u*u*(1-u)*(1-u)/duration
        d2=(60*u-180*u*u+120*u**3)/duration**2
        d3=(60-360*u+360*u*u)/duration**3 if k<=ticks else 0.
        rows.append({'t_s':k/hz,'q':[x+h*d for x,d in zip(q0,delta)],
            'qd':[d1*d for d in delta],'qdd':[d2*d for d in delta],'jerk':[d3*d for d in delta]})
    require(max(abs(x) for r in rows for x in r['qd'])<=v+1e-10 and
            max(abs(x) for r in rows for x in r['qdd'])<=a+1e-10 and
            max(abs(x) for r in rows for x in r['jerk'])<=j+1e-10,'Reference derivative bounds')
    return rows


def action_reference(q,action,cfg):
    q,raw=vector(q),vector(action);clipped=[max(-1.,min(1.,x)) for x in raw]
    cap=math.radians(cfg['limits']['command_deg']);step=math.radians(cfg['limits']['increment_deg'])
    target=[max(-cap,min(cap,x+u*step)) for x,u in zip(q,clipped)]
    rows=segment(q,target,cfg['limits'],cfg['physics_hz'],cfg['move_s'],cfg['hold_s'])
    require(len(rows)==241,'Fixed 240-physics-tick decision')
    return target,clipped,rows
