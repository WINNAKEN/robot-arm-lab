"""069 transport. No SDK is imported by this module or by host validation."""
import base64
import ctypes
import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import types
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = 'outputs/isaac-hold-diagnostic-098'
SOURCE_A = {'driver.py', 'sdk.py', 'validate.py', 'test_host.py', 'launch.ps1', 'config.json'}
SOURCE_B = {'scene.py', 'capture.py', 'program.json', 'test_scene.py', 'README.md', 'workspace.py', 'init_boundary.py', 'torque.py', 'reference.py', 'balance.py', 'root_binding.py', 'recovery.py'}
SOURCE = SOURCE_A | SOURCE_B
MODEL = {'robot_arm.urdf', 'asset-ledger.json', 'manifest.json', 'provenance.json', 'README.md'} | {
    'meshes/' + n + '.stl' for n in ('Base', 'Link1', 'Link2', 'Link3', 'Link4', 'Link5', 'Link6', 'KG1', 'KG1_A', 'KG1_B', 'KG1_R')}
PURPOSES = ('import', 'render_smoke', 'motion')
EXPERIMENT = 'hold_diagnostic_098'
PLAN_SHA = 'fc69b7ba326b74399f53fa04cf729ca9f4ada3dd7e31ba66e5773406557efe24'
RECOVERY_SHA = '8111c2c657f2652bf2cfd84630f0ad3110bc48102189296b738977c0d4065315'
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
PROOF = {'job.json', 'terminal.json', 'exit.json', 'remote-shell.json', 'static.json', 'report.json', 'model.usda'}
UNSEALED = {'terminal.json', 'status.json', 'stdout.txt', 'stderr.txt', 'exit.json', 'remote-shell.json', 'child-started.json', 'recovery-manifest.json'}
RENDER_ERRORS = ('renderer failed to advance to the scheduled frame', 'Orchestrator failed to schedule a capture')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def parse(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate JSON key: ' + key)
            out[key] = value
        return out
    def finite_float(text):
        value = float(text)
        need(math.isfinite(value), 'Nonfinite JSON number')
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def read(path):
    return parse(Path(path).read_bytes().decode('utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def load_module(name, raw, path):
    module = types.ModuleType('_checked069_' + name)
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


class VerifiedSource(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Bare imports resolve only to bytes already read by the closed snapshot."""
    def __init__(self, ctx):
        self.ctx = ctx
        self.modules = {Path(name).stem: (name, ctx.data['source/' + name])
                        for name in SOURCE if name.endswith('.py')}

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.modules:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name, raw = self.modules[module.__name__]
        module.__file__ = str(self.ctx.run / 'input/source' / name)
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)


def bind_sources(ctx):
    source = str(ctx.run / 'input/source')
    sys.path[:] = [item for item in sys.path if item != source]
    sys.path.insert(0, source)
    sys.meta_path[:] = [item for item in sys.meta_path if not getattr(item, '_verified069', False)]
    finder = VerifiedSource(ctx)
    finder._verified069 = True
    for name in finder.modules:
        sys.modules.pop(name, None)
    sys.meta_path.insert(0, finder)


def relative(value):
    return (type(value) is str and bool(value) and '\\' not in value and ':' not in value
            and not value.startswith('/') and all(p not in ('', '.', '..') for p in value.split('/')))


def hash_string(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def no_link(path):
    path = Path(path)
    return not path.is_symlink() and not (hasattr(path, 'is_junction') and path.is_junction())


def checked_path(root, value):
    need(relative(value), 'Relative path without traversal required')
    root = Path(root)
    need(root.is_absolute(), 'Absolute root required')
    need(no_link(root) and all(no_link(p) for p in root.parents), 'Root ancestry link')
    path = root.joinpath(*value.split('/'))
    need(all(no_link(p) for p in (path, *path.parents)), 'Payload ancestry link')
    need(path.resolve().is_relative_to(root.resolve()), 'Path escapes absolute root')
    return path


def file_bytes(folder):
    folder = Path(folder)
    need(folder.is_absolute() and folder.is_dir(), 'Absolute existing directory required')
    need(no_link(folder) and all(no_link(p) for p in folder.parents), 'Directory ancestry link')
    result = {}
    for path in folder.rglob('*'):
        need(no_link(path), 'Directory/file link')
        need(path.is_dir() or path.is_file(), 'Regular input only')
        if path.is_file():
            key = path.relative_to(folder).as_posix()
            checked_path(folder, key)
            result[key] = path.read_bytes()
    return result



def effective_clock(record,wall,mono):
    for value in (wall,mono,record['started_unix'],record['started_monotonic']):
        need(type(value) in (int,float) and math.isfinite(value),'Finite nonbool clock anchor')
    elapsed=mono-record['started_monotonic'];need(elapsed>=0,'Monotonic anchor after reboot/backward')
    expected=record['started_unix']+elapsed
    need(abs(wall-expected)<=.25,'Local wall/monotonic clock uncertainty')
    return expected

def session_now(cfg):
    folder=ROOT/OUT;b=read(folder/'runtime-budget.json');ready=read(folder/'activation.json')
    need(b['unit']=='098' and b['duration_s']==2700 and b['deadline_unix']==b['started_unix']+2700==cfg['deadline_unix']
         and b['hardware_approved'] is False and b['plan_sha256']==PLAN_SHA,'Bound absolute098 budget')
    need(ready['status']=='READY' and ready['runtime_budget_sha256']==sha(folder/'runtime-budget.json')
         and read(Path(__file__).parent/'config.json')['deadline_unix']==cfg['deadline_unix']
         and b['execution_source']['config.json']==sha(Path(__file__).parent/'config.json')
         and b['execution_source']['driver.py']==sha(Path(__file__)),'Active local source/budget pins')
    return effective_clock(b,time.time(),time.monotonic())

def clock_bounds(cert):
    need(type(cert) is dict and set(cert)=={'run_id','job_sha256','deadline_unix','local_send_unix','local_receive_unix','local_elapsed_s','remote_unix','remote_uptime_ms'},'Closed admission clock certificate')
    for key in ('deadline_unix','local_send_unix','local_receive_unix','local_elapsed_s','remote_unix'):
        need(type(cert[key]) in (int,float) and math.isfinite(cert[key]),'Finite clock field '+key)
    need(type(cert['remote_uptime_ms']) is int and cert['remote_uptime_ms']>=0,'Typed remote uptime')
    sent,received=cert['local_send_unix'],cert['local_receive_unix']
    need(received>=sent and cert['local_elapsed_s']>=0 and abs(received-sent-cert['local_elapsed_s'])<=.25,'Local probe clock coherence')
    low,high=cert['remote_unix']-received-.002,cert['remote_unix']-sent+.002
    need(-1<=low<=high<=1,'Remote clock offset uncertainty exceeds one second')
    return low,high

def uptime_ms():
    need(os.name=='nt','Windows uptime witness required')
    getter=ctypes.windll.kernel32.GetTickCount64;getter.restype=ctypes.c_ulonglong
    return int(getter())

def remote_clock_now(ctx):
    cert=ctx.admission;clock_bounds(cert)
    need(cert['run_id']==ctx.run.name and cert['job_sha256']==ctx.job_hash and cert['deadline_unix']==ctx.cfg['deadline_unix'],'Clock certificate run/job/deadline')
    now=time.time();age=(uptime_ms()-cert['remote_uptime_ms'])/1000
    need(0<=age<=120 and abs(now-cert['remote_unix']-age)<=.25,'Remote uptime age/wall-jump witness')
    return now+2

def clock_probe(ctx):
    paths=[ctx.run/('clock-query'+suffix) for suffix in ('-stdout.txt','-stderr.txt','.json','-failure.json')]
    need(not any(p.exists() for p in paths),'Clock query already consumed; no overwrite/retry')
    session_now(ctx.cfg);sent=time.time();mono=time.monotonic();result=None;received=None;elapsed=None
    # Windows PowerShell5.1 lacks Environment.TickCount64. Query the same Win32
    # witness through existing isolated Python with site/SDK startup disabled.
    code="import ctypes,json,sys,time;g=ctypes.windll.kernel32.GetTickCount64;g.restype=ctypes.c_ulonglong;print(json.dumps({'remote_unix':time.time(),'remote_uptime_ms':int(g()),'kit_count':int(sys.argv[1])}))"
    token=base64.b64encode(code.encode()).decode();python=str(Path(ctx.cfg['sdk']['isaac_root'])/'kit/python/python.exe')
    need("'" not in python,'Clock executable quote')
    command="$n=@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count;& '"+python+"' -I -S -B -c \"import base64;exec(base64.b64decode('"+token+"'))\" $n;exit $LASTEXITCODE"
    def record(path,value):
        with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False)
    def raw_files(stdout,stderr):
        for path,value in zip(paths[:2],(stdout,stderr)):
            if not path.exists():
                with path.open('xb') as stream:stream.write(value.encode() if isinstance(value,str) else value or b'')
    try:
        result=remote(command,ctx.cfg['ssh_alias'],20)
        received=time.time();elapsed=time.monotonic()-mono
        raw_files(result.stdout,result.stderr)
        record(paths[2],{'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'deadline_unix':ctx.cfg['deadline_unix'],
                         'local_send_unix':sent,'local_receive_unix':received,'local_elapsed_s':elapsed,'returncode':result.returncode,'SimulationApp_started':False})
        session_now(ctx.cfg)
        need(result.returncode==0,'Remote clock OS query failed')
        raw=parse(result.stdout.decode('utf-8-sig'))
        need(set(raw)=={'remote_unix','remote_uptime_ms','kit_count'} and type(raw['kit_count']) is int and raw['kit_count']==0,'Existing Kit process; do not disturb')
        cert={'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'deadline_unix':ctx.cfg['deadline_unix'],
              'local_send_unix':sent,'local_receive_unix':received,'local_elapsed_s':elapsed,
              'remote_unix':raw['remote_unix'],'remote_uptime_ms':raw['remote_uptime_ms']}
        clock_bounds(cert);return cert
    except Exception as exc:
        try:
            if received is None:
                received=time.time();elapsed=time.monotonic()-mono
            raw_files(getattr(exc,'stdout',b'') if result is None else result.stdout,getattr(exc,'stderr',b'') if result is None else result.stderr)
            if not paths[2].exists():
                record(paths[2],{'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'deadline_unix':ctx.cfg['deadline_unix'],
                                 'local_send_unix':sent,'local_receive_unix':received,'local_elapsed_s':elapsed,
                                 'returncode':None if result is None else result.returncode,'timed_out':isinstance(exc,subprocess.TimeoutExpired),'SimulationApp_started':False})
            record(paths[3],{'status':'CLOCK_QUERY_REJECTED','error':repr(exc),'run_id':ctx.run.name,'job_sha256':ctx.job_hash,
                             'local_send_unix':sent,'local_receive_unix':received,'local_elapsed_s':elapsed,'SimulationApp_started':False})
        except Exception as diagnostic:
            print('CLOCK_DIAGNOSTIC_FAILURE primary='+repr(exc)+' secondary='+repr(diagnostic),file=sys.stderr,flush=True)
        raise

def own_source(folder):
    source = file_bytes(Path(folder).absolute())
    need(set(source) == SOURCE, 'Exact source18 inventory')
    return source


def phase_limits(cfg,purpose):
    need(type(purpose) is str and purpose in PURPOSES,'Closed timing purpose')
    for key,value in (('timeout_s',600),('motion_timeout_s',900),('motion_launch_headroom_s',1680),('minimum_launch_headroom_s',1380)):
        need(type(cfg.get(key)) is int and cfg[key]==value,'Typed fixed timing '+key)
    return (cfg['motion_timeout_s'],cfg['motion_launch_headroom_s']) if purpose=='motion' else (cfg['timeout_s'],cfg['minimum_launch_headroom_s'])


def launch_budget(cfg,purpose,now=None):
    timeout,headroom=phase_limits(cfg,purpose)
    need(type(cfg.get('deadline_unix')) in (int,float) and math.isfinite(cfg['deadline_unix']) and cfg['deadline_unix']>0,'Inactive absolute deadline')
    current=session_now(cfg) if now is None else now
    end=cfg['deadline_unix']
    need(type(current) in (int,float) and math.isfinite(current)
         and type(end) in (int,float) and math.isfinite(end) and current+headroom<end,'Purpose launch headroom')
    return timeout


def native_timeout(cfg,purpose,now=None):
    timeout,_=phase_limits(cfg,purpose)
    current=session_now(cfg) if now is None else now
    end=cfg['deadline_unix']
    need(type(current) in (int,float) and math.isfinite(current)
         and type(end) in (int,float) and math.isfinite(end),'Typed absolute deadline')
    remaining=min(timeout,end-current-30)
    need(remaining>0,'Native absolute deadline')
    return remaining


def transport_timeout(cfg,purpose):return phase_limits(cfg,purpose)[0]+150


def config_contract(cfg):
    need(type(cfg) is dict and cfg.get('experiment_id') == EXPERIMENT, 'Explicit new gravity/workspace experiment')
    need(type(cfg.get('remote_root')) is str and re.fullmatch('[A-Za-z]:/isaacsim_remote/robot-arm-lab/098/runs',cfg['remote_root']), 'Fixed new experiment root; old ledgers untouched')
    need(type(cfg.get('ssh_alias')) is str and re.fullmatch('[A-Za-z0-9_-]+',cfg['ssh_alias']), 'SSH endpoint')
    phase_limits(cfg, 'import')
    recovery_limits(cfg)
    need(cfg.get('offline_only') is False and cfg.get('native_limits')=={'import':1,'render_smoke':1,'motion':1}
         and all(type(v) is int for v in cfg['native_limits'].values()),'098 bounded native authority')
    need(cfg.get('model_dir')=='models/robot-arm-urdf-v3' and type(cfg.get('sdk')) is dict, 'Model and SDK')
    need(cfg.get('hardware_approved') is False and cfg.get('physical_calibration') is False and cfg.get('training')=='NOT_RUN', 'Simulation-only authority')
    need(cfg['sdk'].get('hardware_approved') is False and cfg['sdk'].get('calibration_approved') is False and cfg['sdk'].get('training')=='NOT_RUN','Nested SDK authority')
    refs=cfg.get('refs');need(type(refs) is dict and refs,'Pinned references')
    for key,item in refs.items():
        need(relative(key) and type(item) is dict and set(item)=={'path','sha256'} and relative(item['path']) and hash_string(item['sha256']),'Closed reference pin')
    item=cfg.get('model_submission');need(type(item) is dict and set(item)=={'path','sha256'} and relative(item['path']) and hash_string(item['sha256']),'Approved model submission')
    need('workspace.json' in refs,'Pinned actual sampled workspace')


def common_signature(inputs):
    common = {key: value for key, value in inputs.items()
              if key.startswith(('model/', 'ref/')) or key in {'source/' + n for n in SOURCE_A}}
    need({'source/' + n for n in SOURCE_A} <= set(common), 'Missing common source core')
    return digest(json.dumps(common, sort_keys=True, separators=(',', ':')).encode())


def job_contract(job, run_name):
    need(type(job) is dict and set(job) == {'schema_version', 'run_id', 'purpose', 'inputs', 'common_signature', 'plan_sha256', 'hardware_approved', 'experiment_id'}, 'Closed job schema')
    need(type(job['schema_version']) is int and job['schema_version'] == 1, 'Typed job version')
    need(job['run_id'] == run_name and re.fullmatch('[0-9a-f]{32}', run_name), 'Run identity')
    need(job['purpose'] in PURPOSES and job['hardware_approved'] is False and job['plan_sha256'] == PLAN_SHA and job['experiment_id']==EXPERIMENT, 'Closed experiment/purpose/authority')
    need(type(job['inputs']) is dict and all(relative(k) and hash_string(v) for k, v in job['inputs'].items()), 'Typed input hash mapping')
    need(hash_string(job['common_signature']) and common_signature(job['inputs']) == job['common_signature'], 'Common signature')


def snapshot(run, job_hash, expected_driver_sha=None):
    run = Path(run)
    need(run.is_absolute() and no_link(run) and all(no_link(p) for p in run.parents), 'Absolute run without ancestry links')
    raw = checked_path(run, 'job.json').read_bytes()
    need(hash_string(job_hash) and digest(raw) == job_hash, 'Pinned single-read job')
    job = parse(raw)
    job_contract(job, run.name)
    data = file_bytes(run / 'input')
    need(set(data) == set(job['inputs']) and all(digest(raw) == job['inputs'][key] for key, raw in data.items()), 'Exact hashed input inventory')
    need({'source/' + n for n in SOURCE} <= set(data), 'Every source module required before imports')
    if expected_driver_sha is not None:
        need(job['inputs']['source/driver.py'] == expected_driver_sha, 'Pinned executable driver')
    cfg = parse(data['source/config.json'])
    config_contract(cfg)
    expected = {'source/' + n for n in SOURCE} | {'model/' + n for n in MODEL} | {'ref/' + n for n in cfg['refs']}
    if job['purpose'] in ('render_smoke','motion'):
        expected |= {'import-proof/' + n for n in PROOF}
    if job['purpose']=='motion':
        expected |= {n for n in data if n.startswith('smoke-proof/')}
    if job['purpose']!='import':expected |= {n for n in data if n.startswith('retry-proof/')}
    need(set(data) == expected, 'Closed payload inventory/model full sixteen')
    need(all(job['inputs']['ref/' + key] == value['sha256'] for key, value in cfg['refs'].items()), 'Pinned reference content')
    matched = [key for key, value in cfg['refs'].items() if value == cfg['model_submission']]
    need(len(matched) == 1, 'Submission must be included in pinned references')
    submission = parse(data['ref/' + matched[0]])
    need(type(submission) is dict and type(submission.get('source_and_evidence_files')) is dict,
         'Pinned submission model inventory')
    prefix = cfg['model_dir'] + '/'
    model_pins = {key[len(prefix):]: value for key, value in submission['source_and_evidence_files'].items()
                  if key.startswith(prefix)}
    need(set(model_pins) == MODEL, 'Submission binds exactly all sixteen model files')
    for name, pin in model_pins.items():
        raw_model = data['model/' + name]
        need(type(pin) is dict and set(pin) == {'sha256', 'bytes'} and hash_string(pin['sha256'])
             and type(pin['bytes']) is int and pin['bytes'] == len(raw_model)
             and pin['sha256'] == digest(raw_model), 'Submitted model SHA/byte binding: ' + name)
    need(hash_string(submission.get('canonical_urdf_sha256'))
         and submission['canonical_urdf_sha256'] == digest(data['model/robot_arm.urdf']),
         'Submitted canonical XML SHA binding')
    ctx = types.SimpleNamespace(run=run, job=job, job_hash=job_hash, cfg=cfg)
    ctx.data = data
    if job['purpose'] in ('render_smoke','motion'):
        verify_import_proof(ctx, {n: data['import-proof/' + n] for n in PROOF})
    if job['purpose']=='motion':verify_smoke_proof(ctx)
    if any(n.startswith('retry-proof/') for n in data):verify_retry(ctx)
    return ctx


def load(ctx):
    """Re-read and verify all inputs before loading any source module."""
    return snapshot(ctx.run, ctx.job_hash)


def identity(item, job, job_hash):
    need(type(item) is dict and item.get('run_id') == job['run_id'] and item.get('job_sha256') == job_hash, 'Record run/job binding')


def process_contract(job, job_hash, terminal, ex, shell, allow_one=False):
    for item in (terminal, ex, shell):
        identity(item, job, job_hash)
    for key in ('pid', 'child_pid', 'actual_child_exit_code', 'policy_exit_code'):
        need(type(ex.get(key)) is int, 'Typed parent process field ' + key)
    need(ex['pid'] > 0 and ex['child_pid'] > 0 and ex['purpose'] == job['purpose'], 'Parent process purpose')
    need(ex.get('timed_out') is False and ex.get('child_state') == 'REAPED', 'Child actually reaped without timeout')
    need(type(shell.get('python_exit_code')) is int and type(terminal.get('code')) is int, 'Typed shell/native code')
    need(type(terminal.get('pid')) is int and type(terminal.get('parent_pid')) is int, 'Typed native PID chain')
    need(terminal['pid'] == ex['child_pid'] and terminal['parent_pid'] == ex['pid'] and terminal.get('purpose') == job['purpose'], 'Direct native PID chain')
    code = ex['actual_child_exit_code']
    need(code in ((0, 1) if allow_one else (0,)) and code == ex['policy_exit_code'] == shell['python_exit_code'] == terminal['code'], 'Actual child/policy/shell/native code')
    need(terminal.get('status') in ('CLOSED', 'COMPLETE_PRE_CLOSE'), 'Native lifecycle complete')
    return code


def verify_import_proof(ctx, raws):
    need(set(raws) == PROOF, 'Exact original import proof')
    old = parse(raws['job.json'])
    job_contract(old, old.get('run_id', ''))
    need(old['purpose'] == 'import' and old['common_signature'] == ctx.job['common_signature'], 'Same common-signature original import')
    h = digest(raws['job.json'])
    terminal, ex, shell = (parse(raws[n]) for n in ('terminal.json', 'exit.json', 'remote-shell.json'))
    process_contract(old, h, terminal, ex, shell)
    pins = terminal.get('files_sha256')
    need(type(pins) is dict and all(relative(n) and hash_string(v) for n, v in pins.items()), 'Original import terminal hashes')
    need({'static.json', 'report.json', 'model.usda'} <= set(pins), 'Import artifacts sealed')
    need(all(digest(raws[n]) == pins[n] for n in ('static.json', 'report.json', 'model.usda')), 'Original import artifact hashes')
    return old


def b_signature(inputs):
    return digest(json.dumps({n:inputs['source/'+n] for n in sorted(SOURCE_B)},sort_keys=True,separators=(',',':')).encode())


def verify_retry(ctx):
    names={'job.json','terminal.json','exit.json','remote-shell.json','review.json'}
    raws={n[12:]:b for n,b in ctx.data.items() if n.startswith('retry-proof/')}
    need(set(raws)==names,'Exact failed integration/review proof')
    old=parse(raws['job.json']);job_contract(old,old.get('run_id',''));h=digest(raws['job.json'])
    need(old['purpose']==ctx.job['purpose'] and old['purpose']!='import' and old['common_signature']==ctx.job['common_signature'],'Same-stage failed integration with unchanged domain')
    terminal,ex,shell=(parse(raws[n]) for n in ('terminal.json','exit.json','remote-shell.json'))
    for item in (terminal,ex,shell):identity(item,old,h)
    for item,key in ((terminal,'pid'),(terminal,'parent_pid'),(terminal,'code'),(ex,'pid'),(ex,'child_pid'),(ex,'actual_child_exit_code'),(ex,'policy_exit_code'),(shell,'python_exit_code')):need(type(item.get(key)) is int,'Typed failed integration process')
    need(terminal['pid']==ex['child_pid']>0 and terminal['parent_pid']==ex['pid']>0,'Failed integration direct PID chain')
    need(terminal['purpose']==ex['purpose']==old['purpose'] and terminal['status']=='FAILED' and terminal['code']==ex['actual_child_exit_code']==ex['policy_exit_code']==shell['python_exit_code']==1,'Actual native integration failure; no valid dynamics retune')
    need(ex['timed_out'] is False and ex['child_state']=='REAPED' and terminal.get('primary_phase')=='COLLECTOR','Completed failed integration collector')
    need(type(terminal.get('primary_error')) is str and terminal['primary_error'] and not any(x in terminal['primary_error'].lower() for x in ('original cap','gravity query differs','velocity limit','joint limit','fk/axis')),'Not load/trajectory/physics retuning')
    need(b_signature(old['inputs'])!=b_signature(ctx.job['inputs']),'Actual limited B source repair required')
    review=parse(raws['review.json']);need(type(review) is dict and set(review)=={'verdict','phase','reviewer','failed_run_id','source_b_signature','new_defect_union'},'Closed repair review')
    need(review['verdict']=='PASS' and review['phase']=='L4' and type(review['reviewer']) is str and review['reviewer'] and review['reviewer']!='author' and review['failed_run_id']==old['run_id'] and review['source_b_signature']==b_signature(ctx.job['inputs']) and type(review['new_defect_union']) is int and review['new_defect_union']==0,'Non-author PASS bound to repaired source and original failure')
    return old


def verify_smoke_proof(ctx):
    raws={n[12:]:b for n,b in ctx.data.items() if n.startswith('smoke-proof/')}
    need({'job.json','terminal.json','exit.json','remote-shell.json','report.json','scene.usda','stdout.txt','stderr.txt'}<=set(raws),'Original smoke raw tree')
    old=parse(raws['job.json']);job_contract(old,old.get('run_id',''));need(old['purpose']=='render_smoke' and old['common_signature']==ctx.job['common_signature'] and b_signature(old['inputs'])==b_signature(ctx.job['inputs']),'Exact same-domain and B implementation smoke')
    terminal,ex,shell=(parse(raws[n]) for n in ('terminal.json','exit.json','remote-shell.json'));process_contract(old,digest(raws['job.json']),terminal,ex,shell)
    pins=terminal.get('files_sha256');need(type(pins) is dict and set(pins)==set(raws)-UNSEALED-{'job.json'} and all(relative(n) and hash_string(v) and digest(raws[n])==v for n,v in pins.items()),'Complete unchanged native smoke artifacts')
    need(not any(t.lower() in (raws['stdout.txt']+raws['stderr.txt']).decode('utf-8',errors='replace').lower() for t in RENDER_ERRORS),'No smoke renderer softfailure')
    module=load_module('smoke_verify',ctx.data['source/validate.py'],ctx.run/'input/source/validate.py')
    metrics=module.verify_simulation(ctx.run/'input/model/robot_arm.urdf',parse(raws['report.json']),ctx.cfg,ctx.run/'input/smoke-proof',purpose='render_smoke')
    need(metrics['dynamics_pass'] is True,'Native physics/render smoke full acceptance')
    return old


def portable_policy(actual):
    return (actual, 'WORKER_EXIT') if type(actual) is int and 0 <= actual <= 255 else (1, 'NONPORTABLE_WORKER_EXIT')


def stop_and_reap(child, result):
    try:
        if os.name == 'nt':
            result['cleanup_exit_code'] = subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True, timeout=15, creationflags=HIDDEN).returncode
        else:
            child.kill()
            result['cleanup_exit_code'] = 0
    except Exception as exc:
        result['cleanup_error'] = repr(exc)
    try:
        result['actual_child_exit_code'] = child.wait(timeout=15)
    except Exception as exc:
        result['reap_error'] = repr(exc)
        result['actual_child_exit_code'] = child.poll()
    result['child_state'] = 'REAPED' if result['actual_child_exit_code'] is not None else 'RUNNING_OR_NOT_REAPED'


def run_child(argv, out, timeout, admit=None):
    child = None
    result = {'child_pid': None, 'actual_child_exit_code': None, 'policy_exit_code': 1,
              'policy_basis': 'NOT_STARTED', 'timed_out': False, 'child_state': 'NOT_STARTED'}
    started = time.monotonic()
    awake = False
    try:
        if os.name == 'nt':
            need(ctypes.windll.kernel32.SetThreadExecutionState(0x80000003) != 0, 'Process-scoped keep-awake failed')
            awake = True
        with (out / 'stdout.txt').open('xb') as stdout, (out / 'stderr.txt').open('xb') as stderr:
            if admit is not None:admit()
            child = subprocess.Popen(argv, stdout=stdout, stderr=stderr, creationflags=HIDDEN)
            result['child_pid'] = child.pid
            write(out / 'child-started.json', {'pid': child.pid, 'parent_pid': os.getpid(), 'started_unix': time.time()})
            try:
                result['actual_child_exit_code'] = child.wait(timeout=timeout)
                result['policy_exit_code'], result['policy_basis'] = portable_policy(result['actual_child_exit_code'])
                result['child_state'] = 'REAPED'
            except subprocess.TimeoutExpired:
                result.update(timed_out=True, policy_exit_code=124, policy_basis='TIMEOUT')
                stop_and_reap(child, result)
    except Exception as exc:
        result['observation_error'] = repr(exc)
        if not result['timed_out']:
            result.update(policy_exit_code=1, policy_basis='OBSERVATION_FAILURE')
        if child is not None and result['actual_child_exit_code'] is None:
            stop_and_reap(child, result)
    finally:
        if awake:
            result['keep_awake_reset'] = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
    result['duration_s'] = time.monotonic() - started
    return result


def reserve(ctx, ledger):
    need(type(ledger) is dict and set(ledger)=={'schema_version','experiment_id','reservations'} and type(ledger['schema_version']) is int and ledger['schema_version']==1 and ledger['experiment_id']==EXPERIMENT,'Explicit new experiment ledger')
    rows=ledger['reservations'];need(type(rows) is list,'Reservation list');runs=set();jobs=set();counts={p:0 for p in PURPOSES}
    for row in rows:
        need(type(row) is dict and set(row)=={'purpose','run_id','job_sha256','common_signature','reserved_unix'},'Reservation schema')
        need(row['purpose'] in PURPOSES and type(row['run_id']) is str and re.fullmatch('[0-9a-f]{32}',row['run_id']) and hash_string(row['job_sha256']) and hash_string(row['common_signature']),'Reservation identity')
        need(type(row['reserved_unix']) in (int,float) and math.isfinite(row['reserved_unix']) and row['run_id'] not in runs and row['job_sha256'] not in jobs,'Unique typed reservations');runs.add(row['run_id']);jobs.add(row['job_sha256']);counts[row['purpose']]+=1
    need(all(counts[p]<=ctx.cfg['native_limits'][p] for p in PURPOSES),'No exceeded existing purpose')
    purpose=ctx.job['purpose'];need(counts[purpose]<ctx.cfg['native_limits'][purpose] and ctx.run.name not in runs and ctx.job_hash not in jobs,'Remaining unique purpose slot')
    if purpose=='import':need(not rows,'Import once before new experiment stages')
    else:
        proof=parse(ctx.data['import-proof/job.json']);need(any(r['purpose']=='import' and r['run_id']==proof['run_id'] and r['job_sha256']==digest(ctx.data['import-proof/job.json']) and r['common_signature']==ctx.job['common_signature'] for r in rows),'Exact accepted import reservation')
        if counts[purpose]:
            old=verify_retry(ctx);need(any(r['purpose']==purpose and r['run_id']==old['run_id'] and r['job_sha256']==digest(ctx.data['retry-proof/job.json']) for r in rows),'Exact failed first stage reservation')
        else:need(not any(n.startswith('retry-proof/') for n in ctx.data),'No invented retry proof on first attempt')
        if purpose=='motion':
            smoke=parse(ctx.data['smoke-proof/job.json']);need(any(r['purpose']=='render_smoke' and r['run_id']==smoke['run_id'] and r['job_sha256']==digest(ctx.data['smoke-proof/job.json']) for r in rows),'Exact accepted physics/render smoke reservation')
    rows.append({'purpose':purpose,'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'common_signature':ctx.job['common_signature'],'reserved_unix':time.time()})


def literal(ctx, role):
    args = {'run': str(ctx.run), 'job_hash': ctx.job_hash, 'driver_sha': ctx.job['inputs']['source/driver.py'], 'role': role}
    if role in ('native','supervise'):args['admission']=ctx.admission
    token = base64.b64encode(json.dumps(args).encode()).decode()
    code = ("import base64,hashlib,json,pathlib\n"
            + "a=json.loads(base64.b64decode('" + token + "'))\n"
            + "p=pathlib.Path(a['run'])/'input/source/driver.py';b=p.read_bytes()\n"
            + "if hashlib.sha256(b).hexdigest()!=a['driver_sha']:raise SystemExit('Pinned driver changed')\n"
            + "n={'__name__':'_remote069','__file__':str(p)};exec(compile(b,str(p),'exec'),n)\n"
            + "raise SystemExit(n['entry'](a['run'],a['job_hash'],a['driver_sha'],a['role']))\n")
    return "import base64;exec(base64.b64decode('" + base64.b64encode(code.encode()).decode() + "'))"


def failure_text(exc):
    try:
        return type(exc).__name__ + ': ' + str(exc)
    except BaseException:
        return type(exc).__name__ + ': <error formatting failed>'


def native_failure(ctx, out, exc, writer=None, stream=None):
    """Preserve the primary in memory; failing diagnostic channels cannot return success."""
    primary = getattr(ctx, 'first_fault', None)
    if type(primary) is not dict:
        primary = {'phase': 'NATIVE_ENTRY', 'error': failure_text(exc)}
        ctx.first_fault = primary
    record = {'run_id': ctx.run.name, 'job_sha256': ctx.job_hash, 'purpose': ctx.job['purpose'],
              'pid': os.getpid(), 'parent_pid': os.getppid(), 'error': primary['error'],
              'primary': dict(primary), 'outer_error': failure_text(exc), 'publication_errors': [], 'code': 1}
    ctx.native_failure_record = record
    try:
        (write if writer is None else writer)(Path(out) / 'native-firstfault.json', record)
    except BaseException as diagnostic:
        record['publication_errors'].append({'channel': 'file', 'error': failure_text(diagnostic)})
    try:
        print(json.dumps(record), file=sys.stderr if stream is None else stream, flush=True)
    except BaseException as diagnostic:
        record['publication_errors'].append({'channel': 'stderr', 'error': failure_text(diagnostic)})
    return 1


def entry(run, job_hash, driver_sha, role, admission=None):
    need(sys.flags.isolated == 1,'Isolated interpreter required')
    need(role in ('export','supervise','native'),'Closed remote role')
    if role=='export':
        run=Path(run);need(run.is_absolute() and no_link(run) and all(no_link(p) for p in run.parents),'Owned export path')
        job=parse(checked_path(run,'job.json').read_bytes())
        need(sha(run/'job.json')==job_hash and job['inputs']['source/driver.py']==driver_sha,'Trusted export job/driver binding')
        source=checked_path(run,'input/source/recovery.py').read_bytes()
        need(digest(source)==job['inputs']['source/recovery.py']==RECOVERY_SHA,'Reviewed stdlib-only recovery source before load')
        module=load_module('closed_recovery',source,run/'input/source/recovery.py')
        module.export_closed(run,job_hash,driver_sha,run)
        return 0
    ctx=snapshot(run,job_hash,driver_sha);ctx.admission=admission
    need(ctx.run.parent==Path(ctx.cfg['remote_root']),'Owned remote native root')
    out=ctx.run/'output';out.mkdir(exist_ok=True)
    if role=='supervise':return supervise(ctx)
    try:
        need(remote_clock_now(ctx)<ctx.cfg['deadline_unix'],'Native absolute interval')
        lock=read(ctx.run.parent/'session.lock')
        need(lock['pid']==os.getppid() and lock['run_id']==ctx.run.name and lock['job_sha256']==ctx.job_hash,'Actual owning supervisor parent')
        ledger=read(ctx.run.parent/'session-ledger.json')
        need(any(row['run_id']==ctx.run.name and row['job_sha256']==ctx.job_hash and row['purpose']==ctx.job['purpose'] for row in ledger['reservations']),'Native reservation precedes SDK')
        bind_sources(ctx)
        name='sdk.py' if ctx.job['purpose']=='import' else 'scene.py'
        module=load_module(name[:-3],ctx.data['source/'+name],ctx.run/'input/source'/name)
        code=module.run_import(ctx) if name=='sdk.py' else module.run(ctx)
        need(type(code) is int and 0<=code<=255,'Native result integer')
        return code
    except BaseException as exc:return native_failure(ctx,out,exc)


def recovery_manifest(out, job, job_hash, ex):
    need(ex['policy_exit_code']!=0,'Recovery cannot accept successful native execution')
    pins={}
    for p in sorted(Path(out).rglob('*')):
        if not p.is_file() or p.name=='recovery-manifest.json':continue
        need(no_link(p),'Recovery member cannot be a link');h=hashlib.sha256()
        with p.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        pins[p.relative_to(out).as_posix()]=h.hexdigest()
    return {'kind':'FAILED_PARENT_RECOVERY_SNAPSHOT_NOT_NATIVE_TERMINAL','status':'FAILED','native_acceptance':False,'run_id':job['run_id'],'job_sha256':job_hash,'purpose':job['purpose'],'exit':dict(ex),'files_sha256':pins,'native_reexecuted':False}


def finalize_parent(out, job, job_hash, ex, handle, lock):
    errors=[]
    if ex.get('child_state')=='NOT_STARTED':
        for name in ('stdout.txt','stderr.txt'):
            path=out/name
            if not path.exists():
                try:
                    with path.open('xb') as stream:stream.write(b'')
                except Exception as exc:errors.append({'channel':name,'error':failure_text(exc)})
    try:write(out/'exit.json',ex)
    except Exception as exc:errors.append({'channel':'exit','error':failure_text(exc)})
    if handle is not None:
        for channel,action in (('handle',handle.close),('lock',lock.unlink)):
            try:action()
            except Exception as exc:errors.append({'channel':channel,'error':failure_text(exc)})
    if errors:
        ex['parent_finalization_errors']=errors
        if ex['policy_exit_code']==0:ex.update(policy_exit_code=1,policy_basis='PARENT_FINALIZATION_FAILED')
        try:write(out/'exit.json',ex)
        except Exception as exc:print('FAILED_EXIT_PUBLICATION: '+failure_text(exc),file=sys.stderr,flush=True)
    if ex['policy_exit_code']!=0:
        try:write(out/'recovery-manifest.json',recovery_manifest(out,job,job_hash,ex))
        except Exception as exc:
            ex['recovery_publication_error']=failure_text(exc)
            try:write(out/'exit.json',ex)
            except Exception as saved:print('FAILED_RECOVERY_PUBLICATION: '+failure_text(saved),file=sys.stderr,flush=True)
    return ex['policy_exit_code']


def verify_parent_recovery(job, job_hash, raw, ex):
    if 'recovery-manifest.json' not in raw:return
    record=parse(raw['recovery-manifest.json'])
    need(set(record)=={'kind','status','native_acceptance','run_id','job_sha256','purpose','exit','files_sha256','native_reexecuted'},'Closed parent recovery snapshot')
    identity(record,job,job_hash)
    need(record['kind']=='FAILED_PARENT_RECOVERY_SNAPSHOT_NOT_NATIVE_TERMINAL' and record['status']=='FAILED' and record['native_acceptance'] is False and record['native_reexecuted'] is False,'Recovery diagnostic cannot claim native acceptance')
    need(record['purpose']==job['purpose'] and record['exit']==ex and type(ex['policy_exit_code']) is int and ex['policy_exit_code']!=0,'Recovery bound to original failed parent exit')
    pins=record['files_sha256'];need(type(pins) is dict and set(pins)==set(raw)-{'recovery-manifest.json','remote-shell.json'},'Exact parent snapshot inventory before remote shell publication')
    need(all(relative(n) and hash_string(h) and digest(raw[n])==h for n,h in pins.items()),'All original parent snapshot file hashes')


def supervise(ctx):
    need(ctx.run.parent == Path(ctx.cfg['remote_root']), 'Owned fixed remote root')
    out = ctx.run / 'output'
    need(not (out / 'exit.json').exists(), 'Existing native attempt cannot repeat')
    lock = ctx.run.parent / 'session.lock'
    handle = None
    ex = {'run_id': ctx.run.name, 'job_sha256': ctx.job_hash, 'purpose': ctx.job['purpose'], 'pid': os.getpid(),
          'child_pid': None, 'actual_child_exit_code': None, 'policy_exit_code': 1, 'policy_basis': 'NOT_STARTED',
          'timed_out': False, 'child_state': 'NOT_STARTED', 'started_unix': time.time()}
    try:
        need(no_link(lock), 'Lock cannot be link')
        handle = lock.open('x', encoding='utf-8')
        handle.write(json.dumps({'pid': os.getpid(), 'run_id': ctx.run.name, 'job_sha256': ctx.job_hash}))
        handle.flush()
        os.fsync(handle.fileno())
        ledger_path = ctx.run.parent / 'session-ledger.json'
        need(no_link(ledger_path), 'Ledger cannot be link')
        ledger = read(ledger_path) if ledger_path.exists() else {'schema_version': 1, 'experiment_id': EXPERIMENT, 'reservations': []}
        launch_budget(ctx.cfg,ctx.job['purpose'],now=remote_clock_now(ctx))
        reserve(ctx, ledger)
        write(ledger_path, ledger)  # Reservation is consumed before any native/bootstrap failure.
        probe = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', "@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count"], capture_output=True, timeout=min(20,ctx.cfg['deadline_unix']-remote_clock_now(ctx)), creationflags=HIDDEN)
        need(probe.returncode == 0 and probe.stdout.strip() == b'0', 'Existing Kit process; do not disturb')
        python = str(Path(ctx.cfg['sdk']['isaac_root']) / 'kit/python/python.exe')
        def admit():
            launch_budget(ctx.cfg,ctx.job['purpose'],now=remote_clock_now(ctx))
            write(out/'admission-clock.json',{'certificate':ctx.admission,'checked_remote_unix':time.time(),'run_id':ctx.run.name,'job_sha256':ctx.job_hash})
            launch_budget(ctx.cfg,ctx.job['purpose'],now=remote_clock_now(ctx))
        ex.update(run_child([python,'-I','-B','-c',literal(ctx,'native')],out,
                            native_timeout(ctx.cfg,ctx.job['purpose'],now=remote_clock_now(ctx)),admit=admit))
    except Exception as exc:
        ex['supervisor_error'] = repr(exc)
    finally:
        ex['finished_unix'] = time.time()
        code=finalize_parent(out,ctx.job,ctx.job_hash,ex,handle,lock)
    return code


def prepare(source, purpose):
    need(purpose in PURPOSES, 'Closed prepare purpose')
    cfg = parse(source['config.json'])
    launch_budget(cfg,purpose)
    need(not (ROOT/OUT/'runs'/('attempt-'+purpose+'.json')).exists(),'Local purpose attempt already consumed')
    config_contract(cfg)
    model = file_bytes(checked_path(ROOT, cfg['model_dir']))
    need(set(model) == MODEL, 'Exact sixteen source model files')
    payload = {'source/' + n: raw for n, raw in source.items()}
    payload.update({'model/' + n: raw for n, raw in model.items()})
    for key, item in cfg['refs'].items():
        raw = checked_path(ROOT, item['path']).read_bytes()
        need(digest(raw) == item['sha256'], 'Frozen reference changed ' + key)
        payload['ref/' + key] = raw
    pins = {key: digest(raw) for key, raw in payload.items()}
    common = common_signature(pins)
    if purpose in ('render_smoke','motion'):
        verified = read(ROOT / OUT / 'import-verified.json')
        oldrun = checked_path(ROOT / OUT / 'runs', verified['run_id'])
        oldctx = snapshot(oldrun, verified['job_sha256'])
        need(oldctx.job['common_signature'] == common, 'Current common input differs from import')
        code, accepted = consume(oldctx)
        need(code == 0 and accepted['status'] == 'IMPORT_VERIFIED', 'Actual original import must verify again')
        raws = {n: ((oldrun / 'job.json') if n == 'job.json' else (oldrun / 'retrieved' / n)).read_bytes() for n in PROOF}
        payload.update({'import-proof/' + n: raw for n, raw in raws.items()})
        if purpose=='motion':
            receipt=read(ROOT/OUT/'smoke-verified.json');sr=checked_path(ROOT/OUT/'runs',receipt['run_id']);sc=snapshot(sr,receipt['job_sha256']);code,accepted=consume(sc);need(code==0 and accepted['status']=='SMOKE_VERIFIED','Original native smoke verified again')
            payload.update({'smoke-proof/'+n:raw for n,raw in file_bytes(sr/'retrieved').items()});payload['smoke-proof/job.json']=(sr/'job.json').read_bytes()
        last=ROOT/OUT/('last-'+purpose+'.json')
        if last.exists():
            prev=read(last);pr=checked_path(ROOT/OUT/'runs',prev['run_id']);payload.update({'retry-proof/'+n:(pr/'retrieved'/n).read_bytes() for n in ('terminal.json','exit.json','remote-shell.json')});payload['retry-proof/job.json']=(pr/'job.json').read_bytes();payload['retry-proof/review.json']=(ROOT/OUT/('repair-'+purpose+'.json')).read_bytes()
    run = ROOT / OUT / 'runs' / uuid.uuid4().hex
    for key, raw in payload.items():
        target = run / 'input' / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    job = {'schema_version': 1, 'run_id': run.name, 'purpose': purpose,
           'inputs': {key: digest(raw) for key, raw in payload.items()}, 'common_signature': common,
           'plan_sha256': PLAN_SHA, 'hardware_approved': False, 'experiment_id': EXPERIMENT}
    write(run / 'job.json', job)
    ctx = snapshot(run, sha(run / 'job.json'))
    validator=load_module('prepare_workspace',source['validate.py'],run/'input/source/validate.py')
    validator.verify_workspace(run/'input/model/robot_arm.urdf')
    with zipfile.ZipFile(run / 'bundle.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.write(run / 'job.json', 'job.json')
        for key in payload:
            archive.write(run / 'input' / key, 'input/' + key)
    write(run / 'prepared.json', {'run_id': run.name, 'job_sha256': ctx.job_hash,
          'remote': cfg['remote_root'] + '/' + run.name, 'bundle_sha256': sha(run / 'bundle.zip')})
    return run


def remote(script, alias, timeout=120):
    deadline=read(Path(__file__).parent/'config.json')['deadline_unix']
    timeout=min(timeout, deadline-session_now(read(Path(__file__).parent/'config.json')))
    need(timeout>0, '077 absolute transport deadline')
    token = base64.b64encode(script.encode('utf-16le')).decode()
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', alias,
                           'powershell', '-NoProfile', '-NonInteractive', '-EncodedCommand', token], capture_output=True, timeout=timeout, creationflags=HIDDEN)


def unpack(archive_path, destination):
    destination = Path(destination)
    need(not destination.exists(), 'Do not overwrite retrieved evidence')
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)) and all(relative(n) for n in names), 'Unique safe archive paths')
        need(all((info.external_attr >> 16) & 0o170000 != 0o120000 for info in archive.infolist()), 'Archive link')
        destination.mkdir()
        for name in names:
            target = checked_path(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))


class RecoveryTransportError(RuntimeError):pass


def recovery_limits(cfg):
    need(type(cfg.get('export_timeout_s')) is int and cfg['export_timeout_s']==300,'Typed export300')
    need(type(cfg.get('recovery_total_s')) is int and cfg['recovery_total_s']==600,'Typed recovery total600')
    return 300,600


def recovery_deadline(cfg,now):
    _,total=recovery_limits(cfg)
    end=cfg['deadline_unix']
    need(type(now) in (int,float) and math.isfinite(now) and type(end) in (int,float) and math.isfinite(end),'Finite recovery clock')
    need(end>now,'No recovery time remains')
    return min(end,now+total)


def recovery_timeout(cfg,end,now,mono_end=None,mono_now=None):
    per_call,_=recovery_limits(cfg)
    need(type(now) in (int,float) and math.isfinite(now) and type(end) in (int,float) and math.isfinite(end),'Finite shared recovery deadline')
    need(end>now,'Recovery absolute deadline reached')
    if mono_end is not None:
        need(type(mono_end) in (int,float) and type(mono_now) in (int,float) and math.isfinite(mono_end) and math.isfinite(mono_now) and mono_now<mono_end,'Recovery monotonic deadline')
        return min(per_call,end-now,mono_end-mono_now)
    return min(per_call,end-now)


def recover_transport(ctx,remctx,python,rr,alias):
    need(not any((ctx.run/name).exists() for name in ('recovery-budget.json','recovery-status.json','recovery-receipt.json','records.zip','retrieved')),
         'Recovery already consumed;no overwrite/reset/retry')
    stage='BEFORE_EXPORT';end=None
    try:
        started=session_now(ctx.cfg);started_mono=time.monotonic();mono_end=started_mono+600;end=recovery_deadline(ctx.cfg,started)
        with (ctx.run/'recovery-budget.json').open('x',encoding='utf-8') as stream:
            json.dump({'started_unix':started,'deadline_unix':end,'export_timeout_s':300,'total_s':600,'started_monotonic':started_mono,'deadline_monotonic':mono_end,'hardware_approved':False},stream)
            stream.flush();os.fsync(stream.fileno())
        stage='EXPORT'
        result=remote("& '"+python+"' -I -B -c \""+literal(remctx,'export')+"\";exit $LASTEXITCODE",alias,recovery_timeout(ctx.cfg,end,session_now(ctx.cfg),mono_end,time.monotonic()))
        need(result.returncode==0,'Closed export failed')
        for name in ('recovery-receipt.json','records.zip'):
            stage='COPY_'+name
            result=subprocess.run(['scp','-q',alias+':'+rr+'/'+name,str(ctx.run/name)],capture_output=True,
                timeout=recovery_timeout(ctx.cfg,end,session_now(ctx.cfg),mono_end,time.monotonic()),creationflags=HIDDEN)
            need(result.returncode==0,'Closed recovery copy failed '+name)
        stage='VERIFY_AND_UNPACK'
        need(digest(ctx.data['source/recovery.py'])==ctx.job['inputs']['source/recovery.py']==RECOVERY_SHA,'Reviewed local recovery verifier')
        module=load_module('closed_recovery_local',ctx.data['source/recovery.py'],ctx.run/'input/source/recovery.py')
        module.unpack_verified(ctx.run/'records.zip',ctx.run/'recovery-receipt.json',ctx.run/'retrieved',ctx.job_hash,ctx.job['inputs']['source/driver.py'])
        need(session_now(ctx.cfg)<end and time.monotonic()<mono_end,'Recovery completion exceeded absolute deadline')
        record={'status':'CLOSED_ARTIFACT_COPY_VERIFIED_NOT_PHYSICS_ACCEPTANCE','deadline_unix':end,'native_transport':read(ctx.run/'transport.json'),
                'native_reexecuted':False,'hardware_approved':False}
        write(ctx.run/'recovery-status.json',record)
    except Exception as exc:
        record={'status':'RECOVERY_FAILED','stage':stage,'error':repr(exc),'deadline_unix':end,
                'native_transport':read(ctx.run/'transport.json'),'native_reexecuted':False,'hardware_approved':False}
        write(ctx.run/'recovery-status.json',record)
        raise RecoveryTransportError('Closed artifact recovery failed: '+stage) from exc


def launch(ctx, prepared):
    launch_budget(ctx.cfg,ctx.job['purpose'])
    with (ctx.run.parent/('attempt-'+ctx.job['purpose']+'.json')).open('x',encoding='utf-8') as stream:
        json.dump({'purpose':ctx.job['purpose'],'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'started_unix':session_now(ctx.cfg)},stream)
        stream.flush();os.fsync(stream.fileno())
    with (ctx.run/'launch-attempt.json').open('x',encoding='utf-8') as stream:
        json.dump({'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'started_unix':session_now(ctx.cfg)},stream)
    rr, alias = prepared['remote'], ctx.cfg['ssh_alias']
    need(rr == ctx.cfg['remote_root'] + '/' + ctx.run.name and re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+', rr), 'Pinned remote path')
    need(sha(ctx.run / 'bundle.zip') == prepared['bundle_sha256'], 'Pinned transport archive')
    created = remote("$ErrorActionPreference='Stop';if(Test-Path -LiteralPath '" + rr + "'){throw 'Run exists'};New-Item -ItemType Directory -Path '" + rr + "'|Out-Null", alias)
    need(created.returncode == 0, 'Remote create')
    upload = subprocess.run(['scp', '-q', str(ctx.run / 'bundle.zip'), alias + ':' + rr + '/bundle.zip'], capture_output=True, timeout=min(120,ctx.cfg['deadline_unix']-session_now(ctx.cfg)), creationflags=HIDDEN)
    need(upload.returncode == 0, 'Bundle upload')
    expanded = remote("$ErrorActionPreference='Stop';if((Get-FileHash -LiteralPath '" + rr + "/bundle.zip').Hash -ine '" + prepared['bundle_sha256'] + "'){throw 'Bundle SHA'};Expand-Archive -LiteralPath '" + rr + "/bundle.zip' -DestinationPath '" + rr + "'", alias)
    need(expanded.returncode == 0, 'Pinned archive extraction')
    ctx.admission=clock_probe(ctx)
    with (ctx.run/'admission-clock.json').open('x',encoding='utf-8') as stream:json.dump(ctx.admission,stream)
    launch_budget(ctx.cfg,ctx.job['purpose'])
    remctx = types.SimpleNamespace(run=Path(rr), job_hash=ctx.job_hash, job=ctx.job,admission=ctx.admission)
    python = str(Path(ctx.cfg['sdk']['isaac_root']) / 'kit/python/python.exe')
    need("'" not in python, 'SDK executable quote')
    script = ("& '" + python + "' -I -B -c \"" + literal(remctx, 'supervise') + "\";$ec=$LASTEXITCODE;if($null -eq $ec){$ec=1};"
              + "$r=@{run_id='" + ctx.run.name + "';job_sha256='" + ctx.job_hash + "';python_exit_code=[int]$ec};"
              + "[IO.File]::WriteAllText('" + rr + "/output/remote-shell.json',($r|ConvertTo-Json),[Text.UTF8Encoding]::new($false));exit $ec")
    try:
        launch_budget(ctx.cfg,ctx.job['purpose'])
        result = remote(script, alias, transport_timeout(ctx.cfg,ctx.job['purpose']))
        transport = {'returncode': result.returncode, 'timed_out': False}
        (ctx.run / 'transport-stdout.txt').write_bytes(result.stdout)
        (ctx.run / 'transport-stderr.txt').write_bytes(result.stderr)
    except subprocess.TimeoutExpired as exc:
        transport = {'returncode': None, 'timed_out': True, 'error': repr(exc)}
        (ctx.run / 'transport-stdout.txt').write_bytes(exc.stdout or b'')
        (ctx.run / 'transport-stderr.txt').write_bytes(exc.stderr or b'')
    write(ctx.run / 'transport.json', transport)
    # Recovery is separately bounded; it never changes the native transport record.
    recover_transport(ctx,remctx,python,rr,alias)


def consume(ctx):
    out = ctx.run / 'retrieved'
    raw = file_bytes(out)
    need({'terminal.json', 'exit.json', 'remote-shell.json', 'stdout.txt', 'stderr.txt'} <= set(raw), 'Required original process records/logs')
    terminal, ex, shell = (parse(raw[n]) for n in ('terminal.json', 'exit.json', 'remote-shell.json'))
    verify_parent_recovery(ctx.job,ctx.job_hash,raw,ex)
    code = process_contract(ctx.job, ctx.job_hash, terminal, ex, shell)
    transport = read(ctx.run / 'transport.json')
    need(transport.get('timed_out') is False and type(transport.get('returncode')) is int and transport['returncode'] == code, 'Actual local SSH return code')
    pins = terminal.get('files_sha256')
    need(type(pins) is dict and all(relative(k) and hash_string(v) for k, v in pins.items()), 'Typed terminal hashes')
    need(set(pins) == set(raw) - UNSEALED, 'Exact terminal artifact inventory')
    need(all(digest(raw[n]) == value for n, value in pins.items()), 'All original output artifacts sealed')
    need(not any(error.lower() in (raw['stdout.txt'] + raw['stderr.txt']).decode('utf-8', errors='replace').lower() for error in RENDER_ERRORS), 'Native renderer scheduling firstfault')
    bind_sources(ctx)
    validate = load_module('validate', ctx.data['source/validate.py'], ctx.run / 'input/source/validate.py')
    adapter = load_module('sdk', ctx.data['source/sdk.py'], ctx.run / 'input/source/sdk.py')
    provider_metrics = adapter.verify_records(ctx, out, terminal)
    model = ctx.run / 'input/model/robot_arm.urdf'
    _,workspace_metrics=validate.verify_workspace(model)
    result = {'run_id': ctx.run.name, 'job_sha256': ctx.job_hash, 'purpose': ctx.job['purpose'],
              'common_signature': ctx.job['common_signature'], 'sdk_connected': True, 'actual_child_exit_code': code,
              'providers': provider_metrics, 'workspace':workspace_metrics}
    if ctx.job['purpose'] == 'import':
        need({'static.json', 'report.json', 'model.usda'} <= set(pins), 'Import static/USD/report required')
        result['metrics'] = validate.verify_import(model, out / 'static.json', ctx.cfg)
        result['status'] = 'IMPORT_VERIFIED'
        return 0, result
    metrics = validate.verify_simulation(model, read(out / 'report.json'), ctx.cfg, out, purpose=ctx.job['purpose'])
    need(type(metrics) is dict and type(metrics.get('dynamics_pass')) is bool, 'Typed dynamics result')
    result['metrics'] = metrics
    if metrics['dynamics_pass']:
        need(code == 0, 'Successful dynamics requires actual zero exit')
        result['status'] = 'SMOKE_VERIFIED' if ctx.job['purpose']=='render_smoke' else 'WORKSPACE_MOTION_VERIFIED'
        return 0, result
    result['status'] = 'LATEST_SCENE_DYNAMICS_FAILED'
    return 1, result


def local_failure_result(ctx,exc):
    record=None;path=ctx.run/'recovery-status.json'
    if path.exists():
        try:record=read(path)
        except (ValueError,OSError) as error:record={'status':'RECOVERY_METADATA_UNREADABLE','error':repr(error)}
    previous=None;primary=ctx.run/'validation.json'
    if primary.exists():
        try:previous=read(primary)
        except (ValueError,OSError) as error:previous={'status':'PRIMARY_VALIDATION_UNREADABLE','error':repr(error)}
    failed=isinstance(exc,RecoveryTransportError) or (type(record) is dict and record.get('status')=='RECOVERY_FAILED')
    if record is None or (type(record) is dict and record.get('status')=='RECOVERY_METADATA_UNREADABLE'):
        failed=failed or (type(previous) is dict and previous.get('status')=='RECOVERY_FAILED')
    result={'status':'RECOVERY_FAILED' if failed else 'FAILED','run_id':ctx.run.name,'job_sha256':ctx.job_hash,
            'purpose':ctx.job['purpose'],'sdk_connected':None,'native_execution':'NOT_INFERRED_FROM_RECOVERY_FAILURE' if failed else 'UNKNOWN_FROM_LOCAL_ERROR','reason':repr(exc)}
    if record is not None:result['recovery']=record
    return result


def publish_validation(run,result):
    primary=run/'validation.json';value=dict(result)
    if primary.exists():
        value['initial_validation_sha256']=sha(primary)
        target=run/('validation-query-'+uuid.uuid4().hex+'.json')
    else:target=primary
    value['validation_file']=target.name
    with target.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return value


def public(role, run_dir='', purpose=''):
    source = own_source(Path(__file__).resolve().parent)
    if role == 'test':
        module = load_module('test_host', source['test_host.py'], Path(__file__).parent / 'test_host.py')
        return module.run_tests(types.SimpleNamespace(**globals()), source)
    if role == 'prepare':
        print(prepare(source, purpose))
        return 0
    need(role in ('run', 'verify'), 'Closed public role')
    run = Path(run_dir)
    need(run.is_absolute() and run.parent == ROOT / OUT / 'runs', 'Owned local run root')
    prepared = read(run / 'prepared.json')
    ctx = snapshot(run, prepared['job_sha256'], digest(source['driver.py']))
    need(prepared['run_id'] == run.name and all(ctx.job['inputs']['source/' + n] == digest(raw) for n, raw in source.items()), 'Current reviewed source binding')
    try:
        if role == 'run':
            need(not (run / 'transport.json').exists(), 'Transport attempt already consumed')
            launch(ctx, prepared)
        code, result = consume(ctx)
    except RecoveryTransportError as exc:
        code=1
        result=local_failure_result(ctx,exc)
    except Exception as exc:
        code = 1
        result=local_failure_result(ctx,exc)
    result=publish_validation(run,result)
    write(ROOT / OUT / 'current.json', result)
    if result['status'] in ('IMPORT_VERIFIED','SMOKE_VERIFIED'):
        name='import-verified.json' if result['status']=='IMPORT_VERIFIED' else 'smoke-verified.json'
        write(ROOT / OUT / name, {'run_id': run.name, 'job_sha256': ctx.job_hash})
    if role=='run':
        write(ROOT / OUT / ('last-'+ctx.job['purpose']+'.json'), {'run_id':run.name,'job_sha256':ctx.job_hash})
    print(json.dumps(result, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit('Use launch.ps1')
