"""Offline native placement experiment. No repository reads during module import."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import uuid

OUTPUT = 'outputs/native-direction-v1'
MODEL = 'models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft'
KIN = 'models/armold-mks-concept-v1/kinematics.json'
CORE = 'src/joint_frames/frames.py'
CLI_SHA = 'fa17c35d53443c5bd91dfe6cf648d46aa8151869d2259948ae2f101098340538'
PINS = {
    MODEL: 'c784ee45bdbbba0b62eaa1218ebaba6b276d8f259c31baed8110174b96f84bc1',
    KIN: 'fe000e47a3885566a9ca808b053f429e13272da97a8dac132cb44b6153eeae50',
    CORE: '1eb5d41f439e5201ce0b0c5ee53222584082b8446bfef2e00a5bdd3eed5b4d46',
    '.dev/joint-frames-evidence/frozen-r2-manifest.json': '43d1153d75917a96e8ded6f313e4314846766f8cbb67f818670b095c41ff8422',
    '.dev/joint-frames-evidence/l4-r2.md': 'fdd4030257d77b51e9077d1e8cbd1425dd036a70f9ffa4be13ae96e3ba5f5138',
    'src/startup_alignment/runner.py': '2665de5f80a2b484d05fd0f4abc6febd39be4452e3e093b83078cdc07db4a8b4',
    'src/startup_alignment/worker.py': '00bfbf56e4048175b501946b5604b9abcbfeea856ec116a34f65977940ae642f',
    'src/startup_alignment/contract.json': 'f429ec4a4b763e751358e498071b5248ef9d4c7572b844cbeb3e0087356e780d',
    '.dev/startup-boundary-evidence/l4-r1.md': '491179331bc003c804d1fa899ec4147cfa32f760f9df1794a9f39b99c37ea3b1',
}
ROT_TOL = 1e-7
POS_TOL_MM = 1e-4
TIMEOUT = 60
I4 = [[float(i == j) for j in range(4)] for i in range(4)]


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, cap=16*1024*1024):
    with path.open('rb') as stream:
        raw = stream.read(cap+1)
    need(len(raw) <= cap, 'oversized input: '+str(path))
    return raw


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    stack = [(value, 0)]
    while stack:
        node, depth = stack.pop()
        need(depth <= 128, 'JSON nesting bound')
        if type(node) in (dict, list):
            stack.extend((v, depth+1) for v in (node.values() if type(node) is dict else node))
        elif type(node) is float:
            need(math.isfinite(node), 'nonfinite JSON')
    return value


def atomic(path, value):
    temp = path.with_name(path.name+'.tmp')
    temp.write_bytes(encoded(value))
    os.replace(temp, path)


def finite(x):
    return type(x) in (int, float) and math.isfinite(x) and abs(x) <= 1e7


def vector(x, n):
    need(type(x) is list and len(x) == n and all(finite(v) for v in x), 'bad vector')
    return x


def rigid(x):
    need(type(x) is list and len(x) == 4, 'bad matrix')
    for row in x:
        vector(row, 4)
    need(max(abs(x[3][j]-(j == 3)) for j in range(4)) <= 1e-10, 'bad homogeneous row')
    for i in range(3):
        for j in range(3):
            need(abs(sum(x[k][i]*x[k][j] for k in range(3))-(i == j)) < 1e-8, 'nonrigid matrix')
    det = sum(x[0][i]*(x[1][(i+1)%3]*x[2][(i+2)%3]-x[1][(i+2)%3]*x[2][(i+1)%3]) for i in range(3))
    need(abs(det-1) < 1e-8, 'improper rotation')
    return x


def compare(actual, expected):
    rigid(actual)
    rigid(expected)
    rotation = max(abs(actual[i][j]-expected[i][j]) for i in range(3) for j in range(3))
    position = max(abs(actual[i][3]-expected[i][3]) for i in range(3))
    return {'rotation_component_error': rotation, 'position_component_error_mm': position,
            'matches': rotation <= ROT_TOL and position <= POS_TOL_MM}


def predict(core, layout, degrees):
    zero = core.fk(layout, [0.]*6)
    pose = core.fk(layout, [math.radians(q) for q in degrees])
    result = {'Base:1': I4}
    for i, (base, now) in enumerate(zip(zero, pose), 1):
        a, b = now['rotation_world'], base['rotation_world']
        rotation = [[sum(a[j][k]*b[l][k] for k in range(3)) for l in range(3)] for j in range(3)]
        t = [1000*(now['origin_m'][j]-sum(rotation[j][k]*base['origin_m'][k] for k in range(3))) for j in range(3)]
        result[f'Link{i}:1'] = [rotation[j]+[t[j]] for j in range(3)]+[[0., 0., 0., 1.]]
    return result


def state(results, degrees):
    """Validate actual CLI observations independently of any FK direction hypothesis."""
    need(type(results) is list and len(results) == 3, 'expected three observation results')
    components, inspection, listing = results
    roots = [c for c in components['components'] if c['id'] == 0]
    need(len(roots) == 1 and not components['pending_moves'], 'root/pending placement')
    children = roots[0]['children']
    names = ['Base:1']+[f'Link{i}:1' for i in range(1, 7)]
    need(len(children) == 7 and sorted(c['name'] for c in children) == sorted(names), 'occurrence set')
    byname = {c['name']: c for c in children}
    # component.list serializes nalgebra column arrays, unlike occurrence.move's
    # documented row-major input. Cross-check below against native world frames.
    transforms = {name: [list(row) for row in zip(*child['transform'])] for name, child in byname.items()}
    need(len({c['id'] for c in children}) == 7, 'duplicate occurrence ID')
    for name, child in byname.items():
        need(child['parent'] == 0 and child['grounded'] == (name == 'Base:1'), 'grounding/parent')
        rigid(transforms[name])
    need(not listing['errors'] and not listing['conflicts'] and not listing['floating'] and not listing['links'], 'solver/list failure')
    need(set(listing['fixed']) == {0, byname['Base:1']['id']}, 'unexpected fixed occurrence')
    for collection in (inspection['joints'], listing['joints']):
        need(len(collection) == 6 and len({j['name'] for j in collection}) == 6, 'joint set')
        indexed = {j['name']: j for j in collection}
        for i, angle in enumerate(degrees, 1):
            joint = indexed[f'J{i}_DISPLAY_ZERO']
            need(joint['type'] == 'revolute' and joint['suppressed'] is False and joint['flip'] is True, 'joint definition')
            need(finite(joint['offset']) and abs(joint['offset']) < 1e-10, 'joint offset')
            values = joint['values']
            need(len(values) == 1 and values[0]['unit'] == 'deg' and finite(values[0]['value']) and abs(values[0]['value']-angle) < 1e-8, 'actual degree mismatch/clamp')
            need(values[0]['limits'] == [-170, 170], 'unexpected CAD limits')
            endpoints = []
            for side, name in (('a', names[i-1]), ('b', names[i])):
                endpoint = joint[side]
                if type(endpoint) is dict:
                    need(endpoint['occurrence'] == byname[name]['id'] and endpoint['occurrence_name'] == name and endpoint['resolves'] is True, 'unresolved/wrong endpoint')
                    need(not joint['errors'] and not joint['conflicts'], 'joint inspection failure')
                    frame = endpoint['frame']
                    snap = endpoint['snap']
                    local_origin = vector(snap['point'] if snap['type'] == 'point' else snap['origin'], 3)
                    local_axis = vector(snap['z'], 3)
                    t = transforms[name]
                    measured = frame['origin']
                    for k in range(3):
                        need(abs(sum(t[k][j]*local_origin[j] for j in range(3))+t[k][3]-measured[k]) <= POS_TOL_MM,
                             'placement serialization disagrees with native world origin')
                        need(abs(sum(t[k][j]*local_axis[j] for j in range(3))-frame['z'][k]) <= ROT_TOL,
                             'placement serialization disagrees with native world axis')
                    if 'x' in snap:
                        local_x = vector(snap['x'], 3)
                        for k in range(3):
                            need(abs(sum(t[k][j]*local_x[j] for j in range(3))-frame['x'][k]) <= ROT_TOL,
                                 'placement serialization disagrees with native world x')
                else:
                    need(endpoint == byname[name]['id'], 'wrong chain')
                    frame = joint['frame_'+side]
                origin, axis = vector(frame['origin'], 3), vector(frame['z'], 3)
                need(abs(sum(v*v for v in axis)-1) < 1e-8, 'nonunit axis')
                endpoints.append((origin, axis))
            for a, b in zip(endpoints[0], endpoints[1]):
                need(max(abs(x-y) for x, y in zip(a, b)) <= POS_TOL_MM, 'native joint endpoints do not mate')
    return transforms


def observations():
    return [{'command': name, 'params': params} for name, params in (
        ('component.list', {'compact': False}), ('joint.inspect', {}), ('joint.list', {}))]


def drives(degrees):
    return [{'command': 'joint.drive', 'params': {'joint': f'J{i}_DISPLAY_ZERO', 'value': q}}
            for i, q in enumerate(degrees, 1)]


def commands_for(degrees):
    return observations()+drives(degrees)+[{'command': 'joint.solve', 'params': {}}]+observations()+drives([0.]*6)+[{'command': 'joint.solve', 'params': {}}]+observations()


def cases():
    result = [('zero', [0.]*6)]
    for i in range(6):
        for q in (5, -5, 30, -30):
            values = [0.]*6
            values[i] = q
            result.append((f'J{i+1}_{q:+d}', values))
    result.extend([('mixed_positive', [15, -20, 25, 10, -15, 20]),
                   ('mixed_negative', [-15, 20, -25, -10, 15, -20])])
    return result


def drive_results(results, target, previous):
    need(len(results) == 6, 'drive count')
    for i, (result, angle, old) in enumerate(zip(results, target, previous), 1):
        need(not result['errors'] and not result['conflicts'] and result.get('reason') is None
             and result.get('stopped_by_contact') is None and result.get('stopped_by_loop') is None, 'drive failure')
        need(type(result['moved']) is bool and (angle == old or result['moved']), 'drive did not move')
        values = result['values']
        need(len(values) == 1 and finite(values[0]['value']) and values[0]['unit'] == 'deg'
             and abs(values[0]['value']-angle) < 1e-8, f'J{i} drive clamped/wrong unit')


def check_pose(raw, degrees, core, layout):
    need(type(raw) is list and len(raw) == 23, 'case response count')
    initial = state(raw[:3], [0.]*6)
    for transform in initial.values():
        need(compare(transform, I4)['matches'], 'nonidentity saved placement')
    drive_results(raw[3:9], degrees, [0.]*6)
    need(not raw[9]['errors'] and not raw[9]['conflicts'], 'solve failure')
    actual = state(raw[10:13], degrees)
    drive_results(raw[13:19], [0.]*6, degrees)
    need(not raw[19]['errors'] and not raw[19]['conflicts'], 'return solve failure')
    returned = state(raw[20:23], [0.]*6)
    for transform in returned.values():
        need(compare(transform, I4)['matches'], 'return to zero failed')
    direct = predict(core, layout, degrees)
    opposite = predict(core, layout, [-v for v in degrees])
    return {'degrees': degrees, 'official_plus_one': {n: compare(t, direct[n]) for n, t in actual.items()},
            'diagnostic_all_signs_reversed_NOT_ADOPTED': {n: compare(t, opposite[n]) for n, t in actual.items()},
            'return_to_zero': True}


def execute(argv, bundle, label, timeout=TIMEOUT):
    try:
        proc = subprocess.run([str(a) for a in argv], cwd=bundle, capture_output=True, timeout=timeout,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired as exc:
        (bundle/(label+'-stdout.bin')).write_bytes(exc.stdout or b'')
        (bundle/(label+'-stderr.bin')).write_bytes(exc.stderr or b'')
        raise
    (bundle/(label+'-stdout.bin')).write_bytes(proc.stdout)
    (bundle/(label+'-stderr.bin')).write_bytes(proc.stderr)
    (bundle/(label+'-exit.json')).write_bytes(encoded({'exit_code': proc.returncode}))
    need(proc.returncode == 0, label+': child nonzero '+str(proc.returncode))
    return proc.stdout


def capture(root):
    sources = {p: read(root/p) for p in PINS}
    for path, raw in sources.items():
        need(sha(raw) == PINS[path], 'unapproved source '+path)
    return sources


def load_core(root, raw):
    spec = importlib.util.spec_from_file_location('nd_approved_core', root/CORE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(raw, str(root/CORE), 'exec'), module.__dict__)
    return module


def build(root, cli):
    out, run, bundle, success = root/OUTPUT, None, None, False
    reason = 'unfinished'
    try:
        out.mkdir(parents=True, exist_ok=True)
        atomic(out/'current.json', {'status': 'BUILDING', 'run_id': None})
        run = uuid.uuid4().hex
        atomic(out/'current.json', {'status': 'BUILDING', 'run_id': run})
        bundle = out/'runs'/run
        bundle.mkdir(parents=True, exist_ok=False)
        sources = capture(root)
        need(sha(read(cli, 256*1024*1024)) == CLI_SHA, 'unapproved CLI binary')
        producer = read(Path(__file__))
        (bundle/'producer.py').write_bytes(producer)
        for path, raw in sources.items():
            dest = bundle/'inputs'/path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        version = execute([cli, '--version'], bundle, 'version').decode('utf-8').strip()
        need(version == 'solidcraft-cli 0.20.0', 'unexpected CLI version')
        admission = parse(execute([sys.executable, '-I', '-B', root/'src/startup_alignment/runner.py', 'verify', '--root', root], bundle, 'admission'))
        need(admission == {'status': 'PASS', 'run_id': 'fb368d55ae10444fa3650641d37280cf', 'scope': 'STATIC_JOINT_METADATA_ALIGNED'}, 'unaccepted static baseline')
        core = load_core(root, sources[CORE])
        layout = core.decode(sources[KIN])
        results = []
        for index, (name, degrees) in enumerate(cases()):
            label = f'case-{index:02d}'
            commands = commands_for(degrees)
            script, response = bundle/(label+'-commands.json'), bundle/(label+'-response.json')
            script.write_bytes(encoded({'commands': commands}))
            execute([cli, 'run', script, '--in', bundle/'inputs'/MODEL, '--results', '--quiet', '--json-out', response], bundle, label)
            result = check_pose(parse(read(response)), degrees, core, layout)
            results.append({'name': name, **result})
        need(capture(root) == sources and sha(read(cli, 256*1024*1024)) == CLI_SHA
             and read(Path(__file__)) == producer, 'inputs/producer changed during measurement')
        matches = all(row['matches'] for case in results for row in case['official_plus_one'].values())
        diagnostic = all(row['matches'] for case in results for row in case['diagnostic_all_signs_reversed_NOT_ADOPTED'].values())
        report = {'schema': 1, 'run_id': run, 'status': 'ALIGNED' if matches else 'BLOCK_DIRECTION_MISMATCH',
                  'scope': 'OFFLINE_NATIVE_PLACEMENT_OBSERVATION', 'cli_version': version, 'cli_sha256': CLI_SHA,
                  'inputs': PINS, 'tolerances': {'rotation_component': ROT_TOL, 'position_component_mm': POS_TOL_MM},
                  'official_plus_one_matches': matches, 'all_signs_reversed_diagnostic_matches': diagnostic,
                  'mapping_adopted': False, 'hardware_approved': False, 'ring_geometry': 'DEFERRED_UNRESOLVED_020', 'cases': results}
        (bundle/'report.json').write_bytes(encoded(report))
        lines = ['# CAD 실제 회전 방향 측정', '', f'판정: {report["status"]}. 실제 CLI: {version}.',
                 '', 'CAD 각도는 저장 표시0 기준. 공식 core +1 대조이며 -1 열은 채택하지 않은 진단 가설이다.',
                 '링/형상/접촉/모터 방향/물리 한계/Isaac 수용을 뜻하지 않는다.', '',
                 '| 자세 | core +1 | 전체 -1 가설 | 0 복귀 |', '|---|---|---|---|']
        for result in results:
            direct = all(v['matches'] for v in result['official_plus_one'].values())
            reverse = all(v['matches'] for v in result['diagnostic_all_signs_reversed_NOT_ADOPTED'].values())
            lines.append(f'| {result["name"]} | {direct} | {reverse} | True |')
        (bundle/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        files = {str(p.relative_to(bundle)).replace('\\', '/'): sha(read(p, 256*1024*1024)) for p in bundle.rglob('*') if p.is_file()}
        manifest = encoded({'run_id': run, 'producer_sha256': sha(producer), 'sources': PINS, 'cli_sha256': CLI_SHA, 'files': files})
        (bundle/'manifest.json').write_bytes(manifest)
        if not matches:
            reason = 'NativeDirectionMismatch'
            raise ValueError(reason)
        atomic(out/'current.json', {'status': 'PASS', 'run_id': run, 'manifest_sha256': sha(manifest)})
        verify(root, cli)
        success = True
        return report
    except BaseException as exc:
        if reason != 'NativeDirectionMismatch':
            reason = type(exc).__name__+': '+str(exc)[:300]
        raise
    finally:
        if not success:
            atomic(out/'current.json', {'status': 'FAILED', 'run_id': run, 'reason': reason,
                                       'report_path': str(bundle/'report.json') if bundle else None})


def verify(root, cli):
    current = parse(read(root/OUTPUT/'current.json'))
    need(current['status'] == 'PASS', 'current is not aligned PASS; explicit new measurement required')
    run = current['run_id']
    need(type(run) is str and len(run) == 32 and all(c in '0123456789abcdef' for c in run), 'invalid run')
    bundle = root/OUTPUT/'runs'/run
    manifest_raw = read(bundle/'manifest.json')
    need(sha(manifest_raw) == current['manifest_sha256'], 'manifest changed')
    manifest = parse(manifest_raw)
    need(manifest['run_id'] == run and manifest['sources'] == PINS and manifest['cli_sha256'] == CLI_SHA, 'wrong manifest identity')
    sources = capture(root)
    admission = subprocess.run([sys.executable, '-I', '-B', str(root/'src/startup_alignment/runner.py'), 'verify', '--root', str(root)],
                               capture_output=True, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    need(admission.returncode == 0 and parse(admission.stdout) == {
        'status': 'PASS', 'run_id': 'fb368d55ae10444fa3650641d37280cf', 'scope': 'STATIC_JOINT_METADATA_ALIGNED'}, 'dependency no longer admitted')
    need(sha(read(Path(__file__))) == manifest['producer_sha256'] and sha(read(cli, 256*1024*1024)) == CLI_SHA, 'producer/CLI drift')
    actual_files = {str(p.relative_to(bundle)).replace('\\', '/') for p in bundle.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    need(actual_files == set(manifest['files']), 'bundle membership drift')
    for path, digest in manifest['files'].items():
        need(path in actual_files and sha(read(bundle/path, 256*1024*1024)) == digest, 'bundle changed')
    expected_files = {'producer.py', 'report.json', 'report.md'} | {'inputs/'+p for p in PINS}
    for label in ['version', 'admission']+[f'case-{i:02d}' for i in range(len(cases()))]:
        expected_files.update(label+suffix for suffix in ('-stdout.bin', '-stderr.bin', '-exit.json'))
        need(parse(read(bundle/(label+'-exit.json'))) == {'exit_code': 0}, 'nonzero child evidence')
    for index in range(len(cases())):
        expected_files.update(f'case-{index:02d}'+suffix for suffix in ('-commands.json', '-response.json'))
    need(actual_files == expected_files, 'incomplete experiment evidence')
    for path, digest in PINS.items():
        need(sha(read(bundle/'inputs'/path)) == digest, 'snapshot approval mismatch')
    need(sha(read(bundle/'producer.py')) == manifest['producer_sha256'], 'producer snapshot mismatch')
    need(read(bundle/'version-stdout.bin').decode('utf-8').strip() == 'solidcraft-cli 0.20.0', 'wrong recorded CLI version')
    need(parse(read(bundle/'admission-stdout.bin')) == {'status': 'PASS', 'run_id': 'fb368d55ae10444fa3650641d37280cf',
                                                     'scope': 'STATIC_JOINT_METADATA_ALIGNED'}, 'wrong admission')
    report = parse(read(bundle/'report.json'))
    need(report['run_id'] == run and report['status'] == 'ALIGNED' and report['official_plus_one_matches'] is True
         and report['mapping_adopted'] is False and report['hardware_approved'] is False, 'not accepted direction evidence')
    core = load_core(root, read(root/CORE))
    layout = core.decode(read(root/KIN))
    rechecked = []
    for index, (name, degrees) in enumerate(cases()):
        need(parse(read(bundle/f'case-{index:02d}-commands.json')) == {'commands': commands_for(degrees)}, 'wrong experiment commands')
        case = check_pose(parse(read(bundle/f'case-{index:02d}-response.json')), degrees, core, layout)
        need(all(v['matches'] for v in case['official_plus_one'].values()), 'native direction mismatch')
        rechecked.append({'name': name, **case})
    reverse_matches = all(v['matches'] for case in rechecked for v in case['diagnostic_all_signs_reversed_NOT_ADOPTED'].values())
    need(report['cases'] == rechecked and report['inputs'] == PINS and report['cli_sha256'] == CLI_SHA
         and report['scope'] == 'OFFLINE_NATIVE_PLACEMENT_OBSERVATION' and report['schema'] == 1
         and report['cli_version'] == 'solidcraft-cli 0.20.0'
         and report['tolerances'] == {'rotation_component': ROT_TOL, 'position_component_mm': POS_TOL_MM}
         and report['all_signs_reversed_diagnostic_matches'] == reverse_matches
         and report['ring_geometry'] == 'DEFERRED_UNRESOLVED_020', 'report/replayed evidence mismatch')
    need(capture(root) == sources and sha(read(Path(__file__))) == manifest['producer_sha256']
         and sha(read(cli, 256*1024*1024)) == CLI_SHA, 'verify input drift')
    return {'status': 'PASS', 'run_id': run, 'scope': 'OFFLINE_NATIVE_PLACEMENT_OBSERVATION'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'verify'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--cli', type=Path, required=True)
    args = parser.parse_args()
    need(args.root.is_absolute() and args.cli.is_absolute(), 'absolute root and CLI required')
    value = build(args.root, args.cli) if args.action == 'build' else verify(args.root, args.cli)
    print(json.dumps({key: value[key] for key in ('status', 'run_id', 'scope')}, allow_nan=False))


if __name__ == '__main__':
    main()
