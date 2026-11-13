"""Meaningful HOST controls, including the actual spliced native function; SDK=0."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
import uuid

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B = load('builder124_host', HERE / 'build_candidate.py')
RESET = load('reset124_host', HERE / 'stage_reset.py')
original = B.BASE.read_bytes()
candidate, proof = B.candidate_bytes(original, (HERE / 'stage_reset.py').read_bytes())
SPLICED = types.ModuleType('actual_spliced_native124_HOST_ONLY')
SPLICED.__file__ = str(B.OUT / 'HOST_ONLY_native.py')
exec(compile(candidate, SPLICED.__file__, 'exec'), SPLICED.__dict__)
FUNCTIONS = (RESET.fresh_stage, SPLICED.fresh_stage)


class Prim:
    def __init__(self, path, kind='Xform', schemas=()):
        self.path, self.kind, self.schemas = path, kind, schemas

    def GetPath(self): return self.path
    def GetTypeName(self): return self.kind
    def GetAppliedSchemas(self): return list(self.schemas)


class Layer:
    def __init__(self, identifier, prims=(), default=None, anonymous=True):
        self.identifier, self.anonymous = identifier, anonymous
        self.prims, self.default = list(prims), default
        self.sublayers, self.calls, self.on_clear = [], 0, None
        self.failure = None
        self.noop = False

    @property
    def empty(self): return not self.prims and self.default is None and not self.sublayers

    def ExportToString(self):
        return json.dumps({'prims': [(p.path, p.kind, p.schemas) for p in self.prims],
                           'default': self.default, 'sublayers': [s.identifier for s in self.sublayers]})

    def Clear(self):
        self.calls += 1
        if self.failure:
            raise self.failure
        if not self.noop:
            self.prims, self.default, self.sublayers = [], None, []
        if self.on_clear:
            self.on_clear()


class Stage:
    def __init__(self, name, prims=(), default=None):
        self.root = Layer('anon:' + name + ':root', prims, default)
        self.session = Layer('anon:' + name + ':session')
        self.extra_prims, self.used, self.extra_default = [], [], None
        self.census_error = None

    def GetRootLayer(self): return self.root
    def GetSessionLayer(self): return self.session
    def GetLayerStack(self): return [self.session, self.root] + self.session.sublayers + self.root.sublayers
    def GetUsedLayers(self): return self.GetLayerStack() + self.used

    def GetDefaultPrim(self):
        name = self.extra_default or self.session.default or self.root.default
        return Prim(name) if name else None

    def TraverseAll(self):
        if self.census_error:
            raise self.census_error
        return [p for layer in self.GetLayerStack() for p in layer.prims] + self.extra_prims


class Context:
    def __init__(self, old, new):
        self.stage, self.new, self.new_calls, self.result = old, new, 0, True

    def get_stage(self): return self.stage

    def new_stage(self):
        self.new_calls += 1
        self.stage = self.new
        return self.result


class Harness:
    def __init__(self, times=()):
        self.old = Stage('old', [Prim('/OldRobot', schemas=['PhysicsArticulationRootAPI'])], '/OldRobot')
        self.new = Stage('new', [Prim('/World')], '/World')
        self.new.session.prims = [Prim('/OmniverseKit_Persp', 'Camera')]
        self.context = Context(self.old, self.new)
        self.rows, self.write_failure = [], None
        self.times = iter(times)
        self.ctx = types.SimpleNamespace(run=Path('HOST_ONLY'), write=self.write)

    def write(self, path, value):
        json.dumps(value, allow_nan=False)
        if self.write_failure:
            error = self.write_failure(value)
            if error:
                raise error
        self.rows.append(copy.deepcopy(value))

    def clock(self): return next(self.times, 0.)
    def call(self, function): return function(self.ctx, self.context, self.clock)


class ResetTests(unittest.TestCase):
    def test_default_world_and_session_camera_are_removed_without_touching_old(self):
        for function in FUNCTIONS:
            h = Harness()
            old = [layer.ExportToString() for layer in (h.old.root, h.old.session)]
            self.assertIs(h.call(function), h.new)
            self.assertEqual([layer.ExportToString() for layer in (h.old.root, h.old.session)], old)
            self.assertEqual(h.old.root.calls + h.old.session.calls, 0)
            self.assertEqual(h.rows[-1]['after']['prims'], [])
            self.assertTrue(h.rows[-1]['verified'])
            initial = next(row for row in h.rows if row['after_new'])
            self.assertEqual({p['path'] for p in initial['after_new']['prims']}, {'/World', '/OmniverseKit_Persp'})
            self.assertEqual(initial['cleared_layers'], [])

    def test_already_empty_stage_and_absent_old_stage(self):
        for function in FUNCTIONS:
            h = Harness()
            h.context.stage = None
            h.new.root.prims, h.new.root.default, h.new.session.prims = [], None, []
            self.assertIs(h.call(function), h.new)
            self.assertEqual(h.rows[-1]['old_layers_after_reset'], {})

    def test_reused_root_or_session_is_rejected_before_any_clear(self):
        for function in FUNCTIONS:
            for field in ('root', 'session'):
                with self.subTest(implementation=function.__module__, field=field):
                    h = Harness()
                    setattr(h.new, field, getattr(h.old, field))
                    with self.assertRaisesRegex(ValueError, 'share any old'):
                        h.call(function)
                    self.assertEqual(sum(layer.calls for layer in (h.old.root, h.old.session, h.new.root, h.new.session)), 0)
                    self.assertFalse(h.rows[-1]['verified'])

    def test_old_referenced_layer_alias_is_also_rejected(self):
        for function in FUNCTIONS:
            h = Harness()
            h.old.used.append(h.new.session)
            with self.assertRaisesRegex(ValueError, 'share any old'):
                h.call(function)
            self.assertEqual(h.new.root.calls + h.new.session.calls, 0)

    def test_file_backed_or_identical_new_layers_are_never_cleared(self):
        for function in FUNCTIONS:
            for field in ('root', 'session', 'same'):
                h = Harness()
                if field == 'same': h.new.session = h.new.root
                else: getattr(h.new, field).anonymous = False
                with self.assertRaisesRegex(ValueError, 'distinct anonymous'):
                    h.call(function)
                self.assertEqual(h.new.root.calls + h.new.session.calls, 0)

    def test_positive_or_nonfinite_before_clock_prevents_new_stage(self):
        for function in FUNCTIONS:
            for value in (.01, -.01, float('nan'), float('inf'), -float('inf')):
                h = Harness([value])
                with self.assertRaisesRegex(ValueError, 'Zero engine clock before fresh'):
                    h.call(function)
                self.assertEqual(h.context.new_calls, 0)
                self.assertFalse(h.rows[-1]['verified'])
                json.dumps(h.rows[-1], allow_nan=False)

    def test_nonzero_after_new_prevents_clear_and_preserves_census(self):
        for function in FUNCTIONS:
            for value in (.01, float('nan')):
                h = Harness([0., value])
                with self.assertRaisesRegex(ValueError, 'after stage creation'):
                    h.call(function)
                self.assertEqual(h.new.root.calls + h.new.session.calls, 0)
                self.assertIsNotNone(h.rows[-1]['after_new'])

    def test_mid_clear_clock_prevents_next_mutation(self):
        for function in FUNCTIONS:
            h = Harness([0., 0., 0., .1])
            with self.assertRaisesRegex(ValueError, 'before Clear'):
                h.call(function)
            self.assertEqual((h.new.root.calls, h.new.session.calls), (1, 0))

    def test_postclear_clock_rejects_acceptance(self):
        for function in FUNCTIONS:
            h = Harness([0., 0., 0., 0., .1])
            with self.assertRaisesRegex(ValueError, 'preserves zero'):
                h.call(function)
            self.assertFalse(h.rows[-1]['verified'])

    def test_context_switch_cannot_clear_foreign_session(self):
        for function in FUNCTIONS:
            h = Harness()
            foreign = Stage('foreign', [Prim('/Foreign')])
            h.new.root.on_clear = lambda: setattr(h.context, 'stage', foreign)
            with self.assertRaisesRegex(ValueError, 'remain current before Clear'):
                h.call(function)
            self.assertEqual((h.new.session.calls, foreign.root.calls, foreign.session.calls), (0, 0, 0))

    def test_failed_clear_is_not_promoted_to_pass(self):
        for function in FUNCTIONS:
            h = Harness()
            h.new.root.failure = RuntimeError('PRIMARY_CLEAR_FAILURE')
            with self.assertRaisesRegex(RuntimeError, 'PRIMARY_CLEAR_FAILURE'):
                h.call(function)
            self.assertIn('PRIMARY_CLEAR_FAILURE', h.rows[-1]['error'])
            self.assertIsNotNone(h.rows[-1]['failure_census'])
            self.assertEqual(h.new.session.calls, 0)

    def test_noop_clear_and_hidden_inactive_residue_are_rejected(self):
        for function in FUNCTIONS:
            for mode in ('noop', 'hidden', 'default', 'oldlayer'):
                h = Harness()
                if mode == 'noop': h.new.root.noop = True
                elif mode == 'hidden': h.new.extra_prims.append(Prim('/HiddenInactive', schemas=['PhysicsRigidBodyAPI']))
                elif mode == 'default': h.new.extra_default = '/GhostDefault'
                else: h.new.used.append(h.old.root)
                with self.assertRaises(ValueError):
                    h.call(function)
                self.assertFalse(h.rows[-1]['verified'])

    def test_old_layer_modification_by_callback_is_detected(self):
        for function in FUNCTIONS:
            h = Harness()
            h.new.root.on_clear = lambda: h.old.root.prims.append(Prim('/UnexpectedMutation'))
            with self.assertRaisesRegex(ValueError, 'remain unchanged'):
                h.call(function)
            self.assertEqual(h.old.root.calls + h.old.session.calls, 0)

    def test_primary_clear_error_survives_evidence_write_error(self):
        for function in FUNCTIONS:
            h = Harness()
            h.new.root.failure = RuntimeError('PRIMARY_CLEAR_FAILURE')
            h.write_failure = lambda row: OSError('EVIDENCE_DISK_ERROR') if 'error' in row else None
            with self.assertRaisesRegex(RuntimeError, 'PRIMARY_CLEAR_FAILURE') as caught:
                h.call(function)
            self.assertTrue(any('EVIDENCE_DISK_ERROR' in note for note in caught.exception.__notes__))

    def test_initial_observation_failure_has_no_stage_mutation(self):
        for function in FUNCTIONS:
            h = Harness()
            h.write_failure = lambda row: OSError('NO_OBSERVATION')
            with self.assertRaisesRegex(OSError, 'NO_OBSERVATION'):
                h.call(function)
            self.assertEqual(h.context.new_calls, 0)

    def test_final_observation_failure_cannot_return_success(self):
        for function in FUNCTIONS:
            h = Harness()
            h.write_failure = lambda row: OSError('FINAL_WRITE') if row['verified'] else None
            with self.assertRaisesRegex(OSError, 'FINAL_WRITE'):
                h.call(function)
            self.assertFalse(h.rows[-1]['verified'])

    def test_census_error_keeps_primary_and_failure_observation_error(self):
        for function in FUNCTIONS:
            h = Harness()
            h.new.census_error = RuntimeError('PRIMARY_CENSUS_FAILURE')
            with self.assertRaisesRegex(RuntimeError, 'PRIMARY_CENSUS_FAILURE'):
                h.call(function)
            self.assertIn('PRIMARY_CENSUS_FAILURE', h.rows[-1]['failure_census_error'])

    def test_new_stage_false_or_none_never_clears(self):
        for function in FUNCTIONS:
            for missing in (False, True):
                h = Harness()
                h.context.result = False
                if missing: h.context.new = None
                with self.assertRaisesRegex(ValueError, 'Actual fresh stage'):
                    h.call(function)
                self.assertEqual(h.new.root.calls + h.new.session.calls, 0)

    def test_splice_preserves_every_other_original_byte(self):
        a, b, _ = B.function_span(original)
        c, d, _ = B.function_span(candidate)
        self.assertEqual(original[:a], candidate[:c])
        self.assertEqual(original[b:], candidate[d:])
        self.assertEqual(B.BASE.read_bytes(), original)
        self.assertTrue(proof['outside_function_bytes_unchanged'])

    def test_changed_base_duplicate_function_and_changed_signature_are_rejected(self):
        replacement = (HERE / 'stage_reset.py').read_bytes()
        with self.assertRaisesRegex(ValueError, 'SHA'):
            B.candidate_bytes(original + b'\n', replacement)
        with self.assertRaisesRegex(ValueError, 'Exactly one'):
            B.candidate_bytes(original, replacement + b'\ndef fresh_stage(ctx,context,clock):\n    return None\n')
        with self.assertRaisesRegex(ValueError, 'signature'):
            B.candidate_bytes(original, replacement.replace(b'ctx, context, clock', b'ctx, context, clock, other'))

    def test_exclusive_candidate_and_owned_path(self):
        destination = B.OUT / ('HOST_ONLY_build_' + uuid.uuid4().hex)
        manifest = B.build(destination)
        before = (destination / 'native.py').read_bytes()
        self.assertEqual(manifest['native_sha256'], B.digest(before))
        self.assertFalse(manifest['approved_to_execute'])
        with self.assertRaises(FileExistsError): B.build(destination)
        self.assertEqual((destination / 'native.py').read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'owned output'): B.build(HERE / 'FORBIDDEN')

    def test_no_sdk_modules_loaded(self):
        self.assertFalse(any(name == 'isaacsim' or name.startswith(('isaacsim.', 'omni.usd')) for name in sys.modules))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ResetTests))
    summary = {'unit': 124, 'kind': 'HOST_ONLY_REAL_SPLICED_FUNCTION_AND_STANDALONE',
               'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'passed': result.wasSuccessful(), 'implementations_per_stage_control': 2,
               'SDK_initializations': 0, 'SSH_launches': 0, 'hardware_approved': False,
               'base_source_unchanged': B.BASE.read_bytes() == original,
               'candidate_sha256': B.digest(candidate)}
    with (B.OUT / 'host-result.json').open('x', encoding='utf8') as stream:
        json.dump(summary, stream, indent=2)
        stream.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
