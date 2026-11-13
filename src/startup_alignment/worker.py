"""Internal child. No current writes or calls to023 build/verify;021 admission only."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys


def read(path, cap=1024*1024):
    with path.open('rb') as stream:
        raw = stream.read(cap+1)
    if len(raw) > cap:
        raise ValueError('Input exceeds bound: '+str(path))
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def capture(root, contract):
    return {path: read(root/path, cap) for path, cap in contract['inputs'].items()}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, required=True)
    cli.add_argument('--bundle', type=Path, required=True)
    cli.add_argument('--contract', type=Path, required=True)
    args = cli.parse_args()
    contract_raw = read(args.contract)
    contract = json.loads(contract_raw)
    asset = args.root/contract['asset_path']
    raw = read(asset)
    if sha(raw) != contract['asset_sha256']:
        raise ValueError('Frozen comparison content changed')
    spec = importlib.util.spec_from_file_location('_supervised_alignment_asset', asset)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Execute exactly the checked bytes, not a later loader read or cached pyc.
    exec(compile(raw, str(asset), 'exec'), module.__dict__)
    core_path = args.root/contract['core_path']
    core_raw = read(core_path)
    if sha(core_raw) != contract['core_sha256']:
        raise ValueError('Approved core content changed')
    core_spec = importlib.util.spec_from_file_location('_supervised_exact_frames', core_path)
    f = importlib.util.module_from_spec(core_spec)
    sys.modules[core_spec.name] = f
    exec(compile(core_raw, str(core_path), 'exec'), f.__dict__)
    dependency = module.admission(args.root, f)
    before = capture(args.root, contract)
    layout = f.decode(before[module.KIN])
    report = module.compare(layout, module.decode_native(before[module.NATIVE], f),
                            module.decode_commands(before[module.COMMANDS], f), f)
    report['dependency_021'] = dependency
    report['supervised_run_id'] = args.bundle.name
    report_raw = encoded(report)
    table_raw = module.table(report)
    if before != capture(args.root, contract) or dependency != module.admission(args.root, f):
        raise ValueError('Source/dependency changed while computing')
    (args.bundle/'report.json').write_bytes(report_raw)
    (args.bundle/'report.md').write_bytes(table_raw)
    response = {'run_id': args.bundle.name, 'status': 'OK', 'scope': report['status'],
        'contract_sha256': sha(contract_raw), 'sources': {p: sha(b) for p, b in before.items()},
        'files': {'report.json': sha(report_raw), 'report.md': sha(table_raw)},
        'dependency_021': dependency}
    (args.bundle/'response.json').write_bytes(encoded(response))


if __name__ == '__main__':
    main()
