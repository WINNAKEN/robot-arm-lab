"""049 capability kernel: checked bytes, no project import search namespace."""
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
import types
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[3]
OUT='outputs/isaac-control-kernel-v1'
FIXED=frozenset(('code/kernel.py','code/control.py','code/verify.py','code/native.py','config.json',
    'lib/motion.py','lib/frames.py','lib/environment.py','lib/extract.py','data/model.usda','data/golden.json',
    'data/kinematics.json','data/program.json','data/assumptions.json','prefix-seal.json'))


def need(ok,reason):
    if not ok:raise ValueError(reason)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(raw):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    def invalid(x):raise ValueError('Nonfinite JSON: '+x)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)


def read(p):return parse(Path(p).read_text(encoding='utf-8-sig'))


def write(p,value,exclusive=False):
    with Path(p).open('x' if exclusive else 'w',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def checked_bytes(run,expected_job):
    run=Path(run).resolve();need(sha(run/'job.json')==expected_job,'Host-pinned job SHA')
    job=read(run/'job.json');need(set(job)=={'schema_version','run_id','inputs','prefix','prefix_seal_sha256','hardware_approved'},'Closed job schema')
    need(job['schema_version']==1 and job['hardware_approved'] is False and job['run_id']==run.name and re.fullmatch('[0-9a-f]{32}',run.name),'Job identity/authority')
    need(set(job['inputs'])==FIXED,'Fixed complete input manifest')
    base=run/'input';actual={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
    need(actual==FIXED and all(not p.is_symlink() for p in base.rglob('*')),'Exact input tree, no shadow packages or symlinks')
    data={name:(base/name).read_bytes() for name in FIXED}
    for name,raw in data.items():need(hashlib.sha256(raw).hexdigest()==job['inputs'][name],'Input bytes changed: '+name)
    need(hashlib.sha256(data['prefix-seal.json']).hexdigest()==job['prefix_seal_sha256'],'Host-bound installation seal')
    return job,data


def verify_prefix(prefix,seal_bytes):
    expected=parse(seal_bytes.decode('utf-8-sig'));need(set(expected)=={'schema_version','files'} and expected['schema_version']==1,'Installation seal schema')
    prefix=Path(prefix).resolve();actual={}
    for p in prefix.rglob('*'):
        need(not p.is_symlink(),'Unsealed prefix symlink')
        if p.is_file():actual[p.relative_to(prefix).as_posix()]=sha(p)
    need(actual==expected['files'],'Exact installed code tree/bytes')


def capabilities(run,job,data):
    """Execute cached verified project bytes; never insert project directories in sys.path."""
    api={'run':Path(run),'job':job,'cfg':parse(data['config.json'].decode()),'need':need,'sha':sha,'read':read,'write':write,'parse':parse,
         'golden':parse(data['data/golden.json'].decode()),'lib':{}}
    def load(name,key):
        module=types.ModuleType('_verified049_'+name);module.__file__=str(Path(run)/'input'/key)
        module.__dict__['API']=api
        exec(compile(data[key],module.__file__,'exec'),module.__dict__)
        return module
    for name,key in [('motion','lib/motion.py'),('frames','lib/frames.py'),('environment','lib/environment.py'),('extract','lib/extract.py'),
                     ('control','code/control.py'),('verify','code/verify.py')]:api['lib'][name]=load(name,key)
    api['lib']['native']=load('native','code/native.py')
    return api


def bootstrap(run,kernel_sha,job_sha,role):
    path=str(Path(run)/'input/code/kernel.py')
    code=("import pathlib,hashlib\n"+f"p=pathlib.Path({path!r});j=pathlib.Path({str(Path(run)/'job.json')!r})\n"
          +f"b=p.read_bytes()\nif hashlib.sha256(b).hexdigest()!={kernel_sha!r} or hashlib.sha256(j.read_bytes()).hexdigest()!={job_sha!r}:raise SystemExit('Unapproved root before project execution')\n"
          +f"n={{'__name__':'_verified_kernel','__file__':str(p)}}\nexec(compile(b,str(p),'exec'),n)\nn['entry'](pathlib.Path({str(run)!r}),{job_sha!r},{role!r})\n")
    return "import base64;exec(base64.b64decode('"+base64.b64encode(code.encode()).decode()+"'))"


def modules(api):
    import importlib
    import importlib.metadata
    prefix=Path(api['job']['prefix']).resolve();result={}
    for name,dist,version in [('isaaclab','isaaclab','3.0.0'),('torch','torch','2.11.0+cu130'),('warp','warp-lang','1.17.0'),('gymnasium','gymnasium',None),('rsl_rl','rsl-rl-lib','5.5.1')]:
        m=importlib.import_module(name);origin=Path(m.__file__).resolve();v=importlib.metadata.version(dist)
        need(origin.is_relative_to(prefix) and (version is None or v==version),'Actual module identity: '+name)
        result[name]={'version':v,'origin':str(origin)}
    import torch
    need(torch.cuda.is_available() and torch.version.cuda.startswith('13.'),'CUDA13 GPU required')
    x=torch.ones((2,3),device='cuda:0');total=float(x.sum().item());need(total==6 and x.is_cuda,'Actual GPU calculation')
    return {'status':'MODULE_GPU_CAPTURED','modules':result,'cuda':torch.version.cuda,'sum':total,'device':str(x.device),
            'run_id':api['run'].name,'pid':os.getpid(),'parent_pid':os.getppid(),'job_sha256':sha(api['run']/'job.json'),'hardware_approved':False}


def entry(run,expected_job,role):
    # This function is reached only by the isolated literal root, not name imports.
    job,data=checked_bytes(run,expected_job)
    if role=='export':
        with zipfile.ZipFile(run/'records.zip','w',zipfile.ZIP_DEFLATED) as z:
            for p in (run/'output').rglob('*'):
                if p.is_file():z.write(p,p.relative_to(run/'output').as_posix())
        return
    if role=='inspect':
        verify_prefix(job['prefix'],data['prefix-seal.json'])
        api=capabilities(run,job,data);out=run/'output';out.mkdir(exist_ok=True)
        write(out/'entry-proof.json',{'status':'HOST_CODE_INSPECTION_ONLY','loaded':list(api['lib']),
            'project_search_path':any(Path(p or '.').resolve().is_relative_to(run.resolve()) for p in sys.path),'hardware_approved':False})
        return
    need(role in ('module','native','supervisor'),'Fixed phase')
    cfg=parse(data['config.json'].decode());need(cfg['hardware_approved'] is False and cfg['calibration_approved'] is False and cfg['training']=='NOT_RUN','Authority')
    need(job['prefix']==cfg['installation_prefix'] and job['prefix_seal_sha256']==cfg['installation_seal_sha256'],'Source-pinned installation handoff')
    need((Path(cfg['isaac_root'])/'VERSION').read_text(encoding='utf-8-sig').strip()==cfg['isaac_version'],'SDK identity')
    verify_prefix(job['prefix'],data['prefix-seal.json'])
    if role=='supervisor':
        supervise(run,expected_job,cfg,job)
        return
    # Only immutable installed libraries and SDK paths are discoverable; no run/input/code/lib path.
    if role=='native':
        sdk=Path(cfg['isaac_root']).resolve()
        for value in os.environ.get('PYTHONPATH','').split(os.pathsep):
            if value:need(Path(value).resolve().is_relative_to(sdk),'Foreign SDK path');sys.path.append(str(Path(value).resolve()))
    sys.path.insert(0,str(Path(job['prefix']).resolve()))
    api=capabilities(run,job,data);out=run/'output';out.mkdir(exist_ok=True)
    try:
        if role=='module':write(out/'module.json',modules(api),True)
        else:
            prior=read(out/'module.json');need(prior['status']=='MODULE_GPU_CAPTURED' and prior['job_sha256']==expected_job,'Module gate first')
            # Recompute live in this isolated process; an edited phase marker has no authority.
            write(out/'native-module.json',modules(api),True)
            api['lib']['native'].worker(run)
    except Exception as e:
        write(out/(role+'-failure.json'),{'status':'FAILED','run_id':run.name,'pid':os.getpid(),'reason':repr(e),'hardware_approved':False});raise


def supervise(run,expected_job,cfg,job):
    need(run.parent==Path(cfg['remote_root']).resolve() and cfg['native_limit']==2 and cfg['timeout_s']==600,'Owned finite native scope')
    out=run/'output';out.mkdir(exist_ok=True);ledger=run.parent/'native-attempts.json';lock=run.parent/'native-launch.lock'
    process=None;code=1;started=time.time();handle=None
    try:
        handle=lock.open('x');handle.write(str(os.getpid()));handle.flush()
        attempts=read(ledger) if ledger.exists() else []
        need(type(attempts) is list and len(attempts)<2,'Global 049 native attempts exhausted')
        need(not (out/'summary.json').exists(),'Captured experiment is not repeated')
        attempts.append({'run_id':run.name,'job_sha256':expected_job,'reserved_unix':time.time()});write(ledger,attempts)
        query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',"@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count"],capture_output=True,timeout=20)
        need(query.returncode==0 and query.stdout.strip()==b'0','Existing Kit session or failed process query')
        code_text=bootstrap(run,job['inputs']['code/kernel.py'],expected_job,'native');env=os.environ.copy()
        env['PYTHONEXE']=str(Path(cfg['isaac_root'])/'kit/python/python.exe')
        argv=[env['COMSPEC'],'/d','/c',str(Path(cfg['isaac_root'])/'python.bat'),'-I','-B','-c',code_text]
        with (out/'native-stdout.txt').open('xb') as so,(out/'native-stderr.txt').open('xb') as se:
            process=subprocess.Popen(argv,env=env,stdout=so,stderr=se,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            write(out/'supervisor.json',{'run_id':run.name,'pid':os.getpid(),'child_pid':process.pid,'status':'RUNNING','job_sha256':expected_job,'argv':argv})
            try:code=process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                cleanup=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                write(out/'timeout.json',{'owned_pid':process.pid,'cleanup_exit':cleanup.returncode});process.wait(timeout=15);code=124
    finally:
        status=read(out/'status.json') if (out/'status.json').exists() else {}
        previous=read(out/'supervisor.json') if (out/'supervisor.json').exists() else {}
        write(out/'supervisor.json',{**previous,'status':'FINISHED','run_id':run.name,'pid':os.getpid(),
            'child_pid':process.pid if process else None,'worker_pid':status.get('pid'),'child_exit_code':int(code),'job_sha256':expected_job})
        write(out/'exit.json',{'run_id':run.name,'job_sha256':expected_job,'exit_code':int(code),'pid':status.get('pid'),
            'native_pid':process.pid if process else None,'supervisor_pid':os.getpid(),'started_unix':started,'finished_unix':time.time()})
        if handle:handle.close();lock.unlink()
    need(code==0,'Native process failed '+str(code))


def remote(script,alias,timeout=720):
    encoded=base64.b64encode(script.encode('utf-16le')).decode()
    answer=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=10',alias,'powershell','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=timeout)
    need(answer.returncode==0,'SSH: '+str(answer.returncode)+' '+answer.stderr.decode(errors='replace'));return answer.stdout


def prepare(root=ROOT):
    root=Path(root);source=root/'src/simulation/isolated_control';cfg=read(source/'config.json');out=root/OUT;out.mkdir(parents=True,exist_ok=True)
    run=out/'runs'/uuid.uuid4().hex;run.mkdir(parents=True);base=run/'input';base.mkdir();write(out/'current.json',{'status':'BUILDING','run_id':run.name,'hardware_approved':False})
    try:
        for name in ('kernel.py','control.py','verify.py','native.py'):
            p=base/'code'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(source/name,p)
        shutil.copyfile(source/'config.json',base/'config.json')
        for key,value in cfg['references'].items():
            need(sha(root/value['path'])==value['sha256'],'Approved source changed: '+key);p=base/key;p.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(root/value['path'],p)
        install=root/cfg['installation_record'];record=read(install/'install-result.json');seal=install/'prefix-seal.json'
        need(record['status']=='INSTALL_DATA_CAPTURED' and record['seal_sha256']==sha(seal)==cfg['installation_seal_sha256'] and
             record['job_sha256']==cfg['installation_job_sha256'] and record['wheel_sha256']==cfg['installation_wheel_sha256'] and
             record['prefix']==cfg['installation_prefix'],'Source-pinned recorded installation')
        for name in ('pip-dependencies','pip-lab'):
            ex=read(install/(name+'-exit.json'));process=read(install/(name+'-process.json'))
            need(ex['exit_code']==0 and ex['child_pid']==process['pid'] and ex['supervisor_pid']==record['pid'],'Actual installer child evidence')
        shutil.copyfile(seal,base/'prefix-seal.json')
        job={'schema_version':1,'run_id':run.name,'hardware_approved':False,'prefix':record['prefix'],'prefix_seal_sha256':sha(seal),
             'inputs':{k:sha(base/k) for k in sorted(FIXED)}}
        write(run/'job.json',job);checked_bytes(run,sha(run/'job.json'))
        with zipfile.ZipFile(run/'bundle.zip','x',zipfile.ZIP_DEFLATED) as z:
            z.write(run/'job.json','job.json')
            for k in FIXED:z.write(base/k,'input/'+k)
        write(run/'prepared.json',{'run_id':run.name,'remote':cfg['remote_root']+'/'+run.name,'kernel_sha256':sha(base/'code/kernel.py'),'job_sha256':sha(run/'job.json'),'bundle_sha256':sha(run/'bundle.zip')})
        return run
    except Exception as e:write(out/'current.json',{'status':'FAILED','run_id':run.name,'reason':repr(e),'hardware_approved':False});raise


def launch(run,role):
    p=read(run/'prepared.json');cfg=read(run/'input/config.json');rr=Path(p['remote']);alias=cfg['ssh_alias']
    need(re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+',p['remote']) and re.fullmatch('[A-Za-z0-9_-]+',alias),'Safe endpoint')
    if role=='module':
        remote("$ErrorActionPreference='Stop'; if(Test-Path -LiteralPath '"+str(rr)+"') {throw 'Owned run exists'}; New-Item -ItemType Directory -Path '"+str(rr)+"' | Out-Null",alias)
        x=subprocess.run(['scp','-q',str(run/'bundle.zip'),alias+':'+str(rr/'bundle.zip')],timeout=120);need(x.returncode==0,'SCP bundle')
        remote("$ErrorActionPreference='Stop'; if((Get-FileHash -LiteralPath '"+str(rr/'bundle.zip')+"').Hash -ine '"+p['bundle_sha256']+"') {throw 'Bundle hash'}; Expand-Archive -LiteralPath '"+str(rr/'bundle.zip')+"' -DestinationPath '"+str(rr)+"'",alias)
    code=bootstrap(rr,p['kernel_sha256'],p['job_sha256'],'supervisor' if role=='native' else role);python=str(Path(cfg['isaac_root'])/'kit/python/python.exe')
    script="$ProgressPreference='SilentlyContinue'; $env:PYTHONEXE='"+python+"'; & '"+python+"' -I -B -c \""+code+"\"; exit $LASTEXITCODE"
    failure=None
    try:remote(script,alias)
    except Exception as e:failure=e
    export=bootstrap(rr,p['kernel_sha256'],p['job_sha256'],'export')
    remote("& '"+python+"' -I -B -c \""+export+"\"; exit $LASTEXITCODE",alias,120)
    x=subprocess.run(['scp','-q',alias+':'+str(rr/'records.zip'),str(run/'records.zip')],timeout=120);need(x.returncode==0,'SCP results')
    dest=run/'retrieved';dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(run/'records.zip') as z:
        for name in z.namelist():
            path=(dest/name).resolve();need(path.is_relative_to(dest.resolve()),'Unsafe records path');path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes(z.read(name))
    if failure:raise failure


def main():
    p=argparse.ArgumentParser();p.add_argument('role',choices=('prepare','module','native','verify'));p.add_argument('--run-dir',type=Path);a=p.parse_args()
    if a.role=='prepare':print(prepare());return
    need(a.run_dir is not None,'Owned run required');run=a.run_dir.resolve();prepared=read(run/'prepared.json');job,data=checked_bytes(run,prepared['job_sha256'])
    try:
        if a.role in ('module','native'):launch(run,a.role)
        if a.role=='module':result=read(run/'retrieved/module.json');need(result['status']=='MODULE_GPU_CAPTURED','Actual module result');print(json.dumps(result));return
        api=capabilities(run,job,data);result=api['lib']['verify'].verify_run(run/'retrieved',api);write(run/'validation.json',result)
        write(run.parent.parent/'current.json',result);print(json.dumps(result))
    except Exception as e:write(run.parent.parent/'current.json',{'status':'FAILED','run_id':run.name,'reason':repr(e),'hardware_approved':False});raise


if __name__=='__main__':main()
