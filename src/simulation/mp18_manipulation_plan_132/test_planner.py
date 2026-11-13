"""132 local HOST; physical grasp and SDK are deliberately not fabricated."""
import copy,importlib.util,json,math,unittest
from pathlib import Path
from unittest import mock
P=Path(__file__).with_name('planner.py');spec=importlib.util.spec_from_file_location('planner132',P);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.s=M.parse(P.with_name('scenario.json').read_bytes());cls.C,cls.model,_=M.sources()
    def bad(self,mutation):
        s=copy.deepcopy(self.s);mutation(s)
        with self.assertRaises(ValueError):M.validate(s)
    def test01_actual_schema_and_runtime_API(self):
        r=M.validate(self.s);self.assertEqual(r['status'],'STATIC_PLAN_VALID_RUNTIME_NOT_RUN');self.assertGreater(r['lift_m'],.020);self.assertGreater(r['transport_xy_m'],.150)
        self.assertEqual(M.build_scenario(),self.s)
        for k in range(self.s['duration_s']*120+1):
            p=M.sample(self.s,k/120);self.assertEqual(set(p['targets']),set(M.NAMES));self.assertEqual(set(p['reference_velocity']),set(M.NAMES))
            self.assertAlmostEqual(p['targets']['KG1_slide_B'],p['targets']['KG1_slide_A']);self.assertAlmostEqual(p['targets']['KG1_pinion'],M.RATIO*p['targets']['KG1_slide_A'])
        self.assertEqual(M.sample(self.s,85)['phase'],'home_settle')
    def test02_named_limits_mimic_and_velocity_attacks(self):
        self.bad(lambda s:s['stages'][0]['targets_si'].update(J7=0))
        self.bad(lambda s:s['stages'][0]['targets_si'].update(J2=10))
        self.bad(lambda s:s['stages'][0]['targets_si'].update(KG1_slide_B=-.01))
        self.bad(lambda s:s['stages'][0].update(duration_steps=120,end_s=1))
        self.bad(lambda s:s['stages'][0]['targets_si'].update(J1=float('nan')))
    def test03_actual_mesh_pad_and_closure_sign(self):
        measured=M.measure_pad_band();self.assertEqual(set(measured),{'visual','collision'})
        for kind in measured:
            for row in measured[kind]:self.assertAlmostEqual(row['gap_m'],.040,places=5)
        open_q=self.s['stages'][7]['targets_si'];closed_q=self.s['stages'][8]['targets_si']
        self.assertLess(closed_q['KG1_slide_A'],open_q['KG1_slide_A'])
        def width(q):
            fk=self.C.fk(self.model,q);A=self.C.mv(self.C.mm(self.C.inverse(fk['KG1']),fk['KG1_A']),[0,0,.104,1]);B=self.C.mv(self.C.mm(self.C.inverse(fk['KG1']),fk['KG1_B']),[0,0,.104,1]);return B[0]-A[0]
        self.assertAlmostEqual(width(open_q),.060);self.assertAlmostEqual(width(closed_q),.019)
        self.bad(lambda s:s['grasp'].update(pinion_multiplier=-M.RATIO))
    def test04_source_binding_and_current_raw_attack(self):
        self.bad(lambda s:s['source_pins'][M.MODEL].update(sha256='0'*64))
        original=Path.read_bytes
        def mutated(p):
            raw=original(p)
            return raw+b'\n' if p==M.ROOT/M.CONTRACT else raw
        with mock.patch.object(Path,'read_bytes',mutated):
            with self.assertRaisesRegex(ValueError,'Contract pin'):M.validate(self.s)
    def test05_object_gap_yaw_floor_and_false_grasp_attacks(self):
        self.bad(lambda s:s['object'].update(dimensions_m=[.04,.01,.008]))
        self.bad(lambda s:s['object']['source_T_world'][2].__setitem__(3,-.01))
        self.bad(lambda s:s['pedestals'][0].update(yaw_rad=0))
        self.bad(lambda s:s['runtime_grasp_status'].__class__ and s.update(runtime_grasp_status='PASS'))
        self.bad(lambda s:s['acceptance'].update(static_grasp_success=True))
    def test06_actual_FK_grasp_source_destination_and_safe_home(self):
        for phase,key in [(7,'source_grasp_T_world'),(10,'lift_grasp_T_world'),(12,'destination_grasp_T_world')]:
            fk=self.C.fk(self.model,self.s['stages'][phase]['targets_si']);actual=self.C.mm(fk['KG1'],self.C.tf([0,0,.104],[r[:3] for r in self.C.ident()[:3]]));self.C.near(actual,self.s['geometry_hypothesis'][key],1e-12)
            self.assertLess(abs(actual[0][2])+abs(actual[1][2]),1e-12);self.assertAlmostEqual(actual[2][2],-1)
        import numpy as np,trimesh
        q=self.s['stages'][0]['targets_si'];fk=self.C.fk(self.model,q);floor=1
        for name,row in self.model['links'].items():
            if name=='Base':continue
            for entry in row['collisions']:
                v=trimesh.load(Path(self.model['model_dir'])/entry['file'],force='mesh',process=False).vertices;T=np.asarray(fk[name]);floor=min(floor,float((v@T[:3,:3].T+T[:3,3])[:,2].min()))
        self.assertGreater(floor,.05)
    def test07_duration_boundaries_and_continuity(self):
        for t in self.s['boundaries_s']:
            row=M.sample(self.s,t);self.assertLess(max(abs(x) for x in row['reference_velocity'].values()),1e-10)
            if t<85:
                nextrow=M.sample(self.s,t+1e-6);self.assertLess(max(abs(row['targets'][n]-nextrow['targets'][n]) for n in M.NAMES),1e-10)
        for t in [-1,86,float('nan')]:
            with self.assertRaises(ValueError):M.sample(self.s,t)
        self.bad(lambda s:s['stages'][0].update(duration_steps=720.5))
        self.bad(lambda s:s['stages'][2].update(name='typo'))
    def test08_immutable_criteria_gain_caps_no_attachment(self):
        for k,v in [('arm_stiffness',65),('arm_damping',15),('floor_z_m',-.1),('source_velocity_tolerance',.001),('object_attachment_forbidden',False)]:
            self.bad(lambda s,k=k,v=v:s['policy'].update({k:v}))
        self.bad(lambda s:s['policy']['caps_si'].update(J2=13))
        self.assertEqual(self.s['hardware_approved'],False);self.assertEqual(self.s['runtime_grasp_status'],'NOT_RUN')
        self.assertIn('unresolved',' '.join(self.s['limitations']))
    def test09_actual_object_sweep(self):
        r=M.measure_object_sweep(self.s);self.assertEqual(r['sampled_steps'],10201);self.assertEqual(r['unexpected_object_overlap'],{})
        self.assertGreater(r['nonjaw_object_separation_lower_bound_m'],0)
        Path(M.ROOT/'outputs/mp18-manipulation-plan-132/HOST/object-sweep.json').write_bytes(M.canonical(r))
if __name__=='__main__':unittest.main(verbosity=2)
