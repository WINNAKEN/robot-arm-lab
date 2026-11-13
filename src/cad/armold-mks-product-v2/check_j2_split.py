# -*- coding: utf-8 -*-
"""MP4 A3 — `build_j2_split.py` 가 만든 J2 분할을 검사해 `validation.json` 을 쓴다(만들기의 검사 다섯 + 이 파일의 다섯).

사용: python check_j2_split.py [--out <j2-split 폴더>] [--evidence <근거 폴더>]
이 파일의 검사:
- parts_closed_one_shell: 부품마다 정확 커널의 셸 1 · 부피 양수 · 내보낸 STL 이 닫힘(watertight) · 조각 하나.
- j2_boxes_inside_can_bore: J2 의 모터 · 드라이버 · 커넥터 가정 상자(v1 치수)의 모서리 여덟이 뒤 하우징의 빈 속(반지름 = 캔 안 반지름 ·
  z = 끝 덮개 쪽 끝 .. 뒷벽 아랫면) 안 — 수로 계산.
- min_wall_at_least_1_2: 설계 치수로 적은 최소 벽 두께(`split.json` 의 `min_wall_mm`)가 모두 1.2 mm 이상(A1 의 시험편과 같은 하한).
- clearances_positive: 볼트 머리 자리파기와 뒷벽 바깥 모서리 둥글림 · 캔 바깥면 사이의 틈(`split.json` 의 `clearances_mm`)이 모두 양수 — 자리파기가
  둥글림에 걸리면 볼트 머리가 곡면에 앉고, 내보낸 STL 에 찌꺼기 삼각형이 생긴다(2026-10-23 첫 판에서 이 검사기가 잡음).
- print_orientation_for_every_part: 부품마다 출력 방향(판에 닿는 면)이 적혀 있다.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import trimesh

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), Path(r"C:\projects\robot-arm-lab"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "models" / "armold-mks-product-v2" / "j2-split")
    ap.add_argument("--evidence", type=Path, default=ROOT / ".dev" / "product-v2-evidence" / "j2-split")
    a = ap.parse_args()
    split = json.loads((a.out / "split.json").read_text(encoding="utf-8"))
    ev = json.loads((a.evidence / "eval.json").read_text(encoding="utf-8"))
    body = {b["name"]: b for b in ev["bodies"]}

    parts = []
    for name in split["parts"]:
        m = trimesh.load(a.out / "parts" / f"{name}.stl", force="mesh")
        parts.append({"part": name, "kernel_shells": body[name]["kernel"]["shells"], "volume_mm3": round(body[name]["volume_mm3"], 3),
                      "stl_watertight": bool(m.is_watertight), "stl_pieces": len(m.split(only_watertight=False)),
                      "bbox_mm": [round(hi - lo, 3) for hi, lo in zip(body[name]["bbox"]["max"], body[name]["bbox"]["min"])]})

    params = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    z_rear = split["interfaces"]["motor_face"]["z_mm"]
    bore = split["interfaces"]["end_cap"]["can_bore_radius_mm"]
    z_end = body["J2_REAR_HOUSING"]["bbox"]["min"][2]   # 캔의 끝(끝 덮개 쪽) = 뒤 하우징의 가장 낮은 z
    boxes = []
    for name in ("REF_MOTOR_ASSUMED", "REF_DRIVER_ASSUMED", "REF_CONNECTOR_ASSUMED"):
        lo, hi = body[name]["bbox"]["min"], body[name]["bbox"]["max"]
        r = max(math.hypot(x, y) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]))
        boxes.append({"box": name, "corner_radius_mm": round(r, 3), "z_mm": [round(lo[2], 3), round(hi[2], 3)],
                      "inside": r <= bore + 1e-9 and lo[2] >= z_end - 1e-9 and hi[2] <= z_rear + 1e-9})

    build_checks = split["checks"]
    checks = {
        **{f"build_{k}": v for k, v in build_checks.items()},
        "parts_closed_one_shell": all(p["kernel_shells"] == 1 and p["volume_mm3"] > 0 and p["stl_watertight"] and p["stl_pieces"] == 1 for p in parts),
        "j2_boxes_inside_can_bore": all(b["inside"] for b in boxes),
        "min_wall_at_least_1_2": all(v >= 1.2 for v in split["min_wall_mm"].values()),
        "clearances_positive": all(v > 0 for v in split["clearances_mm"].values()),
        "print_orientation_for_every_part": all(n in split["print_orientation"] for n in split["parts"]),
    }
    out = {"checks": checks, "parts": parts, "boxes": boxes, "can_bore_radius_mm": bore, "can_z_mm": [z_end, z_rear],
           "min_wall_mm": split["min_wall_mm"], "clearances_mm": split["clearances_mm"], "status": params["j2_split"]["fit_status"]}
    (a.out / "validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=1))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
