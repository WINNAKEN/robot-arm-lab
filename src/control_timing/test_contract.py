"""Policy/oracle tests, NOT a replacement for firmware or browser tests."""
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import unittest
from dataclasses import replace

module_path = Path(sys.argv.pop(1)) if len(sys.argv) > 1 and sys.argv[1].endswith('.py') else Path(__file__).with_name('contract.py')
spec = importlib.util.spec_from_file_location('timing_under_test', module_path)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
ROOT = Path(__file__).resolve().parents[2]


def transfer(until=670, at=0, key=None):
    t = m.Transfer()
    assert t.reserve(at, until, key or m.Key())
    return t


class TimeContractTests(unittest.TestCase):
    def test_round_trip_counterexample_and_strict_margin(self):
        actual = 350 + 50 + 49 + 49
        self.assertEqual(actual, 498)
        self.assertGreater(actual, 100 + 250 + 49 + 50)  # rejected R1 bound
        self.assertEqual(m.observation_bound(100, 49), actual)
        self.assertFalse(m.enough_headroom(100, actual, margin=400))
        self.assertFalse(m.enough_headroom(100, actual, margin=353))
        self.assertTrue(m.enough_headroom(100, actual, margin=352))
        self.assertEqual(m.OBSERVE_MS, 1147)

    def test_recorded_points_old_failure_new_policy_only(self):
        raw = json.loads((ROOT / '.dev/phone-browser-evidence/author-attempt-006/normal.json').read_text(encoding='utf-8-sig'))
        handoff = next(x for x in raw['commands'] if x['op'] == 'handoff')
        accepted = int(handoff['result']['accepted_at'])
        renew = max(int(x['result']['accepted_at']) for x in raw['commands'] if x['op'] == 'maintenance-renew')
        deadline = renew + 800
        points = [x for x in raw['actor'] if x.get('text') == 'P' and x.get('result', {}).get('ready') is True]
        ready_at = {int(x['result']['at']) for x in points}
        self.assertEqual((accepted, deadline), (6558, 7228))
        self.assertEqual(ready_at, {6993, 7162, 7177})
        browser = []
        for request in raw['requests']:
            if request['url'] != '/api/status' or 'reply_ms' not in request:
                continue
            matches = [x for x in raw['actor'] if x.get('text') == 'P'
                       and request['host_ms'] <= x['host_ms'] <= request['reply_ms']]
            self.assertEqual(len(matches), 1)
            s = matches[0]['result']
            if accepted <= int(s['at']) < deadline:
                browser.append((int(s['at']), s['ready']))
        self.assertEqual(browser, [(6673, False), (6935, False), (7179, False)])
        self.assertFalse(any(x['op'] == 'acquire' for x in raw['commands']))
        self.assertTrue(any(x.get('result', {}).get('stop_at') == '7228' for x in raw['actor']))
        t = transfer(deadline, accepted)
        # This branch executes NEW POLICY over recorded proof points. Not actual Owner.
        for now in range(accepted, 7180):
            t.tick(now, proof=now in ready_at)
        self.assertEqual(t.grant_at, 6993)
        self.assertEqual(t.acquire_attempts, 1)
        o = m.Observer(t.key, clicked=accepted)
        self.assertTrue(o.accept(t.receipt(7179, t.key), 7179))
        self.assertEqual(t.lease_until, 7793)

    def test_synthetic_phase_delay_sweep(self):
        cases = 0
        for phase, outbound, inbound, gap in itertools.product(range(250), (0, 25, 49), (0, 25, 49), (1, 9)):
            t = transfer()
            observer = m.Observer(t.key)
            # Synthetic continuous proof window, NOT inferred between raw P points.
            query_due = phase
            while query_due < 98:  # worst bounded command ACK (49 each direction)
                query_due += 250
            events = {}
            for now in range(0, 1150, gap):
                events.setdefault(now, []).append(('actor', None))
            while query_due < 1000:
                server_at = query_due + 50 + outbound
                events.setdefault(server_at, []).append(('query', None))
                query_due += 250
            adopted = None
            for now in sorted(events):
                for kind, value in events[now]:
                    if kind == 'actor':
                        t.tick(now, proof=435 <= now < 445)
                    elif kind == 'query':
                        receipt = t.receipt(now, t.key)
                        arrival = now + inbound
                        if observer.accept(receipt, arrival):
                            adopted = arrival
                            break
                if adopted is not None:
                    break
            self.assertIsNotNone(adopted, (phase, outbound, inbound, gap))
            self.assertLess(t.grant_at, 670)
            self.assertLessEqual(adopted, m.observation_bound(t.grant_at, 98, query_request=outbound, query_response=inbound))
            self.assertTrue(m.enough_headroom(t.grant_at, adopted, margin=300))
            self.assertEqual((t.acquire_attempts, t.renewals), (1, 0))
            cases += 1
        self.assertEqual(cases, 4500)
        print('SYNTHETIC_PHASE_DELAY_CASES', cases)

    def test_deadline_strict_before_equal_after_and_actual_detection(self):
        for when, grants in ((669, 1), (670, 0), (671, 0)):
            t = transfer()
            t.tick(when, proof=True)
            self.assertEqual(t.acquire_attempts, grants)
            if not grants:
                self.assertEqual((t.stop_at, t.fault_at), (when, when))
        t = transfer(2000)
        self.assertEqual(t.pending_until, 700)
        t.tick(700, proof=True)
        self.assertEqual(t.acquire_attempts, 0)
        t = transfer()
        for now in range(0, 676, 9):
            t.tick(now)
        self.assertEqual((t.stop_at, t.pending_until), (675, 670))

    def test_no_proof_and_no_hidden_renewal(self):
        t = transfer()
        for now in range(0, 671):
            t.tick(now)
            if now % 50 == 0:
                t.receipt(now, t.key)
            self.assertEqual(t.pending_until, 670)
            self.assertEqual(t.boot_until, 670)
        self.assertEqual((t.acquire_attempts, t.renewals, t.stop_at), (0, 0, 670))

    def test_stop_wins_same_time_and_no_late_restore(self):
        t = transfer()
        t.tick(435, proof=True, stop=True)
        t.tick(500, proof=True)
        self.assertEqual((t.acquire_attempts, t.stop_at), (0, 435))
        t = transfer()
        t.tick(435, proof=True)
        captured = t.receipt(450, t.key)
        o = m.Observer(t.key)
        o.cancel()  # local Stop / hidden / disconnect all cancel observation
        t.tick(451, stop=True)
        self.assertFalse(o.accept(captured, 499))
        self.assertFalse(o.lease)
        self.assertEqual(t.stop_at, 451)
        t.tick(600, stop=True)
        self.assertEqual(t.stop_at, 451)

    def test_unobserved_external_stop_does_not_assume_client_knowledge(self):
        t = transfer()
        t.tick(435, proof=True)
        captured = t.receipt(450, t.key)
        t.tick(451, stop=True)
        o = m.Observer(t.key)
        self.assertTrue(o.accept(captured, 499))  # client cannot know unseen Stop
        self.assertFalse(t.renew(500, t.key, o.next_sequence()))
        self.assertFalse(t.motion_eligible(501, t.key, explicit=True, approved=True,
                         calibrated=True, ready=True, armed=True, ticket=True, consume_proof=True))

    def test_identity_binding_and_one_shot(self):
        for field in ('boot', 'session', 'principal', 'axis', 'nonce', 'boot_generation'):
            t = transfer()
            wrong = replace(t.key, **{field: getattr(t.key, field) + 1})
            self.assertIsNone(t.receipt(100, wrong))
            self.assertEqual(t.state, 'PENDING')
            t.tick(435, proof=True, key=wrong)
            self.assertEqual(t.acquire_attempts, 0)
            self.assertEqual(t.state, 'CANCELLED')
            self.assertFalse(t.reserve(500, 900, t.key))
        t = transfer()
        t.tick(435, proof=True)
        for now in range(436, 600):
            r = t.receipt(now, t.key)
            self.assertEqual(r.lease_until, 1235)
            t.tick(now, proof=True)
        self.assertEqual(t.acquire_attempts, 1)
        self.assertEqual(t.renewals, 0)

    def test_observer_generation_sequence_and_late_boundaries(self):
        t = transfer()
        t.tick(435, proof=True)
        r = t.receipt(500, t.key)
        for bad in (replace(r, generation=4), replace(r, sequence_floor=0),
                    replace(r, key=replace(r.key, nonce=2))):
            self.assertFalse(m.Observer(t.key).accept(bad, 510))
        self.assertFalse(m.Observer(t.key).accept(r, 510, generation=4))
        self.assertTrue(m.Observer(t.key).accept(r, 510, generation=2))
        o = m.Observer(t.key)
        self.assertTrue(o.accept(r, 510, generation=3))
        self.assertFalse(t.renew(511, t.key, 1))  # server Acquire consumed seq1
        self.assertTrue(t.renew(512, t.key, o.next_sequence()))
        self.assertEqual(t.lease_until, 1312)
        self.assertFalse(m.Observer(t.key).accept(r, 1100))  # snapshot age==600
        self.assertFalse(m.Observer(t.key).accept(replace(r, at=1147), 1147))
        self.assertFalse(m.Observer(t.key, clicked=1000).accept(replace(r, at=1235), 1235))
        self.assertFalse(m.Observer(t.key).accept(r, 499))  # clock mismatch/reversal

    def test_failed_admission_never_retries_and_movement_stays_separate(self):
        t = transfer()
        t.tick(435, proof=True, admission_ok=False)
        t.tick(436, proof=True, admission_ok=True)
        self.assertEqual((t.state, t.acquire_attempts, t.fault_at), ('FAILED', 1, 435))
        t = transfer()
        t.tick(435, proof=True)
        good = dict(explicit=True, approved=True, calibrated=True, ready=True,
                    armed=True, ticket=True, consume_proof=True)
        self.assertTrue(t.motion_eligible(436, t.key, **good))  # positive model control
        for field in good:
            self.assertFalse(t.motion_eligible(437, t.key, **{**good, field: False}))

    def test_invalid_start_overflow_and_renew_expiry(self):
        for options in ({'explicit': False}, {'boot_owner_valid': False}, {'granted_boot': False}):
            self.assertFalse(m.Transfer().reserve(0, 670, m.Key(), **options))
        self.assertFalse(m.Transfer().reserve(0, 670, m.Key(axis=3)))
        self.assertFalse(m.Transfer().reserve(670, 670, m.Key()))
        self.assertFalse(m.Transfer().reserve(m.MAX_TIME-699, m.MAX_TIME, m.Key()))
        t = transfer(m.MAX_TIME, m.MAX_TIME-750)
        t.tick(m.MAX_TIME-749, proof=True)
        self.assertEqual(t.state, 'FAILED')  # 800ms normal lease overflows
        t = transfer()
        t.tick(435, proof=True)
        self.assertFalse(t.renew(1235, t.key, 2))
        self.assertEqual(t.stop_at, 1235)
        self.assertFalse(t.renew(1236, t.key, 3))

    def test_delayed_ack_and_result_observation_are_not_new_authority(self):
        t = transfer()
        t.tick(10, proof=True)  # explicit consent already received server-side
        o = m.Observer(t.key)
        ack = 98  # ACK can be later than grant; no server sleep implied
        received = 348 + 50 + 49 + 49
        self.assertLessEqual(received, m.observation_bound(10, ack))
        self.assertTrue(o.accept(t.receipt(447, t.key), received))
        t.tick(810)
        self.assertFalse(m.Observer(t.key).accept(t.receipt(900, t.key), 949))
        self.assertEqual(t.acquire_attempts, 1)
        t = transfer()
        t.tick(435, proof=True)
        # Result can be observed beyond old local700 while still under the
        # ACTUAL normal lease1235; receipt query must not extend either deadline.
        r = t.receipt(1000, t.key)
        self.assertTrue(m.Observer(t.key).accept(r, 1049))
        self.assertEqual((t.pending_until, t.lease_until, t.acquire_attempts), (670, 1235, 1))
        self.assertFalse(m.Observer(t.key).accept(t.receipt(1147, t.key), 1147))


if __name__ == '__main__':
    unittest.main(verbosity=2)
