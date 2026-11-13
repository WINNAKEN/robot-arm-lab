# -*- coding: utf-8 -*-
"""MP8 — 그리퍼 KG1 만들기: kg1.py 의 SolidCraft 명령 → native · STEP · 3MF · 부품 STL · 그림 + 만들기 기록.

쓰기는 guard.py 로 models/kmjh-gripper-v1 · .dev/mp8-evidence/gripper · 격리 작업 뿌리(표지 MP8_SCRATCH)만.
사용: python build_gripper.py --cli <solidcraft-cli.exe> --scratch-root <작업 뿌리> [--out <models 폴더>] [--evidence <근거 폴더>]
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
import kg1  # noqa: E402

NAME = "kmjh-gripper-v1"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch-root", required=True, type=Path)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    a = ap.parse_args()
    root = guard.find_root(HERE)
    out = guard.checked_dir(root / "models" / NAME, root, a.scratch_root)
    ev = guard.checked_dir(root / ".dev" / "mp8-evidence" / "gripper", root, a.scratch_root)
    work = guard.checked_dir(Path(a.scratch_root) / "build", root, a.scratch_root)
    for d in (out, out / "parts", ev, work):
        guard.checked_dir(d, root, a.scratch_root).mkdir(parents=True, exist_ok=True)

    P = kg1.load_params(a.params)
    sc, parts, pads, coupon = kg1.build_all(P)
    bodies = parts + pads + coupon
    stl = {}
    for b in bodies:
        p = guard.checked_file(out / "parts" / f"{b}.stl", root, a.scratch_root)
        sc.cmd("file.export", path=str(p), bodies=[b])
        stl[b] = p
    script = guard.checked_file(work / "build.json", root, a.scratch_root)
    script.write_bytes((json.dumps({"commands": sc.commands}, ensure_ascii=False) + "\n").encode("utf-8"))
    native = guard.checked_file(out / f"{NAME}.solidcraft", root, a.scratch_root)
    step = guard.checked_file(out / f"{NAME}.step", root, a.scratch_root)
    m3f = guard.checked_file(out / f"{NAME}.3mf", root, a.scratch_root)
    result = guard.checked_file(work / "result.json", root, a.scratch_root)
    env = dict(os.environ)
    p = subprocess.run([str(a.cli), "run", str(script), "--save", str(native), "--out", str(step), "--out", str(m3f), "--results",
                        "--json-out", str(result)], capture_output=True, text=True, encoding="utf-8", timeout=3600, env=env)
    (work / "run.log").write_bytes(((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"))
    if p.returncode:
        raise SystemExit(f"solidcraft run rc {p.returncode}: {(p.stderr or p.stdout)[-2000:]}")
    for view in ("iso", "front", "top"):
        png = guard.checked_file(out / f"{view}.png", root, a.scratch_root)
        q = subprocess.run([str(a.cli), "snapshot", "--in", str(native), "--out", str(png), "--view", view, "--width", "1600", "--height", "1200"],
                           capture_output=True, text=True, encoding="utf-8", timeout=600, env=env)
        if q.returncode:
            print(f"snapshot {view} rc {q.returncode}: {(q.stderr or q.stdout)[-500:]}")
    missing = [b for b, pth in stl.items() if not pth.is_file()]
    if missing:
        raise SystemExit(f"STL not written: {missing}")
    v = subprocess.run([str(a.cli), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    rec = {
        "what": "KG1 만들기 기록 — 이 기록의 sha256 과 지금 파일이 같아야 검사가 지금 형상을 본 것이다",
        "tool": {"cli_version": (v.stdout or v.stderr or "").strip(), "cli_sha256": sha(a.cli), "cli_name": Path(a.cli).name},
        "bodies": {"parts": parts, "pads": pads, "coupon": coupon},
        "fits_used": P["fits"], "fit_status": P["fit_status"],
        "holes": sc.holes,
        "inputs_sha256": {"parameters.json": sha(a.params), "kg1.py": sha(HERE / "kg1.py"), "build_gripper.py": sha(__file__),
                          "print-fits.json": sha((a.params.parent / P["fits_from"]["ledger"]).resolve())},
        "outputs_sha256": {**{f"parts/{b}.stl": sha(p) for b, p in stl.items()}, f"{NAME}.solidcraft": sha(native), f"{NAME}.step": sha(step),
                           f"{NAME}.3mf": sha(m3f)},
        "command_count": len(sc.commands),
    }
    guard.write_bytes(ev / "build-record.json", (json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), root, a.scratch_root)
    print(json.dumps({"bodies": len(bodies), "commands": len(sc.commands), "holes": len(sc.holes)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
