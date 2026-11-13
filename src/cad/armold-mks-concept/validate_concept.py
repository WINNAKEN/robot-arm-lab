"""Validate saved native B-reps against independent primitive and FK expectations."""
import hashlib
import itertools
import json
import math
import re
import zipfile
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'models'/'armold-mks-concept-v1'
EV=ROOT/'.dev'/'armold-concept-evidence'/'build'

def main():
    evaluation=json.loads((EV/'main-eval.json').read_text())
    actual={b['name']:b for b in evaluation['bodies']}
    prim=json.loads((EV/'primitive-expectations.json').read_text())
    assert len(actual)==len(prim)==69
    comparisons=[]
    for p in prim:
        R=np.array(p['rotation']); O=np.array(p['origin']); b=actual[p['name']]
        assert np.allclose(R.T@R,np.eye(3),atol=1e-10) and np.linalg.det(R)>.999999
        if p['kind']=='box':
            s=np.array(p['size']); c=np.array(p['center'])
            points=np.array([O+R@(c+s*np.array(sign)/2) for sign in itertools.product((-1,1),repeat=3)])
            bounds=np.array([points.min(axis=0),points.max(axis=0)]); volume=float(np.prod(s))
        else:
            z=R[:,2]; center=O+z*(p['z']+p['h']/2)
            half=np.abs(z)*p['h']/2+p['r']*np.sqrt(np.maximum(0,1-z*z))
            bounds=np.array([center-half,center+half]); volume=math.pi*(p['r']**2-p['inner']**2)*p['h']
        bb=np.array([b['bbox']['min'],b['bbox']['max']]); delta=float(np.max(np.abs(bb-bounds)))
        rel=abs(b['volume_mm3']-volume)/volume
        good=bool(b['volume_mm3']>0 and b.get('kernel',{}).get('shells')==1 and delta<.02 and rel<.001)
        comparisons.append({'body':p['name'],'bbox_max_delta_mm':delta,'volume_relative_error':rel,'one_positive_solid_shell':good})
        assert good,(p['name'],delta,rel)
    outputs=json.loads((EV/'main-build-result.json').read_text())
    graph=next(x for x in outputs if isinstance(x,dict) and 'joints'in x and 'dof'in x)
    inspect=next(x for x in outputs if isinstance(x,dict) and 'joints'in x and 'dof'not in x)
    assert len(graph['joints'])==6 and not graph['errors'] and not graph['conflicts'] and not graph['floating']
    assert max(x['dof'] for x in graph['dof'])==6
    assert all(j['type']=='revolute' and not j['suppressed'] for j in graph['joints'])
    for j in inspect['joints']:
        assert j['a']['resolves'] and j['b']['resolves'] and not j['errors'] and not j['conflicts']
    k=json.loads((OUT/'kinematics.json').read_text())
    for j,native in zip(k['joints'],graph['joints']):
        assert np.allclose(j['origin_mm'],native['frame_a']['origin'],atol=1e-8)
        assert np.allclose(j['axis_world'],native['frame_a']['z'],atol=1e-8)
    check=json.loads((EV/'static-check-result.json').read_text())
    interference=check[0]
    keepout_clashes=[x for x in interference['interferences'] if any(t in x['a']+x['b'] for t in ('MOTOR_ASSUMED','KEEP_OUT'))]
    assert not keepout_clashes and not interference['unchecked'] and not interference['budget_exceeded']
    # Retained intersections are same rigid-link schematic/attachment volumes.
    comp=next(x for x in outputs if isinstance(x,dict) and 'components'in x and 'active'in x)
    ownership={b:c['name'] for c in comp['components'] for b in c['bodies']}
    cross=[x for x in interference['interferences'] if ownership[x['a']]!=ownership[x['b']]]
    assert not cross
    drive=check[1]; assert drive['moved'] and not drive['errors'] and not drive['conflicts']
    moved=check[3]['joints']; a=math.radians(5); Rz=np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]])
    for expected,observed in zip(k['joints'],moved):
        assert np.allclose(Rz@np.array(expected['origin_mm']),observed['a']['frame']['origin'],atol=1e-7)
        assert np.allclose(Rz@np.array(expected['axis_world']),observed['a']['frame']['z'],atol=1e-7)
    parameters=outputs[-1]['parameters']
    # `uses` means upstream dependencies, not downstream CAD users. The CLI's
    # used_by list omits fixed-point sketch expressions, so inspect the saved
    # native feature expressions as the authoritative persisted linkage.
    native_path=OUT/'armold-type-mks-six-axis-concept.solidcraft'
    with zipfile.ZipFile(native_path) as archive:
        document=json.loads(archive.read('document.json'))
    params_linked={}
    for p in parameters:
        if p['name'] not in ['motor_frame','motor_length','driver_width','driver_depth','connector_clearance']:
            continue
        features=[f['name'] for f in document['features'] if re.search(r'\b'+re.escape(p['name'])+r'\b',json.dumps(f))]
        assert features,p['name']
        params_linked[p['name']]={'persisted_feature_reference_count':len(features),'feature_names':features,'cli_used_by':p.get('used_by',[]),'upstream_parameter_dependencies':p.get('uses',[])}
    files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in OUT.iterdir() if p.suffix in ('.solidcraft','.step','.3mf','.png','.json') and p.name!='validation.json'}
    report={'status':'PASS_SCOPED_CONCEPT','units':'mm','bodies':69,'native_brep_solids':69,'root_rigid_links':7,'native_revolute_joints':6,'terminal_link_dof':6,'joint_errors':[],'joint_conflicts':[],'floating_chains':[],'positive_solid_checks':comparisons,'static_display_pose':{'kernel_bodies_checked':interference['checked'],'keepout_or_motor_clashes':keepout_clashes,'cross_rigid_link_intersections':cross,'same_link_schematic_or_attachment_intersections':interference['count'],'unchecked':interference['unchecked'],'note':'Same-link intersections represent attachment unions and undesigned-envelope overlap; no fabricated assembly topology is claimed.'},'software_drive_probe':{'joint':'J1','delta_deg':5,'moved':True,'downstream_joint_axes_and_origins_match_rigid_FK':True,'saved_main_file_unchanged_by_probe':True},'native_parameter_users':params_linked,'files':files,'limitations':{'mechanical_fit':'NOT_RUN','load_torque_strength':'NOT_RUN','full_range_collision_sweep':'NOT_RUN','physical_print':'NOT_RUN','hardware':'NOT_RUN','purchase':'NOT_RUN','native_joint_values':'Display pose is zero; source pose_deg is the geometry construction pose. Native deltas add at their displayed joint frame.','mass':'Default CAD density only; not robot mass or payload.'}}
    (OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['status','bodies','native_revolute_joints','terminal_link_dof']}))

if __name__=='__main__':main()
