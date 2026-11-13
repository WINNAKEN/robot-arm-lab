# -*- coding: utf-8 -*-
"""MP7 — 1:1 제품 외장 v3(KMJH 브랜드)를 SolidCraft 로 만든다. 관절은 v1 기구학(kinematics.json) 그대로.

사용: python build_product.py --cli <solidcraft-cli.exe> [--out <모델 폴더>] [--evidence <근거 폴더>] [--scratch-root <격리 작업 뿌리>]
      [--control <양성 대조 이름>] [--no-snapshots]
산출: native `.solidcraft`(Base + Link1..6 · revolute 6) · STEP · 3MF · 바디마다 STL(`meshes/` — 블렌더 장면용 · 세계 좌표 mm · 표시 자세) ·
등각/정면/측면 PNG · `bodies.json`(바디 → 링크 · 색 역할 · 색) · `build-commands.json`. 근거 폴더: 실행 결과 JSON · 표준 출력/오류.

쓰기는 guard 로 거른다 — 폴더(checked_dir)는 만들기 전에, 파일(checked_file — 쓰거나 지우거나 SolidCraft 에 넘기는 마지막 대상 하나하나)은 그 직전에.
`--control` 은 검사가 실제로 잡는지 보려고 일부러 틀린 모델을 만든다 — 격리 작업 뿌리 아래로만."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard import checked_dir, checked_file, find_root  # noqa: E402
from v3geom import CONTROLS, Builder, Frame, Spec  # noqa: E402

ROOT = find_root(HERE)
V1 = ROOT / "models" / "armold-mks-concept-v1"
NAME = "kmjh-arm-product-v3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "models" / "armold-mks-product-v3")
    ap.add_argument("--evidence", type=Path, default=ROOT / ".dev" / "product-v3-evidence" / "build")
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    ap.add_argument("--scratch-root", type=Path, default=None)
    ap.add_argument("--control", choices=sorted(CONTROLS), default=None)
    ap.add_argument("--no-snapshots", action="store_true")
    a = ap.parse_args()
    out = checked_dir(a.out, ROOT, a.scratch_root)
    evidence = checked_dir(a.evidence, ROOT, a.scratch_root)
    if a.control:
        scratch = Path(os.path.abspath(a.scratch_root)).resolve() if a.scratch_root else None
        if scratch is None or scratch not in out.parents or scratch not in evidence.parents:
            raise SystemExit("a control model goes under --scratch-root only")

    def F_(p):
        return checked_file(p, ROOT, a.scratch_root)

    def run(label, argv):
        p = subprocess.run([str(a.cli), *map(str, argv)], capture_output=True, text=True, encoding="utf-8", timeout=1800,
                           env=dict(os.environ, SOLIDCRAFT_GPU="cpu"))
        F_(evidence / f"{label}-stdout.txt").write_text(p.stdout, encoding="utf-8")
        F_(evidence / f"{label}-stderr.txt").write_text(p.stderr, encoding="utf-8")
        if p.returncode:
            raise SystemExit(f"{label}: rc {p.returncode}: {p.stderr[-1500:]}")

    out.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    meshes = checked_dir(out / "meshes", ROOT, a.scratch_root)
    meshes.mkdir(exist_ok=True)
    for old in meshes.glob("*.stl"):
        F_(old).unlink()
    spec = Spec(a.params, V1, control=a.control)
    b = Builder(spec)
    b.cmd("document.metadata.set", values={"project": "robot-arm-lab", "part_number": "KMJH-ARM-PRODUCT-V3", "revision": "product-exterior-v3-kmjh-rev1-tool-kg1",
                                           "description": "1:1 product exterior v3 (KMJH brand) on the v1 kinematics (display pose). Solid envelopes - NOT FOR FABRICATION."})
    for k in range(7):
        comp = "Base" if k == 0 else f"Link{k}"
        b.cmd("component.activate", component="root")
        b.cmd("component.create", name=comp)
        if k == 0:
            F = Frame()
        else:
            j = spec.kin["joints"][k - 1]
            F = Frame(j["origin_mm"], j["R_child"])
        b.link(k, F)
        if a.control == "owner_both" and k == 5:
            j6 = spec.kin["joints"][5]
            b.tool_flange(Frame(j6["origin_mm"], j6["R_child"]), 5)       # 같은 형상 · 틀린 소속(Link5)
    b.cmd("component.activate", component="root")
    b.cmd("occurrence.ground", occurrence="Base:1", grounded=True)
    for j in spec.kin["joints"]:
        pt = list(j["origin_mm"])
        if a.control == "joint_origin" and j["name"] == "J3":
            pt[0] += 1.0
        b.cmd("joint.as_built", type="revolute", a=j["parent"] + ":1", b=j["child"] + ":1", at={"point": pt, "z": j["axis_world"]},
              name=j["name"] + "_DISPLAY_ZERO", limits=[[-170, 170]])
    for body in b.bodies:
        b.cmd("file.save_mesh", path=str(F_(meshes / f"{body['name']}.stl")), format="stl", bodies=[body["name"]], quality="fine")
    b.cmd("component.list", compact=True, bodies=True)
    b.cmd("joint.list")
    script = F_(out / "build-commands.json")
    script.write_text(json.dumps({"commands": b.commands}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    F_(out / "bodies.json").write_text(json.dumps({"bodies": b.bodies, "colors": spec.COLORS, "color_names": spec.p["brand"]["color_names"],
                                                   "control": a.control}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    native = F_(out / f"{NAME}.solidcraft")
    run("main-build", ["run", script, "--save", native, "--out", F_(out / f"{NAME}.step"), "--out", F_(out / f"{NAME}.3mf"),
                       "--results", "--json-out", F_(evidence / "main-build-result.json")])
    run("main-eval", ["eval", native, "--json-out", F_(evidence / "main-eval.json")])
    if not a.no_snapshots:
        for view in ("iso", "front", "right"):
            run(f"snapshot-{view}", ["snapshot", "--in", native, "--out", F_(out / f"{view}.png"), "--view", view, "--width", "1600",
                                     "--height", "1200", "--no-grid", "--no-axes"])
    # 출처 묶음(L4 R1 F1): 이 실행이 쓴 native · STL · 기록의 sha256 — 검사기가 지금 파일이 이 실행의 것인지 본다
    import hashlib

    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    prov = {"native": sha(native), "step": sha(out / f"{NAME}.step"), "3mf": sha(out / f"{NAME}.3mf"), "bodies_json": sha(out / "bodies.json"),
            "build_commands": sha(script), "main_eval": sha(evidence / "main-eval.json"),
            "stl": {body["name"]: sha(meshes / f"{body['name']}.stl") for body in b.bodies}, "control": a.control}
    F_(evidence / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"native": str(native), "bodies": len(b.bodies), "meshes": len(list(meshes.glob("*.stl"))), "control": a.control}))


if __name__ == "__main__":
    main()
