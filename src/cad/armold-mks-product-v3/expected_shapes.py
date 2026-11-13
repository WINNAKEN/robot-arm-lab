# -*- coding: utf-8 -*-
"""MP7 검사기의 독립 기대 형상(L2 R2-01 · R2-05) — 계획 045 의 형상을 **생성기(v3geom.py)를 쓰지 않고** 다시 만든다.

- 관절 · 링크 프레임 = 검사기가 v1 길이 · 축 · pose 로 다시 낸 순기구학(fk).
- 보호 치수(드럼 지름 · 깊이 · 캔 반지름 · 캔 길이 · 덮개 두께 · 띠 · 출력 부호 · 링크 치수) = v1 · v2 parameters. 겉모양 값(모따기 · 표시 크기 ·
  글자)만 v3 parameters · kmjh_logo 다각형.
- 바디마다 (링크 · 역할 · 기대 메시 — 세계 좌표 mm · 표시 자세)를 돌려준다. 이 목록 자체가 바디 이름 · 소속 · 역할의 정답이다.
회전체는 trimesh 회전(720 등분), 각기둥은 다각형 밀기, 45° 끝 자르기는 manifold 불리언으로 만든다."""
from __future__ import annotations

import math

import numpy as np
import trimesh
from shapely.geometry import Polygon

SECTIONS = 720


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def perp(a):
    a = np.asarray(a, float)
    h = np.array([0, 0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0, 0])
    v = h - a * np.dot(h, a)
    return v / np.linalg.norm(v)


def octagon(hw, hh, c):
    return [(hw, -hh + c), (hw, hh - c), (hw - c, hh), (-hw + c, hh), (-hw, hh - c), (-hw, -hh + c), (-hw + c, -hh), (hw - c, -hh)]


def slash(height, width):
    h, w = height / 2, width
    return [(-h - w / 2, -h), (-h + w / 2, -h), (h + w / 2, h), (h - w / 2, h)]


def revolve(profile, origin, axis):
    """profile = [(축 방향 u, 반지름 r)] — 축 위에서 시작해 축 위에서 끝나면 열린 선, 아니면 닫힌 고리. 축 = axis(세계) · 원점 = origin."""
    pts = [(r, u) for u, r in profile]
    if profile[0][1] != 0 or profile[-1][1] != 0:
        pts = pts + [pts[0]]
    m = trimesh.creation.revolve(np.asarray(pts, float), sections=SECTIONS)
    z = unit(axis)
    x = perp(z)
    T = np.eye(4)
    T[:3, :3] = np.column_stack([x, np.cross(z, x), z])
    T[:3, 3] = origin
    m.apply_transform(T)
    return m


def prism(poly, origin, xdir, ydir, distance):
    """평면(원점 · x · y)의 다각형을 법선(x × y) 쪽으로 distance 만큼."""
    m = trimesh.creation.extrude_polygon(Polygon(poly), distance)
    x, y = unit(xdir), unit(ydir)
    T = np.eye(4)
    T[:3, :3] = np.column_stack([x, y, np.cross(x, y)])
    T[:3, 3] = origin
    m.apply_transform(T)
    return m


def link_T(fk, link):
    T = np.eye(4)
    if link:
        T[:3, :3] = fk[link - 1]["R_child"]
        T[:3, 3] = fk[link - 1]["origin"]
    return T


def bar_local(hw, hh, c, x0, x1, yc, end_edge_y=None):
    """링크 좌표의 팔각 막대(단면 y-z · 길이 x0 → x1 · 중심 y = yc) − 45° 끝 자르기."""
    bar = trimesh.creation.extrude_polygon(Polygon(octagon(hw, hh, c)), x1 - x0)          # (y - yc, z, x - x0)
    P = np.array([[0, 0, 1, x0], [1, 0, 0, yc], [0, 1, 0, 0], [0, 0, 0, 1]], float)     # → (x, y, z)
    bar.apply_transform(P)
    if end_edge_y is None:
        return bar
    sg = 1.0 if yc > 0 else -1.0
    y_out = yc + sg * hw
    L = x1
    x_a = L - abs(y_out - end_edge_y)
    tri = [(x_a - 1, y_out + sg), (L + 1, y_out + sg), (L + 1, end_edge_y - sg)]
    cut = trimesh.creation.extrude_polygon(Polygon(tri), 2 * hh + 2)
    cut.apply_translation([0, 0, -hh - 1])
    return trimesh.boolean.difference([bar, cut], engine="manifold")


def face_marks(origin, n, poly, depth, right=None):
    """바깥 법선 n 인 평면에 다각형을 depth 만큼 돋운다. right 를 안 주면 위 = 세계 Z(거의 수직이면 X)의 평면 성분 · 오른쪽 = 위 × n."""
    n = unit(n)
    if right is None:
        hint = np.array([0, 0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
        up = unit(hint - n * np.dot(hint, n))
        right = np.cross(up, n)
    else:
        right = unit(np.asarray(right, float) - n * np.dot(right, n))
        up = np.cross(n, right)
    return prism(poly, origin, right, up, depth), right, up


def tool_interface_expected(p3, base_dir):
    """공구 끝 규격의 정답(MP9 2 단계) — 생성기(v3geom.tool_interface)를 쓰지 않고 그리퍼 parameters · 끼움 원장을 따로 읽는다."""
    import json
    from pathlib import Path
    src = p3["links"]["tool"]["interface_from"]
    g = json.loads((Path(base_dir) / src["gripper_params"]).resolve().read_text(encoding="utf-8"))
    led = json.loads((Path(base_dir) / src["ledger"]).resolve().read_text(encoding="utf-8"))
    ins = led["materials"][src["material"]]["values"]["insert_hole_dia"]
    lay = g["layout"]
    seat = lay["base_top"] - lay["arm_screw_cbore"][1]                   # 팔 나사 머리가 앉는 높이(받침 아랫면 기준)
    shank_below = g["screws"]["arm_m3"]["length"] - seat                  # 몸통이 받침 아랫면 밑으로 나온 길이
    return {"boss_r": lay["recess_dia"] / 2, "boss_t": lay["recess_depth"], "pcd": lay["arm_screw_pcd"], "phase_deg": lay["arm_screw_phase_deg"],
            "count": 4, "hole_d": ins["value"], "hole_status": ins["status"], "hole_depth": shank_below + p3["links"]["tool"]["screw_hole_extra_depth"],
            "shank_below_mm": shank_below, "material": src["material"], "gripper_fits_material": g["fits_from"]["material"]}


def expected_bodies(p1, p2, p3, fk, logo_rows, logo_width, tif):
    D = float(p1["reducer_depth_mm"])
    RDs = [d / 2 for d in p1["reducer_diameters_mm"]]
    e2, L2 = p2["exterior"], p2["links"]
    RC = float(e2["motor_can_radius_mm"])
    LC = float(3 + p1["motor_length_mm"] + 2 + p1["driver_depth_mm"] + e2["can_rear_clearance_mm"])
    CAP, RW, RT = float(e2["end_cap_thickness_mm"]), float(e2["accent_ring_width_mm"]), float(e2["accent_ring_depth_mm"])
    sign = e2["output_side_sign"]
    e3, L3, mk = p3["exterior"], p3["links"], p3["marks"]
    em = mk["emboss_mm"]
    out = {}

    def put(name, link, role, mesh):
        assert name not in out, name
        out[name] = {"link": link, "role": role, "mesh": mesh}

    # 관절 모듈 · 띠 · 끝 덮개 · 덮개 사선(관절 k 의 고정자는 링크 k−1)
    for k in range(1, 7):
        O, a = fk[k - 1]["origin"], fk[k - 1]["axis"] * sign[k - 1]
        R = RDs[k - 1]
        if R - RC >= 1:
            c = e3["drum_chamfer_mm"]
            prof = [(-D / 2 - LC, 0), (-D / 2 - LC, RC), (-D / 2, RC), (-D / 2, R - c), (-D / 2 + c, R), (D / 2 - RW, R), (D / 2 - RW, R - RT),
                    (D / 2, R - RT), (D / 2, 0)]
        else:
            prof = [(-D / 2 - LC, 0), (-D / 2 - LC, RC), (-D / 2 - 2, RC), (-D / 2 - 2, RC - 1.5), (-D / 2, RC - 1.5), (-D / 2, R),
                    (D / 2 - RW, R), (D / 2 - RW, R - RT), (D / 2, R - RT), (D / 2, 0)]
        put(f"J{k}_MODULE", k - 1, "body", revolve(prof, O, a))
        put(f"J{k}_ACCENT_RING", k - 1, "accent", revolve([(D / 2 - RW, R - RT), (D / 2 - RW, R), (D / 2, R), (D / 2, R - RT)], O, a))
        if k >= 2:
            cc, uf = e3["cap_chamfer_mm"], -D / 2 - LC - CAP
            put(f"J{k}_END_CAP", k - 1, "accent", revolve([(uf, 0), (uf, RC - 1 - cc), (uf + cc, RC - 1), (-D / 2 - LC, RC - 1), (-D / 2 - LC, 0)], O, a))
            cs = mk["cap_slash"]
            n = -a
            hint = np.array([0, 0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
            up = unit(hint - n * np.dot(hint, n))
            right = np.cross(up, n)
            Rl = fk[k - 2]["R_child"] if k >= 2 else np.eye(3)                      # 관절 k 모듈이 그려진 링크(k−1)의 회전
            sh = Rl @ np.asarray(cs.get("shift_link_mm", {}).get(str(k), [0, 0, 0]), float)
            du, dv = float(np.dot(sh, right)), float(np.dot(sh, up))
            poly = [(u + du, v + dv) for u, v in slash(cs["height"], cs["width"])]
            mesh, _r, _u = face_marks(O + a * uf, n, poly, em, right=right)
            put(f"J{k}_CAP_SLASH", k - 1, "highlight", mesh)

    # 베이스(링크 0 · 세계 Z 축 · 원점 0)
    b, b3 = L2["base"], L3["base"]
    Z0 = np.zeros(3)
    fc = b3["foot_chamfer"]
    put("BASE_FOOT", 0, "frame", revolve([(0, 0), (0, b["foot_r"]), (b["foot_h"] - fc, b["foot_r"]), (b["foot_h"], b["foot_r"] - fc), (b["foot_h"], 0)],
                                         Z0, [0, 0, 1]))
    z0, z1, z2, zt = b["foot_h"], b["band_z0"], b["band_z1"], p1["joint1_height_mm"] - D / 2
    r0, rg, rt = b["column_r"], b["column_r"] - RT, b["column_top_r"]
    put("BASE_COLUMN", 0, "body", revolve([(z0, 0), (z0, r0), (z1, r0), (z1, rg), (z2, rg), (z2, rg - 1), (zt, rt), (zt, 0)], Z0, [0, 0, 1]))
    put("BASE_LIGHT_RING", 0, "highlight", revolve([(z1, rg), (z1, r0), (z2, r0), (z2, rg)], Z0, [0, 0, 1]))

    # 링크 1: 어깨 덮개 · 기둥
    s2, s3 = L2["shoulder"], L3["shoulder"]
    T1 = link_T(fk, 1)
    O1, R1 = fk[0]["origin"], fk[0]["R_child"]
    cc = s3["cap_chamfer"]
    put("LINK1_SHOULDER_CAP", 1, "body", revolve([(D / 2, 0), (D / 2, s2["cap_r"]), (D / 2 + s2["cap_h"] - cc, s2["cap_r"]),
                                                  (D / 2 + s2["cap_h"], s2["cap_r"] - cc), (D / 2 + s2["cap_h"], 0)], O1, R1[:, 2]))
    cy, hy = (s2["post_y0"] + s2["post_y1"]) / 2, (s2["post_y1"] - s2["post_y0"]) / 2
    post = trimesh.creation.extrude_polygon(Polygon(octagon(s2["post_half_w"], hy, s3["post_chamfer"])), p1["shoulder_rise_mm"] - D / 2)
    post.apply_translation([0, cy, D / 2])
    post.apply_transform(T1)
    put("LINK1_POST", 1, "body", post)

    # 허브 · 허브 덮개 · 허브 사선 · 막대(링크 2 · 3 · 5)
    hc = e3["hub_chamfer_mm"]
    for link, key, hub, bar, out_sign, scale, cut in ((2, "upper_arm", "LINK2_SHOULDER_HUB", "LINK2_UPPER_BAR", 1, 1.0, False),
                                                      (3, "forearm", "LINK3_ELBOW_HUB", "LINK3_FOREARM_BAR", -1, 1.0, True),
                                                      (5, "wrist2", "LINK5_WRIST_HUB", "LINK5_WRIST_BAR", 1, 0.8, True)):
        O, R = fk[link - 1]["origin"], fk[link - 1]["R_child"]
        y = R[:, 1]
        r, t = L2[key]["hub_r"], L2[key]["hub_t"]
        u0, u1 = (D / 2, D / 2 + t) if out_sign > 0 else (-D / 2 - t, -D / 2)
        put(hub, link, "body", revolve([(u0, 0), (u0, r - hc), (u0 + hc, r), (u1 - hc, r), (u1, r - hc), (u1, 0)], O, y))
        a_out = y * out_sign
        uf = D / 2 + t
        rd = r - hc - 2
        put(hub + "_CAP", link, "accent", revolve([(uf, 0), (uf, rd), (uf + 1, rd), (uf + 1, 0)], O, a_out))
        cs = mk["cap_slash"]
        mesh, _r, _u = face_marks(O + a_out * (uf + 1), a_out, slash(cs["height"] * scale, cs["width"] * scale), em)
        put(hub + "_SLASH", link, "highlight", mesh)
        b3l = L3[key]
        yc = out_sign * (D / 2 + t / 2)
        hw, hh, c = L2[key]["tube_r"], L2[key]["tube_r"], b3l["bar_chamfer"]
        x1 = p1["upper_arm_mm"] if link == 2 else L2[key]["tube_len"]
        edge = (out_sign * math.sqrt((RC - 0.5) ** 2 - hh ** 2)) if cut else None
        m = bar_local(hw, hh, c, 0.0, x1, yc, edge)
        m.apply_transform(link_T(fk, link))
        put(bar, link, "body", m)

    # 링크 2 글자(앞에서 보이는 −y 면 · 오른쪽 = 링크 x · 위 = 링크 z)
    lg = mk["logo"]
    u2 = L2["upper_arm"]
    O2, R2 = fk[1]["origin"], fk[1]["R_child"]
    face_y = (D / 2 + u2["hub_t"] / 2) - u2["tube_r"]
    h = lg["cap_height"]
    x_left = lg["center_x"] - logo_width * h / 2
    for nm, role, pts in logo_rows:
        poly = [(x_left + px * h, (py - 0.5) * h) for px, py in pts]
        mesh, _r, _u = face_marks(O2 + R2 @ np.array([0, face_y, 0]), -R2[:, 1], poly, em, right=R2[:, 0])
        put(f"LINK2_LOGO_{nm}", 2, "accent" if role == "navy" else "highlight", mesh)

    # 링크 4 목
    w2, w3 = L2["wrist1"], L3["wrist1"]
    x0, x1 = D / 2, p1["wrist_offsets_mm"][0] - w2["neck_gap"]
    neck = trimesh.creation.extrude_polygon(Polygon(octagon(w2["neck_w"] / 2, w2["neck_h"] / 2, w3["neck_chamfer"])), x1 - x0)
    neck.apply_transform(np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float))
    neck.apply_transform(link_T(fk, 4))
    put("LINK4_NECK", 4, "body", neck)

    # 링크 6 공구 — 플랜지 바깥 = v2 값 · 돌기 · 인서트 구멍 넷 = 그리퍼 규격 · 원장(tif · MP9 2 단계)
    t2, t3 = L2["tool"], L3["tool"]
    O6, R6 = fk[5]["origin"], fk[5]["R_child"]
    a6, y6, z6 = R6[:, 0], R6[:, 1], R6[:, 2]
    tc = t3["flange_chamfer"]
    flange = revolve([(D / 2, 0), (D / 2, t2["flange_r"]), (D / 2 + t2["flange_t"] - tc, t2["flange_r"]),
                      (D / 2 + t2["flange_t"], t2["flange_r"] - tc), (D / 2 + t2["flange_t"], 0)], O6, a6)
    f1 = D / 2 + t2["flange_t"]
    cyls = []
    h = tif["hole_depth"] + 1.0                                              # 면 위로 1 더(구멍이 면을 뚫음)
    for i in range(tif["count"]):
        ang = math.radians(tif["phase_deg"] + i * 360.0 / tif["count"])
        c = O6 + a6 * (f1 - tif["hole_depth"] + h / 2) + y6 * (tif["pcd"] / 2 * math.cos(ang)) + z6 * (tif["pcd"] / 2 * math.sin(ang))
        cyl = trimesh.creation.cylinder(radius=tif["hole_d"] / 2, height=h, sections=SECTIONS)
        T = np.eye(4)
        T[:3, :3] = np.column_stack([y6, z6, a6])                           # 원통 z → J6 축
        T[:3, 3] = c
        cyl.apply_transform(T)
        cyls.append(cyl)
    put("LINK6_TOOL_FLANGE", 6, "frame", trimesh.boolean.difference([flange] + cyls, engine="manifold"))
    put("LINK6_TOOL_RING", 6, "highlight", revolve([(f1, 0), (f1, tif["boss_r"]), (f1 + tif["boss_t"], tif["boss_r"]), (f1 + tif["boss_t"], 0)], O6, a6))
    return out


def point_mesh_distance(points, mesh, samples=60000, k=24, seed=0):
    """점들 → 메시 표면 거리(rtree 없이). 표면 표본 + 꼭짓점의 KD 트리로 가까운 면 후보 k 개를 고르고 그 면까지의 정확한 거리 중 최소.
    참 최근접 면이 후보에서 빠지면 거리가 **크게** 나온다(보수적 — 잘못된 형상을 통과시키는 쪽이 아님)."""
    from scipy.spatial import cKDTree
    pts_s, fid = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    vf = np.asarray(mesh.vertex_faces)[:, 0]
    keep = vf >= 0
    P = np.vstack([pts_s, np.asarray(mesh.vertices)[keep]])
    F = np.concatenate([fid, vf[keep]])
    _d, idx = cKDTree(P).query(points, k=k)
    cand = F[idx]                                                # (n, k)
    n = len(points)
    tri = np.asarray(mesh.triangles)[cand.reshape(-1)]           # (n·k, 3, 3)
    q = np.repeat(np.asarray(points, float), k, axis=0)
    cp = trimesh.triangles.closest_point(tri, q)
    d = np.linalg.norm(cp - q, axis=1).reshape(n, k).min(axis=1)
    # 후보 방식은 가늘고 긴 면(모따기 원뿔 등)에서 최근접 면을 놓칠 수 있다 → 0.005 mm 를 넘는 점은 모든 면에 대해 정확히 다시 잰다
    T = np.asarray(mesh.triangles)
    for i in np.nonzero(d > 0.005)[0]:
        p = np.asarray(points[i], float)
        cpa = trimesh.triangles.closest_point(T, np.repeat(p[None], len(T), axis=0))
        d[i] = float(np.linalg.norm(cpa - p, axis=1).min())
    return d


def surface_distance(stl, exp, samples=4000, seed=0):
    """양방향: STL 꼭짓점 → 기대 표면 최대 거리 · 기대 표면(꼭짓점 + 고른 표본) → STL 표면 최대 거리(mm)."""
    d1 = point_mesh_distance(np.asarray(stl.vertices), exp, seed=seed)
    pts = np.vstack([exp.vertices, trimesh.sample.sample_surface_even(exp, samples, seed=seed)[0]])
    d2 = point_mesh_distance(pts, stl, seed=seed + 1)
    return float(d1.max()), float(d2.max())
