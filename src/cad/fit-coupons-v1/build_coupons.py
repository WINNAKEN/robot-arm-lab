# -*- coding: utf-8 -*-
"""MP4 A1 — H2D · PLA 끼움 시험편 세트(1:1). 판 위 배치 그대로 만든다(모두 바닥 z = 0 · 구멍 축은 Z — ③ 의 가로 구멍 묶음만 Y).

사용: python build_coupons.py --cli <solidcraft-cli.exe> [--out <폴더>] [--evidence <폴더>]
산출(out): native `fit-coupons-v1.solidcraft` · 판 STL(셸 여럿 — PrintForge 출력 준비의 입력) · `parts/<시험편>.stl` · STEP · `iso.png` · `top.png` ·
`coupons.json`(시험편마다 치수 · 구멍 축과 Z 의 각도 · 표시 · 설계 치수로 계산한 최소 재료 두께) · `build-commands.json`.
근거(evidence): 실행 결과 JSON · 표준 오류. 치수의 출처는 계획 `docs/design/014-…` 의 A1."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ap = argparse.ArgumentParser()
ap.add_argument("--cli", required=True, type=Path)
ap.add_argument("--out", type=Path, default=ROOT / "models" / "fit-coupons-v1")
ap.add_argument("--evidence", type=Path, default=ROOT / ".dev" / "fit-coupons-evidence" / "build")
args = ap.parse_args()
OUT, EV = args.out, args.evidence
(OUT / "parts").mkdir(parents=True, exist_ok=True)
EV.mkdir(parents=True, exist_ok=True)

cmds, table, bodies = [], [], []
LABEL_H, LABEL_D = 3.5, 0.6     # 글자 높이 · 새김 깊이


def cmd(c, **p):
    cmds.append({"command": c, "params": p})


def plane(name, x, y, z):
    cmd("sketch.create", name=name, plane={"origin": [x, y, z], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})


def rr_block(name, x, y, w, d, h, r, new=True):
    """바닥 중심 (x, y) · 크기 w × d × h · 모서리 반지름 r 의 둥근 사각 덩어리."""
    plane(name + "_P", x, y, 0)
    cmd("sketch.rectangle.rounded", p0=[-w / 2, -d / 2], p1=[w / 2, d / 2], radius=r)
    cmd("sketch.finish")
    cmd("solid.extrude", distance=h, operation="new", body_name=name, name=name + "_X")
    if new:
        bodies.append(name)


def disc(name, x, y, z0, h, r, new=True):
    cmd("solid.cylinder", radius=r, height=h, base=[x, y, z0], axis="Z", operation="new", body_name=name, name=name + "_C")
    if new:
        bodies.append(name)


def hole_z(body, x, y, ztop, depth, dia, tag):
    """윗면 ztop 에서 아래로 지름 dia · 깊이 depth 구멍(관통이면 depth = 높이)."""
    plane(f"{body}_H_{tag}", x, y, ztop)
    cmd("sketch.circle.center", center=[0, 0], radius=dia / 2)
    cmd("sketch.finish")
    cmd("solid.extrude", distance=depth, direction="negative", operation="cut", targets=[body], name=f"{body}_HOLE_{tag}")


def engrave(body, x, y, ztop, text, h=LABEL_H):
    plane(f"{body}_T_{len(cmds)}", x, y, ztop)
    cmd("sketch.text", text=text, at=[0, 0], height=h)
    cmd("sketch.finish")
    cmd("solid.extrude", distance=LABEL_D, direction="negative", operation="cut", targets=[body], name=f"{body}_LABEL_{len(cmds)}")


# ---- ① NEMA17 장착면 판 셋: 두께 3 · 파일럿 관통 구멍 · M3 통과 Ø3.4 네 개(31 mm 정사각) ----
for i, delta in enumerate((0.15, 0.30, 0.45)):
    name = f"C1_NEMA17_PLATE_{i + 1}"
    x, y = -90 + i * 50, 85
    rr_block(name, x, y, 46, 46, 3, 4)
    hole_z(name, x, y, 3, 3, 22 + delta, "PILOT")
    for sx in (-1, 1):
        for sy in (-1, 1):
            hole_z(name, x + sx * 15.5, y + sy * 15.5, 3, 3, 3.4, f"M3_{sx}{sy}")
    engrave(name, x - 8, y - 22, 3, f"{22 + delta:.2f}")
    table.append({"body": name, "test": "NEMA17 pilot Ø22 boss (through hole) + M3 clearance on 31 mm square", "pilot_dia_mm": round(22 + delta, 2),
                  "m3_clearance_dia_mm": 3.4, "thickness_mm": 3, "hole_axis_vs_z_deg": 0, "label": f"{22 + delta:.2f}",
                  # 두께 3 · 판 가장자리–M3 구멍 23 − 15.5 − 1.7 = 5.8 · 파일럿–M3 구멍 21.92 − (22 + δ)/2 − 1.7 ≥ 8.99
                  "min_material_mm": round(min(3.0, 23 - 15.5 - 1.7, (2 * 15.5 ** 2) ** 0.5 - (22 + delta) / 2 - 1.7), 2),
                  "mating_part": "NEMA17 motor (not on hand)"})

# ---- ② 608(d × D × B = 8 × 22 × 7) 바깥 고리 자리 — 높이 5 ----
for i, delta in enumerate((0.00, 0.10, 0.20, 0.30)):
    name = f"C2_BEARING_608_SEAT_{i + 1}"
    x, y, ring_od, h = -90 + i * 35, 25, 30.0, 5.0
    disc(name, x, y, 0, h, ring_od / 2)
    rr_block(name + "_TAB", x, y - ring_od / 2 - 3, 14, 10, h, 2, new=False)
    cmd("solid.combine", target=name, tools=[name + "_TAB"], operation="join")
    hole_z(name, x, y, h, h, 22.0 + delta, "SEAT")
    label = f"{delta:+.1f}" if delta else "0.0"
    engrave(name, x - 5.5, y - ring_od / 2 - 6, h, label, h=3.0)
    table.append({"body": name, "test": "bearing 608 outer-ring seat (press fit)", "seat_dia_mm": round(22.0 + delta, 2), "bearing": "608 8x22x7",
                  "height_mm": h, "hole_axis_vs_z_deg": 0, "label": label, "min_material_mm": round((ring_od - 22.0 - delta) / 2, 2),
                  "mating_part": "608 bearing (not on hand)"})

# ---- ③ M3 구멍 덩어리(높이 10): 세로 + 같은 아홉을 가로로 ----
name = "C3_M3_HOLE_BLOCK"
bx, by = 85, 85
rr_block(name, bx, by, 64, 26, 10, 2)
groups = [("C", (3.2, 3.4, 3.6), 10, "M3 clearance", "M3 bolt (not on hand)"),
          ("T", (2.5, 2.7, 2.9), 8, "M3 self-tap", "M3 bolt (not on hand)"),
          ("I", (4.0, 4.2, 4.4), 8, "M3 heat-set insert", "M3 heat-set insert (on hand — length unknown; depth 8 fits up to 5.7)")]
k = 0
for g, dias, depth, what, mate in groups:
    for dia in dias:
        hx = bx - 27 + k * 6.75
        hole_z(name, hx, by + 6, 10, depth, dia, f"V{k}")
        cmd("sketch.create", name=f"{name}_HS{k}", plane={"origin": [hx, by - 13, 5], "x_dir": [1, 0, 0], "y_dir": [0, 0, 1]})
        cmd("sketch.circle.center", center=[0, 0], radius=dia / 2)
        cmd("sketch.finish")
        cmd("solid.extrude", distance=10, direction="negative", operation="cut", targets=[name], name=f"{name}_HOLE_H{k}")
        table.append({"body": name, "test": what, "hole_dia_mm": dia, "depth_mm": depth, "hole_axis_vs_z_deg": 0,
                      "position_mm": [round(hx - bx, 2), 6], "label": g, "mating_part": mate})
        table.append({"body": name, "test": what + " (horizontal)", "hole_dia_mm": dia, "depth_mm": 10, "hole_axis_vs_z_deg": 90,
                      "position_mm": [round(hx - bx, 2), -13], "label": g, "mating_part": mate})
        k += 1
for i, (g, _, _, _, _) in enumerate(groups):
    engrave(name, bx - 24 + i * 20.25, by - 4, 10, g)
# 구멍 사이(6.75 − 4.4) · 막힌 구멍 밑바닥(높이 10 − 깊이 8) · 가로 구멍의 위아래((10 − 4.4) / 2) 가운데 가장 얇은 곳(MP4 L4 R1 F3 — 바닥을 빠뜨렸었다)
table.append({"body": name, "test": "block material between holes and under the blind holes",
              "min_material_mm": round(min(6.75 - 4.4, 10 - 8, (10 - 4.4) / 2), 2)})

# ---- ④ 링 · 덮개 미끄럼 끼움: 속 빈 Ø40 보스 + 고리 셋(반지름 틈 0.10 / 0.20 / 0.30 · 점 1 / 2 / 3) ----
name = "C4_SLIP_BOSS_40"
sx, sy = -90, -105
disc(name, sx, sy, 0, 3, 24)
disc(name + "_BOSS", sx, sy, 3, 5, 20, new=False)
cmd("solid.combine", target=name, tools=[name + "_BOSS"], operation="join")
hole_z(name, sx, sy, 8, 8, 32, "CORE")
table.append({"body": name, "test": "slip-fit boss Ø40 (hollow)", "boss_dia_mm": 40, "hole_axis_vs_z_deg": 0, "min_material_mm": 4.0,
              "mating_part": "C4 slip rings (printed)"})
for i, clr in enumerate((0.10, 0.20, 0.30)):
    rn = f"C4_SLIP_RING_{i + 1}"
    rx = -35 + i * 50
    disc(rn, rx, sy, 0, 4, 23)
    hole_z(rn, rx, sy, 4, 4, 40 + 2 * clr, "BORE")
    for k2 in range(i + 1):
        hole_z(rn, rx - 2 + k2 * 2, sy - 21.5, 4, 0.5, 1.0, f"DOT{k2}")
    table.append({"body": rn, "test": "slip ring on Ø40 boss", "bore_dia_mm": round(40 + 2 * clr, 2), "radial_clearance_mm": clr,
                  "hole_axis_vs_z_deg": 0, "label": f"{i + 1} dot(s)", "min_material_mm": round((46 - 40 - 2 * clr) / 2, 2),
                  "mating_part": "C4 boss (printed)"})

# ---- ⑤ D 자 구멍 판(두께 5): D6 핀용 · 틈 0.10 / 0.20 / 0.30 + D6 핀 둘 ----
# 모터 축 D5 줄은 첫 슬라이스가 1.5 시간을 넘어(5494 s) 계획의 자를 차례 첫째로 뺐다(모터도 지금 없음).
name = "C5_D_HOLE_PLATE"
dx, dy = 105, 25
rr_block(name, dx, dy, 60, 18, 5, 3)
for row, (r_nom, flat_nom, tag, mate) in enumerate(((3.0, 5.0, "D6", "C5 D pins (printed)"),)):
    for i, clr in enumerate((0.10, 0.20, 0.30)):
        r, flat = r_nom + clr, flat_nom + 2 * clr
        yf = flat - r
        xf = (r * r - yf * yf) ** 0.5
        hx, hy = dx - 18 + i * 18, dy + 2
        plane(f"{name}_DP_{tag}{i}", hx, hy, 5)
        cmd("sketch.line", points=[[-xf, yf], [xf, yf]])
        cmd("sketch.arc.three_point", start=[xf, yf], end=[-xf, yf], through=[0, -r])
        cmd("sketch.finish")
        cmd("solid.extrude", distance=5, direction="negative", operation="cut", targets=[name], name=f"{name}_D_{tag}_{i}")
        table.append({"body": name, "test": f"D hole for {tag}", "radius_mm": round(r, 2), "flat_to_far_side_mm": round(flat, 2), "clearance_mm": clr,
                      "hole_axis_vs_z_deg": 0, "label": f"{tag} column {i + 1}", "mating_part": mate})
engrave(name, dx - 27, dy - 7.5, 5, "D6", h=3.0)
for i in range(2):
    pn = f"C5_D_PIN_6_{i + 1}"
    px, py = 100, -35 - i * 14
    xf = (3.0 ** 2 - 2.0 ** 2) ** 0.5      # 반지름 3 · 중심에서 평면까지 2 → 평면에서 먼 쪽까지 5
    cmd("sketch.create", name=pn + "_P", plane={"origin": [px - 10, py, 2.0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]})
    cmd("sketch.line", points=[[-xf, -2.0], [xf, -2.0]])
    cmd("sketch.arc.three_point", start=[xf, -2.0], end=[-xf, -2.0], through=[0, 3.0])
    cmd("sketch.finish")
    cmd("solid.extrude", distance=20, operation="new", body_name=pn, name=pn + "_X")
    bodies.append(pn)
    table.append({"body": pn, "test": "D pin Ø6 / flat 5 (printed lying on its flat)", "length_mm": 20, "hole_axis_vs_z_deg": 90,
                  "min_material_mm": 5.0, "mating_part": "C5 D6 holes (printed)"})

for b in bodies:
    cmd("file.export", path=str(OUT / "parts" / f"{b}.stl"), bodies=[b])
cmd("component.list", compact=True, bodies=True)
script = OUT / "build-commands.json"
script.write_text(json.dumps({"commands": cmds}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
native = OUT / "fit-coupons-v1.solidcraft"
env = dict(os.environ, SOLIDCRAFT_GPU="cpu")
p = subprocess.run([str(args.cli), "run", str(script), "--save", str(native), "--out", str(OUT / "fit-coupons-v1-plate.stl"),
                    "--out", str(OUT / "fit-coupons-v1.step"), "--results", "--json-out", str(EV / "build-result.json")],
                   capture_output=True, text=True, encoding="utf-8", timeout=900, env=env)
(EV / "build-stderr.txt").write_text(p.stderr, encoding="utf-8")
if p.returncode:
    raise SystemExit(f"build rc {p.returncode}: {p.stderr[-1500:]}")
(OUT / "coupons.json").write_text(json.dumps({"units": "mm", "bodies": bodies, "coupons": table}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for view in ("iso", "top"):
    s = subprocess.run([str(args.cli), "snapshot", "--in", str(native), "--out", str(OUT / f"{view}.png"), "--view", view, "--width", "1600",
                        "--height", "1200", "--no-axes"], capture_output=True, text=True, encoding="utf-8", timeout=900, env=env)
    if s.returncode:
        raise SystemExit(f"snapshot {view} rc {s.returncode}: {s.stderr[-800:]}")
print(json.dumps({"native": str(native), "bodies": len(bodies), "coupons": len(table)}))
