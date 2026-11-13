"""Prepare a fresh, hashed remote Isaac job. Does not connect or launch anything."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import shutil
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[3]
PINNED_MANIFEST = 'd82f530e301a448c58248b5e5cb94580da610c247fddbc7f643b76836b626b4c'


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def prepare(root):
    root = Path(root).resolve()
    evidence = root/'.dev/isaac-import-evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    current = evidence/'current.json'
    write(current, {'status': 'BUILDING', 'hardware_approved': False})
    try:
        source = Path(__file__).parent
        config = json.loads((source/'remote_config.json').read_text(encoding='utf-8'))
        need(config['hardware_approved'] is False and config['timeline_play'] is False, 'Physical operation/play excluded')
        need(config['maximum_author_import_attempts'] == 2 and config['timeout_seconds'] == 600, 'Finite execution contract')
        package = root/'models/robot-arm-urdf-v1'
        need(sha(package/'manifest.json') == PINNED_MANIFEST, 'Pinned package manifest changed')
        manifest = json.loads((package/'manifest.json').read_text(encoding='utf-8'))
        for name, digest in manifest['files'].items():
            path = (package/name).resolve()
            need(path.is_relative_to(package) and sha(path) == digest, 'Package hash/path drift')
        run_id = uuid.uuid4().hex
        out = root/'outputs/isaac-import-v1/runs'/run_id
        out.mkdir(parents=True, exist_ok=False)
        bundle = out/'bundle'
        bundle.mkdir()
        shutil.copytree(package, bundle/'input/robot-arm-urdf-v1')
        scripts = {}
        for name in ('remote_import.py', 'extract_usd.py'):
            shutil.copyfile(source/name, bundle/name)
            scripts[name] = sha(bundle/name)
        shutil.copyfile(source/'supervise.py', bundle/'supervise.py')
        job = {'run_id': run_id, 'package_rel': 'input/robot-arm-urdf-v1',
            'package_manifest_sha256': PINNED_MANIFEST, 'scripts_sha256': scripts, 'supervisor_sha256': sha(bundle/'supervise.py'),
            'expected_isaac_version': config['expected_isaac_version'],
            'owned_runs_root': config['remote_runs_root'], 'expected_isaac_root': config['isaac_root'],
            'hardware_approved': False, 'timeline_play': False}
        write(bundle/'job.json', job)
        archive = out/'bundle.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(bundle.rglob('*')):
                if path.is_file():
                    z.write(path, path.relative_to(bundle).as_posix())
        prepared = {'status': 'PREPARED', 'run_id': run_id, 'bundle_zip': str(archive),
            'bundle_sha256': sha(archive), 'local_run_dir': str(out),
            'remote_run_dir': (PureWindowsPath(config['remote_runs_root'])/run_id).as_posix(),
            'config': config, 'job_sha256': sha(bundle/'job.json'), 'hardware_approved': False}
        write(out/'prepared.json', prepared)
        write(current, prepared)
        return prepared
    except Exception as exc:
        write(current, {'status': 'FAILED', 'reason': f'{type(exc).__name__}: {exc}', 'hardware_approved': False})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root)))
