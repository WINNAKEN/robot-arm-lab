# -*- coding: utf-8 -*-
"""MP4 외장 v2 의 형상(SolidCraft 명령) — 실제 크기 조립(표시 자세)과 축소 전시 부품이 같이 쓴다.

좌표: 링크 k 의 지역 좌표 = 관절 k 원점 · 그 링크의 회전(v1 kinematics.json 의 R_child). 링크 k 안에 관절 k+1 의 고정자(드럼 · 모터 캔)가 있다.
`Frame` 은 지역 점 · 방향을 명령의 좌표(실제 조립 = 세계 · 부품 = 지역 그대로)로 바꾼다."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

WHITE, ORANGE, GRAPH = "#eceff1", "#ed7d31", "#2b3138"


class Spec:
    """외장 치수(mm · 실제 크기). parameters.json 과 v1 kinematics.json · parameters.json 에서 읽는다."""

    def __init__(self, params_path: Path, v1_dir: Path):
        self.p = json.loads(params_path.read_text(encoding="utf-8"))
        self.kin = json.loads((v1_dir / "kinematics.json").read_text(encoding="utf-8"))
        v1 = json.loads((v1_dir / "parameters.json").read_text(encoding="utf-8"))
        self.v1 = v1
        self.axes = np.asarray(v1["axis_parent_zero"], float)
        self.offs = [[0, 0, v1["joint1_height_mm"]], [0, 0, v1["shoulder_rise_mm"]], [v1["upper_arm_mm"], 0, 0], [v1["forearm_mm"], 0, 0],
                     [v1["wrist_offsets_mm"][0], 0, 0], [v1["wrist_offsets_mm"][1], 0, 0]]
        e = self.p["exterior"]
        self.D = float(v1["reducer_depth_mm"])
        self.RD = [d / 2 for d in v1["reducer_diameters_mm"]]
        self.RC = float(e["motor_can_radius_mm"])
        self.LC = float(3 + v1["motor_length_mm"] + 2 + v1["driver_depth_mm"] + e["can_rear_clearance_mm"])
        self.CAP = float(e["end_cap_thickness_mm"])
        self.RING_W, self.RING_T = float(e["accent_ring_width_mm"]), float(e["accent_ring_depth_mm"])
        self.OUT_SIGN = e["output_side_sign"]


class Frame:
    def __init__(self, O=None, R=None):
        self.O = np.zeros(3) if O is None else np.asarray(O, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)

    def p(self, v):
        return (self.O + self.R @ np.asarray(v, float)).tolist()

    def d(self, v):
        return (self.R @ np.asarray(v, float)).tolist()


def perp(a):
    a = np.asarray(a, float)
    h = np.array([0, 0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0, 0])
    v = h - a * np.dot(h, a)
    return v / np.linalg.norm(v)


class Builder:
    """명령 목록을 모은다. 바디마다 (이름, 링크, 색 역할)을 기록한다 — 역할: body(흰) · accent(주황) · dark(진회색)."""

    def __init__(self, spec: Spec):
        self.s = spec
        self.commands = []
        self.bodies = []

    def cmd(self, c, **p):
        self.commands.append({"command": c, "params": p})

    def _reg(self, name, link, role):
        color = {"body": WHITE, "accent": ORANGE, "dark": GRAPH}[role]
        self.cmd("appearance.assign", bodies=[name], color=color)
        self.bodies.append({"name": name, "link": link, "role": role})

    def revolve(self, F, name, link, role, center, axis, profile):
        a = np.asarray(axis, float) / np.linalg.norm(axis)
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": F.p(center), "x_dir": F.d(a), "y_dir": F.d(perp(a))})
        self.cmd("sketch.line", points=[[float(u), float(v)] for u, v in profile], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.revolve", axis="x", operation="new", body_name=name, name=name + "_REVOLVE")
        self._reg(name, link, role)

    def fillet_circle(self, F, name, center, axis, u, r, radius):
        a = np.asarray(axis, float) / np.linalg.norm(axis)
        pt = np.asarray(center, float) + a * u + perp(a) * r
        self.cmd("solid.fillet", body=name, edges=[F.p(pt)], radius=float(radius))

    def hub(self, F, name, link, center, axis, r, u0, u1, fillet=6):
        self.revolve(F, name, link, "body", center, axis, [(u0, 0), (u0, r), (u1, r), (u1, 0)])
        self.fillet_circle(F, name, center, axis, u0, r, fillet)
        self.fillet_circle(F, name, center, axis, u1, r, fillet)

    def tube(self, F, name, link, p0, p1, r):
        p0 = np.asarray(p0, float)
        p1 = np.asarray(p1, float)
        v = p1 - p0
        self.cmd("solid.cylinder", radius=float(r), height=float(np.linalg.norm(v)), base=F.p(p0), axis=F.d(v / np.linalg.norm(v)), operation="new",
                 body_name=name, name=name + "_CYL")
        self._reg(name, link, "body")

    def rounded_bar(self, F, name, link, x0, x1, wy, hz, radius):
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": F.p([x0, 0, 0]), "x_dir": F.d([0, 1, 0]), "y_dir": F.d([0, 0, 1])})
        self.cmd("sketch.rectangle.rounded", p0=[-wy / 2, -hz / 2], p1=[wy / 2, hz / 2], radius=radius)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(x1 - x0), operation="new", body_name=name, name=name + "_EXTRUDE")
        self._reg(name, link, "body")

    def rounded_post(self, F, name, link, z0, z1, x0, x1, y0, y1, radius):
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": F.p([0, 0, z0]), "x_dir": F.d([1, 0, 0]), "y_dir": F.d([0, 1, 0])})
        self.cmd("sketch.rectangle.rounded", p0=[x0, y0], p1=[x1, y1], radius=radius)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(z1 - z0), operation="new", body_name=name, name=name + "_EXTRUDE")
        self._reg(name, link, "body")

    def module(self, F, k, link, center, axis, with_cap=True):
        """관절 k 의 고정자 — 드럼 + 뒤 모터 캔(흰) · 출력 쪽 색 링 · 끝 덮개(주황). 출력 면 = 중심 + 축 × 출력 방향 × D/2."""
        s = self.s
        a = np.asarray(axis, float) * s.OUT_SIGN[k - 1]
        D, R, RC, LC = s.D, s.RD[k - 1], s.RC, s.LC
        if R - RC >= 1:
            prof = [(-D / 2 - LC, 0), (-D / 2 - LC, RC), (-D / 2, RC), (-D / 2, R), (D / 2 - s.RING_W, R), (D / 2 - s.RING_W, R - s.RING_T),
                    (D / 2, R - s.RING_T), (D / 2, 0)]
        else:          # 손목: 드럼과 캔이 같은 굵기 — 이음매 홈만 남긴다
            prof = [(-D / 2 - LC, 0), (-D / 2 - LC, RC), (-D / 2 - 2, RC), (-D / 2 - 2, RC - 1.5), (-D / 2, RC - 1.5), (-D / 2, R),
                    (D / 2 - s.RING_W, R), (D / 2 - s.RING_W, R - s.RING_T), (D / 2, R - s.RING_T), (D / 2, 0)]
        name = f"J{k}_MODULE"
        self.revolve(F, name, link, "body", center, a, prof)
        if R - RC >= 1:
            self.fillet_circle(F, name, center, a, -D / 2, R, 5)
        self.revolve(F, f"J{k}_ACCENT_RING", link, "accent", center, a,
                     [(D / 2 - s.RING_W, R - s.RING_T), (D / 2 - s.RING_W, R), (D / 2, R), (D / 2, R - s.RING_T)])
        if with_cap:
            cap = f"J{k}_END_CAP"
            self.revolve(F, cap, link, "accent", center, a, [(-D / 2 - LC - s.CAP, 0), (-D / 2 - LC - s.CAP, RC - 1), (-D / 2 - LC, RC - 1), (-D / 2 - LC, 0)])
            self.fillet_circle(F, cap, center, a, -D / 2 - LC - s.CAP, RC - 1, 3)

    # ---- 링크 ----
    def link(self, k, F):
        s, D, L = self.s, self.s.D, self.s.p["links"]
        if k == 0:
            b = L["base"]
            self.revolve(F, "BASE_FOOT", 0, "dark", [0, 0, 0], [0, 0, 1], [(0, 0), (0, b["foot_r"]), (b["foot_h"], b["foot_r"]), (b["foot_h"], 0)])
            self.fillet_circle(F, "BASE_FOOT", [0, 0, 0], [0, 0, 1], b["foot_h"], b["foot_r"], 5)
            z0, z1, z2, zt = b["foot_h"], b["band_z0"], b["band_z1"], s.offs[0][2] - D / 2
            r0, rg, rt = b["column_r"], b["column_r"] - s.RING_T, b["column_top_r"]
            self.revolve(F, "BASE_COLUMN", 0, "body", [0, 0, 0], [0, 0, 1],
                         [(z0, 0), (z0, r0), (z1, r0), (z1, rg), (z2, rg), (z2, rg - 1), (zt, rt), (zt, 0)])
            self.revolve(F, "BASE_LIGHT_RING", 0, "accent", [0, 0, 0], [0, 0, 1], [(z1, rg), (z1, r0), (z2, r0), (z2, rg)])
            self.module(F, 1, 0, s.offs[0], s.axes[0], with_cap=False)   # J1 의 캔은 기둥 안에 숨는다
        elif k == 1:
            c = L["shoulder"]
            self.revolve(F, "LINK1_SHOULDER_CAP", 1, "body", [0, 0, 0], [0, 0, 1],
                         [(D / 2, 0), (D / 2, c["cap_r"]), (D / 2 + c["cap_h"], c["cap_r"]), (D / 2 + c["cap_h"], 0)])
            self.fillet_circle(F, "LINK1_SHOULDER_CAP", [0, 0, 0], [0, 0, 1], D / 2 + c["cap_h"], c["cap_r"], 8)
            self.rounded_post(F, "LINK1_POST", 1, D / 2, s.offs[1][2], -c["post_half_w"], c["post_half_w"], c["post_y0"], c["post_y1"], 14)
            self.module(F, 2, 1, s.offs[1], s.axes[1])
        elif k == 2:
            u = L["upper_arm"]
            self.hub(F, "LINK2_SHOULDER_HUB", 2, [0, 0, 0], [0, 1, 0], u["hub_r"], D / 2, D / 2 + u["hub_t"])
            self.tube(F, "LINK2_UPPER_TUBE", 2, [0, D / 2 + u["hub_t"] / 2, 0], [s.offs[2][0], D / 2 + u["hub_t"] / 2, 0], u["tube_r"])
            self.module(F, 3, 2, s.offs[2], s.axes[2])
        elif k == 3:
            f = L["forearm"]
            self.hub(F, "LINK3_ELBOW_HUB", 3, [0, 0, 0], [0, 1, 0], f["hub_r"], -D / 2 - f["hub_t"], -D / 2)
            self.tube(F, "LINK3_FOREARM_TUBE", 3, [0, -D / 2 - f["hub_t"] / 2, 0], [f["tube_len"], -D / 2 - f["hub_t"] / 2, 0], f["tube_r"])
            self.module(F, 4, 3, s.offs[3], s.axes[3])
        elif k == 4:
            w = L["wrist1"]
            self.rounded_bar(F, "LINK4_NECK", 4, D / 2, s.offs[4][0] - w["neck_gap"], w["neck_w"], w["neck_h"], 12)
            self.module(F, 5, 4, s.offs[4], s.axes[4])
        elif k == 5:
            w = L["wrist2"]
            self.hub(F, "LINK5_WRIST_HUB", 5, [0, 0, 0], [0, 1, 0], w["hub_r"], D / 2, D / 2 + w["hub_t"])
            self.tube(F, "LINK5_WRIST_TUBE", 5, [0, D / 2 + w["hub_t"] / 2, 0], [w["tube_len"], D / 2 + w["hub_t"] / 2, 0], w["tube_r"])
            self.module(F, 6, 5, s.offs[5], s.axes[5])
        else:
            t = L["tool"]
            self.revolve(F, "LINK6_TOOL_FLANGE", 6, "dark", [0, 0, 0], [1, 0, 0],
                         [(D / 2, 0), (D / 2, t["flange_r"]), (D / 2 + t["flange_t"], t["flange_r"]), (D / 2 + t["flange_t"], 0)])
            self.fillet_circle(F, "LINK6_TOOL_FLANGE", [0, 0, 0], [1, 0, 0], D / 2 + t["flange_t"], t["flange_r"], 2)
            self.revolve(F, "LINK6_TOOL_RING", 6, "accent", [0, 0, 0], [1, 0, 0],
                         [(D / 2 + t["flange_t"], 0), (D / 2 + t["flange_t"], t["ring_r"]), (D / 2 + t["flange_t"] + t["ring_t"], t["ring_r"]),
                          (D / 2 + t["flange_t"] + t["ring_t"], 0)])
