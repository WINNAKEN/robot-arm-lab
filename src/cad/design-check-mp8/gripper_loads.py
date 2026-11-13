# -*- coding: utf-8 -*-
"""MP8 — 그리퍼 + 물체를 짐으로 넣어 MP5 부하 계산(joint_loads.py)을 다시 돌린다(MP5 파일은 읽기만).

짐 모형: MP5 는 짐을 「공구 플랜지 앞면 + 0.05 m · 팔 줄 위의 점질량 하나」로 둔다(inputs.json:21-22). 팔을 곧게 편 자세에서 중력 토크는
Σ mᵢ(x_f − x_k + oᵢ) = M(x_f − x_k + c) 이므로, 그리퍼(m_g · 무게중심 o_g)와 물체(m_o · 쥐는 점 o_o)를 질량 M = m_g + m_o · 자리
c = (m_g o_g + m_o o_o) / M 인 점질량 하나로 바꿔도 모든 관절의 중력 항이 같다(J4 의 두 성분도 같은 꼴). 관성 항은 Σ mᵢ(oᵢ − c)² 만큼 작게 잡힌다 —
그 크기를 함께 적는다. J6 의 짐 비킴(0.02 m)은 MP5 가정 그대로 둔다(그리퍼 · 물체 중심이 J6 축 위면 더 작음).

하는 일: inputs.json 사본의 payloads_kg · payload_offset_from_flange_m(· 비관 경우 usable_torque_fraction)만 바꿔 --work 아래에 두고, joint_loads 모듈의
HERE 만 그 폴더로 돌려 main() 을 부른다(ROOT · 다른 입력 · 계산은 그대로). 결과에서 후보 구동 표의 칸을 뽑아 요약한다.
- 그리퍼 질량 · 무게중심 · 쥐는 점 = --gripper (models/kmjh-gripper-v1/mass-properties.json — 출력 준비가 낸다). 쥐는 점은 grasp_cases_z_mm
  (손끝 판 가운데 · 트레이 집기 물체 높이별 — 검토 G04)를 모두 돌려 --work/grasp_z<높이>/{nominal,usable_0.4} 에 둔다.
- 물체 = --object-kg (사용자 결정 G3 「중간 (폭 80 mm · 200 g 이하)」 → 0.2).

사용: python gripper_loads.py --gripper <mass-properties.json> [--object-kg 0.2] [--work <폴더 — 저장소 안>] [--out <요약 json>]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])
MP5 = ROOT / "src" / "cad" / "review-mp5"
WATCH = (("사이클로이드 1 단 27:1", "J4 · J5 · S1(17-40)"), ("사이클로이드 1 단 27:1", "J4 · J5 · S2(17-48)"),
         ("앞단 2:1 + 사이클로이드 27:1 = 54:1", "J4 · J5 · S1(17-40)"),
         ("앞단 5:1 + 사이클로이드 27:1 = 135:1", "J2 · S2(17-48)"), ("앞단 3:1 + 사이클로이드 27:1 = 81:1", "J2 · S4(23-56)"),
         ("앞단 6:1 + 사이클로이드 27:1 = 162:1", "J2 · S2(17-48)"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_joint_loads(inputs, work):
    """inputs(dict)를 work/inputs.json 으로 두고 joint_loads.main() 을 돌린다 — 산출 = work/loads.json."""
    work.mkdir(parents=True, exist_ok=True)
    (work / "inputs.json").write_bytes((json.dumps(inputs, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    spec = importlib.util.spec_from_file_location(f"joint_loads_{work.name}", MP5 / "joint_loads.py")
    jl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jl)
    if jl.ROOT != ROOT:
        raise SystemExit(f"joint_loads 의 ROOT 가 다름: {jl.ROOT}")
    jl.HERE = work
    argv = sys.argv
    try:
        sys.argv = ["joint_loads.py", "--out", str(work)]
        jl.main()
    finally:
        sys.argv = argv
    return json.loads((work / "loads.json").read_text(encoding="utf-8"))


def floor_pct(m):
    """MP5 표(loads.md)와 같은 꼴 — 0.1 % 아래 내림."""
    return math.floor(m * 1000) / 10


def signed_margin(loads, inp, row, col, payload):
    """그 짐에서의 토크 여유(부호 있음 — 모자라면 음수). joint_loads 5b 와 같은 식: 유지 토크 × 쓸 수 있는 비율 × η × R / 필요 − 1."""
    sname, joints = inp["candidate_drives"]["columns"][col]
    sres = loads["results"][next(n for n in loads["results"] if n.startswith(sname + " "))]
    key = next(k for k in sres["payloads"] if abs(float(k) - payload) < 1e-9)
    jr = sres["payloads"][key]
    need = max(jr[j]["required_Nm"] for j in joints)
    usable = inp["usable_torque_fraction"]["value"] if isinstance(inp.get("usable_torque_fraction"), dict) else 0.5
    have = inp["motors"][jr[joints[0]]["motor"]]["holding_Nm"] * usable * row["efficiency"] * row["ratio"]
    return have / need - 1.0


def cells(loads, payload, inp):
    """칸마다: 짐을 견디는지 · 그 짐에서의 여유(margin_pct_at_payload — 부호 있음, 모자라면 음수) · MP5 칸 그대로의 「견딘 가장 큰 짐에서의 여유」.
    통과한 칸은 부호 있는 여유가 MP5 칸 값과 같아야 한다(같은 식을 따로 쓴 것의 대조)."""
    out = {}
    for row in loads["candidate_drives"]:
        for name, col in WATCH:
            if row["name"] == name and col in row["cells"]:
                c = row["cells"][col]
                ok = c is not None and abs(c["max_payload_kg"] - payload) < 1e-9
                sm = signed_margin(loads, inp, row, col, payload)
                if ok and abs(sm - c["margin"]) > 1e-9:
                    raise SystemExit(f"부호 있는 여유가 MP5 칸과 다름: {name} | {col} {sm} vs {c['margin']}")
                if ok != (sm >= 0):
                    raise SystemExit(f"통과 판정과 여유 부호가 다름: {name} | {col}")
                out[f"{name} | {col}"] = {"passes_payload": ok, "max_payload_kg": None if c is None else c["max_payload_kg"],
                                          "margin_pct_at_payload": floor_pct(sm),
                                          "margin_pct_at_max_payload": None if c is None else floor_pct(c["margin"])}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gripper", type=Path, required=True)
    ap.add_argument("--object-kg", type=float, default=0.2)
    ap.add_argument("--work", type=Path, default=ROOT / ".dev" / "mp8-evidence" / "loads-gripper")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    work = a.work.resolve()
    if not work.is_relative_to(ROOT):
        raise SystemExit("--work 는 저장소 안이어야 한다(joint_loads 가 입력 경로를 저장소 기준 상대 경로로 기록)")
    gp = json.loads(a.gripper.read_text(encoding="utf-8"))
    mg = gp["total_mass_g"] / 1000
    og = gp["com_mm"][2] / 1000
    mo = a.object_kg
    M = mg + mo
    base = json.loads((MP5 / "inputs.json").read_text(encoding="utf-8"))
    # 쥐는 점(물체 무게중심) 경우 — mass-properties 의 grasp_cases_z_mm(손끝 판 가운데 · 트레이 집기 높이별). 기본 = grasp_centre_mm
    zs = gp.get("grasp_cases_z_mm") or [gp["grasp_centre_mm"][2]]
    cases = {}
    for zmm in zs:
        oo = zmm / 1000
        c = (mg * og + mo * oo) / M
        inertia_gap = mg * (og - c) ** 2 + mo * (oo - c) ** 2
        runs = {}
        for tag, usable in (("nominal", None), ("usable_0.4", 0.4)):
            inp = json.loads(json.dumps(base))
            inp["payloads_kg"] = [0.0, round(M, 4)]
            inp["payload_offset_from_flange_m"] = {"value": round(c, 5), "note": f"MP8 — 그리퍼 {mg * 1000:.0f} g(무게중심 {og * 1000:.1f} mm) + 물체 {mo * 1000:.0f} g(쥐는 점 {oo * 1000:.1f} mm)의 합성 무게중심 · 플랜지 앞면 기준"}
            if usable is not None:
                inp["usable_torque_fraction"] = {"value": usable, "note": "MP8 비관 경우 — MP5 민감도의 0.5 → 0.4 와 같은 값"}
            loads = run_joint_loads(inp, work / f"grasp_z{zmm:g}" / tag)
            runs[tag] = cells(loads, round(M, 4), inp)
        cases[f"{zmm:g}"] = {"grasp_from_flange_m": oo, "combined": {"mass_kg": M, "offset_from_flange_m": c, "within_payload_0p5": M <= 0.5 + 1e-9,
                                                                  "moment_about_flange_kgm": M * c, "mp5_reference_moment_kgm": 0.5 * 0.05,
                                                                  "inertia_term_underestimate_kgm2": inertia_gap},
                             "cells": runs}
    # 비교 기준: MP5 결정 그대로(0.5 kg · 플랜지 + 0.05 m)의 같은 칸 — MP5 산출(loads.json)에서 읽음
    mp5 = json.loads((ROOT / ".dev" / "mp5-review-evidence" / "loads.json").read_text(encoding="utf-8"))
    ref = {}
    for row in mp5["candidate_drives"]:
        for name, col in WATCH:
            if row["name"] == name and col in row["cells"]:
                cc = row["cells"][col]
                ref[f"{name} | {col}"] = None if cc is None else {"max_payload_kg": cc["max_payload_kg"], "margin_pct_at_max_payload": floor_pct(cc["margin"])}
    summary = {
        "what": "그리퍼 + 물체를 MP5 짐 자리에 넣은 후보 구동 판정(관절 거리 · 팔 질량 모형 = MP5 그대로) — 쥐는 점(물체 무게중심) 높이별",
        "margin_note": "margin_pct_at_payload = 그 짐(그리퍼 + 물체)에서의 토크 여유(부호 있음 — 모자라면 음수 · joint_loads 5b 와 같은 식, 통과 칸은 MP5 값과 같음을 확인) · margin_pct_at_max_payload = MP5 칸 그대로(견딘 가장 큰 짐 — 0 kg 일 수 있음) · 둘 다 MP5 표처럼 0.1 % 아래 내림",
        "default_grasp_z_mm": gp["grasp_centre_mm"][2],
        "gripper": {"mass_kg": mg, "com_from_flange_m": og, "source": str(a.gripper.resolve().relative_to(ROOT)) if a.gripper.resolve().is_relative_to(ROOT) else str(a.gripper),
                    "source_sha256": sha(a.gripper)},
        "object": {"mass_kg": mo, "decision": "G3 「중간 (폭 80 mm · 200 g 이하)」", "grasp_cases_z_mm": zs,
                   "grasp_note": gp.get("grasp_note")},
        "cases": cases,
        "mp5_reference_cells_0p5kg_at_0p05m": ref,
        "inputs_sha256": {"mp5_inputs": sha(MP5 / "inputs.json"), "joint_loads": sha(MP5 / "joint_loads.py"),
                          "mp5_loads": sha(ROOT / ".dev" / "mp5-review-evidence" / "loads.json")},
    }
    text = json.dumps(summary, ensure_ascii=False, indent=1) + "\n"
    out = a.out or (work / "summary.json")
    out.write_bytes(text.encode("utf-8"))
    print(text)


if __name__ == "__main__":
    main()
