# -*- coding: utf-8 -*-
"""MP6 — 한 번에: 계산 → 형상(세 자세 · 구멍 탐침 · 작은 부품) → 출력 판 → 출력 준비(PrintForge printprep) → 검사 C1 ~ C8 → README.
끼움 값을 바꾼 뒤에도 이것 하나로 다시 만든다. 단계마다 표준 출력을 증거 폴더의 make-all.log 에 남긴다.

사용: python make_all.py --cli <solidcraft-cli.exe> --scratch <무거운 STL 폴더(저장소 밖)> --printforge <printforge 저장소> [--theta 0 45 90]
산출: models/cycloid-27-v1/(cycloid.json · parts · STEP · solidcraft · print-plate.stl · slicer/ · checks.json · README.md)
     .dev/cycloid-27-evidence/build/(assembly-checks.json · print-plate.json · make-all.log)
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next((q for q in HERE.parents if (q / "models" / "armold-mks-concept-v1").exists()), HERE.parents[2])
MODEL = ROOT / "models" / "cycloid-27-v1"
EVID = ROOT / ".dev" / "cycloid-27-evidence" / "build"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--printforge", required=True, type=Path, help="printforge 저장소(printprep 를 그 가상환경 파이썬으로 돌린다)")
    ap.add_argument("--theta", type=float, nargs="+", default=[0.0, 45.0, 90.0])
    ap.add_argument("--from", dest="start", default="calc", choices=["calc", "build", "images", "images-iso", "plate", "printprep", "checks", "readme", "plansync"],
                    help="이 단계부터(앞 단계 산출은 그대로 쓴다 — 형상이 안 바뀐 판 · 출력 준비만 다시 할 때)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    MODEL.mkdir(parents=True, exist_ok=True)
    EVID.mkdir(parents=True, exist_ok=True)
    log = (EVID / "make-all.log").open("w" if a.start == "calc" else "a", encoding="utf-8")
    log.write(f"### make_all from {a.start}\n")
    py = sys.executable
    slicer = MODEL / "slicer"
    if slicer.exists() and a.start in ("calc", "build", "images", "images-iso", "plate", "printprep"):   # printprep 는 빈 폴더를 원한다 — 지우는 것은 이 단위의 산출 폴더뿐
        assert slicer.resolve().parent == MODEL.resolve()

        def writable_then_retry(func, path, _exc):
            os.chmod(path, stat.S_IWRITE)    # printprep 가 남긴 폴더에 읽기 전용 속성이 붙어 있었다(2026-10-25 · WinError 5)
            func(path)

        shutil.rmtree(slicer, onexc=writable_then_retry)
    steps = [
        ("calc", [py, str(HERE / "cycloid.py"), "--out", str(MODEL / "cycloid.json")], ROOT),
        ("build", [py, str(HERE / "build_cycloid.py"), "--cli", str(a.cli), "--out", str(MODEL), "--evidence", str(EVID), "--scratch", str(a.scratch),
                   "--theta", *[str(t) for t in a.theta]], ROOT),
        ("images", [str(a.cli), "snapshot", "--in", str(MODEL / "cycloid-27-theta000.solidcraft"), "--out", str(MODEL / "section.png"), "--view", "front",
                    "--width", "1600", "--height", "1000", "--no-axes", "--section", "XZ,flip", "--body", "REF_MOTOR:opacity=0.25"], ROOT),
        ("images-iso", [str(a.cli), "snapshot", "--in", str(MODEL / "cycloid-27-theta000.solidcraft"), "--out", str(MODEL / "iso.png"), "--view", "iso",
                        "--width", "1400", "--height", "1100", "--no-axes"], ROOT),
        ("plate", [py, str(HERE / "print_plate.py"), "--parts", str(MODEL / "parts"), "--out", str(MODEL / "print-plate.stl"), "--report",
                   str(EVID / "print-plate.json")], ROOT),
        ("printprep", [py, "-m", "printforge.printprep", "--out", str(slicer), "--plate", "Textured PEI Plate", "--support", "auto",
                       str(MODEL / "print-plate.stl")], a.printforge),
        ("checks", [py, str(HERE / "check_cycloid.py"), "--calc", str(MODEL / "cycloid.json"), "--assembly", str(EVID / "assembly-checks.json"),
                    "--plate", str(EVID / "print-plate.json"), "--prep", str(slicer / "print_prep_report.json"), "--out", str(MODEL / "checks.json")], ROOT),
        ("readme", [py, str(HERE / "fill_readme.py"), "--template", str(HERE / "README_TEMPLATE.md"), "--plate", str(EVID / "print-plate.json"),
                    "--assembly", str(EVID / "assembly-checks.json"), "--prep", str(slicer / "print_prep_report.json"), "--calc", str(MODEL / "cycloid.json"),
                    "--out", str(MODEL / "README.md")], ROOT),
        ("plansync", [py, str(HERE / "check_plan_sync.py"), "--calc", str(MODEL / "cycloid.json"), "--out", str(EVID / "plan-sync.json")], ROOT),
    ]
    rc_all = 0
    names = [s[0] for s in steps]
    steps = steps[names.index(a.start):]
    for name, argv, cwd in steps:
        p = subprocess.run(argv, cwd=str(cwd), capture_output=True, encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8", "SOLIDCRAFT_GPU": "cpu"})
        log.write(f"== {name} rc {p.returncode}\n{p.stdout}\n{p.stderr[-3000:] if p.returncode else ''}\n")
        log.flush()
        print(f"STEP {name} rc {p.returncode}")
        if name in ("checks", "plansync"):
            print(p.stdout)
        if p.returncode:
            rc_all = p.returncode
            if name not in ("checks", "plansync"):
                print(p.stderr[-2000:])
                break
    log.close()
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
