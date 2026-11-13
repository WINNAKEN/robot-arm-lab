"""HOST-only policy/JSON/filesystem tests; never touches system time or UAC."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


if "ral109_core" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("ral109_core", Path(__file__).with_name("core.py"))
    _core = importlib.util.module_from_spec(_spec)
    sys.modules["ral109_core"] = _core
    _spec.loader.exec_module(_core)
c = sys.modules["ral109_core"]

P, F, R = c.PLAN_SHA, "1" * 64, "2" * 64


def approval():
    return {"unit": "109", "explicit_user_approval": True,
            "scope": "LOCAL_CLOCK_ALIGN109_ONCE_LE5S", "hardware_approved": False,
            "clock_cap_s": 5, "one_adjustment": 1, "plan_sha256": P,
            "source_freeze_sha256": F, "review_sha256": R,
            "user_quote": "HOST_SYNTHETIC_ONLY_NOT_EXECUTION_AUTHORITY"}


def review():
    return {"unit": "109", "phase": "L4", "round": 1, "verdict": "PASS",
            "non_author": True, "all_required_met": True, "met": 6, "unmet": 0,
            "reviewer": "HOST_SYNTHETIC_NONAUTHOR", "actual_freeze_sha256": F,
            "actual_plan_sha256": P,
            "criteria": [{"id": "AC" + str(i), "required": True, "met": True}
                         for i in range(1, 7)]}


def sample():
    return {"local_send_unix": 1000.0, "local_receive_unix": 1000.2,
            "local_elapsed_s": 0.2, "finished_tick_ms": 10000,
            "remote_unix_ms": 1002100, "computer": "민주환-JUHWANMI", "nonce": "fresh-test"}


class JSONTests(unittest.TestCase):
    def test_need_requires_actual_bool(self):
        c.need(True, "accepted")
        for value in (False, 0, 1, [], {}, "true", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.need(value, "denied")

    def test_strict_nested_roundtrip(self):
        value = {"한글": [1, 2.5, True, None], "a": {"b": "ok"}}
        self.assertEqual(c.strict_loads(c.canonical(value)), value)
        self.assertEqual(c.strict_loads(c.canonical(value).decode("utf-8")), value)

    def test_duplicate_keys_rejected_at_every_depth(self):
        for raw in ('{"a":1,"a":2}', '{"nested":{"a":1,"a":2}}',
                    '[{"a":1,"a":2}]', '{"a":1,"\\u0061":2}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.strict_loads(raw)

    def test_nonfinite_json_and_exponents_rejected(self):
        for raw in ("NaN", "Infinity", "-Infinity", "1e9999", "-1e9999", '[1, {"x": NaN}]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.strict_loads(raw)

    def test_double_json_and_trailing_content_rejected(self):
        for raw in ('{}{}', '{} false', '{}\n{}', '[1] 2', '{"x":1,}', b"\xff", b"\xef\xbb\xbf{}"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.strict_loads(raw)

    def test_json_input_types(self):
        for raw in (None, 1, True, {}, [], bytearray(b"{}")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.strict_loads(raw)

    def test_canonical_stable_and_nan_denied(self):
        self.assertEqual(c.canonical({"z": 2, "a": "한"}), b'{"a":"\xed\x95\x9c","z":2}')
        for value in (math.nan, math.inf, -math.inf, {"deep": [math.inf]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.canonical(value)

    def test_sha_only_bytes(self):
        self.assertEqual(c.sha(b"abc"), hashlib.sha256(b"abc").hexdigest())
        for value in ("abc", bytearray(b"abc"), 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.sha(value)


class AuthorityTests(unittest.TestCase):
    def test_approval_positive_returns_distinct_object(self):
        original = approval()
        got = c.validate_approval(original, P, F, R)
        self.assertEqual(got, original)
        self.assertIsNot(got, original)

    def test_approval_closed_fields(self):
        for candidate in (None, [], {**approval(), "extra": True},
                          {k: v for k, v in approval().items() if k != "user_quote"}):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                c.validate_approval(candidate, P, F, R)

    def test_approval_types_scope_cap_and_quote(self):
        bad = {"unit": (109, "108", None), "explicit_user_approval": (1, False, "true"),
               "hardware_approved": (0, True, "false"),
               "clock_cap_s": (True, "5", 5.001, 4.999, math.nan, math.inf),
               "one_adjustment": (True, 1.0, 0, 2, "1"),
               "scope": ("NATIVE108", None, "LOCAL_CLOCK_ALIGN109_ONCE_LE5S "),
               "user_quote": (None, "", " \n ", 1)}
        for key, values in bad.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    c.validate_approval({**approval(), key: value}, P, F, R)

    def test_approval_hash_pins(self):
        for key in ("plan_sha256", "source_freeze_sha256", "review_sha256"):
            for value in ("0" * 64, "x" * 64, "1" * 63, 1, None, ""):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    c.validate_approval({**approval(), key: value}, P, F, R)
        for pins in (("bad", F, R), (P, None, R), (P, F, "z" * 64)):
            with self.subTest(pins=pins), self.assertRaises(ValueError):
                c.validate_approval(approval(), *pins)

    def test_l4_positive_rounds_and_bookkeeping(self):
        for number in (1, 2):
            c.validate_l4({**review(), "round": number, "bookkeeping": {"retained": True}}, F, P)

    def test_l4_typed_receipt(self):
        bad = {"unit": (109, "108", None), "phase": ("L2", None),
               "round": (True, 1.0, 0, 3, None), "verdict": ("BLOCK", None),
               "non_author": (1, False), "all_required_met": (1, False),
               "met": (True, 6.0, 5), "unmet": (False, 0.0, 1),
               "reviewer": ("", "  ", "author", " AuThOr ", 1),
               "actual_freeze_sha256": ("0" * 64, None),
               "actual_plan_sha256": ("0" * 64, None)}
        for key, values in bad.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    c.validate_l4({**review(), key: value}, F, P)

    def test_l4_missing_required_fields(self):
        for key in review():
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.validate_l4({k: v for k, v in review().items() if k != key}, F, P)

    def test_l4_criteria_must_be_exact_unique_and_typed(self):
        original = review()["criteria"]
        candidates = ([], original[:-1], original + [original[0]], tuple(original),
                      [*original[:-1], original[0]], [*original[:-1], {"id": "AC7", "required": True, "met": True}],
                      [*original[:-1], {"id": "AC6", "required": 1, "met": True}],
                      [*original[:-1], {"id": "AC6", "required": True, "met": 1}],
                      [*original[:-1], None])
        for value in candidates:
            with self.subTest(criteria=value), self.assertRaises(ValueError):
                c.validate_l4({**review(), "criteria": value}, F, P)


class SampleTests(unittest.TestCase):
    def test_positive_interval_sign_and_pads(self):
        result = c.validate_sample(sample(), 10000)
        self.assertAlmostEqual(result["low"], 1.898)
        self.assertAlmostEqual(result["high"], 2.102)
        self.assertAlmostEqual(result["midpoint"], 2.0)
        self.assertTrue(result["needs_change"])
        self.assertEqual(set(result), {"low", "high", "midpoint", "needs_change"})

    def test_negative_correction(self):
        result = c.validate_sample({**sample(), "remote_unix_ms": 998100}, 10000)
        self.assertAlmostEqual(result["midpoint"], -2.0)
        self.assertTrue(result["needs_change"])

    def test_full_interval_required_for_no_change(self):
        for remote_ms, expected in ((1000100, False), (1000999, True),
                                     (999203, False), (999101, True)):
            with self.subTest(remote_ms=remote_ms):
                self.assertEqual(c.validate_sample({**sample(), "remote_unix_ms": remote_ms}, 10000)["needs_change"], expected)

    def test_age_inclusive_five_seconds_and_negative_age(self):
        c.validate_sample(sample(), 15000)
        for tick in (9999, 15001, True, 15000.0, -1):
            with self.subTest(tick=tick), self.assertRaises(ValueError):
                c.validate_sample(sample(), tick)

    def test_wall_monotonic_coherence_boundary(self):
        clean = {**sample(), "local_send_unix": 0, "local_receive_unix": 0.5,
                 "remote_unix_ms": 2250, "local_elapsed_s": 0.25}
        c.validate_sample(clean, 10000)
        for elapsed in (0.249999, 0.750001, -1):
            with self.subTest(elapsed=elapsed), self.assertRaises(ValueError):
                c.validate_sample({**clean, "local_elapsed_s": elapsed}, 10000)
        with self.assertRaises(ValueError):
            c.validate_sample({**clean, "local_receive_unix": -0.1}, 10000)

    def test_uncertainty_width_includes_both_pads(self):
        clean = {**sample(), "local_send_unix": 0, "local_receive_unix": 1.495,
                 "local_elapsed_s": 1.495, "remote_unix_ms": 2000}
        c.validate_sample(clean, 10000)
        with self.assertRaises(ValueError):
            c.validate_sample({**clean, "local_receive_unix": 1.497, "local_elapsed_s": 1.497}, 10000)

    def test_midpoint_cap_both_signs(self):
        clean = {**sample(), "local_send_unix": 0, "local_receive_unix": 0,
                 "local_elapsed_s": 0}
        for remote in (5000, -5000):
            c.validate_sample({**clean, "remote_unix_ms": remote}, 10000)
        for remote in (5001, -5001):
            with self.subTest(remote=remote), self.assertRaises(ValueError):
                c.validate_sample({**clean, "remote_unix_ms": remote}, 10000)

    def test_sample_numeric_types_nonfinite_and_overflow(self):
        for key in ("local_send_unix", "local_receive_unix", "local_elapsed_s"):
            for value in (True, "1", None, math.nan, math.inf, -math.inf, 10 ** 400):
                with self.subTest(key=key, value=str(value)[:20]), self.assertRaises(ValueError):
                    c.validate_sample({**sample(), key: value}, 10000)

    def test_extreme_finite_values_cannot_round_to_false_zero_width(self):
        with self.assertRaises(ValueError):
            c.validate_sample({**sample(), "local_send_unix": 1e297,
                               "local_receive_unix": 1e297, "local_elapsed_s": 0,
                               "remote_unix_ms": 10 ** 300}, 10000)
        for key in ("finished_tick_ms", "remote_unix_ms"):
            for value in (True, "10000", 10000.0, None):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    c.validate_sample({**sample(), key: value}, 10000)

    def test_machine_nonce_and_closed_fields(self):
        candidates = ({**sample(), "computer": "WRONG"}, {**sample(), "computer": None},
                      {**sample(), "nonce": " "}, {**sample(), "nonce": 1},
                      {**sample(), "extra": 1}, {k: v for k, v in sample().items() if k != "nonce"})
        for value in candidates:
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.validate_sample(value, 10000)


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.lease = c.Lease(1000, 123, 123456789, "one-invocation")

    def test_lease_frozen_and_ends_derived(self):
        self.assertEqual((self.lease.uac_end, self.lease.active_end, self.lease.hard_end),
                         (91000, 171000, 181000))
        for key in ("start_tick", "parent_pid", "parent_created", "nonce"):
            with self.subTest(key=key), self.assertRaises(FrozenInstanceError):
                setattr(self.lease, key, 1)

    def test_uac_deadline_cannot_be_extended(self):
        self.assertEqual(self.lease.remaining_ms(90999, "uac"), 1)
        for tick in (91000, 171000, 181000):
            with self.subTest(tick=tick), self.assertRaises(ValueError):
                self.lease.check(tick, "uac")

    def test_final_ten_seconds_only_cleanup(self):
        self.lease.check(170999, "adjust")
        self.lease.check(171000, "cleanup")
        self.assertEqual(self.lease.remaining_ms(180999, "cleanup"), 1)
        for phase in ("active", "sample", "adjust", "verify", "worker", "api", "cleanup"):
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                self.lease.check(181000 if phase == "cleanup" else 171000, phase)

    def test_regressed_boot_tick_unknown_phase_and_malformed_ticks(self):
        for tick, phase in ((999, "active"), (False, "active"), (1000.0, "active"),
                            (1000, "later"), (1000, None), (-1, "cleanup")):
            with self.subTest(tick=tick, phase=phase), self.assertRaises(ValueError):
                self.lease.check(tick, phase)

    def test_invalid_lease_identity(self):
        for args in ((True, 1, 1, "n"), (-1, 1, 1, "n"), (0, True, 1, "n"),
                     (0, 0, 1, "n"), (0, 1, True, "n"), (0, 1, 0, "n"),
                     (0, 1, 1, " "), (0, 1, 1, 1), (2 ** 64 - 1, 1, 1, "n"),
                     (0, 2 ** 32, 1, "n"), (0, 1, 2 ** 64, "n")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                c.Lease(*args)


class ExclusiveFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ral109-core-HOST-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reservation_is_exclusive_and_durable(self):
        target = self.root / "attempt.json"
        with patch.object(c.os, "fsync", wraps=os.fsync) as sync:
            c.reserve_attempt(target, {"nonce": "one"})
            self.assertEqual(sync.call_count, 1)
        original = target.read_bytes()
        self.assertEqual(c.strict_loads(original), {"nonce": "one"})
        with self.assertRaises(FileExistsError):
            c.reserve_attempt(target, {"nonce": "two"})
        self.assertEqual(target.read_bytes(), original)

    def test_concurrent_reservation_exactly_one_winner(self):
        target = self.root / "attempt.json"
        gate = threading.Barrier(5)
        outcomes = []
        def reserve(number):
            gate.wait()
            try:
                c.reserve_attempt(target, {"nonce": str(number)})
                outcomes.append("reserved")
            except FileExistsError:
                outcomes.append("exists")
        threads = [threading.Thread(target=reserve, args=(i,)) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(outcomes), ["exists"] * 4 + ["reserved"])
        self.assertIn(c.strict_loads(target.read_bytes())["nonce"], {str(i) for i in range(5)})

    def test_failed_fsync_leaves_consumption_in_place(self):
        target = self.root / "attempt.json"
        with patch.object(c.os, "fsync", side_effect=OSError("HOST_INJECTED_FSYNC")):
            with self.assertRaises(OSError):
                c.reserve_attempt(target, {"nonce": "one"})
        self.assertTrue(target.exists())
        with self.assertRaises(FileExistsError):
            c.reserve_attempt(target, {"nonce": "two"})

    def test_zero_write_consumes_and_denies_retry(self):
        target = self.root / "attempt.json"
        with patch.object(c.os, "write", return_value=0):
            with self.assertRaises(ValueError):
                c.reserve_attempt(target, {"nonce": "one"})
        self.assertTrue(target.exists())
        with self.assertRaises(FileExistsError):
            c.reserve_attempt(target, {"nonce": "two"})

    def test_partial_writes_are_completed(self):
        target = self.root / "attempt.json"
        real_write = os.write
        with patch.object(c.os, "write", side_effect=lambda fd, raw: real_write(fd, raw[:2])):
            c.reserve_attempt(target, {"nonce": "one"})
        self.assertEqual(c.strict_loads(target.read_bytes()), {"nonce": "one"})

    def test_result_full_atomic_nooverwrite_and_attempt_unchanged(self):
        attempt, target = self.root / "attempt.json", self.root / "result.json"
        c.reserve_attempt(attempt, {"nonce": "one"})
        consumed = attempt.read_bytes()
        c.atomic_result_exclusive(target, {"status": "HOST_NOT_OS"})
        original = target.read_bytes()
        with self.assertRaises(FileExistsError):
            c.atomic_result_exclusive(target, {"status": "replaced"})
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(attempt.read_bytes(), consumed)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["attempt.json", "result.json"])

    def test_result_not_visible_before_complete_sync(self):
        target = self.root / "result.json"
        real_sync = os.fsync
        def sync(fd):
            self.assertFalse(target.exists())
            real_sync(fd)
        with patch.object(c.os, "fsync", side_effect=sync):
            c.atomic_result_exclusive(target, {"status": "HOST_NOT_OS"})
        self.assertEqual(c.strict_loads(target.read_bytes())["status"], "HOST_NOT_OS")

    def test_result_write_failure_never_publishes_or_resets_attempt(self):
        attempt, target = self.root / "attempt.json", self.root / "result.json"
        c.reserve_attempt(attempt, {"nonce": "one"})
        with patch.object(c.os, "fsync", side_effect=OSError("HOST_RESULT_IO_LOSS")):
            with self.assertRaises(OSError):
                c.atomic_result_exclusive(target, {"status": "HOST_NOT_OS"})
        self.assertFalse(target.exists())
        self.assertTrue(attempt.exists())

    def test_result_publication_failure_does_not_reset_attempt(self):
        attempt, target = self.root / "attempt.json", self.root / "result.json"
        c.reserve_attempt(attempt, {"nonce": "one"})
        with patch.object(c.os, "link", side_effect=OSError("HOST_LINK_DENIED")):
            with self.assertRaises(OSError):
                c.atomic_result_exclusive(target, {"status": "HOST_NOT_OS"})
        self.assertFalse(target.exists())
        self.assertTrue(attempt.exists())

    def test_bad_json_is_denied_before_consumption(self):
        target = self.root / "attempt.json"
        with self.assertRaises(ValueError):
            c.reserve_attempt(target, {"bad": math.nan})
        self.assertFalse(target.exists())

    def test_symlink_or_junction_attribute_denied(self):
        actual = self.root / "real"
        actual.mkdir()
        original = Path.lstat
        def reparse(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == actual:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400,
                                       st_dev=info.st_dev, st_ino=info.st_ino)
            return info
        with patch.object(Path, "lstat", new=reparse):
            for operation in (c.reserve_attempt, c.atomic_result_exclusive):
                with self.subTest(operation=operation.__name__), self.assertRaises(ValueError):
                    operation(actual / "denied.json", {"nonce": "one"})
        self.assertFalse((actual / "denied.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction branch")
    def test_actual_owned_windows_junction_denied(self):
        import _winapi
        actual, junction = self.root / "actual", self.root / "junction"
        actual.mkdir()
        _winapi.CreateJunction(str(actual), str(junction))
        try:
            self.assertTrue(junction.is_junction())
            for operation in (c.reserve_attempt, c.atomic_result_exclusive):
                with self.subTest(operation=operation.__name__), self.assertRaises(ValueError):
                    operation(junction / "denied.json", {"nonce": "one"})
            self.assertFalse((actual / "denied.json").exists())
        finally:
            # This is the exact owned empty junction, not its target directory.
            junction.rmdir()

    def test_existing_directory_and_link_destinations_not_overwritten(self):
        target = self.root / "result.json"
        target.mkdir()
        for operation in (c.reserve_attempt, c.atomic_result_exclusive):
            with self.subTest(operation=operation.__name__), self.assertRaises(OSError):
                operation(target, {"nonce": "one"})
        self.assertTrue(target.is_dir())

    def test_parent_replacement_detected_before_attempt_write(self):
        target = self.root / "attempt.json"
        actual = c._parents
        calls = 0
        def changed(path):
            nonlocal calls
            calls += 1
            return actual(path) if calls == 1 else (("HOST_CHANGED", 1, 2),)
        with patch.object(c, "_parents", side_effect=changed):
            with self.assertRaises(ValueError):
                c.reserve_attempt(target, {"nonce": "one"})
        self.assertTrue(target.exists())
        self.assertEqual(target.read_bytes(), b"")

    def test_unsafe_alias_names_denied_without_write(self):
        for name in ("NUL", "CON.json", "result.json:stream", "result.json.", "result.json "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                c.reserve_attempt(self.root / name, {"nonce": "one"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
