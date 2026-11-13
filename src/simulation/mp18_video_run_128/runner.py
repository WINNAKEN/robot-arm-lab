"""128 prepare/run/offline consume/encode owner. Import is SDK/network/Git free."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import threading
import time
import types
import zipfile
from collections import namedtuple

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'outputs/mp18-video-run-128'
DERIVED=ROOT/'src/simulation/mp18_isaac_128'
RELEASE_SHA='c123e62dd43d3e8d55bafcf685f506d987ab15f49a986ff978c898e445589eb6'
FACTS={
  "outputs/mp18-isaac-119/native-result.json": "1898aab076128712316497d72c886fee323f715b591accd0f6027bf2dca62f9c",
  "outputs/mp18-isaac-119/runs/f68441cd00534b88919cfd71f8f436a8/retrieved/process.json": "4e26c4005a16e3608f7fb699228199688f2613f53fc938abd0c04ff6055dec46",
  "outputs/mp18-stage-diagnosis-124/candidate/manifest.json": "ce52c132a270853f9ee29f06b1df851c65a80e3342656f67e50005c61ae17644",
  "outputs/mp18-stage-diagnosis-124/review/source-freeze.json": "9f24b6206a679e036db4e30504d289404df08bc3e625c1e759d40580532770bc",
  "outputs/mp18-stage-diagnosis-124/review/main-L4-final.json": "121d50752922d688c13da2696d550c93f128d1bf001ca379eb2d4de5730d2360",
  "src/simulation/mp18_video_run_125/release.py": "bfbef2914e44f7dc2d24b23ec477cdbdc9ad6b216e2ba1aa364862f7cc4974fa",
  "src/simulation/mp18_video_run_125/runner.py": "dbe098b33aa1dd280028211fab72e217d7672e36057365bd5416df074fc0f996",
  "src/simulation/mp18_video_run_125/test_runner.py": "7785d6574a06b2d6b8a95873649e919a988fc57f092e6a3086e66fc96937a1d2",
  "outputs/mp18-video-run-125/runtime-final.json": "10b743c00ef5cdd9dbf14ac044c7c14292938f1cbd92e0514ba8d0b75aa03a1c",
  "outputs/mp18-video-run-125/native-result.json": "c58efeea61812eedeecedd5ccf0ef16428ef0421e90f20285cdc73f72a77e4ea",
  "outputs/mp18-layer-lifetime-126/candidate/manifest.json": "7ff93a0f9a05ad6cfe8d13d3d675127bc7526846b886fa6804c11843bd85f49a",
  "outputs/mp18-layer-lifetime-126/review/source-freeze.json": "1ed21862a94341d2da27a4cde129b36a02c3a8e2429dfe62c9b27cb42b351234",
  "outputs/mp18-layer-lifetime-126/review/main-L4-final.json": "57ba8312a28ebb6fdb4e6bb0b1a47f89ad8295468c6386e573012ff22e21ebed",
  "outputs/mp18-layer-lifetime-126/review/main-L4-r1/publication-complete.json": "1019069c318441ea55a5063377ee29598a8c036eebefafbdf35ac67c2664059c",
  "outputs/mp18-layer-lifetime-126/result.json": "c539a79a7fbd183b757d64c1d46e28eb41f39f86fb0c34c09963c03a6f179dbd",
  "outputs/mp18-video-run-125/review/source-freeze.json": "35498e4b8e19d6b38ff3a94b1c6a9b2f22aa69c076f4ac100f256e83803099a9",
  "outputs/mp18-video-run-125/runs/f3bdb19d83ea4615af27ddb17150c6fc/retrieved/process.json": "fcc1c3cdddd173d97398050beea231b022934423c7e6cc0dd545b93e9a067e3a",
  "outputs/mp18-video-run-128/approval-evidence.json": "5810fff5660bbf0f4c6a3aca5af675591ce5de1747f6f883492124743816acc4",
  "outputs/mp18-video-run-128/task-scope.json": "3f516148ebc5bf021af4203c8852579e2449c2574ad4868993f7927d5b7fa15b",
  "src/simulation/mp18_video_run_127/release.py": "d7dcd75333db35d36a9d77e6b3256864ff92316c9b239a6cd13b6441b2457697",
  "src/simulation/mp18_video_run_127/runner.py": "122c61b21380a1b663958271ce6183754ab116b59ba4caea0d9e3356796163a1",
  "src/simulation/mp18_video_run_127/test_runner.py": "d4668b7247dda597fb7c0ca5c57ffab4590bb7eb298abb00ff28832ebdbd1eed",
  "src/simulation/mp18_isaac_127/native.py": "06a36b35713337d42fdb76f6f3ac161d56d6cb3cb7ce47f4d2fa683176c22e17",
  "outputs/mp18-video-run-127/review/source-freeze.json": "dd237b11646708495fae1f2f172846a934f8bd78cc73a8f1d55dbf5302a7d5c7",
  "outputs/mp18-video-run-127/review/main-L4-final.json": "c53f5e08361890ce594416d94998a72467fb170fb173ad14423df4aabd5c2c97",
  "outputs/mp18-video-run-127/runtime-final.json": "ab575828e35f05d734f1995ef8f9dccdeaadb105714359103e766015e8ad48f7",
  "outputs/mp18-video-run-127/native-result.json": "3260e173564e722b1e5cf470e7cc424ebd7d000038590a3c67d1c9ec4d1a2321",
  "outputs/mp18-video-run-127/post-native-analysis/author/analysis.json": "54f531c2340e221375d1da90a1f873d6483106784fdf0d1d1b0fa765421f6e50",
  "outputs/mp18-video-run-127/post-native-analysis/main/main-diagnosis.json": "18dde93eb1d570ebd6471ee1b908ff0d79f73486d10285cbfa46724cec76311b",
  "outputs/mp18-video-run-127/runs/28a26406faab4d8abe1b81efc4eb80c3/retrieved/process.json": "b8c7cc0a2eb7a52e8170dc3087a3c6b943738128a565e0af7d30e4e0e0a51df2",
  "outputs/mp18-video-run-128/preparation-evidence/source-scene-settings.json": "1799229a93272b0a60eff68104d8ce152d53cae514c9fce0b1db56672f8520e9",
  "outputs/mp18-layer-lifetime-126/candidate/native.py": "06a36b35713337d42fdb76f6f3ac161d56d6cb3cb7ce47f4d2fa683176c22e17",
  "outputs/mp18-video-run-128/preparation-evidence/solver-order-reference.json": "7fc18350d09395a790b0df5e649167eb37654fa30851de5f16fd57579b45eef2"
}

IDENTITY=('nonce','run_id','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')


def _load_release():
    p=HERE/'release.py';value=p.read_bytes()
    if hashlib.sha256(value).hexdigest()!=RELEASE_SHA:raise ValueError('Release helper pin before execution')
    module=types.ModuleType('release128_checked');module.__file__=str(p);sys.modules[module.__name__]=module
    exec(compile(value,str(p),'exec'),module.__dict__)
    return module


R=_load_release()
need,parse,encode,digest=R.need,R.parse,R.encode,R.digest
Grant=namedtuple('Grant','raw reply_raw source_sha prepared_sha start end nonce')
Snapshot=namedtuple('Snapshot','files inputs generated manifest_raw source_sha out prepared_raw bundle job_raw record_raw grant')


def _unique(rows):return tuple(sorted(dict(rows).items()))


def current(snapshot):
    R.verify_files(snapshot.files)
    if snapshot.grant is not None:
        need(R.read(snapshot.out/'user-budget-grant.json')==snapshot.grant.raw and
             R.read(snapshot.out/'user-budget-reply.json')==snapshot.grant.reply_raw,'Current actual128 grant/reply bytes')


def generated_bytes(snapshot,name):
    value=dict(snapshot.generated)[name];pin=parse(snapshot.manifest_raw)['files'][name]
    need(digest(value)==pin['sha256'] and len(value)==pin['bytes'],'Captured generated source pin')
    return value


def driver(snapshot):
    current(snapshot)
    data=generated_bytes(snapshot,'driver.py')
    D=R.load_raw('derived_driver128_'+str(id(snapshot)),data,DERIVED/'driver.py')
    D.OUT=snapshot.out
    bind_driver(D,snapshot,lambda:current(snapshot))
    return D


def bind_driver(D,snapshot,guard):
    inputs=dict(snapshot.inputs)
    def resolver(path):
        R.path_guard(path)
        value=inputs.get(str(path));need(type(value) is bytes,'Closed immutable payload input')
        return value
    D.bind_local_authority(guard,resolver)


def source_snapshot(out=OUT):
    source_sha,rows=R.review_capture(out)
    generated,manifest,release_rows=R.verify_release()
    rows.extend(release_rows)
    facts={}
    for rel,expected in FACTS.items():
        p=ROOT/rel;value=R.read(p);need(digest(value)==expected,'PriorSDK/candidate/latestapproval immutable evidence')
        rows.append((str(p),value));facts[rel]=value
    prior=parse(facts['outputs/mp18-isaac-119/native-result.json'])
    need(prior['unit']==119 and prior['run_id']=='f68441cd00534b88919cfd71f8f436a8' and prior['status']=='FAIL' and
         prior['SDK_reaped'] is True and prior['remote_attempts']==1,'Original first actual SDK failure retained')
    oldrun=parse(facts['outputs/mp18-video-run-125/runtime-final.json'])
    oldnative=parse(facts['outputs/mp18-video-run-125/native-result.json'])
    oldprocess=parse(facts['outputs/mp18-video-run-125/runs/f3bdb19d83ea4615af27ddb17150c6fc/retrieved/process.json'])
    oldid='f3bdb19d83ea4615af27ddb17150c6fc'
    need(oldrun['unit']==125 and oldrun['run_id']==oldid and oldrun['status']=='IMPORT_FAILED' and
         oldrun['actual_new_SDK']==1 and oldrun['actual_prior_SDK']==1 and oldrun['total_actual_SDK']==2 and
         oldrun['SDK_reaped'] is True and oldrun['frames']==0 and oldrun['completed_steps']==0 and
         oldrun['phases']=={'import':'FAIL','hold':'NOT_RUN','small':'NOT_RUN','large':'NOT_RUN'},'Original125 SDK2 history is consumed FAIL')
    need(oldnative['unit']==119 and oldnative['run_id']==oldid and oldnative['status']=='FAIL' and
         oldnative['SDK_reaped'] is True and oldnative['remote_attempts']==1 and
         {p['name']:p['status'] for p in oldnative['phases']}==oldrun['phases'] and
         oldprocess['run_id']==oldid and oldprocess['child_pid']==38180 and oldprocess['raw_complete'] is True and
         oldprocess['terminal'] is True and oldprocess['child_state']=='REAPED' and oldprocess['job_active_after']==0 and
         oldprocess['actual_child_exit_code']==1,'Actual125 SDK reaped failure, never upgraded')
    fraw=facts['outputs/mp18-layer-lifetime-126/review/source-freeze.json'];f126=parse(fraw)
    lraw=facts['outputs/mp18-layer-lifetime-126/review/main-L4-final.json'];l126=parse(lraw)
    praw=facts['outputs/mp18-layer-lifetime-126/review/main-L4-r1/publication-complete.json'];pub126=parse(praw)
    result126=parse(facts['outputs/mp18-layer-lifetime-126/result.json'])
    candidate126=parse(facts['outputs/mp18-layer-lifetime-126/candidate/manifest.json'])
    need(type(f126['unit']) is int and f126['unit']==126 and type(f126['files']) is list and len(f126['files'])==16 and
         f126['native_acceptance']=='NOT_RUN' and f126['SDK']==0 and f126['SSH']==0,'126 local-only source freeze')
    need(l126['unit']==126 and l126['phase']=='L4' and type(l126['round']) is int and l126['round'] in (1,2) and
         l126['non_author'] is True and l126['verdict']=='PASS' and l126['unmet']==0 and l126['unresolved_count']==0 and
         l126['source_freeze_sha256']==digest(fraw),'Current126 final local source authority')
    need(pub126['unit']==126 and pub126['phase']=='L4' and pub126['kind']=='FINAL_PUBLICATION_INTEGRITY' and
         pub126['verdict']=='PASS' and pub126['unmet']==0 and pub126['unresolved_count']==0 and pub126['hash_byte_mismatches']==0 and
         pub126['source_freeze_sha256']==digest(fraw) and pub126['report_sha256']==digest(lraw),'Current126 publication binds exact report/F')
    need(result126['unit']==126 and result126['status']=='SOURCE_LOCAL_CANDIDATE_PASS' and
         result126['actual_runtime_acceptance']=='NOT_RUN' and result126['source_freeze_sha256']==digest(fraw) and
         result126['mismatches']==0 and result126['new_SDK']==0 and result126['new_SSH']==0 and
         result126['L4']['sha256']==digest(lraw) and result126['L4']['publication_sha256']==digest(praw) and
         result126['original_125_failure_preserved'] is True and result126['original_125_SDK1_consumed'] is True,
         '126 code acceptance cannot become native or reopen125')
    need(candidate126['unit']==126 and candidate126['kind']=='LOCAL_UNDEPLOYED_NATIVE_CANDIDATE' and
         candidate126['approved_to_execute'] is False and candidate126['SDK_initializations']==0 and candidate126['SSH_launches']==0 and
         candidate126['native_sha256']==R.CANDIDATE_SHA==result126['native']['sha256']==digest(facts[R.CANDIDATE]) and
         candidate126['bytes']==result126['native']['bytes']==len(facts[R.CANDIDATE])==51296 and
         candidate126['outside_function_bytes_unchanged'] is True,'Exact126 candidate in fresh128 payload')
    need(len({p['path'].casefold() for p in f126['files']})==16,'Unique126 source pin inventory')
    for pin in f126['files']:
        p=ROOT/pin['path'];value=R.read(p)
        need(digest(value)==pin['sha256'] and len(value)==pin['bytes'],'Current126 original source pin')
        rows.append((str(p),value))
    need(manifest['native_derived_from127'] is True and manifest['native_base_sha256']==R.NATIVE_BASE_SHA and
         digest(generated['native.py'])==manifest['files']['native.py']['sha256'], 'Current generated128 native differs from historical126 base identity')
    runtime127=parse(facts['outputs/mp18-video-run-127/runtime-final.json'])
    native127=parse(facts['outputs/mp18-video-run-127/native-result.json'])
    process127=parse(facts['outputs/mp18-video-run-127/runs/28a26406faab4d8abe1b81efc4eb80c3/retrieved/process.json'])
    id127='28a26406faab4d8abe1b81efc4eb80c3'
    phases127={'import':'PASS','hold':'PASS','small':'FAIL','large':'NOT_RUN'}
    need(runtime127['unit']==127 and runtime127['run_id']==id127 and runtime127['actual_prior_v4_SDK']==2 and
         runtime127['actual_new_SDK']==1 and runtime127['SDK_pid']==52020 and runtime127['SDK_reaped'] is True and
         runtime127['frames']==120 and runtime127['completed_steps']==1429 and
         runtime127['initialization_fixed_verified'] is True and {p['name']:p['status'] for p in runtime127['phases']}==phases127,
         'Original127 third actualSDK smallFAIL preserved')
    need(native127['unit']==119 and native127['run_id']==id127 and native127['status']=='FAIL' and native127['SDK_reaped'] is True and
         {p['name']:p['status'] for p in native127['phases']}==phases127 and process127['run_id']==id127 and
         process127['child_pid']==52020 and process127['child_state']=='REAPED' and process127['raw_complete'] is True and
         process127['job_active_after']==0,'127 nativeFAIL is current reaped history, not successful large motion')
    taskraw=facts['outputs/mp18-video-run-128/task-scope.json'];task=parse(taskraw)
    taskkeys={'allowed_runtime_units','criteria_changes_allowed','fixed_remote_period_s_per_unit','hardware_approved','kind',
        'max_SDK_per_unit','max_sum_remote_periods_s','max_total_SDK','new_user_reply_fabricated','physical_CAN','physical_RS485',
        'request_sha256','retry_per_unit','task_id'}
    need(type(task) is dict and set(task)==taskkeys and task['kind']=='ROOT_BOUND_GOAL_ALLOCATION' and
         task['task_id']=='j6-fix-large-motion-20261107-128','Closed immutable goal allocation')
    need(type(task['allowed_runtime_units']) is list and all(type(x) is int for x in task['allowed_runtime_units']) and
         task['allowed_runtime_units']==[128,129] and 128 in task['allowed_runtime_units'],'Current128 is one of exactly128/129')
    for key,value in {'fixed_remote_period_s_per_unit':2700,'max_SDK_per_unit':1,'max_sum_remote_periods_s':5400,'max_total_SDK':2,'retry_per_unit':0}.items():
        need(type(task[key]) is int and task[key]==value,'Exact goal allocation quota/period')
    need(task['criteria_changes_allowed'] is False and task['hardware_approved'] is False and task['new_user_reply_fabricated'] is False and
         task['physical_CAN']=='NOT_RUN' and task['physical_RS485']=='NOT_RUN' and
         task['request_sha256']==digest(facts['outputs/mp18-video-run-128/approval-evidence.json']), 'Actual unchanged criteria/request hardwarefalse allocation')

    cfg=parse(generated['config.json']);inputs={str(DERIVED/n):b for n,b in generated.items()}
    for name,pin in cfg['model_pins'].items():
        p=ROOT/cfg['model_dir']/name;b=R.read(p)
        need(digest(b)==pin['sha256'] and len(b)==pin['bytes'],'Current original model bytes')
        rows.append((str(p),b));inputs[str(p)]=b
    for name,item in cfg['refs'].items():
        p=ROOT/item['path'];b=R.read(p);need(digest(b)==item['sha256'],'Current installed-reference input bytes')
        rows.append((str(p),b));inputs[str(p)]=b
    cap=R.read(ROOT/R.CAP);need(digest(cap)==R.CAP_SHA,'Original cap reply distinct from new budget')
    rows.append((str(ROOT/R.CAP),cap));inputs[str(out/'user-decision.json')]=cap
    if (out/'user-decision.json').exists():
        need(R.read(out/'user-decision.json')==cap,'Own cap byte copy changed')
        rows.append((str(out/'user-decision.json'),cap))
    return Snapshot(_unique(rows),tuple(sorted(inputs.items())),tuple(sorted(generated.items())),encode(manifest),source_sha,
                    Path(out),None,None,None,None,None)


def prepare(out=OUT):
    snapshot=source_snapshot(out);current(snapshot)
    cap=dict(snapshot.inputs)[str(out/'user-decision.json')]
    if not (out/'user-decision.json').exists():R.exclusive(out/'user-decision.json',cap,lambda:current(snapshot))
    snapshot=snapshot._replace(files=_unique([*snapshot.files,(str(out/'user-decision.json'),cap)]))
    D=driver(snapshot)
    record=D.prepare()
    complete=prepared_snapshot(snapshot,D)
    R.exclusive(out/'prepare-evidence.json',encode({'unit':128,'legacy_envelope_unit':119,'source_freeze_sha256':snapshot.source_sha,
        'prepared_sha256':digest(complete.prepared_raw),'run_id':record['run_id'],'nonce':record['nonce'],
        'bundle_sha256':record['bundle_sha256'],'bundle_bytes':record['bundle_bytes'],'native_sha256':digest(generated_bytes(snapshot,'native.py')),
        'contract_config_program_byte_identical':True,'SDK':0,'SSH':0,'hardware_approved':False}),lambda:current(complete))
    return record


def prepared_snapshot(snapshot,D=None):
    value=R.read(snapshot.out/'prepared.json');record=parse(value)
    need(type(record) is dict and set(record)==set(IDENTITY) and all(type(record[k]) is str and re.fullmatch('[0-9a-f]{32}',record[k]) for k in ('run_id','nonce')),
         'Closed new prepared identity')
    need(type(record['bundle_bytes']) is int and 0<record['bundle_bytes']<=128*1024**2 and
         all(type(record[k]) is str and re.fullmatch('[0-9a-f]{64}',record[k]) for k in ('driver_sha256','bundle_sha256','job_sha256')),'Prepared sizes/hashes')
    run=snapshot.out/'runs'/record['run_id'];R.path_guard(run)
    bundle=R.read(run/'bundle.zip');job=R.read(run/'job.json')
    need(len(bundle)==record['bundle_bytes'] and digest(bundle)==record['bundle_sha256'] and digest(job)==record['job_sha256'],'Captured current bundle/job raw')
    s=snapshot._replace(files=_unique([*snapshot.files,(str(snapshot.out/'prepared.json'),value),(str(run/'bundle.zip'),bundle),(str(run/'job.json'),job)]),
                        prepared_raw=value,bundle=bundle,job_raw=job,record_raw=encode(record))
    current(s)
    if D is None:D=driver(s)
    bind_driver(D,s,lambda:current(s))
    D.verified_payload(run,record)
    current(s)
    return s


def grant_records(out=OUT,active=True,now=time.monotonic):
    # Actual absence rejects before any mutable output, prepare, SSH or SDK.
    graw=R.read(out/'user-budget-grant.json');rraw=R.read(out/'user-budget-reply.json')
    need(len(graw)<=65536 and len(rraw)<=65536,'Bounded actual budget records')
    g,r=parse(graw),parse(rraw)
    common={'unit','kind','approved','duration_s','hardware_approved'}
    need(type(r) is dict and set(r)==common|{'reply_text','conversation_ref'},'Closed actual128 reply')
    need(type(g) is dict and set(g)==common|{'reply_sha256','source_freeze_sha256','prepared_sha256','started_monotonic','deadline_monotonic','grant_nonce'},'Closed actual128 grant')
    for item,kind in ((r,'ACTUAL_USER_REPLY'),(g,'REVIEWED_V4_VIDEO_RUN_GRANT')):
        need(type(item['unit']) is int and item['unit']==128 and item['kind']==kind and item['approved'] is True and
             type(item['duration_s']) is int and item['duration_s']==2700 and item['hardware_approved'] is False,'Actual new128 simulation budget only')
    need(all(type(r[k]) is str and 0<len(r[k].strip())<=16384 for k in ('reply_text','conversation_ref')),'Retained latest actual reply')
    evidence=R.read(ROOT/'outputs/mp18-video-run-128/approval-evidence.json');e=parse(evidence)
    need(digest(evidence)==FACTS['outputs/mp18-video-run-128/approval-evidence.json'] and r['reply_text']==e['reply_text'],'Latest user approval, never old123/cap reply')
    for key in ('reply_sha256','source_freeze_sha256','prepared_sha256'):
        need(type(g[key]) is str and re.fullmatch('[0-9a-f]{64}',g[key]),'Closed grant SHA')
    need(g['reply_sha256']==digest(rraw) and type(g['grant_nonce']) is str and re.fullmatch('[0-9a-f]{32}',g['grant_nonce']),'Same captured actual reply/nonce')
    start,end=g['started_monotonic'],g['deadline_monotonic']
    need(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (start,end)) and end==start+2700,'Root fixed2700, no rearming')
    if active:need(start<=now()<end,'Actual Root period active')
    return Grant(graw,rraw,g['source_freeze_sha256'],g['prepared_sha256'],start,end,g['grant_nonce'])


def run_snapshot(out=OUT,active=True,now=time.monotonic):
    grant=grant_records(out,active,now)
    s=prepared_snapshot(source_snapshot(out))
    need(grant.source_sha==s.source_sha and grant.prepared_sha==digest(s.prepared_raw),'Actual grant binds final F and new prepared bytes')
    s=s._replace(files=_unique([*s.files,(str(out/'user-budget-grant.json'),grant.raw),(str(out/'user-budget-reply.json'),grant.reply_raw)]),grant=grant)
    current(s)
    return s


def write_all(stream,data,end,now=time.monotonic):
    view=memoryview(data);offset=0
    while offset<len(view):
        need(now()<end,'Same fixed transport end')
        n=stream.write(view[offset:]);need(type(n) is int and 0<n<=len(view)-offset,'Partial write progress')
        offset+=n


def _metadata(snapshot,dispatch):
    g=snapshot.grant
    return {'unit':128,'legacy_envelope_unit':119,'source_freeze_sha256':snapshot.source_sha,
        'prepared_sha256':digest(snapshot.prepared_raw),'grant_sha256':digest(g.raw),'reply_sha256':digest(g.reply_raw),
        'grant_nonce':g.nonce,'period_start':g.start,'period_end':g.end,'dispatch_monotonic':dispatch,
        'record':parse(snapshot.record_raw),'files':{p:{'sha256':digest(b),'bytes':len(b)} for p,b in snapshot.files},
        'actual_prior_SDK':3,'new_SDK_max':1,'retry':0,'hardware_approved':False,
        'task_scope_sha256':digest(dict(snapshot.files)[str(ROOT/'outputs/mp18-video-run-128/task-scope.json')]),
        'goal_allocation':parse(dict(snapshot.files)[str(ROOT/'outputs/mp18-video-run-128/task-scope.json')])}


def _seal(snapshot_raw,metadata):
    return encode({'unit':128,'snapshot_sha256':digest(snapshot_raw),'grant_sha256':metadata['grant_sha256'],
        'prepared_sha256':metadata['prepared_sha256'],'source_freeze_sha256':metadata['source_freeze_sha256'],
        'period_start':metadata['period_start'],'period_end':metadata['period_end'],'dispatch_monotonic':metadata['dispatch_monotonic']})


class Owner:
    def __init__(self,snapshot,snapshot_raw,seal_raw,dispatch):
        self.snapshot,self.snapshot_raw,self.seal_raw,self.dispatch=snapshot,snapshot_raw,seal_raw,dispatch
        self.lock,self.sent=threading.Lock(),False
        self.go_raw=None
        self.recovered_rows=()
    def current(self,active=False,now=time.monotonic):
        s=self.snapshot;current(s)
        if self.recovered_rows:R.verify_files(self.recovered_rows)
        need(R.read(s.out/'consumed-snapshot.json')==self.snapshot_raw and R.read(s.out/'admission.json')==self.seal_raw,'Expected in-memory snapshot/seal bytes')
        if self.go_raw is not None:need(R.read(s.out/'GO.json')==self.go_raw,'Own GO original bytes')
        if active:need(s.grant.start<=now()<s.grant.end,'Same active Root period')
    def sender(self,stream,ready,work_end,now=time.monotonic):
        with self.lock:
            s=self.snapshot;g=s.grant
            need(not self.sent and now()<min(self.dispatch+20,g.end,work_end),'First timely GO only')
            expected={k:parse(s.record_raw)[k] for k in IDENTITY}
            need(type(ready) is dict and set(ready)==set(expected)|{'kind','remote_ready'} and ready['kind']=='READY' and
                 {k:ready[k] for k in expected}==expected and type(ready['remote_ready']) in (int,float) and math.isfinite(ready['remote_ready']),'Original closed READY')
            self.current(True,now)
            go=encode({'unit':128,'grant_nonce':g.nonce,'grant_sha256':digest(g.raw),'prepared_sha256':digest(s.prepared_raw),
                'period_start':g.start,'period_end':g.end,'dispatch_monotonic':self.dispatch,'sent_monotonic':now(),
                'run_id':expected['run_id'],'nonce':expected['nonce'],'GO_count':1,'new_SDK_max':1,'retry':0})
            R.exclusive(s.out/'GO.json',go,lambda:self.current(True,now));self.go_raw=go
            # Required post-exclusive current revalidation before any wire GO.
            self.current(True,now)
            need(now()<min(self.dispatch+20,g.end,work_end),'Current GO fence after proof')
            self.sent=True
            write_all(stream,encode(dict(expected,kind='GO'))+b'\n',min(self.dispatch+20,work_end,g.end),now);stream.flush()
            for i in range(0,len(s.bundle),1024*1024):write_all(stream,s.bundle[i:i+1024*1024],min(work_end,g.end),now)
            stream.flush()


def admit(snapshot,now=time.monotonic):
    s=snapshot;g=s.grant;need(g is not None and g.start<=now()<g.end and g.end-now()>2402,'Actual Root active2402 headroom before RPC')
    current(s);record=parse(s.record_raw);run=s.out/'runs'/record['run_id']
    for p in (s.out/'admission.json',s.out/'consumed-snapshot.json',s.out/'attempt.json',s.out/'GO.json',s.out/'transport',s.out/'run-result.json',
              run/'retrieved',run/'retrieved.zip',s.out/'native-result.json'):
        R.path_guard(p);need(not p.exists(),'Duplicate new128 admission/GO/result')
    dispatch=now();metadata=_metadata(s,dispatch);snap=encode(metadata);seal=_seal(snap,metadata)
    R.exclusive(s.out/'admission.json',seal,lambda:current(s));R.exclusive(s.out/'consumed-snapshot.json',snap,lambda:current(s))
    owner=Owner(s,snap,seal,dispatch)
    owner.current(True,now);R.path_guard(s.out/'transport').mkdir(exist_ok=False)
    return owner


def offline_owner(out=OUT):
    # Period expiration is not rearmed and does not prevent source-bound offline verification/encoding.
    s=run_snapshot(out,active=False)
    snap=R.read(out/'consumed-snapshot.json');meta=parse(snap)
    expected=_metadata(s,meta['dispatch_monotonic'])
    need(meta==expected,'Offline consumed identity matches actual canonical grant/prepared/F')
    seal=_seal(snap,meta);need(R.read(out/'admission.json')==seal,'Offline expected admission seal')
    owner=Owner(s,snap,seal,meta['dispatch_monotonic'])
    need((out/'GO.json').exists(),'Offline native result requires original GO attempt')
    go_raw=R.read(out/'GO.json');go=parse(go_raw);record=parse(s.record_raw)
    need(go.get('unit')==128 and go.get('grant_nonce')==s.grant.nonce and go.get('grant_sha256')==digest(s.grant.raw) and
         go.get('prepared_sha256')==digest(s.prepared_raw) and go.get('run_id')==record['run_id'] and go.get('nonce')==record['nonce'] and
         go.get('period_start')==s.grant.start and go.get('period_end')==s.grant.end and go.get('dispatch_monotonic')==meta['dispatch_monotonic'] and
         go.get('GO_count')==1 and go.get('new_SDK_max')==1 and go.get('retry')==0 and
         type(go.get('sent_monotonic')) in (int,float) and math.isfinite(go['sent_monotonic']) and
         s.grant.start<=go['sent_monotonic']<min(s.grant.end,meta['dispatch_monotonic']+20),'Offline original GO identity')
    owner.go_raw=go_raw
    owner.current(False)
    if (out/'result-receipt.json').exists():
        owner.recovered_rows=capture_recovered(owner)
        owner.current(False)
    return owner


def capture_recovered(owner):
    # Preserve exact recovered members before any subsequent offline consumer/encoder write.
    s=owner.snapshot;record=parse(s.record_raw);run=s.out/'runs'/record['run_id']
    receipt_raw=R.read(s.out/'result-receipt.json');receipt=parse(receipt_raw);archive=R.read(run/'retrieved.zip')
    need(type(receipt) is dict and set(receipt)=={'unit','run_id','nonce','archive_sha256','archive_bytes','native_consumer_exit'} and
         receipt['unit']==128 and receipt['run_id']==record['run_id'] and receipt['nonce']==record['nonce'] and
         receipt['archive_bytes']==len(archive) and receipt['archive_sha256']==digest(archive),'Current recovered archive receipt')
    rows=[(str(s.out/'result-receipt.json'),receipt_raw),(str(run/'retrieved.zip'),archive)]
    D=driver(s)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist();need(infos and len(infos)==len({i.filename.casefold() for i in infos}) and
            sum(i.file_size for i in infos)<2*1024**3,'Current recovered unique bounded members')
        for item in infos:
            D._safe_name(item.filename)
            need(not item.is_dir() and item.flag_bits&1==0 and (item.external_attr>>16)&0o170000!=0o120000,'Current recovered member role')
            p=run/'retrieved'/item.filename;value=R.read(p)
            need(value==z.read(item),'Current exact recovered member bytes')
            rows.append((str(p),value))
    return tuple(rows)


def result_path(owner,path):
    owner.current(False);s=owner.snapshot;record=parse(s.record_raw);run=s.out/'runs'/record['run_id'];p=Path(path)
    need(p==s.out/'native-result.json' or p==run or p.is_relative_to(run),'Closed new128 result role')
    R.path_guard(run);R.path_guard(p);need(run.resolve()==run and p.resolve().is_relative_to(ROOT),'Original result anchor unchanged')
    return p


def consume_archive(owner,wire,D=None):
    s=owner.snapshot;record=parse(s.record_raw);run=s.out/'runs'/record['run_id']
    current(s)
    ready_raw,header_raw,archive=wire.split(b'\n',2);ready=parse(ready_raw);header=parse(header_raw)
    expected={k:record[k] for k in IDENTITY}
    need(type(ready) is dict and set(ready)==set(expected)|{'kind','remote_ready'} and ready['kind']=='READY' and
         {k:ready[k] for k in expected}==expected and type(ready['remote_ready']) in (int,float) and math.isfinite(ready['remote_ready']),'Recovered READY identity')
    need(type(header) is dict and set(header)=={'kind','run_id','nonce','bytes','sha256'} and header['kind']=='RESULT' and
         header['run_id']==record['run_id'] and header['nonce']==record['nonce'] and type(header['bytes']) is int and
         0<header['bytes']<=2*1024**3 and len(archive)==header['bytes'] and digest(archive)==header['sha256'],'Closed RESULT bytes/hash/nonce')
    if D is None:D=driver(s)
    bind_driver(D,s,lambda:owner.current(False))
    D.verified_payload(run,record)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist();need(bool(infos) and len(infos)==len({i.filename.casefold() for i in infos}) and sum(i.file_size for i in infos)<2*1024**3,'Unique bounded result ZIP')
        for i in infos:
            D._safe_name(i.filename);need(not i.is_dir() and i.flag_bits&1==0 and (i.external_attr>>16)&0o170000!=0o120000,'No result links/encrypted entries')
        need({'process.json','recovery-seal.json'}<={i.filename for i in infos},'Original result records')
        destination,archive_path=run/'retrieved',run/'retrieved.zip';paths=[destination/i.filename for i in infos]
        for p in (destination,archive_path,s.out/'native-result.json',*paths):result_path(owner,p)
        need(not destination.exists() and not archive_path.exists() and not (s.out/'native-result.json').exists(),'First recovery only')
        need(z.testzip() is None,'Complete archive CRC')
        result_path(owner,destination).mkdir(exist_ok=False)
        R.exclusive(result_path(owner,archive_path),archive,lambda:owner.current(False))
        for i,p in zip(infos,paths):
            data=z.read(i);result_path(owner,p).parent.mkdir(parents=True,exist_ok=True)
            R.exclusive(result_path(owner,p),data,lambda:owner.current(False))
    result_path(owner,s.out/'native-result.json')
    code=D.verify_native_result(run,record,destination)
    R.exclusive(s.out/'result-receipt.json',encode({'unit':128,'run_id':record['run_id'],'nonce':record['nonce'],
        'archive_sha256':digest(archive),'archive_bytes':len(archive),'native_consumer_exit':code}),lambda:owner.current(False))
    return code


def consume(out=OUT):
    owner=offline_owner(out);s=owner.snapshot;record=parse(s.record_raw);run=out/'runs'/record['run_id']
    if not (run/'retrieved').exists():return consume_archive(owner,R.read(out/'transport/stdout.txt'))
    receipt=parse(R.read(out/'result-receipt.json'));archive=R.read(run/'retrieved.zip')
    need(receipt['run_id']==record['run_id'] and receipt['nonce']==record['nonce'] and receipt['archive_sha256']==digest(archive),'Original recovered archive identity')
    D=driver(s);bind_driver(D,s,lambda:owner.current(False));result_path(owner,out/'native-result.json')
    return D.verify_native_result(run,record,run/'retrieved')


def guarded_media_invoke(owner, invoke):
    def checked(argv, timeout=120):
        owner.current(False)
        return invoke(argv, timeout=timeout)
    return checked


def encode_video(out=OUT):
    owner=offline_owner(out);s=owner.snapshot;current(s)
    data=generated_bytes(s,'media.py');media=R.load_raw('media128_checked_'+str(id(s)),data,DERIVED/'media.py')
    media.D.OUT=out;media.OUT=out
    bind_driver(media.D,s,lambda:owner.current(False))
    media.invoke=guarded_media_invoke(owner,media.invoke)
    return media.encode()


def load_proxy():
    value=R.read(ROOT/R.PROXY);need(digest(value)==R.PROXY_SHA,'Accepted123 raw stdin proxy pin')
    return R.load_raw('proxy123_for128',value,ROOT/R.PROXY)


def run(out=OUT):
    s=run_snapshot(out,active=True);D=driver(s)
    cfg=parse(generated_bytes(s,'config.json'));item=cfg['refs']['winjob.py'];helper_raw=R.read(ROOT/item['path'])
    need(digest(helper_raw)==item['sha256'],'Original WinJob helper')
    helper=D.load_module('winjob128_local',helper_raw,ROOT/item['path']);proxy=load_proxy()
    owner=admit(s);g=s.grant;record=parse(s.record_raw)
    bind_driver(D,s,lambda:owner.current(False))
    remaining=g.end-time.monotonic();args=dict(record,remote_root=cfg['remote_root'],remaining=remaining)
    literal=R.thin_bootstrap(generated_bytes(s,'driver.py'),generated_bytes(s,'contract.py'),args)
    command=proxy.proxy_command(str(Path(cfg['sdk']['isaac_root'])/'kit/python/python.exe'),literal,remaining)
    import os
    ssh=Path(os.environ['SystemRoot'])/'System32/OpenSSH/ssh.exe'
    argv=[str(ssh),'-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ConnectTimeout=10',cfg['ssh_alias'],command]
    R.exclusive(out/'attempt.json',encode({'unit':128,'dispatch_monotonic':owner.dispatch,'period_start':g.start,'period_end':g.end,
        'grant_sha256':digest(g.raw),'run_id':record['run_id'],'actual_prior_SDK':3,'new_SDK_max':1,'retry':0,
        'pipeline_SSH_launch_attempts':1}),lambda:owner.current(True))
    def sender(stream,stdout_path,work_end):
        ready=None
        while time.monotonic()<min(owner.dispatch+20,work_end):
            b=stdout_path.read_bytes()
            if b'\n' in b:ready=parse(b.split(b'\n',1)[0]);break
            time.sleep(.01)
        owner.sender(stream,ready,work_end)
    process=None
    try:
        process=helper.run(argv,out/'transport',g.end-time.monotonic()-2,cleanup_s=2,input_sender=sender)
        R.exclusive(out/'transport.json',encode(process),lambda:owner.current(False))
        need(process['raw_complete'] and process['terminal'] and process['child_state']=='REAPED' and process['job_active_after']==0 and
             process['actual_child_exit_code']==0 and not process['timed_out'],'Actual proxy lifetime complete/reaped')
        code=consume_archive(owner,R.read(out/'transport/stdout.txt'),D)
    except BaseException as exc:
        R.exclusive(out/'run-result.json',encode({'unit':128,'status':'FAIL','phase':'TRANSPORT_OR_RESULT','error':type(exc).__name__+': '+str(exc),
            'actual_prior_SDK':3,'new_SDK_initializations':'UNKNOWN' if (out/'GO.json').exists() else 0,'new_SDK_max':1,'retry':0,
            'pipeline_SSH_launch_attempts':1,'process':process,'run_id':record['run_id'],'period_end':g.end,'hardware_approved':False}),lambda:owner.current(False))
        raise
    R.exclusive(out/'run-result.json',encode({'unit':128,'status':'PASS' if code==0 else 'FAIL','native_consumer_exit':code,
        'actual_prior_SDK':3,'new_SDK_max':1,'retry':0,'pipeline_SSH_launch_attempts':1,'run_id':record['run_id'],
        'period_start':g.start,'period_end':g.end,'finished_monotonic':time.monotonic(),'hardware_approved':False}),lambda:owner.current(False))
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('prepare','run','consume','encode'))
    role=parser.parse_args().role
    value={'prepare':prepare,'run':run,'consume':consume,'encode':encode_video}[role]()
    print(json.dumps(value,ensure_ascii=False));raise SystemExit(value if type(value) is int else 0)
