"""110 C regression: real generated entry and local transport, never SDK."""
from pathlib import Path
import ast
import base64
import builtins
import contextlib
import hashlib
import io
import json
import os
import sys
import time
import types
import unittest
import uuid
import zipfile
import subprocess

SRC=Path(__file__).resolve().parent
REPO=SRC.parents[2]
FIX=REPO/'outputs/single-host-controller-110/C-fixtures'


def load(path,name='fixture110'):
    m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__)
    return m


def fixture():
    p=FIX/uuid.uuid4().hex;p.mkdir(parents=True)
    return p


def receiver(api, role='supervise', mutate=False, tamper=False):
    folder=fixture();run=folder/'run';src=run/'input/source';src.mkdir(parents=True)
    path=src/'driver.py';path.write_bytes((SRC/'driver.py').read_bytes())
    cert={'run_id':'test','job_sha256':'a'*64,'sentinel':'fifth-argument'}
    ctx=types.SimpleNamespace(run=run,job_hash='a'*64,job={'inputs':{'source/driver.py':api.sha(path)}},admission=cert)
    tree=ast.parse(api.literal(ctx,role))
    code=base64.b64decode(tree.body[1].value.args[0].args[0].value).decode()
    if mutate:
        parsed=ast.parse(code);n=0
        for call in ast.walk(parsed):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Subscript) and isinstance(call.func.slice,ast.Constant) and call.func.slice.value=='entry':
                assert len(call.args)==5;call.args.pop();n+=1
        assert n==1;code=ast.unparse(ast.fix_missing_locations(parsed))
    if tamper:path.write_bytes(path.read_bytes()+b'\n# altered\n')
    seen=[]
    def checked_exec(compiled,namespace):
        builtins.exec(compiled,namespace)
        namespace['snapshot']=lambda *a:types.SimpleNamespace(run=run,cfg={'remote_root':str(run.parent),'deadline_unix':2})
        def supervise(c):seen.append(c.admission);return 0
        namespace['supervise']=supervise
        if role=='native':
            namespace['remote_clock_now']=lambda c:seen.append(c.admission) or 1
            def stop(_):raise RuntimeError('stop before lock/SDK')
            namespace['read']=stop
            namespace['native_failure']=lambda *a:0
        if role=='export':
            namespace['entry']=lambda *a:seen.append(a[4]) or 0
    env={'__builtins__':dict(vars(builtins),exec=checked_exec)}
    try:builtins.exec(compile(code,'<actual-literal-consumer>','exec'),env)
    except SystemExit as exit:
        if exit.code!=0:raise
    return seen[-1],cert


class DriverTests(unittest.TestCase):
    def setUp(self):self.api=load(SRC/'driver.py')

    def closed(self,**changes):
        value={'actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,'terminal':True,
               'raw_complete':True,'job_active_after':0,'child_pid':1234,'child_state':'REAPED','errors':[]}
        value.update(changes)
        def run(argv,out,*a,**k):
            (out/'stdout.txt').write_bytes(b'original stdout\x00')
            (out/'stderr.txt').write_bytes(b'original stderr\r\n')
            return value
        return types.SimpleNamespace(run=run)

    def test_actual_generated_entry_receives_admission(self):
        value,cert=receiver(self.api);self.assertEqual(value,cert)

    def test_original_four_argument_mutation_is_detected(self):
        value,cert=receiver(self.api,mutate=True);self.assertIsNone(value)
        with self.assertRaises(AssertionError):self.assertEqual(value,cert)

    def test_actual_native_entry_receives_admission_before_sdk(self):
        value,cert=receiver(self.api,role='native');self.assertEqual(value,cert)

    def test_export_generated_entry_receives_none(self):
        self.assertIsNone(receiver(self.api,role='export')[0])

    def test_actual_generated_caller_rejects_changed_driver(self):
        with self.assertRaisesRegex(SystemExit,'Pinned driver changed'):receiver(self.api,tamper=True)

    def test_unchanged_physics_and_proof_function_bytecode(self):
        original=ast.parse((REPO/'src/simulation/clock_ready_resume_108/driver.py').read_bytes())
        current=ast.parse((SRC/'driver.py').read_bytes())
        old={x.name:x for x in original.body if isinstance(x,ast.FunctionDef)}
        new={x.name:x for x in current.body if isinstance(x,ast.FunctionDef)}
        changed={'clock_probe','session_now','clock_window','clock_remote_code','clock_argv','clock_capture_available','clock_exchange','own_source','config_contract','stop_and_reap','run_child','literal','supervise','remote','recover_transport','launch','consume','public'}
        checked=0
        for name,node in old.items():
            if name not in changed:self.assertEqual(ast.dump(node),ast.dump(new[name]),name);checked+=1
        self.assertGreaterEqual(checked,35)

    def test_config_preserves_all_physical_and_numeric_limits(self):
        old=self.api.read(REPO/'src/simulation/clock_ready_resume_108/config.json');new=self.api.read(SRC/'config.json')
        changed={'experiment_id','remote_root','source_A'}
        for key,value in old.items():
            if key not in changed:self.assertEqual(new[key],value,key)
        self.assertEqual(new['deadline_unix'],0);self.assertIs(type(new['deadline_unix']),int)

    def test_actual_composed_source19_and_legacy16(self):
        source=self.api.own_source(SRC);self.assertEqual(len(source),19)
        for name,raw in source.items():
            expected=(SRC if name in {'driver.py','config.json','winjob.py'} else REPO/'src/simulation/clock_ready_resume_108')/name
            self.assertEqual(raw,expected.read_bytes())

    def test_new_config_requires_explicit_local_transport(self):
        cfg=self.api.read(SRC/'config.json');self.api.config_contract(cfg)
        cfg['transport_kind']='SSH'
        with self.assertRaisesRegex(ValueError,'Explicit local'):self.api.config_contract(cfg)

    def test_legacy_test_entry_cannot_write_output108(self):
        with self.assertRaisesRegex(ValueError,'Legacy108 HOST'):self.api.public('test')

    def test_actual_closed_helper_load(self):
        module=self.api._job_helper();self.assertTrue(callable(module.run));self.assertTrue(callable(module.Fence))

    def test_wrong_snapshot_helper_pin_rejected(self):
        c=types.SimpleNamespace(run=fixture(),data={'source/winjob.py':b'bad'},cfg={'winjob_sha256':'0'*64},job={'inputs':{'source/winjob.py':'0'*64}})
        with self.assertRaisesRegex(ValueError,'snapshot helper'):self.api._job_helper(c)

    def test_actual_local_copy_and_exclusive_destination(self):
        p=fixture();a=p/'original';b=p/'copied';a.write_bytes(b'original\x00raw\r\n')
        r=self.api._copy_new(a,b,self.api.sha(a));self.assertEqual(a.read_bytes(),b.read_bytes());self.assertEqual(r['transport_kind'],'LOCAL_COPY')
        with self.assertRaisesRegex(ValueError,'Exclusive'):self.api._copy_new(a,b)

    def test_wrong_copy_pin_refuses_before_destination(self):
        p=fixture();a=p/'a';b=p/'b';a.write_bytes(b'raw')
        with self.assertRaisesRegex(ValueError,'expected bytes'):self.api._copy_new(a,b,'0'*64)
        self.assertFalse(b.exists())

    def test_copy_ancestry_rejection_at_actual_consumer(self):
        p=fixture();a=p/'a';a.write_bytes(b'raw');self.api.no_link=lambda _:False
        with self.assertRaisesRegex(ValueError,'safe absolute'):self.api._copy_new(a,p/'b')

    def archive(self,items):
        p=fixture();z=p/'bundle.zip'
        with zipfile.ZipFile(z,'x') as archive:
            for name,raw in items:archive.writestr(name,raw)
        return p,z

    def test_actual_same_host_extraction(self):
        p,z=self.archive([('input/source.txt',b'data'),('job.json',b'{}')]);self.api._extract_local(z,p,self.api.sha(z))
        self.assertEqual((p/'input/source.txt').read_bytes(),b'data')

    def test_extraction_refuses_original_file_overwrite(self):
        p,z=self.archive([('bundle.zip',b'changed')]);pin=self.api.sha(z)
        with self.assertRaises(FileExistsError):self.api._extract_local(z,p,pin)
        self.assertEqual(self.api.sha(z),pin)

    def test_archive_traversal_refused(self):
        p,z=self.archive([('../outside',b'bad')])
        with self.assertRaisesRegex(ValueError,'safe archive'):self.api._extract_local(z,p,self.api.sha(z))

    def test_archive_duplicate_refused(self):
        p,z=self.archive([('item',b'one'),('item',b'two')])
        with self.assertRaisesRegex(ValueError,'safe archive'):self.api._extract_local(z,p,self.api.sha(z))

    def test_archive_link_refused(self):
        p=fixture();z=p/'bundle.zip';info=zipfile.ZipInfo('link');info.external_attr=(0o120777<<16)
        with zipfile.ZipFile(z,'x') as archive:archive.writestr(info,b'target')
        with self.assertRaisesRegex(ValueError,'Archive link'):self.api._extract_local(z,p,self.api.sha(z))

    def test_uncertain_process_cannot_be_accepted(self):
        p=fixture()
        fake=self.closed(terminal=False)
        with self.assertRaisesRegex(ValueError,'Actual owned process'):self.api._controlled_process(['ignored'],p,3,fake)

    def test_capture_failure_cannot_be_accepted(self):
        p=fixture()
        fake=self.closed(raw_complete=False)
        with self.assertRaisesRegex(ValueError,'Actual owned process'):self.api._controlled_process(['ignored'],p,3,fake)

    def test_remaining_descendant_cannot_be_accepted(self):
        p=fixture()
        fake=self.closed(job_active_after=1)
        with self.assertRaisesRegex(ValueError,'Actual owned process'):self.api._controlled_process(['ignored'],p,3,fake)

    def test_bool_active_count_cannot_masquerade_as_zero(self):
        with self.assertRaisesRegex(ValueError,'Actual owned process'):
            self.api._controlled_process(['ignored'],fixture(),3,self.closed(job_active_after=False))

    def test_zero_actual_but_nonzero_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'code agreement'):
            self.api._controlled_process(['ignored'],fixture(),3,self.closed(policy_exit_code=1))

    def test_real_failure_code_and_raw_are_retained(self):
        r=self.api._controlled_process(['ignored'],fixture(),3,self.closed(actual_child_exit_code=7,policy_exit_code=7))
        self.assertEqual(r.returncode,7);self.assertEqual(r.stderr,b'original stderr\r\n')

    def test_closed_timeout_retains_raw_for_existing_recovery(self):
        import subprocess
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            self.api._controlled_process(['ignored'],fixture(),3,self.closed(actual_child_exit_code=124,policy_exit_code=124,timed_out=True))
        self.assertEqual(caught.exception.stdout,b'original stdout\x00');self.assertEqual(caught.exception.stderr,b'original stderr\r\n')

    def transport_case(self,kind):
        p=fixture();retrieved=p/'retrieved';retrieved.mkdir();job={'run_id':p.name,'purpose':'import'};h='a'*64
        identity={'run_id':p.name,'job_sha256':h}
        terminal={**identity,'pid':2,'parent_pid':1,'purpose':'import','code':0,'status':'CLOSED','files_sha256':{}}
        ex={**identity,'pid':1,'child_pid':2,'purpose':'import','actual_child_exit_code':0,'policy_exit_code':0,'timed_out':False,'child_state':'REAPED'}
        shell={**identity,'python_exit_code':0}
        for name,value in [('terminal.json',terminal),('exit.json',ex),('remote-shell.json',shell)]:
            (retrieved/name).write_text(json.dumps(value),encoding='utf-8')
        for name in ['stdout.txt','stderr.txt']:(retrieved/name).write_bytes(b'')
        (p/'transport.json').write_text(json.dumps({'transport_kind':kind,'timed_out':False,'returncode':0}),encoding='utf-8')
        return types.SimpleNamespace(run=p,job_hash=h,job=job)

    def test_actual_consumer_rejects_false_ssh_transport_identity(self):
        with self.assertRaisesRegex(ValueError,'same-host process return'):
            self.api.consume(self.transport_case('SSH'))

    def test_local_transport_passes_actual_consumer_boundary(self):
        class Reached(Exception):pass
        def reach(_):raise Reached('transport accepted; physics not executed')
        self.api.bind_sources=reach
        with self.assertRaisesRegex(Reached,'transport accepted'):
            self.api.consume(self.transport_case('LOCAL_PROCESS'))

    def test_process_shared_cleanup_budget_is_not_reset(self):
        p=fixture()
        fake=types.SimpleNamespace(run=lambda *a,**k:self.fail('child must not start'))
        for total in (0,1,2,True,float('inf')):
            with self.assertRaisesRegex(ValueError,'cleanup reserve'):self.api._controlled_process(['ignored'],p,total,fake)

    def test_runtime_b_missing_is_default_deny(self):
        self.api.ROOT=fixture()
        with self.assertRaises(FileNotFoundError):self.api.session_now(self.api.read(SRC/'config.json'))

    def test_cli_run_and_controller_refuse_missing_b(self):
        m=load(REPO/'outputs/single-host-controller-110/execute.py')
        for args in (['--run'],['--controller']):
            with contextlib.redirect_stdout(io.StringIO()) as stream:self.assertEqual(m.main(args),2)
            self.assertEqual(json.loads(stream.getvalue())['status'],'B_INTEGRATION_L2_BLOCK_NO_RUNTIME_AUTHORITY')

    @unittest.skipUnless(os.name=='nt','Windows pure-OS probe')
    def test_actual_same_host_clock_child_and_original_bounds(self):
        self.clock_case(False)

    @unittest.skipUnless(os.name=='nt','Windows pure-OS probe')
    def test_actual_slow_os_child_rejected_not_retried(self):
        self.clock_case(True)

    def local_fixture(self,remaining=2700):
        p=fixture();self.api.ROOT=p;out=p/self.api.OUT;out.mkdir(parents=True)
        cfg=self.api.read(SRC/'config.json');cfg['deadline_unix']=time.time()+remaining
        (out/'runtime-budget.json').write_text(json.dumps({'started_monotonic':time.monotonic()-2700+remaining}),encoding='utf-8')
        original_read=self.api.read
        self.api.read=lambda path:cfg if Path(path)==SRC/'config.json' else original_read(path)
        self.api.session_now=lambda _:time.time()
        return cfg,out

    @unittest.skipUnless(os.name=='nt','Windows own PowerShell child')
    def test_actual_local_powershell_exit_and_capture(self):
        cfg,out=self.local_fixture()
        r=self.api.remote("[Console]::WriteLine('only owned fixture');exit 7",cfg['ssh_alias'],8)
        self.assertEqual(r.returncode,7);self.assertIn(b'only owned fixture',r.stdout)
        self.assertIs(r.record['terminal'],True);self.assertEqual(r.record['job_active_after'],0)
        self.assertEqual(len(list((out/'local-transport').iterdir())),1)

    @unittest.skipUnless(os.name=='nt','Windows own PowerShell child')
    def test_actual_local_rpc_respects_existing_global_end(self):
        import subprocess
        cfg,out=self.local_fixture(5);started=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            self.api.remote("[Console]::WriteLine('entered');[Threading.Thread]::Sleep(10000)",cfg['ssh_alias'],120)
        self.assertIn(b'entered',caught.exception.stdout)
        records=list((out/'local-transport').glob('*/process.json'));self.assertEqual(len(records),1)
        record=json.loads(records[0].read_text(encoding='utf-8'))
        self.assertIs(record['timed_out'],True);self.assertIs(record['terminal'],True)
        self.assertEqual(record['job_active_after'],0);self.assertLess(time.monotonic()-started,5.5)

    @unittest.skipUnless(os.name=='nt','Windows own native-entry substitute')
    def test_actual_run_child_snapshot_helper_and_admit(self):
        p=fixture();raw=(SRC/'winjob.py').read_bytes();pin=self.api.digest(raw)
        ctx=types.SimpleNamespace(run=p,data={'source/winjob.py':raw},cfg={'winjob_sha256':pin},job={'inputs':{'source/winjob.py':pin}})
        called=[]
        def admit():
            self.assertFalse((p/'stdout.txt').exists());called.append(True)
        r=self.api.run_child([sys.executable,'-I','-B','-c',"print('owned substitute, no SDK')"],p,5,admit,ctx)
        self.assertEqual(called,[True]);self.assertEqual(r['actual_child_exit_code'],0)
        self.assertEqual(r['policy_exit_code'],0);self.assertEqual(r['child_state'],'REAPED');self.assertIs(r['keep_awake_reset'],True)

    @unittest.skipUnless(os.name=='nt','Windows failed admission, no child')
    def test_admit_failure_retains_original_not_started_parent_contract(self):
        p=fixture();raw=(SRC/'winjob.py').read_bytes();pin=self.api.digest(raw)
        ctx=types.SimpleNamespace(run=p,data={'source/winjob.py':raw},cfg={'winjob_sha256':pin},job={'inputs':{'source/winjob.py':pin}})
        def reject():raise ValueError('fixture admission refused')
        r=self.api.run_child([sys.executable,'-I','-B','-c',"raise RuntimeError('must not run')"],p,5,reject,ctx)
        self.assertIsNone(r['child_pid']);self.assertEqual(r['child_state'],'NOT_STARTED');self.assertNotEqual(r['policy_exit_code'],0)
        job={'run_id':p.name,'purpose':'import'};r.update(run_id=p.name,job_sha256='a'*64,purpose='import',pid=os.getpid())
        self.api.finalize_parent(p,job,'a'*64,r,None,p/'absent-lock')
        self.assertEqual((p/'stdout.txt').read_bytes(),b'');self.assertEqual((p/'stderr.txt').read_bytes(),b'')
        self.assertEqual(self.api.read(p/'recovery-manifest.json')['native_acceptance'],False)

    @unittest.skipUnless(os.name=='nt','Windows actual child before join-observation failure')
    def test_executed_child_is_unknown_after_delegate_exception(self):
        p=fixture();raw=(SRC/'winjob.py').read_bytes();pin=self.api.digest(raw)
        ctx=types.SimpleNamespace(run=p,data={'source/winjob.py':raw},cfg={'winjob_sha256':pin},job={'inputs':{'source/winjob.py':pin}})
        helper=self.api._job_helper(ctx);original=helper.Fence
        class JoinObservationFails(original):
            def close(self):
                super().close();raise OSError('fixture post-child join observation failed')
        helper.Fence=JoinObservationFails;self.api._job_helper=lambda *a:helper
        r=self.api.run_child([sys.executable,'-I','-B','-c',"print('ACTUAL_C_CHILD_RAN')"],p,5,ctx=ctx)
        self.assertIn(b'ACTUAL_C_CHILD_RAN',(p/'stdout.txt').read_bytes())
        self.assertEqual(r['child_state'],'UNKNOWN');self.assertIsNone(r['actual_child_exit_code']);self.assertNotEqual(r['policy_exit_code'],0)

    @unittest.skipUnless(os.name=='nt','Windows actual closed process provenance')
    def test_known_clock_record_survives_process_json_publication_failure(self):
        p=fixture();self.api.ROOT=p;out=p/self.api.OUT;out.mkdir(parents=True)
        cfg=self.api.read(SRC/'config.json');cfg['deadline_unix']=time.time()+2700
        (out/'runtime-budget.json').write_text(json.dumps({'unit':'110','duration_s':2700,'deadline_unix':cfg['deadline_unix'],'started_monotonic':time.monotonic()}),encoding='utf-8')
        self.api.session_now=lambda _:time.time()
        self.api.clock_argv=lambda c,n:[sys.executable,'-I','-S','-B','-c',self.api.clock_remote_code(n)]
        original=self.api.write
        def fail_process(path,value):
            if Path(path).name=='process.json':
                Path(path).write_bytes(b'{}')
                raise OSError('fixture process publication failed after partial publication')
            original(path,value)
        self.api.write=fail_process
        with self.assertRaises(self.api.ClockChannelError) as caught:
            self.api.clock_probe(types.SimpleNamespace(run=out,job_hash='a'*64,cfg=cfg))
        self.assertEqual(caught.exception.returncode,0)
        value=self.api.read(out/'clock-query.json');self.assertGreater(value['process']['child_pid'],0)
        self.assertEqual(value['process']['actual_child_exit_code'],0);self.assertIs(value['process']['terminal'],True)
        self.assertIs(value['query_record_complete'],False);self.assertIs(value['raw_complete'],False)

    @unittest.skipUnless(os.name=='nt','Windows own bounded filesystem producer')
    def test_recovery_actual_copy_and_verifier_positive(self):
        recovery_subject(fixture(),'normal')

    @unittest.skipUnless(os.name=='nt','Windows own bounded filesystem producer')
    def test_blocked_recovery_copy_owner_and_omission_mutation(self):
        for mode in ('blocked','no_owner_mutant'):
            p=fixture();started=time.monotonic()
            child=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(Path(__file__)),'--recovery-subject',str(p),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
            if mode=='blocked':
                stdout,stderr=child.communicate(timeout=3)
                self.assertEqual(child.returncode,124,(stdout,stderr));self.assertIn(b'COPY_ENTERED',stdout);self.assertLess(time.monotonic()-started,2)
            else:
                with self.assertRaises(subprocess.TimeoutExpired):child.communicate(timeout=.9)
                child.terminate();stdout,stderr=child.communicate(timeout=3)
                self.assertIn(b'COPY_ENTERED',stdout)

    @unittest.skipUnless(os.name=='nt','Windows owned upload/extract lifetime subjects')
    def test_actual_launch_upload_and_extract_have_lifetime_owner(self):
        for mode in ('upload','extract'):
            p=fixture()
            child=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(Path(__file__)),'--launch-subject',str(p),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
            stdout,stderr=child.communicate(timeout=3)
            self.assertEqual(child.returncode,124,(stdout,stderr));self.assertIn(b'FS_ENTERED',stdout)

    def clock_case(self,slow):
        p=fixture();self.api.ROOT=p;out=p/self.api.OUT;out.mkdir(parents=True)
        cfg=self.api.read(SRC/'config.json');cfg['deadline_unix']=time.time()+2700
        (out/'runtime-budget.json').write_text(json.dumps({'unit':'110','duration_s':2700,'deadline_unix':cfg['deadline_unix'],'started_monotonic':time.monotonic()}),encoding='utf-8')
        self.api.session_now=lambda _:time.time()
        self.api.clock_argv=lambda c,n:[sys.executable,'-I','-S','-B','-c',('import time;time.sleep(1.1);\n' if slow else '')+self.api.clock_remote_code(n)]
        ctx=types.SimpleNamespace(run=out,job_hash='a'*64,cfg=cfg)
        if slow:
            with self.assertRaisesRegex(ValueError,'offset uncertainty'):self.api.clock_probe(ctx)
            self.assertTrue((out/'clock-query-attempt.json').exists())
        else:
            cert=self.api.clock_probe(ctx);self.api.clock_bounds(cert)
            ctx.admission=cert;self.assertGreater(self.api.remote_clock_now(ctx),time.time())
            observation=self.api.read(out/'clock-query.json')
            capture=p/observation['capture_dir'];request=self.api.read(capture/'request.json')
            self.assertEqual(request['nonce'],observation['nonce'])
            self.assertEqual((capture/'stdout.txt').read_bytes(),(out/'clock-query-stdout.txt').read_bytes())

    def test_failed_clock_capture_keeps_process_and_raw_provenance(self):
        p=fixture();self.api.ROOT=p;out=p/self.api.OUT;out.mkdir(parents=True)
        cfg=self.api.read(SRC/'config.json');cfg['deadline_unix']=time.time()+2700
        (out/'runtime-budget.json').write_text(json.dumps({'unit':'110','duration_s':2700,'deadline_unix':cfg['deadline_unix'],'started_monotonic':time.monotonic()}),encoding='utf-8')
        self.api.session_now=lambda _:time.time()
        real=self.api._job_helper();fake=self.closed(terminal=False,raw_complete=False,errors=['capture fixture problem']);fake.Fence=real.Fence
        self.api._job_helper=lambda *a:fake
        with self.assertRaisesRegex(self.api.ClockChannelError,'Actual owned process'):
            self.api.clock_probe(types.SimpleNamespace(run=out,job_hash='a'*64,cfg=cfg))
        observation=self.api.read(out/'clock-query.json');capture=p/observation['capture_dir']
        self.assertIs(observation['raw_complete'],False);self.assertEqual(observation['process']['child_pid'],1234)
        self.assertEqual(self.api.read(capture/'request.json')['nonce'],observation['nonce'])
        self.assertEqual((out/'clock-query-stdout.txt').read_bytes(),b'original stdout\x00')


def recovery_subject(p,mode):
    api=load(SRC/'driver.py');api.ROOT=p;out=p/api.OUT;out.mkdir(parents=True)
    original_read=api.read;cfg=api.read(SRC/'config.json');cfg['deadline_unix']=time.time()+2700
    (out/'runtime-budget.json').write_text(json.dumps({'started_monotonic':time.monotonic()}),encoding='utf-8')
    api.session_now=lambda _:time.time()
    run_id=uuid.uuid4().hex;remote=p/'worker'/run_id;local=p/'controller'/run_id
    (remote/'input/source').mkdir(parents=True);local.mkdir(parents=True);output=remote/'output';output.mkdir()
    recovery_raw=(REPO/'src/simulation/clock_ready_resume_108/recovery.py').read_bytes()
    data={'source/driver.py':(SRC/'driver.py').read_bytes(),'source/recovery.py':recovery_raw,
          'source/config.json':json.dumps({'hardware_approved':False,'physical_calibration':False,'training':'NOT_RUN','sdk':{'hardware_approved':False,'calibration_approved':False}}).encode()}
    for name,raw in data.items():(remote/'input'/name).write_bytes(raw)
    job={'schema_version':1,'run_id':run_id,'purpose':'import','inputs':{k:api.digest(v) for k,v in data.items()},'common_signature':'a'*64,
         'plan_sha256':api.PLAN_SHA,'hardware_approved':False,'experiment_id':api.EXPERIMENT}
    api.write(remote/'job.json',job);job_hash=api.sha(remote/'job.json')
    ex={'run_id':run_id,'job_sha256':job_hash,'purpose':'import','pid':os.getpid(),'child_pid':None,'actual_child_exit_code':None,
        'policy_exit_code':1,'child_state':'NOT_STARTED','timed_out':False}
    api.finalize_parent(output,job,job_hash,ex,None,remote/'unused-lock')
    api.write(output/'remote-shell.json',{'run_id':run_id,'job_sha256':job_hash,'python_exit_code':1})
    api.write(local/'transport.json',{'returncode':1,'timed_out':False,'transport_kind':'LOCAL_PROCESS'})
    recovery=api.load_module('fixture_closed_recovery',recovery_raw,remote/'input/source/recovery.py')
    def export(*a,**k):
        recovery.export_closed(remote,job_hash,job['inputs']['source/driver.py'],remote)
        return types.SimpleNamespace(returncode=0)
    api.remote=export
    ctx=types.SimpleNamespace(run=local,cfg=cfg,job=job,job_hash=job_hash,data=data)
    remctx=types.SimpleNamespace(run=remote,job=job,job_hash=job_hash)
    if mode!='normal':
        api.recovery_deadline=lambda c,now:now+.4
        def blocked(*a,**k):
            print('COPY_ENTERED',flush=True);time.sleep(5);raise AssertionError('copy outlived phase')
        api._copy_new=blocked
        if mode=='no_owner_mutant':
            helper=api._job_helper()
            class NoOwner:
                def __init__(self,*a,**k):pass
                def __enter__(self):return self
                def __exit__(self,*a):return False
            helper.Fence=NoOwner;api._job_helper=lambda *a:helper
    api.recover_transport(ctx,remctx,sys.executable,str(remote),cfg['ssh_alias'])
    receipt=api.read(local/'recovery-receipt.json')
    assert receipt['native_acceptance'] is False and receipt['kind']=='FAILED_PARENT_SNAPSHOT_COPY'
    assert (local/'retrieved/exit.json').is_file()
    assert api.read(local/'recovery-status.json')['status']=='CLOSED_ARTIFACT_COPY_VERIFIED_NOT_PHYSICS_ACCEPTANCE'


def launch_subject(p,mode):
    api=load(SRC/'driver.py');api.ROOT=p
    run=p/'controller'/uuid.uuid4().hex;run.mkdir(parents=True)
    archive=run/'bundle.zip'
    with zipfile.ZipFile(archive,'x') as z:z.writestr('job.json',b'{}')
    rr=p/'worker'/run.name;rr.parent.mkdir()
    cfg=api.read(SRC/'config.json');cfg['remote_root']=rr.parent.as_posix()
    ctx=types.SimpleNamespace(run=run,cfg=cfg,job={'purpose':'import'},job_hash='a'*64)
    prepared={'remote':rr.as_posix(),'bundle_sha256':api.sha(archive)}
    api.launch_budget=lambda *a,**k:600;api.session_now=lambda _:time.time()
    def create(*a,**k):rr.mkdir();return types.SimpleNamespace(returncode=0)
    api.remote=create
    def deadline(c,limit):
        assert limit==120
        return time.monotonic()+.35
    api._operation_end=deadline
    def blocked(*a,**k):
        print('FS_ENTERED',flush=True);time.sleep(5);raise AssertionError('unowned FS operation')
    if mode=='upload':api._copy_new=blocked
    else:api._extract_local=blocked
    api.launch(ctx,prepared)



if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--recovery-subject':recovery_subject(Path(sys.argv[2]),sys.argv[3])
    elif len(sys.argv)>1 and sys.argv[1]=='--launch-subject':launch_subject(Path(sys.argv[2]),sys.argv[3])
    else:unittest.main(verbosity=2)
