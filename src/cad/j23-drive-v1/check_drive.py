# -*- coding: utf-8 -*-
"""MP16 — 구동 모듈 검사(커밋된 부품 STL 을 스스로 재기 · 구매품은 이 파일이 따로 만든 기준 몸체 — 생성기의 형상 명령을 쓰지 않는다).

C0 만들기 기록 sha = 지금 파일 · C1 부품 닫힘 · 한 덩어리 · C2 입력 각 표본마다 인쇄 부품 · 구매품 기준 몸체 쌍 교차 ≤ 0.01 mm³ ·
C3 원판 ↔ 고정 핀 기구학 틈(입력 한 바퀴를 촘촘히) · 출력 핀 ↔ 원판 구멍 · 원판 끝 ↔ 하우징 구멍 · C4 벨트 단(축 거리 · 물린 이 · 장력 · 덮개 ↔ 벨트 · 풀리 · 모터 볼트 머리 —
장력 조절 ±travel 양 끝 · 모터 축이 벨트 가운데까지) · C5 최소 재료 · 틈(설계 수치 + 잰 모터 판 끝) · C6 나사 물림 · C7 구멍 지름(STL 단면에서 잼) ·
C8 출력 준비(print_prep 기록 — 없으면 거짓) · C9 베어링 고리마다 양쪽 받침 면(자기 고리만 · 같은 높이 — 설계 수치). 구매품 기준 몸체끼리도 잰다(벨트 ↔ 풀리만 뺌).
사용: python check_drive.py [--parts <폴더> --record <build-record.json> --out <json>] (기본 = models/j23-drive-v1 · .dev/mp16-evidence)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import manifold3d as m3d
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src" / "cad" / "cycloid-27-v1"))
from build_drive import ASSEMBLY, geometry, ring  # noqa: E402
from cycloid import load_params, profile_xy  # noqa: E402

LIM = 0.01


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def clean(o):
    """numpy 값 → 파이썬 값(재귀)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, np.generic):
        return o.item()
    return o


def man(mesh):
    return m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32), tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))


def tf(mf, ang=0.0, about=(0.0, 0.0), shift=(0.0, 0.0)):
    """z 축 돌림(about 둘레 ang rad) 뒤 옮김."""
    c, s = math.cos(ang), math.sin(ang)
    ax, ay = about
    tx = ax - c * ax + s * ay + shift[0]
    ty = ay - s * ax - c * ay + shift[1]
    return mf.transform(np.array([[c, -s, 0, tx], [s, c, 0, ty], [0, 0, 1, 0]], dtype=np.float32))


def cyl(r, z0, z1, x=0.0, y=0.0, seg=128):
    return m3d.Manifold.cylinder(z1 - z0, r, r, seg).translate([x, y, z0])


def annulus(ri, ro, z0, z1, x=0.0, y=0.0):
    return cyl(ro, z0, z1, x, y) - cyl(ri, z0 - 1, z1 + 1, x, y)


def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def vol(a, b):
    v = (a ^ b).volume()
    return float(v)


def references(P, g, th, motor="J2", travel=0.0):
    """구매품 기준 몸체(입력 각 th rad) — 이름 → (Manifold, 도는 쪽)."""
    E, B = g["E"], P["bearings"]
    rot_out = -th / (P["ring"]["pins"] - 1)
    c1 = (E * math.cos(th), E * math.sin(th))
    c2 = (-c1[0], -c1[1])
    inset = 0.02
    ref = {}
    ref["RING_PINS"] = m3d.Manifold.batch_boolean([cyl(P["ring"]["pin_dia"] / 2, *g["z_ring_pin"], x, y) for x, y in ring(P["ring"]["pins"], P["ring"]["pin_circle_radius"])], m3d.OpType.Add)
    op = P["output_pins"]
    ref["OUT_PINS"] = tf(m3d.Manifold.batch_boolean([cyl(op["dia"] / 2, *g["z_out_pin"], x, y) for x, y in ring(op["count"], op["radius"], op["phase_deg"])], m3d.OpType.Add), rot_out)
    sb = B["shaft"]
    ref["B608_1"] = annulus(sb["id"] / 2 + inset, sb["od"] / 2 - inset, *g["z_b1"])
    ref["B608_2"] = annulus(sb["id"] / 2 + inset, sb["od"] / 2 - inset, *g["z_b2"])
    db = B["disc"]
    ref["B6804_1"] = annulus(db["id"] / 2 + inset, db["od"] / 2 - inset, *g["z_db1"], *c1)
    ref["B6804_2"] = annulus(db["id"] / 2 + inset, db["od"] / 2 - inset, *g["z_db2"], *c2)
    ob = B["output"]
    ref["B6812"] = annulus(ob["id"] / 2 + inset, ob["od"] / 2 - inset, *g["z_ob"])
    s = P["shaft"]
    dsh = cyl(s["dia"] / 2 - 0.01, *g["z_shaft"]) ^ box(-10, 10, -10, s["flat_to_axis"] - 0.01, g["z_shaft"][0] - 1, g["z_shaft"][1] + 1)
    ref["SHAFT"] = tf(dsh, th)
    pe = P["belt"]["pulley_envelope"]
    C = g["C"] + travel
    ref["PULLEY_BIG"] = cyl(pe["big_od"] / 2, *pe["big_z"])
    ref["PULLEY_SMALL"] = cyl(pe["small_od"] / 2, *pe["small_z"], C, 0.0)
    bt = P["belt"]
    zc, w = bt["z_centre"], bt["width"]

    def hullz(r1, r2, z0, z1):
        pts = []
        for (cx, r) in ((0.0, r1), (C, r2)):
            for k in range(96):
                a = 2 * math.pi * k / 96
                for z in (z0, z1):
                    pts.append([cx + r * math.cos(a), r * math.sin(a), z])
        return m3d.Manifold.hull_points(np.array(pts, dtype=np.float32))
    ref["BELT"] = hullz(g["d_big"] / 2 + bt["thickness"] - 0.6, g["d_small"] / 2 + bt["thickness"] - 0.6, zc - w / 2, zc + w / 2) - \
        hullz(g["d_big"] / 2 - 0.6, g["d_small"] / 2 - 0.6, zc - w / 2 - 1, zc + w / 2 + 1)
    m = P["motor"]
    L = m["body_length"][motor] + m["board_length"]
    fz, hf = g["motor_face_z"], m["frame"] / 2
    ref["MOTOR"] = box(C - hf, C + hf, -hf, hf, fz + 0.01, fz + L) + cyl(m["pilot_dia"] / 2, fz - m["pilot_height"], fz + 0.02, C, 0.0) + \
        cyl(m["shaft_dia"] / 2, fz - m["shaft_length"][motor], fz, C, 0.0)
    hb = m["bolt_square"] / 2
    mh = P["screws"]["m5_head"]
    ref["MOTOR_BOLT_HEADS"] = m3d.Manifold.batch_boolean([cyl(mh[0] / 2, -mh[1], -0.01, C + sx * hb, sy * hb) for sx in (-1, 1) for sy in (-1, 1)], m3d.OpType.Add)
    bh, sh = P["screws"]["button_head"], P["screws"]["socket_head"]
    cb = P["base"]["screw_counterbore"]
    ref["CAP_SCREW_HEADS"] = m3d.Manifold.batch_boolean([cyl(sh[0] / 2, 0.02, sh[1] - 0.02, x, y) for x, y in ring(6, P["cap"]["screw_radius"], 30.0)], m3d.OpType.Add)
    zr = g["z_ob"][1] + P["retainer"]["thickness"]
    ref["RETAINER_HEADS"] = m3d.Manifold.batch_boolean([cyl(bh[0] / 2, zr + 0.01, zr + bh[1], x, y) for x, y in ring(6, P["cap"]["retainer_screw_radius"])], m3d.OpType.Add)
    zl = g["z_ob"][1] + P["output_flange"]["thickness"] + P["lever"]["hub_thickness"] - P["lever"]["counterbore"]
    ref["LEVER_HEADS"] = tf(m3d.Manifold.batch_boolean([cyl(bh[0] / 2, zl + 0.01, zl + bh[1], x, y) for x, y in ring(6, P["carrier"]["insert_radius"])], m3d.OpType.Add), rot_out)
    zs = g["face"] + P["stand"]["plate_thickness"] - P["stand"]["counterbore"]
    ref["STAND_HEADS"] = m3d.Manifold.batch_boolean([cyl(bh[0] / 2, zs + 0.01, zs + bh[1], x, y) for x, y in ring(6, P["cap"]["stand_insert_radius"], 30.0)], m3d.OpType.Add)
    gd = P["guard"]
    tabs = [(gd["tab_radius"] * math.cos(math.radians(a)), gd["tab_radius"] * math.sin(math.radians(a))) for a in gd["tab_angles_deg"]] + [(gd["tab_motor_x"], 0.0)]
    ref["GUARD_HEADS"] = m3d.Manifold.batch_boolean([cyl(bh[0] / 2, -3.0 - bh[1], -3.01, x, y) for x, y in tabs], m3d.OpType.Add)
    rot = {"OUT_PINS": "out", "B6804_1": "in", "B6804_2": "in", "SHAFT": "in", "LEVER_HEADS": "out", "PULLEY_BIG": "in"}
    return ref, rot


def posed_parts(meshes, P, g, th):
    E = g["E"]
    rot_out = -th / (P["ring"]["pins"] - 1)
    out = {}
    for n, mf in meshes.items():
        if n in ("CAM_LOWER", "CAM_UPPER", "WASHER_T1p4"):
            out[n] = tf(mf, th)
        elif n == "DISC_1":
            out[n] = tf(mf, rot_out, (E, 0.0), (E * math.cos(th) - E, E * math.sin(th)))
        elif n == "DISC_2":
            out[n] = tf(mf, rot_out, (-E, 0.0), (-E * math.cos(th) + E, -E * math.sin(th)))
        elif n in ("CARRIER", "OUTPUT_FLANGE", "LEVER"):
            out[n] = tf(mf, rot_out)
        else:
            out[n] = mf
    return out


REF_WRAP = {frozenset(p) for p in [("BELT", "PULLEY_BIG"), ("BELT", "PULLEY_SMALL")]}   # 벨트는 풀리를 감는다(기준 몸체끼리 나머지는 모두 잰다 — R1)


# 맞닿게 설계한 쌍(면 접촉 — 교차 부피 0 이어야 하지만 같은 면이라 검사 대상) · 같은 부품의 짝(회전 함께)은 검사하지 않는다
SAME_BODY = {frozenset(p) for p in [("CARRIER", "OUT_PINS"), ("CARRIER", "OUTPUT_FLANGE"), ("OUTPUT_FLANGE", "LEVER"), ("CARRIER", "LEVER"),
                                     ("CAM_LOWER", "SHAFT"), ("CAM_UPPER", "SHAFT"), ("WASHER_T1p4", "SHAFT"), ("LEVER", "LEVER_HEADS"),
                                     ("PULLEY_BIG", "SHAFT"), ("PULLEY_SMALL", "MOTOR"), ("MOTOR", "MOTOR_BOLT_HEADS")]}


def c2_interference(meshes, P, g, thetas, motor, travel):
    rows, worst = [], 0.0
    for td in thetas:
        th = math.radians(td)
        parts = posed_parts(meshes, P, g, th)
        ref, _rot = references(P, g, th, motor, travel)
        allb = {**parts, **ref}
        names = sorted(allb)
        bbs = {n: allb[n].bounding_box() for n in names}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if frozenset((a, b)) in SAME_BODY or frozenset((a, b)) in REF_WRAP:
                    continue
                A, Bb = bbs[a], bbs[b]
                if any(A[k] > Bb[k + 3] + 1e-6 or Bb[k] > A[k + 3] + 1e-6 for k in range(3)):
                    continue
                v = vol(allb[a], allb[b])
                worst = max(worst, v)
                if v > LIM:
                    rows.append({"theta_deg": td, "a": a, "b": b, "mm3": round(v, 4)})
    return {"ok": not rows, "limit_mm3": LIM, "worst_mm3": worst, "over": rows[:40], "thetas": thetas, "motor": motor, "travel": travel}


def c3_kinematics(P, g):
    """원판 ↔ 고정 핀 · 출력 핀 ↔ 원판 구멍 · 원판 끝 ↔ 하우징 — 입력 한 바퀴 720 점(해석)."""
    N, R, E = P["ring"]["pins"], P["ring"]["pin_circle_radius"], g["E"]
    t = np.linspace(0, 2 * np.pi, 20000, endpoint=False)
    prof = profile_xy(t, N, R, g["rr"], E)
    pins = np.array(ring(N, R))
    rp = P["ring"]["pin_dia"] / 2
    op = P["output_pins"]
    opins = np.array(ring(op["count"], op["radius"], op["phase_deg"]))
    gap_pin, gap_out, tip = 1e9, 1e9, 0.0
    for k in range(2):
        for th in np.linspace(0, 2 * np.pi, 720, endpoint=False):
            sign, extra = (1.0, 0.0) if k == 0 else (-1.0, math.pi)
            c = np.array([sign * E * math.cos(th), sign * E * math.sin(th)])
            a = -th / (N - 1) + extra
            Rm = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
            pp = prof @ Rm.T + c
            d = np.min(np.linalg.norm(pp[None, :, :] - pins[:, None, :], axis=2)) - rp
            gap_pin = min(gap_pin, float(d))
            tip = max(tip, float(np.max(np.linalg.norm(pp, axis=1))))
            hc = np.array(ring(op["count"], op["radius"], op["phase_deg"])) @ Rm.T + c     # 원판 구멍 중심(원판에 붙어 돔)
            out_rot = -th / (N - 1)
            Ro = np.array([[math.cos(out_rot), -math.sin(out_rot)], [math.sin(out_rot), math.cos(out_rot)]])
            pc = opins @ Ro.T
            dmin = np.min(np.linalg.norm(hc[:, None, :] - pc[None, :, :], axis=2), axis=0)   # 핀마다 가장 가까운 구멍
            gap_out = min(gap_out, float(np.min(g["out_hole_r"] - dmin - op["dia"] / 2)))
    bore = P["ring"]["pin_circle_radius"]
    return {"ok": gap_pin >= 0.05 and gap_out >= 0.05 and bore - tip >= 0.5,
            "disc_to_ring_pin_min_mm": gap_pin, "output_pin_in_hole_min_mm": gap_out, "disc_tip_max_r": tip, "disc_tip_to_housing_bore_mm": bore - tip,
            "limits": {"pin": 0.05, "out_pin": 0.05, "bore": 0.5}}


def c4_belt(P, g, inp_tension=None):
    bt = P["belt"]
    C, d1, d2 = g["C"], g["d_small"], g["d_big"]
    wrap = 180 - 2 * math.degrees(math.asin((d2 - d1) / (2 * C)))
    teeth = bt["small_teeth"] * wrap / 360
    rows = {"centre_distance": C, "pitch_dia_small": d1, "pitch_dia_big": d2, "wrap_small_deg": wrap, "teeth_in_mesh_small": teeth,
            "ratio": bt["big_teeth"] / bt["small_teeth"] * (P["ring"]["pins"] - 1)}
    rows["belt_below_base_mm"] = 0.0 - (bt["z_centre"] + bt["width"] / 2)
    fz = P["base"]["lobe_thickness"]
    rows["motor_shaft_end_z"] = {k: fz - v for k, v in P["motor"]["shaft_length"].items()}
    rows["motor_shaft_reaches_belt_centre"] = all(z <= bt["z_centre"] + 1e-9 for z in rows["motor_shaft_end_z"].values())   # 허브 없는 풀리의 멈춤나사 높이
    rows["input_shaft_end_below_belt_band"] = g["z_shaft"][0] <= bt["z_centre"] - bt["width"] / 2 - 1.0
    rows["ok"] = (teeth >= 6 and rows["belt_below_base_mm"] >= 1.0 and abs(rows["ratio"] - 81) < 1e-9 and rows["motor_shaft_reaches_belt_centre"]
                  and rows["input_shaft_end_below_belt_band"])
    return rows


def c5_walls(P, g):
    """설계 수치로 잰 최소 재료(부품마다 가장 얇은 곳 후보)."""
    Rr, Rp = P["ring"]["pin_circle_radius"], P["output_pins"]["radius"]
    w = {}
    w["base_pin_hole_to_shaft_seat"] = Rr - g["ring_press_r"] - g["seat"]["shaft"]
    w["base_pin_floor"] = P["ring"]["pin_floor"]
    w["cap_groove_to_outer"] = P["base"]["outer_radius"] - Rr - g["ring_slip_r"]
    w["cap_bottom_insert_to_groove"] = P["cap"]["screw_radius"] - g["ins_r"] - (Rr + g["ring_slip_r"])
    w["cap_bottom_insert_to_outer"] = P["base"]["outer_radius"] - P["cap"]["screw_radius"] - g["ins_r"]
    w["cap_retainer_insert_to_seat"] = P["cap"]["retainer_screw_radius"] - g["ins_r"] - g["seat"]["output"]
    w["cap_stand_insert_to_outer"] = P["base"]["outer_radius"] - P["cap"]["stand_insert_radius"] - g["ins_r"]
    w["cap_above_pin_tops_to_seat_floor"] = g["z_ob"][0] - (g["z_ring_pin"][1] + 0.5)
    w["cap_6812_ledge"] = g["seat"]["output"] - P["cap"]["inner_radius_above_discs"]
    w["cap_cone_end_under_6812_ledge (height, not a wall - thin by design)"] = g["z_ob"][0] - g["z_cone"][1]
    w["stand_counterbore_to_centre_hole"] = P["cap"]["stand_insert_radius"] - P["base"]["screw_counterbore"][0] / 2 - P["stand"]["centre_hole_radius"]
    w["stand_counterbore_to_outer"] = P["stand"]["outer_radius"] - P["cap"]["stand_insert_radius"] - P["base"]["screw_counterbore"][0] / 2
    w["carrier_608_ledge (contact width over the 608 outer ring band - thin by design)"] = g["seat"]["shaft"] - P["carrier"]["seat_ledge_radius"]
    w["carrier_pin_hole_to_plate_edge"] = P["carrier"]["plate_radius"] - Rp - g["out_press_r"]
    w["carrier_pin_floor"] = P["carrier"]["pin_floor"]
    w["carrier_insert_to_hub_edge"] = g["boss"]["output"] - P["carrier"]["insert_radius"] - g["ins_r"]
    w["carrier_insert_to_shaft_lip"] = P["carrier"]["insert_radius"] - g["ins_r"] - P["base"]["lip_bore_dia"] / 2
    w["carrier_hub_insert_floor_above_pins"] = (g["face"] - g["ins_depth"]) - g["z_out_pin"][1]
    w["disc_hole_to_seat"] = Rp - g["out_hole_r"] - g["seat"]["disc"]
    w["disc_hole_to_root"] = (P["ring"]["pin_circle_radius"] - g["E"] - g["rr"]) - (Rp + g["out_hole_r"])
    w["disc_hole_web"] = 2 * Rp * math.sin(math.pi / P["output_pins"]["count"]) - 2 * g["out_hole_r"]
    w["disc_lip"] = g["seat"]["disc"] - P["disc"]["lip_bore_dia"] / 2
    dl = g["d_bore"]["lower"]
    w["cam_lobe_over_d_bore"] = g["boss"]["disc"] - g["E"] - dl[0] / 2
    w["cam_spacer_over_d_bore"] = P["cam"]["spacer_radius"] - g["d_bore"]["upper"][0] / 2
    w["cam_collar_over_d_bore(thin by design - 0.6 tall contact ring)"] = P["cam"]["collar_radius"] - g["E"] - dl[0] / 2
    w["washer_ring"] = P["washer"]["od"] / 2 - (P["shaft"]["dia"] / 2 + P["washer"]["bore_clearance"])
    w["retainer_hole_to_inner"] = P["cap"]["retainer_screw_radius"] - g["m3_r"] - P["cap"]["inner_radius_above_discs"]
    w["retainer_hole_to_outer"] = P["retainer"]["outer_radius"] - P["cap"]["retainer_screw_radius"] - g["m3_r"]
    w["flange_hole_to_edge"] = P["output_flange"]["radius"] - P["carrier"]["insert_radius"] - g["m3_r"]
    lim = P["min_material"]
    short = {k: v for k, v in w.items() if v < lim - 1e-9 and k not in ("base_pin_floor", "carrier_pin_floor", "washer_ring") and "thin by design" not in k}
    short_floor = {k: w[k] for k in ("base_pin_floor", "carrier_pin_floor") if w[k] < 1.0 - 1e-9}
    gaps = {"carrier_plate_to_cap": P["cap"]["inner_radius_above_discs"] - P["carrier"]["plate_radius"],
            "flange_to_retainer": P["cap"]["inner_radius_above_discs"] - P["output_flange"]["radius"],
            "stand_hole_to_retainer_head": P["stand"]["centre_hole_radius"] - (P["cap"]["retainer_screw_radius"] + P["screws"]["button_head"][0] / 2),
            "stand_edge_to_motor": (g["C"] - P["belt"]["slot_travel"] - P["motor"]["frame"] / 2) - P["stand"]["outer_radius"],
            "cap_to_motor": (g["C"] - P["belt"]["slot_travel"] - P["motor"]["frame"] / 2) - P["base"]["outer_radius"],
            "lever_arm_above_stand": (g["z_ob"][1] + P["output_flange"]["thickness"] + P["lever"]["hub_thickness"] - P["lever"]["arm_thickness"]) -
            (g["face"] + P["stand"]["plate_thickness"])}
    bad_gap = {k: v for k, v in gaps.items() if v < 0.8}
    return {"ok": not short and not short_floor and not bad_gap, "min_material": lim, "walls": w, "gaps": gaps, "short": short, "short_floor": short_floor, "bad_gap": bad_gap}


def c6_screws(P, g):
    s = P["screws"]
    ins_len, depth = 6.0, g["ins_depth"]
    rows = {}
    gap = P["cap"]["seat_proud"]                                         # 누름 고리 · 플랜지 밑 = 6812 고리 면(덮개 · 허브 면보다 0.2 위)
    under = {"cap": P["base"]["thickness"] - P["base"]["screw_counterbore"][1], "retainer": P["retainer"]["thickness"] + gap,
             "flange": P["output_flange"]["thickness"] + gap, "lever": P["lever"]["hub_thickness"] - P["lever"]["counterbore"] + P["output_flange"]["thickness"] + gap,
             "stand": P["stand"]["plate_thickness"] - P["stand"]["counterbore"], "guard": 3.0}
    for k, t in under.items():
        L = s[k][1]
        eng = L - t
        rows[k] = {"screw": f"M{s[k][0]} x {L}", "clamped": t, "engagement": eng, "tip_to_floor": depth - eng,
                   "ok": eng >= s["min_engagement"] - 1e-9 and depth - eng >= s["tip_to_floor_min"] - 1e-9}
    L = s["guard_motor_end"][1]
    clamp = 3.0 + P["base"]["lobe_thickness"]
    rows["guard_motor_end"] = {"screw": f"M3 x {L} + nut", "clamped": clamp, "past_nut": L - clamp - s["m3_nut"], "ok": L - clamp - s["m3_nut"] >= 1.0}
    rows["insert_assumed_length"] = ins_len
    return {"ok": all(v["ok"] for v in rows.values() if isinstance(v, dict)), "rows": rows}


def c9_bearing_faces(P, g):
    """베어링 고리마다 양쪽 면에 닿는 부품 면(설계 수치) — 자기 고리의 확실한 띠와 겹치고 다른 고리(넓은 한계)와는 떨어지는가 · 높이가 같은가."""
    B, E = P["bearings"], g["E"]
    fmin, fmax = B["ring_section_min_factor"], B["ring_section_factor"]

    def bands(k):
        d, D = B[k]["id"], B[k]["od"]
        return {"inner_own": (d / 2, (d + fmin * (D - d)) / 2), "inner_other_from": (D - fmax * (D - d)) / 2,
                "outer_own": ((D - fmin * (D - d)) / 2, D / 2), "outer_other_to": (d + fmax * (D - d)) / 2}
    th = np.linspace(0, 2 * np.pi, 360, endpoint=False)

    def dists(pc, bc, ri, ro):
        rr = np.linspace(ri, ro, 25)
        X = pc[0] + np.outer(rr, np.cos(th)) - bc[0]
        Y = pc[1] + np.outer(rr, np.sin(th)) - bc[1]
        return np.hypot(X, Y)
    cm, cr, ci = P["cam"], P["carrier"], P["cap"]
    dl = g["d_bore"]["lower"][0] / 2
    # (베어링, 쪽, 고리, 베어링 중심, 고리 면 z, 부품, 부품 면 z, 부품 중심, 부품 면 r 안 · 밖)
    rows = [("608_1", "outer", "bottom", (0, 0), g["z_b1"][0], "HOUSING_BASE lip", g["z_b1"][0], (0, 0), P["base"]["lip_bore_dia"] / 2, g["seat"]["shaft"]),
            ("608_1", "inner", "top", (0, 0), g["z_b1"][1], "CAM_LOWER collar", g["z_collar_lo"][0], (0, 0), dl, cm["collar_radius"]),
            ("6804_1", "inner", "bottom", (E, 0), g["z_db1"][0], "CAM_LOWER hub", g["z_db1"][0], (E, 0), g["boss"]["disc"], cm["hub_radius"]),
            ("6804_1", "inner", "top", (E, 0), g["z_db1"][1], "CAM_UPPER spacer", g["z_db1"][1], (0, 0), g["d_bore"]["upper"][0] / 2, cm["spacer_radius"]),
            ("6804_1", "outer", "bottom", (E, 0), g["z_db1"][0], "DISC_1 seat floor", g["z_db1"][0], (E, 0), P["disc"]["lip_bore_dia"] / 2, g["seat"]["disc"]),
            ("6804_2", "inner", "bottom", (-E, 0), g["z_db2"][0], "CAM_UPPER spacer", g["z_db2"][0], (0, 0), g["d_bore"]["upper"][0] / 2, cm["spacer_radius"]),
            ("6804_2", "inner", "top", (-E, 0), g["z_db2"][1], "CAM_UPPER collar", g["z_collar_up"][0], (-E, 0), g["boss"]["disc"], cm["upper_collar_radius"]),
            ("6804_2", "outer", "bottom", (-E, 0), g["z_db2"][0], "DISC_2 seat floor", g["z_db2"][0], (-E, 0), P["disc"]["lip_bore_dia"] / 2, g["seat"]["disc"]),
            ("608_2", "inner", "bottom", (0, 0), g["z_b2"][0], "WASHER", g["z_washer"][1], (0, 0), P["shaft"]["dia"] / 2 + P["washer"]["bore_clearance"], P["washer"]["od"] / 2),
            ("608_2", "outer", "top", (0, 0), g["z_b2"][1], "CARRIER 608 ledge", g["z_b2"][1], (0, 0), cr["seat_ledge_radius"], g["seat"]["shaft"]),
            ("6812", "outer", "bottom", (0, 0), g["z_ob"][0], "CAP ledge", g["z_ob"][0], (0, 0), ci["inner_radius_above_discs"], g["seat"]["output"]),
            ("6812", "outer", "top", (0, 0), g["z_ob"][1], "RETAINER", g["z_ob"][1], (0, 0), ci["inner_radius_above_discs"], P["retainer"]["outer_radius"]),
            ("6812", "inner", "bottom", (0, 0), g["z_ob"][0], "CARRIER plate top", g["car_top"], (0, 0), g["boss"]["output"], cr["inner_ring_relief_radius"]),
            ("6812", "inner", "top", (0, 0), g["z_ob"][1], "OUTPUT_FLANGE", g["z_ob"][1], (0, 0), 0.0, P["output_flange"]["radius"])]
    out, ok = [], True
    for brg, ringk, side, bc, zb, part, zp, pc, ri, ro in rows:
        k = {"608_1": "shaft", "608_2": "shaft", "6804_1": "disc", "6804_2": "disc", "6812": "output"}[brg]
        bd = bands(k)
        d = dists(pc, bc, ri, ro)
        if ringk == "inner":
            own = bool(np.any((d >= bd["inner_own"][0]) & (d <= bd["inner_own"][1])))
            clear = bool(np.max(d) < bd["inner_other_from"] - 1e-6)
        else:
            own = bool(np.any((d >= bd["outer_own"][0]) & (d <= bd["outer_own"][1])))
            clear = bool(np.min(d) > bd["outer_other_to"] + 1e-6)
        same_z = abs(zp - zb) < 1e-6
        good = own and clear and same_z
        ok &= good
        out.append({"bearing": brg, "ring": ringk, "side": side, "part": part, "touches_own_ring": own, "clear_of_other_ring": clear, "same_height": same_z, "ok": good})
    return {"ok": ok, "rows": out, "note": "6804 outer rings are held by the press fit in the disc seats (flush with the disc top) - the top side has no shoulder by design (as MP6)"}


def c7_holes(parts_dir, P, g):
    """STL 단면에서 구멍 지름을 잰다(가장 가까운 단면 고리의 평균 반지름)."""
    def ring_r(stl, z, cx, cy, expect):
        m = trimesh.load(stl, force="mesh")
        sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        best = None
        for e in sec.discrete:   # 중심이 (cx, cy) 에서 1 mm 안인 고리 중 반지름이 기대에 가장 가까운 것(동심 고리가 여럿일 수 있음)
            pts = np.asarray(e)[:, :2]
            c = pts.mean(axis=0)
            if float(np.hypot(c[0] - cx, c[1] - cy)) < 1.0:
                r = float(np.max(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)))   # 꼭짓점 최대 거리(단면 꼭짓점 일부는 면의 현 위라 평균은 작게 나옴)
                if best is None or abs(r - expect) < abs(best - expect):
                    best = r
        if best is None:         # 열린 홈(구멍 벽에 반쯤 묻힌 핀 홈) — 모든 고리에서 중심 둘레 기대 + 0.3 안의 점들의 최대 거리
            allp = np.vstack([np.asarray(e)[:, :2] for e in sec.discrete])
            dd = np.hypot(allp[:, 0] - cx, allp[:, 1] - cy)
            near = dd[dd < expect + 0.3]
            best = float(near.max()) if near.size else None
        return best
    Rr, E = P["ring"]["pin_circle_radius"], g["E"]
    zo, zb2, zd1 = sum(g["z_ob"]) / 2, sum(g["z_b2"]) / 2, sum(g["z_db1"]) / 2
    q = [("HOUSING_BASE", "ring pin press", (P["ring"]["pin_floor"] + g["T"]) / 2, Rr, 0.0, g["ring_press_r"]), ("HOUSING_BASE", "608 seat", sum(g["z_b1"]) / 2, 0.0, 0.0, g["seat"]["shaft"]),
         ("CAP", "ring pin groove (open, half in the bore)", (g["z_d1"][0] + g["z_d2"][1]) / 2, Rr, 0.0, g["ring_slip_r"]), ("CAP", "6812 seat", zo, 0.0, 0.0, g["seat"]["output"]),
         ("CARRIER", "output pin press", (g["z_car"] + g["z_out_pin"][1]) / 2, P["output_pins"]["radius"], 0.0, g["out_press_r"]),
         ("CARRIER", "608 seat", zb2, 0.0, 0.0, g["seat"]["shaft"]), ("CARRIER", "6812 hub (outside)", zo, 0.0, 0.0, g["boss"]["output"]),
         ("DISC_1", "6804 seat", zd1, E, 0.0, g["seat"]["disc"]), ("DISC_1", "output pin hole", sum(g["z_d1"]) / 2, E + P["output_pins"]["radius"], 0.0, g["out_hole_r"]),
         ("CAM_LOWER", "6804 lobe (outside)", zd1, E, 0.0, g["boss"]["disc"])]
    rows, ok = [], True
    for body, what, z, cx, cy, expect in q:
        r = ring_r(parts_dir / f"{body}.stl", z, cx, cy, expect)
        good = r is not None and abs(r - expect) <= 0.03
        ok &= good
        rows.append({"body": body, "what": what, "z": z, "expect_r": expect, "measured_r": r, "ok": good})
    return {"ok": ok, "rows": rows, "tolerance_mm": 0.03}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", type=Path, default=ROOT / "models" / "j23-drive-v1" / "parts")
    ap.add_argument("--record", type=Path, default=ROOT / ".dev" / "mp16-evidence" / "build" / "build-record.json")
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--out", type=Path, default=ROOT / "models" / "j23-drive-v1" / "check.json")
    ap.add_argument("--quick", action="store_true", help="C2 at 4 angles only")
    a = ap.parse_args()
    rec = json.loads(a.record.read_text(encoding="utf-8"))
    P = load_params(a.params)        # 기대값 = 설계(매개변수 + 원장) — 양성 대조 판도 이 값으로 잰다
    g = geometry(P)
    res = {}
    stl_sha = {k: sha(a.parts / Path(k).name) for k in rec["outputs_sha256"] if k.startswith("parts/")}
    res["C0"] = {"ok": all(stl_sha[k] == v for k, v in rec["outputs_sha256"].items() if k in stl_sha) and
                 (rec.get("control") or rec["inputs_sha256"]["parameters.json"] == sha(a.params)) and
                 rec["inputs_sha256"]["build_drive.py"] == sha(HERE / "build_drive.py"), "control": rec.get("control")}
    meshes, c1 = {}, {}
    for n in ASSEMBLY:
        tm = trimesh.load(a.parts / f"{n}.stl", force="mesh")
        c1[n] = {"watertight": bool(tm.is_watertight), "pieces": len(tm.split(only_watertight=False))}
        meshes[n] = man(tm)
    res["C1"] = {"ok": all(v["watertight"] and v["pieces"] == 1 for v in c1.values()), "bodies": c1}
    thetas = [0, 90, 180, 270] if a.quick else P["checks"]["theta_deg"]
    res["C2"] = c2_interference(meshes, P, g, thetas, "J2", 0.0)
    res["C2_motor_J3"] = c2_interference(meshes, P, g, [0], "J3", 0.0)
    tr = P["belt"]["slot_travel"]
    res["C2_slot_ends"] = {"minus": c2_interference(meshes, P, g, [0], "J2", -tr), "plus": c2_interference(meshes, P, g, [0], "J2", tr)}
    res["C2_slot_ends"]["ok"] = res["C2_slot_ends"]["minus"]["ok"] and res["C2_slot_ends"]["plus"]["ok"]
    res["C3"] = c3_kinematics(P, g)
    res["C4"] = c4_belt(P, g)
    res["C5"] = c5_walls(P, g)
    bx = trimesh.load(a.parts / "HOUSING_BASE.stl", force="mesh").bounds[1][0]       # 잰 값: 모터 판 끝이 볼트 구멍 · 덮개 나사 구멍을 감싸는가
    need = max(g["C"] + P["motor"]["bolt_square"] / 2 + P["belt"]["slot_travel"] + P["fits"]["m5_clearance"] / 2, P["guard"]["tab_motor_x"] + g["m3_r"]) + P["min_material"]
    res["C5"]["lobe_end_measured"], res["C5"]["lobe_end_needed"] = float(bx), need
    res["C5"]["ok"] = res["C5"]["ok"] and bx >= need - 1e-6
    res["C6"] = c6_screws(P, g)
    res["C7"] = c7_holes(a.parts, P, g)
    res["C9"] = c9_bearing_faces(P, g)
    pp = ROOT / ".dev" / "mp16-evidence" / "printprep.json"
    if not rec.get("control") and not pp.is_file():
        res["C8"] = {"ok": False, "printprep": "missing - run print_prep_drive.py"}
    if pp.is_file() and not rec.get("control"):
        pr = json.loads(pp.read_text(encoding="utf-8"))
        res["C8"] = {"ok": pr.get("ok", False) and all(pr["parts"][n]["parts_sha256"] == stl_sha.get(f"parts/{n}.stl") for n in pr["parts"]), "printprep": str(pp.name)}
    verdict = bool(all(bool(v.get("ok", False)) for k, v in res.items() if isinstance(v, dict) and "ok" in v))
    out = {"what": "MP16 구동 모듈 검사 — 커밋된 STL 로 스스로 계산", "verdict": verdict, "results": res, "record": rec.get("outputs_sha256")}
    a.out.write_bytes((json.dumps(clean(out), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps(clean({k: v.get("ok") for k, v in res.items() if isinstance(v, dict)}), ensure_ascii=False), "verdict", verdict)


if __name__ == "__main__":
    main()
