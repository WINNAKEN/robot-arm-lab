# -*- coding: utf-8 -*-
"""MP8 — 그리퍼 KG1 합격 검사. 커밋된 부품 STL(models/kmjh-gripper-v1/parts)만으로 스스로 계산한다(kg1.py 를 부르지 않는다).

정답의 출처는 parameters.json · 끼움 원장(print-fits.json)이고, 아래 계산은 생성기와 따로 쓴 것이다(MP7 교훈 ① 독립 정답표).
- G0 출처: 부품 STL · native · STEP · 3MF 의 sha256 = 만들기 기록 · 기록의 출력 키 집합 = 독립 기대 집합 · 기록의 입력 sha256 = 지금 파일 ·
  기록의 끼움 값 = 원장 · 출력 준비 기록(print-prep.json)의 부품 · 판 STL · 슬라이서 파일 sha256 과 질량 기록의 부품 sha256 = 지금 파일 · 만들기 도구(CLI 판 · sha256) 기록.
- G1 부품 목록(독립 표) · 모두 닫힌 메시 · 부피 > 0.
- G2 조립 간섭(표본 u 여섯 · 손끝 두 벌): 고정 받침 · 턱 A(−u) · 턱 B(+u) · 피니언(θ = −u / r, +y 축) · 손끝(턱과 함께) · 기준 입체(서보 몸체 · 커넥터 자리 · 혼 ·
  혼 나사 머리 · 서보 M2 머리 · 몸통 · 피니언 M3 머리 · 몸통 · 탄소 관 넷 · 손끝 나사 머리 · 몸통 · 팔 나사 머리 · 몸통) 가운데 인쇄 부품이 낀 모든 쌍:
  ① 교차 부피 ≤ 0.01 mm³(면 맞닿음은 부피 0 — 맞닿음도 이 한계 안)
  ② 서로 움직이는 쌍(묶음 F · A · B · R 이 다름)은 한쪽을 ±x · ±y · ±z 로 δ = 0.3 옮겨도 ≤ 0.01 — 빼는 방향은 표 DELTA_SKIP 에 이름으로만
     (맞물림 쌍의 x · z = 백래시는 G3 가 봄 · 턱 ↔ 관의 y · z = 미끄럼 끼움 · u = 0 의 손끝 ↔ 손끝 x = 닫힘 맞닿음)
  ③ 구매품 · 놀음 범위의 끝(VARIANTS: 혼 높이 2.65 · 턱이 관 위에서 놂 ± · 피니언이 나사 구멍 안에서 비킴)에서 상대 위치가 바뀌는 쌍의 교차 ≤ 0.01
     — 턱 ↔ 관 쌍만은 놀음 끝이 곧 닿음이라 ROD_CONTACT_BACKOFF(0.02) 덜 민 자리에서 본다(MP19 · 구멍 다각형 오차가 닿음을 겹침으로 세지 않게)
  ④ 구매품끼리 가운데 정한 쌍(피니언 나사 끝 ↔ 서보 몸체 — 나사 축으로 δ 더 들어가도)의 교차 ≤ 0.01.
- G3 맞물림(표본 u + 한 피치보다 넓은 위상 표본 20 개): 피니언 ↔ 랙 겹침 ≤ 0.01 · 랙을 피니언 쪽으로 「피니언 비킴 + 관 놀음」 만큼 밀어도 ≤ 0.01(최소 백래시) ·
  「원장 백래시의 반경 환산(깎음 피니언 + 랙) / (2 tan α) + ENGAGE_MARGIN 0.125」 만큼 밀면 겹침 > 1 mm³(물려 있음 — MP19: 옛 고정값 0.4 = 0.275 + 0.125 를 원장에서 읽게).
- G4 행정: 손끝 면 간격 = 2u(±0.02) · 닫힘 0 · 최대 벌림 ≥ 물체 80 + 10 · 서보 각 · 물체 상자(parameters pad.object_box)를 벌림 80 + 1 에 놓고 인쇄 부품과 겹침 0.
- G5 구멍: 만들기 기록이 선언한 구멍마다 ① 지름 = 출처(원장 키 · parameters 값 · 시험편 목록 — 종류별) ② 안이 비었음(반지름 −0.05 기둥 · M2 홈은 홈 길이 막대)
  ③ 둘레에 재료(반지름 +0.05 ~ +0.3 껍질의 85 % 이상 — 인서트 · 관 · 시험편 구멍) + 독립 개수 표(모든 (부품, 종류) — 표 밖 조합도 거짓) · 인서트 구멍 축 = 출력 방향의 세로.
- G6 출력: 부품별 출력 방향으로 돌려 판(300 × 300 · 높이 300) 안 · 판 닿는 넓이 · 아래 향한 면(수평에서 43.9° 보다 눕은 면 = 법선 z < −0.72 · 판 면 제외)마다
  면 바로 아래 0.3 단면에서 ±x · ±y 로 가장 가까운 재료까지의 거리 합(다리 길이)을 재어, 가파른 면은 20 mm · 수평 면은 30 mm 보다 길거나 한쪽이 비면 받침 없음으로 센다
  (구멍 가림 없음 — 구멍 천장은 양쪽 벽이 가까워 짧은 다리로 잡힌다).
- G7 기어 강도(루이스) · 서보 각 · 질량 어림(출력 질량은 슬라이서 기록이 정본).
- G8 조립 경로 · 관 축(README 조립 차례 1 ~ 6): 턱 A 를 위로 빼냄(혼 높이 두 끝) · 턱 B 를 앞으로 빼냄(턱 A 정위치 · 0.3 처짐) · 기둥 구멍 = 슬리브 구멍 = parameters 관 축 ·
  넣는 쪽 기둥 = 미끄럼 · 맞은편 = 고정.
사용: python verify_gripper.py [--model <models 폴더>] [--evidence <근거 폴더>] [--params <parameters.json>] [--out <검사 기록 json>] [--scratch-root <작업 뿌리>] [--u …]
--out 은 guard 로 그리퍼 산출 · MP8 그리퍼 근거 · 표지 있는 작업 뿌리 안만 쓴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402

ROOT = guard.find_root(HERE)
LIMIT = 0.01
DELTA = 0.3
ROD_CONTACT_BACKOFF = 0.02    # MP19: 놀음 끝 변형에서 턱 ↔ 관은 이만큼 덜 밀어 본다(놀음 끝 = 닿음 · 관 기준 입체도 반지름 0.02 작게 만듦)
ENGAGE_MARGIN = 0.125         # MP19: 물림 확인 = 원장 백래시의 반경 환산 + 이 여유(옛 고정 0.4 = 0.275 + 0.125)
U_SAMPLES = (0.0, 2.0, 10.0, 23.5, 35.0, 47.0)
PHASES = tuple(round(23.5 + 0.25 * k, 2) for k in range(20))     # 23.5 ~ 28.25 — 한 피치(π × 1.5 = 4.712)보다 넓게
STEEP_SPAN, BRIDGE_SPAN = 20.0, 30.0
NAME = "kmjh-gripper-v1"
EXPECTED_PARTS = ["BASE", "JAW_A", "JAW_B", "PINION", "PAD_A_FLAT", "PAD_B_FLAT", "PAD_A_V", "PAD_B_V",
                  "FIT_BLOCK", "FIT_MESH", "FIT_RACK_A", "FIT_RACK_B", "FIT_PINION_005", "FIT_PINION_010", "FIT_PINION_015", "FIT_PINION_020"]
EXPECTED_OUTPUT_KEYS = sorted([f"parts/{p}.stl" for p in EXPECTED_PARTS] + [f"{NAME}.solidcraft", f"{NAME}.step", f"{NAME}.3mf"])
FIT_PINIONS = [p for p in EXPECTED_PARTS if p.startswith("FIT_PINION_")]
PRINT_ORIENT = {"BASE": "z_up", "JAW_A": "y_up", "JAW_B": "z_up", "PINION": "y_down", "PAD_A_FLAT": "x_down", "PAD_A_V": "x_down",
                "PAD_B_FLAT": "x_up", "PAD_B_V": "x_up", "FIT_BLOCK": "z_up", "FIT_MESH": "z_up", "FIT_RACK_A": "z_up", "FIT_RACK_B": "z_up",
                **{p: "y_down" for p in FIT_PINIONS}}
ORIENT = {"z_up": np.eye(3), "y_up": np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float),
          "y_down": np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float),
          "x_down": np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float), "x_up": np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float)}
# 독립 개수 표: (부품, 종류) → 개수 — 기록의 조합이 이 표와 꼭 같아야 한다(표 밖 조합도 거짓)
EXPECTED_HOLES = {("BASE", "rod_press"): 4, ("BASE", "rod_slide"): 4, ("BASE", "m3_clearance"): 6, ("BASE", "m2_clearance_slot"): 4,
                  ("BASE", "clearance_horn"): 1,
                  ("JAW_A", "rod_slide"): 2, ("JAW_A", "relief"): 2, ("JAW_A", "insert"): 2,
                  ("JAW_B", "rod_slide"): 2, ("JAW_B", "relief"): 2, ("JAW_B", "insert"): 2,
                  ("PINION", "m3_close"): 4, ("PINION", "clearance_horn_screw"): 1,
                  ("PAD_A_FLAT", "m3_clearance"): 2, ("PAD_B_FLAT", "m3_clearance"): 2, ("PAD_A_V", "m3_clearance"): 2, ("PAD_B_V", "m3_clearance"): 2,
                  ("FIT_BLOCK", "coupon_rod"): 6, ("FIT_BLOCK", "coupon_m3"): 3,
                  **{(p, "m3_close"): 4 for p in FIT_PINIONS}, **{(p, "clearance_horn_screw"): 1 for p in FIT_PINIONS}}
PRINTED = {"BASE", "JAW_A", "JAW_B", "PINION", "PAD_A", "PAD_B"}
FIT_OF_KIND = {"insert": "insert_hole_dia", "m3_clearance": "m3_clearance_dia", "m3_close": "m3_close_hole_dia", "rod_slide": "rod_slide_hole_dia",
               "rod_press": "rod_press_hole_dia", "m2_clearance_slot": "m2_clearance_dia"}
WALL_KINDS = ("insert", "rod_slide", "rod_press", "coupon_rod", "coupon_m3")
# δ 검사에서 빼는 방향(쌍 이름 → 축) — 이 표 밖의 움직이는 쌍은 여섯 방향 모두 본다
DELTA_SKIP = {frozenset({"JAW_A", "PINION"}): "xz", frozenset({"JAW_B", "PINION"}): "xz"}   # 맞물림: 백래시(반경 0.275 · 원주 0.2) < δ — G3 가 본다


def delta_skip(la, lb, u):
    s = DELTA_SKIP.get(frozenset({la, lb}), "")
    for j in ("JAW_A", "JAW_B"):
        if j in (la, lb) and (la.startswith("ROD_") or lb.startswith("ROD_")):
            s += "yz"                                    # 슬리브 ↔ 관: 미끄럼 끼움(반경 놀음 0.125)
    if {la, lb} == {"PAD_A", "PAD_B"} and u == 0:
        s += "x"                                         # 닫힘 = 두 손끝 면 맞닿음
    return s


def m3d():
    import manifold3d
    return manifold3d


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def to_man(mesh):
    M = m3d()
    return M.Manifold(M.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32), tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))


def vol(man):
    return float(man.volume()) if hasattr(man, "volume") else float(man.get_volume())


def bbox(man):
    b = man.bounding_box()
    if hasattr(b, "min"):
        return np.array(b.min, float), np.array(b.max, float)
    return np.array(b[:3], float), np.array(b[3:], float)


def bb_near(ba, bb, gap):
    return bool(np.all(ba[0] <= bb[1] + gap) and np.all(bb[0] <= ba[1] + gap))


def box(x, y, z):
    M = m3d()
    return M.Manifold.cube([x[1] - x[0], y[1] - y[0], z[1] - z[0]]).translate([x[0], y[0], z[0]])


def cyl_axis(axis, a, b, c1, c2, r, seg=96):
    """axis ∈ x|y|z · 구간 [a, b] · 중심 (c1, c2) = (그 축에 수직인 두 좌표 — x 축: (y, z) · y 축: (x, z) · z 축: (x, y))."""
    M = m3d()
    a, b = min(a, b), max(a, b)
    c = M.Manifold.cylinder(b - a, r, r, seg)          # +z, 원점 밑면
    if axis == "z":
        return c.translate([c1, c2, a])
    if axis == "x":
        return c.rotate([0, 90, 0]).translate([a, c1, c2])   # +z → +x
    return c.rotate([-90, 0, 0]).translate([c1, a, c2])       # +z → +y


def slot_axis_y(a, b, x, z, r, half):
    """y 축 둥근 홈(z 로 ±half 늘림) 탐침."""
    return cyl_axis("y", a, b, x, z - half, r) + cyl_axis("y", a, b, x, z + half, r) + box((x - r, x + r), (a, b), (z - half, z + half))


def ledger(P):
    src = P["fits_from"]
    mat = json.loads((HERE / src["ledger"]).resolve().read_text(encoding="utf-8"))["materials"][src["material"]]
    f = {k: float(mat["values"][k]["value"]) for k in src["values"]}
    f.update({k: float(mat["pending"][k]["value"]) for k in src["pending"]})
    st = {k: mat["values"][k]["status"] for k in src["values"]}
    st.update({k: mat["pending"][k]["status"] for k in src["pending"]})
    return f, st


def references(P, f):
    """구매품 기준 입체(G 좌표 · 닫힌 자세 · 혼 바깥면 = 높은 끝 3.0) — (이름, 입체, 묶음 F|A|B|R)."""
    L, S, g, SC = P["layout"], P["servo"], P["gear"], P["screws"]
    zc = L["z_c"]
    top = L["wall_y"][0]                       # 서보 몸통 윗면 = 벽 뒷면
    sx0 = -S["spline_from_out_end"]
    Lb, Wb, Hb = S["body"]
    step = (Hb - S["out_end_thickness"]) / 2
    out = []
    body = box((sx0 + S["out_end_length"], sx0 + Lb), (top - Hb, top), (zc - Wb / 2, zc + Wb / 2))
    outend = box((sx0, sx0 + S["out_end_length"]), (top - Hb + step, top - step), (zc - Wb / 2, zc + Wb / 2))
    bump = box((sx0 + S["out_end_length"], sx0 + Lb), (top - Hb - S["bottom_bump"], top - Hb), (zc - Wb / 2, zc + Wb / 2))
    plug = box((sx0 + S["plug_zone_from_out_end"][0], sx0 + S["plug_zone_from_out_end"][1]),
               (top - Hb - S["bottom_bump"] - S["plug_zone_depth"], top - Hb - S["bottom_bump"]), (zc - Wb / 2 + 2, zc + Wb / 2 - 2))
    out.append(("SERVO_BODY", body + outend + bump, "F"))
    out.append(("SERVO_PLUGS", plug, "F"))
    hf_hi = S["horn_face_above_body_top"][1]
    spline_top = top - step + S["spline_above_out_end_face"]
    out.append(("SPLINE", cyl_axis("y", top - step, spline_top, 0.0, zc, 5.9 / 2), "R"))
    # 혼(Feetech 혼 도면 · drawing_read): 플랜지 Ø19.95 × 2.5(바깥면 = 몸통 윗면 위 hf — 불확실 2.65 ~ 3.0 · 여기는 3.0, 2.65 는 VARIANTS horn_low) + 허브 Ø9 × 2.0
    out.append(("HORN", cyl_axis("y", top + hf_hi - 2.5, top + hf_hi, 0.0, zc, S["horn_dia"] / 2)
                + cyl_axis("y", top + hf_hi - 4.5, top + hf_hi - 2.5, 0.0, zc, 4.5), "R"))
    out.append(("HORN_SCREW_HEAD", cyl_axis("y", top + hf_hi, top + hf_hi + 3.0, 0.0, zc, 5.5 / 2), "R"))
    # 서보 나사 M2: 머리(지름 · 높이 상한 — parameters screws.servo_m2) = 벽 앞면 자리파기 바닥에 앉음 · 몸통(지름 2 − 0.04) = 머리 밑에서 길이만큼 서보 쪽(−y)
    face = L["wall_y"][1]
    seat = face - 1.8
    hd, hh = SC["servo_m2"]["head_max"]
    for s in S["top_holes_from_out_end"]:
        for sg in (-1, 1):
            x, z = s + sx0, zc + sg * S["top_holes_width_spacing"] / 2
            out.append((f"M2_HEAD_{s}_{sg}", cyl_axis("y", seat, seat + hh, x, z, hd / 2), "F"))
            out.append((f"M2_SHANK_{s}_{sg}", cyl_axis("y", seat - SC["servo_m2"]["length"], seat, x, z, 1.0 - 0.02), "F"))
    # 피니언 나사 M3: 머리 = 자리파기 바닥(앞면 − 깊이)에 앉음 · 몸통 = 그 바닥에서 −y 로 길이만큼(혼 플랜지 탭에 물림)
    y_top = L["gear_band_y"][1]
    cbd, cbh = g["screw_cbore"]
    phd, phh = SC["pinion_m3"]["head"]
    for i in range(g["screw_count"]):
        a = math.radians(g["screw_phase_deg"]) + i * 2 * math.pi / g["screw_count"]
        x, z = g["screw_pcd"] / 2 * math.cos(a), zc + g["screw_pcd"] / 2 * math.sin(a)
        out.append((f"PIN_HEAD_{i}", cyl_axis("y", y_top - cbh, y_top - cbh + phh, x, z, phd / 2), "R"))
        out.append((f"PIN_SHANK_{i}", cyl_axis("y", y_top - cbh - SC["pinion_m3"]["length"], y_top - cbh, x, z, 1.5 - 0.02), "R"))
    # 탄소 관 넷(고정) — 받침 기둥 구멍과 같은 반지름은 STL 다각형 오차로 겹쳐 보이므로 0.02 줄임(MP6 REF_PIN_SHRINK 와 같은 까닭)
    R = P["rod"]
    for yy in L["rod_y_a"] + L["rod_y_b"]:
        out.append((f"ROD_{yy}", cyl_axis("x", -R["length"] / 2, R["length"] / 2, yy, L["rod_z"], R["od"] / 2 - 0.02), "F"))
    # 팔 나사 M3: 머리(ISO 4762 · 지름 · 높이 = parameters) = 받침 위면 자리파기 바닥에 앉음 · 몸통 = 아래로(팔 쪽)
    pcd, ph = L["arm_screw_pcd"], math.radians(L["arm_screw_phase_deg"])
    ahd, ahh = SC["arm_m3"]["head"]
    seat_z = L["base_top"] - L["arm_screw_cbore"][1]
    for i in range(4):
        x, y = pcd / 2 * math.cos(ph + i * math.pi / 2), pcd / 2 * math.sin(ph + i * math.pi / 2)
        out.append((f"ARM_HEAD_{i}", cyl_axis("z", seat_z, seat_z + ahh, x, y, ahd / 2), "F"))
        out.append((f"ARM_SHANK_{i}", cyl_axis("z", seat_z - SC["arm_m3"]["length"], seat_z, x, y, 1.5 - 0.02), "F"))
    # 손끝 나사 M3(둥근머리): A = 날개 +y 면 위 · 몸통 −y · B = 덮개 위 · 몸통 −z
    JA, JB, Q = P["jaw_a"], P["jaw_b"], P["pad"]
    pd_, pdh = SC["pad_m3"]["head"]
    plen = SC["pad_m3"]["length"]
    ya = Q["y"][1] + Q["flange_t_a"]
    for i, zz in enumerate(JA["pad_insert_z"]):
        out.append((f"PAD_A_HEAD_{i}", cyl_axis("y", ya, ya + pdh, JA["pad_insert_x"], zz, pd_ / 2), "A"))
        out.append((f"PAD_A_SHANK_{i}", cyl_axis("y", ya - plen, ya, JA["pad_insert_x"], zz, 1.5 - 0.02), "A"))
    zb = JB["stalk_top"] + Q["cap_t_b"]
    for i, yy in enumerate(JB["cap_insert_y"]):
        out.append((f"PAD_B_HEAD_{i}", cyl_axis("z", zb, zb + pdh, JB["cap_insert_x"], yy, pd_ / 2), "B"))
        out.append((f"PAD_B_SHANK_{i}", cyl_axis("z", zb - plen, zb, JB["cap_insert_x"], yy, 1.5 - 0.02), "B"))
    return out


ROT_SIGN = 1.0


def place(man, group, u, r, zc, shift=(0.0, 0.0, 0.0)):
    if group == "A":
        man = man.translate([-u, 0, 0])
    elif group == "B":
        man = man.translate([u, 0, 0])
    elif group == "R":
        th = -u / r                                  # +y 축 둘레 θ — manifold rotate 의 y 부호는 sign_check 로 확인
        man = man.translate([0, 0, -zc]).rotate([0, math.degrees(th) * ROT_SIGN, 0]).translate([0, 0, zc])
    if any(shift):
        man = man.translate(list(shift))
    return man


def sign_check():
    """R_y(θ)(x, z) = (x cos θ + z sin θ, −x sin θ + z cos θ) — manifold rotate([0, deg, 0]) 이 같은 뜻인지 점 하나로 본다."""
    global ROT_SIGN
    M = m3d()
    moved = M.Manifold.cube([1, 1, 1], True).translate([0, 0, 10]).rotate([0, 30, 0])
    lo, hi = bbox(moved)
    xc = (lo[0] + hi[0]) / 2
    ROT_SIGN = 1.0 if xc > 0 else -1.0                # R_y(+30°)(0, 10) → x = 10 sin 30 = +5
    return {"manifold_rotate_y_plus30_moves_top_to_x": round(float(xc), 3), "rot_sign": ROT_SIGN}


def assemble(man, refs, padset, u, r, zc, shifts=None):
    """(이름, 묶음, 인쇄?, 입체, 상자) 목록."""
    shifts = shifts or {}
    items = [("BASE", "BASE", "F"), ("JAW_A", "JAW_A", "A"), ("JAW_B", "JAW_B", "B"), ("PINION", "PINION", "R"),
             ("PAD_A", f"PAD_A_{padset}", "A"), ("PAD_B", f"PAD_B_{padset}", "B")]
    out = []
    for lab, src, grp in items:
        s = place(man[src], grp, u, r, zc, shifts.get(grp, (0.0, 0.0, 0.0)))
        out.append((lab, grp, True, s, bbox(s)))
    for lab, s0, grp in refs:
        s = place(s0, grp, u, r, zc, shifts.get(grp, (0.0, 0.0, 0.0)))
        out.append((lab, grp, False, s, bbox(s)))
    return out


DIRS = {"x": [(1, 0, 0), (-1, 0, 0)], "y": [(0, 1, 0), (0, -1, 0)], "z": [(0, 0, 1), (0, 0, -1)]}


def bridge_spans(mm, idx):
    """아래 향한 면마다: 면 바로 아래(0.3) 높이의 단면에서 그 면 가운데로부터 ±x · ±y 로 가장 가까운 재료까지 거리 — 한 축의 양쪽 합 중 작은 것(다리 길이).
    양쪽 어느 축에서도 재료가 없으면 inf(받침 없는 처마). 단면 = manifold slice · 거리 = shapely 선과 다각형 교차(광선 대신 — rtree 없음)."""
    from shapely.geometry import LineString, Point, Polygon
    man = to_man(mm)
    tc = mm.triangles_center
    out = np.full(len(idx), np.inf)
    by_z = {}
    for j, i in enumerate(idx):
        by_z.setdefault(round(float(tc[i, 2]), 2), []).append(j)
    for zf, js in by_z.items():
        zs = zf - 0.3
        if zs <= 0:
            continue
        cs = man.slice(zs)
        polys = cs.to_polygons()
        shapes = [Polygon(p) for p in polys if len(p) >= 3]
        region = None
        for s in sorted(shapes, key=lambda s: -abs(s.area)):        # 짝홀 규칙(안쪽 고리 = 구멍) — 넓이 큰 것부터 빼고 더함
            s = s.buffer(0)
            if region is None:
                region = s
            elif region.contains(s.representative_point()):
                region = region.difference(s)
            else:
                region = region.union(s)
        if region is None or region.is_empty:
            continue
        for j in js:
            x, y = float(tc[idx[j], 0]), float(tc[idx[j], 1])
            best = np.inf
            for dx, dy in ((1, 0), (0, 1)):
                d = []
                for sg in (1, -1):
                    ln = LineString([(x, y), (x + sg * dx * 400, y + sg * dy * 400)])
                    hit = ln.intersection(region)
                    d.append(Point(x, y).distance(hit) if not hit.is_empty else np.inf)
                best = min(best, d[0] + d[1])
            out[j] = best
    return out


def pair_overlaps(placed, u, pairs_filter=None, delta=0.0, skip_fn=None):
    """인쇄 부품이 낀 쌍의 교차 부피(δ > 0 이면 서로 움직이는 쌍을 여섯 방향으로 δ 옮긴 최대)."""
    res = {}
    for (la, ga, pa, sa, ba), (lb, gb, pb, sb, bb) in combinations(placed, 2):
        if not (pa or pb):
            continue
        if pairs_filter is not None and not pairs_filter(la, ga, lb, gb):
            continue
        key = f"{la}|{lb}"
        if delta <= 0:
            res[key] = vol(sa ^ sb) if bb_near(ba, bb, 0.0) else 0.0
            continue
        if ga == gb or not bb_near(ba, bb, delta):
            continue
        skip = skip_fn(la, lb, u) if skip_fn else ""
        worst = 0.0
        for ax, dl in DIRS.items():
            if ax in skip:
                continue
            for d in dl:
                worst = max(worst, vol(sa.translate([delta * d[0], delta * d[1], delta * d[2]]) ^ sb))
        res[key] = worst
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, default=ROOT / "models" / NAME)
    ap.add_argument("--evidence", type=Path, default=ROOT / ".dev" / "mp8-evidence" / "gripper")
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--scratch-root", type=Path)
    ap.add_argument("--u", type=float, nargs="*", default=list(U_SAMPLES))
    a = ap.parse_args()
    if a.out:
        guard.checked_file(a.out, ROOT, a.scratch_root)            # 쓰기 자리를 먼저 본다(계산 전에 멈추게)
    P = json.loads(a.params.read_text(encoding="utf-8"))
    f, fst = ledger(P)
    rec_path = a.evidence / "build-record.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    out = {"what": "KG1 합격 검사(커밋된 STL 로 스스로 계산)", "checks": {}, "numbers": {}}
    C, N = out["checks"], out["numbers"]
    N["rotation_sign"] = sign_check()

    # ---- G0 출처 ----
    now_out = {k: (sha(a.model / k) if (a.model / k).is_file() else None) for k in rec["outputs_sha256"]}
    C["G0_outputs_match_record"] = now_out == rec["outputs_sha256"]
    C["G0_output_keys_match_independent_set"] = sorted(rec["outputs_sha256"]) == EXPECTED_OUTPUT_KEYS
    now_in = {"parameters.json": sha(a.params), "kg1.py": sha(HERE / "kg1.py"), "build_gripper.py": sha(HERE / "build_gripper.py"),
              "print-fits.json": sha((HERE / P["fits_from"]["ledger"]).resolve())}
    C["G0_inputs_match_record"] = now_in == rec["inputs_sha256"]
    N["G0_input_mismatch"] = sorted(k for k in now_in if now_in[k] != rec["inputs_sha256"].get(k))
    C["G0_fits_used_equal_ledger"] = {k: float(v) for k, v in rec["fits_used"].items()} == f
    tool = rec.get("tool") or {}
    C["G0_build_tool_recorded"] = bool(tool.get("cli_version")) and len(tool.get("cli_sha256") or "") == 64
    pp_path = a.evidence / "print-prep.json"
    pp_bad = []
    if pp_path.is_file():
        pp = json.loads(pp_path.read_text(encoding="utf-8"))
        if sorted(pp.get("per_part", {})) != sorted(EXPECTED_PARTS):
            pp_bad.append("per_part names")
        for n_, v in pp.get("per_part", {}).items():
            p_ = a.model / "parts" / f"{n_}.stl"
            if not p_.is_file() or v.get("stl_sha256") != sha(p_):
                pp_bad.append(f"part {n_}")
        for pn, v in pp.get("plates", {}).items():
            p_ = a.model / f"print-plate-{pn}.stl"
            if not p_.is_file() or v.get("plate_sha256") != sha(p_):
                pp_bad.append(f"plate {pn}")
            sl = v.get("slicer_sha256") or {}
            if not sl:
                pp_bad.append(f"slicer {pn} not recorded")
            for fn, h in sl.items():
                q = a.model / "slicer" / pn / fn
                if not q.is_file() or sha(q) != h:
                    pp_bad.append(f"slicer {pn}/{fn}")
        if sorted(pp.get("plates", {})) != ["fit", "main"]:
            pp_bad.append("plate names")
        mp_path = a.model / "mass-properties.json"
        if mp_path.is_file():
            mp = json.loads(mp_path.read_text(encoding="utf-8"))
            for n_, h in mp.get("parts_sha256", {}).items():
                p_ = a.model / "parts" / f"{n_}.stl"
                if not p_.is_file() or sha(p_) != h:
                    pp_bad.append(f"mass {n_}")
        else:
            pp_bad.append("mass-properties.json missing")
    else:
        pp_bad.append("print-prep.json missing")
    N["G0_print_prep_mismatch"] = pp_bad
    C["G0_print_prep_matches_outputs"] = not pp_bad

    # ---- G1 부품 ----
    parts_dir = a.model / "parts"
    names = sorted(p.stem for p in parts_dir.glob("*.stl"))
    C["G1_part_list_matches_independent_table"] = names == sorted(EXPECTED_PARTS)
    mesh, man = {}, {}
    for nm in names:
        mm = trimesh.load(parts_dir / f"{nm}.stl", force="mesh")
        mesh[nm] = mm
        man[nm] = to_man(mm)
    closed = {nm: bool(mesh[nm].is_watertight and mesh[nm].volume > 0) for nm in names}
    C["G1_all_closed_positive_volume"] = all(closed.values())
    N["G1_volume_cm3"] = {nm: round(mesh[nm].volume / 1000, 3) for nm in names}
    # 불리언 계산은 manifold 로 한다 — 바꾸기가 실패하면 빈 입체가 되어 겹침이 모두 0 으로 조용히 통과하므로, 부피가 메시와 같아야 한다
    mstat = {nm: {"status": str(man[nm].status()), "manifold_cm3": round(vol(man[nm]) / 1000, 3)} for nm in names}
    N["G1_manifold"] = mstat
    C["G1_manifold_equals_mesh"] = all(abs(vol(man[nm]) - mesh[nm].volume) <= 1e-4 * max(1.0, abs(mesh[nm].volume)) for nm in names)

    # ---- G2 · G3 · G4 조립 ----
    L, g, S = P["layout"], P["gear"], P["servo"]
    zc, r = L["z_c"], g["module"] * g["teeth"] / 2
    refs = references(P, f)
    pf = (f["m3_close_hole_dia"] - 3.0) / 2               # 피니언이 혼 위에서 비킬 수 있는 반경(M3 = 3.0)
    sp = (f["rod_slide_hole_dia"] - P["rod"]["od"]) / 2    # 슬리브가 관 위에서 놀 수 있는 반경
    dh = S["horn_face_above_body_top"][1] - S["horn_face_above_body_top"][0]
    VARIANTS = {"horn_low": {"R": (0.0, -dh, 0.0)},
                "jaw_a_axial_plus": {"A": (0.0, sp, 0.0)}, "jaw_a_axial_minus": {"A": (0.0, -sp, 0.0)},
                "jaw_b_axial_plus": {"B": (0.0, sp, 0.0)}, "jaw_b_axial_minus": {"B": (0.0, -sp, 0.0)},
                "horn_low_jaw_a_plus": {"R": (0.0, -dh, 0.0), "A": (0.0, sp, 0.0)},
                "mesh_a_tight": {"R": (0.0, 0.0, pf), "A": (0.0, 0.0, -sp)},
                "mesh_b_tight": {"R": (0.0, 0.0, -pf), "B": (0.0, 0.0, sp)}}
    N["play_mm"] = {"pinion_float_radius": round(pf, 4), "sleeve_play_radius": round(sp, 4), "horn_height_range": round(dh, 4), "delta": DELTA,
                    "jaw_rod_backoff": ROD_CONTACT_BACKOFF}

    def jaw_rod(la, lb):
        return (la in ("JAW_A", "JAW_B") and lb.startswith("ROD_")) or (lb in ("JAW_A", "JAW_B") and la.startswith("ROD_"))

    def backed_off(sh):
        """턱 묶음(A · B)의 옮김만 크기를 ROD_CONTACT_BACKOFF 줄인다(축 하나만 옮기는 변형 — 방향 그대로)."""
        out_ = dict(sh)
        for g_ in ("A", "B"):
            if g_ in sh:
                v_ = sh[g_]
                n_ = math.sqrt(sum(c * c for c in v_))
                out_[g_] = tuple(c * max(0.0, n_ - ROD_CONTACT_BACKOFF) / n_ for c in v_) if n_ > 0 else v_
        return out_
    N["variants"] = {k: {g_: list(v) for g_, v in d.items()} for k, d in VARIANTS.items()}
    need = {"BASE", "JAW_A", "JAW_B", "PINION"}
    worst, worst_d, worst_v = {}, {}, {}
    n_eval = {"plain": 0, "delta": 0, "variant": 0}
    stroke = {}
    N["G2_skipped_padsets"] = []
    for padset in ("FLAT", "V"):
        if not (need | {f"PAD_A_{padset}", f"PAD_B_{padset}"}) <= set(man):
            N["G2_skipped_padsets"].append(padset)        # 부품이 빠지면 그 조합은 못 본다 — G1 이 거짓이 된다
            continue
        for u in a.u:
            placed = assemble(man, refs, padset, u, r, zc)
            res = pair_overlaps(placed, u)
            n_eval["plain"] += len(res)
            for k, v in res.items():
                if k not in worst or v > worst[k][0]:
                    worst[k] = (v, u, padset)
            res = pair_overlaps(placed, u, delta=DELTA, skip_fn=delta_skip)
            n_eval["delta"] += len(res)
            for k, v in res.items():
                if k not in worst_d or v > worst_d[k][0]:
                    worst_d[k] = (v, u, padset)
            if padset == "FLAT":
                for vn, sh in VARIANTS.items():
                    pv = assemble(man, refs, padset, u, r, zc, sh)
                    moved = lambda la, ga, lb, gb, sh=sh: tuple(sh.get(ga, (0, 0, 0))) != tuple(sh.get(gb, (0, 0, 0)))
                    res = pair_overlaps(pv, u, pairs_filter=lambda la, ga, lb, gb, moved=moved: moved(la, ga, lb, gb) and not jaw_rod(la, lb))
                    if any(g_ in sh for g_ in ("A", "B")):       # 턱 ↔ 관: 놀음 끝 = 닿음 → ROD_CONTACT_BACKOFF 덜 민 자리에서(MP19)
                        pc = assemble(man, refs, padset, u, r, zc, backed_off(sh))
                        res.update(pair_overlaps(pc, u, pairs_filter=lambda la, ga, lb, gb, moved=moved: moved(la, ga, lb, gb) and jaw_rod(la, lb)))
                    n_eval["variant"] += len(res)
                    for k, v in res.items():
                        kk = f"{vn}:{k}"
                        if kk not in worst_v or v > worst_v[kk][0]:
                            worst_v[kk] = (v, u)
            # 행정: 손끝 면 간격(맞닿는 면 = 손끝 A 의 최대 x · 손끝 B 의 최소 x, 판 부분 z 60 ~ 100)
            d_ = {lab: s for lab, _g, _p, s, _b in placed}
            ba = bbox(d_["PAD_A"] ^ box((-200, 200), (-10, 10), (60, 100)))
            bb_ = bbox(d_["PAD_B"] ^ box((-200, 200), (-10, 10), (60, 100)))
            stroke[f"{padset}@{u}"] = float(bb_[0][0] - ba[1][0])
    bad = {k: v for k, v in worst.items() if v[0] > LIMIT}
    bad_d = {k: v for k, v in worst_d.items() if v[0] > LIMIT}
    bad_v = {k: v for k, v in worst_v.items() if v[0] > LIMIT}
    N["G2_evaluations"] = n_eval
    N["G2_pairs_checked"] = len(worst)
    N["G2_over_limit"] = {k: {"mm3": round(v[0], 4), "u": v[1], "pads": v[2]} for k, v in sorted(bad.items())}
    N["G2_largest_10"] = {k: round(v[0], 5) for k, v in sorted(worst.items(), key=lambda kv: -kv[1][0])[:10]}
    N["G2_delta_pairs_checked"] = sorted(worst_d)
    N["G2_delta_largest_10"] = {k: round(v[0], 5) for k, v in sorted(worst_d.items(), key=lambda kv: -kv[1][0])[:10]}
    N["G2_delta_over_limit"] = {k: {"mm3": round(v[0], 4), "u": v[1], "pads": v[2]} for k, v in sorted(bad_d.items())}
    N["G2_variant_over_limit"] = {k: {"mm3": round(v[0], 4), "u": v[1]} for k, v in sorted(bad_v.items())}
    C["G2_no_interference"] = not bad and not N["G2_skipped_padsets"]
    C["G2_moving_pairs_clear_by_delta"] = not bad_d and not N["G2_skipped_padsets"]
    C["G2_variants_no_interference"] = not bad_v and not N["G2_skipped_padsets"]
    # 구매품끼리 정한 쌍: 피니언 나사 끝이 서보 몸체에 닿지 않음(혼 높이 두 끝 · 나사 축으로 δ 더)
    rd = {lab: (s, grp) for lab, s, grp in refs}
    tips = {}
    for vn, sh in (("nominal", {}), ("horn_low", VARIANTS["horn_low"])):
        body = rd["SERVO_BODY"][0]
        for lab, (s, grp) in rd.items():
            if lab.startswith("PIN_SHANK_"):
                moved = place(s, grp, 0.0, r, zc, sh.get("R", (0.0, 0.0, 0.0))).translate([0, -DELTA, 0])
                tips[f"{vn}:{lab}|SERVO_BODY"] = round(vol(moved ^ body), 5)
    N["G2_purchased_pairs"] = tips
    C["G2_purchased_pair_checks"] = bool(tips) and all(v <= LIMIT for v in tips.values())

    # G3 맞물림(표본 u + 위상 표본)
    mesh_ok, min_bl_ok, engaged = True, True, {}
    push_min = pf + sp
    backlash_radial = (f["gear_thinning_pinion"] + f["gear_thinning_rack"]) / (2 * math.tan(math.radians(g["pressure_angle_deg"])))
    push_eng = backlash_radial + ENGAGE_MARGIN                 # MP19: 옛 고정 0.4(= 0.275 + 0.125)를 원장에서
    N["G3_engage_push_mm"] = {"backlash_radial": round(backlash_radial, 4), "margin": ENGAGE_MARGIN, "push": round(push_eng, 4)}
    for u in (sorted(set(a.u) | set(PHASES)) if need <= set(man) else []):
        pin = place(man["PINION"], "R", u, r, zc)
        ja, jb = man["JAW_A"].translate([-u, 0, 0]), man["JAW_B"].translate([u, 0, 0])
        rack_a = ja ^ box((-200, 200), tuple(L["gear_band_y"]), (zc + 10, zc + 20))
        rack_b = jb ^ box((-200, 200), tuple(L["gear_band_y"]), (zc - 20, zc - 10))
        v0 = max(vol(pin ^ rack_a), vol(pin ^ rack_b))
        vt = max(vol(pin ^ rack_a.translate([0, 0, -push_min])), vol(pin ^ rack_b.translate([0, 0, push_min])))
        if v0 > LIMIT:
            mesh_ok = False
        if vt > LIMIT:
            min_bl_ok = False
        engaged[u] = {"nominal_mm3": round(v0, 4), f"pushed_{round(push_min, 3)}_mm3": round(vt, 4),
                      "A_pushed_eng_mm3": round(vol(pin ^ rack_a.translate([0, 0, -push_eng])), 3), "B_pushed_eng_mm3": round(vol(pin ^ rack_b.translate([0, 0, push_eng])), 3)}
    C["G3_mesh_no_interference_sampled"] = mesh_ok and bool(engaged)
    C["G3_min_backlash_under_play"] = min_bl_ok and bool(engaged)
    C["G3_mesh_engaged_sampled"] = bool(engaged) and all(v["A_pushed_eng_mm3"] > 1.0 and v["B_pushed_eng_mm3"] > 1.0 for v in engaged.values())
    N["G3_engaged"] = engaged
    # G4 행정 · 물체
    N["G4_pad_gap"] = {k: round(v, 3) for k, v in stroke.items()}
    C["G4_gap_equals_2u"] = bool(stroke) and all(abs(v - 2 * float(k.split("@")[1])) <= 0.02 for k, v in stroke.items())
    umax = max(a.u)
    C["G4_open_at_least_object_plus_10"] = 2 * L["stroke_half"] >= 80 + 10 and umax >= L["stroke_half"] - 1e-9
    N["G4_servo_angle_deg_full_stroke"] = round(math.degrees(L["stroke_half"] / r), 1)
    C["G4_servo_angle_within_300"] = math.degrees(L["stroke_half"] / r) <= 300
    ow, od, oh = P["pad"]["object_box"]
    u_obj = (ow + 1.0) / 2
    z1 = P["pad"]["z"][1]
    obj = box((-ow / 2, ow / 2), (-od / 2, od / 2), (z1 - oh, z1))
    hits = {}
    for padset in ("FLAT", "V"):
        if not (need | {f"PAD_A_{padset}", f"PAD_B_{padset}"}) <= set(man):
            continue
        for lab, _g, _p, s, b in assemble(man, refs, padset, u_obj, r, zc):
            v = vol(obj ^ s) if bb_near(bbox(obj), b, 0.0) else 0.0
            if v > LIMIT:
                hits[f"{padset}:{lab}"] = round(v, 4)
    N["G4_object_box"] = {"box_mm": [ow, od, oh], "u": u_obj, "z": [z1 - oh, z1], "hits": hits,
                          "height_limit_when_tips_on_tray_mm": round(z1 - (P["jaw_a"]["sleeve_z"][1] + 0.5), 2)}
    C["G4_object_box_fits"] = not hits and not N["G2_skipped_padsets"]

    # ---- G5 구멍 ----
    def want_dia(h):
        k = h["kind"]
        if k in FIT_OF_KIND:
            return abs(h["dia"] - f[FIT_OF_KIND[k]]) < 1e-9
        if k == "clearance_horn":
            return abs(h["dia"] - L["horn_hole_dia"]) < 1e-9
        if k == "clearance_horn_screw":
            return abs(h["dia"] - g["centre_hole"]) < 1e-9
        if k == "relief":
            jaw = {"JAW_A": "jaw_a", "JAW_B": "jaw_b"}.get(h["body"])
            return jaw is not None and abs(h["dia"] - P[jaw]["relief_dia"]) < 1e-9
        if k == "coupon_rod":
            return h["dia"] in P["fit_coupon"]["holes"]
        if k == "coupon_m3":
            return h["dia"] in P["fit_coupon"]["m3_close_holes"]
        return False                                   # 모르는 종류
    probe = []
    counts = {}
    for h in rec["holes"]:
        counts[(h["body"], h["kind"])] = counts.get((h["body"], h["kind"]), 0) + 1
        body = man.get(h["body"])
        if body is None:
            continue
        r_h = h["dia"] / 2
        a0, b0 = h["span"]
        spans = h.get("bearing_spans") or [[a0, b0]]
        empty, ring_fill = 0.0, []
        for s0, s1 in spans:
            s0c, s1c = max(s0, a0) + 0.05, min(s1, b0) - 0.05
            if s1c <= s0c:
                continue
            if h["kind"] == "m2_clearance_slot":
                inner = slot_axis_y(s0c, s1c, h["c"][0], h["c"][1], r_h - 0.05, h["slot_half_len"])
            else:
                inner = cyl_axis(h["axis"], s0c, s1c, h["c"][0], h["c"][1], r_h - 0.05)
            empty += vol(body ^ inner)
            if h["kind"] in WALL_KINDS:
                shell = cyl_axis(h["axis"], s0c, s1c, h["c"][0], h["c"][1], r_h + 0.3) - cyl_axis(h["axis"], s0c - 1, s1c + 1, h["c"][0], h["c"][1], r_h + 0.05)
                sv = vol(shell)
                ring_fill.append(vol(body ^ shell) / sv if sv > 0 else 0.0)
        probe.append({"body": h["body"], "tag": h["tag"], "kind": h["kind"], "dia": h["dia"], "dia_equals_source": want_dia(h),
                      "inside_material_mm3": round(empty, 4), "shell_fill_min": round(min(ring_fill), 3) if ring_fill else None})
    N["G5_holes"] = probe
    C["G5_hole_dias_equal_source"] = bool(probe) and all(p["dia_equals_source"] for p in probe)
    C["G5_holes_empty"] = all(p["inside_material_mm3"] <= LIMIT for p in probe)
    C["G5_holes_have_walls"] = all((p["shell_fill_min"] or 0) >= 0.85 for p in probe if p["kind"] in WALL_KINDS)
    N["G5_counts"] = {f"{k[0]}|{k[1]}": v for k, v in sorted(counts.items())}
    N["G5_counts_diff"] = {f"{k[0]}|{k[1]}": [counts.get(k, 0), EXPECTED_HOLES.get(k, 0)] for k in sorted(set(counts) | set(EXPECTED_HOLES))
                           if counts.get(k, 0) != EXPECTED_HOLES.get(k, 0)}
    C["G5_counts_match_independent_table"] = counts == EXPECTED_HOLES
    vertical = {"y_up": "y", "y_down": "y", "z_up": "z", "x_up": "x", "x_down": "x"}
    C["G5_inserts_vertical_in_print"] = all(h["axis"] == vertical[PRINT_ORIENT.get(h["body"], "z_up")] for h in rec["holes"] if h["kind"] == "insert")

    # ---- G6 출력 ----
    pr = {}
    for nm in names:
        R = ORIENT[PRINT_ORIENT.get(nm, "z_up")]
        mm = mesh[nm].copy()
        mm.apply_transform(np.vstack([np.hstack([R, np.zeros((3, 1))]), [0, 0, 0, 1]]))
        mm.apply_translation(-mm.bounds[0])
        ext = mm.extents
        fn = mm.face_normals
        cz = mm.triangles_center[:, 2]
        area = mm.area_faces
        bed = (fn[:, 2] < -0.99) & (cz < 0.05)
        down = (fn[:, 2] < -0.72) & (cz >= 0.05)
        steep = down & (fn[:, 2] > -0.99)
        bridge = down & (fn[:, 2] <= -0.99)
        idx = np.where(down)[0]
        spans = bridge_spans(mm, idx) if len(idx) else np.zeros(0)
        lim = np.where(fn[idx, 2] <= -0.99, BRIDGE_SPAN, STEEP_SPAN) if len(idx) else np.zeros(0)
        unsup = idx[~np.isfinite(spans) | (spans > lim)] if len(idx) else idx
        st_un = unsup[steep[unsup]]
        br_un = unsup[bridge[unsup]]
        pr[nm] = {"orient": PRINT_ORIENT.get(nm, "z_up"), "extent": [round(float(e), 2) for e in ext], "bed_mm2": round(float(area[bed].sum()), 1),
                  "steep_mm2": round(float(area[steep].sum()), 2), "bridge_mm2": round(float(area[bridge].sum()), 1),
                  "steep_unsupported_mm2": round(float(area[st_un].sum()), 2), "bridge_unsupported_mm2": round(float(area[br_un].sum()), 1),
                  "span_max_finite_mm": None if not np.isfinite(spans).any() else round(float(np.max(spans[np.isfinite(spans)])), 1)}
    N["G6_print"] = pr
    N["G6_rule"] = {"down_face": "normal z < -0.72 (43.9° from horizontal)", "steep_span_max_mm": STEEP_SPAN, "bridge_span_max_mm": BRIDGE_SPAN,
                    "allowed_unsupported_mm2": 5.0}
    C["G6_fits_plate"] = all(p["extent"][0] <= 300 and p["extent"][1] <= 300 and p["extent"][2] <= 300 for p in pr.values())
    C["G6_bed_contact"] = all(p["bed_mm2"] >= 100 for p in pr.values())
    C["G6_no_steep_overhang"] = all(p["steep_unsupported_mm2"] <= 5.0 for p in pr.values())
    C["G6_bridges_short"] = all(p["bridge_unsupported_mm2"] <= 5.0 for p in pr.values())

    # ---- G8 조립 경로 · 관 축 ----
    # 차례(README): 1 받침을 팔에(팔 나사 넷) → 2 서보를 받침 턱에 눌러 대고 M2 넷 → 3 혼 → 4 피니언(M3 넷 · 이 뒤로는 앞이 턱 B 벽에 가려 나사에 닿지 않음) →
    # 5 턱 A 를 위에서 내려 랙 A 를 물림 → 6 턱 B 를 앞(+y)에서 밀어 넣음(랙 B 가 피니언 아래를 축 방향으로 미끄러짐) → 7 관 넷 → 8 손끝.
    # 빼내는 길(거꾸로)을 1 mm 마다 본다 — 관 · 손끝은 아직 없음. 혼 높이 두 끝 · 턱 B 를 넣을 때 관 없는 턱 A 가 0.3 처진 경우도 본다.
    if need <= set(man):
        def core(shift_r=(0.0, 0.0, 0.0)):
            s = man["BASE"] + place(man["PINION"], "R", 0.0, r, zc, shift_r)
            for lab, s0, grp in refs:
                if lab.startswith(("SERVO_BODY", "M2_", "ARM_")):
                    s = s + s0
                elif grp == "R":
                    s = s + place(s0, "R", 0.0, r, zc, shift_r)
            return s
        res8 = {}
        for vn, shr in (("nominal", (0.0, 0.0, 0.0)), ("horn_low", (0.0, -dh, 0.0))):
            obst = core(shr)
            res8[f"jaw_a_lift_z_0.5_80:{vn}"] = max(vol(man["JAW_A"].translate([0, 0, dz]) ^ obst) for dz in np.arange(0.5, 80.5, 1.0))
            if vn == "nominal":
                res8["jaw_b_slide_y_0.5_40:nominal"] = max(vol(man["JAW_B"].translate([0, dy, 0]) ^ (obst + man["JAW_A"])) for dy in np.arange(0.5, 40.5, 1.0))
                sag = man["JAW_A"].translate([0, 0, -0.3])
                res8["jaw_b_slide_y_0.5_40:jaw_a_sag_0.3"] = max(vol(man["JAW_B"].translate([0, dy, 0]) ^ (obst + sag)) for dy in np.arange(0.5, 40.5, 1.0))
        N["G8_path_worst_overlap_mm3"] = {k: round(v, 4) for k, v in res8.items()}
        C["G8_jaw_a_lifts_out"] = all(v <= LIMIT for k, v in res8.items() if k.startswith("jaw_a_lift"))
        C["G8_jaw_b_slides_out"] = res8["jaw_b_slide_y_0.5_40:nominal"] <= LIMIT
        C["G8_jaw_b_slides_with_jaw_a_sagged"] = res8["jaw_b_slide_y_0.5_40:jaw_a_sag_0.3"] <= LIMIT
    else:
        C["G8_jaw_a_lifts_out"] = C["G8_jaw_b_slides_out"] = C["G8_jaw_b_slides_with_jaw_a_sagged"] = False
    base_rod = [h for h in rec["holes"] if h["body"] == "BASE" and h["kind"] in ("rod_press", "rod_slide")]
    post = sorted({(round(h["c"][0], 3), round(h["c"][1], 3)) for h in base_rod})
    bores_ = sorted({(round(h["c"][0], 3), round(h["c"][1], 3)) for h in rec["holes"] if h["body"] in ("JAW_A", "JAW_B") and h["kind"] == "rod_slide"})
    want_rods = sorted({(float(y), float(L["rod_z"])) for y in L["rod_y_a"] + L["rod_y_b"]})
    N["G8_rod_axes"] = {"post_holes": post, "sleeve_bores": bores_, "parameters": want_rods}
    C["G8_rods_coaxial_posts_sleeves"] = post == bores_ == want_rods
    ins = P["rod"]["insert_from"]
    side_of = lambda h: "L" if (h["span"][0] + h["span"][1]) / 2 < 0 else "R"
    sides = {(side_of(h), h["kind"]) for h in base_rod}
    N["G8_rod_fit_sides"] = sorted(f"{s}:{k}" for s, k in sides)
    C["G8_rod_fit_sides"] = sides == {(ins, "rod_slide"), ({"L": "R", "R": "L"}[ins], "rod_press")} and len(base_rod) == 2 * len(want_rods)

    # ---- G7 강도 · 질량 ----
    m, b_ = g["module"], g["face_width"]
    Y_pin, Y_rack = 0.309, 0.485       # 셰글리 Table 14-2(20° · 전 이 높이 · z18) · 랙 0.485 = 조사 값(원문 미확인)
    out7 = {}
    for name, T in (("rated_0.98", 0.98), ("eeprom_limit_50pct_1.47", 1.47), ("stall_2.94", 2.94)):
        Ft_all = T / (r / 1000)
        row = {}
        for share in (0.5, 0.6):                         # 0.5 = 두 랙이 반씩 · 0.6 = 턱 B 안내 마찰로 랙 B 몫이 큰 경우(검토 G05)
            Ft = Ft_all * share
            row[f"share_{share}"] = {"Ft_N": round(Ft, 1), "pinion_MPa": round(Ft / (b_ * m * Y_pin), 1), "rack_MPa_Y_unverified": round(Ft / (b_ * m * Y_rack), 1)}
        row["jaw_force_equal_share_no_friction_N"] = round(Ft_all / 2, 1)
        out7[name] = row
    N["G7_lewis"] = out7
    N["G7_lewis_note"] = "face width = parameters gear.face_width · 피니언 이는 층 면 안(y 아래 출력) · 랙 B 이는 층을 가로지름(층 사이 인장 하한 31 MPa 와 견줌) · 안내 마찰 무시"
    dens = 1.24
    N["G7_note"] = "부피 × 1.24 g/cm³ 는 꽉 찬 어림(상한) — 출력 질량은 슬라이서 기록(print-prep)이 정본"
    N["G7_solid_upper_g"] = {nm: round(mesh[nm].volume / 1000 * dens, 1) for nm in names}
    out["all_true"] = all(C.values())
    out["provenance"] = {"verify_gripper.py": sha(__file__), "guard.py": sha(HERE / "guard.py"), "parameters.json": sha(a.params),
                         "print-fits.json": sha((HERE / P["fits_from"]["ledger"]).resolve()), "build-record.json": sha(rec_path),
                         "print-prep.json": sha(pp_path) if pp_path.is_file() else None}
    out["samples"] = {"u": list(a.u), "g3_phases": list(PHASES), "padsets": ["FLAT", "V"], "variants_padset": "FLAT"}
    text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
    if a.out:
        guard.write_bytes(a.out, text.encode("utf-8"), ROOT, a.scratch_root)
    print(json.dumps({"checks": C, "all_true": out["all_true"]}, ensure_ascii=False, indent=1))
    for k in ("G2_over_limit", "G2_delta_over_limit", "G2_variant_over_limit"):
        if N.get(k):
            print(k, json.dumps(N[k], ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
