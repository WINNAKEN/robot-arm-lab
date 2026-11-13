"""Run one owned Isaac child through the existing runtime; no shared configuration edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    run = parser.parse_args().run_dir.resolve()
    state = {'run_id': run.name, 'supervisor_pid': os.getpid(), 'status': 'STARTING', 'started_unix': time.time()}
    write(run/'supervisor.json', state)
    code, child = 1, None
    try:
        job = json.loads((run/'job.json').read_text(encoding='utf-8'))
        if run.parent != Path(job['owned_runs_root']).resolve() or run.name != job['run_id']:
            raise ValueError('Owned run identity mismatch')
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != job['supervisor_sha256']:
            raise ValueError('Supervisor source hash mismatch')
        isaac = Path(job['expected_isaac_root']).resolve()
        exe = isaac/'kit/python/kit.exe'
        if not exe.is_file():
            exe = isaac/'kit/python/python.exe'
        env = os.environ.copy()
        env['PYTHONEXE'] = str(exe)
        batch, script = isaac/'python.bat', run/'remote_import.py'
        # Approved configured roots contain no spaces or shell metacharacters.
        for path in (batch, script, run):
            if any(c.isspace() or c in '&|<>^\"' for c in str(path)):
                raise ValueError('Unsupported command path')
        argv = [env['COMSPEC'], '/d', '/c', str(batch), '-B', str(script), '--run-dir', str(run)]
        with (run/'runtime-stdout.txt').open('xb') as stdout, (run/'runtime-stderr.txt').open('xb') as stderr:
            child = subprocess.Popen(argv, cwd=isaac, env=env, stdout=stdout, stderr=stderr,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            write(run/'native-process.json', {'pid': child.pid, 'argv': argv, 'python_exe': str(exe), 'deadline_seconds': 600})
            state.update({'status': 'RUNNING', 'child_pid': child.pid})
            write(run/'supervisor.json', state)
            try:
                code = child.wait(timeout=600)
            except subprocess.TimeoutExpired:
                killed = subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                        capture_output=True, text=True, timeout=15)
                write(run/'timeout-cleanup.json', {'owned_pid': child.pid, 'exit': killed.returncode,
                                                  'stdout': killed.stdout, 'stderr': killed.stderr})
                child.wait(timeout=15)
                code = 124
    except Exception as exc:
        state['error'] = f'{type(exc).__name__}: {exc}'
        code = 1
    finally:
        state.update({'status': 'FINISHED', 'child_exit_code': code, 'finished_unix': time.time()})
        write(run/'supervisor.json', state)
        write(run/'exit.json', {'exit_code': int(code), 'run_id': run.name, 'supervisor_pid': os.getpid(),
                               'native_pid': child.pid if child else None, 'finished_unix': time.time()})
    print(json.dumps(state))


if __name__ == '__main__':
    main()
