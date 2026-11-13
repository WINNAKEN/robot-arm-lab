# -*- coding: utf-8 -*-
"""MP17 팔 전체 v1 — 검사(커밋된 STL 로 스스로 계산). 결과 = models/manipulator-v1/check.json(대조는 --out).

C0 만들기 기록 sha = 지금 STL · 입력          C1 새 부품 닫힘 · 한 덩어리 · manifold 부피 = 메시 부피
C2 독립 순기구학(v1 parameters) = v1 kinematics.json · 모듈 축 = 관절 축 · 그리퍼 자리 = MP9 행렬
C3 나사 — STL 에 광선(머리 자리 · 지나는 구멍 · 쌓임 틈 · 물림 · 구멍 바닥)
C4 정지 자세(q = 0 · 표시 · 준비) 겹침 — 다른 몸체끼리(같은 기존 모듈 안은 그 단위가 봄) · 맞춤 짝 · 구매품 어림은 따로
C5 관절 훑기 — 관절마다 표시 자세에서 5° · 바라는 범위(parameters poses.wanted_ranges_deg)에서 충돌 없음 + J2 × J3 격자 지도(보고)
C6 구멍 · 자리 지름(STL 단면)                C7 출력 준비 기록 = 지금 STL · ready · 지지대 없음 · 판 안
C8 하중 기록(loads.json) = 지금 입력 · 여유
사용: python check_arm.py [--params P] [--parts DIR] [--out DIR] [--checks C0,C1,...] [--fast]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from pathlib import Path

import manifold3d as m3
import numpy as np
import trimesh

import layout as L

HERE = Path(__file__).resolve().parent
OVERLAP_TOL = 0.05          # mm³ — 나사로 맞붙인 면의 단정밀도 STL 잡음(실측 0.006 이하)
FIT_PAIRS = {   # 맞춤 짝: (겹침 하한, 상한 mm³, 뜻) — 범위 밖이면 C4 거짓(검토 R1-13)
    ("TOOL_FLANGE", "KG1.BASE"): (0.0, 2.0, "boss r 10 into the KG1 recess r 10 (zero clearance by design, MP9 rev1) - polygon chords only; radii in C6"),
    ("MOTOR_COVER_J2", "REF.J2.MOTOR57"): (110.0, 155.0, "6 ribs x 3 wide x 49 long x 0.15 press = 132"),
    ("MOTOR_COVER_J3", "REF.J3.MOTOR57"): (90.0, 127.0, "6 ribs x 3 wide x 40 long x 0.15 press = 108"),
    ("J2_CAP", "J2_CAP_MARK"): (0.0, 4.0, "raised mark printed as one object with its cap (0.02 embedded x 154 mm2 = 3.1)"),
    ("J3_CAP", "J3_CAP_MARK"): (0.0, 4.0, "raised mark printed as one object with its cap (0.02 embedded)"),
    ("UPPER_ARM", "UA_LOGO"): (0.0, 2.0, "raised letters printed as one object with the upper arm (0.02 embedded)")}
MULTI_PIECE = {"UA_LOGO"}           # 글자 다섯 조각(K · K 사선 · M · J · H)
DESIGNED_GAPS = {("J2.OUTPUT_FLANGE", "J2.CARRIER"): 0.2, ("J3.OUTPUT_FLANGE", "J3.CARRIER"): 0.2}     # MP16: 플랜지는 6812 고리 면에 · 캐리어 면은 0.2 아래


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return float(round(float(o), 6))
    return o


def to_man(m):
    return m3.Manifold(m3.Mesh(vert_properties=np.asarray(m.vertices, dtype=np.float32), tri_verts=np.asarray(m.faces, dtype=np.uint32)))


class Arm:
    def __init__(self, params, parts_dir):
        self.params_path = Path(params)
        self.P = L.load(params)
        self.parts_dir = Path(parts_dir)
        self.cat = L.catalog(self.P)
        self.refs = L.refs(self.P)
        self.Fr = L.frames(self.P)
        self.Ts0 = L.link_transforms(self.P, [0.0] * 6)
        self.local = {}
        for n, c in self.cat.items():
            p = self.parts_dir / f"{n}.stl" if c["kind"] == "new" else Path(c["path"])
            self.local[n] = trimesh.load(p, force="mesh")
        for n in L.COUPONS:
            self.local[n] = trimesh.load(self.parts_dir / f"{n}.stl", force="mesh")
        self.head_refs()
        for n, r in self.refs.items():
            if "local_mesh" in r:
                self.local[n] = r["local_mesh"]
                continue
            if "boxes" in r:
                m = trimesh.util.concatenate([trimesh.creation.box(bounds=[[b[0], b[2], b[4]], [b[1], b[3], b[5]]]) for b in r["boxes"]])
            else:
                ri, ro, z0, z1 = r["annulus"]
                m = trimesh.creation.annulus(r_min=ri + 0.05, r_max=ro - 0.05, height=z1 - z0, sections=180)     # 다각형 현 오차 0.05 들임(맞춤은 C6 가 지름으로)
                m.apply_translation([0, 0, (z0 + z1) / 2])
            self.local[n] = m

    def head_refs(self):
        """나사 머리(둥근머리 ISO 7380 Ø5.7 × 1.65 · 그리퍼만 렌치볼트 Ø5.5 × 3.0) + 와셔(Ø7 × 0.5)를 구매품 어림으로 — 첫 조임 부품의 링크(검토 R1-12)."""
        import build_arm as B
        P, g, _s, _l = B.prepare(self.params_path, control="check")
        bh, sk = P["screws"]["button_head"], P["screws"]["socket_head"]
        for s in B.screws(P, g):
            first = s["clamped"][0]
            lk = self.cat[first]["link"]
            a = np.array(s["axis_world"], float)
            a /= np.linalg.norm(a)
            d, k = (sk if s["name"] == "gripper_to_tool_flange" else bh)
            for i, h in enumerate(s["heads_world"]):
                h = np.array(h, float)
                parts = []
                wt = s.get("washer_t", 0.0)
                if wt > 0:
                    w = trimesh.creation.cylinder(radius=3.5, height=wt, sections=48)
                    parts.append((w, h - a * wt / 2))
                c = trimesh.creation.cylinder(radius=d / 2, height=k, sections=48)
                parts.append((c, h - a * (wt + k / 2)))
                for j, (m, ctr) in enumerate(parts):
                    m = m.copy()
                    z = np.array([0.0, 0.0, 1.0])
                    v = np.cross(z, a)
                    if np.linalg.norm(v) > 1e-9:
                        ang = math.acos(max(-1.0, min(1.0, float(np.dot(z, a)))))
                        m.apply_transform(trimesh.transformations.rotation_matrix(ang, v))
                    m.apply_translation(ctr)
                    Mw0 = L.link_transforms(self.P, [0.0] * 6)[lk] @ np.linalg.inv(self.Ts0[lk])        # 세계(q = 0) 그대로 — 틀 W
                    del Mw0
                    self.refs[f"REF.HEAD.{s['name']}.{i}.{j}"] = {"frame": "W", "link": lk, "local_mesh": m}

    def info(self, n):
        return self.cat[n] if n in self.cat else self.refs[n]

    def M(self, n, q):
        i = self.info(n)
        Tq = L.link_transforms(self.P, q)
        return Tq[i["link"]] @ np.linalg.inv(self.Ts0[i["link"]]) @ self.Fr[i["frame"]]

    def placed(self, n, q):
        m = self.local[n].copy()
        m.apply_transform(self.M(n, q))
        return m

    def collide_names(self):
        return [n for n, c in self.cat.items() if c["collide"]] + list(self.refs)


def group(n):
    """같은 기존 모듈 묶음(그 안의 겹침은 그 단위가 이미 봄) — 새 부품 · 구매품 어림은 묶음 없음."""
    if n.startswith("REF.") or "." not in n:
        return None
    return n.split(".")[0] + ("" if n.split(".")[0] in ("J2", "J3", "KG1") else "." + n.split(".")[1])


# ---------------- C0 · C1 ----------------
def c0(arm, rec_path):
    rec = json.loads(Path(rec_path).read_text(encoding="utf-8"))
    out = {}
    for k, v in rec["outputs_sha256"].items():
        p = arm.parts_dir.parent / k if k.startswith("parts/") else arm.parts_dir.parent / k
        out[k] = p.is_file() and L.sha(p) == v
    ins = rec["inputs_sha256"]
    files = {"build_arm.py": HERE / "build_arm.py", "layout.py": HERE / "layout.py", "j5geom.py(MP10)": Path(arm.P["_paths"]["wrist_code"]) / "j5geom.py",
             "parameters.json(MP10)": Path(arm.P["_paths"]["wrist_code"]) / "parameters.json", "parameters.json(MP16)": Path(arm.P["_paths"]["drive_params"]),
             "print-fits.json": Path(arm.P["_paths"]["fits_ledger"]), "motor-mks42d.json": Path(arm.P["_paths"]["motor_ledger"]),
             "cycloid.json(MP6)": Path(arm.P["_paths"]["reducer_json"]), "v1 parameters.json": Path(arm.P["_paths"]["v1_dir"]) / "parameters.json"}
    inp = {k: (L.sha(files[k]) == ins.get(k)) for k in files}
    inp["parameters.json"] = L.sha(arm.params_path) == ins.get("parameters.json")
    return {"ok": all(out.values()) and all(inp.values()) and len(out) == len(L.NEW_PARTS) + len(L.COUPONS) + 1, "outputs": out, "inputs": inp}


def c1(arm):
    rows = {}
    for n in list(L.NEW_PARTS) + list(L.COUPONS):
        m = arm.local[n]
        pieces = len(m.split(only_watertight=False))
        mv = to_man(m).volume() if m.is_watertight else 0.0
        rows[n] = {"watertight": bool(m.is_watertight), "pieces": pieces, "mesh_volume": float(m.volume), "manifold_volume": float(mv),
                   "ok": bool(m.is_watertight and (pieces == 1 or n in MULTI_PIECE) and m.volume > 0 and abs(mv - m.volume) <= 1e-4 * m.volume + 1e-3)}
    return {"ok": all(r["ok"] for r in rows.values()), "parts": rows}


# ---------------- C2 ----------------
def c2(arm):
    P = arm.P
    kin = json.loads((Path(P["_paths"]["v1_dir"]) / "kinematics.json").read_text(encoding="utf-8"))
    qd = [float(j["pose_deg"]) for j in kin["joints"]]
    Ts = L.link_transforms(P, qd)
    err_o, err_a = 0.0, 0.0
    axis_idx = {"x": 0, "y": 1, "z": 2}
    ko = P.get("kinematics_override", {})
    ext = float(ko.get("forearm_mm", P["_v1"]["forearm_mm"])) - float(P["_v1"]["forearm_mm"])        # 아래팔 늘림(사용자 「165 로 늘림 (권장)」)
    fwd = Ts[3][:3, 0]                                                          # 표시 자세 링크 3 의 x(아래팔 방향)
    for k, j in enumerate(kin["joints"]):
        o = Ts[k + 1][:3, 3]
        expect = np.array(j["origin_mm"]) + (fwd * ext if k >= 3 else 0.0)      # J4 이후는 v1 + 늘림만큼 아래팔 방향으로
        err_o = max(err_o, float(np.linalg.norm(o - expect)))
        a = Ts[k + 1][:3, axis_idx[L.AXES[j["name"]]]]
        err_a = max(err_a, float(np.linalg.norm(a - np.array(j["axis_world"]))))
    o0 = L.joint_origins_q0(P)
    axes0 = {"J1": [0, 0, 1], "J2": [0, 1, 0], "J3": [0, 1, 0], "J4": [1, 0, 0], "J5": [0, 1, 0], "J6": [1, 0, 0]}
    mods = {"J1": "J1", "J2": "M2", "J3": "M3", "J4": "C4", "J5": "J5M", "J6": "C6"}
    mod = {}
    for j, fr in mods.items():
        F = arm.Fr[fr]
        z = F[:3, 2]
        par = float(np.linalg.norm(np.cross(z, axes0[j])))
        d = float(np.linalg.norm(np.cross(o0[j] - F[:3, 3], np.array(axes0[j], dtype=float))))
        mod[j] = {"axis_parallel_err": par, "axis_offset_mm": d, "ok": par < 1e-9 and d < 1e-9}
    mp9 = json.loads(Path(P["_paths"]["gripper_mount"]).read_text(encoding="utf-8"))["mount"]["g_to_link6_local"]
    G_l6 = np.linalg.inv(arm.Ts0[6]) @ arm.Fr["G"]
    g_err = float(np.abs(G_l6 - np.array(mp9)).max())
    return {"ok": err_o < 1e-6 and err_a < 1e-9 and all(v["ok"] for v in mod.values()) and g_err < 1e-9, "fk_origin_err_mm": err_o, "fk_axis_err": err_a,
            "display_pose_deg": qd, "forearm_extension_mm": ext, "module_axes": mod, "gripper_vs_mp9_max_err": g_err,
            "note": "J1 - J3 origins = v1 kinematics.json exactly; J4 - J6 = v1 + forearm extension along the display-pose forearm direction"}


# ---------------- C3 나사 ----------------
def intervals(mesh, origin, d):
    loc, _ri, _ti = mesh.ray.intersects_location([origin], [d], multiple_hits=True)
    if len(loc) == 0:
        return []
    t = sorted(set(round(float(np.dot(p - origin, d)), 5) for p in loc))
    return [(t[i], t[i + 1]) for i in range(0, len(t) - 1, 2)]


def c3(arm, screws, P):
    smin, tmin, ins_len = P["screws"]["min_engagement"], P["screws"]["tip_to_floor_min"], P["screws"]["insert_length"]
    meshes = {}
    rows = []
    ok = True
    for s in screws:
        names = s["clamped"] + s["target"].split("|")
        for n in names:
            if n not in meshes:
                meshes[n] = arm.placed(n, [0.0] * 6)
        a = np.array(s["axis_world"], dtype=float)
        a /= np.linalg.norm(a)
        u = np.cross(a, [0.0, 0.0, 1.0]) if abs(a[2]) < 0.9 else np.cross(a, [1.0, 0.0, 0.0])
        u /= np.linalg.norm(u)
        v = np.cross(a, u)
        for hi, h in enumerate(s["heads_world"]):
            h = np.array(h, dtype=float)
            o = h - a * 1.0
            axis_hits = {n: [(t0 - 1.0, t1 - 1.0) for t0, t1 in intervals(meshes[n], o, a)] for n in names}
            blocked = [n for n in s["clamped"] if any(t1 > 0.01 and t0 < s["length"] for t0, t1 in axis_hits[n])]
            tg = [n for n in s["target"].split("|") if axis_hits[n]] or [s["target"].split("|")[0]]
            tgt = tg[0]
            floor = min((t0 for t0, _t1 in axis_hits[tgt] if t0 > -0.5), default=None)
            seats, faces, gaps = [], [], []
            for ang in range(4):
                w = math.cos(ang * math.pi / 2) * u + math.sin(ang * math.pi / 2) * v
                oo = o + w * s.get("probe_r", 2.6)
                iv = {n: [(t0 - 1.0, t1 - 1.0) for t0, t1 in intervals(meshes[n], oo, a)] for n in names}
                first = iv[s["clamped"][0]]
                seats.append(first[0][0] if first else None)
                stack = []
                for n in s["clamped"]:
                    stack += [(t0, t1, n) for t0, t1 in iv[n] if t1 > -0.5 and t0 < s["length"] + 5]
                stack.sort()
                tf = min((t0 for t0, _t1 in iv[tgt] if t0 > -0.5), default=None)
                faces.append(tf)
                prev = None
                for t0, t1, n in stack + ([(tf, tf + 1, tgt)] if tf is not None else []):
                    if prev is not None:
                        gaps.append((prev[2], n, round(t0 - prev[1], 4)))
                    prev = (t0, t1, n)
            seat = max(abs(x) for x in seats if x is not None) if all(x is not None for x in seats) else None
            face = max(f for f in faces if f is not None) if all(f is not None for f in faces) else None
            leff = s["length"] - s.get("washer_t", 0.0)                          # 와셔 몫만큼 짧게(검토 R1-3)
            eng = leff - face if face is not None else None
            tip = floor - leff if floor is not None else None
            depth = floor - face if floor is not None and face is not None else None            # 인서트 구멍 깊이(면 → 바닥)
            bad_gaps = [g for g in gaps if g[2] > DESIGNED_GAPS.get((g[0], g[1]), 0.0) + 0.05 or g[2] < -0.05]
            r_ok = (seat is not None and seat <= 0.05 and not blocked and eng is not None and eng >= smin - 1e-6 and tip is not None and tip >= tmin - 1e-6
                    and depth is not None and depth >= ins_len + 0.25 - 1e-6 and not bad_gaps)
            ok &= bool(r_ok)
            rows.append({"screw": s["name"], "i": hi, "length": s["length"], "target": tgt, "seat_err": seat, "blocked_by": blocked, "engagement": eng,
                         "tip_to_floor": tip, "insert_hole_depth": depth, "stack_gaps": sorted(set(gaps)), "bad_gaps": bad_gaps, "ok": bool(r_ok)})
    summary = {}
    for r in rows:
        k = r["screw"]
        sm = summary.setdefault(k, {"n": 0, "min_engagement": 1e9, "min_tip_to_floor": 1e9, "min_insert_hole_depth": 1e9, "ok": True})
        sm["n"] += 1
        sm["min_engagement"] = min(sm["min_engagement"], r["engagement"] if r["engagement"] is not None else -1e9)
        sm["min_tip_to_floor"] = min(sm["min_tip_to_floor"], r["tip_to_floor"] if r["tip_to_floor"] is not None else -1e9)
        sm["min_insert_hole_depth"] = min(sm["min_insert_hole_depth"], r["insert_hole_depth"] if r["insert_hole_depth"] is not None else -1e9)
        sm["ok"] &= r["ok"]
    return {"ok": bool(ok), "summary": summary, "rows": rows}


# ---------------- C4 정지 자세 ----------------
def overlaps(arm, q, names=None):
    names = names or arm.collide_names()
    pl = {n: arm.placed(n, q) for n in names}
    mm = {n: to_man(m) for n, m in pl.items()}
    hits, fit = [], []
    for a, b in itertools.combinations(names, 2):
        ga, gb = group(a), group(b)
        if ga is not None and ga == gb:
            continue
        if a.startswith("REF.") and b.startswith("REF.") and arm.info(a)["link"] == arm.info(b)["link"]:
            continue                                                           # 같은 링크 구매품 어림끼리만 뺌(다른 링크끼리는 봄 · 검토 R1-16)
        lo = np.maximum(pl[a].bounds[0], pl[b].bounds[0])
        hi = np.minimum(pl[a].bounds[1], pl[b].bounds[1])
        if np.any(lo > hi + 0.01):
            continue
        vol = (mm[a] ^ mm[b]).volume()
        fp = FIT_PAIRS.get((a, b)) or FIT_PAIRS.get((b, a))
        if fp:
            fit.append({"pair": [a, b], "overlap_mm3": vol, "expected": [fp[0], fp[1]], "ok": fp[0] <= vol <= fp[1]})
            continue
        if vol > OVERLAP_TOL:
            hits.append({"pair": [a, b], "links": [arm.info(a)["link"], arm.info(b)["link"]], "overlap_mm3": vol})
    return hits, fit


def c4(arm, P):
    poses = {"zero": [0.0] * 6, "display": P["poses"]["display_deg"], "ready": P["poses"]["ready_deg"]}
    res = {}
    for k, q in poses.items():
        hits, fit = overlaps(arm, q)
        res[k] = {"q": q, "hits": sorted(hits, key=lambda h: -h["overlap_mm3"]), "fit_pairs": fit,
                  "ok": not hits and all(f["ok"] for f in fit) and len(fit) == len(FIT_PAIRS)}
    return {"ok": all(v["ok"] for v in res.values()), "poses": res, "tolerance_mm3": OVERLAP_TOL, "fit_pairs_note": FIT_PAIRS}


# ---------------- C5 관절 훑기 ----------------
class Sweep:
    def __init__(self, arm):
        self.arm = arm
        names = arm.collide_names()
        self.link_man = {}
        self.link_box = {}
        for k in range(7):
            ms = [arm.placed(n, [0.0] * 6) for n in names if arm.info(n)["link"] == k]
            u = None
            for m in ms:
                mm = to_man(m)
                u = mm if u is None else u + mm
            self.link_man[k] = u
            allm = trimesh.util.concatenate(ms)
            self.link_box[k] = allm.bounds
        self.desk_pts = {k: (trimesh.util.concatenate([arm.placed(n, [0.0] * 6) for n in names if arm.info(n)["link"] == k])).convex_hull.vertices
                         for k in range(2, 7)}

    def pose(self, q, pairs=None):
        Ts0 = self.arm.Ts0
        Tq = L.link_transforms(self.arm.P, q)
        X = {k: Tq[k] @ np.linalg.inv(Ts0[k]) for k in range(7)}
        mans = {k: self.link_man[k].transform(X[k][:3, :].tolist()) for k in range(7)}
        boxes = {}
        for k in range(7):
            b = self.link_box[k]
            corners = np.array([[x, y, z, 1.0] for x in b[:, 0] for y in b[:, 1] for z in b[:, 2]]) @ X[k].T
            boxes[k] = (corners[:, :3].min(0), corners[:, :3].max(0))
        hits = []
        for i, j in (pairs or itertools.combinations(range(7), 2)):
            lo = np.maximum(boxes[i][0], boxes[j][0])
            hi = np.minimum(boxes[i][1], boxes[j][1])
            if np.any(lo > hi):
                continue
            v = (mans[i] ^ mans[j]).volume()
            if v > OVERLAP_TOL:
                hits.append((i, j, round(v, 3)))
        zmin = min(float((self.desk_pts[k] @ X[k][:3, :3].T + X[k][:3, 3])[:, 2].min()) for k in range(2, 7))
        return hits, zmin


def c5(arm, P, fast=False):
    sw = Sweep(arm)
    disp = P["poses"]["display_deg"]
    step = P["poses"]["sweep_step_deg"]
    want = P["poses"]["wanted_ranges_deg"]
    joints = ["J1", "J2", "J3", "J4", "J5", "J6"]
    res = {}
    t0 = time.time()
    for k, j in enumerate(joints):
        pairs = [(a, b) for a in range(0, k + 1) for b in range(k + 1, 7)]
        angles = np.arange(-180.0, 180.0 + 1e-9, step)
        rows = {}
        for ang in angles:
            q = list(disp)
            q[k] = float(ang)
            hits, zmin = sw.pose(q, pairs)
            rows[float(ang)] = {"hits": hits, "zmin": zmin}
        free = [a for a, r in rows.items() if not r["hits"]]
        a0 = float(round(disp[k] / step) * step)
        lo = hi = a0
        if a0 in free:
            while lo - step in rows and not rows[lo - step]["hits"]:
                lo -= step
            while hi + step in rows and not rows[hi + step]["hits"]:
                hi += step
            full = len(free) == len(rows)
        else:
            full = False
        if a0 in free and not full:                                           # 범위 끝 다시 훑기(1° · 얇은 부품 스침 — 검토 R1-14)
            for end, sgn in ((lo, -1.0), (hi, 1.0)):
                fine = []
                for d in np.arange(-4.0, 4.0 + 1e-9, 1.0):
                    q = list(disp)
                    q[k] = float(end + d)
                    h_, _z = sw.pose(q, pairs)
                    fine.append((float(end + d), bool(h_)))
                inner = [x for x, hit in fine if (x - end) * sgn <= 0]
                if any(hit for x, hit in fine if x in inner):
                    bad = [x for x, hit in fine if hit and x in inner]
                    if sgn < 0:
                        lo = max(bad) + 1.0
                    else:
                        hi = min(bad) - 1.0
        desk_lo = min((a for a in rows if lo <= a <= hi and rows[a]["zmin"] < 0.0), default=None)
        res[j] = {"free_range_deg": [lo, hi] if a0 in free else None, "full_turn": full, "wanted_deg": want[j],
                  "covers_wanted": bool(a0 in free and (full or (lo <= want[j][0] and hi >= want[j][1]))), "refined_1deg": bool(a0 in free and not full),
                  "first_hits_outside": {"below": rows.get(lo - step, {}).get("hits"), "above": rows.get(hi + step, {}).get("hits")},
                  "desk_below_zero_within_free": desk_lo is not None, "zmin_over_free": min(r["zmin"] for a, r in rows.items() if lo <= a <= hi)}
    grid = None
    if not fast:
        gs = P["poses"]["grid_step_deg"]
        g2 = np.arange(-180.0, 90.0 + 1e-9, gs)
        g3 = np.arange(-180.0, 180.0 + 1e-9, gs)
        cells = {}
        pairs = [(a, b) for a in range(0, 3) for b in range(3, 7)] + [(a, b) for a in range(0, 2) for b in range(2, 3)]
        for a2 in g2:
            for a3 in g3:
                q = [0.0, float(a2), float(a3), 0.0, 0.0, 0.0]
                hits, zmin = sw.pose(q, pairs)
                cells[f"{a2:.0f},{a3:.0f}"] = {"free": not hits, "desk_ok": zmin >= 0.0, "hits": hits}
        grid = {"step_deg": gs, "J2": [float(g2[0]), float(g2[-1])], "J3": [float(g3[0]), float(g3[-1])],
                "free_fraction": sum(c["free"] for c in cells.values()) / len(cells), "free_and_above_desk_fraction": sum(c["free"] and c["desk_ok"] for c in cells.values()) / len(cells),
                "cells": cells}
    return {"ok": all(r["covers_wanted"] for r in res.values()), "per_joint_from_display": res, "j2_j3_grid": grid, "seconds": round(time.time() - t0, 1),
            "note": "pairs checked = links on the two sides of the swept joint (one rigid body each side · union of every collide body + purchased-part envelopes); desk = z 0 (reported, not a self-collision)"}


# ---------------- C6 지름 ----------------
def loop_radius(mesh, origin, normal, centre, near_r):
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return None
    best = None
    for ent in sec.discrete:
        pts = np.asarray(ent)
        d = np.linalg.norm(pts - np.asarray(centre), axis=1)
        r = float(d.mean())
        if d.std() < 0.05 and (best is None or abs(r - near_r) < abs(best - near_r)):
            best = r
    return best


def c6(arm, P, g, spec):
    rows = []

    def chk(name, part, frame_pt, normal, centre, expect, tol=0.03):
        m = arm.local[part]
        r = loop_radius(m, frame_pt, normal, centre, expect)
        rows.append({"what": name, "part": part, "expect_r": expect, "measured_r": r, "ok": r is not None and abs(r - expect) <= tol})
    j1z = 0.0
    chk("sleeve OD = 6818 bore + bearing_bore_extra", "BASE", [0, 0, j1z + 8.5], [0, 0, 1], [0, 0, j1z + 8.5], g["sleeve_r"])
    chk("sleeve OD (upper bearing)", "BASE", [0, 0, 34.5], [0, 0, 1], [0, 0, 34.5], g["sleeve_r"])
    sir = loop_radius(arm.local["BASE"], [0, 0, 20.0], [0, 0, 1], [0, 0, 20.0], g["sleeve_inner_r"])   # 슬리브 안 ↔ J1 MP6 최소 틈(STL) — 겹침만 보는 C4 가 못 보는 틈
    need = spec.mp6["outer_r"] + 1.5                                            # 몸통 중심 맞춤 떠돎 (5.2 − 3.0)/2 = 1.1 + 0.4(대조 sleeve_tight 가 찾은 빈틈 · 2026-11-06)
    rows.append({"what": "sleeve ID clears the J1 MP6 (>= MP6 r + 1.5 = self-centring float 1.1 + 0.4)", "part": "BASE", "expect_r": need, "measured_r": sir,
                 "ok": sir is not None and sir >= need})
    chk("turret bore = 6818 OD + bearing_seat_extra", "TURRET", [0, 0, 8.5], [0, 0, 1], [0, 0, 8.5], g["cup_bore_r"])
    chk("turret bore (upper)", "TURRET", [0, 0, 34.5], [0, 0, 1], [0, 0, 34.5], g["cup_bore_r"])
    chk("shoulder hole", "SHOULDER", [0, 47.0, 0], [0, 1, 0], [0, 47.0, 174.0], g["shoulder_hole_r"])
    chk("upper arm J3 hole", "UPPER_ARM", [0, 55.5, 0], [0, 1, 0], [165.0, 55.5, 174.0], P["j3"]["upper_arm"]["hole_r"])
    chk("J2 hub outer", "J2_HUB", [0, 50.0, 0], [0, 1, 0], [0, 50.0, 174.0], P["j2"]["hub"]["r_outer"])
    chk("forearm boss outer", "FOREARM", [0, 52.5, 0], [0, 1, 0], [165.0, 52.5, 174.0], P["j3"]["forearm"]["boss_r_outer"])
    chk("tool-flange boss = KG1 recess (MP9 rev1)", "TOOL_FLANGE", [0, 0, 54.25], [0, 0, 1], [0, 0, 54.25], P["tool_flange"]["boss_r"])
    gb = arm.local["KG1.BASE"]
    rec = loop_radius(gb, [0, 0, 0.75], [0, 0, 1], [0, 0, 0.75], P["tool_flange"]["boss_r"])
    rows.append({"what": "KG1 BASE recess radius (read)", "part": "KG1.BASE", "expect_r": P["tool_flange"]["boss_r"], "measured_r": rec,
                 "ok": rec is not None and abs(rec - P["tool_flange"]["boss_r"]) <= 0.05})
    tf = P["tool_flange"]
    for i, a in enumerate(tf["insert_angles"][:2]):
        x, y = tf["insert_r"] * math.cos(math.radians(a)), tf["insert_r"] * math.sin(math.radians(a))
        chk(f"tool-flange insert {i}", "TOOL_FLANGE", [0, 0, 50.0], [0, 0, 1], [x, y, 50.0], g["ins"] / 2)
    for i, (x, y) in enumerate(P["j1"]["turret"]["foot_insert_xy"][:1]):
        chk("turret wing insert", "TURRET", [0, 0, 46.0], [0, 0, 1], [x, y, 46.0], g["ins"] / 2)
    chk("pad insert (J4 can A)", "J4_CAN_A", [-38.0, 0, 0], [1, 0, 0], [-38.0, P["pad"]["inserts_yz"][0][0], P["pad"]["inserts_yz"][0][1]], g["ins"] / 2)
    chk("close hole (upper arm J2 screw)", "UPPER_ARM", [0, 53.0, 0], [0, 1, 0], [-22.0, 53.0, 174.0], g["m3c"] / 2)
    chk("close hole (forearm pad screw)", "FOREARM", [0, 44.0, 0], [0, 1, 0], [L.motor_face_x(P, "J4") + P["pad"]["inserts_yz"][0][1], 44.0, 174.0 - P["pad"]["inserts_yz"][0][0]], g["m3c"] / 2)
    chk("close hole (turret MP6 screw)", "TURRET", [0, 0, 45.0], [0, 0, 1], [14.0 * math.cos(math.radians(45)), 14.0 * math.sin(math.radians(45)), 45.0], g["m3c"] / 2)
    chk("fit coupon sleeve ring OD", "J1_FIT_SLEEVE", [0, 0, 3.0], [0, 0, 1], [0, 0, 3.0], g["sleeve_r"])
    chk("fit coupon bore ring ID", "J1_FIT_BORE", [0, 0, 3.0], [0, 0, 1], [0, 0, 3.0], g["cup_bore_r"])
    tz = arm.local["TURRET"]                                                    # 회전대 턱 ↔ 위 6818 바깥 고리 틈(축 기준 하나 · 검토 R1-1)
    r_ring = (P["j1"]["bearing"]["outer_ring_face_r"][0] + P["j1"]["bearing"]["outer_ring_face_r"][1]) / 2
    top = P["j1"]["bearing"]["z"][1][1]
    z_start = float(tz.bounds[0][2]) - 1.0                                      # 회전대 밑 바깥에서 출발 — 턱이 고리 면에 닿거나(틈 0) 파고들면 광선이 살 안에서
    loc, _r, _t = tz.ray.intersects_location([[r_ring, 0.0, z_start]], [[0.0, 0.0, 1.0]])   # 출발해 윗면까지 재던 빈틈(대조 turret_shoulder_touch 가 놓침 · 2026-11-06)
    zhit = min((float(p_[2]) for p_ in loc), default=None)                      # 그 반지름에서 가장 낮은 회전대 면 = 턱 밑면
    gap = (zhit - top) if zhit is not None else None
    rows.append({"what": "turret shoulder above the top 6818 outer ring (gap)", "part": "TURRET", "expect_r": None, "measured_r": gap,
                 "ok": gap is not None and gap >= 0.2})
    return {"ok": all(r["ok"] for r in rows), "rows": rows}


# ---------------- C7 · C8 ----------------
def c7(arm, pp_path):
    if not Path(pp_path).is_file():
        return {"ok": False, "why": "no printprep.json"}
    pp = json.loads(Path(pp_path).read_text(encoding="utf-8"))
    rows = {}
    for n in list(L.NEW_PARTS) + list(L.COUPONS):
        r = pp["parts"].get(n)
        rows[n] = bool(r and r["parts_sha256"] == L.sha(arm.parts_dir / f"{n}.stl") and r["verdict"] == "ready" and not r["support_needed"])
    plates = {k: bool(v["verdict"] == "ready" and v["fits_bed"] and not v["support_needed"]) for k, v in pp["plates"].items()}
    return {"ok": all(rows.values()) and all(plates.values()) and bool(plates), "parts": rows, "plates": plates}


def c8(arm, loads_path):
    if not Path(loads_path).is_file():
        return {"ok": False, "why": "no loads.json"}
    ld = json.loads(Path(loads_path).read_text(encoding="utf-8"))
    stale = [k for k, v in ld["inputs_sha256"].items() if k.startswith("parts/") and L.sha(arm.parts_dir / k.split("/", 1)[1]) != v]
    for k, f in (("parameters.json", arm.params_path), ("layout.py", HERE / "layout.py"), ("loads_arm.py", HERE / "loads_arm.py")):
        if ld["inputs_sha256"].get(k) != L.sha(f):
            stale.append(k)                                                     # 하중 입력도 지금 파일과 같아야(검토 R1-15)
    return {"ok": not stale and ld["verdict"], "stale": stale, "verdict": ld["verdict"], "margins": ld.get("margins_summary")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--parts", type=Path, default=L.MODEL / "parts")
    ap.add_argument("--record", type=Path, default=L.EV / "build" / "build-record.json")
    ap.add_argument("--printprep", type=Path, default=L.EV / "printprep.json")
    ap.add_argument("--loads", type=Path, default=L.EV / "loads" / "loads.json")
    ap.add_argument("--out", type=Path, default=L.MODEL)
    ap.add_argument("--checks", default="C0,C1,C2,C3,C4,C5,C6,C7,C8")
    ap.add_argument("--fast", action="store_true", help="skip the J2 x J3 grid map")
    a = ap.parse_args()
    sys.path.insert(0, str(HERE))
    import build_arm as B
    P, g, _spec, _lim = B.prepare(a.params, control="check")
    arm = Arm(a.params, a.parts)
    want = a.checks.split(",")
    R = {}
    t0 = time.time()
    if "C0" in want:
        R["C0"] = c0(arm, a.record)
    if "C1" in want:
        R["C1"] = c1(arm)
    if "C2" in want:
        R["C2"] = c2(arm)
    if "C3" in want:
        R["C3"] = c3(arm, B.screws(P, g), P)
    if "C4" in want:
        R["C4"] = c4(arm, P)
    if "C6" in want:
        R["C6"] = c6(arm, P, g, _spec)
    if "C7" in want:
        R["C7"] = c7(arm, a.printprep)
    if "C8" in want:
        R["C8"] = c8(arm, a.loads)
    if "C5" in want:
        R["C5"] = c5(arm, P, fast=a.fast)
    verdict = all(R[k]["ok"] for k in R) and len(R) == 9
    out = {"what": "MP17 팔 전체 v1 검사 — 커밋된 STL 로 스스로 계산", "verdict": verdict, "checks_run": sorted(R), "seconds": round(time.time() - t0, 1),
           "results": R}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "check.json").write_bytes((json.dumps(clean(out), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({k: R[k]["ok"] for k in R}), "verdict", verdict, "s", out["seconds"])


if __name__ == "__main__":
    main()
