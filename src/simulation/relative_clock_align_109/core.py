"""109 policy only: no clock, process, privilege or transport operations.

Filesystem helpers preserve an exclusive attempt on every post-create failure.
Their parent directory must be an already trusted, locally owned output root;
no path component may be a symlink, junction or other reparse point.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import uuid


PLAN_SHA = "6984878e7e5a10435c230594551017f500c4bed2330f0936d965536a04736b29"
EXPECTED_COMPUTER = "민주환-JUHWANMI"
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")


def need(condition: bool, reason: str) -> None:
    """Only an actual True admits the next operation."""
    if condition is not True:
        raise ValueError(reason)


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def _float(raw: str) -> float:
    result = float(raw)
    need(math.isfinite(result), "nonfinite JSON number")
    return result


def _constant(raw: str) -> None:
    raise ValueError("nonfinite JSON constant: " + raw)


def strict_loads(raw: str | bytes):
    need(type(raw) in (str, bytes), "JSON input must be str or bytes")
    if type(raw) is bytes:
        raw = raw.decode("utf-8", errors="strict")
    return json.loads(raw, object_pairs_hook=_pairs, parse_float=_float,
                      parse_constant=_constant)


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw: bytes) -> str:
    need(type(raw) is bytes, "hash input must be bytes")
    return hashlib.sha256(raw).hexdigest()


def _hash(value, reason: str) -> None:
    need(type(value) is str and _HASH.fullmatch(value) is not None, reason)


def _text(value, reason: str) -> None:
    need(type(value) is str and bool(value.strip()), reason)


def validate_approval(value, plan_hash: str, freeze_hash: str,
                      review_hash: str) -> dict:
    keys = {"unit", "explicit_user_approval", "scope", "hardware_approved",
            "clock_cap_s", "one_adjustment", "plan_sha256",
            "source_freeze_sha256", "review_sha256", "user_quote"}
    need(type(value) is dict and set(value) == keys, "closed109 approval fields")
    need(type(value["unit"]) is str and value["unit"] == "109", "approval unit109")
    need(value["explicit_user_approval"] is True, "explicit user approval required")
    need(value["scope"] == "LOCAL_CLOCK_ALIGN109_ONCE_LE5S"
         and type(value["scope"]) is str, "local clock scope required")
    need(value["hardware_approved"] is False, "hardware stays unapproved")
    need(type(value["clock_cap_s"]) in (int, float)
         and value["clock_cap_s"] == 5, "clock cap exactly5 seconds")
    need(type(value["one_adjustment"]) is int and value["one_adjustment"] == 1,
         "one adjustment exactly int1")
    for key, expected in (("plan_sha256", plan_hash),
                          ("source_freeze_sha256", freeze_hash),
                          ("review_sha256", review_hash)):
        _hash(expected, "invalid reference hash: " + key)
        _hash(value[key], "invalid approval hash: " + key)
        need(value[key] == expected, "approval hash mismatch: " + key)
    _text(value["user_quote"], "actual nonempty user quote required")
    return dict(value)


def validate_l4(value, freeze_hash: str, plan_hash: str) -> None:
    need(type(value) is dict, "L4 object required")
    need(type(value.get("unit")) is str and value.get("unit") == "109", "L4 unit109")
    need(value.get("phase") == "L4" and type(value.get("phase")) is str, "L4 phase")
    need(type(value.get("round")) is int and value["round"] in (1, 2), "L4 round1or2")
    need(value.get("verdict") == "PASS" and type(value.get("verdict")) is str,
         "L4 PASS required")
    need(value.get("non_author") is True and value.get("all_required_met") is True,
         "non-author complete L4 required")
    need(type(value.get("met")) is int and value["met"] == 6
         and type(value.get("unmet")) is int and value["unmet"] == 0,
         "L4 exact6met0unmet")
    _text(value.get("reviewer"), "L4 reviewer required")
    need(value["reviewer"].strip().casefold() != "author", "author cannot review")
    for key, expected in (("actual_freeze_sha256", freeze_hash),
                          ("actual_plan_sha256", plan_hash)):
        _hash(expected, "invalid L4 reference hash: " + key)
        _hash(value.get(key), "invalid L4 hash: " + key)
        need(value[key] == expected, "L4 hash mismatch: " + key)
    criteria = value.get("criteria")
    need(type(criteria) is list and len(criteria) == 6, "six L4 criteria required")
    ids = set()
    for item in criteria:
        need(type(item) is dict, "criterion object required")
        criterion = item.get("id")
        need(type(criterion) is str and criterion in {"AC" + str(i) for i in range(1, 7)}
             and criterion not in ids, "unique AC1through6 required")
        need(item.get("required") is True and item.get("met") is True,
             "every required criterion must be met")
        ids.add(criterion)


def _number(value, reason: str) -> float:
    need(type(value) in (int, float), reason)
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(reason) from error
    need(math.isfinite(result), reason)
    return result


def _tick(value, reason: str) -> None:
    need(type(value) is int and 0 <= value <= 0xFFFFFFFFFFFFFFFF, reason)


def validate_sample(sample, now_tick: int) -> dict:
    keys = {"local_send_unix", "local_receive_unix", "local_elapsed_s",
            "finished_tick_ms", "remote_unix_ms", "computer", "nonce"}
    need(type(sample) is dict and set(sample) == keys, "closed fresh sample fields")
    _tick(now_tick, "current boot tick must be uint64 int")
    _tick(sample["finished_tick_ms"], "sample boot tick must be uint64 int")
    need(type(sample["remote_unix_ms"]) is int, "remote milliseconds must be int")
    need(type(sample["computer"]) is str and sample["computer"] == EXPECTED_COMPUTER,
         "expected peer machine required")
    _text(sample["nonce"], "sample nonce required")
    _number(sample["local_send_unix"], "finite send UTC required")
    _number(sample["local_receive_unix"], "finite receive UTC required")
    _number(sample["local_elapsed_s"], "finite monotonic RTT required")
    _number(sample["remote_unix_ms"], "finite remote milliseconds required")
    # Keep integer milliseconds exact; float cancellation at extreme finite
    # timestamps must not fabricate a small interval or zero correction.
    send = Fraction(sample["local_send_unix"])
    receive = Fraction(sample["local_receive_unix"])
    elapsed = Fraction(sample["local_elapsed_s"])
    remote = Fraction(sample["remote_unix_ms"], 1000)
    wall = receive - send
    need(wall >= 0 and elapsed >= 0, "nonnegative RTT required")
    need(abs(wall - elapsed) <= Fraction(1, 4), "wall/monotonic coherence exceeds0.25s")
    age_ms = now_tick - sample["finished_tick_ms"]
    need(0 <= age_ms <= 5000, "fresh sample age must be0through5s")
    low_exact = remote - receive - Fraction(1, 500)
    high_exact = remote - send + Fraction(1, 500)
    width = high_exact - low_exact
    need(0 <= width <= Fraction(3, 2),
         "uncertainty width exceeds1.5s")
    midpoint_exact = low_exact + width / 2
    need(abs(midpoint_exact) <= 5, "midpoint correction exceeds5s")
    low, high = float(low_exact), float(high_exact)
    if Fraction(low) > low_exact:
        low = math.nextafter(low, -math.inf)
    if Fraction(high) < high_exact:
        high = math.nextafter(high, math.inf)
    return {"low": low, "high": high, "midpoint": float(midpoint_exact),
            "needs_change": not (low_exact >= -1 and high_exact <= 1)}


@dataclass(frozen=True, slots=True)
class Lease:
    start_tick: int
    parent_pid: int
    parent_created: int
    nonce: str

    def __post_init__(self) -> None:
        _tick(self.start_tick, "lease start must be uint64 int")
        need(self.start_tick <= 0xFFFFFFFFFFFFFFFF - 180000, "lease end tick overflow")
        need(type(self.parent_pid) is int and 0 < self.parent_pid <= 0xFFFFFFFF,
             "positive DWORD parent PID required")
        need(type(self.parent_created) is int and 0 < self.parent_created <= 0xFFFFFFFFFFFFFFFF,
             "positive parent creation FILETIME required")
        _text(self.nonce, "lease nonce required")

    @property
    def active_end(self) -> int:
        return self.start_tick + 170000

    @property
    def hard_end(self) -> int:
        return self.start_tick + 180000

    @property
    def uac_end(self) -> int:
        return self.start_tick + 90000

    def _end(self, phase: str) -> int:
        need(type(phase) is str, "lease phase must be str")
        if phase == "uac":
            return self.uac_end
        if phase == "cleanup":
            return self.hard_end
        need(phase in {"active", "sample", "adjust", "verify", "worker", "api"},
             "unknown lease phase")
        return self.active_end

    def check(self, now_tick: int, phase: str = "active") -> None:
        _tick(now_tick, "current boot tick must be uint64 int")
        need(self.start_tick <= now_tick < self._end(phase), "lease phase expired or different boot")

    def remaining_ms(self, now_tick: int, phase: str = "active") -> int:
        self.check(now_tick, phase)
        return self._end(phase) - now_tick


def _not_reparse(info: os.stat_result) -> bool:
    return not stat.S_ISLNK(info.st_mode) and not (
        getattr(info, "st_file_attributes", 0) & 0x400)


def _parents(path: Path) -> tuple:
    """Snapshot all existing directories without resolving away a link."""
    snapshots = []
    for part in reversed(path.parent.parents):
        info = part.lstat()
        need(_not_reparse(info) and stat.S_ISDIR(info.st_mode), "unsafe output ancestor")
        snapshots.append((str(part), info.st_dev, info.st_ino))
    info = path.parent.lstat()
    need(_not_reparse(info) and stat.S_ISDIR(info.st_mode), "unsafe output parent")
    snapshots.append((str(path.parent), info.st_dev, info.st_ino))
    return tuple(snapshots)


def _target(path) -> tuple[Path, tuple]:
    path = Path(path)
    need(path.name not in ("", ".", ".."), "output filename required")
    # Reject ADS, device spellings and Windows trailing-dot/space aliases.
    need(":" not in path.name and path.name == path.name.rstrip(" .")
         and path.stem.upper() not in {"CON", "PRN", "AUX", "NUL",
                                      *{"COM" + str(i) for i in range(1, 10)},
                                      *{"LPT" + str(i) for i in range(1, 10)}},
         "unsafe output filename")
    # GetFullPathName may erase trailing dots/spaces, so validate first.
    path = Path(os.path.abspath(os.fspath(path)))
    return path, _parents(path)


def _open_exclusive(path: Path) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and _not_reparse(info) and info.st_nlink == 1,
             "exclusive output must be a new regular file")
        os.set_inheritable(fd, False)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _write_all(fd: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(fd, raw[offset:])
        need(type(written) is int and 0 < written <= len(raw) - offset,
             "exclusive output write made no progress")
        offset += written
    os.fsync(fd)


def reserve_attempt(path, record) -> None:
    """Durably consume before UAC; never delete/reset a created reservation."""
    raw = canonical(record)
    target, parents = _target(path)
    fd = _open_exclusive(target)
    try:
        need(_parents(target) == parents, "output parent changed during reservation")
        _write_all(fd, raw)
        need(_parents(target) == parents, "output parent changed during reservation")
    finally:
        os.close(fd)


def atomic_result_exclusive(path, record) -> None:
    """Publish a fully fsynced result atomically with no replace/retry fallback."""
    raw = canonical(record)
    target, parents = _target(path)
    temp = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    fd = _open_exclusive(temp)
    try:
        need(_parents(target) == parents, "output parent changed before result write")
        _write_all(fd, raw)
    finally:
        os.close(fd)
    # link() atomically refuses every existing destination, including a link.
    # A failure keeps the consumed attempt outside this function untouched.
    try:
        need(_parents(target) == parents, "output parent changed before result publication")
        os.link(temp, target, follow_symlinks=False)
        need(_parents(target) == parents, "output parent changed during result publication")
    finally:
        # Never follow a swapped directory solely to clean up a temp file.
        if _parents(temp) == parents:
            temp.unlink()
