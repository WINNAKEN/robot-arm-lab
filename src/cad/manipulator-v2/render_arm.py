# -*- coding: utf-8 -*-
"""MP18 팔 전체 v2 그림 — 자세마다 조립 GLB(부품 색 = layout 목록 · 구매품 어림 = 어두운 회색) + 블렌더 Workbench 렌더(blender_arm.py).
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


CABLE = "#F97316"          # MP18 이어서: 케이블 길(고정 구간 · 고리) — 보기용 색


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
        m = L.ref_mesh(r)
        col = CABLE if "capsule" in r else ("#9CA3AF" if "annulus" in r else ("#7F1D1D" if ".TERM57_" in n else "#1F2937"))
        m.apply_transform(M)
        m.visual.face_colors = hexrgba(col)
        sc.add_geometry(m, node_name=n, geom_name=n)
    for lp in P["v2"].get("cable", {}).get("loops", []):                      # MP18 이어서: 관절 고리(보기용 — 두 고정점 사이 처진 곡선 · 길이는 검사 C10)
        A = (Tq[lp["a"]["link"]] @ np.linalg.inv(Ts0[lp["a"]["link"]]) @ np.array(list(lp["a"]["p"]) + [1.0]))[:3]
        B = (Tq[lp["b"]["link"]] @ np.linalg.inv(Ts0[lp["b"]["link"]]) @ np.array(list(lp["b"]["p"]) + [1.0]))[:3]
        sag = max(0.0, (lp["length"] - float(np.linalg.norm(B - A))) * 0.35)
        c1, c2 = A + (B - A) / 3 + [0.0, 0.0, -sag], A + 2 * (B - A) / 3 + [0.0, 0.0, -sag]
        t = np.linspace(0.0, 1.0, 24)[:, None]
        pts = ((1 - t) ** 3) * A + 3 * ((1 - t) ** 2) * t * c1 + 3 * (1 - t) * (t ** 2) * c2 + (t ** 3) * B
        m = trimesh.util.concatenate([L.capsule_mesh(a_, b_, P["v2"]["cable"]["bundle_d"] / 2 * 0.8) for a_, b_ in zip(pts[:-1], pts[1:])])
        m.visual.face_colors = hexrgba(CABLE)
        sc.add_geometry(m, node_name=f"LOOP.{lp['joint']}", geom_name=f"LOOP.{lp['joint']}")
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
        views = "back,isoback,iso,front,top" if name == "display" else "isoback"                # MP18: 앞 = +y(위팔 덮개 쪽) → back · isoback
        p = subprocess.run([str(a.blender), "-b", "-P", str(HERE / "blender_arm.py"), "--", str(glb), str(out / name), views], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        if p.returncode:
            raise SystemExit(f"blender rc {p.returncode}: {(p.stderr or p.stdout)[-1500:]}")
        rec[name] = {"q_deg": poses[name], "glb": glb.name if name == "display" else None, "glb_note": None if name == "display" else "scratch only (not committed)",
                     "glb_sha256": L.sha(glb), "pngs": sorted(x.name for x in out.glob(f"{name}-*.png"))}
        print(name, rec[name]["pngs"], flush=True)
    (out / "renders.json").write_bytes((json.dumps({"what": "MP18 보기용 그림(치수 원천 아님) — 부품 색 = layout · 구매품 어림 = 어두운 회색 · 57D 단자 어림 = 어두운 빨강 · 케이블 = 주황(고리는 처진 곡선 그림 — 길이는 검사 C10)", "poses": rec},
                                                    ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
