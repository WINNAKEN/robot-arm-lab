# -*- coding: utf-8 -*-
"""MP17 팔 전체 그림 — 자세마다 조립 GLB(부품 색 = layout 목록 · 구매품 어림 = 어두운 회색) + 블렌더 Workbench 렌더(blender_arm.py).
보기용(치수 원천 아님). 표시 자세 GLB 만 모델 폴더에 남기고 다른 자세 GLB 는 저장소 밖 작업 폴더에(크기 — 그림 PNG 는 모두 renders/).
사용: python render_arm.py --blender <blender.exe> --scratch <저장소 밖 작업 폴더> [--poses display,zero,ready]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import trimesh

import layout as L

HERE = Path(__file__).resolve().parent


def hexrgba(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [255]


def scene_at(P, q):
    cat, Fr, Ts0, Tq = L.catalog(P), L.frames(P), L.link_transforms(P, [0.0] * 6), L.link_transforms(P, q)
    sc = trimesh.Scene()
    for n, c in cat.items():
        if c["kind"] == "inner":
            continue
        m = trimesh.load(c["path"], force="mesh")
        m.apply_transform(Tq[c["link"]] @ np.linalg.inv(Ts0[c["link"]]) @ Fr[c["frame"]])
        m.visual.face_colors = hexrgba(c["color"])
        sc.add_geometry(m, node_name=n, geom_name=n)
    for n, r in L.refs(P).items():
        M = Tq[r["link"]] @ np.linalg.inv(Ts0[r["link"]]) @ Fr[r["frame"]]
        if "boxes" in r:
            m = trimesh.util.concatenate([trimesh.creation.box(bounds=[[b[0], b[2], b[4]], [b[1], b[3], b[5]]]) for b in r["boxes"]])
            col = "#1F2937"
        else:
            ri, ro, z0, z1 = r["annulus"]
            m = trimesh.creation.annulus(r_min=ri, r_max=ro, height=z1 - z0, sections=128)
            m.apply_translation([0, 0, (z0 + z1) / 2])
            col = "#9CA3AF"
        m.apply_transform(M)
        m.visual.face_colors = hexrgba(col)
        sc.add_geometry(m, node_name=n, geom_name=n)
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", required=True, type=Path)
    ap.add_argument("--poses", default="display,zero,ready")
    ap.add_argument("--scratch", type=Path, default=None, help="outside the repo - GLBs of the poses other than display")
    a = ap.parse_args()
    P = L.load()
    poses = {"display": P["poses"]["display_deg"], "zero": [0.0] * 6, "ready": P["poses"]["ready_deg"]}
    out = L.MODEL / "renders"
    out.mkdir(parents=True, exist_ok=True)
    rec = {}
    for name in a.poses.split(","):
        sc = scene_at(P, poses[name])
        if name == "display":
            glb = L.MODEL / f"{L.NAME}-{name}.glb"
        else:
            if a.scratch is None:
                raise SystemExit("--scratch is needed for the poses other than display")
            sd = a.scratch.resolve() / "render"
            assert L.ROOT.resolve() not in sd.parents and sd != L.ROOT.resolve()
            sd.mkdir(parents=True, exist_ok=True)
            glb = sd / f"{L.NAME}-{name}.glb"
        glb.write_bytes(sc.export(file_type="glb"))
        views = "iso,isoback,front,top" if name == "display" else "iso"
        p = subprocess.run([str(a.blender), "-b", "-P", str(HERE / "blender_arm.py"), "--", str(glb), str(out / name), views], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        if p.returncode:
            raise SystemExit(f"blender rc {p.returncode}: {(p.stderr or p.stdout)[-1500:]}")
        rec[name] = {"q_deg": poses[name], "glb": glb.name if name == "display" else None, "glb_note": None if name == "display" else "scratch only (not committed)",
                     "glb_sha256": L.sha(glb), "pngs": sorted(x.name for x in out.glob(f"{name}-*.png"))}
        print(name, rec[name]["pngs"], flush=True)
    (out / "renders.json").write_bytes((json.dumps({"what": "MP17 보기용 그림(치수 원천 아님) — 부품 색 = layout · 구매품 어림 = 어두운 회색", "poses": rec},
                                                    ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
