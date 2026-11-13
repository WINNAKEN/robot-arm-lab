"""137 pure policy controls. Native dispatch is exercised by test_prepare."""
from pathlib import Path
import copy,math,types,unittest

ROOT=Path(__file__).absolute().parents[3]
raw=(Path(__file__).parent/'feedback.py').read_bytes();F=types.ModuleType('feedback137_test');exec(compile(raw,'feedback.py','exec'),F.__dict__)

def fixture():
    joints={n:dict(type='prismatic'if'slide'in n else'revolute',lower=v[0],upper=v[1],effort=v[2],velocity=v[3],axis=list(v[4]))for n,v in F.LIMITS.items()}
    joints[F.FOLLOWER]['mimic']={'joint':F.LEADER,'multiplier':F.RATIO,'offset':0.}
    joints[F.OTHER]['mimic']={'joint':F.LEADER,'multiplier':1.,'offset':0.}
    model={'movable':list(F.NAMES),'joints':joints}
    q={n:0. for n in F.NAMES};qd=dict(q);q[F.LEADER]=-.010016066953539848;q[F.OTHER]=-.010016286745667458;qd[F.LEADER]=.001
    clock={'engine_time_s':57.,'lab_step':6840};state={'q':q,'qd':qd,'clock':dict(clock),'clock_before':dict(clock),'clock_after':dict(clock)}
    target={k:{n:0. for n in F.NAMES}for k in ['targets','velocity_targets','reference_velocity']};target['targets'][F.LEADER]=target['targets'][F.OTHER]=-.0105;target['targets'][F.FOLLOWER]=.7777777777777779
    return model,state,target,clock

class PolicyTests(unittest.TestCase):
    def test_actual_lag_changes_only_pinion_and_does_not_mutate(self):
        m,s,t,c=fixture();before=copy.deepcopy((m,s,t,c));r=F.reference(t,s,m,list(F.NAMES),c,6841)
        self.assertAlmostEqual(r['positions'][F.FOLLOWER],F.RATIO*s['q'][F.LEADER],places=7)
        self.assertGreater(abs(t['targets'][F.FOLLOWER]-r['positions'][F.FOLLOWER]),.03)
        self.assertAlmostEqual(r['velocities'][F.FOLLOWER],F.RATIO*.001,places=7)
        self.assertEqual((m,s,t,c),before)
        for n in F.NAMES:
            if n!=F.FOLLOWER:self.assertEqual(r['positions'][n],F.binary32(t['targets'][n]));self.assertEqual(r['velocities'][n],t['velocity_targets'][n])
    def test_permuted_names_preserve_named_output(self):
        m,s,t,c=fixture();a=F.reference(t,s,m,list(F.NAMES),c,6841);b=F.reference(t,s,m,list(reversed(F.NAMES)),c,6841)
        self.assertEqual(a['positions'],b['positions']);self.assertEqual(a['velocities'],b['velocities'])
    def test_bad_scalars_and_missing_census(self):
        for bad in [True,float('nan'),float('inf'),[0.],None]:
            m,s,t,c=fixture();s['q'][F.LEADER]=bad
            with self.subTest(value=bad),self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,6841)
        m,s,t,c=fixture();s['qd'].pop('J1')
        with self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,6841)
    def test_causal_clock_and_order_reject(self):
        for field in ['clock','clock_before','clock_after']:
            m,s,t,c=fixture();s[field]['lab_step']-=1
            with self.subTest(field=field),self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,6841)
        m,s,t,c=fixture()
        for command in [True,0,6840,6842]:
            with self.subTest(command=command),self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,command)
    def test_model_ratio_axis_and_limits_reject(self):
        for field,value in [('multiplier',-F.RATIO),('multiplier',F.RATIO*1000),('joint',F.OTHER),('offset',.01)]:
            m,s,t,c=fixture();m['joints'][F.FOLLOWER]['mimic'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,6841)
        m,s,t,c=fixture();m['joints']['J2']['velocity']=100
        with self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,6841)
    def test_limits_are_not_clamped_or_target_fallback(self):
        for q,qd in [(-.021,0.),(.028,0.),(0.,.021)]:
            m,s,t,c=fixture();s['q'][F.LEADER]=q;s['qd'][F.LEADER]=qd
            with self.subTest(q=q,qd=qd),self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,6841)
        m,s,t,c=fixture();t['targets']['J2']=10.
        with self.assertRaises(ValueError):F.reference(t,s,m,list(F.NAMES),c,6841)
    def test_readback_clock_or_corruption_fails(self):
        m,s,t,c=fixture();r=F.reference(t,s,m,list(F.NAMES),c,6841);p=dict(r['positions']);p[F.FOLLOWER]+=.01
        with self.assertRaises(ValueError):F.acknowledge(r,p,r['velocities'],c)
        self.assertFalse(r['readback_verified']);late=dict(c,lab_step=6841,engine_time_s=6841/120)
        with self.assertRaises(ValueError):F.guard_clock(r,late)
        F.acknowledge(r,r['positions'],r['velocities'],c);self.assertTrue(r['readback_verified'])
    def test_journal_initial_and_applied_are_distinct(self):
        self.assertEqual(F.journal_row({'step':0},None)['applied137']['status'],'NOT_APPLIED_INITIAL_ROW')
        with self.assertRaises(ValueError):F.journal_row({'step':1},None)
        m,s,t,c=fixture();r=F.reference(t,s,m,list(F.NAMES),c,6841);F.acknowledge(r,r['positions'],r['velocities'],c)
        row=F.journal_row({'step':6841},r);self.assertEqual(row['applied137']['source_step'],6840);r['positions']['J1']=8;self.assertNotEqual(row['applied137']['positions']['J1'],8)
    def test_A_leader_not_average_B_and_float32_error(self):
        m,s,t,c=fixture();s['q'][F.OTHER]=0.;r=F.reference(t,s,m,list(F.NAMES),c,6841)
        self.assertEqual(r['positions'][F.FOLLOWER],F.binary32(F.RATIO*s['q'][F.LEADER]));self.assertGreater(abs(r['B_relative_reference_residual_rad']),.7)
        self.assertLess(abs(r['binary32_position_error_rad']),1e-7)

if __name__=='__main__':unittest.main(verbosity=2)
