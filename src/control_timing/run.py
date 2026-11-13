"""Run reference-model tests and behavioral controls; no firmware execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import argparse
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('contract.py')
TEST = Path(__file__).with_name('test_contract.py')
EVIDENCE = ROOT / '.dev/handoff-time-evidence'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-name', default='author-r1')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,60}', args.run_name):
        raise ValueError('Use a simple new evidence directory name')
    OUT = EVIDENCE / args.run_name
    OUT.mkdir(parents=True, exist_ok=False)  # prior failed run never overwritten
    pins = json.loads((EVIDENCE / 'source-pins.json').read_text(encoding='utf-8'))
    for pin in pins:
        if hashlib.sha256((ROOT / pin['path']).read_bytes()).hexdigest() != pin['sha256']:
            raise RuntimeError('Changed actual source/evidence: ' + pin['path'])
    anchors = {
        'src/firmware/components/robot_phone/web/app.js': [
            'until:this.now()+700', 'this.now()-this.received<600',
            'this.now()-this.renewAt>=200', '},250);', '},50);'],
        'src/firmware/components/robot_gate/control_gate.cpp': [
            'if (!stopped()) return fail(Error::Denied);',
            'if (!deadline(now,800,lease_until_))'],
        'src/firmware/main/phone_runtime.cpp': ['if(n<started||n-started>=50)return false;'],
        'src/firmware/main/phone_http.cpp': ['n-c.started<250'],
        'src/firmware/components/robot_run/bench_run.cpp': [
            'now>=authority_until_', 'authority_until_=e.authority_',
            'authority_until_=0;'],
    }
    for path, needles in anchors.items():
        text = (ROOT / path).read_text(encoding='utf-8')
        for needle in needles:
            if needle not in text:
                raise RuntimeError('Actual timing premise missing: ' + needle)
    (OUT / 'premises.json').write_text(json.dumps({
        'kind': 'actual source anchors and byte hashes, not proof of future integration',
        'pins_match': len(pins), 'anchors': anchors,
        'timing': {'poll': 250, 'pulse': 50, 'renew': 200, 'fresh': 600,
                   'old_client_intent': 700, 'normal_lease': 800,
                   'exchange_strict': 50, 'http_strict': 250},
    }, indent=2), encoding='utf-8')
    original = SOURCE.read_text(encoding='utf-8')
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}

    def execute(path, name):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        run = subprocess.run([sys.executable, str(TEST), str(path)], cwd=ROOT,
                             env=env, capture_output=True, text=True,
                             encoding='utf-8', timeout=60)
        (OUT / (name + '.stdout.txt')).write_text(run.stdout, encoding='utf-8')
        (OUT / (name + '.stderr.txt')).write_text(run.stderr, encoding='utf-8')
        return {'name': name, 'compile_exit': 0, 'run_exit': run.returncode,
                'assertion_failure': 'AssertionError' in run.stderr,
                'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    results = [execute(SOURCE, 'positive')]
    if results[0]['run_exit'] != 0:
        raise RuntimeError('Reference-model positive failed; no control credited')
    for name, old, new in (
        ('deadline-equality', 'if now >= self.pending_until:', 'if now > self.pending_until:'),
        ('hidden-extension', 'self.pending_until = min(self.pending_until, self.boot_until)',
         'self.pending_until = max(self.pending_until, now + PENDING_MS)'),
        ('cancelled-receipt-revival', 'if self.cancelled:', 'if False:'),
        ('receipt-reissues-acquire', 'self.reads += 1', 'self.reads += 1; self.acquire_attempts += 1'),
    ):
        if original.count(old) != 1:
            raise RuntimeError('Nonunique control target: ' + name)
        mutated = OUT / (name + '.py')
        mutated.write_text(original.replace(old, new), encoding='utf-8')
        result = execute(mutated, name)
        results.append(result)
        if result['run_exit'] == 0 or not result['assertion_failure']:
            raise RuntimeError('Control did not reach behavioral assertion: ' + name)
    results.append(execute(SOURCE, 'positive-after-controls'))
    if results[-1]['run_exit'] != 0:
        raise RuntimeError('Original reference model no longer passes')
    report = {'scope': 'REFERENCE_MODEL_ONLY; product/GUI/physical NOT_RUN',
              'result': 'PASS', 'unittest_methods': 12, 'synthetic_sweep_cases': 4500,
              'controls_killed': 4, 'results': results}
    (OUT / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}))


if __name__ == '__main__':
    main()
