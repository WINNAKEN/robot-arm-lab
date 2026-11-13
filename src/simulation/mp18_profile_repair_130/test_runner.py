"""130 HOST-only integration. One real generated package; synthetic SDK-less failure records, never SDK/SSH/Drive/Git."""
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
sp=importlib.util.spec_from_file_location('runner130_HOST',HERE/'runner.py');V=importlib.util.module_from_spec(sp);sys.modules[sp.name]=V;sp.loader.exec_module(V)
R=V.R;HOST=R.OUT/'HOST';HOST.mkdir(exist_ok=True)


def freeze_fixture(out):
    (out/'review').mkdir(parents=True,exist_ok=True)
    paths=['src/simulation/mp18_profile_repair_130/'+n for n in ('release.py','runner.py','test_runner.py')]
    paths+=['src/simulation/mp18_isaac_130/'+n for n in ('driver.py','contract.py','native.py','config.json','program.json','media.py')]
    paths+=[R.PLAN,'outputs/mp18-profile-repair-130/release-manifest.json',*V.FACTS]
    f={'unit':130,'round':1,'HOST_ONLY_NOT_ACTUAL_L4':True,'files':{p:{'sha256':R.digest((R.ROOT/p).read_bytes()),'bytes':(R.ROOT/p).stat().st_size} for p in set(paths)}}
    raw=R.encode(f);(out/'review/source-freeze.json').write_bytes(raw)
    review={'unit':130,'phase':'L4','round':1,'non_author':True,'verdict':'PASS','unmet':0,'unresolved_count':0,
            'source_freeze_sha256':R.digest(raw),'HOST_ONLY_NOT_ACTUAL_L4':True}
    for who in ('main',):(out/('review/'+who+'-L4-final.json')).write_bytes(R.encode(review))
    return review


class ReleaseTests(unittest.TestCase):
    def test_01_deterministic_6file_release_and_only_candidate_fresh_stage_delta(self):
        data,m=R.build();actual,_,_=R.verify_release()
        self.assertEqual(data,actual)
        for name in ('contract.py','config.json'):
            self.assertEqual(data[name],(R.ROOT/'src/simulation/mp18_isaac_119'/name).read_bytes())
        self.assertNotEqual(R.digest(data['native.py']),R.CANDIDATE_SHA)
        self.assertTrue(m['native_exact129'])
        old=(R.ROOT/'src/simulation/mp18_isaac_119/native.py').read_bytes()
        def functions(b):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(b).body if isinstance(n,ast.FunctionDef)}
        a,b=functions(old),functions(data['native.py']);self.assertEqual([k for k in a if a[k]!=b[k]],['fresh_stage','_native','collect'])
        self.assertTrue(m['driver_delta']['outside_replaced_spans_byte_identical'])
        self.assertNotIn('getsource',data['driver.py'].decode().split('def bootstrap_code')[1].split('def ')[0])

    def test_02_contract_and_media_same_checked_raw_no_loader_reread(self):
        data,_,_=R.verify_release();calls=[];original=Path.read_bytes;contract=R.DERIVED/'contract.py'
        def read_once(path):
            if Path(path)==contract:
                calls.append('contract')
                return data['contract.py'] if len(calls)==1 else b'raise RuntimeError("MUST_NOT_EXECUTE")'
            return original(path)
        with mock.patch.object(Path,'read_bytes',read_once):D=R.load_raw('contract_once_HOST130',data['driver.py'],R.DERIVED/'driver.py')
        self.assertEqual(calls,['contract']);self.assertTrue(callable(D.C.parse))
        wrong=HOST/uuid.uuid4().hex;wrong.mkdir();(wrong/'contract.py').write_bytes(b'raise RuntimeError("UNVERIFIED")')
        D.HERE=wrong
        with self.assertRaisesRegex(ValueError,'Fixed contract'):D._checked_contract_bytes()
        module=R.load_raw('media_loader_HOST130',data['media.py'],R.DERIVED/'media.py')
        self.assertTrue(callable(module.validate_frames));self.assertTrue(callable(module.encode))
        with self.assertRaises(ValueError):module.publish()

    def test_03_thinbootstrap_captured_AST_and_child_read_once_pin_before_exec(self):
        data,_,_=R.verify_release();args={'driver_sha256':R.digest(data['driver.py'])}
        literal=R.thin_bootstrap(data['driver.py'],data['contract.py'],args)
        self.assertLess(len(literal),7000);self.assertNotIn('inspect',literal)
        with self.assertRaises(ValueError):R.thin_bootstrap(data['driver.py']+b'\n',data['contract.py'],args)
        D=R.load_raw('childmacro_HOST130',data['driver.py'],R.DERIVED/'driver.py')
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
        assert not (cls.out/'new-runtime-permission.json').exists(), 'HOST local prepare precedes any runtime permission'
        permission={'unit':130,'kind':'NEW_EXPLICIT_RUNTIME_PERMISSION','approved':True,
            'reply_text':'HOST_ONLY_SYNTHETIC_NEW_EXPLICIT_PERMISSION_FOR_ONE130_SDK_NOT_CANONICAL',
            'conversation_ref':'HOST_ONLY_NEW_PERMISSION_MESSAGE_FIXTURE_NOT_ACTUAL',
            'source_freeze_sha256':cls.prepared.source_sha,'L4_report_sha256':R.digest((cls.out/'review/main-L4-final.json').read_bytes()),
            'original_request_sha256':V.FACTS['outputs/mp18-video-run-128/approval-evidence.json'],
            'exhausted_allocation_sha256':V.FACTS['outputs/mp18-video-run-128/task-scope.json'],
            'additional_SDK_max':1,'retry':0,'duration_s':2700,'hardware_approved':False}
        cls.permission_raw=R.encode(permission);(cls.out/'new-runtime-permission.json').write_bytes(cls.permission_raw)
        reply={'unit':130,'kind':'ACTUAL_USER_REPLY','approved':True,'duration_s':2700,'hardware_approved':False,
               'reply_text':permission['reply_text'],
               'conversation_ref':permission['conversation_ref']+'|permission_sha256='+R.digest(cls.permission_raw)}
        raw_reply=R.encode(reply)
        grant={'unit':130,'kind':'REVIEWED_V4_VIDEO_RUN_GRANT','approved':True,'duration_s':2700,'hardware_approved':False,
               'reply_sha256':R.digest(raw_reply),'source_freeze_sha256':cls.prepared.source_sha,'prepared_sha256':R.digest(cls.prepared.prepared_raw),
               'started_monotonic':999.,'deadline_monotonic':3699.,'grant_nonce':'a'*32}
        cls.reply_raw,cls.grant_raw=raw_reply,R.encode(grant)
        (cls.out/'user-budget-reply.json').write_bytes(raw_reply);(cls.out/'user-budget-grant.json').write_bytes(cls.grant_raw)
        cls.snapshot=V.run_snapshot(cls.out,now=lambda:1000.)
        cls.owner=V.admit(cls.snapshot,now=lambda:1000.)
        print(json.dumps({'HOST_ONLY':'GENERATED130_PACKAGE','run_id':cls.record['run_id'],'nonce':cls.record['nonce'],
            'bundle_bytes':cls.record['bundle_bytes'],'prepare_s':cls.prepare_s,'legacy_job_unit':119,'outer_unit':130,'SDK':0,'SSH':0}),flush=True)

    def test_04_actual_generated_prepare_new_identity_and_legacy_contract(self):
        s=self.prepared;record=self.record
        self.assertNotEqual(record['run_id'],'f68441cd00534b88919cfd71f8f436a8')
        job=R.parse(s.job_raw);self.assertEqual(job['unit'],119);self.assertEqual(job['run_id'],record['run_id'])
        self.assertEqual(R.digest(dict(s.generated)['native.py']),R.parse(s.manifest_raw)['files']['native.py']['sha256'])
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
        self.assertFalse((self.out/'delivery/robot-arm-v4-130.mp4').exists())
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
        self.assertEqual(V._metadata(self.snapshot,1000.)['actual_prior_SDK'],5)
        self.assertEqual(R.parse(self.owner.snapshot_raw)['actual_prior_SDK'],5)
        self.assertEqual(R.parse(self.prepared.manifest_raw)['native_exact129'],True)
        self.assertNotIn('native_exact124_candidate',R.parse(self.prepared.manifest_raw))
        self.assertEqual(R.CANDIDATE,'outputs/mp18-layer-lifetime-126/candidate/native.py')
        self.assertEqual(R.digest(dict(self.prepared.generated)['native.py']),R.parse(self.prepared.manifest_raw)['files']['native.py']['sha256'])
        self.assertNotEqual(R.digest(dict(self.prepared.generated)['native.py']),R.CANDIDATE_SHA)
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
        print(json.dumps({'HOST_ONLY':'130_CURRENT_AUTHORITY_MAIN_ONLY_PRIOR4_DERIVED_NATIVE','sole_main_without_lens':True,'prior_SDK':5,'native_exact129':True,'video_allowlist_only':True,'current126_mutations_rejected':True,'coherent_prior_count_promotion_rejected':True,'SDK':0,'SSH':0}),flush=True)

    def test_18_closed_task_allocation_prior3_current_derived_native_and_same_raw_proof(self):
        self.assertEqual(V._metadata(self.snapshot,1000.)['actual_prior_SDK'],5)
        meta=R.parse(self.owner.snapshot_raw);self.assertEqual(meta['goal_allocation']['allowed_runtime_units'],[128,129])
        self.assertEqual(meta['task_scope_sha256'],V.FACTS['outputs/mp18-video-run-128/task-scope.json'])
        proof=R.parse((self.out/'prepare-evidence.json').read_bytes())
        self.assertEqual(proof['native_sha256'],R.digest(dict(self.prepared.generated)['native.py']))
        self.assertNotEqual(proof['native_sha256'],R.CANDIDATE_SHA)
        rel='outputs/mp18-video-run-128/task-scope.json';target=R.ROOT/rel;read_bytes=Path.read_bytes;original=read_bytes(target)
        fpath=self.out/'review/source-freeze.json';main=self.out/'review/main-L4-final.json';fraw=fpath.read_bytes();mraw=main.read_bytes();oldpin=V.FACTS[rel]
        cases=[('allowed_runtime_units',[130,130]),('max_total_SDK',3),('max_SDK_per_unit',True),('fixed_remote_period_s_per_unit',2701),('max_sum_remote_periods_s',5401),('request_sha256','0'*64),('hardware_approved',True),('retry_per_unit',1),('extra',0)]
        for key,value in cases:
            task=R.parse(original);task[key]=value;bad=R.encode(task);f=R.parse(fraw);f['files'][rel]={'sha256':R.digest(bad),'bytes':len(bad)};newf=R.encode(f);review=R.parse(mraw);review['source_freeze_sha256']=R.digest(newf)
            fpath.write_bytes(newf);main.write_bytes(R.encode(review));V.FACTS[rel]=R.digest(bad)
            def replace(path):return bad if Path(path)==target else read_bytes(path)
            try:
                with mock.patch.object(Path,'read_bytes',replace):
                    with self.assertRaises(ValueError):V.source_snapshot(self.out)
            finally:fpath.write_bytes(fraw);main.write_bytes(mraw);V.FACTS[rel]=oldpin
        with mock.patch.object(Path,'read_bytes',lambda p:original+b' ' if Path(p)==target else read_bytes(p)):
            with self.assertRaises(ValueError):V.current(self.snapshot)

    def test_36_closed_continuation_captured_original_authority_and_allocation_are_actual_consumed(self):
        originals={p:R.read(R.ROOT/p) for p in V.CONTINUATION_FILES}
        result=V._continuation_records(originals);self.assertEqual(result['unit'],128)
        reference,authority,task=V.CONTINUATION_FILES
        cases=[(reference,'unit',128),(reference,'actual_authority_unit',130),(reference,'actual_authority_path','outputs/mp18-video-run-127/approval-evidence.json'),(reference,'actual_authority_sha256','0'*64),(reference,'task_scope_path','wrong'),(reference,'task_scope_sha256','0'*64),(reference,'reply_text','FABRICATED'),(reference,'hardware_approved',True),(reference,'new_user_reply_fabricated',True),(reference,'extra',0),(authority,'unit',130),(authority,'kind','CONTINUATION_REFERENCE_TO_ACTUAL_USER_REQUEST'),(authority,'source','fabricated'),(task,'request_sha256',R.digest(originals[reference])),(task,'allowed_runtime_units',[128,130]),(task,'max_total_SDK',3),(task,'max_SDK_per_unit',True),(task,'fixed_remote_period_s_per_unit',2701),(task,'hardware_approved',True)]
        for path,key,value in cases:
            changed=dict(originals);obj=R.parse(changed[path]);obj[key]=value;changed[path]=R.encode(obj)
            # This controlled coherent repin bypasses only the fixed raw pin to exercise semantic use.
            old=V.FACTS[path];V.FACTS[path]=R.digest(changed[path])
            try:
                with self.assertRaises(ValueError,msg=str((path,key))):V._continuation_records(changed)
            finally:V.FACTS[path]=old
        good=V.grant_records(self.out,now=lambda:1000.);self.assertEqual(good.raw,(self.out/'user-budget-grant.json').read_bytes())
        original_read=R.read
        for path in V.CONTINUATION_FILES:
            def changed_read(p):return originals[path]+b' ' if Path(p)==R.ROOT/path else original_read(p)
            with mock.patch.object(R,'read',changed_read):
                with self.assertRaises(ValueError):V.grant_records(self.out,now=lambda:1000.)
        raw_read=Path.read_bytes
        for rel in ('outputs/mp18-video-run-128/run-result.json','outputs/mp18-video-run-128/review/main-L4-final.json','outputs/mp18-video-run-128/runs/d0f2b14ff76d4079a43f7ba8f218f603/retrieved/process.json'):
            def changed_read(p):return raw_read(p)+b' ' if Path(p)==R.ROOT/rel else raw_read(p)
            with mock.patch.object(Path,'read_bytes',changed_read):
                with self.assertRaises(ValueError):V.current(self.snapshot)

    def test_37_actual_new_program_only_eight_paths_and_original_validator_consumer(self):
        data,m,_=R.verify_release();old=R.parse(R.read(R.ROOT/'src/simulation/mp18_isaac_119/program.json'));new=R.parse(data['program.json'])
        paths=[['stages','small','segments',i,'q_deg',j] for i in range(4) for j in (1,2)]
        self.assertEqual(m['program_delta']['allowed_JSON_paths'],paths);self.assertFalse(m['contract_config_program_byte_identical'])
        restored=R.parse(data['program.json'])
        for i in range(4):
            for j in (1,2):self.assertEqual(new['stages']['small']['segments'][i]['q_deg'][j],0);restored['stages']['small']['segments'][i]['q_deg'][j]=-3
        self.assertEqual(restored,old);self.assertEqual(new['stages']['large'],old['stages']['large']);self.assertEqual(new['stages']['hold'],old['stages']['hold'])
        self.assertEqual(data['native.py'],R.read(R.ROOT/'src/simulation/mp18_isaac_129/native.py'))
        D=V.driver(self.prepared);C=D.C;cfg=R.parse(data['config.json']);model=C.parse_model(R.ROOT/cfg['model_dir']/'robot_arm.urdf');support=R.parse(R.read(R.ROOT/'outputs/mp18-isaac-119/A/support.json'))
        proof=C.validate_program(new,model,support)
        self.assertAlmostEqual(proof['stages']['small']['minimum_moving_link_z_m'],.010987203559618824,places=12)
        for phase,t in (('small',12.),('large',34.)):
            row=C.target_at(new,phase,t);self.assertTrue(all(v==0 for v in row['targets'].values()));self.assertTrue(all(v==0 for v in row['reference_velocity'].values()))
        self.assertEqual(R.parse(self.prepared.job_raw)['inputs']['source/program.json'],R.digest(data['program.json']))
        prepared=R.parse((self.out/'prepare-evidence.json').read_bytes());meta=V._metadata(self.snapshot,1000.)
        self.assertEqual(prepared['program_sha256'],R.digest(data['program.json']));self.assertEqual(meta['program_sha256'],prepared['program_sha256']);self.assertEqual(meta['program_delta_paths'],paths)
        actual=Path.read_bytes;target=R.DERIVED/'program.json';oldraw=R.read(R.ROOT/'src/simulation/mp18_isaac_119/program.json')
        with mock.patch.object(Path,'read_bytes',lambda p:oldraw if Path(p)==target else actual(p)):
            with self.assertRaises(ValueError):V.source_snapshot(self.out)
        print(json.dumps({'HOST_ONLY':'130_PROGRAM_EIGHT_PATHS_C119_VALIDATED','program_sha256':R.digest(data['program.json']),'minimum_nominal_small_z_m':proof['stages']['small']['minimum_moving_link_z_m'],'original_criteria':True,'native_exact129':True,'SDK':0}),flush=True)

    def test_38_local_prepare_without_permission_does_not_authorize_run_or_admit(self):
        p=self.out/'new-runtime-permission.json';raw=p.read_bytes();before={n:(self.out/n).read_bytes() for n in ('admission.json','consumed-snapshot.json','GO.json') if (self.out/n).exists()}
        before_roles=((self.out/'attempt.json').exists(),(self.out/'transport').exists())
        p.unlink()
        try:
            source=V.source_snapshot(self.out);self.assertIsNone(source.grant);prepared=V.prepared_snapshot(source)
            with mock.patch.object(V,'driver',side_effect=AssertionError('NO_DRIVER_OR_SDK_HELPER_BEFORE_PERMISSION')):
                with self.assertRaises(FileNotFoundError):V.run(self.out)
            with self.assertRaises(FileNotFoundError):V.admit(prepared,now=lambda:1000.)
            self.assertEqual(before_roles,((self.out/'attempt.json').exists(),(self.out/'transport').exists()))
            fresh=HOST/('missing-permission-'+uuid.uuid4().hex);fresh.mkdir()
            with mock.patch.object(V,'driver',side_effect=AssertionError('NO_HELPER_WITHOUT_NEW_PERMISSION')):
                with self.assertRaises(FileNotFoundError):V.run(fresh)
            with self.assertRaises(FileNotFoundError):V.admit(self.prepared._replace(out=fresh),now=lambda:1000.)
            self.assertEqual(list(fresh.iterdir()),[])
            self.assertEqual(before,{n:(self.out/n).read_bytes() for n in before})
        finally:p.write_bytes(raw)
        self.assertFalse((R.OUT/'new-runtime-permission.json').exists())

    def test_39_actual_new_permission_schema_roles_binding_and_unique_reply_token(self):
        path=self.out/'new-runtime-permission.json';original=path.read_bytes();e=R.parse(original)
        self.assertEqual(V.runtime_permission(self.out)[0],original)
        actual_old_quote=R.parse(R.read(R.ROOT/'outputs/mp18-video-run-128/approval-evidence.json'))['reply_text']
        cases=[('unit',129),('kind','LOCAL_REPAIR_ONLY_REFERENCE_TO_EXISTING_USER_REQUEST'),('approved',False),('reply_text',actual_old_quote),('conversation_ref','bad|permission_sha256='+'0'*64),('source_freeze_sha256','0'*64),('L4_report_sha256','0'*64),('original_request_sha256','0'*64),('exhausted_allocation_sha256','0'*64),('additional_SDK_max',2),('additional_SDK_max',True),('retry',1),('duration_s',2701),('hardware_approved',True),('extra',0)]
        try:
            for key,value in cases:
                bad=dict(e);bad[key]=value;path.write_bytes(R.encode(bad))
                with self.assertRaises(ValueError,msg=key):V.run_snapshot(self.out,now=lambda:1000.)
            for rel in ('outputs/mp18-video-run-128/approval-evidence.json','outputs/mp18-video-run-129/user-budget-grant.json','outputs/mp18-profile-repair-130/source-authorization.json'):
                path.write_bytes(R.read(R.ROOT/rel))
                with self.assertRaises(ValueError,msg=rel):V.run_snapshot(self.out,now=lambda:1000.)
        finally:path.write_bytes(original)
        replypath,grantpath=self.out/'user-budget-reply.json',self.out/'user-budget-grant.json';reply,grant=R.parse(self.reply_raw),R.parse(self.grant_raw)
        try:
            for ref in (e['conversation_ref']+'|permission_sha256='+'0'*64,reply['conversation_ref']+'|permission_sha256='+R.digest(original),'NO_PERMISSION_TOKEN'):
                bad=dict(reply,conversation_ref=ref);rraw=R.encode(bad);replypath.write_bytes(rraw);grantpath.write_bytes(R.encode(dict(grant,reply_sha256=R.digest(rraw))))
                with self.assertRaises(ValueError):V.grant_records(self.out,now=lambda:1000.)
        finally:replypath.write_bytes(self.reply_raw);grantpath.write_bytes(self.grant_raw)

    def test_40_permission_same_raw_lifetime_first_GO_and_current_consumers(self):
        s=self.snapshot;permission=self.out/'new-runtime-permission.json';raw=permission.read_bytes();meta=V._metadata(s,1000.)
        self.assertEqual(s.grant.permission_raw,raw);self.assertEqual(dict(s.files)[str(permission)],raw)
        self.assertEqual(meta['new_runtime_permission_sha256'],R.digest(raw));self.assertEqual(R.parse(V._seal(self.owner.snapshot_raw,meta))['new_runtime_permission_sha256'],R.digest(raw))
        self.assertEqual(meta['goal_allocation']['allowed_runtime_units'],[128,129]);self.assertNotIn(130,meta['goal_allocation']['allowed_runtime_units'])
        actual=Path.read_bytes
        with mock.patch.object(Path,'read_bytes',lambda p:raw+b' ' if Path(p)==permission else actual(p)):
            with self.assertRaises(ValueError):V.current(s)
            with self.assertRaises(ValueError):V.offline_owner(self.out)
            with self.assertRaises(ValueError):V.admit(s,now=lambda:1000.)
        go=self.out/'GO.json';oldgo=go.read_bytes() if go.exists() else None;exclusive=R.exclusive;stream=io.BytesIO();owner=V.Owner(s,self.owner.snapshot_raw,self.owner.seal_raw,1000.)
        if go.exists():go.unlink()
        def changed(path,data,guard=lambda:None):
            result=exclusive(path,data,guard)
            if Path(path)==go:permission.write_bytes(raw+b' ')
            return result
        try:
            with mock.patch.object(R,'exclusive',changed):
                with self.assertRaises(ValueError):owner.sender(stream,dict(self.record,kind='READY',remote_ready=10.),3697.,now=lambda:1001.)
            self.assertEqual(stream.getvalue(),b'')
        finally:
            permission.write_bytes(raw)
            if oldgo is None:
                if go.exists():go.unlink()
            else:go.write_bytes(oldgo)

    def test_41_permission_one_GO_concurrency_and_BrokenPipe_are_one_shot(self):
        import threading
        go=self.out/'GO.json';oldgo=go.read_bytes() if go.exists() else None
        class Sink:
            def __init__(self):self.bytes=0
            def write(self,data):self.bytes+=len(data);return len(data)
            def flush(self):pass
        try:
            if go.exists():go.unlink()
            owner=V.Owner(self.snapshot,self.owner.snapshot_raw,self.owner.seal_raw,1000.);ready=dict(self.record,kind='READY',remote_ready=10.);stream=Sink();results=[]
            def send():
                try:owner.sender(stream,ready,3697.,now=lambda:1001.);results.append('SENT')
                except ValueError:results.append('DENIED')
            threads=[threading.Thread(target=send) for _ in range(2)]
            for t in threads:t.start()
            for t in threads:t.join(10);self.assertFalse(t.is_alive())
            self.assertEqual(sorted(results),['DENIED','SENT']);self.assertEqual(R.parse(go.read_bytes())['new_runtime_permission_sha256'],R.digest(self.permission_raw))
            go.unlink();owner=V.Owner(self.snapshot,self.owner.snapshot_raw,self.owner.seal_raw,1000.);failure=BrokenPipeError('HOST_ONLY_PIPE_CLOSED')
            class Broken:
                def write(self,data):raise failure
                def flush(self):pass
            try:owner.sender(Broken(),ready,3697.,now=lambda:1001.)
            except BrokenPipeError as got:self.assertIs(got,failure)
            else:self.fail('BrokenPipe swallowed')
            with self.assertRaises(ValueError):owner.sender(Sink(),ready,3697.,now=lambda:1001.)
            self.assertTrue(owner.sent);self.assertTrue(go.exists())
        finally:
            if oldgo is None:
                if go.exists():go.unlink()
            else:go.write_bytes(oldgo)

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
    def test_12_actual_absent130_grant_refuses_before_preparation_or_mutation(self):
        self.assertFalse((V.OUT/'user-budget-grant.json').exists());self.assertFalse((V.OUT/'user-budget-reply.json').exists())
        with mock.patch.object(V,'source_snapshot',side_effect=AssertionError('MUST_NOT_PREPARE')):
            with self.assertRaises(FileNotFoundError):V.run()
        self.assertFalse((V.OUT/'admission.json').exists());self.assertFalse((V.OUT/'GO.json').exists())


class LocalWritesAndFrames(unittest.TestCase):
    def test_13_actual116_RGB_validator_replay_is_explicitly_NOT130_native(self):
        data,_,_=R.verify_release();M=R.load_raw('media_frame_replay130',data['media.py'],R.DERIVED/'media.py')
        old=R.ROOT/'outputs/blended-reference-trial-116/native-artifacts/runs/4f38ca9612b34716947baa6f56c96e05/retrieved'
        folder=HOST/('SYNTHETIC_HOST_OLD116_RGB_NOT130_NATIVE_'+uuid.uuid4().hex);(folder/'frames').mkdir(parents=True)
        png=(old/'frames/frame-0000.png').read_bytes();self.assertEqual(R.digest(png),'71d4d8d8265bf07eeb958c99c738274f69279d5f39d8c38a546542a0b86c8403')
        row=R.parse((old/'frames/frame-0000.json').read_bytes());row['phase']='hold:HOST_OLD116_NOT130_NATIVE'
        (folder/'frames/frame-0000.png').write_bytes(png)
        cfg=R.parse(data['config.json']);item=cfg['refs']['capture.py'];raw=R.read(R.ROOT/item['path']);self.assertEqual(R.digest(raw),item['sha256'])
        capture=R.load_raw('capture116_replay130',raw,R.ROOT/item['path'])
        def persist(value):
            b=R.encode(value);(folder/'frames/frame-0000.json').write_bytes(b)
            return {'frames/frame-0000.png':R.digest(png),'frames/frame-0000.json':R.digest(b)}
        self.assertEqual(len(M.validate_frames(folder,persist(row),capture)),1)
        bad=R.parse(R.encode(row));bad['freshness']['after']['rgb']['compute_count']=bad['freshness']['before']['rgb']['compute_count']
        with self.assertRaises(capture.CaptureError):M.validate_frames(folder,persist(bad),capture)
        bad=R.parse(R.encode(row));bad['state_index']=1
        with self.assertRaises(ValueError):M.validate_frames(folder,persist(bad),capture)
        self.assertFalse((folder/'robot-arm-v4-130.mp4').exists())

    def test_14_local_write_guard_uses_original_ROOT_ancestors_and_current_before_data(self):
        data,_,_=R.verify_release();D=R.load_raw('writeguard130',data['driver.py'],R.DERIVED/'driver.py')
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


class Native130Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np, contextlib, copy
        cls.np,cls.contextlib,cls.copy=np,contextlib,copy
        cls.data,_,_=R.verify_release()
        cls.N=R.load_raw('native130_actual_HOST',cls.data['native.py'],R.DERIVED/'native.py')
        cls.D=R.load_raw('native130_contract_HOST',cls.data['driver.py'],R.DERIVED/'driver.py');cls.C=cls.D.C
        cls.tree=ast.parse(cls.data['native.py']);cls.native=next(n for n in cls.tree.body if isinstance(n,ast.FunctionDef) and n.name=='_native')
        cls.names=list(cls.C.NAMES)
        cls.model={'movable':cls.names,'joints':{n:{'lower':-3.,'upper':3.,'velocity':.02 if n.startswith('KG1_slide') else 2. if n=='KG1_pinion' else .5} for n in cls.names}}
    def context(self,fail=None):
        writes=[];fail=fail or {};cfg=R.parse(self.data['config.json']);approval=R.parse(R.read(R.ROOT/R.CAP))
        cfg=dict(cfg,approval=approval,effective_caps=self.C.effective_caps(cfg,approval))
        def write(path,data):
            if Path(path).name in fail:raise fail[Path(path).name]
            writes.append((Path(path).name,R.parse(R.encode(data))))
        ctx=types.SimpleNamespace(job={'run_id':'b'*32},job_hash='c'*64,cfg=cfg,run=HOST/uuid.uuid4().hex,
            write=write,sha=lambda p:cfg['model_pins']['robot_arm.urdf']['sha256'],started_monotonic=time.monotonic(),native_budget=types.SimpleNamespace(check=lambda:None,phase='small',end=time.monotonic()+1000))
        return ctx,writes
    def robot_fixture(self,tensor_equal=False):
        np=self.np;names=self.names;C=self.C;outer=self
        class Backend:
            mode='usd'
            @outer.contextlib.contextmanager
            def use_backend(self,name,**kw):
                assert kw=={'raise_on_unsupported':True,'raise_on_fallback':True}
                old=self.mode;self.mode=name
                try:yield
                finally:self.mode=old
        backend=Backend();clock={'engine_time_s':0.,'lab_step':0};q={n:0. for n in names};qd=dict(q)
        class HostArray(np.ndarray):
            def numpy(self):return np.asarray(self)
        class Robot:
            dof_names=list(names)
            values={'usd':np.asarray([[C.binary32(outer.model['joints'][n]['velocity']) for n in names]],dtype=np.float32),
                    'tensor':np.asarray([[C.binary32(outer.model['joints'][n]['velocity']) if tensor_equal else 9. for n in names]],dtype=np.float32)}
            sets=[];touch=False
            def get_dof_max_velocities(self):return self.values[backend.mode].copy().view(HostArray)
            def set_dof_max_velocities(self,value):
                self.sets.append((backend.mode,np.asarray(value).copy()));self.values[backend.mode]=np.asarray(value,dtype=np.float32).reshape(1,9)
                if self.touch:q['J6']=1e-5
            def set_dof_drive_types(self,*a):pass
            def set_dof_gains(self,*a):pass
            def set_dof_max_efforts(self,*a):pass
            def set_enabled_self_collisions(self,*a):pass
            def set_link_enabled_gravities(self,*a):pass
            def get_dof_positions(self):return np.asarray([[q[n] for n in names]],dtype=np.float32)
            def get_dof_velocities(self):return np.asarray([[qd[n] for n in names]],dtype=np.float32)
        robot=Robot()
        def state():return {'q':dict(q),'qd':dict(qd),'clock':dict(clock),'clock_before':dict(clock),'clock_after':dict(clock),'body_poses':[]}
        return robot,backend,clock,q,qd,state
    def test_19_actual_native_velocity_callers_same_value_and_no_set(self):
        for equal in (False,True):
            ctx,writes=self.context();robot,backend,clk,q,qd,state=self.robot_fixture(equal)
            env=dict(self.N.__dict__,ctx=ctx,robot=robot,names=self.names,model=self.model,C=self.C,array=lambda v:self.np.asarray(v),backend=backend,velocity_clock=lambda:dict(clk),clock=lambda:dict(clk),state=state,report={},caps={n:1 for n in self.names},out=ctx.run/'output')
            usd=next(n for n in self.native.body if isinstance(n,ast.With) and 'set_dof_drive_types' in ast.unparse(n))
            usdcall=next(n for n in self.native.body if isinstance(n,ast.Assign) and "report['velocity_limits'] =" in ast.unparse(n))
            tensorcall=next(n for n in self.native.body if isinstance(n,ast.Assign) and "report['velocity_limits']['tensor_after_reset']" in ast.unparse(n))
            exec(compile(ast.Module(body=[usd,usdcall,tensorcall],type_ignores=[]),'<ACTUAL_NATIVE_VELOCITY_CALLERS>','exec'),env)
            self.assertEqual([x[0] for x in robot.sets],['usd'] if equal else ['usd','tensor'])
            self.assertEqual(ctx._velocity_audit['tensor_after_reset']['set_same_source_values'],not equal)
            self.assertEqual(clk,{'engine_time_s':0.,'lab_step':0});self.assertTrue(all(x==0 for x in q.values()))
    def test_20_velocity_mapping_shape_finite_readback_and_state_change_reject(self):
        for case in ('duplicate','order','shape','nan','badreadback','statechange','clock'):
            ctx,_=self.context();robot,backend,clk,q,qd,state=self.robot_fixture(False);names=list(self.names)
            if case=='duplicate':names[1]=names[0]
            if case=='order':robot.dof_names=list(reversed(names))
            if case=='shape':robot.values['tensor']=self.np.zeros(9)
            if case=='nan':robot.values['tensor'][0,5]=float('nan')
            if case=='badreadback':robot.set_dof_max_velocities=lambda v:None
            if case=='statechange':robot.touch=True
            if case=='clock':clk['engine_time_s']=.01
            with self.assertRaises(ValueError):self.N._velocity_limits(ctx,robot,names,self.model,self.C,lambda v:self.np.asarray(v),backend,lambda:dict(clk),state,True)
    def critical(self,ctx,report,kind='speed'):
        loop=next(n for n in ast.walk(self.native) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='local_step')
        a=next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and getattr(n.value.func,'id','')=='_fault_begin')
        z=next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Assign) and "ctx._fault_pending['accepted_journal']" in ast.unparse(n))
        code=compile(ast.Module(body=loop.body[a:z+1],type_ignores=[]),'<ACTUAL_NATIVE_POSTSTEP_CALLERS>','exec')
        clk={'engine_time_s':1428/120,'lab_step':1428};previous={'q':{n:0. for n in self.names},'qd':{n:0. for n in self.names},'clock':dict(clk),'body_poses':[]}
        class Sim:
            def step(self,render=False):clk.update(engine_time_s=1429/120,lab_step=1429)
        def state():
            clock=dict(clk) if kind!='stale' else {'engine_time_s':1428/120,'lab_step':1428}
            return {'q':{n:0. for n in self.names},'qd':{n:.6 if n=='J6' and kind=='speed' else 0. for n in self.names},'clock':clock,
                'body_poses':[{'name':'Base','position':[0.,0.,0.],'orientation_wxyz':[1.,0.,0.,0.]}]}
        if kind=='nonfinite':
            robot,backend,_,q,qd,_=self.robot_fixture(True);qd['J6']=float('nan')
            node=next(n for n in self.native.body if isinstance(n,ast.FunctionDef) and n.name=='state')
            se=dict(self.N.__dict__,ctx=ctx,clock=lambda:dict(clk),backend=backend,robot=robot,C=self.C,model=self.model,names=self.names,array=lambda v:self.np.asarray(v),links=[])
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<ACTUAL_NATIVE_STATE_READ>','exec'),se);state=se['state']
        journal=types.SimpleNamespace(rows=[],write=lambda text:journal.rows.append(text),flush=lambda:None)
        ctx._contact_probe=types.SimpleNamespace(last={'status':'CURRENT_STEP_REPORT_COPIED','owner_step':1428,'owner_clock_before':dict(clk),'owner_clock_after':dict(clk),'headers':[]},sample=lambda step:None,close=lambda:{'closed':True})
        C=types.SimpleNamespace(floor_and_bounds=lambda *a:(.01,{}),near=self.C.near,tf=self.C.tf,quat=self.C.quat,ident=self.C.ident)
        env=dict(self.N.__dict__,ctx=ctx,report=report,stage_name='small',local_step=1189,target={'targets':{n:0. for n in self.names},'reference_velocity':{n:0. for n in self.names},'velocity_targets':{n:0. for n in self.names}},current=previous,proof={},remaining={n:1. for n in self.names},sim=Sim(),state=state,baseline={'engine_time_s':0.,'lab_step':0},program={'dt_s':1/120},C=C,matrices=lambda o:{},support={},names=self.names,model=self.model,journal=journal,row_for=lambda *a:(_ for _ in ()).throw(AssertionError('INVALID_ROW_MUST_NOT_BE_JOURNALED')))
        report['completed_steps']=1428
        try:exec(code,env)
        finally:self.assertEqual(journal.rows,[])
    def test_21_actual_poststep_speed_failure_is_saved_without_valid_row_or_frame(self):
        ctx,writes=self.context();original=self.N._native
        def execute(c,a,report,budget):self.critical(c,report,'speed')
        with mock.patch.object(self.N,'_native',execute):
            with self.assertRaisesRegex(ValueError,'Actual source speed limit:J6'):self.N.collect(ctx,None)
        packet=next(v for n,v in writes if n=='first-fault.json')
        self.assertEqual(packet['attempted_step'],1429);self.assertEqual(packet['observed_state_index'],1429)
        self.assertEqual(packet['current_state']['qd']['J6'],.6);self.assertFalse(packet['accepted_journal'])
        self.assertEqual(next(v for n,v in writes if n=='report.json')['frames'],[])
    def test_22_stale_nonfinite_and_setup_measurement_never_relabel_previous(self):
        for kind in ('stale','nonfinite','setup'):
            ctx,writes=self.context()
            def execute(c,a,report,budget):
                if kind=='setup':raise ValueError('SETUP_PRIMARY')
                self.critical(c,report,kind)
            with mock.patch.object(self.N,'_native',execute):
                with self.assertRaises(ValueError):self.N.collect(ctx,None)
            packet=next(v for n,v in writes if n=='first-fault.json')
            self.assertFalse(packet['current_measurement_available'])
            if kind=='stale':self.assertEqual(packet['observed_state_index'],1428);self.assertEqual(packet['attempted_step'],1429)
            if kind=='nonfinite':
                self.assertIsNone(packet['current_state']);self.assertEqual(packet['raw_state_read']['qd'][5],{'nonfinite':'nan'})
                self.assertEqual(packet['contact']['status'],'UNKNOWN_NOT_OBSERVED_FOR_ATTEMPT')
                self.assertEqual(packet['contact']['owner_step'],1429);self.assertEqual(packet['contact']['previous_contact']['owner_step'],1428)
            if kind=='setup':self.assertEqual(packet['current_state_status'],'NOT_MEASURED_SETUP')
    def test_23_primary_object_survives_firstfault_finalwrite_and_cleanup_failures(self):
        primary=ValueError('EXACT_PRIMARY_OBJECT');secondary=OSError('SECONDARY_WRITE')
        ctx,writes=self.context({'first-fault.json':secondary,'report.json':secondary})
        ctx.init_boundary=types.SimpleNamespace(close=lambda:(_ for _ in ()).throw(RuntimeError('CLEANUP_SECONDARY')))
        def execute(*a):raise primary
        with mock.patch.object(self.N,'_native',execute):
            try:self.N.collect(ctx,None)
            except BaseException as got:self.assertIs(got,primary)
            else:self.fail('primary vanished')
        self.assertEqual(ctx._first_fault['primary']['type'],'ValueError')
        self.assertTrue({'first_fault_write','init_cleanup_exception','final_report_write'}<={x['where'] for x in ctx._diag_secondary})
    def test_24_GateFailure_return_and_secondary_camera_cleanup_finalwrite_preserve(self):
        primary=self.N.GateFailure('ORIGINAL_GATE');ctx,writes=self.context({'report.json':OSError('FINAL')})
        ctx.native_camera=types.SimpleNamespace(finish=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('CAMERA')))
        ctx.init_boundary=types.SimpleNamespace(finish=lambda *a:(_ for _ in ()).throw(RuntimeError('FINISH')),close=lambda:['CLOSE'])
        def execute(c,a,report,budget):report['frames']=[{'HOST_ONLY':True}];raise primary
        with mock.patch.object(self.N,'_native',execute):report=self.N.collect(ctx,None)
        self.assertEqual(report['gate_failure'],'ORIGINAL_GATE');self.assertEqual(ctx._first_fault['primary']['type'],'GateFailure')
        self.assertTrue({'camera_finish','boundary_finish','init_cleanup_errors','final_report_write'}<={x['where'] for x in report['diagnostic_secondary']})
    def test_25_finalwrite_without_previous_error_still_raises_original_write_object(self):
        failure=OSError('ONLY_FINAL_WRITE');ctx,_=self.context({'report.json':failure})
        with mock.patch.object(self.N,'_native',lambda *a:None):
            try:self.N.collect(ctx,None)
            except BaseException as got:self.assertIs(got,failure)
            else:self.fail('final write error vanished')
    def contact_fixture(self,arity=2):
        ctx,_=self.context();clk={'engine_time_s':1429/120,'lab_step':1429};state={'q':{n:0. for n in self.names},'qd':{n:0. for n in self.names}}
        ctx._fault_pending={'current_state':dict(self.copy.deepcopy(state),clock=dict(clk))};sets=[]
        class Attr:
            def __init__(self,name,value,authored=False):self.name,self.value,self.authored=name,value,authored
            def GetName(self):return self.name
            def GetTypeName(self):return 'float'
            def Set(self,v):sets.append((self.name,v));self.value=v;return True
            def Get(self):return self.value
            def HasAuthoredValueOpinion(self):return self.authored
        class Prim:
            def GetAttribute(self,n):return Attr(n,.02,False) if n=='physxCollision:contactOffset' else None
        class Stage:
            def GetPrimAtPath(self,p):return Prim()
        class Schema:
            class PhysxContactReportAPI:
                @staticmethod
                def Apply(p):return types.SimpleNamespace(CreateThresholdAttr=lambda:Attr('physxContactReport:threshold',1.,True))
        point=types.SimpleNamespace(position=[1.,2.,3.],normal=[0.,0.,1.],impulse=[0.,0.,.2],separation=-.00003)
        header=types.SimpleNamespace(stage_id=77,type='CONTACT_FOUND',actor0=1,actor1=2,collider0=3,collider1=4,contact_data_offset=0,num_contact_data=1)
        class Interface:
            attached=77
            raw=([header],[point]) if arity==2 else ([header],[point],[])
            def get_attached_stage(self):return self.attached
            def get_contact_report(self):return self.raw
        paths={1:'/World/Robot/KG1_A',2:'/World/Floor',3:'/World/Robot/KG1_A/shape',4:'/World/Floor/shape'}
        tools=types.SimpleNamespace(intToSdfPath=lambda v:paths[v],decodeSdfPath=lambda *v:paths[v[0][0] if len(v)==1 else v[0]])
        interface=Interface();probe=self.N._contact_setup(ctx,Stage(),['/World/Robot/KG1_A'],Schema,interface,77,lambda:dict(clk),lambda v:self.N._decode_contact_path(tools,v))
        probe.stage_reader=lambda:{'status':'OWNED_IDS_OBSERVED_NOT_YET_ADMITTED','cache_id':77,'context_id':77,'device':'cpu','backend_device':'cpu','root_layer':'anon:HOST_ROOT','session_layer':'anon:HOST_SESSION',**{k:True for k in ('sim_stage_same','lab_stage_same','kit_stage_same','manager_owner_same','cache_dereference_same','context_registration_same','lab_layers_same','kit_layers_same')}}
        probe.state_reader=lambda:self.copy.deepcopy(state)
        return ctx,probe,interface,header,point,clk,state,sets
    def test_26_contacts_tuple2_tuple3_ownedcopy_pairdecode_and_report_only_schema(self):
        for arity in (2,3):
            ctx,probe,interface,header,point,clk,state,sets=self.contact_fixture(arity)
            if arity==3:header.actor0=(1,0)
            value=probe.sample(1429);self.assertEqual(value['status'],'CURRENT_STEP_REPORT_COPIED');self.assertEqual(value['tuple_arity'],arity)
            header.actor0=999;point.position[0]=999
            self.assertEqual(value['headers'][0]['actor0'],'/World/Robot/KG1_A');self.assertEqual(value['headers'][0]['contacts'][0]['position'],[1.,2.,3.])
            self.assertEqual(sets,[('physxContactReport:threshold',0.)]);self.assertEqual(value['native_timestamp'],'NOT_PROVIDED_BY_HEADER')
            self.assertFalse(value['settings']['/World/Floor']['physxCollision:contactOffset']['authored']);self.assertFalse(value['settings']['/World/Floor']['physxCollision:contactOffset']['runtime_observed'])
            self.assertEqual(value['settings']['/World/Floor']['physxCollision:restOffset']['status'],'UNKNOWN_NOT_AVAILABLE')
            self.assertTrue(probe.close()['closed']);self.assertTrue(probe.close()['closed']);self.assertTrue(probe.sample(1429)['status'].startswith('UNKNOWN'))
    def test_27_contact_missing_overflow_stage_decoder_clock_qd_errors_are_unknown(self):
        for kind in ('missing','overflow','stage','headerstage','offset','decoder','clock','qd','arity'):
            ctx,probe,interface,header,point,clk,state,sets=self.contact_fixture()
            if kind=='missing':probe.enabled=False
            if kind=='overflow':interface.raw=([header],[point]*257)
            if kind=='stage':interface.attached=78
            if kind=='headerstage':header.stage_id=78
            if kind=='offset':header.num_contact_data=3
            if kind=='decoder':header.actor0='unknown'
            if kind=='arity':interface.raw=([],)
            if kind in ('clock','qd'):
                def get():
                    if kind=='clock':clk['lab_step']+=1
                    else:state['qd']['J6']=1.
                    return ([header],[point])
                interface.get_contact_report=get
            result=probe.sample(1429);self.assertTrue(result['status'].startswith('UNKNOWN'),kind)
            if kind in ('clock','qd'):self.assertTrue(result['observer_changed_state'])
    def test_28_zero_reported_pairs_are_not_a_no_contact_claim_and_bounds_are_enforced(self):
        ctx,probe,interface,header,point,clk,state,sets=self.contact_fixture();interface.raw=([],[])
        result=probe.sample(1429);self.assertEqual(result['reported_pairs'],0);self.assertIn('NOT_PROOF',result['zero_pairs_mean'])
        with self.assertRaises(ValueError):self.N._diag_owned([0.]*17000)
        primary=ValueError('COPY_PRIMARY');ctx,_=self.context();ctx._fault_pending={'bad':object(),'attempted_step':1429}
        report=self.N.ledger(ctx);self.N._save_first_fault(ctx,report,primary)
        self.assertTrue(any(x['where']=='first_fault_pending_copy' for x in ctx._diag_secondary))

    def test_29_composed_contact_ranges_are_bounded_and_actual_collect_keeps_J6_primary(self):
        ctx,probe,interface,header,point,clk,state,sets=self.contact_fixture()
        ctx._contact_probe=probe
        current=dict(self.copy.deepcopy(state),clock=dict(clk),body_poses=[]);current['qd']['J6']=.6;state['qd']['J6']=.6
        self.N._fault_begin(ctx,'small',1429,{}, {'clock':{'lab_step':1428}}, {},{})
        self.N._fault_observe(ctx,current)
        header.num_contact_data=256;interface.raw=([self.copy.deepcopy(header) for _ in range(64)],[point]*256)
        value=probe.sample(1429)
        self.assertTrue(value['status'].startswith('UNKNOWN'));self.assertIn('cumulative',value['error'])
        self.assertLessEqual(sum(len(h['contacts']) for h in value.get('headers',[])),256)
        primary=ValueError('Actual source speed limit:J6');writes=[]
        ctx.write=lambda path,data:writes.append((Path(path).name,R.parse(R.encode(data))))
        with mock.patch.object(self.N,'_native',lambda *a:(_ for _ in ()).throw(primary)):
            try:self.N.collect(ctx,None)
            except BaseException as got:self.assertIs(got,primary)
            else:self.fail('J6 primary vanished')
        self.assertTrue({'first-fault.json','report.json'}<={n for n,v in writes})
        self.assertEqual(next(v for n,v in writes if n=='first-fault.json')['current_state']['qd']['J6'],.6)
        self.assertTrue(next(v for n,v in writes if n=='report.json')['last_contact_observation']['status'].startswith('UNKNOWN'))
    def test_30_all_final_and_fault_diagnostic_overflows_publish_minimal_report_without_masking(self):
        primary=ValueError('ORIGINAL_J6_PRIMARY');ctx,writes=self.context()
        ctx._fault_pending={'attempted_step':1429,'bad':[0.]*17000}
        ctx._velocity_audit={'oversized':[0.]*17000}
        ctx._contact_probe=types.SimpleNamespace(last={'oversized':[0.]*17000},close=lambda:{'oversized':[0.]*17000})
        with mock.patch.object(self.N,'_native',lambda *a:(_ for _ in ()).throw(primary)):
            try:self.N.collect(ctx,None)
            except BaseException as got:self.assertIs(got,primary)
            else:self.fail('overflow masked primary')
        self.assertTrue({'first-fault.json','report.json'}<={n for n,v in writes})
        report=next(v for n,v in writes if n=='report.json');packet=next(v for n,v in writes if n=='first-fault.json')
        self.assertEqual(packet['current_state_status'],'UNAVAILABLE_DIAGNOSTIC_COPY_ERROR')
        self.assertTrue(all(report[k]['status']=='UNKNOWN_DIAGNOSTIC_COPY_ERROR' for k in ('contact_cleanup','last_contact_observation','velocity_limits')))
        self.assertEqual(packet['primary']['type'],'ValueError')

    def test_31_actual_native_official_cfg_call_has_exactly_one_default_delta(self):
        vendor=ast.parse(R.read(R.ROOT/'outputs/isaac-physics-v1/evidence/sdk-source/lab_physx_cfg.py'))
        cfg=next(n for n in vendor.body if isinstance(n,ast.ClassDef) and n.name=='PhysxCfg')
        defaults={}
        for n in cfg.body:
            if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.value is not None:
                try:defaults[n.target.id]=eval(compile(ast.Expression(n.value),'<CAPTURED_OFFICIAL_CFG_DEFAULT>','eval'),{'__builtins__':{}},{})
                except (NameError,TypeError,ValueError):defaults[n.target.id]=ast.dump(n.value)
        self.assertIs(defaults['solve_articulation_contact_last'],False)
        class Config:
            def __init__(self,**kw):self.values=dict(defaults,**kw);self.__dict__.update(self.values)
            def to_dict(self):return dict(self.values)
        captured={}
        def simcfg(**kw):captured.update(kw);return types.SimpleNamespace(**kw)
        env=dict(self.N.__dict__,PhysxCfg=Config,SimulationCfg=simcfg,SimulationContext=lambda cfg:types.SimpleNamespace(cfg=cfg),report={})
        calls=[n for n in self.native.body if isinstance(n,ast.Assign) and ('_constraint_order_cfg(' in ast.unparse(n) or 'sim = SimulationContext(' in ast.unparse(n))]
        self.assertEqual(len(calls),2)
        exec(compile(ast.Module(body=calls,type_ignores=[]),'<ACTUAL_NATIVE_SIMULATION_CFG_CALLSITE>','exec'),env)
        self.assertEqual({k:v for k,v in captured.items() if k!='physics'},{'dt':1/120,'device':'cpu','gravity':(0.,0.,-9.81),'physics_prim_path':'/World/physicsScene','use_newton_actuators':False})
        candidate=captured['physics'].to_dict();self.assertEqual([k for k in defaults if defaults[k]!=candidate[k]],['solve_articulation_contact_last'])
        for bad in ('false','other'):
            class Wrong(Config):
                def __init__(self,**kw):
                    super().__init__(**kw)
                    if kw:
                        if bad=='false':self.values['solve_articulation_contact_last']=False
                        else:self.values['solver_type']=0
            with self.assertRaises(ValueError):self.N._constraint_order_cfg(Wrong)

    def order_fixture(self):
        attr=types.SimpleNamespace(value=True,Get=lambda:attr.value,GetTypeName=lambda:'bool',HasAuthoredValueOpinion=lambda:True)
        layer=types.SimpleNamespace(identifier='anon:HOST_ORDER')
        stage=types.SimpleNamespace(GetPrimAtPath=lambda p:types.SimpleNamespace(GetAttribute=lambda n:attr),GetRootLayer=lambda:layer,GetSessionLayer=lambda:layer)
        sim=types.SimpleNamespace(stage=stage,cfg=types.SimpleNamespace(physics=types.SimpleNamespace(solve_articulation_contact_last=True)))
        clk={'engine_time_s':0.,'lab_step':0};state={'q':{'J6':0.},'qd':{'J6':0.}}
        return attr,stage,sim,clk,state

    def test_32_actual_native_before_after_reset_readbacks_and_mutations(self):
        attr,stage,sim,clk,state=self.order_fixture();ctx,writes=self.context()
        env=dict(self.N.__dict__,sim=sim,stage=stage,velocity_clock=lambda:dict(clk),clock=lambda:dict(clk),contact_state_read=lambda:self.copy.deepcopy(state),report={'constraint_order':{}},ctx=ctx,out=ctx.run/'output')
        calls=[n for n in self.native.body if isinstance(n,ast.Assign) and "report['constraint_order']" in ast.unparse(n) and '_constraint_order_readback(' in ast.unparse(n)]
        self.assertEqual(len(calls),2)
        exec(compile(ast.Module(body=calls,type_ignores=[]),'<ACTUAL_NATIVE_CONSTRAINT_READBACK_CALLERS>','exec'),env)
        self.assertIs(env['report']['constraint_order']['before_reset']['value'],True);self.assertIs(env['report']['constraint_order']['after_reset']['value'],True)
        for bad in ('false','resolved','clock','state'):
            attr,stage,sim,clk,state=self.order_fixture()
            if bad=='false':attr.value=False
            if bad=='resolved':sim.cfg.physics.solve_articulation_contact_last=False
            def read():
                if bad=='state':state['qd']['J6']+=.1
                return self.copy.deepcopy(state)
            def clock():
                if bad=='clock':clk['lab_step']+=1
                return dict(clk)
            with self.assertRaises(ValueError):self.N._constraint_order_readback(sim,stage,clock,read)

    def owner_fixture(self,device='cpu'):
        ctx,probe,interface,header,point,clk,state,sets=self.contact_fixture()
        stage=probe.stage;root=types.SimpleNamespace(identifier='anon:HOST_ROOT');session=types.SimpleNamespace(identifier='anon:HOST_SESSION')
        stage.GetRootLayer=lambda:root;stage.GetSessionLayer=lambda:session
        ident=types.SimpleNamespace(ToLongInt=lambda:77)
        cache=types.SimpleNamespace(GetId=lambda s:ident,Find=lambda i:stage)
        context=types.SimpleNamespace(get_stage_id=lambda:77,get_stage=lambda:stage)
        sim=types.SimpleNamespace(stage=stage,cfg=types.SimpleNamespace(device=device))
        manager=types.SimpleNamespace(_sim=sim,get_device=lambda:device)
        env=dict(self.N.__dict__,ctx=ctx,sim=sim,stage=stage,omni=types.SimpleNamespace(usd=types.SimpleNamespace(get_context=lambda:context)),UsdUtils=types.SimpleNamespace(StageCache=types.SimpleNamespace(Get=lambda:cache)),get_current_stage=lambda:stage,PhysxManager=manager)
        actual=next(n for n in ast.walk(self.native) if isinstance(n,ast.Assign) and 'ctx._contact_probe.stage_reader =' in ast.unparse(n))
        ctx._contact_probe=probe
        exec(compile(ast.Module(body=[actual],type_ignores=[]),'<ACTUAL_NATIVE_STAGE_PROOF_WIRING>','exec'),env)
        return ctx,probe,interface,header,point,clk,state,sets,env,context,cache,manager,root

    def test_33_actual_CPU_implicit_and_GPU_explicit_same_owned_stage_current_reports(self):
        for device,attached,mode in (('cpu',0,'CPU_KIT_IMPLICIT_CURRENT_STAGE'),('cuda:0',77,'GPU_EXPLICIT_CURRENT_STAGE')):
            ctx,p,i,h,point,clk,state,sets,env,context,cache,manager,root=self.owner_fixture(device);i.attached=attached
            got=p.sample(1429);self.assertEqual(got['status'],'CURRENT_STEP_REPORT_COPIED');self.assertEqual(got['stage_provenance']['mode'],mode)
            self.assertEqual(got['stage_provenance']['attached_stage_id'],attached);self.assertEqual(got['stage_provenance']['header_stage_ids'],[77])
            point.impulse[2]=999.;root.identifier='CHANGED_NEXT_STEP';h.stage_id=999
            self.assertEqual(got['headers'][0]['contacts'][0]['impulse'],[0.,0.,.2]);self.assertEqual(got['stage_provenance']['current']['root_layer'],'anon:HOST_ROOT')
            self.assertEqual(clk,{'engine_time_s':1429/120,'lab_step':1429});self.assertEqual(state['qd']['J6'],0.)

    def test_34_actual_stage_proof_unproven_zero_wrong_header_owner_and_changed_stage_stay_UNKNOWN(self):
        for bad in ('no_callback','gpu_zero','context','cache','lab','kit','manager','header_zero','header_wrong','actor','during_getter'):
            ctx,p,i,h,point,clk,state,sets,env,context,cache,manager,root=self.owner_fixture('cuda:0' if bad=='gpu_zero' else 'cpu');i.attached=0
            if bad=='no_callback':p.stage_reader=None
            if bad=='context':context.get_stage_id=lambda:88
            if bad=='cache':cache.Find=lambda ident:None
            if bad=='lab':env['get_current_stage']=lambda:None
            if bad=='kit':context.get_stage=lambda:None
            if bad=='manager':manager._sim=None
            if bad=='header_zero':h.stage_id=0
            if bad=='header_wrong':h.stage_id=88
            if bad=='actor':p.stage.GetPrimAtPath=lambda path:None
            if bad=='during_getter':
                def getter():root.identifier='DIFFERENT_ROOT';return ([h],[point])
                i.get_contact_report=getter
            got=p.sample(1429);self.assertTrue(got['status'].startswith('UNKNOWN'),bad)
            if bad!='no_callback':self.assertIn('attached_stage_id',got['stage_provenance'])
            if bad in ('header_zero','header_wrong'):self.assertEqual(got['stage_provenance']['header_stage_ids'],[h.stage_id])

    def test_35_actual_new_stage_producer_is_bounded_owned_and_preserves_primary_collection(self):
        ctx,p,i,h,point,clk,state,sets,env,context,cache,manager,root=self.owner_fixture();i.attached=0
        context.get_stage_id=lambda:88
        for _ in range(20):p.sample(1429)
        self.assertEqual(len(ctx._diag_secondary),12)
        self.assertTrue(all(set(row)=={'where','type','message'} and all(type(v) is str and len(v)<=1000 for v in row.values()) for row in ctx._diag_secondary))
        first=self.copy.deepcopy(p.last);context.get_stage_id=lambda:77
        self.assertEqual(first['stage_provenance']['current']['context_id'],88)
        self.N._fault_begin(ctx,'small',1429,{}, {'clock':{'lab_step':1428}}, {},{})
        self.N._fault_observe(ctx,dict(self.copy.deepcopy(state),clock=dict(clk),body_poses=[]))
        context.get_stage_id=lambda:88;p.sample(1429)
        primary=ValueError('Actual source speed limit:J6');writes=[];ctx.write=lambda path,value:writes.append((Path(path).name,R.parse(R.encode(value))))
        with mock.patch.object(self.N,'_native',lambda *a:(_ for _ in ()).throw(primary)):
            try:self.N.collect(ctx,None)
            except BaseException as got:self.assertIs(got,primary)
            else:self.fail('primary was lost')
        self.assertTrue({'first-fault.json','report.json'}<={n for n,value in writes})
        self.assertTrue(next(value for name,value in writes if name=='report.json')['last_contact_observation']['status'].startswith('UNKNOWN'))


if __name__=='__main__':unittest.main(verbosity=2)
