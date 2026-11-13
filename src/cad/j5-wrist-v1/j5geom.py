# -*- coding: utf-8 -*-
"""MP10 — J5 손목 굽힘 관절 실부품 v1 의 형상(SolidCraft 명령). 계획 = docs/design/056-j5-wrist-real-part.md.

좌표(모듈 = MP6 좌표): z = J5 축 · z = 0 = 모터 앞 장착면 · 감속기 출력 면 z = stack_mm.output_face · x = 링크 4 의 +x(J4 → J5) · y = 링크 4 의 −z.
수치의 권위: parameters.json(형상) · cycloid.json + MP6 parameters(감속기 접속) · motor-mks42d.json(모터 · 드라이버 가정) · print-fits.json(구멍 — PLA).
parameters.json 에 끼움 키(fit_keys)가 있으면 멈춘다.

부품: J5_STATOR_A(캔 반쪽 x < 0 + J4 쪽 목) · J5_STATOR_B(캔 반쪽 x > 0) · J5_REAR_COVER · J5_OUTPUT_HUB.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARTS = ["J5_STATOR_A", "J5_STATOR_B", "J5_REAR_COVER", "J5_OUTPUT_HUB"]
CONTROLS = {"notch_rotated", "clamp_tight", "driver_small", "neck_shift", "hub_big", "cover_insert_out", "split_zero", "bolt_shallow",
            "insert_r", "ribs_low", "no_head_channel", "neck_under", "hub_under", "cover_shallow", "no_j4_relief", "term_narrow",
            "tslot_closed", "cover_insert_old_angles", "no_motor_connector"}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def octagon(hw, hh, c, cu=0.0, cv=0.0):
    """가로 반폭 hw · 세로 반높이 hh · 모서리 45° 모따기 c 인 팔각형(반시계) · 가운데 (cu, cv)."""
    pts = [(hw, -hh + c), (hw, hh - c), (hw - c, hh), (-hw + c, hh), (-hw, hh - c), (-hw, -hh + c), (-hw + c, -hh), (hw - c, -hh)]
    out = []
    for u, v in pts:                                 # c = 0 이면 겹친 점(길이 0 선 — SolidCraft 가 거부)을 뺀다
        q = (u + cu, v + cv)
        if not out or abs(out[-1][0] - q[0]) > 1e-9 or abs(out[-1][1] - q[1]) > 1e-9:
            out.append(q)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= 1e-9 and abs(out[0][1] - out[-1][1]) <= 1e-9:
        out.pop()
    return out


def clamp_profile(s):
    """조임 칸 단면(x, y · 반시계): x 면은 모터에서 rib_gap 떨어진 공기 틈이고, 갈비(y 중심 rib_y · 반폭 hw)만 모터 면(±clamp_x)에 닿는다."""
    X0, Xr, Y, hw = s.clamp_x + s.rib["gap"], s.clamp_x, s.clamp_y, s.rib["hw"]
    ys = sorted(s.rib["y"])
    pts = [(X0, -Y)]
    for y in ys:
        pts += [(X0, y - hw), (Xr, y - hw), (Xr, y + hw), (X0, y + hw)]
    pts += [(X0, Y), (-X0, Y)]
    for y in reversed(ys):
        pts += [(-X0, y + hw), (-Xr, y + hw), (-Xr, y - hw), (-X0, y - hw)]
    pts.append((-X0, -Y))
    return pts


def slash(height, width):
    """KMJH 사선(v3 와 같은 꼴) — 위 · 아래 변은 가로, 옆변은 45°. 가운데가 원점."""
    h, w = height / 2, width
    return [(-h - w / 2, -h), (-h + w / 2, -h), (h + w / 2, h), (h - w / 2, h)]


def _rect_gap(px, py, rect):
    """점 (px, py) 에서 xy 사각형 [(x0, x1), (y0, y1)] 까지의 거리(안이면 0)."""
    (x0, x1), (y0, y1) = rect
    return math.hypot(max(x0 - px, 0.0, px - x1), max(y0 - py, 0.0, py - y1))


class Spec:
    """parameters.json 과 원천 파일에서 읽고 이끌어 낸 치수(mm)."""

    def __init__(self, params_path=HERE / "parameters.json", control=None):
        assert control is None or control in CONTROLS, control
        self.control = control
        path = Path(params_path)
        P = json.loads(path.read_text(encoding="utf-8"))
        self.P = P
        src = P["sources"]
        clash = sorted(set(src["fit_keys"]) & set(_keys({k: v for k, v in P.items() if k != "sources"})))
        if clash:
            raise SystemExit(f"fit keys written in {path.name}: {clash} - they live only in the fits ledger")
        base = path.parent

        def rd(rel):
            return json.loads((base / rel).resolve().read_text(encoding="utf-8"))
        self.paths = {k: (base / src[k]).resolve() for k in ("reducer_json", "reducer_params", "motor_ledger", "fits_ledger")}
        cyc, mp6, mot, fit = rd(src["reducer_json"]), rd(src["reducer_params"]), rd(src["motor_ledger"]), rd(src["fits_ledger"])
        self.v1 = rd(src["v1_dir"] + "/parameters.json")
        mat = fit["materials"][src["material"]]["values"]
        self.fits = {k: float(mat[k]["value"]) for k in src["fit_keys"]}
        self.fit_status = {k: mat[k]["status"] for k in src["fit_keys"]}
        self.motor = {k: float(mot["items"][k]["value"]) for k in src["motor_keys"]}
        self.motor_status = {k: mot["items"][k]["status"] for k in src["motor_keys"]}
        st, rr, sc = cyc["stack_mm"], cyc["radii_mm"], cyc["screws"]
        ph = P["mp6_phases_deg"]
        self.mp6 = {
            "output_face": float(st["output_face"]), "retainer_top": float(st["retainer"][1]), "flange": [float(v) for v in st["flange"]],
            "flange_r": float(mp6["carrier"]["shoulder_dia"]) / 2,
            "outer_r": float(rr["outer"]), "cap_screw_r": float(rr["cap_screw"]), "retainer_screw_r": float(rr["retainer_screw"]),
            "output_insert_r": float(rr["output_insert"]),
            "cap_screw_n": int(mp6["housing"]["cap_screws"]), "output_insert_n": int(mp6["carrier"]["output_inserts"]),
            "head_dia": float(mp6["motor"]["screw_head_dia"]), "head_h": float(mp6["motor"]["screw_head_height"]),
            "screw_lengths": [float(v) for v in mp6["housing"]["screw_lengths_available"]],
            "flange_screw": {k: float(sc["flange"][k]) for k in ("length_mm", "engagement_mm", "tip_to_hole_floor_mm")},
            "cap_screw_len": float(sc["cap"]["length_mm"]),
            "phase": {k: float(ph[k]) for k in ("cap_screw", "output_insert", "retainer_screw")},
        }
        m, c = self.motor, P["can"]
        self.outer_r = float(c["outer_r"])
        hd = P["screw_heads"]
        self.cap_head = {k: float(hd["cap_screw_envelope"][k]) for k in ("dia", "height")}
        self.ret_head = {k: float(hd["retainer_screw"][k]) for k in ("dia", "height")}
        self.rib = {"gap": float(c["rib_gap"]), "hw": 0.5 if control == "ribs_low" else float(c["rib_half_width"]),
                    "y": [float(v) for v in c["rib_y"]]}
        self.head_channel = control != "no_head_channel"
        self.z_motor_rear = -m["body_length"]
        # 드라이버 칸 = 몸체 + 간격(가정) 뒤에서 실측 overall_length(뒤 단자대 끝까지 · 상한)까지 — 원장 driver_depth 가정은 안 읽음(MP10 다시 만들기 10/30)
        self.z_drv = [-m["overall_length"], -(m["body_length"] + m["motor_driver_gap"])]
        assert self.z_drv[1] - self.z_drv[0] > 5.0, f"driver span too short: {self.z_drv}"
        self.z_rear = self.z_drv[0] - float(c["rear_clearance"])
        self.ring_z0 = -float(c["ring_zone"])
        self.split = 0.0 if control == "split_zero" else float(c["split_gap"]) / 2
        self.clamp_x = m["frame"] / 2 - (0.5 if control == "clamp_tight" else 0.0)
        self.clamp_y = m["frame"] / 2 + float(c["clamp_side_clearance"])
        self.ring_half = m["frame"] / 2 + float(c["ring_extra"])
        self.drv_half = m["driver_width"] / 2 + float(c["driver_clearance"]) - (1.5 if control == "driver_small" else 0.0)
        self.drv_apothem = m["driver_width"] / math.sqrt(2) + float(c["driver_clearance"])
        con = P["connector"]
        self.con_side = con["side"]
        assert self.con_side == "-x", "only a -x connector side is drawn in v1"
        # 바깥 = 커넥터 가정 끝(굽힘 여유 포함 값) · 안 = 드라이버 칸 가장자리에서 0.1 겹침(천장 박공이 조임 칸과 min_wall 을 남기게)
        self.con_x = [-(m["driver_width"] / 2 + m["connector_clearance"]), -(m["driver_width"] / 2 + float(c["driver_clearance"])) + 0.1]
        self.con_y = float(con["pocket_half_width"])
        self.con_z = [self.z_drv[0] - float(c["driver_clearance"]), self.z_drv[1] + float(c["driver_clearance"])]
        # 모터 커넥터 앞 칸(다시 만들기 3 · 11/01 사용자 실측 — 모터 −x 면 뒤 뚜껑 위 6 핀 커넥터): (y, z) 단면을 x 로 밀어냄 · 지붕 = y 방향 45° 박공
        # (양 끝 벽에서 자라 오름 — x 로 기운 지붕은 모터 쪽 공중에서 시작하는 칼날 모서리라 Bambu Studio 「floating regions」 · parameters pocket_note).
        # 깊은 칸(y0 ~ deep_y_max) = 옛 칸 바깥 끝 너머까지(옛 45° 지붕을 품음) · 옆 칸(~ y1) = 커넥터 높이 + 여유까지(벽이 얇아 더 못 감) · 지붕 · 바닥 side_step 아래
        mc = P["motor_connector"]
        mm, mp_ = mc["measured"], mc["pocket"]
        y0, y1 = (float(v) for v in mp_["y"])
        zb, ze = self.z_drv[1] - float(mp_["rear_overlap"]), -(float(mm["front_from_motor_face"]) - float(mp_["front_clearance"]))
        x_in, ym, st = -(m["frame"] / 2 - float(mp_["into_motor"])), float(mp_["deep_y_max"]), float(mp_["side_step"])
        self.mconn = None if control == "no_motor_connector" else {
            "y": [y0, y1], "z_ends": ze, "ridge": [(y0 + y1) / 2, ze + (y1 - y0) / 2],
            "deep": {"x": [self.con_x[0] - float(mp_["deep_beyond_old_pocket"]), x_in], "y": [y0, ym], "z0": zb, "dz": 0.0},
            "side": {"x": [-(m["frame"] / 2 + float(mm["height_above_motor_face"]) + float(mp_["top_clearance"])), x_in],
                     "y": [ym - float(mp_["side_overlap"]), y1], "z0": zb + st, "dz": -st}}
        cs = P["cable_slot"]
        zf = [float(v) for v in cs["z_from_driver"]]
        self.slot = {"x": [-(self.outer_r + 1.0), self.con_x[0] + 1.0], "y": float(cs["half_width"]), "z": [self.z_drv[0] + zf[0], self.z_drv[1] - zf[1]]}
        # 단자대 칸 · 이음 자리 창(±y · 두 반쪽에 반씩 — 사용자 「양옆 단자를 이음 쪽으로 (권장)」 10/30): 칸 = (x, z) 상자 + 이음 쪽 45° 박공 ·
        # 창 = 뒤 끝면 기준 상자 + 박공(조임 귀 45° 밑면보다 아래) · 바깥 끝은 조임 귀 너머(parameters terminals 의 메모들)
        tm = P["terminals"]
        assert sorted(tm["sides"]) == ["+y", "-y"], "terminal pockets are drawn only on +-y in v1"
        # 칸 = y 로 밀어낸 (x, z) 단면: 바닥 ~ 옆 높이(커넥터 칸 위와 같음)는 상자 · 그 위 45° 박공(꼭대기 = 이음) — 안쪽은 조임 칸 · 깔때기와 합쳐짐(roof_note)
        self.term = {"x": float(tm["pocket_half_width"]), "z": list(self.con_z),
                     "y": [self.clamp_y - float(tm["inner_into_clamp_pocket"]),
                           m["driver_width"] / 2 + m["connector_clearance"] - (1.5 if control == "term_narrow" else 0.0)]}
        lg0, tw = P["clamp_bolts"]["lug"], tm["window"]
        self.tslot = {"x": float(tw["half_width"]), "z": [self.z_rear + float(tw["z_from_rear"][0]), self.z_rear + float(tw["z_from_rear"][1])],
                      "y": [self.term["y"][1] - 1.0, self.outer_r + float(lg0["out"]) + 1.0]}
        self.route = P["cable_route"]
        self.notch_w, self.notch_d = float(c["head_notch_width"]), float(c["head_notch_depth"])
        self.notch_angles = [self.mp6["phase"]["cap_screw"] + 360.0 * i / self.mp6["cap_screw_n"] + (5.0 if control == "notch_rotated" else 0.0)
                             for i in range(self.mp6["cap_screw_n"])]
        cb = P["clamp_bolts"]
        lg = cb["lug"]
        self.lug = {"a": 6.5 if control == "bolt_shallow" else float(lg["a_thick"]), "b": float(lg["b_thick"]), "out": float(lg["out"]),
                    "in": float(lg["in"]), "z": [float(v) for v in lg["z"]], "ch": float(lg["chamfer"])}
        self.cb = {"y": self.outer_r + float(cb["y_out"]), "z": [float(v) for v in cb["z"]], "len": float(cb["length"]),
                   "seat_x": -(self.split + self.lug["a"]), "ins_depth": float(cb["insert_hole_depth"])}
        cv = P["cover"]
        self.cover = {"t": float(cv["t"]), "r": 36.0 if control == "cover_insert_out" else float(cv["insert_r"]),
                      "angles": [70.0, 110.0, 250.0, 290.0] if control == "cover_insert_old_angles" else [float(a) for a in cv["insert_angles_deg"]],
                      "ins_depth": 6.0 if control == "cover_shallow" else float(cv["insert_hole_depth"]),
                      "len": float(cv["screw_length"]), "slash": cv["slash"]}
        nk = P["neck"]
        x_face = float(nk["j4_face_x_link4"]) - float(self.v1["wrist_offsets_mm"][0])
        rl = nk["j4_face_relief"]
        self.neck = {"x_face": x_face + (1.0 if control == "neck_shift" else 0.0), "t": float(nk["plate_t"]), "half": float(nk["plate_half"]),
                     "ch": float(nk["plate_chamfer"]), "web_y": float(nk["web_half_y"]), "web_x_end": float(nk["web_x_end"]),
                     "web_top": float(nk["web_top_z"]), "inset": float(nk["web_inset"]), "front_ch": float(nk["plate_front_chamfer"]),
                     # J4 = MP6 가정: 나사 원 · 개수 · 각은 MP6 출력 인서트에서(복사하지 않음)
                     "scr_r": self.mp6["output_insert_r"], "scr_phase": self.mp6["phase"]["output_insert"], "scr_n": self.mp6["output_insert_n"],
                     "under": 7.0 if control == "neck_under" else float(nk["j4_screw_under_head"]), "cbore": float(nk["j4_cbore_dia"]),
                     "relief_r": float(rl["contact_r"]), "relief_d": 0.0 if control == "no_j4_relief" else float(rl["depth"])}
        self.j4_axis_z = -float(P["placement"]["motor_face_from_joint_along_axis"])     # J4 축의 모듈 z(= 링크 4 y 0)
        hb = P["hub"]
        self.hub = {"r": 31.0 if control == "hub_big" else float(hb["r"]), "t": float(hb["t"]), "ch": float(hb["chamfer"]),
                    "under": 5.0 if control == "hub_under" else float(hb["screw_under_head"]), "cbore": float(hb["cbore_dia"]),
                    "ins_r": 22.5 if control == "insert_r" else float(hb["link5_insert_r"]), "ins_phase": float(hb["link5_insert_phase_deg"]),
                    "ins_n": int(hb["link5_insert_count"]), "ins_depth": float(hb["link5_insert_depth"])}
        self.hub_z = [self.mp6["output_face"], self.mp6["output_face"] + self.hub["t"]]
        self.screws_available = self.mp6["screw_lengths"]
        if control is None:
            self.check_limits()

    # ---- 한계(넘으면 만들지 않는다 · 검사기가 따로 다시 본다) ----
    def check_limits(self):
        R, mw, ins, m3 = self.outer_r, float(self.P["min_wall"]), self.fits["insert_hole_dia"], self.fits["m3_clearance_dia"]
        mp = self.mp6
        head_r = self.ret_head["dia"] / 2
        rt = self.route
        lim = {
            "can_outer_equals_mp6_outer": abs(R - mp["outer_r"]) < 1e-9,
            "ribs_inside_clamp_face": all(abs(y) + self.rib["hw"] <= self.clamp_y - 1.0 for y in self.rib["y"]),
            "j4_relief_clears_retainer_heads": self.neck["relief_d"] >= (mp["retainer_top"] + self.ret_head["height"] - mp["output_face"]) + 0.3,
            "j4_contact_covers_flange": self.neck["relief_r"] >= mp["flange_r"] + 1.0,
            "tie_slots_clear_of_groove": float(rt["tie_y"]) - float(rt["tie_slot"][1]) / 2 - float(rt["groove_half_width"]) >= mw,
            "tie_slots_inside_web": float(rt["tie_y"]) + float(rt["tie_slot"][1]) / 2 + mw <= self.neck["web_y"],
            "drv_corner_inside_can": self.drv_apothem + mw <= R,
            "lug_insert_inside_lug": (R + self.lug["out"]) - self.cb["y"] - ins / 2 >= mw,
            "lug_holes_inside_lug_height": all(self.lug["z"][0] + mw <= z - ins / 2 and z + ins / 2 <= self.lug["z"][1] - mw for z in self.cb["z"]),
            "lug_root_in_wall": R - self.lug["in"] - self.drv_half >= mw,
            "lug_slope_45": abs(self.lug["ch"] - (self.lug["out"] + self.lug["in"])) < 1e-9,
            "ring_opening_not_narrower_than_clamp_pocket": self.ring_half >= max(self.clamp_x + self.rib["gap"], self.clamp_y),
            "cover_insert_clear_of_cavity": all(max(abs(x), abs(y)) - ins / 2 - self.drv_half >= mw for x, y in self._cover_xy()),
            "cover_inserts_clear_of_pockets": all(_rect_gap(x, y, r) - ins / 2 >= mw for x, y in self._cover_xy() for r in self._pocket_rects()),
            "terminal_pocket_inside_can": math.hypot(self.term["x"], self.term["y"][1]) + mw <= R,
            "terminal_pocket_inner_inside_clamp_pocket": self.term["y"][0] < self.clamp_y,               # 조임 칸 · 깔때기와 합쳐 칼날 모서리가 없게(roof_note)
            "terminal_pocket_ends_inside_clamp_pocket_corners": self.term["x"] + mw <= self.clamp_x,     # 칸 끝 벽(x = ±11)이 조임 칸 모서리 안쪽에 남게
            # 창 꼭대기(가르는 면 자리) ≤ 조임 귀 45° 밑면이 캔 바깥에 닿는 높이 − 0.5(그 위로 파고들면 SolidCraft 빼기 「no result」 · 검토 R3-1)
            "terminal_window_clear_of_lug": self.tslot["z"][1] + self.tslot["x"] - self.split
                                            <= self.lug["z"][0] - self.lug["ch"] + (math.sqrt(R * R - self.split ** 2) - (R - self.lug["in"])) - 0.5,
            "terminal_pocket_clear_of_clamp_holes": self.cb["y"] - ins / 2 - self.term["y"][1] >= mw,
            "terminal_window_clear_of_clamp_holes": min(self.cb["z"]) - ins / 2 - (self.tslot["z"][1] + self.tslot["x"]) >= mw,
            "terminal_window_open": self.tslot["z"][1] > self.tslot["z"][0],
            "terminal_window_floor": self.tslot["z"][0] - self.z_rear >= mw,
            "terminal_window_peak_below_pocket_top": self.tslot["z"][1] + self.tslot["x"] <= self.term["z"][1],
            "cover_insert_clear_of_outer": self.cover["r"] + ins / 2 + mw <= R,
            "hub_inside_retainer_heads": self.hub["r"] + 1.0 <= mp["retainer_screw_r"] - head_r,
            "hub_cbore_clear_of_inserts": self._hub_hole_gap() >= mw,
            "hub_inserts_inside": self.hub["ins_r"] + float(self.P["insert_od"]) / 2 + mw <= self.hub["r"] - self.hub["ch"],   # 인서트 바깥지름 · 위 모따기 끝 기준
            "notch_covers_head": self.notch_w >= self.cap_head["dia"] + 0.6 and self.notch_d >= self.cap_head["height"] + 0.4,
            "split_positive": self.split > 0,
            "connector_inside_can": math.hypot(self.con_x[0], self.con_y) + mw <= R,
            "connector_roof_below_clamp_zone_at_inner_end": self.con_z[1] <= self.z_motor_rear,
            **self._mconn_limits(R, mw),
            "web_outside_cavity": -self.neck["web_x_end"] - self.drv_half >= mw,
        }
        bad = [k for k, v in lim.items() if not v]
        if bad:
            raise SystemExit(f"J5 geometry out of limits: {bad}")

    def mconn_profile(self, part):
        """모터 커넥터 앞 칸 한 조각의 (y, z) 단면 — 바닥 z0 · 지붕 = 전체 y0 ~ y1 의 45° 박공(끝 = z_ends · 가운데 꼭대기) + dz."""
        k = self.mconn
        p = k[part]
        (y0, y1), ze, (ya, yb), z0, dz = k["y"], k["z_ends"], p["y"], p["z0"], p["dz"]
        roof = lambda y: ze + min(y - y0, y1 - y) + dz          # noqa: E731
        pts = [(ya, z0), (yb, z0), (yb, roof(yb))]
        if ya < k["ridge"][0] < yb:
            pts.append((k["ridge"][0], roof(k["ridge"][0])))
        return pts + [(ya, roof(ya))]

    def _mconn_limits(self, R, mw):
        """모터 커넥터 앞 칸 한계 — 캔 안 · 잰 커넥터(사진 어림 가운데와 가운데 둘 다)를 덮음 · 갈비 하나는 온전 · 꼭대기가 앞 테 뒤 · 옛 칸 지붕을 품음 ·
        이웃 면과 같은 평면 없음."""
        mc, k = self.P["motor_connector"], self.mconn
        w, yc, h = float(mc["measured"]["width"]), float(mc["y_center_estimate"]), float(mc["measured"]["height_above_motor_face"])
        (y0, y1), dp, sd = k["y"], k["deep"], k["side"]
        edges = [e for y in self.rib["y"] for e in (y - self.rib["hw"], y + self.rib["hw"])] + [-self.con_y, self.con_y]
        return {
            "motor_connector_pocket_inside_can": all(math.hypot(p["x"][0], max(abs(p["y"][0]), abs(p["y"][1]))) + mw <= R for p in (dp, sd)),
            "motor_connector_pocket_covers_measured": y0 <= min(yc - w / 2, -w / 2) - 0.5 and y1 >= max(yc + w / 2, w / 2) + 0.5
                                                      and max(dp["x"][0], sd["x"][0]) <= -(self.motor["frame"] / 2 + h) - 1.0,
            "motor_connector_keeps_one_rib_whole": any(y + self.rib["hw"] <= y0 or y - self.rib["hw"] >= y1 for y in self.rib["y"]),
            "motor_connector_ridge_behind_ring_zone": k["ridge"][1] + mw <= self.ring_z0,
            "motor_connector_rear_inside_driver_zone": dp["z0"] < sd["z0"] < self.z_drv[1] < k["z_ends"] + sd["dz"],
            "motor_connector_deep_holds_old_roof": dp["x"][0] < self.con_x[0] and dp["y"][0] == y0 and dp["y"][1] > self.con_y and y0 > -self.con_y,
            "motor_connector_side_overlaps_deep": sd["y"][0] < dp["y"][1] < sd["y"][1] and sd["x"][0] > dp["x"][0],
            "motor_connector_no_shared_planes": all(abs(y - e) >= 0.15 for y in (y0, y1, dp["y"][1], sd["y"][0]) for e in edges)
                                                and abs(dp["x"][0] - self.con_x[0]) >= 0.15 and abs(sd["x"][0] - self.slot["x"][1]) >= 0.3,
        }

    def _cover_xy(self):
        return [(self.cover["r"] * math.cos(math.radians(a)), self.cover["r"] * math.sin(math.radians(a))) for a in self.cover["angles"]]

    def _pocket_rects(self):
        """커넥터(모터 선) 칸 · 단자대 칸 둘의 xy 사각형 [(x0, x1), (y0, y1)]."""
        t = self.term
        return [((self.con_x[0], self.con_x[1]), (-self.con_y, self.con_y)),
                ((-t["x"], t["x"]), (t["y"][0], t["y"][1])), ((-t["x"], t["x"]), (-t["y"][1], -t["y"][0]))]

    def _hub_hole_gap(self):
        h, mp = self.hub, self.mp6
        best = 1e9
        for i in range(mp["output_insert_n"]):
            a = math.radians(mp["phase"]["output_insert"] + 360.0 * i / mp["output_insert_n"])
            for j in range(h["ins_n"]):
                b = math.radians(h["ins_phase"] + 360.0 * j / h["ins_n"])
                d = math.hypot(mp["output_insert_r"] * math.cos(a) - h["ins_r"] * math.cos(b), mp["output_insert_r"] * math.sin(a) - h["ins_r"] * math.sin(b))
                best = min(best, d - h["cbore"] / 2 - self.fits["insert_hole_dia"] / 2)
        return best

    # ---- 나사(길이 · 자리) ----
    def screws(self):
        """나사 묶음 — 이름 · 개수 · 길이 · 머리 자리 · 축 · 끝 · 구멍 바닥 · 물림 시작(검사기는 STL 로 다시 잰다)."""
        mp, s = self.mp6, []
        f = mp["flange_screw"]
        hub_len = f["length_mm"] + self.hub["under"]
        s.append({"name": "hub_to_carrier", "count": mp["output_insert_n"], "length": hub_len, "note": "MP6 flange screw M3 x 8 made longer by the hub under-head thickness"})
        s.append({"name": "neck_to_j4", "count": self.neck["scr_n"], "length": f["length_mm"] + self.neck["under"], "note": "same as MP6 flange screw + plate under-head (J4 = MP6 assumption)"})
        s.append({"name": "clamp", "count": 2 * len(self.cb["z"]), "length": self.cb["len"]})
        s.append({"name": "cover", "count": len(self.cover["angles"]), "length": self.cover["len"]})
        return s


class SC:
    def __init__(self, spec: Spec):
        self.s = spec
        self.commands = []

    def cmd(self, c, **p):
        self.commands.append({"command": c, "params": p})

    def _sk(self, name, plane, pts):
        self.cmd("sketch.create", name=name, plane=plane)
        self.cmd("sketch.line", points=[[round(float(u), 5), round(float(v), 5)] for u, v in pts], closed=True)
        self.cmd("sketch.finish")

    @staticmethod
    def plane(axis, at):
        """축에 수직인 평면(법선 = +축) · 점 사상 f: 그 평면의 두 좌표 → 스케치 좌표. z: (x, y) · x: (y, z) · y: (x, z)."""
        if axis == "z":
            return {"origin": [0.0, 0.0, float(at)], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}, (lambda a, b: (a, b))
        if axis == "x":
            return {"origin": [float(at), 0.0, 0.0], "x_dir": [0, 1, 0], "y_dir": [0, 0, 1]}, (lambda a, b: (a, b))
        return {"origin": [0.0, float(at), 0.0], "x_dir": [1, 0, 0], "y_dir": [0, 0, -1]}, (lambda a, b: (a, -b))

    def prism(self, name, axis, a, b, pts, op="new", target=None):
        pl, f = self.plane(axis, a)
        self._sk(f"{name}_SK", pl, [f(u, v) for u, v in pts])
        if op == "new":
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="new", body_name=name, name=f"{name}_X")
        else:
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="cut", targets=[target], name=f"{name}_X")

    def box(self, name, xr, yr, zr, op="new", target=None):
        self.prism(name, "z", zr[0], zr[1], [(xr[0], yr[0]), (xr[1], yr[0]), (xr[1], yr[1]), (xr[0], yr[1])], op, target)

    def cyl(self, name, axis, a, b, c1, c2, dia, op="new", target=None):
        pl, f = self.plane(axis, a)
        u, v = f(c1, c2)
        self.cmd("sketch.create", name=f"{name}_SK", plane=pl)
        self.cmd("sketch.circle.center", center=[round(float(u), 5), round(float(v), 5)], radius=float(dia) / 2)
        self.cmd("sketch.finish")
        if op == "new":
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="new", body_name=name, name=f"{name}_X")
        else:
            self.cmd("solid.extrude", distance=float(b - a), direction="positive", operation="cut", targets=[target], name=f"{name}_X")

    def revolve_z(self, name, profile):
        """z 축 둘레 회전 — profile = (z, r) 점들."""
        self.cmd("sketch.create", name=name + "_PROFILE", plane={"origin": [0.0, 0.0, 0.0], "x_dir": [0, 0, 1], "y_dir": [1, 0, 0]})
        self.cmd("sketch.line", points=[[float(u), float(v)] for u, v in profile], closed=True)
        self.cmd("sketch.finish")
        self.cmd("solid.revolve", axis="x", operation="new", body_name=name, name=name + "_REVOLVE")

    def combine(self, target, tools, op):
        self.cmd("solid.combine", target=target, tools=list(tools), operation=op)

    def color(self, body, hexcolor):
        self.cmd("appearance.assign", bodies=[body], color=hexcolor)

    # ---------------- 캔 반쪽 ----------------
    def can_half(self, name, side):
        s = self.s
        R, zr = s.outer_r, s.z_rear
        self.cyl(name, "z", zr, 0.0, 0.0, 0.0, 2 * R)
        # 조임 볼트 귀(가르는 면 양옆) — 반쪽으로 자르기 전에 원통과 합친다(가르는 면을 자르기 한 번이 만들게 · 같은 평면 합치기 없음)
        lg = s.lug
        z_lo, z_hi = lg["z"]
        for k, sg in enumerate((1.0, -1.0)):
            prof = [(sg * (R - lg["in"]), z_lo - lg["ch"]), (sg * (R + lg["out"]), z_lo), (sg * (R + lg["out"]), z_hi), (sg * (R - lg["in"]), z_hi)]
            self.prism(f"{name}_LUG{k}", "x", -(s.split + lg["a"]), s.split + lg["b"], prof)
        self.combine(name, [f"{name}_LUG0", f"{name}_LUG1"], "join")
        keep = f"{name}_KEEP"
        xr = [-(R + 30.0), -s.split] if side < 0 else [s.split, R + 30.0]
        self.box(keep, xr, [-(R + 30.0), R + 30.0], [zr - 30.0, 80.0])
        self.combine(name, [keep], "intersect")
        if side < 0:
            self.neck(name)
        # 속: 앞 테(조이지 않음) · 조임 칸(x 면이 모터에 닿음) · 드라이버 칸(모서리 45°)
        self.box(f"{name}_RING", [-s.ring_half, s.ring_half], [-s.ring_half, s.ring_half], [s.ring_z0, 0.5], op="cut", target=name)
        self.prism(f"{name}_CLAMP", "z", s.z_motor_rear, s.ring_z0 + 0.1, clamp_profile(s), op="cut", target=name)
        h, ap = s.drv_half, s.drv_apothem * math.sqrt(2)          # |x| + |y| ≤ ap
        c = max(0.0, 2 * h - ap)
        self.prism(f"{name}_DRV", "z", zr - 0.5, s.z_motor_rear, octagon(h, h, c), op="cut", target=name)
        # 드라이버 칸 → 조임 칸 45° 깔때기(사각뿔대 · 기울기 −45°) — 갈비 · 공기 틈 밑이 공중에서 시작하지 않게(2 차: 평평한 턱 + 갈비 = Bambu Studio
        # 「floating cantilever」 · 깔때기 변형 슬라이스에서 사라짐). 밑면은 드라이버 칸 속(z_motor_rear − 0.5)에서 시작해 같은 평면 면을 피한다.
        lo = s.drv_half + 0.5
        pl, f = self.plane("z", s.z_motor_rear - 0.5)
        self._sk(f"{name}_FUN_SK", pl, [(-lo, -lo), (lo, -lo), (lo, lo), (-lo, lo)])
        self.cmd("solid.extrude", distance=float(lo - s.clamp_x), direction="positive", operation="cut", targets=[name], taper=-45,
                 name=f"{name}_FUN_X")
        # 덮개 나사 머리 홈(반지름 방향 · 가운데부터 바깥까지)
        for i, a in enumerate(s.notch_angles):
            t = math.radians(a)
            ca, sa = math.cos(t), math.sin(t)
            w, L = s.notch_w / 2, R + 2.0
            pts = [(-w * -sa, -w * ca), (L * ca - w * -sa, L * sa - w * ca), (L * ca + w * -sa, L * sa + w * ca), (w * -sa, w * ca)]
            if (side < 0 and ca < 0) or (side > 0 and ca > 0):
                self.prism(f"{name}_NOTCH{i}", "z", -s.notch_d, 0.5, pts, op="cut", target=name)
                if s.head_channel:          # 머리 자리에서 가르는 면까지 x 방향 길 — 반쪽을 옆에서 밀어 넣을 때 머리가 지나감(검토 R-1)
                    hx, hy = s.mp6["cap_screw_r"] * ca, s.mp6["cap_screw_r"] * sa       # 홈과 같은 각(대조 notch_rotated 면 돌린 각)
                    xr = [hx - w, 1.0] if side < 0 else [-1.0, hx + w]
                    self.box(f"{name}_HCH{i}", xr, [hy - w, hy + w], [-s.notch_d, 0.5], op="cut", target=name)
        # 조임 볼트(x 방향 · 귀를 지남): A = 통과 구멍(머리는 귀 바깥 평면) · B = 가르는 면에서 인서트 구멍
        m3, ins = s.fits["m3_clearance_dia"], s.fits["insert_hole_dia"]
        for yi, y in enumerate((s.cb["y"], -s.cb["y"])):
            for zi, z in enumerate(s.cb["z"]):
                tag = f"{yi}{zi}"
                if side < 0:
                    self.cyl(f"{name}_CH{tag}", "x", s.cb["seat_x"] - 0.5, 0.5, y, z, m3, op="cut", target=name)
                else:
                    self.cyl(f"{name}_CI{tag}", "x", 0.0, s.split + s.cb["ins_depth"], y, z, ins, op="cut", target=name)
        # 덮개 인서트(뒤 끝면에서)
        for i, a in enumerate(s.cover["angles"]):
            t = math.radians(a)
            x, y = s.cover["r"] * math.cos(t), s.cover["r"] * math.sin(t)
            if (side < 0) == (x < 0):
                self.cyl(f"{name}_VI{i}", "z", zr - 0.5, zr + s.cover["ins_depth"], x, y, ins, op="cut", target=name)
        # 단자대 칸(±y · (x, z) 단면을 y 로 밀어냄 · 이음 쪽으로 오르는 45° 박공) · 이음 자리 창(박공 · 귀 너머까지) — 두 반쪽이 반씩 판다
        tx, (ty0, ty1), (tz0, tz1) = s.term["x"], s.term["y"], s.term["z"]
        sx, (w0, w1), (wy0, wy1) = s.tslot["x"], s.tslot["z"], s.tslot["y"]
        for k, sg in enumerate((1.0, -1.0)):
            ya, yb = (ty0, ty1) if sg > 0 else (-ty1, -ty0)
            self.prism(f"{name}_TERM{k}", "y", ya, yb, [(-tx, tz0), (tx, tz0), (tx, tz1), (0.0, tz1 + tx), (-tx, tz1)], op="cut", target=name)
            ya, yb = (wy0, wy1) if sg > 0 else (-wy1, -wy0)
            if s.control != "tslot_closed":
                self.prism(f"{name}_TSLOT{k}", "y", ya, yb, [(-sx, w0), (sx, w0), (sx, w1), (0.0, w1 + sx), (-sx, w1)], op="cut", target=name)
        if side < 0:
            # 커넥터 칸 — 옆 윤곽(x, z)을 y 로 밀어낸 한 번의 빼기 · 45° 외쪽 지붕: 안쪽 끝(드라이버 칸 쪽)이 낮고 바깥 벽 쪽이 높다
            # (평평한 넓은 천장 = Bambu Studio 「floating cantilever」 · 상자 + 박공 둘은 같은 평면 면에서 열린 이음매 · 조임 면 뒤로 솟지 않게 — 검토 R-8)
            cy, (z0, z1) = s.con_y, s.con_z
            x0c, x1c = s.con_x
            self.prism(f"{name}_CON", "y", -cy, cy, [(x0c, z0), (x1c, z0), (x1c, z1), (x0c, z1 + (x1c - x0c))], op="cut", target=name)
            if s.mconn:     # 모터 커넥터 앞 칸(다시 만들기 3) — 깊은 칸 · 옆 칸 둘 · y 방향 45° 박공 지붕 · 안쪽 끝은 모터 면 속 0.15(공기만 자름)
                for part in ("deep", "side"):
                    xa, xb = s.mconn[part]["x"]
                    self.prism(f"{name}_MCON_{part.upper()}", "x", xa, xb, s.mconn_profile(part), op="cut", target=name)
            sy, (w0, w1) = s.slot["y"], s.slot["z"]
            self.prism(f"{name}_SLOT", "x", s.slot["x"][0], s.slot["x"][1], [(-sy, w0), (sy, w0), (sy, w1), (0.0, w1 + sy), (-sy, w1)], op="cut", target=name)
            self.neck_holes(name)

    def neck(self, name):
        """J4 쪽 목 — 판(x = x_face ~ x_face + t · (y, z) 팔각 · 가운데 = J4 축) + 받침(옆 윤곽 · y 방향으로 밀어냄).

        받침은 어느 면도 판 · 캔의 면과 같은 평면에 놓이지 않게 한다(첫 만들기에서 z = 0 공유 평면이 열린 이음매를 남김):
        윗면 = web_top(캔 앞면 0 아래) · 앞면 = 판 안쪽 inset · 아랫면 = 판 밑면보다 inset 아래에서 시작하는 45° 면 → web_x_end(캔 벽 속).
        판 아래 앞 모서리는 45° 로 front_ch 만큼 깎는다(받침 앞의 띠가 세워 출력할 때 공중에 뜬 첫 층이 되지 않게 — 판에만 깎고 받침과 합친다)."""
        s, n = self.s, self.s.neck
        x0, xi = n["x_face"], n["x_face"] + n["inset"]
        zbot, cf = s.j4_axis_z - n["half"], n["front_ch"]
        self.prism(f"{name}_PLATE", "x", x0, x0 + n["t"], octagon(n["half"], n["half"], n["ch"], 0.0, s.j4_axis_z))
        self.prism(f"{name}_PLATE_CH", "y", -(n["half"] + 1.0), n["half"] + 1.0,
                   [(x0 - 0.5, zbot + cf + 0.5), (x0 + cf + 0.5, zbot - 0.5), (x0 - 0.5, zbot - 0.5)], op="cut", target=f"{name}_PLATE")
        zb = zbot - n["inset"]                                       # 45° 아랫면의 시작(판 밑면보다 inset 아래)
        web = [(xi, n["web_top"]), (xi, zb), (n["web_x_end"], zb - (n["web_x_end"] - xi)), (n["web_x_end"], n["web_top"])]
        self.prism(f"{name}_WEB", "y", -n["web_y"], n["web_y"], web)
        self.combine(name, [f"{name}_PLATE", f"{name}_WEB"], "join")
        if n["relief_d"] > 0:       # J4 면: 반지름 relief_r 바깥을 relief_d 물려 깎음(J4 누름 고리 나사 머리 — 검토 R-3)
            pl, f = self.plane("x", x0 - 0.5)
            self.cmd("sketch.create", name=f"{name}_J4REL_SK", plane=pl)
            self.cmd("sketch.line", points=[list(f(u, v)) for u, v in ((-45.0, -45.0), (45.0, -45.0), (45.0, 70.0), (-45.0, 70.0))], closed=True)
            self.cmd("sketch.circle.center", center=list(f(0.0, s.j4_axis_z)), radius=n["relief_r"])
            self.cmd("sketch.finish")
            self.cmd("solid.extrude", distance=0.5 + n["relief_d"], direction="positive", operation="cut", targets=[name], name=f"{name}_J4REL_X")
        # 케이블 길(사용자 고른 글 「하우징 밖 홈과 묶는 고리 자리」 — 검토 R-4): 받침 45° 아랫면을 따라 홈 · 케이블 타이 구멍 둘(한 쌍씩)
        rt = s.route
        gw, gd = float(rt["groove_half_width"]), float(rt["groove_depth"])
        xg0 = x0 + 2.0                                              # J4 면은 남김
        xg1 = -math.sqrt(s.outer_r ** 2 - gw ** 2)                   # 경사면이 캔 바깥에 닿는 곳
        z_at = lambda x: zb - (x - xi)                              # noqa: E731 — 받침 아랫면(45°)
        d = gd / math.sqrt(2)
        band = [(xg0 - d, z_at(xg0) - d), (xg1 - d, z_at(xg1) - d), (xg1 + d, z_at(xg1) + d), (xg0 + d, z_at(xg0) + d)]
        self.prism(f"{name}_GROOVE", "y", -gw, gw, band, op="cut", target=name)
        sl, sw = (float(v) for v in rt["tie_slot"])
        for i, tx in enumerate(float(v) for v in rt["tie_x"]):
            for j, ty in enumerate((float(rt["tie_y"]), -float(rt["tie_y"]))):
                self.box(f"{name}_TIE{i}{j}", [tx - sl / 2, tx + sl / 2], [ty - sw / 2, ty + sw / 2], [z_at(tx + sl / 2) - 2.0, n["web_top"] + 0.5],
                         op="cut", target=name)

    def neck_holes(self, name):
        s, n = self.s, self.s.neck
        x0 = n["x_face"]
        for i in range(n["scr_n"]):
            t = math.radians(n["scr_phase"] + 360.0 * i / n["scr_n"])
            y, z = n["scr_r"] * math.cos(t), s.j4_axis_z + n["scr_r"] * math.sin(t)
            self.cyl(f"{name}_J4H{i}", "x", x0 - 0.5, x0 + n["t"] + 0.5, y, z, s.fits["m3_clearance_dia"], op="cut", target=name)
            self.cyl(f"{name}_J4C{i}", "x", x0 + n["under"], x0 + n["t"] + 0.5, y, z, n["cbore"], op="cut", target=name)

    # ---------------- 덮개 · 허브 ----------------
    def cover(self, name):
        s, c = self.s, self.s.cover
        z1 = s.z_rear
        z0 = z1 - c["t"]
        self.cyl(name, "z", z0, z1, 0.0, 0.0, 2 * s.outer_r)
        for i, a in enumerate(c["angles"]):
            t = math.radians(a)
            self.cyl(f"{name}_H{i}", "z", z0 - 0.5, z1 + 0.5, c["r"] * math.cos(t), c["r"] * math.sin(t), s.fits["m3_clearance_dia"], op="cut", target=name)
        sl = c["slash"]
        self.prism(f"{name}_SLASH", "z", z0 - 0.5, z0 + float(sl["depth"]), slash(float(sl["height"]), float(sl["width"])), op="cut", target=name)

    def hub(self, name):
        s, h, mp = self.s, self.s.hub, self.s.mp6
        z0, z1 = s.hub_z
        self.revolve_z(name, [(z0, 0.0), (z0, h["r"]), (z1 - h["ch"], h["r"]), (z1, h["r"] - h["ch"]), (z1, 0.0)])
        for i in range(mp["output_insert_n"]):
            t = math.radians(mp["phase"]["output_insert"] + 360.0 * i / mp["output_insert_n"])
            x, y = mp["output_insert_r"] * math.cos(t), mp["output_insert_r"] * math.sin(t)
            self.cyl(f"{name}_H{i}", "z", z0 - 0.5, z1 + 0.5, x, y, s.fits["m3_clearance_dia"], op="cut", target=name)
            self.cyl(f"{name}_C{i}", "z", z0 + h["under"], z1 + 0.5, x, y, h["cbore"], op="cut", target=name)
        for i in range(h["ins_n"]):
            t = math.radians(h["ins_phase"] + 360.0 * i / h["ins_n"])
            self.cyl(f"{name}_I{i}", "z", z1 - h["ins_depth"], z1 + 0.5, h["ins_r"] * math.cos(t), h["ins_r"] * math.sin(t), s.fits["insert_hole_dia"],
                     op="cut", target=name)


COLORS = {"J5_STATOR_A": "#FFFFFF", "J5_STATOR_B": "#FFFFFF", "J5_REAR_COVER": "#0B2545", "J5_OUTPUT_HUB": "#6B7280"}


def build_all(spec: Spec):
    sc = SC(spec)
    sc.can_half("J5_STATOR_A", -1)
    sc.can_half("J5_STATOR_B", +1)
    sc.cover("J5_REAR_COVER")
    sc.hub("J5_OUTPUT_HUB")
    for b, col in COLORS.items():
        sc.color(b, col)
    return sc
