"""137 measured-jaw reference policy and exact native dispatch derivation (stdlib only)."""
from __future__ import annotations
import ast
import copy
import math
from numbers import Real
import struct

NAMES = ('J1','J2','J3','J4','J5','J6','KG1_slide_A','KG1_slide_B','KG1_pinion')
LEADER, FOLLOWER, OTHER = 'KG1_slide_A', 'KG1_pinion', 'KG1_slide_B'
RATIO = -1/.0135
LIMITS = {
 'J1':(-3.2288591161895095,2.705260340591211,3.,.5,(0.,0.,1.)),
 'J2':(-.8726646259971648,.8726646259971648,6.,.5,(0.,1.,0.)),
 'J3':(-1.5707963267948966,.8726646259971648,5.,.5,(0.,1.,0.)),
 'J4':(-2.356194490192345,1.8325957145940461,2.,.5,(1.,0.,0.)),
 'J5':(-2.007128639793479,1.1344640137963142,2.,.5,(0.,1.,0.)),
 'J6':(-2.792526803190927,math.pi,1.,.5,(1.,0.,0.)),
 LEADER:(-.02,.027,10.,.02,(-1.,0.,0.)), OTHER:(-.02,.027,10.,.02,(1.,0.,0.)),
 FOLLOWER:(-2.,1.4814814814814814,.2,2.,(0.,1.,0.)),
}

def need(ok, message):
    if not ok: raise ValueError(message)

def number(value):
    need(isinstance(value,Real) and not isinstance(value,bool) and math.isfinite(value),'Finite nonboolean scalar')
    return float(value)

def binary32(value):
    return struct.unpack('<f',struct.pack('<f',number(value)))[0]

def model_ratio(model):
    need(isinstance(model,dict) and set(model['movable'])==set(NAMES) and len(model['movable'])==9,'Canonical nine movable DOFs')
    for name,(lo,hi,effort,speed,axis) in LIMITS.items():
        j=model['joints'][name]
        need(j['type']==('prismatic' if 'slide' in name else 'revolute'),'Original joint type')
        need(tuple(j['axis'])==axis,'Original joint axis')
        need(all(number(j[k])==v for k,v in zip(('lower','upper','effort','velocity'),(lo,hi,effort,speed))),'Original source joint limits')
    m=model['joints'][FOLLOWER]['mimic']; b=model['joints'][OTHER]['mimic']
    need(m['joint']==LEADER and number(m['multiplier'])==RATIO and number(m['offset'])==0.,'Original SI pinion mimic')
    need(b['joint']==LEADER and number(b['multiplier'])==1. and number(b['offset'])==0.,'Original B mimic')
    return number(m['multiplier']),number(m['offset'])

def checked_clock(value, expected_step):
    need(isinstance(value,dict) and set(value)=={'engine_time_s','lab_step'},'Exact native clock fields')
    need(type(value['lab_step']) is int and value['lab_step']==expected_step,'Expected causal native step')
    need(abs(number(value['engine_time_s'])-expected_step/120)<=1e-8,'Expected native engine time')
    return dict(value)

def reference(target, current, model, names, now, command_step):
    """Pure per-command validation. No setters, input mutation, clamp or fallback."""
    need(type(command_step) is int and command_step>=1,'Positive command step')
    need(len(names)==9 and set(names)==set(NAMES),'Exact reordered native DOFs')
    m,offset=model_ratio(model)
    for field in ('targets','velocity_targets','reference_velocity'):
        need(isinstance(target[field],dict) and set(target[field])==set(NAMES),'Exact logical reference census')
        for v in target[field].values():number(v)
    for field in ('q','qd'):
        need(isinstance(current[field],dict) and set(current[field])==set(NAMES),'Exact measured census')
        for v in current[field].values():number(v)
    source=checked_clock(current['clock'],command_step-1)
    need(checked_clock(current['clock_before'],command_step-1)==source==checked_clock(current['clock_after'],command_step-1)==checked_clock(now,command_step-1),'Same causal observed clock')
    q,qd=number(current['q'][LEADER]),number(current['qd'][LEADER])
    lo,hi,_,speed,_=LIMITS[LEADER]
    need(lo<=q<=hi and abs(qd)<=speed,'Measured leader source limits')
    p,v=m*q+offset,m*qd
    flo,fhi,_,fspeed,_=LIMITS[FOLLOWER]
    need(flo<=p<=fhi and abs(v)<=fspeed,'Derived pinion source limits')
    positions={n:binary32(target['targets'][n]) for n in names}
    velocities={n:number(target['velocity_targets'][n]) for n in names}
    positions[FOLLOWER],velocities[FOLLOWER]=binary32(p),binary32(v)
    need(flo<=positions[FOLLOWER]<=fhi and abs(velocities[FOLLOWER])<=fspeed,'Transmitted pinion source limits')
    for n in names:
        nlo,nhi,_,nspeed,_=LIMITS[n]
        need(nlo<=positions[n]<=nhi and abs(velocities[n])<=nspeed,'All transmitted references remain in source limits')
    return {'schema':'measured-pinion-reference-137-v1','command_step':command_step,'source_step':command_step-1,
            'source_clock':source,'leader':LEADER,'multiplier_rad_per_m':m,'offset_rad':offset,
            'input_q':copy.deepcopy(current['q']),'input_qd':copy.deepcopy(current['qd']),
            'logical_targets':copy.deepcopy(target['targets']),'logical_velocity_targets':copy.deepcopy(target['velocity_targets']),
            'positions':positions,'velocities':velocities,'pinion_reference_before_binary32':{'position_rad':p,'velocity_rad_s':v},
            'binary32_position_error_rad':positions[FOLLOWER]-p,'binary32_velocity_error_rad_s':velocities[FOLLOWER]-v,
            'B_relative_reference_residual_rad':positions[FOLLOWER]-(m*number(current['q'][OTHER])+offset),
            'state_provenance':'HOST_RECONSTRUCTED_CLOCK_BOUNDS' if current.get('_host_reconstructed_clock_bounds') is True else 'LIVE_NATIVE_STATE_WITH_BEFORE_AFTER_CLOCK',
            'readback_verified':False,'new_plant_response':False}

def guard_clock(receipt, now):
    need(checked_clock(now,receipt['source_step'])==receipt['source_clock'],'Current clock changed before command')

def acknowledge(receipt, positions, velocities, now):
    guard_clock(receipt,now)
    for field,actual in [('positions',positions),('velocities',velocities)]:
        need(set(actual)==set(NAMES),'Command readback census')
        need(all(abs(number(actual[n])-receipt[field][n])<=1e-7 for n in NAMES),'Actual applied reference readback mismatch')
    receipt['readback_positions']=copy.deepcopy(positions);receipt['readback_velocities']=copy.deepcopy(velocities)
    receipt['readback_clock']=dict(now);receipt['readback_verified']=True

def journal_row(row, receipt):
    need(receipt is not None or row['step']==0,'Only initial row may have no applied command')
    row['applied137']={'status':'NOT_APPLIED_INITIAL_ROW'} if receipt is None else copy.deepcopy(receipt)
    if receipt is not None:
        need(receipt['readback_verified'] and row['step']==receipt['command_step'],'Poststep receipt binding')
    return row

SETTER_OLD = """                with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                    robot.set_dof_max_efforts([[remaining[n] for n in names]])
                    robot.set_dof_position_targets([[C.binary32(target['targets'][n]) for n in names]])
                    robot.set_dof_velocity_targets([[target['velocity_targets'][n] for n in names]])
                    robot.set_dof_efforts([[ff[n] for n in names]])
                    # Actual command readbacks remain within the original velocity/cap/gain policy.
                    C.near(C.named_columns(names, model['movable'], array(robot.get_dof_max_efforts())[0]), remaining, 2e-6)
                    C.near(C.named_columns(names, model['movable'], array(robot.get_dof_position_targets())[0]),
                           {n: C.binary32(target['targets'][n]) for n in names}, 1e-7)
                    C.near(C.named_columns(names, model['movable'], array(robot.get_dof_velocity_targets())[0]), target['velocity_targets'], 1e-7)"""
SETTER_NEW = """                applied137 = _feedback137.reference(target,current,model,names,clock(),report['completed_steps']+1)
                with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                    _feedback137.guard_clock(applied137,clock())
                    robot.set_dof_max_efforts([[remaining[n] for n in names]])
                    robot.set_dof_position_targets([[applied137['positions'][n] for n in names]])
                    robot.set_dof_velocity_targets([[applied137['velocities'][n] for n in names]])
                    robot.set_dof_efforts([[ff[n] for n in names]])
                    C.near(C.named_columns(names, model['movable'], array(robot.get_dof_max_efforts())[0]), remaining, 2e-6)
                    _feedback137.acknowledge(applied137,
                        C.named_columns(names,model['movable'],array(robot.get_dof_position_targets())[0]),
                        C.named_columns(names,model['movable'],array(robot.get_dof_velocity_targets())[0]),clock())"""

def derive_effective(source):
    """Called after all133 source derivations, before its real compile/exec."""
    replacements=[(SETTER_OLD,SETTER_NEW),
      ('    def row_for(stage_name, local_step, observed, target, proof=None, remaining=None):',
       '    applied137 = None\n    def row_for(stage_name, local_step, observed, target, proof=None, remaining=None):'),
      ("        return {'step': report['completed_steps'], 'time_s': report['completed_steps']/120,",
       "        row137 = {'step': report['completed_steps'], 'time_s': report['completed_steps']/120,"),
      ("'effort_remaining': remaining}","'effort_remaining': remaining}\n        return _feedback137.journal_row(row137,applied137)")]
    inventory=[]
    for old,new in replacements:
        need(source.count(old)==1,'Exact137 native derivation anchor')
        source=source.replace(old,new,1);inventory.append({'anchor':old,'count':1})
    tree=ast.parse(source);native=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_native')
    need(sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='set_dof_position_targets' for n in ast.walk(native))==1,'One actual position target dispatch')
    return source,inventory
