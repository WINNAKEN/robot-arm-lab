"""136: SI joint transforms and diagnostic coupling, with no model mutation."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import numpy as np

GRIPPER = ('KG1_slide_A', 'KG1_slide_B', 'KG1_pinion')
OWNERS = ('Base', 'Link1', 'Link2', 'Link3', 'Link4', 'Link5', 'Link6', 'KG1', 'KG1_A', 'KG1_B', 'KG1_R')


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value):
    require(isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, (bool, np.bool_)) and math.isfinite(value), 'Finite non-boolean number required')
    return float(value)


def vector(value, length=3):
    a = np.asarray(value, dtype=float)
    require(a.shape == (length,) and np.isfinite(a).all(), 'Finite vector shape')
    return a


def axis_rotation(axis, angle):
    a = vector(axis)
    n = float(np.linalg.norm(a))
    require(abs(n-1) <= 1e-10, 'Unit joint axis required')
    x, y, z = a
    cross = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3) + math.sin(number(angle))*cross + (1-math.cos(angle))*(cross@cross)


def rpy_rotation(rpy):
    roll, pitch, yaw = vector(rpy)
    return axis_rotation([0, 0, 1], yaw) @ axis_rotation([0, 1, 0], pitch) @ axis_rotation([1, 0, 0], roll)


def origin(xyz, rpy):
    t = np.eye(4)
    t[:3, :3], t[:3, 3] = rpy_rotation(rpy), vector(xyz)
    return t


def rigid(t):
    t = np.asarray(t, dtype=float)
    require(t.shape == (4, 4) and np.isfinite(t).all() and np.allclose(t[3], [0, 0, 0, 1], atol=1e-12, rtol=0), 'Rigid transform shape')
    require(np.allclose(t[:3, :3].T@t[:3, :3], np.eye(3), atol=1e-9, rtol=0) and abs(np.linalg.det(t[:3, :3])-1) < 1e-9, 'Proper orthogonal transform')
    return t


def inverse(t):
    t = rigid(t)
    out = np.eye(4)
    out[:3, :3] = t[:3, :3].T
    out[:3, 3] = -out[:3, :3]@t[:3, 3]
    return out


def millimetres(t):
    out = rigid(t).copy()
    out[:3, 3] *= 1000
    return out


def quaternion(wxyz):
    q = vector(wxyz, 4)
    norm = float(np.linalg.norm(q))
    require(abs(norm-1) <= 1e-5, 'Near-unit actual quaternion required')
    w, x, y, z = q/norm
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def body_pose(row):
    t = np.eye(4)
    t[:3, :3], t[:3, 3] = quaternion(row['orientation_wxyz']), vector(row['position'])
    return t


def rotation_angle(r):
    r = np.asarray(r, dtype=float)
    skew = np.array([r[2, 1]-r[1, 2], r[0, 2]-r[2, 0], r[1, 0]-r[0, 1]])/2
    return math.atan2(float(np.linalg.norm(skew)), float((np.trace(r)-1)/2))


def residual(actual, expected):
    delta = inverse(expected)@rigid(actual)
    a = rotation_angle(delta[:3, :3])
    return {'translation_in_expected_frame_mm': (delta[:3, 3]*1000).tolist(),
            'translation_norm_mm': float(np.linalg.norm(delta[:3, 3])*1000),
            'rotation_rad': a, 'rotation_deg': math.degrees(a)}


def parse_urdf(raw, ledger, cad_parameters):
    tree = ET.fromstring(raw)
    all_joints = tree.findall('joint')
    require(len({j.get('name') for j in all_joints}) == len(all_joints), 'Unique XML joint names')
    expected = {'KG1_mount': ('fixed', 'Link6', 'KG1'), 'KG1_slide_A': ('prismatic', 'KG1', 'KG1_A'),
                'KG1_slide_B': ('prismatic', 'KG1', 'KG1_B'), 'KG1_pinion': ('revolute', 'KG1', 'KG1_R')}
    joints = {}
    for j in all_joints:
        name = j.get('name')
        if name not in expected:
            continue
        require((j.get('type'), j.find('parent').get('link'), j.find('child').get('link')) == expected[name], 'Pinned gripper XML topology')
        o = j.find('origin')
        xyz, rpy = [list(map(float, o.get(k, '0 0 0').split())) for k in ('xyz', 'rpy')]
        info = {'name': name, 'type': j.get('type'), 'parent': j.find('parent').get('link'),
                'child': j.find('child').get('link'), 'xyz_m': xyz, 'rpy_rad': rpy, 'zero': origin(xyz, rpy)}
        if info['type'] != 'fixed':
            axis = list(map(float, j.find('axis').get('xyz').split()))
            axis_rotation(axis, 0.)
            info['axis'] = axis
        mimic = j.find('mimic')
        if mimic is not None:
            info['mimic'] = {'joint': mimic.get('joint'), 'multiplier': float(mimic.get('multiplier', '1')), 'offset': float(mimic.get('offset', '0'))}
        joints[name] = info
    require(set(joints) == set(expected), 'All four gripper joints required')
    m = joints['KG1_pinion']['mimic']
    require(m['joint'] == 'KG1_slide_A' and math.isfinite(m['multiplier']) and m['multiplier'] < 0 and m['offset'] == 0, 'Pinion mimic SI convention')
    require(joints['KG1_slide_B']['mimic'] == {'joint': 'KG1_slide_A', 'multiplier': 1., 'offset': 0.}, 'Jaw B mimic convention')
    require(np.array_equal(joints['KG1_slide_A']['axis'], [-1, 0, 0]) and np.array_equal(joints['KG1_slide_B']['axis'], [1, 0, 0]) and
            np.array_equal(joints['KG1_pinion']['axis'], [0, 1, 0]), 'XML axis convention')
    radius_mm = number(cad_parameters['gear']['module'])*number(cad_parameters['gear']['teeth'])/2
    require(radius_mm > 0 and abs(m['multiplier']+1000/radius_mm) < 1e-10, 'CAD pitch radius / XML rad per metre')
    mount_mm = np.asarray(ledger['KG1_mount_T_Link6_from_G_mm'], dtype=float)
    require(np.allclose(millimetres(joints['KG1_mount']['zero']), mount_mm, atol=1e-12, rtol=0), 'XML / numeric-ledger fixed mount')
    require(ledger['gripper_asset_reference']['u_mm'] == 0 and ledger['gripper_asset_reference']['rotor_pivot_G_mm'] == [0, 0, 26], 'Closed original geometry reference')
    opening_zero_mm = float(-joints['KG1_slide_A']['xyz_m'][0]*1000)
    require(opening_zero_mm == joints['KG1_slide_B']['xyz_m'][0]*1000 == 20., 'URDF zero half opening')
    require(abs(joints['KG1_pinion']['rpy_rad'][1]+opening_zero_mm/radius_mm) < 1e-12, 'URDF rotor zero includes opening phase')
    return joints, {'radius_mm': radius_mm, 'mimic_rad_per_m': m['multiplier'], 'mimic_offset_rad': m['offset'],
                    'geometry_reference_u_mm': 0., 'URDF_zero_half_opening_mm': opening_zero_mm,
                    'nominal_mount_ledger_mm': mount_mm.tolist()}


def joint_transform(joint, q=0.):
    motion = np.eye(4)
    if joint['type'] == 'prismatic':
        motion[:3, 3] = vector(joint['axis'])*number(q)
    elif joint['type'] == 'revolute':
        motion[:3, :3] = axis_rotation(joint['axis'], number(q))
    else:
        require(joint['type'] == 'fixed' and q == 0., 'Fixed joint cannot move')
    return joint['zero']@motion


def gripper_fk(joints, q):
    return {'KG1': np.eye(4), **{joints[n]['child']: joint_transform(joints[n], number(q[n])) for n in GRIPPER}}


def project_joint(actual_parent_from_child, joint, q_hint):
    d = inverse(joint['zero'])@rigid(actual_parent_from_child)
    axis = vector(joint['axis'])
    if joint['type'] == 'prismatic':
        value = float(d[:3, 3]@axis)
        off_translation = float(np.linalg.norm(d[:3, 3]-axis*value)*1000)
        off_rotation = rotation_angle(d[:3, :3])
    else:
        require(joint['type'] == 'revolute', 'Project only movable joints')
        rr = d[:3, :3]
        skew = np.array([rr[2, 1]-rr[1, 2], rr[0, 2]-rr[2, 0], rr[1, 0]-rr[0, 1]])/2
        principal = math.atan2(float(axis@skew), float((np.trace(rr)-1)/2))
        value = principal+2*math.pi*round((number(q_hint)-principal)/(2*math.pi))
        off_translation = float(np.linalg.norm(d[:3, 3])*1000)
        off_rotation = rotation_angle(axis_rotation(axis, value).T@rr)
    return {'projected_q': value, 'logged_q': number(q_hint), 'projected_minus_logged_q': value-q_hint,
            'off_axis_translation_mm': off_translation, 'off_axis_rotation_rad': off_rotation}


def coupling(q, targets, ratio, offset, radius_mm):
    result = {}
    for label, name in [('A', 'KG1_slide_A'), ('B', 'KG1_slide_B')]:
        error = number(q['KG1_pinion'])-(ratio*number(q[name])+offset)
        target_error = number(targets['KG1_pinion'])-(ratio*number(targets[name])+offset)
        result['phase_'+label+'_rad'] = error
        result['phase_'+label+'_deg'] = math.degrees(error)
        result['equivalent_rack_'+label+'_mm'] = error*radius_mm
        result['target_phase_'+label+'_rad'] = target_error
        result['jaw_'+label+'_tracking_mm'] = (number(q[name])-number(targets[name]))*1000
    result['jaw_asymmetry_mm'] = (q['KG1_slide_A']-q['KG1_slide_B'])*1000
    result['pinion_tracking_rad'] = number(q['KG1_pinion'])-number(targets['KG1_pinion'])
    return result
