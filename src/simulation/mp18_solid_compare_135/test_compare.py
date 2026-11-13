"""HOST real input census/pose controls and owned-clone publication boundaries."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import unittest
import uuid
from unittest import mock

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).absolute().parent))
import compare
import solids

ROOT = pathlib.Path(__file__).absolute().parents[3]
AUTHOR = ROOT/'outputs/mp18-solid-compare-135/author'
FIXTURE = AUTHOR/('host-fixtures-'+uuid.uuid4().hex)
FIXTURE.mkdir(parents=True, exist_ok=False)


def clone_code(label):
    root = FIXTURE/label
    own = root/'src/simulation/mp18_solid_compare_135'
    own.mkdir(parents=True)
    for name in ('compare.py', 'solids.py', 'test_compare.py', 'test_solids.py'):
        shutil.copyfile(pathlib.Path(__file__).parent/name, own/name)
    (root/compare.PLAN).parent.mkdir(parents=True)
    shutil.copyfile(ROOT/compare.PLAN, root/compare.PLAN)
    return root


def junction(path, target):
    # Creation only, in a verified owned fixture. No shell filesystem deletion.
    assert path.absolute().is_relative_to(FIXTURE.absolute())
    assert target.absolute().is_relative_to(FIXTURE.absolute())
    target.mkdir(parents=True, exist_ok=True)
    command = "New-Item -ItemType Junction -Path '"+str(path).replace("'", "''")+"' -Target '"+str(target).replace("'", "''")+"' | Out-Null"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Native junction fixture creation failed: '+result.stderr)


def cli(root, name='case'):
    return subprocess.run([sys.executable, '-X', 'utf8', '-I', '-B', '-u',
                           str(root/'src/simulation/mp18_solid_compare_135/compare.py'), '--name', name],
                          capture_output=True, text=True, timeout=30)


class ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = compare.Producer(ROOT)
        cls.parts, cls.partitions = compare.partition_originals(cls.producer)
        cls.mappings = compare.map_envelopes(cls.producer, cls.parts)
        cls.cases = compare.select_cases(cls.producer)

    def test_real_partition_mapping_selection_and_exact_pose_positive_path(self):
        self.assertEqual(len(self.parts), 274)
        self.assertEqual(len(self.partitions), 11)
        self.assertTrue(all(p['solid'].evidence['valid'] for p in self.parts.values()))
        self.assertEqual(sum(bool(p['record']['collision_included']) for p in self.parts.values()), 244)
        self.assertEqual(len(self.cases), 91)
        self.assertEqual(len({c['pair_id'] for c in self.cases}), 18)
        self.assertEqual(self.mappings['KG1_A:03']['part_ids'], ['KG1:PAD_A_HEAD_1'])
        self.assertEqual(self.mappings['KG1_A:04']['part_ids'], ['KG1:PAD_A_SHANK_0'])
        self.assertTrue(all(m.get('bilateral_cloud_error_m', 0) == 0 for m in self.mappings.values()))
        # A real source-pair sample traverses actual producer, partition, mapping, Boolean and report.
        results, counts = compare.evaluate_cases(self.cases[:1], self.mappings, self.parts, progress=False)
        self.assertTrue(results[0]['part_cross_product_complete'])
        self.assertGreater(counts['actual_boolean_calls'], 0)
        report = compare.render_report({'selected_processing_complete': False,
                                        'part_pair_categories': results[0]['category_counts']}, results)
        self.assertIn(results[0]['pair_id'], report)
        self.assertIn('UNKNOWN', report)

    def test_hash_gate_and_duplicate_json_reject(self):
        bad = object.__new__(compare.Producer)
        bad.root, bad.raw, bad.manifest = ROOT, {}, {}
        with self.assertRaisesRegex(ValueError, 'SHA/bytes'):
            bad.read(compare.F6, '0'*64)
        with self.assertRaises(ValueError): compare.parse(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError): compare.parse(b'{"x":NaN}')
        for relative in ('../outside', '/outside', ROOT.drive+'/outside', 'a\\b'):
            with self.subTest(relative=relative), self.assertRaises(ValueError): bad.read(relative, '0'*64)

    def test_actual_run_job_acceptance_and_source_freeze_identity_fail_closed(self):
        original = compare.parse(self.producer.raw[compare.NATIVE])
        compare.validate_native(original)
        for key, value in [('run_id', 'another-run'), ('job_sha256', '0'*64), ('unit', 134),
                           ('source_freeze_sha256', '0'*64), ('runtime_accepted', False), ('SDK_reaped', False),
                           ('hardware_approved', True), ('terminal_status', 'FAILED')]:
            mutated = copy.deepcopy(original)
            mutated[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): compare.validate_native(mutated)

    def test_part_missing_face_count_and_source_order_fail(self):
        for mutation in ('missing', 'faces', 'order', 'SI'):
            with self.subTest(mutation=mutation):
                producer = copy.copy(self.producer)
                producer.ledger = copy.deepcopy(self.producer.ledger)
                rows = producer.ledger['geometry_components']
                if mutation == 'missing': rows.pop()
                elif mutation == 'faces': rows[0]['triangles'] += 1
                elif mutation == 'order': rows[0], rows[1] = rows[1], rows[0]
                else: rows[0]['scale_to_m'] = 1.
                with self.assertRaises(ValueError): compare.partition_originals(producer)

    def test_jaw_ordinal_reordering_still_maps_by_cloud_and_bad_local_face_fails(self):
        producer = copy.copy(self.producer)
        producer.jaws = copy.deepcopy(self.producer.jaws)
        producer.jaws['jaws']['KG1_A']['components'].reverse()
        self.assertEqual(compare.map_envelopes(producer, self.parts), self.mappings)
        producer.jaws['jaws']['KG1_A']['components'][0]['triangle_indices'][0][0] = 999999
        with self.assertRaises(ValueError): compare.map_envelopes(producer, self.parts)

    def test_91_selection_and_actual_pose_mismatch_fail(self):
        for mutation in ('missing_case', 'pose', 'time', 'pair'):
            producer = copy.copy(self.producer)
            producer.witnesses = copy.deepcopy(self.producer.witnesses)
            row = next(w for w in producer.witnesses if w['category'] == compare.POSITIVE_134)
            if mutation == 'missing_case': row['category'] = 'UNKNOWN_OR_UNCHECKED'
            elif mutation == 'pose': row['poses'][0]['position_m'][0] += .001
            elif mutation == 'time': row['time_s'] += .1
            else: row['pair_id'] = 'missing-owner-pair'
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                compare.select_cases(producer)

    def test_cross_product_counts_cache_and_invalid_input_unknown(self):
        case = self.cases[0]
        results, counts = compare.evaluate_cases([case, copy.deepcopy(case)], self.mappings, self.parts, progress=False)
        expected = len(results[0]['part_ids_a'])*len(results[0]['part_ids_b'])
        self.assertEqual(counts['reported_part_pairs'], 2*expected)
        self.assertEqual(counts['reused_exact_part_pose_pairs'], expected)
        self.assertEqual(results[0]['evaluated_part_pairs'], expected)
        self.assertTrue(all(p['reused_exact_owner_step_part_pair'] for p in results[1]['pairs']))


class BoundaryTests(unittest.TestCase):
    def test_normal_exclusive_leaf_and_slug_escape_reject(self):
        root = clone_code('normal')
        for name in ('../escape', '.', '', 'x/y', 'x\\y', '/tmp', 'x:stream', 'x.', 'x '):
            with self.subTest(name=name), self.assertRaises(ValueError): compare.output_destination(root, name, create=True)
        path = compare.output_destination(root, 'safe', create=True)
        self.assertEqual(path, root/'outputs/mp18-solid-compare-135/safe')
        with self.assertRaises(FileExistsError): compare.output_destination(root, 'safe', create=True)
        # Unrelated mutable module state cannot change the authority.
        with mock.patch.object(compare, 'OUTPUT_ROOT', str(FIXTURE/'outside'), create=True):
            self.assertEqual(compare.output_destination(root, 'second'), root/'outputs/mp18-solid-compare-135/second')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows reparse evidence requires Windows')
    def test_real_cli_native_root_parent_leaf_and_repo_alias_reject(self):
        results = []
        for mode in ('output-root', 'outputs-parent', 'leaf', 'repo-alias'):
            root = clone_code('native-'+mode)
            outside = FIXTURE/('outside-'+mode)
            name = 'case'
            if mode == 'outputs-parent':
                junction(root/'outputs', outside)
            elif mode == 'repo-alias':
                alias = FIXTURE/'repo-alias'
                junction(alias, root)
                root = alias
            else:
                (root/'outputs').mkdir()
                if mode == 'output-root': junction(root/'outputs/mp18-solid-compare-135', outside)
                else:
                    (root/'outputs/mp18-solid-compare-135').mkdir()
                    junction(root/'outputs/mp18-solid-compare-135'/name, outside)
            proc = cli(root, name)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('Native reparse/symlink', proc.stderr)
            self.assertFalse(any(outside.rglob('comparison.json')) if outside.exists() else False)
            results.append({'mode': mode, 'exit': proc.returncode, 'blocked_reparse': True,
                            'stdout': proc.stdout, 'stderr': proc.stderr})
        (FIXTURE/'native-boundaries.json').write_text(json.dumps(results, indent=2), encoding='utf-8')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows reparse evidence requires Windows')
    def test_exact_vulnerable_resolved_authority_mutant_escapes_owned_clone(self):
        root = clone_code('authority-mutant')
        outside = FIXTURE/'mutant-outside'
        (root/'outputs').mkdir()
        junction(root/'outputs/mp18-solid-compare-135', outside)
        source = root/'src/simulation/mp18_solid_compare_135/compare.py'
        text = source.read_text(encoding='utf-8')
        indent = '    ' if '\n    def output_destination(' in text else ''
        start, stop = text.index(indent+'def output_destination('), text.index('\n\n'+indent+'class Producer:')
        mutant = '''def output_destination(root, name, create=False):
    # Exact former authority error: derive allowed authority by resolving its own alias.
    allowed = (pathlib.Path(root)/'outputs/mp18-solid-compare-135').resolve()
    destination = (allowed/name).resolve()
    solids.require(destination.is_relative_to(allowed) and destination != allowed, 'boundary')
    if create:
        allowed.mkdir(parents=True, exist_ok=True)
        destination.mkdir(exist_ok=False)
    return destination
'''
        mutant = '\n'.join(indent+line if line else '' for line in mutant.splitlines())+'\n'
        source.write_text(text[:start]+mutant+text[stop:], encoding='utf-8')
        proc = cli(root, 'escaped-before-input')
        # The small fixture deliberately has no F6. The escaped write occurs BEFORE producer authentication.
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue((outside/'escaped-before-input').is_dir())
        self.assertNotIn('Native reparse/symlink', proc.stderr)
        (FIXTURE/'exact-authority-mutant.json').write_text(json.dumps({'escaped_directory_observed': True,
            'producer_authentication_intentionally_unavailable': True, 'exit': proc.returncode,
            'stdout': proc.stdout, 'stderr': proc.stderr}, indent=2), encoding='utf-8')

    def test_early_consumed_source_cli_and_bootstrap_capture_gap_fail_closed(self):
        """Same real-CLI timing as L4 F1, plus capture-to-compile gaps for both executed modules."""
        evidence = []
        inputs = json.loads((ROOT/'outputs/mp18-solid-compare-135/author-baseline-r2/input-manifest.json').read_text())
        for mode in ('after-leaf-solids', 'before-snapshot-exec-solids', 'before-snapshot-exec-compare', 'before-first-read-compare'):
            root = clone_code('early-source-'+mode)
            for relative, expected in inputs.items():
                target = root/relative
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT/relative, target)  # authentic inputs; source135 files are separate copies
            name = 'early-source-case'
            destination = root/'outputs/mp18-solid-compare-135'/name
            relative = 'src/simulation/mp18_solid_compare_135/'+('compare.py' if mode.endswith('-compare') else 'solids.py')
            source = root/relative
            original = source.read_bytes()
            log_path = root/'early-source-cli.log'
            command = [sys.executable, '-X', 'utf8', '-I', '-B', '-u',
                       str(root/'src/simulation/mp18_solid_compare_135/compare.py'), '--name', name]
            shim = None
            if mode.startswith('before-'):
                # Auditing compile observes the second compare compile, AFTER the bundle was
                # captured and BEFORE it is executed. A live sibling import would execute the
                # injected raise; the correct path executes captured bytes and rejects drift.
                shim = root/'bootstrap-gap-probe.py'
                shim.write_text('''import pathlib,runpy,sys
entry=pathlib.Path(sys.argv[1]);target=pathlib.Path(sys.argv[2]);label=sys.argv[3];mode=sys.argv[4]
original=target.read_bytes();seen=0
def mutate():
 if target.name == 'compare.py':
  return original.replace(b'from __future__ import annotations\\n',b'from __future__ import annotations\\nraise RuntimeError("F1_MUTATION_WOULD_ABORT_IF_EXECUTED")\\n',1)
 return original+b'\\nSMALL_MM3 = 1000000.0\\nraise RuntimeError("F1_MUTATION_WOULD_ABORT_IF_EXECUTED")\\n'
def audit(event,args):
 global seen
 if event == 'compile' and pathlib.Path(str(args[1])) == entry:
  seen += 1
  if seen == (1 if mode == 'before-first-read-compare' else 2):
   target.write_bytes(mutate())
sys.addaudithook(audit)
sys.argv=[str(entry),'--name',label]
runpy.run_path(str(entry),run_name='__main__')
''', encoding='utf-8')
                command = [sys.executable, '-X', 'utf8', '-I', '-B', '-u', str(shim),
                           str(root/'src/simulation/mp18_solid_compare_135/compare.py'), str(source), name, mode]
            started = time.monotonic()
            with log_path.open('w', encoding='utf-8') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=root)
                if mode == 'after-leaf-solids':
                    while not destination.exists() and process.poll() is None and time.monotonic()-started < 20:
                        time.sleep(.001)
                    self.assertTrue(destination.is_dir(), 'Real CLI must reach the same post-import leaf seam')
                    source.write_bytes(original+b'\nSMALL_MM3 = 1000000.0\nraise RuntimeError("F1_MUTATION_WOULD_ABORT_IF_EXECUTED")\n')
                code = process.wait(timeout=90)
            log = log_path.read_text(encoding='utf-8')
            self.assertNotEqual(source.read_bytes(), original)
            self.assertNotEqual(code, 0)
            self.assertFalse((destination/'comparison.json').exists())
            if mode == 'before-first-read-compare':
                # The interpreter had already read the outer bootstrap. Its fresh
                # captured compare bytes MUST be re-executed, including this raise.
                self.assertIn('RuntimeError: F1_MUTATION_WOULD_ABORT_IF_EXECUTED', log)
            else:
                self.assertIn('135 captured source changed:', log)
                self.assertNotIn('RuntimeError: F1_MUTATION_WOULD_ABORT_IF_EXECUTED', log)
            evidence.append({'mode': mode, 'returncode': code, 'comparison_completion_exists': False,
                             'source_was_mutated': True, 'expected_execution_binding_observed': True,
                             'elapsed_s': time.monotonic()-started, 'log': str(log_path.relative_to(FIXTURE)),
                             'before_sha256': compare.digest(original), 'after_sha256': compare.digest(source.read_bytes())})
        (FIXTURE/'early-consumed-source-results.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')


class PublicationTests(unittest.TestCase):
    """Small owned clones isolate publication failures; full producer is tested above."""
    def fixture_run(self, label, callback=None, fail_filename=None, recheck_callback=None):
        root = clone_code('publication-'+label)
        sentinel = root/'sentinel.bin'
        sentinel.write_bytes(b'authenticated input')
        expected = compare.digest(sentinel.read_bytes())
        real_recheck = compare.Producer.recheck
        class FixtureProducer:
            def __init__(self, root):
                self.root = root
                self.manifest = {compare.PLAN: {'sha256': compare.PLAN_SHA, 'bytes': (root/compare.PLAN).stat().st_size},
                                 'sentinel.bin': {'sha256': expected, 'bytes': len(b'authenticated input')}}
                self.provenance = {'input_census': {}}
                self.rechecks = 0
            def recheck(self):
                self.rechecks += 1
                if recheck_callback is not None:
                    recheck_callback(root, self.rechecks)
                real_recheck(self)
        original_open = pathlib.Path.open
        def checked_open(path, mode='r', *args, **kwargs):
            if fail_filename is not None and path.name == fail_filename and mode == 'xb':
                raise OSError('injected artifact publication failure')
            return original_open(path, mode, *args, **kwargs)
        def before(producer, destination):
            if callback is not None:
                callback(root, producer, destination)
        destination = root/'outputs/mp18-solid-compare-135/case'
        counts = {'actual_boolean_calls': 0, 'unique_evaluated_part_pose_pairs': 0,
                  'reported_part_pairs': 0, 'reused_exact_part_pose_pairs': 0}
        with mock.patch.object(compare, 'Producer', FixtureProducer), \
             mock.patch.object(compare, 'partition_originals', return_value=({}, [])), \
             mock.patch.object(compare, 'map_envelopes', return_value={}), \
             mock.patch.object(compare, 'select_cases', return_value=[]), \
             mock.patch.object(compare, 'evaluate_cases', return_value=([], counts)), \
             mock.patch.object(pathlib.Path, 'open', checked_open):
            if callback is None and fail_filename is None and recheck_callback is None:
                result, actual = compare.run('case', root=root, before_publish=before)
                self.assertEqual(actual, destination)
                self.assertTrue((actual/'comparison.json').is_file())
                self.assertFalse(result['selected_processing_complete'])
                self.assertEqual(set(result['artifacts']), {'original-parts.json', 'envelope-parts.json', 'cases.json',
                                                          'input-manifest.json', 'source-manifest.json', 'comparison.md'})
            else:
                with self.assertRaises((ValueError, OSError)):
                    compare.run('case', root=root, before_publish=before)
                self.assertFalse((destination/'comparison.json').exists())
        return root

    def test_normal_publication_completion_json_is_last(self):
        self.fixture_run('normal')

    def test_mutated_input_or_source_has_no_completion_record(self):
        self.fixture_run('input-change', callback=lambda r, p, d: (r/'sentinel.bin').write_bytes(b'changed'))
        self.fixture_run('source-change', callback=lambda r, p, d: (r/'src/simulation/mp18_solid_compare_135/solids.py').write_bytes(b'changed'))

    def test_mid_publication_failure_has_no_completion_record(self):
        root = self.fixture_run('artifact-failure', fail_filename='cases.json')
        self.assertTrue((root/'outputs/mp18-solid-compare-135/case/original-parts.json').is_file())

    def test_late_source_change_is_caught_after_artifacts_before_completion(self):
        def change(root, rechecks):
            if rechecks == 2:
                (root/'src/simulation/mp18_solid_compare_135/solids.py').write_bytes(b'late source change')
        self.fixture_run('late-source-change', recheck_callback=change)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows reparse evidence requires Windows')
    def test_late_native_output_root_transition_has_no_completion_record(self):
        def swap(root, producer, destination):
            old = destination.parent
            saved = root/'saved-owned-output'
            assert old.resolve().is_relative_to(FIXTURE.resolve()) and saved.absolute().is_relative_to(FIXTURE.absolute())
            old.rename(saved)
            junction(old, FIXTURE/'late-native-outside')
        self.fixture_run('late-native-transition', callback=swap)


if __name__ == '__main__':
    unittest.main(verbosity=2)
