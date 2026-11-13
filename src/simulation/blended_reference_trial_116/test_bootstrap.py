"""116 B HOST tests. Synthetic authority fixtures; no SSH or SDK is executed."""
import ast
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
spec=importlib.util.spec_from_file_location('bootstrap116_test',HERE/'bootstrap.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
OUTPUT=ROOT/b.OUT/'B-implementation'


def synthetic_receipt(root, deps):
    """SYNTHETIC_HOST_FIXTURE_NOT_REVIEW_OR_NATIVE_AUTHORITY; actual policy, synthetic full-sampling claim."""
    payload={record['target_path']:(root/record['target_path']).read_bytes() for record in deps}
    source={Path(record['target_path']).name:payload[record['target_path']]
            for record in deps if record['group'] in ('source108','immutable_A')}
    for name in ('bootstrap.py','driver.py','config.json','validate.py','decision_schema.py','scene.py','workspace.py','program.json','test_scene.py'):
        source[name]=(root/b.SRC/name).read_bytes()
    bundle=b.workspace_bundle(source,payload,source['config.json'])
    d=b.workspace_validator(source['validate.py'],source['decision_schema.py'])
    bundle=d._bundle(bundle)
    numeric_contract=d._run_policy(bundle)
    data=d._json(bundle['ref/workspace.json']);metrics=d._metrics(data)
    sha=d._digest(bundle['ref/workspace.json'])
    record={'schema_version':1,'unit':'116','scope':d._WORKSPACE_SCOPE,
            'inputs':d._input_pins(bundle),'algorithms':d._algorithm_pins(bundle),
            'full_sampling':True,'sample_count':8192,'path_state_count':6241,
            'workspace_sha256':sha,'metrics':metrics,'numeric_contract':numeric_contract,
            'result_sha256':d._result_sha(sha,metrics,numeric_contract)}
    raw=d._canonical(record)
    (root/b.OUT/'workspace-preflight.json').write_bytes(raw)
    return bundle,raw


def fixture(folder, *, preserve_remote_root=False):
    root=folder/'capsule';root.mkdir(parents=True)
    deps=b.read(ROOT/b.OUT/'dependency-census-pre-receipt.json')['records']
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
    (out/'dependency-census-pre-receipt.json').write_bytes((ROOT/b.OUT/'dependency-census-pre-receipt.json').read_bytes())
    cfg=b.read(root/b.SRC/'config.json')
    # HOST namespace only. This config is never supplied to an actual SDK.
    if not preserve_remote_root:
        cfg['remote_root']=str(folder/'robot-arm-lab/116/worker/runs').replace('\\','/')
    (root/b.SRC/'config.json').write_bytes(json.dumps(cfg,indent=2).encode())
    synthetic_receipt(root,deps)
    receipt_raw=(out/'workspace-preflight.json').read_bytes()
    deps=[*deps,{'source_path':b.RECEIPT,'target_path':b.RECEIPT,'sha256':b.digest(receipt_raw),'bytes':len(receipt_raw),'group':'workspace_preflight'}]
    freeze={'unit':'116','round':1,'source_count':21,'hardware_approved':False,'plan_sha256':b.PLAN_SHA,'L2_sha256':b.L2_SHA,
            'source':{n:b.digest((root/b.SRC/n).read_bytes()) for n in b.MUTABLE},
            'harness':{'execute.py':b.digest((out/'execute.py').read_bytes())},'dependencies':deps}
    fr=b.canonical(freeze);(out/'source-freeze-r1.json').write_bytes(fr)
    review={'unit':'116','phase':'L4','round':1,'reviewer':'SYNTHETIC_HOST_FIXTURE_NOT_REVIEW_OR_NATIVE_AUTHORITY',
            'non_author':True,'verdict':'PASS','all_required_met':True,'met':18,'unmet':0,'required':18,'unresolved_count':0,
            'criteria':[{'id':n,'required':True,'met':True} for n in sorted(b.AC)],
            'actual_plan_sha256':b.PLAN_SHA,'actual_freeze_sha256':b.digest(fr),
            'unit_dispositions':{n:{'verdict':'PASS','unresolved_count':0} for n in ('B','C','D','E','integration','performance')}}
    rr=b.canonical(review);(out/'review/L4-r1.json').write_bytes(rr)
    approval={'unit':'116','explicit_user_approval':True,'user_quote':'SYNTHETIC HOST ONLY',
              'scope':'116_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S_HALFBLEND','duration_s':2700,
              'native_limits':{'import':1,'render_smoke':1,'motion':1},'native_budget_starts_after_review':True,
              'clock_mutation':False,'hardware_approved':False,'plan_sha256':b.PLAN_SHA,
              'template_freeze_sha256':b.digest(fr),'review_sha256':b.digest(rr)}
    (out/'native-approval.json').write_bytes(b.canonical(approval))
    return root


def request(ctx):
    now=time.monotonic()
    return dict(schema_version=1,unit='116',nonce='a'*32,client_started_monotonic=now,
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

    def test_context_actual_positive_source21(self):
        ctx=self.ctx()
        self.assertTrue(ctx.native_authorized)
        self.assertEqual(len(ctx.source),21)
        self.assertEqual(len(ctx.payload),62)
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
        self.assertEqual(len([p for p in target.rglob('*') if p.is_file()]),63)
        with self.assertRaises(ValueError):b.extract_capsule(cap.raw,target,l)
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(cap.raw)) as old,zipfile.ZipFile(out,'w') as new:
            for n in old.namelist():new.writestr(n,old.read(n))
            new.writestr('../escape.txt',b'x')
        with self.assertRaises(ValueError):b.extract_capsule(out.getvalue(),target.parent/'other',l)

    def test_activation_actual_roundtrip(self):
        folder=self.batch/'active';root=fixture(folder);ctx=b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10,require_native=True)
        l=lease(ctx);claim=b.claim_path(root);claim.parent.mkdir(parents=True,exist_ok=True);claim.write_bytes(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
        budget=b.activate(ctx,l);self.assertEqual(len(budget['execution_source']),21)
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
        args={'root':str(self.batch/'116/controller'/l['nonce']),'round_number':1,'lease':l,'op':'fetch'}
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
                    inputs['workspace-preflight.json']=ctx.workspace_preflight_sha256
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
            hello=b.hello_code(q,ctx.helper_bytes)
            l=lease(ctx);l['nonce']=q['nonce']
            l['claim_sha256']=b.digest(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
            args={'root':str(Path(ctx.template_config['remote_root']).parents[1]/'controller'/l['nonce']),
                  'round_number':1,'lease':l,'op':'install'}
            relay=b.relay_code(args,ctx.helper_bytes)
            lengths.append({'nonce':q['nonce'],
                'hello_complete_argv':len(subprocess.list2cmdline(b.ssh_argv(ctx.template_config,hello))),
                'relay_complete_argv':len(subprocess.list2cmdline(b.ssh_argv(ctx.template_config,relay)))})
        self.assertEqual(len(lengths),65)
        self.assertLess(max(r['hello_complete_argv'] for r in lengths),8000)
        self.assertLess(max(r['relay_complete_argv'] for r in lengths),8000)
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


    def test_scope_pure_ancestry_thread_and_same_end_new_phase(self):
        rt=b.Runtime(self.root,1,self.helper,lease(self.ctx()),native_authorized=True)
        with patch.object(b.Path,'read_bytes',side_effect=AssertionError('scope performs I/O')):
            with self.assertRaises(ValueError):rt.workspace_scope()
            with rt.phase():
                scope=rt.workspace_scope()
                self.assertIsNone(rt.require_workspace_scope(scope))
                with self.assertRaises(AttributeError):scope.end=scope.end+1
                with rt.phase():self.assertIsNone(rt.require_workspace_scope(scope))
                seen=[]
                def other():
                    try:rt.require_workspace_scope(scope)
                    except ValueError:seen.append('DENIED')
                thread=threading.Thread(target=other);thread.start();thread.join()
                self.assertEqual(seen,['DENIED'])
            with rt.phase() as same_end:
                self.assertEqual(same_end,scope.end)
                with self.assertRaises(ValueError):rt.require_workspace_scope(scope)

    def test_scope_wrong_runtime_and_expired_memory_check(self):
        l=lease(self.ctx());rt=b.Runtime(self.root,1,self.helper,l,native_authorized=True)
        other=b.Runtime(self.root,1,self.helper,l,native_authorized=True)
        with rt.phase(10):
            scope=rt.workspace_scope()
            with self.assertRaises(ValueError):other.require_workspace_scope(scope)
            with patch.object(b.time,'monotonic',return_value=scope.end),self.assertRaises(ValueError):
                rt.require_workspace_scope(scope)

    def test_authority_actual_context_activation_and_no_producer(self):
        root=fixture(self.batch/'authority');ctx=b.context(root,1,helper=self.helper,owner_end=time.monotonic()+20,require_native=True)
        l=lease(ctx);claim=b.claim_path(root);claim.parent.mkdir(parents=True,exist_ok=True)
        claim.write_bytes(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
        b.activate(ctx,l);rt=b.Runtime(root,1,self.helper,l,native_authorized=True)
        original=b.workspace_validator;calls=[]
        def consumer(validate_raw,policy_raw):
            d=original(validate_raw,policy_raw)
            d.produce_workspace_receipt=lambda *_: (_ for _ in ()).throw(AssertionError('consumer produced'))
            calls.append('actual D identity consumer')
            return d
        with rt.phase(),patch.object(b,'workspace_validator',consumer):
            scope=rt.workspace_scope();result=rt.workspace_authority(scope)
            self.assertEqual(set(result),{'schema_version','unit','receipt_raw','receipt_sha256',
                             'template_config_raw','active_config_raw','decision_inputs'})
            self.assertEqual(result['unit'],'116');self.assertEqual(len(result['decision_inputs']),48)
            self.assertEqual(result['active_config_raw'],b.stamp(ctx.template_bytes,l['remote_deadline_unix']))
            self.assertEqual(result['receipt_sha256'],ctx.workspace_preflight_sha256)
            self.assertEqual(calls,['actual D identity consumer'])
            budget=b.read(ctx.out/'runtime-budget.json');budget['workspace_preflight_sha256']='0'*64
            (ctx.out/'runtime-budget.json').write_bytes(b.canonical(budget))
            with self.assertRaises(ValueError):rt.workspace_authority(scope)
        with rt.phase(),patch.object(b.Path,'read_bytes',side_effect=AssertionError('stale owner read')):
            with self.assertRaises(ValueError):rt.workspace_authority(scope)

    def test_build_explicit_local_service_seam_no_review_and_exclusive(self):
        root=fixture(self.batch/'build');out=root/b.OUT
        receipt=(out/'workspace-preflight.json').read_bytes();(out/'workspace-preflight.json').unlink()
        (out/'review/L4-r1.json').unlink();(out/'native-approval.json').unlink()
        calls=[]
        def produce(bundle):
            calls.append((len(bundle),any(t.is_alive() and t.name.startswith('Thread-') for t in threading.enumerate())))
            self.assertIs(type(b.parse(bundle['source/config.json'])['deadline_unix']),int)
            return receipt
        service=types.SimpleNamespace(produce_workspace_receipt=produce)
        with patch.object(b,'workspace_validator',return_value=service):
            result=b.build_static_receipt(root)
            self.assertEqual(calls,[(48,True)])
            self.assertEqual(result['sha256'],b.digest(receipt));self.assertEqual(len(result['decision_inputs']),48)
            with self.assertRaises(ValueError):b.build_static_receipt(root)
            self.assertEqual(calls,[(48,True)])
        self.assertFalse((out/'activation.json').exists())
        self.assertFalse((out/'runtime-budget.json').exists())

    def test_context_receipt_missing_mutated_and_extra_dependency(self):
        root=fixture(self.batch/'badreceipt');out=root/b.OUT
        raw=(out/'workspace-preflight.json').read_bytes()
        for replacement in (b'{}',raw+b' '):
            (out/'workspace-preflight.json').write_bytes(replacement)
            with self.assertRaises(ValueError):b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10)
        (out/'workspace-preflight.json').unlink()
        with self.assertRaises(FileNotFoundError):b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10)
        (out/'workspace-preflight.json').write_bytes(raw)
        self.assertEqual(b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10).workspace_preflight_sha256,b.digest(raw))

    def test_review_exact_fourteen_and_each_unit_required(self):
        ctx=self.ctx();review=dict(ctx.review)
        for change in ({'met':10},{'met':True},{'criteria':review['criteria'][:-1]},
                       {'unit_dispositions':{n:v for n,v in review['unit_dispositions'].items() if n!='D'}}):
            with self.assertRaises(ValueError):b.review_gate(dict(review,**change),1,ctx.pins['template_freeze_sha256'])




    def test_validator_binds_policy_raw_without_policy_execution(self):
        validate_raw=(b"def bind_decision_schema(raw):\n global received\n received=raw\n")
        policy_raw=b"raise AssertionError('policy must not execute during binding')\n"
        with patch.object(b.Path,'read_bytes',side_effect=AssertionError('bind I/O')):
            d=b.workspace_validator(validate_raw,policy_raw)
        self.assertIs(d.__source_bytes__,validate_raw)
        self.assertIs(d.received,policy_raw)

    def test_current_policy_pin_before_validator_load(self):
        root=fixture(self.batch/'policy-before-load')
        policy=root/b.SRC/'decision_schema.py';original=policy.read_bytes()
        try:
            policy.write_bytes(original+b'\nraise AssertionError("unverified code")\n')
            with patch.object(b,'workspace_validator',side_effect=AssertionError('validator loaded before current pins')) as load:
                with self.assertRaisesRegex(ValueError,'mutable source decision_schema.py'):
                    b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10)
                load.assert_not_called()
        finally:
            policy.write_bytes(original)

    def test_every_mutable_pin_before_validator_load(self):
        root=fixture(self.batch/'late-freeze-before-load')
        target=root/b.SRC/'test_decision_schema.py';original=target.read_bytes()
        try:
            target.write_bytes(original+b'\n# changed support test\n')
            with patch.object(b,'workspace_validator',side_effect=AssertionError('unverified full freeze')) as load:
                with self.assertRaisesRegex(ValueError,'mutable source test_decision_schema.py'):
                    b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10)
                load.assert_not_called()
        finally:
            target.write_bytes(original)

    def test_closed_source13_and_fresh_policy_in_bundle48(self):
        ctx=self.ctx()
        self.assertEqual(b.MUTABLE,{'bootstrap.py','test_bootstrap.py','driver.py','config.json',
                         'test_driver.py','validate.py','test_validate.py','decision_schema.py','test_decision_schema.py',
                         'scene.py','workspace.py','program.json','test_scene.py'})
        self.assertEqual(len(ctx.freeze['dependencies']),43)
        self.assertEqual(len(ctx.source),21)
        bundle=b.workspace_bundle(ctx.source,ctx.payload,ctx.template_bytes)
        self.assertEqual(len(bundle),48)
        self.assertEqual(bundle['source/decision_schema.py'],ctx.source['decision_schema.py'])
        self.assertEqual(ctx.decision_inputs['source/decision_schema.py'],
                         {'sha256':b.digest(ctx.source['decision_schema.py']),'bytes':len(ctx.source['decision_schema.py'])})
        bad=dict(ctx.source);del bad['decision_schema.py']
        with self.assertRaisesRegex(ValueError,'source21'):
            b.workspace_bundle(bad,ctx.payload,ctx.template_bytes)


    def test_old_runtime20_freeze_rejected_before_validator(self):
        root=fixture(self.batch/'old-source-count');out=root/b.OUT
        item=b.read(out/'source-freeze-r1.json');item['source_count']=20
        fr=b.canonical(item);(out/'source-freeze-r1.json').write_bytes(fr)
        review=b.read(out/'review/L4-r1.json');review['actual_freeze_sha256']=b.digest(fr)
        (out/'review/L4-r1.json').write_bytes(b.canonical(review))
        with patch.object(b,'workspace_validator',side_effect=AssertionError('old20 executed')) as load:
            with self.assertRaisesRegex(ValueError,'source13 plus harness1 freeze'):
                b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10)
            load.assert_not_called()

    def test_no_native_authority_before_context_reads(self):
        rt=b.Runtime(self.root,1,self.helper,lease(self.ctx()),native_authorized=False)
        with rt.phase():
            scope=rt.workspace_scope()
            with patch.object(b.Path,'read_bytes',side_effect=AssertionError('unauthorized context read')):
                with self.assertRaises(ValueError):rt.workspace_authority(scope)



    def _identity_observer(self, events, *, mutate=None):
        original=b.workspace_validator
        def load(validate_raw,policy_raw):
            d=original(validate_raw,policy_raw)
            d._run_policy=lambda *_: (_ for _ in ()).throw(AssertionError('control path executed all-format policy'))
            d.verify_workspace_receipt=lambda *_: (_ for _ in ()).throw(AssertionError('control path used numeric API'))
            d._memory_modules=lambda *_: (_ for _ in ()).throw(AssertionError('control path executed full math'))
            identity=d.verify_workspace_receipt_identity
            parse_json=d._json
            blocked=set()
            def small_json(raw):
                if raw in blocked:
                    raise AssertionError('control path parsed a typed decision input')
                return parse_json(raw)
            d._json=small_json
            def checked(bundle,receipt_raw,expected_sha):
                blocked.update(raw for name,raw in bundle.items()
                               if name.endswith('.json') and name!='source/config.json')
                evidence=identity(bundle,receipt_raw,expected_sha)
                events.append({'identity_keys':sorted(evidence),'current_inputs':len(bundle),
                               'policy_bytes':len(bundle['source/decision_schema.py'])})
                return mutate(evidence) if mutate else evidence
            d.verify_workspace_receipt_identity=checked
            return d
        return load

    def test_control_context_identity_only_no_policy_or_typed_parse(self):
        events=[]
        with patch.object(b,'workspace_validator',self._identity_observer(events)):
            first=self.ctx();second=self.ctx()
        self.assertIsNot(first,second)
        self.assertEqual(first.decision_inputs,second.decision_inputs)
        self.assertEqual(len(events),2)
        self.assertTrue(all(r['current_inputs']==48 for r in events))
        self.assertTrue(all(r['identity_keys']==['inputs_sha256','receipt_sha256','scope','unit'] for r in events))

    def test_control_verify_and_authority_are_fresh_identity_only(self):
        root=fixture(self.batch/'identity-runtime');ctx=b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10,require_native=True)
        l=lease(ctx);claim=b.claim_path(root);claim.parent.mkdir(parents=True,exist_ok=True)
        claim.write_bytes(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
        b.activate(ctx,l);rt=b.Runtime(root,1,self.helper,l,native_authorized=True);events=[]
        with rt.phase(10),patch.object(b,'workspace_validator',self._identity_observer(events)):
            rt.verify();rt.verify();scope=rt.workspace_scope();authority=rt.workspace_authority(scope)
        self.assertEqual(len(events),3)
        self.assertEqual(authority['unit'],'116')
        self.assertEqual(len(authority['decision_inputs']),48)
        self.assertEqual(set(authority),{'schema_version','unit','receipt_raw','receipt_sha256',
                         'template_config_raw','active_config_raw','decision_inputs'})

    def test_context_requires_exact_current_closed4_identity_evidence(self):
        changes=[lambda _:None,lambda e:dict(e,data={}),lambda e:dict(e,unit='113'),
                 lambda e:dict(e,scope='PURE_WORKSPACE_PREFLIGHT_NOT_NATIVE_AUTHORITY'),
                 lambda e:dict(e,receipt_sha256='0'*64),lambda e:dict(e,inputs_sha256='0'*64),
                 lambda e:{k:v for k,v in e.items() if k!='scope'}]
        for index,change in enumerate(changes):
            events=[]
            with self.subTest(index=index),patch.object(b,'workspace_validator',self._identity_observer(events,mutate=change)):
                with self.assertRaisesRegex(ValueError,'closed current-input identity evidence only'):
                    self.ctx()
            self.assertEqual(len(events),1)

    def test_identity_control_rechecks_current_source_model_and_ref(self):
        root=fixture(self.batch/'current-identity');ctx=b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10,require_native=True)
        l=lease(ctx);claim=b.claim_path(root);claim.parent.mkdir(parents=True,exist_ok=True)
        claim.write_bytes(b.canonical({k:v for k,v in l.items() if k!='claim_sha256'}))
        b.activate(ctx,l);rt=b.Runtime(root,1,self.helper,l,native_authorized=True)
        paths=[root/b.SRC/'decision_schema.py',root/'models/robot-arm-urdf-v3/robot_arm.urdf',
               root/ctx.template_config['refs']['workspace.json']['path']]
        events=[]
        with rt.phase(10),patch.object(b,'workspace_validator',self._identity_observer(events)):
            scope=rt.workspace_scope();rt.workspace_authority(scope)
            for path in paths:
                raw=path.read_bytes()
                try:
                    path.write_bytes(raw+b'\n')
                    with self.subTest(path=path.name),self.assertRaises(ValueError):
                        rt.workspace_authority(scope)
                finally:path.write_bytes(raw)
            rt.workspace_authority(scope)
        self.assertEqual(len(events),2)

    def test_review_rejects_old12_old113_and_missing_performance(self):
        ctx=self.ctx();review=ctx.review
        variants=[dict(review,unit='113'),dict(review,met=12),dict(review,criteria=review['criteria'][:-2]),
                  dict(review,unit_dispositions={k:v for k,v in review['unit_dispositions'].items() if k!='performance'})]
        for field,value in (('verdict','BLOCK'),('unresolved_count',1),('unresolved_count',False)):
            units={k:dict(v) for k,v in review['unit_dispositions'].items()};units['performance'][field]=value
            variants.append(dict(review,unit_dispositions=units))
        for index,item in enumerate(variants):
            with self.subTest(index=index),self.assertRaises(ValueError):
                b.review_gate(item,1,ctx.pins['template_freeze_sha256'])

    def test_native_gate_rejects_old113_scope_and_wrong_closed_shape(self):
        ctx=self.ctx();approval=b.read(self.root/b.OUT/'native-approval.json')
        b.native_gate(approval,ctx.pins)
        for change in ({'unit':'113'},{'scope':'113_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S'},
                       {'duration_s':True},{'extra':'native'},{'native_limits':{'import':True,'render_smoke':1,'motion':1}}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                b.native_gate(dict(approval,**change),ctx.pins)




    def test_actual_context_bridge_inside_original_owner(self):
        checks=[];original=b.scene_reference_binding
        def checked(raw,old_sha):
            checks.append(any(t.is_alive() and t.name.startswith('Thread-') for t in threading.enumerate()))
            return original(raw,old_sha)
        with patch.object(b,'scene_reference_binding',checked):self.ctx()
        self.assertEqual(checks,[True])

    def test_actual_context_rejects_reference_physical_change_even_repin(self):
        root=fixture(self.batch/'scene-physical-change');out=root/b.OUT
        scene=root/b.SRC/'scene.py';scene.write_bytes(scene.read_bytes()+b'\nUNREVIEWED_PHYSICAL_GLOBAL=1\n')
        freeze=b.read(out/'source-freeze-r1.json');freeze['source']['scene.py']=b.digest(scene.read_bytes())
        fr=b.canonical(freeze);(out/'source-freeze-r1.json').write_bytes(fr)
        review=b.read(out/'review/L4-r1.json');review['actual_freeze_sha256']=b.digest(fr)
        (out/'review/L4-r1.json').write_bytes(b.canonical(review))
        with patch.object(b,'workspace_validator',side_effect=AssertionError('numeric before physical proof')):
            with self.assertRaisesRegex(ValueError,'physical scene module projection'):
                b.context(root,1,helper=self.helper,owner_end=time.monotonic()+10)

    def test_actual_context_reference_parse_stall_keeps_owner_deadline(self):
        folder=self.batch/'bridge-parse-stall';root=fixture(folder)
        code=('import importlib.util,time;from pathlib import Path;'
              'p=Path('+repr(str(HERE/'bootstrap.py'))+');'
              's=importlib.util.spec_from_file_location("stall_b",p);'
              'b=importlib.util.module_from_spec(s);s.loader.exec_module(b);'
              'h=b.load_helper(Path('+repr(str(root))+'));'
              'b.ast.parse=lambda *a,**k:time.sleep(50);'
              'b.context(Path('+repr(str(root))+'),1,helper=h,owner_end=time.monotonic()+0.5)')
        start=time.monotonic()
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,timeout=4)
        (folder/'parse-stall-stdout.raw').write_bytes(result.stdout)
        (folder/'parse-stall-stderr.raw').write_bytes(result.stderr)
        (folder/'parse-stall-observation.json').write_bytes(b.canonical({'actual_exit':result.returncode,'elapsed_s':time.monotonic()-start,'owner_s':0.5,'policy_executions':0,'SDK':'NOT_RUN'}))
        self.assertEqual(result.returncode,124)
        self.assertLess(time.monotonic()-start,3)



class ReferenceBridge(unittest.TestCase):
    old_sha='f3b4e08491124ea3daf13949dc994618374c0be8cd6267f56ef7ac4789fd1807'

    def raw(self, statements=None, edit=None):
        tree=ast.parse((HERE/'scene.py').read_bytes())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='target_at')
        if statements is not None:fn.body=ast.parse(statements).body+fn.body
        if edit is not None:edit(tree,fn)
        return ast.unparse(ast.fix_missing_locations(tree)).encode()

    def denied(self, raw):
        with self.assertRaises((ValueError,SyntaxError)):
            b.scene_reference_binding(raw,self.old_sha)

    def test_original_and_actual_new_scene_positive(self):
        old=(ROOT/'src/simulation/clock_ready_resume_108/scene.py').read_bytes()
        self.assertEqual(b.digest(old),self.old_sha)
        self.assertTrue(b.scene_reference_binding(old,self.old_sha))
        self.assertTrue(b.scene_reference_binding((HERE/'scene.py').read_bytes(),self.old_sha))
        self.assertTrue(b.scene_reference_binding(self.raw(),self.old_sha))

    def test_physical_import_global_and_helper_changes_denied(self):
        for statement in ('import os','NEW_PHYSICAL_VALUE=1','def added_helper():\n return 1'):
            self.denied(self.raw(edit=lambda tree,fn,s=statement:tree.body.extend(ast.parse(s).body)))
        def change(tree,fn):
            other=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name not in ('target_at','validate_program'))
            other.body.insert(0,ast.Expr(ast.Constant('physical change')))
        self.denied(self.raw(edit=change))

    def test_duplicate_missing_and_async_denied(self):
        self.denied(self.raw(edit=lambda tree,fn:tree.body.append(fn)))
        self.denied(self.raw(edit=lambda tree,fn:tree.body.remove(fn)))
        self.denied(self.raw().replace(b'def target_at(',b'async def target_at(',1))

    def test_defaults_decorators_annotations_and_argument_changes_denied(self):
        edits=[lambda t,f:f.args.defaults.append(ast.Constant(0)),
               lambda t,f:f.decorator_list.append(ast.Name('binary32',ast.Load())),
               lambda t,f:setattr(f.args.args[0],'annotation',ast.Name('dict',ast.Load())),
               lambda t,f:setattr(f,'returns',ast.Name('dict',ast.Load())),
               lambda t,f:setattr(f.args,'vararg',ast.arg('extra')),
               lambda t,f:setattr(f.args.args[0],'arg','different')]
        for edit in edits:self.denied(self.raw(edit=edit))

    def test_io_import_eval_and_free_globals_denied(self):
        for s in ('open("x")','import os','eval("1")','exec("pass")','x=GLOBALS',
                  '__import__("os")','global external','x=math.pi'):
            self.denied(self.raw(s))

    def test_input_store_and_mutating_methods_denied(self):
        for s in ('program={}','time_s=0','program["x"]=1','program.update(x=1)',
                  'program.clear()','x=program; x.pop("x")'):
            self.denied(self.raw(s))

    def test_protected_names_callable_alias_and_callbacks_denied(self):
        for s in ('type=1','math={}','binary32=1','need=1','x=binary32; x(1)',
                  'x=program.get("callback"); x()','program.get("callback")()'):
            self.denied(self.raw(s))

    def test_local_dict_alias_and_nonlocal_store_denied(self):
        for s in ('q=program','velocity=dict(program)','maximum=program',
                  'x=program; x["a"]=1','for q in program:\n pass'):
            self.denied(self.raw(s))

    def test_type_construction_starargs_keywords_and_attributes_denied(self):
        for s in ('x=type("X",(),{})','x=type(program).__dict__','x=type(*program)',
                  'x=max(program,key=float)','q={}; q.update(other=1)',
                  'q={}; q.update(program)','x=math.sqrt(1,2)','x=math.sin(1)'):
            self.denied(self.raw(s))

    def test_closed_statement_and_expression_denials(self):
        for s in ('while True:\n break','try:\n x=1\nexcept:\n x=2',
                  'def nested():\n return 1','x=lambda:1','x: int=1','time_s+=1',
                  'del program["x"]','x=(y:=1)','with program:\n x=1'):
            self.denied(self.raw(s))

    def test_original_provenance_version_and_no_contract_io(self):
        raw=(HERE/'scene.py').read_bytes()
        with self.assertRaises(ValueError):b.scene_reference_binding(raw,'0'*64)
        with patch.object(b.sys,'version_info',(3,11)):
            with self.assertRaises(ValueError):b.scene_reference_binding(raw,self.old_sha)
        with patch.object(b.Path,'read_bytes',side_effect=AssertionError('bridge contract I/O')):
            self.assertTrue(b.scene_reference_binding(raw,self.old_sha))


if __name__=='__main__':unittest.main(verbosity=2)
