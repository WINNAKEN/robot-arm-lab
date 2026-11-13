"""Native force observations; no physics control and no SDK imports."""
import math,struct
SEMANTICS={'command':'EXTERNAL_COMMAND_NOT_MEASURED_DRIVE','projected':'NET_ACTIVE_JOINT_EFFORT_NOT_ISOLATED_PD','incoming':'CHILD_JOINT_FRAME_6D'}
def need(ok,message):
    if not ok:raise RuntimeError(message)
def finite(value):
    need(type(value) in (float,int) and math.isfinite(value),'Finite non-bool force');return float(value)
def make_binding(static,model,names,links):
    need(len(names)==len(set(names))==9 and set(names)==set(model['movable']),'Unique complete force DOFs')
    need(len(links)==len(set(links))==11 and set(links)=={n for n,x in model['links'].items() if x['mass'] is not None},'Unique complete incoming links')
    joints={j['name']:j for j in static['joints']};mapping={}
    for n in model['movable']:
        j=joints[n];child=model['joints'][n]['child'];kind=model['joints'][n]['type']
        need(j['axis'] in ('X','Y','Z') and j['body1'].split('/')[-1]==child,'Native child joint frame axis')
        mapping[n]={'dof_index':names.index(n),'link_index':links.index(child),'axis':j['axis'],'child':child,'kind':kind,'unit':'N' if kind=='prismatic' else 'N*m'}
    return {'dof_names':list(names),'link_names':list(links),'mapping':mapping}
def unavailable(clock):return {'available':False,'sample_step':0,'reason':'NO_COMPLETED_POSITIVE_STEP','clock':clock}
def validate_sample(obs,binding,ff):
    need(type(obs['sample_step']) is int and obs['available'] is (obs['sample_step']>0),'Exact force availability/index')
    need(obs['semantics']==SEMANTICS,'No force semantic promotion')
    need(obs['clock_before']==obs['clock_after'],'Clock changed during force query')
    raw=obs['raw'];need(set(raw)=={'command','projected','force','torque'},'Closed force channels')
    for key in ('command','projected'):
        need(len(raw[key])==1 and len(raw[key][0])==9,'Force shape1x9')
        for x in raw[key][0]:finite(x)
    for key in ('force','torque'):
        need(len(raw[key])==1 and len(raw[key][0])==11 and all(len(x)==3 for x in raw[key][0]),'Incoming shape1x11x3')
        for row in raw[key][0]:
            for x in row:finite(x)
    if not obs['available']:return
    for n,m in binding['mapping'].items():
        di=m['dof_index'];li=m['link_index'];axis=('X','Y','Z').index(m['axis']);key='force' if m['kind']=='prismatic' else 'torque'
        a=raw['projected'][0][di];b=raw[key][0][li][axis]
        need(abs(a-b)<=1e-3+1e-4*max(abs(a),abs(b)),'Projected/incoming force coherence')
        expected=struct.unpack('<f',struct.pack('<f',ff[n]))[0]
        need(abs(raw['command'][0][di]-expected)<=1e-8,'External effort readback must match command')
def observe(robot,backend,array,clock,binding,step,ff):
    need(type(step) is int and step>=0,'Nonnegative force step')
    before=clock()
    with backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
        force,moment=robot.get_link_incoming_joint_force()
        raw={'command':array(robot.get_dof_efforts()).tolist(),'projected':array(robot.get_dof_projected_joint_forces()).tolist(),'force':array(force).tolist(),'torque':array(moment).tolist()}
    after=clock();obs={'available':step>0,'sample_step':step,'clock_before':before,'clock_after':after,'raw':raw,'semantics':dict(SEMANTICS)}
    validate_sample(obs,binding,ff);return obs

def braking_summary(report):
    """Net effort diagnostics; cannot identify isolated PD or prove saturation."""
    rows=report['observations'];segments=report['program']['segments'];dt=report['program']['dt_s'];elapsed=0.;previous=None;windows=[]
    for segment in segments:
        end=elapsed+segment['duration_s']
        if segment['kind']=='hold' and previous is not None and previous['kind']=='move':
            begin=int(round(elapsed/dt));finish=int(round(end/dt));brake=int(round((elapsed-previous['duration_s']/2)/dt))
            window={'phase':segment['name'],'hold_start_s':elapsed,'hold_end_s':end,'deceleration_start_s':brake*dt,'joints':{}}
            if finish>=len(rows):window['status']='CENSORED_MISSING_ENDPOINT';windows.append(window);elapsed=end;previous=segment;continue
            window['status']='OBSERVED_ORIGINAL_WINDOW'
            for n in ('J1','J2','J3','J4','J5','J6'):
                suffix=finish+1
                for i in range(finish,begin-1,-1):
                    row=rows[i]
                    if abs(row['q'][n]-row['targets'][n])>math.radians(.5) or abs(row['qd'][n])>math.radians(1):break
                    suffix=i
                settled=suffix<=finish;power=[];ratios=[];acc=[];nonzero=0
                di=report['torque_binding']['dof_names'].index(n)
                for i in range(max(1,brake),finish+1):
                    row=rows[i];effort=row['torque_observation']['raw']['projected'][0][di];speed=row['qd'][n]
                    power.append(effort*speed);nonzero+=int(abs(effort)>1e-8);cap=row['effort_remaining'][n]
                    if cap>0:ratios.append(abs(effort)/cap)
                    acc.append(abs((speed-rows[i-1]['qd'][n])/dt))
                work=sum((a+b)*.5*dt for a,b in zip(power,power[1:]))
                window['joints'][n]={'settling':'SETTLED_SUFFIX' if settled else 'CENSORED_NOT_SETTLED','time_to_settle_s':rows[suffix]['time_s']-elapsed if settled else None,'endpoint_error_deg':math.degrees(abs(rows[finish]['q'][n]-rows[finish]['targets'][n])),'endpoint_speed_deg_s':math.degrees(abs(rows[finish]['qd'][n])),'max_abs_acceleration_rad_s2':max(acc),'signed_net_joint_work_J':work,'opposing_net_power_samples':sum(x<0 for x in power),'nonzero_projected_samples':nonzero,'samples':len(power),'max_net_over_drive_cap_ratio_NOT_SATURATION_PROOF':max(ratios) if ratios else None}
            windows.append(window)
        elapsed=end;previous=segment
    return {'status':'NET_JOINT_EFFORT_AND_BRAKING_OBSERVED','windows':windows,'isolated_PD_drive_torque':'NOT_AVAILABLE','drive_saturation':'NOT_DETERMINABLE_FROM_NET_PROJECTION','unique_failure_cause':'INCONCLUSIVE_REQUIRES_DECOMPOSITION_OR_CONTROLLED_COUNTERFACTUAL','semantics':'Internal projection coherence is not independent force calibration; work is net active joint work, not motor-only work.'}
