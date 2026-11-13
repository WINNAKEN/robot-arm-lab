# -*- coding: utf-8 -*-
"""MP4 A2 — 1:1 제품 외장 v2 조립(표시 자세)을 SolidCraft 로 만든다. v1 기구학(kinematics.json)을 그대로 쓴다.

사용: python build_product.py --cli <solidcraft-cli.exe> [--out <모델 폴더>] [--evidence <근거 폴더>]
산출: native `.solidcraft`(Base + Link1..6 · revolute 6) · STEP · 3MF · 등각/정면/측면 PNG · `bodies.json`(바디 → 링크 · 색 역할) ·
`build-commands.json`. 근거 폴더: 실행 결과 JSON · 표준 출력/오류."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from v2geom import Builder, Frame, Spec  # noqa: E402

ROOT = next((p for p in HERE.parents if (p / "models" / "armold-mks-concept-v1").exists()), Path(r"C:\projects\robot-arm-lab"))
V1 = ROOT / "models" / "armold-mks-concept-v1"


def run(cli, ev, label, argv):
    p = subprocess.run([str(cli), *map(str, argv)], capture_output=True, text=True, encoding="utf-8", timeout=1800,
                       env=dict(os.environ, SOLIDCRAFT_GPU="cpu"))
    (ev / f"{label}-stdout.txt").write_text(p.stdout, encoding="utf-8")
    (ev / f"{label}-stderr.txt").write_text(p.stderr, encoding="utf-8")
    if p.returncode:
        raise SystemExit(f"{label}: rc {p.returncode}: {p.stderr[-1500:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "models" / "armold-mks-product-v2")
    ap.add_argument("--evidence", type=Path, default=ROOT / ".dev" / "product-v2-evidence" / "build")
    ap.add_argument("--params", type=Path, default=HERE / "parameters.json")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    a.evidence.mkdir(parents=True, exist_ok=True)
    spec = Spec(a.params, V1)
    b = Builder(spec)
    b.cmd("document.metadata.set", values={"project": "robot-arm-lab", "part_number": "ARMOLD-TYPE-MKS-PRODUCT-V2", "revision": "product-exterior-v2",
                                           "description": "1:1 product exterior v2 on the v1 kinematics (display pose). Solid envelopes - NOT FOR FABRICATION."})
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
    b.cmd("component.activate", component="root")
    b.cmd("occurrence.ground", occurrence="Base:1", grounded=True)
    for j in spec.kin["joints"]:
        b.cmd("joint.as_built", type="revolute", a=j["parent"] + ":1", b=j["child"] + ":1", at={"point": j["origin_mm"], "z": j["axis_world"]},
              name=j["name"] + "_DISPLAY_ZERO", limits=[[-170, 170]])
    b.cmd("component.list", compact=True, bodies=True)
    b.cmd("joint.list")
    script = a.out / "build-commands.json"
    script.write_text(json.dumps({"commands": b.commands}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (a.out / "bodies.json").write_text(json.dumps({"bodies": b.bodies}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    native = a.out / "armold-type-mks-product-v2.solidcraft"
    run(a.cli, a.evidence, "main-build", ["run", script, "--save", native, "--out", a.out / "armold-type-mks-product-v2.step",
                                          "--out", a.out / "armold-type-mks-product-v2.3mf", "--results", "--json-out", a.evidence / "main-build-result.json"])
    run(a.cli, a.evidence, "main-eval", ["eval", native, "--json-out", a.evidence / "main-eval.json"])
    for view in ("iso", "front", "right"):
        run(a.cli, a.evidence, f"snapshot-{view}", ["snapshot", "--in", native, "--out", a.out / f"{view}.png", "--view", view, "--width", "1600",
                                                    "--height", "1200", "--no-grid", "--no-axes"])
    # v1 과 v2 를 같은 방향(iso · 같은 그림 크기 · 각자 화면 맞춤)으로 나란히
    from PIL import Image
    left, right = Image.open(V1 / "iso.png").convert("RGB"), Image.open(a.out / "iso.png").convert("RGB")
    both = Image.new("RGB", (left.width + right.width, max(left.height, right.height)), "white")
    both.paste(left, (0, 0))
    both.paste(right, (left.width, 0))
    both.save(a.out / "v1-v2-side-by-side.png")
    print(json.dumps({"native": str(native), "bodies": len(b.bodies)}))


if __name__ == "__main__":
    main()
