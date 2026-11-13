"""Positive regression suite, then three independently compiled behavior mutants."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', ND_CLI=str(args.cli))
    env.pop('ND_MODULE', None)
    positive = subprocess.run([sys.executable, '-B', str(here/'test_direction.py')], env=env, capture_output=True, timeout=90)
    (args.evidence/'positive.txt').write_bytes(positive.stdout+positive.stderr)
    if positive.returncode:
        raise RuntimeError('positive suite failed; mutations not run')
    source = (here/'measure.py').read_text(encoding='utf-8')
    edits = [
        ('reverse_direction', 'math.radians(q) for q in degrees', 'math.radians(-q) for q in degrees', 'test_recorded_actual_cli_direction'),
        ('ignore_rotation', 'rotation <= ROT_TOL and position <= POS_TOL_MM', 'True and position <= POS_TOL_MM', 'test_rotation_guard'),
        ('ignore_translation', 'rotation <= ROT_TOL and position <= POS_TOL_MM', 'rotation <= ROT_TOL and True', 'test_translation_guard'),
    ]
    results = []
    for name, old, new, test in edits:
        if source.count(old) != 1:
            raise RuntimeError('mutation anchor count: '+name)
        changed = source.replace(old, new)
        path = args.evidence/(name+'.py')
        compile(changed, str(path), 'exec')
        path.write_text(changed, encoding='utf-8')
        proc = subprocess.run([sys.executable, '-B', str(here/'test_direction.py'), 'DirectionTests.'+test],
                              env=dict(env, ND_MODULE=str(path.resolve())), capture_output=True, timeout=60)
        raw = proc.stdout+proc.stderr
        (args.evidence/(name+'.txt')).write_bytes(raw)
        killed = proc.returncode == 1 and b'AssertionError' in raw and b'ERROR:' not in raw
        results.append({'name': name, 'compiled': True, 'exit': proc.returncode, 'assertion_killed': killed})
    (args.evidence/'mutations.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    if not all(row['assertion_killed'] for row in results):
        raise RuntimeError('mutation survived or test errored')
    print('Positive suite PASS; compiled behavioral mutants killed 3/3')


if __name__ == '__main__':
    main()
