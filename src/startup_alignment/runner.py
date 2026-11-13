"""Stdlib supervisor. Valid absolute --root required; no repository I/O on import."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import uuid

CONTRACT_SHA = 'f429ec4a4b763e751358e498071b5248ef9d4c7572b844cbeb3e0087356e780d'
OUTPUT = 'outputs/supervised-alignment-v1'
TIMEOUT_S = 10
SCOPE = 'STATIC_JOINT_METADATA_ALIGNED'
BASE_FILES = {'worker.py', 'contract.json', 'report.json', 'report.md', 'response.json',
              'child-stdout.bin', 'child-stderr.bin'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, cap=1024*1024):
    with path.open('rb') as stream:
        raw = stream.read(cap+1)
    need(len(raw) <= cap, 'File exceeds bound: '+str(path))
    return raw


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def atomic(path, value):
    # One parent writer only. Marker writes never need UUID/OS randomness.
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_bytes(encoded(value))
    os.replace(temporary, path)


def parse(raw):
    need(len(raw) <= 1024*1024, 'JSON exceeds bound')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON constant: '+value)
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    stack = [(result, 0)]
    while stack:
        value, depth = stack.pop()
        need(depth <= 64, 'JSON exceeds depth64')
        if type(value) in (dict, list):
            stack.extend((x, depth+1) for x in (value.values() if type(value) is dict else value))
        elif type(value) is float:
            need(math.isfinite(value), 'Nonfinite JSON value')
    return result


def field(value, key):
    need(type(value) is dict and key in value, 'Missing object field: '+key)
    return value[key]


def number(value, bound):
    need(type(value) in (float, int) and -bound <= value <= bound, 'Numeric type/range')
    need(math.isfinite(float(value)), 'Nonfinite number')
    return float(value)


def expected_dependency(contract):
    return {'run_id': contract['accepted_run'], 'approval_sha256': contract['approval_sha256'],
            'receipt_sha256': contract['receipt_sha256'], 'core_sha256': contract['core_sha256']}


def load_contract():
    raw = read(Path(__file__).with_name('contract.json'))
    need(sha(raw) == CONTRACT_SHA, 'Unapproved supervisor contract')
    value = parse(raw)
    need(field(value, 'schema') == 1, 'Contract version')
    for path, cap in field(value, 'inputs').items():
        need(type(path) is str and not Path(path).is_absolute() and '..' not in Path(path).parts, 'Input path')
        need(type(cap) is int and 0 < cap <= 8*1024*1024, 'Input bound')
    return raw, value


def capture(root, contract):
    raw = {p: read(root/p, cap) for p, cap in contract['inputs'].items()}
    for path_key, sha_key in (('asset_path', 'asset_sha256'), ('core_path', 'core_sha256'),
                              ('approval_path', 'approval_sha256'), ('receipt_path', 'receipt_sha256')):
        need(sha(raw[contract[path_key]]) == contract[sha_key], 'Pinned dependency changed: '+path_key)
    approved = parse(raw[contract['approval_path']])
    need(type(approved) is list and len(approved) == 9, 'Approved021 manifest')
    for record in approved:
        need(sha(raw[field(record, 'path')]) == field(record, 'sha256').lower(), 'Accepted021 file changed')
    accepted_input = f"outputs/joint-frames-v1/runs/{contract['accepted_run']}/input.json"
    need(raw[contract['kin_path']] == raw[accepted_input], 'Unapproved021 source')
    return raw


def check_report(report, run, contract, expected_geometric):
    need(type(report) is dict and set(report) == {'status', 'joints', 'position_tolerance_mm',
        'axis_component_tolerance', 'scope', 'ring_geometry', 'native_solver_execution',
        'native_positive_angle_mapping', 'native_body_orientation_agreement', 'physical_calibration',
        'hardware_approved', 'dependency_021', 'supervised_run_id'}, 'Report fields')
    need(field(report, 'status') == SCOPE and field(report, 'supervised_run_id') == run, 'Report scope/run')
    need(field(report, 'scope') == 'saved anchors/axes/zero labels only; identity world occurrences', 'Report scope details')
    need(field(report, 'dependency_021') == expected_dependency(contract), 'Report dependency')
    need(field(report, 'hardware_approved') is False, 'No hardware approval')
    for key, value in (('ring_geometry', 'DEFERRED_UNRESOLVED_020'),
                       ('native_solver_execution', 'NOT_RUN'), ('native_positive_angle_mapping', 'NOT_RUN'),
                       ('native_body_orientation_agreement', 'NOT_DERIVED'), ('physical_calibration', 'NOT_RUN')):
        need(field(report, key) == value, 'Unsupported report claim: '+key)
    need(number(field(report, 'position_tolerance_mm'), 1) == 1e-5 and
         number(field(report, 'axis_component_tolerance'), 1) == 1e-8, 'Tolerance contract')
    joints = field(report, 'joints')
    need(type(joints) is list and len(joints) == 6, 'Six report joints required')
    for i, row in enumerate(joints):
        need(type(row) is dict and set(row) == {'joint', 'parent', 'child', 'native_origin_mm',
            'native_axis_world', 'core_axis_parent', 'core_offset_m', 'origin_max_error_mm',
            'axis_max_component_error', 'native_saved_angle_rad', 'native_saved_value_rad',
            'native_saved_offset', 'native_flip', 'canonical_delta_at_saved_zero_rad',
            'canonical_delta_at_geometric_zero_deg', 'native_command_at_geometric_zero',
            'native_positive_sign', 'software_limits_rad_not_physical'}, 'Joint report fields')
        need(field(row, 'joint') == f'J{i+1}' and field(row, 'parent') == ('Base' if i == 0 else f'Link{i}')
             and field(row, 'child') == f'Link{i+1}', 'Report joint topology')
        for key, bound in (('origin_max_error_mm', 1e-5), ('axis_max_component_error', 1e-8)):
            need(number(field(row, key), bound) >= 0, 'Invalid report error')
        for key in ('native_saved_angle_rad', 'native_saved_value_rad', 'native_saved_offset'):
            number(field(row, key), 1e-10)
        need(number(field(row, 'canonical_delta_at_saved_zero_rad'), 1e-10) == 0, 'Saved zero')
        need(abs(number(field(row, 'canonical_delta_at_geometric_zero_deg'), 360)-expected_geometric[i]) <= 1e-10, 'Geometric conversion')
        for key in ('native_positive_sign', 'native_command_at_geometric_zero'):
            need(field(row, key) is None, 'Native runtime mapping not established')
        need(type(field(row, 'native_flip')) is bool, 'Flip type')
        for key in ('native_origin_mm', 'native_axis_world', 'core_axis_parent', 'core_offset_m'):
            vector = field(row, key)
            need(type(vector) is list and len(vector) == 3, 'Report vector shape')
            for value in vector:
                number(value, 1e6)
            if key in ('native_axis_world', 'core_axis_parent'):
                need(abs(sum(x*x for x in vector)-1) <= 1e-8, 'Unit report axis')
        bounds = field(row, 'software_limits_rad_not_physical')
        need(type(bounds) is list and len(bounds) == 2, 'Software limit shape')
        low, high = (number(x, 1e6) for x in bounds)
        need(low < high and low <= 0 <= high, 'Software limits')


def check_payload(bundle, run, contract, sources):
    response = parse(read(bundle/'response.json'))
    need(type(response) is dict and set(response) == {
        'run_id', 'status', 'scope', 'contract_sha256', 'sources', 'files', 'dependency_021'}, 'Response fields')
    need(response['run_id'] == run and response['status'] == 'OK' and response['scope'] == SCOPE, 'Response run/status')
    need(response['contract_sha256'] == CONTRACT_SHA, 'Response contract identity')
    need(response['sources'] == {p: sha(b) for p, b in sources.items()}, 'Response source identity')
    need(response['dependency_021'] == expected_dependency(contract), 'Response dependency identity')
    files = response['files']
    need(type(files) is dict and set(files) == {'report.json', 'report.md'}, 'Response artifact set')
    for name, digest in files.items():
        need(sha(read(bundle/name)) == digest, 'Response artifact hash')
    geometric = [-row['pose_deg'] for row in parse(sources[contract['kin_path']])['joints']]
    check_report(parse(read(bundle/'report.json')), run, contract, geometric)


def producer(contract_raw, worker_raw):
    return {'runner_sha256': sha(read(Path(__file__))), 'worker_sha256': sha(worker_raw),
            'contract_sha256': sha(contract_raw)}


def verify(root):
    # No core/asset imports, even when either is absent.
    out = root/OUTPUT
    current = parse(read(out/'current.json'))
    need(field(current, 'status') == 'PASS', 'No current PASS; no fallback')
    run = field(current, 'run_id')
    need(type(run) is str and re.fullmatch('[0-9a-f]{32}', run) is not None, 'Run ID')
    bundle = out/'runs'/run
    contract_raw, contract = load_contract()
    worker_raw = read(Path(__file__).with_name('worker.py'))
    need(sha(worker_raw) == contract['worker_sha256'], 'Worker pin')
    manifest_raw = read(bundle/'manifest.json')
    need(sha(manifest_raw) == field(current, 'manifest_sha256'), 'Manifest hash')
    manifest = parse(manifest_raw)
    need(field(manifest, 'run_id') == run and field(manifest, 'producer') == producer(contract_raw, worker_raw), 'Manifest run/producer')
    need(type(field(manifest, 'child_exit_code')) is int and manifest['child_exit_code'] == 0, 'Manifest child exit')
    sources = capture(root, contract)
    need(field(manifest, 'sources') == {p: sha(b) for p, b in sources.items()}, 'Current source identity')
    files = field(manifest, 'files')
    need(type(files) is dict and set(files) == BASE_FILES | {'inputs/'+p for p in sources}, 'Manifest file set')
    for name, digest in files.items():
        need(sha(read(bundle/name, 8*1024*1024)) == digest, 'Bundle artifact hash: '+name)
    need(files['worker.py'] == sha(worker_raw) and files['contract.json'] == sha(contract_raw), 'Executable snapshot identity')
    for path, raw in sources.items():
        need(files['inputs/'+path] == sha(raw), 'Input snapshot identity')
    check_payload(bundle, run, contract, sources)
    return {'status': 'PASS', 'run_id': run, 'scope': SCOPE}


def build(root):
    out = root/OUTPUT
    current = out/'current.json'
    success, run, child_exit, bundle = False, None, None, None
    try:
        out.mkdir(parents=True, exist_ok=True)
        atomic(current, {'status': 'BUILDING', 'run_id': None})
        run = uuid.uuid4().hex
        atomic(current, {'status': 'BUILDING', 'run_id': run})
        contract_raw, contract = load_contract()
        worker_raw = read(Path(__file__).with_name('worker.py'))
        need(sha(worker_raw) == contract['worker_sha256'], 'Unapproved worker')
        before_producer = producer(contract_raw, worker_raw)
        bundle = out/'runs'/run
        bundle.mkdir(parents=True, exist_ok=False)
        (bundle/'worker.py').write_bytes(worker_raw)
        (bundle/'contract.json').write_bytes(contract_raw)
        command = [sys.executable, '-I', '-B', str(bundle/'worker.py'), '--root', str(root),
                   '--bundle', str(bundle), '--contract', str(bundle/'contract.json')]
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            child = subprocess.run(command, capture_output=True, timeout=TIMEOUT_S, creationflags=flags)
        except subprocess.TimeoutExpired as exc:
            (bundle/'child-stdout.bin').write_bytes(exc.stdout or b'')
            (bundle/'child-stderr.bin').write_bytes(exc.stderr or b'')
            raise
        child_exit = child.returncode
        (bundle/'child-stdout.bin').write_bytes(child.stdout)
        (bundle/'child-stderr.bin').write_bytes(child.stderr)
        need(child_exit == 0, 'Worker failed; see preserved child-stderr.bin')
        sources = capture(root, contract)
        check_payload(bundle, run, contract, sources)
        for path, raw in sources.items():
            target = bundle/'inputs'/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        need(sources == capture(root, contract), 'Source changed during snapshot')
        need(producer(*load_inputs()) == before_producer, 'Supervisor source changed during build')
        names = BASE_FILES | {'inputs/'+p for p in sources}
        manifest = encoded({'run_id': run, 'producer': before_producer, 'child_exit_code': child_exit,
            'sources': {p: sha(b) for p, b in sources.items()},
            'files': {name: sha(read(bundle/name, 8*1024*1024)) for name in sorted(names)}})
        (bundle/'manifest.json').write_bytes(manifest)
        atomic(current, {'status': 'PASS', 'run_id': run, 'manifest_sha256': sha(manifest)})
        result = verify(root)
        success = True
        return result
    finally:
        if not success:
            error = sys.exc_info()[1]
            atomic(current, {'status': 'FAILED', 'run_id': run,
                'reason': type(error).__name__ if error else 'IncompleteBuild', 'child_exit_code': child_exit,
                'diagnostic_bundle': str(bundle) if bundle else None})


def load_inputs():
    raw, contract = load_contract()
    worker_raw = read(Path(__file__).with_name('worker.py'))
    need(sha(worker_raw) == contract['worker_sha256'], 'Worker changed')
    return raw, worker_raw


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('build', 'verify'))
    cli.add_argument('--root', type=Path, required=True)
    args = cli.parse_args(argv)
    if not args.root.is_absolute():
        cli.error('--root must be absolute')
    print(json.dumps((build if args.action == 'build' else verify)(args.root)))


if __name__ == '__main__':
    main()
