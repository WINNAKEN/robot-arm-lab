# -*- coding: utf-8 -*-
"""MP4 A1 검사 — 시험편 STL(부품마다 · 판)이 출력 전 판정을 지나는지 본다. 결과 = `models/fit-coupons-v1/validation.json`(checks 가 모두 참이면
종료 값 0). 판정: 부품마다 닫힘 · 체적 양수 · 셸 하나(속 빈 공간 없음) · 바닥 z = 0 · 판 STL 의 셸 수 = 부품 수 · 판 크기가 H2D 프로필(350 × 320 ×
325 mm — MP1 슬라이스 보고서) 안 · 설계 치수로 계산한 최소 재료 두께 ≥ 1.2 mm(`coupons.json` 의 `min_material_mm`)."""
from __future__ import annotations

import json
from pathlib import Path

import trimesh

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "models" / "fit-coupons-v1"
BED = (350.0, 320.0, 325.0)


def main() -> int:
    info = json.loads((MODEL / "coupons.json").read_text(encoding="utf-8"))
    parts = []
    for name in info["bodies"]:
        m = trimesh.load(MODEL / "parts" / f"{name}.stl", process=True)
        shells = m.split(only_watertight=False)
        parts.append({"body": name, "watertight": bool(m.is_watertight), "volume_mm3": round(float(m.volume), 2), "shells": len(shells),
                      "min_z_mm": round(float(m.bounds[0][2]), 4), "size_mm": [round(float(v), 3) for v in m.extents]})
    plate = trimesh.load(MODEL / "fit-coupons-v1-plate.stl", process=True)
    plate_shells = len(plate.split(only_watertight=False))
    size = [float(v) for v in plate.extents]
    mins = [r["min_material_mm"] for r in info["coupons"] if "min_material_mm" in r]
    checks = {
        "every_part_watertight": all(p["watertight"] for p in parts),
        "every_part_positive_volume": all(p["volume_mm3"] > 0 for p in parts),
        "every_part_one_shell_no_cavity": all(p["shells"] == 1 for p in parts),
        "every_part_on_the_bed": all(abs(p["min_z_mm"]) <= 1e-6 for p in parts),
        "plate_shells_equal_parts": plate_shells == len(parts),
        "plate_inside_h2d_profile": size[0] <= BED[0] and size[1] <= BED[1] and size[2] <= BED[2],
        "min_material_at_least_1_2_mm": min(mins) >= 1.2,
    }
    out = {"checks": checks, "parts": parts, "plate": {"shells": plate_shells, "size_mm": [round(v, 3) for v in size],
                                                        "volume_mm3": round(float(plate.volume), 2)},
           "min_material_mm": min(mins), "bed_profile_mm": BED,
           "not_checked": ["label legibility (engraved, 0.6 mm deep, ≥ 3 mm tall — backup: dots and position)",
                           "actual printed fits (user, after printing — README record sheet)"]}
    (MODEL / "validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
