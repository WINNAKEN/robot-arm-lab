"""136 real producer, malformed-input and owned-clone publication controls."""
from pathlib import Path
from unittest import mock
import contextlib
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).absolute().parent))
import analyze as a

ROOT=Path(__file__).absolute().parents[3]
FIXTURE=ROOT/'outputs/mp18-mating-analysis-136/author'/('host-fixtures-'+uuid.uuid4().hex)
FIXTURE.mkdir(parents=True)
CODE=set(a._SOURCE_BYTES_136)

def clone_code(label):
    root=FIXTURE/label
    root.mkdir()
    for rel in CODE:
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
    return root

def authentic_clone(label):
    root=clone_code(label)
    names=set(json.loads((ROOT/'outputs/mp18-solid-compare-135/Root-compare-r1/input-manifest.json').read_text()))
    previous=json.loads((ROOT/(a.P135+'comparison.json')).read_text())
    names|={a.P135+'comparison.json',*(a.P135+p for p in previous['artifacts'])}
    names|={'outputs/mp18-solid-compare-135/Root-final-result.json','outputs/mp18-solid-compare-135/review/L4-r2/report.json',
            'outputs/mp18-solid-compare-135/review/L4-r2/publication.json',a.CAD_PARAMETERS,a.CAD_VERIFY,a.MOUNT_PARAMETERS,a.FIT_LEDGER,
            a.MODEL+'robot_arm.urdf',a.MODEL+'numeric-ledger.json'}
    for rel in names:
        p=root/rel
        if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
    return root

def cli(root,name):
    return subprocess.run([sys.executable,'-X','utf8','-I','-B','-u',str(root/'src/simulation/mp18_mating_analysis_136/analyze.py'),'--name',name],cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=150)

def junction(path,target):
    target.mkdir(parents=True,exist_ok=True)
    def ps(p):return "'"+str(p).replace("'","''")+"'"
    proc=subprocess.run(['powershell','-NoProfile','-Command','New-Item -ItemType Junction -Path '+ps(path)+' -Target '+ps(target)+' | Out-Null'],capture_output=True,text=True)
    if proc.returncode:raise RuntimeError('Owned native junction fixture failed: '+proc.stderr)

class ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base,cls.producer,cls.previous,cls.parameters,cls.verifier=a.inputs(ROOT)
        cls.parts,_=cls.base.partition_originals(cls.producer)
        cls.original=a.parse(cls.producer.raw[a.P135+'cases.json'])
        cls.selected=a.select_printed(cls.original)
        cls.joints,cls.geometry=a.k.parse_urdf(cls.producer.raw[a.MODEL+'robot_arm.urdf'],a.parse(cls.producer.raw[a.MODEL+'numeric-ledger.json']),cls.parameters)
        cls.picked,cls.coupling,cls.rows=a.motion_analysis(cls.producer.raw[a.MOTION],cls.joints,cls.geometry,{x['case']['step']for x in cls.selected})
        cls.cases=a.compare_variants(cls.base,cls.parts,cls.selected,cls.picked,cls.joints,cls.geometry)

    def test_actual8_reproduction_counterfactual_and_full_trace(self):
        self.assertEqual(len(self.cases),8);self.assertEqual(len(self.rows),11161)
        self.assertEqual(sum(self.coupling['by_phase'][p]['rows']for p in self.coupling['by_phase']),11161)
        for c in self.cases:
            self.assertAlmostEqual(c['variants']['actual_body_poses']['volume_mm3'],c['original135_volume_mm3'],places=6)
            self.assertFalse(c['hypotheses']['confirmed_physical_or_design_defect'])
            if c['part_a']!='TOOL_FLANGE':
                self.assertEqual(len(c['variants']),8)
                self.assertIn('FK_logged_actual_q',c['variants'])
                self.assertFalse(c['diagnostics']['counterfactual_is_simulated_new_runtime'])
        self.assertFalse(self.verifier['current_matches_generation'])
        self.assertTrue(self.verifier['mount_parameters_generation_pin_matches'])

    def test_selection_missing_duplicate_or_unexpected_printed_pair_fails(self):
        for mode in ['missing','duplicate','wrongpart']:
            cases=copy.deepcopy(self.original)
            case=next(c for c in cases if any(p['category']=='PRINTED_STL_MODEL_OVERLAP'for p in c['pairs']))
            pair=next(p for p in case['pairs']if p['category']=='PRINTED_STL_MODEL_OVERLAP')
            if mode=='missing':pair['category']='UNKNOWN'
            elif mode=='duplicate':case['pairs'].append(copy.deepcopy(pair))
            else:pair['part_a']='WRONG'
            with self.subTest(mode=mode),self.assertRaises(ValueError):a.select_printed(cases)

    def test_actual_motion_bad_joint_clock_owner_step_and_nonfinite_fails(self):
        first=a.parse(self.producer.raw[a.MOTION].splitlines()[0])
        for mode in ['joint','clock','owner','step','nonfinite']:
            row=copy.deepcopy(first)
            if mode=='joint':row['q'].pop('KG1_pinion')
            elif mode=='clock':row['clock']['lab_step']=7
            elif mode=='owner':row['body_poses'][0]['name']='UNEXPECTED'
            elif mode=='step':row['step']=1
            else:row['q']['KG1_pinion']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):a.motion_analysis((json.dumps(row)+'\n').encode(),self.joints,self.geometry,{0})

    def test_logged_q_is_not_replaced_with_targets(self):
        row=self.picked[6840]['row'];c=self.picked[6840]['coupling']
        self.assertGreater(abs(c['phase_A_rad']),.03)
        self.assertLess(abs(c['target_phase_A_rad']),1e-12)
        self.assertGreater(abs(row['q']['KG1_slide_A']-row['targets']['KG1_slide_A']),.0004)
        self.assertLess(abs(c['pinion_tracking_rad']),.00002)

    def test_input_hash_and_duplicate_json_fail_closed(self):
        with self.assertRaises(ValueError):a.parse(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError):self.producer.read(a.P135+'comparison.json','0'*64)
        with self.assertRaises(ValueError):self.producer.read('C:relative','0'*64)

    def test_actual_fresh_cli_full_path_publishes_last_and_matches_cases(self):
        root=authentic_clone('actual-normal')
        proc=cli(root,'normal-final')
        self.assertEqual(proc.returncode,0,proc.stderr)
        out=root/'outputs/mp18-mating-analysis-136/normal-final'
        result=json.loads((out/'analysis.json').read_text(encoding='utf-8'))
        self.assertEqual(result['selected_cases'],8);self.assertEqual(result['actual_motion_rows'],11161)
        self.assertTrue(result['selected_processing_complete'])
        cases=json.loads((out/'cases.json').read_text())
        self.assertEqual(cases,self.cases)
        self.assertGreaterEqual((out/'analysis.json').stat().st_mtime_ns,max((out/p).stat().st_mtime_ns for p in result['artifacts']))
        self.assertEqual(json.loads((out/'source-manifest.json').read_text()),a.source_manifest())
        (FIXTURE/'normal-cli.json').write_text(json.dumps({'exit':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'artifacts':result['artifacts']},indent=2))

class BoundaryTests(unittest.TestCase):
    def test_slug_exclusive_and_literal_authority(self):
        root=clone_code('normal-boundary')
        for name in ['../escape','x/y','x\\y','x:stream','.', '', 'x.', 'x ']:
            with self.subTest(name=name),self.assertRaises(ValueError):a.destination(root,name,True)
        out=a.destination(root,'safe',True)
        self.assertEqual(out,root/'outputs/mp18-mating-analysis-136/safe')
        with self.assertRaises(FileExistsError):a.destination(root,'safe',True)
        with mock.patch.object(a,'OUTPUT_ROOT',FIXTURE/'outside',create=True):self.assertEqual(a.destination(root,'second').parent,out.parent)

    @unittest.skipUnless(os.name=='nt','Windows native fixture')
    def test_real_cli_native_root_parent_leaf_repo_alias_reject(self):
        records=[]
        for mode in ['root','parent','leaf','repo-alias']:
            root=clone_code('native-'+mode);outside=FIXTURE/('outside-'+mode)
            if mode=='parent':
                # Preserve the authenticated dependency location under this owned alias.
                target=outside/Path(a.F135).relative_to('outputs');target.parent.mkdir(parents=True);shutil.copyfile(ROOT/a.F135,target)
                old=root/'outputs';archive=root/'bootstrap-outputs'
                self.assertTrue(old.absolute().is_relative_to(FIXTURE.absolute())and archive.absolute().is_relative_to(FIXTURE.absolute()))
                os.rename(old,archive)
                junction(root/'outputs',outside)
            elif mode=='repo-alias':
                alias=FIXTURE/'repo-alias';junction(alias,root);root=alias
            else:
                (root/'outputs').mkdir(exist_ok=True)
                if mode=='root':junction(root/'outputs/mp18-mating-analysis-136',outside)
                else:
                    (root/'outputs/mp18-mating-analysis-136').mkdir();junction(root/'outputs/mp18-mating-analysis-136/case',outside)
            proc=cli(root,'case')
            self.assertNotEqual(proc.returncode,0);self.assertIn('Native reparse/symlink',proc.stderr)
            self.assertFalse(any(outside.rglob('analysis.json')))
            records.append({'mode':mode,'exit':proc.returncode,'stderr':proc.stderr,'outside_completion_files':0})
        (FIXTURE/'native-boundaries.json').write_text(json.dumps(records,indent=2))

    def test_real_cli_early_source_four_timing_windows_fail(self):
        records=[]
        for mode in ['after-leaf','capture-kinematics','capture-analyze','initial-analyze']:
            root=authentic_clone('early-'+mode);entry=root/'src/simulation/mp18_mating_analysis_136/analyze.py'
            target=root/'src/simulation/mp18_mating_analysis_136'/('analyze.py'if mode.endswith('analyze')else'kinematics.py')
            original=target.read_bytes();name='early';out=root/'outputs/mp18-mating-analysis-136'/name
            command=[sys.executable,'-X','utf8','-I','-B','-u',str(entry),'--name',name]
            if mode!='after-leaf':
                shim=root/'timing-probe.py';shim.write_text('''import pathlib,runpy,sys
entry=pathlib.Path(sys.argv[1]);target=pathlib.Path(sys.argv[2]);mode=sys.argv[3];original=target.read_bytes();seen=0
def mutate():
 return original.replace(b'from __future__ import annotations\\n',b'from __future__ import annotations\\nraise RuntimeError("INJECTED_IF_FRESH_BYTES_EXECUTE")\\n',1)
def audit(event,args):
 global seen
 if event=='compile' and pathlib.Path(str(args[1]))==entry:
  seen+=1
  if seen==(1 if mode=='initial-analyze'else 2):target.write_bytes(mutate())
sys.addaudithook(audit);sys.argv=[str(entry),'--name','early'];runpy.run_path(str(entry),run_name='__main__')
''',encoding='utf-8')
                command=[sys.executable,'-X','utf8','-I','-B','-u',str(shim),str(entry),str(target),mode]
            start=time.monotonic();log=root/'cli.log'
            with log.open('w',encoding='utf-8')as f:
                proc=subprocess.Popen(command,cwd=root,stdout=f,stderr=subprocess.STDOUT)
                if mode=='after-leaf':
                    while not out.exists()and proc.poll()is None and time.monotonic()-start<20:time.sleep(.001)
                    self.assertTrue(out.is_dir());target.write_bytes(original+b'\nraise RuntimeError("INJECTED_IF_FRESH_BYTES_EXECUTE")\n')
                code=proc.wait(timeout=150)
            text=log.read_text(encoding='utf-8');self.assertNotEqual(code,0);self.assertFalse((out/'analysis.json').exists())
            if mode=='initial-analyze':self.assertIn('RuntimeError: INJECTED_IF_FRESH_BYTES_EXECUTE',text)
            else:
                self.assertIn('Captured source drift:',text);self.assertNotIn('RuntimeError: INJECTED_IF_FRESH_BYTES_EXECUTE',text)
            records.append({'mode':mode,'exit':code,'completion':False,'before_sha256':a.digest(original),'after_sha256':a.digest(target.read_bytes()),'log':str(log.relative_to(FIXTURE))})
        (FIXTURE/'source-timing.json').write_text(json.dumps(records,indent=2))

class PublicationTests(unittest.TestCase):
    def small_run(self,label,callback=None,late_source=False,fail_filename=None):
        root=clone_code('publish-'+label);sentinel=root/'sentinel';sentinel.write_bytes(b'original input')
        base=a.dependency135(ROOT)
        class Producer:
            def __init__(self):
                self.root=root;self.manifest={'sentinel':{'sha256':a.digest(sentinel.read_bytes()),'bytes':sentinel.stat().st_size}}
                self.raw={a.MODEL+'numeric-ledger.json':(ROOT/(a.MODEL+'numeric-ledger.json')).read_bytes(),
                    a.MODEL+'robot_arm.urdf':(ROOT/(a.MODEL+'robot_arm.urdf')).read_bytes(),a.P135+'cases.json':b'[]',a.MOTION:b''}
            recheck=base.Producer.recheck
        producer=Producer();params=json.loads((ROOT/a.CAD_PARAMETERS).read_text())
        real_open=Path.open
        @contextlib.contextmanager
        def opening(path,mode='r',*args,**kwargs):
            if mode=='xb'and path.name==fail_filename:raise OSError('Injected artifact write failure')
            with real_open(path,mode,*args,**kwargs)as stream:yield stream
            if late_source and mode=='xb'and path.name=='cause-report.md':
                q=root/'src/simulation/mp18_mating_analysis_136/kinematics.py';q.write_bytes(q.read_bytes()+b'\n# late drift\n')
        with mock.patch.object(a,'inputs',return_value=(base,producer,{},params,{})),mock.patch.object(base,'partition_originals',return_value=({},[])),\
             mock.patch.object(a,'select_printed',return_value=[{'case':{'step':0}}]),\
             mock.patch.object(a,'motion_analysis',return_value=({}, {'rows':11161}, [])),\
             mock.patch.object(a,'compare_variants',return_value=[{'part_a':'A','part_b':'B'}]*8),\
             mock.patch.object(a,'render_report',return_value='report'),mock.patch.object(Path,'open',opening):
            a.run(label,root=root,before_publish=callback)
        return root

    def test_publication_input_or_source_mutation_rejected(self):
        for mode in ['input','source']:
            reached=[]
            def change(producer,out):
                reached.append(True)
                target=producer.root/('sentinel'if mode=='input'else'src/simulation/mp18_mating_analysis_136/kinematics.py')
                target.write_bytes(target.read_bytes()+b' drift')
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'Input changed before publication|Captured source drift:'):self.small_run(mode,change)
            self.assertEqual(reached,[True])
            self.assertFalse((FIXTURE/('publish-'+mode)/'outputs/mp18-mating-analysis-136'/mode/'analysis.json').exists())

    def test_late_source_change_and_write_failure_no_completion(self):
        for mode in ['late','write']:
            with self.subTest(mode=mode),self.assertRaisesRegex((ValueError,OSError),'Captured source drift:|Injected artifact write failure'):
                self.small_run(mode,late_source=mode=='late',fail_filename='cause-report.md'if mode=='write'else None)
            self.assertFalse((FIXTURE/('publish-'+mode)/'outputs/mp18-mating-analysis-136'/mode/'analysis.json').exists())

    @unittest.skipUnless(os.name=='nt','Windows native fixture')
    def test_late_native_transition_after_compute_rejected(self):
        reached=[]
        def change(producer,out):
            reached.append(True)
            allowed=out.parent;archive=allowed.with_name('archived-computed')
            self.assertTrue(allowed.absolute().is_relative_to(FIXTURE.absolute())and archive.absolute().is_relative_to(FIXTURE.absolute()))
            os.rename(allowed,archive)
            junction(allowed,producer.root/'outside')
        with self.assertRaisesRegex(ValueError,'Native reparse/symlink'):self.small_run('late-junction',change)
        self.assertEqual(reached,[True])
        root=FIXTURE/'publish-late-junction';self.assertFalse(any((root/'outside').rglob('analysis.json')))

if __name__=='__main__':unittest.main(verbosity=2)
