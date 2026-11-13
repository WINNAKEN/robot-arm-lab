"""113 local controller. Parent-validated scalar owners precede managed I/O."""
import base64
import ctypes
from contextlib import contextmanager
import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import types
import uuid
import zipfile

ROOT = Path(__file__).parents[3]
OUT = 'outputs/typed-decision-preflight-113'
SOURCE_A = {'driver.py', 'sdk.py', 'validate.py', 'test_host.py', 'launch.ps1', 'config.json', 'winjob.py', 'bootstrap.py'}
SOURCE_B = {'scene.py', 'capture.py', 'program.json', 'test_scene.py', 'README.md', 'workspace.py', 'init_boundary.py', 'torque.py', 'reference.py', 'balance.py', 'root_binding.py', 'recovery.py', 'decision_schema.py'}
SOURCE = SOURCE_A | SOURCE_B
MODEL = {'robot_arm.urdf', 'asset-ledger.json', 'manifest.json', 'provenance.json', 'README.md'} | {
    'meshes/' + n + '.stl' for n in ('Base', 'Link1', 'Link2', 'Link3', 'Link4', 'Link5', 'Link6', 'KG1', 'KG1_A', 'KG1_B', 'KG1_R')}
PURPOSES = ('import', 'render_smoke', 'motion')
EXPERIMENT = 'typed_decision_preflight_113'
PLAN_SHA = '771c9e11173c7f3d6d0776bd5a4b8c200f46bbcef211d9a22e5044b89d8707f8'
RECOVERY_SHA = '8111c2c657f2652bf2cfd84630f0ad3110bc48102189296b738977c0d4065315'
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
PROOF = {'job.json', 'terminal.json', 'exit.json', 'remote-shell.json', 'static.json', 'report.json', 'model.usda'}
UNSEALED = {'terminal.json', 'status.json', 'stdout.txt', 'stderr.txt', 'exit.json', 'remote-shell.json', 'child-started.json', 'recovery-manifest.json'}
RENDER_ERRORS = ('renderer failed to advance to the scheduled frame', 'Orchestrator failed to schedule a capture')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _runtime(value):
    """Validate memory scalars before any managed read or path inspection."""
    rt=getattr(value,'runtime',None)
    if rt is None and getattr(value,'unit',None)=='113':rt=value
    need(rt is not None and rt.unit=='113' and rt.native_authorized is True and rt.hardware_approved is False,'Authorized113 runtime required')
    need(type(rt.end_monotonic) in (int,float) and math.isfinite(rt.end_monotonic) and time.monotonic()<rt.end_monotonic,'Finite original runtime remains')
    need(type(rt.helper_bytes) is bytes and digest(rt.helper_bytes)=='2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0','Loaded exact helper bytes')
    need(isinstance(rt.root,Path) and all(callable(getattr(rt,k,None)) for k in ('phase','verify','bind','bind_config','entry_code','workspace_scope','require_workspace_scope','workspace_authority')),'Runtime interface')
    return rt

def _ctx_owned(limit=None):
    def decorate(function):
        def owned(ctx,*args,**kwargs):
            rt=_runtime(ctx)
            with rt.phase(limit):return function(ctx,*args,**kwargs)
        owned.__name__=function.__name__;owned.__doc__=function.__doc__
        return owned
    return decorate


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
    module.__source_bytes__ = raw
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
        module.__source_bytes__ = raw
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        if name == 'validate.py':_bind_workspace(self.ctx,module)


@_ctx_owned()
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


def _workspace_authority_contract(authority):
    """Only actual B supplies independent pins and exact template/active bytes."""
    fields={'schema_version','unit','receipt_raw','receipt_sha256','template_config_raw','active_config_raw','decision_inputs'}
    need(type(authority) is dict and set(authority)==fields,'Closed workspace authority7')
    need(type(authority['schema_version']) is int and authority['schema_version']==1
         and type(authority['unit']) is str and authority['unit']=='113','Typed113 workspace authority')
    need(all(type(authority[n]) is bytes for n in ('receipt_raw','template_config_raw','active_config_raw')),'Exact authority bytes')
    need(hash_string(authority['receipt_sha256']) and digest(authority['receipt_raw'])==authority['receipt_sha256'],'Independent receipt authority pin')
    pins=authority['decision_inputs']
    need(type(pins) is dict and len(pins)==48,'Workspace authority input48')
    for name,item in pins.items():
        need(relative(name) and type(item) is dict and set(item)=={'sha256','bytes'} and hash_string(item['sha256'])
             and type(item['bytes']) is int and item['bytes']>0,'Typed workspace decision pin')
    return authority


def _bind_workspace(ctx,module):
    """Bind to the already armed caller; every D use re-observes B and raw inputs."""
    rt=_runtime(ctx)
    scope=rt.workspace_scope()
    run=ctx.run
    need(isinstance(run,Path) and run.is_absolute(),'Workspace original absolute run')
    job_hash=ctx.job_hash
    need(hash_string(job_hash),'Workspace original job hash')
    job_contract(ctx.job,run.name)
    job_identity=json.dumps(ctx.job,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    input_pins=tuple(sorted(ctx.job['inputs'].items()))
    need(type(ctx.data) is dict and set(ctx.data)=={n for n,_ in input_pins}
         and all(type(ctx.data[n]) is bytes and digest(ctx.data[n])==pin for n,pin in input_pins),'Workspace bound original input pins')
    config_contract(dict(ctx.cfg))
    need(len(ctx.cfg['refs'])==11,'Workspace original reference11')
    decision_names=frozenset({'source/'+n for n in SOURCE}|{'model/'+n for n in MODEL}|{'ref/'+n for n in ctx.cfg['refs']})
    need(len(decision_names)==48 and decision_names|{'workspace-preflight.json'}<=set(ctx.data),'Workspace closed decision48 plus receipt')
    expected_model=run/'input/model/robot_arm.urdf'
    need(getattr(module,'__file__',None)==str(run/'input/source/validate.py')
         and type(getattr(module,'__source_bytes__',None)) is bytes
         and module.__source_bytes__==ctx.data['source/validate.py'],'Workspace actual validator source binding')
    need(all(callable(getattr(module,n,None)) for n in ('bind_decision_schema','bind_workspace','verify_workspace','verify_workspace_receipt')),'Workspace validator API')

    policy_raw=ctx.data['source/decision_schema.py']
    module.bind_decision_schema(policy_raw)

    @contextmanager
    def workspace_use():
        # This pure check must precede phase creation, authority I/O, and any cache.
        rt.require_workspace_scope(scope)
        with rt.phase() as owner_end:
            authority=_workspace_authority_contract(rt.workspace_authority(scope))
            current_job_raw=checked_path(run,'job.json').read_bytes()
            need(digest(current_job_raw)==job_hash,'Workspace current original job bytes')
            current_job=parse(current_job_raw)
            job_contract(current_job,run.name)
            need(json.dumps(current_job,sort_keys=True,separators=(',',':'),allow_nan=False).encode()==job_identity,'Workspace current original job identity')
            data=file_bytes(run/'input')
            need(set(data)=={n for n,_ in input_pins}
                 and all(digest(data[n])==pin for n,pin in input_pins),'Workspace current entire input inventory/pins')
            need(data['source/config.json']==authority['active_config_raw'],'Workspace exact active config stamp')
            need(data['workspace-preflight.json']==authority['receipt_raw'],'Workspace current actual receipt bytes')
            need(set(authority['decision_inputs'])==decision_names,'Workspace authority closed decision names48')
            bundle={name:data[name] for name in decision_names}
            bundle['source/config.json']=authority['template_config_raw']
            need(all(digest(raw)==authority['decision_inputs'][n]['sha256']
                     and len(raw)==authority['decision_inputs'][n]['bytes'] for n,raw in bundle.items()),'Workspace projected exact decision48 pins')
            need(module.__source_bytes__==data['source/validate.py'],'Workspace current same validator code')
            need(policy_raw==data['source/decision_schema.py'],'Workspace current same policy code')
            try:
                yield bundle,authority['receipt_raw'],authority['receipt_sha256'],expected_model
            finally:
                rt.require_workspace_scope(scope)
                need(type(owner_end) in (int,float) and math.isfinite(owner_end) and time.monotonic()<owner_end,'Workspace child owner remains through D exit')

    module.bind_workspace(workspace_use)



def effective_clock(record,wall,mono):
    for value in (wall,mono,record['started_unix'],record['started_monotonic']):
        need(type(value) in (int,float) and math.isfinite(value),'Finite nonbool clock anchor')
    elapsed=mono-record['started_monotonic'];need(elapsed>=0,'Monotonic anchor after reboot/backward')
    expected=record['started_unix']+elapsed
    need(abs(wall-expected)<=.25,'Local wall/monotonic clock uncertainty')
    return expected

def session_now(cfg):
    rt=_runtime(cfg)
    with rt.phase():
        b=rt.verify()
        need(type(b) is dict and b.get('unit')=='113' and type(b.get('duration_s')) is int and b['duration_s']==2700
             and b.get('hardware_approved') is False and b.get('plan_sha256')==PLAN_SHA,'Bound absolute111 budget')
        need(all(type(b.get(k)) in (int,float) and math.isfinite(b[k]) for k in ('started_unix','started_monotonic','deadline_unix')),'Typed remote clock budget')
        need(b['deadline_unix']==b['started_unix']+2700==cfg['deadline_unix'] and b['started_monotonic']+2700==rt.end_monotonic,'Original clock anchors')
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

def clock_deadlines(started,global_end):
    need(all(type(v) in (int,float) and math.isfinite(v) for v in (started,global_end)), 'Finite clock lifecycle anchors')
    end=min(started+20.,global_end);communication=end-2.
    need(started<communication,'Clock lifecycle lacks shared cleanup reserve')
    return end,communication


def clock_window(cfg,started):
    rt=_runtime(cfg)
    return clock_deadlines(started,rt.end_monotonic)



def clock_remote_code(nonce):
    need(type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce),'Clock nonce')
    return """import ctypes,json,sys,time
from ctypes import wintypes as w
k=ctypes.WinDLL('kernel32',use_last_error=True)
class P(ctypes.Structure):
 _fields_=[('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),('heap',ctypes.c_size_t),('module',w.DWORD),('threads',w.DWORD),('parent',w.DWORD),('priority',w.LONG),('flags',w.DWORD),('exe',w.WCHAR*260)]
k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
k.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(P)];k.Process32FirstW.restype=w.BOOL
k.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(P)];k.Process32NextW.restype=w.BOOL
k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
k.GetTickCount64.argtypes=[];k.GetTickCount64.restype=ctypes.c_ulonglong
h=k.CreateToolhelp32Snapshot(2,0)
if h in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
n=0;p=P();p.size=ctypes.sizeof(P)
try:
 if not k.Process32FirstW(h,ctypes.byref(p)):raise ctypes.WinError(ctypes.get_last_error())
 while True:
  if p.exe.lower() in ('kit.exe','isaacsim.exe'):n+=1
  if not k.Process32NextW(h,ctypes.byref(p)):
   if ctypes.get_last_error()!=18:raise ctypes.WinError(ctypes.get_last_error())
   break
finally:
 if not k.CloseHandle(h):raise ctypes.WinError(ctypes.get_last_error())
nonce=NONCE
print(json.dumps({'protocol':'local-clock-110-v1','kind':'READY','nonce':nonce,'site_loaded':'site' in sys.modules}),flush=True)
wall=time.time();tick=int(k.GetTickCount64())
print(json.dumps({'kind':'SAMPLE','nonce':nonce,'remote_unix':wall,'remote_uptime_ms':tick,'kit_count':n}),flush=True)
""".replace('NONCE',repr(nonce),1)



def clock_argv(cfg,nonce):
    python=str(Path(cfg['sdk']['isaac_root'])/'kit/python/python.exe')
    need(Path(python).is_absolute(),'Absolute same-host OS executable')
    return [python,'-I','-S','-B','-c',clock_remote_code(nonce)]



class ClockChannelError(RuntimeError):
    def __init__(self,primary,stdout,stderr,timing):
        super().__init__(str(primary));self.stdout=stdout;self.stderr=stderr;self.timing=timing
        known=timing.get('process')
        self.returncode=timing.get('returncode');self.timed_out=(isinstance(primary,(TimeoutError,subprocess.TimeoutExpired)) or (type(known) is dict and known.get('timed_out') is True))




def clock_exchange(cfg,nonce,end,communication,helper=None):
    rt=_runtime(cfg)
    with rt.phase(20) as owned_end:
        need(end<=owned_end+0.000001,'Clock inherited absolute end')
        return _clock_exchange_body(cfg,nonce,end,communication,helper,rt)


def _clock_exchange_body(cfg,nonce,end,communication,helper,runtime):
    need(type(end) in (int,float) and math.isfinite(end) and communication==end-2.,'Shared clock20 cleanup partition')
    session_now(cfg)
    folder=runtime.root/OUT/'clock-transport'/uuid.uuid4().hex;folder.mkdir(parents=True)
    sent=time.time();mono=time.monotonic();total=end-mono
    timing={'phase':'LOCAL_PROCESS','nonce':nonce,'local_send_unix':sent,'local_send_monotonic':mono,
            'overall_deadline_monotonic':end,'communication_deadline_monotonic':communication,
            'capture_dir':folder.relative_to(runtime.root).as_posix()}
    stdout=stderr=b''
    try:
        argv=clock_argv(cfg,nonce)
        write(folder/'request.json',{**timing,'argv_sha256':digest(json.dumps(argv).encode()),'transport_kind':'LOCAL_PROCESS'})
        result=_controlled_process(argv,folder,total,runtime.helper if helper is None else helper,runtime=runtime)
        received=time.time();received_mono=time.monotonic()
        timing.update(result.record,returncode=result.returncode,local_receive_unix=received,
                      local_receive_monotonic=received_mono,local_elapsed_s=received_mono-mono)
        need(received_mono<=end,'Clock total lifecycle exceeded')
        return types.SimpleNamespace(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,timing=timing)
    except Exception as exc:
        timing.update(error=failure_text(exc),raw_complete=False,query_record_complete=False)
        known=getattr(exc,'process_record',None)
        if type(known) is dict:
            timing['process']=known
            timing['returncode']=known.get('actual_child_exit_code')
        try:
            if type(known) is not dict and (folder/'process.json').exists():timing['process']=read(folder/'process.json')
        except Exception as read_error:timing['process_record_error']=failure_text(read_error)
        for name in ('stdout','stderr'):
            try:
                path=folder/(name+'.txt');raw=path.read_bytes() if path.exists() else b''
                if name=='stdout':stdout=raw
                else:stderr=raw
            except Exception as read_error:timing[name+'_capture_error']=failure_text(read_error)
        raise ClockChannelError(exc,stdout,stderr,timing) from exc



def clock_probe(ctx):
    rt=_runtime(ctx)
    with rt.phase(20) as end:
        return _clock_probe_body(ctx,end)


def _clock_probe_body(ctx,owned_end):
    helper=_job_helper(ctx)
    paths=[ctx.run/('clock-query'+suffix) for suffix in ('-stdout.txt','-stderr.txt','.json','-failure.json')]
    attempt=ctx.run/'clock-query-attempt.json'
    need(not any(p.exists() for p in (*paths,attempt)),'Clock query already consumed; no overwrite/retry')
    session_now(ctx.cfg);started=time.time();mono=time.monotonic();end=owned_end;communication=end-2.;need(mono<communication,"Clock cleanup reserve");nonce=uuid.uuid4().hex
    with helper.Fence(end):
        marker={'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'deadline_unix':ctx.cfg['deadline_unix'],'nonce':nonce,
                'started_unix':started,'started_monotonic':mono,'overall_deadline_monotonic':end,'communication_deadline_monotonic':communication}
        with attempt.open('xb') as stream:
            stream.write((json.dumps(marker,allow_nan=False)+'\n').encode());stream.flush();os.fsync(stream.fileno())
        result=None
        def record(path,value):
            with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False)
        def raw_files(stdout,stderr):
            for path,value in zip(paths[:2],(stdout,stderr)):
                if not path.exists():
                    with path.open('xb') as stream:stream.write(value or b'')
        def observation(value):
            return {**marker,**getattr(value,'timing',{}),'returncode':getattr(value,'returncode',None),
                    'timed_out':getattr(value,'timed_out',False),'SimulationApp_started':False}
        try:
            result=clock_exchange(ctx.cfg,nonce,end,communication,helper=helper)
            raw_files(result.stdout,result.stderr);record(paths[2],observation(result));session_now(ctx.cfg)
            need(result.returncode==0,'Remote clock OS query failed')
            rows=result.stdout.splitlines();need(len(rows)==2,'Two clock protocol records')
            ready,raw=[parse(row.decode('utf-8')) for row in rows]
            need(ready=={'protocol':'local-clock-110-v1','kind':'READY','nonce':nonce,'site_loaded':False}
                 and type(ready['site_loaded']) is bool,'Clock READY protocol/nonce/site')
            need(set(raw)=={'kind','nonce','remote_unix','remote_uptime_ms','kit_count'} and raw['kind']=='SAMPLE'
                 and raw['nonce']==nonce and type(raw['kit_count']) is int and raw['kit_count']==0,'Clock SAMPLE/nonce/Kit process')
            timing=result.timing
            cert={'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'deadline_unix':ctx.cfg['deadline_unix'],
                  'local_send_unix':timing['local_send_unix'],'local_receive_unix':timing['local_receive_unix'],
                  'local_elapsed_s':timing['local_elapsed_s'],'remote_unix':raw['remote_unix'],'remote_uptime_ms':raw['remote_uptime_ms']}
            clock_bounds(cert);return cert
        except Exception as exc:
            value=result if result is not None else exc
            try:
                raw_files(getattr(value,'stdout',b''),getattr(value,'stderr',b''))
                if not paths[2].exists():record(paths[2],observation(value))
                record(paths[3],{**observation(value),'status':'CLOCK_QUERY_REJECTED','error':repr(exc)})
            except Exception as diagnostic:
                print('CLOCK_DIAGNOSTIC_FAILURE primary='+repr(exc)+' secondary='+repr(diagnostic),file=sys.stderr,flush=True)
            raise


def own_source(folder=None,*,runtime):
    rt=_runtime(runtime)
    with rt.phase():
        budget=rt.verify();folder=rt.root/'src/simulation/typed_decision_preflight_113' if folder is None else Path(folder)
        need(folder==rt.src,'Owned runtime source root')
        cfg=read(checked_path(folder,'config.json'));config_contract(cfg)
        pins=cfg.get('immutable_source_pins');legacy=SOURCE-{'driver.py','config.json','winjob.py','bootstrap.py','validate.py','decision_schema.py'}
        need(type(pins) is dict and set(pins)==legacy and all(hash_string(v) for v in pins.values()),'Exact immutable source15 pins')
        base=rt.root/'src/simulation/clock_ready_resume_108';source={}
        for name,pin in pins.items():
            raw=checked_path(base,name).read_bytes();need(digest(raw)==pin,'Legacy source changed '+name);source[name]=raw
        for name in ('driver.py','config.json','bootstrap.py','validate.py','decision_schema.py'):source[name]=checked_path(folder,name).read_bytes()
        source['winjob.py']=rt.helper_bytes
        need(set(source)==SOURCE and len(source)==21,'Actual composed source21')
        need({k:digest(v) for k,v in source.items()}==budget['execution_source'],'Exact active runtime21 source')
        need(digest(source['winjob.py'])==cfg['winjob_sha256'],'Helper/config source binding')
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
    need(type(cfg.get('remote_root')) is str and re.fullmatch('[A-Za-z]:/isaacsim_remote/robot-arm-lab/113/worker/runs',cfg['remote_root']), 'Fixed new experiment root; old ledgers untouched')
    need(type(cfg.get('ssh_alias')) is str and re.fullmatch('[A-Za-z0-9_-]+',cfg['ssh_alias']), 'SSH endpoint')
    need(cfg.get('transport_kind')=='LOCAL_PROCESS' and hash_string(cfg.get('winjob_sha256')),'Explicit local helper transport')
    need(type(cfg.get('source_A')) is list and set(cfg['source_A'])==SOURCE_A and len(cfg['source_A'])==len(SOURCE_A),'Exact core source group')
    need(type(cfg.get('source_B')) is list and set(cfg['source_B'])==SOURCE_B and len(cfg['source_B'])==len(SOURCE_B),'Exact scene source group')
    phase_limits(cfg, 'import')
    recovery_limits(cfg)
    need(cfg.get('offline_only') is False and cfg.get('native_limits')=={'import':1,'render_smoke':1,'motion':1}
         and all(type(v) is int for v in cfg['native_limits'].values()),'113 bounded native authority')
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
              if key.startswith(('model/', 'ref/')) or key in {'source/' + n for n in SOURCE_A} | {'source/decision_schema.py', 'workspace-preflight.json'}}
    need({'source/' + n for n in SOURCE_A} | {'source/decision_schema.py'} <= set(common), 'Missing common source core and policy')
    return digest(json.dumps(common, sort_keys=True, separators=(',', ':')).encode())


def job_contract(job, run_name):
    need(type(job) is dict and set(job) == {'schema_version', 'run_id', 'purpose', 'inputs', 'common_signature', 'plan_sha256', 'hardware_approved', 'experiment_id'}, 'Closed job schema')
    need(type(job['schema_version']) is int and job['schema_version'] == 1, 'Typed job version')
    need(job['run_id'] == run_name and re.fullmatch('[0-9a-f]{32}', run_name), 'Run identity')
    need(job['purpose'] in PURPOSES and job['hardware_approved'] is False and job['plan_sha256'] == PLAN_SHA and job['experiment_id']==EXPERIMENT, 'Closed experiment/purpose/authority')
    need(type(job['inputs']) is dict and all(relative(k) and hash_string(v) for k, v in job['inputs'].items()), 'Typed input hash mapping')
    need(hash_string(job['common_signature']) and common_signature(job['inputs']) == job['common_signature'], 'Common signature')


def _snapshot_body(run, job_hash, expected_driver_sha, runtime):
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
    need({n:digest(data['source/'+n]) for n in SOURCE}==runtime.verify()['execution_source'],'Snapshot source21 equals active execution21')
    cfg=runtime.bind_config(cfg)
    expected = {'source/' + n for n in SOURCE} | {'model/' + n for n in MODEL} | {'ref/' + n for n in cfg['refs']} | {'workspace-preflight.json'}
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
    runtime.bind(ctx)
    if job['purpose'] in ('render_smoke','motion'):
        verify_import_proof(ctx, {n: data['import-proof/' + n] for n in PROOF})
    if job['purpose']=='motion':verify_smoke_proof(ctx)
    if any(n.startswith('retry-proof/') for n in data):verify_retry(ctx)
    return ctx


def snapshot(run,job_hash,expected_driver_sha=None,*,runtime):
    rt=_runtime(runtime)
    with rt.phase():
        rt.verify()
        return rt.bind(_snapshot_body(run,job_hash,expected_driver_sha,rt))

def load(ctx,*,runtime=None):
    rt=_runtime(ctx if runtime is None else runtime)
    with rt.phase():return snapshot(ctx.run,ctx.job_hash,runtime=rt)



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


@_ctx_owned()
def verify_smoke_proof(ctx):
    raws={n[12:]:b for n,b in ctx.data.items() if n.startswith('smoke-proof/')}
    need({'job.json','terminal.json','exit.json','remote-shell.json','report.json','scene.usda','stdout.txt','stderr.txt'}<=set(raws),'Original smoke raw tree')
    old=parse(raws['job.json']);job_contract(old,old.get('run_id',''));need(old['purpose']=='render_smoke' and old['common_signature']==ctx.job['common_signature'] and b_signature(old['inputs'])==b_signature(ctx.job['inputs']),'Exact same-domain and B implementation smoke')
    terminal,ex,shell=(parse(raws[n]) for n in ('terminal.json','exit.json','remote-shell.json'));process_contract(old,digest(raws['job.json']),terminal,ex,shell)
    pins=terminal.get('files_sha256');need(type(pins) is dict and set(pins)==set(raws)-UNSEALED-{'job.json'} and all(relative(n) and hash_string(v) and digest(raws[n])==v for n,v in pins.items()),'Complete unchanged native smoke artifacts')
    need(not any(t.lower() in (raws['stdout.txt']+raws['stderr.txt']).decode('utf-8',errors='replace').lower() for t in RENDER_ERRORS),'No smoke renderer softfailure')
    module=load_module('smoke_verify',ctx.data['source/validate.py'],ctx.run/'input/source/validate.py')
    _bind_workspace(ctx,module)
    metrics=module.verify_simulation(ctx.run/'input/model/robot_arm.urdf',parse(raws['report.json']),ctx.cfg,ctx.run/'input/smoke-proof',purpose='render_smoke')
    need(metrics['dynamics_pass'] is True,'Native physics/render smoke full acceptance')
    return old


def portable_policy(actual):
    return (actual, 'WORKER_EXIT') if type(actual) is int and 0 <= actual <= 255 else (1, 'NONPORTABLE_WORKER_EXIT')




def run_child(argv,out,timeout,admit=None,ctx=None):
    rt=_runtime(ctx)
    need(type(timeout) in (int,float) and math.isfinite(timeout) and timeout>2,'Native total cleanup reserve')
    with rt.phase(timeout) as end:
        remaining=end-time.monotonic()
        need(remaining>2,'Native cleanup reserve remains')
        return _run_child_body(argv,out,remaining,admit,ctx)


def _run_child_body(argv,out,timeout,admit,ctx):
    need(ctx is not None,'Snapshot helper required for actual native child')
    initial={'child_pid':None,'actual_child_exit_code':None,'policy_exit_code':1,'policy_basis':'NOT_STARTED',
             'timed_out':False,'child_state':'NOT_STARTED'}
    result=initial;awake=False;delegated=False
    try:
        need(os.name=='nt','Windows Job native worker required')
        need(ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)!=0,'Process-scoped keep-awake failed');awake=True
        helper=_job_helper(ctx);delegated=True
        record=helper.run(argv,Path(out),timeout-2,cleanup_s=2,admit=admit)
        need(type(record) is dict,'Structured native helper result')
        result=record
        if result.get('child_state')=='NOT_CREATED':result['child_state']='NOT_STARTED'
    except BaseException as exc:
        if delegated and result is initial:
            result.update(child_state='UNKNOWN',terminal=False,raw_complete=False,execution_history='UNKNOWN_AFTER_DELEGATION')
        result.update(observation_error=failure_text(exc),policy_exit_code=1,policy_basis='OBSERVATION_FAILURE')
    finally:
        if awake:
            try:
                result['keep_awake_reset']=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
                if not result['keep_awake_reset']:result.update(policy_exit_code=1,policy_basis='KEEP_AWAKE_RESET_FAILED')
            except BaseException as exc:
                result.update(keep_awake_reset=False,keep_awake_reset_error=failure_text(exc),policy_exit_code=1,policy_basis='KEEP_AWAKE_RESET_EXCEPTION')
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


def literal(ctx,role):
    rt=_runtime(ctx)
    need(role in ('native','supervise','export'),'Closed child role')
    return rt.entry_code(ctx,role)



def failure_text(exc):
    try:
        return type(exc).__name__ + ': ' + str(exc)
    except BaseException:
        return type(exc).__name__ + ': <error formatting failed>'


@_ctx_owned()
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


def entry(run,job_hash,driver_sha,role,admission=None,*,runtime):
    rt=_runtime(runtime)
    with rt.phase():
        rt.verify()
        return _entry_body(run,job_hash,driver_sha,role,admission,rt)

def _entry_body(run, job_hash, driver_sha, role, admission, runtime):
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
    ctx=snapshot(run,job_hash,driver_sha,runtime=runtime);ctx.admission=admission
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


@_ctx_owned()
def supervise(ctx):
    need(ctx.run.parent == Path(ctx.cfg['remote_root']), 'Owned fixed remote root')
    out = ctx.run / 'output'
    need(not (out / 'exit.json').exists(), 'Existing native attempt cannot repeat')
    lock = ctx.run.parent / 'session.lock'
    handle = None
    native_invoked=False
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
        probe = _kit_probe(ctx)
        need(probe.returncode == 0 and probe.stdout.strip() == b'0', 'Existing Kit process; do not disturb')
        python = str(Path(ctx.cfg['sdk']['isaac_root']) / 'kit/python/python.exe')
        def admit():
            launch_budget(ctx.cfg,ctx.job['purpose'],now=remote_clock_now(ctx))
            write(out/'admission-clock.json',{'certificate':ctx.admission,'checked_remote_unix':time.time(),'run_id':ctx.run.name,'job_sha256':ctx.job_hash})
            launch_budget(ctx.cfg,ctx.job['purpose'],now=remote_clock_now(ctx))
        argv=[python,'-I','-B','-c',literal(ctx,'native')]
        need(len(subprocess.list2cmdline(argv))<8000,'Actual SDK command length')
        native_invoked=True
        ex.update(run_child(argv,out,
                            native_timeout(ctx.cfg,ctx.job['purpose'],now=remote_clock_now(ctx)),admit=admit,ctx=ctx))
    except BaseException as exc:
        if native_invoked and ex.get('child_state')=='NOT_STARTED':ex['child_state']='UNKNOWN'
        ex['supervisor_error'] = failure_text(exc)
    finally:
        ex['finished_unix'] = time.time()
        code=finalize_parent(out,ctx.job,ctx.job_hash,ex,handle,lock)
    return code



def prepare(source,purpose,*,runtime):
    rt=_runtime(runtime)
    with rt.phase():
        budget=rt.verify()
        need(set(source)==SOURCE and {n:digest(b) for n,b in source.items()}==budget['execution_source'],'Prepared active source21')
        return _prepare_body(source,purpose,rt)

def _prepare_body(source, purpose, runtime):
    need(purpose in PURPOSES, 'Closed prepare purpose')
    cfg = parse(source['config.json'])
    config_contract(cfg)
    cfg=runtime.bind_config(cfg)
    launch_budget(cfg,purpose)
    need(not (runtime.root/OUT/'runs'/('attempt-'+purpose+'.json')).exists(),'Local purpose attempt already consumed')
    config_contract(dict(cfg))
    model = file_bytes(checked_path(runtime.root, cfg['model_dir']))
    need(set(model) == MODEL, 'Exact sixteen source model files')
    payload = {'source/' + n: raw for n, raw in source.items()}
    payload.update({'model/' + n: raw for n, raw in model.items()})
    for key, item in cfg['refs'].items():
        raw = checked_path(runtime.root, item['path']).read_bytes()
        need(digest(raw) == item['sha256'], 'Frozen reference changed ' + key)
        payload['ref/' + key] = raw
    authority=_workspace_authority_contract(runtime.workspace_authority(runtime.workspace_scope()))
    payload['workspace-preflight.json']=authority['receipt_raw']
    pins = {key: digest(raw) for key, raw in payload.items()}
    common = common_signature(pins)
    if purpose in ('render_smoke','motion'):
        verified = read(runtime.root / OUT / 'import-verified.json')
        oldrun = checked_path(runtime.root / OUT / 'runs', verified['run_id'])
        oldctx = snapshot(oldrun, verified['job_sha256'],runtime=runtime)
        need(oldctx.job['common_signature'] == common, 'Current common input differs from import')
        code, accepted = consume(oldctx)
        need(code == 0 and accepted['status'] == 'IMPORT_VERIFIED', 'Actual original import must verify again')
        raws = {n: ((oldrun / 'job.json') if n == 'job.json' else (oldrun / 'retrieved' / n)).read_bytes() for n in PROOF}
        payload.update({'import-proof/' + n: raw for n, raw in raws.items()})
        if purpose=='motion':
            receipt=read(runtime.root/OUT/'smoke-verified.json');sr=checked_path(runtime.root/OUT/'runs',receipt['run_id']);sc=snapshot(sr,receipt['job_sha256'],runtime=runtime);code,accepted=consume(sc);need(code==0 and accepted['status']=='SMOKE_VERIFIED','Original native smoke verified again')
            payload.update({'smoke-proof/'+n:raw for n,raw in file_bytes(sr/'retrieved').items()});payload['smoke-proof/job.json']=(sr/'job.json').read_bytes()
        last=runtime.root/OUT/('last-'+purpose+'.json')
        if last.exists():
            prev=read(last);pr=checked_path(runtime.root/OUT/'runs',prev['run_id']);payload.update({'retry-proof/'+n:(pr/'retrieved'/n).read_bytes() for n in ('terminal.json','exit.json','remote-shell.json')});payload['retry-proof/job.json']=(pr/'job.json').read_bytes();payload['retry-proof/review.json']=(runtime.root/OUT/('repair-'+purpose+'.json')).read_bytes()
    run = runtime.root / OUT / 'runs' / uuid.uuid4().hex
    for key, raw in payload.items():
        target = run / 'input' / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    job = {'schema_version': 1, 'run_id': run.name, 'purpose': purpose,
           'inputs': {key: digest(raw) for key, raw in payload.items()}, 'common_signature': common,
           'plan_sha256': PLAN_SHA, 'hardware_approved': False, 'experiment_id': EXPERIMENT}
    write(run / 'job.json', job)
    ctx = snapshot(run, sha(run / 'job.json'),runtime=runtime)
    validator=load_module('prepare_workspace',source['validate.py'],run/'input/source/validate.py')
    _bind_workspace(ctx,validator)
    validator.verify_workspace(run/'input/model/robot_arm.urdf')
    with zipfile.ZipFile(run / 'bundle.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.write(run / 'job.json', 'job.json')
        for key in payload:
            archive.write(run / 'input' / key, 'input/' + key)
    write(run / 'prepared.json', {'run_id': run.name, 'job_sha256': ctx.job_hash,
          'remote': cfg['remote_root'] + '/' + run.name, 'bundle_sha256': sha(run / 'bundle.zip')})
    return run


def remote(script,alias,timeout=120,*,runtime):
    rt=_runtime(runtime)
    need(type(timeout) in (int,float) and math.isfinite(timeout) and timeout>2,'Local process finite budget')
    with rt.phase(timeout) as end:
        cfg=rt.bind_config(read(rt.root/'src/simulation/typed_decision_preflight_113/config.json'))
        config_contract(dict(cfg));session_now(cfg)
        need(cfg.get('transport_kind')=='LOCAL_PROCESS' and alias==cfg['ssh_alias'],'Explicit same-host backend')
        folder=rt.root/OUT/'local-transport'/uuid.uuid4().hex;folder.mkdir(parents=True)
        script_path=folder/'command.ps1'
        script_bytes=script.encode('utf-8')
        with script_path.open('xb') as stream:stream.write(script_bytes);stream.flush();os.fsync(stream.fileno())
        need("'" not in str(script_path),'Owned script path quote')
        # Fixed short loader consumes the same pinned bytes, with no policy setting.
        loader=("$b=[IO.File]::ReadAllBytes('"+str(script_path)+"');$h=[Security.Cryptography.SHA256]::Create();"
                +"$p=[BitConverter]::ToString($h.ComputeHash($b)).Replace('-','').ToLowerInvariant();"
                +"if($p -ne '"+digest(script_bytes)+"'){throw 'Owned script pin'};"
                +"& ([ScriptBlock]::Create([Text.Encoding]::UTF8.GetString($b)))")
        executable=str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
        argv=[executable,'-NoProfile','-NonInteractive','-Command',loader]
        need(len(subprocess.list2cmdline(argv))<8000,'Actual local command length')
        return _controlled_process(argv,folder,end-time.monotonic(),rt.helper,runtime=rt)





def unpack(archive_path,destination,*,runtime):
    rt=_runtime(runtime)
    with rt.phase(120):return _unpack_body(archive_path,destination)


def _unpack_body(archive_path, destination):
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


def _operation_end(cfg,limit):
    rt=_runtime(cfg)
    need(type(limit) in (int,float) and math.isfinite(limit) and limit>0,'Finite operation lifetime')
    return min(time.monotonic()+limit,rt.end_monotonic)



def recover_transport(ctx,remctx,python,rr,alias):
    rt=_runtime(ctx)
    with rt.phase(600) as mono_end:
        started=session_now(ctx.cfg);mono=time.monotonic();end=recovery_deadline(ctx.cfg,started)
        return _recover_transport_scoped(ctx,remctx,python,rr,alias,rt.helper,started,mono,end,mono_end)



def _recover_transport_scoped(ctx,remctx,python,rr,alias,helper,started,started_mono,end,mono_end):
    need(not any((ctx.run/name).exists() for name in ('recovery-budget.json','recovery-status.json','recovery-receipt.json','records.zip','retrieved')),
         'Recovery already consumed;no overwrite/reset/retry')
    stage='BEFORE_EXPORT'
    try:
        need(time.monotonic()<mono_end,'Recovery absolute lifetime remains')
        with (ctx.run/'recovery-budget.json').open('x',encoding='utf-8') as stream:
            json.dump({'started_unix':started,'deadline_unix':end,'export_timeout_s':300,'total_s':600,'started_monotonic':started_mono,'deadline_monotonic':mono_end,'hardware_approved':False},stream)
            stream.flush();os.fsync(stream.fileno())
        stage='EXPORT'
        call_mono=time.monotonic();window=recovery_timeout(ctx.cfg,end,session_now(ctx.cfg),mono_end,call_mono)
        with helper.Fence(min(mono_end,call_mono+window)):
            need(len(subprocess.list2cmdline([python,'-I','-B','-c',literal(remctx,'export')]))<8000,'Actual SDK export command length')
            result=remote("& '"+python+"' -I -B -c \""+literal(remctx,'export')+"\";exit $LASTEXITCODE",alias,window,runtime=ctx.runtime)
        need(result.returncode==0,'Closed export failed')
        for name in ('recovery-receipt.json','records.zip'):
            stage='COPY_'+name
            call_mono=time.monotonic();window=recovery_timeout(ctx.cfg,end,session_now(ctx.cfg),mono_end,call_mono)
            with helper.Fence(min(mono_end,call_mono+window)):
                copied=_copy_new(Path(rr)/name,ctx.run/name,runtime=ctx.runtime)
                write(ctx.run/('copy-'+name+'.json'),copied)
        stage='VERIFY_AND_UNPACK'
        need(digest(ctx.data['source/recovery.py'])==ctx.job['inputs']['source/recovery.py']==RECOVERY_SHA,'Reviewed local recovery verifier')
        module=load_module('closed_recovery_local',ctx.data['source/recovery.py'],ctx.run/'input/source/recovery.py')
        with ctx.runtime.phase(120):
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



@_ctx_owned()
def launch(ctx, prepared):
    fs_helper=_job_helper(ctx)
    launch_budget(ctx.cfg,ctx.job['purpose'])
    with (ctx.run.parent/('attempt-'+ctx.job['purpose']+'.json')).open('x',encoding='utf-8') as stream:
        json.dump({'purpose':ctx.job['purpose'],'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'started_unix':session_now(ctx.cfg)},stream)
        stream.flush();os.fsync(stream.fileno())
    with (ctx.run/'launch-attempt.json').open('x',encoding='utf-8') as stream:
        json.dump({'run_id':ctx.run.name,'job_sha256':ctx.job_hash,'started_unix':session_now(ctx.cfg)},stream)
    rr, alias = prepared['remote'], ctx.cfg['ssh_alias']
    need(rr == ctx.cfg['remote_root'] + '/' + ctx.run.name and re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+', rr), 'Pinned remote path')
    need(sha(ctx.run / 'bundle.zip') == prepared['bundle_sha256'], 'Pinned transport archive')
    created = remote("$ErrorActionPreference='Stop';if(Test-Path -LiteralPath '" + rr + "'){throw 'Run exists'};New-Item -ItemType Directory -Path '" + rr + "'|Out-Null", alias,runtime=ctx.runtime)
    need(created.returncode == 0, 'Remote create')
    with fs_helper.Fence(_operation_end(ctx.cfg,120)):
        _copy_new(ctx.run/'bundle.zip',Path(rr)/'bundle.zip',prepared['bundle_sha256'],runtime=ctx.runtime,limit=120)
    with fs_helper.Fence(_operation_end(ctx.cfg,120)):
        _extract_local(Path(rr)/'bundle.zip',Path(rr),prepared['bundle_sha256'],runtime=ctx.runtime)
    ctx.admission=clock_probe(ctx)
    with (ctx.run/'admission-clock.json').open('x',encoding='utf-8') as stream:json.dump(ctx.admission,stream)
    launch_budget(ctx.cfg,ctx.job['purpose'])
    remctx = types.SimpleNamespace(run=Path(rr), job_hash=ctx.job_hash, job=ctx.job,admission=ctx.admission,runtime=ctx.runtime,cfg=ctx.cfg)
    python = str(Path(ctx.cfg['sdk']['isaac_root']) / 'kit/python/python.exe')
    need(len(subprocess.list2cmdline([python,'-I','-B','-c',literal(remctx,'supervise')]))<8000,'Actual SDK supervise command length')
    need("'" not in python, 'SDK executable quote')
    script = ("& '" + python + "' -I -B -c \"" + literal(remctx, 'supervise') + "\";$ec=$LASTEXITCODE;if($null -eq $ec){$ec=1};"
              + "$r=@{run_id='" + ctx.run.name + "';job_sha256='" + ctx.job_hash + "';python_exit_code=[int]$ec};"
              + "[IO.File]::WriteAllText('" + rr + "/output/remote-shell.json',($r|ConvertTo-Json),[Text.UTF8Encoding]::new($false));exit $ec")
    try:
        launch_budget(ctx.cfg,ctx.job['purpose'])
        result = remote(script, alias, transport_timeout(ctx.cfg,ctx.job['purpose']),runtime=ctx.runtime)
        transport = {'returncode': result.returncode, 'timed_out': False, 'transport_kind':'LOCAL_PROCESS', 'process':result.record}
        (ctx.run / 'transport-stdout.txt').write_bytes(result.stdout)
        (ctx.run / 'transport-stderr.txt').write_bytes(result.stderr)
    except subprocess.TimeoutExpired as exc:
        transport = {'returncode': None, 'timed_out': True, 'error': repr(exc), 'transport_kind':'LOCAL_PROCESS'}
        (ctx.run / 'transport-stdout.txt').write_bytes(exc.stdout or b'')
        (ctx.run / 'transport-stderr.txt').write_bytes(exc.stderr or b'')
    write(ctx.run / 'transport.json', transport)
    # Recovery is separately bounded; it never changes the native transport record.
    recover_transport(ctx,remctx,python,rr,alias)



@_ctx_owned()
def consume(ctx):
    out = ctx.run / 'retrieved'
    raw = file_bytes(out)
    need({'terminal.json', 'exit.json', 'remote-shell.json', 'stdout.txt', 'stderr.txt'} <= set(raw), 'Required original process records/logs')
    terminal, ex, shell = (parse(raw[n]) for n in ('terminal.json', 'exit.json', 'remote-shell.json'))
    verify_parent_recovery(ctx.job,ctx.job_hash,raw,ex)
    code = process_contract(ctx.job, ctx.job_hash, terminal, ex, shell)
    transport = read(ctx.run / 'transport.json')
    need(transport.get('transport_kind')=='LOCAL_PROCESS' and transport.get('timed_out') is False and type(transport.get('returncode')) is int and transport['returncode'] == code, 'Actual same-host process return code')
    pins = terminal.get('files_sha256')
    need(type(pins) is dict and all(relative(k) and hash_string(v) for k, v in pins.items()), 'Typed terminal hashes')
    need(set(pins) == set(raw) - UNSEALED, 'Exact terminal artifact inventory')
    need(all(digest(raw[n]) == value for n, value in pins.items()), 'All original output artifacts sealed')
    need(not any(error.lower() in (raw['stdout.txt'] + raw['stderr.txt']).decode('utf-8', errors='replace').lower() for error in RENDER_ERRORS), 'Native renderer scheduling firstfault')
    bind_sources(ctx)
    validate = load_module('validate', ctx.data['source/validate.py'], ctx.run / 'input/source/validate.py')
    _bind_workspace(ctx,validate)
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


@_ctx_owned()
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


def publish_validation(run,result,*,runtime):
    rt=_runtime(runtime)
    with rt.phase():return _publish_validation_body(run,result)


def _publish_validation_body(run,result):
    primary=run/'validation.json';value=dict(result)
    if primary.exists():
        value['initial_validation_sha256']=sha(primary)
        target=run/('validation-query-'+uuid.uuid4().hex+'.json')
    else:target=primary
    value['validation_file']=target.name
    with target.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return value


def public(role,run_dir='',purpose='',*,runtime):
    rt=_runtime(runtime)
    with rt.phase():
        rt.verify()
        return _public_body(role,run_dir,purpose,rt)

def _public_body(role,run_dir,purpose,runtime):
    source = own_source(runtime=runtime)
    need(role!='test','Legacy108 HOST entry is archived; use test_driver.py')
    if role == 'prepare':
        print(prepare(source,purpose,runtime=runtime))
        return 0
    need(role in ('run', 'verify'), 'Closed public role')
    run = Path(run_dir)
    need(run.is_absolute() and run.parent == runtime.root / OUT / 'runs', 'Owned local run root')
    prepared = read(run / 'prepared.json')
    ctx = snapshot(run,prepared['job_sha256'],digest(source['driver.py']),runtime=runtime)
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
    result=publish_validation(run,result,runtime=runtime)
    write(runtime.root / OUT / 'current.json', result)
    if result['status'] in ('IMPORT_VERIFIED','SMOKE_VERIFIED'):
        name='import-verified.json' if result['status']=='IMPORT_VERIFIED' else 'smoke-verified.json'
        write(runtime.root / OUT / name, {'run_id': run.name, 'job_sha256': ctx.job_hash})
    if role=='run':
        write(runtime.root / OUT / ('last-'+ctx.job['purpose']+'.json'), {'run_id':run.name,'job_sha256':ctx.job_hash})
    print(json.dumps(result, allow_nan=False))
    return code



def _job_helper(ctx=None,*,runtime=None):
    rt=_runtime(ctx if runtime is None else runtime)
    if ctx is not None and hasattr(ctx,'data'):
        need(ctx.data['source/winjob.py']==rt.helper_bytes and digest(rt.helper_bytes)==ctx.cfg['winjob_sha256']==ctx.job['inputs']['source/winjob.py'],'Closed snapshot helper bytes')
    return rt.helper



class ControlledProcessFailure(ValueError):
    def __init__(self,primary,record):
        super().__init__(failure_text(primary));self.primary=primary;self.process_record=record


def _controlled_process(argv,folder,total,helper,*,runtime):
    rt=_runtime(runtime)
    need(helper is rt.helper,'Memory-owned helper')
    with rt.phase(total) as end:
        return _controlled_process_body(argv,folder,end-time.monotonic(),helper)


def _controlled_process_body(argv,folder,total,helper):
    need(type(total) in (int,float) and math.isfinite(total) and total>2,'Shared process cleanup reserve')
    record=helper.run(argv,Path(folder),total-2,cleanup_s=2)
    try:
        write(Path(folder)/'process.json',record)
        need(record.get('terminal') is True and record.get('raw_complete') is True
             and type(record.get('job_active_after')) is int and record['job_active_after']==0
             and type(record.get('child_pid')) is int and record['child_pid']>0
             and record.get('child_state')=='REAPED' and type(record.get('actual_child_exit_code')) is int
             and type(record.get('policy_exit_code')) is int and type(record.get('timed_out')) is bool
             and type(record.get('errors')) is list and not record['errors'],'Actual owned process and raw closure')
        stdout=(Path(folder)/'stdout.txt').read_bytes();stderr=(Path(folder)/'stderr.txt').read_bytes()
        if record['timed_out']:
            raise subprocess.TimeoutExpired(argv,total,output=stdout,stderr=stderr)
        need(record['actual_child_exit_code']==record['policy_exit_code'],'Actual child/policy code agreement')
        return types.SimpleNamespace(returncode=record['actual_child_exit_code'],stdout=stdout,stderr=stderr,record=record)
    except subprocess.TimeoutExpired as exc:
        exc.process_record=record
        raise
    except BaseException as exc:
        raise ControlledProcessFailure(exc,record) from exc



@_ctx_owned(20)
def _kit_probe(ctx):
    folder=ctx.run/'output/kit-probe';folder.mkdir()
    executable=str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
    return _controlled_process([executable,'-NoProfile','-NonInteractive','-Command',
        '@(Get-Process -Name kit,isaacsim -ErrorAction SilentlyContinue).Count'],folder,
        min(20,ctx.cfg['deadline_unix']-remote_clock_now(ctx)),_job_helper(ctx),runtime=ctx.runtime)


def _copy_new(source,destination,expected=None,*,runtime,limit=300):
    rt=_runtime(runtime)
    with rt.phase(limit):return _copy_new_body(source,destination,expected)


def _copy_new_body(source,destination,expected=None):
    source,destination=Path(source),Path(destination)
    for p in (source,destination):
        need(p.is_absolute() and all(no_link(q) for q in (p,*p.parents)),'Local copy safe absolute paths')
    need(source.is_file() and destination.parent.is_dir() and not destination.exists(),'Exclusive actual local copy')
    raw=source.read_bytes();pin=digest(raw)
    if expected is not None:need(hash_string(expected) and pin==expected,'Local copy expected bytes')
    with destination.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    need(sha(destination)==pin,'Actual copied bytes')
    return {'transport_kind':'LOCAL_COPY','source':str(source),'destination':str(destination),'bytes':len(raw),'sha256':pin}


def _extract_local(archive,destination,pin,*,runtime):
    rt=_runtime(runtime)
    with rt.phase(120):return _extract_local_body(archive,destination,pin)


def _extract_local_body(archive,destination,pin):
    import io
    archive,destination=Path(archive),Path(destination)
    need(archive.is_absolute() and destination.is_absolute() and destination.is_dir(),'Owned local extraction')
    need(all(no_link(p) for p in (archive,*archive.parents,destination,*destination.parents)),'Extraction ancestry')
    raw=archive.read_bytes();need(digest(raw)==pin,'Single-read archive pin')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();need(names and len(names)==len(set(names)) and all(relative(n) for n in names),'Closed safe archive names')
        need(all((i.external_attr>>16)&0o170000!=0o120000 for i in z.infolist()),'Archive link rejected')
        for name in names:
            target=checked_path(destination,name);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(z.read(name))
    return {'transport_kind':'LOCAL_EXTRACT','sha256':pin,'files':len(names)}



def controller(runtime):
    rt=_runtime(runtime)
    with rt.phase():
        rt.verify()
        for purpose in PURPOSES:
            source=own_source(runtime=rt)
            run=prepare(source,purpose,runtime=rt)
            code=public('run',str(run),runtime=rt)
            if code!=0:return code
        return 0

if __name__ == '__main__':
    raise SystemExit('Use launch.ps1')
