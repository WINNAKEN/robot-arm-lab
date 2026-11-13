"""Unit127 deterministic release from immutable reviewed originals. stdlib only."""
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
OUT=ROOT/'outputs/mp18-video-run-127'
DERIVED=ROOT/'src/simulation/mp18_isaac_127'
PLAN='docs/design/127-v4-lifetime-integration-and-video.md'
PLAN_SHA='f54c404137f4cb13e35211cbf643694bdff346845b923d1dbfabb8a07b288b5c'
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
'''

TYPED_GATE='''def _review_gate():
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
            "m=types.ModuleType('worker127');m.__file__=str(p);sys.modules[m.__name__]=m;"
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

C = load_module('contract127', _checked_contract_bytes(), HERE/'contract.py')''' % BASE['contract.py']
    changes=[('OUT127',assignment('OUT'),"OUT = ROOT/'outputs/mp18-video-run-127'"),
             ('checked contract loader',assignment('C'),craw),('local current callbacks',named['write'],LOCAL_HELPERS+'\n'+write_raw),
             ('typed127 gate',named['_review_gate'],TYPED_GATE.rstrip()),('same job raw parse/hash',named['_context'],context),('immutable prepare',named['prepare'],PREPARE.rstrip()),
             ('checked SDK child loader and original job authority',named['remote_supervise'],remote),
             ('mandatory native original job authority',named['native_main'],native_entry),
             ('bootstrap original job authority forwarding',named['_bootstrap'],bootstrap),
             ('retired inspect bootstrap',named['bootstrap_code'],"def bootstrap_code(args):\n    raise ValueError('Retired inspect bootstrap; use captured127 AST builder')"),
             ('retired old run_remote',named['run_remote'],"def run_remote():\n    raise ValueError('Retired old entry; use reviewed unit127 runner')")]
    # Keep original imports harmless, including inspect; no getsource call remains executable.
    return _splice(raw,changes)


def build_media(raw,driver_sha):
    nodes=_nodes(raw);named={n.name:n for n in nodes if isinstance(n,ast.FunctionDef)}
    loader=nodes[17:21] # Assert actual AST ownership rather than relying on this slice alone.
    start=next(n for n in nodes if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='s' for t in n.targets))
    end=next(n for n in nodes if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='s.loader.exec_module')
    a,b=_span(raw,start)[0],_span(raw,end)[1]
    replacement=('import hashlib, types\n'
        'def _load_checked_driver127():\n'
        '    value = (HERE/\'driver.py\').read_bytes()\n'
        '    if hashlib.sha256(value).hexdigest() != '+repr(driver_sha)+': raise ValueError(\'Derived driver pin before media execution\')\n'
        '    module = types.ModuleType(\'media_driver127\'); module.__file__ = str(HERE/\'driver.py\')\n'
        '    sys.modules[module.__name__] = module\n'
        '    exec(compile(value,module.__file__,\'exec\'),module.__dict__)\n'
        '    return module\n'
        'D = _load_checked_driver127()')
    # Replace the contiguous original loader once, then reparse for the remaining AST spans.
    first=raw[:a]+replacement.encode()+raw[b:];nodes=_nodes(first);named={n.name:n for n in nodes if isinstance(n,ast.FunctionDef)}
    enc=first[_span(first,named['encode'])[0]:_span(first,named['encode'])[1]].decode()
    enc=enc.replace('robot-arm-v4-119.mp4','robot-arm-v4-127.mp4').replace("{'unit': 119", "{'unit': 127")
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
    changes=[('video127 labels, MP4-only metadata and current local write authority',named['encode'],enc)]
    for n in nodes:
        if isinstance(n,ast.FunctionDef) and n.name in ('self_test','owned','inventory','publisher_inputs','publish'):
            changes.append(('retired '+n.name,n,"def "+n.name+('():' if n.name!='publish' else '(preflight=False):')+"\n    raise ValueError('Legacy Git/publisher/self-test retired in127')"))
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('OWNED','PLAN','HEADER') for t in n.targets):
            changes.append(('retired publisher metadata',n,'# Retired original publisher metadata'))
        if isinstance(n,ast.If) and ast.unparse(n.test)=="__name__ == '__main__'":
            changes.append(('media CLI encode only',n,"if __name__ == '__main__':\n    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('encode',));parser.parse_args();print(json.dumps(encode(),ensure_ascii=False))"))
    result,meta=_splice(first,changes);meta['checked_loader_origin_span']={'start_byte':a,'end_byte':b,'sha256':digest(raw[a:b])}
    return result,meta


def build():
    originals={}
    for name,expected in BASE.items():
        b=read(ROOT/'src/simulation/mp18_isaac_119'/name);need(digest(b)==expected,'Fixed119 original '+name);originals[name]=b
    native=read(ROOT/CANDIDATE);need(digest(native)==CANDIDATE_SHA,'Exact126 native candidate')
    driver,dm=build_driver(originals['driver.py']);media,mm=build_media(originals['media.py'],digest(driver))
    result={'driver.py':driver,'contract.py':originals['contract.py'],'native.py':native,
            'config.json':originals['config.json'],'program.json':originals['program.json'],'media.py':media}
    manifest={'unit':127,'kind':'DERIVED_REVIEWED_RELEASE','legacy_envelope_unit':119,'originals':BASE,'candidate_sha256':CANDIDATE_SHA,
              'files':{n:{'sha256':digest(b),'bytes':len(b)} for n,b in result.items()},'driver_delta':dm,'media_delta':mm,
              'contract_config_program_byte_identical':True,'native_exact126_candidate':True,'driver_media_no_original_publisher_entry':True}
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
    return expected,manifest,rows


def review_capture(out=OUT):
    p=out/'review/source-freeze.json';fraw=read(p);f=parse(fraw)
    need(type(f.get('unit')) is int and f['unit']==127 and type(f['files']) is dict,'Typed127 source freeze')
    required={'src/simulation/mp18_video_run_127/'+n for n in ('release.py','runner.py','test_runner.py')}
    required|={'src/simulation/mp18_isaac_127/'+n for n in ('driver.py','contract.py','native.py','config.json','program.json','media.py')}
    required|={PLAN,'outputs/mp18-video-run-127/release-manifest.json'}
    need(required<=set(f['files']),'Complete127 reviewed package')
    rows=[(str(p),fraw)]
    for rel,pin in f['files'].items():
        q=PurePosixPath(rel);need(not q.is_absolute() and q.as_posix()==rel and not any(x in ('.','..') for x in q.parts) and ':' not in rel and '\\' not in rel,'Canonical freeze path')
        pp=ROOT/rel;b=read(pp);need(digest(b)==pin['sha256'] and len(b)==pin['bytes'],'Current reviewed127 file');rows.append((str(pp),b))
    need(digest(read(ROOT/PLAN))==PLAN_SHA,'Reviewed127 plan')
    for who in ('main',):
        pp=out/('review/'+who+'-L4-final.json');b=read(pp);r=parse(b)
        need(type(r.get('unit')) is int and r['unit']==127 and r['phase']=='L4' and type(r['round']) is int and r['round'] in (1,2) and
             r['non_author'] is True and r['verdict']=='PASS' and type(r['unmet']) is int and r['unmet']==0 and
             type(r['unresolved_count']) is int and r['unresolved_count']==0 and r['source_freeze_sha256']==digest(fraw),'Final typed127 independent reviews')
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
