"""042 finite SIM_ONLY joint-space recipe; no Isaac or hardware dependency.

The q coordinates are CAD display-pose deltas in radians. Inertial gains use
the q0 source USD observations, including LINK-to-COM and principal frames.
"""
import json
import math
from pathlib import Path

JOINT_NAMES = [f'J{i}' for i in range(1, 7)]
EFFORT = [3.0, 6.0, 5.0, 2.0, 2.0, 1.0]
END_TOLERANCE_S = 1e-8
FRAME_TOLERANCE = 1e-5


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + ' must be a finite number')
    return float(value)


def _vector(value, count, label):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(label + f' must have {count} entries')
    return [_number(item, label) for item in value]


def _fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError(label + ' fields do not match the frozen schema')


def _expected_phases():
    phases = [('initial_zero', [0.0] * 6, 0.0, 1.0)]
    for i, name in enumerate(JOINT_NAMES):
        for suffix, angle in [('positive', 5), ('zero_after_positive', 0),
                              ('negative', -5), ('zero_after_negative', 0)]:
            q = [0.0] * 6
            q[i] = math.radians(angle)
            phases.append((name + '_' + suffix, q, 1.5, 0.5))
    for name, angles, duration in [('coordinated_A', [5, -5, 5, 3, -3, 3], 1.5),
                                    ('coordinated_B', [-5, 5, -5, -3, 3, -3], 3.0),
                                    ('final_zero', [0] * 6, 1.5)]:
        phases.append((name, [math.radians(x) for x in angles], duration, 0.5))
    return phases


def _validate_program(program):
    _fields(program, ['schema_version', 'name', 'coordinate_convention', 'units',
                      'joint_names', 'rate_hz', 'max_velocity_rad_s', 'phases'], 'program')
    if type(program['schema_version']) is not int or program['schema_version'] != 1:
        raise ValueError('Unsupported program schema')
    if (program['name'] != 'cad_v2_delta_general_motion'
            or program['coordinate_convention'] != 'cad_display_delta'
            or program['joint_names'] != JOINT_NAMES
            or program['units'] != {'position': 'rad', 'velocity': 'rad/s', 'time': 's'}):
        raise ValueError('Program identity, coordinates, names or SI units changed')
    if _number(program['rate_hz'], 'rate_hz') != 120:
        raise ValueError('The frozen physics rate is 120 Hz')
    cap = _number(program['max_velocity_rad_s'], 'max_velocity_rad_s')
    if cap != 0.5:
        raise ValueError('The assumed velocity cap is fixed at 0.5 rad/s')
    expected = _expected_phases()
    if not isinstance(program['phases'], list) or len(program['phases']) != len(expected):
        raise ValueError('The program must contain all 28 ordered phases')
    previous = [0.0] * 6
    for phase, (name, target, move, hold) in zip(program['phases'], expected):
        _fields(phase, ['name', 'target_rad6', 'move_s', 'hold_s'], 'phase')
        q = _vector(phase['target_rad6'], 6, 'target_rad6')
        duration = _number(phase['move_s'], 'move_s')
        settling = _number(phase['hold_s'], 'hold_s')
        if phase['name'] != name or duration != move or settling != hold:
            raise ValueError('Phase order, name or duration changed: ' + name)
        if any(abs(a - b) > 1e-12 for a, b in zip(q, target)):
            raise ValueError('Frozen SI target changed: ' + name)
        if duration and max(1.875 * abs(a - b) / duration for a, b in zip(q, previous)) > cap:
            raise ValueError('Quintic trajectory exceeds the assumed velocity cap')
        previous = q
    return program


def load_program(path):
    """Read and validate the fixed recipe; reject NaN and duplicate JSON keys."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError('Non-finite JSON number: ' + value)

    return _validate_program(json.loads(Path(path).read_text(encoding='utf-8'),
                                        object_pairs_hook=pairs, parse_constant=constant))


def segments(program):
    """Return an ordered timeline in SI units; each endpoint is after its hold."""
    _validate_program(program)
    result, start, previous = [], 0.0, [0.0] * 6
    for phase in program['phases']:
        target = list(phase['target_rad6'])
        end = start + phase['move_s'] + phase['hold_s']
        result.append({'name': phase['name'], 'start_s': start, 'move_s': phase['move_s'],
                       'hold_s': phase['hold_s'], 'end_s': end,
                       'q0_rad6': previous[:], 'q1_rad6': target})
        start, previous = end, target
    return result


def total_time(program):
    return segments(program)[-1]['end_s']


def sample(program, t):
    """Evaluate quintic q and analytic qd; mark only exact end-hold instants.

    Runtime supplies integer step / 120. This sampler does not observe or
    fabricate the runtime clock. The baseline at t=0 has no checkpoint.
    """
    schedule = segments(program)
    t = _number(t, 'time')
    if t < 0 or t > schedule[-1]['end_s'] + END_TOLERANCE_S:
        raise ValueError('Time is outside the finite program')
    for segment in schedule:
        if t <= segment['end_s'] + END_TOLERANCE_S:
            elapsed = max(0.0, t - segment['start_s'])
            duration = segment['move_s']
            if not duration or elapsed >= duration:
                q, qd = segment['q1_rad6'][:], [0.0] * 6
            else:
                u = elapsed / duration
                h = u * u * u * (10 + u * (-15 + 6 * u))
                dh = 30 * u * u * (1 - u) * (1 - u) / duration
                delta = [b - a for a, b in zip(segment['q0_rad6'], segment['q1_rad6'])]
                q = [a + h * d for a, d in zip(segment['q0_rad6'], delta)]
                qd = [dh * d for d in delta]
            checkpoint = segment['name'] if abs(t - segment['end_s']) <= END_TOLERANCE_S else None
            return {'q_rad': q, 'qd_rad_s': qd, 'segment': segment['name'], 'checkpoint': checkpoint}
    raise ValueError('No segment for time')


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _mv(matrix, vector):
    return [_dot(row, vector) for row in matrix]


def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _transpose(matrix):
    return [list(column) for column in zip(*matrix)]


def _rotation(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(label + ' must be a 3x3 matrix')
    r = [_vector(row, 3, label) for row in value]
    identity = _mm(r, _transpose(r))
    determinant = (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
                   - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
                   + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))
    if (abs(determinant - 1) > FRAME_TOLERANCE
            or max(abs(identity[i][j] - int(i == j)) for i in range(3) for j in range(3)) > FRAME_TOLERANCE):
        raise ValueError(label + ' must be a proper rotation')
    return r


def _quaternion(value, label):
    q = _vector(value, 4, label)
    norm = math.sqrt(_dot(q, q))
    if abs(norm - 1) > FRAME_TOLERANCE:
        raise ValueError(label + ' must be a unit wxyz quaternion')
    w, x, y, z = [v / norm for v in q]
    return [[1 - 2 * (y*y + z*z), 2 * (x*y - w*z), 2 * (x*z + w*y)],
            [2 * (x*y + w*z), 1 - 2 * (x*x + z*z), 2 * (y*z - w*x)],
            [2 * (x*z - w*y), 2 * (y*z + w*x), 1 - 2 * (x*x + y*y)]]


def gains(snapshot):
    """SIM_ONLY K=64 Ieff, D=16 Ieff from actual source q0 USD fields.

    Sum each downstream body's COM tensor about the observed parent joint's
    world anchor and axis. Tensor rotations and parallel-axis terms are kept;
    Base contributes no downstream inertia to J1. This is not motor sizing.
    """
    if not isinstance(snapshot, dict):
        raise ValueError('snapshot must be an actual extract_usd observation')
    units = snapshot.get('units', {})
    if (units.get('meters_per_unit') != 1 or units.get('kilograms_per_unit') != 1
            or units.get('up_axis') != 'Z'):
        raise ValueError('Gain source must use m, kg and Z-up')
    bodies = snapshot.get('bodies')
    joints = snapshot.get('joints')
    if not isinstance(bodies, list) or len(bodies) != 7 or not isinstance(joints, list):
        raise ValueError('Gain source must include seven bodies and six revolute joints')
    by_name, by_path, tensors, centers = {}, {}, {}, {}
    for body in bodies:
        if not isinstance(body, dict):
            raise ValueError('Invalid source body')
        name, path = body.get('name'), body.get('path')
        if (name not in ['Base'] + [f'Link{i}' for i in range(1, 7)]
                or name in by_name or not isinstance(path, str) or not path or path in by_path):
            raise ValueError('Body identity/path must be unique and canonical')
        p = _vector(body.get('position'), 3, name + '.position')
        r = _rotation(body.get('rotation'), name + '.rotation')
        mass = _number(body.get('mass'), name + '.mass')
        com = _vector(body.get('com'), 3, name + '.com')
        diag = _vector(body.get('inertia_diag'), 3, name + '.inertia_diag')
        if mass <= 0 or min(diag) <= 0:
            raise ValueError('Mass and principal inertia must be positive')
        principal = _quaternion(body.get('principal_axes_wxyz'), name + '.principal_axes')
        basis = _mm(r, principal)
        tensors[name] = _mm([[basis[i][j] * diag[j] for j in range(3)] for i in range(3)], _transpose(basis))
        centers[name] = [a + b for a, b in zip(p, _mv(r, com))]
        by_name[name] = {'position': p, 'rotation': r, 'mass': mass, 'path': path}
        by_path[path] = by_name[name]
    revolute = [joint for joint in joints if isinstance(joint, dict) and joint.get('type') == 'revolute']
    if (len(revolute) != 6 or len({joint.get('name') for joint in revolute}) != 6
            or {joint.get('name') for joint in revolute} != set(JOINT_NAMES)):
        raise ValueError('Gain source must have exactly J1..J6 revolute joints')
    by_joint, effective = {joint['name']: joint for joint in revolute}, []
    for index, name in enumerate(JOINT_NAMES, 1):
        joint = by_joint[name]
        parent_name = 'Base' if index == 1 else f'Link{index - 1}'
        parent = by_name[parent_name]
        if joint.get('body0') != parent['path'] or joint.get('body1') != by_name[f'Link{index}']['path']:
            raise ValueError('Joint parent/child relation changed: ' + name)
        if joint.get('axis') not in ('X', 'Y', 'Z'):
            raise ValueError('Joint axis must be the USD axis enum')
        anchor_offset = _mv(parent['rotation'], _vector(joint.get('local_pos0'), 3, name + '.local_pos0'))
        anchor = [a + b for a, b in zip(parent['position'], anchor_offset)]
        local = _quaternion(joint.get('local_rot0_wxyz'), name + '.local_rot0')
        enum = [int(joint['axis'] == axis) for axis in ('X', 'Y', 'Z')]
        axis = _mv(parent['rotation'], _mv(local, enum))
        axis_norm = math.sqrt(_dot(axis, axis))
        axis = [x / axis_norm for x in axis]
        inertia = 0.0
        for child_index in range(index, 7):
            child = f'Link{child_index}'
            offset = [a - b for a, b in zip(centers[child], anchor)]
            radius2 = max(0.0, _dot(offset, offset) - _dot(offset, axis) ** 2)
            inertia += _dot(axis, _mv(tensors[child], axis)) + by_name[child]['mass'] * radius2
        if not math.isfinite(inertia) or inertia <= 0:
            raise ValueError('Invalid effective inertia: ' + name)
        effective.append(inertia)
    return {'kp': [64 * x for x in effective], 'kd': [16 * x for x in effective],
            'effort': EFFORT[:], 'i_eff': effective}
