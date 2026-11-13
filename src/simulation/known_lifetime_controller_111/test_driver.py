"""111 C HOST tests. Authority service and bootstrap bytes are explicit fixtures.
The exact immutable Win32 helper owns actual non-admin child/blocked IO tests.
No SSH, SDK, native approval, production budget, or hardware is used.
"""
from pathlib import Path
import ast
import builtins
import contextlib
import ctypes
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import types
import unittest
import uuid

SRC=Path(__file__).absolute().parent
REPO=SRC.parents[2]
OUT=REPO/'outputs/known-lifetime-controller-111'
FIX=OUT/'C-fixtures'


def module(path,name='C111fixture'):
    value=types.ModuleType(name);value.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),value.__dict__)
    return value


def fixture():
    p=FIX/uuid.uuid4().hex;p.mkdir(parents=True);return p


class ActiveConfig(dict):pass


class RuntimeFixture:
    """Declared authority seam; phase/IO/process behavior is real helper code."""
    unit='111';native_authorized=True;hardware_approved=False;round_number=1
    def __init__(self,api,p,root=None,lifetime=60):
        self.api=api;self.root=p if root is None else root;self.src=self.root/'src/simulation/known_lifetime_controller_111';self.out=self.root/api.OUT
        self.helper_bytes=(REPO/'src/simulation/single_host_controller_110/winjob.py').read_bytes()
        self.helper=api.load_module('actual_A111_fixture_'+uuid.uuid4().hex,self.helper_bytes,REPO/'src/simulation/single_host_controller_110/winjob.py')
        now=time.monotonic();wall=time.time();self.end_monotonic=now+lifetime
        self.budget={'unit':'111','duration_s':2700,'started_unix':wall+lifetime-2700,'started_monotonic':now+lifetime-2700,
                     'deadline_unix':wall+lifetime,'hardware_approved':False,'plan_sha256':api.PLAN_SHA,'execution_source':{}}
        self.budget_path=p/'fixture-runtime-budget.json';self.budget_path.write_text(json.dumps(self.budget),encoding='utf8')
        self.lease={};self.local=threading.local();self.verify_count=0;self.omit_owner=False;self.last_code=[]
    @contextlib.contextmanager
    def phase(self,limit=None):
        stack=getattr(self.local,'stack',[]);end=min(self.end_monotonic,stack[-1] if stack else self.end_monotonic)
        if limit is not None:end=min(end,time.monotonic()+limit)
        self.api.need(end>time.monotonic(),'Expired fixture owner')
        stack.append(end);self.local.stack=stack
        try:
            if self.omit_owner:yield end
            else:
                with self.helper.Fence(end):yield end
        finally:stack.pop()
    def verify(self):
        self.api.need(bool(getattr(self.local,'stack',[])),'Fixture verify requires armed phase')
        self.verify_count+=1
        return self.api.read(self.budget_path)
    def save(self):self.budget_path.write_text(json.dumps(self.budget),encoding='utf8')
    def bind_config(self,cfg):
        out=ActiveConfig(cfg);out.runtime=self;return out
    def bind(self,ctx):ctx.runtime=self;ctx.cfg=self.bind_config(ctx.cfg);return ctx
    def entry_code(self,ctx,role):
        self.last_code.append((ctx,role))
        return "print('DECLARED_LITERAL_SERVICE_SEAM')"


def cfg_for(api,rt):
    cfg=api.read(SRC/'config.json');cfg['deadline_unix']=rt.budget['deadline_unix'];return rt.bind_config(cfg)


def ctx_for(api,rt,p):
    raw=rt.helper_bytes;pin=api.digest(raw)
    return rt.bind(types.SimpleNamespace(run=p,job_hash='a'*64,job={'inputs':{'source/winjob.py':pin}},cfg={'winjob_sha256':pin},data={'source/winjob.py':raw}))


def pipe_block(label):
    read_fd,write_fd=os.pipe()
    print(label,flush=True)
    with os.fdopen(read_fd,'rb',buffering=0) as stream:stream.read(1)
    os.close(write_fd)
    raise AssertionError('blocked fixture unexpectedly continued')


def recovery_case(api,rt,p):
    cfg=cfg_for(api,rt);run_id=uuid.uuid4().hex;remote=p/'worker'/run_id;local=p/'controller'/run_id
    (remote/'input/source').mkdir(parents=True);local.mkdir(parents=True);output=remote/'output';output.mkdir()
    raw=(REPO/'src/simulation/clock_ready_resume_108/recovery.py').read_bytes()
    data={'source/driver.py':(SRC/'driver.py').read_bytes(),'source/recovery.py':raw,
          'source/config.json':json.dumps({'hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN','sdk':{'hardware_approved':False,'calibration_approved':False}}).encode()}
    for name,value in data.items():(remote/'input'/name).write_bytes(value)
    job={'schema_version':1,'run_id':run_id,'purpose':'import','inputs':{k:api.digest(v) for k,v in data.items()},'common_signature':'a'*64,
         'plan_sha256':api.PLAN_SHA,'hardware_approved':False,'experiment_id':api.EXPERIMENT}
    api.write(remote/'job.json',job);job_hash=api.sha(remote/'job.json')
    ex={'run_id':run_id,'job_sha256':job_hash,'purpose':'import','pid':os.getpid(),'child_pid':None,'actual_child_exit_code':None,
        'policy_exit_code':1,'child_state':'NOT_STARTED','timed_out':False}
    api.finalize_parent(output,job,job_hash,ex,None,remote/'unused-lock')
    api.write(output/'remote-shell.json',{'run_id':run_id,'job_sha256':job_hash,'python_exit_code':1})
    api.write(local/'transport.json',{'returncode':1,'timed_out':False,'transport_kind':'LOCAL_PROCESS'})
    recovery=api.load_module('fixture_recovery',raw,remote/'input/source/recovery.py')
    def export(*a,**k):
        recovery.export_closed(remote,job_hash,job['inputs']['source/driver.py'],remote)
        return types.SimpleNamespace(returncode=0)
    api.remote=export
    ctx=rt.bind(types.SimpleNamespace(run=local,cfg=cfg,job=job,job_hash=job_hash,data=data))
    remctx=rt.bind(types.SimpleNamespace(run=remote,cfg=cfg,job=job,job_hash=job_hash,data=data))
    return ctx,remctx,remote


def subject(p,mode):
    api=module(SRC/'driver.py');rt=RuntimeFixture(api,p,lifetime=1.2)
    if mode in ('budget','no_owner'):
        ctx,remctx,remote=recovery_case(api,rt,p);original=api.read
        def blocked(path):
            if Path(path)==rt.budget_path:return pipe_block('BUDGET_READ_ENTERED')
            return original(path)
        api.read=blocked;rt.omit_owner=mode=='no_owner'
        return api.recover_transport(ctx,remctx,sys.executable,str(remote),ctx.cfg['ssh_alias'])
    if mode=='config':
        folder=rt.src;folder.mkdir(parents=True);(folder/'config.json').write_bytes((SRC/'config.json').read_bytes());original=api.read
        def blocked(path):
            if Path(path)==folder/'config.json':return pipe_block('CONFIG_READ_ENTERED')
            return original(path)
        api.read=blocked;return api.public('run',str(p/'absent'),runtime=rt)
    if mode in ('copy','extract'):
        source=p/'payload.bin';source.write_bytes(b'fixture');destination=p/'destination';destination.mkdir();original=Path.read_bytes
        def blocked(path):
            if path==source:return pipe_block('BODY_READ_ENTERED')
            return original(path)
        Path.read_bytes=blocked
        if mode=='copy':return api._copy_new(source,destination/'new',runtime=rt)
        return api._extract_local(source,destination,api.digest(b'fixture'),runtime=rt)
    if mode=='publication':
        original=Path.open
        def blocked(path,*a,**k):
            if path==p/'validation.json':return pipe_block('PUBLICATION_ENTERED')
            return original(path,*a,**k)
        Path.open=blocked;return api.publish_validation(p,{'status':'HOST'},runtime=rt)
    raise ValueError(mode)


class DriverTests(unittest.TestCase):
    def setUp(self):self.api=module(SRC/'driver.py');self.p=fixture();self.rt=RuntimeFixture(self.api,self.p)
    def test_missing_runtime_rejected_before_read(self):
        original=Path.read_bytes;seen=[]
        def reject(path):seen.append(path);raise AssertionError('unauthorized read')
        Path.read_bytes=reject
        try:
            for action in (lambda:self.api.public('run'),lambda:self.api.entry('x','a'*64,'b'*64,'native'),lambda:self.api.snapshot('x','a'*64),lambda:self.api.prepare({},'import')):
                with self.assertRaises(TypeError):action()
            self.rt.native_authorized=False
            with self.assertRaisesRegex(ValueError,'Authorized'):self.api.public('run',runtime=self.rt)
        finally:Path.read_bytes=original
        self.assertEqual(seen,[])
    def test_expired_runtime_rejected_before_verify(self):
        self.rt.end_monotonic=time.monotonic()-1
        with self.assertRaisesRegex(ValueError,'runtime remains'):self.api.public('run',runtime=self.rt)
        self.assertEqual(self.rt.verify_count,0)
    def test_config_preserves_original_physics(self):
        old=self.api.read(REPO/'src/simulation/single_host_controller_110/config.json');new=self.api.read(SRC/'config.json')
        for key in ('experiment_id','remote_root','source_A'):old.pop(key);new.pop(key)
        self.assertEqual(old,new)
        self.api.config_contract(self.api.read(SRC/'config.json'))
    def test_exact_dict_before_bind_and_projection(self):
        cfg=self.api.read(SRC/'config.json');self.api.config_contract(cfg);bound=self.rt.bind_config(cfg)
        with self.assertRaises(ValueError):self.api.config_contract(bound)
        self.api.config_contract(dict(bound));bound['sdk']['hardware_approved']=True
        with self.assertRaises(ValueError):self.api.config_contract(dict(bound))
    def test_preserved_physical_consumer_ast(self):
        old=ast.parse((REPO/'src/simulation/single_host_controller_110/driver.py').read_text(encoding='utf8'));new=ast.parse((SRC/'driver.py').read_text(encoding='utf8'))
        names=('clock_bounds','effective_clock','phase_limits','recovery_limits','recovery_deadline','recovery_timeout','process_contract','verify_import_proof','verify_retry','verify_smoke_proof','reserve','verify_parent_recovery')
        a={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)};b={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
        for name in names:
            a[name].decorator_list=[];b[name].decorator_list=[]
            self.assertEqual(ast.dump(a[name]),ast.dump(b[name]),name)
    def test_session_uses_verified_budget_and_original_clock_gate(self):
        cfg=cfg_for(self.api,self.rt);self.assertAlmostEqual(self.api.session_now(cfg),time.time(),delta=.05)
        self.assertEqual(self.rt.verify_count,1);self.rt.budget['started_unix']+=1;self.rt.budget['deadline_unix']+=1;self.rt.save();cfg['deadline_unix']+=1
        with self.assertRaisesRegex(ValueError,'uncertainty'):self.api.session_now(cfg)
    def test_memory_helper_and_wrong_snapshot_pin(self):
        ctx=ctx_for(self.api,self.rt,self.p);self.assertIs(self.api._job_helper(ctx),self.rt.helper)
        ctx.job['inputs']['source/winjob.py']='0'*64
        with self.assertRaises(ValueError):self.api._job_helper(ctx)
    def test_literal_delegates_runtime_role(self):
        ctx=ctx_for(self.api,self.rt,self.p)
        for role in ('supervise','native','export'):self.assertIn('SEAM',self.api.literal(ctx,role))
        self.assertEqual([v[1] for v in self.rt.last_code],['supervise','native','export'])
    def test_actual_C_entry_fifth_admission_before_sdk(self):
        ctx=ctx_for(self.api,self.rt,self.p);ctx.cfg['remote_root']=str(self.p.parent);ctx.cfg['deadline_unix']=time.time()+60
        self.api.snapshot=lambda *a,**k:ctx;seen=[];self.api.supervise=lambda c:seen.append(c.admission) or 0
        cert={'fifth':'sentinel'}
        self.assertEqual(self.api.entry(str(self.p),'a'*64,'b'*64,'supervise',cert,runtime=self.rt),0);self.assertEqual(seen,[cert])
        self.api.entry(str(self.p),'a'*64,'b'*64,'supervise',runtime=self.rt);self.assertIsNone(seen[-1])
        with self.assertRaises(AssertionError):self.assertEqual(seen[-1],cert)
    def test_controller_order_and_failstop(self):
        seen=[];self.api.own_source=lambda **k:{}
        def prepare(source,purpose,**k):seen.append(purpose);return self.p/purpose
        self.api.prepare=prepare;self.api.public=lambda role,run_dir,**k:1 if Path(run_dir).name=='render_smoke' else 0
        self.assertEqual(self.api.controller(self.rt),1);self.assertEqual(seen,['import','render_smoke'])
    def test_controller_all_three_gates(self):
        seen=[];self.api.own_source=lambda **k:{};self.api.prepare=lambda source,purpose,**k:self.p/purpose
        self.api.public=lambda role,run_dir,**k:seen.append(Path(run_dir).name) or 0
        self.assertEqual(self.api.controller(self.rt),0);self.assertEqual(seen,list(self.api.PURPOSES))
    def test_actual_copy_exclusive_and_pin(self):
        source=self.p/'source';source.write_bytes(b'closed bytes');destination=self.p/'new'
        value=self.api._copy_new(source,destination,self.api.sha(source),runtime=self.rt);self.assertEqual(value['sha256'],self.api.sha(destination))
        with self.assertRaises(ValueError):self.api._copy_new(source,destination,runtime=self.rt)
        with self.assertRaises(ValueError):self.api._copy_new(source,self.p/'wrong','0'*64,runtime=self.rt)
        self.assertFalse((self.p/'wrong').exists())
    def test_actual_extract_rejects_overwrite_and_traversal(self):
        import zipfile
        archive=self.p/'a.zip';destination=self.p/'dst';destination.mkdir()
        with zipfile.ZipFile(archive,'x') as z:z.writestr('safe/data',b'value')
        self.api._extract_local(archive,destination,self.api.sha(archive),runtime=self.rt)
        with self.assertRaises(FileExistsError):self.api._extract_local(archive,destination,self.api.sha(archive),runtime=self.rt)
        bad=self.p/'bad.zip'
        with zipfile.ZipFile(bad,'x') as z:z.writestr('../bad',b'value')
        with self.assertRaises(ValueError):self.api._extract_local(bad,destination,self.api.sha(bad),runtime=self.rt)
    def test_actual_helper_child_and_admission(self):
        ctx=ctx_for(self.api,self.rt,self.p);seen=[]
        result=self.api.run_child([sys.executable,'-I','-B','-c',"print('ACTUAL111_CHILD')"],self.p,5,lambda:seen.append(True),ctx)
        self.assertEqual(seen,[True]);self.assertEqual(result['child_state'],'REAPED');self.assertEqual(result['actual_child_exit_code'],0);self.assertIn(b'ACTUAL111_CHILD',(self.p/'stdout.txt').read_bytes())
    def test_explicit_not_created_is_not_started(self):
        ctx=ctx_for(self.api,self.rt,self.p)
        def reject():raise ValueError('admission denied')
        result=self.api.run_child([sys.executable,'-c',"print('must not run')"],self.p,5,reject,ctx)
        self.assertEqual(result['child_state'],'NOT_STARTED');self.assertIsNone(result['child_pid'])
    def test_actual_child_then_helper_exception_is_unknown(self):
        ctx=ctx_for(self.api,self.rt,self.p);original=self.rt.helper.run
        def fault(*a,**k):original(*a,**k);raise OSError('post actual child observation failure')
        self.rt.helper.run=fault
        result=self.api.run_child([sys.executable,'-I','-B','-c',"print('CHILD_BEFORE_UNKNOWN')"],self.p,5,ctx=ctx)
        self.assertEqual(result['child_state'],'UNKNOWN');self.assertIsNone(result['actual_child_exit_code']);self.assertIn(b'CHILD_BEFORE_UNKNOWN',(self.p/'stdout.txt').read_bytes())
    def clock(self,fault=False,decoy=False):
        cfg=cfg_for(self.api,self.rt);self.api.clock_argv=lambda c,n:[sys.executable,'-I','-S','-B','-c',self.api.clock_remote_code(n)]
        original=self.api.write
        def fail(path,value):
            if Path(path).name=='process.json':
                Path(path).write_text(json.dumps({'child_pid':7,'actual_child_exit_code':99}) if decoy else '{}',encoding='utf8')
                k=ctypes.WinDLL('kernel32',use_last_error=True)
                k.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p]
                k.CreateFileW.restype=ctypes.c_void_p;k.CloseHandle.argtypes=[ctypes.c_void_p];k.CloseHandle.restype=ctypes.c_int
                handle=k.CreateFileW(str(path),0x80000000,3,None,3,0,None)
                if handle in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
                try:
                    try:original(path,value)
                    except PermissionError as error:
                        (self.p/'actual-NTFS-publication-error.json').write_text(json.dumps({'type':type(error).__name__,'winerror':getattr(error,'winerror',None),'partial':Path(path).read_text(encoding='utf8')}),encoding='utf8')
                        raise
                    raise AssertionError('NTFS non-delete sharing should refuse replace')
                finally:k.CloseHandle(handle)
            return original(path,value)
        if fault:self.api.write=fail
        ctx=self.rt.bind(types.SimpleNamespace(run=self.p,cfg=cfg,job_hash='a'*64))
        if fault:
            with self.assertRaises(self.api.ClockChannelError) as caught:self.api.clock_probe(ctx)
            value=self.api.read(self.p/'clock-query.json');self.assertEqual(caught.exception.returncode,0)
            self.assertGreater(value['process']['child_pid'],7);self.assertEqual(value['process']['actual_child_exit_code'],0);self.assertTrue(value['process']['terminal'])
            self.assertFalse(value['raw_complete']);self.assertFalse(value['query_record_complete']);self.assertTrue((self.p/'clock-query-failure.json').is_file())
        else:
            cert=self.api.clock_probe(ctx);self.api.clock_bounds(cert);self.assertEqual(cert['run_id'],self.p.name)
    def test_actual_clock_positive(self):self.clock()
    def test_clock_known_facts_survive_partial_publication(self):self.clock(True)
    def test_clock_known_facts_survive_decoy_publication(self):self.clock(True,True)
    def test_actual_recovery_positive(self):
        ctx,remctx,remote=recovery_case(self.api,self.rt,self.p)
        self.api.recover_transport(ctx,remctx,sys.executable,str(remote),ctx.cfg['ssh_alias'])
        self.assertTrue((ctx.run/'retrieved/exit.json').is_file());self.assertEqual(self.api.read(ctx.run/'recovery-status.json')['status'],'CLOSED_ARTIFACT_COPY_VERIFIED_NOT_PHYSICS_ACCEPTANCE')
    def test_actual_blocked_budget_config_copy_extract_publication_prefixes(self):
        for mode,marker in (('budget',b'BUDGET_READ_ENTERED'),('config',b'CONFIG_READ_ENTERED'),('copy',b'BODY_READ_ENTERED'),('extract',b'BODY_READ_ENTERED'),('publication',b'PUBLICATION_ENTERED')):
            with self.subTest(mode=mode):
                p=fixture();started=time.monotonic();child=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(__file__),'--subject',str(p),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
                stdout,stderr=child.communicate(timeout=4);(p/'observer.json').write_text(json.dumps({'mode':mode,'returncode':child.returncode,'elapsed_s':time.monotonic()-started,'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace')}),encoding='utf8')
                self.assertEqual(child.returncode,124,(stdout,stderr));self.assertIn(marker,stdout);self.assertLess(time.monotonic()-started,2.5)
    def test_omitted_owner_mutation_outlives_original_end(self):
        p=fixture();child=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(__file__),'--subject',str(p),'no_owner'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
        try:
            with self.assertRaises(subprocess.TimeoutExpired):child.communicate(timeout=1.7)
        finally:
            child.terminate();stdout,stderr=child.communicate(timeout=3)
            (p/'mutation-observer.json').write_text(json.dumps({'terminated_own_child':True,'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace')}),encoding='utf8')
        self.assertIn(b'BUDGET_READ_ENTERED',stdout)
    def test_cli_status_and_controller_denial(self):
        cli=module(OUT/'execute.py');output=io.StringIO()
        with contextlib.redirect_stdout(output):self.assertEqual(cli.main([]),0);self.assertEqual(cli.main(['--controller']),2)
        self.assertIn('STANDALONE_CONTROLLER_DENIED',output.getvalue())

    def test_actual_runtime20_prepare_snapshot_and_mismatch(self):
        # Repository-shaped fixture captures current actual B bytes; authority service remains synthetic.
        census=self.api.read(OUT/'dependency-census.json')
        for item in census['records']:
            target=self.p/item['target_path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((REPO/item['source_path']).read_bytes())
        folder=self.p/'src/simulation/known_lifetime_controller_111';folder.mkdir(parents=True,exist_ok=True)
        for name in ('driver.py','config.json'):(folder/name).write_bytes((SRC/name).read_bytes())
        (folder/'bootstrap.py').write_bytes((SRC/'bootstrap.py').read_bytes())
        cfg=self.api.read(folder/'config.json');cfg['deadline_unix']=self.rt.budget['deadline_unix'];(folder/'config.json').write_text(json.dumps(cfg),encoding='utf8')
        source={n:(self.p/'src/simulation/clock_ready_resume_108'/n).read_bytes() for n in cfg['immutable_source_pins']}
        source.update({n:(folder/n).read_bytes() for n in ('driver.py','config.json','bootstrap.py')});source['winjob.py']=self.rt.helper_bytes
        self.rt.budget['execution_source']={n:self.api.digest(b) for n,b in source.items()};self.rt.save()
        # The global fixture lifetime remains a full native preparation interval.
        delta=2700-60;self.rt.end_monotonic+=delta
        for key in ('started_unix','started_monotonic','deadline_unix'):self.rt.budget[key]+=delta
        cfg['deadline_unix']=self.rt.budget['deadline_unix'];(folder/'config.json').write_text(json.dumps(cfg),encoding='utf8');source['config.json']=(folder/'config.json').read_bytes();self.rt.budget['execution_source']['config.json']=self.api.digest(source['config.json']);self.rt.save()
        composed=self.api.own_source(runtime=self.rt);self.assertEqual(set(composed),self.api.SOURCE);self.assertEqual(len(composed),20)
        run=self.api.prepare(composed,'import',runtime=self.rt);prepared=self.api.read(run/'prepared.json');ctx=self.api.snapshot(run,prepared['job_sha256'],runtime=self.rt)
        self.assertIs(ctx.runtime,self.rt);self.assertIs(ctx.cfg.runtime,self.rt);self.assertEqual(ctx.job['purpose'],'import')
        self.assertTrue(run.is_relative_to(self.p));self.rt.budget['execution_source']['bootstrap.py']='0'*64;self.rt.save()
        with self.assertRaisesRegex(ValueError,'source20'):self.api.snapshot(run,prepared['job_sha256'],runtime=self.rt)

    def test_actual_B_literal_inline_owner_and_fifth_consumer(self):
        B=module(SRC/'bootstrap.py','B_actual_inline');helper=self.rt.helper;helper.__source_bytes__=self.rt.helper_bytes
        source=self.p/'input/source';source.mkdir(parents=True)
        for name in ('bootstrap.py','driver.py'):(source/name).write_bytes((SRC/name).read_bytes())
        now=time.monotonic();wall=time.time();end=self.rt.end_monotonic
        lease={k:'a'*64 for k in B.LEASE_KEYS if k.endswith('_sha256')}
        lease.update(schema_version=1,unit='111',nonce=self.p.name,client_started_monotonic=now,client_deadline_monotonic=now+2700,
                     remote_started_monotonic=end-2700,remote_deadline_monotonic=end,remote_started_unix=wall-2640,remote_deadline_unix=wall+60,
                     handshake_deduction_s=20,plan_sha256=B.PLAN_SHA,helper_sha256=B.HELPER_SHA,bootstrap_sha256=B.digest((source/'bootstrap.py').read_bytes()))
        lease['claim_sha256']=B.digest(B.canonical({k:v for k,v in lease.items() if k!='claim_sha256'}))
        actual=B.Runtime(self.p,1,helper,lease,native_authorized=True)
        pins={n:self.api.sha(source/n) for n in ('bootstrap.py','driver.py')};self.rt.budget['execution_source']=pins;self.rt.save()
        cert={'fifth':'INLINE_ACTUAL'};ctx=types.SimpleNamespace(run=self.p,job_hash='a'*64,job={'inputs':{'source/'+n:v for n,v in pins.items()}},admission=cert,runtime=actual)
        seen=[];lengths=[]
        original_module=B.module
        def loaded(raw,path,name):
            value=original_module(raw,path,name);entry=value.entry
            value.snapshot=lambda *a,**k:self.rt.bind(types.SimpleNamespace(run=self.p,cfg={'remote_root':str(self.p.parent)}))
            value.supervise=lambda ctx:0
            def called(*args,**kwargs):
                seen.append((args[3],args[4],len(args),kwargs['runtime']))
                return entry(*args,**kwargs) if args[3]=='supervise' else 0
            value.entry=called;return value
        for role in ('supervise','export'):
            code=self.api.literal(ctx,role);length=len(subprocess.list2cmdline([sys.executable,'-I','-B','-c',code]));lengths.append({'role':role,'characters':length});self.assertLess(length,8000)
            env={}
            def intercepted(code,namespace=None):
                namespace=env if namespace is None else namespace;builtins.exec(code,namespace)
                if namespace.get('__name__')=='_child111':namespace['Runtime']=lambda *a,**k:self.rt;namespace['module']=loaded
            env['__builtins__']=dict(vars(builtins),exec=intercepted)
            with self.assertRaises(SystemExit) as caught:builtins.exec(code,env)
            self.assertEqual(caught.exception.code,0)
        self.assertEqual(seen[0][:3],('supervise',cert,5));self.assertEqual(seen[1][:3],('export',None,5));self.assertTrue(all(v[3] is self.rt for v in seen))
        (self.p/'actual-command-lengths.json').write_text(json.dumps(lengths),encoding='utf8')
    def test_actual_remote_powershell_file_child_and_short_argv(self):
        self.rt.src.mkdir(parents=True);cfg=cfg_for(self.api,self.rt);(self.rt.src/'config.json').write_text(json.dumps(cfg),encoding='utf8')
        actual=[];original=self.rt.helper.run
        def traced(argv,*args,**kwargs):actual.append(list(argv));return original(argv,*args,**kwargs)
        self.rt.helper.run=traced
        result=self.api.remote("Write-Output 'ACTUAL_C111_LOCAL_PS';exit 7",cfg['ssh_alias'],8,runtime=self.rt)
        self.assertEqual(result.returncode,7);self.assertIn(b'ACTUAL_C111_LOCAL_PS',result.stdout);self.assertTrue(result.record['terminal'])
        files=list((self.rt.root/self.api.OUT/'local-transport').glob('*/command.ps1'));self.assertEqual(len(files),1)
        self.assertEqual(len(actual),1);self.assertIn('-Command',actual[0]);self.assertNotIn('-EncodedCommand',actual[0]);length=len(subprocess.list2cmdline(actual[0]));self.assertLess(length,8000)
        (self.p/'actual-PS-command.json').write_text(json.dumps({'argv':actual[0],'characters':length,'script_sha256':self.api.sha(files[0]),'exit':result.returncode}),encoding='utf8')

    def test_actual_B_child_entry_to_C_fifth_admission_and_mutation(self):
        B=module(SRC/'bootstrap.py','fixture_B_actual');B.Runtime=types.SimpleNamespace
        # Real _child_entry code with authority service constructor seam, real C byte load.
        self.rt.budget['execution_source']={'driver.py':self.api.sha(SRC/'driver.py')};self.rt.save()
        B.Runtime=lambda *a,**k:self.rt;seen=[];original=B.module
        def loaded(raw,path,name):
            value=original(raw,path,name)
            value.snapshot=lambda *a,**k:self.rt.bind(types.SimpleNamespace(run=self.p,cfg={'remote_root':str(self.p.parent)}))
            value.supervise=lambda ctx:seen.append(ctx.admission) or 0
            return value
        B.module=loaded
        args={'root':str(self.p),'round_number':1,'lease':{},'driver':str(SRC/'driver.py'),'driver_sha':self.api.sha(SRC/'driver.py'),'role':'supervise','run':str(self.p),'job_hash':'a'*64,'admission':{'fifth':'ACTUAL_B_C'}}
        self.assertEqual(B._child_entry(args,self.rt.helper),0);self.assertEqual(seen[-1],args['admission'])
        tree=ast.parse((SRC/'bootstrap.py').read_text(encoding='utf8'));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_child_entry');changes=0
        for call in ast.walk(node):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='entry':
                self.assertEqual(len(call.args),5);call.args.pop();changes+=1
        self.assertEqual(changes,1);env=dict(B.__dict__);exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<four-argument-mutation>','exec'),env)
        self.assertEqual(env['_child_entry'](args,self.rt.helper),0);self.assertIsNone(seen[-1])
        with self.assertRaises(AssertionError):self.assertEqual(seen[-1],args['admission'])
    def test_execute_run_delegates_actual_B_gate_function(self):
        cli=module(OUT/'execute.py');seen=[]
        def intercepted(code,namespace):
            exec(code,namespace)
            namespace['run']=lambda root,round_number:seen.append((root,round_number)) or 7
        cli.exec=intercepted
        self.assertEqual(cli.main(['--run','--review-round','2']),7);self.assertEqual(seen,[(REPO,2)])

    def test_command_file_has_no_encodedcommand_expansion(self):
        tree=ast.parse((SRC/'driver.py').read_text(encoding='utf8'));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='remote')
        literals=[n.value for n in ast.walk(node) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
        self.assertIn('-Command',literals);self.assertTrue(any('ReadAllBytes' in v for v in literals) and any('SHA256' in v for v in literals));self.assertNotIn('-EncodedCommand',literals)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--subject':subject(Path(sys.argv[2]),sys.argv[3])
    else:unittest.main(verbosity=2)
