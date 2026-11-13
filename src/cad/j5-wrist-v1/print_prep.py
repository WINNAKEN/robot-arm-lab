# -*- coding: utf-8 -*-
"""MP10 — J5 손목 출력 준비 · 질량: 부품마다 출력 방향으로 돌려 하나씩 슬라이스(printforge printprep · H2D · PLA Basic · 0.20 Standard)하고
한 판(J5 부품 넷)을 G-code 없는 뱀부 스튜디오 프로젝트로 준비한다(보내기 · 출력은 사용자). MP6 감속기 인쇄 부품도 질량만 재려고 하나씩 슬라이스한다(읽기만).
질량 기록(mass-properties.json): 인쇄 = 슬라이서 질량 · 무게중심 = STL 부피 중심(모듈 좌표) · 구매품 = 원장 · 어림 값(출처 표기).

사용: python print_prep.py --printforge <printforge 저장소> --scratch-root <작업 뿌리>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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

ORIENT = {"z_up": np.eye(3), "z_down": np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], float)}
PART_ORIENT = {"J5_STATOR_A": "z_up", "J5_STATOR_B": "z_up", "J5_REAR_COVER": "z_down", "J5_OUTPUT_HUB": "z_up"}
MP6_PRINTED = ["HOUSING_BASE", "HOUSING_CAP", "RETAINER", "DISC_1", "DISC_2", "CARRIER", "OUTPUT_FLANGE", "CAM_LOWER", "CAM_UPPER", "WASHER"]
GAP, ROW = 10.0, 300.0


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
        for dp, _dn, fn in os.walk(out):
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
    fits = bool(plate.bounds[0][0] >= 0 and plate.bounds[0][1] >= 0 and plate.bounds[1][0] <= bed[0] and plate.bounds[1][1] <= bed[1])
    return plate, fits, {n: m.bounds.tolist() for n, m in placed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--printforge", type=Path, required=True)
    ap.add_argument("--scratch-root", type=Path, required=True)
    a = ap.parse_args()
    root = guard.find_root(HERE)
    model = guard.checked_dir(root / "models" / "j5-wrist-v1", root, a.scratch_root)
    ev = guard.checked_dir(root / ".dev" / "mp10-evidence", root, a.scratch_root)
    work = guard.checked_dir(Path(a.scratch_root) / "printprep", root, a.scratch_root)
    if work.exists():
        guard.safe_rmtree(work, root, a.scratch_root)
    work.mkdir(parents=True)
    P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    env = dict(os.environ)
    parts = {n: trimesh.load(model / "parts" / f"{n}.stl", force="mesh") for n in PART_ORIENT}
    per_part = {}
    for name, mesh in parts.items():
        d = guard.checked_dir(work / name, root, a.scratch_root)
        d.mkdir()
        stl = guard.write_bytes(d / f"{name}.stl", oriented(mesh, PART_ORIENT[name]).export(file_type="stl"), root, a.scratch_root)
        rep = printprep(a.printforge, stl, d / "out", env)
        est = rep.get("estimate") or {}
        per_part[name] = {"verdict": rep.get("verdict"), "support_needed": (rep.get("support") or {}).get("advised_by_studio"),
                          "mass_g": est.get("filament_g"), "time": est.get("print_time_s"), "orient": PART_ORIENT[name],
                          "stl_sha256": sha(model / "parts" / f"{name}.stl")}
        print(name, per_part[name])
    mp6_dir = (HERE / P["sources"]["reducer_parts"]).resolve()
    mp6 = {}
    for name in MP6_PRINTED:
        src = mp6_dir / f"{name}.stl"
        d = guard.checked_dir(work / f"MP6_{name}", root, a.scratch_root)
        d.mkdir()
        stl = guard.write_bytes(d / f"{name}.stl", oriented(trimesh.load(src, force="mesh"), "z_up").export(file_type="stl"), root, a.scratch_root)
        rep = printprep(a.printforge, stl, d / "out", env)
        est = rep.get("estimate") or {}
        mp6[name] = {"verdict": rep.get("verdict"), "mass_g": est.get("filament_g"), "stl_sha256": sha(src)}
        print("MP6", name, mp6[name])
    slicer = guard.checked_dir(model / "slicer", root, a.scratch_root)
    if slicer.exists():
        guard.safe_rmtree(slicer, root, a.scratch_root)
    plate, fits, bounds = lay_plate({n: oriented(parts[n], PART_ORIENT[n]) for n in PART_ORIENT})
    pstl = guard.checked_file(model / "print-plate.stl", root, a.scratch_root)
    if pstl.exists():
        os.unlink(pstl)
    guard.write_bytes(pstl, plate.export(file_type="stl"), root, a.scratch_root)
    tmp = work / "plate"
    rep = printprep(a.printforge, pstl, tmp, env)
    dest = guard.checked_dir(slicer, root, a.scratch_root)
    dest.mkdir(parents=True, exist_ok=True)
    for f in tmp.iterdir():
        if f.is_file():
            guard.write_bytes(dest / f.name, f.read_bytes(), root, a.scratch_root)
    est = rep.get("estimate") or {}
    plate_rec = {"fits_bed": fits, "bounds": bounds, "verdict": rep.get("verdict"), "support_needed": (rep.get("support") or {}).get("advised_by_studio"),
                 "mass_g": est.get("filament_g"), "time": est.get("print_time_s"), "plate_sha256": sha(pstl),
                 "slicer_sha256": {f.name: sha(f) for f in sorted(dest.iterdir()) if f.is_file()}}
    print("plate", plate_rec["verdict"], plate_rec["mass_g"], plate_rec["time"], "fits", fits)

    # 질량 · 무게중심(모듈 좌표 · z = J5 축 · 0 = 모터 앞면)
    mot = json.loads((HERE / P["sources"]["motor_ledger"]).resolve().read_text(encoding="utf-8"))["items"]
    items = []
    for n, m in parts.items():
        items.append({"name": n, "kind": "printed (J5)", "mass_g": per_part[n]["mass_g"], "com_mm": [round(float(v), 2) for v in m.center_mass],
                      "source": "슬라이서(부품 하나 · 출력 방향) · STL 부피 중심"})
    for n, r in mp6.items():
        m = trimesh.load(mp6_dir / f"{n}.stl", force="mesh")
        items.append({"name": f"MP6 {n}", "kind": "printed (MP6)", "mass_g": r["mass_g"], "com_mm": [round(float(v), 2) for v in m.center_mass],
                      "source": "슬라이서(부품 하나 · 그대로 세움) · STL 부피 중심"})
    ol = float(mot["overall_length"]["value"])
    items.append({"name": "모터 + 드라이버(MKS SERVO42D CAN MT)", "kind": "purchased", "mass_g": 1000 * float(mot["mass_motor_with_driver"]["value"]),
                  "com_mm": [0.0, 0.0, round(-ol / 2, 2)],
                  "source": f"모터 원장 mass_motor_with_driver ({mot['mass_motor_with_driver']['status']}) · 무게중심 = 앞면 ~ overall_length "
                            f"({mot['overall_length']['status']}) 가운데(어림)"})
    steel = 7.85e-3
    pins28 = 28 * math.pi * 2.0 ** 2 * 28.0 * steel
    pins20 = 6 * math.pi * 2.0 ** 2 * 20.0 * steel
    items.append({"name": "강철 다월 Ø4 × 28 (28) + Ø4 × 20 (6)", "kind": "purchased", "mass_g": round(pins28 + pins20, 1), "com_mm": [0.0, 0.0, 15.0],
                  "source": "강 밀도 7.85 g/cm³ × 원기둥 부피(어림) · 무게중심 어림"})
    items.append({"name": "베어링 6808 + 6801 × 2 + 6800", "kind": "purchased", "mass_g": 45.0, "com_mm": [0.0, 0.0, 22.0],
                  "source": "어림(깊은 홈 얇은 판 베어링 대략 무게 — 판매처 · 카탈로그로 확인 안 함 · 받으면 잼)"})
    items.append({"name": "나사 · 인서트(M3 — 이 단위 16 + MP6 12(출력 플랜지 넷은 허브 나사로 바뀜 · 검토 R-12) · 인서트 12 + MP6 12)", "kind": "purchased",
                  "mass_g": round(28 * 0.7 + 24 * 0.3, 1),
                  "com_mm": [0.0, 0.0, 0.0], "source": "어림(강 M3 × 10 약 0.7 g · 황동 인서트 약 0.3 g)"})
    tot = sum(i["mass_g"] for i in items)
    com = [sum(i["mass_g"] * i["com_mm"][k] for i in items) / tot for k in range(3)]
    mpj = {"what": "J5 모듈 질량 · 무게중심 어림(모듈 좌표 · z = J5 축 · 0 = 모터 앞면 · 링크 4 점 = (x + 78, z − 21, −y))",
           "total_mass_g": round(tot, 1), "com_mm": [round(v, 2) for v in com], "items": items,
           "printed_mass_source": "printforge printprep(뱀부 스튜디오 · H2D 0.4 · 0.20 Standard · PLA Basic) — 부품 하나씩",
           "parts_sha256": {n: per_part[n]["stl_sha256"] for n in parts}}
    guard.write_bytes(model / "mass-properties.json", (json.dumps(mpj, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), root, a.scratch_root)
    rec = {"what": "J5 손목 v1 출력 준비 기록(MP10) — 부품별 · 한 판 · MP6 인쇄 부품 질량", "parts": per_part, "mp6_parts": mp6, "plate": plate_rec,
           "orient_note": "반쪽 둘 = 뒤 끝을 바닥에(z 위) · 덮개 = 바깥 면 위(뒤집음) · 허브 = 밑면이 바닥"}
    guard.write_bytes(ev / "printprep.json", (json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), root, a.scratch_root)
    print(json.dumps({"total_mass_g": mpj["total_mass_g"], "com_mm": mpj["com_mm"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
