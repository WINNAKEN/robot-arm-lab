# -*- coding: utf-8 -*-
"""MP10 양성 대조 — 생성기에 고장을 넣어(j5geom CONTROLS) 작업 뿌리 아래에 다시 만들고, 검사기가 그 고장을 잡는지 본다.
대조마다 「잡아야 할 검사」 와 C2(독립 정답표 — 늘 진짜 parameters 로 계산)가 거짓이어야 잡힌 것이다. open_mesh 는 본 판 허브 STL 사본에서 면을 지운다(C1).
쓰기 = guard 로 작업 뿌리 · .dev/mp10-evidence/controls.json.
사용: python run_controls.py --cli <solidcraft-cli.exe> --scratch-root <작업 뿌리> [--only a,b]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402

CONTROLS = [("notch_rotated", ["C3"]), ("clamp_tight", ["C3"]), ("driver_small", ["C3"]), ("neck_shift", ["C5"]), ("hub_big", ["C9"]),
            ("cover_insert_out", ["C7"]), ("split_zero", ["C3"]), ("bolt_shallow", ["C4"]), ("insert_r", ["C2"]),
            ("ribs_low", ["C3b"]), ("no_head_channel", ["C10"]), ("neck_under", ["C4"]), ("hub_under", ["C4"]), ("cover_shallow", ["C4"]),
            ("no_j4_relief", ["C6b"]), ("term_narrow", ["C3"]), ("tslot_closed", ["C11"]), ("cover_insert_old_angles", ["C12"]),
            ("no_motor_connector", ["C3", "C10"])]          # 다시 만들기 3(11/01) 전 판 — 모터 커넥터 앞 칸 없음(사용자가 실물로 겪은 고장)
CODE = ["j5geom.py", "build_j5.py", "expected_j5.py", "validate_j5.py", "run_controls.py", "parameters.json", "guard.py"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, log, root, scr):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=5400, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    guard.write_bytes(log, ((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"), root, scr)
    return p.returncode


def verdict(check_json, targets):
    s = json.loads(Path(check_json).read_text(encoding="utf-8"))["summary"]
    got = {t: [v for k, v in s.items() if k.startswith(t + "_")] for t in targets + ["C2"]}
    caught = {t: (len(v) == 1 and v[0] is False) for t, v in got.items()}
    return s, caught


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch-root", required=True, type=Path)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    root = guard.find_root(HERE)
    scr = Path(a.scratch_root)
    base = guard.checked_dir(scr / "controls", root, scr)
    base.mkdir(parents=True, exist_ok=True)
    only = {x for x in a.only.split(",") if x}
    py = sys.executable
    rows = []
    for name, targets in CONTROLS:
        if only and name not in only:
            continue
        out = guard.checked_dir(base / name, root, scr)
        if out.exists():
            guard.safe_rmtree(out, root, scr)
        out.mkdir(parents=True)
        rc_b = run([py, "-B", str(HERE / "build_j5.py"), "--cli", str(a.cli), "--scratch-root", str(scr), "--control", name, "--out", str(out),
                    "--no-snapshot"], out / "build.log", root, scr)
        row = {"control": name, "targets": targets, "build_rc": rc_b}
        if rc_b == 0:
            rc_v = run([py, "-B", str(HERE / "validate_j5.py"), "--scratch-root", str(scr), "--model-dir", str(out), "--out", str(out / "check.json"),
                        "--no-print-record", "--fast", "--checks", ",".join(sorted(set(["C1", "C2"] + targets)))], out / "validate.log", root, scr)
            row["validate_rc"] = rc_v
            if (out / "check.json").is_file():
                s, caught = verdict(out / "check.json", targets)
                row.update({"summary": s, "caught": caught, "ok": all(caught.values())})
            else:
                row["ok"] = False
        else:
            row["ok"] = False
        rows.append(row)
        print(name, row.get("caught"), row["ok"])
    if not only or "open_mesh" in only:                              # C1: 열린 메시(허브 사본에서 면 20 개 지움)
        out = guard.checked_dir(base / "open_mesh", root, scr)
        if out.exists():
            guard.safe_rmtree(out, root, scr)
        (out / "parts").mkdir(parents=True)
        src = root / "models" / "j5-wrist-v1" / "parts"
        for f in src.glob("*.stl"):
            guard.write_bytes(out / "parts" / f.name, f.read_bytes(), root, scr)
        m = trimesh.load(out / "parts" / "J5_OUTPUT_HUB.stl")
        keep = np.ones(len(m.faces), bool)
        keep[:20] = False
        m.update_faces(keep)
        hub_p = guard.checked_file(out / "parts" / "J5_OUTPUT_HUB.stl", root, scr)
        os.unlink(hub_p)
        guard.write_bytes(hub_p, m.export(file_type="stl"), root, scr)
        rc_v = run([py, "-B", str(HERE / "validate_j5.py"), "--scratch-root", str(scr), "--model-dir", str(out), "--out", str(out / "check.json"),
                    "--no-print-record", "--checks", "C1"], out / "validate.log", root, scr)
        s = json.loads((out / "check.json").read_text(encoding="utf-8"))["summary"] if (out / "check.json").is_file() else {}
        c1 = [v for k, v in s.items() if k.startswith("C1_")]
        rows.append({"control": "open_mesh", "targets": ["C1"], "validate_rc": rc_v, "summary": s, "caught": {"C1": c1 == [False]}, "ok": c1 == [False]})
        print("open_mesh", rows[-1]["caught"])
    if not only or "tamper_record" in only:                          # C0: 본 판 사본 + 만들기 기록 · 허브 STL 을 같은 모양으로 다시 써서 sha 만 바꿈
        out = guard.checked_dir(base / "tamper_record", root, scr)
        if out.exists():
            guard.safe_rmtree(out, root, scr)
        (out / "parts").mkdir(parents=True)
        src = root / "models" / "j5-wrist-v1" / "parts"
        for f in src.glob("*.stl"):
            guard.write_bytes(out / "parts" / f.name, f.read_bytes(), root, scr)
        rec_src = root / ".dev" / "mp10-evidence" / "build" / "build-record.json"
        guard.write_bytes(out / "build-record.json", rec_src.read_bytes(), root, scr)
        m = trimesh.load(out / "parts" / "J5_OUTPUT_HUB.stl")
        hub_p = guard.checked_file(out / "parts" / "J5_OUTPUT_HUB.stl", root, scr)
        os.unlink(hub_p)
        guard.write_bytes(hub_p, m.export(file_type="stl"), root, scr)
        rc_v = run([py, "-B", str(HERE / "validate_j5.py"), "--scratch-root", str(scr), "--model-dir", str(out), "--out", str(out / "check.json"),
                    "--no-print-record", "--checks", "C0,C1"], out / "validate.log", root, scr)
        s = json.loads((out / "check.json").read_text(encoding="utf-8"))["summary"] if (out / "check.json").is_file() else {}
        c0 = [v for k, v in s.items() if k.startswith("C0_")]
        c1 = [v for k, v in s.items() if k.startswith("C1_")]
        rows.append({"control": "tamper_record", "targets": ["C0"], "validate_rc": rc_v, "summary": s, "caught": {"C0": c0 == [False]},
                     "ok": c0 == [False] and c1 == [True]})
        print("tamper_record", rows[-1]["caught"])
    rec = {"what": "MP10 J5 손목 양성 대조 — 고장 판을 검사기가 잡는지(잡아야 할 검사 + C2 가 모두 거짓)",
           "date": datetime.now().astimezone().isoformat(timespec="seconds"), "scratch": str(scr),
           "code_sha256": {n: sha(HERE / n) for n in CODE}, "all_caught": all(r["ok"] for r in rows), "rows": rows}
    dest = root / ".dev" / "mp10-evidence" / ("controls.json" if not only else "controls-partial.json")
    if dest.exists():
        os.unlink(guard.checked_file(dest, root, scr))
    guard.write_bytes(dest, (json.dumps(rec, ensure_ascii=False, indent=1, default=str) + "\n").encode("utf-8"), root, scr)
    print("ALL CAUGHT" if rec["all_caught"] else "NOT ALL CAUGHT")


if __name__ == "__main__":
    main()
