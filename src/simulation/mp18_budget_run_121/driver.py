"""121 actual-user-budget admission. No approval creation, network or SDK action at import."""
from __future__ import annotations
import argparse
import base64
from collections import namedtuple
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT/'outputs/mp18-budget-run-121'
OLD = ROOT/'outputs/mp18-isaac-119'
PREVIOUS = ROOT/'outputs/mp18-shell-entry-120'
PLAN_SHA = 'd6468958c3243afd6a5edcc896bf927694acd0b55f76a271e8f217949a84831e'
SOURCE120_FREEZE = '6ad6e771ed782d77c3fc39693846e44c562b217cb40dbcd9fb215c67a00f4c89'
RUN_ID = 'f68441cd00534b88919cfd71f8f436a8'
OLD_END = 379751.359
IDENTITY = ('nonce','run_id','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')
Probe = namedtuple('Probe', 'record_raw cfg_raw bundle files run source_freeze_sha256 attempt_sha256 transport_sha256 stderr_sha256')
Captured = namedtuple('Captured', 'grant_raw reply_raw proof_raw bundle record_raw cfg_raw start end snapshot_raw seal_raw')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def bad(value):
        raise ValueError('Nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def encode(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()


def safe_file(path, root):
    path, root = Path(path), Path(root).resolve()
    need(path.resolve().is_relative_to(root), 'Outside owned/read authority root')
    for part in (path, *path.parents):
        if part == root:
            break
        need(not part.is_symlink() and not part.is_junction(), 'Linked authority path rejected')
    return path


def read_raw(path):
    return safe_file(path, ROOT).read_bytes()


def exclusive(path, raw, out=OUT):
    path = safe_file(path, out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def result_write(path, value, out=OUT):
    exclusive(path, encode(value), out)


def grant_records(out=OUT):
    # No directory creation, source import, snapshot, marker or RPC before both actual files exist.
    grant_raw = safe_file(out/'user-budget-grant.json', out).read_bytes()
    reply_raw = safe_file(out/'user-budget-reply.json', out).read_bytes()
    need(len(grant_raw) <= 65536 and len(reply_raw) <= 65536, 'Bounded canonical grant evidence')
    g, e = parse(grant_raw), parse(reply_raw)
    common = {'unit','kind','approved','duration_s','hardware_approved'}
    need(type(e) is dict and set(e) == common|{'reply_text','conversation_ref'}, 'Closed actual reply evidence')
    need(type(g) is dict and set(g) == common|{'reply_sha256','source_freeze_sha256','original_run_id',
        'original_attempt_sha256','original_transport_sha256','original_stderr_sha256','grant_nonce'}, 'Closed actual user grant')
    for value, kind in ((e,'ACTUAL_USER_REPLY'), (g,'NEW_SIMULATION_BUDGET')):
        need(type(value['unit']) is int and value['unit'] == 121 and value['kind'] == kind and
             value['approved'] is True and type(value['duration_s']) is int and value['duration_s'] == 2700 and
             value['hardware_approved'] is False, 'Actual explicit2700 simulation grant only')
    need(all(type(e[k]) is str and 0 < len(e[k].strip()) <= 16384 for k in ('reply_text','conversation_ref')), 'Retained actual user reply identity/text')
    for key in ('reply_sha256','source_freeze_sha256','original_attempt_sha256','original_transport_sha256','original_stderr_sha256'):
        need(type(g[key]) is str and re.fullmatch('[0-9a-f]{64}',g[key]), 'Closed grant SHA256')
    need(g['reply_sha256'] == digest(reply_raw) and g['original_run_id'] == RUN_ID and
         type(g['grant_nonce']) is str and re.fullmatch('[0-9a-f]{32}',g['grant_nonce']), 'Grant actual reply/run/nonce binding')
    return grant_raw, reply_raw


def load_library():
    # Pin120 before executing any reference; never invoke or replace its retired run entry.
    freeze_path = PREVIOUS/'review/source-freeze.json'
    raw = read_raw(freeze_path)
    need(digest(raw) == SOURCE120_FREEZE, 'Final accepted120 freeze')
    freeze = parse(raw)
    source = ROOT/'src/simulation/mp18_shell_entry_120/driver.py'
    need(digest(read_raw(source)) == freeze['files'][source.relative_to(ROOT).as_posix()]['sha256'], 'Pre-import accepted120 library pin')
    spec = importlib.util.spec_from_file_location('accepted120_for121', source)
    T = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = T
    spec.loader.exec_module(T)
    D = T.legacy()
    return T, D


def source_gate(D, out=OUT):
    freeze_path = out/'review/source-freeze.json'
    freeze_raw = read_raw(freeze_path)
    freeze = parse(freeze_raw)
    files = freeze['files']
    required = {'src/simulation/mp18_budget_run_121/driver.py','src/simulation/mp18_budget_run_121/test_driver.py',
                'docs/design/121-explicit-user-budget-admission.md'}
    need(type(files) is dict and required <= set(files), 'Complete121 reviewed source scope')
    observed = [(freeze_path, freeze_raw)]
    for name, pin in files.items():
        path = D.C.path_in(ROOT, name)
        raw = read_raw(path)
        need(digest(raw) == pin['sha256'] and len(raw) == pin['bytes'], 'Current121 reviewed source drift')
        observed.append((path, raw))
    need(digest(read_raw(ROOT/'docs/design/121-explicit-user-budget-admission.md')) == PLAN_SHA, 'Final L2R2 plan')
    for who in ('main','lens'):
        path = out/('review/'+who+'-L4-final.json')
        raw = read_raw(path)
        report = parse(raw)
        need(type(report['unit']) is int and report['unit'] == 121 and report['phase'] == 'L4' and type(report['round']) is int and report['round'] in (1,2) and report.get('non_author') is True and
             report['verdict'] == 'PASS' and type(report['unmet']) is int and report['unmet'] == 0 and type(report['unresolved_count']) is int and report['unresolved_count'] == 0 and
             report['source_freeze_sha256'] == digest(freeze_raw), 'Final independent121 source acceptance')
        observed.append((path,raw))
    return digest(freeze_raw), observed


def forbidden_prior(run, out=OUT, allow_admission=False):
    paths = [PREVIOUS/'admission.json', PREVIOUS/'GO.json', OLD/'GO.json', OLD/'native-result.json',
             run/'GO.json', run/'retrieved', run/'retrieved.zip', run/'output', out/'GO.json']
    if not allow_admission:
        paths += [out/'admission.json',out/'consumed-snapshot.json',out/'transport']
    need(not any(p.exists() for p in paths), 'Prior SDK/GO/result/admission or duplicate121 dispatch')


def actual_probe(T, D, out=OUT):
    T.gates(D)
    freeze_sha, files = source_gate(D,out)
    record, run, original = T.prior_admission(D)
    need(record['run_id'] == RUN_ID and record['bundle_bytes'] == 40710375 and original['global_deadline_monotonic'] == OLD_END,
         'Same original prepared payload and immutable deadline')
    forbidden_prior(run,out,allow_admission=True)
    job, data, cfg = D.verified_payload(run,record)
    record_raw, cfg_raw = encode(record), encode(cfg)
    bundle = read_raw(run/'bundle.zip')
    need(digest(bundle) == record['bundle_sha256'] and len(bundle) == record['bundle_bytes'], 'Actual full current payload bytes')
    # Freeze raw source/report/failure/cap authority independently of self-declared on-disk digests.
    for base in (OLD,PREVIOUS):
        freeze_path = base/'review/source-freeze.json'
        raw = read_raw(freeze_path)
        need(digest(raw) == (SOURCE120_FREEZE if base == PREVIOUS else T.OLD_FREEZE), 'Captured immutable old source freeze')
        files.append((freeze_path,raw))
        for name,pin in parse(raw)['files'].items():
            path = D.C.path_in(ROOT,name);captured_raw=read_raw(path)
            need(digest(captured_raw)==pin['sha256'] and len(captured_raw)==pin['bytes'], 'Captured old source/input bytes pin')
            files.append((path,captured_raw))
        for who in ('main','lens'):
            path=base/('review/'+who+'-L4-final.json');files.append((path,read_raw(path)))
    for path in (OLD/'prepared.json',OLD/'native-attempt.json',OLD/'user-decision.json',run/'job.json',
                 run/'transport.json',run/'stdout.txt',run/'stderr.txt'):
        files.append((path,read_raw(path)))
    T.gates(D) # Validate copied current report/source authority before dispatch; no ZIP decompression here.
    unique = {str(path): raw for path,raw in files}
    return Probe(record_raw,cfg_raw,bundle,tuple(sorted(unique.items())),str(run),freeze_sha,
                 digest(read_raw(OLD/'native-attempt.json')),digest(read_raw(run/'transport.json')),digest(read_raw(run/'stderr.txt')))


def proof_raw(proof):
    return encode({'record':parse(proof.record_raw),'cfg_sha256':digest(proof.cfg_raw),'bundle_sha256':digest(proof.bundle),
        'files':{path:{'sha256':digest(raw),'bytes':len(raw)} for path,raw in proof.files},'run':proof.run,
        'source_freeze_sha256':proof.source_freeze_sha256,'original_attempt_sha256':proof.attempt_sha256,
        'original_transport_sha256':proof.transport_sha256,'original_stderr_sha256':proof.stderr_sha256})


def refresh_proof(proof, out=OUT):
    """Equivalent current authority by exact captured bytes, without repeated ZIP execution/decompression."""
    for path, expected in proof.files:
        need(read_raw(Path(path)) == expected, 'Current captured authority bytes drift: '+path)
    need(read_raw(Path(proof.run)/'bundle.zip') == proof.bundle, 'Current captured payload drift')
    forbidden_prior(Path(proof.run),out,allow_admission=True)
    safe_file(Path(out)/'transport',out)
    return proof


class Admission:
    def __init__(self, out, probe, captured):
        self.out,self.probe,self.captured=Path(out),probe,captured
        self.lock,self.used=threading.Lock(),False

    def first_go(self, stream, ready, work_end, now=time.monotonic):
        with self.lock:
            c=self.captured
            need(not self.used and now() < min(c.start+20,work_end,c.end), 'One timely first GO only')
            expected={k:parse(c.record_raw)[k] for k in IDENTITY}
            need(type(ready) is dict and set(ready)==set(expected)|{'kind','remote_ready'} and
                 ready['kind']=='READY' and {k:ready[k] for k in expected}==expected and
                 type(ready['remote_ready']) in (int,float) and math.isfinite(ready['remote_ready']), 'Closed actual READY identity')
            grant,reply=grant_records(self.out)
            need(grant==c.grant_raw and reply==c.reply_raw, 'Current actual grant/reply changed or revoked')
            need((self.out/'consumed-snapshot.json').read_bytes()==c.snapshot_raw and
                 (self.out/'admission.json').read_bytes()==c.seal_raw, 'Original consumed snapshot/admission bytes')
            current=self.probe()
            need(proof_raw(current)==c.proof_raw and current.bundle==c.bundle and
                 current.record_raw==c.record_raw and current.cfg_raw==c.cfg_raw, 'Current source/payload/oldfail/cap authority drift')
            # Repeat cheap authority/seal reads after potentially expensive current-payload validation.
            need(grant_records(self.out)==(c.grant_raw,c.reply_raw) and
                 (self.out/'consumed-snapshot.json').read_bytes()==c.snapshot_raw and
                 (self.out/'admission.json').read_bytes()==c.seal_raw and
                 now()<min(c.start+20,work_end,c.end), 'Authority current through first GO')
            go_record=encode({'unit':121,'run_id':expected['run_id'],'nonce':expected['nonce'],
                'grant_nonce':parse(c.grant_raw)['grant_nonce'],'grant_sha256':digest(c.grant_raw),
                'admission_sha256':digest(c.seal_raw),'snapshot_sha256':digest(c.snapshot_raw),
                'started_monotonic':c.start,'deadline_monotonic':c.end,'sent_monotonic':now(),
                'GO_count':1,'SDK_actual_max':1,'SDK_retry':0,'hardware_approved':False})
            exclusive(self.out/'GO.json',go_record,self.out)
            self.used=True
            stream.write(encode(dict(expected,kind='GO'))+b'\n')
            # Send only captured verified bytes; never reopen a mutable bundle after GO.
            for at in range(0,len(c.bundle),1024*1024):
                need(now()<min(work_end,c.end),'Upload within granted absolute end')
                stream.write(c.bundle[at:at+1024*1024])
            stream.flush()


def admit(probe, out=OUT, now=time.monotonic):
    out=Path(out)
    grant,reply=grant_records(out)
    proof=probe()
    g=parse(grant)
    need(g['source_freeze_sha256']==proof.source_freeze_sha256 and
         g['original_attempt_sha256']==proof.attempt_sha256 and g['original_transport_sha256']==proof.transport_sha256 and
         g['original_stderr_sha256']==proof.stderr_sha256, 'Actual grant binds current reviewed source and original failure')
    refresh_proof(proof,out)
    forbidden_prior(Path(proof.run),out)
    need(grant_records(out)==(grant,reply), 'Actual grant/reply current before any consumption')
    # All heavyweight read-only preparation precedes this new first-dispatch clock.
    start=now()
    need(type(start) in (int,float) and math.isfinite(start) and start>0, 'Actual local dispatch monotonic clock')
    end=start+2700.
    snapshot=encode({'unit':121,'kind':'CONSUMED_ACTUAL_USER_BUDGET','grant_raw_b64':base64.b64encode(grant).decode(),
        'reply_raw_b64':base64.b64encode(reply).decode(),'grant_sha256':digest(grant),'reply_sha256':digest(reply),
        'proof':parse(proof_raw(proof)),'grant_nonce':g['grant_nonce'],'job_nonce':parse(proof.record_raw)['nonce'],
        'started_monotonic':start,'deadline_monotonic':end,'duration_s':2700,'original_deadline_monotonic':OLD_END,
        'SSH_cumulative_launches':2,'actual_prior_SDK':0,'SDK_actual_max':1,'SDK_retry':0,'hardware_approved':False})
    seal=encode({'unit':121,'kind':'EXCLUSIVE_BUDGET_ADMISSION','snapshot_sha256':digest(snapshot),
        'grant_sha256':digest(grant),'reply_sha256':digest(reply),'proof_sha256':digest(proof_raw(proof)),
        'started_monotonic':start,'deadline_monotonic':end,'grant_nonce':g['grant_nonce'],
        'run_id':parse(proof.record_raw)['run_id'],'original_deadline_monotonic':OLD_END})
    exclusive(out/'admission.json',seal,out)
    exclusive(out/'consumed-snapshot.json',snapshot,out)
    (out/'transport').mkdir(exist_ok=False)
    return Admission(out,lambda:refresh_proof(proof,out),Captured(grant,reply,proof_raw(proof),proof.bundle,proof.record_raw,proof.cfg_raw,start,end,snapshot,seal))


def result_path_guard(run, path, record):
    """Original lexical ROOT/run remain authority; resolved destination is never a new trust root."""
    run, path = Path(run), Path(path)
    need(type(record.get('run_id')) is str and record['run_id'] == RUN_ID, 'Original result run identity')
    expected = OLD/'runs'/record['run_id']
    need(ROOT.is_absolute() and run == expected and expected.is_relative_to(ROOT), 'Exact original run anchored to original ROOT')
    need(path.is_absolute() and path.is_relative_to(ROOT), 'Result path stays in original ROOT namespace')
    need(path == OLD/'native-result.json' or path == run or path.is_relative_to(run), 'Closed original run/result write role')
    for role in (path, *path.parents, run, *run.parents):
        need(not role.is_symlink() and not role.is_junction(), 'Original result path/ancestor reparse role rejected: '+str(role))
    need(ROOT.resolve() == ROOT and run.resolve() == expected and path.resolve().is_relative_to(ROOT),
         'Original namespace resolution unchanged')
    return path


def consume_result(D, raw, record, run, out=OUT):
    ready_raw,header_raw,archive=raw.split(b'\n',2)
    ready=parse(ready_raw)
    expected={key:record[key] for key in IDENTITY}
    need(type(ready) is dict and set(ready)==set(expected)|{'kind','remote_ready'} and ready['kind']=='READY' and
         {key:ready[key] for key in expected}==expected and type(ready['remote_ready']) in (int,float) and math.isfinite(ready['remote_ready']), 'Recovered actual READY identity')
    header=parse(header_raw)
    need(type(header) is dict and set(header)=={'kind','run_id','nonce','bytes','sha256'} and
         header['kind']=='RESULT' and header['run_id']==record['run_id'] and header['nonce']==record['nonce'] and
         type(header['bytes']) is int and 0<header['bytes']<=2*1024**3 and len(archive)==header['bytes'] and
         digest(archive)==header['sha256'],'Closed actual RESULT byte/hash/nonce')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        need(bool(infos) and len(infos)==len({n.casefold() for n in names}) and sum(i.file_size for i in infos)<2*1024**3,'Bounded unique RESULT inventory')
        for i in infos:
            D._safe_name(i.filename)
            need(not i.is_dir() and i.flag_bits&1==0 and (i.external_attr>>16)&0o170000!=0o120000,'No result links/encryption/directories')
        need({'process.json','recovery-seal.json'} <= set(names),'Original119 required result records')
        destination,archive_path,result_path=run/'retrieved',run/'retrieved.zip',OLD/'native-result.json'
        members=[destination/i.filename for i in infos] # _safe_name checked canonical relative names above.
        # Preflight all proposed roles before any write, then revalidate at each write.
        for path in (run,destination,archive_path,result_path,*members):
            result_path_guard(run,path,record)
        need(not destination.exists() and not archive_path.exists() and not result_path.exists(),'Original result can only be recovered once')
        need(z.testzip() is None, 'Complete actual result CRC')
        result_path_guard(run,destination,record).mkdir(exist_ok=False)
        result_path_guard(run,archive_path,record)
        with archive_path.open('xb') as stream:
            result_path_guard(run,archive_path,record)
            stream.write(archive)
        for i,p in zip(infos,members):
            data=z.read(i)
            result_path_guard(run,p,record)
            p.parent.mkdir(parents=True,exist_ok=True)
            result_path_guard(run,p,record)
            with p.open('xb') as stream:
                result_path_guard(run,p,record)
                stream.write(data)
    for path in (run,destination,archive_path,result_path,*members):
        result_path_guard(run,path,record)
    need(not result_path.exists() and getattr(D,'OUT',OLD)==OLD, 'Original consumer result output role')
    return D.verify_native_result(run,record,destination)


def run():
    grant_records() # Actual absence rejects before imports, snapshots, directories or RPC.
    T,D=load_library()
    probe=lambda:actual_probe(T,D)
    initial=probe()
    cfg=parse(initial.cfg_raw)
    item=cfg['refs']['winjob.py'];raw=read_raw(ROOT/item['path'])
    need(digest(raw)==item['sha256'],'Frozen actual WinJob helper')
    helper=D.load_module('local_job121',raw,ROOT/item['path'])
    admission=admit(lambda:initial)
    c=admission.captured;record=parse(c.record_raw)
    remaining=c.end-time.monotonic()
    need(remaining>1222,'Granted native/recovery headroom')
    args=dict(record,remote_root=cfg['remote_root'],remaining=remaining)
    command=T.proxy_command(str(Path(cfg['sdk']['isaac_root'])/'kit/python/python.exe'),D.bootstrap_code(args),remaining)
    ssh=Path(os.environ['SystemRoot'])/'System32/OpenSSH/ssh.exe'
    argv=[str(ssh),'-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ConnectTimeout=10',cfg['ssh_alias'],command]
    def sender(stream,stdout_path,work_end):
        ready=None
        while time.monotonic()<min(c.start+20,work_end):
            raw=stdout_path.read_bytes()
            if b'\n' in raw:
                ready=parse(raw.split(b'\n',1)[0]);break
            time.sleep(.01)
        admission.first_go(stream,ready,work_end)
    process=helper.run(argv,OUT/'transport',c.end-time.monotonic()-2,cleanup_s=2,input_sender=sender)
    result_write(OUT/'transport.json',process)
    need(process['raw_complete'] and process['terminal'] and process['child_state']=='REAPED' and process['job_active_after']==0 and
         not process['timed_out'] and process['actual_child_exit_code']==0,'Actual proxy reaped complete result')
    code=consume_result(D,(OUT/'transport/stdout.txt').read_bytes(),record,Path(initial.run))
    result_write(OUT/'result.json',{'unit':121,'run_id':record['run_id'],'native_consumer_exit':code,'status':'PASS' if code==0 else 'FAIL',
        'grant_sha256':digest(c.grant_raw),'snapshot_sha256':digest(c.snapshot_raw),'admission_sha256':digest(c.seal_raw),
        'started_monotonic':c.start,'deadline_monotonic':c.end,'original_deadline_monotonic':OLD_END,
        'finished_monotonic':time.monotonic(),'SSH_cumulative_launches':2,'SDK_actual_max':1,'SDK_retry':0,'hardware_approved':False})
    return code


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('role',choices=('run',));p.parse_args();raise SystemExit(run())
