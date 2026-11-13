"""119 closed local/remote lifetime owner. Only CLI run can start SSH; no hardware I/O."""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import inspect
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys
import threading
import time
import types
import uuid
import zipfile
import zlib

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT/'outputs/mp18-video-run-127'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_module(name, raw, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _checked_contract_bytes():
    value = (HERE/'contract.py').read_bytes()
    need(hashlib.sha256(value).hexdigest() == '9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf', 'Fixed contract raw before execution')
    return value

C = load_module('contract127', _checked_contract_bytes(), HERE/'contract.py')
parse, sha, read = C.parse, C.sha, lambda p: C.parse(Path(p).read_bytes())
_ACTIVE_OUT = None


_LOCAL_GUARD = None
_LOCAL_INPUT = None

def bind_local_authority(guard, resolver):
    need(callable(guard) and callable(resolver), 'Explicit local127 authority callbacks')
    global _LOCAL_GUARD, _LOCAL_INPUT
    _LOCAL_GUARD, _LOCAL_INPUT = guard, resolver

def _local_guard():
    need(callable(_LOCAL_GUARD), 'Local127 current authority is not bound')
    _LOCAL_GUARD()

def _local_write_guard(path):
    _local_guard()
    p = Path(path)
    need(p.is_absolute() and OUT.is_relative_to(ROOT) and p.is_relative_to(OUT), 'Original127 local output role')
    for item in (p, *p.parents):
        need(not item.is_symlink() and not item.is_junction(), 'Local write reparse role')
    need(ROOT.resolve() == ROOT and p.resolve().is_relative_to(OUT), 'Original127 local output anchor')
    return p

def _payload_bytes(path):
    need(callable(_LOCAL_INPUT), 'Local127 immutable payload resolver is not bound')
    value = _LOCAL_INPUT(Path(path))
    need(type(value) is bytes, 'Immutable input bytes')
    return value

def write(path, value):
    p = Path(path)
    if _ACTIVE_OUT is None: _local_write_guard(p)
    if _ACTIVE_OUT is not None:
        need(p.resolve().is_relative_to(_ACTIVE_OUT.resolve()), 'Write outside owned output')
    else:
        need(p.resolve().is_relative_to(OUT.resolve()), 'Local evidence write outside unit119')
    p.parent.mkdir(parents=True, exist_ok=True)
    if _ACTIVE_OUT is None: _local_write_guard(p)
    p.write_text(json.dumps(value, allow_nan=False, separators=(',', ':'))+'\n', encoding='utf-8')


def _safe_name(name):
    need(type(name) is str and name and not any(x in name for x in ('\\', ':', '\0', '\n', '\r', '\t')), 'Unsafe archive name')
    p = PurePosixPath(name)
    need(not p.is_absolute() and p.as_posix() == name and not any(x in ('.', '..') for x in p.parts), 'Archive traversal')
    need(all(not x.endswith((' ', '.')) for x in p.parts), 'Ambiguous Windows component')
    need(all(not re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', x) for x in p.parts), 'Reserved Windows component')
    return name


def _unpack_payload(raw, run, expected_job):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        need(len(infos) == len({i.filename.casefold() for i in infos}), 'Duplicate archive name')
        need(sum(i.file_size for i in infos) <= 512*1024*1024, 'Bounded archive size')
        for i in infos:
            _safe_name(i.filename)
            need(not i.is_dir() and (i.external_attr >> 16) & 0o170000 != 0o120000, 'Archive symlink/directory rejected')
        job_raw = archive.read('job.json')
        need(hashlib.sha256(job_raw).hexdigest() == expected_job, 'Actual job hash')
        job = parse(job_raw)
        need(job['unit'] == 119 and job['hardware_approved'] is False and type(job['inputs']) is dict, 'Closed payload job')
        need({i.filename for i in infos} == {'job.json'} | {'input/'+n for n in job['inputs']}, 'Exact payload inventory')
        for name in job['inputs']:
            _safe_name(name)
            need(name.startswith(('source/', 'model/', 'ref/')) or name == 'approval.json', 'Closed payload namespace')
        run = Path(run)
        for p in (run, *run.parents):
            need(not p.is_symlink() and not p.is_junction(), 'Remote reparse path rejected')
        need(not run.exists(), 'Run already exists')
        # Validate all content before the first payload write.
        for name, expected in job['inputs'].items():
            need(hashlib.sha256(archive.read('input/'+name)).hexdigest() == expected, 'Payload member hash')
        run.mkdir(parents=True, exist_ok=False)
        for i in infos:
            p = run/i.filename
            need(p.resolve().is_relative_to(run.resolve()), 'Payload escaped run')
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as stream:
                stream.write(archive.read(i))
    return job


def lease_end(remote_ready, local_remaining, handshake=20):
    need(all(type(v) in (float, int) and math.isfinite(v) for v in (remote_ready, local_remaining, handshake)), 'Finite lease')
    need(handshake == 20 and local_remaining > handshake+602, 'Lease headroom')
    return remote_ready+local_remaining-handshake


def _bootstrap(args):
    ready_time = time.monotonic()
    lock = threading.Lock()
    state = {'end': ready_time+20., 'stop': False}
    def watch():
        while True:
            with lock:
                if state['stop']:
                    return
                remaining = state['end']-time.monotonic()
                if remaining <= 0:
                    os._exit(124)
            time.sleep(min(.02, remaining))
    threading.Thread(target=watch, daemon=True).start()
    identity = {k: args[k] for k in ('nonce', 'run_id', 'driver_sha256', 'bundle_sha256', 'bundle_bytes', 'job_sha256')}
    print(json.dumps(dict(identity, kind='READY', remote_ready=ready_time)), flush=True)
    line = sys.stdin.buffer.readline(4097)
    need(len(line) <= 4096 and line.endswith(b'\n'), 'Closed GO line')
    go = parse(line)
    need(go == dict(identity, kind='GO'), 'GO identity')
    with lock:
        need(time.monotonic() < ready_time+20., 'Late GO')
        # One monitor reads the new absolute end every iteration; no dead-man gap.
        state['end'] = lease_end(ready_time, args['remaining'])
    need(0 < args['bundle_bytes'] <= 128*1024*1024, 'Bounded bundle')
    data = bytearray()
    while len(data) < args['bundle_bytes']:
        block = sys.stdin.buffer.read(min(1024*1024, args['bundle_bytes']-len(data)))
        need(bool(block), 'Truncated payload stream')
        data.extend(block)
    need(sys.stdin.buffer.read(1) == b'', 'Trailing payload stream')
    need(hashlib.sha256(data).hexdigest() == args['bundle_sha256'], 'Bundle hash')
    need(re.fullmatch('[0-9a-f]{32}', args['run_id']) and re.fullmatch('[0-9a-f]{32}', args['nonce']), 'Closed run identity')
    need(re.fullmatch('[A-Za-z]:/[A-Za-z0-9_/-]+', args['remote_root']) and args['remote_root'].endswith('/robot-arm-lab/119/runs'), 'Closed remote root')
    run = Path(args['remote_root'])/args['run_id']
    job = _unpack_payload(bytes(data), run, args['job_sha256'])
    need(job['run_id'] == args['run_id'] and job['nonce'] == args['nonce'], 'Payload identity')
    source = run/'input/source/driver.py'
    raw = source.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == args['driver_sha256'], 'Execution source hash')
    mod = types.ModuleType('remote_owner119')
    mod.__file__ = str(source)
    sys.modules[mod.__name__] = mod
    exec(compile(raw, str(source), 'exec'), mod.__dict__)
    archive = mod.remote_supervise(run, state['end'], args['job_sha256'])
    size = archive.stat().st_size
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    header = {'kind': 'RESULT', 'run_id': args['run_id'], 'nonce': args['nonce'], 'bytes': size, 'sha256': digest.hexdigest()}
    sys.stdout.buffer.write(json.dumps(header).encode()+b'\n')
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            sys.stdout.buffer.write(block)
    sys.stdout.buffer.flush()
    with lock:
        need(time.monotonic() < state['end'], 'Result exceeded remote lease')
        state['stop'] = True


def bootstrap_code(args):
    raise ValueError('Retired inspect bootstrap; use captured127 AST builder')


def _context(run, expected_job_sha256):
    run = Path(run)
    need(type(expected_job_sha256) is str and re.fullmatch('[0-9a-f]{64}', expected_job_sha256), 'Mandatory original expected job hash')
    job_raw = (run/'job.json').read_bytes()
    need(hashlib.sha256(job_raw).hexdigest() == expected_job_sha256, 'Original expected job hash before context inputs')
    job = parse(job_raw)
    need(job['unit'] == 119 and job['hardware_approved'] is False and job['run_id'] == run.name, 'Native job identity')
    data = {}
    for name, expected in job['inputs'].items():
        p = C.path_in(run/'input', name)
        raw = p.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == expected, 'Native input hash: '+name)
        data[name] = raw
    cfg = parse(data['source/config.json'])
    need(cfg['unit'] == 119 and cfg['hardware_approved'] is False, 'Native config scope')
    model = C.verify_inputs(run/'input/model', cfg)
    approval = parse(data['approval.json'])
    caps = C.effective_caps(cfg, approval)
    cfg = dict(cfg, program=parse(data['source/program.json']), effective_caps=caps, approval=approval)
    return types.SimpleNamespace(run=run, job=job, job_hash=hashlib.sha256(job_raw).hexdigest(), data=data, cfg=cfg,
                                 contract=C, model=model, need=need, read=read, write=write, sha=sha)


def native_main(run, expected_job_sha256):
    global _ACTIVE_OUT
    ctx = _context(run, expected_job_sha256)
    _ACTIVE_OUT = ctx.run/'output'
    _ACTIVE_OUT.mkdir(parents=True, exist_ok=True)
    owner = read(_ACTIVE_OUT/'owner.json')
    need(owner['run_id'] == ctx.run.name and owner['job_sha256'] == ctx.job_hash and
         owner['parent_pid'] == os.getppid() and owner['native_deadline_monotonic'] <= owner['remote_deadline_monotonic']-600 and
         time.monotonic() < owner['native_deadline_monotonic'], 'Owned native deadline')
    ctx.deadline = ctx.native_deadline_monotonic = owner['native_deadline_monotonic']
    ctx.started_monotonic = time.monotonic()
    ctx.owner = owner
    sys.modules['driver'] = sys.modules[__name__]
    # normalize_tool has only this legacy helper import; new native readback owns validation.
    sys.modules['validate'] = types.SimpleNamespace(near=C.near)
    ctx.scene_modules = {name: load_module(name+'119', ctx.data['ref/'+name+'.py'], ctx.run/'input/ref'/(name+'.py'))
                         for name in ('sdk', 'capture', 'init_boundary', 'root_binding')}
    native = load_module('native119', ctx.data['source/native.py'], ctx.run/'input/source/native.py')
    # B owns one phase watchdog around the entire pinned SDK lifecycle, including startup.
    return native.run(ctx)


def remote_supervise(run, deadline, expected_job_sha256):
    global _ACTIVE_OUT
    ctx = _context(run, expected_job_sha256)
    out = ctx.run/'output'
    out.mkdir(exist_ok=True)
    _ACTIVE_OUT = out
    remaining = deadline-time.monotonic()
    need(remaining > 602, 'No recovery headroom before SDK')
    limit = min(1800., remaining-602.)
    helper = load_module('winjob119', ctx.data['ref/winjob.py'], ctx.run/'input/ref/winjob.py')
    exe = Path(ctx.cfg['sdk']['isaac_root'])/'kit/python/python.exe'
    source = ctx.run/'input/source/driver.py'
    expected_driver = ctx.job['inputs']['source/driver.py']
    need(hashlib.sha256(ctx.data['source/driver.py']).hexdigest() == expected_driver, 'Captured parent driver pin')
    code = ("import pathlib,hashlib,types,sys; p=pathlib.Path("+repr(str(source))+"); b=p.read_bytes(); "
            "assert hashlib.sha256(b).hexdigest()=="+repr(expected_driver)+"; "
            "m=types.ModuleType('worker127');m.__file__=str(p);sys.modules[m.__name__]=m;"
            "exec(compile(b,str(p),'exec'),m.__dict__);raise SystemExit(m.native_main(p.parents[2],"+repr(expected_job_sha256)+"))")
    write(out/'owner.json', {'unit': 119, 'run_id': ctx.run.name, 'job_sha256': ctx.job_hash,
          'parent_pid': os.getpid(), 'remote_deadline_monotonic': deadline,
          'native_deadline_monotonic': time.monotonic()+limit-2})
    record = helper.run([str(exe), '-I', '-B', '-c', code], out, limit, cleanup_s=2)
    write(out/'process.json', dict(record, parent_pid=os.getpid(), remote_deadline_monotonic=deadline,
                                   job_sha256=ctx.job_hash, run_id=ctx.run.name))
    need(record['raw_complete'] and record['terminal'] and record['child_state'] == 'REAPED' and
         record['job_active_after'] == 0, 'Actual SDK child reaped before export')
    need(deadline-time.monotonic() > 5, 'Archive headroom')
    # Parent ownership, not SDK success: retain authentic partial frames even after a hard timeout.
    recovery = {'unit': 119, 'run_id': ctx.run.name, 'job_sha256': ctx.job_hash,
                'actual_child_pid': record['child_pid'], 'files_sha256': {}}
    for p in sorted(out.rglob('*')):
        if p.is_file():
            name = p.relative_to(out).as_posix()
            C.relative(name)
            need(not p.is_symlink() and not p.is_junction(), 'Recovery reparse rejected')
            recovery['files_sha256'][name] = sha(p)
    write(out/'recovery-seal.json', recovery)
    archive = ctx.run/'records.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():
                relative = p.relative_to(out).as_posix()
                C.relative(relative)
                need(not p.is_symlink() and not p.is_junction(), 'No result reparse file')
                z.write(p, relative)
    need(time.monotonic() < deadline, 'Archive within original lease')
    return archive


def prepare():
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


def _review_gate():
    freeze_path = OUT/'review/source-freeze.json'
    freeze_raw = freeze_path.read_bytes()
    freeze = parse(freeze_raw)
    need(type(freeze.get('unit')) is int and freeze['unit'] == 127, 'Typed127 source freeze')
    required = {'src/simulation/mp18_video_run_127/'+n for n in ('release.py','runner.py','test_runner.py')}
    required |= {'src/simulation/mp18_isaac_127/'+n for n in ('driver.py','contract.py','native.py','config.json','program.json','media.py')}
    need(type(freeze['files']) is dict and required <= set(freeze['files']), 'Complete127 source release')
    for relative, item in freeze['files'].items():
        p = C.path_in(ROOT, relative)
        raw = p.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == item['sha256'] and len(raw) == item['bytes'], 'Current127 source drift')
    for name in ('main',):
        report = read(OUT/('review/'+name+'-L4-final.json'))
        need(type(report.get('unit')) is int and report['unit'] == 127 and report['phase'] == 'L4' and
             type(report['round']) is int and report['round'] in (1,2) and report['non_author'] is True and
             report['verdict'] == 'PASS' and type(report['unmet']) is int and report['unmet'] == 0 and
             type(report['unresolved_count']) is int and report['unresolved_count'] == 0 and
             report['source_freeze_sha256'] == hashlib.sha256(freeze_raw).hexdigest(), 'Final typed127 independent source authority')


def verify_prepared(run, record, cfg):
    job = read(run/'job.json')
    expected = {'source/'+name: sha(HERE/name) for name in ('driver.py', 'contract.py', 'native.py', 'config.json', 'program.json')}
    expected.update({'model/'+name: item['sha256'] for name, item in cfg['model_pins'].items()})
    expected.update({'ref/'+name: item['sha256'] for name, item in cfg['refs'].items()})
    expected['approval.json'] = sha(OUT/'user-decision.json')
    need(job['inputs'] == expected and job['unit'] == 119 and job['purpose'] == 'v4_validation_video' and job['hardware_approved'] is False and
         job['run_id'] == record['run_id'] == run.name and job['nonce'] == record['nonce'] and
         sha(run/'job.json') == record['job_sha256'] and record['driver_sha256'] == expected['source/driver.py'],
         'Prepared payload must bind the actually reviewed source/model/decision')
    C.effective_caps(cfg, read(OUT/'user-decision.json'))


def verified_payload(run, record):
    """Recheck current authority and every original byte before loading any executable reference."""
    _review_gate()
    cfg = read(HERE/'config.json')
    verify_prepared(run, record, cfg)
    need(sha(run/'bundle.zip') == record['bundle_sha256'] and
         (run/'bundle.zip').stat().st_size == record['bundle_bytes'] <= 128*1024*1024, 'Original consumed bundle hash/size')
    raw_job = (run/'job.json').read_bytes()
    need(hashlib.sha256(raw_job).hexdigest() == record['job_sha256'], 'Original consumed job hash')
    job = parse(raw_job)
    with zipfile.ZipFile(run/'bundle.zip') as z:
        infos = z.infolist()
        need(len(infos) == len({i.filename.casefold() for i in infos}) and
             {i.filename for i in infos} == {'job.json'} | {'input/'+n for n in job['inputs']} and
             sum(i.file_size for i in infos) <= 512*1024*1024, 'Exact consumed payload inventory')
        for i in infos:
            _safe_name(i.filename)
            need(not i.is_dir() and (i.external_attr >> 16) & 0o170000 != 0o120000, 'Consumed payload reparse rejected')
        need(z.read('job.json') == raw_job, 'Archived original job bytes')
        data = {}
        for name, expected in job['inputs'].items():
            raw = z.read('input/'+name)
            need(hashlib.sha256(raw).hexdigest() == expected, 'Original consumed member hash: '+name)
            data[name] = raw
    return job, data, cfg


def verify_native_result(run, record, destination):
    """Read-only original-result consumer; never opens SSH or initializes SDK."""
    job, data, cfg = verified_payload(run, record)
    child = read(destination/'process.json')
    need(child['run_id'] == record['run_id'] and child['job_sha256'] == record['job_sha256'] and child['raw_complete'] and
         child['terminal'] and child['child_state'] == 'REAPED' and child['job_active_after'] == 0 and
         type(child['child_pid']) is int and child['child_pid'] > 0, 'Actual SDK lifetime identity')
    recovery = read(destination/'recovery-seal.json')
    need(recovery['unit'] == 119 and recovery['run_id'] == record['run_id'] and
         recovery['job_sha256'] == record['job_sha256'] and recovery['actual_child_pid'] == child['child_pid'], 'Recovery owner identity')
    seal = recovery['files_sha256']
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} - {'recovery-seal.json'}
    need(type(seal) is dict and set(seal) == actual and bool(seal), 'Complete recovery inventory')
    for name, expected in seal.items():
        need(sha(C.path_in(destination, name)) == expected, 'Actual native artifact seal')
    terminal = read(destination/'terminal.json') if 'terminal.json' in seal else None
    if terminal is not None:
        need(terminal['pid'] == child['child_pid'] and terminal['run_id'] == record['run_id'] and
             terminal['job_sha256'] == record['job_sha256'], 'Actual SDK lifetime identity')
    ctx = types.SimpleNamespace(cfg=cfg, data=data, run=run, job=job, job_hash=record['job_sha256'])
    complete = terminal is not None and terminal['status'] == 'CLOSED' and terminal['code'] == 0
    if complete:
        native_seal = terminal.get('files_sha256')
        need(type(native_seal) is dict and 'report.json' in native_seal and bool(native_seal), 'Complete native artifact seal')
        for name, expected in native_seal.items():
            need(name in seal and seal[name] == expected, 'Closed SDK seal matches actual recovered bytes')
        sys.modules['driver'] = sys.modules[__name__]
        sdk = load_module('verified_sdk119', data['ref/sdk.py'], run/'input/ref/sdk.py')
        sdk.verify_records(ctx, destination, terminal)
    else:
        need(child['actual_child_exit_code'] != 0 or child['timed_out'] or
             terminal is not None and terminal['status'] == 'FAILED' and terminal['code'] != 0, 'Incomplete diagnostic requires actual failed lifetime')
    report_name = 'report.json' if 'report.json' in seal else 'report.partial.json'
    report = read(destination/report_name)
    need(report['pid'] == child['child_pid'] and report['run_id'] == record['run_id'] and
         report['job_sha256'] == record['job_sha256'], 'Native report direct PID/job identity')
    need([p['name'] for p in report['phases']] == ['import', 'hold', 'small', 'large'], 'Exact phase ledger')
    need(all(p['status'] in ('PASS', 'FAIL', 'NOT_RUN') for p in report['phases']), 'Typed native phases')
    allowed = True
    for p in report['phases']:
        need(allowed or p['status'] == 'NOT_RUN', 'No later phase after failed gate')
        if p['status'] != 'PASS':
            allowed = False
    phases = report['phases']
    if not complete:
        # Never promote an interrupted or failed lifecycle to accepted motion.
        if not any(p['status'] == 'FAIL' for p in phases):
            failed_index = next((i for i,p in enumerate(phases) if p['status'] == 'NOT_RUN'), len(phases)-1)
            phases = [dict(p) for p in phases]
            phases[failed_index] = dict(phases[failed_index], status='FAIL', reason='INCOMPLETE_SDK_LIFETIME')
            for i in range(failed_index+1, len(phases)):
                phases[i] = dict(phases[i], status='NOT_RUN', reason='PRECEDING_GATE')
        if any(n.startswith('frames/frame-') and n.endswith('.png') for n in seal):
            verify_partial_sdk(ctx, destination, child)
    passed = complete and all(p['status'] == 'PASS' for p in phases) and child['actual_child_exit_code'] == 0 and not child['timed_out']
    write(OUT/'native-result.json', {'unit': 119, 'run_id': record['run_id'], 'phases': phases,
          'status': 'PASS' if passed else 'FAIL', 'hardware_approved': False, 'retrieved': str(destination),
          'SDK_reaped': True, 'remote_attempts': 1, 'original_report': report_name,
          'capture_provenance': 'SDK_CLOSED_SEAL' if complete else 'REAPED_PARENT_RECOVERY_SEAL_PARTIAL'})
    return 0 if passed else 2


def verify_partial_sdk(ctx, folder, child):
    """Partial diagnostics only: verify preapp evidence; never claim postcheck/module stability."""
    sys.modules['driver'] = sys.modules[__name__]
    sdk = load_module('partial_sdk119', ctx.data['ref/sdk.py'], ctx.run/'input/ref/sdk.py')
    kernel, policy = sdk.reference(ctx, 'kernel.py'), sdk.reference(ctx, 'policy.py')
    observed, provider = read(folder/'sdk.json'), read(folder/'providers.json')
    cfg = ctx.cfg['sdk']
    need(observed['pid'] == provider['pid'] == child['child_pid'] and observed['job_sha256'] == provider['job_sha256'] == ctx.job_hash and
         provider['run_id'] == ctx.job['run_id'], 'Partial actual SDK/provider PID/job')
    need(observed['version'] == cfg['isaac_version'] and kernel.owned_origin(observed['isaacsim_origin'], cfg['isaac_root']) and
         observed['bootstrap_sha256'] == {n:v['sha256'] for n,v in cfg['sdk_files'].items()}, 'Partial pinned SDK')
    kernel.check_numeric(read(folder/'numeric-before.json'), cfg, need)
    need(provider['before'] == read(folder/'binding-before.json'), 'Partial preapp binding identity')
    policy.require_observation(provider['observation'], cfg)


def run_remote():
    raise ValueError('Retired old entry; use reviewed unit127 runner')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('role', choices=('prepare', 'run', 'consume'))
    selected = parser.parse_args().role
    if selected == 'prepare':
        print(json.dumps(prepare()), flush=True)
    elif selected == 'run':
        raise SystemExit(run_remote())
    else:
        record = read(OUT/'prepared.json')
        run = OUT/'runs'/record['run_id']
        raise SystemExit(verify_native_result(run, record, run/'retrieved'))
