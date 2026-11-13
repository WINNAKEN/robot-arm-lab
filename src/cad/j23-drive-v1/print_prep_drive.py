# -*- coding: utf-8 -*-
"""MP16 구동 모듈 출력 준비 — printforge printprep(H2D · 0.20 Standard · PLA Basic · Textured PEI · 지지대 자동 판정)로 부품마다 슬라이스하고,
J2 · J3 두 모듈 몫을 판 셋(STL + G-code 없는 뱀부 스튜디오 프로젝트)으로 낸다. 커밋된 STL 을 출력 방향으로 돌리고(뒤집기만) 옮겨서 쓴다.
보내기 · 출력은 사용자. 두 색 · 물체별 설정(구멍 턱 희생 레이어 등)은 보낼 때 판 도구에서 넣는다(이 스크립트는 한 색 · 시스템 기본값).
사용: python print_prep_drive.py --printforge <printforge 저장소> --scratch <작업 폴더>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME = "j23-drive-v1"
GAP, BED = 8.0, (350.0, 320.0)
AREA = (30.0, 320.0, 8.0, 312.0)                               # 두 노즐이 다 닿는 x 30 ~ 320(H2D) · y 8 ~ 312 — 한 노즐 판도 이 안에
FLIP = {"STAND", "LEVER"}                                     # 윗면을 판에(시험대 = 판 윗면 · 발이 위로 · 시험 팔 = 팔 윗면) · 덮개는 바로(R1)
PARTS = ["HOUSING_BASE", "CAP", "CARRIER", "DISC_1", "CAM_LOWER", "CAM_UPPER", "WASHER_T1p2", "WASHER_T1p4", "WASHER_T1p6", "RETAINER", "OUTPUT_FLANGE",
         "GUARD", "STAND", "LEVER"]
PLATES = {"A_base_carrier": {"HOUSING_BASE": 2, "CARRIER": 2, "CAM_LOWER": 2, "CAM_UPPER": 2, "WASHER_T1p2": 2, "WASHER_T1p4": 2, "WASHER_T1p6": 2},
          "B_cap_disc": {"CAP": 2, "DISC_1": 2},
          "C_guard_disc": {"GUARD": 2, "DISC_1": 2},
          "D_stand_lever": {"STAND": 1, "LEVER": 1},
          "E_retainer_flange": {"RETAINER": 2, "OUTPUT_FLANGE": 2}}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def oriented(name, path):
    m = trimesh.load(path, force="mesh")
    if name in FLIP:
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
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
    """선반 채우기: 큰 것부터 · 한 줄에 x 로 늘어놓되 부품마다 0° / 90° 중 줄에 맞는 쪽 · 넘치면 다음 줄(긴 변을 x 로). (이름, 메시) → 놓인 메시 목록 · 판 안인가."""
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
            mm = min(ok, key=lambda c: c.extents[1])
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
    a = ap.parse_args()
    model = ROOT / "models" / NAME
    work = a.scratch.resolve() / "printprep"
    assert ROOT.resolve() not in work.parents
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    meshes = {n: oriented(n, model / "parts" / f"{n}.stl") for n in PARTS}
    parts = {}
    for n, m in meshes.items():
        d = work / n
        d.mkdir()
        (d / f"{n}.stl").write_bytes(m.export(file_type="stl"))
        parts[n] = {**summary(printprep(a.printforge, d / f"{n}.stl", d / "out")), "parts_sha256": sha(model / "parts" / f"{n}.stl"),
                    "flipped": n in FLIP, "extents": [round(v, 2) for v in m.extents]}
        print(n, parts[n], flush=True)
    sl = model / "slicer"
    sl.mkdir(exist_ok=True)
    for f in sl.iterdir():                                   # 폴더는 두고 파일만(드라이브 미러가 폴더를 잡고 있으면 rmdir 이 거부됨)
        if f.is_file():
            f.unlink()
    plates = {}
    for pn, want in PLATES.items():
        items = [(f"{n}#{k + 1}", meshes[n]) for n, c in want.items() for k in range(c)]
        placed, allm, fits = pack(items)
        pstl = model / f"print-plate-{pn}.stl"
        pstl.write_bytes(allm.export(file_type="stl"))
        rep = printprep(a.printforge, pstl, work / f"plate-{pn}")
        proj = next((work / f"plate-{pn}").glob("*.3mf"))
        shutil.copyfile(proj, sl / f"{NAME}-{pn}.bambu.3mf")
        shutil.copyfile(work / f"plate-{pn}" / "print_prep_report.json", sl / f"print_prep_report-{pn}.json")
        plates[pn] = {**summary(rep), "fits_bed": fits, "items": want, "plate_stl_sha256": sha(pstl), "project_sha256": sha(sl / f"{NAME}-{pn}.bambu.3mf"),
                      "bounds": allm.bounds.tolist(), "profiles": rep.get("profiles")}
        print(pn, plates[pn]["verdict"], plates[pn]["support_needed"], plates[pn]["mass_g"], plates[pn]["time_s"], fits, flush=True)
    ok = all(p["verdict"] == "ready" and not p["support_needed"] for p in parts.values()) and all(p["fits_bed"] and p["verdict"] == "ready" for p in plates.values())
    out = {"what": "MP16 구동 모듈 출력 준비(뱀부 스튜디오 명령줄 · printforge printprep) — 한 색 · 시스템 기본값. 프로젝트는 명령줄이 저장한 것이라 그대로는 "
                   "명령줄 슬라이스가 −100(창에서는 됨) · 두 색 · 희생 레이어는 보낼 때 판 도구로", "ok": ok, "parts": parts, "plates": plates,
           "two_modules_note": "판 셋 = J2 · J3 두 모듈 몫(원판 넷 = DISC_1 넷 · 와셔 세 벌 두 짝 · 시험대 · 시험 팔 하나)"}
    (ROOT / ".dev" / "mp16-evidence" / "printprep.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item()) + "\n")
                                                                    .encode("utf-8"))
    print("ok", ok)


if __name__ == "__main__":
    main()
