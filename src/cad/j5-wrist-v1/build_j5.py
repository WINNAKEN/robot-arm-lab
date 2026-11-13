# -*- coding: utf-8 -*-
"""MP10 — J5 손목 실부품 만들기: j5geom.py 의 SolidCraft 명령 → native · STEP · 3MF · 부품 STL(fine) · 그림 + 만들기 기록.

쓰기는 guard.py 로 models/j5-wrist-v1 · .dev/mp10-evidence · 격리 작업 뿌리(표지 MP10_SCRATCH)만.
사용: python build_j5.py --cli <solidcraft-cli.exe> --scratch-root <작업 뿌리> [--control <이름> --out <작업 뿌리 아래>] [--no-snapshot]
양성 대조(--control)는 산출을 작업 뿌리 아래에만 쓴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402
import j5geom  # noqa: E402

NAME = "j5-wrist-v1"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch-root", required=True, type=Path)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--control", default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-snapshot", action="store_true")
    a = ap.parse_args()
    root = guard.find_root(HERE)
    scratch = Path(a.scratch_root)
    if a.control:
        if a.out is None:
            raise SystemExit("--control needs --out under the scratch root")
        out = guard.checked_dir(a.out, root, scratch)
        if guard._scratch(root, scratch) not in [out, *out.parents]:
            raise SystemExit("control output must be under the scratch root")
        ev = out
    else:
        out = guard.checked_dir(a.out or root / "models" / NAME, root, scratch)
        ev = guard.checked_dir(root / ".dev" / "mp10-evidence" / "build", root, scratch)
    work = guard.checked_dir(scratch / ("build-" + (a.control or "main")), root, scratch)
    for d in (out, out / "parts", ev, work):
        guard.checked_dir(d, root, scratch).mkdir(parents=True, exist_ok=True)

    spec = j5geom.Spec(a.params, control=a.control)
    sc = j5geom.build_all(spec)
    stl = {}
    for b in j5geom.PARTS:
        p = guard.checked_file(out / "parts" / f"{b}.stl", root, scratch)
        sc.cmd("file.save_mesh", path=str(p), format="stl", bodies=[b], quality="fine")
        stl[b] = p
    script = guard.checked_file(work / "build.json", root, scratch)
    script.write_bytes((json.dumps({"commands": sc.commands}, ensure_ascii=False) + "\n").encode("utf-8"))
    native = guard.checked_file(out / f"{NAME}.solidcraft", root, scratch)
    step = guard.checked_file(out / f"{NAME}.step", root, scratch)
    m3f = guard.checked_file(out / f"{NAME}.3mf", root, scratch)
    result = guard.checked_file(work / "result.json", root, scratch)
    env = dict(os.environ)
    env["PATH"] = str(Path(a.cli).parent) + os.pathsep + env.get("PATH", "")
    p = subprocess.run([str(a.cli), "run", str(script), "--save", str(native), "--out", str(step), "--out", str(m3f), "--results",
                        "--json-out", str(result)], capture_output=True, text=True, encoding="utf-8", timeout=3600, env=env)
    guard.write_bytes(work / "run.log", ((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"), root, scratch)
    if p.returncode:
        raise SystemExit(f"solidcraft run rc {p.returncode}: {(p.stderr or p.stdout)[-2000:]}")
    if not a.no_snapshot:
        for view in ("iso", "front", "top"):
            png = guard.checked_file(out / f"{view}.png", root, scratch)
            q = subprocess.run([str(a.cli), "snapshot", "--in", str(native), "--out", str(png), "--view", view, "--width", "1600", "--height", "1200"],
                               capture_output=True, text=True, encoding="utf-8", timeout=600, env=env)
            if q.returncode:
                print(f"snapshot {view} rc {q.returncode}: {(q.stderr or q.stdout)[-500:]}")
    missing = [b for b, pth in stl.items() if not pth.is_file()]
    if missing:
        raise SystemExit(f"STL not written: {missing}")
    v = subprocess.run([str(a.cli), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    rec = {
        "what": "J5 손목 v1 만들기 기록 — 이 기록의 sha256 과 지금 파일이 같아야 검사가 지금 형상을 본 것이다",
        "control": a.control,
        "tool": {"cli_version": (v.stdout or v.stderr or "").strip(), "cli_sha256": sha(a.cli), "cli_name": Path(a.cli).name},
        "parts": j5geom.PARTS,
        "fits_used": spec.fits, "fit_status": spec.fit_status, "motor_used": spec.motor, "motor_status": spec.motor_status, "driver_z_used": spec.z_drv,
        "screws": spec.screws(),
        "inputs_sha256": {"parameters.json": sha(a.params), "j5geom.py": sha(HERE / "j5geom.py"), "build_j5.py": sha(__file__),
                          **{k: sha(v) for k, v in spec.paths.items()}},
        "outputs_sha256": {**{f"parts/{b}.stl": sha(p) for b, p in stl.items()}, f"{NAME}.solidcraft": sha(native), f"{NAME}.step": sha(step),
                           f"{NAME}.3mf": sha(m3f)},
        "command_count": len(sc.commands),
    }
    guard.write_bytes(ev / "build-record.json", (json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), root, scratch)
    print(json.dumps({"parts": len(stl), "commands": len(sc.commands), "control": a.control}, ensure_ascii=False))


if __name__ == "__main__":
    main()
