# -*- coding: utf-8 -*-
"""MP8 — 첫 그리퍼 KG1 의 형상(SolidCraft 명령). 수치의 권위는 parameters.json 과 끼움 원장(print-fits.json — values + pending).

좌표 G: 원점 = 팔 공구 플랜지에 닿는 면의 가운데 · +z = 다가가는 쪽 · x = 턱이 움직이는 쪽 · y = 깊이. 닫힌 자세(u = 0 · 두 손끝 면이 x = 0 에서 맞닿음)로 그린다.
턱 A 는 −x 로, 턱 B 는 +x 로 u 만큼 열린다 · 피니언은 +y 축을 θ = −u / r 만큼 돈다(위 이 끝이 −x 로).

부품: BASE(원판 · 판 · 받침 기둥 둘 · 서보 벽 · 버팀 둘 · 서보 받침 턱) · JAW_A(슬리브 · 위 랙 · 손끝 대) · JAW_B(슬리브 · 손끝 대 · 세운 벽 · 갈비 · 아래 랙) ·
PINION · PAD_A_FLAT / PAD_B_FLAT / PAD_A_V / PAD_B_V(손끝 — 나사 둘로 교체) · 시험편: FIT_BLOCK(Ø6 관 구멍 · M3 꼭 맞는 구멍) · FIT_MESH(핀 + 랙 막대 둘 자리) ·
FIT_RACK_A(눕혀 출력 — 턱 A 와 같은 층 방향) · FIT_RACK_B(세워 출력 — 턱 B 와 같은 층 방향) · FIT_PINION_*(백래시 시험 피니언).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


# ---------------- 입력 ----------------
def load_params(path=HERE / "parameters.json"):
    """parameters.json + 원장 값(fits_from 의 values · pending 키만). parameters 에 끼움 키가 있으면 멈춘다."""
    path = Path(path)
    P = json.loads(path.read_text(encoding="utf-8"))
    src = P["fits_from"]
    ledger_path = (path.parent / src["ledger"]).resolve()
    mat = json.loads(ledger_path.read_text(encoding="utf-8"))["materials"][src["material"]]
    want = set(src["values"]) | set(src["pending"])

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    clash = sorted(want & set(keys({k: v for k, v in P.items() if k != "fits_from"})))
    if clash:
        raise ValueError(f"fit keys written in {path.name}: {clash} - edit {ledger_path.name} instead")
    fits, status = {}, {}
    for k in src["values"]:
        fits[k] = float(mat["values"][k]["value"])
        status[k] = mat["values"][k]["status"]
    for k in src["pending"]:
        fits[k] = float(mat["pending"][k]["value"])
        status[k] = mat["pending"][k]["status"]
    P["fits"] = fits
    P["fit_status"] = status
    return P


# ---------------- 기어 윤곽 ----------------
def inv(a):
    return math.tan(a) - a


def pinion_outline(P, thinning, cx=0.0, cz=0.0, n_flank=14, n_arc=6):
    """피니언 바깥 윤곽(x, z) — 이 0 의 가운데가 +z(90°) · 인벌류트 옆면 · 이뿌리 원 · 이끝 원. 피치선 이 두께에서 thinning 을 뺀다."""
    g = P["gear"]
    m, z, a = g["module"], g["teeth"], math.radians(g["pressure_angle_deg"])
    r = m * z / 2
    rb, ra, rf = r * math.cos(a), r + g["addendum"] * m, r - g["dedendum"] * m
    psi_p = (math.pi * m / 2 - thinning) / (2 * r)          # 피치원에서 이 반각

    def psi(rho):
        return psi_p + inv(a) - inv(math.acos(rb / rho))

    r0 = max(rb, rf)
    rhos = [r0 + (ra - r0) * i / n_flank for i in range(n_flank + 1)]
    pts = []
    pitch_ang = 2 * math.pi / z
    for k in range(z):
        c = math.pi / 2 + k * pitch_ang
        # 이뿌리(앞 이의 뒤쪽 옆면 끝 → 이 이의 앞쪽 옆면 시작) — 원호
        a0 = c - pitch_ang + psi(r0)
        a1 = c - psi(r0)
        for i in range(n_arc + 1):
            t = a0 + (a1 - a0) * i / n_arc
            pts.append((rf * math.cos(t), rf * math.sin(t)))
        if rf < rb:                                          # 기초원 아래 = 반지름 선
            pts.append((rb * math.cos(c - psi(rb)), rb * math.sin(c - psi(rb))))
        for rho in rhos:                                     # 앞쪽 옆면(각이 작은 쪽) 바깥으로
            t = c - psi(rho)
            pts.append((rho * math.cos(t), rho * math.sin(t)))
        ta0, ta1 = c - psi(ra), c + psi(ra)
        for i in range(1, n_arc):
            t = ta0 + (ta1 - ta0) * i / n_arc
            pts.append((ra * math.cos(t), ra * math.sin(t)))
        for rho in reversed(rhos):
            t = c + psi(rho)
            pts.append((rho * math.cos(t), rho * math.sin(t)))
        if rf < rb:
            pts.append((rb * math.cos(c + psi(rb)), rb * math.sin(c + psi(rb))))
    out = []
    for x, y in pts:                                         # 같은 점 겹침 제거
        q = (round(cx + x, 5), round(cz + y, 5))
        if not out or abs(out[-1][0] - q[0]) > 1e-6 or abs(out[-1][1] - q[1]) > 1e-6:
            out.append(q)
    return out


def rack_outline(P, thinning, x0, x1, z_pitch, tip_dir, z_back):
    """랙 윤곽(x, z) — 피치선 z_pitch · 이끝이 tip_dir(−1 = 아래 · +1 = 위)쪽 · 등 = z_back. 이 가운데 = (k + 1/2) p(x = 0 이 이 사이 가운데)."""
    g = P["gear"]
    m, a = g["module"], math.radians(g["pressure_angle_deg"])
    p = math.pi * m
    ha, hf = g["addendum"] * m, g["dedendum"] * m
    s = p / 2 - thinning
    tip_z, root_z = z_pitch + tip_dir * ha, z_pitch - tip_dir * hf
    half_tip, half_root = s / 2 - ha * math.tan(a), s / 2 + hf * math.tan(a)
    edge = []
    k0, k1 = math.floor(x0 / p) - 1, math.ceil(x1 / p) + 1
    for k in range(k0, k1 + 1):
        c = (k + 0.5) * p
        for x, zz in ((c - half_root, root_z), (c - half_tip, tip_z), (c + half_tip, tip_z), (c + half_root, root_z)):
            edge.append((x, zz))
    # x0 ~ x1 로 자른다(잘린 이는 그 x 에서 선형 보간)
    clipped = []
    for i in range(len(edge) - 1):
        (xa, za), (xb, zb) = edge[i], edge[i + 1]
        if xb < x0 or xa > x1:
            continue
        if xa < x0 <= xb:
            clipped.append((x0, za + (zb - za) * (x0 - xa) / (xb - xa) if xb != xa else za))
        if x0 <= xa <= x1:
            clipped.append((xa, za))
        if xa < x1 <= xb:
            clipped.append((x1, za + (zb - za) * (x1 - xa) / (xb - xa) if xb != xa else za))
    if clipped[-1][0] < x1:
        clipped.append((x1, root_z))
    pts = [(x0, z_back)] + clipped + [(x1, z_back)]
    out = []
    for x, zz in pts:
        q = (round(x, 5), round(zz, 5))
        if not out or abs(out[-1][0] - q[0]) > 1e-6 or abs(out[-1][1] - q[1]) > 1e-6:
            out.append(q)
    return out


# ---------------- SolidCraft 명령 ----------------
class SC:
    def __init__(self):
        self.commands = []
        self.holes = []      # (몸체, 축 'x'|'y'|'z', 중심 두 좌표, 구간 [a, b], 지름, 이름, 종류)

    def cmd(self, c, **p):
        self.commands.append({"command": c, "params": p})

    def _sketch(self, name, plane, pts):
        self.cmd("sketch.create", name=name, plane=plane)
        self.cmd("sketch.line", points=[[round(float(u), 5), round(float(v), 5)] for u, v in pts], closed=True)
        self.cmd("sketch.finish")

    # 평면 · 법선: XZ(+y) · YZ(+x) · XY(+z)
    @staticmethod
    def plane(axis, at):
        if axis == "y":
            return {"origin": [0.0, float(at), 0.0], "x_dir": [1, 0, 0], "y_dir": [0, 0, -1]}, (lambda x, z: (x, -z))
        if axis == "x":
            return {"origin": [float(at), 0.0, 0.0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]}, (lambda y, z: (y, z))
        return {"origin": [0.0, 0.0, float(at)], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}, (lambda x, y: (x, y))

    def prism(self, name, axis, a, b, pts, op="new", target=None):
        """axis 방향으로 [a, b] 를 채우는 기둥 — pts = 그 축에 수직인 평면의 (첫 좌표, 둘째 좌표): y 축이면 (x, z) · x 축이면 (y, z) · z 축이면 (x, y)."""
        pl, f = self.plane(axis, a)
        self._sketch(f"{name}_SK", pl, [f(u, v) for u, v in pts])
        if op == "new":
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="new", body_name=name, name=f"{name}_X")
        else:
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="cut", targets=[target], name=f"{name}_X")

    def box(self, name, xr, yr, zr, op="new", target=None):
        self.prism(name, "z", zr[0], zr[1], [(xr[0], yr[0]), (xr[1], yr[0]), (xr[1], yr[1]), (xr[0], yr[1])], op, target)

    def circle_prism(self, name, axis, a, b, c1, c2, dia, op="new", target=None, seg=None):
        pl, f = self.plane(axis, a)
        u, v = f(c1, c2)
        self.cmd("sketch.create", name=f"{name}_SK", plane=pl)
        self.cmd("sketch.circle.center", center=[round(float(u), 5), round(float(v), 5)], radius=float(dia) / 2)
        self.cmd("sketch.finish")
        if op == "new":
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="new", body_name=name, name=f"{name}_X")
        else:
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="cut", targets=[target], name=f"{name}_X")

    def hole(self, body, axis, a, b, c1, c2, dia, tag, kind):
        self.circle_prism(f"{body}_H_{tag}", axis, a, b, c1, c2, dia, op="cut", target=body)
        self.holes.append({"body": body, "axis": axis, "c": [float(c1), float(c2)], "span": [float(a), float(b)], "dia": float(dia),
                           "tag": tag, "kind": kind})

    def join(self, target, tools):
        self.cmd("solid.combine", target=target, tools=list(tools), operation="join")

    def color(self, body, hexcolor):
        self.cmd("appearance.assign", bodies=[body], color=hexcolor)


def stadium(c1, c2, r, half_len):
    """c2 방향으로 ±half_len 늘린 둥근 홈(점 목록)."""
    pts = []
    for i in range(13):
        t = math.pi + math.pi * i / 12
        pts.append((c1 + r * math.cos(t), c2 - half_len + r * math.sin(t)))
    for i in range(13):
        t = math.pi * i / 12
        pts.append((c1 + r * math.cos(t), c2 + half_len + r * math.sin(t)))
    return pts


# ---------------- 부품 ----------------
WHITE, NAVY, GRAY, MINT = "#FFFFFF", "#0B2545", "#6B7280", "#34D399"


def derived(P):
    g, L = P["gear"], P["layout"]
    r = g["module"] * g["teeth"] / 2
    zc = L["z_c"]
    return {"r": r, "zc": zc, "pA": zc + r, "pB": zc - r, "ha": g["addendum"] * g["module"], "hf": g["dedendum"] * g["module"],
            "rack_a_top": P["jaw_a"]["sleeve_z"][0] - 0.5, "rack_b_bottom": L["base_top"] + 0.5}


def build_base(sc, P):
    L, F, S = P["layout"], P["fits"], P["servo"]
    n = "BASE"
    sc.box(n, (-L["base_x"], L["base_x"]), tuple(L["base_y"]), (0.0, L["base_top"]))
    parts = []
    sc.circle_prism(n + "_DISC", "z", 0.0, L["base_top"], 0.0, 0.0, L["disc_dia"]); parts.append(n + "_DISC")
    for side, (x0, x1) in (("R", L["post_x"]), ("L", (-L["post_x"][1], -L["post_x"][0]))):
        sc.box(f"{n}_POST_{side}", (x0, x1), tuple(L["post_y"]), (L["base_top"], L["post_top"])); parts.append(f"{n}_POST_{side}")
    sc.box(n + "_WALL", tuple(L["wall_x"]), tuple(L["wall_y"]), (L["base_top"], L["wall_top"])); parts.append(n + "_WALL")
    for i, gx in enumerate(L["gusset_x"]):
        sc.box(f"{n}_GUSSET_{i}", tuple(gx), tuple(L["gusset_y"]), (L["base_top"], L["wall_top"])); parts.append(f"{n}_GUSSET_{i}")
    zc = L["z_c"]
    # 서보 받침 턱(벽 뒤 · 서보 아래 옆면 z = z_c − 폭 / 2 를 받침 — 조일 때 서보를 이 턱에 눌러 댄다) · 아래 면은 약 50° 빗면
    led = L["servo_ledge"]
    zs = zc - S["body"][1] / 2
    y0 = L["wall_y"][0]
    sc.prism(n + "_LEDGE", "x", led["x"][0], led["x"][1], [(y0, zs - led["height"]), (y0, zs), (y0 - led["depth"], zs)]); parts.append(n + "_LEDGE")
    sc.join(n, parts)
    # 맞춤 오목 홈(아랫면 · 팔 쪽 Ø20 돌기를 받음 — 아랫면을 판에 대고 출력하므로 돌기 대신 홈)
    sc.circle_prism(n + "_RECESS", "z", -0.5, L["recess_depth"], 0.0, 0.0, L["recess_dia"], op="cut", target=n)
    # 서보 축 · 혼 구멍(벽을 y 로 관통)
    sc.hole(n, "y", L["wall_y"][0] - 0.5, L["wall_y"][1] + 0.5, 0.0, zc, L["horn_hole_dia"], "HORN", "clearance_horn")
    # 서보 위면 M2 자리 넷 — z 방향 홈(위면 폭 간격 20.1 ~ 20.5 를 받음)
    half = (S["top_holes_width_spacing_range"][1] - S["top_holes_width_spacing_range"][0]) / 2
    for i, s in enumerate(S["top_holes_from_out_end"]):
        x = s - S["spline_from_out_end"]
        for j, sgn in enumerate((-1, 1)):
            zz = zc + sgn * (S["top_holes_width_spacing"] / 2 - half / 2)
            tag = f"SERVO_{i}{j}"
            pts = stadium(x, zz, F["m2_clearance_dia"] / 2, half / 2 + 0.2)
            sc.prism(f"{n}_S_{tag}", "y", L["wall_y"][0] - 0.5, L["wall_y"][1] + 0.5, pts, op="cut", target=n)
            # M2 머리(지름 ≤ 3.8 · 높이 ≤ 1.6 — parameters screws.servo_m2) 자리파기 Ø4.0 × 1.8. 위 둘은 벽 꼭대기 밖까지 늘린 홈 하나로 터 둔다
            # (꼭대기에 0.05 껍질이 남던 것 — 검토 G06 · 상자를 덧대면 면이 겹쳐 열린 메시가 됨)
            hl = half / 2 + 0.2
            if sgn > 0:
                z_lo, z_hi = zz - hl, L["wall_top"] + 0.5 + 2.0
                cb = stadium(x, (z_lo + z_hi) / 2, 2.0, (z_hi - z_lo) / 2)
            else:
                cb = stadium(x, zz, 2.0, hl)
            sc.prism(f"{n}_CB_{tag}", "y", L["wall_y"][1] - 1.8, L["wall_y"][1] + 0.5, cb, op="cut", target=n)
            sc.holes.append({"body": n, "axis": "y", "c": [x, zz], "span": [L["wall_y"][0], L["wall_y"][1]], "dia": F["m2_clearance_dia"],
                             "tag": tag, "kind": "m2_clearance_slot", "slot_half_len": half / 2 + 0.2})
    # 봉 구멍(기둥 둘을 x 로 관통) — 관은 L 기둥(미끄럼)으로 넣어 두 슬리브를 지나 R 기둥에만 눌러 끼운다(긴 거리를 꼭 끼움 구멍으로 밀지 않게 — 검토 R-14)
    kind_of = {P["rod"]["insert_from"]: ("rod_slide", F["rod_slide_hole_dia"])}
    for side, (x0, x1) in (("R", L["post_x"]), ("L", (-L["post_x"][1], -L["post_x"][0]))):
        kind, dia = kind_of.get(side, ("rod_press", F["rod_press_hole_dia"]))
        for k, yy in enumerate(L["rod_y_a"] + L["rod_y_b"]):
            sc.hole(n, "x", x0 - 0.5, x1 + 0.5, yy, L["rod_z"], dia, f"ROD_{side}{k}", kind)
    # 맞춤 홈(앞면 · x = 0 · 세로 — x = 0 의 앞면은 판(base_y[1])과 원판(지름 / 2) 중 앞선 것) — 두 손끝이 맞닿는 선이 이 홈 위에 와야 두 턱이 같은 이에 물린 것
    gv = L["align_groove"]
    yf = max(L["base_y"][1], L["disc_dia"] / 2)
    sc.box(n + "_GROOVE", (-gv["width"] / 2, gv["width"] / 2), (yf - gv["depth"], yf + 0.5), (-0.5, L["base_top"] + 0.5), op="cut", target=n)
    # 팔 쪽 나사 넷(z 관통 · 위에서 자리파기)
    pcd, ph = L["arm_screw_pcd"], math.radians(L["arm_screw_phase_deg"])
    cbd, cbh = L["arm_screw_cbore"]
    for i in range(4):
        x, y = pcd / 2 * math.cos(ph + i * math.pi / 2), pcd / 2 * math.sin(ph + i * math.pi / 2)
        sc.hole(n, "z", -0.5, L["base_top"] + 0.5, x, y, F["m3_clearance_dia"], f"ARM_{i}", "m3_clearance")
        sc.circle_prism(f"{n}_ACB_{i}", "z", L["base_top"] - cbh, L["base_top"] + 0.5, x, y, cbd, op="cut", target=n)
    for i, (x, y) in enumerate(L["camera_holes"]):
        sc.hole(n, "z", -0.5, L["base_top"] + 0.5, x, y, F["m3_clearance_dia"], f"CAM_{i}", "m3_clearance")
    sc.color(n, GRAY)
    return n


def bores(sc, body, P, jaw, ys, xr):
    """슬리브의 봉 구멍: 양 끝 bearing_len 은 미끄럼 지름 · 가운데는 relief 지름."""
    J, F, L = P[jaw], P["fits"], P["layout"]
    bl = J["bearing_len"]
    for k, yy in enumerate(ys):
        sc.hole(body, "x", xr[0] - 0.5, xr[1] + 0.5, yy, L["rod_z"], F["rod_slide_hole_dia"], f"ROD{k}", "rod_slide")
        sc.holes[-1]["bearing_spans"] = [[xr[0], xr[0] + bl], [xr[1] - bl, xr[1]]]
        sc.hole(body, "x", xr[0] + bl, xr[1] - bl, yy, L["rod_z"], J["relief_dia"], f"REL{k}", "relief")


def build_jaw_a(sc, P):
    J, L, F, d = P["jaw_a"], P["layout"], P["fits"], derived(P)
    n = "JAW_A"
    xr, yr, zr = J["local_x"], J["sleeve_y"], J["sleeve_z"]
    sc.box(n, tuple(xr), tuple(yr), tuple(zr))
    parts = []
    # 위 랙(이끝 아래) — y 띠 전체, 위는 슬리브 밑 0.5 아래까지 · 슬리브와 겹치는 y ≤ 0 은 슬리브까지 잇는다
    gy = L["gear_band_y"]
    rx = P["rack"]["local_x_a"]
    out = rack_outline(P, F["gear_thinning_rack"], rx[0], rx[1], d["pA"], -1, d["rack_a_top"])
    sc.prism(n + "_RACK", "y", gy[0], gy[1], out); parts.append(n + "_RACK")
    sc.box(n + "_RACK_JOIN", tuple(rx), (gy[0], yr[1]), (d["rack_a_top"] - 0.5, zr[0])); parts.append(n + "_RACK_JOIN")
    # 랙 뒤(−y) 45° 쐐기 — y 를 위로 세워 출력할 때 랙 밑을 받친다(벽 위 · 서보 위를 지나지 않게: 벽 꼭대기 < 쐐기 밑)
    tip_z = d["pA"] - d["ha"]
    wedge = [(gy[0], tip_z), (gy[0], zr[0]), (gy[0] - (zr[0] - tip_z), zr[0])]
    sc.prism(n + "_RACK_WEDGE", "x", rx[0], rx[1], wedge); parts.append(n + "_RACK_WEDGE")
    # 손끝 대 — 슬리브 위(y ≤ 0)는 슬리브에 붙고, 턱 B 슬리브 위(y > 0)는 0.5 띄움
    sx = J["stalk_x"]
    sc.box(n + "_STALK", tuple(sx), (yr[0], 0.0), (zr[1], J["stalk_top"])); parts.append(n + "_STALK")
    sc.box(n + "_STALK2", tuple(sx), (0.0, P["pad"]["y"][1]), (zr[1] + 0.5, J["stalk_top"])); parts.append(n + "_STALK2")
    sc.join(n, parts)
    bores(sc, n, P, "jaw_a", L["rod_y_a"], xr)
    # 손끝 인서트(대의 +y 면에서 −y 로 — 이 부품은 y 를 위로 세워 출력하므로 세로 구멍)
    ytop = P["pad"]["y"][1]
    for i, zz in enumerate(J["pad_insert_z"]):
        sc.hole(n, "y", ytop - J["pad_insert_depth"], ytop + 0.5, J["pad_insert_x"], zz, F["insert_hole_dia"], f"PAD{i}", "insert")
    sc.color(n, WHITE)
    return n


def build_jaw_b(sc, P):
    J, L, F, d = P["jaw_b"], P["layout"], P["fits"], derived(P)
    n = "JAW_B"
    xr, yr, zr = J["local_x"], J["sleeve_y"], J["sleeve_z"]
    sc.box(n, tuple(xr), tuple(yr), tuple(zr))
    parts = []
    hy = J["hanger_y"]
    sc.box(n + "_HANGER", tuple(xr), tuple(hy), (d["rack_b_bottom"], zr[0])); parts.append(n + "_HANGER")
    for i, xc in enumerate(J["rib_local_x"]):           # 45° 갈비(슬리브 밑을 받침 — z 를 위로 출력)
        t = J["rib_t"] / 2
        tri = [(hy[1], zr[0]), (yr[1], zr[0]), (hy[1], zr[0] - (yr[1] - hy[1]))]
        sc.prism(f"{n}_RIB{i}", "x", xc - t, xc + t, tri); parts.append(f"{n}_RIB{i}")
    gy = L["gear_band_y"]
    rx = (-P["rack"]["local_x_a"][1], -P["rack"]["local_x_a"][0])
    out = rack_outline(P, F["gear_thinning_rack"], rx[0], rx[1], d["pB"], +1, d["rack_b_bottom"])
    sc.prism(n + "_RACK", "y", gy[0], hy[0], out); parts.append(n + "_RACK")
    # 손끝 대 — 슬리브 위 + 손끝 쪽(y < 5.5)으로 45° 쐐기(z 를 위로 출력해도 받침 없이)
    sx = J["stalk_x"]
    sc.box(n + "_STALK", tuple(sx), tuple(yr), (zr[1], J["stalk_top"])); parts.append(n + "_STALK")
    y0 = P["pad"]["y"][0]
    z0 = zr[1] + 0.5
    wedge = [(yr[0], z0), (yr[0], J["stalk_top"]), (y0, J["stalk_top"]), (y0, z0 + (yr[0] - y0))]
    sc.prism(n + "_WEDGE", "x", sx[0], sx[1], wedge); parts.append(n + "_WEDGE")
    sc.join(n, parts)
    bores(sc, n, P, "jaw_b", L["rod_y_b"], xr)
    for i, yy in enumerate(J["cap_insert_y"]):            # 손끝 덮개 인서트(대 윗면에서 −z — z 를 위로 출력하므로 세로 구멍)
        sc.hole(n, "z", J["stalk_top"] - J["cap_insert_depth"], J["stalk_top"] + 0.5, J["cap_insert_x"], yy, F["insert_hole_dia"], f"CAP{i}", "insert")
    sc.color(n, WHITE)
    return n


def build_pinion(sc, P, name, thinning, offset=(0.0, 0.0, 0.0)):
    """피니언 — 앞면 = gear_band_y[1] · 이 너비 face_width(뒤로) · 그 뒤 허브(혼 바깥면에 앉음). 나사 넷 = 꼭 맞는 구멍(혼 위 가운데 맞춤)."""
    g, L, F = P["gear"], P["layout"], P["fits"]
    gy = L["gear_band_y"]
    ox, oy, oz = offset
    cz = L["z_c"] + oz
    y_top = gy[1] + oy
    y_face = y_top - g["face_width"]
    y_bot = y_face - g["hub_len"]
    out = pinion_outline(P, thinning, ox, cz)
    sc.prism(name, "y", y_face, y_top, out)
    sc.circle_prism(name + "_HUB", "y", y_bot, y_face, ox, cz, g["hub_dia"])
    sc.join(name, [name + "_HUB"])
    sc.hole(name, "y", y_bot - 0.5, y_top + 0.5, ox, cz, g["centre_hole"], "CENTRE", "clearance_horn_screw")
    cbd, cbh = g["screw_cbore"]
    for i in range(g["screw_count"]):
        a = math.radians(g["screw_phase_deg"]) + i * 2 * math.pi / g["screw_count"]
        x, z = ox + g["screw_pcd"] / 2 * math.cos(a), cz + g["screw_pcd"] / 2 * math.sin(a)
        sc.hole(name, "y", y_bot - 0.5, y_top + 0.5, x, z, F["m3_close_hole_dia"], f"S{i}", "m3_close")
        sc.circle_prism(f"{name}_CB{i}", "y", y_top - cbh, y_top + 0.5, x, z, cbd, op="cut", target=name)
    sc.color(name, NAVY)
    return name


def build_pads(sc, P):
    J, Q, F = P["jaw_a"], P["pad"], P["fits"]
    JB = P["jaw_b"]
    t, ch = Q["t"], Q["tip_chamfer"]
    z0, z1 = Q["z"]
    names = []
    for kind in ("FLAT", "V"):
        # 손끝 A — 맞닿는 면 x = 0 · 판 x [−t, 0] · 끝(+z) 바깥쪽 45° 모따기
        n = f"PAD_A_{kind}"
        prof = [(-t, z0), (0.0, z0), (0.0, z1), (-(t - ch) if ch < t else -1.0, z1), (-t, z1 - ch)]
        sc.prism(n, "y", Q["y"][0], Q["y"][1] + Q["flange_t_a"], prof)
        sx = J["stalk_x"]
        sc.box(n + "_FL", (sx[0], -t), (Q["y"][1], Q["y"][1] + Q["flange_t_a"]), (J["pad_insert_z"][0] - 8.0, z1 - ch))
        sc.join(n, [n + "_FL"])
        for i, zz in enumerate(J["pad_insert_z"]):
            sc.hole(n, "y", Q["y"][1] - 0.5, Q["y"][1] + Q["flange_t_a"] + 0.5, J["pad_insert_x"], zz, F["m3_clearance_dia"], f"S{i}", "m3_clearance")
        names.append(n)
        # 손끝 B — 맞닿는 면 x = 0 · 판 x [0, t] · 대 윗면을 덮는 덮개(나사 z)
        n = f"PAD_B_{kind}"
        prof = [(0.0, z0), (t, z0), (t, z1 - ch), (t - ch if ch < t else 1.0, z1), (0.0, z1)]
        sc.prism(n, "y", Q["y"][0], Q["y"][1], prof)
        sxb = JB["stalk_x"]
        sc.box(n + "_CAP", (0.0, sxb[1]), (Q["y"][0], JB["sleeve_y"][1]), (JB["stalk_top"], JB["stalk_top"] + Q["cap_t_b"]))
        sc.join(n, [n + "_CAP"])
        for i, yy in enumerate(JB["cap_insert_y"]):
            sc.hole(n, "z", JB["stalk_top"] - 0.5, JB["stalk_top"] + Q["cap_t_b"] + 0.5, JB["cap_insert_x"], yy, F["m3_clearance_dia"], f"S{i}", "m3_clearance")
        names.append(n)
        if kind == "V":                                  # 세로(z) V 홈 — 둥근 출력물 가운데 맞춤
            dv = Q["v_depth"]
            w = dv * math.tan(math.radians(45))             # 90° 홈 — 맞닿는 면을 판에 대고 출력해도 홈 면이 45°
            for nm, sgn in (("PAD_A_V", -1), ("PAD_B_V", 1)):
                # x-y 단면 삼각형(맞닿는 면 x = 0 에서 판 쪽으로 깊이 dv · 꼭지각 90°) — z 로 끝까지
                pts = [(-sgn * 0.5, -w - 0.5), (sgn * dv, 0.0), (-sgn * 0.5, w + 0.5)]
                sc.prism(f"{nm}_VG", "z", z0 - 0.5, z1 + 0.5, pts, op="cut", target=nm)
    for n in names:
        sc.color(n, GRAY)
    return names


def mark_notches(sc, body, count, xr, yc, z_top, tag):
    """윗면 홈 count 개(y 로 1.5 간격 · 폭 0.8 · 깊이 0.6) = 구멍 순번."""
    for k in range(count):
        yn = yc - 3.75 + 1.5 * k
        sc.box(f"{body}_N{tag}_{k}", tuple(xr), (yn, yn + 0.8), (z_top - 0.6, z_top + 0.5), op="cut", target=body)


def build_coupon(sc, P, at):
    """끼움 시험편 판(KG1_FIT) — 모두 모형 그대로(z 위) 출력, FIT_PINION_* 만 피니언과 같은 y 아래."""
    C, F, g = P["fit_coupon"], P["fits"], P["gear"]
    n = "FIT_BLOCK"
    _bx, bz = C["block"]
    ny = len(C["holes"])
    x0, y0 = at
    hl = C["hole_len"]
    sc.box(n, (x0, x0 + hl), (y0, y0 + ny * C["pitch"]), (0.0, bz))
    # M3 꼭 맞는 구멍 날개(블록 +y 끝에 붙임 · 세로 구멍 — 피니언 나사 구멍과 같은 출력 방향 · 관 구멍 출구를 막지 않게 x 쪽이 아니라 y 끝)
    tx, ty, tz = C["m3_tab"]
    ty0 = y0 + ny * C["pitch"]
    sc.box(n + "_TAB", (x0, x0 + tx), (ty0, ty0 + ty), (0.0, tz))
    sc.join(n, [n + "_TAB"])
    for i, dia in enumerate(C["holes"]):
        yc = y0 + C["pitch"] * (i + 0.5)
        sc.hole(n, "x", x0 - 0.5, x0 + hl + 0.5, yc, bz / 2, dia, f"T{i}", "coupon_rod")
        mark_notches(sc, n, i + 1, (x0 + 1.0, x0 + hl - 1.0), yc, bz, f"T{i}")
    nm3 = len(C["m3_close_holes"])
    for i, dia in enumerate(C["m3_close_holes"]):
        yc = ty0 + ty / nm3 * (i + 0.5)
        sc.hole(n, "z", -0.5, tz + 0.5, x0 + 4.5, yc, dia, f"M{i}", "coupon_m3")
        mark_notches(sc, n, i + 1, (x0 + 7.0, x0 + tx - 1.0), yc, tz, f"M{i}")
    sc.color(n, WHITE)
    names = [n]
    # 맞물림 지그: 판 + 핀(피니언 가운데 구멍에) + 바깥 벽 둘 — 랙 막대 피치선이 핀에서 r 이 되게 벽 안쪽 면 = r + 이뿌리 + 등
    J = C["mesh_jig"]
    r = g["module"] * g["teeth"] / 2
    hf = g["dedendum"] * g["module"]
    back = r + hf + J["rack_back"]
    jx, jy = x0 + 55.0, y0 + 40.0
    m = "FIT_MESH"
    sc.box(m, (jx - J["half_len"], jx + J["half_len"]), (jy - back - J["wall_t"], jy + back + J["wall_t"]), (0.0, J["plate_t"]))
    jparts = []
    for s, sgn in (("S", -1), ("N", 1)):
        ya, yb = sorted((jy + sgn * back, jy + sgn * (back + J["wall_t"])))
        sc.box(f"{m}_WALL_{s}", (jx - J["half_len"], jx + J["half_len"]), (ya, yb), (J["plate_t"], J["plate_t"] + J["wall_h"])); jparts.append(f"{m}_WALL_{s}")
    sc.circle_prism(m + "_PIN", "z", J["plate_t"], J["plate_t"] + J["pin_above_plate"], jx, jy, J["pin_dia"]); jparts.append(m + "_PIN")
    sc.join(m, jparts)
    sc.color(m, WHITE)
    names.append(m)
    # 랙 막대 A — 눕혀 출력(이 윤곽이 층 면 안 · 턱 A 와 같음): 윤곽 (x, y) · 두께 z
    th = F["gear_thinning_rack"]
    ax0, ay = x0 + 100.0, y0 + 10.0
    out = rack_outline(P, th, ax0, ax0 + J["rack_len"], ay, +1, ay - hf - J["rack_back"])
    sc.prism("FIT_RACK_A", "z", 0.0, J["rack_t"], out)
    sc.color("FIT_RACK_A", NAVY)
    names.append("FIT_RACK_A")
    # 랙 막대 B — 세워 출력(이끝 위 · 이 윤곽이 층을 가로지름 · 턱 B 와 같음): 윤곽 (x, z) · 두께 y
    by = y0 + 30.0
    out = rack_outline(P, th, ax0, ax0 + J["rack_len"], hf + J["rack_back"], +1, 0.0)
    sc.prism("FIT_RACK_B", "y", by, by + J["rack_t"], out)
    sc.color("FIT_RACK_B", NAVY)
    names.append("FIT_RACK_B")
    for i, t in enumerate(g["coupon_thinning"]):
        nm = f"FIT_PINION_{int(round(t * 100)):03d}"
        build_pinion(sc, P, nm, t, offset=(x0 + 40.0 + 36.0 * i, 0.0, -P["layout"]["z_c"] + 120.0))
        names.append(nm)
    return names


def build_all(P):
    sc = SC()
    parts = [build_base(sc, P), build_jaw_a(sc, P), build_jaw_b(sc, P), build_pinion(sc, P, "PINION", P["fits"]["gear_thinning_pinion"])]
    pads = build_pads(sc, P)
    coupon = build_coupon(sc, P, (120.0, 60.0))
    return sc, parts, pads, coupon
