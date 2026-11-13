# -*- coding: utf-8 -*-
"""MP6 — 부품 STL 을 출력 방향(조립과 같은 z 위 · 판에 놓이는 면 = 부품의 가장 낮은 면)으로 한 판에 놓고, 판 STL · 배치 · 부품별 아래로 향한 면의
무리(기록용 — 상자 크기라 고리 턱도 지름으로 잰다 · 지지대 판정은 printprep 의 Bambu Studio 권고)를 기록한다. 출력 준비는 printprep 가 이 판 STL 로 한다.

사용: python print_plate.py --parts <parts 폴더> --out <판 STL> --report <json> [--bed 350 320]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh

# 판에 올릴 부품과 개수(원판은 같은 부품 둘 — DISC_1 의 STL 을 두 번)
PLATE = [("HOUSING_BASE", 1), ("HOUSING_CAP", 1), ("RETAINER", 1), ("DISC_1", 2), ("CARRIER", 1), ("OUTPUT_FLANGE", 1), ("CAM_LOWER", 1),
         ("CAM_UPPER", 1), ("FIT_STRIP", 1), ("WASHER_T2p0", 1), ("WASHER_T2p2", 1), ("WASHER_T2p4", 1), ("GAUGE", 1)]
GAP = 8.0


def downward_faces(mesh, z_floor, cos_lim=0.7071):
    """판 위(z > 바닥 + 0.2)에서 아래를 향한(법선 z < −cos 45°) 면 — 이어진 무리마다 수평 크기(지지 없이 걸칠 거리의 어림)와 넓이."""
    n = mesh.face_normals
    c = mesh.triangles_center
    sel = np.where((n[:, 2] < -cos_lim) & (c[:, 2] > z_floor + 0.2))[0]
    if len(sel) == 0:
        return []
    sub = mesh.submesh([sel], append=True)
    groups = trimesh.graph.connected_components(sub.face_adjacency, nodes=np.arange(len(sub.faces)))
    out = []
    for g in groups:
        tri = sub.triangles[g].reshape(-1, 3)
        ext = tri[:, :2].max(axis=0) - tri[:, :2].min(axis=0)
        out.append({"z": float(tri[:, 2].mean()), "span_mm": float(max(ext)), "short_span_mm": float(min(ext)), "area_mm2": float(sub.area_faces[g].sum())})
    return sorted(out, key=lambda d: -d["area_mm2"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--bed", type=float, nargs=2, default=[350.0, 320.0])
    ap.add_argument("--row-width", type=float, default=280.0,
                    help="한 줄 최대 폭 — H2D 는 노즐 둘이라 한 노즐로 닿는 폭이 판 350 보다 좁다(338.5 mm 판을 Bambu Studio 가 「판 밖」 으로 거절 · 2026-10-25)")
    a = ap.parse_args()
    items, source_sha = [], {}
    for name, count in PLATE:
        source_sha[name] = hashlib.sha256((a.parts / f"{name}.stl").read_bytes()).hexdigest()   # 판이 어느 부품 STL 에서 왔는가(MP6 L4 R2 F2)
        m = trimesh.load(a.parts / f"{name}.stl", force="mesh")
        lo = m.bounds[0]
        m.apply_translation([-lo[0], -lo[1], -lo[2]])
        for k in range(count):
            items.append((f"{name}#{k + 1}" if count > 1 else name, m.copy()))
    # 큰 것부터 줄 채우기(선반 배치)
    items.sort(key=lambda it: -(it[1].extents[0] * it[1].extents[1]))
    x = y = row_h = 0.0
    placed = []
    W, H = a.bed
    for name, m in items:
        w, d = m.extents[0], m.extents[1]
        if x > 0 and x + w > a.row_width:
            x, y, row_h = 0.0, y + row_h + GAP, 0.0
        m.apply_translation([x, y, 0])
        placed.append((name, m))
        x += w + GAP
        row_h = max(row_h, d)
    # 판 전체를 출력대 한가운데로
    allb = np.array([m.bounds for _n, m in placed])
    lo, hi = allb[:, 0, :2].min(axis=0), allb[:, 1, :2].max(axis=0)
    shift = np.array([W / 2, H / 2]) - (lo + hi) / 2
    for _n, m in placed:
        m.apply_translation([shift[0], shift[1], 0])
    plate = trimesh.util.concatenate([m for _n, m in placed])
    size = plate.extents
    fits = bool(plate.bounds[0][0] >= 0 and plate.bounds[0][1] >= 0 and plate.bounds[1][0] <= W and plate.bounds[1][1] <= H
                and size[0] <= a.row_width)
    overlaps = []
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            bi, bj = placed[i][1].bounds, placed[j][1].bounds
            if bi[0][0] < bj[1][0] and bj[0][0] < bi[1][0] and bi[0][1] < bj[1][1] and bj[0][1] < bi[1][1]:
                overlaps.append([placed[i][0], placed[j][0]])
    report = {"bed_mm": [W, H], "row_width_mm": a.row_width, "plate_bounds_mm": plate.bounds.tolist(), "plate_size_mm": size.tolist(), "fits_bed": fits,
              "bbox_overlaps": overlaps, "source_part_sha256": source_sha, "parts": []}
    for name, m in placed:
        dn = downward_faces(m, m.bounds[0][2])
        report["parts"].append({"name": name, "bounds_mm": m.bounds.tolist(), "volume_mm3": float(m.volume), "watertight": bool(m.is_watertight),
                                "downward_groups": len(dn), "largest_downward_span_mm": max((g["span_mm"] for g in dn), default=0.0),
                                "downward": dn[:6]})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    plate.export(a.out)
    report["plate_sha256"] = hashlib.sha256(a.out.read_bytes()).hexdigest()    # printprep 보고서의 model.sha256 과 같아야 같은 판
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("plate", [round(v, 1) for v in size], "fits", fits, "overlaps", overlaps)
    for p in report["parts"]:
        print(f"  {p['name']:16s} watertight {p['watertight']} downward groups {p['downward_groups']} largest span {p['largest_downward_span_mm']:.1f}")


if __name__ == "__main__":
    main()
