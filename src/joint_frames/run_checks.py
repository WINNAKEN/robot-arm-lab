"""Execute positive tests then compiled behavioral mutants; retain raw evidence."""
from pathlib import Path
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVIDENCE = ROOT/'.dev/joint-frames-evidence'


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('FRAMES_MODULE', None)
    tests = ['FramesTest.test_display_and_geometric', 'FramesTest.test_all_axis_derivatives',
             'FramesTest.test_transform_domain_closure']
    positive = subprocess.run([sys.executable, str(HERE/'test_frames.py'), *tests],
                              env=env, capture_output=True, text=True)
    (EVIDENCE/'positive-output.txt').write_text(positive.stdout+positive.stderr, encoding='utf-8')
    if positive.returncode:
        raise RuntimeError('Positive baseline failed; see positive-output.txt')
    source = (HERE/'frames.py').read_text(encoding='utf-8')
    cases = {
        'wrong_units': ('tuple(x/1000 for x in vector', 'tuple(x for x in vector'),
        'wrong_zero': ('q-j.pose_rad for q, j', 'q+j.pose_rad for q, j'),
        'wrong_frame_order': ('r = mm(r, mm(rotation(joint.axis_parent, q), joint.fixed_rotation))',
                              'r = mm(mm(rotation(joint.axis_parent, q), joint.fixed_rotation), r)'),
        'j6_sign': ('rotation(joint.axis_parent, q), joint.fixed_rotation',
                    "rotation(joint.axis_parent, -q if joint.name == 'J6' else q), joint.fixed_rotation"),
        'r1_domain_regression': ("6, sys.float_info.max, 'angles_rad'", "6, 1e6, 'angles_rad'"),
    }
    results = []
    mutant_dir = EVIDENCE/'mutants'
    mutant_dir.mkdir(exist_ok=True)
    for name, (before, after) in cases.items():
        if source.count(before) != 1:
            raise RuntimeError('Mutation target not unique: '+name)
        mutated = source.replace(before, after)
        compile(mutated, name, 'exec')
        path = mutant_dir/(name+'.py')
        path.write_text(mutated, encoding='utf-8')
        run = subprocess.run([sys.executable, str(HERE/'test_frames.py'), *tests],
            env=dict(env, FRAMES_MODULE=str(path)), capture_output=True, text=True)
        output = run.stdout+run.stderr
        (mutant_dir/(name+'-output.txt')).write_text(output, encoding='utf-8')
        caught = run.returncode == 1 and 'AssertionError' in output and '\nERROR:' not in output
        results.append({'name': name, 'exit': run.returncode, 'compiled': True, 'detected': caught})
        if not caught:
            raise RuntimeError('Mutation not behaviorally detected: '+name)
    (EVIDENCE/'author-checks.json').write_text(json.dumps({
        'positive_exit': positive.returncode, 'mutations': results}, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'positive_exit': 0, 'detected_mutations': len(results)}))


if __name__ == '__main__':
    main()
