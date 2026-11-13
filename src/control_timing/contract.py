"""031 reference policy, NOT the firmware Owner/Gate or a hardware simulator.

All times share a virtual monotonic millisecond clock. Proof/admission are
explicit oracle inputs; this module cannot establish their physical validity.
"""
from dataclasses import dataclass

MAX_TIME = (1 << 64) - 1
PENDING_MS = 700
LEASE_MS = 800
POLL_MS = 250
FRESH_MS = 600
LEG_MS = 49
JITTER_MS = 50
OBSERVE_MS = LEG_MS + PENDING_MS + POLL_MS + JITTER_MS + 2 * LEG_MS


def observation_bound(grant, ack, poll=POLL_MS, jitter=JITTER_MS,
                      query_request=LEG_MS, query_response=LEG_MS):
    return max(grant, ack) + poll + jitter + query_request + query_response


def enough_headroom(grant, observed, command=LEG_MS, margin=0):
    return observed + command + margin < grant + LEASE_MS


@dataclass(frozen=True)
class Key:
    boot: int = 11
    session: int = 1
    principal: int = 101
    axis: int = 1
    nonce: int = 1
    boot_generation: int = 1

    def valid(self):
        return (self.axis in (1, 2) and 0 < self.boot_generation < MAX_TIME - 1
                and all(isinstance(v, int) and 0 < v < MAX_TIME for v in
                        (self.boot, self.session, self.principal, self.nonce)))


@dataclass(frozen=True)
class Receipt:
    key: Key
    state: str
    at: int
    pending_until: int
    generation: int
    grant_at: int = 0
    lease: int = 0
    lease_until: int = 0
    sequence_floor: int = 0


class Transfer:
    """One explicit reservation for one actor lifetime; no speculative retry.

    Actual integration must replace oracle booleans with current Boot evidence,
    actual Run proof AND the actual Gate Acquire result in the same actor turn.
    """
    def __init__(self):
        self.key = None
        self.state = 'NONE'
        self.last_at = 0
        self.boot_until = self.pending_until = 0
        self.grant_at = self.lease = self.lease_until = self.sequence_floor = 0
        self.acquire_attempts = self.renewals = self.reads = 0
        self.stop_at = self.fault_at = None
        self.reason = ''

    def reserve(self, now, boot_until, key, *, explicit=True,
                boot_owner_valid=True, granted_boot=True):
        if (self.state != 'NONE' or not explicit or not boot_owner_valid
                or not granted_boot or not key.valid() or now < 0
                or now >= boot_until or boot_until > MAX_TIME
                or now > MAX_TIME - PENDING_MS):
            return False
        self.key = key
        self.last_at = now
        self.boot_until = boot_until
        self.pending_until = min(boot_until, now + PENDING_MS)
        self.state = 'PENDING'
        return True

    def halt(self, now, state, reason):
        if self.stop_at is None:
            self.stop_at = now
            self.reason = reason
        self.state = state
        self.lease = self.lease_until = 0

    def tick(self, now, *, proof=False, admission_ok=True, stop=False, key=None):
        if self.state == 'NONE':
            return
        if self.stop_at is not None:
            return  # terminal result never re-enters or overwrites first time
        if now < self.last_at:
            self.fault_at = now
            self.halt(now, 'FAILED', 'clock')
            return
        self.last_at = now
        if stop or (key is not None and key != self.key):
            self.halt(now, 'CANCELLED', 'stop' if stop else 'identity')
            return
        if self.state == 'PENDING':
            self.pending_until = min(self.pending_until, self.boot_until)
            if now >= self.pending_until:
                self.fault_at = now
                self.halt(now, 'EXPIRED', 'pending-expired')
                return
            if proof:
                self.acquire_attempts += 1
                if not admission_ok or now > MAX_TIME - LEASE_MS:
                    self.fault_at = now
                    self.halt(now, 'FAILED', 'admission')
                    return
                self.state = 'GRANTED'
                self.grant_at = now
                self.lease = 1  # symbolic unique lease within this one-shot model
                self.lease_until = now + LEASE_MS
                self.sequence_floor = 1  # internal Acquire consumed this sequence
        elif self.state == 'GRANTED' and now >= self.lease_until:
            self.halt(now, 'EXPIRED', 'normal-expired')

    def receipt(self, now, key):
        self.tick(now)
        self.reads += 1
        if key != self.key:
            return None
        return Receipt(self.key, self.state, now, self.pending_until,
                       self.key.boot_generation + 2, self.grant_at,
                       self.lease, self.lease_until, self.sequence_floor)

    def renew(self, now, key, sequence):
        self.tick(now)
        if (key != self.key or self.state != 'GRANTED'
                or not self.sequence_floor < sequence < MAX_TIME
                or now > MAX_TIME - LEASE_MS):
            return False
        self.sequence_floor = sequence
        self.lease_until = now + LEASE_MS
        self.renewals += 1
        return True

    def motion_eligible(self, now, key, *, explicit, approved, calibrated,
                        ready, armed, ticket, consume_proof):
        self.tick(now)
        return (self.state == 'GRANTED' and key == self.key and explicit
                and approved and calibrated and ready and armed and ticket
                and consume_proof)


class Observer:
    """Common-clock reference consumer; not deployed PhoneControl code."""
    def __init__(self, key, clicked=0):
        self.key = key
        self.until = clicked + OBSERVE_MS
        self.cancelled = False
        self.lease = self.lease_until = self.sequence = 0

    def cancel(self):
        self.cancelled = True
        self.lease = self.lease_until = 0

    def accept(self, receipt, now, *, generation=None):
        if self.cancelled:
            return False
        if (receipt is None or receipt.key != self.key
                or receipt.state != 'GRANTED' or receipt.lease == 0
                or receipt.generation != self.key.boot_generation + 2
                or generation not in (None, self.key.boot_generation + 1,
                                      self.key.boot_generation + 2)
                or now >= self.until or now < receipt.at
                or now - receipt.at >= FRESH_MS or now >= receipt.lease_until
                or receipt.grant_at >= receipt.pending_until
                or receipt.sequence_floor < 1):
            return False
        self.lease = receipt.lease
        self.lease_until = receipt.lease_until
        self.sequence = max(self.sequence, receipt.sequence_floor)
        return True

    def next_sequence(self):
        self.sequence += 1
        return self.sequence
