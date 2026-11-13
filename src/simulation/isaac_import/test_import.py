"""Actual observation positive/semantic controls and isolated no-runtime startup failures."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from verify_import import compare, completion_gate, load_reference, sha, verify_run


def qmul(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return [w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j, w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v]


def masked_exit_host_control(run_copy, source):
    """Actual producer/consumer code with a host mock, never an Isaac execution."""
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        run_dir = root/'runs'/run_copy.name
        run_dir.mkdir(parents=True)
        job = json.loads((run_copy/'job.json').read_text())
        job['owned_runs_root'] = str(run_dir.parent)
        isaac = root/'mock-runtime'
        job['expected_isaac_root'] = str(isaac)
        isaac.mkdir()
        (isaac/'VERSION').write_text(job['expected_isaac_version'])
        for extension in ('omni.scene.optimizer.core', 'isaacsim.robot.schema', 'isaacsim.asset.importer.urdf'):
            path = isaac/'exts'/extension/'config/extension.toml'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# host mock only\n')
        impl = isaac/'exts/isaacsim.asset.importer.urdf/pip_prebundle/isaacsim/asset/importer/urdf/impl'
        impl.mkdir(parents=True)
        for name in ('config.py', 'converter.py'):
            (impl/name).write_text('# host mock only\n')
        shutil.copytree(run_copy/'input', run_dir/'input')
        for name in ('remote_import.py', 'extract_usd.py'):
            shutil.copyfile(source/name, run_dir/name)
        (run_dir/'job.json').write_text(json.dumps(job))
        modules = root/'mock-modules'
        (modules/'isaacsim').mkdir(parents=True)
        (modules/'isaacsim/__init__.py').write_text('import os\nclass SimulationApp:\n def __init__(self, config): pass\n def close(self): os._exit(0)\n')
        (modules/'omni').mkdir()
        (modules/'omni/__init__.py').write_text("raise RuntimeError('HOST_MOCK_AFTER_APP_CREATED')\n")
        env = os.environ.copy()
        env['ISAAC_PATH'], env['PYTHONPATH'] = str(isaac), str(modules)
        producer = subprocess.run([sys.executable, '-B', str(run_dir/'remote_import.py'), '--run-dir', str(run_dir)],
                                  env=env, capture_output=True, timeout=30)
        state = json.loads((run_dir/'status.json').read_text())
        if producer.returncode != 0 or state['status'] != 'BUILDING' or state['phase'] != 'SIMULATION_APP_START':
            raise AssertionError('Host mock did not reproduce real fast-close masked failure')
        # A valid older snapshot is deliberately present: it still must not pass.
        shutil.copyfile(run_copy/'snapshot.json', run_dir/'snapshot.json')
        (run_dir/'exit.json').write_text(json.dumps({'exit_code': producer.returncode, 'run_id': job['run_id']}))
        isolated = root/'src/simulation/isaac_import'
        isolated.mkdir(parents=True)
        shutil.copyfile(source/'verify_import.py', isolated/'verify_import.py')
        consumer = subprocess.run([sys.executable, '-B', str(isolated/'verify_import.py'), '--run-copy', str(run_dir),
                                  '--remote-run-dir', str(run_dir)], capture_output=True, timeout=30)
        terminal = json.loads((root/'.dev/isaac-import-evidence/current.json').read_text())
        if consumer.returncode == 0 or terminal['status'] != 'FAILED' or 'Incomplete runtime phase' not in terminal['reason']:
            raise AssertionError('Actual consumer accepted masked failure with stale valid snapshot')
        return {'producer_exit': 0, 'producer_raw_status': 'BUILDING', 'injected_phase': 'AFTER_APP_CREATED',
                'consumer_exit': consumer.returncode, 'central_status': terminal['status'], 'actual_isaac': 'NOT_RUN_HOST_MOCK'}


def public_provenance_controls(run_copy, remote_dir):
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp)/'copied-run'
        shutil.copytree(run_copy, out)
        original = {name: (out/name).read_bytes() for name in ('snapshot.json', 'status.json', 'job.json')}
        verify_run(out, remote_dir)
        decisions = []
        cases = [('runtime_manifest', 'Runtime package identity'), ('runtime_script', 'Runtime script identity'),
                 ('installed_importer', 'Runtime importer identity'), ('import_settings', 'Observed import settings'),
                 ('coherent_job_version', 'Executed job differs from original preparation')]
        for case, intended in cases:
            for name, raw in original.items():
                (out/name).write_bytes(raw)
            snapshot = json.loads(original['snapshot.json'])
            status = json.loads(original['status.json'])
            if case == 'runtime_manifest': snapshot['runtime']['package_manifest_sha256'] = '0'*64
            elif case == 'runtime_script': snapshot['runtime']['scripts_sha256']['remote_import.py'] = '0'*64
            elif case == 'installed_importer': snapshot['runtime']['importer_config_sha256'] = '0'*64
            elif case == 'import_settings': snapshot['import_settings']['fix_base'] = False
            elif case == 'coherent_job_version':
                job = json.loads(original['job.json'])
                job['expected_isaac_version'] = 'FALSE_VERSION'
                snapshot['runtime']['isaac_version'] = 'FALSE_VERSION'
                (out/'job.json').write_text(json.dumps(job), encoding='utf-8')
            status['runtime'] = copy.deepcopy(snapshot['runtime'])
            (out/'snapshot.json').write_text(json.dumps(snapshot), encoding='utf-8')
            status['snapshot_sha256'] = sha(out/'snapshot.json')
            (out/'status.json').write_text(json.dumps(status), encoding='utf-8')
            try:
                verify_run(out, remote_dir)
            except ValueError as exc:
                if intended not in str(exc):
                    raise AssertionError(f'{case}: wrong rejection {exc}') from exc
                decisions.append({'case': case, 'decision': 'REJECTED', 'reason': str(exc)})
            else:
                raise AssertionError('Public consumer accepted resealed provenance: '+case)
        for name, raw in original.items():
            (out/name).write_bytes(raw)
        verify_run(out, remote_dir)
        return {'original_before_after': 'PASS', 'correctly_resealed_copies': decisions}


def run(run_copy, remote_dir):
    reference = load_reference()
    actual = json.loads((run_copy/'snapshot.json').read_text(encoding='utf-8'))
    verify_run(run_copy, remote_dir)
    compare(actual, reference)
    def mass_unit(s):
        s['units']['kilograms_per_unit'] = .001
        s['units']['kilograms_per_unit_authored_value'] = .001
    def length_default(s):
        s['units'].update(meters_per_unit=.01, meters_per_unit_authored=False, meters_per_unit_authored_value=None)
    def pose(s):
        s['bodies'][2]['position'][0] += .01
    def anchor(s):
        next(j for j in s['joints'] if j['type'] == 'revolute')['local_pos0'][0] += .01
    def axis_sign(s):
        j = next(j for j in s['joints'] if j['type'] == 'revolute')
        perpendicular = 1 if j['axis'] == 'X' else 0
        flip = [0., 0., 0., 0.]
        flip[perpendicular+1] = 1.
        for key in ('local_rot0_wxyz', 'local_rot1_wxyz'):
            j[key] = qmul(j[key], flip)
    def mass(s):
        s['bodies'][2]['mass'] *= 2
    def inertia(s):
        s['bodies'][2]['inertia_diag'] = [x*2 for x in s['bodies'][2]['inertia_diag']]
    def missing_joint(s):
        s['joints'].remove(next(j for j in s['joints'] if j['type'] == 'revolute'))
    def duplicate_joint(s):
        s['joints'].append(copy.deepcopy(next(j for j in s['joints'] if j['type'] == 'revolute')))
    def reflection(s):
        s['bodies'][2]['rotation'] = [[-row[0], *row[1:]] for row in s['bodies'][2]['rotation']]
    def visual(s):
        s['bodies'][2]['visual_bounds']['max'][0] += .01
    def nonfinite(s):
        s['bodies'][2]['inertia_diag'][0] = float('nan')
    def fixed_anchor(s):
        next(j for j in s['joints'] if j['type'] == 'fixed')['local_pos0'][0] += .1
    def fixed_rotation(s):
        next(j for j in s['joints'] if j['type'] == 'fixed')['local_rot0_wxyz'] = [0., 1., 0., 0.]
    cases = [(mass_unit, 'Unsupported mass unit'), (length_default, 'Unsupported length unit'),
             (pose, 'CAD zero link pose'), (anchor, 'CAD joint anchor'),
             (axis_sign, 'CAD signed joint axis'), (mass, 'Assumed mass changed'),
             (inertia, 'Assumed inertia tensor'), (missing_joint, 'Six unique revolute'),
             (duplicate_joint, 'Six unique revolute'), (reflection, 'Proper rigid rotation'),
             (visual, 'CAD zero visual bounds'), (nonfinite, 'Finite vector'),
             (fixed_anchor, 'Fixed base anchor closure'), (fixed_rotation, 'Fixed base zero-frame closure')]
    observed = []
    for mutate, intended in cases:
        candidate = copy.deepcopy(actual)
        mutate(candidate)
        try:
            compare(candidate, reference)
        except ValueError as exc:
            if intended not in str(exc):
                raise AssertionError(f'{mutate.__name__}: wrong rejection {exc}') from exc
            observed.append({'case': mutate.__name__, 'decision': 'REJECTED', 'reason': str(exc)})
        else:
            raise AssertionError(f'{mutate.__name__}: semantic corruption accepted')
    equivalent = copy.deepcopy(actual)
    for b in equivalent['bodies']:
        b['principal_axes_wxyz'] = [-x for x in b['principal_axes_wxyz']]
    for j in equivalent['joints']:
        for key in ('local_rot0_wxyz', 'local_rot1_wxyz'):
            j[key] = [-x for x in j[key]]
    compare(equivalent, reference)
    coherent_fixed = copy.deepcopy(actual)
    fixed = next(j for j in coherent_fixed['joints'] if j['type'] == 'fixed')
    fixed['local_pos0'][0] += .025
    fixed['local_pos1'][0] += .025
    compare(coherent_fixed, reference)  # Same fixed constraint with a common anchor gauge.
    compare(actual, reference)
    status = json.loads((run_copy/'status.json').read_text())
    process = json.loads((run_copy/'exit.json').read_text())
    job = json.loads((run_copy/'job.json').read_text())
    completion_controls = []
    for case in ('early_phase_exit0', 'failed_status_exit0', 'bad_snapshot_hash', 'different_attempt', 'nonzero_process'):
        st, pr = copy.deepcopy(status), copy.deepcopy(process)
        if case == 'early_phase_exit0': st['phase'] = 'IMPORTING'
        elif case == 'failed_status_exit0': st['status'] = 'FAILED'
        elif case == 'bad_snapshot_hash': st['snapshot_sha256'] = '0'*64
        elif case == 'different_attempt': st['run_id'] = 'another'
        elif case == 'nonzero_process': pr['exit_code'] = 1
        try:
            completion_gate(st, pr, job, actual, sha(run_copy/'snapshot.json'))
        except ValueError as exc:
            completion_controls.append({'case': case, 'decision': 'REJECTED', 'reason': str(exc)})
        else:
            raise AssertionError('Invalid completion accepted: '+case)
    completion_gate(status, process, job, actual, sha(run_copy/'snapshot.json'))
    startup = []
    source = Path(__file__).parent
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        p = subprocess.run([sys.executable, '-B', str(source/'prepare.py'), '--root', str(root)], capture_output=True, timeout=30)
        status = json.loads((root/'.dev/isaac-import-evidence/current.json').read_text(encoding='utf-8'))
        if p.returncode == 0 or status['status'] != 'FAILED':
            raise AssertionError('Missing package did not produce FAILED/nonzero')
        startup.append('prepare missing package FAILED/nonzero')
        run_dir = root/'missing-job'
        p = subprocess.run([sys.executable, '-B', str(source/'remote_import.py'), '--run-dir', str(run_dir)], capture_output=True, timeout=30)
        status = json.loads((run_dir/'status.json').read_text(encoding='utf-8'))
        if p.returncode == 0 or status['status'] != 'FAILED' or (run_dir/'usd').exists():
            raise AssertionError('Missing job entered runtime or did not fail')
        startup.append('remote missing job FAILED/nonzero/no USD')
    masked = masked_exit_host_control(run_copy, source)
    provenance = public_provenance_controls(run_copy, remote_dir)
    return {'status': 'PASS', 'original_before_after': 'PASS', 'semantic_controls': observed,
            'equivalent_quaternion_sign': 'PASS', 'completion_controls': completion_controls, 'startup': startup,
            'masked_exit_host_pipeline': masked,
            'fixed_common_anchor_equivalence': 'PASS', 'public_provenance_controls': provenance,
            'scope': 'Copied actual observation semantics; no additional simulator import/play'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-copy', required=True, type=Path)
    parser.add_argument('--remote-run-dir', required=True)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.run_copy, args.remote_run_dir)
    args.report.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(result))
