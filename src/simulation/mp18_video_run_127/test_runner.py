"""127 HOST-only integration. One real generated package; synthetic SDK-less failure records, never SDK/SSH/Drive/Git."""
import ast
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import types
import unittest
from unittest import mock
import uuid
import zipfile

HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('runner127_HOST',HERE/'runner.py');V=importlib.util.module_from_spec(sp);sys.modules[sp.name]=V;sp.loader.exec_module(V)
R=V.R;HOST=R.OUT/'HOST';HOST.mkdir(exist_ok=True)


def freeze_fixture(out):
    (out/'review').mkdir(parents=True,exist_ok=True)
    paths=['src/simulation/mp18_video_run_127/'+n for n in ('release.py','runner.py','test_runner.py')]
    paths+=['src/simulation/mp18_isaac_127/'+n for n in ('driver.py','contract.py','native.py','config.json','program.json','media.py')]
    paths+=[R.PLAN,'outputs/mp18-video-run-127/release-manifest.json',*V.FACTS]
    f={'unit':127,'round':1,'HOST_ONLY_NOT_ACTUAL_L4':True,'files':{p:{'sha256':R.digest((R.ROOT/p).read_bytes()),'bytes':(R.ROOT/p).stat().st_size} for p in set(paths)}}
    raw=R.encode(f);(out/'review/source-freeze.json').write_bytes(raw)
    review={'unit':127,'phase':'L4','round':1,'non_author':True,'verdict':'PASS','unmet':0,'unresolved_count':0,
            'source_freeze_sha256':R.digest(raw),'HOST_ONLY_NOT_ACTUAL_L4':True}
    for who in ('main',):(out/('review/'+who+'-L4-final.json')).write_bytes(R.encode(review))
    return review


class ReleaseTests(unittest.TestCase):
    def test_01_deterministic_6file_release_and_only_candidate_fresh_stage_delta(self):
        data,m=R.build();actual,_,_=R.verify_release()
        self.assertEqual(data,actual)
        for name in ('contract.py','config.json','program.json'):
            self.assertEqual(data[name],(R.ROOT/'src/simulation/mp18_isaac_119'/name).read_bytes())
        self.assertEqual(R.digest(data['native.py']),R.CANDIDATE_SHA)
        old=(R.ROOT/'src/simulation/mp18_isaac_119/native.py').read_bytes()
        def functions(b):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(b).body if isinstance(n,ast.FunctionDef)}
        a,b=functions(old),functions(data['native.py']);self.assertEqual([k for k in a if a[k]!=b[k]],['fresh_stage'])
        self.assertTrue(m['driver_delta']['outside_replaced_spans_byte_identical'])
        self.assertNotIn('getsource',data['driver.py'].decode().split('def bootstrap_code')[1].split('def ')[0])

    def test_02_contract_and_media_same_checked_raw_no_loader_reread(self):
        data,_,_=R.verify_release();calls=[];original=Path.read_bytes;contract=R.DERIVED/'contract.py'
        def read_once(path):
            if Path(path)==contract:
                calls.append('contract')
                return data['contract.py'] if len(calls)==1 else b'raise RuntimeError("MUST_NOT_EXECUTE")'
            return original(path)
        with mock.patch.object(Path,'read_bytes',read_once):D=R.load_raw('contract_once_HOST127',data['driver.py'],R.DERIVED/'driver.py')
        self.assertEqual(calls,['contract']);self.assertTrue(callable(D.C.parse))
        wrong=HOST/uuid.uuid4().hex;wrong.mkdir();(wrong/'contract.py').write_bytes(b'raise RuntimeError("UNVERIFIED")')
        D.HERE=wrong
        with self.assertRaisesRegex(ValueError,'Fixed contract'):D._checked_contract_bytes()
        module=R.load_raw('media_loader_HOST127',data['media.py'],R.DERIVED/'media.py')
        self.assertTrue(callable(module.validate_frames));self.assertTrue(callable(module.encode))
        with self.assertRaises(ValueError):module.publish()

    def test_03_thinbootstrap_captured_AST_and_child_read_once_pin_before_exec(self):
        data,_,_=R.verify_release();args={'driver_sha256':R.digest(data['driver.py'])}
        literal=R.thin_bootstrap(data['driver.py'],data['contract.py'],args)
        self.assertLess(len(literal),7000);self.assertNotIn('inspect',literal)
        with self.assertRaises(ValueError):R.thin_bootstrap(data['driver.py']+b'\n',data['contract.py'],args)
        D=R.load_raw('childmacro_HOST127',data['driver.py'],R.DERIVED/'driver.py')
        case=HOST/uuid.uuid4().hex;(case/'input/source').mkdir(parents=True);(case/'output').mkdir()
        source=case/'input/source/driver.py';marker=case/'marker.txt'
        good=b'def native_main(run, expected_job_sha256):\n assert expected_job_sha256 == "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"\n return 37\n';source.write_bytes(good)
        ctx=types.SimpleNamespace(run=case,job={'run_id':case.name,'inputs':{'source/driver.py':R.digest(good)}},job_hash='f'*64,
            data={'source/driver.py':good,'ref/winjob.py':b'HOST_ONLY'},cfg={'sdk':{'isaac_root':'HOST_ONLY_NO_SDK'}})
        captured={}
        class StopMacro(Exception):pass
        def helper_run(argv,*a,**kw):captured['code']=argv[-1];raise StopMacro()
        D._context=lambda run,expected:(self.assertEqual(expected,ctx.job_hash),ctx)[1];D.load_module=lambda *a:types.SimpleNamespace(run=helper_run)
        try:
            with self.assertRaises(StopMacro):D.remote_supervise(case,time.monotonic()+1000,ctx.job_hash)
        finally:D._ACTIVE_OUT=None
        code=captured['code'];self.assertNotIn('exec_module',code)
        p=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=5);self.assertEqual(p.returncode,37,p.stderr)
        source.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("BAD")\n',encoding='utf8')
        p=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,timeout=5)
        self.assertNotEqual(p.returncode,0);self.assertFalse(marker.exists())


class PackageIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=HOST/('package-'+uuid.uuid4().hex);cls.review=freeze_fixture(cls.out)
        at=time.perf_counter();cls.record=V.prepare(cls.out);cls.prepare_s=time.perf_counter()-at
        cls.source=V.source_snapshot(cls.out);cls.prepared=V.prepared_snapshot(cls.source)
        reply={'unit':127,'kind':'ACTUAL_USER_REPLY','approved':True,'duration_s':2700,'hardware_approved':False,
               'reply_text':R.parse(R.read(R.ROOT/'outputs/mp18-video-run-127/approval-evidence.json'))['reply_text'],
               'conversation_ref':'HOST_ONLY_SYNTHETIC_RECORD_NOT_CANONICAL_APPROVAL'}
        raw_reply=R.encode(reply)
        grant={'unit':127,'kind':'REVIEWED_V4_VIDEO_RUN_GRANT','approved':True,'duration_s':2700,'hardware_approved':False,
               'reply_sha256':R.digest(raw_reply),'source_freeze_sha256':cls.prepared.source_sha,'prepared_sha256':R.digest(cls.prepared.prepared_raw),
               'started_monotonic':999.,'deadline_monotonic':3699.,'grant_nonce':'a'*32}
        cls.reply_raw,cls.grant_raw=raw_reply,R.encode(grant)
        (cls.out/'user-budget-reply.json').write_bytes(raw_reply);(cls.out/'user-budget-grant.json').write_bytes(cls.grant_raw)
        cls.snapshot=V.run_snapshot(cls.out,now=lambda:1000.)
        cls.owner=V.admit(cls.snapshot,now=lambda:1000.)
        print(json.dumps({'HOST_ONLY':'GENERATED127_PACKAGE','run_id':cls.record['run_id'],'nonce':cls.record['nonce'],
            'bundle_bytes':cls.record['bundle_bytes'],'prepare_s':cls.prepare_s,'legacy_job_unit':119,'outer_unit':127,'SDK':0,'SSH':0}),flush=True)

    def test_04_actual_generated_prepare_new_identity_and_legacy_contract(self):
        s=self.prepared;record=self.record
        self.assertNotEqual(record['run_id'],'f68441cd00534b88919cfd71f8f436a8')
        job=R.parse(s.job_raw);self.assertEqual(job['unit'],119);self.assertEqual(job['run_id'],record['run_id'])
        self.assertEqual(R.digest(dict(s.generated)['native.py']),R.CANDIDATE_SHA)
        D=V.driver(s);D.verified_payload(self.out/'runs'/record['run_id'],record)
        self.assertEqual((self.out/'user-decision.json').read_bytes(),R.read(R.ROOT/R.CAP))

    def test_05_current_model_cap_source_and_archive_tamper_are_denied_without_original_writes(self):
        s=self.snapshot;original=Path.read_bytes
        targets=[next(Path(p) for p,b in s.files if '/models/' in p.replace('\\','/')),
                 R.ROOT/R.CAP,R.DERIVED/'native.py',self.out/'runs'/self.record['run_id']/'bundle.zip']
        for target in targets:
            def changed(path):return original(path)+b'HOST_MUTATION' if Path(path)==target else original(path)
            with mock.patch.object(Path,'read_bytes',changed):
                with self.assertRaises(ValueError):V.current(s)
        with self.assertRaises(ValueError):V.admit(s,now=lambda:1000.)

    def test_06_typed_unit_phase_reviews_and_actual_grant_closed_schema(self):
        path=self.out/'review/main-L4-final.json';base=path.read_bytes()
        for key,value in [('unit',119),('unit',125),('phase','L2'),('round',True),('non_author',False),('unresolved_count',1)]:
            row=R.parse(base);row[key]=value;path.write_bytes(R.encode(row))
            try:
                with self.assertRaises(ValueError):V.source_snapshot(self.out)
            finally:path.write_bytes(base)
        gp=self.out/'user-budget-grant.json';base=gp.read_bytes()
        for key,value in [('approved',False),('duration_s',True),('unit',119),('deadline_monotonic',5000.),('reply_sha256','0'*64),('extra',1)]:
            row=R.parse(base);row[key]=value;gp.write_bytes(R.encode(row))
            try:
                with self.assertRaises(ValueError):V.grant_records(self.out,now=lambda:1000.)
            finally:gp.write_bytes(base)
        with self.assertRaises(ValueError):V.admit(self.snapshot,now=lambda:1300.) # 2399headroom

    def test_07_partial_write_closed_GO_and_exact_full_new_bundle(self):
        class Sink:
            def __init__(self):self.line=bytearray();self.hash=hashlib.sha256();self.bytes=0;self.in_payload=False
            def write(self,data):
                n=min(65536,len(data));b=bytes(data[:n])
                if not self.in_payload:self.line.extend(b);self.in_payload=b.endswith(b'\n')
                else:self.hash.update(b);self.bytes+=n
                return n
            def flush(self):pass
        stream=Sink();at=time.perf_counter()
        ready=dict(self.record,kind='READY',remote_ready=10.)
        self.owner.sender(stream,ready,3697.,now=lambda:1001.)
        self.assertEqual(R.parse(stream.line),dict(self.record,kind='GO'))
        self.assertEqual(stream.bytes,self.record['bundle_bytes']);self.assertEqual(stream.hash.hexdigest(),self.record['bundle_sha256'])
        with self.assertRaises(ValueError):self.owner.sender(stream,ready,3697.,now=lambda:1001.)
        print(json.dumps({'HOST_ONLY':'ACTUAL_GENERATED_BUNDLE_MEMORY_TRANSMISSION','bytes':stream.bytes,'elapsed_s':time.perf_counter()-at,'SDK':0,'SSH':0}),flush=True)

    def packet(self,entries=None,nonce=None):
        r=self.record;pid=24680
        if entries is None:
            data={'process.json':R.encode({'run_id':r['run_id'],'job_sha256':r['job_sha256'],'raw_complete':True,'terminal':True,
                 'child_state':'REAPED','job_active_after':0,'child_pid':pid,'actual_child_exit_code':1,'timed_out':False,'HOST_ONLY_SDKLESS':True}),
                'terminal.json':R.encode({'pid':pid,'run_id':r['run_id'],'job_sha256':r['job_sha256'],'status':'FAILED','code':1}),
                'report.json':R.encode({'unit':119,'pid':pid,'run_id':r['run_id'],'job_sha256':r['job_sha256'],'frames':[],
                    'phases':[{'name':n,'status':'FAIL' if n=='import' else 'NOT_RUN','reason':'HOST_ONLY_SDKLESS'} for n in ('import','hold','small','large')]})}
            data['recovery-seal.json']=R.encode({'unit':119,'run_id':r['run_id'],'job_sha256':r['job_sha256'],'actual_child_pid':pid,
                                                'files_sha256':{n:R.digest(b) for n,b in data.items()}})
            entries=list(data.items())
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            for n,b in entries:z.writestr(n,b)
        archive=buf.getvalue();header={'kind':'RESULT','run_id':r['run_id'],'nonce':nonce or r['nonce'],'bytes':len(archive),'sha256':R.digest(archive)}
        return R.encode(dict(r,kind='READY',remote_ready=10.))+b'\n'+R.encode(header)+b'\n'+archive

    def test_08_malformed_duplicate_wrongnonce_and_result_reparse_before_write(self):
        owner=self.owner;run=self.out/'runs'/self.record['run_id']
        for packet in (self.packet(nonce='b'*32),self.packet([('process.json',b'{}'),('process.json',b'{}'),('recovery-seal.json',b'{}')]),
                       self.packet([('../evil',b'bad'),('process.json',b'{}'),('recovery-seal.json',b'{}')]),self.packet()+b'TRAILING'):
            with self.assertRaises(ValueError):V.consume_archive(owner,packet)
            self.assertFalse((run/'retrieved').exists())
        original=Path.is_junction
        with mock.patch.object(Path,'is_junction',lambda p:Path(p)==run or original(p)):
            with self.assertRaises(ValueError):V.consume_archive(owner,self.packet())
        self.assertFalse((run/'retrieved').exists())

    def test_09_authority_changes_during_result_write_are_denied(self):
        gp=self.out/'user-budget-grant.json';original=R.exclusive;trigger=[False];run=self.out/'runs'/self.record['run_id']
        def mutation(path,data,guard=lambda:None):
            if Path(path).name=='retrieved.zip':gp.write_bytes(self.grant_raw+b' ');trigger[0]=True
            return original(path,data,guard)
        try:
            with mock.patch.object(R,'exclusive',mutation):
                with self.assertRaises(ValueError):V.consume_archive(self.owner,self.packet())
            self.assertTrue(trigger[0]);self.assertFalse((run/'retrieved.zip').exists())
        finally:
            gp.write_bytes(self.grant_raw)
            dest=run/'retrieved'
            if dest.exists():self.assertEqual(list(dest.iterdir()),[]);dest.rmdir()

    def test_10_generated_SDKless_failure_consumer_and_offline_encode_bind_after_period(self):
        code=V.consume_archive(self.owner,self.packet())
        self.assertEqual(code,2)
        result=R.parse((self.out/'native-result.json').read_bytes());self.assertEqual(result['status'],'FAIL');self.assertTrue(result['SDK_reaped'])
        self.assertEqual(result['run_id'],self.record['run_id'])
        # Actual now is long past the HOSTfixed999..3699 period; offline data verification remains allowed.
        self.assertEqual(V.consume(self.out),2)
        with self.assertRaisesRegex(ValueError,'nonempty'):V.encode_video(self.out)
        self.assertFalse((self.out/'delivery/robot-arm-v4-127.mp4').exists())
        offline=V.offline_owner(self.out);original_read=Path.read_bytes;member=self.out/'runs'/self.record['run_id']/'retrieved/report.json'
        def changed_member(path):
            value=original_read(path)
            return value+b' ' if Path(path)==member else value
        with mock.patch.object(Path,'read_bytes',changed_member):
            with self.assertRaises(ValueError):offline.current(False)
        with self.assertRaises(ValueError):V.consume_archive(self.owner,self.packet())

    def test_16_original_unpacked_job_authority_survives_parent_native_and_child_boundaries(self):
        D=V.driver(self.prepared);remote=self.out/'remote-authority'/self.record['run_id'];expected=self.record['job_sha256']
        original=D._unpack_payload(self.prepared.bundle,remote,expected)
        ctx=D._context(remote,expected);self.assertEqual(ctx.job_hash,expected)
        for function,args in ((D._context,(remote,)),(D.native_main,(remote,)),(D.remote_supervise,(remote,time.monotonic()+1000))):
            with self.assertRaises(TypeError):function(*args)
        helper_path=remote/'input/ref/winjob.py';old_helper=helper_path.read_bytes();jobraw=(remote/'job.json').read_bytes()
        marker=self.out/'UNVERIFIED_HELPER_MUST_NOT_EXECUTE.txt'
        bad=('from pathlib import Path\nPath('+repr(str(marker))+').write_text("BAD")\nraise RuntimeError("BAD_HELPER")\n').encode()
        newjob=dict(original,inputs=dict(original['inputs']));newjob['inputs']['ref/winjob.py']=R.digest(bad)
        helper_path.write_bytes(bad);(remote/'job.json').write_bytes(R.encode(newjob))
        input_reads=[];read_bytes=Path.read_bytes
        def observed(path):
            if Path(path).is_relative_to(remote/'input'):input_reads.append(str(path))
            return read_bytes(path)
        with mock.patch.object(Path,'read_bytes',observed):
            for call in (lambda:D._context(remote,expected),lambda:D.remote_supervise(remote,time.monotonic()+2600,expected),lambda:D.native_main(remote,expected)):
                with self.assertRaisesRegex(ValueError,'Original expected job hash'):call()
        self.assertEqual(input_reads,[]);self.assertFalse(marker.exists());self.assertFalse((remote/'output').exists())
        (remote/'job.json').write_bytes(jobraw)
        with self.assertRaisesRegex(ValueError,'Native input hash'):D._context(remote,expected)
        helper_path.write_bytes(old_helper)
        self.assertEqual(D._context(remote,expected).job_hash,expected)
        class StopBeforeSDK(Exception):pass
        captured={}
        def helper_run(argv,*a,**kw):captured['code']=argv[-1];raise StopBeforeSDK()
        original_loader=D.load_module
        def loader(name,raw,path):
            self.assertEqual(raw,old_helper);return types.SimpleNamespace(run=helper_run)
        D.load_module=loader
        try:
            with self.assertRaises(StopBeforeSDK):D.remote_supervise(remote,time.monotonic()+2600,expected)
        finally:D._ACTIVE_OUT=None;D.load_module=original_loader
        owner=R.parse((remote/'output/owner.json').read_bytes());self.assertEqual(owner['job_sha256'],expected)
        self.assertIn(repr(expected),captured['code']);self.assertIn('m.native_main(p.parents[2],',captured['code'])
        tree=ast.parse(dict(self.prepared.generated)['driver.py']);bootstrap=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_bootstrap')
        call=next(n for n in ast.walk(bootstrap) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='remote_supervise')
        self.assertEqual(len(call.args),3);self.assertEqual(ast.unparse(call.args[2]),"args['job_sha256']")
        with self.assertRaisesRegex(ValueError,'Owned native deadline'):D.native_main(remote,expected)
        D._ACTIVE_OUT=None
        print(json.dumps({'HOST_ONLY':'ORIGINAL_JOB_AUTHORITY_R2','normal_original_context':True,'coherent_job_helper_swap_parent_native_context_denied':True,'input_reads_before_rejection':len(input_reads),'unverified_helper_executed':marker.exists(),'owner_and_child_original_hash':expected,'SDK':0,'SSH':0}),flush=True)

    def test_17_current126_priorSDK2_main_only_and_video_only_contract(self):
        self.assertFalse((self.out/'review/lens-L4-final.json').exists())
        self.assertEqual(V._metadata(self.snapshot,1000.)['actual_prior_SDK'],2)
        self.assertEqual(R.parse(self.owner.snapshot_raw)['actual_prior_SDK'],2)
        self.assertEqual(R.parse(self.prepared.manifest_raw)['native_exact126_candidate'],True)
        self.assertNotIn('native_exact124_candidate',R.parse(self.prepared.manifest_raw))
        self.assertEqual(R.CANDIDATE,'outputs/mp18-layer-lifetime-126/candidate/native.py')
        self.assertEqual(R.digest(dict(self.prepared.generated)['native.py']),'06a36b35713337d42fdb76f6f3ac161d56d6cb3cb7ce47f4d2fa683176c22e17')
        D=V.driver(self.prepared);D._review_gate()
        main=self.out/'review/main-L4-final.json';read_bytes=Path.read_bytes;lens_reads=[]
        def missing_main(path):
            if Path(path)==main:raise FileNotFoundError('HOST missing sole main')
            if Path(path)==self.out/'review/lens-L4-final.json':lens_reads.append(1);return main.read_bytes()
            return read_bytes(path)
        with mock.patch.object(Path,'read_bytes',missing_main):
            with self.assertRaises(FileNotFoundError):V.source_snapshot(self.out)
            with self.assertRaises(FileNotFoundError):D._review_gate()
        self.assertEqual(lens_reads,[])
        facts=['outputs/mp18-video-run-125/runtime-final.json','outputs/mp18-video-run-125/native-result.json',
               'outputs/mp18-layer-lifetime-126/review/source-freeze.json','outputs/mp18-layer-lifetime-126/review/main-L4-final.json',
               'outputs/mp18-layer-lifetime-126/review/main-L4-r1/publication-complete.json','outputs/mp18-layer-lifetime-126/result.json']
        for rel in facts:
            target=R.ROOT/rel
            def changed(path):return read_bytes(path)+b' ' if Path(path)==target else read_bytes(path)
            with mock.patch.object(Path,'read_bytes',changed):
                with self.assertRaises(ValueError):V.current(self.snapshot)
        # Coherent HOST-only re-pinning cannot promote prior125 SDK failure/count semantics.
        rel=facts[0];target=R.ROOT/rel;good=read_bytes(target);wrong=R.parse(good);wrong['total_actual_SDK']=1;bad=R.encode(wrong)
        fpath=self.out/'review/source-freeze.json';fraw=fpath.read_bytes();mraw=main.read_bytes();old_pin=V.FACTS[rel]
        f=R.parse(fraw);f['files'][rel]={'sha256':R.digest(bad),'bytes':len(bad)};newf=R.encode(f)
        review=R.parse(mraw);review['source_freeze_sha256']=R.digest(newf)
        fpath.write_bytes(newf);main.write_bytes(R.encode(review));V.FACTS[rel]=R.digest(bad)
        def replaced(path):return bad if Path(path)==target else read_bytes(path)
        try:
            with mock.patch.object(Path,'read_bytes',replaced):
                with self.assertRaisesRegex(ValueError,'Original125 SDK2 history'):V.source_snapshot(self.out)
        finally:fpath.write_bytes(fraw);main.write_bytes(mraw);V.FACTS[rel]=old_pin
        media_tree=ast.parse(dict(self.prepared.generated)['media.py'])
        manifests=[n for n in ast.walk(media_tree) if isinstance(n,ast.Dict) and any(isinstance(k,ast.Constant) and k.value=='upload_allowlist' for k in n.keys)]
        self.assertEqual(len(manifests),1)
        values=[v for k,v in zip(manifests[0].keys,manifests[0].values) if isinstance(k,ast.Constant) and k.value=='upload_allowlist']
        self.assertEqual(ast.unparse(values[0]),'[movie.name]')
        print(json.dumps({'HOST_ONLY':'127_CURRENT_AUTHORITY_MAIN_ONLY_PRIOR2_NATIVE126','sole_main_without_lens':True,'prior_SDK':2,'native_exact126':True,'video_allowlist_only':True,'current126_mutations_rejected':True,'coherent_prior_count_promotion_rejected':True,'SDK':0,'SSH':0}),flush=True)

    def test_11_context_job_parse_and_hash_use_the_same_single_read(self):
        D=V.driver(self.prepared);run=HOST/uuid.uuid4().hex;(run/'input/source').mkdir(parents=True)
        cfg=dict(self.prepared.generated)['config.json'];program=dict(self.prepared.generated)['program.json'];approval=R.read(R.ROOT/R.CAP)
        blobs={'source/config.json':cfg,'source/program.json':program,'approval.json':approval}
        for name,b in blobs.items():p=run/'input'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        job={'unit':119,'run_id':run.name,'hardware_approved':False,'inputs':{k:R.digest(v) for k,v in blobs.items()}}
        jobraw=R.encode(job);(run/'job.json').write_bytes(jobraw);original=Path.read_bytes;calls=[]
        def once(path):
            if Path(path)==run/'job.json':calls.append(1);return jobraw if len(calls)==1 else b'{"MALICIOUS":true}'
            return original(path)
        with mock.patch.object(Path,'read_bytes',once),mock.patch.object(D.C,'verify_inputs',return_value={'HOST_ONLY':True}):ctx=D._context(run,R.digest(jobraw))
        self.assertEqual(len(calls),1);self.assertEqual(ctx.job_hash,R.digest(jobraw));self.assertEqual(ctx.job,job)


class EarlyDenials(unittest.TestCase):
    def test_12_actual_absent127_grant_refuses_before_preparation_or_mutation(self):
        self.assertFalse((V.OUT/'user-budget-grant.json').exists());self.assertFalse((V.OUT/'user-budget-reply.json').exists())
        with mock.patch.object(V,'source_snapshot',side_effect=AssertionError('MUST_NOT_PREPARE')):
            with self.assertRaises(FileNotFoundError):V.run()
        self.assertFalse((V.OUT/'admission.json').exists());self.assertFalse((V.OUT/'GO.json').exists())


class LocalWritesAndFrames(unittest.TestCase):
    def test_13_actual116_RGB_validator_replay_is_explicitly_NOT127_native(self):
        data,_,_=R.verify_release();M=R.load_raw('media_frame_replay127',data['media.py'],R.DERIVED/'media.py')
        old=R.ROOT/'outputs/blended-reference-trial-116/native-artifacts/runs/4f38ca9612b34716947baa6f56c96e05/retrieved'
        folder=HOST/('SYNTHETIC_HOST_OLD116_RGB_NOT127_NATIVE_'+uuid.uuid4().hex);(folder/'frames').mkdir(parents=True)
        png=(old/'frames/frame-0000.png').read_bytes();self.assertEqual(R.digest(png),'71d4d8d8265bf07eeb958c99c738274f69279d5f39d8c38a546542a0b86c8403')
        row=R.parse((old/'frames/frame-0000.json').read_bytes());row['phase']='hold:HOST_OLD116_NOT127_NATIVE'
        (folder/'frames/frame-0000.png').write_bytes(png)
        cfg=R.parse(data['config.json']);item=cfg['refs']['capture.py'];raw=R.read(R.ROOT/item['path']);self.assertEqual(R.digest(raw),item['sha256'])
        capture=R.load_raw('capture116_replay127',raw,R.ROOT/item['path'])
        def persist(value):
            b=R.encode(value);(folder/'frames/frame-0000.json').write_bytes(b)
            return {'frames/frame-0000.png':R.digest(png),'frames/frame-0000.json':R.digest(b)}
        self.assertEqual(len(M.validate_frames(folder,persist(row),capture)),1)
        bad=R.parse(R.encode(row));bad['freshness']['after']['rgb']['compute_count']=bad['freshness']['before']['rgb']['compute_count']
        with self.assertRaises(capture.CaptureError):M.validate_frames(folder,persist(bad),capture)
        bad=R.parse(R.encode(row));bad['state_index']=1
        with self.assertRaises(ValueError):M.validate_frames(folder,persist(bad),capture)
        self.assertFalse((folder/'robot-arm-v4-127.mp4').exists())

    def test_14_local_write_guard_uses_original_ROOT_ancestors_and_current_before_data(self):
        data,_,_=R.verify_release();D=R.load_raw('writeguard127',data['driver.py'],R.DERIVED/'driver.py')
        out=HOST/uuid.uuid4().hex;D.OUT=out;D.bind_local_authority(lambda:None,lambda p:b'')
        target=out/'nested/result.json';original=Path.is_junction
        for changed in (R.ROOT,out,target.parent,target):
            def junction(path,c=changed):return True if Path(path)==c else original(path)
            with mock.patch.object(Path,'is_junction',junction):
                with self.assertRaises(ValueError):D.write(target,{'HOST_ONLY':True})
            self.assertFalse(target.exists())
        calls=[]
        def revoked():
            calls.append(1)
            if len(calls)>1:raise ValueError('HOST current authority revoked before write')
        D.bind_local_authority(revoked,lambda p:b'')
        with self.assertRaisesRegex(ValueError,'revoked'):D.write(target,{'HOST_ONLY':True})
        self.assertFalse(target.exists());self.assertEqual(len(calls),2)
        D.bind_local_authority(lambda:None,lambda p:b'');D.write(target,{'HOST_ONLY':True})
        self.assertEqual(R.parse(target.read_bytes()),{'HOST_ONLY':True})

    def test_15_every_media_invoke_checks_current_without_reclassifying_input_or_null(self):
        calls=[];state={'revoked':False}
        def current(active=False):
            if state['revoked']:raise ValueError('HOST authority revoked')
            calls.append('current')
        def invoke(argv,timeout=120):calls.append((argv,timeout));return b'HOST_ONLY'
        checked=V.guarded_media_invoke(types.SimpleNamespace(current=current),invoke)
        commands=[['ffprobe','-of','json','input.mp4'],['ffmpeg','-i','input.mp4','-f','null','-'],['ffmpeg','-n','output.mp4']]
        for argv in commands:self.assertEqual(checked(argv,timeout=30),b'HOST_ONLY')
        self.assertEqual(calls,[item for argv in commands for item in ('current',(argv,30))])
        state['revoked']=True
        with self.assertRaisesRegex(ValueError,'revoked'):checked(commands[1])


if __name__=='__main__':unittest.main(verbosity=2)
