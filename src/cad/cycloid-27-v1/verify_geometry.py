# -*- coding: utf-8 -*-
"""MP6 합격 검사의 형상 계산(L4 R3 뒤 재작성 — 계획 029 「검사 장치 재작성」) — 커밋된 부품 STL(입력 0° 자리)만으로 스스로 계산한다.

- `assembly()`: 입력 0 · 45 · 90° 에서 부품을 계약대로 강체 이동(원판 = disc_pose · 편심 축 · 와셔 = +θ · 캐리어 · 출력 플랜지 = −θ/27 · 하우징 고정)하고
  **부품 10 개의 모든 쌍 · 고정 핀 28 · 출력 핀 6 · 기준 입체(베어링 고리 공간 넷 · 모터 D 축 · 파일럿 · 몸체 · 나사 머리 넷) × 모든 부품**의 교차 부피를 낸다.
  쌍 목록은 여기서 만든다(저장된 요약을 읽지 않는다).
  **베어링 고리 끝면 계약**(L4-N1 F2): 고리 끝면 바로 옆 얇은 판에 그 고리와 다른 속도의 부품이 있으면 실패 · 설계가 받치게 한 면(허브 · 간격 고리 · 와셔 ·
  캐리어 턱 · 플랜지 · 덮개 턱 · 누름 고리)에는 그 부품이 꼭 있는 고리 띠에서 닿아야 한다.
- `features()`: 형상 생성기가 선언한 구멍(구매 부품과 맞닿는 면은 회전 윤곽으로 생긴 것까지 모두 선언) · 베어링이 끼는 축을 입체 포함 관계로 — 구멍 = 줄인 기둥
  안 재료 없음 · 넓힌 껍질은 재료로 가득 · 막힌 끝 너머 재료 · **구매 부품이 들어오는 길**(구멍마다 들어오는 쪽으로 그 부품의 실제 끝 너머까지 — L4-N2 F1)
  비었음 · 축 = 안쪽 껍질 가득 · **베어링이 들어오는 길 전체**(축 반지름 ~ 베어링 바깥지름, 자리에서 위로 부품 끝 너머까지 — L4-N1 F1) 비었음.

기준 입체는 맞닿는 면에서 FIT_GAP_MM 물린다(STL 다각형 오차 최대 0.0232 · 2026-10-25 실측 127 구멍). 그래서 반지름 FIT_GAP_MM 이하의 어긋남은 못 가린다.
"""
from __future__ import annotations

import hashlib
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_cycloid as bd  # noqa: E402
from cycloid import disc_pose, profile_for, radii, ring_sections, stack  # noqa: E402

FIT_GAP_MM = 0.04      # 기준 입체 · 구멍 기둥 · 축 껍질을 맞닿는 면에서 물리는 거리
SHELL_MM = 0.2         # 「재료로 가득」 을 보는 껍질 두께
PATH_BEYOND_MM = 1.0   # 들어오는 길의 끝 = 그 부품 STL 의 실제 위 · 아래 끝 너머 이만큼(고정 길이를 쓰지 않는다 — L4-N2)
FACE_GAP_MM, FACE_SLAB_MM = 0.005, 0.02   # 베어링 고리 끝면 옆 판(끝면에서 0.005 ~ 0.02)
FACE_FORBID_MM3 = 1e-4  # 다른 속도 부품이 그 판에 들어온 부피의 상한(넓이 약 0.007 mm²)
FACE_REQUIRE_MM3 = 0.01  # 받침 면이 그 판에 들어온 부피의 하한(넓이 약 0.67 mm²)
FLOOR_MM = 0.3         # 막힌 구멍 끝 너머 재료를 보는 두께
INSET_MM = 0.05        # 구멍 · 축 검사 입체를 위아래 끝에서 들이는 거리(끝 면과 겹치지 않게)
REF_INSET_MM = 0.01    # 기준 입체(베어링 · 나사 머리 · 모터)를 맞닿는 평면에서 들이는 거리
LIMIT_MM3 = 0.01       # 교차 · 모자람의 상한
THETAS = (0.0, 45.0, 90.0)
SEG = 256


def m3d():
    import manifold3d
    return manifold3d


def vol(man):
    return float(man.volume()) if hasattr(man, "volume") else float(man.get_volume())


def stl_solid(path):
    import trimesh
    mm = trimesh.load(path, force="mesh")
    M = m3d()
    return M.Manifold(M.Mesh(vert_properties=np.asarray(mm.vertices, dtype=np.float32), tri_verts=np.asarray(mm.faces, dtype=np.uint32)))


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cyl(r, z0, z1, cx=0.0, cy=0.0):
    return m3d().Manifold.cylinder(z1 - z0, r, r, SEG).translate([cx, cy, z0])


def ring(r_in, r_out, z0, z1, cx=0.0, cy=0.0):
    return cyl(r_out, z0, z1, cx, cy) - cyl(r_in, z0 - 1, z1 + 1, cx, cy)


def section(shape, grow, z0, z1, cx, cy):
    """선언 단면(원 · D)을 grow 만큼 넓힌(음수 = 줄인) 기둥 — D 는 호 반지름 · 평면 거리를 같이 옮긴다."""
    r = shape["r"] + grow
    if shape["kind"] == "circle":
        return cyl(r, z0, z1, cx, cy)
    flat = shape["flat"] + grow
    a0 = math.acos(flat / r)
    t = np.linspace(a0, 2 * math.pi - a0, SEG)
    pts = np.column_stack([r * np.cos(t + shape["ang"]), r * np.sin(t + shape["ang"])])
    M = m3d()
    return M.CrossSection([pts]).extrude(z1 - z0).translate([cx, cy, z0])


# ---------------- 조립 ----------------
def place(solid, part, P, theta_deg):
    """입력 0° 자리의 부품을 입력 θ 자리로(계약 — 형상 생성기와 같은 함수)."""
    th = math.radians(theta_deg)
    lobes = P["ring"]["pins"] - 1
    if part in ("DISC_1", "DISC_2"):
        k = int(part[-1])
        c0, a0 = disc_pose(P, k, 0.0)
        c, a = disc_pose(P, k, th)
        return solid.translate([-c0[0], -c0[1], 0]).rotate([0, 0, math.degrees(a - a0)]).translate([c[0], c[1], 0])
    if part in ("CAM_LOWER", "CAM_UPPER", "WASHER"):
        return solid.rotate([0, 0, theta_deg])
    if part in ("CARRIER", "OUTPUT_FLANGE"):
        return solid.rotate([0, 0, -theta_deg / lobes])
    return solid


def references(P, theta_deg):
    """기준 입체: (이름, 입체, {압입 부품: 줄인 입체}) — 핀은 실제 지름(압입 부품만 구멍 − 0.04) · 베어링은 고리 공간 · 모터 D 축 · 파일럿 · 몸체 · 나사 머리."""
    z, r, B, m, f = stack(P), radii(P), P["bearings"], P["motor"], P["fits"]
    th = math.radians(theta_deg)
    g, e = FIT_GAP_MM, REF_INSET_MM
    out = []
    pin_r, press_r = P["ring"]["pin_dia"] / 2, (f["pin_press_hole_dia"] - bd.REF_PIN_SHRINK) / 2
    for i, (x, y) in enumerate(bd.ring(P["ring"]["pins"], r["ring"], math.radians(P["ring"]["pin_phase_deg"]))):
        out.append((f"RING_PIN_{i}", cyl(pin_r, *z["ring_pin"], x, y), {"HOUSING_BASE": cyl(press_r, *z["ring_pin"], x, y)}))
    op = P["output_pins"]
    phi = -th / (P["ring"]["pins"] - 1)
    for j, (u, v) in enumerate(bd.ring(op["count"], op["radius"], math.radians(op["phase_deg"]))):
        x, y = bd.rotxy(u, v, phi)
        out.append((f"OUTPUT_PIN_{j}", cyl(op["dia"] / 2, *z["output_pin"], x, y), {"CARRIER": cyl(press_r, *z["output_pin"], x, y)}))
    for k in (1, 2):
        c, _a = disc_pose(P, k, th)
        z0, z1 = z[f"disc_bearing{k}"]
        out.append((f"BEARING_6801_{k}", ring(B["disc"]["id"] / 2 + g, B["disc"]["od"] / 2 - g, z0 + e, z1 - e, c[0], c[1]), {}))
    for name, key, zz in (("BEARING_6800", "shaft_end", z["shaft_bearing"]), ("BEARING_6808", "output", z["output_bearing"])):
        out.append((name, ring(B[key]["id"] / 2 + g, B[key]["od"] / 2 - g, zz[0] + e, zz[1] - e), {}))
    shaft = {"kind": "d", "r": m["shaft_dia"] / 2, "flat": m["shaft_flat_to_axis"], "ang": th + math.pi / 2}
    out.append(("MOTOR_D_SHAFT", section(shaft, -g, e, m["shaft_length"] - e, 0.0, 0.0), {}))
    out.append(("MOTOR_PILOT", cyl(m["pilot_dia"] / 2 - g, e, m["pilot_height"] - e), {}))
    fr = m["frame"] / 2
    out.append(("MOTOR_BODY", m3d().Manifold.cube([2 * fr, 2 * fr, 40.0 - e]).translate([-fr, -fr, -40.0]), {}))
    hb = m["bolt_square"] / 2
    for i, (x, y) in enumerate([(sx * hb, sy * hb) for sx in (-1, 1) for sy in (-1, 1)]):
        out.append((f"MOTOR_SCREW_HEAD_{i}", cyl(m["screw_head_dia"] / 2, z["motor_screw_head"][0] + e, z["motor_screw_head"][1] - e, x, y), {}))
    return out


SPEED = {"CAM_LOWER": "input", "CAM_UPPER": "input", "WASHER": "input", "DISC_1": "disc1", "DISC_2": "disc2", "CARRIER": "output",
         "OUTPUT_FLANGE": "output", "HOUSING_BASE": "fixed", "HOUSING_CAP": "fixed", "RETAINER": "fixed"}
# 설계가 받치게 한 고리 끝면(cycloid.py 의 axial_location · 계획의 쌓임) — (베어링, 면, 고리, 받치는 부품)
REQUIRED_FACES = [("BEARING_6801_1", "bottom", "inner", "CAM_LOWER"), ("BEARING_6801_1", "top", "inner", "CAM_UPPER"),
                  ("BEARING_6801_2", "bottom", "inner", "CAM_UPPER"), ("BEARING_6801_2", "top", "inner", "WASHER"),
                  ("BEARING_6800", "bottom", "inner", "WASHER"), ("BEARING_6800", "top", "outer", "CARRIER"),
                  ("BEARING_6808", "bottom", "inner", "CARRIER"), ("BEARING_6808", "top", "inner", "OUTPUT_FLANGE"),
                  ("BEARING_6808", "bottom", "outer", "HOUSING_CAP"), ("BEARING_6808", "top", "outer", "RETAINER")]


def bearings_at(P, theta_deg):
    """(이름, 베어링 키, 중심, z 범위, 속 고리 속도, 바깥 고리 속도)."""
    z, th = stack(P), math.radians(theta_deg)
    return [("BEARING_6801_1", "disc", disc_pose(P, 1, th)[0], z["disc_bearing1"], "input", "disc1"),
            ("BEARING_6801_2", "disc", disc_pose(P, 2, th)[0], z["disc_bearing2"], "input", "disc2"),
            ("BEARING_6800", "shaft_end", (0.0, 0.0), z["shaft_bearing"], "input", "output"),
            ("BEARING_6808", "output", (0.0, 0.0), z["output_bearing"], "output", "fixed")]


def face_slabs(P, theta_deg):
    """베어링 고리 끝면 옆 판: (베어링, 면, 고리, 고리 속도, 넓은 띠 판(다른 고리 피하기), 꼭 있는 띠 판(받침))."""
    rs, B, g = ring_sections(P), P["bearings"], FIT_GAP_MM
    out = []
    for name, key, c, (z0, z1), sp_in, sp_out in bearings_at(P, theta_deg):
        d2, D2 = B[key]["id"] / 2, B[key]["od"] / 2
        bands = {"inner": ((d2 + g, rs[key]["inner_ring_od_max"] / 2), (d2 + g, rs[key]["inner_ring_od_min"] / 2), sp_in),
                 "outer": ((rs[key]["outer_ring_id_min"] / 2, D2 - g), (rs[key]["outer_ring_id_max"] / 2, D2 - g), sp_out)}
        for face, (za, zb) in (("bottom", (z0 - FACE_SLAB_MM, z0 - FACE_GAP_MM)), ("top", (z1 + FACE_GAP_MM, z1 + FACE_SLAB_MM))):
            for ring_name, (wide, sure, speed) in bands.items():
                out.append((name, face, ring_name, speed, ring(*wide, za, zb, c[0], c[1]), ring(*sure, za, zb, c[0], c[1])))
    return out


def assembly(P, parts_dir):
    """세 입력 각에서 부품 쌍 전부 · 기준 입체 × 부품 전부의 교차 부피. 돌려주는 rows 하나 = 한 쌍(빠짐없이)."""
    _sc, parts, _refs, _specs = bd.build(P, profile_for(P)[0], 0.0)
    base = {p: stl_solid(Path(parts_dir) / f"{p}.stl") for p in parts}
    rows = []
    for th in THETAS:
        placed = {p: place(s, p, P, th) for p, s in base.items()}
        for a, b in combinations(parts, 2):
            rows.append({"theta": th, "kind": "part-part", "a": a, "b": b, "mm3": vol(placed[a] ^ placed[b])})
        for name, solid, press in references(P, th):
            for p in parts:
                rows.append({"theta": th, "kind": "reference", "a": p, "b": name, "press_reference": p in press,
                             "mm3": vol(placed[p] ^ press.get(p, solid))})
        for name, face, ring_name, speed, wide, sure in face_slabs(P, th):
            for p in parts:
                if SPEED[p] != speed:
                    rows.append({"theta": th, "kind": "ring-face-forbidden", "a": p, "b": f"{name}:{face}:{ring_name}", "mm3": vol(placed[p] ^ wide),
                                 "limit": FACE_FORBID_MM3})
            for bname, bface, bring, bpart in REQUIRED_FACES:
                if (bname, bface, bring) == (name, face, ring_name):
                    rows.append({"theta": th, "kind": "ring-face-required", "a": bpart, "b": f"{name}:{face}:{ring_name}", "mm3": vol(placed[bpart] ^ sure),
                                 "minimum": FACE_REQUIRE_MM3})

    def ok(r_):
        if not math.isfinite(r_["mm3"]):
            return False
        if r_["kind"] == "ring-face-required":
            return r_["mm3"] >= FACE_REQUIRE_MM3
        return r_["mm3"] <= r_.get("limit", LIMIT_MM3)

    bad = [r_ for r_ in rows if not ok(r_)]
    n_ref = len(references(P, 0.0))
    n_forbid = sum(1 for _n, _f, _r, sp, _w, _s in face_slabs(P, 0.0) for p in parts if SPEED[p] != sp)
    expected = (len(list(combinations(parts, 2))) + n_ref * len(parts) + n_forbid + len(REQUIRED_FACES)) * len(THETAS)
    count = {k: sum(1 for r_ in rows if r_["kind"] == k) for k in ("part-part", "reference", "ring-face-forbidden", "ring-face-required")}
    return {"parts": parts, "thetas": list(THETAS), "pairs_part_part": count["part-part"], "pairs_reference": count["reference"],
            "ring_face_forbidden": count["ring-face-forbidden"], "ring_face_required": count["ring-face-required"], "rows": len(rows),
            "max_part_part_mm3": max(r_["mm3"] for r_ in rows if r_["kind"] == "part-part"),
            "max_reference_mm3": max(r_["mm3"] for r_ in rows if r_["kind"] == "reference"),
            "max_ring_face_forbidden_mm3": max(r_["mm3"] for r_ in rows if r_["kind"] == "ring-face-forbidden"),
            "min_ring_face_required_mm3": min(r_["mm3"] for r_ in rows if r_["kind"] == "ring-face-required"),
            "failed": [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r_.items()} for r_ in bad],
            "ok": not bad and len(rows) == expected}


# ---------------- 부품 형상(구멍 · 축) ----------------
def declared(P):
    """형상 생성기가 선언한 구멍 · 축(입력 0° 자리 + 맞춤 확인 판 · 와셔 · 게이지) · 구멍마다 들어오는 쪽."""
    sc = bd.build(P, profile_for(P)[0], 0.0)[0]
    sm = bd.small_parts(P)[0]
    return sc.holes + sm.holes, {**sc.shapes, **sm.shapes}, sc.bosses + sm.bosses, {**sc.entries, **sm.entries}


def skin_range(P, body, tag, z0, h):
    """껍질(구멍 둘레 재료)을 볼 높이 — 바닥판 고정 핀 구멍은 벽 안쪽으로 반쯤 열려 있어(핀이 반쯤 묻힘) 바닥판 두께 안만."""
    if body == "HOUSING_BASE" and tag.startswith("P"):
        return z0, min(z0 + h, stack(P)["base_top"])
    return z0, z0 + h


def features(P, parts_dir):
    holes, shapes, bosses, entries = declared(P)
    solids, rows = {}, []
    g = FIT_GAP_MM
    for body, cx, cy, z0, h, _dia, floor, tag in holes:
        if body not in solids:
            solids[body] = stl_solid(Path(parts_dir) / f"{body}.stl")
        S, sh = solids[body], shapes[(body, tag)]
        core = section(sh, -g, z0 + INSET_MM, z0 + h - INSET_MM, cx, cy)
        s0, s1 = skin_range(P, body, tag, z0, h)
        skin = section(sh, g + SHELL_MM, s0 + INSET_MM, s1 - INSET_MM, cx, cy) - section(sh, g, s0 - 1, s1 + 1, cx, cy)
        if s1 < z0 + h - INSET_MM:       # 바닥판 고정 핀 구멍의 벽 안 높이: 벽 쪽 반(핀 원 바깥)만 재료로 가득이어야(L4-N1 — 위쪽 지지 길이)
            rr = radii(P)
            upper = section(sh, g + SHELL_MM, s1 + INSET_MM, z0 + h - INSET_MM, cx, cy) - section(sh, g, s1, z0 + h + 1, cx, cy)
            skin = skin + (upper ^ ring(rr["ring"] + g, rr["outer"] + 1.0, s1, z0 + h + 1))
        row = {"body": body, "tag": tag, "kind": sh["kind"], "core_material_mm3": vol(S ^ core), "skin_missing_mm3": vol(skin) - vol(S ^ skin)}
        if floor:
            fz = (z0 - FLOOR_MM, z0) if floor == "below" else (z0 + h, z0 + h + FLOOR_MM)
            fl = section(sh, -g, fz[0], fz[1], cx, cy)
            row["floor_missing_mm3"] = vol(fl) - vol(S ^ fl)
        # 들어오는 길(L4-N2 F1): 선언 단면을 0.04 줄인 기둥을 들어오는 쪽으로 그 부품의 실제 끝 너머까지 — 재료 없음
        bb = S.bounding_box()
        row["entry"] = entries[(body, tag)]
        path_mm3 = 0.0
        if row["entry"] in ("up", "both"):
            path_mm3 += vol(S ^ section(sh, -g, z0 + h - INSET_MM, bb[5] + PATH_BEYOND_MM, cx, cy))
        if row["entry"] in ("down", "both"):
            path_mm3 += vol(S ^ section(sh, -g, bb[2] - PATH_BEYOND_MM, z0 + INSET_MM, cx, cy))
        row["entry_path_material_mm3"] = path_mm3
        row["ok"] = all(math.isfinite(v) and v <= LIMIT_MM3 for k, v in row.items() if k.endswith("_mm3"))
        rows.append(row)
    for body, cx, cy, z0, h, r, tag, bearing in bosses:
        if body not in solids:
            solids[body] = stl_solid(Path(parts_dir) / f"{body}.stl")
        S = solids[body]
        za, zb = z0 + INSET_MM, z0 + h - INSET_MM
        shell = ring(r - g - SHELL_MM, r - g, za, zb, cx, cy)
        # 베어링이 들어오는 길: 축 반지름 + 물림 ~ 베어링 바깥지름 − 물림, 자리 밑에서 위로 그 부품의 실제 위 끝 너머까지(L4-N1 F1 · L4-N2)
        path = ring(r + g, P["bearings"][bearing]["od"] / 2 - g, za, S.bounding_box()[5] + PATH_BEYOND_MM, cx, cy)
        row = {"body": body, "tag": tag, "kind": "shaft", "bearing": P["bearings"][bearing]["model"], "shell_missing_mm3": vol(shell) - vol(S ^ shell),
               "insertion_path_material_mm3": vol(S ^ path)}
        row["ok"] = all(math.isfinite(v) and v <= LIMIT_MM3 for k, v in row.items() if k.endswith("_mm3"))
        rows.append(row)
    bad = [q for q in rows if not q["ok"]]
    return {"holes": len(holes), "shafts": len(bosses), "rows": rows, "failed": [f"{q['body']}:{q['tag']}" for q in bad],
            "worst": {k: max((q[k] for q in rows if k in q), default=None) for k in
                      ("core_material_mm3", "skin_missing_mm3", "floor_missing_mm3", "entry_path_material_mm3", "shell_missing_mm3",
                       "insertion_path_material_mm3")},
            "ok": not bad and len(rows) == len(holes) + len(bosses) and len(holes) > 0}
