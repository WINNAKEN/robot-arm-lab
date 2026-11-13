"""HOST attacks on new task authority, lifecycle, archive and immutable builders."""
import copy
import ast
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
import zipfile
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def load():
    m=types.ModuleType('runner133_HOST');m.__file__=str(HERE/'runner.py');exec(compile((HERE/'runner.py').read_bytes(),m.__file__,'exec'),m.__dict__);return m


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.R=load()

    def test_01_typed_review_false_values_and_hash_substitution(self):
        r={'unit':133,'phase':'L4','verdict':'PASS','non_author':True,'required':8,'met':8,'unmet':0,'unresolved_count':0,'all_required_met':True,'source_freeze_sha256':'a'*64}
        self.R.review_gate(self.R.encode(r),'a'*64,133)
        for key,value in [('verdict','BLOCK'),('non_author',1),('all_required_met',1),('source_freeze_sha256','b'*64),('unmet',1),('unresolved_count',1),('phase','L2')]:
            bad=dict(r);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.R.review_gate(self.R.encode(bad),'a'*64,133)

    def lifecycle_fixture(self):
        R=self.R;record={'run_id':'a'*32,'job_sha256':'b'*64};job={'run_id':record['run_id']}
        p={'child_pid':42,'child_creation_time':134385467972140495,'actual_child_exit_code':0,'policy_exit_code':0,'errors':[],
           'raw_complete':True,'terminal':True,'child_state':'REAPED','job_active_after':0,'timed_out':False,'parent_pid':7,**record}
        owner={'parent_pid':7,**record};report={'watchdog':{'parent_pid':42,'parent_birth':p['child_creation_time']}}
        values={'process.json':R.encode(p),'owner.json':R.encode(owner),'report.json':R.encode(report),'stdout.txt':b'','stderr.txt':b''}
        t={**record,'pid':42,'parent_pid':7,'purpose':'physics_pick_place_133','status':'COMPLETE_PRE_CLOSE','phase':'CLOSING_APP','code':0,
           'hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN','files_sha256':{n:R.digest(v) for n,v in values.items() if n not in {'process.json','stdout.txt','stderr.txt'}}}
        values['terminal.json']=values['status.json']=R.encode(t)
        values['recovery-seal.json']=R.encode({'unit':119,**record,'actual_child_pid':42,'files_sha256':{n:R.digest(v) for n,v in values.items()}})
        return values,job,record

    def test_02_exact_PRE_CLOSE_and_CLOSED_success(self):
        v,j,r=self.lifecycle_fixture();self.R.lifecycle(v,j,r)
        t=self.R.parse(v['terminal.json']);t.update(status='CLOSED',phase='APP_CLOSED');v['terminal.json']=v['status.json']=self.R.encode(t)
        self.R.lifecycle(v,j,r)

    def test_03_bad_lifecycle_process_status_birth_and_seal(self):
        for mutant in ('timeout','nonzero','not_reaped','status','birth','extra','pid','phase','code','bool_code','parent','errors'):
            v,j,r=self.lifecycle_fixture();p=self.R.parse(v['process.json']);t=self.R.parse(v['terminal.json'])
            if mutant=='timeout':p['timed_out']=True
            elif mutant=='nonzero':p['actual_child_exit_code']=1
            elif mutant=='not_reaped':p['child_state']='RUNNING'
            elif mutant=='status':v['status.json']=b'{}'
            elif mutant=='birth':p['child_creation_time']+=1
            elif mutant=='extra':t['files_sha256']['not-sealed.json']='f'*64
            elif mutant=='pid':t['pid']=43
            elif mutant=='phase':t['phase']='APP_CLOSED'
            elif mutant=='code':t['code']=1
            elif mutant=='bool_code':t['code']=False
            elif mutant=='parent':p['parent_pid']=8
            elif mutant=='errors':p['errors']=['unreaped']
            v['process.json']=self.R.encode(p)
            if mutant!='status':v['status.json']=v['terminal.json']=self.R.encode(t)
            with self.subTest(mutant=mutant),self.assertRaises((ValueError,KeyError)):self.R.lifecycle(v,j,r)

    def test_04_json_duplicate_nonfinite_windows_path_attacks(self):
        for data in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):self.R.parse(data)
        for path in ('../escape','/root','A\\B','x:ads','CON','x/../y','x.','x/COM3.txt','x\n'):
            with self.subTest(path=path),self.assertRaises(ValueError):self.R._zip_name(path)
        self.assertEqual(self.R._zip_name('frames/frame-0000.png'),'frames/frame-0000.png')

    def test_05_wire_complete_actual_sha_and_identity(self):
        R=self.R;record={k:('a'*32 if k in ('run_id','nonce') else 4 if k=='bundle_bytes' else 'b'*64) for k in ('run_id','nonce','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
        archive=b'zip payload actual bytes';ready=dict(record,kind='READY',remote_ready=1.)
        result={'kind':'RESULT','run_id':record['run_id'],'nonce':record['nonce'],'bytes':len(archive),'sha256':R.digest(archive)}
        wire=R.encode(ready)+R.encode(result)+archive
        self.assertEqual(R.unpack_result(wire,record)[0],archive)
        for bad in (wire[:-1],wire+b'x',wire.replace(b'RESULT',b'WRONG!'),wire.replace(b'zip payload',b'bad payload')):
            with self.assertRaises(ValueError):R.unpack_result(bad,record)

    def test_06_archive_duplicate_traversal_and_crc(self):
        R=self.R
        for names in (['x','X'],['../escape'],['x:ads'],['CON']):
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w') as z:
                for n in names:z.writestr(n,b'x')
            with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
                with self.assertRaises((ValueError,KeyError)):R.extract_archive(buffer.getvalue(),Path(tmp)/'new')
        v,_,_=self.lifecycle_fixture();buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            for n,b in v.items():z.writestr(n,b)
        with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
            dest=Path(tmp)/'new';actual,_=R.extract_archive(buffer.getvalue(),dest);self.assertEqual(actual,v)
            with self.assertRaises(ValueError):R.extract_archive(buffer.getvalue(),dest)

    def test_07_actual_native_and_driver_derivation_no_SDK_import(self):
        base=(ROOT/'src/simulation/mp18_isaac_130/driver.py').read_bytes()
        raw=(HERE/'driver.py').read_text().replace("_base133=(_here133/'base_driver.py').read_bytes()",'_base133='+repr(base))
        old=(ROOT/'src/simulation/mp18_isaac_130/contract.py').read_bytes()
        # Base loader is pinned; replace only the read in the test fixture, not production code.
        raw=raw.replace('exec(compile(_text133,str(_here133/\'base_driver.py\')+\'#133\',\'exec\'),globals())',"_text133=_text133.replace(\"value = (HERE/'base_contract.py').read_bytes()\",'value = '+repr("+repr(old)+"))\nexec(compile(_text133,str(_here133/'base_driver.py')+'#133','exec'),globals())")
        D=types.ModuleType('driver133_HOST');D.__file__=str(HERE/'driver.py');exec(compile(raw,D.__file__,'exec'),D.__dict__)
        self.assertIn('133/runs',D._text133);self.assertNotIn('isaacsim',D.__dict__)

    def test_08_bootstrap_raw_proxy_limits_and_exact_namespace(self):
        R=self.R;cfg=json.loads((HERE/'config.json').read_text());files={}
        for key in ('base_driver','base_contract','proxy120','proxy'):files[cfg['dependency_paths'][key]]=(ROOT/cfg['dependency_paths'][key]).read_bytes()
        files[HERE.relative_to(ROOT).as_posix()+'/driver.py']=(HERE/'driver.py').read_bytes()
        snapshot={'cfg':cfg,'files':files};code=R._remote_driver(snapshot)
        self.assertIn("endswith('/robot-arm-lab/133/runs')",code)
        bootstrap=types.ModuleType('bootstrap133_HOST');exec(compile(code,'<actual133-bootstrap>','exec'),bootstrap.__dict__)
        for invalid in (b'{"GO":1,"GO":2}',b'{"GO":NaN}'):
            with self.assertRaises(ValueError):bootstrap.parse(invalid)
        self.assertEqual(bootstrap.parse(b'{"kind":"GO"}'),{'kind':'GO'})
        self.assertEqual(bootstrap.lease_end(100,2700),2780)
        with self.assertRaises(ValueError):bootstrap.lease_end(100,382)
        command=R.proxy_command(snapshot,"print('HOST_ONLY')",2700)
        self.assertLess(len(command),30000);self.assertIn('FromBase64String',command)

    def test_09_no_source_hash_per_archive_member(self):
        # Count the real current() caller seam while actual ZIP values are extracted.
        R=self.R;v,_,_=self.lifecycle_fixture();buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            for n,b in v.items():z.writestr(n,b)
        original=R.current;calls=[];R.current=lambda *a:calls.append(a)
        try:
            with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:R.extract_archive(buffer.getvalue(),Path(tmp)/'batch')
        finally:R.current=original
        self.assertEqual(calls,[])

    def test_10_two_attempt_bounds(self):
        for n in (0,6,True,-1):
            with self.assertRaises(ValueError):self.R.attempt_path(n)
        self.assertEqual(self.R.attempt_path(2).name,'02')

    def test_11_actual_full_payload_context_without_SDK(self):
        R=self.R;cfg=json.loads((HERE/'config.json').read_text());deps=cfg['dependency_paths'];files={}
        for p in [*HERE.glob('*.py'),HERE/'config.json',HERE/'jaw_components.json']:
            files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
        needed=set(deps.values())-{deps['freeze133'],deps['review133']}
        needed|={cfg['model_dir']+'/'+n for n in cfg['model_pins']}
        needed|={p['path'] for p in cfg['refs'].values()}
        for path in needed:
            if (ROOT/path).is_file():files[path]=(ROOT/path).read_bytes()
        values=R.payload_inputs({'cfg':cfg,'files':files})
        with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
            run=Path(tmp)/('f'*32);run.mkdir()
            for name,raw in values.items():
                p=run/'input'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            job={'unit':119,'task_unit':133,'purpose':'physics_pick_place_133','current_user_approval_sha256':'5a2f2e4656fdb0d9b9ed4d082751a3d001ea2d9059f509bd14def3b0355611fc','run_id':run.name,'nonce':'e'*32,'hardware_approved':False,'inputs':{n:R.digest(b) for n,b in values.items()}}
            jobraw=R.encode(job);(run/'job.json').write_bytes(jobraw)
            D=R.load('driver133_full_HOST',values['source/driver.py'],run/'input/source/driver.py')
            with self.assertRaises(ValueError):D._context(run,'0'*64)
            ctx=D._context(run,R.digest(jobraw))
            self.assertEqual(ctx.scenario['duration_s'],85)
            self.assertEqual(ctx.contract.target_at(ctx.cfg['program'],'large',54)['phase'],'home_settle')
            self.assertEqual(ctx.cfg['effective_caps']['J2'],12)
            N=R.load('native133_full_HOST',values['source/native.py'],run/'input/source/native.py')
            self.assertTrue(callable(N._native));self.assertNotIn('isaacsim',N.__dict__)

    def test_12_original_SDK_postcheck_on_immutable130_records_HOST_only(self):
        R=self.R;cfg=json.loads((ROOT/'src/simulation/mp18_isaac_130/config.json').read_text())
        run=ROOT/'outputs/mp18-profile-repair-130/runs/dee4f7e320ea464aabd34bc41740efe1'
        terminal=R.parse((run/'retrieved/terminal.json').read_bytes())
        ctx=types.SimpleNamespace(cfg=cfg,job={'run_id':terminal['run_id']},job_hash=terminal['job_sha256'],run=run,
            data={'ref/'+n:(ROOT/p['path']).read_bytes() for n,p in cfg['refs'].items()})
        stub=types.ModuleType('driver');stub.need=R.need;stub.read=lambda p:R.parse(Path(p).read_bytes())
        stub.write=lambda *a:R.need(False,'HOST postcheck writes0');stub.sha=lambda p:R.digest(Path(p).read_bytes());stub.load_module=R.load
        previous=sys.modules.get('driver');sys.modules['driver']=stub
        try:
            sdk=R.load('sdk133_originalpost_HOST',ctx.data['ref/sdk.py'],ROOT/cfg['refs']['sdk.py']['path'])
            result=sdk.verify_records(ctx,run/'retrieved',terminal)
        finally:
            if previous is None:del sys.modules['driver']
            else:sys.modules['driver']=previous
        self.assertEqual(result,{'provider':'OBSERVED_AND_RECHECKED','numeric':'SDK_PINNED_BEFORE_AFTER','binding':'SAME_MODULES','cuda':'ACTUAL_GPU_SUM_6'})

    def test_13_actual_media_postvalidation_swap_uses_captured_png(self):
        # Reuse the independent R1 observer's unchanged851-frame fixture; only codec seam changes.
        path=ROOT/'outputs/mp18-manipulation-133/review/main-L4-r1/observe_media_input.py'
        source=path.read_text();node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='invoke')
        source=source.replace('range(851)','range(931)')
        node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='invoke')
        old=ast.get_source_segment(source,node)
        new="""def invoke_png(argv,frames,timeout=180):
  observed.append(dict(expected_png_sha=pins["frames/frame-0425.png"],actual_encoder_input_sha=sha(frames[425]),mutable_filename_sha=sha((folder/"frames/frame-0425.png").read_bytes()),argv=argv))
  raise StopBeforeEncode("Captured immutable PNG bytes reached codec seam")"""
        self.assertEqual(source.count(old),1);source=source.replace(old,new)
        source=source.replace('invoke=invoke)','invoke=lambda *args:None,invoke_png=invoke_png)')
        source=source.replace('ROOT=Path(__file__).resolve().parents[4]','ROOT=ROOT_HOST').replace('OWN=Path(__file__).resolve().parent','OWN=OWN_HOST')
        with tempfile.TemporaryDirectory(dir=self.R.OUT/'author') as tmp:
            ns={'__file__':str(Path(tmp)/'observer.py'),'ROOT_HOST':ROOT,'OWN_HOST':Path(tmp)}
            exec(compile(source,'<R1-observer-with-actual133-R2-media>','exec'),ns)
            result=json.loads((Path(tmp)/'media-input-observations.json').read_text())
            self.assertEqual(len(result['cases']),2)
            for case in result['cases']:
                self.assertEqual(case['encode_invocations'],1)
                obs=case['observed'][0];self.assertEqual(obs['actual_encoder_input_sha'],obs['expected_png_sha'])
                self.assertEqual(obs['argv'][obs['argv'].index('-i')+1],'pipe:0')
                if case['case']=='changed_after_validation':self.assertNotEqual(obs['mutable_filename_sha'],obs['expected_png_sha'])

    def test_14_actual_png_pipe_input_error_timeout_and_reap(self):
        R=self.R;m=R.load('media133_pipe_HOST',(HERE/'media.py').read_bytes(),HERE/'media.py')
        with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
            target=Path(tmp)/'actual-sha.txt';frames=(b'A'*1500000,b'B'*1700000,b'C'*11)
            code="import sys,hashlib,pathlib;pathlib.Path(sys.argv[1]).write_text(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
            audit=m.invoke_png([sys.executable,'-I','-B','-c',code,str(target)],frames,timeout=10)
            expected=__import__('hashlib').sha256()
            for b in frames:expected.update(b)
            self.assertEqual(target.read_text(),expected.hexdigest());self.assertEqual(audit['input_sha256'],expected.hexdigest())
            self.assertEqual(audit['png_bytes'],sum(map(len,frames)));self.assertEqual(audit['child_state'],'REAPED')
            with self.assertRaises(ValueError):m.invoke_png([sys.executable,'-I','-B','-c','raise SystemExit(3)'],(b'X'*4000000,),timeout=5)
            with self.assertRaises(TimeoutError):m.invoke_png([sys.executable,'-I','-B','-c','import time;time.sleep(10)'],(b'X'*4000000,),timeout=.2)
            self.assertFalse(any(t.name=='133-verified-PNG-pipe' and t.is_alive() for t in __import__('threading').enumerate()))

    def test_15_actual_ffmpeg_image2pipe_smoke_HOST_only(self):
        import shutil
        R=self.R;m=R.load('media133_codec_HOST',(HERE/'media.py').read_bytes(),HERE/'media.py')
        ffmpeg,ffprobe=[shutil.which(n) for n in ('ffmpeg','ffprobe')];self.assertTrue(ffmpeg and ffprobe)
        png=(ROOT/'outputs/mp18-profile-repair-130/runs/dee4f7e320ea464aabd34bc41740efe1/retrieved/frames/frame-0000.png').read_bytes()
        with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
            movie=Path(tmp)/'HOST_ONLY_CODEC_NOT_NEW_SIMULATION.mp4'
            audit=m.invoke_png([ffmpeg,'-hide_banner','-v','error','-n','-f','image2pipe','-vcodec','png','-framerate','10','-i','pipe:0',
                '-frames:v','3','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-an',str(movie)],(png,png,png),timeout=30)
            self.assertEqual(audit['png_frames'],3)
            probe=json.loads(m.invoke([ffprobe,'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames,width,height,r_frame_rate','-of','json',str(movie)],timeout=10))
            self.assertEqual(probe['streams'][0],{'width':640,'height':480,'r_frame_rate':'10/1','nb_read_frames':'3'})
            m.invoke([ffmpeg,'-hide_banner','-v','error','-i',str(movie),'-f','null','-'],timeout=10)

    def test_16_actual_WinJob_missing_directory_and_full_run_owned_directory(self):
        R=self.R;cfg=json.loads((HERE/'config.json').read_text());hp=cfg['refs']['winjob.py'];raw=(ROOT/hp['path']).read_bytes()
        helper=R.load('winjob133_directory_HOST',raw,ROOT/hp['path'])
        with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
            root=Path(tmp);absent=root/'absent'
            fail=helper.run([sys.executable,'-I','-B','-c','print("HOST_ONLY")'],absent,10,cleanup_s=2)
            self.assertEqual(fail['child_state'],'NOT_CREATED');self.assertIsNone(fail['child_pid']);self.assertFalse(absent.exists())
            source_cfg=cfg['dependency_paths'];snap={'cfg':cfg,'files':{source_cfg['proxy']:(ROOT/source_cfg['proxy']).read_bytes(),hp['path']:raw,'outputs/mp18-manipulation-133/Root-user-followup-approval-r5.json':(ROOT/'outputs/mp18-manipulation-133/Root-user-followup-approval-r5.json').read_bytes(),'outputs/mp18-manipulation-133/Root-user-termination-approval-r7.json':(ROOT/'outputs/mp18-manipulation-133/Root-user-termination-approval-r7.json').read_bytes()},'freeze_sha256':'a'*64}
            record={'run_id':'b'*32,'nonce':'c'*32,'driver_sha256':'d'*64,'bundle_sha256':'e'*64,'bundle_bytes':4,'job_sha256':'f'*64}
            job={'run_id':record['run_id']};calls=[]
            original={n:getattr(R,n) for n in ('capture','previous_gate','attempt_path','_payload','_remote_driver','proxy_command','current','load','consume')}
            out=root/'full-run';out.mkdir()
            def actual_helper(argv,folder,timeout,cleanup_s,input_sender):
                self.assertTrue(folder.is_dir());self.assertEqual(list(folder.iterdir()),[]);calls.append('created-before-actual-WinJob')
                return helper.run([sys.executable,'-I','-B','-c','print("HOST_ONLY_NO_SSH_NO_SDK")'],folder,10,cleanup_s=2)
            try:
                R.capture=lambda:snap;R.previous_gate=lambda *a:None;R.attempt_path=lambda a:out;R._payload=lambda *a:(record,job,b'HOST')
                R._remote_driver=lambda s:'';R.proxy_command=lambda *a:'HOST_ONLY';R.current=lambda s:None
                R.load=lambda name,*a:types.SimpleNamespace(run=actual_helper) if name=='winjob133' else original['load'](name,*a)
                R.consume=lambda *a,**kw:{'runtime_accepted':True,'HOST_FIXTURE_ONLY':True}
                result=R.run(1);self.assertTrue(result['HOST_FIXTURE_ONLY']);self.assertEqual(len(calls),1)
                lifetime=R.parse((out/'transport.json').read_bytes());self.assertEqual(lifetime['child_state'],'REAPED');self.assertEqual(lifetime['actual_child_exit_code'],0)
                self.assertFalse((out/'GO.json').exists())
                with self.assertRaises(ValueError):R.transport_directory(out)
            finally:
                for n,value in original.items():setattr(R,n,value)

    def test_17_actual_NOT_CREATED_handoff_identity_and_unknown_rejections(self):
        R=self.R;previous=R.attempt_path(1);names={'bundle.zip','job.json','prepared.json','attempt.json','transport.json','run-result.json'}
        actual={n:(previous/n).read_bytes() for n in names}
        with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
            fixture=Path(tmp)/'previous';fixture.mkdir()
            for n,raw in actual.items():(fixture/n).write_bytes(raw)
            old=R.attempt_path;R.attempt_path=lambda a:fixture
            def snapshot():return {'files':{(fixture/n).relative_to(ROOT).as_posix():(fixture/n).read_bytes() for n in names}}
            try:
                R.previous_gate(2,snapshot())
                for key,value in [('child_state','UNKNOWN'),('child_state','RUNNING'),('child_pid',99),('raw_complete',True),('terminal',True),('timed_out',True),('actual_child_exit_code',0),('job_active_after',0)]:
                    p=R.parse(actual['transport.json']);p[key]=value;(fixture/'transport.json').write_bytes(R.encode(p))
                    with self.subTest(key=key,value=value),self.assertRaises(ValueError):R.previous_gate(2,snapshot())
                (fixture/'transport.json').write_bytes(actual['transport.json'])
                (fixture/'GO.json').write_text('{}')
                with self.assertRaises(ValueError):R.previous_gate(2,snapshot())
                (fixture/'GO.json').unlink()
                for key,value in [('status','PASS'),('transport_reaped',True),('SDK_reaped',True),('run_id','0'*32)]:
                    result=R.parse(actual['run-result.json']);result[key]=value;(fixture/'run-result.json').write_bytes(R.encode(result))
                    with self.subTest(key=key,value=value),self.assertRaises(ValueError):R.previous_gate(2,snapshot())
                (fixture/'run-result.json').write_bytes(actual['run-result.json'])
                wrong=snapshot();wrong['files'][(fixture/'job.json').relative_to(ROOT).as_posix()]=b'{}'
                with self.assertRaises(ValueError):R.previous_gate(2,wrong)
                p=R.parse(actual['run-result.json']);p.update(transport_reaped=True,SDK_reaped=True);(fixture/'run-result.json').write_bytes(R.encode(p))
                R.previous_gate(2) # Preserve the existing known-reaped continuation branch.
            finally:R.attempt_path=old

    def test_18_last_actual_SDK_admission_original02_and_negatives(self):
        R=self.R;files={}
        for attempt,names in [(1,['bundle.zip','job.json','prepared.json','attempt.json','transport.json','run-result.json']),
                              (2,['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/report.json','retrieved/terminal.json'])]:
            for name in names:
                p=R.attempt_path(attempt)/name;files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
        s={'files':files};R.previous_gate(3,s)
        self.assertEqual(R.attempt_path(3).name,'03')
        with self.assertRaises(ValueError):R.attempt_path(6)
        path=(R.attempt_path(2)/'retrieved/process.json').relative_to(ROOT).as_posix();original=R.read
        try:
            for key,value in [('child_state','RUNNING'),('child_pid',1),('timed_out',True),('actual_child_exit_code',0),('job_sha256','0'*64)]:
                bad=dict(files);p=R.parse(bad[path]);p[key]=value;bad[path]=R.encode(p)
                R.read=lambda p:bad.get(Path(p).relative_to(ROOT).as_posix(),original(p))
                with self.subTest(key=key),self.assertRaises(ValueError):R.previous_gate(3,{'files':bad})
        finally:R.read=original

    def test_19_explicit_followup04_authority_and_original_failed03_lineage(self):
        R=self.R;files={}
        inventories={1:['bundle.zip','job.json','prepared.json','attempt.json','transport.json','run-result.json'],
             2:['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/report.json','retrieved/terminal.json'],
             3:['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/report.json','retrieved/terminal.json','retrieved/recovery-seal.json']}
        for attempt,names in inventories.items():
            for name in names:
                p=R.attempt_path(attempt)/name;files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
        approval='outputs/mp18-manipulation-133/Root-user-followup-approval-r5.json';files[approval]=(ROOT/approval).read_bytes()
        R.previous_gate(4,{'files':files});self.assertEqual(R.attempt_path(4).name,'04')
        with self.assertRaises(ValueError):R.attempt_path(6)
        without=dict(files);without.pop(approval)
        with self.assertRaises(ValueError):R.previous_gate(4,{'files':without})
        false=dict(files);v=R.parse(false[approval]);v['future_SDK_max']=2;false[approval]=R.encode(v)
        with self.assertRaises(ValueError):R.previous_gate(4,{'files':false})
        path=(R.attempt_path(3)/'retrieved/process.json').relative_to(ROOT).as_posix();original=R.read
        try:
            for key,value in [('child_state','RUNNING'),('timed_out',True),('child_creation_time',1),('job_sha256','0'*64),('actual_child_exit_code',0)]:
                bad=dict(files);p=R.parse(bad[path]);p[key]=value;bad[path]=R.encode(p)
                R.read=lambda p:bad.get(Path(p).relative_to(ROOT).as_posix(),original(p))
                with self.subTest(key=key),self.assertRaises(ValueError):R.previous_gate(4,{'files':bad})
        finally:R.read=original

    def test_20_owned_stdlib_watchdog_stop_reason_and_logger_failure_stall(self):
        import subprocess,time
        code=r'''
from pathlib import Path
import sys,json,time,types
root=Path(sys.argv[1]);folder=Path(sys.argv[2]);mode=sys.argv[3]
path=root/'src/simulation/mp18_manipulation_133/native.py';base=(root/'src/simulation/mp18_isaac_130/native.py').read_bytes()
source=path.read_text().replace("_raw = (_here/'base_native.py').read_bytes()",'_raw = '+repr(base))
N=types.ModuleType('owned_native_watchdog_HOST');N.__file__=str(path);exec(compile(source,str(path),'exec'),N.__dict__)
if mode=='stall':N.WATCHDOG_CODE=N.WATCHDOG_CODE.replace("with open(logpath,'a',encoding='utf-8') as stream:","time.sleep(10)\n            with open(logpath,'a',encoding='utf-8') as stream:")
if mode=='error':(folder/'watchdog-reason.ndjson').mkdir()
start=time.monotonic();limits={'native_s':.22 if mode=='global' else 2.,'import_s':.22 if mode not in ('normal','global','eof') else 1.,'cleanup_s':.01,'hold_s':1.,'small_s':1.,'large_s':1.}
ctx=types.SimpleNamespace(cfg={'limits':limits},started_monotonic=start,deadline=start+3,run=folder,job={'run_id':'a'*32},job_hash='b'*64)
b=N.Budget(ctx).arm()
if mode=='normal':b.disarm();raise SystemExit(0)
if mode=='eof':b.process.stdin.close()
if mode=='invalid_type':b.process.stdin.write('0\n');b.process.stdin.flush()
time.sleep(4);raise SystemExit(7)
'''
        with tempfile.TemporaryDirectory(dir=self.R.OUT/'author') as tmp:
            observations=[]
            for mode in ('normal','phase','global','eof','invalid_type','error','stall'):
                folder=Path(tmp)/mode;folder.mkdir();start=time.monotonic()
                proc=subprocess.run([sys.executable,'-X','utf8','-I','-B','-u','-c',code,str(ROOT),str(folder),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=6)
                elapsed=time.monotonic()-start
                self.assertEqual(proc.returncode,0 if mode=='normal' else 124,msg=proc.stderr.decode('utf-8','replace'))
                self.assertLess(elapsed,3.,msg=mode)
                log=folder/'watchdog-reason.ndjson';records=[json.loads(x) for x in log.read_text().splitlines()] if log.is_file() else []
                if mode in ('normal','phase','global','eof','invalid_type'):
                    expected={'normal':'NORMAL_DISARM','phase':'PHASE_DEADLINE','global':'GLOBAL_DEADLINE','eof':'CONTROL_PIPE_EOF','invalid_type':'CONTROL_PIPE_INVALID'}[mode]
                    self.assertIn(expected,[r['reason'] for r in records]);self.assertTrue(all(r['run_id']=='a'*32 and r['job_sha256']=='b'*64 and r['parent_birth']>0 for r in records))
                observations.append({'mode':mode,'actual_exit':proc.returncode,'elapsed_s':elapsed,'reaped_by_subprocess_wait':True,'reasons':[r['reason'] for r in records],'SDK':0})
            print('OWNED_WATCHDOG_HOST',json.dumps(observations))

    def test_21_new05_incomplete04_authority_and_linked_reserve(self):
        R=self.R;files={}
        inventories={1:['bundle.zip','job.json','prepared.json','attempt.json','transport.json','run-result.json'],
             2:['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/report.json','retrieved/terminal.json'],
             3:['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/report.json','retrieved/terminal.json','retrieved/recovery-seal.json'],
             4:['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/recovery-seal.json']}
        for attempt,names in inventories.items():
            for name in names:
                p=R.attempt_path(attempt)/name;files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
        for name in ('Root-user-followup-approval-r5.json','Root-user-termination-approval-r7.json'):
            p=R.OUT/name;files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
        R.previous_gate(5,{'files':files});self.assertEqual(R.attempt_path(5).name,'05')
        with self.assertRaises(ValueError):R.attempt_path(6)
        bad=dict(files);bad.pop((R.OUT/'Root-user-termination-approval-r7.json').relative_to(ROOT).as_posix())
        with self.assertRaises(ValueError):R.previous_gate(5,{'files':bad})
        original=R.read;path=(R.attempt_path(4)/'retrieved/process.json').relative_to(ROOT).as_posix()
        try:
            for key,value in [('timed_out',True),('actual_child_exit_code',0),('policy_basis','TIMEOUT'),('child_state','RUNNING'),('child_creation_time',1)]:
                bad=dict(files);v=R.parse(bad[path]);v[key]=value;bad[path]=R.encode(v)
                R.read=lambda p:bad.get(Path(p).relative_to(ROOT).as_posix(),original(p))
                with self.subTest(key=key),self.assertRaises(ValueError):R.previous_gate(5,{'files':bad})
        finally:R.read=original
        cfg=json.loads((HERE/'config.json').read_text());self.assertEqual([cfg['limits'][k] for k in ('total_s','native_s','recovery_reserve_s','large_s','handshake_s','cleanup_s')],[2700,2280,360,1120,20,2])
        deps=cfg['dependency_paths'];snapshot={'cfg':cfg,'files':{deps['base_driver']:(ROOT/deps['base_driver']).read_bytes(),deps['base_contract']:(ROOT/deps['base_contract']).read_bytes(),HERE.relative_to(ROOT).as_posix()+'/driver.py':(HERE/'driver.py').read_bytes()}}
        ns={};exec(compile(R._remote_driver(snapshot),'<actual-linked-bootstrap>','exec'),ns)
        self.assertEqual(ns['lease_end'](100,2700),2780)
        with self.assertRaises(ValueError):ns['lease_end'](100,382)
        self.assertEqual(ns['lease_end'](100,383),463)

    def test_22_parent_watchdog_receipt_preserves_five_seal_roles(self):
        R=self.R;source=(HERE/'driver.py').read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_parent_watchdog_receipt133')
        base=(ROOT/'src/simulation/mp18_isaac_130/contract.py').read_bytes();C=R.load('receipt_baseC_HOST',base,ROOT/'src/simulation/mp18_isaac_130/contract.py')
        ns={'C':C,'parse':R.parse,'need':R.need,'hashlib':__import__('hashlib'),'math':__import__('math')};exec(compile(ast.get_source_segment(source,node),'<actual-parent-watchdog-receipt>','exec'),ns)
        with tempfile.TemporaryDirectory(dir=R.OUT/'author') as tmp:
            ctx=types.SimpleNamespace(run=Path(tmp),job={'run_id':'a'*32},job_hash='b'*64)
            record={'child_state':'REAPED','job_active_after':0,'raw_complete':True,'child_pid':42,'child_creation_time':134386004953591235}
            row={'run_id':'a'*32,'job_sha256':'b'*64,'parent_pid':42,'parent_birth':record['child_creation_time'],'reason':'PHASE_DEADLINE','phase':'large','kill_intent':True,'chosen_deadline_monotonic':1.,'phase_deadline_monotonic':1.,'native_end_monotonic':2.,'observed_monotonic':1.01}
            path=ctx.run/'watchdog-reason.ndjson';raw=R.encode(row);path.write_bytes(raw)
            receipt=ns['_parent_watchdog_receipt133'](ctx,record);self.assertEqual(receipt['status'],'OBSERVED_VALIDATED_ASYNC_INTENTS');self.assertEqual(receipt['raw_sha256'],R.digest(raw))
            self.assertEqual(receipt['parent_birth'],134386004953591235);self.assertIn('NOT_INFERRED',receipt['OS_exit_causality'])
            armed=dict(row,reason='ARMED',kill_intent=False);path.write_bytes(R.encode(armed))
            self.assertEqual(ns['_parent_watchdog_receipt133'](ctx,record)['status'],'UNKNOWN_TERMINATION_INTENT_NOT_RECORDED')
            path.unlink();self.assertEqual(ns['_parent_watchdog_receipt133'](ctx,record)['status'],'UNKNOWN_LOG_NOT_FOUND')
            path.write_bytes(b'x'*65537);self.assertEqual(ns['_parent_watchdog_receipt133'](ctx,record)['status'],'UNKNOWN_LOG_UNBOUNDED')
            row['parent_birth']+=1;path.write_bytes(R.encode(row));self.assertEqual(ns['_parent_watchdog_receipt133'](ctx,record)['status'],'UNKNOWN_LOG_READ_OR_VALIDATION_ERROR')
        v,j,r=self.lifecycle_fixture();self.R.lifecycle(v,j,r)


if __name__=='__main__':unittest.main(verbosity=2)
