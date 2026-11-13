"""047 fixed solver/PD experiment; approved gravity and geometry are preserved."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def approved_dependencies(root=ROOT):
    root=Path(root);pins=json.loads((root/'src/simulation/settling_recovery/pins.json').read_text(encoding='utf-8'))
    for path,expected in pins['dependencies_sha256'].items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Approved transitive dependency drift before import: '+path)
    return pins


if (HERE/'gravity_core.py').is_file():
    job=json.loads((HERE/'job.json').read_text(encoding='utf-8'))
    for name in ('gravity_core.py','motion_core.py'):
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=job['files_sha256'][name]:
            raise ValueError('Executed gravity dependency changed: '+name)
    path=HERE/'gravity_core.py'
else:
    approved_dependencies()
    path=ROOT/'src/simulation/contact_motion/core.py'
spec=importlib.util.spec_from_file_location('_recovery_gravity',path)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
load_program,sample,total_time=old.load_program,old.sample,old.total_time
segments=old.motion.segments
gravity_efforts,bounded_efforts,CAP=old.gravity_efforts,old.bounded_efforts,old.CAP


def gains(snapshot):
    variant=snapshot.get('control_variant')
    if variant not in ('solver','solver_pd'):raise ValueError('Approved fixed control variant required')
    result=old.gains(snapshot)
    if variant=='solver_pd':
        result['kp']=[4*x for x in result['kp']]
        result['kd']=[2*x for x in result['kd']]
    return result
