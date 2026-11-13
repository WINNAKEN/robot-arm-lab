"""067 read-only CAD conversion and numeric scaffolding. Never writes URDF XML."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / 'models/robot-arm-urdf-v2'
OUT = ROOT / 'outputs/urdf-revised-v2'
NAMES = ['Base', *[f'Link{i}' for i in range(1, 7)], 'KG1']
ASSUMED_ARM_MASSES_KG = [1.2, .65, .7, .65, .4, .35, .2]

def readj(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def writej(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def source_paths():
    fixed = ['models/armold-mks-concept-v1/kinematics.json',
             'models/armold-mks-concept-v1/parameters.json',
             'models/armold-mks-product-v3/bodies.json',
             'models/armold-mks-product-v3/kmjh-arm-product-v3.solidcraft',
             'models/arm-v3-kg1-assembly/assembly.json',
             'models/kmjh-gripper-v1/mass-properties.json',
             'models/robot-arm-urdf-v1/robot_arm.urdf',
             'models/robot-arm-urdf-v1/assumptions.json',
             'models/j5-wrist-v1/README.md',
             'models/j5-wrist-v1/mass-properties.json',
             'src/cad/armold-mks-product-v3/parameters.json',
             'src/cad/arm-v3-kg1-assembly/assemble.py',
             'src/cad/arm-v3-kg1-assembly/parameters.json',
             'src/cad/arm-v3-kg1-assembly/guard.py',
             'src/cad/kmjh-gripper-v1/parameters.json',
             'src/cad/kmjh-gripper-v1/verify_gripper.py',
             'src/cad/kmjh-gripper-v1/guard.py',
             'src/cad/calibration/print-fits.json']
    return sorted([ROOT / p for p in fixed] + list((ROOT / 'models/armold-mks-product-v3/meshes').glob('*.stl'))
                  + list((ROOT / 'models/kmjh-gripper-v1/parts').glob('*.stl')))

def census():
    return {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in source_paths()}

def construct():
    """Returns CAD-derived triangles in each display link frame, metres."""
    kin = readj(ROOT / 'models/armold-mks-concept-v1/kinematics.json')['joints']
    bodies = readj(ROOT / 'models/armold-mks-product-v3/bodies.json')['bodies']
    assert len(bodies) == 47 and len({b['name'] for b in bodies}) == 47
    arrays = {n: [] for n in NAMES}
    records = []
    for b in bodies:
        p = ROOT / 'models/armold-mks-product-v3/meshes' / (b['name'] + '.stl')
        mesh = trimesh.load(p, force='mesh', process=False)
        tri = np.array(mesh.triangles, dtype=float, copy=True)
        i = b['link']
        if i:
            j = kin[i - 1]
            tri = (tri - np.asarray(j['origin_mm'])) @ np.asarray(j['R_child'])
        tri *= .001
        arrays[NAMES[i]].append(tri)
        records.append({'name': b['name'], 'link': NAMES[i], 'triangles': len(tri),
                        'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)})
    spec = importlib.util.spec_from_file_location('readonly_mp9', ROOT / 'src/cad/arm-v3-kg1-assembly/assemble.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    gp, parts, mans, refs = mod.load_gripper()
    prm = readj(ROOT / 'src/cad/arm-v3-kg1-assembly/parameters.json')
    assert prm['gripper']['render_u'] == 20 and prm['gripper']['padset'] == 'FLAT'
    grip = mod.gripper_items(gp, mans, refs, 20., 'FLAT')
    assert len(grip) == 47
    for g in grip:
        tri = g['v'][g['f']] * .001
        arrays['KG1'].append(tri)
        records.append({'name': g['name'], 'link': 'KG1', 'triangles': len(tri),
                        'printed': g['printed'], 'group': g['group'],
                        'source': 'MP9 readonly gripper_items(u=20,FLAT); source STL plus purchased reference primitives'})
    return {n: np.concatenate(v) for n, v in arrays.items()}, records

def box_properties(tri, mass):
    xyz = tri.reshape(-1, 3)
    lo, hi = xyz.min(axis=0), xyz.max(axis=0)
    center, size = (lo + hi) / 2, hi - lo
    x, y, z = size
    return {'mass_kg': mass, 'com_m': center.tolist(), 'box_size_m': size.tolist(),
            'inertia_kg_m2': [mass*(y*y+z*z)/12, mass*(x*x+z*z)/12, mass*(x*x+y*y)/12]}

def seal(model=MODEL):
    writej(model / 'manifest.json', {'canonical': 'robot_arm.urdf',
        'files': {p.relative_to(model).as_posix(): sha(p) for p in sorted(model.rglob('*'))
                  if p.is_file() and p.name != 'manifest.json'}})

def prepare():
    if (MODEL / 'robot_arm.urdf').exists():
        raise RuntimeError('Canonical URDF already exists; assets are not implicitly regenerated.')
    before = census()
    writej(OUT / 'input-before.json', before)
    triangles, records = construct()
    (MODEL / 'meshes').mkdir(parents=True, exist_ok=True)
    mass = ASSUMED_ARM_MASSES_KG + [readj(ROOT / 'models/kmjh-gripper-v1/mass-properties.json')['total_mass_g']*.001]
    props = {}
    for i, name in enumerate(NAMES):
        t = triangles[name]
        mesh = trimesh.Trimesh(t.reshape(-1, 3), np.arange(t.size//3).reshape(-1, 3), process=False)
        mesh.export(MODEL / 'meshes' / (name + '.stl'))
        saved = trimesh.load(MODEL / 'meshes' / (name + '.stl'), force='mesh', process=False)
        props[name] = box_properties(np.asarray(saved.triangles), mass[i])
        props[name]['triangles'] = len(t)
    writej(MODEL / 'asset-ledger.json', {'source_bodies': records, 'links': props})
    writej(MODEL / 'provenance.json', {'input_census': before,
        'canonical_source': 'robot_arm.urdf authored directly; assets.py is conversion/calculation scaffolding only',
        'assembly': 'MP9 rev1 v3+KG1; MP10 standalone J5 NOT_INTEGRATED; MP11 illustration NOT_DIMENSION_SOURCE',
        'physics_acceptance': 'NOT_RUN; no 065 physics acceptance inherited'})
    after = census()
    writej(OUT / 'input-after-preparation.json', after)
    assert before == after
    print(json.dumps(props, indent=2))

if __name__ == '__main__':
    prepare()
