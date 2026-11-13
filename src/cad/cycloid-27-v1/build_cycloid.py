# -*- coding: utf-8 -*-
"""MP6 — 사이클로이드 27:1 시제품(손목 크기)의 형상(SolidCraft 명령) · 조립 간섭 · 구멍 탐침 · 부품 STL · 맞춤 확인 판 · 와셔 · 게이지.

좌표: z = 감속기 축 · 모터 면 z = 0 · 출력 쪽 +z. 쌓임 · 반지름 · 원판 자세 · 윤곽은 `cycloid.py`(stack · radii · disc_pose · profile_for)에서
가져온다 — 수치의 권위는 그 모듈과 parameters.json 이다. 입력 각 θ 에서 원판 1 중심 = (E cos θ, E sin θ) · 원판 2 = 반대 · 출력(캐리어) = −θ/27(명목).
원판 2 는 원판 1 과 같은 부품을 자기 중심에서 180° 돌려 끼운다(27 로브는 180° 대칭이 아니다 — 그 돌림이 곧 반대 편심에 필요한 반 로브 어긋남).
편심 축은 둘(아래 = 허브 + 편심 1 · 위 = 간격 고리 + 편심 2 + 저널) — 모터 D 축이 둘의 180° 관계를 정한다.

사용: python build_cycloid.py --cli <solidcraft-cli.exe> --out <models 폴더> --evidence <폴더> --scratch <무거운 STL 폴더> [--theta 0 45 90]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cycloid import disc_pose, load_params, profile_for, radii, stack  # noqa: E402

CONTACT_MM = 1e-3          # 간섭 상자의 가장 얇은 변이 이보다 얇으면 닿음(같은 면의 접촉)
MESH_CONTACT_MM3 = 0.01    # 메시 교차로 가를 때 닿음의 상한(MP4 와 같은 값)
REF_PIN_SHRINK = 0.04      # 압입 구멍(바닥판 고정 핀 · 캐리어 출력 핀)의 기준 핀 지름 = 구멍 − 이것: 같은 반지름 원통 둘의 STL 다각형 오차(2026-10-24 핀마다
                           # 약 0.96 mm³ — 원 출력은 덮어써 없음 · 재현값 = .dev/cycloid-27-evidence/source-records.json 의 same_radius_pin)를 간섭으로
                           # 세지 않게(`verify_geometry.references()`). 압입이 아닌 부품에는 실제 핀 지름 · 원판 ↔ 핀 틈의 권위는 cycloid.py 의 기구학


class SC:
    def __init__(self):
        self.commands = []
        self.holes = []    # 구멍 탐침용: (몸체, x, y, z0, h, 지름, 막힌 끝 쪽 "below" | "above" | None, 이름)
        self.shapes = {}   # 단면 검사용: (몸체, 이름) → 선언한 단면(원 반지름 · D 의 반지름 · 평면 거리 · 평면 방향)
        self.entries = {}  # (몸체, 이름) → 구매 부품이 들어오는 쪽 "up"(+z) · "down"(−z) · "both" — 그 길이 부품 밖까지 비어야 한다(MP6 L4-N2 F1)
        self.bosses = []   # 베어링 속 고리가 끼는 축: (몸체, x, y, z0, h, 반지름, 이름, 베어링 키) — 형상 명령은 따로

    def boss(self, body, cx, cy, z0, h, r, tag, bearing):
        self.bosses.append((body, float(cx), float(cy), float(z0), float(h), float(r), tag, bearing))

    def declare_hole(self, body, cx, cy, z0, h, dia, tag, floor=None, entry=None):
        """회전 윤곽 등으로 이미 생긴 구멍을 검사 목록에만 올린다(형상 명령 없음) — 구매 부품과 맞닿는 면은 모두 선언한다(MP6 L4-N1 F2)."""
        self.holes.append((body, float(cx), float(cy), float(z0), float(h), float(dia), floor, tag))
        self.shapes[(body, tag)] = {"kind": "circle", "r": float(dia) / 2}
        self.entries[(body, tag)] = self._entry(floor, entry)

    def cmd(self, c, **p):
        self.commands.append({"command": c, "params": p})

    def revolve_z(self, name, prof, cx=0.0, cy=0.0):
        """z 축(중심 (cx, cy))을 도는 회전체 — prof = [(z, r), ...] 닫힌 윤곽."""
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": [float(cx), float(cy), 0.0], "x_dir": [0, 0, 1], "y_dir": [1, 0, 0]})
        self.cmd("sketch.line", points=[[float(u), float(v)] for u, v in prof], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.revolve", axis="x", operation="new", body_name=name, name=name + "_REVOLVE")

    def cyl(self, name, r, z0, h, cx=0.0, cy=0.0):
        self.cmd("solid.cylinder", radius=float(r), height=float(h), base=[float(cx), float(cy), float(z0)], axis="Z", operation="new",
                 body_name=name, name=name + "_C")

    @staticmethod
    def _entry(floor, entry):
        return entry or {"below": "up", "above": "down"}.get(floor, "both")

    def hole(self, body, cx, cy, z0, h, dia, tag, floor=None, entry=None):
        """z0 에서 +z 로 높이 h 의 원통 구멍. floor = 막힌 끝이 있는 쪽("below" = z0 아래 · "above" = z0 + h 위)에 재료가 남아야 하는 막힌 구멍.
        entry = 들어오는 쪽(없으면 막힌 끝의 반대 · 관통은 양쪽)."""
        self.entries[(body, tag)] = self._entry(floor, entry)
        self.cmd("sketch.create", name=f"{body}_H_{tag}", plane={"origin": [float(cx), float(cy), float(z0)], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})
        self.cmd("sketch.circle.center", center=[0, 0], radius=float(dia) / 2)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(h), direction="positive", operation="cut", targets=[body], name=f"{body}_HOLE_{tag}")
        self.holes.append((body, float(cx), float(cy), float(z0), float(h), float(dia), floor, tag))
        self.shapes[(body, tag)] = {"kind": "circle", "r": float(dia) / 2}

    def d_hole(self, body, cx, cy, z0, h, dia, flat_to_axis, ang, tag):
        """D 모양 관통 구멍(지름 dia · 평면이 축에서 flat_to_axis · 평면 방향 ang)."""
        r = dia / 2
        a0 = math.acos(flat_to_axis / r)
        pts = [[r * math.cos(t + ang), r * math.sin(t + ang)] for t in np.linspace(a0, 2 * math.pi - a0, 72)]
        self.cmd("sketch.create", name=f"{body}_D_{tag}", plane={"origin": [float(cx), float(cy), float(z0)], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})
        self.cmd("sketch.line", points=pts, closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(h), direction="positive", operation="cut", targets=[body], name=f"{body}_DHOLE_{tag}")
        self.holes.append((body, float(cx), float(cy), float(z0), float(h), 2 * float(flat_to_axis), None, tag))
        self.shapes[(body, tag)] = {"kind": "d", "r": float(r), "flat": float(flat_to_axis), "ang": float(ang)}
        self.entries[(body, tag)] = "both"

    def poly_extrude(self, name, pts, z0, h, origin, x_dir):
        self.cmd("sketch.create", name=name + "_P", plane={"origin": [float(origin[0]), float(origin[1]), float(z0)],
                                                         "x_dir": [float(x_dir[0]), float(x_dir[1]), 0.0], "y_dir": [-float(x_dir[1]), float(x_dir[0]), 0.0]})
        self.cmd("sketch.line", points=[[round(float(u), 5), round(float(v), 5)] for u, v in pts], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(h), direction="positive", operation="new", body_name=name, name=name + "_X")


def ring(n, r, phase):
    return [(r * math.cos(phase + 2 * math.pi * i / n), r * math.sin(phase + 2 * math.pi * i / n)) for i in range(n)]


def rotxy(u, v, a):
    return u * math.cos(a) - v * math.sin(a), u * math.sin(a) + v * math.cos(a)


def build(P, profile, theta_deg):
    sc = SC()
    z, r = stack(P), radii(P)
    rp, op, fits, B, m, car, hs = P["ring"], P["output_pins"], P["fits"], P["bearings"], P["motor"], P["carrier"], P["housing"]
    N, E = rp["pins"], P["eccentricity"]
    th = math.radians(theta_deg)
    phi = -th / (N - 1)                       # 캐리어(출력) 각 — 명목
    pins = ring(N, r["ring"], math.radians(rp["pin_phase_deg"]))
    hb = m["bolt_square"] / 2
    bolts = [(sx * hb, sy * hb) for sx in (-1, 1) for sy in (-1, 1)]
    parts, refs = [], []

    # ---- 아래 하우징: 바닥판(파일럿 · 모터 나사 4 · 덮개 나사 4 · 고정 핀 구멍) + 벽(핀이 반쯤 묻힘) ----
    n = "HOUSING_BASE"
    sc.revolve_z(n, [(0, r["pilot_hole"]), (0, r["outer"]), (z["joint"], r["outer"]), (z["joint"], r["ring"]), (z["base_top"], r["ring"]),
                     (z["base_top"], r["pilot_hole"])])
    for i, (x, y) in enumerate(pins):
        sc.hole(n, x, y, z["ring_pin_hole_base"][0], z["ring_pin_hole_base"][1] - z["ring_pin_hole_base"][0], fits["pin_press_hole_dia"], f"P{i}",
                floor="below")
    for i, (x, y) in enumerate(bolts):
        sc.hole(n, x, y, 0, z["base_top"], fits["m3_clearance_dia"], f"M{i}")
    for i, (x, y) in enumerate(ring(hs["cap_screws"], r["cap_screw"], math.pi / 4)):
        sc.hole(n, x, y, 0, z["joint"], fits["m3_clearance_dia"], f"S{i}")
    sc.declare_hole(n, 0, 0, 0, z["base_top"], 2 * r["pilot_hole"], "PILOT")       # 모터 파일럿(회전 윤곽으로 생김)
    parts.append(n)

    # ---- 덮개: 고정 핀 윗끝 구멍 · 캐리어 판 둘레 · 턱(6808 바깥 고리 밑) · 6808 바깥 자리 ----
    n = "HOUSING_CAP"
    zc0, zc1 = z["cap"]
    sc.revolve_z(n, [(zc0, r["cap_bore"]), (zc0, r["outer"]), (zc1, r["outer"]), (zc1, r["seat_output"]), (z["output_bearing"][0], r["seat_output"]),
                     (z["output_bearing"][0], r["outer_shoulder_output"]), (z["cap_lip"][0], r["outer_shoulder_output"]),
                     (z["cap_lip"][0], r["cap_bore"])])
    for i, (x, y) in enumerate(pins):   # 덮개는 핀 28 개 위로 미끄러져 씌운다(바닥판만 압입) — 다시 열 때도 핀을 뽑지 않는다
        sc.hole(n, x, y, zc0, z["ring_pin_hole_cap"][1] - zc0, fits["pin_slip_hole_dia"], f"P{i}", floor="above")
    for i, (x, y) in enumerate(ring(hs["cap_screws"], r["cap_screw"], math.pi / 4)):
        sc.hole(n, x, y, zc0, hs["cap_insert_depth"], fits["insert_hole_dia"], f"I{i}", floor="above")   # 바닥판 아래 나사가 표준 길이로 물리게 깊게
    for i, (x, y) in enumerate(ring(hs["cap_screws"], r["retainer_screw"], 0.0)):
        sc.hole(n, x, y, zc1 - fits["insert_depth"], fits["insert_depth"], fits["insert_hole_dia"], f"R{i}", floor="below")
    sc.declare_hole(n, 0, 0, z["output_bearing"][0], z["output_bearing"][1] - z["output_bearing"][0], 2 * r["seat_output"], "SEAT6808",
                    entry="up")   # 회전 윤곽 · 6808 은 위에서 넣는다(밑은 덮개 턱)
    parts.append(n)

    # ---- 누름 고리(6808 바깥 고리 위) ----
    n = "RETAINER"
    zr0, zr1 = z["retainer"]
    sc.revolve_z(n, [(zr0, r["outer_shoulder_output"]), (zr0, r["retainer_out"]), (zr1, r["retainer_out"]), (zr1, r["outer_shoulder_output"])])
    for i, (x, y) in enumerate(ring(hs["cap_screws"], r["retainer_screw"], 0.0)):
        sc.hole(n, x, y, zr0, zr1 - zr0, fits["m3_clearance_dia"], f"S{i}")
    parts.append(n)

    # ---- 원판 둘(같은 부품 · 둘째는 자기 중심에서 180° 돌려 끼움) ----
    for k in (1, 2):
        n = f"DISC_{k}"
        c, a = disc_pose(P, k, th)
        z0, z1 = z[f"disc{k}"]
        sc.poly_extrude(n, profile, z0, z1 - z0, c, (math.cos(a), math.sin(a)))
        sc.hole(n, c[0], c[1], z0, z1 - z0, 2 * r["disc_bore"], "BORE")
        for i, (u, v) in enumerate(ring(op["count"], op["radius"], math.radians(op["phase_deg"]))):
            du, dv = rotxy(u, v, a)
            sc.hole(n, c[0] + du, c[1] + dv, z0, z1 - z0, 2 * r["out_hole"], f"O{i}")
        parts.append(n)

    # ---- 편심 축 둘(D 축 평면 방향 = θ + 90° · 둘 다 D 구멍 관통) ----
    flat_ang = th + math.pi / 2
    n = "CAM_LOWER"
    sc.cyl(n, r["cam_shoulder"], z["cam_hub"][0], z["cam_hub"][1] - z["cam_hub"][0])
    sc.cyl(n + "_LOBE", r["lobe"], z["lobe1"][0], z["lobe1"][1] - z["lobe1"][0], E * math.cos(th), E * math.sin(th))
    sc.cmd("solid.combine", target=n, tools=[n + "_LOBE"], operation="join")
    sc.boss(n, E * math.cos(th), E * math.sin(th), z["lobe1"][0], z["lobe1"][1] - z["lobe1"][0], r["lobe"], "LOBE", "disc")
    dx = fits["d_bore_extra"]
    sc.d_hole(n, 0, 0, z["cam_lower"][0], z["cam_lower"][1] - z["cam_lower"][0], m["shaft_dia"] + dx, m["shaft_flat_to_axis"] + dx / 2, flat_ang,
              "SHAFT")   # 압입(게이지로 높이)
    parts.append(n)
    n = "CAM_UPPER"
    sc.cyl(n, r["cam_shoulder"], z["cam_spacer"][0], z["cam_spacer"][1] - z["cam_spacer"][0])
    sc.cyl(n + "_LOBE", r["lobe"], z["lobe2"][0], z["lobe2"][1] - z["lobe2"][0], -E * math.cos(th), -E * math.sin(th))
    sc.cyl(n + "_J", r["journal"], z["journal"][0], z["journal"][1] - z["journal"][0])
    sc.cmd("solid.combine", target=n, tools=[n + "_LOBE", n + "_J"], operation="join")
    sc.boss(n, -E * math.cos(th), -E * math.sin(th), z["lobe2"][0], z["lobe2"][1] - z["lobe2"][0], r["lobe"], "LOBE", "disc")
    sc.boss(n, 0, 0, z["journal"][0], z["journal"][1] - z["journal"][0], r["journal"], "JOURNAL", "shaft_end")
    du = dx + fits["cam_upper_bore_extra"]
    sc.d_hole(n, 0, 0, z["cam_upper"][0], z["cam_upper"][1] - z["cam_upper"][0], m["shaft_dia"] + du, m["shaft_flat_to_axis"] + du / 2, flat_ang,
              "SHAFT")   # 미끄럼(6801 #1 속 고리 위에 얹힘)
    parts.append(n)

    # ---- 와셔(6801 #2 속 고리 ↔ 6800 속 고리 · 기본 두께) ----
    n = "WASHER"
    sc.revolve_z(n, [(z["washer"][0], r["washer_in"]), (z["washer"][0], r["washer_out"]), (z["washer"][1], r["washer_out"]), (z["washer"][1], r["washer_in"])])
    sc.declare_hole(n, 0, 0, z["washer"][0], z["washer"][1] - z["washer"][0], 2 * r["washer_in"], "BORE")
    parts.append(n)

    # ---- 출력 캐리어: 판(출력 핀 압입 · 6800 자리 + 속 고리 위 오목) + 턱(6808 속 고리 밑) + 허브(6808 속 고리 안) + 인서트 ----
    n = "CARRIER"
    zp0, zp1 = z["carrier_plate"]
    zh1 = z["carrier_hub"][1]
    sc.revolve_z(n, [(zp0, 0), (zp0, r["plate"]), (zp1, r["plate"]), (zp1, r["inner_shoulder_output"]), (z["collar"][1], r["inner_shoulder_output"]),
                     (z["collar"][1], r["hub"]), (zh1, r["hub"]), (zh1, 0)])
    sc.boss(n, 0, 0, z["carrier_hub"][0], z["carrier_hub"][1] - z["carrier_hub"][0], r["hub"], "HUB", "output")
    sc.hole(n, 0, 0, zp0, z["shaft_bearing"][1] - zp0, 2 * r["shaft_seat"], "SEAT", entry="down")    # 6800 은 판 밑에서 넣는다(위는 턱)
    sc.hole(n, 0, 0, z["seat_relief"][0], z["seat_relief"][1] - z["seat_relief"][0], 2 * r["seat_relief"], "RELIEF", floor="above")
    for i, (u, v) in enumerate(ring(op["count"], op["radius"], math.radians(op["phase_deg"]))):
        x, y = rotxy(u, v, phi)
        sc.hole(n, x, y, zp0, zp1 - zp0, fits["pin_press_hole_dia"], f"P{i}", floor="above")
    for i, (u, v) in enumerate(ring(car["output_inserts"], r["output_insert"], math.pi / 4)):
        x, y = rotxy(u, v, phi)
        sc.hole(n, x, y, zh1 - fits["insert_depth"], fits["insert_depth"], fits["insert_hole_dia"], f"I{i}", floor="below")
    parts.append(n)

    # ---- 출력 플랜지: 허브 윗면에 나사 4 개 · 6808 속 고리를 위에서 누름 · 시험 짐 · 팔을 이 나사로 함께 붙인다 ----
    n = "OUTPUT_FLANGE"
    zf0, zf1 = z["flange"]
    sc.revolve_z(n, [(zf0, 0), (zf0, r["inner_shoulder_output"]), (zf1, r["inner_shoulder_output"]), (zf1, 0)])
    for i, (u, v) in enumerate(ring(car["output_inserts"], r["output_insert"], math.pi / 4)):
        x, y = rotxy(u, v, phi)
        sc.hole(n, x, y, zf0, zf1 - zf0, fits["m3_clearance_dia"], f"S{i}")
    parts.append(n)

    # ---- 참조(인쇄 안 함) ----
    # 고정 핀 28 개는 SolidCraft 몸체로 넣지 않는다: 바닥판 구멍과 같은 축인 바닥판 ↔ 핀 쌍마다 정확 커널이 약 150 s 들여 「빈 결과」 로 끝냈다
    # (2026-10-24 초안 θ45 의 가장 느린 10 쌍 148.3 ~ 153.1 s · 모든 쌍의 불리언 시간 합 3644 s — 발췌 = source-records.json · 배터리에서는 자세마다
    # 1 시간 가까이). 대신 `verify_geometry.assembly()` 가 파이썬 원통과 부품 STL 의 입체 교차로 본다(세 입력 각 · 모든 부품 · 바닥판만 압입).
    pin_ref = fits["pin_press_hole_dia"] - REF_PIN_SHRINK      # SolidCraft 참조 출력 핀(캐리어에 압입) — 기록용 정확 커널 검사
    ring_pin_specs = [(f"RING_PIN_{i}", x, y, z["ring_pin"][0], z["ring_pin"][1] - z["ring_pin"][0]) for i, (x, y) in enumerate(pins)]
    for i, (u, v) in enumerate(ring(op["count"], op["radius"], math.radians(op["phase_deg"]))):
        nm = f"REF_OUTPUT_PIN_{i}"
        x, y = rotxy(u, v, phi)
        sc.cyl(nm, pin_ref / 2, z["output_pin"][0], z["output_pin"][1] - z["output_pin"][0], x, y)
        refs.append(nm)
    for k in (1, 2):
        nm = f"REF_BEARING_DISC_{k}"
        c, _a = disc_pose(P, k, th)
        z0, z1 = z[f"disc_bearing{k}"]
        sc.revolve_z(nm, [(z0, B["disc"]["id"] / 2), (z0, B["disc"]["od"] / 2), (z1, B["disc"]["od"] / 2), (z1, B["disc"]["id"] / 2)], *c)
        refs.append(nm)
    for nm, key, zz in (("REF_BEARING_OUTPUT", "output", z["output_bearing"]), ("REF_BEARING_SHAFT", "shaft_end", z["shaft_bearing"])):
        sc.revolve_z(nm, [(zz[0], B[key]["id"] / 2), (zz[0], B[key]["od"] / 2), (zz[1], B[key]["od"] / 2), (zz[1], B[key]["id"] / 2)])
        refs.append(nm)
    f = m["frame"]
    nm = "REF_MOTOR"
    sc.poly_extrude(nm, [(-f / 2, -f / 2), (f / 2, -f / 2), (f / 2, f / 2), (-f / 2, f / 2)], -40.0, 40.0, (0, 0), (1, 0))
    sc.cyl(nm + "_PILOT", m["pilot_dia"] / 2, 0.0, m["pilot_height"])
    sc.cmd("solid.combine", target=nm, tools=[nm + "_PILOT"], operation="join")
    refs.append(nm)
    nm = "REF_MOTOR_SHAFT"
    rs = m["shaft_dia"] / 2
    a0 = math.acos(m["shaft_flat_to_axis"] / rs)
    sc.poly_extrude(nm, [(rs * math.cos(t + flat_ang), rs * math.sin(t + flat_ang)) for t in np.linspace(a0, 2 * math.pi - a0, 72)],
                    m["pilot_height"], z["motor_shaft"][1] - m["pilot_height"], (0, 0), (1, 0))
    refs.append(nm)
    for i, (x, y) in enumerate(bolts):
        nm = f"REF_MOTOR_SCREW_HEAD_{i}"
        sc.cyl(nm, m["screw_head_dia"] / 2, z["motor_screw_head"][0], z["motor_screw_head"][1] - z["motor_screw_head"][0], x, y)
        refs.append(nm)
    return sc, parts, refs, ring_pin_specs


def mesh_intersection(path_a, path_b):
    """두 STL 의 교차 부피(mm³) — 정확 커널이 못 한 쌍(같은 축 · 같은 반지름 등)에만 쓴다(MP4 와 같은 길)."""
    import manifold3d as m3d
    import trimesh

    def solid(path):
        mm = trimesh.load(path, force="mesh")
        return m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(mm.vertices, dtype=np.float32), tri_verts=np.asarray(mm.faces, dtype=np.uint32)))

    both = solid(path_a) ^ solid(path_b)
    return float(both.volume()) if hasattr(both, "volume") else float(both.get_volume())


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry_sha256(sc):
    """형상 명령(내보내기 · 검사 명령을 붙이기 전)의 지문 — 조립 증거가 지금 생성기 · 매개변수의 형상에서 나왔는가를 검사 묶음이 다시 계산해 견준다."""
    return hashlib.sha256(json.dumps(sc.commands, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def small_parts(P):
    """맞춤 확인 판 · 와셔 변형 셋 · 끼움 게이지(인쇄) — 조립 밖 · 판에서 따로 놓는다."""
    sc = SC()
    fs, B, m, r = P["fit_strip"], P["bearings"], P["motor"], radii(P)
    # 판 120 × 72 × 6 · 자리(왼쪽 → 오른쪽 = 시리즈 순서):
    #   아래 줄 y 8: 핀 구멍 x 8 · 18 · 28 · 38 | D 구멍 x 52 · 66 · 80
    #   가운데 줄 y 30: 6801 바깥 자리 x 16 · 44 · 72 | 위 줄 y 56: 6800 바깥 자리 x 16 · 44 · 72
    #   오른쪽 두 열(판 위에 선 기둥): x 96 = 6801 안지름(Ø12 ±) y 14 · 32 · 50 | x 113 = 6800 안지름(Ø10 ±) y 14 · 32 · 50
    w, d, t = 120.0, 72.0, 6.0
    n = "FIT_STRIP"
    sc.poly_extrude(n, [(0, 0), (w, 0), (w, d), (0, d)], 0.0, t, (0, 0), (1, 0))
    rows = []
    for i, dia in enumerate(fs["pin_holes"]):
        x, y = 8.0 + 10 * i, 8.0
        sc.hole(n, x, y, t - 5.0, 5.0, dia, f"PIN{i}", floor="below")
        rows.append({"feature": "Ø4 pin press hole", "dia": dia, "xy": [x, y], "depth": 5.0})
    for i, off in enumerate(fs["bearing_seat_offsets"]):   # 가운데 = 아래 편심 축의 실제 D 구멍(축 + d_bore_extra)
        x, y = 52.0 + 14 * i, 8.0
        dx = P["fits"]["d_bore_extra"] + off
        dia, flat = m["shaft_dia"] + dx, m["shaft_flat_to_axis"] + dx / 2
        sc.d_hole(n, x, y, 0.0, t, dia, flat, math.pi / 2, f"D{i}")
        rows.append({"feature": "motor D-shaft bore (d_bore_extra " + f"{dx:+.2f})", "dia": dia, "flat_to_axis": flat, "xy": [x, y]})
    for j, (key, y) in enumerate((("disc", 30.0), ("shaft_end", 56.0))):
        for i, off in enumerate(fs["bearing_seat_offsets"]):   # 가운데 = 지금 자리 값(바깥지름 + bearing_seat_extra)
            x = 16.0 + 28 * i
            dia = B[key]["od"] + P["fits"]["bearing_seat_extra"] + off
            sc.hole(n, x, y, t - B[key]["width"], B[key]["width"], dia, f"S{j}{i}", entry="up")   # 베어링은 위에서 · 밑은 밀어내는 구멍만
            sc.hole(n, x, y, 0.0, t - B[key]["width"], 6.0, f"SP{j}{i}")      # 베어링을 밀어내는 구멍
            rows.append({"feature": f"{B[key]['model']} outer-ring seat", "dia": dia, "xy": [x, y], "depth": B[key]["width"]})
    pegs = []
    # 기둥 간격: 기둥에 끼운 베어링(6801 바깥 r 10.5 · 6800 r 9.5)이 옆 기둥(r ≤ 6.05)에 걸리지 않게 — 같은 열 18 · 두 열 사이 17(필요 17.05 · 16.05 +
    # 여유). 처음 꼴(14 간격)은 베어링이 옆 기둥에 걸려 끼워지지 않았다(L4-N1 뒤 새 「베어링이 들어오는 길」 검사가 찾음)
    for j, (key, x) in enumerate((("disc", 96.0), ("shaft_end", 113.0))):
        for i, off in enumerate(fs["bearing_seat_offsets"]):
            y = 14.0 + 18 * i
            dia = B[key]["id"] + P["fits"]["bearing_bore_extra"] + off      # 가운데 = 지금 축 값(안지름 + bearing_bore_extra)
            nm = f"{n}_PEG_{j}{i}"
            sc.cyl(nm, dia / 2, t, B[key]["width"], x, y)
            sc.boss(n, x, y, t, B[key]["width"], dia / 2, f"PEG{j}{i}", key)
            pegs.append(nm)
            rows.append({"feature": f"{B[key]['model']} inner-ring peg", "dia": dia, "xy": [x, y], "height": B[key]["width"]})
    sc.cmd("solid.combine", target=n, tools=pegs, operation="join")
    names = [n]
    # 와셔 변형(두께별 · 판 오른쪽 위에 따로 놓음 — 이름에 두께)
    for i, tw in enumerate(P["washer"]["variants"]):
        nm = f"WASHER_T{tw:.1f}".replace(".", "p")
        sc.revolve_z(nm, [(0.0, r["washer_in"]), (0.0, r["washer_out"]), (tw, r["washer_out"]), (tw, r["washer_in"])], 140.0 + 20 * i, 10.0)
        sc.declare_hole(nm, 140.0 + 20 * i, 10.0, 0.0, tw, 2 * r["washer_in"], "BORE")
        names.append(nm)
        rows.append({"feature": "washer variant", "thickness": tw, "od": 2 * r["washer_out"], "bore": 2 * r["washer_in"]})
    # 끼움 게이지: 두께 0.5 포크(홈 = 모터 축 + 1 · 홈 길이 10) — 아래 편심 축을 모터 파일럿 위 0.5 에 두고 누른 뒤 뺀다
    g = P["gauge"]["thickness"]
    slot = m["shaft_dia"] + 1.0
    nm = "GAUGE"
    sc.poly_extrude(nm, [(0, 0), (30, 0), (30, 14), (0, 14), (0, 7 + slot / 2), (10, 7 + slot / 2), (10, 7 - slot / 2), (0, 7 - slot / 2)],
                    0.0, g, (140.0, 40.0), (1, 0))
    names.append(nm)
    rows.append({"feature": "insertion gauge fork", "thickness": g, "slot": slot})
    return sc, names, rows


def run_cli(cli, args, env, timeout=3600):
    p = subprocess.run([str(cli), *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env)
    if p.returncode:
        raise SystemExit(f"{args[0]} rc {p.returncode}: {p.stderr[-1500:]}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--theta", type=float, nargs="+", default=[0.0, 45.0, 90.0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--scratch", type=Path, required=True, help="자세별 부품 · 참조 STL(정확 커널이 못 한 쌍의 메시 교차용 — 무겁다, 저장소 밖)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    P = load_params(a.params)
    profile, _n, _e = profile_for(P)
    env = dict(os.environ, SOLIDCRAFT_GPU="cpu")
    (a.out / "parts").mkdir(parents=True, exist_ok=True)
    a.evidence.mkdir(parents=True, exist_ok=True)
    summary = {}
    for theta in a.theta:
        sc, parts, refs, _pins = build(P, profile, theta)
        geom = geometry_sha256(sc)     # 내보내기 · 검사 명령을 붙이기 전
        tag = f"theta{int(round(theta)):03d}"
        first = theta == a.theta[0]
        stl_dir = a.scratch / f"stl-{tag}"
        stl_dir.mkdir(parents=True, exist_ok=True)
        for b in parts + refs:
            sc.cmd("file.export", path=str(stl_dir / f"{b}.stl"), bodies=[b])
        if first:
            for b in parts:
                sc.cmd("file.export", path=str(a.out / "parts" / f"{b}.stl"), bodies=[b])
        sc.cmd("inspect.interference", budget_s=900)
        sc.cmd("inspect.clearance", bodies=parts, against=parts + refs)
        script = a.scratch / f"build-{tag}.json"
        script.write_text(json.dumps({"commands": sc.commands}, ensure_ascii=False) + "\n", encoding="utf-8")
        native = (a.out if first else a.scratch) / f"cycloid-27-{tag}.solidcraft"
        args = ["run", str(script), "--save", str(native), "--results", "--json-out", str(a.scratch / f"result-{tag}.json")]
        if first:
            args += ["--out", str(a.out / "cycloid-27.step")]
        run_cli(a.cli, args, env)
        res = json.loads((a.scratch / f"result-{tag}.json").read_text(encoding="utf-8"))
        found = [x for rr in (res if isinstance(res, list) else res.get("results", [])) for x in (rr, rr.get("result") if isinstance(rr, dict) else None)
                 if isinstance(x, dict)]
        inter = next(x for x in found if "interferences" in x)
        clear = next(x for x in found if "overlaps" in x and "near" in x)
        kind = {**{x: "part" for x in parts}, **{x: "ref" for x in refs}}
        clash, touch, mesh_rows = [], [], []
        for it in inter["interferences"]:
            if "part" not in (kind.get(it["a"]), kind.get(it["b"])):
                continue
            thin = min(hi - lo for hi, lo in zip(it["bbox"]["max"], it["bbox"]["min"]))
            row = {"a": it["a"], "b": it["b"], "volume_mm3": float(it.get("volume_mm3") or 0), "thinnest_mm": thin}
            (touch if thin <= CONTACT_MM else clash).append(row)
        for u in inter.get("unchecked", []):
            v = mesh_intersection(stl_dir / f"{u['a']}.stl", stl_dir / f"{u['b']}.stl")
            row = {"a": u["a"], "b": u["b"], "mesh_intersection_mm3": v, "reason": u.get("reason")}
            mesh_rows.append(row)
            (touch if v <= MESH_CONTACT_MM3 else clash).append({**row, "by": "mesh"})
        if first:
            theta0_stl = {b: file_sha256(stl_dir / f"{b}.stl") for b in parts}
        summary[tag] = {"theta_deg": theta, "geometry_sha256": geom, "bodies": len(parts) + len(refs),
                        "stl_sha256": {b: file_sha256(stl_dir / f"{b}.stl") for b in parts},
                        "parts": parts, "refs": len(refs), "interference": clash, "contacts": touch,
                        "unchecked_resolved_by_mesh": mesh_rows, "clearance_overlaps": clear.get("overlaps", []),
                        "interference_stats": {k: inter[k] for k in ("checked", "pairs_candidate", "pairs_intersected", "pairs_not_checked", "budget_exceeded",
                                                                     "truncated") if k in inter},
                        "note": "SolidCraft exact-kernel record (reference only - the acceptance is verify_geometry, computed by check_cycloid.py itself)"}
        print(tag, "clash", len(clash), "contacts", len(touch), "mesh-resolved", len(mesh_rows),
              "max mesh mm3", round(max([q["mesh_intersection_mm3"] for q in mesh_rows], default=0.0), 4))
    # ---- 맞춤 확인 판 · 와셔 변형 · 게이지(따로 한 번) ----
    sc, names, rows = small_parts(P)
    small_geom = geometry_sha256(sc)
    sp_dir = a.scratch / "stl-small"
    sp_dir.mkdir(parents=True, exist_ok=True)
    for nm in names:
        sc.cmd("file.export", path=str(a.out / "parts" / f"{nm}.stl"), bodies=[nm])
        sc.cmd("file.export", path=str(sp_dir / f"{nm}.stl"), bodies=[nm])
    script = a.scratch / "build-small-parts.json"
    script.write_text(json.dumps({"commands": sc.commands}, ensure_ascii=False) + "\n", encoding="utf-8")
    run_cli(a.cli, ["run", str(script), "--save", str(a.out / "small-parts.solidcraft")], env, 1800)
    # 증거를 지금 형상에 묶는다: 커밋되는 부품 STL 의 sha256 · 입력 0° 의 SolidCraft 기록에 쓴 STL 이 그것과 같은가 · 생성기 입력의 sha256
    committed = {nm: file_sha256(a.out / "parts" / f"{nm}.stl") for nm in summary[next(iter(summary))]["parts"] + names}
    exported = {**theta0_stl, **{nm: file_sha256(sp_dir / f"{nm}.stl") for nm in names}}
    import verify_geometry as vg
    asm, feat = vg.assembly(P, a.out / "parts"), vg.features(P, a.out / "parts")
    print("verify assembly ok", asm["ok"], asm["rows"], "features ok", feat["ok"], feat["holes"], feat["shafts"], "failed", asm["failed"][:4], feat["failed"][:4])
    out = {"generator_sha256": {**{pth.name: file_sha256(pth) for pth in (a.params, HERE / "cycloid.py", HERE / "build_cycloid.py")},
                                "fit_calibration_values": P["fits"]["calibration"]["values_sha256"]},
           "small_parts_geometry_sha256": small_geom, "part_stl_sha256": committed,
           "exported_twice_identical": {nm: exported[nm] == committed[nm] for nm in committed},
           "stack_mm": stack(P), "by_theta": summary,
           "verify_geometry_at_build": {"assembly": {k: v for k, v in asm.items() if k != "failed"} | {"failed": asm["failed"][:20]},
                                        "features": {k: v for k, v in feat.items() if k != "rows"}},
           "small_parts": rows}
    (a.evidence / "assembly-checks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
