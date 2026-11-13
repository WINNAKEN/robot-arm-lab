"""069B nine-DOF native physics producer; SDK imports occur only in simulate()."""
import math
import struct
import copy
import json
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


def binary32(value):
    need(type(value) in (float,int) and math.isfinite(value),'Finite velocity command')
    return struct.unpack('<f',struct.pack('<f',value))[0]


def validate_velocity_target(target, model):
    names=set(model['movable'])
    need(set(target['reference_velocity'])==set(target['velocity_targets'])==names,'Exact nine velocity coordinates')
    for n in names:
        value=target['reference_velocity'][n];encoded=binary32(value)
        need(target['velocity_targets'][n]==encoded and math.isfinite(encoded),'Exact binary32 velocity command')
        need(abs(encoded)<=model['joints'][n]['velocity'],'Velocity command exceeds original limit')


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
            u=max(0.0,min(1.0,(time_s-start)/phase['duration_s']))
            rate=30*u*u*(1-u)*(1-u)/phase['duration_s']
            velocity={n:(after[n]-arm[n])*rate for n in arm}
            jaw=(phase['opening_m']-opening)*rate/2.0
            velocity.update(KG1_slide_A=jaw,KG1_slide_B=jaw,KG1_pinion=-jaw/0.0135)
            encoded={n:binary32(v) for n,v in velocity.items()}
            return {'phase': phase['name'], 'gravity': phase['gravity'], 'opening_m': value,
                    'targets': q, 'reference_velocity':velocity, 'velocity_targets':encoded, 'phase_start_s': start, 'phase_end_s': end}
        opening, arm, start = phase['opening_m'], after, end
    raise RuntimeError('Program has no phase')


def program_for_purpose(program, purpose):
    need(purpose in ('render_smoke', 'motion'), 'Closed workspace trial purpose')
    value = copy.deepcopy(program)
    if purpose == 'render_smoke':
        need(value['segments'][0]['kind'] == 'hold' and value['segments'][0]['duration_s'] == 2,
             'Smoke derives the actual source initial hold')
        value['segments'] = value['segments'][:1]
        value['duration_s'] = 2
        value['steps'] = 240
        value['capture_count'] = 21
    return value


def validate_program(program, model):
    need(type(program['schema_version']) is int and program['schema_version'] == 1, 'Program schema')
    need(all(type(program[k]) is int for k in ('steps', 'capture_count', 'capture_stride', 'fps')),
         'Typed integer program inventory')
    need(abs(program['dt_s'] - 1 / 120) < 1e-15 and program['steps'] > 0,
         'Actual 120 Hz positive program')
    need(program['capture_stride'] == 12 and program['fps'] == 10 and program['steps'] % 12 == 0
         and program['capture_count'] == program['steps']//12+1, 'Derived 10 fps capture inventory')
    need(program['resolution'] == [640, 480], 'Native camera output dimensions')
    need(program['initial_opening_m'] == .04 and all(p['opening_m'] == .04 for p in program['segments']),
         'This sampled workspace fixes gripper opening at 40 mm')
    need(all(p['gravity'] is True for p in program['segments']), 'Full physical gravity from initial hold onward')
    need(all(type(p['duration_s']) in (int,float) and math.isfinite(p['duration_s']) and p['duration_s'] > 0
             and abs(p['duration_s']*120-round(p['duration_s']*120)) < 1e-8 for p in program['segments']), 'Integral positive phase physics steps')
    need(len({p['name'] for p in program['segments']}) == len(program['segments']), 'Unique source phase names')
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
    need(abs(start-program['duration_s']) < 1e-10 and abs(start*120-program['steps']) < 1e-8,
         'Complete derived program duration')
    return {'peak_velocity_by_name': maximum, 'capture_steps': list(range(0, program['steps']+1, 12))}


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
    factor=2.0/(w*w+x*x+y*y+z*z)
    return [[1 - factor * (y*y + z*z), factor * (x*y-z*w), factor * (x*z+y*w)],
            [factor * (x*y+z*w), 1 - factor * (x*x+z*z), factor * (y*z-x*w)],
            [factor * (x*z-y*w), factor * (y*z+x*w), 1 - factor * (x*x+y*y)]]


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
        if phase.get('checkpoint') is True:
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
    ctx.scene_modules = {name: load_source(ctx, name) for name in ('sdk', 'validate', 'capture', 'init_boundary', 'torque', 'reference', 'balance', 'root_binding')}
    return ctx.scene_modules['sdk'].lifecycle(ctx, simulate)


def prepare_self_collision_api(stage, roots, expected_root, timeline):
    """Materialize the typed PhysX attribute on the actual canonical root only."""
    from pxr import UsdPhysics, PhysxSchema
    need(timeline.is_stopped(), 'Apply articulation schema before timeline starts')
    need(type(roots) is list and len(roots) == 1 and roots[0] == expected_root,
         'Exactly the reviewed articulation-root prim')
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


def cloud_points(workspace):
    cloud = workspace['cloud']; voxels = cloud['voxels']; indices = cloud['render_indices']
    need(cloud['opacity'] == .08 and cloud['collision'] is False, 'Pinned translucent nonphysical cloud policy')
    need(type(indices) is list and 0 < len(indices) <= 1600 and len(set(indices)) == len(indices)
         and all(type(i) is int and 0 <= i < len(voxels) for i in indices), 'Pinned deterministic cloud render indices')
    points = [voxels[i]['position'] for i in indices]
    need(all(type(p) is list and len(p) == 3 and all(type(x) in (int,float) and math.isfinite(x) for x in p) for p in points),
         'Finite sampled feasible TCP points')
    return indices, points


def actual_tcp_from_row(model, row):
    joint=model['joints']['tool0_mount']
    need(joint['type']=='fixed' and joint['child']=='tool0','Canonical fixed TCP frame')
    matches=[body for body in row['body_poses'] if body['name']==joint['parent']]
    need(len(matches)==1,'Exactly one actual TCP parent body')
    body=matches[0];offset=joint['origin'][0]
    position=add(body['position'],mv(quaternion_rotation(body['orientation_wxyz']),offset))
    return {'position':position,'source_body':body['name'],'body_position':body['position'],
            'body_orientation_wxyz':body['orientation_wxyz'],'local_tool_offset':offset}


def create_actual_tcp_visual(stage):
    from pxr import Gf, UsdGeom, UsdShade, Sdf, UsdPhysics
    root='/World/ActualTCP';UsdGeom.Scope.Define(stage,root)
    marker=UsdGeom.Sphere.Define(stage,root+'/Marker');marker.GetRadiusAttr().Set(.014)
    translate=marker.AddTranslateOp()
    trail=UsdGeom.BasisCurves.Define(stage,root+'/Trail')
    trail.CreateTypeAttr().Set('linear');trail.CreateWrapAttr().Set('nonperiodic')
    trail.CreatePointsAttr().Set([]);trail.CreateCurveVertexCountsAttr().Set([]);trail.CreateWidthsAttr().Set([.004])
    material=UsdShade.Material.Define(stage,root+'/Material');shader=UsdShade.Shader.Define(stage,root+'/Material/Surface')
    shader.CreateIdAttr('UsdPreviewSurface')
    shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.,.38,.02))
    shader.CreateInput('emissiveColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.2,.076,.004))
    shader.CreateInput('opacity',Sdf.ValueTypeNames.Float).Set(1.)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
    for shape in (marker,trail):
        shape.CreateDisplayColorAttr().Set([Gf.Vec3f(1.,.38,.02)])
        UsdShade.MaterialBindingAPI.Apply(shape.GetPrim()).Bind(material)
    points=[]
    def update(tcp):
        point=list(tcp['position']);points.append(point);translate.Set(Gf.Vec3d(*point))
        rendered_points=points if len(points)>=2 else []
        trail.GetPointsAttr().Set([Gf.Vec3f(*p) for p in rendered_points])
        trail.GetCurveVertexCountsAttr().Set([len(points)] if len(points)>=2 else [])
        return {'marker_path':str(marker.GetPath()),'trail_path':str(trail.GetPath()),
                'marker_position':[float(x) for x in translate.Get()], 'trail_count':len(rendered_points)}
    def snapshot():
        roles=[]
        for prim in stage.Traverse():
            if str(prim.GetPath()).startswith(root):
                flags={name:bool(prim.HasAPI(api)) for name,api in
                       (('rigid_body',UsdPhysics.RigidBodyAPI),('mass_api',UsdPhysics.MassAPI),('collision',UsdPhysics.CollisionAPI))}
                need(not any(flags.values()),'Actual TCP visuals have no physics API')
                roles.append({'path':str(prim.GetPath()),'type':str(prim.GetTypeName()),
                              'applied_schemas':[str(x) for x in prim.GetAppliedSchemas()],**flags})
        return {'root':root,'marker_path':str(marker.GetPath()),'trail_path':str(trail.GetPath()),
                'positions':[[float(x) for x in p] for p in trail.GetPointsAttr().Get()],
                'prim_roles':roles,'color_rgb':[1.,.38,.02],'physics':False,
                'label':'Actual native TCP marker and captured-position trail'}
    return update,snapshot


def create_workspace_cloud(stage, workspace):
    from pxr import Gf, UsdGeom, UsdShade, Sdf, UsdPhysics
    indices, points = cloud_points(workspace)
    root = '/World/SampledWorkspace'
    instancer = UsdGeom.PointInstancer.Define(stage, root)
    sphere = UsdGeom.Sphere.Define(stage, root+'/Prototypes/Point')
    sphere.GetRadiusAttr().Set(.01)
    sphere.CreateDisplayColorAttr().Set([Gf.Vec3f(.48,.22,.9)])
    material = UsdShade.Material.Define(stage, root+'/Material')
    shader = UsdShade.Shader.Define(stage, root+'/Material/PreviewSurface')
    shader.CreateIdAttr('UsdPreviewSurface')
    shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.48,.22,.9))
    shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(.08)
    shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(.7)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
    UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(material)
    instancer.CreatePrototypesRel().SetTargets([sphere.GetPath()])
    instancer.CreateProtoIndicesAttr().Set([0]*len(points))
    instancer.CreatePositionsAttr().Set([Gf.Vec3f(*p) for p in points])
    instancer.CreateIdsAttr().Set(indices)
    instancer.MakeInvisible()
    roles=[]
    for prim in stage.Traverse():
        if str(prim.GetPath()).startswith(root):
            need(not any(prim.HasAPI(api) for api in (UsdPhysics.RigidBodyAPI, UsdPhysics.MassAPI, UsdPhysics.CollisionAPI)),
                 'Workspace cloud has no physics API')
            roles.append({'path':str(prim.GetPath()),'type':str(prim.GetTypeName()),
                          'applied_schemas':[str(a) for a in prim.GetAppliedSchemas()],
                          'rigid_body':bool(prim.HasAPI(UsdPhysics.RigidBodyAPI)),
                          'mass_api':bool(prim.HasAPI(UsdPhysics.MassAPI)),
                          'collision':bool(prim.HasAPI(UsdPhysics.CollisionAPI))})
    observed_points=[[float(x) for x in point] for point in instancer.GetPositionsAttr().Get()]
    return {'path':root,'kind':'UsdGeom.PointInstancer','render_indices':[int(x) for x in instancer.GetIdsAttr().Get()],
            'positions':observed_points,'prim_roles':roles,
            'sphere_radius_m':float(sphere.GetRadiusAttr().Get()),'opacity':float(shader.GetInput('opacity').Get()),'color_rgb':[.48,.22,.9],
            'physics':False,'visibility':str(instancer.GetVisibilityAttr().Get()),'label':'Workspace fog hidden per user request',
            'robot_label':'Actual native robot state'}


def validate_gain_initialization(record,names):
    need(record['backend']=='tensor' and type(record['engine_time_s']) in (int,float) and record['engine_time_s']==0.,'Gain initialization before positive time')
    need(set(record['kp'])==set(record['kd'])==set(names),'All nine gain readbacks')
    need(all(v==64. for v in record['kp'].values()) and all(v==16. for v in record['kd'].values()),'Exact same nominal tensor gain readback')


def simulate_native(ctx, app):
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
    from driver import parse
    source_program = ctx.read(source/'source/program.json')
    program = program_for_purpose(source_program, ctx.job['purpose'])
    workspace = parse(ctx.data['ref/workspace.json'])
    analysis = validate_program(program, model)
    physical = [n for n, b in model['links'].items() if b['mass'] is not None]
    need(len(physical) == 11, 'Canonical eleven physical links')
    from isaaclab_physx.physics.physx_manager import PhysxManager
    import omni.physx
    boundary = ctx.scene_modules['init_boundary'].Boundary(ctx, PhysxManager, omni.physx.get_physx_interface(), carb.settings.get_settings(), SimulationManager.get_simulation_time)
    ctx.init_boundary = boundary
    sim = SimulationContext(SimulationCfg(dt=1/120, device='cpu', gravity=(0., 0., -9.81),
        physics_prim_path='/World/physicsScene', use_newton_actuators=False))
    stage = sim.stage
    UsdGeom.Xform.Define(stage, "/World")
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
    stage.Flatten().Export(str(out/'base-before.usda'))
    base_before=sdk.observe(stage,out/'base-before.usda',ctx,True)
    validator.verify_import(source/'model/robot_arm.urdf',base_before,ctx.cfg,floor=True)
    root_binding=ctx.scene_modules['root_binding']
    root_normalization=root_binding.normalize(stage,base_before,roots,timeline)
    roots=[root_normalization['after_root']]
    self_collision_attr = prepare_self_collision_api(stage, roots, '/World/Robot', timeline)
    stage.Flatten().Export(str(out/'base-after.usda'))
    base_after=sdk.observe(stage,out/'base-after.usda',ctx,True)
    fixed_binding={'schema_version':1,'before':base_before,'after':base_after,'normalization':root_normalization}
    root_binding.verify(fixed_binding,validator.__dict__,out)
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
    stage.Flatten().Export(str(out/'initial-setup.usda'))
    initial_static = sdk.observe(stage, out/'initial-setup.usda', ctx, True)
    reference_module=ctx.scene_modules['reference']
    reference_items=reference_module.create_safe(stage,ctx)
    cloud = create_workspace_cloud(stage, workspace)
    update_tcp_visual,tcp_visual_snapshot=create_actual_tcp_visual(stage)
    camera = capture_module.NativeCapture(ctx, stage, program, workspace)
    stage.Flatten().Export(str(out/'scene.usda'))
    report = {'schema_version': 1, 'run_id': ctx.run.name,
              'job_sha256': ctx.job_hash, 'pid': os.getpid(),
              'program': program, 'purpose':ctx.job['purpose'], 'analysis': analysis, 'static': initial_static,
              'workspace_cloud':cloud, 'camera':camera.camera,
              'import_static_sha256': ctx.sha(source/'import-proof/static.json'), 'dof_names': names,
              'observations': [], 'frames': [], 'checkpoints': [],
              'dynamics': {'passed': True, 'reasons': []}, 'render': {'passed': False},
              'fixed_base_binding':fixed_binding}
    ctx.write(out/'report.partial.json', report)
    sim.reset()
    boundary.after_reset()
    need(timeline.is_playing(), 'Actual Lab timeline playing after reset')
    report['binding'] = sdk.bind(ctx, sim, [robot, *[prim for _, prim in links]])
    need(robot._physics_articulation_view.shared_metatype.fixed_base is True,'Native actual fixed-base flag after reviewed root normalization')
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
    def init_state():
        with backend.use_backend("tensor", raise_on_unsupported=True, raise_on_fallback=True):
            return {"q":named_columns(names, model["movable"], array(robot.get_dof_positions())[0]),"qd":named_columns(names, model["movable"], array(robot.get_dof_velocities())[0])}
    references=reference_module.References(ctx,reference_items,backend,array,clock,view)
    report['reference']=references.packet
    report['robot_mechanisms_initial']=reference_module.robot_inventory(robot,backend,array)
    dynamics_observer=ctx.scene_modules['balance'].Dynamics(ctx,robot,backend,array,clock,names,stage,bodies)
    report['dynamics_balance']=dynamics_observer.packet
    with backend.use_backend("tensor", raise_on_unsupported=True, raise_on_fallback=True):
        robot.set_dof_gains([[64.0]*9], [[16.0]*9])
    gain_state=drives()
    report['gain_initialization']={'backend':'tensor','engine_time_s':clock()['engine_time_s'],'kp':gain_state['kp'],'kd':gain_state['kd']}
    validate_gain_initialization(report['gain_initialization'], names)
    boundary.ready(init_state)
    baseline = clock()
    current = state()
    report['initial_state'] = current
    zero_ff = {n: 0.0 for n in model['movable']}
    torque=ctx.scene_modules['torque']
    report['torque_binding']=torque.make_binding(initial_static,model,names,list(robot.link_names))
    report['torque_api_pin']=ctx.cfg['sdk_source_pins'][-1]
    report['torque_prime']=torque.observe(robot,backend,array,clock,report['torque_binding'],0,zero_ff)
    def command(step, observed):
        target = target_at(program, step/120)
        validate_velocity_target(target, model)
        ff = zero_ff.copy()
        proof = {'full': [], 'shape': [], 'names': names, 'columns': {},
                 'native': ff.copy(), 'expected': ff.copy(), 'max_difference': 0.0,
                 'source_clock': observed['clock'], 'source_state_index': max(0, step-1)}
        if target['gravity']:
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
            robot.set_dof_velocity_targets([[target['velocity_targets'][n] for n in names]])
            robot.set_dof_efforts([[ff[n] for n in names]])
        return target, proof, remaining, True
    with (out/'motion.ndjson').open('x', encoding='utf-8', newline='\n') as journal:
        for step in range(program['steps']+1):
            before = clock()
            target, proof, remaining, feasible = command(step, current)
            if not feasible:
                report['stopped_at_step'] = step
                report['stopped_command'] = {'target': target, 'ff': proof, 'remaining_caps': remaining,
                                             'source_before': current, 'clock': clock()}
                break
            if step:
                reference_command=references.issue(step)
                dynamics_command=dynamics_observer.issue(step,current,proof)
                sim.step(render=False)
                references.observe(reference_command)
            current = state()
            need(abs(current['clock']['engine_time_s']-baseline['engine_time_s']-step/120) <= 1e-6,
                 'Native engine clock follows actual 120 Hz steps')
            need(current['clock']['lab_step']-baseline['lab_step'] == step, 'Actual Lab physics-step count')
            row = {'step': step, 'time_s': step/120, 'phase': target['phase'], 'opening_m': target['opening_m'],
                   'targets': target['targets'], 'reference_velocity':target['reference_velocity'], 'velocity_targets':target['velocity_targets'], 'q': current['q'], 'qd': current['qd'], 'body_poses': current['body_poses'],
                   'before_step': before, 'clock_before': current['clock_before'], 'clock_after': current['clock_after'],
                   'ff': proof, 'effort_remaining': remaining,
                   'configuration': drives()}
            row['torque_observation']=torque.observe(robot,backend,array,clock,report['torque_binding'],step,proof['native']) if step else torque.unavailable(clock())
            row['mechanism_inventory']=reference_module.robot_inventory(robot,backend,array) if step%12==0 else None
            if step:dynamics_observer.observe(dynamics_command,row)
            row['actual_tcp']=actual_tcp_from_row(model,row)
            report['observations'].append(row)
            journal.write(json.dumps(row, allow_nan=False, separators=(',',':'))+'\n')
            journal.flush()
            checked = checkpoint(program, row)
            if checked is not None:
                report['checkpoints'].append(checked)
                if not checked['passed']:
                    report['dynamics']['passed'] = False
                    report['dynamics']['reasons'].append({'kind': 'SETTLE_CHECKPOINT', **checked})
            if step % program['capture_stride'] == 0:
                visual=update_tcp_visual(row['actual_tcp'])
                report['frames'].append(camera.capture(len(report['frames']), row, state, tcp_visual=visual))
                journal.flush()
                ctx.write(out/'report.partial.json', {'run_id':ctx.run.name,'job_sha256':ctx.job_hash,
                          'last_row':row,'observation_count':len(report['observations']),
                          'frame_count':len(report['frames']),'checkpoints':report['checkpoints'],
                          'dynamics':report['dynamics'],'complete_program':False})
    report['render'] = camera.finish(len(report['frames']), purpose=ctx.job['purpose'])
    report['actual_tcp_visual']=tcp_visual_snapshot()
    report['completed_steps'] = report['observations'][-1]['step']
    report['complete_program'] = report['completed_steps'] == program['steps'] and len(report['frames']) == program['capture_count']
    if not report['complete_program']:
        report['dynamics']['passed'] = False
    references.close()
    dynamics_observer.close()
    boundary.finish(report['completed_steps'])
    report['initialization_boundary'] = boundary.audit
    ctx.write(out/'report.json', report)
    return report


def simulate(ctx, app):
    primary=None
    try:
        return simulate_native(ctx, app)
    except BaseException as exc:
        primary=exc
        raise
    finally:
        if hasattr(ctx, 'init_boundary'):
            try:errors=ctx.init_boundary.close()
            except BaseException as cleanup:
                ctx.init_cleanup_errors=['unexpected-close:'+type(cleanup).__name__]
                if primary is None:raise
                errors=ctx.init_cleanup_errors
            if errors and primary is None:raise RuntimeError('INIT_CLEANUP_FAILED: '+str(errors))
