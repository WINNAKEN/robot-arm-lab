if __name__ == '__main__':
    raise SystemExit('Use launch.ps1; direct Python script execution is forbidden')

import base64
import hashlib
import importlib
import importlib.metadata
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

SOURCE=frozenset(('launch.ps1','runner.py','providers.py','test_runner.py','README.md','obligations.json','model.py','verify.py','test_model.py','config.json'))
CORE={'code/runner.py':'runner.py','code/providers.py':'providers.py','code/model.py':'model.py','code/verify.py':'verify.py','config.json':'config.json','obligations.json':'obligations.json'}
FILES=frozenset((*CORE,'lib/extract.py','lib/environment.py','lib/frames.py','data/model.usda','data/golden.json','data/kinematics.json','data/assumptions.json','prefix-seal.json'))
STAGES=frozenset(('sdk_preflight','robot_connection'))
FACETS=('static','bodies','trace','contact')
ROOT=Path(__file__).resolve().parents[3]
OUT='outputs/isaac-contract-v3'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON '+value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def read(path):
    return parse(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value, exclusive=False):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def isolated(forbidden):
    need(sys.flags.isolated == 1, 'All Python entry points require -I')
    for item in sys.path:
        p = Path(item or '.').resolve()
        need(all(not p.is_relative_to(Path(f).resolve()) for f in forbidden), 'Project search namespace exposed')


def no_link(path):
    return not path.is_symlink() and not path.is_junction()


def source_bytes(folder):
    folder = Path(folder)
    need(all(no_link(p) for p in folder.rglob('*')), 'Source link')
    need({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()} == SOURCE, 'Exact source tree')
    return {name:(folder/name).read_bytes() for name in SOURCE}


def checked(run, expected_job, expected_code):
    run = Path(run).resolve()
    isolated([run])
    need(no_link(run) and sha(run/'job.json') == expected_job, 'Pinned job bytes')
    job = read(run/'job.json')
    need(set(job) == {'schema_version','run_id','stage','inputs','hardware_approved'} and job['schema_version'] == 1,
         'Closed job schema')
    need(job['stage'] in STAGES,'Closed stage')
    need(job['run_id'] == run.name and re.fullmatch('[0-9a-f]{32}',run.name) and job['hardware_approved'] is False, 'Job authority')
    need(set(job['inputs']) == FILES, 'Complete mandatory manifest')
    base = run/'input'
    need(all(no_link(p) for p in base.rglob('*')) and
         {p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()} == FILES, 'Exact payload tree')
    data = {name:(base/name).read_bytes() for name in FILES}
    for name, value in data.items():
        need(hashlib.sha256(value).hexdigest() == job['inputs'][name], 'Changed payload '+name)
    need(set(expected_code) == set(CORE), 'Literal code inventory')
    for name, value in expected_code.items():
        need(job['inputs'][name] == value, 'Host source authority '+name)
    cfg = parse(data['config.json'].decode())
    need(cfg['hardware_approved'] is False and cfg['calibration_approved'] is False and cfg['training']=='NOT_RUN', 'No physical/training authority')
    need(cfg['steps']==10 and cfg['rate_hz']==120 and cfg['gravity']==[0,0,0] and cfg['cap_Nm']==[3,6,5,2,2,1], 'Fixed connection recipe')
    for name, reference in cfg['references'].items():
        need(job['inputs'][name] == reference['sha256'], 'Source-derived reference '+name)
    need(job['inputs']['prefix-seal.json'] == cfg['installation_seal_sha256'], 'Source-pinned installation seal')
    validate_contract(parse(data['obligations.json']))
    return job, data, cfg


def compile_module(name, raw, path, api):
    module = types.ModuleType('_checked052_'+name)
    module.__file__ = str(path)
    module.__dict__['API'] = api
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


def validate_contract(contract):
    need(set(contract)=={'schema_version','facets','required_fields'} and contract['schema_version']==1,'Closed source obligations')
    need(contract['facets']==list(FACETS) and set(contract['required_fields'])==set(FACETS),'All four source obligations are mandatory')
    need(all(type(v) is list and v and len(v)==len(set(v)) for v in contract['required_fields'].values()),'Nonempty unique required fields')


def api_for(run,job,data,cfg):
    api={'run':Path(run),'job':job,'cfg':cfg,'data':data,'need':need,'write':write,'read':read,'sha':sha,'parse':parse,
         'runner':types.SimpleNamespace(**globals()),'contract':parse(data['obligations.json']),'lib':{}}
    for name,key in [('frames','lib/frames.py'),('extract','lib/extract.py'),('environment','lib/environment.py'),
                     ('providers','code/providers.py'),('verify','code/verify.py'),('model','code/model.py')]:
        api['lib'][name]=compile_module(name,data[key],Path(run)/'input'/key,api)
    api['lib']['model'].bindings(api);api['lib']['verify'].bindings(api)
    return api


def signature(job):
    return hashlib.sha256(json.dumps(job['inputs'],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_prefix(prefix, raw):
    seal = parse(raw.decode('utf-8-sig'))
    need(set(seal)=={'schema_version','files'} and seal['schema_version']==1, 'Prefix seal schema')
    root = Path(prefix).resolve()
    actual = {}
    for p in root.rglob('*'):
        need(no_link(p), 'Prefix link')
        if p.is_file():
            actual[p.relative_to(root).as_posix()] = sha(p)
    need(actual == seal['files'], 'Installed prefix bytes changed')


def sdk_initialize(cfg):
    sdk = Path(cfg['isaac_root']).resolve()
    need((sdk/'VERSION').read_text(encoding='utf-8-sig').strip()==cfg['isaac_version'], 'Installed SDK identity')
    data = {}
    for name, item in cfg['sdk_files'].items():
        path = Path(item['path']).resolve()
        need(path.is_relative_to(sdk) and no_link(path) and sha(path)==item['sha256'], 'SDK bootstrap changed '+name)
        data[name] = path.read_bytes()
    os.environ.update(ISAAC_PATH=str(sdk), EXP_PATH=str(sdk/'apps'), CARB_APP_PATH=str(sdk/'kit'), PYTHONPATH=str(sdk/'site'))
    before = list(sys.path)
    namespace = {'__file__':str(sdk/'site/sitecustomize.py'),'__name__':'_verified_sdk_site'}
    exec(compile(data['sitecustomize.py'],namespace['__file__'],'exec'),namespace)
    need(all(Path(p).resolve().is_relative_to(sdk) for p in sys.path if p not in before), 'SDK added a foreign path')
    return namespace




def literal(run, job_hash, code_hashes, role):
    args = {'run':str(run),'job':job_hash,'code':code_hashes,'role':role}
    payload = base64.b64encode(json.dumps(args).encode()).decode()
    text = ("import base64,json,pathlib,hashlib\n"+f"a=json.loads(base64.b64decode('{payload}'))\n"
            +"p=pathlib.Path(a['run'])/'input/code/runner.py';b=p.read_bytes()\n"
            +"if hashlib.sha256(b).hexdigest()!=a['code']['code/runner.py']:raise SystemExit('Root changed')\n"
            +"n={'__name__':'_remote052','__file__':str(p)}\nexec(compile(b,str(p),'exec'),n)\n"
            +"raise SystemExit(n['entry'](pathlib.Path(a['run']),a['job'],a['code'],a['role']))\n")
    return "import base64;exec(base64.b64decode('"+base64.b64encode(text.encode()).decode()+"'))"


def entry(run,expected_job,expected_code,role):
    job,data,cfg=checked(run,expected_job,expected_code)
    out=run/'output';out.mkdir(exist_ok=True)
    if role=='export':
        with zipfile.ZipFile(run/'records.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for p in out.rglob('*'):
                if p.is_file():archive.write(p,p.relative_to(out).as_posix())
        return 0
    if role=='supervise':return supervise(run,expected_job,expected_code,cfg)
    need(role=='native','Closed worker phase')
    if job['stage']=='robot_connection':verify_prefix(cfg['installation_prefix'],data['prefix-seal.json'])
    sdk_namespace=sdk_initialize(cfg)
    # Prepend only SDK numerical parents, before importing either numerical package.
    for name in ('scipy_root','numpy_root'):
        parent=Path(cfg[name]).resolve().parent
        need(parent.is_relative_to(Path(cfg['isaac_root']).resolve()),'SDK numeric root')
        sys.path.insert(0,str(parent))
    api=api_for(run,job,data,cfg);api['sdk_namespace']=sdk_namespace
    return api['lib']['providers'].preflight(api) if job['stage']=='sdk_preflight' else api['lib']['model'].run(api)


def sdk_pass(records,job,expected_job,expected_signature,cfg,providers):
    records=Path(records);need(job['stage']=='sdk_preflight' and signature(job)==expected_signature,'Prerequisite source-input signature/stage')
    terminal,ex=read(records/'terminal.json'),read(records/'exit.json')
    need(terminal['run_id']==ex['run_id']==job['run_id'] and terminal['job_sha256']==ex['job_sha256']==expected_job,'Prerequisite run/job binding')
    need(type(terminal['code']) is int and terminal['code']==0 and type(ex['child_exit_code']) is int and ex['child_exit_code']==0,'Prerequisite actual exit0')
    need(terminal['stage']=='sdk_preflight' and terminal['status']=='PREFLIGHT_COMPLETE' and terminal['phase']=='SDK_DLL_PROBE_FINISHED' and ex['status']=='FINISHED','Prerequisite actual terminal')
    need(type(terminal['pid']) is int and terminal['pid']>0 and terminal['pid']==ex['child_pid']==ex['worker_pid'] and terminal['parent_pid']==ex['pid'],'Prerequisite process chain')
    need(terminal['hardware_approved'] is False and terminal['physical_calibration'] is False and terminal['training']=='NOT_RUN','Prerequisite no physical authority')
    need(set(terminal['files_sha256'])=={'providers.json','sdk.json'},'Complete prerequisite observations')
    for name,h in terminal['files_sha256'].items():need(sha(records/name)==h,'Prerequisite raw hash')
    packet,sdk=read(records/'providers.json'),read(records/'sdk.json')
    need(packet['pid']==sdk['pid']==terminal['pid'] and packet['job_sha256']==sdk['job_sha256']==expected_job,'Prerequisite same process observations')
    need(sdk['version']==cfg['isaac_version'] and sdk['isaacsim_origin'] is None and sdk['bootstrap_sha256']=={k:v['sha256'] for k,v in cfg['sdk_files'].items()},'Prerequisite SDK bootstrap identity')
    providers.check_numeric(packet['numeric'],cfg,need)
    return {'status':'SDK_NUMERICAL_PREFLIGHT_VERIFIED','run_id':job['run_id'],'sdk_connected':False,'hardware_approved':False,'training':'NOT_RUN'}


def prerequisite(run,job,cfg,ledger,providers):
    need(job['stage'] in STAGES,'Closed prerequisite stage')
    need(type(ledger) is list and len(ledger)<=2,'Closed stage ledger')
    seen=set()
    for row in ledger:
        need(set(row)=={'stage','run_id','job_sha256','input_signature','reserved_unix'} and row['stage'] in STAGES and row['stage'] not in seen and re.fullmatch('[0-9a-f]{32}',row['run_id']),'Unique closed stage reservation')
        seen.add(row['stage'])
    need(job['stage'] not in seen,'Stage already consumed; no retry after any outcome')
    if job['stage']=='sdk_preflight':
        need(not ledger,'SDK diagnostic must be first')
        return None
    need(len(ledger)==1 and ledger[0]['stage']=='sdk_preflight','Actual SDK prerequisite required')
    row=ledger[0];prior=run.parent/row['run_id']
    need(sha(prior/'job.json')==row['job_sha256'] and row['input_signature']==signature(job),'Original prerequisite identity/signature')
    old_job=read(prior/'job.json');need(old_job['run_id']==row['run_id'],'Prerequisite run directory identity')
    sdk_pass(prior/'output',old_job,row['job_sha256'],signature(job),cfg,providers)
    return prior


def supervise(run,job_hash,code_hashes,cfg):
    need(run.parent==Path(cfg['remote_root']).resolve() and cfg['stage_limits']=={'sdk_preflight':1,'robot_connection':1} and cfg['timeout_s']==600,'Owned single-use stages')
    out=run/'output';out.mkdir(exist_ok=True)
    # An existing record is immutable even when someone calls the internal supervisor twice.
    if (out/'terminal.json').exists() or (out/'exit.json').exists():return 1
    handle,process,code=None,None,1;started=time.time()
    ledger_path,lock=run.parent/'stage-ledger.json',run.parent/'stage.lock'
    try:
        handle=lock.open('x');handle.write(str(os.getpid()));handle.flush()
        job=read(run/'job.json');need(sha(run/'job.json')==job_hash,'Supervisor job hash')
        providers=compile_module('gate_providers',(run/'input/code/providers.py').read_bytes(),run/'input/code/providers.py',{})
        ledger=read(ledger_path) if ledger_path.exists() else []
        prior=prerequisite(run,job,cfg,ledger,providers)
        if prior is not None:
            dest=out/'prerequisite';dest.mkdir()
            shutil.copyfile(prior/'job.json',dest/'job.json')
            for name in ('terminal.json','exit.json','providers.json','sdk.json'):shutil.copyfile(prior/'output'/name,dest/name)
            write(dest/'reservation.json',ledger[0],True)
        ledger.append({'stage':job['stage'],'run_id':run.name,'job_sha256':job_hash,'input_signature':signature(job),'reserved_unix':time.time()})
        write(ledger_path,ledger)
        query=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',"@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count"],capture_output=True,timeout=20)
        need(query.returncode==0 and query.stdout.strip()==b'0','Existing Kit session')
        argv=[str(Path(cfg['isaac_root'])/'kit/python/python.exe'),'-I','-B','-c',literal(run,job_hash,code_hashes,'native')]
        with (out/'stdout.txt').open('xb') as so,(out/'stderr.txt').open('xb') as se:
            process=subprocess.Popen(argv,stdout=so,stderr=se,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            write(out/'supervisor.json',{'run_id':run.name,'job_sha256':job_hash,'pid':os.getpid(),'child_pid':process.pid,'status':'RUNNING'})
            try:code=process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                cleanup=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                write(out/'timeout.json',{'owned_pid':process.pid,'cleanup_exit':cleanup.returncode});process.wait(timeout=15);code=124
    except Exception as exc:
        write(out/'supervisor-failure.json',{'reason':repr(exc),'code':1});code=1
    finally:
        terminal=read(out/'terminal.json') if (out/'terminal.json').exists() else {}
        envelope={'run_id':run.name,'job_sha256':job_hash,'pid':os.getpid(),'child_pid':process.pid if process else None,
                  'worker_pid':terminal.get('pid'),'status':'FINISHED','child_exit_code':int(code),'started_unix':started,'finished_unix':time.time()}
        if (out/'prerequisite').exists():envelope['prerequisite_hashes']={p.name:sha(p) for p in (out/'prerequisite').iterdir() if p.is_file()}
        write(out/'supervisor.json',envelope);write(out/'exit.json',envelope)
        if handle:handle.close();lock.unlink()
    return int(code)


def remote(script, alias, timeout=900):
    encoded = base64.b64encode(script.encode('utf-16le')).decode()
    p = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15',alias,
                        'powershell','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=timeout)
    return p


def prepare(root, source, stage):
    need(stage in STAGES,"Closed stage")
    cfg = parse(source['config.json'].decode())
    out = root/OUT
    run = out/'runs'/uuid.uuid4().hex
    (run/'input/code').mkdir(parents=True)
    try:
        for name in ('runner.py','verify.py','model.py','providers.py'):
            (run/'input/code'/name).write_bytes(source[name])
        (run/'input/config.json').write_bytes(source['config.json'])
        (run/'input/obligations.json').write_bytes(source['obligations.json'])
        for name, reference in cfg['references'].items():
            p = root/reference['path']
            need(sha(p)==reference['sha256'], 'Original input changed '+name)
            target = run/'input'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
        install = root/cfg['installation_record']
        record = read(install/'install-result.json')
        need(record['status']=='INSTALL_DATA_CAPTURED' and record['job_sha256']==cfg['installation_job_sha256'] and
             record['wheel_sha256']==cfg['installation_wheel_sha256'] and record['prefix']==cfg['installation_prefix'] and
             record['seal_sha256']==sha(install/'prefix-seal.json')==cfg['installation_seal_sha256'], 'Recorded installation identity')
        shutil.copyfile(install/'prefix-seal.json',run/'input/prefix-seal.json')
        job = {'schema_version':1,'run_id':run.name,'stage':stage,'inputs':{k:sha(run/'input'/k) for k in sorted(FILES)},'hardware_approved':False}
        write(run/'job.json',job,True)
        pins = {k:job['inputs'][k] for k in CORE}
        checked(run,sha(run/'job.json'),pins)
        with zipfile.ZipFile(run/'bundle.zip','x',zipfile.ZIP_DEFLATED) as archive:
            archive.write(run/'job.json','job.json')
            for key in FILES:
                archive.write(run/'input'/key,'input/'+key)
        write(run/'prepared.json',{'run_id':run.name,'remote':cfg['remote_root']+'/'+run.name,
                                  'job_sha256':sha(run/'job.json'),'code':pins,'bundle_sha256':sha(run/'bundle.zip')},True)
        write(out/'current.json',{'status':'PREPARED_NOT_RUN','run_id':run.name,'hardware_approved':False})
        return run
    except Exception as exc:
        write(out/'current.json',{'status':'FAILED','run_id':run.name,'reason':repr(exc),'hardware_approved':False})
        raise


def launch(run, prepared, cfg):
    rr, alias = Path(prepared['remote']), cfg['ssh_alias']
    need(re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+',prepared['remote']) and re.fullmatch('[A-Za-z0-9_-]+',alias), 'Safe endpoint')
    p = remote("$ErrorActionPreference='Stop';if(Test-Path -LiteralPath '"+str(rr)+"'){throw 'Run exists'};New-Item -ItemType Directory -Path '"+str(rr)+"'|Out-Null",alias)
    need(p.returncode==0,'Remote create')
    p = subprocess.run(['scp','-q',str(run/'bundle.zip'),alias+':'+str(rr/'bundle.zip')],timeout=120)
    need(p.returncode==0,'Upload bundle')
    p = remote("$ErrorActionPreference='Stop';if((Get-FileHash -LiteralPath '"+str(rr/'bundle.zip')+"').Hash -ine '"+prepared['bundle_sha256']+"'){throw 'Bundle SHA'};Expand-Archive -LiteralPath '"+str(rr/'bundle.zip')+"' -DestinationPath '"+str(rr)+"'",alias,120)
    need(p.returncode==0,'Remote expand')
    python = str(Path(cfg['isaac_root'])/'kit/python/python.exe')
    code = literal(rr,prepared['job_sha256'],prepared['code'],'supervise')
    p = remote("& '"+python+"' -I -B -c \""+code+"\";exit $LASTEXITCODE",alias)
    write(run/'transport.json',{'returncode':p.returncode,'stderr':p.stderr.decode(errors='replace')})
    code = literal(rr,prepared['job_sha256'],prepared['code'],'export')
    exported = remote("& '"+python+"' -I -B -c \""+code+"\";exit $LASTEXITCODE",alias,120)
    need(exported.returncode==0,'Export original result, do not rerun')
    p = subprocess.run(['scp','-q',alias+':'+str(rr/'records.zip'),str(run/'records.zip')],timeout=120)
    need(p.returncode==0,'Retrieve original result')
    dest = run/'retrieved'
    dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(run/'records.zip') as archive:
        for name in archive.namelist():
            target = (dest/name).resolve()
            need(target.is_relative_to(dest.resolve()),'Unsafe result archive path')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(name))


def public(role,run_dir,stage=''):
    folder=Path(__file__).resolve().parent;isolated([ROOT,folder]);source=source_bytes(folder)
    if role=='test':
        api={'runner':types.SimpleNamespace(**globals()),'source':source,'root':ROOT,'folder':folder}
        a=compile_module('tests_A',source['test_runner.py'],folder/'test_runner.py',api)
        b=compile_module('tests_B',source['test_model.py'],folder/'test_model.py',api)
        api['tests_B']=b
        return a.run_tests(b)
    if role=='prepare':print(prepare(ROOT,source,stage));return 0
    need(role in ('run','verify') and run_dir,'Owned run required')
    run=Path(run_dir).resolve();prepared=read(run/'prepared.json');pins={key:hashlib.sha256(source[name]).hexdigest() for key,name in CORE.items()}
    job,data,cfg=checked(run,prepared['job_sha256'],pins)
    need(prepared['code']==pins and prepared['run_id']==run.name and prepared['remote']==cfg['remote_root']+'/'+run.name,'Host preparation binding')
    need(not stage or job['stage']==stage,'Requested stage identity')
    try:
        if role=='run':launch(run,prepared,cfg)
        api=api_for(run,job,data,cfg)
        result=sdk_pass(run/'retrieved',job,prepared['job_sha256'],signature(job),cfg,api['lib']['providers']) if job['stage']=='sdk_preflight' else api['lib']['verify'].consume(run/'retrieved',api)
        write(run/'validation.json',result);write(run.parent.parent/'current.json',result);print(json.dumps(result));return 0
    except Exception as exc:
        write(run.parent.parent/'current.json',{'status':'FAILED','run_id':run.name,'stage':job['stage'],'reason':repr(exc),'hardware_approved':False})
        print(repr(exc),file=sys.stderr);return 1
