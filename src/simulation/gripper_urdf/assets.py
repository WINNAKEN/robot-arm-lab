"""068 read-only CAD conversion/numeric scaffolding; never writes URDF XML."""
from __future__ import annotations
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import trimesh

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / 'models/robot-arm-urdf-v3'
OLD = ROOT / 'models/robot-arm-urdf-v2'
OUT = ROOT / 'outputs/urdf-gripper-v3'
ARM = ['Base', *[f'Link{i}' for i in range(1, 7)]]
GROUPS = {'F': 'KG1', 'A': 'KG1_A', 'B': 'KG1_B', 'R': 'KG1_R'}
NAMES = ARM + list(GROUPS.values())

def readj(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def writej(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def census():
    paths = list(OLD.rglob('*'))
    for folder in ['src/cad/arm-v3-kg1-assembly', 'src/cad/kmjh-gripper-v1',
                   'models/kmjh-gripper-v1/parts', 'models/armold-mks-product-v3/meshes']:
        paths.extend((ROOT/folder).rglob('*'))
    paths += [ROOT/p for p in ['models/arm-v3-kg1-assembly/assembly.json',
        'models/kmjh-gripper-v1/mass-properties.json', 'models/armold-mks-concept-v1/kinematics.json',
        'models/armold-mks-concept-v1/parameters.json', 'models/armold-mks-product-v3/bodies.json',
        'src/cad/calibration/print-fits.json']]
    return {p.relative_to(ROOT).as_posix(): {'bytes':p.stat().st_size,'sha256':sha(p)}
            for p in sorted(set(paths)) if p.is_file() and '__pycache__' not in p.parts}

@lru_cache(maxsize=1)
def cad():
    p = ROOT/'src/cad/arm-v3-kg1-assembly/assemble.py'
    spec = importlib.util.spec_from_file_location('readonly_mp9_068',p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, mod.load_gripper()

def items(u_mm):
    mod, (gp, _parts, mans, refs) = cad()
    return mod.gripper_items(gp,mans,refs,float(u_mm),'FLAT')

def construct():
    arrays = {v:[] for v in GROUPS.values()}
    records = []
    for item in items(0.):
        name = GROUPS[item['group']]
        tri = item['v'][item['f']].copy()
        if item['group'] == 'R':
            tri -= np.array([0.,0.,26.])
        arrays[name].append(tri*.001)
        records.append({'name':item['name'],'group':item['group'],'link':name,
                        'printed':item['printed'],'triangles':len(tri)})
    assert len(records)==47 and len({r['name'] for r in records})==47, 'source ownership'
    return {k:np.concatenate(v) for k,v in arrays.items()}, records

def masses():
    source = readj(ROOT/'models/kmjh-gripper-v1/mass-properties.json')
    printed = {x['name']:float(x['mass_g']) for x in source['items'] if x['kind']=='printed'}
    # Servo spline .2g and 9g screw allocation are explicit simulation assumptions.
    mg = {'KG1': printed['BASE']+54.8+13.19+9.*16/33,
          'KG1_A':printed['JAW_A']+printed['PAD_A_FLAT']+9.*4/33,
          'KG1_B':printed['JAW_B']+printed['PAD_B_FLAT']+9.*4/33,
          'KG1_R':printed['PINION']+3.+.2+9.*9/33}
    assert abs(sum(mg.values())-source['total_mass_g'])<1e-10, 'mass conservation'
    return {k:v*.001 for k,v in mg.items()}

def properties(tri, mass):
    xyz=tri.reshape(-1,3)
    lo,hi=xyz.min(0),xyz.max(0)
    c,s=(lo+hi)/2,hi-lo
    x,y,z=s
    return {'mass_kg':mass,'com_m':c.tolist(),'box_size_m':s.tolist(),
            'inertia_kg_m2':[mass*(y*y+z*z)/12,mass*(x*x+z*z)/12,mass*(x*x+y*y)/12],
            'triangles':len(tri)}

def seal(model=MODEL):
    writej(model/'manifest.json',{'canonical':'robot_arm.urdf','files':{
        p.relative_to(model).as_posix():sha(p) for p in sorted(model.rglob('*'))
        if p.is_file() and p.name!='manifest.json'}})

def prepare():
    if (MODEL/'robot_arm.urdf').exists():
        raise RuntimeError('Canonical XML already exists; explicit asset rebuild required.')
    before=census()
    writej(OUT/'input-before.json',before)
    (MODEL/'meshes').mkdir(parents=True,exist_ok=True)
    for name in ARM:
        shutil.copyfile(OLD/'meshes'/f'{name}.stl',MODEL/'meshes'/f'{name}.stl')
    arrays,records=construct()
    props={}
    for name,tri in arrays.items():
        mesh=trimesh.Trimesh(tri.reshape(-1,3),np.arange(tri.size//3).reshape(-1,3),process=False)
        mesh.export(MODEL/'meshes'/f'{name}.stl')
        saved=np.asarray(trimesh.load(MODEL/'meshes'/f'{name}.stl',force='mesh',process=False).triangles)
        props[name]=properties(saved,masses()[name])
    writej(MODEL/'asset-ledger.json',{'source_items':records,'links':props,
        'mass_allocation':'184.2g conserved; printed source masses; servo spline .2g to R; servo54.8g F; horn3g R; rods13.19g F; screws9g split16/4/4/9 of33 by F/A/B/R',
        'mass_confidence':'ASSUMED_NOT_WEIGHED; COM/inertia uniform AABB placeholders'})
    writej(MODEL/'provenance.json',{'input_census':before,
        'canonical_source':'robot_arm.urdf authored directly; assets.py writes only mesh/numeric scaffolding',
        'assembly':'MP9 rev1 v3+KG1; MP10 neck user decision made but standalone NOT_INTEGRATED',
        'physics_acceptance':'NOT_RUN in 068; root 069 independently records actual SDK evidence'})
    after=census()
    assert before==after,'source preservation'
    writej(OUT/'input-after-preparation.json',after)
    print(json.dumps(props,indent=2))

if __name__=='__main__':
    prepare()
