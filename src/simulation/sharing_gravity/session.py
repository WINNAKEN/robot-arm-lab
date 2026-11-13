if __name__ == '__main__':
    raise SystemExit('Use launch.ps1')

import base64
from collections import namedtuple
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import types
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[3]
OUT='outputs/isaac-sharing-gravity-v1'
SOURCE={'launch.ps1','session.py','providers.py','worker.py','settings.json','test_session.py','README.md','physics.py','robot.py'}
CORE={'code/physics.py':'physics.py','code/robot.py':'robot.py','code/session.py':'session.py','code/provider_observer.py':'providers.py','code/worker.py':'worker.py','settings.json':'settings.json'}
PURPOSES=('installation_audit','provider_diagnosis','provider_connection')
HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)
Context=namedtuple('Context','run job_hash pins job data settings cfg')

def need(ok,reason):
    if not ok:raise ValueError(reason)

def digest(raw):return hashlib.sha256(raw).hexdigest()
def sha(path):return digest(Path(path).read_bytes())
def parse(raw):
    def pairs(items):
        result={}
        for k,v in items:
            need(k not in result,'Duplicate JSON key');result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda n:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def read(path):return parse(Path(path).read_bytes().decode('utf-8-sig'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def freeze(value):
    if isinstance(value,dict):return types.MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value,list):return tuple(freeze(v) for v in value)
    return value
def plain(value):
    if isinstance(value,(dict,types.MappingProxyType)):return {k:plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain(v) for v in value]
    return value
def no_link(p):return not p.is_symlink() and not p.is_junction()
def signature(job):return digest(json.dumps(plain(job['inputs']),sort_keys=True,separators=(',',':')).encode())
def package(source):return json.dumps({n:digest(b) for n,b in sorted(source.items())},sort_keys=True).encode()
def load_module(name,raw,path):
    m=types.ModuleType('_checked065_'+name);m.__file__=str(path)
    exec(compile(raw,str(path),'exec'),m.__dict__);return m
def own_source(folder):
    need({p.name for p in folder.iterdir()}==SOURCE,'Exact source inventory')
    need(all(p.is_file() and no_link(p) for p in folder.iterdir()),'Source links/directories')
    return {n:(folder/n).read_bytes() for n in SOURCE}

def snapshot(run,job_hash,pins):
    need(sys.flags.isolated==1,'Python -I required')
    run=Path(run);need(no_link(run) and no_link(run/'job.json'),'Run/job link');run=run.resolve()
    need(all(not Path(p or '.').resolve().is_relative_to(run) for p in sys.path),'Project import search namespace')
    raw=(run/'job.json').read_bytes();need(digest(raw)==job_hash,'Pinned single-read job')
    job=parse(raw.decode('utf-8-sig'))
    need(set(job)=={'schema_version','run_id','purpose','stage','inputs','hardware_approved','profile'} and job['schema_version']==1,'Closed job schema')
    need(job['run_id']==run.name and re.fullmatch('[0-9a-f]{32}',run.name) and job['purpose'] in PURPOSES and job['stage']=='robot_connection' and job['hardware_approved'] is False,'Job authority')
    base=run/'input';need(no_link(base) and all(no_link(p) for p in base.rglob('*')),'Payload link')
    data={p.relative_to(base).as_posix():p.read_bytes() for p in base.rglob('*') if p.is_file()}
    need(set(data)==set(job['inputs']) and all(digest(v)==job['inputs'][n] for n,v in data.items()),'Exact checked payload')
    need(set(pins)=={*CORE,'source-package.json'} and all(job['inputs'][n]==h for n,h in pins.items()),'Host runtime/package authority')
    settings=parse(data['settings.json']);cfg=parse(data['config.json'])
    need(set(data)=={*CORE,'source-package.json',*settings['references']},'Complete fixed input inventory')
    need(all(job['inputs'][n]==v['sha256'] for n,v in settings['references'].items()),'Frozen reference identity')
    need(settings['limits']=={'installation_audit':900,'provider_diagnosis':300,'provider_connection':600} and settings['max_each']==1 and settings['audit_freshness_s']==300,'Fixed purpose limits')
    need((job['profile'] in ('BASELINE_CONFIRMED','PREFIX_TORCH_PREAPP') if job['purpose']=='provider_connection' else job['profile'] is None),'Fixed profile authority')
    need(cfg['hardware_approved'] is False and cfg['calibration_approved'] is False and cfg['training']=='NOT_RUN' and cfg['steps']==10 and cfg['gravity']==[0,0,0],'No physical/training authority')
    return Context(run,job_hash,freeze(pins),freeze(job),freeze(data),freeze(settings),freeze(cfg))

def frozen_api(c,sdk=False):
    k=load_module('frozen053',c.data['code/kernel.py'],c.run/'input/code/kernel.py')
    old=k.Snapshot(c.run,c.job_hash,c.pins,c.job,c.data,c.cfg)
    return k,k.api_for(old,sdk=sdk)

def legacy(c):
    raw=Path(c.settings['legacy_ledger']).read_bytes()
    need(digest(raw)==c.settings['legacy_sha256'],'Original064 ledger changed')
    value=parse(raw)
    need(set(value)=={'schema_version','legacy_063','reservations'} and value['schema_version']==1,'Original064 ledger schema')
    rows=value['reservations']
    need(type(rows) is list and len(rows)==3 and {x['purpose'] for x in rows}==set(PURPOSES),'Original064 consumed purposes')
    need({x['run_id'] for x in rows}==set(c.settings['legacy_runs']),'Original064 identities')
    return {'sha256':digest(raw),'record':value}


def records(folder,names):
    data={n:(Path(folder)/n).read_bytes() for n in names}
    return {n:parse(b.decode('utf-8-sig')) for n,b in data.items()},{n:digest(b) for n,b in data.items()}

AUDIT_RECORDS=('audit-report.json','worker-terminal.json','exit.json','remote-shell.json')
def audit_proof(folder,job,job_hash,expected_signature,settings,reference_unix=None,raws=None):
    raws={n:(Path(folder)/n).read_bytes() for n in AUDIT_RECORDS} if raws is None else raws
    values={n:parse(raws[n].decode('utf-8-sig')) for n in AUDIT_RECORDS}
    hashes={n:digest(raws[n]) for n in AUDIT_RECORDS}
    report,terminal,ex,shell=(values[n] for n in AUDIT_RECORDS)
    need(job['purpose']=='installation_audit' and signature(job)==expected_signature,'Same-input original audit purpose')
    for item in (report,terminal,ex,shell):need(item['run_id']==job['run_id'] and item['job_sha256']==job_hash,'Audit run/job binding')
    need(ex['purpose']=='installation_audit' and ex['timed_out'] is False and type(ex['actual_child_exit_code']) is int and type(shell['python_exit_code']) is int and ex['actual_child_exit_code']==ex['policy_exit_code']==shell['python_exit_code']==0,'Actual audit process/shell exit0')
    need(report['pid']==terminal['pid']==ex['child_pid'] and terminal['parent_pid']==ex['pid'] and terminal['code']==0,'Direct audit process chain')
    need(report['status']=='INSTALLATION_AUDITED' and terminal['purpose']=='installation_audit' and terminal['report_sha256']==hashes['audit-report.json'],'Complete original audit report')
    need(report['input_signature']==expected_signature and report['seal_sha256']==settings['references']['prefix-seal.json']['sha256'] and report['file_count']==39919 and report['sdk_modules']==[],'Whole sealed installation and SDK-free audit')
    reference=time.time() if reference_unix is None else reference_unix
    need(0<=reference-report['finished_unix']<=settings['audit_freshness_s'],'Recent audit completion at authorization')
    return values,hashes

def reservation(c,ledger):
    need(set(ledger)=={'schema_version','legacy_064','reservations'} and ledger['schema_version']==1,'Closed ledger')
    need(ledger['legacy_064']==legacy(c),'Original history retained')
    rows=ledger['reservations'];need(type(rows) is list and len(rows)<=3,'Bounded reservations')
    seen=set()
    for row in rows:
        need(set(row)=={'purpose','run_id','job_sha256','input_signature','reserved_unix'} and row['purpose'] in PURPOSES and row['purpose'] not in seen and re.fullmatch('[0-9a-f]{32}',row['run_id']),'Unique closed reservation')
        seen.add(row['purpose'])
    purpose=c.job['purpose'];need(purpose not in seen,'Purpose consumed; no retry')
    if purpose=='installation_audit':need(not rows,'Audit first');return None
    expected=1 if purpose=='provider_diagnosis' else 2
    need(len(rows)==expected and [r['purpose'] for r in rows]==list(PURPOSES[:expected]),'Original ordered prerequisites')
    row=rows[-1];prior=c.run.parent/row['run_id'];raw=(prior/'job.json').read_bytes();job=parse(raw)
    need(digest(raw)==row['job_sha256'] and row['input_signature']==signature(c.job) and job['run_id']==row['run_id'],'Original prerequisite job/signature')
    if purpose=='provider_diagnosis':
        raws={n:(prior/'output'/n).read_bytes() for n in AUDIT_RECORDS}
        audit_proof(prior/'output',job,row['job_sha256'],signature(c.job),c.settings,raws=raws)
        return {'directory':'audit-proof','files':{'job.json':raw,**raws,'reservation.json':json.dumps(row).encode()}}
    raws=diagnostic_bytes(prior/'output')
    report=diagnostic_proof(c,raws,job,row['job_sha256'])
    need(c.job['profile']==choose_profile(report['observation'],c.cfg),'Root-derived profile only')
    return {'directory':'diagnostic-proof','files':{'job.json':raw,**raws,'reservation.json':json.dumps(row).encode()}}


def literal(c,role):
    a={'run':str(c.run),'job':c.job_hash,'pins':plain(c.pins),'role':role}
    encoded=base64.b64encode(json.dumps(a).encode()).decode()
    text=("import base64,hashlib,json,pathlib\n"+f"a=json.loads(base64.b64decode('{encoded}'))\n"
        +"p=pathlib.Path(a['run'])/'input/code/session.py';b=p.read_bytes()\n"
        +"if hashlib.sha256(b).hexdigest()!=a['pins']['code/session.py']:raise SystemExit('Root changed')\n"
        +"n={'__name__':'_remote065','__file__':str(p)};exec(compile(b,str(p),'exec'),n)\n"
        +"raise SystemExit(n['entry'](a['run'],a['job'],a['pins'],a['role']))\n")
    return "import base64;exec(base64.b64decode('"+base64.b64encode(text.encode()).decode()+"'))"

def portable_policy(actual):
    return (actual,'WORKER_EXIT') if type(actual) is int and 0<=actual<=255 else (1,'NONPORTABLE_WORKER_EXIT')

def stop_and_reap(p,result):
    try:
        result['cleanup_exit_code']=subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=15,creationflags=HIDDEN).returncode
    except Exception as exc:result['cleanup_error']=repr(exc)
    try:result['actual_child_exit_code']=p.wait(timeout=15)
    except Exception as exc:
        result['reap_error']=repr(exc)
        try:result['actual_child_exit_code']=p.poll()
        except Exception as poll_exc:result['poll_error']=repr(poll_exc)
    result['child_state']='REAPED' if result['actual_child_exit_code'] is not None else 'RUNNING_OR_NOT_REAPED'

def run_child(argv,out,timeout):
    started=time.monotonic();p=None
    result={'child_pid':None,'actual_child_exit_code':None,'policy_exit_code':1,'policy_basis':'NOT_STARTED',
        'timed_out':False,'cleanup_exit_code':None,'child_state':'NOT_STARTED'}
    try:
        with (out/'stdout.txt').open('xb') as so,(out/'stderr.txt').open('xb') as se:
            p=subprocess.Popen(argv,stdout=so,stderr=se,creationflags=HIDDEN);result['child_pid']=p.pid
            write(out/'child-started.json',{'pid':p.pid,'started_unix':time.time()})
            try:
                result['actual_child_exit_code']=p.wait(timeout=timeout)
                result['policy_exit_code'],result['policy_basis']=portable_policy(result['actual_child_exit_code'])
                result['child_state']='REAPED'
            except subprocess.TimeoutExpired:
                result.update(timed_out=True,policy_exit_code=124,policy_basis='TIMEOUT',timeout_detected_unix=time.time())
                stop_and_reap(p,result)
    except Exception as exc:
        result['observation_error']=repr(exc)
        if not result['timed_out']:result.update(policy_exit_code=1,policy_basis='OBSERVATION_FAILURE')
        if p is not None and result['actual_child_exit_code'] is None:stop_and_reap(p,result)
    result['duration_s']=time.monotonic()-started
    return result

def supervise(c):
    need(c.run.parent==Path(c.settings['remote_root']).resolve(),'Owned remote root')
    out=c.run/'output';out.mkdir(exist_ok=True)
    if (out/'exit.json').exists():return 1
    lock=c.run.parent/'session.lock';handle=None
    ex={'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':c.job['purpose'],'pid':os.getpid(),
        'child_pid':None,'actual_child_exit_code':None,'policy_exit_code':1,'timed_out':False,'started_unix':time.time()}
    try:
        handle=lock.open('x');handle.write(str(os.getpid()));handle.flush()
        lp=c.run.parent/'session-ledger.json'
        ledger=read(lp) if lp.exists() else {'schema_version':1,'legacy_064':legacy(c),'reservations':[]}
        prior=reservation(c,ledger)
        if prior:
            ex['audit_authorized_unix' if c.job['purpose']=='provider_diagnosis' else 'diagnostic_authorized_unix']=time.time()
            ex['prerequisite_sha256']={n:digest(v) for n,v in prior['files'].items()}
            dest=out/prior['directory'];dest.mkdir()
            for n,raw in prior['files'].items():
                p=dest/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        ledger['reservations'].append({'purpose':c.job['purpose'],'run_id':c.run.name,'job_sha256':c.job_hash,
            'input_signature':signature(c.job),'reserved_unix':time.time()});write(lp,ledger)
        if c.job['purpose']!='installation_audit':
            p=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',"@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count"],capture_output=True,timeout=20,creationflags=HIDDEN)
            need(p.returncode==0 and p.stdout.strip()==b'0','Existing Kit; do not disturb')
        argv=[str(Path(c.cfg['isaac_root'])/'kit/python/python.exe'),'-I','-B','-c',literal(c,'worker')]
        ex.update(run_child(argv,out,c.settings['limits'][c.job['purpose']]))
    except Exception as exc:ex['supervisor_error']=repr(exc)
    finally:
        ex['finished_unix']=time.time();write(out/'exit.json',ex)
        if handle:handle.close();lock.unlink()
    return ex['policy_exit_code']

def entry(run,job_hash,pins,role):
    c=snapshot(run,job_hash,pins);out=c.run/'output';out.mkdir(exist_ok=True)
    if role=='supervise':return supervise(c)
    if role=='export':
        with zipfile.ZipFile(c.run/'records.zip','w',zipfile.ZIP_DEFLATED) as z:
            for p in out.rglob('*'):
                if p.is_file():z.write(p,p.relative_to(out).as_posix())
        return 0
    need(role=='worker','Closed worker role')
    terminal={'run_id':c.run.name,'job_sha256':c.job_hash,'purpose':c.job['purpose'],'pid':os.getpid(),'parent_pid':os.getppid(),'code':1,'phase':'WORKER_ENTERED'}
    write(out/'worker-phase.json',terminal)
    try:
        module='audit' if c.job['purpose']=='installation_audit' else 'worker'
        m=load_module(module,c.data['code/'+module+'.py'],c.run/'input/code'/ (module+'.py'))
        code=m.run(c,types.SimpleNamespace(**globals()))
        terminal.update(code=code,phase='FINISHED')
        if module=='audit' and code==0:terminal['report_sha256']=sha(out/'audit-report.json')
    except Exception as exc:code=1;terminal['error']=repr(exc)
    write(out/'worker-terminal.json',terminal);return code

def remote(script,alias,timeout=1000):
    encoded=base64.b64encode(script.encode('utf-16le')).decode()
    return subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15',alias,'powershell','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=timeout,creationflags=HIDDEN)

def prepare(source,purpose):
    need(purpose in PURPOSES,'Closed purpose');settings=parse(source['settings.json'])
    run=ROOT/OUT/'runs'/uuid.uuid4().hex;(run/'input/code').mkdir(parents=True)
    for key,name in CORE.items():(run/'input'/key).write_bytes(source[name])
    (run/'input/source-package.json').write_bytes(package(source))
    for key,item in settings['references'].items():
        raw=(ROOT/item['path']).read_bytes();need(digest(raw)==item['sha256'],'Frozen input changed '+key)
        target=run/'input'/key;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    files={p.relative_to(run/'input').as_posix():sha(p) for p in (run/'input').rglob('*') if p.is_file()}
    job={'schema_version':1,'run_id':run.name,'purpose':purpose,'stage':'robot_connection','inputs':files,'hardware_approved':False,'profile':None}
    if purpose=='provider_connection':job['profile']=profile_from_local(run,files,source)
    write(run/'job.json',job);pins={n:files[n] for n in (*CORE,'source-package.json')}
    c=snapshot(run,sha(run/'job.json'),pins)
    with zipfile.ZipFile(run/'bundle.zip','x',zipfile.ZIP_DEFLATED) as z:
        z.write(run/'job.json','job.json')
        for n in files:z.write(run/'input'/n,'input/'+n)
    write(run/'prepared.json',{'run_id':run.name,'job_sha256':c.job_hash,'pins':pins,'remote':settings['remote_root']+'/'+run.name,'bundle_sha256':sha(run/'bundle.zip')})
    return run

def launch(c,prepared):
    rr=prepared['remote'];alias=c.settings['ssh_alias'];need(re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+',rr) and re.fullmatch('[A-Za-z0-9_-]+',alias),'Fixed endpoint')
    p=remote("$ErrorActionPreference='Stop';if(Test-Path -LiteralPath '"+rr+"'){throw 'Run exists'};New-Item -ItemType Directory -Path '"+rr+"'|Out-Null",alias);need(p.returncode==0,'Remote create')
    p=subprocess.run(['scp','-q',str(c.run/'bundle.zip'),alias+':'+rr+'/bundle.zip'],timeout=120,creationflags=HIDDEN);need(p.returncode==0,'Upload')
    p=remote("$ErrorActionPreference='Stop';if((Get-FileHash -LiteralPath '"+rr+"/bundle.zip').Hash -ine '"+prepared['bundle_sha256']+"'){throw 'Bundle SHA'};Expand-Archive -LiteralPath '"+rr+"/bundle.zip' -DestinationPath '"+rr+"'",alias,120);need(p.returncode==0,'Expand')
    rc=c._replace(run=Path(rr));python=str(Path(c.cfg['isaac_root'])/'kit/python/python.exe')
    script="& '"+python+"' -I -B -c \""+literal(rc,'supervise')+"\";$ec=$LASTEXITCODE;if($null -eq $ec){$ec=1};$r=@{run_id='"+c.run.name+"';job_sha256='"+c.job_hash+"';python_exit_code=[int]$ec};[IO.File]::WriteAllText('"+rr+"/output/remote-shell.json',($r|ConvertTo-Json),[Text.UTF8Encoding]::new($false));exit $ec"
    p=remote(script,alias,c.settings['limits'][c.job['purpose']]+150)
    (c.run/'transport-stdout.txt').write_bytes(p.stdout);(c.run/'transport-stderr.txt').write_bytes(p.stderr)
    write(c.run/'transport.json',{'returncode':p.returncode})
    p=remote("& '"+python+"' -I -B -c \""+literal(rc,'export')+"\";exit $LASTEXITCODE",alias,120);need(p.returncode==0,'Recover original output; never rerun')
    p=subprocess.run(['scp','-q',alias+':'+rr+'/records.zip',str(c.run/'records.zip')],timeout=120,creationflags=HIDDEN);need(p.returncode==0,'Retrieve')
    dest=c.run/'retrieved';dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(c.run/'records.zip') as z:
        for n in z.namelist():
            target=(dest/n).resolve();need(target.is_relative_to(dest.resolve()),'Result archive path');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(n))

def consume(c):
    out=c.run/'retrieved';v,h=records(out,('exit.json','remote-shell.json'));ex,shell=v.values()
    for item in (ex,shell):need(item['run_id']==c.run.name and item['job_sha256']==c.job_hash,'Actual parent/shell identity')
    need(ex['purpose']==c.job['purpose'] and type(ex['pid']) is int and ex['pid']>0,'Actual parent purpose/PID')
    policy=ex['policy_exit_code'];need(type(policy) is int and 0<=policy<=255 and type(shell['python_exit_code']) is int and shell['python_exit_code']==policy,'Recorded root/shell policy code')
    transport=read(c.run/'transport.json')['returncode']
    if policy!=0:return policy,{'status':'FAILED','purpose':c.job['purpose'],'run_id':c.run.name,'parent':ex,'transport_exit_code':transport,'worker_terminal':read(out/'worker-terminal.json') if (out/'worker-terminal.json').exists() else None}
    need(transport==0 and ex['timed_out'] is False and type(ex['actual_child_exit_code']) is int and ex['actual_child_exit_code']==0,'Actual transport/worker success')
    if c.job['purpose']=='installation_audit':
        audit_proof(out,c.job,c.job_hash,signature(c.job),c.settings,ex['finished_unix'])
        return 0,{'status':'INSTALLATION_AUDIT_VERIFIED','run_id':c.run.name,'report':read(out/'audit-report.json'),'sdk_connected':False}
    if c.job['purpose']=='provider_diagnosis':
        report=diagnostic_proof(c,diagnostic_bytes(out),c.job,c.job_hash,ex['finished_unix'])
        return 0,{'status':'PROVIDER_DIAGNOSIS_VERIFIED','run_id':c.run.name,'profile':choose_profile(report['observation'],c.cfg),'torch':report['observation']['torch'],'modules':report['observation']['modules'],'sdk_connected':False}
    need(c.job['purpose']=='provider_connection','Connection purpose')
    proof=out/'diagnostic-proof';proof_raw={'job.json':(proof/'job.json').read_bytes(),'reservation.json':(proof/'reservation.json').read_bytes(),**diagnostic_bytes(proof)}
    need(set(ex['prerequisite_sha256'])==set(proof_raw) and all(ex['prerequisite_sha256'][n]==digest(v) for n,v in proof_raw.items()),'Parent-bound original diagnostic proof')
    raw=proof_raw['job.json'];prior=parse(raw);row=parse(proof_raw['reservation.json'])
    need(row['purpose']=='provider_diagnosis' and row['run_id']==prior['run_id'] and row['job_sha256']==digest(raw) and row['input_signature']==signature(c.job),'Consumed original diagnosis')
    need(ex['started_unix']<=ex['diagnostic_authorized_unix']<=ex['finished_unix'],'Observed diagnosis admission time')
    report=diagnostic_proof(c,{n:proof_raw[n] for n in proof_raw if n not in ('job.json','reservation.json')},prior,digest(raw),ex['diagnostic_authorized_unix'])
    need(c.job['profile']==choose_profile(report['observation'],c.cfg),'Same measured profile decision')
    terminal=read(out/'terminal.json')
    need(terminal['pid']==ex['child_pid'] and terminal['parent_pid']==ex['pid'] and terminal['run_id']==c.run.name and terminal['job_sha256']==c.job_hash and terminal['code']==0,'Actual native direct PID/exit')
    need(terminal['status'] in ('CLOSED','COMPLETE_PRE_CLOSE') and terminal['phase'] in ('APP_CLOSED','CLOSING_APP') and terminal['hardware_approved'] is False and terminal['physical_calibration'] is False and terminal['training']=='NOT_RUN','Native complete lifecycle/no hardware authority')
    expected={'observations.json','scene.usda','providers.json','sdk.json','physics-binding.json','clock-report.json','gravity-report.json','gravity-journal.ndjson','gravity-checkpoint.json'}
    need(set(terminal['files_sha256'])==expected,'Complete actual artifacts')
    raw={n:(out/n).read_bytes() for n in expected};need(all(digest(b)==terminal['files_sha256'][n] for n,b in raw.items()),'Actual artifact hashes')
    providers,sdk,packet=(parse(raw[n]) for n in ('providers.json','sdk.json','observations.json'))
    need(all(x['pid']==terminal['pid'] and x['job_sha256']==c.job_hash for x in (providers,sdk,packet)),'Same-process actual observations')
    physics=load_module('physics_check',c.data['code/physics.py'],c.run/'input/code/physics.py')
    physics.check(parse(raw['physics-binding.json']),c.job['run_id'],c.job_hash,terminal['pid'],c.cfg,need)
    robot_clock=load_module('clock_check',c.data['code/robot.py'],c.run/'input/code/robot.py')
    robot_clock.check_clock(parse(raw['clock-report.json']),packet['facets']['trace']['rows'],c.job['run_id'],c.job_hash,terminal['pid'],c.cfg,parse(raw['physics-binding.json']),need)
    k,api=frozen_api(c)
    need(sdk['version']==c.cfg['isaac_version'] and k.owned_origin(sdk['isaacsim_origin'],c.cfg['isaac_root']) and sdk['bootstrap_sha256']=={n:i['sha256'] for n,i in c.cfg['sdk_files'].items()},'Actual SDK identity')
    for n in ('numeric_before','numeric_after'):k.check_numeric(providers[n],c.cfg,need)
    require_observation(providers['provider_observation'],c.cfg)
    need(providers['selected_profile']==c.job['profile'],'Selected profile binding')
    binding_contract(providers['binding_before'],providers['binding_after'],c.job['profile'],providers['provider_observation'])
    k.check_frameworks(providers['frameworks'],c.cfg);metrics=k.observations(packet,api)
    robot_clock.check_journal(raw['gravity-journal.ndjson'],parse(raw['gravity-checkpoint.json']),parse(raw['gravity-report.json']),digest(raw['gravity-report.json']),need)
    gravity=robot_clock.check_gravity(parse(raw['gravity-report.json']),packet,parse(raw['clock-report.json']),api,parse(raw['physics-binding.json']))
    return (0 if gravity['dynamics_pass'] else 1),{'gravity':gravity,'gravity_steps':240,'gravity_samples':241,'status':'GRAVITY_DIAGNOSTIC_VERIFIED' if gravity['dynamics_pass'] else 'GRAVITY_DIAGNOSTIC_FAILED','run_id':c.run.name,'sdk_connected':True,'steps':10,'samples':11,'metrics':metrics,'mass_inertia':'SIMULATION_ASSUMPTION','physical_calibration':False,'training':'NOT_RUN','ring_geometry':'DEFERRED','settling_047':'UNRESOLVED'}

def local_proof(current,run,purpose):
    prepared=read(run/'prepared.json');pc=snapshot(run,prepared['job_sha256'],current.pins)
    need(pc.job['purpose']==purpose and signature(pc.job)==signature(current.job),'Local same-input purpose')
    code,result=consume(pc);need(code==0,'Original local/transport success')
    return pc,result

def admit_host(c):
    expected='installation_audit' if c.job['purpose']=='provider_diagnosis' else 'provider_diagnosis'
    for prior in c.run.parent.iterdir():
        if prior==c.run or not (prior/'prepared.json').is_file():continue
        try:
            pc,result=local_proof(c,prior,expected)
            if expected=='installation_audit':audit_proof(prior/'retrieved',pc.job,pc.job_hash,signature(c.job),c.settings)
            else:
                report=diagnostic_proof(c,diagnostic_bytes(prior/'retrieved'),pc.job,pc.job_hash)
                need(c.job['profile']==choose_profile(report['observation'],c.cfg),'Local measured profile')
            return
        except (ValueError,KeyError,OSError):continue
    raise ValueError('Original successful transport-bound fresh prerequisite required')

def profile_from_local(run,inputs,source):
    pins={n:inputs[n] for n in (*CORE,'source-package.json')}
    for prior in run.parent.iterdir():
        if prior==run or not (prior/'prepared.json').is_file():continue
        try:
            prep=read(prior/'prepared.json');pc=snapshot(prior,prep['job_sha256'],pins)
            if pc.job['purpose']!='provider_diagnosis' or signature(pc.job)!=digest(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()):continue
            code,result=consume(pc);need(code==0,'Original diagnosis success')
            report=diagnostic_proof(pc,diagnostic_bytes(prior/'retrieved'),pc.job,pc.job_hash)
            return choose_profile(report['observation'],pc.cfg)
        except (ValueError,KeyError,OSError):continue
    raise ValueError('Verified fresh diagnosis required to prepare connection')



def progress_script(c):
    path=c.settings['remote_root']+'/'+c.run.name+'/output/gravity-journal.ndjson'
    need(re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+',c.settings['remote_root']) and re.fullmatch('[0-9a-f]{32}',c.run.name),'Fixed progress endpoint')
    return """$ErrorActionPreference='Stop';$taskPath='"""+path+"""';$taskResult=@{exists=(Test-Path -LiteralPath $taskPath);snapshot_bytes=0;data_b64=''};if($taskResult.exists){$taskStream=[IO.File]::Open($taskPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete));try{$taskLength=$taskStream.Length;if($taskLength -gt 16777216){throw 'Progress snapshot too large'};$taskBuffer=New-Object byte[] ([int]$taskLength);$taskOffset=0;while($taskOffset -lt $taskLength){$taskCount=$taskStream.Read($taskBuffer,$taskOffset,[int]($taskLength-$taskOffset));if($taskCount -le 0){throw 'Progress snapshot shrank'};$taskOffset+=$taskCount};$taskResult.snapshot_bytes=$taskLength;$taskResult.data_b64=[Convert]::ToBase64String($taskBuffer)}finally{$taskStream.Dispose()}};$taskJson=$taskResult|ConvertTo-Json -Compress;[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($taskJson))"""


def progress(c):
    p=remote(progress_script(c),c.settings['ssh_alias'],30);need(p.returncode==0,'Read-only progress transport failed')
    value=parse(base64.b64decode(p.stdout.strip(),validate=True));need(type(value) is dict and set(value)=={'exists','snapshot_bytes','data_b64'} and type(value['exists']) is bool and type(value['snapshot_bytes']) is int and 0<=value['snapshot_bytes']<=16777216,'Closed progress transport')
    raw=base64.b64decode(value['data_b64'],validate=True);need(len(raw)==value['snapshot_bytes'] and (value['exists'] or not raw),'Exact bounded snapshot bytes')
    module=load_module('progress_reader',c.data['code/robot.py'],c.run/'input/code/robot.py')
    result=module.journal_progress(raw,c.run.name,c.job_hash,need);result['exists']=value['exists']
    write(c.run/'progress.json',result);return result


def public(role,run_dir='',purpose=''):
    source=own_source(Path(__file__).resolve().parent)
    if role=='test':
        m=load_module('tests',source['test_session.py'],Path(__file__).parent/'test_session.py')
        return m.run_tests(types.SimpleNamespace(**globals()),source)
    if role=='prepare':print(prepare(source,purpose));return 0
    need(role in ('run','verify','progress'),'Closed public role');run=Path(run_dir).resolve();prepared=read(run/'prepared.json')
    pins={n:digest(source[v]) for n,v in CORE.items()};pins['source-package.json']=digest(package(source))
    c=snapshot(run,prepared['job_sha256'],pins)
    need(prepared['pins']==pins and prepared['remote']==c.settings['remote_root']+'/'+run.name and prepared['run_id']==run.name,'Current source preparation binding')
    if role=='progress':
        try:print(json.dumps(progress(c)));return 0
        except Exception as exc:print(json.dumps({'status':'PROGRESS_READ_FAILED','run_id':c.run.name,'error':repr(exc),'acceptance':False}));return 1
    try:
        if role=='run':
            if c.job['purpose']!='installation_audit':admit_host(c)
            launch(c,prepared)
        code,result=consume(c);write(run/'validation.json',result);write(run.parent.parent/'current.json',result);print(json.dumps(result));return code
    except Exception as exc:
        result={'status':'FAILED','run_id':run.name,'purpose':c.job['purpose'],'reason':repr(exc),'sdk_connected':False}
        write(run/'validation.json',result);write(run.parent.parent/'current.json',result);print(json.dumps(result));return 1

BOUND={'torch': {'name': 'torch', 'version': '2.11.0+cu130', 'dist_dir': 'torch-2.11.0+cu130.dist-info', 'files': {'torch/__init__.py': '9805fe98af34a65b1ab758c7909cc7b9906f40777257e513968545b19e319aa1', 'torch-2.11.0+cu130.dist-info/METADATA': 'bd2fe854330a995245c5866a81ec406eb8522474a89af48609a56f69e6bcd247', 'torch-2.11.0+cu130.dist-info/RECORD': '9161511aa33196c8002a54b99360fdd73123dc63c01ba9de43fe48af1b8bc432'}}, 'torchvision': {'name': 'torchvision', 'version': '0.26.0+cu130', 'dist_dir': 'torchvision-0.26.0+cu130.dist-info', 'files': {'torchvision/__init__.py': 'd98be1bb51d14749dc9718d27d42cd4250203e6276d0e90ab6021aac807a4735', 'torchvision-0.26.0+cu130.dist-info/METADATA': '6f44a49a81fcca1e47644d2b3dc9b93b542983eeee0977db66a66ffa1fc56285', 'torchvision-0.26.0+cu130.dist-info/RECORD': '0ebe1de77ccff04a64a5f3456e6b28a289ec18b053b79b3644c004fb01a6ed3e'}}}
EXPECTED={'torch':'2.11.0+cu130','torchvision':'0.26.0+cu130','isaaclab':'3.0.0','warp':'1.17.0','gymnasium':'1.4.0','rsl_rl':'5.5.1','numpy':'2.3.1','scipy':'1.17.0'}
TORCH_FIELDS={'state','origin','module_version','module_id','cuda_build','version_origin','c_extension_origin','availability','availability_error','gpu','gpu_error','loaded_torch_modules'}
TORCH_FIELDS|={'torch_inventory','fileless_torch_modules','torch_module_count','inventory_scope'}
INVENTORY_ROW={'module_id','reported_file','spec_origin','loader_module','loader_qualname','type_module','type_qualname','type_definition_origin','type_definition_module_id','type_is_definition'}
def canonical(value,root):
    if type(value) is not str or not value or any(p in ('.','..') for p in re.split(r'[\\/]',value)):return False
    try:return Path(value).is_absolute() and Path(value).resolve().is_relative_to(Path(root).resolve())
    except OSError:return False

def absolute_file(value):
    return type(value) is str and bool(value) and Path(value).is_absolute() and not any(p in ('.','..') for p in re.split(r'[\\/]',value))

def same_file(a,b):return absolute_file(a) and absolute_file(b) and Path(a).resolve()==Path(b).resolve()

def check_inventory(t):
    files,rows,fileless=t['loaded_torch_modules'],t['torch_inventory'],t['fileless_torch_modules']
    need(type(files) is dict and type(rows) is dict and set(files)==set(rows) and files.get('torch')==t['origin'],'Exact file-reported Torch inventory')
    need(type(fileless) is dict and not set(fileless)&set(rows) and type(t['torch_module_count']) is int and t['torch_module_count']==len(rows)+len(fileless),'Complete observed partition count')
    need(t['inventory_scope']=='FILE_REPORTED_TORCH_MODULES','Explicit inventory scope')
    for name in (*rows,*fileless):need(type(name) is str and (name=='torch' or name.startswith('torch.')),'Torch inventory name')
    for ident in fileless.values():need(type(ident) is int and ident>0,'Observed fileless identity only')
    need(rows['torch']['module_id']==t['module_id'],'Inventory identifies actual Torch object')
    namespaces={'torch.ops':('torch._ops','_Ops','_ops.py'),'torch.classes':('torch._classes','_Classes','_classes.py')}
    need(not set(fileless)&set(namespaces),'Reserved namespaces cannot be fileless')
    for name,row in rows.items():
        need(type(row) is dict and set(row)==INVENTORY_ROW and row['reported_file']==files[name],'Exact typed row and original raw file')
        need(type(row['module_id']) is int and row['module_id']>0 and type(row['type_is_definition']) is bool,'Measured row identity/class relation')
        need(all(type(row[k]) is str and bool(row[k]) for k in ('type_module','type_qualname')),'Actual object type')
        for key in ('spec_origin','loader_module','loader_qualname','type_definition_origin'):
            need(row[key] is None or (type(row[key]) is str and bool(row[key])),'Nullable raw metadata '+key)
        need((row['loader_module'] is None)==(row['loader_qualname'] is None),'Complete loader type pair')
        need(row['type_definition_module_id'] is None or (type(row['type_definition_module_id']) is int and row['type_definition_module_id']>0),'Nullable definition identity')
        if name not in namespaces and absolute_file(row['reported_file']):
            need(row['spec_origin'] is None or same_file(row['reported_file'],row['spec_origin']),'File/spec origins agree')
            continue
        need(name in namespaces,'Unknown relative file-reported Torch object')
        module,qualname,marker=namespaces[name]
        need(row['reported_file']==marker and row['type_module']==module and row['type_qualname']==qualname and row['type_is_definition'] is True and row['spec_origin'] is None,'Measured dynamic namespace type')
        need(module in rows,'Observed dynamic type definition module')
        definition=rows[module]
        need(definition['module_id']==row['type_definition_module_id'] and same_file(definition['reported_file'],row['type_definition_origin']),'Same measured definition object and file')
        need(same_file(row['type_definition_origin'],str(Path(t['origin']).parent/marker)),'Definition file beside actual Torch')
    return [row['reported_file'] for row in rows.values() if absolute_file(row['reported_file'])]

def bound_contract(name,item):
    need({'ambient_metadata','bound_state','bound_proof','bound_error'}<=set(item),'Complete bound metadata observation')
    ambient=item['ambient_metadata'];need(type(ambient) is dict and set(ambient)=={'version','root','error'},'Ambient metadata preserved')
    if item['bound_state']=='ERROR':
        need(item['bound_proof'] is None and type(item['bound_error']) is str and bool(item['bound_error']) and item['distribution_version'] is None and item['distribution_root'] is None,'Explicit bound failure without ambient fallback');return
    need(item['bound_state']=='VERIFIED' and item['bound_error'] is None,'Verified bound state')
    proof=item['bound_proof'];pin=BOUND[name]
    need(type(proof) is dict and set(proof)=={'name','version','root','module_relative','files'},'Complete bound proof')
    need(proof['name']==name and proof['version']==pin['version'] and proof['files']==pin['files'] and proof['module_relative']==name+'/__init__.py','Pinned metadata and module hashes')
    need(same_file(item['origin'],str(Path(proof['root'])/proof['module_relative'])) and absolute_file(proof['root']),'Metadata owns actual module')
    need(item['distribution_root']==proof['root'] and item['distribution_version']==proof['version'] and item['version']==proof['version'],'Bound root/version agrees')

def diagnostic_observation(value):
    need(set(value)=={'modules','torch','sys_path'} and set(value['modules'])==set(EXPECTED),'Complete measured module/error inventory')
    for n,item in value['modules'].items():
        need(item['status'] in ('OBSERVED','IMPORT_ERROR'),'Measured module status')
        if item['status']=='IMPORT_ERROR':need(type(item['error']) is str and bool(item['error']),'Explicit module import error')
        else:
            if n in BOUND:bound_contract(n,item)
            need({'origin','version','module_id','distribution_version','distribution_root'}<=set(item),'Complete observed module record')
            need(type(item['origin']) is str and Path(item['origin']).is_absolute() and type(item['module_id']) is int and item['module_id']>0,'Actual observed module identity')
            need((type(item['version']) is str and bool(item['version'])) or (item['version'] is None and bool(item.get('metadata_error'))),'Version observation or explicit metadata error')
    t=value['torch'];need(type(t) is dict and TORCH_FIELDS<=set(t),'Every mandatory Torch observation field')
    need(t['state']=='OBSERVED' and type(t['origin']) is str and Path(t['origin']).is_absolute() and type(t['module_version']) is str and bool(t['module_version']) and type(t['module_id']) is int and t['module_id']>0,'Actual Torch identity required')
    need(t['cuda_build'] is None or (type(t['cuda_build']) is str and bool(t['cuda_build'])),'Explicit CPU/CUDA build observation')
    need(all(type(t[n]) is str and Path(t[n]).is_absolute() for n in ('version_origin','c_extension_origin')),'Actual version and C-extension origins')
    check_inventory(t)
    need(type(t['availability']) is bool or (t['availability'] is None and type(t['availability_error']) is str and bool(t['availability_error'])),'Actual availability or explicit probe error')
    if type(t['availability']) is bool:need(t['availability_error'] is None,'No contradictory availability error')
    need(t['gpu_error'] is None or (type(t['gpu_error']) is str and bool(t['gpu_error'])),'Explicit GPU probe error')
    if t['availability'] is True:
        if 'device_details_error' in t:
            need(type(t['device_details_error']) is str and bool(t['device_details_error']),'Explicit device-details query error')
        else:
            need({'device_count','device_name','capability'}<=set(t),'Complete CUDA device observations')
            need(type(t['device_count']) is int and t['device_count']>0 and type(t['device_name']) is str and bool(t['device_name']),'Measured device count/name')
            need(type(t['capability']) is list and len(t['capability'])==2 and all(type(v) is int and v>=0 for v in t['capability']),'Measured compute capability')
        need((type(t['gpu']) is dict and set(t['gpu'])=={'is_cuda','device','sum'} and type(t['gpu']['is_cuda']) is bool and type(t['gpu']['device']) is str and type(t['gpu']['sum']) in (int,float) and t['gpu_error'] is None) or (t['gpu'] is None and t['gpu_error'] is not None),'GPU result or explicit failed probe')
    else:need(t['gpu'] is None and t['gpu_error'] is None,'Unavailable GPU has no invented result/probe')
    m=value['modules']['torch'];need(m['status']=='OBSERVED' and m['origin']==t['origin'] and m['version']==t['module_version'] and m['module_id']==t['module_id'],'Same observed Torch object')

def require_torch(t,cfg):
    files=check_inventory(t)
    need(all(canonical(t[n],cfg['installation_prefix']) for n in ('origin','version_origin','c_extension_origin')) and t['module_version']=='2.11.0+cu130','Canonical prefix Torch/version/C extension')
    need(t['availability'] is True and type(t['cuda_build']) is str and t['cuda_build'].startswith('13.'),'Measured Torch CUDA13')
    gpu=t['gpu'];need(type(gpu) is dict and gpu['is_cuda'] is True and gpu['device']=='cuda:0' and gpu['sum']==6,'Actual Torch GPU calculation')
    need(all(canonical(p,cfg['installation_prefix']) for p in files),'Single file-backed Torch provider')

def require_observation(value,cfg):
    diagnostic_observation(value);require_torch(value['torch'],cfg)
    for name,version in EXPECTED.items():
        item=value['modules'][name];root=cfg[name+'_root'] if name in ('numpy','scipy','warp') else cfg['installation_prefix']
        need(item['status']=='OBSERVED' and item['version']==version and canonical(item['origin'],root),'Intended framework provider '+name)
        if name not in ('numpy','scipy'):
            if name in BOUND:need(item['bound_state']=='VERIFIED','Bound metadata required '+name)
            need(item['distribution_version']==version,'Intended distribution version '+name)
            if name!='warp':need(canonical(item['distribution_root'],cfg['installation_prefix']),'Intended distribution root '+name)

def choose_profile(value,cfg):
    diagnostic_observation(value)
    try:require_observation(value,cfg);return 'BASELINE_CONFIRMED'
    except (ValueError,KeyError,TypeError):return 'PREFIX_TORCH_PREAPP'

def binding_contract(before,after,profile,observation):
    names={'numpy','scipy','warp','torch','torchvision'};need(set(before)==set(after)==names,'Complete object binding inventory')
    for n in names:
        need(type(after[n]) is int and after[n]>0,'Actual post-app module object')
        observed=observation['modules'][n]
        need(observed['status']=='OBSERVED' and type(observed['module_id']) is int and observed['module_id']==after[n],'Binding identifies observed module '+n)
        if n in ('numpy','scipy') or profile=='PREFIX_TORCH_PREAPP':need(type(before[n]) is int and before[n]>0,'Required pre-app module object')
        if before[n] is not None:need(before[n]==after[n],'Module object replaced across app '+n)

DIAG_RECORDS=('diagnosis-report.json','diagnostic-terminal.json','exit.json','remote-shell.json','sdk.json')
PROOF_AUDIT=('job.json',*AUDIT_RECORDS,'reservation.json')
def diagnostic_bytes(folder):
    folder=Path(folder);raws={n:(folder/n).read_bytes() for n in DIAG_RECORDS}
    raws.update({'audit-proof/'+n:(folder/'audit-proof'/n).read_bytes() for n in PROOF_AUDIT})
    return raws

def diagnostic_proof(c,raws,job,job_hash,reference_unix=None):
    need(job['purpose']=='provider_diagnosis' and signature(job)==signature(c.job),'Original same-input diagnostic purpose')
    values={n:parse(raws[n]) for n in DIAG_RECORDS};report,terminal,ex,shell,sdk=(values[n] for n in DIAG_RECORDS)
    for item in (report,terminal,ex,shell):need(item['run_id']==job['run_id'] and item['job_sha256']==job_hash,'Diagnostic original run/job binding')
    need(sdk['job_sha256']==job_hash,'Diagnostic SDK job binding')
    need(ex['purpose']=='provider_diagnosis' and ex['timed_out'] is False and type(ex['actual_child_exit_code']) is int and type(shell['python_exit_code']) is int and ex['actual_child_exit_code']==ex['policy_exit_code']==shell['python_exit_code']==terminal['code']==0,'Actual diagnostic process/shell/terminal success')
    need(type(ex['child_pid']) is int and ex['child_pid']>0 and report['pid']==sdk['pid']==terminal['pid']==ex['child_pid'] and terminal['parent_pid']==ex['pid'],'Direct diagnostic PID chain')
    need(terminal['purpose']=='provider_diagnosis' and terminal['status']=='DIAGNOSIS_COMPLETE_PRE_CLOSE' and terminal['phase']=='CLOSING_APP' and terminal['hardware_approved'] is False and terminal['training']=='NOT_RUN','Scoped diagnostic completion')
    need(set(terminal['files_sha256'])=={'diagnosis-report.json','sdk.json'} and all(digest(raws[n])==h for n,h in terminal['files_sha256'].items()),'Original diagnostic artifacts')
    need(report['status']=='PROVIDER_DIAGNOSIS_COMPLETE' and report['input_signature']==signature(c.job) and report['hardware_approved'] is False and report['training']=='NOT_RUN','Complete observation only, no hardware authority')
    proof={n:raws['audit-proof/'+n] for n in PROOF_AUDIT}
    need(set(ex['prerequisite_sha256'])==set(proof) and all(ex['prerequisite_sha256'][n]==digest(v) for n,v in proof.items()),'Parent-bound complete nested audit proof')
    old=parse(proof['job.json']);row=parse(proof['reservation.json'])
    need(row['purpose']=='installation_audit' and row['run_id']==old['run_id'] and row['job_sha256']==digest(proof['job.json']) and row['input_signature']==signature(c.job),'Original nested audit reservation')
    need(ex['started_unix']<=ex['audit_authorized_unix']<=ex['finished_unix'],'Actual audit authorization time')
    audit_proof(None,old,row['job_sha256'],signature(c.job),c.settings,ex['audit_authorized_unix'],{n:proof[n] for n in AUDIT_RECORDS})
    k=load_module('pure053',c.data['code/kernel.py'],c.run/'input/code/kernel.py')
    need(sdk['version']==c.cfg['isaac_version'] and canonical(sdk['isaacsim_origin'],c.cfg['isaac_root']) and sdk['bootstrap_sha256']=={n:v['sha256'] for n,v in c.cfg['sdk_files'].items()},'Measured diagnostic SDK identity')
    for n in ('numeric_before','numeric_after'):k.check_numeric(report[n],c.cfg,need)
    diagnostic_observation(report['observation'])
    reference=time.time() if reference_unix is None else reference_unix
    need(0<=reference-report['finished_unix']<=c.settings['audit_freshness_s'],'Recent diagnosis at connection authorization')
    return report
