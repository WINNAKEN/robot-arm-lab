# -*- coding: utf-8 -*-
"""README 의 {PARTS_TABLE} · {FIT_TABLE} 을 산출물(print-plate.json · assembly-checks.json · print_prep_report.json)에서 채운다 — 손으로 옮겨 적지 않게.

사용: python fill_readme.py --template README.md --plate <print-plate.json> --assembly <assembly-checks.json> --prep <print_prep_report.json> --out <README.md>
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROLE = {
    "HOUSING_BASE": "아래 하우징 — 바닥판(모터 · 고정 핀) + 벽", "HOUSING_CAP": "덮개 — 고정 핀 윗끝 · 6808 자리", "RETAINER": "누름 고리 — 6808 바깥 고리",
    "DISC_1": "원판(같은 부품 둘 · 둘째는 180° 돌려 끼움)", "CARRIER": "출력 캐리어 — 출력 핀 · 6800 · 6808 속 고리", "OUTPUT_FLANGE": "출력 플랜지 — 6808 속 고리를 누름",
    "CAM_LOWER": "편심 축 아래 — 허브 + 편심 1", "CAM_UPPER": "편심 축 위 — 간격 고리 + 편심 2 + 저널", "FIT_STRIP": "맞춤 확인 판",
    "WASHER_T2p0": "와셔 2.0(6801 #2 ↔ 6800 속 고리 · 셋 중 맞는 것 하나)", "WASHER_T2p2": "와셔 2.2(기본)", "WASHER_T2p4": "와셔 2.4",
    "GAUGE": "끼움 게이지 0.6(아래 편심 축 높이 — 모터만 있을 때 쓰고 뺀다)",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", type=Path, required=True)
    ap.add_argument("--plate", type=Path, required=True)
    ap.add_argument("--assembly", type=Path, required=True)
    ap.add_argument("--prep", type=Path, required=True)
    ap.add_argument("--calc", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, default=Path(__file__).resolve().parent.parent / "calibration" / "print-fits.json")
    a = ap.parse_args()
    plate = json.loads(a.plate.read_text(encoding="utf-8"))
    asm = json.loads(a.assembly.read_text(encoding="utf-8"))
    prep = json.loads(a.prep.read_text(encoding="utf-8"))
    count = {}
    size = {}
    for p in plate["parts"]:
        base = p["name"].split("#")[0]
        count[base] = count.get(base, 0) + 1
        b = p["bounds_mm"]
        size[base] = [b[1][i] - b[0][i] for i in range(3)]
    rows = ["| 부품 | 쓰임 | 개수 | 크기 mm(x × y × 높이) |", "|---|---|---|---|"]
    for name, n in count.items():
        s = size[name]
        rows.append(f"| `{name}` | {ROLE.get(name, '')} | {n} | {s[0]:.2f} × {s[1]:.2f} × {s[2]:.2f} |")
    est = prep.get("estimate") or {}
    secs = est.get("print_time_s")
    rows += ["", f"한 판 {plate['plate_size_mm'][0]:.1f} × {plate['plate_size_mm'][1]:.1f} mm · Bambu Studio 미리 슬라이스: 판정 `{prep.get('verdict')}` · 지지대 권고 "
                 f"{'있음' if prep.get('support', {}).get('advised_by_studio') else '없음'} · 예상 "
                 f"{int(secs // 3600)} 시간 {int(secs % 3600 // 60)} 분 · {est.get('filament_g')} g · {est.get('filament_m')} m"
                 f"(프로필 {prep['profiles']['printer']} · {prep['profiles']['process']} · {prep['profiles']['filament']} · {prep['plate']['used']})."]
    fit = ["| 자리 | 시험 | 지름 mm | 판정 |", "|---|---|---|---|"]
    for r in asm["small_parts"]:
        if "xy" not in r:
            continue
        extra = f" · 평면 {r['flat_to_axis']:.2f}" if "flat_to_axis" in r else ""
        fit.append(f"| ({r['xy'][0]:g}, {r['xy'][1]:g}) | {r['feature']} | {r['dia']:.2f}{extra} | |")
    zs = asm["stack_mm"]
    calc = json.loads(a.calc.read_text(encoding="utf-8"))
    t = a.template.read_text(encoding="utf-8")
    for key in ("{PARTS_TABLE}", "{FIT_TABLE}", "{HEIGHT}"):
        assert key in t, key
    t = t.replace("{PARTS_TABLE}", "\n".join(rows)).replace("{FIT_TABLE}", "\n".join(fit)).replace("{HEIGHT}", f"{zs['output_face']:.1f}")
    st, ad, bs = calc["stack_mm"], calc["assembly_datum"], calc["ring_contacts"]
    gp = calc["gaps"]
    fill = {"{RING_PIN_LEN}": f"{st['ring_pin'][1] - st['ring_pin'][0]:g}", "{OUTPUT_PIN_LEN}": f"{st['output_pin'][1] - st['output_pin'][0]:g}",
            "{RING_PIN_IN_BASE}": f"{ad['ring_pin_pressed_in_base_mm']:.2f}", "{RING_PIN_INTO_CAP}": f"{ad['ring_pin_into_cap_mm']:.2f}",
            "{WASHER_DATUM}": f"{ad['washer_top_minus_base_wall_top_mm']:.2f}", "{GAUGE_GAP}": f"{ad['lower_cam_hub_above_pilot_mm']:.1f}",
            "{DISC_HEAD_GAP}": f"{gp['disc1_to_motor_screw_head_axial']['mm']:.1f}",
            "{SLID_GAP}": f"{gp['disc1_to_motor_screw_head_if_lower_cam_on_pilot_axial']['mm']:.1f}",
            "{RING_MIN}": f"{calc['ring_section_factors']['min']:g}", "{RING_MAX}": f"{calc['ring_section_factors']['max']:g}",
            "{RING_OVERLAP_MIN}": f"{min(x['sure_overlap_mm'] for x in bs):.2f}"}
    fc = calc["fit_calibration"]     # 값은 이 판을 만든 계산에서 · 상태는 지금 원장에서(상태만 바뀌면 README 만 다시 채운다)
    ledger = json.loads(a.ledger.read_text(encoding="utf-8"))["materials"][fc["material"]]["values"]
    word = {"placeholder": "임시값(시험 전)", "provisional": "시험함 · 확정 전", "confirmed": "확정"}
    cal = [f"재료 **{fc['material']}**(원장 `{fc['ledger']}`).", "", "| 값 | mm | 상태 | 근거 |", "|---|---|---|---|"]
    for k, v in fc["values"].items():
        assert ledger[k]["value"] == v, f"{k}: the ledger now says {ledger[k]['value']} but this plate was built with {v} - run make_all.py --from calc"
        cal.append(f"| `{k}` | {v:g} | {word.get(ledger[k]['status'], ledger[k]['status'])} | {ledger[k]['source']} |")
    fill["{FIT_CALIBRATION}"] = "\n".join(cal)
    for key, val in fill.items():
        assert key in t, key
        t = t.replace(key, val)
    for name, sc in calc["screws"].items():
        assert "{SCREW_" + name + "}" in t, name
        t = t.replace("{SCREW_" + name + "}", f"{sc['length_mm']}").replace("{ENGAGE_" + name + "}", f"{sc['engagement_mm']:.1f}")
    assert "{" not in t.replace("{{", ""), "placeholder left"
    a.out.write_bytes(t.encode("utf-8"))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
