# -*- coding: utf-8 -*-
"""MP17 팔 전체 v1 — 새 인쇄 부품(SolidCraft 명령줄).

부품마다 지역 좌표(layout.NEW_PARTS 의 틀)로 만든다 — 한 문서에 겹쳐 있어도 부품 STL 은 따로 낸다(조립 자리 = layout.placement).
J1 · J4 · J6 모터 몸통 = MP10 생성기(`../j5-wrist-v1/j5geom.py`)를 읽기만 해서 불러 쓴 캔(목 대신: J1 = 없음 · J4 · J6 = 링크 받침 + 인서트).
끼움 · 구멍 보정은 원장(print-fits.json)에서 읽는다. 쓰기 = models/manipulator-v1 · .dev/mp17-evidence · --scratch 만.
사용: python build_arm.py --cli <solidcraft-cli.exe> --scratch <작업 폴더> [--control <이름> --out <작업 폴더 아래>]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

import layout as L

HERE = Path(__file__).resolve().parent
ROOT = L.ROOT
sys.path.insert(0, str(ROOT / "src" / "cad" / "j5-wrist-v1"))
import j5geom  # noqa: E402  (MP10 — 읽기만)

CONTROLS = {     # 이름: (뜻, 매개변수 바꿈 [(키 경로, 값)], 다시 만드나)
    "shoulder_hole_small": ("shoulder centre hole r 45 (the J2 hub r 46 cannot pass)", [(("j2", "shoulder", "hole_r"), 45.0)], True),
    "turret_high": ("turret plate 3 mm thicker upward (meets the J2 cap bottom)", [(("j1", "turret", "plate_z"), [43.5, 52.5])], True),
    "j3_layer_shift": ("J3 module placed 2 mm toward the wrist plane (parts unchanged)", [(("j3", "module_axis_y0"), 126.3)], False),
    "pad_insert_shallow": ("can pad insert holes 7.5 -> 5.0 deep (the M3 x 12 tip runs past the hole floor)", [(("pad", "insert_depth"), 5.0)], True),
    "turret_shoulder_touch": ("turret shoulder back on the top 6818 outer ring (two axial datums - review R1-1)", [(("j1", "turret", "shoulder_gap"), 0.0)], True),
    "floor_hole_big": ("floor float holes 5.2 -> 7.4 (the washer and head lose their seat - review R1-3)", [(("j1", "floor", "can_hole_dia"), 7.4)], True),
    "shoulder_cbore_none": ("shoulder J2-cap screw counterbore 3.5 -> 0 (button heads stand into the upper-arm layer)", [(("j2", "shoulder", "cap_screw_cbore"), [6.5, 0.0])], True),
    "sleeve_tight": ("J1 sleeve inner radius 41 -> 39.5 (J1 MP6 r 39)", [(("j1", "base", "sleeve_inner_r"), 39.5)], True),
    "tool_boss_big": ("tool-flange boss r 10 -> 10.6 (gripper recess r 10)", [(("tool_flange", "boss_r"), 10.6)], True),
    "can_turned": ("J4 can placed turned 180 deg about its axis (pad away from the forearm)", [(("j4", "can_turn_deg"), 180.0)], False),
}


def control_params(raw, name):
    """parameters.json(사전) 사본에 대조 하나의 바꿈을 넣는다."""
    raw = copy.deepcopy(raw)
    for path, val in CONTROLS[name][1]:
        d = raw
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = val
    return raw


def sha(p):
    return L.sha(p)


def inside(p, *roots):
    p = Path(p).resolve()
    return any(p == r.resolve() or r.resolve() in p.parents for r in roots)


def ring(n, r, phase_deg=0.0):
    return [(r * math.cos(math.radians(phase_deg + 360.0 * k / n)), r * math.sin(math.radians(phase_deg + 360.0 * k / n))) for k in range(n)]


def poly_pts(g):
    """shapely 다각형 바깥 → 점 목록(반시계 · 끝점 반복 없음 · 짧은 변 정리)."""
    g = g.buffer(0)
    if g.geom_type != "Polygon":
        raise SystemExit(f"outline not one polygon: {g.geom_type}")
    g = Polygon(g.exterior).simplify(0.01)
    pts = list(g.exterior.coords)[:-1]
    if Polygon(pts).exterior.is_ccw is False:
        pts = pts[::-1]
    return [(round(x, 4), round(y, 4)) for x, y in pts]


def circle(cx, cy, r, n=120):
    return Point(cx, cy).buffer(r, resolution=max(8, n // 4))


def chamfered_rect(x0, x1, y0, y1, c):
    return Polygon([(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)])


# ---------------- 이끌어 낸 치수 · 나사 ----------------
def geometry(P):
    f = P["_fits"]
    D = P["_drive"]
    g = {"m3": f["m3_clearance_dia"], "m3c": f["m3_close_hole_dia"], "ins": f["insert_hole_dia"], "ins_od": float(P["insert_od"]),
         "seat_extra": f["bearing_seat_extra"], "bore_extra": f["bearing_bore_extra"]}
    j1 = P["j1"]
    b = j1["bearing"]
    g["sleeve_r"] = (b["id"] + f["bearing_bore_extra"]) / 2
    g["cup_bore_r"] = (b["od"] + f["bearing_seat_extra"]) / 2
    g["sleeve_inner_r"] = j1["base"]["sleeve_inner_r"]
    g["turret_plate"] = list(j1["turret"]["plate_z"])
    g["turret_shoulder_z"] = b["z"][1][1] + j1["turret"]["shoulder_gap"]           # 위 6818 바깥 고리와 띄움(축 기준 = MP6 면 하나 · 검토 R1-1)
    g["drive_cap_face"] = D["cap"]["top"] - D["cap"]["seat_proud"]                 # MP16 덮개 윗면 = 캐리어 허브 윗면(모듈 z 69.3)
    g["drive_flange_top"] = D["cap"]["top"] + D["output_flange"]["thickness"]      # 플랜지 · 누름 고리는 6812 고리 면(69.5) 위에 앉음(STL 69.5 ~ 74.5)
    g["drive_retainer_head_top"] = D["cap"]["top"] + D["retainer"]["thickness"] + D["screws"]["button_head"][1]
    g["y3"] = P["j3"]["module_axis_y0"]
    g["shoulder_hole_r"] = P["j2"]["shoulder"]["hole_r"]
    g["pad_cbore_depth"] = P["j3"]["forearm"]["pad_cbore"][1]
    g["tool_boss_r"] = P["tool_flange"]["boss_r"]
    return g


def screws(P, g):
    """나사 묶음 — 이름 · 길이 · 머리 자리(자리파기 바닥) · 방향 · 위치(세계 q = 0) · 조이는 부품 · 들어가는 부품(인서트). 검사기가 STL 에 광선을 쏴 다시 잰다."""
    Fr = L.frames(P)
    S = []

    def add(name, length, frame, pts_local, axis_local, clamped, target, note="", probe_r=2.6, washer=0.0):
        M = Fr[frame]
        R = M[:3, :3]
        pw = [list(map(float, (M @ [x, y, z, 1.0])[:3])) for x, y, z in pts_local]
        S.append({"name": name, "length": float(length), "frame": frame, "heads_world": pw, "axis_world": list(map(float, R @ axis_local)),
                  "clamped": clamped, "target": target, "note": note, "probe_r": probe_r, "washer_t": float(washer)})
    j1 = P["j1"]
    fl = j1["floor"]
    sp = P["_wrist_spec"]
    zf = sp.z_rear - fl["thickness"]                                            # 바닥 밑면(J1 z)
    cv = [(sp.cover["r"] * math.cos(math.radians(a)), sp.cover["r"] * math.sin(math.radians(a)), zf + fl["can_cbore"][1]) for a in sp.cover["angles"]]
    add("floor_to_j1_can", 10, "J1", cv, (0, 0, 1), ["FLOOR"], "J1_CAN_A|J1_CAN_B",
        "J1 can rear inserts (MP10 cover pattern) · Ø5.2 float holes + M3 flat washer 7 x 0.5 (review R1-3)", probe_r=2.7, washer=fl["washer"][1])
    add("floor_to_base", 8, "J1", [(fl["base_screw_r"] * math.cos(math.radians(a)), fl["base_screw_r"] * math.sin(math.radians(a)), zf + fl["base_cbore"][1])
                                   for a in fl["base_screw_angles"]], (0, 0, 1), ["FLOOR"], "BASE")
    t = j1["turret"]
    add("turret_to_j1_mp6", 12, "J1", [(x, y, g["turret_plate"][0] + t["mp6_screw_under_head"]) for x, y in ring(4, 14.0, 45.0)], (0, 0, -1),
        ["TURRET", "J1.MP6.OUTPUT_FLANGE"], "J1.MP6.CARRIER", "MP6 flange screw M3 x 8 made longer by the turret under-head 4 (same as the MP10 hub)")
    sh = P["j2"]["shoulder"]
    add("shoulder_to_turret", 12, "W", [(sx * x, y, sh["foot_z"][1] - sh["foot_cbore"][1]) for sx in (1, -1) for x, y in t["foot_insert_xy"]], (0, 0, -1),
        ["SHOULDER"], "TURRET")
    m2 = [(-53.5 * math.cos(math.radians(a)), sh["plate_y"][1] - sh["cap_screw_cbore"][1], 174.0 + 53.5 * math.sin(math.radians(a)))
          for a in (30 + 60 * k for k in range(6))]
    add("shoulder_to_j2_cap", 10, "W", m2, (0, -1, 0), ["SHOULDER"], "J2.CAP", "MP16 stand inserts r 53.5 phase 30")
    ua = P["j3"]["upper_arm"]
    j2s = [(-22.0 * math.cos(math.radians(a)), ua["plate_y"][1] - ua["j2_cbore"][1], 174.0 + 22.0 * math.sin(math.radians(a))) for a in (60 * k for k in range(6))]
    add("upper_arm_to_j2_carrier", 16, "W", j2s, (0, -1, 0), ["UPPER_ARM", "J2_HUB", "J2.OUTPUT_FLANGE"], "J2.CARRIER", "MP16 flange screw M3 x 10 made longer")
    jo = L.joint_origins_q0(P)
    o3, x5 = float(jo["J3"][0]), float(jo["J5"][0])
    j3c = [(o3 - 53.5 * math.sin(math.radians(a)), ua["plate_y"][0] + ua["j3_cbore"][1], 174.0 + 53.5 * math.cos(math.radians(a))) for a in (30 + 60 * k for k in range(6))]
    add("upper_arm_to_j3_cap", 10, "W", j3c, (0, 1, 0), ["UPPER_ARM"], "J3.CAP")
    fa = P["j3"]["forearm"]
    j3f = [(o3 - 22.0 * math.sin(math.radians(a)), fa["plate_y"][0] + fa["j3_cbore"][1], 174.0 + 22.0 * math.cos(math.radians(a))) for a in (60 * k for k in range(6))]
    add("forearm_to_j3_carrier", 16, "W", j3f, (0, 1, 0), ["FOREARM", "J3.OUTPUT_FLANGE"], "J3.CARRIER")
    pd = P["pad"]
    x4 = L.motor_face_x(P, "J4")
    pf = [(x4 + z, fa["plate_y"][1] - g["pad_cbore_depth"], 174.0 - y) for y, z in pd["inserts_yz"]]
    add("forearm_to_j4_pad", 12, "W", pf, (0, -1, 0), ["FOREARM"], "J4_CAN_A")
    l5 = P["link5"]
    hb = [(x5 + 20.5 * math.cos(math.radians(a)), l5["plate_y"][1] - l5["hub_cbore"][1], 174.0 - 20.5 * math.sin(math.radians(a))) for a in (90 * k for k in range(4))]
    add("link5_to_j5_hub", 20, "W", hb, (0, -1, 0), ["LINK5"], "J5.J5_OUTPUT_HUB")
    x6 = L.motor_face_x(P, "J6")
    p6 = [(x6 + z, l5["plate_y"][1] - l5["pad_cbore"][1], 174.0 - y) for y, z in pd["inserts_yz"]]
    add("link5_to_j6_pad", 12, "W", p6, (0, -1, 0), ["LINK5"], "J6_CAN_A")
    sp5 = P["_wrist_spec"]                                                      # J5 목 → J4 MP6 캐리어(BOM W02 · MP10 목판 · 이 단위에서 J4 = MP6 확정)
    nk = sp5.neck
    nh = [(nk["x_face"] + nk["under"], nk["scr_r"] * math.cos(math.radians(a)), sp5.j4_axis_z + nk["scr_r"] * math.sin(math.radians(a)))
          for a in (nk["scr_phase"] + 360.0 * k / nk["scr_n"] for k in range(nk["scr_n"]))]
    add("j5_neck_to_j4_mp6", 16, "J5M", nh, (-1, 0, 0), ["J5.J5_STATOR_A", "J4.MP6.OUTPUT_FLANGE"], "J4.MP6.CARRIER", "BOM W02 M3 x 16 (MP10 neck)")
    tf = P["tool_flange"]
    add("tool_flange_to_j6_mp6", 12, "C6", [(x, y, 43.5 + tf["mp6_screw_under_head"]) for x, y in ring(4, 14.0, 45.0)], (0, 0, -1),
        ["TOOL_FLANGE", "J6.MP6.OUTPUT_FLANGE"], "J6.MP6.CARRIER")
    gs = P["gripper_screw"]
    add("gripper_to_tool_flange", gs["length"], "G", [(tf["insert_r"] * math.cos(math.radians(a)), tf["insert_r"] * math.sin(math.radians(a)), gs["seat_z"])
                                                       for a in tf["insert_angles"]], (0, 0, -1), ["KG1.BASE"], "TOOL_FLANGE",
        "BOM G11 - KG1 base disc 6 thick at the screws, counterbore floor z 3 (measured from KG1 BASE.stl) -> M3 socket x 10")
    return S


def limits(P, g, spec):
    """만들기 전 한계(넘으면 만들지 않는다 · 검사기가 STL 로 따로 다시 본다)."""
    mw, ins = P["min_wall"], g["ins_od"]                                       # 벽은 인서트 바깥지름 4.2 로 셈(검토 R1-11)
    pd = P["pad"]
    mc = spec.mconn
    roof = lambda y: mc["z_ends"] + min(y - mc["y"][0], mc["y"][1] - y)      # noqa: E731
    con_roof_outer = spec.con_z[1] + (spec.con_x[1] - spec.con_x[0])

    def gap_rect(y, z, y0, y1, z0, z1):
        return math.hypot(max(y0 - y, 0.0, y - y1), max(z0 - z, 0.0, z - z1))
    pad_ok = []
    for y, z in pd["inserts_yz"]:
        r = ins / 2
        pad_ok.append(gap_rect(y, z, mc["deep"]["y"][0], mc["deep"]["y"][1], mc["deep"]["z0"], roof(min(max(y, mc["y"][0]), mc["y"][1]))) - r >= mw)
        pad_ok.append(gap_rect(y, z, mc["side"]["y"][0], mc["side"]["y"][1], mc["side"]["z0"], mc["z_ends"]) - r >= mw)
        pad_ok.append(gap_rect(y, z, -spec.con_y, spec.con_y, spec.con_z[0], con_roof_outer) - r >= mw)
        pad_ok.append(z + r + mw <= pd["z"][1] and z - r - mw >= pd["z"][0] and y - r - mw >= pd["y"][0] and y + r + mw <= pd["y"][1])
        pad_ok.append(abs(-pd["x_face_j4"] - pd["insert_depth"]) >= spec.clamp_x + spec.rib["gap"] + mw)      # 인서트 바닥이 조임 칸 벽 밖
    D = P["_drive"]
    j2, ua, fa = P["j2"], P["j3"]["upper_arm"], P["j3"]["forearm"]
    lim = {
        "pad_inserts_clear_of_pockets": all(pad_ok),
        "j2_hub_inside_shoulder_hole": j2["hub"]["r_outer"] + 2.0 <= g["shoulder_hole_r"],
        "j2_hub_outer_clears_retainer_heads": j2["hub"]["outer_face_y"] - (g["drive_retainer_head_top"] + j2["module_axis_y0"]) >= 0.9,
        "j2_hub_contact_inside_flange": j2["hub"]["r_contact"] <= D["output_flange"]["radius"] + 1e-9,
        "shoulder_on_cap_top": abs(j2["shoulder"]["plate_y"][0] - (g["drive_cap_face"] + j2["module_axis_y0"])) < 1e-9,
        "hub_on_flange_top": abs(j2["hub"]["y"][0] - (g["drive_flange_top"] + j2["module_axis_y0"])) < 1e-9,
        "upper_arm_on_hub": abs(ua["plate_y"][0] - j2["hub"]["y"][1]) < 1e-9 and ua["plate_y"][0] - j2["shoulder"]["plate_y"][1] >= 1.0,
        "upper_arm_on_j3_cap_top": abs(ua["plate_y"][1] - (g["y3"] - g["drive_cap_face"])) < 1e-9,
        "forearm_boss_on_j3_flange": abs(fa["boss_y"][1] - (g["y3"] - g["drive_flange_top"])) < 1e-9,
        "forearm_below_upper_arm": ua["plate_y"][0] - fa["plate_y"][1] >= 1.0,
        "forearm_boss_inside_upper_arm_hole": fa["boss_r_outer"] + 2.0 <= ua["hole_r"],
        "forearm_boss_outer_clears_retainer_heads": (g["y3"] - g["drive_retainer_head_top"]) - fa["boss_outer_face_y"] >= 0.9,
        "j3_motor_clears_forearm": (g["y3"] - (D["base"]["lobe_thickness"] + D["motor"]["body_length"]["J3"] + D["motor"]["board_length"])) - fa["plate_y"][1] >= 2.0,
        "j3_ring_clears_j3_motor": (L.belt_centre(D) - D["motor"]["frame"] / 2) - ua["j3_ring_r"] >= 2.0,
        "shoulder_ring_clears_j2_motor": (L.belt_centre(D) - D["motor"]["frame"] / 2) - j2["shoulder"]["ring_r"] >= 2.0,
        "j4_pad_on_forearm": abs(-pd["x_face_j4"] - fa["plate_y"][0]) < 1e-9,
        "j6_pad_on_link5": abs(-pd["x_face_j6"] - P["link5"]["plate_y"][0]) < 1e-9,
        "link5_boss_on_hub": abs(P["link5"]["boss_y"][0] - (spec.hub_z[1] - 21.0)) < 1e-9,
        "turret_below_j2_cap": (174.0 - D["base"]["outer_radius"]) - (P["j1"]["motor_face_z"] + g["turret_plate"][1]) >= 1.5,
        "sleeve_clears_mp6": g["sleeve_inner_r"] - spec.mp6["outer_r"] >= 1.5,
        "sleeve_wall": g["sleeve_r"] - g["sleeve_inner_r"] >= mw + 1.5,
        "base_wall_clears_lugs": P["j1"]["base"]["wall_r"][0] - (spec.outer_r + spec.lug["out"]) >= 2.0,
        "base_cone_clears_lug_corner": (g["sleeve_inner_r"] + (P["j1"]["base"]["cone_top"] - spec.lug["z"][1])) - math.hypot(spec.split + spec.lug["b"], spec.outer_r + spec.lug["out"]) >= 1.2,
        "turret_shoulder_clears_top_bearing": g["turret_shoulder_z"] - P["j1"]["bearing"]["z"][1][1] >= 0.2,
        "base_wall_insert": min(P["j1"]["floor"]["base_screw_r"] - P["j1"]["base"]["wall_r"][0], P["j1"]["base"]["wall_r"][1] - P["j1"]["floor"]["base_screw_r"]) - ins / 2 >= mw,
        "turret_contact_clears_retainer_heads": P["j1"]["turret"]["relief_d"] >= (spec.mp6["retainer_top"] + spec.ret_head["height"] - spec.mp6["output_face"]) + 0.3,
        "tool_flange_inside_retainer_heads": P["tool_flange"]["r"] + 1.0 <= spec.mp6["retainer_screw_r"] - spec.ret_head["dia"] / 2 + 1e-9,
        "tool_boss_clear_of_cbores": 14.0 - P["tool_flange"]["mp6_cbore"] / 2 - g["tool_boss_r"] >= 0.5,
    }
    bad = [k for k, v in lim.items() if not v]
    if bad:
        raise SystemExit(f"MP17 geometry out of limits: {bad}")
    return lim


# ---------------- SolidCraft ----------------
class ArmSC(j5geom.SC):
    """MP10 SC(읽기만 불러 씀) + MP17 부품. mode: None = 목 없음(J1) · 'pad' = 링크 받침."""

    def __init__(self, spec, P, g):
        super().__init__(spec)
        self.P, self.g = P, g
        self.mode, self.pad_face = None, None

    def neck(self, name):                     # MP10 목 자리 → 링크 받침(J4 · J6) / 없음(J1)
        if self.mode != "pad":
            return
        pd = self.P["pad"]
        x0, xi = self.pad_face, pd["x_inner"]
        (y0, y1), (z0, z1) = pd["y"], (pd["z_j6"] if self.pad_face == pd["x_face_j6"] else pd["z"])
        prof = [(x0, z1), (x0, z0), (xi, z0 - (xi - x0)), (xi, z1)]            # (x, z) · 밑면 45°(뒤 끝을 판에 세워 출력)
        self.prism(f"{name}_PAD", "y", y0, y1, prof)
        self.combine(name, [f"{name}_PAD"], "join")

    def neck_holes(self, name):
        if self.mode != "pad":
            return
        pd = self.P["pad"]
        for i, (y, z) in enumerate(pd["inserts_yz"]):
            self.cyl(f"{name}_PI{i}", "x", self.pad_face - 0.5, self.pad_face + pd["insert_depth"], y, z, self.g["ins"], op="cut", target=name)

    # ---- 공통 ----
    def plate_y(self, name, y0, y1, geom, op="new", target=None):
        self.prism(name, "y", y0, y1, poly_pts(geom), op, target)

    def revolve_profile(self, name, prof):
        self.revolve_z(name, prof)

    def revolve_y(self, name, cx, cz, prof):
        """세계 y 축과 나란한 축(점 (cx, ·, cz)) 둘레 회전 — prof = (y, 반지름)."""
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": [float(cx), 0.0, float(cz)], "x_dir": [0, 1, 0], "y_dir": [1, 0, 0]})
        self.cmd("sketch.line", points=[[float(u), float(v)] for u, v in prof], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.revolve", axis="x", operation="new", body_name=name, name=name + "_REVOLVE")

    # ---- J1 ----
    def floor(self, name="FLOOR"):
        P, g, s = self.P, self.g, self.s
        fl = P["j1"]["floor"]
        z1 = s.z_rear
        z0 = z1 - fl["thickness"]
        self.cyl(name, "z", z0, z1, 0.0, 0.0, 2 * fl["radius"])
        for i, a in enumerate(fl["desk_hole_angles"]):
            x, y = fl["desk_hole_r"] * math.cos(math.radians(a)), fl["desk_hole_r"] * math.sin(math.radians(a))
            self.cyl(f"{name}_DH{i}", "z", z0 - 0.5, z1 + 0.5, x, y, fl["desk_hole_dia"], op="cut", target=name)
        for i, a in enumerate(s.cover["angles"]):
            x, y = s.cover["r"] * math.cos(math.radians(a)), s.cover["r"] * math.sin(math.radians(a))
            self.cyl(f"{name}_CH{i}", "z", z0 - 0.5, z1 + 0.5, x, y, fl["can_hole_dia"], op="cut", target=name)
            self.cyl(f"{name}_CC{i}", "z", z0 - 0.5, z0 + fl["can_cbore"][1], x, y, fl["can_cbore"][0], op="cut", target=name)
        for i, a in enumerate(fl["base_screw_angles"]):
            x, y = fl["base_screw_r"] * math.cos(math.radians(a)), fl["base_screw_r"] * math.sin(math.radians(a))
            self.cyl(f"{name}_BH{i}", "z", z0 - 0.5, z1 + 0.5, x, y, g["m3"], op="cut", target=name)
            self.cyl(f"{name}_BC{i}", "z", z0 - 0.5, z0 + fl["base_cbore"][1], x, y, fl["base_cbore"][0], op="cut", target=name)
        w = fl["window"] / 2
        self.box(f"{name}_WIN", [-w, w], [-w, w], [z0 - 0.5, z1 + 0.5], op="cut", target=name)

    def base(self, name="BASE"):
        P, g, s = self.P, self.g, self.s
        b = P["j1"]["base"]
        zr = s.z_rear
        (wi, wo), (ci, co) = b["wall_r"], b["collar_r"]
        sr, si, st = g["sleeve_r"], g["sleeve_inner_r"], b["sleeve_top"]
        z_cone_top = b["cone_top"]                                               # 귀 모서리와 1.3(검토 R1-7)
        z_cone_bot = z_cone_top - (wi - si)
        c = b["chamfer"]                                                          # 슬리브 위 바깥 모서리 모따기(6818 넣는 길 · 검토 R1-4)
        prof = [(zr, wi), (zr, wo), (b["wall_top"], wo), (b["wall_top"], co), (b["collar_z"][1], co), (b["collar_z"][1], sr), (st - c, sr), (st, sr - c), (st, si),
                (z_cone_top, si), (z_cone_bot, wi)]
        self.revolve_z(name, prof)
        br = P["style"]["base_ring"]                                           # 민트 끊긴 고리 홈(v3 바닥 고리) — 윗면 45°(세워 출력할 때 처마 없음)
        (gz0, gz1), gr = br["groove_z"], br["groove_r"]
        za = gz1 - (wo - gr)                                                     # 45° 윗면이 바깥 면(r wo)과 gz1 에서 만나게 — 경사는 벽 밖까지(면 위 꼭짓점 없음)
        self.revolve_z(f"{name}_GROOVE", [(gz0, gr), (gz0, wo + 1.0), (za + (wo + 1.0 - gr), wo + 1.0), (za, gr)])
        self.combine(name, [f"{name}_GROOVE"], "cut")
        for i, a in enumerate(b["window_angles"]):                             # 케이블 창 — 위 45° 박공(다리 대신)
            hw = b["window_half_width"]
            t = math.radians(a)
            ca, sa = math.cos(t), math.sin(t)
            r0, r1 = wi - 3.0, wo + 3.0
            prof = [(-hw, zr - 0.5), (hw, zr - 0.5), (hw, b["window_top"]), (0.0, b["window_top"] + hw), (-hw, b["window_top"])]     # (가로, z)
            # 창 방향(반지름) 축의 판 — 가로 = 반지름에 수직
            self.cmd("sketch.create", name=f"{name}_WIN{i}_SK", plane={"origin": [r0 * ca, r0 * sa, 0.0], "x_dir": [-sa, ca, 0.0], "y_dir": [0.0, 0.0, 1.0]})
            self.cmd("sketch.line", points=[[round(u, 5), round(v, 5)] for u, v in prof], closed=True)
            self.cmd("sketch.finish")
            self.cmd("solid.extrude", distance=float(r1 - r0), direction="positive", operation="cut", targets=[name], name=f"{name}_WIN{i}_X")
        fl = P["j1"]["floor"]
        for i, a in enumerate(fl["base_screw_angles"]):
            x, y = fl["base_screw_r"] * math.cos(math.radians(a)), fl["base_screw_r"] * math.sin(math.radians(a))
            self.cyl(f"{name}_I{i}", "z", zr - 0.5, zr + 7.5, x, y, g["ins"], op="cut", target=name)

    def spacer(self, name="J1_SPACER"):
        sp = self.P["j1"]["spacer"]
        (r0, r1), (z0, z1) = sp["r"], sp["z"]
        self.revolve_z(name, [(z0, r0), (z0, r1), (z1, r1), (z1, r0)])

    def turret(self, name="TURRET"):
        P, g, s = self.P, self.g, self.s
        t = P["j1"]["turret"]
        b = P["j1"]["bearing"]
        z0 = b["z"][0][0]
        zp0, zp1 = g["turret_plate"]
        R, cb, sh = t["cup_outer_r"], g["cup_bore_r"], t["shoulder_inner_r"]
        zs = g["turret_shoulder_z"]
        bc = t["bore_chamfer"]                                                  # 구멍 입구 모따기(6818 넣는 길 · 검토 R1-4)
        prof = [(z0, cb + bc), (z0, R), (zp1, R), (zp1, 0.0), (zp0, 0.0), (zp0, t["relief_r"]), (zp0 + t["relief_d"], t["relief_r"]), (zp0 + t["relief_d"], sh),
                (zs, sh), (zs, cb), (z0 + bc, cb)]
        self.revolve_z(name, prof)
        (x0, x1), (y0, y1) = t["ext_x"], t["ext_y"]
        c = t["ext_chamfer"]
        for k, sg in enumerate((1.0, -1.0)):
            pts = [(sg * x, y) for x, y in poly_pts(chamfered_rect(x0, x1, y0, y1, c))]
            if sg < 0:
                pts = pts[::-1]
            self.prism(f"{name}_EXT{k}", "z", t["ext_z0"], zp1, pts)
        self.combine(name, [f"{name}_EXT0", f"{name}_EXT1"], "join")
        for i, (x, y) in enumerate(ring(4, 14.0, 45.0)):
            self.cyl(f"{name}_H{i}", "z", zp0 - 0.5, zp1 + 0.5, x, y, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_C{i}", "z", zp0 + t["mp6_screw_under_head"], zp1 + 0.5, x, y, t["mp6_cbore"], op="cut", target=name)
        k = 0
        for sg in (1.0, -1.0):
            for x, y in t["foot_insert_xy"]:
                self.cyl(f"{name}_FI{k}", "z", zp1 - 7.5, zp1 + 0.5, sg * x, y, g["ins"], op="cut", target=name)
                k += 1

    # ---- 어깨 · 허브 · 위팔 · 아래팔 · 링크 5 ----
    def shoulder(self, name="SHOULDER"):
        P, g = self.P, self.g
        sh = P["j2"]["shoulder"]
        (y0, y1) = sh["plate_y"]
        bx, bz = sh["body_x"], sh["body_z"]
        outline = unary_union([circle(0.0, 174.0, sh["ring_r"]), box(bx[0], bz[0], bx[1], bz[1])]).convex_hull
        outline = outline.difference(box(-400.0, sh["motor_keepout_z"], sh["motor_keepout_x"], 400.0))
        outline = outline.intersection(chamfered_rect(bx[0], bx[1], bz[0], 400.0, P["style"]["shoulder_chamfer"]))      # 아래 모서리 45°
        self.plate_y(name, y0, y1, outline)
        (fx0, fx1), (fy0, fy1), (fz0, fz1) = sh["foot_x"], sh["foot_y"], sh["foot_z"]
        (wx0, wx1), (wz0, wz1) = sh["wall_x"], sh["wall_z"]
        tools = []
        for k, sg in enumerate((1.0, -1.0)):
            xa, xb = sorted((sg * fx0, sg * fx1))
            self.prism(f"{name}_FOOT{k}", "z", fz0, fz1, poly_pts(chamfered_rect(xa, xb, fy0, fy1, 4.0)))
            xa, xb = sorted((sg * wx0, sg * wx1))
            self.box(f"{name}_WALL{k}", [xa, xb], [fy0 + 1.0, y0 + 0.5], [wz0 - 1.0, wz1])      # 발 · 판과 부피로 겹침(같은 면 · 모서리 맞닿음 없음)
            tools += [f"{name}_FOOT{k}", f"{name}_WALL{k}"]
        self.combine(name, tools, "join")
        self.cyl(f"{name}_HOLE", "y", y0 - 1.0, y1 + 1.0, 0.0, 174.0, 2 * g["shoulder_hole_r"], op="cut", target=name)
        cbd, cbr = sh["cap_screw_cbore"][1], sh["cap_screw_cbore"][0]
        for i, a in enumerate(30 + 60 * k for k in range(6)):
            x, z = -53.5 * math.cos(math.radians(a)), 174.0 + 53.5 * math.sin(math.radians(a))
            self.cyl(f"{name}_CS{i}", "y", y0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_CB{i}", "y", y1 - cbd, y1 + 1.0, x, z, cbr, op="cut", target=name)
        k = 0
        for sg in (1.0, -1.0):
            for x, y in P["j1"]["turret"]["foot_insert_xy"]:
                self.cyl(f"{name}_FH{k}", "z", fz0 - 1.0, fz1 + 1.0, sg * x, y, g["m3"], op="cut", target=name)
                self.cyl(f"{name}_FC{k}", "z", fz1 - sh["foot_cbore"][1], fz1 + 1.0, sg * x, y, sh["foot_cbore"][0], op="cut", target=name)
                k += 1
        self.tie_pairs(name, "y", y0 - 1.0, y1 + 1.0, [(sg * 80.0, 135.0) for sg in (1.0, -1.0)], along="v")

    def j2_hub(self, name="J2_HUB"):
        P, g = self.P, self.g
        h = P["j2"]["hub"]
        self.cyl(name, "y", h["y"][0], h["y"][1], 0.0, 174.0, 2 * h["r_contact"])
        self.cyl(f"{name}_OUT", "y", h["outer_face_y"], h["y"][1], 0.0, 174.0, 2 * h["r_outer"])
        self.combine(name, [f"{name}_OUT"], "join")
        for i, a in enumerate(60 * k for k in range(6)):
            self.cyl(f"{name}_H{i}", "y", h["y"][0] - 1.0, h["y"][1] + 1.0, -22.0 * math.cos(math.radians(a)), 174.0 + 22.0 * math.sin(math.radians(a)), g["m3c"],
                     op="cut", target=name)

    def upper_arm(self, name="UPPER_ARM"):
        P, g = self.P, self.g
        ua = P["j3"]["upper_arm"]
        y0, y1 = ua["plate_y"]
        hz = ua["beam_half_z"]
        outline = unary_union([circle(0.0, 174.0, ua["j2_disc_r"]), box(0.0, 174.0 - hz, 165.0, 174.0 + hz), circle(165.0, 174.0, ua["j3_ring_r"])])
        self.plate_y(name, y0, y1, outline)
        (bx0, bx1), (by0, by1), bh = ua["box_x"], ua["box_y"], ua["box_half_z"]
        self.prism(f"{name}_BOX", "y", by0 + 0.5, by1, poly_pts(chamfered_rect(bx0, bx1, 174.0 - bh, 174.0 + bh, ua["chamfer"])))
        self.combine(name, [f"{name}_BOX"], "join")
        self.cyl(f"{name}_HOLE", "y", y0 - 1.0, y1 + 1.0, 165.0, 174.0, 2 * ua["hole_r"], op="cut", target=name)
        for i, a in enumerate(30 + 60 * k for k in range(6)):
            x, z = 165.0 - 53.5 * math.sin(math.radians(a)), 174.0 + 53.5 * math.cos(math.radians(a))
            self.cyl(f"{name}_JS{i}", "y", y0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_JB{i}", "y", y0 - 1.0, y0 + ua["j3_cbore"][1], x, z, ua["j3_cbore"][0], op="cut", target=name)
        for i, a in enumerate(60 * k for k in range(6)):
            x, z = -22.0 * math.cos(math.radians(a)), 174.0 + 22.0 * math.sin(math.radians(a))
            self.cyl(f"{name}_HS{i}", "y", y0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_HB{i}", "y", y1 - ua["j2_cbore"][1], y1 + 1.0, x, z, ua["j2_cbore"][0], op="cut", target=name)
        cp = P["style"]["cap"]                                                 # J2 끝 덮개 자리(+y 면)
        self.cyl(f"{name}_CAPR", "y", y1 - cp["seat"], y1 + 1.0, 0.0, 174.0, 2 * (cp["r"] + cp["recess_extra"]), op="cut", target=name)
        lg = P["style"]["logo"]                                                # 앞(−y) 판면 KMJH 새김(아래팔이 1 mm 틈으로 지나가 돋움 대신 새김)
        sys.path.insert(0, str(ROOT / "src" / "cad" / "armold-mks-product-v3"))
        import kmjh_logo                                                       # noqa: PLC0415 (MP7 — 읽기만)
        rows, width = kmjh_logo.letters()
        h = lg["height"]
        pl, f = self.plane("y", y0 - 0.5)
        self.cmd("sketch.create", name=f"{name}_LOGO_SK", plane=pl)
        for _n, _role, pts in rows:
            loop = [f(lg["centre_x"] + (u - width / 2) * h, 174.0 + (v - 0.5) * h) for u, v in pts]
            self.cmd("sketch.line", points=[[round(float(a), 5), round(float(b), 5)] for a, b in loop], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(0.5 + lg["engrave"]), direction="positive", operation="cut", targets=[name], name=f"{name}_LOGO_X")

    def forearm(self, name="FOREARM"):
        P, g = self.P, self.g
        fa = P["j3"]["forearm"]
        y0, y1 = fa["plate_y"]
        hz = fa["beam_half_z"]
        x4 = L.motor_face_x(P, "J4")
        xe = x4 + fa["beam_end_past_motor_face"]
        outline = unary_union([circle(165.0, 174.0, fa["j3_disc_r"]), box(165.0, 174.0 - hz, xe, 174.0 + hz)])
        corner = fa["chamfer"]
        outline = outline.difference(Polygon([(xe - corner, 174.0 + hz + 1), (xe + 1, 174.0 + hz + 1), (xe + 1, 174.0 + hz - corner - 1)])).difference(
            Polygon([(xe - corner, 174.0 - hz - 1), (xe + 1, 174.0 - hz - 1), (xe + 1, 174.0 - hz + corner + 1)]))
        self.plate_y(name, y0, y1, outline)
        by0, by1 = fa["boss_y"]
        self.cyl(f"{name}_BC", "y", y1 - 1.0, by1, 165.0, 174.0, 2 * fa["boss_r_contact"])
        self.cyl(f"{name}_BO", "y", y1 - 1.0, fa["boss_outer_face_y"], 165.0, 174.0, 2 * fa["boss_r_outer"])
        self.combine(name, [f"{name}_BC", f"{name}_BO"], "join")
        for i, a in enumerate(60 * k for k in range(6)):
            x, z = 165.0 - 22.0 * math.sin(math.radians(a)), 174.0 + 22.0 * math.cos(math.radians(a))
            self.cyl(f"{name}_JS{i}", "y", y0 - 1.0, by1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_JB{i}", "y", y0 - 1.0, y0 + fa["j3_cbore"][1], x, z, fa["j3_cbore"][0], op="cut", target=name)
        for i, (yc, zc) in enumerate(P["pad"]["inserts_yz"]):
            x, z = x4 + zc, 174.0 - yc
            self.cyl(f"{name}_PS{i}", "y", y0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_PB{i}", "y", y1 - g["pad_cbore_depth"], y1 + 1.0, x, z, fa["pad_cbore"][0], op="cut", target=name)
        self.tie_pairs(name, "y", y0 - 1.0, y1 + 1.0, [(165.0 + fa["tie_x_from_j3"], 174.0 + P["ties"]["z_off"]), (165.0 + fa["tie_x_from_j3"], 174.0 - P["ties"]["z_off"])], along="h")

    def link5(self, name="LINK5"):
        P, g = self.P, self.g
        l5 = P["link5"]
        y0, y1 = l5["plate_y"]
        hz = l5["beam_half_z"]
        x5 = float(L.joint_origins_q0(P)["J5"][0])
        x6 = L.motor_face_x(P, "J6")
        xe = x6 + l5["beam_end_past_motor_face"]
        outline = unary_union([circle(x5, 174.0, l5["j5_disc_r"]), box(x5, 174.0 - hz, xe, 174.0 + hz)])
        c = l5["chamfer"]
        outline = outline.difference(Polygon([(xe - c, 174.0 + hz + 1), (xe + 1, 174.0 + hz + 1), (xe + 1, 174.0 + hz - c - 1)])).difference(
            Polygon([(xe - c, 174.0 - hz - 1), (xe + 1, 174.0 - hz - 1), (xe + 1, 174.0 - hz + c + 1)]))
        self.plate_y(name, y0, y1, outline)
        b0, b1 = l5["boss_y"]
        self.cyl(f"{name}_BOSS", "y", b0, y0 + 1.0, x5, 174.0, 2 * l5["boss_r"])
        self.combine(name, [f"{name}_BOSS"], "join")
        for i, a in enumerate(90 * k for k in range(4)):
            x, z = x5 + 20.5 * math.cos(math.radians(a)), 174.0 - 20.5 * math.sin(math.radians(a))
            self.cyl(f"{name}_HS{i}", "y", b0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_HB{i}", "y", y1 - l5["hub_cbore"][1], y1 + 1.0, x, z, l5["hub_cbore"][0], op="cut", target=name)
        for i, (yc, zc) in enumerate(P["pad"]["inserts_yz"]):
            x, z = x6 + zc, 174.0 - yc
            self.cyl(f"{name}_PS{i}", "y", y0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_PB{i}", "y", y1 - l5["pad_cbore"][1], y1 + 1.0, x, z, l5["pad_cbore"][0], op="cut", target=name)
        self.tie_pairs(name, "y", y0 - 1.0, y1 + 1.0, [(x5 + l5["tie_x_from_j5"], 174.0 + P["ties"]["z_off"]), (x5 + l5["tie_x_from_j5"], 174.0 - P["ties"]["z_off"])], along="h")

    def tool_flange(self, name="TOOL_FLANGE"):
        P, g = self.P, self.g
        tf = P["tool_flange"]
        z0, z1 = 43.5, 43.5 + tf["t"]
        r, c, br, bh = tf["r"], tf["chamfer"], g["tool_boss_r"], tf["boss_h"]
        self.revolve_z(name, [(z0, 0.0), (z0, r), (z1 - c, r), (z1, r - c), (z1, br), (z1 + bh, br), (z1 + bh, 0.0)])
        for i, (x, y) in enumerate(ring(4, 14.0, 45.0)):
            self.cyl(f"{name}_H{i}", "z", z0 - 0.5, z1 + bh + 0.5, x, y, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_C{i}", "z", z0 + tf["mp6_screw_under_head"], z1 + bh + 0.5, x, y, tf["mp6_cbore"], op="cut", target=name)
        for i, a in enumerate(tf["insert_angles"]):
            x, y = tf["insert_r"] * math.cos(math.radians(a)), tf["insert_r"] * math.sin(math.radians(a))
            self.cyl(f"{name}_I{i}", "z", z1 - tf["insert_depth"], z1 + bh + 0.5, x, y, g["ins"], op="cut", target=name)

    def tie_pairs(self, name, axis, a, b, centres, along):
        """케이블 타이 구멍 짝(MP10 목 크기 4.5 × 2.4) — centres = 짝 가운데(판 좌표) · along h = 다발이 가로(x)로 · v = 세로(z)로."""
        sl, sw = self.P["ties"]["slot"]
        pt = self.P["ties"]["pitch"] / 2
        for i, (u, v) in enumerate(centres):
            for j, sg in enumerate((1.0, -1.0)):
                if along == "h":                                            # 다발 가로 → 구멍 긴 변 가로 · 짝은 세로로 벌림
                    pts = [(u - sl / 2, v + sg * pt - sw / 2), (u + sl / 2, v + sg * pt - sw / 2), (u + sl / 2, v + sg * pt + sw / 2), (u - sl / 2, v + sg * pt + sw / 2)]
                else:
                    pts = [(u + sg * pt - sw / 2, v - sl / 2), (u + sg * pt + sw / 2, v - sl / 2), (u + sg * pt + sw / 2, v + sl / 2), (u + sg * pt - sw / 2, v + sl / 2)]
                self.prism(f"{name}_TIE{i}{j}", axis, a, b, pts, op="cut", target=name)

    def fit_coupons(self):
        """6818 끼움 시편 둘(판 B 전에 실물 베어링으로) — 슬리브 고리(바깥 = 슬리브 지름 · 위 모따기) · 구멍 고리(안 = 회전대 구멍 · 입구 모따기)."""
        fc, g = self.P["fit_coupons"], self.g
        h, c = fc["height"], fc["chamfer"]
        ro, ri = g["sleeve_r"], g["sleeve_r"] - fc["sleeve_ring_wall"]
        self.revolve_z("J1_FIT_SLEEVE", [(0.0, ri), (0.0, ro), (h - c, ro), (h, ro - c), (h, ri)])
        ri, ro = g["cup_bore_r"], g["cup_bore_r"] + fc["bore_ring_wall"]
        self.revolve_z("J1_FIT_BORE", [(0.0, ri), (0.0, ro), (h, ro), (h, ri + c), (h - c, ri)])

    # ---- 디자인 부품(KMJH · v3 외장 언어) ----
    def base_ring(self, name="BASE_RING"):
        br = self.P["style"]["base_ring"]
        (r0, r1), (z0, z1) = br["r"], br["z"]
        c = br["inner_top_chamfer"]                                             # 홈 45° 윗면에 맞춘 안쪽 위 모서리
        self.revolve_z(name, [(z0, r0), (z0, r1), (z1, r1), (z1, r0 + c), (z1 - c, r0)])
        s = br["split"] / 2
        self.box(f"{name}_SPLIT", [-(r1 + 1.0), -(r0 - 1.0)], [-s, s], [z0 - 0.5, z1 + 0.5], op="cut", target=name)      # 뒤(−x) 끊음 — 홈에 벌려 끼움

    def cap(self, name, cx, y_in, sgn):
        """끝 덮개 — 링크 면의 자리(깊이 seat)에 들어가는 남색 원판 + 바깥 모따기 + 갈비 돌기(누름 끼움). sgn = 바깥 방향(+1 = +y)."""
        cp = self.P["style"]["cap"]
        t, c = cp["t"], cp["chamfer"]
        rs = cp["r"] + cp["recess_extra"] - cp["seat_clear"]                  # 자리 틈 0.05(접착 한 방울)
        yo = y_in + sgn * t                                                    # 바깥 면
        prof = [(y_in, 0.0), (y_in, rs), (yo - sgn * c, rs), (yo, rs - c), (yo, 0.0)]       # (y, 반지름) — 납작 원판 + 바깥 모따기(안쪽 면을 판에 · 표시가 맨 위)
        self.revolve_y(name, cx, 174.0, prof)

    def mark(self, name, cx, y_face, sgn, h, w, raise_):
        """45° 사선 표시(돋움) — 면 y_face 에서 sgn 방향으로 raise_ 만큼."""
        pts = [(cx + px, 174.0 + pz) for px, pz in j5geom.slash(h, w)]
        ya, yb = sorted((y_face - sgn * 0.02, y_face + sgn * raise_))
        self.prism(name, "y", ya, yb, pts)

    def logo(self, name="UA_LOGO"):
        """KMJH 글자(MP7 kmjh_logo.py 를 읽기만) — 위팔 상자 바깥(+y) 면에 돋움 · +y 에서 바로 읽히게."""
        sys.path.insert(0, str(ROOT / "src" / "cad" / "armold-mks-product-v3"))
        import kmjh_logo                                                       # noqa: PLC0415 (MP7 — 읽기만)
        lg = self.P["style"]["logo"]
        ua = self.P["j3"]["upper_arm"]
        rows, width = kmjh_logo.letters()
        h = lg["height"]
        y0 = ua["box_y"][1]
        pl, f = self.plane("y", y0 - 0.02)
        self.cmd("sketch.create", name=f"{name}_SK", plane=pl)
        for _n, _role, pts in rows:
            loop = [f(lg["centre_x"] + (width / 2 - u) * h, 174.0 + (v - 0.5) * h) for u, v in pts][::-1]
            self.cmd("sketch.line", points=[[round(float(a), 5), round(float(b), 5)] for a, b in loop], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(lg["raise"] + 0.02), direction="positive", operation="new", body_name=name, name=f"{name}_X")

    def motor_cover(self, name, joint):
        """J2 · J3 모터 덮개(모듈 좌표) — 드럼 쪽(−x)이 열린 U · 양 끝 열림 · 모터 몸통에 닿는 갈비 · 옆면 통풍 홈 · 바깥 면 사선 홈."""
        P = self.P
        mc = P["style"]["motor_cover"]
        D = P["_drive"]
        C = L.belt_centre(D)
        hm = D["motor"]["frame"] / 2
        hi, ho = hm + mc["clear"], hm + mc["clear"] + mc["wall"]
        z0, z1 = mc["z_j2"] if joint == "J2" else mc["z_j3"]
        outer = chamfered_rect(C - ho, C + ho, -ho, ho, mc["corner"])
        u = outer.difference(box(C - hi, -hi, C + hi, hi)).difference(box(C - ho - 5.0, -hi, C - hi + 0.01, hi))
        ribs = []
        for o in mc["rib_offsets"]:
            ribs.append(box(C + hi - mc["rib_in"], o - mc["rib_w"] / 2, C + hi + 0.5, o + mc["rib_w"] / 2))          # 바깥 면
            ribs.append(box(C + o - mc["rib_w"] / 2, hi - mc["rib_in"], C + o + mc["rib_w"] / 2, hi + 0.5))                 # +y 면
            ribs.append(box(C + o - mc["rib_w"] / 2, -hi - 0.5, C + o + mc["rib_w"] / 2, -hi + mc["rib_in"]))                # −y 면
        geom = unary_union([u] + [r for r in ribs])
        self.prism(name, "z", z0, z1, poly_pts(geom))
        vw = mc["vent_w"] / 2
        for k, sg in enumerate((1.0, -1.0)):                                      # 옆면(±y) 통풍 홈
            self.box(f"{name}_VENT{k}", [C - vw, C + vw], sorted((sg * (hi - 0.5), sg * (ho + 1.0))), [z0 + mc["vent_margin"], z1 - mc["vent_margin"]],
                     op="cut", target=name)
        mk = mc["mark"]                                                          # 바깥 면(+x) 사선 홈(세운 면이라 색 대신 그림자 선)
        zc = (z0 + z1) / 2
        pts = [(py, zc + pz) for py, pz in j5geom.slash(mk["h"], mk["w"])]
        self.prism(f"{name}_MARK", "x", C + ho - mk["raise"], C + ho + 1.0, pts, op="cut", target=name)


def build_commands(P, g, spec):
    sc = ArmSC(spec, P, g)
    sc.mode = None
    sc.can_half("J1_CAN_A", -1)
    sc.can_half("J1_CAN_B", +1)
    sc.floor()
    sc.base()
    sc.spacer()
    sc.turret()
    sc.shoulder()
    sc.j2_hub()
    sc.upper_arm()
    sc.forearm()
    for tag, xf in (("J4", P["pad"]["x_face_j4"]), ("J6", P["pad"]["x_face_j6"])):
        sc.mode, sc.pad_face = "pad", xf
        sc.can_half(f"{tag}_CAN_A", -1)
        sc.mode = None
        sc.can_half(f"{tag}_CAN_B", +1)
        sc.cover(f"{tag}_REAR_COVER")
    sc.link5()
    sc.tool_flange()
    sc.base_ring()
    cp = P["style"]["cap"]
    ua_y1, fa_y0 = P["j3"]["upper_arm"]["plate_y"][1], P["j3"]["forearm"]["plate_y"][0]
    x3 = float(L.joint_origins_q0(P)["J3"][0])
    sc.cap("J2_CAP", 0.0, ua_y1 - cp["seat"], +1)                             # 위팔 +y 면 자리(깊이 1.5)에
    sc.cap("J3_CAP", x3, fa_y0, -1)                                            # 아래팔 −y 면 위에 바로(그 면이 출력 판 쪽이라 자리 없음)
    m = cp["mark"]
    sc.mark("J2_CAP_MARK", 0.0, ua_y1 - cp["seat"] + cp["t"], +1, m["h"], m["w"], m["raise"])
    sc.mark("J3_CAP_MARK", x3, fa_y0 - cp["t"], -1, m["h"], m["w"], m["raise"])
    sc.logo()
    sc.motor_cover("MOTOR_COVER_J2", "J2")
    sc.motor_cover("MOTOR_COVER_J3", "J3")
    sc.fit_coupons()
    for n, (_fr, _lk, col) in L.NEW_PARTS.items():
        sc.color(n, col)
    for n, col in L.COUPONS.items():
        sc.color(n, col)
    return sc.commands


def run(cli, script, native, step, work, env):
    p = subprocess.run([str(cli), "run", str(script), "--save", str(native)] + (["--out", str(step)] if step else []) +
                       ["--results", "--json-out", str(work / "result.json")], capture_output=True, text=True, encoding="utf-8", timeout=3600, env=env)
    (work / "run.log").write_bytes(((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"))
    return p


def prepare(params=HERE / "parameters.json", control=None):
    P = L.load(params)
    spec = j5geom.Spec(Path(P["_paths"]["wrist_code"]) / "parameters.json")
    P["_wrist_spec"] = spec
    g = geometry(P)
    lim = limits(P, g, spec) if control is None else None
    return P, g, spec, lim


def write_control_params(params, name, out):
    """대조 매개변수 사본 — 원천 경로는 절대 경로로(사본이 작업 폴더에 있어도 같은 파일을 읽게)."""
    raw = json.loads(Path(params).read_text(encoding="utf-8"))
    base = Path(params).resolve().parent
    raw["sources"] = {k: ((base / v).resolve().as_posix() if isinstance(v, str) and ("/" in v or v.endswith(".json")) else v) for k, v in raw["sources"].items()}
    cp = Path(out) / "parameters.json"
    cp.write_bytes((json.dumps(control_params(raw, name), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return cp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--control", choices=sorted(CONTROLS), default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--only", default=None, help="comma list of parts to build (scratch trial only)")
    a = ap.parse_args()
    scr = a.scratch.resolve()
    assert not inside(scr, ROOT), "scratch must be outside the repo"
    if a.control or a.only:
        assert a.out and inside(a.out, scr), "--control / --only need --out under --scratch"
        out, ev = a.out, a.out
    else:
        out, ev = L.MODEL, L.EV / "build"
    work = scr / ("build-" + (a.control or ("only" if a.only else "main")))
    for d in (out, out / "parts", ev, work):
        assert inside(d, L.MODEL, L.EV, scr), d
        d.mkdir(parents=True, exist_ok=True)
    if a.control:
        a.params = write_control_params(a.params, a.control, out)
    P, g, spec, lim = prepare(a.params, a.control)
    cmds = build_commands(P, g, spec)
    bodies = list(L.NEW_PARTS) + list(L.COUPONS)
    if a.only:
        bodies = [b for b in bodies if b in a.only.split(",")]
    stls = {n: out / "parts" / f"{n}.stl" for n in bodies}
    for n, p in stls.items():
        cmds.append({"command": "file.save_mesh", "params": {"path": str(p), "format": "stl", "bodies": [n], "quality": P["quality"]}})
    script = work / "build.json"
    script.write_bytes((json.dumps({"commands": cmds}, ensure_ascii=False) + "\n").encode("utf-8"))
    native = out / f"{L.NAME}-parts.solidcraft"
    env = dict(os.environ)
    env["PATH"] = str(a.cli.parent) + os.pathsep + env.get("PATH", "")
    p = run(a.cli, script, native, None, work, env)
    if p.returncode or not all(s.is_file() for s in stls.values()):
        raise SystemExit(f"solidcraft run rc {p.returncode}: {(p.stderr or p.stdout)[-3000:]}")
    bak = native.with_name(native.name + ".bak")
    if bak.is_file():
        bak.unlink()
    v = subprocess.run([str(a.cli), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    wc = Path(P["_paths"]["wrist_code"])
    rec = {"what": "MP17 팔 전체 새 부품 만들기 기록 — 이 sha 와 지금 파일이 같아야 검사가 지금 형상을 본 것이다", "control": a.control,
           "control_means": CONTROLS[a.control][0] if a.control else None, "geometry": g, "limits": lim, "screws": screws(P, g), "fits_used": P["_fits"], "fit_status": P["_fit_status"],
           "tool": {"cli_version": (v.stdout or v.stderr or "").strip(), "cli_sha256": sha(a.cli)},
           "inputs_sha256": {"parameters.json": sha(a.params), "build_arm.py": sha(__file__), "layout.py": sha(HERE / "layout.py"),
                             "j5geom.py(MP10)": sha(wc / "j5geom.py"), "parameters.json(MP10)": sha(wc / "parameters.json"),
                             "parameters.json(MP16)": sha(P["_paths"]["drive_params"]), "print-fits.json": sha(P["_paths"]["fits_ledger"]),
                             "motor-mks42d.json": sha(P["_paths"]["motor_ledger"]), "cycloid.json(MP6)": sha(P["_paths"]["reducer_json"]),
                             "v1 parameters.json": sha(Path(P["_paths"]["v1_dir"]) / "parameters.json")},
           "outputs_sha256": {**{f"parts/{n}.stl": sha(s) for n, s in stls.items()}, native.name: sha(native)},
           "command_count": len(cmds)}
    (ev / "build-record.json").write_bytes((json.dumps(rec, ensure_ascii=False, indent=1, default=float) + "\n").encode("utf-8"))
    print(json.dumps({"control": a.control, "commands": len(cmds), "parts": len(stls)}))


if __name__ == "__main__":
    main()
