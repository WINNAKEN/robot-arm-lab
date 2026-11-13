# -*- coding: utf-8 -*-
"""계획 029 에 손으로 옮겨 쓴 수(쌓임 표 · 핀 길이 · 원판 틈 · 게이지 · 와셔 안지름 · 캐리어 판 · 덮개 나사 · 고리 단면 가정 · 형상 검사 물림)가
계산 산출 · 매개변수와 같은가 — 기대 문구를 산출에서 만들어 계획 본문에 그대로 있는지 본다. 종료 코드 0 = 모두 있음.

사용: python check_plan_sync.py --calc <cycloid.json> [--plan <029 문서>] [--out <json>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cycloid as cy  # noqa: E402
import verify_geometry as vg  # noqa: E402


def f(v):
    return f"{round(float(v), 2):g}"


def rng(z, k):
    return f"{f(z[k][0])} ~ {f(z[k][1])}"


def expected(c, P):
    z, sc = c["stack_mm"], c["screws"]
    g, ad, gp = P["disc"]["axial_gap"], c["assembly_datum"], c["gaps"]
    pin_len = z["ring_pin"][1] - z["ring_pin"][0]
    stack_rows = {
        "모터 파일럿 · 바닥판 · 나사 머리": f"{f(z['motor_face'])} ~ {f(z['motor_pilot_top'])} · {f(z['motor_face'])} ~ {f(z['base_top'])} · {rng(z, 'motor_screw_head')}",
        "아래 편심 축(허브 · 편심 1)": f"{rng(z, 'cam_hub')} · {rng(z, 'lobe1')}",
        "원판 1 · 6801 #1": f"{rng(z, 'disc1')} · {rng(z, 'disc_bearing1')}",
        "위 편심 축(간격 고리 · 편심 2 · 저널)": f"{rng(z, 'cam_spacer')} · {rng(z, 'lobe2')} · {rng(z, 'journal')}",
        "원판 2 · 6801 #2": f"{rng(z, 'disc2')} · {rng(z, 'disc_bearing2')}",
        "와셔(기본 2.2)": rng(z, "washer"),
        "아래 하우징 윗면 = 덮개 밑 = 캐리어 판 밑": f(z["joint"]),
        "캐리어 판 · 6800 · 오목": f"{rng(z, 'carrier_plate')} · {rng(z, 'shaft_bearing')} · {rng(z, 'seat_relief')}",
        "고정 핀 · 덮개의 핀 구멍": f"{rng(z, 'ring_pin')} · {rng(z, 'ring_pin_hole_cap')}",
        "덮개 턱 · 캐리어 턱 · 6808": f"{rng(z, 'cap_lip')} · {rng(z, 'collar')} · {rng(z, 'output_bearing')}",
        "누름 고리 · 출력 플랜지": f"{rng(z, 'retainer')} · {rng(z, 'flange')}",
    }
    phrases = [f"| {k} | {v} |" for k, v in stack_rows.items()]
    phrases += [
        f"고정 핀 구멍 {rng(z, 'ring_pin_hole_base')}(바닥 {f(z['ring_pin_hole_base'][0])})",
        f"| 출력 면 {f(z['output_face'])} |",
        f"Ø4 강철 다월 × **{f(pin_len)}**",
        f"강철 다월 Ø4 × {f(pin_len)} · 28 개",
        f"Ø4 다월 × **{f(z['output_pin'][1] - z['output_pin'][0])}**(캐리어 판에 압입 {f(z['carrier_plate'][1] - z['carrier_plate'][0])})",
        f"사이 **{g:.1f}**",
        f"원판 1 을 머리 + {gp['disc1_to_motor_screw_head_axial']['mm']:.1f} 위로",
        f"게이지 높이 {f(ad['lower_cam_hub_above_pilot_mm'])} 을 다 잃어도 {f(gp['disc1_to_motor_screw_head_if_lower_cam_on_pilot_axial']['mm'])} 남음",
        f"끼움 게이지 {f(P['gauge']['thickness'])}",
        f"안 Ø{f(2 * c['radii_mm']['washer_in'])}",
        f"판 Ø{f(P['carrier']['plate_dia'])} × {f(P['carrier']['plate_thickness'])}",
        f"M3 × {sc['cap']['length_mm']} 4 개",
        f"d + {f(P['bearings']['ring_section_min_factor'])}(D − d) ≤ 안 고리 바깥지름 ≤ d + {f(P['bearings']['ring_section_factor'])}(D − d)",
        f"선언 단면(원 · D)을 {f(vg.FIT_GAP_MM)} 줄인 기둥 안에 재료 없음",
        f"맞닿는 면에서 {f(vg.FIT_GAP_MM)} 물림",
    ]
    return phrases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calc", type=Path, required=True)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--plan", type=Path, default=cy.DEFAULT_REPO / "docs" / "design" / "029-cycloid-27-prototype.md")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    c = json.loads(a.calc.read_text(encoding="utf-8"))
    P = cy.load_params(a.params)
    text = a.plan.read_text(encoding="utf-8")
    ph = expected(c, P)
    missing = [q for q in ph if q not in text]
    out = {"plan": a.plan.name, "phrases": len(ph), "missing": missing, "pass": not missing}
    print(f"plan sync: {len(ph) - len(missing)}/{len(ph)} phrases found")
    for q in missing:
        print("MISSING", q)
    if a.out:
        a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
