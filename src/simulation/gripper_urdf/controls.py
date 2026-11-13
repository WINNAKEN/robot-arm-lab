"""068: mutate/reseal copied assets and call the same semantic consumer.

This module never edits the canonical model. Every run keeps a new, uniquely
named collection of contradictory copies, including the missing-input case.
The original model must pass before and after all controls.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import struct
import sys
from uuid import uuid4
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assets
import verify

EXPECTED_CONTROLS = 20
REQUIRED_CONTROL_NAMES = (
    'slide_a_axis', 'slide_a_zero', 'slide_b_axis', 'slide_b_mimic_multiplier',
    'slide_b_mimic_offset', 'pinion_axis', 'pinion_center', 'pinion_zero_angle',
    'pinion_mimic_multiplier', 'pinion_mimic_offset', 'slide_a_limit', 'pinion_limit',
    'duplicated_fixed_mass', 'moving_com', 'moving_inertia', 'moving_collision_size',
    'moving_collision_rotation', 'arm_origin', 'moving_mesh_vertex', 'missing_moving_mesh',
)


def require_inventory(planned) -> None:
    """Count is a fixed acceptance contract, independent of the supplied cases."""
    assert len(REQUIRED_CONTROL_NAMES) == EXPECTED_CONTROLS, 'fixed control inventory definition'
    assert len(planned) == EXPECTED_CONTROLS, 'required control count must be exactly 20'
    assert tuple(case[0] for case in planned) == REQUIRED_CONTROL_NAMES, 'required unique control inventory'


def require_report(report) -> None:
    assert report['expected_controls'] == EXPECTED_CONTROLS, 'required report count must be exactly 20'
    rows = report['controls']
    assert len(rows) == EXPECTED_CONTROLS, 'required observed control count must be exactly 20'
    assert tuple(row['name'] for row in rows) == REQUIRED_CONTROL_NAMES, 'required report control inventory'
    assert report['all_caught'] is True, 'control report completion must be true'
    assert all(row['rejected'] and row['intended_reached'] and row['manifest_resealed'] for row in rows), 'some contradictory controls escaped the intended semantic check'
    assert report['positive_before']['ok'] and report['positive_after']['ok'], 'control baselines must pass'
    assert report['canonical_model_preserved'], 'canonical model changed during controls'


def xml_change(model: Path, path: str, attribute: str, value: str) -> None:
    description = model / 'robot_arm.urdf'
    tree = ET.parse(description)
    target = tree.find(path)
    if target is None:
        raise RuntimeError('Control target absent: ' + path)
    target.set(attribute, value)
    tree.write(description, encoding='utf-8', xml_declaration=True)


def referenced_mesh(model: Path, link_name: str) -> Path:
    tree = ET.parse(model / 'robot_arm.urdf')
    visual = tree.find(f"link[@name='{link_name}']/visual/geometry/mesh")
    if visual is None:
        raise RuntimeError('Control requires a mesh visual: ' + link_name)
    result = (model / visual.get('filename')).resolve()
    if model.resolve() not in result.parents:
        raise RuntimeError('Control mesh must be inside copied model')
    return result


def mesh_vertex_change(model: Path) -> None:
    path = referenced_mesh(model, 'KG1_A')
    raw = bytearray(path.read_bytes())
    if len(raw) < 134:
        raise RuntimeError('Control requires binary STL geometry')
    triangles = struct.unpack_from('<I', raw, 80)[0]
    if len(raw) != 84 + triangles * 50:
        raise RuntimeError('Control requires exact binary STL record count')
    # First triangle, first vertex X: 84 byte header + 12 byte normal.
    old = struct.unpack_from('<f', raw, 96)[0]
    struct.pack_into('<f', raw, 96, old + .001)
    path.write_bytes(raw)


def hide_mesh(model: Path) -> None:
    path = referenced_mesh(model, 'KG1_A')
    # Preserve the supplied bytes while making the actual URDF input absent.
    path.rename(path.with_suffix('.stl.hidden'))


def xml_case(name, path, attribute, value, expected):
    return (name, lambda model: xml_change(model, path, attribute, value), expected, False)


def cases():
    """Each marker names the semantic check that must reject the mutation."""
    return [
        xml_case('slide_a_axis', "joint[@name='KG1_slide_A']/axis", 'xyz', '1 0 0', 'gripper axis'),
        xml_case('slide_a_zero', "joint[@name='KG1_slide_A']/origin", 'xyz', '-0.021 0 0', 'gripper origin'),
        xml_case('slide_b_axis', "joint[@name='KG1_slide_B']/axis", 'xyz', '-1 0 0', 'gripper axis'),
        xml_case('slide_b_mimic_multiplier', "joint[@name='KG1_slide_B']/mimic", 'multiplier', '-1', 'gripper mimic'),
        xml_case('slide_b_mimic_offset', "joint[@name='KG1_slide_B']/mimic", 'offset', '0.001', 'gripper mimic'),
        xml_case('pinion_axis', "joint[@name='KG1_pinion']/axis", 'xyz', '0 -1 0', 'gripper axis'),
        xml_case('pinion_center', "joint[@name='KG1_pinion']/origin", 'xyz', '0 0 0.027', 'gripper origin'),
        xml_case('pinion_zero_angle', "joint[@name='KG1_pinion']/origin", 'rpy', '0 0 0', 'gripper origin'),
        xml_case('pinion_mimic_multiplier', "joint[@name='KG1_pinion']/mimic", 'multiplier', '74.07407407407408', 'gripper mimic'),
        xml_case('pinion_mimic_offset', "joint[@name='KG1_pinion']/mimic", 'offset', '0.1', 'gripper mimic'),
        xml_case('slide_a_limit', "joint[@name='KG1_slide_A']/limit", 'upper', '0.047', 'gripper limits'),
        xml_case('pinion_limit', "joint[@name='KG1_pinion']/limit", 'lower', '-3', 'gripper limits'),
        xml_case('duplicated_fixed_mass', "link[@name='KG1']/inertial/mass", 'value', '0.1842', 'assumed source mass'),
        xml_case('moving_com', "link[@name='KG1_A']/inertial/origin", 'xyz', '0 0 0', 'inertial COM'),
        xml_case('moving_inertia', "link[@name='KG1_B']/inertial/inertia", 'ixx', '0.001', 'actual STL box inertia'),
        xml_case('moving_collision_size', "link[@name='KG1_A']/collision/geometry/box", 'size', '1 1 1', 'actual STL collision size'),
        xml_case('moving_collision_rotation', "link[@name='KG1_R']/collision/origin", 'rpy', '0 0.1 0', 'collision RPY'),
        xml_case('arm_origin', "joint[@name='J3']/origin", 'xyz', '0.166 0 0', 'legacy arm joint'),
        ('moving_mesh_vertex', mesh_vertex_change, 'actual STL/source vertices', False),
        ('missing_moving_mesh', hide_mesh, 'missing mesh', True),
    ]


def payload_hashes(model: Path):
    return {
        path.relative_to(model).as_posix(): assets.sha(path)
        for path in sorted(model.rglob('*'))
        if path.is_file()
    }


def main() -> None:
    planned = cases()
    require_inventory(planned)
    source = assets.MODEL.resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    attempt = assets.OUT / 'controls' / f'{stamp}-{uuid4().hex[:8]}'
    attempt.mkdir(parents=True, exist_ok=False)
    original_hashes = payload_hashes(source)
    baseline_before = verify.verify(source)
    results = []
    for name, mutate, expected, permits_missing_file in planned:
        copied = attempt / name
        shutil.copytree(source, copied)
        mutate(copied)
        assets.seal(copied)
        manifest = assets.readj(copied / 'manifest.json')['files']
        actual = {
            path.relative_to(copied).as_posix(): assets.sha(path)
            for path in sorted(copied.rglob('*'))
            if path.is_file() and path.name != 'manifest.json'
        }
        assert manifest == actual, 'contradictory control must be completely resealed'
        result = {
            'name': name,
            'model': copied.relative_to(assets.ROOT).as_posix(),
            'manifest_resealed': True,
            'intended_check': expected,
            'rejected': False,
            'intended_reached': False,
        }
        try:
            verify.verify(copied)
        except AssertionError as exc:
            result['error'] = str(exc)
            result['rejected'] = True
            result['intended_reached'] = expected in str(exc)
        except (FileNotFoundError, ValueError) as exc:
            if not permits_missing_file:
                raise
            result['error'] = type(exc).__name__ + ': ' + str(exc)
            result['rejected'] = True
            missing = referenced_mesh(copied, 'KG1_A')
            result['intended_reached'] = not missing.exists() and missing.name in str(exc)
        results.append(result)
    baseline_after = verify.verify(source)
    preserved = original_hashes == payload_hashes(source)
    report = {
        'scope': 'STATIC_SEMANTIC_CONTROLS_NOT_ISAAC_OR_PHYSICAL_ACCEPTANCE',
        'attempt': attempt.relative_to(assets.ROOT).as_posix(),
        'positive_before': baseline_before,
        'controls': results,
        'expected_controls': EXPECTED_CONTROLS,
        'all_caught': len(results) == EXPECTED_CONTROLS and all(item['rejected'] and item['intended_reached'] for item in results),
        'positive_after': baseline_after,
        'canonical_model_preserved': preserved,
        'canonical_input_hashes': original_hashes,
    }
    require_report(report)
    assets.writej(attempt / 'report.json', report)
    assets.writej(assets.OUT / 'semantic-controls.json', report)
    print(json.dumps({key: report[key] for key in ['attempt', 'expected_controls', 'all_caught', 'canonical_model_preserved']}, indent=2))
    for result in results:
        print(json.dumps(result))
    assert preserved, 'canonical model changed during controls'
    assert report['all_caught'], 'some contradictory controls escaped the intended semantic check'


if __name__ == '__main__':
    main()
