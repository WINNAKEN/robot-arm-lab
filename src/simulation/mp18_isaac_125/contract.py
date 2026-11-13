"""119 pure input/physics contracts. SDK and numeric libraries are never imported here at import time."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import struct
import xml.etree.ElementTree as ET

ARM = ['J%d' % i for i in range(1, 7)]
NAMES = ARM + ['KG1_slide_A', 'KG1_slide_B', 'KG1_pinion']
PHYSICAL = ['Base'] + ['Link%d' % i for i in range(1, 7)] + ['KG1', 'KG1_A', 'KG1_B', 'KG1_R']


def need(ok, message):
    if not ok:
        raise ValueError(message)


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def bad(value):
        raise ValueError('Nonfinite JSON: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(name):
    need(type(name) is str and name and not any(x in name for x in ('\\', ':', '\0', '\n', '\r', '\t')),
         'Canonical relative path required')
    p = PurePosixPath(name)
    need(not p.is_absolute() and p.as_posix() == name and all(x not in ('.', '..') for x in p.parts),
         'Path traversal/normalization rejected')
    return name


def path_in(root, name):
    root = Path(root).resolve()
    p = root / relative(name)
    for part in (p, *p.parents):
        if part == root:
            break
        need(not part.is_symlink() and not part.is_junction(), 'Linked path rejected')
    need(p.resolve().is_relative_to(root), 'Escaped path')
    return p


def near(a, b, tol=1e-6):
    if isinstance(a, dict):
        need(isinstance(b, dict) and set(a) == set(b), 'Dictionary comparison keys')
        for k in a:
            near(a[k], b[k], tol)
    elif isinstance(a, (list, tuple)):
        need(isinstance(b, (list, tuple)) and len(a) == len(b), 'Sequence comparison shape')
        for x, y in zip(a, b):
            near(x, y, tol)
    elif type(a) in (float, int) and type(b) in (float, int):
        need(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tol, 'Numerical mismatch')
    else:
        need(type(a) is type(b) and a == b, 'Exact comparison mismatch')


def ident():
    return [[float(i == j) for j in range(4)] for i in range(4)]


def mm(a, b):
    return [[sum(x*y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


def mv(a, b):
    return [sum(x*y for x, y in zip(row, b)) for row in a]


def tr(a):
    return [list(x) for x in zip(*a)]


def add(a, b):
    return [x+y for x, y in zip(a, b)]


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def rotation(axis, angle):
    norm = math.sqrt(sum(x*x for x in axis))
    need(norm > 0 and math.isfinite(angle), 'Finite axis rotation')
    x, y, z = [v/norm for v in axis]
    c, s, d = math.cos(angle), math.sin(angle), 1-math.cos(angle)
    return [[c+x*x*d, x*y*d-z*s, x*z*d+y*s], [y*x*d+z*s, c+y*y*d, y*z*d-x*s],
            [z*x*d-y*s, z*y*d+x*s, c+z*z*d]]


def quat(q):
    w, x, y, z = q
    need(abs(sum(v*v for v in q)-1) < 1e-4, 'Normalized WXYZ quaternion')
    return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]


def tf(position, R):
    t = ident()
    for i in range(3):
        t[i][:3] = R[i]
        t[i][3] = position[i]
    return t


def inverse(t):
    R = tr([row[:3] for row in t[:3]])
    return tf(mv(R, [-row[3] for row in t[:3]]), R)


def xyz(e, key, default='0 0 0'):
    values = [float(x) for x in (default if e is None else e.get(key, default)).split()]
    need(len(values) == 3 and all(math.isfinite(x) for x in values), 'Finite XYZ')
    return values


def origin(e):
    r, p, y = xyz(e, 'rpy')
    return tf(xyz(e, 'xyz'), mm(mm(rotation([0, 0, 1], y), rotation([0, 1, 0], p)), rotation([1, 0, 0], r)))


def parse_model(path):
    path = Path(path)
    robot = ET.parse(path).getroot()
    materials = {m.get('name'): [float(x) for x in m.find('color').get('rgba').split()]
                 for m in robot.findall('material')}
    links, joints = {}, {}
    for link in robot.findall('link'):
        name = link.get('name')
        need(name not in links, 'Duplicate link')
        i = link.find('inertial')
        entry = {'mass': None, 'com': None, 'inertia': None, 'visuals': [], 'collisions': []}
        if i is not None:
            entry['mass'] = float(i.find('mass').get('value'))
            need(entry['mass'] > 0, 'Positive physical mass')
            entry['com'] = xyz(i.find('origin'), 'xyz')
            v = i.find('inertia').attrib
            I = [[float(v['ixx']), float(v['ixy']), float(v['ixz'])],
                 [float(v['ixy']), float(v['iyy']), float(v['iyz'])],
                 [float(v['ixz']), float(v['iyz']), float(v['izz'])]]
            R = [row[:3] for row in origin(i.find('origin'))[:3]]
            entry['inertia'] = mm(mm(R, I), tr(R))
        for kind in ('visual', 'collision'):
            for e in link.findall(kind):
                mesh = e.find('geometry/mesh')
                need(mesh is not None, 'v4 mesh geometry required')
                relative(mesh.get('filename'))
                near(xyz(mesh, 'scale', '1 1 1'), [1., 1., 1.], 0)
                near(origin(e.find('origin')), ident(), 0)
                material = e.find('material')
                entry[kind+'s'].append({'file': mesh.get('filename'), 'color':
                    materials.get(material.get('name')) if material is not None else None})
        entry['visual'] = entry['visuals'] or None
        entry['collision'] = entry['collisions'] or None
        links[name] = entry
    for e in robot.findall('joint'):
        name = e.get('name')
        need(name not in joints, 'Duplicate joint')
        o = origin(e.find('origin'))
        j = {'parent': e.find('parent').get('link'), 'child': e.find('child').get('link'),
             'type': e.get('type'), 'matrix': o, 'origin': ([row[3] for row in o[:3]], [row[:3] for row in o[:3]])}
        if j['type'] != 'fixed':
            j['axis'] = xyz(e.find('axis'), 'xyz')
            j.update({key: float(e.find('limit').get(key)) for key in ('lower', 'upper', 'effort', 'velocity')})
        m = e.find('mimic')
        if m is not None:
            j['mimic'] = {'joint': m.get('joint'), 'multiplier': float(m.get('multiplier', '1')),
                          'offset': float(m.get('offset', '0'))}
        joints[name] = j
    need(set(links) == set(PHYSICAL + ['tool0']) and len(joints) == 11, 'Canonical v4 tree')
    need({k for k, j in joints.items() if j['type'] != 'fixed'} == set(NAMES), 'Canonical nine DOFs')
    need(sum(len(v['visuals']) for v in links.values()) == 47 and
         sum(len(v['collisions']) for v in links.values()) == 11, 'All v4 geometry references')
    children = [j['child'] for j in joints.values()]
    need(len(set(children)) == len(children) and set(links)-set(children) == {'Base'}, 'Single-parent Base-rooted tree')
    need(all(j['parent'] in links and j['child'] in links and j['parent'] != j['child'] for j in joints.values()), 'Known joint endpoints')
    model = {'path': str(path), 'model_dir': str(path.parent), 'links': links, 'joints': joints, 'movable': NAMES.copy()}
    fk(model, {})
    return model


pmodel = parse_model


def fk(model, q):
    def position(name, stack=()):
        need(name not in stack, 'Mimic cycle')
        j = model['joints'][name]
        if 'mimic' in j:
            m = j['mimic']
            need(m['joint'] in model['joints'], 'Known mimic leader')
            return position(m['joint'], stack+(name,))*m['multiplier']+m['offset']
        return float(q.get(name, 0.))
    world, todo = {'Base': ident()}, dict(model['joints'])
    while todo:
        before = len(todo)
        for name, j in list(todo.items()):
            if j['parent'] not in world:
                continue
            d = ident()
            if j['type'] == 'revolute':
                d = tf([0., 0., 0.], rotation(j['axis'], position(name)))
            elif j['type'] == 'prismatic':
                d = tf([x*position(name) for x in j['axis']], [row[:3] for row in ident()[:3]])
            else:
                need(j['type'] == 'fixed', 'Unsupported joint')
            world[j['child']] = mm(mm(world[j['parent']], j['matrix']), d)
            del todo[name]
        need(len(todo) < before, 'Disconnected/cyclic tree')
    return world


def binary32(x):
    need(type(x) in (float, int) and math.isfinite(x), 'Finite binary32 input')
    return struct.unpack('<f', struct.pack('<f', x))[0]


def target_at(program, stage_name, time_s):
    stage = program['stages'][stage_name]
    need(math.isfinite(time_s) and 0 <= time_s <= stage['duration_s']+1e-8, 'Stage time bounds')
    previous = [0.]*6
    start = 0.
    targets, velocities = {}, {}
    for phase in stage['segments']:
        dur = phase['duration_s']
        final = [math.radians(x) for x in phase['q_deg']]
        if time_s <= start+dur+1e-10:
            u = min(1., max(0., (time_s-start)/dur))
            s = u*u*u*(10+u*(-15+6*u))
            sd = 30*u*u*(1-u)*(1-u)/dur
            targets = {n: a+(b-a)*s for n, a, b in zip(ARM, previous, final)}
            velocities = {n: (b-a)*sd for n, a, b in zip(ARM, previous, final)}
            break
        previous, start = final, start+dur
    need(len(targets) == 6, 'Complete program time')
    targets.update({n: 0. for n in NAMES[6:]})
    velocities.update({n: 0. for n in NAMES[6:]})
    return {'targets': targets, 'reference_velocity': velocities,
            'velocity_targets': {n: binary32(x) for n, x in velocities.items()},
            'phase': stage_name, 'opening_m': .04}


def named_columns(names, expected, values):
    need(len(names) == len(set(names)) == len(expected) and set(names) == set(expected), 'Exact named DOF set')
    need(len(values) == len(names) and all(math.isfinite(float(x)) for x in values), 'Finite DOF values')
    return {n: float(values[names.index(n)]) for n in expected}


def map_gravity(names, expected, full):
    need(len(full)-len(names) in (0, 6), 'Known gravity force columns')
    offset = len(full)-len(names)
    return named_columns(names, expected, full[offset:]), {n: offset+names.index(n) for n in expected}


def remaining_caps(model, ff, caps=None):
    caps = caps or {n: model['joints'][n]['effort'] for n in model['movable']}
    remaining = {n: caps[n]-abs(ff[n]) for n in model['movable']}
    return remaining, [n for n, value in remaining.items() if value < 0]


def effective_caps(cfg, approval):
    need(type(approval) is dict and set(approval) == {'unit', 'cap_mode', 'cap_approved', 'user_request', 'user_reply', 'hardware_approved'},
         'Closed user decision record')
    need(approval['unit'] == 119 and approval['hardware_approved'] is False and
         approval['user_request'] == '119_SIMULATION_VIDEO_DRIVE', 'Simulation-only user scope')
    mode = approval['cap_mode']
    need(mode in ('legacy', 'sim_override_12_7') and mode in cfg['cap_modes'], 'Closed cap choice')
    need(approval['cap_approved'] is (mode == 'sim_override_12_7'), 'Cap override needs explicit approval')
    need(type(approval['user_reply']) is str and bool(approval['user_reply'].strip()), 'Retained actual user reply')
    caps = cfg['cap_modes'][mode]
    expected = dict(zip(NAMES, [3, 6, 5, 2, 2, 1, 10, 10, .2]))
    if mode == 'sim_override_12_7':
        expected.update(J2=12, J3=7)
    need(caps == expected, 'Only approved simulation cap difference')
    return dict(caps)


def verify_inputs(model_dir, cfg, root=None):
    pins = cfg['model_pins']
    need(len(pins) == 74 and cfg['unit'] == 119 and cfg['hardware_approved'] is False, 'Exact v4 model scope')
    found = {p.relative_to(model_dir).as_posix() for p in Path(model_dir).rglob('*') if p.is_file()}
    need(found == set(pins), 'Complete model inventory')
    for rel, expected in pins.items():
        p = path_in(model_dir, rel)
        need(p.is_file() and p.stat().st_size == expected['bytes'] and sha(p) == expected['sha256'], 'Model pin: '+rel)
    if root is not None:
        for key, item in cfg['refs'].items():
            p = path_in(root, item['path'])
            need(p.is_file() and sha(p) == item['sha256'], 'Immutable dependency pin: '+key)
    return parse_model(Path(model_dir)/'robot_arm.urdf')


def phase_check(model, stage_name, q, qd, target, program, min_world_z=None):
    need(set(q) == set(qd) == set(target['targets']) == set(NAMES), 'Exact observed coordinates')
    reasons = []
    for name in NAMES:
        need(all(math.isfinite(v) for v in (q[name], qd[name], target['targets'][name])), 'Finite observed state')
        if name in ARM:
            if abs(q[name]-target['targets'][name]) > math.radians(program['settling']['position_deg']):
                reasons.append(name+':position')
            if abs(qd[name]) > math.radians(program['settling']['velocity_deg_s']):
                reasons.append(name+':velocity')
        else:
            tol = .001 if name != 'KG1_pinion' else .02
            if abs(q[name]-target['targets'][name]) > tol:
                reasons.append(name+':gripper')
    if min_world_z is not None and min_world_z < -.0001:
        reasons.append('desk_penetration')
    return {'stage': stage_name, 'passed': not reasons, 'reasons': reasons}


def build_support(model):
    """Exact linear support extrema of visual convex hull vertices, not a collision acceptance."""
    import trimesh
    return {name: trimesh.load(path_in(model['model_dir'], 'meshes/'+name+'.stl'), force='mesh').convex_hull.vertices.tolist()
            for name in PHYSICAL}


def floor_and_bounds(model, matrices, support):
    import numpy as np
    lo, hi = [float('inf')]*3, [-float('inf')]*3
    moving_floor = float('inf')
    for name, points in support.items():
        t = np.asarray(matrices[name])
        world = np.asarray(points) @ t[:3, :3].T + t[:3, 3]
        low, high = world.min(axis=0), world.max(axis=0)
        for i in range(3):
            lo[i], hi[i] = min(lo[i], float(low[i])), max(hi[i], float(high[i]))
        if name != 'Base':
            moving_floor = min(moving_floor, float(low[2]))
    return moving_floor, {'min': lo, 'max': hi}


def validate_program(program, model, support):
    need(program['unit'] == 119 and program['dt_s'] == 1/120 and program['fps'] == 10 and program['capture_stride'] == 12,
         'Fixed source timing')
    need(program['drive'] == {'type': 'acceleration', 'kp': 64, 'kd': 16} and program['resolution'] == [640, 480], 'Fixed drive and pixels')
    need(program['settling'] == {'position_deg': .5, 'velocity_deg_s': 1, 'large_check_s': 34}, 'Unchanged settling criteria')
    need(set(program['stages']) == {'hold', 'small', 'large'}, 'Three closed phases')
    low, high, result = [float('inf')]*3, [-float('inf')]*3, {}
    for name, duration in (('hold', 2), ('small', 12), ('large', 42)):
        stage = program['stages'][name]
        need(stage['duration_s'] == duration and sum(s['duration_s'] for s in stage['segments']) == duration, 'Complete phase duration')
        previous = [0.]*6
        for segment in stage['segments']:
            dur = segment['duration_s']
            need(type(dur) in (float, int) and dur > 0 and abs(dur*120-round(dur*120)) < 1e-9, 'Integral phase step count')
            need(len(segment['q_deg']) == 6, 'Six arm endpoints')
            final = [math.radians(x) for x in segment['q_deg']]
            for joint, a, b in zip(ARM, previous, final):
                j = model['joints'][joint]
                need(j['lower'] <= min(a, b) and max(a, b) <= j['upper'], 'Position endpoint limits')
                need(abs(b-a)*1.875/dur <= j['velocity'], 'Continuous quintic peak velocity limit')
            previous = final
        near(previous, [0.]*6, 0)
        minimum = float('inf')
        for step in range(round(duration*120)+1):
            target = target_at(program, name, step/120)
            floor, bounds = floor_and_bounds(model, fk(model, target['targets']), support)
            need(floor >= .001, 'Planned moving link clears desk in all sampled poses')
            minimum = min(minimum, floor)
            for i in range(3):
                low[i], high[i] = min(low[i], bounds['min'][i]), max(high[i], bounds['max'][i])
        result[name] = {'steps': round(duration*120), 'minimum_moving_link_z_m': minimum}
    return {'stages': result, 'planned_body_bounds': {'min': low, 'max': high},
            'cloud': {'bbox': {'min': low, 'max': high}}, 'scope': 'SAMPLED_DESK_CLEARANCE_NOT_SELF_COLLISION'}


def gravity_reference(model, poses, runtime_masses):
    frames = {}
    for p in poses:
        frames[p['name']] = (p['position'], quat(p['orientation_wxyz']))
    bodies = {b['name']: b for b in runtime_masses}
    children = {}
    for j in model['joints'].values():
        children.setdefault(j['parent'], []).append(j['child'])
    result = {}
    for name in model['movable']:
        j = model['joints'][name]
        pos, R = frames[j['child']]
        axis = mv(R, j['axis'])
        todo, total = [j['child']], 0.
        while todo:
            link = todo.pop()
            todo.extend(children.get(link, []))
            if link not in bodies:
                continue
            b = bodies[link]
            bp, br = frames[link]
            force = [0., 0., -9.81*b['mass']]
            centre = add(bp, mv(br, b['com']))
            contribution = cross(sub(centre, pos), force) if j['type'] == 'revolute' else force
            total += sum(x*y for x, y in zip(contribution, axis))
        # PhysX gravity compensation counters the external gravity torque/force.
        result[name] = -total
    return result


def check_runtime_inertias(model, rows):
    need(len(rows) == 11 and {b['name'] for b in rows} == set(PHYSICAL), 'Exact runtime mass rows')
    for b in rows:
        source = model['links'][b['name']]
        near(b['mass'], source['mass'], max(1e-6, source['mass']*1e-4))
        near(b['com'], source['com'], 2e-6)
        near(b['inertia_link_about_com'], source['inertia'], 2e-8)
    return {'mass_kg': sum(b['mass'] for b in rows), 'bodies': 11}


def verify_static(model, packet, cfg=None):
    """Actual stage readback packet; geometry facets are checked separately."""
    rows = packet['links']
    if isinstance(rows, dict):
        rows = [dict(b, name=n) for n, b in rows.items()]
    check_runtime_inertias(model, rows)
    world = fk(model, {})
    for b in rows:
        near(b['T_world'], world[b['name']], 2e-5)
        expected = model['links'][b['name']]
        need(b['visual_count'] == len(expected['visuals']) and b['collision_count'] == len(expected['collisions']),
             'Complete native visual/collision ownership')
    need(packet['fixed_base'] is True and packet['articulation_count'] == 1, 'Actual fixed-base world joint')
    need(packet['tool0']['physical'] is False, 'Frame-only tool0')
    near(packet['tool0']['T_world'], world['tool0'], 2e-5)
    joints = packet['joints']
    expected_names = (set(model['joints'])-{'tool0_mount'}) | {'root_joint'}
    need(len(joints) == 11 and {j['name'] for j in joints} == expected_names, 'Source joints plus world fixed root')
    # The frame-only tool0 joint is normalized away and root_joint replaces it.
    for a in joints:
        if a['name'] == 'root_joint':
            need(a['type'] == 'fixed' and a['child'] == 'Base' and a['enabled'] is True,
                 'Actual enabled world fixed root')
            continue
        source = model['joints'][a['name']]
        need(a['parent'] == source['parent'] and a['child'] == source['child'] and
             a['type'] == source['type'] and a['enabled'] is True, 'Native source joint identity')
        near(mm(a['anchor0'], inverse(a['anchor1'])), source['matrix'], 2e-5)
        if source['type'] != 'fixed':
            token = [float(a['axis'] == key) for key in ('X', 'Y', 'Z')]
            need(sum(token) == 1, 'Native joint axis token')
            near(mv([row[:3] for row in a['anchor1'][:3]], token), source['axis'], 2e-5)
            near([a['lower'], a['upper']], [source['lower'], source['upper']], 2e-5)
    return {'status': 'IMPORT_VERIFIED', 'mass_kg': sum(b['mass'] for b in rows), 'visuals': 47, 'physical_bodies': 11}


def verify_geometry(model, actual_triangles_by_link, kind='visual', tolerance=2e-6, visual_groups=None):
    """Compare full triangle multiplicities, not only counts or bounds; numeric imports are post-bootstrap only."""
    import numpy as np
    from scipy.spatial import cKDTree
    need(kind in ('visual', 'collision'), 'Closed native geometry role')
    if visual_groups is None:
        groups = {n: [('meshes/'+n+'.stl') if kind == 'visual' else ('meshes/collision/'+n+'.stl')] for n in PHYSICAL}
    else:
        need(kind == 'visual' and type(visual_groups) is dict and bool(visual_groups), 'Closed colored visual groups')
        need(all(type(n) is str and n and type(v) is list and v and all(type(p) is str for p in v)
                 for n, v in visual_groups.items()), 'Named nonempty visual source groups')
        supplied = [p for paths in visual_groups.values() for p in paths]
        expected_files = [v['file'] for n in PHYSICAL for v in model['links'][n]['visuals']]
        need(len(supplied) == len(set(supplied)) == len(expected_files) and set(supplied) == set(expected_files),
             'Exact complete source visual partition')
        groups = visual_groups
    need(set(actual_triangles_by_link) == set(groups), 'Every physical native mesh owner or colored group')
    metrics = {}
    dtype = np.dtype([('normal', '<f4', (3,)), ('v', '<f4', (3, 3)), ('attribute', '<u2')])
    for name, paths in groups.items():
        pieces = []
        for rel in paths:
            raw = path_in(model['model_dir'], rel).read_bytes()
            count = struct.unpack_from('<I', raw, 80)[0]
            need(count > 0 and len(raw) == 84+50*count, 'Binary STL complete length')
            pieces.append(np.frombuffer(raw, dtype=dtype, offset=84, count=count)['v'])
        expected = np.concatenate(pieces).astype(float)
        count = len(expected)
        actual = np.asarray(actual_triangles_by_link[name], dtype=float)
        need(actual.shape == expected.shape and np.isfinite(actual).all(), 'Full native facet census')
        order = np.lexsort((expected[:, :, 2], expected[:, :, 1], expected[:, :, 0]), axis=1)
        sorted_source = np.take_along_axis(expected, order[:, :, None], axis=1).reshape((-1, 9))
        unique, multiplicity = np.unique(sorted_source, axis=0, return_counts=True)
        triangles = unique.reshape((-1, 3, 3))
        tree = cKDTree(triangles.mean(axis=1))
        observed = np.zeros(len(unique), dtype=int)
        maximum = 0.
        for start in range(0, len(actual), 16384):
            block = actual[start:start+16384]
            k = min(4, len(unique))
            _, indices = tree.query(block.mean(axis=1), k=k)
            indices = np.asarray(indices).reshape((len(block), k))
            candidates = triangles[indices]
            distances = ((block[:, None, :, None, :] - candidates[:, :, None, :, :])**2).sum(axis=-1)
            score = np.maximum(distances.min(axis=3).max(axis=2), distances.min(axis=2).max(axis=2))
            best = score.argmin(axis=1)
            error = score[np.arange(len(block)), best]
            need(bool((error <= tolerance*tolerance).all()), 'Native facet vertex mismatch')
            chosen = indices[np.arange(len(block)), best]
            observed += np.bincount(chosen, minlength=len(unique))
            maximum = max(maximum, float(error.max(initial=0.))**.5)
        need(np.array_equal(observed, multiplicity), 'Native triangle multiplicity mismatch')
        metrics[name] = {'triangles': count, 'max_vertex_error_m': maximum, 'tolerance_m': tolerance}
    return metrics
