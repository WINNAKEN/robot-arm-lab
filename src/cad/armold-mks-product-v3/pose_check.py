# -*- coding: utf-8 -*-
"""MP7 갤러리 자세 검사 — 블렌더 없이, 커밋된 바디 STL(표시 자세 · mm)을 v1 관절 축으로 돌려 자세마다 다음을 스스로 계산한다.

- 관절각이 v1 의 ±170 도(예시 범위) 안인지.
- 서로 다른 링크의 바디 쌍마다 겹친 부피(manifold3d 불리언 · 상자 거름) — 표시 자세의 값이 기준선(접촉면 분할 오차).
- 링크 1 … 6 바디의 가장 낮은 점이 바닥(z = 0) 위로 여유만큼 떠 있는지.
- 이웃 아닌 링크 쌍(링크 번호 차 2 이상)의 꼭짓점 사이 최소 거리(근사 · 큰 삼각형에선 실제보다 큼) — 거의 닿는 곳을 표시만.

사용: python pose_check.py --model <v3 모델 폴더> --kin <v1 kinematics.json> --poses gallery_poses.json --out <json>
자세 변환은 blender_scene.py 의 expected() 와 같다 — 표시 자세의 관절 축으로 바깥 관절부터 안쪽으로 (q − pose_deg) 만큼 돌린다.
보기용 자세의 겹침 검사이지 충돌 모델 · 경로 검사가 아니다(자세 사이 움직임은 보지 않는다)."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import manifold3d as m3d
import numpy as np
import trimesh
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import checked_file, find_root  # noqa: E402

LIMIT_DEG = 170.0
FLOOR_CLEAR_MM = 5.0
OVERLAP_MM3 = 0.05      # 이보다 크면 「겹침」 — 표시 자세 기준선(접촉면 분할 오차)이 이 아래인지도 따로 본다
NEAR_MM = 2.0


def rot(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def posed(P, link, deltas, J):
    Q = P.copy()
    for k in range(link, 0, -1):
        if deltas[k - 1]:
            O, A = J[k - 1]
            Q = (Q - O) @ rot(A, deltas[k - 1]).T + O
    return Q


def manifold(v, f):
    m = m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(v, np.float32), tri_verts=np.asarray(f, np.uint32)))
    return m


def volume(m):
    return float(m.volume()) if hasattr(m, "volume") else float(m.get_volume())


def load_inputs(model, kin_path):
    """바디(STL 을 trimesh 로 · 점 합침) · v1 관절 축 J · 표시 자세 pose_deg."""
    bd = json.loads((Path(model) / "bodies.json").read_text(encoding="utf-8"))
    kin = json.loads(Path(kin_path).read_text(encoding="utf-8"))
    J = [(np.asarray(j["origin_mm"], float), np.asarray(j["axis_world"], float)) for j in kin["joints"]]
    pose_deg = [float(j["pose_deg"]) for j in kin["joints"]]
    bodies = []
    for b in bd["bodies"]:
        tm = trimesh.load(Path(model) / "meshes" / f"{b['name']}.stl", force="mesh", process=True)
        mf = manifold(tm.vertices, tm.faces)
        bodies.append({"name": b["name"], "link": b["link"], "v": np.asarray(tm.vertices, float), "f": np.asarray(tm.faces),
                       "status": str(mf.status()), "watertight": bool(tm.is_watertight)})
    return bodies, J, pose_deg


def evaluate(bodies, J, pose_deg, q, name):
    """자세 하나(q = 기하 영점 기준 도) — 관절 범위 · 다른 링크 바디 쌍의 겹친 부피 · 이웃 아닌 링크 근접 · 바닥 여유. 반환 = 기록 한 줄 + 돌린 점."""
    q = [float(x) for x in q]
    deltas = [qq - pd for qq, pd in zip(q, pose_deg)]
    V = [posed(b["v"], b["link"], deltas, J) for b in bodies]
    lo = [v.min(axis=0) for v in V]
    hi = [v.max(axis=0) for v in V]
    M = [manifold(v, b["f"]) for v, b in zip(V, bodies)]
    overlaps, near, pairs_checked = [], [], 0
    for i in range(len(bodies)):
        for k in range(i + 1, len(bodies)):
            li, lk = bodies[i]["link"], bodies[k]["link"]
            if li == lk:
                continue
            if np.any(lo[i] > hi[k] + 10.0) or np.any(lo[k] > hi[i] + 10.0):
                continue
            if not (np.any(lo[i] > hi[k] + 0.01) or np.any(lo[k] > hi[i] + 0.01)):
                pairs_checked += 1
                vol = volume(M[i] ^ M[k])
                if vol > 1e-6:
                    overlaps.append({"a": bodies[i]["name"], "b": bodies[k]["name"], "links": [li, lk], "mm3": round(vol, 6)})
            if abs(li - lk) >= 2:
                d = float(cKDTree(V[k]).query(V[i], k=1)[0].min())
                if d < 10.0:
                    near.append({"a": bodies[i]["name"], "b": bodies[k]["name"], "links": [li, lk], "approx_gap_mm": round(d, 3)})
    moving_min_z = min(float(V[i][:, 2].min()) for i, b in enumerate(bodies) if b["link"] >= 1)
    base_min_z = min(float(V[i][:, 2].min()) for i, b in enumerate(bodies) if b["link"] == 0)
    big = [o for o in overlaps if o["mm3"] > OVERLAP_MM3]
    close = [n for n in near if n["approx_gap_mm"] < NEAR_MM]
    row = {"name": name, "q_deg": q, "delta_from_display_deg": deltas,
           "within_limits": all(abs(x) <= LIMIT_DEG for x in q),
           "pairs_checked": pairs_checked, "overlaps": sorted(overlaps, key=lambda o: -o["mm3"]), "max_overlap_mm3": max([o["mm3"] for o in overlaps], default=0.0),
           "near_non_adjacent": sorted(near, key=lambda n: n["approx_gap_mm"]),
           "moving_min_z_mm": moving_min_z, "base_min_z_mm": base_min_z,
           "ok": all(abs(x) <= LIMIT_DEG for x in q) and not big and not close and moving_min_z >= FLOOR_CLEAR_MM}
    return row, V, big, close


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--kin", required=True, type=Path)
    ap.add_argument("--poses", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--scratch-root", type=Path, default=None)
    a = ap.parse_args()
    root = find_root(Path(__file__).resolve().parent)
    out = checked_file(a.out, root, a.scratch_root)

    poses = json.loads(a.poses.read_text(encoding="utf-8"))["poses"]
    bodies, J, pose_deg = load_inputs(a.model, a.kin)

    report = {"limit_deg": LIMIT_DEG, "floor_clear_mm": FLOOR_CLEAR_MM, "overlap_mm3": OVERLAP_MM3, "near_mm": NEAR_MM,
              "mesh_status": {b["name"]: {"manifold": b["status"], "watertight": b["watertight"]} for b in bodies}, "poses": []}
    for pz in poses:
        row, _V, big, close = evaluate(bodies, J, pose_deg, pz["q_deg"], pz["name"])
        moving_min_z, pairs_checked = row["moving_min_z_mm"], row["pairs_checked"]
        report["poses"].append(row)
        print(f"{pz['name']:<11} ok={row['ok']} max_overlap={row['max_overlap_mm3']:.4f} mm3 overlaps>{OVERLAP_MM3}={len(big)} "
              f"near<{NEAR_MM}={len(close)} min_z={moving_min_z:.1f} pairs={pairs_checked}")
        for o in big[:6]:
            print("   overlap", o)
        for n in close[:6]:
            print("   near", n)
    report["mesh_all_manifold"] = all(r["manifold"].endswith("NoError") for r in report["mesh_status"].values())
    report["all_ok"] = report["mesh_all_manifold"] and all(r["ok"] for r in report["poses"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("POSE_CHECK", "OK" if report["all_ok"] else "FAILED", "manifold_all", report["mesh_all_manifold"])


if __name__ == "__main__":
    main()
