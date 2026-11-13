# -*- coding: utf-8 -*-
"""MP7 외장 v3 — 사용자 브랜드 KMJH(흰 · Deep Navy · Cool Gray + 민트 강조 · 각진 면 + 45° 사선)로 다시 그린 1:1 외장.

관절 원점 · 축 · 길이 · 드럼 지름 · 깊이 · 캔 반지름 · 표시 자세는 v1 / v2 그대로다(사용자: URDF 준비 중 — 관절 거리 불변).
바뀌는 것 = 모서리(둥근 필렛 → 45° 모따기) · 링크 단면(둥근 관 → 모따기한 팔각 막대) · 색 · 표시(끝 덮개 민트 사선 · 상완 KMJH 글자).

좌표: 링크 k 의 지역 좌표 = 관절 k 원점 · 그 링크의 회전(v1 kinematics.json 의 R_child). 링크 k 안에 관절 k+1 의 고정자(드럼 · 모터 캔)가 있다.
`Frame` 은 지역 점 · 방향을 세계 좌표로 바꾼다. v2 의 v2geom.py 를 가져오지 않는다(v2 는 Codex 검사가 해시로 묶어 두어 손대지 않는다)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from kmjh_logo import letters


# 양성 대조(검사가 실제로 잡는지 — build_product.py --control · 저장소 밖 작업 뿌리에만): 이름 → 일부러 넣는 잘못
CONTROLS = {
    "logo_on_drum": "KMJH 글자를 x = 30(J2 드럼 위)에 둔다 — 생성기의 x > 52 확인도 끈다(C2 가 잡아야 함)",
    "bar_shift": "상완 막대만 x 로 1 mm 민다 — 관절은 그대로(C1d 가 잡아야 함)",
    "can_short": "모터 캔을 12 mm 짧게 — 가정 상자가 모듈 밖으로(C3 가 잡아야 함)",
    "cap_color": "J2 끝 덮개를 흰색으로 칠한다 — bodies.json 의 역할은 남색 그대로(C5 가 저장 색으로 잡아야 함)",
    "joint_origin": "J3 관절 객체를 x 로 1 mm 옮긴다 — 형상은 그대로(C1 이 잡아야 함 · build_product.py 에서 적용)",
    "owner_both": "공구 플랜지를 Link5 컴포넌트에 만들고 bodies.json 도 링크 5 로 — native · 기록이 함께 틀림(C1c 의 독립 정답표가 잡아야 함)",
    "drop_ring": "공구 끝 고리를 아예 만들지 않음 — native · 기록 · 메시에서 함께 빠짐(C1c · C1e 가 잡아야 함)",
    "tool_holes_rotated": "MP9 2 단계 — 플랜지 나사 자리 넷을 45° 돌려 판다 · 다른 것은 그대로(C1e 가 잡아야 함)",
    "tool_holes_dropped": "MP9 2 단계(검토 B6) — 플랜지 나사 자리를 아예 파지 않는다(C1e 가 잡아야 함)",
    "tool_hole_deeper": "MP9 2 단계(검토 B6) — 나사 자리를 1 mm 더 깊게 판다(C1e 가 잡아야 함)",
}


class Spec:
    """외장 치수(mm · 실제 크기). 이 폴더의 parameters.json 과 v1 kinematics.json · parameters.json 에서 읽는다."""

    def __init__(self, params_path: Path, v1_dir: Path, control: str | None = None):
        assert control is None or control in CONTROLS, control
        self.control = control
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
        self.LC = float(3 + v1["motor_length_mm"] + 2 + v1["driver_depth_mm"] + e["can_rear_clearance_mm"]) - (12.0 if control == "can_short" else 0.0)
        self.CAP = float(e["end_cap_thickness_mm"])
        self.RING_W, self.RING_T = float(e["accent_ring_width_mm"]), float(e["accent_ring_depth_mm"])
        self.OUT_SIGN = e["output_side_sign"]
        self.COLORS = self.p["brand"]["colors"]
        self.TOOL = tool_interface(self.p["links"]["tool"], params_path.parent)


def tool_interface(t, base: Path):
    """공구 끝 규격(MP9 2 단계 · 계획 051) — 숫자는 그리퍼 parameters · 끼움 원장에만 있고 여기서는 읽기만 한다."""
    src = t["interface_from"]
    g = json.loads((base / src["gripper_params"]).resolve().read_text(encoding="utf-8"))
    ins = json.loads((base / src["ledger"]).resolve().read_text(encoding="utf-8"))["materials"][src["material"]]["values"]["insert_hole_dia"]
    lay, m3 = g["layout"], g["screws"]["arm_m3"]
    below = float(m3["length"]) - (float(lay["base_top"]) - float(lay["arm_screw_cbore"][1]))      # 팔 나사 몸통이 받침 아랫면 밑으로 나온 길이
    out = {"boss_r": float(lay["recess_dia"]) / 2, "boss_t": float(lay["recess_depth"]), "pcd": float(lay["arm_screw_pcd"]),
           "phase_deg": float(lay["arm_screw_phase_deg"]), "count": 4, "hole_d": float(ins["value"]), "hole_status": ins["status"],
           "hole_depth": below + float(t["screw_hole_extra_depth"])}      # count 4 = 그리퍼 팔 나사 수(그리퍼 쪽도 넷으로 고정 · 매개변수 없음)
    # 한계(검토 MP9-B1 · 검사기도 따로 단언): 넘으면 만들지 않는다 — 그리퍼 나사 길이 같은 원천 값이 바뀌어 구멍이 플랜지 뒤를 뚫는 일을 막음
    lim = {"depth_leaves_floor": out["hole_depth"] <= float(t["flange_t"]) - float(t["screw_hole_min_floor"]),
           "holes_clear_boss": out["pcd"] / 2 - out["hole_d"] / 2 > out["boss_r"],
           "holes_inside_flange_face": out["pcd"] / 2 + out["hole_d"] / 2 < float(t["flange_r"]) - float(t["flange_chamfer"]),
           "material_matches_gripper": src["material"] == g["fits_from"]["material"]}
    bad = [k for k, v in lim.items() if not v]
    if bad:
        raise SystemExit(f"tool interface out of limits: {bad} · {out}")
    return out


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


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def octagon(hw, hh, c):
    """가로 반폭 hw · 세로 반높이 hh · 네 모서리를 45° 로 c 만큼 깎은 팔각형(반시계)."""
    return [(hw, -hh + c), (hw, hh - c), (hw - c, hh), (-hw + c, hh), (-hw, hh - c), (-hw, -hh + c), (-hw + c, -hh), (hw - c, -hh)]


def slash(height, width):
    """로고 K 의 민트 사선 꼴 — 위 · 아래 변은 가로, 옆변은 45°. 가운데가 원점."""
    h, w = height / 2, width
    return [(-h - w / 2, -h), (-h + w / 2, -h), (h + w / 2, h), (h - w / 2, h)]


class Builder:
    """명령 목록을 모은다. 바디마다 (이름, 링크, 색 역할)을 기록한다 — 역할: body(흰) · accent(남) · frame(회) · highlight(민트)."""

    def __init__(self, spec: Spec):
        self.s = spec
        self.commands = []
        self.bodies = []

    def cmd(self, c, **p):
        self.commands.append({"command": c, "params": p})

    def _reg(self, name, link, role):
        paint = self.s.COLORS["body"] if (self.s.control == "cap_color" and name == "J2_END_CAP") else self.s.COLORS[role]
        self.cmd("appearance.assign", bodies=[name], color=paint)
        self.bodies.append({"name": name, "link": link, "role": role, "color": self.s.COLORS[role]})

    def revolve(self, F, name, link, role, center, axis, profile):
        a = unit(axis)
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": F.p(center), "x_dir": F.d(a), "y_dir": F.d(perp(a))})
        self.cmd("sketch.line", points=[[float(u), float(v)] for u, v in profile], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.revolve", axis="x", operation="new", body_name=name, name=name + "_REVOLVE")
        self._reg(name, link, role)

    def prism(self, name, link, role, origin_w, xdir_w, ydir_w, poly, distance):
        """세계 좌표 평면(원점 · x · y)에 다각형을 그려 평면 법선(x × y) 쪽으로 distance 만큼 밀어낸다."""
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": list(map(float, origin_w)), "x_dir": list(map(float, xdir_w)),
                                                                "y_dir": list(map(float, ydir_w))})
        self.cmd("sketch.line", points=[[float(u), float(v)] for u, v in poly], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=float(distance), operation="new", body_name=name, name=name + "_EXTRUDE")
        self._reg(name, link, role)

    def hub(self, F, name, link, center, axis, r, u0, u1):
        c = self.s.p["exterior"]["hub_chamfer_mm"]
        self.revolve(F, name, link, "body", center, axis, [(u0, 0), (u0, r - c), (u0 + c, r), (u1 - c, r), (u1, r - c), (u1, 0)])

    def bar(self, F, name, link, p0, p1, hw, hh, c, end_edge_y=None):
        """p0 → p1(지역 · 링크 x 방향) 팔각 막대. 단면의 가로 = 링크 y · 세로 = 링크 z.

        end_edge_y: 막대 끝이 다음 관절의 모터 캔(축 = 링크 x · y = 0) 옆에 붙을 때, 캔 밖으로 나온 바깥쪽을 45° 로 잘라 낸다 —
        바깥 면(가운데에서 먼 쪽)의 끝을 x_a 에서 시작해 끝 x 에서 y = end_edge_y(캔 안쪽)에 닿는 45° 면."""
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        v = p1 - p0
        assert abs(v[1]) < 1e-9 and abs(v[2]) < 1e-9 and v[0] > 0, "bars run along +x of the link"
        self.prism(name, link, "body", F.p(p0), F.d([0, 1, 0]), F.d([0, 0, 1]), octagon(hw, hh, c), v[0])
        if end_edge_y is not None:
            yc, L = p0[1], p1[0]
            sg = 1.0 if yc > 0 else -1.0
            y_out = yc + sg * hw
            x_a = L - abs(y_out - end_edge_y)
            assert x_a > p0[0], "45 deg end cut longer than the bar"
            tri = [(x_a - 1, y_out + sg), (L + 1, y_out + sg), (L + 1, end_edge_y - sg)]
            self.cmd("sketch.create", name=name + "_ENDCUT_PROFILE", plane={"origin": F.p([0, 0, -hh - 1]), "x_dir": F.d([1, 0, 0]), "y_dir": F.d([0, 1, 0])})
            self.cmd("sketch.line", points=[[float(u), float(w)] for u, w in tri], closed=True)
            self.cmd("sketch.finish")
            self.cmd("solid.extrude", distance=float(2 * hh + 2), operation="cut", targets=[name], name=name + "_ENDCUT")

    def hub_cap(self, F, name, link, center, out_axis, u_face, r_disc, slash_scale=1.0):
        """허브 바깥 원판 면에 남색 원판(1.0 돋움) + 그 위에 민트 사선 — 관절 끝 덮개와 같은 꼴을 허브에도."""
        a = unit(out_axis)
        self.revolve(F, name + "_CAP", link, "accent", center, a, [(u_face, 0), (u_face, r_disc), (u_face + 1.0, r_disc), (u_face + 1.0, 0)])
        n_w = np.asarray(F.d(a))
        up_hint = np.array([0, 0, 1.0]) if abs(n_w[2]) < 0.9 else np.array([1.0, 0, 0])
        up = unit(up_hint - n_w * np.dot(up_hint, n_w))
        m = self.s.p["marks"]["cap_slash"]
        face_w = np.asarray(F.p(np.asarray(center, float) + a * (u_face + 1.0)))
        self.mark_on_face(name + "_SLASH", link, "highlight", face_w, n_w, np.cross(up, n_w), slash(m["height"] * slash_scale, m["width"] * slash_scale))

    def mark_on_face(self, name, link, role, origin_w, normal_w, along_w, poly):
        """바깥을 향한 평면(원점 · 바깥 법선)에 다각형을 emboss_mm 만큼 돋운다. along = 글자의 오른쪽(평면 안)."""
        n, r = unit(normal_w), unit(along_w)
        r = unit(r - n * np.dot(r, n))
        up = np.cross(n, r)          # r × up = n — 바깥에서 보면 r 이 오른쪽 · up 이 위
        self.prism(name, link, role, origin_w, r, up, poly, self.s.p["marks"]["emboss_mm"])

    def module(self, F, k, link, center, axis, with_cap=True):
        """관절 k 의 고정자 — 드럼 + 뒤 모터 캔(흰) · 출력 쪽 띠 · 끝 덮개(남) · 끝 덮개의 민트 사선. 출력 면 = 중심 + 축 × 출력 방향 × D/2."""
        s, e = self.s, self.s.p["exterior"]
        a = np.asarray(axis, float) * s.OUT_SIGN[k - 1]
        D, R, RC, LC = s.D, s.RD[k - 1], s.RC, s.LC
        if R - RC >= 1:
            c = e["drum_chamfer_mm"]
            prof = [(-D / 2 - LC, 0), (-D / 2 - LC, RC), (-D / 2, RC), (-D / 2, R - c), (-D / 2 + c, R), (D / 2 - s.RING_W, R),
                    (D / 2 - s.RING_W, R - s.RING_T), (D / 2, R - s.RING_T), (D / 2, 0)]
        else:          # 손목: 드럼과 캔이 같은 굵기 — 이음매 홈만 남긴다(v2 와 같음)
            prof = [(-D / 2 - LC, 0), (-D / 2 - LC, RC), (-D / 2 - 2, RC), (-D / 2 - 2, RC - 1.5), (-D / 2, RC - 1.5), (-D / 2, R),
                    (D / 2 - s.RING_W, R), (D / 2 - s.RING_W, R - s.RING_T), (D / 2, R - s.RING_T), (D / 2, 0)]
        name = f"J{k}_MODULE"
        self.revolve(F, name, link, "body", center, a, prof)
        self.revolve(F, f"J{k}_ACCENT_RING", link, "accent", center, a,
                     [(D / 2 - s.RING_W, R - s.RING_T), (D / 2 - s.RING_W, R), (D / 2, R), (D / 2, R - s.RING_T)])
        if with_cap:
            cap, cc, u_face = f"J{k}_END_CAP", e["cap_chamfer_mm"], -D / 2 - LC - s.CAP
            self.revolve(F, cap, link, "accent", center, a,
                         [(u_face, 0), (u_face, RC - 1 - cc), (u_face + cc, RC - 1), (-D / 2 - LC, RC - 1), (-D / 2 - LC, 0)])
            m = s.p["marks"]["cap_slash"]
            if k in m["joints"]:
                n_w = np.asarray(F.d(-a))
                up_hint = np.array([0, 0, 1.0]) if abs(n_w[2]) < 0.9 else np.array([1.0, 0, 0])
                up = unit(up_hint - n_w * np.dot(up_hint, n_w))
                right = np.cross(up, n_w)
                face_w = np.asarray(F.p(np.asarray(center, float) + a * u_face))
                shift_w = np.asarray(F.d(m.get("shift_link_mm", {}).get(str(k), [0, 0, 0])))     # 덮개를 지나가는 막대에서 사선을 비켜 놓는다
                du, dv = float(np.dot(shift_w, right)), float(np.dot(shift_w, up))
                poly = [(u + du, v + dv) for u, v in slash(m["height"], m["width"])]
                self.mark_on_face(f"J{k}_CAP_SLASH", link, "highlight", face_w, n_w, right, poly)

    # ---- 링크 ----
    def link(self, k, F):
        s, D, L = self.s, self.s.D, self.s.p["links"]
        if k == 0:
            b = L["base"]
            fc = b["foot_chamfer"]
            self.revolve(F, "BASE_FOOT", 0, "frame", [0, 0, 0], [0, 0, 1],
                         [(0, 0), (0, b["foot_r"]), (b["foot_h"] - fc, b["foot_r"]), (b["foot_h"], b["foot_r"] - fc), (b["foot_h"], 0)])
            z0, z1, z2, zt = b["foot_h"], b["band_z0"], b["band_z1"], s.offs[0][2] - D / 2
            r0, rg, rt = b["column_r"], b["column_r"] - s.RING_T, b["column_top_r"]
            self.revolve(F, "BASE_COLUMN", 0, "body", [0, 0, 0], [0, 0, 1],
                         [(z0, 0), (z0, r0), (z1, r0), (z1, rg), (z2, rg), (z2, rg - 1), (zt, rt), (zt, 0)])
            self.revolve(F, "BASE_LIGHT_RING", 0, "highlight", [0, 0, 0], [0, 0, 1], [(z1, rg), (z1, r0), (z2, r0), (z2, rg)])
            self.module(F, 1, 0, s.offs[0], s.axes[0], with_cap=False)   # J1 의 캔은 기둥 안에 숨는다
        elif k == 1:
            c = L["shoulder"]
            cc = c["cap_chamfer"]
            self.revolve(F, "LINK1_SHOULDER_CAP", 1, "body", [0, 0, 0], [0, 0, 1],
                         [(D / 2, 0), (D / 2, c["cap_r"]), (D / 2 + c["cap_h"] - cc, c["cap_r"]), (D / 2 + c["cap_h"], c["cap_r"] - cc),
                          (D / 2 + c["cap_h"], 0)])
            hw, y0, y1, pc = c["post_half_w"], c["post_y0"], c["post_y1"], c["post_chamfer"]
            cy, hy = (y0 + y1) / 2, (y1 - y0) / 2
            self.prism("LINK1_POST", 1, "body", F.p([0, cy, D / 2]), F.d([1, 0, 0]), F.d([0, 1, 0]), octagon(hw, hy, pc), s.offs[1][2] - D / 2)
            self.module(F, 2, 1, s.offs[1], s.axes[1])
        elif k == 2:
            u = L["upper_arm"]
            yc = D / 2 + u["hub_t"] / 2
            self.hub(F, "LINK2_SHOULDER_HUB", 2, [0, 0, 0], [0, 1, 0], u["hub_r"], D / 2, D / 2 + u["hub_t"])
            self.hub_cap(F, "LINK2_SHOULDER_HUB", 2, [0, 0, 0], [0, 1, 0], D / 2 + u["hub_t"], u["hub_r"] - s.p["exterior"]["hub_chamfer_mm"] - 2)
            dx = 1.0 if s.control == "bar_shift" else 0.0
            self.bar(F, "LINK2_UPPER_BAR", 2, [dx, yc, 0], [s.offs[2][0] + dx, yc, 0], u["bar_half_w"], u["bar_half_h"], u["bar_chamfer"])
            self.module(F, 3, 2, s.offs[2], s.axes[2])
            lg = s.p["marks"]["logo"]
            rows, width = letters()
            h = lg["cap_height"]
            cx = 30.0 if s.control == "logo_on_drum" else lg["center_x"]
            x_left = cx - width * h / 2
            if s.control != "logo_on_drum":
                assert x_left > lg["keep_clear_of_j2_drum_x"], "logo would sit on the J2 drum"
            face_y = yc - u["bar_half_w"]                   # -y 면(앞에서 보이는 면)
            for nm, role, pts in rows:
                poly = [(x_left + px * h, (py - 0.5) * h) for px, py in pts]
                self.mark_on_face(f"LINK2_LOGO_{nm}", 2, "accent" if role == "navy" else "highlight", F.p([0, face_y, 0]), F.d([0, -1, 0]),
                                  F.d([1, 0, 0]), poly)
        elif k == 3:
            f = L["forearm"]
            yc = -D / 2 - f["hub_t"] / 2
            self.hub(F, "LINK3_ELBOW_HUB", 3, [0, 0, 0], [0, 1, 0], f["hub_r"], -D / 2 - f["hub_t"], -D / 2)
            self.hub_cap(F, "LINK3_ELBOW_HUB", 3, [0, 0, 0], [0, -1, 0], D / 2 + f["hub_t"], f["hub_r"] - s.p["exterior"]["hub_chamfer_mm"] - 2)
            self.bar(F, "LINK3_FOREARM_BAR", 3, [0, yc, 0], [f["tube_len"], yc, 0], f["bar_half_w"], f["bar_half_h"], f["bar_chamfer"],
                     end_edge_y=-math.sqrt((s.RC - 0.5) ** 2 - f["bar_half_h"] ** 2))
            self.module(F, 4, 3, s.offs[3], s.axes[3])
        elif k == 4:
            w = L["wrist1"]
            x0, x1 = D / 2, s.offs[4][0] - w["neck_gap"]
            self.prism("LINK4_NECK", 4, "body", F.p([x0, 0, 0]), F.d([0, 1, 0]), F.d([0, 0, 1]),
                       octagon(w["neck_w"] / 2, w["neck_h"] / 2, w["neck_chamfer"]), x1 - x0)
            self.module(F, 5, 4, s.offs[4], s.axes[4])
        elif k == 5:
            w = L["wrist2"]
            yc = D / 2 + w["hub_t"] / 2
            self.hub(F, "LINK5_WRIST_HUB", 5, [0, 0, 0], [0, 1, 0], w["hub_r"], D / 2, D / 2 + w["hub_t"])
            self.hub_cap(F, "LINK5_WRIST_HUB", 5, [0, 0, 0], [0, 1, 0], D / 2 + w["hub_t"], w["hub_r"] - s.p["exterior"]["hub_chamfer_mm"] - 2,
                         slash_scale=0.8)
            self.bar(F, "LINK5_WRIST_BAR", 5, [0, yc, 0], [w["tube_len"], yc, 0], w["bar_half_w"], w["bar_half_h"], w["bar_chamfer"],
                     end_edge_y=math.sqrt((s.RC - 0.5) ** 2 - w["bar_half_h"] ** 2))
            self.module(F, 6, 5, s.offs[5], s.axes[5])
        else:
            if s.control != "owner_both":
                self.tool_flange(F, 6)
            if s.control != "drop_ring":
                t, T = L["tool"], s.TOOL
                f1 = D / 2 + t["flange_t"]
                # MP9 2 단계: 옛 민트 고리 → 그리퍼 받침 맞춤 홈에 들어가는 돌기(이름 · 색 그대로)
                self.revolve(F, "LINK6_TOOL_RING", 6, "highlight", [0, 0, 0], [1, 0, 0],
                             [(f1, 0), (f1, T["boss_r"]), (f1 + T["boss_t"], T["boss_r"]), (f1 + T["boss_t"], 0)])

    def tool_flange(self, F6, link_tag):
        """공구 플랜지 — F6 = 링크 6 프레임. 양성 대조 owner_both 는 같은 형상을 Link5 컴포넌트 · 링크 5 표지로 만든다."""
        D, t = self.s.D, self.s.p["links"]["tool"]
        tc = t["flange_chamfer"]
        self.revolve(F6, "LINK6_TOOL_FLANGE", link_tag, "frame", [0, 0, 0], [1, 0, 0],
                     [(D / 2, 0), (D / 2, t["flange_r"]), (D / 2 + t["flange_t"] - tc, t["flange_r"]), (D / 2 + t["flange_t"], t["flange_r"] - tc),
                      (D / 2 + t["flange_t"], 0)])
        # MP9 2 단계: 그리퍼 팔 나사(M3)의 열압입 인서트 구멍 넷 — 플랜지 면에서 hole_depth 만큼(면 위로 0.5 더 파서 면을 확실히 뚫음)
        T = self.s.TOOL
        x1 = D / 2 + t["flange_t"]
        depth = T["hole_depth"] + (1.0 if self.s.control == "tool_hole_deeper" else 0.0)
        x0 = x1 - depth
        ph = T["phase_deg"] + (45.0 if self.s.control == "tool_holes_rotated" else 0.0)
        for i in range(0 if self.s.control == "tool_holes_dropped" else T["count"]):
            a = math.radians(ph + i * 360.0 / T["count"])
            nm = f"LINK6_TOOL_FLANGE_SCREW{i}"
            self.cmd("sketch.create", name=nm + "_PROFILE", plane={"origin": F6.p([x0, 0, 0]), "x_dir": F6.d([0, 1, 0]), "y_dir": F6.d([0, 0, 1])})
            self.cmd("sketch.circle.center", center=[round(T["pcd"] / 2 * math.cos(a), 6), round(T["pcd"] / 2 * math.sin(a), 6)], radius=T["hole_d"] / 2)
            self.cmd("sketch.finish")
            self.cmd("solid.extrude", distance=depth + 0.5, direction="positive", operation="cut", targets=["LINK6_TOOL_FLANGE"], name=nm + "_CUT")
