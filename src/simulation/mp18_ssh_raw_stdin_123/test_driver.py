"""123 local HOST foundation only: real local PS pipes, no SSH or SDK."""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import types
import unittest
from unittest import mock
import uuid

HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('raw123_host',HERE/'driver.py');N=importlib.util.module_from_spec(sp);sys.modules[sp.name]=N;sp.loader.exec_module(N)
HOST=N.OUT/'HOST';HOST.mkdir(exist_ok=True)
PS=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
EXE=sys._base_executable


class LocalProxy(unittest.TestCase):
    def test_01_only_input_adapter_and_its_resources_differ_from_accepted_script(self):
        old,new=N.proxy_script(EXE,'pass',30.)
        restored=new.replace(N.INPUT_ADAPTER,'  $ti=[Console]::OpenStandardInput().CopyToAsync($p.StandardInput.BaseStream)')
        restored=restored.replace('[void]$ti.GetAwaiter().GetResult(); $rawChild123.Flush(); $p.StandardInput.Close(); $closed=$true',
            '[void]$ti.GetAwaiter().GetResult(); $p.StandardInput.Close(); $closed=$true')
        restored=restored.replace('} finally { '+N.INPUT_DISPOSE+' }','} finally { $p.Dispose() }')
        self.assertEqual(restored,old)
        self.assertIn('[RawStdin123]::GetStdHandle(-10)',new)
        self.assertEqual(new.count('SafeFileHandle]::new('),2)
        self.assertIn('[IO.FileAccess]::Write,1,$false',new)
        self.assertIn('[IO.FileAccess]::Read,1,$false',new)
        self.assertNotIn('[Console]::OpenStandardInput()',new)
        (HOST/'input-only-proxy.ps1').write_text(new,encoding='utf8')

    def test_02_actual_small_go_before_bulk_all256_eof_and_reverse_stderr(self):
        payload=bytes(range(256))*4096
        code=("import sys,time,json,hashlib,threading,os\n"
              "t=threading.Timer(8,lambda:os._exit(124));t.daemon=True;t.start()\n"
              "print('READ_ONLY_READY',flush=True)\n"
              "line=sys.stdin.buffer.readline(100);print(json.dumps({'kind':'ACK','line_hex':line.hex()}),flush=True)\n"
              "d=sys.stdin.buffer.read();print(json.dumps({'kind':'BULK','bytes':len(d),'sha256':hashlib.sha256(d).hexdigest(),'eof':True}),flush=True)\n"
              "sys.stdout.buffer.write(d);sys.stdout.buffer.flush();sys.stderr.buffer.write(d[::-1]);sys.stderr.buffer.flush();t.cancel()\n")
        p=subprocess.Popen([str(PS),'-NoLogo','-NoProfile','-NonInteractive','-Command',N.proxy_command(EXE,code,35.)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        ready,ack=threading.Event(),threading.Event();data={};events=[]
        def stdout():
            data['ready']=p.stdout.readline();events.append(('READY',time.perf_counter()));ready.set()
            data['ack']=p.stdout.readline();events.append(('ACK',time.perf_counter()));ack.set()
            data['rest']=p.stdout.read()
        def stderr():data['stderr']=p.stderr.read()
        ts=[threading.Thread(target=stdout,daemon=True),threading.Thread(target=stderr,daemon=True)]
        for t in ts:t.start()
        try:
            self.assertTrue(ready.wait(5),'Local target READY')
            N.write_all(p.stdin,b'GO\n',time.monotonic()+5);p.stdin.flush();go_at=time.perf_counter()
            self.assertTrue(ack.wait(3),'Small GO must reach Python before any bulk or EOF')
            self.assertEqual(N.parse(data['ack']),{'kind':'ACK','line_hex':'474f0a'})
            ack_at=time.perf_counter()
            bulk_at=time.perf_counter();N.write_all(p.stdin,payload,time.monotonic()+5);p.stdin.close()
            p.wait(timeout=8)
            for t in ts:t.join(2)
            self.assertEqual(p.returncode,0)
            self.assertEqual(data['ready'],b'READ_ONLY_READY\r\n')
            self.assertEqual(N.parse(data['ack']),{'kind':'ACK','line_hex':'474f0a'})
            header,actual=data['rest'].split(b'\n',1)
            self.assertEqual(N.parse(header),{'kind':'BULK','bytes':len(payload),'sha256':N.sha(payload),'eof':True})
            self.assertEqual(actual,payload)
            baseline=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-Command','exit 0'],capture_output=True,timeout=10)
            self.assertEqual(data['stderr'],baseline.stderr+payload[::-1])
            self.assertLessEqual(go_at,ack_at);self.assertLess(ack_at,bulk_at)
            out=data['ready']+data['ack']+data['rest']
            (HOST/'local-proxy.stdout.raw').write_bytes(out);(HOST/'local-proxy.stderr.raw').write_bytes(data['stderr'])
            (HOST/'local-proxy-observation.json').write_bytes(N.encode({'HOST_ONLY':True,'SDK':0,'SSH':0,
                'small_GO_before_bulk':True,'GO':go_at,'ACK':ack_at,'BULK':bulk_at,'bytes':len(payload),'sha256':N.sha(payload),
                'exit':p.returncode,'EOF':True,'startup_stderr_prefix_bytes':len(baseline.stderr)}))
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=3)
            for stream in (p.stdin,p.stdout,p.stderr):
                if not stream.closed:stream.close()

    def test_03_actual_blocked_child_original_deadline_and_early_exit_with_stdin_open(self):
        at=time.monotonic()
        p=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-Command',N.proxy_command(EXE,'import time;time.sleep(10)',20.5)],
                         input=b'',capture_output=True,timeout=6)
        self.assertEqual(p.returncode,124,p.stderr.decode('utf8','replace'));self.assertLess(time.monotonic()-at,5)
        p=subprocess.Popen([str(PS),'-NoProfile','-NonInteractive','-Command',N.proxy_command(EXE,'raise SystemExit(37)',30.)],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(p.wait(timeout=5),37)
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=3)
            for stream in (p.stdin,p.stdout,p.stderr):stream.close()


class AuthorityHost(unittest.TestCase):
    def fixture(self):
        root=HOST/uuid.uuid4().hex;out=root/'new';out.mkdir(parents=True);old=root/'old';old.mkdir()
        origin=root/'origin';origin.mkdir();grant=origin/'grant.bin';reply=origin/'reply.bin';source=root/'source.bin'
        grant.write_bytes(b'HOST_ONLY_ORIGINAL_GRANT');reply.write_bytes(b'HOST_ONLY_ORIGINAL_REPLY');source.write_bytes(b'HOST_ONLY_SOURCE')
        record={'run_id':'f'*32,'nonce':'a'*32,'driver_sha256':'1'*64,'bundle_sha256':N.sha(b'HOST_ONLY_PAYLOAD'),'bundle_bytes':17,'job_sha256':'2'*64}
        run=old/'runs'/record['run_id'];run.mkdir(parents=True);(run/'bundle.zip').write_bytes(b'HOST_ONLY_PAYLOAD')
        M=types.SimpleNamespace(grant_records=lambda p:(grant.read_bytes(),reply.read_bytes()))
        a=N.Authority(N.encode(record),b'{}',b'HOST_ONLY_PAYLOAD',tuple((str(p),p.read_bytes()) for p in (grant,reply,source)),
            grant.read_bytes(),reply.read_bytes(),N.PERIOD_END,N.encode({'own_readonly_target_probe':1,'actual_prior_SDK':0,'SDK_max':1,'source_freeze_sha256':'3'*64,'target_probe_sha256':'4'*64,
                'period':{'mode':'old','start':N.PERIOD_START,'end':N.PERIOD_END,'grant_sha256':None,'reply_sha256':None}}))
        return root,out,old,origin,M,a,record,grant,reply,source

    def test_04_partial_write_all_exact_and_stalled_contract_rejects(self):
        class Partial:
            def __init__(self):self.data=bytearray()
            def write(self,data):n=min(3,len(data));self.data.extend(data[:n]);return n
        p=Partial();self.assertEqual(N.write_all(p,bytes(range(256)),time.monotonic()+2),256);self.assertEqual(p.data,bytes(range(256)))
        for value in (0,None,-1,999,True):
            with self.assertRaises(ValueError):N.write_all(types.SimpleNamespace(write=lambda b:value),b'abc',time.monotonic()+1)

    def test_05_same_old_period_ownexclusive_firstGO_partial_and_duplicate(self):
        root,out,old,origin,M,a,record,*_=self.fixture();now=lambda:N.PERIOD_END-1500
        with mock.patch.multiple(N,OLD=old,ORIGIN=origin):
            c=N.admit(a,M,out,now)
            self.assertEqual(c.consumed.end,N.PERIOD_END)
            class Partial:
                def __init__(self):self.data=bytearray();self.flushes=0
                def write(self,b):n=min(7,len(b));self.data.extend(b[:n]);return n
                def flush(self):self.flushes+=1
            p=Partial();c.sender(p,dict(record,kind='READY',remote_ready=10.),N.PERIOD_END-2,now)
            go,payload=bytes(p.data).split(b'\n',1);self.assertEqual(N.parse(go),dict(record,kind='GO'));self.assertEqual(payload,a.bundle)
            self.assertGreaterEqual(p.flushes,2)
            with self.assertRaises(ValueError):c.sender(p,dict(record,kind='READY',remote_ready=10.),N.PERIOD_END-2,now)
            self.assertFalse((out/'run-result.json').exists());self.assertTrue((out/'GO.json').exists())

    def test_06_current_origin_source_grant_snapshot_seal_and_headroom_deny(self):
        for role in ('grant','reply','source','snapshot','seal'):
            root,out,old,origin,M,a,record,grant,reply,source=self.fixture();now=lambda:N.PERIOD_END-1500
            with mock.patch.multiple(N,OLD=old,ORIGIN=origin):
                c=N.admit(a,M,out,now)
                p={'grant':grant,'reply':reply,'source':source,'snapshot':out/'continuation-snapshot.json','seal':out/'admission.json'}[role]
                p.write_bytes(p.read_bytes()+b'CHANGED')
                with self.assertRaises(ValueError):c.sender(io.BytesIO(),dict(record,kind='READY',remote_ready=10.),N.PERIOD_END-2,now)
                self.assertFalse((out/'GO.json').exists())
        root,out,old,origin,M,a,*_=self.fixture();before=set(out.iterdir())
        with mock.patch.multiple(N,OLD=old,ORIGIN=origin):
            with self.assertRaises(ValueError):N.admit(a,M,out,now=lambda:N.PERIOD_END-1222)
        self.assertEqual(set(out.iterdir()),before)

    def test_07_actual_probe_raw_wire_rejects_coherent_sha_only_reseal(self):
        out=HOST/uuid.uuid4().hex;(out/'target-probe').mkdir(parents=True);payload=bytes(range(256))*4096
        wire=b'READ_ONLY_READY\r\n'+N.encode({'kind':'ACK','line_hex':'474f0a'})+b'\r\n'+N.encode({'kind':'BULK','bytes':len(payload),'sha256':N.sha(payload),'eof':True})+b'\r\n'+payload
        p=out/'target-probe/stdout.txt';e=out/'target-probe/stderr.txt';p.write_bytes(wire);e.write_bytes(payload[::-1])
        record={'unit':123,'kind':'ACTUAL_NO_SDK_TARGET_PROBE','source_driver_sha256':N.sha((HERE/'driver.py').read_bytes()),'source_freeze_sha256':'3'*64,
            'process':{'raw_complete':True,'terminal':True,'child_state':'REAPED','actual_child_exit_code':0,'job_active_after':0},
            'small_GO_before_bulk':True,'eof':True,'all256duplex':True,'SDK_initializations':0,'SSH_readonly_launches':1,
            'stdout_sha256':N.sha(wire),'stderr_sha256':N.sha(payload[::-1])}
        events=[{'event':name,'time':float(i)} for i,name in enumerate(('GO_WRITTEN','ACK_OBSERVED','BULK_START','BULK_DONE'))]
        eb=N.encode(events);(out/'target-probe/sender-events.json').write_bytes(eb);record['sender_events_sha256']=N.sha(eb)
        meta=out/'target-probe.json';meta.write_bytes(N.encode(record));files=[]
        self.assertEqual(N.target_probe(files,'3'*64,out),1)
        p.write_bytes(wire[:-1]+b'X');record['stdout_sha256']=N.sha(p.read_bytes());meta.write_bytes(N.encode(record))
        with self.assertRaises(ValueError):N.target_probe([],'3'*64,out)
        p.write_bytes(wire);record['stdout_sha256']=N.sha(wire)
        events[1]['time']=events[2]['time'];eb=N.encode(events)
        (out/'target-probe/sender-events.json').write_bytes(eb);record['sender_events_sha256']=N.sha(eb);meta.write_bytes(N.encode(record))
        with self.assertRaisesRegex(ValueError,'ACK'):N.target_probe([],'3'*64,out)


    def test_08_no_retired_entry_calls_and_readonly_current160_authority(self):
        import ast
        tree=ast.parse((HERE/'driver.py').read_text());calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)]
        for name in ('T.run','M.run','M.admit','M.actual_probe'):self.assertNotIn(name,calls)
        M,T,D=N.load_helpers();folder=HOST/uuid.uuid4().hex;folder.mkdir();f=folder/'HOST_ONLY_REVIEW_SEAM';f.write_bytes(b'HOST_ONLY')
        with mock.patch.object(N,'source_gate',return_value=([(str(f),f.read_bytes())],'3'*64)):
            a=N.capture_authority(M,T,D,folder,require_target_probe=False)
        self.assertEqual(len(a.bundle),40710375);self.assertEqual(a.end,389263.421)
        self.assertEqual(N.parse(a.counts_raw)['own_readonly_target_probe'],0)
        with self.assertRaises(ValueError):N.admit(a,M,folder,now=lambda:N.PERIOD_END-1500)

class FreshDataHost(unittest.TestCase):
    def setup_fresh(self):
        base=AuthorityHost();root,out,old,origin,M,a,record,grant,reply,source=base.fixture()
        start=N.PERIOD_END+1000.;now=lambda:start+1.
        r={'unit':123,'kind':'ACTUAL_USER_REPLY','approved':True,'duration_s':2700,'hardware_approved':False,
           'reply_text':'HOST_ONLY_NOT_ACTUAL_FRESH_APPROVAL','conversation_ref':'HOST_ONLY'}
        g={'unit':123,'kind':'EXPLICIT_ADDITIONAL_SIMULATION_BUDGET','approved':True,'duration_s':2700,'hardware_approved':False,
           'reply_sha256':N.sha(N.encode(r)),'source_freeze_sha256':'3'*64,'target_probe_sha256':'4'*64,
           'original_121_grant_sha256':N.FACTS['outputs/mp18-budget-run-121/user-budget-grant.json'],
           'original_121_transport_sha256':N.FACTS['outputs/mp18-budget-run-121/transport.json'],
           'grant_nonce':'c'*32,'started_monotonic':start,'deadline_monotonic':start+2700.}
        (out/'user-budget-reply.json').write_bytes(N.encode(r));(out/'user-budget-grant.json').write_bytes(N.encode(g))
        return root,out,old,origin,M,a,record,r,g,now

    def test_09_actual_fresh_absence_and_old_headroom_refusal_has_no_mutations(self):
        self.assertFalse((N.OUT/'user-budget-grant.json').exists());self.assertFalse((N.OUT/'user-budget-reply.json').exists())
        before=[(N.OUT/x).exists() for x in ('admission.json','GO.json','run-result.json','pipeline-attempt.json')]
        with mock.patch.object(N,'load_helpers',side_effect=AssertionError('NO_IMPORT_OR_RPC')):
            with self.assertRaisesRegex(ValueError,'headroom'):N.run()
        self.assertEqual(before,[(N.OUT/x).exists() for x in ('admission.json','GO.json','run-result.json','pipeline-attempt.json')])

    def test_10_fresh_closed_schema_period_and_fixed_data_DAG_negatives(self):
        for key,value in [('approved',False),('duration_s',True),('started_monotonic',True),('deadline_monotonic',1.),
                          ('source_freeze_sha256','5'*64),('target_probe_sha256','5'*64),('original_121_grant_sha256','5'*64),
                          ('original_121_transport_sha256','5'*64),('extra','notclosed')]:
            root,out,old,origin,M,a,record,r,g,now=self.setup_fresh();g[key]=value;(out/'user-budget-grant.json').write_bytes(N.encode(g))
            with self.assertRaises(ValueError):N.select_period('3'*64,'4'*64,out,now)
            self.assertFalse((out/'admission.json').exists())
        root,out,old,origin,M,a,record,r,g,now=self.setup_fresh()
        for at in (g['started_monotonic']-1,g['deadline_monotonic']):
            with self.assertRaises(ValueError):N.select_period('3'*64,'4'*64,out,now=lambda:at)
        (out/'user-budget-reply.json').unlink()
        with self.assertRaises(ValueError):N.select_period('3'*64,'4'*64,out,now)
        self.assertFalse((out/'admission.json').exists())

    def test_11_fresh_fixed_period_and_raw_current_bridge_to_firstGO(self):
        root,out,old,origin,M,a,record,r,g,now=self.setup_fresh()
        period,files=N.select_period('3'*64,'4'*64,out,now)
        meta=N.parse(a.counts_raw);meta['period']=period
        a=a._replace(end=period['end'],files=tuple([*a.files,*files]),counts_raw=N.encode(meta))
        with mock.patch.multiple(N,OLD=old,ORIGIN=origin):
            c=N.admit(a,M,out,now)
            self.assertEqual(c.consumed.end,g['deadline_monotonic']);self.assertNotEqual(c.consumed.end,now()+2700)
            sink=io.BytesIO();c.sender(sink,dict(record,kind='READY',remote_ready=10.),g['deadline_monotonic']-2,now)
            line,body=sink.getvalue().split(b'\n',1);self.assertEqual(N.parse(line),dict(record,kind='GO'));self.assertEqual(body,a.bundle)
            with self.assertRaises(ValueError):N.admit(a,M,out,now)

    def test_12_fresh_revocation_disappearance_and_old_mode_appearance_deny_GO0(self):
        for change in ('revoke','delete_one','delete_both','reseal'):
            root,out,old,origin,M,a,record,r,g,now=self.setup_fresh();period,files=N.select_period('3'*64,'4'*64,out,now)
            meta=N.parse(a.counts_raw);meta['period']=period;a=a._replace(end=period['end'],files=tuple([*a.files,*files]),counts_raw=N.encode(meta))
            with mock.patch.multiple(N,OLD=old,ORIGIN=origin):
                c=N.admit(a,M,out,now)
                if change=='revoke':g['approved']=False;(out/'user-budget-grant.json').write_bytes(N.encode(g))
                if change=='delete_one':(out/'user-budget-reply.json').unlink()
                if change=='delete_both':(out/'user-budget-grant.json').unlink();(out/'user-budget-reply.json').unlink()
                if change=='reseal':g['deadline_monotonic']+=2700;(out/'user-budget-grant.json').write_bytes(N.encode(g))
                with self.assertRaises((ValueError,FileNotFoundError)):c.sender(io.BytesIO(),dict(record,kind='READY',remote_ready=10.),a.end-2,now)
                self.assertFalse((out/'GO.json').exists())
        root,out,old,origin,M,a,record,*_=AuthorityHost().fixture();now=lambda:N.PERIOD_END-1500
        with mock.patch.multiple(N,OLD=old,ORIGIN=origin):
            c=N.admit(a,M,out,now);(out/'user-budget-grant.json').write_bytes(b'INVALID_FRESH_APPEARED')
            with self.assertRaises(ValueError):c.sender(io.BytesIO(),dict(record,kind='READY',remote_ready=10.),a.end-2,now)
            self.assertFalse((out/'GO.json').exists())

    def test_13_probe_coherent_reseal_changes_pinned_grant_probe_rawhash(self):
        root,out,old,origin,M,a,record,r,g,now=self.setup_fresh()
        N.select_period('3'*64,'4'*64,out,now)
        # Even a separately self-consistent probe would now have different raw JSON bytes.
        with self.assertRaisesRegex(ValueError,'DAG'):N.select_period('3'*64,'5'*64,out,now)


    def test_14_original121_consumer_result_guard_normal_opaque_and_reparse_negative(self):
        import zipfile
        M,T,D=N.load_helpers()
        for invalid in (False,True):
            root,out,old,origin,fake,a,record,*_=AuthorityHost().fixture();run=old/'runs'/record['run_id']
            # Original121 guard requires the exact original119 run id; this remains HOST-only data.
            actual_record=dict(record,run_id=D.read(N.OLD/'prepared.json')['run_id'])
            actual_run=old/'runs'/actual_record['run_id'];actual_run.mkdir(exist_ok=True)
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:z.writestr('process.json',b'{}');z.writestr('recovery-seal.json',b'{}');z.writestr('imported/opaque.native-cache',b'HOST_ONLY')
            archive=buf.getvalue();ready=dict(actual_record,kind='READY',remote_ready=10.)
            header={'kind':'RESULT','run_id':actual_record['run_id'],'nonce':actual_record['nonce'],'bytes':len(archive),'sha256':N.sha(archive)}
            packet=N.encode(ready)+b'\n'+N.encode(header)+b'\n'+archive;calls=[]
            consumer=types.SimpleNamespace(C=D.C,_safe_name=D._safe_name,verify_native_result=lambda *x:(calls.append('HOST_ONLY'),2)[1])
            original=Path.is_junction
            def metadata(path):return invalid and Path(path)==actual_run or original(path)
            with mock.patch.object(M,'OLD',old),mock.patch.object(Path,'is_junction',metadata):
                if invalid:
                    with self.assertRaises(ValueError):M.consume_result(consumer,packet,actual_record,actual_run,out)
                    self.assertFalse((actual_run/'retrieved').exists());self.assertFalse(calls)
                else:
                    self.assertEqual(M.consume_result(consumer,packet,actual_record,actual_run,out),2)
                    self.assertEqual(len(calls),1)

    def test_15_runtime_output_collision_is_separated_and_final_gate_schema(self):
        self.assertTrue((N.OUT/'preparation-result.json').is_file())
        self.assertFalse((N.OUT/'run-result.json').exists())
        M,T,D=N.load_helpers();out=HOST/uuid.uuid4().hex;(out/'review').mkdir(parents=True)
        paths=['src/simulation/mp18_ssh_raw_stdin_123/driver.py','src/simulation/mp18_ssh_raw_stdin_123/test_driver.py','docs/design/123-ssh-raw-stdin-continuation.md']
        f={'unit':123,'HOST_ONLY':True,'files':{p:{'sha256':N.sha((N.ROOT/p).read_bytes()),'bytes':(N.ROOT/p).stat().st_size} for p in paths}}
        fr=N.encode(f);(out/'review/source-freeze.json').write_bytes(fr)
        r={'unit':123,'phase':'L4','round':2,'non_author':True,'verdict':'PASS','unmet':0,'unresolved_count':0,'source_freeze_sha256':N.sha(fr),'HOST_ONLY':True}
        for who in ('main','lens'):(out/('review/'+who+'-L4-final.json')).write_bytes(N.encode(r))
        self.assertEqual(N.source_gate(M,D,out)[1],N.sha(fr))
        for key,value in [('round',True),('non_author',False),('unresolved_count',1),('source_freeze_sha256','0'*64)]:
            (out/'review/main-L4-final.json').write_bytes(N.encode(dict(r,**{key:value})))
            with self.assertRaises(ValueError):N.source_gate(M,D,out)


if __name__=='__main__':unittest.main(verbosity=2)
