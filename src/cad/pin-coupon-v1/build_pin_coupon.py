# -*- coding: utf-8 -*-
"""MP13 — 강철 Ø4 다월 핀 구멍 시편 v1(SolidCraft): 관통 구멍 여덟(parameters.json holes · 왼쪽 → 오른쪽 = 작은 값 → 큰 값) + 새긴 두 자리 숫자.

윗면에서 넣음 = 바닥판 · 캐리어 압입 구멍(출력할 때 위로 열림) · 밑면(판에 닿던 면)에서 넣음 = 덮개 미끄럼 구멍(덮개는 핀 구멍이 판 쪽으로 열린 채 출력).
쓰기는 models/pin-coupon-v1 · .dev/mp13-evidence · 작업 폴더(--scratch)만. 양성 대조(--control)는 작업 폴더 아래에만 쓴다.
사용: python build_pin_coupon.py --cli <solidcraft-cli.exe> --scratch <작업 폴더> [--control swap|blind --out <작업 폴더 아래>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME, BODY = "pin-coupon-v1", "PIN_COUPON"
CONTROLS = {"swap": "second and third holes swapped (4.20 drilled where 4.15 is labelled)", "blind": "holes stop 1.0 above the bottom face"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inside(p, *roots):
    p = Path(p).resolve()
    return any(p == r.resolve() or r.resolve() in p.parents for r in roots)


def commands(P, control=None):
    cmds = []

    def cmd(c, **p):
        cmds.append({"command": c, "params": p})

    pl, t = P["plate"], P["plate"]["thickness"]
    holes = list(P["holes"])
    if control == "swap":
        holes[1], holes[2] = holes[2], holes[1]
    cmd("sketch.create", name="PLATE_SK", plane={"origin": [0, 0, 0], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})
    cmd("sketch.rectangle.rounded", p0=[0, 0], p1=[pl["length"], pl["width"]], radius=pl["corner_r"])
    cmd("sketch.finish")
    cmd("solid.extrude", distance=t, operation="new", body_name=BODY, name="PLATE_X")
    lb = P["label"]
    for i, dia in enumerate(holes):
        x = P["first_x"] + P["pitch"] * i
        cmd("sketch.create", name=f"H{i}_SK", plane={"origin": [x, P["hole_y"], t], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})
        cmd("sketch.circle.center", center=[0, 0], radius=dia / 2)
        cmd("sketch.finish")
        cmd("solid.extrude", distance=(t - 1.0) if control == "blind" else t, direction="negative", operation="cut", targets=[BODY], name=f"H{i}_X")
        # 숫자는 설계 값(대조 swap 이어도 표 순서 그대로) — 4.10 → 「10」
        text = f"{round((P['holes'][i] - 4.0) * 100):02d}"
        cmd("sketch.create", name=f"L{i}_SK", plane={"origin": [x + lb["x_offset"], lb["y"], t], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]})
        cmd("sketch.text", text=text, at=[0, 0], height=lb["height"])
        cmd("sketch.finish")
        cmd("solid.extrude", distance=lb["depth"], direction="negative", operation="cut", targets=[BODY], name=f"L{i}_X")
    return cmds, holes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--control", choices=sorted(CONTROLS), default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-snapshot", action="store_true")
    a = ap.parse_args()
    scr = a.scratch.resolve()
    assert not inside(scr, ROOT), "scratch must be outside the repo"
    if a.control:
        assert a.out and inside(a.out, scr), "--control needs --out under --scratch"
        out, ev = a.out, a.out
    else:
        out, ev = ROOT / "models" / NAME, ROOT / ".dev" / "mp13-evidence" / "build"
    work = scr / ("build-" + (a.control or "main"))
    for d in (out, out / "parts", ev, work):
        assert inside(d, ROOT / "models" / NAME, ROOT / ".dev" / "mp13-evidence", scr), d
        d.mkdir(parents=True, exist_ok=True)
    P = json.loads(a.params.read_text(encoding="utf-8"))
    cmds, drilled = commands(P, a.control)
    stl = out / "parts" / f"{BODY}.stl"
    cmds.append({"command": "file.save_mesh", "params": {"path": str(stl), "format": "stl", "bodies": [BODY], "quality": P["quality"]}})
    script = work / "build.json"
    script.write_bytes((json.dumps({"commands": cmds}, ensure_ascii=False) + "\n").encode("utf-8"))
    native, step = out / f"{NAME}.solidcraft", out / f"{NAME}.step"
    env = dict(os.environ)
    env["PATH"] = str(a.cli.parent) + os.pathsep + env.get("PATH", "")
    p = subprocess.run([str(a.cli), "run", str(script), "--save", str(native), "--out", str(step), "--results", "--json-out", str(work / "result.json")],
                       capture_output=True, text=True, encoding="utf-8", timeout=1200, env=env)
    (work / "run.log").write_bytes(((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")).encode("utf-8"))
    if p.returncode or not stl.is_file():
        raise SystemExit(f"solidcraft run rc {p.returncode}: {(p.stderr or p.stdout)[-1500:]}")
    if not a.no_snapshot:
        for view in ("iso", "top"):
            q = subprocess.run([str(a.cli), "snapshot", "--in", str(native), "--out", str(out / f"{view}.png"), "--view", view, "--width", "1600",
                                "--height", "1200"], capture_output=True, text=True, encoding="utf-8", timeout=600, env=env)
            if q.returncode:
                print(f"snapshot {view} rc {q.returncode}: {(q.stderr or q.stdout)[-400:]}")
    v = subprocess.run([str(a.cli), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    rec = {"what": "MP13 핀 구멍 시편 만들기 기록 — 이 sha 와 지금 파일이 같아야 검사가 지금 형상을 본 것이다", "control": a.control,
           "control_means": CONTROLS.get(a.control), "drilled_holes": drilled, "labelled_holes": P["holes"],
           "tool": {"cli_version": (v.stdout or v.stderr or "").strip(), "cli_sha256": sha(a.cli)},
           "inputs_sha256": {"parameters.json": sha(a.params), "build_pin_coupon.py": sha(__file__)},
           "outputs_sha256": {f"parts/{BODY}.stl": sha(stl), f"{NAME}.solidcraft": sha(native), f"{NAME}.step": sha(step)},
           "command_count": len(cmds)}
    (ev / "build-record.json").write_bytes((json.dumps(rec, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({"control": a.control, "commands": len(cmds), "stl": str(stl)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
