# -*- coding: utf-8 -*-
"""MP15 모터 받침 검사 — 커밋된 STL 로 스스로 계산(읽기만 · 쓰기 = check.json 하나 · 대조 때 controls.json).

C0 만들기 기록의 sha = 지금 STL · 입력(매개변수 · 생성기 · 모터 원장 · 감속기 산출 · J5 매개변수 · 끼움 원장) · 고장 판 아님
C1 두 몸체 닫힘 · 부피 > 0 · 한 덩어리씩
C2 U 홈: 옆 틈(한쪽) = (안쪽 폭 − 원장 frame) / 2 가 check_tolerance.side_clearance 안 · 바닥 = 축 높이 − frame / 2 · 모터 상자와 겹침 0
C3 감속기(바깥 반지름 + reducer_gap · 뒤로는 stop_gap 까지) · 덮개 나사 머리 넷(바닥판 뒤로 나온 M3 × 30 머리 + 주머니 틈)과 받침 · 막대 겹침 0
   + 뒤 멈춤: 받침 앞면이 감속기 바닥판 뒷면에서 stop_gap(모터가 뒤로 밀리면 바닥판이 받침에 닿음)
C4 바닥판 위 재료 · 막대가 모두 x ≤ 모터 커넥터 앞 끝 − connector_gap · connector_front = J5 매개변수 값(드라이버는 모델에 없음 — 커넥터 뒤라 이 한계로 같이 막힘)
C5 조임: 벽 윗면이 모터 윗면보다 clamp_gap 아래(check_tolerance.clamp_gap 안) · 막대 밑면 = 모터 윗면
C6 인서트 구멍 둘(지름 · 깊이 · 벽 안팎 재료 ≥ min_material) · 막대 구멍 둘(M3 통과 지름 · 인서트와 같은 중심)
   · 나사 물림: inserts.screws 길이마다 (막대 나사 자리 → 벽 윗면) 을 재어 인서트 물림 ≥ min_engagement · 나사 끝 ↔ 구멍 바닥 ≥ tip_to_floor_min
C7 바닥판 구멍 넷 관통 · 지름 · 구멍 가 ↔ 받침 덩어리 · 바닥판 가장자리 ≥ min_material
C8 출력 준비 기록 = 지금 STL · 두 부품 ready · 지지대 없음 · 한 판(print-plate.stl · 프로젝트 sha 같음 · ready · 지지대 없음)
대조: --controls <작업 폴더> --cli <solidcraft-cli.exe> 면 build_holder.py 로 고장 판 열둘을 만들어 표적 검사가 잡는지 보고 controls.json 을 쓴다.
사용: python check_holder.py [--model-dir D] [--out F] [--controls <작업 폴더> --cli <solidcraft-cli.exe>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME = "motor-holder-v1"
EV = ROOT / ".dev" / "mp15-evidence"
sys.path.insert(0, str(HERE))
from build_holder import CONTROLS as CONTROLS_MEANS, load  # noqa: E402  (파일 읽기 · 대조 이름만 같이 씀 — 형상 수는 여기서 따로 셈)

TARGETS = {"tight": "C2_cradle_fits_motor", "front": "C3_clear_of_reducer", "nopocket": "C3_clear_of_reducer", "far": "C3_clear_of_reducer",
           "long": "C4_clear_of_connector", "flush": "C5_bar_clamps_motor", "barup": "C5_bar_clamps_motor", "thin": "C6_inserts_and_bar_holes",
           "barhole": "C6_inserts_and_bar_holes", "nocb": "C6_inserts_and_bar_holes", "low": "C3_clear_of_reducer", "blind": "C7_base_holes"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def first_hit(m, origin, direction):
    o, d = np.array([origin], float), np.array([direction], float)
    loc = m.ray.intersects_location(o, d)[0]
    if not len(loc):
        return None
    t = (loc - o) @ d[0]
    return loc[int(np.argmin(t))].tolist()


def loops_xy(m, z):
    """z 단면의 닫힌 고리마다 (넓이 같은 원 지름, 중심 xy, 넓이) — 구멍 · 바깥 둘레 모두."""
    sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    out = []
    if sec is None:
        return out
    for loop in sec.discrete:
        q = np.asarray(loop)[:, :2]
        x0, y0, x1, y1 = q[:-1, 0], q[:-1, 1], q[1:, 0], q[1:, 1]
        cr = x0 * y1 - x1 * y0
        area = cr.sum() / 2
        if abs(area) < 1e-9:
            continue
        c = np.array([((x0 + x1) * cr).sum(), ((y0 + y1) * cr).sum()]) / (6 * area)
        out.append((2 * math.sqrt(abs(area) / math.pi), c, abs(area)))
    return out


def find_hole(loops, cx, cy, near=1.5):
    best = None
    for dia, c, area in loops:
        d = math.hypot(c[0] - cx, c[1] - cy)
        if d < near and area < 100 and (best is None or d < best[1]):
            best = (dia, d, c.tolist())
    return best


def cyl_x(r, x0, x1, y, z):
    c = trimesh.creation.cylinder(radius=r, height=x1 - x0, sections=96)
    c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    c.apply_translation([(x0 + x1) / 2, y, z])
    return c


def overlap(a, b):
    try:
        i = trimesh.boolean.intersection([a, b], engine="manifold")
        return float(i.volume) if i is not None and not i.is_empty else 0.0
    except Exception as e:                      # 빈 교차를 예외로 내는 판도 있다
        return 0.0 if "empty" in str(e).lower() else float("nan")


def check(model, D, rec, pp):
    P = D["P"]
    tol = P["check_tolerance"]
    H, fr = P["axis_height"], D["frame"]
    hold = trimesh.load(model / "parts" / "HOLDER.stl", force="mesh")
    bar = trimesh.load(model / "parts" / "BAR.stl", force="mesh")
    s, r = {}, {}
    if rec is not None:
        outs = {f"parts/{n}.stl": sha(model / "parts" / f"{n}.stl") for n in ("HOLDER", "BAR")}
        ok_out = all(rec["outputs_sha256"].get(k) == v for k, v in outs.items())
        want_in = {"parameters.json": sha(HERE / "parameters.json"), "build_holder.py": sha(HERE / "build_holder.py"), **D["sha"]}
        ok_in = rec["inputs_sha256"] == want_in
        r["C0"] = {"stl_matches": ok_out, "inputs_match": ok_in, "control": rec.get("control"),
                   "inputs_differ": sorted(k for k in set(want_in) | set(rec["inputs_sha256"]) if want_in.get(k) != rec["inputs_sha256"].get(k))}
        s["C0_build_record_matches_files"] = ok_out and ok_in and rec.get("control") is None
    parts = {n: len(m.split(only_watertight=False)) for n, m in (("HOLDER", hold), ("BAR", bar))}
    s["C1_closed_one_piece_each"] = all(bool(m.is_watertight) and float(m.volume) > 0 for m in (hold, bar)) and all(v == 1 for v in parts.values())
    r["C1"] = {"watertight": [bool(hold.is_watertight), bool(bar.is_watertight)], "volume_mm3": [float(hold.volume), float(bar.volume)], "pieces": parts}

    # C2 — U 홈 가운데 x 에서 안쪽 벽 · 바닥을 광선으로
    xm = sum(P["cradle"]["x"]) / 2
    yp, yn = first_hit(hold, [xm, 0, H], [0, 1, 0]), first_hit(hold, [xm, 0, H], [0, -1, 0])
    fl = first_hit(hold, [xm, 0, H], [0, 0, -1])
    clr = [yp[1] - fr / 2, -yn[1] - fr / 2] if yp and yn else [float("nan")] * 2
    floor_want = H - fr / 2
    Hm = fl[2] + fr / 2 if fl else H            # 모터가 실제로 앉는 축 높이(잰 바닥 + frame / 2) — 아래 C3 · C5 는 이 높이로
    motor = trimesh.creation.box(extents=[D["P"]["keepout"]["connector_front"], fr - 0.01, fr - 0.01])   # 바닥 · 막대에 닿기만 한 면은 겹침 아님
    motor.apply_translation([D["P"]["keepout"]["connector_front"] / 2, 0, Hm])
    ov_m = overlap(hold, motor) + overlap(bar, motor)
    lo, hi = tol["side_clearance"]
    s["C2_cradle_fits_motor"] = all(lo <= c <= hi for c in clr) and fl is not None and abs(fl[2] - floor_want) <= tol["length"] and ov_m < 1e-3
    r["C2"] = {"x": xm, "inner_y": [yn and yn[1], yp and yp[1]], "side_clearance": clr, "band": [lo, hi], "floor_z": fl and fl[2],
               "floor_want": floor_want, "motor_box_overlap_mm3": ov_m, "frame": fr, "frame_status": D["frame_status"]}

    # C3 — 감속기 원기둥(뒤로는 stop_gap 까지) · 덮개 나사 머리(45° 대각선 넷 · 주머니 틈) — 틈을 0.05 덜 부풀려 닿기만 한 면은 겹침으로 치지 않음
    k = P["keepout"]
    g = k["reducer_gap"] - 0.05
    red = cyl_x(D["reducer_r"] + g, -D["output_face"] - g, k["stop_gap"] - 0.05, 0.0, Hm)
    hd = k["cap_screw_head"]
    heads = []
    for i in range(D["cap_screws"]):
        a = math.pi / 4 + 2 * math.pi * i / D["cap_screws"]
        heads.append(cyl_x(hd["dia"] / 2 + hd["pocket_gap"] - 0.05, -0.5, hd["height"] + hd["pocket_depth_gap"] - 0.05, D["cap_screw_r"] * math.cos(a),
                           Hm + D["cap_screw_r"] * math.sin(a)))
    keep = trimesh.util.concatenate([red] + heads)
    ov = {"reducer": overlap(hold, red) + overlap(bar, red), "cap_screw_heads": sum(overlap(hold, h) + overlap(bar, h) for h in heads)}
    stop = first_hit(hold, [-20.0, 0.0, Hm - 25.0], [1, 0, 0])      # 바닥판 원(반지름 39) 안 · 바닥 아래 덩어리 앞면
    stop_ok = stop is not None and abs(stop[0] - k["stop_gap"]) <= tol["length"]
    s["C3_clear_of_reducer"] = all(v < 1e-3 for v in ov.values()) and stop_ok
    r["C3"] = {"overlap_mm3": ov, "stop_face_x": stop and stop[0], "stop_gap": k["stop_gap"], "stop_ok": stop_ok, "axis_z_measured": Hm,
               "reducer_r_plus_gap": D["reducer_r"] + g, "reducer_bottom_z": Hm - D["reducer_r"],
               "head_x_end_plus_gap": hd["height"] + hd["pocket_depth_gap"] - 0.05, "keepout_bounds": keep.bounds.tolist()}

    # C4 — 바닥판 위 재료 · 막대의 가장 뒤 x
    t = P["base"]["thickness"]
    up = trimesh.intersections.slice_mesh_plane(hold, plane_normal=[0, 0, 1], plane_origin=[0, 0, t + 0.01], cap=True)
    xmax = max(float(up.bounds[1][0]), float(bar.bounds[1][0]))
    lim = k["connector_front"] - k["connector_gap"]
    same = k["connector_front"] == D["connector_front_j5"]
    s["C4_clear_of_connector"] = xmax <= lim + tol["length"] and same
    r["C4"] = {"x_max_above_base": float(up.bounds[1][0]), "bar_x_max": float(bar.bounds[1][0]), "limit": lim, "connector_front": k["connector_front"],
               "connector_front_in_j5_params": D["connector_front_j5"], "same_as_j5": same}

    # C5 — 벽 윗면(인서트 안쪽 · 막대 밖 mesh) · 막대 밑면
    motor_top = Hm + fr / 2
    wy = fr / 2 + P["cradle"]["side_clearance"] + 1.0
    tops = [first_hit(hold, [P["inserts"]["x"], sgn * wy, 300], [0, 0, -1]) for sgn in (1, -1)]
    gaps = [motor_top - q[2] if q else float("nan") for q in tops]
    glo, ghi = tol["clamp_gap"]
    bar_bottom = float(bar.bounds[0][2])
    s["C5_bar_clamps_motor"] = all(glo <= v <= ghi for v in gaps) and abs(bar_bottom - motor_top) <= tol["length"]
    r["C5"] = {"motor_top": motor_top, "wall_top_z": [q and q[2] for q in tops], "clamp_gap": gaps, "band": [glo, ghi], "bar_bottom_z": bar_bottom}

    # C6 — 인서트 구멍(벽 윗면 아래 4.0 단면) · 막대 구멍(막대 두께 가운데 단면)
    wt = tops[0][2] if tops[0] else motor_top - P["cradle"]["clamp_gap"]
    ins_d, m3_d, mm = D["fits"]["insert_hole_dia"], D["fits"]["m3_clearance_dia"], P["min_material"]
    iy = fr / 2 + P["cradle"]["side_clearance"] + P["cradle"]["wall"] / 2
    L = loops_xy(hold, wt - 4.0)
    Lb = loops_xy(bar, float(bar.bounds[0][2] + bar.bounds[1][2]) / 2)
    rows, ok6 = [], True
    for sgn in (1, -1):
        h = find_hole(L, P["inserts"]["x"], sgn * iy)
        hb = find_hole(Lb, P["inserts"]["x"], sgn * iy)
        if h is None or hb is None:
            rows.append({"side": sgn, "found": [h is not None, hb is not None], "ok": False})
            ok6 = False
            continue
        cy = h[2][1]
        inner = first_hit(hold, [P["inserts"]["x"], 0, wt - 4.0], [0, sgn, 0])
        outer = first_hit(hold, [P["inserts"]["x"], sgn * 200, wt - 4.0], [0, -sgn, 0])
        mat_in = abs(cy) - h[0] / 2 - abs(inner[1])
        mat_out = abs(outer[1]) - abs(cy) - h[0] / 2
        floor_hit = first_hit(hold, [h[2][0], cy, 300], [0, 0, -1])
        depth = wt - floor_hit[2] if floor_hit else float("nan")
        same_c = math.hypot(hb[2][0] - h[2][0], hb[2][1] - h[2][1])
        # 나사 머리 자리: 막대 구멍과 자리파기 사이 고리(구멍 중심에서 x 로 2.5)를 위에서 — 자리파기가 없으면 막대 윗면
        seat = first_hit(bar, [hb[2][0] + 2.5, hb[2][1], 300], [0, 0, -1])
        d = seat[2] - wt if seat else float("nan")
        I = P["inserts"]
        screws = [{"length": L, "tip_below_wall_top": L - d, "engagement": min(L - d, I["length"]),
                   "ok": bool(min(L - d, I["length"]) >= I["min_engagement"] - tol["length"] and L - d <= depth - I["tip_to_floor_min"] + tol["length"])}
                  for L in I["screws"]]
        ok = bool(abs(h[0] - ins_d) <= tol["dia"] and abs(depth - I["depth"]) <= tol["length"] and mat_in >= mm - tol["length"]
                  and mat_out >= mm - tol["length"] and abs(hb[0] - m3_d) <= tol["dia"] and same_c <= 0.05 and all(q["ok"] for q in screws))
        ok6 &= ok
        rows.append({"side": sgn, "insert_dia": round(h[0], 4), "insert_centre": h[2], "depth": depth, "material_inner": mat_in, "material_outer": mat_out,
                     "bar_hole_dia": round(hb[0], 4), "bar_hole_to_insert_centre": same_c, "seat_z": seat and seat[2], "seat_to_wall_top": d,
                     "screws": screws, "ok": ok})
    s["C6_inserts_and_bar_holes"] = ok6
    r["C6"] = {"rows": rows, "insert_hole_dia": ins_d, "m3_clearance_dia": m3_d, "fit_status": D["fit_status"], "min_material": mm}

    # C7 — 바닥판 구멍 넷
    b = P["base"]
    Lf = loops_xy(hold, t / 2)
    rows, ok7 = [], True
    bx0, bx1 = P["cradle"]["x"]
    ho = fr / 2 + P["cradle"]["side_clearance"] + P["cradle"]["wall"]
    for x in b["holes"]["x"]:
        for sgn in (1, -1):
            y = sgn * b["holes"]["y"]
            h = find_hole(Lf, x, y)
            through = first_hit(hold, [x, y, t + 50.0], [0, 0, -1]) is None
            if h is None:
                rows.append({"at": [x, y], "found": False, "through": through, "ok": False})
                ok7 = False
                continue
            rr = h[0] / 2
            dx = max(bx0 - x, x - bx1, 0.0)
            dy = max(abs(y) - ho, 0.0)
            to_block = math.hypot(dx, dy) - rr
            to_edge = min(x - hold.bounds[0][0], hold.bounds[1][0] - x, b["y_half"] - abs(y)) - rr
            ok = bool(through and abs(h[0] - b["holes"]["dia"]) <= tol["dia"] and to_block >= mm and to_edge >= mm)
            ok7 &= ok
            rows.append({"at": [x, y], "dia": round(h[0], 4), "through": through, "to_block": to_block, "to_edge": to_edge, "ok": ok})
    s["C7_base_holes"] = ok7
    r["C7"] = {"rows": rows}

    if pp is not None:
        e = pp.get("parts", {})
        okp = all(e.get(n, {}).get("stl_sha256") == sha(model / "parts" / f"{n}.stl") and e.get(n, {}).get("verdict") == "ready"
                  and e.get(n, {}).get("support_needed") is False for n in ("HOLDER", "BAR"))
        pl = pp.get("plate", {})
        proj = model / "slicer" / f"{NAME}.bambu.3mf"
        ok_pl = (pl.get("plate_stl_sha256") == sha(model / "print-plate.stl") and proj.is_file() and pl.get("project_sha256") == sha(proj)
                 and pl.get("verdict") == "ready" and pl.get("support_needed") is False and pl.get("fits_bed") is True)
        s["C8_print_prep_ready"] = okp and ok_pl
        r["C8"] = {"parts": e, "plate": pl, "plate_ok": ok_pl}
    return {k: bool(v) for k, v in s.items()}, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, default=ROOT / "models" / NAME)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--controls", type=Path, default=None)
    ap.add_argument("--cli", type=Path, default=None)
    a = ap.parse_args()
    D = load(HERE / "parameters.json")
    if a.controls:
        rows = []
        for name, target in TARGETS.items():
            out = a.controls / name
            p = subprocess.run([sys.executable, "-B", str(HERE / "build_holder.py"), "--cli", str(a.cli), "--scratch", str(a.controls),
                                "--control", name, "--out", str(out), "--no-snapshot"], capture_output=True, text=True, encoding="utf-8", timeout=1200)
            if p.returncode:
                rows.append({"control": name, "build_rc": p.returncode, "ok": False, "err": (p.stderr or p.stdout)[-600:]})
                continue
            s, _r = check(out, D, None, None)
            others = {k: v for k, v in s.items() if k != target}
            rows.append({"control": name, "means": CONTROLS_MEANS.get(name), "target": target, "summary": s, "caught": s[target] is False,
                         "ok": s[target] is False, "C3_detail": {k: _r["C3"][k] for k in ("overlap_mm3", "stop_face_x", "stop_ok")}})
            print(name, target, "caught" if s[target] is False else "MISSED", "| others false:", [k for k, v in others.items() if v is False])
        rec = {"what": "MP15 모터 받침 양성 대조 — 고장 판을 표적 검사가 잡는지(다른 검사가 같이 걸리는 것은 기록만)", "rows": rows,
               "all_caught": all(x["ok"] for x in rows),
               "code_sha256": {n: sha(HERE / n) for n in ("parameters.json", "build_holder.py", "check_holder.py")}}
        (EV / "controls.json").write_bytes((json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        print("ALL CAUGHT" if rec["all_caught"] else "NOT ALL CAUGHT")
        return
    rec = json.loads((EV / "build" / "build-record.json").read_text(encoding="utf-8"))
    ppf = EV / "printprep.json"
    pp = json.loads(ppf.read_text(encoding="utf-8")) if ppf.is_file() else {}
    s, r = check(a.model_dir, D, rec, pp)
    out = {"what": "MP15 모터 받침 검사 — 커밋된 STL 로 스스로 계산", "summary": s, "all_true": all(s.values()), "results": r,
           "inputs_sha256": {**{f"parts/{n}.stl": sha(a.model_dir / "parts" / f"{n}.stl") for n in ("HOLDER", "BAR")},
                             "check_holder.py": sha(__file__), "parameters.json": sha(HERE / "parameters.json")}}
    (a.out or a.model_dir / "check.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n").encode("utf-8"))
    print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
