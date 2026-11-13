"""123 raw SSH stdin continuation. No network, SDK, approval or mutable work at import."""
from __future__ import annotations
import argparse
import base64
from collections import namedtuple
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import threading
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'outputs/mp18-ssh-raw-stdin-123'
ORIGIN=ROOT/'outputs/mp18-budget-run-121'
OLD=ROOT/'outputs/mp18-isaac-119'
PERIOD_START=386563.421
PERIOD_END=389263.421
PLAN_SHA='3ea8210b63c0a7b6b0dcb3449c7c60eab26d6a1fcd6c36d1707eeb6a7d4d9ced'
FREEZE121='b02516a44efe076d3d10fc82ee609e156b8ad5c987668357429533cd889bdf54'
FREEZE120='6ad6e771ed782d77c3fc39693846e44c562b217cb40dbcd9fb215c67a00f4c89'
IDENTITY=('nonce','run_id','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')
FACTS={
  "outputs/mp18-budget-run-121/user-budget-grant.json": "7697f63af9a42f16d66276208ac7d2e84ceeac2ba4c8542a938877b9e7e96ebb",
  "outputs/mp18-budget-run-121/user-budget-reply.json": "3da2514be2a4b117fcb10c66532f3263e207360a80adfff2833eca457444e8f3",
  "outputs/mp18-budget-run-121/admission.json": "184d6b94716c1932c5940269461646312d7d2cb09cad5933cff5892614f13599",
  "outputs/mp18-budget-run-121/consumed-snapshot.json": "e5da0a26df781acbe93a990154181defb2d457697005785f37e9b88404796ac9",
  "outputs/mp18-budget-run-121/GO.json": "d9131271604c73f25f590878612678c85abb209160357249e2d63ba4d6d5bd07",
  "outputs/mp18-budget-run-121/transport.json": "b3f36a805eb1864b72a6ac94ac34a682559cbfb76b56306c8ca87371e84720d1",
  "outputs/mp18-budget-run-121/transport/stdout.txt": "7d229a032b3a6c92ef89626032867ec680b75d24437a44712fa969066784344b",
  "outputs/mp18-budget-run-121/transport/stderr.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "outputs/mp18-budget-run-121/runtime-outcome.json": "adc664df2cc6c7c81e2a9b0dd0bbd4558082453d38bab932c7a8603d76a60d8d",
  "outputs/mp18-budget-run-121/cap-adjustment-authority.json": "2245813e7cb1dea3d1acd348602b257bb92a50c09624e491c86221ab1d405ee7",
  "outputs/mp18-ingress-diagnosis-122/readonly-observation.json": "d52a1789e8210031fa3942bfc80cbe38757710f8916d25decc34a55cf8c46738",
  "outputs/mp18-ingress-diagnosis-122/readonly-stdout.raw": "10e1e453c833c2fc04c039e2eac57dcd872dcf464656080fc2376149c38b2ab7",
  "outputs/mp18-ingress-diagnosis-122/remote-pipe-01/observation.json": "b9355a4c2a73393ae4f0cedad8287c907214b20df9316bcedf627a3970063350",
  "outputs/mp18-ingress-diagnosis-122/remote-pipe-01/stdout.txt": "6d7e4a255c3e3fb5e1b6c30cb41a71a691955d05d7fe72efdefa746e17326503",
  "outputs/mp18-ingress-diagnosis-122/remote-pipe-01/stderr.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "outputs/mp18-ingress-diagnosis-122/remote-pipe-02-rawhandle/observation.json": "f13eb545e0a9978a2119c6731edf2863a85fcc125018f978842d3feb3032fbc9",
  "outputs/mp18-ingress-diagnosis-122/remote-pipe-02-rawhandle/stdout.txt": "10990247ddac749297cade842e1928954c131665a66e24469f2f48adc8e17a0a",
  "outputs/mp18-ingress-diagnosis-122/remote-pipe-02-rawhandle/stderr.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "outputs/mp18-ingress-diagnosis-122/readonly-request.json": "9c30a8e006591f18140164ed5474705fd49b936c24a40240e46b90c973513a34",
  "outputs/mp18-ingress-diagnosis-122/readonly_query.py": "609aabaf09626afd7b0b7b2baf97327c4ba8a3baf08eef4d26299f7a440a3fd7"
}
Authority=namedtuple('Authority','record_raw cfg_raw bundle files grant_raw reply_raw end counts_raw')
Consumed=namedtuple('Consumed','authority dispatch end snapshot_raw seal_raw')


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    def bad(v):raise ValueError('Nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def encode(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def checked_path(path):
    path=Path(path)
    need(path.is_absolute() and path.is_relative_to(ROOT),'Original ROOT namespace')
    for p in (path,*path.parents):need(not p.is_symlink() and not p.is_junction(),'Reparse role')
    need(ROOT.resolve()==ROOT and path.resolve().is_relative_to(ROOT),'Original ROOT resolution')
    return path


def raw(path):return checked_path(path).read_bytes()


def exclusive(path,data,out=OUT):
    path=checked_path(path);need(path.is_relative_to(out),'Only123 output')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())


def _load(name,path,data):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    exec(compile(data,str(path),'exec'),module.__dict__)
    return module


def load_transport():
    fraw=raw(ROOT/'outputs/mp18-shell-entry-120/review/source-freeze.json')
    need(sha(fraw)==FREEZE120,'Accepted120 freeze')
    p=ROOT/'src/simulation/mp18_shell_entry_120/driver.py';data=raw(p)
    need(sha(data)==parse(fraw)['files'][p.relative_to(ROOT).as_posix()]['sha256'],'Pre-import120 pin')
    return _load('transport120_for123',p,data)


def load_helpers():
    fraw=raw(ORIGIN/'review/source-freeze.json');need(sha(fraw)==FREEZE121,'Accepted121 final freeze')
    p=ROOT/'src/simulation/mp18_budget_run_121/driver.py';data=raw(p)
    need(sha(data)==parse(fraw)['files'][p.relative_to(ROOT).as_posix()]['sha256'],'Pre-import121 pin')
    M=_load('results121_for123',p,data)
    T,D=M.load_library()
    return M,T,D


INPUT_ADAPTER=r'''  Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RawStdin123 {
 [DllImport("kernel32.dll", SetLastError=true)]
 public static extern IntPtr GetStdHandle(int id);
}
'@
  $rawHandle123=[RawStdin123]::GetStdHandle(-10)
  if($rawHandle123 -eq [IntPtr]::Zero -or $rawHandle123 -eq [IntPtr](-1)) { throw 'Invalid inherited stdin handle' }
  $safeInput123=[Microsoft.Win32.SafeHandles.SafeFileHandle]::new($rawHandle123,$false)
  $rawInput123=[IO.FileStream]::new($safeInput123,[IO.FileAccess]::Read,1,$false)
  $childHandle123=$p.StandardInput.BaseStream.SafeFileHandle.DangerousGetHandle()
  $safeChild123=[Microsoft.Win32.SafeHandles.SafeFileHandle]::new($childHandle123,$false)
  $rawChild123=[IO.FileStream]::new($safeChild123,[IO.FileAccess]::Write,1,$false)
  $ti=$rawInput123.CopyToAsync($rawChild123)'''
INPUT_DISPOSE=r'''if($null -ne $rawChild123) { $rawChild123.Dispose() }
  if($null -ne $rawInput123) { $rawInput123.Dispose() }
  if($null -ne $safeChild123) { $safeChild123.Dispose() }
  if($null -ne $safeInput123) { $safeInput123.Dispose() }
  $p.Dispose()'''


def proxy_script(executable,code,remaining):
    # Read the accepted proxy as an immutable library result; never replace source or monkeypatch a module.
    command=load_transport().proxy_command(executable,code,remaining)
    old=base64.b64decode(command.split("FromBase64String('",1)[1].split("'",1)[0]).decode('utf-16le')
    needle='  $ti=[Console]::OpenStandardInput().CopyToAsync($p.StandardInput.BaseStream)'
    need(old.count(needle)==1 and old.count('} finally { $p.Dispose() }')==1,'Exact accepted input adapter boundary')
    new=old.replace(needle,INPUT_ADAPTER)
    eof='[void]$ti.GetAwaiter().GetResult(); $p.StandardInput.Close(); $closed=$true'
    need(new.count(eof)==1,'Exact accepted EOF boundary')
    new=new.replace(eof,'[void]$ti.GetAwaiter().GetResult(); $rawChild123.Flush(); $p.StandardInput.Close(); $closed=$true')
    new=new.replace('} finally { $p.Dispose() }','} finally { '+INPUT_DISPOSE+' }')
    return old,new


def proxy_command(executable,code,remaining):
    _,script=proxy_script(executable,code,remaining)
    value=base64.b64encode(script.encode('utf-16le')).decode()
    command="& ([ScriptBlock]::Create([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"+value+"'))))"
    need(len(command)<30000,'Bounded original PowerShell invocation')
    return command


def source_gate(M,D,out=OUT):
    path=out/'review/source-freeze.json';fraw=raw(path);f=parse(fraw)
    required={'src/simulation/mp18_ssh_raw_stdin_123/driver.py','src/simulation/mp18_ssh_raw_stdin_123/test_driver.py','docs/design/123-ssh-raw-stdin-continuation.md'}
    need(type(f['files']) is dict and required<=set(f['files']),'Complete123 source freeze')
    files=[(str(path),fraw)]
    for rel,pin in f['files'].items():
        p=D.C.path_in(ROOT,rel);b=raw(p)
        need(sha(b)==pin['sha256'] and len(b)==pin['bytes'],'Current123 frozen source')
        files.append((str(p),b))
    need(sha(raw(ROOT/'docs/design/123-ssh-raw-stdin-continuation.md'))==PLAN_SHA,'Final123 plan')
    for who in ('main','lens'):
        p=out/('review/'+who+'-L4-final.json');b=raw(p);r=parse(b)
        need(type(r['unit']) is int and r['unit']==123 and r['phase']=='L4' and type(r['round']) is int and r['round'] in (1,2) and
             r['non_author'] is True and r['verdict']=='PASS' and type(r['unmet']) is int and r['unmet']==0 and
             type(r['unresolved_count']) is int and r['unresolved_count']==0 and r['source_freeze_sha256']==sha(fraw),'Independent final123 source authority')
        files.append((str(p),b))
    return files,sha(fraw)


def target_probe(files,source_freeze,out=OUT):
    p=out/'target-probe.json';b=raw(p);r=parse(b);process=r['process']
    need(type(r['unit']) is int and r['unit']==123 and r['kind']=='ACTUAL_NO_SDK_TARGET_PROBE' and r['source_driver_sha256']==sha(raw(HERE/'driver.py')) and
         r['source_freeze_sha256']==source_freeze and r['small_GO_before_bulk'] is True and r['eof'] is True and
         r['all256duplex'] is True and type(r['SDK_initializations']) is int and r['SDK_initializations']==0 and type(r['SSH_readonly_launches']) is int and r['SSH_readonly_launches']==1,'Actual reviewed adapter target probe')
    need(process['raw_complete'] is True and process['terminal'] is True and process['child_state']=='REAPED' and
         type(process['actual_child_exit_code']) is int and process['actual_child_exit_code']==0 and type(process['job_active_after']) is int and process['job_active_after']==0,'Actual target probe closed lifetime')
    probe_raw={}
    for name in ('stdout','stderr'):
        pp=out/('target-probe/'+name+'.txt');data=raw(pp)
        need(sha(data)==r[name+'_sha256'],'Actual target probe raw bytes')
        files.append((str(pp),data));probe_raw[name]=data
    first,ack,bulk,payload=probe_raw['stdout'].split(b'\n',3)
    expected=bytes(range(256))*4096
    need(first==b'READ_ONLY_READY\r' and parse(ack)=={'kind':'ACK','line_hex':'474f0a'} and
         parse(bulk)=={'kind':'BULK','bytes':1048576,'sha256':sha(expected),'eof':True} and
         payload==expected and probe_raw['stderr']==expected[::-1], 'Actual all256 target wire/EOF/bidirectional bytes')
    ep=out/'target-probe/sender-events.json';eb=raw(ep);events=parse(eb)
    need(sha(eb)==r['sender_events_sha256'] and type(events) is list and len(events)==4, 'Actual target event rawSHA')
    need([x['event'] for x in events]==['GO_WRITTEN','ACK_OBSERVED','BULK_START','BULK_DONE'] and
         all(type(x) is dict and set(x)=={'event','time'} and type(x['time']) is float and math.isfinite(x['time']) for x in events), 'Closed actual sender event rows')
    times=[x['time'] for x in events]
    need(times[0]<=times[1]<times[2]<=times[3], 'Actual ACK observed before bulk input')
    files.append((str(ep),eb));files.append((str(p),b))
    return r['SSH_readonly_launches']


def fresh_presence(out=OUT):
    present=[checked_path(out/name).exists() for name in ('user-budget-grant.json','user-budget-reply.json')]
    need(present[0]==present[1],'Both fresh canonical grant/reply required; never old fallback')
    return present[0]


def select_period(source_freeze_sha,probe_sha,out=OUT,now=time.monotonic):
    if not fresh_presence(out):
        return {'mode':'old','start':PERIOD_START,'end':PERIOD_END,'grant_sha256':None,'reply_sha256':None},[]
    gp,rp=out/'user-budget-grant.json',out/'user-budget-reply.json'
    gb,rb=raw(gp),raw(rp);need(len(gb)<=65536 and len(rb)<=65536,'Bounded actual fresh records')
    g,r=parse(gb),parse(rb)
    common={'unit','kind','approved','duration_s','hardware_approved'}
    need(type(r) is dict and set(r)==common|{'reply_text','conversation_ref'},'Closed fresh actual reply')
    need(type(g) is dict and set(g)==common|{'reply_sha256','source_freeze_sha256','target_probe_sha256','original_121_grant_sha256',
        'original_121_transport_sha256','grant_nonce','started_monotonic','deadline_monotonic'},'Closed fresh explicit grant')
    for value,kind in ((r,'ACTUAL_USER_REPLY'),(g,'EXPLICIT_ADDITIONAL_SIMULATION_BUDGET')):
        need(type(value['unit']) is int and value['unit']==123 and value['kind']==kind and value['approved'] is True and
             type(value['duration_s']) is int and value['duration_s']==2700 and value['hardware_approved'] is False,'Actual explicit fresh simulation-only permission')
    need(all(type(r[k]) is str and 0<len(r[k].strip())<=16384 for k in ('reply_text','conversation_ref')),'Retained actual fresh reply')
    import re
    for key in ('reply_sha256','source_freeze_sha256','target_probe_sha256','original_121_grant_sha256','original_121_transport_sha256'):
        need(type(g[key]) is str and re.fullmatch('[0-9a-f]{64}',g[key]),'Closed fresh SHA')
    need(g['reply_sha256']==sha(rb) and g['source_freeze_sha256']==source_freeze_sha and g['target_probe_sha256']==probe_sha and
         g['original_121_grant_sha256']==FACTS['outputs/mp18-budget-run-121/user-budget-grant.json'] and
         g['original_121_transport_sha256']==FACTS['outputs/mp18-budget-run-121/transport.json'],'Fresh originalgrant/source/probe data DAG')
    need(type(g['grant_nonce']) is str and re.fullmatch('[0-9a-f]{32}',g['grant_nonce']),'Fresh nonce')
    start,end=g['started_monotonic'],g['deadline_monotonic'];at=now()
    need(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (start,end,at)) and
         end==start+2700 and start<=at<end,'Fixed root-provided fresh period; no rearming')
    return {'mode':'fresh','start':start,'end':end,'grant_sha256':sha(gb),'reply_sha256':sha(rb)},[(str(gp),gb),(str(rp),rb)]


def period_current(authority,out=OUT,now=time.monotonic):
    metadata=parse(authority.counts_raw)
    selected,_=select_period(metadata['source_freeze_sha256'],metadata['target_probe_sha256'],out,now)
    need(selected==metadata['period'] and authority.end==selected['end'] and now()<authority.end,'Current captured period/mode/fresh raw authority')
    return selected


def capture_authority(M,T,D,out=OUT,require_target_probe=True,now=time.monotonic):
    # Existing121grant is canonical; no123 grant or approval mirror is created.
    grant,reply=M.grant_records(ORIGIN)
    M.source_gate(D,ORIGIN);T.gates(D)
    files,ownfreeze=source_gate(M,D,out)
    facts={}
    for name,expected in FACTS.items():
        p=ROOT/name;b=raw(p);need(sha(b)==expected,'Immutable origin/SDK0 fact: '+name)
        facts[name]=b;files.append((str(p),b))
    snapshot=parse(facts['outputs/mp18-budget-run-121/consumed-snapshot.json'])
    seal=parse(facts['outputs/mp18-budget-run-121/admission.json'])
    go=parse(facts['outputs/mp18-budget-run-121/GO.json'])
    need(base64.b64decode(snapshot['grant_raw_b64'])==grant and base64.b64decode(snapshot['reply_raw_b64'])==reply and
         snapshot['grant_sha256']==sha(grant) and snapshot['reply_sha256']==sha(reply) and
         seal['snapshot_sha256']==sha(facts['outputs/mp18-budget-run-121/consumed-snapshot.json']) and
         seal['proof_sha256']==sha(M.encode(snapshot['proof'])) and go['admission_sha256']==sha(facts['outputs/mp18-budget-run-121/admission.json']), 'Original consumed authority chain')
    need(snapshot['started_monotonic']==seal['started_monotonic']==go['started_monotonic']==PERIOD_START and
         snapshot['deadline_monotonic']==seal['deadline_monotonic']==go['deadline_monotonic']==PERIOD_END and
         snapshot['duration_s']==2700 and go['GO_count']==1,'Original granted period/GO1 unchanged')
    transport=parse(facts['outputs/mp18-budget-run-121/transport.json'])
    need(transport['child_state']=='UNKNOWN' and transport['raw_complete'] is False and transport['terminal'] is False and
         transport['job_active_after']==0 and transport['errors']==['work: BrokenPipeError: [Errno 32] Broken pipe'],'Exact prior ingress failure, not upgraded')
    absence=parse(facts['outputs/mp18-ingress-diagnosis-122/readonly-stdout.raw'])
    outcome=parse(facts['outputs/mp18-budget-run-121/runtime-outcome.json'])
    need(absence=={'unit':122,'kind':'READ_ONLY_RUN_EXISTENCE','run_exists':False,'owner_exists':False,'process_exists':False} and
         outcome['SDK_initializations']==0 and outcome['status']=='INGRESS_FAILED_BEFORE_SDK' and
         outcome['deadline_monotonic']==PERIOD_END,'Original exact remote absence plus frozen bootstrap ordering supports SDK0')
    for path,pin in snapshot['proof']['files'].items():
        b=raw(Path(path));need(sha(b)==pin['sha256'] and len(b)==pin['bytes'],'Current original160 input/source proof')
        files.append((path,b))
    record=snapshot['proof']['record'];run=OLD/'runs'/record['run_id']
    job,data,cfg=D.verified_payload(run,record)
    bundle=raw(run/'bundle.zip')
    need(len(bundle)==40710375 and sha(bundle)==record['bundle_sha256'] and sha(M.encode(cfg))==snapshot['proof']['cfg_sha256'],'Same original bundle/config authority')
    caps=D.C.effective_caps(cfg,D.parse(data['approval.json']));need(caps['J2']==12 and caps['J3']==7,'Reviewed initial caps unchanged')
    probe_count=target_probe(files,ownfreeze,out) if require_target_probe else 0
    need(M.grant_records(ORIGIN)==(grant,reply),'Current canonical121grant before capture')
    probe_hash=sha(dict(files)[str(out/'target-probe.json')]) if require_target_probe else '0'*64
    period,fresh_files=select_period(ownfreeze,probe_hash,out,now)
    files.extend(fresh_files)
    counts={'source_freeze_sha256':ownfreeze,'target_probe_sha256':probe_hash,'period':period,'prior_pipeline':outcome['actual_pipeline_SSH_launches_cumulative'],'prior_readonly':outcome['actual_readonly_SSH_launches'],
            'own_readonly_target_probe':probe_count,'own_pipeline':0,'actual_prior_SDK':0,'SDK_max':1,'SDK_retry':0}
    return Authority(M.encode(record),M.encode(cfg),bundle,tuple(sorted(dict(files).items())),grant,reply,period['end'],encode(counts))


def no_prior(authority,out=OUT):
    record=parse(authority.record_raw);run=OLD/'runs'/record['run_id']
    for path in (out/'admission.json',out/'GO.json',out/'continuation-snapshot.json',out/'transport',out/'run-result.json',
                 run/'retrieved',run/'retrieved.zip',run/'output',OLD/'native-result.json'):
        checked_path(path);need(not path.exists(),'Duplicate continuation or prior SDK/result')


def current(authority,M,out=OUT,now=time.monotonic):
    period_current(authority,out,now)
    for path,expected in authority.files:need(raw(Path(path))==expected,'Current origin/source/probe authority drift')
    r=parse(authority.record_raw);run=OLD/'runs'/r['run_id']
    need(raw(run/'bundle.zip')==authority.bundle,'Current original payload drift')
    need(M.grant_records(ORIGIN)==(authority.grant_raw,authority.reply_raw),'Current canonical121grant/reply revoked or changed')
    period_current(authority,out,now)
    for path in (run/'retrieved',run/'retrieved.zip',run/'output',OLD/'native-result.json',out/'GO.json'):
        checked_path(path);need(not path.exists(),'Prior SDK/result or GO')


def write_all(stream,data,end,now=time.monotonic):
    view=memoryview(data);offset=0
    while offset<len(view):
        need(now()<end,'Write within original absolute end')
        count=stream.write(view[offset:])
        need(type(count) is int and 0<count<=len(view)-offset,'Partial-write progress contract')
        offset+=count
    return offset


class Continuation:
    def __init__(self,M,consumed,out):self.M,self.consumed,self.out=M,consumed,Path(out);self.lock=threading.Lock();self.used=False
    def sender(self,stream,ready,work_end,now=time.monotonic):
        with self.lock:
            c=self.consumed;a=c.authority
            need(not self.used and now()<min(c.dispatch+20,c.end,work_end),'One timely123GO')
            expected={k:parse(a.record_raw)[k] for k in IDENTITY}
            need(type(ready) is dict and set(ready)==set(expected)|{'kind','remote_ready'} and ready['kind']=='READY' and
                 {k:ready[k] for k in expected}==expected and type(ready['remote_ready']) in (int,float) and math.isfinite(ready['remote_ready']),'Original closed READY')
            current(a,self.M,self.out,now)
            need(raw(self.out/'admission.json')==c.seal_raw and raw(self.out/'continuation-snapshot.json')==c.snapshot_raw,'Own original admission/snapshot memory anchor')
            need(self.M.grant_records(ORIGIN)==(a.grant_raw,a.reply_raw) and now()<min(c.dispatch+20,c.end,work_end),'Canonical grant current at firstGO')
            period_current(a,self.out,now)
            exclusive(self.out/'GO.json',encode({'unit':123,'run_id':expected['run_id'],'nonce':expected['nonce'],
                'origin_grant_sha256':sha(a.grant_raw),'origin_admission_sha256':FACTS['outputs/mp18-budget-run-121/admission.json'],
                'own_admission_sha256':sha(c.seal_raw),'sent_monotonic':now(),'dispatch_monotonic':c.dispatch,
                'original_deadline_monotonic':PERIOD_END,'selected_deadline_monotonic':c.end,'period':parse(a.counts_raw)['period'],'GO_count':1,'SDK_max':1,'SDK_retry':0}),self.out)
            self.used=True
            write_all(stream,encode(dict(expected,kind='GO'))+b'\n',min(c.dispatch+20,work_end,c.end),now);stream.flush()
            for at in range(0,len(a.bundle),1024*1024):write_all(stream,a.bundle[at:at+1024*1024],min(work_end,c.end),now)
            stream.flush()


def admit(authority,M,out=OUT,now=time.monotonic):
    need(parse(authority.counts_raw)['own_readonly_target_probe']==1, 'Actual final target probe before SDK admission')
    need(authority.end-now()>1222,'Selected fixed period/headroom before any mutation')
    current(authority,M,out,now);no_prior(authority,out)
    dispatch=now();need(authority.end-dispatch>1222,'Selected current dispatch headroom')
    snapshot=encode({'unit':123,'kind':'CONTINUATION_NOT_NEW_GRANT','dispatch_monotonic':dispatch,'original_started_monotonic':PERIOD_START,
        'deadline_monotonic':authority.end,'original_deadline_monotonic':PERIOD_END,'period':parse(authority.counts_raw)['period'],'origin_grant_path':'outputs/mp18-budget-run-121/user-budget-grant.json','origin_grant_sha256':sha(authority.grant_raw),
        'origin_reply_sha256':sha(authority.reply_raw),'record':parse(authority.record_raw),'bundle_sha256':sha(authority.bundle),
        'current_files':{p:{'sha256':sha(b),'bytes':len(b)} for p,b in authority.files},'counts':parse(authority.counts_raw)})
    seal=encode({'unit':123,'snapshot_sha256':sha(snapshot),'dispatch_monotonic':dispatch,'deadline_monotonic':authority.end,'period':parse(authority.counts_raw)['period'],
                 'origin_grant_sha256':sha(authority.grant_raw),'SDK_max':1,'SDK_retry':0})
    exclusive(out/'admission.json',seal,out);exclusive(out/'continuation-snapshot.json',snapshot,out)
    checked_path(out/'transport').mkdir(exist_ok=False)
    return Continuation(M,Consumed(authority,dispatch,authority.end,snapshot,seal),out)


def run():
    if not fresh_presence():
        need(PERIOD_END-time.monotonic()>1222,'Original period/headroom, no deadline restart')
    M,T,D=load_helpers();authority=capture_authority(M,T,D)
    cfg=parse(authority.cfg_raw);item=cfg['refs']['winjob.py'];helper_raw=raw(ROOT/item['path'])
    need(sha(helper_raw)==item['sha256'],'Original WinJob helper')
    helper=D.load_module('local_job123',helper_raw,ROOT/item['path'])
    continuation=admit(authority,M);c=continuation.consumed;record=parse(authority.record_raw)
    L=c.end-time.monotonic();args=dict(record,remote_root=cfg['remote_root'],remaining=L)
    cmd=proxy_command(str(Path(cfg['sdk']['isaac_root'])/'kit/python/python.exe'),D.bootstrap_code(args),L)
    ssh=Path(os.environ['SystemRoot'])/'System32/OpenSSH/ssh.exe'
    argv=[str(ssh),'-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ConnectTimeout=10',cfg['ssh_alias'],cmd]
    def sender(stream,stdout_path,work_end):
        ready=None
        while time.monotonic()<min(c.dispatch+20,work_end):
            b=stdout_path.read_bytes()
            if b'\n' in b:ready=parse(b.split(b'\n',1)[0]);break
            time.sleep(.01)
        continuation.sender(stream,ready,work_end)
    counts=parse(authority.counts_raw);counts['own_pipeline_attempts']=1
    exclusive(OUT/'pipeline-attempt.json',encode({'unit':123,'dispatch':c.dispatch,'selected_end':c.end,
        'counts':counts,'SDK_max':1,'SDK_retry':0,'original_end':PERIOD_END}))
    process=None
    try:
        process=helper.run(argv,OUT/'transport',c.end-time.monotonic()-2,cleanup_s=2,input_sender=sender)
        exclusive(OUT/'transport.json',encode(process))
        counts['own_pipeline']=1 if type(process.get('child_pid')) is int and process['child_pid']>0 else 0
        need(process['raw_complete'] and process['terminal'] and process['child_state']=='REAPED' and process['job_active_after']==0 and
             process['actual_child_exit_code']==0 and not process['timed_out'],'Actual123 proxy result/reap')
        code=M.consume_result(D,raw(OUT/'transport/stdout.txt'),record,OLD/'runs'/record['run_id'],OUT)
    except BaseException as exc:
        if process is None:counts['own_pipeline']='UNKNOWN'
        exclusive(OUT/'run-result.json',encode({'unit':123,'status':'FAIL','phase':'TRANSPORT_OR_RESULT',
            'error':type(exc).__name__+': '+str(exc),'original_start':PERIOD_START,'original_end':PERIOD_END,
            'period':parse(authority.counts_raw)['period'],'selected_end':c.end,'dispatch':c.dispatch,'finished':time.monotonic(),
            'process':process,'counts':counts,'new_SDK_initializations':'UNKNOWN' if (OUT/'GO.json').exists() else 0,
            'prior_SDK_initializations':0,'hardware_approved':False}))
        raise
    exclusive(OUT/'run-result.json',encode({'unit':123,'status':'PASS' if code==0 else 'FAIL','native_consumer_exit':code,
        'original_start':PERIOD_START,'original_end':PERIOD_END,'period':parse(authority.counts_raw)['period'],'selected_end':c.end,'dispatch':c.dispatch,'finished':time.monotonic(),
        'counts':counts,'new_SDK_initializations':1 if code==0 else 'SEE_ORIGINAL_VERIFIED_NATIVE_RESULT',
        'prior_SDK_initializations':0,'grant_mirrored':False,'hardware_approved':False}))
    return code


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('role',choices=('run',));p.parse_args();raise SystemExit(run())
