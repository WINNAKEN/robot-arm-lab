"""048 closed-set bootstrap; standalone stdlib until every payload byte is checked."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[3]
PAYLOAD=frozenset(('setup.py','native_probe.py','config.json','frames.py','extract_usd.py','input.usda','kinematics.json','baseline.json'))
PYTHON_FILES=frozenset(x for x in PAYLOAD if x.endswith('.py'))
OUT='outputs/isaac-lab-recovery-v1'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    def invalid(x):raise ValueError('Nonfinite JSON: '+x)
    return json.loads(Path(p).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)


def write(p,value):
    Path(p).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def verify_payload(run,expected_job):
    run=Path(run).resolve();need(sha(run/'job.json')==expected_job,'Host-pinned job changed')
    job=read(run/'job.json')
    need(set(job)=={'run_id','files_sha256','hardware_approved'} and re.fullmatch('[0-9a-f]{32}',job['run_id']) and job['run_id']==run.name,'Job schema/identity')
    need(job['hardware_approved'] is False and set(job['files_sha256'])==PAYLOAD,'Exact complete fixed payload inventory required')
    need({p.name for p in run.glob('*.py')}==PYTHON_FILES,'Unknown or missing executable Python input')
    for name in sorted(PAYLOAD):need(sha(run/name)==job['files_sha256'][name],'Unapproved payload bytes: '+name)
    return job


def tree(prefix):
    prefix=Path(prefix).resolve();result={}
    for p in sorted(prefix.rglob('*')):
        need(not p.is_symlink(),'Prefix symlink outside seal model')
        if p.is_file():result[p.relative_to(prefix).as_posix()]=sha(p)
    return result


def verify_seal(prefix,seal,expected):
    need(sha(seal)==expected,'Host-pinned prefix seal changed')
    value=read(seal);need(set(value)=={'schema_version','files'} and type(value['schema_version']) is int and value['schema_version']==1,'Prefix seal schema')
    need(value['files']==tree(prefix),'Exact installed file inventory/bytes changed')


def shim(run,job_sha,role,seal_sha=None):
    """Trusted caller pins setup AND job before runpy can execute any project code."""
    run=Path(run);setup_sha=sha(run/'setup.py')
    args=[str(run/'setup.py'),role,'--run-dir',str(run),'--expected-job',job_sha]
    if seal_sha:args+=['--expected-seal',seal_sha]
    code=("import hashlib,pathlib,runpy,sys\n"
          f"p=pathlib.Path({str(run/'setup.py')!r});j=pathlib.Path({str(run/'job.json')!r})\n"
          f"if hashlib.sha256(p.read_bytes()).hexdigest()!={setup_sha!r} or hashlib.sha256(j.read_bytes()).hexdigest()!={job_sha!r}:raise SystemExit('Trusted root identity mismatch')\n"
          f"sys.argv={args!r}\nrunpy.run_path(str(p),run_name='__main__')\n")
    encoded=base64.b64encode(code.encode()).decode()
    return "import base64;exec(base64.b64decode('"+encoded+"'))"


def remote_shim(run,job_sha,role,setup_sha,seal_sha=None):
    # Same root verifier with host-owned hashes and the remote owned directory.
    args=[str(run/'setup.py'),role,'--run-dir',str(run),'--expected-job',job_sha]
    if seal_sha:args+=['--expected-seal',seal_sha]
    code=("import hashlib,pathlib,runpy,sys\n"
        f"p=pathlib.Path({str(run/'setup.py')!r});j=pathlib.Path({str(run/'job.json')!r})\n"
        f"if hashlib.sha256(p.read_bytes()).hexdigest()!={setup_sha!r} or hashlib.sha256(j.read_bytes()).hexdigest()!={job_sha!r}:raise SystemExit('Trusted root identity mismatch')\n"
        f"sys.argv={args!r}\nrunpy.run_path(str(p),run_name='__main__')\n")
    return "import base64;exec(base64.b64decode('"+base64.b64encode(code.encode()).decode()+"'))"


def runtime_config(run):
    cfg=read(run/'config.json')
    need(cfg['schema_version']==1 and cfg['hardware_approved'] is False and cfg['physical_calibration'] is False and cfg['training']=='NOT_RUN','Simulation-only config')
    need(cfg['native_scope']=='STATIC_ONLY_NO_RESET_NO_STEP' and cfg['install_timeout_s']==1800 and cfg['probe_timeout_s']==600 and cfg['native_attempts_max']==2,'Frozen finite static-only scope')
    need(cfg['wheel']['filename']=='isaaclab-3.0.0-py3-none-any.whl' and cfg['wheel']['sha256']=='625f752c7dd912eb8efade85daeb7a8119d620266852380d17d8f9e701b80bca','Approved Lab wheel')
    need(cfg['wheel']['url'].startswith('https://files.pythonhosted.org/'),'Official wheel host')
    need({'torch==2.11.0+cu130','torchvision==0.26.0+cu130','warp-lang==1.17.0'}<=set(cfg['requirements']),'Pinned CUDA/Lab versions')
    need(Path(run).resolve().parent==Path(cfg['remote_root']).resolve(),'Owned remote run root')
    need((Path(cfg['isaac_root'])/'VERSION').read_text(encoding='utf-8-sig').strip()==cfg['isaac_version'],'Existing Isaac changed')
    return cfg


def child(argv,run,name,timeout,env=None):
    process=None;started=time.time();code=1
    try:
        with (run/(name+'-stdout.txt')).open('xb') as so,(run/(name+'-stderr.txt')).open('xb') as se:
            process=subprocess.Popen(argv,stdout=so,stderr=se,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            write(run/(name+'-process.json'),{'status':'RUNNING','pid':process.pid,'supervisor_pid':os.getpid(),'started_unix':started,'argv':argv})
            try:code=process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                cleanup=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                write(run/(name+'-timeout.json'),{'owned_pid':process.pid,'cleanup_exit':cleanup.returncode});process.wait(timeout=15);code=124
    finally:
        write(run/(name+'-exit.json'),{'exit_code':int(code),'child_pid':process.pid if process else None,'supervisor_pid':os.getpid(),'started_unix':started,'finished_unix':time.time()})
    need(code==0,name+' failed, exit '+str(code))


def install(run,cfg):
    prefix=run/'packages';prefix.mkdir(exist_ok=False)
    wheel=run/cfg['wheel']['filename']
    with urllib.request.urlopen(cfg['wheel']['url'],timeout=90) as response:wheel.write_bytes(response.read())
    need(sha(wheel)==cfg['wheel']['sha256'],'Downloaded Lab wheel identity')
    python=Path(cfg['isaac_root'])/'kit/python/python.exe';deadline=time.monotonic()+cfg['install_timeout_s']
    common=[str(python),'-I','-B','-m','pip','install','--disable-pip-version-check','--no-input','--target',str(prefix)]
    child(common+['--report',str(run/'pip-dependencies.json'),'--extra-index-url','https://download.pytorch.org/whl/cu130',*cfg['requirements']],run,'pip-dependencies',max(1,deadline-time.monotonic()))
    child(common+['--no-deps','--report',str(run/'pip-lab.json'),str(wheel)],run,'pip-lab',max(1,deadline-time.monotonic()))
    write(run/'prefix-seal.json',{'schema_version':1,'files':tree(prefix)})
    write(run/'install-result.json',{'status':'INSTALL_DATA_CAPTURED','run_id':run.name,'pid':os.getpid(),'prefix':str(prefix),
        'job_sha256':sha(run/'job.json'),'seal_sha256':sha(run/'prefix-seal.json'),'wheel_sha256':sha(wheel),'hardware_approved':False})


def probe(run,cfg,job_sha,seal_sha,native=False):
    verify_seal(run/'packages',run/'prefix-seal.json',seal_sha)
    role='native' if native else 'modules';attempts=run/'native-attempts.json'
    if native:
        rows=read(attempts) if attempts.is_file() else []
        need(type(rows) is list and len(rows)<2,'Native probe budget exhausted')
        rows.append({'reserved_unix':time.time(),'role':role});write(attempts,rows)
        existing=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',"@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count"],capture_output=True,timeout=20)
        need(existing.returncode==0 and existing.stdout.strip()==b'0','Existing Kit session or failed process query')
    code=(f"import pathlib,hashlib,runpy,sys\nr=pathlib.Path({str(run)!r})\n"
          f"if hashlib.sha256((r/'setup.py').read_bytes()).hexdigest()!={sha(run/'setup.py')!r}:raise SystemExit('Setup root changed')\n"
          "sys.path.insert(0,str(r))\nfrom setup import verify_payload,verify_seal\n"
          f"verify_payload(r,{job_sha!r});verify_seal(r/'packages',r/'prefix-seal.json',{seal_sha!r})\n"
          f"sys.argv=[str(r/'native_probe.py'),{role!r},str(r)]\nrunpy.run_path(str(r/'native_probe.py'),run_name='__main__')\n")
    encoded="import base64;exec(base64.b64decode('"+base64.b64encode(code.encode()).decode()+"'))"
    python=Path(cfg['isaac_root'])/'kit/python/python.exe';env=os.environ.copy();env['PYTHONEXE']=str(python)
    argv=[str(python),'-I','-B','-c',encoded]
    if native:argv=[env['COMSPEC'],'/d','/c',str(Path(cfg['isaac_root'])/'python.bat'),'-I','-B','-c',encoded]
    child(argv,run,role,cfg['probe_timeout_s'],env)


def records(run):
    target=run/'records.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in run.iterdir():
            if p.is_file() and p.suffix in ('.json','.txt') and p.name not in ('kinematics.json','baseline.json'):
                archive.write(p,p.name)


def remote(script,alias,timeout=2000):
    encoded=base64.b64encode(script.encode('utf-16le')).decode()
    done=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=10',alias,'powershell','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=timeout)
    need(done.returncode==0,'SSH returned '+str(done.returncode)+': '+done.stderr.decode('utf-8',errors='replace'))
    return done.stdout


def prepare(root=ROOT):
    root=Path(root);out=root/OUT;out.mkdir(parents=True,exist_ok=True);rid=uuid.uuid4().hex;run=out/'runs'/rid;run.mkdir(parents=True,exist_ok=False)
    write(out/'current.json',{'status':'BUILDING','run_id':rid,'hardware_approved':False})
    try:
        source=root/'src/simulation/lab_connection';cfg=read(source/'config.json')
        for name in ('setup.py','native_probe.py','config.json'):shutil.copyfile(source/name,run/name)
        for name,value in cfg['references'].items():
            need(sha(root/value['path'])==value['sha256'],'Approved input changed: '+name);shutil.copyfile(root/value['path'],run/name)
        need({p.name for p in run.iterdir()}==PAYLOAD,'Preparation inventory')
        job={'run_id':rid,'hardware_approved':False,'files_sha256':{name:sha(run/name) for name in sorted(PAYLOAD)}}
        write(run/'job.json',job);verify_payload(run,sha(run/'job.json'))
        with zipfile.ZipFile(run/'bundle.zip','x',zipfile.ZIP_DEFLATED) as z:
            for name in [*sorted(PAYLOAD),'job.json']:z.write(run/name,name)
        write(run/'prepared.json',{'run_id':rid,'remote_run_dir':cfg['remote_root']+'/'+rid,'job_sha256':sha(run/'job.json'),'setup_sha256':sha(run/'setup.py'),'bundle_sha256':sha(run/'bundle.zip')})
        return run
    except Exception as e:
        write(out/'current.json',{'status':'FAILED','run_id':rid,'reason':repr(e),'hardware_approved':False});raise


def launch(local,role):
    local=Path(local);p=read(local/'prepared.json');cfg=read(local/'config.json');rr=Path(p['remote_run_dir']);alias=cfg['ssh_alias']
    need(re.fullmatch('[A-Za-z0-9_-]+',alias) and re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+',p['remote_run_dir']),'Safe remote endpoint')
    if role=='install':
        remote("$ErrorActionPreference='Stop'; if(Test-Path -LiteralPath '"+str(rr)+"') { throw 'Owned run exists' }; New-Item -ItemType Directory -Path '"+str(rr)+"' | Out-Null",alias)
        done=subprocess.run(['scp','-q',str(local/'bundle.zip'),alias+':'+str(rr)+'/bundle.zip'],timeout=120);need(done.returncode==0,'Bundle transfer failed')
        remote("$ErrorActionPreference='Stop'; if((Get-FileHash -LiteralPath '"+str(rr/ 'bundle.zip')+"').Hash -ine '"+p['bundle_sha256']+"') { throw 'Bundle SHA' }; Expand-Archive -LiteralPath '"+str(rr/'bundle.zip')+"' -DestinationPath '"+str(rr)+"'",alias)
    seal=sha(local/'retrieved/prefix-seal.json') if role!='install' else None
    bootstrap=remote_shim(rr,p['job_sha256'],role,p['setup_sha256'],seal)
    py=str(Path(cfg['isaac_root'])/'kit/python/python.exe')
    script="$ProgressPreference='SilentlyContinue'; & '"+py+"' -I -B -c \""+bootstrap+"\"; exit $LASTEXITCODE"
    error=None
    try:remote(script,alias)
    except Exception as e:error=e
    # Recover reports without rerunning an uncertain installation/probe.
    export=remote_shim(rr,p['job_sha256'],'records',p['setup_sha256'])
    remote("& '"+py+"' -I -B -c \""+export+"\"; exit $LASTEXITCODE",alias,120)
    done=subprocess.run(['scp','-q',alias+':'+str(rr/'records.zip'),str(local/'records.zip')],timeout=120);need(done.returncode==0,'Records retrieval failed')
    dest=local/'retrieved';dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(local/'records.zip') as z:
        for name in z.namelist():need(Path(name).name==name,'Unsafe records path');(dest/name).write_bytes(z.read(name))
    if error:raise error
    return dest


def evaluate(local,role):
    local=Path(local);p=read(local/'prepared.json');verify_payload(local,p['job_sha256']);r=local/'retrieved'
    result=read(r/(('install' if role=='install' else role)+'-result.json'))
    need(result['run_id']==local.name and result['job_sha256']==p['job_sha256'] and result['hardware_approved'] is False,'Result identity/authority')
    if role=='install':
        need(result['status']=='INSTALL_DATA_CAPTURED' and result['seal_sha256']==sha(r/'prefix-seal.json'),'Installation seal binding')
        need(result['wheel_sha256']==read(local/'config.json')['wheel']['sha256'],'Installed Lab wheel')
        for name in ('pip-dependencies','pip-lab'):
            ex=read(r/(name+'-exit.json'));need(type(ex['exit_code']) is int and ex['exit_code']==0,'Installer child exit')
    else:
        ex=read(r/(role+'-exit.json'));need(type(ex['exit_code']) is int and ex['exit_code']==0,'Actual probe child exit')
        need(type(result['pid']) is int and result['pid']>0,'Actual probe PID')
        if role=='modules':
            need(result['status']=='MODULE_GPU_DATA_CAPTURED' and result['pid']==ex['child_pid'],'Module PID/status')
            need(result['cuda'].startswith('13.') and result['tensor_device']=='cuda:0' and result['tensor_sum']==6,'Actual CUDA GPU operation')
            expected={'isaaclab':'3.0.0','torch':'2.11.0+cu130','torchvision':'0.26.0+cu130','warp':'1.17.0','rsl_rl':'5.5.1'}
            need(set(result['modules'])==set(expected)|{'gymnasium'},'Exact module observation set')
            prefix=(Path(p['remote_run_dir'])/'packages').resolve()
            for name,value in result['modules'].items():
                need(Path(value['origin']).resolve().is_relative_to(prefix),'Foreign module origin')
                if name in expected:need(value['version']==expected[name],'Unexpected module version: '+name)
            major,minor,*_=result['modules']['gymnasium']['version'].split('.')
            need(major=='1' and int(minor)>=2,'Gym version range')
        else:
            need(result['status']=='LAB_STATIC_MODEL_CONNECTION_DATA_CAPTURED' and result['parent_pid']==ex['child_pid'],'Native PID/status')
            need(result['model_sha256']==read(local/'job.json')['files_sha256']['input.usda'],'Native model bytes')
            need(result['scope']=='STATIC_ONLY_NO_RESET_NO_STEP' and type(result['steps']) is int and result['steps']==0 and result['gravity_m_s2']==[0.,0.,0.],'Static-only native scope')
            need(result['dof_names']==[f'J{i}' for i in range(1,7)] and result['links']==7 and result['colliders']==7,'Native model cardinality')
            need(result['snapshot_sha256']==sha(r/'lab-static-snapshot.json'),'Native observed snapshot bytes')
            need(type(result['max_zero_frame_error']) in (int,float) and 0<=result['max_zero_frame_error']<=1e-6 and 'physx' in result['manager'].lower(),'Native zero frame/manager')
            need(result['physical_calibration'] is False and result['weights'] is None and result['dynamic_connection']=='NOT_RUN','No dynamic/physical escalation')
    return {'status':{'install':'MINIMAL_RUNTIME_INSTALLED','modules':'MODULE_GPU_VERIFIED','native':'LAB_STATIC_MODEL_CONNECTED'}[role],
        'run_id':local.name,'role':role,'source_result_sha256':sha(r/(role+'-result.json')),'native_dynamics':'NOT_RUN','training':'NOT_RUN','hardware_approved':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('role',choices=('prepare','launch-install','launch-modules','launch-native','verify-install','verify-modules','verify-native','install','modules','native','records'))
    parser.add_argument('--run-dir',type=Path);parser.add_argument('--expected-job');parser.add_argument('--expected-seal');args=parser.parse_args()
    if args.role=='prepare':print(prepare());return
    need(args.run_dir is not None,'Explicit run directory');run=args.run_dir.resolve()
    if args.role.startswith(('launch-','verify-')):
        try:
            if args.role.startswith('launch-'):launch(run,args.role[7:])
            result=evaluate(run,args.role.split('-',1)[1]);write(run.parent.parent/'current.json',result);print(json.dumps(result))
        except Exception as e:
            write(run.parent.parent/'current.json',{'status':'FAILED','run_id':run.name,'role':args.role,'reason':repr(e),'hardware_approved':False});raise
        return
    verify_payload(run,args.expected_job)
    if args.role=='records':records(run);return
    cfg=runtime_config(run)
    try:
        if args.role=='install':install(run,cfg)
        else:probe(run,cfg,args.expected_job,args.expected_seal,args.role=='native')
    except Exception as e:
        write(run/(args.role+'-failed.json'),{'status':'FAILED','run_id':run.name,'pid':os.getpid(),'reason':repr(e),'hardware_approved':False});raise


if __name__=='__main__':main()
