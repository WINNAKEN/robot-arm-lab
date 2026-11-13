"""137 producer, actual generated native dispatch and publication boundary controls."""
from pathlib import Path
import copy,hashlib,json,os,subprocess,sys,types,unittest,uuid
ROOT=Path(__file__).absolute().parents[3];HERE=Path(__file__).absolute().parent
P=types.ModuleType('prepare137_test');P.__file__=str(HERE/'prepare.py');exec(compile((HERE/'prepare.py').read_bytes(),P.__file__,'exec'),P.__dict__)
FIXTURE=ROOT/'outputs/mp18-pinion-feedback-137/author'/('host-fixtures-'+uuid.uuid4().hex);FIXTURE.mkdir(parents=True)

def clone(tag):
    root=FIXTURE/tag;root.mkdir();names=set(P._BYTES137)|set(INPUTS.raw)
    for name in names:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(P._BYTES137.get(name,INPUTS.raw.get(name)))
    return root
def junction(path,target):
    target.mkdir(parents=True,exist_ok=True);path.parent.mkdir(parents=True,exist_ok=True)
    command="New-Item -ItemType Junction -Path '"+str(path).replace("'","''")+"' -Target '"+str(target).replace("'","''")+"' | Out-Null"
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:raise RuntimeError('Native fixture junction failed:'+p.stderr.decode(errors='replace'))
def cli(root,name):return subprocess.run([sys.executable,'-X','utf8','-I','-B','-u',str(root/'src/simulation/mp18_pinion_feedback_137/prepare.py'),'--name',name],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)

INPUTS=P.Inputs(ROOT);VALUES=P.kit_values(INPUTS);KIT=FIXTURE/'kit'
for name,raw in VALUES.items():P.write_exclusive(KIT/name,raw)
MANIFEST={n:P.pin(b)for n,b in VALUES.items()}

class RuntimeTests(unittest.TestCase):
    def test_real_11160_native_commands_old_bug_and_original_observations(self):
        result,receipts,records,effective=P.replay(KIT,MANIFEST,INPUTS.rows)
        old,_,oldrecords,_=P.replay(KIT,MANIFEST,INPUTS.rows,restore_old=True)
        self.assertEqual(result['command_count'],11160);self.assertEqual(result['setter_calls'],44640);self.assertEqual(len(receipts),11160)
        self.assertLess(result['peak_position_reference_coupling_error']['abs_error_rad'],1e-7)
        self.assertGreater(old['peak_position_reference_coupling_error']['abs_error_rad'],.03)
        self.assertFalse(result['new_runtime_accepted']);self.assertTrue(old['exact_old_dispatch_restored'])
        (FIXTURE/'native-full-replay-result.json').write_bytes(P.encode({'corrected':result,'exact_old':old}))
    def test_permutation_reaches_actual_arrays_and_journal(self):
        seen=[];r,_,_,_=P.replay(KIT,MANIFEST,INPUTS.rows,names=list(reversed(P.F.NAMES)),steps_limit=2,callback=lambda row,p,v:seen.append((row['step'],p,v)))
        self.assertEqual(r['command_count'],2);self.assertEqual(len(seen),2)
    def test_bad_state_fails_before_any_command_setter(self):
        # The actual generated loop reaches reference validation before robot dispatch.
        original=P.HostRobot;created=[]
        def robot(*a,**k):v=original(*a,**k);created.append(v);return v
        P.HostRobot=robot
        try:
            for mode in ['nan','stale','clock_after','limit']:
                def mutate(s,i):
                    if i==0:
                        if mode=='nan':s['q'][P.F.LEADER]=float('nan')
                        elif mode=='stale':s['clock']['lab_step']=-1
                        elif mode=='clock_after':s['clock_after']['engine_time_s']=1.
                        else:s['qd'][P.F.LEADER]=.1
                with self.subTest(mode=mode),self.assertRaises(ValueError):P.replay(KIT,MANIFEST,INPUTS.rows,mutate_current=mutate,steps_limit=1)
                self.assertEqual(created[-1].calls,[])
        finally:P.HostRobot=original
    def test_readback_corruption_stops_before_simulation_step(self):
        seen=[]
        with self.assertRaises(ValueError):P.replay(KIT,MANIFEST,INPUTS.rows,poison=True,steps_limit=1,callback=lambda *a:seen.append(a))
        self.assertEqual(seen,[])
    def test_clock_changes_at_actual_dispatch_before_any_setter(self):
        original=P.HostRobot;created=[]
        def robot(*a,**k):v=original(*a,**k);created.append(v);return v
        P.HostRobot=robot
        try:
            with self.assertRaises(ValueError):P.replay(KIT,MANIFEST,INPUTS.rows,clock_advance_on_dispatch=True,steps_limit=1)
            self.assertEqual(created[-1].calls,[])
        finally:P.HostRobot=original
    def test_source_anchors_and_kit_mutation_rejected(self):
        _,_,n=P.load_kit(KIT,MANIFEST)
        with self.assertRaises(ValueError):P.F.derive_effective(n._text)
        copied=FIXTURE/'bad-kit'
        for name,raw in VALUES.items():P.write_exclusive(copied/name,raw)
        with(copied/'source/feedback137.py').open('ab')as f:f.write(b'\nraise RuntimeError("changed")\n')
        with self.assertRaises(ValueError):P.load_kit(copied,MANIFEST)
    def test_kit_contains_no_authority_or_transport(self):
        for name in VALUES:self.assertFalse(any(t in name.lower()for t in ['approval','job.json','lease','runner','driver','proxy','bootstrap']))

class BoundaryTests(unittest.TestCase):
    def test_own_source_four_real_cli_timing_controls(self):
        results=[]
        for mode in ['after-leaf-feedback','initial-exec-prepare','capture-compile-prepare','capture-compile-feedback']:
            root=clone('source-'+mode);source=root/'src/simulation/mp18_pinion_feedback_137/prepare.py'
            if mode=='after-leaf-feedback':
                proc=subprocess.Popen([sys.executable,'-X','utf8','-I','-B','-u',str(source),'--name','case'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                import time
                deadline=time.monotonic()+30
                while not(root/'outputs/mp18-pinion-feedback-137/case').exists()and proc.poll()is None and time.monotonic()<deadline:time.sleep(.005)
                self.assertTrue((root/'outputs/mp18-pinion-feedback-137/case').exists(),'Reached actual output-leaf window')
                target=source.with_name('feedback.py');target.write_bytes(target.read_bytes()+b'\nraise RuntimeError("CHANGED_AFTER_CAPTURE")\n')
                out,err=proc.communicate(timeout=180);code=proc.returncode
            else:
                harness=root/'audit-timing.py'
                harness.write_text('''import sys,runpy\nfrom pathlib import Path\np=Path(sys.argv[1]);mode=sys.argv[2];seen=0;done=False\ndef audit(event,args):\n global seen,done\n if done:return\n hit=False\n if mode=='initial-exec-prepare' and event=='exec' and args[0].co_filename==str(p):hit=True\n if event=='compile' and str(args[1])==str(p):\n  seen+=1\n  if mode=='capture-compile-prepare' and seen==2:hit=True\n if event=='compile' and str(args[1])==str(p.with_name('feedback.py')) and mode=='capture-compile-feedback':hit=True\n if hit:\n  done=True;t=p.with_name('feedback.py')if mode=='capture-compile-feedback'else p\n  raw=t.read_bytes();anchor=b'from __future__ import annotations\\n';assert raw.count(anchor)==1\n  t.write_bytes(raw.replace(anchor,anchor+b'raise RuntimeError("CHANGED_SOURCE_TIMING")\\n',1))\nsys.addaudithook(audit);sys.argv=[str(p),'--name','case'];runpy.run_path(str(p),run_name='__main__')\n''',encoding='utf-8')
                proc=subprocess.run([sys.executable,'-X','utf8','-I','-B','-u',str(harness),str(source),mode],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180);out,err,code=proc.stdout,proc.stderr,proc.returncode
            self.assertNotEqual(code,0,mode);self.assertFalse((root/'outputs/mp18-pinion-feedback-137/case/preparation.json').exists(),mode)
            self.assertNotIn(b'RuntimeError: CHANGED_SOURCE_TIMING',err,mode)
            self.assertNotIn(b'RuntimeError: CHANGED_AFTER_CAPTURE',err,mode)
            results.append({'mode':mode,'exit':code,'completion_exists':False,'stderr':err.decode('utf-8',errors='replace')})
        (FIXTURE/'source-timing-results.json').write_bytes(P.encode(results))
    def test_slug_alias_and_exclusive_leaf(self):
        root=clone('slug')
        for slug in ['../escape','x/y','x\\y','x:stream','x.','', '.', '/tmp']:
            with self.subTest(slug=slug),self.assertRaises(ValueError):P.destination(root,slug,True)
        P.destination(root,'fresh',True)
        with self.assertRaises(FileExistsError):P.destination(root,'fresh',True)
    @unittest.skipUnless(os.name=='nt','Native Windows junction control')
    def test_real_cli_root_parent_leaf_and_repo_reparse(self):
        observed=[]
        for mode in ['root','parent','leaf','repo']:
            root=clone('native-'+mode);outside=FIXTURE/('outside-'+mode)
            if mode=='parent':
                original=root/'outputs';saved=root/'saved-outputs';original.rename(saved);junction(original,saved)
            elif mode=='repo':
                alias=FIXTURE/'repo-alias';junction(alias,root);root=alias
            else:
                parent=root/'outputs/mp18-pinion-feedback-137';parent.mkdir(parents=True,exist_ok=True)
                if mode=='root':parent.rmdir();junction(parent,outside)
                else:junction(parent/'case',outside)
            p=cli(root,'case');self.assertNotEqual(p.returncode,0);self.assertIn(b'Native reparse/symlink',p.stderr)
            observed.append({'mode':mode,'exit':p.returncode,'stderr':p.stderr.decode('utf-8',errors='replace')})
        (FIXTURE/'native-boundary-results.json').write_bytes(P.encode(observed))
    def test_full_actual_cli_and_last_completion_publication(self):
        root=clone('actual-cli');p=cli(root,'case');self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'))
        out=root/'outputs/mp18-pinion-feedback-137/case';d=P.parse((out/'preparation.json').read_bytes());self.assertTrue(d['prepared_complete']);self.assertEqual(d['command_count'],11160)
        self.assertGreaterEqual((out/'preparation.json').stat().st_mtime_ns,max(f.stat().st_mtime_ns for f in out.rglob('*')if f.is_file()and f.name!='preparation.json'))
        (FIXTURE/'actual-cli-result.json').write_bytes(P.encode({'exit':p.returncode,'summary':d,'output':out.relative_to(ROOT).as_posix()}))
    def test_input_source_kit_change_after_compute_prevents_completion(self):
        for mode in ['input','source','kit']:
            root=clone('late-'+mode)
            def mutate(inputs,out,kit,manifest):
                path=root/P.MOTION if mode=='input'else root/'src/simulation/mp18_pinion_feedback_137/feedback.py'if mode=='source'else kit/'source/feedback137.py'
                with path.open('ab')as f:f.write(b'\n')
            with self.subTest(mode=mode),self.assertRaises(ValueError):P.run('case',root=root,before_publish=mutate)
            self.assertFalse((root/'outputs/mp18-pinion-feedback-137/case/preparation.json').exists())

if __name__=='__main__':unittest.main(verbosity=2)
