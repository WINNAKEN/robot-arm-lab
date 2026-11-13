"""041 one fresh remote Isaac import. Never plays physics or commands devices."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import traceback


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value, exclusive=False):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8', newline='\n') as file:
        json.dump(value, file, ensure_ascii=True, indent=2, allow_nan=False)
        file.write('\n')


def safe_child(root, relative):
    relative = Path(relative)
    need(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe relative payload path')
    path = (root / relative).resolve()
    need(path.is_relative_to(root), 'Payload escapes declared root')
    return path


def validate_inputs(run_dir):
    job = json.loads((run_dir / 'job.json').read_text(encoding='utf-8-sig'))
    need(type(job['run_id']) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', job['run_id']), 'Invalid run ID')
    need(Path(job['owned_runs_root']).is_absolute() and Path(job['expected_isaac_root']).is_absolute(), 'Explicit absolute approved roots required')
    owned_runs_root = Path(job['owned_runs_root']).resolve()
    isaac_root = Path(os.environ['ISAAC_PATH']).resolve()
    need(isaac_root == Path(job['expected_isaac_root']).resolve(), 'Installed runtime root differs from approved job')
    need(run_dir.parent == owned_runs_root and run_dir.name == job['run_id'], 'Unexpected owned run directory')
    need(Path(__file__).resolve().parent == run_dir, 'Runtime script must be inside its owned run')
    need(job['package_rel'] == 'input/robot-arm-urdf-v1', 'Unexpected package layout')
    package = safe_child(run_dir, job['package_rel'])
    manifest_path = package / 'manifest.json'
    need(sha(manifest_path) == job['package_manifest_sha256'], 'Transferred manifest mismatch')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    need(manifest['status'] == 'URDF_DRAFT_STATIC_VALIDATED' and manifest['isaac_import'] == 'NOT_RUN', 'Source draft identity')
    need(isinstance(manifest['files'], dict) and len(manifest['files']) == 38, 'Source payload inventory')
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    need(actual == set(manifest['files']), 'Transferred payload file-set mismatch')
    for name, expected in manifest['files'].items():
        need(sha(safe_child(package, name)) == expected, 'Transferred payload hash mismatch: ' + name)
    need(set(job['scripts_sha256']) == {'remote_import.py', 'extract_usd.py'}, 'Runtime script inventory')
    for name, expected in job['scripts_sha256'].items():
        need(sha(safe_child(run_dir, name)) == expected, 'Transferred runtime script hash mismatch: ' + name)
    version = (isaac_root / 'VERSION').read_text(encoding='utf-8-sig').strip()
    need(version == job['expected_isaac_version'], 'Installed Isaac version drift')
    return job, package, isaac_root, version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / 'status.json'
    # Exclusive creation prevents a second invocation from replacing old evidence.
    state = {'status': 'BUILDING', 'run_id': run_dir.name, 'pid': os.getpid(),
             'started_utc': datetime.now(timezone.utc).isoformat(), 'hardware_approved': False}
    write_json(status_path, state, exclusive=True)
    app, primary, primary_trace = None, None, None
    try:
        job, package, isaac_root, version = validate_inputs(run_dir)
        usd_directory = run_dir / 'usd'
        usd_directory.mkdir(exist_ok=False)
        runtime = {'isaac_version': version, 'python': sys.version, 'pid': os.getpid(),
                   'run_id': job['run_id'], 'argv': sys.argv[:], 'scripts_sha256': job['scripts_sha256'],
                   'package_manifest_sha256': job['package_manifest_sha256']}
        required_extensions = ('omni.scene.optimizer.core', 'isaacsim.robot.schema', 'isaacsim.asset.importer.urdf')
        local_extensions = {}
        for extension in required_extensions:
            candidates = []
            for base in (isaac_root / 'exts', isaac_root / 'extscache', isaac_root / 'kit/exts', isaac_root / 'kit/extscache'):
                if base.is_dir():
                    candidates.extend(p for p in base.iterdir() if p.is_dir() and
                                      (p.name == extension or p.name.startswith(extension + '-')) and
                                      (p / 'config/extension.toml').is_file())
            need(candidates, 'Required extension is not already installed locally: ' + extension)
            local_extensions[extension] = [str(p) for p in candidates]
        runtime['locally_installed_extensions'] = local_extensions
        for name, relative in {
            'importer_config_sha256': 'exts/isaacsim.asset.importer.urdf/pip_prebundle/isaacsim/asset/importer/urdf/impl/config.py',
            'importer_converter_sha256': 'exts/isaacsim.asset.importer.urdf/pip_prebundle/isaacsim/asset/importer/urdf/impl/converter.py',
            'importer_extension_sha256': 'exts/isaacsim.asset.importer.urdf/config/extension.toml',
        }.items():
            runtime[name] = sha(isaac_root / relative)
        state.update({'phase': 'SIMULATION_APP_START', 'runtime': runtime})
        write_json(status_path, state)

        from isaacsim import SimulationApp
        app = SimulationApp({'headless': True})
        import omni.kit.app
        import omni.timeline
        import omni.usd

        manager = omni.kit.app.get_app().get_extension_manager()
        for extension in required_extensions:
            need(manager.set_extension_enabled_immediate(extension, True) is not False, 'Extension unavailable: ' + extension)
        timeline = omni.timeline.get_timeline_interface()
        need(timeline.is_stopped(), 'Timeline must be stopped before import')
        state.update({'phase': 'IMPORTING', 'timeline_stopped_before': True})
        write_json(status_path, state)

        from isaacsim.asset.importer.urdf import URDFImporter, URDFImporterConfig
        settings = {
            'urdf_path': str(package / 'robot_arm.urdf'), 'usd_path': str(usd_directory),
            'merge_mesh': False, 'merge_fixed_joints': False, 'collision_from_visuals': False,
            'allow_self_collision': False, 'fix_base': True, 'link_density': None,
            'joint_drive_type': None, 'joint_target_type': None,
            'override_joint_stiffness': None, 'override_joint_damping': None,
            'run_asset_transformer': False, 'run_multi_physics_conversion': False,
        }
        write_json(run_dir / 'import-settings.json', settings, exclusive=True)
        result = URDFImporter(URDFImporterConfig(**settings)).import_urdf()
        need(isinstance(result, str) and result, 'Importer did not return an asset path')
        usd_path = Path(result).resolve()
        need(usd_path.is_relative_to(usd_directory.resolve()) and usd_path.is_file(), 'Importer output must be a saved owned USD')
        need(timeline.is_stopped(), 'Timeline changed during import')
        state.update({'phase': 'REOPENING_SAVED_USD', 'usd_path': str(usd_path), 'usd_sha256': sha(usd_path)})
        write_json(status_path, state)
        context = omni.usd.get_context()
        context.open_stage(str(usd_path))
        for _ in range(3):
            app.update()  # Kit loading/render update only, with timeline STOPPED.
            need(timeline.is_stopped(), 'Timeline changed during stage update')
        stage = context.get_stage()
        need(stage is not None, 'Saved USD did not open in active context')
        need(Path(stage.GetRootLayer().realPath).resolve() == usd_path, 'Active stage is not the saved importer result')
        from extract_usd import observe_stage
        snapshot = observe_stage(stage, usd_path, runtime, timeline.is_stopped())
        snapshot['import_settings'] = settings
        write_json(run_dir / 'snapshot.json', snapshot, exclusive=True)
        state.update({'phase': 'CLOSING_APP', 'snapshot_sha256': sha(run_dir / 'snapshot.json'),
                      'timeline_stopped_after': bool(timeline.is_stopped())})
        write_json(status_path, state)
    except Exception as exc:
        primary, primary_trace = exc, traceback.format_exc()
    finally:
        if app is not None:
            try:
                app.close()
            except Exception as close_error:
                if primary is None:
                    primary, primary_trace = close_error, traceback.format_exc()
                else:
                    state['app_close_error'] = repr(close_error)
        if primary is not None:
            state.update({'status': 'FAILED', 'reason': type(primary).__name__ + ': ' + str(primary)})
            write_json(status_path, state)
            (run_dir / 'failure-traceback.txt').write_text(primary_trace, encoding='utf-8')
    if primary is not None:
        raise primary
    state.update({'status': 'EXTRACTED', 'phase': 'APP_CLOSED', 'finished_utc': datetime.now(timezone.utc).isoformat(),
                  'dynamics_playback': 'NOT_RUN', 'rl_training': 'NOT_RUN', 'ring_geometry': 'DEFERRED'})
    write_json(status_path, state)
    print(json.dumps(state, ensure_ascii=True))


if __name__ == '__main__':
    main()
