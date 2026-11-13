"""022: stored v2 joint metadata alignment only; no geometry or CAD solver proof."""
from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import sys
import uuid
import zipfile

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'src/joint_frames/frames.py').is_file())
CORE_PATH = ROOT/'src/joint_frames/frames.py'
CORE_SHA = '1eb5d41f439e5201ce0b0c5ee53222584082b8446bfef2e00a5bdd3eed5b4d46'
APPROVAL = '.dev/joint-frames-evidence/frozen-r2-manifest.json'
RECEIPT = '.dev/joint-frames-evidence/l4-r2.md'
APPROVAL_SHA = '43d1153d75917a96e8ded6f313e4314846766f8cbb67f818670b095c41ff8422'
RECEIPT_SHA = 'fdd4030257d77b51e9077d1e8cbd1425dd036a70f9ffa4be13ae96e3ba5f5138'
ACCEPTED_RUN = '9921dbd274204f93956849385affe980'
NATIVE = 'models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft'
COMMANDS = 'models/armold-mks-product-v2/build-commands.json'
KIN = 'models/armold-mks-concept-v1/kinematics.json'
OUTPUT = 'outputs/v2-joint-alignment'
POINT_TOL_MM, AXIS_TOL, ZERO_TOL_RAD = 1e-5, 1e-8, 1e-10
FILES = ('native.solidcraft', 'commands.json', 'kinematics.json', 'report.json', 'report.md')
_CORE = None


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, cap=1024*1024):
    with path.open('rb') as stream:
        raw = stream.read(cap+1)
    need(len(raw) <= cap, 'file size limit: '+str(path))
    return raw


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def atomic(path, value):
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_bytes(encoded(value))
    os.replace(temporary, path)


def approved_core():
    global _CORE
    need(sha(read(CORE_PATH)) == CORE_SHA, 'Unapproved actual core producer')
    if _CORE is None:
        spec = importlib.util.spec_from_file_location('_alignment_approved_frames', CORE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _CORE = module
    need(sha(read(Path(_CORE.__file__))) == CORE_SHA, 'Loaded core producer differs')
    return _CORE


def admission(root, f):
    approval, receipt = read(root/APPROVAL), read(root/RECEIPT)
    need(sha(approval) == APPROVAL_SHA and sha(receipt) == RECEIPT_SHA, 'Unapproved021 baseline/receipt')
    records = f.array(f.parse(approval), 9, 'approval')
    paths = []
    for i, row in enumerate(records):
        path = f.field(row, 'path', f'approval[{i}]')
        digest = f.field(row, 'sha256', f'approval[{i}]')
        need(type(path) is str and not Path(path).is_absolute() and '..' not in Path(path).parts, 'approval path')
        need(type(digest) is str and re.fullmatch('[0-9a-fA-F]{64}', digest) is not None, 'approval hash')
        need(sha(read(root/path)) == digest.lower(), 'Accepted021 file changed: '+path)
        paths.append(path)
    need(len(set(paths)) == 9, 'Duplicate approved path')
    result = f.verify(root)
    need(result['run_id'] == ACCEPTED_RUN, 'Unapproved021 run')
    return {'run_id': result['run_id'], 'approval_sha256': APPROVAL_SHA,
            'receipt_sha256': RECEIPT_SHA, 'core_sha256': CORE_SHA}


def producer():
    return {'alignment_sha256': sha(read(Path(__file__))), 'core_sha256': sha(read(CORE_PATH))}


def identifier(value, path):
    need(type(value) is int and 0 < value < 2**31, path+': expected positive integer ID')
    return value


def text(value, path):
    need(type(value) is str and 0 < len(value) <= 256, path+': expected text')
    return value


def sequence(value, path):
    need(type(value) is list, path+': expected array')
    return value


def root_parent(value, path):
    need(type(value) is int and value == 0, path+': only world-root parent0 supported')


def limits(value, path, f):
    rows = f.array(value, 1, path)
    pair = f.vector(rows[0], 2, 1e6, path+'[0]')
    need(pair[0] < pair[1] and pair[0] <= 0 <= pair[1], path+': invalid software limits')
    return pair


@dataclass(frozen=True)
class NativeJoint:
    name: str
    parent: str
    child: str
    point_a: tuple
    point_b: tuple
    axis_a: tuple
    axis_b: tuple
    x_b: tuple
    angle_rad: float
    values_rad: tuple
    offset: float
    flip: bool
    limits_rad: tuple


@dataclass(frozen=True)
class CommandJoint:
    name: str
    parent: str
    child: str
    point: tuple
    axis: tuple
    limits_deg: tuple


def native_document(raw, f):
    need(len(raw) <= 8*1024*1024, 'ZIP exceeds8MiB')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [x for x in archive.infolist() if x.filename == 'document.json']
        need(len(entries) == 1, 'Exactly one root document.json required')
        info = entries[0]
        need(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'Unsupported ZIP encryption/compression')
        need(info.file_size <= 1024*1024, 'Native document exceeds1MiB')
        with archive.open(info) as stream:
            document = stream.read(1024*1024+1)
    return f.obj(f.parse(document), 'native')


def decode_native(raw, f):
    data = native_document(raw, f)
    get = f.field
    need(get(data, 'format', 'native') == 'solidcraft/31', 'Unsupported native format')
    need(get(data, 'units', 'native') == 'mm', 'Native units must be mm')
    names = {'Base'} | {f'Link{i}' for i in range(1, 7)}
    components, seen = {}, set()
    for i, row in enumerate(f.array(get(data, 'components', 'native'), 7, 'components')):
        path = f'components[{i}]'
        identity = identifier(get(row, 'id', path), path+'.id')
        name = text(get(row, 'name', path), path+'.name')
        root_parent(get(row, 'parent', path), path+'.parent')
        need(identity not in components and name not in seen and name in names, 'Component identity/name')
        components[identity], seen = name, seen | {name}
    occurrences, occ_names = {}, set()
    identity4 = ((1., 0., 0., 0.), (0., 1., 0., 0.), (0., 0., 1., 0.), (0., 0., 0., 1.))
    for i, row in enumerate(f.array(get(data, 'occurrences', 'native'), 7, 'occurrences')):
        path = f'occurrences[{i}]'
        identity = identifier(get(row, 'id', path), path+'.id')
        component = identifier(get(row, 'component', path), path+'.component')
        name = text(get(row, 'name', path), path+'.name')
        root_parent(get(row, 'parent', path), path+'.parent')
        grounded = get(row, 'grounded', path)
        transform = tuple(f.vector(x, 4, 1e6, path+f'.transform[{k}]') for k, x in
                          enumerate(f.array(get(row, 'transform', path), 4, path+'.transform')))
        need(transform == identity4, 'Only identity occurrence transforms supported')
        need(component in components and name == components[component]+':1', 'Occurrence/component reference')
        need(type(grounded) is bool and grounded == (components[component] == 'Base'), 'Grounded base policy')
        need(identity not in occurrences and identity not in components and name not in occ_names, 'Occurrence identity/name')
        occurrences[identity], occ_names = name, occ_names | {name}
    rows = f.array(get(get(data, 'assembly', 'native'), 'joints', 'assembly'), 6, 'assembly.joints')
    joints, ids = {}, set(components) | set(occurrences)
    for i, row in enumerate(rows):
        path = f'joints[{i}]'
        identity = identifier(get(row, 'id', path), path+'.id')
        name = text(get(row, 'name', path), path+'.name')
        need(identity not in ids and name not in joints, 'Joint identity/name')
        ids.add(identity)
        need(get(row, 'kind', path) == 'revolute', path+': expected revolute')
        a, b = get(row, 'a', path), get(row, 'b', path)
        a_id = identifier(get(a, 'occurrence', path+'.a'), path+'.a.occurrence')
        b_id = identifier(get(b, 'occurrence', path+'.b'), path+'.b.occurrence')
        need(a_id in occurrences and b_id in occurrences, 'Joint occurrence reference')
        sa, sb = get(a, 'snap', path+'.a'), get(b, 'snap', path+'.b')
        need(get(sa, 'type', path+'.a.snap') == 'point' and get(sb, 'type', path+'.b.snap') == 'frame', 'Unsupported snap kind')
        pa = f.vector(get(sa, 'point', path+'.a.snap'), 3, 1e6, path+'.a.point')
        pb = f.vector(get(sb, 'origin', path+'.b.snap'), 3, 1e6, path+'.b.origin')
        za = f.unit_axis(get(sa, 'z', path+'.a.snap'), path+'.a.z')
        zb = f.unit_axis(get(sb, 'z', path+'.b.snap'), path+'.b.z')
        xb = f.unit_axis(get(sb, 'x', path+'.b.snap'), path+'.b.x')
        need(abs(sum(x*z for x, z in zip(xb, zb))) <= AXIS_TOL, 'Invalid auxiliary snap x')
        flip = get(row, 'flip', path)
        need(type(flip) is bool, 'flip must be bool; native sign remains unknown')
        joints[name] = NativeJoint(name, occurrences[a_id], occurrences[b_id], pa, pb, za, zb, xb,
            f.number(get(row, 'angle', path), 1e6, path+'.angle'),
            f.vector(get(row, 'values', path), 1, 1e6, path+'.values'),
            f.number(get(row, 'offset', path), 1e6, path+'.offset'), flip,
            limits(get(row, 'limits', path), path+'.limits', f))
    need(set(joints) == {f'J{i}_DISPLAY_ZERO' for i in range(1, 7)}, 'Native joint names')
    return tuple(joints[f'J{i}_DISPLAY_ZERO'] for i in range(1, 7))


def decode_commands(raw, f):
    data = f.obj(f.parse(raw), 'commands')
    rows = sequence(f.field(data, 'commands', 'commands'), 'commands.commands')
    joints = {}
    for i, row in enumerate(rows):
        path = f'commands[{i}]'
        command = text(f.field(row, 'command', path), path+'.command')
        params = f.obj(f.field(row, 'params', path), path+'.params')
        if command != 'joint.as_built':
            continue
        name = text(f.field(params, 'name', path), path+'.name')
        need(name not in joints, 'Duplicate joint command')
        need(f.field(params, 'type', path) == 'revolute', 'Unsupported command joint kind')
        parent = text(f.field(params, 'a', path), path+'.a')
        child = text(f.field(params, 'b', path), path+'.b')
        at = f.field(params, 'at', path)
        joints[name] = CommandJoint(name, parent, child,
            f.vector(f.field(at, 'point', path+'.at'), 3, 1e6, path+'.at.point'),
            f.unit_axis(f.field(at, 'z', path+'.at'), path+'.at.z'),
            limits(f.field(params, 'limits', path), path+'.limits', f))
    need(set(joints) == {f'J{i}_DISPLAY_ZERO' for i in range(1, 7)}, 'Command joint names/count')
    return tuple(joints[f'J{i}_DISPLAY_ZERO'] for i in range(1, 7))


def compare(layout, natives, commands, f):
    poses = f.fk(layout, [0.]*6)
    rows, previous_mm = [], (0., 0., 0.)
    for joint, native, command, pose in zip(layout.joints, natives, commands, poses):
        need(native.parent == command.parent == joint.parent+':1' and
             native.child == command.child == joint.child+':1', joint.name+': topology mismatch')
        target = tuple(x*1000 for x in pose['origin_m'])
        point_error = max(abs(x-y) for point in (native.point_a, native.point_b, command.point)
                          for x, y in zip(point, target))
        need(point_error <= POINT_TOL_MM, joint.name+': origin mismatch')
        need(f.close(native.point_a, native.point_b, POINT_TOL_MM), joint.name+': snap origins differ')
        axis_error = max(abs(x-y) for axis in (native.axis_a, native.axis_b, command.axis)
                         for x, y in zip(axis, pose['axis_world']))
        need(axis_error <= AXIS_TOL, joint.name+': axis mismatch')
        local_axis = f.mv(f.transpose(joint.parent_rotation), native.axis_a)
        local_offset = f.mv(f.transpose(joint.parent_rotation),
                            tuple((x-y)/1000 for x, y in zip(native.point_a, previous_mm)))
        need(f.close(local_axis, joint.axis_parent, AXIS_TOL), joint.name+': local axis mismatch')
        need(f.close(local_offset, joint.offset_m, POINT_TOL_MM/1000), joint.name+': local offset mismatch')
        need(abs(native.angle_rad) <= ZERO_TOL_RAD and abs(native.values_rad[0]) <= ZERO_TOL_RAD
             and abs(native.offset) <= ZERO_TOL_RAD, joint.name+': stored zero mismatch')
        need(f.close(native.limits_rad, tuple(math.radians(x) for x in command.limits_deg), 1e-10),
             joint.name+': software limit unit mismatch')
        rows.append({'joint': joint.name, 'parent': joint.parent, 'child': joint.child,
            'native_origin_mm': native.point_a, 'native_axis_world': native.axis_a,
            'core_axis_parent': joint.axis_parent, 'core_offset_m': joint.offset_m,
            'origin_max_error_mm': point_error, 'axis_max_component_error': axis_error,
            'native_saved_angle_rad': native.angle_rad, 'native_saved_value_rad': native.values_rad[0],
            'native_saved_offset': native.offset, 'native_flip': native.flip,
            'canonical_delta_at_saved_zero_rad': 0.,
            'canonical_delta_at_geometric_zero_deg': -math.degrees(joint.pose_rad),
            'native_command_at_geometric_zero': None, 'native_positive_sign': None,
            'software_limits_rad_not_physical': native.limits_rad})
        previous_mm = native.point_a
    return {'status': 'STATIC_JOINT_METADATA_ALIGNED', 'joints': rows,
        'position_tolerance_mm': POINT_TOL_MM, 'axis_component_tolerance': AXIS_TOL,
        'scope': 'saved anchors/axes/zero labels only; identity world occurrences',
        'ring_geometry': 'DEFERRED_UNRESOLVED_020', 'native_solver_execution': 'NOT_RUN',
        'native_positive_angle_mapping': 'NOT_RUN', 'native_body_orientation_agreement': 'NOT_DERIVED',
        'physical_calibration': 'NOT_RUN', 'hardware_approved': False}


def table(report):
    lines = ['# v2 CAD 관절축·저장 영점 정적 대조', '',
        '저장된 원점·축·0각 표지만 대조했습니다. CAD solver/양의 회전부호·링 형상·실물은 미검증입니다.', '',
        '| 관절 | 원점 mm | 월드 축 | 저장각 rad | 기하0의 canonical delta deg |',
        '|---|---|---|---|---|']
    for row in report['joints']:
        point = ', '.join(f'{x:.6f}' for x in row['native_origin_mm'])
        axis = ', '.join(f'{x:.6f}' for x in row['native_axis_world'])
        lines.append(f"| {row['joint']} | {point} | {axis} | {row['native_saved_angle_rad']:g} | {row['canonical_delta_at_geometric_zero_deg']:g} |")
    lines += ['', '`native saved 0`은 현재 표시 자세와 대응하는 정적 기록입니다.',
              '마지막 열은 수학 코어 입력이며 CAD native 명령각이 아닙니다. 그 native 명령각은 미정입니다.',
              'snap의 보조 x는 링크의 R_child와 동일한 프레임이 아닙니다. 소프트웨어 limits는 실물 가동범위가 아닙니다.',
              '현재 사용 전 verify를 실행하십시오. 이 파일은 run 당시의 읽기용 스냅샷입니다.', '']
    return '\n'.join(lines).encode('utf-8')


def capture(root, f):
    dependency = admission(root, f)
    raw = {KIN: read(root/KIN), NATIVE: read(root/NATIVE, 8*1024*1024), COMMANDS: read(root/COMMANDS)}
    return raw, dependency


def verify(root):
    f = approved_core()
    out = root/OUTPUT
    current = f.obj(f.parse(read(out/'current.json')), 'current')
    need(f.field(current, 'status', 'current') == 'PASS', 'No current PASS; no fallback')
    run = f.field(current, 'run_id', 'current')
    need(type(run) is str and re.fullmatch('[0-9a-f]{32}', run) is not None, 'Invalid run ID')
    bundle = out/'runs'/run
    raw = read(bundle/'manifest.json')
    need(sha(raw) == f.field(current, 'manifest_sha256', 'current'), 'Manifest hash')
    manifest = f.obj(f.parse(raw), 'manifest')
    need(f.field(manifest, 'run_id', 'manifest') == run, 'Run identity')
    need(f.field(manifest, 'producer', 'manifest') == producer(), 'Producer changed')
    sources, dependency = capture(root, f)
    need(f.field(manifest, 'sources', 'manifest') == {p: sha(b) for p, b in sources.items()}, 'Source changed')
    need(f.field(manifest, 'dependency_021', 'manifest') == dependency, 'Dependency changed')
    files = f.obj(f.field(manifest, 'files', 'manifest'), 'manifest.files')
    need(set(files) == set(FILES), 'Artifact set')
    for name in FILES:
        need(sha(read(bundle/name, 8*1024*1024 if name.endswith('.solidcraft') else 1024*1024)) == files[name], 'Artifact hash: '+name)
    for path, name in ((KIN, 'kinematics.json'), (COMMANDS, 'commands.json'), (NATIVE, 'native.solidcraft')):
        need(files[name] == sha(sources[path]), 'Input snapshot identity')
    return {'status': 'PASS', 'run_id': run, 'scope': 'STATIC_JOINT_METADATA_ALIGNED'}


def build(root):
    out = root/OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    run, success = uuid.uuid4().hex, False
    current = out/'current.json'
    try:
        atomic(current, {'status': 'BUILDING', 'run_id': run})
        f = approved_core()
        sources, dependency = capture(root, f)
        own_producer = producer()
        layout = f.decode(sources[KIN])
        report = compare(layout, decode_native(sources[NATIVE], f), decode_commands(sources[COMMANDS], f), f)
        report['dependency_021'] = dependency
        payloads = {'native.solidcraft': sources[NATIVE], 'commands.json': sources[COMMANDS],
                    'kinematics.json': sources[KIN], 'report.json': encoded(report), 'report.md': table(report)}
        bundle = out/'runs'/run
        bundle.mkdir(parents=True, exist_ok=False)
        for name, raw in payloads.items():
            (bundle/name).write_bytes(raw)
        after, dep_after = capture(root, f)
        need(sources == after and dependency == dep_after and producer() == own_producer, 'Inputs/producer changed during build')
        manifest = encoded({'run_id': run, 'sources': {p: sha(b) for p, b in sources.items()},
            'dependency_021': dependency, 'producer': own_producer, 'files': {p: sha(b) for p, b in payloads.items()}})
        (bundle/'manifest.json').write_bytes(manifest)
        atomic(current, {'status': 'PASS', 'run_id': run, 'manifest_sha256': sha(manifest)})
        result = verify(root)
        success = True
        return result
    finally:
        if not success:
            error = sys.exc_info()[1]
            atomic(current, {'status': 'FAILED', 'run_id': run, 'reason': type(error).__name__ if error else 'IncompleteBuild'})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('build', 'verify'))
    cli.add_argument('--root', type=Path, default=ROOT)
    args = cli.parse_args()
    print(json.dumps((build if args.action == 'build' else verify)(args.root)))


if __name__ == '__main__':
    main()
