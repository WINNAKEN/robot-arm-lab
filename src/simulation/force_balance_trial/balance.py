"""Native raw dynamics collection and independent force/moment verification."""
import math,json

def json_safe(value):
    if isinstance(value,float) and not math.isfinite(value):return {'NONFINITE_RAW':repr(value)}
    if isinstance(value,dict):return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [json_safe(v) for v in value]
    return value

def need(ok,why):
    if not ok:raise ValueError(why)
def make_module_oracle(o):return o
def fixture_spec(mode):
    return {'axis':[0.,1.,0.] if mode=='acceleration' else [0.,0.,1.],'axis_token':'Y' if mode=='acceleration' else 'Z','com':[.4,0.,0.] if mode=='acceleration' else [0.,0.,0.],'Icom':.05 if mode=='acceleration' else .2,'basis':[math.cos(math.pi/8),0.,0.,math.sin(math.pi/8)] if mode=='acceleration' else [1.,0.,0.,0.],'pivot':[6.,0.,2.] if mode=='acceleration' else [5.,0.,2.]}
def expected_wrench(mode,q0,v0,q1,v1,o):
    spec=fixture_spec(mode);R0=o['quat'](spec['basis']);Ra=o['mm'](R0,o['axis_rot'](spec['axis'],q1));Rb=o['mm'](R0,o['axis_rot'](spec['axis'],q0));axis=o['mv'](R0,spec['axis']);ra=o['mv'](Ra,spec['com']);rb=o['mv'](Rb,spec['com']);va=o['cross']([x*v1 for x in axis],ra);vb=o['cross']([x*v0 for x in axis],rb);fw=[(a-b)*120 for a,b in zip(va,vb)];ie=spec['Icom']+sum(x*x for x in spec['com']);tau=ie*(v1-v0)*120;tw=[x*tau for x in axis]
    return {'rotation':Ra,'force_child':o['mv'](o['tr'](Ra),fw),'torque_child':o['mv'](o['tr'](Ra),tw),'force_world':fw,'torque_world':tw,'total_Nm':tau}
def verify_fixture(report,o):
    try:return _fixture(report,o)
    except (ValueError,KeyError,TypeError,IndexError) as exc:return {'status':'REFERENCE_RECORD_INVALID','faults':[{'error':str(exc)}],'summary':{},'robot_PD':'NOT_DIRECTLY_MEASURED','combined_PD':'UNKNOWN'}
def _fixture(report,o):
    num=o['num'];vec=o['vec'];packet=report['reference']
    if packet.get('errors'):return {'status':'REFERENCE_OBSERVATION_FAILED','faults':packet['errors'],'summary':{},'robot_PD':'NOT_DIRECTLY_MEASURED','combined_PD':'UNKNOWN'}
    metas={x['mode']:x for x in packet['setup']};need(len(packet['setup'])==2 and set(metas)=={'force','acceleration'},'Exactly two declared references');need(len(packet['samples'])==240,'Complete240 reference steps')
    phases=('external_only','force_PD_only','combined_residual','acceleration_PD_only','free');summary={m:{p:[] for p in phases} for m in metas};faults=[];prior={};max_error=0.
    for mode,m in metas.items():
        s=fixture_spec(mode);need(m['same_owned_lab_view'] is True and m['body_count']==2 and m['collision_shapes']==0 and len(m['dof_names'])==1,'Bound independent reference inventory')
        need(len(m['link_names'])==2 and set(m['link_names'])=={'Base','Rotor'},'Reference link identity');ri=m['link_names'].index('Rotor');bi=m['link_names'].index('Base');need(m['axis']==s['axis_token'] and max(abs(a-b) for a,b in zip(vec(m['basis_wxyz'],4),s['basis']))<1e-6 and m['pivot']==s['pivot'],'Declared axis, basis and pivot')
        need(m['gravity_enabled']==[[False,False]] and all(type(x) is bool for x in m['gravity_enabled'][0]),'Only reference gravity disabled')
        need(m['tensor_drive_type']==[[2 if mode=='acceleration' else 1]],'Native drive mode')
        need(len(m['masses'])==len(m['inertias'])==len(m['coms'])==1 and len(m['masses'][0])==len(m['inertias'][0])==len(m['coms'][0])==2,'Raw native reference shapes')
        for index in (ri,bi):
            need(abs(num(m['masses'][0][index])-1)<1e-6,'Known mass');tensor=vec(m['inertias'][0][index],9);need(all(abs(x-(s['Icom'] if i in (0,4,8) else 0.))<1e-6 for i,x in enumerate(tensor)),'Known isotropic inertia')
        need(max(abs(a-b) for a,b in zip(vec(m['coms'][0][ri]),s['com']))<1e-6 and max(abs(x) for x in vec(m['coms'][0][bi]))<1e-6,'Native offset COM')
        com=m['coms'][0][ri];ie=m['inertias'][0][ri][(1 if mode=='acceleration' else 2)*4]+sum(x*x for x in com)-sum(a*b for a,b in zip(com,s['axis']))**2
        need(abs(num(m['effective_inertia'])-ie)<1e-12 and abs(ie-(.21 if mode=='acceleration' else .2))<1e-6,'Parallel-axis native inertia')
        need(len(m['friction'])==3 and all(num(v)==0 for matrix in m['friction'] for row in matrix for v in row) and m['armature']==[[0.]],'Zero reference friction/armature')
        need(abs(num(m['initial_q']))<1e-6 and abs(num(m['initial_qd']))<1e-6 and m['velocity_limit']==10.,'Initial unmoved reference')
        need(len(m['initial_transforms'])==1 and len(m['initial_transforms'][0])==2,'Initial native pose shape')
        for raw in m['initial_transforms'][0]:
            t=vec(raw,7);R=o['quat']([t[6],*t[3:6]]);R0=o['quat'](s['basis']);need(max(abs(a-b) for a,b in zip(t[:3],s['pivot']))<5e-5 and max(abs(R[i][j]-R0[i][j]) for i in range(3) for j in range(3))<5e-5,'Initial native child joint pose')
        prior[mode]=(m['initial_q'],m['initial_qd'])
    for step,sample in enumerate(packet['samples'],1):
        before=sample['clock_before_step'];after=sample['clock_after_step'];need(after==sample['clock_after_read'] and before==report['observations'][step-1]['clock_after'] and after==report['observations'][step]['clock_after'] and after['lab_step']==before['lab_step']+1 and abs(after['engine_time_s']-before['engine_time_s']-1/120)<1e-10,'Exact reference/robot step clocks')
        need(len(sample['rows'])==len(sample['issued'])==2 and {x['mode'] for x in sample['rows']}==set(metas),'Two distinct reference rows');phase=phases[(step-1)//48]
        for row in sample['rows']:
            mode=row['mode'];m=metas[mode];s=fixture_spec(mode);need(row['step']==step and (num(row['before_q']),num(row['before_qd']))==prior[mode],'Reference endpoint continuity')
            need(sum(x=={k:row[k] for k in ('mode','step','command','before_q','before_qd')} for x in sample['issued'])==1,'Same issued command')
            active=(mode=='force' and phase in phases[1:3]) or (mode=='acceleration' and phase==phases[3]);external=.02 if phase==phases[0] or (mode=='force' and phase==phases[2]) else 0.
            command={'phase':phase,'kp':64. if active else 0.,'kd':16. if active else 0.,'target':.2,'external':external,'cap':.01};need(row['command']==command,'Independent command/phase reconstruction')
            need(row['kp_readback']==command['kp'] and row['kd_readback']==command['kd'] and abs(num(row['cap_readback'])-.01)<1e-8 and abs(num(row['external_readback'])-external)<1e-8,'Actual reference readbacks')
            q=num(row['after_q']);qd=num(row['after_qd']);need(abs(q)<10 and abs(qd)<9,'Reference limit inactive');prior[mode]=(q,qd)
            predicted=expected_wrench(mode,row['before_q'],row['before_qd'],q,qd,o);need(len(row['after_transforms'])==1 and len(row['after_transforms'][0])==2,'Native reference pose shape')
            for index,name in enumerate(m['link_names']):
                t=vec(row['after_transforms'][0][index],7);R=o['quat']([t[6],*t[3:6]]);expected_R=predicted['rotation'] if name=='Rotor' else o['quat'](s['basis']);need(max(abs(a-b) for a,b in zip(t[:3],s['pivot']))<5e-5 and max(abs(R[i][j]-expected_R[i][j]) for i in range(3) for j in range(3))<5e-5,'Actual child-joint pose bound to q/axis')
            need(len(row['incoming_force'])==len(row['incoming_torque'])==1 and len(row['incoming_force'][0])==len(row['incoming_torque'][0])==2,'Full native6D shapes');ri=m['link_names'].index('Rotor')
            for f,t in zip(row['incoming_force'][0],row['incoming_torque'][0]):vec(f);vec(t)
            measured=vec(row['incoming_force'][0][ri])+vec(row['incoming_torque'][0][ri]);expected=predicted['force_child']+predicted['torque_child']
            if any(abs(a-b)>1e-4+.01*max(abs(a),abs(b)) for a,b in zip(measured,expected)):faults.append({'step':step,'mode':mode,'kind':'FULL6D_DECLARED_CHILD_JOINT_PIVOT_MISMATCH','expected':expected,'actual':measured})
            max_error=max(max_error,max(abs(a-b) for a,b in zip(measured,expected)));tau=m['effective_inertia']*(qd-row['before_qd'])*120;projection=num(row['projected']);ai=1 if mode=='acceleration' else 2
            need(abs(projection-measured[3+ai])<=1e-3+1e-4*abs(projection),'Incoming active-axis coherence')
            if abs(tau-projection)>1e-4+.01*max(abs(tau),abs(projection)):faults.append({'step':step,'mode':mode,'kind':'SCALAR_INERTIAL_PROJECTION_MISMATCH'})
            if not active and abs(tau-external)>1e-4+.01*abs(external):faults.append({'step':step,'mode':mode,'kind':'EXTERNAL_OR_COAST_MISMATCH'})
            if active and external==0 and abs(tau)>.0102:faults.append({'step':step,'mode':mode,'kind':'PD_ONLY_CAP_MISMATCH'})
            if mode=='force' and phase==phases[2] and abs(tau-.03)>.0004:faults.append({'step':step,'mode':mode,'kind':'COMBINED_ADDITIVITY_UNCONFIRMED'})
            summary[mode][phase].append({'step':step,'total_inertial_Nm':tau,'PD_only_Nm':tau if active and external==0 else None,'conditional_residual_Nm':tau-external,'projected_Nm':projection,'reference_PD_only_near_cap':active and external==0 and abs(abs(tau)-.01)<=.0002})
    for mode,p in (('force',phases[1]),('acceleration',phases[3])):
        if not any(abs(x['PD_only_Nm'])>1e-4 for x in summary[mode][p]):faults.append({'mode':mode,'kind':'PD_ONLY_SIGNAL_MISSING'})
    return {'status':'NONZERO_COM_FULL6D_VERIFIED' if not faults else 'NONZERO_COM_FULL6D_UNRESOLVED','faults':faults,'summary':summary,'max_full6D_component_error':max_error,'robot_PD':'NOT_DIRECTLY_MEASURED','combined_PD':'UNKNOWN','scope':'Declared child-joint-frame pivot full6D contract; no fitted alternative'}

class Dynamics:
    def __init__(self,ctx,robot,backend,array,clock,names,stage,bodies):
        self.ctx=ctx;self.robot=robot;self.backend=backend;self.array=array;self.clock=clock;self.names=list(names);self.packet={'samples':[],'errors':[],'damping_config':[]};self.stream=None
        try:self.stream=(ctx.run/'output/dynamics.ndjson').open('x',encoding='utf-8',newline='\n')
        except Exception as exc:self.fail('JOURNAL_OPEN',exc)
        for name,path in bodies.items():
            entry={'link':name,'authority':'USD_CONFIG_NOT_RUNTIME_SENSOR'}
            try:
                prim=stage.GetPrimAtPath(path)
                for key,attribute in (('linear','physxRigidBody:linearDamping'),('angular','physxRigidBody:angularDamping')):
                    attr=prim.GetAttribute(attribute);entry[key]=attr.Get() if attr else None
            except Exception as exc:entry['error']=str(exc)
            self.packet['damping_config'].append(entry)
    def event(self,value):
        safe=json_safe(value)
        if safe!=value:
            clean=json_safe(self.packet);self.packet.clear();self.packet.update(clean);self.packet['errors'].append({'phase':'NONFINITE_OBSERVATION','raw':safe})
        if self.stream is None:return
        try:self.stream.write(json.dumps(safe,allow_nan=False,separators=(',',':'))+'\n');self.stream.flush()
        except Exception as exc:self.packet['errors'].append({'phase':'PERSISTENCE','error':str(exc)})
    def fail(self,phase,exc,partial=None):
        self.packet['errors'].append({'phase':phase,'error':type(exc).__name__+': '+str(exc),'partial':json_safe(partial)});self.event({'phase':'FAILED','fault':self.packet['errors'][-1],'partial':json_safe(partial)})
    def issue(self,step,state,proof):
        if step<=0 or step%12 or self.packet['errors']:return None
        raw={'step':step,'dof_names':self.names,'clock_before':self.clock(),'q_before':dict(state['q']),'qd_before':dict(state['qd']),'G':dict(proof['native']),'FF':dict(proof['native']),'G_clock':proof['source_clock']}
        try:
            with self.backend.use_backend('tensor',raise_on_unsupported=True,raise_on_fallback=True):
                raw['M']=self.array(self.robot.get_mass_matrices()).tolist();raw['C']=self.array(self.robot.get_dof_coriolis_and_centrifugal_compensation_forces()).tolist()
            raw['clock_after_query']=self.clock();need(raw['clock_before']==raw['clock_after_query']==state['clock']==proof['source_clock'],'Pre-step dynamics clock stable');self.event({'phase':'ISSUED','data':raw});return None if self.packet['errors'] else raw
        except Exception as exc:self.fail('QUERY',exc,raw);return None
    def observe(self,raw,row):
        if raw is None:return
        raw.update(clock_after_step=row['clock_after'],qd_after=dict(row['qd']));self.packet['samples'].append(raw);self.event({'phase':'OBSERVED','data':raw})
    def close(self):
        self.event({'phase':'CLOSE_PACKET','data':self.packet})
        try:self.ctx.write(self.ctx.run/'output/dynamics.partial.json',self.packet)
        except Exception as exc:self.fail('CLOSE_PERSISTENCE',exc)
        try:
            if self.stream is not None:self.stream.close()
        except Exception as exc:self.packet['errors'].append({'phase':'CLOSE','error':str(exc)})

def verify_dynamics(report,o):
    try:return _dynamics(report,o)
    except (ValueError,KeyError,TypeError,IndexError) as exc:return {'status':'DYNAMICS_RECORD_INVALID','faults':[{'error':str(exc)}],'samples':[],'robot_PD':'UNKNOWN'}
def _dynamics(report,o):
    p=report['dynamics_balance'];names=report['dof_names'];num=o['num']
    if p['errors']:return {'status':'DYNAMICS_OBSERVATION_FAILED','faults':p['errors'],'samples':[],'robot_PD':'UNKNOWN'}
    need(len(p['samples'])==(len(report['observations'])-1)//12,'Complete declared dynamics stride');derived=[]
    for i,s in enumerate(p['samples'],1):
        step=12*i;pre=report['observations'][step-1];post=report['observations'][step];need(s['step']==step and s['dof_names']==names and len(names)==9,'Actual DOF order/stride')
        need(s['clock_after_step']['lab_step']==s['clock_before']['lab_step']+1 and abs(s['clock_after_step']['engine_time_s']-s['clock_before']['engine_time_s']-1/120)<1e-10,'Dynamics exact single-step advance')
        need(s['clock_before']==s['clock_after_query']==s['G_clock']==pre['clock_after'] and s['clock_after_step']==post['clock_after'],'Exact pre/post dynamics clocks');need(s['q_before']==pre['q'] and s['qd_before']==pre['qd'] and s['qd_after']==post['qd'] and s['G']==post['ff']['native']==s['FF'],'Same state/command/G inputs')
        if len(s['M'])!=1 or len(s['M'][0])!=9 or any(len(row)!=9 for row in s['M'][0]):return {'status':'DYNAMICS_LAYOUT_UNSUPPORTED','faults':[{'step':step,'kind':'M_NOT_FIXED_BASE_9x9'}],'samples':derived,'robot_PD':'UNKNOWN'}
        M=[[num(x) for x in row] for row in s['M'][0]];need(all(M[j][j]>0 for j in range(9)) and max(abs(M[j][k]-M[k][j]) for j in range(9) for k in range(9))<=1e-5,'Native mass matrix symmetry/positive diagonal')
        need(len(s['C'])==1 and len(s['C'][0]) in (9,15),'Explicit C9/15 layout');C=[num(x) for x in s['C'][0]][-9:];a=[(num(s['qd_after'][n])-num(s['qd_before'][n]))*120 for n in names];total={n:sum(M[j][k]*a[k] for k in range(9))+C[j]+num(s['G'][n]) for j,n in enumerate(names)}
        derived.append({'step':step,'time_s':post['time_s'],'inverse_dynamics_estimate':total,'conditional_nonFF_residual_estimate':{n:total[n]-num(s['FF'][n]) for n in names},'projected_minus_inverse_estimate':{n:post['torque_observation']['raw']['projected'][0][j]-total[n] for j,n in enumerate(names)}})
    return {'status':'INVERSE_DYNAMICS_ESTIMATE_AVAILABLE_NOT_PD_SENSOR','faults':[],'samples':derived,'robot_PD':'UNKNOWN','saturation':'UNKNOWN_UNIDENTIFIED_CONSTRAINT_DAMPING_EXTERNAL_CONTRIBUTIONS','damping_config':p['damping_config'],'method':'Pre-step M/C/G times average finite-difference acceleration; estimate, not force calibration'}
