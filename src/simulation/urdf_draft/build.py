"""040 write-once CAD-derived URDF draft. No simulator or device access."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import types
import xml.etree.ElementTree as ET
import zipfile

NATIVE = 'models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft'
KIN = 'models/armold-mks-concept-v1/kinematics.json'
CORE = 'src/joint_frames/frames.py'
MAP = 'models/armold-mks-product-v2/bodies.json'
PARAMS = 'src/cad/armold-mks-product-v2/parameters.json'
PINS = {NATIVE: 'c784ee45bdbbba0b62eaa1218ebaba6b276d8f259c31baed8110174b96f84bc1',
        KIN: 'fe000e47a3885566a9ca808b053f429e13272da97a8dac132cb44b6153eeae50',
        CORE: '1eb5d41f439e5201ce0b0c5ee53222584082b8446bfef2e00a5bdd3eed5b4d46'}
I = [[float(i == j) for j in range(3)] for i in range(3)]
COLOURS = {'body': (236, 239, 241), 'accent': (237, 125, 49), 'dark': (43, 49, 56)}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def tr(a):
    return list(map(list, zip(*a)))


def mv(a, v):
    return [sum(x*y for x, y in zip(row, v)) for row in a]


def mm(a, b):
    return [[sum(x*y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


def rpy(a):
    pitch = math.asin(max(-1.0, min(1.0, -a[2][0])))
    need(abs(math.cos(pitch)) > 1e-8, 'Unsupported singular origin rotation')
    return [math.atan2(a[2][1], a[2][2]), pitch, math.atan2(a[1][0], a[0][0])]


def text(v):
    return ' '.join(format(float(x), '.15g') for x in v)


def core_module(root):
    # Only execute exact previously accepted local math bytes, after BUILDING.
    raw = (root / CORE).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == PINS[CORE], 'Unapproved core bytes')
    module = types.ModuleType('_urdf_approved_math')
    module.__file__ = str(root / CORE)
    sys.modules[module.__name__] = module
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


def read_inputs(root, export):
    for name, expected in PINS.items():
        need(sha(root / name) == expected, 'Pinned input changed: ' + name)
    with zipfile.ZipFile(root / NATIVE) as z:
        native = json.loads(z.read('document.json'))
    kin = json.loads((root / KIN).read_text(encoding='utf-8'))
    body_map = json.loads((root / MAP).read_text(encoding='utf-8'))['bodies']
    need(len(body_map) == 31 and len({b['name'] for b in body_map}) == 31, '31 unique bodies required')
    need(all(b['role'] in COLOURS and type(b['link']) is int and 0 <= b['link'] <= 6 for b in body_map), 'body map schema')
    names = ['Base'] + [f'Link{i}' for i in range(1, 7)]
    components = {c['id']: c['name'] for c in native['components']}
    need(sorted(components.values()) == sorted(names), 'Native components')
    occurrences = {o['id']: o for o in native['occurrences']}
    identity = [[float(i == j) for j in range(4)] for i in range(4)]
    need(len(occurrences) == 7, 'Native occurrence count')
    for o in occurrences.values():
        need(o['parent'] == 0 and o['transform'] == identity, 'Only identity world-root occurrences supported')
        need(o['grounded'] == (components[o['component']] == 'Base'), 'Native grounding')
    owners = {}
    for f in native['features']:
        for name in f.get('body_names', []):
            need(name not in owners, 'Duplicate native body creation')
            owners[name] = components[f['component']]
    need(set(owners) == {b['name'] for b in body_map}, 'Native body map coverage')
    for b in body_map:
        need(owners[b['name']] == names[b['link']], 'Native body ownership: ' + b['name'])
    need(len(native['assembly']['joints']) == 6, 'Native joint count')
    for i, (j, k) in enumerate(zip(native['assembly']['joints'], kin['joints'])):
        need(j['name'] == f'J{i+1}_DISPLAY_ZERO' and j['kind'] == 'revolute', 'Native joint identity')
        need(j['angle'] == 0 and j['values'] == [0.0], 'Native joint not at display zero')
        for end, expected in [('a', k['parent']), ('b', k['child'])]:
            need(components[occurrences[j[end]['occurrence']]['component']] == expected, 'Native joint chain')
        need(max(abs(x-y) for x, y in zip(j['a']['snap']['point'], k['origin_mm'])) < 1e-6, 'Native joint origin')
        need(max(abs(x-y) for x, y in zip(j['a']['snap']['z'], k['axis_world'])) < 1e-8, 'Native joint axis')
    with zipfile.ZipFile(export) as z:
        model = ET.fromstring(z.read('3D/3dmodel.model'))
    ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    need(model.get('unit') == 'millimeter', '3MF must be millimeter')
    objects = model.findall('m:resources/m:object', ns)
    items = model.findall('m:build/m:item', ns)
    need(len(objects) == len(items) == 31, '31 flat build objects required')
    need(len({o.get('id') for o in objects}) == len({i.get('objectid') for i in items}) == 31, 'Unique3MF ids')
    need({i.get('objectid') for i in items} == {o.get('id') for o in objects}, '3MF build coverage')
    need(all(i.get('transform') is None for i in items), '3MF build transform unsupported')
    meshes = {}
    for o in objects:
        name = o.get('name')
        need(name not in meshes and name in owners, 'Unknown/duplicate mesh name')
        vertices = [tuple(float(v.get(c)) for c in ('x', 'y', 'z')) for v in o.findall('m:mesh/m:vertices/m:vertex', ns)]
        triangles = [tuple(int(t.get(c)) for c in ('v1', 'v2', 'v3')) for t in o.findall('m:mesh/m:triangles/m:triangle', ns)]
        need(vertices and triangles, 'Empty visual mesh')
        need(all(math.isfinite(x) for v in vertices for x in v), 'Nonfinite vertex')
        need(all(0 <= i < len(vertices) for t in triangles for i in t), 'Triangle index outside vertices')
        meshes[name] = (vertices, triangles)
    need(set(meshes) == set(owners), 'Mesh/body coverage')
    return kin, body_map, meshes


def stl_write(path, vertices, triangles):
    with path.open('wb') as f:
        f.write(b'robot-arm-lab SIMULATION DRAFT metres'.ljust(80, b'\0'))
        f.write(struct.pack('<I', len(triangles)))
        for t in triangles:
            a, b, c = [vertices[i] for i in t]
            u, v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
            n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            length = math.sqrt(sum(x*x for x in n))
            n = [x/length for x in n] if length else [0., 0., 0.]
            f.write(struct.pack('<12fH', *n, *a, *b, *c, 0))


def bounds(vertices):
    lo, hi = [min(v[i] for v in vertices) for i in range(3)], [max(v[i] for v in vertices) for i in range(3)]
    return [(lo[i]+hi[i])/2 for i in range(3)], [hi[i]-lo[i] for i in range(3)]


def make_package(root, out, export, cfg_path):
    kin, mapping, meshes = read_inputs(root, export)
    core = core_module(root)
    layout = core.decode((root / KIN).read_bytes())
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    need(cfg['status'] == 'SIMULATION_ASSUMPTION' and cfg['physical_verified'] is False, 'Assumption flags')
    need(len(cfg['mass_kg']) == 7 and all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in cfg['mass_kg']), 'Assumed masses')
    need(len(cfg['effort_Nm']) == 6 and all(type(x) in (int, float) and x > 0 and math.isfinite(x) for x in cfg['effort_Nm']), 'Assumed effort')
    scalars = [cfg[k] for k in ('joint_limit_deg', 'velocity_rad_s', 'damping_Nm_s_rad', 'friction_Nm')]
    need(all(type(x) in (int, float) and math.isfinite(x) for x in scalars), 'Finite assumption scalars')
    need(0 < cfg['joint_limit_deg'] <= 170 and cfg['velocity_rad_s'] > 0 and cfg['damping_Nm_s_rad'] >= 0 and cfg['friction_Nm'] >= 0, 'Assumed limits')
    need(all(cfg[k] is None for k in ('can_ids', 'motor_signs', 'measured_gear_ratios', 'physical_zeros', 'encoder_scales')), 'Physical mapping remains unknown')
    frames = [([0., 0., 0.], I)] + [(j['origin_mm'], j['R_child']) for j in kin['joints']]
    out.mkdir(parents=True, exist_ok=False)
    (out / 'meshes').mkdir()
    robot = ET.Element('robot', name='robot_arm_lab_v2_simulation_draft')
    robot.append(ET.Comment('SIMULATION ONLY. Assumed mass/inertia/limits. q=0 is CAD display pose. Hardware unapproved.'))
    for role, rgb in COLOURS.items():
        material = ET.SubElement(robot, 'material', name=role)
        ET.SubElement(material, 'color', rgba=text([x/255 for x in rgb] + [1.]))
    rows, local_meshes = [], {}
    for i in range(7):
        origin, rotation = frames[i]
        link = ET.SubElement(robot, 'link', name='Base' if i == 0 else f'Link{i}')
        all_vertices = []
        for b in [b for b in mapping if b['link'] == i]:
            world, triangles = meshes[b['name']]
            vertices = [[x/1000 for x in mv(tr(rotation), [v[k]-origin[k] for k in range(3)])] for v in world]
            path = f"meshes/{b['name']}.stl"
            stl_write(out / path, vertices, triangles)
            visual = ET.SubElement(link, 'visual', name=b['name'])
            ET.SubElement(ET.SubElement(visual, 'geometry'), 'mesh', filename=path, scale='1 1 1')
            ET.SubElement(visual, 'material', name=b['role'])
            all_vertices.extend(vertices)
            local_meshes[b['name']] = (vertices, triangles, b)
        center, size = bounds(all_vertices)
        need(all(x > 0 and math.isfinite(x) for x in size), 'Link box dimensions')
        mass = cfg['mass_kg'][i]
        inertia = [mass*(size[1]**2+size[2]**2)/12, mass*(size[0]**2+size[2]**2)/12, mass*(size[0]**2+size[1]**2)/12]
        inertial = ET.SubElement(link, 'inertial')
        ET.SubElement(inertial, 'origin', xyz=text(center), rpy='0 0 0')
        ET.SubElement(inertial, 'mass', value=str(mass))
        ET.SubElement(inertial, 'inertia', ixx=str(inertia[0]), iyy=str(inertia[1]), izz=str(inertia[2]), ixy='0', ixz='0', iyz='0')
        collision = ET.SubElement(link, 'collision', name='assumed_aabb_proxy')
        ET.SubElement(collision, 'origin', xyz=text(center), rpy='0 0 0')
        ET.SubElement(ET.SubElement(collision, 'geometry'), 'box', size=text(size))
        rows.append({'link': link.get('name'), 'status': 'SIMULATION_ASSUMPTION', 'mass_kg': mass,
                     'com_m': center, 'box_size_m': size, 'inertia_kg_m2': inertia})
    joint_rows = []
    for i, j in enumerate(kin['joints']):
        po, pr = frames[i]
        xyz = [x/1000 for x in mv(tr(pr), [j['origin_mm'][k]-po[k] for k in range(3)])]
        fixed = mm(tr(pr), j['R_child'])
        axis = mv(tr(j['R_child']), j['axis_world'])
        need(max(abs(x-y) for x, y in zip(axis, j['axis_parent_zero'])) < 1e-8, 'Local canonical axis')
        joint = ET.SubElement(robot, 'joint', name=j['name'], type='revolute')
        ET.SubElement(joint, 'parent', link=j['parent'])
        ET.SubElement(joint, 'child', link=j['child'])
        ET.SubElement(joint, 'origin', xyz=text(xyz), rpy=text(rpy(fixed)))
        ET.SubElement(joint, 'axis', xyz=text(axis))
        limit = math.radians(cfg['joint_limit_deg'])
        ET.SubElement(joint, 'limit', lower=str(-limit), upper=str(limit), effort=str(cfg['effort_Nm'][i]), velocity=str(cfg['velocity_rad_s']))
        ET.SubElement(joint, 'dynamics', damping=str(cfg['damping_Nm_s_rad']), friction=str(cfg['friction_Nm']))
        joint_rows.append({'joint': j['name'], 'pose_deg': j['pose_deg'], 'urdf_zero': 'CAD_DISPLAY_POSE', 'q_urdf': 'canonical_delta_rad', 'q_geometric': 'q_urdf + radians(pose_deg)', 'physical_zero_verified': False})
    ET.indent(robot)
    ET.ElementTree(robot).write(out / 'robot_arm.urdf', encoding='utf-8', xml_declaration=True)
    params = json.loads((root / PARAMS).read_text(encoding='utf-8'))
    tool_x = (json.loads((root / 'models/armold-mks-concept-v1/parameters.json').read_text())['reducer_depth_mm']/2 + params['links']['tool']['flange_t'] + params['links']['tool']['ring_t'])/1000
    write_json(out / 'assumptions.json', {**cfg, 'links': rows, 'joints': joint_rows, 'tcp_candidate': {'link': 'Link6', 'xyz_m': [tool_x, 0, 0], 'status': 'CAD_NOMINAL_NOT_CALIBRATED'}, 'hardware_approved': False, 'isaac_import': 'NOT_RUN', 'rl_training': 'NOT_RUN'})
    inputs = [root / n for n in (NATIVE, KIN, CORE, MAP, PARAMS, 'models/armold-mks-concept-v1/parameters.json')] + [export, cfg_path]
    input_hashes = {str(p): sha(p) for p in inputs}
    generators = {p.name: sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    write_json(out / 'provenance.json', {'basis': 'Latest full product-exterior-v2, not a fabricated/internal reducer model', 'inputs': input_hashes, 'generator_files_sha256': generators, 'export_cli_version': '0.23.0', 'preflight': json.loads((root / '.dev/urdf-draft-evidence/preflight/hashes.json').read_text(encoding='utf-8-sig')), 'geometry_scope': 'Tessellation conversion and placement only; ring topology/strength/contact not accepted'})
    # Imports occur after the caller has written BUILDING and inside its failure boundary.
    from verify import verify
    result = verify(out, root, export, require_manifest=False)
    write_json(out / 'validation.json', result)
    from preview import render
    render(out, root)
    from readme import write_readme
    write_readme(out)
    need(all(sha(Path(p)) == h for p, h in input_hashes.items()), 'Input changed during generation')
    write_json(out / 'manifest.json', {'status': 'URDF_DRAFT_STATIC_VALIDATED', 'isaac_import': 'NOT_RUN', 'files': {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}})
    return verify(out, root, export)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument('--out', type=Path)
    ap.add_argument('--export', type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    evidence = root / '.dev/urdf-draft-evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    status = evidence / 'build-status.json'
    write_json(status, {'status': 'BUILDING', 'hardware_approved': False})
    try:
        out = args.out or root / 'models/robot-arm-urdf-v1'
        export = args.export or evidence / 'preflight/v2-current.3mf'
        result = make_package(root, out, export, Path(__file__).with_name('assumptions.json'))
        write_json(status, {'status': 'URDF_DRAFT_STATIC_VALIDATED', 'output': str(out), 'isaac_import': 'NOT_RUN', 'hardware_approved': False})
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        write_json(status, {'status': 'FAILED', 'reason': type(exc).__name__ + ': ' + str(exc), 'hardware_approved': False})
        raise


if __name__ == '__main__':
    main()
