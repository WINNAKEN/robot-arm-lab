"""067 static asset semantics. Reads canonical XML; does not author it."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assets

def vec(s):
    v = np.array([float(x) for x in s.split()])
    assert v.shape == (3,) and np.isfinite(v).all(), 'finite xyz/rpy vector'
    return v

def rotation(axis, q):
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    k = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + math.sin(q)*k + (1-math.cos(q))*(k@k)

def origin(e):
    o = e.find('origin')
    t = np.eye(4)
    if o is not None:
        r, p, y = vec(o.get('rpy', '0 0 0'))
        t[:3, :3] = rotation([0, 0, 1], y) @ rotation([0, 1, 0], p) @ rotation([1, 0, 0], r)
        t[:3, 3] = vec(o.get('xyz', '0 0 0'))
    return t

def close(a, b, tol, label):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all(), label + ' shape/finite'
    residual = float(np.max(np.abs(a-b))) if a.size else 0.
    assert residual <= tol, f'{label}: residual {residual} > {tol}'
    return residual

def fk(joints, q):
    frames = {'Base': np.eye(4)}
    axes = []
    for joint in joints:
        t = frames[joint.find('parent').get('link')] @ origin(joint)
        if joint.get('type') == 'revolute':
            axis = vec(joint.find('axis').get('xyz'))
            axes.append(t[:3, :3] @ axis)
            turn = np.eye(4)
            turn[:3, :3] = rotation(axis, q[int(joint.get('name')[1:])-1])
            t = t @ turn
        frames[joint.find('child').get('link')] = t
    return frames, axes

def independent_fk(q):
    p = assets.readj(assets.ROOT/'models/armold-mks-concept-v1/parameters.json')
    offsets = [[0,0,p['joint1_height_mm']], [0,0,p['shoulder_rise_mm']],
               [p['upper_arm_mm'],0,0], [p['forearm_mm'],0,0],
               [p['wrist_offsets_mm'][0],0,0], [p['wrist_offsets_mm'][1],0,0]]
    r, t = np.eye(3), np.zeros(3)
    frames, axes = {}, []
    for k, off in enumerate(offsets):
        t = t + r @ (np.asarray(off)*.001)
        axis = np.asarray(p['axis_parent_zero'][k])
        axes.append(r @ axis)
        r = r @ rotation(axis, q[k] + math.radians(p['pose_deg'][k]))
        m = np.eye(4)
        m[:3, :3], m[:3, 3] = r, t
        frames[f'Link{k+1}'] = m
    return frames, axes

def verify(model=assets.MODEL):
    root = ET.parse(model/'robot_arm.urdf').getroot()
    links, joints = root.findall('link'), root.findall('joint')
    assert [x.get('name') for x in links] == assets.NAMES + ['tool0'], 'link set/order'
    assert [x.get('name') for x in joints] == [f'J{i}' for i in range(1,7)]+['KG1_mount','tool0_mount'], 'joint set/order'
    assert [x.get('type') for x in joints] == ['revolute']*6 + ['fixed']*2, 'joint types'
    expected_parents = ['Base','Link1','Link2','Link3','Link4','Link5','Link6','KG1']
    for i, j in enumerate(joints):
        assert j.find('parent').get('link') == expected_parents[i], 'joint parent'
        assert j.find('child').get('link') == (assets.NAMES+['tool0'])[i+1], 'joint child'
    old = ET.parse(assets.ROOT/'models/robot-arm-urdf-v1/robot_arm.urdf').getroot().findall('joint')
    limits = [(-170.,170.)]*6
    limits[4] = (-135.,85.)
    effort = [3.,6.,5.,2.,2.,1.]
    legacy_residual = 0.
    for k, j in enumerate(joints[:6]):
        legacy_residual = max(legacy_residual, close(origin(j), origin(old[k]), 1e-12, 'legacy joint origin'))
        close(vec(j.find('axis').get('xyz')), vec(old[k].find('axis').get('xyz')), 1e-12, 'legacy axis')
        lim = j.find('limit')
        close([float(lim.get(x)) for x in ['lower','upper']], np.radians(limits[k]), 1e-12, 'declared limits')
        close([float(lim.get('effort')),float(lim.get('velocity'))], [effort[k],.5], 1e-12, 'assumed actuator caps')
        d = j.find('dynamics')
        close([float(d.get('damping')),float(d.get('friction'))], [.05,0.], 1e-12, 'assumed dynamics')
    asm = assets.readj(assets.ROOT/'models/arm-v3-kg1-assembly/assembly.json')
    mount = np.asarray(asm['mount']['g_to_link6_local'],dtype=float).copy()
    mount[:3,3] *= .001
    close(origin(joints[6]), mount, 1e-12, 'MP9 fixed mount')
    tcp = np.eye(4)
    tcp[:3,3] = np.asarray(asm['grasp_point']['g_mm'])*.001
    close(origin(joints[7]), tcp, 1e-12, 'nominal tool0')
    poses = [np.zeros(6)]
    for k in range(6):
        for angle in [-5.,5.,*limits[k]]:
            q = np.zeros(6)
            q[k] = math.radians(angle)
            poses.append(q)
    poses += [np.radians([10,-20,30,-40,20,-30]), np.radians([-25,15,-10,20,-35,45]), np.radians([40,-30,20,10,-20,30])]
    position_error, rotation_error, axis_error = 0., 0., 0.
    for q in poses:
        actual, axes = fk(joints,q)
        expected, exaxes = independent_fk(q)
        for k in range(6):
            name = f'Link{k+1}'
            position_error = max(position_error, close(actual[name][:3,3],expected[name][:3,3],1e-12,'independent position'))
            rotation_error = max(rotation_error, close(actual[name][:3,:3],expected[name][:3,:3],1e-12,'independent orientation'))
            axis_error = max(axis_error, close(axes[k],exaxes[k],1e-12,'independent signed axis'))
        close(actual['KG1'], expected['Link6']@mount, 1e-12, 'KG1 forward placement')
        close(actual['tool0'], expected['Link6']@mount@tcp, 1e-12, 'TCP forward placement')
    expected_meshes, records = assets.construct()
    ledger = assets.readj(model/'asset-ledger.json')
    assert ledger['source_bodies'] == records, 'source ownership/cardinality ledger'
    assert set(ledger['links']) == set(assets.NAMES), 'link ledger set'
    masses = assets.ASSUMED_ARM_MASSES_KG + [assets.readj(assets.ROOT/'models/kmjh-gripper-v1/mass-properties.json')['total_mass_g']*.001]
    mesh_error, world_error = 0., 0.
    frames, _ = fk(joints,np.zeros(6))
    for i, link in enumerate(links[:-1]):
        name = link.get('name')
        assert len(link.findall('visual')) == len(link.findall('inertial')) == len(link.findall('collision')) == 1, 'physical block cardinality'
        visual = link.find('visual')
        close(origin(visual),np.eye(4),1e-15,'visual identity')
        mesh = visual.find('geometry/mesh')
        assert mesh is not None and mesh.get('filename') == f'meshes/{name}.stl', 'mesh reference'
        close(vec(mesh.get('scale')), [1,1,1], 1e-15, 'metre mesh scale')
        tri = np.asarray(trimesh.load(model/mesh.get('filename'),force='mesh',process=False).triangles)
        mesh_error = max(mesh_error,close(tri,expected_meshes[name],5e-8,'actual STL/source vertices'))
        if i < 7:
            kin = assets.readj(assets.ROOT/'models/armold-mks-concept-v1/kinematics.json')['joints']
            expected_world = expected_meshes[name] if not i else expected_meshes[name]@np.asarray(kin[i-1]['R_child']).T + np.asarray(kin[i-1]['origin_mm'])*.001
            restored = tri@frames[name][:3,:3].T + frames[name][:3,3]
            world_error = max(world_error,close(restored,expected_world,5e-8,'saved STL world restoration'))
        prop = assets.box_properties(tri,masses[i])
        for key in ['mass_kg','com_m','box_size_m','inertia_kg_m2']:
            close(ledger['links'][name][key],prop[key],1e-14,'actual STL/ledger '+key)
        assert ledger['links'][name]['triangles'] == len(tri), 'triangle ledger'
        inertia = link.find('inertial')
        close(float(inertia.find('mass').get('value')), masses[i], 1e-14, 'assumed source mass')
        close(vec(inertia.find('origin').get('xyz')),prop['com_m'],1e-14,'inertial COM')
        close(vec(inertia.find('origin').get('rpy')), [0,0,0], 1e-15, 'inertial RPY')
        tensor = inertia.find('inertia')
        close([float(tensor.get(k)) for k in ['ixx','iyy','izz']],prop['inertia_kg_m2'],1e-14,'actual STL box inertia')
        close([float(tensor.get(k)) for k in ['ixy','ixz','iyz']], [0,0,0],1e-15,'zero off-diagonals')
        collision = link.find('collision')
        close(vec(collision.find('origin').get('xyz')),prop['com_m'],1e-14,'collision COM')
        close(vec(collision.find('origin').get('rpy')),[0,0,0],1e-15,'collision RPY')
        assert len(collision.find('geometry')) == 1 and collision.find('geometry/box') is not None, 'one proxy box'
        close(vec(collision.find('geometry/box').get('size')),prop['box_size_m'],1e-14,'actual STL collision size')
    assert len(links[-1]) == 0, 'tool0 frame-only intent'
    prov = assets.readj(model/'provenance.json')
    assert prov['input_census'] == assets.census(), 'source input preservation'
    assert prov['physics_acceptance'].startswith('NOT_RUN'), 'physics acceptance scope'
    pins = {'v3 bodies.json':'models/armold-mks-product-v3/bodies.json',
        'v1 kinematics.json':'models/armold-mks-concept-v1/kinematics.json',
        'v1 parameters.json':'models/armold-mks-concept-v1/parameters.json',
        'v3 parameters.json':'src/cad/armold-mks-product-v3/parameters.json',
        'parameters.json (MP9)':'src/cad/arm-v3-kg1-assembly/parameters.json',
        'gripper parameters.json':'src/cad/kmjh-gripper-v1/parameters.json',
        'verify_gripper.py':'src/cad/kmjh-gripper-v1/verify_gripper.py',
        'print-fits.json':'src/cad/calibration/print-fits.json',
        'assemble.py':'src/cad/arm-v3-kg1-assembly/assemble.py'}
    for key, path in pins.items():
        assert asm['inputs_sha256'][key] == assets.sha(assets.ROOT/path), 'MP9 bound input '+key
    bodies = assets.readj(assets.ROOT/'models/armold-mks-product-v3/bodies.json')['bodies']
    folded = hashlib.sha256(''.join(assets.sha(assets.ROOT/'models/armold-mks-product-v3/meshes'/(b['name']+'.stl')) for b in sorted(bodies,key=lambda b:b['name'])).encode()).hexdigest()
    assert folded == asm['inputs_sha256']['v3 meshes (이름순 sha 의 sha)'], 'MP9 mesh folded fingerprint'
    for part, expected_hash in asm['inputs_sha256'].items():
        if part.startswith('gripper parts/'):
            assert assets.sha(assets.ROOT/'models/kmjh-gripper-v1/parts'/part.split('/')[-1]) == expected_hash, 'MP9 gripper STL pin'
    assert assets.sha(assets.ROOT/'models/kmjh-gripper-v1/mass-properties.json') == asm['gripper_mass']['source_sha256'], 'MP9 mass source pin'
    manifest = assets.readj(model/'manifest.json')
    actual_files = {p.relative_to(model).as_posix():assets.sha(p) for p in sorted(model.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
    assert manifest['files'] == actual_files, 'manifest actual payload binding'
    return {'ok':True,'scope':'STATIC_ONLY_PHYSICS_NOT_RUN','links':9,'physical_links':8,'revolute_joints':6,'fixed_joints':2,
        'arm_source_bodies':47,'gripper_items':47,'poses':len(poses),'joint_frames':len(poses)*6,
        'max_position_error_m':position_error,'max_rotation_component_error':rotation_error,'max_signed_axis_error':axis_error,
        'max_saved_mesh_error_m':mesh_error,'max_saved_mesh_world_error_m':world_error,'legacy_origin_max_error':legacy_residual,
        'total_assumed_mass_kg':sum(masses),'input_files_preserved':len(prov['input_census'])}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--model',type=Path,default=assets.MODEL)
    ap.add_argument('--out',type=Path)
    args = ap.parse_args()
    try:
        result = verify(args.model)
    except Exception as exc:
        result = {'ok':False,'error':type(exc).__name__+': '+str(exc)}
        if args.out:
            assets.writej(args.out,result)
        print(json.dumps(result))
        raise
    if args.out:
        assets.writej(args.out,result)
    print(json.dumps(result,indent=2))
