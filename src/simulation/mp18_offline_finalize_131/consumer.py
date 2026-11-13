"""131 offline-only lifecycle compatibility. No SDK/SSH/network entry point."""
from __future__ import annotations
import argparse,ast,hashlib,json,math,sys,types,zipfile
from pathlib import Path
from types import MappingProxyType
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OUT=ROOT/'outputs/mp18-offline-finalize-131';OLD=ROOT/'outputs/mp18-profile-repair-130'
RUN_ID='dee4f7e320ea464aabd34bc41740efe1';JOB_SHA='bbba39e02d168ba15e04a907cf832ec374ce92ddf81568f2782c6b3795e1fbcc'
PLAN='docs/design/131-offline-preclose-consumer-compatibility.md';PLAN_SHA='c511830a4d8497040221a05311071cbd6e52dfe73e48a04da52b3a7ee17d4454'
ARCHIVE_SHA='b7e90d5d76643f6a29bdc24a0cb80c1e3ade19eea361fc3579e899c8f65ada45';ARCHIVE_BYTES=212046781
EXCLUDED={'process.json','status.json','stderr.txt','stdout.txt','terminal.json'}
PINS={
 'src/simulation/mp18_profile_repair_130/runner.py':'1af71c2a2cec59ca3ac38fa09640fb35d1de69cdb76233811fbd9bca591007f0',
 'src/simulation/mp18_isaac_130/driver.py':'a9e9cce9fe9c56812123be8b207591092cf7ce75328a24e2c9a7e75b59d29dea',
 'src/simulation/mp18_isaac_130/media.py':'63ff61fed3f5767206d366891ac06b5ee6fbdc971a63289fc15b7067cb005b30',
 'src/simulation/clock_ready_resume_108/sdk.py':'f3d3dd3d3c7ff8aa2774689e135b64a3d85a61701a8e9a6810313bbdc6aa06cf',
 'outputs/mp18-profile-repair-130/review/source-freeze.json':'ebc92a386965044fea307671028ddf2214ae32554d60083b4e750e13181f1a82',
 'outputs/mp18-profile-repair-130/review/main-L4-final.json':'db953eaa57c099e9c4c37435a2f7e5f2655d5f90613e90ce1037540f7855bb1d',
 'outputs/mp18-profile-repair-130/new-runtime-permission.json':'2fa8169c41ea0bcd6d8dc8d3bd17dbb9cad41e6b9aaf50da6a00b166c1149b10',
 'outputs/mp18-profile-repair-130/user-budget-grant.json':'bc45001c0b4c0a7570057ed0dce99cb4b6259528e4bb7ba2626f72ad7da44b7a',
 'outputs/mp18-offline-finalize-131/source-authorization.json':'e8ddb44e2c46b819bc39fd56244ec9cd93b318847e03f0e646e413c4e48a75e8'
}
def need(ok,message):
    if not ok:raise ValueError(message)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def path_guard(path):
    p=Path(path);need(p.is_absolute() and p.is_relative_to(ROOT),'Original ROOT role')
    for q in (p,*p.parents):need(not q.is_symlink() and not q.is_junction(),'Reparse path/ancestor denied')
    need(ROOT.resolve()==ROOT and p.resolve().is_relative_to(ROOT),'Original ROOT resolution');return p
def read_raw(path):return path_guard(path).read_bytes()
def sha(path):
    h=hashlib.sha256()
    with path_guard(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def parse(raw):
    def pairs(rows):
        result={}
        for k,v in rows:need(k not in result,'Duplicate JSON key');result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def load_raw(name,raw,path):
    m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(raw,str(path),'exec'),m.__dict__);return m
def checked(relative):
    raw=read_raw(ROOT/relative);need(digest(raw)==PINS[relative],'Pinned original source/data: '+relative);return raw
def span(raw,node):
    ls=raw.splitlines(keepends=True);a=sum(map(len,ls[:node.lineno-1]))+node.col_offset;b=sum(map(len,ls[:node.end_lineno-1]))+node.end_col_offset;return raw[a:b]
def function(raw,name):return span(raw,next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==name))
def review_gate(out=OUT):
    fraw=read_raw(out/'review/source-freeze.json');f=parse(fraw)
    required={'src/simulation/mp18_offline_finalize_131/'+n for n in ('consumer.py','test_consumer.py')}|{PLAN,'outputs/mp18-offline-finalize-131/manifest.json'}
    need(type(f.get('unit')) is int and f['unit']==131 and type(f.get('files')) is dict and required<=set(f['files']),'Typed complete131 source freeze')
    for rel,pin in f['files'].items():
        p=ROOT/rel;need(not Path(rel).is_absolute() and '..' not in Path(rel).parts and '\\' not in rel and ':' not in rel,'Canonical source file role')
        raw=read_raw(p);need(digest(raw)==pin['sha256'] and len(raw)==pin['bytes'],'Current131 source/data drift')
    lraw=read_raw(out/'review/main-L4-final.json');l=parse(lraw)
    need(type(l.get('unit')) is int and l['unit']==131 and l.get('phase')=='L4' and type(l.get('round')) is int and l['round'] in (1,2) and l.get('non_author') is True and l.get('verdict')=='PASS' and type(l.get('unmet')) is int and l['unmet']==0 and type(l.get('unresolved_count')) is int and l['unresolved_count']==0 and l.get('source_freeze_sha256')==digest(fraw),'Final typed131 independent source authority')
    return ((out/'review/source-freeze.json',fraw),(out/'review/main-L4-final.json',lraw))
def process_zero(p,label):
    need(type(p) is dict and p.get('child_state')=='REAPED' and p.get('raw_complete') is True and p.get('terminal') is True and p.get('timed_out') is False and p.get('errors')==[],label+' actual reaped complete no-timeout/no-errors')
    for k in ('actual_child_exit_code','policy_exit_code','job_active_after'):need(type(p.get(k)) is int and p[k]==0,label+' typed zero '+k)
    need(type(p.get('child_pid')) is int and p['child_pid']>0,label+' actual PID')
class Context:
    def __init__(self,out=OUT):
        self.out=path_guard(out);self.source_rows=review_gate(self.out);self.audit={};self.pins={};self.cache={}
        for p,h in PINS.items():checked(p)
        need(digest(read_raw(ROOT/PLAN))==PLAN_SHA,'Fixed131 plan')
        V=load_raw('owner130_offline131',checked('src/simulation/mp18_profile_repair_130/runner.py'),ROOT/'src/simulation/mp18_profile_repair_130/runner.py')
        self.V,self.owner=V,V.offline_owner(OLD);self.record=V.parse(self.owner.snapshot.record_raw);self.run=OLD/'runs'/RUN_ID;self.folder=self.run/'retrieved'
        need(self.record['run_id']==RUN_ID and self.record['job_sha256']==JOB_SHA,'Actual approved original130 run/job')
        D=V.driver(self.owner.snapshot);self.job,self.data,self.cfg=D.verified_payload(self.run,self.record)
        self.D=D;self.input_rows=dict(self.owner.snapshot.inputs)
        self.capture()
        self.original_verify=function(checked('src/simulation/mp18_isaac_130/driver.py'),'verify_native_result')
        code=self.original_verify.decode();old="complete = terminal is not None and terminal['status'] == 'CLOSED' and terminal['code'] == 0"
        need(code.count(old)==1,'Exact CLOSED-only predicate span')
        code=code.replace(old,'complete = _completion_131(ctx, destination, child, terminal, seal, record)')
        need(code.count('sdk.verify_records(ctx, destination, terminal)')==1,'Exact original SDK postcheck call')
        code=code.replace('sdk.verify_records(ctx, destination, terminal)','_record_sdk_131(sdk.verify_records(ctx, destination, terminal))')
        code=code.replace("'SDK_CLOSED_SEAL' if complete else 'REAPED_PARENT_RECOVERY_SEAL_PARTIAL'","_provenance_131(terminal) if complete else 'REAPED_PARENT_RECOVERY_SEAL_PARTIAL'")
        self.derived_verify=code.encode();D.OUT=self.out
        D.read=self.read;D.write=self.write;D.sha=sha;D._review_gate=self.guard;D._local_write_guard=self.write_path
        D.verified_payload=self.payload;D._completion_131=self.complete;D._record_sdk_131=self.record_sdk;D._provenance_131=self.provenance
        D.bind_local_authority(self.guard,lambda p:self.input_rows[str(p)])
        exec(compile(code,str(HERE/'consumer.py')+'::<PINNED130_VERIFY_SPAN>','exec'),D.__dict__)
    def capture(self):
        archive=self.run/'retrieved.zip';need(archive.stat().st_size==ARCHIVE_BYTES and sha(archive)==ARCHIVE_SHA,'Original complete RESULT archive')
        self.pin(archive)
        wire=OLD/'transport/stdout.txt'
        with path_guard(wire).open('rb') as f:
            ready_raw=f.readline(65537);header_raw=f.readline(65537);need(ready_raw.endswith(b'\n') and header_raw.endswith(b'\n'),'Closed original wire headers')
            ready,header=map(parse,(ready_raw,header_raw));expected=dict(self.record)
            need(set(ready)==set(expected)|{'kind','remote_ready'} and ready['kind']=='READY' and all(ready[k]==v for k,v in expected.items()),'Original READY identity')
            need(set(header)=={'kind','run_id','nonce','bytes','sha256'} and header['kind']=='RESULT' and header['run_id']==RUN_ID and header['nonce']==self.record['nonce'] and type(header['bytes']) is int and header['bytes']==ARCHIVE_BYTES and header['sha256']==ARCHIVE_SHA,'Original closed RESULT identity')
            h=hashlib.sha256();size=0
            for b in iter(lambda:f.read(1024*1024),b''):size+=len(b);h.update(b)
            need(size==ARCHIVE_BYTES and h.hexdigest()==ARCHIVE_SHA,'Actual RESULT complete tail bytes')
        self.pin(wire)
        files=[p for p in self.folder.rglob('*') if p.is_file()];need(len(files)==1163,'Actual complete1163 file inventory')
        names=[p.relative_to(self.folder).as_posix() for p in files];need(len(names)==len(set(n.casefold() for n in names)),'Unique recovered roles')
        for p in files:self.pin(p,cache=p.suffix=='.json')
        with zipfile.ZipFile(archive) as z:
            infos=z.infolist();need(len(infos)==len(names) and {i.filename for i in infos}==set(names),'Original ZIP and recovered inventory identical')
            for info in infos:
                need(not info.is_dir() and info.flag_bits&1==0 and (info.external_attr>>16)&0o170000!=0o120000,'Original ZIP member role')
                h=hashlib.sha256();size=0
                with z.open(info) as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block);size+=len(block)
                need(self.pins[str(self.folder/info.filename)]==(h.hexdigest(),size) and size==info.file_size,'Actual ZIP bytes/CRC match recovered member')
        recovery=self.read(self.folder/'recovery-seal.json');need(recovery['unit']==119 and recovery['run_id']==RUN_ID and recovery['job_sha256']==JOB_SHA,'Original recovery owner')
        need(set(recovery['files_sha256'])==set(names)-{'recovery-seal.json'},'Exact full recovery keyset')
        for n,h in recovery['files_sha256'].items():need(self.pins[str(self.folder/n)][0]==h,'Actual recovered SHA '+n)
        for p in (OLD/'transport.json',OLD/'run-result.json',OLD/'production-run-process.json'):
            if p.exists():self.pin(p,cache=True)
        self.audit.update(recovered_files=1163,recovery_members=len(recovery['files_sha256']),archive_sha256=ARCHIVE_SHA)
    def pin(self,path,cache=False):
        p=path_guard(path);raw=read_raw(p) if cache else None;h=digest(raw) if raw is not None else sha(p)
        self.pins[str(p)]=(h,p.stat().st_size)
        if raw is not None:self.cache[str(p)]=raw
    def read(self,path):
        p=path_guard(path);raw=self.cache.get(str(p));return parse(raw if raw is not None else read_raw(p))
    def raw(self,path):return self.cache.get(str(path_guard(path))) or read_raw(path)
    def payload(self,run,record):
        need(Path(run)==self.run and record==self.record,'Captured actual original payload only');self.guard();return self.job,self.data,self.cfg
    def guard(self):
        for p,raw in self.source_rows:need(read_raw(p)==raw,'Current131 F/review raw')
        review_gate(self.out);self.owner.current(False)
        for p,(h,size) in self.pins.items():
            path=path_guard(p);need(path.stat().st_size==size and sha(path)==h,'Current original closed artifact changed: '+p)
        current={p.relative_to(self.folder).as_posix() for p in self.folder.rglob('*') if p.is_file()}
        need(current=={Path(p).relative_to(self.folder).as_posix() for p in self.pins if Path(p).is_relative_to(self.folder)},'Current recovered inventory unchanged')
    def write_path(self,path):
        self.guard();p=path_guard(path);need(p.is_relative_to(self.out),'Only131 output role');return p
    def write(self,path,value):
        p=self.write_path(path);raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        if p.exists():need(p.name=='native-result.json' and read_raw(p)==raw,'Preserve existing131 output')
        p.parent.mkdir(parents=True,exist_ok=True);self.guard();path_guard(p).write_bytes(raw)
    def complete(self,ctx,folder,child,terminal,seal,record):
        need(Path(folder)==self.folder and record==self.record and ctx.job_hash==JOB_SHA and ctx.job['run_id']==RUN_ID,'Direct original130 context identity')
        process_zero(child,'SDK');transport=self.read(OLD/'transport.json');process_zero(transport,'Local transport')
        need(type(child.get('parent_pid')) is int and child['parent_pid']>0,'Typed SDK parent PID')
        need(type(terminal) is dict and self.raw(self.folder/'status.json')==self.raw(self.folder/'terminal.json') and parse(self.raw(self.folder/'terminal.json'))==terminal,'Actual identical terminal/status raw')
        need(type(terminal.get('pid')) is int and type(terminal.get('parent_pid')) is int and terminal['pid']==child['child_pid'] and terminal['parent_pid']==child['parent_pid'],'Actual SDK PID/parent identity')
        owner=self.read(self.folder/'owner.json')
        need(owner['run_id']==RUN_ID and owner['job_sha256']==JOB_SHA and type(owner['parent_pid']) is int and owner['parent_pid']==child['parent_pid'] and child['run_id']==RUN_ID and child['job_sha256']==JOB_SHA,'Owned actual parent/job/run')
        need(terminal.get('run_id')==RUN_ID and terminal.get('job_sha256')==JOB_SHA and terminal.get('purpose')=='v4_validation_video' and terminal.get('hardware_approved') is False and terminal.get('physical_calibration') is False and terminal.get('training')=='NOT_RUN' and type(terminal.get('code')) is int and terminal['code']==0,'Typed successful simulation-only terminal')
        need((terminal.get('status'),terminal.get('phase')) in (('COMPLETE_PRE_CLOSE','CLOSING_APP'),('CLOSED','APP_CLOSED')),'Supported exact completion representation')
        native=terminal.get('files_sha256');need(type(native) is dict and set(native)==set(seal)-EXCLUDED and 'report.json' in native,'Exact native seal equals recovery minus five parent/output records')
        for n,h in native.items():need(type(h) is str and len(h)==64 and seal[n]==h and sha(self.folder/n)==h,'Complete native sealed data')
        self.audit.update(raw_terminal_status=terminal['status'],raw_terminal_phase=terminal['phase'],native_members=len(native),SDK_pid=terminal['pid'],parent_pid=terminal['parent_pid'],parent_reaped_zero=True)
        return True
    def record_sdk(self,result):
        expected={'provider':'OBSERVED_AND_RECHECKED','numeric':'SDK_PINNED_BEFORE_AFTER','binding':'SAME_MODULES','cuda':'ACTUAL_GPU_SUM_6'}
        need(result==expected,'Actual original SDK numeric-before/after and provider/binding postchecks');self.audit['original_SDK_verify_records']=result
    def provenance(self,terminal):return 'SDK_PRE_CLOSE_SEAL_AND_PARENT_REAPED_0' if terminal['status']=='COMPLETE_PRE_CLOSE' else 'SDK_CLOSED_SEAL'
    def consume(self):
        self.guard();code=self.D.verify_native_result(self.run,self.record,self.folder)
        need(code==0 and 'original_SDK_verify_records' in self.audit,'Verified lifecycle and all native phase gates')
        result={'unit':131,'status':'PASS','source_runtime_unit':130,'run_id':RUN_ID,'job_sha256':JOB_SHA,'native_result':str(self.out/'native-result.json'),'lifecycle_proof':self.audit,'original130_failure_preserved':True,'additional_SDK':0,'SSH':0,'hardware_approved':False}
        self.write(self.out/'result.json',result);return result
    def media(self):
        raw=checked('src/simulation/mp18_isaac_130/media.py');m=load_raw('media130_offline131_'+str(id(self)),raw,ROOT/'src/simulation/mp18_isaac_130/media.py')
        body=function(raw,'encode').decode();need(body.count("record = D.read(OUT/'prepared.json')")==1 and body.count("run = OUT/'runs'/record['run_id']")==1,'Exact original media input wiring')
        body=body.replace("record = D.read(OUT/'prepared.json')","record = _original_record_131()").replace("run = OUT/'runs'/record['run_id']","run = _original_run_131()")
        need(body.count("OUT/'user-decision.json'")==3,'Exact cap-decision input occurrences');body=body.replace("OUT/'user-decision.json'","ORIGINAL_OUT/'user-decision.json'")
        body=body.replace('robot-arm-v4-130.mp4','robot-arm-v4-131.mp4').replace("'unit': 130","'unit': 131")
        m.D,m.C,m.OUT,m.ORIGINAL_OUT=self.D,self.D.C,self.out,OLD;m._original_record_131=lambda:dict(self.record);m._original_run_131=lambda:self.run
        invoke=m.invoke
        def guarded(argv,timeout=120):self.guard();return invoke(argv,timeout)
        m.invoke=guarded;exec(compile(body,str(HERE/'consumer.py')+'::<PINNED130_ENCODE_SPAN>','exec'),m.__dict__)
        self.audit['media_encode_original_span_sha256']=digest(function(raw,'encode'));self.audit['media_encode_derived_span_sha256']=digest(body.encode())
        return m
    def encode(self):self.guard();return self.media().encode()
def consume(out=OUT):return Context(out).consume()
def encode(out=OUT):return Context(out).encode()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('role',choices=('consume','encode'));a=p.parse_args();print(json.dumps({'consume':consume,'encode':encode}[a.role](),ensure_ascii=False))
