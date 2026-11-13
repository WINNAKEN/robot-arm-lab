# -*- coding: utf-8 -*-
"""MP18 팔 전체 v2 — 새 인쇄 부품(SolidCraft 명령줄 · MP17 생성기를 복사해 고침 · MP17 파일은 그대로).

부품마다 지역 좌표(layout.NEW_PARTS 의 틀)로 만든다 — 한 문서에 겹쳐 있어도 부품 STL 은 따로 낸다(조립 자리 = layout.placement).
J1 · J4 · J6 모터 몸통 = MP10 생성기(`../j5-wrist-v1/j5geom.py`)를 읽기만 해서 불러 쓴 캔(목 대신: J1 = 없음 · J4 · J6 = 링크 받침 + 인서트).
끼움 · 구멍 보정은 원장(print-fits.json)에서 읽는다. 쓰기 = models/manipulator-v2 · .dev/mp18-evidence · --scratch 만.
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

from shapely.geometry import LineString, Point, Polygon, box
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
    "j3_turn_zero": ("MP18: J3 module not turned (motor back above the elbow, out of the upper-arm box)", [(("j3", "module_turn_deg"), 0.0)], True),
    "logo_one_letter": ("MP18: KMJH letters not joined (only the first letter body saved - the MP17 fault)", [(("v2", "logo", "join_letters"), False)], True),
    "ua_j3_ribs_back": ("MP18: J3-end cover ribs back in the box at r 59 (they block the J3 module's way in - review R1-1)",
                        [(("v2", "upper_arm", "cover_ribs"), [{"at": [224.0, 174.0], "out": "+x"}, {"at": [165.0, 233.0], "out": "+z"}, {"at": [165.0, 115.0], "out": "-z"}])], True),
    "j3_bracket_post_out": ("MP18: J3 bracket posts r 55 -> 59 (post walls into the box wall r 61.5)", [(("v2", "j3_bracket", "post_r"), 59.0)], True),
    "mark_floating": ("MP18: raised marks start 0.3 above their faces instead of 0.02 inside (review R1-12)", [(("v2", "caps", "mark_embed"), -0.3)], True),
    "hood_rib_tight": ("MP18: J2 motor-hood ribs press 1.0 instead of 0.15", [(("v2", "shoulder", "hood", "rib_press"), 1.0)], True),
    "shroud_small": ("MP18: shoulder rear housing drum r 64 -> 60 (wall into the J2 cap r 59)", [(("v2", "shoulder", "drum_r"), 60.0)], True),
    "tube_slot_narrow": ("MP18: forearm / J6 tube slot from y 39.5 -> 44 (tube wall into the forearm / link-5 plate)", [(("v2", "tubes", "slot_y"), [44.0, 62.0])], True),
    "ua_bar_low": ("cable unit: upper-arm bar half-height 45.5 -> 39 (the J3 57D terminal envelopes run into the walls)", [(("v2", "upper_arm", "bar_half_z"), 39.0)], True),
    "hood_no_pockets": ("cable unit: J2 hood without the terminal bumps / pockets (the MP18 box hood)", [(("v2", "shoulder", "hood", "pockets"), False)], True),
    "hood_exit_closed": ("cable unit: no cable hole in the navy hood face", [(("v2", "shoulder", "hood", "exit", "d"), 0.0)], True),
    "ua_entry_closed": ("cable unit: no cable entry through the upper-arm J2-end wall", [(("v2", "upper_arm", "j2_entry", "d"), 0.0)], True),
    "skin_slot_small": ("cable unit: base-skin cable slot back to 16 wide / 7 + 45 deg (MP18 size - the in and out bundles do not pass)",
                        [(("v2", "base_skin", "cable_slot", "w"), 16.0), (("v2", "base_skin", "cable_slot", "side_h"), 7.0), (("v2", "base_skin", "cable_slot", "apex_h"), 15.0)], True),
    "j2_loop_short": ("cable unit: J2 cable loop 75 -> 50 mm (shorter than the 56 the wanted range needs)", [(("v2", "cable", "loops", 1, "length"), 50.0)], False),
    "loop_anchor_off": ("cable unit: J3 loop forearm anchor moved 10 mm off the end of its fixed segment", [(("v2", "cable", "loops", 2, "b", "p"), [205.0, 36.0, 160.0])], False),
    "j1_loop_fold": ("cable review R1-1: J1 loop 300 -> 265 mm (enough only when the wrap angle is folded into 0 .. 180 deg - the -170 deg end needs 282)",
                     [(("v2", "cable", "loops", 0, "length"), 265.0)], False),
    "cable_in_j3_motor": ("cable review R1-3: one upper-arm cable point moved into the J3 57D motor body (a same-link purchased-part envelope)",
                          [(("v2", "cable", "segments", 7, "pts", 7), [74.0, 65.0, 190.0])], False),
    "tie_decl_off": ("cable review R1-2: the J2-loop tie on the hood face looked for 20 mm above where it is cut", [(("v2", "cable", "ties", "J2.a", "c"), [-80.0, 84.75, 217.0])], False),
    "notch_no_travel": ("cable review R1-4: upper-arm plate notches without the belt-tension travel (J3 terminal envelopes at the slot ends run into the plate)",
                        [(("v2", "upper_arm", "notches", "travel"), 0.0)], True),
    "hood_vents_short": ("cable review R1-5: hood vent slots cut only to the box top (the octagon fill closes them)", [(("v2", "shoulder", "hood", "vent_top"), "box")], True),
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


def tube_cable_slot(P, name):
    """통 뒤판 케이블 구멍(y, z) — MP18 이어서 검토 R1-11: 통 틈을 따라 원호 홈(가운데 반지름 r · 폭 d · 둥근 끝 · arc_deg) · 없으면 지름 d 둥근 구멍."""
    ch = P["v2"]["tubes"]["cable_hole"]
    if "arc_deg" in ch:
        a0, a1 = ch["arc_deg"][name]
        n = max(8, int(abs(a1 - a0) / 2.0) + 1)
        pts = [(ch["r"] * math.cos(math.radians(a0 + (a1 - a0) * i / n)), 174.0 + ch["r"] * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        return LineString(pts).buffer(ch["d"] / 2, 16)
    if "phi_deg" in ch:
        ph = math.radians(ch["phi_deg"][name])
        return Point(ch["r"] * math.cos(ph), 174.0 + ch["r"] * math.sin(ph)).buffer(ch["d"] / 2, 32)
    return Point(ch["y"], ch["z"]).buffer(ch["d"] / 2, 32)


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
    ph3 = P["v2"]["upper_arm"]["j3_stand_phase_deg"] + P["j3"]["module_turn_deg"]                   # MP18: 모듈과 함께 돈 덮개 윗면 인서트
    j3c = [(o3 - 53.5 * math.sin(math.radians(a)), ua["plate_y"][0] + ua["j3_cbore"][1], 174.0 + 53.5 * math.cos(math.radians(a))) for a in (ph3 + 60 * k for k in range(6))]
    add("upper_arm_to_j3_cap", 10, "W", j3c, (0, 1, 0), ["UPPER_ARM"], "J3.CAP", "MP16 stand inserts r 53.5 - phase 30 + module turn 90")
    u2 = P["v2"]["upper_arm"]
    yc = u2["wall_top_y"] + u2["cover_t"] - 1.65 - 0.2
    sc_ = ArmSC.__new__(ArmSC)
    sc_.P = P
    add("ua_cover_to_upper_arm", u2["cover_screw_len"], "W", [(x, yc, z) for x, z, _ya, _o in sc_.ua_rib_points()], (0, -1, 0), ["UA_COVER"], "UPPER_ARM",
        "MP18 front cover, J2 end - button heads in 0.2 + 1.65 deep counterbores")
    btabs, bposts, byf = sc_.j3_bracket_points()
    add("ua_cover_to_j3_bracket", u2["cover_screw_len"], "W", [(x, yc, z) for x, z in bposts], (0, -1, 0), ["UA_COVER"], "UA_J3_BRACKET",
        "MP18 review R1-1: front cover, J3 end - into the bracket post inserts")
    add("j3_bracket_to_j3_base", P["_drive"]["screws"]["guard"][1], "W", [(x, byf + P["v2"]["j3_bracket"]["t"], z) for x, z in btabs], (0, -1, 0),
        ["UA_J3_BRACKET"], "J3.HOUSING_BASE", "MP16 J3 belt-guard tab inserts and screws (M3 x 8, BOM 2d) - v2 does not print the guard")
    fa = P["j3"]["forearm"]
    j3f = [(o3 - 22.0 * math.sin(math.radians(a)), fa["plate_y"][0] + fa["j3_cbore"][1], 174.0 + 22.0 * math.cos(math.radians(a)))
           for a in (P["j3"]["module_turn_deg"] + 60 * k for k in range(6))]                      # MP18: 모듈과 함께 돈 캐리어 인서트
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
    sk = P["v2"]["base_skin"]                                                    # MP18: 바닥판 밑에서 원뿔 겉 발 셋(M3 x 10)
    add("floor_to_base_skin", 8, "J1", [(sk["screw_r"] * math.cos(math.radians(a)), sk["screw_r"] * math.sin(math.radians(a)), zf + fl["base_cbore"][1])
                                         for a in sk["screw_angles"]], (0, 0, 1), ["FLOOR"], "BASE_SKIN", "MP18 base skin feet")
    sh2 = P["v2"]["shoulder"]                                                     # MP18: 어깨 뒤 통 = MP16 벨트 덮개 귀 셋(바닥판 밑 인서트 · M3 x 8 그대로)
    gd = P["_drive"]["guard"]
    ys_ = float((Fr["M2"] @ [0.0, 0.0, 0.0, 1.0])[1]) - sh2["tab_t"]
    tabs = []
    for a in gd["tab_angles_deg"]:
        w_ = Fr["M2"] @ [gd["tab_radius"] * math.cos(math.radians(a)), gd["tab_radius"] * math.sin(math.radians(a)), 0.0, 1.0]
        tabs.append((float(w_[0]), ys_, float(w_[2])))
    add("shoulder_shroud_to_j2_base", 8, "W", tabs, (0, 1, 0), ["SHOULDER_SHROUD"], "J2.HOUSING_BASE",
        "MP16 guard tab screws reused (the housing replaces the belt guard) · the motor-end tab (M3 x 12 + nut through the lobe) is not ray-checked")
    tb = P["v2"]["tubes"]
    for tag, fr, cap_ in (("J4", "C4", "FA_TUBE_CAP"), ("J6", "C6", "J6_TUBE_CAP")):     # MP18: 통 뒤판을 몸통 뒤 덮개 나사로(길게)
        cvp = [(sp.cover["r"] * math.cos(math.radians(a)), sp.cover["r"] * math.sin(math.radians(a)), sp.z_rear - sp.cover["t"] - tb["plate_t"]) for a in sp.cover["angles"]]
        add(f"{cap_.lower()}_to_{tag.lower()}_can", tb["cover_screw_len"], fr, cvp, (0, 0, 1), [cap_, f"{tag}_REAR_COVER"], f"{tag}_CAN_A|{tag}_CAN_B",
            "MP10 rear-cover screws M3 x 10 -> 12 (3 mm tube rear plate under the heads)")
    return S


def v2_internals(P):
    """MP18: 위팔 상자 안의 J3 구동부(돌린 모듈) 윤곽 (x, z) — y 범위별: 덮개(원 r 59 · y 59 ~ 118.3) · 바닥판(원 + 날개 · y 118.3 ~ 128.3) · 모터(y 53.2 ~ 123.3) · 벨트 고리(풀리 60 / 20 + 벨트 · y 129.8 ~ 162.8)."""
    D = P["_drive"]
    C = L.belt_centre(D)
    t = math.radians(P["j3"]["module_turn_deg"])
    def w(xm, ym):                                                                # 모듈 (x, y) → 세계 (x, z)(돌림 포함)
        xr, yr = xm * math.cos(t) - ym * math.sin(t), xm * math.sin(t) + ym * math.cos(t)
        return 165.0 - yr, 174.0 + xr
    b = D["base"]
    lobe = Polygon([w(0.0, -b["lobe_half_width"]), w(b["lobe_x_end"], -b["lobe_half_width"]), w(b["lobe_x_end"], b["lobe_half_width"]), w(0.0, b["lobe_half_width"])])
    base = unary_union([circle(165.0, 174.0, b["outer_radius"]), lobe])
    hm = D["motor"]["frame"] / 2
    mx, mz = w(C, 0.0)
    motor = box(mx - hm, mz - hm, mx + hm, mz + hm)
    pe = D["belt"]["pulley_envelope"]
    belt = unary_union([circle(165.0, 174.0, pe["big_od"] / 2 + 1.0), circle(mx, mz, pe["small_od"] / 2 + D["belt"]["thickness"] + 1.0)]).convex_hull
    return {"cap": circle(165.0, 174.0, D["cap"]["screw_radius"] + 4.5), "base": base, "motor": motor, "belt": belt}


def bracket_limits(P, sc, inner, I, gap):
    """MP18 검토 R1-1: J3 끝 덮개 받침대 — 상자 안 · 벨트 밖 · 덮개 나사 자리가 J3 뚜껑 자리 밖."""
    bk, cp = P["v2"]["j3_bracket"], P["v2"]["caps"]
    _tabs, posts, _yf = sc.j3_bracket_points()
    plan = sc.j3_bracket_plan()
    pr = bk["post_d"] / 2
    pc = unary_union([circle(x, z, pr) for x, z in posts])
    return {
        "j3_bracket_inside_box": inner.buffer(-gap + 0.05).contains(unary_union([plan, pc])),      # 0.05 = 다각형 현 오차(기둥이 벽과 꼭 2.0)
        "j3_bracket_clear_of_belt": plan.distance(I["belt"]) >= 1.0 and pc.distance(I["belt"]) >= 1.0,
        "j3_bracket_post_pads_under_posts": bk["post_pad_r"] < pr,
        "j3_bracket_plan_one_piece": sc.j3_bracket_plan(raw=True).geom_type == "Polygon",
        "cover_screws_clear_of_j3_cap_recess": all(math.hypot(x - 165.0, z - 174.0) - 3.25 - (cp["j3_r"] + cp["recess_clear"]) >= 1.0 for x, z in posts),
    }


def skin_limits(P, g):
    """MP18 검토 R1-9: 원뿔 겉 발 — 인서트(바깥 4.2) 둘레 벽 ≥ min_wall · BASE 와 1 mm."""
    k, mw = P["v2"]["base_skin"], P["min_wall"]
    (z0, z1), rb, rt = k["z"], k["r_bottom"], k["r_top"]
    ro = rb + (rt - rb) * k["insert_depth"] / (z1 - z0)
    return {
        "skin_foot_side_wall": k["boss_r"] - g["ins_od"] / 2 >= mw - 1e-9,
        "skin_insert_outer_wall": ro - (k["screw_r"] + g["ins_od"] / 2) >= mw - 1e-9,
        "skin_foot_clears_base": k["screw_r"] - k["boss_r"] - P["j1"]["base"]["wall_r"][1] >= 1.0 - 1e-9,
    }


def cable_limits(P, g, sc):
    """MP18 이어서(57D 단자 · 케이블): 단자 칸 · 창 · 구멍 · 묶음 구멍이 서로 · 나사 자리와 벽 min_wall(2) 이상."""
    u, t5, W, mw = P["v2"]["upper_arm"], P["v2"]["term57"], P["v2"]["wall"], P["min_wall"]
    D = P["_drive"]
    hm = D["motor"]["frame"] / 2
    Rr = hm + t5["driver_excess"] + t5["clearance"] + t5["pocket_gap"]
    bt = t5["band_half"] + t5["pocket_gap"]
    xm = 165.0 - L.belt_centre(D)
    hx, hz = hm + u["motor_window_clear_x"], hm + u["motor_window_clear"]
    ph = u["j3_stand_phase_deg"] + P["j3"]["module_turn_deg"]
    cb = [Point(165.0 - 53.5 * math.sin(math.radians(a)), 174.0 + 53.5 * math.cos(math.radians(a))).buffer(P["j3"]["upper_arm"]["j3_cbore"][0] / 2, 32)
          for a in (ph + 60 * k for k in range(6))]
    ex0, ex1 = u["notches"]["exit_x"]
    top_exit = u["notches"].get("exit_side", "bottom") == "top"
    tr = u["notches"].get("travel", 0.0)                                       # 검토 R1-4: 벨트 장력 이동(±2.5)
    btx = bt + tr
    wide, narrow = (min(ex0, xm - btx), max(ex1, xm + btx)), (xm - btx, xm + btx)
    tx, bx_ = (wide, narrow) if top_exit else (narrow, wide)
    win = unary_union([box(xm - hx, 174.0 - hz, xm + hx, 174.0 + hz), box(tx[0], 174.0 + hz - 1.0, tx[1], 174.0 + Rr),
                       box(bx_[0], 174.0 - Rr, bx_[1], 174.0 - hz + 1.0), box(xm - Rr - tr, 174.0 - bt, xm - hx + 1.0, 174.0 + bt)])
    je = u["j2_entry"]
    rc = u["j2_end_r"] - W / 2
    ec = Point(rc * math.cos(math.radians(je["phi_deg"])), 174.0 + rc * math.sin(math.radians(je["phi_deg"])))
    posts = [Point(x, z) for x, z in u["cover_posts_xz"]]
    h, s5 = P["v2"]["shoulder"]["hood"], P["v2"]["shoulder"]
    xh = -L.belt_centre(D)
    ho = hm + h["x_clear"] + W
    tb = P["v2"]["tubes"]
    sp = P["_wrist_spec"]
    covs = [(sp.cover["r"] * math.cos(math.radians(a)), sp.cover["r"] * math.sin(math.radians(a))) for a in sp.cover["angles"]]
    tube_ok = []
    for nm, fr in (("FA_TUBE", "C4"), ("J6_TUBE", "C6")):
        ch = tb["cable_hole"]
        hole = tube_cable_slot(P, nm)                                          # 검토 R1-11: 통 틈을 따라 원호 홈(둥근 끝)
        M = L.frames(P)[fr]
        for x_, y_ in covs:
            w_ = M @ [x_, y_, sp.z_rear, 1.0]
            tube_ok.append(hole.distance(Point(float(w_[1]), float(w_[2]))) - tb["cover_screw_clear"] / 2 >= mw)
        tube_ok.append(ch["r"] - ch["d"] / 2 >= sp.outer_r + 0.2 and ch["r"] + ch["d"] / 2 <= tb["r_in"] - 0.2)
    ft_ok = []                                                                 # 검토 R1-2: 통 앞 타이 — 앞 고리 · 통풍 홈(−y 쪽)과 벽 min_wall
    sl_ = P["ties"]["slot"][0]
    for nm, fr in (("FA_TUBE", "C4"), ("J6_TUBE", "C6")):
        f_ = tb.get("front_tie", {}).get(nm)
        if f_:
            M = L.frames(P)[fr]
            x_rear = float((M @ [0.0, 0.0, sp.z_rear, 1.0])[0]) - sp.cover["t"]
            x_front = float((M @ [0.0, 0.0, 0.0, 1.0])[0])
            ft_ok.append(f_["x_from_front"] - sl_ / 2 - tb["ring_len"] >= mw)
            near_vents = abs(((f_["phi_deg"] - 180.0) + 180.0) % 360.0 - 180.0) < 30.0       # 통풍 홈 = −y 쪽(180° ± 13°)
            ft_ok.append(not near_vents or x_rear + tb["vents"]["x_from_rear"][1] + mw <= x_front - f_["x_from_front"] - sl_ / 2)
            ph_ = math.radians(f_["phi_deg"])                                  # +y 판 홈(y ≥ slot_y[0] · z slot_z)과 떨어짐 — 타이 바깥 끝(접선 반 간격 + 반 폭)까지
            ty_max = (tb["r_in"] + tb["wall"]) * math.cos(ph_) + (P["ties"]["pitch"] / 2 + P["ties"]["slot"][1] / 2) * abs(math.sin(ph_))
            ft_ok.append(ty_max + mw <= tb["slot_y"][0] or not (tb["slot_z"][0] <= 174.0 + tb["r_in"] * math.sin(ph_) <= tb["slot_z"][1]))
    l5, x5 = P["link5"], float(L.joint_origins_q0(P)["J5"][0])
    tab = l5["tab"]
    hub = [Point(x5 + 20.5 * math.cos(math.radians(a)), 174.0 - 20.5 * math.sin(math.radians(a))).buffer(l5["hub_cbore"][0] / 2, 32) for a in (0, 90, 180, 270)]
    sl, sw = P["ties"]["slot"]
    tie5 = box(x5 + tab["tie_x_from_j5"] - sl / 2, 174.0 - P["ties"]["pitch"] / 2 - sw / 2, x5 + tab["tie_x_from_j5"] + sl / 2, 174.0 + P["ties"]["pitch"] / 2 + sw / 2)
    k = P["v2"]["base_skin"]
    t_ = k["tie"]
    skin_r = k["r_bottom"] + (k["r_top"] - k["r_bottom"]) * (t_["z"] - k["z"][0]) / (k["z"][1] - k["z"][0])
    feet_gap = min(abs(((t_["angle"] - a) + 180.0) % 360.0 - 180.0) for a in k["screw_angles"]) * math.pi / 180.0 * skin_r
    ex = h["exit"]
    pt_ = P["ties"]["pitch"] / 2

    def tie_rects(cu, cv, along):                                              # tie_pairs 와 같은 꼴(판 좌표 짝 두 네모)
        if along == "h":
            return unary_union([box(cu - sl / 2, cv + sg * pt_ - sw / 2, cu + sl / 2, cv + sg * pt_ + sw / 2) for sg in (1.0, -1.0)])
        return unary_union([box(cu + sg * pt_ - sw / 2, cv - sl / 2, cu + sg * pt_ + sw / 2, cv + sl / 2) for sg in (1.0, -1.0)])
    face_o = sc.hood_outlines()[0]
    fts = [tie_rects(t["at"][0], t["at"][1], t["along"]) for t in h.get("face_ties", [])]
    exit_c = Point(ex["x"], ex["z"]).buffer(ex["d"] / 2, 64) if ex.get("d", 0.0) > 0.0 else None
    vt_ = u["vents"]
    vx = [vt_["x"][0] + (vt_["x"][1] - vt_["x"][0]) * i / max(1, vt_["n"] - 1) for i in range(vt_["n"])]
    vents_xy = unary_union([box(x - vt_["w"] / 2, vt_["y"][0], x + vt_["w"] / 2, vt_["y"][1]) for x in vx])
    top_posts = unary_union([box(x - u["boss_r"], 0.0, x + u["boss_r"], 400.0) for x, z in u["cover_posts_xz"] if z > 174.0])
    ua_ties = [tie_rects(it_["x"], it_["y"], "h") for it_ in (u["inner_tie"], u.get("j2_tie")) if it_ and it_.get("side", "top") == "top"]
    return {
        "hood_face_ties_inside_face_clear_of_hole": all(face_o.buffer(-mw).contains(r) and (exit_c is None or r.distance(exit_c) >= mw) for r in fts)
                                                    and all(a_.distance(b_) >= mw for i, a_ in enumerate(fts) for b_ in fts[i + 1:]),
        "ua_top_ties_clear_of_vents_and_posts": all(r.distance(vents_xy) >= mw and r.distance(top_posts) >= mw and r.bounds[1] >= u["plate_y"][1] + mw
                                                    and r.bounds[3] <= u["wall_top_y"] - mw for r in ua_ties) and all(a_.distance(b_) >= mw for i, a_ in enumerate(ua_ties) for b_ in ua_ties[i + 1:]),
        "tube_front_ties_clear_of_ring_and_vents": all(ft_ok),
        "ua_inner_holds_j3_terminals": (u["bar_half_z"] - W) - Rr >= 0.4,
        "j3_window_and_notches_clear_of_j3_cap_cbores": all(win.distance(c) >= mw for c in cb),
        "j2_entry_clear_of_cover_posts": all(ec.distance(p) - je["d"] / 2 - u["boss_r"] >= mw for p in posts),
        "hood_exit_inside_face_and_outside_bumps": (abs(ex["x"] - xh) + ex["d"] / 2 <= ho - mw and abs(ex["z"] - 174.0) + ex["d"] / 2 <= ho - mw
                                                    and abs(ex["x"] - xh) - ex["d"] / 2 >= bt + W),
        "hood_entry_slot_inside_bottom_bump": h["entry_slot"]["half_w"] + mw <= bt + W and h["entry_slot"]["y"][0] - h["entry_slot"]["half_w"] >= h["y"][0] + mw,
        "tube_cable_holes_in_annulus_clear_of_cover_screws": all(tube_ok),
        "link5_tab_tie_clear_of_hub_cbores": all(tie5.distance(c) >= mw for c in hub) and tie5.bounds[0] - (x5 + tab["x_from_j5"][0]) >= mw,
        "skin_tie_clear_of_feet": feet_gap - k["boss_r"] - P["ties"]["pitch"] / 2 - sw >= mw,
        "hood_bump_keepout_gap": s5["hood_bump_keepout_gap"] >= 1.0,
    }


def v2_limits(P, g):
    sc = ArmSC.__new__(ArmSC)
    sc.P = P
    u = P["v2"]["upper_arm"]
    gap, W = P["v2"]["gap"], P["v2"]["wall"]
    inner = sc.ua_outline(-W)
    I = v2_internals(P)
    ribs = [(x, z, ya) for x, z, ya, _o in sc.ua_rib_points()]
    rib = lambda x, z: box(x - u["boss_r"], z - u["boss_r"], x + u["boss_r"], z + u["boss_r"])        # noqa: E731 — 네모로 셈(원 기둥보다 큼)
    D = P["_drive"]
    hm = D["motor"]["frame"] / 2
    ex57 = P["v2"].get("term57", {}).get("driver_excess", 0.0)                 # MP18 이어서: 57D 드라이버 가정 폭(모터 몸통보다 한쪽 1.85)
    return {
        "box_holds_j3_cap": inner.buffer(-gap).contains(circle(165.0, 174.0, D["base"]["outer_radius"])),
        "box_holds_j3_base_and_motor": inner.buffer(-gap).contains(unary_union([I["base"], I["motor"]])),
        "box_holds_belt": inner.buffer(-gap).contains(I["belt"]),
        "motor_window_clear": u["motor_window_clear"] >= 1.5,
        "plate_strips_beside_window": (u["bar_half_z"] - hm - u["motor_window_clear"]) >= 6.0,     # 판 홈 밖 x 구간의 창 옆 띠(홈 자리는 아래 상자 단면이 짐)
        "box_walls_carry_bending_at_notches": L.ua_box_section(P) >= 4.0 * 7.0 * 60.0 ** 2 / 6.0,     # 케이블 검토 R1-8: 판 홈 자리 위 · 아래 벽 + 덮개 ≥ MP17 판(7 × 60) × 4
        "ribs_clear_of_belt": all(rib(x, z).distance(I["belt"]) >= 1.0 for x, z, ya in ribs),
        "plate_posts_clear_of_internals": all(rib(x, z).distance(unary_union([I["base"], I["motor"], I["cap"]])) >= 1.0 for x, z, ya in ribs if ya < 118.3),
        "rib_feet_above_base_plate": all(ya - u["rib_wedge"] >= 128.3 + 1.0 for x, z, ya in ribs if ya >= 118.3),
        "no_box_ribs_in_j3_module_path": all(rib(x, z).distance(circle(165.0, 174.0, D["base"]["outer_radius"])) >= 1.0 for x, z, ya in ribs if ya >= 118.3),
        "window_covers_tension_travel": u.get("motor_window_clear_x", u["motor_window_clear"]) >= ex57 + D["belt"]["slot_travel"] + 1.0,
        "window_clears_driver_z": u["motor_window_clear"] >= ex57 + 1.0,
        **bracket_limits(P, sc, inner, I, gap),
        **skin_limits(P, g),
        **(cable_limits(P, g, sc) if "term57" in P["v2"] else {}),
    }


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
        **v2_limits(P, g),
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
        raise SystemExit(f"MP18 geometry out of limits: {bad}")
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
        sk = P["v2"]["base_skin"]                                             # MP18: 원뿔 겉 나사 셋(밑에서)
        for i, a in enumerate(sk["screw_angles"]):
            x, y = sk["screw_r"] * math.cos(math.radians(a)), sk["screw_r"] * math.sin(math.radians(a))
            self.cyl(f"{name}_KH{i}", "z", z0 - 0.5, z1 + 0.5, x, y, g["m3"], op="cut", target=name)
            self.cyl(f"{name}_KC{i}", "z", z0 - 0.5, z0 + fl["base_cbore"][1], x, y, fl["base_cbore"][0], op="cut", target=name)
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
            hw = b.get("window_half_width_back", b["window_half_width"]) if a == 180.0 else b["window_half_width"]    # MP18 이어서: 뒤 창 = 들고 나는 묶음 둘
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
        if "term57" in P["v2"]:                                               # MP18 이어서: 두건(57D 드라이버 맞춤 · 단자 혹 팔각)이 판을 지나는 자리 = 두건 바깥 + 틈
            outline = outline.difference(self.hood_outlines()[0].buffer(P["v2"]["shoulder"]["hood_bump_keepout_gap"], join_style=2))
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
        ties = [tuple(t) for t in sh.get("ties", [[80.0, 135.0], [-80.0, 135.0]])]       # MP18 이어서: 자리표시 둘 없앰(케이블은 두건 아래 홈에서 잡음)
        if ties:
            self.tie_pairs(name, "y", y0 - 1.0, y1 + 1.0, ties, along="v")

    def j2_hub(self, name="J2_HUB"):
        P, g = self.P, self.g
        h = P["j2"]["hub"]
        self.cyl(name, "y", h["y"][0], h["y"][1], 0.0, 174.0, 2 * h["r_contact"])
        self.cyl(f"{name}_OUT", "y", h["outer_face_y"], h["y"][1], 0.0, 174.0, 2 * h["r_outer"])
        self.combine(name, [f"{name}_OUT"], "join")
        for i, a in enumerate(60 * k for k in range(6)):
            self.cyl(f"{name}_H{i}", "y", h["y"][0] - 1.0, h["y"][1] + 1.0, -22.0 * math.cos(math.radians(a)), 174.0 + 22.0 * math.sin(math.radians(a)), g["m3c"],
                     op="cut", target=name)

    # ---- MP18 어깨 집(뒤 통 + 모터 두건) ----
    def sh_outline(self, off=0.0):
        """어깨 뒤 통 윤곽(x, z) — J2 북(원) + 뒤 기둥(모서리 모따기) · 바닥은 z bottom_z 에서 자름."""
        s = self.P["v2"]["shoulder"]
        (x0, x1), (z0, z1), c = s["post_x"], s["post_z"], s["post_chamfer"]
        post = Polygon([(x0, z0), (x1, z0), (x1, z1), (x0 + c, z1), (x0, z1 - c)])          # 왼쪽 위 모서리만 모따기(오른쪽 위 모따기는 북 원과 오목한 자리를 만들어 J2 날개를 파고듦)
        geom = unary_union([circle(0.0, 174.0, s["drum_r"], n=240), post])
        geom = geom.intersection(box(-400.0, s["bottom_z"], 400.0, 400.0))
        return geom.buffer(off, join_style=1, resolution=16) if off else geom          # 둥근 이음(오목 모서리의 뾰족한 연장이 J2 날개에 닿음 — 2026-11-06)

    def guard_tabs(self):
        """MP16 벨트 덮개 귀 자리 → (세계 x, z, 모터 쪽 귀인지) + 바닥판 밑면 세계 y. 뒤 통이 덮개 대신 같은 인서트 · 나사를 쓴다."""
        gd = self.P["_drive"]["guard"]
        Fr = L.frames(self.P)
        pts = [(gd["tab_radius"] * math.cos(math.radians(a)), gd["tab_radius"] * math.sin(math.radians(a))) for a in gd["tab_angles_deg"]] + [(gd["tab_motor_x"], 0.0)]
        out = []
        for i, (xm, ym) in enumerate(pts):
            w = Fr["M2"] @ [xm, ym, 0.0, 1.0]
            out.append((float(w[0]), float(w[2]), i == len(pts) - 1))
        return out, float((Fr["M2"] @ [0.0, 0.0, 0.0, 1.0])[1])

    def shoulder_shroud(self, name="SHOULDER_SHROUD"):
        """J2 뒤 통 — 북 + 뒤 기둥 · 뒤판 · 바닥 열림 · 앞(어깨 판 쪽) 열림. MP16 벨트 덮개 귀 넷 자리의 기둥으로 바닥판 밑 인서트에 나사(덮개 대신)."""
        P, g = self.P, self.g
        s, W = P["v2"]["shoulder"], P["v2"]["wall"]
        y0, y1, yb = s["back_y"], s["front_y"], s["back_y"] + s["back_t"]
        self.prism(name, "y", y0, y1, poly_pts(self.sh_outline()))
        self.prism(f"{name}_IN", "y", yb, y1 + 1.0, poly_pts(self.sh_outline(-W)), op="cut", target=name)
        bx0, _bz0, bx1, _bz1 = self.sh_outline(-W).bounds
        self.box(f"{name}_OPEN", [bx0, bx1], [yb, y1 + 1.0], [s["bottom_z"] - 1.0, s["bottom_z"] + W + 0.5], op="cut", target=name)
        vt = s["vents"]                                                        # 통풍 홈 — 기둥 윗면(J2 모터 몸통 위)
        zt = s["post_z"][1]
        for i in range(vt["n"]):
            x = vt["x"][0] + (vt["x"][1] - vt["x"][0]) * i / max(1, vt["n"] - 1)
            self.box(f"{name}_V{i}", [x - vt["w"] / 2, x + vt["w"] / 2], vt["y"], [zt - W - 1.0, zt + 1.0], op="cut", target=name)
        tabs, yface = self.guard_tabs()
        for i, (x, z, _me) in enumerate(tabs):
            self.cyl(f"{name}_TAB{i}", "y", yb - 0.5, yface, x, z, 2 * s["tab_boss_r"])
            self.combine(name, [f"{name}_TAB{i}"], "join")
            self.cyl(f"{name}_TH{i}", "y", y0 - 1.0, yface + 1.0, x, z, g["m3"], op="cut", target=name)
            self.cyl(f"{name}_TC{i}", "y", y0 - 1.0, yface - s["tab_t"], x, z, 6.5, op="cut", target=name)

    def hood_outlines(self):
        """J2 두건 단면(x, z) — 바깥(모터 둘레 네모 + MP18 이어서: 57D 단자 혹 셋 뒤 · 위 · 아래, 바깥 모서리 45° 모따기) · 안(속 네모 + 단자 칸 셋).
        단자 칸 = 42D 배치 가정(v2.term57): 뒤(−x) = 모터 커넥터 · 4 단자(띠 ±12.5) · 위 = CAN 단자대 · 아래 = 전원 단자대(띠 ±11.5) — 모터 축에서 42.55 까지.
        hood.pockets = False(대조) 이면 MP18 네모 두건."""
        P = self.P
        s, W = P["v2"]["shoulder"], P["v2"]["wall"]
        h = s["hood"]
        D = P["_drive"]
        hm = D["motor"]["frame"] / 2
        xm = -L.belt_centre(D)
        hd = hm + P["v2"].get("term57", {}).get("driver_excess", 0.0)          # MP18 이어서: 57D 드라이버 가정 폭 — 두건은 드라이버 둘레에 맞춤(밀어 끼울 때 드라이버를 지남)
        hi, ho = hd + h["x_clear"], hd + h["x_clear"] + W
        inner = [box(xm - hi, 174.0 - hi, xm + hi, 174.0 + hi)]
        outer = [box(xm - ho, 174.0 - ho, xm + ho, 174.0 + ho)]
        if "term57" in P["v2"] and h.get("pockets", True):
            t5 = P["v2"]["term57"]
            Rr = hm + t5["driver_excess"] + t5["clearance"] + t5["pocket_gap"]
            bt = t5["band_half"] + t5["pocket_gap"]
            bc = max(t5["band_half"], t5["conn"]["band_half"]) + t5["pocket_gap"]
            c = h["bump_chamfer"]
            inner += [box(xm - Rr, 174.0 - bc, xm - hi + 0.5, 174.0 + bc), box(xm - bt, 174.0 + hi - 0.5, xm + bt, 174.0 + Rr),
                      box(xm - bt, 174.0 - Rr, xm + bt, 174.0 - hi + 0.5)]
            outer += [chamfered_rect(xm - Rr - W, xm - ho + c + 1.0, 174.0 - bc - W, 174.0 + bc + W, c),         # 안쪽 모따기 모서리는 네모 속으로(합친 뒤 안 보임)
                      chamfered_rect(xm - bt - W, xm + bt + W, 174.0 + ho - c - 1.0, 174.0 + Rr + W, c),
                      chamfered_rect(xm - bt - W, xm + bt + W, 174.0 - Rr - W, 174.0 - ho + c + 1.0, c)]
            return unary_union(outer).convex_hull, unary_union(inner), xm, hi, ho          # 바깥 = 혹 셋을 감싼 팔각(십자 앞면 대신 · 2026-11-06 첫 그림) — 속은 칸만
        return unary_union(outer), unary_union(inner), xm, hi, ho

    def motor_hood(self, name="J2_MOTOR_HOOD", face="J2_HOOD_FACE"):
        """J2 모터 끝 두건 — 어깨 판 넓힌 피함 자리를 지나 모터 몸통에 갈비로 끼움(MP17 모터 덮개 방식) · 앞면(남색 · 따로 몸체 · 한 물체로 출력) · 윗면 통풍 홈.
        MP18 이어서(57D 단자 · 케이블): 단자 혹 셋(y 방향 각기둥 · 뒤 끝 열림 = 밀어 끼울 때 단자가 지나감) · 앞을 늘려 드라이버 앞 선 방 ·
        아래 혹 바닥 선 홈(45° 뾰족 · 얼굴을 판에 놓고 뽑으면 위) · 남색 앞면 선 구멍(J2 고리로)."""
        P = self.P
        s = P["v2"]["shoulder"]
        h = s["hood"]
        D = P["_drive"]
        hm = D["motor"]["frame"] / 2
        outer, inner, xm, hi, ho = self.hood_outlines()
        y0, y1 = h["y"]
        yf = y1 - h["front_t"]
        self.prism(name, "y", y0, yf, poly_pts(outer))
        self.prism(f"{name}_IN", "y", y0 - 1.0, yf + 1.0, poly_pts(inner), op="cut", target=name)
        k = 0
        hd = hm + P["v2"].get("term57", {}).get("driver_excess", 0.0)
        d = hi - (hd - h["rib_press"])                                         # 갈비가 벽에서 나온 깊이 — MP18 이어서: 갈비는 드라이버 덮개를 누름(rib_y = 드라이버 구간)
        ry0, ry1 = h["rib_y"]
        ld = h["rib_lead"]
        for o in h["rib_offsets"]:
            for ax, sg in (("x", 1.0), ("x", -1.0), ("z", 1.0), ("z", -1.0)):
                if ax == "x":                                                  # (x, y) 단면 · y 큰 끝 = 45° 경사(얼굴을 판에 놓고 뽑으면 아래쪽)
                    pts = [(xm + sg * (hi + 0.5), ry0), (xm + sg * (hi - d + ld), ry0), (xm + sg * (hi - d), ry0 + ld), (xm + sg * (hi - d), ry1),
                           (xm + sg * (hi + 0.5), ry1 + d + 0.5)]                # y 작은 끝 = 들어가는 쪽 45° 모따기(검토 R1-11f)
                    self.prism(f"{name}_RB{k}", "z", 174.0 + o - h["rib_w"] / 2, 174.0 + o + h["rib_w"] / 2, pts)
                else:
                    pts = [(ry0, 174.0 + sg * (hi + 0.5)), (ry0, 174.0 + sg * (hi - d + ld)), (ry0 + ld, 174.0 + sg * (hi - d)), (ry1, 174.0 + sg * (hi - d)),
                           (ry1 + d + 0.5, 174.0 + sg * (hi + 0.5))]
                    self.prism(f"{name}_RB{k}", "x", xm + o - h["rib_w"] / 2, xm + o + h["rib_w"] / 2, pts)
                self.combine(name, [f"{name}_RB{k}"], "join")
                k += 1
        zt_ = 174.0 + ho + 1.0
        if "term57" in P["v2"] and h.get("pockets", True) and h.get("vent_top", "box") == "hull":     # 검토 R1-5: 팔각(볼록 껍질) 채움 위까지
            t5_ = P["v2"]["term57"]
            zt_ = 174.0 + hm + t5_["driver_excess"] + t5_["clearance"] + t5_["pocket_gap"] + P["v2"]["wall"] + 1.0
        for i, o in enumerate(h["vent_offsets"]):                                # 윗면 통풍 홈(위 단자 혹 · 갈비 밖)
            x = xm + o
            self.box(f"{name}_V{i}", [x - h["vent_w"] / 2, x + h["vent_w"] / 2], [y0 + 8.0, yf - 6.0], [174.0 + hi - 0.5, zt_], op="cut", target=name)
        self.prism(face, "y", yf - 0.02, y1, poly_pts(outer))
        for k_, t_ in enumerate(h.get("face_ties", [])):                       # 검토 R1-2: 남색 앞면 타이 짝(J1 고리 끝 · J2 고리 끝) — 끈은 앞면 바깥으로
            self.tie_pairs(face, "y", yf - 1.0, y1 + 1.0, [tuple(t_["at"])], along=t_["along"], tag=f"F{k_}")
        if "term57" in P["v2"] and h.get("pockets", True):
            t5 = P["v2"]["term57"]
            Rr = hm + t5["driver_excess"] + t5["clearance"] + t5["pocket_gap"]
            es = h["entry_slot"]
            w = es["half_w"]
            ya, yb = es["y"]
            prof = [(xm - w, yb), (xm - w, ya), (xm, ya - w), (xm + w, ya), (xm + w, yb)]          # (x, y) · 낮은 y 끝 45° 뾰족
            self.prism(f"{name}_ENTRY", "z", 174.0 - Rr - P["v2"]["wall"] - 1.0, 174.0 - Rr + 0.5, prof, op="cut", target=name)
        ex = h.get("exit")
        if ex and ex.get("d", 0.0) > 0.0:
            self.cyl(f"{face}_EXIT", "y", yf - 1.0, y1 + 1.0, ex["x"], ex["z"], ex["d"], op="cut", target=face)

    # ---- MP18 바닥 원뿔 겉 · 회전대 띠 · 통 · 링크 5 뚜껑 ----
    def base_skin(self, name="BASE_SKIN", band="BASE_SKIN_BAND"):
        """흰 원뿔 겉(바닥 링크 0) — MP17 BASE 둘레 · 바닥판 위에 서고 바닥판 밑에서 나사 셋 · 민트 띠(한 물체 · 높이 구간 색) · 뒤 아래 케이블 홈."""
        P, g = self.P, self.g
        k = P["v2"]["base_skin"]
        W = P["v2"]["wall"]
        (z0, z1), rb, rt = k["z"], k["r_bottom"], k["r_top"]
        zj = P["j1"]["motor_face_z"]                                                # 세계 z → J1 틀 z(이 부품은 틀 J1)
        a0, a1 = z0 - zj, z1 - zj
        fl_ = k["flange"]                                                      # 밑 안쪽 턱(판에 닿음) — 나사 발은 그 위에 선다(같은 밑면 합치기 · 띄운 벽 모두 피함)
        ri = lambda z: (rb - W) + ((rt - W) - (rb - W)) * (z - a0) / (a1 - a0)  # noqa: E731 — 원뿔 안 반지름
        self.revolve_z(name, [(a0, fl_["r_in"]), (a0, rb), (a1, rt), (a1, rt - W), (a0 + fl_["t"], ri(a0 + fl_["t"])), (a0 + fl_["t"], fl_["r_in"])])
        rtrim = rb + (rt - rb) * k["boss_h"] / (z1 - z0) - k["boss_trim_inset"]    # 발 바깥 = 원뿔 바깥 면(발 꼭대기 높이) 0.3 안에서 자름(검토 R1-9)
        for i, ang in enumerate(k["screw_angles"]):
            x, y = k["screw_r"] * math.cos(math.radians(ang)), k["screw_r"] * math.sin(math.radians(ang))
            foot = circle(x, y, k["boss_r"]).intersection(circle(0.0, 0.0, rtrim, n=720))
            self.prism(f"{name}_B{i}", "z", a0 + fl_["t"] - 0.5, a0 + k["boss_h"], poly_pts(foot))
            self.combine(name, [f"{name}_B{i}"], "join")
        for i, ang in enumerate(k["screw_angles"]):
            x, y = k["screw_r"] * math.cos(math.radians(ang)), k["screw_r"] * math.sin(math.radians(ang))
            self.cyl(f"{name}_BI{i}", "z", a0 - 1.0, a0 + k["insert_depth"], x, y, g["ins"], op="cut", target=name)
        cs = k["cable_slot"]                                                   # 바닥에서 여는 박공 홈(세운 옆 + 45° 지붕) — 평평한 천장 없음
        assert cs["angle"] in (0.0, 180.0), "the gable notch is drawn along x only"
        hw = cs["w"] / 2
        assert abs(cs["apex_h"] - cs["side_h"] - hw) < 1e-6, "45 deg roof: apex_h = side_h + w / 2"
        sx = -1.0 if cs["angle"] == 180.0 else 1.0
        xa, xb = sorted((sx * rb * 0.8, sx * (rb + 2.0)))
        gable = [(-hw, a0 - 1.0), (hw, a0 - 1.0), (hw, a0 + cs["side_h"]), (0.0, a0 + cs["apex_h"]), (-hw, a0 + cs["side_h"])]
        self.prism(f"{name}_CS", "x", xa, xb, gable, op="cut", target=name)
        t_ = k.get("tie")                                                      # MP18 이어서: 뒤 묶음 구멍 짝(겉을 따라 오르는 묶음 · J1 고리의 링크 0 끝)
        if t_:
            assert t_["angle"] == 180.0, "the skin tie is drawn along x only"
            rr_ = rb + (rt - rb) * (t_["z"] - z0) / (z1 - z0)
            self.tie_pairs(name, "x", -(rr_ + 2.0), -(rr_ - W - 2.0), [(0.0, t_["z"] - zj)], along="v")
        (b0, b1) = k["band_z"]
        rr = lambda z: rb + (rt - rb) * (z - z0) / (z1 - z0)                    # noqa: E731 — 원뿔 바깥 반지름
        self.revolve_z(band, [(b0 - zj, rr(b0) - 0.02), (b0 - zj, rr(b0) + k["band_raise"]), (b1 - zj, rr(b1) + k["band_raise"]), (b1 - zj, rr(b1) - 0.02)])
        if z0 + cs["apex_h"] > b0:                                             # 박공 꼭대기가 띠 안으로 → 띠도 같은 꼴로 자름(띠가 홈 위에 떠 있지 않게)
            self.prism(f"{band}_CS", "x", xa, xb, gable, op="cut", target=band)

    def turret_band(self, name="TURRET_BAND"):
        """회전대 남색 띠(링크 1 · 한 물체 · 높이 구간 색)."""
        P = self.P
        tb = P["v2"]["turret_band"]
        zj = P["j1"]["motor_face_z"]
        r = P["j1"]["turret"]["cup_outer_r"]
        z0, z1 = tb["z"][0] - zj, tb["z"][1] - zj
        self.revolve_z(name, [(z0, r - 0.02), (z0, r + tb["raise"]), (z1, r + tb["raise"]), (z1, r - 0.02)])

    def tube(self, name, cap, ring, x_rear, x_front, cover_pts):
        """흰 통(J4 · J6 몸통 둘레) — 뒤판(남색 · 따로 몸체) · 앞 고리(남색 · 따로 몸체) · +y 홈(링크 판) · 뒤판 나사 구멍(몸통 뒤 덮개 나사) · 케이블 구멍."""
        P = self.P
        t = P["v2"]["tubes"]
        ri, ro = t["r_in"], t["r_in"] + t["wall"]
        xp = x_rear - t["plate_t"]
        self.cyl(name, "x", x_rear - 0.02, x_front - t["ring_len"], 0.0, 174.0, 2 * ro)      # 통이 뒤판에 0.02 겹침(뒤판은 덮개 면에서 멈춤)
        self.cyl(f"{name}_IN", "x", x_rear - 1.0, x_front + 1.0, 0.0, 174.0, 2 * ri, op="cut", target=name)
        self.cyl(cap, "x", xp, x_rear, 0.0, 174.0, 2 * ro)
        self.cyl(ring, "x", x_front - t["ring_len"] - 0.02, x_front, 0.0, 174.0, 2 * ro)
        self.cyl(f"{ring}_IN", "x", x_front - t["ring_len"] - 1.0, x_front + 1.0, 0.0, 174.0, 2 * ri, op="cut", target=ring)
        (sy0, sy1), (sz0, sz1) = t["slot_y"], t["slot_z"]
        for nm in (name, cap, ring):
            self.box(f"{nm}_SLOT", [xp - 1.0, x_front + 1.0], [sy0, sy1], [sz0, sz1], op="cut", target=nm)
        for i, (y, z) in enumerate(cover_pts):
            self.cyl(f"{cap}_S{i}", "x", xp - 1.0, x_rear + 1.0, y, z, t["cover_screw_clear"], op="cut", target=cap)
        ch = t["cable_hole"]
        if "arc_deg" in ch:                                                    # 검토 R1-11: 통 틈을 따라 원호 홈(선이 나란히 지남)
            self.prism(f"{cap}_CH", "x", xp - 1.0, x_rear + 1.0, poly_pts(tube_cable_slot(P, name)), op="cut", target=cap)
        else:
            if "phi_deg" in ch:                                                # MP18 이어서: 통 틈(r 39 ~ 48.5) 안 · 묶음이 오는 각
                ph_ = math.radians(ch["phi_deg"][name])
                cy_, cz_ = ch["r"] * math.cos(ph_), 174.0 + ch["r"] * math.sin(ph_)
            else:
                cy_, cz_ = ch["y"], ch["z"]
            self.cyl(f"{cap}_CH", "x", xp - 1.0, x_rear + 1.0, cy_, cz_, ch["d"], op="cut", target=cap)
        ft = t.get("front_tie", {}).get(name)                                  # 검토 R1-2: 통 앞 타이 짝(선을 벽에 붙여 묶음 · 끈은 통 바깥으로) — 반지름 방향(통에 접한 스케치)
        if ft:
            xt = x_front - ft["x_from_front"]
            ph_ = math.radians(ft["phi_deg"])
            ca, sa = math.cos(ph_), math.sin(ph_)
            r0, r1 = ro + 1.0, ri - 0.5
            sl, sw = P["ties"]["slot"]
            pt = P["ties"]["pitch"] / 2
            for j, sg in enumerate((1.0, -1.0)):                               # 스케치 u = 세계 x · v = 접선(−sin, cos) · 법선 = 안쪽
                prof = [(xt - sl / 2, sg * pt - sw / 2), (xt + sl / 2, sg * pt - sw / 2), (xt + sl / 2, sg * pt + sw / 2), (xt - sl / 2, sg * pt + sw / 2)]
                self.cmd("sketch.create", name=f"{name}_TIEF{j}_SK", plane={"origin": [0.0, r0 * ca, 174.0 + r0 * sa], "x_dir": [1.0, 0.0, 0.0], "y_dir": [0.0, -sa, ca]})
                self.cmd("sketch.line", points=[[round(a_, 5), round(b_, 5)] for a_, b_ in prof], closed=True)
                self.cmd("sketch.finish")
                self.cmd("solid.extrude", distance=float(r0 - r1), direction="positive", operation="cut", targets=[name], name=f"{name}_TIEF{j}_X")
        vt = t["vents"]                                                        # 통풍 홈 — −y 쪽(+y 쪽은 판 홈으로 열림)
        for i in range(vt["n"]):
            z = 174.0 + (i - (vt["n"] - 1) / 2) * vt["z_pitch"]
            self.box(f"{name}_V{i}", [x_rear + vt["x_from_rear"][0], x_rear + vt["x_from_rear"][1]], [-ro - 1.0, -ri + 1.0], [z - vt["w"] / 2, z + vt["w"] / 2],
                     op="cut", target=name)

    def ua_outline(self, off=0.0):
        """MP18 위팔 상자 윤곽(x, z) — J2 끝 원 · 막대 · J3 끝 원의 합. off < 0 = 안쪽으로."""
        u = self.P["v2"]["upper_arm"]
        hb = u["bar_half_z"]
        geom = unary_union([circle(0.0, 174.0, u["j2_end_r"], n=240), box(0.0, 174.0 - hb, 165.0, 174.0 + hb), circle(165.0, 174.0, u["j3_end_r"], n=240)])
        return geom.buffer(off, join_style=1, resolution=16) if off else geom

    def ua_rib_points(self):
        """덮개 나사 자리(상자 인서트) — (x, z, 온전한 단면이 시작하는 y, 바깥 방향 또는 None).
        J2 끝 기둥 셋 = 판에서(x < 29 — J3 바닥판 날개 · 모터 밖). J3 끝 갈비(cover_ribs)는 기본 없음 — r 59 갈비가 J3 모듈이 앞으로 들어오는 길을 막았다
        (검토 R1-1 · 대조 ua_j3_ribs_back 만 씀). J3 끝 덮개 나사 = 받침대 기둥(j3_bracket_points)."""
        u = self.P["v2"]["upper_arm"]
        out = [(x, z, u["plate_y"][1], None) for x, z in u["cover_posts_xz"]]
        out += [(r["at"][0], r["at"][1], u["rib_from_y"], r["out"]) for r in u["cover_ribs"]]
        return out

    def j3_bracket_points(self):
        """MP18 검토 R1-1: J3 끝 덮개 받침대 — 귀 셋(MP16 J3 벨트 덮개 인서트 · 세계 x, z) · 기둥 셋(덮개 나사 · 세계 x, z) · 바닥판 밑면(벨트 쪽 면) 세계 y."""
        P = self.P
        gd, bk = P["_drive"]["guard"], P["v2"]["j3_bracket"]
        Fr = L.frames(P)
        tabs = []
        for a in gd["tab_angles_deg"]:
            w = Fr["M3"] @ [gd["tab_radius"] * math.cos(math.radians(a)), gd["tab_radius"] * math.sin(math.radians(a)), 0.0, 1.0]
            tabs.append((float(w[0]), float(w[2])))
        posts = [(165.0 + bk["post_r"] * math.cos(math.radians(a)), 174.0 + bk["post_r"] * math.sin(math.radians(a))) for a in bk["post_angles_deg"]]
        return tabs, posts, float((Fr["M3"] @ [0.0, 0.0, 0.0, 1.0])[1])

    def j3_bracket_plan(self, raw=False):
        """받침대 판(x, z) — J3 축 둘레 부채꼴 띠(벨트 반대쪽 · −125° ~ 125°) + 귀 자리 + 기둥 자리(기둥보다 작게).
        조각이 갈라지면(대조 판 — 모듈을 안 돌림 · 기둥을 밖으로) 볼록 껍질로 이어 만들게 한다 · 본판이 한 조각인지는 한계식 j3_bracket_plan_one_piece(raw=True)."""
        bk = self.P["v2"]["j3_bracket"]
        tabs, posts, _y = self.j3_bracket_points()
        (r0, r1), (a0, a1) = bk["arc_r"], bk["arc_deg"]
        n = 96
        arc = lambda r, s, e: [(165.0 + r * math.cos(math.radians(s + (e - s) * i / n)), 174.0 + r * math.sin(math.radians(s + (e - s) * i / n))) for i in range(n + 1)]  # noqa: E731
        band = Polygon(arc(r1, a0, a1) + arc(r0, a1, a0))
        pads = [circle(x, z, bk["tab_pad_r"]) for x, z in tabs] + [circle(x, z, bk["post_pad_r"]) for x, z in posts]
        g_ = unary_union([band] + pads).buffer(0)
        if raw or g_.geom_type == "Polygon":
            return g_
        return g_.convex_hull                                                  # 대조 판에서만(2026-11-06 대조 j3_turn_zero · j3_bracket_post_out 이 「outline not one polygon」 으로 안 만들어짐)

    def ua_j3_bracket(self, name="UA_J3_BRACKET"):
        """MP18 검토 R1-1: J3 끝 덮개 받침대(따로 출력 · −y 면이 판) — 판(바닥판 벨트 쪽 면 위 · 두께 t) + 기둥 셋(덮개 안쪽 면까지 · 꼭대기 인서트).
        귀 셋 = MP16 J3 벨트 덮개 인서트에 그 덮개 나사 M3 × 8(2d 그대로 — v2 는 벨트 덮개를 뽑지 않음). 모듈을 상자에 넣은 뒤 앞에서 넣어 조인다."""
        P, g = self.P, self.g
        bk, u = P["v2"]["j3_bracket"], P["v2"]["upper_arm"]
        tabs, posts, yf = self.j3_bracket_points()
        t, yt = bk["t"], u["wall_top_y"]
        self.prism(name, "y", yf, yf + t, poly_pts(self.j3_bracket_plan()))
        for i, (x, z) in enumerate(posts):
            self.cyl(f"{name}_P{i}", "y", yf + t - 0.5, yt, x, z, bk["post_d"])
            self.combine(name, [f"{name}_P{i}"], "join")
            self.cyl(f"{name}_PI{i}", "y", yt - bk["insert_depth"], yt + 1.0, x, z, g["ins"], op="cut", target=name)
        for i, (x, z) in enumerate(tabs):
            self.cyl(f"{name}_TH{i}", "y", yf - 1.0, yf + t + 1.0, x, z, g["m3"], op="cut", target=name)

    def upper_arm(self, name="UPPER_ARM"):
        """MP18 위팔 — 뒤 판(MP17 판 자리 · y 52 ~ 59) + 둘레 벽(y 170 까지) = 앞이 열린 상자. J3 모듈은 앞에서 넣고 뒤에서 나사(MP17 과 같음) ·
        J3 모터(모듈을 90° 돌려 J2 쪽)는 판의 창을 지나 상자 안에. 덮개(UA_COVER)가 앞을 닫는다."""
        P, g = self.P, self.g
        u = P["v2"]["upper_arm"]
        ua = P["j3"]["upper_arm"]
        y0, y1 = u["plate_y"]
        yt = u["wall_top_y"]
        W = P["v2"]["wall"]
        self.prism(name, "y", y0, yt, poly_pts(self.ua_outline()))
        self.prism(f"{name}_IN", "y", y1, yt + 1.0, poly_pts(self.ua_outline(-W)), op="cut", target=name)
        b_ = u["boss_r"]
        for i, (x, z, ya, out_) in enumerate(self.ua_rib_points()):            # 덮개 나사 기둥 · 갈비(벽과 하나) + 인서트 구멍
            if out_ is None:
                self.cyl(f"{name}_RIB{i}", "y", ya - 0.5, yt, x, z, 2 * b_)
            else:                                                              # 네모 갈비 + 벽 쪽 45° 받침(가장 낮은 곳이 바깥 벽)
                w_ = u["rib_wedge"]
                sg = 1.0 if out_[0] == "+" else -1.0
                if out_[1] == "x":
                    self.prism(f"{name}_RIB{i}", "z", z - b_, z + b_, [(x - sg * b_, ya), (x + sg * b_, ya - w_), (x + sg * b_, yt), (x - sg * b_, yt)])
                else:
                    self.prism(f"{name}_RIB{i}", "x", x - b_, x + b_, [(ya, z - sg * b_), (ya - w_, z + sg * b_), (yt, z + sg * b_), (yt, z - sg * b_)])
            self.combine(name, [f"{name}_RIB{i}"], "join")
            self.cyl(f"{name}_RI{i}", "y", yt - u["insert_depth"], yt + 1.0, x, z, g["ins"], op="cut", target=name)
        self.cyl(f"{name}_HOLE", "y", y0 - 1.0, y1 + 1.0, 165.0, 174.0, 2 * ua["hole_r"], op="cut", target=name)
        vt = u["vents"]                                                        # 통풍 홈 — 위 · 아래 벽(J3 모터 몸통 위)
        hb = u["bar_half_z"]
        for i in range(vt["n"]):
            x = vt["x"][0] + (vt["x"][1] - vt["x"][0]) * i / max(1, vt["n"] - 1)
            for k, zc in enumerate((174.0 - hb, 174.0 + hb)):
                self.box(f"{name}_V{i}{k}", [x - vt["w"] / 2, x + vt["w"] / 2], vt["y"], [zc - W - 1.0, zc + W + 1.0], op="cut", target=name)
        D = P["_drive"]
        hm0 = D["motor"]["frame"] / 2
        hx, hm = hm0 + u.get("motor_window_clear_x", u["motor_window_clear"]), hm0 + u["motor_window_clear"]      # MP18 이어서: x 쪽 = 57D 드라이버 가정 폭 + 벨트 이동
        xm = 165.0 - L.belt_centre(D)                                         # 돌린 J3 모터 축(세계 x)
        self.box(f"{name}_MWIN", [xm - hx, xm + hx], [y0 - 1.0, y1 + 1.0], [174.0 - hm, 174.0 + hm], op="cut", target=name)
        if "term57" in P["v2"]:                                               # MP18 이어서: J3 57D 단자 칸 판 홈(위 · 아래 · J2 쪽) + 선 출구(아래 홈과 합침)
            t5 = P["v2"]["term57"]
            Rr = hm0 + t5["driver_excess"] + t5["clearance"] + t5["pocket_gap"]
            bt = t5["band_half"] + t5["pocket_gap"]
            ex0, ex1 = u["notches"]["exit_x"]
            top_exit = u["notches"].get("exit_side", "bottom") == "top"           # 선 출구를 합칠 홈(위 = J2 · J3 범위를 막지 않음 — 2026-11-06 첫 전체 검사)
            tr = u["notches"].get("travel", 0.0)                               # 검토 R1-4: 모터가 벨트 홈(±2.5) 어느 끝에 가도 단자 어림이 판에 닿지 않게
            btx = bt + tr
            tx = [min(ex0, xm - btx), max(ex1, xm + btx)] if top_exit else [xm - btx, xm + btx]
            bx_ = [xm - btx, xm + btx] if top_exit else [min(ex0, xm - btx), max(ex1, xm + btx)]
            yb = y1 + 0.5
            self.box(f"{name}_NT_TOP", tx, [y0 - 1.0, yb], [174.0 + hm - 1.0, 174.0 + Rr], op="cut", target=name)
            self.box(f"{name}_NT_BOT", bx_, [y0 - 1.0, yb], [174.0 - Rr, 174.0 - hm + 1.0], op="cut", target=name)
            self.box(f"{name}_NT_J2", [xm - Rr - tr, xm - hx + 1.0], [y0 - 1.0, yb], [174.0 - bt, 174.0 + bt], op="cut", target=name)
            je = u["j2_entry"]
            if je.get("d", 0.0) > 0.0:                                         # J2 끝 벽 선 입구(반지름 방향 · +y 쪽 45° 뾰족 — 판을 바닥에 두고 뽑음)
                ph_ = math.radians(je["phi_deg"])
                ca, sa = math.cos(ph_), math.sin(ph_)
                r0, r1 = u["j2_end_r"] - W - 1.5, u["j2_end_r"] + 1.5
                w, yc = je["d"] / 2, je["y"]
                prof = [(-w, yc - w), (w, yc - w), (w, yc + w), (0.0, yc + 2 * w), (-w, yc + w)]
                self.cmd("sketch.create", name=f"{name}_J2E_SK", plane={"origin": [r0 * ca, 0.0, 174.0 + r0 * sa], "x_dir": [sa, 0.0, -ca], "y_dir": [0.0, 1.0, 0.0]})
                self.cmd("sketch.line", points=[[round(a_, 5), round(b_, 5)] for a_, b_ in prof], closed=True)
                self.cmd("sketch.finish")
                self.cmd("solid.extrude", distance=float(r1 - r0), direction="positive", operation="cut", targets=[name], name=f"{name}_J2E_X")
            for tg_, it in (("", u["inner_tie"]), ("J2", u.get("j2_tie"))):     # 안 묶음 구멍 짝 — J3 고리 위팔 끝(출구 쪽) · J2 고리 위팔 끝(검토 R1-2)
                if not it:
                    continue
                if it.get("side", "bottom") == "top":
                    self.tie_pairs(name, "z", 174.0 + u["bar_half_z"] - W - 0.5, 174.0 + u["bar_half_z"] + 1.0, [(it["x"], it["y"])], along="h", tag=tg_)
                else:
                    self.tie_pairs(name, "z", 174.0 - u["bar_half_z"] - 1.0, 174.0 - u["bar_half_z"] + W + 0.5, [(it["x"], it["y"])], along="h", tag=tg_)
        ph = u["j3_stand_phase_deg"] + P["j3"]["module_turn_deg"]
        for i, a in enumerate(ph + 60 * k for k in range(6)):                 # J3 덮개 윗면 인서트(모듈과 함께 돈 자리)
            x, z = 165.0 - 53.5 * math.sin(math.radians(a)), 174.0 + 53.5 * math.cos(math.radians(a))
            self.cyl(f"{name}_JS{i}", "y", y0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_JB{i}", "y", y0 - 1.0, y0 + ua["j3_cbore"][1], x, z, ua["j3_cbore"][0], op="cut", target=name)
        for i, a in enumerate(60 * k for k in range(6)):
            x, z = -22.0 * math.cos(math.radians(a)), 174.0 + 22.0 * math.sin(math.radians(a))
            self.cyl(f"{name}_HS{i}", "y", y0 - 1.0, y1 + 1.0, x, z, g["m3c"], op="cut", target=name)
            self.cyl(f"{name}_HB{i}", "y", y1 - ua["j2_cbore"][1], y1 + 1.0, x, z, ua["j2_cbore"][0], op="cut", target=name)

    def ua_cover(self, name="UA_COVER"):
        """MP18 위팔 앞 덮개(y 170 ~ 173) — 상자 윤곽 · 바깥 모서리 모따기 · 덮개 나사 · 남색 뚜껑 자리(핀 구멍) · KMJH 글자는 따로(돋움)."""
        P, g = self.P, self.g
        u, cp = P["v2"]["upper_arm"], P["v2"]["caps"]
        y0, t, c = u["wall_top_y"], u["cover_t"], u["cover_edge_chamfer"]
        self.prism(name, "y", y0, y0 + t - c, poly_pts(self.ua_outline()))
        self.prism(f"{name}_TOP", "y", y0 + t - c - 0.5, y0 + t, poly_pts(self.ua_outline(-c)))
        self.combine(name, [f"{name}_TOP"], "join")
        pts_ = [(x, z) for x, z, _ya, _o in self.ua_rib_points()] + self.j3_bracket_points()[1]     # 상자 기둥 · (대조의) 갈비 + J3 받침대 기둥
        for i, (x, z) in enumerate(pts_):
            self.cyl(f"{name}_S{i}", "y", y0 - 1.0, y0 + t + 1.0, x, z, g["m3"], op="cut", target=name)
            self.cyl(f"{name}_SB{i}", "y", y0 + t - 1.65 - 0.2, y0 + t + 1.0, x, z, 6.5, op="cut", target=name)
        for tag, cx, r in (("J2", 0.0, cp["j2_r"]), ("J3", 165.0, cp["j3_r"])):
            self.cyl(f"{name}_R{tag}", "y", y0 + t - cp["recess"], y0 + t + 1.0, cx, 174.0, 2 * (r + cp["recess_clear"]), op="cut", target=name)
            for k in range(3):                                                  # 핀은 덮개 자리 바닥에서 위로(뚜껑에는 막힌 구멍)
                a = math.radians(90.0 + 120.0 * k)
                rr = r * cp["pin_r_fracs"][k]
                self.cyl(f"{name}_P{tag}{k}", "y", y0 + t - cp["recess"] - 0.5, y0 + t - cp["recess"] + cp["pin_h"], cx + rr * math.cos(a), 174.0 + rr * math.sin(a), cp["pin_d"])
                self.combine(name, [f"{name}_P{tag}{k}"], "join")

    def cap_v2(self, name, cx, r, y_seat, holes=True):
        """MP18 남색 끝 뚜껑 — 자리(깊이 recess)에 앉는 원판 + 바깥 모따기 · 밑면 막힌 구멍 셋(덮개 핀에 눌러 끼움 · 떼어 정비). holes=False = 핀 없는 자리(접착)."""
        cp = self.P["v2"]["caps"]
        t, c = cp["t"], cp["chamfer"]
        prof = [(y_seat, 0.0), (y_seat, r), (y_seat + t - c, r), (y_seat + t, r - c), (y_seat + t, 0.0)]
        self.revolve_y(name, cx, 174.0, prof)
        if not holes:
            return
        for k in range(3):
            a = math.radians(90.0 + 120.0 * k)
            rr = r * cp["pin_r_fracs"][k]
            self.cyl(f"{name}_H{k}", "y", y_seat - 0.5, y_seat + cp["hole_depth"], cx + rr * math.cos(a), 174.0 + rr * math.sin(a), cp["pin_d"] + cp["pin_hole_extra"],
                     op="cut", target=name)

    def logo_v2(self, name="UA_LOGO"):
        """KMJH 글자(MP7 kmjh_logo.py 를 읽기만) — 위팔 앞 덮개(+y) 면에 돋움 · +y 에서 바로 읽히게."""
        sys.path.insert(0, str(ROOT / "src" / "cad" / "armold-mks-product-v3"))
        import kmjh_logo                                                       # noqa: PLC0415 (MP7 — 읽기만)
        P = self.P
        lg, u = P["v2"]["logo"], P["v2"]["upper_arm"]
        rows, width = kmjh_logo.letters()
        h = lg["height"]
        y0 = u["wall_top_y"] + u["cover_t"]
        pl, f = self.plane("y", y0 - 0.02)
        self.cmd("sketch.create", name=f"{name}_SK", plane=pl)
        for _n, _role, pts in rows:
            loop = [f(lg["centre_x"] + (width / 2 - uu) * h, 174.0 + (v - 0.5) * h) for uu, v in pts][::-1]
            self.cmd("sketch.line", points=[[round(float(a), 5), round(float(b), 5)] for a, b in loop], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(lg["raise"] + 0.02), direction="positive", operation="new", body_name=name, name=f"{name}_X")
        if len(rows) > 1 and lg.get("join_letters", True):                    # 글자 고리마다 몸체가 하나씩 생김(「UA_LOGO (2)」 …) — 합쳐야 STL 에 다 들어감
            self.combine(name, [f"{name} ({k})" for k in range(2, len(rows) + 1)], "join")      # (MP17 은 첫 글자만 저장됨 — 2026-11-06 MP18 시험 생성에서 찾음)

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
        for i, a in enumerate(P["j3"]["module_turn_deg"] + 60 * k for k in range(6)):    # MP18: 캐리어 · 출력 플랜지도 모듈과 함께 돈 자리
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
        tb_ = l5.get("tab")
        if tb_:                                                                # MP18 이어서: J5 쪽 귀(묶음 구멍 짝 · J5 고리의 링크 5 끝)
            outline = unary_union([outline, chamfered_rect(x5 + tb_["x_from_j5"][0], x5 + tb_["x_from_j5"][1], 174.0 - tb_["z_half"], 174.0 + tb_["z_half"], tb_["chamfer"])])
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
        if tb_:
            self.tie_pairs(name, "y", y0 - 1.0, y1 + 1.0, [(x5 + tb_["tie_x_from_j5"], 174.0)], along="h")
        cpv, c5 = P["v2"]["caps"], P["v2"]["link5_cap"]                       # MP18: 남색 뚜껑(+y 면 · J5 허브 나사 위)
        if c5["recess"] > 0:                                                   # 검토 R1-10: 기본은 자리 없음(판에 놓는 면의 넓은 천장) — 평면에 양면테이프
            x5c = float(L.joint_origins_q0(P)["J5"][0])
            self.cyl(f"{name}_CAPR", "y", y1 - c5["recess"], y1 + 1.0, x5c, 174.0, 2 * (c5["r"] + cpv["recess_clear"]), op="cut", target=name)

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

    def tie_pairs(self, name, axis, a, b, centres, along, tag=""):
        """케이블 타이 구멍 짝(MP10 목 크기 4.5 × 2.4) — centres = 짝 가운데(판 좌표) · along h = 다발이 가로(x)로 · v = 세로(z)로."""
        sl, sw = self.P["ties"]["slot"]
        pt = self.P["ties"]["pitch"] / 2
        for i, (u, v) in enumerate(centres):
            for j, sg in enumerate((1.0, -1.0)):
                if along == "h":                                            # 다발 가로 → 구멍 긴 변 가로 · 짝은 세로로 벌림
                    pts = [(u - sl / 2, v + sg * pt - sw / 2), (u + sl / 2, v + sg * pt - sw / 2), (u + sl / 2, v + sg * pt + sw / 2), (u - sl / 2, v + sg * pt + sw / 2)]
                else:
                    pts = [(u + sg * pt - sw / 2, v - sl / 2), (u + sg * pt + sw / 2, v - sl / 2), (u + sg * pt + sw / 2, v + sl / 2), (u + sg * pt - sw / 2, v + sl / 2)]
                self.prism(f"{name}_TIE{tag}{i}{j}", axis, a, b, pts, op="cut", target=name)

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
        ya, yb = sorted((y_face - sgn * self.P["v2"]["caps"].get("mark_embed", 0.02), y_face + sgn * raise_))      # 대조 mark_floating = 음수(면 위에 뜸)
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
    cp = P["style"]["cap"]
    fa_y0 = P["j3"]["forearm"]["plate_y"][0]
    x3 = float(L.joint_origins_q0(P)["J3"][0])
    sc.cap("J3_CAP", x3, fa_y0, -1)                                            # 아래팔 −y 면(뒤) 위에 바로 — MP17 그대로
    m = cp["mark"]
    sc.mark("J3_CAP_MARK", x3, fa_y0 - cp["t"], -1, m["h"], m["w"], m["raise"])
    sc.ua_cover()                                                               # MP18 위팔 앞 덮개 + 남색 뚜껑 둘 + 사선 + KMJH
    u2, c2 = P["v2"]["upper_arm"], P["v2"]["caps"]
    ys = u2["wall_top_y"] + u2["cover_t"] - c2["recess"]
    sc.cap_v2("UA_CAP_J2", 0.0, c2["j2_r"], ys)
    sc.cap_v2("UA_CAP_J3", x3, c2["j3_r"], ys)
    m2 = c2["mark"]
    sc.mark("UA_CAP_J2_MARK", 0.0, ys + c2["t"], +1, m2["h"], m2["w"], m2["raise"])
    sc.mark("UA_CAP_J3_MARK", x3, ys + c2["t"], +1, m2["h"], m2["w"], m2["raise"])
    sc.logo_v2()
    sc.ua_j3_bracket()                                                          # 검토 R1-1: J3 끝 덮개 받침대
    sc.shoulder_shroud()
    sc.motor_hood()
    sc.base_skin()
    sc.turret_band()
    sp_ = sc.s
    Fr_ = L.frames(P)
    for tag, cap_, ring_, fr in (("FA_TUBE", "FA_TUBE_CAP", "FA_TUBE_RING", "C4"), ("J6_TUBE", "J6_TUBE_CAP", "J6_TUBE_RING", "C6")):
        M = Fr_[fr]
        xr = float((M @ [0.0, 0.0, sp_.z_rear, 1.0])[0])                       # 몸통 뒤 덮개 바깥 면(세계 x) — 커버 두께 만큼 뒤
        xf = float((M @ [0.0, 0.0, 0.0, 1.0])[0])                              # 모터 앞면 = 몸통 앞 끝
        cv = [(M @ [sp_.cover["r"] * math.cos(math.radians(a)), sp_.cover["r"] * math.sin(math.radians(a)), sp_.z_rear, 1.0])[1:3] for a in sp_.cover["angles"]]
        sc.tube(tag, cap_, ring_, xr - sp_.cover["t"], xf, [(float(y), float(z)) for y, z in cv])
    c5 = P["v2"]["link5_cap"]
    x5 = float(L.joint_origins_q0(P)["J5"][0])
    y5 = P["link5"]["plate_y"][1]
    cpv = P["v2"]["caps"]
    sc.cap_v2("LINK5_CAP", x5, c5["r"], y5 - c5["recess"], holes=False)
    sc.mark("LINK5_CAP_MARK", x5, y5 - c5["recess"] + cpv["t"], +1, c5["mark"]["h"], c5["mark"]["w"], c5["mark"]["raise"])
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
    rec = {"what": "MP18 팔 전체 v2 새 부품 만들기 기록 — 이 sha 와 지금 파일이 같아야 검사가 지금 형상을 본 것이다", "control": a.control,
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
