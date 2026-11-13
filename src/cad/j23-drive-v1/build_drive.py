# -*- coding: utf-8 -*-
"""MP16 — J2 · J3 공통 구동 모듈 v1 (SolidCraft): NEMA23 + SERVO57D → HTD 3M 벨트 20 : 60 → 인쇄 사이클로이드(핀 28 · 로브 27) = 81 : 1.

좌표 = parameters.json frame(관절 축 z · 바닥판 밑면 z 0 · 출력 +z · 벨트 쪽 −z · 모터 축 x = 축 거리 · y 0). 모든 부품을 조립 자리(입력 각 0)로 만든다
(원판 2 = 원판 1 과 같은 부품을 제 중심에서 180° 돌린 것 — 출력 판에는 DISC_1 을 두 번). 윤곽은 MP6 생성기(`cycloid.make_profile`)를 읽기만 해서 쓴다.
끼움 · 구멍 보정은 원장(fits_from)에서 읽는다(Ø6 · Ø8 핀 구멍 = 핀 + Ø4 시험의 더한 값 — 가정). 쓰기 = models/j23-drive-v1 · .dev/mp16-evidence · --scratch 만.
사용: python build_drive.py --cli <solidcraft-cli.exe> --scratch <작업 폴더> [--control <이름> --out <작업 폴더 아래>] [--no-snapshot]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME = "j23-drive-v1"
EV = ROOT / ".dev" / "mp16-evidence"
sys.path.insert(0, str(ROOT / "src" / "cad" / "cycloid-27-v1"))
from cycloid import load_params, make_profile  # noqa: E402  (MP6 — 읽기만)

ASSEMBLY = ["HOUSING_BASE", "CAP", "CARRIER", "DISC_1", "DISC_2", "CAM_LOWER", "CAM_UPPER", "WASHER_T1p4", "RETAINER", "OUTPUT_FLANGE", "GUARD", "STAND", "LEVER"]
EXTRA = ["WASHER_T1p2", "WASHER_T1p6"]          # 조립에 안 쓰는 와셔 두 벌(조립 자리 밖 — 출력 판에만)
CONTROLS = {"pin_tight": "ring pin press hole = pin (no oversize)", "disc_big": "profile clearance -0.15 (disc lobes grown into the ring pins)",
            "plate_wide": "carrier plate radius 36.5 (meets the cap lip)", "seat_small": "bearing seats 0.2 under the bearing outside diameter",
            "lobe_short": "lobe ends at x 110 (motor bolt slots cut off)", "guard_narrow": "guard inner half width 22 (motor bolt heads)"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inside(p, *roots):
    p = Path(p).resolve()
    return any(p == r.resolve() or r.resolve() in p.parents for r in roots)


def belt_centre(L, z1, z2, pitch):
    d1, d2 = z1 * pitch / math.pi, z2 * pitch / math.pi
    b = L - math.pi * (d1 + d2) / 2
    return (b + math.sqrt(b * b - 2 * (d2 - d1) ** 2)) / 4, d1, d2


def geometry(P):
    """쌓임 · 반지름(검사도 이 함수를 부른다)."""
    F, B, d = P["fits"], P["bearings"], P["disc"]
    T = P["base"]["thickness"]
    g = {"E": P["eccentricity"], "T": T}
    g["z_d1"] = [T + d["axial_gap"], T + d["axial_gap"] + d["thickness"]]
    g["z_d2"] = [g["z_d1"][1] + d["axial_gap"], g["z_d1"][1] + d["axial_gap"] + d["thickness"]]
    g["z_car"] = g["z_d2"][1] + d["axial_gap"]
    g["car_top"] = P["carrier"]["plate_top"]
    g["z_ob"] = [g["car_top"], g["car_top"] + B["output"]["width"]]
    assert abs(g["z_ob"][1] - P["cap"]["top"]) < 1e-9, "cap top must equal the 6812 top"
    s = P["shaft"]
    g["z_shaft"] = [s["z_bottom"], s["z_bottom"] + s["length"]]
    g["z_b1"] = [P["base"]["shaft_seat_from"], P["base"]["shaft_seat_from"] + B["shaft"]["width"]]
    g["z_b2"] = [g["z_shaft"][1] - B["shaft"]["width"], g["z_shaft"][1]]
    g["z_db1"] = [g["z_d1"][1] - B["disc"]["width"], g["z_d1"][1]]
    g["z_db2"] = [g["z_d2"][1] - B["disc"]["width"], g["z_d2"][1]]
    c = P["cam"]
    g["z_collar_lo"] = [g["z_b1"][1], g["z_b1"][1] + c["collar_height"]]
    g["z_collar_up"] = [g["z_d2"][1], g["z_d2"][1] + c["collar_height"]]
    g["z_washer"] = [g["z_collar_up"][1], g["z_b2"][0]]
    g["washer_t"] = round(g["z_washer"][1] - g["z_washer"][0], 3)
    g["seat"] = {k: (B[k]["od"] + F["bearing_seat_extra"]) / 2 for k in ("disc", "output", "shaft")}
    g["boss"] = {k: (B[k]["id"] + F["bearing_bore_extra"]) / 2 for k in ("disc", "output")}
    po, ps = F["pin_press_hole_dia"] - 4.0, F["pin_slip_hole_dia"] - 4.0
    g["ring_press_r"] = (P["ring"]["pin_dia"] + po) / 2
    g["ring_slip_r"] = (P["ring"]["pin_dia"] + ps) / 2
    g["out_press_r"] = (P["output_pins"]["dia"] + po) / 2
    g["out_hole_r"] = P["output_pins"]["dia"] / 2 + g["E"] + P["fits"]["output_hole_clearance"]
    g["z_ring_pin"] = [P["ring"]["pin_floor"], P["ring"]["pin_floor"] + P["ring"]["pin_length"]]
    g["face"] = P["cap"]["top"] - P["cap"]["seat_proud"]                 # 덮개 윗면 · 허브 윗면(6812 고리 면보다 0.2 아래 — 누름 고리 · 플랜지가 고리를 누름)
    g["z_cone"] = [g["z_ring_pin"][1] + P["cap"]["cone_start_above_pin_tops"], 0.0]
    g["z_cone"][1] = g["z_cone"][0] + (P["ring"]["pin_circle_radius"] - P["cap"]["inner_radius_above_discs"])
    assert g["z_cone"][1] < g["z_ob"][0] - 0.5, "cone must end under the 6812 ledge"
    g["z_out_pin"] = [g["car_top"] - P["carrier"]["pin_floor"] - P["output_pins"]["length"], g["car_top"] - P["carrier"]["pin_floor"]]
    g["d_bore"] = {"lower": [s["dia"] + F["d_bore_extra"], s["flat_to_axis"] + F["d_bore_extra"] / 2],
                   "upper": [s["dia"] + F["d_bore_extra"] + F["cam_upper_bore_extra"], s["flat_to_axis"] + (F["d_bore_extra"] + F["cam_upper_bore_extra"]) / 2]}
    g["ins_r"], g["ins_depth"], g["m3_r"] = F["insert_hole_dia"] / 2, P["fits"]["insert_hole_depth"], F["m3_clearance_dia"] / 2
    bt = P["belt"]
    g["C"], g["d_small"], g["d_big"] = belt_centre(bt["length"], bt["small_teeth"], bt["big_teeth"], bt["pitch"])
    g["motor_face_z"] = P["base"]["lobe_thickness"]
    g["pilot_recess"] = [g["motor_face_z"] - 2.0, g["motor_face_z"]]
    g["rr"] = P["ring"]["pin_dia"] / 2 + P["fits"]["profile_clearance"]
    g["disc_tip_r"] = P["ring"]["pin_circle_radius"] + g["E"] - g["rr"]
    return g


def ring(n, r, phase_deg=0.0):
    return [(r * math.cos(math.radians(phase_deg) + 2 * math.pi * k / n), r * math.sin(math.radians(phase_deg) + 2 * math.pi * k / n)) for k in range(n)]


def hull(points):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def circle_pts(cx, cy, r, n=96):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def d_shape(dia, flat, n=64):
    """D 구멍 윤곽 — 지름 dia · 평면은 +y 쪽(축에서 flat) · (x, y)."""
    r = dia / 2
    a0 = math.asin(min(1.0, flat / r))
    angs = [a0 + (math.pi - 2 * a0) * 0 for _ in range(0)]
    start, end = math.pi - a0, 2 * math.pi + a0          # 평면 위 끝(왼쪽) → 아래로 돌아 → 평면 위 끝(오른쪽)
    pts = [(r * math.cos(start + (end - start) * k / n), r * math.sin(start + (end - start) * k / n)) for k in range(n + 1)]
    return pts + angs


def stadium(cx, cy, r, travel, n=24):
    """x 로 ±travel 길쭉한 구멍(반지름 r)."""
    pts = [(cx + travel + r * math.cos(-math.pi / 2 + math.pi * k / n), cy + r * math.sin(-math.pi / 2 + math.pi * k / n)) for k in range(n + 1)]
    pts += [(cx - travel + r * math.cos(math.pi / 2 + math.pi * k / n), cy + r * math.sin(math.pi / 2 + math.pi * k / n)) for k in range(n + 1)]
    return pts


class SC:
    def __init__(self):
        self.c = []

    def cmd(self, c, **p):
        self.c.append({"command": c, "params": p})

    def plane(self, z):
        return {"origin": [0.0, 0.0, float(z)], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}

    def revolve(self, name, prof, cx=0.0, cy=0.0, op="new", target=None):
        self.cmd("sketch.create", name=name + "_RV_SK", plane={"origin": [float(cx), float(cy), 0.0], "x_dir": [0, 0, 1], "y_dir": [1, 0, 0]})
        self.cmd("sketch.line", points=[[float(u), float(v)] for u, v in prof], closed=True)
        self.cmd("sketch.finish")
        kw = {"body_name": name} if op == "new" else {"targets": [target]}
        self.cmd("solid.revolve", axis="x", operation=op, name=name + "_RV", **kw)

    def circles(self, body, z, centers, r, dist, op="cut", direction=None, tag="C"):
        self.cmd("sketch.create", name=f"{body}_{tag}_SK", plane=self.plane(z))
        for x, y in centers:
            self.cmd("sketch.circle.center", center=[float(x), float(y)], radius=float(r))
        self.cmd("sketch.finish")
        kw = {"body_name": body} if op == "new" else {"targets": [body]}
        if direction:
            kw["direction"] = direction
        self.cmd("solid.extrude", distance=float(dist), operation=op, name=f"{body}_{tag}_X", **kw)

    def poly(self, body, z, pts_list, dist, op="cut", direction=None, tag="P"):
        self.cmd("sketch.create", name=f"{body}_{tag}_SK", plane=self.plane(z))
        for pts in pts_list:
            self.cmd("sketch.line", points=[[float(x), float(y)] for x, y in pts], closed=True)
        self.cmd("sketch.finish")
        kw = {"body_name": body} if op == "new" else {"targets": [body]}
        if direction:
            kw["direction"] = direction
        self.cmd("solid.extrude", distance=float(dist), operation=op, name=f"{body}_{tag}_X", **kw)

    def rect(self, body, z, p0, p1, radius, dist, op="join", direction=None, tag="R"):
        self.cmd("sketch.create", name=f"{body}_{tag}_SK", plane=self.plane(z))
        self.cmd("sketch.rectangle.rounded", p0=[float(p0[0]), float(p0[1])], p1=[float(p1[0]), float(p1[1])], radius=float(radius))
        self.cmd("sketch.finish")
        kw = {"body_name": body} if op == "new" else {"targets": [body]}
        if direction:
            kw["direction"] = direction
        self.cmd("solid.extrude", distance=float(dist), operation=op, name=f"{body}_{tag}_X", **kw)


def disc_outline(P, g):
    pts, n, err = make_profile(P["ring"]["pins"], P["ring"]["pin_circle_radius"], g["rr"], g["E"], P["checks"]["profile_chord_error_max"])
    return [(float(x), float(y)) for x, y in pts], n, err


def commands(P, g):
    sc = SC()
    E, T = g["E"], g["T"]
    Rr, Rp = P["ring"]["pin_circle_radius"], P["output_pins"]["radius"]
    pins = ring(P["ring"]["pins"], Rr)
    scr_cap = ring(P["cap"]["screw_count"], P["cap"]["screw_radius"], 30.0)
    b = P["base"]
    # ---- HOUSING_BASE ----
    sc.circles("HOUSING_BASE", 0.0, [(0, 0)], b["outer_radius"], T, op="new", tag="DISK")
    sc.rect("HOUSING_BASE", 0.0, (30.0, -b["lobe_half_width"]), (b["lobe_x_end"], b["lobe_half_width"]), b["lobe_corner"], b["lobe_thickness"], tag="LOBE")
    sc.circles("HOUSING_BASE", T + 0.5, [(0, 0)], b["lip_bore_dia"] / 2, T + 1.0, direction="negative", tag="LIP")
    sc.circles("HOUSING_BASE", T + 0.5, [(0, 0)], g["seat"]["shaft"], T + 0.5 - g["z_b1"][0], direction="negative", tag="SEAT")
    sc.circles("HOUSING_BASE", T + 0.5, pins, g["ring_press_r"], T + 0.5 - P["ring"]["pin_floor"], direction="negative", tag="PIN")
    sc.circles("HOUSING_BASE", T + 0.5, scr_cap, g["m3_r"], T + 1.0, direction="negative", tag="CAPSCR")
    sc.circles("HOUSING_BASE", -0.5, scr_cap, b["screw_counterbore"][0] / 2, b["screw_counterbore"][1] + 0.5, tag="CAPCB")
    gd = P["guard"]
    tabs = [(gd["tab_radius"] * math.cos(math.radians(a)), gd["tab_radius"] * math.sin(math.radians(a))) for a in gd["tab_angles_deg"]]
    sc.circles("HOUSING_BASE", -0.5, tabs, g["ins_r"], g["ins_depth"] + 0.5, tag="GINS")
    sc.circles("HOUSING_BASE", -0.5, [(gd["tab_motor_x"], 0.0)], g["m3_r"], b["lobe_thickness"] + 1.0, tag="GTHRU")
    C, h = g["C"], P["motor"]["bolt_square"] / 2
    tr = P["belt"]["slot_travel"]
    lt = b["lobe_thickness"]
    sc.poly("HOUSING_BASE", -0.5, [stadium(C + sx * h, sy * h, P["fits"]["m5_clearance"] / 2, tr) for sx in (-1, 1) for sy in (-1, 1)], lt + 1.0, tag="MSLOT")
    sc.poly("HOUSING_BASE", lt + 0.5, [stadium(C, 0.0, P["motor"]["pilot_dia"] / 2 + P["fits"]["slot_width_extra"] / 2, tr)], 2.5, direction="negative", tag="PILOT")
    sc.poly("HOUSING_BASE", -0.5, [stadium(C, 0.0, 7.0, tr)], lt + 1.0, tag="SHAFT")
    # ---- CAP ----
    ci = P["cap"]
    zp_top = g["z_ring_pin"][1]
    # 덮개는 바로(밑면 z 10 을 판에) 출력 — 원판 위 안쪽 처마 = 45° 경사. 경사는 고정 핀 끝(+1)보다 위에서 시작한다: 경사가 핀 홈과 만나면
    # SolidCraft STL 이 홈 사이에서 열렸다(R0 · fine / finest 모두) → 6812 를 핀 끝 위로 올림(R1). 6812 턱(z_ob[0])은 윗면이라 판 위에서 평평하다.
    ri = ci["inner_radius_above_discs"]
    sc.revolve("CAP", [(T, Rr), (T, b["outer_radius"]), (g["face"], b["outer_radius"]), (g["face"], g["seat"]["output"]), (g["z_ob"][0], g["seat"]["output"]),
                       (g["z_ob"][0], ri), (g["z_cone"][1], ri), (g["z_cone"][0], Rr)])
    sc.circles("CAP", T - 0.5, pins, g["ring_slip_r"], zp_top + 0.5 - (T - 0.5), tag="GROOVE")
    sc.circles("CAP", T - 0.5, scr_cap, g["ins_r"], g["ins_depth"] + 0.5, tag="BINS")
    sc.circles("CAP", g["face"] + 0.5, ring(6, ci["retainer_screw_radius"], 0.0), g["ins_r"], g["ins_depth"] + 0.5, direction="negative", tag="RINS")
    sc.circles("CAP", g["face"] + 0.5, ring(6, ci["stand_insert_radius"], 30.0), g["ins_r"], g["ins_depth"] + 0.5, direction="negative", tag="SINS")
    # ---- CARRIER ----
    cr = P["carrier"]
    zr = g["car_top"] - cr["relief_depth"]                               # 판 윗면은 6812 속 고리 띠까지만(그 밖은 0.5 낮춤 — 시일 · 바깥 고리에 안 닿게)
    sc.revolve("CARRIER", [(g["z_car"], g["seat"]["shaft"]), (g["z_car"], cr["plate_radius"]), (zr, cr["plate_radius"]), (zr, cr["inner_ring_relief_radius"]),
                           (g["car_top"], cr["inner_ring_relief_radius"]), (g["car_top"], g["boss"]["output"]),
                           (g["face"], g["boss"]["output"]), (g["face"], 0.0), (g["z_b2"][1] + 2.0, 0.0), (g["z_b2"][1] + 2.0, b["lip_bore_dia"] / 2),
                           (g["z_b2"][1], cr["seat_ledge_radius"]), (g["z_b2"][1], g["seat"]["shaft"])])   # 608 바깥 고리 위 = 좁은 턱 + 45°
    sc.circles("CARRIER", g["z_car"] - 0.5, ring(P["output_pins"]["count"], Rp, P["output_pins"]["phase_deg"]), g["out_press_r"],
               g["z_out_pin"][1] - (g["z_car"] - 0.5), tag="OPIN")
    sc.circles("CARRIER", g["face"] + 0.5, ring(cr["inserts"], cr["insert_radius"], 0.0), g["ins_r"], g["ins_depth"] + 0.5, direction="negative", tag="HINS")
    # ---- DISC_1 / DISC_2 (조립 자리 · 입력 각 0) ----
    prof, _n, _e = disc_outline(P, g)
    for name, (cx, cy), rot, z0 in (("DISC_1", (E, 0.0), 0.0, g["z_d1"][0]), ("DISC_2", (-E, 0.0), math.pi, g["z_d2"][0])):
        cs, sn = math.cos(rot), math.sin(rot)
        pts = [(cx + x * cs - y * sn, cy + x * sn + y * cs) for x, y in prof]
        sc.poly(name, z0, [pts], P["disc"]["thickness"], op="new", tag="PROF")
        top = z0 + P["disc"]["thickness"]
        sc.circles(name, top + 0.5, [(cx, cy)], g["seat"]["disc"], P["bearings"]["disc"]["width"] + 0.5, direction="negative", tag="SEAT")
        sc.circles(name, top + 0.5, [(cx, cy)], P["disc"]["lip_bore_dia"] / 2, P["disc"]["thickness"] + 1.0, direction="negative", tag="LIP")
        holes = [(cx + x * cs - y * sn, cy + x * sn + y * cs) for x, y in ring(P["output_pins"]["count"], Rp, P["output_pins"]["phase_deg"])]
        sc.circles(name, top + 0.5, holes, g["out_hole_r"], P["disc"]["thickness"] + 1.0, direction="negative", tag="OHOLE")
    # ---- CAM_LOWER / CAM_UPPER (D 축 평면 = +y · 아래 편심 +x · 위 편심 −x) ----
    cm = P["cam"]
    zc0, zc1 = g["z_collar_lo"]
    zcone = min(zc1 + (cm["hub_radius"] - cm["collar_radius"]), g["z_db1"][0] - 0.4)   # 목 → 허브 45° 경사(목을 판에 두고 지지대 없이)
    sc.circles("CAM_LOWER", zc0, [(0, 0)], cm["collar_radius"], cm["collar_height"], op="new", tag="COLLAR")   # 목 = 축 중심(608 속 고리만 — R1)
    zs0 = zc1 + 0.2                                                        # 편심 원통이 목 윗면과 같은 높이에서 꺾이면 STL 에 조각이 생겼다(R1) → 0.2 엇갈림
    zcone = min(zs0 + (cm["hub_radius"] - cm["collar_radius"]), g["z_db1"][0] - 0.4)
    sc.revolve("CAM_LOWER", [(zc0 + 0.3, 0.0), (zc0 + 0.3, cm["collar_radius"]), (zs0, cm["collar_radius"]), (zcone, cm["hub_radius"]), (g["z_db1"][0], cm["hub_radius"]),
                             (g["z_db1"][0], g["boss"]["disc"]), (g["z_db1"][1], g["boss"]["disc"]), (g["z_db1"][1], 0.0)], cx=E, op="join", target="CAM_LOWER")
    dl = g["d_bore"]["lower"]
    sc.poly("CAM_LOWER", g["z_collar_lo"][0] - 0.5, [d_shape(dl[0], dl[1])], g["z_db1"][1] - g["z_collar_lo"][0] + 1.0, tag="DBORE")
    sc.circles("CAM_UPPER", g["z_db1"][1], [(0, 0)], cm["spacer_radius"], g["z_db2"][0] - g["z_db1"][1], op="new", tag="SPACER")
    sc.circles("CAM_UPPER", g["z_db2"][0], [(-E, 0)], g["boss"]["disc"], P["bearings"]["disc"]["width"], op="join", tag="LOBE")
    sc.circles("CAM_UPPER", g["z_collar_up"][0], [(-E, 0)], cm["upper_collar_radius"], cm["collar_height"], op="join", tag="COLLAR")   # 6804 #2 속 고리를 위에서 누름(R1)
    du = g["d_bore"]["upper"]
    sc.poly("CAM_UPPER", g["z_db1"][1] - 0.5, [d_shape(du[0], du[1])], g["z_collar_up"][1] - g["z_db1"][1] + 1.0, tag="DBORE")
    # ---- 와셔(조립 = 지금 쌓임 두께 · 나머지 둘은 조립 자리 밖) ----
    w = P["washer"]
    wb = P["shaft"]["dia"] / 2 + w["bore_clearance"]
    for k, t in enumerate(w["variants"]):
        nm = f"WASHER_T{t:.1f}".replace(".", "p")
        if abs(t - g["washer_t"]) < 1e-6:
            z0, ox = g["z_washer"][0], 0.0
        else:
            z0, ox = 0.0, -200.0 - 20.0 * k
        sc.circles(nm, z0, [(ox, 0)], w["od"] / 2, t, op="new", tag="OD")
        sc.circles(nm, z0 - 0.5, [(ox, 0)], wb, t + 1.0, tag="BORE")
    # ---- RETAINER · OUTPUT_FLANGE ----
    rt = P["retainer"]
    sc.revolve("RETAINER", [(ci["top"], ci["inner_radius_above_discs"]), (ci["top"], rt["outer_radius"]), (ci["top"] + rt["thickness"], rt["outer_radius"]),
                            (ci["top"] + rt["thickness"], ci["inner_radius_above_discs"])])
    sc.circles("RETAINER", ci["top"] - 0.5, ring(6, ci["retainer_screw_radius"], 0.0), g["m3_r"], rt["thickness"] + 1.0, tag="HOLE")
    of = P["output_flange"]
    sc.circles("OUTPUT_FLANGE", ci["top"], [(0, 0)], of["radius"], of["thickness"], op="new", tag="DISK")
    sc.circles("OUTPUT_FLANGE", ci["top"] - 0.5, ring(cr["inserts"], cr["insert_radius"], 0.0), g["m3_r"], of["thickness"] + 1.0, tag="HOLE")
    # ---- GUARD (벨트 덮개 — 바닥판 밑) ----
    zf = g["z_shaft"][0] - 2.0
    inner = hull(circle_pts(0, 0, gd["inner_radius"]) + [(x, y) for x in (0.0, gd["inner_x_end"]) for y in (-gd["inner_half_width"], gd["inner_half_width"])])
    outer = hull(circle_pts(0, 0, gd["inner_radius"] + gd["wall"]) +
                 [(x, y) for x in (0.0, gd["inner_x_end"] + gd["wall"]) for y in (-gd["inner_half_width"] - gd["wall"], gd["inner_half_width"] + gd["wall"])])
    sc.poly("GUARD", zf - gd["floor"], [outer], -zf + gd["floor"], op="new", tag="OUTER")
    sc.poly("GUARD", zf, [inner], -zf + 0.5, tag="INNER")
    tab_t = 3.0                                                           # 귀 = 바닥까지 기둥(처마 없음) · 나사는 밑에서 자리파기 굴로
    zb = zf - gd["floor"]
    sc.circles("GUARD", zb, tabs + [(gd["tab_motor_x"], 0.0)], gd["tab_boss_r"], -zb, op="join", tag="TAB")
    sc.rect("GUARD", zb, (gd["inner_x_end"], -gd["tab_boss_r"]), (gd["tab_motor_x"], gd["tab_boss_r"]), 0.5, -zb, tag="ARM")
    sc.circles("GUARD", zb - 0.5, tabs + [(gd["tab_motor_x"], 0.0)], g["m3_r"], -zb + 1.0, tag="TABHOLE")
    sc.circles("GUARD", zb - 0.5, tabs + [(gd["tab_motor_x"], 0.0)], P["base"]["screw_counterbore"][0] / 2, -zb - tab_t + 0.5, tag="TABCB")
    # ---- STAND (시험대 — 덮개 윗면에 앉는 판 + 책상 발 · 벤치 자세: 축 수평 · +x 위) ----
    st = P["stand"]
    z0s, z1s = g["face"], g["face"] + st["plate_thickness"]
    xd = -st["axis_height"]
    sc.circles("STAND", z0s, [(0, 0)], st["outer_radius"], st["plate_thickness"], op="new", tag="DISK")
    sc.rect("STAND", z0s, (xd, -st["width"] / 2), (0.0, st["width"] / 2), 4.0, st["plate_thickness"], tag="WEB")
    sc.circles("STAND", z1s + 0.5, [(0, 0)], st["centre_hole_radius"], st["plate_thickness"] + 1.0, direction="negative", tag="HOLE")
    sc.circles("STAND", z1s + 0.5, ring(6, ci["stand_insert_radius"], 30.0), g["m3_r"], st["plate_thickness"] + 1.0, direction="negative", tag="SCR")
    sc.circles("STAND", z1s + 0.5, ring(6, ci["stand_insert_radius"], 30.0), b["screw_counterbore"][0] / 2, st["counterbore"] + 0.5, direction="negative", tag="SCRCB")
    zfoot = z1s - st["foot_back"] - st["plate_thickness"]
    sc.rect("STAND", zfoot, (xd, -st["width"] / 2), (xd + st["foot_thickness"], st["width"] / 2), 1.0, z1s - zfoot, tag="FOOT")   # 발 — 판과 부피로 겹침
    for k, dirn in enumerate((None, "negative")):                 # 책상 구멍(x 방향) — 면 법선의 부호를 몰라도 뚫리게 양쪽으로
        sc.cmd("sketch.create", name=f"STAND_DESK{k}_SK", plane={"origin": [xd + st["foot_thickness"] / 2, 0.0, 0.0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]})
        for yy in (-st["width"] / 2 + 12, st["width"] / 2 - 12):
            for zz in (zfoot + 12.0, z1s - 30.0):
                sc.cmd("sketch.circle.center", center=[yy, zz], radius=st["desk_hole"] / 2)
        sc.cmd("sketch.finish")
        kw = {"direction": dirn} if dirn else {}
        sc.cmd("solid.extrude", distance=st["foot_thickness"] / 2 + 1.0, operation="cut", targets=["STAND"], name=f"STAND_DESK{k}_X", **kw)
    # ---- LEVER (시험 팔 — 출력 플랜지 위 · +y 로 뻗음) ----
    lv = P["lever"]
    zl0 = ci["top"] + of["thickness"]
    sc.circles("LEVER", zl0, [(0, 0)], lv["hub_radius"], lv["hub_thickness"], op="new", tag="HUB")
    za = zl0 + lv["hub_thickness"] - lv["arm_thickness"]
    sc.rect("LEVER", za, (-lv["width"] / 2, 0.0), (lv["width"] / 2, lv["length"]), lv["width"] / 2 - 0.5, lv["arm_thickness"], tag="ARM")
    zt = zl0 + lv["hub_thickness"]
    sc.circles("LEVER", zt + 0.5, ring(cr["inserts"], cr["insert_radius"], 0.0), g["m3_r"], lv["hub_thickness"] + 1.0, direction="negative", tag="HOLE")
    sc.circles("LEVER", zt + 0.5, ring(cr["inserts"], cr["insert_radius"], 0.0), b["screw_counterbore"][0] / 2, lv["counterbore"] + 0.5, direction="negative", tag="HOLECB")
    sc.circles("LEVER", zt + 0.5, [(0.0, r) for r in lv["hook_radii"]], lv["hook_hole"] / 2, lv["arm_thickness"] + 1.0, direction="negative", tag="HOOK")
    return sc.c


def preview_commands(P, g):
    """그림용 어림 몸체(구매품) — 따로 문서."""
    sc = SC()
    C, mf = g["C"], g["motor_face_z"]
    m = P["motor"]
    L = m["body_length"]["J2"] + m["board_length"]
    sc.cmd("solid.box", length=m["frame"], width=m["frame"], height=L, corner=[C - m["frame"] / 2, -m["frame"] / 2, mf], operation="new", body_name="REF_MOTOR_J2")
    sc.circles("REF_PINS", g["z_ring_pin"][0], ring(P["ring"]["pins"], P["ring"]["pin_circle_radius"]), P["ring"]["pin_dia"] / 2, P["ring"]["pin_length"], op="new", tag="P")
    pe = P["belt"]["pulley_envelope"]
    sc.circles("REF_PULLEY_BIG", pe["big_z"][0], [(0, 0)], pe["big_od"] / 2, pe["big_z"][1] - pe["big_z"][0], op="new", tag="B")
    sc.circles("REF_PULLEY_SMALL", pe["small_z"][0], [(C, 0)], pe["small_od"] / 2, pe["small_z"][1] - pe["small_z"][0], op="new", tag="S")
    return sc.c


def control_params(P, name):
    P = copy.deepcopy(P)
    if name == "pin_tight":
        P["fits"]["pin_press_hole_dia"] = 4.0
    elif name == "disc_big":
        P["fits"]["profile_clearance"] = -0.15
    elif name == "plate_wide":
        P["carrier"]["plate_radius"] = 36.5
    elif name == "seat_small":
        P["fits"]["bearing_seat_extra"] = -0.2
    elif name == "lobe_short":
        P["base"]["lobe_x_end"] = 110.0
    elif name == "guard_narrow":
        P["guard"]["inner_half_width"] = 22.0
    return P


def run(cli, script, native, step, work, env):
    p = subprocess.run([str(cli), "run", str(script), "--save", str(native)] + (["--out", str(step)] if step else []) +
                       ["--results", "--json-out", str(work / "result.json")], capture_output=True, text=True, encoding="utf-8", timeout=3600, env=env)
    (work / "run.log").write_bytes(((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--control", choices=sorted(CONTROLS), default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-snapshot", action="store_true")
    a = ap.parse_args()
    scr = a.scratch.resolve()
    assert not inside(scr, ROOT), "scratch must be outside the repo"
    if a.control:
        assert a.out and inside(a.out, scr), "--control needs --out under --scratch"
        out, ev = a.out, a.out
    else:
        out, ev = ROOT / "models" / NAME, EV / "build"
    work = scr / ("build-" + (a.control or "main"))
    for d in (out, out / "parts", ev, work):
        assert inside(d, ROOT / "models" / NAME, EV, scr), d
        d.mkdir(parents=True, exist_ok=True)
    P = load_params(a.params)
    if a.control:
        P = control_params(P, a.control)
    g = geometry(P)
    cmds = commands(P, g)
    bodies = ASSEMBLY + EXTRA
    stls = {n: out / "parts" / f"{n}.stl" for n in bodies}
    for n, p in stls.items():
        cmds.append({"command": "file.save_mesh", "params": {"path": str(p), "format": "stl", "bodies": [n], "quality": P.get("quality_by_body", {}).get(n, P["quality"])}})
    script = work / "build.json"
    script.write_bytes((json.dumps({"commands": cmds}, ensure_ascii=False) + "\n").encode("utf-8"))
    native, step = out / f"{NAME}.solidcraft", out / f"{NAME}.step"
    env = dict(os.environ)
    env["PATH"] = str(a.cli.parent) + os.pathsep + env.get("PATH", "")
    p = run(a.cli, script, native, None if a.control else step, work, env)
    if p.returncode or not all(s.is_file() for s in stls.values()):
        raise SystemExit(f"solidcraft run rc {p.returncode}: {(p.stderr or p.stdout)[-2500:]}")
    bak = native.with_name(native.name + ".bak")
    if bak.is_file():
        bak.unlink()
    if not a.no_snapshot and not a.control:
        pw = scr / "preview"
        pw.mkdir(parents=True, exist_ok=True)
        ps = pw / "preview.json"
        ps.write_bytes((json.dumps({"commands": cmds[:-len(bodies)] + preview_commands(P, g)}, ensure_ascii=False) + "\n").encode("utf-8"))
        pn = pw / "preview.solidcraft"
        q = run(a.cli, ps, pn, None, pw, env)
        for doc, views in ((native, ("iso",)), (pn if q.returncode == 0 else None, ("iso", "front", "top"))):
            if doc is None:
                print(f"preview rc {q.returncode}: {(q.stderr or q.stdout)[-600:]}")
                continue
            for view in views:
                png = out / (f"{view}.png" if doc == native else f"with-refs-{view}.png")
                r = subprocess.run([str(a.cli), "snapshot", "--in", str(doc), "--out", str(png), "--view", view, "--width", "1600", "--height", "1200"],
                                   capture_output=True, text=True, encoding="utf-8", timeout=900, env=env)
                if r.returncode:
                    print(f"snapshot {png.name} rc {r.returncode}: {(r.stderr or r.stdout)[-400:]}")
    v = subprocess.run([str(a.cli), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    _pts, n_prof, err_prof = disc_outline(P, g)
    rec = {"what": "MP16 구동 모듈 만들기 기록 — 이 sha 와 지금 파일이 같아야 검사가 지금 형상을 본 것이다", "control": a.control,
           "control_means": CONTROLS.get(a.control), "geometry": g, "profile_points": n_prof, "profile_chord_error": err_prof,
           "fits_used": {k: v for k, v in P["fits"].items() if k != "calibration"}, "calibration_sha256": P["fits"].get("calibration", {}).get("values_sha256"),
           "tool": {"cli_version": (v.stdout or v.stderr or "").strip(), "cli_sha256": sha(a.cli)},
           "inputs_sha256": {"parameters.json": sha(a.params), "build_drive.py": sha(__file__), "cycloid.py(MP6)": sha(ROOT / "src/cad/cycloid-27-v1/cycloid.py"),
                             "print-fits.json": sha(ROOT / "src/cad/calibration/print-fits.json")},
           "outputs_sha256": {**{f"parts/{n}.stl": sha(s) for n, s in stls.items()}, f"{NAME}.solidcraft": sha(native),
                              **({f"{NAME}.step": sha(step)} if not a.control else {})},
           "command_count": len(cmds)}
    (ev / "build-record.json").write_bytes((json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"control": a.control, "commands": len(cmds), "C": round(g["C"], 3), "washer_t": g["washer_t"], "disc_tip_r": round(g["disc_tip_r"], 3)}))


if __name__ == "__main__":
    main()
