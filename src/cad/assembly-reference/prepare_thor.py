"""Read saved Thor FCStd shapes only; never load or execute FreeCAD Python.

Build a cached-geometry reference for inspection. Not a robot manufacturing model.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import re
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'docs/references/packages/01/mechanical_refs/Thor/upstream'
EVIDENCE = ROOT / '.dev/assembly-evidence/conversion'
OUT = ROOT / 'models/six-axis-reference'
CLI = None


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(command_id, **params):
    return {'command': command_id, 'params': params}


def run_cli(args, logname):
    result = subprocess.run([str(CLI), *map(str, args)], capture_output=True,
                            env=dict(os.environ, SOLIDCRAFT_GPU='cpu'), timeout=120)
    (EVIDENCE / (logname + '.stdout.json')).write_bytes(result.stdout)
    (EVIDENCE / (logname + '.stderr.txt')).write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout.decode('utf-8')


def properties(obj):
    return {x.attrib['name']: x for x in obj.findall('./Properties/Property')}


def prop_child(props, name):
    return props[name][0] if name in props and len(props[name]) else None


def placement(props, name='Placement'):
    p = prop_child(props, name)
    if p is None:
        return np.eye(4)
    q = [float(p.attrib.get(k, d)) for k, d in [('Q3', 1), ('Q0', 0), ('Q1', 0), ('Q2', 0)]]
    mat = trimesh.transformations.quaternion_matrix(q)
    mat[:3, 3] = [float(p.attrib.get(k, 0)) for k in ['Px', 'Py', 'Pz']]
    return mat


class Archive:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.zip = zipfile.ZipFile(self.path)
        self.xml = ET.fromstring(self.zip.read('Document.xml'))
        self.types = {x.attrib['name']: x.attrib['type'] for x in self.xml.findall('./Objects/Object')}
        self.objects = {x.attrib['name']: x for x in self.xml.findall('./ObjectData/Object')}


def set_prop(props, name, typ, tag, attributes):
    p = ET.SubElement(props, 'Property', name=name, type=typ)
    ET.SubElement(p, tag, **attributes)


def xml_placement(matrix):
    q = trimesh.transformations.quaternion_from_matrix(matrix)
    return dict(zip(['Px', 'Py', 'Pz', 'Q0', 'Q1', 'Q2', 'Q3'],
                    map(lambda x: f'{float(x):.16g}', [*matrix[:3, 3], q[1], q[2], q[3], q[0]])))


def minimal_fcstd(path, brep, *, own_placement=None, parent_matrix=None):
    doc = ET.Element('Document', SchemaVersion='4', ProgramVersion='0.19R24276', FileVersion='1')
    objects = ET.SubElement(doc, 'Objects', Count='2' if parent_matrix is not None else '1')
    data = ET.SubElement(doc, 'ObjectData', Count='2' if parent_matrix is not None else '1')
    if parent_matrix is not None:
        ET.SubElement(objects, 'Object', type='App::Part', name='ReferenceGroup')
        pp = ET.SubElement(ET.SubElement(data, 'Object', name='ReferenceGroup'), 'Properties')
        set_prop(pp, 'Label', 'App::PropertyString', 'String', {'value': 'ReferenceGroup'})
        set_prop(pp, 'Visibility', 'App::PropertyBool', 'Bool', {'value': 'true'})
        set_prop(pp, 'Placement', 'App::PropertyPlacement', 'PropertyPlacement', xml_placement(parent_matrix))
        group = ET.SubElement(ET.SubElement(pp, 'Property', name='Group', type='App::PropertyLinkList'), 'LinkList', count='1')
        ET.SubElement(group, 'Link', value='SavedShape')
    ET.SubElement(objects, 'Object', type='Part::Feature', name='SavedShape')
    pp = ET.SubElement(ET.SubElement(data, 'Object', name='SavedShape'), 'Properties')
    set_prop(pp, 'Label', 'App::PropertyString', 'String', {'value': 'SavedShape'})
    set_prop(pp, 'Visibility', 'App::PropertyBool', 'Bool', {'value': 'true'})
    set_prop(pp, 'Placement', 'App::PropertyPlacement', 'PropertyPlacement', xml_placement(own_placement if own_placement is not None else np.eye(4)))
    set_prop(pp, 'Shape', 'Part::PropertyPartShape', 'Part', {'file': 'SavedShape.brp'})
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('Document.xml', ET.tostring(doc, encoding='utf-8', xml_declaration=True))
        z.writestr('SavedShape.brp', brep)


def probe():
    """Differential probes show whether importer double-applies BREP/own Placement."""
    archive = Archive(SOURCE/'freecad-src/AssemblyArt1.FCStd')
    p = properties(archive.objects['Screw'])
    brep = archive.zip.read(prop_child(p, 'Shape').attrib['file'])
    source_matrix = placement(p)
    translation = np.eye(4)
    translation[0, 3] = 100
    results = {}
    for name, own, parent in [('identity_xml', np.eye(4), None), ('source_xml', source_matrix, None),
                               ('parent100', np.eye(4), translation)]:
        fcstd = EVIDENCE/f'probe_{name}.FCStd'
        minimal_fcstd(fcstd, brep, own_placement=own, parent_matrix=parent)
        script = EVIDENCE/f'probe_{name}.json'
        write_json(script, {'commands': [command('file.insert_step', path=str(fcstd))]})
        meshpath = EVIDENCE/f'probe_{name}.stl'
        run_cli(['run', script, '--out', meshpath, '--results'], f'probe_{name}')
        mesh = trimesh.load_mesh(meshpath)
        results[name] = {'bounds_mm': mesh.bounds.tolist(), 'volume_mm3': float(mesh.volume), 'faces': len(mesh.faces)}
    results['own_placement_not_doubled'] = np.allclose(results['identity_xml']['bounds_mm'], results['source_xml']['bounds_mm'], atol=1e-6)
    results['parent_translation_applied_once'] = np.allclose(np.array(results['parent100']['bounds_mm']) - np.array(results['identity_xml']['bounds_mm']), [[100,0,0],[100,0,0]], atol=1e-6)
    write_json(EVIDENCE/'transform_probe.json', results)
    print(json.dumps(results, indent=2))


def inventory():
    archives = {}
    leaves = []
    ignored = []
    links = []

    def get_archive(path):
        path = Path(path).resolve(strict=True)
        if path not in archives:
            archives[path] = Archive(path)
        return archives[path]

    def walk(archive, name, parent, path, stack=(), force=False):
        key = (archive.path, name)
        if key in stack:
            raise ValueError(f'Cycle: {path}')
        obj = archive.objects[name]
        props = properties(obj)
        typ = archive.types[name]
        vis = prop_child(props, 'Visibility')
        if not force and vis is not None and vis.attrib.get('value') == 'false':
            ignored.append({'path': path, 'reason': 'hidden'})
            return
        if typ == 'App::Link':
            x = prop_child(props, 'LinkedObject')
            if x is None:
                raise ValueError(f'Link without target {path}')
            if prop_child(props, 'LinkTransform').attrib['value'] != 'false':
                raise ValueError(f'Unsupported LinkTransform=true {path}')
            for k, default in [('Scale', 1), ('ElementCount', 0)]:
                c = prop_child(props, k)
                if c is not None and float(c.attrib['value']) != default:
                    raise ValueError(f'Unsupported {k} in {path}')
            target_archive = get_archive(archive.path.parent / x.attrib['file']) if x.attrib.get('file') else archive
            target_name = x.attrib['name']
            link_matrix = placement(props)
            target_matrix = placement(properties(target_archive.objects[target_name]))
            # LinkTransform=false replaces the linked object's own Placement.
            # BREP already carries that own Placement: remove once here, never add twice.
            outer = parent @ link_matrix @ np.linalg.inv(target_matrix)
            links.append({'path': path, 'source': str(archive.path.relative_to(ROOT)), 'name': name,
                          'target_file': str(target_archive.path.relative_to(ROOT)), 'target_object': target_name,
                          'link_matrix': link_matrix.tolist(), 'target_placement': target_matrix.tolist()})
            walk(target_archive, target_name, outer, path, stack+(key,), force=True)
        elif typ in ('App::Part', 'App::DocumentObjectGroup'):
            group = prop_child(props, 'Group')
            if group is not None:
                for child in group:
                    child_name = child.attrib['value']
                    walk(archive, child_name, parent @ placement(props), path+'/'+child_name, stack+(key,))
        elif typ in ('PartDesign::CoordinateSystem', 'App::Origin', 'App::Line', 'App::Plane'):
            ignored.append({'path': path, 'reason': 'datum'})
        elif 'Shape' in props:
            shape_name = prop_child(props, 'Shape').attrib['file']
            if shape_name not in archive.zip.namelist():
                raise ValueError(f'Missing saved shape {path}')
            label = prop_child(props, 'Label')
            leaves.append({'path': path, 'source': str(archive.path.relative_to(ROOT)), 'object': name,
                           'type': typ, 'label': label.attrib['value'] if label is not None else name,
                           'brep': shape_name, 'outer_matrix': parent.tolist(),
                           'source_placement': placement(props).tolist(),
                           'brep_sha256': hashlib.sha256(archive.zip.read(shape_name)).hexdigest()})
        elif typ not in ('App::FeaturePython',):
            ignored.append({'path': path, 'reason': f'no saved shape: {typ}'})

    root = get_archive(SOURCE/'freecad-src/Assembly.FCStd')
    for node in prop_child(properties(root.objects['Model']), 'Group'):
        name = node.attrib['value']
        if root.types[name] == 'App::Link':
            walk(root, name, np.eye(4), name)
    for i, leaf in enumerate(leaves):
        leaf['index'] = i
    result = {'leaves': leaves, 'visible_links': links, 'ignored': ignored,
              'sources': [{'path': str(path.relative_to(ROOT)), 'sha256': sha(path)} for path in sorted(archives)],
              'groups': {g: sum(x['path'].split('/')[0] == g for x in leaves) for g in dict.fromkeys(x['path'].split('/')[0] for x in leaves)}}
    write_json(EVIDENCE/'cached_shape_inventory.json', result)
    return result, archives


def prepare():
    inv, archives = inventory()
    cached = EVIDENCE/'saved-shapes'
    cached.mkdir(exist_ok=True)
    scripts = []
    for gi, (group, count) in enumerate(inv['groups'].items()):
        commands = [command('component.activate', component='root'), command('component.create', name=group)]
        for leaf in [x for x in inv['leaves'] if x['path'].split('/')[0] == group]:
            source = (ROOT/leaf['source']).resolve()
            fname = f"{source.stem}__{leaf['object']}.FCStd"
            target = cached/fname
            if not target.exists():
                minimal_fcstd(target, archives[source].zip.read(leaf['brep']))
            commands.append(command('file.insert_step', path=str(target),
                                    name=f"{leaf['index']:03d}_{leaf['label']}",
                                    matrix=leaf['outer_matrix'], up='z'))
        commands.append(command('component.activate', component='root'))
        script = EVIDENCE/f'build_{gi}_{group}.json'
        write_json(script, {'commands': commands})
        scripts.append(script)
    print(json.dumps({'sources': len(inv['sources']), 'shapes': len(inv['leaves']), 'groups': inv['groups']}, indent=2))
    return scripts


def diagnostic():
    """Bounded import with every rejected source recorded; never returns a full-fidelity PASS."""
    scripts = prepare()
    start = time.monotonic()
    previous = None
    failures = []
    completed_groups = []
    attempts = []
    for gi, original_script in enumerate(scripts):
        commands = json.loads(original_script.read_text(encoding='utf-8'))['commands']
        attempt = 0
        while True:
            if time.monotonic() - start > 300:
                write_json(EVIDENCE/'diagnostic_status.json', {'status':'INCOMPLETE_TIME_BUDGET', 'failures':failures, 'groups':completed_groups, 'attempts':attempts})
                return
            script = EVIDENCE/f'diagnostic_{gi}_{attempt}.json'
            write_json(script, {'commands':commands})
            checkpoint = EVIDENCE/f'thor_diagnostic_{gi}.solidcraft'
            args = ['run', script, '--save', checkpoint, '--results', '--timings']
            if previous is not None:
                args += ['--in', previous]
            print(f'Diagnostic group {gi+1}/6 attempt {attempt+1}: {len(commands)-3} shapes', flush=True)
            tick = time.monotonic()
            try:
                run_cli(args, f'diagnostic_{gi}_{attempt}')
            except RuntimeError as exc:
                error = str(exc)
                match = re.search(r'step (\d+) \(file.insert_step\)', error)
                if not match:
                    raise
                offset = int(match[1])-1
                rejected = commands.pop(offset)
                failures.append({'group':gi, 'command':rejected, 'error':error})
                write_json(EVIDENCE/'diagnostic_status.json', {'status':'IN_PROGRESS_WITH_REJECTED_SHAPES', 'failures':failures, 'groups':completed_groups, 'attempts':attempts})
                print(f"Rejected {rejected['params']['name']}: {error[:250]}", flush=True)
                attempt += 1
                if attempt >= 12:
                    return
            else:
                attempts.append({'group':gi,'attempt':attempt,'seconds':time.monotonic()-tick})
                completed_groups.append({'group':gi,'accepted_shapes':len(commands)-3})
                previous = checkpoint
                break
    # Even an accepted cached body can have silently omitted faces in its warning
    # list. These native checkpoints are diagnostic only, never a deliverable.
    write_json(EVIDENCE/'diagnostic_status.json', {'status':'DIAGNOSTIC_ONLY_NOT_DELIVERABLE',
                'failures':failures, 'groups':completed_groups, 'attempts':attempts,
                'elapsed_seconds':time.monotonic()-start, 'last_checkpoint':str(previous.relative_to(ROOT))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--solidcraft', required=True, type=Path)
    args = parser.parse_args()
    CLI = args.solidcraft.resolve(strict=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if args.probe:
        probe()
    elif args.inventory:
        prepare()
    elif args.diagnostic:
        diagnostic()
