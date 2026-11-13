"""116: an explicit lifetime precedes every application read."""
import ast
import sys
import base64
import contextlib
import ctypes
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
import time
import types
import uuid
import zipfile
import zlib

UNIT = '116'
SRC = 'src/simulation/blended_reference_trial_116'
OUT = 'outputs/blended-reference-trial-116'
PLAN = 'docs/design/116-blended-reference-trial.md'
PLAN_SHA = 'b6ba64dc67b9a1ea822059467ffb6120d8144c99915feaf848cf486c1aece78e'
L2_SHA = '5d99a281dc89c726036b5ba45dcacd21c887f6f05554d80757c1fb9690ac3287'
L2_ROUND = 2
HELPER_SHA = '2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0'
MUTABLE = {'test_driver.py', 'test_scene.py', 'program.json', 'test_validate.py', 'bootstrap.py', 'test_bootstrap.py', 'config.json', 'scene.py', 'decision_schema.py', 'workspace.py', 'validate.py', 'test_decision_schema.py', 'driver.py'}
AC = {'B3', 'C2', 'C1', 'E1', 'E3', 'C3', 'P2', 'D1', 'P1', 'B4', 'I1', 'B2', 'B1', 'D2', 'I2', 'E2', 'C4', 'E4'}
CENSUS_SHA = 'b27671e9cd0694d3082a8a403e821f5fbad01b6c7aebc266bf022938a8198d0c'  # Bound after the new workspace reference is sealed.
CENSUS_RECORDS_SHA = 'c04d7f0029eeeda7342f892fad83f331764804151fe46684e9709f97cac133d3'
RECEIPT = OUT + '/workspace-preflight.json'
LEASE_KEYS = set(('schema_version unit nonce claim_sha256 plan_sha256 template_freeze_sha256 review_sha256 '
 'native_approval_sha256 client_started_monotonic client_deadline_monotonic remote_started_monotonic '
 'remote_deadline_monotonic remote_started_unix remote_deadline_unix bootstrap_sha256 helper_sha256 '
 'handshake_deduction_s').split())
REQUEST_KEYS = LEASE_KEYS - {'claim_sha256','remote_started_monotonic','remote_deadline_monotonic',
                           'remote_started_unix','remote_deadline_unix','handshake_deduction_s'}
NATIVE_KEYS = set(('unit explicit_user_approval user_quote scope duration_s native_limits '
 'native_budget_starts_after_review clock_mutation hardware_approved plan_sha256 '
 'template_freeze_sha256 review_sha256').split())


def need(ok, message):
    if not ok:
        raise ValueError(message)


def report(helper, *args, **kwargs):
    try: print(*args, **kwargs)
    except BaseException: helper._die()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('nonfinite JSON')
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    def finite(item):
        if type(item) is float:
            need(math.isfinite(item), 'finite JSON')
        if type(item) is dict:
            for v in item.values(): finite(v)
        if type(item) is list:
            for v in item: finite(v)
    finite(result)
    return result


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def hash_string(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def relative(name):
    return (type(name) is str and name and not name.startswith(('/', '\\')) and '\\' not in name
            and ':' not in name and all(p not in ('', '.', '..') for p in name.split('/')))


def safe(root, name=''):
    root = Path(root)
    need(root.is_absolute(), 'absolute root')
    if name:
        need(relative(name), 'closed relative path')
    p = root / name
    for q in (p, *p.parents):
        need(not q.is_symlink() and not q.is_junction(), 'links rejected')
    return p


def read(path):
    return parse(Path(path).read_bytes().decode('utf-8-sig'))


def write_new(path, raw):
    path = Path(path)
    safe(path.parent)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def module(raw, path, name):
    value = types.ModuleType(name)
    value.__file__ = str(path)
    value.__source_bytes__ = raw
    exec(compile(raw, str(path), 'exec'), value.__dict__)
    return value


def load_helper(root):
    root = Path(root)
    p = safe(root, SRC + '/winjob.py')
    if not p.exists():
        p = safe(root, 'src/simulation/single_host_controller_110/winjob.py')
    raw = p.read_bytes()
    need(digest(raw) == HELPER_SHA, 'exact immutable A helper')
    return module(raw, p, '_winjob114')


def native_gate(value, pins):
    need(type(value) is dict and set(value) == NATIVE_KEYS, 'closed native approval')
    need(value['unit'] == UNIT and value['explicit_user_approval'] is True
         and value['native_budget_starts_after_review'] is True
         and value['clock_mutation'] is False and value['hardware_approved'] is False
         and value['scope'] == '116_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S_HALFBLEND', 'new116 native authority')
    need(type(value['duration_s']) is int and value['duration_s'] == 2700
         and value['native_limits'] == {'import':1,'render_smoke':1,'motion':1}
         and all(type(v) is int for v in value['native_limits'].values()), 'exact purpose budget')
    need(type(value['user_quote']) is str and value['user_quote'].strip(), 'explicit user quote')
    for key in ('plan_sha256','template_freeze_sha256','review_sha256'):
        need(value[key] == pins[key], 'native pin ' + key)


def review_gate(review, round_number, freeze_hash=None, *, phase='L4'):
    need(type(review) is dict and review.get('unit') == UNIT and review.get('phase') == phase
         and type(review.get('round')) is int and review['round'] == round_number
         and review.get('non_author') is True and review.get('verdict') == 'PASS'
         and review.get('all_required_met') is True
         and type(review.get('met')) is int and review['met'] == 18
         and type(review.get('unmet')) is int and review['unmet'] == 0, 'typed complete116 review18')
    need(type(review.get('reviewer')) is str and review['reviewer'] and review['reviewer'] != 'author', 'non-author reviewer identity')
    need(type(review.get('required')) is int and review['required'] == 18 and
         type(review.get('unresolved_count')) is int and review['unresolved_count'] == 0, 'required18 and no unresolved')
    criteria = review.get('criteria')
    need(type(criteria) is list and len(criteria) == 18 and {r['id'] for r in criteria} == AC
         and all(r.get('required') is True and r.get('met') is True for r in criteria), 'all eighteen criteria')
    need(review.get('actual_plan_sha256') == PLAN_SHA
         and (phase == 'L2' or review.get('actual_freeze_sha256') == freeze_hash), 'exact reviewed bytes')
    units = review.get('unit_dispositions')
    need(type(units) is dict and {'B','C','D','E','integration','performance'} == set(units)
         and all(units[k].get('verdict') == 'PASS' and type(units[k].get('unresolved_count')) is int
                 and units[k]['unresolved_count'] == 0 for k in ('B','C','D','E','integration','performance')), 'each unit accepted')


def stamp(template, end):
    cfg = parse(template.decode('utf-8-sig'))
    need(type(cfg['deadline_unix']) is int and cfg['deadline_unix'] == 0 and number(end) and end > 0,
         'inactive template and fixed end')
    token = rb'"deadline_unix": 0(?=[,\r\n}])'
    need(len(re.findall(token, template)) == 1, 'exactly one deadline token')
    final = re.sub(token, b'"deadline_unix": ' + repr(float(end)).encode(), template)
    expected = dict(cfg); expected['deadline_unix'] = float(end)
    need(parse(final.decode('utf-8-sig')) == expected, 'single field change')
    return final


def workspace_validator(validate_raw, policy_raw):
    validator = module(validate_raw, 'workspace-validate116.py', '_workspace116')
    validator.bind_decision_schema(policy_raw)
    return validator


def workspace_bundle(source, payload, template):
    cfg = parse(template)
    need(type(cfg.get('source_A')) is list and type(cfg.get('source_B')) is list
         and len(cfg['source_A']) == 8 and len(cfg['source_B']) == 13
         and len(cfg['source_A'] + cfg['source_B']) == 21
         and set(cfg['source_A'] + cfg['source_B']) == set(source), 'exact source21 template names')
    projected = dict(source); projected['config.json'] = template
    bundle = {'source/'+n:raw for n,raw in projected.items()}
    model_prefix = 'models/robot-arm-urdf-v3/'
    models = {n[len(model_prefix):]:raw for n,raw in payload.items() if n.startswith(model_prefix)}
    need(len(models) == 16, 'exact model16')
    bundle.update({'model/'+n:raw for n,raw in models.items()})
    need(type(cfg.get('refs')) is dict and len(cfg['refs']) == 11, 'original ref11')
    for name,record in cfg['refs'].items():
        need(relative(name) and type(record) is dict and set(record) == {'path','sha256'}
             and relative(record['path']) and hash_string(record['sha256']), 'typed original ref')
        raw = payload[record['path']]
        need(digest(raw) == record['sha256'], 'original ref pin')
        bundle['ref/'+name] = raw
    need(len(bundle) == 48 and all(type(raw) is bytes for raw in bundle.values()), 'closed template bundle48')
    return bundle


def build_static_receipt(root):
    """Explicit local authoring only; never called by a consumer or native path."""
    root = Path(root)
    helper = load_helper(root)
    with helper.Fence(time.monotonic()+600):
        out = safe(root, OUT); target = safe(root, RECEIPT)
        need(not target.exists(), 'workspace receipt already exists; explicit revision required')
        census_raw = safe(root, OUT+'/dependency-census-pre-receipt.json').read_bytes()
        need(digest(census_raw) == CENSUS_SHA, 'pinned immutable census42')
        records = parse(census_raw)['records']
        need(type(records) is list and len(records) == 42
             and digest(canonical(records)) == CENSUS_RECORDS_SHA, 'exact immutable42')
        payload = {}; source = {}
        for record in records:
            path = safe(root, record['target_path'])
            if record['group'] == 'immutable_A' and not path.exists():
                path = safe(root, record['source_path'])
            raw = path.read_bytes()
            need(digest(raw) == record['sha256'] and len(raw) == record['bytes'], 'producer immutable dependency')
            payload[record['target_path']] = raw
            if record['group'] in ('source108','immutable_A'):
                source[Path(record['target_path']).name] = raw
        for name in ('driver.py','config.json','bootstrap.py','validate.py','decision_schema.py','scene.py','workspace.py','program.json','test_scene.py'):
            source[name] = safe(root, SRC+'/'+name).read_bytes()
        template = source['config.json']
        cfg = parse(template)
        need(type(cfg['deadline_unix']) is int and cfg['deadline_unix'] == 0
             and cfg.get('hardware_approved') is False and cfg['sdk'].get('hardware_approved') is False
             and cfg['sdk'].get('calibration_approved') is False, 'pure inactive template only')
        bundle = workspace_bundle(source,payload,template)
        receipt = workspace_validator(source['validate.py'], source['decision_schema.py']).produce_workspace_receipt(bundle)
        need(type(receipt) is bytes and receipt, 'canonical producer bytes')
        need(out == target.parent, 'receipt within exact OUT')
        receipt_sha = write_new(target,receipt)
        return {'path':str(target),'sha256':receipt_sha,
                'decision_inputs':{n:{'sha256':digest(raw),'bytes':len(raw)} for n,raw in bundle.items()}}



def scene_reference_binding(raw, original_sha):
    """Bind unchanged physical authoring and closed reference-only edits; no math/native acceptance."""
    need(type(raw) is bytes and type(original_sha) is str and
         original_sha == 'f3b4e08491124ea3daf13949dc994618374c0be8cd6267f56ef7ac4789fd1807',
         'original scene/old USD provenance')
    need(sys.version_info[:2] == (3, 12), 'physical scene AST uses CPython3.12')
    tree = ast.parse(raw, filename='source/scene.py')
    signatures = {'target_at':['program','time_s'], 'validate_program':['program','model']}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in signatures]
    need(len(functions) == 2 and {node.name for node in functions} == set(signatures), 'unique two reference definitions')
    allowed_calls = {'RuntimeError', 'binary32', 'dict', 'need', 'enumerate', 'len', 'target_at', 'int', 'range', 'list', 'abs', 'round', 'max', 'quintic', 'all', 'min', 'set', 'type', 'float', 'str', 'tuple'}
    scalar_types = {'int','float','str','bool','dict','list','tuple','set'}
    protected = allowed_calls | scalar_types | {'math'}
    readonly_methods = {'get','items','keys','values','copy'}
    private_dicts = {'q','velocity','maximum'}
    statements = (ast.Assign, ast.For, ast.If, ast.Expr, ast.Raise, ast.Return)
    banned = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef,
              ast.FunctionDef, ast.AsyncFunctionDef, ast.With, ast.AsyncWith, ast.Try,
              ast.While, ast.Await, ast.Yield, ast.YieldFrom, ast.Lambda, ast.NamedExpr,
              ast.AnnAssign, ast.AugAssign, ast.Delete, ast.Starred)
    for fn in functions:
        a = fn.args
        need([x.arg for x in a.args] == signatures[fn.name] and
             not (a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg or a.defaults or a.kw_defaults or
                  fn.decorator_list or fn.returns or fn.type_comment or fn.type_params) and
             all(x.annotation is None and x.type_comment is None for x in a.args),
             'unchanged pure reference signature')
        parents = {child: node for node in ast.walk(fn) for child in ast.iter_child_nodes(node)}
        locals_ = {node.id for node in ast.walk(fn) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        args = set(signatures[fn.name])
        need(not (locals_ & (args | protected)), 'reference cannot shadow inputs/callees/types/math')
        for node in ast.walk(fn):
            if node is fn:
                continue
            need(not isinstance(node, banned), 'closed reference syntax: '+type(node).__name__)
            if isinstance(node, ast.stmt):
                need(isinstance(node, statements), 'closed reference statement')
            if isinstance(node, ast.comprehension):
                need(node.is_async == 0, 'synchronous reference expression')
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    need(node.id in args | locals_ | protected, 'closed reference free name '+node.id)
                if isinstance(node.ctx, ast.Store) and node.id in private_dicts:
                    owner = parents[node]
                    need(isinstance(owner, ast.Assign) and len(owner.targets) == 1 and
                         owner.targets[0] is node and isinstance(owner.value, (ast.Dict, ast.DictComp)),
                         'local dict cannot alias external input')
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
                need(isinstance(node.value, ast.Name) and node.value.id == 'maximum' and
                     'maximum' in locals_, 'only local maximum subscript writes')
            if isinstance(node, ast.Attribute):
                parent = parents[node]
                need(isinstance(node.ctx, ast.Load) and isinstance(parent, ast.Call) and
                     parent.func is node and isinstance(node.value, ast.Name),
                     'attributes only as approved simple callees')
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    need(func.id in allowed_calls and not node.keywords, 'approved positional reference call')
                    if func.id == 'type':
                        need(len(node.args) == 1, 'one-argument type only')
                elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    receiver, method = func.value.id, func.attr
                    if method == 'update':
                        keys = [key.arg for key in node.keywords]
                        need(receiver in {'q','velocity'} and not node.args and len(keys) == 3 and
                             set(keys) == {'KG1_slide_A','KG1_slide_B','KG1_pinion'} and
                             receiver in locals_, 'fixed local gripper update only')
                    elif receiver == 'math':
                        need(method in {'isfinite','sqrt'} and len(node.args) == 1 and
                             not node.keywords, 'approved math call')
                    else:
                        need(receiver in args | locals_ and method in readonly_methods and
                             not node.keywords, 'read-only container method')
                else:
                    need(False, 'no callable aliases or expression callees')
    projected = ast.Module(body=[node for node in tree.body if node not in functions], type_ignores=tree.type_ignores)
    need(digest(ast.dump(projected, include_attributes=False).encode('utf-8')) ==
         '5babee70c8f3c8a85026ee51e86b52b12e04943fc6788206f901bfd59ab61f9f',
         'physical scene module projection')
    return True


def context(root, round_number, *, helper, owner_end, require_native=False):
    need(type(round_number) is int and round_number in (1,2), 'closed review round')
    need(number(owner_end) and owner_end > time.monotonic(), 'known live owner end')
    need(type(require_native) is bool, 'typed native request')
    with helper.Fence(owner_end):
        root = Path(root); src = safe(root, SRC); out = safe(root, OUT)
        plan = safe(root, PLAN).read_bytes()
        l2path = safe(root, OUT + '/review/L2-r%d.json' % L2_ROUND); l2raw = l2path.read_bytes(); l2 = parse(l2raw)
        need(digest(plan) == PLAN_SHA and digest(l2raw) == L2_SHA and l2.get('unit') == UNIT
             and l2.get('phase') == 'L2' and l2.get('round') == L2_ROUND and l2.get('verdict') == 'PASS'
             and l2.get('all_required_met') is True, 'fixed final L2 and plan')
        review_gate(l2, L2_ROUND, phase='L2')
        freeze_path = out / ('source-freeze-r%d.json' % round_number)
        review_path = out / 'review' / ('L4-r%d.json' % round_number)
        fr = freeze_path.read_bytes(); rr = review_path.read_bytes(); freeze = parse(fr); review = parse(rr)
        need(freeze.get('unit') == UNIT and freeze.get('plan_sha256') == PLAN_SHA
             and freeze.get('L2_sha256') == L2_SHA
             and type(freeze.get('source_count')) is int and freeze['source_count'] == 21
             and set(freeze['source']) == MUTABLE
             and set(freeze['harness']) == {'execute.py'}, 'source13 plus harness1 freeze')
        review_gate(review, round_number, digest(fr))
        deps = freeze['dependencies']
        need(type(deps) is list and len(deps) == 43 and len({d['target_path'] for d in deps}) == 43,
             'exact dependency43')
        # Dependency records are part of the reviewed freeze, not a hidden census file.
        groups = {g: sum(d['group'] == g for d in deps) for g in ('source108','refs108','refs116','model','USD_pure_gate','immutable_A','workspace_preflight')}
        need(groups == {'source108':11,'refs108':10,'refs116':1,'model':16,'USD_pure_gate':3,'immutable_A':1,'workspace_preflight':1}, 'closed dependency groups')
        immutable = [d for d in deps if d['group'] != 'workspace_preflight']
        need(digest(canonical(immutable)) == CENSUS_RECORDS_SHA, 'exact pinned immutable42')
        receipt_records = [d for d in deps if d['group'] == 'workspace_preflight']
        need(len(receipt_records) == 1 and receipt_records[0]['source_path'] == RECEIPT
             and receipt_records[0]['target_path'] == RECEIPT, 'sole workspace receipt path')
        payload = {}; source = {}
        for d in deps:
            need(set(d) == {'source_path','target_path','sha256','bytes','group'} and hash_string(d['sha256'])
                 and type(d['bytes']) is int and d['bytes'] > 0 and relative(d['source_path']), 'typed dependency')
            p = safe(root, d['target_path'])
            # Local preflight may use the sole original A asset; capsule uses its alias.
            if d['group'] == 'immutable_A' and not p.exists(): p = safe(root, d['source_path'])
            raw = p.read_bytes()
            need(len(raw) == d['bytes'] and digest(raw) == d['sha256'], 'dependency bytes ' + d['target_path'])
            payload[d['target_path']] = raw
            if d['group'] in ('source108','immutable_A'): source[Path(d['target_path']).name] = raw
        backup = out / 'config-before-budget.json'
        for name, pin in freeze['source'].items():
            raw = safe(root, SRC + '/' + name).read_bytes()
            template = backup.read_bytes() if name == 'config.json' and backup.exists() else raw
            need(hash_string(pin) and digest(template) == pin, 'mutable source ' + name)
            payload[SRC + '/' + name] = template
            if name in ('driver.py','config.json','bootstrap.py','validate.py','decision_schema.py','scene.py','workspace.py','program.json','test_scene.py'): source[name] = raw
        raw = safe(root, OUT + '/execute.py').read_bytes()
        need(digest(raw) == freeze['harness']['execute.py'], 'harness pin'); payload[OUT + '/execute.py'] = raw
        need(len(source) == 21 and digest(source['winjob.py']) == HELPER_SHA, 'runtime21/helper')
        template = payload[SRC + '/config.json']; cfg = parse(template.decode('utf-8-sig'))
        need(type(cfg['deadline_unix']) is int and cfg['deadline_unix'] == 0
             and cfg.get('hardware_approved') is False
             and cfg['sdk'].get('hardware_approved') is False and cfg['sdk'].get('calibration_approved') is False,
             'inactive simulation-only config')
        old = read(safe(root, 'outputs/isaac-clock-ready-108/source-freeze-r2.json'))
        usdmod = module(payload['outputs/isaac-clock-ready-108/activate-budget.py'], 'pure-usd.py', '_pure_usd116')
        usdmod.verify_usd(safe(root, 'outputs/isaac-clock-ready-108/usd-check-r1-stdout.txt'), old)
        need(digest(source['root_binding.py']) == old['source']['root_binding.py'], 'original runtime root binding')
        scene_reference_binding(source['scene.py'], old['source']['scene.py'])
        bundle = workspace_bundle(source, payload, template)
        receipt_raw = payload[RECEIPT]; receipt_sha = receipt_records[0]['sha256']
        validator = workspace_validator(source['validate.py'], source['decision_schema.py'])
        identity = validator.verify_workspace_receipt_identity(bundle, receipt_raw, receipt_sha)
        decision_inputs = {n:{'sha256':digest(raw),'bytes':len(raw)} for n,raw in bundle.items()}
        need(type(identity) is dict and set(identity) == {'unit','scope','receipt_sha256','inputs_sha256'}
             and all(type(value) is str for value in identity.values())
             and identity['unit'] == UNIT
             and identity['scope'] == 'IDENTITY_ONLY_NOT_NUMERIC_OR_NATIVE_AUTHORITY'
             and identity['receipt_sha256'] == receipt_sha
             and identity['inputs_sha256'] == digest(canonical(decision_inputs)),
             'closed current-input identity evidence only')
        pins = {'plan_sha256':PLAN_SHA,'template_freeze_sha256':digest(fr),'review_sha256':digest(rr),
                'bootstrap_sha256':digest(source['bootstrap.py']),'helper_sha256':HELPER_SHA}
        metadata = {PLAN:plan, OUT+'/review/L2-r%d.json'%L2_ROUND:l2raw,
                    OUT+'/'+freeze_path.name:fr, OUT+'/review/'+review_path.name:rr}
        approval_path = out / 'native-approval.json'
        approval = None
        if require_native or approval_path.exists():
            ar = approval_path.read_bytes(); approval = parse(ar); native_gate(approval,pins)
            pins['native_approval_sha256'] = digest(ar); metadata[OUT+'/native-approval.json'] = ar
        payload.update(metadata)
        need(digest(helper.__source_bytes__) == HELPER_SHA, 'already loaded helper binding')
        return types.SimpleNamespace(root=root,src=src,out=out,round_number=round_number,helper=helper,
             helper_bytes=helper.__source_bytes__,template_config=cfg,template_bytes=template,source=source,
             freeze=freeze,review=review,pins=pins,payload=payload,workspace_preflight_sha256=receipt_sha,
             receipt_raw=receipt_raw,decision_inputs=decision_inputs,native_authorized=require_native and approval is not None)


def lease_check(lease, *, live=True):
    need(type(lease) is dict and set(lease) == LEASE_KEYS and lease['unit'] == UNIT
         and type(lease['schema_version']) is int and lease['schema_version'] == 1
         and type(lease['nonce']) is str and re.fullmatch('[0-9a-f]{32}', lease['nonce']), 'closed lease')
    need(all(hash_string(lease[k]) for k in LEASE_KEYS if k.endswith('_sha256')), 'lease hashes')
    for k in ('client_started_monotonic','client_deadline_monotonic','remote_started_monotonic',
              'remote_deadline_monotonic','remote_started_unix','remote_deadline_unix'):
        need(number(lease[k]) and lease[k] >= 0, 'typed lease clock')
    need(lease['plan_sha256'] == PLAN_SHA and lease['helper_sha256'] == HELPER_SHA
         and type(lease['handshake_deduction_s']) is int and lease['handshake_deduction_s'] == 20, 'lease fixed pins')
    need(lease['client_deadline_monotonic'] == lease['client_started_monotonic']+2700
         and lease['remote_deadline_monotonic'] == lease['remote_started_monotonic']+2700
         and lease['remote_deadline_unix'] == lease['remote_started_unix']+2700, 'original duration')
    need(digest(canonical({k:v for k,v in lease.items() if k != 'claim_sha256'})) == lease['claim_sha256'], 'claim canonical16 SHA')
    if live: need(time.monotonic() < lease['remote_deadline_monotonic'], 'expired remote lease')
    return dict(lease)


def claim_path(root):
    return safe(Path(root).parents[1], 'attempt.json')


def verify_execution(ctx, lease):
    lease_check(lease)
    need(claim_path(ctx.root).read_bytes() == canonical({k:v for k,v in lease.items() if k != 'claim_sha256'}), 'exact owned claim')
    for k,v in ctx.pins.items(): need(lease.get(k) == v, 'lease/context pin '+k)
    budget = read(ctx.out/'runtime-budget.json'); ex = read(ctx.out/'execution-freeze.json'); ready = read(ctx.out/'activation.json')
    need(budget.get('unit') == UNIT and type(budget.get('duration_s')) is int and budget['duration_s'] == 2700
         and budget.get('hardware_approved') is False and budget.get('plan_sha256') == PLAN_SHA
         and budget['started_unix'] == lease['remote_started_unix']
         and budget['started_monotonic'] == lease['remote_started_monotonic']
         and budget['deadline_unix'] == lease['remote_deadline_unix']
         and budget['lease_sha256'] == digest(canonical(lease))
         and budget.get('workspace_preflight_sha256') == ctx.workspace_preflight_sha256, 'runtime original budget')
    final = stamp(ctx.template_bytes, lease['remote_deadline_unix'])
    need(ctx.source['config.json'] == final, 'only exact active config')
    pins = {n:digest(raw) for n,raw in ctx.source.items()}
    need(budget['execution_source'] == ex['source'] == pins and len(pins) == 21
         and ex['template_freeze_sha256'] == lease['template_freeze_sha256']
         and ex['runtime_budget_sha256'] == digest((ctx.out/'runtime-budget.json').read_bytes())
         and ex['config_delta'] == 'deadline_unix only'
         and ex.get('workspace_preflight_sha256') == ctx.workspace_preflight_sha256, 'execution source21 pin chain')
    need(ready == {'status':'READY','runtime_budget_sha256':digest((ctx.out/'runtime-budget.json').read_bytes()),
         'execution_freeze_sha256':digest((ctx.out/'execution-freeze.json').read_bytes()),
         'template_config_sha256':digest(ctx.template_bytes),
         'workspace_preflight_sha256':ctx.workspace_preflight_sha256}, 'activation closure')
    return budget


def activate(ctx, lease):
    need(ctx.native_authorized is True, 'native approval before activation'); lease_check(lease)
    need(claim_path(ctx.root).read_bytes() == canonical({k:v for k,v in lease.items() if k != 'claim_sha256'}), 'claim precedes activation')
    for k,v in ctx.pins.items(): need(lease.get(k) == v, 'activation lease pin')
    for name in ('runtime-budget.json','execution-freeze.json','activation.json','config-before-budget.json'):
        need(not (ctx.out/name).exists(), 'activation already consumed')
    final = stamp(ctx.template_bytes, lease['remote_deadline_unix'])
    source = dict(ctx.source); source['config.json'] = final
    budget = {'unit':UNIT,'duration_s':2700,'started_unix':lease['remote_started_unix'],
              'started_monotonic':lease['remote_started_monotonic'],'deadline_unix':lease['remote_deadline_unix'],
              'hardware_approved':False,'plan_sha256':PLAN_SHA,'lease_sha256':digest(canonical(lease)),
              'workspace_preflight_sha256':ctx.workspace_preflight_sha256,
              'execution_source':{n:digest(b) for n,b in source.items()}}
    bh = write_new(ctx.out/'runtime-budget.json',canonical(budget))
    write_new(ctx.out/'config-before-budget.json',ctx.template_bytes)
    tmp = ctx.src/'config.activation.tmp'; write_new(tmp,final); os.replace(tmp,ctx.src/'config.json')
    eh = write_new(ctx.out/'execution-freeze.json',canonical({'source':budget['execution_source'],
         'template_freeze_sha256':lease['template_freeze_sha256'],'runtime_budget_sha256':bh,'config_delta':'deadline_unix only',
         'workspace_preflight_sha256':ctx.workspace_preflight_sha256}))
    write_new(ctx.out/'activation.json',canonical({'status':'READY','runtime_budget_sha256':bh,
         'execution_freeze_sha256':eh,'template_config_sha256':digest(ctx.template_bytes),
         'workspace_preflight_sha256':ctx.workspace_preflight_sha256}))
    ctx.source = source
    return verify_execution(ctx,lease)


class _WorkspaceScope:
    __slots__ = ('runtime','thread','token','end')

    def __init__(self, runtime, thread, token, end):
        for name,value in (('runtime',runtime),('thread',thread),('token',token),('end',end)):
            object.__setattr__(self,name,value)

    def __setattr__(self, name, value):
        raise AttributeError('immutable workspace scope')


class ActiveConfig(dict):
    pass


class Runtime:
    unit = UNIT
    hardware_approved = False

    def __init__(self, root, round_number, helper, lease, *, native_authorized=False):
        self.lease = lease_check(lease)
        self.root = Path(root); self.src = self.root/SRC; self.out = self.root/OUT
        self.round_number = round_number; self.helper = helper; self.helper_bytes = helper.__source_bytes__
        self.end_monotonic = float(self.lease['remote_deadline_monotonic'])
        self.native_authorized = native_authorized is True
        self._owners = threading.local()

    @contextlib.contextmanager
    def phase(self, limit=None):
        now = time.monotonic()
        need(limit is None or number(limit) and limit > 0, 'finite positive phase limit')
        stack = getattr(self._owners,'stack',[])
        end = min(self.end_monotonic, stack[-1] if stack else self.end_monotonic,
                  now+limit if limit is not None else self.end_monotonic)
        need(end > now, 'expired phase before I/O')
        frames = getattr(self._owners,'frames',[])
        need(len(frames) == len(stack), 'parallel armed owner frames')
        with self.helper.Fence(end):
            token = object()
            self._owners.stack = [*stack,end]
            self._owners.frames = [*frames,token]
            try: yield float(end)
            finally:
                self._owners.frames = frames
                self._owners.stack = stack

    def workspace_scope(self):
        stack = getattr(self._owners,'stack',[])
        frames = getattr(self._owners,'frames',[])
        need(stack and len(stack) == len(frames) and time.monotonic() < stack[-1],
             'actual armed workspace parent')
        return _WorkspaceScope(self, threading.get_ident(), frames[-1], stack[-1])

    def require_workspace_scope(self, scope):
        need(type(scope) is _WorkspaceScope and scope.runtime is self
             and scope.thread == threading.get_ident(), 'original workspace runtime/thread')
        stack = getattr(self._owners,'stack',[])
        frames = getattr(self._owners,'frames',[])
        need(len(frames) == len(stack) and any(token is scope.token and end == scope.end
             for token,end in zip(frames,stack)) and time.monotonic() < scope.end,
             'original active workspace frame/end')
        return None

    def workspace_authority(self, scope):
        self.require_workspace_scope(scope)
        with self.phase() as end:
            need(self.native_authorized is True, 'actual workspace authority')
            ctx = context(self.root,self.round_number,helper=self.helper,owner_end=end,require_native=True)
            verify_execution(ctx,self.lease)
            self.require_workspace_scope(scope)
            return {'schema_version':1,'unit':UNIT,'receipt_raw':ctx.receipt_raw,
                    'receipt_sha256':ctx.workspace_preflight_sha256,
                    'template_config_raw':ctx.template_bytes,
                    'active_config_raw':stamp(ctx.template_bytes,self.lease['remote_deadline_unix']),
                    'decision_inputs':{n:dict(pin) for n,pin in ctx.decision_inputs.items()}}

    def bind_config(self, cfg):
        need(isinstance(cfg,dict), 'config mapping')
        if isinstance(cfg,ActiveConfig):
            need(cfg.runtime is self, 'same runtime binding'); return cfg
        result = ActiveConfig(cfg); result.runtime = self
        return result

    def bind(self, ctx):
        ctx.runtime = self; ctx.cfg = self.bind_config(ctx.cfg)
        return ctx

    def verify(self):
        stack = getattr(self._owners,'stack',[])
        need(stack and stack[-1] > time.monotonic(), 'current-thread armed phase before reads')
        need(self.native_authorized is True, 'no runtime authority from an arbitrary lease')
        ctx = context(self.root,self.round_number,helper=self.helper,owner_end=stack[-1],require_native=True)
        return verify_execution(ctx,self.lease)

    def entry_code(self, ctx, role):
        need(role in ('native','supervise','export','controller'), 'closed entry role')
        need(self.native_authorized is True, 'entry authority')
        lease_check(self.lease)
        if role == 'controller':
            boot = str(self.src/'bootstrap.py'); driver = str(self.src/'driver.py'); job_hash = None; run = str(self.root)
            driver_sha = None; admission = None
        else:
            run = str(ctx.run); job_hash = ctx.job_hash
            driver_sha = ctx.job['inputs']['source/driver.py']
            need(ctx.job['inputs']['source/bootstrap.py'] == self.lease['bootstrap_sha256'], 'snapshot B pin')
            boot = str(Path(run)/'input/source/bootstrap.py'); driver = str(Path(run)/'input/source/driver.py')
            admission = ctx.admission if role in ('native','supervise') else None
        args = dict(root=str(self.root),round_number=self.round_number,lease=self.lease,role=role,
                    run=run,job_hash=job_hash,driver_sha=driver_sha,bootstrap=boot,driver=driver,admission=admission)
        body = ("a="+repr(args)+"\nimport pathlib\nend=a['lease']['remote_deadline_monotonic']\n"
                "if not isinstance(end,(int,float)) or isinstance(end,bool) or not math.isfinite(end) or end<=time.monotonic():raise SystemExit(2)\n"
                "with h.Fence(end):\n try:\n  b=pathlib.Path(a['bootstrap']).read_bytes()\n"
                "  if hashlib.sha256(b).hexdigest()!=a['lease']['bootstrap_sha256']:raise ValueError('bootstrap pin')\n"
                "  n={'__name__':'_child114','__file__':a['bootstrap'],'__source_bytes__':b};exec(compile(b,a['bootstrap'],'exec'),n)\n"
                "  rc=n['_child_entry'](a,h)\n except BaseException as e:\n  try:print(type(e).__name__,str(e),file=sys.stderr,flush=True)\n  except BaseException:h._die()\n  rc=2\n"
                "raise SystemExit(rc)\n")
        return inline(body,self.helper_bytes)


def _child_entry(args, helper):
    rt = Runtime(args['root'],args['round_number'],helper,args['lease'],native_authorized=True)
    with rt.phase():
        budget = rt.verify()
        raw = Path(args['driver']).read_bytes()
        expected = budget['execution_source']['driver.py']
        need(digest(raw) == expected and (args['driver_sha'] is None or args['driver_sha'] == expected), 'actual child driver pin')
        driver = module(raw,args['driver'],'_driver114_child')
        if args['role'] == 'controller': return driver.controller(rt)
        return driver.entry(args['run'],args['job_hash'],args['driver_sha'],args['role'],args['admission'],runtime=rt)


def prepare_capsule(ctx):
    need(ctx.native_authorized and len(ctx.payload) == 62, 'authorized exact payload62')
    manifest = {'unit':UNIT,'plan_sha256':PLAN_SHA,'files':{n:{'bytes':len(b),'sha256':digest(b)} for n,b in ctx.payload.items()}}
    out = io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(ctx.payload.items()): z.writestr(n,b)
        z.writestr('manifest.json',canonical(manifest))
    raw = out.getvalue()
    return types.SimpleNamespace(raw=raw,sha256=digest(raw),manifest=manifest)


def extract_capsule(raw, destination, expected_pins):
    destination = Path(destination); need(not destination.exists(), 'new capsule only'); safe(destination)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist(); names = [i.filename for i in infos]
        need(len(names) == 63 and len(set(names)) == 63 and all(relative(n) for n in names)
             and all((i.external_attr>>16)&0o170000 != 0o120000 for i in infos), 'closed safe63 ZIP')
        manifest = parse(z.read('manifest.json'))
        need(manifest.get('unit') == UNIT and manifest.get('plan_sha256') == PLAN_SHA
             and len(manifest['files']) == 62 and set(names) == set(manifest['files'])|{'manifest.json'}, 'exact manifest inventory')
        data = {n:z.read(n) for n in manifest['files']}
        need(all(digest(b) == manifest['files'][n]['sha256'] and len(b) == manifest['files'][n]['bytes'] for n,b in data.items()), 'same-read ZIP hashes')
        need(digest(data[SRC+'/bootstrap.py']) == expected_pins['bootstrap_sha256']
             and digest(data[PLAN]) == expected_pins['plan_sha256'], 'capsule expected source/plan')
        freezes=[n for n in data if re.fullmatch(re.escape(OUT)+r'/source-freeze-r[12]\.json',n)]
        need(len(freezes)==1 and digest(data[freezes[0]])==expected_pins['template_freeze_sha256'], 'expected capsule freeze')
        fr=parse(data[freezes[0]]);rnd=int(Path(freezes[0]).stem[-1])
        expected={SRC+'/'+n for n in MUTABLE}|{OUT+'/execute.py'}|{d['target_path'] for d in fr['dependencies']}
        expected|={PLAN,OUT+'/review/L2-r%d.json'%L2_ROUND,freezes[0],OUT+'/review/L4-r%d.json'%rnd,OUT+'/native-approval.json'}
        need(set(data)==expected and len(expected)==62,'exact frozen capsule allowlist before write')
        cfg=parse(data[SRC+'/config.json'])
        need(destination==(Path(cfg['remote_root']).parents[1]/'controller'/expected_pins['nonce']), 'configured capsule destination')
    destination.mkdir(parents=True,exist_ok=False)
    for name,b in data.items():
        p = safe(destination,name); p.parent.mkdir(parents=True,exist_ok=True); write_new(p,b)
    write_new(destination/'manifest.json',canonical(manifest))


def inline(body, helper_bytes):
    need(digest(helper_bytes) == HELPER_SHA, 'inline immutable helper')
    packet=len(helper_bytes).to_bytes(4,'big')+helper_bytes+body.encode()
    encoded=base64.b64encode(zlib.compress(packet,9)).decode()
    code = ("import base64,zlib,hashlib,types,time,math,sys;_p=zlib.decompress(base64.b64decode('"+encoded+"'));"
            "_n=int.from_bytes(_p[:4],'big');_b=_p[4:4+_n];"
            "assert hashlib.sha256(_b).hexdigest()=='"+HELPER_SHA+"';h=types.ModuleType('_fixedA');"
            "h.__source_bytes__=_b;exec(compile(_b,'<fixed-A>','exec'),h.__dict__);exec(_p[4+_n:])")
    need(len(code) < 7900, 'inline command envelope')
    return code


HELLO = """import json,ctypes
def c(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
with h.Fence(time.monotonic()+20):
 try:
  r=REQUEST
  if set(r)!=KEYS or r['unit']!='116' or r['schema_version']!=1:raise ValueError('request schema')
  ctypes.windll.kernel32.GetTickCount64.restype=ctypes.c_ulonglong
  ready={'kind':'READY','nonce':r['nonce'],'wall':time.time(),'monotonic':time.monotonic(),'uptime_ms':int(ctypes.windll.kernel32.GetTickCount64()),'site_loaded':'site' in sys.modules,'Kit_started':False,'request_sha256':hashlib.sha256(c(r)).hexdigest()}
  if ready['site_loaded'] or not sys.flags.no_site:raise ValueError('site loaded')
  print(c(ready).decode(),flush=True)
  line=sys.stdin.buffer.readline(16385)
  if len(line)>16384 or not line.endswith(b'\\n'):raise ValueError('bounded LIVE line')
  live=json.loads(line)
  if set(live)!={'kind','request','ready_sha256'} or live['kind']!='LIVE' or live['request']!=r or live['ready_sha256']!=hashlib.sha256(c(ready)).hexdigest():raise ValueError('closed LIVE')
  if any(isinstance(r[k],bool) or not isinstance(r[k],(int,float)) or not math.isfinite(r[k]) for k in ('client_started_monotonic','client_deadline_monotonic')) or r['client_deadline_monotonic']!=r['client_started_monotonic']+2700:raise ValueError('client interval')
  if sys.stdin.buffer.read(1):raise ValueError('no application payload in first HELLO')
  lease=dict(r,remote_started_monotonic=ready['monotonic']-20,remote_deadline_monotonic=ready['monotonic']+2680,remote_started_unix=ready['wall']-20,remote_deadline_unix=ready['wall']+2680,handshake_deduction_s=20)
  lease['claim_sha256']=hashlib.sha256(c(lease)).hexdigest()
  print(c({'kind':'GRANT','lease':lease}).decode(),flush=True);rc=0
 except BaseException as e:
  try:print(type(e).__name__,str(e),file=sys.stderr,flush=True)
  except BaseException:h._die()
  rc=2
raise SystemExit(rc)
"""


def hello_code(request, helper_bytes):
    need(type(request) is dict and set(request) == REQUEST_KEYS, 'HELLO fixed request')
    return inline(HELLO.replace('REQUEST',repr(request)).replace('KEYS',repr(REQUEST_KEYS)),helper_bytes)


def relay_code(args, helper_bytes):
    lease_check(args['lease'],live=False)
    body = ("a="+repr(args)+"\nentry=time.monotonic();end=a['lease']['remote_deadline_monotonic']\n"
      "if isinstance(end,bool) or not isinstance(end,(int,float)) or not math.isfinite(end) or end<=entry:raise SystemExit(2)\n"
      "initial=h.Fence(min(entry+20,end)).__enter__()\ntry:\n"
      " header=__import__('json').loads(sys.stdin.buffer.readline(4097))\n"
      " if set(header)!={'bootstrap_length','bootstrap_sha256','payload_length','payload_sha256'} or type(header['bootstrap_length']) is not int or not 0<header['bootstrap_length']<1000000:raise ValueError('closed relay header')\n"
      " b=sys.stdin.buffer.read(header['bootstrap_length'])\n"
      " if len(b)!=header['bootstrap_length'] or hashlib.sha256(b).hexdigest()!=a['lease']['bootstrap_sha256'] or header['bootstrap_sha256']!=a['lease']['bootstrap_sha256']:raise ValueError('B source pin')\n"
      " n={'__name__':'_relay114','__file__':'<stdin-bootstrap>','__source_bytes__':b};exec(compile(b,'<stdin-bootstrap>','exec'),n)\n"
      " rc=n['_relay_main'](a,h,initial,entry,header)\nexcept BaseException as e:\n if initial.closed:h._die()\n try:print(type(e).__name__,str(e),file=sys.stderr,flush=True)\n except BaseException:h._die()\n initial.close();rc=2\nraise SystemExit(rc)\n")
    return inline(body,helper_bytes)


def _relay_main(args, helper, initial, entry, header):
    lease = lease_check(args['lease']); root = Path(args['root']); operation = args['op']
    need(operation in ('install','activate','controller','fetch'), 'closed relay operation')
    need(root.is_absolute() and root.name == lease['nonce'] and root.parent.name == 'controller'
         and root.parent.parent.name == UNIT, 'fixed remote capsule namespace')
    claim = canonical({k:v for k,v in lease.items() if k != 'claim_sha256'})
    cp = claim_path(root)
    if operation == 'install':
        safe(cp.parent); cp.parent.mkdir(parents=True,exist_ok=True); write_new(cp,claim)
    else:
        need(cp.read_bytes() == claim, 'same fixed claim before full handoff')
    limit = {'install':120,'activate':120,'controller':None,'fetch':300}[operation]
    end = min(lease['remote_deadline_monotonic'], entry+limit if limit else lease['remote_deadline_monotonic'])
    with helper.Fence(end):
        initial.close()
        try:
            need(type(header['payload_length']) is int and 0 <= header['payload_length'] <= 1500000000
                 and hash_string(header['payload_sha256']), 'bounded payload header')
            payload = sys.stdin.buffer.read(header['payload_length'])
            need(len(payload) == header['payload_length'] and digest(payload) == header['payload_sha256']
                 and not sys.stdin.buffer.read(1), 'payload exact bytes/SHA/EOF')
            if operation == 'install':
                extract_capsule(payload,root,lease)
                context(root,args['round_number'],helper=helper,owner_end=end,require_native=True)
            else:
                need(not payload, 'no extra operation payload')
                ctx = context(root,args['round_number'],helper=helper,owner_end=end,require_native=True)
                if operation == 'activate': activate(ctx,lease)
                elif operation == 'controller':
                    rt = Runtime(root,args['round_number'],helper,lease,native_authorized=True)
                    with rt.phase():
                        rt.verify(); folder=ctx.out/'controller-process';folder.mkdir(exist_ok=False)
                        code=rt.entry_code(None,'controller')
                        argv=[str(Path(ctx.template_config['sdk']['isaac_root'])/'kit/python/python.exe'),'-I','-S','-B','-c',code]
                        need(len(subprocess.list2cmdline(argv))<8000,'actual controller command length')
                        remaining=end-time.monotonic();need(remaining>2,'controller cleanup reserve')
                        record=helper.run(argv,folder,remaining-2,cleanup_s=2)
                        write_new(folder/'process.json',canonical(record)); process_ok(record)
                        need(record['actual_child_exit_code']==0,'controller actual failure')
                else:
                    verify_execution(ctx,lease)
                    raw=fetch_zip(ctx.out)
                    sys.stdout.buffer.write(canonical({'bytes':len(raw),'sha256':digest(raw)})+b'\n'+raw)
                    sys.stdout.buffer.flush();return 0
            print(json.dumps({'unit':UNIT,'op':operation,'status':'COMPLETED','claim_sha256':lease['claim_sha256']}),flush=True)
            return 0
        except BaseException as exc:
            try: print(type(exc).__name__,str(exc),file=sys.stderr,flush=True)
            except BaseException: helper._die()
            return 2


def fetch_zip(out):
    files={}
    for p in Path(out).rglob('*'):
        safe(out,p.relative_to(out).as_posix())
        if p.is_file(): files[p.relative_to(out).as_posix()]=p.read_bytes()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(files.items()): z.writestr(n,b)
    return buffer.getvalue()


def process_ok(record):
    need(type(record) is dict and record.get('terminal') is True and record.get('raw_complete') is True
         and type(record.get('job_active_after')) is int and record['job_active_after']==0
         and type(record.get('child_pid')) is int and record['child_pid']>0 and record.get('child_state')=='REAPED'
         and type(record.get('actual_child_exit_code')) is int and type(record.get('policy_exit_code')) is int
         and record.get('timed_out') is False and record.get('errors')==[]
         and record['actual_child_exit_code']==record['policy_exit_code']==0,'actual process/EOF/exit closure')


def verify_fetch(ctx, lease, raw, require_success=False):
    """Pure original recovery consumer plus the new lease/execution binding."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist()
        need(len(names)==len(set(names)) and all(relative(n) for n in names)
             and all((i.external_attr>>16)&0o170000!=0o120000 for i in z.infolist()),'closed fetched names')
        data={n:z.read(n) for n in names}
    need(data['workspace-preflight.json'] == ctx.receipt_raw, 'fetched original workspace receipt bytes')
    budget=parse(data['runtime-budget.json']);ex=parse(data['execution-freeze.json']);ready=parse(data['activation.json'])
    active=stamp(ctx.template_bytes,lease['remote_deadline_unix'])
    source={n:digest(v) for n,v in ctx.source.items()};source['config.json']=digest(active)
    need(data['config-before-budget.json']==ctx.template_bytes
         and budget['unit']==UNIT and budget['hardware_approved'] is False and budget['plan_sha256']==PLAN_SHA
         and budget['lease_sha256']==digest(canonical(lease)) and budget['duration_s']==2700
         and budget['started_unix']==lease['remote_started_unix'] and budget['started_monotonic']==lease['remote_started_monotonic']
         and budget['deadline_unix']==lease['remote_deadline_unix']
         and budget['execution_source']==ex['source']==source
         and budget.get('workspace_preflight_sha256')==ctx.workspace_preflight_sha256,'offline original lease/source21')
    need(ex['runtime_budget_sha256']==digest(data['runtime-budget.json'])
         and ex['template_freeze_sha256']==lease['template_freeze_sha256'] and ex['config_delta']=='deadline_unix only'
         and ex.get('workspace_preflight_sha256')==ctx.workspace_preflight_sha256
         and ready=={'status':'READY','runtime_budget_sha256':digest(data['runtime-budget.json']),
                     'execution_freeze_sha256':digest(data['execution-freeze.json']),'template_config_sha256':digest(ctx.template_bytes),
                     'workspace_preflight_sha256':ctx.workspace_preflight_sha256},'offline activation pin chain')
    usd=module(ctx.payload['outputs/isaac-clock-ready-108/activate-budget.py'],'pure-usd.py','_offline_usd114')
    usd.verify_usd(safe(ctx.root,'outputs/isaac-clock-ready-108/usd-check-r1-stdout.txt'),
                   parse(ctx.payload['outputs/isaac-clock-ready-108/source-freeze-r2.json']))
    recovery=module(ctx.source['recovery.py'],'recovery.py','_original_recovery114')
    outcomes={};jobs={};validations={}
    for name in names:
        match=re.fullmatch(r'runs/([0-9a-f]{32})/job\.json',name)
        if not match:continue
        run_id=match[1];job=parse(data[name]);prefix='runs/'+run_id+'/retrieved/'
        files={n[len(prefix):]:v for n,v in data.items() if n.startswith(prefix)}
        if not files:continue
        need(job['run_id']==run_id and job['plan_sha256']==PLAN_SHA
             and job['hardware_approved'] is False
             and {n[7:]:v for n,v in job['inputs'].items() if n.startswith('source/')}==source
             and job['inputs'].get('workspace-preflight.json')==ctx.workspace_preflight_sha256,'fetched actual job/source21')
        mode,_,code=recovery.verify_output(run_id,digest(data[name]),job['purpose'],
                          {n:digest(v) for n,v in files.items()},lambda n:files[n])
        validation=parse(data['runs/'+run_id+'/validation.json'])
        need(validation['run_id']==run_id and validation['job_sha256']==digest(data[name])
             and validation['purpose']==job['purpose'],'actual validation identity')
        need(job['purpose'] not in outcomes,'no duplicated purpose receipt')
        outcomes[job['purpose']]={'mode':mode,'code':code,'status':validation['status']}
        jobs[job['purpose']]=(job,digest(data[name]));validations[job['purpose']]=validation
    if require_success:
        expected={'import':'IMPORT_VERIFIED','render_smoke':'SMOKE_VERIFIED','motion':'WORKSPACE_MOTION_VERIFIED'}
        need(set(outcomes)==set(expected) and all(outcomes[p]=={'mode':'CLOSED_NATIVE_ARTIFACT_COPY','code':0,'status':s}
             for p,s in expected.items()),'all original import/stop/motion recovered')
        for purpose in ('render_smoke','motion'):
            need(jobs[purpose][0]['inputs']['import-proof/job.json']==jobs['import'][1], 'accepted import precedes later phase')
        need(jobs['motion'][0]['inputs']['smoke-proof/job.json']==jobs['render_smoke'][1], 'accepted stop precedes motion')
        need(parse(data['current.json'])==validations['motion'], 'actual final current receipt')
        for purpose,name in (('import','import-verified.json'),('render_smoke','smoke-verified.json')):
            need(parse(data[name])=={'run_id':jobs[purpose][0]['run_id'],'job_sha256':jobs[purpose][1]}, 'accepted phase reference')
        process_ok(parse(data['controller-process/process.json']))
    return {'unit':UNIT,'raw_zip_sha256':digest(raw),'outcomes':outcomes,
            'controller_gates_reported_verified':bool(require_success),'native_outcome_accepted':False,
            'acceptance_scope':'REMOTE_C_GATES_BOUND_TO_RAW;INDEPENDENT_SEAL_AUDIT_REQUIRED',
            'hardware_approved':False}


def ssh_argv(cfg, code):
    ssh = str(Path(os.environ['SystemRoot'])/'System32/OpenSSH/ssh.exe')
    python = str(Path(cfg['sdk']['isaac_root'])/'kit/python/python.exe').replace('\\','/')
    need(re.fullmatch('[A-Za-z0-9_.-]+',cfg['ssh_alias']) and "'" not in python and '"' not in code,'closed SSH command')
    remote = "& '"+python+"' -I -S -B -c \""+code+"\""
    argv=[ssh,'-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ConnectTimeout=10',cfg['ssh_alias'],remote]
    need(len(subprocess.list2cmdline(argv)) < 8000,'actual SSH Windows command under8000')
    return argv


def first_exchange(ctx, request, client_end):
    end=min(client_end,request['client_started_monotonic']+20)
    need(end>time.monotonic(),'first20 before client I/O')
    with ctx.helper.Fence(end):
        return _first_exchange_owned(ctx,request,client_end)


def _first_exchange_owned(ctx, request, client_end):
    code=hello_code(request,ctx.helper_bytes);argv=ssh_argv(ctx.template_config,code)
    folder=ctx.out/('first-'+request['nonce']);folder.mkdir()
    def sender(stream,stdout_path,work_end):
        deadline=min(work_end,request['client_started_monotonic']+18)
        while True:
            raw=stdout_path.read_bytes()
            if b'\n' in raw:break
            need(time.monotonic()<deadline,'READY communication deadline');time.sleep(.005)
        need(time.monotonic()<deadline,'late READY')
        ready=parse(raw.split(b'\n',1)[0]); validate_ready(ready,request)
        stream.write(canonical({'kind':'LIVE','request':request,'ready_sha256':digest(canonical(ready))})+b'\n')
    start=time.monotonic()
    record=ctx.helper.run(argv,folder,18,cleanup_s=2,input_sender=sender)
    need(time.monotonic()-start<=20 and time.monotonic()<=request['client_started_monotonic']+20
         and time.monotonic()<client_end,'whole first20')
    process_ok(record)
    rows=(folder/'stdout.txt').read_bytes().splitlines();need(len(rows)==2,'two control rows')
    ready,grant=map(parse,rows);validate_ready(ready,request)
    need(type(grant) is dict and set(grant)=={'kind','lease'} and grant['kind']=='GRANT','closed pure grant')
    lease=lease_check(grant['lease'],live=False)
    need(all(lease[k]==v for k,v in request.items()) and lease['remote_started_monotonic']==ready['monotonic']-20
         and lease['remote_deadline_monotonic']==ready['monotonic']+2680
         and lease['remote_started_unix']==ready['wall']-20 and lease['remote_deadline_unix']==ready['wall']+2680,'fixed whole20 deduction')
    write_new(folder/'process.json',canonical(record));return lease


def validate_ready(ready, request):
    need(type(ready) is dict and set(ready)=={'kind','nonce','wall','monotonic','uptime_ms','site_loaded','Kit_started','request_sha256'}
         and ready['kind']=='READY' and ready['nonce']==request['nonce']
         and ready['site_loaded'] is False and ready['Kit_started'] is False
         and number(ready['wall']) and number(ready['monotonic'])
         and type(ready['uptime_ms']) is int and ready['uptime_ms']>=0
         and ready['request_sha256']==digest(canonical(request)),'actual closed OS READY')


def subsequent(ctx, lease, op, payload=b''):
    started=time.monotonic()
    limit={'install':120,'activate':120,'controller':2700,'fetch':300}[op]
    end=min(lease['client_deadline_monotonic'],started+limit)
    need(end>started,'original client end')
    with ctx.helper.Fence(end):
        return _subsequent_owned(ctx,lease,op,payload,end)


def _subsequent_owned(ctx, lease, op, payload, end):
    root=(Path(ctx.template_config['remote_root']).parents[1]/'controller'/lease['nonce']).as_posix()
    args={'root':root,'round_number':ctx.round_number,'lease':lease,'op':op}
    code=relay_code(args,ctx.helper_bytes);argv=ssh_argv(ctx.template_config,code)
    header={'bootstrap_length':len(ctx.source['bootstrap.py']),'bootstrap_sha256':digest(ctx.source['bootstrap.py']),
            'payload_length':len(payload),'payload_sha256':digest(payload)}
    folder=ctx.out/(op+'-'+lease['nonce']);folder.mkdir()
    wire=folder/'stdin.bin';write_new(wire,canonical(header)+b'\n'+ctx.source['bootstrap.py']+payload)
    need(end-time.monotonic()>2,'transport cleanup reserve')
    with ctx.helper.Fence(end):
        record=ctx.helper.run(argv,folder,max(.001,end-time.monotonic()-2),cleanup_s=2,stdin_path=wire)
        write_new(folder/'process.json',canonical(record));process_ok(record)
        raw=(folder/'stdout.txt').read_bytes()
        if op=='fetch':
            head,sep,data=raw.partition(b'\n');need(sep,'fetch header');h=parse(head)
            need(type(h) is dict and set(h)=={'bytes','sha256'} and type(h['bytes']) is int
                 and len(data)==h['bytes'] and digest(data)==h['sha256'],'actual fetch length/SHA')
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names=z.namelist();need(len(names)==len(set(names)) and all(relative(n) for n in names),'safe fetched ZIP')
                need(all((i.external_attr>>16)&0o170000!=0o120000 for i in z.infolist()),'no fetched link')
            write_new(folder/'retrieved.zip',data)
        else:
            row=parse(raw);need(row=={'unit':UNIT,'op':op,'status':'COMPLETED','claim_sha256':lease['claim_sha256']},'actual operation receipt')
        return folder


def run(root, round_number):
    helper=load_helper(root)
    with helper.Fence(time.monotonic()+120):
        try:
            ctx=context(root,round_number,helper=helper,owner_end=time.monotonic()+110,require_native=True)
            capsule=prepare_capsule(ctx)
        except BaseException as exc:
            try: report(helper,'116 preflight:',type(exc).__name__,str(exc),file=sys.stderr,flush=True)
            except BaseException: helper._die()
            return 2
    t0=time.monotonic();client_end=t0+2700
    with helper.Fence(client_end):
        try:
            nonce=uuid.uuid4().hex
            request=dict(schema_version=1,unit=UNIT,nonce=nonce,client_started_monotonic=t0,
                         client_deadline_monotonic=client_end,**ctx.pins)
            write_new(ctx.out/'remote-attempt.json',canonical(request))
            lease=first_exchange(ctx,request,client_end)
            write_new(ctx.out/'accepted-grant.json',canonical(lease))
            subsequent(ctx,lease,'install',capsule.raw)
            subsequent(ctx,lease,'activate')
            controller_code=0
            try: subsequent(ctx,lease,'controller')
            except BaseException as exc:
                controller_code=2
                try: report(helper,'116 controller failed:',type(exc).__name__,str(exc),file=sys.stderr,flush=True)
                except BaseException: helper._die()
            fetched=subsequent(ctx,lease,'fetch')
            verified=verify_fetch(ctx,lease,(fetched/'retrieved.zip').read_bytes(),require_success=controller_code==0)
            write_new(fetched/'offline-verification.json',canonical(verified))
            report(helper,json.dumps({'unit':UNIT,'status':'FETCHED' if controller_code==0 else 'FAILED_FETCHED',
                              'retrieved':str(fetched),'native_outcome_accepted':verified['native_outcome_accepted']}),flush=True)
            return controller_code
        except BaseException as exc:
            try: report(helper,'116 consumed failure:',type(exc).__name__,str(exc),file=sys.stderr,flush=True)
            except BaseException: helper._die()
            return 2
