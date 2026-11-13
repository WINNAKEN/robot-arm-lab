"""HOST tests use the authentic producer capture, plus isolated negative seams."""
import copy
import itertools
import json
import pathlib
import subprocess
import sys
import unittest
import uuid

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import audit

ROOT = pathlib.Path(__file__).resolve().parents[3]
AUTHOR = ROOT/audit.OUTPUT_ROOT/'author'


class ActualProducer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = audit.Producer(ROOT)
        cls.raw = cls.producer.raw[audit.ATTEMPT+'/retrieved/motion.ndjson']
        first_end = cls.raw.index(b'\n')
        cls.first = audit.parse(cls.raw[:first_end])
        cls.tail = cls.raw[first_end:]

    def bad_first(self, mutate, message):
        row = copy.deepcopy(self.first)
        mutate(row)
        raw = json.dumps(row, allow_nan=True).encode()+self.tail
        with self.assertRaisesRegex(ValueError, message):
            audit.parse_motion(raw)

    def test_authentic_capture_pins_and_original_runtime(self):
        self.assertEqual(audit.digest(self.producer.raw[audit.F6_PATH]), audit.F6_SHA)
        self.assertEqual(audit.digest(self.producer.raw[audit.ATTEMPT+'/native-result.json']), audit.NATIVE_SHA)
        self.assertTrue(self.producer.native['runtime_accepted'])
        audit.dump(AUTHOR/('baseline-capture-'+uuid.uuid4().hex+'.json'), self.producer.manifest)

    def test_real_producer_refuses_changed_canonical_hash(self):
        fixture = AUTHOR/'host-negative-captures'/uuid.uuid4().hex
        for relative in (audit.F6_PATH, audit.ATTEMPT+'/native-result.json'):
            path = fixture/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = self.producer.raw[relative]
            path.write_bytes(raw+(b'\n' if relative.endswith('native-result.json') else b''))
        with self.assertRaisesRegex(ValueError, 'SHA/bytes mismatch'):
            audit.Producer(fixture)

    def test_actual_document_run_owner_and_completeness_negatives(self):
        for file, key, value, message in (
                ('process.json', 'run_id', 'wrong', 'run/job'),
                ('process.json', 'child_pid', -1, 'SDK owner'),
                ('process.json', 'raw_complete', False, 'completeness'),
                ('report.json', 'completed_steps', 11159, 'complete rows')):
            docs = dict(self.producer.documents)
            docs[file] = copy.deepcopy(docs[file])
            docs[file][key] = value
            with self.assertRaisesRegex(ValueError, message):
                audit.validate_runtime(self.producer.native, docs)

    def test_body_duplicate_missing_nonfinite_and_quaternion_negatives(self):
        self.bad_first(lambda r: r['body_poses'].__setitem__(1, r['body_poses'][0]), 'Duplicate')
        self.bad_first(lambda r: r['body_poses'].pop(), 'body count')
        self.bad_first(lambda r: r['body_poses'][0]['position'].__setitem__(0, float('nan')), 'finite position')
        self.bad_first(lambda r: r['body_poses'][0].__setitem__('orientation_wxyz', [0, 0, 0, 0]), 'near unit')

    def test_actual_clock_and_duplicate_json_negatives(self):
        self.bad_first(lambda r: r['clock'].__setitem__('engine_time_s', .1), 'engine clock')
        self.bad_first(lambda r: r.__setitem__('time_s', .1), 'time/dt')
        self.bad_first(lambda r: r.__setitem__('step', 1), 'Contiguous')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            audit.parse(b'{"step":0,"step":1}')

    def test_actual_missing_last_row_rejected(self):
        raw = self.raw.rstrip(b'\r\n')
        without_last = raw[:raw.rfind(b'\n')+1]
        with self.assertRaisesRegex(ValueError, 'Missing final'):
            audit.parse_motion(without_last)

    def test_si_component_owner_and_approximation_negatives(self):
        static = copy.deepcopy(self.producer.documents['import-static.json'])
        static['units']['meters'] = .001
        with self.assertRaisesRegex(ValueError, 'SI units'):
            audit.build_envelopes(self.producer, static=static)
        scene = copy.deepcopy(self.producer.documents['manipulation-scene.json'])
        scene['jaw_component_overlay']['after_reset']['active_components'][0]['owner_path'] = '/wrong/body'
        with self.assertRaisesRegex(ValueError, 'owner/vertices/faces'):
            audit.build_envelopes(self.producer, scene=scene)
        scene = copy.deepcopy(self.producer.documents['manipulation-scene.json'])
        scene['collision_approximation'][0]['after'] = 'convexHull'
        with self.assertRaisesRegex(ValueError, 'KG1 after override'):
            audit.build_envelopes(self.producer, scene=scene)
        components = copy.deepcopy(audit.parse(self.producer.source(audit.COMPONENTS)))
        components['jaws']['KG1_A']['scale'] = [.001]*3
        with self.assertRaisesRegex(ValueError, 'source/SI/origin'):
            audit.build_envelopes(self.producer, components=components)

    def test_exact_registry_and_no_mount_or_joint_auto_exclusion(self):
        envelopes, adjacency = audit.build_envelopes(self.producer)
        registry = audit.pair_registry(envelopes, adjacency)
        self.assertEqual(len(registry['interbody']), 180)
        self.assertEqual(len(registry['same_owner_internal']), 30)
        self.assertEqual(registry['body_pair_count'], 55)
        self.assertTrue(any(p['direct_joints'] for p in registry['interbody']))
        self.assertTrue(all(not p['automatic_geometry_exclusion'] for p in registry['interbody']))
        kg1 = next(e for e in envelopes if e.meta['id'] == 'KG1')
        self.assertEqual(kg1.meta['final_authored_approximation'], 'convexDecomposition')
        self.assertEqual(kg1.meta['backend_cooked_shape_count'], 'UNKNOWN')

    def test_temporal_broadphase_seam_keeps_unchecked_false_positives_unknown(self):
        shape = audit.geo.hull(np.array(list(itertools.product((-1, 1), (-.05, .05), (-.05, .05)))))
        envelopes = [audit.Envelope(shape, {'id': name, 'owner': name}) for name in ('Base', 'Link1')]
        positions = np.zeros((11161, 11, 3))
        positions[:, 1, 0] = 10
        positions[100:105, 1] = [-.12/np.sqrt(2), .12/np.sqrt(2), 0]
        quaternions = np.zeros((11161, 11, 4))
        quaternions[:, :, 0] = np.cos(np.pi/8)
        quaternions[:, :, 3] = np.sin(np.pi/8)
        registry = {'interbody': [{'id': 'Base|Link1', 'indices': [0, 1], 'body_pair': 'Base|Link1'}]}
        broad, witnesses = audit.analyze(envelopes, registry, positions, quaternions)
        self.assertEqual(broad[0]['candidate_rows'], 5)
        self.assertEqual(broad[0]['candidate_intervals'][0]['first_step'], 100)
        self.assertEqual(broad[0]['candidate_intervals'][0]['last_step'], 104)
        self.assertEqual(broad[0]['unchecked_candidate_rows'], 4)
        self.assertEqual(broad[0]['category'], audit.geo.UNKNOWN)
        self.assertEqual(len(witnesses), 6)
        self.assertTrue(all(w['category'] == audit.geo.SEPARATION for w in witnesses))

    def test_output_boundary_and_existing_output_preservation(self):
        with self.assertRaisesRegex(ValueError, 'below the 134'):
            audit.run(ROOT, 'outputs/forbidden-134-test')
        existing = AUTHOR/'host-existing-output'/uuid.uuid4().hex
        existing.mkdir(parents=True)
        marker = existing/'marker.txt'
        marker.write_bytes(b'preserved')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            audit.run(ROOT, existing)
        self.assertEqual(marker.read_bytes(), b'preserved')

    def test_full_production_cli_actual_rows_to_report(self):
        relative = audit.OUTPUT_ROOT+'/author/host-baseline-'+uuid.uuid4().hex
        proc = subprocess.run([sys.executable, '-X', 'utf8', '-I', '-B', '-u', str(pathlib.Path(audit.__file__)),
                               '--output', relative], cwd=ROOT, capture_output=True, timeout=240)
        evidence = AUTHOR/('cli-raw-'+uuid.uuid4().hex+'.json')
        audit.dump(evidence, {'argv': proc.args, 'returncode': proc.returncode,
                             'stdout': proc.stdout.decode('utf-8'), 'stderr': proc.stderr.decode('utf-8'),
                             'output': relative})
        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8'))
        result = json.loads((ROOT/relative/'audit.json').read_text(encoding='utf-8'))
        self.assertIs(result['audit_completed'], True)
        self.assertEqual(result['motion']['rows'], 11161)
        self.assertEqual(result['interbody_source_envelope_pairs'], 180)
        self.assertEqual(result['body_pair_count'], 55)
        self.assertEqual(result['backend_cooked_shape_count'], 'UNKNOWN')
        broad = json.loads((ROOT/relative/'broadphase.json').read_text())
        self.assertEqual(sum(p['rows_checked'] for p in broad), 180*11161)
        self.assertTrue(all(len(p['narrowphase_samples']) <= 6 for p in broad))
        self.assertIs(result['source_envelope_collision_free'], False)
        self.assertGreater(result['unchecked_candidate_pair_rows'], 0)
        self.assertTrue((ROOT/relative/'audit.md').is_file())


class NativeOutputBoundary(unittest.TestCase):
    def test_f2_exact_old_cli_and_fixed_native_junction_admission(self):
        """All junctions, targets, clones and old writes stay in one author fixture."""
        evidence = AUTHOR/'f2-native-fixtures'/uuid.uuid4().hex
        base = evidence/'authenticated-input-clone'
        base.mkdir(parents=True)
        producer = audit.Producer(ROOT)
        audit.build_envelopes(producer)  # Capture every consumed original model mesh.
        for relative, raw in producer.raw.items():
            target = base/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
        source = pathlib.Path(audit.__file__).parent
        source_names = ('audit.py', 'geometry.py', 'test_audit.py', 'test_geometry.py')
        current_sources = {name: (source/name).read_bytes() for name in source_names}
        old_sources = {name: (AUTHOR/'before-F2/src/simulation/mp18_collision_audit_134'/name).read_bytes()
                       for name in source_names}
        old_source = old_sources['audit.py']
        self.assertEqual(audit.digest(old_source), 'd797b6328bc220fa54b74be4d8fa0bd0a1a73277aa02e8769e8f08fabcdd8694')
        records = []

        def fixture(name, old=False):
            project = evidence/name
            project.mkdir()
            for relative in producer.raw:
                target = project/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(producer.raw[relative])  # Independent copied bytes; original inputs stay untouched.
            for file_name, raw in current_sources.items():
                target = project/'src/simulation/mp18_collision_audit_134'/file_name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(old_sources[file_name] if old else raw)
            return project

        def link(project, relative):
            junction = project/relative
            target = project/'src/controlled-output-target'
            target.mkdir()
            if junction.exists():
                self.assertEqual(relative, 'outputs')
                preserved = project/'preserved-authenticated-outputs'
                self.assertTrue(junction.resolve().is_relative_to(evidence) and preserved.is_relative_to(evidence))
                junction.rename(preserved)  # Preserve the clone bytes before testing its parent alias.
            junction.parent.mkdir(parents=True, exist_ok=True)
            self.assertTrue(junction.is_relative_to(evidence) and target.is_relative_to(evidence))
            command = ['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(target)]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertTrue(junction.lstat().st_file_attributes & 1024)
            return junction, target, {'argv': command, 'returncode': result.returncode,
                 'stdout': result.stdout.decode(errors='replace'), 'stderr': result.stderr.decode(errors='replace')}

        def cli(project, output):
            command = [sys.executable, '-X', 'utf8', '-I', '-B', '-u',
                 str(project/'src/simulation/mp18_collision_audit_134/audit.py'), '--output', str(output)]
            result = subprocess.run(command, cwd=project, capture_output=True, timeout=240)
            return {'argv': command, 'returncode': result.returncode, 'stdout': result.stdout.decode('utf-8'),
                    'stderr': result.stderr.decode('utf-8')}

        old = fixture('exact-old-source-output-root', old=True)
        junction, target, creation = link(old, audit.OUTPUT_ROOT)
        record = cli(old, audit.OUTPUT_ROOT+'/old-unsafe-write')
        actual = target/'old-unsafe-write'
        record.update({'case': 'EXACT_OLD_SOURCE_NATIVE_JUNCTION', 'creation': creation,
                       'source_sha256': audit.digest(old_source), 'actual_write_under_fixture_src': True,
                       'artifacts': sorted(p.name for p in actual.iterdir()) if actual.exists() else []})
        records.append(record)
        audit.dump(evidence/'old-exact-result.json', record)
        self.assertEqual(record['returncode'], 0, record['stderr'])
        self.assertEqual(len(record['artifacts']), 8)
        self.assertTrue(json.loads((actual/'audit.json').read_text())['audit_completed'])

        for name, link_relative, output in (
                ('fixed-output-root', audit.OUTPUT_ROOT, audit.OUTPUT_ROOT+'/must-not-write'),
                ('fixed-outputs-parent', 'outputs', audit.OUTPUT_ROOT+'/must-not-write'),
                ('fixed-leaf-alias', audit.OUTPUT_ROOT+'/alias', audit.OUTPUT_ROOT+'/alias/must-not-write')):
            project = fixture(name)
            junction, target, creation = link(project, link_relative)
            record = cli(project, output)
            record.update({'case': name, 'creation': creation,
                           'source_sha256': audit.digest(current_sources['audit.py']),
                           'incorrect_result_files': sorted(str(p.relative_to(target)) for p in target.rglob('*') if p.is_file())})
            records.append(record)
            self.assertEqual(record['returncode'], 1, record)
            self.assertIn('Reparse or symbolic-link', record['stderr'])
            self.assertEqual(record['incorrect_result_files'], [])
            # Direct resolved-target aliases cannot grant authority either.
            direct = cli(project, target/'direct-alias')
            direct['case'] = name+'-resolved-target-alias'
            records.append(direct)
            self.assertEqual(direct['returncode'], 1)
            self.assertIn('below the 134', direct['stderr'])
        project = fixture('fixed-lexical-escape')
        escape = cli(project, audit.OUTPUT_ROOT+'/../../src/lexical-escape')
        escape['case'] = 'fixed-lexical-escape'
        records.append(escape)
        self.assertEqual(escape['returncode'], 1)
        self.assertFalse((project/'src/lexical-escape').exists())
        for relative, pin in producer.manifest.items():
            self.assertEqual(audit.digest((ROOT/relative).read_bytes()), pin['sha256'])
        for name, raw in current_sources.items():
            self.assertEqual((source/name).read_bytes(), raw)
        audit.dump(evidence/'native-boundary-results.json', {'records': records,
             'original_input_and_source_mutations': 0, 'mocked_product_functions': 0,
             'exact_old_source_artifacts': 8, 'fixed_unauthorized_artifacts': 0,
             'all_junctions_targets_and_old_writes_within_this_author_fixture': True})


if __name__ == '__main__':
    unittest.main(verbosity=2)
