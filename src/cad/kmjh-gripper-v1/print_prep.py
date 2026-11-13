# -*- coding: utf-8 -*-
"""MP8 — 그리퍼 KG1 출력 준비 · 질량: 부품마다 출력 방향으로 돌려 하나씩 슬라이스(printforge printprep · H2D · PLA Basic · 0.20 Standard)해 부품별 출력 질량을 얻고,
판 둘(KG1_FIT = 먼저 출력할 끼움 시험편 · KG1_MAIN = 그리퍼 부품)을 만들어 G-code 없는 뱀부 스튜디오 프로젝트로 준비한다(보내기 · 출력은 사용자).
질량 기록(mass-properties.json): 인쇄 부품 = 슬라이서 질량 · 무게중심 = 그 부품 STL 부피 중심(조립 좌표 · 닫힌 자세) · 구매품 = 목록 질량 · 자리.

사용: python print_prep.py --printforge <printforge 저장소> --scratch-root <작업 뿌리>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402

ORIENT = {"z_up": np.eye(3), "y_up": np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float),
          "y_down": np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float),
          "x_down": np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float), "x_up": np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float)}
FIT_PINIONS = ["FIT_PINION_005", "FIT_PINION_010", "FIT_PINION_015", "FIT_PINION_020"]
PART_ORIENT = {"BASE": "z_up", "JAW_A": "y_up", "JAW_B": "z_up", "PINION": "y_down", "PAD_A_FLAT": "x_down", "PAD_A_V": "x_down",
               "PAD_B_FLAT": "x_up", "PAD_B_V": "x_up", "FIT_BLOCK": "z_up", "FIT_MESH": "z_up", "FIT_RACK_A": "z_up", "FIT_RACK_B": "z_up",
               **{p: "y_down" for p in FIT_PINIONS}}
PLATES = {"fit": ["FIT_BLOCK", "FIT_MESH", "FIT_RACK_A", "FIT_RACK_B", *FIT_PINIONS],
          "main": ["BASE", "JAW_A", "JAW_B", "PINION", "PAD_A_FLAT", "PAD_B_FLAT", "PAD_A_V", "PAD_B_V"]}
ASSEMBLED = ["BASE", "JAW_A", "JAW_B", "PINION", "PAD_A_FLAT", "PAD_B_FLAT"]
GAP, ROW = 8.0, 280.0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def oriented(mesh, key):
    R = ORIENT[key]
    m = mesh.copy()
    m.apply_transform(np.vstack([np.hstack([R, np.zeros((3, 1))]), [0, 0, 0, 1]]))
    m.apply_translation(-m.bounds[0])
    return m


def printprep(pf, model, out, env):
    if out.exists():
        for dp, dn, fn in os.walk(out):
            for f in fn:
                os.chmod(Path(dp) / f, stat.S_IWRITE)
    p = subprocess.run([str(pf / ".venv" / "Scripts" / "python.exe"), "-m", "printforge.printprep", "--out", str(out), "--plate", "Textured PEI Plate",
                        "--support", "auto", str(model)], cwd=str(pf), capture_output=True, text=True, encoding="utf-8", timeout=1800, env=env)
    rep = out / "print_prep_report.json"
    if not rep.is_file():
        raise SystemExit(f"printprep gave no report for {model}: rc {p.returncode} {(p.stderr or p.stdout)[-800:]}")
    return json.loads(rep.read_text(encoding="utf-8"))


def lay_plate(meshes, bed=(350.0, 320.0)):
    items = sorted(meshes.items(), key=lambda kv: -(kv[1].extents[0] * kv[1].extents[1]))
    x = y = row_h = 0.0
    placed = []
    for name, m in items:
        m = m.copy()
        w, d = m.extents[0], m.extents[1]
        if x > 0 and x + w > ROW:
            x, y, row_h = 0.0, y + row_h + GAP, 0.0
        m.apply_translation([x, y, 0])
        placed.append((name, m))
        x += w + GAP
        row_h = max(row_h, d)
    allb = np.array([m.bounds for _n, m in placed])
    lo, hi = allb[:, 0, :2].min(axis=0), allb[:, 1, :2].max(axis=0)
    shift = np.array(bed) / 2 - (lo + hi) / 2
    for _n, m in placed:
        m.apply_translation([shift[0], shift[1], 0])
    plate = trimesh.util.concatenate([m for _n, m in placed])
    fits = bool(plate.bounds[0][0] >= 0 and plate.bounds[0][1] >= 0 and plate.bounds[1][0] <= bed[0] and plate.bounds[1][1] <= bed[1]
                and plate.extents[0] <= ROW)
    return plate, fits, {n: m.bounds.tolist() for n, m in placed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--printforge", type=Path, required=True)
    ap.add_argument("--scratch-root", type=Path, required=True)
    a = ap.parse_args()
    root = guard.find_root(HERE)
    model = guard.checked_dir(root / "models" / "kmjh-gripper-v1", root, a.scratch_root)
    ev = guard.checked_dir(root / ".dev" / "mp8-evidence" / "gripper", root, a.scratch_root)
    work = guard.checked_dir(Path(a.scratch_root) / "printprep", root, a.scratch_root)
    if work.exists():
        guard.safe_rmtree(work, root, a.scratch_root)
    work.mkdir(parents=True)
    P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    env = dict(os.environ)
    parts = {p.stem: trimesh.load(p, force="mesh") for p in sorted((model / "parts").glob("*.stl"))}
    per_part = {}
    for name, mesh in parts.items():
        om = oriented(mesh, PART_ORIENT[name])
        d = work / name
        d.mkdir()
        stl = d / f"{name}.stl"
        om.export(stl)
        rep = printprep(a.printforge, stl, d / "out", env)
        est = rep.get("estimate") or {}
        per_part[name] = {"verdict": rep.get("verdict"), "support_advised": (rep.get("support") or {}).get("advised_by_studio"),
                          "filament_g": est.get("filament_g"), "print_time_s": est.get("print_time_s"), "orient": PART_ORIENT[name],
                          "stl_sha256": sha(model / "parts" / f"{name}.stl")}
        print(name, per_part[name]["verdict"], per_part[name]["filament_g"], per_part[name]["support_advised"])
    plates = {}
    slicer = guard.checked_dir(model / "slicer", root, a.scratch_root)
    if slicer.exists():
        guard.safe_rmtree(slicer, root, a.scratch_root)
    for pname, names in PLATES.items():
        plate, fits, bounds = lay_plate({n: oriented(parts[n], PART_ORIENT[n]) for n in names})
        pstl = guard.checked_file(model / f"print-plate-{pname}.stl", root, a.scratch_root)
        plate.export(pstl)
        tmp = work / f"plate-{pname}"
        rep = printprep(a.printforge, pstl, tmp, env)
        dest = guard.checked_dir(slicer / pname, root, a.scratch_root)
        dest.mkdir(parents=True, exist_ok=True)
        for f in tmp.iterdir():
            if f.is_file():
                guard.write_bytes(dest / f.name, f.read_bytes(), root, a.scratch_root)
        est = rep.get("estimate") or {}
        plates[pname] = {"parts": names, "fits_bed_row280": fits, "bounds": bounds, "verdict": rep.get("verdict"),
                         "support_advised": (rep.get("support") or {}).get("advised_by_studio"), "filament_g": est.get("filament_g"),
                         "print_time_s": est.get("print_time_s"), "plate_sha256": sha(pstl),
                         "slicer_sha256": {f.name: sha(f) for f in sorted(dest.iterdir()) if f.is_file()}}
        print("plate", pname, plates[pname]["verdict"], est.get("filament_g"), est.get("print_time_s"), "fits", fits)
    # 질량 · 무게중심(조립 · 닫힌 자세 · 손끝 = FLAT)
    S, L, R = P["servo"], P["layout"], P["rod"]
    zc = L["z_c"]
    top = L["wall_y"][0]
    items = []
    for n in ASSEMBLED:
        c = parts[n].center_mass if parts[n].is_watertight else parts[n].centroid
        items.append({"name": n, "kind": "printed", "mass_g": per_part[n]["filament_g"], "com_mm": [round(float(v), 2) for v in c],
                      "source": "슬라이서(부품 하나 · 이 방향) · 부피 중심"})
    sx = -S["spline_from_out_end"] + S["body"][0] / 2
    purchased = [
        ("STS3215 서보", S["mass_g"], [sx, top - S["body"][2] / 2, zc], "Feetech C018 55 ± 1 g"),
        ("스플라인 혼(알루미늄)", 3.0, [0.0, top + 1.5, zc], "어림 — 6061 원판 Ø19.95 × 2.5 + 허브(재지 않음)"),
        ("탄소 관 6 × 4 × 140 (넷)", 4 * 3.14159 / 4 * (R["od"] ** 2 - R["id"] ** 2) * R["length"] / 1000 * R["density_g_cm3"], [0.0, sum(L["rod_y_a"] + L["rod_y_b"]) / 4, L["rod_z"]],
         "밀도 1.5 g/cm³(탄소 봉 판매 표기) × 부피"),
        ("나사 · 인서트(서보 M2 × 5 넷 · 피니언 M3 × 6 넷 · 손끝 M3 × 8 둥근머리 넷 · 팔 M3 × 10 넷 · 인서트 넷)", 4 * 0.15 + 4 * 0.5 + 4 * 0.6 + 4 * 0.7 + 4 * 0.3,
         [0.0, 0.0, 40.0], "어림(강 M3 × 8 약 0.6 g) — 받으면 잼"),
    ]
    for nm, g_, c, src in purchased:
        items.append({"name": nm, "kind": "purchased", "mass_g": round(g_, 2), "com_mm": [round(float(v), 2) for v in c], "source": src})
    tot = sum(i["mass_g"] for i in items)
    com = [sum(i["mass_g"] * i["com_mm"][k] for i in items) / tot for k in range(3)]
    grasp = P["pad"]["grasp_centre"]
    mp = {"what": "KG1 질량 · 무게중심(조립 · 닫힌 자세 · 손끝 FLAT) — 좌표 G(원점 = 팔 공구 플랜지에 닿는 면 가운데 · +z 다가가는 쪽)",
          "total_mass_g": round(tot, 1), "com_mm": [round(v, 2) for v in com], "grasp_centre_mm": grasp,
          "grasp_cases_z_mm": P["pad"]["grasp_cases_z"], "grasp_note": P["pad"]["grasp_note"], "items": items,
          "printed_mass_source": "printforge printprep(뱀부 스튜디오 2.8.2.61 · H2D 0.4 · 0.20 Standard · PLA Basic) — 부품 하나씩",
          "parts_sha256": {n: per_part[n]["stl_sha256"] for n in ASSEMBLED}}
    guard.write_bytes(model / "mass-properties.json", (json.dumps(mp, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), root, a.scratch_root)
    rec = {"per_part": per_part, "plates": plates}
    guard.write_bytes(ev / "print-prep.json", (json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), root, a.scratch_root)
    print(json.dumps({"total_mass_g": mp["total_mass_g"], "com_mm": mp["com_mm"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
