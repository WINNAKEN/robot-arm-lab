"""114 C HOST tests. Authority service and bootstrap bytes are explicit fixtures.
The exact immutable Win32 helper owns actual non-admin child/blocked IO tests.
No SSH, SDK, production native approval/budget, or hardware is used.
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
OUT=REPO/'outputs/control-identity-split-114'
FIX=OUT/'C-implementation'/'fixtures'


def module(path,name='C114fixture'):
    value=types.ModuleType(name);value.__file__=str(path)
    value.__source_bytes__=path.read_bytes()
    exec(compile(value.__source_bytes__,str(path),'exec'),value.__dict__)
    return value


def fixture():
    p=FIX/uuid.uuid4().hex;p.mkdir(parents=True);return p


class ActiveConfig(dict):pass


class RuntimeFixture:
    """Declared authority seam; phase/IO/process behavior is real helper code."""
    unit='114';native_authorized=True;hardware_approved=False;round_number=1
    def __init__(self,api,p,root=None,lifetime=60):
        self.api=api;self.root=p if root is None else root;self.src=self.root/'src/simulation/control_identity_split_114';self.out=self.root/api.OUT
        self.helper_bytes=(REPO/'src/simulation/single_host_controller_110/winjob.py').read_bytes()
        self.helper=api.load_module('actual_A114_fixture_'+uuid.uuid4().hex,self.helper_bytes,REPO/'src/simulation/single_host_controller_110/winjob.py')
        now=time.monotonic();wall=time.time();self.end_monotonic=now+lifetime
        self.budget={'unit':'114','duration_s':2700,'started_unix':wall+lifetime-2700,'started_monotonic':now+lifetime-2700,
                     'deadline_unix':wall+lifetime,'hardware_approved':False,'plan_sha256':api.PLAN_SHA,'execution_source':{}}
        self.budget_path=p/'fixture-runtime-budget.json';self.budget_path.write_text(json.dumps(self.budget),encoding='utf8')
        self.lease={};self.local=threading.local();self.verify_count=0;self.omit_owner=False;self.last_code=[];self.workspace_auth=None;self.authority_calls=0
    @contextlib.contextmanager
    def phase(self,limit=None):
        stack=getattr(self.local,'stack',[]);end=min(self.end_monotonic,stack[-1] if stack else self.end_monotonic)
        if limit is not None:end=min(end,time.monotonic()+limit)
        self.api.need(end>time.monotonic(),'Expired fixture owner')
        stack.append(end);self.local.stack=stack
        frames=getattr(self.local,'frames',[]);self.local.frames=frames;token=object()
        try:
            if self.omit_owner:
                frames.append((token,end));yield end
            else:
                with self.helper.Fence(end):
                    frames.append((token,end));yield end
        finally:
            if frames and frames[-1][0] is token:frames.pop()
            stack.pop()
    def workspace_scope(self):
        frames=getattr(self.local,'frames',[]);self.api.need(bool(frames),'Fixture original owner scope')
        token,end=frames[-1];return (self,threading.get_ident(),token,end)
    def require_workspace_scope(self,scope):
        self.api.need(type(scope) is tuple and len(scope)==4 and scope[0] is self and scope[1]==threading.get_ident()
                      and any(t is scope[2] and e==scope[3] for t,e in getattr(self.local,'frames',[]))
                      and time.monotonic()<scope[3],'Fixture original scope/thread/token/end')
    def workspace_authority(self,scope):
        self.require_workspace_scope(scope)
        with self.phase():
            self.verify();self.authority_calls+=1
            self.api.need(self.workspace_auth is not None,'Declared workspace authority fixture required')
            return self.workspace_auth() if callable(self.workspace_auth) else self.workspace_auth
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


def workspace_fixture(api,rt,p):
    """Actual source/data/D consumer, declared synthetic authority and receipt seam.

    This does not execute producer math or claim final review/native authority.
    """
    census=api.read(OUT/'dependency-census-pre-receipt.json')
    for item in census['records']:
        raw=(REPO/item['source_path']).read_bytes()
        api.need(api.digest(raw)==item['sha256'] and len(raw)==item['bytes'],'Fixture immutable census')
        target=p/item['target_path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    folder=rt.src;folder.mkdir(parents=True,exist_ok=True)
    for name in ('driver.py','config.json','bootstrap.py','validate.py','decision_schema.py'):(folder/name).write_bytes((SRC/name).read_bytes())
    template=(folder/'config.json').read_bytes();cfg=api.parse(template)
    B=module(folder/'bootstrap.py','B114_stamp_fixture')
    active=B.stamp(template,rt.budget['deadline_unix']);(folder/'config.json').write_bytes(active)
    source={n:(p/'src/simulation/clock_ready_resume_108'/n).read_bytes() for n in cfg['immutable_source_pins']}
    source.update({n:(folder/n).read_bytes() for n in ('driver.py','config.json','bootstrap.py','validate.py','decision_schema.py')});source['winjob.py']=rt.helper_bytes
    bundle={'source/'+n:raw for n,raw in source.items()};bundle['source/config.json']=template
    bundle.update({'model/'+n:raw for n,raw in api.file_bytes(p/cfg['model_dir']).items()})
    bundle.update({'ref/'+n:(p/item['path']).read_bytes() for n,item in cfg['refs'].items()})
    D=api.load_module('synthetic_receipt_D114',source['validate.py'],folder/'validate.py')
    D.bind_decision_schema(source['decision_schema.py'])
    policy=module(folder/'decision_schema.py','synthetic_policy114')
    numeric=policy.validate_decision_inputs(bundle)
    data=D._json(bundle['ref/workspace.json']);metrics=D._metrics(data);workspace_sha=D._digest(bundle['ref/workspace.json'])
    receipt=D._canonical({'schema_version':1,'unit':'114','scope':D._WORKSPACE_SCOPE,'inputs':D._input_pins(bundle),
        'algorithms':D._algorithm_pins(bundle),'full_sampling':True,'sample_count':8192,'path_state_count':6241,
        'workspace_sha256':workspace_sha,'metrics':metrics,'numeric_contract':numeric,'result_sha256':D._result_sha(workspace_sha,metrics,numeric)})
    rt.workspace_auth={'schema_version':1,'unit':'114','receipt_raw':receipt,'receipt_sha256':api.digest(receipt),
        'template_config_raw':template,'active_config_raw':active,'decision_inputs':D._input_pins(bundle)}
    rt.budget['execution_source']={n:api.digest(raw) for n,raw in source.items()};rt.save()
    run=p/api.OUT/'runs'/uuid.uuid4().hex
    payload=dict(bundle);payload['source/config.json']=active;payload['workspace-preflight.json']=receipt
    for name,raw in payload.items():
        target=run/'input'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    pins={n:api.digest(raw) for n,raw in payload.items()}
    job={'schema_version':1,'run_id':run.name,'purpose':'import','inputs':pins,'common_signature':api.common_signature(pins),
        'plan_sha256':api.PLAN_SHA,'hardware_approved':False,'experiment_id':api.EXPERIMENT}
    api.write(run/'job.json',job)
    ctx=api.snapshot(run,api.sha(run/'job.json'),runtime=rt)
    validator=api.load_module('workspace_D114',source['validate.py'],run/'input/source/validate.py')
    (p/'SYNTHETIC_HOST_FIXTURE_NOT_REVIEW.json').write_text(json.dumps({'unit':'114','native_authority':False,'producer_executed':False}),encoding='utf8')
    return ctx,validator,source


def actual_b_workspace(api,p,*,prepare=True):
    """Actual B activation/context/owners using synthetic HOST review/receipt only."""
    helper_module=module(SRC/'test_bootstrap.py','B114_fixture_builder')
    B=helper_module.b;root=helper_module.fixture(p/'actual-B',preserve_remote_root=True)
    helper=B.load_helper(root);authority=B.context(root,1,helper=helper,owner_end=time.monotonic()+30,require_native=True)
    lease=helper_module.lease(authority);claim=B.claim_path(root);claim.parent.mkdir(parents=True,exist_ok=True)
    claim.write_bytes(B.canonical({k:v for k,v in lease.items() if k!='claim_sha256'}))
    B.activate(authority,lease);runtime=B.Runtime(root,1,helper,lease,native_authorized=True)
    if not prepare:return B,runtime,None
    source=api.own_source(runtime=runtime);run=api.prepare(source,'import',runtime=runtime)
    ctx=api.snapshot(run,api.sha(run/'job.json'),runtime=runtime)
    (p/'SYNTHETIC_ACTIVATION_NOT_NATIVE.json').write_text(json.dumps({'B_context':'actual','receipt':'synthetic no producer math','transport':'NOT_RUN','SDK':'NOT_RUN'}),encoding='utf8')
    return B,runtime,ctx


def replay_stage(api,rt,base,purpose,previous=None):
    """Old111 physical bytes; synthetic current process/identity records for HOST.

    Original111 artifacts are read-only. This is not a new native observation.
    """
    payload={n:raw for n,raw in base.data.items() if n.startswith(('source/','model/','ref/')) or n=='workspace-preflight.json'}
    import_origin=REPO/'outputs/known-lifetime-controller-111/native-artifacts/runs/30377b7d96a2425eaf17c401de37386d'
    proof={n:(import_origin/'retrieved'/n).read_bytes() for n in api.PROOF-{'job.json'}}
    proof['job.json']=(base.run/'job.json').read_bytes()
    for name in ('terminal.json','exit.json','remote-shell.json'):
        row=api.parse(proof[name]);row.update(run_id=base.run.name,job_sha256=base.job_hash);proof[name]=json.dumps(row).encode()
    payload.update({'import-proof/'+n:raw for n,raw in proof.items()})
    if purpose=='motion':
        payload.update({'smoke-proof/'+n:raw for n,raw in api.file_bytes(previous.run/'retrieved').items()})
        payload['smoke-proof/job.json']=(previous.run/'job.json').read_bytes()
    run=rt.root/api.OUT/'runs'/uuid.uuid4().hex
    for name,raw in payload.items():
        target=run/'input'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    pins={n:api.digest(raw) for n,raw in payload.items()}
    job={'schema_version':1,'run_id':run.name,'purpose':purpose,'inputs':pins,'common_signature':api.common_signature(pins),
        'plan_sha256':api.PLAN_SHA,'hardware_approved':False,'experiment_id':api.EXPERIMENT}
    api.write(run/'job.json',job);job_hash=api.sha(run/'job.json')
    ctx=api.snapshot(run,job_hash,runtime=rt)
    if purpose=='render_smoke':
        origin=REPO/'outputs/known-lifetime-controller-111/native-artifacts/runs/b490bce18c954ab190a14fcba33a1285/retrieved'
        raw=api.file_bytes(origin)
        for name in ('terminal.json','exit.json','remote-shell.json','sdk.json','providers.json','report.json'):
            row=api.parse(raw[name]);row.update(run_id=run.name,job_sha256=job_hash);raw[name]=json.dumps(row).encode()
        terminal=api.parse(raw['terminal.json']);terminal['files_sha256']={n:api.digest(b) for n,b in raw.items() if n not in api.UNSEALED};raw['terminal.json']=json.dumps(terminal).encode()
        for name,value in raw.items():
            target=run/'retrieved'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
        api.write(run/'transport.json',{'transport_kind':'LOCAL_PROCESS','timed_out':False,'returncode':0,'scope':'SYNTHETIC_HOST_PROCESS_RECORD_SEAM_NOT_NEW_NATIVE'})
    return ctx


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
    if mode=='actual_control_clock_stall':
        B,rt,_=actual_b_workspace(api,p,prepare=False)
        run=rt.root/'HOST_LOCAL_OS_CLOCK_STALL_SEAM'/uuid.uuid4().hex;run.mkdir(parents=True)
        ctx=rt.bind(types.SimpleNamespace(run=run,job_hash='a'*64,cfg=api.read(rt.src/'config.json')))
        original=Path.read_bytes
        def blocked(path):
            if path==rt.src/'decision_schema.py':return pipe_block('CONTROL_CURRENT_POLICY_READ_ENTERED')
            return original(path)
        def unexpected(*args):print('UNEXPECTED_OS_ARGV',flush=True);raise AssertionError('OS argv must follow current authority')
        api.clock_argv=unexpected
        api.write(p/'actual-control-stall-start.json',{'started_monotonic':time.monotonic(),'original_clock_s':20,'scope':'HOST_CURRENT_INPUT_READ_STALL_NOT_TARGET_FAILURE'})
        Path.read_bytes=blocked
        return api.clock_probe(ctx)
    if mode=='workspace':
        rt=RuntimeFixture(api,p,lifetime=30)
        ctx,validator,source=workspace_fixture(api,rt,p)
        original=Path.read_bytes
        def blocked(path):
            if path==ctx.run/'input/model/robot_arm.urdf':return pipe_block('WORKSPACE_CURRENT_READ_ENTERED')
            return original(path)
        with rt.phase(.6):
            api._bind_workspace(ctx,validator);Path.read_bytes=blocked
            return validator.verify_workspace(ctx.run/'input/model/robot_arm.urdf')
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
        old=self.api.read(REPO/'src/simulation/typed_decision_preflight_113/config.json');new=self.api.read(SRC/'config.json')
        self.assertEqual({k for k in old if old[k]!=new[k]},{'experiment_id','remote_root'})
        self.assertEqual(new['source_B'],old['source_B'])
        self.assertEqual(set(old['source_B'])-set(new['source_B']),set())
        for key in ('experiment_id','remote_root'):old.pop(key);new.pop(key)
        self.assertEqual(old,new)
        self.api.config_contract(self.api.read(SRC/'config.json'))
    def test_old20_and_old112_contracts_rejected(self):
        cfg=self.api.read(SRC/'config.json')
        for changes in ({'experiment_id':'static_workspace_preflight_112'}, {'remote_root':cfg['remote_root'].replace('/114/','/112/')},
                        {'source_B':[n for n in cfg['source_B'] if n!='decision_schema.py']}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.api.config_contract(dict(cfg,**changes))
        source={n:b'closed HOST source bytes' for n in self.api.SOURCE-{'decision_schema.py'}}
        self.rt.budget['execution_source']={n:self.api.digest(raw) for n,raw in source.items()};self.rt.save()
        with self.assertRaisesRegex(ValueError,'source21'):self.api.prepare(source,'import',runtime=self.rt)
    def test_exact_dict_before_bind_and_projection(self):
        cfg=self.api.read(SRC/'config.json');self.api.config_contract(cfg);bound=self.rt.bind_config(cfg)
        with self.assertRaises(ValueError):self.api.config_contract(bound)
        self.api.config_contract(dict(bound));bound['sdk']['hardware_approved']=True
        with self.assertRaises(ValueError):self.api.config_contract(dict(bound))
    def test_preserved_physical_consumer_ast(self):
        old=ast.parse((REPO/'src/simulation/known_lifetime_controller_111/driver.py').read_text(encoding='utf8'));new=ast.parse((SRC/'driver.py').read_text(encoding='utf8'))
        names=('clock_bounds','effective_clock','phase_limits','recovery_limits','recovery_deadline','recovery_timeout','process_contract','verify_import_proof','verify_retry','verify_smoke_proof','reserve','verify_parent_recovery')
        a={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)};b={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
        for name in names:
            a[name].decorator_list=[];b[name].decorator_list=[]
            if name=='verify_smoke_proof':
                b[name].body=[n for n in b[name].body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_bind_workspace')]
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
    def test_truthful_motion_prelaunch_headroom_blocks_before_attempt_and_child(self):
        ctx=ctx_for(self.api,self.rt,self.p);ctx.cfg=cfg_for(self.api,self.rt);ctx.job['purpose']='motion';seen=[]
        self.api.remote=lambda *a,**k:seen.append('remote') or (_ for _ in ()).throw(AssertionError('prelaunch remote'))
        with self.assertRaisesRegex(ValueError,'Purpose launch headroom'):self.api.launch(ctx,{})
        self.assertEqual(seen,[]);self.assertFalse((self.p/'launch-attempt.json').exists())
        self.assertFalse((self.p.parent/'attempt-motion.json').exists());self.assertFalse((self.p/'clock-query.json').exists())
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
        result=self.api.run_child([sys.executable,'-I','-B','-c',"print('ACTUAL114_CHILD')"],self.p,5,lambda:seen.append(True),ctx)
        self.assertEqual(seen,[True]);self.assertEqual(result['child_state'],'REAPED');self.assertEqual(result['actual_child_exit_code'],0);self.assertIn(b'ACTUAL114_CHILD',(self.p/'stdout.txt').read_bytes())
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

    def test_actual_runtime21_prepare_snapshot_and_mismatch(self):
        self.rt=RuntimeFixture(self.api,self.p,lifetime=2700)
        original,validator,source=workspace_fixture(self.api,self.rt,self.p)
        composed=self.api.own_source(runtime=self.rt);self.assertEqual(set(composed),self.api.SOURCE);self.assertEqual(len(composed),21)
        run=self.api.prepare(composed,'import',runtime=self.rt);prepared=self.api.read(run/'prepared.json');ctx=self.api.snapshot(run,prepared['job_sha256'],runtime=self.rt)
        self.assertIs(ctx.runtime,self.rt);self.assertIs(ctx.cfg.runtime,self.rt);self.assertEqual(ctx.job['purpose'],'import')
        self.assertEqual(len(ctx.data),49);self.assertIn('workspace-preflight.json',ctx.data)
        changed=dict(ctx.job['inputs']);changed['workspace-preflight.json']='0'*64
        self.assertNotEqual(self.api.common_signature(changed),ctx.job['common_signature'])
        self.assertTrue(run.is_relative_to(self.p));self.rt.budget['execution_source']['bootstrap.py']='0'*64;self.rt.save()
        with self.assertRaisesRegex(ValueError,'source21'):self.api.snapshot(run,prepared['job_sha256'],runtime=self.rt)

    def test_workspace_actual_D_fresh_use_and_exact_template_projection(self):
        ctx,D,source=workspace_fixture(self.api,self.rt,self.p);seen=[];original=D.verify_workspace_receipt
        def checked(bundle,receipt,pin):
            seen.append((bundle['source/config.json'],receipt,pin));return original(bundle,receipt,pin)
        D.verify_workspace_receipt=checked
        with self.rt.phase():
            self.api._bind_workspace(ctx,D)
            first,metrics=D.verify_workspace(ctx.run/'input/model/robot_arm.urdf')
            first['status']='MUTATED_RESULT';metrics['samples']=-1
            second,other=D.verify_workspace(ctx.run/'input/model/robot_arm.urdf')
        self.assertEqual(self.rt.authority_calls,2);self.assertEqual(len(seen),2)
        self.assertNotEqual(second.get('status'),'MUTATED_RESULT');self.assertEqual(other['samples'],8192)
        self.assertEqual(seen[0][0],self.rt.workspace_auth['template_config_raw'])
        self.assertNotEqual(seen[0][0],ctx.data['source/config.json'])
        self.assertEqual(seen[0][1],ctx.data['workspace-preflight.json']);self.assertEqual(seen[0][2],self.api.digest(seen[0][1]))

    def test_workspace_policy_binding_and_actual_execution_order(self):
        ctx,D,source=workspace_fixture(self.api,self.rt,self.p);events=[]
        original_bind=D.bind_decision_schema;original_run=D._run_policy;original_authority=self.rt.workspace_authority
        def bind(raw):
            self.assertEqual(raw,ctx.data['source/decision_schema.py']);events.append('bind bytes');return original_bind(raw)
        def authority(scope):events.append('current B authority');return original_authority(scope)
        def run(bundle):
            self.assertEqual(events[-1],'current B authority');self.assertEqual(bundle['source/decision_schema.py'],source['decision_schema.py'])
            self.assertGreaterEqual(len(self.rt.local.stack),2);events.append('actual fresh policy');return original_run(bundle)
        D.bind_decision_schema=bind;D._run_policy=run;self.rt.workspace_authority=authority
        with self.rt.phase():
            self.api._bind_workspace(ctx,D);self.assertEqual(events,['bind bytes'])
            D.verify_workspace(ctx.run/'input/model/robot_arm.urdf');D.verify_workspace(ctx.run/'input/model/robot_arm.urdf')
        self.assertEqual(events,['bind bytes','current B authority','actual fresh policy','current B authority','actual fresh policy'])

    def test_workspace_second_use_current_job_entire_inventory_and_authority(self):
        ctx,D,source=workspace_fixture(self.api,self.rt,self.p);model=ctx.run/'input/model/robot_arm.urdf'
        with self.rt.phase():
            self.api._bind_workspace(ctx,D);D.verify_workspace(model)
            for name in ('model/robot_arm.urdf','ref/workspace.json','source/config.json','source/validate.py','source/decision_schema.py','source/bootstrap.py','workspace-preflight.json'):
                target=ctx.run/'input'/name;old=target.read_bytes()
                try:
                    target.write_bytes(old+b'\n')
                    with self.subTest(name=name),self.assertRaises(ValueError):D.verify_workspace(model)
                finally:target.write_bytes(old)
            target=ctx.run/'job.json';old=target.read_bytes()
            try:
                target.write_bytes(old+b'\n')
                with self.assertRaisesRegex(ValueError,'job bytes'):D.verify_workspace(model)
            finally:target.write_bytes(old)
            extra=ctx.run/'input/source/extra.py';extra.write_bytes(b'new source22')
            try:
                with self.assertRaisesRegex(ValueError,'inventory'):D.verify_workspace(model)
            finally:extra.unlink()
            authority=self.rt.workspace_auth
            for field,value in (('unit','111'),('schema_version',True),('receipt_sha256','0'*64),('active_config_raw',b'wrongstamp'),('template_config_raw',b'{}')):
                self.rt.workspace_auth=dict(authority,**{field:value})
                with self.subTest(field=field),self.assertRaises(ValueError):D.verify_workspace(model)
            self.rt.workspace_auth=authority;D.verify_workspace(model)

    def test_workspace_parent_end_same_float_reentry_thread_and_no_read(self):
        ctx,D,source=workspace_fixture(self.api,self.rt,self.p);model=ctx.run/'input/model/robot_arm.urdf'
        with self.rt.phase() as original_end:self.api._bind_workspace(ctx,D);D.verify_workspace(model)
        original=Path.read_bytes;reads=[]
        def unowned(path):reads.append(str(path));raise AssertionError('scope must precede I/O')
        Path.read_bytes=unowned
        try:
            with self.rt.phase() as new_end:
                self.assertEqual(original_end,new_end)
                with self.assertRaisesRegex(ValueError,'scope'):D.verify_workspace(model)
            errors=[]
            def other():
                try:D.verify_workspace(model)
                except Exception as exc:errors.append(type(exc).__name__)
            t=threading.Thread(target=other);t.start();t.join();self.assertEqual(errors,['ValueError'])
        finally:Path.read_bytes=original
        self.assertEqual(reads,[])

    def test_workspace_provider_keeps_child_owner_through_D_exit(self):
        ctx,D,source=workspace_fixture(self.api,self.rt,self.p);original=D.verify_workspace_receipt;depth=[]
        def checked(*args):depth.append(len(self.rt.local.stack));return original(*args)
        D.verify_workspace_receipt=checked
        with self.rt.phase():
            self.api._bind_workspace(ctx,D);D.verify_workspace(ctx.run/'input/model/robot_arm.urdf')
            self.assertEqual(len(self.rt.local.stack),1)
        self.assertEqual(depth,[2])

    def test_workspace_postyield_check_precedes_successful_return(self):
        ctx,D,source=workspace_fixture(self.api,self.rt,self.p);original=self.rt.require_workspace_scope;checks=[]
        def checked(scope):
            original(scope);checks.append(len(self.rt.local.stack))
            if len(checks)==3:raise ValueError('HOST postyield original scope rejected')
        self.rt.require_workspace_scope=checked
        with self.rt.phase():
            self.api._bind_workspace(ctx,D)
            with self.assertRaisesRegex(ValueError,'postyield original'):D.verify_workspace(ctx.run/'input/model/robot_arm.urdf')
        self.assertEqual(checks,[1,2,2]);self.assertEqual(self.rt.local.stack,[])

    def test_workspace_missing_bind_wrong_module_and_prepare_omission(self):
        self.rt=RuntimeFixture(self.api,self.p,lifetime=2700);ctx,D,source=workspace_fixture(self.api,self.rt,self.p)
        with self.assertRaisesRegex(ValueError,'bound'):D.verify_workspace(ctx.run/'input/model/robot_arm.urdf')
        with self.rt.phase():
            D.__file__=str(ctx.run/'input/source/alias.py')
            with self.assertRaisesRegex(ValueError,'source binding'):self.api._bind_workspace(ctx,D)
        self.api._bind_workspace=lambda *a:None
        with self.assertRaisesRegex(ValueError,'bound'):self.api.prepare(source,'import',runtime=self.rt)

    def test_workspace_current_read_block_expires_original_owner(self):
        p=fixture();started=time.monotonic();child=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(__file__),'--subject',str(p),'workspace'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
        stdout,stderr=child.communicate(timeout=8)
        (p/'workspace-block-observer.json').write_text(json.dumps({'returncode':child.returncode,'elapsed_s':time.monotonic()-started,'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace')}),encoding='utf8')
        self.assertEqual(child.returncode,124,(stdout,stderr));self.assertIn(b'WORKSPACE_CURRENT_READ_ENTERED',stdout)

    def test_actual_C_to_B_to_D_prepare_and_current_authority_mutation(self):
        B,rt,ctx=actual_b_workspace(self.api,self.p)
        D=self.api.load_module('actual_B_provider_D',ctx.data['source/validate.py'],ctx.run/'input/source/validate.py')
        model=ctx.run/'input/model/robot_arm.urdf';calls=[];original=rt.workspace_authority
        def traced(scope):calls.append('actual B authority');return original(scope)
        rt.workspace_authority=traced
        with rt.phase():
            self.api._bind_workspace(ctx,D);D.verify_workspace(model);D.verify_workspace(model)
            self.assertEqual(calls,['actual B authority','actual B authority'])
            target=rt.out/'runtime-budget.json';raw=target.read_bytes()
            try:
                item=B.parse(raw);item['workspace_preflight_sha256']='0'*64;target.write_bytes(B.canonical(item))
                with self.assertRaises(ValueError):D.verify_workspace(model)
            finally:target.write_bytes(raw)
            D.verify_workspace(model)
        with rt.phase():
            with self.assertRaisesRegex(ValueError,'original active'):D.verify_workspace(model)

    def test_actual_C_B_D_consume_two_uses_and_smoke_proof_physics(self):
        B,rt,base=actual_b_workspace(self.api,self.p);calls=[];original=self.api.load_module
        def observed(name,raw,path):
            D=original(name,raw,path)
            if name in ('validate','smoke_verify'):
                consumer=D.verify_workspace_receipt
                def check(*args):calls.append(name);return consumer(*args)
                D.verify_workspace_receipt=check
            return D
        self.api.load_module=observed
        smoke=replay_stage(self.api,rt,base,'render_smoke')
        code,result=self.api.consume(smoke)
        self.assertEqual(code,0);self.assertEqual(result['status'],'SMOKE_VERIFIED');self.assertTrue(result['metrics']['dynamics_pass'])
        self.assertEqual(calls,['validate','validate'])
        motion=replay_stage(self.api,rt,base,'motion',previous=smoke)
        self.assertEqual(calls,['validate','validate','smoke_verify'])
        self.assertEqual(motion.job['purpose'],'motion')
        saved=self.api._bind_workspace;self.api._bind_workspace=lambda *a:None
        try:
            with self.assertRaisesRegex(ValueError,'bound'):self.api.consume(smoke)
            with self.assertRaisesRegex(ValueError,'bound'):self.api.snapshot(motion.run,motion.job_hash,runtime=rt)
        finally:self.api._bind_workspace=saved
        self.api.write(self.p/'actual-C-B-D-replay.json',{'scope':'SYNTHETIC_HOST_CURRENT_IDENTITIES_OLD111_PHYSICS_NOT114_NATIVE',
            'calls':calls,'smoke_physics':result['metrics'],'import_inputs':len(base.data),'smoke_inputs':len(smoke.data),'motion_inputs':len(motion.data)})

    def test_actual_consume_second_internal_use_rejects_current_file_and_authority(self):
        B,rt,base=actual_b_workspace(self.api,self.p);smoke=replay_stage(self.api,rt,base,'render_smoke');original=self.api.load_module
        for target in (smoke.run/'input/ref/workspace.json',smoke.run/'input/source/decision_schema.py',rt.out/'runtime-budget.json'):
            raw=target.read_bytes();uses=[]
            def changed(name,source,path):
                D=original(name,source,path)
                if name=='validate':
                    check=D.verify_workspace_receipt
                    def after_first(*args):
                        value=check(*args);uses.append(name)
                        if len(uses)==1:target.write_bytes(raw+b'\n')
                        return value
                    D.verify_workspace_receipt=after_first
                return D
            self.api.load_module=changed
            try:
                if target.name=='runtime-budget.json':
                    # Byte changes alone are JSON-equivalent; change the independent authority value.
                    def mutate_authority(name,source,path):
                        D=original(name,source,path)
                        if name=='validate':
                            check=D.verify_workspace_receipt
                            def after_first(*args):
                                value=check(*args);uses.append(name)
                                item=B.parse(raw);item['workspace_preflight_sha256']='0'*64;target.write_bytes(B.canonical(item));return value
                            D.verify_workspace_receipt=after_first
                        return D
                    self.api.load_module=mutate_authority
                with self.subTest(target=str(target)),self.assertRaises(ValueError):self.api.consume(smoke)
                self.assertEqual(uses,['validate'])
            finally:target.write_bytes(raw);self.api.load_module=original

    def test_actual_B_control_clock_identity_policy_zero_cold_repeated_mutations(self):
        B,rt,_=actual_b_workspace(self.api,self.p,prepare=False)
        original_validator=B.workspace_validator;original_phase=rt.phase;control_policy=[];numeric_identity=[];phases=[];observations=[];argv_calls=[]
        def validator(*args):
            D=original_validator(*args);identity=D.verify_workspace_receipt_identity
            def forbidden(bundle):control_policy.append('UNEXPECTED_POLICY');raise AssertionError('control authority must not execute all-format policy')
            def identity_use(*values):numeric_identity.append('fresh current identity');return identity(*values)
            D._run_policy=forbidden;D.verify_workspace_receipt_identity=identity_use;return D
        B.workspace_validator=validator
        @contextlib.contextmanager
        def phase(limit=None):
            with original_phase(limit) as end:
                phases.append((limit,end));yield end
        rt.phase=phase
        def local_clock(cfg,nonce):
            argv_calls.append(nonce);return [sys.executable,'-I','-S','-B','-c',self.api.clock_remote_code(nonce)]
        self.api.clock_argv=local_clock
        def current_ctx():
            run=rt.root/'HOST_LOCAL_OS_CLOCK_EXECUTABLE_SEAM'/uuid.uuid4().hex;run.mkdir(parents=True)
            return rt.bind(types.SimpleNamespace(run=run,job_hash='a'*64,cfg=self.api.read(rt.src/'config.json')))
        for iteration in ('cold','repeated'):
            with rt.phase():
                authority=rt.workspace_authority(rt.workspace_scope())
                self.assertEqual(len(authority['decision_inputs']),48);self.assertEqual(authority['unit'],'114')
            ctx=current_ctx();phases.clear();started=time.monotonic();cert=self.api.clock_probe(ctx);elapsed=time.monotonic()-started
            self.api.clock_bounds(cert);self.assertLess(elapsed,20);self.assertEqual(phases[0][0],20)
            original_end=phases[0][1];self.assertTrue(all(end<=original_end+1e-6 for _,end in phases))
            marker=self.api.read(ctx.run/'clock-query-attempt.json');query=self.api.read(ctx.run/'clock-query.json')
            self.assertEqual(marker['overall_deadline_monotonic'],original_end)
            self.assertEqual(marker['communication_deadline_monotonic'],original_end-2.)
            self.assertEqual(query['overall_deadline_monotonic'],original_end);self.assertTrue(query['terminal']);self.assertEqual(query['actual_child_exit_code'],0)
            observations.append({'iteration':iteration,'elapsed_s':elapsed,'original20_end':original_end,'nested_phases':len(phases),'policy_calls':len(control_policy)})
        self.assertEqual(len(argv_calls),2);self.assertEqual(control_policy,[]);self.assertGreaterEqual(len(numeric_identity),6)
        cfg=self.api.read(rt.src/'config.json')
        for target in (rt.src/'decision_schema.py',rt.root/cfg['refs']['workspace.json']['path'],rt.out/'runtime-budget.json'):
            raw=target.read_bytes();before=len(argv_calls)
            try:
                if target.name=='runtime-budget.json':
                    item=B.parse(raw);item['workspace_preflight_sha256']='0'*64;target.write_bytes(B.canonical(item))
                else:target.write_bytes(raw+b'\n')
                with self.subTest(target=target.name),self.assertRaises(ValueError):self.api.clock_probe(current_ctx())
                self.assertEqual(len(argv_calls),before)
            finally:target.write_bytes(raw)
        self.assertEqual(control_policy,[])
        self.api.write(self.p/'actual-control-clock-identity-observer.json',{'scope':'HOST_LOCAL_OS_CLOCK_EXECUTABLE_SEAM_NOT_TARGET_NATIVE','current_inputs':48,'current_sources':21,'policy_calls':0,'fresh_identity_calls':len(numeric_identity),'observations':observations,'mutations_rejected_before_OS':3})

    def test_actual_control_clock_current_input_stall_keeps_original20_owner(self):
        p=fixture();started=time.monotonic();child=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(__file__),'--subject',str(p),'actual_control_clock_stall'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
        try:stdout,stderr=child.communicate(timeout=35)
        except BaseException:
            child.terminate();stdout,stderr=child.communicate(timeout=3)
            self.api.write(p/'actual-control-stall-observer.json',{'returncode':child.returncode,'own_child_terminated':True,'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace')});raise
        finished=time.monotonic();entry=self.api.read(p/'actual-control-stall-start.json');clock_elapsed=finished-entry['started_monotonic']
        self.api.write(p/'actual-control-stall-observer.json',{'scope':'HOST_CURRENT_INPUT_READ_STALL_NOT_TARGET_FAILURE','returncode':child.returncode,'elapsed_s':finished-started,'clock_entry_elapsed_s':clock_elapsed,'original_clock_s':20,'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace')})
        self.assertEqual(child.returncode,124,(stdout,stderr));self.assertIn(b'CONTROL_CURRENT_POLICY_READ_ENTERED',stdout);self.assertNotIn(b'UNEXPECTED_OS_ARGV',stdout)
        self.assertGreater(clock_elapsed,19.5);self.assertLess(clock_elapsed,22)

    def test_actual_numeric_provider_current_B_identity_policy_zero_and_fresh_D_policy(self):
        B,rt,_=actual_b_workspace(self.api,self.p,prepare=False);original_validator=B.workspace_validator;control_policy=[];numeric=[];original_load=self.api.load_module
        def validator(*args):
            D=original_validator(*args)
            def forbidden(bundle):control_policy.append('UNEXPECTED_POLICY');raise AssertionError('B control authority numeric policy forbidden')
            D._run_policy=forbidden;return D
        B.workspace_validator=validator
        def load(name,raw,path):
            D=original_load(name,raw,path)
            if name=='prepare_workspace':
                policy=D._run_policy
                def fresh(bundle):numeric.append(name);return policy(bundle)
                D._run_policy=fresh
            return D
        self.api.load_module=load
        source=self.api.own_source(runtime=rt);run=self.api.prepare(source,'import',runtime=rt)
        ctx=self.api.snapshot(run,self.api.sha(run/'job.json'),runtime=rt);self.assertEqual(len(ctx.data),49);self.assertEqual(numeric,['prepare_workspace'])
        D=original_load('actual114_numeric_count',ctx.data['source/validate.py'],ctx.run/'input/source/validate.py');policy=D._run_policy
        def fresh(bundle):numeric.append('same D numeric');return policy(bundle)
        D._run_policy=fresh
        with rt.phase():
            self.api._bind_workspace(ctx,D)
            first,metrics=D.verify_workspace(run/'input/model/robot_arm.urdf');first['status']='HOST_RESULT_MUTATION';metrics['samples']=-1
            second,other=D.verify_workspace(run/'input/model/robot_arm.urdf')
        self.assertEqual(numeric,['prepare_workspace','same D numeric','same D numeric']);self.assertEqual(control_policy,[])
        self.assertNotEqual(second.get('status'),'HOST_RESULT_MUTATION');self.assertEqual(other['samples'],8192)
        self.api.write(self.p/'actual-numeric-use-boundary-observer.json',{'scope':'SYNTHETIC_HOST_FIXTURE_NOT_REVIEW_OR_NATIVE_AUTHORITY','control_policy_calls':0,'numeric_policy_calls':len(numeric),'numeric_sites':numeric,'input49':len(ctx.data),'source21':len(source)})

    def test_actual_B_literal_inline_owner_and_fifth_consumer(self):
        B=module(SRC/'bootstrap.py','B_actual_inline');helper=self.rt.helper;helper.__source_bytes__=self.rt.helper_bytes
        source=self.p/'input/source';source.mkdir(parents=True)
        for name in ('bootstrap.py','driver.py'):(source/name).write_bytes((SRC/name).read_bytes())
        now=time.monotonic();wall=time.time();end=self.rt.end_monotonic
        lease={k:'a'*64 for k in B.LEASE_KEYS if k.endswith('_sha256')}
        lease.update(schema_version=1,unit='114',nonce=self.p.name,client_started_monotonic=now,client_deadline_monotonic=now+2700,
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
                if namespace.get('__name__')=='_child114':namespace['Runtime']=lambda *a,**k:self.rt;namespace['module']=loaded
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
        result=self.api.remote("Write-Output 'ACTUAL_C114_LOCAL_PS';exit 7",cfg['ssh_alias'],8,runtime=self.rt)
        self.assertEqual(result.returncode,7);self.assertIn(b'ACTUAL_C114_LOCAL_PS',result.stdout);self.assertTrue(result.record['terminal'])
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
