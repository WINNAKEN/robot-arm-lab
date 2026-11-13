# -*- coding: utf-8 -*-
"""MP10 두 번째 구현(정답 형상) — j5geom.py 를 부르지 않고 parameters.json · 끼움 원장 · 모터 원장 · cycloid.json · MP6 parameters 만으로
계획 056 · parameters 의 글로 적은 형상을 manifold3d 로 다시 만든다.

한계(검토 MP10 R-5): 같은 작성자가 같은 세션에 썼고, 겹침 여유(넘침 길이 · 0.1 비킴 · 0.3 들임) 같은 작은 수까지 생성기와 같게 따랐다 —
그래서 C2 는 「설계 의도의 독립 판단」 이 아니라 SolidCraft ↔ manifold3d 두 구현의 일치 확인에 가깝다. 의도는 C3 · C4 · C5 · C7 · C9 · C10 의 측정 검사가 본다.

또 검사기가 쓰는 기대 수치(나사 · 자리 · 가정 상자 · J4 = MP6 가정 부품)를 한곳에서 낸다. 형상 비교 = v3 expected_shapes.py 의 양방향 표면 거리와 같은 방법.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import manifold3d as m3
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
SEG = 720


# ---------------- 입력 ----------------
def load(params_path=HERE / "parameters.json"):
    path = Path(params_path)
    P = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    S = P["sources"]

    def rd(rel):
        return json.loads((base / rel).resolve().read_text(encoding="utf-8"))
    cyc, mp6, mot, fit, v1 = rd(S["reducer_json"]), rd(S["reducer_params"]), rd(S["motor_ledger"]), rd(S["fits_ledger"]), rd(S["v1_dir"] + "/parameters.json")
    pla = fit["materials"][S["material"]]["values"]
    M = {k: float(mot["items"][k]["value"]) for k in ("frame", "body_length", "motor_driver_gap", "overall_length", "driver_width", "connector_clearance")}
    D = {"P": P, "m3": float(pla["m3_clearance_dia"]["value"]), "ins": float(pla["insert_hole_dia"]["value"]), "motor": M,
         "insert_len": float(P["insert_length"]), "insert_od": float(P["insert_od"]), "min_wall": float(P["min_wall"]),
         "avail": [float(v) for v in mp6["housing"]["screw_lengths_available"]], "area_min": {k: float(v) for k, v in P["contact_area_min_mm2"].items()}}
    c = P["can"]
    D["R"] = float(c["outer_r"])
    D["z_drv"] = [-M["overall_length"], -(M["body_length"] + M["motor_driver_gap"])]          # 뒤 끝 = 실측 전체 길이(상한)
    D["z_rear"] = D["z_drv"][0] - float(c["rear_clearance"])
    D["split"] = float(c["split_gap"]) / 2
    D["clamp"] = (M["frame"] / 2, M["frame"] / 2 + float(c["clamp_side_clearance"]))
    D["rib"] = {"gap": float(c["rib_gap"]), "hw": float(c["rib_half_width"]), "y": [float(v) for v in c["rib_y"]]}
    D["ring"] = (M["frame"] / 2 + float(c["ring_extra"]), -float(c["ring_zone"]))
    D["drv_half"] = M["driver_width"] / 2 + float(c["driver_clearance"])
    D["drv_sum"] = M["driver_width"] + math.sqrt(2) * float(c["driver_clearance"])        # |x| + |y| ≤ 이 값(드라이버 모서리 + 틈 · 45° 방향)
    D["notch"] = (float(c["head_notch_width"]), float(c["head_notch_depth"]))
    hd = P["screw_heads"]
    D["cap_head"] = {k: float(hd["cap_screw_envelope"][k]) for k in ("dia", "height")}
    D["ret_head"] = {k: float(hd["retainer_screw"][k]) for k in ("dia", "height")}
    ph = P["mp6_phases_deg"]
    st, rr, sc = cyc["stack_mm"], cyc["radii_mm"], cyc["screws"]
    D["mp6"] = {"output_face": float(st["output_face"]), "retainer": [float(v) for v in st["retainer"]], "flange": [float(v) for v in st["flange"]],
                "outer_r": float(rr["outer"]), "cap_r": float(rr["cap_screw"]), "ret_r": float(rr["retainer_screw"]), "out_ins_r": float(rr["output_insert"]),
                "cap_n": int(mp6["housing"]["cap_screws"]), "out_n": int(mp6["carrier"]["output_inserts"]), "flange_r": float(mp6["carrier"]["shoulder_dia"]) / 2,
                "head_d": float(mp6["motor"]["screw_head_dia"]), "head_h": float(mp6["motor"]["screw_head_height"]),
                "flange_len": float(sc["flange"]["length_mm"]), "cap_ph": float(ph["cap_screw"]), "out_ph": float(ph["output_insert"]),
                "ret_ph": float(ph["retainer_screw"])}
    con = P["connector"]
    D["con"] = {"x": [-(M["driver_width"] / 2 + M["connector_clearance"]), -D["drv_half"] + 0.1], "y": float(con["pocket_half_width"]),
                "z": [D["z_drv"][0] - float(c["driver_clearance"]), D["z_drv"][1] + float(c["driver_clearance"])]}
    mc = P["motor_connector"]                                                # 모터 6 핀 커넥터(11/01 실측) · 그 앞 칸(반쪽 A)
    mm, mpk = {k: float(v) for k, v in mc["measured"].items()}, mc["pocket"]
    f = M["frame"] / 2
    D["mconn_meas"] = {**mm, "yc": float(mc["y_center_estimate"])}
    zfl = -(M["body_length"] + M["motor_driver_gap"]) - float(mpk["rear_overlap"])
    D["mconn"] = {"y": [float(mpk["y"][0]), float(mpk["y"][1])], "z_end": -mm["front_from_motor_face"] + float(mpk["front_clearance"]),
                  # 깊은 칸 = 옛 칸 바깥 끝 너머 · 옆 칸 = 커넥터 높이 + 여유 · 옆 칸 지붕 · 바닥은 step 만큼 아래(같은 평면 피함)
                  "parts": [(D["con"]["x"][0] - float(mpk["deep_beyond_old_pocket"]), float(mpk["y"][0]), float(mpk["deep_y_max"]), zfl, 0.0),
                            (-f - mm["height_above_motor_face"] - float(mpk["top_clearance"]), float(mpk["deep_y_max"]) - float(mpk["side_overlap"]),
                             float(mpk["y"][1]), zfl + float(mpk["side_step"]), -float(mpk["side_step"]))],
                  "x_in": -f + float(mpk["into_motor"])}
    cs = P["cable_slot"]
    zf = [float(v) for v in cs["z_from_driver"]]
    D["slot"] = {"x": [-(D["R"] + 1.0), D["con"]["x"][0] + 1.0], "y": float(cs["half_width"]), "z": [D["z_drv"][0] + zf[0], D["z_drv"][1] - zf[1]]}
    tm = P["terminals"]                                                      # 단자대 칸 · 이음 창(±y · 10/30 사용자 「양옆 단자를 이음 쪽으로 (권장)」)
    D["term"] = {"x": float(tm["pocket_half_width"]), "z": list(D["con"]["z"]),             # (x, z) 단면: 상자 + 이음 쪽 45° 박공 · 안쪽 = 조임 칸 면 − 0.15
                 "y": [M["frame"] / 2 + float(c["clamp_side_clearance"]) - float(tm["inner_into_clamp_pocket"]), M["driver_width"] / 2 + M["connector_clearance"]]}
    tw = tm["window"]                                                        # 창 높이 = 뒤 끝면에서(드라이버 칸 기준 아님 — parameters window_note)
    D["tslot"] = {"x": float(tw["half_width"]), "z": [D["z_rear"] + float(tw["z_from_rear"][0]), D["z_rear"] + float(tw["z_from_rear"][1])],
                  "y": [D["term"]["y"][1] - 1.0, D["R"] + float(P["clamp_bolts"]["lug"]["out"]) + 1.0]}
    rt = P["cable_route"]
    D["route"] = {"gw": float(rt["groove_half_width"]), "gd": float(rt["groove_depth"]), "tie_x": [float(v) for v in rt["tie_x"]],
                  "tie_y": float(rt["tie_y"]), "tie_slot": [float(v) for v in rt["tie_slot"]]}
    cb = P["clamp_bolts"]
    lg = cb["lug"]
    D["lug"] = {"a": float(lg["a_thick"]), "b": float(lg["b_thick"]), "out": float(lg["out"]), "in": float(lg["in"]), "z": [float(v) for v in lg["z"]],
                "ch": float(lg["chamfer"])}
    D["cb"] = {"y": D["R"] + float(cb["y_out"]), "z": [float(v) for v in cb["z"]], "len": float(cb["length"]), "seat": -(D["split"] + D["lug"]["a"]),
               "depth": float(cb["insert_hole_depth"])}
    cv = P["cover"]
    D["cover"] = {"t": float(cv["t"]), "r": float(cv["insert_r"]), "ang": [float(a) for a in cv["insert_angles_deg"]], "depth": float(cv["insert_hole_depth"]),
                  "len": float(cv["screw_length"]), "slash": {k: float(v) for k, v in cv["slash"].items()}}
    nk = P["neck"]
    D["j4z"] = -float(P["placement"]["motor_face_from_joint_along_axis"])
    D["wrist0"] = float(v1["wrist_offsets_mm"][0])
    D["neck"] = {"x": float(nk["j4_face_x_link4"]) - D["wrist0"], "t": float(nk["plate_t"]), "half": float(nk["plate_half"]), "ch": float(nk["plate_chamfer"]),
                 "wy": float(nk["web_half_y"]), "wx": float(nk["web_x_end"]), "wtop": float(nk["web_top_z"]), "inset": float(nk["web_inset"]),
                 "fch": float(nk["plate_front_chamfer"]),
                 "r": D["mp6"]["out_ins_r"], "ph": D["mp6"]["out_ph"], "n": D["mp6"]["out_n"],               # J4 = MP6 가정
                 "under": float(nk["j4_screw_under_head"]), "cbore": float(nk["j4_cbore_dia"]),
                 "relief_r": float(nk["j4_face_relief"]["contact_r"]), "relief_d": float(nk["j4_face_relief"]["depth"])}
    hb = P["hub"]
    D["hub"] = {"r": float(hb["r"]), "t": float(hb["t"]), "ch": float(hb["chamfer"]), "under": float(hb["screw_under_head"]), "cbore": float(hb["cbore_dia"]),
                "ir": float(hb["link5_insert_r"]), "iph": float(hb["link5_insert_phase_deg"]), "in": int(hb["link5_insert_count"]), "idepth": float(hb["link5_insert_depth"])}
    D["hub_z"] = [D["mp6"]["output_face"], D["mp6"]["output_face"] + D["hub"]["t"]]
    return D


# ---------------- manifold 도움 ----------------
def ccw(poly):
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else list(reversed(poly))


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    return m3.Manifold.cylinder(z1 - z0, r, -1.0, SEG).translate((x, y, z0))


def cyl_x(r, x0, x1, y, z):
    return m3.Manifold.cylinder(x1 - x0, r, -1.0, SEG).rotate((0.0, 90.0, 0.0)).translate((x0, y, z))


def box(xr, yr, zr):
    return m3.Manifold.cube((xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0])).translate((xr[0], yr[0], zr[0]))


def prism_z(poly_xy, z0, z1):
    return m3.CrossSection([ccw(poly_xy)]).extrude(z1 - z0).translate((0.0, 0.0, z0))


def prism_x(poly_yz, x0, x1):
    e = m3.CrossSection([ccw(poly_yz)]).extrude(x1 - x0)                     # (u = y, v = z, w) → (x = w, y = u, z = v)
    return e.transform(np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]], float))


def prism_y(poly_xz, y0, y1):
    e = m3.CrossSection([ccw(poly_xz)]).extrude(y1 - y0)                     # (u = x, v = z, w) → (x = u, y = y1 − w, z = v)
    return e.transform(np.array([[1, 0, 0, 0], [0, 0, -1, y1], [0, 1, 0, 0]], float))


def octagon(hw, hh, c, cu=0.0, cv=0.0):
    pts = [(hw, -hh + c), (hw, hh - c), (hw - c, hh), (-hw + c, hh), (-hw, hh - c), (-hw, -hh + c), (-hw + c, -hh), (hw - c, -hh)]
    out = []
    for u, v in pts:
        q = (u + cu, v + cv)
        if not out or abs(out[-1][0] - q[0]) > 1e-9 or abs(out[-1][1] - q[1]) > 1e-9:
            out.append(q)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= 1e-9 and abs(out[0][1] - out[-1][1]) <= 1e-9:
        out.pop()
    return out


def radial_slot(angle_deg, width, length):
    t = math.radians(angle_deg)
    d, n = np.array([math.cos(t), math.sin(t)]), np.array([-math.sin(t), math.cos(t)])
    w = width / 2
    return [tuple(-w * n), tuple(length * d - w * n), tuple(length * d + w * n), tuple(w * n)]


def polar(r, deg):
    t = math.radians(deg)
    return r * math.cos(t), r * math.sin(t)


# ---------------- 부품 ----------------
def stator(D, side):
    R, zr, s = D["R"], D["z_rear"], D["split"]
    keep = box([-(R + 30), -s] if side < 0 else [s, R + 30], [-(R + 30), R + 30], [zr - 30, 80])
    lg = D["lug"]
    can = cyl_z(R, zr, 0.0)
    for sg in (1.0, -1.0):                                                   # 조임 볼트 귀(45° 밑면) — 반쪽으로 자르기 전에 합침
        can = can + prism_x([(sg * (R - lg["in"]), lg["z"][0] - lg["ch"]), (sg * (R + lg["out"]), lg["z"][0]), (sg * (R + lg["out"]), lg["z"][1]),
                             (sg * (R - lg["in"]), lg["z"][1])], -(s + lg["a"]), s + lg["b"])
    body = can ^ keep
    if side < 0:
        n = D["neck"]
        x0, cf = n["x"], n["fch"]
        zbot = D["j4z"] - n["half"]
        plate = prism_x(octagon(n["half"], n["half"], n["ch"], 0.0, D["j4z"]), x0, x0 + n["t"])
        plate = plate - prism_y([(x0 - 0.5, zbot + cf + 0.5), (x0 + cf + 0.5, zbot - 0.5), (x0 - 0.5, zbot - 0.5)], -(n["half"] + 1), n["half"] + 1)
        xi, zb = x0 + n["inset"], zbot - n["inset"]
        web = prism_y([(xi, n["wtop"]), (xi, zb), (n["wx"], zb - (n["wx"] - xi)), (n["wx"], n["wtop"])], -n["wy"], n["wy"])
        body = body + plate + web
        # J4 면: 반지름 relief_r 바깥을 relief_d 물림(계획 · parameters 의 글)
        body = body - (box([x0 - 0.5, x0 + n["relief_d"]], [-45.0, 45.0], [-45.0, 70.0]) - cyl_x(n["relief_r"], x0 - 1.0, x0 + n["relief_d"] + 1.0, 0.0, D["j4z"]))
        # 케이블 홈(받침 45° 아랫면을 따라 · J4 면 2 mm 뒤부터 경사가 캔에 닿는 곳까지) · 타이 구멍
        rt = D["route"]
        xg0, xg1 = x0 + 2.0, -math.sqrt(R ** 2 - rt["gw"] ** 2)
        z_at = lambda x: zb - (x - xi)                                       # noqa: E731
        d = rt["gd"] / math.sqrt(2)
        body = body - prism_y([(xg0 - d, z_at(xg0) - d), (xg1 - d, z_at(xg1) - d), (xg1 + d, z_at(xg1) + d), (xg0 + d, z_at(xg0) + d)], -rt["gw"], rt["gw"])
        sl, sw = rt["tie_slot"]
        for tx in rt["tie_x"]:
            for ty in (rt["tie_y"], -rt["tie_y"]):
                body = body - box([tx - sl / 2, tx + sl / 2], [ty - sw / 2, ty + sw / 2], [z_at(tx + sl / 2) - 2.0, n["wtop"] + 0.5])
    rh, rz0 = D["ring"]
    cx, cy = D["clamp"]
    rb = D["rib"]
    X0 = cx + rb["gap"]
    prof = [(X0, -cy)]
    for y in sorted(rb["y"]):
        prof += [(X0, y - rb["hw"]), (cx, y - rb["hw"]), (cx, y + rb["hw"]), (X0, y + rb["hw"])]
    prof += [(X0, cy), (-X0, cy)]
    for y in sorted(rb["y"], reverse=True):
        prof += [(-X0, y + rb["hw"]), (-cx, y + rb["hw"]), (-cx, y - rb["hw"]), (-X0, y - rb["hw"])]
    prof.append((-X0, -cy))
    h = D["drv_half"]
    zm = -D["motor"]["body_length"]
    lo = h + 0.5                                                             # 45° 깔때기(사각뿔대): z_m − 0.5 에서 반폭 lo → 반폭 cx 까지
    zf0, zf1 = zm - 0.5, zm - 0.5 + (lo - cx)
    funnel = m3.Manifold.hull_points([(sx * lo, sy * lo, zf0) for sx in (-1, 1) for sy in (-1, 1)] + [(sx * cx, sy * cx, zf1) for sx in (-1, 1) for sy in (-1, 1)])
    cut = [box([-rh, rh], [-rh, rh], [rz0, 0.5]), prism_z(prof, zm, rz0 + 0.1),
           prism_z(octagon(h, h, max(0.0, 2 * h - D["drv_sum"])), zr - 0.5, zm), funnel]
    nw, nd = D["notch"]
    mp = D["mp6"]
    for i in range(mp["cap_n"]):
        a = mp["cap_ph"] + 360.0 * i / mp["cap_n"]
        cut.append(prism_z(radial_slot(a, nw, R + 2.0), -nd, 0.5))
        hx, hy = polar(mp["cap_r"], a)                                       # 머리 → 가르는 면 x 방향 길
        if (side < 0) == (hx < 0):
            cut.append(box([hx - nw / 2, 1.0] if side < 0 else [-1.0, hx + nw / 2], [hy - nw / 2, hy + nw / 2], [-nd, 0.5]))
    cb = D["cb"]
    for y in (cb["y"], -cb["y"]):
        for z in cb["z"]:
            if side < 0:
                cut.append(cyl_x(D["m3"] / 2, cb["seat"] - 0.5, 0.5, y, z))            # 귀를 지나는 통과 구멍 · 머리는 귀 바깥 평면
            else:
                cut.append(cyl_x(D["ins"] / 2, 0.0, s + cb["depth"], y, z))
    cv = D["cover"]
    for a in cv["ang"]:
        x, y = polar(cv["r"], a)
        if (side < 0) == (x < 0):
            cut.append(cyl_z(D["ins"] / 2, zr - 0.5, zr + cv["depth"], x, y))
    tm, ts = D["term"], D["tslot"]
    (ty0, ty1), (tz0, tz1) = tm["y"], tm["z"]
    tgab = [(-ts["x"], ts["z"][0]), (ts["x"], ts["z"][0]), (ts["x"], ts["z"][1]), (0.0, ts["z"][1] + ts["x"]), (-ts["x"], ts["z"][1])]
    tpent = [(-tm["x"], tz0), (tm["x"], tz0), (tm["x"], tz1), (0.0, tz1 + tm["x"]), (-tm["x"], tz1)]
    for sg in (1.0, -1.0):                                                   # 두 반쪽이 반씩 판다(가르는 면을 건너 x = ±pocket_half_width)
        cut.append(prism_y(tpent, *((ty0, ty1) if sg > 0 else (-ty1, -ty0))))
        cut.append(prism_y(tgab, *((ts["y"][0], ts["y"][1]) if sg > 0 else (-ts["y"][1], -ts["y"][0]))))
    if side < 0:
        cn, sl, n = D["con"], D["slot"], D["neck"]
        (x0c, x1c), (z0c, z1c) = cn["x"], cn["z"]
        shed = [(x0c, z0c), (x1c, z0c), (x1c, z1c), (x0c, z1c + (x1c - x0c))]           # 45° 외쪽 지붕(안쪽 낮음 · 바깥 벽 쪽 높음)
        sgab = [(-sl["y"], sl["z"][0]), (sl["y"], sl["z"][0]), (sl["y"], sl["z"][1]), (0.0, sl["z"][1] + sl["y"]), (-sl["y"], sl["z"][1])]
        cut += [prism_y(shed, -cn["y"], cn["y"]), prism_x(sgab, sl["x"][0], sl["x"][1])]
        mk = D["mconn"]                                                      # 모터 커넥터 앞 칸 — 지붕 = y 방향 45° 박공(양 끝 z_end · 가운데 꼭대기)
        (Y0, Y1), ze = mk["y"], mk["z_end"]
        for xo, ya, yb, zf, dz in mk["parts"]:
            ys_ = sorted({ya, yb} | ({(Y0 + Y1) / 2} if ya < (Y0 + Y1) / 2 < yb else set()))
            top = [(y, ze + min(y - Y0, Y1 - y) + dz) for y in reversed(ys_)]
            cut.append(prism_x([(ya, zf), (yb, zf)] + top, xo, mk["x_in"]))
        for i in range(n["n"]):
            u, v = polar(n["r"], n["ph"] + 360.0 * i / n["n"])
            cut += [cyl_x(D["m3"] / 2, n["x"] - 0.5, n["x"] + n["t"] + 0.5, u, D["j4z"] + v),
                    cyl_x(n["cbore"] / 2, n["x"] + n["under"], n["x"] + n["t"] + 0.5, u, D["j4z"] + v)]
    for t in cut:
        body = body - t
    return body


def cover(D):
    R, zr, cv = D["R"], D["z_rear"], D["cover"]
    z0 = zr - cv["t"]
    body = cyl_z(R, z0, zr)
    for a in cv["ang"]:
        x, y = polar(cv["r"], a)
        body = body - cyl_z(D["m3"] / 2, z0 - 0.5, zr + 0.5, x, y)
    sl = cv["slash"]
    hh, w = sl["height"] / 2, sl["width"]
    return body - prism_z([(-hh - w / 2, -hh), (-hh + w / 2, -hh), (hh + w / 2, hh), (hh - w / 2, hh)], z0 - 0.5, z0 + sl["depth"])


def hub(D):
    h, mp = D["hub"], D["mp6"]
    z0, z1 = D["hub_z"]
    body = m3.CrossSection([ccw([(0.0, z0), (h["r"], z0), (h["r"], z1 - h["ch"]), (h["r"] - h["ch"], z1), (0.0, z1)])]).revolve(SEG)
    for i in range(mp["out_n"]):
        x, y = polar(mp["out_ins_r"], mp["out_ph"] + 360.0 * i / mp["out_n"])
        body = body - cyl_z(D["m3"] / 2, z0 - 0.5, z1 + 0.5, x, y) - cyl_z(h["cbore"] / 2, z0 + h["under"], z1 + 0.5, x, y)
    for i in range(h["in"]):
        x, y = polar(h["ir"], h["iph"] + 360.0 * i / h["in"])
        body = body - cyl_z(D["ins"] / 2, z1 - h["idepth"], z1 + 0.5, x, y)
    return body


def expected_parts(D):
    return {"J5_STATOR_A": stator(D, -1), "J5_STATOR_B": stator(D, +1), "J5_REAR_COVER": cover(D), "J5_OUTPUT_HUB": hub(D)}


# ---------------- 가정 상자 · 나사 몸(조립 검사용) ----------------
def assumed_boxes(D):
    """모터 · 드라이버 · 커넥터(모두 원장 가정값). 커넥터 y 반폭 10 = 이 정답표의 가정(원장에 폭 없음)."""
    M = D["motor"]
    f, w = M["frame"] / 2, M["driver_width"] / 2
    return {"MOTOR": box([-f, f], [-f, f], [-M["body_length"], 0.0]),
            "DRIVER": box([-w, w], [-w, w], D["z_drv"]),
            "CONNECTOR": box([-(w + M["connector_clearance"]), -w], [-10.0, 10.0], D["z_drv"]),
            # 양옆 단자대(10/30 사진 — ±y) · x 반폭 10 = 같은 가정
            "TERM_P": box([-10.0, 10.0], [w, w + M["connector_clearance"]], D["z_drv"]),
            "TERM_N": box([-10.0, 10.0], [-(w + M["connector_clearance"]), -w], D["z_drv"]),
            # 모터 6 핀 커넥터 + 선(11/01 실측 높이 · 폭 · 앞 끝 · 뒤 = 드라이버 앞까지) — y 자리는 사진 어림(_EST)과 가운데(_MID) 둘 다
            **{f"MOTOR_CABLE_{t}": box([-f - D["mconn_meas"]["height_above_motor_face"], -f], [yc - D["mconn_meas"]["width"] / 2, yc + D["mconn_meas"]["width"] / 2],
                                      [-(M["body_length"] + M["motor_driver_gap"]), -D["mconn_meas"]["front_from_motor_face"]])
               for t, yc in (("EST", D["mconn_meas"]["yc"]), ("MID", 0.0))}}


def screw_solids(D):
    """나사 머리 · 몸통(이 단위 나사 = 둥근머리 ISO 7380 Ø head_d × head_h · MP6 덮개 나사 = 렌치볼트까지 덮는 겉봉 · 몸통 Ø3) — 이름 → (머리, 몸통, 머리가 앉는 부품)."""
    mp, hd, hh = D["mp6"], D["mp6"]["head_d"] / 2, D["mp6"]["head_h"]
    ch = D["cap_head"]
    out = {}
    for i in range(mp["cap_n"]):                                             # MP6 덮개 나사 머리(바닥판 밑) — R08 겉봉
        x, y = polar(mp["cap_r"], mp["cap_ph"] + 360.0 * i / mp["cap_n"])
        out[f"MP6_CAP_HEAD{i}"] = (cyl_z(ch["dia"] / 2, -ch["height"], 0.0, x, y), None, "HOUSING_BASE")
    rh = D["ret_head"]
    for i in range(mp["cap_n"]):                                             # MP6 누름 고리 나사 머리(누름 고리 위) — R09 둥근머리
        x, y = polar(mp["ret_r"], mp["ret_ph"] + 360.0 * i / mp["cap_n"])
        r1 = mp["retainer"][1]
        out[f"MP6_RET_HEAD{i}"] = (cyl_z(rh["dia"] / 2, r1, r1 + rh["height"], x, y), None, "RETAINER")
    h, z0 = D["hub"], D["hub_z"][0]
    seat = z0 + h["under"]
    for i in range(mp["out_n"]):
        x, y = polar(mp["out_ins_r"], mp["out_ph"] + 360.0 * i / mp["out_n"])
        L = mp["flange_len"] + h["under"]
        out[f"HUB_SCREW{i}"] = (cyl_z(hd, seat, seat + hh, x, y), cyl_z(1.5, seat - L, seat, x, y), "J5_OUTPUT_HUB")
    cb = D["cb"]
    k = 0
    for y in (cb["y"], -cb["y"]):
        for z in cb["z"]:
            out[f"CLAMP_BOLT{k}"] = (cyl_x(hd, cb["seat"] - hh, cb["seat"], y, z), cyl_x(1.5, cb["seat"], cb["seat"] + cb["len"], y, z), "J5_STATOR_A")
            k += 1
    cv, zr = D["cover"], D["z_rear"]
    z0c = zr - cv["t"]
    for i, a in enumerate(cv["ang"]):
        x, y = polar(cv["r"], a)
        out[f"COVER_SCREW{i}"] = (cyl_z(hd, z0c - hh, z0c, x, y), cyl_z(1.5, z0c, z0c + cv["len"], x, y), "J5_REAR_COVER")
    n = D["neck"]
    for i in range(n["n"]):
        u, v = polar(n["r"], n["ph"] + 360.0 * i / n["n"])
        sx = n["x"] + n["under"]
        L = mp["flange_len"] + n["under"]
        out[f"NECK_SCREW{i}"] = (cyl_x(hd, sx, sx + hh, u, D["j4z"] + v), cyl_x(1.5, sx - L, sx, u, D["j4z"] + v), "J5_STATOR_A")
    return out


def j4_mp6_transform(D):
    """J4 = MP6 가정: MP6 좌표(z = 축 · 출력 면 output_face) → 모듈 좌표. J4 축 = 모듈 x · 출력 면 = 목판 면(x = neck x) · 축 중심 (y, z) = (0, j4z).
    MP6 (x6, y6, z6) → 모듈 (z6 − output_face + neck_x, x6, y6 + j4z)."""
    return np.array([[0, 0, 1, D["neck"]["x"] - D["mp6"]["output_face"]], [1, 0, 0, 0], [0, 1, 0, D["j4z"]]], float)


# ---------------- 메시 · 거리(v3 expected_shapes.py 와 같은 방법) ----------------
def to_trimesh(man):
    mesh = man.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=False)


def to_manifold(tm):
    return m3.Manifold(m3.Mesh(np.asarray(tm.vertices, np.float32), np.asarray(tm.faces, np.uint32)))


def point_mesh_distance(points, mesh, samples=60000, k=24, seed=0, recheck=0.02):
    """점들 → 메시 표면 거리(rtree 없이) — 표면 표본 + 꼭짓점 KD 트리로 후보 면 k 개(참 거리 이상 = 보수적) · recheck 를 넘는 점만 모든 면에 대해 다시 잰다.
    v3 는 0.005 에서 다시 쟀다 — 여기서는 허용 0.03 의 2/3 인 0.02(그 아래 후보 값은 참 거리 이상이라 합격 판정이 바뀌지 않음 · 보고 값은 위쪽 한계)."""
    from scipy.spatial import cKDTree
    pts_s, fid = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    vf = np.asarray(mesh.vertex_faces)[:, 0]
    keep = vf >= 0
    P = np.vstack([pts_s, np.asarray(mesh.vertices)[keep]])
    F = np.concatenate([fid, vf[keep]])
    _d, idx = cKDTree(P).query(points, k=k)
    cand = F[idx]
    n = len(points)
    tri = np.asarray(mesh.triangles)[cand.reshape(-1)]
    q = np.repeat(np.asarray(points, float), k, axis=0)
    cp = trimesh.triangles.closest_point(tri, q)
    d = np.linalg.norm(cp - q, axis=1).reshape(n, k).min(axis=1)
    T = np.asarray(mesh.triangles)
    for i in np.nonzero(d > recheck)[0]:
        p = np.asarray(points[i], float)
        cpa = trimesh.triangles.closest_point(T, np.repeat(p[None], len(T), axis=0))
        d[i] = float(np.linalg.norm(cpa - p, axis=1).min())
    return d


def clean(tm):
    """넓이 0(퇴화) 삼각형을 뺀 사본 — closest_point 가 그런 면에서 nan 을 내 최대 거리가 nan 이 됐다(2 차)."""
    m = tm.copy()
    m.update_faces(m.area_faces > 1e-12)
    m.remove_unreferenced_vertices()
    return m


def surface_distance(stl, exp, samples=4000, seed=0):
    stl, exp = clean(stl), clean(exp)
    d1 = point_mesh_distance(np.asarray(stl.vertices), exp, seed=seed)
    pts = np.vstack([exp.vertices, trimesh.sample.sample_surface_even(exp, samples, seed=seed)[0]])
    d2 = point_mesh_distance(pts, stl, seed=seed + 1)
    return float(d1.max()), float(d2.max())
