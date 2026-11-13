# -*- coding: utf-8 -*-
"""MP7 동작 영상 경로 검사 — motion_plan.json 의 이동을 프레임보다 촘촘히(기본 8 배 — 샘플 사이 꼭짓점 이동 약 4.5 mm 이하 · 2026-10-27 2 배는 18 mm) 나눈 자세마다 pose_check.evaluate 와 같은 판정을 한다.

- 판정(자세마다): 관절각 ±170 도 안 · 서로 다른 링크 바디 쌍의 겹친 부피 ≤ 0.05 mm³ · 이웃 아닌 링크 꼭짓점 거리 ≥ 2 mm(근사) · 움직이는 링크 바닥 위 ≥ 5 mm.
- 이웃한 샘플 사이에 바디 꼭짓점이 움직인 최대 거리도 적는다(샘플 사이는 검사하지 않음 — 그 거리가 「샘플 사이에 놓칠 수 있는 크기」의 기준).
- 한 바퀴 영상의 자세(계획의 turntable.pose = 표시 자세)도 같은 판정으로 한 번 검사해 `turntable` 에 적는다.
- 통과(all_ok) = 모든 바디 메시가 닫힘(manifold NoError — pose_check 와 같은 관문) · 모든 샘플과 한 바퀴 자세 통과 · 검사 시작과 끝의 입력 sha256 이 같음.
- 기록에 입력 sha256(bodies.json · STL 47 · kinematics · 계획 · 자세 · 검사 코드)을 남긴다 — blender_motion.py · motion_encode.py 가 지금 파일과 대조.
  블렌더 · 묶기 단계는 per_frame ≥ 8 · 샘플 사이 꼭짓점 이동 ≤ 5 mm 인 기록만 받는다.

사용: python path_check.py --model <v3 모델> --kin <v1 kinematics.json> --poses gallery_poses.json --plan motion_plan.json --out <json> [--per-frame 8] [--workers N]"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_path  # noqa: E402
from guard import checked_file, find_root  # noqa: E402
from pose_check import FLOOR_CLEAR_MM, LIMIT_DEG, NEAR_MM, OVERLAP_MM3, evaluate, load_inputs, posed  # noqa: E402

_W = {}


def input_hashes(model, kin, plan, poses):
    """검사가 읽은 입력의 sha256 — 블렌더 · 묶기 단계가 지금 파일과 같은지 대조한다(검토 PC-2 · DOC-7: 메시를 다시 만든 뒤 낡은 검사 기록이 통과하지 않게)."""
    model = Path(model)
    bd = json.loads((model / "bodies.json").read_text(encoding="utf-8"))
    h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()       # noqa: E731
    here = Path(__file__).resolve().parent
    return {"bodies_json": h(model / "bodies.json"), "kinematics": h(kin), "plan": h(plan), "poses": h(poses),
            "stl": {b["name"]: h(model / "meshes" / f"{b['name']}.stl") for b in bd["bodies"]},
            "code": {n: h(here / n) for n in ("pose_check.py", "path_check.py", "motion_path.py")}}


def _init(model, kin):
    _W["bodies"], _W["J"], _W["pose_deg"] = load_inputs(model, kin)


def _one(job):
    idx, t, q, kind = job
    row, _V, big, close = evaluate(_W["bodies"], _W["J"], _W["pose_deg"], q, f"t={t:.4f}")
    return idx, {"i": idx, "t_s": round(t, 6), "kind": kind, "q_deg": [round(x, 6) for x in q], "ok": row["ok"],
                 "within_limits": row["within_limits"], "pairs_checked": row["pairs_checked"], "max_overlap_mm3": row["max_overlap_mm3"],
                 "overlaps_over_limit": big, "near_under_limit": close,
                 "min_near_non_adjacent_mm": min([n["approx_gap_mm"] for n in row["near_non_adjacent"]], default=None),
                 "moving_min_z_mm": round(row["moving_min_z_mm"], 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--kin", required=True, type=Path)
    ap.add_argument("--poses", required=True, type=Path)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--per-frame", type=int, default=motion_path.MIN_PER_FRAME)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--scratch-root", type=Path, default=None)
    a = ap.parse_args()
    root = find_root(Path(__file__).resolve().parent)
    out = checked_file(a.out, root, a.scratch_root)
    inputs_start = input_hashes(a.model, a.kin, a.plan, a.poses)      # 검토 R2-PC-B: 검사 시작 때와 끝날 때의 입력이 같아야 통과
    plan, poses = motion_path.load(a.plan, a.poses)
    samples = motion_path.path_samples(plan, poses, a.per_frame)
    jobs = [(i, t, q, kind) for i, (t, q, kind) in enumerate(samples)]
    rows = [None] * len(jobs)
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(str(a.model), str(a.kin))) as ex:
        for n, (idx, row) in enumerate(ex.map(_one, jobs, chunksize=4), start=1):
            rows[idx] = row
            if not row["ok"]:
                print("PATH_FAIL", idx, row["t_s"], row["q_deg"], row["overlaps_over_limit"][:3], row["near_under_limit"][:3], row["moving_min_z_mm"], flush=True)
            if n % 50 == 0:
                print("PATH_PROGRESS", n, "/", len(jobs), flush=True)
    bodies, J, pose_deg = load_inputs(a.model, a.kin)          # 샘플 사이 이동 거리(메인 프로세스에서 같은 회전으로) · 메시 닫힘(pose_check 와 같은 관문)
    mesh_status = {b["name"]: {"manifold": b["status"], "watertight": b["watertight"]} for b in bodies}
    step_move, prev = [], None
    for i, (t, q, kind) in enumerate(samples):
        V = [posed(b["v"], b["link"], [x - p for x, p in zip(q, pose_deg)], J) for b in bodies]
        if prev is not None and kind == "move" and samples[i - 1][2] == "move" and t > samples[i - 1][0]:
            step_move.append(max(float(np.max(np.linalg.norm(v1 - v0, axis=1))) for v0, v1 in zip(prev, V)))
        prev = V
    # 한 바퀴 영상의 자세(표시 자세)도 같은 판정으로 — 검토 R2-PC-D: 한 바퀴 영상도 입력 sha256 이 있는 이 기록으로 묶는다
    tt_name = plan["turntable"]["pose"]
    tt_row, _V, tt_big, tt_close = evaluate(bodies, J, pose_deg, poses[tt_name], tt_name)
    turntable = {"pose": tt_name, "q_deg": tt_row["q_deg"], "ok": tt_row["ok"], "max_overlap_mm3": tt_row["max_overlap_mm3"],
                 "overlaps_over_limit": tt_big, "near_under_limit": tt_close, "moving_min_z_mm": round(tt_row["moving_min_z_mm"], 4),
                 "within_limits": tt_row["within_limits"], "pairs_checked": tt_row["pairs_checked"]}
    inputs_end = input_hashes(a.model, a.kin, a.plan, a.poses)
    fps = plan["fps"]
    report = {"criteria": {"limit_deg": LIMIT_DEG, "overlap_mm3": OVERLAP_MM3, "near_mm": NEAR_MM, "floor_clear_mm": FLOOR_CLEAR_MM},
              "fps": fps, "per_frame": a.per_frame, "duration_s": motion_path.duration(plan, poses),
              "segments": [{"t0": s[0], "t1": s[1], "from": s[2], "to": s[3], "kind": s[4]} for s in motion_path.segments(plan, poses)],
              "samples": len(rows), "failed": [r["i"] for r in rows if not r["ok"]],
              "max_overlap_mm3": max(r["max_overlap_mm3"] for r in rows),
              "min_moving_z_mm": min(r["moving_min_z_mm"] for r in rows),
              "min_near_non_adjacent_mm": min([r["min_near_non_adjacent_mm"] for r in rows if r["min_near_non_adjacent_mm"] is not None], default=None),
              "max_vertex_step_between_samples_mm": max(step_move, default=0.0),
              "inputs": inputs_start, "inputs_unchanged_during_check": inputs_end == inputs_start,
              "mesh_status": mesh_status, "mesh_all_manifold": all(r["manifold"].endswith("NoError") for r in mesh_status.values()),
              "turntable": turntable,
              "rows": rows}
    # 2026-10-27 비작성자 검토 PC-1: 닫히지 않은 메시는 겹친 부피가 조용히 0 이 된다 → pose_check 처럼 메시 닫힘을 통과 조건에
    report["all_ok"] = (report["mesh_all_manifold"] and report["inputs_unchanged_during_check"] and turntable["ok"]
                        and not report["failed"] and len(rows) == len(samples))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")        # 한 줄(샘플 수천 개)
    print("PATH_CHECK", "OK" if report["all_ok"] else "FAILED", "samples", len(rows), "max_overlap", report["max_overlap_mm3"],
          "min_z", report["min_moving_z_mm"], "min_near", report["min_near_non_adjacent_mm"], "max_step", round(report["max_vertex_step_between_samples_mm"], 3))


if __name__ == "__main__":
    main()
