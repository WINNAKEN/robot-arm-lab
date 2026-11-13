"""021 offline candidate math. No CAD runtime, motors, TCP or physics acceptance."""
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import sys
import uuid

SOURCE = 'models/armold-mks-concept-v1/kinematics.json'
OUTPUT = 'outputs/joint-frames-v1'
I = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))


def require(ok, path):
    if not ok:
        raise ValueError(path)


def obj(value, path):
    require(type(value) is dict, path + ': expected object')
    return value


def field(value, key, path):
    obj(value, path)
    require(key in value, path + '.' + key + ': missing')
    return value[key]


def array(value, n, path):
    require(type(value) is list and len(value) == n, path + ': wrong array shape')
    return value


def number(value, bound, path):
    require(type(value) in (float, int), path + ': expected number')
    require(-bound <= value <= bound, path + ': out of range')
    result = float(value)
    require(math.isfinite(result), path + ': nonfinite')
    return result


def vector(value, n, bound, path):
    return tuple(number(x, bound, f'{path}[{i}]')
                 for i, x in enumerate(array(value, n, path)))


def transpose(a):
    return tuple(zip(*a))


def mv(a, b):
    return tuple(sum(x*y for x, y in zip(row, b)) for row in a)


def mm(a, b):
    return tuple(tuple(sum(x*y for x, y in zip(row, col))
                       for col in zip(*b)) for row in a)


def close(a, b, tol=1e-8):
    return len(a) == len(b) and all(
        close(x, y, tol) if isinstance(x, (tuple, list)) else abs(x-y) <= tol
        for x, y in zip(a, b))


def rotation(axis, angle):
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    d = 1-c
    return ((c+x*x*d, x*y*d-z*s, x*z*d+y*s),
            (y*x*d+z*s, c+y*y*d, y*z*d-x*s),
            (z*x*d-y*s, z*y*d+x*s, c+z*z*d))


def matrix(value, path):
    rows = tuple(vector(row, 3, 1.000001, f'{path}[{i}]')
                 for i, row in enumerate(array(value, 3, path)))
    require(close(mm(transpose(rows), rows), I), path + ': not orthonormal')
    a, b, c = rows
    determinant = (a[0]*(b[1]*c[2]-b[2]*c[1])
                   - a[1]*(b[0]*c[2]-b[2]*c[0])
                   + a[2]*(b[0]*c[1]-b[1]*c[0]))
    require(abs(determinant-1) < 1e-8, path + ': not SO(3)')
    return rows


def unit_axis(value, path):
    result = vector(value, 3, 1.000001, path)
    require(abs(sum(x*x for x in result)-1) < 1e-8, path + ': not unit axis')
    return result


def parse(raw):
    require(len(raw) <= 1024*1024, 'JSON exceeds 1MiB')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    stack = [(value, 0)]
    while stack:
        node, depth = stack.pop()
        require(depth <= 64, 'JSON exceeds depth64')
        if type(node) in (dict, list):
            children = node.values() if type(node) is dict else node
            stack.extend((x, depth+1) for x in children)
        elif type(node) is float:
            require(math.isfinite(node), 'nonfinite JSON number')
    return value


@dataclass(frozen=True)
class Joint:
    name: str
    parent: str
    child: str
    origin_m: tuple
    axis_world: tuple
    axis_parent: tuple
    pose_rad: float
    parent_rotation: tuple
    child_rotation: tuple
    offset_m: tuple
    fixed_rotation: tuple


@dataclass(frozen=True)
class Layout:
    joints: tuple


def decode(raw):
    data = obj(parse(raw), '$')
    require(field(data, 'units', '$') == 'mm', '$.units: expected mm')
    count = field(data, 'joint_count', '$')
    require(type(count) is int and count == 6, '$.joint_count: expected integer6')
    records = array(field(data, 'joints', '$'), 6, '$.joints')
    joints, prev_p, prev_r = [], (0., 0., 0.), I
    for i, record in enumerate(records):
        path = f'$.joints[{i}]'
        obj(record, path)
        values = {key: field(record, key, path) for key in (
            'name', 'parent', 'child', 'origin_mm', 'axis_world',
            'axis_parent_zero', 'pose_deg', 'R_parent', 'R_child')}
        expected = (f'J{i+1}', 'Base' if i == 0 else f'Link{i}', f'Link{i+1}')
        for key, text in zip(('name', 'parent', 'child'), expected):
            require(type(values[key]) is str and values[key] == text, path+'.'+key)
        p = tuple(x/1000 for x in vector(values['origin_mm'], 3, 1e6, path+'.origin_mm'))
        a = unit_axis(values['axis_parent_zero'], path+'.axis_parent_zero')
        world = unit_axis(values['axis_world'], path+'.axis_world')
        pose = math.radians(number(values['pose_deg'], 360, path+'.pose_deg'))
        rp = matrix(values['R_parent'], path+'.R_parent')
        rc = matrix(values['R_child'], path+'.R_child')
        require(close(rp, prev_r), path+': discontinuous parent rotation')
        require(close(mv(rp, a), world), path+': world axis mismatch')
        fixed = mm(transpose(rp), rc)
        require(close(fixed, rotation(a, pose)), path+': display rotation mismatch')
        offset = mv(transpose(rp), tuple(x-y for x, y in zip(p, prev_p)))
        joints.append(Joint(*expected, p, world, a, pose, rp, rc, offset, fixed))
        prev_p, prev_r = p, rc
    return Layout(tuple(joints))


def angles(values):
    return vector(list(values) if type(values) is tuple else values,
                  6, sys.float_info.max, 'angles_rad')


def geometric_to_delta(layout, values):
    return tuple(q-j.pose_rad for q, j in zip(angles(values), layout.joints))


def delta_to_geometric(layout, values):
    return tuple(q+j.pose_rad for q, j in zip(angles(values), layout.joints))


def fk(layout, values):
    p, r, result = (0., 0., 0.), I, []
    for joint, q in zip(layout.joints, angles(values)):
        p = tuple(a+b for a, b in zip(p, mv(r, joint.offset_m)))
        axis = mv(r, joint.axis_parent)
        r = mm(r, mm(rotation(joint.axis_parent, q), joint.fixed_rotation))
        result.append({'name': joint.name, 'origin_m': p, 'axis_world': axis,
                       'rotation_world': r})
    return result


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    with path.open('rb') as stream:
        raw = stream.read(1024*1024+1)
    require(len(raw) <= 1024*1024, 'file exceeds 1MiB: '+str(path))
    return raw


def atomic(path, value):
    temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_bytes(encoded(value))
    os.replace(temp, path)


def verify(root):
    out = root / OUTPUT
    current = obj(parse(read(out/'current.json')), 'current')
    require(field(current, 'status', 'current') == 'PASS', 'No current PASS; no fallback')
    run = field(current, 'run_id', 'current')
    require(type(run) is str and re.fullmatch('[0-9a-f]{32}', run) is not None, 'Invalid run ID')
    bundle = out/'runs'/run
    raw = read(bundle/'manifest.json')
    require(sha(raw) == field(current, 'manifest_sha256', 'current'), 'manifest hash')
    manifest = obj(parse(raw), 'manifest')
    require(field(manifest, 'run_id', 'manifest') == run, 'run identity')
    require(field(manifest, 'producer_sha256', 'manifest') == sha(read(Path(__file__))), 'producer changed')
    require(field(manifest, 'source_path', 'manifest') == SOURCE, 'source path changed')
    source_hash = field(manifest, 'source_sha256', 'manifest')
    require(sha(read(root/SOURCE)) == source_hash, 'source changed')
    files = obj(field(manifest, 'files', 'manifest'), 'manifest.files')
    require(set(files) == {'input.json', 'frames.json'}, 'artifact set')
    for name in ('input.json', 'frames.json'):
        require(sha(read(bundle/name)) == files[name], 'artifact hash: '+name)
    require(files['input.json'] == source_hash, 'snapshot source identity')
    return {'status': 'PASS', 'run_id': run, 'scope': 'OFFLINE_MATH_CANDIDATE'}


def build(root):
    out = root/OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    run, success = uuid.uuid4().hex, False
    current = out/'current.json'
    try:
        atomic(current, {'status': 'BUILDING', 'run_id': run})
        raw = read(root/SOURCE)
        producer = sha(read(Path(__file__)))
        layout = decode(raw)
        payload = encoded({
            'scope': 'OFFLINE_MATH_CANDIDATE', 'native_cad_agreement': 'NOT_RUN',
            'coordinate_convention': 'right-hand q_geometric=q_delta+pose_rad; delta0=display',
            'joints': [asdict(j) for j in layout.joints],
            'display_pose': fk(layout, [0.]*6),
            'geometric_zero': fk(layout, geometric_to_delta(layout, [0.]*6)),
            'physical_unknowns': dict.fromkeys(('can_ids', 'motor_signs', 'reduction',
                'hardware_zeros', 'encoder_scale', 'limits', 'mass_inertia', 'tcp', 'native_angle_sign')),
            'ring_geometry': 'DEFERRED_UNRESOLVED_020', 'hardware_approved': False})
        bundle = out/'runs'/run
        bundle.mkdir(parents=True, exist_ok=False)
        (bundle/'input.json').write_bytes(raw)
        (bundle/'frames.json').write_bytes(payload)
        require(read(root/SOURCE) == raw, 'source changed during build')
        require(sha(read(Path(__file__))) == producer, 'producer changed during build')
        manifest = encoded({'run_id': run, 'source_path': SOURCE, 'source_sha256': sha(raw),
            'producer_sha256': producer, 'files': {'input.json': sha(raw), 'frames.json': sha(payload)}})
        (bundle/'manifest.json').write_bytes(manifest)
        atomic(current, {'status': 'PASS', 'run_id': run, 'manifest_sha256': sha(manifest)})
        result = verify(root)
        success = True
        return result
    finally:
        if not success:
            error = sys.exc_info()[1]
            atomic(current, {'status': 'FAILED', 'run_id': run,
                             'reason': type(error).__name__ if error else 'IncompleteBuild'})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('build', 'verify'))
    cli.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = cli.parse_args()
    print(json.dumps((build if args.action == 'build' else verify)(args.root)))


if __name__ == '__main__':
    main()
