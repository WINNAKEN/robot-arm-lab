"""121 HOST-only admission proofs. Synthetic grants live only under HOST, never canonical OUT."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
import types
import unittest
from unittest import mock
import uuid
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('budget121_host',HERE/'driver.py')
M=importlib.util.module_from_spec(spec);sys.modules[spec.name]=M;spec.loader.exec_module(M)
HOST=M.OUT/'HOST';HOST.mkdir(exist_ok=True)


class Fixture:
    def __init__(self):
        self.root=HOST/uuid.uuid4().hex;self.out=self.root/'new';self.out.mkdir(parents=True)
        self.old=self.root/'old';self.old.mkdir();self.previous=self.root/'previous';self.previous.mkdir()
        self.run=self.old/'runs'/M.RUN_ID;self.run.mkdir(parents=True)
        self.source=self.root/'source.bin';self.source.write_bytes(b'HOST_ONLY_SOURCE')
        self.cap=self.root/'caps.json';self.cap.write_bytes(b'{"J2":12,"J3":7}')
        self.marker=self.old/'native-attempt.json';self.marker.write_bytes(b'{"global_deadline_monotonic":379751.359,"SDK_attempts":1,"retry":0}')
        self.transport=self.run/'transport.json';self.transport.write_bytes(b'HOST_ONLY_EXACT_PRE_PYTHON_PARSE_FAILURE')
        self.error=self.run/'stderr.txt';self.error.write_bytes(b'ParserError UnexpectedToken -I -B python.exe HOST_ONLY')
        self.bundle=self.run/'bundle.zip';self.bundle.write_bytes(bytes(range(256))*4096)
        self.record={'run_id':M.RUN_ID,'nonce':'a'*32,'bundle_sha256':M.digest(self.bundle.read_bytes()),
                     'bundle_bytes':self.bundle.stat().st_size,'job_sha256':'8'*64,'driver_sha256':'9'*64}
        self.files=(self.source,self.cap,self.marker,self.transport,self.error)
        self.frozen='1'*64
        self.write_grant()
    def proof(self):
        return M.Probe(M.encode(self.record),self.cap.read_bytes(),self.bundle.read_bytes(),
            tuple((str(p),p.read_bytes()) for p in self.files),str(self.run),self.frozen,
            M.digest(self.marker.read_bytes()),M.digest(self.transport.read_bytes()),M.digest(self.error.read_bytes()))
    def write_grant(self):
        self.e={'unit':121,'kind':'ACTUAL_USER_REPLY','approved':True,'duration_s':2700,'hardware_approved':False,
                'reply_text':'HOST_ONLY_SYNTHETIC_USER_REPLY_NOT_AN_ACTUAL_APPROVAL','conversation_ref':'HOST_ONLY_FIXTURE'}
        self.g={'unit':121,'kind':'NEW_SIMULATION_BUDGET','approved':True,'duration_s':2700,'hardware_approved':False,
                'reply_sha256':M.digest(M.encode(self.e)),'source_freeze_sha256':self.frozen,'original_run_id':M.RUN_ID,
                'original_attempt_sha256':M.digest(self.marker.read_bytes()),'original_transport_sha256':M.digest(self.transport.read_bytes()),
                'original_stderr_sha256':M.digest(self.error.read_bytes()),'grant_nonce':'b'*32}
        (self.out/'user-budget-reply.json').write_bytes(M.encode(self.e));(self.out/'user-budget-grant.json').write_bytes(M.encode(self.g))
    def context(self):
        return mock.patch.multiple(M,OLD=self.old,PREVIOUS=self.previous)
    def admit(self):
        return M.admit(self.proof,self.out,now=lambda:1000.)
    def ready(self):return dict(self.record,kind='READY',remote_ready=2000.)


class AdmissionTests(unittest.TestCase):
    def test_actual_canonical_grant_absent_run_rejects_before_import_or_write(self):
        self.assertFalse((M.OUT/'user-budget-grant.json').exists())
        self.assertFalse((M.OUT/'user-budget-reply.json').exists())
        before={p.relative_to(M.OUT).as_posix() for p in M.OUT.rglob('*') if p.is_file()}
        with mock.patch.object(M,'load_library',side_effect=AssertionError('MUST_NOT_LOAD_REFERENCE')):
            with self.assertRaises(FileNotFoundError):M.run()
        after={p.relative_to(M.OUT).as_posix() for p in M.OUT.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        self.assertFalse((M.OUT/'admission.json').exists())

    def test_grant_closed_types_and_reply_binding_reject_before_consumption(self):
        for key,value in [('approved',False),('approved',1),('duration_s',True),('duration_s',2699),('hardware_approved',True),
                          ('kind','CAP_APPROVAL'),('unexpected',1),('reply_sha256','0'*64),('grant_nonce','not-a-nonce')]:
            f=Fixture();f.g[key]=value;(f.out/'user-budget-grant.json').write_bytes(M.encode(f.g))
            with f.context():
                with self.assertRaises(ValueError):f.admit()
            self.assertFalse((f.out/'admission.json').exists());self.assertFalse((f.out/'consumed-snapshot.json').exists())
        f=Fixture();(f.out/'user-budget-grant.json').write_bytes(b'{"unit":121,"unit":121}')
        with self.assertRaises(ValueError):M.grant_records(f.out)
        f=Fixture();(f.out/'user-budget-reply.json').unlink()
        with self.assertRaises(FileNotFoundError):M.grant_records(f.out)

    def test_no_new_grant_from_old_cap_decision_or_missing_reply_text(self):
        f=Fixture();f.e['reply_text']='';(f.out/'user-budget-reply.json').write_bytes(M.encode(f.e));f.g['reply_sha256']=M.digest(M.encode(f.e));(f.out/'user-budget-grant.json').write_bytes(M.encode(f.g))
        with self.assertRaises(ValueError):M.grant_records(f.out)
        f=Fixture();f.g['kind']='119_SIMULATION_CAP';(f.out/'user-budget-grant.json').write_bytes(M.encode(f.g))
        with self.assertRaises(ValueError):M.grant_records(f.out)

    def test_new_period2700_and_old_bytes_unchanged_single_closed_go(self):
        f=Fixture();old=f.marker.read_bytes()
        with f.context():
            a=f.admit();self.assertEqual(a.captured.end-a.captured.start,2700.)
            self.assertEqual(a.captured.end,3700.);self.assertEqual(f.marker.read_bytes(),old)
            stream=io.BytesIO();at=time.perf_counter();a.first_go(stream,f.ready(),3698.,now=lambda:1001.)
            elapsed=time.perf_counter()-at
            go,payload=stream.getvalue().split(b'\n',1)
            self.assertEqual(M.parse(go),dict(f.record,kind='GO'));self.assertEqual(payload,f.bundle.read_bytes())
            self.assertNotIn('grant_nonce',M.parse(go))
            self.assertEqual(M.parse((f.out/'GO.json').read_bytes())['grant_nonce'],'b'*32)
            with self.assertRaises(ValueError):a.first_go(io.BytesIO(),f.ready(),3698.,now=lambda:1001.)
        self.assertEqual(old,f.marker.read_bytes())
        print(json.dumps({'HOST_ONLY':'SYNTHETIC_ADMISSION','new_period_s':2700,'old_end':M.OLD_END,'GO_elapsed_s':elapsed,'SDK':0,'SSH':0}),flush=True)

    def test_after_dispatch_raw_grant_reply_and_revocation_mutations_deny_go0(self):
        for which in ('grant','reply','delete_grant','delete_reply'):
            f=Fixture()
            with f.context():
                a=f.admit()
                p=f.out/('user-budget-reply.json' if 'reply' in which else 'user-budget-grant.json')
                if which.startswith('delete'):p.unlink()
                else:
                    v=M.parse(p.read_bytes());v['approved']=False;p.write_bytes(M.encode(v))
                stream=io.BytesIO()
                with self.assertRaises((ValueError,FileNotFoundError)):a.first_go(stream,f.ready(),3698.,now=lambda:1001.)
                self.assertEqual(stream.getvalue(),b'');self.assertFalse((f.out/'GO.json').exists())

    def test_after_dispatch_source_payload_cap_oldfailure_each_deny_go0(self):
        for which in ('source','bundle','cap','marker','transport','error'):
            f=Fixture()
            with f.context():
                a=f.admit();p=getattr(f,which);p.write_bytes(p.read_bytes()+b'CHANGED')
                stream=io.BytesIO()
                with self.assertRaises(ValueError):a.first_go(stream,f.ready(),3698.,now=lambda:1001.)
                self.assertEqual(stream.getvalue(),b'');self.assertFalse((f.out/'GO.json').exists())

    def test_snapshot_and_coherent_self_resealed_admission_deny_against_memory(self):
        for which in ('snapshot','seal','coherent'):
            f=Fixture()
            with f.context():
                a=f.admit();sp=f.out/'consumed-snapshot.json';se=f.out/'admission.json'
                if which in ('snapshot','coherent'):
                    v=M.parse(sp.read_bytes());v['deadline_monotonic']+=2700;sp.write_bytes(M.encode(v))
                if which in ('seal','coherent'):
                    v=M.parse(se.read_bytes());v['snapshot_sha256']=M.digest(sp.read_bytes());v['deadline_monotonic']+=2700;se.write_bytes(M.encode(v))
                stream=io.BytesIO()
                with self.assertRaises(ValueError):a.first_go(stream,f.ready(),6398.,now=lambda:1001.)
                self.assertEqual(stream.getvalue(),b'');self.assertFalse((f.out/'GO.json').exists())

    def test_prior120_or121_or_actual_sdk_or_result_markers_deny(self):
        for target in ('previous_admission','previous_GO','old_result','run_GO','run_output','retrieved','new_admission','snapshot','transport'):
            f=Fixture();paths={'previous_admission':f.previous/'admission.json','previous_GO':f.previous/'GO.json',
                'old_result':f.old/'native-result.json','run_GO':f.run/'GO.json','run_output':f.run/'output',
                'retrieved':f.run/'retrieved','new_admission':f.out/'admission.json','snapshot':f.out/'consumed-snapshot.json','transport':f.out/'transport'}
            paths[target].write_bytes(b'EXISTING_HOST_ONLY')
            with f.context():
                with self.assertRaises(ValueError):f.admit()

    def test_duplicate_admission_and_preexisting_exclusive_go_rejected(self):
        f=Fixture()
        with f.context():
            a=f.admit()
            with self.assertRaises(ValueError):f.admit()
            (f.out/'GO.json').write_bytes(b'EXISTING')
            with self.assertRaises((ValueError,FileExistsError)):a.first_go(io.BytesIO(),f.ready(),3698.,now=lambda:1001.)
            self.assertEqual((f.out/'GO.json').read_bytes(),b'EXISTING')

    def test_late_ready_wrong_identity_and_unknown_keys_deny_without_go(self):
        for kind in ('late','nonce','extra','nonfinite'):
            f=Fixture()
            with f.context():
                a=f.admit();ready=f.ready()
                if kind=='nonce':ready['nonce']='c'*32
                if kind=='extra':ready['extra']=True
                if kind=='nonfinite':ready['remote_ready']=float('nan')
                stream=io.BytesIO()
                with self.assertRaises(ValueError):a.first_go(stream,ready,3698.,now=lambda:1021. if kind=='late' else 1001.)
                self.assertFalse((f.out/'GO.json').exists());self.assertEqual(stream.getvalue(),b'')

    def test_actual_accepted120_current_payload_and_fast_go_proof(self):
        T,D=M.load_library();T.gates(D)
        actual_marker=(M.OLD/'native-attempt.json').read_bytes()
        out=HOST/('actual-current-'+uuid.uuid4().hex);out.mkdir()
        own=out/'HOST_ONLY_121_REVIEW.bin';own.write_bytes(b'HOST_ONLY_121_REVIEW_SEAM_NOT_L4_AUTHORITY')
        # Only new121 review admission is a HOST seam. Existing119/120 validators and full payload are actual.
        with mock.patch.object(M,'source_gate',return_value=('1'*64,[(own,own.read_bytes())])):
            proof=M.actual_probe(T,D,out)
        self.assertEqual(len(proof.bundle),40710375);self.assertEqual(M.parse(proof.record_raw)['run_id'],M.RUN_ID)
        at=time.perf_counter();M.refresh_proof(proof,out);elapsed=time.perf_counter()-at
        self.assertLess(elapsed,10.)
        e={'unit':121,'kind':'ACTUAL_USER_REPLY','approved':True,'duration_s':2700,'hardware_approved':False,
           'reply_text':'HOST_ONLY_SYNTHETIC_NOT_AN_ACTUAL_USER_APPROVAL','conversation_ref':'HOST_ONLY_REALPAYLOAD_SEAM'}
        g={'unit':121,'kind':'NEW_SIMULATION_BUDGET','approved':True,'duration_s':2700,'hardware_approved':False,
           'reply_sha256':M.digest(M.encode(e)),'source_freeze_sha256':proof.source_freeze_sha256,'original_run_id':M.RUN_ID,
           'original_attempt_sha256':proof.attempt_sha256,'original_transport_sha256':proof.transport_sha256,
           'original_stderr_sha256':proof.stderr_sha256,'grant_nonce':'b'*32}
        (out/'user-budget-reply.json').write_bytes(M.encode(e));(out/'user-budget-grant.json').write_bytes(M.encode(g))
        a=M.admit(lambda:proof,out,now=lambda:1000.)
        class Sink:
            def __init__(self):self.go=None;self.size=0;self.hash=hashlib.sha256()
            def write(self,block):
                if self.go is None:self.go=M.parse(block)
                else:self.hash.update(block);self.size+=len(block)
            def flush(self):pass
        sink=Sink();at=time.perf_counter()
        a.first_go(sink,dict(M.parse(proof.record_raw),kind='READY',remote_ready=2000.),3698.,now=lambda:1001.)
        full_go_elapsed=time.perf_counter()-at
        self.assertEqual(sink.size,40710375);self.assertEqual(sink.hash.hexdigest(),M.parse(proof.record_raw)['bundle_sha256'])
        self.assertEqual(sink.go,dict(M.parse(proof.record_raw),kind='GO'));self.assertLess(full_go_elapsed,10.)
        print(json.dumps({'HOST_ONLY':'FULL_FIRST_GO_REAL_PAYLOAD_MEMORY_SINK','elapsed_s':full_go_elapsed,'bundle_bytes':sink.size,'canonical_grant_created':False,'SDK':0,'SSH':0}),flush=True)
        self.assertEqual((M.OLD/'native-attempt.json').read_bytes(),actual_marker)
        self.assertEqual(T.sha(T.HERE/'driver.py'), 'ae3b90c941b55035942b58e732d8256b4b58537c1ed261f6f4c2b71637650b27')
        print(json.dumps({'HOST_ONLY':'ACTUAL119_PAYLOAD120_GATES_FAKE121_REVIEW_SEAM','bundle_bytes':len(proof.bundle),'fast_current_GO_proof_s':elapsed,'old_deadline':M.OLD_END,'SDK':0,'SSH':0}),flush=True)

    def test_no_retired120_run_or_source_replacement(self):
        import ast
        source=(HERE/'driver.py').read_text();tree=ast.parse(source)
        calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)]
        self.assertNotIn('T.run',calls);self.assertNotIn('D.run_remote',calls)
        self.assertFalse(any('replace' in c and c.startswith(('T.','D.')) for c in calls))
        self.assertEqual(M.parse(b'{"a":1}'),{'a':1})
        for raw in (b'{"a":NaN}',b'{"a":Infinity}',b'{"a":1,"a":2}'):
            with self.assertRaises(ValueError):M.parse(raw)

    def test_closed_result_nonce_scope_duplicate_and_original_consumer(self):
        f=Fixture();record=f.record
        class Contract:
            @staticmethod
            def path_in(root,name):
                M.need('..' not in Path(name).parts and not Path(name).is_absolute(),'Unsafe');return root/name
        consumer=mock.Mock(return_value=2)
        D=types.SimpleNamespace(C=Contract,_safe_name=lambda n:Contract.path_in(Path('.'),n),verify_native_result=consumer)
        def packet(entries,nonce=None,extra=False):
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:
                for k,v in entries:z.writestr(k,v)
            raw=buf.getvalue();header={'kind':'RESULT','run_id':record['run_id'],'nonce':nonce or record['nonce'],'bytes':len(raw),'sha256':M.digest(raw)}
            if extra:header['extra']=1
            return M.encode(f.ready())+b'\n'+M.encode(header)+b'\n'+raw
        entries=[('process.json',b'{}'),('recovery-seal.json',b'{}')]
        with f.context():
            for raw in (packet(entries,nonce='c'*32),packet(entries,extra=True),packet(entries+[('../source/driver.py',b'bad')]),packet(entries+[('process.json',b'duplicate')])):
                with self.assertRaises(ValueError):M.consume_result(D,raw,record,f.run,f.out)
                self.assertFalse((f.run/'retrieved').exists());consumer.assert_not_called()
            self.assertEqual(M.consume_result(D,packet(entries+[('imported/opaque.native-cache',b'HOST_ONLY_OPAQUE_DATA')]),record,f.run,f.out),2)
            consumer.assert_called_once()
            with self.assertRaises(ValueError):M.consume_result(D,packet(entries),record,f.run,f.out)

    def test_two_concurrent_dispatches_have_one_exclusive_admission(self):
        import concurrent.futures
        import threading
        f=Fixture();barrier=threading.Barrier(2);original=M.exclusive
        def together(path,raw,out=M.OUT):
            if Path(path).name=='admission.json':barrier.wait(timeout=5)
            return original(path,raw,out)
        def attempt():
            try:return ('ADMITTED',f.admit())
            except (FileExistsError,ValueError) as e:return (type(e).__name__,None)
        with f.context(),mock.patch.object(M,'exclusive',side_effect=together):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda x:attempt(),range(2)))
        self.assertEqual(sum(r[0]=='ADMITTED' for r in results),1)
        self.assertTrue((f.out/'admission.json').exists());self.assertTrue((f.out/'consumed-snapshot.json').exists())
        self.assertFalse((f.out/'GO.json').exists())

    def test_grant_revoked_during_readonly_capture_has_snapshot0_and_ssh0(self):
        f=Fixture()
        def mutate_during_capture():
            proof=f.proof();f.g['approved']=False;(f.out/'user-budget-grant.json').write_bytes(M.encode(f.g));return proof
        with f.context():
            with self.assertRaises(ValueError):M.admit(mutate_during_capture,f.out,now=lambda:1000.)
        self.assertFalse((f.out/'admission.json').exists());self.assertFalse((f.out/'consumed-snapshot.json').exists())

    def test_121_source_gate_requires_current_source_and_typed_final_nonauthor_reviews(self):
        out=HOST/('source-gate-'+uuid.uuid4().hex);(out/'review').mkdir(parents=True)
        paths=['src/simulation/mp18_budget_run_121/driver.py','src/simulation/mp18_budget_run_121/test_driver.py',
               'docs/design/121-explicit-user-budget-admission.md']
        freeze={'unit':121,'round':1,'HOST_ONLY_NOT_ACTUAL_SOURCE_ACCEPTANCE':True,
                'files':{n:{'sha256':M.digest((M.ROOT/n).read_bytes()),'bytes':(M.ROOT/n).stat().st_size} for n in paths}}
        freeze_path=out/'review/source-freeze.json';freeze_path.write_bytes(M.encode(freeze))
        valid={'unit':121,'phase':'L4','round':1,'non_author':True,'verdict':'PASS','unmet':0,'unresolved_count':0,
               'source_freeze_sha256':M.digest(M.encode(freeze)),'HOST_ONLY':True}
        for who in ('main','lens'):(out/('review/'+who+'-L4-final.json')).write_bytes(M.encode(valid))
        D=types.SimpleNamespace(C=types.SimpleNamespace(path_in=lambda root,name:root/name))
        sha,files=M.source_gate(D,out);self.assertEqual(sha,M.digest(freeze_path.read_bytes()));self.assertTrue(files)
        report_path=out/'review/main-L4-final.json'
        for key,value in [('unit',True),('phase','L2'),('round',True),('round',3),('non_author',False),
                          ('verdict','BLOCK'),('unmet',False),('unmet',1),('unresolved_count',False),('unresolved_count',1),('source_freeze_sha256','0'*64)]:
            mutant=dict(valid,**{key:value});report_path.write_bytes(M.encode(mutant))
            with self.assertRaises(ValueError):M.source_gate(D,out)
        report_path.write_bytes(M.encode(valid));freeze['files'][paths[0]]['sha256']='0'*64;freeze_path.write_bytes(M.encode(freeze))
        with self.assertRaises(ValueError):M.source_gate(D,out)

    def test_F2_original_root_run_destination_archive_member_reparse_roles_deny_before_write(self):
        roles=('run_self','run_ancestor','ROOT','destination','archive','member','member_parent','native_result')
        observations=[]
        for kind in ('junction','symlink'):
            for role in roles:
                f=Fixture();calls=[]
                D=types.SimpleNamespace(_safe_name=lambda n:M.need(not Path(n).is_absolute() and '..' not in Path(n).parts,'Safe relative member'),
                    verify_native_result=lambda *a:(calls.append('HOST_CONSUMER'),2)[1])
                buf=io.BytesIO()
                with zipfile.ZipFile(buf,'w') as z:
                    z.writestr('process.json',b'{}');z.writestr('recovery-seal.json',b'{}');z.writestr('imported/opaque.native-cache',b'HOST_ONLY_OPAQUE')
                archive=buf.getvalue();header={'kind':'RESULT','run_id':f.record['run_id'],'nonce':f.record['nonce'],'bytes':len(archive),'sha256':M.digest(archive)}
                packet=M.encode(f.ready())+b'\n'+M.encode(header)+b'\n'+archive
                destination=f.run/'retrieved'
                target={'run_self':f.run,'run_ancestor':f.run.parent,'ROOT':M.ROOT,'destination':destination,
                    'archive':f.run/'retrieved.zip','member':destination/'process.json','member_parent':destination/'imported',
                    'native_result':f.old/'native-result.json'}[role]
                method='is_junction' if kind=='junction' else 'is_symlink';original=getattr(Path,method)
                def invalid_metadata(path):return Path(path)==target or original(path)
                with f.context():
                    # Establish the HOST-only firstGO while every OS/path role is normal.
                    a=f.admit();a.first_go(io.BytesIO(),f.ready(),3698.,now=lambda:1001.)
                    with mock.patch.object(Path,method,invalid_metadata):
                        with self.assertRaises(ValueError):M.consume_result(D,packet,f.record,f.run,f.out)
                self.assertFalse(destination.exists());self.assertFalse((f.run/'retrieved.zip').exists());self.assertFalse(calls)
                observations.append({'metadata_only':True,'actual_OS_junction_created':False,'kind':kind,'role':role,
                    'destination_created':False,'archive_written':False,'consumer_calls':0,'denied':True})
        (HOST/'F2-reparse-role-observations.json').write_bytes(M.encode({'SDK':0,'SSH':0,'OS_link_attempts':0,'cases':observations}))

    def test_F2_roles_are_rechecked_after_preflight_and_before_consumer(self):
        for role in ('archive_after_mkdir','member_after_archive_open','native_result_before_consumer'):
            f=Fixture();calls=[];flag=[False]
            D=types.SimpleNamespace(_safe_name=lambda n:M.need('..' not in Path(n).parts,'Safe relative member'),
                verify_native_result=lambda *a:(calls.append('HOST_CONSUMER'),2)[1])
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:z.writestr('process.json',b'{}');z.writestr('recovery-seal.json',b'{}');z.writestr('opaque.native-cache',b'HOST_ONLY')
            archive=buf.getvalue();header={'kind':'RESULT','run_id':f.record['run_id'],'nonce':f.record['nonce'],'bytes':len(archive),'sha256':M.digest(archive)}
            packet=M.encode(f.ready())+b'\n'+M.encode(header)+b'\n'+archive
            dest,zip_path=f.run/'retrieved',f.run/'retrieved.zip'
            target=zip_path if role=='archive_after_mkdir' else dest/'process.json' if role=='member_after_archive_open' else f.old/'native-result.json'
            original_meta,original_mkdir,original_open=Path.is_junction,Path.mkdir,Path.open
            def metadata(path):return flag[0] and Path(path)==target or original_meta(path)
            def mkdir(path,*a,**kw):
                result=original_mkdir(path,*a,**kw)
                if Path(path)==dest and role=='archive_after_mkdir':flag[0]=True
                return result
            def opening(path,*a,**kw):
                result=original_open(path,*a,**kw)
                if Path(path)==zip_path and role!='archive_after_mkdir':flag[0]=True
                return result
            with f.context(),mock.patch.object(Path,'is_junction',metadata),mock.patch.object(Path,'mkdir',mkdir),mock.patch.object(Path,'open',opening):
                with self.assertRaises(ValueError):M.consume_result(D,packet,f.record,f.run,f.out)
            self.assertFalse(calls)
            if role=='archive_after_mkdir':self.assertFalse(zip_path.exists())
            if role=='member_after_archive_open':self.assertFalse((dest/'process.json').exists())
            self.assertFalse((f.old/'native-result.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
