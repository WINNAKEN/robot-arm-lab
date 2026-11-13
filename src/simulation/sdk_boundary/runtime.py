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

SOURCE = frozenset(('launch.ps1','runtime.py','native.py','audit.py','config.json','test_boundary.py','README.md'))
FILES = frozenset(('code/runtime.py','code/native.py','code/audit.py','config.json','lib/extract.py',
                  'lib/environment.py','lib/frames.py','data/model.usda','data/golden.json',
                  'data/kinematics.json','data/assumptions.json','prefix-seal.json'))
ROOT = Path(__file__).resolve().parents[3]
OUT = 'outputs/isaac-boundary-v2'


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
    need(set(job) == {'schema_version','run_id','inputs','hardware_approved'} and job['schema_version'] == 1,
         'Closed job schema')
    need(job['run_id'] == run.name and re.fullmatch('[0-9a-f]{32}',run.name) and job['hardware_approved'] is False, 'Job authority')
    need(set(job['inputs']) == FILES, 'Complete mandatory manifest')
    base = run/'input'
    need(all(no_link(p) for p in base.rglob('*')) and
         {p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()} == FILES, 'Exact payload tree')
    data = {name:(base/name).read_bytes() for name in FILES}
    for name, value in data.items():
        need(hashlib.sha256(value).hexdigest() == job['inputs'][name], 'Changed payload '+name)
    need(set(expected_code) == {'code/runtime.py','code/audit.py','code/native.py','config.json'}, 'Literal code inventory')
    for name, value in expected_code.items():
        need(job['inputs'][name] == value, 'Host source authority '+name)
    cfg = parse(data['config.json'].decode())
    need(cfg['hardware_approved'] is False and cfg['calibration_approved'] is False and cfg['training']=='NOT_RUN', 'No physical/training authority')
    need(cfg['steps']==10 and cfg['rate_hz']==120 and cfg['gravity']==[0,0,0] and cfg['cap_Nm']==[3,6,5,2,2,1], 'Fixed connection recipe')
    for name, reference in cfg['references'].items():
        need(job['inputs'][name] == reference['sha256'], 'Source-derived reference '+name)
    need(job['inputs']['prefix-seal.json'] == cfg['installation_seal_sha256'], 'Source-pinned installation seal')
    return job, data, cfg


def compile_module(name, raw, path, api):
    module = types.ModuleType('_checked050_'+name)
    module.__file__ = str(path)
    module.__dict__['API'] = api
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


def api_for(run, job, data, cfg):
    api = {'run':Path(run),'job':job,'cfg':cfg,'data':data,'need':need,'write':write,'read':read,'sha':sha,'parse':parse,
           'runtime':sys.modules.get(__name__), 'lib':{}}
    for name, key in [('frames','lib/frames.py'),('extract','lib/extract.py'),('environment','lib/environment.py'),
                      ('audit','code/audit.py'),('native','code/native.py')]:
        api['lib'][name] = compile_module(name,data[key],Path(run)/'input'/key,api)
    return api


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


def modules(cfg):
    prefix = Path(cfg['installation_prefix']).resolve()
    result = {}
    for name, dist, expected in [('isaaclab','isaaclab','3.0.0'),('torch','torch','2.11.0+cu130'),
                                 ('warp','warp-lang','1.17.0'),('gymnasium','gymnasium','1.4.0'),('rsl_rl','rsl-rl-lib','5.5.1')]:
        item = importlib.import_module(name)
        version = importlib.metadata.version(dist)
        origin = Path(item.__file__).resolve()
        need(origin.is_relative_to(prefix) and version==expected, 'Module provider/version '+name)
        result[name] = {'version':version,'origin':str(origin)}
    torch = importlib.import_module('torch')
    need(torch.cuda.is_available() and torch.version.cuda.startswith('13.'), 'CUDA13 required')
    tensor = torch.ones((2,3),device='cuda:0')
    total = float(tensor.sum().item())
    need(tensor.is_cuda and total==6., 'Actual GPU calculation')
    return {'modules':result,'cuda':torch.version.cuda,'device':str(tensor.device),'sum':total,'pid':os.getpid()}


def literal(run, job_hash, code_hashes, role):
    args = {'run':str(run),'job':job_hash,'code':code_hashes,'role':role}
    payload = base64.b64encode(json.dumps(args).encode()).decode()
    text = ("import base64,json,pathlib,hashlib\n"+f"a=json.loads(base64.b64decode('{payload}'))\n"
            +"p=pathlib.Path(a['run'])/'input/code/runtime.py';b=p.read_bytes()\n"
            +"if hashlib.sha256(b).hexdigest()!=a['code']['code/runtime.py']:raise SystemExit('Root changed')\n"
            +"n={'__name__':'_remote050','__file__':str(p)}\nexec(compile(b,str(p),'exec'),n)\n"
            +"raise SystemExit(n['entry'](pathlib.Path(a['run']),a['job'],a['code'],a['role']))\n")
    return "import base64;exec(base64.b64decode('"+base64.b64encode(text.encode()).decode()+"'))"


def entry(run, expected_job, expected_code, role):
    job, data, cfg = checked(run,expected_job,expected_code)
    out = run/'output'
    out.mkdir(exist_ok=True)
    if role == 'export':
        with zipfile.ZipFile(run/'records.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for p in out.rglob('*'):
                if p.is_file():
                    archive.write(p,p.relative_to(out).as_posix())
        return 0
    if role == 'supervise':
        return supervise(run,expected_job,expected_code,cfg)
    need(role == 'native', 'Closed remote phase')
    verify_prefix(cfg['installation_prefix'],data['prefix-seal.json'])
    sdk_namespace = sdk_initialize(cfg)
    sys.path.insert(0,str(Path(cfg['installation_prefix']).resolve()))
    api = api_for(run,job,data,cfg)
    api['sdk_namespace'] = sdk_namespace
    api['modules'] = lambda:modules(cfg)
    return api['lib']['native'].run(api)


def supervise(run, job_hash, code_hashes, cfg):
    need(run.parent==Path(cfg['remote_root']).resolve() and cfg['native_limit']==2 and cfg['timeout_s']==600, 'Owned finite scope')
    out = run/'output'
    ledger, lock = run.parent/'native-attempts.json', run.parent/'native-launch.lock'
    handle, process, code = None, None, 1
    started = time.time()
    try:
        handle = lock.open('x')
        handle.write(str(os.getpid())); handle.flush()
        attempts = read(ledger) if ledger.exists() else []
        need(type(attempts) is list and len(attempts)<2 and not (out/'terminal.json').exists(), 'Attempt budget or repeat')
        attempts.append({'run_id':run.name,'job_sha256':job_hash,'reserved_unix':time.time()})
        write(ledger,attempts)
        query = subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',"@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count"],capture_output=True,timeout=20)
        need(query.returncode==0 and query.stdout.strip()==b'0', 'Existing Kit session')
        argv = [str(Path(cfg['isaac_root'])/'kit/python/python.exe'),'-I','-B','-c',literal(run,job_hash,code_hashes,'native')]
        with (out/'stdout.txt').open('xb') as so, (out/'stderr.txt').open('xb') as se:
            process = subprocess.Popen(argv,stdout=so,stderr=se,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            write(out/'supervisor.json',{'run_id':run.name,'job_sha256':job_hash,'pid':os.getpid(),'child_pid':process.pid,'status':'RUNNING'})
            try:
                code = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                cleanup = subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                write(out/'timeout.json',{'owned_pid':process.pid,'cleanup_exit':cleanup.returncode})
                process.wait(timeout=15)
                code = 124
    except Exception as exc:
        write(out/'supervisor-failure.json',{'reason':repr(exc),'code':1})
        code = 1
    finally:
        terminal = read(out/'terminal.json') if (out/'terminal.json').exists() else {}
        envelope = {'run_id':run.name,'job_sha256':job_hash,'pid':os.getpid(),
                    'child_pid':process.pid if process else None,'worker_pid':terminal.get('pid'),
                    'status':'FINISHED','child_exit_code':int(code),'started_unix':started,'finished_unix':time.time()}
        write(out/'supervisor.json',envelope)
        write(out/'exit.json',envelope)
        if handle:
            handle.close(); lock.unlink()
    return int(code)


def remote(script, alias, timeout=900):
    encoded = base64.b64encode(script.encode('utf-16le')).decode()
    p = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15',alias,
                        'powershell','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=timeout)
    return p


def prepare(root, source):
    cfg = parse(source['config.json'].decode())
    out = root/OUT
    run = out/'runs'/uuid.uuid4().hex
    (run/'input/code').mkdir(parents=True)
    try:
        for name in ('runtime.py','audit.py','native.py'):
            (run/'input/code'/name).write_bytes(source[name])
        (run/'input/config.json').write_bytes(source['config.json'])
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
        job = {'schema_version':1,'run_id':run.name,'inputs':{k:sha(run/'input'/k) for k in sorted(FILES)},'hardware_approved':False}
        write(run/'job.json',job,True)
        pins = {k:job['inputs'][k] for k in ('code/runtime.py','code/native.py','code/audit.py','config.json')}
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


def public(role, run_dir):
    folder = Path(__file__).resolve().parent
    isolated([ROOT,folder])
    source = source_bytes(folder)
    if role == 'test':
        runtime = types.SimpleNamespace(**globals())
        api = {'runtime':runtime,'source':source,'root':ROOT,'folder':folder}
        tests = compile_module('tests',source['test_boundary.py'],folder/'test_boundary.py',api)
        return tests.run_tests()
    if role == 'prepare':
        print(prepare(ROOT,source))
        return 0
    need(role in ('native','verify') and run_dir, 'Owned run required')
    run = Path(run_dir).resolve()
    prepared = read(run/'prepared.json')
    pins = {('config.json' if n=='config.json' else 'code/'+n):hashlib.sha256(source[n]).hexdigest()
            for n in ('runtime.py','audit.py','native.py','config.json')}
    job, data, cfg = checked(run,prepared['job_sha256'],pins)
    need(prepared['code']==pins and prepared['run_id']==run.name and prepared['remote']==cfg['remote_root']+'/'+run.name,'Host preparation binding')
    try:
        if role == 'native':
            launch(run,prepared,cfg)
        api = api_for(run,job,data,cfg)
        result = api['lib']['audit'].consume(run/'retrieved',api)
        write(run/'validation.json',result)
        write(run.parent.parent/'current.json',result)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        write(run.parent.parent/'current.json',{'status':'FAILED','run_id':run.name,'reason':repr(exc),'hardware_approved':False})
        print(repr(exc),file=sys.stderr)
        return 1
