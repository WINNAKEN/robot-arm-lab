"""133 named-SI trajectory adapter and independent actual-object task acceptance."""
from __future__ import annotations
import hashlib
import itertools
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
_BASE_SHA = '9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf'
_base = (HERE/'base_contract.py').read_bytes()
if hashlib.sha256(_base).hexdigest() != _BASE_SHA:
    raise ValueError('Captured original130 contract SHA before execution')
exec(compile(_base, str(HERE/'base_contract.py'), 'exec'), globals())

SCENARIO = None
PLANNER = None
OFFSETS = {'hold':0., 'small':8., 'large':39.}
DURATIONS = {'hold':8., 'small':31., 'large':54.}


def configure(scenario, planner):
    need(scenario['unit'] == 132 and scenario['hardware_approved'] is False and
         scenario['duration_s'] == 85 and scenario['dt_s'] == 1/120, 'Frozen132 task scope')
    need(len(scenario['stages']) == 18 and scenario['boundaries_s'] == [6,12,21,29,35,37,43,48,50,51,56,63,68,70,72,77,83,85], 'Exact18 task schedule')
    need(set(scenario['joint_units']) == set(NAMES) and all(scenario['joint_units'][n] == ('m' if 'slide' in n else 'rad') for n in NAMES), 'Named SI units')
    need(scenario['policy']['object_attachment_forbidden'] is True and scenario['runtime_grasp_status'] == 'NOT_RUN', 'Static is not physical grasp')
    global SCENARIO, PLANNER
    SCENARIO, PLANNER = scenario, planner


def time_map(time_s):
    need(type(time_s) in (int,float) and math.isfinite(time_s) and 0 <= time_s <= 93., 'Actual93s time')
    if time_s<=6:return time_s,1.
    if time_s<=8:return 6.,0.
    if time_s<=50:return time_s-2.,1.
    if time_s<=52:return 48.,0.
    if time_s<=56:return 48.+.5*(time_s-52.),.5
    if time_s<=74:return time_s-6.,1.
    if time_s<=78:return 68.+.5*(time_s-74.),.5
    return time_s-8.,1.


def actual_to_source(time_s):return time_map(time_s)[0]


def target_at(program, stage_name, time_s):
    need(SCENARIO is not None and PLANNER is not None, 'Frozen scenario configured')
    need(stage_name in OFFSETS and math.isfinite(time_s) and 0 <= time_s <= DURATIONS[stage_name]+1e-8, 'Legacy adapter phase/time')
    actual = min(93., OFFSETS[stage_name]+time_s)
    t,jacobian = time_map(actual)
    value = PLANNER.sample(SCENARIO, t)
    velocity={n:value['reference_velocity'][n]*jacobian for n in NAMES}
    return dict(value,reference_velocity=velocity,velocity_targets={n:binary32(velocity[n]) for n in NAMES},scenario_time_s=t,actual_time_s=actual,time_jacobian=jacobian)


def settled(q, qd, target, gripper=True):
    need(set(q) == set(qd) == set(target['targets']) == set(NAMES), 'Exact observed DOFs')
    reasons = []
    for n in NAMES:
        need(all(math.isfinite(v) for v in (q[n], qd[n], target['targets'][n])), 'Finite actual settling')
        if n in ARM:
            if abs(q[n]-target['targets'][n]) > math.radians(.5): reasons.append(n+':position')
            if abs(qd[n]) > math.radians(1): reasons.append(n+':velocity')
        elif gripper:
            if abs(q[n]-target['targets'][n]) > (.02 if n == 'KG1_pinion' else .001): reasons.append(n+':gripper')
    return {'passed':not reasons, 'reasons':reasons}


def phase_check(model, stage_name, q, qd, target, program, min_world_z=None):
    result = settled(q, qd, target, gripper=target['gripper_mode'] == 'open')
    if min_world_z is not None and min_world_z < -.0001:
        result['reasons'].append('desk_penetration'); result['passed'] = False
    return dict(result, stage=stage_name, criterion='ORIGINAL_ARM_0.5deg_1deg_s_NEW_TASK_TIME')


def object_corners(pose, dimensions):
    R = quat(pose['orientation_wxyz'])
    return [add(pose['position'], mv(R,p)) for p in itertools.product(*[(-d/2,d/2) for d in dimensions])]


def contact_pairs(contact, object_path, jaw_paths, active_colliders=None):
    need(contact.get('status') == 'CURRENT_STEP_REPORT_COPIED', 'Current contact observation required')
    result = {n:False for n in jaw_paths}
    for h in contact['headers']:
        actors = {h['actor0'],h['actor1']}
        if object_path not in actors: continue
        positive = any(c['separation'] <= .001 and sum(v*v for v in c['impulse']) > 1e-18 for c in h['contacts'])
        for name,path in jaw_paths.items():
            if path in actors and positive:
                if active_colliders is not None:
                    jaw_index=0 if h['actor0']==path else 1
                    need(h['collider'+str(jaw_index)] in active_colliders[name] and
                         h['collider'+str(1-jaw_index)]==object_path+'/Collision','Positive contact uses active original-component collider and actual object')
                result[name] = True
    return result


class Task:
    """No pose setters: consume same-step independent tensor poses and copied contacts."""
    def __init__(self, scenario, object_path, jaw_paths, active_colliders=None):
        self.s, self.object_path, self.jaw_paths = scenario, object_path, jaw_paths
        self.active_colliders=active_colliders
        self.rows = 0; self.last_step = -1; self.checkpoints = []
        self.minimum = {n:1e9 for n in ARM}; self.maximum = {n:-1e9 for n in ARM}
        self.lift_hold = 0; self.max_lift_hold = 0; self.release_hold = 0; self.max_release_hold = 0
        self.max_lift = 0.; self.max_transport = 0.; self.max_slip = 0.; self.grasp_confirmed = False
        self.source = [r[3] for r in scenario['object']['source_T_world'][:3]]
        self.destination = [r[3] for r in scenario['object']['destination_T_world'][:3]]
        self.carry_samples = 0; self.positive_both_samples = 0; self.release_separation_samples = 0
        self.subphases = []; self.final_home = False

    def observe(self, row, object_state, contact):
        step = row['step']; need(type(step) is int and step == self.last_step+1, 'Contiguous actual task steps')
        self.last_step = step; self.rows += 1
        need(object_state['clock'] == row['clock'], 'Same-step object/robot clock')
        need(object_state['binding']['valid'] is True and object_state['binding']['path'] == self.object_path, 'Current actual dynamic object binding')
        need(object_state['binding']['kinematic'] is False and object_state['binding']['gravity_enabled'] is True and
             abs(object_state['binding']['mass_kg']-.002) < 1e-9, 'Actual free2g object')
        q,qd = row['q'],row['qd']; actual = row['time_s']; t = actual_to_source(actual); desired = PLANNER.sample(self.s,t)
        phase = desired['phase']
        if not self.subphases or self.subphases[-1] != phase: self.subphases.append(phase)
        for n in ARM:
            self.minimum[n] = min(self.minimum[n],q[n]); self.maximum[n] = max(self.maximum[n],q[n])
        obj = object_state['pose']; pos = obj['position']
        need(all(math.isfinite(x) for x in pos+obj['orientation_wxyz']+object_state['linear_velocity']+object_state['angular_velocity']), 'Finite actual object tensor data')
        body = next(p for p in row['body_poses'] if p['name'] == 'KG1')
        G = tf(body['position'],quat(body['orientation_wxyz'])); inv = inverse(G)
        local = [r[3] for r in mm(inv,tf(pos,quat(obj['orientation_wxyz'])))[:3]]
        slip = math.dist(local,self.s['grasp']['translation_m'])
        object_R = mm(inv,tf(pos,quat(obj['orientation_wxyz'])))
        desired_R = [1.,-1.,-1.]
        angle = math.acos(max(-1.,min(1.,(sum(object_R[i][i]*desired_R[i] for i in range(3))-1)/2)))
        gap = .04+q['KG1_slide_A']+q['KG1_slide_B']
        sym = abs(q['KG1_slide_A']-q['KG1_slide_B'])
        corners = object_corners(obj,self.s['object']['dimensions_m'])
        local_corners = [[r[3] for r in mm(inv,tf(p,rotation([0,0,1],0)))[:3]] for p in corners]
        left_gap = min(p[0] for p in local_corners)-(-.02-q['KG1_slide_A'])
        right_gap = (.02+q['KG1_slide_B'])-max(p[0] for p in local_corners)
        both = False
        if step > 0:
            need(contact.get('owner_step') == step, 'Current contact owner step')
            pairs = contact_pairs(contact,self.object_path,self.jaw_paths,self.active_colliders)
            both = all(pairs.values())
            self.positive_both_samples += int(both)
        valid_grasp = both and .018 <= gap <= .022 and sym <= .001 and slip <= .003 and angle <= math.radians(10)
        if t == 51:
            need(valid_grasp, 'Actual bilateral pad-width/orientation/grasp-frame contact at close')
            self.grasp_confirmed = True
        lift = pos[2]-self.source[2]
        transport = math.hypot(pos[0]-self.source[0],pos[1]-self.source[1])
        self.max_lift = max(self.max_lift,lift); self.max_transport = max(self.max_transport,transport)
        if 51 < t <= 63:
            self.carry_samples += 1; self.max_slip = max(self.max_slip,slip)
            need(slip <= .003 and angle <= math.radians(10), 'Actual object slips/rotates outside grasp')
            need(.018 <= gap <= .022 and sym <= .001, 'Actual pad opening matches physical20mm object')
            # Actual oriented corner minimum, current offsets0.5mm each, 0.1mm numerical margin.
            separated = min(p[2] for p in corners) > max(p['dimensions_m'][2] for p in self.s['pedestals'])+.0011
            self.lift_hold = self.lift_hold+1 if lift >= .02 and valid_grasp and separated else 0
            self.max_lift_hold = max(self.max_lift_hold,self.lift_hold)
        if t == 63:
            need(self.grasp_confirmed and lift >= .02 and transport >= .15 and self.max_lift_hold >= 60,
                 'Actual lift20mm/hold0.5s/XYtransfer150mm')
        if 70 < t <= 72:
            v = math.sqrt(sum(x*x for x in object_state['linear_velocity']))
            w = math.sqrt(sum(x*x for x in object_state['angular_velocity']))
            location = all(abs(pos[i]-self.destination[i]) <= (.002 if i==2 else .003) for i in range(3))
            open_tracking = settled(q,qd,desired,gripper=True)['passed']
            # Positive conservative actual geometry separation, not absent header => no contact.
            separated = left_gap > .0011 and right_gap > .0011
            ok = location and v <= .01 and w <= .1 and open_tracking and separated and not both
            self.release_separation_samples += int(separated)
            self.release_hold = self.release_hold+1 if ok else 0
            self.max_release_hold = max(self.max_release_hold,self.release_hold)
        if t == 72: need(self.max_release_hold >= 120, 'Released object settled on actual target for1s')
        if actual == 8 or t in (37,51,72,85):
            result = settled(q,qd,desired,gripper=desired['gripper_mode']=='open')
            self.checkpoints.append(dict(result,time_s=t,actual_time_s=actual,phase=phase,actual_q_rad={n:q[n] for n in ARM},
                actual_qd_rad_s={n:qd[n] for n in ARM},minimum_moving_link_z_m=row.get('minimum_moving_link_z_m')))
            need(result['passed'],'Original ARM settling at new checkpoint:'+str(t)+':'+','.join(result['reasons']))
            if t == 85: self.final_home = True
        return {'phase':phase,'logical_time_s':t,'actual_time_s':actual,'actual_opening_m':gap,'symmetry_error_m':sym,'relative_slip_m':slip,
                'relative_orientation_error_rad':angle,'bilateral_positive_contact':both,'valid_grasp':valid_grasp,
                'lift_m':lift,'transport_xy_m':transport,'release_separation_m':[left_gap,right_gap]}

    def finish(self):
        need(self.rows == 11161 and self.last_step == 11160 and self.final_home, 'Complete93s actual task/home')
        need(self.grasp_confirmed and self.max_lift_hold >= 60 and self.max_release_hold >= 120, 'Actual grasp/place success evidence')
        ranges = {n:self.maximum[n]-self.minimum[n] for n in ARM}
        for n in ARM:
            planned = [self.s['initial_targets_si'][n]]+[p['targets_si'][n] for p in self.s['stages'][:6]]
            need(ranges[n] >= max(planned)-min(planned)-math.radians(1), 'Actual diverse joint range:'+n)
        need(self.subphases == [p['name'] for p in self.s['stages']], 'All18 actual subphases')
        return {'passed':True,'physics_grasp':'ACTUAL_DYNAMIC_FREE_OBJECT','subphases':self.subphases,
                'rows':self.rows,'checkpoints':self.checkpoints,'actual_joint_range_rad':ranges,
                'actual_joint_min_rad':self.minimum,'actual_joint_max_rad':self.maximum,
                'max_lift_m':self.max_lift,'max_transport_xy_m':self.max_transport,'max_relative_slip_m':self.max_slip,
                'lift_hold_steps':self.max_lift_hold,'release_hold_steps':self.max_release_hold,
                'positive_bilateral_samples':self.positive_both_samples,'carry_samples':self.carry_samples,
                'release_separation_samples':self.release_separation_samples,'hardware_approved':False,
                'safe_home':{'qualification':'SIMULATION_DEFINED_RETURN_POSE_NOT_HARDWARE_CERTIFIED',
                    'reference_q_rad':{n:self.s['stages'][-1]['targets_si'][n] for n in ARM},
                    'reference_q_deg':{n:math.degrees(self.s['stages'][-1]['targets_si'][n]) for n in ARM},
                    'actual_final':self.checkpoints[-1]},
                'self_collision_certification':'NOT_CLAIMED','physical_gear_contact':'NOT_VERIFIED'}
