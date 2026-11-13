"""073 deterministic, quasi-static TCP sampling; no SDK or hardware imports."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import types


ROOT = Path(__file__).resolve().parents[3]
ORACLE_SHA256 = 'c9b311532241fe4d6f2636a5f39363a781afc83673f3343cb721059ded777c10'
ARM = tuple('J' + str(i) for i in range(1, 7))
GRIPPER = ('KG1_slide_A', 'KG1_slide_B', 'KG1_pinion')
NAMES = ARM + GRIPPER
SETTINGS = {'seed': 7301, 'sample_count': 8192, 'gripper_opening_m': .04,
            'floor_clearance_m': .005, 'cloud_max_gravity_ratio': .8,
            'transition_max_gravity_ratio': .95, 'voxel_size_m': .025,
            'max_render_voxels': 1600}
DEGREES = ((0, 0, 0, 0, 0, 0), (0, -35, 20, 0, 0, 0),
           (-60, -35, 20, -25, -15, -45), (60, -35, 20, 25, 15, 45),
           (60, -55, -25, -25, -20, -60), (-60, -55, -25, 25, 15, 60),
           (0, -35, 20, 0, 0, 0))
DURATIONS = (5, 6, 9, 8, 9, 7)
PHASE_NAMES = ('raise', 'sweep_left', 'sweep_right', 'reach_high_right', 'sweep_high_left', 'return_safe')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    need(type(value) in (int, float) and math.isfinite(value), 'finite non-bool number')
    return float(value)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def q9(arm):
    need(type(arm) is dict and set(arm) == set(ARM), 'exact six arm coordinates')
    q = {n: finite(arm[n]) for n in ARM}
    q.update({n: 0.0 for n in GRIPPER})
    return q


def bounds(points):
    need(bool(points), 'nonempty bounds')
    return {'min': [min(p[i] for p in points) for i in range(3)],
            'max': [max(p[i] for p in points) for i in range(3)]}


def corners(model, oracle):
    return {n: oracle.box_corners(link['collision']) for n, link in model['links'].items()
            if link['collision'] is not None}


def assess(model, oracle, q, local_corners, include_bounds=False):
    need(set(q) == set(NAMES), 'exact nine coordinates')
    for n, value in q.items():
        value = finite(value)
        joint = model['joints'][n]
        need(joint['lower'] - 1e-12 <= value <= joint['upper'] + 1e-12, 'original position limit: ' + n)
    poses = oracle.fk(model, q)
    efforts = oracle.gravity(model, poses)
    ratios = {n: abs(efforts[n]) / model['joints'][n]['effort'] for n in NAMES}
    points = []
    low = math.inf
    for name, vertices in local_corners.items():
        p, rotation = poses[name]
        world = [oracle.add(p, oracle.mv(rotation, v)) for v in vertices]
        if name != model['root']:
            low = min(low, min(v[2] for v in world))
        if include_bounds:
            points.extend(world)
    row = {'q': dict(q), 'tcp': list(poses['tool0'][0]), 'gravity_efforts': efforts,
           'cap_ratios': ratios, 'max_gravity_ratio': max(ratios.values()),
           'floor_clearance_m': low}
    if include_bounds:
        row['body_bounds'] = bounds(points)
    return row


def make_program():
    zero = {n: 0.0 for n in ARM}
    segments = [{'name': 'initial_hold', 'kind': 'hold', 'duration_s': 2,
                 'arm': zero, 'opening_m': .04, 'gravity': True, 'checkpoint': True}]
    for name, duration, target in zip(PHASE_NAMES, DURATIONS, DEGREES[1:]):
        arm = {n: math.radians(v) for n, v in zip(ARM, target)}
        segments.append({'name': name, 'kind': 'move', 'duration_s': duration,
                         'arm': arm, 'opening_m': .04, 'gravity': True, 'checkpoint': False})
        segments.append({'name': name + '_settle', 'kind': 'hold', 'duration_s': 1,
                         'arm': arm, 'opening_m': .04, 'gravity': True, 'checkpoint': True})
    return {'schema_version': 1, 'dt_s': 1 / 120, 'duration_s': 52, 'steps': 6240,
            'capture_stride': 12, 'capture_count': 521, 'fps': 10, 'resolution': [640, 480],
            'drive': {'type': 'acceleration', 'kp': 64, 'kd': 16},
            'initial_opening_m': .04, 'gravity_all': True, 'segments': segments,
            'settling': {'window_s': .5, 'arm_position_rad': math.radians(.5),
                         'arm_velocity_rad_s': math.radians(1), 'jaw_position_m': .0005,
                         'jaw_velocity_m_s': .001, 'pinion_position_rad': math.radians(2),
                         'pinion_velocity_rad_s': math.radians(3)},
            'floor': {'path': '/World/Floor', 'size': 1, 'scale': [2, 2, .02], 'translation': [0, 0, -.01]},
            'camera': {'path': '/World/Camera', 'eye': [1.4, -1.6, 1.42], 'target': [0, 0, .42],
                       'focal_length_mm': 35, 'horizontal_aperture_mm': 36, 'vertical_aperture_mm': 27},
            'assumptions': ['Assumed mass, COM, inertia and effort limits; no real calibration.',
                            'All phases use gravity, native compensation and remaining original effort caps.',
                            'The cloud is finite sampled quasi-static TCP points, not a certified working volume.',
                            'Self collision is disabled for overlapping source AABB proxies; no grasp/load certification.',
                            'Fixed 40 mm opening; orientation-unconstrained workspace samples.']}


def target_at(program, time_s):
    t = finite(time_s)
    need(0 <= t <= program['duration_s'] + 1e-9, 'program time range')
    before = {n: 0.0 for n in ARM}
    start = 0.0
    for index, segment in enumerate(program['segments']):
        end = start + segment['duration_s']
        if t <= end + 1e-9:
            u = min(1.0, max(0.0, (t - start) / segment['duration_s']))
            blend = u * u * u * (10 + u * (-15 + 6 * u))
            arm = {n: before[n] + blend * (segment['arm'][n] - before[n]) for n in ARM}
            return q9(arm), index, segment['name']
        before = segment['arm']
        start = end
    raise ValueError('missing program phase')


def render_indices(count, maximum=1600):
    need(type(count) is int and count > 0 and type(maximum) is int and maximum > 0, 'render selection counts')
    if count <= maximum:
        return list(range(count))
    need(maximum > 1, 'at least two render points')
    return [i * (count - 1) // (maximum - 1) for i in range(maximum)]


def model_pins(model):
    path = Path(model['path']).resolve()
    files = {p.relative_to(path.parent).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
             for p in path.parent.rglob('*') if p.is_file()}
    need(len(files) == 16 and sum(n.endswith('.stl') for n in files) == 11, 'exact source model sixteen/eleven mesh inventory')
    return files


def build(model, oracle, config=None):
    settings = dict(SETTINGS)
    if config is not None:
        need(type(config) is dict and not (set(config) - set(settings)), 'closed sampler settings')
        settings.update(config)
    need(settings == SETTINGS and all(type(settings[k]) is type(v) for k, v in SETTINGS.items()), 'fixed approved 073 sampling recipe')
    need(set(model['movable']) == set(NAMES), 'canonical nine physical joints')
    pins = model_pins(model)
    local = corners(model, oracle)
    rng = random.Random(settings['seed'])
    samples = []
    cells = {}
    for index in range(settings['sample_count']):
        arm = {n: rng.uniform(model['joints'][n]['lower'], model['joints'][n]['upper']) for n in ARM}
        row = assess(model, oracle, q9(arm), local)
        row['index'] = index
        row['feasible'] = row['floor_clearance_m'] >= settings['floor_clearance_m'] and row['max_gravity_ratio'] <= settings['cloud_max_gravity_ratio']
        samples.append(row)
        if row['feasible']:
            key = tuple(math.floor(v / settings['voxel_size_m']) for v in row['tcp'])
            if key not in cells:
                cells[key] = {'key': list(key), 'position': list(row['tcp']), 'count': 0, 'witness_index': index}
            cells[key]['count'] += 1
    voxels = [cells[k] for k in sorted(cells)]
    need(len(voxels) >= settings['max_render_voxels'], 'sufficient feasible cloud voxels')
    program = make_program()
    peak_velocity = {n: 0.0 for n in NAMES}
    peak_acceleration = {n: 0.0 for n in NAMES}
    prior = {n: 0.0 for n in ARM}
    for segment in program['segments']:
        for name in ARM:
            delta = abs(segment['arm'][name] - prior[name])
            peak_velocity[name] = max(peak_velocity[name], 1.875 * delta / segment['duration_s'])
            peak_acceleration[name] = max(peak_acceleration[name], (10 / math.sqrt(3)) * delta / segment['duration_s'] ** 2)
            need(peak_velocity[name] <= model['joints'][name]['velocity'] + 1e-12, 'original velocity limit: ' + name)
        prior = segment['arm']
    path_checks = []
    body_points = []
    for step in range(program['steps'] + 1):
        t = step * program['dt_s']
        q, phase_index, phase_name = target_at(program, t)
        row = assess(model, oracle, q, local, True)
        limit = settings['transition_max_gravity_ratio'] if phase_index <= 1 else settings['cloud_max_gravity_ratio']
        need(row['floor_clearance_m'] >= settings['floor_clearance_m'], 'planned path floor clearance')
        need(row['max_gravity_ratio'] <= limit, 'planned path original-cap gravity margin')
        for key in ('min', 'max'):
            body_points.append(row['body_bounds'][key])
        row.pop('body_bounds')
        row.update(step=step, time_s=t, phase=phase_name, phase_index=phase_index, max_allowed_gravity_ratio=limit)
        path_checks.append(row)
    waypoints = []
    for index, values in enumerate(DEGREES):
        arm = {n: math.radians(v) for n, v in zip(ARM, values)}
        row = assess(model, oracle, q9(arm), local)
        row.update(index=index, arm_degrees=list(values))
        waypoints.append(row)
    feasible = [r for r in samples if r['feasible']]
    result = {'schema_version': 1, 'settings': settings, 'gravity': [0, 0, -9.81],
              'joint_names': list(NAMES), 'arm_joint_names': list(ARM),
              'effort_limits': {n: model['joints'][n]['effort'] for n in NAMES},
              'effort_units': {n: 'N' if model['joints'][n]['type'] == 'prismatic' else 'Nm' for n in NAMES},
              'joint_limits_rad': {n: [model['joints'][n]['lower'], model['joints'][n]['upper']] for n in ARM},
              'model_inputs': pins, 'source_urdf_sha256': pins[Path(model['path']).name]['sha256'],
              'oracle_sha256': sha(oracle.__file__), 'generator_sha256': sha(__file__),
              'samples': samples, 'waypoints': waypoints, 'path_checks': path_checks,
              'cloud': {'style': 'sampled_feasible_voxel_points', 'voxels': voxels,
                        'render_indices': render_indices(len(voxels), settings['max_render_voxels']),
                        'bbox': bounds([r['tcp'] for r in feasible]), 'opacity': .08,
                        'width_m': settings['voxel_size_m'], 'collision': False,
                        'label': 'Approximate sampled TCP cloud: gravity margin + floor proxies; not certified'},
              'planned_body_bounds': bounds(body_points), 'program': program,
              'stats': {'sample_count': len(samples), 'feasible_count': len(feasible), 'voxel_count': len(voxels),
                        'render_count': min(len(voxels), settings['max_render_voxels']),
                        'kinematic_bounds': bounds([r['tcp'] for r in samples]),
                        'initial_max_gravity_ratio': path_checks[0]['max_gravity_ratio'],
                        'initial_inside_conservative_cloud': path_checks[0]['max_gravity_ratio'] <= settings['cloud_max_gravity_ratio'],
                        'path_min_floor_clearance_m': min(r['floor_clearance_m'] for r in path_checks),
                        'path_max_gravity_ratio': max(r['max_gravity_ratio'] for r in path_checks),
                        'post_raise_max_gravity_ratio': max(r['max_gravity_ratio'] for r in path_checks if r['phase_index'] >= 2),
                        'peak_velocity': peak_velocity, 'peak_acceleration': peak_acceleration},
              'assumptions': program['assumptions'] + [
                  'Cloud densities count uniform joint-space samples, not probabilities or dexterity.',
                  'Cloud XYZ permits varying tool orientations; a prescribed orientation may be unreachable.',
                  'Only non-Base source AABB floor clearance and quasi-static gravity are screened.',
                  'Initial zero pose uses a 95 percent cap-ratio limit; conservative cloud uses 80 percent.',
                  'Interpolation checked every 1/120 second; inertia/dynamic effects require native observation.']}
    need(model_pins(model) == pins, 'source model changed during sampling')
    return result


def validate_result(data, model, oracle, full=True):
    need(data['settings'] == SETTINGS and type(data['schema_version']) is int and data['schema_version'] == 1, 'fixed data recipe')
    need(data['source_urdf_sha256'] == sha(model['path']) and data['model_inputs'] == model_pins(model), 'model bytes bound')
    need(data['oracle_sha256'] == sha(oracle.__file__) == ORACLE_SHA256 and data['generator_sha256'] == sha(__file__), 'generator/oracle bytes bound')
    need(data['gravity'] == [0, 0, -9.81] and data['joint_names'] == list(NAMES)
         and data['arm_joint_names'] == list(ARM), 'source gravity and joint order')
    need(data['effort_limits'] == {n: model['joints'][n]['effort'] for n in NAMES}
         and data['effort_units'] == {n: 'N' if model['joints'][n]['type'] == 'prismatic' else 'Nm' for n in NAMES}
         and data['joint_limits_rad'] == {n: [model['joints'][n]['lower'], model['joints'][n]['upper']] for n in ARM},
         'original joint cap, unit, and range metadata')
    samples = data['samples'];need(len(samples) == 8192 and [r['index'] for r in samples] == list(range(8192)), 'complete sample census')
    need(data['program'] == make_program() and len(data['path_checks']) == 6241, 'fixed complete program/path')
    local = corners(model, oracle);cells = {};rng = random.Random(SETTINGS['seed'])
    for row in samples:
        need(type(row['feasible']) is bool and set(row['q']) == set(NAMES), 'typed sample fields')
        need(all(type(v) in (int, float) and math.isfinite(v) for v in row['tcp']) and len(row['tcp']) == 3, 'finite TCP')
        need(all(row['q'][n] == 0.0 for n in GRIPPER), 'fixed opening coordinates')
        seeded = q9({n: rng.uniform(model['joints'][n]['lower'], model['joints'][n]['upper']) for n in ARM})
        need(row['q'] == seeded, 'exact seeded full-range joint sample')
        if full:
            observed = assess(model, oracle, row['q'], local)
            for key in observed:oracle.near(row[key], observed[key], 1e-10)
        ok = row['floor_clearance_m'] >= .005 and row['max_gravity_ratio'] <= .8
        need(row['feasible'] is ok, 'derived quasi-static feasibility')
        if ok:
            key = tuple(math.floor(v / .025) for v in row['tcp'])
            if key not in cells:cells[key] = {'key': list(key), 'position': list(row['tcp']), 'count': 0, 'witness_index': row['index']}
            cells[key]['count'] += 1
    need(data['cloud']['voxels'] == [cells[k] for k in sorted(cells)], 'actual first witnesses and occupancy')
    need(data['cloud']['render_indices'] == render_indices(len(cells), 1600), 'deterministic bounded render selection')
    need(data['cloud']['collision'] is False and data['cloud']['opacity'] == .08 and data['cloud']['width_m'] == .025, 'nonphysical cloud style')
    need(data['cloud']['style'] == 'sampled_feasible_voxel_points'
         and data['cloud']['label'] == 'Approximate sampled TCP cloud: gravity margin + floor proxies; not certified',
         'cloud semantics')
    need(len(data['waypoints']) == len(DEGREES), 'complete waypoint census')
    for index, degrees in enumerate(DEGREES):
        waypoint = assess(model, oracle, q9({n: math.radians(v) for n, v in zip(ARM, degrees)}), local)
        waypoint.update(index=index, arm_degrees=list(degrees))
        oracle.near(data['waypoints'][index], waypoint, 1e-12)
    body_points = []
    for i, row in enumerate(data['path_checks']):
        need(type(row['step']) is int and row['step'] == i, 'path index')
        oracle.near(row['time_s'], i / 120, 1e-12)
        q, phase, name = target_at(data['program'], i / 120)
        oracle.near(row['q'], q, 1e-12)
        need(row['phase_index'] == phase and row['phase'] == name, 'path phase')
        limit = .95 if phase <= 1 else .8
        need(row['max_allowed_gravity_ratio'] == limit and row['max_gravity_ratio'] <= limit and row['floor_clearance_m'] >= .005, 'path caps/floor')
        if full:
            observed = assess(model, oracle, q, local, True)
            for key in ('min', 'max'):body_points.append(observed['body_bounds'][key])
            observed.pop('body_bounds')
            for key in observed:oracle.near(row[key], observed[key], 1e-10)
    feasible = [r for r in samples if r['feasible']]
    oracle.near(data['cloud']['bbox'], bounds([r['tcp'] for r in feasible]), 1e-12)
    if full:oracle.near(data['planned_body_bounds'], bounds(body_points), 1e-12)
    expected_stats = {'sample_count': len(samples), 'feasible_count': len(feasible), 'voxel_count': len(cells),
                      'render_count': min(len(cells), 1600), 'kinematic_bounds': bounds([r['tcp'] for r in samples]),
                      'initial_max_gravity_ratio': data['path_checks'][0]['max_gravity_ratio'],
                      'initial_inside_conservative_cloud': data['path_checks'][0]['max_gravity_ratio'] <= .8,
                      'path_min_floor_clearance_m': min(r['floor_clearance_m'] for r in data['path_checks']),
                      'path_max_gravity_ratio': max(r['max_gravity_ratio'] for r in data['path_checks']),
                      'post_raise_max_gravity_ratio': max(r['max_gravity_ratio'] for r in data['path_checks'] if r['phase_index'] >= 2),
                      'peak_velocity': {n: 0.0 for n in NAMES}, 'peak_acceleration': {n: 0.0 for n in NAMES}}
    before = {n: 0.0 for n in ARM}
    for segment in data['program']['segments']:
        for n in ARM:
            delta = abs(segment['arm'][n] - before[n]);duration = segment['duration_s']
            expected_stats['peak_velocity'][n] = max(expected_stats['peak_velocity'][n], 1.875 * delta / duration)
            expected_stats['peak_acceleration'][n] = max(expected_stats['peak_acceleration'][n], (10 / math.sqrt(3)) * delta / duration ** 2)
        before = segment['arm']
    oracle.near(data['stats'], expected_stats, 1e-12)
    return {'samples': len(samples), 'feasible': sum(r['feasible'] for r in samples), 'voxels': len(cells),
            'render': len(data['cloud']['render_indices']), 'path_states': len(data['path_checks']), 'status': 'HOST_SAMPLER_VALID'}


def write_json(path, value):
    path = Path(path).resolve()
    need(path.is_relative_to(ROOT / 'outputs/isaac-workspace-v1'), 'sampler output stays in owned experiment')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, default=ROOT / 'models/robot-arm-urdf-v3/robot_arm.urdf')
    parser.add_argument('--oracle', type=Path, default=ROOT / 'src/simulation/latest_scene/validate.py')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/isaac-workspace-v1/data/workspace.json')
    parser.add_argument('--program-output', type=Path, default=ROOT / 'outputs/isaac-workspace-v1/data/program.json')
    args = parser.parse_args()
    raw = args.oracle.read_bytes();need(hashlib.sha256(raw).hexdigest() == ORACLE_SHA256, 'immutable 071 mathematical oracle')
    oracle = types.ModuleType('_073_math_oracle');oracle.__file__ = str(args.oracle.resolve())
    exec(compile(raw, oracle.__file__, 'exec'), oracle.__dict__)
    model = oracle.pmodel(args.model.resolve())
    data = build(model, oracle)
    checked = validate_result(data, model, oracle)
    write_json(args.output, data);write_json(args.program_output, data['program'])
    print(json.dumps({'status': checked['status'], 'output': str(args.output.resolve()),
                      'program_output': str(args.program_output.resolve()), 'stats': data['stats']}))


if __name__ == '__main__':
    main()
