# -*- coding: utf-8 -*-
"""MP13 핀 구멍 시편 출력 준비 — printforge printprep(H2D · 0.20 Standard · PLA Basic · Textured PEI · 지지대 자동 판정)로 STL 을 그대로(바닥 z 0 · 구멍 축 z)
슬라이스해 G-code 없는 뱀부 스튜디오 프로젝트(models/pin-coupon-v1/slicer)와 기록(.dev/mp13-evidence/printprep.json)을 낸다. 보내기 · 출력은 사용자.
사용: python print_prep_coupon.py --printforge <printforge 저장소> --scratch <작업 폴더>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME, BODY = "pin-coupon-v1", "PIN_COUPON"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--printforge", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    a = ap.parse_args()
    model = ROOT / "models" / NAME
    stl = model / "parts" / f"{BODY}.stl"
    work = a.scratch.resolve() / "printprep"
    assert ROOT.resolve() not in work.parents
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    src = work / f"{BODY}.stl"
    shutil.copyfile(stl, src)
    p = subprocess.run([str(a.printforge / ".venv" / "Scripts" / "python.exe"), "-m", "printforge.printprep", "--out", str(work / "out"),
                        "--plate", "Textured PEI Plate", "--support", "auto", str(src)], cwd=str(a.printforge), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    rep_p = work / "out" / "print_prep_report.json"
    if not rep_p.is_file():
        raise SystemExit(f"printprep gave no report: rc {p.returncode} {(p.stderr or p.stdout)[-800:]}")
    rep = json.loads(rep_p.read_text(encoding="utf-8"))
    sl = model / "slicer"
    sl.mkdir(exist_ok=True)
    proj = next((work / "out").glob("*.3mf"))
    shutil.copyfile(proj, sl / f"{NAME}.bambu.3mf")
    shutil.copyfile(rep_p, sl / "print_prep_report.json")
    est = rep.get("estimate") or {}
    part = {"verdict": rep.get("verdict"), "support_needed": (rep.get("support") or {}).get("advised_by_studio"),
            "mass_g": est.get("filament_g"), "time": est.get("print_time_s"), "stl_sha256": sha(stl),
            "project_sha256": sha(sl / f"{NAME}.bambu.3mf")}
    out = {"what": "MP13 핀 구멍 시편 출력 준비(뱀부 스튜디오 명령줄 · printforge printprep) — 프로젝트는 명령줄이 저장한 것이라 그대로는 명령줄 슬라이스가 −100(창에서는 됨)",
           "profiles": rep.get("profiles"), "plate": rep.get("plate"), "part": part, "report_keys": sorted(rep)}
    (ROOT / ".dev" / "mp13-evidence" / "printprep.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps(part, ensure_ascii=False))


if __name__ == "__main__":
    main()
