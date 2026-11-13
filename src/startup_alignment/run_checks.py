"""Positive execution then compiled mutations of each supervisor boundary."""
from pathlib import Path
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parents[1]/'.dev/startup-boundary-evidence'


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('STARTUP_PARENT_MODULE', None)
    tests = ['StartupTest.test_first_dependency_read_observes_building',
             'StartupTest.test_original_missing_core_cli_and_recovery',
             'StartupTest.test_exit_nonzero_after_valid_bound_response']
    args = [sys.executable, str(HERE/'test_startup.py'), *tests]
    baseline = subprocess.run(args, env=env, capture_output=True, text=True)
    (EVIDENCE/'mutation-positive.txt').write_text(baseline.stdout+baseline.stderr, encoding='utf-8')
    if baseline.returncode:
        raise RuntimeError('Positive mutation baseline failed')
    source = (HERE/'runner.py').read_text(encoding='utf-8')
    first = "        atomic(current, {'status': 'BUILDING', 'run_id': None})\n"
    second = "        atomic(current, {'status': 'BUILDING', 'run_id': run})\n"
    worker_read = "        worker_raw = read(Path(__file__).with_name('worker.py'))\n"
    failed = ("            atomic(current, {'status': 'FAILED', 'run_id': run,\n"
              "                'reason': type(error).__name__ if error else 'IncompleteBuild', 'child_exit_code': child_exit,\n"
              "                'diagnostic_bundle': str(bundle) if bundle else None})")
    cases = {
        'late_building': [(first, ''), (second, ''), (worker_read, worker_read+first+second)],
        'missing_failed': [(failed, '            # FAILED publication intentionally removed by mutant')],
        'ignored_child_exit': [
            ("need(child_exit == 0, 'Worker failed; see preserved child-stderr.bin')", "need(True, 'child exit bypass')"),
            ("need(type(field(manifest, 'child_exit_code')) is int and manifest['child_exit_code'] == 0, 'Manifest child exit')",
             "need(True, 'manifest child exit bypass')")],
    }
    directory = EVIDENCE/'mutants'
    directory.mkdir(exist_ok=True)
    results = []
    for name, replacements in cases.items():
        code = source
        for before, after in replacements:
            if code.count(before) != 1:
                raise RuntimeError('Mutation target not unique: '+name)
            code = code.replace(before, after)
        compile(code, name, 'exec')
        path = directory/(name+'.py')
        path.write_text(code, encoding='utf-8')
        run = subprocess.run(args, env=dict(env, STARTUP_PARENT_MODULE=str(path)), capture_output=True, text=True)
        output = run.stdout+run.stderr
        (directory/(name+'-output.txt')).write_text(output, encoding='utf-8')
        caught = run.returncode == 1 and 'AssertionError' in output and '\nERROR:' not in output
        results.append({'name': name, 'compiled': True, 'exit': run.returncode,
                        'assertion_detected': caught, 'source_replacements': len(replacements)})
        if not caught:
            raise RuntimeError('Behavioral mutation survived or errored: '+name)
    (EVIDENCE/'mutation-results.json').write_text(json.dumps({'positive_exit': 0, 'mutants': results}, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'positive_exit': 0, 'detected_mutants': len(results)}))


if __name__ == '__main__':
    main()
