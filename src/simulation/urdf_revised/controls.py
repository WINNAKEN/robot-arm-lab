"""067 resealed contradictory-asset controls against the actual static consumer."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assets
import verify

def xml_change(model, path, attr, value):
    p = model/'robot_arm.urdf'
    tree = ET.parse(p)
    tree.find(path).set(attr,value)
    tree.write(p,encoding='utf-8',xml_declaration=True)

def owner_change(model):
    p = model/'asset-ledger.json'
    v = assets.readj(p)
    v['source_bodies'][0]['link'] = 'Link1'
    assets.writej(p,v)

def mesh_change(model):
    p = model/'meshes/Link2.stl'
    raw = bytearray(p.read_bytes())
    x = struct.unpack_from('<f',raw,96)[0]
    struct.pack_into('<f',raw,96,x+.001)
    p.write_bytes(raw)

def main():
    dest = assets.OUT/'controls'
    dest.mkdir(parents=True,exist_ok=True)
    cases = [
      ('joint_origin',lambda m:xml_change(m,"joint[@name='J3']/origin",'xyz','0.166 0 0'),'legacy joint origin'),
      ('axis_flip',lambda m:xml_change(m,"joint[@name='J5']/axis",'xyz','0 -1 0'),'legacy axis'),
      ('visual_rotation',lambda m:xml_change(m,"link[@name='Link2']/visual/origin",'rpy','0.2 0 0'),'visual identity'),
      ('mesh_scale_1000',lambda m:xml_change(m,"link[@name='Link2']/visual/geometry/mesh",'scale','1000 1000 1000'),'metre mesh scale'),
      ('collision_size',lambda m:xml_change(m,"link[@name='Link2']/collision/geometry/box",'size','1 1 1'),'actual STL collision size'),
      ('inertia',lambda m:xml_change(m,"link[@name='Link2']/inertial/inertia",'ixx','0.05'),'actual STL box inertia'),
      ('inertial_rotation',lambda m:xml_change(m,"link[@name='Link2']/inertial/origin",'rpy','0.1 0 0'),'inertial RPY'),
      ('collision_rotation',lambda m:xml_change(m,"link[@name='Link2']/collision/origin",'rpy','0.1 0 0'),'collision RPY'),
      ('mass',lambda m:xml_change(m,"link[@name='KG1']/inertial/mass",'value','0.3'),'assumed source mass'),
      ('mount',lambda m:xml_change(m,"joint[@name='KG1_mount']/origin",'xyz','0.032 0 0'),'MP9 fixed mount'),
      ('tcp',lambda m:xml_change(m,"joint[@name='tool0_mount']/origin",'xyz','0 0 0.107'),'nominal tool0'),
      ('ownership',owner_change,'source ownership/cardinality ledger'),
      ('mesh_vertex',mesh_change,'actual STL/source vertices'),
    ]
    assert len(cases) == 13
    before = verify.verify()
    results = []
    for name, mutate, expected in cases:
        model = dest/name
        if model.exists():
            raise RuntimeError('Refusing to overwrite preserved control '+name)
        shutil.copytree(assets.MODEL,model)
        mutate(model)
        assets.seal(model)
        manifest = assets.readj(model/'manifest.json')['files']
        assert all(assets.sha(model/p)==h for p,h in manifest.items()), 'control must be correctly resealed'
        try:
            verify.verify(model)
        except AssertionError as exc:
            message = str(exc)
            results.append({'name':name,'rejected':True,'intended_check':expected,'error':message,'intended_reached':expected in message,'manifest_resealed':True})
        else:
            results.append({'name':name,'rejected':False,'intended_check':expected,'intended_reached':False,'manifest_resealed':True})
    after = verify.verify()
    report = {'positive_before':before,'controls':results,'expected_controls':13,
              'all_caught':all(r['rejected'] and r['intended_reached'] for r in results), 'positive_after':after}
    assets.writej(assets.OUT/'semantic-controls.json',report)
    print(json.dumps({'all_caught':report['all_caught'],'controls':results},indent=2))
    assert report['all_caught']

if __name__ == '__main__':
    main()
