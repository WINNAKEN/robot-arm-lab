"""Unit129 deterministic release from immutable reviewed originals. stdlib only."""
from __future__ import annotations
import ast
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import types
import zlib

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'outputs/mp18-video-run-129'
DERIVED=ROOT/'src/simulation/mp18_isaac_129'
PLAN='docs/design/129-constraint-order-and-cpu-contact-repair.md'
PLAN_SHA='0cff488303d57d2f1937ddf356fd1b7a92feb81abb4b3e18e40e55bbc9e632e0'
BASE={
 'driver.py':'d28a2a9c689486a48173ac9d3d4871959f4b23e5df0d6671e630c4086db8e001',
 'contract.py':'9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf',
 'config.json':'401d0bc27b72b628e50de1db8dba735d4e3a9ccf4ff7fd54fbb377f476415350',
 'program.json':'521772bfbe4e85023bc5de67a5bc6be8ce200b0ffa5a4dbe6336161315225474',
 'media.py':'dfa72243410208113bc2bfc02f880871e88982ca7f4c379c84e881fcff9a0fe9'}
CANDIDATE='outputs/mp18-layer-lifetime-126/candidate/native.py'
CANDIDATE_SHA='06a36b35713337d42fdb76f6f3ac161d56d6cb3cb7ce47f4d2fa683176c22e17'
CAP='outputs/mp18-isaac-119/user-decision.json'
CAP_SHA='7b647795939751e85b1140e53c76600a22074d1ed691fbb3cbf27b4ba3cfee6c'
PROXY='src/simulation/mp18_ssh_raw_stdin_123/driver.py'
PROXY_SHA='8e8b134556ffad2faf105c73440b07af83baef408069331fdcfb1b40703855ad'


def need(ok,message):
    if not ok:raise ValueError(message)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    def bad(x):raise ValueError('Nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def path_guard(path,root=ROOT):
    path=Path(path)
    need(path.is_absolute() and path.is_relative_to(root),'Original ROOT namespace')
    for p in (path,*path.parents):need(not p.is_symlink() and not p.is_junction(),'Reparse role rejected')
    need(root.resolve()==root and path.resolve().is_relative_to(root),'Original namespace resolution')
    return path


def read(path):return path_guard(path).read_bytes()


def verify_files(files):
    # Deduplicate common ancestor queries per current check; no metadata/hash cache across uses.
    paths=[Path(p) for p,b in files]
    need(all(p.is_absolute() and p.is_relative_to(ROOT) for p in paths),'Current original ROOT paths')
    for p in {p for x in paths for p in (x,*x.parents)}:
        need(not p.is_symlink() and not p.is_junction(),'Current path/ancestor role')
    need(ROOT.resolve()==ROOT,'Current ROOT identity')
    for p,expected in files:
        need(Path(p).resolve().is_relative_to(ROOT) and Path(p).read_bytes()==expected,'Current immutable bytes drift: '+str(p))


def exclusive(path,data,guard=lambda:None):
    guard();path_guard(path).parent.mkdir(parents=True,exist_ok=True);guard();path_guard(path)
    with Path(path).open('xb') as stream:
        guard();stream.write(data)


def load_raw(name,data,path):
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(data,str(path),'exec'),module.__dict__)
    return module


def _nodes(raw):return ast.parse(raw).body


def _span(raw,node):
    lines=raw.splitlines(keepends=True)
    a=sum(map(len,lines[:node.lineno-1]))+node.col_offset
    b=sum(map(len,lines[:node.end_lineno-1]))+node.end_col_offset
    return a,b


def _splice(raw,changes):
    edits=[]
    for label,node,replacement in changes:
        a,b=_span(raw,node);edits.append((a,b,label,replacement.encode()))
    edits.sort();need(all(x[1]<=y[0] for x,y in zip(edits,edits[1:])),'Nonoverlapping AST spans')
    cursor=0;parts=[];records=[]
    for a,b,label,replacement in edits:
        parts.extend((raw[cursor:a],replacement));records.append({'scope':label,'start_byte':a,'end_byte':b,
            'original_span_sha256':digest(raw[a:b]),'replacement_sha256':digest(replacement),'replacement_bytes':len(replacement)})
        cursor=b
    parts.append(raw[cursor:]);result=b''.join(parts);ast.parse(result)
    return result,{'edits':records,'outside_replaced_spans_byte_identical':True}


LOCAL_HELPERS='''_LOCAL_GUARD = None
_LOCAL_INPUT = None

def bind_local_authority(guard, resolver):
    need(callable(guard) and callable(resolver), 'Explicit local129 authority callbacks')
    global _LOCAL_GUARD, _LOCAL_INPUT
    _LOCAL_GUARD, _LOCAL_INPUT = guard, resolver

def _local_guard():
    need(callable(_LOCAL_GUARD), 'Local129 current authority is not bound')
    _LOCAL_GUARD()

def _local_write_guard(path):
    _local_guard()
    p = Path(path)
    need(p.is_absolute() and OUT.is_relative_to(ROOT) and p.is_relative_to(OUT), 'Original129 local output role')
    for item in (p, *p.parents):
        need(not item.is_symlink() and not item.is_junction(), 'Local write reparse role')
    need(ROOT.resolve() == ROOT and p.resolve().is_relative_to(OUT), 'Original129 local output anchor')
    return p

def _payload_bytes(path):
    need(callable(_LOCAL_INPUT), 'Local129 immutable payload resolver is not bound')
    value = _LOCAL_INPUT(Path(path))
    need(type(value) is bytes, 'Immutable input bytes')
    return value
'''

TYPED_GATE='''def _review_gate():
    freeze_path = OUT/'review/source-freeze.json'
    freeze_raw = freeze_path.read_bytes()
    freeze = parse(freeze_raw)
    need(type(freeze.get('unit')) is int and freeze['unit'] == 129, 'Typed129 source freeze')
    required = {'src/simulation/mp18_video_run_129/'+n for n in ('release.py','runner.py','test_runner.py')}
    required |= {'src/simulation/mp18_isaac_129/'+n for n in ('driver.py','contract.py','native.py','config.json','program.json','media.py')}
    need(type(freeze['files']) is dict and required <= set(freeze['files']), 'Complete129 source release')
    for relative, item in freeze['files'].items():
        p = C.path_in(ROOT, relative)
        raw = p.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == item['sha256'] and len(raw) == item['bytes'], 'Current129 source drift')
    for name in ('main',):
        report = read(OUT/('review/'+name+'-L4-final.json'))
        need(type(report.get('unit')) is int and report['unit'] == 129 and report['phase'] == 'L4' and
             type(report['round']) is int and report['round'] in (1,2) and report['non_author'] is True and
             report['verdict'] == 'PASS' and type(report['unmet']) is int and report['unmet'] == 0 and
             type(report['unresolved_count']) is int and report['unresolved_count'] == 0 and
             report['source_freeze_sha256'] == hashlib.sha256(freeze_raw).hexdigest(), 'Final typed129 independent source authority')
'''

PREPARE='''def prepare():
    _review_gate()
    _local_guard()
    need(not (OUT/'prepared.json').exists(), 'Own prepared identity already exists')
    cfg = parse(_payload_bytes(HERE/'config.json'))
    approval = parse(_payload_bytes(OUT/'user-decision.json'))
    C.effective_caps(cfg, approval)
    inputs = {}
    for name in ('driver.py','contract.py','native.py','config.json','program.json'):
        inputs['source/'+name] = _payload_bytes(HERE/name)
    for name, pin in cfg['model_pins'].items():
        b = _payload_bytes(C.path_in(ROOT/cfg['model_dir'], name))
        need(hashlib.sha256(b).hexdigest() == pin['sha256'] and len(b) == pin['bytes'], 'Captured original model pin')
        inputs['model/'+name] = b
    for name, item in cfg['refs'].items():
        b = _payload_bytes(C.path_in(ROOT,item['path']))
        need(hashlib.sha256(b).hexdigest() == item['sha256'], 'Captured original dependency pin')
        inputs['ref/'+name] = b
    inputs['approval.json'] = _payload_bytes(OUT/'user-decision.json')
    run_id, nonce = uuid.uuid4().hex, uuid.uuid4().hex
    run = OUT/'runs'/run_id
    job = {'unit':119,'schema_version':1,'purpose':'v4_validation_video','run_id':run_id,'nonce':nonce,
           'hardware_approved':False,'inputs':{n:hashlib.sha256(b).hexdigest() for n,b in inputs.items()}}
    raw_job = json.dumps(job,separators=(',',':'),sort_keys=True).encode()
    _local_write_guard(run).mkdir(parents=True,exist_ok=False)
    _local_write_guard(run/'bundle.zip')
    with zipfile.ZipFile(run/'bundle.zip','x',zipfile.ZIP_DEFLATED) as z:
        _local_write_guard(run/'bundle.zip');z.writestr('job.json',raw_job)
        for name,b in inputs.items():
            _local_write_guard(run/'bundle.zip');z.writestr('input/'+name,b)
        _local_write_guard(run/'bundle.zip')
    _local_write_guard(run/'job.json')
    with (run/'job.json').open('xb') as stream:stream.write(raw_job)
    record = {'run_id':run_id,'nonce':nonce,'bundle_sha256':sha(run/'bundle.zip'),'bundle_bytes':(run/'bundle.zip').stat().st_size,
              'job_sha256':hashlib.sha256(raw_job).hexdigest(),'driver_sha256':hashlib.sha256(inputs['source/driver.py']).hexdigest()}
    verified_payload(run,record)
    write(OUT/'prepared.json',record)
    return record
'''


def build_driver(raw):
    nodes=_nodes(raw);named={n.name:n for n in nodes if isinstance(n,ast.FunctionDef)}
    assignment=lambda name:next(n for n in nodes if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    write_raw=raw[_span(raw,named['write'])[0]:_span(raw,named['write'])[1]].decode()
    write_raw=write_raw.replace("    p = Path(path)","    p = Path(path)\n    if _ACTIVE_OUT is None: _local_write_guard(p)",1)
    write_raw=write_raw.replace("    p.write_text(","    if _ACTIVE_OUT is None: _local_write_guard(p)\n    p.write_text(",1)
    remote=raw[_span(raw,named['remote_supervise'])[0]:_span(raw,named['remote_supervise'])[1]].decode()
    remote=remote.replace('def remote_supervise(run, deadline):','def remote_supervise(run, deadline, expected_job_sha256):').replace('ctx = _context(run)','ctx = _context(run, expected_job_sha256)')
    old='''    code = ("import importlib.util,pathlib; p=pathlib.Path("+repr(str(source))+ "); "
            "s=importlib.util.spec_from_file_location('worker119',p); m=importlib.util.module_from_spec(s); "
            "import sys;sys.modules[s.name]=m;s.loader.exec_module(m);raise SystemExit(m.native_main(p.parents[2]))")'''
    new='''    expected_driver = ctx.job['inputs']['source/driver.py']
    need(hashlib.sha256(ctx.data['source/driver.py']).hexdigest() == expected_driver, 'Captured parent driver pin')
    code = ("import pathlib,hashlib,types,sys; p=pathlib.Path("+repr(str(source))+"); b=p.read_bytes(); "
            "assert hashlib.sha256(b).hexdigest()=="+repr(expected_driver)+"; "
            "m=types.ModuleType('worker129');m.__file__=str(p);sys.modules[m.__name__]=m;"
            "exec(compile(b,str(p),'exec'),m.__dict__);raise SystemExit(m.native_main(p.parents[2],"+repr(expected_job_sha256)+"))")'''
    need(remote.count(old)==1,'Exact old child loader boundary');remote=remote.replace(old,new)
    context=raw[_span(raw,named['_context'])[0]:_span(raw,named['_context'])[1]].decode()
    need(context.count("job = read(run/'job.json')")==1 and context.count("job_hash=sha(run/'job.json')")==1,'Exact context job authority boundary')
    context=context.replace('def _context(run):','def _context(run, expected_job_sha256):')
    context=context.replace("job = read(run/'job.json')","need(type(expected_job_sha256) is str and re.fullmatch('[0-9a-f]{64}', expected_job_sha256), 'Mandatory original expected job hash')\n    job_raw = (run/'job.json').read_bytes()\n    need(hashlib.sha256(job_raw).hexdigest() == expected_job_sha256, 'Original expected job hash before context inputs')\n    job = parse(job_raw)")
    context=context.replace("job_hash=sha(run/'job.json')","job_hash=hashlib.sha256(job_raw).hexdigest()")
    native_entry=raw[_span(raw,named['native_main'])[0]:_span(raw,named['native_main'])[1]].decode()
    native_entry=native_entry.replace('def native_main(run):','def native_main(run, expected_job_sha256):').replace('ctx = _context(run)','ctx = _context(run, expected_job_sha256)')
    bootstrap=raw[_span(raw,named['_bootstrap'])[0]:_span(raw,named['_bootstrap'])[1]].decode()
    need(bootstrap.count("mod.remote_supervise(run, state['end'])")==1,'Exact expected-job bootstrap admission')
    bootstrap=bootstrap.replace("mod.remote_supervise(run, state['end'])","mod.remote_supervise(run, state['end'], args['job_sha256'])")
    craw='''def _checked_contract_bytes():
    value = (HERE/'contract.py').read_bytes()
    need(hashlib.sha256(value).hexdigest() == %r, 'Fixed contract raw before execution')
    return value

C = load_module('contract129', _checked_contract_bytes(), HERE/'contract.py')''' % BASE['contract.py']
    changes=[('OUT129',assignment('OUT'),"OUT = ROOT/'outputs/mp18-video-run-129'"),
             ('checked contract loader',assignment('C'),craw),('local current callbacks',named['write'],LOCAL_HELPERS+'\n'+write_raw),
             ('typed129 gate',named['_review_gate'],TYPED_GATE.rstrip()),('same job raw parse/hash',named['_context'],context),('immutable prepare',named['prepare'],PREPARE.rstrip()),
             ('checked SDK child loader and original job authority',named['remote_supervise'],remote),
             ('mandatory native original job authority',named['native_main'],native_entry),
             ('bootstrap original job authority forwarding',named['_bootstrap'],bootstrap),
             ('retired inspect bootstrap',named['bootstrap_code'],"def bootstrap_code(args):\n    raise ValueError('Retired inspect bootstrap; use captured129 AST builder')"),
             ('retired old run_remote',named['run_remote'],"def run_remote():\n    raise ValueError('Retired old entry; use reviewed unit129 runner')")]
    # Keep original imports harmless, including inspect; no getsource call remains executable.
    return _splice(raw,changes)


def build_media(raw,driver_sha):
    nodes=_nodes(raw);named={n.name:n for n in nodes if isinstance(n,ast.FunctionDef)}
    loader=nodes[17:21] # Assert actual AST ownership rather than relying on this slice alone.
    start=next(n for n in nodes if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='s' for t in n.targets))
    end=next(n for n in nodes if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='s.loader.exec_module')
    a,b=_span(raw,start)[0],_span(raw,end)[1]
    replacement=('import hashlib, types\n'
        'def _load_checked_driver129():\n'
        '    value = (HERE/\'driver.py\').read_bytes()\n'
        '    if hashlib.sha256(value).hexdigest() != '+repr(driver_sha)+': raise ValueError(\'Derived driver pin before media execution\')\n'
        '    module = types.ModuleType(\'media_driver129\'); module.__file__ = str(HERE/\'driver.py\')\n'
        '    sys.modules[module.__name__] = module\n'
        '    exec(compile(value,module.__file__,\'exec\'),module.__dict__)\n'
        '    return module\n'
        'D = _load_checked_driver129()')
    # Replace the contiguous original loader once, then reparse for the remaining AST spans.
    first=raw[:a]+replacement.encode()+raw[b:];nodes=_nodes(first);named={n.name:n for n in nodes if isinstance(n,ast.FunctionDef)}
    enc=first[_span(first,named['encode'])[0]:_span(first,named['encode'])[1]].decode()
    enc=enc.replace('robot-arm-v4-119.mp4','robot-arm-v4-129.mp4').replace("{'unit': 119", "{'unit': 129")
    old_capture = """    with zipfile.ZipFile(run/'bundle.zip') as z:
        raw = z.read('input/ref/capture.py')
        cfg = C.parse(z.read('input/source/config.json'))
        C.need(C.sha(OUT/'user-decision.json') == D.read(run/'job.json')['inputs']['approval.json'], 'Actual cap decision')"""
    new_capture = """    cfg = C.parse(D._payload_bytes(HERE/'config.json'))
    capture_item = cfg['refs']['capture.py']
    raw = D._payload_bytes(C.path_in(D.ROOT,capture_item['path']))
    C.need(hashlib.sha256(raw).hexdigest() == capture_item['sha256'], 'Captured native frame validator pin')
    C.need(D._payload_bytes(OUT/'user-decision.json') == (OUT/'user-decision.json').read_bytes(), 'Actual current cap decision')"""
    need(enc.count(old_capture)==1,'Exact media capture loader boundary');enc=enc.replace(old_capture,new_capture)
    enc=enc.replace("    delivery.mkdir(parents=True, exist_ok=True)","    D._local_write_guard(delivery).mkdir(parents=True, exist_ok=True)")
    enc=enc.replace("    invoke([ffmpeg, '-hide_banner', '-v', 'error', '-n', '-framerate'", "    D._local_write_guard(movie)\n    invoke([ffmpeg, '-hide_banner', '-v', 'error', '-n', '-framerate'")
    enc=enc.replace("    for index in samples:\n        invoke", "    for index in samples:\n        D._local_write_guard(delivery/('preview-%04d.png' % index))\n        invoke")
    enc=enc.replace("'upload_allowlist': [movie.name, 'result.json']","'upload_allowlist': [movie.name]")
    changes=[('video129 labels, MP4-only metadata and current local write authority',named['encode'],enc)]
    for n in nodes:
        if isinstance(n,ast.FunctionDef) and n.name in ('self_test','owned','inventory','publisher_inputs','publish'):
            changes.append(('retired '+n.name,n,"def "+n.name+('():' if n.name!='publish' else '(preflight=False):')+"\n    raise ValueError('Legacy Git/publisher/self-test retired in129')"))
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('OWNED','PLAN','HEADER') for t in n.targets):
            changes.append(('retired publisher metadata',n,'# Retired original publisher metadata'))
        if isinstance(n,ast.If) and ast.unparse(n.test)=="__name__ == '__main__'":
            changes.append(('media CLI encode only',n,"if __name__ == '__main__':\n    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('encode',));parser.parse_args();print(json.dumps(encode(),ensure_ascii=False))"))
    result,meta=_splice(first,changes);meta['checked_loader_origin_span']={'start_byte':a,'end_byte':b,'sha256':digest(raw[a:b])}
    return result,meta


NATIVE_HELPERS = "def _diag_owned(value, budget=None, depth=0):\n    budget = [16384] if budget is None else budget\n    budget[0] -= 1\n    if budget[0] < 0 or depth > 12: raise ValueError('Diagnostic bounded copy overflow')\n    if value is None or type(value) in (str, bool, int):\n        return value[:2000] if type(value) is str else value\n    if type(value) is float:\n        return value if math.isfinite(value) else {'nonfinite': repr(value)}\n    if isinstance(value, (list, tuple)):\n        return [_diag_owned(v, budget, depth+1) for v in value]\n    if isinstance(value, dict):\n        return {str(k)[:200]: _diag_owned(v, budget, depth+1) for k,v in value.items()}\n    raise ValueError('Diagnostic nonprimitive copy: '+type(value).__name__)\n\n\ndef _diag_secondary(ctx, label, exc):\n    rows = getattr(ctx, '_diag_secondary', None)\n    if rows is None: rows = []; ctx._diag_secondary = rows\n    try: message=str(exc)[:1000]\n    except BaseException: message='UNKNOWN_EXCEPTION_MESSAGE'\n    if len(rows) < 12: rows.append({'where': label, 'type': type(exc).__name__, 'message': message})\n\n\ndef _diag_final_copy(ctx, label, value):\n    try: return _diag_owned(value)\n    except BaseException as exc:\n        _diag_secondary(ctx,label,exc)\n        return {'status':'UNKNOWN_DIAGNOSTIC_COPY_ERROR','type':type(exc).__name__}\n\n\ndef _fault_begin(ctx, phase, step, target, previous, proof, remaining):\n    ctx._fault_pending = {'status':'UNVALIDATED', 'attempted_phase':phase, 'attempted_step':step,\n        'current_state':None, 'current_state_status':'PENDING_READ', 'observed_state_index':None, 'accepted_journal':False}\n    try:\n        probe=getattr(ctx,'_contact_probe',None)\n        if probe is not None:\n            previous_contact=_diag_owned(probe.last)\n            probe.last={'status':'UNKNOWN_NOT_OBSERVED_FOR_ATTEMPT','owner_step':step,\n                'native_timestamp':'NOT_PROVIDED_BY_HEADER','previous_contact':previous_contact}\n        ctx._fault_pending.update({'previous_state':_diag_owned(previous), 'target':_diag_owned(target),\n            'FF':_diag_owned(proof), 'remaining_cap':_diag_owned(remaining)})\n    except BaseException as exc: _diag_secondary(ctx, 'pending_context_copy', exc)\n\n\ndef _fault_raw(ctx, clock, names, q, qd):\n    pending = getattr(ctx, '_fault_pending', None)\n    if pending is None: return\n    try:\n        pending['raw_state_read'] = _diag_owned({'owner_read_clock':clock, 'names':list(names), 'q':list(q), 'qd':list(qd)})\n    except BaseException as exc: _diag_secondary(ctx, 'raw_state_copy', exc)\n\n\ndef _fault_raw_poses(ctx, poses, after):\n    pending = getattr(ctx, '_fault_pending', None)\n    if pending is None: return\n    try: pending['raw_pose_read'] = _diag_owned({'body_poses':poses,'owner_clock_after':after})\n    except BaseException as exc: _diag_secondary(ctx, 'raw_pose_copy', exc)\n\n\ndef _fault_observe(ctx, current):\n    pending = getattr(ctx, '_fault_pending', None)\n    if pending is None: return\n    try:\n        observed = _diag_owned(current)\n        index = observed['clock']['lab_step']\n        pending['current_state'] = observed\n        pending['observed_state_index'] = index\n        pending['current_state_status'] = 'AVAILABLE_UNVALIDATED' if index == pending['attempted_step'] else 'STALE_NOT_CURRENT'\n    except BaseException as exc:\n        pending['current_state_status'] = 'UNAVAILABLE_COPY_FAILED'\n        _diag_secondary(ctx, 'poststep_state_copy', exc)\n\n\ndef _save_first_fault(ctx, report, primary):\n    if hasattr(ctx, '_first_fault'): return\n    pending = getattr(ctx, '_fault_pending', None)\n    if pending is None:\n        pending = {'attempted_phase':'setup', 'attempted_step':report.get('completed_steps'),\n            'current_state':None, 'current_state_status':'NOT_MEASURED_SETUP', 'observed_state_index':None,\n            'accepted_journal':False}\n    try:\n        packet = _diag_final_copy(ctx,'first_fault_pending_copy',pending)\n        if packet.get('status')=='UNKNOWN_DIAGNOSTIC_COPY_ERROR':\n            packet={'status':'UNVALIDATED','attempted_phase':pending.get('attempted_phase','UNKNOWN'),\n                'attempted_step':pending.get('attempted_step'), 'current_state':None,\n                'current_state_status':'UNAVAILABLE_DIAGNOSTIC_COPY_ERROR','observed_state_index':None,'accepted_journal':False}\n        if packet.get('current_state') is None and packet.get('current_state_status')=='PENDING_READ':\n            packet['current_state_status']='UNAVAILABLE_STATE_READ_OR_STEP_FAILED'\n        packet['current_measurement_available']=packet.get('current_state') is not None and packet.get('observed_state_index')==packet.get('attempted_step')\n        contact=_diag_final_copy(ctx,'first_fault_contact_copy',getattr(getattr(ctx,'_contact_probe',None),'last',{'status':'UNKNOWN_NOT_OBSERVED'}))\n        if contact.get('status')=='CURRENT_STEP_REPORT_COPIED':\n            current_clock=(packet.get('current_state') or {}).get('clock')\n            if contact.get('owner_step')!=packet.get('attempted_step') or contact.get('owner_clock_before')!=current_clock or contact.get('owner_clock_after')!=current_clock:\n                contact={'status':'UNKNOWN_STALE_CONTACT_NOT_CURRENT','owner_step':packet.get('attempted_step'),'previous_contact':contact}\n        packet.update({'schema_version':1, 'classification':'UNVALIDATED_FIRST_FAULT_NOT_ACCEPTED_TRAJECTORY',\n            'run_id':ctx.job['run_id'], 'job_sha256':ctx.job_hash,\n            'primary':{'type':type(primary).__name__, 'message':str(primary)[:2000]},\n            'contact':contact,\n            'velocity_limits':_diag_final_copy(ctx,'first_fault_velocity_copy',getattr(ctx, '_velocity_audit', {})),\n            'secondary':_diag_final_copy(ctx,'first_fault_secondary_copy',getattr(ctx, '_diag_secondary', []))})\n        ctx._first_fault = packet\n        report['first_fault'] = {'path':'first-fault.json', 'classification':packet['classification'],\n            'attempted_step':packet['attempted_step'], 'observed_state_index':packet['observed_state_index'],\n            'current_state_status':packet['current_state_status'], 'saved':False}\n        try:\n            ctx.write(ctx.run/'output/first-fault.json', packet)\n            report['first_fault']['saved'] = True\n        except BaseException as exc: _diag_secondary(ctx, 'first_fault_write', exc)\n    except BaseException as exc: _diag_secondary(ctx, 'first_fault_build', exc)\n\n\ndef _velocity_limits(ctx, robot, names, model, C, array, backend, clock, state=None, repair=False):\n    phase = 'tensor_after_reset' if repair else 'usd_before_reset'\n    if not hasattr(ctx, '_velocity_audit'): ctx._velocity_audit = {}\n    record = {'status':'OBSERVING', 'names':list(names), 'source_SI':{n:model['joints'][n]['velocity'] for n in names},\n        'set_same_source_values':False, 'phase':phase}\n    ctx._velocity_audit[phase] = record\n    need(len(names)==9 and len(set(names))==9 and set(names)==set(model['movable']), 'Velocity binding exact nine names')\n    before_clock = _diag_owned(clock())\n    need(before_clock == {'engine_time_s':0.0,'lab_step':0}, 'Velocity binding zero native clock')\n    before_state = _diag_owned(state()) if state is not None else None\n    if before_state is not None:\n        need(all(v==0. for k in ('q','qd') for v in before_state[k].values()), 'Velocity binding zero q and qd')\n    expected = {n:C.binary32(model['joints'][n]['velocity']) for n in names}\n    def read():\n        need(list(robot.dof_names)==list(names), 'Velocity binding stable DOF order')\n        raw = array(robot.get_dof_max_velocities())\n        need(raw.ndim==2 and tuple(raw.shape)==(1,9), 'Velocity binding exact (1,9) shape')\n        return C.named_columns(names, model['movable'], raw[0])\n    with backend.use_backend('tensor' if repair else 'usd', raise_on_unsupported=True, raise_on_fallback=True):\n        actual = read();record['before_SI'] = actual\n        if actual != expected:\n            need(repair, 'USD source velocity readback differs')\n            robot.set_dof_max_velocities([[expected[n] for n in names]])\n            record['set_same_source_values'] = True\n        final = read();record['after_SI'] = final\n        need(final == expected, 'Actual tensor/source velocity readback differs')\n    after_state = _diag_owned(state()) if state is not None else None\n    after_clock = _diag_owned(clock())\n    record.update({'owner_clock_before':before_clock, 'owner_clock_after':after_clock,\n        'state_before':before_state, 'state_after':after_state})\n    need(before_clock == after_clock and before_state == after_state, 'Velocity binding changes no clock/q/qd/pose')\n    record['status'] = 'VERIFIED_SAME_ORIGINAL_SI_LIMITS'\n    return record\n\n\ndef _diag_attribute(prim, name):\n    try:\n        attr = prim.GetAttribute(name)\n        if not attr: return {'status':'UNKNOWN_NOT_AVAILABLE', 'authored':False, 'runtime_observed':False}\n        return {'status':'USD_ATTRIBUTE_READ', 'authored':bool(attr.HasAuthoredValueOpinion()),\n            'type':str(attr.GetTypeName()), 'value':_diag_owned(attr.Get()), 'runtime_observed':False}\n    except BaseException as exc: return {'status':'UNKNOWN_READ_ERROR', 'error':type(exc).__name__+': '+str(exc)[:500], 'runtime_observed':False}\n\n\ndef _contact_settings(stage, paths):\n    attrs = ('physxCollision:contactOffset','physxCollision:restOffset','physxRigidBody:maxDepenetrationVelocity',\n        'physxArticulation:solverPositionIterationCount','physxArticulation:solverVelocityIterationCount',\n        'physxScene:solverType','physxScene:minVelocityIterationCount','physxScene:maxVelocityIterationCount',\n        'physxScene:solveArticulationContactLast')\n    return {p:{a:_diag_attribute(stage.GetPrimAtPath(p),a) for a in attrs} for p in list(dict.fromkeys(paths))[:32]}\n\n\nclass _ContactProbe:\n    def __init__(self, ctx, interface, stage, expected_stage, clock, decode, enabled, setup):\n        self.ctx, self.interface, self.stage, self.expected_stage = ctx, interface, stage, expected_stage\n        self.clock, self.decode, self.enabled, self.setup = clock, decode, enabled, setup\n        self.closed = False\n        self.state_reader = None\n        self.last = {'status':'UNKNOWN_NOT_OBSERVED', 'setup':setup}\n    def sample(self, step):\n        self.last = {'status':'UNKNOWN_NOT_OBSERVED', 'owner_step':step,\n            'native_timestamp':'NOT_PROVIDED_BY_HEADER', 'setup':self.setup}\n        try:\n            need(not self.closed and self.enabled, 'Contact report unavailable or closed')\n            before = _diag_owned(self.clock())\n            pending=getattr(self.ctx,'_fault_pending',{})\n            observed=pending.get('current_state')\n            before_state={k:observed[k] for k in ('q','qd')} if observed is not None else None\n            need(before['lab_step']==step, 'Contact observation current owner step')\n            need(observed is not None and observed.get('clock')==before,'Contact owner clock matches poststep state')\n            attached = int(self.interface.get_attached_stage())\n            need(attached==self.expected_stage, 'Contact attached stage identity')\n            raw = self.interface.get_contact_report()\n            need(isinstance(raw,tuple) and len(raw) in (2,3), 'Contact report tuple2 or tuple3')\n            headers, data = raw[:2]\n            need(len(headers)<=64 and len(data)<=256 and (len(raw)==2 or len(raw[2])<=256), 'Contact report bounded vector overflow')\n            expanded=0\n            for header in headers:\n                offset,count=int(header.contact_data_offset),int(header.num_contact_data)\n                need(offset>=0 and count>=0 and offset+count<=len(data), 'Contact offset/count range')\n                expanded+=count\n                need(expanded<=256, 'Contact cumulative expanded contacts overflow')\n            owned=[];paths=[]\n            for h in headers:\n                need(int(h.stage_id)==attached, 'Contact header stage identity')\n                offset,count=int(h.contact_data_offset),int(h.num_contact_data)\n                need(offset>=0 and count>=0 and offset+count<=len(data), 'Contact offset/count range')\n                row={'event':str(h.type), 'stage_id':int(h.stage_id), 'offset':offset, 'count':count}\n                for key in ('actor0','actor1','collider0','collider1'):\n                    value=getattr(h,key);decoded=str(self.decode(value))\n                    need(len(decoded)<=2000 and decoded.startswith('/World/'), 'Contact decoded owned world path')\n                    row[key]=decoded;paths.append(decoded)\n                row['contacts']=[]\n                for index in range(offset,offset+count):\n                    p=data[index]\n                    item={'position':[float(x) for x in p.position], 'normal':[float(x) for x in p.normal],\n                        'impulse':[float(x) for x in p.impulse], 'separation':float(p.separation)}\n                    need(all(len(item[k])==3 for k in ('position','normal','impulse')) and\n                        all(math.isfinite(v) for k in ('position','normal','impulse') for v in item[k]) and\n                        math.isfinite(item['separation']), 'Finite contact primitive vectors')\n                    row['contacts'].append(item)\n                owned.append(row)\n            after=_diag_owned(self.clock())\n            after_state=_diag_owned(self.state_reader()) if callable(self.state_reader) else None\n            if before!=after or before_state is not None and after_state is not None and before_state!=after_state:\n                self.last['observer_changed_state']=True\n                raise ValueError('Contact getter changes no native clock/q/qd')\n            result={'status':'CURRENT_STEP_REPORT_COPIED', 'owner_step':step, 'owner_clock_before':before,\n                'owner_clock_after':after, 'native_timestamp':'NOT_PROVIDED_BY_HEADER', 'attached_stage_id':attached,\n                'tuple_arity':len(raw), 'headers':owned, 'reported_pairs':len(owned),\n                'friction_anchors_count':len(raw[2]) if len(raw)==3 else None,\n                'zero_pairs_mean':'NO_PAIRS_REPORTED_NOT_PROOF_OF_NO_PHYSICAL_CONTACT',\n                'settings':_contact_settings(self.stage,paths+['/World/Robot','/World/physicsScene','/World/Floor'])}\n            self.last=_diag_owned(result,budget=[8192])\n        except BaseException as exc:\n            self.last.update({'status':'UNKNOWN_OBSERVATION_ERROR', 'error':type(exc).__name__+': '+str(exc)[:1000]})\n            _diag_secondary(self.ctx,'contact_sample',exc)\n        finally:\n            if 'before' in locals():\n                try:\n                    final_clock=_diag_owned(self.clock())\n                    final_state=_diag_owned(self.state_reader()) if callable(self.state_reader) else None\n                    if before!=final_clock or before_state is not None and final_state is not None and before_state!=final_state:\n                        self.last.update({'status':'UNKNOWN_OBSERVER_STATE_CHANGED','observer_changed_state':True})\n                except BaseException as secondary:\n                    self.last['state_preservation_unverified']=True\n                    _diag_secondary(self.ctx,'contact_state_preservation',secondary)\n        return self.last\n    def close(self):\n        self.closed=True\n        return {'mode':'DIRECT_GETTER_NO_SUBSCRIPTION', 'closed':True, 'physics_operations':0}\n\n\ndef _contact_setup(ctx, stage, body_paths, schema, interface, expected_stage, clock, decode):\n    setup={'mode':'DIRECT_GETTER_NO_SUBSCRIPTION','threshold_requested':0.0,'bodies':[], 'enabled':False}\n    enabled=False\n    try:\n        need(callable(getattr(interface,'get_contact_report',None)) and callable(getattr(interface,'get_attached_stage',None)), 'Direct contact API unsupported')\n        for path in body_paths:\n            api=schema.PhysxContactReportAPI.Apply(stage.GetPrimAtPath(path))\n            maker=getattr(api,'CreateThresholdAttr',None)\n            method='CreateThresholdAttr'\n            if not callable(maker): maker=getattr(api,'CreatePhysxContactReportThresholdAttr',None);method='CreatePhysxContactReportThresholdAttr'\n            need(callable(maker), 'Contact report threshold API unsupported')\n            attr=maker()\n            need(str(attr.GetName())=='physxContactReport:threshold' and str(attr.GetTypeName())=='float','Exact report-only threshold attribute')\n            need(attr.Set(0.0) is True and float(attr.Get())==0., 'Report-only threshold zero readback')\n            setup['bodies'].append({'path':path,'method':method,'threshold':0.0,'report_only':True})\n        enabled=True;setup['enabled']=True\n    except BaseException as exc:\n        setup['status']='UNKNOWN_SETUP_ERROR';setup['error']=type(exc).__name__+': '+str(exc)[:1000]\n        _diag_secondary(ctx,'contact_setup',exc)\n    return _ContactProbe(ctx,interface,stage,expected_stage,clock,decode,enabled,setup)\n\n\ndef _decode_contact_path(tools, value):\n    if type(value) is int:\n        return tools.intToSdfPath(value)\n    if isinstance(value,(tuple,list)) and len(value)==2 and all(type(x) is int for x in value):\n        try: return tools.decodeSdfPath(value[0],value[1])\n        except TypeError: return tools.decodeSdfPath(value)\n    raise ValueError('UNKNOWN contact actor ID encoding')\n"
NATIVE_COLLECT = "def collect(ctx, app):\n    \"\"\"One collector; primary exceptions survive every diagnostic/finalization failure.\"\"\"\n    report = ledger(ctx)\n    budget = ctx.native_budget if hasattr(ctx, 'native_budget') else arm_watchdog(ctx)\n    primary = None\n    primary_tb = None\n    gate = False\n    try:\n        budget.check()\n        ctx.write(ctx.run/'output/report.partial.json', report)\n        _native(ctx, app, report, budget)\n    except GateFailure as exc:\n        primary, primary_tb, gate = exc, exc.__traceback__, True\n        mark(report, budget.phase, 'FAIL', str(exc), completed_steps=report['completed_steps'])\n        report['gate_failure'] = str(exc)\n        _save_first_fault(ctx, report, exc)\n        if hasattr(ctx, 'native_camera') and report['frames']:\n            try: report['render'] = ctx.native_camera.finish(len(report['frames']), purpose='render_smoke')\n            except BaseException as secondary: _diag_secondary(ctx,'camera_finish',secondary)\n        if hasattr(ctx, 'init_boundary'):\n            try: ctx.init_boundary.finish(report['completed_steps'])\n            except BaseException as secondary: _diag_secondary(ctx,'boundary_finish',secondary)\n    except BaseException as exc:\n        primary, primary_tb = exc, exc.__traceback__\n        mark(report, budget.phase, 'FAIL', type(exc).__name__+': '+str(exc), completed_steps=report['completed_steps'])\n        report['exception'] = traceback.format_exc()\n        _save_first_fault(ctx, report, exc)\n    finally:\n        if hasattr(ctx, '_contact_probe'):\n            try: report['contact_cleanup'] = _diag_final_copy(ctx,'contact_cleanup_copy',ctx._contact_probe.close())\n            except BaseException as secondary: _diag_secondary(ctx,'contact_close',secondary)\n        if hasattr(ctx, 'init_boundary'):\n            try:\n                errors = ctx.init_boundary.close()\n                report['init_cleanup_errors'] = _diag_final_copy(ctx,'init_cleanup_copy',errors)\n                if errors:\n                    if primary is None:\n                        primary = RuntimeError('INIT_CLEANUP_FAILED:'+str(errors))\n                        mark(report,budget.phase,'FAIL',str(primary))\n                        _save_first_fault(ctx,report,primary)\n                    else: _diag_secondary(ctx,'init_cleanup_errors',RuntimeError(str(errors)))\n            except BaseException as secondary:\n                if primary is None:\n                    primary, primary_tb = secondary, secondary.__traceback__\n                    mark(report,budget.phase,'FAIL','INIT_CLEANUP_EXCEPTION:'+str(secondary))\n                    _save_first_fault(ctx,report,primary)\n                else: _diag_secondary(ctx,'init_cleanup_exception',secondary)\n        report['elapsed_native_s'] = time.monotonic()-ctx.started_monotonic\n        report['native_deadline_monotonic'] = budget.end\n        report['diagnostic_secondary'] = _diag_final_copy(ctx,'secondary_final_copy',getattr(ctx,'_diag_secondary',[]))\n        if hasattr(ctx, '_contact_probe'): report['last_contact_observation'] = _diag_final_copy(ctx,'contact_final_copy',ctx._contact_probe.last)\n        if hasattr(ctx,'_velocity_audit'): report['velocity_limits'] = _diag_final_copy(ctx,'velocity_final_copy',ctx._velocity_audit)\n        try: ctx.write(ctx.run/'output/report.json', report)\n        except BaseException as secondary:\n            if primary is None: primary, primary_tb = secondary, secondary.__traceback__\n            else: _diag_secondary(ctx,'final_report_write',secondary)\n            report['diagnostic_secondary'] = _diag_owned(getattr(ctx,'_diag_secondary',[]))\n    if primary is not None and not gate:\n        raise primary.with_traceback(primary_tb)\n    return report\n"

NATIVE_BASE='src/simulation/mp18_isaac_128/native.py'
NATIVE_BASE_SHA='2ae9e7720ee7accf8fd611ab9223fbe17d7da6dc6e827011dd3b22725e4a3e7c'


CONSTRAINT_CONTACT_HELPERS = "def _constraint_order_cfg(PhysxCfg):\n    baseline,candidate=PhysxCfg(),PhysxCfg(solve_articulation_contact_last=True)\n    before,after=baseline.to_dict(),candidate.to_dict()\n    need(type(before) is dict and type(after) is dict and set(before)==set(after),'Same official PhysxCfg fields')\n    changed=[key for key in before if before[key]!=after[key]]\n    need(changed==['solve_articulation_contact_last'] and before[changed[0]] is False and after[changed[0]] is True,'Only official constraint order bool changes')\n    return candidate,{'changed_fields':changed,'default':False,'requested':True,'other_fields_equal':True,'field_count':len(before)}\n\n\ndef _constraint_order_readback(sim,stage,clock,state_reader=None):\n    before=_diag_owned(clock())\n    state_before=_diag_owned(state_reader()) if callable(state_reader) else None\n    attr=stage.GetPrimAtPath('/World/physicsScene').GetAttribute('physxScene:solveArticulationContactLast')\n    proof={'clock_before':before,'authored':bool(attr and attr.HasAuthoredValueOpinion()),\n        'attribute_type':str(attr.GetTypeName()) if attr else 'UNKNOWN',\n        'value':attr.Get() if attr else None,'resolved_config_value':sim.cfg.physics.solve_articulation_contact_last,\n        'root_layer':str(stage.GetRootLayer().identifier),'session_layer':str(stage.GetSessionLayer().identifier)}\n    after=_diag_owned(clock());state_after=_diag_owned(state_reader()) if callable(state_reader) else None\n    proof.update(clock_after=after,state_before=state_before,state_after=state_after)\n    need(before==after and before['engine_time_s']==0. and before['lab_step']==0 and state_before==state_after,'Constraint readback preserves zero clock/q/qd')\n    need(sim.stage==stage and proof['authored'] and proof['attribute_type']=='bool' and proof['value'] is True and proof['resolved_config_value'] is True,'Current official constraint-order scene True')\n    return proof\n\n\ndef _contact_stage_state(sim,stage,context,cache,lab_current,manager):\n    # All observed IDs are copied before the consumer classifies their meaning.\n    result={'status':'UNKNOWN_STAGE_PROOF','cache_id':None,'context_id':None,'device':str(sim.cfg.device),\n        'backend_device':None,'root_layer':str(stage.GetRootLayer().identifier),'session_layer':str(stage.GetSessionLayer().identifier)}\n    try:\n        cache_id=cache.GetId(stage)\n        result['cache_id']=int(cache_id.ToLongInt())\n        result['context_id']=int(context.get_stage_id())\n        result['backend_device']=str(manager.get_device())\n        lab,kit=lab_current(),context.get_stage()\n        result.update(sim_stage_same=sim.stage==stage,lab_stage_same=lab==stage,kit_stage_same=kit==stage,\n            manager_owner_same=manager._sim is sim,cache_dereference_same=cache.Find(cache_id)==stage,\n            context_registration_same=result['context_id']==result['cache_id'],\n            lab_layers_same=lab is not None and lab.GetRootLayer()==stage.GetRootLayer() and lab.GetSessionLayer()==stage.GetSessionLayer(),\n            kit_layers_same=kit is not None and kit.GetRootLayer()==stage.GetRootLayer() and kit.GetSessionLayer()==stage.GetSessionLayer())\n        result['status']='OWNED_IDS_OBSERVED_NOT_YET_ADMITTED'\n    except BaseException as exc:\n        result['error']=type(exc).__name__+': '+str(exc)[:1000]\n    return _diag_owned(result,budget=[256])\n\n\ndef _contact_stage_mode(proof,attached,expected):\n    need(type(proof) is dict and proof.get('status')=='OWNED_IDS_OBSERVED_NOT_YET_ADMITTED','Complete current contact stage proof')\n    need(type(expected) is int and expected>0 and proof.get('cache_id')==expected and proof.get('context_id')==expected,'Current registered contact stage IDs')\n    need(all(proof.get(k) is True for k in ('sim_stage_same','lab_stage_same','kit_stage_same','manager_owner_same','cache_dereference_same','context_registration_same','lab_layers_same','kit_layers_same')),'Owned Lab/Kit/cache current stage identity')\n    need(all(type(proof.get(k)) is str and 0<len(proof[k])<=2000 for k in ('root_layer','session_layer')),'Owned current stage layers')\n    cpu=proof.get('device')=='cpu' and proof.get('backend_device')=='cpu'\n    gpu=str(proof.get('device','')).startswith('cuda') and str(proof.get('backend_device','')).startswith('cuda')\n    if attached==0:\n        need(cpu,'Only proven CPU Kit implicit attachment has zero explicit interface ID')\n        return 'CPU_KIT_IMPLICIT_CURRENT_STAGE'\n    need(attached==expected and (cpu or gpu),'Exact explicit current contact stage identity')\n    return 'GPU_EXPLICIT_CURRENT_STAGE' if gpu else 'CPU_EXPLICIT_CURRENT_STAGE'\n"


def build_native(raw):
    nodes={n.name:n for n in _nodes(raw) if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    body=raw[_span(raw,nodes['_native'])[0]:_span(raw,nodes['_native'])[1]].decode()
    def change(old,new):
        nonlocal body
        need(body.count(old)==1,'Exact128 native integration replacement: '+old[:90]);body=body.replace(old,new)
    change('from isaaclab_physx.physics.physx_manager import PhysxManager','from isaaclab_physx.physics.physx_manager import PhysxManager\n    from isaaclab_physx.physics import PhysxCfg\n    from isaaclab.sim.utils.stage import get_current_stage')
    change("    sim = SimulationContext(SimulationCfg(dt=1/120, device='cpu', gravity=(0., 0., -9.81),", "    order_cfg,report['constraint_order'] = _constraint_order_cfg(PhysxCfg)\n    sim = SimulationContext(SimulationCfg(physics=order_cfg,dt=1/120, device='cpu', gravity=(0., 0., -9.81),")
    change("            lambda value:_decode_contact_path(PhysicsSchemaTools,value))", "            lambda value:_decode_contact_path(PhysicsSchemaTools,value))\n        ctx._contact_probe.stage_reader = lambda:_contact_stage_state(sim,stage,omni.usd.get_context(),UsdUtils.StageCache.Get(),get_current_stage,PhysxManager)")
    change("    budget.check()\n    sim.reset()", "    report['constraint_order']['before_reset'] = _constraint_order_readback(sim,stage,velocity_clock)\n    budget.check()\n    sim.reset()")
    change("    ctx._contact_probe.state_reader = contact_state_read", "    ctx._contact_probe.state_reader = contact_state_read\n    report['constraint_order']['after_reset'] = _constraint_order_readback(sim,stage,clock,contact_state_read)\n    ctx.write(out/'constraint-order.json',report['constraint_order'])")
    probe=raw[_span(raw,nodes['_ContactProbe'])[0]:_span(raw,nodes['_ContactProbe'])[1]].decode()
    def probechange(old,new):
        nonlocal probe
        need(probe.count(old)==1,'Exact128 contact probe replacement: '+old[:90]);probe=probe.replace(old,new)
    probechange('        self.state_reader = None','        self.state_reader = None\n        self.stage_reader = None')
    probechange("            attached = int(self.interface.get_attached_stage())\n            need(attached==self.expected_stage, 'Contact attached stage identity')", "            self.last['stage_provenance']={'expected_stage_id':self.expected_stage,'attached_stage_id':None,'header_stage_ids':[],'mode':'UNKNOWN'}\n            need(callable(self.stage_reader),'Current contact stage proof callback required')\n            stage_before=_diag_owned(self.stage_reader(),budget=[256])\n            self.last['stage_provenance']['current']=stage_before\n            attached = int(self.interface.get_attached_stage())\n            self.last['stage_provenance']['attached_stage_id']=attached\n            mode=_contact_stage_mode(stage_before,attached,self.expected_stage)\n            self.last['stage_provenance']['mode']=mode")
    probechange("            expanded=0", "            self.last['stage_provenance']['header_stage_ids']=[int(h.stage_id) for h in headers]\n            expanded=0")
    probechange("                need(int(h.stage_id)==attached, 'Contact header stage identity')", "                need(int(h.stage_id)==self.expected_stage, 'Contact header current registered stage identity')")
    probechange("                    row[key]=decoded;paths.append(decoded)", "                    need(bool(self.stage.GetPrimAtPath(decoded)),'Contact actor/collider exists on owned current stage')\n                    row[key]=decoded;paths.append(decoded)")
    probechange("            after=_diag_owned(self.clock())", "            stage_after=_diag_owned(self.stage_reader(),budget=[256])\n            self.last['stage_provenance']['after']=stage_after\n            need(stage_before==stage_after,'Contact getter preserves current owned stage')\n            after=_diag_owned(self.clock())")
    probechange("                'settings':_contact_settings", "                'stage_provenance':self.last['stage_provenance'],\n                'settings':_contact_settings")
    return _splice(raw,[('owned CPU/explicit contact stage provenance',nodes['_ContactProbe'],probe),
        ('official one-bool constraint order and current-stage consumer',nodes['_native'],CONSTRAINT_CONTACT_HELPERS+'\n\n'+body)])



def build():
    originals={}
    for name,expected in BASE.items():
        b=read(ROOT/'src/simulation/mp18_isaac_119'/name);need(digest(b)==expected,'Fixed119 original '+name);originals[name]=b
    historical=read(ROOT/CANDIDATE);need(digest(historical)==CANDIDATE_SHA,'Exact126 historical native base')
    base=read(ROOT/NATIVE_BASE);need(digest(base)==NATIVE_BASE_SHA,'Exact current immutable128 native base')
    native,native_delta=build_native(base)
    driver,dm=build_driver(originals['driver.py']);media,mm=build_media(originals['media.py'],digest(driver))
    result={'driver.py':driver,'contract.py':originals['contract.py'],'native.py':native,
            'config.json':originals['config.json'],'program.json':originals['program.json'],'media.py':media}
    manifest={'unit':129,'kind':'DERIVED_REVIEWED_RELEASE','legacy_envelope_unit':119,'originals':BASE,'candidate_sha256':CANDIDATE_SHA,
              'files':{n:{'sha256':digest(b),'bytes':len(b)} for n,b in result.items()},'driver_delta':dm,'media_delta':mm,
              'contract_config_program_byte_identical':True,'native_derived_from128':True,'native_base_sha256':NATIVE_BASE_SHA,'native_delta':native_delta,'driver_media_no_original_publisher_entry':True}
    return result,manifest


def generate(destination=DERIVED,out=OUT):
    need(destination.is_relative_to(ROOT) and out.is_relative_to(ROOT),'Owned generator destination')
    result,manifest=build();destination.mkdir(parents=True,exist_ok=True)
    for name,data in result.items():
        p=path_guard(destination/name)
        if p.exists():need(read(p)==data,'Existing derived file differs; no overwrite')
        else:exclusive(p,data)
    data=encode(manifest);p=out/'release-manifest.json'
    if p.exists():need(read(p)==data,'Existing release manifest differs')
    else:exclusive(p,data)
    return manifest


def verify_release(destination=DERIVED,out=OUT):
    expected,manifest=build();mraw=read(out/'release-manifest.json')
    need(mraw==encode(manifest),'Current deterministic release manifest')
    rows=[(str(out/'release-manifest.json'),mraw)]
    for name,b in expected.items():
        p=destination/name;actual=read(p);need(actual==b,'Current derived release '+name);rows.append((str(p),actual))
    for name in BASE:rows.append((str(ROOT/'src/simulation/mp18_isaac_119'/name),read(ROOT/'src/simulation/mp18_isaac_119'/name)))
    rows.append((str(ROOT/CANDIDATE),read(ROOT/CANDIDATE)))
    rows.append((str(ROOT/NATIVE_BASE),read(ROOT/NATIVE_BASE)))
    return expected,manifest,rows


def review_capture(out=OUT):
    p=out/'review/source-freeze.json';fraw=read(p);f=parse(fraw)
    need(type(f.get('unit')) is int and f['unit']==129 and type(f['files']) is dict,'Typed129 source freeze')
    required={'src/simulation/mp18_video_run_129/'+n for n in ('release.py','runner.py','test_runner.py')}
    required|={'src/simulation/mp18_isaac_129/'+n for n in ('driver.py','contract.py','native.py','config.json','program.json','media.py')}
    required|={PLAN,'outputs/mp18-video-run-129/release-manifest.json'}
    need(required<=set(f['files']),'Complete129 reviewed package')
    rows=[(str(p),fraw)]
    for rel,pin in f['files'].items():
        q=PurePosixPath(rel);need(not q.is_absolute() and q.as_posix()==rel and not any(x in ('.','..') for x in q.parts) and ':' not in rel and '\\' not in rel,'Canonical freeze path')
        pp=ROOT/rel;b=read(pp);need(digest(b)==pin['sha256'] and len(b)==pin['bytes'],'Current reviewed129 file');rows.append((str(pp),b))
    need(digest(read(ROOT/PLAN))==PLAN_SHA,'Reviewed129 plan')
    for who in ('main',):
        pp=out/('review/'+who+'-L4-final.json');b=read(pp);r=parse(b)
        need(type(r.get('unit')) is int and r['unit']==129 and r['phase']=='L4' and type(r['round']) is int and r['round'] in (1,2) and
             r['non_author'] is True and r['verdict']=='PASS' and type(r['unmet']) is int and r['unmet']==0 and
             type(r['unresolved_count']) is int and r['unresolved_count']==0 and r['source_freeze_sha256']==digest(fraw),'Final typed129 independent reviews')
        rows.append((str(pp),b))
    return digest(fraw),rows


def thin_bootstrap(driver_raw,contract_raw,args):
    need(digest(contract_raw)==BASE['contract.py'],'Captured contract AST bytes')
    need(driver_raw==build()[0]['driver.py'] and digest(driver_raw)==args['driver_sha256'],'Captured deterministic driver AST bytes')
    selected=[]
    for data,names in ((driver_raw,('need','_safe_name','_unpack_payload','lease_end','_bootstrap')),(contract_raw,('parse',))):
        nodes={n.name:n for n in _nodes(data) if isinstance(n,ast.FunctionDef)}
        for name in names:
            node=nodes[name];need(not node.decorator_list,'Closed bootstrap AST span')
            a,b=_span(data,node);selected.append(data[a:b].decode())
    code=('import os,sys,json,hashlib,io,zipfile,types,re,time,threading,math\nfrom pathlib import Path,PurePosixPath\n'+
          '\n\n'.join(selected)+'\na='+repr(args)+'\n_bootstrap(a)\n')
    ast.parse(code);encoded=base64.b64encode(zlib.compress(code.encode(),9)).decode()
    literal="import base64,zlib;exec(zlib.decompress(base64.b64decode('"+encoded+"')))"
    need('"' not in literal and len(literal)<7000,'Original bounded thin bootstrap')
    return literal


if __name__=='__main__':generate()
