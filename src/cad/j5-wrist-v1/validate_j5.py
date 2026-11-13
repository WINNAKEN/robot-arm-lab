# -*- coding: utf-8 -*-
"""MP10 검사기 — 커밋된 J5 부품 STL 로 스스로 계산한다(계획 056 의 C0 ~ C9). 생성기(j5geom.py)를 부르지 않는다.

C0 만들기 기록 sha = 지금 파일 · C1 닫힘 · manifold 부피 = 메시 부피 > 0 · C2 독립 정답 형상 ↔ STL 양방향 표면 거리 ≤ 0.03 ·
C3 조립 겹침 · 틈(닿기로 한 쌍만 면 접촉) · C4 나사(자리 · 바닥을 STL 에 광선을 쏴 잰다) · C5 자리(v1 parameters 독립 순기구학 ↔ kinematics.json) ·
C6 J4 한 바퀴 ↔ v3 링크 0 ~ 3 · C7 단면 벽 두께 · C8 출력 준비 기록 · C9 J5 한 바퀴 허브 ↔ 고정 쪽.
쓰기 = guard 로 models/j5-wrist-v1 · .dev/mp10-evidence · 작업 뿌리.
사용: python validate_j5.py --scratch-root <작업 뿌리> [--model-dir <부품 폴더의 부모>] [--out <check.json>] [--no-print-record] [--fast]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import manifold3d as m3
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import expected_j5 as E  # noqa: E402
import guard  # noqa: E402

PARTS = ["J5_STATOR_A", "J5_STATOR_B", "J5_REAR_COVER", "J5_OUTPUT_HUB"]
A, B, CV, HB = PARTS
MP6_PARTS = ["HOUSING_BASE", "HOUSING_CAP", "RETAINER", "OUTPUT_FLANGE", "CARRIER"]
SHAPE_TOL = 0.03
CONTACT_OVERLAP = 0.5     # mm³ — 면 접촉 쌍(다각형 근사 차)
FREE_OVERLAP = 1e-3       # mm³ — 그 밖의 쌍
TOUCH_GAP = 0.01          # 면 접촉 쌍은 실제로 닿아야 한다
THIN_AREA = 1.5           # mm² — 단면 열림(반지름 = min_wall/2)이 지운 한 조각이 이보다 크면 얇은 벽. 45° 예각 모서리 하나가 지우는 넓이 =
                          # r²(cot 22.5° − 3π/8) ≈ 1.24(r ≈ 1) — 얇은 벽이 아님(타이 구멍이 45° 경사면을 뚫는 곳 · 2 차). 길이 1 mm 넘는 2 mm 미만 벽은 이보다 크다.


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_part(p):
    tm = trimesh.load(p)
    return tm, E.to_manifold(tm)


def bbox(man):
    v = np.asarray(man.to_mesh().vert_properties)[:, :3]
    return (v.min(0), v.max(0)) if len(v) else (np.zeros(3), np.zeros(3))


def bbox_gap(b1, b2):
    d = np.maximum(0.0, np.maximum(b1[0] - b2[1], b2[0] - b1[1]))
    return float(np.linalg.norm(d))


def intervals(man, p0, p1):
    """선분 p0 → p1 위의 재료 구간 [(들어감 mm, 나감 mm)] — ray_cast 의 distance 는 선분 길이에 대한 비율."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    d = (p1 - p0) / L
    out, cur = [], None
    for h in man.ray_cast(tuple(p0), tuple(p1)):
        s = float(h.distance) * L
        if float(np.dot(h.normal, d)) < 0:
            if cur is None:
                cur = s
        elif cur is not None:
            out.append((cur, s))
            cur = None
    if cur is not None:                                             # 선분 끝이 재료 안 — 끝까지를 구간으로
        out.append((cur, L))
    return out


def first_in(man, p0, p1):
    iv = intervals(man, p0, p1)
    return None if not iv else iv[0][0]


def rot(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def fk_v1(p1):
    """독립 순기구학 — v1 parameters 의 거리 · axis_parent_zero · pose_deg 만. 반환 = 관절 원점 · 세계 축 · 관절 뒤 링크 회전."""
    offs = [[0, 0, p1["joint1_height_mm"]], [0, 0, p1["shoulder_rise_mm"]], [p1["upper_arm_mm"], 0, 0], [p1["forearm_mm"], 0, 0],
            [p1["wrist_offsets_mm"][0], 0, 0], [p1["wrist_offsets_mm"][1], 0, 0]]
    R, p = np.eye(3), np.zeros(3)
    O, Ax, Rc = [], [], []
    for k in range(6):
        ax = np.asarray(p1["axis_parent_zero"][k], float)
        p = p + R @ np.asarray(offs[k], float)
        O.append(p.copy())
        Ax.append(R @ ax)
        R = R @ rot(ax, p1["pose_deg"][k])
        Rc.append(R.copy())
    return O, Ax, Rc


def transform(man, R, t):
    M = np.hstack([np.asarray(R, float), np.asarray(t, float).reshape(3, 1)])
    return man.transform(M)


def polygons_to_shape(cs):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    outer, holes = [], []
    for loop in cs.to_polygons():
        pts = np.asarray(loop)
        if len(pts) < 3:
            continue
        poly = Polygon(pts)
        a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, np.roll(pts, -1, axis=0)))
        (outer if a > 0 else holes).append(poly.buffer(0))
    return unary_union(outer).difference(unary_union(holes)) if outer else None


def thin_parts(shape, wall):
    r = wall / 2 * 0.999
    opened = shape.buffer(-r).buffer(r)
    removed = shape.difference(opened)
    geoms = getattr(removed, "geoms", [removed])
    areas = [g.area for g in geoms if not g.is_empty]
    big = max(areas) if areas else 0.0
    where = None
    if areas:
        g = max((g for g in geoms if not g.is_empty), key=lambda g: g.area)
        where = [round(float(c), 2) for c in g.centroid.coords[0]]
    return big, where


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch-root", required=True, type=Path)
    ap.add_argument("--model-dir", type=Path, default=None)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-print-record", action="store_true")
    ap.add_argument("--fast", action="store_true", help="C6 를 15° 간격으로(대조용)")
    ap.add_argument("--checks", default="all", help="쉼표로 고른 검사만(대조용) — 예 C1,C2,C3")
    a = ap.parse_args()
    pick = None if a.checks == "all" else set(a.checks.split(","))

    def want(c):
        return pick is None or c in pick
    root = guard.find_root(HERE)
    model = Path(a.model_dir) if a.model_dir else root / "models" / "j5-wrist-v1"
    out_json = guard.checked_file(a.out or model / "check.json", root, a.scratch_root)
    D = E.load(a.params)
    P = D["P"]
    res, summary = {}, {}

    parts = {n: load_part(model / "parts" / f"{n}.stl") for n in PARTS}
    mp6_dir = (a.params.parent / P["sources"]["reducer_parts"]).resolve()
    mp6 = {n: load_part(mp6_dir / f"{n}.stl")[1] for n in MP6_PARTS}

    src_files = {"parameters.json": a.params, "j5geom.py": HERE / "j5geom.py", "build_j5.py": HERE / "build_j5.py"}
    src_files.update({k: (a.params.parent / P["sources"][k]).resolve() for k in ("reducer_json", "reducer_params", "motor_ledger", "fits_ledger")})

    # ---- C0 만들기 기록 ----
    if want("C0"):
        rec_path = model / "build-record.json" if (model / "build-record.json").is_file() else root / ".dev" / "mp10-evidence" / "build" / "build-record.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        out_ok = {f"parts/{n}.stl": rec["outputs_sha256"].get(f"parts/{n}.stl") == sha(model / "parts" / f"{n}.stl") for n in PARTS}
        in_ok = {k: rec["inputs_sha256"].get(k) == sha(v) for k, v in src_files.items()}
        res["C0"] = {"record": str(rec_path.relative_to(root)) if root in rec_path.parents else str(rec_path), "control": rec.get("control"),
                     "outputs": out_ok, "inputs": in_ok}
        summary["C0_build_record_matches_files"] = all(out_ok.values()) and all(in_ok.values()) and rec.get("control") is None

    # ---- C1 메시 ----
    if want("C1"):
        rows = []
        for n, (tm, man) in parts.items():
            mv, tv = float(man.volume()), float(tm.volume)
            rows.append({"part": n, "watertight": bool(tm.is_watertight), "mesh_mm3": tv, "manifold_mm3": mv,
                         "ok": bool(tm.is_watertight) and mv > 0 and abs(mv - tv) <= 1e-6 * max(1.0, tv)})
        res["C1"] = rows
        summary["C1_parts_closed_and_manifold_equals_mesh"] = all(r["ok"] for r in rows)

    # ---- C2 독립 정답 형상 ----
    if want("C2"):
        exp = E.expected_parts(D)
        rows = []
        for n in PARTS:
            d1, d2 = E.surface_distance(parts[n][0], E.to_trimesh(exp[n]))
            rows.append({"part": n, "stl_to_expected_mm": d1, "expected_to_stl_mm": d2, "expected_mm3": float(exp[n].volume()),
                         "ok": d1 <= SHAPE_TOL and d2 <= SHAPE_TOL})
        res["C2"] = rows
        summary["C2_every_part_matches_independent_expected_shape"] = all(r["ok"] for r in rows)

    # ---- C3 조립 겹침 · 틈 ----
    bodies, group, seat_of = {}, {}, {}
    for n in PARTS:
        bodies[n], group[n] = parts[n][1], "part"
    for n, m in mp6.items():
        bodies[n], group[n] = m, "mp6"
    for n, m in E.assumed_boxes(D).items():
        bodies[n], group[n] = m, "box"
    for n, (head, shank, seat) in E.screw_solids(D).items():
        own = not n.startswith("MP6_")
        bodies[n + "_HEAD"], group[n + "_HEAD"] = head, ("screw" if own else "mp6screw")
        seat_of[n + "_HEAD"] = seat
        if shank is not None:
            bodies[n + "_SHANK"], group[n + "_SHANK"] = shank, "screw"
    bb = {n: bbox(m) for n, m in bodies.items()}
    contact = {frozenset(p) for p in [(A, "MOTOR"), (B, "MOTOR"), (A, "HOUSING_BASE"), (B, "HOUSING_BASE"), (HB, "OUTPUT_FLANGE"), (CV, A), (CV, B),
                                      (A, "CONNECTOR"), (A, "TERM_P"), (B, "TERM_P"), (A, "TERM_N"), (B, "TERM_N")]}
    contact |= {frozenset((h, s)) for h, s in seat_of.items() if group[h] == "screw"}

    def gmin(x, y):
        s = {x, y}
        if s == {A, B}:
            return 0.5
        if s & {A, B} and any(t.startswith("MOTOR_CABLE_") for t in s):      # 모터 커넥터(11/01 실측) — 사진 어림 · 가운데 두 자리 모두 0.5 이상 떠야
            return 0.5
        if s & {A, B, CV} and "DRIVER" in s:
            return 0.5
        if s & {A, B} and any(t.startswith("MP6_CAP_HEAD") for t in s):
            return 0.3
        if HB in s and (s & {"RETAINER", "HOUSING_CAP"} or any(t.startswith("MP6_RET_HEAD") for t in s)):
            return 1.0
        if s & {A, B} and s & {"HOUSING_CAP", "RETAINER", "OUTPUT_FLANGE", "CARRIER"}:
            return 1.0
        return 0.0
    pairs = []
    names = list(bodies)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            gx, gy = group[x], group[y]
            if "part" not in (gx, gy) and not ("screw" in (gx, gy) and {gx, gy} & {"mp6", "box"}):
                continue                                            # MP6 · 상자 · 남의 나사끼리는 이 단위 밖
            if gx == gy == "screw":
                continue
            pairs.append((x, y))
    if want("C3"):
        rows = []
        for x, y in pairs:
            key = frozenset((x, y))
            wgap = gmin(x, y)
            search = max(wgap, TOUCH_GAP) + 1.0
            if bbox_gap(bb[x], bb[y]) > search:
                continue
            ov = float((bodies[x] ^ bodies[y]).volume())
            gap = float(bodies[x].min_gap(bodies[y], search))
            if key in contact:
                ok = ov <= CONTACT_OVERLAP and gap <= TOUCH_GAP
                kind = "contact"
            else:
                ok = ov <= FREE_OVERLAP and (wgap == 0.0 or gap >= wgap - 1e-6)
                kind = "free"
            rows.append({"a": x, "b": y, "kind": kind, "overlap_mm3": ov, "gap_mm": gap, "min_gap_wanted": wgap, "ok": ok})
        missing_contacts = sorted("/".join(sorted(k)) for k in contact if not any(frozenset((r["a"], r["b"])) == k for r in rows))
        res["C3"] = {"rows": rows, "contact_pairs_not_evaluated": missing_contacts, "bad": [r for r in rows if not r["ok"]]}
        summary["C3_assembly_overlap_and_gaps"] = all(r["ok"] for r in rows) and not missing_contacts

    mA, mB, mC, mH = (parts[n][1] for n in PARTS)                       # C4 · C5 가 같이 쓴다(C4 를 빼고 돌릴 때도 — 대조 neck_shift 가 찾음)

    # ---- C4 나사(광선으로 잰 자리 · 바닥) ----
    if want("C4"):
        srows = []
        avail, minE, minT, ilen = D["avail"], float(P["min_engagement"]), float(P["min_tip_to_floor"]), D["insert_len"]
        off = 2.4                                                       # 구멍(1.7) 과 자리파기(3.1) 사이
        Rr, zr0 = D["R"], D["z_rear"]
        xs = -(Rr + 10.0)                                               # 광선 시작 · 끝은 원천 값에서(검토 R-7)
        cb = D["cb"]
        for y in (cb["y"], -cb["y"]):
            for z in cb["z"]:
                seat = first_in(mA, (xs, y + off, z), (0.0, y + off, z))
                seat = None if seat is None else xs + seat
                axis_clear = not intervals(mA, (seat + 0.2 if seat else -10.0, y, z), (-0.4, y, z)) if seat is not None else False
                face_b = first_in(mB, (-1.0, y + off, z), (5.0, y + off, z))
                face_b = None if face_b is None else -1.0 + face_b
                floor = first_in(mB, (0.0, y, z), (Rr + 5.0, y, z))
                floor = None if floor is None else floor
                L = cb["len"]
                r = {"screw": f"clamp y{y:+.0f} z{z:+.0f}", "length": L, "seat": seat, "insert_face": face_b, "floor": floor, "hole_clear_in_A": axis_clear}
                if None not in (seat, face_b, floor):
                    tip = seat + L
                    r.update({"tip": tip, "engagement": min(tip, face_b + ilen) - face_b, "tip_to_floor": floor - tip})
                    r["ok"] = L in avail and r["engagement"] >= minE and r["tip_to_floor"] >= minT and axis_clear
                else:
                    r["ok"] = False
                srows.append(r)
        cv, zr = D["cover"], D["z_rear"]
        for ang in cv["ang"]:
            x, y = E.polar(cv["r"], ang)
            half = mA if x < 0 else mB
            ox, oy = E.polar(cv["r"] + off, ang)
            zlo = zr0 - cv["t"] - 20.0
            seat = first_in(mC, (ox, oy, zlo), (ox, oy, zr0 + 1.0))
            seat = None if seat is None else zlo + seat
            face = first_in(half, (ox, oy, zlo), (ox, oy, zr0 + cv["depth"] + 10.0))
            face = None if face is None else zlo + face
            floor = first_in(half, (x, y, zr - 0.3), (x, y, 0.0))
            floor = None if floor is None else zr - 0.3 + floor
            L = cv["len"]
            r = {"screw": f"cover {ang:.0f} deg", "length": L, "seat": seat, "insert_face": face, "floor": floor}
            if None not in (seat, face, floor):
                tip = seat + L
                r.update({"tip": tip, "engagement": min(tip, face + ilen) - face, "tip_to_floor": floor - tip})
                r["ok"] = L in avail and r["engagement"] >= minE and r["tip_to_floor"] >= minT
            else:
                r["ok"] = False
            srows.append(r)
        mp = D["mp6"]
        mp6_tip = mp["output_face"] - mp["flange_len"]                    # MP6 이 검사한 출력 플랜지 나사 끝 자리(물림 · 바닥 여유는 MP6 cycloid.json)
        for i in range(mp["out_n"]):
            ang = mp["out_ph"] + 360.0 * i / mp["out_n"]
            x, y = E.polar(mp["out_ins_r"], ang)
            ox, oy = E.polar(mp["out_ins_r"] + off, ang)
            ztop, zbot_ = D["hub_z"][1] + 15.0, D["hub_z"][0] - 3.0
            seat = first_in(mH, (ox, oy, ztop), (ox, oy, zbot_))
            seat = None if seat is None else ztop - seat
            clear = not intervals(mH, (x, y, ztop), (x, y, zbot_))
            L = mp["flange_len"] + D["hub"]["under"]
            r = {"screw": f"hub {ang:.0f} deg", "length": L, "seat": seat, "hole_clear_in_hub": clear, "mp6_tip": mp6_tip}
            if seat is not None:
                r["tip"] = seat - L
                r["ok"] = L in avail and abs(r["tip"] - mp6_tip) <= 1e-3 and clear
            else:
                r["ok"] = False
            srows.append(r)
        n = D["neck"]
        for i in range(n["n"]):
            ang = n["ph"] + 360.0 * i / n["n"]
            u, v = E.polar(n["r"], ang)
            ou, ov_ = E.polar(n["r"] + off, ang)
            xa, xb = n["x"] + n["t"] + 10.0, n["x"] - 10.0
            seat = first_in(mA, (xa, ou, D["j4z"] + ov_), (xb, ou, D["j4z"] + ov_))
            seat = None if seat is None else xa - seat
            fu, fv = E.polar(n["r"] + 5.0, ang)
            iv = intervals(mA, (xa, fu, D["j4z"] + fv), (xb, fu, D["j4z"] + fv))
            face = None if not iv else xa - iv[0][1]
            clear = not intervals(mA, (xa, u, D["j4z"] + v), (xb, u, D["j4z"] + v))
            L = mp["flange_len"] + n["under"]
            r = {"screw": f"neck {ang:.0f} deg", "length": L, "seat": seat, "j4_face": face, "hole_clear_in_plate": clear}
            if None not in (seat, face):
                r.update({"tip": seat - L, "j4_tip_assumed": face - mp["flange_len"]})
                r["ok"] = L in avail and abs(r["tip"] - r["j4_tip_assumed"]) <= 1e-3 and clear
            else:
                r["ok"] = False
            srows.append(r)
        res["C4"] = srows
        summary["C4_screws_length_engagement_floor"] = all(r["ok"] for r in srows) and len(srows) == 16

    # ---- C5 자리 ----
    v1dir = (a.params.parent / P["sources"]["v1_dir"]).resolve()
    p1 = json.loads((v1dir / "parameters.json").read_text(encoding="utf-8"))
    kin = json.loads((v1dir / "kinematics.json").read_text(encoding="utf-8"))
    O, Ax, Rc = fk_v1(p1)
    J4, J5 = kin["joints"][3], kin["joints"][4]
    R4, O4 = Rc[3], O[3]
    Mm = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])            # 모듈 → 링크 4: (x, y, z) → (x, z, −y)
    t_m = np.array([D["wrist0"], float(P["placement"]["motor_face_from_joint_along_axis"]), 0.0])
    Rw, tw = R4 @ Mm, O4 + R4 @ t_m
    if want("C5"):
        # 목판 면 가운데 = 판 단면(아래 앞 모따기 · 받침을 피한 x)의 나사 구멍 넷 중심의 평균 · 면 x = 반쪽 A 의 가장 작은 x
        # 단면 좌표: y 축 둘레 −90° 돌림 → (x, y, z) → (−z, y, x) · 단면 평면 좌표 = (−z, y)
        sec = polygons_to_shape(transform(mA, rot([0, 1, 0], -90), [0, 0, 0]).slice(D["neck"]["x"] + D["neck"]["fch"] + 0.5))
        hole_a = math.pi * (D["m3"] / 2) ** 2
        holes = []
        for g in (getattr(sec, "geoms", [sec]) if sec is not None else []):
            for ring in g.interiors:
                from shapely.geometry import Polygon
                pg = Polygon(ring)
                if abs(pg.area - hole_a) <= 0.05 * hole_a:
                    holes.append((pg.centroid.x, pg.centroid.y))
        if len(holes) == D["neck"]["n"]:
            hx, hy = np.mean(np.asarray(holes), axis=0)
            face_y, face_z = float(hy), float(-hx)
        else:
            face_y = face_z = float("nan")
        face_min_x = float(parts[A][0].bounds[0][0])
        face_w = Rw @ np.array([face_min_x, face_y, face_z]) + tw
        want_face = np.asarray(J4["origin_mm"], float) + float(P["neck"]["j4_face_x_link4"]) * np.asarray(J4["axis_world"], float)
        c5 = {"fk_vs_kinematics_J4_origin_mm": float(np.linalg.norm(O4 - np.asarray(J4["origin_mm"], float))),
              "fk_vs_kinematics_link4_R": float(np.abs(R4 - np.asarray(J4["R_child"], float)).max()),
              "module_z_axis_vs_J5_axis": float(np.linalg.norm(Rw @ np.array([0, 0, 1.0]) - np.asarray(J5["axis_world"], float))),
              "module_J5_point_vs_J5_origin_mm": float(np.linalg.norm(Rw @ np.array([0, 0, -t_m[1]]) + tw - np.asarray(J5["origin_mm"], float))),
              "neck_face_center_module": [face_min_x, face_y, face_z], "neck_face_vs_J4_origin_plus_axis_mm": float(np.linalg.norm(face_w - want_face))}
        c5["ok"] = (c5["fk_vs_kinematics_J4_origin_mm"] <= 1e-6 and c5["fk_vs_kinematics_link4_R"] <= 1e-9 and c5["module_z_axis_vs_J5_axis"] <= 1e-9
                    and c5["module_J5_point_vs_J5_origin_mm"] <= 1e-6 and c5["neck_face_vs_J4_origin_plus_axis_mm"] <= 0.05)
        res["C5"] = c5
        summary["C5_placement_on_v1_joints"] = c5["ok"]

    # ---- C6 J4 한 바퀴 ↔ v3 링크 0 ~ 3 ----
    if want("C6"):
        v3 = root / "models" / "armold-mks-product-v3"
        v3b = json.loads((v3 / "bodies.json").read_text(encoding="utf-8"))["bodies"]
        arm = {b["name"]: E.to_manifold(trimesh.load(v3 / "meshes" / f"{b['name']}.stl")) for b in v3b if b["link"] <= 3}
        arm_bb = {k: bbox(m) for k, m in arm.items()}
        # J4 쪽 목 나사 몸통은 J4 출력 플랜지 · 캐리어로 들어가는 것이 설계(v3 J4 덩어리 안 226 mm³ = 넷 × 8 mm)라 뺀다
        mod = m3.Manifold.batch_boolean([bodies[k] for k in bodies if group[k] in ("part", "mp6", "box", "screw")
                                         and not (k.startswith("NECK_SCREW") and k.endswith("_SHANK"))], m3.OpType.Add)
        mod_w = transform(mod, Rw, tw)
        a4 = np.asarray(Ax[3], float)
        face_ok = {"J4_MODULE", "J4_ACCENT_RING"}
        step = 15 if a.fast else 5
        worst, hits = [], []
        for q in range(-180, 180, step):
            Rq = rot(a4, q)
            mq = transform(mod_w, Rq, O4 - Rq @ O4)
            bq = bbox(mq)
            for k, m in arm.items():
                if bbox_gap(bq, arm_bb[k]) > 0.0:
                    continue
                ov = float((mq ^ m).volume())
                lim = CONTACT_OVERLAP if k in face_ok else FREE_OVERLAP
                if ov > lim:
                    hits.append({"q4_delta_deg": q, "v3_body": k, "overlap_mm3": ov})
                worst.append(ov if k not in face_ok else 0.0)
        gap0 = {k: float(mod_w.min_gap(m, 20.0)) for k, m in arm.items() if bbox_gap(bbox(mod_w), arm_bb[k]) <= 20.0}
        res["C6"] = {"step_deg": step, "hits": hits, "display_pose_min_gap_mm": gap0, "contact_allowed": sorted(face_ok)}
        summary["C6_j4_full_turn_free_of_v3_links_0_3"] = not hits

    # ---- C7 단면 벽 ----
    if want("C7"):
        mw = D["min_wall"]
        zr0, zm, rz0, zd = D["z_rear"], -D["motor"]["body_length"], D["ring"][1], D["z_drv"]
        cn, sl, nk, hb_, cvv, cbz = D["con"], D["slot"], D["neck"], D["hub"], D["cover"], D["cb"]["z"]
        zs_half = sorted({-0.5, -D["notch"][1] / 2, rz0 - 1.0, *cbz, (zm + rz0) / 2, zm + 2.0, zd[1] + 0.5, (zd[0] + zd[1]) / 2,
                          (sl["z"][0] + sl["z"][1]) / 2, zd[0] + 1.0, zr0 + 1.5})          # 뒤 끝면 + 1.5(+ 2.0 은 이음 창 바닥과 같은 평면 — 검토 R3-8)
        tm, ts = D["term"], D["tslot"]
        zs_half = sorted(set(zs_half) | {tm["z"][1] + tm["x"] / 2, tm["z"][1] + tm["x"] - 1.0, (ts["z"][0] + ts["z"][1]) / 2,
                                         ts["z"][1] + ts["x"] / 2})                                  # 단자대 칸 박공 · 이음 창 · 박공
        zs_a = sorted(set(zs_half) | {cn["z"][1] + cn["y"] / 2, cn["z"][1] + cn["y"] - 1.0})          # 박공(커넥터 칸 위)
        mk = D["mconn"]                                                                                # 모터 커넥터 앞 칸(11/01) — 박공 끝 위 · 가운데 · 꼭대기 밑
        mhalf = (mk["y"][1] - mk["y"][0]) / 2
        zs_a = sorted(set(zs_a) | {mk["z_end"] + 1.0, mk["z_end"] + mhalf / 2, mk["z_end"] + mhalf - 1.0})
        xs_mk = [p[0] + 0.5 for p in mk["parts"]] + [(mk["parts"][1][0] + mk["x_in"]) / 2]
        ys_mk = [mk["y"][0] + 1.0, (mk["y"][0] + mk["y"][1]) / 2, mk["y"][1] - 1.0]
        rib_y = [y for y in D["rib"]["y"]]
        ty_mid = (tm["y"][0] + tm["y"][1]) / 2
        ys = sorted({0.0, D["cb"]["y"], *rib_y, D["route"]["tie_y"], ty_mid, -ty_mid})
        xs_a = [nk["x"] + 0.3, nk["x"] + 5.0, nk["x"] + nk["t"] - 1.0, (nk["x"] + nk["t"] + nk["wx"]) / 2, *D["route"]["tie_x"], -ts["x"] / 2, -1.0]
        # 단면 자리는 원천 값에서(검토 R-7 — 모터 원장 값이 바뀌어도 따라온다)
        plan = {A: [("z", z) for z in zs_a] + [("x", x) for x in xs_a + xs_mk] + [("y", y) for y in sorted(set(ys) | set(ys_mk))],
                B: [("z", z) for z in zs_half] + [("x", ts["x"] / 2), ("x", 1.0)] + [("y", y) for y in ys],
                CV: [("z", zr0 - cvv["t"] + 0.4), ("z", zr0 - cvv["t"] / 2)],
                HB: [("z", D["hub_z"][0] + 0.5), ("z", D["hub_z"][0] + hb_["under"] + 1.0), ("z", D["hub_z"][1] - hb_["ch"] - 0.5),
                     ("z", D["hub_z"][1] - 0.1)]}
        wrows = []
        for nme, cuts in plan.items():
            for ax_, h in cuts:
                m = parts[nme][1]
                if ax_ == "x":
                    m = transform(m, rot([0, 1, 0], -90), [0, 0, 0])
                elif ax_ == "y":
                    m = transform(m, rot([1, 0, 0], 90), [0, 0, 0])
                shape = polygons_to_shape(m.slice(h))
                if shape is None or shape.is_empty:
                    wrows.append({"part": nme, "plane": f"{ax_}={h}", "empty": True, "ok": False})
                    continue
                big, where = thin_parts(shape, mw)
                wrows.append({"part": nme, "plane": f"{ax_}={h}", "thin_area_mm2": big, "where": where, "ok": big <= THIN_AREA})
        res["C7"] = wrows
        summary["C7_section_walls_at_least_min_wall"] = all(r["ok"] for r in wrows)

    # ---- C8 출력 준비 기록 ----
    if a.no_print_record or not want("C8"):
        res["C8"] = {"not_run": "control run"}
    else:
        pr_path = root / ".dev" / "mp10-evidence" / "printprep.json"
        if pr_path.is_file():
            pr = json.loads(pr_path.read_text(encoding="utf-8"))
            rows = []
            for nme in PARTS:
                e = pr["parts"].get(nme, {})
                rows.append({"part": nme, "stl_sha_matches": e.get("stl_sha256") == sha(model / "parts" / f"{nme}.stl"), "verdict": e.get("verdict"),
                             "support_needed": e.get("support_needed"), "mass_g": e.get("mass_g"), "time": e.get("time"),
                             "ok": e.get("stl_sha256") == sha(model / "parts" / f"{nme}.stl") and e.get("verdict") == "ready"
                             and e.get("support_needed") is False})                 # 지지대 없이 세워 출력(2 차부터 판정에 넣음)
            res["C8"] = rows
            summary["C8_print_prep_ready"] = all(r["ok"] for r in rows)
        else:
            res["C8"] = {"missing": str(pr_path)}
            summary["C8_print_prep_ready"] = False

    # ---- C9 J5 한 바퀴 ----
    if want("C9"):
        rotor = [HB] + [k for k in bodies if k.startswith("HUB_SCREW")]
        stator = [A, B, "HOUSING_BASE", "HOUSING_CAP", "RETAINER"] + [k for k in bodies if k.startswith(("MP6_RET_HEAD", "MP6_CAP_HEAD"))]
        rrows = []
        for q in range(0, 360, 15):
            for r_ in rotor:
                mr = bodies[r_].rotate((0.0, 0.0, float(q)))
                for s_ in stator:
                    if bbox_gap(bbox(mr), bb[s_]) > 2.0:
                        continue
                    ov = float((mr ^ bodies[s_]).volume())
                    gp = float(mr.min_gap(bodies[s_], 2.0))
                    wg = 1.0 if r_ == HB else 0.5
                    if ov > FREE_OVERLAP or gp < wg - 1e-6:
                        rrows.append({"q5_deg": q, "rotor": r_, "stator": s_, "overlap_mm3": ov, "gap_mm": gp, "wanted": wg})
        res["C9"] = {"step_deg": 15, "bad": rrows}
        summary["C9_j5_full_turn_hub_clear_of_stator"] = not rrows

    # ---- C3b 닿는 면 넓이(검토 R-6): 한쪽을 닿는 쪽으로 δ 옮긴 겹침 / δ ----
    j4M = E.j4_mp6_transform(D)
    j4p = {n: mp6[n].transform(j4M) for n in ("HOUSING_CAP", "RETAINER", "OUTPUT_FLANGE")}
    if want("C3b"):
        dl, am = 0.05, D["area_min"]

        def area(mov, fix, vec):
            return float((mov.translate(tuple(dl * np.asarray(vec, float))) ^ fix).volume()) / dl
        arows = []
        for nme, mov, fix, vec, key in ((A, bodies[A], bodies["MOTOR"], (1, 0, 0), "halves_motor"), (B, bodies[B], bodies["MOTOR"], (-1, 0, 0), "halves_motor"),
                                        (A, bodies[A], bodies["HOUSING_BASE"], (0, 0, 1), "halves_base"),
                                        (B, bodies[B], bodies["HOUSING_BASE"], (0, 0, 1), "halves_base"),
                                        (HB, bodies[HB], bodies["OUTPUT_FLANGE"], (0, 0, -1), "hub_flange"),
                                        (CV + "/A", bodies[CV], bodies[A], (0, 0, 1), "cover_half"), (CV + "/B", bodies[CV], bodies[B], (0, 0, 1), "cover_half"),
                                        (A + "/J4", bodies[A], j4p["OUTPUT_FLANGE"], (-1, 0, 0), "neck_j4_flange")):
            a_ = area(mov, fix, vec)
            arows.append({"pair": nme, "partner": key, "area_mm2": a_, "min": am[key], "ok": a_ >= am[key]})
        res["C3b"] = arows
        summary["C3b_contact_areas_at_least_minimum"] = all(r["ok"] for r in arows)

    # ---- C6b J4 = MP6 가정(검토 R-3): J4 고정 쪽(덮개 · 누름 고리 · 그 나사 머리)을 J4 축 둘레로 한 바퀴 — 반쪽 A 와 겹침 0 · 틈 ≥ 0.3 ----
    if want("C6b"):
        rh = D["ret_head"]
        j4_stator = [j4p["HOUSING_CAP"], j4p["RETAINER"]]
        for i in range(D["mp6"]["cap_n"]):
            x6, y6 = E.polar(D["mp6"]["ret_r"], D["mp6"]["ret_ph"] + 360.0 * i / D["mp6"]["cap_n"])
            r1 = D["mp6"]["retainer"][1]
            j4_stator.append(E.cyl_z(rh["dia"] / 2, r1, r1 + rh["height"], x6, y6).transform(j4M))
        stat = m3.Manifold.batch_boolean(j4_stator, m3.OpType.Add)
        axis_pt = np.array([0.0, 0.0, D["j4z"]])
        bad6, gmin6 = [], 1e9
        for q in range(0, 360, 5):
            Rq = rot([1, 0, 0], q)
            sq = transform(stat, Rq, axis_pt - Rq @ axis_pt)
            ov = float((sq ^ bodies[A]).volume())
            gp = float(sq.min_gap(bodies[A], 2.0))
            gmin6 = min(gmin6, gp)
            if ov > FREE_OVERLAP or gp < 0.3:
                bad6.append({"q4_deg": q, "overlap_mm3": ov, "gap_mm": gp})
        flange_ov = float((j4p["OUTPUT_FLANGE"] ^ bodies[A]).volume())
        res["C6b"] = {"step_deg": 5, "min_gap_mm": gmin6, "bad": bad6, "j4_flange_overlap_mm3": flange_ov,
                      "note": "J4 = MP6 가정 — 출력 플랜지는 모듈과 함께 돌고(면 접촉) 덮개 · 누름 고리 · 그 나사 머리(R09 둥근머리)는 링크 3 에 고정"}
        summary["C6b_j4_mp6_assumed_turn_clear"] = not bad6 and flange_ov <= CONTACT_OVERLAP

    # ---- C11 창이 밖으로 열림(검토 R3-3): 창 상자 단면 속(가장자리 0.3 안)을 칸 바깥 끝에서 캔 밖까지 막대로 — 반쪽과 겹침 0 ----
    if want("C11"):
        sl, ts, R, e = D["slot"], D["tslot"], D["R"], 0.3
        probes = {"minus_x_spare": ([A], E.box([-(R + 0.5), D["con"]["x"][0] + 0.5], [-(sl["y"] - e), sl["y"] - e], [sl["z"][0] + e, sl["z"][1] - e])),
                  "plus_y": ([A, B], E.box([-(ts["x"] - e), ts["x"] - e], [ts["y"][0] + 1.5, R + 0.5], [ts["z"][0] + e, ts["z"][1] - e])),
                  "minus_y": ([A, B], E.box([-(ts["x"] - e), ts["x"] - e], [-(R + 0.5), -(ts["y"][0] + 1.5)], [ts["z"][0] + e, ts["z"][1] - e]))}
        rows = []
        for k, (halves, pr) in probes.items():
            for h in halves:
                ov = float((pr ^ parts[h][1]).volume())
                rows.append({"window": k, "half": h, "overlap_mm3": ov, "ok": ov <= FREE_OVERLAP})
        res["C11"] = {"rows": rows, "terminal_window": {"width": 2 * ts["x"], "box_height": ts["z"][1] - ts["z"][0], "gable_height": ts["x"],
                                                       "z": ts["z"], "y": ts["y"]},
                      "spare_window": {"width": 2 * sl["y"], "box_height": sl["z"][1] - sl["z"][0], "gable_height": sl["y"]}}
        summary["C11_windows_open_to_outside"] = all(r["ok"] for r in rows)

    # ---- C12 덮개 인서트 구멍 둘레 벽(검토 R3-3): 구멍 둘레 min_wall 고리가 모두 재료 · 구멍 속은 비어 있음 ----
    if want("C12"):
        cv, zr, mw = D["cover"], D["z_rear"], D["min_wall"]
        rows = []
        for ang_ in cv["ang"]:                                                  # 이름 a 는 명령줄 인자(argparse)라 쓰지 않음
            x, y = E.polar(cv["r"], ang_)
            h = A if x < 0 else B
            z0, z1 = zr + 0.3, zr + cv["depth"] - 0.3
            ring = E.cyl_z(D["ins"] / 2 + mw, z0, z1, x, y) - E.cyl_z(D["ins"] / 2 + 0.05, z0 - 1.0, z1 + 1.0, x, y)
            core = E.cyl_z(D["ins"] / 2 - 0.3, z0, z1, x, y)
            rv, inside, core_ov = float(ring.volume()), float((ring ^ parts[h][1]).volume()), float((core ^ parts[h][1]).volume())
            rows.append({"angle_deg": ang_, "half": h, "ring_mm3": rv, "ring_in_material_mm3": inside, "hole_core_overlap_mm3": core_ov,
                         "ok": inside >= 0.995 * rv and core_ov <= FREE_OVERLAP})
        res["C12"] = rows
        summary["C12_cover_insert_holes_walled"] = all(r["ok"] for r in rows)

    # ---- C10 옆에서 밀어 넣기(검토 R-1): 반쪽 A 는 −x 에서 · B 는 +x 에서 최종 자리로 — 지나는 길에 모터 · 드라이버 · 커넥터 · 단자대 둘 · MP6 덮개 나사 머리(겉봉)와 겹치지 않음 ----
    if want("C10"):
        obst = {k: bodies[k] for k in ("MOTOR", "DRIVER", "CONNECTOR", "TERM_P", "TERM_N", "MOTOR_CABLE_EST", "MOTOR_CABLE_MID")}
        obst.update({k: bodies[k] for k in bodies if k.startswith("MP6_CAP_HEAD")})
        steps = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0, 35.0, 40.0, 45.0]
        bad10 = []
        for nme, sgn in ((A, -1.0), (B, 1.0)):
            for st_ in steps:
                mv = bodies[nme].translate((sgn * st_, 0.0, 0.0))
                bmv = bbox(mv)
                for k, ob in obst.items():
                    if bbox_gap(bmv, bb[k]) > 0.0:
                        continue
                    ov = float((mv ^ ob).volume())
                    if ov > FREE_OVERLAP:
                        bad10.append({"half": nme, "out_by_mm": st_, "hits": k, "overlap_mm3": ov})
                ovb = float((mv ^ bodies["HOUSING_BASE"]).volume())
                if ovb > CONTACT_OVERLAP:
                    bad10.append({"half": nme, "out_by_mm": st_, "hits": "HOUSING_BASE", "overlap_mm3": ovb})
        res["C10"] = {"steps_mm": steps, "bad": bad10, "note": "반쪽을 바깥으로 st 만큼 뺀 자리마다(= 밀어 넣는 길) 겹침 — MP6 덮개 나사는 바닥판에 조인 뒤"}
        summary["C10_halves_slide_on_from_the_side"] = not bad10

    out = {"what": "J5 손목 v1 검사(MP10 · 계획 056) — 커밋된 STL 로 스스로 계산", "model_dir": str(model), "summary": summary,
           "all_true": all(summary.values()), "results": res,
           "inputs_sha256": {**{f"parts/{n}.stl": sha(model / "parts" / f"{n}.stl") for n in PARTS},
                             **{k: sha(v) for k, v in src_files.items()}, "expected_j5.py": sha(HERE / "expected_j5.py"), "validate_j5.py": sha(__file__)}}
    guard.write_bytes(out_json, (json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n").encode("utf-8"), root, a.scratch_root)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
