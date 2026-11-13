# -*- coding: utf-8 -*-
"""MP11 분해도 만들기 — 샷마다 Blender(explode_arm.py)를 돌리고 번호 그림(label_parts.py)을 붙인 뒤 manifest.json 을 쓴다.
산출 = models/arm-v3-kg1-exploded/(renders · data · manifest.json) · Blender 기록 = .dev/mp11-evidence/build/.
--scratch-root 를 주면 그 격리 폴더(표지 MP11_SCRATCH) 아래 arm-v3-kg1-exploded/ 에만 쓴다(시험용).
지문(sha256)은 글 파일(.py · .json · .md)이면 CRLF 를 LF 로 바꾼 바이트로 잰다 — 체크아웃 줄바꿈이 달라도 같은 값.

사용: python -I -B -X utf8 make_all.py [--blender <blender.exe>] [--scratch-root <격리 폴더>]
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard  # noqa: E402
import label_parts  # noqa: E402

BLENDER = r"C:\tools\Blender-5.2.3\blender-5.2.3-windows-x64\blender.exe"
TEXT = {".py", ".json", ".md"}
SCRIPTS = ["explode_arm.py", "label_parts.py", "guard.py", "make_all.py", "parameters.json"]


def fingerprint(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix.lower() in TEXT:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def input_paths(repo: Path) -> list[str]:
    """그림이 기대는 입력(읽기만) — 저장소 상대 경로."""
    prm = json.loads((repo / "src" / "cad" / "arm-v3-kg1-assembly" / "parameters.json").read_text(encoding="utf-8"))
    pad = prm["gripper"]["padset"]
    parts = ["BASE", "JAW_A", "JAW_B", "PINION", f"PAD_A_{pad}", f"PAD_B_{pad}"]
    return (["models/armold-mks-product-v3/blender/kmjh-arm-v3.blend", "models/arm-v3-kg1-assembly/assembly.json",
             "src/cad/arm-v3-kg1-assembly/parameters.json", "src/cad/kmjh-gripper-v1/parameters.json",
             "models/armold-mks-concept-v1/kinematics.json", "src/cad/armold-mks-product-v3/gallery_poses.json"]
            + [f"models/kmjh-gripper-v1/parts/{n}.stl" for n in parts])


def output_rel(prm: dict) -> list[str]:
    out = []
    for s in prm["shots"]:
        if s["assembled"]:
            out.append(f"renders/arm-assembled-{s['name']}.jpg")
        out += [f"renders/arm-exploded-{s['name']}.jpg", f"data/render-report-{s['name']}.json", f"data/label-grid-{s['name']}.json"]
    out.append(f"renders/{prm['numbered']['file']}")
    return out


def main():
    argv = sys.argv[1:]
    opt = {"blender": BLENDER, "scratch-root": None}
    i = 0
    while i < len(argv):
        opt[argv[i].lstrip("-")] = argv[i + 1]
        i += 2
    repo = guard.find_root(HERE)
    sr = opt["scratch-root"]
    base = (guard.allowed_roots(repo, sr)[-1] / "arm-v3-kg1-exploded") if sr else repo / "models" / "arm-v3-kg1-exploded"
    logdir = (base / "build-logs") if sr else repo / ".dev" / "mp11-evidence" / "build"
    for d in (base, base / "renders", base / "data", logdir):
        guard.checked_dir(d, repo, sr).mkdir(parents=True, exist_ok=True)
    prm = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    ins = input_paths(repo)
    in_sha0 = {p: fingerprint(repo / p) for p in ins}

    runs = []
    for s in prm["shots"]:
        cmd = [opt["blender"], "--background", "--factory-startup", "--python", str(HERE / "explode_arm.py"), "--",
               "--shot", s["name"], "--renders", str(base / "renders"), "--data", str(base / "data")]
        if sr:
            cmd += ["--scratch-root", sr]
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True)
        dt = time.time() - t0
        guard.write_bytes(logdir / f"blender-{s['name']}.log", r.stdout + b"\n--- stderr ---\n" + r.stderr, repo, sr)
        ok = r.returncode == 0 and b"DONE blend_unchanged True" in r.stdout
        runs.append({"shot": s["name"], "returncode": r.returncode, "seconds": round(dt, 1), "done_marker": ok})
        print("SHOT", s["name"], "rc", r.returncode, "done", ok, f"{dt:.0f}s", flush=True)
        if not ok:
            raise SystemExit(f"blender run failed for shot {s['name']} - see {logdir}")

    nb = prm["numbered"]
    lab = label_parts.label(base / "renders" / f"arm-exploded-{nb['shot']}.jpg", base / "data" / f"label-grid-{nb['shot']}.json",
                            base / "renders" / nb["file"], nb["subtitle"], repo, sr)

    in_sha1 = {p: fingerprint(repo / p) for p in ins}
    assert in_sha1 == in_sha0, "an input changed during the run"
    manifest = {
        "what": "MP11 팔 전체 분해도(보기용) — 입력 · 스크립트 · 산출 지문(sha256 · 글 파일은 CRLF → LF 로 잼) · 실행 기록. check_exploded.py 가 지금 파일과 견준다.",
        "unit": "MP11", "plan": "docs/design/061-arm-exploded-view.md",
        "inputs": in_sha0,
        "scripts": {f"src/cad/arm-v3-kg1-exploded/{n}": fingerprint(HERE / n) for n in SCRIPTS},
        "outputs": {p: fingerprint(base / p) for p in output_rel(prm)},
        "runs": runs, "numbered": lab,
        "command": "python -I -B -X utf8 src/cad/arm-v3-kg1-exploded/make_all.py",
        "python": sys.version.split()[0],
    }
    guard.write_bytes(base / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), repo, sr)
    print("MANIFEST", base / "manifest.json", "outputs", len(manifest["outputs"]))


if __name__ == "__main__":
    main()
