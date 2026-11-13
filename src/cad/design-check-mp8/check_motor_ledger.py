# -*- coding: utf-8 -*-
"""MP8 — 모터 실측 원장 형식 검사 + 양성 대조.

검사(하나라도 어긋나면 거부 목록에 올림):
- 머리 키(what · how_to_update · status_words · safety · motor · items · observations · history) · history 한 줄 이상.
- 항목마다 value(숫자 · 글 · null) · unit · status(status_words 의 낱말) · means · source · used_by(비지 않은 목록).
- 숫자 항목의 단위는 mm · kg · N·m 중 하나 · 0 보다 큼.
- source_ref / source_ref_sum([{file, json_path}] — file = 저장소 기준 · json_path = 점으로 이은 키): status assumed 이면
  source_ref 의 각 파일 값 = value · source_ref_sum 의 합 = value(못 읽으면 unreadable · 꼴이 틀리면 form · 다르면 mismatch).
  measured · published 는 모델과 다를 수 있으므로 보지 않는다.
- status = measured 이면 value 가 null 이 아님 · observations 에 그 키의 원문(verbatim)이 하나 이상 · 그 원문 중 하나에 value 의 수가 그대로
  (원문에서 수를 뽑아 같은지 — 140.1 은 40.1 이 아님 · 글 값이면 그 글이 원문에 있음) · history 의 한 줄에 키 이름.
- observations 의 줄마다 set ∈ motor.sets · date(YYYY-MM-DD) · key ∈ items · verbatim 비지 않음.
--controls: 원장 사본(observations 를 비우고 measured · published 항목을 assumed — source_ref 가 있으면 그 모델 값 — 로 되돌린 것)을 메모리에서
하나씩 망가뜨려(파일은 쓰지 않음) 거부 목록이 기대 목록과 정확히 같은지 본다. 사본 자체가 깨끗한지(baseline)도 대조 하나로 본다.

사용: python check_motor_ledger.py [--ledger <원장>] [--controls] [--out <json>]
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])
HEAD = ("what", "how_to_update", "status_words", "safety", "motor", "items", "observations", "history")
ITEM = ("value", "unit", "status", "means", "source", "used_by")
UNITS = {"mm", "kg", "N·m"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NUM = re.compile(r"(?<![\d.])[-+]?\d+(?:\.\d+)?")
EPS = 1e-9


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class Refs:
    """source_ref 파일 읽기(한 번 읽은 파일은 기억)."""

    def __init__(self, root):
        self.root, self.cache = Path(root), {}

    def get(self, ref):
        """ref = {file, json_path} → 값. 못 읽으면 KeyError."""
        f = ref["file"]
        if f not in self.cache:
            p = self.root / f
            self.cache[f] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        node = self.cache[f]
        if node is None:
            raise KeyError(f)
        for k in str(ref["json_path"]).split("."):
            if not isinstance(node, dict) or k not in node:
                raise KeyError(k)
            node = node[k]
        if not is_num(node):
            raise KeyError("not a number")
        return float(node)


def ref_lists(it):
    """[(모드, 목록)] — 모드 each(각각 = value) · sum(합 = value). 꼴이 틀리면 None."""
    out = []
    for field, mode in (("source_ref", "each"), ("source_ref_sum", "sum")):
        if field not in it:
            continue
        refs = it[field]
        if not isinstance(refs, list) or not refs or not all(isinstance(r, dict) and isinstance(r.get("file"), str) and isinstance(r.get("json_path"), str)
                                                            for r in refs):
            return None
        out.append((mode, refs))
    return out


def ref_value(refs, mode, R):
    vals = [R.get(r) for r in refs]
    return sum(vals) if mode == "sum" else vals[0]


def value_in_text(v, text):
    if is_num(v):
        return any(abs(float(t) - float(v)) <= EPS for t in NUM.findall(text))
    return isinstance(v, str) and bool(v.strip()) and v in text


def check(d, root=ROOT):
    bad = []
    for k in HEAD:
        if k not in d:
            bad.append(f"head:{k}")
    if bad:
        return bad
    if not d["history"]:
        bad.append("history:empty")
    words = set(d["status_words"])
    sets = set(d["motor"].get("sets", []))
    R = Refs(root)
    for key, it in d["items"].items():
        for f in ITEM:
            if f not in it:
                bad.append(f"item:{key}:{f}")
        if any(f"item:{key}:{f}" in bad for f in ITEM):
            continue
        if it["status"] not in words:
            bad.append(f"item:{key}:status_word")
        if not isinstance(it["used_by"], list) or not it["used_by"]:
            bad.append(f"item:{key}:used_by")
        v = it["value"]
        if isinstance(v, bool) or not (v is None or isinstance(v, (int, float, str))):
            bad.append(f"item:{key}:value_type")
        if is_num(v):
            if it["unit"] not in UNITS:
                bad.append(f"item:{key}:unit")
            elif v <= 0:
                bad.append(f"item:{key}:nonpositive")
        refs = ref_lists(it)
        if refs is None:
            bad.append(f"item:{key}:source_ref_form")
        elif it["status"] == "assumed":
            for mode, rl in refs:
                try:
                    want = ref_value(rl, mode, R)
                except KeyError:
                    bad.append(f"item:{key}:source_ref_unreadable")
                    continue
                if mode == "each":
                    try:
                        same = all(abs(R.get(r) - float(v)) <= EPS for r in rl) if is_num(v) else False
                    except KeyError:
                        bad.append(f"item:{key}:source_ref_unreadable")
                        continue
                else:
                    same = is_num(v) and abs(want - float(v)) <= EPS
                if not same:
                    bad.append(f"item:{key}:source_ref_mismatch")
        if it["status"] == "measured":
            if v is None:
                bad.append(f"item:{key}:measured_null")
            texts = [str(o.get("verbatim", "")) for o in d["observations"] if o.get("key") == key and str(o.get("verbatim", "")).strip()]
            if not texts:
                bad.append(f"item:{key}:measured_without_observation")
            elif v is not None and not any(value_in_text(v, t) for t in texts):
                bad.append(f"item:{key}:measured_value_not_in_observation")
            if not any(key in str(h) for h in d["history"]):
                bad.append(f"item:{key}:measured_without_history")
    for i, o in enumerate(d["observations"]):
        if o.get("set") not in sets:
            bad.append(f"obs:{i}:set")
        if not DATE.match(str(o.get("date", ""))):
            bad.append(f"obs:{i}:date")
        if o.get("key") not in d["items"]:
            bad.append(f"obs:{i}:key")
        if not str(o.get("verbatim", "")).strip():
            bad.append(f"obs:{i}:verbatim")
    return bad


def control_base(d, root=ROOT):
    """대조용 사본 — observations 를 비우고 measured · published 를 assumed(source_ref 가 있으면 그 모델 값)로 되돌린다."""
    b = copy.deepcopy(d)
    b["observations"] = []
    R = Refs(root)
    for it in b["items"].values():
        if it.get("status") != "assumed":
            for mode, rl in ref_lists(it) or []:
                try:
                    it["value"] = ref_value(rl, mode, R)
                except KeyError:
                    pass
            it["status"] = "assumed"
    return b


def controls(base, root=ROOT):
    """(이름, 망가뜨리는 함수, 기대 거부 목록) — 거부 목록이 정확히 기대와 같아야 통과."""
    k0 = "body_length"
    H = "2026-10-28 body_length 40 → 40.1(세트 A 실측)"

    def noref(d, k=k0):        # 값 규칙만 보려고 그 항목의 source_ref 를 뗀다
        d["items"][k].pop("source_ref", None)
        d["items"][k].pop("source_ref_sum", None)

    def baseline(d):
        pass

    def drop_head(d):
        del d["safety"]

    def empty_hist(d):
        d["history"] = []

    def drop_unit(d):
        del d["items"][k0]["unit"]

    def bad_word(d):
        d["items"][k0]["status"] = "guess"

    def bad_unit(d):
        d["items"][k0]["unit"] = "cm"

    def neg(d):
        noref(d)
        d["items"][k0]["value"] = -1.0

    def boolv(d):
        noref(d)
        d["items"][k0]["value"] = True

    def no_used(d):
        d["items"][k0]["used_by"] = []

    def ref_mismatch(d):
        d["items"][k0]["value"] = 41.0

    def ref_unreadable(d):
        d["items"][k0]["source_ref"][0]["json_path"] = "motor_length_mm_nope"

    def ref_bad_file(d):
        d["items"][k0]["source_ref"][0]["file"] = "models/nope.json"

    def ref_form(d):
        d["items"][k0]["source_ref"] = "models/armold-mks-concept-v1/parameters.json motor_length_mm"

    def ref_sum_mismatch(d):
        d["items"]["mass_motor_with_driver"]["value"] = 0.32

    def measured_no_obs(d):
        d["items"][k0]["status"] = "measured"
        d["history"].append(H)

    def measured_null(d):
        d["items"]["frame_corner_chamfer"]["status"] = "measured"
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": "frame_corner_chamfer", "verbatim": "모서리 3"})
        d["history"].append("2026-10-28 frame_corner_chamfer null → ?")

    def measured_value_not_in_obs(d):
        d["items"][k0].update(value=40.1, status="measured")
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": k0, "verbatim": "장착면→뒷면 40.2"})
        d["history"].append(H)

    def measured_value_substring_only(d):
        d["items"][k0].update(value=40.1, status="measured")
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": k0, "verbatim": "장착면→뒷면 140.1"})
        d["history"].append(H)

    def measured_no_history(d):
        d["items"][k0].update(value=40.1, status="measured")
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": k0, "verbatim": "장착면→뒷면 40.1"})
        d["history"] = ["2026-10-28 다른 줄"]

    def obs_set(d):
        d["observations"].append({"set": "C", "date": "2026-10-28", "key": k0, "verbatim": "40.1"})

    def obs_date(d):
        d["observations"].append({"set": "A", "date": "10/28", "key": k0, "verbatim": "40.1"})

    def obs_key(d):
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": "nope", "verbatim": "40.1"})

    def obs_text(d):
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": k0, "verbatim": "  "})

    def good_measured(d):   # 음성 대조: 원문 · history 가 있는 measured 는 source_ref(40)와 달라도 통과해야 한다
        d["items"][k0].update(value=40.1, status="measured")
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": k0, "verbatim": "장착면→뒷면 40.10"})
        d["observations"].append({"set": "B", "date": "2026-10-28", "key": k0, "verbatim": "장착면→뒷면 40.0"})
        d["history"].append(H)

    def good_measured_text(d):   # 음성 대조: 글 값
        d["items"]["label_text"].update(value="MKS SERVO42D", status="measured")
        d["observations"].append({"set": "A", "date": "2026-10-28", "key": "label_text", "verbatim": "라벨: MKS SERVO42D CAN V1.0"})
        d["history"].append("2026-10-28 label_text null → 라벨 글")

    i = f"item:{k0}"
    cases = [("baseline_clean", baseline, []),
             ("drop_head", drop_head, ["head:safety"]), ("empty_history", empty_hist, ["history:empty"]),
             ("drop_unit", drop_unit, [f"{i}:unit"]), ("bad_status_word", bad_word, [f"{i}:status_word"]),
             ("bad_unit", bad_unit, [f"{i}:unit"]), ("negative", neg, [f"{i}:nonpositive"]),
             ("bool_value", boolv, [f"{i}:value_type"]), ("no_used_by", no_used, [f"{i}:used_by"]),
             ("source_ref_mismatch", ref_mismatch, [f"{i}:source_ref_mismatch"]),
             ("source_ref_bad_path", ref_unreadable, [f"{i}:source_ref_unreadable"]),
             ("source_ref_bad_file", ref_bad_file, [f"{i}:source_ref_unreadable"]),
             ("source_ref_form", ref_form, [f"{i}:source_ref_form"]),
             ("source_ref_sum_mismatch", ref_sum_mismatch, ["item:mass_motor_with_driver:source_ref_mismatch"]),
             ("measured_without_obs", measured_no_obs, [f"{i}:measured_without_observation"]),
             ("measured_null", measured_null, ["item:frame_corner_chamfer:measured_null"]),
             ("measured_value_not_in_obs", measured_value_not_in_obs, [f"{i}:measured_value_not_in_observation"]),
             ("measured_value_substring_only", measured_value_substring_only, [f"{i}:measured_value_not_in_observation"]),
             ("measured_without_history", measured_no_history, [f"{i}:measured_without_history"]),
             ("obs_bad_set", obs_set, ["obs:0:set"]), ("obs_bad_date", obs_date, ["obs:0:date"]),
             ("obs_bad_key", obs_key, ["obs:0:key"]), ("obs_blank_text", obs_text, ["obs:0:verbatim"]),
             ("good_measured_passes", good_measured, []), ("good_measured_text_passes", good_measured_text, [])]
    res = []
    for name, fn, want in cases:
        d = copy.deepcopy(base)
        fn(d)
        got = check(d, root)
        res.append({"case": name, "want": want, "got": got, "ok": got == want})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=ROOT / "src" / "cad" / "calibration" / "motor-mks42d.json")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    d = json.loads(a.ledger.read_text(encoding="utf-8"))
    bad = check(d)
    out = {"ledger_ok": not bad, "rejections": bad}
    if a.controls:
        cs = controls(control_base(d))
        out["controls_base"] = "원장 사본 — observations 비움 · measured / published 는 assumed(source_ref 가 있으면 그 모델 값)로 되돌림 · 파일은 쓰지 않음"
        out["controls"] = cs
        out["controls_ok"] = all(c["ok"] for c in cs)
        out["controls_summary"] = f"{sum(c['ok'] for c in cs)} / {len(cs)} ok"
    text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_bytes(text.encode("utf-8"))
    print(text)
    if bad or (a.controls and not out["controls_ok"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
