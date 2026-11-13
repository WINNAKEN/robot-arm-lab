"""049 actual Lab/PhysX collector, compiled from verified bytes with API capabilities."""
import json
import os
import sys
import traceback
import time
from pathlib import Path
LINKS=['Base']+[f'Link{i}' for i in range(1,7)]
JOINTS=[f'J{i}' for i in range(1,7)]
need,write,sha=API['need'],API['write'],API['sha']

def worker(run):
    out=run/'output'
    state = {'status': 'BUILDING', 'phase': 'ENTRY', 'run_id': run.name, 'pid': os.getpid(),
             'started_unix': time.time(), 'hardware_approved': False}
    write(out/'status.json', state, exclusive=True)
    app, code = None, 1
    try:
        job=API['job'];cfg=API['cfg'];isaac=Path(cfg['isaac_root']);out=run/'output';source=run/'input'
        motion=API['lib']['motion'];control=API['lib']['control'];environment=API['lib']['environment']
        load_program,sample,total_time,gains=motion.load_program,motion.sample,motion.total_time,control.gains
        program = load_program(source/'data/program.json')
        runtime = {'run_id': run.name, 'pid': os.getpid(), 'isaac_version': cfg['isaac_version'],
                   'parent_pid':os.getppid(),
                   'module_probe_sha256':sha(out/'native-module.json'),
                   'close_protocol': 'OFFICIAL_FAST_SHUTDOWN_EXPLICIT_EXIT',
                   'python': sys.version, 'input_sha256': job['inputs'], 'job_sha256': sha(run/'job.json')}
        state.update({'phase': 'SIMULATION_APP_START', 'runtime': runtime})
        write(out/'status.json', state)
        from isaacsim import SimulationApp
        app = SimulationApp({'headless': True, 'fast_shutdown': True})
        import omni.timeline
        from pxr import Gf, Usd, UsdGeom, UsdPhysics, PhysxSchema
        import isaacsim.core.experimental.utils.backend as backend
        import isaacsim.core.experimental.utils.stage as stage_utils
        from isaacsim.core.experimental.prims import Articulation, RigidPrim
        from isaacsim.core.simulation_manager import SimulationManager, SimulationEvent, PhysxScene
        observe_stage=API['lib']['extract'].observe_stage
        from isaaclab.sim import SimulationCfg,SimulationContext

        need(SimulationManager.switch_physics_engine('physx') is not False, 'Cannot select PhysX')
        SimulationManager.set_physics_sim_device('cpu')
        need(SimulationManager.get_active_physics_engine() == 'physx', 'Actual engine must be PhysX')
        sim=SimulationContext(SimulationCfg(dt=1/120,device='cpu',gravity=(0.,0.,-9.81),physics_prim_path='/World/physicsScene',use_newton_actuators=False))
        stage=sim.stage
        stage_utils.set_stage_units(meters_per_unit=1.0, kilograms_per_unit=1.0)
        stage_utils.set_stage_up_axis('Z')
        stage_utils.add_reference_to_stage(str(source/'data/model.usda'), '/World/Robot')
        stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
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
        art_api.CreateSolverPositionIterationCountAttr(64);art_api.CreateSolverVelocityIterationCountAttr(16)
        collider_prims = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.CollisionAPI)
                          and str(p.GetPath()).startswith(environment.ROOT+'/')]
        need(len(collider_prims) == 7, 'Seven enabled robot proxies')
        static = observe_stage(stage, source/'data/model.usda', runtime, timeline.is_stopped())
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
        static['solver']={'position_iterations':int(art_api.GetSolverPositionIterationCountAttr().Get()),'velocity_iterations':int(art_api.GetSolverVelocityIterationCountAttr().Get())}
        static['controller']='ENGINE_COMPUTED_TORQUE_NATIVE_PD_ZERO'
        static['lab_manager']=sim.physics_manager.__module__+'.'+sim.physics_manager.__name__
        static['configuration'] = {'engine': SimulationManager.get_active_physics_engine(), 'device': 'cpu',
            'gravity': [float(x) for x in scene.get_gravity()], 'frequency_hz': 1./scene.get_dt(),
            'self_collisions': bool(art_api.GetEnabledSelfCollisionsAttr().Get())}
        stage.Flatten().Export(str(out/'scene.usda'))
        state['phase'] = 'PHYSICS_INITIALIZATION'
        write(out/'status.json', state)
        sim.reset()
        need(timeline.is_playing() and not timeline.is_stopped(), 'Lab playing explicit-step protocol')
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
        static['lab_baseline_step']=int(sim.get_physics_step_count())
        write(out/'static.json', static, exclusive=True)
        dt = float(scene.get_dt())
        need(abs(dt-1./120) <= 1e-9, 'Actual physics dt')
        count = round(total_time(program)/dt)
        need(count == 6780, 'Finite motion step inventory')
        def record(index, command, before_step, before_time, actuation=None):
            at_step = int(SimulationManager.get_num_physics_steps());lab_at=int(sim.get_physics_step_count())
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
                'timeline_playing': bool(timeline.is_playing()), 'lab_step': int(sim.get_physics_step_count()),
                'clock': {'step_before': before_step, 'step_after': at_step,
                    'time_before_s': before_time, 'time_after_s': float(SimulationManager.get_simulation_time()),
                    'callback_count': observed['count'], 'callback_time_s': observed['time'],
                    'read_step_before': at_step, 'read_step_after': after_read,
                    'lab_read_before': lab_at, 'lab_read_after': int(sim.get_physics_step_count())}}
        state['phase'] = 'FINITE_DRIVE_SEQUENCE'
        write(out/'status.json', state)
        with (out/'samples.ndjson').open('x', encoding='utf-8', newline='\n') as stream:
            def emit(value):
                stream.write(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')
            previous = record(0, sample(program, 0.), static['baseline_step'], static['baseline_time_s'])
            emit(previous)
            for index in range(1, count+1):
                command = sample(program, index/120.)
                with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                    M0=robot.get_mass_matrices().numpy().copy()[0]
                    g0=robot.get_dof_gravity_compensation_forces().numpy().copy()[0]
                    c0=robot.get_dof_coriolis_and_centrifugal_compensation_forces().numpy().copy()[0]
                    need(M0.shape==(6,6) and g0.shape==c0.shape==(6,), 'Fixed-base engine dynamics dimensions')
                    M=M0[canonical_indices][:,canonical_indices].tolist()
                    g=[float(g0[i]) for i in canonical_indices];c=[float(c0[i]) for i in canonical_indices]
                    qdd=control.acceleration(motion,program,index/120.)
                    effort=control.command(previous['q_rad'],previous['qd_rad_s'],command,qdd,M,g,c)
                    actuation={**effort,'M':M,'g':g,'c':c,'qdd_ref':qdd,'source_index':index-1,
                               'read_step':int(SimulationManager.get_num_physics_steps()),'torque_scope':'SIM_COMMAND_NOT_MEASURED_ACTUATOR_FORCE'}
                    robot.set_dof_efforts(native(effort['tau']))
                    actual=robot.get_dof_efforts().numpy().copy()[0]
                    actuation['tau_readback']=[float(actual[i]) for i in canonical_indices]
                before_step = int(SimulationManager.get_num_physics_steps())
                before_time = float(SimulationManager.get_simulation_time())
                sim.step(render=False)
                value = record(index, command, before_step, before_time, actuation)
                need(value['clock']['step_after']-before_step == 1 and observed['count'] == index,
                     'Physics must advance exactly once')
                emit(value)
                previous = value
                if index % 1200 == 0:
                    state.update({'observed_steps': index, 'observed_time_s': value['clock']['time_after_s']})
                    write(out/'status.json', state)
        SimulationManager.deregister_callback(callback)
        need(not timeline.is_stopped(), 'Final observation must precede STOP/reset')
        summary = {'status': 'DATA_CAPTURED', 'kind': 'ACTUAL_PHYSX_DRIVE_TELEMETRY',
            'run_id': run.name, 'pid': os.getpid(), 'runtime': runtime, 'sample_count': count+1,
            'physics_steps': count, 'experiment': 'ISOLATED_COMPUTED_TORQUE_049', 'protocol':'LAB_PLAYING_EXPLICIT_STEP', 'final_before_stop': True, 'hardware_approved': False,
            'physical_calibration': False, 'ring_geometry': 'DEFERRED',
            'files_sha256': {name: sha(out/name) for name in ('static.json', 'samples.ndjson', 'scene.usda')},
            'finished_unix': time.time()}
        write(out/'summary.json', summary, exclusive=True)
        state.update({'status': 'DATA_CAPTURED', 'phase': 'CLOSING_APP', 'summary_sha256': sha(out/'summary.json')})
        write(out/'status.json', state)
        code = 0
    except Exception as exc:
        state.update({'status': 'FAILED', 'reason': f'{type(exc).__name__}: {exc}'})
        (out/'failure-traceback.txt').write_text(traceback.format_exc(), encoding='utf-8')
        write(out/'status.json', state)  # Before close: fast shutdown cannot hide an earlier failure.
    finally:
        if app is not None:
            try:
                app.close(wait_for_replicator=False, exit_code=code)
            except Exception as exc:
                code = 1
                state.update({'status': 'FAILED', 'close_error': f'{type(exc).__name__}: {exc}'})
        if code == 0:
            state.update({'status': 'CLOSED', 'phase': 'APP_CLOSED', 'closed_unix': time.time()})
        write(out/'status.json', state)
    return code
