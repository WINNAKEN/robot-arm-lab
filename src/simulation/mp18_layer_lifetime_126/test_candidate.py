"""SDK-free controls for the real native splice and weak USD handle lifetimes."""
import gc
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import weakref

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = load('candidate126_HOST_ONLY', HERE / 'candidate.py')
T = load('fixtures124_HOST_ONLY', ROOT / 'src/simulation/mp18_stage_reset_124/test_stage_reset.py')
BASE = C.BASE.read_bytes()
SOURCE = (HERE / 'candidate.py').read_bytes()
CANDIDATE, PROOF = C.candidate_bytes(BASE, SOURCE)
NATIVE = types.ModuleType('generated126_HOST_ONLY')
exec(compile(CANDIDATE, 'generated126_HOST_ONLY_native.py', 'exec'), NATIVE.__dict__)
FUNCTIONS = (C.fresh_stage, NATIVE.fresh_stage)


class WeakLayer:
    """A Python reference to this handle does not retain the underlying layer."""
    def __init__(self, raw, arena):
        self.raw, self.arena = raw, arena

    def _check(self):
        if self.arena.retired and not any(p.raw is self.raw for p in self.arena.live_pins):
            raise TypeError('EXPIRED_WEAK_LAYER')

    def __getattr__(self, name):
        self._check()
        return getattr(self.raw, name)

    def __bool__(self):
        self._check()
        return True

    def __eq__(self, other):
        self._check()
        return self.raw is getattr(other, 'raw', other)

    def __hash__(self):
        return hash(id(self.raw))


class StrongLayer(WeakLayer):
    def _check(self):
        return None


class LifetimeHarness(T.Harness):
    def __init__(self):
        super().__init__()
        self.retired, self.live_pins, self.pin_calls = False, weakref.WeakSet(), []
        self.raw_layers = (self.old.root, self.old.session)
        self.old.root, self.old.session = (WeakLayer(layer, self) for layer in self.raw_layers)
        self.raw_map = {layer.identifier: layer for layer in self.raw_layers}
        self.on_switch = None
        self.pin_mode = 'strong'

        def new_stage():
            self.context.new_calls += 1
            self.retired = True
            if self.on_switch:
                self.on_switch()
            self.context.stage = self.new
            return True

        self.context.new_stage = new_stage

    def find_or_open(self, identifier):
        self.pin_calls.append(identifier)
        raw = self.raw_map[identifier]
        if self.pin_mode == 'missing':
            return None
        if self.pin_mode == 'throw':
            raise OSError('PIN_FAILURE')
        if self.pin_mode == 'wrong':
            return StrongLayer(T.Layer('anon:wrong'), self)
        if self.pin_mode == 'weak':
            return WeakLayer(raw, self)
        pinned = StrongLayer(raw, self)
        self.live_pins.add(pinned)
        return pinned

    def run_function(self, function):
        fake = types.ModuleType('pxr')
        fake.Sdf = types.SimpleNamespace(Layer=types.SimpleNamespace(
            FindOrOpen=self.find_or_open,
            Find=lambda identifier: WeakLayer(self.raw_map[identifier], self)))
        with patch.dict(sys.modules, {'pxr': fake}):
            return self.call(function)


class LifetimeTests(unittest.TestCase):
    def test_original_sdk_failure_reproduced_before_clear(self):
        h = LifetimeHarness()
        with self.assertRaisesRegex(TypeError, 'EXPIRED_WEAK_LAYER'):
            h.run_function(T.SPLICED.fresh_stage)
        self.assertEqual(h.new.root.calls + h.new.session.calls, 0)
        self.assertIsNotNone(h.rows[-1]['after_new'])
        self.assertFalse(h.rows[-1]['verified'])

    def test_both_real_paths_retain_two_strong_pins_through_comparison(self):
        for function in FUNCTIONS:
            h = LifetimeHarness()
            before = [layer.ExportToString() for layer in h.raw_layers]
            self.assertIs(h.run_function(function), h.new)
            self.assertEqual(h.pin_calls, [layer.identifier for layer in h.raw_layers])
            self.assertEqual([layer.ExportToString() for layer in h.raw_layers], before)
            self.assertEqual(sum(layer.calls for layer in h.raw_layers), 0)
            self.assertTrue(h.rows[-1]['verified'])
            self.assertEqual(h.rows[-1]['old_layers_before_reset'], h.rows[-1]['old_layers_after_reset'])
            self.assertTrue(any(row.get('old_layers_before_reset') and row['after_new'] is None for row in h.rows))
            gc.collect()
            self.assertEqual(len(h.live_pins), 0)

    def test_weak_find_mutation_fails_on_actual_spliced_path(self):
        changed = SOURCE.replace(b'Sdf.Layer.FindOrOpen(identifier)', b'Sdf.Layer.Find(identifier)')
        raw, _ = C.candidate_bytes(BASE, changed)
        mutated = types.ModuleType('weak126_MUTANT_HOST_ONLY')
        exec(compile(raw, 'weak126_MUTANT_HOST_ONLY.py', 'exec'), mutated.__dict__)
        h = LifetimeHarness()
        with self.assertRaisesRegex(TypeError, 'EXPIRED_WEAK_LAYER'):
            h.run_function(mutated.fresh_stage)
        self.assertFalse(h.rows[-1]['verified'])
        self.assertEqual(sum(layer.calls for layer in h.raw_layers), 0)
        # This mutant reaches the post-clear old-content comparison; it must
        # fail acceptance, while only the two owned new layers were cleared.
        self.assertEqual(h.new.root.calls + h.new.session.calls, 2)

    def test_missing_wrong_and_throwing_pins_prevent_new_stage(self):
        for function in FUNCTIONS:
            for mode in ('missing', 'wrong', 'throw'):
                h = LifetimeHarness()
                h.pin_mode = mode
                with self.assertRaises((ValueError, OSError)):
                    h.run_function(function)
                self.assertEqual(h.context.new_calls, 0)
                self.assertFalse(h.rows[-1]['verified'])
                self.assertEqual(sum(layer.calls for layer in h.raw_layers), 0)

    def test_old_content_mutated_during_new_stage_is_detected(self):
        for function in FUNCTIONS:
            h = LifetimeHarness()
            h.on_switch = lambda: h.raw_layers[0].prims.append(T.Prim('/UNEXPECTED'))
            with self.assertRaisesRegex(ValueError, 'remain unchanged'):
                h.run_function(function)
            self.assertFalse(h.rows[-1]['verified'])

    def test_failed_pin_evidence_preserves_primary_exception(self):
        h = LifetimeHarness()
        h.pin_mode = 'throw'
        h.write_failure = lambda row: OSError('SECONDARY_WRITE') if 'error' in row else None
        with self.assertRaisesRegex(OSError, 'PIN_FAILURE') as caught:
            h.run_function(NATIVE.fresh_stage)
        self.assertTrue(any('SECONDARY_WRITE' in note for note in caught.exception.__notes__))
        self.assertEqual(h.context.new_calls, 0)

    def test_pre_switch_snapshot_write_failure_prevents_new_stage(self):
        h = LifetimeHarness()
        h.write_failure = lambda row: OSError('PIN_SNAPSHOT_WRITE') if row.get('old_layer_ownership') else None
        with self.assertRaisesRegex(OSError, 'PIN_SNAPSHOT_WRITE'):
            h.run_function(NATIVE.fresh_stage)
        self.assertEqual(h.context.new_calls, 0)

    def test_anonymous_pin_guard_rejects_file_backed_old_layer(self):
        h = LifetimeHarness()
        h.raw_layers[0].anonymous = False
        with self.assertRaisesRegex(ValueError, 'Pin only existing anonymous'):
            h.run_function(NATIVE.fresh_stage)
        self.assertEqual(h.pin_calls, [])
        self.assertEqual(h.context.new_calls, 0)

    def test_base_and_all_bytes_outside_function_are_preserved(self):
        a, b, _ = C.function_span(BASE)
        c, d, _ = C.function_span(CANDIDATE)
        self.assertEqual(BASE[:a], CANDIDATE[:c])
        self.assertEqual(BASE[b:], CANDIDATE[d:])
        self.assertEqual(C.BASE.read_bytes(), BASE)
        self.assertEqual(C.digest(BASE), C.BASE_SHA256)
        self.assertTrue(PROOF['outside_function_bytes_unchanged'])
        with self.assertRaisesRegex(ValueError, 'SHA'):
            C.candidate_bytes(BASE + b'\n', SOURCE)
        with self.assertRaisesRegex(ValueError, 'signature'):
            C.candidate_bytes(BASE, SOURCE.replace(b'ctx, context, clock', b'ctx, context, clock, extra'))
        with self.assertRaisesRegex(ValueError, 'Exactly one'):
            C.candidate_bytes(BASE, SOURCE + b'\ndef fresh_stage(ctx, context, clock):\n    pass\n')

    def test_sdk_modules_not_loaded(self):
        self.assertFalse(any(name == 'isaacsim' or name.startswith(('isaacsim.', 'omni.usd')) for name in sys.modules))


def main():
    # Run the existing stage invariants against BOTH new real implementations.
    # Exclude124 builder/output tests: original124 artifacts must stay unchanged.
    excluded = {'test_splice_preserves_every_other_original_byte',
                'test_changed_base_duplicate_function_and_changed_signature_are_rejected',
                'test_exclusive_candidate_and_owned_path'}
    registry = {}
    old_init = T.Layer.__init__

    def register(layer, *args, **kwargs):
        old_init(layer, *args, **kwargs)
        registry[layer.identifier] = layer

    fake = types.ModuleType('pxr')
    fake.Sdf = types.SimpleNamespace(Layer=types.SimpleNamespace(FindOrOpen=lambda identifier: registry[identifier]))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LifetimeTests)
    for name in unittest.defaultTestLoader.getTestCaseNames(T.ResetTests):
        if name not in excluded:
            suite.addTest(T.ResetTests(name))
    with patch.object(T, 'FUNCTIONS', FUNCTIONS), patch.object(T.Layer, '__init__', register), patch.dict(sys.modules, {'pxr': fake}):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {'unit':126, 'kind':'HOST_WEAK_LIFETIME_AND_ACTUAL_NATIVE_SPLICE',
               'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors),
               'passed':result.wasSuccessful(), 'SDK_initializations':0, 'SSH_launches':0,
               'hardware_approved':False, 'native_sha256':C.digest(CANDIDATE),
               'base_sha256':C.digest(BASE), 'base_unchanged':C.BASE.read_bytes()==BASE}
    with (C.OUT/'host-result.json').open('x',encoding='utf8') as stream:
        json.dump(summary,stream,indent=2)
        stream.write('\n')
    print(json.dumps(summary))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
