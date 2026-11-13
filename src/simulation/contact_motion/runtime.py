"""043 gravity/contact simulation-only runner. No hardware, CAN, installation or shared service changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import uuid
import zipfile

USD_SHA = '117d94292c75e89b201e12606eafbcf24065c537c6f8308647562f9a0679f4db'
LINKS = ['Base'] + [f'Link{i}' for i in range(1, 7)]
JOINTS = [f'J{i}' for i in range(1, 7)]


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, exclusive=False):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


SOURCE_PATHS = {
    'runtime.py': 'src/simulation/contact_motion/runtime.py',
    'core.py': 'src/simulation/contact_motion/core.py',
    'motion_core.py': 'src/simulation/motion/core.py',
    'environment.py': 'src/simulation/contact_motion/environment.py',
    'program.json': 'src/simulation/motion/program.json',
    'config.json': 'src/simulation/contact_motion/remote_config.json',
    'extract_usd.py': 'src/simulation/isaac_import/extract_usd.py',
    'frames.py': 'src/joint_frames/frames.py',
    'kinematics.json': 'models/armold-mks-concept-v1/kinematics.json',
    'input.usda': 'outputs/isaac-import-v1/asset/robot-arm-v2.usda',
    'source-assumptions.json': 'outputs/isaac-import-v1/asset/source-assumptions.json',
    'reference.urdf': 'models/robot-arm-urdf-v1/robot_arm.urdf',
}

def prepare(root):
    root = Path(root).resolve()
    source = root/'src/simulation/contact_motion'
    cfg = json.loads((source/'remote_config.json').read_text(encoding='utf-8'))
    need(cfg['hardware_approved'] is False and cfg['maximum_author_attempts'] == 2 and
         cfg['timeout_seconds'] == 600, 'Simulation scope/budget configuration drift')
    run_id = uuid.uuid4().hex
    run = root/'outputs/isaac-contact-v1/runs'/run_id
    run.mkdir(parents=True, exist_ok=False)
    sources = SOURCE_PATHS.copy()
    need(sha(root/sources['input.usda']) == USD_SHA, 'Pinned 041 USD changed')
    files = {}
    for name, relative in sources.items():
        raw = (root/relative).read_bytes()
        (run/name).write_bytes(raw)
        files[name] = hashlib.sha256(raw).hexdigest()
    job = {'run_id': run_id, 'owned_runs_root': cfg['remote_runs_root'],
           'expected_isaac_root': cfg['isaac_root'], 'expected_isaac_version': cfg['expected_isaac_version'],
           'files_sha256': files, 'source_paths': sources, 'hardware_approved': False,
           'physical_calibration': False, 'ring_geometry': 'DEFERRED', 'created_unix': time.time()}
    write(run/'job.json', job, exclusive=True)
    with zipfile.ZipFile(run/'bundle.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in [*files, 'job.json']:
            archive.write(run/name, name)
    prepared = {'run_id': run_id, 'local_run_dir': str(run),
                'remote_run_dir': cfg['remote_runs_root'].rstrip('/')+'/'+run_id,
                'job_sha256': sha(run/'job.json'), 'files_sha256': files, 'source_paths': sources,
                'bundle_sha256': sha(run/'bundle.zip'), 'hardware_approved': False}
    write(run/'prepared.json', prepared, exclusive=True)
    print(json.dumps(prepared))


def inputs(run, require_isaac=False):
    job = json.loads((run/'job.json').read_text(encoding='utf-8'))
    need(re.fullmatch('[0-9a-f]{32}', job['run_id']) is not None and run.name == job['run_id'], 'Job identity')
    need(run.parent == Path(job['owned_runs_root']).resolve(), 'Owned remote directory')
    need(job['hardware_approved'] is False and job['physical_calibration'] is False, 'Hardware forbidden')
    need(Path(__file__).resolve().parent == run, 'Runtime must execute its owned copy')
    for name, digest in job['files_sha256'].items():
        need(Path(name).name == name and sha(run/name) == digest, 'Input drift: '+name)
    need(sha(run/'input.usda') == USD_SHA, 'Source USD pin')
    isaac = Path(job['expected_isaac_root']).resolve()
    if require_isaac:
        need(Path(os.environ['ISAAC_PATH']).resolve() == isaac, 'Runtime installation root drift')
    need((isaac/'VERSION').read_text(encoding='utf-8-sig').strip() == job['expected_isaac_version'], 'Isaac version drift')
    return job, isaac


def supervise(run):
    state = {'run_id': run.name, 'pid': os.getpid(), 'status': 'STARTING', 'started_unix': time.time()}
    write(run/'supervisor.json', state, exclusive=True)
    child, code = None, 1
    try:
        job, isaac = inputs(run)
        state['expected_isaac_root'] = str(isaac)
        exe = isaac/'kit/python/kit.exe'
        if not exe.is_file():
            exe = isaac/'kit/python/python.exe'
        env = os.environ.copy()
        env['PYTHONEXE'] = str(exe)  # Prevent python.bat from copying into the installation tree.
        script, batch = run/'runtime.py', isaac/'python.bat'
        for path in (script, batch, run):
            need(not any(c.isspace() or c in '&|<>^\"' for c in str(path)), 'Unsupported shell path')
        argv = [env['COMSPEC'], '/d', '/c', str(batch), '-B', str(script), 'worker', '--run-dir', str(run)]
        with (run/'runtime-stdout.txt').open('xb') as stdout, (run/'runtime-stderr.txt').open('xb') as stderr:
            child = subprocess.Popen(argv, cwd=isaac, env=env, stdout=stdout, stderr=stderr,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            state.update({'status': 'RUNNING', 'child_pid': child.pid, 'argv': argv, 'python_exe': str(exe)})
            write(run/'supervisor.json', state)
            try:
                code = child.wait(timeout=600)
            except subprocess.TimeoutExpired:
                cleanup = subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                         capture_output=True, text=True, timeout=15)
                write(run/'timeout-cleanup.json', {'owned_pid': child.pid, 'exit_code': cleanup.returncode,
                                                  'stdout': cleanup.stdout, 'stderr': cleanup.stderr})
                child.wait(timeout=15)
                code = 124
    except Exception as exc:
        state['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        worker_pid = None
        if (run/'status.json').is_file():
            worker_pid = json.loads((run/'status.json').read_text(encoding='utf-8')).get('pid')
        state.update({'status': 'FINISHED', 'worker_pid': worker_pid,
                      'child_exit_code': int(code), 'finished_unix': time.time()})
        write(run/'supervisor.json', state)
        write(run/'exit.json', {'run_id': run.name, 'pid': worker_pid, 'native_pid': child.pid if child else None,
                               'exit_code': int(code), 'supervisor_pid': os.getpid(), 'finished_unix': time.time()}, exclusive=True)
    print(json.dumps(state))
    return code


def worker(run):
    state = {'status': 'BUILDING', 'phase': 'ENTRY', 'run_id': run.name, 'pid': os.getpid(),
             'started_unix': time.time(), 'hardware_approved': False}
    write(run/'status.json', state, exclusive=True)
    app, code = None, 1
    try:
        job, isaac = inputs(run, require_isaac=True)
        from core import load_program, sample, total_time, gains, gravity_efforts, bounded_efforts
        import environment
        program = load_program(run/'program.json')
        runtime = {'run_id': run.name, 'pid': os.getpid(), 'isaac_version': job['expected_isaac_version'],
                   'close_protocol': 'OFFICIAL_FAST_SHUTDOWN_EXPLICIT_EXIT',
                   'python': sys.version, 'scripts_sha256': {k: job['files_sha256'][k] for k in
                   ('runtime.py', 'core.py', 'motion_core.py', 'environment.py', 'extract_usd.py', 'frames.py')}}
        state.update({'phase': 'SIMULATION_APP_START', 'runtime': runtime})
        write(run/'status.json', state)
        from isaacsim import SimulationApp
        app = SimulationApp({'headless': True, 'fast_shutdown': True})
        import omni.timeline
        from pxr import Gf, Usd, UsdGeom, UsdPhysics, PhysxSchema
        import isaacsim.core.experimental.utils.backend as backend
        import isaacsim.core.experimental.utils.stage as stage_utils
        from isaacsim.core.experimental.prims import Articulation, RigidPrim
        from isaacsim.core.simulation_manager import SimulationManager, SimulationEvent, PhysxScene
        from extract_usd import observe_stage

        need(SimulationManager.switch_physics_engine('physx') is not False, 'Cannot select PhysX')
        SimulationManager.set_physics_sim_device('cpu')
        need(SimulationManager.get_active_physics_engine() == 'physx', 'Actual engine must be PhysX')
        stage = stage_utils.create_new_stage(template='sunlight')
        stage_utils.set_stage_units(meters_per_unit=1.0, kilograms_per_unit=1.0)
        stage_utils.set_stage_up_axis('Z')
        stage_utils.add_reference_to_stage(str(run/'input.usda'), '/World/Robot')
        timeline = omni.timeline.get_timeline_interface()
        need(timeline.is_stopped(), 'Unexpected pre-play timeline')
        scene = PhysxScene('/World/physicsScene')
        scene.set_gravity([0, 0, -9.81])
        scene.set_steps_per_second(120)
        SimulationManager.set_default_physics_scene('/World/physicsScene')
        base = stage.GetPrimAtPath('/World/Robot/Geometry/Base')
        need(base.IsValid(), 'Missing Base')
        environment.setup(stage)
        art_api = PhysxSchema.PhysxArticulationAPI(base)
        collider_prims = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.CollisionAPI)
                          and str(p.GetPath()).startswith(environment.ROOT+'/')]
        need(len(collider_prims) == 7, 'Seven enabled robot proxies')
        static = observe_stage(stage, run/'input.usda', runtime, timeline.is_stopped())
        static['environment'] = environment.snapshot(stage)
        static['environment']['probe_source_observation'] = next(b for b in static['bodies'] if b['path'] == environment.PROBE)
        static['bodies'] = [b for b in static['bodies'] if b['name'] in LINKS]
        bodies = {b['name']: b for b in static['bodies']}
        need(set(bodies) == set(LINKS), 'Exact physical link inventory')
        robot = Articulation('/World/Robot/Geometry/Base')
        links = [RigidPrim(bodies[name]['path']) for name in LINKS]
        probe = RigidPrim(environment.PROBE)
        actual_names = list(robot.dof_names)
        need(robot.num_dofs == 6 and len(actual_names) == 6 and set(actual_names) == set(JOINTS), 'Exact named DOFs')
        canonical_indices = [actual_names.index(name) for name in JOINTS]
        def native(values):
            return [values[JOINTS.index(name)] for name in actual_names]
        settings = gains(static)
        with backend.use_backend('usd'):
            robot.set_dof_drive_types('force')
            robot.set_dof_gains(native(settings['kp']), native(settings['kd']))
            robot.set_dof_max_efforts(native(settings['effort']))
            robot.set_dof_position_targets([0.]*6)
            robot.set_dof_velocity_targets([0.]*6)
        cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        def placement(prim):
            transform = cache.GetLocalToWorldTransform(prim)
            return {'path': str(prim.GetPath()), 'position': [float(x) for x in transform.ExtractTranslation()],
                    'rotation': [[float(transform[j][i]) for j in range(3)] for i in range(3)]}
        static['robot_root'] = placement(stage.GetPrimAtPath('/World/Robot'))
        static['colliders'] = []
        for prim in collider_prims:
            body = prim.GetParent()
            need(str(body.GetPath()) in {b['path'] for b in static['bodies']}, 'Collider body parent')
            local = cache.GetLocalToWorldTransform(prim) * cache.GetLocalToWorldTransform(body).GetInverse()
            static['colliders'].append({'path': str(prim.GetPath()), 'body_path': str(body.GetPath()),
                'local_position': [float(x) for x in local.ExtractTranslation()],
                'local_basis': [[float(local[j][i]) for j in range(3)] for i in range(3)],
                'size': float(UsdGeom.Cube(prim).GetSizeAttr().Get()),
                'enabled': bool(UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get())})
        static['dof_names'], static['gains'] = actual_names, settings
        static['configuration'] = {'engine': SimulationManager.get_active_physics_engine(), 'device': 'cpu',
            'gravity': [float(x) for x in scene.get_gravity()], 'frequency_hz': 1./scene.get_dt(),
            'self_collisions': bool(art_api.GetEnabledSelfCollisionsAttr().Get())}
        stage.Flatten().Export(str(run/'scene.usda'))
        state['phase'] = 'PHYSICS_INITIALIZATION'
        write(run/'status.json', state)
        timeline.play()
        app.update()
        timeline.pause()
        app.update()
        need(not timeline.is_playing() and not timeline.is_stopped(), 'Paused tensor-ready timeline required')
        contacts = environment.ContactReader(SimulationManager.get_physics_simulation_view())
        static['environment']['contact_mapping'] = contacts.mapping
        observed = {'count': 0, 'time': 0.}
        def on_step(dt, context):
            observed['count'] += 1
            observed['time'] += float(dt)
        callback = SimulationManager.register_callback(on_step, event=SimulationEvent.PHYSICS_POST_STEP)
        static['runtime_masses'] = []
        with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
            actual_kp, actual_kd = robot.get_dof_gains()
            actual_kp, actual_kd = actual_kp.numpy().copy()[0], actual_kd.numpy().copy()[0]
            actual_effort = robot.get_dof_max_efforts().numpy().copy()[0]
            static['actual_drives'] = {
                'kp': [float(actual_kp[i]) for i in canonical_indices],
                'kd': [float(actual_kd[i]) for i in canonical_indices],
                'effort': [float(actual_effort[i]) for i in canonical_indices]}
            for name, link in zip(LINKS, links):
                com, axes = link.get_coms()
                inertia = link.get_inertias().numpy().copy()[0].reshape((3, 3), order='F')
                static['runtime_masses'].append({'name': name, 'mass': float(link.get_masses().numpy()[0, 0]),
                    'com': com.numpy().copy()[0].tolist(), 'principal_axes_wxyz': axes.numpy().copy()[0].tolist(),
                    'inertia_link_about_com': inertia.tolist()})
        with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
            com, axes = probe.get_coms()
            static['environment']['probe_runtime_mass'] = {'mass': float(probe.get_masses().numpy()[0, 0]),
                'com': com.numpy()[0].tolist(), 'principal_axes_wxyz': axes.numpy()[0].tolist(),
                'inertia_link_about_com': probe.get_inertias().numpy()[0].reshape((3,3), order='F').tolist()}
        with backend.use_backend('usd', raise_on_unsupported=True, raise_on_fallback=True):
            drive_types = robot.get_dof_drive_types()[0]
            static['actual_drives']['types'] = [drive_types[i] for i in canonical_indices]
        static['baseline_step'] = int(SimulationManager.get_num_physics_steps())
        static['baseline_time_s'] = float(SimulationManager.get_simulation_time())
        write(run/'static.json', static, exclusive=True)
        dt = float(scene.get_dt())
        need(abs(dt-1./120) <= 1e-9, 'Actual physics dt')
        count = round(total_time(program)/dt)
        need(count == 6780, 'Finite motion step inventory')
        def record(index, command, before_step, before_time, actuation=None):
            at_step = int(SimulationManager.get_num_physics_steps())
            with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                q = robot.get_dof_positions().numpy().copy()[0].tolist()
                qd = robot.get_dof_velocities().numpy().copy()[0].tolist()
                poses = []
                for name, link in zip(LINKS, links):
                    p, r = link.get_world_poses()
                    poses.append({'name': name, 'position': p.numpy().copy()[0].tolist(),
                                  'orientation_wxyz': r.numpy().copy()[0].tolist()})
                pp, pq = probe.get_world_poses()
                probe_pose = {'position': pp.numpy()[0].tolist(), 'orientation_wxyz': pq.numpy()[0].tolist()}
                contact_data = contacts.read(float(scene.get_dt()))
            after_read = int(SimulationManager.get_num_physics_steps())
            return {'index': index, 'schedule_time_s': index/120., 'segment': command['segment'],
                'checkpoint': command['checkpoint'], 'target_q_rad': command['q_rad'],
                'target_qd_rad_s': command['qd_rad_s'], 'q_rad': [q[i] for i in canonical_indices],
                'qd_rad_s': [qd[i] for i in canonical_indices], 'links': poses,
                'probe_pose': probe_pose, 'contacts': contact_data, 'actuation': actuation,
                'timeline_paused': not timeline.is_playing() and not timeline.is_stopped(),
                'clock': {'step_before': before_step, 'step_after': at_step,
                    'time_before_s': before_time, 'time_after_s': float(SimulationManager.get_simulation_time()),
                    'callback_count': observed['count'], 'callback_time_s': observed['time'],
                    'read_step_before': at_step, 'read_step_after': after_read}}
        state['phase'] = 'FINITE_DRIVE_SEQUENCE'
        write(run/'status.json', state)
        with (run/'samples.ndjson').open('x', encoding='utf-8', newline='\n') as stream:
            def emit(value):
                stream.write(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')
            previous = record(0, sample(program, 0.), static['baseline_step'], static['baseline_time_s'])
            emit(previous)
            for index in range(1, count+1):
                command = sample(program, index/120.)
                effort = bounded_efforts(gravity_efforts(static, previous['links']))
                actuation = {**effort, 'source_index': index-1,
                             'read_step': int(SimulationManager.get_num_physics_steps())}
                with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                    robot.set_dof_efforts(native(effort['ff']))
                    robot.set_dof_max_efforts(native(effort['pd_cap']))
                    af = robot.get_dof_efforts().numpy()[0]
                    ac = robot.get_dof_max_efforts().numpy()[0]
                    actuation['ff_readback'] = [float(af[i]) for i in canonical_indices]
                    actuation['pd_cap_readback'] = [float(ac[i]) for i in canonical_indices]
                    robot.set_dof_position_targets(native(command['q_rad']))
                    robot.set_dof_velocity_targets(native(command['qd_rad_s']))
                before_step = int(SimulationManager.get_num_physics_steps())
                before_time = float(SimulationManager.get_simulation_time())
                SimulationManager.step(steps=1)
                value = record(index, command, before_step, before_time, actuation)
                need(value['clock']['step_after']-before_step == 1 and observed['count'] == index,
                     'Physics must advance exactly once')
                emit(value)
                previous = value
                if index % 1200 == 0:
                    state.update({'observed_steps': index, 'observed_time_s': value['clock']['time_after_s']})
                    write(run/'status.json', state)
        SimulationManager.deregister_callback(callback)
        need(not timeline.is_stopped(), 'Final observation must precede STOP/reset')
        summary = {'status': 'DATA_CAPTURED', 'kind': 'ACTUAL_PHYSX_DRIVE_TELEMETRY',
            'run_id': run.name, 'pid': os.getpid(), 'runtime': runtime, 'sample_count': count+1,
            'physics_steps': count, 'experiment': 'GRAVITY_COLLISION_043', 'final_before_stop': True, 'hardware_approved': False,
            'physical_calibration': False, 'ring_geometry': 'DEFERRED',
            'files_sha256': {name: sha(run/name) for name in ('static.json', 'samples.ndjson', 'scene.usda')},
            'finished_unix': time.time()}
        write(run/'summary.json', summary, exclusive=True)
        state.update({'status': 'DATA_CAPTURED', 'phase': 'CLOSING_APP', 'summary_sha256': sha(run/'summary.json')})
        write(run/'status.json', state)
        code = 0
    except Exception as exc:
        state.update({'status': 'FAILED', 'reason': f'{type(exc).__name__}: {exc}'})
        (run/'failure-traceback.txt').write_text(traceback.format_exc(), encoding='utf-8')
        write(run/'status.json', state)  # Before close: fast shutdown cannot hide an earlier failure.
    finally:
        if app is not None:
            try:
                app.close(wait_for_replicator=False, exit_code=code)
            except Exception as exc:
                code = 1
                state.update({'status': 'FAILED', 'close_error': f'{type(exc).__name__}: {exc}'})
        if code == 0:
            state.update({'status': 'CLOSED', 'phase': 'APP_CLOSED', 'closed_unix': time.time()})
        write(run/'status.json', state)
    return code


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('prepare', 'supervise', 'worker'))
    cli.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    cli.add_argument('--run-dir', type=Path)
    args = cli.parse_args()
    if args.action == 'prepare':
        prepare(args.root)
        return 0
    need(args.run_dir is not None, 'Explicit owned run directory required')
    run = args.run_dir.resolve()
    return (supervise if args.action == 'supervise' else worker)(run)


if __name__ == '__main__':
    raise SystemExit(main())
