"""Reparse written URDF/STL and compare to source CAD/accepted FK. No physics runtime."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


def need(ok, why):
    if not ok:
        raise ValueError(why)


def values(s, n):
    x = list(map(float, s.split()))
    need(len(x) == n and all(math.isfinite(v) for v in x), 'Finite vector length')
    return x


def recorded_vector(v):
    need(isinstance(v, list) and len(v) == 3 and
         all(type(x) in (int, float) and math.isfinite(x) for x in v), 'Recorded finite vector')
    return v


def multiply(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def apply(a, x):
    return [sum(a[i][k]*x[k] for k in range(3)) for i in range(3)]


def euler(v):
    cr, cp, cy = [math.cos(x) for x in v]
    sr, sp, sy = [math.sin(x) for x in v]
    return [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
            [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]


def axis_rotation(a, q):
    c, s, v = math.cos(q), math.sin(q), 1-math.cos(q)
    x, y, z = a
    return [[c+x*x*v, x*y*v-z*s, x*z*v+y*s], [y*x*v+z*s, c+y*y*v, y*z*v-x*s], [z*x*v-y*s, z*y*v+x*s, c+z*z*v]]


def stl_triangles(p):
    raw = p.read_bytes()
    need(len(raw) >= 84, 'STL header')
    count = struct.unpack_from('<I', raw, 80)[0]
    need(count > 0 and len(raw) == 84+50*count, 'STL count/length')
    triangles = []
    for offset in range(84, len(raw), 50):
        row = struct.unpack_from('<12fH', raw, offset)
        need(all(math.isfinite(x) for x in row[:12]), 'STL nonfinite')
        triangles.append([row[i:i+3] for i in (3, 6, 9)])
    return triangles


def urdf_fk(joints, angles):
    p, r, out = [0., 0., 0.], [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]], []
    for j, angle in zip(joints, angles):
        origin = j.find('origin')
        offset = apply(r, values(origin.get('xyz'), 3))
        p = [p[i]+offset[i] for i in range(3)]
        r = multiply(multiply(r, euler(values(origin.get('rpy'), 3))), axis_rotation(values(j.find('axis').get('xyz'), 3), angle))
        out.append((p, r))
    return out


def verify(package, root, export, require_manifest=True):
    from build import read_inputs, core_module, KIN
    package, root, export = Path(package).resolve(), Path(root).resolve(), Path(export).resolve()
    kin, mapping, source_meshes = read_inputs(root, export)
    core = core_module(root)
    layout = core.decode((root / KIN).read_bytes())
    robot = ET.parse(package / 'robot_arm.urdf').getroot()
    cfg = json.loads((package / 'assumptions.json').read_text(encoding='utf-8'))
    need(cfg['status'] == 'SIMULATION_ASSUMPTION' and cfg['physical_verified'] is False and cfg['hardware_approved'] is False, 'Unapproved assumptions required')
    need(cfg['isaac_import'] == cfg['rl_training'] == 'NOT_RUN', 'Runtime status')
    need(all(cfg[k] is None for k in ('can_ids', 'motor_signs', 'measured_gear_ratios', 'physical_zeros', 'encoder_scales')), 'Physical mapping unknown')
    names = ['Base'] + [f'Link{i}' for i in range(1, 7)]
    need(len(cfg['links']) == 7, 'Seven recorded link assumptions')
    links, joints = robot.findall('link'), robot.findall('joint')
    need(robot.tag == 'robot' and [l.get('name') for l in links] == names, 'Seven-link tree/order')
    need(len(joints) == 6, 'Six joints required')
    for i, j in enumerate(joints):
        need(j.get('type') == 'revolute' and j.get('name') == f'J{i+1}', 'Joint type/name')
        need(j.find('parent').get('link') == names[i] and j.find('child').get('link') == names[i+1], 'Parent/child chain')
        axis = values(j.find('axis').get('xyz'), 3)
        need(abs(sum(x*x for x in axis)-1) < 1e-10, 'Unit joint axis')
        limit = j.find('limit')
        need(abs(float(limit.get('lower')) + math.radians(cfg['joint_limit_deg'])) < 1e-12, 'Joint lower')
        need(abs(float(limit.get('upper')) - math.radians(cfg['joint_limit_deg'])) < 1e-12, 'Joint upper')
        speed, effort = float(limit.get('velocity')), float(limit.get('effort'))
        need(math.isfinite(speed) and math.isfinite(effort) and speed == cfg['velocity_rad_s'] > 0 and effort == cfg['effort_Nm'][i] > 0, 'Velocity/effort assumptions')
        need(float(j.find('dynamics').get('damping')) == cfg['damping_Nm_s_rad'] and float(j.find('dynamics').get('friction')) == cfg['friction_Nm'], 'Dynamics assumptions')
    poses = [[0.]*6, [-math.radians(j['pose_deg']) for j in kin['joints']]]
    for i in range(6):
        for angle in (-math.pi/6, math.pi/6):
            q = [0.]*6
            q[i] = angle
            poses.append(q)
    poses += [[math.radians(x) for x in (15, -20, 25, 10, -15, 20)], [math.radians(x) for x in (-15, 20, -25, -10, 15, -20)]]
    max_pos, max_rot = 0., 0.
    for q in poses:
        actual, expected = urdf_fk(joints, q), core.fk(layout, q)
        for (p, r), e in zip(actual, expected):
            max_pos = max(max_pos, max(abs(x-y) for x, y in zip(p, e['origin_m'])))
            max_rot = max(max_rot, max(abs(r[a][b]-e['rotation_world'][a][b]) for a in range(3) for b in range(3)))
    need(max_pos < 1e-10 and max_rot < 1e-10, 'Reparsed URDF FK mismatch')
    display = [([0., 0., 0.], [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])] + urdf_fk(joints, [0.]*6)
    by_name = {b['name']: b for b in mapping}
    seen, triangle_count, max_vertex = set(), 0, 0.
    for i, link in enumerate(links):
        all_vertices = []
        for visual in link.findall('visual'):
            name = visual.get('name')
            need(name in by_name and name not in seen and by_name[name]['link'] == i, 'Visual ownership')
            seen.add(name)
            need(visual.find('origin') is None, 'Visual origin must be baked into local vertices')
            need(visual.find('material').get('name') == by_name[name]['role'], 'CAD material role')
            mesh = visual.find('geometry/mesh')
            need(values(mesh.get('scale'), 3) == [1., 1., 1.], 'Mesh metre scale')
            relative = Path(mesh.get('filename'))
            need(not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == f'meshes/{name}.stl', 'Unsafe/mismatched mesh path')
            path = (package / relative).resolve()
            need(path.is_relative_to(package), 'Mesh escapes package')
            triangles = stl_triangles(path)
            original_v, original_t = source_meshes[name]
            need(len(triangles) == len(original_t), 'Mesh triangles changed')
            p, r = display[i]
            for triangle, indices in zip(triangles, original_t):
                for v, index in zip(triangle, indices):
                    all_vertices.append(v)
                    world = [a+b for a, b in zip(p, apply(r, v))]
                    max_vertex = max(max_vertex, max(abs(world[k]-original_v[index][k]/1000) for k in range(3)))
            triangle_count += len(triangles)
        need(all_vertices, 'Empty link')
        lo, hi = [min(v[k] for v in all_vertices) for k in range(3)], [max(v[k] for v in all_vertices) for k in range(3)]
        center, size = [(lo[k]+hi[k])/2 for k in range(3)], [hi[k]-lo[k] for k in range(3)]
        need(all(x > 0 and math.isfinite(x) for x in size), 'Positive actual STL box dimensions')
        # Sidecar rows describe this actual link, not an independent inertia basis.
        row = cfg['links'][i]
        need(row['link'] == names[i] and row['status'] == 'SIMULATION_ASSUMPTION', 'Recorded link identity/status')
        recorded_size = recorded_vector(row['box_size_m'])
        length_tolerance = 1e-7  # metres; covers pre-STL double vs written float32 bounds.
        need(max(abs(x-y) for x, y in zip(recorded_size, size)) < length_tolerance, 'Recorded box differs from actual STL')
        need(max(abs(x-y) for x, y in zip(recorded_vector(row['com_m']), center)) < length_tolerance, 'Recorded COM differs from actual STL')
        proxy = link.find('collision')
        need(len(link.findall('collision')) == 1, 'One proxy per link')
        geometry = proxy.find('geometry')
        need(len(geometry) == 1 and geometry[0].tag == 'box', 'Collision must be one local AABB box')
        need(values(proxy.find('origin').get('rpy', '0 0 0'), 3) == [0., 0., 0.], 'Collision local AABB rotation')
        need(max(abs(x-y) for x, y in zip(size, values(proxy.find('geometry/box').get('size'), 3))) < 1e-7, 'Collision size')
        need(max(abs(x-y) for x, y in zip(center, values(proxy.find('origin').get('xyz'), 3))) < 1e-7, 'Collision center')
        need(len(link.findall('inertial')) == 1, 'One inertial per link')
        inertial = link.find('inertial')
        need(values(inertial.find('origin').get('rpy', '0 0 0'), 3) == [0., 0., 0.], 'Inertia local AABB rotation')
        mass = float(inertial.find('mass').get('value'))
        need(math.isfinite(mass) and mass > 0 and mass == cfg['mass_kg'][i], 'Assumed mass mismatch')
        need(type(row['mass_kg']) in (int, float) and row['mass_kg'] == mass, 'Recorded mass mismatch')
        com = values(inertial.find('origin').get('xyz'), 3)
        need(max(abs(x-y) for x, y in zip(com, center)) < 1e-7, 'Assumed COM mismatch')
        tensor = inertial.find('inertia')
        diag = [float(tensor.get(k)) for k in ('ixx', 'iyy', 'izz')]
        need(all(math.isfinite(x) and x > 0 for x in diag), 'Inertia positive/finite')
        need(all(float(tensor.get(k)) == 0 for k in ('ixy', 'ixz', 'iyz')), 'Inertia box axes')
        need(max(abs(x-y) for x, y in zip(diag, recorded_vector(row['inertia_kg_m2']))) < 1e-12, 'Recorded inertia mismatch')
        for k, (a, b) in enumerate(((1, 2), (0, 2), (0, 1))):
            recorded_inertia = mass*(recorded_size[a]**2+recorded_size[b]**2)/12
            need(abs(diag[k]-recorded_inertia) < 1e-12, 'Inertia recorded formula')
            actual_inertia = mass*(size[a]**2+size[b]**2)/12
            # Propagate the bound error in each length through m*(a²+b²)/12.
            error_bound = mass*(2*length_tolerance*(abs(size[a])+abs(size[b])) + 2*length_tolerance**2)/12 + 1e-12
            need(abs(diag[k]-actual_inertia) <= error_bound, 'Inertia actual STL formula')
        need(all(diag[k] <= sum(diag)-diag[k]+1e-12 for k in range(3)), 'Inertia triangle inequality')
    need(seen == set(by_name) and max_vertex < 1e-7, 'Visual world conversion mismatch')
    if require_manifest:
        manifest = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
        need(manifest['status'] == 'URDF_DRAFT_STATIC_VALIDATED' and manifest['isaac_import'] == 'NOT_RUN', 'Manifest draft status')
        actual_names = {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file() and p.name != 'manifest.json'}
        need(actual_names == set(manifest['files']), 'Manifest file-set mismatch')
        for name, expected in manifest['files'].items():
            path = (package / name).resolve()
            need(path.is_relative_to(package) and hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Manifest hash/path mismatch')
        provenance = json.loads((package / 'provenance.json').read_text(encoding='utf-8'))
        need(all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in provenance['inputs'].items()), 'Provenance input drift')
        producer = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
        need(producer == provenance['generator_files_sha256'], 'Generator source drift')
    return {'status': 'URDF_DRAFT_STATIC_VALIDATED', 'physical_links': 7, 'revolute_joints': 6,
            'visual_bodies': len(seen), 'triangles': triangle_count, 'fk_poses': len(poses),
            'max_fk_position_error_m': max_pos, 'max_fk_rotation_component_error': max_rot,
            'max_stl_world_vertex_error_m': max_vertex, 'assumed_mass_kg': sum(cfg['mass_kg']),
            'mass_inertia_verified': False, 'collision_physics': 'NOT_VALIDATED_AABB_PROXIES',
            'ring_geometry': 'DEFERRED', 'isaac_import': 'NOT_RUN', 'rl_training': 'NOT_RUN', 'hardware_approved': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('package', type=Path)
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument('--export', type=Path)
    a = ap.parse_args()
    print(json.dumps(verify(a.package, a.root, a.export or a.root / '.dev/urdf-draft-evidence/preflight/v2-current.3mf')))
