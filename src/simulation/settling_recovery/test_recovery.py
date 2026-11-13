"""Host regression and negative controls; never launches SSH/Isaac/hardware."""
import copy
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
try:from . import verify as V
except ImportError:import verify as V
C,R,ROOT=V.C,V.R,V.ROOT


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=V.read_json(ROOT/'outputs/isaac-contact-v1/delivery.json')
        cls.original=ROOT/'outputs/isaac-contact-v1/runs'/d['run_id']/'retrieved'/d['run_id']
        cls.static=V.read_json(cls.original/'static.json')
        cls.rows=[V.parse(line) for line in (cls.original/'samples.ndjson').read_text().splitlines()]
        cls.ref,cls.reference,cls.frames,cls.layout,cls.core,cls.program=V.context(ROOT)

    def test_fixed_gain_variants_preserve_torque_cap(self):
        s={**self.static,'control_variant':'solver'};a=C.gains(s);b=C.gains({**s,'control_variant':'solver_pd'})
        self.assertEqual(a['effort'],[3,6,5,2,2,1]);self.assertEqual(a['effort'],b['effort'])
        self.assertEqual(b['kp'],[4*x for x in a['kp']]);self.assertEqual(b['kd'],[2*x for x in a['kd']])
        with self.assertRaises(ValueError):C.gains({**s,'control_variant':'unreviewed'})

    def test_solver_metadata_and_gain_negative_controls(self):
        s=copy.deepcopy(self.static);s.update(control_variant='solver',solver={'position_iterations':64,'velocity_iterations':16})
        V.validate_static(s,self.ref,self.reference,self.core,ROOT)
        for key,value in [('position_iterations',4),('velocity_iterations',True)]:
            wrong=copy.deepcopy(s);wrong['solver'][key]=value
            with self.assertRaises(ValueError):V.validate_static(wrong,self.ref,self.reference,self.core,ROOT)
        wrong=copy.deepcopy(s);wrong['actual_drives']['effort'][1]=60
        with self.assertRaises(ValueError):V.validate_static(wrong,self.ref,self.reference,self.core,ROOT)

    def test_old_failed_tracking_still_scans_all_6781_frames(self):
        result=V.compare_samples(self.static,iter(self.rows),self.program,self.frames,self.layout,self.core)
        self.assertEqual(result['full_frame_samples'],6781);self.assertEqual(result['checkpoints_passed'],0)
        self.assertEqual(len(result['tracking_failures']),28)

    def test_late_frame_corruption_is_seen_after_first_tracking_failure(self):
        rows=list(self.rows);rows[-1]=copy.deepcopy(rows[-1]);rows[-1]['links'][0]['position'][0]+=.01
        with self.assertRaisesRegex(ValueError,'LINK frame'):
            V.compare_samples(self.static,iter(rows),self.program,self.frames,self.layout,self.core)

    def test_contacts_and_unchanged_recipe(self):
        result=V.audit_contacts(self.static,self.rows)
        self.assertEqual(result['dynamic_failures'],[])
        self.assertEqual(C.total_time(self.program),56.5)
        self.assertEqual(len(C.segments(self.program)),28)
        self.assertEqual(V.ANGLE_TOL,V.math.radians(.5));self.assertEqual(V.SPEED_TOL,V.math.radians(1))

    def test_preimport_helper_pin_detects_real_file_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pins=C.approved_dependencies()
            for name in [*pins['dependencies_sha256'],'src/simulation/settling_recovery/pins.json']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
            C.approved_dependencies(root)
            with (root/'src/joint_frames/frames.py').open('a') as f:f.write('\n# drift\n')
            with self.assertRaisesRegex(ValueError,'before import'):C.approved_dependencies(root)

    def test_write_once_preparation_binds_actual_variant_and_missing_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pins=C.approved_dependencies()
            for name in set(R.SOURCE_PATHS.values())|set(pins['dependencies_sha256']):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):R.prepare(root,'solver')
            prepared=json.loads(stream.getvalue());run=Path(prepared['local_run_dir']);job=V.read_json(run/'job.json')
            self.assertEqual(job['control_variant'],'solver');self.assertEqual(prepared['files_sha256'],job['files_sha256'])
            self.assertEqual(V.sha(run/'bundle.zip'),prepared['bundle_sha256'])
            with self.assertRaises(ValueError):R.prepare(root,'unreviewed')
            (root/R.SOURCE_PATHS['input.usda']).unlink()
            with self.assertRaises(FileNotFoundError):R.prepare(root,'solver')
            self.assertEqual(V.sha(run/'bundle.zip'),prepared['bundle_sha256'])

    def test_retry_guard_rejects_contact_only_incomplete_or_successful_results(self):
        with tempfile.TemporaryDirectory() as folder:
            script=Path(folder)/'control.ps1';data=Path(folder)/'prior.json'
            script.write_text("""param($source,$data,$variant)
$tokens=$null;$errors=$null
$tree=[System.Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
$node=$tree.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Assert-SecondAttemptEligible'},$true)
if($null -eq $node) { throw 'Missing actual eligibility function' }
Invoke-Expression $node.Extent.Text
$prior=Get-Content -LiteralPath $data -Raw | ConvertFrom-Json
Assert-SecondAttemptEligible $prior $variant
""",encoding='utf-8')
            base={'status':'DYNAMICS_FAILED','evidence_valid':True,'full_frame_samples':6781,'checkpoints_passed':27,
                  'tracking_failures':['initial_zero'],'dynamic_failures':[]}
            variants=[(base,'solver_pd',0),({**base,'tracking_failures':[],'checkpoints_passed':28,
                'dynamic_failures':['CONTACT_ENGINE_POSITIVE_CONTROL_FAILED']},'solver_pd',1),
                ({**base,'full_frame_samples':2},'solver_pd',1),({**base,'evidence_valid':False},'solver_pd',1),
                ({**base,'dynamic_failures':['GRAVITY_FEEDFORWARD_SATURATED']},'solver_pd',1),
                ({**base,'status':'GRAVITY_COLLISION_MOTION_PASS'},'solver_pd',1),(None,'solver_pd',1),(None,'solver',1),
                ({**base,'tracking_failures':None},'solver_pd',1),({**base,'checkpoints_passed':True},'solver_pd',1)]
            for prior,variant,expected in variants:
                data.write_text(json.dumps(prior),encoding='utf-8')
                done=subprocess.run(['pwsh','-NoProfile','-File',str(script),str(Path(__file__).with_name('driver.ps1')),str(data),variant],capture_output=True,timeout=15)
                self.assertEqual(done.returncode,expected,done.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
