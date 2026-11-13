"""111 B HOST tests. Synthetic authority fixtures; no SSH or SDK is executed."""
import ctypes
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch
import zipfile

HERE=Path(__file__).absolute().parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('bootstrap111_test',HERE/'bootstrap.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
OUTPUT=ROOT/b.OUT/'B-implementation'


def fixture(folder):
    root=folder/'capsule';root.mkdir(parents=True)
    deps=b.read(ROOT/b.OUT/'dependency-census.json')['records']
    for d in deps:
        p=root/d['target_path'];p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes((ROOT/d['source_path']).read_bytes())
    for n in b.MUTABLE:
        p=root/b.SRC/n
        original=HERE/n
        p.write_bytes(original.read_bytes() if original.exists() else b'# declared HOST fixture\n')
    out=root/b.OUT;out.mkdir(parents=True,exist_ok=True);(out/'review').mkdir(exist_ok=True)
    executable=ROOT/b.OUT/'execute.py'
    (out/'execute.py').write_bytes(executable.read_bytes() if executable.exists() else b'# HOST harness\n')
    p=root/b.PLAN;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/b.PLAN).read_bytes())
    (out/'review/L2-r2.json').write_bytes((ROOT/b.OUT/'review/L2-r2.json').read_bytes())
    cfg=b.read(root/b.SRC/'config.json')
    # HOST namespace only. This config is never supplied to an actual SDK.
    cfg['remote_root']=str(folder/'111/worker/runs').replace('\\','/')
    (root/b.SRC/'config.json').write_bytes(json.dumps(cfg,indent=2).encode())
    freeze={'unit':'111','round':1,'source_count':20,'hardware_approved':False,'plan_sha256':b.PLAN_SHA,'L2_sha256':b.L2_SHA,
            'source':{n:b.digest((root/b.SRC/n).read_bytes()) for n in b.MUTABLE},
            'harness':{'execute.py':b.digest((out/'execute.py').read_bytes())},'dependencies':deps}
    fr=b.canonical(freeze);(out/'source-freeze-r1.json').write_bytes(fr)
    review={'unit':'111','phase':'L4','round':1,'reviewer':'SYNTHETIC_HOST_FIXTURE_NOT_REVIEW',
            'non_author':True,'verdict':'PASS','all_required_met':True,'met':10,'unmet':0,
            'criteria':[{'id':n,'required':True,'met':True} for n in sorted(b.AC)],
            'actual_plan_sha256':b.PLAN_SHA,'actual_freeze_sha256':b.digest(fr),
            'unit_dispositions':{n:{'verdict':'PASS','unresolved_count':0} for n in ('B','C','integration')}}
    rr=b.canonical(review);(out/'review/L4-r1.json').write_bytes(rr)
    approval={'unit':'111','explicit_user_approval':True,'user_quote':'SYNTHETIC HOST ONLY',
              'scope':'111_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S','duration_s':2700,
              'native_limits':{'import':1,'render_smoke':1,'motion':1},'native_budget_starts_after_review':True,
              'clock_mutation':False,'hardware_approved':False,'plan_sha256':b.PLAN_SHA,
              'template_freeze_sha256':b.digest(fr),'review_sha256':b.digest(rr)}
    (out/'native-approval.json').write_bytes(b.canonical(approval))
    return root


def request(ctx):
    now=time.monotonic()
    return dict(schema_version=1,unit='111',nonce='a'*32,client_started_monotonic=now,
                client_deadline_monotonic=now+2700,**ctx.pins)


def lease(ctx):
    q=request(ctx);now=time.monotonic();wall=time.time()
    q.update(remote_started_monotonic=now-20,remote_deadline_monotonic=now+2680,
             remote_started_unix=wall-20,remote_deadline_unix=wall+2680,handshake_deduction_s=20)
    q['claim_sha256']=b.digest(b.canonical(q));return q


class Host(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        cls.batch=OUTPUT/('host-'+str(time.time_ns()));cls.batch.mkdir()
        cls.root=fixture(cls.batch)
        cls.helper=b.load_helper(cls.root)

    def ctx(self,native=True):
        return b.context(self.root,1,helper=self.helper,owner_end=time.monotonic()+10,require_native=native)

    def test_context_actual_positive_source20(self):
        ctx=self.ctx()
        self.assertTrue(ctx.native_authorized)
        self.assertEqual(len(ctx.source),20)
        self.assertEqual(len(ctx.payload),58)
        self.assertEqual(b.digest(ctx.helper_bytes),b.HELPER_SHA)
        self.assertEqual(ctx.template_config['deadline_unix'],0)

    def test_native_false_cannot_mint(self):
        ctx=self.ctx(False)
        self.assertFalse(ctx.native_authorized)
        with self.assertRaises(ValueError):b.prepare_capsule(ctx)

    def test_context_rejection_controls(self):
        p=self.root/b.OUT/'native-approval.json';raw=p.read_bytes()
        for field,value in (('hardware_approved',True),('clock_mutation',True),('unit','108'),('duration_s',True)):
            try:
                item=b.parse(raw);item[field]=value;p.write_bytes(b.canonical(item))
                with self.subTest(field=field),self.assertRaises(ValueError):self.ctx()
            finally:p.write_bytes(raw)
        p=self.root/b.OUT/'review/L4-r1.json';raw=p.read_bytes()
        try:
            item=b.parse(raw);item['unit_dispositions']['C']['verdict']='BLOCK';p.write_bytes(b.canonical(item))
            with self.assertRaises(ValueError):self.ctx()
        finally:p.write_bytes(raw)

    def test_context_armed_before_first_read(self):
        original=b.Path.read_bytes;observations=[]
        def checked(path):
            observations.append(any(t.is_alive() and t.name.startswith('Thread-') for t in threading.enumerate()))
            return original(path)
        with patch.object(b.Path,'read_bytes',checked):self.ctx()
        self.assertTrue(observations and all(observations))
        with patch.object(b.Path,'read_bytes',side_effect=AssertionError('read before owner')):
            with self.assertRaises(ValueError):
                b.context(self.root,1,helper=self.helper,owner_end=time.monotonic()-1)

    def test_phase_binding_and_thread_owner(self):
        rt=b.Runtime(self.root,1,self.helper,lease(self.ctx()),native_authorized=True)
        cfg=rt.bind_config({'deadline_unix':123,'hardware_approved':False})
        self.assertEqual(dict(cfg),{'deadline_unix':123,'hardware_approved':False})
        self.assertIs(cfg.runtime,rt)
        ctx=rt.bind(types.SimpleNamespace(cfg=dict(cfg)));self.assertIs(ctx.runtime,rt)
        with patch.object(b.Path,'read_bytes',side_effect=AssertionError('unowned read')):
            with self.assertRaises(ValueError):rt.verify()
        with rt.phase(2) as outer:
            with rt.phase(4) as inner:self.assertLessEqual(inner,outer)
            result=[]
            def other():
                try:rt.verify()
                except Exception as e:result.append(type(e).__name__)
            t=threading.Thread(target=other);t.start();t.join()
            self.assertEqual(result,['ValueError'])

    def test_closed_lease_min_and_mutation(self):
        item=lease(self.ctx());b.lease_check(item)
        for change in ({'unit':'108'},{'remote_deadline_monotonic':float('inf')},{'handshake_deduction_s':True}):
            changed=dict(item,**change)
            with self.assertRaises(ValueError):b.lease_check(changed)

    def test_capsule_roundtrip_and_extra(self):
        ctx=self.ctx();l=lease(ctx);cap=b.prepare_capsule(ctx)
        target=Path(ctx.template_config['remote_root']).parents[1]/'controller'/l['nonce']
        b.extract_capsule(cap.raw,target,l)
        self.assertEqual(len([p for p in target.rglob('*') if p.is_file()]),59)
        with self.assertRaises(ValueError):b.extract_capsule(cap.raw,target,l)
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(cap.raw)) as old,zipfile.ZipFile(out,'w') as new:
            for n in old.namelist():new.writestr(n,old.read(n))
            new.writestr('../escape.txt',b'x')
        with self.assertRaises(ValueError):b.extract_capsule(out.getvalue(),target.parent/'other',l)

    def test_activation_actual_roundtrip(self):
        folder=self.batch/'active';root=fixture(folder);ctx=b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10,require_native=True)
        l=lease(ctx);claim=b.claim_path(root);claim.parent.mkdir(parents=True,exist_ok=True);claim.write_bytes(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
        budget=b.activate(ctx,l);self.assertEqual(len(budget['execution_source']),20)
        rt=b.Runtime(root,1,self.helper,l,native_authorized=True)
        with rt.phase():self.assertEqual(rt.verify(),budget)
        with self.assertRaises(ValueError):b.activate(ctx,l)
        claim.write_bytes(b'{}')
        with rt.phase(),self.assertRaises(ValueError):rt.verify()

    def test_command_lengths_actual(self):
        ctx=self.ctx();q=request(ctx)
        code=b.hello_code(q,ctx.helper_bytes);argv=b.ssh_argv(ctx.template_config,code)
        self.assertLess(len(subprocess.list2cmdline(argv)),8000)
        l=lease(ctx);a={'op':'install','root':str(self.root),'round_number':1,'lease':l}
        code=b.relay_code(a,ctx.helper_bytes)
        self.assertLess(len(subprocess.list2cmdline(b.ssh_argv(ctx.template_config,code))),8000)
        (self.batch/'command-lengths.json').write_text(json.dumps({'hello':len(subprocess.list2cmdline(argv)),'relay':len(code)}))

    def test_client_prefix_owner_before_folder_and_wire(self):
        ctx=self.ctx();l=lease(ctx);seen=[]
        def stopped(*_):
            seen.append(any(t.is_alive() and t.name.startswith('Thread-') for t in threading.enumerate()))
            raise OSError('HOST stop before actual SSH')
        with patch.object(b,'ssh_argv',stopped):
            with self.assertRaises(OSError):b.subsequent(ctx,l,'install',b'payload')
        self.assertEqual(seen,[True])

    def test_first_hello_actual_process_and_live(self):
        ctx=self.ctx();q=request(ctx);code=b.hello_code(q,ctx.helper_bytes)
        process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ready=b.parse(process.stdout.readline());b.validate_ready(ready,q)
        out,err=process.communicate(b.canonical({'kind':'LIVE','request':q,'ready_sha256':b.digest(b.canonical(ready))})+b'\n',timeout=4)
        self.assertEqual(process.returncode,0,err)
        l=b.parse(out)['lease'];b.lease_check(l)
        self.assertEqual(l['remote_deadline_monotonic'],ready['monotonic']+2680)
        self.assertFalse((self.root/'attempt.json').exists())
        (self.batch/'actual-hello-stdout.raw').write_bytes(b.canonical(ready)+b'\n'+out)
        (self.batch/'actual-hello-stderr.raw').write_bytes(err)

    def test_actual_first_exchange_service_local_process(self):
        ctx=self.ctx();q=request(ctx)
        local=lambda cfg,code:[sys.executable,'-I','-S','-B','-c',code]
        with patch.object(b,'ssh_argv',local):
            accepted=b.first_exchange(ctx,q,q['client_deadline_monotonic'])
        self.assertEqual(accepted['nonce'],q['nonce'])
        self.assertEqual(accepted['handshake_deduction_s'],20)
        q=request(ctx);q['nonce']='b'*32
        with patch.object(b,'ssh_argv',local),patch.object(b,'validate_ready',side_effect=ValueError('HOST rejected READY')):
            with self.assertRaises(ValueError):b.first_exchange(ctx,q,q['client_deadline_monotonic'])
        self.assertNotIn(b'GRANT',(ctx.out/('first-'+q['nonce'])/'stdout.txt').read_bytes())

    def test_first_application_payload_rejected(self):
        ctx=self.ctx();code=b.hello_code(request(ctx),ctx.helper_bytes)
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],input=ctx.source['bootstrap.py'],capture_output=True,timeout=4)
        self.assertEqual(result.returncode,2)
        self.assertNotIn(b'GRANT',result.stdout)
        (self.batch/'first-payload-rejected.raw').write_bytes(result.stdout+result.stderr)

    def test_expired_relay_read_zero(self):
        ctx=self.ctx();l=lease(ctx);l['remote_started_monotonic']=time.monotonic()-2701
        l['remote_deadline_monotonic']=l['remote_started_monotonic']+2700
        l['claim_sha256']=b.digest(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
        code=b.relay_code({'op':'fetch','root':str(self.root),'round_number':1,'lease':l},ctx.helper_bytes)
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,timeout=3)
        self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,b'')

    def test_actual_prefix_block_owned_process(self):
        ctx=self.ctx();l=lease(ctx)
        l['remote_started_monotonic']=time.monotonic()-2698.8;l['remote_deadline_monotonic']=l['remote_started_monotonic']+2700
        l['claim_sha256']=b.digest(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
        folder=self.batch/'prefix';folder.mkdir()
        args={'root':str(self.batch/'111/controller'/l['nonce']),'round_number':1,'lease':l,'op':'fetch'}
        code=("import importlib.util,pathlib,time,os,json; s=importlib.util.spec_from_file_location('b',"+repr(str(HERE/'bootstrap.py'))+");b=importlib.util.module_from_spec(s);s.loader.exec_module(b);h=b.load_helper(pathlib.Path("+repr(str(ROOT))+"));a="+repr(args)+";r,w=os.pipe();orig=b.Path.read_bytes;"
              "b.Path.read_bytes=lambda p:os.read(r,1) if p.name=='attempt.json' else orig(p);"
              "f=h.Fence(min(time.monotonic()+20,a['lease']['remote_deadline_monotonic'])).__enter__();"
              "b._relay_main(a,h,f,time.monotonic(),{})")
        start=time.monotonic();process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        h=self.helper;kernel=h.Kernel();times=[ctypes.wintypes.FILETIME() for _ in range(4)]
        kernel.check(kernel.k.GetProcessTimes(int(process._handle),*[ctypes.byref(t) for t in times]))
        creation=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        out,err=process.communicate(timeout=4)
        self.assertEqual(process.returncode,124,err)
        self.assertLess(time.monotonic()-start,3)
        (folder/'observation.json').write_text(json.dumps({'held_pid':process.pid,'held_creation_time':creation,'actual_exit':process.returncode,'elapsed':time.monotonic()-start,'seam':'actual B claim read redirected to blocking OS pipe; no SDK'}))
        (folder/'stdout.raw').write_bytes(out);(folder/'stderr.raw').write_bytes(err)

    def test_actual_subsequent_install_activate_fetch_and_bad_claim(self):
        folder=self.batch/'wire';root=fixture(folder)
        ctx=b.context(root,1,helper=self.helper,owner_end=time.monotonic()+20,require_native=True)
        l=lease(ctx);capsule=b.prepare_capsule(ctx)
        target=Path(ctx.template_config['remote_root']).parents[1]/'controller'/l['nonce']
        for op,payload in (('install',capsule.raw),('activate',b''),('fetch',b'')):
            args={'root':str(target),'round_number':1,'lease':l,'op':op}
            code=b.relay_code(args,ctx.helper_bytes)
            header={'bootstrap_length':len(ctx.source['bootstrap.py']),'bootstrap_sha256':b.digest(ctx.source['bootstrap.py']),
                    'payload_length':len(payload),'payload_sha256':b.digest(payload)}
            wire=b.canonical(header)+b'\n'+ctx.source['bootstrap.py']+payload
            result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],input=wire,capture_output=True,timeout=20)
            (folder/(op+'-stdout.raw')).write_bytes(result.stdout);(folder/(op+'-stderr.raw')).write_bytes(result.stderr)
            self.assertEqual(result.returncode,0,result.stderr)
            if op=='fetch':
                h,sep,data=result.stdout.partition(b'\n');h=b.parse(h)
                self.assertEqual(b.digest(data),h['sha256'])
                with zipfile.ZipFile(io.BytesIO(data)) as z:self.assertIn('activation.json',z.namelist())
                verification=b.verify_fetch(ctx,l,data,require_success=False)
                self.assertFalse(verification['native_outcome_accepted'])
                with self.assertRaises(ValueError):b.verify_fetch(ctx,l,data,require_success=True)
                # Declared synthetic C receipts prove the positive closure gate;
                # these records are never presented as an actual SDK run.
                with zipfile.ZipFile(io.BytesIO(data)) as z:content={n:z.read(n) for n in z.namelist()}
                budget=b.parse(content['runtime-budget.json']);jobs={};validation={}
                for index,(purpose,status) in enumerate((('import','IMPORT_VERIFIED'),('render_smoke','SMOKE_VERIFIED'),('motion','WORKSPACE_MOTION_VERIFIED')),1):
                    run_id=('%032x'%index);prefix='runs/'+run_id+'/'
                    inputs={'source/'+n:v for n,v in budget['execution_source'].items()}
                    if purpose!='import':inputs['import-proof/job.json']=jobs['import'][1]
                    if purpose=='motion':inputs['smoke-proof/job.json']=jobs['render_smoke'][1]
                    job={'run_id':run_id,'purpose':purpose,'plan_sha256':b.PLAN_SHA,'hardware_approved':False,'inputs':inputs}
                    jr=b.canonical(job);jh=b.digest(jr);jobs[purpose]=(job,jh);content[prefix+'job.json']=jr
                    identity={'run_id':run_id,'job_sha256':jh,'purpose':purpose}
                    ex=dict(identity,pid=11,timed_out=False,policy_exit_code=0,child_state='REAPED',child_pid=12,actual_child_exit_code=0)
                    terminal=dict(identity,pid=12,parent_pid=11,hardware_approved=False,physical_calibration=False,training='NOT_RUN',status='CLOSED',phase='APP_CLOSED',code=0,files_sha256={})
                    for n,v in (('exit.json',ex),('terminal.json',terminal),('remote-shell.json',dict(identity,python_exit_code=0))):
                        content[prefix+'retrieved/'+n]=b.canonical(v)
                    content[prefix+'retrieved/stdout.txt']=b'';content[prefix+'retrieved/stderr.txt']=b''
                    validation[purpose]=dict(identity,status=status);content[prefix+'validation.json']=b.canonical(validation[purpose])
                content['current.json']=b.canonical(validation['motion'])
                for purpose,n in (('import','import-verified.json'),('render_smoke','smoke-verified.json')):
                    content[n]=b.canonical({'run_id':jobs[purpose][0]['run_id'],'job_sha256':jobs[purpose][1]})
                content['controller-process/process.json']=b.canonical({'terminal':True,'raw_complete':True,'job_active_after':0,'child_pid':77,'child_state':'REAPED','actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,'errors':[]})
                synthetic=io.BytesIO()
                with zipfile.ZipFile(synthetic,'w') as z:
                    for n,v in content.items():z.writestr(n,v)
                accepted=b.verify_fetch(ctx,l,synthetic.getvalue(),require_success=True)
                self.assertTrue(accepted['controller_gates_reported_verified'])
                self.assertFalse(accepted['native_outcome_accepted'])
        b.claim_path(target).write_bytes(b'{}')
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],input=wire,capture_output=True,timeout=4)
        self.assertEqual(result.returncode,2)
        self.assertNotIn(b'COMPLETED',result.stdout)


    def test_repair_actual_uuid65_complete_commands(self):
        ctx=self.ctx();lengths=[]
        for _ in range(65):
            q=request(ctx);q['nonce']=__import__('uuid').uuid4().hex
            code=b.hello_code(q,ctx.helper_bytes)
            lengths.append(len(subprocess.list2cmdline(b.ssh_argv(ctx.template_config,code))))
        self.assertEqual(len(lengths),65)
        self.assertLess(max(lengths),8000)
        (self.batch/'repair-uuid65-lengths.json').write_text(json.dumps(lengths))

    def test_repair_actual_hello_float_canonical(self):
        ctx=self.ctx()
        for delta,expected in ((0,0),(.125,2)):
            q=request(ctx);q['client_started_monotonic']=1396.002;q['client_deadline_monotonic']=1396.002+2700+delta
            code=b.hello_code(q,ctx.helper_bytes)
            process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            ready=b.parse(process.stdout.readline());b.validate_ready(ready,q)
            raw,err=process.communicate(b.canonical({'kind':'LIVE','request':q,'ready_sha256':b.digest(b.canonical(ready))})+b'\n',timeout=4)
            self.assertEqual(process.returncode,expected,err)
            self.assertEqual(b'GRANT' in raw,expected==0)
            (self.batch/('repair-float-'+str(delta)+'-stdout.raw')).write_bytes(raw)
            (self.batch/('repair-float-'+str(delta)+'-stderr.raw')).write_bytes(err)



if __name__=='__main__':unittest.main(verbosity=2)
