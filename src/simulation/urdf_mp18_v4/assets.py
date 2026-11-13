"""118 A: read-only CAD inputs -> mesh/numeric scaffolding. NEVER authors XML."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np
import trimesh

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / 'models/robot-arm-urdf-v4'
OUT = ROOT / 'outputs/urdf-mp18-v4-118/A'
CAD = ROOT / 'src/cad/manipulator-v2'
ARM = ['Base'] + [f'Link{i}' for i in range(1, 7)]
GROUPS = {'F': 'KG1', 'A': 'KG1_A', 'B': 'KG1_B', 'R': 'KG1_R'}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def readj(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        require(math.isfinite(float(value)), 'Nonfinite derived value')
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def owned(path):
    path = Path(path).resolve()
    require(path.is_relative_to(MODEL.resolve()) or path.is_relative_to(OUT.resolve()), 'Output outside A ownership')
    require(path.suffix.lower() not in ('.urdf', '.xml'), 'A never writes XML')
    return path


def writej(path, value):
    path = owned(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + str(time.monotonic_ns()) + '.tmp')
    temporary.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def module(path, name):
    path = Path(path)
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def readonly_bodies(layout):
    """Execute only the inspected original main prefix, before nested world(q)."""
    path = CAD / 'loads_arm.py'
    raw = path.read_bytes()
    tree = ast.parse(raw, filename=str(path))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    boundary = next(i for i, n in enumerate(main.body) if isinstance(n, ast.FunctionDef) and n.name == 'world')
    prefix = main.body[:boundary]
    calls = [n for n in ast.walk(ast.Module(body=prefix, type_ignores=[])) if isinstance(n, ast.Call)]
    require(not any(isinstance(n.func, ast.Attribute) and n.func.attr.startswith(('write', 'mkdir', 'export')) for n in calls), 'Prefix contains writes')
    cli = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == 'parse_args']
    require(len(cli) == 1 and not cli[0].args, 'Expected sole original CLI parse')
    cli[0].args = [ast.List(elts=[], ctx=ast.Load())]
    prefix.append(ast.Return(value=ast.Dict(keys=[ast.Constant(k) for k in ('bodies', 'P', 'Fr', 'Ts0', 'cat')], values=[ast.Name(id=k, ctx=ast.Load()) for k in ('bodies', 'P', 'Fr', 'Ts0', 'cat')])))
    fn = ast.FunctionDef(name='_readonly_prefix', args=main.args, body=prefix, decorator_list=[], returns=None, type_comment=None, type_params=[])
    safe_top = []
    for node in tree.body:
        if isinstance(node, ast.Import) and any(a.name == 'layout' for a in node.names):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign)) or (isinstance(node, ast.FunctionDef) and node.name == 'box_inertia'):
            safe_top.append(node)
    env = {'__file__': str(path), '__name__': '_readonly118_loads_prefix', 'L': layout}
    exec(compile(ast.fix_missing_locations(ast.Module(body=safe_top + [fn], type_ignores=[])), str(path) + ':read-only-prefix', 'exec'), env)
    result = env['_readonly_prefix']()
    return result, {'source': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest(), 'main_prefix_start_line': main.body[0].lineno, 'excluded_world_and_rest_start_line': main.body[boundary].lineno, 'cli_override': 'parse_args([])', 'source_modified': False, 'torque_and_output_main_executed': False}


def moved(mesh, transform_mm):
    value = mesh.copy()
    value.apply_transform(transform_mm)
    value.apply_scale(.001)
    return value


def tensor_component(name, link, mass, c_mm, inertia, transform_mm, method, source_name, geometry_ids=None):
    transform_mm = np.asarray(transform_mm, float)
    c = (transform_mm @ np.r_[np.asarray(c_mm, float), 1])[:3] * .001
    R = transform_mm[:3, :3]
    I = R @ np.asarray(inertia, float) @ R.T
    return {'id': 'mass:' + name, 'name': name, 'link': link, 'source_record_name': source_name,
            'source_mass_kg': float(mass), 'source_com_mm': np.asarray(c_mm), 'source_inertia_kg_m2': np.asarray(inertia),
            'T_link_from_source_mm': transform_mm, 'mass_kg': float(mass), 'com_m': c,
            'inertia_kg_m2': I, 'method': method, 'geometry_component_ids': geometry_ids or []}


def aggregate(rows):
    mass = sum(r['mass_kg'] for r in rows)
    require(mass > 0, 'Positive aggregate mass')
    c = sum(r['mass_kg'] * np.asarray(r['com_m']) for r in rows) / mass
    I = np.zeros((3, 3))
    for row in rows:
        d = np.asarray(row['com_m']) - c
        I += np.asarray(row['inertia_kg_m2']) + row['mass_kg'] * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    I = (I + I.T) / 2
    eig = np.linalg.eigvalsh(I)
    require(np.all(eig > 0) and eig[-1] <= eig[:2].sum() + 1e-12, 'Invalid aggregate inertia')
    return mass, c, I, eig


def save_mesh(path, meshes):
    require(bool(meshes), 'Empty link mesh')
    path = owned(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.util.concatenate(meshes)
    mesh.export(path, file_type='stl')
    saved = trimesh.load(path, force='mesh', process=False)
    return {'file': path.relative_to(MODEL).as_posix(), 'sha256': sha(path), 'bytes': path.stat().st_size,
            'triangles': len(saved.faces), 'bounds_m': saved.bounds.tolist()}


def pin_audit(records, aliases):
    output = []
    for key, expected in records.items():
        path = aliases.get(key)
        output.append({'record_key': key, 'path': path.relative_to(ROOT).as_posix() if path else None,
                       'expected_sha256': expected, 'actual_sha256': sha(path) if path and path.is_file() else None,
                       'match': bool(path and path.is_file() and sha(path) == expected)})
    return output


def source_pin_checks():
    """Current CAD proof pins, not a new CAD build or loads-main execution."""
    L = module(CAD / 'layout.py', '_mp18_pin_layout118')
    load = readj(ROOT / '.dev/mp18-evidence/loads/loads.json')
    aliases = {f'parts/{n}.stl': L.MODEL / 'parts' / f'{n}.stl' for n in L.NEW_PARTS}
    aliases.update({'printprep.json': L.EV / 'printprep.json', 'inputs.json(MP5)': ROOT / 'src/cad/review-mp5/inputs.json',
                    'printprep.json(MP16)': ROOT / '.dev/mp16-evidence/printprep.json', 'sizing.json(MP16)': ROOT / '.dev/mp16-evidence/sizing/sizing.json',
                    'mass-properties.json(MP10)': ROOT / 'models/j5-wrist-v1/mass-properties.json', 'mass-properties.json(KG1)': ROOT / 'models/kmjh-gripper-v1/mass-properties.json',
                    'parameters.json': CAD / 'parameters.json', 'loads_arm.py': CAD / 'loads_arm.py', 'layout.py': CAD / 'layout.py'})
    build = readj(ROOT / '.dev/mp18-evidence/build/build-record.json')
    build_aliases = {'parameters.json': CAD / 'parameters.json', 'build_arm.py': CAD / 'build_arm.py', 'layout.py': CAD / 'layout.py',
                     'j5geom.py(MP10)': ROOT / 'src/cad/j5-wrist-v1/j5geom.py', 'parameters.json(MP10)': ROOT / 'src/cad/j5-wrist-v1/parameters.json',
                     'parameters.json(MP16)': ROOT / 'src/cad/j23-drive-v1/parameters.json', 'print-fits.json': ROOT / 'src/cad/calibration/print-fits.json',
                     'motor-mks42d.json': ROOT / 'src/cad/calibration/motor-mks42d.json', 'cycloid.json(MP6)': ROOT / 'models/cycloid-27-v1/cycloid.json',
                     'v1 parameters.json': ROOT / 'models/armold-mks-concept-v1/parameters.json'}
    outputs = {key: L.MODEL / key for key in build['outputs_sha256']}
    require(all(path.resolve().is_relative_to(L.MODEL.resolve()) for path in outputs.values()), 'Build output proof paths')
    loads = pin_audit(load['inputs_sha256'], aliases)
    build_in = pin_audit(build['inputs_sha256'], build_aliases)
    build_out = pin_audit(build['outputs_sha256'], outputs)
    require(len(loads) == 50 and len(build_in) == 10 and len(build_out) == 44, 'Exact current loads50/build10+44 proof census')
    records = loads + build_in + build_out
    require(all(item['match'] for item in records), 'Current CAD loads/build proof hash mismatch')
    return {'load_pins_match': loads, 'build_pins_match': build_in + build_out,
            'build_input_pins_match': build_in, 'build_output_pins_match': build_out}, sorted(set(aliases.values()) | set(build_aliases.values()) | set(outputs.values()))


def finalize_pin_audit():
    """Explicit metadata-only revision; mesh/numerical values/XML are untouched."""
    checks, paths = source_pin_checks()
    stage_before = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in paths}
    writej(OUT / 'input-pin-audit-before.json', stage_before)
    numeric = readj(MODEL / 'numeric-ledger.json')
    structural_keys = ('links', 'frames', 'joints', 'totals', 'KG1_mount_T_Link6_from_G_mm', 'gripper_asset_reference')
    structural_before = json.dumps({k: numeric[k] for k in structural_keys}, sort_keys=True, separators=(',', ':'))
    mesh_before = {p.relative_to(MODEL).as_posix(): sha(p) for p in (MODEL / 'meshes').rglob('*.stl')}
    asset_before = sha(MODEL / 'asset-ledger.json')
    original_census = readj(OUT / 'input-before.json')
    require(all(sha(ROOT / p) == record['sha256'] and (ROOT / p).stat().st_size == record['bytes'] for p, record in original_census.items()), 'Original generation inputs changed before metadata audit')
    stage_after = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in paths}
    require(stage_before == stage_after, 'Pin audit input drift')
    writej(OUT / 'input-pin-audit-after.json', stage_after)
    numeric['sourcechecks'].update(checks)
    numeric['sourcechecks'].update(pin_audit_preserved=True, generation_input_count=len(original_census), pin_audit_input_count=len(stage_before))
    writej(MODEL / 'numeric-ledger.json', numeric)
    provenance = readj(MODEL / 'provenance.json')
    provenance['generation_assets_code_sha256'] = provenance['assets_code_sha256']
    provenance['assets_code_sha256'] = sha(__file__)
    provenance['pin_audit'] = {'mode': 'METADATA_ONLY_NO_MESH_NUMERIC_XML_REGENERATION', 'input_records': checks,
                              'generation_census': 'outputs/urdf-mp18-v4-118/A/input-before.json',
                              'pin_audit_before': 'outputs/urdf-mp18-v4-118/A/input-pin-audit-before.json',
                              'pin_audit_after': 'outputs/urdf-mp18-v4-118/A/input-pin-audit-after.json',
                              'original_generation_files': len(original_census), 'additional_pin_inputs_first_read_at_audit': [p for p in stage_before if p not in original_census]}
    writej(MODEL / 'provenance.json', provenance)
    after_numeric = readj(MODEL / 'numeric-ledger.json')
    require(structural_before == json.dumps({k: after_numeric[k] for k in structural_keys}, sort_keys=True, separators=(',', ':')), 'Metadata revision changed numerical values')
    require(mesh_before == {p.relative_to(MODEL).as_posix(): sha(p) for p in (MODEL / 'meshes').rglob('*.stl')}, 'Metadata revision changed meshes')
    require(asset_before == sha(MODEL / 'asset-ledger.json'), 'Metadata revision changed component ledger')
    writej(OUT / 'pin-audit-result.json', {'load50_match': True, 'build_inputs10_match': True, 'build_outputs44_match': True,
           'input_stage_preserved': True, 'original_generation_inputs_preserved': True, 'numeric_values_unchanged': True, 'mesh_hashes_unchanged': True,
           'component_ledger_unchanged': True, 'XML_written': False, 'assets_code_sha256': sha(__file__),
           'outputs': {n: {'sha256': sha(MODEL / n), 'bytes': (MODEL / n).stat().st_size} for n in ('numeric-ledger.json', 'asset-ledger.json', 'provenance.json')}})
    print(json.dumps({'load50': True, 'build_inputs10': True, 'build_outputs44': True, 'metadata_only': True}), flush=True)


def prepare():
    started = time.monotonic()
    before = readj(OUT / 'input-before.json')
    require(not (MODEL / 'numeric-ledger.json').exists(), 'Explicit asset revision required; no overwrite')
    L = module(CAD / 'layout.py', '_mp18_layout118')
    prefix, prefix_meta = readonly_bodies(L)
    P, Fr, Ts0, cat, bodies = (prefix[k] for k in ('P', 'Fr', 'Ts0', 'cat', 'bodies'))
    source_loads = readj(ROOT / '.dev/mp18-evidence/loads/loads.json')
    expected = source_loads['bodies']
    require(len(bodies) == len(expected) == 173, 'Original173 body inventory')
    original_records = []
    for row, recorded in zip(bodies, expected):
        name, link, mass, c, frame, I = row
        require(name == recorded['name'] and link == recorded['link'] and round(float(mass), 4) == recorded['kg'], 'Original mass row mismatch: ' + name)
        original_records.append({'name': name, 'link': link, 'unrounded_kg': float(mass), 'rounded4_kg': round(float(mass), 4), 'ledger_rounded4_kg': recorded['kg'], 'match': True})
    original_total = sum(float(r[2]) for r in bodies)
    require(round(original_total, 4) == source_loads['mass_kg']['total'], 'Original total independently rounded')
    display = P['poses']['display_deg']
    Td = L.link_transforms(P, display)
    inv0 = [np.linalg.inv(t) for t in Ts0]
    mount = inv0[6] @ Fr['G']
    frame_world = {ARM[k]: Td[k] for k in range(7)}
    frame_world.update({name: Td[6] @ mount for name in GROUPS.values()})
    pivot = np.eye(4); pivot[2, 3] = 26.
    frame_world['KG1_R'] = Td[6] @ mount @ pivot
    geometry, masses, exclusions, mismatches = [], [], [], []
    visual_arrays = {n: [] for n in ARM + list(GROUPS.values())}
    colors = {n: {} for n in visual_arrays}
    hulls = {n: [] for n in visual_arrays}

    def geometry_item(name, link, mesh, transform, color, source, collide):
        m = moved(mesh, transform)
        require(np.isfinite(m.vertices).all(), 'Nonfinite geometry')
        visual_arrays[link].append(m)
        colors[link].setdefault(color.upper(), []).append((name, m))
        record = {'id': name, 'name': name, 'link': link, 'source': source, 'T_link_from_source_mm': transform,
                  'scale_to_m': .001, 'bounds_m': m.bounds, 'triangles': len(m.faces), 'collision_included': bool(collide),
                  'collision_reason': 'PER_PART_COARSE_HULL_CLOSES_HOLES' if collide else 'SOURCE_CATALOG_INNER_COLLIDE_FALSE'}
        if collide:
            h = m.convex_hull
            record['collision_hull'] = {'shell_index': len(hulls[link]), 'faces': len(h.faces), 'bounds_m': h.bounds,
                                        'volume_m3': h.volume, 'source_coverage': bool(np.all(m.bounds[0] >= h.bounds[0] - 1e-9) and np.all(m.bounds[1] <= h.bounds[1] + 1e-9))}
            hulls[link].append(h)
        geometry.append(record)

    for name, item in cat.items():
        if name.startswith('KG1.'):
            exclusions.append({'name': name, 'reason': 'REPLACED_ONCE_BY_ACTUAL_47_KG1_ITEMS'})
            continue
        path = Path(item['path'])
        mesh = trimesh.load(path, force='mesh')
        geometry_item(name, ARM[item['link']], mesh, inv0[item['link']] @ Fr[item['frame']], item['color'],
                      {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'kind': 'PRINTED_STL', 'units': 'mm', 'frame': item['frame']}, item['collide'])
    for name, item in L.refs(P).items():
        if 'TERM57' in name or 'DRIVER57' in name or '@' in name:
            exclusions.append({'name': name, 'reason': 'INSPECTION_CLEARANCE_ENVELOPE_NOT_AN_EXTRA_PHYSICAL_PART'})
            continue
        geometry_item(name, ARM[item['link']], L.ref_mesh(item), inv0[item['link']] @ Fr[item['frame']], '#141416' if 'MOTOR' in name else '#6B7280',
                      {'path': 'src/cad/manipulator-v2/layout.py', 'sha256': sha(CAD / 'layout.py'), 'kind': 'CABLE_APPROX' if 'CABLE' in name else 'PURCHASED_PRIMITIVE', 'units': 'mm', 'primitive': item}, True)
    geometry_ids = {g['id'] for g in geometry}
    for name, lk, mass, c, frame, I in bodies:
        if name == 'KG1 gripper (total)':
            require(abs(float(mass) - .1842) < 1e-12, 'KG1 original mass')
            continue
        if np.any(np.asarray(I)):
            method = 'KNOWN_BOX_SOURCE' if 'motor' in name else 'MESH_VOLUME_SCALED_TO_LEDGER_MASS'
        else:
            method = 'POINT_I0_SOURCE'
        row = tensor_component(name, ARM[lk], mass, c, I, inv0[lk] @ Fr[frame], method, name, [name] if name in geometry_ids else [])
        row['source_frame'] = frame
        masses.append(row)
    for i in (1, 2):
        mismatches.append({'mass_component': f'J1.6818 #{i}', 'geometry_component': f'REF.J1.6818_{i}', 'mass_link': 'Link1', 'visual_link': 'Base', 'reason': 'ORIGINAL_MP18_LOADS_ASSIGN_LINK1_BUT_REFERENCE_GEOMETRY_ASSIGN_LINK0; PRESERVED_NOT_SILENTLY_CORRECTED'})

    G = module(ROOT / 'src/cad/arm-v3-kg1-assembly/assemble.py', '_mp9_gripper118')
    gp, _, mans, refs = G.load_gripper()
    grip = G.gripper_items(gp, mans, refs, 0., 'FLAT')
    require(len(grip) == len({i['name'] for i in grip}) == 47, 'Actual47 gripper items')
    kgledger = readj(ROOT / 'models/kmjh-gripper-v1/mass-properties.json')
    printed_mass = {i['name']: i['mass_g'] * .001 for i in kgledger['items'] if i['kind'] == 'printed'}
    printed_alias = {'PAD_A': 'PAD_A_FLAT', 'PAD_B': 'PAD_B_FLAT'}
    categories, gm = {}, {}
    for item in grip:
        name = item['name']
        mesh = trimesh.Trimesh(vertices=item['v'], faces=item['f'], process=True)
        require(mesh.is_watertight and mesh.volume > 0, 'KG1 actual component not closed positive: ' + name)
        gm[name] = mesh
        if item['printed']:
            category = 'printed:' + name
        elif name.startswith('SERVO_'):
            category = 'servo_F'
        elif name == 'SPLINE':
            category = 'spline_R'
        elif name == 'HORN':
            category = 'horn_R'
        elif name.startswith('ROD_'):
            category = 'rods_F'
        else:
            category = 'screws_' + item['group']
        categories[name] = category
    targets = {'servo_F': .0548, 'spline_R': .0002, 'horn_R': .003, 'rods_F': .01319,
               'screws_F': .009 * 16 / 33, 'screws_A': .009 * 4 / 33, 'screws_B': .009 * 4 / 33, 'screws_R': .009 * 9 / 33}
    for item in grip:
        if item['printed']:
            targets[categories[item['name']]] = printed_mass[printed_alias.get(item['name'], item['name'])]
    volumes = {c: sum(gm[n].volume for n in gm if categories[n] == c) for c in set(categories.values())}
    grip_allocation = []
    for item in grip:
        name, group = item['name'], item['group']
        link, mesh, category = GROUPS[group], gm[name], categories[name]
        mass = targets[category] * mesh.volume / volumes[category]
        transform = np.eye(4)
        if group == 'R':
            transform[2, 3] = -26.
        gid = 'KG1:' + name
        color = G.GRIP_COLORS.get(name, G.GRIP_COLORS.get('PAD_A' if name.startswith('PAD_A') else 'PAD_B' if name.startswith('PAD_B') else name, G.ROD_COLOR if name.startswith('ROD_') else G.SCREW_COLOR))
        geometry_item(gid, link, mesh, transform, color, {'path': 'src/cad/arm-v3-kg1-assembly/assemble.py', 'sha256': sha(ROOT / 'src/cad/arm-v3-kg1-assembly/assemble.py'), 'kind': 'PRINTED_STL' if item['printed'] else 'PURCHASED_PRIMITIVE', 'item': name, 'group': group, 'u_mm': 0., 'padset': 'FLAT', 'units': 'mm'}, True)
        I = mesh.moment_inertia * mass / mesh.volume * 1e-6
        row = tensor_component('KG1:' + name, link, mass, mesh.center_mass, I, transform,
                               'MESH_VOLUME_SCALED_TO_LEDGER_MASS' if item['printed'] else 'GRIPPER_PRIMITIVE_VOLUME_ALLOCATION', category, [gid])
        row['source_frame'] = 'G'; row['allocation_category'] = category
        masses.append(row)
        grip_allocation.append({'name': name, 'group': group, 'category': category, 'source_volume_mm3': mesh.volume, 'mass_kg': mass})
    require(len(masses) == 219, '173 - 1 + 47 effective components')
    require(abs(sum(x['mass_kg'] for x in grip_allocation) - .1842) < 1e-12, 'Gripper mass conserved exactly')

    links = {}
    for name in visual_arrays:
        canonical = save_mesh(MODEL / 'meshes' / f'{name}.stl', visual_arrays[name])
        visual = []
        for color, items in sorted(colors[name].items()):
            record = save_mesh(MODEL / 'meshes/visual' / f'{name}__{color.removeprefix("#")}.stl', [m for _, m in items])
            record.update(color=[int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)] + [1.], component_ids=[n for n, _ in items])
            visual.append(record)
        coll = save_mesh(MODEL / 'meshes/collision' / f'{name}.stl', hulls[name])
        coll.update(method='CONCATENATED_PER_PART_CONVEX_HULLS_NOT_GLOBAL_CONVEX', component_ids=[g['id'] for g in geometry if g['link'] == name and g['collision_included']], shells=len(hulls[name]))
        rows = [m for m in masses if m['link'] == name]
        mass, c, I, eig = aggregate(rows)
        links[name] = {'mass_kg': mass, 'com_m': c, 'inertia_kg_m2': I, 'principal_inertias_kg_m2': eig,
                       'bounds_m': canonical['bounds_m'], 'canonical_mesh': canonical['file'], 'canonical_mesh_record': canonical,
                       'visuals': visual, 'collisions': [coll], 'mass_component_ids': [m['id'] for m in rows]}
    old_world, new_world = [], []
    for name, lk, mass, c, fr, I in bodies:
        old_world.append((mass, (Fr[fr] @ np.r_[c, 1.])[:3] * .001))
    for row in masses:
        T = frame_world[row['link']]
        # World transforms retain mm translations; component COMs are already metres.
        new_world.append((row['mass_kg'], T[:3, :3] @ np.asarray(row['com_m']) + T[:3, 3] * .001))
    # Original MP18 total at display, not its CAD q=0 summary, for equal-pose COM comparison.
    old_display = []
    for name, lk, mass, c, fr, I in bodies:
        T = Td[lk] @ inv0[lk] @ Fr[fr]
        old_display.append((mass, (T @ np.r_[c, 1.])[:3] * .001))
    com_old0 = sum(m * c for m, c in old_world) / original_total
    com_old_disp = sum(m * c for m, c in old_display) / original_total
    new_total = sum(m for m, _ in new_world)
    com_new_disp = sum(m * c for m, c in new_world) / new_total
    require(abs(new_total - original_total) < 1e-10, 'Total mass conservation')
    # At CAD q=0, each arm link origin is Ts0 and each gripper group is the G frame.
    new0 = []
    for row in masses:
        name = row['link']; T = Ts0[ARM.index(name)] if name in ARM else Fr['G'] @ (pivot if name == 'KG1_R' else np.eye(4))
        new0.append((row['mass_kg'], T[:3, :3] @ np.asarray(row['com_m']) + T[:3, 3] * .001))
    com_new0 = sum(m * c for m, c in new0) / new_total
    old_xml = ET.parse(ROOT / 'models/robot-arm-urdf-v3/robot_arm.urdf').getroot()
    joints = {}
    for k, name in enumerate(('J1', 'J2', 'J3', 'J4', 'J5', 'J6')):
        T = np.linalg.inv(Td[k]) @ Td[k + 1]
        rpy = trimesh.transformations.euler_from_matrix(T, axes='sxyz')
        limit = old_xml.find(f"joint[@name='{name}']/limit")
        axis = [float(L.AXES[name] == n) for n in ('x', 'y', 'z')]
        lo, hi = P['poses']['wanted_ranges_deg'][name]
        joints[name] = {'parent': ARM[k], 'child': ARM[k + 1], 'type': 'revolute', 'origin_xyz_m': T[:3, 3] * .001,
                        'origin_rpy_rad': rpy, 'axis': axis, 'cad_zero_offset_deg': display[k],
                        'limit': {'lower': math.radians(lo - display[k]), 'upper': math.radians(hi - display[k]), 'effort': float(limit.attrib['effort']), 'velocity': float(limit.attrib['velocity'])},
                        'range_authority': 'CAD_DESIGNER_PROPOSAL_WITH_ONE_AXIS_SAMPLE_SCOPE_NOT_HARDWARE_SAFE'}
    aliases = {f'parts/{n}.stl': L.MODEL / 'parts' / f'{n}.stl' for n in L.NEW_PARTS}
    aliases.update({'printprep.json': L.EV / 'printprep.json', 'inputs.json(MP5)': ROOT / 'src/cad/review-mp5/inputs.json',
                    'printprep.json(MP16)': ROOT / '.dev/mp16-evidence/printprep.json', 'sizing.json(MP16)': ROOT / '.dev/mp16-evidence/sizing/sizing.json',
                    'mass-properties.json(MP10)': ROOT / 'models/j5-wrist-v1/mass-properties.json', 'mass-properties.json(KG1)': ROOT / 'models/kmjh-gripper-v1/mass-properties.json',
                    'parameters.json': CAD / 'parameters.json', 'loads_arm.py': CAD / 'loads_arm.py', 'layout.py': CAD / 'layout.py'})
    audit = pin_audit(source_loads.get('inputs_sha256', {}), aliases)
    all_pin_checks, _pin_paths = source_pin_checks()
    require(all(row['match'] for row in audit), 'All original loads input pins must match')
    after = {p: {'sha256': sha(ROOT / p), 'bytes': (ROOT / p).stat().st_size} for p in before}
    writej(OUT / 'input-after.json', after)
    require(before == after, 'Protected input drift: before/after differ')
    census_digest = hashlib.sha256(json.dumps(before, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    totals = {'original_unrounded_mass_kg': original_total, 'new_mass_kg': new_total,
              'original_rounded_body_sum_kg': sum(x['kg'] for x in expected), 'original_rounded_total_kg': source_loads['mass_kg']['total'],
              'closed_original_com_world_m': com_old0, 'closed_new_com_world_m': com_new0, 'closed_com_delta_m': com_new0 - com_old0,
              'display_closed_original_com_world_m': com_old_disp, 'display_closed_new_com_world_m': com_new_disp, 'display_closed_com_delta_m': com_new_disp - com_old_disp}
    frames = {}
    for name, T in frame_world.items():
        value = T.copy(); value[:3, 3] *= .001
        frames[name] = {'T_world_at_arm_zero_m': value}
    writej(MODEL / 'numeric-ledger.json', {'schema_version': 1, 'unit': '118', 'units': {'length': 'm', 'mass': 'kg', 'angle': 'rad', 'inertia': 'kg*m^2'},
           'arm_zero_cad_deg': display, 'gripper_asset_reference': {'u_mm': 0., 'padset': 'FLAT', 'rotor_pivot_G_mm': [0, 0, 26]},
           'links': links, 'frames': frames, 'joints': joints, 'KG1_mount_T_Link6_from_G_mm': mount,
           'totals': totals, 'sourcechecks': {'before_census_sha256': census_digest, 'after_census_sha256': census_digest, 'preserved': True, **all_pin_checks}})
    writej(MODEL / 'asset-ledger.json', {'schema_version': 1, 'unit': '118', 'geometry_components': geometry, 'mass_components': masses,
           'original_173_bodies': original_records, 'replaced_KG1_lump': {'count': 1, 'mass_kg': .1842},
           'gripper_47_allocation': {'target_by_category_kg': targets, 'actual_by_group_kg': {g: sum(x['mass_kg'] for x in grip_allocation if x['group'] == g) for g in GROUPS}, 'actual_sum_kg': sum(x['mass_kg'] for x in grip_allocation), 'items': grip_allocation,
               'assumption': '068 F/A/B/R group totals preserved. Printed parts use original individual masses; servo54.8g F/spline0.2g R/horn3g R/rods13.19g F/screws9g group16:4:4:9; category mass distributed by actual closed primitive volume.'},
           'excluded_envelopes': exclusions, 'ownership_mismatches': mismatches, 'point_I0_items': [m['name'] for m in masses if m['method'] == 'POINT_I0_SOURCE'],
           'collision_limitations': ['Concatenated individual convex hull shells form a globally concave compound mesh.', 'Guide holes/annular bores close in their individual hulls: false contacts possible.', 'Internal catalog collide=False meshes excluded.', 'No self collision, safety or dynamic Isaac decomposition/import acceptance.']})
    writej(MODEL / 'provenance.json', {'schema_version': 1, 'unit': '118', 'canonical_source': 'Root-authored robot_arm.urdf; A writes no XML', 'input_census': before,
           'read_only_load_prefix': prefix_meta, 'source_preservation': True, 'mass_confidence': 'SLICER_ESTIMATES_AND_ORIGINAL_PURCHASED_ASSUMPTIONS_NOT_WEIGHED',
           'COM_difference': 'Original KG1 aggregate COM replaced by actual47-component allocation. Mass conserved; whole COM delta explicitly retained.',
           'visual_mass_model_difference': 'Central motor geometry only; original driver point masses retained. J1 bearing mass-owner Link1 vs visual Base preserved as source mismatch.',
           'physics_acceptance': 'NOT_RUN', 'hardware_approved': False, 'XML_written_by_A': False, 'assets_code_sha256': sha(__file__),
           'versions': {'python': sys.version, 'numpy': np.__version__, 'trimesh': trimesh.__version__}, 'elapsed_prepare_s': time.monotonic() - started})
    writej(OUT / 'prepare-result.json', {'unit': '118', 'links': len(links), 'geometry_components': len(geometry), 'mass_components': len(masses), 'original173_match': True,
           'total_mass_preserved': True, 'input_files_preserved': len(before), 'load_pin_mismatches': [x for x in audit if not x['match']], 'totals': totals,
           'outputs': {p.relative_to(MODEL).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(MODEL.rglob('*')) if p.is_file() and p.suffix.lower() != '.urdf'}, 'elapsed_s': time.monotonic() - started})
    print(json.dumps(clean({'links': len(links), 'geometry_components': len(geometry), 'mass_components': len(masses), 'totals': totals, 'elapsed_s': time.monotonic() - started}), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--finalize-pins']:
        finalize_pin_audit()
    else:
        require(not sys.argv[1:], 'Only explicit --finalize-pins metadata revision is accepted')
        prepare()
