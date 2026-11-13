"""133 bounded one-shot simulation owner, batch result consumer, no physical I/O."""
from __future__ import annotations
import argparse
import base64
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path,PurePosixPath
import re
import sys
import time
import types
import uuid
import zipfile
import zlib

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'outputs/mp18-manipulation-133'


def need(ok,message):
    if not ok:raise ValueError(message)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def encode(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:need(False,'Nonfinite JSON'))


def safe(path,root=ROOT):
    p=Path(path)
    need(p.is_absolute() and p.is_relative_to(root),'Owned absolute path')
    for x in (p,*p.parents):need(not x.is_symlink() and not x.is_junction(),'Reparse path rejected')
    need(p.resolve().is_relative_to(root.resolve()),'Resolved owned path')
    return p


def read(path):return safe(path).read_bytes()


def exclusive(path,raw):
    p=safe(path,OUT);p.parent.mkdir(parents=True,exist_ok=True);safe(p,OUT)
    with p.open('xb') as stream:
        need(stream.write(raw)==len(raw),'Complete exclusive local write')
    need(read(p)==raw,'Actual complete output byte readback')


def load(name,raw,path):
    m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
    exec(compile(raw,str(path),'exec'),m.__dict__);return m


def review_gate(raw,freeze_sha,unit):
    value=parse(raw)
    need(value['unit']==unit and value['phase']=='L4' and value['verdict']=='PASS' and value['non_author'] is True,'Typed nonauthor L4')
    need(type(value['required']) is int and value['required']>=8 and value['met']==value['required'] and value['unmet']==0 and
         value['unresolved_count']==0 and value['all_required_met'] is True,'All required review criteria literally true')
    need(value['source_freeze_sha256']==freeze_sha,'Exact sourceF bound to final L4')
    return value


def capture():
    """One full snapshot per transaction; execute these bytes, never mutable payload paths."""
    cfgraw=read(HERE/'config.json');cfg=parse(cfgraw);deps=cfg['dependency_paths']
    frozen=read(ROOT/deps['freeze133']);F=parse(frozen)
    need(F['unit']==133 and F['hardware_approved'] is False and type(F['files']) is dict,'SourceF133')
    files={}
    for name,pin in F['files'].items():
        p=ROOT/name;raw=read(p)
        need(type(pin['bytes']) is int and len(raw)==pin['bytes'] and digest(raw)==pin['sha256'],'Current SourceF member:'+name)
        files[name]=raw
    rel=(HERE/'config.json').relative_to(ROOT).as_posix()
    need(files[rel]==cfgraw,'Same captured config')
    need(all((HERE/name).relative_to(ROOT).as_posix() in files for name in ('contract.py','native.py','driver.py','runner.py','media.py','config.json','test_contract.py','test_runner.py')),'Eight registered source files')
    r133raw=read(ROOT/deps['review133']);review_gate(r133raw,digest(frozen),133)
    f132=files[deps['freeze132']];review_gate(files[deps['review132']],digest(f132),132)
    frozen132=parse(f132)
    for name,pin in frozen132['files'].items():
        raw=files.get(name)
        need(type(raw) is bytes and len(raw)==pin['bytes'] and digest(raw)==pin['sha256'],'Current inherited132 pin:'+name)
    scope=parse(files[deps['request']])
    need(scope['hardware_approved'] is False and scope['root_internal_allocation']=={'user_explicit_minute_quote':False,'units':[133],'sdk_max':2,'period_s_each':2700,'retry_each':0,'total_period_s_max':5400,'old_grants_rearm':False},'Actual request versus internal bounded allocation')
    need(type(scope['quote']) is str and scope['quote'].strip(),'Actual user request quote')
    return {'cfg':cfg,'files':files,'freeze_raw':frozen,'freeze_sha256':digest(frozen),'review_raw':r133raw,'review_sha256':digest(r133raw),'scope':scope}


def current(snapshot):
    """Transaction boundary verification, not N-files times whole-source hashing."""
    F=parse(snapshot['freeze_raw'])
    for name,pin in F['files'].items():
        raw=read(ROOT/name);need(raw==snapshot['files'][name] and digest(raw)==pin['sha256'],'Current source transaction:'+name)
    deps=snapshot['cfg']['dependency_paths']
    need(read(ROOT/deps['freeze133'])==snapshot['freeze_raw'] and read(ROOT/deps['review133'])==snapshot['review_raw'],'Current typed source authority')


def driver_bytes(snapshot):
    """Produce an entirely captured remote driver with no package-local mutable dependencies."""
    files=snapshot['files'];cfg=snapshot['cfg'];deps=cfg['dependency_paths']
    own=HERE.relative_to(ROOT).as_posix()
    driverraw=files[own+'/driver.py'];baseraw=files[deps['base_driver']]
    return driverraw,baseraw


def payload_inputs(snapshot):
    files=snapshot['files'];cfg=snapshot['cfg'];deps=cfg['dependency_paths'];own=HERE.relative_to(ROOT).as_posix()
    values={'source/'+n:files[own+'/'+n] for n in ('contract.py','native.py','driver.py','config.json','jaw_components.json')}
    values.update({'source/base_'+n+'.py':files[deps['base_'+n]] for n in ('contract','native','driver')})
    values['source/planner132.py']=files[deps['planner132']];values['source/scenario132.json']=files[deps['scenario132']]
    program=parse(files[deps['base_program']]);program['stages']={n:dict(program['stages'][n],duration_s=d) for n,d in {'hold':8,'small':31,'large':54}.items()}
    program['purpose']='PHYSICS_PICK_PLACE_133_LEGACY_ENVELOPE_8_31_54';program['settling']['large_check_s']=48
    values['source/program.json']=encode(program)
    for name,pin in cfg['model_pins'].items():
        raw=files[cfg['model_dir']+'/'+name];need(digest(raw)==pin['sha256'] and len(raw)==pin['bytes'],'Captured model member')
        values['model/'+name]=raw
    for name,pin in cfg['refs'].items():
        raw=files[pin['path']];need(digest(raw)==pin['sha256'],'Captured dependency')
        values['ref/'+name]=raw
    values['approval.json']=files[deps['approval']]
    values['source/current-user-approval.json']=followup_approval(snapshot)
    return values


def attempt_path(attempt):
    need(type(attempt) is int and attempt in (1,2,3,4,5),'Local05 is the single new termination followup; local06 is forbidden')
    return OUT/'attempts'/('%02d'%attempt)


def historical_approval133(snapshot):
    path='outputs/mp18-manipulation-133/Root-user-followup-approval-r5.json'
    raw=snapshot['files'].get(path)
    need(type(raw) is bytes and digest(raw)=='7319648b1e7e30f7eaa4e42e5ca9b37ca0747e81336b1fa246ab9f17f2eca6c4','Actual separately pinned followup user approval')
    v=parse(raw)
    need(v['status']=='GRANTED' and v['approval_answer']=='진행ㅎ9' and v['hardware_approved'] is False and v['future_first_remote_period_s']==2700 and v['future_SDK_max']==1 and v['retry']==0 and v['future_remote_requires_code_acceptance'] is True,'Exact current followup approval execution scope')
    return raw


def followup_approval(snapshot):
    path='outputs/mp18-manipulation-133/Root-user-termination-approval-r7.json';raw=snapshot['files'].get(path)
    need(type(raw) is bytes and digest(raw)=='5a2f2e4656fdb0d9b9ed4d082751a3d001ea2d9059f509bd14def3b0355611fc','Actual current termination followup user approval')
    v=parse(raw)
    need(v['status']=='GRANTED' and v['approval_answer']=='추가 승인' and v['hardware_approved'] is False and v['total_remote_s']==2700 and v['future_SDK_max']==1 and v['future_local_attempt']==5 and v['future_actual_SDK_ordinal']==4 and v['retry']==0 and v['old_periods_rearm'] is False,'Exact new05 execution authority')
    return raw


def previous_gate(attempt,snapshot=None):
    if attempt==1:return
    if attempt==5:
        need(snapshot is not None,'Current05 requires captured new grant and original incomplete04')
        followup_approval(snapshot);previous_gate(4,snapshot)
        prior=attempt_path(4);names=['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/recovery-seal.json']
        values={}
        for name in names:
            path=prior/name;raw=read(path);need(snapshot['files'].get(path.relative_to(ROOT).as_posix())==raw,'Pinned original04 incomplete ownership:'+name);values[name]=parse(raw)
        record=values['prepared.json'];job=values['job.json'];dispatch=values['attempt.json'];go=values['GO.json'];result=values['run-result.json'];proc=values['retrieved/process.json'];recovery=values['retrieved/recovery-seal.json']
        identity={k:record[k] for k in ('run_id','nonce','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
        need(dispatch['identity']==go['identity']==result['identity']==identity and record['attempt']==dispatch['attempt']==result['attempt']==4,'Original04 dispatch/run/job/nonce tuple')
        _transport(values['transport.json']);_process(proc,job,record)
        need(result['status']=='FAIL' and result['transport_reaped'] is True and result['SDK_reaped'] is True and proc['actual_child_exit_code']==proc['policy_exit_code']==124 and proc['policy_basis']=='CHILD_EXIT' and proc['timed_out'] is False and proc['errors']==[],'Observed04 child124 reaped is incomplete, not successful or parent timeout')
        need(type(proc['child_creation_time']) is int and proc['child_creation_time']>0 and recovery['actual_child_pid']==proc['child_pid'] and recovery['run_id']==record['run_id'] and recovery['job_sha256']==record['job_sha256'],'Original04 recovery/PID birth identity')
        need(dispatch['period_end']==dispatch['period_start']+2700 and go['period_end']==result['period_end']==dispatch['period_end'] and go['attempt']==4,'Original04 period remains immutable')
        missing={'terminal.json','report.json','manipulation.json'}
        need(not missing.intersection(recovery['files_sha256']) and all(not (prior/'retrieved'/n).exists() for n in missing),'Original04 missing native final files preserved')
        folder=prior/'retrieved'
        actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        need(actual==set(recovery['files_sha256'])|{'recovery-seal.json'},'Complete original04 incomplete recovery inventory')
        for name,pin in recovery['files_sha256'].items():
            need(digest(read(folder/_zip_name(name)))==pin,'Actual original04 recovery bytes:'+name)
        for name in ('process.json','owner.json','report.partial.json'):
            raw=read(prior/'retrieved'/name);need(digest(raw)==recovery['files_sha256'][name],'Original04 sealed incomplete record:'+name)
            if name=='report.partial.json':
                partial=parse(raw);need(partial['watchdog']['parent_birth']==proc['child_creation_time'] and partial['watchdog']['parent_pid']==proc['child_pid'] and partial['run_id']==record['run_id'] and partial['job_sha256']==record['job_sha256'],'Original04 owned partial evidence')
        return
    if attempt==4:
        need(snapshot is not None,'Current user followup requires captured authority')
        historical_approval133(snapshot);previous_gate(3,snapshot)
        prior=attempt_path(3);names=['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/report.json','retrieved/terminal.json','retrieved/recovery-seal.json']
        values={}
        for name in names:
            path=prior/name;raw=read(path);need(snapshot['files'].get(path.relative_to(ROOT).as_posix())==raw,'Original complete failed03 evidence:'+name);values[name]=parse(raw)
        record=values['prepared.json'];job=values['job.json'];dispatch=values['attempt.json'];go=values['GO.json'];result=values['run-result.json'];proc=values['retrieved/process.json'];report=values['retrieved/report.json'];terminal=values['retrieved/terminal.json'];recovery=values['retrieved/recovery-seal.json']
        identity={k:record[k] for k in ('run_id','nonce','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
        need(dispatch['identity']==go['identity']==result['identity']==identity and record['attempt']==dispatch['attempt']==result['attempt']==3,'Original03 run/nonce/job admission')
        _transport(values['transport.json']);_process(proc,job,record)
        need(result['status']=='FAIL' and result['transport_reaped'] is True and result['SDK_reaped'] is True and proc['actual_child_exit_code']==proc['policy_exit_code']==1 and proc['errors']==[] and terminal['code']==1,'Original failed03 actual SDK and transport reaped')
        need(terminal['run_id']==report['run_id']==recovery['run_id']==record['run_id'] and terminal['job_sha256']==report['job_sha256']==recovery['job_sha256']==record['job_sha256'] and terminal['pid']==recovery['actual_child_pid']==proc['child_pid'],'Original03 complete recovery identity')
        need(report['watchdog']['parent_birth']==proc['child_creation_time'] and report['watchdog']['parent_pid']==proc['child_pid'] and report['runtime_accepted'] is False and report['completed_steps']==6197 and report['phases'][2]['status']=='PASS' and report['phases'][3]['status']=='FAIL','Original03 actual failure and PID birth')
        need(dispatch['period_end']==dispatch['period_start']+2700 and go['period_end']==result['period_end']==dispatch['period_end'] and go['attempt']==3,'Original03 period not rearmed')
        for name in ('process.json','report.json','terminal.json'):
            need(digest(read(prior/'retrieved'/name))==recovery['files_sha256'][name],'Failed03 closed artifact seal pin')
        return
    if attempt==3:
        previous_gate(2,snapshot)
        prior=attempt_path(2)
        names=['prepared.json','job.json','attempt.json','GO.json','transport.json','run-result.json','retrieved/process.json','retrieved/report.json','retrieved/terminal.json']
        values={}
        need(snapshot is not None,'Last actual SDK requires pinned previous failure')
        for name in names:
            path=prior/name;raw=read(path);need(snapshot['files'].get(path.relative_to(ROOT).as_posix())==raw,'Pinned actual SDK1 evidence:'+name);values[name]=parse(raw)
        record=values['prepared.json'];job=values['job.json'];dispatch=values['attempt.json'];go=values['GO.json'];result=values['run-result.json'];proc=values['retrieved/process.json'];report=values['retrieved/report.json'];terminal=values['retrieved/terminal.json']
        identity={k:record[k] for k in ('run_id','nonce','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
        need(dispatch['identity']==go['identity']==result['identity']==identity and record['attempt']==dispatch['attempt']==result['attempt']==2,'Original second-local actual SDK identity')
        need(result['status']=='FAIL' and result['transport_reaped'] is True and result['SDK_reaped'] is True,'Last SDK only after actual failed/reaped first SDK')
        _transport(values['transport.json']);_process(proc,job,record)
        need(proc['actual_child_exit_code']==1 and proc['policy_exit_code']==1 and proc['errors']==[] and terminal['code']==1 and terminal['pid']==proc['child_pid'] and terminal['run_id']==report['run_id']==record['run_id'] and terminal['job_sha256']==report['job_sha256']==record['job_sha256'],'Authentic original failed SDK1 records')
        need(report['runtime_accepted'] is False and report['phases'][0]['status']=='PASS' and report['phases'][1]['status']=='FAIL' and report['completed_steps']==720,'Measured6s first-home failure only')
        need(dispatch['period_end']==dispatch['period_start']+2700 and go['period_end']==result['period_end']==dispatch['period_end'] and go['attempt']==2,'Prior actual SDK period immutable')
        return
    previous=attempt_path(1)
    result=parse(read(previous/'run-result.json'))
    need(result['status']=='FAIL','No retry after success')
    need(result['attempt']==1 and result['new_SDK_max']==1,'Original first-attempt accounting')
    if result['transport_reaped'] is True and result['SDK_reaped'] is True:return
    need(snapshot is not None,'No-process continuation requires captured F-bound original evidence')
    expected={'bundle.zip','job.json','prepared.json','attempt.json','transport.json','run-result.json'}
    need({p.relative_to(previous).as_posix() for p in previous.rglob('*')}==expected,'No GO/transport/recovery/process traces in NOT_CREATED attempt')
    values={}
    for name in expected:
        path=previous/name;rel=path.relative_to(ROOT).as_posix();raw=read(path)
        need(type(snapshot['files'].get(rel)) is bytes and snapshot['files'][rel]==raw,'Original failed no-process evidence pinned to current sourceF:'+name)
        values[name]=raw
    p=parse(values['transport.json']);record=parse(values['prepared.json']);dispatch=parse(values['attempt.json']);job=parse(values['job.json'])
    need(p['child_state']=='NOT_CREATED' and p['child_pid'] is None and p.get('child_creation_time') is None and p['actual_child_exit_code'] is None and
         p['job_active_after'] is None and p['raw_complete'] is False and p['terminal'] is False and p['timed_out'] is False and
         type(p['policy_exit_code']) is int and p['policy_exit_code']==125 and p['policy_basis']=='ERROR' and
         type(p['errors']) is list and len(p['errors'])==1 and p['errors'][0].startswith('work: FileNotFoundError:'),'Actual known local NOT_CREATED lifetime only; UNKNOWN/created rejected')
    identity={k:record[k] for k in ('run_id','nonce','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
    need(dispatch['identity']==result['identity']==identity and record['unit']==dispatch['unit']==result['unit']==133 and
         record['attempt']==dispatch['attempt']==result['attempt']==1 and record['hardware_approved'] is False and result['hardware_approved'] is False,'Original failed prepared/dispatch/result identity')
    need(result['transport_reaped'] is False and result['SDK_reaped'] is False and dispatch['run_id']==result['run_id']==record['run_id'] and
         dispatch['source_freeze_sha256']==result['source_freeze_sha256']==record['source_freeze_sha256'] and
         dispatch['period_start']==result['period_start'] and dispatch['period_end']==result['period_end']==dispatch['period_start']+2700 and
         dispatch['fixed_period_s']==2700 and dispatch['retry']==result['retry']==0,'Original NOT_CREATED preserved; no reap/period fabrication')
    need(digest(values['job.json'])==record['job_sha256'] and digest(values['bundle.zip'])==record['bundle_sha256'] and len(values['bundle.zip'])==record['bundle_bytes'],'Original no-process package actual bytes')
    need(job['run_id']==record['run_id'] and job['nonce']==record['nonce'] and job['task_unit']==133 and job['hardware_approved'] is False and
         job['source_freeze_sha256']==record['source_freeze_sha256'] and job['review_sha256']==record['review_sha256'] and
         job['inputs']['source/driver.py']==record['driver_sha256'],'Original no-process job/source identity')


def transport_directory(out):
    path=safe(out/'transport',OUT)
    need(not path.exists(),'Fresh exclusive transport directory')
    path.mkdir(parents=False,exist_ok=False)
    need(safe(path,OUT).is_dir() and not any(path.iterdir()),'Exact empty owned transport directory')
    return path


def prepare(attempt=1):
    snapshot=capture();previous_gate(attempt,snapshot);out=attempt_path(attempt)
    need(not out.exists(),'Fresh attempt root only')
    values=payload_inputs(snapshot);run_id,nonce=uuid.uuid4().hex,uuid.uuid4().hex
    job={'unit':119,'task_unit':133,'schema_version':1,'purpose':'physics_pick_place_133','run_id':run_id,'nonce':nonce,
         'hardware_approved':False,'source_freeze_sha256':snapshot['freeze_sha256'],'review_sha256':snapshot['review_sha256'],'current_user_approval_sha256':digest(followup_approval(snapshot)),
         'inputs':{name:digest(raw) for name,raw in values.items()}}
    jobraw=encode(job);buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        z.writestr('job.json',jobraw)
        for name,raw in values.items():z.writestr('input/'+name,raw)
    bundle=buffer.getvalue();need(len(bundle)<=128*1024*1024,'Bounded payload')
    current(snapshot)
    exclusive(out/'bundle.zip',bundle);exclusive(out/'job.json',jobraw)
    record={'unit':133,'attempt':attempt,'run_id':run_id,'nonce':nonce,'bundle_sha256':digest(bundle),'bundle_bytes':len(bundle),
            'job_sha256':digest(jobraw),'driver_sha256':digest(values['source/driver.py']),'source_freeze_sha256':snapshot['freeze_sha256'],
            'review_sha256':snapshot['review_sha256'],'hardware_approved':False}
    exclusive(out/'prepared.json',encode(record));return record


def _payload(snapshot,out):
    record=parse(read(out/'prepared.json'));jobraw=read(out/'job.json');bundle=read(out/'bundle.zip')
    need(record['source_freeze_sha256']==snapshot['freeze_sha256'] and record['review_sha256']==snapshot['review_sha256'],'Prepared authority current')
    need(digest(jobraw)==record['job_sha256'] and digest(bundle)==record['bundle_sha256'] and len(bundle)==record['bundle_bytes'],'Original prepared bytes')
    expected=payload_inputs(snapshot);job=parse(jobraw)
    need(job['run_id']==record['run_id'] and job['nonce']==record['nonce'] and job['inputs']=={k:digest(v) for k,v in expected.items()} and job['source_freeze_sha256']==snapshot['freeze_sha256'] and job['review_sha256']==snapshot['review_sha256'],'Prepared exact current task inputs')
    with zipfile.ZipFile(io.BytesIO(bundle)) as z:
        need(len(z.infolist())==len(set(i.filename.casefold() for i in z.infolist())) and set(z.namelist())=={'job.json'}|{'input/'+k for k in expected},'Exact package inventory')
        need(z.read('job.json')==jobraw,'Same package job')
        for k,v in expected.items():need(z.read('input/'+k)==v,'Actual captured package member')
    return record,job,bundle


def _remote_driver(snapshot):
    """In-memory load uses fake HERE with checked dependency bytes via temporary module compiler."""
    own=HERE.relative_to(ROOT).as_posix();raw=snapshot['files'][own+'/driver.py']
    # Local prepare needs only bootstrap_code; execute its original source-independent builder.
    base=snapshot['files'][snapshot['cfg']['dependency_paths']['base_driver']].decode()
    anchor="endswith('/robot-arm-lab/119/runs')";need(base.count(anchor)==1,'Exact remote namespace derivation')
    base=base.replace(anchor,"endswith('/robot-arm-lab/133/runs')",1)
    need(base.count('local_remaining > handshake+602')==1,'Exact bootstrap reserve boundary')
    base=base.replace('local_remaining > handshake+602','local_remaining > handshake+362',1)
    import ast
    names={'need','_safe_name','_unpack_payload','lease_end','_bootstrap'}
    blocks=[ast.get_source_segment(base,n) for n in ast.parse(base).body if isinstance(n,ast.FunctionDef) and n.name in names]
    contract=snapshot['files'][snapshot['cfg']['dependency_paths']['base_contract']].decode()
    parseblock=next(ast.get_source_segment(contract,n) for n in ast.parse(contract).body if isinstance(n,ast.FunctionDef) and n.name=='parse')
    need(len(blocks)==len(names),'Exact bootstrap functions')
    header='import sys,os,time,threading,hashlib,json,math,re,types,io,zipfile\nfrom pathlib import Path,PurePosixPath\n'
    return header+'\n\n'.join(blocks)+'\n'+parseblock+'\n'


def proxy_command(snapshot,code,remaining):
    """Execute only pinned pure120 quoting/proxy functions and pinned123 raw-stdin adapter."""
    import ast
    deps=snapshot['cfg']['dependency_paths'];files=snapshot['files']
    source=files[deps['proxy120']].decode()
    selected=[ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in ('ps_literal','proxy_command')]
    need(len(selected)==2,'Exact captured120 pure proxy functions')
    header='import subprocess,math,base64\nfrom pathlib import Path\n'
    m=load('proxy120_captured133',(header+'\n\n'.join(selected)).encode(),ROOT/deps['proxy120']);m.need=need
    p=load('proxy123_captured133',files[deps['proxy']],ROOT/deps['proxy']);p.load_transport=lambda:m
    return p.proxy_command(code=code,executable=str(Path(snapshot['cfg']['sdk']['isaac_root'])/'kit/python/python.exe'),remaining=remaining)


def run(attempt=1):
    snapshot=capture();previous_gate(attempt,snapshot);out=attempt_path(attempt);record,job,bundle=_payload(snapshot,out)
    need(not (out/'attempt.json').exists() and not (out/'GO.json').exists(),'One-shot dispatch cannot rearm')
    cfg=snapshot['cfg'];deps=cfg['dependency_paths'];proxyraw=snapshot['files'][deps['proxy']]
    need(digest(proxyraw)=='8e8b134556ffad2faf105c73440b07af83baef408069331fdcfb1b40703855ad','Original123 raw-stdin proxy')
    hp=cfg['refs']['winjob.py'];helper=load('winjob133',snapshot['files'][hp['path']],ROOT/hp['path'])
    current(snapshot)
    # The first remote command starts this immutable period; preparation/waits are excluded.
    start=time.monotonic();end=start+2700.
    identity={k:record[k] for k in ('run_id','nonce','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
    args=dict(identity,remote_root=cfg['remote_root'],remaining=end-time.monotonic())
    bootstrap=_remote_driver(snapshot)+'\n_bootstrap('+repr(args)+')\n'
    compressed=base64.b64encode(zlib.compress(bootstrap.encode(),9)).decode()
    literal="import base64,zlib;exec(zlib.decompress(base64.b64decode('"+compressed+"')))"
    need(len(literal)<7000,'Original bounded compressed bootstrap')
    command=proxy_command(snapshot,literal,end-time.monotonic())
    ssh=Path(os.environ['SystemRoot'])/'System32/OpenSSH/ssh.exe'
    argv=[str(ssh),'-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ConnectTimeout=10',cfg['ssh_alias'],command]
    dispatch={'unit':133,'attempt':attempt,'run_id':record['run_id'],'period_start':start,'period_end':end,'fixed_period_s':2700,
              'first_remote_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'retry':0,'new_SDK_max':1,
              'user_explicit_minutes':attempt in (4,5),'root_internal_allocation':attempt not in (4,5),'current_user_approval_sha256':digest(followup_approval(snapshot)),'source_freeze_sha256':snapshot['freeze_sha256'],'identity':identity}
    exclusive(out/'attempt.json',encode(dispatch))
    def sender(stream,stdout_path,work_end):
        ready=None
        while time.monotonic()<min(start+20,work_end):
            raw=read(stdout_path)
            if b'\n' in raw:ready=parse(raw.split(b'\n',1)[0]);break
            time.sleep(.01)
        need(type(ready) is dict and {k:ready.get(k) for k in identity}==identity and ready.get('kind')=='READY','Actual remote READY binding')
        need(time.monotonic()<min(start+20,work_end) and type(ready.get('remote_ready')) in (int,float) and math.isfinite(ready['remote_ready']),'Bounded READY time')
        go=encode(dict(identity,kind='GO'))
        exclusive(out/'GO.json',encode({'unit':133,'attempt':attempt,'identity':identity,'go_sha256':digest(go),'period_end':end,'retry':0}))
        data=go+bundle;view=memoryview(data);offset=0
        while offset<len(view):
            need(time.monotonic()<work_end,'Original transport deadline')
            written=stream.write(view[offset:offset+1024*1024]);need(type(written) is int and written>0,'Complete raw stdin send')
            offset+=written
        stream.flush()
    process=None
    try:
        transport=transport_directory(out)
        current(snapshot)
        need(safe(transport,OUT).is_dir() and not any(transport.iterdir()),'Current owned empty transport directory immediately before helper')
        process=helper.run(argv,transport,end-time.monotonic()-2,cleanup_s=2,input_sender=sender)
        exclusive(out/'transport.json',encode(process))
        _transport(process)
        current(snapshot)
        value=consume(attempt,snapshot=snapshot,admitted=(record,job,dispatch))
        status='PASS' if value['runtime_accepted'] else 'FAIL'
    except BaseException as exc:
        sdk_reaped=False
        recovered=out/'retrieved/process.json'
        if recovered.exists():
            try:sdk_reaped=_process(parse(read(recovered)),job,record)
            except (ValueError,KeyError,TypeError):sdk_reaped=False
        result=dict(dispatch,status='FAIL',error=type(exc).__name__+': '+str(exc),transport_reaped=bool(process and process.get('child_state')=='REAPED' and process.get('job_active_after')==0),SDK_reaped=sdk_reaped,finished_monotonic=time.monotonic(),hardware_approved=False)
        exclusive(out/'run-result.json',encode(result));raise
    result=dict(dispatch,status=status,transport_reaped=True,SDK_reaped=True,finished_monotonic=time.monotonic(),hardware_approved=False)
    exclusive(out/'run-result.json',encode(result));return value


def _transport(process):
    need(process['raw_complete'] is True and process['terminal'] is True and process['child_state']=='REAPED' and process['job_active_after']==0 and
         type(process['actual_child_exit_code']) is int and process['actual_child_exit_code']==0 and type(process['policy_exit_code']) is int and process['policy_exit_code']==0 and process['timed_out'] is False and process['errors']==[],'Actual SSH lifetime reaped exit0')


def _process(process,job,record):
    need(process['raw_complete'] is True and process['terminal'] is True and process['child_state']=='REAPED' and process['job_active_after']==0 and process['timed_out'] is False,'Actual SDK lifetime reaped')
    need(process['run_id']==record['run_id']==job['run_id'] and process['job_sha256']==record['job_sha256'],'SDK lifetime same run/job')
    need(type(process['child_pid']) is int and process['child_pid']>0 and type(process['child_creation_time']) is int,'Actual SDK PID/birth')
    return True


def _zip_name(name):
    need(type(name) is str and name and not any(c in name for c in ('\\',':','\0','\n','\r')),'Closed recovery path')
    p=PurePosixPath(name)
    need(not p.is_absolute() and p.as_posix()==name and all(s not in ('.','..') and not s.endswith((' ','.')) and not re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',s) for s in p.parts),'Canonical recovery role')
    return name


def unpack_result(wire,record):
    first,sep,rest=wire.partition(b'\n');need(sep==b'\n','READY record')
    ready=parse(first);line,sep,archive=rest.partition(b'\n');need(sep==b'\n','RESULT record')
    result=parse(line)
    need(ready['kind']=='READY' and result['kind']=='RESULT' and ready['run_id']==result['run_id']==record['run_id'] and ready['nonce']==result['nonce']==record['nonce'],'Wire run/nonce binding')
    for k in ('job_sha256','driver_sha256','bundle_sha256','bundle_bytes'):need(ready[k]==record[k],'READY prepared identity')
    need(type(result['bytes']) is int and len(archive)==result['bytes'] and digest(archive)==result['sha256'],'Complete result binary SHA/length')
    need(len(archive)<=2*1024**3,'Bounded result archive')
    return archive,result


def extract_archive(archive,destination):
    need(not destination.exists(),'Fresh exclusive recovery destination')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos=z.infolist();need(len(infos)<=4096 and len(infos)==len({i.filename.casefold() for i in infos}),'No duplicate recovery paths')
        need(sum(i.file_size for i in infos)<=4*1024**3,'Bounded uncompressed result')
        values={}
        for i in infos:
            name=_zip_name(i.filename)
            need(not i.is_dir() and (i.external_attr>>16)&0o170000!=0o120000,'No result symlink/directory')
            values[name]=z.read(i) # ZipFile checks each actual CRC before publication.
    recovery=parse(values['recovery-seal.json']);sealed=recovery['files_sha256']
    need(set(values)==set(sealed)|{'recovery-seal.json'},'Exact recovery inventory')
    for name,pin in sealed.items():need(digest(values[name])==pin,'Every recovery member actual SHA')
    for name,raw in values.items():exclusive(destination/name,raw)
    return values,recovery


def lifecycle(values,job,record):
    p=parse(values['process.json']);_process(p,job,record)
    need(type(p['actual_child_exit_code']) is int and p['actual_child_exit_code']==0 and type(p['policy_exit_code']) is int and p['policy_exit_code']==0 and p['errors']==[],'Actual SDK child code0/errors0')
    need(values['status.json']==values['terminal.json'],'Original terminal/status identical bytes')
    t=parse(values['terminal.json'])
    need(t['run_id']==record['run_id'] and t['job_sha256']==record['job_sha256'] and t['pid']==p['child_pid'] and t.get('purpose')=='physics_pick_place_133','Terminal actual SDK/run/job/task')
    need(type(t['code']) is int and t['code']==0 and t.get('hardware_approved') is False and t.get('physical_calibration') is False and t.get('training')=='NOT_RUN','SDK successful simulation-only terminal')
    need((t['status'],t['phase']) in (('COMPLETE_PRE_CLOSE','CLOSING_APP'),('CLOSED','APP_CLOSED')),'Exact supported lifecycle representation')
    owner=parse(values['owner.json'])
    need(t['parent_pid']==p['parent_pid']==owner['parent_pid'] and owner['run_id']==record['run_id'] and owner['job_sha256']==record['job_sha256'],'Actual owned SDK parent/run/job')
    need(not any(k in t for k in ('primary_error','close_error','cleanup_error')),'No hidden SDK terminal errors')
    report=parse(values['report.json']);watchdog=report['watchdog']
    need(watchdog['parent_pid']==p['child_pid'] and watchdog['parent_birth']==p['child_creation_time'],'SDK PID creation time tied to owned native watchdog')
    recovery=parse(values['recovery-seal.json'])
    expected={n:v for n,v in recovery['files_sha256'].items() if n not in {'process.json','status.json','stderr.txt','stdout.txt','terminal.json'}}
    need(t['files_sha256']==expected,'Exact native terminal artifact seal versus parent recovery minus5')
    for name,pin in t['files_sha256'].items():need(digest(values[name])==pin,'Actual native artifact member')
    return t,p


def consume(attempt=1,snapshot=None,admitted=None):
    s=capture() if snapshot is None else snapshot;current(s);out=attempt_path(attempt);record,job,bundle=_payload(s,out)
    dispatch=parse(read(out/'attempt.json'));go=parse(read(out/'GO.json'))
    expected_identity={k:record[k] for k in ('run_id','nonce','driver_sha256','bundle_sha256','bundle_bytes','job_sha256')}
    need(dispatch['run_id']==record['run_id'] and dispatch['source_freeze_sha256']==s['freeze_sha256'] and dispatch['identity']==go['identity']==expected_identity and go['period_end']==dispatch['period_end'],'Original admitted dispatch/GO identity')
    if admitted is not None:need((record,job,dispatch)==admitted,'Actual captured pre-RPC admission still current')
    need(dispatch['fixed_period_s']==2700 and dispatch['period_end']==dispatch['period_start']+2700 and dispatch['attempt']==go['attempt']==attempt and go['retry']==0,'Original fixed one-shot period')
    _transport(parse(read(out/'transport.json')))
    archive,wire=unpack_result(read(out/'transport/stdout.txt'),record)
    exclusive(out/'retrieved.zip',archive)
    values,recovery=extract_archive(archive,out/'retrieved')
    need(recovery['unit']==119 and recovery['run_id']==record['run_id'] and recovery['job_sha256']==record['job_sha256'],'Recovery original job identity')
    terminal,process=lifecycle(values,job,record)
    need(recovery['actual_child_pid']==process['child_pid'],'Recovery actual SDK child identity')
    # Re-run original SDK provider/postnumeric/binding validation over authentic new records.
    cfg=s['cfg'];deps=cfg['dependency_paths'];sdkpin=cfg['refs']['sdk.py']
    hostdriver=types.ModuleType('driver');hostdriver.need=need;hostdriver.read=lambda p:parse(read(p))
    hostdriver.write=lambda *a:need(False,'Pure SDK host verification has no write authority')
    hostdriver.sha=lambda p:digest(read(p));hostdriver.load_module=load
    sys.modules['driver']=hostdriver
    sdk=load('sdk133_consume',s['files'][sdkpin['path']],ROOT/sdkpin['path'])
    baseC=load('baseC133_consume',s['files'][deps['base_contract']],ROOT/deps['base_contract'])
    class Context:pass
    ctx=Context();ctx.job=job;ctx.job_hash=record['job_sha256'];ctx.cfg=cfg
    ctx.data=payload_inputs(s);ctx.contract=baseC;ctx.sha=lambda p:digest(read(p));ctx.run=out
    sdkproof=sdk.verify_records(ctx,out/'retrieved',terminal)
    report=parse(values['report.json']);task=parse(values['manipulation.json'])
    need(report['run_id']==record['run_id'] and report['job_sha256']==record['job_sha256'] and report['pid']==process['child_pid'],'Actual new report identity')
    need(report['runtime_accepted'] is True and all(p['status']=='PASS' for p in report['phases']) and report['completed_steps']==11160,'Complete native task phases')
    need(report['manipulation']==task and task['passed'] is True and task['rows']==11161 and task['physics_grasp']=='ACTUAL_DYNAMIC_FREE_OBJECT','Actual physical task final report')
    need(task['lift_hold_steps']>=60 and task['release_hold_steps']>=120 and task['positive_bilateral_samples']>0,'Genuine current contact/lift/release')
    # Original motion rows/actual-object evidence are sealed; independently rerun task acceptance.
    replay_task(s,values)
    current(s)
    result={'unit':133,'attempt':attempt,'run_id':record['run_id'],'job_sha256':record['job_sha256'],'runtime_accepted':True,
            'source_freeze_sha256':s['freeze_sha256'],'review_sha256':s['review_sha256'],'archive_sha256':digest(archive),'archive_bytes':len(archive),
            'files_sha256':{n:digest(v) for n,v in values.items()},'terminal_status':terminal['status'],'SDK_reaped':True,
            'SDK_pid':process['child_pid'],'SDK_birth':process['child_creation_time'],'watchdog_reason':process.get('watchdog_reason',{'status':'UNKNOWN_NOT_RECORDED'}),'sdk_postcheck':sdkproof,'task':task,'hardware_approved':False}
    exclusive(out/'native-result.json',encode(result));return result


def replay_task(snapshot,values):
    # Execute the same F-bound task contract, independently against sealed raw rows.
    files=snapshot['files'];deps=snapshot['cfg']['dependency_paths'];own=HERE.relative_to(ROOT).as_posix()
    base=files[deps['base_contract']];facade=files[own+'/contract.py'].decode()
    anchor="_base = (HERE/'base_contract.py').read_bytes()";need(facade.count(anchor)==1,'Exact in-memory base contract capture')
    facade=facade.replace(anchor,'_base = '+repr(base),1)
    C=load('task133_replay',facade.encode(),HERE/'contract.py')
    planner=load('planner132_replay',files[deps['planner132']],ROOT/deps['planner132'])
    scenario=parse(files[deps['scenario132']]);C.configure(scenario,planner)
    scene=parse(values['manipulation-scene.json']);paths=scene.get('jaw_paths')
    need(type(paths) is dict and set(paths)=={'KG1_A','KG1_B'},'Sealed actual named jaw body paths')
    active=scene['jaw_component_overlay']['after_reset']['active_components']
    need(len(active)==12,'Actual reset-verified twelve collider inventory for contact replay')
    task=C.Task(scenario,scene['object']['path'],paths,{name:{r['path'] for r in active if r['owner_path']==path} for name,path in paths.items()})
    count=0
    for line in values['motion.ndjson'].splitlines():
        row=parse(line);task.observe(row,row['object'],row.get('object_contacts',{}));count+=1
    result=task.finish();need(result==parse(values['manipulation.json']) and count==11161,'Independent replay exact task result')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('prepare','run','consume','encode'));parser.add_argument('--attempt',type=int,default=1)
    args=parser.parse_args()
    if args.role=='encode':
        s=capture();raw=s['files'][HERE.relative_to(ROOT).as_posix()+'/media.py'];m=load('media133',raw,HERE/'media.py');result=m.encode_video(args.attempt,s)
    else:result={'prepare':prepare,'run':run,'consume':consume}[args.role](args.attempt)
    print(json.dumps(result,ensure_ascii=False))
