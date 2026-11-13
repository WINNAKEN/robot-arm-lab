"""Splice the reviewed fresh_stage into an owned local candidate; never launch it."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'outputs/mp18-stage-diagnosis-124'
BASE = ROOT / 'src/simulation/mp18_isaac_119/native.py'
BASE_SHA256 = '42ecacda2b8bc1a1d4ed56da75abc4b5dbba3671483e4f2e8a2a762cfc7bb9d2'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def function_span(raw):
    tree = ast.parse(raw)
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name == 'fresh_stage']
    if len(nodes) != 1 or type(nodes[0]) is not ast.FunctionDef or nodes[0].decorator_list:
        raise ValueError('Exactly one ordinary undecorated fresh_stage required')
    node = nodes[0]
    rows = raw.splitlines(keepends=True)
    start, end = sum(map(len, rows[:node.lineno-1])), sum(map(len, rows[:node.end_lineno]))
    return start, end, node


def candidate_bytes(base, replacement):
    if digest(base) != BASE_SHA256:
        raise ValueError('Fixed original native SHA mismatch')
    start, end, old_node = function_span(base)
    rs, re, new_node = function_span(replacement)
    if ast.dump(old_node.args) != ast.dump(new_node.args):
        raise ValueError('Original function signature changed')
    body = replacement[rs:re]
    candidate = base[:start] + body + base[end:]
    cs, ce, _ = function_span(candidate)
    if candidate[:cs] != base[:start] or candidate[ce:] != base[end:]:
        raise ValueError('Bytes outside fresh_stage changed')
    compile(candidate, 'LOCAL_CANDIDATE_native.py', 'exec')
    return candidate, {'base_sha256': digest(base), 'replacement_sha256': digest(replacement),
                       'function_sha256': digest(body), 'prefix_sha256': digest(base[:start]),
                       'suffix_sha256': digest(base[end:]), 'outside_function_bytes_unchanged': True}


def build(output=None):
    destination = OUT / 'candidate' if output is None else Path(output)
    if not destination.is_absolute() or not destination.resolve().is_relative_to(OUT.resolve()):
        raise ValueError('Candidate output must stay in the owned output')
    for path in (destination, *destination.parents):
        if path.is_symlink() or path.is_junction():
            raise ValueError('No candidate reparse path')
    raw, proof = candidate_bytes(BASE.read_bytes(), (HERE / 'stage_reset.py').read_bytes())
    manifest = dict(unit=124, kind='LOCAL_UNDEPLOYED_NATIVE_CANDIDATE',
                    native_sha256=digest(raw), bytes=len(raw), approved_to_execute=False,
                    SDK_initializations=0, SSH_launches=0, hardware_approved=False, **proof)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / 'native.py').open('xb') as stream:
        stream.write(raw)
    with (destination / 'manifest.json').open('x', encoding='utf8') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps(build()))
