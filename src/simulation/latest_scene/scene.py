"""069B nine-DOF native physics producer; SDK imports occur only in simulate()."""
import math
import os
import sys
import types
from pathlib import Path


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def quintic(u):
    need(type(u) in (float, int) and math.isfinite(u), 'Finite interpolation coordinate')
    u = max(0.0, min(1.0, u))
    return u * u * u * (10.0 + u * (-15.0 + 6.0 * u))


def target_at(program, time_s):
    need(0 <= time_s <= program['duration_s'] + 1e-9, 'Program time in range')
    start, opening = 0.0, program['initial_opening_m']
    arm = {'J%d' % i: 0.0 for i in range(1, 7)}
    for i, phase in enumerate(program['segments']):
        end = start + phase['duration_s']
        after = {**arm, **phase.get('arm', {})}
        if time_s <= end + 1e-9 or i == len(program['segments']) - 1:
            blend = quintic((time_s - start) / phase['duration_s'])
            value = opening + (phase['opening_m'] - opening) * blend
            q = {name: arm[name] + (after[name]-arm[name])*blend for name in arm}
            d = value / 2.0 - 0.020
            q.update(KG1_slide_A=d, KG1_slide_B=d, KG1_pinion=-d / 0.0135)
            return {'phase': phase['name'], 'gravity': phase['gravity'], 'opening_m': value,
                    'targets': q, 'phase_start_s': start, 'phase_end_s': end}
        opening, arm, start = phase['opening_m'], after, end
    raise RuntimeError('Program has no phase')


def validate_program(program, model):
    need(type(program['schema_version']) is int and program['schema_version'] == 1, 'Program schema')
    need(all(type(program[k]) is int for k in ('steps', 'capture_count', 'capture_stride', 'fps')),
         'Typed integer program inventory')
    need(program['steps'] == 2640 and program['capture_count'] == 331 and program['capture_stride'] == 8,
         'Fixed physics and camera inventory')
    need(abs(program['dt_s'] - 1 / 120) < 1e-15 and program['duration_s'] == 22,
         'Fixed 120 Hz, 22 second program')
    need(program['resolution'] == [640, 480] and program['fps'] == 15, 'Fixed native camera output')
    need([p['duration_s'] for p in program['segments']] == [1, 3, 5, 3, 3, 3, 1, 3], 'Fixed transition durations')
    need([p['name'] for p in program['segments']] == ['initial','open','close','reopen','arm_out','arm_return','settle','gravity_hold'], 'Fixed named program phases')
    need(program['initial_opening_m'] == .04 and [p['opening_m'] for p in program['segments']] == [.04,.08,0.,.04,.04,.04,.04,.04], 'Fixed opening program')
    need(all(type(p['gravity']) is bool for p in program['segments']), 'Gravity flags must be booleans')
    excursion = {'J%d' % (i+1): math.radians(3 if i % 2 == 0 else -3) for i in range(6)}
    need(program['segments'][4].get('arm') == excursion and
         program['segments'][5].get('arm') == {n:0 for n in excursion} and
         all('arm' not in p for i,p in enumerate(program['segments']) if i not in (4,5)), 'Fixed six-axis excursion')
    need(program['drive'] == {'type': 'acceleration', 'kp': 64, 'kd': 16}, 'Fixed acceleration-drive gains')
    names = list(model['movable'])
    expected = ['J%d' % i for i in range(1, 7)] + ['KG1_slide_A', 'KG1_slide_B', 'KG1_pinion']
    need(len(names) == 9 and set(names) == set(expected), 'Exact canonical nine physical DOFs')
    maximum = {n: 0.0 for n in names}
    start = 0.0
    previous = target_at(program, 0)['targets']
    # Quintic derivative has its exact maximum 15/8 at u=1/2.
    for phase in program['segments']:
        end = start + phase['duration_s']
        final = target_at(program, end)['targets']
        for name in names:
            joint = model['joints'][name]
            need(joint['lower']-1e-12 <= previous[name] <= joint['upper']+1e-12 and
                 joint['lower']-1e-12 <= final[name] <= joint['upper']+1e-12, 'Target exceeds original position limit: ' + name)
            peak = abs(final[name] - previous[name]) * 1.875 / phase['duration_s']
            need(peak <= joint['velocity'] + 1e-12, 'Quintic exceeds original velocity limit: ' + name)
            maximum[name] = max(maximum[name], peak)
        previous, start = final, end
    need(start == 22, 'Complete program duration')
    need([p['gravity'] for p in program['segments']] == [False] * 7 + [True], 'Gravity only during final phase')
    return {'peak_velocity_by_name': maximum, 'capture_steps': list(range(0, 2641, 8))}


def named_columns(names, expected, values):
    need(len(names) == len(expected) and len(set(names)) == len(names) and set(names) == set(expected),
         'Exact unique native DOF names')
    need(len(values) == len(names) and all(math.isfinite(float(v)) for v in values), 'Finite complete native DOF values')
    return {name: float(values[names.index(name)]) for name in expected}


def map_gravity(names, expected, full):
    need(len(full) in (9, 15), 'Only 9 or 15 generalized-force columns are supported')
    offset = len(full) - len(names)
    need(offset in (0, 6), 'Generalized-force layout offset')
    mapped = named_columns(names, expected, full[offset:])
    return mapped, {n: offset + names.index(n) for n in expected}


def remaining_caps(model, ff):
    remaining = {n: model['joints'][n]['effort'] - abs(ff[n]) for n in model['movable']}
    return remaining, [n for n, cap in remaining.items() if cap < 0]


def quaternion_rotation(q):
    w, x, y, z = q
    need(all(math.isfinite(float(v)) for v in q) and abs(sum(v * v for v in q) - 1) < 1e-4,
         'Actual normalized finite body quaternion')
    return [[1 - 2 * (y*y + z*z), 2 * (x*y-z*w), 2 * (x*z+y*w)],
            [2 * (x*y+z*w), 1 - 2 * (x*x+z*z), 2 * (y*z-x*w)],
            [2 * (x*z-y*w), 2 * (y*z+x*w), 1 - 2 * (x*x+y*y)]]


def mv(matrix, vector):
    return [sum(a*b for a, b in zip(row, vector)) for row in matrix]


def add(a, b):
    return [x+y for x, y in zip(a, b)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def gravity_reference(model, poses, runtime_masses):
    """Independent producer virtual-work sum using actual world poses and runtime COMs."""
    frames = {p['name']: (p['position'], quaternion_rotation(p['orientation_wxyz'])) for p in poses}
    masses = {m['name']: m for m in runtime_masses}
    children = {}
    for joint in model['joints'].values():
        children.setdefault(joint['parent'], []).append(joint['child'])
    def descendants(link):
        result, todo = [], [link]
        while todo:
            child = todo.pop()
            result.append(child)
            todo.extend(children.get(child, []))
        return result
    result = {}
    for name in model['movable']:
        joint = model['joints'][name]
        parent_p, parent_r = frames[joint['parent']]
        origin_p, origin_r = joint['origin']
        pivot = add(parent_p, mv(parent_r, origin_p))
        axis = mv(parent_r, mv(origin_r, joint['axis']))
        force = [0.0, 0.0, 0.0]
        torque = [0.0, 0.0, 0.0]
        for body in descendants(joint['child']):
            if body not in masses:
                need(model['links'][body]['mass'] is None, 'Missing physical runtime mass: ' + body)
                continue
            mass = masses[body]
            pos, rot = frames[body]
            com = add(pos, mv(rot, mass['com']))
            upward = [0.0, 0.0, mass['mass'] * 9.81]
            force = add(force, upward)
            torque = add(torque, cross([x-y for x, y in zip(com, pivot)], upward))
        wrench = force if joint['type'] == 'prismatic' else torque
        result[name] = sum(x*y for x, y in zip(axis, wrench))
    return result


def checkpoint(program, row):
    """Settling is checked at phase endpoints, never mislabeled transient tracking."""
    ends, t = [], 0.0
    for phase in program['segments']:
        t += phase['duration_s']
        ends.append((t, phase['name']))
    matches = [name for end, name in ends if abs(row['time_s']-end) < 1e-8]
    if not matches:
        return None
    limits = program['settling']
    failed = []
    values = {}
    for name, target in row['targets'].items():
        kind = 'jaw' if name in ('KG1_slide_A', 'KG1_slide_B') else 'pinion' if name == 'KG1_pinion' else 'arm'
        position_key = {'arm': 'arm_position_rad', 'jaw': 'jaw_position_m', 'pinion': 'pinion_position_rad'}[kind]
        velocity_key = {'arm': 'arm_velocity_rad_s', 'jaw': 'jaw_velocity_m_s', 'pinion': 'pinion_velocity_rad_s'}[kind]
        error = abs(row['q'][name]-target)
        speed = abs(row['qd'][name])
        values[name] = {'position_error': error, 'speed': speed}
        if error > limits[position_key] or speed > limits[velocity_key]:
            failed.append(name)
    return {'phase': matches[0], 'step': row['step'], 'passed': not failed, 'failed_joints': failed, 'values': values}


def load_source(ctx, name):
    """Load only bytes already verified and bound by the transport snapshot."""
    module = types.ModuleType('_checked069b_' + name)
    module.__file__ = str(ctx.run/'input/source'/(name+'.py'))
    sys.modules[module.__name__] = module
    exec(compile(ctx.data['source/'+name+'.py'], module.__file__, 'exec'), module.__dict__)
    return module


def run(ctx):
    ctx.scene_modules = {name: load_source(ctx, name) for name in ('sdk', 'validate', 'capture')}
    return ctx.scene_modules['sdk'].lifecycle(ctx, simulate)


def prepare_self_collision_api(stage, roots, expected_root, timeline):
    """Materialize the typed PhysX attribute on the actual canonical root only."""
    from pxr import UsdPhysics, PhysxSchema
    need(timeline.is_stopped(), 'Apply articulation schema before timeline starts')
    need(type(roots) is list and len(roots) == 1 and roots[0] == expected_root,
         'Exactly the canonical Base articulation root')
    prim = stage.GetPrimAtPath(roots[0])
    need(bool(prim) and prim.HasAPI(UsdPhysics.ArticulationRootAPI), 'Actual physics articulation root')
    schema = PhysxSchema.PhysxArticulationAPI.Apply(prim)
    need(bool(schema) and prim.HasAPI(PhysxSchema.PhysxArticulationAPI), 'Apply actual PhysX articulation API')
    attr = schema.GetEnabledSelfCollisionsAttr()
    need(bool(attr) and str(attr.GetTypeName()) == 'bool', 'Typed bool self-collision attribute')
    return attr


def check_self_collision_disabled(attr):
    value = attr.Get()
    need(type(value) is bool and value is False, 'Actual typed self-collision false readback')


def simulate(ctx, app):
    import carb
    import omni.timeline
    import isaacsim.core.experimental.utils.backend as backend
    import isaacsim.core.experimental.utils.stage as stage_utils
    from isaacsim.core.experimental.prims import Articulation, RigidPrim
    from isaacsim.core.simulation_manager import SimulationManager
    from isaaclab.sim import SimulationCfg, SimulationContext
    from pxr import Gf, UsdGeom, UsdPhysics
    sdk, validator = ctx.scene_modules['sdk'], ctx.scene_modules['validate']
    capture_module = ctx.scene_modules['capture']
    source, out = ctx.run/'input', ctx.run/'output'
    model = validator.pmodel(source/'model/robot_arm.urdf')
    program = ctx.read(source/'source/program.json')
    analysis = validate_program(program, model)
    physical = [n for n, b in model['links'].items() if b['mass'] is not None]
    need(len(physical) == 11, 'Canonical eleven physical links')
    sim = SimulationContext(SimulationCfg(dt=1/120, device='cpu', gravity=(0., 0., 0.),
        physics_prim_path='/World/physicsScene', use_newton_actuators=False))
    stage = sim.stage
    stage_utils.set_stage_units(meters_per_unit=1.0, kilograms_per_unit=1.0)
    stage_utils.set_stage_up_axis('Z')
    stage_utils.add_reference_to_stage(str(source/'import-proof/model.usda'), '/World/Robot')
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    floor_config = program['floor']
    floor = UsdGeom.Cube.Define(stage, floor_config['path'])
    floor.GetSizeAttr().Set(floor_config['size'])
    floor.AddTranslateOp().Set(Gf.Vec3d(*floor_config['translation']))
    floor.AddScaleOp().Set(Gf.Vec3f(*floor_config['scale']))
    UsdPhysics.CollisionAPI.Apply(floor.GetPrim()).GetCollisionEnabledAttr().Set(True)
    timeline = omni.timeline.get_timeline_interface()
    need(timeline.is_stopped(), 'Native initialization starts stopped')
    bodies = {}
    roots = []
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith('/World/Robot/'):
            continue
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            name = prim.GetName()
            need(name not in bodies, 'Unique canonical body leaf names')
            bodies[name] = str(prim.GetPath())
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            roots.append(str(prim.GetPath()))
    need(set(bodies) == set(physical) and len(roots) == 1, 'Exact 11 bodies and one articulation root')
    self_collision_attr = prepare_self_collision_api(stage, roots, bodies[model['root']], timeline)
    robot = Articulation(roots[0])
    links = [(name, RigidPrim(bodies[name])) for name in physical]
    names = list(robot.dof_names)
    named_columns(names, model['movable'], [0.0]*len(names))
    native_caps = [model['joints'][n]['effort'] for n in names]
    native_velocities = [model['joints'][n]['velocity'] for n in names]
    with backend.use_backend('usd', raise_on_unsupported=True, raise_on_fallback=True):
        robot.set_dof_drive_types('acceleration')
        robot.set_dof_gains([64.0]*9, [16.0]*9)
        robot.set_dof_max_efforts(native_caps)
        robot.set_dof_max_velocities(native_velocities)
        robot.set_enabled_self_collisions(False)
        check_self_collision_disabled(self_collision_attr)
        robot.set_link_enabled_gravities(True)
    initial_static = sdk.observe(stage, source/'import-proof/model.usda', ctx, True)
    camera = capture_module.NativeCapture(ctx, stage, program)
    stage.Flatten().Export(str(out/'scene.usda'))
    report = {'schema_version': 1, 'run_id': ctx.run.name,
              'job_sha256': ctx.job_hash, 'pid': os.getpid(),
              'program': program, 'analysis': analysis, 'static': initial_static,
              'import_static_sha256': ctx.sha(source/'import-proof/static.json'), 'dof_names': names,
              'observations': [], 'frames': [], 'checkpoints': [],
              'dynamics': {'passed': True, 'reasons': []}, 'render': {'passed': False}}
    ctx.write(out/'report.partial.json', report)
    sim.reset()
    need(timeline.is_playing(), 'Actual Lab timeline playing after reset')
    report['binding'] = sdk.bind(ctx, sim, [robot, *[prim for _, prim in links]])
    need(set(robot.dof_names) == set(names) and list(robot.dof_names) == names, 'Native DOF identity unchanged after reset')
    need(len(robot.link_names) == 11 and set(robot.link_names) == set(physical), 'All 11 tensor articulation links')
    report['inertias'] = sdk.runtime_inertias(ctx, links)
    validator.check_runtime_inertias(model, report['inertias'])
    view = sim.physics_manager.get_physics_sim_view()
    def array(value):
        return value.numpy().copy()
    def clock():
        return {'engine_time_s': float(SimulationManager.get_simulation_time()), 'lab_step': int(sim.get_physics_step_count())}
    def state():
        before = clock()
        with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
            q = named_columns(names, model['movable'], array(robot.get_dof_positions())[0])
            qd = named_columns(names, model['movable'], array(robot.get_dof_velocities())[0])
            poses = []
            for name, prim in links:
                pos, quat = prim.get_world_poses()
                poses.append({'name': name, 'position': array(pos)[0].tolist(),
                              'orientation_wxyz': array(quat)[0].tolist()})
        after = clock()
        need(before == after, 'Stable native clock during physical read')
        return {'clock': after, 'clock_before': before, 'clock_after': after, 'q': q, 'qd': qd, 'body_poses': poses}
    def drives():
        with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
            kp, kd = robot.get_dof_gains()
            data = {'kp': named_columns(names, model['movable'], array(kp)[0]),
                    'kd': named_columns(names, model['movable'], array(kd)[0]),
                    'effort': named_columns(names, model['movable'], array(robot.get_dof_max_efforts())[0]),
                    'velocity_limits': named_columns(names, model['movable'], array(robot.get_dof_max_velocities())[0]),
                    'position_targets': named_columns(names, model['movable'], array(robot.get_dof_position_targets())[0]),
                    'velocity_targets': named_columns(names, model['movable'], array(robot.get_dof_velocity_targets())[0]),
                    'link_names': list(robot.link_names),
                    'link_enabled': array(robot.get_link_enabled_gravities())[0].astype(bool).tolist(),
                    'gravity': [float(v) for v in view.get_gravity()]}
        with backend.use_backend('usd', raise_on_unsupported=True, raise_on_fallback=True):
            types = robot.get_dof_drive_types()[0]
            data['drive_types'] = {n: str(types[names.index(n)]) for n in model['movable']}
        return data
    baseline = clock()
    current = state()
    report['initial_state'] = current
    zero_ff = {n: 0.0 for n in model['movable']}
    gravity_on = False
    def command(step, observed):
        nonlocal gravity_on
        target = target_at(program, step/120)
        if target['gravity'] and not gravity_on:
            view.set_gravity(carb.Float3(0., 0., -9.81))
            gravity_on = True
        ff = zero_ff.copy()
        proof = {'full': [], 'shape': [], 'names': names, 'columns': {},
                 'native': ff.copy(), 'expected': ff.copy(), 'max_difference': 0.0,
                 'source_clock': observed['clock'], 'source_state_index': max(0, step-1)}
        if gravity_on:
            query_before = clock()
            with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
                raw = array(robot.get_dof_gravity_compensation_forces())
            query_after = clock()
            need(query_before == query_after == observed['clock'], 'Stable native clock during gravity query')
            need(raw.ndim == 2 and raw.shape[0] == 1, 'One native generalized-force row')
            ff, columns = map_gravity(names, model['movable'], raw[0].tolist())
            reference = gravity_reference(model, observed['body_poses'], report['inertias'])
            difference = max(abs(ff[n]-reference[n]) for n in model['movable'])
            proof.update(full=raw[0].tolist(), shape=list(raw.shape), columns=columns,
                         native=ff, expected=reference, max_difference=difference,
                         query_before=query_before, query_after=query_after)
            need(difference <= 1e-3, 'Native gravity query differs from independent actual-pose reference')
        remaining, overloaded = remaining_caps(model, ff)
        if overloaded:
            report['dynamics']['passed'] = False
            report['dynamics']['reasons'].append({'step': step, 'kind': 'FF_EXCEEDS_ORIGINAL_CAP', 'joints': overloaded, 'remaining': remaining})
            return target, proof, remaining, False
        with backend.use_backend('tensor', raise_on_unsupported=True, raise_on_fallback=True):
            robot.set_dof_max_efforts([[remaining[n] for n in names]])
            robot.set_dof_position_targets([[target['targets'][n] for n in names]])
            robot.set_dof_velocity_targets([[0.0]*9])
            robot.set_dof_efforts([[ff[n] for n in names]])
        return target, proof, remaining, True
    for step in range(2641):
        before = clock()
        target, proof, remaining, feasible = command(step, current)
        if not feasible:
            report['stopped_at_step'] = step
            report['stopped_command'] = {'target': target, 'ff': proof, 'remaining_caps': remaining,
                                         'source_before': current, 'clock': clock()}
            break
        if step:
            sim.step(render=False)
        current = state()
        need(abs(current['clock']['engine_time_s']-baseline['engine_time_s']-step/120) <= 1e-6,
             'Native engine clock follows actual 120 Hz steps')
        need(current['clock']['lab_step']-baseline['lab_step'] == step, 'Actual Lab physics-step count')
        row = {'step': step, 'time_s': step/120, 'phase': target['phase'], 'opening_m': target['opening_m'],
               'targets': target['targets'], 'q': current['q'], 'qd': current['qd'], 'body_poses': current['body_poses'],
               'before_step': before, 'clock_before': current['clock_before'], 'clock_after': current['clock_after'],
               'ff': proof, 'effort_remaining': remaining,
               'configuration': drives()}
        report['observations'].append(row)
        checked = checkpoint(program, row)
        if checked is not None:
            report['checkpoints'].append(checked)
            if not checked['passed']:
                report['dynamics']['passed'] = False
                report['dynamics']['reasons'].append({'kind': 'SETTLE_CHECKPOINT', **checked})
        if step % 8 == 0:
            report['frames'].append(camera.capture(len(report['frames']), row, state))
            ctx.write(out/'report.partial.json', report)
    report['render'] = camera.finish(len(report['frames']))
    report['completed_steps'] = report['observations'][-1]['step']
    report['complete_program'] = report['completed_steps'] == 2640 and len(report['frames']) == 331
    if not report['complete_program']:
        report['dynamics']['passed'] = False
    ctx.write(out/'report.json', report)
    return report
