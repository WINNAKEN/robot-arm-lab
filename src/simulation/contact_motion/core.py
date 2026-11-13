"""043 assumption-based gravity feedforward; no device or simulator I/O."""
import importlib.util
import math
from pathlib import Path

_path = Path(__file__).with_name('motion_core.py')
if not _path.exists():
    _path = Path(__file__).parent.parent/'motion/core.py'
_spec = importlib.util.spec_from_file_location('_gravity_motion_core', _path)
motion = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motion)
load_program, sample, total_time, gains = motion.load_program, motion.sample, motion.total_time, motion.gains
LINKS = ['Base']+[f'Link{i}' for i in range(1, 7)]
GRAVITY = [0., 0., -9.81]
CAP = [3., 6., 5., 2., 2., 1.]


def need(value, reason):
    if not value:
        raise ValueError(reason)


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def gravity_efforts(static, observed, gravity=GRAVITY):
    """Minus generalized gravity from previous actual LINK-origin observations."""
    bodies = {x['name']: x for x in static['bodies']}
    poses = {x['name']: (x['position'], motion._quaternion(x['orientation_wxyz'], 'actual pose')) for x in observed}
    need(set(bodies) == set(poses) == set(LINKS), 'Seven unique assumed bodies and actual poses')
    by_path = {x['path']: x['name'] for x in bodies.values()}
    joints = {x['name']: x for x in static['joints'] if x['type'] == 'revolute'}
    result = []
    for i in range(6):
        joint = joints[f'J{i+1}']
        p, r = poses[by_path[joint['body0']]]
        anchor = [a+b for a, b in zip(p, motion._mv(r, joint['local_pos0']))]
        jr = motion._mm(r, motion._quaternion(joint['local_rot0_wxyz'], 'joint frame'))
        axis = motion._mv(jr, [float(joint['axis'] == x) for x in 'XYZ'])
        torque = 0.
        for name in LINKS[i+1:]:
            body = bodies[name]
            pos, rotation = poses[name]
            center = [a+b for a, b in zip(pos, motion._mv(rotation, body['com']))]
            force = [body['mass']*g for g in gravity]
            torque -= sum(a*b for a, b in zip(axis, cross([x-y for x, y in zip(center, anchor)], force)))
        need(math.isfinite(torque), 'Finite gravity effort')
        result.append(torque)
    return result


def bounded_efforts(torque):
    need(len(torque) == 6 and all(type(t) in (int, float) and math.isfinite(t) for t in torque), 'Finite six efforts')
    ff = [max(-cap, min(cap, t)) for t, cap in zip(torque, CAP)]
    return {'ff': ff, 'pd_cap': [cap-abs(t) for cap, t in zip(CAP, ff)],
            'saturated': [abs(t) > cap for t, cap in zip(torque, CAP)]}
