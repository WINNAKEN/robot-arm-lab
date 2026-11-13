"""Compile and execute three guard-removal mutants after a positive baseline."""
from pathlib import Path
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parents[1]/'.dev/cad-alignment-evidence'


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    source = (HERE/'alignment.py').read_text(encoding='utf-8')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('ALIGNMENT_MODULE', None)
    args = [sys.executable, str(HERE/'test_alignment.py'),
            'AlignmentTest.test_each_joint_origin_axis_zero_and_topology']
    positive = subprocess.run(args, env=env, capture_output=True, text=True)
    (EVIDENCE/'mutation-positive.txt').write_text(positive.stdout+positive.stderr, encoding='utf-8')
    if positive.returncode != 0:
        raise RuntimeError('Positive baseline failed')
    cases = {
        'origin': [
            ('need(point_error <= POINT_TOL_MM,', 'need(True,'),
            ('need(f.close(local_offset, joint.offset_m, POINT_TOL_MM/1000),', 'need(True,')],
        'axis': [
            ('need(axis_error <= AXIS_TOL,', 'need(True,'),
            ('need(f.close(local_axis, joint.axis_parent, AXIS_TOL),', 'need(True,')],
        'stored_zero': [
            ('need(abs(native.angle_rad) <= ZERO_TOL_RAD and abs(native.values_rad[0]) <= ZERO_TOL_RAD\n'
             '             and abs(native.offset) <= ZERO_TOL_RAD,', 'need(True,')],
    }
    directory = EVIDENCE/'mutants'
    directory.mkdir(exist_ok=True)
    results = []
    for name, changes in cases.items():
        mutated = source
        for before, after in changes:
            if mutated.count(before) != 1:
                raise RuntimeError('Mutation target not unique: '+name)
            mutated = mutated.replace(before, after)
        compile(mutated, name, 'exec')
        path = directory/(name+'.py')
        path.write_text(mutated, encoding='utf-8')
        run = subprocess.run(args, env=dict(env, ALIGNMENT_MODULE=str(path)), capture_output=True, text=True)
        output = run.stdout+run.stderr
        (directory/(name+'-output.txt')).write_text(output, encoding='utf-8')
        caught = run.returncode == 1 and 'AssertionError' in output and '\nERROR:' not in output
        results.append({'name': name, 'compiled': True, 'exit': run.returncode,
                        'assertion_detected': caught, 'guard_removals': len(changes)})
        if not caught:
            raise RuntimeError('Mutant not caught by behavior: '+name)
    (EVIDENCE/'mutation-results.json').write_text(json.dumps({'positive_exit': 0, 'mutants': results}, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'positive_exit': 0, 'detected_mutants': len(results)}))


if __name__ == '__main__':
    main()
