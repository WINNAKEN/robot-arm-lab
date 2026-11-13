"""Meaningful offline draft checks: semantic rejection and missing-core start failure."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from verify import verify

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'models/robot-arm-urdf-v1'
EXPORT = ROOT / '.dev/urdf-draft-evidence/preflight/v2-current.3mf'


class DraftTests(unittest.TestCase):
    def test_positive_and_semantic_corruptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'package'
            shutil.copytree(PACKAGE, out)
            baseline = (out / 'robot_arm.urdf').read_bytes()
            self.assertEqual(verify(out, ROOT, EXPORT)['fk_poses'], 16)
            def axis(robot):
                robot.find('joint/axis').set('xyz', '1 0 0')
            def unit(robot):
                robot.find('link/visual/geometry/mesh').set('scale', '1000 1000 1000')
            def parent(robot):
                robot.find('joint/parent').set('link', 'Link6')
            def mass(robot):
                robot.find('link/inertial/mass').set('value', '0')
            def path(robot):
                robot.find('link/visual/geometry/mesh').set('filename', '../escape.stl')
            def inertia(robot):
                robot.find('link/inertial/inertia').set('ixx', '-1')
            for mutate, message in [(axis, 'FK mismatch'), (unit, 'metre scale'), (parent, 'chain'),
                                     (mass, 'mass mismatch'), (path, 'mesh path'), (inertia, 'Inertia positive')]:
                with self.subTest(mutation=mutate.__name__):
                    robot = ET.fromstring(baseline)
                    mutate(robot)
                    ET.ElementTree(robot).write(out / 'robot_arm.urdf', encoding='utf-8', xml_declaration=True)
                    with self.assertRaisesRegex(ValueError, message):
                        verify(out, ROOT, EXPORT)
            (out / 'robot_arm.urdf').write_bytes(baseline)
            self.assertEqual(verify(out, ROOT, EXPORT)['visual_bodies'], 31)
            print('PASS semantic controls6 rejected at intended checks; original before/after passes')

    def test_resealed_frame_and_inertia_basis_corruptions(self):
        # Re-seal file digests so semantic checks, not stale checksums, must reject.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'package'
            shutil.copytree(PACKAGE, out)
            originals = {name: (out / name).read_bytes() for name in
                         ('robot_arm.urdf', 'assumptions.json', 'manifest.json')}
            self.assertEqual(verify(out, ROOT, EXPORT)['physical_links'], 7)
            def inertial_rotation(robot, cfg):
                robot.find("link[@name='Link2']/inertial/origin").set('rpy', '0.4 0.3 0.2')
            def collision_rotation(robot, cfg):
                robot.find("link[@name='Link2']/collision/origin").set('rpy', '0.4 0.3 0.2')
            def box_basis(robot, cfg):
                row = cfg['links'][2]
                row['box_size_m'] = [1., 1., 1.]
                row['inertia_kg_m2'] = [cfg['mass_kg'][2]/6]*3
                tensor = robot.find("link[@name='Link2']/inertial/inertia")
                for key, value in zip(('ixx', 'iyy', 'izz'), row['inertia_kg_m2']):
                    tensor.set(key, str(value))
            def recorded_com(robot, cfg):
                cfg['links'][2]['com_m'][0] += 0.1
            def recorded_mass(robot, cfg):
                cfg['links'][2]['mass_kg'] = 10.
            def recorded_inertia(robot, cfg):
                cfg['links'][2]['inertia_kg_m2'] = [1., 1., 1.]
            def recorded_identity(robot, cfg):
                cfg['links'][2]['link'] = 'Link3'
            cases = [(inertial_rotation, 'Inertia local AABB rotation'),
                     (collision_rotation, 'Collision local AABB rotation'),
                     (box_basis, 'Recorded box differs from actual STL'),
                     (recorded_com, 'Recorded COM differs from actual STL'),
                     (recorded_mass, 'Recorded mass mismatch'),
                     (recorded_inertia, 'Recorded inertia mismatch'),
                     (recorded_identity, 'Recorded link identity/status')]
            for mutate, message in cases:
                with self.subTest(mutation=mutate.__name__):
                    for name, data in originals.items():
                        (out / name).write_bytes(data)
                    robot = ET.fromstring(originals['robot_arm.urdf'])
                    cfg = json.loads(originals['assumptions.json'])
                    mutate(robot, cfg)
                    ET.ElementTree(robot).write(out / 'robot_arm.urdf', encoding='utf-8', xml_declaration=True)
                    (out / 'assumptions.json').write_text(json.dumps(cfg), encoding='utf-8')
                    manifest = json.loads(originals['manifest.json'])
                    for name in manifest['files']:
                        manifest['files'][name] = hashlib.sha256((out / name).read_bytes()).hexdigest()
                    (out / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, message):
                        verify(out, ROOT, EXPORT)
            for name, data in originals.items():
                (out / name).write_bytes(data)
            self.assertEqual(verify(out, ROOT, EXPORT)['visual_bodies'], 31)
            print('PASS resealed semantic controls7 rejected; actual-STL basis/origins/sidecar; original before/after passes')

    def test_missing_core_records_failed_before_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft', 'models/armold-mks-concept-v1/kinematics.json'):
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            p = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('build.py')), '--root', str(root), '--export', str(EXPORT)], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(p.returncode, 0)
            status = json.loads((root / '.dev/urdf-draft-evidence/build-status.json').read_text())
            self.assertEqual(status['status'], 'FAILED')
            self.assertIn('frames.py', status['reason'])
            self.assertFalse((root / 'models/robot-arm-urdf-v1').exists())
            print('PASS missing-core startup exits nonzero / FAILED / no package')


if __name__ == '__main__':
    unittest.main()
