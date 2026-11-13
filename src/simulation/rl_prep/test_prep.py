"""Offline behavior/mutation tests. No native simulation or learning."""
import copy
from dataclasses import replace
import math
from pathlib import Path
import shutil
import tempfile
import unittest
try:
    from . import profile,prepare,policy_io,isaaclab_adapter
    from .trajectory import segment,action_reference
    from .task import State,MockBackend,JointReachTask
except ImportError:
    import profile,prepare,policy_io,isaaclab_adapter
    from trajectory import segment,action_reference
    from task import State,MockBackend,JointReachTask


def clone(root):
    """Copy only input dependencies, never run or import original043 helpers."""
    d=profile.read(profile.ROOT/'outputs/isaac-contact-v1/delivery.json')
    cfg=profile.configuration();names=set(cfg['input_pins'])|set(d['source_sha256'])|set(prepare.sources(profile.ROOT))
    names.add('outputs/isaac-contact-v1/runs/'+d['run_id']+'/retrieved/'+d['run_id']+'/validation.json')
    names.add('outputs/rl-prep-v1/evidence/environment.json')
    for name in names:
        target=Path(root)/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(profile.ROOT/name,target)


class InjectedBackend(MockBackend):
    def __init__(self,change):self.change=change
    def execute_reference(self,reference):return self.change(super().execute_reference(reference))


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.p=profile.build();cls.cfg=cls.p['config'];cls.lim=cls.cfg['limits']

    def task(self,backend=None,goal=None):
        t=JointReachTask(self.p,backend or MockBackend());t.reset(goal=goal,randomize=False);return t

    def test_quintic_physical_bounds_and_knots(self):
        rows=segment([-.17]*6,[.17]*6,self.lim)
        self.assertGreater(rows[-1]['t_s'],2)
        for r in (rows[0],rows[-1]):
            self.assertEqual(r['qd'],[0]*6);self.assertEqual(r['qdd'],[0]*6)
        for key,cap in [('qd',.2),('qdd',.5),('jerk',2)]:
            self.assertLessEqual(max(abs(x) for r in rows for x in r[key]),cap+1e-9)
        for i in range(2,len(rows)-62):
            derivative=(rows[i+1]['q'][0]-rows[i-1]['q'][0])*60
            self.assertAlmostEqual(derivative,rows[i]['qd'][0],delta=2e-5)

    def test_duration_scales_for_each_derivative_bound(self):
        for key in ('velocity_rad_s','acceleration_rad_s2','jerk_rad_s3'):
            limits={**self.lim,key:.001}
            rows=segment([0]*6,[.03]*6,limits)
            self.assertGreater(rows[-1]['t_s'],2)

    def test_zero_move_and_fixed_action_clock(self):
        rows=segment([0]*6,[0]*6,self.lim)
        self.assertEqual(len(rows),241);self.assertEqual(rows[-1]['t_s'],2)
        target,clipped,rows=action_reference([math.radians(9.5)]*6,[99]*6,self.cfg)
        self.assertEqual(clipped,[1]*6);self.assertEqual(target,[math.radians(10)]*6)
        self.assertEqual(len(rows),241)

    def test_reject_nonfinite_boolean_and_bad_range(self):
        for bad in (True,float('nan'),float('inf'),'1'):
            with self.assertRaises(ValueError):action_reference([0]*6,[bad]*6,self.cfg)
        with self.assertRaises(ValueError):segment([0]*6,[1]*6,self.lim)
        with self.assertRaises(ValueError):segment([0]*6,[0]*6,self.lim,hold_s=.501)
        with self.assertRaises(ValueError):State((0,)*6,(0,)*6,0,True)

    def test_seeded_reset_and_41_observations(self):
        a=JointReachTask(self.p,MockBackend());b=JointReachTask(self.p,MockBackend())
        self.assertEqual(a.reset(seed=9),b.reset(seed=9));self.assertEqual(a.state,b.state)
        self.assertEqual(len(a.observation()[0]),41)
        self.assertLessEqual(max(map(abs,a.state.q)),math.radians(4))
        self.assertLessEqual(max(map(abs,a.state.qd)),math.radians(8))

    def test_success_requires_full_half_second_61_samples(self):
        t=self.task(goal=[0]*6);obs,reward,done,timeout,info=t.step([0]*6)
        self.assertTrue(done and info['success']);self.assertFalse(timeout)
        self.assertEqual(info['raw_metrics']['settle_window_intervals'],60)
        # One bad sample at exactly the beginning of the final 0.5-second window.
        def fail_boundary(rows):
            rows[-61]=replace(rows[-61],q=(math.radians(.6),0,0,0,0,0));return rows
        t=self.task(InjectedBackend(fail_boundary),goal=[0]*6)
        self.assertFalse(t.step([0]*6)[4]['success'])

    def test_last_sample_success_does_not_hide_motion_in_hold(self):
        def change(rows):
            rows[-2]=replace(rows[-2],qd=(math.radians(2),0,0,0,0,0));return rows
        t=self.task(InjectedBackend(change),goal=[0]*6)
        self.assertFalse(t.step([0]*6)[4]['success'])

    def test_contact_anywhere_overrides_goal(self):
        def contact(rows):rows[1]=replace(rows[1],unexpected_contact=True);return rows
        t=self.task(InjectedBackend(contact),goal=[0]*6)
        _,reward,done,_,info=t.step([0]*6)
        self.assertTrue(done);self.assertFalse(info['success']);self.assertLess(reward,0)
        self.assertIn('UNEXPECTED_CONTACT',info['faults']);self.assertEqual(info['reward_terms']['goal_bonus'],0)
        with self.assertRaises(ValueError):t.step([0]*6)

    def test_actor_clipping_cannot_hide_actual_speed_fault_or_jerk(self):
        def spike(rows):rows[-1]=replace(rows[-1],qd=(100,0,0,0,0,0));return rows
        t=self.task(InjectedBackend(spike),goal=[0]*6)
        obs,reward,done,_,info=t.step([0]*6)
        self.assertTrue(info['observation_clipped']);self.assertLessEqual(max(map(abs,obs)),5)
        self.assertIn('ACTUAL_SPEED_BOUND',info['faults']);self.assertTrue(done)
        self.assertGreater(info['raw_metrics']['actual_jerk_cost_unclipped'],1e8);self.assertLess(reward,-1e5)

    def test_position_fault_in_middle_not_masked_by_final_goal(self):
        def spike(rows):rows[100]=replace(rows[100],q=(1,0,0,0,0,0));return rows
        info=self.task(InjectedBackend(spike),goal=[0]*6).step([0]*6)[4]
        self.assertFalse(info['success']);self.assertIn('ACTUAL_JOINT_RANGE',info['faults'])

    def test_stale_short_or_wrong_clock_forces_reset(self):
        def stale(rows):rows[12]=rows[11];return rows
        def clock(rows):rows[3]=replace(rows[3],t_s=10);return rows
        for change in (lambda rows:rows[:-1],stale,clock):
            t=self.task(InjectedBackend(change))
            with self.assertRaises(ValueError):t.step([0]*6)
            self.assertTrue(t.needs_reset)
            with self.assertRaises(ValueError):t.step([0]*6)

    def test_idle_wrong_goal_costs_and_timeout_is_not_termination(self):
        t=self.task(goal=[math.radians(5)]*6)
        for i in range(16):
            _,reward,done,truncated,info=t.step([0]*6)
            self.assertFalse(done);self.assertFalse(info['success']);self.assertLess(reward,0)
            self.assertEqual(truncated,i==15)
        with self.assertRaises(ValueError):t.step([0]*6)

    def test_closer_goal_gives_progress_and_smoke_not_learning(self):
        t=self.task(goal=[math.radians(5)]*6)
        info=t.step([1]*6)[4];self.assertGreater(info['reward_terms']['progress'],0)
        report=prepare.smoke(self.p,profile.ROOT)
        self.assertEqual(report['learning'],'NOT_RUN');self.assertEqual(len(report['episodes']),3)
        self.assertTrue(all(e['scope']=='HOST_KINEMATIC_CONTRACT_TEST' for e in report['episodes']))

    def test_failed_original_baseline_blocks_native_and_training_before_call(self):
        class ForbiddenNative:
            kind='ISAAC_SIM';native_verified=True;control_signature=self.p['control_signature']
            def reset(self,*args):raise AssertionError('Native must never be called')
        with self.assertRaisesRegex(ValueError,'BASELINE_DYNAMICS_FAILED'):JointReachTask(self.p,ForbiddenNative())
        with self.assertRaisesRegex(ValueError,'Training blocked'):
            isaaclab_adapter.as_gym_environment(self.task(),self.p,training=True)
        edited=copy.deepcopy(self.p);edited['baseline']['accepted']=True
        edited.pop('profile_hash');edited['profile_hash']=profile.digest(edited)
        with self.assertRaises(ValueError):profile.validate(edited)

    def test_policy_package_checks_without_executing_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'policy.json';opaque=Path(folder)/'opaque.bin';opaque.write_bytes(b'not executable weights')
            m=policy_io.untrained_contract(self.p);prepare.write(path,m)
            with self.assertRaises(ValueError):policy_io.validate_weights_manifest(path,self.p)
            m.update(status='TRAINED_SIMULATION_ONLY',weights_path=opaque.name,weights_sha256=profile.sha(opaque))
            prepare.write(path,m);result=policy_io.validate_weights_manifest(path,self.p)
            self.assertFalse(result['weights_executed']);self.assertFalse(result['physical_authority'])
            for key,value in [('hardware_approved',True),('calibration_approved',True),('profile_hash','bad'),
                              ('weights_path','../opaque.bin'),('weights_sha256','bad'),('action_dim',7),('observation_dim',True)]:
                bad={**m,key:value};prepare.write(path,bad)
                with self.assertRaises((ValueError,FileNotFoundError)):policy_io.validate_weights_manifest(path,self.p)

    def test_reference_request_never_dispatches(self):
        request=policy_io.reference_request(self.p,[0]*6,[1]*6)
        self.assertEqual(request['device_dispatch'],'NOT_IMPLEMENTED_NOT_AUTHORIZED')
        self.assertFalse(request['hardware_approved']);self.assertEqual(len(request['samples']),241)

    def test_json_and_candidate_schema_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'x.json'
            for text in ('{"x":1,"x":2}','{"x":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):profile.read(path)
            root=Path(folder)/'root';clone(root);cfg=copy.deepcopy(self.cfg);cfg['ppo_candidate']['learning_epochs']=True
            prepare.write(root/prepare.SOURCE_DIR/'task_config.json',cfg)
            with self.assertRaises(ValueError):profile.configuration(root)

    def test_build_artifact_source_mutation_and_failed_start_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);clone(root);run=prepare.build(root)
            self.assertEqual(prepare.verify_run(run,root)['status'],'PREPARATION_ARTIFACTS_VERIFIED')
            self.assertEqual(profile.read(run/'training-readiness.json')['status'],'BLOCKED')
            file=run/'reference-program.csv';file.write_text(file.read_text()+'bad')
            m=profile.read(run/'manifest.json')
            with self.assertRaisesRegex(ValueError,'artifact changed'):prepare.verify_run(run,root)
            # Even resealing the artifact hash cannot change the original failed baseline profile.
            edited=profile.read(run/'profile.json');edited['baseline']['accepted']=True;prepare.write(run/'profile.json',edited)
            m['artifact_sha256']['profile.json']=profile.sha(run/'profile.json');m['artifact_sha256'][file.name]=profile.sha(file)
            prepare.write(run/'manifest.json',m)
            with self.assertRaisesRegex(ValueError,'Profile/config/source mismatch'):prepare.verify_run(run,root)
            (root/'outputs/isaac-contact-v1/delivery.json').unlink()
            with self.assertRaises(FileNotFoundError):prepare.build(root)
            current=profile.read(root/prepare.OUTPUT_DIR/'current.json')
            self.assertEqual(current['status'],'FAILED');self.assertNotEqual(current['run_id'],run.name)
            self.assertTrue((run/'manifest.json').is_file())

    def test_reference_program_time_and_limits(self):
        program=prepare.reference_program(self.p);rows=program['samples']
        self.assertEqual(program['status'],'REFERENCE_ONLY_NOT_EXECUTED')
        self.assertEqual(rows[0]['q'],[0]*6)
        for a,b in zip(rows,rows[1:]):self.assertAlmostEqual(b['t_s']-a['t_s'],1/120,places=10)
        for x in rows[-1]['q']:self.assertAlmostEqual(x,0,places=12)

    def test_resealed_readiness_and_source_edits_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);clone(root);run=prepare.build(root)
            path=run/'training-readiness.json';value=profile.read(path);value.update(status='READY_FOR_SIMULATION_TRAINING',ready=True,reasons=[])
            prepare.write(path,value);m=profile.read(run/'manifest.json');m['artifact_sha256'][path.name]=profile.sha(path);prepare.write(run/'manifest.json',m)
            with self.assertRaisesRegex(ValueError,'semantics changed'):prepare.verify_run(run,root)
            source=root/prepare.SOURCE_DIR/'task.py';source.write_text(source.read_text()+'\n# drift\n')
            with self.assertRaisesRegex(ValueError,'source changed'):prepare.verify_run(run,root)


if __name__=='__main__':unittest.main(verbosity=2)
