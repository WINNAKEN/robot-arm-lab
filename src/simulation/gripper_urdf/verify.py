"""068 semantic verifier: canonical XML and actual meshes against original CAD motion."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import assets
from command import joint_positions

def close(a,b,tol,label):
    a,b=np.asarray(a),np.asarray(b)
    assert a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),label+' shape/finite'
    error=float(np.max(np.abs(a-b))) if a.size else 0.
    assert error<=tol,f'{label}: residual {error} > {tol}'
    return error

def vec(text):
    a=np.asarray([float(x) for x in text.split()])
    assert a.shape==(3,) and np.isfinite(a).all(),'finite vector'
    return a

def rot(axis,q):
    x,y,z=np.asarray(axis)/np.linalg.norm(axis)
    k=np.array([[0,-z,y],[z,0,-x],[-y,x,0.]])
    return np.eye(3)+math.sin(q)*k+(1-math.cos(q))*(k@k)

def origin(element):
    t=np.eye(4)
    e=element.find('origin')
    if e is not None:
        r,p,y=vec(e.get('rpy','0 0 0'))
        t[:3,:3]=rot([0,0,1],y)@rot([0,1,0],p)@rot([1,0,0],r)
        t[:3,3]=vec(e.get('xyz','0 0 0'))
    return t

def fk(joints,q):
    frames={'Base':np.eye(4)}
    positions=dict(q)
    for j in joints:
        name=j.get('name')
        mimic=j.find('mimic')
        if mimic is not None:
            positions[name]=positions[mimic.get('joint')]*float(mimic.get('multiplier','1'))+float(mimic.get('offset','0'))
        t=frames[j.find('parent').get('link')]@origin(j)
        m=np.eye(4)
        if j.get('type') in ['revolute','prismatic']:
            a=vec(j.find('axis').get('xyz'))
            value=positions[name]
            if j.get('type')=='revolute':
                m[:3,:3]=rot(a,value)
            else:
                m[:3,3]=a*value
        frames[j.find('child').get('link')]=t@m
    return frames,positions

def arm_reference(q):
    p=assets.readj(assets.ROOT/'models/armold-mks-concept-v1/parameters.json')
    offsets=[[0,0,p['joint1_height_mm']],[0,0,p['shoulder_rise_mm']],
        [p['upper_arm_mm'],0,0],[p['forearm_mm'],0,0],
        [p['wrist_offsets_mm'][0],0,0],[p['wrist_offsets_mm'][1],0,0]]
    r,t=np.eye(3),np.zeros(3)
    frames={}
    for i,off in enumerate(offsets):
        t=t+r@(np.asarray(off)*.001)
        r=r@rot(p['axis_parent_zero'][i],float(q[i])+math.radians(p['pose_deg'][i]))
        m=np.eye(4)
        m[:3,:3],m[:3,3]=r,t
        frames[f'Link{i+1}']=m
    return frames

def transformed(tri,t):
    return tri@t[:3,:3].T+t[:3,3]

def verify(model=assets.MODEL):
    model=Path(model)
    tree=ET.parse(model/'robot_arm.urdf').getroot()
    old=ET.parse(assets.OLD/'robot_arm.urdf').getroot()
    links,joints=tree.findall('link'),tree.findall('joint')
    assert [l.get('name') for l in links]==assets.NAMES+['tool0'],'link set/order'
    expected_joints=[f'J{i}' for i in range(1,7)]+['KG1_mount','KG1_slide_A','KG1_slide_B','KG1_pinion','tool0_mount']
    assert [j.get('name') for j in joints]==expected_joints,'joint set/order'
    for i in range(6):
        # Entire element preserves source origin/axis/limits/dynamics, not only selected fields.
        assert ET.tostring(joints[i])==ET.tostring(old.find(f"joint[@name='J{i+1}']")),'legacy arm joint'
    for name in ['KG1_mount','tool0_mount']:
        assert ET.tostring(tree.find(f"joint[@name='{name}']"))==ET.tostring(old.find(f"joint[@name='{name}']")), 'legacy mount/TCP'
    for name in assets.ARM:
        assert ET.tostring(tree.find(f"link[@name='{name}']"))==ET.tostring(old.find(f"link[@name='{name}']")), 'legacy arm link'
        assert assets.sha(model/'meshes'/f'{name}.stl')==assets.sha(assets.OLD/'meshes'/f'{name}.stl'),'legacy arm mesh'
    r=.0135
    specs={'KG1_slide_A':('KG1_A','prismatic',[-1,0,0],[-.020,0,0],[0,0,0],[-.020,.027,10,.02],None),
        'KG1_slide_B':('KG1_B','prismatic',[1,0,0],[.020,0,0],[0,0,0],[-.020,.027,10,.02],1.),
        'KG1_pinion':('KG1_R','revolute',[0,1,0],[0,0,.026],[0,-.020/r,0],[-.027/r,.020/r,.2,2.],-1/r)}
    for name,(child,kind,axis,xyz,rpy,limit,mult) in specs.items():
        j=tree.find(f"joint[@name='{name}']")
        assert j.get('type')==kind and j.find('parent').get('link')=='KG1' and j.find('child').get('link')==child,'gripper topology'
        close(vec(j.find('axis').get('xyz')),axis,1e-15,'gripper axis')
        close(vec(j.find('origin').get('xyz')),xyz,1e-15,'gripper origin')
        close(vec(j.find('origin').get('rpy')),rpy,1e-14,'gripper origin')
        close([float(j.find('limit').get(k)) for k in ['lower','upper','effort','velocity']],limit,1e-14,'gripper limits')
        close([float(j.find('dynamics').get(k)) for k in ['damping','friction']],[.05,0.],1e-15,'gripper dynamics')
        mimic=j.find('mimic')
        if mult is None:
            assert mimic is None,'leader independent'
        else:
            assert mimic is not None and mimic.get('joint')=='KG1_slide_A','gripper mimic'
            close([float(mimic.get('multiplier')),float(mimic.get('offset'))],[mult,0.],1e-14,'gripper mimic')
    expected_meshes,records=assets.construct()
    ledger=assets.readj(model/'asset-ledger.json')
    assert ledger['source_items']==records,'source ownership'
    assert Counter(r['group'] for r in records)=={'F':23,'A':6,'B':6,'R':12},'source group cardinality'
    assert set(ledger['links'])==set(assets.GROUPS.values()),'gripper mass ledger'
    source_tri={}
    max_mesh_error=0.
    mass=assets.masses()
    for name in assets.GROUPS.values():
        link=tree.find(f"link[@name='{name}']")
        assert len(link.findall('visual'))==len(link.findall('collision'))==len(link.findall('inertial'))==1,'physical block cardinality'
        visual=link.find('visual')
        close(origin(visual),np.eye(4),1e-15,'visual identity')
        me=visual.find('geometry/mesh')
        assert me is not None and len(visual.find('geometry'))==1 and me.get('filename')==f'meshes/{name}.stl','mesh reference'
        close(vec(me.get('scale')),[1,1,1],1e-15,'metre mesh scale')
        tri=np.asarray(trimesh.load(model/me.get('filename'),force='mesh',process=False).triangles)
        source_tri[name]=tri
        max_mesh_error=max(max_mesh_error,close(tri,expected_meshes[name],5e-8,'actual STL/source vertices'))
        prop=assets.properties(tri,mass[name])
        for key in ['mass_kg','com_m','box_size_m','inertia_kg_m2','triangles']:
            close(ledger['links'][name][key],prop[key],1e-14,'actual STL/ledger '+key)
        inertial=link.find('inertial')
        close(float(inertial.find('mass').get('value')),mass[name],1e-14,'assumed source mass')
        close(vec(inertial.find('origin').get('xyz')),prop['com_m'],1e-14,'inertial COM')
        close(vec(inertial.find('origin').get('rpy')),[0,0,0],1e-15,'inertial RPY')
        tensor=inertial.find('inertia')
        close([float(tensor.get(k)) for k in ['ixx','iyy','izz']],prop['inertia_kg_m2'],1e-14,'actual STL box inertia')
        close([float(tensor.get(k)) for k in ['ixy','ixz','iyz']],[0,0,0],1e-15,'inertia offdiagonal')
        collision=link.find('collision')
        close(vec(collision.find('origin').get('xyz')),prop['com_m'],1e-14,'collision COM')
        close(vec(collision.find('origin').get('rpy')),[0,0,0],1e-15,'collision RPY')
        assert len(collision.find('geometry'))==1 and collision.find('geometry/box') is not None,'one collision box'
        close(vec(collision.find('geometry/box').get('size')),prop['box_size_m'],1e-14,'actual STL collision size')
    close(sum(mass.values()),.1842,1e-14,'gripper total mass')
    assert len(links[-1])==0,'tool0 frame only'
    asm=assets.readj(assets.ROOT/'models/arm-v3-kg1-assembly/assembly.json')
    mount=np.asarray(asm['mount']['g_to_link6_local'],float).copy()
    mount[:3,3]*=.001
    close(origin(tree.find("joint[@name='KG1_mount']")),mount,1e-12,'MP9 mount transform')
    trials=[(np.zeros(6),u) for u in [0.,10.,20.,35.,47.]]
    for i in range(6):
        for bound in ['lower','upper']:
            q=np.zeros(6)
            q[i]=float(joints[i].find('limit').get(bound))
            trials.append((q,[0.,20.,47.][i%3]))
    trials += [(np.radians([10,-20,30,-40,20,-30]),u) for u in [0.,20.,47.]]
    max_fk_error,max_motion_error,max_old_display_error=0.,0.,0.
    for q,u in trials:
        raw=joint_positions(2*u*.001)
        frames,resolved=fk(joints,{**{f'J{i+1}':float(v) for i,v in enumerate(q)},'KG1_slide_A':raw['KG1_slide_A']})
        for name,value in raw.items():
            close(resolved[name],value,1e-14,'logical raw command')
        reference=arm_reference(q)
        for name in reference:
            max_fk_error=max(max_fk_error,close(frames[name],reference[name],1e-12,'independent arm FK'))
        gw=reference['Link6']@mount
        close(frames['KG1'],gw,1e-12,'gripper base FK')
        cad_items=assets.items(u)
        for group,name in assets.GROUPS.items():
            expected=np.concatenate([item['v'][item['f']]*.001 for item in cad_items if item['group']==group])
            actual=transformed(source_tri[name],frames[name])
            max_motion_error=max(max_motion_error,close(actual,transformed(expected,gw),8e-8,'CAD physical vertex motion'))
        if u==20. and np.array_equal(q,np.zeros(6)):
            # Restore original item ordering to compare every triangle to former rigid KG1.
            cursors={name:0 for name in assets.GROUPS.values()}
            restored=[]
            for record in records:
                name,n=record['link'],record['triangles']
                start=cursors[name]
                restored.append(transformed(source_tri[name][start:start+n],np.linalg.inv(gw)@frames[name]))
                cursors[name]+=n
            oldtri=np.asarray(trimesh.load(assets.OLD/'meshes/KG1.stl',force='mesh',process=False).triangles)
            max_old_display_error=close(np.concatenate(restored),oldtri,8e-8,'old display triangle equivalence')
    for bad in [True,False,float('nan'),float('inf'),-.001,.094001,'0.04',None]:
        try:
            joint_positions(bad)
        except ValueError:
            continue
        raise AssertionError('invalid logical opening accepted')
    prov=assets.readj(model/'provenance.json')
    assert prov['input_census']==assets.census(),'source preservation'
    assert prov['physics_acceptance'].startswith('NOT_RUN'),'static acceptance scope'
    actual={p.relative_to(model).as_posix():assets.sha(p) for p in sorted(model.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    assert assets.readj(model/'manifest.json')['files']==actual,'manifest actual payload binding'
    return {'ok':True,'scope':'STATIC_ONLY_068','links':12,'physical_links':11,'movable_joints':9,
        'independent_coordinates':7,'gripper_source_items':47,'groups':{'F':23,'A':6,'B':6,'R':12},
        'motion_trials':len(trials),'max_mesh_error_m':max_mesh_error,'max_FK_component_error':max_fk_error,
        'max_CAD_physical_vertex_error_m':max_motion_error,'max_old_display_triangle_error_m':max_old_display_error,
        'gripper_mass_kg':sum(mass.values()),'total_assumed_mass_kg':4.15+sum(mass.values()),
        'source_inputs_preserved':len(prov['input_census'])}

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',type=Path,default=assets.MODEL)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    result=verify(args.model)
    if args.out:
        assets.writej(args.out,result)
    print(json.dumps(result,indent=2))
