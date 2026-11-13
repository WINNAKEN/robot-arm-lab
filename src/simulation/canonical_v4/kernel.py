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

SOURCE=frozenset(('launch.ps1','kernel.py','providers.py','robot.py','contract.json','config.json','test_kernel.py','README.md'))
CORE={'code/kernel.py':'kernel.py','code/providers.py':'providers.py','code/robot.py':'robot.py','config.json':'config.json','contract.json':'contract.json'}
FILES=frozenset((*CORE,'lib/extract.py','lib/environment.py','lib/frames.py','data/model.usda','data/golden.json','data/kinematics.json','data/assumptions.json','prefix-seal.json'))
STAGES=frozenset(('sdk_preflight','robot_connection'))
FACETS=('static','bodies','trace','contact')
ROOT=Path(__file__).resolve().parents[3]
OUT='outputs/isaac-canonical-v4'


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
    job_raw = (run/'job.json').read_bytes()
    need(no_link(run) and hashlib.sha256(job_raw).hexdigest() == expected_job, 'Pinned job bytes')
    job = parse(job_raw.decode('utf-8-sig'))
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
    validate_contract(parse(data['contract.json']))
    return job, data, cfg


def compile_module(name, raw, path, api):
    module = types.ModuleType('_checked053_'+name)
    module.__file__ = str(path)
    module.__dict__['API'] = api
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


def validate_contract(contract):
    need(set(contract)=={'schema_version','facets','required_fields'} and contract['schema_version']==1,'Closed source obligations')
    need(contract['facets']==list(FACETS) and set(contract['required_fields'])==set(FACETS),'All four source obligations are mandatory')
    need(all(type(v) is list and v and len(v)==len(set(v)) for v in contract['required_fields'].values()),'Nonempty unique required fields')


def freeze(value):
    if isinstance(value,dict):return types.MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value,list):return tuple(freeze(x) for x in value)
    return value


def snapshot(run,job_hash,pins):
    job,data,cfg=checked(run,job_hash,pins)
    return Snapshot(Path(run).resolve(),job_hash,freeze(pins),freeze(job),freeze(data),freeze(cfg))


def bindings(api):
    need(set(VALIDATORS)==set(api['contract']['facets']),'Kernel validator obligations')


def api_for(context,sdk=False):
    run,job,data,cfg=context.run,context.job,context.data,context.cfg
    api={'run':run,'job':job,'cfg':cfg,'data':data,'need':need,'write':write,'read':read,'sha':sha,'parse':parse,
         'kernel':types.SimpleNamespace(**globals()),'runner':types.SimpleNamespace(**globals()),
         'contract':parse(data['contract.json']),'lib':{}}
    for name,key in [('frames','lib/frames.py'),('extract','lib/extract.py'),('environment','lib/environment.py'),
                     ('providers','code/providers.py'),('robot','code/robot.py')]:
        api['lib'][name]=compile_module(name,data[key],run/'input'/key,api)
    api['lib']['verify']=types.SimpleNamespace(**globals())
    bindings(api);api['lib']['robot'].bindings(api)
    api['check_numeric']=lambda value:check_numeric(value,cfg,need)
    api['check_frameworks']=lambda value:check_frameworks(value,cfg)
    # The source oracle stays in a separate root-owned callback context.
    oracle={**api,'data':data}
    api['validate_observations']=lambda packet:observations(packet,oracle)
    if sdk:api['data']=types.MappingProxyType({k:v for k,v in data.items() if k!='data/golden.json'})
    return api


def signature(job):
    return hashlib.sha256(json.dumps(dict(job['inputs']),sort_keys=True,separators=(',',':')).encode()).hexdigest()


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
        raw=path.read_bytes()
        need(owned_origin(str(path),str(sdk)) and no_link(path) and hashlib.sha256(raw).hexdigest()==item['sha256'], 'SDK bootstrap changed '+name)
        data[name]=raw
    os.environ.update(ISAAC_PATH=str(sdk), EXP_PATH=str(sdk/'apps'), CARB_APP_PATH=str(sdk/'kit'), PYTHONPATH=str(sdk/'site'))
    before = list(sys.path)
    namespace = {'__file__':str(sdk/'site/sitecustomize.py'),'__name__':'_verified_sdk_site'}
    exec(compile(data['sitecustomize.py'],namespace['__file__'],'exec'),namespace)
    need(all(Path(p).resolve().is_relative_to(sdk) for p in sys.path if p not in before), 'SDK added a foreign path')
    return namespace




def literal(run, job_hash, code_hashes, role):
    args = {'run':str(run),'job':job_hash,'code':dict(code_hashes),'role':role}
    payload = base64.b64encode(json.dumps(args).encode()).decode()
    text = ("import base64,json,pathlib,hashlib\n"+f"a=json.loads(base64.b64decode('{payload}'))\n"
            +"p=pathlib.Path(a['run'])/'input/code/kernel.py';b=p.read_bytes()\n"
            +"if hashlib.sha256(b).hexdigest()!=a['code']['code/kernel.py']:raise SystemExit('Root changed')\n"
            +"n={'__name__':'_remote053','__file__':str(p)}\nexec(compile(b,str(p),'exec'),n)\n"
            +"raise SystemExit(n['entry'](pathlib.Path(a['run']),a['job'],a['code'],a['role']))\n")
    return "import base64;exec(base64.b64decode('"+base64.b64encode(text.encode()).decode()+"'))"


def entry(run,expected_job,expected_code,role):
    context=snapshot(run,expected_job,expected_code)
    job,data,cfg=context.job,context.data,context.cfg
    out=run/'output';out.mkdir(exist_ok=True)
    if role=='export':
        with zipfile.ZipFile(run/'records.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for p in out.rglob('*'):
                if p.is_file():archive.write(p,p.relative_to(out).as_posix())
        return 0
    if role=='supervise':return supervise(context)
    need(role=='native','Closed worker phase')
    if job['stage']=='robot_connection':verify_prefix(cfg['installation_prefix'],data['prefix-seal.json'])
    sdk_namespace=sdk_initialize(cfg)
    for name in ('scipy_root','numpy_root'):
        parent=Path(cfg[name]).resolve().parent
        need(owned_origin(str(parent),cfg['isaac_root']),'SDK numeric root')
        sys.path.insert(0,str(parent))
    api=api_for(context,sdk=True);api['sdk_namespace']=sdk_namespace
    return api['lib']['providers'].preflight(api) if job['stage']=='sdk_preflight' else api['lib']['robot'].run(api)


def sdk_pass(records,job,expected_job,expected_signature,cfg,providers=None):
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
    check_numeric(packet['numeric'],cfg,need)
    return {'status':'SDK_NUMERICAL_PREFLIGHT_VERIFIED','run_id':job['run_id'],'sdk_connected':False,'hardware_approved':False,'training':'NOT_RUN'}


def prerequisite(run,job,cfg,ledger,providers=None):
    need(job['stage'] in STAGES,'Closed prerequisite stage')
    need(type(ledger) is list and len(ledger)<=2,'Closed stage ledger')
    for legacy in cfg.get('frozen_stage_ledgers',()):
        if Path(legacy).exists():
            prior_ledger=read(legacy)
            need(type(prior_ledger) is list and all(type(x) is dict and x.get('stage') in STAGES for x in prior_ledger),'Legacy stage ledger schema')
            need(not any(x['stage']==job['stage'] for x in prior_ledger),'Stage already reserved in frozen052; cumulative one-use limit')
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


def supervise(context):
    run,job_hash,code_hashes,cfg=context.run,context.job_hash,context.pins,context.cfg
    job=context.job
    need(run.parent==Path(cfg['remote_root']).resolve() and cfg['stage_limits']=={'sdk_preflight':1,'robot_connection':1} and cfg['timeout_s']==600,'Owned single-use stages')
    out=run/'output';out.mkdir(exist_ok=True)
    # An existing record is immutable even when someone calls the internal supervisor twice.
    if (out/'terminal.json').exists() or (out/'exit.json').exists():return 1
    handle,process,code=None,None,1;started=time.time()
    ledger_path,lock=run.parent/'stage-ledger.json',run.parent/'stage.lock'
    try:
        handle=lock.open('x');handle.write(str(os.getpid()));handle.flush()
        ledger=read(ledger_path) if ledger_path.exists() else []
        prior=prerequisite(run,job,cfg,ledger)
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
        for name in ('kernel.py','robot.py','providers.py'):
            (run/'input/code'/name).write_bytes(source[name])
        (run/'input/config.json').write_bytes(source['config.json'])
        (run/'input/contract.json').write_bytes(source['contract.json'])
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
        api={'kernel':types.SimpleNamespace(**globals()),'source':source,'root':ROOT,'folder':folder}
        tests=compile_module('tests',source['test_kernel.py'],folder/'test_kernel.py',api)
        return tests.run_tests()
    if role=='prepare':print(prepare(ROOT,source,stage));return 0
    need(role in ('run','verify') and run_dir,'Owned run required')
    run=Path(run_dir).resolve();prepared=read(run/'prepared.json');pins={k:hashlib.sha256(source[n]).hexdigest() for k,n in CORE.items()}
    context=snapshot(run,prepared['job_sha256'],pins);job,cfg=context.job,context.cfg
    need(prepared['code']==pins and prepared['run_id']==run.name and prepared['remote']==cfg['remote_root']+'/'+run.name,'Host preparation binding')
    need(not stage or job['stage']==stage,'Requested stage identity')
    try:
        if role=='run':launch(run,prepared,cfg)
        api=api_for(context)
        result=sdk_pass(run/'retrieved',job,prepared['job_sha256'],signature(job),cfg) if job['stage']=='sdk_preflight' else consume(run/'retrieved',api)
        write(run/'validation.json',result);write(run.parent.parent/'current.json',result);print(json.dumps(result));return 0
    except Exception as exc:
        write(run.parent.parent/'current.json',{'status':'FAILED','run_id':run.name,'stage':job['stage'],'reason':repr(exc),'hardware_approved':False})
        print(repr(exc),file=sys.stderr);return 1


def deep_equal(actual,expected,path='source',tolerance=1e-6):
    if isinstance(expected,dict):
        need(type(actual) is dict and set(actual)==set(expected),'Complete field schema: '+path)
        for key in expected:deep_equal(actual[key],expected[key],path+'.'+key,1e-7 if key=='inertia_diag' else tolerance)
    elif isinstance(expected,list):
        need(type(actual) is list and len(actual)==len(expected),'Full field array: '+path)
        for i,(a,b) in enumerate(zip(actual,expected)):deep_equal(a,b,path+'.'+str(i),tolerance)
    elif type(expected) in (int,float):
        need(type(actual) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=tolerance,'Source numeric frame mismatch: '+path)
    else:need(type(actual) is type(expected) and actual==expected,'Source identity/type mismatch: '+path)

def number(value, label):
    need(type(value) in (int, float) and math.isfinite(value), 'Finite number: ' + label)
    return float(value)

def integer(value, label):
    need(type(value) is int and value >= 0, 'Nonnegative integer: ' + label)
    return value

def vector(value, length=3, label='vector'):
    need(type(value) is list and len(value) == length, 'Vector shape: ' + label)
    return [number(x, label) for x in value]

def transpose(a):
    return [list(row) for row in zip(*a)]

def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def mv(a, b):
    return [sum(x*y for x, y in zip(row, b)) for row in a]

def add(a, b):
    return [x+y for x, y in zip(a, b)]

def error(a, b):
    if isinstance(a[0], (list, tuple)):
        return max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3))
    return max(abs(x-y) for x, y in zip(a, b))

def matrix(value, label='matrix', rigid=True):
    need(type(value) is list and len(value) == 3, 'Matrix shape: ' + label)
    result = [vector(row, label=label) for row in value]
    if rigid:
        a, b, c = result
        determinant = (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0])
                       + a[2]*(b[0]*c[1]-b[1]*c[0]))
        need(error(mm(result, transpose(result)), IDENTITY) <= 1e-5
             and abs(determinant-1) <= 1e-5, 'Proper rotation: ' + label)
    return result

def quaternion(value):
    w, x, y, z = vector(value, 4, 'quaternion wxyz')
    norm = math.sqrt(w*w+x*x+y*y+z*z)
    need(abs(norm-1) <= 1e-5, 'Unit quaternion wxyz')
    w, x, y, z = [q/norm for q in (w, x, y, z)]
    return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]

def frame(body_pose, joint, side):
    position, rotation = body_pose
    return (add(position, mv(rotation, vector(joint['local_pos'+str(side)]))),
            mm(rotation, quaternion(joint['local_rot'+str(side)+'_wxyz'])))

def validate_static(value, facets, api):
    s=value;golden=api['parse'](api['data']['data/golden.json'])
    for key in ('units','default_prim','root_placement','robot_root','bodies','joints','colliders'):
        deep_equal(s[key],golden[key],key)
    expected = {k:v for k,v in golden['environment'].items() if k not in ('contact_mapping','probe_runtime_mass')}
    deep_equal(s['environment'],expected,'complete source environment')

def validate_bodies(value, facets, api):
    s={**facets['static'],**value};cfg=api['cfg']
    deep_equal(s['configuration'],{'gravity':[0,0,0],'frequency_hz':120,'device':'cpu','manager':'isaaclab_physx.physics.physx_manager.PhysxManager'})
    need(len(s['dof_names'])==6 and set(s['dof_names'])==set(JOINTS), 'Exact named DOFs')
    deep_equal(s['actual_drives'],{'kp':[0]*6,'kd':[0]*6,'effort':list(cfg['cap_Nm']),'types':['force']*6})
    golden=api['parse'](api['data']['data/golden.json'])
    expected_bodies={b['name']:b for b in golden['bodies']}
    expected_bodies['probe']=golden['environment']['probe_source_observation']
    runtime = s['runtime_masses']
    need(len(runtime)==8 and {b['name'] for b in runtime}==set(expected_bodies), 'All runtime mass frames')
    for item in runtime:
        source = expected_bodies[item['name']]
        need(abs(number(item['mass'],'mass')-source['mass'])<=1e-6 and error(vector(item['com']),source['com'])<=1e-6,'Runtime mass/local COM')
        rotation = quaternion(source['principal_axes_wxyz'])
        d = vector(source['inertia_diag'])
        expected_tensor = mm(mm(rotation,[[d[i] if i==j else 0 for j in range(3)] for i in range(3)]),transpose(rotation))
        actual = matrix(item['inertia_link_about_com'],rigid=False)
        need(error(actual,expected_tensor)<=1e-7,'Full source inertia tensor')
        principal = quaternion(item['principal_axes_wxyz'])
        diagonal = mm(mm(transpose(principal),actual),principal)
        need(min(diagonal[i][i] for i in range(3))>0 and max(abs(diagonal[i][j]) for i in range(3) for j in range(3) if i!=j)<=1e-7,'Principal frame diagonalizes full tensor')

def rows_check(s, rows, api):
    need(type(rows) is list and len(rows)==11,'All eleven connection observations')
    layout = api['lib']['frames'].decode(api['data']['data/kinematics.json'])
    frames = api['lib']['frames']
    bodies = {b['name']:b for b in s['bodies']}
    paths = {b['path']:name for name,b in bodies.items()}
    joints = {j['name']:j for j in s['joints'] if j['type']=='revolute'}
    fixed = [j for j in s['joints'] if j['type']=='fixed']
    need(set(joints)==set(JOINTS) and len(fixed)==1,'Complete physical joints')
    baseline = rows[0]['read_after']
    base_lab = integer(baseline['lab_step'],'baseline Lab step')
    base_time = number(baseline['engine_time_s'],'baseline engine time')
    maxima = {'link_m':0.,'rotation':0.,'anchor_m':0.,'joint_rotation':0.,'axis':0.,'angle_rad':0.,'speed_rad_s':0.}
    previous = None
    for index,row in enumerate(rows):
        need(type(row['index']) is int and row['index']==index and row['timeline_playing'] is True,'Actual indexed playing observation')
        deep_equal(row['read_before'],row['read_after'],'read ownership',1e-10)
        clock = row['read_after']
        need(set(clock)=={'lab_step','engine_event_index','engine_time_s','callback_time_s'},'Closed observed clock schema')
        need(integer(clock['lab_step'],'Lab step')==base_lab+index and integer(clock['engine_event_index'],'PhysX post-event index')==index,'Actual Lab request/post-step progress')
        need(abs(number(clock['engine_time_s'],'engine time')-base_time-index*DT)<=1e-6,'Actual engine time progression')
        need(abs(number(clock['callback_time_s'],'callback time')-index*CALLBACK_DT)<=1e-9,'Actual float32 post-step dt progression')
        deep_equal(row['before_step'],previous if previous is not None else baseline,'Consecutive step interval',1e-10)
        previous = clock
        q,qd = vector(row['q_rad'],6),vector(row['qd_rad_s'],6)
        maxima['angle_rad'] = max(maxima['angle_rad'],max(abs(x) for x in q))
        maxima['speed_rad_s'] = max(maxima['speed_rad_s'],max(abs(x) for x in qd))
        need(maxima['angle_rad']<=math.radians(.5) and maxima['speed_rad_s']<=math.radians(1),'Gravity-zero unchanged display pose')
        need(len(row['links'])==7 and {x['name'] for x in row['links']}==set(LINKS),'All actual LINK poses')
        poses = {x['name']:(vector(x['position']),quaternion(x['orientation_wxyz'])) for x in row['links']}
        fk_rows = frames.fk(layout,q)
        fk = {'Base':([0.,0.,0.],IDENTITY),**{f'Link{i}':(r['origin_m'],r['rotation_world']) for i,r in enumerate(fk_rows,1)}}
        for name in LINKS:
            maxima['link_m']=max(maxima['link_m'],error(poses[name][0],fk[name][0]))
            maxima['rotation']=max(maxima['rotation'],error(poses[name][1],fk[name][1]))
        def pose(target):
            if target in paths:
                return poses[paths[target]]
            need(target in (None,'','/World/Robot','/World'),'Unknown root joint target')
            return [0.,0.,0.],IDENTITY
        for joint in [*fixed,*[joints[n] for n in JOINTS]]:
            a,b=frame(pose(joint['body0']),joint,0),frame(pose(joint['body1']),joint,1)
            maxima['anchor_m']=max(maxima['anchor_m'],error(a[0],b[0]))
            rotated=a[1]
            if joint['type']=='revolute':
                i=JOINTS.index(joint['name']);axis=[float(joint['axis']==x) for x in 'XYZ']
                rotated=mm(a[1],frames.rotation(axis,q[i]))
                maxima['axis']=max(maxima['axis'],error(mv(a[1],axis),fk_rows[i]['axis_world']),error(mv(b[1],axis),fk_rows[i]['axis_world']))
            maxima['joint_rotation']=max(maxima['joint_rotation'],error(rotated,b[1]))
        need(maxima['link_m']<=.001 and maxima['anchor_m']<=.001 and max(maxima['rotation'],maxima['joint_rotation'],maxima['axis'])<=.001,'All physical frames/FK/closure/signed axes')
        probe=row['probe_pose'];expected=s['environment']['probe']
        need(error(vector(probe['position']),vector(expected['position']))<=.001 and error(quaternion(probe['orientation_wxyz']),IDENTITY)<=.001,'Gravity-zero probe frame')
    return maxima

def validate_trace(value,facets,api):
    return rows_check(facets['static'],value['rows'],api)

def validate_contact(value,facets,api):
    golden=api['parse'](api['data']['data/golden.json'])['environment']['contact_mapping']
    mapping=value['mapping'];sensors,filters=golden['canonical_sensors'],golden['canonical_filters']
    need(set(mapping)==set(golden),'Complete live contact mapping schema')
    need(mapping['canonical_sensors']==sensors and mapping['canonical_filters']==filters and mapping['capacity']==512 and
         mapping['force_frame']=='WORLD' and mapping['force_units']=='N','Live contact canonical identity/units/capacity')
    need(len(mapping['sensor_paths'])==8 and set(mapping['sensor_paths'])==set(sensors),'All unique actual sensor indices')
    need(len(mapping['filter_paths'])==8 and all(len(row)==9 and set(row)==set(filters) for row in mapping['filter_paths']),'All actual per-sensor filter indices')
    need(value['sensor_count']==8 and value['filter_count']==9 and value['capacity']==512 and
         type(value['engine_event_index']) is int and value['engine_event_index']==10,'Actual view dimensions and final event')
    sample=value['sample'];need(set(sample)=={'normal_force_N','counts','active','dt_s'} and abs(number(sample['dt_s'],'contact dt')-DT)<1e-10,'Actual contact sample schema/dt')
    force,counts=sample['normal_force_N'],sample['counts']
    need(type(force) is list and len(force)==8 and type(counts) is list and len(counts)==8,'Eight contact rows')
    for frow,crow in zip(force,counts):
        need(type(frow) is list and len(frow)==9 and type(crow) is list and len(crow)==9,'Nine contact filters per row')
        for f,c in zip(frow,crow):
            vector(f);need(type(c) is int and 0<=c<512,'Actual contact count range')
    need(type(sample['active']) is list and len(sample['active'])==sum(sum(r) for r in counts)<512,'Complete actual contact buffer')
    tally=[[0]*9 for _ in range(8)];reconstructed=[[[0.]*3 for _ in range(9)] for _ in range(8)]
    for item in sample['active']:
        need(set(item)=={'sensor','filter','force_N','point','normal','separation_m'},'Complete active contact schema')
        i,j=item['sensor'],item['filter'];need(type(i) is int and 0<=i<8 and type(j) is int and 0<=j<9,'Canonical active contact indices')
        need(number(item['force_N'],'force')>=0,'Contact force sign');number(item['separation_m'],'separation');vector(item['point']);vector(item['normal'])
        tally[i][j]+=1
        for axis in range(3):reconstructed[i][j][axis]+=item['force_N']*item['normal'][axis]
    need(tally==counts,'All active contacts match each canonical count')
    need(all(abs(force[i][j][k]-reconstructed[i][j][k])<=1e-6 for i in range(8) for j in range(9) for k in range(3)),'Contact matrix equals scalar force times world normal sum')

def observations(packet,api):
    bindings(api)
    need(set(packet)=={'run_id','job_sha256','pid','usd_sha256','facets'},'Closed robot observation envelope')
    need(packet['run_id']==api['run'].name and packet['job_sha256']==sha(api['run']/'job.json') and
         packet['usd_sha256']==api['job']['inputs']['data/model.usda'],'Source robot observation binding')
    facets=packet['facets'];need(type(facets) is dict and set(facets)==set(api['contract']['facets']),'Every source obligation is present')
    metrics={}
    for name in api['contract']['facets']:
        need(type(facets[name]) is dict and set(facets[name])==set(api['contract']['required_fields'][name]),'Complete facet fields '+name)
        metrics[name]=VALIDATORS[name](facets[name],facets,api)
    return metrics

def consume(records,api):
    records=Path(records);run,job,cfg=api['run'],api['job'],api['cfg'];h=sha(run/'job.json')
    terminal,ex=read(records/'terminal.json'),read(records/'exit.json')
    need(job['stage']=='robot_connection' and terminal['stage']=='robot_connection','Scoped robot stage')
    need(terminal['run_id']==ex['run_id']==run.name and terminal['job_sha256']==ex['job_sha256']==h,'Actual run/job identity')
    need(type(terminal['code']) is int and terminal['code']==0 and type(ex['child_exit_code']) is int and ex['child_exit_code']==0,'Worker/process exit failure dominates')
    need(terminal['status'] in ('CLOSED','COMPLETE_PRE_CLOSE') and terminal['phase'] in ('APP_CLOSED','CLOSING_APP') and ex['status']=='FINISHED','Actual complete lifecycle')
    need(type(terminal['pid']) is int and terminal['pid']>0 and terminal['pid']==ex['child_pid']==ex['worker_pid'] and terminal['parent_pid']==ex['pid'],'Actual direct supervisor/worker PID chain')
    need(terminal['hardware_approved'] is False and terminal['physical_calibration'] is False and terminal['training']=='NOT_RUN','No physical/training authority')
    expected={'observations.json','scene.usda','providers.json','sdk.json'}
    need(set(terminal['files_sha256'])==expected,'All actual robot artifacts')
    for name,value in terminal['files_sha256'].items():need(sha(records/name)==value,'Actual raw hash '+name)
    prereq=records/'prerequisite';expected_prereq={'job.json','terminal.json','exit.json','providers.json','sdk.json','reservation.json'}
    need(set(ex['prerequisite_hashes'])==expected_prereq,'Complete parent prerequisite proof')
    for name,value in ex['prerequisite_hashes'].items():need(sha(prereq/name)==value,'Original prerequisite raw bytes')
    old_job,reservation=read(prereq/'job.json'),read(prereq/'reservation.json')
    need(reservation['stage']=='sdk_preflight' and reservation['run_id']==old_job['run_id'] and
         reservation['job_sha256']==sha(prereq/'job.json') and reservation['input_signature']==api['runner'].signature(job),'Prerequisite reservation/source binding')
    api['runner'].sdk_pass(prereq,old_job,reservation['job_sha256'],api['runner'].signature(job),cfg,api['lib']['providers'])
    providers,sdk=read(records/'providers.json'),read(records/'sdk.json')
    need(providers['pid']==sdk['pid']==terminal['pid'] and providers['job_sha256']==sdk['job_sha256']==h,'Same-process module/SDK evidence')
    need(sdk['version']==cfg['isaac_version'] and owned_origin(sdk['isaacsim_origin'],cfg['isaac_root']) and
         sdk['bootstrap_sha256']=={k:v['sha256'] for k,v in cfg['sdk_files'].items()},'Actual SDK identity')
    for key in ('numeric_before','numeric_after'):check_numeric(providers[key],cfg,need)
    framework=providers['frameworks'];versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','warp':'1.17.0','gymnasium':'1.4.0','rsl_rl':'5.5.1'}
    need(set(framework['modules'])==set(versions) and framework['cuda'].startswith('13.') and framework['sum']==6 and framework['device']=='cuda:0','Actual framework/GPU result')
    for name,version in versions.items():
        item=framework['modules'][name];allowed=cfg['warp_root'] if name=='warp' else cfg['installation_prefix']
        need(item['version']==version and owned_origin(item['origin'],allowed),'Actual framework provider')
    packet=read(records/'observations.json');need(packet['pid']==terminal['pid'],'Actual robot observer process')
    metrics=observations(packet,api)
    return {'status':'ISAACLAB_ROBOT_CONNECTION_VERIFIED','sdk_connected':True,'run_id':run.name,'steps':10,'samples':11,
            'facets_verified':list(api['contract']['facets']),'metrics':metrics,'mass_inertia':'SIMULATION_ASSUMPTION',
            'physical_calibration':False,'hardware_approved':False,'training':'NOT_RUN','weights':None,'ring_geometry':'DEFERRED','settling':'UNRESOLVED_047'}

import math
import struct
from collections import namedtuple
IDENTITY=[[float(i==j) for j in range(3)] for i in range(3)]
LINKS=['Base']+[f'Link{i}' for i in range(1,7)]
JOINTS=[f'J{i}' for i in range(1,7)]
DT=1/120
CALLBACK_DT=struct.unpack('f',struct.pack('f',DT))[0]
VALIDATORS={'static':validate_static,'bodies':validate_bodies,'trace':validate_trace,'contact':validate_contact}

Snapshot=namedtuple("Snapshot","run job_hash pins job data cfg")


def check_numeric(value,cfg,need):
    need(set(value)=={'numpy_version','scipy_version','numpy_origin','scipy_origin','fft_extension','fft','rotation','loaded_numeric_modules'},'Complete numerical provider contract')
    need(value['numpy_version']=='2.3.1' and value['scipy_version']=='1.17.0','Numerical provider versions')
    nr,sr=Path(cfg['numpy_root']),Path(cfg['scipy_root'])
    need(owned_origin(value['numpy_origin'],nr) and owned_origin(value['fft_extension'],nr) and owned_origin(value['scipy_origin'],sr),'Single SDK NumPy/SciPy roots')
    need(type(value['loaded_numeric_modules']) is dict and {'numpy','scipy','numpy.fft._pocketfft_umath'}<=set(value['loaded_numeric_modules']),'Actual loaded numerical module inventory')
    for name,path in value['loaded_numeric_modules'].items():
        need(name=='numpy' or name.startswith('numpy.') or name=='scipy' or name.startswith('scipy.'),'Closed numeric module namespace')
        need(owned_origin(path,nr if name.split('.')[0]=='numpy' else sr),'Mixed numerical provider '+name)
    for actual,expected in ((value['fft'],[[6,0],[-2,2],[-2,0]]),(value['rotation'],[[1,0,0],[0,1,0],[0,0,1]])):
        need(type(actual) is list and len(actual)==len(expected),'Numerical result shape')
        for a,e in zip(actual,expected):
            need(type(a) is list and len(a)==len(e),'Numerical row shape')
            need(all(type(x) in (int,float) and math.isfinite(x) and abs(x-y)<1e-9 for x,y in zip(a,e)),'Actual FFT/Rotation calculation')

def owned_origin(value,root):
    if not isinstance(value,(str,Path)) or not isinstance(root,(str,Path)):return False
    raw=str(value);base=str(root)
    if any(x in ('.','..') for x in re.split(r'[\\/]',raw)) or any(x in ('.','..') for x in re.split(r'[\\/]',base)):return False
    p,r=Path(raw),Path(base)
    return p.is_absolute() and r.is_absolute() and p.resolve().is_relative_to(r.resolve())


def check_frameworks(value,cfg):
    versions={'isaaclab':'3.0.0','torch':'2.11.0+cu130','warp':'1.17.0','gymnasium':'1.4.0','rsl_rl':'5.5.1'}
    need(set(value['modules'])==set(versions) and value['cuda'].startswith('13.') and value['sum']==6 and value['device']=='cuda:0','Actual framework/GPU result')
    for name,version in versions.items():
        item=value['modules'][name];root=cfg['warp_root'] if name=='warp' else cfg['installation_prefix']
        need(item['version']==version and owned_origin(item['origin'],root),'Canonical framework provider '+name)
