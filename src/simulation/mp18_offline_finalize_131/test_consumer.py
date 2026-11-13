"""HOST-only131 actual recovered-data checks; no extraction/SDK/SSH or actual encoding."""
import copy,hashlib,importlib.util,json,sys,time,types,unittest,uuid
from pathlib import Path
from unittest import mock
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('consumer131_HOST',HERE/'consumer.py');C=importlib.util.module_from_spec(spec);sys.modules[spec.name]=C;spec.loader.exec_module(C)
HOST=C.OUT/'HOST';HOST.mkdir(exist_ok=True)
def fixture(out):
    (out/'review').mkdir(parents=True)
    paths=['src/simulation/mp18_offline_finalize_131/consumer.py','src/simulation/mp18_offline_finalize_131/test_consumer.py',C.PLAN,'outputs/mp18-offline-finalize-131/manifest.json',*C.PINS]
    f={'unit':131,'HOST_ONLY_NOT_CANONICAL':True,'files':{p:{'sha256':C.digest((C.ROOT/p).read_bytes()),'bytes':(C.ROOT/p).stat().st_size} for p in paths}}
    raw=json.dumps(f).encode();(out/'review/source-freeze.json').write_bytes(raw)
    l={'unit':131,'phase':'L4','round':1,'non_author':True,'verdict':'PASS','unmet':0,'unresolved_count':0,'source_freeze_sha256':C.digest(raw),'HOST_ONLY_NOT_CANONICAL':True}
    (out/'review/main-L4-final.json').write_text(json.dumps(l),'utf8')
class Compatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=HOST/('actual-'+uuid.uuid4().hex);fixture(cls.out);at=time.monotonic();cls.ctx=C.Context(cls.out);cls.capture_s=time.monotonic()-at
        cls.child=cls.ctx.read(cls.ctx.folder/'process.json');cls.term=cls.ctx.read(cls.ctx.folder/'terminal.json');cls.seal=cls.ctx.read(cls.ctx.folder/'recovery-seal.json')['files_sha256']
        cls.native_ctx=types.SimpleNamespace(job=cls.ctx.job,job_hash=C.JOB_SHA,cfg=cls.ctx.cfg,data=cls.ctx.data,run=cls.ctx.run)
        print(json.dumps({'HOST_ONLY':'ACTUAL1163_CAPTURED_READONLY','capture_s':cls.capture_s,'files':cls.ctx.audit['recovered_files'],'SDK':0,'SSH':0}),flush=True)
    def light(self,terminal=None):
        x=object.__new__(C.Context);x.folder=self.ctx.folder;x.record=self.ctx.record;x.audit={};x.cache=dict(self.ctx.cache)
        term=copy.deepcopy(self.term if terminal is None else terminal);raw=json.dumps(term,separators=(',',':')).encode()
        x.cache[str(x.folder/'terminal.json')]=raw;x.cache[str(x.folder/'status.json')]=raw
        return x,term
    def complete(self,x,t,child=None,seal=None):return x.complete(self.native_ctx,x.folder,copy.deepcopy(self.child if child is None else child),t,copy.deepcopy(self.seal if seal is None else seal),self.ctx.record)
    def test_01_exact_original_CLOSED_only_bug_rejects_real_success_before_write(self):
        d=self.ctx.D;original=self.ctx.original_verify.decode()
        exec(compile(original,'<ACTUAL130_ORIGINAL_VERIFY>','exec'),d.__dict__)
        try:
            with self.assertRaisesRegex(ValueError,'Incomplete diagnostic requires actual failed lifetime'):d.verify_native_result(self.ctx.run,self.ctx.record,self.ctx.folder)
            self.assertFalse((self.out/'native-result.json').exists())
        finally:exec(compile(self.ctx.derived_verify.decode(),'<ACTUAL131_DERIVED_VERIFY>','exec'),d.__dict__)
    def test_02_actual1163_strict_preclose_positive_calls_original_SDK_numeric_and_binding(self):
        result=self.ctx.consume();self.assertEqual(result['status'],'PASS');self.assertEqual(self.ctx.audit['native_members'],1157)
        self.assertEqual(self.ctx.audit['raw_terminal_status'],'COMPLETE_PRE_CLOSE');self.assertEqual(self.ctx.audit['original_SDK_verify_records']['numeric'],'SDK_PINNED_BEFORE_AFTER')
        native=C.parse((self.out/'native-result.json').read_bytes());self.assertEqual(native['capture_provenance'],'SDK_PRE_CLOSE_SEAL_AND_PARENT_REAPED_0');self.assertEqual(len(native['phases']),4)
        self.assertTrue(all(p['status']=='PASS' for p in native['phases']))
        print(json.dumps({'HOST_ONLY':'STRICT_REAL1163_POSITIVE','native_seal':1157,'original_SDK_verify_records':self.ctx.audit['original_SDK_verify_records'],'source_terminal_sha256':C.sha(self.ctx.folder/'terminal.json'),'raw_terminal_unchanged':True}),flush=True)
    def test_03_existing_CLOSED_APP_CLOSED_valid_shape_is_supported_without_rewriting_raw(self):
        term=copy.deepcopy(self.term);term.update(status='CLOSED',phase='APP_CLOSED');x,t=self.light(term);self.assertTrue(self.complete(x,t))
        self.assertEqual(C.sha(self.ctx.folder/'terminal.json'),'9dd522a2ec91459577c79a5201f7d6c241dd5a41bda4cf9ba8e84c30bfb8c158')
    def test_04_typed_process_epoch_parent_and_terminal_mutations_never_promote(self):
        for key,value in [('actual_child_exit_code',1),('actual_child_exit_code',False),('policy_exit_code',1),('job_active_after',1),('raw_complete',False),('timed_out',True),('errors',['FAIL']),('child_pid',True),('parent_pid',True),('job_sha256','0'*64),('run_id','f'*32)]:
            p=copy.deepcopy(self.child);p[key]=value;x,t=self.light()
            with self.assertRaises((ValueError,KeyError),msg=key):self.complete(x,t,p)
        for key,value in [('status','FAILED'),('status','UNKNOWN'),('phase','APP_CLOSED'),('code',1),('code',False),('pid',True),('parent_pid',999),('job_sha256','0'*64),('hardware_approved',True),('physical_calibration',True),('training','RUN')]:
            term=copy.deepcopy(self.term);term[key]=value;x,t=self.light(term)
            with self.assertRaises((ValueError,KeyError),msg=key):self.complete(x,t)
        x,t=self.light();x.cache[str(x.folder/'status.json')]=b'{}'
        with self.assertRaises(ValueError):self.complete(x,t)
    def test_05_seal_keyset_and_byte_mutations_reject_before_acceptance(self):
        for mode in ('missing','extra','hash'):
            term=copy.deepcopy(self.term);seal=copy.deepcopy(self.seal)
            if mode=='missing':term['files_sha256'].pop('numeric-after.json')
            if mode=='extra':term['files_sha256']['process.json']=seal['process.json']
            if mode=='hash':term['files_sha256']['numeric-after.json']='0'*64;seal['numeric-after.json']='0'*64
            x,t=self.light(term)
            with self.assertRaises(ValueError):self.complete(x,t,seal=seal)
    def test_06_actual_original_SDK_postnumeric_and_binding_consumer_rejects(self):
        d=self.ctx.D;sys.modules['driver']=d;sdk=d.load_module('sdk131_negative_HOST',self.ctx.data['ref/sdk.py'],self.ctx.run/'input/ref/sdk.py');original=sdk.read
        for case in ('numeric-after.json','binding-after.json'):
            def altered(p):
                if Path(p).name==case:
                    if case=='numeric-after.json':return {}
                    bad=copy.deepcopy(original(p));bad['torch']+=1;return bad
                return original(p)
            with mock.patch.object(sdk,'read',altered):
                with self.assertRaises((ValueError,KeyError)):sdk.verify_records(self.native_ctx,self.ctx.folder,self.term)
        def missing(p):
            if Path(p).name=='numeric-after.json':raise FileNotFoundError('HOST missing postnumeric')
            return original(p)
        with mock.patch.object(sdk,'read',missing):
            with self.assertRaises(FileNotFoundError):sdk.verify_records(self.native_ctx,self.ctx.folder,self.term)
    def test_07_current_data_source_and_typed131_review_guard(self):
        actual=C.sha;changed=self.ctx.folder/'numeric-after.json'
        with mock.patch.object(C,'sha',lambda p:'0'*64 if Path(p)==changed else actual(p)):
            with self.assertRaises(ValueError):self.ctx.guard()
        path=self.out/'review/main-L4-final.json';raw=path.read_bytes();obj=C.parse(raw);obj['round']=True;path.write_text(json.dumps(obj),'utf8')
        try:
            with self.assertRaises(ValueError):C.review_gate(self.out)
        finally:path.write_bytes(raw)
        normal=Path.is_junction
        with mock.patch.object(Path,'is_junction',lambda p:Path(p)==self.ctx.run or normal(p)):
            with self.assertRaises(ValueError):C.path_guard(self.ctx.folder/'report.json')
    def test_08_actual_original561_frame_validator_and_before_media_invoke_current(self):
        m=self.ctx.media();capture=self.ctx.D.load_module('capture131_frames_HOST',self.ctx.data['ref/capture.py'],self.ctx.folder/'original-capture.py')
        rows=m.validate_frames(self.ctx.folder,self.seal,capture);self.assertEqual(len(rows),561);self.assertEqual(rows[-1]['physics_time_s'],56.)
        called=[];actual=C.sha
        with mock.patch.object(C,'sha',lambda p:'0'*64 if Path(p)==self.ctx.folder/'numeric-after.json' else actual(p)),mock.patch.object(m.subprocess,'run',lambda *a,**k:called.append(1)):
            with self.assertRaises(ValueError):m.invoke(['ffprobe','HOST_ONLY_NO_ACTUAL_TOOL'])
        self.assertEqual(called,[])
        print(json.dumps({'HOST_ONLY':'ORIGINAL561_RGBA_VALIDATOR_READONLY','frames':len(rows),'SDK':0,'SSH':0,'actual_encode':0}),flush=True)
if __name__=='__main__':unittest.main(verbosity=2)
