# -*- coding: utf-8 -*-
"""MP17 팔 전체 v1 출력 준비 — printforge printprep(H2D · 0.20 Standard · PLA Basic · Textured PEI · 지지대 자동 판정)로 새 부품마다 슬라이스하고,
팔 한 대 몫을 판 다섯(STL + G-code 없는 뱀부 스튜디오 프로젝트)으로 낸다. 커밋된 STL 을 출력 방향으로 돌리고 옮겨서 쓴다.
기존 모듈(MP16 · MP6 · MP10 · KG1)의 판은 그 단위 폴더 것을 쓴다(README). 보내기 · 출력은 사용자.
사용: python print_prep_arm.py --printforge <printforge 저장소> --scratch <작업 폴더>
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

import trimesh

import layout as L

HERE = Path(__file__).resolve().parent
ROOT = L.ROOT
GAP = 8.0
AREA = (30.0, 320.0, 8.0, 312.0)                    # H2D 두 노즐이 다 닿는 x 30 ~ 320 · y 8 ~ 312(MP16 교훈)
ORIENT = {   # 부품: 출력 방향(지역 좌표 → 판) — z_up = 그대로 · z_down = x 축 180° · y_down = +y 면을 판에 · y_up = −y 면을 판에
    "FLOOR": "z_up", "BASE": "z_up", "BASE_RING": "z_up", "J1_CAN_A": "z_up", "J1_CAN_B": "z_up", "TURRET": "z_down", "J1_SPACER": "z_up",
    "SHOULDER": "y_down", "MOTOR_COVER_J2": "z_up", "J2_HUB": "y_down", "UPPER_ARM": "y_up", "J2_CAP": "y_up", "MOTOR_COVER_J3": "z_up",
    "FOREARM": "y_up", "J3_CAP": "y_down",
    "J4_CAN_A": "z_up", "J4_CAN_B": "z_up", "J4_REAR_COVER": "z_down", "LINK5": "y_down",
    "J6_CAN_A": "z_up", "J6_CAN_B": "z_up", "J6_REAR_COVER": "z_down", "TOOL_FLANGE": "z_up", "J1_FIT_SLEEVE": "z_up", "J1_FIT_BORE": "z_down"}
ORIENT_NOTE = {"z_up": "그대로(밑면이 판)", "z_down": "뒤집어(윗면이 판)", "y_down": "+y 면이 판", "y_up": "−y 면이 판"}
PLATES = {"A_shoulder_upper_arm": {"SHOULDER": 1, "UPPER_ARM": 1},
          "B_turret_base": {"TURRET": 1, "BASE": 1},
          "C_floor_forearm": {"FLOOR": 1, "FOREARM": 1},
          "D_cans": {"J1_CAN_A": 1, "J1_CAN_B": 1, "J4_CAN_A": 1, "J4_CAN_B": 1, "J6_CAN_A": 1, "J6_CAN_B": 1},
          "E_link5_rings": {"LINK5": 1, "J1_SPACER": 1, "J2_HUB": 1, "BASE_RING": 1},
          "F_covers": {"J2_CAP": 1, "J3_CAP": 1, "J4_REAR_COVER": 1, "J6_REAR_COVER": 1, "TOOL_FLANGE": 1, "MOTOR_COVER_J2": 1, "MOTOR_COVER_J3": 1},
          "G_fit_coupons_first": {"J1_FIT_SLEEVE": 1, "J1_FIT_BORE": 1}}
COLOR_NOTE = {"navy": ["J2_HUB", "J2_CAP", "J3_CAP", "J4_REAR_COVER", "J6_REAR_COVER", "UA_LOGO (UPPER_ARM 맨 위 0.6 mm)"],
              "mint": ["BASE_RING", "TOOL_FLANGE", "J2_CAP_MARK · J3_CAP_MARK (덮개 맨 위 0.6 mm)"], "gray": ["FLOOR", "J1_SPACER"],
              "white": "그 밖 전부", "note": "AMS 로 물체마다 색 · 돋움 표시는 높이 구간 수정자(맨 위 0.6 mm)"}


def oriented(name, path, mark_path=None):
    m = trimesh.load(path, force="mesh")
    if mark_path is not None:                                                  # 돋움 표시를 밑 부품과 한 물체로(두 껍질)
        m = trimesh.util.concatenate([m, trimesh.load(mark_path, force="mesh")])
    o = ORIENT[name]
    if o == "z_down":
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    elif o == "y_down":
        m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))
    elif o == "y_up":
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    m.apply_translation(-m.bounds[0])
    return m


def printprep(pf, stl, out):
    p = subprocess.run([str(pf / ".venv" / "Scripts" / "python.exe"), "-m", "printforge.printprep", "--out", str(out), "--plate", "Textured PEI Plate",
                        "--support", "auto", str(stl)], cwd=str(pf), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    rep = out / "print_prep_report.json"
    if not rep.is_file():
        raise SystemExit(f"printprep gave no report for {stl}: rc {p.returncode} {(p.stderr or p.stdout)[-800:]}")
    return json.loads(rep.read_text(encoding="utf-8"))


def summary(rep):
    est = rep.get("estimate") or {}
    return {"verdict": rep.get("verdict"), "support_needed": (rep.get("support") or {}).get("advised_by_studio"), "mass_g": est.get("filament_g"),
            "time_s": est.get("print_time_s")}


def pack(items):
    """선반 채우기(MP16 과 같은 방식): 큰 것부터 · 한 줄에 x 로 · 0° / 90° 중 줄에 맞는 쪽 · 넘치면 다음 줄."""
    R90 = trimesh.transformations.rotation_matrix(math.pi / 2, [0, 0, 1])
    items = sorted(items, key=lambda t: -max(t[1].extents[:2]))
    x = y = row = 0.0
    out = []
    lim = AREA[1] - AREA[0]
    for n, m in items:
        cands = [m.copy(), m.copy()]
        cands[1].apply_transform(R90)
        fit_row = [c for c in cands if x + c.extents[0] <= lim and (row == 0 or c.extents[1] <= row)]
        if fit_row:
            mm = min(fit_row, key=lambda c: c.extents[0])
        else:
            if x > 0:
                x, y, row = 0.0, y + row + GAP, 0.0
            ok = [c for c in cands if c.extents[0] <= lim]
            mm = min(ok or cands, key=lambda c: c.extents[1])
        mm.apply_translation([x - mm.bounds[0][0], y - mm.bounds[0][1], -mm.bounds[0][2]])
        out.append((n, mm))
        x += mm.extents[0] + GAP
        row = max(row, mm.extents[1])
    allm = trimesh.util.concatenate([m for _n, m in out])
    lo, hi = allm.bounds[0][:2], allm.bounds[1][:2]
    for _n, m in out:
        m.apply_translation([(AREA[0] + AREA[1]) / 2 - (lo[0] + hi[0]) / 2, (AREA[2] + AREA[3]) / 2 - (lo[1] + hi[1]) / 2, 0])
    allm = trimesh.util.concatenate([m for _n, m in out])
    b = allm.bounds
    fits = bool(b[0][0] >= AREA[0] - 1e-6 and b[1][0] <= AREA[1] + 1e-6 and b[0][1] >= AREA[2] - 1e-6 and b[1][1] <= AREA[3] + 1e-6)
    return out, allm, fits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--printforge", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--plates-only", action="store_true", help="only lay out the plates (no slicing) - quick fit trial")
    a = ap.parse_args()
    model = L.MODEL
    work = a.scratch.resolve() / "printprep"
    assert ROOT.resolve() not in work.parents
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with_mark = {base: mk for mk, base in L.MARKS.items()}
    printed = [n for n in L.NEW_PARTS if n not in L.MARKS] + list(L.COUPONS)
    meshes = {n: oriented(n, model / "parts" / f"{n}.stl", model / "parts" / f"{with_mark[n]}.stl" if n in with_mark else None) for n in printed}
    assert sorted(ORIENT) == sorted(printed) and sorted(n for v in PLATES.values() for n in v) == sorted(printed)
    if a.plates_only:
        for pn, want in PLATES.items():
            _placed, allm, fits = pack([(f"{n}#{k + 1}", meshes[n]) for n, c in want.items() for k in range(c)])
            print(pn, fits, [round(v, 1) for v in allm.extents])
        return
    parts = {}
    for n, m in meshes.items():
        d = work / n
        d.mkdir()
        (d / f"{n}.stl").write_bytes(m.export(file_type="stl"))
        parts[n] = {**summary(printprep(a.printforge, d / f"{n}.stl", d / "out")), "parts_sha256": L.sha(model / "parts" / f"{n}.stl"),
                    "orient": ORIENT[n], "extents": [round(v, 2) for v in m.extents]}
        if n in with_mark:
            parts[n]["with_mark"] = with_mark[n]
            parts[with_mark[n]] = {"printed_with": n, "parts_sha256": L.sha(model / "parts" / f"{with_mark[n]}.stl"), "verdict": parts[n]["verdict"],
                                   "support_needed": parts[n]["support_needed"], "mass_g": 0.0, "time_s": 0.0, "orient": ORIENT[n],
                                   "mass_note": "inside the base part's slicer mass"}
        print(n, parts[n], flush=True)
    sl = model / "slicer"
    sl.mkdir(exist_ok=True)
    for f in sl.iterdir():
        if f.is_file():
            f.unlink()
    plates = {}
    for pn, want in PLATES.items():
        items = [(f"{n}#{k + 1}", meshes[n]) for n, c in want.items() for k in range(c)]
        _placed, allm, fits = pack(items)
        pstl = model / f"print-plate-{pn}.stl"
        pstl.write_bytes(allm.export(file_type="stl"))
        rep = printprep(a.printforge, pstl, work / f"plate-{pn}")
        proj = next((work / f"plate-{pn}").glob("*.3mf"))
        shutil.copyfile(proj, sl / f"{L.NAME}-{pn}.bambu.3mf")
        shutil.copyfile(work / f"plate-{pn}" / "print_prep_report.json", sl / f"print_prep_report-{pn}.json")
        plates[pn] = {**summary(rep), "fits_bed": fits, "items": want, "plate_stl_sha256": L.sha(pstl), "project_sha256": L.sha(sl / f"{L.NAME}-{pn}.bambu.3mf"),
                      "bounds": allm.bounds.tolist(), "profiles": rep.get("profiles")}
        print(pn, plates[pn]["verdict"], plates[pn]["support_needed"], plates[pn]["mass_g"], plates[pn]["time_s"], fits, flush=True)
    ok = all(p["verdict"] == "ready" and not p["support_needed"] for p in parts.values()) and all(p["fits_bed"] and p["verdict"] == "ready" and not p["support_needed"]
                                                                                              for p in plates.values())
    out = {"what": "MP17 팔 전체 새 부품 출력 준비(뱀부 스튜디오 명령줄 · printforge printprep) — 한 색 · 시스템 기본값. 프로젝트는 명령줄이 저장한 것이라 그대로는 "
                   "명령줄 슬라이스가 −100(창에서는 됨) · 색 · 희생 레이어는 보낼 때 판 도구로", "ok": ok, "orient_note": ORIENT_NOTE, "color_note": COLOR_NOTE,
           "parts": parts, "plates": plates}
    L.EV.mkdir(parents=True, exist_ok=True)
    (L.EV / "printprep.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item()) + "\n").encode("utf-8"))
    print("ok", ok)


if __name__ == "__main__":
    main()
