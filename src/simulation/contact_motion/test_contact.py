"""043 host contract tests only; no Isaac, SSH or hardware execution."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
try:
    from . import verify as V
except ImportError:
    import verify as V
C, E = V.C, V.E
ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT/'outputs/isaac-motion-v1/runs/6202d94eecf2492294b4ebbbbc5921c7/retrieved/6202d94eecf2492294b4ebbbbc5921c7'


def fixture():
    s = json.loads((RUN/'static.json').read_text())
    s['configuration'].update(gravity=[0.,0.,-9.81],self_collisions=True)
    for collider in s['colliders']:
        collider['enabled']=True
    with (RUN/'samples.ndjson').open() as stream:
        row=json.loads(next(stream))
    return s,row['links']


def environment_fixture():
    inertia=.1*.05*.05/6
    mass={'mass':.1,'com':[0,0,0],'principal_axes_wxyz':[1,0,0,0],'inertia_diag':[inertia]*3}
    shape={'position':[-.6,0,.2],'basis':V.IDENTITY,'size':.05,'collision_enabled':True,'rigid':True,'path':E.PROBE}
    return {'actors':E.SENSORS[:], 'colliders':[p+'/assumed_aabb_proxy' for p in E.PATHS]+[E.GROUND,E.PROBE],
        'ground':{'position':[0,0,-.05],'basis':[[4,0,0],[0,4,0],[0,0,.1]],'size':1.,'collision_enabled':True,'rigid':False,'path':E.GROUND},
        'probe':{**shape,**mass,'collider_owner_path':E.PROBE,'collider_local_position':[0,0,0],'collider_local_basis':V.IDENTITY},
        'probe_source_observation':{**mass,'path':E.PROBE,'position':[-.6,0,.2],'rotation':V.IDENTITY},
        'probe_runtime_mass':{**mass,'inertia_link_about_com':[[inertia if i==j else 0 for j in range(3)] for i in range(3)]},
        'material':{'path':E.MATERIAL,'static_friction':.6,'dynamic_friction':.5,'restitution':0},
        'filters':{a:[b] for a,b in zip(E.PATHS,E.PATHS[1:])},'joint_collisions':{n:True for n in V.JOINTS},
        'report_thresholds':{p:0 for p in E.SENSORS},
        'material_bindings':{p:[E.MATERIAL] for p in [x+'/assumed_aabb_proxy' for x in E.PATHS]+[E.GROUND,E.PROBE]},
        'contact_mapping':{'canonical_sensors':E.SENSORS,'canonical_filters':E.FILTERS,'capacity':512,'force_frame':'WORLD','force_units':'N',
            'sensor_paths':E.SENSORS[:],'filter_paths':[E.FILTERS[:] for _ in E.SENSORS]}}


class FakeContact:
    sensor_count,filter_count,max_contact_data_count=8,9,512
    sensor_paths=E.SENSORS[::-1];filter_paths=E.FILTERS[::-1]
    def create_rigid_contact_view(self,*args,**kwargs):return self
    def get_normal_contact_force_matrix(self,dt):
        a=np.zeros((8,9,3));a[0,8,2]=.981;return a
    def get_normal_contact_data(self,dt):
        f=np.zeros((512,1));p=np.zeros((512,3));n=np.zeros((512,3));d=np.zeros((512,1))
        count=np.zeros((8,9),dtype=int);start=np.zeros((8,9),dtype=int)
        f[0,0]=.981;n[0,2]=1;p[0,0]=-.6;count[0,8]=1
        return f,p,n,d,count,start


class Tests(unittest.TestCase):
    def test_virtual_work_gravity_sign_rotated_com_and_zero_g(self):
        s,_=fixture();_,_,F,layout,_,_=V.B.context(ROOT)
        bodies={b['name']:b for b in s['bodies']}
        def poses(q):
            rows=[{'origin_m':[0,0,0],'rotation_world':V.IDENTITY}]+F.fk(layout,q)
            result=[]
            for name,r in zip(C.LINKS,rows):
                R=np.array(r['rotation_world']);w=math.sqrt(1+np.trace(R))/2
                quat=[w,(R[2,1]-R[1,2])/(4*w),(R[0,2]-R[2,0])/(4*w),(R[1,0]-R[0,1])/(4*w)]
                result.append({'name':name,'position':r['origin_m'],'orientation_wxyz':[float(v) for v in quat]})
            return result
        def energy(q):
            return sum(bodies[p['name']]['mass']*9.81*(p['position'][2]+V.mv(V.quaternion(p['orientation_wxyz']),bodies[p['name']]['com'])[2]) for p in poses(q))
        for q in ([0.]*6,[.04,-.07,.03,.02,-.05,.03]):
            observed=poses(q);tau=C.gravity_efforts(s,observed)
            self.assertEqual(C.gravity_efforts(s,observed,[0,0,0]),[0.]*6)
            for j in range(6):
                a=q[:];b=q[:];a[j]+=1e-6;b[j]-=1e-6
                self.assertAlmostEqual(tau[j],(energy(a)-energy(b))/2e-6,places=6)

    def test_total_effort_triangle_bound_and_invalid(self):
        for raw in ([100,-100,2,-.5,.3,0],[0]*6,[-3,6,-5,2,-2,1]):
            result=C.bounded_efforts(raw)
            self.assertTrue(all(abs(t)+p<=cap for t,p,cap in zip(result['ff'],result['pd_cap'],C.CAP)))
        for bad in ([float('nan')]*6,[0]*5):
            with self.assertRaises(ValueError):C.bounded_efforts(bad)

    def test_static_gravity_collision_source_mass_and_frame_gates(self):
        s,_=fixture();refmod,ref,_,_,core,_=V.B.context(ROOT)
        V.validate_static(s,refmod,ref,core,ROOT)
        for mutate in (lambda x:x['configuration'].update(gravity=[0,0,0]),lambda x:x['configuration'].update(self_collisions=False),
                       lambda x:x['colliders'][0].update(enabled=False),lambda x:x['colliders'][1]['local_position'].__setitem__(0,.4),
                       lambda x:x['runtime_masses'][1]['com'].__setitem__(0,.1)):
            bad=copy.deepcopy(s);mutate(bad)
            with self.assertRaises(ValueError):V.validate_static(bad,refmod,ref,core,ROOT)

    def test_all_environment_frames_filters_material_and_mapping(self):
        e=environment_fixture();V.validate_environment(e)
        changes=[lambda x:x['ground']['position'].__setitem__(2,.1),lambda x:x['ground']['basis'][2].__setitem__(2,.2),
            lambda x:x['probe']['collider_local_position'].__setitem__(0,.1),lambda x:x['probe']['com'].__setitem__(0,.01),
            lambda x:x['probe_runtime_mass']['inertia_link_about_com'][0].__setitem__(0,1),lambda x:x['probe_source_observation']['rotation'][0].__setitem__(0,-1),
            lambda x:x['filters'].pop(E.PATHS[0]),lambda x:x['filters'].update({E.PROBE:[E.GROUND]}),
            lambda x:x['material'].update(restitution=.9),lambda x:x['material_bindings'].pop(E.GROUND),
            lambda x:x['contact_mapping']['sensor_paths'].pop(),lambda x:x['contact_mapping'].update(force_units='impulse'),
            lambda x:x['actors'].append('/World/Unknown'),lambda x:x['colliders'].pop()]
        for change in changes:
            bad=copy.deepcopy(e);change(bad)
            with self.assertRaises(ValueError):V.validate_environment(bad)

    def test_contact_tensor_mapping_detail_units_and_capacity(self):
        reader=E.ContactReader(FakeContact());data=reader.read(1/120)
        self.assertAlmostEqual(data['normal_force_N'][7][0][2],.981)
        self.assertEqual(data['active'][0]['sensor'],7);self.assertEqual(data['active'][0]['filter'],0)
        class Overflow(FakeContact):
            def get_normal_contact_data(self,dt):
                values=list(super().get_normal_contact_data(dt));values[4][0,8]=512;return values
        with self.assertRaises(ValueError):E.ContactReader(Overflow()).read(1/120)

    def test_contact_positive_and_negative_controls_effort_readback(self):
        s,links=fixture();contacts=E.ContactReader(FakeContact()).read(1/120)
        rows=[]
        for i,z in enumerate((.2,.025)):
            effort=C.bounded_efforts(C.gravity_efforts(s,links))
            command={**effort,'ff_readback':effort['ff'][:],'pd_cap_readback':effort['pd_cap'][:],'source_index':0,'read_step':4}
            rows.append({'index':i,'links':links,'contacts':copy.deepcopy(contacts),
                'probe_pose':{'position':[-.6,0,z],'orientation_wxyz':[1,0,0,0]},'actuation':command if i else None,'clock':{'step_before':4}})
        rows[0]['contacts']={'normal_force_N':np.zeros((8,9,3)).tolist(),'counts':np.zeros((8,9),dtype=int).tolist(),'active':[],'dt_s':1/120}
        self.assertEqual(V.audit_contacts(s,rows)['dynamic_failures'],[])
        bad=copy.deepcopy(rows)
        for row in bad:
            row['contacts']={'normal_force_N':np.zeros((8,9,3)).tolist(),'counts':np.zeros((8,9),dtype=int).tolist(),'active':[],'dt_s':1/120}
        self.assertIn('CONTACT_ENGINE_POSITIVE_CONTROL_FAILED',V.audit_contacts(s,bad)['dynamic_failures'])
        bad=copy.deepcopy(rows);bad[1]['contacts']['normal_force_N'][7][0][2]=2
        with self.assertRaises(ValueError):V.audit_contacts(s,bad)
        bad=copy.deepcopy(rows);bad[1]['contacts']['active'][0]['point'][0]=0.
        with self.assertRaises(ValueError):V.audit_contacts(s,bad)
        bad=copy.deepcopy(rows);bad[1]['actuation']['ff_readback'][1]+=1
        with self.assertRaises(ValueError):V.audit_contacts(s,bad)

    def test_missing_job_fails_before_isaac_import(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(V.R.worker(Path(folder)),1)
            self.assertEqual(json.loads((Path(folder)/'status.json').read_text())['status'],'FAILED')

    def test_full_clock_schema_is_checked_independently_of_tracking_outcome(self):
        static=json.loads((RUN/'static.json').read_text())
        rows=[json.loads(line) for line in (RUN/'samples.ndjson').read_text().splitlines()]
        program=C.load_program(ROOT/'src/simulation/motion/program.json')
        V.audit_record_quality(static,rows,program,C.motion)
        rows[-1]['clock']['callback_count']-=1
        with self.assertRaises(ValueError):V.audit_record_quality(static,rows,program,C.motion)

    def test_approved_dependencies_reject_modified_bytes_before_execution(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('_contact_render_test',Path(__file__).with_name('render.py'))
        render=importlib.util.module_from_spec(spec);spec.loader.exec_module(render)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'changed.py';p.write_text("raise RuntimeError('MUST NOT EXECUTE')")
            with self.assertRaisesRegex(ValueError,'dependency hash drift'):
                V.module('_forbidden_modified_verify',p,V.BASE_VERIFY_SHA)
            with self.assertRaisesRegex(ValueError,'dependency hash drift'):
                render.load_module('_forbidden_modified_replay',p,render.BASE_REPLAY_SHA)


if __name__=='__main__':unittest.main()
