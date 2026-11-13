# -*- coding: utf-8 -*-
"""MP15 모터 받침 출력 준비 — printforge printprep(H2D · 0.20 Standard · PLA Basic · Textured PEI · 지지대 자동 판정)로 부품마다 하나씩 슬라이스하고
두 부품(받침 = 바닥판이 판에 · 막대 = 눕혀서)을 한 판으로 G-code 없는 뱀부 스튜디오 프로젝트(models/motor-holder-v1/slicer)와 기록
(.dev/mp15-evidence/printprep.json)으로 낸다. 커밋된 STL 을 평행 이동만 해서 쓴다(받침은 그대로 · 막대는 z 를 0 으로). 보내기 · 출력은 사용자.
사용: python print_prep_holder.py --printforge <printforge 저장소> --scratch <작업 폴더>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME = "motor-holder-v1"
GAP, BED = 12.0, (350.0, 320.0)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def on_bed(m):
    m = m.copy()
    m.apply_translation([0, 0, -m.bounds[0][2]])
    return m


def printprep(pf, stl, out):
    p = subprocess.run([str(pf / ".venv" / "Scripts" / "python.exe"), "-m", "printforge.printprep", "--out", str(out), "--plate", "Textured PEI Plate",
                        "--support", "auto", str(stl)], cwd=str(pf), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    rep = out / "print_prep_report.json"
    if not rep.is_file():
        raise SystemExit(f"printprep gave no report for {stl}: rc {p.returncode} {(p.stderr or p.stdout)[-800:]}")
    return json.loads(rep.read_text(encoding="utf-8"))


def summary(rep):
    est = rep.get("estimate") or {}
    return {"verdict": rep.get("verdict"), "support_needed": (rep.get("support") or {}).get("advised_by_studio"), "mass_g": est.get("filament_g"),
            "time": est.get("print_time_s")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--printforge", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    a = ap.parse_args()
    model = ROOT / "models" / NAME
    work = a.scratch.resolve() / "printprep"
    assert ROOT.resolve() not in work.parents
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    meshes = {n: on_bed(trimesh.load(model / "parts" / f"{n}.stl", force="mesh")) for n in ("HOLDER", "BAR")}
    parts = {}
    for n, m in meshes.items():
        d = work / n
        d.mkdir()
        (d / f"{n}.stl").write_bytes(m.export(file_type="stl"))
        parts[n] = {**summary(printprep(a.printforge, d / f"{n}.stl", d / "out")), "stl_sha256": sha(model / "parts" / f"{n}.stl"),
                    "translation_z": float(-trimesh.load(model / "parts" / f"{n}.stl", force="mesh").bounds[0][2])}
        print(n, parts[n])
    # 한 판: 받침 왼쪽 · 막대 오른쪽(x 방향으로 나란히) → 판 가운데로
    h, b = meshes["HOLDER"].copy(), meshes["BAR"].copy()
    h.apply_translation([-h.bounds[0][0], -h.bounds[0][1], 0])
    b.apply_translation([h.bounds[1][0] + GAP - b.bounds[0][0], -b.bounds[0][1], 0])
    plate = trimesh.util.concatenate([h, b])
    lo, hi = plate.bounds[0][:2], plate.bounds[1][:2]
    plate.apply_translation([BED[0] / 2 - (lo[0] + hi[0]) / 2, BED[1] / 2 - (lo[1] + hi[1]) / 2, 0])
    fits = bool((plate.bounds[0][:2] >= 0).all() and plate.bounds[1][0] <= BED[0] and plate.bounds[1][1] <= BED[1])
    pstl = model / "print-plate.stl"
    pstl.write_bytes(plate.export(file_type="stl"))
    rep = printprep(a.printforge, pstl, work / "plate")
    sl = model / "slicer"
    sl.mkdir(exist_ok=True)
    for f in sl.iterdir():                                 # 폴더는 두고 파일만(드라이브 미러가 폴더를 잡고 있으면 rmdir 이 거부됨)
        f.unlink()
    proj = next((work / "plate").glob("*.3mf"))
    shutil.copyfile(proj, sl / f"{NAME}.bambu.3mf")
    shutil.copyfile(work / "plate" / "print_prep_report.json", sl / "print_prep_report.json")
    out = {"what": "MP15 모터 받침 출력 준비(뱀부 스튜디오 명령줄 · printforge printprep) — 프로젝트는 명령줄이 저장한 것이라 그대로는 명령줄 슬라이스가 −100(창에서는 됨)",
           "profiles": rep.get("profiles"), "plate": {**summary(rep), "fits_bed": fits, "plate_stl_sha256": sha(pstl),
                                                    "project_sha256": sha(sl / f"{NAME}.bambu.3mf"), "bounds": plate.bounds.tolist()},
           "parts": parts, "report_keys": sorted(rep)}
    (ROOT / ".dev" / "mp15-evidence" / "printprep.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item()) + "\n")
                                                                    .encode("utf-8"))
    print(json.dumps(out["plate"], ensure_ascii=False))


if __name__ == "__main__":
    main()
