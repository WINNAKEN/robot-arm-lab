# -*- coding: utf-8 -*-
"""MP13 핀 구멍 시편 검사 — 커밋된 STL 로 스스로 계산(읽기만 · 쓰기 = check.json 하나).

C0 만들기 기록의 sha = 지금 STL · 입력 · 고장 판 아님   C1 닫힘 · 부피 > 0
C2 구멍마다 단면(z 2 · 5 · 8)의 넓이 같은 원 지름 = 표의 값(± check_tolerance.dia) · 중심(± centre) · 왼쪽 → 오른쪽 커짐
C3 구멍이 관통(가운데 z 방향 광선이 재료를 만나지 않음)   C4 출력 준비 기록 = 지금 STL · ready · 지지대 없음
대조: --controls <작업 폴더> 면 build_pin_coupon.py 로 고장 판 둘(swap → C2 · blind → C3)을 만들어 잡히는지 보고 controls.json 을 쓴다.
사용: python check_pin_coupon.py [--model-dir D] [--out F] [--controls <작업 폴더> --cli <solidcraft-cli.exe>]
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
NAME, BODY = "pin-coupon-v1", "PIN_COUPON"
EV = ROOT / ".dev" / "mp13-evidence"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(model, P, rec, pp):
    stl = model / "parts" / f"{BODY}.stl"
    m = trimesh.load(stl, force="mesh")
    s, r = {}, {}
    if rec is not None:
        ok_out = rec["outputs_sha256"].get(f"parts/{BODY}.stl") == sha(stl)
        ok_in = rec["inputs_sha256"] == {"parameters.json": sha(HERE / "parameters.json"), "build_pin_coupon.py": sha(HERE / "build_pin_coupon.py")}
        r["C0"] = {"stl_matches": ok_out, "inputs_match": ok_in, "control": rec.get("control")}
        s["C0_build_record_matches_files"] = ok_out and ok_in and rec.get("control") is None
    s["C1_closed_and_positive_volume"] = bool(m.is_watertight) and float(m.volume) > 0
    r["C1"] = {"watertight": bool(m.is_watertight), "volume_mm3": float(m.volume)}
    tol = P["check_tolerance"]
    rows, ok2 = [], True
    for i, dia in enumerate(P["holes"]):
        cx, cy = P["first_x"] + P["pitch"] * i, P["hole_y"]
        for z in (2.0, 5.0, 8.0):
            sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            best = None
            for loop in sec.discrete:                                   # 닫힌 고리마다 xy 신발끈 넓이 · 무게중심
                q = np.asarray(loop)[:, :2]
                x0, y0, x1, y1 = q[:-1, 0], q[:-1, 1], q[1:, 0], q[1:, 1]
                cr = x0 * y1 - x1 * y0
                area = cr.sum() / 2
                if abs(area) < 1e-9:
                    continue
                c = np.array([((x0 + x1) * cr).sum(), ((y0 + y1) * cr).sum()]) / (6 * area)
                d = math.hypot(c[0] - cx, c[1] - cy)
                if d < 1.0 and abs(area) < 50 and (best is None or d < best[0]):
                    best = (d, 2 * math.sqrt(abs(area) / math.pi), c.tolist())
            if best is None:
                rows.append({"hole": i, "design": dia, "z": z, "found": False, "ok": False})
                ok2 = False
                continue
            ok = abs(best[1] - dia) <= tol["dia"] and best[0] <= tol["centre"]
            ok2 &= ok
            rows.append({"hole": i, "design": dia, "z": z, "dia_area_eq": round(best[1], 4), "centre_off": round(best[0], 4), "ok": ok})
    mean = [float(np.mean([q["dia_area_eq"] for q in rows if q["hole"] == i and q.get("dia_area_eq")])) if any(q["hole"] == i and q.get("dia_area_eq") for q in rows)
            else 0.0 for i in range(len(P["holes"]))]
    rising = all(b > a for a, b in zip(mean, mean[1:]))
    r["C2"] = {"rows": rows, "mean_dia": [round(v, 4) for v in mean], "rising_left_to_right": rising}
    s["C2_holes_match_table"] = ok2 and rising
    t = P["plate"]["thickness"]
    blocked = []
    for i in range(len(P["holes"])):
        o = np.array([[P["first_x"] + P["pitch"] * i, P["hole_y"], t + 5.0]])
        hits = m.ray.intersects_location(o, np.array([[0, 0, -1.0]]))[0]
        if len(hits):
            blocked.append({"hole": i, "first_hit_z": float(hits[:, 2].max())})
    r["C3"] = {"blocked": blocked}
    s["C3_holes_go_through"] = not blocked
    if pp is not None:
        e = pp.get("part", {})
        r["C4"] = e
        s["C4_print_prep_ready"] = e.get("stl_sha256") == sha(stl) and e.get("verdict") == "ready" and e.get("support_needed") is False
    return s, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, default=ROOT / "models" / NAME)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--controls", type=Path, default=None)
    ap.add_argument("--cli", type=Path, default=None)
    a = ap.parse_args()
    P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    if a.controls:
        rows = []
        for name, target in (("swap", "C2_holes_match_table"), ("blind", "C3_holes_go_through")):
            out = a.controls / name
            p = subprocess.run([sys.executable, "-B", str(HERE / "build_pin_coupon.py"), "--cli", str(a.cli), "--scratch", str(a.controls),
                                "--control", name, "--out", str(out), "--no-snapshot"], capture_output=True, text=True, encoding="utf-8", timeout=1200)
            if p.returncode:
                rows.append({"control": name, "build_rc": p.returncode, "ok": False, "err": (p.stderr or p.stdout)[-600:]})
                continue
            s, _r = check(out, P, None, None)
            rows.append({"control": name, "target": target, "summary": s, "caught": s[target] is False, "ok": s[target] is False})
        rec = {"what": "MP13 핀 구멍 시편 양성 대조 — 고장 판을 검사가 잡는지", "rows": rows, "all_caught": all(x["ok"] for x in rows),
               "code_sha256": {n: sha(HERE / n) for n in ("parameters.json", "build_pin_coupon.py", "check_pin_coupon.py")}}
        (EV / "controls.json").write_bytes((json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        print(json.dumps({x["control"]: x.get("caught") for x in rows}), "ALL CAUGHT" if rec["all_caught"] else "NOT ALL CAUGHT")
        return
    rec = json.loads((EV / "build" / "build-record.json").read_text(encoding="utf-8"))
    ppf = EV / "printprep.json"
    pp = json.loads(ppf.read_text(encoding="utf-8")) if ppf.is_file() else {}
    s, r = check(a.model_dir, P, rec, pp)
    out = {"what": "MP13 핀 구멍 시편 검사 — 커밋된 STL 로 스스로 계산", "summary": s, "all_true": all(s.values()), "results": r,
           "inputs_sha256": {f"parts/{BODY}.stl": sha(a.model_dir / "parts" / f"{BODY}.stl"), "check_pin_coupon.py": sha(__file__),
                             "parameters.json": sha(HERE / "parameters.json")}}
    (a.out or a.model_dir / "check.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
